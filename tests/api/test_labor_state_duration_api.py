"""GET /api/v1/monitors/labor/state-duration -- PostgreSQL-only, real
isolated test database, no FRED, no OpenAI. State Duration V1
(`docs/product/state-duration-v1.md`): one narrow, read-only endpoint.
Economic-content boundary-type coverage (EXACT/DATA_BOUNDED/
LOOKBACK_BOUNDED math, including the canonical real 2025-10 UNRATE
gap) is exhaustively covered at the service layer
(tests/integration/test_labor_state_duration_service.py) and the pure
helper layer (tests/test_domain_state_duration.py); this file covers
the HTTP contract itself -- exact response shape, infrastructure
failure mapping, determinism, non-mutation, and FRED/AI independence.
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

T = date(2026, 1, 1)


def _flat_payems(anchor: date, months: int, value: float = 150_000.0) -> list[Observation]:
    return [Observation(date=month_before(anchor, n), value=value) for n in range(months)]


def _flat_unrate(anchor: date, months: int, value: float = 4.0) -> list[Observation]:
    return [Observation(date=month_before(anchor, n), value=value) for n in range(months)]


def _seed(seed_session, series_id: str, observations: list[Observation]) -> None:
    units = "Thousands of Persons" if series_id == PAYEMS_SERIES_ID else "Percent"
    SeriesRepository(seed_session).save_series(SeriesResponse(series_id=series_id, title=series_id, units=units, observations=observations))
    seed_session.commit()


class TestSuccessAndContract:
    def test_exact_boundary_response_contract(self, client, seed_session):
        payems = _flat_payems(month_before(T, 1), 25)
        payems.append(Observation(date=T, value=150_000.0 + 600.0))
        _seed(seed_session, PAYEMS_SERIES_ID, payems)
        _seed(seed_session, UNRATE_SERIES_ID, _flat_unrate(T, 25))

        response = client.get("/api/v1/monitors/labor/state-duration")
        assert response.status_code == 200
        body = response.json()

        assert body == {
            "status": "AVAILABLE",
            "state": "MIXED",
            "evaluation_period": T.isoformat(),
            "duration_months": 1,
            "earliest_confirmed_period": T.isoformat(),
            "boundary_type": "EXACT",
            "previous_state": "STABLE",
            "previous_period": month_before(T, 1).isoformat(),
            "methodology_id": "labor_v1.0",
            "data_basis": "latest_revised_data",
            "history_type": "latest_revised_reconstruction",
        }

    def test_lookback_bounded_response(self, client, seed_session):
        _seed(seed_session, PAYEMS_SERIES_ID, _flat_payems(T, 80))
        _seed(seed_session, UNRATE_SERIES_ID, _flat_unrate(T, 80))
        response = client.get("/api/v1/monitors/labor/state-duration")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "AVAILABLE"
        assert body["boundary_type"] == "LOOKBACK_BOUNDED"
        assert body["duration_months"] == 60

    def test_current_insufficient_response(self, client, seed_session):
        response = client.get("/api/v1/monitors/labor/state-duration")
        assert response.status_code == 200
        body = response.json()
        assert body == {
            "status": "CURRENT_INSUFFICIENT",
            "methodology_id": "labor_v1.0",
            "data_basis": "latest_revised_data",
        }

    def test_no_jolts_or_civpart_field_anywhere_in_the_response(self, client, seed_session):
        _seed(seed_session, PAYEMS_SERIES_ID, _flat_payems(T, 30))
        _seed(seed_session, UNRATE_SERIES_ID, _flat_unrate(T, 30))
        response = client.get("/api/v1/monitors/labor/state-duration")
        body_text = response.text
        for forbidden in ("jolts", "civpart", "JOLTS", "CIVPART"):
            assert forbidden not in body_text


class TestInfrastructureFailures:
    def test_operational_error_returns_503_not_a_fabricated_economic_response(self, client, seed_session):
        _seed(seed_session, PAYEMS_SERIES_ID, _flat_payems(T, 30))
        with patch.object(LaborMonitorService, "get_state_duration_result", side_effect=OperationalError("s", {}, Exception("down"))):
            response = client.get("/api/v1/monitors/labor/state-duration")
        assert response.status_code == 503
        assert "down" not in response.text

    def test_generic_sqlalchemy_error_returns_500(self, client, seed_session):
        _seed(seed_session, PAYEMS_SERIES_ID, _flat_payems(T, 30))
        with patch.object(LaborMonitorService, "get_state_duration_result", side_effect=SQLAlchemyError("synthetic failure")):
            response = client.get("/api/v1/monitors/labor/state-duration")
        assert response.status_code == 500

    def test_database_not_configured_returns_503(self, client, monkeypatch, test_database_url):
        from app.core.config import settings

        monkeypatch.setattr(settings, "database_url", None)
        response = client.get("/api/v1/monitors/labor/state-duration")
        assert response.status_code == 503


class TestNoMutationAndNoSideEffect:
    def test_no_row_created_for_a_series_that_is_not_persisted(self, client, seed_session):
        response = client.get("/api/v1/monitors/labor/state-duration")
        assert response.status_code == 200
        lookup = client.get(f"/api/v1/series/{PAYEMS_SERIES_ID}/observations")
        assert lookup.status_code == 404

    def test_request_does_not_mutate_persisted_observations(self, client, seed_session):
        _seed(seed_session, PAYEMS_SERIES_ID, _flat_payems(T, 30))
        _seed(seed_session, UNRATE_SERIES_ID, _flat_unrate(T, 30))
        before = client.get(f"/api/v1/series/{PAYEMS_SERIES_ID}/observations").json()

        client.get("/api/v1/monitors/labor/state-duration")
        client.get("/api/v1/monitors/labor/state-duration")

        after = client.get(f"/api/v1/series/{PAYEMS_SERIES_ID}/observations").json()
        assert before == after


class TestDeterminism:
    def test_repeated_requests_return_identical_body(self, client, seed_session):
        _seed(seed_session, PAYEMS_SERIES_ID, _flat_payems(T, 30))
        _seed(seed_session, UNRATE_SERIES_ID, _flat_unrate(T, 30))
        r1 = client.get("/api/v1/monitors/labor/state-duration")
        r2 = client.get("/api/v1/monitors/labor/state-duration")
        assert r1.json() == r2.json()


class TestAIAndFredIndependence:
    def test_works_without_openai_key(self, client, seed_session, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "openai_api_key", None)
        _seed(seed_session, PAYEMS_SERIES_ID, _flat_payems(T, 30))
        _seed(seed_session, UNRATE_SERIES_ID, _flat_unrate(T, 30))
        response = client.get("/api/v1/monitors/labor/state-duration")
        assert response.status_code == 200

    def test_never_constructs_a_fred_client(self, client, seed_session):
        _seed(seed_session, PAYEMS_SERIES_ID, _flat_payems(T, 30))
        _seed(seed_session, UNRATE_SERIES_ID, _flat_unrate(T, 30))
        with patch.object(FREDClient, "__init__", side_effect=AssertionError("FREDClient must never be constructed here")):
            response = client.get("/api/v1/monitors/labor/state-duration")
        assert response.status_code == 200

    def test_no_ai_import_anywhere_in_the_route_module(self):
        import ast
        from pathlib import Path

        tree = ast.parse(Path("app/api/labor.py").read_text())
        imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        forbidden = {m for m in imported if m == "app.services.ai" or m.startswith("app.services.ai.") or m == "openai"}
        assert forbidden == set()


class TestNoMutationEndpoint:
    def test_no_post_route_exists_for_labor_state_duration(self, client, seed_session):
        response = client.post("/api/v1/monitors/labor/state-duration")
        assert response.status_code in (404, 405)


class TestFailureIsolationFromTheOrdinaryMonitorRoute:
    def test_state_duration_failure_does_not_affect_the_ordinary_monitor_route(self, client, seed_session):
        _seed(seed_session, PAYEMS_SERIES_ID, _flat_payems(T, 30))
        _seed(seed_session, UNRATE_SERIES_ID, _flat_unrate(T, 30))
        with patch.object(LaborMonitorService, "get_state_duration_result", side_effect=OperationalError("s", {}, Exception("down"))):
            broken = client.get("/api/v1/monitors/labor/state-duration")
            still_works = client.get("/api/v1/monitors/labor")
        assert broken.status_code == 503
        assert still_works.status_code == 200


class TestInflationLaborIndependence:
    def test_labor_state_duration_failure_does_not_affect_inflation_state_duration(self, client, seed_session):
        """Mirrors this project's own established failure-isolation
        discipline, restated here for this specific pair of routes
        (frozen contract §48)."""
        from app.models.inflation import PRIMARY_SERIES_ID
        from app.repositories.series_repository import SeriesRepository as Repo
        from app.services.inflation import InflationMonitorService

        _seed(seed_session, PAYEMS_SERIES_ID, _flat_payems(T, 30))
        _seed(seed_session, UNRATE_SERIES_ID, _flat_unrate(T, 30))
        Repo(seed_session).save_series(
            SeriesResponse(
                series_id=PRIMARY_SERIES_ID,
                title=PRIMARY_SERIES_ID,
                units="Index",
                observations=[Observation(date=month_before(T, n), value=100.0) for n in range(30)],
            )
        )
        seed_session.commit()

        with patch.object(LaborMonitorService, "get_state_duration_result", side_effect=OperationalError("s", {}, Exception("down"))):
            labor_broken = client.get("/api/v1/monitors/labor/state-duration")
            inflation_still_works = client.get("/api/v1/monitors/inflation/state-duration")

        assert labor_broken.status_code == 503
        assert inflation_still_works.status_code == 200
