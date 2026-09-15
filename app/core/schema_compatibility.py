"""Read-only schema compatibility checking between this application's
own expected Alembic head and the database it is configured to use.

Authoritative contract: docs/product/production-reliability-deployment-v1.md
(#26B), specifically §8/§9 (exact-equality V1 policy), §14 (readiness
definition), §60 (architecture guards). Implements Increment #26C.

Bounded, pure responsibility (frozen, #26C source prompt §12): this
module knows exactly two things -- the Alembic migration graph
packaged with this application, and a database's own `alembic_version`
table. It knows nothing about Inflation, Labor, FRED, release
processing, Recorded State History, Since Last Visit, or AI, and
imports none of them. It is reused identically by the web readiness
route (`app/main.py`) and both operational CLIs
(`app/operations/process_release.py`, `app/operations/run_maintenance.py`)
-- one shared function, never a second, independently-written check
(#26B §20).

Never mutates anything: no `CREATE`, no `ALTER`, no `alembic upgrade`,
no `alembic downgrade`, no `Base.metadata.create_all()`. Every database
access here is a single, read-only `SELECT`.
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import DatabaseNotConfiguredError, session_scope

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_ALEMBIC_INI = _REPO_ROOT / "alembic.ini"


class SchemaCompatibilityStatus(str, Enum):
    """Every distinguishable outcome of comparing a database's own
    current Alembic revision against this application's own expected
    head (#26C source prompt §5). `COMPATIBLE` is the only status
    under which traffic may be served or economic processing may
    proceed (#26B's own frozen invariant, §2/§14 there).

    `SCHEMA_UNINITIALIZED` and `SCHEMA_AMBIGUOUS` are refinements of
    #26B's own coarser two-value schema vocabulary (`SCHEMA_BEHIND`/
    `SCHEMA_AHEAD`) -- more precise internally, still exactly two
    concepts once summarized for the public `/readiness` surface
    (both map to the single `schema_mismatch` reason, #26B §19):
    an uninitialized database is a specific, common, easy-to-diagnose
    case of "behind" (nothing has ever been migrated); an ambiguous
    database (more than one `alembic_version` row, or a revision this
    application's own migration graph does not recognize as an
    ancestor of its expected head) is never guessed at (#26C source
    prompt §11) -- it degrades to the same safe, non-compatible
    classification the public surface already exposes for any schema
    problem.
    """

    COMPATIBLE = "COMPATIBLE"
    SCHEMA_BEHIND = "SCHEMA_BEHIND"
    SCHEMA_AHEAD = "SCHEMA_AHEAD"
    SCHEMA_UNINITIALIZED = "SCHEMA_UNINITIALIZED"
    SCHEMA_AMBIGUOUS = "SCHEMA_AMBIGUOUS"
    DATABASE_UNAVAILABLE = "DATABASE_UNAVAILABLE"
    CONFIGURATION_MISSING = "CONFIGURATION_MISSING"


@dataclass(frozen=True)
class SchemaCompatibilityResult:
    """`expected_revision`/`actual_revision` are short, non-secret
    Alembic revision hex identifiers -- safe to surface publicly
    (#26B §17/§19), never a connection string, host, or credential.
    `actual_revision` is `None` whenever it could not be determined at
    all (database unreachable, configuration missing, or genuinely
    uninitialized)."""

    status: SchemaCompatibilityStatus
    expected_revision: str | None
    actual_revision: str | None

    @property
    def compatible(self) -> bool:
        return self.status is SchemaCompatibilityStatus.COMPATIBLE


def _script_directory() -> ScriptDirectory:
    config = AlembicConfig(str(_ALEMBIC_INI))
    return ScriptDirectory.from_config(config)


def expected_revision() -> str | None:
    """The Alembic revision this packaged application's own migration
    files declare as head -- derived from the actual files under
    `alembic/versions/` via Alembic's own `ScriptDirectory`, never a
    manually duplicated hard-coded revision string (#26C source prompt
    §3: "avoid two independent sources of truth"). Requires no
    database connection at all -- reading the migration graph is a
    pure filesystem operation.

    Returns `None` (never guesses, never raises past the caller) if
    this application's own packaged migration graph itself does not
    have exactly one head -- a packaging defect, not a database
    condition, and exactly the same "ambiguous, do not guess" posture
    this module applies everywhere else (#26C source prompt §11).
    """
    heads = _script_directory().get_heads()
    if len(heads) != 1:
        return None
    return heads[0]


def _is_ancestor(script: ScriptDirectory, candidate: str, of: str) -> bool:
    """True only if `candidate` is a real ancestor of `of`, walked
    directly through each revision's own `down_revision` chain in this
    application's own known migration graph -- never inferred from
    string/lexical comparison. A revision this graph does not
    recognize at all (e.g. a newer migration a future application
    version added, which this packaged version has never heard of)
    correctly returns `False`, never assumed to be an ancestor."""
    revision: str | None = of
    while revision is not None:
        if revision == candidate:
            return True
        script_revision = script.get_revision(revision)
        down = script_revision.down_revision if script_revision is not None else None
        # This project's own migration graph is confirmed, single-head
        # and strictly linear (production-reliability-deployment-v1.md
        # §7) -- a tuple `down_revision` would mean a merge revision,
        # which does not exist here. Fail safe rather than walk one
        # arbitrary branch if that ever changes.
        if isinstance(down, tuple):
            return False
        revision = down
    return False


def _read_actual_revision(session: Session) -> str | None | SchemaCompatibilityStatus:
    """Reads `alembic_version` read-only. Returns the single revision
    string, `None` for a genuinely empty (but existing) table, or a
    terminal `SchemaCompatibilityStatus` for every condition that
    prevents a plain revision string from being determined at all."""
    try:
        rows = session.execute(text("SELECT version_num FROM alembic_version")).fetchall()
    except ProgrammingError:
        # The alembic_version table itself does not exist -- a
        # genuinely fresh, never-migrated database (#26C source
        # prompt §10).
        return SchemaCompatibilityStatus.SCHEMA_UNINITIALIZED
    except OperationalError:
        return SchemaCompatibilityStatus.DATABASE_UNAVAILABLE
    except SQLAlchemyError:
        return SchemaCompatibilityStatus.DATABASE_UNAVAILABLE

    if len(rows) == 0:
        return SchemaCompatibilityStatus.SCHEMA_UNINITIALIZED
    if len(rows) > 1:
        # A branched/multi-head database state -- never guess which
        # row is authoritative (#26C source prompt §11).
        return SchemaCompatibilityStatus.SCHEMA_AMBIGUOUS
    return rows[0][0]


def check_schema_compatibility(session: Session | None = None) -> SchemaCompatibilityResult:
    """The one, shared compatibility check -- used identically by
    `/readiness` and both operational CLIs (#26B §20). Read-only:
    never issues `CREATE`/`ALTER`/`DROP`, never runs `alembic upgrade`/
    `downgrade`, never calls `Base.metadata.create_all()`.

    `session` is an optional injection point for tests that need to
    point this check at a specific, real database in a specific,
    deliberately-arranged migration state (production-reliability-
    deployment-v1.md §59) without going through this application's own
    configured `DATABASE_URL`. Production callers (the readiness route,
    both CLI preflights) call this with no argument, and it resolves
    the application's own configured database via the existing,
    unmodified `session_scope()` -- the identical session lifecycle
    every other read path in this codebase already uses, never a
    second, parallel database-access pattern built just for this.
    """
    expected = expected_revision()
    if expected is None:
        return SchemaCompatibilityResult(SchemaCompatibilityStatus.SCHEMA_AMBIGUOUS, None, None)

    if session is not None:
        return _check_with_session(session, expected)

    try:
        with session_scope() as scoped_session:
            return _check_with_session(scoped_session, expected)
    except DatabaseNotConfiguredError:
        return SchemaCompatibilityResult(SchemaCompatibilityStatus.CONFIGURATION_MISSING, expected, None)
    except OperationalError:
        return SchemaCompatibilityResult(SchemaCompatibilityStatus.DATABASE_UNAVAILABLE, expected, None)
    except SQLAlchemyError:
        return SchemaCompatibilityResult(SchemaCompatibilityStatus.DATABASE_UNAVAILABLE, expected, None)


def _check_with_session(session: Session, expected: str) -> SchemaCompatibilityResult:
    actual = _read_actual_revision(session)
    if isinstance(actual, SchemaCompatibilityStatus):
        return SchemaCompatibilityResult(actual, expected, None)

    if actual == expected:
        return SchemaCompatibilityResult(SchemaCompatibilityStatus.COMPATIBLE, expected, actual)

    script = _script_directory()
    if _is_ancestor(script, actual, expected):
        return SchemaCompatibilityResult(SchemaCompatibilityStatus.SCHEMA_BEHIND, expected, actual)
    return SchemaCompatibilityResult(SchemaCompatibilityStatus.SCHEMA_AHEAD, expected, actual)
