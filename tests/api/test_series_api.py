"""GET /api/v1/series/{series_id} (FRED-backed metadata) and
POST /api/v1/series/{series_id}/sync (FRED-backed, persists to the
isolated test database).

FRED is mocked at the narrowest sensible boundary -- `FREDClient`'s own
methods -- never httpx, never internal deterministic service/domain
logic. No live network call occurs anywhere in this file.
"""

from unittest.mock import patch

from sqlalchemy import text

from app.clients.fred import FREDAuthError, FREDClient, FREDSeriesNotFoundError, FREDTimeoutError, FREDUpstreamError


class TestGetSeriesMetadata:
    def test_missing_fred_configuration_returns_503(self, client, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "fred_api_key", None)
        response = client.get("/api/v1/series/UNRATE")
        assert response.status_code == 503
        assert "FRED_API_KEY" not in response.text  # no secret-adjacent detail leaked

    def test_success_exact_response_contract(self, client, fred_configured):
        with patch.object(FREDClient, "get_series_info", return_value={"id": "UNRATE", "title": "Unemployment Rate", "units": "Percent"}), \
             patch.object(FREDClient, "get_observations", return_value=[
                 {"date": "2024-02-01", "value": "3.9"},
                 {"date": "2024-01-01", "value": "3.8"},
             ]):
            response = client.get("/api/v1/series/UNRATE")

        assert response.status_code == 200
        assert response.json() == {
            "series_id": "UNRATE",
            "title": "Unemployment Rate",
            "units": "Percent",
            "source": "FRED",
            "observations": [
                {"date": "2024-01-01", "value": 3.8},  # normalized to chronological order
                {"date": "2024-02-01", "value": 3.9},
            ],
        }

    def test_missing_observation_value_parses_as_null(self, client, fred_configured):
        """FRED represents a missing observation as the literal string '.'."""
        with patch.object(FREDClient, "get_series_info", return_value={"id": "UNRATE", "title": "t", "units": "u"}), \
             patch.object(FREDClient, "get_observations", return_value=[{"date": "2024-01-01", "value": "."}]):
            response = client.get("/api/v1/series/UNRATE")
        assert response.json()["observations"] == [{"date": "2024-01-01", "value": None}]

    def test_series_not_found_returns_404(self, client, fred_configured):
        with patch.object(FREDClient, "get_series_info", side_effect=FREDSeriesNotFoundError("not found")):
            response = client.get("/api/v1/series/NOPE")
        assert response.status_code == 404
        assert "not found" not in response.json()["detail"] or "NOPE" in response.json()["detail"]

    def test_fred_auth_error_returns_503_no_key_leaked(self, client, fred_configured):
        with patch.object(FREDClient, "get_series_info", side_effect=FREDAuthError("real upstream message with secret-looking-key=ABC123")):
            response = client.get("/api/v1/series/UNRATE")
        assert response.status_code == 503
        assert "ABC123" not in response.text  # our mapping never echoes the raw upstream message

    def test_fred_timeout_returns_504(self, client, fred_configured):
        with patch.object(FREDClient, "get_series_info", side_effect=FREDTimeoutError("timed out")):
            response = client.get("/api/v1/series/UNRATE")
        assert response.status_code == 504

    def test_fred_upstream_error_returns_502(self, client, fred_configured):
        with patch.object(FREDClient, "get_series_info", side_effect=FREDUpstreamError("bad gateway equivalent")):
            response = client.get("/api/v1/series/UNRATE")
        assert response.status_code == 502

    def test_malformed_provider_response_maps_to_upstream_error(self, client, fred_configured):
        """get_series's own KeyError/ValueError-catching maps a
        malformed observations payload (missing "value") to
        FREDUpstreamError -> 502, not a raw 500."""
        with patch.object(FREDClient, "get_series_info", return_value={"id": "UNRATE", "title": "t", "units": "u"}), \
             patch.object(FREDClient, "get_observations", return_value=[{"date": "2024-01-01"}]):
            response = client.get("/api/v1/series/UNRATE")
        assert response.status_code == 502

    def test_no_stack_trace_or_python_internals_in_any_failure_body(self, client, fred_configured):
        with patch.object(FREDClient, "get_series_info", side_effect=FREDUpstreamError("boom")):
            response = client.get("/api/v1/series/UNRATE")
        body_text = response.text.lower()
        for forbidden in ("traceback", "site-packages", ".py\"", "raise ", "exception in"):
            assert forbidden not in body_text


class TestSyncSeries:
    def test_missing_fred_configuration_returns_503(self, client, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "fred_api_key", None)
        response = client.post("/api/v1/series/UNRATE/sync")
        assert response.status_code == 503

    def test_successful_sync_response_contract_and_persistence(self, client, fred_configured, seed_session):
        with patch.object(FREDClient, "get_series_info", return_value={"id": "UNRATE", "title": "Unemployment Rate", "units": "Percent"}), \
             patch.object(FREDClient, "get_observations", return_value=[
                 # FRED returns newest-first; the service reverses this to chronological.
                 {"date": "2024-02-01", "value": "3.9"}, {"date": "2024-01-01", "value": "3.8"}
             ]):
            response = client.post("/api/v1/series/UNRATE/sync")

        assert response.status_code == 200
        body = response.json()
        assert body["series_id"] == "UNRATE"
        assert body["observations"] == [{"date": "2024-01-01", "value": 3.8}, {"date": "2024-02-01", "value": 3.9}]

        # Persisted for real, verified via a separate connection.
        row = seed_session.execute(text("SELECT title, units FROM economic_series WHERE series_id = 'UNRATE'")).fetchone()
        assert row is not None and row[0] == "Unemployment Rate" and row[1] == "Percent"
        obs_count = seed_session.execute(text("SELECT count(*) FROM economic_observations")).scalar_one()
        assert obs_count == 2

    def test_repeated_sync_is_idempotent_no_duplicate_observations(self, client, fred_configured, seed_session):
        with patch.object(FREDClient, "get_series_info", return_value={"id": "UNRATE", "title": "Unemployment Rate", "units": "Percent"}), \
             patch.object(FREDClient, "get_observations", return_value=[{"date": "2024-01-01", "value": "3.8"}]):
            client.post("/api/v1/series/UNRATE/sync")
            client.post("/api/v1/series/UNRATE/sync")

        series_count = seed_session.execute(text("SELECT count(*) FROM economic_series WHERE series_id = 'UNRATE'")).scalar_one()
        obs_count = seed_session.execute(text("SELECT count(*) FROM economic_observations")).scalar_one()
        assert series_count == 1
        assert obs_count == 1

    def test_repeated_sync_updates_changed_observation_value(self, client, fred_configured, seed_session):
        with patch.object(FREDClient, "get_series_info", return_value={"id": "UNRATE", "title": "t", "units": "u"}), \
             patch.object(FREDClient, "get_observations", return_value=[{"date": "2024-01-01", "value": "3.8"}]):
            client.post("/api/v1/series/UNRATE/sync")
        with patch.object(FREDClient, "get_series_info", return_value={"id": "UNRATE", "title": "t", "units": "u"}), \
             patch.object(FREDClient, "get_observations", return_value=[{"date": "2024-01-01", "value": "4.2"}]):
            response = client.post("/api/v1/series/UNRATE/sync")

        assert response.json()["observations"] == [{"date": "2024-01-01", "value": 4.2}]
        value = seed_session.execute(text("SELECT value FROM economic_observations")).scalar_one()
        assert value == 4.2

    def test_series_not_found_returns_404(self, client, fred_configured):
        with patch.object(FREDClient, "get_series_info", side_effect=FREDSeriesNotFoundError("not found")):
            response = client.post("/api/v1/series/NOPE/sync")
        assert response.status_code == 404

    def test_fred_timeout_returns_504(self, client, fred_configured):
        with patch.object(FREDClient, "get_series_info", side_effect=FREDTimeoutError("timed out")):
            response = client.post("/api/v1/series/UNRATE/sync")
        assert response.status_code == 504

    def test_fred_upstream_error_returns_502(self, client, fred_configured):
        with patch.object(FREDClient, "get_series_info", side_effect=FREDUpstreamError("boom")):
            response = client.post("/api/v1/series/UNRATE/sync")
        assert response.status_code == 502

    def test_integrity_conflict_returns_409(self, client, fred_configured):
        from sqlalchemy.exc import IntegrityError

        from app.services.economic_data import EconomicDataService

        with patch.object(FREDClient, "get_series_info", return_value={"id": "UNRATE", "title": "t", "units": "u"}), \
             patch.object(FREDClient, "get_observations", return_value=[]), \
             patch.object(EconomicDataService, "sync_series", side_effect=IntegrityError("stmt", {}, Exception("conflict"))):
            response = client.post("/api/v1/series/UNRATE/sync")
        assert response.status_code == 409

    def test_database_unavailable_returns_503(self, client, fred_configured):
        from sqlalchemy.exc import OperationalError

        from app.services.economic_data import EconomicDataService

        with patch.object(FREDClient, "get_series_info", return_value={"id": "UNRATE", "title": "t", "units": "u"}), \
             patch.object(FREDClient, "get_observations", return_value=[]), \
             patch.object(EconomicDataService, "sync_series", side_effect=OperationalError("stmt", {}, Exception("connection refused"))):
            response = client.post("/api/v1/series/UNRATE/sync")
        assert response.status_code == 503
        assert "connection refused" not in response.text

    def test_generic_database_error_returns_500(self, client, fred_configured):
        from sqlalchemy.exc import SQLAlchemyError

        from app.services.economic_data import EconomicDataService

        with patch.object(FREDClient, "get_series_info", return_value={"id": "UNRATE", "title": "t", "units": "u"}), \
             patch.object(FREDClient, "get_observations", return_value=[]), \
             patch.object(EconomicDataService, "sync_series", side_effect=SQLAlchemyError("unexpected synthetic failure")):
            response = client.post("/api/v1/series/UNRATE/sync")
        assert response.status_code == 500
