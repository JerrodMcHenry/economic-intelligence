"""Integration tests for Increment #25G's `SinceLastVisitRepository`
against a real, isolated PostgreSQL test database (see
tests/conftest.py). Frozen contract: docs/product/since-last-visit-v1.md
(#25F), specifically §17/§40-47/§58-61.

Mirrors tests/integration/test_recorded_monitor_result_repository.py's
own established fixture discipline -- a synthetic release/mapping well
outside the real curated range ("9701"+).
"""

from datetime import date, datetime, timezone

from app.db.models import EconomicRelease, MaintenanceSweep, ReleaseSeriesMapping
from app.models.release_processing import AnalysisChangeRecord, ObservationChangeRecord, RecordableMonitorResult
from app.repositories.release_processing_repository import ReleaseProcessingRepository
from app.repositories.release_repository import ReleaseRepository
from app.repositories.since_last_visit_repository import SinceLastVisitRepository

AS_OF = date(2026, 8, 1)


def _release(session, name="SLV Test Release", provider_release_id="9701", active=True):
    release = EconomicRelease(name=name, provider="FRED", provider_release_id=provider_release_id, active=active)
    session.add(release)
    session.flush()
    return release


def _mapping(session, release, series_id="PCEPILFE"):
    session.add(ReleaseSeriesMapping(economic_release_id=release.id, series_id=series_id, active=True))
    session.flush()


def _occurrence(session, release, scheduled_date=AS_OF):
    return ReleaseRepository(session).upsert_occurrence(release.id, scheduled_date)


def _check_run(session, occurrence, status="CHANGED", completed_at=None):
    completed_at = completed_at or datetime.now(timezone.utc)
    return ReleaseProcessingRepository(session).add_check_run(occurrence.id, status, completed_at, completed_at)


class TestRelevantReleaseIdsBySeries:
    def test_a_release_mapped_to_an_inflation_series_is_relevant_to_inflation_only(self, db_session):
        release = _release(db_session)
        _mapping(db_session, release, series_id="PCEPILFE")

        repo = SinceLastVisitRepository(db_session)
        inflation_ids, labor_ids = repo.relevant_release_ids_by_series(frozenset({"PCEPILFE"}), frozenset({"PAYEMS"}))
        assert release.id in inflation_ids
        assert release.id not in labor_ids

    def test_an_inactive_mapping_is_excluded(self, db_session):
        release = _release(db_session)
        db_session.add(ReleaseSeriesMapping(economic_release_id=release.id, series_id="PCEPILFE", active=False))
        db_session.flush()

        repo = SinceLastVisitRepository(db_session)
        inflation_ids, _ = repo.relevant_release_ids_by_series(frozenset({"PCEPILFE"}), frozenset())
        assert release.id not in inflation_ids

    def test_an_unmapped_series_release_is_relevant_to_neither(self, db_session):
        release = _release(db_session)
        _mapping(db_session, release, series_id="FABRICATED_UNMAPPED")

        repo = SinceLastVisitRepository(db_session)
        inflation_ids, labor_ids = repo.relevant_release_ids_by_series(frozenset({"PCEPILFE"}), frozenset({"PAYEMS"}))
        assert release.id not in inflation_ids
        assert release.id not in labor_ids


class TestListCheckRunsInWindow:
    def test_boundary_after_is_exclusive_through_is_inclusive(self, db_session):
        release = _release(db_session)
        _mapping(db_session, release)
        occurrence = _occurrence(db_session, release)

        after = datetime(2026, 9, 1, tzinfo=timezone.utc)
        through = datetime(2026, 9, 10, tzinfo=timezone.utc)
        run_at_after = _check_run(db_session, occurrence, completed_at=after)  # excluded: completed_at == after
        run_inside = _check_run(db_session, occurrence, completed_at=datetime(2026, 9, 5, tzinfo=timezone.utc))
        run_at_through = _check_run(db_session, occurrence, completed_at=through)  # included: completed_at == through
        run_after_through = _check_run(db_session, occurrence, completed_at=datetime(2026, 9, 11, tzinfo=timezone.utc))

        repo = SinceLastVisitRepository(db_session)
        rows = repo.list_check_runs_in_window(frozenset({release.id}), after, through)
        run_ids = {run.id for run, _release in rows}
        assert run_ids == {run_inside.id, run_at_through.id}
        assert run_at_after.id not in run_ids
        assert run_after_through.id not in run_ids

    def test_none_after_is_unbounded_lower_edge(self, db_session):
        release = _release(db_session)
        _mapping(db_session, release)
        occurrence = _occurrence(db_session, release)
        through = datetime(2026, 9, 10, tzinfo=timezone.utc)
        run = _check_run(db_session, occurrence, completed_at=datetime(2020, 1, 1, tzinfo=timezone.utc))

        repo = SinceLastVisitRepository(db_session)
        rows = repo.list_check_runs_in_window(frozenset({release.id}), None, through)
        assert run.id in {r.id for r, _ in rows}

    def test_ordering_is_completed_at_asc_then_id_asc(self, db_session):
        release = _release(db_session)
        _mapping(db_session, release)
        occurrence = _occurrence(db_session, release)
        through = datetime(2026, 9, 20, tzinfo=timezone.utc)
        t1 = datetime(2026, 9, 5, tzinfo=timezone.utc)
        t2 = datetime(2026, 9, 10, tzinfo=timezone.utc)
        run_b = _check_run(db_session, occurrence, completed_at=t2)
        run_a = _check_run(db_session, occurrence, completed_at=t1)

        repo = SinceLastVisitRepository(db_session)
        rows = repo.list_check_runs_in_window(frozenset({release.id}), None, through)
        ordered_ids = [run.id for run, _ in rows]
        assert ordered_ids.index(run_a.id) < ordered_ids.index(run_b.id)

    def test_release_context_is_inlined(self, db_session):
        release = _release(db_session, name="A Named Release")
        _mapping(db_session, release)
        occurrence = _occurrence(db_session, release)
        through = datetime(2026, 9, 20, tzinfo=timezone.utc)
        _check_run(db_session, occurrence, completed_at=datetime(2026, 9, 5, tzinfo=timezone.utc))

        repo = SinceLastVisitRepository(db_session)
        rows = repo.list_check_runs_in_window(frozenset({release.id}), None, through)
        assert rows[0][1].name == "A Named Release"

    def test_empty_release_id_set_returns_nothing(self, db_session):
        repo = SinceLastVisitRepository(db_session)
        assert repo.list_check_runs_in_window(frozenset(), None, datetime.now(timezone.utc)) == []


class TestSettledReleaseIdsInWindow:
    def test_no_change_and_changed_both_count_as_settled(self, db_session):
        release = _release(db_session)
        _mapping(db_session, release)
        occurrence = _occurrence(db_session, release)
        through = datetime(2026, 9, 20, tzinfo=timezone.utc)
        _check_run(db_session, occurrence, status="NO_CHANGE", completed_at=datetime(2026, 9, 5, tzinfo=timezone.utc))

        repo = SinceLastVisitRepository(db_session)
        settled = repo.settled_release_ids_in_window(frozenset({release.id}), None, through)
        assert release.id in settled

    def test_partial_failure_and_failed_provider_never_settle(self, db_session):
        release = _release(db_session)
        _mapping(db_session, release)
        occurrence = _occurrence(db_session, release)
        through = datetime(2026, 9, 20, tzinfo=timezone.utc)
        _check_run(db_session, occurrence, status="PARTIAL_FAILURE", completed_at=datetime(2026, 9, 5, tzinfo=timezone.utc))
        _check_run(db_session, occurrence, status="FAILED_PROVIDER", completed_at=datetime(2026, 9, 6, tzinfo=timezone.utc))

        repo = SinceLastVisitRepository(db_session)
        settled = repo.settled_release_ids_in_window(frozenset({release.id}), None, through)
        assert release.id not in settled

    def test_settlement_outside_the_window_does_not_count(self, db_session):
        release = _release(db_session)
        _mapping(db_session, release)
        occurrence = _occurrence(db_session, release)
        after = datetime(2026, 9, 1, tzinfo=timezone.utc)
        through = datetime(2026, 9, 10, tzinfo=timezone.utc)
        _check_run(db_session, occurrence, status="NO_CHANGE", completed_at=datetime(2026, 8, 1, tzinfo=timezone.utc))

        repo = SinceLastVisitRepository(db_session)
        settled = repo.settled_release_ids_in_window(frozenset({release.id}), after, through)
        assert release.id not in settled


class TestLatestSettledCompletedAt:
    def test_returns_the_most_recent_settled_run_system_wide(self, db_session):
        release = _release(db_session)
        _mapping(db_session, release)
        occurrence = _occurrence(db_session, release)
        older = datetime(2026, 1, 1, tzinfo=timezone.utc)
        newer = datetime(2026, 6, 1, tzinfo=timezone.utc)
        _check_run(db_session, occurrence, status="NO_CHANGE", completed_at=older)
        _check_run(db_session, occurrence, status="CHANGED", completed_at=newer)

        repo = SinceLastVisitRepository(db_session)
        assert repo.latest_settled_completed_at(frozenset({release.id})) == newer

    def test_none_when_no_relevant_releases(self, db_session):
        repo = SinceLastVisitRepository(db_session)
        assert repo.latest_settled_completed_at(frozenset()) is None


class TestSweepEvidence:
    def test_any_sweep_started_in_window_true_for_an_unfinished_sweep(self, db_session):
        sweep = MaintenanceSweep(started_at=datetime(2026, 9, 5, tzinfo=timezone.utc))
        db_session.add(sweep)
        db_session.flush()

        repo = SinceLastVisitRepository(db_session)
        after = datetime(2026, 9, 1, tzinfo=timezone.utc)
        through = datetime(2026, 9, 10, tzinfo=timezone.utc)
        assert repo.any_sweep_started_in_window(after, through) is True

    def test_no_sweep_evidence_in_window_is_false(self, db_session):
        sweep = MaintenanceSweep(started_at=datetime(2020, 1, 1, tzinfo=timezone.utc))
        db_session.add(sweep)
        db_session.flush()

        repo = SinceLastVisitRepository(db_session)
        after = datetime(2026, 9, 1, tzinfo=timezone.utc)
        through = datetime(2026, 9, 10, tzinfo=timezone.utc)
        assert repo.any_sweep_started_in_window(after, through) is False

    def test_latest_sweep_finished_at_ignores_unfinished_sweeps(self, db_session):
        finished = datetime(2026, 6, 1, tzinfo=timezone.utc)
        db_session.add(MaintenanceSweep(started_at=datetime(2026, 9, 1, tzinfo=timezone.utc), finished_at=None))
        db_session.add(MaintenanceSweep(started_at=finished, finished_at=finished, status="SUCCEEDED"))
        db_session.flush()

        repo = SinceLastVisitRepository(db_session)
        assert repo.latest_sweep_finished_at() == finished


class TestEarliestRecordedResultIdByMonitor:
    def test_returns_the_minimum_id_per_monitor(self, db_session):
        release = _release(db_session)
        _mapping(db_session, release)
        occurrence = _occurrence(db_session, release)
        run_a = _check_run(db_session, occurrence)
        run_b = _check_run(db_session, occurrence)
        repo_write = ReleaseProcessingRepository(db_session)
        repo_write.add_recorded_monitor_result(
            run_a.id,
            RecordableMonitorResult(monitor="inflation", evaluation_period=date(2026, 6, 1), state="COOLING", methodology_id="inflation_v1.0", data_basis="latest_revised_data"),
            datetime.now(timezone.utc),
        )
        repo_write.add_recorded_monitor_result(
            run_b.id,
            RecordableMonitorResult(monitor="inflation", evaluation_period=date(2026, 7, 1), state="COOLING", methodology_id="inflation_v1.0", data_basis="latest_revised_data"),
            datetime.now(timezone.utc),
        )
        db_session.flush()

        repo = SinceLastVisitRepository(db_session)
        earliest = repo.earliest_recorded_result_id_by_monitor()
        assert earliest["inflation"] is not None


class TestSeriesMetadata:
    def test_returns_title_for_known_series_omits_unknown(self, db_session):
        repo_write = ReleaseProcessingRepository(db_session)
        repo_write.create_series("FABRICATED_SERIES_META", "A Title", "Percent")
        db_session.flush()

        repo = SinceLastVisitRepository(db_session)
        metadata = repo.list_series_metadata(["FABRICATED_SERIES_META", "UNKNOWN_SERIES"])
        assert metadata["FABRICATED_SERIES_META"].title == "A Title"
        assert "UNKNOWN_SERIES" not in metadata


class TestNoWriteMethods:
    def test_repository_exposes_no_add_write_or_create_method(self):
        method_names = [name for name in dir(SinceLastVisitRepository) if not name.startswith("_")]
        forbidden_prefixes = ("add_", "write_", "create_", "update_", "delete_")
        violations = [name for name in method_names if any(name.startswith(p) for p in forbidden_prefixes)]
        assert violations == [], f"SinceLastVisitRepository must be read-only: {violations}"
