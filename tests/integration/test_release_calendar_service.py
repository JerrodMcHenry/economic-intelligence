"""Integration tests for the release calendar service layer --
`ReleaseReadService` (database-only) and `ReleaseSyncService` (FRED
mocked at the `FREDClient`-*method* boundary, the same pattern
tests/integration/test_discovery_service.py already establishes for
FRED-touching service tests -- see that file's docstring, and this
file's entry in test_transaction_and_safety.py's `NETWORK_EXCEPTIONS`).
No live FRED anywhere.

The six releases seeded by
alembic/versions/fbbe6b1ab8d9_seed_curated_v1_release_catalog.py
(provider_release_id 9/10/50/53/54/192) are real, persistent, *active*
data in the isolated test database this file runs against. Read-path
tests use a provider_release_id well outside that range ("9001"+) so
they never collide with the real UNIQUE(provider, provider_release_id)
constraint. Sync-path tests additionally deactivate the curated catalog
first (`ReleaseSyncService.sync_all` processes every active release) --
safe: `db_session` rolls the whole transaction back at teardown, so
this never leaks into another test.
"""

import inspect
from datetime import date
from unittest.mock import patch

import pytest
from sqlalchemy import select, update

from app.clients.fred import FREDAuthError, FREDClient, FredReleaseDate
from app.db.models import EconomicObservation, EconomicRelease
from app.repositories.release_repository import ReleaseRepository
from app.services.releases import InvalidDateRangeError, ReleaseReadService, ReleaseSyncService

JAN, FEB, MAR = (date(2026, m, 1) for m in range(1, 4))


def _release(session, name="Test Release", provider_release_id="9001", active=True):
    release = EconomicRelease(name=name, provider="FRED", provider_release_id=provider_release_id, active=active)
    session.add(release)
    session.flush()
    return release


def _deactivate_curated_releases(session):
    session.execute(update(EconomicRelease).values(active=False))
    session.flush()


class TestReleaseReadServiceIsDatabaseOnly:
    def test_no_method_accepts_anything_fred_shaped(self):
        """Structural proof, not just behavioral: no constructor or
        method on this class has a FRED-named parameter -- there is
        nothing for a future edit to accidentally wire a live call
        into."""
        service = ReleaseReadService()
        for name, member in inspect.getmembers(service, predicate=inspect.ismethod):
            if name.startswith("_"):
                continue
            for param_name in inspect.signature(member).parameters:
                assert "fred" not in param_name.lower()

    def test_reads_persisted_occurrences(self, db_session):
        release = _release(db_session)
        ReleaseRepository(db_session).upsert_occurrence(release.id, JAN)
        db_session.flush()

        result = ReleaseReadService().list_releases(
            db_session, start_date=None, end_date=None, limit=100, offset=0, order="asc", as_of_date=JAN
        )
        assert len(result.releases) == 1
        assert result.releases[0].name == "Test Release"
        assert result.releases[0].scheduled_date == JAN

    def test_derives_schedule_status_from_the_given_as_of_date(self, db_session):
        release = _release(db_session)
        ReleaseRepository(db_session).upsert_occurrence(release.id, JAN)
        db_session.flush()

        service = ReleaseReadService()
        before = service.list_releases(
            db_session, start_date=None, end_date=None, limit=100, offset=0, order="asc", as_of_date=date(2025, 12, 1)
        )
        after = service.list_releases(
            db_session, start_date=None, end_date=None, limit=100, offset=0, order="asc", as_of_date=date(2026, 2, 1)
        )
        assert before.releases[0].schedule_status == "SCHEDULED"
        assert after.releases[0].schedule_status == "PAST_DUE"

    def test_invalid_date_range_raises(self, db_session):
        with pytest.raises(InvalidDateRangeError):
            ReleaseReadService().list_releases(
                db_session, start_date=FEB, end_date=JAN, limit=100, offset=0, order="asc", as_of_date=JAN
            )

    def test_filters_order_and_pagination_pass_through_to_the_repository(self, db_session):
        release = _release(db_session)
        repo = ReleaseRepository(db_session)
        for d in (JAN, FEB, MAR):
            repo.upsert_occurrence(release.id, d)
        db_session.flush()

        result = ReleaseReadService().list_releases(
            db_session, start_date=None, end_date=None, limit=1, offset=1, order="asc", as_of_date=JAN
        )
        assert result.pagination.total == 3
        assert result.pagination.returned == 1
        assert result.releases[0].scheduled_date == FEB


class TestReleaseSyncService:
    def test_syncs_active_curated_releases_only(self, db_session):
        _deactivate_curated_releases(db_session)
        _release(db_session, name="Active", provider_release_id="9001", active=True)
        _release(db_session, name="Inactive", provider_release_id="9002", active=False)

        client = FREDClient(api_key="not-used", timeout=1.0)
        with patch.object(FREDClient, "get_release_dates", return_value=[FredReleaseDate(release_id="9001", date=JAN)]):
            result = ReleaseSyncService(client).sync_all(db_session)

        assert [s.name for s in result.synced] == ["Active"]
        assert result.failed == []
        _, total = ReleaseRepository(db_session).list_occurrences(
            start_date=None, end_date=None, limit=100, offset=0, order="asc"
        )
        assert total == 1

    def test_syncs_exactly_the_six_curated_releases_when_active(self, db_session):
        """The real migration-seeded catalog, not a synthetic
        substitute -- proves sync actually attempts the six approved
        V1 releases and nothing else, satisfying the follow-up's own
        requirement that sync only ever touches this set."""
        client = FREDClient(api_key="not-used", timeout=1.0)
        with patch.object(FREDClient, "get_release_dates", return_value=[]):
            result = ReleaseSyncService(client).sync_all(db_session)

        assert sorted(s.name for s in result.synced) == [
            "Advance Monthly Sales for Retail and Food Services",
            "Consumer Price Index",
            "Employment Situation",
            "Gross Domestic Product",
            "Job Openings and Labor Turnover Survey",
            "Personal Income and Outlays",
        ]
        assert result.failed == []

    def test_repeated_sync_is_idempotent(self, db_session):
        _deactivate_curated_releases(db_session)
        _release(db_session)
        client = FREDClient(api_key="not-used", timeout=1.0)
        with patch.object(FREDClient, "get_release_dates", return_value=[FredReleaseDate(release_id="9001", date=JAN)]):
            ReleaseSyncService(client).sync_all(db_session)
            ReleaseSyncService(client).sync_all(db_session)

        _, total = ReleaseRepository(db_session).list_occurrences(
            start_date=None, end_date=None, limit=100, offset=0, order="asc"
        )
        assert total == 1

    def test_historical_occurrence_survives_when_provider_stops_returning_it(self, db_session):
        _deactivate_curated_releases(db_session)
        _release(db_session)
        client = FREDClient(api_key="not-used", timeout=1.0)
        with patch.object(FREDClient, "get_release_dates", return_value=[FredReleaseDate(release_id="9001", date=JAN)]):
            ReleaseSyncService(client).sync_all(db_session)
        with patch.object(FREDClient, "get_release_dates", return_value=[FredReleaseDate(release_id="9001", date=FEB)]):
            ReleaseSyncService(client).sync_all(db_session)

        rows, total = ReleaseRepository(db_session).list_occurrences(
            start_date=None, end_date=None, limit=100, offset=0, order="asc"
        )
        assert total == 2
        assert {row[1].scheduled_date for row in rows} == {JAN, FEB}

    def test_one_release_provider_failure_does_not_prevent_syncing_others(self, db_session):
        _deactivate_curated_releases(db_session)
        _release(db_session, name="Good", provider_release_id="9001")
        _release(db_session, name="Bad", provider_release_id="9002")
        client = FREDClient(api_key="not-used", timeout=1.0)

        def fake_get_release_dates(self_, release_id):
            if release_id == "9002":
                raise FREDAuthError("simulated auth failure")
            return [FredReleaseDate(release_id=release_id, date=JAN)]

        with patch.object(FREDClient, "get_release_dates", fake_get_release_dates):
            result = ReleaseSyncService(client).sync_all(db_session)

        assert [s.name for s in result.synced] == ["Good"]
        assert [f.name for f in result.failed] == ["Bad"]
        assert "FRED rejected" in result.failed[0].error  # safe, generic message -- never the raw exception text

    def test_provider_failure_never_erases_a_previously_persisted_occurrence(self, db_session):
        _deactivate_curated_releases(db_session)
        _release(db_session)
        client = FREDClient(api_key="not-used", timeout=1.0)

        with patch.object(FREDClient, "get_release_dates", return_value=[FredReleaseDate(release_id="9001", date=JAN)]):
            ReleaseSyncService(client).sync_all(db_session)
        with patch.object(FREDClient, "get_release_dates", side_effect=FREDAuthError("simulated")):
            ReleaseSyncService(client).sync_all(db_session)

        _, total = ReleaseRepository(db_session).list_occurrences(
            start_date=None, end_date=None, limit=100, offset=0, order="asc"
        )
        assert total == 1

    def test_sync_never_writes_an_economic_observation(self, db_session):
        _deactivate_curated_releases(db_session)
        _release(db_session)
        client = FREDClient(api_key="not-used", timeout=1.0)
        with patch.object(FREDClient, "get_release_dates", return_value=[FredReleaseDate(release_id="9001", date=JAN)]):
            ReleaseSyncService(client).sync_all(db_session)

        assert db_session.execute(select(EconomicObservation)).first() is None
