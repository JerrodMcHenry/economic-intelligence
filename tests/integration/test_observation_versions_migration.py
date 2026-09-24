"""Migration tests for `observation_versions` (Increment #31),
exercised against the isolated schema-drift database so the primary
test database's own migrated state is never disturbed.

Proves the three things a migration must actually guarantee: that it is
reversible, that it backfills pre-existing data, and that the invariants
it claims to enforce are genuinely enforced by PostgreSQL rather than by
the application.
"""

import os
import subprocess
import sys
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from tests.conftest import migrate_schema_drift_database, reset_schema_drift_database_to_nothing

pytestmark = pytest.mark.integration

_BEFORE_VERSIONS = "b7c41d92e8a3"
_HEAD = "a6f1c3d95e20"

REPO_ROOT = Path(__file__).resolve().parents[2]

T1 = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)


def _alembic(schema_drift_database_url: str, *args: str) -> None:
    """Run one alembic command against the drift database WITHOUT the
    reset-first behavior of `migrate_schema_drift_database`.

    Backfill can only be tested by migrating FORWARD over data that
    already exists, which a reset-first helper structurally cannot do.
    Same subprocess pattern conftest itself uses; `DATABASE_URL` is
    overridden for this subprocess only.
    """
    env = {**os.environ, "DATABASE_URL": schema_drift_database_url}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args], cwd=REPO_ROOT, env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, f"alembic {' '.join(args)} failed: {result.stdout}\n{result.stderr}"


@contextmanager
def _connect(schema_drift_database_url: str):
    """A short-lived engine per use: migrations terminate existing
    connections, so nothing may be held across one."""
    engine = create_engine(schema_drift_database_url)
    try:
        with engine.connect() as connection:
            yield connection
    finally:
        engine.dispose()


def _seed_pre_version_observation(schema_drift_database_url: str, value: float = 100.0) -> None:
    """One series + observation created while the schema is still at the
    pre-#31 revision -- exactly the shape the backfill must handle."""
    engine = create_engine(schema_drift_database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO economic_series (series_id, title, units, source) "
                    "VALUES ('BACKFILL_TEST', 'Backfill Test', 'Index', 'FRED')"
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO economic_observations (economic_series_id, observation_date, value, created_at)
                    SELECT id, DATE '2026-01-01', :value, TIMESTAMPTZ '2026-02-01 00:00:00+00'
                    FROM economic_series WHERE series_id = 'BACKFILL_TEST'
                    """
                ),
                {"value": value},
            )
    finally:
        engine.dispose()


class TestMigration:
    def test_upgrade_downgrade_upgrade_is_clean(self, schema_drift_database_url):
        reset_schema_drift_database_to_nothing(schema_drift_database_url)
        migrate_schema_drift_database(schema_drift_database_url, _HEAD)

        _alembic(schema_drift_database_url, "downgrade", _BEFORE_VERSIONS)
        with _connect(schema_drift_database_url) as connection:
            assert connection.execute(text("SELECT to_regclass('observation_versions')")).scalar_one() is None

        _alembic(schema_drift_database_url, "upgrade", _HEAD)
        with _connect(schema_drift_database_url) as connection:
            assert connection.execute(text("SELECT to_regclass('observation_versions')")).scalar_one() is not None

    def test_downgrade_preserves_existing_observation_data(self, schema_drift_database_url):
        """The table is additive: dropping it must not touch the
        canonical observations it was derived from."""
        reset_schema_drift_database_to_nothing(schema_drift_database_url)
        migrate_schema_drift_database(schema_drift_database_url, _BEFORE_VERSIONS)
        _seed_pre_version_observation(schema_drift_database_url)

        _alembic(schema_drift_database_url, "upgrade", _HEAD)
        _alembic(schema_drift_database_url, "downgrade", _BEFORE_VERSIONS)

        with _connect(schema_drift_database_url) as connection:
            surviving = connection.execute(
                text("SELECT value FROM economic_observations WHERE observation_date = DATE '2026-01-01'")
            ).scalar_one()
        assert surviving == 100.0

    def test_backfill_creates_one_marked_open_version_per_existing_observation(self, schema_drift_database_url):
        reset_schema_drift_database_to_nothing(schema_drift_database_url)
        migrate_schema_drift_database(schema_drift_database_url, _BEFORE_VERSIONS)
        _seed_pre_version_observation(schema_drift_database_url)

        _alembic(schema_drift_database_url, "upgrade", _HEAD)

        with _connect(schema_drift_database_url) as connection:
            row = connection.execute(
                text(
                    """
                    SELECT v.value, v.recorded_from, v.recorded_to, v.change_type, v.origin, v.is_backfilled
                    FROM observation_versions v
                    JOIN economic_series s ON s.id = v.economic_series_id
                    WHERE s.series_id = 'BACKFILL_TEST'
                    """
                )
            ).one()

        value, recorded_from, recorded_to, change_type, origin, is_backfilled = row
        assert value == 100.0
        # The observation's own created_at -- honestly "this value
        # existed by then", never "this was the first publication".
        assert recorded_from == datetime(2026, 2, 1, tzinfo=timezone.utc)
        assert recorded_to is None
        assert change_type == "BACKFILL"
        assert origin == "BACKFILL"
        assert is_backfilled is True

    def test_backfill_leaves_no_observation_without_history(self, schema_drift_database_url):
        reset_schema_drift_database_to_nothing(schema_drift_database_url)
        migrate_schema_drift_database(schema_drift_database_url, _BEFORE_VERSIONS)
        _seed_pre_version_observation(schema_drift_database_url)

        _alembic(schema_drift_database_url, "upgrade", _HEAD)

        with _connect(schema_drift_database_url) as connection:
            orphans = connection.execute(
                text(
                    """
                    SELECT count(*) FROM economic_observations o
                    WHERE NOT EXISTS (
                        SELECT 1 FROM observation_versions v
                        WHERE v.economic_series_id = o.economic_series_id
                          AND v.observation_date = o.observation_date
                    )
                    """
                )
            ).scalar_one()
        assert orphans == 0


class TestMigrationEnforcedInvariants:
    """The invariants are asserted against PostgreSQL itself: each test
    seeds through raw SQL, bypassing the repository entirely, so a passing
    test means the database refuses the write -- not that the application
    declined to attempt it."""

    @pytest.fixture(autouse=True)
    def _at_head(self, schema_drift_database_url):
        reset_schema_drift_database_to_nothing(schema_drift_database_url)
        migrate_schema_drift_database(schema_drift_database_url, _BEFORE_VERSIONS)
        # Seeded BEFORE the versioning migration so the backfilled open
        # row these tests collide with is produced by the migration.
        _seed_pre_version_observation(schema_drift_database_url)
        _alembic(schema_drift_database_url, "upgrade", _HEAD)

    def _insert_version(self, url, recorded_from, recorded_to, observation_date=date(2026, 1, 1)):
        engine = create_engine(url)
        try:
            with engine.begin() as connection:
                series_id = connection.execute(
                    text("SELECT id FROM economic_series WHERE series_id = 'BACKFILL_TEST'")
                ).scalar_one()
                connection.execute(
                    text(
                        """
                        INSERT INTO observation_versions (
                            economic_series_id, observation_date, value, recorded_from, recorded_to,
                            change_type, origin, is_backfilled
                        ) VALUES (:series_id, :observation_date, 1.0, :recorded_from, :recorded_to,
                                  'REVISED', 'SERIES_SYNC', false)
                        """
                    ),
                    {
                        "series_id": series_id,
                        "observation_date": observation_date,
                        "recorded_from": recorded_from,
                        "recorded_to": recorded_to,
                    },
                )
        finally:
            engine.dispose()

    def test_a_second_open_version_is_rejected_by_the_database(self, schema_drift_database_url):
        # The backfilled row is already open for this (series, date).
        with pytest.raises(Exception, match="uq_observation_version_one_open_per_series_date"):
            self._insert_version(schema_drift_database_url, recorded_from=T2, recorded_to=None)

    def test_a_backwards_interval_is_rejected_by_the_database(self, schema_drift_database_url):
        with pytest.raises(Exception, match="ck_observation_version_interval"):
            self._insert_version(schema_drift_database_url, recorded_from=T2, recorded_to=T1)

    def test_an_equal_from_and_to_is_rejected_by_the_database(self, schema_drift_database_url):
        """A zero-length interval would be invisible to every half-open
        as-of query -- a version that exists but can never be observed."""
        with pytest.raises(Exception, match="ck_observation_version_interval"):
            self._insert_version(schema_drift_database_url, recorded_from=T1, recorded_to=T1)

    def test_two_versions_starting_at_the_same_instant_are_rejected(self, schema_drift_database_url):
        self._insert_version(schema_drift_database_url, recorded_from=T1, recorded_to=T2)
        with pytest.raises(Exception, match="uq_observation_version_series_date_from"):
            self._insert_version(schema_drift_database_url, recorded_from=T1, recorded_to=T2 + timedelta(days=1))
