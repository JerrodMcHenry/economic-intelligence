"""Pure, deterministic comparator for the Labor Market Monitor's "What
Changed?" contract (`labor_what_changed_v1.0`, frozen and normative in
`research/labor_momentum/LABOR_WHAT_CHANGED_V1_FROZEN_METHODOLOGY.md`).

CRITICAL architectural boundary: this module contains **zero**
`labor_v1.0` formula knowledge. It does not import `app.domain.labor`
(enforced by the architectural-independence test, extended for this
module -- the identical precedent `app.domain.inflation_what_changed`'s
own "never imports app.domain.inflation" guard already establishes),
does not know how PAYEMS/UNRATE are averaged, does not apply the
50,000-job or 0.2pp deadbands, and does not classify condition/
momentum/state itself. It only reads already-computed fields off two
already-canonical `EmploymentResult`/`UnemploymentResult`/`LaborState`
values (built elsewhere, by `app.domain.labor`'s own primitives, at
periods `app.domain.labor.month_over_month_labor_periods` chooses) and
does arithmetic/equality/membership checks on them. Like
`app.domain.inflation_what_changed`, this module has no knowledge of
FastAPI, HTTP, FRED, SQLAlchemy, database sessions, environment
variables, or logging, and never mutates global state.

None of the four functions below ever compares `previous_period`
against `current_period` -- they are used only to LABEL each produced
event's own `previous_period`/`current_period` fields. This is what
lets the exact same functions serve both month-over-month comparison
(`previous_period != current_period`) and a future release-processing
same-period revision comparison (`previous_period == current_period`)
with zero code change -- see LABOR_WHAT_CHANGED_V1_FROZEN_METHODOLOGY.md
§11.
"""

from datetime import date
from typing import Literal, TypeVar

from app.models.labor import EmploymentResult, LaborState, UnemploymentResult
from app.models.labor_what_changed import (
    COMPONENT_ORDER,
    EVENT_TYPE_ORDER,
    FIELD_ORDER,
    EmploymentSectionChanges,
    LaborChangeComponent,
    LaborChangeEvent,
    LaborWhatChangedResult,
    UnemploymentSectionChanges,
)

# The "valid economic value" sets for each state-shaped field --
# INSUFFICIENT_DATA is deliberately excluded from all three: it is an
# availability condition, never an economic direction (the frozen
# contract's own §4, restated here as the one place this rule is
# actually enforced).
_VALID_LABOR_STATES = frozenset({"STRENGTHENING", "COOLING", "STABLE", "MIXED"})
_VALID_EMPLOYMENT_STATES = frozenset({"EXPANDING", "COOLING", "STABLE", "CONTRACTING", "RECOVERING"})
_VALID_EMPLOYMENT_CONDITIONS = frozenset({"EXPANDING", "FLAT", "CONTRACTING"})
_VALID_EMPLOYMENT_MOMENTA = frozenset({"IMPROVING", "STEADY", "WORSENING"})
_VALID_UNEMPLOYMENT_STATES = frozenset({"IMPROVING", "DETERIORATING", "STABLE"})

_EMPLOYMENT_METRIC_FIELDS: tuple[str, ...] = ("current_3m_avg_jobs", "prior_3m_avg_jobs", "momentum_delta_jobs")
_UNEMPLOYMENT_METRIC_FIELDS: tuple[str, ...] = ("current_3m_avg", "prior_year_3m_avg", "delta_pp")

_T = TypeVar("_T", bound=str)


# ---------------------------------------------------------------------
# Low-level, per-field comparisons (no formula knowledge, pure diffing)
# ---------------------------------------------------------------------


def _state_events(
    component: LaborChangeComponent,
    field: str,
    valid_values: frozenset[str],
    previous_value: _T,
    current_value: _T,
    previous_period: date | None,
    current_period: date | None,
) -> list[LaborChangeEvent]:
    """One state-shaped field's comparison -- `STATE_CHANGED` only when
    BOTH sides are a valid economic value (never `INSUFFICIENT_DATA`)
    and unequal; `AVAILABILITY_LOST`/`RESTORED` when validity itself
    flips; nothing when both sides are `INSUFFICIENT_DATA` or both
    valid and equal. Transcribed from
    `app.domain.inflation_what_changed._state_events`, generalized
    over an explicit `valid_values` set instead of one hardcoded
    frozenset, so the same function serves `state`, `condition`, and
    `momentum` -- all five of Labor's state-shaped fields share this
    one rule (frozen contract §4)."""
    previous_valid = previous_value in valid_values
    current_valid = current_value in valid_values

    if previous_valid and current_valid:
        if previous_value != current_value:
            return [
                LaborChangeEvent(
                    component=component,
                    event_type="STATE_CHANGED",
                    field=field,
                    previous_value=previous_value,
                    current_value=current_value,
                    delta=None,
                    previous_period=previous_period,
                    current_period=current_period,
                )
            ]
        return []
    if previous_valid and not current_valid:
        return [
            LaborChangeEvent(
                component=component,
                event_type="AVAILABILITY_LOST",
                field=field,
                previous_value=previous_value,
                current_value=current_value,
                delta=None,
                previous_period=previous_period,
                current_period=current_period,
            )
        ]
    if not previous_valid and current_valid:
        return [
            LaborChangeEvent(
                component=component,
                event_type="AVAILABILITY_RESTORED",
                field=field,
                previous_value=previous_value,
                current_value=current_value,
                delta=None,
                previous_period=previous_period,
                current_period=current_period,
            )
        ]
    return []  # both INSUFFICIENT_DATA -- no economic transition


def _metric_events(
    component: LaborChangeComponent,
    field: str,
    previous_value: float | None,
    current_value: float | None,
    previous_period: date | None,
    current_period: date | None,
) -> list[LaborChangeEvent]:
    """One numeric metric field's comparison: `METRIC_CHANGED` if both
    sides are available and canonically (exactly) unequal -- no
    epsilon, no rounding, never a comparison of formatted display
    strings (frozen contract §7, citing
    docs/methodology/inflation-what-changed-v1.0.md's own frozen
    "Float/display rule" verbatim); `AVAILABILITY_LOST`/`RESTORED` if
    availability itself changed; nothing if both unavailable, or both
    available and equal. Transcribed from
    `app.domain.inflation_what_changed._metric_events`."""
    if previous_value is not None and current_value is not None:
        if previous_value != current_value:
            return [
                LaborChangeEvent(
                    component=component,
                    event_type="METRIC_CHANGED",
                    field=field,
                    previous_value=previous_value,
                    current_value=current_value,
                    delta=current_value - previous_value,
                    previous_period=previous_period,
                    current_period=current_period,
                )
            ]
        return []
    if previous_value is not None and current_value is None:
        return [
            LaborChangeEvent(
                component=component,
                event_type="AVAILABILITY_LOST",
                field=field,
                previous_value=previous_value,
                current_value=None,
                delta=None,
                previous_period=previous_period,
                current_period=current_period,
            )
        ]
    if previous_value is None and current_value is not None:
        return [
            LaborChangeEvent(
                component=component,
                event_type="AVAILABILITY_RESTORED",
                field=field,
                previous_value=None,
                current_value=current_value,
                delta=None,
                previous_period=previous_period,
                current_period=current_period,
            )
        ]
    return []  # both unavailable


def _sort_key(event: LaborChangeEvent) -> tuple[int, int, int]:
    """The frozen, total, deterministic ordering: component, then
    event type, then field -- never dict iteration, database row
    order, or judgment. An unlisted field (there are none today) sorts
    last rather than raising, so a future additive field never breaks
    ordering determinism -- the same discipline
    `app.domain.inflation_what_changed._sort_key` already applies."""
    component_index = COMPONENT_ORDER.index(event.component)
    event_type_index = EVENT_TYPE_ORDER.index(event.event_type)
    field_index = FIELD_ORDER.index(event.field) if event.field in FIELD_ORDER else len(FIELD_ORDER)
    return (component_index, event_type_index, field_index)


def _sort_events(events: list[LaborChangeEvent]) -> list[LaborChangeEvent]:
    return sorted(events, key=_sort_key)


# ---------------------------------------------------------------------
# Per-section comparators
# ---------------------------------------------------------------------


def compare_employment_section(
    previous_period: date | None,
    current_period: date | None,
    previous_evidence: EmploymentResult,
    current_evidence: EmploymentResult,
) -> EmploymentSectionChanges:
    """`state`, `condition`, and `momentum` are each compared
    INDEPENDENTLY (frozen contract §6) -- a `state` change never
    suppresses an accompanying `condition`/`momentum` event, and vice
    versa; this is deliberate, not an oversight (see that module's own
    docstring for why: `labor_v1.0`'s condition/momentum split exists
    specifically to preserve information a fused `state`-only signal
    would lose)."""
    events: list[LaborChangeEvent] = []
    events.extend(
        _state_events("EMPLOYMENT", "state", _VALID_EMPLOYMENT_STATES, previous_evidence.state, current_evidence.state, previous_period, current_period)
    )
    events.extend(
        _state_events(
            "EMPLOYMENT", "condition", _VALID_EMPLOYMENT_CONDITIONS, previous_evidence.condition, current_evidence.condition, previous_period, current_period
        )
    )
    events.extend(
        _state_events(
            "EMPLOYMENT", "momentum", _VALID_EMPLOYMENT_MOMENTA, previous_evidence.momentum, current_evidence.momentum, previous_period, current_period
        )
    )
    for field in _EMPLOYMENT_METRIC_FIELDS:
        events.extend(
            _metric_events(
                "EMPLOYMENT",
                field,
                getattr(previous_evidence, field),
                getattr(current_evidence, field),
                previous_period,
                current_period,
            )
        )
    events = _sort_events(events)

    return EmploymentSectionChanges(
        previous_evidence=previous_evidence,
        current_evidence=current_evidence,
        changes=events,
        # Deliberate, documented refinement of the frozen contract's own
        # compact schema sketch (§10): `state_changed` tracks SPECIFICALLY
        # whether the `state` field itself moved -- not "any of state/
        # condition/momentum changed." EMPLOYMENT is the one section with
        # THREE independently-reported state-shaped fields (unlike
        # Inflation's sections, which each have exactly one, so this
        # distinction never arose there); collapsing all three into one
        # ambiguous flag would silently reintroduce the "condition/momentum
        # change gets lost behind a state-shaped summary" problem this
        # whole increment exists to avoid (frozen contract §6's own
        # "never suppressed" principle, applied to the SUMMARY FLAG, not
        # just the events list). A consumer asking "did EMPLOYMENT's
        # headline state change?" gets an honest answer; a consumer
        # asking "did ANYTHING change?" already has `changes != []` --
        # see docs/ENGINEERING_JOURNAL.md's #20C.2 entry.
        state_changed=any(e.event_type == "STATE_CHANGED" and e.field == "state" for e in events),
        metric_changed=any(e.event_type == "METRIC_CHANGED" for e in events),
        availability_lost=any(e.event_type == "AVAILABILITY_LOST" for e in events),
        availability_restored=any(e.event_type == "AVAILABILITY_RESTORED" for e in events),
    )


def compare_unemployment_section(
    previous_period: date | None,
    current_period: date | None,
    previous_evidence: UnemploymentResult,
    current_evidence: UnemploymentResult,
) -> UnemploymentSectionChanges:
    events: list[LaborChangeEvent] = list(
        _state_events("UNEMPLOYMENT", "state", _VALID_UNEMPLOYMENT_STATES, previous_evidence.state, current_evidence.state, previous_period, current_period)
    )
    for field in _UNEMPLOYMENT_METRIC_FIELDS:
        events.extend(
            _metric_events(
                "UNEMPLOYMENT",
                field,
                getattr(previous_evidence, field),
                getattr(current_evidence, field),
                previous_period,
                current_period,
            )
        )
    events = _sort_events(events)

    return UnemploymentSectionChanges(
        previous_evidence=previous_evidence,
        current_evidence=current_evidence,
        changes=events,
        state_changed=any(e.event_type == "STATE_CHANGED" for e in events),
        metric_changed=any(e.event_type == "METRIC_CHANGED" for e in events),
        availability_lost=any(e.event_type == "AVAILABILITY_LOST" for e in events),
        availability_restored=any(e.event_type == "AVAILABILITY_RESTORED" for e in events),
    )


def compare_labor_state(
    previous_period: date | None,
    current_period: date | None,
    previous_state: LaborState,
    current_state: LaborState,
) -> list[LaborChangeEvent]:
    """The top-level `LABOR.state` comparison -- no dedicated section
    wrapper (unlike EMPLOYMENT/UNEMPLOYMENT) since there is no nested
    evidence beyond the bare state value itself at this layer (frozen
    contract §10). May independently coexist with an EMPLOYMENT or
    UNEMPLOYMENT `AVAILABILITY_LOST`/`RESTORED` event from the SAME
    underlying cause -- these are different semantic layers, not
    duplicates (frozen contract's own "availability transitions"
    reasoning)."""
    return _sort_events(
        _state_events("LABOR", "state", _VALID_LABOR_STATES, previous_state, current_state, previous_period, current_period)
    )


# ---------------------------------------------------------------------
# Top-level assembly
# ---------------------------------------------------------------------


def assemble_labor_what_changed_result(
    previous_period: date | None,
    current_period: date | None,
    previous_labor_state: LaborState,
    current_labor_state: LaborState,
    labor_state_changes: list[LaborChangeEvent],
    employment_changes: EmploymentSectionChanges,
    unemployment_changes: UnemploymentSectionChanges,
    current_labor_result=None,
) -> LaborWhatChangedResult:
    """Flattens all sections' events into one deterministically ordered
    list and computes the top-level summary flags -- itself zero
    formula knowledge, purely aggregation of already-computed section
    results. `comparison_available` is derived solely from whether
    `current_period` is not `None`."""
    all_events = _sort_events([*labor_state_changes, *employment_changes.changes, *unemployment_changes.changes])

    return LaborWhatChangedResult(
        comparison_available=current_period is not None,
        previous_period=previous_period,
        current_period=current_period,
        previous_labor_state=previous_labor_state,
        current_labor_state=current_labor_state,
        employment_changes=employment_changes,
        unemployment_changes=unemployment_changes,
        changes=all_events,
        any_state_changed=(
            bool(labor_state_changes) or employment_changes.state_changed or unemployment_changes.state_changed
        ),
        any_metric_changed=(employment_changes.metric_changed or unemployment_changes.metric_changed),
        any_availability_changed=(
            employment_changes.availability_lost
            or employment_changes.availability_restored
            or unemployment_changes.availability_lost
            or unemployment_changes.availability_restored
            or any(e.event_type in ("AVAILABILITY_LOST", "AVAILABILITY_RESTORED") for e in labor_state_changes)
        ),
        current_labor_result=current_labor_result,
    )
