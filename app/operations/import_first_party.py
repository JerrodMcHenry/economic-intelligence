"""Import first-party Inflation and Jobs history from BLS and BEA
(Increment #56A).

    python -m app.operations.import_first_party [--years 10] [--provider all|bls|bea] [--as-of-date YYYY-MM-DD]

A command, not an HTTP route. BEA's NIPA file is ~37 MB, and #54A
measured a single long ingestion request being cut off by a deploy
(Render stops an old instance ~360 s after cutover). Run it from a
Render Shell or a one-off job, where no request timeout applies.

Populates the concept-keyed BLS/BEA rows only. Their bindings stay
INACTIVE, so this changes no monitor, API response or page until #56B
activates them. Keyless by default; set `BLS_API_KEY` for BLS v2 (more
queries per day, up to 20 years). The key is never printed.

Exit codes, as `run_maintenance`: 0 every provider succeeded; 1 a
provider failed or returned an empty series (anything it did store is
kept); 2 operational failure (configuration, schema, database), with
nothing written.
"""

import argparse
import sys
from datetime import date

from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.clients.bea import BEAClient
from app.clients.bls import BLSClient
from app.core.config import settings
from app.core.schema_compatibility import check_schema_compatibility
from app.db.session import session_scope
from app.models.first_party import DEFAULT_IMPORT_YEARS, PROVIDER_BEA, PROVIDER_BLS
from app.services.first_party_ingestion import FirstPartyIngestionService, ProviderRunOutcome

_PROVIDERS = {"all": (PROVIDER_BLS, PROVIDER_BEA), "bls": (PROVIDER_BLS,), "bea": (PROVIDER_BEA,)}


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if not settings.database_url:
        print("Operational failure: database is not configured on this server.", file=sys.stderr)
        return 2

    compatibility = check_schema_compatibility()
    if not compatibility.compatible:
        print(
            f"Operational failure: database schema is not compatible with this application version "
            f"({compatibility.status.value}; expected {compatibility.expected_revision}, "
            f"found {compatibility.actual_revision}).",
            file=sys.stderr,
        )
        return 2

    service = FirstPartyIngestionService(BLSClient(api_key=settings.bls_api_key), BEAClient())
    try:
        with session_scope() as session:
            outcomes = service.import_history(
                session, years=args.years, as_of=args.as_of_date, providers=_PROVIDERS[args.provider]
            )
    except ValueError as exc:
        # Argument validation only (years out of range for the access mode).
        print(f"Refusing to import: {exc}", file=sys.stderr)
        return 2
    except OperationalError:
        print("Operational failure: database is currently unavailable.", file=sys.stderr)
        return 2
    except SQLAlchemyError:
        print("Operational failure: a database error occurred; nothing was written.", file=sys.stderr)
        return 2

    for outcome in outcomes:
        _print_outcome(outcome)
    return 0 if all(outcome.status == "SUCCEEDED" for outcome in outcomes) else 1


def _print_outcome(outcome: ProviderRunOutcome) -> None:
    published = f", source published {outcome.source_published_at.isoformat()}" if outcome.source_published_at else ""
    print(
        f"{outcome.provider} [{outcome.access_mode}] {outcome.status} {outcome.import_mode} "
        f"{outcome.window_start}..{outcome.window_end}{published}"
        + (f" error={outcome.error_class}" if outcome.error_class else "")
    )
    for series in outcome.series:
        print(
            f"  {series.provider_series_id:<16} {series.concept_id:<44} received={series.received} "
            f"inserted={series.inserted} revised={series.revised} unchanged={series.unchanged} "
            f"unavailable={series.unavailable} {series.first_period}..{series.last_period}"
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.operations.import_first_party",
        description="Import BLS and BEA Inflation/Jobs history into the concept-keyed first-party rows.",
    )
    parser.add_argument(
        "--years",
        type=int,
        default=DEFAULT_IMPORT_YEARS,
        help=f"Calendar years to import, counting the current one (default {DEFAULT_IMPORT_YEARS}).",
    )
    parser.add_argument("--provider", choices=sorted(_PROVIDERS), default="all")
    parser.add_argument(
        "--as-of-date",
        type=date.fromisoformat,
        default=None,
        help="Treat this date as today (default: today, UTC). For reproducible verification.",
    )
    return parser


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
