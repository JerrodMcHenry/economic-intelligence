"""Read-only operator CLI for Increment #26E's maintenance-worker
heartbeat. See docs/product/production-reliability-deployment-v1.md
(#26B) §26/§54.

    python -m app.operations.maintenance_health [--json]
        [--stale-threshold-hours N] [--unfinished-grace-minutes N]

Never mutates anything, never calls FRED/OpenAI, never performs an
economic calculation, never triggers a maintenance sweep. Checks
schema compatibility FIRST (reusing Increment #26C's own shared
`check_schema_compatibility` -- never a second, independently-written
check) and refuses to interpret sweep history at all if the schema is
not compatible, since a stale/incompatible schema would make any
sweep-history reading unreliable in ways this command cannot detect.

Exit codes:
  0 -- HEALTHY.
  1 -- DEGRADED / STALE / UNFINISHED / NEVER_RUN. `NEVER_RUN` is the
       expected state before the scheduler is activated (#26E source
       prompt §22) -- still exit 1 (no healthy evidence exists yet to
       report), but distinguishable from the other three by the
       `status` field in the output, never conflated with "broken."
  2 -- schema incompatible, database unavailable, or configuration
       missing -- an operational failure this command cannot see past,
       mirroring `run_maintenance.py`'s/`process_release.py`'s own
       identical exit-code-2 convention for the identical class of
       problem.

Safety: never prints a connection string, host, username, or password
-- mirrors every other operational CLI in this project exactly.
"""

import argparse
import json
import sys
from datetime import timedelta

from app.core.schema_compatibility import SchemaCompatibilityStatus
from app.domain.maintenance_health import MaintenanceHealthStatus
from app.services.maintenance_health import (
    DEFAULT_STALE_THRESHOLD,
    DEFAULT_UNFINISHED_GRACE_PERIOD,
    MaintenanceHealthCheckResult,
    check_maintenance_health,
)

_HEALTHY_EXIT = 0
_UNHEALTHY_EXIT = 1
_OPERATIONAL_FAILURE_EXIT = 2

_UNHEALTHY_STATUSES = frozenset(
    {
        MaintenanceHealthStatus.DEGRADED,
        MaintenanceHealthStatus.STALE,
        MaintenanceHealthStatus.UNFINISHED,
        MaintenanceHealthStatus.NEVER_RUN,
    }
)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    result = check_maintenance_health(
        stale_threshold=timedelta(hours=args.stale_threshold_hours),
        unfinished_grace_period=timedelta(minutes=args.unfinished_grace_minutes),
    )

    if args.json:
        print(json.dumps(_as_dict(result)))
    else:
        _print_summary(result)

    return _exit_code(result)


def _exit_code(result: MaintenanceHealthCheckResult) -> int:
    if result.schema_compatibility.status is not SchemaCompatibilityStatus.COMPATIBLE:
        return _OPERATIONAL_FAILURE_EXIT
    assert result.health is not None
    if result.health.status in _UNHEALTHY_STATUSES:
        return _UNHEALTHY_EXIT
    return _HEALTHY_EXIT


def _as_dict(result: MaintenanceHealthCheckResult) -> dict:
    compat = result.schema_compatibility
    body: dict = {
        "schema_compatible": compat.compatible,
        "schema_status": compat.status.value,
    }
    if result.health is None:
        body["status"] = None
        return body

    body["status"] = result.health.status.value
    body["latest_sweep"] = _sweep_dict(result.health.latest_sweep)
    body["latest_finished_sweep"] = _sweep_dict(result.health.latest_finished_sweep)
    return body


def _sweep_dict(snapshot) -> dict | None:
    if snapshot is None:
        return None
    return {
        "started_at": snapshot.started_at.isoformat(),
        "finished_at": snapshot.finished_at.isoformat() if snapshot.finished_at else None,
        "failed_count": snapshot.failed_count,
    }


def _print_summary(result: MaintenanceHealthCheckResult) -> None:
    compat = result.schema_compatibility
    if compat.status is not SchemaCompatibilityStatus.COMPATIBLE:
        print(f"Schema: {compat.status.value} -- refusing to interpret sweep history.", file=sys.stderr)
        print(f"Expected revision: {compat.expected_revision}")
        print(f"Actual revision: {compat.actual_revision}")
        return

    assert result.health is not None
    print(f"Status: {result.health.status.value}")
    _print_sweep("Latest sweep", result.health.latest_sweep)
    _print_sweep("Latest finished sweep", result.health.latest_finished_sweep)


def _print_sweep(label: str, snapshot) -> None:
    if snapshot is None:
        print(f"{label}: none")
        return
    finished = snapshot.finished_at.isoformat() if snapshot.finished_at else "not finished"
    print(f"{label}: started {snapshot.started_at.isoformat()}, finished {finished}, failed_count={snapshot.failed_count}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.operations.maintenance_health",
        description=(
            "Read-only maintenance-worker heartbeat check, derived entirely from persisted "
            "MaintenanceSweep evidence (docs/product/production-reliability-deployment-v1.md #26B §26/§54). "
            "Never calls FRED, never mutates anything, never triggers a sweep."
        ),
    )
    parser.add_argument(
        "--stale-threshold-hours",
        type=float,
        default=DEFAULT_STALE_THRESHOLD.total_seconds() / 3600,
        metavar="N",
        help=f"Hours after which the latest known-good sweep is considered stale (default {DEFAULT_STALE_THRESHOLD}).",
    )
    parser.add_argument(
        "--unfinished-grace-minutes",
        type=float,
        default=DEFAULT_UNFINISHED_GRACE_PERIOD.total_seconds() / 60,
        metavar="N",
        help=f"Minutes a sweep may run before being considered crashed/hung (default {DEFAULT_UNFINISHED_GRACE_PERIOD}).",
    )
    parser.add_argument("--json", action="store_true", help="Emit a single JSON object instead of human-readable text.")
    return parser


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
