"""Small, focused proof that the deterministic discovery capability
preserved during the Increment 012.5 cleanup (app/models/discovery.py,
app/services/discovery.py, SeriesRepository.search_series,
FREDClient.search_series) still works correctly on its own, now that it
is no longer wired into the (reverted) AI tool loop.

Local-only: `SeriesDiscoveryService(fred_client=None)` -- no FRED
dependency, no live network call, matching the discovery service's own
documented graceful-degradation behavior when no FRED client is given.
Not yet exposed via any HTTP route (that's Increment 013's job) -- this
tests the service directly, exactly as it will be called from wherever
that future route ends up.
"""

from app.models.series import Observation, SeriesResponse
from app.repositories.series_repository import SeriesRepository
from app.services.discovery import SeriesDiscoveryService


def _seed(db_session, series_id, title):
    SeriesRepository(db_session).save_series(
        SeriesResponse(series_id=series_id, title=title, units="Percent", observations=[Observation(date="2024-01-01", value=1.0)])
    )
    db_session.flush()


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
