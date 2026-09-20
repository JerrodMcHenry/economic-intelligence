"""Unit tests for `app.domain.rates` -- the pure `rates_v1.0`
arithmetic (Increment #29).

No database, no network, no fixtures beyond plain lists: every function
under test is a total function of its arguments. The properties these
tests protect are the ones the methodology actually promises:
observation-counted windows, exact-date alignment, basis-point
correctness, and "missing is never zero".
"""

from datetime import date

import pytest

from app.domain.rates import (
    RateObservation,
    align_on_exact_date,
    basis_point_change,
    change_over_sessions,
    historical_session_changes,
    inflation_compensation_series,
    latest_observation,
    percentage_point_difference,
    rank_against,
    spread_series,
    to_basis_points,
    usable_observations,
)


def obs(day: int, value: float | None, month: int = 1) -> RateObservation:
    return RateObservation(observation_date=date(2026, month, day), value=value)


class TestBasisPoints:
    def test_percentage_points_convert_to_basis_points(self):
        assert to_basis_points(0.15) == 15.0
        assert to_basis_points(1.0) == 100.0
        assert to_basis_points(-0.25) == -25.0

    def test_change_follows_direction_of_travel(self):
        # The increment's own worked example: 4.25% -> 4.40% is +15bp.
        assert basis_point_change(4.25, 4.40) == 15.0
        assert basis_point_change(4.40, 4.25) == -15.0

    def test_no_floating_point_residue_leaks_into_results(self):
        """0.15 is not exactly representable in binary; the naive
        expression yields 15.000000000000002. Rounding is centralized in
        `to_basis_points` precisely so no caller has to know that."""
        assert basis_point_change(4.25, 4.40) == 15.0
        assert basis_point_change(2.55, 2.68) == 13.0
        assert percentage_point_difference(5.01, 2.68) == 2.33

    def test_zero_change_is_exactly_zero(self):
        assert basis_point_change(4.25, 4.25) == 0.0


class TestUsableObservations:
    def test_null_values_are_dropped_never_zero_filled(self):
        result = usable_observations([obs(1, 4.0), obs(2, None), obs(3, 4.2)])
        assert [o.observation_date.day for o in result] == [1, 3]

    def test_input_order_is_not_trusted(self):
        result = usable_observations([obs(3, 4.2), obs(1, 4.0), obs(2, 4.1)])
        assert [o.observation_date.day for o in result] == [1, 2, 3]

    def test_latest_observation_of_empty_series_is_none(self):
        assert latest_observation([]) is None
        assert latest_observation([obs(1, None)]) is None


class TestChangeOverSessions:
    def test_one_session_compares_against_the_previous_published_session(self):
        """Sessions are observations, not calendar days: Friday ->
        Monday is one session even though three calendar days passed."""
        friday = RateObservation(observation_date=date(2026, 9, 11), value=4.90)
        monday = RateObservation(observation_date=date(2026, 9, 14), value=5.00)
        result = change_over_sessions([friday, monday], 1)
        assert result.available is True
        assert result.change_basis_points == 10.0
        assert result.from_date == date(2026, 9, 11)
        assert result.to_date == date(2026, 9, 14)

    def test_five_sessions_counts_observations_not_days(self):
        series = [obs(day, 4.0 + day / 100) for day in range(1, 11)]
        result = change_over_sessions(series, 5)
        assert result.available is True
        assert result.from_value == pytest.approx(4.05)
        assert result.to_value == pytest.approx(4.10)
        assert result.change_basis_points == pytest.approx(5.0)

    def test_null_sessions_do_not_count_toward_the_window(self):
        series = [obs(1, 4.00), obs(2, None), obs(3, None), obs(4, 4.10)]
        result = change_over_sessions(series, 1)
        assert result.from_date == date(2026, 1, 1)
        assert result.to_date == date(2026, 1, 4)
        assert result.change_basis_points == 10.0

    def test_insufficient_history_is_unavailable_never_zero(self):
        result = change_over_sessions([obs(1, 4.0)], 1)
        assert result.available is False
        assert result.change_basis_points is None
        assert result.from_date is None and result.to_date is None

    def test_exactly_enough_history_is_available(self):
        result = change_over_sessions([obs(1, 4.0), obs(2, 4.1)], 1)
        assert result.available is True

    def test_empty_series_is_unavailable(self):
        assert change_over_sessions([], 5).available is False

    def test_zero_or_negative_sessions_is_a_programming_error(self):
        with pytest.raises(ValueError):
            change_over_sessions([obs(1, 4.0)], 0)


class TestHistoricalSessionChanges:
    def test_every_window_of_the_requested_length_is_produced(self):
        series = [obs(day, 4.0 + day / 100) for day in range(1, 6)]
        changes = historical_session_changes(series, 1)
        assert len(changes) == 4
        assert all(value == pytest.approx(1.0) for _, value in changes)

    def test_final_element_matches_change_over_sessions(self):
        series = [obs(1, 4.00), obs(2, 4.05), obs(3, 4.30)]
        assert historical_session_changes(series, 1)[-1][1] == change_over_sessions(series, 1).change_basis_points

    def test_too_short_history_produces_no_windows(self):
        assert historical_session_changes([obs(1, 4.0)], 1) == []


class TestRankAgainst:
    def test_rank_counts_strictly_smaller_values(self):
        result = rank_against([1.0, 2.0, 3.0, 4.0], 3.5)
        assert result.available is True
        assert result.observation_count == 4
        assert result.percentile_rank == 0.75

    def test_magnitude_rank_uses_absolute_size(self):
        """A large negative move is unremarkable in signed terms but
        extreme in magnitude -- both are reported, so neither reading
        can be mistaken for the other."""
        result = rank_against([-1.0, 1.0, 2.0], -10.0)
        assert result.percentile_rank == 0.0
        assert result.magnitude_percentile_rank == 1.0

    def test_empty_population_is_unavailable_not_zero(self):
        result = rank_against([], 5.0)
        assert result.available is False
        assert result.percentile_rank is None

    def test_minimum_and_maximum_are_reported(self):
        result = rank_against([-3.0, 7.0], 1.0)
        assert result.minimum == -3.0
        assert result.maximum == 7.0


class TestAlignment:
    def test_only_exactly_shared_dates_are_paired(self):
        first = [obs(1, 5.0), obs(2, 5.1), obs(3, 5.2)]
        second = [obs(1, 2.5), obs(3, 2.7)]
        pairs = align_on_exact_date(first, second)
        assert [p.observation_date.day for p in pairs] == [1, 3]

    def test_a_missing_counterpart_is_never_forward_filled(self):
        """The core honesty rule: 2 Jan exists on the nominal side only,
        so it produces no pair at all -- not a pair reusing 1 Jan's real
        yield."""
        first = [obs(1, 5.0), obs(2, 5.1)]
        second = [obs(1, 2.5)]
        pairs = align_on_exact_date(first, second)
        assert len(pairs) == 1
        assert pairs[0].observation_date == date(2026, 1, 1)

    def test_null_on_either_side_prevents_a_pair(self):
        assert align_on_exact_date([obs(1, 5.0)], [obs(1, None)]) == []
        assert align_on_exact_date([obs(1, None)], [obs(1, 2.5)]) == []

    def test_no_overlap_produces_no_pairs(self):
        assert align_on_exact_date([obs(1, 5.0)], [obs(2, 2.5)]) == []


class TestSpreadSeries:
    def test_spread_is_long_minus_short_in_percentage_points(self):
        """The SERIES is in percentage points, not basis points -- see
        `spread_series`'s docstring. Callers convert the level once, at
        the presentation boundary."""
        ten_year = [obs(1, 5.01)]
        two_year = [obs(1, 4.76)]
        series = spread_series(ten_year, two_year)
        assert series[0].value == pytest.approx(0.25)
        assert to_basis_points(series[0].value) == pytest.approx(25.0)

    def test_a_spread_change_is_not_scaled_twice(self):
        """Regression (#30): the spread series is consumed by
        `change_over_sessions`, which converts a percentage-point
        difference into basis points. When the series itself was stored
        in basis points, a 2bp move was reported as 200bp."""
        ten_year = [obs(1, 4.94), obs(2, 5.01)]
        two_year = [obs(1, 4.67), obs(2, 4.76)]
        series = spread_series(ten_year, two_year)

        # 27bp -> 25bp is a 2bp narrowing.
        assert to_basis_points(series[0].value) == pytest.approx(27.0)
        assert to_basis_points(series[1].value) == pytest.approx(25.0)
        assert change_over_sessions(series, 1).change_basis_points == pytest.approx(-2.0)

    def test_historical_spread_changes_are_also_in_basis_points(self):
        series = spread_series(
            [obs(1, 4.94), obs(2, 5.01), obs(3, 5.05)],
            [obs(1, 4.67), obs(2, 4.76), obs(3, 4.76)],
        )
        changes = [value for _, value in historical_session_changes(series, 1)]
        assert changes == pytest.approx([-2.0, 4.0])

    def test_inversion_is_reported_as_a_negative_number_with_no_label(self):
        series = spread_series([obs(1, 4.00)], [obs(1, 4.50)])
        assert series[0].value == pytest.approx(-0.50)

    def test_unaligned_dates_produce_an_empty_series(self):
        assert spread_series([obs(1, 5.0)], [obs(2, 4.0)]) == []


class TestInflationCompensationSeries:
    def test_compensation_is_nominal_minus_real_in_percentage_points(self):
        series = inflation_compensation_series([obs(1, 5.01)], [obs(1, 2.68)])
        assert series[0].value == pytest.approx(2.33)

    def test_requires_both_sides_on_the_same_date(self):
        """Nominal publishes 2Y-30Y daily and real only 5Y and longer;
        a date present on one side only must yield nothing rather than a
        silently mismatched pairing."""
        nominal = [obs(1, 5.00), obs(2, 5.05)]
        real = [obs(2, 2.70)]
        series = inflation_compensation_series(nominal, real)
        assert len(series) == 1
        assert series[0].observation_date == date(2026, 1, 2)
        assert series[0].value == pytest.approx(2.35)

    def test_no_overlap_yields_no_compensation_rather_than_zero(self):
        assert inflation_compensation_series([obs(1, 5.0)], [obs(2, 2.5)]) == []
