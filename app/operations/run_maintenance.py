"""Operational CLI entry point for Increment #25C's automated economic
maintenance -- one bounded sweep per invocation.

    python -m app.operations.run_maintenance [--as-of-date YYYY-MM-DD]

Frozen and normative in docs/product/automated-economic-maintenance-v1.md
(§17/§41/§47/§55): this script owns exactly one bounded sweep's worth
of ORCHESTRATION -- discover due release occurrences, invoke the
existing, unmodified `ReleaseProcessingService`/`try_acquire_and_process_occurrence`
per occurrence, record sweep-level operational health -- and then
terminates. It does NOT loop, does NOT sleep, and does NOT schedule
itself; an external scheduler (cron, a platform's own scheduled-task
feature, or any equivalent) is responsible for invoking this script
periodically (§15/§55) -- this script has no opinion about, and no
code path depends on, how or how often it is invoked.

This is deliberately a SEPARATE script from `app.operations.process_release`,
never a mode flag on it -- the existing single-occurrence, explicit-id
CLI remains completely unmodified in shape (only gaining the shared
advisory lock, §59) and available for manual/operator use; this script
is the new, additive "process all due occurrences" entry point (§47),
reusing that same underlying service and the same locking mechanism
so the two paths can never diverge in safety.

No business logic lives here. This module only: parses arguments,
resolves configuration, delegates the entire sweep to
`MaintenanceOrchestrator`, renders a safe/structured summary, and maps
outcomes to an exit code. Every economic, persistence, and due-work
decision belongs to `app.services.maintenance`/`app.services.release_processing`,
never to this file.

Exit codes (frozen contract's own source prompt §42 -- an external
scheduler must be able to distinguish three outcomes):
  0 -- the sweep completed and no occurrence ended in a failure status.
  1 -- the sweep completed, but at least one occurrence ended
       `PARTIAL_FAILURE`/`FAILED_PROVIDER` or a database-layer failure
       (`failed_count > 0`) -- the sweep record itself still exists
       and is finished; see its own counts for detail.
  2 -- a fatal/configuration failure: the sweep could not even start
       or complete its own orchestration (missing configuration, or a
       database failure during sweep-start/due-work discovery/sweep-
       finish, outside any single occurrence's own processing). The
       sweep record, if one was already started, is left with
       `finished_at IS NULL` -- the intentional, honest signal this
       case produces (frozen contract §52/§25), never papered over
       with a fabricated "finished" row.

Safety: never prints an API key, a database URL, a raw provider
response body, generated SQL, or a stack trace that could contain a
credential -- mirrors `app.operations.process_release`'s own identical
discipline exactly.
"""

import argparse
import sys
from datetime import date, datetime, timezone

from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.clients.fred import FREDClient
from app.core.config import settings
from app.services.maintenance import DEFAULT_RETRY_WINDOW_DAYS, MaintenanceOrchestrator, MaintenanceSweepOutcome


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    as_of_date = args.as_of_date or datetime.now(timezone.utc).date()

    if not settings.fred_api_key:
        print("Operational failure: FRED integration is not configured on this server.", file=sys.stderr)
        return 2
    if not settings.database_url:
        print("Operational failure: database is not configured on this server.", file=sys.stderr)
        return 2

    client = FREDClient(api_key=settings.fred_api_key, timeout=settings.fred_timeout_seconds)
    orchestrator = MaintenanceOrchestrator(client)

    try:
        outcome = orchestrator.run_sweep(as_of_date, retry_window_days=args.retry_window_days)
    except OperationalError:
        print("Operational failure: database is currently unavailable.", file=sys.stderr)
        return 2
    except SQLAlchemyError:
        print("Operational failure: a database error occurred while running this maintenance sweep.", file=sys.stderr)
        return 2

    _print_summary(outcome)
    return 1 if outcome.failed_count > 0 else 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.operations.run_maintenance",
        description=(
            "Run one bounded automated-maintenance sweep: discover every mapped release occurrence "
            "currently due for a check (docs/product/automated-economic-maintenance-v1.md §8), and process "
            "each one via the existing, unmodified release-processing service. Runs once and terminates -- "
            "an external scheduler is responsible for invoking this periodically."
        ),
    )
    parser.add_argument(
        "--as-of-date",
        type=_parse_date,
        default=None,
        metavar="YYYY-MM-DD",
        help="Explicit as-of date for due-work eligibility. Defaults to today (UTC) if omitted.",
    )
    parser.add_argument(
        "--retry-window-days",
        type=int,
        default=DEFAULT_RETRY_WINDOW_DAYS,
        metavar="N",
        help=(
            "Operator-tunable retry window (frozen contract §14 -- a tunable operational parameter, "
            f"not an empirically measured economic fact; default {DEFAULT_RETRY_WINDOW_DAYS} days)."
        ),
    )
    return parser


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"'{value}' is not a valid YYYY-MM-DD date.") from exc


def _print_summary(outcome: MaintenanceSweepOutcome) -> None:
    print(f"Sweep: {outcome.sweep_id}")
    print(f"Started: {outcome.started_at.isoformat()}")
    print(f"Finished: {outcome.finished_at.isoformat()}")
    print(f"Due occurrences: {outcome.due_count}")
    print(f"Processed: {outcome.processed_count}")
    print(f"Skipped (lock contention): {outcome.skipped_lock_count}")
    print(f"Failed: {outcome.failed_count}")
    if outcome.database_failure_occurrence_ids:
        ids = ", ".join(str(occurrence_id) for occurrence_id in outcome.database_failure_occurrence_ids)
        print(f"  Database-layer failures (no ReleaseCheckRun row persisted for these attempts): {ids}")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
