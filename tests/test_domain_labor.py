"""Unit tests for the pure Labor Monitor domain layer
(`app.domain.labor`), methodology `labor_v1.0` -- frozen and normative
in `research/labor_momentum/LABOR_V1_FROZEN_METHODOLOGY.md`. Pure,
offline, deterministic: no database, no FRED, no FastAPI.

Historical regression fixtures use REAL PAYEMS values (FRED's native
"Thousands of Persons"), taken directly from the cached research data
that validated `labor_v1.0` (`research/labor_momentum/data/PAYEMS.csv`)
-- not fabricated numbers -- so these tests prove the shipped
production code reproduces the exact validated research result, not
merely "a plausible-looking one."
"""

from datetime import date

import pytest

from app.domain.labor import (
    average_monthly_change,
    average_rate,
    build_jobs_index,
    build_rate_index,
    classify_employment_condition,
    classify_employment_momentum,
    classify_unemployment_trend_state,
    combine_employment_state,
    combine_labor_state,
    compute_employment_result,
    compute_labor_monitor_result,
    compute_unemployment_result,
    determine_evaluation_period,
    latest_observation_date,
    month_before,
    monthly_change,
)
from app.models.labor import (
    CONDITION_DEADBAND_JOBS,
    EmploymentCondition,
    EmploymentMomentum,
    EmploymentState,
    MOMENTUM_DEADBAND_JOBS,
    UNEMPLOYMENT_DEADBAND_PP,
    UnemploymentTrendState,
)
from app.models.series import Observation


def _obs(year: int, month: int, value: float | None) -> Observation:
    return Observation(date=date(year, month, 1), value=value)


# ---------------------------------------------------------------------
# Units
# ---------------------------------------------------------------------


class TestUnits:
    def test_payems_thousands_are_converted_to_actual_jobs(self):
        # A raw persisted PAYEMS value of 159500.0 ("Thousands of
        # Persons") must become 159,500,000 actual jobs -- not
        # 159,500 (an unconverted native-thousands figure) and not
        # 159,500,000,000 (an accidental double conversion).
        index = build_jobs_index([_obs(2026, 8, 159500.0)])
        assert index[date(2026, 8, 1)] == 159_500_000.0

    def test_a_native_50_never_means_50000_jobs(self):
        """Explicit proof that the unit bug #20A.1 caught (comparing a
        native-thousands value directly against a jobs-unit deadband)
        cannot happen here: a native value of 50 converts to 50,000
        actual jobs, comfortably BELOW `CONDITION_DEADBAND_JOBS`
        (50,000) -- it must classify FLAT, not EXPANDING. If the
        conversion were ever skipped, 50 would incorrectly classify as
        FLAT too (50 < 50,000), so this test also pins the exact
        converted magnitude via a direct equality check, not just the
        classification outcome."""
        index = build_jobs_index([_obs(2020, 1, 50.0)])
        assert index[date(2020, 1, 1)] == 50_000.0
        assert classify_employment_condition(index[date(2020, 1, 1)], CONDITION_DEADBAND_JOBS) == "FLAT"

    def test_unrate_is_never_converted(self):
        index = build_rate_index([_obs(2020, 1, 4.1)])
        assert index[date(2020, 1, 1)] == 4.1

    def test_missing_value_excluded_from_jobs_index(self):
        index = build_jobs_index([_obs(2020, 1, None), _obs(2020, 2, 100.0)])
        assert date(2020, 1, 1) not in index
        assert index[date(2020, 2, 1)] == 100_000.0


# ---------------------------------------------------------------------
# Calendar arithmetic
# ---------------------------------------------------------------------


class TestMonthBefore:
    def test_zero_months_back_is_the_same_month(self):
        assert month_before(date(2026, 7, 1), 0) == date(2026, 7, 1)

    def test_simple_case(self):
        assert month_before(date(2026, 7, 1), 3) == date(2026, 4, 1)

    def test_year_rollover_backward(self):
        assert month_before(date(2026, 2, 1), 3) == date(2025, 11, 1)

    def test_multi_year_rollover(self):
        assert month_before(date(2026, 6, 1), 14) == date(2025, 4, 1)


class TestLatestObservationDate:
    def test_empty_list_is_none(self):
        assert latest_observation_date([]) is None

    def test_includes_a_row_with_a_missing_value(self):
        assert latest_observation_date([_obs(2020, 1, None)]) == date(2020, 1, 1)

    def test_picks_the_max_date_regardless_of_input_order(self):
        obs = [_obs(2020, 3, 1.0), _obs(2020, 1, 1.0), _obs(2020, 2, 1.0)]
        assert latest_observation_date(obs) == date(2020, 3, 1)


# ---------------------------------------------------------------------
# Monthly change / averages
# ---------------------------------------------------------------------


class TestMonthlyChange:
    def test_exact_positive_change(self):
        index = {date(2020, 1, 1): 100.0, date(2020, 2, 1): 150.0}
        assert monthly_change(index, date(2020, 2, 1)) == 50.0

    def test_exact_negative_change(self):
        index = {date(2020, 1, 1): 150.0, date(2020, 2, 1): 100.0}
        assert monthly_change(index, date(2020, 2, 1)) == -50.0

    def test_zero_change(self):
        index = {date(2020, 1, 1): 100.0, date(2020, 2, 1): 100.0}
        assert monthly_change(index, date(2020, 2, 1)) == 0.0

    def test_missing_current_month_is_none(self):
        index = {date(2020, 1, 1): 100.0}
        assert monthly_change(index, date(2020, 2, 1)) is None

    def test_missing_prior_month_is_none(self):
        index = {date(2020, 2, 1): 100.0}
        assert monthly_change(index, date(2020, 2, 1)) is None


class TestAverageMonthlyChange:
    def test_averages_three_consecutive_changes(self):
        # changes: Feb=+10, Jan=+20, Dec(prev yr)=+30 -> mean=20
        index = {
            date(2019, 11, 1): 100.0,
            date(2019, 12, 1): 130.0,
            date(2020, 1, 1): 150.0,
            date(2020, 2, 1): 160.0,
        }
        assert average_monthly_change(index, date(2020, 2, 1), 3) == pytest.approx(20.0)

    def test_missing_one_month_in_the_window_makes_the_whole_average_none(self):
        index = {
            date(2019, 12, 1): 130.0,
            # 2020-01 deliberately missing
            date(2020, 2, 1): 160.0,
        }
        assert average_monthly_change(index, date(2020, 2, 1), 3) is None

    def test_prior_3m_window_is_anchored_three_months_earlier(self):
        # Reused for prior_3m_avg_jobs by anchoring at month_before(t, 3).
        # A non-linear synthetic level sequence (quadratic in n) so the
        # month-over-month change genuinely differs between the two
        # windows -- a linear sequence would give every monthly change
        # the same constant value, making this test pass vacuously
        # regardless of whether the two windows were correctly offset.
        index = {month_before(date(2020, 6, 1), n): float(n * n) for n in range(8)}
        recent = average_monthly_change(index, date(2020, 6, 1), 3)
        prior = average_monthly_change(index, month_before(date(2020, 6, 1), 3), 3)
        assert recent is not None and prior is not None
        assert recent != prior  # genuinely different windows, not accidentally aliased


# ---------------------------------------------------------------------
# Employment condition
# ---------------------------------------------------------------------


class TestClassifyEmploymentCondition:
    def test_none_is_insufficient_data(self):
        assert classify_employment_condition(None, CONDITION_DEADBAND_JOBS) == "INSUFFICIENT_DATA"

    def test_comfortably_positive_is_expanding(self):
        assert classify_employment_condition(300_000, CONDITION_DEADBAND_JOBS) == "EXPANDING"

    def test_comfortably_negative_is_contracting(self):
        assert classify_employment_condition(-300_000, CONDITION_DEADBAND_JOBS) == "CONTRACTING"

    def test_zero_is_flat(self):
        assert classify_employment_condition(0, CONDITION_DEADBAND_JOBS) == "FLAT"

    def test_exactly_positive_boundary_is_flat_inclusive(self):
        assert classify_employment_condition(50_000, CONDITION_DEADBAND_JOBS) == "FLAT"

    def test_exactly_negative_boundary_is_flat_inclusive(self):
        assert classify_employment_condition(-50_000, CONDITION_DEADBAND_JOBS) == "FLAT"

    def test_just_outside_positive_boundary_is_expanding(self):
        assert classify_employment_condition(50_000.01, CONDITION_DEADBAND_JOBS) == "EXPANDING"

    def test_just_outside_negative_boundary_is_contracting(self):
        assert classify_employment_condition(-50_000.01, CONDITION_DEADBAND_JOBS) == "CONTRACTING"


# ---------------------------------------------------------------------
# Employment momentum
# ---------------------------------------------------------------------


class TestClassifyEmploymentMomentum:
    def test_either_input_none_is_insufficient_data(self):
        assert classify_employment_momentum(None, 100_000, MOMENTUM_DEADBAND_JOBS) == "INSUFFICIENT_DATA"
        assert classify_employment_momentum(100_000, None, MOMENTUM_DEADBAND_JOBS) == "INSUFFICIENT_DATA"

    def test_comfortably_higher_recent_is_improving(self):
        assert classify_employment_momentum(300_000, 0, MOMENTUM_DEADBAND_JOBS) == "IMPROVING"

    def test_comfortably_lower_recent_is_worsening(self):
        assert classify_employment_momentum(0, 300_000, MOMENTUM_DEADBAND_JOBS) == "WORSENING"

    def test_equal_values_are_steady(self):
        assert classify_employment_momentum(100_000, 100_000, MOMENTUM_DEADBAND_JOBS) == "STEADY"

    def test_exactly_positive_boundary_is_steady_inclusive(self):
        assert classify_employment_momentum(150_000, 100_000, MOMENTUM_DEADBAND_JOBS) == "STEADY"

    def test_exactly_negative_boundary_is_steady_inclusive(self):
        assert classify_employment_momentum(50_000, 100_000, MOMENTUM_DEADBAND_JOBS) == "STEADY"

    def test_just_outside_positive_boundary_is_improving(self):
        assert classify_employment_momentum(150_000.01, 100_000, MOMENTUM_DEADBAND_JOBS) == "IMPROVING"

    def test_just_outside_negative_boundary_is_worsening(self):
        assert classify_employment_momentum(49_999.99, 100_000, MOMENTUM_DEADBAND_JOBS) == "WORSENING"

    def test_a_decelerating_contraction_is_improving_not_accelerating(self):
        """The whole reason IMPROVING/WORSENING (not ACCELERATING/
        DECELERATING) was frozen: a contraction easing from -700K to
        -300K is a real improvement in trend, correctly IMPROVING."""
        assert classify_employment_momentum(-300_000, -700_000, MOMENTUM_DEADBAND_JOBS) == "IMPROVING"


# ---------------------------------------------------------------------
# Employment state -- all 9 condition x momentum cells, transcribed
# exactly from LABOR_V1_FROZEN_METHODOLOGY.md §5
# ---------------------------------------------------------------------


class TestCombineEmploymentState:
    @pytest.mark.parametrize(
        ("condition", "momentum", "expected"),
        [
            ("EXPANDING", "IMPROVING", "EXPANDING"),
            ("EXPANDING", "STEADY", "EXPANDING"),
            ("EXPANDING", "WORSENING", "COOLING"),
            ("FLAT", "IMPROVING", "STABLE"),
            ("FLAT", "STEADY", "STABLE"),
            ("FLAT", "WORSENING", "STABLE"),
            ("CONTRACTING", "IMPROVING", "RECOVERING"),
            ("CONTRACTING", "STEADY", "CONTRACTING"),
            ("CONTRACTING", "WORSENING", "CONTRACTING"),
        ],
    )
    def test_every_frozen_table_cell(
        self, condition: EmploymentCondition, momentum: EmploymentMomentum, expected: EmploymentState
    ):
        assert combine_employment_state(condition, momentum) == expected

    def test_insufficient_condition_propagates(self):
        assert combine_employment_state("INSUFFICIENT_DATA", "IMPROVING") == "INSUFFICIENT_DATA"

    def test_insufficient_momentum_propagates(self):
        assert combine_employment_state("EXPANDING", "INSUFFICIENT_DATA") == "INSUFFICIENT_DATA"

    def test_contracting_never_collapses_into_expanding_even_when_improving(self):
        """The critical invariant: still-contracting-but-improving is
        RECOVERING, never EXPANDING -- employment is factually still
        shrinking."""
        assert combine_employment_state("CONTRACTING", "IMPROVING") != "EXPANDING"
        assert combine_employment_state("CONTRACTING", "IMPROVING") == "RECOVERING"


# ---------------------------------------------------------------------
# Unemployment trend
# ---------------------------------------------------------------------


class TestClassifyUnemploymentTrendState:
    def test_none_is_insufficient_data(self):
        assert classify_unemployment_trend_state(None, UNEMPLOYMENT_DEADBAND_PP) == "INSUFFICIENT_DATA"

    def test_comfortably_positive_delta_is_deteriorating(self):
        assert classify_unemployment_trend_state(1.0, UNEMPLOYMENT_DEADBAND_PP) == "DETERIORATING"

    def test_comfortably_negative_delta_is_improving(self):
        assert classify_unemployment_trend_state(-1.0, UNEMPLOYMENT_DEADBAND_PP) == "IMPROVING"

    def test_zero_delta_is_stable(self):
        assert classify_unemployment_trend_state(0.0, UNEMPLOYMENT_DEADBAND_PP) == "STABLE"

    def test_exactly_positive_boundary_is_stable_inclusive(self):
        assert classify_unemployment_trend_state(0.2, UNEMPLOYMENT_DEADBAND_PP) == "STABLE"

    def test_exactly_negative_boundary_is_stable_inclusive(self):
        assert classify_unemployment_trend_state(-0.2, UNEMPLOYMENT_DEADBAND_PP) == "STABLE"

    def test_just_outside_positive_boundary_is_deteriorating(self):
        assert classify_unemployment_trend_state(0.2001, UNEMPLOYMENT_DEADBAND_PP) == "DETERIORATING"

    def test_just_outside_negative_boundary_is_improving(self):
        assert classify_unemployment_trend_state(-0.2001, UNEMPLOYMENT_DEADBAND_PP) == "IMPROVING"


class TestAverageRate:
    def test_averages_three_months(self):
        index = {date(2020, 1, 1): 4.0, date(2020, 2, 1): 4.2, date(2020, 3, 1): 4.1}
        assert average_rate(index, date(2020, 3, 1), 3) == pytest.approx((4.0 + 4.2 + 4.1) / 3)

    def test_missing_one_of_the_three_months_is_none(self):
        index = {date(2020, 1, 1): 4.0, date(2020, 3, 1): 4.1}
        assert average_rate(index, date(2020, 3, 1), 3) is None


# ---------------------------------------------------------------------
# Top-level Labor state -- every explicit branch + representative
# defaults, transcribed exactly from LABOR_V1_FROZEN_METHODOLOGY.md §7
# ---------------------------------------------------------------------


class TestCombineLaborState:
    def test_expanding_improving_is_strengthening(self):
        assert combine_labor_state("EXPANDING", "IMPROVING") == "STRENGTHENING"

    def test_cooling_deteriorating_is_cooling(self):
        assert combine_labor_state("COOLING", "DETERIORATING") == "COOLING"

    def test_contracting_deteriorating_is_cooling(self):
        assert combine_labor_state("CONTRACTING", "DETERIORATING") == "COOLING"

    def test_stable_stable_is_stable(self):
        assert combine_labor_state("STABLE", "STABLE") == "STABLE"

    @pytest.mark.parametrize(
        ("employment_state", "unemployment_state"),
        [
            ("EXPANDING", "DETERIORATING"),
            ("EXPANDING", "STABLE"),
            ("COOLING", "IMPROVING"),
            ("COOLING", "STABLE"),
            ("STABLE", "IMPROVING"),
            ("STABLE", "DETERIORATING"),
            ("CONTRACTING", "IMPROVING"),
            ("CONTRACTING", "STABLE"),
            ("RECOVERING", "IMPROVING"),
            ("RECOVERING", "DETERIORATING"),
            ("RECOVERING", "STABLE"),
        ],
    )
    def test_every_remaining_combination_defaults_to_mixed(
        self, employment_state: EmploymentState, unemployment_state: UnemploymentTrendState
    ):
        assert combine_labor_state(employment_state, unemployment_state) == "MIXED"

    def test_recovering_never_resolves_to_strengthening(self):
        """RECOVERING means employment is still factually contracting
        -- no pairing with it may claim STRENGTHENING at the top
        level, even when unemployment is independently IMPROVING."""
        for unemployment_state in ("IMPROVING", "DETERIORATING", "STABLE"):
            assert combine_labor_state("RECOVERING", unemployment_state) != "STRENGTHENING"

    def test_insufficient_employment_propagates(self):
        assert combine_labor_state("INSUFFICIENT_DATA", "STABLE") == "INSUFFICIENT_DATA"

    def test_insufficient_unemployment_propagates(self):
        assert combine_labor_state("EXPANDING", "INSUFFICIENT_DATA") == "INSUFFICIENT_DATA"

    def test_both_insufficient_propagates(self):
        assert combine_labor_state("INSUFFICIENT_DATA", "INSUFFICIENT_DATA") == "INSUFFICIENT_DATA"


# ---------------------------------------------------------------------
# compute_employment_result / compute_unemployment_result --
# completeness, missing-month behavior, evidence
# ---------------------------------------------------------------------


def _complete_payems_index(anchor: date) -> dict[date, float]:
    """13 consecutive months of PAYEMS (in jobs) ending at `anchor` --
    comfortably more than the 7 `compute_employment_result` needs, so
    individual tests can remove exactly one month to prove it's load-
    bearing."""
    return {month_before(anchor, n): 150_000_000.0 + n * 10_000 for n in range(13)}


class TestComputeEmploymentResult:
    def test_complete_window_produces_a_real_state(self):
        anchor = date(2020, 6, 1)
        result = compute_employment_result(_complete_payems_index(anchor), anchor, CONDITION_DEADBAND_JOBS, MOMENTUM_DEADBAND_JOBS)
        assert result.state != "INSUFFICIENT_DATA"
        assert len(result.observations) == 7

    @pytest.mark.parametrize("missing_offset", range(7))
    def test_missing_any_one_of_the_seven_required_months_makes_state_insufficient_data(self, missing_offset: int):
        """`state` (which needs momentum, and therefore all 7 months)
        is INSUFFICIENT_DATA if ANY of the 7 is missing -- per
        LABOR_V1_FROZEN_METHODOLOGY.md §4."""
        anchor = date(2020, 6, 1)
        index = _complete_payems_index(anchor)
        del index[month_before(anchor, missing_offset)]
        result = compute_employment_result(index, anchor, CONDITION_DEADBAND_JOBS, MOMENTUM_DEADBAND_JOBS)
        assert result.state == "INSUFFICIENT_DATA"
        assert result.momentum == "INSUFFICIENT_DATA"

    @pytest.mark.parametrize("missing_offset", [0, 1, 2, 3])
    def test_missing_any_of_the_four_condition_months_makes_condition_insufficient_data(self, missing_offset: int):
        """`condition` needs only `t..t-3` (per §3) -- a narrower
        requirement than `momentum`'s full 7 months."""
        anchor = date(2020, 6, 1)
        index = _complete_payems_index(anchor)
        del index[month_before(anchor, missing_offset)]
        result = compute_employment_result(index, anchor, CONDITION_DEADBAND_JOBS, MOMENTUM_DEADBAND_JOBS)
        assert result.condition == "INSUFFICIENT_DATA"

    @pytest.mark.parametrize("missing_offset", [4, 5, 6])
    def test_missing_only_a_prior_3m_only_month_leaves_condition_computable(self, missing_offset: int):
        """A month needed only by `prior_3m_avg_jobs` (offsets 4-6, per
        §4) does not affect `condition`'s own narrower 4-month
        requirement -- `condition` remains a real value even though
        `momentum`/`state` are INSUFFICIENT_DATA. This is a frozen,
        deliberate distinction (§3 vs. §4), not an implementation gap."""
        anchor = date(2020, 6, 1)
        index = _complete_payems_index(anchor)
        del index[month_before(anchor, missing_offset)]
        result = compute_employment_result(index, anchor, CONDITION_DEADBAND_JOBS, MOMENTUM_DEADBAND_JOBS)
        assert result.condition != "INSUFFICIENT_DATA"
        assert result.momentum == "INSUFFICIENT_DATA"
        assert result.state == "INSUFFICIENT_DATA"

    def test_observations_evidence_lists_all_seven_months_even_when_one_is_missing(self):
        anchor = date(2020, 6, 1)
        index = _complete_payems_index(anchor)
        missing_month = month_before(anchor, 4)
        del index[missing_month]
        result = compute_employment_result(index, anchor, CONDITION_DEADBAND_JOBS, MOMENTUM_DEADBAND_JOBS)
        assert len(result.observations) == 7
        missing_entries = [o for o in result.observations if o.observation_date == missing_month]
        assert len(missing_entries) == 1
        assert missing_entries[0].value is None


def _complete_unrate_index(anchor: date) -> dict[date, float]:
    months = [month_before(anchor, n) for n in range(3)] + [month_before(anchor, 12 + n) for n in range(3)]
    return {m: 4.0 for m in months}


class TestComputeUnemploymentResult:
    def test_complete_window_produces_a_real_state(self):
        anchor = date(2020, 6, 1)
        result = compute_unemployment_result(_complete_unrate_index(anchor), anchor, UNEMPLOYMENT_DEADBAND_PP)
        assert result.state != "INSUFFICIENT_DATA"
        assert len(result.observations) == 6

    @pytest.mark.parametrize("missing_offset", [0, 1, 2, 12, 13, 14])
    def test_missing_any_one_of_the_six_required_months_is_insufficient_data(self, missing_offset: int):
        anchor = date(2020, 6, 1)
        index = _complete_unrate_index(anchor)
        del index[month_before(anchor, missing_offset)]
        result = compute_unemployment_result(index, anchor, UNEMPLOYMENT_DEADBAND_PP)
        assert result.state == "INSUFFICIENT_DATA"

    def test_known_real_historical_gap_shape_2025_10_unrate(self):
        """Mirrors the real gap #20A.1's own research found (UNRATE has
        no persisted value for 2025-10) -- no special-case hack exists
        anywhere in this module; a missing exact month is handled
        exactly like any other missing month, and only matters when it
        actually falls inside a required window.

        Case 1: evaluating 2026-08 needs {2026-08,07,06} (current) and
        {2025-08,07,06} (prior year) -- the 2025-10 gap falls in
        NEITHER window, so the result is unaffected by it.

        Case 2: evaluating 2026-10 needs {2026-10,09,08} (current) and
        {2025-10,09,08} (prior year) -- the 2025-10 gap DOES fall in
        the prior-year window this time, so the result must be
        INSUFFICIENT_DATA."""
        gap_month = date(2025, 10, 1)

        unaffected_anchor = date(2026, 8, 1)
        index_unaffected = _complete_unrate_index(unaffected_anchor)
        assert gap_month not in {month_before(unaffected_anchor, n) for n in range(3)} | {
            month_before(unaffected_anchor, 12 + n) for n in range(3)
        }
        result_unaffected = compute_unemployment_result(index_unaffected, unaffected_anchor, UNEMPLOYMENT_DEADBAND_PP)
        assert result_unaffected.state != "INSUFFICIENT_DATA"

        affected_anchor = date(2026, 10, 1)
        index_affected = _complete_unrate_index(affected_anchor)
        del index_affected[gap_month]
        result_affected = compute_unemployment_result(index_affected, affected_anchor, UNEMPLOYMENT_DEADBAND_PP)
        assert result_affected.state == "INSUFFICIENT_DATA"


# ---------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------


class TestDeterminism:
    def test_same_input_twice_is_byte_identical(self):
        payems = [Observation(date=month_before(date(2020, 6, 1), n), value=150_000.0 + n) for n in range(13)]
        unrate = [Observation(date=month_before(date(2020, 6, 1), n), value=4.0) for n in range(15)]
        first = compute_labor_monitor_result(payems, unrate, CONDITION_DEADBAND_JOBS, MOMENTUM_DEADBAND_JOBS, UNEMPLOYMENT_DEADBAND_PP)
        second = compute_labor_monitor_result(payems, unrate, CONDITION_DEADBAND_JOBS, MOMENTUM_DEADBAND_JOBS, UNEMPLOYMENT_DEADBAND_PP)
        assert first.model_dump() == second.model_dump()


# ---------------------------------------------------------------------
# Evaluation period
# ---------------------------------------------------------------------


class TestDetermineEvaluationPeriod:
    def test_none_when_payems_has_no_observations(self):
        assert determine_evaluation_period([], [_obs(2020, 1, 4.0)]) is None

    def test_none_when_unrate_has_no_observations(self):
        assert determine_evaluation_period([_obs(2020, 1, 100.0)], []) is None

    def test_none_when_neither_has_observations(self):
        assert determine_evaluation_period([], []) is None

    def test_equal_latest_dates_use_that_date(self):
        payems = [_obs(2020, 1, 100.0), _obs(2020, 2, 110.0)]
        unrate = [_obs(2020, 1, 4.0), _obs(2020, 2, 4.1)]
        assert determine_evaluation_period(payems, unrate) == date(2020, 2, 1)

    def test_payems_newer_than_unrate_uses_the_earlier_unrate_date(self):
        payems = [_obs(2020, 3, 100.0)]
        unrate = [_obs(2020, 1, 4.0)]
        assert determine_evaluation_period(payems, unrate) == date(2020, 1, 1)

    def test_unrate_newer_than_payems_uses_the_earlier_payems_date(self):
        payems = [_obs(2020, 1, 100.0)]
        unrate = [_obs(2020, 3, 4.0)]
        assert determine_evaluation_period(payems, unrate) == date(2020, 1, 1)


class TestComputeLaborMonitorResultEvaluationPeriod:
    def test_no_observations_at_all_is_insufficient_with_null_period(self):
        result = compute_labor_monitor_result([], [], CONDITION_DEADBAND_JOBS, MOMENTUM_DEADBAND_JOBS, UNEMPLOYMENT_DEADBAND_PP)
        assert result.state == "INSUFFICIENT_DATA"
        assert result.evaluation_period is None
        assert result.employment.observations == []
        assert result.unemployment.observations == []

    def test_employment_and_unemployment_share_one_evaluation_period(self):
        anchor = date(2020, 6, 1)
        payems = [Observation(date=month_before(anchor, n), value=150_000.0 + n) for n in range(13)]
        unrate = [Observation(date=month_before(anchor, n), value=4.0) for n in range(15)]
        result = compute_labor_monitor_result(payems, unrate, CONDITION_DEADBAND_JOBS, MOMENTUM_DEADBAND_JOBS, UNEMPLOYMENT_DEADBAND_PP)
        assert result.evaluation_period == anchor
        # Every evidence observation date across both components must
        # be derived from this SAME anchor -- never two different
        # reference months in one result.
        employment_dates = {o.observation_date for o in result.employment.observations}
        assert max(employment_dates) == anchor

    def test_mismatched_series_availability_bounds_evaluation_period_by_the_earlier_series(self):
        payems = [Observation(date=month_before(date(2020, 8, 1), n), value=150_000.0 + n) for n in range(13)]
        # UNRATE only available through 2020-06 -- two months behind PAYEMS.
        unrate = [Observation(date=month_before(date(2020, 6, 1), n), value=4.0) for n in range(15)]
        result = compute_labor_monitor_result(payems, unrate, CONDITION_DEADBAND_JOBS, MOMENTUM_DEADBAND_JOBS, UNEMPLOYMENT_DEADBAND_PP)
        assert result.evaluation_period == date(2020, 6, 1)


# ---------------------------------------------------------------------
# Historical regression -- REAL PAYEMS values (native FRED thousands),
# taken directly from research/labor_momentum/data/PAYEMS.csv, the
# exact data that validated labor_v1.0.
# ---------------------------------------------------------------------


def _real_payems_jobs(values_thousands: dict[date, float]) -> dict[date, float]:
    return {d: v * 1000 for d, v in values_thousands.items()}


class TestAugust2009Regression:
    """The rejected original methodology called this month
    STRENGTHENING (payrolls were still falling ~331K/month, merely
    decelerating relative to a contaminated baseline). labor_v1.0's
    frozen, redesigned methodology must classify this RECOVERING --
    never STRENGTHENING, never EXPANDING."""

    RAW_THOUSANDS = {
        date(2009, 2, 1): 133318,
        date(2009, 3, 1): 132494,
        date(2009, 4, 1): 131822,
        date(2009, 5, 1): 131466,
        date(2009, 6, 1): 131008,
        date(2009, 7, 1): 130662,
        date(2009, 8, 1): 130472,
    }

    def test_august_2009_is_recovering_not_strengthening(self):
        index = _real_payems_jobs(self.RAW_THOUSANDS)
        result = compute_employment_result(index, date(2009, 8, 1), CONDITION_DEADBAND_JOBS, MOMENTUM_DEADBAND_JOBS)
        assert result.condition == "CONTRACTING"
        assert result.momentum == "IMPROVING"
        assert result.state == "RECOVERING"
        assert result.state != "STRENGTHENING"
        assert result.state != "EXPANDING"

    def test_august_2009_exact_values(self):
        """Pinned to the exact figures the validated research produced
        (research/labor_momentum/outputs/v2_critical_months.csv) --
        current_3m = -331,333.33, prior_3m = -617,333.33."""
        index = _real_payems_jobs(self.RAW_THOUSANDS)
        result = compute_employment_result(index, date(2009, 8, 1), CONDITION_DEADBAND_JOBS, MOMENTUM_DEADBAND_JOBS)
        assert result.current_3m_avg_jobs == pytest.approx(-331_333.33, abs=1)
        assert result.prior_3m_avg_jobs == pytest.approx(-617_333.33, abs=1)


class TestApril2021ToJune2021Regression:
    """The rejected original methodology called all three months
    COOLING (compared against a rolling 12-month baseline still
    contaminated by the 2020 COVID collapse/rebound). labor_v1.0 must
    classify EXPANDING for all three -- never COOLING."""

    RAW_THOUSANDS = {
        date(2020, 9, 1): 141770,
        date(2020, 10, 1): 142460,
        date(2020, 11, 1): 142733,
        date(2020, 12, 1): 142548,
        date(2021, 1, 1): 142863,
        date(2021, 2, 1): 143380,
        date(2021, 3, 1): 144232,
        date(2021, 4, 1): 144587,
        date(2021, 5, 1): 145065,
        date(2021, 6, 1): 145820,
    }

    @pytest.mark.parametrize("month", [date(2021, 4, 1), date(2021, 5, 1), date(2021, 6, 1)])
    def test_never_cooling(self, month: date):
        index = _real_payems_jobs(self.RAW_THOUSANDS)
        result = compute_employment_result(index, month, CONDITION_DEADBAND_JOBS, MOMENTUM_DEADBAND_JOBS)
        assert result.state != "COOLING"
        assert result.condition == "EXPANDING"

    def test_april_and_may_2021_are_expanding_improving(self):
        index = _real_payems_jobs(self.RAW_THOUSANDS)
        for month in (date(2021, 4, 1), date(2021, 5, 1)):
            result = compute_employment_result(index, month, CONDITION_DEADBAND_JOBS, MOMENTUM_DEADBAND_JOBS)
            assert result.momentum == "IMPROVING"
            assert result.state == "EXPANDING"

    def test_june_2021_is_expanding_steady(self):
        """The validated research found June 2021 lands on STEADY
        momentum (current_3m=529,333 vs prior_3m=561,333, a small
        deceleration inside the 50,000 band) -- still EXPANDING, not
        COOLING, since the deceleration itself doesn't cross the
        momentum deadband."""
        index = _real_payems_jobs(self.RAW_THOUSANDS)
        result = compute_employment_result(index, date(2021, 6, 1), CONDITION_DEADBAND_JOBS, MOMENTUM_DEADBAND_JOBS)
        assert result.momentum == "STEADY"
        assert result.state == "EXPANDING"


# ---------------------------------------------------------------------
# Affected horizons -- the frozen, empirically-verified {0, 3, 6}
# sparse set (LABOR_V1_FROZEN_METHODOLOGY.md §13), NOT a contiguous
# range. This is the single most important revision-propagation
# regression this specification names explicitly.
# ---------------------------------------------------------------------


class TestPayemsAffectedHorizons:
    def _index_around(self, anchor: date, span: int = 12) -> dict[date, float]:
        return {month_before(anchor, n): 150_000_000.0 + n * 137.0 for n in range(-span, span + 1)}

    def test_a_level_revision_affects_exactly_offsets_0_3_and_6(self):
        m = date(2015, 3, 1)  # a quiet period, deliberately away from COVID
        baseline = self._index_around(m)
        revised = dict(baseline)
        revised[m] = revised[m] + 500_000.0

        changed_offsets = []
        for offset in range(-2, 10):
            t = month_before(m, -offset)  # t = m + offset
            b = compute_employment_result(baseline, t, CONDITION_DEADBAND_JOBS, MOMENTUM_DEADBAND_JOBS)
            r = compute_employment_result(revised, t, CONDITION_DEADBAND_JOBS, MOMENTUM_DEADBAND_JOBS)
            if b.current_3m_avg_jobs != r.current_3m_avg_jobs or b.prior_3m_avg_jobs != r.prior_3m_avg_jobs:
                changed_offsets.append(offset)

        assert sorted(changed_offsets) == [0, 3, 6]

    def test_offsets_1_and_2_are_unaffected_by_cancellation(self):
        """The non-obvious property this whole regression exists to
        pin: a window containing BOTH monthly_change(M) and
        monthly_change(M+1) sees the revision's opposite-signed effects
        cancel exactly -- offsets 1 and 2 must show NO change at all,
        not merely "less change." """
        m = date(2015, 3, 1)
        baseline = self._index_around(m)
        revised = dict(baseline)
        revised[m] = revised[m] + 500_000.0

        for offset in (1, 2):
            t = month_before(m, -offset)
            b = compute_employment_result(baseline, t, CONDITION_DEADBAND_JOBS, MOMENTUM_DEADBAND_JOBS)
            r = compute_employment_result(revised, t, CONDITION_DEADBAND_JOBS, MOMENTUM_DEADBAND_JOBS)
            assert b.current_3m_avg_jobs == r.current_3m_avg_jobs
            assert b.prior_3m_avg_jobs == r.prior_3m_avg_jobs


class TestUnrateAffectedHorizons:
    def _index_around(self, anchor: date, span: int = 16) -> dict[date, float]:
        return {month_before(anchor, n): 4.0 + n * 0.01 for n in range(-span, span + 1)}

    def test_a_revision_affects_exactly_the_two_disjoint_clusters(self):
        m = date(2015, 3, 1)
        baseline = self._index_around(m)
        revised = dict(baseline)
        revised[m] = revised[m] + 1.0

        changed_offsets = []
        for offset in range(-2, 17):
            t = month_before(m, -offset)
            b = compute_unemployment_result(baseline, t, UNEMPLOYMENT_DEADBAND_PP)
            r = compute_unemployment_result(revised, t, UNEMPLOYMENT_DEADBAND_PP)
            if b.current_3m_avg != r.current_3m_avg or b.prior_year_3m_avg != r.prior_year_3m_avg:
                changed_offsets.append(offset)

        assert sorted(changed_offsets) == [0, 1, 2, 12, 13, 14]
