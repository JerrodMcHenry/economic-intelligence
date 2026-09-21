"""Tests for the pure What Changed comparator
(app.domain.inflation_what_changed), contract `inflation_what_changed_v1.0`
-- frozen and normative in docs/methodology/inflation-what-changed-v1.0.md.
Pure, offline, deterministic: no database, no network, no OpenAI, and --
deliberately -- no call into app.domain.inflation's construction
primitives; every evidence object below is hand-constructed directly
from the Pydantic models, proving the comparator itself needs zero
economic formula knowledge to be fully exercised.
"""

from datetime import date

import pytest

from app.domain.inflation_what_changed import (
    assemble_what_changed_result,
    compare_confirmation_section,
    compare_series_momentum_section,
    compare_target_section,
)
from app.models.inflation import ConfirmationRelationship, InflationState, SeriesMomentumResult, TargetResult
from app.models.inflation_what_changed import ChangeEvent
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

JAN, FEB, MAR = date(2025, 1, 1), date(2025, 2, 1), date(2025, 3, 1)


def _momentum(
    period: date | None,
    state: InflationState,
    r1: float | None = None,
    r3: float | None = None,
    r6: float | None = None,
    r12: float | None = None,
) -> SeriesMomentumResult:
    """A hand-constructed SeriesMomentumResult -- never produced by
    calling classify_period/app.domain.inflation. `missing_required_metrics`
    is derived trivially for realism but is not itself read by the
    comparator."""
    missing = [name for name, value in (("r_3m", r3), ("r_6m", r6), ("r_12m", r12)) if value is None]
    return SeriesMomentumResult(
        concept_id=PRIMARY_IDENTITY.concept_id,
        series_id="PCEPILFE",
        calculation_period=period,
        latest_observation_period=period,
        latest_valid_state_period=period if state != "INSUFFICIENT_DATA" else None,
        r_1m_annualized=r1,
        r_3m_annualized=r3,
        r_6m_annualized=r6,
        r_12m=r12,
        neutral_band_pp=0.10,
        lower_boundary=(r12 - 0.10) if r12 is not None else None,
        upper_boundary=(r12 + 0.10) if r12 is not None else None,
        state=state,
        missing_required_metrics=missing,
        evidence_1m=None,
        evidence_3m=None,
        evidence_6m=None,
        evidence_12m=None,
    )


def _target(period: date | None, yoy: float | None, gap: float | None) -> TargetResult:
    return TargetResult(
        calculation_period=period,
        headline_pce_yoy=yoy,
        fed_objective_percent=2.0,
        target_gap_pp=gap,
        available=yoy is not None,
        evidence=None,
    )


# ---------------------------------------------------------------------
# 1-3: identical/changed available metric, unrounded-change-hidden-by-display
# ---------------------------------------------------------------------


class TestMetricComparison:
    def test_1_identical_available_metric_is_unchanged(self):
        previous = _momentum(JAN, "STABLE", r3=3.0, r6=3.0, r12=3.0)
        current = _momentum(FEB, "STABLE", r3=3.0, r6=3.0, r12=3.0)
        result = compare_series_momentum_section("PRIMARY_MOMENTUM", JAN, FEB, previous, current)
        assert result.metric_changed is False
        assert result.changes == []

    def test_2_changed_available_metric_produces_delta(self):
        previous = _momentum(JAN, "STABLE", r3=2.8, r6=3.0, r12=3.0)
        current = _momentum(FEB, "STABLE", r3=2.6, r6=3.0, r12=3.0)
        result = compare_series_momentum_section("PRIMARY_MOMENTUM", JAN, FEB, previous, current)
        assert result.metric_changed is True
        event = next(e for e in result.changes if e.field == "r_3m_annualized")
        assert event.event_type == "METRIC_CHANGED"
        assert event.previous_value == 2.8
        assert event.current_value == 2.6
        assert event.delta == pytest.approx(-0.2)
        # state itself is unchanged (both STABLE) -- no state_changed:
        assert result.state_changed is False

    def test_3_unrounded_change_hidden_by_display_rounding_still_changed(self):
        previous = _momentum(JAN, "STABLE", r3=2.849999, r6=3.0, r12=3.0)
        current = _momentum(FEB, "STABLE", r3=2.850001, r6=3.0, r12=3.0)
        result = compare_series_momentum_section("PRIMARY_MOMENTUM", JAN, FEB, previous, current)
        assert result.metric_changed is True
        event = next(e for e in result.changes if e.field == "r_3m_annualized")
        assert event.previous_value == 2.849999
        assert event.current_value == 2.850001
        # both round to the same 2-decimal display value -- canonical unrounded values still differ:
        assert round(event.previous_value, 2) == round(event.current_value, 2) == 2.85
        assert event.previous_value != event.current_value


# ---------------------------------------------------------------------
# 4-6: metric availability transitions
# ---------------------------------------------------------------------


class TestMetricAvailability:
    def test_4_available_to_unavailable_no_delta(self):
        previous = _momentum(JAN, "STABLE", r1=1.0, r3=2.8, r6=3.0, r12=3.0)
        current = _momentum(FEB, "INSUFFICIENT_DATA", r1=None, r3=None, r6=3.0, r12=3.0)
        result = compare_series_momentum_section("PRIMARY_MOMENTUM", JAN, FEB, previous, current)
        event = next(e for e in result.changes if e.field == "r_3m_annualized")
        assert event.event_type == "AVAILABILITY_LOST"
        assert event.delta is None
        assert event.current_value is None

    def test_5_unavailable_to_available_no_delta(self):
        previous = _momentum(JAN, "INSUFFICIENT_DATA", r3=None, r6=3.0, r12=3.0)
        current = _momentum(FEB, "STABLE", r3=2.9, r6=3.0, r12=3.0)
        result = compare_series_momentum_section("PRIMARY_MOMENTUM", JAN, FEB, previous, current)
        event = next(e for e in result.changes if e.field == "r_3m_annualized")
        assert event.event_type == "AVAILABILITY_RESTORED"
        assert event.delta is None
        assert event.previous_value is None

    def test_6_unavailable_to_unavailable_no_event(self):
        previous = _momentum(JAN, "INSUFFICIENT_DATA", r3=None, r6=None, r12=None)
        current = _momentum(FEB, "INSUFFICIENT_DATA", r3=None, r6=None, r12=None)
        result = compare_series_momentum_section("PRIMARY_MOMENTUM", JAN, FEB, previous, current)
        assert result.changes == []
        assert result.availability_lost is False
        assert result.availability_restored is False
        # a legitimate "compared, nothing different" outcome, still comparison_available:
        assert result.comparison_available is True


# ---------------------------------------------------------------------
# 7-11: state comparisons
# ---------------------------------------------------------------------


class TestStateComparison:
    def test_7_cooling_to_cooling_no_state_change(self):
        previous = _momentum(JAN, "COOLING", r3=2.0, r6=2.0, r12=3.0)
        current = _momentum(FEB, "COOLING", r3=1.9, r6=2.0, r12=3.0)
        result = compare_series_momentum_section("PRIMARY_MOMENTUM", JAN, FEB, previous, current)
        assert result.state_changed is False
        assert result.metric_changed is True  # r_3m did move

    def test_8_stable_to_cooling_state_changed(self):
        previous = _momentum(JAN, "STABLE", r3=3.0, r6=3.0, r12=3.0)
        current = _momentum(FEB, "COOLING", r3=2.0, r6=2.0, r12=3.0)
        result = compare_series_momentum_section("PRIMARY_MOMENTUM", JAN, FEB, previous, current)
        assert result.state_changed is True
        event = next(e for e in result.changes if e.event_type == "STATE_CHANGED")
        assert event.previous_value == "STABLE"
        assert event.current_value == "COOLING"
        assert event.delta is None

    def test_9_cooling_to_insufficient_data_availability_lost_no_state_transition(self):
        previous = _momentum(JAN, "COOLING", r3=2.0, r6=2.0, r12=3.0)
        current = _momentum(FEB, "INSUFFICIENT_DATA", r3=None, r6=None, r12=None)
        result = compare_series_momentum_section("PRIMARY_MOMENTUM", JAN, FEB, previous, current)
        assert result.availability_lost is True
        assert result.state_changed is False
        state_events = [e for e in result.changes if e.field == "state"]
        assert len(state_events) == 1
        assert state_events[0].event_type == "AVAILABILITY_LOST"

    def test_10_insufficient_data_to_cooling_availability_restored_no_state_transition(self):
        previous = _momentum(JAN, "INSUFFICIENT_DATA", r3=None, r6=None, r12=None)
        current = _momentum(FEB, "COOLING", r3=2.0, r6=2.0, r12=3.0)
        result = compare_series_momentum_section("PRIMARY_MOMENTUM", JAN, FEB, previous, current)
        assert result.availability_restored is True
        assert result.state_changed is False
        state_events = [e for e in result.changes if e.field == "state"]
        assert state_events[0].event_type == "AVAILABILITY_RESTORED"

    def test_11_mixed_to_heating_state_changed(self):
        previous = _momentum(JAN, "MIXED", r3=2.0, r6=4.0, r12=3.0)
        current = _momentum(FEB, "HEATING", r3=5.0, r6=5.0, r12=3.0)
        result = compare_series_momentum_section("PRIMARY_MOMENTUM", JAN, FEB, previous, current)
        assert result.state_changed is True
        event = next(e for e in result.changes if e.event_type == "STATE_CHANGED")
        assert event.previous_value == "MIXED"
        assert event.current_value == "HEATING"


# ---------------------------------------------------------------------
# 12-14: confirmation relationship comparisons
# ---------------------------------------------------------------------


class TestConfirmationComparison:
    def _confirm(self, previous_rel, current_rel):
        previous_primary = _momentum(JAN, "COOLING", r3=2.0, r6=2.0, r12=3.0)
        previous_confirmation = _momentum(JAN, "COOLING", r3=2.0, r6=2.0, r12=3.0)
        current_primary = _momentum(FEB, "COOLING", r3=2.0, r6=2.0, r12=3.0)
        current_confirmation = _momentum(FEB, "COOLING", r3=2.0, r6=2.0, r12=3.0)
        return compare_confirmation_section(
            JAN, FEB,
            previous_primary, previous_confirmation, previous_rel,
            current_primary, current_confirmation, current_rel,
        )

    def test_12_confirms_to_inconclusive_relationship_changed_availability_stays_true(self):
        result = self._confirm("CONFIRMS", "INCONCLUSIVE")
        assert result.relationship_changed is True
        assert result.confirmation_availability_lost is False
        assert result.confirmation_availability_restored is False
        event = next(e for e in result.changes if e.event_type == "CONFIRMATION_CHANGED")
        assert event.previous_value == "CONFIRMS"
        assert event.current_value == "INCONCLUSIVE"

    def test_13_confirms_to_unavailable_relationship_changed_and_availability_lost(self):
        result = self._confirm("CONFIRMS", "UNAVAILABLE")
        assert result.relationship_changed is True
        assert result.confirmation_availability_lost is True
        assert result.confirmation_availability_restored is False
        event_types = {e.event_type for e in result.changes}
        assert event_types == {"CONFIRMATION_CHANGED", "AVAILABILITY_LOST"}

    def test_14_unavailable_to_confirms_relationship_changed_and_availability_restored(self):
        result = self._confirm("UNAVAILABLE", "CONFIRMS")
        assert result.relationship_changed is True
        assert result.confirmation_availability_restored is True
        assert result.confirmation_availability_lost is False
        event_types = {e.event_type for e in result.changes}
        assert event_types == {"CONFIRMATION_CHANGED", "AVAILABILITY_RESTORED"}

    def test_confirmation_preserves_availability_invariant_both_sides(self):
        result = self._confirm("CONFIRMS", "UNAVAILABLE")
        assert (result.previous_relationship != "UNAVAILABLE") is True
        assert (result.current_relationship != "UNAVAILABLE") is False

    def test_unavailable_to_unavailable_no_events(self):
        result = self._confirm("UNAVAILABLE", "UNAVAILABLE")
        assert result.changes == []
        assert result.relationship_changed is False
        assert result.confirmation_availability_lost is False
        assert result.confirmation_availability_restored is False


# ---------------------------------------------------------------------
# 15-16: exact-calendar-period / no-row-position behavior
# (comparator-level: proves it just reports whatever periods it's
# given, never derives or substitutes them itself)
# ---------------------------------------------------------------------


class TestPeriodPassthrough:
    def test_15_exact_periods_are_reported_verbatim(self):
        previous = _momentum(JAN, "COOLING", r3=2.0, r6=2.0, r12=3.0)
        current = _momentum(FEB, "COOLING", r3=1.9, r6=2.0, r12=3.0)
        result = compare_series_momentum_section("PRIMARY_MOMENTUM", JAN, FEB, previous, current)
        assert result.previous_period == JAN
        assert result.current_period == FEB
        for event in result.changes:
            assert event.previous_period == JAN
            assert event.current_period == FEB

    def test_16_comparator_never_computes_or_substitutes_a_period(self):
        """The comparator has no month_before/calendar logic at all --
        passing in a non-adjacent pair (e.g. JAN and MAR, skipping FEB)
        is accepted verbatim; period SELECTION is entirely the caller's
        responsibility, never the comparator's."""
        previous = _momentum(JAN, "COOLING", r3=2.0, r6=2.0, r12=3.0)
        current = _momentum(MAR, "HEATING", r3=5.0, r6=5.0, r12=3.0)
        result = compare_series_momentum_section("PRIMARY_MOMENTUM", JAN, MAR, previous, current)
        assert result.previous_period == JAN
        assert result.current_period == MAR
        assert result.state_changed is True  # the comparator just diffs whatever it's given


# ---------------------------------------------------------------------
# 17: July/August/September-style missing-month protection
# ---------------------------------------------------------------------


class TestMissingMonthProtection:
    JUL, AUG, SEP = date(2025, 7, 1), date(2025, 8, 1), date(2025, 9, 1)

    def test_september_current_compares_only_against_august_never_july(self):
        august = _momentum(self.AUG, "INSUFFICIENT_DATA", r3=None, r6=None, r12=None)
        september = _momentum(self.SEP, "HEATING", r3=5.0, r6=5.0, r12=3.0)
        result = compare_series_momentum_section("PRIMARY_MOMENTUM", self.AUG, self.SEP, august, september)
        assert result.availability_restored is True
        assert result.state_changed is False
        # No COOLING->HEATING event exists anywhere -- July is never an input at all:
        assert all(e.previous_value != "COOLING" for e in result.changes)
        assert result.previous_period == self.AUG  # never JUL

    def test_august_current_compares_against_july_shows_availability_lost(self):
        july = _momentum(self.JUL, "COOLING", r3=2.0, r6=2.0, r12=3.0)
        august = _momentum(self.AUG, "INSUFFICIENT_DATA", r3=None, r6=None, r12=None)
        result = compare_series_momentum_section("PRIMARY_MOMENTUM", self.JUL, self.AUG, july, august)
        assert result.availability_lost is True
        assert result.state_changed is False
        assert all(e.current_value != "HEATING" for e in result.changes)  # September never appears


# ---------------------------------------------------------------------
# 18: multiple simultaneous changes
# ---------------------------------------------------------------------


class TestMultipleSimultaneousChanges:
    def test_18_all_five_sections_can_change_at_once(self):
        primary = compare_series_momentum_section(
            "PRIMARY_MOMENTUM", JAN, FEB,
            _momentum(JAN, "STABLE", r3=3.0, r6=3.0, r12=3.0),
            _momentum(FEB, "COOLING", r3=2.0, r6=2.0, r12=3.0),
        )
        confirmation = compare_confirmation_section(
            JAN, FEB,
            _momentum(JAN, "COOLING", r3=2.0, r6=2.0, r12=3.0),
            _momentum(JAN, "COOLING", r3=2.0, r6=2.0, r12=3.0),
            "CONFIRMS",
            _momentum(FEB, "COOLING", r3=2.0, r6=2.0, r12=3.0),
            _momentum(FEB, "STABLE", r3=3.0, r6=3.0, r12=3.0),
            "INCONCLUSIVE",
        )
        target = compare_target_section(JAN, FEB, _target(JAN, 3.1, 1.1), _target(FEB, 2.9, 0.9))
        headline_pce = compare_series_momentum_section(
            "HEADLINE_PCE", JAN, FEB,
            _momentum(JAN, "STABLE", r3=3.0, r6=3.0, r12=3.0),
            _momentum(FEB, "STABLE", r3=3.0, r6=3.0, r12=3.0),
        )
        headline_cpi = compare_series_momentum_section(
            "HEADLINE_CPI", JAN, FEB,
            _momentum(JAN, "HEATING", r3=5.0, r6=5.0, r12=3.0),
            _momentum(FEB, "HEATING", r3=5.5, r6=5.0, r12=3.0),
        )
        result = assemble_what_changed_result(primary, confirmation, target, headline_pce, headline_cpi)

        assert result.any_state_changed is True
        assert result.confirmation_changed is True
        assert result.any_metric_changed is True
        # every deterministic fact preserved -- not reduced to one winning event:
        components_present = {e.component for e in result.changes}
        assert components_present == {"PRIMARY_MOMENTUM", "CONFIRMATION", "TARGET", "HEADLINE_CPI"}
        assert len(result.changes) >= 4


# ---------------------------------------------------------------------
# 19: deterministic event ordering
# ---------------------------------------------------------------------


class TestDeterministicOrdering:
    def test_19_component_then_event_type_then_field_ordering(self):
        primary = compare_series_momentum_section(
            "PRIMARY_MOMENTUM", JAN, FEB,
            _momentum(JAN, "STABLE", r1=1.0, r3=3.0, r6=3.0, r12=3.0),
            _momentum(FEB, "COOLING", r1=0.5, r3=2.0, r6=2.0, r12=3.0),
        )
        confirmation = compare_confirmation_section(
            JAN, FEB,
            _momentum(JAN, "COOLING", r3=2.0, r6=2.0, r12=3.0),
            _momentum(JAN, "COOLING", r3=2.0, r6=2.0, r12=3.0),
            "CONFIRMS",
            _momentum(FEB, "COOLING", r3=2.0, r6=2.0, r12=3.0),
            _momentum(FEB, "HEATING", r3=5.0, r6=5.0, r12=3.0),
            "DIVERGES",
        )
        target = compare_target_section(JAN, FEB, _target(JAN, 3.1, 1.1), _target(FEB, 2.9, 0.9))
        headline_pce = compare_series_momentum_section(
            "HEADLINE_PCE", JAN, FEB, _momentum(JAN, "STABLE", r3=3.0, r6=3.0, r12=3.0), _momentum(FEB, "STABLE", r3=3.0, r6=3.0, r12=3.0)
        )
        headline_cpi = compare_series_momentum_section(
            "HEADLINE_CPI", JAN, FEB,
            _momentum(JAN, "HEATING", r1=1.0, r3=5.0, r6=5.0, r12=3.0),
            _momentum(FEB, "HEATING", r1=2.0, r3=5.5, r6=5.0, r12=3.0),
        )
        result = assemble_what_changed_result(primary, confirmation, target, headline_pce, headline_cpi)

        component_order = [e.component for e in result.changes]
        expected_component_priority = {"PRIMARY_MOMENTUM": 0, "CONFIRMATION": 1, "TARGET": 2, "HEADLINE_PCE": 3, "HEADLINE_CPI": 4}
        priorities = [expected_component_priority[c] for c in component_order]
        assert priorities == sorted(priorities)  # non-decreasing -- components never interleaved

        # Within PRIMARY_MOMENTUM: STATE_CHANGED must precede METRIC_CHANGED events:
        primary_events = [e for e in result.changes if e.component == "PRIMARY_MOMENTUM"]
        primary_event_types = [e.event_type for e in primary_events]
        assert primary_event_types.index("STATE_CHANGED") < primary_event_types.index("METRIC_CHANGED")

        # Within PRIMARY_MOMENTUM's METRIC_CHANGED events: r_1m before r_3m before r_6m:
        primary_metric_fields = [e.field for e in primary_events if e.event_type == "METRIC_CHANGED"]
        assert primary_metric_fields.index("r_1m_annualized") < primary_metric_fields.index("r_3m_annualized") < primary_metric_fields.index("r_6m_annualized")

    def test_ordering_is_stable_across_repeated_calls(self):
        primary = compare_series_momentum_section(
            "PRIMARY_MOMENTUM", JAN, FEB,
            _momentum(JAN, "STABLE", r1=1.0, r3=3.0, r6=3.0, r12=3.0),
            _momentum(FEB, "COOLING", r1=0.5, r3=2.0, r6=2.0, r12=3.0),
        )
        result_1 = primary.changes
        result_2 = compare_series_momentum_section(
            "PRIMARY_MOMENTUM", JAN, FEB,
            _momentum(JAN, "STABLE", r1=1.0, r3=3.0, r6=3.0, r12=3.0),
            _momentum(FEB, "COOLING", r1=0.5, r3=2.0, r6=2.0, r12=3.0),
        ).changes
        assert [e.field for e in result_1] == [e.field for e in result_2]


# ---------------------------------------------------------------------
# 20-21: repeated-call determinism / input nonmutation
# ---------------------------------------------------------------------


class TestDeterminismAndNonMutation:
    def test_20_repeated_calls_produce_identical_results(self):
        previous = _momentum(JAN, "STABLE", r3=3.0, r6=3.0, r12=3.0)
        current = _momentum(FEB, "COOLING", r3=2.0, r6=2.0, r12=3.0)
        result_1 = compare_series_momentum_section("PRIMARY_MOMENTUM", JAN, FEB, previous, current)
        result_2 = compare_series_momentum_section("PRIMARY_MOMENTUM", JAN, FEB, previous, current)
        assert result_1 == result_2

    def test_21_input_evidence_objects_not_mutated(self):
        previous = _momentum(JAN, "STABLE", r3=3.0, r6=3.0, r12=3.0)
        current = _momentum(FEB, "COOLING", r3=2.0, r6=2.0, r12=3.0)
        previous_snapshot = previous.model_copy(deep=True)
        current_snapshot = current.model_copy(deep=True)
        compare_series_momentum_section("PRIMARY_MOMENTUM", JAN, FEB, previous, current)
        assert previous == previous_snapshot
        assert current == current_snapshot


# ---------------------------------------------------------------------
# comparison_available semantics (no current anchor at all)
# ---------------------------------------------------------------------


class TestComparisonAvailable:
    def test_no_current_anchor_is_comparison_unavailable_not_no_change(self):
        result = compare_series_momentum_section("PRIMARY_MOMENTUM", None, None, None, None)
        assert result.comparison_available is False
        assert result.current_period is None
        assert result.previous_period is None
        assert result.changes == []
        assert result.metric_changed is False
        assert result.state_changed is False

    def test_no_change_with_comparison_available_is_distinguishable_from_unavailable(self):
        available_no_change = compare_series_momentum_section(
            "PRIMARY_MOMENTUM", JAN, FEB,
            _momentum(JAN, "STABLE", r3=3.0, r6=3.0, r12=3.0),
            _momentum(FEB, "STABLE", r3=3.0, r6=3.0, r12=3.0),
        )
        unavailable = compare_series_momentum_section("PRIMARY_MOMENTUM", None, None, None, None)
        assert available_no_change.changes == unavailable.changes == []
        assert available_no_change.comparison_available is True
        assert unavailable.comparison_available is False

    def test_target_no_current_anchor(self):
        result = compare_target_section(None, None, None, None)
        assert result.comparison_available is False
        assert result.changes == []

    def test_confirmation_no_current_anchor(self):
        result = compare_confirmation_section(None, None, None, None, None, None, None, None)
        assert result.comparison_available is False
        assert result.changes == []
        assert result.previous_relationship is None
        assert result.current_relationship is None


# ---------------------------------------------------------------------
# Target section specifics
# ---------------------------------------------------------------------


class TestTargetSection:
    def test_target_gap_change_never_paired_with_momentum_event(self):
        result = compare_target_section(JAN, FEB, _target(JAN, 3.2, 1.2), _target(FEB, 2.9, 0.9))
        assert result.metric_changed is True
        fields = {e.field for e in result.changes}
        assert fields == {"headline_pce_yoy", "target_gap_pp"}
        # target section never emits a "state" field -- no categorical target state exists:
        assert "state" not in fields

    def test_target_available_to_unavailable(self):
        result = compare_target_section(JAN, FEB, _target(JAN, 3.2, 1.2), _target(FEB, None, None))
        assert result.availability_lost is True
        assert result.metric_changed is False


# ---------------------------------------------------------------------
# No-change result semantics
# ---------------------------------------------------------------------


class TestNoChangeResult:
    def test_fully_identical_comparison_yields_empty_changes_and_false_flags(self):
        previous = _momentum(JAN, "STABLE", r1=1.0, r3=3.0, r6=3.0, r12=3.0)
        current = _momentum(FEB, "STABLE", r1=1.0, r3=3.0, r6=3.0, r12=3.0)
        primary = compare_series_momentum_section("PRIMARY_MOMENTUM", JAN, FEB, previous, current)
        confirmation = compare_confirmation_section(
            JAN, FEB, previous, previous, "CONFIRMS", current, current, "CONFIRMS"
        )
        target = compare_target_section(JAN, FEB, _target(JAN, 2.0, 0.0), _target(FEB, 2.0, 0.0))
        headline_pce = compare_series_momentum_section("HEADLINE_PCE", JAN, FEB, previous, current)
        headline_cpi = compare_series_momentum_section("HEADLINE_CPI", JAN, FEB, previous, current)

        result = assemble_what_changed_result(primary, confirmation, target, headline_pce, headline_cpi)
        assert result.changes == []
        assert result.any_metric_changed is False
        assert result.any_state_changed is False
        assert result.any_availability_changed is False
        assert result.confirmation_changed is False
