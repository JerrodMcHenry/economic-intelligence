"""Check -- and optionally write -- the first-party release schedule
(Increment #56B).

    python -m app.operations.release_schedule [--sync] [--as-of-date YYYY-MM-DD]

Prints one line per release (BLS CPI, BLS Employment Situation, BEA
Personal Income and Outlays): OK, EXPIRING (the last known date is
within 45 days), EXPIRED (every known date has passed, so scheduled
updates have STOPPED), or MISSING. `--sync` also writes the committed
dates as release occurrences; `run_maintenance` does the same at the
start of every sweep, so this flag is for bootstrap and inspection.

Exit codes: 0 all OK or EXPIRING; 1 any EXPIRED or MISSING; 2
operational failure. The fix for 1 is to add the next year's dates to
`app/models/release_schedule.py` from the agencies' published schedules
and deploy; until then, `python -m app.operations.import_first_party`
keeps the data current by hand.
"""

import argparse
import sys
from datetime import date, datetime, timezone

from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.core.config import settings
from app.core.schema_compatibility import check_schema_compatibility
from app.db.session import session_scope
from app.models.release_schedule import SCHEDULE_VERIFIED_ON
from app.services.release_schedule import schedule_status, sync_schedule


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.operations.release_schedule", description=__doc__.split("\n\n")[0])
    parser.add_argument("--sync", action="store_true", help="Write the committed dates as release occurrences.")
    parser.add_argument("--as-of-date", type=date.fromisoformat, default=None, help="Treat this date as today.")
    args = parser.parse_args(argv)
    today = args.as_of_date or datetime.now(timezone.utc).date()

    missing: tuple[str, ...] = ()
    if args.sync:
        if not settings.database_url:
            print("Operational failure: database is not configured on this server.", file=sys.stderr)
            return 2
        compatibility = check_schema_compatibility()
        if not compatibility.compatible:
            print(
                f"Operational failure: database schema is not compatible ({compatibility.status.value}).",
                file=sys.stderr,
            )
            return 2
        try:
            with session_scope() as session:
                outcome = sync_schedule(session)
        except (OperationalError, SQLAlchemyError):
            print("Operational failure: a database error occurred; nothing was written.", file=sys.stderr)
            return 2
        missing = outcome.missing_catalog_releases
        print(f"Occurrences written: {outcome.occurrences_created} new, {outcome.occurrences_existing} already present")

    print(f"Schedule verified against the agencies' pages on {SCHEDULE_VERIFIED_ON}")
    problem = False
    for status in schedule_status(today):
        if f"{status.provider}/{status.provider_release_id}" in missing:
            problem = True
            print(f"{status.provider} {status.provider_release_id}: MISSING: release is not in the active catalog")
            continue
        problem = problem or status.state in {"EXPIRED", "MISSING"}
        print(status.describe())
    return 1 if problem else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
