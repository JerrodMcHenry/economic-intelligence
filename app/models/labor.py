"""Typed, application-owned canonical result models for the Labor
Market Monitor, methodology `labor_v1.0` (frozen in
`research/labor_momentum/LABOR_V1_FROZEN_METHODOLOGY.md` -- normative;
this module implements it, it does not reinterpret it).

Plain Pydantic data, like `app.models.inflation` -- no FastAPI or
SQLAlchemy dependency. Consumed by `app.domain.labor`'s pure functions
and `app.services.labor`'s orchestration, and returned directly by
`app.api.labor`.

This is the ONE canonical production definition of `labor_v1.0`'s
constants and enums. Nothing else in the application may hardcode a
duplicate series ID or deadband -- every other module imports them
from here.

Deliberately a NEW, independently-defined set of models -- not a
shared base class with `app.models.inflation`'s own
`InflationMetricEvidence`/`SeriesMomentumResult` shapes, even though
the two monitors are structurally similar. This is the second
canonical monitor; per the frozen spec's own "no premature generic
monitor framework" instruction, Labor is implemented independently
first, and any real shared abstraction is deferred until a third
monitor's own requirements can inform what that abstraction should
actually look like.

`data_basis` uses `"latest_revised_data"` -- `app.models.inflation.DATA_BASIS`'s
exact machine-string convention, not the frozen methodology document's
own human-sentence example ("Latest revised data") -- per this
increment's own explicit instruction to use "the existing project
convention" and reconcile in the project's favor when the two differ
(see docs/ENGINEERING_JOURNAL.md's #20B entry for the full account of
this and the other resolved discrepancies).
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel

from app.concepts.bindings import active_binding
from app.models.series import SeriesIdentity

METHODOLOGY_ID = "labor_v1.0"
DATA_BASIS = "latest_revised_data"

# --- Economic concept identity (Increment #38, ADR-034) -------------
#
# `labor_v1.0`'s two components, named by what they measure rather than
# by who publishes them. The distinction between these two concepts is
# not cosmetic: the employment concept counts nonfarm payroll JOBS from
# the CES establishment survey, the unemployment concept counts PEOPLE
# from the CPS household survey. Different universes, different
# surveys, and -- as the #35 Radar research found -- incompatible
# resolutions, which is why neither is ever a substitute for the other.
EMPLOYMENT_CONCEPT_ID = "us.nonfarm.payroll-employment.sa.monthly"
UNEMPLOYMENT_CONCEPT_ID = "us.unemployment-rate.sa.monthly"

# --- Stored series identifiers, DERIVED from the active binding ------
#
# Byte-identical to the literals they replaced; no longer hardcoded.
# These name a place to LOOK IN STORAGE, not MacroChipz's identity.
PAYEMS_SERIES_ID = active_binding(EMPLOYMENT_CONCEPT_ID).storage_series_id
UNRATE_SERIES_ID = active_binding(UNEMPLOYMENT_CONCEPT_ID).storage_series_id

# PAYEMS is persisted in FRED's native "Thousands of Persons" -- every
# `labor_v1.0` formula operates on actual persons/jobs instead (see
# LABOR_V1_FROZEN_METHODOLOGY.md §2). This is the ONE conversion
# constant; `app.domain.labor.build_jobs_index` is the ONE place it is
# applied.
PAYEMS_JOBS_PER_NATIVE_UNIT = active_binding(EMPLOYMENT_CONCEPT_ID).canonical_unit_factor

CONDITION_DEADBAND_JOBS = 50_000
MOMENTUM_DEADBAND_JOBS = 50_000
UNEMPLOYMENT_DEADBAND_PP = 0.2


class LaborSeriesIdentities(BaseModel):
    """Who `labor_v1.0`'s two input series actually are (#38).

    Kept as one object because the two must never be swapped: the
    employment concept counts nonfarm payroll JOBS from the CES
    establishment survey and the unemployment concept counts PEOPLE
    from the CPS household survey. A positional mix-up would attribute
    one survey's evidence to the other.
    """

    employment: SeriesIdentity
    unemployment: SeriesIdentity


EmploymentCondition = Literal["EXPANDING", "FLAT", "CONTRACTING", "INSUFFICIENT_DATA"]
EmploymentMomentum = Literal["IMPROVING", "STEADY", "WORSENING", "INSUFFICIENT_DATA"]
EmploymentState = Literal["EXPANDING", "COOLING", "STABLE", "CONTRACTING", "RECOVERING", "INSUFFICIENT_DATA"]
UnemploymentTrendState = Literal["IMPROVING", "DETERIORATING", "STABLE", "INSUFFICIENT_DATA"]
LaborState = Literal["STRENGTHENING", "COOLING", "STABLE", "MIXED", "INSUFFICIENT_DATA"]


class LaborObservationEvidence(BaseModel):
    """One exact-calendar-month source observation, exactly as
    persisted (FRED-native units -- PAYEMS in thousands of persons,
    UNRATE in percent; the jobs conversion is a pure, deterministic,
    documented multiply, reconstructable from this raw value alone, so
    it is not duplicated here). `value: None` means this exact required
    calendar month has no usable persisted observation -- never
    omitted from the list, so a caller can always see exactly which
    month(s) were missing, not just that something was missing."""

    #: Source-neutral identity (#38), plus the provider that actually
    #: supplied this observation and their own identifier for it. Read
    #: from the persisted series row rather than stamped from a module
    #: constant -- the defect ADR-034 exists to fix.
    concept_id: str
    provider: str
    series_id: str
    observation_date: date
    value: float | None


class EmploymentResult(BaseModel):
    """The PAYEMS-owned half of `labor_v1.0`: employment condition
    (level) and momentum (trend), combined into one `EmploymentState`.
    `condition`/`momentum`/`state` are all `INSUFFICIENT_DATA` together
    whenever any of the 7 exact required PAYEMS calendar months
    (`observations`, `t` through `t-6`) is missing -- never computed
    from a partial window."""

    series_id: str = PAYEMS_SERIES_ID
    current_3m_avg_jobs: float | None
    prior_3m_avg_jobs: float | None
    momentum_delta_jobs: float | None
    condition_deadband_jobs: float = CONDITION_DEADBAND_JOBS
    momentum_deadband_jobs: float = MOMENTUM_DEADBAND_JOBS
    condition: EmploymentCondition
    momentum: EmploymentMomentum
    state: EmploymentState
    observations: list[LaborObservationEvidence]


class UnemploymentResult(BaseModel):
    """The UNRATE-owned half of `labor_v1.0`: current 3-month average
    vs. the 3-month average from exactly one year earlier.
    `INSUFFICIENT_DATA` whenever any of the 6 exact required UNRATE
    calendar months (`observations`) is missing."""

    series_id: str = UNRATE_SERIES_ID
    current_3m_avg: float | None
    prior_year_3m_avg: float | None
    delta_pp: float | None
    unemployment_deadband_pp: float = UNEMPLOYMENT_DEADBAND_PP
    state: UnemploymentTrendState
    observations: list[LaborObservationEvidence]


class LaborMonitorResult(BaseModel):
    """The complete canonical, typed Labor Monitor result -- structured
    evidence, not prose. Every result carries `methodology_id`
    explicitly; it is never inferred from the request path or any
    other context.

    `evaluation_period` is `None` only when neither PAYEMS nor UNRATE
    has any persisted observation at all (no candidate period can be
    chosen) -- distinct from, and never conflated with, `state ==
    "INSUFFICIENT_DATA"` at a genuine, chosen `evaluation_period` where
    one or both components simply lack enough trailing history. Once
    chosen, `evaluation_period` is the SAME calendar month for both
    `employment` and `unemployment` -- this monitor never reports the
    two owners evaluated at two different reference months in one
    result (see LABOR_V1_FROZEN_METHODOLOGY.md §10).
    """

    methodology_id: str = METHODOLOGY_ID
    data_basis: str = DATA_BASIS
    state: LaborState
    evaluation_period: date | None
    employment: EmploymentResult
    unemployment: UnemploymentResult
