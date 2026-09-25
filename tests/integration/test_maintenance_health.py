"""Real-PostgreSQL tests for Increment #26E's maintenance-health
service/repository (`app.services.maintenance_health`,
`MaintenanceRepository.get_latest_finished_sweep`). Exercised entirely
against the isolated schema-drift database (`tests/conftest.py`) --
never `TEST_DATABASE_URL` (shared with every other suite) or the
developer's own `economic_intelligence` database -- so this file can
freely control both the database's own MIGRATION state (for the
schema-incompatible scenario) and its `maintenance_sweeps` table
content (for the health-status scenarios) without any risk of
interfering with, or being polluted by, any other test file that
happens to share `maintenance_sweeps` on `TEST_DATABASE_URL`.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import pytest

from app.db.models import MaintenanceSweep
from app.domain.maintenance_health import MaintenanceHealthStatus
from app.services.maintenance_health import check_maintenance_health
from tests.conftest import migrate_schema_drift_database

pytestmark = pytest.mark.integration

_HEAD = "b8d2e4f60a17"
_ONE_BEFORE_HEAD = "a6f1c3d95e20"
NOW = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)
STALE_THRESHOLD = timedelta(hours=3)
UNFINISHED_GRACE = timedelta(minutes=30)


@pytest.fixture(autouse=True)
def _point_database_at_drift_db(monkeypatch, schema_drift_database_url):
    from app.core.config import settings
    from app.db import session as session_module

    monkeypatch.setattr(settings, "database_url", schema_drift_database_url)
    session_module._get_engine.cache_clear()
    session_module._get_session_factory.cache_clear()
    yield
    session_module._get_engine.cache_clear()
    session_module._get_session_factory.cache_clear()


def _insert_sweep(schema_drift_database_url, started_at, finished_at=None, failed_count=None, due_count=0, processed_count=0):
    engine = create_engine(schema_drift_database_url, pool_pre_ping=True)
    try:
        session = Session(engine)
        try:
            sweep = MaintenanceSweep(
                started_at=started_at,
                finished_at=finished_at,
                status="SUCCEEDED" if finished_at else None,
                due_count=due_count if finished_at else None,
                processed_count=processed_count if finished_at else None,
                failed_count=failed_count if finished_at else None,
            )
            session.add(sweep)
            session.commit()
        finally:
            session.close()
    finally:
        engine.dispose()


def _check(**overrides):
    kwargs = {"now": NOW, "stale_threshold": STALE_THRESHOLD, "unfinished_grace_period": UNFINISHED_GRACE}
    kwargs.update(overrides)
    return check_maintenance_health(**kwargs)


class TestNeverRun:
    def test_fresh_database_with_zero_sweeps_is_never_run(self, schema_drift_database_url):
        migrate_schema_drift_database(schema_drift_database_url, _HEAD)
        result = _check()
        assert result.schema_compatibility.compatible is True
        assert result.health.status is MaintenanceHealthStatus.NEVER_RUN


class TestHealthy:
    def test_recent_successful_zero_work_sweep_is_healthy(self, schema_drift_database_url):
        migrate_schema_drift_database(schema_drift_database_url, _HEAD)
        _insert_sweep(schema_drift_database_url, started_at=NOW - timedelta(minutes=5), finished_at=NOW - timedelta(minutes=4), failed_count=0)
        result = _check()
        assert result.health.status is MaintenanceHealthStatus.HEALTHY


class TestStale:
    def test_old_completed_sweep_is_stale(self, schema_drift_database_url):
        migrate_schema_drift_database(schema_drift_database_url, _HEAD)
        _insert_sweep(schema_drift_database_url, started_at=NOW - timedelta(hours=6), finished_at=NOW - timedelta(hours=6), failed_count=0)
        result = _check()
        assert result.health.status is MaintenanceHealthStatus.STALE


class TestUnfinished:
    def test_old_unfinished_sweep_is_unfinished(self, schema_drift_database_url):
        migrate_schema_drift_database(schema_drift_database_url, _HEAD)
        _insert_sweep(schema_drift_database_url, started_at=NOW - timedelta(hours=2), finished_at=None)
        result = _check()
        assert result.health.status is MaintenanceHealthStatus.UNFINISHED

    def test_recent_in_progress_sweep_is_not_prematurely_unfinished(self, schema_drift_database_url):
        migrate_schema_drift_database(schema_drift_database_url, _HEAD)
        _insert_sweep(schema_drift_database_url, started_at=NOW - timedelta(hours=1), finished_at=NOW - timedelta(hours=1), failed_count=0)
        _insert_sweep(schema_drift_database_url, started_at=NOW - timedelta(minutes=1), finished_at=None)
        result = _check()
        assert result.health.status is not MaintenanceHealthStatus.UNFINISHED
        assert result.health.status is MaintenanceHealthStatus.HEALTHY


class TestFailureCount:
    def test_recent_completed_sweep_with_failures_is_degraded(self, schema_drift_database_url):
        migrate_schema_drift_database(schema_drift_database_url, _HEAD)
        _insert_sweep(schema_drift_database_url, started_at=NOW - timedelta(minutes=10), finished_at=NOW - timedelta(minutes=9), failed_count=3)
        result = _check()
        assert result.health.status is MaintenanceHealthStatus.DEGRADED


class TestMultipleSweeps:
    def test_latest_attempt_and_latest_success_are_both_reported_and_deterministic(self, schema_drift_database_url):
        migrate_schema_drift_database(schema_drift_database_url, _HEAD)
        _insert_sweep(schema_drift_database_url, started_at=NOW - timedelta(hours=3), finished_at=NOW - timedelta(hours=3), failed_count=0)
        _insert_sweep(schema_drift_database_url, started_at=NOW - timedelta(hours=2), finished_at=NOW - timedelta(hours=2), failed_count=1)
        _insert_sweep(schema_drift_database_url, started_at=NOW - timedelta(minutes=5), finished_at=None)  # currently in progress
        result = _check()
        # The most recent attempt is the in-progress one, within grace
        # -- overall status falls back to the latest COMPLETED sweep,
        # which is the one with failed_count=1 (2 hours ago), not the
        # oldest, fully-healthy one.
        assert result.health.latest_sweep.finished_at is None
        assert result.health.latest_finished_sweep.failed_count == 1
        assert result.health.status is MaintenanceHealthStatus.DEGRADED


class TestSchemaIncompatible:
    def test_behind_schema_refuses_to_interpret_sweep_history(self, schema_drift_database_url):
        migrate_schema_drift_database(schema_drift_database_url, _ONE_BEFORE_HEAD)
        result = _check()
        assert result.schema_compatibility.compatible is False
        assert result.health is None


class TestDatabaseUnavailable:
    def test_unreachable_database_is_reported_via_schema_compatibility(self, monkeypatch):
        from app.core.config import settings
        from app.db import session as session_module

        monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://localhost:1/does_not_matter")
        session_module._get_engine.cache_clear()
        session_module._get_session_factory.cache_clear()
        try:
            result = _check()
        finally:
            session_module._get_engine.cache_clear()
            session_module._get_session_factory.cache_clear()
        assert result.schema_compatibility.compatible is False
        assert result.health is None


class TestReadOnly:
    def test_health_check_creates_zero_rows(self, schema_drift_database_url):
        migrate_schema_drift_database(schema_drift_database_url, _HEAD)
        _insert_sweep(schema_drift_database_url, started_at=NOW - timedelta(minutes=5), finished_at=NOW - timedelta(minutes=4), failed_count=0)

        engine = create_engine(schema_drift_database_url, pool_pre_ping=True)
        try:
            with engine.connect() as connection:
                from sqlalchemy import func, select

                before = Session(bind=connection).execute(select(func.count()).select_from(MaintenanceSweep)).scalar_one()
        finally:
            engine.dispose()

        _check()
        _check()

        engine = create_engine(schema_drift_database_url, pool_pre_ping=True)
        try:
            with engine.connect() as connection:
                from sqlalchemy import func, select

                after = Session(bind=connection).execute(select(func.count()).select_from(MaintenanceSweep)).scalar_one()
        finally:
            engine.dispose()

        assert before == after == 1
