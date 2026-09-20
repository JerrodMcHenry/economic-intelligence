"""HTTP contract tests for point-in-time intelligence history
(Increment #32).

Scoped to what only the route layer can get wrong -- status codes,
validation bounds, pagination wiring, and the monitor vocabulary. The
economic semantics behind the payload are proven in
`tests/integration/test_monitor_history_service.py`, against a session
the test itself controls.
"""

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.db.models import EconomicRelease, RecordedMonitorResult, ReleaseCheckRun, ReleaseOccurrence
from app.models.inflation import METHODOLOGY_ID as INFLATION_METHODOLOGY_ID
from app.models.labor import METHODOLOGY_ID as LABOR_METHODOLOGY_ID

pytestmark = pytest.mark.api

CALCULATED_AT = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def history_seed_session(test_database_url: str):
    """A real, committing session -- the ASGI request opens its own
    connection and cannot see an uncommitted transaction (see
    tests/api/conftest.py). Cleanup truncates only the recorded-history
    tables this suite creates; `economic_releases` keeps its
    migration-seeded curated catalog, exactly as `release_seed_session`
    already establishes.
    """
    engine = create_engine(test_database_url)
    session = Session(bind=engine)
    try:
        yield session
    finally:
        session.rollback()
        session.execute(text("TRUNCATE TABLE release_occurrences RESTART IDENTITY CASCADE"))
        session.execute(text("DELETE FROM economic_releases WHERE provider_release_id = '8888'"))
        session.commit()
        session.close()
        engine.dispose()


def _recorded(session, monitor: str, state: str, methodology_id: str, period: date) -> int:
    release = session.execute(
        select(EconomicRelease).where(EconomicRelease.provider == "FRED", EconomicRelease.provider_release_id == "8888")
    ).scalar_one_or_none()
    if release is None:
        release = EconomicRelease(name="History Test Release", provider="FRED", provider_release_id="8888", active=True)
        session.add(release)
        session.flush()
    occurrence = session.execute(
        select(ReleaseOccurrence).where(
            ReleaseOccurrence.economic_release_id == release.id,
            ReleaseOccurrence.scheduled_date == date(2026, 5, 1),
        )
    ).scalar_one_or_none()
    if occurrence is None:
        occurrence = ReleaseOccurrence(economic_release_id=release.id, scheduled_date=date(2026, 5, 1))
        session.add(occurrence)
        session.flush()
    run = ReleaseCheckRun(
        release_occurrence_id=occurrence.id, status="CHANGED", started_at=CALCULATED_AT, completed_at=CALCULATED_AT
    )
    session.add(run)
    session.flush()
    recorded = RecordedMonitorResult(
        release_check_run_id=run.id,
        monitor=monitor,
        evaluation_period=period,
        state=state,
        methodology_id=methodology_id,
        data_basis="latest_revised_data",
        calculated_at=CALCULATED_AT,
    )
    session.add(recorded)
    session.commit()
    return recorded.id


class TestHistoryList:
    def test_an_empty_history_is_a_200_with_an_empty_page(self, client):
        response = client.get("/api/v1/monitors/inflation/history")
        assert response.status_code == 200
        body = response.json()
        assert body["monitor"] == "inflation"
        assert body["entries"] == []
        assert body["pagination"] == {"limit": 20, "offset": 0, "returned": 0, "total": 0}

    def test_default_limit_matches_the_read_model_convention(self, client):
        body = client.get("/api/v1/monitors/labor/history").json()
        assert body["pagination"]["limit"] == 20

    def test_history_is_bounded_and_cannot_be_requested_unbounded(self, client):
        assert client.get("/api/v1/monitors/labor/history", params={"limit": 101}).status_code == 422
        assert client.get("/api/v1/monitors/labor/history", params={"limit": 0}).status_code == 422
        assert client.get("/api/v1/monitors/labor/history", params={"offset": -1}).status_code == 422
        assert client.get("/api/v1/monitors/labor/history", params={"limit": 100}).status_code == 200

    def test_a_recorded_result_is_returned_with_its_replay_outcome(self, client, history_seed_session):
        _recorded(history_seed_session, "inflation", "COOLING", INFLATION_METHODOLOGY_ID, date(2026, 3, 1))

        body = client.get("/api/v1/monitors/inflation/history").json()

        assert body["pagination"]["total"] == 1
        entry = body["entries"][0]
        assert entry["state"] == "COOLING"
        assert entry["evaluation_period"] == "2026-03-01"
        assert entry["methodology_id"] == INFLATION_METHODOLOGY_ID
        # No version history was seeded, so replay must refuse rather
        # than recompute from whatever exists.
        assert entry["replay"]["outcome"] == "NOT_REPLAYABLE"
        assert entry["replay"]["replayed_state"] is None


class TestMonitorVocabulary:
    def test_rates_has_no_recorded_state_history_and_is_rejected(self, client):
        """Rates gained observation versioning in #31 but records no
        monitor state. An empty list would imply a history that does not
        exist, so the monitor is not part of this route's vocabulary."""
        assert client.get("/api/v1/monitors/rates/history").status_code == 422

    def test_an_unknown_monitor_is_rejected(self, client):
        assert client.get("/api/v1/monitors/equities/history").status_code == 422

    @pytest.mark.parametrize("monitor", ["inflation", "labor"])
    def test_both_recording_monitors_are_accepted(self, client, monitor):
        assert client.get(f"/api/v1/monitors/{monitor}/history").status_code == 200


class TestHistoryDetail:
    def test_a_missing_recorded_result_is_a_404(self, client):
        response = client.get("/api/v1/monitors/inflation/history/999999")
        assert response.status_code == 404
        assert "999999" in response.json()["detail"]

    def test_a_result_belonging_to_another_monitor_is_a_404(self, client, history_seed_session):
        labor_id = _recorded(history_seed_session, "labor", "MIXED", LABOR_METHODOLOGY_ID, date(2026, 3, 1))

        assert client.get(f"/api/v1/monitors/labor/history/{labor_id}").status_code == 200
        assert client.get(f"/api/v1/monitors/inflation/history/{labor_id}").status_code == 404

    def test_a_non_integer_id_is_a_422(self, client):
        assert client.get("/api/v1/monitors/inflation/history/not-an-id").status_code == 422

    def test_the_detail_payload_carries_every_contracted_section(self, client, history_seed_session):
        recorded_id = _recorded(history_seed_session, "labor", "MIXED", LABOR_METHODOLOGY_ID, date(2026, 3, 1))

        body = client.get(f"/api/v1/monitors/labor/history/{recorded_id}").json()

        assert set(body) == {
            "recorded",
            "historical_inputs",
            "current_comparison",
            "related_changes",
            "other_changes_in_same_run",
        }
        assert body["recorded"]["monitor"] == "labor"
        assert body["current_comparison"]["methodology_id_then"] == LABOR_METHODOLOGY_ID


class TestReadSideNeverWrites:
    def test_requesting_history_never_creates_a_recorded_result(self, client, history_seed_session):
        """`recorded_monitor_results` is append-only and written only by
        release processing (ADR-025). Reading history must never add to
        the history it reads."""
        _recorded(history_seed_session, "inflation", "COOLING", INFLATION_METHODOLOGY_ID, date(2026, 3, 1))
        before = history_seed_session.execute(text("SELECT count(*) FROM recorded_monitor_results")).scalar_one()

        for _ in range(3):
            client.get("/api/v1/monitors/inflation/history")
            client.get("/api/v1/monitors/labor/history")

        after = history_seed_session.execute(text("SELECT count(*) FROM recorded_monitor_results")).scalar_one()
        assert after == before

    def test_requesting_history_never_creates_an_observation_version(self, client, history_seed_session):
        recorded_id = _recorded(history_seed_session, "inflation", "COOLING", INFLATION_METHODOLOGY_ID, date(2026, 3, 1))
        before = history_seed_session.execute(text("SELECT count(*) FROM observation_versions")).scalar_one()

        client.get(f"/api/v1/monitors/inflation/history/{recorded_id}")

        after = history_seed_session.execute(text("SELECT count(*) FROM observation_versions")).scalar_one()
        assert after == before
