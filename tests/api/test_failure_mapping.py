"""Cross-cutting HTTP failure-mapping matrix, safe-error-body checks,
and the AI/FRED independence proofs for the deterministic API surface.

Per-route FRED/DB failure mapping specific to one endpoint lives beside
that endpoint's other tests (test_series_api.py); this file covers the
DB-failure mapping for the PostgreSQL-only routes (observations,
transform, compare, pipeline) plus the cross-cutting proofs.
"""

import ast
from pathlib import Path
from unittest.mock import patch

from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError

from app.clients.fred import FREDClient
from app.models.series import Observation, SeriesResponse
from app.repositories.series_repository import SeriesRepository

APP_DIR = Path(__file__).resolve().parents[2] / "app"


def _seed(seed_session, series_id, observations):
    SeriesRepository(seed_session).save_series(
        SeriesResponse(series_id=series_id, title=series_id, units="Index", observations=observations)
    )
    seed_session.commit()


class TestDatabaseFailureMappingAcrossPersistedRoutes:
    """OperationalError -> 503, generic SQLAlchemyError -> 500, forced
    at the service boundary (never by breaking the real Postgres
    server)."""

    def test_observations_operational_error_returns_503(self, client, seed_session):
        from app.services.economic_data import EconomicDataService

        _seed(seed_session, "A", [Observation(date="2024-01-01", value=1.0)])
        with patch.object(EconomicDataService, "get_observations", side_effect=OperationalError("s", {}, Exception("down"))):
            response = client.get("/api/v1/series/A/observations")
        assert response.status_code == 503
        assert "down" not in response.text

    def test_observations_generic_sqlalchemy_error_returns_500(self, client, seed_session):
        from app.services.economic_data import EconomicDataService

        _seed(seed_session, "A", [Observation(date="2024-01-01", value=1.0)])
        with patch.object(EconomicDataService, "get_observations", side_effect=SQLAlchemyError("synthetic")):
            response = client.get("/api/v1/series/A/observations")
        assert response.status_code == 500

    def test_transform_operational_error_returns_503(self, client, seed_session):
        from app.services.economic_data import EconomicDataService

        _seed(seed_session, "A", [Observation(date="2024-01-01", value=1.0)])
        with patch.object(EconomicDataService, "get_transformed_observations", side_effect=OperationalError("s", {}, Exception("down"))):
            response = client.get("/api/v1/series/A/transform", params={"transformation": "percent_change"})
        assert response.status_code == 503

    def test_transform_generic_sqlalchemy_error_returns_500(self, client, seed_session):
        from app.services.economic_data import EconomicDataService

        _seed(seed_session, "A", [Observation(date="2024-01-01", value=1.0)])
        with patch.object(EconomicDataService, "get_transformed_observations", side_effect=SQLAlchemyError("synthetic")):
            response = client.get("/api/v1/series/A/transform", params={"transformation": "percent_change"})
        assert response.status_code == 500

    def test_compare_operational_error_returns_503(self, client, seed_session):
        from app.services.analysis import AnalysisService

        _seed(seed_session, "A", [Observation(date="2024-01-01", value=1.0)])
        _seed(seed_session, "B", [Observation(date="2024-01-01", value=1.0)])
        with patch.object(AnalysisService, "compare", side_effect=OperationalError("s", {}, Exception("down"))):
            response = client.get("/api/v1/analysis/compare", params={"series_a": "A", "series_b": "B", "analysis": "aligned"})
        assert response.status_code == 503

    def test_compare_generic_sqlalchemy_error_returns_500(self, client, seed_session):
        from app.services.analysis import AnalysisService

        _seed(seed_session, "A", [Observation(date="2024-01-01", value=1.0)])
        _seed(seed_session, "B", [Observation(date="2024-01-01", value=1.0)])
        with patch.object(AnalysisService, "compare", side_effect=SQLAlchemyError("synthetic")):
            response = client.get("/api/v1/analysis/compare", params={"series_a": "A", "series_b": "B", "analysis": "aligned"})
        assert response.status_code == 500

    def test_pipeline_operational_error_returns_503(self, client, seed_session):
        from app.services.analysis import AnalysisService

        _seed(seed_session, "A", [Observation(date="2024-01-01", value=1.0)])
        _seed(seed_session, "B", [Observation(date="2024-01-01", value=1.0)])
        body = {"series_a": {"series_id": "A"}, "series_b": {"series_id": "B"}, "analysis": "aligned"}
        with patch.object(AnalysisService, "pipeline", side_effect=OperationalError("s", {}, Exception("down"))):
            response = client.post("/api/v1/analysis/pipeline", json=body)
        assert response.status_code == 503

    def test_pipeline_generic_sqlalchemy_error_returns_500(self, client, seed_session):
        from app.services.analysis import AnalysisService

        _seed(seed_session, "A", [Observation(date="2024-01-01", value=1.0)])
        _seed(seed_session, "B", [Observation(date="2024-01-01", value=1.0)])
        body = {"series_a": {"series_id": "A"}, "series_b": {"series_id": "B"}, "analysis": "aligned"}
        with patch.object(AnalysisService, "pipeline", side_effect=SQLAlchemyError("synthetic")):
            response = client.post("/api/v1/analysis/pipeline", json=body)
        assert response.status_code == 500


class TestSafeErrorBodies:
    def test_operational_error_never_leaks_synthetic_marker_text(self, client, seed_session):
        from app.services.economic_data import EconomicDataService

        _seed(seed_session, "A", [Observation(date="2024-01-01", value=1.0)])
        with patch.object(
            EconomicDataService, "get_observations",
            side_effect=OperationalError("SELECT * FROM secret_table", {}, Exception("password=hunter2 host=db.internal")),
        ):
            response = client.get("/api/v1/series/A/observations")
        body_text = response.text
        for forbidden in ("hunter2", "secret_table", "db.internal", "password="):
            assert forbidden not in body_text

    def test_no_stack_trace_in_any_500_response(self, client, seed_session):
        from app.services.economic_data import EconomicDataService

        _seed(seed_session, "A", [Observation(date="2024-01-01", value=1.0)])
        with patch.object(EconomicDataService, "get_observations", side_effect=SQLAlchemyError("synthetic failure")):
            response = client.get("/api/v1/series/A/observations")
        body_text = response.text.lower()
        for forbidden in ("traceback", "site-packages", "/users/", "raise ", ".py\""):
            assert forbidden not in body_text


class TestAIIndependence:
    def test_health_works_without_openai_key(self, client, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "openai_api_key", None)
        assert client.get("/health").status_code == 200

    def test_observations_work_without_openai_key(self, client, seed_session, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "openai_api_key", None)
        _seed(seed_session, "A", [Observation(date="2024-01-01", value=1.0)])
        assert client.get("/api/v1/series/A/observations").status_code == 200

    def test_transform_works_without_openai_key(self, client, seed_session, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "openai_api_key", None)
        _seed(seed_session, "A", [Observation(date="2024-01-01", value=1.0), Observation(date="2024-02-01", value=2.0)])
        assert client.get("/api/v1/series/A/transform", params={"transformation": "percent_change"}).status_code == 200

    def test_compare_works_without_openai_key(self, client, seed_session, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "openai_api_key", None)
        _seed(seed_session, "A", [Observation(date="2024-01-01", value=1.0)])
        _seed(seed_session, "B", [Observation(date="2024-01-01", value=2.0)])
        response = client.get("/api/v1/analysis/compare", params={"series_a": "A", "series_b": "B", "analysis": "aligned"})
        assert response.status_code == 200

    def test_pipeline_works_without_openai_key(self, client, seed_session, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "openai_api_key", None)
        _seed(seed_session, "A", [Observation(date="2024-01-01", value=1.0)])
        _seed(seed_session, "B", [Observation(date="2024-01-01", value=2.0)])
        body = {"series_a": {"series_id": "A"}, "series_b": {"series_id": "B"}, "analysis": "aligned"}
        assert client.post("/api/v1/analysis/pipeline", json=body).status_code == 200

    def test_ai_query_returns_clean_503_without_openai_key(self, client, monkeypatch):
        """The one, narrow, non-behavioral AI-route test this increment
        permits: configuration-unavailable -> 503, nothing more. No live
        OpenAI call, no round behavior, no tool-schema testing."""
        from app.core.config import settings

        monkeypatch.setattr(settings, "openai_api_key", None)
        monkeypatch.setattr(settings, "openai_model", None)
        response = client.post("/api/v1/ai/query", json={"message": "anything"})
        assert response.status_code == 503

    def test_no_deterministic_route_file_imports_aiservice(self):
        """Static guard: app/api/series.py and app/api/analysis.py never
        import AIService/app.services.ai(_tools) -- app/api/ai.py is
        exempt (it IS the AI route)."""
        for route_file in ("api/series.py", "api/analysis.py"):
            path = APP_DIR / route_file
            tree = ast.parse(path.read_text(), filename=str(path))
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module)
                elif isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
            forbidden = {m for m in imported if m.startswith("app.services.ai") or m == "openai"}
            assert forbidden == set(), f"{route_file} imports {forbidden}"


class TestFredIndependenceOfPersistedAnalytics:
    def test_observations_transform_compare_pipeline_never_construct_fred_client(self, client, seed_session):
        """A fail-fast fake FRED boundary: if ANY of these four routes'
        code path ever tried to construct a FREDClient, this raises
        immediately and the request would come back as a 500 -- none
        of these assertions on 200 would otherwise be reachable."""
        _seed(seed_session, "A", [Observation(date="2024-01-01", value=1.0), Observation(date="2024-02-01", value=2.0)])
        _seed(seed_session, "B", [Observation(date="2024-01-01", value=10.0), Observation(date="2024-02-01", value=20.0)])

        with patch.object(FREDClient, "__init__", side_effect=AssertionError("FREDClient must never be constructed here")):
            assert client.get("/api/v1/series/A/observations").status_code == 200
            assert client.get("/api/v1/series/A/transform", params={"transformation": "percent_change"}).status_code == 200
            assert client.get("/api/v1/analysis/compare", params={"series_a": "A", "series_b": "B", "analysis": "aligned"}).status_code == 200
            body = {"series_a": {"series_id": "A"}, "series_b": {"series_id": "B"}, "analysis": "aligned"}
            assert client.post("/api/v1/analysis/pipeline", json=body).status_code == 200
