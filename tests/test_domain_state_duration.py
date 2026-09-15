"""Unit tests for the pure, domain-agnostic State Duration V1 sequence
helper (`app.domain.state_duration`) -- frozen and normative in
`docs/product/state-duration-v1.md` §29/§45. Pure, offline,
deterministic: no database, no FRED, no FastAPI, no economic content
at all (this module never inspects what a state VALUE means).
"""

from datetime import date

import pytest

from app.domain.state_duration import (
    INSUFFICIENT_DATA_SENTINEL,
    StateDurationEvaluation,
    StateDurationPoint,
    evaluate_state_duration,
)

LOOKBACK = 60


def _point(year: int, month: int, state: str) -> StateDurationPoint:
    return StateDurationPoint(period=date(year, month, 1), state=state)


def _sequence_of_matching_months(n: int, state: str = "COOLING") -> list[StateDurationPoint]:
    """`n` consecutive months, all the same state, most-recent-first,
    starting at 2026-01 and walking backward one exact calendar month
    at a time."""
    points = []
    for i in range(n):
        total_months = 2026 * 12 + 0 - i
        year, month0 = divmod(total_months, 12)
        points.append(_point(year, month0 + 1, state))
    return points


class TestEvaluateStateDurationOneMonthRun:
    def test_one_month_run_when_immediately_preceding_month_differs(self):
        """Frozen §45: a one-month run (current differs from the
        immediately preceding month) -> duration_months=1, EXACT."""
        sequence = [_point(2026, 3, "COOLING"), _point(2026, 2, "STABLE")]
        result = evaluate_state_duration(sequence, LOOKBACK)
        assert result == StateDurationEvaluation(
            duration_months=1,
            earliest_confirmed_period=date(2026, 3, 1),
            boundary_type="EXACT",
            previous_state="STABLE",
            previous_period=date(2026, 2, 1),
        )


class TestEvaluateStateDurationMultiMonthRun:
    def test_multi_month_run_with_differing_prior_state(self):
        """Frozen §45: a multi-month run; a differing prior state ->
        EXACT with correct previous_state/previous_period."""
        sequence = [
            _point(2026, 4, "COOLING"),
            _point(2026, 3, "COOLING"),
            _point(2026, 2, "COOLING"),
            _point(2026, 1, "STABLE"),
        ]
        result = evaluate_state_duration(sequence, LOOKBACK)
        assert result.duration_months == 3
        assert result.earliest_confirmed_period == date(2026, 2, 1)
        assert result.boundary_type == "EXACT"
        assert result.previous_state == "STABLE"
        assert result.previous_period == date(2026, 1, 1)


class TestEvaluateStateDurationDataBounded:
    def test_historical_insufficient_data_produces_data_bounded_no_previous_state(self):
        """Frozen §45: a historical INSUFFICIENT_DATA encountered ->
        DATA_BOUNDED, no previous_state."""
        sequence = [
            _point(2026, 3, "COOLING"),
            _point(2026, 2, "COOLING"),
            _point(2026, 1, INSUFFICIENT_DATA_SENTINEL),
        ]
        result = evaluate_state_duration(sequence, LOOKBACK)
        assert result.duration_months == 2
        assert result.earliest_confirmed_period == date(2026, 2, 1)
        assert result.boundary_type == "DATA_BOUNDED"
        assert result.previous_state is None
        assert result.previous_period is None

    def test_insufficient_data_at_the_immediately_preceding_month(self):
        sequence = [_point(2026, 3, "COOLING"), _point(2026, 2, INSUFFICIENT_DATA_SENTINEL)]
        result = evaluate_state_duration(sequence, LOOKBACK)
        assert result.duration_months == 1
        assert result.boundary_type == "DATA_BOUNDED"

    def test_historical_insufficiency_is_never_skipped_past(self):
        """Frozen §16/§45: a regression test proving a real state match
        BEYOND a gap does not get bridged -- the walk stops at the gap,
        even though an identical state reappears further back."""
        sequence = [
            _point(2026, 5, "COOLING"),
            _point(2026, 4, "COOLING"),
            _point(2026, 3, INSUFFICIENT_DATA_SENTINEL),
            _point(2026, 2, "COOLING"),  # would extend the run if bridged -- must NOT be reached
            _point(2026, 1, "COOLING"),
        ]
        result = evaluate_state_duration(sequence, LOOKBACK)
        assert result.duration_months == 2
        assert result.earliest_confirmed_period == date(2026, 4, 1)
        assert result.boundary_type == "DATA_BOUNDED"
        assert result.previous_state is None
        assert result.previous_period is None


class TestEvaluateStateDurationLookbackBounded:
    def test_sequence_that_never_differs_and_never_hits_insufficiency_before_the_bound(self):
        """Frozen §12/§45: never differs, never hits insufficiency
        before the bound -> LOOKBACK_BOUNDED, duration_months equals
        the bound exactly."""
        sequence = _sequence_of_matching_months(LOOKBACK, "COOLING")
        result = evaluate_state_duration(sequence, LOOKBACK)
        assert result.duration_months == LOOKBACK
        assert result.boundary_type == "LOOKBACK_BOUNDED"
        assert result.previous_state is None
        assert result.previous_period is None
        # earliest_confirmed_period is the 60th point (index 59): 2026-01 minus 59 months
        assert result.earliest_confirmed_period == sequence[-1].period

    def test_a_differing_state_exactly_at_the_bound_is_never_examined(self):
        """A sequence longer than the bound, where the 61st point (one
        past the bound) differs, must still report LOOKBACK_BOUNDED --
        that point is never examined, per §12's own "the walk-back
        reaches the bound" definition."""
        sequence = _sequence_of_matching_months(LOOKBACK, "COOLING")
        sequence.append(_point(2020, 1, "STABLE"))  # far past the bound, deliberately differing
        result = evaluate_state_duration(sequence, LOOKBACK)
        assert result.duration_months == LOOKBACK
        assert result.boundary_type == "LOOKBACK_BOUNDED"


class TestEvaluateStateDurationOrderingAndDeterminism:
    def test_deterministic_identical_input_produces_identical_output(self):
        sequence = [_point(2026, 3, "COOLING"), _point(2026, 2, "STABLE")]
        first = evaluate_state_duration(sequence, LOOKBACK)
        second = evaluate_state_duration(sequence, LOOKBACK)
        assert first == second

    def test_single_point_sequence_is_lookback_bounded(self):
        """No prior data at all (a sequence of exactly one point, `t`
        itself) -- nothing to compare against, so the bound is reached
        immediately."""
        sequence = [_point(2026, 3, "COOLING")]
        result = evaluate_state_duration(sequence, LOOKBACK)
        assert result.duration_months == 1
        assert result.boundary_type == "LOOKBACK_BOUNDED"
        assert result.earliest_confirmed_period == date(2026, 3, 1)


class TestEvaluateStateDurationPreconditions:
    def test_empty_sequence_raises(self):
        with pytest.raises(ValueError):
            evaluate_state_duration([], LOOKBACK)

    def test_current_period_itself_insufficient_data_raises(self):
        """Frozen §14: callers must resolve CURRENT_INSUFFICIENT before
        ever calling this function -- sequence[0] being
        INSUFFICIENT_DATA is a caller bug, not a case this function
        silently tolerates."""
        sequence = [_point(2026, 3, INSUFFICIENT_DATA_SENTINEL)]
        with pytest.raises(ValueError):
            evaluate_state_duration(sequence, LOOKBACK)


class TestEvaluateStateDurationCallerOwnsCalendarStepping:
    def test_pure_helper_does_no_calendar_arithmetic_of_its_own(self):
        """Frozen §7/§45: exact-calendar stepping is the CALLER's job,
        not this pure helper's -- it operates over an already-built
        sequence and never inspects the gap between consecutive
        periods' own dates, only their `state` values. A sequence whose
        periods are NOT exact consecutive calendar months (a caller
        bug) is still evaluated purely by state-equality/sentinel
        checks -- proving this function performs no date arithmetic."""
        sequence = [
            _point(2026, 3, "COOLING"),
            _point(2025, 1, "COOLING"),  # a large, non-consecutive gap -- still just "matches", to this function
        ]
        result = evaluate_state_duration(sequence, LOOKBACK)
        assert result.duration_months == 2
        assert result.boundary_type == "LOOKBACK_BOUNDED"


class TestStateDurationDomainModuleHasNoEconomicKnowledge:
    def test_module_source_never_references_a_known_state_literal(self):
        """A structural proof, not merely an assertion: the module's own
        source text never mentions a real economic state literal
        (COOLING/HEATING/STRENGTHENING/etc.) -- it only knows the one
        domain-agnostic sentinel string."""
        import inspect

        import app.domain.state_duration as module

        source = inspect.getsource(module)
        forbidden_literals = ["COOLING", "HEATING", "STRENGTHENING", "MIXED", "STABLE", "IMPROVING", "DETERIORATING"]
        found = [literal for literal in forbidden_literals if literal in source]
        assert found == [], f"app/domain/state_duration.py references known economic state literal(s): {found}"
