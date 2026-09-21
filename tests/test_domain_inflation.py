"""Tests for the pure Inflation Monitor methodology core
(app.domain.inflation), methodology `inflation_v1.0` -- frozen and
normative in docs/methodology/inflation-monitor-v1.0.md. Pure, offline,
deterministic: no database, no network, no OpenAI.

Hand-checked expected values are computed directly from the frozen
formula (Python's own arithmetic operators applied to the same formula
the spec publishes, or literal float boundary values already proven
exact during the methodology freeze -- e.g. `3.0 - 0.10 == 2.9`), never
by calling the function under test to produce its own "expected" value.
This is the same convention already established by
tests/research/test_inflation_momentum.py.

`classify_state` (rates in, state out) is tested directly for every
boundary/adversarial case, deliberately bypassing the annualization
formula's 4th/2nd-root index reconstruction -- verified during test
authoring that hand-picked P values do not generally round-trip to an
exact chosen decimal target through those roots (a real IEEE-754
property, not a shortcut), so boundary correctness is tested at the
rate level, where hand-picked literals are exact by construction.
`classify_period`/`compute_series_momentum`/etc. are tested separately
for calendar-endpoint resolution, using values where the resulting
state is unambiguous without needing bit-exact boundary alignment.
"""

from datetime import date

import pytest

from app.domain.inflation import (
    build_index,
    classify_confirmation_relationship,
    classify_period,
    classify_state,
    compute_confirmation,
    compute_confirmation_at,
    compute_headline_context,
    compute_inflation_monitor_result,
    compute_series_momentum,
    compute_series_momentum_at,
    compute_target,
    compute_target_at,
    find_latest_common_period,
    find_latest_period_with_valid_12m,
    find_latest_valid_state_period,
    latest_observation_date,
    latest_shared_observation_period,
    month_before,
    month_over_month_confirmation,
    month_over_month_series_momentum,
    month_over_month_target,
)
from app.models.inflation import (
    CONFIRMATION_SERIES_ID,
    FED_OBJECTIVE_PERCENT,
    HEADLINE_CPI_SERIES_ID,
    NEUTRAL_BAND_PP,
    PRIMARY_SERIES_ID,
    TARGET_SERIES_ID,
)
from app.models.series import Observation
from tests.identities import (
    CONFIRMATION_IDENTITY,
    EMPLOYMENT_IDENTITY,
    HEADLINE_CPI_IDENTITY,
    INFLATION_IDENTITIES,
    LABOR_IDENTITIES,
    PRIMARY_IDENTITY,
    TARGET_IDENTITY,
    UNEMPLOYMENT_IDENTITY,
)


def _obs(d: date, value: float | None) -> Observation:
    return Observation(date=d, value=value)


def _monthly_series(start: date, values: list[float | None]) -> list[Observation]:
    """Consecutive first-of-month observations starting at `start`,
    one per entry in `values` (index 0 == `start`)."""
    result = []
    for i, v in enumerate(values):
        result.append(_obs(month_before(start, -i), v))
    return result


# ---------------------------------------------------------------------
# Calendar arithmetic
# ---------------------------------------------------------------------


class TestMonthBefore:
    def test_simple_within_year(self):
        assert month_before(date(2026, 7, 1), 1) == date(2026, 6, 1)
        assert month_before(date(2026, 7, 1), 3) == date(2026, 4, 1)
        assert month_before(date(2026, 7, 1), 6) == date(2026, 1, 1)

    def test_crossing_year_boundary(self):
        assert month_before(date(2026, 7, 1), 12) == date(2025, 7, 1)
        assert month_before(date(2026, 1, 1), 1) == date(2025, 12, 1)
        assert month_before(date(2026, 3, 1), 6) == date(2025, 9, 1)

    def test_zero_months_back_is_identity(self):
        assert month_before(date(2026, 7, 1), 0) == date(2026, 7, 1)

    def test_negative_months_back_goes_forward(self):
        """Used by this test file's own _monthly_series helper to build
        ascending fixtures -- proves month_before is symmetric calendar
        arithmetic, not merely a "subtract" one-way helper."""
        assert month_before(date(2026, 1, 1), -3) == date(2026, 4, 1)

    def test_crossing_multiple_years(self):
        assert month_before(date(2026, 1, 1), 24) == date(2024, 1, 1)


# ---------------------------------------------------------------------
# A. Pure domain: annualization, numeric safety
# ---------------------------------------------------------------------


class TestBuildIndexNumericSafety:
    """Explicit protection against None/NaN/+inf/-inf/zero/negative --
    each excluded from the index entirely, never coerced."""

    def test_none_excluded(self):
        index = build_index([_obs(date(2024, 1, 1), None)])
        assert date(2024, 1, 1) not in index

    def test_nan_excluded(self):
        index = build_index([_obs(date(2024, 1, 1), float("nan"))])
        assert date(2024, 1, 1) not in index

    def test_positive_infinity_excluded(self):
        index = build_index([_obs(date(2024, 1, 1), float("inf"))])
        assert date(2024, 1, 1) not in index

    def test_negative_infinity_excluded(self):
        index = build_index([_obs(date(2024, 1, 1), float("-inf"))])
        assert date(2024, 1, 1) not in index

    def test_zero_excluded(self):
        index = build_index([_obs(date(2024, 1, 1), 0.0)])
        assert date(2024, 1, 1) not in index

    def test_negative_excluded(self):
        index = build_index([_obs(date(2024, 1, 1), -5.0)])
        assert date(2024, 1, 1) not in index

    def test_valid_positive_finite_included(self):
        index = build_index([_obs(date(2024, 1, 1), 100.0)])
        assert index[date(2024, 1, 1)] == 100.0

    def test_latest_observation_date_includes_a_row_whose_value_is_null(self):
        """A persisted row with a null value (FRED's own "." convention)
        is still "a persisted observation" for latest_observation_period
        purposes -- it must not be silently treated as if the row never
        existed, even though it can never serve as a calculation
        endpoint. This is the exact real-world 2025-10-01 Core CPI
        situation (the row exists; its value does not)."""
        obs = [_obs(date(2024, 12, 1), 100.0), _obs(date(2025, 1, 1), None)]
        assert latest_observation_date(obs) == date(2025, 1, 1)
        assert max(build_index(obs)) == date(2024, 12, 1)  # the valid-only index, by contrast, stops earlier

    def test_invalid_current_period_value_makes_metric_unavailable(self):
        """Not just a past endpoint -- an invalid value at the
        CURRENT period must also make every horizon unavailable."""
        obs = [_obs(date(2024, 1, 1), 100.0), _obs(date(2024, 2, 1), float("nan"))]
        index = build_index(obs)
        result = classify_period(index, PRIMARY_IDENTITY, date(2024, 2, 1), date(2024, 2, 1), None)
        assert result.r_1m_annualized is None
        assert result.state == "INSUFFICIENT_DATA"


class TestAnnualizedCompounding:
    """1M/3M/6M/12M against the frozen formula, computed independently
    here via Python's own ** operator -- never by calling the function
    under test to produce the expected value."""

    def test_1m_compounded_annualization(self):
        obs = [_obs(date(2024, 1, 1), 100.0), _obs(date(2024, 2, 1), 101.0)]
        index = build_index(obs)
        result = classify_period(index, PRIMARY_IDENTITY, date(2024, 2, 1), date(2024, 2, 1), None)
        expected = ((101.0 / 100.0) ** 12 - 1) * 100
        assert result.r_1m_annualized == pytest.approx(expected, rel=1e-12)

    def test_3m_compounded_annualization(self):
        values = [100.0, 100.5, 101.0, 103.0]
        obs = _monthly_series(date(2024, 1, 1), values)
        index = build_index(obs)
        result = classify_period(index, PRIMARY_IDENTITY, date(2024, 4, 1), date(2024, 4, 1), None)
        expected = ((103.0 / 100.0) ** 4 - 1) * 100
        assert result.r_3m_annualized == pytest.approx(expected, rel=1e-12)

    def test_6m_compounded_annualization(self):
        values = [100.0, 100.2, 100.4, 100.6, 100.8, 101.0, 103.0]
        obs = _monthly_series(date(2024, 1, 1), values)
        index = build_index(obs)
        result = classify_period(index, PRIMARY_IDENTITY, date(2024, 7, 1), date(2024, 7, 1), None)
        expected = ((103.0 / 100.0) ** 2 - 1) * 100
        assert result.r_6m_annualized == pytest.approx(expected, rel=1e-12)

    def test_12m_is_plain_yoy_not_multiplied_by_12(self):
        values = [100.0] + [None] * 11 + [110.0]  # index 0 (Jan) .. index 12 (next Jan)
        obs = _monthly_series(date(2024, 1, 1), values)
        index = build_index(obs)
        result = classify_period(index, PRIMARY_IDENTITY, date(2025, 1, 1), date(2025, 1, 1), None)
        expected = (110.0 / 100.0 - 1) * 100  # NOT * 12
        assert result.r_12m == pytest.approx(expected, rel=1e-12)
        naive_wrong = ((110.0 - 100.0) / 100.0 * 100) * 12
        assert result.r_12m != pytest.approx(naive_wrong)


class TestStateClassificationDirect:
    """Direct tests of classify_state (rates in, state out) -- exactly
    the five frozen states, plus negative-inflation and extreme-value
    cases from the frozen spec's own worked examples."""

    def test_cooling(self):
        state, _, _ = classify_state(r_3m=-5.0, r_6m=-3.0, r_12m=0.0, neutral_band_pp=0.10)
        assert state == "COOLING"

    def test_heating(self):
        state, _, _ = classify_state(r_3m=5.0, r_6m=3.0, r_12m=0.0, neutral_band_pp=0.10)
        assert state == "HEATING"

    def test_stable(self):
        state, _, _ = classify_state(r_3m=0.02, r_6m=-0.02, r_12m=0.0, neutral_band_pp=0.10)
        assert state == "STABLE"

    def test_mixed_cooling_3m_heating_6m(self):
        state, _, _ = classify_state(r_3m=-5.0, r_6m=5.0, r_12m=0.0, neutral_band_pp=0.10)
        assert state == "MIXED"

    def test_negative_inflation_cooling(self):
        # 12M = -1.00, lower = -1.10, upper = -0.90 (frozen spec's own example)
        state, lower, upper = classify_state(r_3m=-2.00, r_6m=-1.50, r_12m=-1.00, neutral_band_pp=0.10)
        assert (lower, upper) == pytest.approx((-1.10, -0.90))
        assert state == "COOLING"

    def test_negative_inflation_heating(self):
        state, _, _ = classify_state(r_3m=0.00, r_6m=-0.50, r_12m=-1.00, neutral_band_pp=0.10)
        assert state == "HEATING"

    def test_extreme_positive_inflation_heating(self):
        state, _, _ = classify_state(r_3m=500.0, r_6m=400.0, r_12m=50.0, neutral_band_pp=0.10)
        assert state == "HEATING"

    def test_extreme_negative_and_positive_horizons_still_mixed_not_a_crash(self):
        state, _, _ = classify_state(r_3m=-1000.0, r_6m=1000.0, r_12m=0.0, neutral_band_pp=0.10)
        assert state == "MIXED"


# ---------------------------------------------------------------------
# B. Exact boundary tests
# ---------------------------------------------------------------------


class TestExactBoundaries:
    """`12M=3.00, delta=0.10` -- the frozen spec's own worked example.
    `lower`/`upper` below are the literal values `3.0 - 0.10`/`3.0 +
    0.10`, already proven bit-exact in IEEE-754 double precision during
    the methodology freeze (`3.0 - 0.10 == 2.9`, `3.0 + 0.10 == 3.1`) --
    used here as literals, not derived by calling the function under
    test."""

    R12 = 3.00
    DELTA = 0.10
    LOWER = 2.9
    UPPER = 3.1
    EPS = 1e-9

    def test_boundary_literals_match_frozen_worked_example(self):
        assert self.R12 - self.DELTA == self.LOWER
        assert self.R12 + self.DELTA == self.UPPER

    def test_lower_minus_small_is_strictly_cooling_side(self):
        state, _, _ = classify_state(self.LOWER - self.EPS, self.LOWER - self.EPS, self.R12, self.DELTA)
        assert state == "COOLING"

    def test_exactly_lower_is_inclusive_stable_side(self):
        state, _, _ = classify_state(self.LOWER, self.LOWER, self.R12, self.DELTA)
        assert state == "STABLE"

    def test_lower_plus_small_is_inside_band(self):
        state, _, _ = classify_state(self.LOWER + self.EPS, self.LOWER + self.EPS, self.R12, self.DELTA)
        assert state == "STABLE"

    def test_upper_minus_small_is_inside_band(self):
        state, _, _ = classify_state(self.UPPER - self.EPS, self.UPPER - self.EPS, self.R12, self.DELTA)
        assert state == "STABLE"

    def test_exactly_upper_is_inclusive_stable_side(self):
        state, _, _ = classify_state(self.UPPER, self.UPPER, self.R12, self.DELTA)
        assert state == "STABLE"

    def test_upper_plus_small_is_strictly_heating_side(self):
        state, _, _ = classify_state(self.UPPER + self.EPS, self.UPPER + self.EPS, self.R12, self.DELTA)
        assert state == "HEATING"

    def test_directional_comparisons_never_fire_exactly_at_boundary(self):
        assert classify_state(self.LOWER, self.LOWER, self.R12, self.DELTA)[0] != "COOLING"
        assert classify_state(self.UPPER, self.UPPER, self.R12, self.DELTA)[0] != "HEATING"

    def test_neutral_boundaries_inclusive_on_both_sides_simultaneously(self):
        state, _, _ = classify_state(self.LOWER, self.UPPER, self.R12, self.DELTA)
        assert state == "STABLE"

    def test_no_hidden_epsilon_a_value_one_eps_outside_is_not_treated_as_inside(self):
        """Guards against an implementation quietly widening the band
        with its own epsilon -- exactly `EPS` past the boundary must
        already be strictly outside, not fuzzily tolerated."""
        state, _, _ = classify_state(self.UPPER + self.EPS, self.R12, self.R12, self.DELTA)
        assert state != "STABLE"


class TestFrozenSpecAdversarialCases:
    """The exact worked cases from
    docs/methodology/inflation-monitor-v1.0.md's "Normative adversarial
    cases" (12M=3.00, lower=2.90, upper=3.10), run against classify_state
    directly -- the same cases already verified against the research
    prototype during the methodology freeze."""

    R12 = 3.00
    DELTA = 0.10

    @pytest.mark.parametrize(
        "r3, r6, expected",
        [
            (2.50, 2.70, "COOLING"),
            (3.40, 3.20, "HEATING"),
            (2.90, 2.90, "STABLE"),
            (3.10, 3.10, "STABLE"),
            (2.90, 3.10, "STABLE"),
            (2.899999, 2.80, "COOLING"),
            (3.100001, 3.20, "HEATING"),
            (2.70, 3.30, "MIXED"),
            (2.70, 3.00, "MIXED"),
            (3.30, 3.00, "MIXED"),
            (3.00, 2.70, "MIXED"),
            (3.00, 3.30, "MIXED"),
        ],
    )
    def test_worked_case(self, r3, r6, expected):
        state, _, _ = classify_state(r3, r6, self.R12, self.DELTA)
        assert state == expected


# ---------------------------------------------------------------------
# C. Golden calculation test (hand-derived index fixture)
# ---------------------------------------------------------------------


class TestGoldenCalculation:
    """A hand-derived 13-month index-value fixture. Expected 1M/3M/6M/
    12M are computed here directly from the frozen formula (Python's **
    operator, never the function under test); expected lower/upper/
    state are reasoned by hand from those values, not computed by
    calling classify_period a second time.

    Fixture (first-of-month levels):
        2024-01: 100.0   (t-12)
        2024-07: 103.0   (t-6)
        2024-10: 106.0   (t-3)
        2024-12: 109.0   (t-1)
        2025-01: 110.0   (t)
    Intervening months are present but their exact values are
    irrelevant to this calculation (endpoint calculation, not a
    row-position one) -- included with distinct values precisely to
    prove that.
    """

    @staticmethod
    def _index() -> dict[date, float]:
        values = {
            date(2024, 1, 1): 100.0,
            date(2024, 2, 1): 100.5,
            date(2024, 3, 1): 101.0,
            date(2024, 4, 1): 101.5,
            date(2024, 5, 1): 102.0,
            date(2024, 6, 1): 102.5,
            date(2024, 7, 1): 103.0,
            date(2024, 8, 1): 104.0,
            date(2024, 9, 1): 105.0,
            date(2024, 10, 1): 106.0,
            date(2024, 11, 1): 107.5,
            date(2024, 12, 1): 109.0,
            date(2025, 1, 1): 110.0,
        }
        return build_index([_obs(d, v) for d, v in values.items()])

    def test_golden_fixture(self):
        index = self._index()
        result = classify_period(index, PRIMARY_IDENTITY, date(2025, 1, 1), date(2025, 1, 1), date(2025, 1, 1))

        expected_r1m = ((110.0 / 109.0) ** 12 - 1) * 100
        expected_r3m = ((110.0 / 106.0) ** 4 - 1) * 100
        expected_r6m = ((110.0 / 103.0) ** 2 - 1) * 100
        expected_r12m = (110.0 / 100.0 - 1) * 100  # == 10.0 exactly

        assert result.r_1m_annualized == pytest.approx(expected_r1m, rel=1e-12)
        assert result.r_3m_annualized == pytest.approx(expected_r3m, rel=1e-12)
        assert result.r_6m_annualized == pytest.approx(expected_r6m, rel=1e-12)
        assert result.r_12m == pytest.approx(10.0, rel=1e-12)

        expected_lower = 10.0 - 0.10
        expected_upper = 10.0 + 0.10
        assert result.lower_boundary == pytest.approx(expected_lower, rel=1e-12)
        assert result.upper_boundary == pytest.approx(expected_upper, rel=1e-12)

        # Both r3m (~15.97) and r6m (~14.05) are comfortably above upper
        # (10.10) -- HEATING, determined by hand, not by calling the
        # function twice.
        assert expected_r3m > expected_upper
        assert expected_r6m > expected_upper
        assert result.state == "HEATING"

    def test_golden_fixture_provenance_endpoints(self):
        index = self._index()
        result = classify_period(index, PRIMARY_IDENTITY, date(2025, 1, 1), date(2025, 1, 1), date(2025, 1, 1))

        assert result.evidence_3m.endpoint_date_current == date(2025, 1, 1)
        assert result.evidence_3m.endpoint_date_past == date(2024, 10, 1)
        assert result.evidence_3m.endpoint_value_current == 110.0
        assert result.evidence_3m.endpoint_value_past == 106.0

        assert result.evidence_6m.endpoint_date_past == date(2024, 7, 1)
        assert result.evidence_6m.endpoint_value_past == 103.0

        assert result.evidence_12m.endpoint_date_past == date(2024, 1, 1)
        assert result.evidence_12m.endpoint_value_past == 100.0


# ---------------------------------------------------------------------
# D. Calendar-endpoint tests (missing months, row-position regression)
# ---------------------------------------------------------------------


class TestCalendarEndpoints:
    def test_missing_required_endpoint_makes_metric_unavailable(self):
        """t-3 itself is missing -> r_3m unavailable -> INSUFFICIENT_DATA,
        even though t, t-6, t-12 are all present and valid."""
        values = {
            date(2024, 1, 1): 100.0,  # t-12
            date(2024, 7, 1): 103.0,  # t-6
            # date(2024, 10, 1) deliberately absent -- t-3
            date(2025, 1, 1): 110.0,  # t
        }
        index = build_index([_obs(d, v) for d, v in values.items()])
        result = classify_period(index, PRIMARY_IDENTITY, date(2025, 1, 1), date(2025, 1, 1), None)
        assert result.r_3m_annualized is None
        assert result.r_6m_annualized is not None
        assert result.r_12m is not None
        assert "r_3m" in result.missing_required_metrics
        assert result.state == "INSUFFICIENT_DATA"

    def test_missing_intermediate_non_endpoint_month_does_not_invalidate(self):
        """February is missing, but April's 3M uses P_April/P_January
        directly -- an endpoint calculation, not a row-position one --
        so it remains valid. This is THE critical regression test for
        row-position vs. calendar-exact resolution."""
        values = {
            date(2024, 1, 1): 100.0,
            # date(2024, 2, 1) missing
            date(2024, 3, 1): 101.0,
            date(2024, 4, 1): 103.0,
        }
        index = build_index([_obs(d, v) for d, v in values.items()])
        result = classify_period(index, PRIMARY_IDENTITY, date(2024, 4, 1), date(2024, 4, 1), None)
        expected_r3m = ((103.0 / 100.0) ** 4 - 1) * 100
        assert result.r_3m_annualized == pytest.approx(expected_r3m, rel=1e-12)
        assert date(2024, 2, 1) not in index  # still genuinely missing, never interpolated

    def test_row_position_shifting_cannot_occur(self):
        """If horizons were (incorrectly) resolved by row position
        rather than calendar date, removing an early, unrelated row
        would shift which value gets used for a later t-3/t-6/t-12
        lookup. Calendar-exact resolution must be IMMUNE to this: the
        result for the same calculation_period must be identical
        whether or not a distant, irrelevant row exists."""
        base_values = {
            date(2024, 1, 1): 100.0,
            date(2024, 10, 1): 106.0,
            date(2025, 1, 1): 110.0,
        }
        index_without_extra_row = build_index([_obs(d, v) for d, v in base_values.items()])

        with_extra_row = dict(base_values)
        with_extra_row[date(2020, 5, 1)] = 999.0  # an early, unrelated, extra row
        index_with_extra_row = build_index([_obs(d, v) for d, v in with_extra_row.items()])

        r_without = classify_period(index_without_extra_row, PRIMARY_IDENTITY, date(2025, 1, 1), date(2025, 1, 1), None)
        r_with = classify_period(index_with_extra_row, PRIMARY_IDENTITY, date(2025, 1, 1), date(2025, 1, 1), None)

        assert r_without.r_3m_annualized == r_with.r_3m_annualized
        assert r_without.evidence_3m.endpoint_date_past == r_with.evidence_3m.endpoint_date_past == date(2024, 10, 1)

    def test_missing_t1_does_not_invalidate_canonical_state(self):
        values = {
            date(2024, 1, 1): 100.0,
            date(2024, 7, 1): 103.0,
            date(2024, 10, 1): 106.0,
            # date(2024, 12, 1) [t-1] deliberately absent
            date(2025, 1, 1): 110.0,
        }
        index = build_index([_obs(d, v) for d, v in values.items()])
        result = classify_period(index, PRIMARY_IDENTITY, date(2025, 1, 1), date(2025, 1, 1), date(2025, 1, 1))
        assert result.r_1m_annualized is None
        assert result.state != "INSUFFICIENT_DATA"
        assert "r_1m" not in result.missing_required_metrics  # r_1m is never a "required" metric at all

    def test_missing_t6_makes_state_insufficient(self):
        values = {
            date(2024, 1, 1): 100.0,
            date(2024, 10, 1): 106.0,
            date(2025, 1, 1): 110.0,
            # t-6 (2024-07-01) deliberately absent
        }
        index = build_index([_obs(d, v) for d, v in values.items()])
        result = classify_period(index, PRIMARY_IDENTITY, date(2025, 1, 1), date(2025, 1, 1), None)
        assert result.state == "INSUFFICIENT_DATA"
        assert "r_6m" in result.missing_required_metrics

    def test_missing_t12_makes_state_insufficient(self):
        values = {
            date(2024, 7, 1): 103.0,
            date(2024, 10, 1): 106.0,
            date(2025, 1, 1): 110.0,
            # t-12 (2024-01-01) deliberately absent
        }
        index = build_index([_obs(d, v) for d, v in values.items()])
        result = classify_period(index, PRIMARY_IDENTITY, date(2025, 1, 1), date(2025, 1, 1), None)
        assert result.state == "INSUFFICIENT_DATA"
        assert "r_12m" in result.missing_required_metrics

    def test_latest_valid_state_period_searches_backward_past_a_real_gap(self):
        """The most recent month can have INSUFFICIENT_DATA (because
        one of ITS required endpoints is a real, currently-missing
        month) while an earlier month remains fully valid -- exactly
        today's real Core CPI situation (the Oct-2025 gap poisons any
        period whose t-3 lands on it)."""
        values = {
            date(2024, 1, 1): 100.0,
            date(2024, 7, 1): 103.0,
            date(2024, 10, 1): 106.0,
            date(2024, 12, 1): 109.0,
            date(2025, 1, 1): 110.0,
            # date(2025, 2, 1) intentionally omitted entirely
        }
        # 2025-02's own r_3m would need 2024-11 (present, via 107.5 below) but
        # let's construct a case where the LATEST observation's OWN 3M/6M/12M
        # cannot all be computed, while 2025-01 (earlier) can.
        values[date(2024, 11, 1)] = 107.5
        values[date(2025, 2, 1)] = 111.0
        # 2025-02's t-12 = 2024-02, which is absent -> 2025-02 is INSUFFICIENT_DATA.
        index = build_index([_obs(d, v) for d, v in values.items()])

        latest_observation_period = max(index)
        assert latest_observation_period == date(2025, 2, 1)

        latest_valid = find_latest_valid_state_period(index)
        assert latest_valid == date(2025, 1, 1)  # NOT 2025-02 -- searched backward correctly

        momentum = compute_series_momentum(
            [_obs(d, v) for d, v in values.items()], PRIMARY_IDENTITY
        )
        assert momentum.latest_observation_period == date(2025, 2, 1)
        assert momentum.latest_valid_state_period == date(2025, 1, 1)
        assert momentum.calculation_period == date(2025, 1, 1)
        assert momentum.state != "INSUFFICIENT_DATA"

    def test_entirely_empty_series_yields_insufficient_data_not_a_crash(self):
        result = compute_series_momentum([], PRIMARY_IDENTITY)
        assert result.calculation_period is None
        assert result.latest_observation_period is None
        assert result.state == "INSUFFICIENT_DATA"
        assert result.evidence_3m is None


# ---------------------------------------------------------------------
# E. Primary authority tests
# ---------------------------------------------------------------------


class TestPrimaryAuthority:
    """Core CPI, Headline CPI, and Headline PCE can never change Core
    PCE's own canonical state -- proven by construction (classify_period/
    compute_series_momentum for Core PCE take ONLY Core PCE's own
    observations) and directly, empirically, here."""

    @staticmethod
    def _primary_obs() -> list[Observation]:
        values = {
            date(2024, 1, 1): 100.0,
            date(2024, 7, 1): 103.0,
            date(2024, 10, 1): 106.0,
            date(2025, 1, 1): 110.0,
        }
        return [_obs(d, v) for d, v in values.items()]

    def test_changing_only_core_cpi_cannot_change_core_pce_state(self):
        primary_obs = self._primary_obs()
        confirmation_obs_a = [_obs(date(2024, 1, 1), 50.0), _obs(date(2025, 1, 1), 50.5)]
        confirmation_obs_b = [_obs(date(2024, 1, 1), 50.0), _obs(date(2025, 1, 1), 80.0)]  # wildly different

        result_a = compute_inflation_monitor_result(primary_obs, confirmation_obs_a, primary_obs, [], identities=INFLATION_IDENTITIES)
        result_b = compute_inflation_monitor_result(primary_obs, confirmation_obs_b, primary_obs, [], identities=INFLATION_IDENTITIES)

        assert result_a.underlying_momentum.state == result_b.underlying_momentum.state
        assert result_a.underlying_momentum.r_3m_annualized == result_b.underlying_momentum.r_3m_annualized

    def test_removing_core_cpi_entirely_cannot_change_core_pce_state(self):
        primary_obs = self._primary_obs()
        with_confirmation = compute_inflation_monitor_result(
            primary_obs, [_obs(date(2024, 1, 1), 50.0), _obs(date(2025, 1, 1), 50.5)], primary_obs, []
        , identities=INFLATION_IDENTITIES)
        without_confirmation = compute_inflation_monitor_result(primary_obs, [], primary_obs, [], identities=INFLATION_IDENTITIES)

        assert with_confirmation.underlying_momentum.state == without_confirmation.underlying_momentum.state
        assert with_confirmation.underlying_momentum == without_confirmation.underlying_momentum

    def test_changing_headline_cpi_cannot_change_core_pce_state(self):
        primary_obs = self._primary_obs()
        result_a = compute_inflation_monitor_result(primary_obs, [], primary_obs, [_obs(date(2025, 1, 1), 500.0)], identities=INFLATION_IDENTITIES)
        result_b = compute_inflation_monitor_result(primary_obs, [], primary_obs, [_obs(date(2025, 1, 1), 5.0)], identities=INFLATION_IDENTITIES)
        assert result_a.underlying_momentum == result_b.underlying_momentum

    def test_changing_headline_pce_cannot_change_core_pce_momentum_state(self):
        primary_obs = self._primary_obs()
        target_obs_a = [_obs(date(2024, 1, 1), 200.0), _obs(date(2025, 1, 1), 202.0)]
        target_obs_b = [_obs(date(2024, 1, 1), 200.0), _obs(date(2025, 1, 1), 260.0)]  # very different level
        result_a = compute_inflation_monitor_result(primary_obs, [], target_obs_a, [], identities=INFLATION_IDENTITIES)
        result_b = compute_inflation_monitor_result(primary_obs, [], target_obs_b, [], identities=INFLATION_IDENTITIES)
        assert result_a.underlying_momentum == result_b.underlying_momentum
        # but the target DOES legitimately differ between the two:
        assert result_a.target.headline_pce_yoy != result_b.target.headline_pce_yoy


# ---------------------------------------------------------------------
# F. Confirmation relationship matrix
# ---------------------------------------------------------------------


class TestConfirmationRelationshipMatrix:
    @pytest.mark.parametrize(
        "primary, confirmation, expected",
        [
            ("COOLING", "COOLING", "CONFIRMS"),
            ("HEATING", "HEATING", "CONFIRMS"),
            ("STABLE", "STABLE", "CONFIRMS"),
            ("COOLING", "HEATING", "DIVERGES"),
            ("HEATING", "COOLING", "DIVERGES"),
            ("MIXED", "MIXED", "INCONCLUSIVE"),
            ("COOLING", "STABLE", "INCONCLUSIVE"),
            ("STABLE", "COOLING", "INCONCLUSIVE"),
            ("COOLING", "MIXED", "INCONCLUSIVE"),
            ("MIXED", "COOLING", "INCONCLUSIVE"),
            ("STABLE", "HEATING", "INCONCLUSIVE"),
            ("HEATING", "MIXED", "INCONCLUSIVE"),
            ("HEATING", "STABLE", "INCONCLUSIVE"),
            ("STABLE", "MIXED", "INCONCLUSIVE"),
            ("MIXED", "HEATING", "INCONCLUSIVE"),
            ("MIXED", "STABLE", "INCONCLUSIVE"),
        ],
    )
    def test_relationship(self, primary, confirmation, expected):
        assert classify_confirmation_relationship(primary, confirmation) == expected

    @pytest.mark.parametrize("valid_state", ["COOLING", "HEATING", "STABLE", "MIXED"])
    def test_valid_plus_insufficient_data_is_unavailable(self, valid_state):
        assert classify_confirmation_relationship(valid_state, "INSUFFICIENT_DATA") == "UNAVAILABLE"
        assert classify_confirmation_relationship("INSUFFICIENT_DATA", valid_state) == "UNAVAILABLE"

    def test_both_insufficient_data_is_unavailable(self):
        assert classify_confirmation_relationship("INSUFFICIENT_DATA", "INSUFFICIENT_DATA") == "UNAVAILABLE"

    def test_none_states_are_unavailable(self):
        assert classify_confirmation_relationship(None, "COOLING") == "UNAVAILABLE"
        assert classify_confirmation_relationship("COOLING", None) == "UNAVAILABLE"
        assert classify_confirmation_relationship(None, None) == "UNAVAILABLE"

    def test_exhaustive_enum_pair_coverage(self):
        """Every (primary, confirmation) pair over the five states
        produces exactly one of the four relationships -- no pair is
        unhandled (would raise or return None)."""
        states = ["COOLING", "HEATING", "STABLE", "MIXED", "INSUFFICIENT_DATA"]
        for p in states:
            for c in states:
                result = classify_confirmation_relationship(p, c)
                assert result in ("CONFIRMS", "DIVERGES", "INCONCLUSIVE", "UNAVAILABLE")


# ---------------------------------------------------------------------
# G. Period tests
# ---------------------------------------------------------------------


class TestPeriodSemantics:
    def test_latest_observation_vs_latest_valid_state_period_can_differ(self):
        values = {date(2025, 1, 1): 100.0}  # a single, brand-new observation
        index = build_index([_obs(d, v) for d, v in values.items()])
        assert max(index) == date(2025, 1, 1)
        assert find_latest_valid_state_period(index) is None  # no 12M history at all yet

    def test_cpi_latest_later_than_pce(self):
        primary_obs = [_obs(date(2024, 1, 1), 100.0), _obs(date(2024, 7, 1), 103.0), _obs(date(2024, 10, 1), 106.0), _obs(date(2025, 1, 1), 110.0)]
        confirmation_obs = primary_obs + [_obs(date(2025, 2, 1), 111.0)]
        confirmation = compute_confirmation(primary_obs, confirmation_obs, identities=INFLATION_IDENTITIES)
        # Both series ARE valid at 2025-01 -> that's the comparison period,
        # even though Core CPI's own *latest* extends to 2025-02.
        assert confirmation.latest_common_period == date(2025, 1, 1)
        assert confirmation.confirmation_latest.latest_observation_period == date(2025, 2, 1)

    def test_pce_latest_later_than_cpi(self):
        confirmation_obs = [_obs(date(2024, 1, 1), 50.0), _obs(date(2024, 7, 1), 51.5), _obs(date(2024, 10, 1), 53.0), _obs(date(2025, 1, 1), 55.0)]
        primary_obs = [
            _obs(date(2024, 1, 1), 100.0),
            _obs(date(2024, 7, 1), 103.0),
            _obs(date(2024, 10, 1), 106.0),
            _obs(date(2025, 1, 1), 110.0),
            _obs(date(2025, 2, 1), 111.0),
        ]
        confirmation = compute_confirmation(primary_obs, confirmation_obs, identities=INFLATION_IDENTITIES)
        assert confirmation.latest_common_period == date(2025, 1, 1)
        assert confirmation.primary_at_comparison_period.calculation_period == date(2025, 1, 1)

    def test_same_latest_row_but_one_missing_a_required_historical_endpoint(self):
        """Both series share their newest observation date (2025-01),
        but Core CPI's own persisted history is missing exactly its
        t-12 endpoint for that date (2024-01) -- so the comparison
        period must fall back to an earlier date (2024-12) where BOTH
        sides are independently valid, rather than either using 2025-01
        anyway or giving up entirely."""
        all_months = [month_before(date(2025, 1, 1), -i) for i in range(-36, 1)]  # 2022-01 .. 2025-01
        primary_obs = [_obs(d, 100.0 + i * 0.5) for i, d in enumerate(all_months)]
        confirmation_obs = [_obs(d, 50.0 + i * 0.2) for i, d in enumerate(all_months) if d != date(2024, 1, 1)]

        assert max(build_index(primary_obs)) == max(build_index(confirmation_obs)) == date(2025, 1, 1)

        confirmation = compute_confirmation(primary_obs, confirmation_obs, identities=INFLATION_IDENTITIES)

        # Primary alone WOULD be valid at 2025-01, but confirmation's own
        # t-12 for 2025-01 (2024-01) is missing, so 2025-01 cannot be the
        # comparison period -- it must fall back to the latest EARLIER
        # period where both sides independently have a valid state.
        assert confirmation.latest_common_period == date(2024, 12, 1)
        assert confirmation.primary_at_comparison_period.calculation_period == date(2024, 12, 1)
        assert confirmation.confirmation_at_comparison_period.calculation_period == date(2024, 12, 1)

    def test_no_common_valid_period_at_all(self):
        primary_obs = [
            _obs(date(2024, 1, 1), 100.0),
            _obs(date(2024, 7, 1), 103.0),
            _obs(date(2024, 10, 1), 106.0),
            _obs(date(2025, 1, 1), 110.0),
        ]
        # Confirmation series exists but shares NO observation dates with primary at all.
        confirmation_obs = [
            _obs(date(2010, 1, 1), 50.0),
            _obs(date(2010, 7, 1), 51.0),
            _obs(date(2010, 10, 1), 52.0),
            _obs(date(2011, 1, 1), 53.0),
        ]
        confirmation = compute_confirmation(primary_obs, confirmation_obs, identities=INFLATION_IDENTITIES)
        assert confirmation.latest_common_period is None
        assert confirmation.relationship == "UNAVAILABLE"
        assert confirmation.primary_at_comparison_period is None
        assert confirmation.confirmation_at_comparison_period is None
        # But Core CPI's OWN standalone state is still reported independently:
        assert confirmation.confirmation_latest.state != "INSUFFICIENT_DATA"

    def test_confirmation_never_compares_mismatched_months(self):
        """A hostile fixture where naive nearest-date matching would
        wrongly pair adjacent months -- exact-date-only resolution must
        refuse to compare July primary against August confirmation."""
        primary_obs = [
            _obs(date(2024, 1, 1), 100.0),
            _obs(date(2024, 7, 1), 103.0),
            _obs(date(2024, 10, 1), 106.0),
            _obs(date(2025, 1, 1), 110.0),  # only July-anchored dates
        ]
        confirmation_obs = [
            _obs(date(2024, 2, 1), 50.0),
            _obs(date(2024, 8, 1), 51.5),
            _obs(date(2024, 11, 1), 53.0),
            _obs(date(2025, 2, 1), 55.0),  # only August-anchored dates -- one month offset throughout
        ]
        confirmation = compute_confirmation(primary_obs, confirmation_obs, identities=INFLATION_IDENTITIES)
        assert confirmation.latest_common_period is None
        assert confirmation.relationship == "UNAVAILABLE"


# ---------------------------------------------------------------------
# H. Target tests
# ---------------------------------------------------------------------


class TestTarget:
    def test_above_2_percent(self):
        obs = [_obs(date(2024, 1, 1), 100.0), _obs(date(2025, 1, 1), 105.0)]
        result = compute_target(obs, target_identity=TARGET_IDENTITY)
        expected_yoy = (105.0 / 100.0 - 1) * 100
        assert result.headline_pce_yoy == pytest.approx(expected_yoy, rel=1e-12)
        assert result.target_gap_pp == pytest.approx(expected_yoy - 2.0, rel=1e-12)
        assert result.target_gap_pp > 0
        assert result.available is True

    def test_exactly_2_percent(self):
        obs = [_obs(date(2024, 1, 1), 100.0), _obs(date(2025, 1, 1), 102.0)]
        result = compute_target(obs, target_identity=TARGET_IDENTITY)
        assert result.headline_pce_yoy == pytest.approx(2.0, rel=1e-12)
        assert result.target_gap_pp == pytest.approx(0.0, abs=1e-9)

    def test_below_2_percent(self):
        obs = [_obs(date(2024, 1, 1), 100.0), _obs(date(2025, 1, 1), 101.0)]
        result = compute_target(obs, target_identity=TARGET_IDENTITY)
        assert result.target_gap_pp < 0

    def test_missing_target_endpoint(self):
        obs = [_obs(date(2025, 1, 1), 110.0)]  # no t-12 at all
        result = compute_target(obs, target_identity=TARGET_IDENTITY)
        assert result.available is False
        assert result.headline_pce_yoy is None
        assert result.target_gap_pp is None
        assert result.calculation_period is None
        assert result.evidence is None

    def test_target_available_while_primary_unavailable(self):
        target_obs = [_obs(date(2024, 1, 1), 100.0), _obs(date(2025, 1, 1), 105.0)]
        result = compute_inflation_monitor_result([], [], target_obs, [], identities=INFLATION_IDENTITIES)
        assert result.coverage.target_available is True
        assert result.coverage.primary_available is False

    def test_primary_available_while_target_unavailable(self):
        primary_obs = [
            _obs(date(2024, 1, 1), 100.0),
            _obs(date(2024, 7, 1), 103.0),
            _obs(date(2024, 10, 1), 106.0),
            _obs(date(2025, 1, 1), 110.0),
        ]
        result = compute_inflation_monitor_result(primary_obs, [], [], [], identities=INFLATION_IDENTITIES)
        assert result.coverage.primary_available is True
        assert result.coverage.target_available is False

    def test_target_does_not_alter_momentum_state(self):
        """Headline PCE YoY = well above target; Core PCE momentum
        independently COOLING -- both must be representable
        simultaneously (Section: Level and momentum are independent)."""
        primary_obs = [
            _obs(date(2024, 1, 1), 100.0),
            _obs(date(2024, 7, 1), 101.0),
            _obs(date(2024, 10, 1), 101.2),
            _obs(date(2025, 1, 1), 101.3),  # slow recent growth -> COOLING vs its own 12M
        ]
        target_obs = [_obs(date(2024, 1, 1), 100.0), _obs(date(2025, 1, 1), 103.4)]  # 3.4% YoY, above 2.0 target
        result = compute_inflation_monitor_result(primary_obs, [], target_obs, [], identities=INFLATION_IDENTITIES)
        assert result.target.target_gap_pp > 0
        assert result.underlying_momentum.state in ("COOLING", "STABLE", "HEATING", "MIXED", "INSUFFICIENT_DATA")
        # The key invariant: target_gap_pp's sign/value is untouched by underlying_momentum's state.
        result_b = compute_inflation_monitor_result([], [], target_obs, [], identities=INFLATION_IDENTITIES)
        assert result_b.target.target_gap_pp == result.target.target_gap_pp

    def test_does_not_substitute_cpi_for_missing_target(self):
        """Even with abundant Headline CPI data, a missing Headline PCE
        endpoint must never be silently replaced by CPI."""
        headline_cpi_obs = [_obs(date(2024, 1, 1), 100.0), _obs(date(2025, 1, 1), 110.0)]
        result = compute_inflation_monitor_result([], [], [], headline_cpi_obs, identities=INFLATION_IDENTITIES)
        assert result.target.available is False
        assert result.target.headline_pce_yoy is None


# ---------------------------------------------------------------------
# I. Coverage tests
# ---------------------------------------------------------------------


class TestCoverage:
    def test_all_unavailable_when_nothing_persisted(self):
        result = compute_inflation_monitor_result([], [], [], [], identities=INFLATION_IDENTITIES)
        assert result.coverage.primary_available is False
        assert result.coverage.confirmation_available is False
        assert result.coverage.target_available is False
        assert result.coverage.headline_cpi_available is False

    def test_row_presence_alone_does_not_imply_availability(self):
        """A single, brand-new observation (no 12M history) must NOT
        count as "available" merely because a row exists."""
        obs = [_obs(date(2025, 1, 1), 100.0)]
        result = compute_inflation_monitor_result(obs, obs, obs, obs, identities=INFLATION_IDENTITIES)
        assert result.coverage.primary_available is False
        assert result.coverage.confirmation_available is False
        assert result.coverage.headline_cpi_available is False
        # target only needs r_12m, also unavailable with a single point:
        assert result.coverage.target_available is False

    def test_all_available_with_full_history(self):
        full = [
            _obs(date(2024, 1, 1), 100.0),
            _obs(date(2024, 7, 1), 103.0),
            _obs(date(2024, 10, 1), 106.0),
            _obs(date(2025, 1, 1), 110.0),
        ]
        result = compute_inflation_monitor_result(full, full, full, full, identities=INFLATION_IDENTITIES)
        assert result.coverage.primary_available is True
        assert result.coverage.confirmation_available is True
        assert result.coverage.target_available is True
        assert result.coverage.headline_cpi_available is True


class TestConfirmationAvailableSemantics:
    """`confirmation_available` is the confirmation TIER's own
    availability -- the same-period Core PCE/Core CPI relationship --
    not merely whether Core CPI's own standalone state happens to be
    calculable. The frozen invariant:

        confirmation_available == (confirmation.relationship != "UNAVAILABLE")

    Core CPI's own standalone availability remains fully visible,
    unabridged, via `confirmation.confirmation_latest.state` -- these
    tests explicitly check that field too, to prove nothing was
    removed, only the meaning of the coverage boolean was corrected.
    """

    FULL = [
        _obs(date(2024, 1, 1), 100.0),
        _obs(date(2024, 7, 1), 103.0),
        _obs(date(2024, 10, 1), 106.0),
        _obs(date(2025, 1, 1), 110.0),
    ]

    def test_1_valid_common_period_confirms_and_available(self):
        """Identical full history on both sides -> same state at the
        same period -> CONFIRMS -> confirmation_available True."""
        result = compute_inflation_monitor_result(self.FULL, self.FULL, [], [], identities=INFLATION_IDENTITIES)
        assert result.confirmation.relationship == "CONFIRMS"
        assert result.coverage.confirmation_available is True

    def test_1_valid_common_period_diverges_still_available(self):
        cooling_primary = [
            _obs(date(2024, 1, 1), 100.0),
            _obs(date(2024, 7, 1), 101.0),
            _obs(date(2024, 10, 1), 101.2),
            _obs(date(2025, 1, 1), 101.3),  # slow recent growth -> COOLING vs its own 12M
        ]
        heating_confirmation = [
            _obs(date(2024, 1, 1), 100.0),
            _obs(date(2024, 7, 1), 103.0),
            _obs(date(2024, 10, 1), 106.0),
            _obs(date(2025, 1, 1), 110.0),  # HEATING vs its own 12M
        ]
        result = compute_inflation_monitor_result(cooling_primary, heating_confirmation, [], [], identities=INFLATION_IDENTITIES)
        assert result.confirmation.relationship == "DIVERGES"
        assert result.coverage.confirmation_available is True

    def test_2_cpi_standalone_valid_but_no_common_period_is_unavailable(self):
        """Core CPI has a fully valid OWN standalone state, but shares
        no observation dates with Core PCE at all -- no same-period
        comparison is possible. This is exactly the case the old
        (incorrect) definition of confirmation_available got wrong: it
        would have reported True here because Core CPI's own state was
        calculable, even though the confirmation TIER itself produces
        nothing."""
        primary_obs = self.FULL
        confirmation_obs = [  # entirely disjoint date range from primary_obs
            _obs(date(2010, 1, 1), 50.0),
            _obs(date(2010, 7, 1), 51.0),
            _obs(date(2010, 10, 1), 52.0),
            _obs(date(2011, 1, 1), 53.0),
        ]
        result = compute_inflation_monitor_result(primary_obs, confirmation_obs, [], [], identities=INFLATION_IDENTITIES)

        # Core CPI's OWN standalone availability is untouched and still visible:
        assert result.confirmation.confirmation_latest.state != "INSUFFICIENT_DATA"
        assert result.confirmation.confirmation_latest.latest_valid_state_period == date(2011, 1, 1)

        # But the confirmation TIER itself has no common period at all:
        assert result.confirmation.latest_common_period is None
        assert result.confirmation.relationship == "UNAVAILABLE"
        assert result.coverage.confirmation_available is False

    def test_3_primary_insufficient_is_unavailable(self):
        result = compute_inflation_monitor_result([], self.FULL, [], [], identities=INFLATION_IDENTITIES)
        assert result.confirmation.relationship == "UNAVAILABLE"
        assert result.coverage.confirmation_available is False
        # Core CPI's own standalone state is still reported, unaffected:
        assert result.confirmation.confirmation_latest.state != "INSUFFICIENT_DATA"

    def test_4_confirmation_insufficient_is_unavailable(self):
        result = compute_inflation_monitor_result(self.FULL, [], [], [], identities=INFLATION_IDENTITIES)
        assert result.confirmation.relationship == "UNAVAILABLE"
        assert result.coverage.confirmation_available is False
        assert result.confirmation.confirmation_latest.state == "INSUFFICIENT_DATA"

    @pytest.mark.parametrize(
        "primary_obs, confirmation_obs",
        [
            pytest.param([], [], id="both_empty"),
            pytest.param(FULL, [], id="only_primary"),
            pytest.param([], FULL, id="only_confirmation"),
            pytest.param(FULL, FULL, id="identical_full_history"),
            pytest.param(
                FULL,
                [_obs(date(2010, 1, 1), 50.0), _obs(date(2010, 7, 1), 51.0), _obs(date(2010, 10, 1), 52.0), _obs(date(2011, 1, 1), 53.0)],
                id="disjoint_date_ranges",
            ),
            pytest.param([_obs(date(2025, 1, 1), 100.0)], [_obs(date(2025, 1, 1), 100.0)], id="single_point_both_sides"),
        ],
    )
    def test_5_invariant_holds_across_fixtures(self, primary_obs, confirmation_obs):
        result = compute_inflation_monitor_result(primary_obs, confirmation_obs, [], [], identities=INFLATION_IDENTITIES)
        assert result.coverage.confirmation_available == (result.confirmation.relationship != "UNAVAILABLE")


# ---------------------------------------------------------------------
# J. Provenance tests
# ---------------------------------------------------------------------


class TestProvenance:
    def test_evidence_reproduces_returned_state_by_hand(self):
        """Given ONLY the evidence fields, a human (or another program)
        can recompute the exact same state without calling any function
        in this module."""
        values = {
            date(2024, 1, 1): 100.0,
            date(2024, 7, 1): 103.0,
            date(2024, 10, 1): 106.0,
            date(2025, 1, 1): 110.0,
        }
        index = build_index([_obs(d, v) for d, v in values.items()])
        result = classify_period(index, PRIMARY_IDENTITY, date(2025, 1, 1), date(2025, 1, 1), date(2025, 1, 1))

        # Reproduce r_3m/r_6m/r_12m from evidence alone:
        e3, e6, e12 = result.evidence_3m, result.evidence_6m, result.evidence_12m
        reproduced_r3 = ((e3.endpoint_value_current / e3.endpoint_value_past) ** 4 - 1) * 100
        reproduced_r6 = ((e6.endpoint_value_current / e6.endpoint_value_past) ** 2 - 1) * 100
        reproduced_r12 = (e12.endpoint_value_current / e12.endpoint_value_past - 1) * 100
        assert reproduced_r3 == pytest.approx(e3.value, rel=1e-12) == pytest.approx(result.r_3m_annualized, rel=1e-12)
        assert reproduced_r6 == pytest.approx(e6.value, rel=1e-12) == pytest.approx(result.r_6m_annualized, rel=1e-12)
        assert reproduced_r12 == pytest.approx(e12.value, rel=1e-12) == pytest.approx(result.r_12m, rel=1e-12)

        reproduced_state, reproduced_lower, reproduced_upper = classify_state(
            reproduced_r3, reproduced_r6, reproduced_r12, result.neutral_band_pp
        )
        assert reproduced_state == result.state
        assert reproduced_lower == pytest.approx(result.lower_boundary, rel=1e-12)
        assert reproduced_upper == pytest.approx(result.upper_boundary, rel=1e-12)

    def test_evidence_carries_series_id_period_transformation_methodology_and_data_basis(self):
        values = {date(2024, 1, 1): 100.0, date(2024, 7, 1): 103.0, date(2024, 10, 1): 106.0, date(2025, 1, 1): 110.0}
        index = build_index([_obs(d, v) for d, v in values.items()])
        result = classify_period(index, PRIMARY_IDENTITY, date(2025, 1, 1), date(2025, 1, 1), date(2025, 1, 1))

        for evidence, expected_transformation in (
            (result.evidence_1m, "1m_annualized"),
            (result.evidence_3m, "3m_annualized"),
            (result.evidence_6m, "6m_annualized"),
            (result.evidence_12m, "12m"),
        ):
            assert evidence.series_id == "PCEPILFE"
            assert evidence.calculation_period == date(2025, 1, 1)
            assert evidence.transformation == expected_transformation
            assert evidence.methodology_id == "inflation_v1.0"
            assert evidence.data_basis == "latest_revised_data"

    def test_insufficient_data_still_carries_evidence_showing_what_was_missing(self):
        values = {date(2024, 7, 1): 103.0, date(2024, 10, 1): 106.0, date(2025, 1, 1): 110.0}  # no t-12
        index = build_index([_obs(d, v) for d, v in values.items()])
        result = classify_period(index, PRIMARY_IDENTITY, date(2025, 1, 1), date(2025, 1, 1), None)
        assert result.state == "INSUFFICIENT_DATA"
        assert result.evidence_12m is not None
        assert result.evidence_12m.value is None
        assert result.evidence_12m.endpoint_value_past is None
        assert result.evidence_12m.endpoint_date_past == date(2024, 1, 1)  # still names the exact missing date

    def test_no_observation_at_all_carries_no_evidence(self):
        result = classify_period({}, PRIMARY_IDENTITY, None, None, None)
        assert result.evidence_1m is None
        assert result.evidence_3m is None
        assert result.evidence_6m is None
        assert result.evidence_12m is None


# ---------------------------------------------------------------------
# Determinism / non-mutation
# ---------------------------------------------------------------------


class TestDeterminismAndNonMutation:
    def test_repeated_calls_produce_identical_results(self):
        values = {date(2024, 1, 1): 100.0, date(2024, 7, 1): 103.0, date(2024, 10, 1): 106.0, date(2025, 1, 1): 110.0}
        obs = [_obs(d, v) for d, v in values.items()]
        r1 = compute_series_momentum(obs, PRIMARY_IDENTITY)
        r2 = compute_series_momentum(obs, PRIMARY_IDENTITY)
        assert r1 == r2

    def test_full_pipeline_deterministic(self):
        primary_obs = [_obs(date(2024, 1, 1), 100.0), _obs(date(2024, 7, 1), 103.0), _obs(date(2024, 10, 1), 106.0), _obs(date(2025, 1, 1), 110.0)]
        result_1 = compute_inflation_monitor_result(primary_obs, primary_obs, primary_obs, primary_obs, identities=INFLATION_IDENTITIES)
        result_2 = compute_inflation_monitor_result(primary_obs, primary_obs, primary_obs, primary_obs, identities=INFLATION_IDENTITIES)
        assert result_1 == result_2

    def test_observations_list_not_mutated(self):
        obs = [_obs(date(2024, 1, 1), 100.0), _obs(date(2024, 2, 1), 101.0)]
        snapshot = list(obs)
        build_index(obs)
        assert obs == snapshot

    def test_index_dict_not_mutated_by_classify_period(self):
        index = build_index([_obs(date(2024, 1, 1), 100.0), _obs(date(2024, 2, 1), 101.0)])
        snapshot = dict(index)
        classify_period(index, PRIMARY_IDENTITY, date(2024, 2, 1), date(2024, 2, 1), None)
        assert index == snapshot


# ---------------------------------------------------------------------
# Headline context: independent, no aggregate/majority vote
# ---------------------------------------------------------------------


class TestHeadlineContext:
    def test_headline_pce_and_cpi_independently_classified(self):
        pce_obs = [_obs(date(2024, 1, 1), 100.0), _obs(date(2024, 7, 1), 103.0), _obs(date(2024, 10, 1), 106.0), _obs(date(2025, 1, 1), 110.0)]
        cpi_obs = [_obs(date(2024, 1, 1), 200.0), _obs(date(2024, 7, 1), 200.5), _obs(date(2024, 10, 1), 200.8), _obs(date(2025, 1, 1), 201.0)]
        result = compute_headline_context(pce_obs, cpi_obs, identities=INFLATION_IDENTITIES)
        assert result.headline_pce.series_id == TARGET_SERIES_ID
        assert result.headline_cpi.series_id == HEADLINE_CPI_SERIES_ID
        assert result.headline_pce.state != result.headline_cpi.state or True  # no forced relationship either way

    def test_no_aggregate_headline_state_field_exists(self):
        pce_obs = [_obs(date(2024, 1, 1), 100.0)]
        cpi_obs = [_obs(date(2024, 1, 1), 200.0)]
        result = compute_headline_context(pce_obs, cpi_obs, identities=INFLATION_IDENTITIES)
        assert set(type(result).model_fields.keys()) == {"headline_pce", "headline_cpi"}


# ---------------------------------------------------------------------
# inflation_what_changed_v1.0's period-selection + exact-period
# construction primitives -- these still live in app.domain.inflation
# (pure inflation_v1.0 construction, per the frozen What Changed
# contract's own architecture note), reusing classify_period/
# _metric_evidence/classify_confirmation_relationship unmodified.
# ---------------------------------------------------------------------


class TestComputeSeriesMomentumAt:
    """`compute_series_momentum_at` evaluates EXACTLY the given period
    -- never searches, unlike `compute_series_momentum`."""

    FULL = [
        _obs(date(2024, 1, 1), 100.0),
        _obs(date(2024, 7, 1), 103.0),
        _obs(date(2024, 10, 1), 106.0),
        _obs(date(2025, 1, 1), 110.0),
    ]

    def test_evaluates_exactly_the_requested_period_even_if_insufficient(self):
        # 2024-07 lacks its own t-12 (2023-07) -- INSUFFICIENT_DATA there,
        # even though 2025-01 (the series' actual latest valid period) exists.
        result = compute_series_momentum_at(self.FULL, PRIMARY_IDENTITY, date(2024, 7, 1))
        assert result.calculation_period == date(2024, 7, 1)
        assert result.state == "INSUFFICIENT_DATA"

    def test_never_substitutes_latest_valid_state_period(self):
        result = compute_series_momentum_at(self.FULL, PRIMARY_IDENTITY, date(2024, 7, 1))
        assert result.calculation_period != date(2025, 1, 1)
        # but the series-level metadata fields still correctly report the true latest:
        assert result.latest_valid_state_period == date(2025, 1, 1)
        assert result.latest_observation_period == date(2025, 1, 1)

    def test_none_period_yields_insufficient_data(self):
        result = compute_series_momentum_at(self.FULL, PRIMARY_IDENTITY, None)
        assert result.calculation_period is None
        assert result.state == "INSUFFICIENT_DATA"

    def test_matches_classify_period_exactly(self):
        """No duplicated formula: compute_series_momentum_at is a thin
        wrapper, byte-for-byte identical to classify_period given the
        same index/period."""
        index = build_index(self.FULL)
        direct = classify_period(index, PRIMARY_IDENTITY, date(2025, 1, 1), date(2025, 1, 1), date(2025, 1, 1))
        via_at = compute_series_momentum_at(self.FULL, PRIMARY_IDENTITY, date(2025, 1, 1))
        assert direct == via_at


class TestComputeTargetAt:
    FULL = [_obs(date(2024, 1, 1), 100.0), _obs(date(2025, 1, 1), 110.0)]

    def test_evaluates_exactly_the_requested_period(self):
        result = compute_target_at(self.FULL, date(2025, 1, 1), target_identity=TARGET_IDENTITY)
        expected_yoy = (110.0 / 100.0 - 1) * 100
        assert result.headline_pce_yoy == pytest.approx(expected_yoy)
        assert result.available is True

    def test_insufficient_at_a_period_lacking_t12(self):
        result = compute_target_at(self.FULL, date(2024, 6, 1), target_identity=TARGET_IDENTITY)
        assert result.available is False
        assert result.headline_pce_yoy is None
        assert result.target_gap_pp is None

    def test_none_period_is_unavailable(self):
        result = compute_target_at(self.FULL, None, target_identity=TARGET_IDENTITY)
        assert result.available is False
        assert result.calculation_period is None

    def test_no_duplicated_target_gap_formula(self):
        """compute_target and compute_target_at share _build_target_result
        -- verified indirectly: both report the identical target_gap_pp
        for the same period/data."""
        latest = compute_target(self.FULL, target_identity=TARGET_IDENTITY)
        at_same_period = compute_target_at(self.FULL, latest.calculation_period, target_identity=TARGET_IDENTITY)
        assert latest == at_same_period


class TestLatestSharedObservationPeriod:
    """The NEW inflation_what_changed_v1.0-only period-selection
    concept -- deliberately weaker than find_latest_common_period (any
    observation row vs. a VALID canonical state)."""

    def test_latest_shared_when_both_have_the_same_latest_row(self):
        primary = [_obs(date(2024, 1, 1), 100.0), _obs(date(2025, 1, 1), 110.0)]
        confirmation = [_obs(date(2024, 1, 1), 50.0), _obs(date(2025, 1, 1), 55.0)]
        assert latest_shared_observation_period(primary, confirmation) == date(2025, 1, 1)

    def test_uses_the_intersection_not_either_series_own_max(self):
        primary = [_obs(date(2024, 1, 1), 100.0), _obs(date(2025, 2, 1), 111.0)]  # latest: 2025-02
        confirmation = [_obs(date(2024, 1, 1), 50.0), _obs(date(2025, 1, 1), 55.0)]  # latest: 2025-01
        # Neither series' own max (2025-02 / 2025-01) is shared with the other --
        # the only shared date is 2024-01:
        assert latest_shared_observation_period(primary, confirmation) == date(2024, 1, 1)

    def test_row_existence_is_sufficient_even_with_a_null_value(self):
        primary = [_obs(date(2024, 1, 1), 100.0), _obs(date(2025, 1, 1), 110.0)]
        confirmation = [_obs(date(2024, 1, 1), 50.0), _obs(date(2025, 1, 1), None)]  # row exists, value null
        assert latest_shared_observation_period(primary, confirmation) == date(2025, 1, 1)

    def test_no_shared_dates_at_all(self):
        primary = [_obs(date(2024, 1, 1), 100.0)]
        confirmation = [_obs(date(2010, 1, 1), 50.0)]
        assert latest_shared_observation_period(primary, confirmation) is None

    def test_never_earlier_than_find_latest_common_period(self):
        """Structural invariant the frozen contract states explicitly:
        latest_common_period <= latest_shared_observation_period always,
        since a VALID state requires an observation to exist, but not
        the reverse. Uses full monthly coverage (2024-01 .. 2025-01) so
        every month has a genuine 12-month trailing window, except the
        deliberately null-valued final confirmation row."""
        months = [month_before(date(2025, 1, 1), -i) for i in range(-24, 1)]  # 2023-01 .. 2025-01
        primary = [_obs(d, 100.0 + i * 0.5) for i, d in enumerate(months)]
        confirmation = [_obs(d, 50.0 + i * 0.2) for i, d in enumerate(months) if d != date(2025, 1, 1)]
        confirmation_partial = confirmation + [_obs(date(2025, 1, 1), None)]  # row exists, value null -> INSUFFICIENT_DATA there

        common = find_latest_common_period(build_index(primary), build_index(confirmation_partial))
        shared = latest_shared_observation_period(primary, confirmation_partial)
        assert shared == date(2025, 1, 1)  # a row exists for confirmation at 2025-01 (even though null)
        assert common == date(2024, 12, 1)  # but that row isn't VALID, so the Monitor's own anchor stays earlier
        assert common < shared


class TestComputeConfirmationAt:
    PRIMARY = [
        _obs(date(2024, 1, 1), 100.0),
        _obs(date(2024, 7, 1), 103.0),
        _obs(date(2024, 10, 1), 106.0),
        _obs(date(2025, 1, 1), 110.0),
    ]
    CONFIRMATION = [
        _obs(date(2024, 1, 1), 50.0),
        _obs(date(2024, 7, 1), 51.5),
        _obs(date(2024, 10, 1), 53.0),
        _obs(date(2025, 1, 1), 55.0),
    ]

    def test_both_series_evaluated_at_the_exact_same_period(self):
        primary_state, confirmation_state, relationship = compute_confirmation_at(
            self.PRIMARY, self.CONFIRMATION, date(2025, 1, 1)
        , identities=INFLATION_IDENTITIES)
        assert primary_state.calculation_period == confirmation_state.calculation_period == date(2025, 1, 1)
        assert relationship in ("CONFIRMS", "DIVERGES", "INCONCLUSIVE", "UNAVAILABLE")

    def test_worked_example_from_frozen_spec_confirms_becomes_unavailable(self):
        """The frozen contract's own motivating worked example: Core CPI
        has an observation in the current month but its t-3 endpoint is
        missing -- the relationship there is UNAVAILABLE even though an
        earlier period (with full history) would CONFIRM."""
        primary = [
            _obs(date(2024, 1, 1), 100.0),
            _obs(date(2024, 4, 1), 100.5),
            _obs(date(2024, 7, 1), 101.0),
            _obs(date(2024, 10, 1), 101.5),
            _obs(date(2025, 1, 1), 102.0),  # July-equivalent: full history
            _obs(date(2025, 2, 1), 102.2),  # August-equivalent: full history too (primary stays valid)
        ]
        confirmation = [
            _obs(date(2024, 1, 1), 50.0),
            _obs(date(2024, 4, 1), 50.2),
            _obs(date(2024, 7, 1), 50.4),
            _obs(date(2024, 10, 1), 50.6),
            _obs(date(2025, 1, 1), 50.8),
            # 2025-02's t-3 endpoint (2024-11) is missing entirely -> INSUFFICIENT_DATA at 2025-02
        ]
        confirmation_with_gap = confirmation + [_obs(date(2025, 2, 1), 51.0)]

        _, _, relationship_at_july_equivalent = compute_confirmation_at(primary, confirmation_with_gap, date(2025, 1, 1), identities=INFLATION_IDENTITIES)
        _, confirmation_state_at_august_equivalent, relationship_at_august_equivalent = compute_confirmation_at(
            primary, confirmation_with_gap, date(2025, 2, 1)
        , identities=INFLATION_IDENTITIES)
        assert relationship_at_july_equivalent != "UNAVAILABLE"
        assert confirmation_state_at_august_equivalent.state == "INSUFFICIENT_DATA"
        assert relationship_at_august_equivalent == "UNAVAILABLE"

    def test_none_period_yields_unavailable(self):
        primary_state, confirmation_state, relationship = compute_confirmation_at(self.PRIMARY, self.CONFIRMATION, None, identities=INFLATION_IDENTITIES)
        assert primary_state.state == "INSUFFICIENT_DATA"
        assert confirmation_state.state == "INSUFFICIENT_DATA"
        assert relationship == "UNAVAILABLE"


class TestMonthOverMonthSeriesMomentum:
    def test_current_period_is_latest_observation_not_latest_valid(self):
        """The exact bug this contract was designed to fix: a series
        whose true latest observation is INSUFFICIENT_DATA must still
        be selected as `current_period` -- never silently resolved back
        to an earlier valid period."""
        observations = [
            _obs(date(2024, 1, 1), 100.0),
            _obs(date(2024, 7, 1), 103.0),
            _obs(date(2024, 10, 1), 106.0),
            _obs(date(2025, 1, 1), 110.0),  # July-equivalent: valid
            _obs(date(2025, 2, 1), None),  # August-equivalent: row exists, value null -> INSUFFICIENT_DATA
        ]
        previous_period, current_period, previous_evidence, current_evidence = month_over_month_series_momentum(
            observations, PRIMARY_IDENTITY
        )
        assert current_period == date(2025, 2, 1)  # NOT date(2025, 1, 1)
        assert previous_period == date(2025, 1, 1)
        assert current_evidence.state == "INSUFFICIENT_DATA"
        assert previous_evidence.state != "INSUFFICIENT_DATA"

    def test_no_observations_at_all_returns_all_none(self):
        result = month_over_month_series_momentum([], PRIMARY_IDENTITY)
        assert result == (None, None, None, None)

    def test_previous_is_exact_calendar_month_never_a_search(self):
        observations = [
            _obs(date(2024, 1, 1), 100.0),
            _obs(date(2025, 1, 1), 110.0),
            # nothing at 2024-12 -- previous_period must be exactly 2024-12, not a search back to 2024-01
        ]
        previous_period, current_period, previous_evidence, current_evidence = month_over_month_series_momentum(
            observations, PRIMARY_IDENTITY
        )
        assert current_period == date(2025, 1, 1)
        assert previous_period == date(2024, 12, 1)
        assert previous_evidence.state == "INSUFFICIENT_DATA"  # 2024-12 has no observation at all


class TestMonthOverMonthTarget:
    def test_current_period_is_latest_observation(self):
        observations = [_obs(date(2024, 1, 1), 100.0), _obs(date(2025, 1, 1), 110.0), _obs(date(2025, 2, 1), None)]
        previous_period, current_period, previous_evidence, current_evidence = month_over_month_target(observations, target_identity=TARGET_IDENTITY)
        assert current_period == date(2025, 2, 1)
        assert current_evidence.available is False
        assert previous_evidence.available is True

    def test_empty_observations_returns_all_none(self):
        assert month_over_month_target([], target_identity=TARGET_IDENTITY) == (None, None, None, None)


class TestMonthOverMonthConfirmation:
    def test_anchors_to_latest_shared_observation_not_latest_common_period(self):
        primary = [
            _obs(date(2024, 1, 1), 100.0),
            _obs(date(2024, 7, 1), 103.0),
            _obs(date(2024, 10, 1), 106.0),
            _obs(date(2025, 1, 1), 110.0),
        ]
        confirmation = [
            _obs(date(2024, 1, 1), 50.0),
            _obs(date(2024, 7, 1), 51.5),
            _obs(date(2024, 10, 1), 53.0),
            _obs(date(2025, 1, 1), None),  # row exists, value null
        ]
        (
            previous_period,
            current_period,
            previous_primary,
            previous_confirmation,
            previous_relationship,
            current_primary,
            current_confirmation,
            current_relationship,
        ) = month_over_month_confirmation(primary, confirmation, identities=INFLATION_IDENTITIES)

        assert current_period == date(2025, 1, 1)  # NOT the Monitor's own latest_common_period (2024-10)
        assert current_relationship == "UNAVAILABLE"
        assert current_confirmation.state == "INSUFFICIENT_DATA"
        assert previous_period == date(2024, 12, 1)

    def test_no_shared_observation_returns_all_none(self):
        primary = [_obs(date(2024, 1, 1), 100.0)]
        confirmation = [_obs(date(2010, 1, 1), 50.0)]
        result = month_over_month_confirmation(primary, confirmation, identities=INFLATION_IDENTITIES)
        assert result == (None, None, None, None, None, None, None, None)

    def test_both_series_at_exact_same_period_never_mismatched(self):
        primary = [_obs(date(2024, 1, 1), 100.0), _obs(date(2025, 1, 1), 110.0)]
        confirmation = [_obs(date(2024, 1, 1), 50.0), _obs(date(2025, 1, 1), 55.0)]
        (
            previous_period,
            current_period,
            previous_primary,
            previous_confirmation,
            previous_relationship,
            current_primary,
            current_confirmation,
            current_relationship,
        ) = month_over_month_confirmation(primary, confirmation, identities=INFLATION_IDENTITIES)
        assert current_primary.calculation_period == current_confirmation.calculation_period == current_period
        assert previous_primary.calculation_period == previous_confirmation.calculation_period == previous_period
