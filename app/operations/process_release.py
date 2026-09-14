"""Operational CLI entry point for Increment #18's release-driven
update pipeline (extended in #20D.2 to also cover Employment
Situation/Labor -- this file itself required no change; see below).

    python -m app.operations.process_release --occurrence-id <id> [--as-of-date YYYY-MM-DD]

This is deliberately the ONLY way to trigger release processing in
#18 -- there is no public HTTP mutation endpoint (see
docs/architecture/release-processing-v1.md's security section: the
project has no authentication anywhere, and release processing issues
external provider requests and canonical database writes, which should
not become another unauthenticated public mutation surface). Running
this script is an operational action, controlled outside normal
end-user HTTP traffic.

No business logic lives here. This module only: parses arguments,
resolves configuration and opens one real database transaction,
delegates the entire decision to `ReleaseProcessingService`, renders a
safe/structured summary, and maps outcomes to an exit code. Every
economic and persistence decision belongs to
`app.services.release_processing`, never to this file.

Safety: never prints an API key, a database URL, a raw provider
response body, generated SQL, or a stack trace that could contain a
credential -- every error path below prints one short, generic,
already-safe message (the same messages `app.api.releases`/
`app.api.series` already use for the equivalent HTTP failure).
"""

import argparse
import sys
from datetime import date, datetime, timezone

from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.clients.fred import FREDClient
from app.core.config import settings
from app.db.session import session_scope
from app.models.release_processing import ReleaseCheckRunResult
from app.services.release_processing import OccurrenceNotEligibleError, OccurrenceNotFoundError, ReleaseProcessingService

_FAILURE_STATUSES = frozenset({"PARTIAL_FAILURE", "FAILED_PROVIDER"})


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    as_of_date = args.as_of_date or datetime.now(timezone.utc).date()

    if not settings.fred_api_key:
        print("Operational failure: FRED integration is not configured on this server.", file=sys.stderr)
        return 1
    if not settings.database_url:
        print("Operational failure: database is not configured on this server.", file=sys.stderr)
        return 1

    client = FREDClient(api_key=settings.fred_api_key, timeout=settings.fred_timeout_seconds)
    service = ReleaseProcessingService(client)

    try:
        with session_scope() as session:
            result = service.process_occurrence(args.occurrence_id, session, as_of_date)
    except OccurrenceNotFoundError as exc:
        print(f"Operational failure: {exc}", file=sys.stderr)
        return 1
    except OccurrenceNotEligibleError as exc:
        print(f"Operational failure: {exc}", file=sys.stderr)
        return 1
    except OperationalError:
        print("Operational failure: database is currently unavailable.", file=sys.stderr)
        return 1
    except SQLAlchemyError:
        print("Operational failure: a database error occurred while processing this release occurrence.", file=sys.stderr)
        return 1

    _print_summary(result)
    return 1 if result.status in _FAILURE_STATUSES else 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.operations.process_release",
        description=(
            "Process one release occurrence: fetch its mapped canonical series from FRED over a bounded "
            "five-year window, detect and persist genuine NEW/REVISED observation changes, and compute+persist "
            "any resulting deterministic Inflation or Labor analytical consequence."
        ),
    )
    parser.add_argument("--occurrence-id", type=int, required=True, help="The internal ReleaseOccurrence id to process.")
    parser.add_argument(
        "--as-of-date",
        type=_parse_date,
        default=None,
        metavar="YYYY-MM-DD",
        help="Explicit as-of date for eligibility and the five-year lookback window. Defaults to today (UTC) if omitted.",
    )
    return parser


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"'{value}' is not a valid YYYY-MM-DD date.") from exc


def _print_summary(result: ReleaseCheckRunResult) -> None:
    succeeded = [outcome for outcome in result.series_outcomes if outcome.succeeded]
    failed = [outcome for outcome in result.series_outcomes if not outcome.succeeded]
    new_count = sum(1 for change in result.observation_changes if change.change_type == "NEW")
    revised_count = sum(1 for change in result.observation_changes if change.change_type == "REVISED")

    print(f"Release occurrence: {result.release_occurrence_id}")
    print(f"Status: {result.status}")
    print(f"Started: {result.started_at.isoformat()}")
    print(f"Completed: {result.completed_at.isoformat()}")
    print(f"Series checked: {len(succeeded)} succeeded, {len(failed)} failed")
    for outcome in succeeded:
        print(
            f"  {outcome.series_id}: {outcome.new_count} new observation detected, "
            f"{outcome.revised_count} revision detected, {outcome.unchanged_count} no change detected"
        )
    for outcome in failed:
        print(f"  {outcome.series_id}: provider check failed -- {outcome.error}")
    print(f"New observation count: {new_count}")
    print(f"Revision count: {revised_count}")
    print(f"Analysis-event count: {len(result.analysis_changes)}")
    for event in result.analysis_changes:
        print(
            f"  {event.component} {event.event_type} {event.field}: "
            f"{event.previous_value} -> {event.current_value} (period {event.evaluation_period.isoformat()})"
        )


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
