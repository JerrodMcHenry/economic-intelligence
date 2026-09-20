"""Integration tests for Increment #26E's read-only maintenance-health
CLI (`app.operations.maintenance_health`), exercised via direct
function call against the isolated schema-drift database -- never
`TEST_DATABASE_URL` or the developer's own `economic_intelligence`
database.
"""

import json

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import pytest

from app.db.models import MaintenanceSweep
from app.operations.maintenance_health import main
from tests.conftest import migrate_schema_drift_database

pytestmark = pytest.mark.integration

_HEAD = "b7c41d92e8a3"
_ONE_BEFORE_HEAD = "f5420059a092"


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


def _insert_sweep(schema_drift_database_url, started_at, finished_at=None, failed_count=None):
    engine = create_engine(schema_drift_database_url, pool_pre_ping=True)
    try:
        session = Session(engine)
        try:
            session.add(
                MaintenanceSweep(
                    started_at=started_at,
                    finished_at=finished_at,
                    status="SUCCEEDED" if finished_at else None,
                    due_count=0 if finished_at else None,
                    processed_count=0 if finished_at else None,
                    failed_count=failed_count if finished_at else None,
                )
            )
            session.commit()
        finally:
            session.close()
    finally:
        engine.dispose()


class TestExitCodes:
    def test_healthy_exits_zero(self, schema_drift_database_url):
        from datetime import datetime, timedelta, timezone

        migrate_schema_drift_database(schema_drift_database_url, _HEAD)
        now = datetime.now(timezone.utc)
        _insert_sweep(schema_drift_database_url, started_at=now - timedelta(minutes=2), finished_at=now - timedelta(minutes=1), failed_count=0)
        assert main([]) == 0

    def test_never_run_exits_one(self, schema_drift_database_url):
        migrate_schema_drift_database(schema_drift_database_url, _HEAD)
        assert main([]) == 1

    def test_stale_exits_one(self, schema_drift_database_url):
        from datetime import datetime, timedelta, timezone

        migrate_schema_drift_database(schema_drift_database_url, _HEAD)
        now = datetime.now(timezone.utc)
        _insert_sweep(schema_drift_database_url, started_at=now - timedelta(hours=10), finished_at=now - timedelta(hours=10), failed_count=0)
        assert main([]) == 1

    def test_degraded_exits_one(self, schema_drift_database_url):
        from datetime import datetime, timedelta, timezone

        migrate_schema_drift_database(schema_drift_database_url, _HEAD)
        now = datetime.now(timezone.utc)
        _insert_sweep(schema_drift_database_url, started_at=now - timedelta(minutes=5), finished_at=now - timedelta(minutes=4), failed_count=1)
        assert main([]) == 1

    def test_schema_incompatible_exits_two(self, schema_drift_database_url):
        migrate_schema_drift_database(schema_drift_database_url, _ONE_BEFORE_HEAD)
        assert main([]) == 2

    def test_database_unavailable_exits_two(self, monkeypatch):
        from app.core.config import settings
        from app.db import session as session_module

        monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://localhost:1/does_not_matter")
        session_module._get_engine.cache_clear()
        session_module._get_session_factory.cache_clear()
        try:
            assert main([]) == 2
        finally:
            session_module._get_engine.cache_clear()
            session_module._get_session_factory.cache_clear()


class TestJsonOutput:
    def test_json_flag_emits_valid_json_with_expected_shape(self, schema_drift_database_url, capsys):
        migrate_schema_drift_database(schema_drift_database_url, _HEAD)
        main(["--json"])
        out = capsys.readouterr().out
        body = json.loads(out)
        assert body["schema_compatible"] is True
        assert body["status"] == "NEVER_RUN"
        assert body["latest_sweep"] is None


class TestThresholdOverrides:
    def test_custom_stale_threshold_is_honored(self, schema_drift_database_url):
        from datetime import datetime, timedelta, timezone

        migrate_schema_drift_database(schema_drift_database_url, _HEAD)
        now = datetime.now(timezone.utc)
        _insert_sweep(schema_drift_database_url, started_at=now - timedelta(hours=2), finished_at=now - timedelta(hours=2), failed_count=0)
        # Default 3h threshold: 2h old is still healthy.
        assert main([]) == 0
        # A 1h override makes the same 2h-old sweep stale.
        assert main(["--stale-threshold-hours", "1"]) == 1


class TestNoSecretLeakage:
    def test_output_never_contains_a_connection_string(self, schema_drift_database_url, capsys):
        migrate_schema_drift_database(schema_drift_database_url, _ONE_BEFORE_HEAD)
        main([])
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "://" not in combined
        assert "psycopg" not in combined
