"""Proof that the deterministic discovery capability preserved during
the Increment 012.5 cleanup (app/models/discovery.py,
app/services/discovery.py, SeriesRepository.search_series,
FREDClient.search_series) works correctly, both on its own (local-only,
no FRED client) and merged with a mocked FRED catalog boundary.

Increment 013 exposes this service via `GET /api/v1/series/search`
(see tests/api/test_series_search_api.py for the HTTP-level contract).
This file focuses on what's better proven below HTTP: merge/dedup
internals, ranking stability, and degradation behavior directly against
the service, without a request/response round trip in the way.
"""

from unittest.mock import patch

from app.clients.fred import FREDClient, FREDUpstreamError
from app.models.series import Observation, SeriesResponse
from app.repositories.series_repository import SeriesRepository
from app.services.discovery import SeriesDiscoveryService


def _seed(db_session, series_id, title):
    SeriesRepository(db_session).save_series(
        SeriesResponse(series_id=series_id, title=title, units="Percent", observations=[Observation(date="2024-01-01", value=1.0)])
    )
    db_session.flush()


def _fred_row(series_id, **overrides):
    row = {"id": series_id, "title": f"{series_id} title", "units": "Percent", "popularity": 50}
    row.update(overrides)
    return row


class TestDiscoveryServiceStandalone:
    def test_local_only_search_finds_persisted_series_by_id(self, db_session):
        _seed(db_session, "UNRATE", "Unemployment Rate")
        service = SeriesDiscoveryService(fred_client=None)
        result = service.search("UNRATE", limit=5, session=db_session)
        assert result.external_search_available is False  # no FRED client given
        assert [c.series_id for c in result.candidates] == ["UNRATE"]
        assert result.candidates[0].persisted is True
        assert result.candidates[0].discovery_source == "local"

    def test_local_only_search_finds_persisted_series_by_title_substring(self, db_session):
        _seed(db_session, "UNRATE", "Unemployment Rate")
        service = SeriesDiscoveryService(fred_client=None)
        result = service.search("unemployment", limit=5, session=db_session)
        assert [c.series_id for c in result.candidates] == ["UNRATE"]

    def test_no_match_returns_empty_candidates_not_an_error(self, db_session):
        service = SeriesDiscoveryService(fred_client=None)
        result = service.search("nonexistent concept", limit=5, session=db_session)
        assert result.candidates == []
        assert result.external_search_available is False

    def test_search_never_mutates_persisted_data(self, db_session):
        _seed(db_session, "UNRATE", "Unemployment Rate")
        before = SeriesRepository(db_session).get_series_by_series_id("UNRATE")
        SeriesDiscoveryService(fred_client=None).search("UNRATE", limit=5, session=db_session)
        after = SeriesRepository(db_session).get_series_by_series_id("UNRATE")
        assert before.title == after.title and before.units == after.units


class TestMergeAndDeduplication:
    def test_local_and_external_merge_is_deduplicated_and_richer(self, db_session):
        _seed(db_session, "UNRATE", "Unemployment Rate")
        fred_client = FREDClient(api_key="not-used", timeout=1.0)
        with patch.object(FREDClient, "search_series", return_value=[_fred_row("UNRATE", frequency="Monthly", popularity=96)]):
            result = SeriesDiscoveryService(fred_client).search("unemployment", limit=5, session=db_session)
        matches = [c for c in result.candidates if c.series_id == "UNRATE"]
        assert len(matches) == 1
        assert matches[0].persisted is True
        assert matches[0].discovery_source == "local_and_fred"
        assert matches[0].frequency == "Monthly"  # FRED metadata layered onto the local match

    def test_persisted_true_wins_over_fred_only_metadata(self, db_session):
        """Even if FRED's own row would imply persisted=False on its
        own, the merged candidate for a locally-known series_id must
        report persisted=True -- local persistence is authoritative."""
        _seed(db_session, "KNOWN", "Known Series")
        fred_client = FREDClient(api_key="not-used", timeout=1.0)
        with patch.object(FREDClient, "search_series", return_value=[_fred_row("KNOWN")]):
            result = SeriesDiscoveryService(fred_client).search("known", limit=5, session=db_session)
        assert next(c for c in result.candidates if c.series_id == "KNOWN").persisted is True

    def test_ranking_is_stable_across_repeated_identical_calls(self, db_session):
        _seed(db_session, "STABLE1", "Stable One")
        fred_rows = [_fred_row("STABLE2"), _fred_row("STABLE3"), _fred_row("STABLE1")]
        fred_client = FREDClient(api_key="not-used", timeout=1.0)
        with patch.object(FREDClient, "search_series", return_value=fred_rows):
            first = SeriesDiscoveryService(fred_client).search("stable", limit=5, session=db_session)
            second = SeriesDiscoveryService(fred_client).search("stable", limit=5, session=db_session)
        assert [c.series_id for c in first.candidates] == [c.series_id for c in second.candidates]

    def test_limit_respected_after_merge_not_before(self, db_session):
        _seed(db_session, "L1", "L1")
        _seed(db_session, "L2", "L2")
        fred_rows = [_fred_row("L1"), _fred_row("F1"), _fred_row("F2")]
        fred_client = FREDClient(api_key="not-used", timeout=1.0)
        with patch.object(FREDClient, "search_series", return_value=fred_rows):
            result = SeriesDiscoveryService(fred_client).search("l", limit=2, session=db_session)
        assert len(result.candidates) == 2


class TestServiceLevelDegradation:
    def test_local_results_survive_fred_upstream_failure(self, db_session):
        _seed(db_session, "SURVIVES", "Survives")
        fred_client = FREDClient(api_key="not-used", timeout=1.0)
        with patch.object(FREDClient, "search_series", side_effect=FREDUpstreamError("boom")):
            result = SeriesDiscoveryService(fred_client).search("survives", limit=5, session=db_session)
        assert result.external_search_available is False
        assert [c.series_id for c in result.candidates] == ["SURVIVES"]

    def test_no_local_and_fred_failure_returns_empty_not_an_exception(self, db_session):
        fred_client = FREDClient(api_key="not-used", timeout=1.0)
        with patch.object(FREDClient, "search_series", side_effect=FREDUpstreamError("boom")):
            result = SeriesDiscoveryService(fred_client).search("totallyunknown", limit=5, session=db_session)
        assert result.candidates == []
        assert result.external_search_available is False
