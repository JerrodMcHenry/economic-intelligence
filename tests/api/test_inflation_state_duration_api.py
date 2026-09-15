"""GET /api/v1/monitors/inflation/state-duration -- PostgreSQL-only,
real isolated test database, no FRED, no OpenAI. State Duration V1
(`docs/product/state-duration-v1.md`): one narrow, read-only endpoint.
Economic-content boundary-type coverage (EXACT/DATA_BOUNDED/
LOOKBACK_BOUNDED math) is exhaustively covered at the service layer
(tests/integration/test_inflation_state_duration_service.py) and the
pure helper layer (tests/test_domain_state_duration.py); this file
covers the HTTP contract itself -- exact response shape, infrastructure
failure mapping, determinism, non-mutation, and FRED/AI independence.
"""

from datetime import date
from unittest.mock import patch

from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.clients.fred import FREDClient
from app.domain.inflation import month_before
from app.models.inflation import PRIMARY_SERIES_ID
from app.models.series import Observation, SeriesResponse
from app.repositories.series_repository import SeriesRepository
from app.services.inflation import InflationMonitorService

T = date(2026, 1, 1)


def _flat_history(anchor: date, months: int, value: float = 100.0, skip: set[date] | None = None) -> list[Observation]:
    skip = skip or set()
    return [Observation(date=month_before(anchor, n), value=value) for n in range(months) if month_before(anchor, n) not in skip]


def _seed(seed_session, series_id: str, observations: list[Observation]) -> None:
    SeriesRepository(seed_session).save_series(SeriesResponse(series_id=series_id, title=series_id, units="Index", observations=observations))
    seed_session.commit()


class TestSuccessAndContract:
    def test_exact_boundary_response_contract(self, client, seed_session):
        points = _flat_history(month_before(T, 1), 30)
        points.append(Observation(date=T, value=130.0))
        _seed(seed_session, PRIMARY_SERIES_ID, points)

        response = client.get("/api/v1/monitors/inflation/state-duration")
        assert response.status_code == 200
        body = response.json()

        assert body == {
            "status": "AVAILABLE",
            "state": "HEATING",
            "evaluation_period": T.isoformat(),
            "duration_months": 1,
            "earliest_confirmed_period": T.isoformat(),
            "boundary_type": "EXACT",
            "previous_state": "STABLE",
            "previous_period": month_before(T, 1).isoformat(),
            "methodology_id": "inflation_v1.0",
            "data_basis": "latest_revised_data",
            "history_type": "latest_revised_reconstruction",
        }

    def test_data_bounded_response(self, client, seed_session):
        missing = date(2024, 5, 1)
        _seed(seed_session, PRIMARY_SERIES_ID, _flat_history(T, 85, skip={missing}))
        response = client.get("/api/v1/monitors/inflation/state-duration")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "AVAILABLE"
        assert body["boundary_type"] == "DATA_BOUNDED"
        assert body["duration_months"] == 8
        assert body["previous_state"] is None
        assert body["previous_period"] is None

    def test_lookback_bounded_response(self, client, seed_session):
        _seed(seed_session, PRIMARY_SERIES_ID, _flat_history(T, 80))
        response = client.get("/api/v1/monitors/inflation/state-duration")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "AVAILABLE"
        assert body["boundary_type"] == "LOOKBACK_BOUNDED"
        assert body["duration_months"] == 60

    def test_current_insufficient_response(self, client, seed_session):
        response = client.get("/api/v1/monitors/inflation/state-duration")
        assert response.status_code == 200
        body = response.json()
        assert body == {
            "status": "CURRENT_INSUFFICIENT",
            "methodology_id": "inflation_v1.0",
            "data_basis": "latest_revised_data",
        }


class TestInfrastructureFailures:
    def test_operational_error_returns_503_not_a_fabricated_economic_response(self, client, seed_session):
        _seed(seed_session, PRIMARY_SERIES_ID, _flat_history(T, 30))
        with patch.object(InflationMonitorService, "get_state_duration_result", side_effect=OperationalError("s", {}, Exception("down"))):
            response = client.get("/api/v1/monitors/inflation/state-duration")
        assert response.status_code == 503
        assert "down" not in response.text

    def test_generic_sqlalchemy_error_returns_500(self, client, seed_session):
        _seed(seed_session, PRIMARY_SERIES_ID, _flat_history(T, 30))
        with patch.object(InflationMonitorService, "get_state_duration_result", side_effect=SQLAlchemyError("synthetic failure")):
            response = client.get("/api/v1/monitors/inflation/state-duration")
        assert response.status_code == 500

    def test_database_not_configured_returns_503(self, client, monkeypatch, test_database_url):
        from app.core.config import settings

        monkeypatch.setattr(settings, "database_url", None)
        response = client.get("/api/v1/monitors/inflation/state-duration")
        assert response.status_code == 503


class TestNoMutationAndNoSideEffect:
    def test_no_row_created_for_a_series_that_is_not_persisted(self, client, seed_session):
        response = client.get("/api/v1/monitors/inflation/state-duration")
        assert response.status_code == 200
        lookup = client.get(f"/api/v1/series/{PRIMARY_SERIES_ID}/observations")
        assert lookup.status_code == 404

    def test_request_does_not_mutate_persisted_observations(self, client, seed_session):
        _seed(seed_session, PRIMARY_SERIES_ID, _flat_history(T, 30))
        before = client.get(f"/api/v1/series/{PRIMARY_SERIES_ID}/observations").json()

        client.get("/api/v1/monitors/inflation/state-duration")
        client.get("/api/v1/monitors/inflation/state-duration")

        after = client.get(f"/api/v1/series/{PRIMARY_SERIES_ID}/observations").json()
        assert before == after


class TestDeterminism:
    def test_repeated_requests_return_identical_body(self, client, seed_session):
        _seed(seed_session, PRIMARY_SERIES_ID, _flat_history(T, 30))
        r1 = client.get("/api/v1/monitors/inflation/state-duration")
        r2 = client.get("/api/v1/monitors/inflation/state-duration")
        assert r1.json() == r2.json()


class TestAIAndFredIndependence:
    def test_works_without_openai_key(self, client, seed_session, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "openai_api_key", None)
        _seed(seed_session, PRIMARY_SERIES_ID, _flat_history(T, 30))
        response = client.get("/api/v1/monitors/inflation/state-duration")
        assert response.status_code == 200

    def test_never_constructs_a_fred_client(self, client, seed_session):
        """A fail-fast fake FRED boundary: if the state-duration path
        ever tried to construct a FREDClient, this raises immediately
        and the request would come back as a 500 -- the 200 assertion
        below would otherwise be unreachable."""
        _seed(seed_session, PRIMARY_SERIES_ID, _flat_history(T, 30))
        with patch.object(FREDClient, "__init__", side_effect=AssertionError("FREDClient must never be constructed here")):
            response = client.get("/api/v1/monitors/inflation/state-duration")
        assert response.status_code == 200

    def test_no_ai_import_anywhere_in_the_route_module(self):
        """Structural guard, mirroring app.api.inflation's own existing
        module docstring claim -- this route module has no dependency
        on app.services.ai/OPENAI_API_KEY at all."""
        import ast
        from pathlib import Path

        tree = ast.parse(Path("app/api/inflation.py").read_text())
        imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        forbidden = {m for m in imported if m == "app.services.ai" or m.startswith("app.services.ai.") or m == "openai"}
        assert forbidden == set()


class TestNoMutationEndpoint:
    def test_no_post_route_exists_for_inflation_state_duration(self, client, seed_session):
        response = client.post("/api/v1/monitors/inflation/state-duration")
        assert response.status_code in (404, 405)


class TestFailureIsolationFromTheOrdinaryMonitorRoute:
    def test_state_duration_failure_does_not_affect_the_ordinary_monitor_route(self, client, seed_session):
        _seed(seed_session, PRIMARY_SERIES_ID, _flat_history(T, 30))
        with patch.object(InflationMonitorService, "get_state_duration_result", side_effect=OperationalError("s", {}, Exception("down"))):
            broken = client.get("/api/v1/monitors/inflation/state-duration")
            still_works = client.get("/api/v1/monitors/inflation")
        assert broken.status_code == 503
        assert still_works.status_code == 200
