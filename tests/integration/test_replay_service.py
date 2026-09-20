"""Integration tests for deterministic point-in-time replay
(Increment #31).

The property under test is not "the stored result can be read back" --
that was already true since #25E. It is that the recorded conclusion can
be RE-DERIVED from the observations MacroChipz actually had when it
concluded, and that a revision arriving afterwards cannot contaminate
that re-derivation.
"""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.db.models import EconomicSeries, RecordedMonitorResult, ReleaseCheckRun, ReleaseOccurrence, EconomicRelease
from app.models.inflation import METHODOLOGY_ID as INFLATION_METHODOLOGY_ID, PRIMARY_SERIES_ID
from app.models.labor import METHODOLOGY_ID as LABOR_METHODOLOGY_ID, PAYEMS_SERIES_ID, UNRATE_SERIES_ID
from app.repositories.observation_versions import ORIGIN_RELEASE_PROCESSING, ObservationVersionWriter
from app.services.replay import ReplayService

pytestmark = pytest.mark.integration

CALCULATED_AT = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
BEFORE = CALCULATED_AT - timedelta(days=30)
AFTER = CALCULATED_AT + timedelta(days=30)
ANCHOR_PERIOD = date(2026, 3, 1)


def _month(anchor: date, months_back: int) -> date:
    year, month = anchor.year, anchor.month - months_back
    while month <= 0:
        year -= 1
        month += 12
    return date(year, month, 1)


def _series(session, series_id: str) -> EconomicSeries:
    """Get-or-create: the shared test database may already carry this
    canonical series from another suite, and this test cares about
    versions, not about owning the series row."""
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


def _recorded(session, monitor: str, state: str, methodology_id: str, calculated_at: datetime = CALCULATED_AT):
    """A recorded result with a real owning check run, exactly as
    release processing would have produced it."""
    release = EconomicRelease(name="Test Release", provider="FRED", provider_release_id="9999", active=True)
    session.add(release)
    session.flush()
    occurrence = ReleaseOccurrence(economic_release_id=release.id, scheduled_date=date(2026, 5, 1))
    session.add(occurrence)
    session.flush()
    run = ReleaseCheckRun(
        release_occurrence_id=occurrence.id,
        status="CHANGED",
        started_at=calculated_at,
        completed_at=calculated_at,
    )
    session.add(run)
    session.flush()
    recorded = RecordedMonitorResult(
        release_check_run_id=run.id,
        monitor=monitor,
        evaluation_period=ANCHOR_PERIOD,
        state=state,
        methodology_id=methodology_id,
        data_basis="latest_revised_data",
        calculated_at=calculated_at,
    )
    session.add(recorded)
    session.flush()
    return recorded


def _core_pce_history(anchor: date, months: int = 14, growth: float = 0.002) -> dict[date, float]:
    """A steadily-growing index -- enough history for the 12-month
    window `inflation_v1.0` requires."""
    return {_month(anchor, n): 120.0 * ((1 + growth) ** (months - n)) for n in range(months)}


class TestReplayReproducesRecordedResults:
    def test_a_recorded_inflation_state_is_re_derived_from_historical_inputs(self, db_session):
        history = _core_pce_history(ANCHOR_PERIOD)
        _seed_versioned(db_session, PRIMARY_SERIES_ID, history, BEFORE)

        # Record whatever the methodology genuinely concludes, so the
        # test proves reproduction rather than asserting a hard-coded
        # state the methodology may not produce.
        from app.domain.inflation import compute_series_momentum_at
        from app.models.series import Observation

        expected = compute_series_momentum_at(
            [Observation(date=d, value=v) for d, v in sorted(history.items())], PRIMARY_SERIES_ID, ANCHOR_PERIOD
        ).state
        recorded = _recorded(db_session, "inflation", expected, INFLATION_METHODOLOGY_ID)

        result = ReplayService().replay_recorded_result(db_session, recorded.id)

        assert result.outcome == "MATCH"
        assert result.replayed_state == result.recorded_state == expected
        assert result.anchor == CALCULATED_AT
        assert result.input_series_ids == [PRIMARY_SERIES_ID]
        assert result.input_observation_count == len(history)
        assert result.inputs_include_backfilled is False

    def test_a_recorded_labor_state_is_re_derived_from_historical_inputs(self, db_session):
        payems = {_month(ANCHOR_PERIOD, n): 150_000.0 - n * 120.0 for n in range(20)}
        unrate = {_month(ANCHOR_PERIOD, n): 4.0 + n * 0.02 for n in range(20)}
        _seed_versioned(db_session, PAYEMS_SERIES_ID, payems, BEFORE)
        _seed_versioned(db_session, UNRATE_SERIES_ID, unrate, BEFORE)

        from app.domain.labor import compute_labor_monitor_result_at
        from app.models.labor import CONDITION_DEADBAND_JOBS, MOMENTUM_DEADBAND_JOBS, UNEMPLOYMENT_DEADBAND_PP
        from app.models.series import Observation

        expected = compute_labor_monitor_result_at(
            [Observation(date=d, value=v) for d, v in sorted(payems.items())],
            [Observation(date=d, value=v) for d, v in sorted(unrate.items())],
            ANCHOR_PERIOD,
            CONDITION_DEADBAND_JOBS,
            MOMENTUM_DEADBAND_JOBS,
            UNEMPLOYMENT_DEADBAND_PP,
        ).state
        recorded = _recorded(db_session, "labor", expected, LABOR_METHODOLOGY_ID)

        result = ReplayService().replay_recorded_result(db_session, recorded.id)

        assert result.outcome == "MATCH"
        assert result.replayed_state == expected
        assert sorted(result.input_series_ids) == sorted([PAYEMS_SERIES_ID, UNRATE_SERIES_ID])


class TestReplayIsNotContaminatedByLaterRevisions:
    def test_a_revision_after_the_anchor_does_not_change_the_replayed_result(self, db_session):
        """The decisive test. A large revision lands AFTER the recorded
        calculation; replay must still see the pre-revision world."""
        history = _core_pce_history(ANCHOR_PERIOD)
        series = _seed_versioned(db_session, PRIMARY_SERIES_ID, history, BEFORE)

        from app.domain.inflation import compute_series_momentum_at
        from app.models.series import Observation

        original_state = compute_series_momentum_at(
            [Observation(date=d, value=v) for d, v in sorted(history.items())], PRIMARY_SERIES_ID, ANCHOR_PERIOD
        ).state
        recorded = _recorded(db_session, "inflation", original_state, INFLATION_METHODOLOGY_ID)

        before_revision = ReplayService().replay_recorded_result(db_session, recorded.id)
        assert before_revision.outcome == "MATCH"

        # A violent revision to the anchor period, recorded afterwards.
        ObservationVersionWriter(db_session, recorded_at=AFTER, origin=ORIGIN_RELEASE_PROCESSING).apply(
            series, ANCHOR_PERIOD, history[ANCHOR_PERIOD] * 1.5
        )
        db_session.flush()

        after_revision = ReplayService().replay_recorded_result(db_session, recorded.id)

        assert after_revision.outcome == "MATCH"
        assert after_revision.replayed_state == before_revision.replayed_state
        assert after_revision.input_observation_count == before_revision.input_observation_count

    def test_recomputing_against_current_data_would_have_differed(self, db_session):
        """Proves the previous test is not vacuous: today's data really
        does produce a different answer, so the as-of read is doing
        genuine work."""
        history = _core_pce_history(ANCHOR_PERIOD)
        series = _seed_versioned(db_session, PRIMARY_SERIES_ID, history, BEFORE)

        from app.domain.inflation import compute_series_momentum_at
        from app.models.series import Observation

        original = compute_series_momentum_at(
            [Observation(date=d, value=v) for d, v in sorted(history.items())], PRIMARY_SERIES_ID, ANCHOR_PERIOD
        )
        ObservationVersionWriter(db_session, recorded_at=AFTER, origin=ORIGIN_RELEASE_PROCESSING).apply(
            series, ANCHOR_PERIOD, history[ANCHOR_PERIOD] * 1.5
        )
        db_session.flush()

        from app.repositories.series_repository import SeriesRepository

        current_rows = SeriesRepository(db_session).get_observations_in_range(series.id, None, None)
        current = compute_series_momentum_at(
            [Observation(date=row.observation_date, value=row.value) for row in current_rows],
            PRIMARY_SERIES_ID,
            ANCHOR_PERIOD,
        )
        assert current.r_12m != original.r_12m

    def test_the_recorded_result_is_never_mutated_by_replay(self, db_session):
        history = _core_pce_history(ANCHOR_PERIOD)
        _seed_versioned(db_session, PRIMARY_SERIES_ID, history, BEFORE)
        recorded = _recorded(db_session, "inflation", "COOLING", INFLATION_METHODOLOGY_ID)
        original = (recorded.state, recorded.methodology_id, recorded.calculated_at, recorded.evaluation_period)

        ReplayService().replay_recorded_result(db_session, recorded.id)
        db_session.flush()

        refreshed = db_session.get(RecordedMonitorResult, recorded.id)
        assert (refreshed.state, refreshed.methodology_id, refreshed.calculated_at, refreshed.evaluation_period) == original


class TestReplayRefusesRatherThanGuessing:
    def test_no_version_history_for_the_inputs_is_reported_honestly(self, db_session):
        recorded = _recorded(db_session, "inflation", "MIXED", INFLATION_METHODOLOGY_ID)

        result = ReplayService().replay_recorded_result(db_session, recorded.id)

        assert result.outcome == "NOT_REPLAYABLE"
        assert result.reason == "NO_VERSION_HISTORY_FOR_INPUTS"
        assert result.replayed_state is None

    def test_history_beginning_after_the_calculation_is_reported_honestly(self, db_session):
        """A recorded result older than the version history cannot be
        replayed -- returning an empty dataset to the methodology would
        yield a confident INSUFFICIENT_DATA that is really a storage
        gap."""
        _seed_versioned(db_session, PRIMARY_SERIES_ID, _core_pce_history(ANCHOR_PERIOD), AFTER)
        recorded = _recorded(db_session, "inflation", "MIXED", INFLATION_METHODOLOGY_ID)

        result = ReplayService().replay_recorded_result(db_session, recorded.id)

        assert result.outcome == "NOT_REPLAYABLE"
        assert result.reason == "VERSION_HISTORY_STARTS_AFTER_CALCULATION"

    def test_an_unknown_methodology_version_is_refused(self, db_session):
        _seed_versioned(db_session, PRIMARY_SERIES_ID, _core_pce_history(ANCHOR_PERIOD), BEFORE)
        recorded = _recorded(db_session, "inflation", "MIXED", "inflation_v9.9")

        result = ReplayService().replay_recorded_result(db_session, recorded.id)

        assert result.outcome == "NOT_REPLAYABLE"
        assert result.reason == "UNKNOWN_METHODOLOGY_VERSION"

    def test_an_unknown_recorded_result_is_refused(self, db_session):
        result = ReplayService().replay_recorded_result(db_session, 999_999)

        assert result.outcome == "NOT_REPLAYABLE"
        assert result.reason == "UNKNOWN_RECORDED_RESULT"

    def test_a_genuine_disagreement_is_reported_as_a_mismatch(self, db_session):
        """If the recorded state and the re-derived state genuinely
        differ, replay says so rather than hiding it."""
        _seed_versioned(db_session, PRIMARY_SERIES_ID, _core_pce_history(ANCHOR_PERIOD), BEFORE)
        recorded = _recorded(db_session, "inflation", "DEFINITELY_NOT_THE_REAL_STATE", INFLATION_METHODOLOGY_ID)

        result = ReplayService().replay_recorded_result(db_session, recorded.id)

        assert result.outcome == "MISMATCH"
        assert result.replayed_state is not None
        assert result.replayed_state != result.recorded_state
