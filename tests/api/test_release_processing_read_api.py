"""GET /api/v1/releases/processing-status -- Increment #19B's public
release-processing read model. Database-only, never FRED, never AI.

Reuses tests/api/conftest.py's `release_seed_session` fixture
(unmodified) for seeding: its `TRUNCATE ... CASCADE` on
`release_occurrences` already cascades to `release_check_runs`,
`release_observation_updates`, and `release_analysis_updates` (each
FKs to the row above it with `ondelete="CASCADE"`), and its `DELETE
FROM economic_releases` cascade already removes this file's
`release_series_mappings` rows too -- no new cleanup fixture needed.
Every release/occurrence a test creates uses a provider_release_id
well outside the curated range ("9001"+), the same discipline
tests/api/test_releases_api.py already establishes.
"""

from datetime import date, datetime, timezone
from unittest.mock import patch

from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.db.models import EconomicRelease, ReleaseAnalysisUpdate, ReleaseCheckRun, ReleaseObservationUpdate, ReleaseSeriesMapping
from app.services.release_processing_read import ReleaseProcessingReadService


def _seed_release(session, provider_release_id="9001", name="Test Release", active=True):
    release = EconomicRelease(name=name, provider="FRED", provider_release_id=provider_release_id, active=active)
    session.add(release)
    session.flush()
    session.commit()
    return release


def _seed_mapping(session, release_id, series_id="UNRATE", active=True):
    mapping = ReleaseSeriesMapping(economic_release_id=release_id, series_id=series_id, active=active)
    session.add(mapping)
    session.commit()
    return mapping


def _seed_occurrence(session, release_id, scheduled_date):
    from app.repositories.release_repository import ReleaseRepository

    if isinstance(scheduled_date, str):
        scheduled_date = date.fromisoformat(scheduled_date)
    occurrence = ReleaseRepository(session).upsert_occurrence(release_id, scheduled_date)
    session.commit()
    return occurrence


def _seed_check_run(session, occurrence_id, status="NO_CHANGE", completed_at=None):
    completed_at = completed_at or datetime(2026, 7, 1, tzinfo=timezone.utc)
    run = ReleaseCheckRun(release_occurrence_id=occurrence_id, status=status, started_at=completed_at, completed_at=completed_at)
    session.add(run)
    session.commit()
    return run


def _seed_observation_update(session, run_id, series_id="UNRATE", observation_date=date(2026, 7, 1), change_type="NEW", detected_at=None):
    update = ReleaseObservationUpdate(
        release_check_run_id=run_id,
        series_id=series_id,
        observation_date=observation_date,
        change_type=change_type,
        previous_value=None,
        new_value=3.9,
        detected_at=detected_at or datetime(2026, 7, 1, tzinfo=timezone.utc),
    )
    session.add(update)
    session.commit()
    return update


def _seed_analysis_update(session, run_id, evaluation_period=date(2026, 7, 1)):
    update = ReleaseAnalysisUpdate(
        release_check_run_id=run_id,
        component="PRIMARY_MOMENTUM",
        event_type="METRIC_CHANGED",
        field="r_3m_annualized",
        previous_value="2.0",
        current_value="2.5",
        delta=0.5,
        evaluation_period=evaluation_period,
        methodology_id="inflation_v1",
        data_basis="revised",
    )
    session.add(update)
    session.commit()
    return update


class TestGetProcessingStatus:
    def test_never_checked_occurrence_is_a_normal_200(self, client, release_seed_session):
        release = _seed_release(release_seed_session, "9201")
        _seed_mapping(release_seed_session, release.id)
        occurrence = _seed_occurrence(release_seed_session, release.id, "2026-07-01")

        response = client.get("/api/v1/releases/processing-status", params={"occurrence_id": occurrence.id})
        assert response.status_code == 200
        body = response.json()
        assert body["occurrences"][0]["latest_check"] == {"status": "NOT_CHECKED", "checked_at": None}
        assert body["occurrences"][0]["detected_observation_changes"] == []
        assert body["occurrences"][0]["detected_analysis_changes"] == []

    def test_check_failed_status_is_still_http_200(self, client, release_seed_session):
        release = _seed_release(release_seed_session, "9202")
        _seed_mapping(release_seed_session, release.id)
        occurrence = _seed_occurrence(release_seed_session, release.id, "2026-07-01")
        _seed_check_run(release_seed_session, occurrence.id, status="FAILED_PROVIDER")

        response = client.get("/api/v1/releases/processing-status", params={"occurrence_id": occurrence.id})
        assert response.status_code == 200
        assert response.json()["occurrences"][0]["latest_check"]["status"] == "CHECK_FAILED"

    def test_unmapped_release_occurrence_is_excluded_entirely(self, client, release_seed_session):
        release = _seed_release(release_seed_session, "9203")
        # No mapping seeded.
        occurrence = _seed_occurrence(release_seed_session, release.id, "2026-07-01")

        response = client.get("/api/v1/releases/processing-status", params={"occurrence_id": occurrence.id})
        assert response.status_code == 200
        assert response.json()["occurrences"] == []
        assert response.json()["pagination"]["total"] == 0

    def test_sibling_not_nested_response_shape(self, client, release_seed_session):
        release = _seed_release(release_seed_session, "9204")
        _seed_mapping(release_seed_session, release.id)
        occurrence = _seed_occurrence(release_seed_session, release.id, "2026-07-01")
        run = _seed_check_run(release_seed_session, occurrence.id, status="CHANGED")
        _seed_observation_update(release_seed_session, run.id)
        _seed_analysis_update(release_seed_session, run.id)

        response = client.get("/api/v1/releases/processing-status", params={"occurrence_id": occurrence.id})
        item = response.json()["occurrences"][0]
        assert "detected_observation_changes" in item
        assert "detected_analysis_changes" in item
        assert "detected_change" not in item
        assert len(item["detected_observation_changes"]) == 1
        assert len(item["detected_analysis_changes"]) == 1
        # Sibling, not nested: an analysis change never appears inside
        # an observation change's own dict.
        assert "analysis_consequences" not in item["detected_observation_changes"][0]
        assert "observation_changes" not in item["detected_analysis_changes"][0]

    def test_retry_history_survives_a_subsequent_no_change_run_over_http(self, client, release_seed_session):
        release = _seed_release(release_seed_session, "9205")
        _seed_mapping(release_seed_session, release.id)
        occurrence = _seed_occurrence(release_seed_session, release.id, "2026-07-01")
        first_run = _seed_check_run(release_seed_session, occurrence.id, status="CHANGED", completed_at=datetime(2026, 7, 1, tzinfo=timezone.utc))
        _seed_observation_update(release_seed_session, first_run.id, detected_at=datetime(2026, 7, 1, tzinfo=timezone.utc))
        _seed_check_run(release_seed_session, occurrence.id, status="NO_CHANGE", completed_at=datetime(2026, 7, 2, tzinfo=timezone.utc))

        response = client.get("/api/v1/releases/processing-status", params={"occurrence_id": occurrence.id})
        item = response.json()["occurrences"][0]
        assert item["latest_check"]["status"] == "NO_CHANGE"
        assert len(item["detected_observation_changes"]) == 1

    def test_filters_by_status(self, client, release_seed_session):
        release = _seed_release(release_seed_session, "9206")
        _seed_mapping(release_seed_session, release.id)
        occ_a = _seed_occurrence(release_seed_session, release.id, "2026-07-01")
        _seed_check_run(release_seed_session, occ_a.id, status="NO_CHANGE")
        occ_b = _seed_occurrence(release_seed_session, release.id, "2026-07-02")
        _seed_check_run(release_seed_session, occ_b.id, status="CHANGED")

        response = client.get("/api/v1/releases/processing-status", params={"release_id": release.id, "status": "CHANGES_DETECTED"})
        occurrence_ids = {item["occurrence_id"] for item in response.json()["occurrences"]}
        assert occ_b.id in occurrence_ids
        assert occ_a.id not in occurrence_ids

    def test_pagination_defaults(self, client, release_seed_session):
        release = _seed_release(release_seed_session, "9207")
        _seed_mapping(release_seed_session, release.id)
        _seed_occurrence(release_seed_session, release.id, "2026-07-01")

        response = client.get("/api/v1/releases/processing-status", params={"release_id": release.id})
        pagination = response.json()["pagination"]
        assert pagination["limit"] == 20
        assert pagination["offset"] == 0

    def test_limit_and_offset_are_honored(self, client, release_seed_session):
        release = _seed_release(release_seed_session, "9208")
        _seed_mapping(release_seed_session, release.id)
        for day in range(1, 6):
            _seed_occurrence(release_seed_session, release.id, date(2026, 7, day))

        response = client.get("/api/v1/releases/processing-status", params={"release_id": release.id, "limit": 2, "offset": 1})
        body = response.json()
        assert len(body["occurrences"]) == 2
        assert body["pagination"] == {"limit": 2, "offset": 1, "returned": 2, "total": 5}

    def test_semantic_invalid_date_range_returns_400(self, client, release_seed_session):
        response = client.get(
            "/api/v1/releases/processing-status", params={"start_date": "2026-03-01", "end_date": "2026-01-01"}
        )
        assert response.status_code == 400

    def test_malformed_limit_returns_422(self, client, release_seed_session):
        response = client.get("/api/v1/releases/processing-status", params={"limit": 0})
        assert response.status_code == 422

    def test_malformed_status_returns_422(self, client, release_seed_session):
        response = client.get("/api/v1/releases/processing-status", params={"status": "BOGUS"})
        assert response.status_code == 422

    def test_malformed_date_returns_422(self, client, release_seed_session):
        response = client.get("/api/v1/releases/processing-status", params={"start_date": "not-a-date"})
        assert response.status_code == 422

    def test_database_operational_error_returns_503(self, client, release_seed_session):
        with patch.object(ReleaseProcessingReadService, "get_processing_status", side_effect=OperationalError("s", {}, Exception("down"))):
            response = client.get("/api/v1/releases/processing-status")
        assert response.status_code == 503
        assert "down" not in response.text

    def test_database_generic_sqlalchemy_error_returns_500(self, client, release_seed_session):
        with patch.object(ReleaseProcessingReadService, "get_processing_status", side_effect=SQLAlchemyError("synthetic")):
            response = client.get("/api/v1/releases/processing-status")
        assert response.status_code == 500
        assert "synthetic" not in response.text

    def test_repeated_requests_are_deterministic(self, client, release_seed_session):
        release = _seed_release(release_seed_session, "9209")
        _seed_mapping(release_seed_session, release.id)
        occurrence = _seed_occurrence(release_seed_session, release.id, "2026-07-01")
        run = _seed_check_run(release_seed_session, occurrence.id, status="CHANGED")
        _seed_observation_update(release_seed_session, run.id)

        first = client.get("/api/v1/releases/processing-status", params={"occurrence_id": occurrence.id})
        second = client.get("/api/v1/releases/processing-status", params={"occurrence_id": occurrence.id})
        assert first.json() == second.json()

    def test_no_occurrence_detail_route_exists(self, client, release_seed_session):
        release = _seed_release(release_seed_session, "9210")
        _seed_mapping(release_seed_session, release.id)
        occurrence = _seed_occurrence(release_seed_session, release.id, "2026-07-01")

        response = client.get(f"/api/v1/releases/{occurrence.id}/processing-status")
        assert response.status_code == 404
