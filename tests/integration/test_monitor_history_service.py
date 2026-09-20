"""Integration tests for point-in-time intelligence history
(Increment #32).

The property under test is that the product surface stays HONEST under
conditions the local development database cannot currently produce: a
genuine provider revision, a recorded conclusion that no longer
reproduces, a methodology version this binary does not implement, and a
result with no usable version history at all.

Those states are constructed here rather than by mutating real data --
a scenario that only exists because the fixture forced it is still a
real test of the code, whereas corrupting a development database to
photograph it is neither.
"""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.db.models import EconomicRelease, EconomicSeries, RecordedMonitorResult, ReleaseCheckRun, ReleaseObservationUpdate, ReleaseOccurrence
from app.domain.inflation import compute_series_momentum_at
from app.models.inflation import METHODOLOGY_ID as INFLATION_METHODOLOGY_ID, PRIMARY_SERIES_ID
from app.models.labor import METHODOLOGY_ID as LABOR_METHODOLOGY_ID, PAYEMS_SERIES_ID, UNRATE_SERIES_ID
from app.models.series import Observation
from app.repositories.observation_versions import ORIGIN_RELEASE_PROCESSING, ObservationVersionWriter
from app.services.monitor_history import MonitorHistoryService, RecordedResultNotFoundError

pytestmark = pytest.mark.integration

CALCULATED_AT = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
BEFORE = CALCULATED_AT - timedelta(days=30)
AFTER = CALCULATED_AT + timedelta(days=30)
PERIOD = date(2026, 3, 1)


def _month(anchor: date, months_back: int) -> date:
    year, month = anchor.year, anchor.month - months_back
    while month <= 0:
        year -= 1
        month += 12
    return date(year, month, 1)


def _series(session, series_id: str) -> EconomicSeries:
    existing = session.execute(select(EconomicSeries).where(EconomicSeries.series_id == series_id)).scalar_one_or_none()
    if existing is not None:
        return existing
    series = EconomicSeries(series_id=series_id, title=series_id, units="Index", source="FRED")
    session.add(series)
    session.flush()
    return series


def _seed_versioned(session, series_id: str, values: dict[date, float], at: datetime) -> EconomicSeries:
    series = _series(session, series_id)
    writer = ObservationVersionWriter(session, recorded_at=at, origin=ORIGIN_RELEASE_PROCESSING)
    for observation_date, value in sorted(values.items()):
        writer.apply(series, observation_date, value)
    session.flush()
    return series


def _check_run(session, calculated_at: datetime) -> ReleaseCheckRun:
    """Several runs per test are normal (one per recorded calculation),
    so the owning release is get-or-create rather than inserted afresh
    -- `(provider, provider_release_id)` is unique."""
    release = session.execute(
        select(EconomicRelease).where(EconomicRelease.provider == "FRED", EconomicRelease.provider_release_id == "9999")
    ).scalar_one_or_none()
    if release is None:
        release = EconomicRelease(name="Test Release", provider="FRED", provider_release_id="9999", active=True)
        session.add(release)
        session.flush()
    # One occurrence, several check runs -- the real shape of a retry,
    # and `(release, scheduled_date)` is unique.
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
        release_occurrence_id=occurrence.id, status="CHANGED", started_at=calculated_at, completed_at=calculated_at
    )
    session.add(run)
    session.flush()
    return run


def _recorded(
    session,
    monitor: str,
    state: str,
    methodology_id: str,
    calculated_at: datetime = CALCULATED_AT,
    period: date = PERIOD,
    run: ReleaseCheckRun | None = None,
) -> RecordedMonitorResult:
    run = run or _check_run(session, calculated_at)
    recorded = RecordedMonitorResult(
        release_check_run_id=run.id,
        monitor=monitor,
        evaluation_period=period,
        state=state,
        methodology_id=methodology_id,
        data_basis="latest_revised_data",
        calculated_at=calculated_at,
    )
    session.add(recorded)
    session.flush()
    return recorded


def _core_pce_history(anchor: date, months: int = 14, growth: float = 0.002) -> dict[date, float]:
    return {_month(anchor, n): 120.0 * ((1 + growth) ** (months - n)) for n in range(months)}


def _state_for(history: dict[date, float], period: date = PERIOD) -> str:
    """What the methodology genuinely concludes -- so tests assert
    reproduction rather than a hard-coded state the frozen methodology
    may not actually produce."""
    return compute_series_momentum_at(
        [Observation(date=d, value=v) for d, v in sorted(history.items())], PRIMARY_SERIES_ID, period
    ).state


@pytest.fixture
def service() -> MonitorHistoryService:
    return MonitorHistoryService()


class TestHistoryListing:
    def test_entries_are_newest_first_with_a_deterministic_tiebreak(self, db_session, service):
        """Every result one run writes shares a `calculated_at`
        verbatim, so ordering must not depend on it alone."""
        run = _check_run(db_session, CALCULATED_AT)
        for period in (date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)):
            _recorded(db_session, "inflation", "COOLING", INFLATION_METHODOLOGY_ID, period=period, run=run)
        older = _recorded(db_session, "inflation", "HEATING", INFLATION_METHODOLOGY_ID, calculated_at=BEFORE)

        response = service.get_history(db_session, "inflation", limit=20, offset=0)
        entries = response.entries

        # Recency wins first, so the genuinely older calculation is last
        # even though its row id is the highest.
        assert [entry.calculated_at for entry in entries] == sorted(
            (entry.calculated_at for entry in entries), reverse=True
        )
        assert entries[-1].recorded_result_id == older.id
        # Within one shared `calculated_at`, the id tiebreak gives a
        # total order -- otherwise paging could repeat or skip a row.
        same_instant = [e.recorded_result_id for e in entries if e.calculated_at == CALCULATED_AT]
        assert same_instant == sorted(same_instant, reverse=True)

    def test_pagination_reports_total_before_the_page_and_does_not_overlap(self, db_session, service):
        for period in (date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1), date(2026, 4, 1)):
            _recorded(db_session, "labor", "MIXED", LABOR_METHODOLOGY_ID, period=period)

        first = service.get_history(db_session, "labor", limit=2, offset=0)
        second = service.get_history(db_session, "labor", limit=2, offset=2)

        assert first.pagination.total == 4
        assert first.pagination.returned == 2
        assert first.pagination.limit == 2 and first.pagination.offset == 0
        first_ids = {entry.recorded_result_id for entry in first.entries}
        second_ids = {entry.recorded_result_id for entry in second.entries}
        assert not (first_ids & second_ids)

    def test_a_monitor_with_no_recorded_results_is_an_empty_page_not_an_error(self, db_session, service):
        response = service.get_history(db_session, "inflation", limit=20, offset=0)
        assert response.entries == []
        assert response.pagination.total == 0

    def test_one_monitors_history_never_contains_another_monitors_results(self, db_session, service):
        _recorded(db_session, "labor", "MIXED", LABOR_METHODOLOGY_ID)
        _recorded(db_session, "inflation", "COOLING", INFLATION_METHODOLOGY_ID)

        response = service.get_history(db_session, "inflation", limit=20, offset=0)
        assert [entry.monitor for entry in response.entries] == ["inflation"]


class TestPreviousResultSemantics:
    def test_a_different_month_classified_differently_is_not_a_changed_opinion(self, db_session, service):
        run = _check_run(db_session, CALCULATED_AT)
        _recorded(db_session, "inflation", "HEATING", INFLATION_METHODOLOGY_ID, period=date(2026, 2, 1), run=run)
        _recorded(db_session, "inflation", "COOLING", INFLATION_METHODOLOGY_ID, period=date(2026, 3, 1), run=run)

        latest = service.get_history(db_session, "inflation", limit=20, offset=0).entries[0]

        assert latest.previous is not None
        assert latest.previous.state == "HEATING"
        assert latest.previous.state_changed is True
        assert latest.previous.same_evaluation_period is False

    def test_a_revised_conclusion_about_the_same_month_is_marked_as_such(self, db_session, service):
        _recorded(db_session, "inflation", "HEATING", INFLATION_METHODOLOGY_ID, calculated_at=BEFORE)
        _recorded(db_session, "inflation", "COOLING", INFLATION_METHODOLOGY_ID, calculated_at=CALCULATED_AT)

        latest = service.get_history(db_session, "inflation", limit=20, offset=0).entries[0]

        assert latest.previous is not None
        assert latest.previous.same_evaluation_period is True
        assert latest.previous.state_changed is True

    def test_the_oldest_entry_has_no_previous(self, db_session, service):
        _recorded(db_session, "labor", "MIXED", LABOR_METHODOLOGY_ID)
        entries = service.get_history(db_session, "labor", limit=20, offset=0).entries
        assert entries[-1].previous is None


class TestReplayPresentation:
    def test_a_reproducible_result_reports_match(self, db_session, service):
        history = _core_pce_history(PERIOD)
        _seed_versioned(db_session, PRIMARY_SERIES_ID, history, BEFORE)
        recorded = _recorded(db_session, "inflation", _state_for(history), INFLATION_METHODOLOGY_ID)

        entry = service.get_history_detail(db_session, "inflation", recorded.id).recorded

        assert entry.replay.outcome == "MATCH"
        assert entry.replay.replayed_state == entry.state

    def test_a_recorded_state_that_no_longer_reproduces_reports_mismatch(self, db_session, service):
        """A MISMATCH is an integrity finding and must reach the surface
        intact -- never normalized into "unverified"."""
        history = _core_pce_history(PERIOD)
        _seed_versioned(db_session, PRIMARY_SERIES_ID, history, BEFORE)
        genuine = _state_for(history)
        wrong = "HEATING" if genuine != "HEATING" else "COOLING"
        recorded = _recorded(db_session, "inflation", wrong, INFLATION_METHODOLOGY_ID)

        entry = service.get_history_detail(db_session, "inflation", recorded.id).recorded

        assert entry.replay.outcome == "MISMATCH"
        assert entry.state == wrong
        assert entry.replay.replayed_state == genuine
        assert entry.replay.replayed_state != entry.state

    def test_a_result_with_no_usable_version_history_is_not_replayable(self, db_session, service):
        """Versions recorded only AFTER the calculation cannot honestly
        answer for it, and the surface says so rather than recomputing
        from whatever exists."""
        _seed_versioned(db_session, PRIMARY_SERIES_ID, _core_pce_history(PERIOD), AFTER)
        recorded = _recorded(db_session, "inflation", "COOLING", INFLATION_METHODOLOGY_ID)

        entry = service.get_history_detail(db_session, "inflation", recorded.id).recorded

        assert entry.replay.outcome == "NOT_REPLAYABLE"
        assert entry.replay.reason == "VERSION_HISTORY_STARTS_AFTER_CALCULATION"
        assert entry.replay.replayed_state is None, "a failed replay must not echo the recorded state back"

    def test_not_replayable_yields_no_historical_inputs_but_still_reports_today(self, db_session, service):
        _seed_versioned(db_session, PRIMARY_SERIES_ID, _core_pce_history(PERIOD), AFTER)
        recorded = _recorded(db_session, "inflation", "COOLING", INFLATION_METHODOLOGY_ID)

        detail = service.get_history_detail(db_session, "inflation", recorded.id)

        assert detail.historical_inputs == []
        assert detail.current_comparison.status == "NOT_COMPARABLE"
        assert detail.current_comparison.reason == "REPLAY_UNAVAILABLE"
        # Today's reconstruction stands on its own and is still useful.
        assert detail.current_comparison.current_state is not None


class TestHistoricalInputs:
    def test_inputs_are_exactly_the_exact_months_the_methodology_used(self, db_session, service):
        """`inflation_v1.0` resolves t, t-1, t-3, t-6 and t-12 by exact
        calendar lookup, so the input list is those five months -- not a
        window this feature invented."""
        history = _core_pce_history(PERIOD)
        _seed_versioned(db_session, PRIMARY_SERIES_ID, history, BEFORE)
        recorded = _recorded(db_session, "inflation", _state_for(history), INFLATION_METHODOLOGY_ID)

        inputs = service.get_history_detail(db_session, "inflation", recorded.id).historical_inputs

        assert {row.observation_date for row in inputs} == {
            PERIOD,
            _month(PERIOD, 1),
            _month(PERIOD, 3),
            _month(PERIOD, 6),
            _month(PERIOD, 12),
        }
        assert {row.series_id for row in inputs} == {PRIMARY_SERIES_ID}

    def test_backfilled_inputs_are_disclosed_per_observation(self, db_session, service):
        history = _core_pce_history(PERIOD)
        series = _series(db_session, PRIMARY_SERIES_ID)
        writer = ObservationVersionWriter(db_session, recorded_at=BEFORE, origin="BACKFILL")
        for observation_date, value in sorted(history.items()):
            writer.apply(series, observation_date, value)
        db_session.flush()
        db_session.execute(
            RecordedMonitorResult.__table__.metadata.tables["observation_versions"]
            .update()
            .values(is_backfilled=True)
        )
        recorded = _recorded(db_session, "inflation", _state_for(history), INFLATION_METHODOLOGY_ID)

        detail = service.get_history_detail(db_session, "inflation", recorded.id)

        assert detail.recorded.replay.inputs_include_backfilled is True
        assert all(row.is_backfilled for row in detail.historical_inputs)

    def test_labor_inputs_carry_the_methodologys_own_units_not_the_providers(self, db_session, service):
        """PAYEMS is persisted in FRED-native thousands but `labor_v1.0`
        reports evidence in actual jobs. Both sides of the comparison
        must speak the same unit, or every input reads as revised by a
        factor of 1,000."""
        payems = {_month(PERIOD, n): 158_000.0 + 50.0 * (20 - n) for n in range(20)}
        unrate = {_month(PERIOD, n): 4.0 for n in range(20)}
        _seed_versioned(db_session, PAYEMS_SERIES_ID, payems, BEFORE)
        _seed_versioned(db_session, UNRATE_SERIES_ID, unrate, BEFORE)
        recorded = _recorded(db_session, "labor", "MIXED", LABOR_METHODOLOGY_ID)

        inputs = service.get_history_detail(db_session, "labor", recorded.id).historical_inputs
        payems_rows = [row for row in inputs if row.series_id == PAYEMS_SERIES_ID]
        unrate_rows = [row for row in inputs if row.series_id == UNRATE_SERIES_ID]

        assert {row.value_unit for row in payems_rows} == {"JOBS"}
        assert {row.value_unit for row in unrate_rows} == {"PERCENT"}
        assert all(row.comparison == "UNCHANGED" for row in inputs), "no data changed, so nothing may read as revised"
        assert all(row.value_then is not None and row.value_then > 1_000_000 for row in payems_rows)


class TestCurrentComparison:
    def test_unchanged_data_reports_identical_inputs(self, db_session, service):
        history = _core_pce_history(PERIOD)
        _seed_versioned(db_session, PRIMARY_SERIES_ID, history, BEFORE)
        recorded = _recorded(db_session, "inflation", _state_for(history), INFLATION_METHODOLOGY_ID)

        comparison = service.get_history_detail(db_session, "inflation", recorded.id).current_comparison

        assert comparison.status == "IDENTICAL_INPUTS"
        assert comparison.changed_input_count == 0
        assert comparison.state_differs is False
        assert comparison.methodology_differs is False

    def test_a_revision_after_the_calculation_is_reported_as_a_changed_input(self, db_session, service):
        history = _core_pce_history(PERIOD)
        _seed_versioned(db_session, PRIMARY_SERIES_ID, history, BEFORE)
        recorded = _recorded(db_session, "inflation", _state_for(history), INFLATION_METHODOLOGY_ID)

        # The provider revises the evaluation month AFTER the recorded
        # calculation -- invisible to replay, visible to "today".
        revised_value = history[PERIOD] * 1.02
        _seed_versioned(db_session, PRIMARY_SERIES_ID, {PERIOD: revised_value}, AFTER)

        detail = service.get_history_detail(db_session, "inflation", recorded.id)
        comparison = detail.current_comparison
        revised_rows = [row for row in detail.historical_inputs if row.comparison == "REVISED"]

        assert comparison.status == "INPUTS_CHANGED"
        assert comparison.changed_input_count == len(revised_rows) == 1
        assert revised_rows[0].observation_date == PERIOD
        assert revised_rows[0].value_then == pytest.approx(history[PERIOD])
        assert revised_rows[0].value_today == pytest.approx(revised_value)

    def test_the_recorded_state_is_never_overwritten_by_the_current_reconstruction(self, db_session, service):
        """The whole point of the distinction: a later revision may
        change what today's data says, and must never change what
        MacroChipz is recorded as having concluded."""
        history = _core_pce_history(PERIOD)
        _seed_versioned(db_session, PRIMARY_SERIES_ID, history, BEFORE)
        recorded_state = _state_for(history)
        recorded = _recorded(db_session, "inflation", recorded_state, INFLATION_METHODOLOGY_ID)
        _seed_versioned(db_session, PRIMARY_SERIES_ID, {PERIOD: history[PERIOD] * 1.10}, AFTER)

        detail = service.get_history_detail(db_session, "inflation", recorded.id)

        assert detail.recorded.state == recorded_state
        assert detail.recorded.replay.outcome == "MATCH", "replay still reproduces from the data known then"

    def test_a_methodology_version_this_binary_cannot_run_is_not_faked(self, db_session, service):
        _seed_versioned(db_session, PRIMARY_SERIES_ID, _core_pce_history(PERIOD), BEFORE)
        recorded = _recorded(db_session, "inflation", "COOLING", "inflation_v0.9")

        detail = service.get_history_detail(db_session, "inflation", recorded.id)
        comparison = detail.current_comparison

        assert comparison.status == "NOT_COMPARABLE"
        assert comparison.reason == "METHODOLOGY_VERSION_DIFFERS"
        assert comparison.methodology_differs is True
        assert comparison.methodology_id_then == "inflation_v0.9"
        assert comparison.methodology_id_today == INFLATION_METHODOLOGY_ID
        assert comparison.current_state is None, "running today's rules would answer a different question"
        assert comparison.state_differs is None, "never defaulted to False, which would read as 'nothing changed'"


class TestRelatedChanges:
    def test_a_new_observation_in_the_same_run_is_reported(self, db_session, service):
        history = _core_pce_history(PERIOD)
        _seed_versioned(db_session, PRIMARY_SERIES_ID, history, BEFORE)
        run = _check_run(db_session, CALCULATED_AT)
        db_session.add(
            ReleaseObservationUpdate(
                release_check_run_id=run.id,
                series_id=PRIMARY_SERIES_ID,
                observation_date=PERIOD,
                change_type="NEW",
                previous_value=None,
                new_value=history[PERIOD],
                detected_at=CALCULATED_AT,
            )
        )
        recorded = _recorded(db_session, "inflation", _state_for(history), INFLATION_METHODOLOGY_ID, run=run)

        related = service.get_history_detail(db_session, "inflation", recorded.id).related_changes

        assert [(row.series_id, row.observation_date, row.change_type) for row in related] == [
            (PRIMARY_SERIES_ID, PERIOD, "NEW")
        ]

    def test_a_revised_observation_in_the_same_run_is_reported_with_both_values(self, db_session, service):
        history = _core_pce_history(PERIOD)
        _seed_versioned(db_session, PRIMARY_SERIES_ID, history, BEFORE)
        run = _check_run(db_session, CALCULATED_AT)
        db_session.add(
            ReleaseObservationUpdate(
                release_check_run_id=run.id,
                series_id=PRIMARY_SERIES_ID,
                observation_date=PERIOD,
                change_type="REVISED",
                previous_value=100.0,
                new_value=history[PERIOD],
                detected_at=CALCULATED_AT,
            )
        )
        recorded = _recorded(db_session, "inflation", _state_for(history), INFLATION_METHODOLOGY_ID, run=run)

        related = service.get_history_detail(db_session, "inflation", recorded.id).related_changes

        assert len(related) == 1
        assert related[0].change_type == "REVISED"
        assert related[0].previous_value == 100.0

    def test_same_run_changes_the_methodology_did_not_use_are_counted_not_listed(self, db_session, service):
        """A bootstrap run can carry years of changes. Attaching all of
        them to every result would be true and useless -- so the
        unrelated remainder is counted, never silently dropped."""
        history = _core_pce_history(PERIOD)
        _seed_versioned(db_session, PRIMARY_SERIES_ID, history, BEFORE)
        run = _check_run(db_session, CALCULATED_AT)
        used_date, unused_date = PERIOD, _month(PERIOD, 2)
        for observation_date in (used_date, unused_date):
            db_session.add(
                ReleaseObservationUpdate(
                    release_check_run_id=run.id,
                    series_id=PRIMARY_SERIES_ID,
                    observation_date=observation_date,
                    change_type="NEW",
                    previous_value=None,
                    new_value=history[observation_date],
                    detected_at=CALCULATED_AT,
                )
            )
        recorded = _recorded(db_session, "inflation", _state_for(history), INFLATION_METHODOLOGY_ID, run=run)

        detail = service.get_history_detail(db_session, "inflation", recorded.id)

        assert [row.observation_date for row in detail.related_changes] == [used_date]
        assert detail.other_changes_in_same_run == 1

    def test_changes_from_a_different_run_are_never_attributed_to_this_result(self, db_session, service):
        history = _core_pce_history(PERIOD)
        _seed_versioned(db_session, PRIMARY_SERIES_ID, history, BEFORE)
        other_run = _check_run(db_session, BEFORE)
        db_session.add(
            ReleaseObservationUpdate(
                release_check_run_id=other_run.id,
                series_id=PRIMARY_SERIES_ID,
                observation_date=PERIOD,
                change_type="REVISED",
                previous_value=1.0,
                new_value=history[PERIOD],
                detected_at=BEFORE,
            )
        )
        recorded = _recorded(db_session, "inflation", _state_for(history), INFLATION_METHODOLOGY_ID)

        detail = service.get_history_detail(db_session, "inflation", recorded.id)

        assert detail.related_changes == []
        assert detail.other_changes_in_same_run == 0


class TestLookupFailures:
    def test_an_unknown_recorded_result_raises_not_found(self, db_session, service):
        with pytest.raises(RecordedResultNotFoundError):
            service.get_history_detail(db_session, "inflation", 999_999)

    def test_a_result_belonging_to_another_monitor_is_not_found_under_this_one(self, db_session, service):
        recorded = _recorded(db_session, "labor", "MIXED", LABOR_METHODOLOGY_ID)
        with pytest.raises(RecordedResultNotFoundError):
            service.get_history_detail(db_session, "inflation", recorded.id)
