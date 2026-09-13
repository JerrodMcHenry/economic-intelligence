"""GET /api/v1/monitors/inflation -- PostgreSQL-only, real isolated
test database, no FRED, no OpenAI. One narrow, read-only endpoint;
these tests cover its exact response contract, missing/partial
economic data (still a 200), DB infrastructure failure (503/500),
determinism, non-mutation, and independence from OpenAI/FRED.
"""

from datetime import date
from unittest.mock import patch

from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.clients.fred import FREDClient
from app.models.inflation import CONFIRMATION_SERIES_ID, HEADLINE_CPI_SERIES_ID, PRIMARY_SERIES_ID, TARGET_SERIES_ID
from app.models.series import Observation, SeriesResponse
from app.repositories.series_repository import SeriesRepository
from app.services.inflation import InflationMonitorService

FULL_HISTORY = [
    Observation(date=date(2024, 1, 1), value=100.0),
    Observation(date=date(2024, 7, 1), value=103.0),
    Observation(date=date(2024, 10, 1), value=106.0),
    Observation(date=date(2025, 1, 1), value=110.0),
]


def _seed(seed_session, series_id: str, observations: list[Observation]) -> None:
    SeriesRepository(seed_session).save_series(
        SeriesResponse(series_id=series_id, title=series_id, units="Index", observations=observations)
    )
    seed_session.commit()


class TestSuccessAndContract:
    def test_success_with_full_data(self, client, seed_session):
        _seed(seed_session, PRIMARY_SERIES_ID, FULL_HISTORY)
        _seed(seed_session, CONFIRMATION_SERIES_ID, FULL_HISTORY)
        _seed(seed_session, TARGET_SERIES_ID, FULL_HISTORY)
        _seed(seed_session, HEADLINE_CPI_SERIES_ID, FULL_HISTORY)

        response = client.get("/api/v1/monitors/inflation")
        assert response.status_code == 200
        body = response.json()

        assert body["methodology_id"] == "inflation_v1.0"
        assert body["data_basis"] == "latest_revised_data"

    def test_exact_response_contract_top_level_keys(self, client, seed_session):
        _seed(seed_session, PRIMARY_SERIES_ID, FULL_HISTORY)
        response = client.get("/api/v1/monitors/inflation")
        body = response.json()
        assert set(body.keys()) == {
            "methodology_id",
            "data_basis",
            "target",
            "underlying_momentum",
            "confirmation",
            "headline_context",
            "periods",
            "coverage",
        }

    def test_underlying_momentum_contract(self, client, seed_session):
        _seed(seed_session, PRIMARY_SERIES_ID, FULL_HISTORY)
        body = client.get("/api/v1/monitors/inflation").json()
        um = body["underlying_momentum"]
        assert um["series_id"] == PRIMARY_SERIES_ID
        assert um["calculation_period"] == "2025-01-01"
        assert um["state"] in ("COOLING", "HEATING", "STABLE", "MIXED", "INSUFFICIENT_DATA")
        assert um["neutral_band_pp"] == 0.10
        assert "r_3m_annualized" in um and "r_6m_annualized" in um and "r_12m" in um
        assert "evidence_3m" in um and um["evidence_3m"]["transformation"] == "3m_annualized"

    def test_confirmation_contract_fields_present(self, client, seed_session):
        _seed(seed_session, PRIMARY_SERIES_ID, FULL_HISTORY)
        _seed(seed_session, CONFIRMATION_SERIES_ID, FULL_HISTORY)
        body = client.get("/api/v1/monitors/inflation").json()
        confirmation = body["confirmation"]
        assert set(confirmation.keys()) == {
            "confirmation_latest",
            "primary_at_comparison_period",
            "confirmation_at_comparison_period",
            "latest_common_period",
            "relationship",
        }
        assert confirmation["relationship"] in ("CONFIRMS", "DIVERGES", "INCONCLUSIVE", "UNAVAILABLE")

    def test_coverage_contract(self, client, seed_session):
        _seed(seed_session, PRIMARY_SERIES_ID, FULL_HISTORY)
        body = client.get("/api/v1/monitors/inflation").json()
        assert set(body["coverage"].keys()) == {
            "primary_available",
            "confirmation_available",
            "target_available",
            "headline_cpi_available",
        }

    def test_no_target_categorical_state_field_exists(self, client, seed_session):
        _seed(seed_session, TARGET_SERIES_ID, FULL_HISTORY)
        body = client.get("/api/v1/monitors/inflation").json()
        assert set(body["target"].keys()) == {
            "series_id",
            "calculation_period",
            "headline_pce_yoy",
            "fed_objective_percent",
            "target_gap_pp",
            "available",
            "evidence",
        }

    def test_no_aggregate_headline_state_field_exists(self, client, seed_session):
        body = client.get("/api/v1/monitors/inflation").json()
        assert set(body["headline_context"].keys()) == {"headline_pce", "headline_cpi"}


class TestPartialOrMissingEconomicData:
    def test_nothing_persisted_returns_200_with_insufficient_data(self, client, seed_session):
        response = client.get("/api/v1/monitors/inflation")
        assert response.status_code == 200
        body = response.json()
        assert body["underlying_momentum"]["state"] == "INSUFFICIENT_DATA"
        assert body["target"]["available"] is False
        assert body["coverage"] == {
            "primary_available": False,
            "confirmation_available": False,
            "target_available": False,
            "headline_cpi_available": False,
        }

    def test_only_primary_persisted_returns_200_with_partial_coverage(self, client, seed_session):
        _seed(seed_session, PRIMARY_SERIES_ID, FULL_HISTORY)
        response = client.get("/api/v1/monitors/inflation")
        assert response.status_code == 200
        body = response.json()
        assert body["coverage"]["primary_available"] is True
        assert body["coverage"]["confirmation_available"] is False
        assert body["confirmation"]["relationship"] == "UNAVAILABLE"


class TestDatabaseInfrastructureFailure:
    def test_operational_error_returns_503_not_insufficient_data(self, client, seed_session):
        _seed(seed_session, PRIMARY_SERIES_ID, FULL_HISTORY)
        with patch.object(InflationMonitorService, "get_result", side_effect=OperationalError("s", {}, Exception("down"))):
            response = client.get("/api/v1/monitors/inflation")
        assert response.status_code == 503
        assert "down" not in response.text

    def test_generic_sqlalchemy_error_returns_500(self, client, seed_session):
        _seed(seed_session, PRIMARY_SERIES_ID, FULL_HISTORY)
        with patch.object(InflationMonitorService, "get_result", side_effect=SQLAlchemyError("synthetic failure")):
            response = client.get("/api/v1/monitors/inflation")
        assert response.status_code == 500

    def test_no_stack_trace_or_internal_detail_in_500_response(self, client, seed_session):
        with patch.object(
            InflationMonitorService, "get_result",
            side_effect=SQLAlchemyError("SELECT * FROM secret_table; password=hunter2 host=db.internal"),
        ):
            response = client.get("/api/v1/monitors/inflation")
        body_text = response.text.lower()
        for forbidden in ("traceback", "site-packages", "/users/", "hunter2", "secret_table", "password="):
            assert forbidden not in body_text

    def test_database_not_configured_returns_503(self, client, monkeypatch, test_database_url):
        from app.core.config import settings

        monkeypatch.setattr(settings, "database_url", None)
        response = client.get("/api/v1/monitors/inflation")
        assert response.status_code == 503


class TestDeterminismAndNonMutation:
    def test_repeated_requests_return_identical_body(self, client, seed_session):
        _seed(seed_session, PRIMARY_SERIES_ID, FULL_HISTORY)
        _seed(seed_session, CONFIRMATION_SERIES_ID, FULL_HISTORY)
        r1 = client.get("/api/v1/monitors/inflation")
        r2 = client.get("/api/v1/monitors/inflation")
        assert r1.json() == r2.json()

    def test_request_does_not_mutate_persisted_observations(self, client, seed_session):
        _seed(seed_session, PRIMARY_SERIES_ID, FULL_HISTORY)
        before = client.get(f"/api/v1/series/{PRIMARY_SERIES_ID}/observations").json()

        client.get("/api/v1/monitors/inflation")
        client.get("/api/v1/monitors/inflation")

        after = client.get(f"/api/v1/series/{PRIMARY_SERIES_ID}/observations").json()
        assert before == after


class TestAIAndFredIndependence:
    def test_works_without_openai_key(self, client, seed_session, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "openai_api_key", None)
        _seed(seed_session, PRIMARY_SERIES_ID, FULL_HISTORY)
        response = client.get("/api/v1/monitors/inflation")
        assert response.status_code == 200

    def test_never_constructs_a_fred_client(self, client, seed_session):
        """A fail-fast fake FRED boundary: if the monitor path ever
        tried to construct a FREDClient, this raises immediately and
        the request would come back as a 500 -- the 200 assertion below
        would otherwise be unreachable."""
        _seed(seed_session, PRIMARY_SERIES_ID, FULL_HISTORY)
        with patch.object(FREDClient, "__init__", side_effect=AssertionError("FREDClient must never be constructed here")):
            response = client.get("/api/v1/monitors/inflation")
        assert response.status_code == 200

    def test_no_synchronization_or_ingestion_side_effect(self, client, seed_session):
        """No series row is created as a side effect of calling the
        monitor endpoint for a series that isn't persisted."""
        response = client.get("/api/v1/monitors/inflation")
        assert response.status_code == 200
        lookup = client.get(f"/api/v1/series/{PRIMARY_SERIES_ID}/observations")
        assert lookup.status_code == 404
