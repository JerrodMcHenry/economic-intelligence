"""Real-PostgreSQL tests for Increment #26C's schema compatibility
checking (`app.core.schema_compatibility`) -- the class of test this
whole increment exists to add. `production-reliability-deployment-v1.md`
(#26B) §11/§59: the existing, always-self-migrating `TEST_DATABASE_URL`
fixture could never represent real deployment drift by construction,
which is exactly why the #26A incident's own database went undetected
by 1,463 passing tests. These tests use the dedicated, isolated
schema-drift database (`tests/conftest.py`'s `schema_drift_database_url`)
instead -- `TEST_DATABASE_URL` itself stays always-at-head throughout,
completely undisturbed, exactly as every other suite in this project
depends on.

Every migration/reset call here goes through `tests/conftest.py`'s own
`migrate_schema_drift_database`/`reset_schema_drift_database_to_nothing`
helpers, never through `app.core.schema_compatibility` itself -- that
module is proven, throughout this file, to only ever READ.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

import pytest

from app.core.schema_compatibility import (
    SchemaCompatibilityStatus,
    check_schema_compatibility,
    expected_revision,
)
from tests.conftest import migrate_schema_drift_database, reset_schema_drift_database_to_nothing

pytestmark = pytest.mark.integration

# The real migration chain, re-confirmed directly against the actual
# repository this turn (production-reliability-deployment-v1.md §7) --
# never assumed or duplicated as application logic, only used here to
# arrange each test's own starting database state.
_HEAD = "d4a2c19e37b5"
_ONE_BEFORE_HEAD = "c3f8a1d47b62"
_THREE_BEFORE_HEAD = "f12b7ec0d626"


@pytest.fixture
def drift_engine(schema_drift_database_url):
    # Deliberately does NOT open a connection here -- `create_engine`
    # is lazy by construction, so this fixture holds no live database
    # session across the test body. A real hang this project hit while
    # writing these tests traced directly to an EARLIER version of
    # this fixture that opened a `Connection` (and bound a `Session`
    # to it) at fixture-setup time, i.e. BEFORE the test body's own
    # `migrate_schema_drift_database`/`reset_schema_drift_database_to_nothing`
    # calls ran -- that still-open connection then blocked those
    # calls' own `DROP SCHEMA ... CASCADE` on a lock indefinitely.
    # Every check in this file now goes through `_check(engine)`
    # below, which opens a session only at the exact point it's used,
    # always AFTER this file's own arrangement calls have already run.
    # `pool_pre_ping=True` mirrors `app/db/session.py`'s own real,
    # already-established production engine exactly: a test that calls
    # `migrate_schema_drift_database` a SECOND time (e.g. to re-arrange
    # state mid-test, `TestPreviousRevisionThenUpgradedToHead`) causes
    # that helper's own defensive "terminate every other backend"
    # step (`reset_schema_drift_database_to_nothing`, above) to kill
    # whatever connection this engine's own pool was quietly holding
    # onto from the FIRST check -- pre-ping detects and transparently
    # replaces a dead pooled connection instead of surfacing it as a
    # false `DATABASE_UNAVAILABLE`.
    engine = create_engine(schema_drift_database_url, pool_pre_ping=True)
    yield engine
    engine.dispose()


def _check(engine):
    """Runs the shared compatibility check against a session opened
    fresh, right now -- never a connection left open since fixture
    setup. See `drift_engine`'s own docstring above for why this
    matters."""
    session = Session(engine)
    try:
        return check_schema_compatibility(session)
    finally:
        session.close()


def _alembic_version_rows(engine) -> list[tuple]:
    with engine.connect() as connection:
        return connection.execute(text("SELECT version_num FROM alembic_version")).fetchall()


def _table_exists(engine, table_name: str) -> bool:
    with engine.connect() as connection:
        return (
            connection.execute(
                text("SELECT 1 FROM information_schema.tables WHERE table_name = :name"), {"name": table_name}
            ).first()
            is not None
        )


class TestExpectedRevisionMatchesRealMigrationGraph:
    def test_expected_revision_is_the_real_known_head(self):
        assert expected_revision() == _HEAD


class TestCompatibleAtHead:
    def test_database_at_head_is_compatible(self, schema_drift_database_url, drift_engine):
        migrate_schema_drift_database(schema_drift_database_url, _HEAD)
        result = _check(drift_engine)
        assert result.status is SchemaCompatibilityStatus.COMPATIBLE
        assert result.compatible is True
        assert result.expected_revision == _HEAD
        assert result.actual_revision == _HEAD


class TestSchemaBehindOneRevision:
    """The literal #26A incident, reproduced deliberately and safely
    against the isolated drift database -- never the developer's own
    `economic_intelligence` database."""

    def test_one_revision_behind_is_not_compatible(self, schema_drift_database_url, drift_engine):
        migrate_schema_drift_database(schema_drift_database_url, _ONE_BEFORE_HEAD)
        result = _check(drift_engine)
        assert result.status is SchemaCompatibilityStatus.SCHEMA_BEHIND
        assert result.compatible is False
        assert result.expected_revision == _HEAD
        assert result.actual_revision == _ONE_BEFORE_HEAD

        # No automatic upgrade occurred -- the database is still
        # exactly where this test put it.
        rows = _alembic_version_rows(drift_engine)
        assert rows == [(_ONE_BEFORE_HEAD,)]


class TestSchemaBehindMultipleRevisions:
    def test_three_revisions_behind_is_not_compatible(self, schema_drift_database_url, drift_engine):
        migrate_schema_drift_database(schema_drift_database_url, _THREE_BEFORE_HEAD)
        result = _check(drift_engine)
        assert result.status is SchemaCompatibilityStatus.SCHEMA_BEHIND
        assert result.actual_revision == _THREE_BEFORE_HEAD


class TestSchemaAhead:
    """A revision this packaged application's own migration graph does
    not recognize at all -- simulating a database migrated by a newer
    application version than the one running this check, WITHOUT
    writing a new migration file (#26C source prompt §57: zero new
    migrations this increment). Directly overwrites `alembic_version`'s
    own tracked value via raw SQL on the isolated drift database only."""

    def test_unknown_newer_revision_is_not_compatible(self, schema_drift_database_url, drift_engine):
        migrate_schema_drift_database(schema_drift_database_url, _HEAD)
        with drift_engine.connect() as connection:
            connection.execute(text("UPDATE alembic_version SET version_num = :fake"), {"fake": "9" * 12})
            connection.commit()

        result = _check(drift_engine)
        assert result.status is SchemaCompatibilityStatus.SCHEMA_AHEAD
        assert result.compatible is False
        assert result.expected_revision == _HEAD
        assert result.actual_revision == "9" * 12


class TestUninitializedDatabase:
    """A genuinely fresh database -- no `alembic_version` table at all,
    not merely a downgraded-to-base one (#26C source prompt §10/§35)."""

    def test_no_alembic_version_table_is_not_compatible(self, schema_drift_database_url, drift_engine):
        reset_schema_drift_database_to_nothing(schema_drift_database_url)
        assert _table_exists(drift_engine, "alembic_version") is False

        result = _check(drift_engine)
        assert result.status is SchemaCompatibilityStatus.SCHEMA_UNINITIALIZED
        assert result.compatible is False
        assert result.expected_revision == _HEAD
        assert result.actual_revision is None

        # Confirmed no table was created by the check itself.
        assert _table_exists(drift_engine, "alembic_version") is False
        assert _table_exists(drift_engine, "recorded_monitor_results") is False

    def test_downgraded_to_base_with_an_empty_but_existing_table_is_also_uninitialized(
        self, schema_drift_database_url, drift_engine
    ):
        migrate_schema_drift_database(schema_drift_database_url, "base")
        assert _table_exists(drift_engine, "alembic_version") is True
        assert _alembic_version_rows(drift_engine) == []

        result = _check(drift_engine)
        assert result.status is SchemaCompatibilityStatus.SCHEMA_UNINITIALIZED
        assert result.actual_revision is None


class TestAmbiguousMultipleVersionRows:
    """A branched/multi-head database state -- never guessed at
    (#26C source prompt §11). Alembic's own normal usage never
    produces this against this project's confirmed single-head graph;
    simulated directly via raw SQL on the isolated drift database."""

    def test_two_version_rows_is_not_compatible_and_never_guessed(
        self, schema_drift_database_url, drift_engine
    ):
        migrate_schema_drift_database(schema_drift_database_url, _HEAD)
        with drift_engine.connect() as connection:
            connection.execute(text("INSERT INTO alembic_version (version_num) VALUES (:rev)"), {"rev": "8" * 12})
            connection.commit()

        result = _check(drift_engine)
        assert result.status is SchemaCompatibilityStatus.SCHEMA_AMBIGUOUS
        assert result.compatible is False
        assert result.actual_revision is None


class TestDatabaseUnavailable:
    def test_unreachable_database_is_not_compatible(self, monkeypatch):
        from app.core.config import settings
        from app.db import session as session_module

        monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://localhost:1/does_not_matter")
        session_module._get_engine.cache_clear()
        session_module._get_session_factory.cache_clear()
        try:
            result = check_schema_compatibility()
        finally:
            session_module._get_engine.cache_clear()
            session_module._get_session_factory.cache_clear()

        assert result.status is SchemaCompatibilityStatus.DATABASE_UNAVAILABLE
        assert result.compatible is False
        assert result.actual_revision is None
        assert result.expected_revision == _HEAD


class TestConfigurationMissing:
    def test_unset_database_url_is_not_compatible(self, monkeypatch):
        from app.core.config import settings
        from app.db import session as session_module

        monkeypatch.setattr(settings, "database_url", None)
        session_module._get_engine.cache_clear()
        session_module._get_session_factory.cache_clear()
        try:
            result = check_schema_compatibility()
        finally:
            session_module._get_engine.cache_clear()
            session_module._get_session_factory.cache_clear()

        assert result.status is SchemaCompatibilityStatus.CONFIGURATION_MISSING
        assert result.compatible is False
        assert result.actual_revision is None
        assert result.expected_revision == _HEAD


class TestFreshDatabaseMigratedFromZero:
    """Connects migration correctness with compatibility enforcement
    (#26C source prompt §49): a genuinely fresh database, migrated with
    the real `alembic upgrade head`, is reported compatible -- proving
    the migration chain and the compatibility check agree on what
    "head" means, independently arrived at (one via the files on disk,
    the other via a real `alembic upgrade` run)."""

    def test_zero_to_head_then_compatible(self, schema_drift_database_url, drift_engine):
        reset_schema_drift_database_to_nothing(schema_drift_database_url)
        migrate_schema_drift_database(schema_drift_database_url, _HEAD)
        result = _check(drift_engine)
        assert result.status is SchemaCompatibilityStatus.COMPATIBLE


class TestPreviousRevisionThenUpgradedToHead:
    """The exact remediation sequence #26B §50 specifies for the real
    incident, proven mechanically: behind -> (an explicit, external
    `alembic upgrade`, never performed by the compatibility module
    itself) -> compatible."""

    def test_behind_becomes_compatible_only_after_an_explicit_external_upgrade(
        self, schema_drift_database_url, drift_engine
    ):
        migrate_schema_drift_database(schema_drift_database_url, _ONE_BEFORE_HEAD)
        before = _check(drift_engine)
        assert before.status is SchemaCompatibilityStatus.SCHEMA_BEHIND

        migrate_schema_drift_database(schema_drift_database_url, _HEAD)  # the test harness, not the checker
        after = _check(drift_engine)
        assert after.status is SchemaCompatibilityStatus.COMPATIBLE


class TestReadOnlyNoMutation:
    """Behavioral proof, across every arranged state, that calling the
    compatibility check itself never changes the database (#26C source
    prompt §18/§51)."""

    @pytest.mark.parametrize("revision", [_HEAD, _ONE_BEFORE_HEAD, "base"])
    def test_repeated_checks_never_change_the_recorded_revision(
        self, schema_drift_database_url, drift_engine, revision
    ):
        migrate_schema_drift_database(schema_drift_database_url, revision)
        before = _alembic_version_rows(drift_engine)

        with drift_engine.connect() as connection:
            session = Session(bind=connection)
            check_schema_compatibility(session)
            check_schema_compatibility(session)
            session.close()

        after = _alembic_version_rows(drift_engine)
        assert before == after

    def test_uninitialized_database_gains_no_tables_from_repeated_checks(
        self, schema_drift_database_url, drift_engine
    ):
        reset_schema_drift_database_to_nothing(schema_drift_database_url)
        with drift_engine.connect() as connection:
            session = Session(bind=connection)
            check_schema_compatibility(session)
            check_schema_compatibility(session)
            session.close()
        assert _table_exists(drift_engine, "alembic_version") is False
