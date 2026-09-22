"""The pure Housing domain (Increment #45).

Three lines of literals per test, no database, no client, no clock --
which is the property `app/domain/` exists to have, and the reason these
numbers are reproducible by hand.

The values used throughout are the real ones Census published for August
2026 and the revised July 2026 figures, in MacroChipz's canonical unit
(housing units, not Census's thousands). Using real figures means the
expected percentages below are the SAME percentages Census's own release
text states, so a sign error or an inverted comparison shows up as a
disagreement with the published source rather than as a self-consistent
mistake.
"""

from datetime import date

import pytest

from app.domain.housing import (
    NO_COMPARISON,
    HousingObservation,
    is_baseline_import,
    latest,
    preceding_comparison,
    recent_window,
    year_ago_comparison,
)


def _obs(year: int, month: int, value: float) -> HousingObservation:
    return HousingObservation(observation_date=date(year, month, 1), value=value)


#: Building permits, seasonally adjusted annual rate, as published.
AUG_2025_PERMITS = _obs(2025, 8, 1_347_000)
JUL_2026_PERMITS = _obs(2026, 7, 1_433_000)
AUG_2026_PERMITS = _obs(2026, 8, 1_394_000)


class TestLatest:
    def test_empty_is_none_not_zero(self) -> None:
        assert latest([]) is None

    def test_the_newest_observation_wins(self) -> None:
        assert latest([JUL_2026_PERMITS, AUG_2026_PERMITS]) == AUG_2026_PERMITS

    def test_input_order_does_not_matter(self) -> None:
        """A pure function that depends on its caller's ordering has a
        hidden precondition."""
        assert latest([AUG_2026_PERMITS, JUL_2026_PERMITS]) == AUG_2026_PERMITS


class TestPrecedingComparison:
    def test_no_observations_is_no_comparison(self) -> None:
        assert preceding_comparison([]) == NO_COMPARISON

    def test_one_observation_is_no_comparison(self) -> None:
        """Never a comparison against zero, and never against itself."""
        assert preceding_comparison([AUG_2026_PERMITS]) == NO_COMPARISON

    def test_the_change_matches_the_published_release(self) -> None:
        result = preceding_comparison([JUL_2026_PERMITS, AUG_2026_PERMITS])
        assert result.period == date(2026, 7, 1)
        assert result.value == 1_433_000
        assert result.change == -39_000
        # Census: permits in August "is 2.7 percent below the revised
        # July rate of 1,433,000".
        assert round(result.change_percent, 1) == -2.7

    def test_preceding_means_the_preceding_PUBLISHED_observation(self) -> None:
        """Not "last calendar month". A policy naming a calendar month
        needs a rule for a missing one, and every such rule quietly
        changes the reported number."""
        result = preceding_comparison([_obs(2026, 3, 1_000_000), AUG_2026_PERMITS])
        assert result.period == date(2026, 3, 1)

    def test_every_field_is_absent_together(self) -> None:
        """A half-filled comparison reads as "no change" rather than "no
        comparison"."""
        result = preceding_comparison([AUG_2026_PERMITS])
        assert (result.period, result.value, result.change, result.change_percent) == (None, None, None, None)

    def test_a_zero_earlier_value_gives_no_percentage_rather_than_infinity(self) -> None:
        result = preceding_comparison([_obs(2026, 7, 0.0), AUG_2026_PERMITS])
        assert result.change == 1_394_000
        assert result.change_percent is None

    def test_an_unchanged_value_is_a_zero_change_not_a_missing_one(self) -> None:
        result = preceding_comparison([_obs(2026, 7, 1_394_000), AUG_2026_PERMITS])
        assert result.change == 0
        assert result.change_percent == 0


class TestYearAgoComparison:
    def test_no_observations_is_no_comparison(self) -> None:
        assert year_ago_comparison([]) == NO_COMPARISON

    def test_the_change_matches_the_published_release(self) -> None:
        result = year_ago_comparison([AUG_2025_PERMITS, JUL_2026_PERMITS, AUG_2026_PERMITS])
        assert result.period == date(2025, 8, 1)
        assert result.value == 1_347_000
        # Census: permits in August "is 3.5 percent above the August 2025
        # rate of 1,347,000".
        assert round(result.change_percent, 1) == 3.5

    def test_an_exact_calendar_match_is_required(self) -> None:
        """A year-over-year figure whose span is not a year is mislabelled
        rather than approximate, so the nearest month is never
        substituted."""
        result = year_ago_comparison([_obs(2025, 9, 1_347_000), AUG_2026_PERMITS])
        assert result == NO_COMPARISON

    def test_it_compares_against_the_latest_not_the_first(self) -> None:
        observations = [_obs(2024, 8, 900_000), AUG_2025_PERMITS, AUG_2026_PERMITS]
        assert year_ago_comparison(observations).period == date(2025, 8, 1)

    def test_a_leap_year_boundary_is_not_special(self) -> None:
        """Every observation sits on the first of its month, so February
        needs no special case -- asserted rather than assumed."""
        result = year_ago_comparison([_obs(2023, 2, 100.0), _obs(2024, 2, 110.0)])
        assert result.period == date(2023, 2, 1)
        assert result.change == 10.0


class TestRecentWindow:
    def test_it_returns_the_most_recent_n_oldest_first(self) -> None:
        observations = [_obs(2026, month, float(month)) for month in range(1, 9)]
        window = recent_window(observations, 3)
        assert [item.observation_date.month for item in window] == [6, 7, 8]

    def test_fewer_than_requested_is_reported_by_being_shorter(self) -> None:
        """Nothing is interpolated, carried forward or zero-filled to
        reach the requested length."""
        window = recent_window([AUG_2026_PERMITS], 60)
        assert len(window) == 1

    def test_an_empty_series_gives_an_empty_window(self) -> None:
        assert recent_window([], 60) == []

    def test_a_gap_is_preserved_as_a_gap(self) -> None:
        """Counting published observations means a missing month is simply
        absent -- it is never filled in to make the window contiguous."""
        window = recent_window([_obs(2026, 1, 1.0), _obs(2026, 5, 5.0), _obs(2026, 6, 6.0)], 3)
        assert [item.observation_date.month for item in window] == [1, 5, 6]

    @pytest.mark.parametrize("months", [0, -1])
    def test_a_non_positive_window_is_a_programming_error(self, months: int) -> None:
        with pytest.raises(ValueError):
            recent_window([AUG_2026_PERMITS], months)


class TestIsBaselineImport:
    """THE #43 boundary for a new source. Everything about whether
    Housing's history can masquerade as observed revision evidence is
    decided here."""

    def test_an_empty_series_makes_everything_a_baseline(self) -> None:
        """The first import. MacroChipz is learning sixty-seven years of
        published history at one instant; it watched none of it."""
        assert is_baseline_import(False, None, date(2026, 8, 1)) is True
        assert is_baseline_import(False, None, date(1959, 1, 1)) is True

    def test_a_series_with_no_latest_period_is_treated_as_empty(self) -> None:
        assert is_baseline_import(True, None, date(2026, 8, 1)) is True

    def test_filling_history_backwards_is_a_baseline(self) -> None:
        """A later sync that reaches further back has still not watched
        those months arrive."""
        assert is_baseline_import(True, date(2026, 8, 1), date(1990, 3, 1)) is True

    def test_a_genuinely_new_month_is_observed_not_a_baseline(self) -> None:
        """The case that must NOT be a baseline: MacroChipz was watching,
        and this is real news."""
        assert is_baseline_import(True, date(2026, 8, 1), date(2026, 9, 1)) is False

    def test_a_write_to_the_latest_stored_month_is_not_a_baseline(self) -> None:
        """This is the revision path. MacroChipz was holding the earlier
        value, so if the value differs it genuinely watched it change --
        the one case where "originally reported" is provable."""
        assert is_baseline_import(True, date(2026, 8, 1), date(2026, 8, 1)) is False
