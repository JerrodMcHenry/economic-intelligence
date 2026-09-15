"""Operational CLI entry point for Increment #26D's deployment release
process -- the ONE and ONLY place this application's own database
schema is ever advanced. See
docs/product/production-reliability-deployment-v1.md (#26B) §11/§12/§13,
ADR-027.

    python -m app.operations.release preflight
    python -m app.operations.release migrate

`preflight` is read-only: reports the current compatibility state
(reusing Increment #26C's own shared `check_schema_compatibility` --
never a second, independently-written check) and exits non-zero unless
it is safe to migrate forward. `COMPATIBLE` (nothing to do),
`SCHEMA_BEHIND`, and `SCHEMA_UNINITIALIZED` are the only states this
command will ever migrate from. A database that is `SCHEMA_AHEAD` or
`SCHEMA_AMBIGUOUS` is refused outright -- this command never attempts
a downgrade or any other automatic correction (§18/§19 of the frozen
contract: "fail closed", "do not attempt downgrade").

`migrate` runs the identical preflight first, aborts with the same
non-zero behavior if preflight itself refuses, otherwise invokes
`alembic.command.upgrade(config, "head")` -- and then re-runs the
shared compatibility check to VERIFY the database actually reached
exactly the expected head. Success requires `COMPATIBLE` after the
upgrade; anything else is a hard failure, never silently accepted as
"probably fine" (§12/§13).

This command is the deployment pipeline's own migration phase (#26B
§12 steps 3-5) -- it is never invoked by web-process startup
(`app/main.py` has, and must continue to have, zero awareness of it),
never by the maintenance worker, and it performs zero economic
processing of its own.

Migration locking (#26D source prompt §21, decision recorded here, not
merely implied): no explicit database advisory lock is added around
the upgrade step. #26B already froze the release process as ONE
serialized pipeline phase (build -> test -> migrate -> deploy), never
run concurrently with itself by design; this project has no
CI/CD-triggered concurrent-deploy mechanism today, and no multi-
operator team that could trigger two releases at once. Postgres's own
transactional DDL means a genuinely concurrent, conflicting attempt
fails LOUDLY (a real database error, caught below and reported as a
safe non-zero exit) rather than silently corrupting the schema -- an
acceptable failure mode for a condition this project's own process
discipline is not expected to produce. Revisit if a genuinely
concurrent-deploy-capable pipeline is ever introduced (#26E or later)
-- at that point, wrapping the upgrade step in a Postgres advisory
lock is the well-known, standard mitigation, not designed further
here.

Safety: never prints a connection string, host, username, or password
-- mirrors `app/operations/process_release.py`'s/`run_maintenance.py`'s
own established discipline exactly.
"""

import argparse
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig

from app.core.config import settings
from app.core.schema_compatibility import SchemaCompatibilityResult, SchemaCompatibilityStatus, check_schema_compatibility

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_ALEMBIC_INI = _REPO_ROOT / "alembic.ini"

# The only states this command will ever migrate FROM. SCHEMA_AHEAD and
# SCHEMA_AMBIGUOUS are refused outright (§18/§19) -- never guessed at,
# never auto-corrected.
_SAFE_TO_MIGRATE_FROM = frozenset(
    {
        SchemaCompatibilityStatus.COMPATIBLE,
        SchemaCompatibilityStatus.SCHEMA_BEHIND,
        SchemaCompatibilityStatus.SCHEMA_UNINITIALIZED,
    }
)


def _report(result: SchemaCompatibilityResult) -> None:
    print(f"Status: {result.status.value}")
    print(f"Expected revision: {result.expected_revision}")
    print(f"Actual revision: {result.actual_revision}")


def preflight() -> int:
    """Read-only. Never mutates the database. Returns `0` only when it
    is safe to proceed to `migrate()`."""
    if not settings.database_url:
        print("Operational failure: database is not configured on this server.", file=sys.stderr)
        return 2

    result = check_schema_compatibility()
    _report(result)

    if result.status not in _SAFE_TO_MIGRATE_FROM:
        print(
            f"Refusing to migrate: {result.status.value} is not a state this command will migrate from -- "
            "no downgrade, no automatic correction is ever attempted "
            "(see docs/product/production-reliability-deployment-v1.md §18/§19).",
            file=sys.stderr,
        )
        return 2

    return 0


def migrate() -> int:
    """Runs `preflight()` first (never a duplicated check); if it
    refuses, `migrate()` aborts with the identical exit code and NEVER
    calls `alembic.command.upgrade` at all. Otherwise applies the
    migration and verifies the result -- success requires `COMPATIBLE`
    after the upgrade, never merely "the upgrade command didn't raise"."""
    preflight_exit_code = preflight()
    if preflight_exit_code != 0:
        return preflight_exit_code

    before = check_schema_compatibility()
    if before.status is SchemaCompatibilityStatus.COMPATIBLE:
        print("Already at head -- nothing to migrate.")
        return 0

    print("Applying migrations (alembic upgrade head)...")
    config = AlembicConfig(str(_ALEMBIC_INI))
    try:
        command.upgrade(config, "head")
    except Exception as exc:
        # Deliberately reports only the exception TYPE, never str(exc)
        # -- an Alembic/SQLAlchemy error message can, in principle,
        # echo back part of a failing statement or connection detail;
        # the type name alone is always safe and is enough for an
        # operator to know where to look (docs/architecture/
        # current-architecture.md's own runbook names the recovery
        # steps).
        print(f"Operational failure: migration failed ({type(exc).__name__}).", file=sys.stderr)
        return 2

    after = check_schema_compatibility()
    _report(after)
    if after.status is not SchemaCompatibilityStatus.COMPATIBLE:
        print(
            "Operational failure: migration command completed but the database is still not compatible "
            f"({after.status.value}) -- refusing to report this release as successful.",
            file=sys.stderr,
        )
        return 2

    print("Migration verified: database is COMPATIBLE.")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.operations.release",
        description=(
            "The deployment release process's own migration phase (docs/product/"
            "production-reliability-deployment-v1.md §12): report or apply exactly the migrations "
            "needed to bring this application's configured database to its own expected Alembic head, "
            "verified afterward, never a downgrade, never a silent success."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("preflight", help="Report compatibility, read-only. Exit 0 only if safe to migrate.")
    subparsers.add_parser("migrate", help="Preflight, then apply and verify migrations. Exit 0 only if COMPATIBLE afterward.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "preflight":
        return preflight()
    return migrate()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
