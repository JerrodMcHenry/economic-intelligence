"""Typed, application-owned canonical result models for the Inflation
Monitor's "What Changed?" comparison layer, contract
`inflation_what_changed_v1.0` (frozen and normative in
`docs/methodology/inflation-what-changed-v1.0.md`).

Plain Pydantic data, like `app.models.inflation` -- no FastAPI or
SQLAlchemy dependency. This is a comparison layer over already-canonical
`inflation_v1.0` results, not a second methodology: every economic value
embedded here (`SeriesMomentumResult`, `TargetResult`,
`ConfirmationRelationship`) is `app.models.inflation`'s own, unmodified
shape, reused verbatim as canonical evidence at an explicit period. No
new economic type is introduced in this module.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel

from app.models.inflation import (
    DATA_BASIS,
    METHODOLOGY_ID,
    ConfirmationRelationship,
    InflationMonitorResult,
    SeriesMomentumResult,
    TargetResult,
)

COMPARISON_CONTRACT_ID = "inflation_what_changed_v1.0"
COMPARISON_TYPE = "MONTH_OVER_MONTH"

ChangeComponent = Literal["PRIMARY_MOMENTUM", "CONFIRMATION", "TARGET", "HEADLINE_PCE", "HEADLINE_CPI"]
ChangeEventType = Literal["METRIC_CHANGED", "STATE_CHANGED", "AVAILABILITY_LOST", "AVAILABILITY_RESTORED", "CONFIRMATION_CHANGED"]

# The frozen contract's deterministic ordering keys -- never derived
# from dict iteration, database row order, or judgment. Exposed here
# (not buried in the comparator) so both the comparator and any test
# asserting on ordering share exactly one source of truth.
COMPONENT_ORDER: tuple[ChangeComponent, ...] = ("PRIMARY_MOMENTUM", "CONFIRMATION", "TARGET", "HEADLINE_PCE", "HEADLINE_CPI")
EVENT_TYPE_ORDER: tuple[ChangeEventType, ...] = (
    "STATE_CHANGED",
    "CONFIRMATION_CHANGED",
    "AVAILABILITY_LOST",
    "AVAILABILITY_RESTORED",
    "METRIC_CHANGED",
)
# Extends the frozen spec's METRIC_CHANGED field order (r_1m_annualized
# .. target_gap_pp) with "state"/"relationship" first, so a state-level
# or relationship-level AVAILABILITY_LOST/RESTORED/STATE_CHANGED/
# CONFIRMATION_CHANGED event always sorts before that same component's
# metric-level events -- a deterministic, documented extension of the
# frozen ordering rule to event types the frozen text left unspecified.
FIELD_ORDER: tuple[str, ...] = (
    "state",
    "relationship",
    "r_1m_annualized",
    "r_3m_annualized",
    "r_6m_annualized",
    "r_12m",
    "headline_pce_yoy",
    "target_gap_pp",
)


class ChangeEvent(BaseModel):
    """One deterministic, structural fact -- never an interpretation.
    Independently auditable: `previous_value`/`current_value` plus
    `previous_period`/`current_period` are sufficient to reproduce this
    event by hand from the section's own embedded evidence."""

    component: ChangeComponent
    event_type: ChangeEventType
    field: str
    previous_value: float | str | None
    current_value: float | str | None
    delta: float | None  # current_value - previous_value when both are numeric and available; None otherwise
    previous_period: date | None
    current_period: date | None
    methodology_id: str = METHODOLOGY_ID
    data_basis: str = DATA_BASIS


class SeriesMomentumSectionChanges(BaseModel):
    """Shape shared by primary momentum, headline PCE, and headline CPI
    -- each independently periodized and independently auditable from
    its own embedded `SeriesMomentumResult` evidence (`inflation_v1.0`'s
    own, unmodified model)."""

    comparison_available: bool
    previous_period: date | None
    current_period: date | None
    previous_evidence: SeriesMomentumResult | None
    current_evidence: SeriesMomentumResult | None
    changes: list[ChangeEvent]
    metric_changed: bool
    state_changed: bool
    availability_lost: bool
    availability_restored: bool


class TargetSectionChanges(BaseModel):
    comparison_available: bool
    previous_period: date | None
    current_period: date | None
    previous_evidence: TargetResult | None
    current_evidence: TargetResult | None
    changes: list[ChangeEvent]
    metric_changed: bool
    availability_lost: bool
    availability_restored: bool


class ConfirmationSectionChanges(BaseModel):
    """Anchored to `latest_shared_observation_period` (see
    `app.domain.inflation.latest_shared_observation_period`), never to
    `inflation_v1.0`'s own `latest_common_period` -- see the frozen
    contract's "Monitor vs. What Changed: anchor semantics." Embeds all
    four underlying `SeriesMomentumResult` evaluations plus both
    relationships, so this section is independently auditable without
    referencing any other section or the live Monitor result."""

    comparison_available: bool
    previous_confirmation_period: date | None
    current_confirmation_period: date | None
    previous_primary_state: SeriesMomentumResult | None
    previous_confirmation_state: SeriesMomentumResult | None
    previous_relationship: ConfirmationRelationship | None
    current_primary_state: SeriesMomentumResult | None
    current_confirmation_state: SeriesMomentumResult | None
    current_relationship: ConfirmationRelationship | None
    changes: list[ChangeEvent]
    relationship_changed: bool
    confirmation_availability_lost: bool
    confirmation_availability_restored: bool


class InflationWhatChangedResult(BaseModel):
    """The complete canonical, typed What Changed result. No global
    `previous_result`/`current_result` snapshot pair (per the frozen
    contract's Decision 3) -- each section below owns its own exact
    canonical evidence and period pair. `current_monitor_result` is
    optional convenience/context only, never required for
    auditability."""

    methodology_id: str = METHODOLOGY_ID
    comparison_contract_id: str = COMPARISON_CONTRACT_ID
    comparison_type: str = COMPARISON_TYPE
    data_basis: str = DATA_BASIS

    primary_momentum_changes: SeriesMomentumSectionChanges
    confirmation_changes: ConfirmationSectionChanges
    target_changes: TargetSectionChanges
    headline_pce_changes: SeriesMomentumSectionChanges
    headline_cpi_changes: SeriesMomentumSectionChanges

    changes: list[ChangeEvent]

    any_metric_changed: bool
    any_state_changed: bool
    any_availability_changed: bool
    confirmation_changed: bool

    current_monitor_result: InflationMonitorResult | None = None
