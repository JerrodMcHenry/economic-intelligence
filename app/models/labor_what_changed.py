"""Typed, application-owned canonical result models for the Labor
Market Monitor's "What Changed?" comparison layer, contract
`labor_what_changed_v1.0` (frozen and normative in
`research/labor_momentum/LABOR_WHAT_CHANGED_V1_FROZEN_METHODOLOGY.md`).

Plain Pydantic data, like `app.models.inflation_what_changed` -- no
FastAPI or SQLAlchemy dependency. This is a comparison layer over
already-canonical `labor_v1.0` results, not a second methodology:
`EmploymentResult`/`UnemploymentResult` (both `app.models.labor`'s own,
unmodified shapes) are reused verbatim as embedded evidence. No new
economic type is introduced in this module.

Deliberately NOT a blind copy of `app.models.inflation_what_changed`'s
own field set -- see the frozen contract's own §2 "Inflation reuse
audit" for exactly what transfers and what doesn't:
- No `CONFIRMATION_CHANGED` event type and no `ConfirmationSectionChanges`-
  shaped model -- Labor V1 has no confirmation component (JOLTS deferred).
- No per-section `previous_period`/`current_period`/`comparison_available`
  triplet -- Labor has exactly ONE shared `evaluation_period` for both
  owners, so these fields are hoisted to the top-level result once
  instead of repeated per-section (Inflation needs the per-section
  triplet because its sections anchor to genuinely different periods).
- Two field values with no Inflation analog: `"condition"` and
  `"momentum"` on the `EMPLOYMENT` component, reusing the same
  `STATE_CHANGED`/`AVAILABILITY_LOST`/`AVAILABILITY_RESTORED`
  vocabulary as `"state"` (see the frozen contract's §6/§8).
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel

from app.models.labor import DATA_BASIS, EmploymentResult, LaborMonitorResult, LaborState, METHODOLOGY_ID, UnemploymentResult

COMPARISON_CONTRACT_ID = "labor_what_changed_v1.0"
COMPARISON_TYPE = "MONTH_OVER_MONTH"

LaborChangeComponent = Literal["LABOR", "EMPLOYMENT", "UNEMPLOYMENT"]
LaborChangeEventType = Literal["STATE_CHANGED", "AVAILABILITY_LOST", "AVAILABILITY_RESTORED", "METRIC_CHANGED"]

# The frozen contract's deterministic ordering keys -- never derived
# from dict iteration, database row order, or judgment. Exposed here
# (not buried in the comparator) so both the comparator and any test
# asserting on ordering share exactly one source of truth -- the same
# discipline `app.models.inflation_what_changed`'s own
# COMPONENT_ORDER/EVENT_TYPE_ORDER/FIELD_ORDER constants establish.
COMPONENT_ORDER: tuple[LaborChangeComponent, ...] = ("LABOR", "EMPLOYMENT", "UNEMPLOYMENT")
EVENT_TYPE_ORDER: tuple[LaborChangeEventType, ...] = (
    "STATE_CHANGED",
    "AVAILABILITY_LOST",
    "AVAILABILITY_RESTORED",
    "METRIC_CHANGED",
)
FIELD_ORDER: tuple[str, ...] = (
    "state",
    "condition",
    "momentum",
    "current_3m_avg_jobs",
    "prior_3m_avg_jobs",
    "momentum_delta_jobs",
    "current_3m_avg",
    "prior_year_3m_avg",
    "delta_pp",
)


class LaborChangeEvent(BaseModel):
    """One deterministic, structural fact -- never an interpretation.
    Independently auditable: `previous_value`/`current_value` plus
    `previous_period`/`current_period` are sufficient to reproduce this
    event by hand from the section's own embedded evidence.
    `methodology_id` is the SOURCE monitor's id (`labor_v1.0`) -- never
    the comparator's own id, which lives once at the top-level result
    (`LaborWhatChangedResult.comparison_contract_id`)."""

    component: LaborChangeComponent
    event_type: LaborChangeEventType
    field: str
    previous_value: float | str | None
    current_value: float | str | None
    delta: float | None  # current_value - previous_value when both are numeric and available; None otherwise
    previous_period: date | None
    current_period: date | None
    methodology_id: str = METHODOLOGY_ID
    data_basis: str = DATA_BASIS


class EmploymentSectionChanges(BaseModel):
    """PAYEMS-owned change evidence -- independently auditable from its
    own embedded `EmploymentResult` evidence (`labor_v1.0`'s own,
    unmodified model). `state`, `condition`, and `momentum` are each
    compared independently (see the frozen contract's §6) -- a
    `state` change never suppresses an accompanying `condition`/
    `momentum` event, and vice versa."""

    previous_evidence: EmploymentResult
    current_evidence: EmploymentResult
    changes: list[LaborChangeEvent]
    state_changed: bool
    metric_changed: bool
    availability_lost: bool
    availability_restored: bool


class UnemploymentSectionChanges(BaseModel):
    """UNRATE-owned change evidence -- independently auditable from its
    own embedded `UnemploymentResult` evidence. `previous_evidence`/
    `current_evidence` are never `None` -- even in the fully-degenerate
    "no candidate period at all" case, they hold a real, `state:
    "INSUFFICIENT_DATA"`-shaped `EmploymentResult`/`UnemploymentResult`
    with empty `observations`, mirroring `labor_v1.0`'s own established
    convention (`LaborMonitorResult.employment`/`.unemployment` are
    likewise never `None`) rather than introducing a second way to
    represent "nothing here." A deliberate, minor simplification of
    the frozen contract's own compact schema sketch (which allowed
    `| None`) -- see docs/ENGINEERING_JOURNAL.md's #20C.2 entry."""

    previous_evidence: UnemploymentResult
    current_evidence: UnemploymentResult
    changes: list[LaborChangeEvent]
    state_changed: bool
    metric_changed: bool
    availability_lost: bool
    availability_restored: bool


class LaborWhatChangedResult(BaseModel):
    """The complete canonical, typed Labor What Changed result.

    `comparison_available` is `False` only when `current_period` could
    not be determined at all (neither PAYEMS nor UNRATE has any
    persisted observation) -- in that case `previous_period`/
    `current_period` are `None`, `previous_labor_state`/
    `current_labor_state` are both the real value `"INSUFFICIENT_DATA"`
    (never Python `None` -- `LaborState` already has a member for
    exactly this), and `employment_changes`/`unemployment_changes`
    embed `INSUFFICIENT_DATA`-shaped evidence with empty observations,
    mirroring `compute_labor_monitor_result`'s own degenerate-case
    shape.

    No per-section `comparison_available`/period fields (unlike
    Inflation's own section models) -- Labor's ONE shared
    `evaluation_period` makes these top-level-only fields sufficient;
    see this module's own docstring for the full reasoning.
    """

    methodology_id: str = METHODOLOGY_ID
    comparison_contract_id: str = COMPARISON_CONTRACT_ID
    comparison_type: str = COMPARISON_TYPE
    data_basis: str = DATA_BASIS

    comparison_available: bool
    previous_period: date | None
    current_period: date | None
    previous_labor_state: LaborState
    current_labor_state: LaborState

    employment_changes: EmploymentSectionChanges
    unemployment_changes: UnemploymentSectionChanges

    changes: list[LaborChangeEvent]

    any_state_changed: bool
    any_metric_changed: bool
    any_availability_changed: bool

    current_labor_result: LaborMonitorResult | None = None
