"""Pure, deterministic methodology core for the Labor Market Monitor
(`labor_v1.0`, frozen and normative in
`research/labor_momentum/LABOR_V1_FROZEN_METHODOLOGY.md`).

Like `app.domain.inflation`, this module has no knowledge of FastAPI,
HTTP, FRED, SQLAlchemy, database sessions, environment variables, or
logging, and never mutates global state. Given the same inputs, every
function here always produces the same output.

Every horizon here is resolved by an EXACT calendar-month lookup
against an explicit `{date: value}` index, never by counting back N
items in a list -- the same discipline `app.domain.inflation` already
established, restated here rather than imported (this project's
domain modules are each independent of one another by design; see
`tests/test_domain_architectural_independence.py`'s
"imports no other domain module" guards for the precedent this
follows).

PAYEMS is converted from FRED's native "Thousands of Persons" to
actual persons/jobs in exactly ONE place (`build_jobs_index`) -- every
`_jobs`-suffixed value downstream of it is already in that unit; never
re-derive or re-convert anywhere else in this module.
"""

from datetime import date

from app.models.labor import (
    LaborObservationEvidence,
    EmploymentCondition,
    EmploymentMomentum,
    EmploymentResult,
    EmploymentState,
    LaborMonitorResult,
    LaborState,
    PAYEMS_JOBS_PER_NATIVE_UNIT,
    PAYEMS_SERIES_ID,
    UNRATE_SERIES_ID,
    UnemploymentResult,
    UnemploymentTrendState,
)
from app.models.series import Observation

# ---------------------------------------------------------------------
# Calendar arithmetic and index construction
# ---------------------------------------------------------------------


def month_before(period: date, months_back: int) -> date:
    """The exact calendar month `months_back` months before `period`,
    both normalized to day 1 -- `months_back=0` returns `period`
    itself. Pure calendar arithmetic; never dependent on which rows
    happen to be persisted."""
    total_months = period.year * 12 + (period.month - 1) - months_back
    year, month0 = divmod(total_months, 12)
    return date(year, month0 + 1, 1)


def latest_observation_date(observations: list[Observation]) -> date | None:
    """The latest date for which ANY persisted observation row exists
    -- deliberately including one whose value is missing/invalid.
    `None` if the series has no persisted observation at all."""
    dates = [obs.date for obs in observations]
    return max(dates) if dates else None


def build_jobs_index(observations: list[Observation]) -> dict[date, float]:
    """A `{month: value}` map of every OBSERVED, numerically present
    PAYEMS value -- converted from FRED's native "Thousands of Persons"
    to actual persons/jobs (`* PAYEMS_JOBS_PER_NATIVE_UNIT`), exactly
    once, here. A `None`-valued observation is simply excluded, never
    coerced to zero and never left in the map as a value a lookup
    could mistake for present."""
    return {obs.date: obs.value * PAYEMS_JOBS_PER_NATIVE_UNIT for obs in observations if obs.value is not None}


def build_rate_index(observations: list[Observation]) -> dict[date, float]:
    """A `{month: value}` map of every OBSERVED, numerically present
    UNRATE value -- UNRATE is already a percentage rate, so no unit
    conversion is applied here (unlike `build_jobs_index`)."""
    return {obs.date: obs.value for obs in observations if obs.value is not None}


# ---------------------------------------------------------------------
# PAYEMS -- employment condition and momentum
# ---------------------------------------------------------------------


def monthly_change(index: dict[date, float], m: date) -> float | None:
    """PAYEMS_jobs[m] - PAYEMS_jobs[m-1]. `None` if either exact
    calendar month is missing from `index`."""
    current = index.get(m)
    past = index.get(month_before(m, 1))
    if current is None or past is None:
        return None
    return current - past


def average_monthly_change(index: dict[date, float], t: date, n_months: int) -> float | None:
    """The average of `monthly_change` over the `n_months` calendar
    months ending at (and including) `t` -- requires exactly
    `n_months + 1` consecutive index entries. `None` if ANY of the
    `n_months` monthly changes in the window is unavailable -- never
    averaged over a partial window. Reused for both
    `current_3m_avg_jobs(t)` (n_months=3, anchored at `t`) and
    `prior_3m_avg_jobs(t)` (n_months=3, anchored at `month_before(t, 3)`)."""
    changes: list[float] = []
    for offset in range(n_months):
        change = monthly_change(index, month_before(t, offset))
        if change is None:
            return None
        changes.append(change)
    return sum(changes) / len(changes)


def classify_employment_condition(value: float | None, deadband_jobs: float) -> EmploymentCondition:
    """Boundary inclusive for `FLAT` on both ends -- a value exactly at
    either edge is `FLAT`, never nudged by an added epsilon (see
    LABOR_V1_FROZEN_METHODOLOGY.md §3)."""
    if value is None:
        return "INSUFFICIENT_DATA"
    if value > deadband_jobs:
        return "EXPANDING"
    if value < -deadband_jobs:
        return "CONTRACTING"
    return "FLAT"


def classify_employment_momentum(recent: float | None, older: float | None, deadband_jobs: float) -> EmploymentMomentum:
    """`IMPROVING`/`STEADY`/`WORSENING` -- NOT `ACCELERATING`/
    `DECELERATING` (see LABOR_V1_FROZEN_METHODOLOGY.md §4's own
    vocabulary note: those words read as implicitly positive-direction-
    only, which would misdescribe a decelerating CONTRACTION as
    something other than "improving"). Boundary inclusive for `STEADY`."""
    if recent is None or older is None:
        return "INSUFFICIENT_DATA"
    diff = recent - older
    if diff > deadband_jobs:
        return "IMPROVING"
    if diff < -deadband_jobs:
        return "WORSENING"
    return "STEADY"


# Transcribed exactly from LABOR_V1_FROZEN_METHODOLOGY.md §5 -- all 9
# cells explicit, never derived from intuition at runtime. Frozen:
# `RECOVERING` exists specifically so a still-contracting-but-improving
# month is never conflated with genuine expansion (August 2009 -- see
# LABOR_V1_FROZEN_METHODOLOGY.md §14).
_EMPLOYMENT_STATE_TABLE: dict[tuple[EmploymentCondition, EmploymentMomentum], EmploymentState] = {
    ("EXPANDING", "IMPROVING"): "EXPANDING",
    ("EXPANDING", "STEADY"): "EXPANDING",
    ("EXPANDING", "WORSENING"): "COOLING",
    ("FLAT", "IMPROVING"): "STABLE",
    ("FLAT", "STEADY"): "STABLE",
    ("FLAT", "WORSENING"): "STABLE",
    ("CONTRACTING", "IMPROVING"): "RECOVERING",
    ("CONTRACTING", "STEADY"): "CONTRACTING",
    ("CONTRACTING", "WORSENING"): "CONTRACTING",
}


def combine_employment_state(condition: EmploymentCondition, momentum: EmploymentMomentum) -> EmploymentState:
    if condition == "INSUFFICIENT_DATA" or momentum == "INSUFFICIENT_DATA":
        return "INSUFFICIENT_DATA"
    return _EMPLOYMENT_STATE_TABLE[(condition, momentum)]


def compute_employment_result(
    index: dict[date, float],
    t: date,
    condition_deadband_jobs: float,
    momentum_deadband_jobs: float,
) -> EmploymentResult:
    """The complete PAYEMS-owned result at exact calendar month `t`.
    Requires exact PAYEMS observations at `t` through `t-6` (7
    consecutive months, per LABOR_V1_FROZEN_METHODOLOGY.md §4);
    `observations` below always lists all 7 exact required months,
    `value=None` for any that are genuinely missing -- never a
    truncated or silently-shorter list."""
    current_3m = average_monthly_change(index, t, 3)
    prior_3m = average_monthly_change(index, month_before(t, 3), 3)
    momentum_delta = None if current_3m is None or prior_3m is None else current_3m - prior_3m

    condition = classify_employment_condition(current_3m, condition_deadband_jobs)
    momentum = classify_employment_momentum(current_3m, prior_3m, momentum_deadband_jobs)
    state = combine_employment_state(condition, momentum)

    observations = [
        LaborObservationEvidence(
            series_id=PAYEMS_SERIES_ID,
            observation_date=month_before(t, offset),
            # Evidence preserves the canonical jobs-unit value (already
            # converted, matching every other _jobs field on this
            # result) -- never the raw native-thousands figure, which
            # would require a reader to redo the conversion by hand.
            value=index.get(month_before(t, offset)),
        )
        for offset in range(7)
    ]

    return EmploymentResult(
        current_3m_avg_jobs=current_3m,
        prior_3m_avg_jobs=prior_3m,
        momentum_delta_jobs=momentum_delta,
        condition_deadband_jobs=condition_deadband_jobs,
        momentum_deadband_jobs=momentum_deadband_jobs,
        condition=condition,
        momentum=momentum,
        state=state,
        observations=observations,
    )


# ---------------------------------------------------------------------
# UNRATE -- unemployment trend
# ---------------------------------------------------------------------


def average_rate(index: dict[date, float], start: date, n_months: int) -> float | None:
    """Mean of `index[start], index[start-1], ..., index[start-(n_months-1)]`
    -- `None` if any of those `n_months` exact calendar months is
    missing."""
    values: list[float] = []
    for offset in range(n_months):
        value = index.get(month_before(start, offset))
        if value is None:
            return None
        values.append(value)
    return sum(values) / len(values)


def classify_unemployment_trend_state(delta_pp: float | None, deadband_pp: float) -> UnemploymentTrendState:
    """Boundary inclusive for `STABLE` (see LABOR_V1_FROZEN_METHODOLOGY.md
    §6)."""
    if delta_pp is None:
        return "INSUFFICIENT_DATA"
    if delta_pp > deadband_pp:
        return "DETERIORATING"
    if delta_pp < -deadband_pp:
        return "IMPROVING"
    return "STABLE"


def compute_unemployment_result(index: dict[date, float], t: date, deadband_pp: float) -> UnemploymentResult:
    """The complete UNRATE-owned result at exact calendar month `t`.
    Requires exact UNRATE observations at `t, t-1, t-2, t-12, t-13,
    t-14` (six specific months, per LABOR_V1_FROZEN_METHODOLOGY.md
    §6); `observations` below always lists all six, `value=None` for
    any that are genuinely missing."""
    current_3m = average_rate(index, t, 3)
    prior_year_3m = average_rate(index, month_before(t, 12), 3)
    delta_pp = None if current_3m is None or prior_year_3m is None else current_3m - prior_year_3m
    state = classify_unemployment_trend_state(delta_pp, deadband_pp)

    required_months = [month_before(t, offset) for offset in range(3)] + [month_before(t, 12 + offset) for offset in range(3)]
    observations = [
        LaborObservationEvidence(series_id=UNRATE_SERIES_ID, observation_date=month, value=index.get(month))
        for month in required_months
    ]

    return UnemploymentResult(
        current_3m_avg=current_3m,
        prior_year_3m_avg=prior_year_3m,
        delta_pp=delta_pp,
        unemployment_deadband_pp=deadband_pp,
        state=state,
        observations=observations,
    )


# ---------------------------------------------------------------------
# Top-level Labor state
# ---------------------------------------------------------------------

# Transcribed exactly from LABOR_V1_FROZEN_METHODOLOGY.md §7. Only
# four combinations resolve to a clean, non-MIXED result; every
# RECOVERING pairing (and everything else not explicitly listed here)
# is MIXED -- an explicit, documented default, never a fallthrough
# bug. No weights, no score, no majority vote, no hidden tie-breaker.
_LABOR_STATE_TABLE: dict[tuple[EmploymentState, UnemploymentTrendState], LaborState] = {
    ("EXPANDING", "IMPROVING"): "STRENGTHENING",
    ("COOLING", "DETERIORATING"): "COOLING",
    ("CONTRACTING", "DETERIORATING"): "COOLING",
    ("STABLE", "STABLE"): "STABLE",
}


def combine_labor_state(employment_state: EmploymentState, unemployment_state: UnemploymentTrendState) -> LaborState:
    if employment_state == "INSUFFICIENT_DATA" or unemployment_state == "INSUFFICIENT_DATA":
        return "INSUFFICIENT_DATA"
    return _LABOR_STATE_TABLE.get((employment_state, unemployment_state), "MIXED")


# ---------------------------------------------------------------------
# Evaluation period and full assembly
# ---------------------------------------------------------------------


def determine_evaluation_period(payems_observations: list[Observation], unrate_observations: list[Observation]) -> date | None:
    """The single shared `evaluation_period` for one `LaborMonitorResult`
    -- bounded by the EARLIER of the two series' own latest persisted
    observation dates (per LABOR_V1_FROZEN_METHODOLOGY.md §10), a
    deterministic choice, never a search for "a month that works."
    `None` only if either series has zero persisted observations at
    all -- no candidate period can be chosen."""
    payems_latest = latest_observation_date(payems_observations)
    unrate_latest = latest_observation_date(unrate_observations)
    if payems_latest is None or unrate_latest is None:
        return None
    return min(payems_latest, unrate_latest)


def compute_labor_monitor_result(
    payems_observations: list[Observation],
    unrate_observations: list[Observation],
    condition_deadband_jobs: float,
    momentum_deadband_jobs: float,
    unemployment_deadband_pp: float,
) -> LaborMonitorResult:
    """The complete canonical `labor_v1.0` result, computed entirely
    from the given observation lists. Deterministic: the same two
    lists always produce byte-identical output.

    `evaluation_period` is chosen once (`determine_evaluation_period`)
    and used for BOTH `employment` and `unemployment` -- this function
    never evaluates the two owners at two different reference months.
    If no evaluation period can be determined at all (either series
    has zero persisted observations), the entire result is
    `INSUFFICIENT_DATA` with `evaluation_period=None` and both
    sub-results built from empty indices (so their own
    `observations` evidence lists still show all required months with
    `value=None`, never omitted).
    """
    payems_index = build_jobs_index(payems_observations)
    unrate_index = build_rate_index(unrate_observations)

    evaluation_period = determine_evaluation_period(payems_observations, unrate_observations)

    if evaluation_period is None:
        # No candidate period at all -- report INSUFFICIENT_DATA
        # against `date.min`-anchored empty evidence lists is
        # misleading (it would claim a specific, fabricated
        # evaluation month); instead both sub-results carry no
        # evidence at all, which is the honest reflection of "not
        # even a candidate period could be chosen."
        employment = EmploymentResult(
            current_3m_avg_jobs=None,
            prior_3m_avg_jobs=None,
            momentum_delta_jobs=None,
            condition_deadband_jobs=condition_deadband_jobs,
            momentum_deadband_jobs=momentum_deadband_jobs,
            condition="INSUFFICIENT_DATA",
            momentum="INSUFFICIENT_DATA",
            state="INSUFFICIENT_DATA",
            observations=[],
        )
        unemployment = UnemploymentResult(
            current_3m_avg=None,
            prior_year_3m_avg=None,
            delta_pp=None,
            unemployment_deadband_pp=unemployment_deadband_pp,
            state="INSUFFICIENT_DATA",
            observations=[],
        )
        return LaborMonitorResult(
            state="INSUFFICIENT_DATA",
            evaluation_period=None,
            employment=employment,
            unemployment=unemployment,
        )

    employment = compute_employment_result(payems_index, evaluation_period, condition_deadband_jobs, momentum_deadband_jobs)
    unemployment = compute_unemployment_result(unrate_index, evaluation_period, unemployment_deadband_pp)
    state = combine_labor_state(employment.state, unemployment.state)

    return LaborMonitorResult(
        state=state,
        evaluation_period=evaluation_period,
        employment=employment,
        unemployment=unemployment,
    )
