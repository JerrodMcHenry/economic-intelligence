"""Unit tests for the pure Labor release-processing dependency
propagation module (app.domain.labor_release_processing), Increment
#20D.2 -- frozen and normative in
docs/architecture/labor-release-integration-v1.md. Pure, offline,
deterministic: no database, no FRED, no FastAPI.
"""

from datetime import date

from app.domain.labor_release_processing import (
    LABOR_SERIES_IDS,
    PAYEMS_AFFECTED_HORIZONS_MONTHS,
    UNRATE_AFFECTED_HORIZONS_MONTHS,
    labor_affected_evaluation_periods,
    payems_affected_evaluation_periods,
    unrate_affected_evaluation_periods,
)


class TestLaborSeriesIds:
    def test_exactly_the_payroll_and_unemployment_storage_rows(self):
        # #56B: the concept-keyed BLS rows, not FRED's PAYEMS/UNRATE.
        assert LABOR_SERIES_IDS == frozenset({"us.nonfarm.payroll-employment.sa.monthly", "us.unemployment-rate.sa.monthly"})


class TestFrozenHorizonConstants:
    def test_payems_is_the_sparse_set_not_a_contiguous_range(self):
        assert PAYEMS_AFFECTED_HORIZONS_MONTHS == (0, 3, 6)
        assert 1 not in PAYEMS_AFFECTED_HORIZONS_MONTHS
        assert 2 not in PAYEMS_AFFECTED_HORIZONS_MONTHS
        assert 4 not in PAYEMS_AFFECTED_HORIZONS_MONTHS
        assert 5 not in PAYEMS_AFFECTED_HORIZONS_MONTHS

    def test_unrate_is_the_two_disjoint_clusters(self):
        assert UNRATE_AFFECTED_HORIZONS_MONTHS == (0, 1, 2, 12, 13, 14)


class TestPayemsPropagation:
    R = date(2015, 3, 1)

    def test_r_plus_0_3_6_included(self):
        periods = payems_affected_evaluation_periods(frozenset({self.R}))
        assert date(2015, 3, 1) in periods  # r+0
        assert date(2015, 6, 1) in periods  # r+3
        assert date(2015, 9, 1) in periods  # r+6

    def test_r_plus_1_and_2_excluded(self):
        periods = payems_affected_evaluation_periods(frozenset({self.R}))
        assert date(2015, 4, 1) not in periods  # r+1
        assert date(2015, 5, 1) not in periods  # r+2

    def test_exact_period_set(self):
        periods = payems_affected_evaluation_periods(frozenset({self.R}))
        assert periods == frozenset({date(2015, 3, 1), date(2015, 6, 1), date(2015, 9, 1)})

    def test_never_backward(self):
        """A revision at r must never affect a period before r --
        forward-only, per the frozen contract."""
        periods = payems_affected_evaluation_periods(frozenset({self.R}))
        assert all(p >= self.R for p in periods)

    def test_multiple_observations_union_and_dedup(self):
        r1, r2 = date(2015, 1, 1), date(2015, 4, 1)  # r2 = r1 + 3, so r1's own +3 overlaps r2's own +0
        periods = payems_affected_evaluation_periods(frozenset({r1, r2}))
        expected = {date(2015, 1, 1), date(2015, 4, 1), date(2015, 7, 1)} | {date(2015, 4, 1), date(2015, 7, 1), date(2015, 10, 1)}
        assert periods == frozenset(expected)
        # the shared date(2015, 4, 1)/date(2015, 7, 1) candidates are not duplicated -- a frozenset has no duplicates by construction:
        assert len(periods) == len(expected)

    def test_empty_input_produces_empty_output(self):
        assert payems_affected_evaluation_periods(frozenset()) == frozenset()

    def test_year_rollover(self):
        periods = payems_affected_evaluation_periods(frozenset({date(2015, 10, 1)}))
        assert periods == frozenset({date(2015, 10, 1), date(2016, 1, 1), date(2016, 4, 1)})


class TestUnratePropagation:
    R = date(2015, 3, 1)

    def test_current_window_cluster(self):
        periods = unrate_affected_evaluation_periods(frozenset({self.R}))
        assert date(2015, 3, 1) in periods  # r+0
        assert date(2015, 4, 1) in periods  # r+1
        assert date(2015, 5, 1) in periods  # r+2

    def test_prior_year_window_cluster(self):
        periods = unrate_affected_evaluation_periods(frozenset({self.R}))
        assert date(2016, 3, 1) in periods  # r+12
        assert date(2016, 4, 1) in periods  # r+13
        assert date(2016, 5, 1) in periods  # r+14

    def test_offsets_between_the_two_clusters_excluded(self):
        periods = unrate_affected_evaluation_periods(frozenset({self.R}))
        excluded = {date(2015, 6, 1), date(2015, 9, 1), date(2015, 12, 1), date(2016, 1, 1), date(2016, 2, 1)}
        assert periods.isdisjoint(excluded)

    def test_exact_period_set(self):
        periods = unrate_affected_evaluation_periods(frozenset({self.R}))
        assert periods == frozenset(
            {
                date(2015, 3, 1), date(2015, 4, 1), date(2015, 5, 1),
                date(2016, 3, 1), date(2016, 4, 1), date(2016, 5, 1),
            }
        )

    def test_never_backward(self):
        periods = unrate_affected_evaluation_periods(frozenset({self.R}))
        assert all(p >= self.R for p in periods)

    def test_real_2025_10_gap_worked_example(self):
        """The exact real gap #20A.1/#20B/#20C.2 already established:
        if UNRATE's 2025-10 observation is NEW/REVISED, the affected
        evaluation periods are 2025-10/11/12 and 2026-10/11/12."""
        periods = unrate_affected_evaluation_periods(frozenset({date(2025, 10, 1)}))
        assert periods == frozenset(
            {
                date(2025, 10, 1), date(2025, 11, 1), date(2025, 12, 1),
                date(2026, 10, 1), date(2026, 11, 1), date(2026, 12, 1),
            }
        )

    def test_multiple_observations_union_and_dedup(self):
        periods = unrate_affected_evaluation_periods(frozenset({date(2020, 1, 1), date(2020, 6, 1)}))
        expected = (
            {date(2020, 1, 1), date(2020, 2, 1), date(2020, 3, 1), date(2021, 1, 1), date(2021, 2, 1), date(2021, 3, 1)}
            | {date(2020, 6, 1), date(2020, 7, 1), date(2020, 8, 1), date(2021, 6, 1), date(2021, 7, 1), date(2021, 8, 1)}
        )
        assert periods == frozenset(expected)

    def test_empty_input_produces_empty_output(self):
        assert unrate_affected_evaluation_periods(frozenset()) == frozenset()


class TestCrossSeriesUnion:
    def test_union_of_payems_and_unrate_affected_periods(self):
        payems_changed = frozenset({date(2020, 1, 1)})  # -> {2020-01, 2020-04, 2020-07}
        unrate_changed = frozenset({date(2020, 4, 1)})  # -> {2020-04,05,06} + {2021-04,05,06}
        combined = labor_affected_evaluation_periods(payems_changed, unrate_changed)
        assert combined == payems_affected_evaluation_periods(payems_changed) | unrate_affected_evaluation_periods(unrate_changed)
        # the shared date(2020, 4, 1) candidate is evaluated as one set member, not duplicated:
        assert date(2020, 4, 1) in combined
        expected = frozenset(
            {date(2020, 1, 1), date(2020, 4, 1), date(2020, 7, 1)}
            | {date(2020, 4, 1), date(2020, 5, 1), date(2020, 6, 1), date(2021, 4, 1), date(2021, 5, 1), date(2021, 6, 1)}
        )
        assert combined == expected

    def test_non_overlapping_periods_all_present(self):
        payems_changed = frozenset({date(2010, 1, 1)})
        unrate_changed = frozenset({date(2020, 1, 1)})
        combined = labor_affected_evaluation_periods(payems_changed, unrate_changed)
        assert date(2010, 1, 1) in combined and date(2010, 4, 1) in combined and date(2010, 7, 1) in combined
        assert date(2020, 1, 1) in combined and date(2020, 2, 1) in combined and date(2021, 2, 1) in combined

    def test_only_payems_changed(self):
        combined = labor_affected_evaluation_periods(frozenset({date(2015, 3, 1)}), frozenset())
        assert combined == payems_affected_evaluation_periods(frozenset({date(2015, 3, 1)}))

    def test_only_unrate_changed(self):
        combined = labor_affected_evaluation_periods(frozenset(), frozenset({date(2015, 3, 1)}))
        assert combined == unrate_affected_evaluation_periods(frozenset({date(2015, 3, 1)}))

    def test_both_empty(self):
        assert labor_affected_evaluation_periods(frozenset(), frozenset()) == frozenset()


class TestDeterminism:
    def test_repeated_calls_produce_identical_results(self):
        changed = frozenset({date(2015, 3, 1), date(2016, 7, 1)})
        assert payems_affected_evaluation_periods(changed) == payems_affected_evaluation_periods(changed)
        assert unrate_affected_evaluation_periods(changed) == unrate_affected_evaluation_periods(changed)
