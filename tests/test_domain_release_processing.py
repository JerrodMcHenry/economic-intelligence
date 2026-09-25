"""Pure-domain tests for Increment #18's observation-change
classification and affected-period computation (app.domain.release_processing).

No database, no FRED, no FastAPI -- every test here is a plain function
call against plain values, mirroring the existing style of
tests/test_domain_inflation.py and tests/test_domain_releases.py.
"""

from datetime import date

import pytest

from app.domain.release_processing import (
    affected_evaluation_periods,
    classify_observation_change,
    components_for_series,
    five_year_observation_start,
)


class TestClassifyObservationChange:
    def test_not_existed_before_is_new_even_with_a_value(self):
        assert classify_observation_change(existed_before=False, previous_value=None, new_value=101.0) == "NEW"

    def test_existed_before_same_value_is_unchanged(self):
        assert classify_observation_change(existed_before=True, previous_value=100.0, new_value=100.0) == "UNCHANGED"

    def test_existed_before_different_value_is_revised(self):
        assert classify_observation_change(existed_before=True, previous_value=100.0, new_value=101.0) == "REVISED"

    def test_both_none_is_unchanged(self):
        assert classify_observation_change(existed_before=True, previous_value=None, new_value=None) == "UNCHANGED"

    def test_previously_missing_now_present_is_revised_not_dropped(self):
        """A transition out of 'missing' is a real, auditable event --
        never silently ignored just because the old value was None."""
        assert classify_observation_change(existed_before=True, previous_value=None, new_value=100.0) == "REVISED"

    def test_previously_present_now_missing_is_revised_not_dropped(self):
        assert classify_observation_change(existed_before=True, previous_value=100.0, new_value=None) == "REVISED"

    def test_is_deterministic_and_repeatable(self):
        args = dict(existed_before=True, previous_value=2.844, new_value=2.846)
        assert classify_observation_change(**args) == classify_observation_change(**args) == "REVISED"

    def test_exact_float_inequality_no_tolerance(self):
        """Tiny differences are still REVISED -- no epsilon, matching
        inflation_what_changed_v1.0's own 'no epsilon' float rule."""
        assert classify_observation_change(existed_before=True, previous_value=2.844, new_value=2.8440001) == "REVISED"


class TestFiveYearObservationStart:
    def test_ordinary_date_subtracts_exactly_five_calendar_years(self):
        assert five_year_observation_start(date(2026, 7, 15)) == date(2021, 7, 15)

    def test_leap_day_five_years_before_a_non_leap_year_falls_back_to_feb_28(self):
        assert five_year_observation_start(date(2024, 2, 29)) == date(2019, 2, 28)

    def test_leap_day_from_a_different_leap_year_also_falls_back_to_feb_28(self):
        # 2028 is a leap year; 2028 - 5 = 2023, which is NOT a leap year
        # (2024, not 2023, is the nearest one) -- included as a second,
        # independent leap-year boundary case rather than assuming the
        # first one generalizes.
        assert five_year_observation_start(date(2028, 2, 29)) == date(2023, 2, 28)

    def test_not_an_approximation_of_365_times_5_days(self):
        # 365*5 = 1825 days before 2026-07-15 is NOT 2021-07-15 (it's a
        # day off, since two of those five years contain a leap day) --
        # this proves exact calendar-year arithmetic is actually used.
        from datetime import timedelta

        approx = date(2026, 7, 15) - timedelta(days=365 * 5)
        assert five_year_observation_start(date(2026, 7, 15)) != approx


class TestComponentsForSeries:
    def test_primary_series_feeds_primary_momentum_and_confirmation(self):
        assert components_for_series("us.pce.core.price-index.sa.monthly") == frozenset({"PRIMARY_MOMENTUM", "CONFIRMATION"})

    def test_confirmation_series_feeds_confirmation_only(self):
        assert components_for_series("us.cpi.core.price-index.sa.monthly") == frozenset({"CONFIRMATION"})

    def test_target_series_feeds_target_and_headline_pce(self):
        assert components_for_series("us.pce.headline.price-index.sa.monthly") == frozenset({"TARGET", "HEADLINE_PCE"})

    def test_headline_cpi_series_feeds_headline_cpi_only(self):
        assert components_for_series("us.cpi.headline.price-index.sa.monthly") == frozenset({"HEADLINE_CPI"})

    def test_unrelated_series_feeds_nothing(self):
        """A future curated series with no deterministic Inflation
        consumer yet -- an empty result, never an error and never a
        fabricated component."""
        assert components_for_series("UNRATE") == frozenset()


class TestAffectedEvaluationPeriods:
    def test_a_changed_date_always_affects_its_own_period(self):
        changed = frozenset({date(2026, 6, 1)})
        result = affected_evaluation_periods(changed, observation_dates_after=frozenset())
        assert date(2026, 6, 1) in result

    def test_forward_horizons_included_only_when_a_later_observation_exists(self):
        changed = frozenset({date(2026, 5, 1)})
        # August exists (May + 3); September, November, and next May do not.
        after = frozenset({date(2026, 5, 1), date(2026, 8, 1)})
        result = affected_evaluation_periods(changed, after)
        assert result == frozenset({date(2026, 5, 1), date(2026, 8, 1)})

    def test_no_forward_horizon_included_when_no_later_observation_exists_yet(self):
        changed = frozenset({date(2026, 5, 1)})
        result = affected_evaluation_periods(changed, observation_dates_after=frozenset({date(2026, 5, 1)}))
        assert result == frozenset({date(2026, 5, 1)})

    def test_multiple_changed_dates_feeding_the_same_later_period_deduplicate(self):
        """May (t-3), February (t-6), and last August (t-12) are all
        distinct endpoints of the SAME August evaluation -- proves the
        shared later period is only computed once (a set), the
        multi-observation-consistency property #18 requires."""
        changed = frozenset({date(2026, 5, 1), date(2026, 2, 1), date(2025, 8, 1)})
        after = frozenset({date(2026, 5, 1), date(2026, 2, 1), date(2025, 8, 1), date(2026, 8, 1)})
        result = affected_evaluation_periods(changed, after)
        assert date(2026, 8, 1) in result
        assert result == frozenset({date(2026, 5, 1), date(2026, 2, 1), date(2025, 8, 1), date(2026, 8, 1)})

    def test_pure_and_repeatable(self):
        changed = frozenset({date(2026, 6, 1)})
        after = frozenset({date(2026, 6, 1), date(2026, 9, 1)})
        assert affected_evaluation_periods(changed, after) == affected_evaluation_periods(changed, after)

    def test_empty_changed_dates_yields_empty_result(self):
        assert affected_evaluation_periods(frozenset(), frozenset({date(2026, 1, 1)})) == frozenset()


class TestNoIOImports:
    def test_module_has_no_io_imports(self):
        """Static guard, mirroring tests/test_domain_architectural_independence.py's
        own style -- redundant with that suite (which also scans this
        file) but kept here too as a direct, local safety net."""
        import ast
        from pathlib import Path

        tree = ast.parse(Path("app/domain/release_processing.py").read_text())
        forbidden = {"sqlalchemy", "fastapi", "httpx", "openai"}
        for node in ast.walk(tree):
            module = None
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name
            elif isinstance(node, ast.ImportFrom) and node.module:
                module = node.module
            if module is not None:
                assert not any(module == f or module.startswith(f + ".") for f in forbidden), module


if __name__ == "__main__":
    pytest.main([__file__])
