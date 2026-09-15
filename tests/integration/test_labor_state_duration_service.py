"""Integration tests for LaborMonitorService.get_state_duration_result
against a real, isolated PostgreSQL test database -- contract
`docs/product/state-duration-v1.md`. No FastAPI, no OpenAI, no FRED.

These tests exist to prove the SERVICE correctly composes persistence
(SeriesRepository), `compute_labor_monitor_result`/
`compute_labor_monitor_result_at` (app.domain.labor, unmodified), and
the pure sequence helper (app.domain.state_duration) -- something
neither tests/test_domain_state_duration.py (pure, hand-built
sequences) nor tests/test_domain_labor.py (pure classification, no
duration concept) can prove on its own. Every fixture below is
hand-constructed so the expected `duration_months`/`boundary_type` is
derivable by hand from `LABOR_V1_FROZEN_METHODOLOGY.md`'s own tables,
not merely reproduced by calling the same code under test.
"""

from datetime import date

from app.domain.labor import month_before
from app.models.labor import PAYEMS_SERIES_ID, UNRATE_SERIES_ID
from app.models.series import Observation, SeriesResponse
from app.repositories.series_repository import SeriesRepository
from app.services.labor import LaborMonitorService

T = date(2026, 1, 1)


def _flat_payems(anchor: date, months: int, value: float = 150_000.0, skip: set[date] | None = None) -> list[tuple[date, float]]:
    """`months` consecutive flat-valued (native "Thousands of Persons")
    months ending at `anchor` -- zero monthly change anywhere, so
    `current_3m_avg_jobs`/`prior_3m_avg_jobs` are both exactly 0 at
    every reconstructed period -> condition=FLAT, momentum=STEADY ->
    EmploymentState=STABLE everywhere, unless a `skip`ped date breaks a
    required endpoint."""
    skip = skip or set()
    return [(month_before(anchor, n), value) for n in range(months) if month_before(anchor, n) not in skip]


def _flat_unrate(anchor: date, months: int, value: float = 4.0, skip: set[date] | None = None) -> list[tuple[date, float]]:
    """Same shape as `_flat_payems`: zero delta_pp anywhere ->
    UnemploymentTrendState=STABLE everywhere, unless `skip`ped."""
    skip = skip or set()
    return [(month_before(anchor, n), value) for n in range(months) if month_before(anchor, n) not in skip]


def _seed(db_session, series_id: str, points: list[tuple[date, float]]) -> None:
    units = "Thousands of Persons" if series_id == PAYEMS_SERIES_ID else "Percent"
    SeriesRepository(db_session).save_series(
        SeriesResponse(series_id=series_id, title=series_id, units=units, observations=[Observation(date=d, value=v) for d, v in points])
    )
    db_session.flush()


class TestExactBoundary:
    def test_a_single_month_payems_jump_produces_a_one_month_exact_run(self, db_session):
        """Hand-verified against LABOR_V1_FROZEN_METHODOLOGY.md §4/§5/
        §7: PAYEMS flat (150,000 thousand) at every month strictly
        before `T`, with a one-time +600 (native units, i.e. +600,000
        jobs) jump AT `T`. UNRATE flat (STABLE) throughout.

        At T: current_3m_avg_jobs = (600,000+0+0)/3 = 200,000 jobs >
        condition_deadband (50,000) -> EXPANDING. prior_3m_avg_jobs =
        0 -> momentum diff = 200,000 > momentum_deadband (50,000) ->
        IMPROVING. EmploymentState = EXPANDING (table: EXPANDING+
        IMPROVING -> EXPANDING). UnemploymentTrendState = STABLE
        (flat). combine_labor_state(EXPANDING, STABLE) -> not a table
        cell -> MIXED (the explicit default).

        At T-1: current_3m_avg_jobs/prior_3m_avg_jobs both use only
        pre-jump (flat) months -> 0/0 -> condition=FLAT, momentum=
        STEADY -> EmploymentState=STABLE (table: FLAT+STEADY ->
        STABLE). combine_labor_state(STABLE, STABLE) -> STABLE (table
        cell). A real, differing, non-INSUFFICIENT_DATA state -> EXACT,
        duration=1.
        """
        payems = _flat_payems(month_before(T, 1), 25, value=150_000.0)
        payems.append((T, 150_000.0 + 600.0))
        _seed(db_session, PAYEMS_SERIES_ID, payems)
        _seed(db_session, UNRATE_SERIES_ID, _flat_unrate(T, 25))

        result = LaborMonitorService().get_state_duration_result(db_session)

        assert result.status == "AVAILABLE"
        assert result.state == "MIXED"
        assert result.evaluation_period == T
        assert result.duration_months == 1
        assert result.earliest_confirmed_period == T
        assert result.boundary_type == "EXACT"
        assert result.previous_state == "STABLE"
        assert result.previous_period == month_before(T, 1)


class TestDataBounded:
    """Frozen §25/§47: the real UNRATE gap at 2025-10 is the canonical
    #24C DATA_BOUNDED test case (this codebase's own worked example,
    `tests/test_domain_labor_release_processing.py`)."""

    def test_the_real_2025_10_unrate_gap_stops_the_walk_at_the_correct_month(self, db_session):
        """T = 2026-03-01, UNRATE's 2025-10-01 observation omitted.
        Unemployment's own required months at period `p` are `p, p-1,
        p-2, p-12, p-13, p-14`. For months_back=0,1,2 (p=2026-03,02,01)
        the current-window {p,p-1,p-2} never reaches 2025-10. At
        months_back=3 (p=2025-12), the current window is {2025-12,
        2025-11, 2025-10} -- includes the missing month ->
        current_3m_avg unavailable -> UnemploymentTrendState=
        INSUFFICIENT_DATA -> LaborState=INSUFFICIENT_DATA ->
        DATA_BOUNDED, duration_months=3 (months_back 0,1,2)."""
        anchor = date(2026, 3, 1)
        gap = date(2025, 10, 1)
        _seed(db_session, PAYEMS_SERIES_ID, _flat_payems(anchor, 24))
        _seed(db_session, UNRATE_SERIES_ID, _flat_unrate(anchor, 24, skip={gap}))

        result = LaborMonitorService().get_state_duration_result(db_session)

        assert result.status == "AVAILABLE"
        assert result.state == "STABLE"
        assert result.evaluation_period == anchor
        assert result.duration_months == 3
        assert result.earliest_confirmed_period == month_before(anchor, 2)
        assert result.boundary_type == "DATA_BOUNDED"
        assert result.previous_state is None
        assert result.previous_period is None

    def test_a_payems_only_gap_produces_data_bounded_independently_of_unrate(self, db_session):
        """PAYEMS employment's own required months at period `p` are
        `p .. p-6` (7 consecutive months). A gap at T-9 first breaks
        period T-3 (whose own window `{T-3..T-9}` first reaches it) --
        UNRATE stays fully flat/STABLE throughout, proving the PAYEMS
        gap alone drives the boundary."""
        gap = month_before(T, 9)
        _seed(db_session, PAYEMS_SERIES_ID, _flat_payems(T, 30, skip={gap}))
        _seed(db_session, UNRATE_SERIES_ID, _flat_unrate(T, 30))

        result = LaborMonitorService().get_state_duration_result(db_session)

        assert result.status == "AVAILABLE"
        assert result.boundary_type == "DATA_BOUNDED"
        assert result.duration_months == 3  # months_back 0,1,2 (T, T-1, T-2) never reach T-9

    def test_an_unrate_only_gap_produces_data_bounded_independently_of_payems(self, db_session):
        """A UNRATE-only gap at T-14 (the prior-year window's own
        farthest offset) first breaks period T itself's prior-year
        cluster {T-12,T-13,T-14} -> DATA_BOUNDED at duration=0's own
        boundary is impossible (current state must be valid to even
        begin) -- placed further back instead, at T-1-14=T-15, so T
        itself remains valid and the walk proceeds one step first."""
        gap = month_before(T, 15)
        _seed(db_session, PAYEMS_SERIES_ID, _flat_payems(T, 30))
        _seed(db_session, UNRATE_SERIES_ID, _flat_unrate(T, 30, skip={gap}))

        result = LaborMonitorService().get_state_duration_result(db_session)

        assert result.status == "AVAILABLE"
        assert result.boundary_type == "DATA_BOUNDED"
        assert result.duration_months == 1  # only T itself; T-1's own prior-year cluster {T-13,T-14,T-15} already reaches the gap


class TestLookbackBounded:
    def test_a_uniform_run_longer_than_the_bound_is_lookback_bounded_at_exactly_sixty(self, db_session):
        """80 consecutive flat months for both PAYEMS and UNRATE (well
        past the 60-month bound, with enough additional trailing
        history that period T-59 itself still has a full, valid
        window) -> every one of the 60 examined periods is STABLE ->
        LOOKBACK_BOUNDED, duration=60."""
        _seed(db_session, PAYEMS_SERIES_ID, _flat_payems(T, 80))
        _seed(db_session, UNRATE_SERIES_ID, _flat_unrate(T, 80))

        result = LaborMonitorService().get_state_duration_result(db_session)

        assert result.status == "AVAILABLE"
        assert result.state == "STABLE"
        assert result.duration_months == 60
        assert result.boundary_type == "LOOKBACK_BOUNDED"
        assert result.earliest_confirmed_period == month_before(T, 59)
        assert result.previous_state is None
        assert result.previous_period is None


class TestCurrentInsufficient:
    def test_nothing_persisted_at_all(self, db_session):
        result = LaborMonitorService().get_state_duration_result(db_session)
        assert result.status == "CURRENT_INSUFFICIENT"
        assert result.methodology_id == "labor_v1.0"
        assert result.data_basis == "latest_revised_data"

    def test_only_payems_persisted(self, db_session):
        """No candidate evaluation_period at all (UNRATE has zero
        observations) -> CURRENT_INSUFFICIENT, matching
        `determine_evaluation_period`'s own None-if-either-missing
        contract."""
        _seed(db_session, PAYEMS_SERIES_ID, _flat_payems(T, 20))
        result = LaborMonitorService().get_state_duration_result(db_session)
        assert result.status == "CURRENT_INSUFFICIENT"

    def test_insufficient_trailing_history_at_the_only_persisted_month(self, db_session):
        _seed(db_session, PAYEMS_SERIES_ID, [(T, 150_000.0)])
        _seed(db_session, UNRATE_SERIES_ID, [(T, 4.0)])
        result = LaborMonitorService().get_state_duration_result(db_session)
        assert result.status == "CURRENT_INSUFFICIENT"


class TestSharedEvaluationPeriod:
    def test_evaluation_period_matches_get_result_own_shared_period(self, db_session):
        """Frozen §5: the current anchor is
        `LaborMonitorResult.evaluation_period` -- confirmed matching a
        separate, plain `get_result` call, not a second, independently
        derived period."""
        _seed(db_session, PAYEMS_SERIES_ID, _flat_payems(T, 30))
        _seed(db_session, UNRATE_SERIES_ID, _flat_unrate(T, 30))

        service = LaborMonitorService()
        duration_result = service.get_state_duration_result(db_session)
        monitor_result = service.get_result(db_session)

        assert duration_result.evaluation_period == monitor_result.evaluation_period
        assert duration_result.state == monitor_result.state


class TestRevisionEffect:
    def test_a_persisted_revision_changes_the_reconstructed_duration(self, db_session):
        """Frozen §26: expected, not a defect."""
        payems = _flat_payems(T, 80)
        _seed(db_session, PAYEMS_SERIES_ID, payems)
        _seed(db_session, UNRATE_SERIES_ID, _flat_unrate(T, 80))
        before = LaborMonitorService().get_state_duration_result(db_session)
        assert before.boundary_type == "LOOKBACK_BOUNDED"

        revised_payems = [(d, (v + 600.0 if d == T else v)) for d, v in payems]
        _seed(db_session, PAYEMS_SERIES_ID, revised_payems)
        after = LaborMonitorService().get_state_duration_result(db_session)

        assert after.boundary_type == "EXACT"
        assert after.duration_months == 1
        assert before.model_dump() != after.model_dump()


class TestContractFields:
    def test_methodology_id_data_basis_history_type_on_available_response(self, db_session):
        _seed(db_session, PAYEMS_SERIES_ID, _flat_payems(T, 30))
        _seed(db_session, UNRATE_SERIES_ID, _flat_unrate(T, 30))
        result = LaborMonitorService().get_state_duration_result(db_session)
        assert result.methodology_id == "labor_v1.0"
        assert result.data_basis == "latest_revised_data"
        assert result.history_type == "latest_revised_reconstruction"

    def test_methodology_id_data_basis_on_current_insufficient_response(self, db_session):
        result = LaborMonitorService().get_state_duration_result(db_session)
        assert result.methodology_id == "labor_v1.0"
        assert result.data_basis == "latest_revised_data"
        assert not hasattr(result, "duration_months")


class TestDeterminismAndNonMutation:
    def test_repeated_calls_are_deterministic(self, db_session):
        _seed(db_session, PAYEMS_SERIES_ID, _flat_payems(T, 30))
        _seed(db_session, UNRATE_SERIES_ID, _flat_unrate(T, 30))
        service = LaborMonitorService()
        result_1 = service.get_state_duration_result(db_session)
        result_2 = service.get_state_duration_result(db_session)
        assert result_1.model_dump() == result_2.model_dump()

    def test_does_not_modify_persisted_observations(self, db_session):
        from app.db.models import EconomicObservation, EconomicSeries

        _seed(db_session, PAYEMS_SERIES_ID, _flat_payems(T, 30))
        _seed(db_session, UNRATE_SERIES_ID, _flat_unrate(T, 30))

        series_count_before = db_session.query(EconomicSeries).count()
        observation_count_before = db_session.query(EconomicObservation).count()

        service = LaborMonitorService()
        service.get_state_duration_result(db_session)
        service.get_state_duration_result(db_session)

        assert db_session.query(EconomicSeries).count() == series_count_before
        assert db_session.query(EconomicObservation).count() == observation_count_before
