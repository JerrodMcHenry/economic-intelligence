"""GET /api/v1/series/search -- the deterministic discovery endpoint.

FRED is mocked at the narrowest boundary (`FREDClient.search_series`),
never `SeriesDiscoveryService` itself: every test here exercises the
real HTTP route -> real SeriesDiscoveryService -> real SeriesRepository
-> real isolated PostgreSQL test database path, with only the external
FRED catalog call replaced.
"""

import ast
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import text

from app.clients.fred import FREDAuthError, FREDClient, FREDTimeoutError, FREDUpstreamError
from app.models.series import Observation, SeriesResponse
from app.repositories.series_repository import SeriesRepository

APP_DIR = Path(__file__).resolve().parents[2] / "app"


def _seed(seed_session, series_id, title="A Series", units="Percent"):
    SeriesRepository(seed_session).save_series(
        SeriesResponse(series_id=series_id, title=title, units=units, observations=[Observation(date="2024-01-01", value=1.0)])
    )
    seed_session.commit()


def _fred_row(series_id, title="FRED Series", **overrides):
    row = {
        "id": series_id, "title": title, "units": "Percent", "frequency": "Monthly",
        "seasonal_adjustment": "Seasonally Adjusted", "observation_start": "1948-01-01",
        "observation_end": "2024-01-01", "popularity": 50,
    }
    row.update(overrides)
    return row


class TestSuccess:
    def test_local_only_match(self, client, seed_session, fred_configured):
        _seed(seed_session, "UNRATE", "Unemployment Rate")
        with patch.object(FREDClient, "search_series", return_value=[]):
            response = client.get("/api/v1/series/search", params={"q": "UNRATE"})
        assert response.status_code == 200
        body = response.json()
        assert body["query"] == "UNRATE"
        assert [c["series_id"] for c in body["candidates"]] == ["UNRATE"]
        assert body["candidates"][0]["persisted"] is True
        assert body["candidates"][0]["discovery_source"] == "local"
        assert body["external_search_available"] is True

    def test_external_only_match(self, client, seed_session, fred_configured):
        with patch.object(FREDClient, "search_series", return_value=[_fred_row("GDPC1", "Real GDP")]):
            response = client.get("/api/v1/series/search", params={"q": "real gdp"})
        body = response.json()
        assert [c["series_id"] for c in body["candidates"]] == ["GDPC1"]
        assert body["candidates"][0]["persisted"] is False
        assert body["candidates"][0]["discovery_source"] == "fred"

    def test_local_and_external_merge_same_series(self, client, seed_session, fred_configured):
        _seed(seed_session, "UNRATE", "Unemployment Rate")
        with patch.object(FREDClient, "search_series", return_value=[_fred_row("UNRATE", "Unemployment Rate", popularity=96)]):
            response = client.get("/api/v1/series/search", params={"q": "unemployment"})
        body = response.json()
        matching = [c for c in body["candidates"] if c["series_id"] == "UNRATE"]
        assert len(matching) == 1  # deduplicated, not two rows
        assert matching[0]["persisted"] is True  # persisted=True wins
        assert matching[0]["discovery_source"] == "local_and_fred"
        assert matching[0]["frequency"] is not None  # FRED's richer metadata layered on

    def test_deduplication_no_series_returned_twice(self, client, seed_session, fred_configured):
        _seed(seed_session, "UNRATE", "Unemployment Rate")
        with patch.object(FREDClient, "search_series", return_value=[_fred_row("UNRATE"), _fred_row("UNRATENSA")]):
            response = client.get("/api/v1/series/search", params={"q": "unemployment"})
        ids = [c["series_id"] for c in response.json()["candidates"]]
        assert len(ids) == len(set(ids))

    def test_persisted_semantics_local_only(self, client, seed_session, fred_configured):
        _seed(seed_session, "LOCALONLY")
        with patch.object(FREDClient, "search_series", return_value=[]):
            response = client.get("/api/v1/series/search", params={"q": "LOCALONLY"})
        assert response.json()["candidates"][0]["persisted"] is True

    def test_persisted_semantics_external_only(self, client, seed_session, fred_configured):
        with patch.object(FREDClient, "search_series", return_value=[_fred_row("EXTERNALONLY")]):
            response = client.get("/api/v1/series/search", params={"q": "externalonly"})
        assert response.json()["candidates"][0]["persisted"] is False

    def test_persisted_semantics_merged(self, client, seed_session, fred_configured):
        _seed(seed_session, "BOTH")
        with patch.object(FREDClient, "search_series", return_value=[_fred_row("BOTH")]):
            response = client.get("/api/v1/series/search", params={"q": "both"})
        assert response.json()["candidates"][0]["persisted"] is True

    def test_deterministic_order_exact_id_first(self, client, seed_session, fred_configured):
        _seed(seed_session, "AAA")
        with patch.object(FREDClient, "search_series", return_value=[_fred_row("AAAX"), _fred_row("AAA")]):
            response = client.get("/api/v1/series/search", params={"q": "AAA"})
        ids = [c["series_id"] for c in response.json()["candidates"]]
        assert ids[0] == "AAA"  # exact match always first

    def test_default_limit(self, client, seed_session, fred_configured):
        rows = [_fred_row(f"S{i}") for i in range(20)]
        with patch.object(FREDClient, "search_series", return_value=rows):
            response = client.get("/api/v1/series/search", params={"q": "s"})
        assert len(response.json()["candidates"]) <= 10

    def test_custom_limit(self, client, seed_session, fred_configured):
        rows = [_fred_row(f"S{i}") for i in range(20)]
        with patch.object(FREDClient, "search_series", return_value=rows):
            response = client.get("/api/v1/series/search", params={"q": "s", "limit": 3})
        assert len(response.json()["candidates"]) == 3

    def test_limit_applied_after_merge(self, client, seed_session, fred_configured):
        _seed(seed_session, "M1")
        _seed(seed_session, "M2")
        with patch.object(FREDClient, "search_series", return_value=[_fred_row("M1"), _fred_row("M3")]):
            response = client.get("/api/v1/series/search", params={"q": "m", "limit": 2})
        assert len(response.json()["candidates"]) == 2

    def test_empty_result(self, client, seed_session, fred_configured):
        with patch.object(FREDClient, "search_series", return_value=[]):
            response = client.get("/api/v1/series/search", params={"q": "nonexistentconceptxyz"})
        assert response.status_code == 200
        assert response.json()["candidates"] == []
        assert response.json()["external_search_available"] is True

    def test_metadata_normalization_complete(self, client, seed_session, fred_configured):
        with patch.object(FREDClient, "search_series", return_value=[_fred_row("FULL", frequency="Quarterly", popularity=77)]):
            response = client.get("/api/v1/series/search", params={"q": "full"})
        c = response.json()["candidates"][0]
        assert c["frequency"] == "Quarterly"
        assert c["popularity"] == 77
        assert c["observation_start"] == "1948-01-01"

    def test_metadata_normalization_missing_optional_fields(self, client, seed_session, fred_configured):
        with patch.object(FREDClient, "search_series", return_value=[{"id": "SPARSE", "title": "Sparse"}]):
            response = client.get("/api/v1/series/search", params={"q": "sparse"})
        c = response.json()["candidates"][0]
        assert c["frequency"] is None
        assert c["popularity"] is None
        assert c["units"] is None  # never fabricated

    def test_malformed_optional_date_passes_through_unvalidated(self, client, seed_session, fred_configured):
        """observation_start/observation_end are plain `str | None` on
        SeriesCandidate -- no date-shape validation happens at this
        layer (confirmed directly from app/models/discovery.py). A
        malformed value from FRED passes through as-is rather than
        raising; this test documents that current behavior rather than
        assuming validation that doesn't exist."""
        with patch.object(FREDClient, "search_series", return_value=[_fred_row("MALFORMEDDATE", observation_start="not-a-date")]):
            response = client.get("/api/v1/series/search", params={"q": "malformeddate"})
        assert response.status_code == 200
        assert response.json()["candidates"][0]["observation_start"] == "not-a-date"

    def test_repeated_identical_request_is_deterministic(self, client, seed_session, fred_configured):
        _seed(seed_session, "REPEAT")
        with patch.object(FREDClient, "search_series", return_value=[_fred_row("REPEATX")]):
            first = client.get("/api/v1/series/search", params={"q": "repeat"}).json()
            second = client.get("/api/v1/series/search", params={"q": "repeat"}).json()
        assert first == second

    def test_route_collision_search_not_treated_as_series_id(self, client, seed_session, fred_configured):
        """GET /series/search must hit discovery, never get_series("search")
        -- proven by mocking search_series (discovery) and NOT mocking
        get_series_info (single-series metadata): if the route collided,
        the request would attempt a real, unmocked FRED call and fail
        differently (or hang), not return a clean discovery response."""
        with patch.object(FREDClient, "search_series", return_value=[]) as search_mock, \
             patch.object(FREDClient, "get_series_info") as get_info_mock:
            response = client.get("/api/v1/series/search", params={"q": "anything"})
        assert response.status_code == 200
        assert response.json()["query"] == "anything"
        assert search_mock.called
        assert not get_info_mock.called  # proves get_series's code path was never entered

    def test_openai_key_absent_discovery_still_works(self, client, seed_session, fred_configured, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "openai_api_key", None)
        _seed(seed_session, "NOAI")
        with patch.object(FREDClient, "search_series", return_value=[]):
            response = client.get("/api/v1/series/search", params={"q": "NOAI"})
        assert response.status_code == 200

    def test_database_not_mutated_by_search(self, client, seed_session, fred_configured):
        _seed(seed_session, "NOMUTATE")
        before = seed_session.execute(text("SELECT series_id, title FROM economic_series ORDER BY series_id")).fetchall()
        with patch.object(FREDClient, "search_series", return_value=[_fred_row("EXTERNAL_NOT_PERSISTED")]):
            client.get("/api/v1/series/search", params={"q": "nomutate"})
        after = seed_session.execute(text("SELECT series_id, title FROM economic_series ORDER BY series_id")).fetchall()
        assert before == after

    def test_external_only_candidate_not_persisted_by_search(self, client, seed_session, fred_configured):
        with patch.object(FREDClient, "search_series", return_value=[_fred_row("NEVERSYNCED")]):
            response = client.get("/api/v1/series/search", params={"q": "neversynced"})
        assert response.json()["candidates"][0]["persisted"] is False
        row = seed_session.execute(text("SELECT * FROM economic_series WHERE series_id = 'NEVERSYNCED'")).fetchone()
        assert row is None  # searching never syncs


class TestDegradedExternalSearch:
    def test_fred_timeout_with_local_results(self, client, seed_session, fred_configured):
        _seed(seed_session, "STILLWORKS")
        with patch.object(FREDClient, "search_series", side_effect=FREDTimeoutError("timed out")):
            response = client.get("/api/v1/series/search", params={"q": "stillworks"})
        assert response.status_code == 200
        body = response.json()
        assert body["external_search_available"] is False
        assert [c["series_id"] for c in body["candidates"]] == ["STILLWORKS"]

    def test_fred_auth_failure_with_local_results(self, client, seed_session, fred_configured):
        _seed(seed_session, "STILLWORKS2")
        with patch.object(FREDClient, "search_series", side_effect=FREDAuthError("rejected")):
            response = client.get("/api/v1/series/search", params={"q": "stillworks2"})
        body = response.json()
        assert body["external_search_available"] is False
        assert body["candidates"][0]["series_id"] == "STILLWORKS2"

    def test_fred_upstream_failure_with_local_results(self, client, seed_session, fred_configured):
        _seed(seed_session, "STILLWORKS3")
        with patch.object(FREDClient, "search_series", side_effect=FREDUpstreamError("boom")):
            response = client.get("/api/v1/series/search", params={"q": "stillworks3"})
        body = response.json()
        assert body["external_search_available"] is False
        assert body["candidates"][0]["series_id"] == "STILLWORKS3"

    def test_external_failure_with_no_local_results_returns_empty_200(self, client, seed_session, fred_configured):
        """Existing SeriesDiscoveryService contract: no exception, no
        error status -- 200 with empty candidates and
        external_search_available=false. Locked down explicitly."""
        with patch.object(FREDClient, "search_series", side_effect=FREDUpstreamError("boom")):
            response = client.get("/api/v1/series/search", params={"q": "totallyunknownXYZ"})
        assert response.status_code == 200
        body = response.json()
        assert body["candidates"] == []
        assert body["external_search_available"] is False

    def test_no_fred_configured_at_all_degrades_to_local_only(self, client, seed_session, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "fred_api_key", None)
        _seed(seed_session, "LOCALDEGRADE")
        response = client.get("/api/v1/series/search", params={"q": "localdegrade"})
        assert response.status_code == 200
        body = response.json()
        assert body["external_search_available"] is False
        assert body["candidates"][0]["series_id"] == "LOCALDEGRADE"


class TestErrorSafety:
    def test_database_operational_error_returns_503_no_secret_leaked(self, client, seed_session, fred_configured):
        from sqlalchemy.exc import OperationalError

        from app.services.discovery import SeriesDiscoveryService

        with patch.object(SeriesDiscoveryService, "search", side_effect=OperationalError("s", {}, Exception("password=hunter2 host=db.internal"))):
            response = client.get("/api/v1/series/search", params={"q": "x"})
        assert response.status_code == 503
        for forbidden in ("hunter2", "db.internal", "password="):
            assert forbidden not in response.text

    def test_database_generic_error_returns_500_no_stack_trace(self, client, seed_session, fred_configured):
        from sqlalchemy.exc import SQLAlchemyError

        from app.services.discovery import SeriesDiscoveryService

        with patch.object(SeriesDiscoveryService, "search", side_effect=SQLAlchemyError("synthetic")):
            response = client.get("/api/v1/series/search", params={"q": "x"})
        assert response.status_code == 500
        body_text = response.text.lower()
        for forbidden in ("traceback", "site-packages", "raise "):
            assert forbidden not in body_text


class TestValidation:
    def test_missing_q_returns_422(self, client, seed_session):
        response = client.get("/api/v1/series/search")
        assert response.status_code == 422

    def test_empty_q_returns_422(self, client, seed_session):
        response = client.get("/api/v1/series/search", params={"q": ""})
        assert response.status_code == 422

    def test_whitespace_only_q_returns_400(self, client, seed_session):
        """Structurally valid (non-empty string, within length bounds);
        semantically empty once stripped -- application-level 400, not
        FastAPI/Pydantic 422."""
        response = client.get("/api/v1/series/search", params={"q": "   "})
        assert response.status_code == 400

    def test_overlong_q_returns_422(self, client, seed_session):
        response = client.get("/api/v1/series/search", params={"q": "x" * 201})
        assert response.status_code == 422

    def test_limit_zero_returns_422(self, client, seed_session):
        response = client.get("/api/v1/series/search", params={"q": "x", "limit": 0})
        assert response.status_code == 422

    def test_limit_above_maximum_returns_422(self, client, seed_session):
        response = client.get("/api/v1/series/search", params={"q": "x", "limit": 51})
        assert response.status_code == 422

    def test_malformed_limit_returns_422(self, client, seed_session):
        response = client.get("/api/v1/series/search", params={"q": "x", "limit": "not-a-number"})
        assert response.status_code == 422


class TestAnalyticsAndAiIndependence:
    def test_discovery_route_imports_no_analytics_or_ai(self):
        """Static guard: the discovery route/service must not import
        AnalysisService, EconomicDataService's transform capability, the
        domain math modules, or any AI/OpenAI module."""
        forbidden_prefixes = ("app.services.ai", "openai", "app.services.analysis", "app.domain")
        for module_file in ("services/discovery.py", "models/discovery.py"):
            path = APP_DIR / module_file
            tree = ast.parse(path.read_text(), filename=str(path))
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module)
                elif isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
            forbidden = {m for m in imported if any(m == p or m.startswith(p + ".") for p in forbidden_prefixes)}
            assert forbidden == set(), f"{module_file} imports {forbidden}"

    def test_discovery_does_not_call_economic_data_service_transform(self, client, seed_session, fred_configured):
        """EconomicDataService IS importable app-wide, but discovery
        must never invoke it -- proven by patching its transform method
        to raise if ever called during a search request."""
        from app.services.economic_data import EconomicDataService

        _seed(seed_session, "NOTRANSFORM")
        with patch.object(EconomicDataService, "get_transformed_observations", side_effect=AssertionError("must not be called")), \
             patch.object(FREDClient, "search_series", return_value=[]):
            response = client.get("/api/v1/series/search", params={"q": "notransform"})
        assert response.status_code == 200
