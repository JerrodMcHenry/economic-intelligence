"""Shared fixtures for every suite that needs a real, isolated PostgreSQL
test database -- tests/integration/ (Increment 011) and tests/api/
(Increment 012). Lives at the tests/ root (not inside either
subdirectory) because pytest fixture visibility only flows downward to
subdirectories, never sideways between siblings -- this is the single,
non-duplicated source of the database safety guard, migration setup,
and rollback-isolated session fixture both suites share.

Deliberately and completely decoupled from `app.core.config.settings`
(the real application's own `DATABASE_URL`): tests read their own,
separate `TEST_DATABASE_URL` environment variable, which
`app/core/config.py` never sees or reads. There is no fallback and no
default -- if it isn't set, these tests skip rather than risk running
against nothing, or worse, against a developer's real database by some
accidental convention-based guess.

Deterministic safety guard: even when `TEST_DATABASE_URL` is set, its
database name must contain "test" (case-insensitive) or setup refuses
to proceed at all. This is a hard requirement, not a convention -- there
is no code path that runs a migration or a test against a database
whose name doesn't make its purpose unambiguous.

Never reads, prints, or logs the actual connection string anywhere
(assertion/exception messages here are always generic) -- a Postgres
URL can carry a password, and it must never appear in test output.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = Path(__file__).resolve().parent

# Any test collected under one of these subdirectories is auto-marked
# with the matching name -- `pytest -m "not integration and not api"`,
# `pytest -m integration`, `pytest -m api` all work without hand-
# annotating individual test functions.
_DB_MARKER_DIRS = {"integration": TESTS_DIR / "integration", "api": TESTS_DIR / "api"}


def _database_name_from_url(url: str) -> str:
    """The trailing path segment of a DB URL -- enough to check "does
    this look like a test database", never enough (nor intended) to
    reconstruct credentials."""
    return url.rsplit("/", 1)[-1].split("?")[0]


def pytest_collection_modifyitems(config, items):
    for item in items:
        item_path = Path(item.fspath).resolve()
        for marker_name, directory in _DB_MARKER_DIRS.items():
            if item_path.is_relative_to(directory):
                item.add_marker(getattr(pytest.mark, marker_name))


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """The isolated test database URL, gated by the safety guard
    described in this module's docstring."""
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip(
            "TEST_DATABASE_URL is not set -- database-backed tests are skipped "
            "(never run against a database implicitly). See the Engineering "
            "Journal's Increment 011/012 entries for setup instructions."
        )
    db_name = _database_name_from_url(url)
    if "test" not in db_name.lower():
        raise RuntimeError(
            "Refusing to run database-backed tests: TEST_DATABASE_URL's database "
            f"name ({db_name!r}) does not contain 'test'. This is a deliberate, "
            "unconditional safety guard against accidentally pointing tests at a "
            "non-test database -- point TEST_DATABASE_URL at a database whose "
            "name makes its purpose unambiguous."
        )
    return url


def _has_marked_db_tests(request) -> bool:
    """Session-scoped autouse fixtures run even for a session that
    collected zero database-backed tests (e.g. a pure `pytest -m "not
    integration and not api"` run) -- skip migration setup entirely in
    that case rather than requiring TEST_DATABASE_URL just to run
    unrelated tests."""
    marker_names = _DB_MARKER_DIRS.keys()
    return any(item.get_closest_marker(name) for item in request.session.items for name in marker_names)


@pytest.fixture(scope="session", autouse=True)
def _apply_migrations(request):
    """Apply the project's existing Alembic migration(s) to the isolated
    test database once per test session -- never duplicates schema
    creation manually, and never touches alembic/env.py or
    app/core/config.py. Alembic is invoked as a subprocess with
    DATABASE_URL overridden only for that subprocess's own environment
    -- exactly alembic's normal, documented usage pattern, just pointed
    at a different value than the application's real configuration.
    """
    if not _has_marked_db_tests(request):
        return
    url = request.getfixturevalue("test_database_url")

    env = {**os.environ, "DATABASE_URL": url}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # Deliberately not including result.stderr/stdout verbatim here --
        # alembic's own log lines don't normally carry the URL, but this
        # guards against that changing without notice. Re-run
        # `DATABASE_URL=<test url> alembic upgrade head` by hand to see
        # full output while debugging.
        raise RuntimeError(
            f"Failed to apply Alembic migrations to the test database (exit code {result.returncode}). "
            "Re-run `alembic upgrade head` by hand against TEST_DATABASE_URL to see full output."
        )


@pytest.fixture
def db_session(test_database_url: str):
    """One test = one connection-level transaction, unconditionally
    rolled back afterward -- regardless of whether the code under test
    itself calls `session.commit()`.

    Uses SQLAlchemy's documented "join an external transaction via a
    savepoint" pattern (`join_transaction_mode="create_savepoint"`): an
    inner `session.commit()` releases a SAVEPOINT rather than ending the
    real transaction, which this fixture rolls back explicitly at the
    end regardless of what happened inside.

    Correct for tests/integration/, where the test itself holds the only
    session in play (it passes `db_session` directly to a repository/
    service call). NOT used by tests/api/ for seeding: an HTTP request
    handled by the real FastAPI route opens its OWN, separate connection
    via `app.db.session.session_scope`, which -- being a different
    Postgres connection -- cannot see this fixture's uncommitted-outside-
    a-savepoint data. tests/api/conftest.py's `seed_session` fixture
    (real commit + explicit truncate-based cleanup) exists specifically
    for that different situation; see its docstring for why.
    """
    engine = create_engine(test_database_url)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


# ---------------------------------------------------------------------
# Increment #26C (docs/product/production-reliability-deployment-v1.md):
# a SECOND, separate, dedicated database for schema-compatibility
# tests -- deliberately NOT the `test_database_url`/`db_session`
# fixtures above. Those are, correctly and by design, kept always-at-
# head by `_apply_migrations`; schema-compatibility tests need a
# database they can freely migrate to an EARLIER revision, or leave
# genuinely uninitialized, without ever disturbing the shared database
# every other suite in this project depends on staying at head (#26C's
# own source prompt: "New deployment-drift tests should explicitly
# manage their own isolated schema state"). This fixture creates that
# second database if it does not already exist -- it never touches
# `economic_intelligence`/`economic_intelligence_test`, and it is
# never migrated to head automatically; each test that uses it is
# responsible for putting it in whatever exact revision state that
# test needs, via `alembic upgrade`/`downgrade` invoked exactly the
# way `_apply_migrations` above already invokes it (a subprocess, with
# `DATABASE_URL` overridden only for that subprocess's own
# environment).
# ---------------------------------------------------------------------

SCHEMA_DRIFT_DB_NAME = "economic_intelligence_schema_drift_test"


@pytest.fixture(scope="session")
def schema_drift_database_url(test_database_url: str) -> str:
    """The isolated, session-scoped schema-drift database's own URL --
    created here if it does not already exist. Never auto-migrated;
    individual tests move it between revisions explicitly via
    `migrate_schema_drift_database` below."""
    base = test_database_url.rsplit("/", 1)[0]
    drift_url = f"{base}/{SCHEMA_DRIFT_DB_NAME}"
    admin_url = f"{base}/postgres"

    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as connection:
            exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": SCHEMA_DRIFT_DB_NAME}
            ).first()
            if exists is None:
                connection.execute(text(f'CREATE DATABASE "{SCHEMA_DRIFT_DB_NAME}"'))
    finally:
        admin_engine.dispose()

    return drift_url


def reset_schema_drift_database_to_nothing(schema_drift_database_url: str) -> None:
    """Drops EVERY table in the schema-drift database, including
    `alembic_version` itself -- a genuinely complete reset, robust
    against ANY prior state, including one Alembic itself would refuse
    to walk backward from (e.g. a test that deliberately left
    `alembic_version` pointing at an unrecognized/simulated-ahead
    revision, #26D's own `TestSchemaAhead`-shaped tests) -- `alembic
    downgrade base` cannot recover from that on its own, since it needs
    to recognize the CURRENT revision to know how to walk backward from
    it. `DROP SCHEMA IF EXISTS public CASCADE` / `CREATE SCHEMA public`
    is the standard, complete, alembic-independent reset for a
    dedicated test database -- safe here only because this database
    exists for exactly this purpose and nothing else ever reads or
    writes it.

    Two defensive measures, both learned directly from a real hang
    this project hit while writing #26D's own tests (a `drift_session`-
    shaped fixture in another test file holding a connection open
    across the reset call, blocking `DROP SCHEMA ... CASCADE` on a lock
    indefinitely): (1) every OTHER backend connected to this database
    is force-terminated first, from a separate admin connection, so a
    leaked or still-open connection from a prior fixture can never
    block this reset; (2) a short `statement_timeout` is set on the
    reset connection itself, so that even an unanticipated future lock
    contention fails LOUDLY and fast, never hangs the whole test run
    silently.
    """
    admin_url = schema_drift_database_url.rsplit("/", 1)[0] + "/postgres"
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as connection:
            connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :name AND pid <> pg_backend_pid()"
                ),
                {"name": SCHEMA_DRIFT_DB_NAME},
            )
    finally:
        admin_engine.dispose()

    engine = create_engine(schema_drift_database_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            connection.execute(text("SET statement_timeout = '10s'"))
            connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
    finally:
        engine.dispose()


def migrate_schema_drift_database(schema_drift_database_url: str, revision: str) -> None:
    """Puts the isolated schema-drift database at EXACTLY `revision`
    (or fully empty, for `revision="base"`), regardless of whatever
    revision it happened to be left at by a previous test -- by always
    resetting to genuinely nothing first (`reset_schema_drift_database_to_nothing`,
    robust against any prior state, including one Alembic itself
    cannot recognize), then upgrading forward to the exact target if it
    isn't `base` itself. Simple and a little wasteful (this project's
    own migration chain is eight migrations, negligible cost) rather
    than detecting direction, which would need to inspect current
    state first and handle every edge case (already past the target,
    already at it, genuinely uninitialized, or an unrecognized
    simulated revision) correctly.

    The identical subprocess-invocation pattern `_apply_migrations`
    above already uses (`python -m alembic ...`, `DATABASE_URL`
    overridden only for that subprocess's own environment), pointed at
    the schema-drift database instead -- never touches
    `TEST_DATABASE_URL` or the developer's own `economic_intelligence`
    database. Raises with full command output if either step fails.

    `revision="base"` is deliberately NOT the same database state as
    `reset_schema_drift_database_to_nothing` alone: a real
    `alembic downgrade base` leaves the `alembic_version` bookkeeping
    table in place, empty -- a genuinely different, real, distinct
    state from a database that has never been touched by Alembic at
    all (no such table exists), and this project's own compatibility
    module has a distinct code path for each (#26C source prompt
    §10/§35). To reach that specific state, this function upgrades to
    head first (reaching a revision Alembic itself recognizes, so it
    knows how to walk backward) and then downgrades to base -- never
    directly downgrading from whatever arbitrary/possibly-unrecognized
    state a prior test left behind, which is exactly the fragility
    this function's own reset-first design otherwise avoids.
    """
    reset_schema_drift_database_to_nothing(schema_drift_database_url)

    env = {**os.environ, "DATABASE_URL": schema_drift_database_url}

    if revision == "base":
        upgrade_to_head = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=REPO_ROOT, env=env, capture_output=True, text=True
        )
        assert upgrade_to_head.returncode == 0, (
            f"Failed to upgrade the schema-drift database to head en route to base: "
            f"{upgrade_to_head.stdout}\n{upgrade_to_head.stderr}"
        )
        downgrade_result = subprocess.run(
            [sys.executable, "-m", "alembic", "downgrade", "base"], cwd=REPO_ROOT, env=env, capture_output=True, text=True
        )
        assert downgrade_result.returncode == 0, (
            f"Failed to downgrade the schema-drift database to base: {downgrade_result.stdout}\n{downgrade_result.stderr}"
        )
        return

    upgrade_result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision], cwd=REPO_ROOT, env=env, capture_output=True, text=True
    )
    assert upgrade_result.returncode == 0, (
        f"Failed to upgrade the schema-drift database to {revision!r}: {upgrade_result.stdout}\n{upgrade_result.stderr}"
    )
