"""HTTP-level tests for Increment #26C's `GET /readiness` --
docs/product/production-reliability-deployment-v1.md (#26B) §14/§15/
§16/§17/§19, the frozen contract this route implements.

Every test here goes through the real, unmodified ASGI app
(`tests/api/conftest.py`'s `client` fixture) -- the same real
`session_scope()`/`app.core.config.settings` wiring a real deployment
uses, not a lookalike. `_redirect_database` (autouse, tests/api/conftest.py)
already points `DATABASE_URL` at the always-at-head shared test
database for every test in this file by default; tests below that need
a DIFFERENT database state override it explicitly, using the same
monkeypatch + `lru_cache.cache_clear()` pattern that fixture itself
already establishes.
"""

from app.core.config import settings
from app.db import session as session_module
from tests.conftest import migrate_schema_drift_database

_ONE_BEFORE_HEAD = "f12b7ec0d626"


def _point_database_at(monkeypatch, url: str | None) -> None:
    monkeypatch.setattr(settings, "database_url", url)
    session_module._get_engine.cache_clear()
    session_module._get_session_factory.cache_clear()


class TestReadinessCompatible:
    def test_ready_true_when_database_is_at_head(self, client):
        response = client.get("/readiness")
        assert response.status_code == 200
        body = response.json()
        assert body["ready"] is True
        assert body["reason"] is None
        assert body["expected_schema_revision"] is not None
        assert body["expected_schema_revision"] == body["actual_schema_revision"]
        assert isinstance(body["version"], str) and body["version"] != ""


class TestReadinessSchemaBehind:
    def test_unready_with_schema_mismatch_reason(self, client, monkeypatch, schema_drift_database_url):
        migrate_schema_drift_database(schema_drift_database_url, _ONE_BEFORE_HEAD)
        _point_database_at(monkeypatch, schema_drift_database_url)

        response = client.get("/readiness")
        assert response.status_code == 503
        body = response.json()
        assert body["ready"] is False
        assert body["reason"] == "schema_mismatch"
        assert body["actual_schema_revision"] == _ONE_BEFORE_HEAD
        assert body["expected_schema_revision"] != body["actual_schema_revision"]


class TestReadinessUninitialized:
    def test_unready_for_a_never_migrated_database(self, client, monkeypatch, schema_drift_database_url):
        from tests.conftest import reset_schema_drift_database_to_nothing

        reset_schema_drift_database_to_nothing(schema_drift_database_url)
        _point_database_at(monkeypatch, schema_drift_database_url)

        response = client.get("/readiness")
        assert response.status_code == 503
        body = response.json()
        assert body["ready"] is False
        assert body["reason"] == "schema_mismatch"
        assert body["actual_schema_revision"] is None


class TestReadinessDatabaseUnavailable:
    def test_unready_with_database_unreachable_reason(self, client, monkeypatch):
        _point_database_at(monkeypatch, "postgresql+psycopg://localhost:1/does_not_matter")

        response = client.get("/readiness")
        assert response.status_code == 503
        body = response.json()
        assert body["ready"] is False
        assert body["reason"] == "database_unreachable"
        assert body["actual_schema_revision"] is None


class TestReadinessConfigurationMissing:
    def test_unready_with_configuration_missing_reason(self, client, monkeypatch):
        _point_database_at(monkeypatch, None)

        response = client.get("/readiness")
        assert response.status_code == 503
        body = response.json()
        assert body["ready"] is False
        assert body["reason"] == "configuration_missing"
        assert body["actual_schema_revision"] is None


class TestReadinessDoesNotRequireEconomicData:
    """A freshly migrated-to-head but economically empty database is
    READY from an application/schema perspective -- application
    readiness is never confused with product bootstrap completeness
    (#26C source prompt §19; bootstrap itself is #26F's own job)."""

    def test_ready_true_even_with_zero_economic_rows(self, client):
        # tests/api/conftest.py's _redirect_database already points at
        # the always-at-head shared test database; no economic seed
        # data is arranged by this test at all.
        response = client.get("/readiness")
        assert response.status_code == 200
        assert response.json()["ready"] is True


class TestReadinessResponseShape:
    """Locks the response body to exactly the small, public-safe field
    set #26B §17/§19 froze -- a future accidental addition (a
    connection string, a hostname, a stack trace) would fail this test
    by changing the key set, not merely by chance not being asserted
    on."""

    def test_response_has_exactly_the_frozen_field_set(self, client):
        body = client.get("/readiness").json()
        assert set(body.keys()) == {"ready", "reason", "expected_schema_revision", "actual_schema_revision", "version"}

    def test_response_never_contains_a_connection_string(self, client, monkeypatch):
        _point_database_at(monkeypatch, "postgresql+psycopg://localhost:1/does_not_matter")
        body = client.get("/readiness").json()
        rendered = str(body)
        assert "://" not in rendered
        assert "psycopg" not in rendered
        assert "localhost" not in rendered
