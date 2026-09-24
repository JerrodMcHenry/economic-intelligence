"""Real-PostgreSQL tests for Increment #26D's deployment release
command (`app.operations.release`) -- the ONE and ONLY place this
application's own database schema is ever advanced.
docs/product/production-reliability-deployment-v1.md (#26B) §11-24,
ADR-027. Exercised entirely against the isolated schema-drift database
(`tests/conftest.py`), never `TEST_DATABASE_URL` or the developer's
own `economic_intelligence` database.
"""

from unittest.mock import patch

from sqlalchemy import create_engine, text

import pytest

from app.core.schema_compatibility import SchemaCompatibilityResult, SchemaCompatibilityStatus, check_schema_compatibility
from app.operations.release import main, migrate, preflight
from tests.conftest import migrate_schema_drift_database, reset_schema_drift_database_to_nothing

pytestmark = pytest.mark.integration

_HEAD = "a6f1c3d95e20"
_ONE_BEFORE_HEAD = "e7b3d51c8a94"
_THREE_BEFORE_HEAD = "b7c41d92e8a3"


@pytest.fixture(autouse=True)
def _point_database_at_drift_db(monkeypatch, schema_drift_database_url):
    """Every test in this file targets the isolated schema-drift
    database via the real `settings.database_url` -- the actual
    production wiring `app.operations.release` itself uses, not a
    lookalike -- reverted automatically after each test."""
    from app.core.config import settings
    from app.db import session as session_module

    monkeypatch.setattr(settings, "database_url", schema_drift_database_url)
    session_module._get_engine.cache_clear()
    session_module._get_session_factory.cache_clear()
    yield
    session_module._get_engine.cache_clear()
    session_module._get_session_factory.cache_clear()


def _actual_revision(schema_drift_database_url: str) -> str | None:
    engine = create_engine(schema_drift_database_url)
    try:
        with engine.connect() as connection:
            rows = connection.execute(text("SELECT version_num FROM alembic_version")).fetchall()
    finally:
        engine.dispose()
    return rows[0][0] if rows else None


class TestPreflightSafeStates:
    def test_compatible_is_safe(self, schema_drift_database_url):
        migrate_schema_drift_database(schema_drift_database_url, _HEAD)
        assert preflight() == 0

    def test_behind_is_safe(self, schema_drift_database_url):
        migrate_schema_drift_database(schema_drift_database_url, _ONE_BEFORE_HEAD)
        assert preflight() == 0

    def test_uninitialized_is_safe(self, schema_drift_database_url):
        reset_schema_drift_database_to_nothing(schema_drift_database_url)
        assert preflight() == 0


class TestPreflightRefusedStates:
    def test_ahead_is_refused(self, schema_drift_database_url, capsys):
        migrate_schema_drift_database(schema_drift_database_url, _HEAD)
        engine = create_engine(schema_drift_database_url)
        with engine.connect() as connection:
            connection.execute(text("UPDATE alembic_version SET version_num = :fake"), {"fake": "9" * 12})
            connection.commit()
        engine.dispose()

        assert preflight() == 2
        err = capsys.readouterr().err
        assert "SCHEMA_AHEAD" in err
        assert "Refusing to migrate" in err

    def test_ambiguous_is_refused(self, schema_drift_database_url):
        migrate_schema_drift_database(schema_drift_database_url, _HEAD)
        engine = create_engine(schema_drift_database_url)
        with engine.connect() as connection:
            connection.execute(text("INSERT INTO alembic_version (version_num) VALUES (:rev)"), {"rev": "8" * 12})
            connection.commit()
        engine.dispose()

        assert preflight() == 2

    def test_database_unavailable_is_refused(self, monkeypatch):
        from app.core.config import settings
        from app.db import session as session_module

        monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://localhost:1/does_not_matter")
        session_module._get_engine.cache_clear()
        session_module._get_session_factory.cache_clear()
        try:
            assert preflight() == 2
        finally:
            session_module._get_engine.cache_clear()
            session_module._get_session_factory.cache_clear()

    def test_configuration_missing_is_refused(self, monkeypatch, capsys):
        from app.core.config import settings
        from app.db import session as session_module

        monkeypatch.setattr(settings, "database_url", None)
        session_module._get_engine.cache_clear()
        session_module._get_session_factory.cache_clear()
        try:
            assert preflight() == 2
        finally:
            session_module._get_engine.cache_clear()
            session_module._get_session_factory.cache_clear()
        assert "database is not configured" in capsys.readouterr().err


class TestMigrateFromBehind:
    def test_one_revision_behind_migrates_to_compatible(self, schema_drift_database_url):
        migrate_schema_drift_database(schema_drift_database_url, _ONE_BEFORE_HEAD)
        assert migrate() == 0
        assert check_schema_compatibility().status is SchemaCompatibilityStatus.COMPATIBLE
        assert _actual_revision(schema_drift_database_url) == _HEAD

    def test_multiple_revisions_behind_migrates_to_compatible(self, schema_drift_database_url):
        migrate_schema_drift_database(schema_drift_database_url, _THREE_BEFORE_HEAD)
        assert migrate() == 0
        assert _actual_revision(schema_drift_database_url) == _HEAD


class TestMigrateFromFresh:
    def test_fresh_database_migrates_to_compatible(self, schema_drift_database_url):
        reset_schema_drift_database_to_nothing(schema_drift_database_url)
        assert migrate() == 0
        assert _actual_revision(schema_drift_database_url) == _HEAD

    def test_fresh_database_seeds_the_curated_release_catalog_with_zero_provider_calls(self, schema_drift_database_url):
        """Remember migrations may seed release-catalog data --
        verified directly, without any FRED/provider call (this
        module imports no provider client at all, confirmed also by
        the architecture guard file)."""
        reset_schema_drift_database_to_nothing(schema_drift_database_url)
        migrate()

        engine = create_engine(schema_drift_database_url)
        try:
            with engine.connect() as connection:
                count = connection.execute(text("SELECT COUNT(*) FROM economic_releases")).scalar_one()
        finally:
            engine.dispose()
        assert count == 6  # the six curated V1 releases, seeded by the migration chain itself


class TestMigrateIdempotency:
    def test_migrating_twice_at_head_is_a_safe_no_op(self, schema_drift_database_url, capsys):
        migrate_schema_drift_database(schema_drift_database_url, _HEAD)
        assert migrate() == 0
        assert "Already at head" in capsys.readouterr().out

        with patch("app.operations.release.command.upgrade") as mocked_upgrade:
            assert migrate() == 0
            mocked_upgrade.assert_not_called()
        assert _actual_revision(schema_drift_database_url) == _HEAD


class TestMigrateRefusedStates:
    def test_ahead_refuses_and_never_calls_alembic_upgrade(self, schema_drift_database_url):
        migrate_schema_drift_database(schema_drift_database_url, _HEAD)
        engine = create_engine(schema_drift_database_url)
        with engine.connect() as connection:
            connection.execute(text("UPDATE alembic_version SET version_num = :fake"), {"fake": "9" * 12})
            connection.commit()
        engine.dispose()

        with patch("app.operations.release.command.upgrade") as mocked_upgrade:
            assert migrate() == 2
            mocked_upgrade.assert_not_called()
        assert _actual_revision(schema_drift_database_url) == "9" * 12  # unchanged, never "corrected"

    def test_database_unavailable_refuses_and_never_calls_alembic_upgrade(self, monkeypatch):
        from app.core.config import settings
        from app.db import session as session_module

        monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://localhost:1/does_not_matter")
        session_module._get_engine.cache_clear()
        session_module._get_session_factory.cache_clear()
        try:
            with patch("app.operations.release.command.upgrade") as mocked_upgrade:
                assert migrate() == 2
                mocked_upgrade.assert_not_called()
        finally:
            session_module._get_engine.cache_clear()
            session_module._get_session_factory.cache_clear()


class TestMigrateFailureHandling:
    def test_a_raising_alembic_upgrade_is_reported_safely_and_never_crashes(self, schema_drift_database_url, capsys):
        migrate_schema_drift_database(schema_drift_database_url, _ONE_BEFORE_HEAD)
        with patch("app.operations.release.command.upgrade", side_effect=RuntimeError("simulated failure")):
            exit_code = migrate()
        assert exit_code == 2
        err = capsys.readouterr().err
        assert "migration failed" in err
        assert "RuntimeError" in err
        assert "simulated failure" not in err  # only the exception TYPE is ever reported, never its message
        assert "://" not in err

    def test_a_verified_no_op_upgrade_is_reported_as_failure_not_silently_accepted(self, schema_drift_database_url, capsys):
        """If `alembic upgrade` completes without raising but the
        database is somehow still not COMPATIBLE afterward (simulated
        here directly), migrate() must report failure -- success is
        never inferred merely from "the upgrade call didn't raise"."""
        migrate_schema_drift_database(schema_drift_database_url, _ONE_BEFORE_HEAD)
        still_behind = SchemaCompatibilityResult(SchemaCompatibilityStatus.SCHEMA_BEHIND, _HEAD, _ONE_BEFORE_HEAD)
        with patch("app.operations.release.command.upgrade"):
            with patch("app.operations.release.check_schema_compatibility", return_value=still_behind):
                exit_code = migrate()
        assert exit_code == 2
        assert "still not compatible" in capsys.readouterr().err


class TestNoSecretLeakage:
    def test_no_output_ever_contains_a_connection_string(self, schema_drift_database_url, capsys):
        migrate_schema_drift_database(schema_drift_database_url, _ONE_BEFORE_HEAD)
        migrate()
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "://" not in combined
        assert "psycopg" not in combined


class TestMainEntrypoint:
    def test_preflight_subcommand(self, schema_drift_database_url):
        migrate_schema_drift_database(schema_drift_database_url, _HEAD)
        assert main(["preflight"]) == 0

    def test_migrate_subcommand(self, schema_drift_database_url):
        migrate_schema_drift_database(schema_drift_database_url, _ONE_BEFORE_HEAD)
        assert main(["migrate"]) == 0
        assert _actual_revision(schema_drift_database_url) == _HEAD

    def test_no_subcommand_is_rejected_by_argument_parsing(self):
        with pytest.raises(SystemExit):
            main([])


class TestReadinessTransitionsOnlyViaExplicitMigration:
    """The central integration proof (#26D source prompt §23): behind
    DB -> web readiness unready -> EXPLICIT migration command ->
    readiness ready. The migration COMMAND causes the transition, the
    web process itself never does."""

    def test_readiness_flips_only_after_the_explicit_migrate_call(self, schema_drift_database_url):
        from fastapi.testclient import TestClient

        from app.main import app

        migrate_schema_drift_database(schema_drift_database_url, _ONE_BEFORE_HEAD)
        client = TestClient(app)

        before = client.get("/readiness")
        assert before.status_code == 503
        assert before.json()["ready"] is False

        exit_code = migrate()
        assert exit_code == 0

        after = client.get("/readiness")
        assert after.status_code == 200
        assert after.json()["ready"] is True
