"""Tests for the Inflation Momentum Methodology Study's research code
(research/inflation_momentum/). Pure, offline, deterministic -- no
network, no database, no OpenAI. Hand-checked expected values are
computed directly from the formula's own definition in each test, never
by calling the function under test to produce its own "expected" value.
"""

import ast
from datetime import date
from pathlib import Path

import pytest

from research.inflation_momentum.methodology import (
    Observation,
    TransformedRow,
    annualized_change,
    classify_candidate_a,
    classify_candidate_b,
    classify_candidate_b_explicit,
    classify_candidate_c,
    classify_candidate_d,
    compute_delta_3m,
    compute_transformations,
    latest_available_period,
    latest_common_period,
)
from research.inflation_momentum.metrics import compute_agreement, compute_directional_metrics, compute_state_series_metrics
from research.inflation_momentum.regimes import REGIMES, regime_coverage

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------
# Transformation math -- hand-checked
# ---------------------------------------------------------------------


class TestAnnualizedChange:
    def test_12m_yoy_is_the_plain_percent_change(self):
        # ((103.7 / 100) ** (12/12) - 1) * 100 = 3.7 exactly
        assert annualized_change(103.7, 100.0, 12) == pytest.approx(3.7)

    def test_6m_annualized_compounds_not_doubles(self):
        # ((103 / 100) ** 2 - 1) * 100 -- computed independently here, not via the function under test
        expected = ((103.0 / 100.0) ** 2 - 1) * 100
        assert annualized_change(103.0, 100.0, 6) == pytest.approx(expected)
        assert annualized_change(103.0, 100.0, 6) == pytest.approx(6.09)  # NOT 6.0 (naive "double the 6m change")

    def test_3m_annualized_compounds_not_quadruples(self):
        expected = ((101.0 / 100.0) ** 4 - 1) * 100
        assert annualized_change(101.0, 100.0, 3) == pytest.approx(expected)
        assert annualized_change(101.0, 100.0, 3) == pytest.approx(4.060401, abs=1e-6)  # NOT 4.0 (naive x4)

    def test_1m_annualized(self):
        expected = ((100.5 / 100.0) ** 12 - 1) * 100
        assert annualized_change(100.5, 100.0, 1) == pytest.approx(expected)

    def test_negative_inflation_deflation(self):
        # Price level FALLING: current < past -> negative annualized rate.
        result = annualized_change(99.0, 100.0, 12)
        expected = ((99.0 / 100.0) - 1) * 100
        assert result == pytest.approx(expected)
        assert result < 0

    def test_missing_current_returns_none(self):
        assert annualized_change(None, 100.0, 12) is None

    def test_missing_past_returns_none(self):
        assert annualized_change(100.0, None, 12) is None

    def test_nonpositive_past_returns_none_not_a_crash(self):
        assert annualized_change(100.0, 0.0, 12) is None
        assert annualized_change(100.0, -5.0, 12) is None

    def test_identical_levels_is_exactly_zero(self):
        assert annualized_change(100.0, 100.0, 12) == pytest.approx(0.0)


class TestComputeTransformations:
    def _obs(self, pairs):
        return [Observation(date=date(2020, 1 + i if i < 12 else 1, 1), value=v) for i, (m, v) in enumerate(pairs)]

    def test_insufficient_history_is_none_not_approximated(self):
        # Only 2 observations -- no 3M/6M/12M lookback exists yet for either row.
        obs = [Observation(date(2020, 1, 1), 100.0), Observation(date(2020, 2, 1), 100.5)]
        rows = compute_transformations(obs)
        assert rows[0].chg_1m_ann is None  # first obs has no predecessor at all
        assert rows[1].chg_3m_ann is None
        assert rows[1].chg_6m_ann is None
        assert rows[1].chg_12m_yoy is None
        assert rows[1].chg_1m_ann is not None  # exactly one month of history exists

    def test_missing_value_propagates_as_none_not_skipped(self):
        obs = [
            Observation(date(2020, 1, 1), 100.0),
            Observation(date(2020, 2, 1), None),  # missing month
            Observation(date(2020, 3, 1), 101.0),
        ]
        rows = compute_transformations(obs)
        assert rows[1].chg_1m_ann is None  # current value missing
        assert rows[2].chg_1m_ann is None  # previous month's value missing -- not silently using Jan instead

    def test_input_not_mutated_and_sorted_explicitly(self):
        obs = [Observation(date(2020, 2, 1), 101.0), Observation(date(2020, 1, 1), 100.0)]  # deliberately out of order
        snapshot = list(obs)
        rows = compute_transformations(obs)
        assert obs == snapshot
        assert [r.date for r in rows] == [date(2020, 1, 1), date(2020, 2, 1)]

    def test_repeated_execution_identical(self):
        obs = [Observation(date(2020, m, 1), 100.0 + m) for m in range(1, 13)]
        assert compute_transformations(obs) == compute_transformations(obs)


# ---------------------------------------------------------------------
# Candidate classifiers
# ---------------------------------------------------------------------


def _row(chg_3m=None, chg_6m=None, chg_12m=None):
    return TransformedRow(date=date(2020, 1, 1), level=100.0, chg_1m_ann=None, chg_3m_ann=chg_3m, chg_6m_ann=chg_6m, chg_12m_yoy=chg_12m)


class TestCandidateA:
    def test_cooling(self):
        assert classify_candidate_a(_row(chg_3m=2.0, chg_12m=3.0), delta=0.25) == "COOLING"

    def test_heating(self):
        assert classify_candidate_a(_row(chg_3m=4.0, chg_12m=3.0), delta=0.25) == "HEATING"

    def test_stable_within_band(self):
        assert classify_candidate_a(_row(chg_3m=3.0, chg_12m=3.0), delta=0.25) == "STABLE"

    def test_boundary_exactly_at_delta_is_stable_not_cooling(self):
        # 3m == 12m - delta exactly -- strict "<" means this is NOT cooling.
        assert classify_candidate_a(_row(chg_3m=2.75, chg_12m=3.0), delta=0.25) == "STABLE"

    def test_adversarial_m_3m_2_01_12m_2_00(self):
        """Adversarial case M: 3M=2.01, 12M=2.00 -- with delta=0, this is
        HEATING (however small); with delta=0.10 it is STABLE. Both
        results are correct for their own delta; this documents the
        sensitivity, not a bug."""
        assert classify_candidate_a(_row(chg_3m=2.01, chg_12m=2.00), delta=0.0) == "HEATING"
        assert classify_candidate_a(_row(chg_3m=2.01, chg_12m=2.00), delta=0.10) == "STABLE"

    def test_missing_data_returns_none_not_stable(self):
        assert classify_candidate_a(_row(chg_3m=None, chg_12m=3.0), delta=0.25) is None
        assert classify_candidate_a(_row(chg_3m=3.0, chg_12m=None), delta=0.25) is None


class TestCandidateB:
    def test_cooling_requires_both_confirmations(self):
        assert classify_candidate_b(_row(chg_3m=2.0, chg_6m=2.0, chg_12m=3.0), delta=0.25) == "COOLING"

    def test_adversarial_d_3m_below_6m_above_is_mixed_not_cooling(self):
        """Adversarial case D: 3M below 12M but 6M above 12M -- dual
        confirmation fails, must not be called COOLING."""
        result = classify_candidate_b(_row(chg_3m=2.0, chg_6m=4.0, chg_12m=3.0), delta=0.25)
        assert result == "MIXED_OR_STABLE"

    def test_adversarial_e_3m_above_6m_below_is_mixed_not_heating(self):
        result = classify_candidate_b(_row(chg_3m=4.0, chg_6m=2.0, chg_12m=3.0), delta=0.25)
        assert result == "MIXED_OR_STABLE"

    def test_heating_requires_both_confirmations(self):
        assert classify_candidate_b(_row(chg_3m=4.0, chg_6m=4.0, chg_12m=3.0), delta=0.25) == "HEATING"

    def test_missing_any_input_returns_none(self):
        assert classify_candidate_b(_row(chg_3m=2.0, chg_6m=None, chg_12m=3.0), delta=0.25) is None


class TestCandidateC:
    def test_strict_cooling_order(self):
        assert classify_candidate_c(_row(chg_3m=1.0, chg_6m=2.0, chg_12m=3.0)) == "COOLING"

    def test_strict_heating_order(self):
        assert classify_candidate_c(_row(chg_3m=3.0, chg_6m=2.0, chg_12m=1.0)) == "HEATING"

    def test_non_monotonic_is_mixed(self):
        assert classify_candidate_c(_row(chg_3m=2.0, chg_6m=1.0, chg_12m=3.0)) == "MIXED"

    def test_band_variant_requires_separation(self):
        # 3M < 6M < 12M but by less than band=0.5 -- base (band=0) says COOLING, band=0.5 variant says MIXED.
        row = _row(chg_3m=2.8, chg_6m=2.9, chg_12m=3.0)
        assert classify_candidate_c(row, band=0.0) == "COOLING"
        assert classify_candidate_c(row, band=0.5) == "MIXED"

    def test_missing_data_returns_none(self):
        assert classify_candidate_c(_row(chg_3m=1.0, chg_6m=None, chg_12m=3.0)) is None


class TestCandidateD:
    def test_delta_3m_computation(self):
        rows = [_row(chg_3m=2.0), _row(chg_3m=3.0), _row(chg_3m=2.5)]
        deltas = compute_delta_3m(rows)
        assert deltas[0] is None  # no predecessor
        assert deltas[1] == pytest.approx(1.0)
        assert deltas[2] == pytest.approx(-0.5)

    def test_classification(self):
        assert classify_candidate_d(1.0) == "ACCELERATING"
        assert classify_candidate_d(-1.0) == "DECELERATING"
        assert classify_candidate_d(0.0) == "FLAT"
        assert classify_candidate_d(None) is None

    def test_missing_predecessor_propagates_as_none(self):
        rows = [_row(chg_3m=2.0), _row(chg_3m=None), _row(chg_3m=2.5)]
        deltas = compute_delta_3m(rows)
        assert deltas[1] is None  # this row's own 3M missing
        assert deltas[2] is None  # predecessor's 3M missing -- not silently skipped to row 0


# ---------------------------------------------------------------------
# Common-period alignment
# ---------------------------------------------------------------------


class TestCommonPeriod:
    def test_latest_available_ignores_trailing_missing_values(self):
        obs = [Observation(date(2020, 1, 1), 100.0), Observation(date(2020, 2, 1), None)]
        assert latest_available_period(obs) == date(2020, 1, 1)

    def test_latest_common_is_the_minimum_across_series(self):
        series = {
            "CPI": [Observation(date(2020, 1, 1), 100.0), Observation(date(2020, 8, 1), 101.0)],
            "PCE": [Observation(date(2020, 1, 1), 100.0), Observation(date(2020, 7, 1), 101.0)],
        }
        assert latest_common_period(series) == date(2020, 7, 1)  # NOT August -- PCE's latest is July

    def test_none_if_any_series_has_no_data(self):
        series = {"CPI": [Observation(date(2020, 1, 1), 100.0)], "PCE": []}
        assert latest_common_period(series) is None


# ---------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------


class TestStateSeriesMetrics:
    def test_hand_constructed_sequence(self):
        # C C H C H H H  (7 months, no missing)
        # Runs: COOLING(2), HEATING(1), COOLING(1), HEATING(3) -- 4 runs, 3 transitions between them.
        states = ["COOLING", "COOLING", "HEATING", "COOLING", "HEATING", "HEATING", "HEATING"]
        m = compute_state_series_metrics(states)
        assert m.total_months == 7
        assert m.classified_months == 7
        assert m.unclassified_months == 0
        assert m.state_counts == {"COOLING": 3, "HEATING": 4}
        assert m.num_state_changes == 3
        assert m.num_one_month_reversals == 2  # the two length-1 runs (HEATING, COOLING)
        assert m.num_two_month_reversals == 1  # the one length-2 run (the initial COOLING)
        # Consecutive run triples: (C,H,C) at runs[0:3] -> one C-H-C whipsaw;
        # (H,C,H) at runs[1:4] -> one H-C-H whipsaw. Both exist in this short, densely-alternating sequence.
        assert m.num_cooling_heating_cooling_whipsaws == 1
        assert m.num_heating_cooling_heating_whipsaws == 1
        assert m.longest_run_by_state == {"COOLING": 2, "HEATING": 3}

    def test_none_values_are_not_a_state_and_break_runs(self):
        states = ["COOLING", None, "COOLING"]
        m = compute_state_series_metrics(states)
        assert m.classified_months == 2
        assert m.unclassified_months == 1
        assert pytest.approx(m.pct_unclassified) == 100 / 3
        # Two separate 1-month COOLING runs, not one 2-month run, since None breaks contemporaneity.
        assert m.longest_run_by_state == {"COOLING": 1}
        # No consecutive classified pair exists across the None gap -- zero changes counted, not one.
        assert m.num_state_changes == 0

    def test_empty_series(self):
        m = compute_state_series_metrics([])
        assert m.total_months == 0
        assert m.median_state_duration is None
        assert m.mean_state_duration is None

    def test_repeated_execution_identical(self):
        states = ["COOLING", "HEATING", "COOLING", "COOLING", None, "HEATING"]
        assert compute_state_series_metrics(states) == compute_state_series_metrics(states)


class TestAgreement:
    OPPOSITE = {("COOLING", "HEATING"), ("HEATING", "COOLING")}

    def test_same_state_agreement(self):
        a = ["COOLING", "HEATING", "COOLING"]
        b = ["COOLING", "HEATING", "COOLING"]
        result = compute_agreement(a, b, self.OPPOSITE)
        assert result.same_state_pct == pytest.approx(100.0)
        assert result.opposite_state_pct == pytest.approx(0.0)

    def test_opposite_is_narrowly_defined_cooling_vs_heating_only(self):
        a = ["COOLING", "COOLING"]
        b = ["HEATING", "STABLE"]
        result = compute_agreement(a, b, self.OPPOSITE)
        # COOLING vs HEATING = opposite; COOLING vs STABLE = other, NOT opposite.
        assert result.opposite_state_pct == pytest.approx(50.0)
        assert result.other_pct == pytest.approx(50.0)

    def test_months_with_either_side_none_are_excluded(self):
        a = ["COOLING", None, "HEATING"]
        b = ["COOLING", "HEATING", None]
        result = compute_agreement(a, b, self.OPPOSITE)
        assert result.compared_months == 1  # only index 0 has both sides classified


# ---------------------------------------------------------------------
# Regimes
# ---------------------------------------------------------------------


class TestRegimeCoverage:
    def test_no_fabricated_coverage_before_series_start(self):
        pce_regime = next(r for r in REGIMES if r.name == "1970s Inflation Shocks")
        coverage = regime_coverage(pce_regime, series_first=date(1959, 1, 1), series_last=date(2026, 1, 1))
        assert coverage["has_any_coverage"] is True
        assert coverage["full_coverage"] is True

    def test_regime_entirely_before_series_start_has_no_coverage(self):
        pre_1959_regime = REGIMES[0]
        coverage = regime_coverage(pre_1959_regime, series_first=date(1959, 1, 1), series_last=date(2026, 1, 1))
        # "1970s Inflation Shocks" starts 1973 -- after 1959, so it DOES overlap; use a synthetic pre-1959 case instead.
        from research.inflation_momentum.regimes import Regime as R

        synthetic = R("Pre-series synthetic regime", date(1950, 1, 1), date(1955, 12, 31), "test only")
        coverage2 = regime_coverage(synthetic, series_first=date(1959, 1, 1), series_last=date(2026, 1, 1))
        assert coverage2["has_any_coverage"] is False


# ---------------------------------------------------------------------
# Architectural independence: app/ must never import research/
# ---------------------------------------------------------------------


class TestStudyEndToEndDeterminism:
    """Full-pipeline reproducibility: same cached data in, byte-
    identical output files out. Skips gracefully if the data cache
    (populated by fetch_data.py, gitignored, not guaranteed present in
    a fresh checkout) doesn't exist -- never fails for that reason,
    matching this project's established pattern for environment-
    dependent tests (see tests/conftest.py's TEST_DATABASE_URL skip)."""

    def test_repeated_study_run_produces_identical_output_files(self, tmp_path, monkeypatch):
        data_dir = REPO_ROOT / "research" / "inflation_momentum" / "data"
        if not any(data_dir.glob("*.json")):
            pytest.skip("No cached FRED data (research/inflation_momentum/data/*.json) -- run fetch_data.py first.")

        from research.inflation_momentum import study

        out_a = tmp_path / "run_a"
        out_b = tmp_path / "run_b"
        monkeypatch.setattr(study, "OUTPUTS_DIR", out_a)
        study.main()
        monkeypatch.setattr(study, "OUTPUTS_DIR", out_b)
        study.main()

        files_a = sorted(p.name for p in out_a.iterdir())
        files_b = sorted(p.name for p in out_b.iterdir())
        assert files_a == files_b
        for name in files_a:
            assert (out_a / name).read_text() == (out_b / name).read_text(), f"{name} differed between runs"


class TestCandidateBExplicit:
    """Boundary tests for the finalist analysis's explicit five-state
    split of Candidate B (Section 4/8 of the finalist-analysis brief).
    Boundary operators (see `_horizon_bucket`'s docstring): the neutral
    band is closed/inclusive `[12M-delta, 12M+delta]`; COOLING/HEATING
    use strict `<`/`>` just outside that closed interval -- so every
    value falls into exactly one of the three per-horizon buckets, with
    no gap and no overlap."""

    DELTA = 0.25

    def test_both_exactly_on_lower_boundary_is_stable_not_cooling(self):
        # 3M == 12M - delta and 6M == 12M - delta exactly: the boundary value itself is "in", not "below".
        row = _row(chg_3m=2.75, chg_6m=2.75, chg_12m=3.0)  # 3.0 - 0.25 = 2.75
        assert classify_candidate_b_explicit(row, self.DELTA) == "STABLE"

    def test_both_exactly_on_upper_boundary_is_stable_not_heating(self):
        row = _row(chg_3m=3.25, chg_6m=3.25, chg_12m=3.0)  # 3.0 + 0.25 = 3.25
        assert classify_candidate_b_explicit(row, self.DELTA) == "STABLE"

    def test_one_exactly_on_boundary_one_beyond_is_mixed(self):
        # 3M exactly on the lower boundary (in-band); 6M strictly beyond it (below-band).
        row = _row(chg_3m=2.75, chg_6m=2.0, chg_12m=3.0)
        assert classify_candidate_b_explicit(row, self.DELTA) == "MIXED"

    def test_one_inside_band_one_outside_is_mixed(self):
        row = _row(chg_3m=3.0, chg_6m=4.0, chg_12m=3.0)  # 3M inside band, 6M above it
        assert classify_candidate_b_explicit(row, self.DELTA) == "MIXED"

    def test_3m_cooling_6m_heating_is_mixed(self):
        row = _row(chg_3m=1.0, chg_6m=5.0, chg_12m=3.0)
        assert classify_candidate_b_explicit(row, self.DELTA) == "MIXED"

    def test_3m_heating_6m_cooling_is_mixed(self):
        row = _row(chg_3m=5.0, chg_6m=1.0, chg_12m=3.0)
        assert classify_candidate_b_explicit(row, self.DELTA) == "MIXED"

    def test_3m_stable_6m_cooling_is_mixed(self):
        row = _row(chg_3m=3.0, chg_6m=1.0, chg_12m=3.0)  # 3M in-band, 6M below
        assert classify_candidate_b_explicit(row, self.DELTA) == "MIXED"

    def test_3m_stable_6m_heating_is_mixed(self):
        row = _row(chg_3m=3.0, chg_6m=5.0, chg_12m=3.0)  # 3M in-band, 6M above
        assert classify_candidate_b_explicit(row, self.DELTA) == "MIXED"

    def test_missing_3m_is_insufficient_data(self):
        row = _row(chg_3m=None, chg_6m=2.0, chg_12m=3.0)
        assert classify_candidate_b_explicit(row, self.DELTA) == "INSUFFICIENT_DATA"

    def test_missing_6m_is_insufficient_data(self):
        row = _row(chg_3m=2.0, chg_6m=None, chg_12m=3.0)
        assert classify_candidate_b_explicit(row, self.DELTA) == "INSUFFICIENT_DATA"

    def test_missing_12m_is_insufficient_data(self):
        row = _row(chg_3m=2.0, chg_6m=2.0, chg_12m=None)
        assert classify_candidate_b_explicit(row, self.DELTA) == "INSUFFICIENT_DATA"

    def test_negative_inflation_deflation_cooling(self):
        # 12M = -1.0; 3M and 6M both well below (-3.0 < -1.25) -- negative values need no special-casing.
        row = _row(chg_3m=-3.0, chg_6m=-3.0, chg_12m=-1.0)
        assert classify_candidate_b_explicit(row, self.DELTA) == "COOLING"

    def test_very_large_positive_inflation_heating(self):
        row = _row(chg_3m=80.0, chg_6m=80.0, chg_12m=50.0)
        assert classify_candidate_b_explicit(row, self.DELTA) == "HEATING"

    def test_identical_repeated_inputs_are_deterministic(self):
        row = _row(chg_3m=2.0, chg_6m=2.5, chg_12m=3.0)
        assert classify_candidate_b_explicit(row, self.DELTA) == classify_candidate_b_explicit(row, self.DELTA)

    def test_never_returns_none(self):
        """Unlike every other candidate in this study, INSUFFICIENT_DATA
        is itself a returned state, never None -- so this function's
        return type always has len==1 when checked against the Literal."""
        row = _row(chg_3m=None, chg_6m=None, chg_12m=None)
        result = classify_candidate_b_explicit(row, self.DELTA)
        assert result is not None
        assert result == "INSUFFICIENT_DATA"


class TestDirectionalMetrics:
    def test_direct_reversal_counted_only_with_no_intervening_neutral_month(self):
        states = ["COOLING", "HEATING"]  # direct flip, no buffer month
        m = compute_directional_metrics(states)
        assert m.num_direct_reversals == 1
        assert m.num_directional_to_neutral_transitions == 0

    def test_reversal_via_neutral_state_is_not_a_direct_reversal(self):
        states = ["COOLING", "STABLE", "HEATING"]  # buffered by a neutral month
        m = compute_directional_metrics(states)
        assert m.num_direct_reversals == 0
        assert m.num_directional_to_neutral_transitions == 2  # COOLING->STABLE, STABLE->HEATING

    def test_rates_share_the_same_denominator_as_all_state_churn(self):
        states = ["COOLING", "COOLING", "HEATING", "STABLE"]
        m = compute_directional_metrics(states)
        all_state = compute_state_series_metrics(states)
        # 3 consecutive pairs total (indices 0-1, 1-2, 2-3), all classified.
        assert m.consecutive_classified_pairs == 3
        assert m.consecutive_classified_pairs == 3  # matches what all-state churn's rate is computed over
        assert all_state.num_state_changes == 2  # COOLING->COOLING (no), COOLING->HEATING (yes), HEATING->STABLE (yes)

    def test_none_excluded_same_as_all_state_metrics(self):
        states = ["COOLING", None, "HEATING"]
        m = compute_directional_metrics(states)
        assert m.consecutive_classified_pairs == 0  # the None breaks contemporaneity on both sides

    def test_custom_directional_states_for_five_state_b(self):
        # Candidate B explicit uses the same two directional states by default; explicit override still works.
        # Pairs: (COOLING,MIXED) dir->neutral; (MIXED,HEATING) neutral->dir; (HEATING,STABLE) dir->neutral;
        # (STABLE,INSUFFICIENT_DATA) neutral->neutral (not counted). 3 directional/neutral crossings, 0 direct reversals.
        states = ["COOLING", "MIXED", "HEATING", "STABLE", "INSUFFICIENT_DATA"]
        m = compute_directional_metrics(states, directional_states=("COOLING", "HEATING"))
        assert m.num_direct_reversals == 0  # never two directional states adjacent
        assert m.num_directional_to_neutral_transitions == 3


class TestArchitecturalIndependence:
    def test_no_app_module_imports_research(self):
        violations = []
        for path in (REPO_ROOT / "app").rglob("*.py"):
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("research"):
                    violations.append(f"{path}: imports '{node.module}'")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("research"):
                            violations.append(f"{path}: imports '{alias.name}'")
        assert violations == [], "app/ must never import research/:\n" + "\n".join(violations)
