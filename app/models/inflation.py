"""Typed, application-owned canonical result models for the Inflation
Monitor, methodology `inflation_v1.0` (frozen in
`docs/methodology/inflation-monitor-v1.0.md` -- normative; this module
implements it, it does not reinterpret it).

Plain Pydantic data, like `app.models.series`/`app.models.analysis` --
no FastAPI or SQLAlchemy dependency. Consumed by `app.domain.inflation`'s
pure functions and `app.services.inflation`'s orchestration, and
returned directly by `app.api.inflation`.

This is the ONE canonical production definition of `inflation_v1.0`'s
constants and enums. Nothing else in the application may hardcode a
duplicate series ID, the Fed objective, or the neutral band -- every
other module imports them from here.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel

from app.concepts.bindings import active_binding
from app.models.series import SeriesIdentity

METHODOLOGY_ID = "inflation_v1.0"
DATA_BASIS = "latest_revised_data"

FED_OBJECTIVE_PERCENT = 2.0
NEUTRAL_BAND_PP = 0.10

# --- Economic concept identity (Increment #38, ADR-034) -------------
#
# These are what `inflation_v1.0` is ABOUT: source-neutral MacroChipz
# identities that do not change when the provider does. The frozen
# methodology's roles -- primary, confirmation, target, headline context
# -- are expressed in concepts.
PRIMARY_CONCEPT_ID = "us.pce.core.price-index.sa.monthly"
CONFIRMATION_CONCEPT_ID = "us.cpi.core.price-index.sa.monthly"
TARGET_CONCEPT_ID = "us.pce.headline.price-index.sa.monthly"
HEADLINE_CPI_CONCEPT_ID = "us.cpi.headline.price-index.sa.monthly"

# --- Stored series identifiers, DERIVED from the active binding ------
#
# Still the FRED identifiers today, and byte-identical to the literals
# these lines replaced -- but no longer hardcoded here. They are now the
# `storage_series_id` of whichever binding is active, so a future
# provider cutover moves them by flipping one flag in
# `app/concepts/bindings.py` rather than by editing a methodology module.
#
# These name a place to LOOK IN STORAGE. They are not MacroChipz's
# identity for the concept, and canonical evidence no longer stamps
# them from here -- see `SeriesIdentity` in app/models/series.py.
PRIMARY_SERIES_ID = active_binding(PRIMARY_CONCEPT_ID).storage_series_id
CONFIRMATION_SERIES_ID = active_binding(CONFIRMATION_CONCEPT_ID).storage_series_id
TARGET_SERIES_ID = active_binding(TARGET_CONCEPT_ID).storage_series_id
HEADLINE_CPI_SERIES_ID = active_binding(HEADLINE_CPI_CONCEPT_ID).storage_series_id


class InflationSeriesIdentities(BaseModel):
    """Who `inflation_v1.0`'s four input series actually are (#38).

    Passed in by the caller rather than read from module constants, so
    every piece of evidence the methodology stamps names the provider
    that genuinely supplied the observations it used. One object rather
    than four parameters, because the four always travel together and a
    positional mix-up between two index series would be silent.
    """

    primary: SeriesIdentity
    confirmation: SeriesIdentity
    target: SeriesIdentity
    headline_cpi: SeriesIdentity


InflationState = Literal["COOLING", "HEATING", "STABLE", "MIXED", "INSUFFICIENT_DATA"]
ConfirmationRelationship = Literal["CONFIRMS", "DIVERGES", "INCONCLUSIVE", "UNAVAILABLE"]
InflationTransformation = Literal["1m_annualized", "3m_annualized", "6m_annualized", "12m"]


class InflationMetricEvidence(BaseModel):
    """Provenance for one horizon's derived value at one exact
    calculation period: which two exact-calendar-month endpoints it
    used, their raw persisted index values, and the unrounded computed
    value. `endpoint_value_*`/`value` are `None` whenever the
    corresponding endpoint is missing or invalid -- never a fabricated
    placeholder. Sufficient, on its own, to reproduce the returned
    value by hand.
    """

    #: What this measures, source-neutral (#38). Stable across a
    #: provider migration.
    concept_id: str
    #: Who actually supplied the underlying observations, and their own
    #: identifier for the series. Read from the persisted series row,
    #: never from a module constant -- so after a provider cutover, old
    #: evidence keeps naming the provider that really produced it
    #: (ADR-034, Invariant D).
    provider: str
    series_id: str
    calculation_period: date
    transformation: InflationTransformation
    endpoint_date_current: date
    endpoint_date_past: date
    endpoint_value_current: float | None
    endpoint_value_past: float | None
    value: float | None
    methodology_id: str = METHODOLOGY_ID
    data_basis: str = DATA_BASIS


class SeriesMomentumResult(BaseModel):
    """One series' independent five-state momentum classification at
    one specific `calculation_period`, under `inflation_v1.0`. The same
    shape is used for Core PCE (primary), Core CPI (confirmation), and,
    context-only, Headline PCE and Headline CPI -- identical
    methodology, identical fields, for all four, per the frozen
    specification. Never references any other series.

    `calculation_period` (and therefore every evidence/value field) is
    `None` only when the series has no usable persisted observation at
    all. Missing `r_1m_annualized` alone never forces `state` to
    `INSUFFICIENT_DATA` -- only a missing/invalid `r_3m`, `r_6m`, or
    `r_12m` does.
    """

    #: Source-neutral identity (#38). `series_id` below remains the
    #: stored provider identifier, so both questions -- "what is this?"
    #: and "where did it come from?" -- have their own field.
    concept_id: str
    series_id: str
    calculation_period: date | None
    latest_observation_period: date | None
    latest_valid_state_period: date | None

    r_1m_annualized: float | None
    r_3m_annualized: float | None
    r_6m_annualized: float | None
    r_12m: float | None

    neutral_band_pp: float
    lower_boundary: float | None
    upper_boundary: float | None

    state: InflationState
    missing_required_metrics: list[str]

    evidence_1m: InflationMetricEvidence | None
    evidence_3m: InflationMetricEvidence | None
    evidence_6m: InflationMetricEvidence | None
    evidence_12m: InflationMetricEvidence | None


class TargetResult(BaseModel):
    """Headline PCE YoY vs. the Fed's 2.0% longer-run objective. A
    numeric gap only -- `inflation_v1.0` defines no categorical
    target-gap state. Computed independently of Core PCE's own
    momentum period; one's availability never gates the other."""

    series_id: str = TARGET_SERIES_ID
    calculation_period: date | None
    headline_pce_yoy: float | None
    fed_objective_percent: float = FED_OBJECTIVE_PERCENT
    target_gap_pp: float | None
    available: bool
    evidence: InflationMetricEvidence | None


class ConfirmationResult(BaseModel):
    """Preserves the distinction the frozen spec requires between Core
    CPI's own latest standalone state, both series' states at the
    shared comparison period, the comparison period itself, and the
    resulting relationship -- so a caller can never accidentally treat
    a different-period pair as confirmation evidence."""

    confirmation_latest: SeriesMomentumResult
    primary_at_comparison_period: SeriesMomentumResult | None
    confirmation_at_comparison_period: SeriesMomentumResult | None
    latest_common_period: date | None
    relationship: ConfirmationRelationship


class HeadlineContextResult(BaseModel):
    """Headline PCE and Headline CPI, each independently classified by
    the same methodology. `inflation_v1.0` defines no aggregate
    headline-context state -- there is deliberately no combined field
    here beyond these two independent results."""

    headline_pce: SeriesMomentumResult
    headline_cpi: SeriesMomentumResult


class InflationPeriods(BaseModel):
    latest_common_period: date | None
    data_through: date | None


class InflationCoverage(BaseModel):
    """Coverage, not confidence: each boolean is true only if that
    tier's own canonical result is actually calculable -- never merely
    that a recent row exists. No confidence percentage is derived here;
    a caller may compute `available_component_count`/`4` for display."""

    primary_available: bool
    # The confirmation TIER's canonical output is the same-period Core
    # PCE/Core CPI relationship -- confirmation_available ==
    # (confirmation.relationship != "UNAVAILABLE"), never merely
    # whether Core CPI's own standalone state happens to be
    # calculable. Core CPI's own standalone availability remains fully
    # visible, unabridged, via confirmation.confirmation_latest.state.
    confirmation_available: bool
    target_available: bool
    headline_cpi_available: bool


class InflationMonitorResult(BaseModel):
    """The complete canonical, typed Inflation Monitor result --
    structured evidence, not prose. Every result carries
    `methodology_id` explicitly; it is never inferred from the request
    path or any other context."""

    methodology_id: str = METHODOLOGY_ID
    data_basis: str = DATA_BASIS
    target: TargetResult
    underlying_momentum: SeriesMomentumResult
    confirmation: ConfirmationResult
    headline_context: HeadlineContextResult
    periods: InflationPeriods
    coverage: InflationCoverage
