"""Shared fixtures for the repository/service integration suite.

Deliberately and completely decoupled from `app.core.config.settings`
(the real application's own `DATABASE_URL`): integration tests read
their own, separate `TEST_DATABASE_URL` environment variable, which
`app/core/config.py` never sees or reads. There is no fallback and no
default -- if it isn't set, integration tests skip rather than risk
running against nothing, or worse, against a developer's real database
by some accidental convention-based guess.

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
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parents[2]


def _database_name_from_url(url: str) -> str:
    """The trailing path segment of a DB URL -- enough to check "does
    this look like a test database", never enough (nor intended) to
    reconstruct credentials."""
    return url.rsplit("/", 1)[-1].split("?")[0]


def pytest_collection_modifyitems(config, items):
    """Every test collected under tests/integration/ is automatically
    marked `integration`, so `pytest -m "not integration"`/`pytest -m
    integration` work without hand-annotating every test function."""
    this_dir = Path(__file__).resolve().parent
    for item in items:
        if Path(item.fspath).resolve().is_relative_to(this_dir):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """The isolated integration-test database URL, gated by the safety
    guard described in this module's docstring."""
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip(
            "TEST_DATABASE_URL is not set -- integration tests are skipped "
            "(never run against a database implicitly). See the Engineering "
            "Journal's Increment 011 entry for setup instructions."
        )
    db_name = _database_name_from_url(url)
    if "test" not in db_name.lower():
        raise RuntimeError(
            "Refusing to run integration tests: TEST_DATABASE_URL's database "
            f"name ({db_name!r}) does not contain 'test'. This is a deliberate, "
            "unconditional safety guard against accidentally pointing "
            "integration tests at a non-test database -- point TEST_DATABASE_URL "
            "at a database whose name makes its purpose unambiguous."
        )
    return url


@pytest.fixture(scope="session", autouse=True)
def _apply_migrations(request):
    """Apply the project's existing Alembic migration(s) to the isolated
    test database once per test session -- never duplicates schema
    creation manually, and never touches alembic/env.py or
    app/core/config.py. Alembic is invoked as a subprocess with
    DATABASE_URL overridden only for that subprocess's own environment
    -- exactly alembic's normal, documented usage pattern, just pointed
    at a different value than the application's real configuration.

    Depends on `test_database_url` implicitly by requesting the fixture
    through `request.getfixturevalue` so that the "no TEST_DATABASE_URL"
    skip (above) also skips migration setup, rather than this fixture
    running (and failing confusingly) before that skip has a chance to.
    """
    if "test_database_url" not in request.fixturenames and not _has_marked_integration_tests(request):
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


def _has_marked_integration_tests(request) -> bool:
    """Session-scoped autouse fixtures run even for a session that
    collected zero integration tests (e.g. a pure `pytest -m "not
    integration"` run) -- skip migration setup entirely in that case
    rather than requiring TEST_DATABASE_URL just to run unrelated tests."""
    return any(item.get_closest_marker("integration") for item in request.session.items)


@pytest.fixture
def db_session(test_database_url: str):
    """One test = one connection-level transaction, unconditionally
    rolled back afterward -- regardless of whether the code under test
    itself calls `session.commit()` (application code always does, via
    `app.db.session.session_scope`, which this fixture deliberately
    bypasses entirely so commit is safe to call without persisting
    anything past the test).

    Uses SQLAlchemy's documented "join an external transaction via a
    savepoint" pattern (`join_transaction_mode="create_savepoint"`):
    an inner `session.commit()` releases a SAVEPOINT rather than ending
    the real transaction, which this fixture rolls back explicitly at
    the end regardless of what happened inside.

    Every test starts from the same known state (the migrated, empty
    schema, or whatever a fully-rolled-back prior test left behind --
    i.e. always the same state) and cannot leak into another test, so
    tests are order-independent by construction, not by convention.
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
