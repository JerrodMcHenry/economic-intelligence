"""GET /api/v1/monitors/labor -- PostgreSQL-only, real isolated test
database, no FRED, no OpenAI. One narrow, read-only endpoint; these
tests cover its exact response contract, missing/partial economic
data (still a 200), DB infrastructure failure (503/500), determinism,
non-mutation, and independence from OpenAI/FRED.
"""

from datetime import date
from unittest.mock import patch

from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.clients.fred import FREDClient
from app.domain.labor import month_before
from app.models.labor import PAYEMS_SERIES_ID, UNRATE_SERIES_ID
from app.models.series import Observation, SeriesResponse
from app.repositories.series_repository import SeriesRepository
from app.services.labor import LaborMonitorService

ANCHOR = date(2025, 8, 1)


def _payems_history(anchor: date, count: int = 20) -> list[Observation]:
    return [Observation(date=month_before(anchor, n), value=150_000.0 - n * 0.3 - (n * n) * 0.01) for n in range(count)]


def _unrate_history(anchor: date, count: int = 20) -> list[Observation]:
    return [Observation(date=month_before(anchor, n), value=4.0 + n * 0.02) for n in range(count)]


def _seed(seed_session, series_id: str, observations: list[Observation]) -> None:
    units = "Thousands of Persons" if series_id == PAYEMS_SERIES_ID else "Percent"
    SeriesRepository(seed_session).save_series(SeriesResponse(series_id=series_id, title=series_id, units=units, observations=observations))
    seed_session.commit()


class TestSuccessAndContract:
    def test_success_with_full_data(self, client, seed_session):
        _seed(seed_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        _seed(seed_session, UNRATE_SERIES_ID, _unrate_history(ANCHOR))

        response = client.get("/api/v1/monitors/labor")
        assert response.status_code == 200
        body = response.json()

        assert body["methodology_id"] == "labor_v1.0"
        assert body["data_basis"] == "latest_revised_data"
        assert body["evaluation_period"] == ANCHOR.isoformat()

    def test_exact_response_contract_top_level_keys(self, client, seed_session):
        _seed(seed_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        _seed(seed_session, UNRATE_SERIES_ID, _unrate_history(ANCHOR))
        response = client.get("/api/v1/monitors/labor")
        body = response.json()
        assert set(body.keys()) == {"methodology_id", "data_basis", "state", "evaluation_period", "employment", "unemployment"}

    def test_employment_contract_fields(self, client, seed_session):
        _seed(seed_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        _seed(seed_session, UNRATE_SERIES_ID, _unrate_history(ANCHOR))
        response = client.get("/api/v1/monitors/labor")
        employment = response.json()["employment"]
        assert employment["series_id"] == "CES0000000001"  # #56B: the BLS series, not the storage key
        assert set(employment.keys()) == {
            "series_id", "current_3m_avg_jobs", "prior_3m_avg_jobs", "momentum_delta_jobs",
            "condition_deadband_jobs", "momentum_deadband_jobs", "condition", "momentum", "state", "observations",
        }
        assert employment["condition_deadband_jobs"] == 50_000
        assert employment["momentum_deadband_jobs"] == 50_000
        assert len(employment["observations"]) == 7

    def test_unemployment_contract_fields(self, client, seed_session):
        _seed(seed_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        _seed(seed_session, UNRATE_SERIES_ID, _unrate_history(ANCHOR))
        response = client.get("/api/v1/monitors/labor")
        unemployment = response.json()["unemployment"]
        assert unemployment["series_id"] == "LNS14000000"  # #56B: the BLS series, not the storage key
        assert set(unemployment.keys()) == {
            "series_id", "current_3m_avg", "prior_year_3m_avg", "delta_pp",
            "unemployment_deadband_pp", "state", "observations",
        }
        assert unemployment["unemployment_deadband_pp"] == 0.2
        assert len(unemployment["observations"]) == 6

    def test_no_jolts_or_civpart_field_anywhere_in_the_response(self, client, seed_session):
        _seed(seed_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        _seed(seed_session, UNRATE_SERIES_ID, _unrate_history(ANCHOR))
        response = client.get("/api/v1/monitors/labor")
        body_text = response.text
        for forbidden in ("jolts", "civpart", "JOLTS", "CIVPART"):
            assert forbidden not in body_text


class TestMissingData:
    def test_nothing_persisted_returns_200_with_insufficient_data(self, client, seed_session):
        response = client.get("/api/v1/monitors/labor")
        assert response.status_code == 200
        body = response.json()
        assert body["state"] == "INSUFFICIENT_DATA"
        assert body["evaluation_period"] is None
        assert body["employment"]["observations"] == []
        assert body["unemployment"]["observations"] == []

    def test_only_payems_persisted_returns_200_with_insufficient_data(self, client, seed_session):
        _seed(seed_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        response = client.get("/api/v1/monitors/labor")
        assert response.status_code == 200
        assert response.json()["state"] == "INSUFFICIENT_DATA"


class TestInfrastructureFailures:
    def test_operational_error_returns_503_not_insufficient_data(self, client, seed_session):
        _seed(seed_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        with patch.object(LaborMonitorService, "get_result", side_effect=OperationalError("s", {}, Exception("down"))):
            response = client.get("/api/v1/monitors/labor")
        assert response.status_code == 503
        assert "down" not in response.text

    def test_generic_sqlalchemy_error_returns_500(self, client, seed_session):
        _seed(seed_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        with patch.object(LaborMonitorService, "get_result", side_effect=SQLAlchemyError("synthetic failure")):
            response = client.get("/api/v1/monitors/labor")
        assert response.status_code == 500

    def test_no_stack_trace_or_internal_detail_in_500_response(self, client, seed_session):
        with patch.object(
            LaborMonitorService, "get_result",
            side_effect=SQLAlchemyError("SELECT * FROM secret_table; password=hunter2 host=db.internal"),
        ):
            response = client.get("/api/v1/monitors/labor")
        body_text = response.text.lower()
        for forbidden in ("traceback", "site-packages", "/users/", "hunter2", "secret_table", "password="):
            assert forbidden not in body_text

    def test_database_not_configured_returns_503(self, client, monkeypatch, test_database_url):
        from app.core.config import settings

        monkeypatch.setattr(settings, "database_url", None)
        response = client.get("/api/v1/monitors/labor")
        assert response.status_code == 503


class TestDeterminismAndNonMutation:
    def test_repeated_requests_return_identical_body(self, client, seed_session):
        _seed(seed_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        _seed(seed_session, UNRATE_SERIES_ID, _unrate_history(ANCHOR))
        r1 = client.get("/api/v1/monitors/labor")
        r2 = client.get("/api/v1/monitors/labor")
        assert r1.json() == r2.json()

    def test_request_does_not_mutate_persisted_observations(self, client, seed_session):
        _seed(seed_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        _seed(seed_session, UNRATE_SERIES_ID, _unrate_history(ANCHOR))
        before = client.get(f"/api/v1/series/{PAYEMS_SERIES_ID}/observations").json()

        client.get("/api/v1/monitors/labor")
        client.get("/api/v1/monitors/labor")

        after = client.get(f"/api/v1/series/{PAYEMS_SERIES_ID}/observations").json()
        assert before == after


class TestAIAndFredIndependence:
    def test_works_without_openai_key(self, client, seed_session, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "openai_api_key", None)
        _seed(seed_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        _seed(seed_session, UNRATE_SERIES_ID, _unrate_history(ANCHOR))
        response = client.get("/api/v1/monitors/labor")
        assert response.status_code == 200

    def test_never_constructs_a_fred_client(self, client, seed_session):
        """A fail-fast fake FRED boundary: if the monitor path ever
        tried to construct a FREDClient, this raises immediately and
        the request would come back as a 500 -- the 200 assertion
        below would otherwise be unreachable."""
        _seed(seed_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        _seed(seed_session, UNRATE_SERIES_ID, _unrate_history(ANCHOR))
        with patch.object(FREDClient, "__init__", side_effect=AssertionError("FREDClient must never be constructed here")):
            response = client.get("/api/v1/monitors/labor")
        assert response.status_code == 200

    def test_no_synchronization_or_ingestion_side_effect(self, client, seed_session):
        """No series row is created as a side effect of calling the
        monitor endpoint for a series that isn't persisted."""
        response = client.get("/api/v1/monitors/labor")
        assert response.status_code == 200
        lookup = client.get(f"/api/v1/series/{PAYEMS_SERIES_ID}/observations")
        assert lookup.status_code == 404


class TestNoMutationEndpoint:
    def test_no_post_route_exists_for_labor(self, client, seed_session):
        response = client.post("/api/v1/monitors/labor")
        assert response.status_code in (404, 405)
