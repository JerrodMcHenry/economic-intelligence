"""Tests for the Finalist Analysis orchestration
(research/inflation_momentum/finalist_study.py). Pure, offline,
deterministic -- no network, no database, no OpenAI. Synthetic
TransformedRow data is hand-built per test; the one end-to-end test
that touches the real cached data only checks reproducibility (byte-
identical output across two runs), never a specific number, so it
never needs updating when FRED revises history.
"""

from datetime import date
from pathlib import Path

import pytest

from research.inflation_momentum.finalist_study import (
    FINALISTS,
    TURN_EPISODES,
    align_two,
    candidate_b_explicit_report,
    core_pce_decision_table,
    cross_measure_confirmation_report,
    finalist_states,
    missing_confirmation_check,
    neutral_band_investigation,
    turn_persistence_report,
)
from research.inflation_momentum.methodology import TransformedRow

REPO_ROOT = Path(__file__).resolve().parents[2]


def _row(d: date, chg_3m=None, chg_6m=None, chg_12m=None):
    return TransformedRow(date=d, level=None, chg_1m_ann=None, chg_3m_ann=chg_3m, chg_6m_ann=chg_6m, chg_12m_yoy=chg_12m)


# ---------------------------------------------------------------------
# finalist_states: cross-finalist-comparable dispatch
# ---------------------------------------------------------------------


class TestFinalistStates:
    def test_family_a_dispatches_to_candidate_a(self):
        row = _row(date(2020, 1, 1), chg_3m=5.0, chg_6m=5.0, chg_12m=3.0)
        assert finalist_states(row, "A_delta_0.25", "A", 0.25) == "HEATING"

    def test_family_c_dispatches_to_candidate_c(self):
        row = _row(date(2020, 1, 1), chg_3m=1.0, chg_6m=2.0, chg_12m=3.0)
        assert finalist_states(row, "C_band_0.25", "C", 0.25) == "COOLING"

    def test_family_b_insufficient_data_normalized_to_none(self):
        # Missing 6M -> classify_candidate_b_explicit returns "INSUFFICIENT_DATA",
        # which finalist_states must normalize to None so Section 2's decision
        # table treats B's early-history gap identically to A/C's None.
        row = _row(date(2020, 1, 1), chg_3m=5.0, chg_6m=None, chg_12m=3.0)
        assert finalist_states(row, "B_delta_0.25", "B", 0.25) is None

    def test_family_b_real_state_passes_through_unchanged(self):
        row = _row(date(2020, 1, 1), chg_3m=5.0, chg_6m=5.0, chg_12m=3.0)
        assert finalist_states(row, "B_delta_0.25", "B", 0.25) == "HEATING"

    def test_unknown_family_raises(self):
        row = _row(date(2020, 1, 1), chg_3m=1.0, chg_6m=1.0, chg_12m=1.0)
        with pytest.raises(ValueError):
            finalist_states(row, "Z", "Z", 0.25)


# ---------------------------------------------------------------------
# Section 2: Core PCE decision table -- cross-finalist comparability
# ---------------------------------------------------------------------


class TestCorePceDecisionTable:
    def _series(self):
        # 6 months: first 2 have insufficient history for every finalist
        # (no chg_12m), remaining 4 alternate HEATING/COOLING/STABLE-ish.
        return [
            _row(date(2020, 1, 1), chg_3m=None, chg_6m=None, chg_12m=None),
            _row(date(2020, 2, 1), chg_3m=1.0, chg_6m=1.0, chg_12m=None),
            _row(date(2020, 3, 1), chg_3m=5.0, chg_6m=5.0, chg_12m=3.0),   # HEATING
            _row(date(2020, 4, 1), chg_3m=1.0, chg_6m=1.0, chg_12m=3.0),   # COOLING
            _row(date(2020, 5, 1), chg_3m=3.0, chg_6m=3.0, chg_12m=3.0),   # STABLE
            _row(date(2020, 6, 1), chg_3m=5.0, chg_6m=5.0, chg_12m=3.0),   # HEATING
        ]

    def test_all_finalists_report_identical_unclassified_count(self):
        rows_by_series = {"Core PCE": self._series()}
        table = core_pce_decision_table(rows_by_series)
        unclassified_counts = {row["finalist"]: row["unclassified_months"] for row in table}
        # Every finalist needs chg_12m at minimum, and B additionally needs
        # chg_6m -- but in this fixture chg_6m is always present whenever
        # chg_12m is, so all finalists should show the identical count of 2.
        assert set(unclassified_counts.values()) == {2}

    def test_covers_exactly_the_five_named_finalists(self):
        rows_by_series = {"Core PCE": self._series()}
        table = core_pce_decision_table(rows_by_series)
        assert [row["finalist"] for row in table] == [variant for variant, _, _ in FINALISTS]
        assert len(FINALISTS) == 5

    def test_required_metric_keys_present(self):
        rows_by_series = {"Core PCE": self._series()}
        table = core_pce_decision_table(rows_by_series)
        required = {
            "total_months", "classified_months", "unclassified_months", "pct_unclassified",
            "num_state_changes", "state_change_rate", "median_state_duration_months",
            "mean_state_duration_months", "num_one_month_reversals", "num_two_month_reversals",
            "num_cooling_heating_cooling_whipsaws", "num_heating_cooling_heating_whipsaws",
            "longest_run_COOLING", "longest_run_HEATING",
        }
        for row in table:
            assert required.issubset(row.keys())


# ---------------------------------------------------------------------
# Section 4: Candidate B explicit-state distributions
# ---------------------------------------------------------------------


class TestCandidateBExplicitReport:
    def test_insufficient_data_reported_as_its_own_percentage(self):
        rows_by_series = {
            "Core PCE": [
                _row(date(2020, 1, 1), chg_3m=None, chg_6m=None, chg_12m=None),
                _row(date(2020, 2, 1), chg_3m=5.0, chg_6m=5.0, chg_12m=3.0),
            ]
        }
        report = candidate_b_explicit_report(rows_by_series)
        row = next(r for r in report if r["series"] == "Core PCE" and r["delta"] == 0.25)
        assert row["pct_INSUFFICIENT_DATA"] == pytest.approx(50.0)
        assert row["pct_HEATING"] == pytest.approx(50.0)
        # Unlike the Section 2 table, total_months == classified_months here
        # by construction, since INSUFFICIENT_DATA is itself a counted state.
        assert row["total_months"] == 2

    def test_covers_all_three_finalist_deltas_per_series(self):
        rows_by_series = {"Core PCE": [_row(date(2020, 1, 1), chg_3m=5.0, chg_6m=5.0, chg_12m=3.0)]}
        report = candidate_b_explicit_report(rows_by_series)
        deltas = sorted({r["delta"] for r in report if r["series"] == "Core PCE"})
        assert deltas == [0.10, 0.25, 0.50]


# ---------------------------------------------------------------------
# Section 7: Neutral-band investigation -- all-state churn decomposes
# exactly into direct reversals + directional-to-neutral transitions
# ---------------------------------------------------------------------


class TestNeutralBandInvestigation:
    def test_candidate_a_all_state_rate_equals_sum_of_direct_and_to_neutral(self):
        # Candidate A only ever produces COOLING/HEATING/STABLE (no MIXED),
        # so every consecutive classified transition is EITHER a direct
        # reversal OR a directional<->neutral move -- never both, never
        # neither. This is the mechanical fact Section 7 asks us to verify.
        rows = [
            _row(date(2020, 1, 1), chg_3m=5.0, chg_6m=5.0, chg_12m=3.0),   # HEATING
            _row(date(2020, 2, 1), chg_3m=3.0, chg_6m=3.0, chg_12m=3.0),   # STABLE
            _row(date(2020, 3, 1), chg_3m=1.0, chg_6m=1.0, chg_12m=3.0),   # COOLING
            _row(date(2020, 4, 1), chg_3m=5.0, chg_6m=5.0, chg_12m=3.0),   # HEATING (direct reversal from COOLING)
        ]
        rows_by_series = {"Core PCE": rows}
        results = neutral_band_investigation(rows_by_series)
        a_rows = [r for r in results if r["candidate"] == "A"]
        assert len(a_rows) == 4  # deltas 0.00, 0.10, 0.25, 0.50
        for r in a_rows:
            # 3 consecutive pairs total in this fixture -- rate * 3 recovers the count.
            total_transitions = round((r["direct_reversal_rate"] + r["directional_to_neutral_rate"]) * 3)
            all_state_transitions = round(r["all_state_change_rate"] * 3)
            assert total_transitions == all_state_transitions

    def test_covers_candidate_a_four_deltas_and_b_explicit_three_deltas(self):
        rows_by_series = {"Core PCE": [_row(date(2020, 1, 1), chg_3m=5.0, chg_6m=5.0, chg_12m=3.0)]}
        results = neutral_band_investigation(rows_by_series)
        a_deltas = sorted(r["delta"] for r in results if r["candidate"] == "A")
        b_deltas = sorted(r["delta"] for r in results if r["candidate"] == "B_explicit")
        assert a_deltas == [0.00, 0.10, 0.25, 0.50]
        assert b_deltas == [0.10, 0.25, 0.50]


# ---------------------------------------------------------------------
# Section 5: Cross-measure confirmation hierarchy
# ---------------------------------------------------------------------


class TestCrossMeasureConfirmation:
    def test_align_two_restricts_to_common_dates_only(self):
        rows_a = [_row(date(2020, 1, 1)), _row(date(2020, 2, 1)), _row(date(2020, 3, 1))]
        rows_b = [_row(date(2020, 2, 1)), _row(date(2020, 3, 1)), _row(date(2020, 4, 1))]
        aligned_a, aligned_b = align_two(rows_a, rows_b)
        assert [r.date for r in aligned_a] == [date(2020, 2, 1), date(2020, 3, 1)]
        assert [r.date for r in aligned_b] == [date(2020, 2, 1), date(2020, 3, 1)]

    def test_underlying_agrees_headline_disagrees_is_detected(self):
        d = date(2020, 3, 1)
        # Both underlying measures HEATING; headline measures split COOLING/HEATING.
        rows_by_series = {
            "Core PCE": [_row(d, chg_3m=5.0, chg_6m=5.0, chg_12m=3.0)],       # HEATING
            "Core CPI": [_row(d, chg_3m=5.0, chg_6m=5.0, chg_12m=3.0)],       # HEATING
            "Headline PCE": [_row(d, chg_3m=1.0, chg_6m=1.0, chg_12m=3.0)],   # COOLING
            "Headline CPI": [_row(d, chg_3m=5.0, chg_6m=5.0, chg_12m=3.0)],   # HEATING
        }
        results = cross_measure_confirmation_report(rows_by_series)
        row = next(r for r in results if r["delta"] == 0.25)
        assert row["all_four_classified_months"] == 1
        assert row["underlying_agrees_headline_disagrees_pct"] == pytest.approx(100.0)
        assert row["all_four_agree_pct"] == pytest.approx(0.0)

    def test_underlying_and_headline_directionally_opposite_is_detected(self):
        d = date(2020, 3, 1)
        rows_by_series = {
            "Core PCE": [_row(d, chg_3m=5.0, chg_6m=5.0, chg_12m=3.0)],       # HEATING
            "Core CPI": [_row(d, chg_3m=5.0, chg_6m=5.0, chg_12m=3.0)],       # HEATING
            "Headline PCE": [_row(d, chg_3m=1.0, chg_6m=1.0, chg_12m=3.0)],   # COOLING
            "Headline CPI": [_row(d, chg_3m=1.0, chg_6m=1.0, chg_12m=3.0)],   # COOLING
        }
        results = cross_measure_confirmation_report(rows_by_series)
        row = next(r for r in results if r["delta"] == 0.25)
        assert row["underlying_headline_directionally_opposite_pct"] == pytest.approx(100.0)
        assert row["all_four_agree_pct"] == pytest.approx(0.0)

    def test_insufficient_data_month_excluded_from_all_four_hierarchy(self):
        d = date(2020, 3, 1)
        rows_by_series = {
            "Core PCE": [_row(d, chg_3m=5.0, chg_6m=5.0, chg_12m=3.0)],
            "Core CPI": [_row(d, chg_3m=None, chg_6m=None, chg_12m=None)],  # INSUFFICIENT_DATA
            "Headline PCE": [_row(d, chg_3m=5.0, chg_6m=5.0, chg_12m=3.0)],
            "Headline CPI": [_row(d, chg_3m=5.0, chg_6m=5.0, chg_12m=3.0)],
        }
        results = cross_measure_confirmation_report(rows_by_series)
        row = next(r for r in results if r["delta"] == 0.25)
        assert row["all_four_classified_months"] == 0
        assert row["all_four_agree_pct"] is None


# ---------------------------------------------------------------------
# Section 3: Turn-persistence -- continuity, not "matches again later"
# ---------------------------------------------------------------------


class TestTurnPersistence:
    def test_persisted_3_requires_continuous_direction_not_a_flip_back(self):
        # HEATING, then a 1-month reversal to COOLING, then back to HEATING.
        # This must NOT count as "persisted >= 3 months" even though month
        # index+2 matches the expected direction again (regression test for
        # a bug where persistence was checked pointwise instead of continuously).
        window_dates = [date(2020, 1, 1), date(2020, 2, 1), date(2020, 3, 1), date(2020, 4, 1)]
        rows = {
            window_dates[0]: _row(window_dates[0], chg_3m=5.0, chg_6m=5.0, chg_12m=3.0),  # HEATING
            window_dates[1]: _row(window_dates[1], chg_3m=1.0, chg_6m=1.0, chg_12m=3.0),  # COOLING
            window_dates[2]: _row(window_dates[2], chg_3m=5.0, chg_6m=5.0, chg_12m=3.0),  # HEATING
            window_dates[3]: _row(window_dates[3], chg_3m=5.0, chg_6m=5.0, chg_12m=3.0),  # HEATING
        }
        rows_by_series = {"Core PCE": list(rows.values())}
        episodes = [("Synthetic episode", window_dates[0], window_dates[-1], "HEATING", "test fixture")]
        import research.inflation_momentum.finalist_study as fs
        original = fs.TURN_EPISODES
        try:
            fs.TURN_EPISODES = episodes
            report = turn_persistence_report(rows_by_series)
        finally:
            fs.TURN_EPISODES = original
        entry = report[0]["per_finalist"]["A_delta_0.25"]
        assert entry["first_entered_direction_on"] == "2020-01-01"
        assert entry["reversed_within_1_month"] is True
        assert entry["persisted_at_least_2_months"] is False
        assert entry["persisted_at_least_3_months"] is False

    def test_persisted_3_true_for_genuinely_continuous_direction(self):
        window_dates = [date(2020, 1, 1), date(2020, 2, 1), date(2020, 3, 1)]
        rows = [
            _row(window_dates[0], chg_3m=5.0, chg_6m=5.0, chg_12m=3.0),
            _row(window_dates[1], chg_3m=5.0, chg_6m=5.0, chg_12m=3.0),
            _row(window_dates[2], chg_3m=5.0, chg_6m=5.0, chg_12m=3.0),
        ]
        rows_by_series = {"Core PCE": rows}
        episodes = [("Synthetic episode", window_dates[0], window_dates[-1], "HEATING", "test fixture")]
        import research.inflation_momentum.finalist_study as fs
        original = fs.TURN_EPISODES
        try:
            fs.TURN_EPISODES = episodes
            report = turn_persistence_report(rows_by_series)
        finally:
            fs.TURN_EPISODES = original
        entry = report[0]["per_finalist"]["A_delta_0.25"]
        assert entry["persisted_at_least_2_months"] is True
        assert entry["persisted_at_least_3_months"] is True
        assert entry["reversed_within_1_month"] is False

    def test_no_reference_direction_never_manufactures_a_signal(self):
        # The "2025-latest available period" episode style: no presumed
        # direction, so no finalist should ever report a "first entered" date.
        window_dates = [date(2020, 1, 1), date(2020, 2, 1)]
        rows = [_row(window_dates[0], chg_3m=5.0, chg_6m=5.0, chg_12m=3.0), _row(window_dates[1], chg_3m=1.0, chg_6m=1.0, chg_12m=3.0)]
        rows_by_series = {"Core PCE": rows}
        episodes = [("No-direction episode", window_dates[0], window_dates[-1], None, "test fixture")]
        import research.inflation_momentum.finalist_study as fs
        original = fs.TURN_EPISODES
        try:
            fs.TURN_EPISODES = episodes
            report = turn_persistence_report(rows_by_series)
        finally:
            fs.TURN_EPISODES = original
        entry = report[0]["per_finalist"]["A_delta_0.25"]
        assert entry["first_entered_direction_on"] is None

    def test_seven_named_episodes_present_with_documented_reference_points(self):
        assert len(TURN_EPISODES) == 7
        for name, start, end, direction, note in TURN_EPISODES:
            assert start < end
            assert note  # every episode's reference point must be documented, per Section 3


# ---------------------------------------------------------------------
# Section 6: Missing-confirmation behavior
# ---------------------------------------------------------------------


class TestMissingConfirmationCheck:
    def test_core_pce_unaffected_when_core_cpi_missing_same_month(self):
        gap_date = date(2025, 10, 1)
        rows_by_series = {
            "Core PCE": [_row(gap_date, chg_3m=5.0, chg_6m=5.0, chg_12m=3.0)],  # HEATING, fully classified
            "Core CPI": [_row(gap_date, chg_3m=None, chg_6m=None, chg_12m=None)],  # INSUFFICIENT_DATA
            "Headline PCE": [_row(gap_date, chg_3m=5.0, chg_6m=5.0, chg_12m=3.0)],
            "Headline CPI": [_row(gap_date, chg_3m=None, chg_6m=None, chg_12m=None)],
        }
        result = missing_confirmation_check(rows_by_series)
        assert result["core_pce_classification_unaffected_by_missing_core_cpi"] is True
        assert result["core_cpi_confirmation_correctly_reports_insufficient_data"] is True
        assert result["gap_month_correctly_not_double_counted_as_agreement_or_disagreement"] is True

    def test_missing_gap_date_in_fixture_reports_error_not_a_fabricated_result(self):
        rows_by_series = {"Core PCE": [], "Core CPI": []}
        result = missing_confirmation_check(rows_by_series)
        assert "error" in result


# ---------------------------------------------------------------------
# End-to-end determinism (mirrors TestStudyEndToEndDeterminism in
# test_inflation_momentum.py) -- skips gracefully with no cached data.
# ---------------------------------------------------------------------


class TestFinalistStudyEndToEndDeterminism:
    def test_repeated_run_produces_identical_output_files(self, tmp_path, monkeypatch):
        data_dir = REPO_ROOT / "research" / "inflation_momentum" / "data"
        if not any(data_dir.glob("*.json")):
            pytest.skip("No cached FRED data (research/inflation_momentum/data/*.json) -- run fetch_data.py first.")

        from research.inflation_momentum import finalist_study

        out_a = tmp_path / "run_a"
        out_b = tmp_path / "run_b"
        monkeypatch.setattr(finalist_study, "OUTPUTS_DIR", out_a)
        out_a.mkdir()
        finalist_study.main()
        monkeypatch.setattr(finalist_study, "OUTPUTS_DIR", out_b)
        out_b.mkdir()
        finalist_study.main()

        files_a = sorted(p.name for p in out_a.iterdir())
        files_b = sorted(p.name for p in out_b.iterdir())
        assert files_a == files_b
        for name in files_a:
            assert (out_a / name).read_text() == (out_b / name).read_text(), f"{name} differed between runs"
