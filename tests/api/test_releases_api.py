"""GET /api/v1/releases (PostgreSQL-only, never FRED) and
POST /api/v1/releases/sync (FRED-backed, mocked at the FREDClient
method boundary -- never httpx, never a live network call).

The six curated releases seeded by
alembic/versions/fbbe6b1ab8d9_seed_curated_v1_release_catalog.py are
real, persistent baseline data for the whole test session (see
tests/api/conftest.py's `release_seed_session` fixture) -- every
release this file creates uses a provider_release_id well outside that
real range ("9001"+) so it can never collide with the curated
UNIQUE(provider, provider_release_id) constraint, and sync-path tests
that need to observe an exact, isolated set of active releases
explicitly deactivate the curated catalog first (the fixture's own
teardown reactivates it, so this never leaks between tests).
"""

from datetime import date
from unittest.mock import patch

from sqlalchemy import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.clients.fred import FREDAuthError, FREDClient, FREDTimeoutError, FREDUpstreamError, FredReleaseDate
from app.db.models import EconomicRelease
from app.services.releases import ReleaseReadService, ReleaseSyncService


def _seed_release(session, name="Test Release", provider_release_id="9001", active=True):
    release = EconomicRelease(name=name, provider="FRED", provider_release_id=provider_release_id, active=active)
    session.add(release)
    session.flush()
    session.commit()
    return release


def _seed_occurrence(session, release_id, scheduled_date):
    from app.repositories.release_repository import ReleaseRepository

    if isinstance(scheduled_date, str):
        scheduled_date = date.fromisoformat(scheduled_date)
    ReleaseRepository(session).upsert_occurrence(release_id, scheduled_date)
    session.commit()


def _deactivate_curated_releases(session):
    """Isolates a sync test to only the release(s) it creates itself --
    `ReleaseSyncService.sync_all` processes every *active* release, and
    the six migration-seeded curated releases are real, active data by
    default (see this module's docstring). Call this BEFORE seeding a
    test's own release. `release_seed_session`'s teardown restores
    `active=True` on the curated catalog afterward, so this never
    leaks into another test."""
    session.execute(text("UPDATE economic_releases SET active = false WHERE provider = 'FRED'"))
    session.commit()


class TestGetReleases:
    def test_success_exact_response_contract_past_due(self, client, release_seed_session):
        # A date far enough in the past that this assertion is stable
        # regardless of when the test actually runs -- no dependency on
        # "today" ambiguity.
        release = _seed_release(release_seed_session)
        _seed_occurrence(release_seed_session, release.id, "2000-01-01")

        response = client.get("/api/v1/releases")
        assert response.status_code == 200
        assert response.json() == {
            "releases": [
                {
                    "release_id": release.id,
                    "name": "Test Release",
                    "provider": "FRED",
                    "provider_release_id": "9001",
                    "official_url": None,
                    "scheduled_date": "2000-01-01",
                    "schedule_status": "PAST_DUE",
                }
            ],
            "pagination": {"limit": 100, "offset": 0, "returned": 1, "total": 1},
        }

    def test_success_exact_response_contract_scheduled(self, client, release_seed_session):
        # A date far enough in the future to be stably SCHEDULED.
        release = _seed_release(release_seed_session)
        _seed_occurrence(release_seed_session, release.id, "2099-01-01")

        response = client.get("/api/v1/releases")
        assert response.status_code == 200
        assert response.json()["releases"][0]["scheduled_date"] == "2099-01-01"
        assert response.json()["releases"][0]["schedule_status"] == "SCHEDULED"

    def test_empty_result_is_a_normal_200(self, client, release_seed_session):
        # No occurrence exists for ANY release yet, including the
        # curated six -- GET /releases lists occurrences (inner-joined
        # to their release), not the release catalog itself, so an
        # empty occurrence table means an empty result regardless of
        # how many releases are catalogued.
        response = client.get("/api/v1/releases")
        assert response.status_code == 200
        assert response.json() == {"releases": [], "pagination": {"limit": 100, "offset": 0, "returned": 0, "total": 0}}

    def test_start_date_filter(self, client, release_seed_session):
        release = _seed_release(release_seed_session)
        _seed_occurrence(release_seed_session, release.id, "2026-01-01")
        _seed_occurrence(release_seed_session, release.id, "2026-03-01")

        response = client.get("/api/v1/releases", params={"start_date": "2026-02-01"})
        dates = [r["scheduled_date"] for r in response.json()["releases"]]
        assert dates == ["2026-03-01"]

    def test_end_date_filter(self, client, release_seed_session):
        release = _seed_release(release_seed_session)
        _seed_occurrence(release_seed_session, release.id, "2026-01-01")
        _seed_occurrence(release_seed_session, release.id, "2026-03-01")

        response = client.get("/api/v1/releases", params={"end_date": "2026-02-01"})
        dates = [r["scheduled_date"] for r in response.json()["releases"]]
        assert dates == ["2026-01-01"]

    def test_ascending_order(self, client, release_seed_session):
        release = _seed_release(release_seed_session)
        _seed_occurrence(release_seed_session, release.id, "2026-03-01")
        _seed_occurrence(release_seed_session, release.id, "2026-01-01")

        response = client.get("/api/v1/releases", params={"order": "asc"})
        assert [r["scheduled_date"] for r in response.json()["releases"]] == ["2026-01-01", "2026-03-01"]

    def test_descending_order(self, client, release_seed_session):
        release = _seed_release(release_seed_session)
        _seed_occurrence(release_seed_session, release.id, "2026-01-01")
        _seed_occurrence(release_seed_session, release.id, "2026-03-01")

        response = client.get("/api/v1/releases", params={"order": "desc"})
        assert [r["scheduled_date"] for r in response.json()["releases"]] == ["2026-03-01", "2026-01-01"]

    def test_pagination(self, client, release_seed_session):
        release = _seed_release(release_seed_session)
        for d in ("2026-01-01", "2026-02-01", "2026-03-01"):
            _seed_occurrence(release_seed_session, release.id, d)

        response = client.get("/api/v1/releases", params={"limit": 1, "offset": 1})
        body = response.json()
        assert body["pagination"] == {"limit": 1, "offset": 1, "returned": 1, "total": 3}
        assert body["releases"][0]["scheduled_date"] == "2026-02-01"

    def test_semantic_invalid_date_range_returns_400(self, client, release_seed_session):
        response = client.get("/api/v1/releases", params={"start_date": "2026-03-01", "end_date": "2026-01-01"})
        assert response.status_code == 400

    def test_malformed_limit_returns_422(self, client, release_seed_session):
        response = client.get("/api/v1/releases", params={"limit": 0})
        assert response.status_code == 422

    def test_malformed_date_returns_422(self, client, release_seed_session):
        response = client.get("/api/v1/releases", params={"start_date": "not-a-date"})
        assert response.status_code == 422

    def test_malformed_order_returns_422(self, client, release_seed_session):
        response = client.get("/api/v1/releases", params={"order": "sideways"})
        assert response.status_code == 422

    def test_database_operational_error_returns_503(self, client, release_seed_session):
        with patch.object(ReleaseReadService, "list_releases", side_effect=OperationalError("s", {}, Exception("down"))):
            response = client.get("/api/v1/releases")
        assert response.status_code == 503
        assert "down" not in response.text

    def test_database_generic_sqlalchemy_error_returns_500(self, client, release_seed_session):
        with patch.object(ReleaseReadService, "list_releases", side_effect=SQLAlchemyError("synthetic")):
            response = client.get("/api/v1/releases")
        assert response.status_code == 500

    def test_never_constructs_a_fred_client_even_when_fred_is_fully_unconfigured(self, client, release_seed_session):
        """Fail-fast fake FRED boundary: if this route's code path ever
        tried to construct a FREDClient, this raises immediately and the
        request would come back as a 500 -- the 200 below would
        otherwise be unreachable. FRED is also left completely
        unconfigured (no fred_configured fixture here) to prove the
        read path doesn't even check for it."""
        release = _seed_release(release_seed_session)
        _seed_occurrence(release_seed_session, release.id, "2026-08-13")

        with patch.object(FREDClient, "__init__", side_effect=AssertionError("FREDClient must never be constructed here")):
            response = client.get("/api/v1/releases")
        assert response.status_code == 200

    def test_repeated_requests_are_deterministic(self, client, release_seed_session):
        release = _seed_release(release_seed_session)
        _seed_occurrence(release_seed_session, release.id, "2026-08-13")

        first = client.get("/api/v1/releases").json()
        second = client.get("/api/v1/releases").json()
        assert first == second


class TestPostReleasesSync:
    def test_missing_fred_configuration_returns_503(self, client, release_seed_session, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "fred_api_key", None)
        response = client.post("/api/v1/releases/sync")
        assert response.status_code == 503
        assert "FRED_API_KEY" not in response.text

    def test_success_exact_response_shape(self, client, release_seed_session, fred_configured):
        _deactivate_curated_releases(release_seed_session)
        release = _seed_release(release_seed_session, name="Test Release")

        with patch.object(FREDClient, "get_release_dates", return_value=[FredReleaseDate(release_id="9001", date=date(2026, 8, 13))]):
            response = client.post("/api/v1/releases/sync")

        assert response.status_code == 200
        assert response.json() == {
            "synced": [{"release_id": release.id, "name": "Test Release", "occurrences_seen": 1}],
            "failed": [],
        }

    def test_curated_catalog_is_what_gets_synced_when_active(self, client, release_seed_session, fred_configured):
        """With the curated catalog active (its normal state -- no
        deactivation here), a sync attempts exactly the six curated
        releases and none created ad hoc by this test."""
        with patch.object(FREDClient, "get_release_dates", return_value=[]):
            response = client.post("/api/v1/releases/sync")

        assert response.status_code == 200
        body = response.json()
        synced_names = sorted(s["name"] for s in body["synced"])
        assert synced_names == [
            "Advance Monthly Sales for Retail and Food Services",
            "Consumer Price Index",
            "Employment Situation",
            "Gross Domestic Product",
            "Job Openings and Labor Turnover Survey",
            "Personal Income and Outlays",
        ]
        assert body["failed"] == []

    def test_idempotent_repeated_sync(self, client, release_seed_session, fred_configured):
        _deactivate_curated_releases(release_seed_session)
        _seed_release(release_seed_session)

        with patch.object(FREDClient, "get_release_dates", return_value=[FredReleaseDate(release_id="9001", date=date(2026, 8, 13))]):
            client.post("/api/v1/releases/sync")
            client.post("/api/v1/releases/sync")

        response = client.get("/api/v1/releases")
        assert response.json()["pagination"]["total"] == 1

    def test_fred_auth_error_is_a_per_release_failure_no_key_leaked(self, client, release_seed_session, fred_configured):
        """A FRED auth failure is per-release (the sync route itself
        still returns 200 -- see ReleaseSyncService.sync_all), and the
        reported error is always the safe, generic message, never the
        raw upstream text (which could in principle echo the key)."""
        _deactivate_curated_releases(release_seed_session)
        release = _seed_release(release_seed_session, name="Test Release")
        with patch.object(FREDClient, "get_release_dates", side_effect=FREDAuthError("real upstream message with secret-looking-key=ABC123")):
            response = client.post("/api/v1/releases/sync")
        assert response.status_code == 200
        assert response.json() == {
            "synced": [],
            "failed": [{"release_id": release.id, "name": "Test Release", "error": "FRED rejected the configured API key."}],
        }
        assert "ABC123" not in response.text

    def test_fred_timeout_reported_as_per_release_failure_not_route_failure(self, client, release_seed_session, fred_configured):
        _deactivate_curated_releases(release_seed_session)
        _seed_release(release_seed_session)
        with patch.object(FREDClient, "get_release_dates", side_effect=FREDTimeoutError("timed out")):
            response = client.post("/api/v1/releases/sync")
        assert response.status_code == 200
        assert response.json()["synced"] == []
        assert len(response.json()["failed"]) == 1

    def test_fred_upstream_error_reported_as_per_release_failure(self, client, release_seed_session, fred_configured):
        _deactivate_curated_releases(release_seed_session)
        _seed_release(release_seed_session)
        with patch.object(FREDClient, "get_release_dates", side_effect=FREDUpstreamError("bad gateway equivalent")):
            response = client.post("/api/v1/releases/sync")
        assert response.status_code == 200
        assert response.json()["failed"][0]["error"] == "FRED returned an unexpected or malformed response."

    def test_database_operational_error_returns_503(self, client, release_seed_session, fred_configured):
        _seed_release(release_seed_session)
        with patch.object(ReleaseSyncService, "sync_all", side_effect=OperationalError("s", {}, Exception("down"))):
            response = client.post("/api/v1/releases/sync")
        assert response.status_code == 503
        assert "down" not in response.text

    def test_database_generic_sqlalchemy_error_returns_500(self, client, release_seed_session, fred_configured):
        _seed_release(release_seed_session)
        with patch.object(ReleaseSyncService, "sync_all", side_effect=SQLAlchemyError("synthetic")):
            response = client.post("/api/v1/releases/sync")
        assert response.status_code == 500

    def test_sync_never_appears_in_get_releases_response_shape(self, client, release_seed_session, fred_configured):
        """Sanity check that sync and read really are separate paths --
        sync's response never leaks into what GET /releases returns."""
        _deactivate_curated_releases(release_seed_session)
        _seed_release(release_seed_session)
        with patch.object(FREDClient, "get_release_dates", return_value=[FredReleaseDate(release_id="9001", date=date(2026, 8, 13))]):
            client.post("/api/v1/releases/sync")

        response = client.get("/api/v1/releases")
        assert "synced" not in response.json()
        assert "failed" not in response.json()
