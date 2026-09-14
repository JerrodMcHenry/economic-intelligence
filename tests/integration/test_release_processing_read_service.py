"""Integration tests for Increment #19B's ReleaseProcessingReadService
against a real, isolated PostgreSQL test database (see
tests/conftest.py). No FastAPI, no FRED, no AI.

Rows are seeded directly via the ORM (not through
`ReleaseProcessingService.process_occurrence`) -- the write path's own
correctness (classification, idempotency, transaction boundaries) is
already exhaustively covered by
tests/integration/test_release_processing_service.py; this file's job
is to prove the READ PROJECTION over whatever rows already exist,
including the specific retry-history-preservation guarantee #19B
exists for.
"""

from datetime import date, datetime, timezone

import pytest

from app.db.models import EconomicRelease, EconomicSeries, ReleaseAnalysisUpdate, ReleaseCheckRun, ReleaseObservationUpdate, ReleaseSeriesMapping
from app.repositories.release_repository import ReleaseRepository
from app.services.release_processing_read import InvalidDateRangeError, ReleaseProcessingReadService

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _release(session, name="Test Release", provider_release_id="9001", active=True):
    release = EconomicRelease(name=name, provider="FRED", provider_release_id=provider_release_id, active=active)
    session.add(release)
    session.flush()
    return release


def _mapping(session, release, series_id="UNRATE", active=True):
    mapping = ReleaseSeriesMapping(economic_release_id=release.id, series_id=series_id, active=active)
    session.add(mapping)
    session.flush()
    return mapping


def _occurrence(session, release, scheduled_date):
    return ReleaseRepository(session).upsert_occurrence(release.id, scheduled_date)


def _check_run(session, occurrence, status="NO_CHANGE", completed_at=NOW):
    run = ReleaseCheckRun(release_occurrence_id=occurrence.id, status=status, started_at=completed_at, completed_at=completed_at)
    session.add(run)
    session.flush()
    return run


def _observation_update(session, run, series_id="UNRATE", observation_date=date(2026, 7, 1), change_type="NEW", detected_at=NOW, previous_value=None, new_value=3.9):
    update = ReleaseObservationUpdate(
        release_check_run_id=run.id,
        series_id=series_id,
        observation_date=observation_date,
        change_type=change_type,
        previous_value=previous_value,
        new_value=new_value,
        detected_at=detected_at,
    )
    session.add(update)
    session.flush()
    return update


def _analysis_update(session, run, evaluation_period=date(2026, 7, 1), component="PRIMARY_MOMENTUM", event_type="METRIC_CHANGED"):
    update = ReleaseAnalysisUpdate(
        release_check_run_id=run.id,
        component=component,
        event_type=event_type,
        field="r_3m_annualized",
        previous_value="2.0",
        current_value="2.5",
        delta=0.5,
        evaluation_period=evaluation_period,
        methodology_id="inflation_v1",
        data_basis="revised",
    )
    session.add(update)
    session.flush()
    return update


def _standard_release_occurrence(session, provider_release_id, scheduled_date=date(2026, 7, 1), series_id="UNRATE"):
    release = _release(session, provider_release_id=provider_release_id)
    _mapping(session, release, series_id=series_id)
    occurrence = _occurrence(session, release, scheduled_date)
    return release, occurrence


class TestNonMutation:
    def test_service_never_writes_a_row(self, db_session):
        release, occurrence = _standard_release_occurrence(db_session, "9101")
        _check_run(db_session, occurrence)

        before = {
            "releases": db_session.query(EconomicRelease).count(),
            "runs": db_session.query(ReleaseCheckRun).count(),
        }
        ReleaseProcessingReadService().get_processing_status(
            db_session, occurrence_id=None, release_id=None, status=None, start_date=None, end_date=None, limit=20, offset=0
        )
        after = {
            "releases": db_session.query(EconomicRelease).count(),
            "runs": db_session.query(ReleaseCheckRun).count(),
        }
        assert before == after


class TestStatusDerivation:
    def test_no_run_at_all_is_not_checked(self, db_session):
        release, occurrence = _standard_release_occurrence(db_session, "9110")
        response = ReleaseProcessingReadService().get_processing_status(
            db_session, occurrence_id=occurrence.id, release_id=None, status=None, start_date=None, end_date=None, limit=20, offset=0
        )
        assert len(response.occurrences) == 1
        item = response.occurrences[0]
        assert item.latest_check.status == "NOT_CHECKED"
        assert item.latest_check.checked_at is None
        assert item.detected_observation_changes == []
        assert item.detected_analysis_changes == []

    def test_no_change_run_maps_to_no_change(self, db_session):
        release, occurrence = _standard_release_occurrence(db_session, "9111")
        _check_run(db_session, occurrence, status="NO_CHANGE")
        item = ReleaseProcessingReadService().get_processing_status(
            db_session, occurrence_id=occurrence.id, release_id=None, status=None, start_date=None, end_date=None, limit=20, offset=0
        ).occurrences[0]
        assert item.latest_check.status == "NO_CHANGE"
        assert item.latest_check.checked_at is not None

    def test_changed_run_maps_to_changes_detected(self, db_session):
        release, occurrence = _standard_release_occurrence(db_session, "9112")
        _check_run(db_session, occurrence, status="CHANGED")
        item = ReleaseProcessingReadService().get_processing_status(
            db_session, occurrence_id=occurrence.id, release_id=None, status=None, start_date=None, end_date=None, limit=20, offset=0
        ).occurrences[0]
        assert item.latest_check.status == "CHANGES_DETECTED"

    def test_partial_failure_run_maps_to_partial_check(self, db_session):
        release, occurrence = _standard_release_occurrence(db_session, "9113")
        _check_run(db_session, occurrence, status="PARTIAL_FAILURE")
        item = ReleaseProcessingReadService().get_processing_status(
            db_session, occurrence_id=occurrence.id, release_id=None, status=None, start_date=None, end_date=None, limit=20, offset=0
        ).occurrences[0]
        assert item.latest_check.status == "PARTIAL_CHECK"

    def test_failed_provider_run_maps_to_check_failed(self, db_session):
        release, occurrence = _standard_release_occurrence(db_session, "9114")
        _check_run(db_session, occurrence, status="FAILED_PROVIDER")
        item = ReleaseProcessingReadService().get_processing_status(
            db_session, occurrence_id=occurrence.id, release_id=None, status=None, start_date=None, end_date=None, limit=20, offset=0
        ).occurrences[0]
        assert item.latest_check.status == "CHECK_FAILED"


class TestRetryHistoryPreservation:
    """The central reason #19B exists: a later NO_CHANGE run's own
    absence of new rows must never erase an earlier run's detected
    changes from the response."""

    def test_changed_then_no_change_retry_still_shows_the_original_detected_changes(self, db_session):
        release, occurrence = _standard_release_occurrence(db_session, "9120")
        first_run = _check_run(db_session, occurrence, status="CHANGED", completed_at=datetime(2026, 7, 1, tzinfo=timezone.utc))
        _observation_update(db_session, first_run, detected_at=datetime(2026, 7, 1, tzinfo=timezone.utc))
        _analysis_update(db_session, first_run)

        second_run = _check_run(db_session, occurrence, status="NO_CHANGE", completed_at=datetime(2026, 7, 2, tzinfo=timezone.utc))
        # second_run deliberately has no observation/analysis rows -- a
        # genuine repeat check that found nothing new.

        item = ReleaseProcessingReadService().get_processing_status(
            db_session, occurrence_id=occurrence.id, release_id=None, status=None, start_date=None, end_date=None, limit=20, offset=0
        ).occurrences[0]

        assert item.latest_check.status == "NO_CHANGE"
        assert item.latest_check.checked_at == second_run.completed_at
        assert len(item.detected_observation_changes) == 1
        assert len(item.detected_analysis_changes) == 1

    def test_failed_then_changed_retry_shows_changes_detected_and_the_real_changes(self, db_session):
        release, occurrence = _standard_release_occurrence(db_session, "9121")
        _check_run(db_session, occurrence, status="FAILED_PROVIDER", completed_at=datetime(2026, 7, 1, tzinfo=timezone.utc))

        second_run = _check_run(db_session, occurrence, status="CHANGED", completed_at=datetime(2026, 7, 2, tzinfo=timezone.utc))
        _observation_update(db_session, second_run, detected_at=datetime(2026, 7, 2, tzinfo=timezone.utc))

        item = ReleaseProcessingReadService().get_processing_status(
            db_session, occurrence_id=occurrence.id, release_id=None, status=None, start_date=None, end_date=None, limit=20, offset=0
        ).occurrences[0]

        assert item.latest_check.status == "CHANGES_DETECTED"
        assert len(item.detected_observation_changes) == 1


class TestObservationAndAnalysisContract:
    def test_observation_without_any_analysis_change_is_a_valid_result(self, db_session):
        release, occurrence = _standard_release_occurrence(db_session, "9130")
        run = _check_run(db_session, occurrence, status="CHANGED")
        _observation_update(db_session, run)
        # No analysis update at all -- a revision that didn't move any
        # canonical value (see test_release_processing_service.py's own
        # equivalent write-side test).

        item = ReleaseProcessingReadService().get_processing_status(
            db_session, occurrence_id=occurrence.id, release_id=None, status=None, start_date=None, end_date=None, limit=20, offset=0
        ).occurrences[0]
        assert len(item.detected_observation_changes) == 1
        assert item.detected_analysis_changes == []

    def test_observation_change_carries_series_metadata_when_available(self, db_session):
        release, occurrence = _standard_release_occurrence(db_session, "9131", series_id="UNRATE")
        db_session.add(EconomicSeries(series_id="UNRATE", title="Unemployment Rate", units="Percent"))
        db_session.flush()
        run = _check_run(db_session, occurrence, status="CHANGED")
        _observation_update(db_session, run, series_id="UNRATE", change_type="REVISED", previous_value=3.8, new_value=3.9)

        change = ReleaseProcessingReadService().get_processing_status(
            db_session, occurrence_id=occurrence.id, release_id=None, status=None, start_date=None, end_date=None, limit=20, offset=0
        ).occurrences[0].detected_observation_changes[0]

        assert change.series_title == "Unemployment Rate"
        assert change.units == "Percent"
        assert change.change_type == "REVISED"
        assert change.previous_value == 3.8
        assert change.new_value == 3.9

    def test_observation_change_falls_back_to_null_metadata_when_series_row_absent(self, db_session):
        release, occurrence = _standard_release_occurrence(db_session, "9132", series_id="GHOST")
        run = _check_run(db_session, occurrence, status="CHANGED")
        _observation_update(db_session, run, series_id="GHOST")

        change = ReleaseProcessingReadService().get_processing_status(
            db_session, occurrence_id=occurrence.id, release_id=None, status=None, start_date=None, end_date=None, limit=20, offset=0
        ).occurrences[0].detected_observation_changes[0]

        assert change.series_id == "GHOST"
        assert change.series_title is None
        assert change.units is None

    def test_analysis_change_field_shape_and_recorded_at(self, db_session):
        release, occurrence = _standard_release_occurrence(db_session, "9133")
        run = _check_run(db_session, occurrence, status="CHANGED")
        _analysis_update(db_session, run, component="TARGET", event_type="STATE_CHANGED")

        change = ReleaseProcessingReadService().get_processing_status(
            db_session, occurrence_id=occurrence.id, release_id=None, status=None, start_date=None, end_date=None, limit=20, offset=0
        ).occurrences[0].detected_analysis_changes[0]

        assert change.component == "TARGET"
        assert change.event_type == "STATE_CHANGED"
        assert change.previous_value == "2.0"
        assert change.current_value == "2.5"
        assert change.delta == 0.5
        assert change.recorded_at is not None


class TestReleaseContext:
    def test_release_identity_is_inlined_on_each_item(self, db_session):
        release, occurrence = _standard_release_occurrence(db_session, "9140")
        item = ReleaseProcessingReadService().get_processing_status(
            db_session, occurrence_id=occurrence.id, release_id=None, status=None, start_date=None, end_date=None, limit=20, offset=0
        ).occurrences[0]
        assert item.release.release_id == release.id
        assert item.release.name == release.name
        assert item.release.provider == "FRED"
        assert item.release.provider_release_id == "9140"


class TestZeroMappingExclusion:
    def test_occurrence_of_an_unmapped_release_never_appears(self, db_session):
        release = _release(db_session, provider_release_id="9150")
        occurrence = _occurrence(db_session, release, date(2026, 7, 1))
        # No ReleaseSeriesMapping row at all.
        response = ReleaseProcessingReadService().get_processing_status(
            db_session, occurrence_id=occurrence.id, release_id=None, status=None, start_date=None, end_date=None, limit=20, offset=0
        )
        assert response.occurrences == []
        assert response.pagination.total == 0


class TestFilteringAndOrdering:
    def test_filters_by_status(self, db_session):
        release_a, occ_a = _standard_release_occurrence(db_session, "9160", date(2026, 7, 1))
        _check_run(db_session, occ_a, status="NO_CHANGE")
        release_b, occ_b = _standard_release_occurrence(db_session, "9161", date(2026, 7, 2))
        _check_run(db_session, occ_b, status="CHANGED")

        response = ReleaseProcessingReadService().get_processing_status(
            db_session, occurrence_id=None, release_id=None, status="CHANGES_DETECTED", start_date=date(2026, 6, 1), end_date=date(2026, 12, 31), limit=20, offset=0
        )
        occurrence_ids = {item.occurrence_id for item in response.occurrences}
        assert occ_b.id in occurrence_ids
        assert occ_a.id not in occurrence_ids

    def test_orders_by_scheduled_date_descending(self, db_session):
        release, occ_old = _standard_release_occurrence(db_session, "9162", date(2026, 1, 1))
        occ_new = _occurrence(db_session, release, date(2026, 6, 1))

        response = ReleaseProcessingReadService().get_processing_status(
            db_session, occurrence_id=None, release_id=release.id, status=None, start_date=None, end_date=None, limit=20, offset=0
        )
        assert [item.occurrence_id for item in response.occurrences] == [occ_new.id, occ_old.id]

    def test_filters_by_release_id(self, db_session):
        release_a, occ_a = _standard_release_occurrence(db_session, "9163", date(2026, 7, 1))
        release_b, occ_b = _standard_release_occurrence(db_session, "9164", date(2026, 7, 1))

        response = ReleaseProcessingReadService().get_processing_status(
            db_session, occurrence_id=None, release_id=release_a.id, status=None, start_date=None, end_date=None, limit=20, offset=0
        )
        occurrence_ids = {item.occurrence_id for item in response.occurrences}
        assert occ_a.id in occurrence_ids
        assert occ_b.id not in occurrence_ids


class TestPagination:
    def test_total_reflects_the_status_filtered_set_not_the_unfiltered_candidate_count(self, db_session):
        release, occ_a = _standard_release_occurrence(db_session, "9170", date(2026, 7, 1))
        _check_run(db_session, occ_a, status="NO_CHANGE")
        occ_b = _occurrence(db_session, release, date(2026, 7, 2))
        _check_run(db_session, occ_b, status="NO_CHANGE")
        occ_c = _occurrence(db_session, release, date(2026, 7, 3))
        _check_run(db_session, occ_c, status="CHANGED")

        response = ReleaseProcessingReadService().get_processing_status(
            db_session, occurrence_id=None, release_id=release.id, status="NO_CHANGE", start_date=None, end_date=None, limit=20, offset=0
        )
        assert response.pagination.total == 2
        assert response.pagination.returned == 2

    def test_limit_and_offset_slice_the_page(self, db_session):
        release, _occ = _standard_release_occurrence(db_session, "9171", date(2026, 1, 1))
        for month in range(2, 6):
            _occurrence(db_session, release, date(2026, month, 1))

        first_page = ReleaseProcessingReadService().get_processing_status(
            db_session, occurrence_id=None, release_id=release.id, status=None, start_date=None, end_date=None, limit=2, offset=0
        )
        second_page = ReleaseProcessingReadService().get_processing_status(
            db_session, occurrence_id=None, release_id=release.id, status=None, start_date=None, end_date=None, limit=2, offset=2
        )
        assert len(first_page.occurrences) == 2
        assert len(second_page.occurrences) == 2
        assert first_page.pagination.total == 5
        assert second_page.pagination.total == 5
        first_ids = {item.occurrence_id for item in first_page.occurrences}
        second_ids = {item.occurrence_id for item in second_page.occurrences}
        assert first_ids.isdisjoint(second_ids)


class TestValidation:
    def test_start_date_after_end_date_raises(self, db_session):
        with pytest.raises(InvalidDateRangeError):
            ReleaseProcessingReadService().get_processing_status(
                db_session, occurrence_id=None, release_id=None, status=None, start_date=date(2026, 12, 31), end_date=date(2026, 1, 1), limit=20, offset=0
            )


class TestRepeatedDeterminism:
    def test_calling_twice_yields_identical_results(self, db_session):
        release, occurrence = _standard_release_occurrence(db_session, "9180")
        run = _check_run(db_session, occurrence, status="CHANGED")
        _observation_update(db_session, run)
        _analysis_update(db_session, run)

        service = ReleaseProcessingReadService()
        first = service.get_processing_status(
            db_session, occurrence_id=occurrence.id, release_id=None, status=None, start_date=None, end_date=None, limit=20, offset=0
        )
        second = service.get_processing_status(
            db_session, occurrence_id=occurrence.id, release_id=None, status=None, start_date=None, end_date=None, limit=20, offset=0
        )
        assert first.model_dump() == second.model_dump()
