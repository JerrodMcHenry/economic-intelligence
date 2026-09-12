"""Golden tests for app.domain.analysis -- pure, deterministic, zero-I/O
functions. No network, no database, no OpenAI, no FRED: offline only.

Expected values (including every Pearson correlation figure) are
independently hand-derived from the documented formula/algorithm, never
obtained by calling the implementation and asserting on its output.
"""

from datetime import date

from app.domain.analysis import align_series, calculate_spread, count_usable_pairs, pearson_correlation
from app.models.analysis import ComparisonObservation
from app.models.series import Observation

JAN, FEB, MAR, APR = date(2024, 1, 1), date(2024, 2, 1), date(2024, 3, 1), date(2024, 4, 1)


class TestAlignSeries:
    def test_canonical_example_exact_date_inner_join(self):
        """A: Jan, Feb, Mar. B: Jan, Mar, Apr. Expected matched dates:
        Jan, Mar only -- Feb and Apr each appear in only one series and
        must be excluded (no positional alignment, no interpolation)."""
        series_a = [
            Observation(date=JAN, value=1.0),
            Observation(date=FEB, value=2.0),
            Observation(date=MAR, value=3.0),
        ]
        series_b = [
            Observation(date=JAN, value=10.0),
            Observation(date=MAR, value=30.0),
            Observation(date=APR, value=40.0),
        ]
        result = align_series(series_a, series_b)
        assert [r.date for r in result] == [JAN, MAR]
        assert result[0].value_a == 1.0 and result[0].value_b == 10.0
        assert result[1].value_a == 3.0 and result[1].value_b == 30.0

    def test_no_positional_alignment(self):
        """Same-length lists whose dates don't correspond positionally
        must still align by date, not by list index."""
        series_a = [Observation(date=JAN, value=1.0), Observation(date=MAR, value=3.0)]
        series_b = [Observation(date=FEB, value=2.0), Observation(date=MAR, value=30.0)]
        result = align_series(series_a, series_b)
        assert [r.date for r in result] == [MAR]  # only the actual shared date
        assert result[0].value_a == 3.0 and result[0].value_b == 30.0

    def test_ascending_chronological_order_regardless_of_input_order(self):
        series_a = [Observation(date=MAR, value=3.0), Observation(date=JAN, value=1.0)]
        series_b = [Observation(date=JAN, value=10.0), Observation(date=MAR, value=30.0)]
        result = align_series(series_a, series_b)
        assert [r.date for r in result] == [JAN, MAR]

    def test_matched_date_with_null_on_either_side_is_preserved(self):
        series_a = [Observation(date=JAN, value=None), Observation(date=FEB, value=5.0)]
        series_b = [Observation(date=JAN, value=100.0), Observation(date=FEB, value=None)]
        result = align_series(series_a, series_b)
        assert [r.date for r in result] == [JAN, FEB]
        assert result[0].value_a is None and result[0].value_b == 100.0
        assert result[1].value_a == 5.0 and result[1].value_b is None

    def test_input_not_mutated(self):
        series_a = [Observation(date=JAN, value=1.0), Observation(date=FEB, value=2.0)]
        series_b = [Observation(date=JAN, value=10.0)]
        snap_a = [Observation(date=o.date, value=o.value) for o in series_a]
        snap_b = [Observation(date=o.date, value=o.value) for o in series_b]
        align_series(series_a, series_b)
        assert series_a == snap_a
        assert series_b == snap_b

    def test_repeated_execution_identical(self):
        series_a = [Observation(date=JAN, value=1.0), Observation(date=MAR, value=3.0)]
        series_b = [Observation(date=JAN, value=10.0), Observation(date=MAR, value=30.0)]
        assert align_series(series_a, series_b) == align_series(series_a, series_b)


class TestCalculateSpread:
    def test_positive_negative_and_zero_spread(self):
        aligned = [
            ComparisonObservation(date=JAN, value_a=10.0, value_b=4.0),  # +6
            ComparisonObservation(date=FEB, value_a=4.0, value_b=10.0),  # -6
            ComparisonObservation(date=MAR, value_a=5.0, value_b=5.0),  # 0
        ]
        result = calculate_spread(aligned)
        assert [r.spread for r in result] == [6.0, -6.0, 0.0]

    def test_null_value_a_produces_null_spread(self):
        aligned = [ComparisonObservation(date=JAN, value_a=None, value_b=5.0)]
        assert calculate_spread(aligned)[0].spread is None

    def test_null_value_b_produces_null_spread(self):
        aligned = [ComparisonObservation(date=JAN, value_a=5.0, value_b=None)]
        assert calculate_spread(aligned)[0].spread is None

    def test_both_null_produces_null_spread(self):
        aligned = [ComparisonObservation(date=JAN, value_a=None, value_b=None)]
        assert calculate_spread(aligned)[0].spread is None

    def test_input_not_mutated(self):
        aligned = [ComparisonObservation(date=JAN, value_a=10.0, value_b=4.0)]
        snapshot = [a.model_copy() for a in aligned]
        calculate_spread(aligned)
        assert aligned == snapshot

    def test_repeated_execution_identical(self):
        aligned = [ComparisonObservation(date=JAN, value_a=10.0, value_b=4.0)]
        assert calculate_spread(aligned) == calculate_spread(aligned)


class TestCountUsablePairs:
    def test_both_non_null_counts(self):
        aligned = [ComparisonObservation(date=JAN, value_a=1.0, value_b=2.0)]
        assert count_usable_pairs(aligned) == 1

    def test_either_null_does_not_count(self):
        aligned = [
            ComparisonObservation(date=JAN, value_a=None, value_b=2.0),
            ComparisonObservation(date=FEB, value_a=1.0, value_b=None),
        ]
        assert count_usable_pairs(aligned) == 0

    def test_zero_usable_pairs_on_empty_list(self):
        assert count_usable_pairs([]) == 0

    def test_all_usable_pairs(self):
        aligned = [
            ComparisonObservation(date=JAN, value_a=1.0, value_b=2.0),
            ComparisonObservation(date=FEB, value_a=3.0, value_b=4.0),
            ComparisonObservation(date=MAR, value_a=None, value_b=6.0),
        ]
        assert count_usable_pairs(aligned) == 2

    def test_input_not_mutated(self):
        aligned = [ComparisonObservation(date=JAN, value_a=1.0, value_b=2.0)]
        snapshot = [a.model_copy() for a in aligned]
        count_usable_pairs(aligned)
        assert aligned == snapshot

    def test_repeated_execution_identical(self):
        aligned = [ComparisonObservation(date=JAN, value_a=1.0, value_b=2.0)]
        assert count_usable_pairs(aligned) == count_usable_pairs(aligned)


def _aligned_from(xs: list[float | None], ys: list[float | None]) -> list[ComparisonObservation]:
    dates = [date(2024, i + 1, 1) for i in range(len(xs))]
    return [ComparisonObservation(date=d, value_a=x, value_b=y) for d, x, y in zip(dates, xs, ys)]


class TestPearsonCorrelation:
    def test_perfectly_positive_linear_relationship_is_exactly_1(self):
        """y = 2x for x in [1,2,3,4] -- hand-derived: mean_x=2.5, mean_y=5,
        covariance=10, variance_x=5, variance_y=20, r=10/sqrt(100)=1.0."""
        aligned = _aligned_from([1.0, 2.0, 3.0, 4.0], [2.0, 4.0, 6.0, 8.0])
        assert pearson_correlation(aligned) == 1.0

    def test_perfectly_inverse_linear_relationship_is_exactly_minus_1(self):
        """y = -2x + 10 for x in [1,2,3,4] -> y=[8,6,4,2]. Hand-derived:
        covariance=-10, variance_x=5, variance_y=20, r=-10/sqrt(100)=-1.0."""
        aligned = _aligned_from([1.0, 2.0, 3.0, 4.0], [8.0, 6.0, 4.0, 2.0])
        assert pearson_correlation(aligned) == -1.0

    def test_series_correlated_with_itself_is_exactly_1(self):
        """A non-constant series correlated against itself: covariance
        equals variance, so r = variance / sqrt(variance * variance) = 1.0
        exactly, not merely "highly positive"."""
        values = [3.0, 7.0, 2.0, 9.0, 5.0]
        aligned = _aligned_from(values, values)
        assert pearson_correlation(aligned) == 1.0

    def test_fewer_than_two_usable_pairs_returns_none(self):
        assert pearson_correlation(_aligned_from([1.0], [2.0])) is None
        assert pearson_correlation([]) is None

    def test_zero_variance_in_a_returns_none(self):
        aligned = _aligned_from([5.0, 5.0, 5.0], [1.0, 2.0, 3.0])
        assert pearson_correlation(aligned) is None

    def test_zero_variance_in_b_returns_none(self):
        aligned = _aligned_from([1.0, 2.0, 3.0], [5.0, 5.0, 5.0])
        assert pearson_correlation(aligned) is None

    def test_null_pairs_are_ignored_not_counted_as_zero(self):
        """Same 4 perfectly-correlated points as the first test, with two
        null-containing pairs interspersed -- result must be identical
        (exactly 1.0), proving nulls are excluded, not treated as 0."""
        with_nulls = [
            ComparisonObservation(date=date(2024, 1, 1), value_a=1.0, value_b=2.0),
            ComparisonObservation(date=date(2024, 1, 15), value_a=None, value_b=999.0),
            ComparisonObservation(date=date(2024, 2, 1), value_a=2.0, value_b=4.0),
            ComparisonObservation(date=date(2024, 2, 15), value_a=888.0, value_b=None),
            ComparisonObservation(date=date(2024, 3, 1), value_a=3.0, value_b=6.0),
            ComparisonObservation(date=date(2024, 4, 1), value_a=4.0, value_b=8.0),
        ]
        assert pearson_correlation(with_nulls) == 1.0

    def test_result_always_within_closed_unit_interval(self):
        """Sanity property across every non-None result computed in this
        file's other cases -- never outside [-1, 1]."""
        cases = [
            _aligned_from([1.0, 2.0, 3.0, 4.0], [2.0, 4.0, 6.0, 8.0]),
            _aligned_from([1.0, 2.0, 3.0, 4.0], [8.0, 6.0, 4.0, 2.0]),
            _aligned_from([3.0, 7.0, 2.0, 9.0, 5.0], [3.0, 7.0, 2.0, 9.0, 5.0]),
            _aligned_from([1.0, 5.0, 2.0, 9.0], [4.0, 1.0, 8.0, 3.0]),
        ]
        for aligned in cases:
            r = pearson_correlation(aligned)
            assert r is None or -1.0 <= r <= 1.0

    def test_input_not_mutated(self):
        aligned = _aligned_from([1.0, 2.0, 3.0, 4.0], [2.0, 4.0, 6.0, 8.0])
        snapshot = [a.model_copy() for a in aligned]
        pearson_correlation(aligned)
        assert aligned == snapshot

    def test_repeated_execution_identical(self):
        aligned = _aligned_from([1.0, 2.0, 3.0, 4.0], [2.0, 4.0, 6.0, 8.0])
        assert pearson_correlation(aligned) == pearson_correlation(aligned)
