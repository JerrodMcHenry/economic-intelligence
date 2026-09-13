"""Pure, deterministic comparator for the Inflation Monitor's "What
Changed?" contract (`inflation_what_changed_v1.0`, frozen and normative
in `docs/methodology/inflation-what-changed-v1.0.md`).

CRITICAL architectural boundary: this module contains **zero**
inflation formula knowledge. It does not import `app.domain.inflation`
(enforced by the architectural-independence test, extended for this
module), does not know how CPI/PCE annualization works, and does not
construct a `SeriesMomentumResult`/`TargetResult` itself. It only reads
already-computed fields off two already-canonical evidence objects
(built elsewhere, by `app.domain.inflation`'s own primitives, at
periods this contract's own period-selection logic chooses) and does
arithmetic/equality/membership checks on them. Like
`app/domain/transformations.py`/`app/domain/analysis.py`/
`app/domain/inflation.py`, this module has no knowledge of FastAPI,
HTTP, FRED, SQLAlchemy, database sessions, environment variables, or
logging, and never mutates global state.
"""

from datetime import date

from app.models.inflation import (
    ConfirmationRelationship,
    InflationMonitorResult,
    InflationState,
    SeriesMomentumResult,
    TargetResult,
)
from app.models.inflation_what_changed import (
    COMPONENT_ORDER,
    EVENT_TYPE_ORDER,
    FIELD_ORDER,
    ChangeComponent,
    ChangeEvent,
    ConfirmationSectionChanges,
    InflationWhatChangedResult,
    SeriesMomentumSectionChanges,
    TargetSectionChanges,
)

_DIRECTIONAL_STATES: frozenset[InflationState] = frozenset({"COOLING", "HEATING", "STABLE", "MIXED"})
_MOMENTUM_METRIC_FIELDS: tuple[str, ...] = ("r_1m_annualized", "r_3m_annualized", "r_6m_annualized", "r_12m")
_TARGET_METRIC_FIELDS: tuple[str, ...] = ("headline_pce_yoy", "target_gap_pp")


# ---------------------------------------------------------------------
# Low-level, per-field comparisons (no formula knowledge, pure diffing)
# ---------------------------------------------------------------------


def _metric_events(
    component: ChangeComponent,
    field: str,
    previous_value: float | None,
    current_value: float | None,
    previous_period: date | None,
    current_period: date | None,
) -> list[ChangeEvent]:
    """One metric field's comparison: `METRIC_CHANGED` if both sides
    are available and canonically unequal (full unrounded precision --
    no epsilon, no rounding first); `AVAILABILITY_LOST`/`RESTORED` if
    availability itself changed; nothing if both unavailable, or both
    available and equal."""
    if previous_value is not None and current_value is not None:
        if previous_value != current_value:
            return [
                ChangeEvent(
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
            ChangeEvent(
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
            ChangeEvent(
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
    return []  # both unavailable -- no_availability_change, nothing to report


def _state_events(
    component: ChangeComponent,
    previous_state: InflationState,
    current_state: InflationState,
    previous_period: date | None,
    current_period: date | None,
) -> list[ChangeEvent]:
    """Canonical momentum state comparison. `INSUFFICIENT_DATA` is an
    availability state, never an economic direction -- a state change
    requires BOTH sides to be one of COOLING/HEATING/STABLE/MIXED and
    unequal."""
    previous_valid = previous_state in _DIRECTIONAL_STATES
    current_valid = current_state in _DIRECTIONAL_STATES
    if previous_valid and current_valid:
        if previous_state != current_state:
            return [
                ChangeEvent(
                    component=component,
                    event_type="STATE_CHANGED",
                    field="state",
                    previous_value=previous_state,
                    current_value=current_state,
                    delta=None,
                    previous_period=previous_period,
                    current_period=current_period,
                )
            ]
        return []
    if previous_valid and not current_valid:
        return [
            ChangeEvent(
                component=component,
                event_type="AVAILABILITY_LOST",
                field="state",
                previous_value=previous_state,
                current_value=current_state,
                delta=None,
                previous_period=previous_period,
                current_period=current_period,
            )
        ]
    if not previous_valid and current_valid:
        return [
            ChangeEvent(
                component=component,
                event_type="AVAILABILITY_RESTORED",
                field="state",
                previous_value=previous_state,
                current_value=current_state,
                delta=None,
                previous_period=previous_period,
                current_period=current_period,
            )
        ]
    return []  # both INSUFFICIENT_DATA -- no economic state transition


def _relationship_events(
    previous_relationship: ConfirmationRelationship,
    current_relationship: ConfirmationRelationship,
    previous_period: date | None,
    current_period: date | None,
) -> list[ChangeEvent]:
    """Confirmation relationship comparison. A relationship change and
    an availability change are independent and may coexist --
    `CONFIRMS -> UNAVAILABLE` yields both `CONFIRMATION_CHANGED` and
    `AVAILABILITY_LOST`; `UNAVAILABLE -> CONFIRMS` yields both
    `CONFIRMATION_CHANGED` and `AVAILABILITY_RESTORED`. The frozen #14
    invariant (`confirmation_available == relationship != UNAVAILABLE`)
    is applied here as a pure read of each already-canonical
    relationship value -- never recomputed."""
    events: list[ChangeEvent] = []
    if previous_relationship != current_relationship:
        events.append(
            ChangeEvent(
                component="CONFIRMATION",
                event_type="CONFIRMATION_CHANGED",
                field="relationship",
                previous_value=previous_relationship,
                current_value=current_relationship,
                delta=None,
                previous_period=previous_period,
                current_period=current_period,
            )
        )
    previous_available = previous_relationship != "UNAVAILABLE"
    current_available = current_relationship != "UNAVAILABLE"
    if previous_available and not current_available:
        events.append(
            ChangeEvent(
                component="CONFIRMATION",
                event_type="AVAILABILITY_LOST",
                field="relationship",
                previous_value=previous_relationship,
                current_value=current_relationship,
                delta=None,
                previous_period=previous_period,
                current_period=current_period,
            )
        )
    elif not previous_available and current_available:
        events.append(
            ChangeEvent(
                component="CONFIRMATION",
                event_type="AVAILABILITY_RESTORED",
                field="relationship",
                previous_value=previous_relationship,
                current_value=current_relationship,
                delta=None,
                previous_period=previous_period,
                current_period=current_period,
            )
        )
    return events


def _sort_key(event: ChangeEvent) -> tuple[int, int, int]:
    """The frozen, total, deterministic ordering: component, then event
    type, then field -- never dict iteration, database row order, or
    judgment. An unlisted field (there are none today) sorts last
    rather than raising, so a future additive field never breaks
    ordering determinism."""
    component_index = COMPONENT_ORDER.index(event.component)
    event_type_index = EVENT_TYPE_ORDER.index(event.event_type)
    field_index = FIELD_ORDER.index(event.field) if event.field in FIELD_ORDER else len(FIELD_ORDER)
    return (component_index, event_type_index, field_index)


def _sort_events(events: list[ChangeEvent]) -> list[ChangeEvent]:
    return sorted(events, key=_sort_key)


# ---------------------------------------------------------------------
# Per-section comparators
# ---------------------------------------------------------------------


def compare_series_momentum_section(
    component: ChangeComponent,
    previous_period: date | None,
    current_period: date | None,
    previous_evidence: SeriesMomentumResult | None,
    current_evidence: SeriesMomentumResult | None,
) -> SeriesMomentumSectionChanges:
    """Shared comparator for primary momentum, headline PCE, and
    headline CPI -- all three share this shape. `comparison_available`
    is derived solely from whether `current_period` is not `None` (per
    the frozen contract) -- never from whether the evidence itself
    classified successfully. Whenever `current_period` exists,
    `previous_period`/`previous_evidence`/`current_evidence` are always
    provided by the caller (a current anchor always makes "one calendar
    month before" computable, and evaluating that period, whatever the
    outcome, is exactly what this contract requires)."""
    comparison_available = current_period is not None
    if not comparison_available:
        return SeriesMomentumSectionChanges(
            comparison_available=False,
            previous_period=None,
            current_period=None,
            previous_evidence=None,
            current_evidence=None,
            changes=[],
            metric_changed=False,
            state_changed=False,
            availability_lost=False,
            availability_restored=False,
        )

    assert previous_evidence is not None and current_evidence is not None  # guaranteed whenever current_period exists

    events: list[ChangeEvent] = list(
        _state_events(component, previous_evidence.state, current_evidence.state, previous_period, current_period)
    )
    for field in _MOMENTUM_METRIC_FIELDS:
        events.extend(
            _metric_events(
                component,
                field,
                getattr(previous_evidence, field),
                getattr(current_evidence, field),
                previous_period,
                current_period,
            )
        )
    events = _sort_events(events)

    return SeriesMomentumSectionChanges(
        comparison_available=True,
        previous_period=previous_period,
        current_period=current_period,
        previous_evidence=previous_evidence,
        current_evidence=current_evidence,
        changes=events,
        metric_changed=any(e.event_type == "METRIC_CHANGED" for e in events),
        state_changed=any(e.event_type == "STATE_CHANGED" for e in events),
        availability_lost=any(e.event_type == "AVAILABILITY_LOST" for e in events),
        availability_restored=any(e.event_type == "AVAILABILITY_RESTORED" for e in events),
    )


def compare_target_section(
    previous_period: date | None,
    current_period: date | None,
    previous_evidence: TargetResult | None,
    current_evidence: TargetResult | None,
) -> TargetSectionChanges:
    """Target's own metrics (`headline_pce_yoy`, `target_gap_pp`) --
    never paired with a momentum interpretation; level and momentum
    stay independent facts here exactly as `inflation_v1.0` keeps them
    independent."""
    comparison_available = current_period is not None
    if not comparison_available:
        return TargetSectionChanges(
            comparison_available=False,
            previous_period=None,
            current_period=None,
            previous_evidence=None,
            current_evidence=None,
            changes=[],
            metric_changed=False,
            availability_lost=False,
            availability_restored=False,
        )

    assert previous_evidence is not None and current_evidence is not None

    events: list[ChangeEvent] = []
    for field in _TARGET_METRIC_FIELDS:
        events.extend(
            _metric_events(
                "TARGET",
                field,
                getattr(previous_evidence, field),
                getattr(current_evidence, field),
                previous_period,
                current_period,
            )
        )
    events = _sort_events(events)

    return TargetSectionChanges(
        comparison_available=True,
        previous_period=previous_period,
        current_period=current_period,
        previous_evidence=previous_evidence,
        current_evidence=current_evidence,
        changes=events,
        metric_changed=any(e.event_type == "METRIC_CHANGED" for e in events),
        availability_lost=any(e.event_type == "AVAILABILITY_LOST" for e in events),
        availability_restored=any(e.event_type == "AVAILABILITY_RESTORED" for e in events),
    )


def compare_confirmation_section(
    previous_confirmation_period: date | None,
    current_confirmation_period: date | None,
    previous_primary_state: SeriesMomentumResult | None,
    previous_confirmation_state: SeriesMomentumResult | None,
    previous_relationship: ConfirmationRelationship | None,
    current_primary_state: SeriesMomentumResult | None,
    current_confirmation_state: SeriesMomentumResult | None,
    current_relationship: ConfirmationRelationship | None,
) -> ConfirmationSectionChanges:
    """Confirmation's own events are driven by the RELATIONSHIP
    comparison only (never by separately diffing the underlying Core
    PCE/Core CPI states as if they were this component's own
    metric/state events -- those states are embedded here purely as
    audit evidence for the relationship, anchored at confirmation's own
    `latest_shared_observation_period`, which is generally a different
    period from primary momentum's own anchor)."""
    comparison_available = current_confirmation_period is not None
    if not comparison_available:
        return ConfirmationSectionChanges(
            comparison_available=False,
            previous_confirmation_period=None,
            current_confirmation_period=None,
            previous_primary_state=None,
            previous_confirmation_state=None,
            previous_relationship=None,
            current_primary_state=None,
            current_confirmation_state=None,
            current_relationship=None,
            changes=[],
            relationship_changed=False,
            confirmation_availability_lost=False,
            confirmation_availability_restored=False,
        )

    assert previous_relationship is not None and current_relationship is not None

    events = _relationship_events(
        previous_relationship, current_relationship, previous_confirmation_period, current_confirmation_period
    )
    events = _sort_events(events)

    return ConfirmationSectionChanges(
        comparison_available=True,
        previous_confirmation_period=previous_confirmation_period,
        current_confirmation_period=current_confirmation_period,
        previous_primary_state=previous_primary_state,
        previous_confirmation_state=previous_confirmation_state,
        previous_relationship=previous_relationship,
        current_primary_state=current_primary_state,
        current_confirmation_state=current_confirmation_state,
        current_relationship=current_relationship,
        changes=events,
        relationship_changed=any(e.event_type == "CONFIRMATION_CHANGED" for e in events),
        confirmation_availability_lost=any(e.event_type == "AVAILABILITY_LOST" for e in events),
        confirmation_availability_restored=any(e.event_type == "AVAILABILITY_RESTORED" for e in events),
    )


# ---------------------------------------------------------------------
# Top-level assembly
# ---------------------------------------------------------------------


def assemble_what_changed_result(
    primary_momentum_changes: SeriesMomentumSectionChanges,
    confirmation_changes: ConfirmationSectionChanges,
    target_changes: TargetSectionChanges,
    headline_pce_changes: SeriesMomentumSectionChanges,
    headline_cpi_changes: SeriesMomentumSectionChanges,
    current_monitor_result: InflationMonitorResult | None = None,
) -> InflationWhatChangedResult:
    """Flattens all five sections' events into one deterministically
    ordered list and computes the top-level summary flags -- itself
    zero formula knowledge, purely aggregation of already-computed
    section results."""
    all_events = _sort_events(
        [
            *primary_momentum_changes.changes,
            *confirmation_changes.changes,
            *target_changes.changes,
            *headline_pce_changes.changes,
            *headline_cpi_changes.changes,
        ]
    )

    return InflationWhatChangedResult(
        primary_momentum_changes=primary_momentum_changes,
        confirmation_changes=confirmation_changes,
        target_changes=target_changes,
        headline_pce_changes=headline_pce_changes,
        headline_cpi_changes=headline_cpi_changes,
        changes=all_events,
        any_metric_changed=(
            primary_momentum_changes.metric_changed
            or target_changes.metric_changed
            or headline_pce_changes.metric_changed
            or headline_cpi_changes.metric_changed
        ),
        any_state_changed=(
            primary_momentum_changes.state_changed
            or headline_pce_changes.state_changed
            or headline_cpi_changes.state_changed
        ),
        any_availability_changed=(
            primary_momentum_changes.availability_lost
            or primary_momentum_changes.availability_restored
            or target_changes.availability_lost
            or target_changes.availability_restored
            or headline_pce_changes.availability_lost
            or headline_pce_changes.availability_restored
            or headline_cpi_changes.availability_lost
            or headline_cpi_changes.availability_restored
            or confirmation_changes.confirmation_availability_lost
            or confirmation_changes.confirmation_availability_restored
        ),
        confirmation_changed=confirmation_changes.relationship_changed,
        current_monitor_result=current_monitor_result,
    )
