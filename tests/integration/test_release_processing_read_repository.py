"""Integration tests for ReleaseProcessingReadRepository against a
real, isolated PostgreSQL test database (see tests/conftest.py). No
FastAPI, no FRED, no AI -- this repository has no dependency on any of
them.

Every test uses a synthetic release/mapping/series with a
provider_release_id well outside the real curated range ("9001"+),
mirroring tests/integration/test_release_processing_repository.py's
own discipline, so nothing here depends on or disturbs the
migration-seeded CPI/Personal Income and Outlays catalog.
"""

from datetime import date, datetime, timezone

import pytest
import sqlalchemy as sa

from app.db.models import EconomicRelease, EconomicSeries, ReleaseAnalysisUpdate, ReleaseCheckRun, ReleaseObservationUpdate, ReleaseSeriesMapping
from app.repositories.release_processing_read_repository import ReleaseProcessingReadRepository
from app.repositories.release_repository import ReleaseRepository

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


def _check_run(session, occurrence, status="NO_CHANGE", started_at=NOW, completed_at=NOW):
    run = ReleaseCheckRun(release_occurrence_id=occurrence.id, status=status, started_at=started_at, completed_at=completed_at)
    session.add(run)
    session.flush()
    return run


def _observation_update(session, run, series_id="UNRATE", observation_date=date(2026, 7, 1), change_type="NEW", detected_at=NOW):
    update = ReleaseObservationUpdate(
        release_check_run_id=run.id,
        series_id=series_id,
        observation_date=observation_date,
        change_type=change_type,
        previous_value=None,
        new_value=3.9,
        detected_at=detected_at,
    )
    session.add(update)
    session.flush()
    return update


def _analysis_update(session, run, evaluation_period=date(2026, 7, 1)):
    update = ReleaseAnalysisUpdate(
        release_check_run_id=run.id,
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
    session.flush()
    return update


class TestListMappedOccurrences:
    def test_excludes_occurrence_of_a_release_with_zero_active_mappings(self, db_session):
        release = _release(db_session)
        occurrence = _occurrence(db_session, release, date(2026, 7, 1))
        # No mapping at all for this release.
        repo = ReleaseProcessingReadRepository(db_session)
        results = repo.list_mapped_occurrences()
        assert occurrence.id not in {occ.id for occ, _rel in results}

    def test_excludes_occurrence_of_a_release_whose_only_mapping_is_inactive(self, db_session):
        release = _release(db_session, provider_release_id="9002")
        _mapping(db_session, release, active=False)
        occurrence = _occurrence(db_session, release, date(2026, 7, 1))
        repo = ReleaseProcessingReadRepository(db_session)
        results = repo.list_mapped_occurrences()
        assert occurrence.id not in {occ.id for occ, _rel in results}

    def test_includes_occurrence_of_a_release_with_an_active_mapping(self, db_session):
        release = _release(db_session, provider_release_id="9003")
        _mapping(db_session, release)
        occurrence = _occurrence(db_session, release, date(2026, 7, 1))
        repo = ReleaseProcessingReadRepository(db_session)
        results = repo.list_mapped_occurrences()
        assert occurrence.id in {occ.id for occ, _rel in results}

    def test_filters_by_occurrence_id(self, db_session):
        release = _release(db_session, provider_release_id="9004")
        _mapping(db_session, release)
        occ1 = _occurrence(db_session, release, date(2026, 7, 1))
        occ2 = _occurrence(db_session, release, date(2026, 8, 1))
        repo = ReleaseProcessingReadRepository(db_session)
        results = repo.list_mapped_occurrences(occurrence_id=occ1.id)
        assert [occ.id for occ, _rel in results] == [occ1.id]
        assert occ2.id not in [occ.id for occ, _rel in results]

    def test_filters_by_release_id(self, db_session):
        release_a = _release(db_session, provider_release_id="9005")
        release_b = _release(db_session, provider_release_id="9006")
        _mapping(db_session, release_a)
        _mapping(db_session, release_b)
        occ_a = _occurrence(db_session, release_a, date(2026, 7, 1))
        occ_b = _occurrence(db_session, release_b, date(2026, 7, 1))
        repo = ReleaseProcessingReadRepository(db_session)
        results = repo.list_mapped_occurrences(release_id=release_a.id)
        occ_ids = {occ.id for occ, _rel in results}
        assert occ_a.id in occ_ids
        assert occ_b.id not in occ_ids

    def test_filters_by_date_range(self, db_session):
        release = _release(db_session, provider_release_id="9007")
        _mapping(db_session, release)
        occ_in = _occurrence(db_session, release, date(2026, 7, 1))
        occ_out = _occurrence(db_session, release, date(2020, 1, 1))
        repo = ReleaseProcessingReadRepository(db_session)
        results = repo.list_mapped_occurrences(start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
        occ_ids = {occ.id for occ, _rel in results}
        assert occ_in.id in occ_ids
        assert occ_out.id not in occ_ids

    def test_orders_by_scheduled_date_descending(self, db_session):
        release = _release(db_session, provider_release_id="9008")
        _mapping(db_session, release)
        older = _occurrence(db_session, release, date(2026, 1, 1))
        newer = _occurrence(db_session, release, date(2026, 6, 1))
        repo = ReleaseProcessingReadRepository(db_session)
        results = repo.list_mapped_occurrences(release_id=release.id)
        assert [occ.id for occ, _rel in results] == [newer.id, older.id]


class TestListCheckRunsForOccurrences:
    def test_empty_occurrence_id_list_returns_empty(self, db_session):
        assert ReleaseProcessingReadRepository(db_session).list_check_runs_for_occurrences([]) == []

    def test_returns_runs_ordered_completed_at_desc(self, db_session):
        release = _release(db_session, provider_release_id="9010")
        _mapping(db_session, release)
        occurrence = _occurrence(db_session, release, date(2026, 7, 1))
        earlier = _check_run(db_session, occurrence, completed_at=datetime(2026, 7, 1, tzinfo=timezone.utc))
        later = _check_run(db_session, occurrence, completed_at=datetime(2026, 7, 2, tzinfo=timezone.utc))
        runs = ReleaseProcessingReadRepository(db_session).list_check_runs_for_occurrences([occurrence.id])
        assert [r.id for r in runs] == [later.id, earlier.id]

    def test_tie_break_by_id_desc_when_completed_at_matches(self, db_session):
        release = _release(db_session, provider_release_id="9011")
        _mapping(db_session, release)
        occurrence = _occurrence(db_session, release, date(2026, 7, 1))
        first = _check_run(db_session, occurrence, completed_at=NOW)
        second = _check_run(db_session, occurrence, completed_at=NOW)
        runs = ReleaseProcessingReadRepository(db_session).list_check_runs_for_occurrences([occurrence.id])
        assert [r.id for r in runs] == [second.id, first.id]


class TestListObservationAndAnalysisUpdatesForRuns:
    def test_empty_run_id_list_returns_empty(self, db_session):
        repo = ReleaseProcessingReadRepository(db_session)
        assert repo.list_observation_updates_for_runs([]) == []
        assert repo.list_analysis_updates_for_runs([]) == []

    def test_observation_updates_ordered_detected_at_desc(self, db_session):
        release = _release(db_session, provider_release_id="9012")
        _mapping(db_session, release)
        occurrence = _occurrence(db_session, release, date(2026, 7, 1))
        run = _check_run(db_session, occurrence)
        earlier = _observation_update(db_session, run, observation_date=date(2026, 6, 1), detected_at=datetime(2026, 7, 1, tzinfo=timezone.utc))
        later = _observation_update(db_session, run, observation_date=date(2026, 7, 1), detected_at=datetime(2026, 7, 2, tzinfo=timezone.utc))
        updates = ReleaseProcessingReadRepository(db_session).list_observation_updates_for_runs([run.id])
        assert [u.id for u in updates] == [later.id, earlier.id]

    def test_analysis_updates_ordered_created_at_desc(self, db_session):
        release = _release(db_session, provider_release_id="9013")
        _mapping(db_session, release)
        occurrence = _occurrence(db_session, release, date(2026, 7, 1))
        run = _check_run(db_session, occurrence)
        first = _analysis_update(db_session, run, evaluation_period=date(2026, 6, 1))
        second = _analysis_update(db_session, run, evaluation_period=date(2026, 7, 1))
        updates = ReleaseProcessingReadRepository(db_session).list_analysis_updates_for_runs([run.id])
        # created_at is server-default `func.now()` for both, inserted in
        # the same transaction -- ordering falls back to id DESC.
        assert [u.id for u in updates] == [second.id, first.id]


class TestListSeriesMetadata:
    def test_empty_series_id_list_returns_empty_dict(self, db_session):
        assert ReleaseProcessingReadRepository(db_session).list_series_metadata([]) == {}

    def test_returns_metadata_keyed_by_series_id(self, db_session):
        series = EconomicSeries(series_id="UNRATE", title="Unemployment Rate", units="Percent")
        db_session.add(series)
        db_session.flush()
        result = ReleaseProcessingReadRepository(db_session).list_series_metadata(["UNRATE"])
        assert result["UNRATE"].title == "Unemployment Rate"
        assert result["UNRATE"].units == "Percent"

    def test_series_id_with_no_matching_row_is_simply_absent(self, db_session):
        result = ReleaseProcessingReadRepository(db_session).list_series_metadata(["DOES_NOT_EXIST"])
        assert "DOES_NOT_EXIST" not in result
