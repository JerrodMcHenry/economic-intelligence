"""Pure, deterministic methodology core for the Inflation Monitor
(`inflation_v1.0`, frozen and normative in
`docs/methodology/inflation-monitor-v1.0.md`).

Like `app/domain/transformations.py` and `app/domain/analysis.py`, this
module has no knowledge of FastAPI, HTTP, FRED, SQLAlchemy, database
sessions, environment variables, or logging, and never mutates global
state. Given the same inputs, every function here always produces the
same output.

CRITICAL, frozen-spec-mandated departure from
`app/domain/transformations.py`'s row-position offset pattern: every
horizon here (`t-1`/`t-3`/`t-6`/`t-12`) is resolved by an EXACT
calendar-month lookup against an explicit `{date: value}` index, never
by counting back N items in a list. A calendar month absent from the
index (no persisted row, or a persisted row whose value fails numeric
validation) is indistinguishable, for this purpose, from any other kind
of "unavailable" -- and an unavailable endpoint can never silently
shift which calendar month a later, unrelated calculation actually
uses. This equivalence was verified (not assumed) for the historical
research data during the methodology freeze; production makes no such
assumption and always resolves dates explicitly.
"""

import math
from datetime import date

from app.models.inflation import (
    NEUTRAL_BAND_PP,
    ConfirmationRelationship,
    FED_OBJECTIVE_PERCENT,
    HeadlineContextResult,
    InflationCoverage,
    InflationMetricEvidence,
    InflationMonitorResult,
    InflationPeriods,
    InflationState,
    InflationTransformation,
    ConfirmationResult,
    CONFIRMATION_SERIES_ID,
    HEADLINE_CPI_SERIES_ID,
    PRIMARY_SERIES_ID,
    SeriesMomentumResult,
    TARGET_SERIES_ID,
    TargetResult,
)
from app.models.series import Observation

_UNDERLYING_HORIZONS: tuple[int, ...] = (3, 6, 12)


# ---------------------------------------------------------------------
# Index construction and numeric safety
# ---------------------------------------------------------------------


def _is_valid_index_value(value: float | None) -> bool:
    """A required index endpoint must be present, finite, and strictly
    greater than zero. `math.isfinite` is required -- not a bare
    `<=`/`>` comparison -- because `NaN` compares `False` to every
    comparison, including `NaN <= 0`; a naive guard would silently let
    it through."""
    return value is not None and math.isfinite(value) and value > 0


def build_index(observations: list[Observation]) -> dict[date, float]:
    """A `{date: value}` map of every OBSERVED, numerically valid index
    level in `observations`. An observation whose value is `None`,
    non-finite, zero, or negative is simply excluded -- never coerced,
    never left in the map as an invalid entry a later lookup could
    mistake for present. This is the single place raw
    `Observation.value`s are sanitized; every function below trusts
    that any value found in an index it's given is safe to use as-is.
    """
    index: dict[date, float] = {}
    for obs in observations:
        if _is_valid_index_value(obs.value):
            index[obs.date] = obs.value  # type: ignore[assignment]
    return index


def latest_observation_date(observations: list[Observation]) -> date | None:
    """The latest date for which ANY persisted observation row exists
    -- deliberately including one whose value is missing/invalid (e.g.
    FRED's "." marker, persisted as `value=None`). This is distinct
    from, and must never be confused with, the latest date in
    `build_index`'s output (which only contains numerically valid
    values): a row that exists but carries an unusable value is still
    "a persisted observation" for `latest_observation_period`'s
    purposes -- it simply cannot serve as a calculation endpoint."""
    dates = [obs.date for obs in observations]
    return max(dates) if dates else None


def month_before(period: date, months_back: int) -> date:
    """The exact calendar month `months_back` months before `period`
    -- both normalized to day 1 (FRED's own monthly convention), e.g.
    `month_before(date(2026, 7, 1), 3) == date(2026, 4, 1)`. Pure
    calendar arithmetic over the `period`/`months_back` values alone;
    never "the Nth previous row," and never dependent on which rows
    happen to be persisted. `months_back=0` returns `period` itself.
    """
    total_months = period.year * 12 + (period.month - 1) - months_back
    year, month0 = divmod(total_months, 12)
    return date(year, month0 + 1, 1)


def _rate(index: dict[date, float], period: date, months_back: int) -> float | None:
    """The one general compounding formula behind every named horizon
    in the frozen spec: `((P_t / P_(t-n)) ** (12/n) - 1) * 100`. At
    `n=12` the exponent is exactly `1`, algebraically identical to the
    frozen spec's exponent-free `r_12m` form. `None` if either exact
    calendar endpoint is missing from `index` (never interpolated,
    never substituted)."""
    current = index.get(period)
    past = index.get(month_before(period, months_back))
    if current is None or past is None:
        return None
    return ((current / past) ** (12 / months_back) - 1) * 100


def _find_latest_period_with_valid_horizons(index: dict[date, float], required_horizons: tuple[int, ...]) -> date | None:
    """The latest period among `index`'s own keys (i.e. an actual
    persisted, valid observation date) for which every horizon in
    `required_horizons` resolves to a valid rate using exact calendar
    endpoints. Searches strictly backward from the most recent such
    date -- the most recent observation is not always usable (e.g. one
    of its required endpoints can itself be a real, currently-missing
    month), and a missing month must never shift which earlier period
    is reported as "latest valid"."""
    for period in sorted(index.keys(), reverse=True):
        if all(_rate(index, period, n) is not None for n in required_horizons):
            return period
    return None


def find_latest_valid_state_period(index: dict[date, float]) -> date | None:
    """The latest period for which `r_3m`, `r_6m`, and `r_12m` are all
    calculable -- distinct from `max(index)` ("latest observation
    period"), which may be a period whose own state cannot yet (or can
    no longer, given a real intermediate gap) be classified."""
    return _find_latest_period_with_valid_horizons(index, _UNDERLYING_HORIZONS)


def find_latest_period_with_valid_12m(index: dict[date, float]) -> date | None:
    """The latest period for which `r_12m` alone is calculable -- all
    the Target result needs; deliberately less strict than
    `find_latest_valid_state_period`, since level (target) and momentum
    (underlying state) are independent per the frozen spec."""
    return _find_latest_period_with_valid_horizons(index, (12,))


def find_latest_common_period(primary_index: dict[date, float], confirmation_index: dict[date, float]) -> date | None:
    """The greatest calendar month for which BOTH series independently
    have a valid canonical (r_3m/r_6m/r_12m) state -- not merely a
    shared observation row. Searches backward chronologically through
    the intersection of both series' own observation dates; `None` if
    no such period exists anywhere in the supported history."""
    common_dates = set(primary_index) & set(confirmation_index)
    for period in sorted(common_dates, reverse=True):
        if (
            all(_rate(primary_index, period, n) is not None for n in _UNDERLYING_HORIZONS)
            and all(_rate(confirmation_index, period, n) is not None for n in _UNDERLYING_HORIZONS)
        ):
            return period
    return None


def latest_shared_observation_period(
    primary_observations: list[Observation],
    confirmation_observations: list[Observation],
) -> date | None:
    """NEW period-selection concept, defined and used only by
    `inflation_what_changed_v1.0` (`docs/methodology/inflation-what-changed-v1.0.md`)
    -- NOT part of `inflation_v1.0` itself, and never used by the
    Monitor's own confirmation logic (`find_latest_common_period`,
    above, is unmodified and continues to serve it).

    The latest calendar month for which BOTH Core PCE and Core CPI have
    ANY observation row, regardless of classifiability -- deliberately
    weaker than `find_latest_common_period`, which requires both sides
    to already have a VALID canonical state. Because "valid state"
    implies "observation exists" but not the reverse,
    `find_latest_common_period(...) <= latest_shared_observation_period(...)`
    always. This is pure date-set arithmetic over the same two
    observation lists already fetched elsewhere; it introduces no new
    formula and requires no repository change.
    """
    primary_dates = {obs.date for obs in primary_observations}
    confirmation_dates = {obs.date for obs in confirmation_observations}
    shared = primary_dates & confirmation_dates
    return max(shared) if shared else None


# ---------------------------------------------------------------------
# Evidence and classification
# ---------------------------------------------------------------------


def _metric_evidence(
    index: dict[date, float],
    series_id: str,
    calculation_period: date,
    months_back: int,
    transformation: InflationTransformation,
) -> InflationMetricEvidence:
    """One horizon's full provenance at one exact calculation period:
    its two exact calendar endpoints, their raw persisted index values
    (whichever are actually present and valid), and the unrounded
    compounded value -- `None` if either endpoint is unavailable."""
    endpoint_date_past = month_before(calculation_period, months_back)
    return InflationMetricEvidence(
        series_id=series_id,
        calculation_period=calculation_period,
        transformation=transformation,
        endpoint_date_current=calculation_period,
        endpoint_date_past=endpoint_date_past,
        endpoint_value_current=index.get(calculation_period),
        endpoint_value_past=index.get(endpoint_date_past),
        value=_rate(index, calculation_period, months_back),
    )


def classify_state(
    r_3m: float, r_6m: float, r_12m: float, neutral_band_pp: float = NEUTRAL_BAND_PP
) -> tuple[InflationState, float, float]:
    """The core `inflation_v1.0` five-state boundary decision, given
    already-computed, valid rates -- deliberately isolated from
    calendar/index concerns so it is directly testable against
    hand-picked float literals (e.g. the exact IEEE-754 value of
    `3.0 - 0.10`), without needing index values that round-trip exactly
    through the annualization formula's roots (3M/6M involve a 4th/2nd
    root of the raw index ratio, which does not generally round-trip
    to a chosen decimal target in binary floating point).

    Boundary semantics (normative): the neutral interval
    `[r_12m - delta, r_12m + delta]` is inclusive on both ends
    (STABLE-eligible exactly at either boundary); COOLING/HEATING use
    strict `<`/`>` just outside it. No epsilon is added to either
    comparison. Returns `(state, lower_boundary, upper_boundary)`.
    """
    lower_boundary = r_12m - neutral_band_pp
    upper_boundary = r_12m + neutral_band_pp
    if r_3m < lower_boundary and r_6m < lower_boundary:
        return "COOLING", lower_boundary, upper_boundary
    if r_3m > upper_boundary and r_6m > upper_boundary:
        return "HEATING", lower_boundary, upper_boundary
    if lower_boundary <= r_3m <= upper_boundary and lower_boundary <= r_6m <= upper_boundary:
        return "STABLE", lower_boundary, upper_boundary
    return "MIXED", lower_boundary, upper_boundary


def classify_period(
    index: dict[date, float],
    series_id: str,
    calculation_period: date | None,
    latest_observation_period: date | None,
    latest_valid_state_period: date | None,
    neutral_band_pp: float = NEUTRAL_BAND_PP,
) -> SeriesMomentumResult:
    """Classify one series at one exact `calculation_period`, under
    `inflation_v1.0`'s five-state Candidate-B-Dual-Confirmation rule.
    `calculation_period` need not be the series' own latest -- this is
    the one primitive both "latest state" and "state at a specific
    (confirmation) comparison period" are built from, so the two paths
    can never drift into different classification logic.

    `calculation_period=None` means the series has no usable persisted
    observation at all; the result is `INSUFFICIENT_DATA` with no
    evidence to show, rather than fabricating a period to anchor to.

    Boundary semantics (normative, per the frozen spec): the neutral
    interval `[r_12m - delta, r_12m + delta]` is inclusive on both
    ends (STABLE-eligible exactly at the boundary); COOLING/HEATING use
    strict `<`/`>` just outside it. No epsilon is added anywhere in
    this comparison.
    """
    if calculation_period is None:
        return SeriesMomentumResult(
            series_id=series_id,
            calculation_period=None,
            latest_observation_period=latest_observation_period,
            latest_valid_state_period=latest_valid_state_period,
            r_1m_annualized=None,
            r_3m_annualized=None,
            r_6m_annualized=None,
            r_12m=None,
            neutral_band_pp=neutral_band_pp,
            lower_boundary=None,
            upper_boundary=None,
            state="INSUFFICIENT_DATA",
            missing_required_metrics=["r_3m", "r_6m", "r_12m"],
            evidence_1m=None,
            evidence_3m=None,
            evidence_6m=None,
            evidence_12m=None,
        )

    evidence_1m = _metric_evidence(index, series_id, calculation_period, 1, "1m_annualized")
    evidence_3m = _metric_evidence(index, series_id, calculation_period, 3, "3m_annualized")
    evidence_6m = _metric_evidence(index, series_id, calculation_period, 6, "6m_annualized")
    evidence_12m = _metric_evidence(index, series_id, calculation_period, 12, "12m")

    r_3m, r_6m, r_12m = evidence_3m.value, evidence_6m.value, evidence_12m.value

    missing_required_metrics: list[str] = []
    if r_3m is None:
        missing_required_metrics.append("r_3m")
    if r_6m is None:
        missing_required_metrics.append("r_6m")
    if r_12m is None:
        missing_required_metrics.append("r_12m")

    lower_boundary: float | None = None
    upper_boundary: float | None = None
    state: InflationState

    if missing_required_metrics:
        state = "INSUFFICIENT_DATA"
    else:
        assert r_3m is not None and r_6m is not None and r_12m is not None  # narrows for type-checking; guaranteed by the check above
        state, lower_boundary, upper_boundary = classify_state(r_3m, r_6m, r_12m, neutral_band_pp)

    return SeriesMomentumResult(
        series_id=series_id,
        calculation_period=calculation_period,
        latest_observation_period=latest_observation_period,
        latest_valid_state_period=latest_valid_state_period,
        r_1m_annualized=evidence_1m.value,
        r_3m_annualized=r_3m,
        r_6m_annualized=r_6m,
        r_12m=r_12m,
        neutral_band_pp=neutral_band_pp,
        lower_boundary=lower_boundary,
        upper_boundary=upper_boundary,
        state=state,
        missing_required_metrics=missing_required_metrics,
        evidence_1m=evidence_1m,
        evidence_3m=evidence_3m,
        evidence_6m=evidence_6m,
        evidence_12m=evidence_12m,
    )


def compute_series_momentum(
    observations: list[Observation],
    series_id: str,
    neutral_band_pp: float = NEUTRAL_BAND_PP,
) -> SeriesMomentumResult:
    """One series' own LATEST valid momentum classification --
    standalone, never comparing to any other series. The primitive
    behind Core PCE's canonical primary result, Core CPI's own latest
    confirmation state, and each headline series' context result.
    """
    index = build_index(observations)
    latest_observation_period = latest_observation_date(observations)
    latest_valid_state_period = find_latest_valid_state_period(index)
    calculation_period = latest_valid_state_period if latest_valid_state_period is not None else latest_observation_period
    return classify_period(
        index, series_id, calculation_period, latest_observation_period, latest_valid_state_period, neutral_band_pp
    )


def compute_series_momentum_at(
    observations: list[Observation],
    series_id: str,
    calculation_period: date | None,
    neutral_band_pp: float = NEUTRAL_BAND_PP,
) -> SeriesMomentumResult:
    """One series' canonical momentum result at an EXPLICIT
    `calculation_period` -- never searched for. The primitive
    `inflation_what_changed_v1.0` needs for its own, observation-based
    anchors (as opposed to `compute_series_momentum`'s "latest valid"
    search, which the Monitor uses). `latest_observation_period`/
    `latest_valid_state_period` are still reported on the result
    (informational, per `inflation_v1.0`'s existing
    `SeriesMomentumResult` contract) but do not influence which period
    is actually classified here -- that is entirely the caller's
    decision. Delegates to the exact same `classify_period` primitive
    `compute_series_momentum` uses; `calculation_period=None` yields
    `INSUFFICIENT_DATA` with no evidence, exactly as `classify_period`
    already defines."""
    index = build_index(observations)
    latest_observation_period = latest_observation_date(observations)
    latest_valid_state_period = find_latest_valid_state_period(index)
    return classify_period(
        index, series_id, calculation_period, latest_observation_period, latest_valid_state_period, neutral_band_pp
    )


def classify_confirmation_relationship(
    primary_state: InflationState | None, confirmation_state: InflationState | None
) -> ConfirmationRelationship:
    """The frozen four-value confirmation matrix, applied to two states
    from the exact same period. `MIXED`+`MIXED` is explicitly
    `INCONCLUSIVE`, never `CONFIRMS` -- confirmation requires
    directional or STABLE agreement, not merely "both uncertain"."""
    if primary_state is None or confirmation_state is None:
        return "UNAVAILABLE"
    if primary_state == "INSUFFICIENT_DATA" or confirmation_state == "INSUFFICIENT_DATA":
        return "UNAVAILABLE"
    if primary_state == confirmation_state and primary_state in ("COOLING", "HEATING", "STABLE"):
        return "CONFIRMS"
    if {primary_state, confirmation_state} == {"COOLING", "HEATING"}:
        return "DIVERGES"
    return "INCONCLUSIVE"


def compute_confirmation(
    primary_observations: list[Observation],
    confirmation_observations: list[Observation],
    neutral_band_pp: float = NEUTRAL_BAND_PP,
) -> ConfirmationResult:
    """Core CPI confirmation of Core PCE. Core CPI is classified fully
    independently (same methodology, own latest state); it NEVER
    changes Core PCE's own canonical state -- that invariant holds
    structurally here, since this function's Core-PCE-at-comparison-
    period value is computed by the same `classify_period` primitive
    used everywhere else, using only Core PCE's own observations.
    Confirmation always compares both series at the exact same period
    (`latest_common_period`); never a mismatched-month pair.
    """
    primary_index = build_index(primary_observations)
    confirmation_index = build_index(confirmation_observations)

    confirmation_latest = compute_series_momentum(confirmation_observations, CONFIRMATION_SERIES_ID, neutral_band_pp)

    latest_common_period = find_latest_common_period(primary_index, confirmation_index)
    if latest_common_period is None:
        return ConfirmationResult(
            confirmation_latest=confirmation_latest,
            primary_at_comparison_period=None,
            confirmation_at_comparison_period=None,
            latest_common_period=None,
            relationship="UNAVAILABLE",
        )

    primary_latest_observation_period = latest_observation_date(primary_observations)
    primary_latest_valid_state_period = find_latest_valid_state_period(primary_index)
    confirmation_latest_observation_period = latest_observation_date(confirmation_observations)
    confirmation_latest_valid_state_period = find_latest_valid_state_period(confirmation_index)

    primary_at_comparison = classify_period(
        primary_index,
        PRIMARY_SERIES_ID,
        latest_common_period,
        primary_latest_observation_period,
        primary_latest_valid_state_period,
        neutral_band_pp,
    )
    confirmation_at_comparison = classify_period(
        confirmation_index,
        CONFIRMATION_SERIES_ID,
        latest_common_period,
        confirmation_latest_observation_period,
        confirmation_latest_valid_state_period,
        neutral_band_pp,
    )

    relationship = classify_confirmation_relationship(primary_at_comparison.state, confirmation_at_comparison.state)

    return ConfirmationResult(
        confirmation_latest=confirmation_latest,
        primary_at_comparison_period=primary_at_comparison,
        confirmation_at_comparison_period=confirmation_at_comparison,
        latest_common_period=latest_common_period,
        relationship=relationship,
    )


def compute_confirmation_at(
    primary_observations: list[Observation],
    confirmation_observations: list[Observation],
    calculation_period: date | None,
    neutral_band_pp: float = NEUTRAL_BAND_PP,
) -> tuple[SeriesMomentumResult, SeriesMomentumResult, ConfirmationRelationship]:
    """Core PCE's and Core CPI's canonical momentum, both at the exact
    SAME explicit `calculation_period`, plus the resulting relationship
    -- the primitive `inflation_what_changed_v1.0`'s confirmation
    section needs. Never a mismatched pair: both `classify_period`
    calls (via `compute_series_momentum_at`) receive the identical
    `calculation_period`. This function does not select which period
    to evaluate -- normally the caller supplies
    `latest_shared_observation_period(...)` or the exact calendar month
    before it; `calculation_period=None` (no shared anchor at all)
    propagates straight through to two `INSUFFICIENT_DATA` results and
    an `UNAVAILABLE` relationship, via the same primitives used
    everywhere else -- no special-casing needed here."""
    primary_state = compute_series_momentum_at(primary_observations, PRIMARY_SERIES_ID, calculation_period, neutral_band_pp)
    confirmation_state = compute_series_momentum_at(
        confirmation_observations, CONFIRMATION_SERIES_ID, calculation_period, neutral_band_pp
    )
    relationship = classify_confirmation_relationship(primary_state.state, confirmation_state.state)
    return primary_state, confirmation_state, relationship


def _build_target_result(
    index: dict[date, float],
    period: date | None,
    fed_objective_percent: float,
) -> TargetResult:
    """Shared assembly for `compute_target`/`compute_target_at`: given
    an index and an ALREADY-DECIDED period (found by search, or
    supplied explicitly by a caller), build the `TargetResult`.
    `period=None` yields an unavailable result directly -- never
    fabricates a period to anchor to. Factored out so the target-gap
    formula (`headline_pce_yoy - fed_objective_percent`) and evidence
    construction exist in exactly one place, regardless of which
    period-selection strategy chose `period`."""
    if period is None:
        return TargetResult(
            calculation_period=None,
            headline_pce_yoy=None,
            fed_objective_percent=fed_objective_percent,
            target_gap_pp=None,
            available=False,
            evidence=None,
        )

    evidence = _metric_evidence(index, TARGET_SERIES_ID, period, 12, "12m")
    headline_pce_yoy = evidence.value
    target_gap_pp = headline_pce_yoy - fed_objective_percent if headline_pce_yoy is not None else None

    return TargetResult(
        calculation_period=period,
        headline_pce_yoy=headline_pce_yoy,
        fed_objective_percent=fed_objective_percent,
        target_gap_pp=target_gap_pp,
        available=headline_pce_yoy is not None,
        evidence=evidence,
    )


def compute_target(
    observations: list[Observation],
    fed_objective_percent: float = FED_OBJECTIVE_PERCENT,
) -> TargetResult:
    """Headline PCE YoY vs. the Fed's longer-run objective, at the
    LATEST period for which `r_12m` is calculable. No categorical
    target state -- the numeric gap is the canonical target-relative
    output. `available=False`/nulls if `r_12m` cannot be calculated at
    any period in the supported history; never substitutes CPI."""
    index = build_index(observations)
    period = find_latest_period_with_valid_12m(index)
    return _build_target_result(index, period, fed_objective_percent)


def compute_target_at(
    observations: list[Observation],
    calculation_period: date | None,
    fed_objective_percent: float = FED_OBJECTIVE_PERCENT,
) -> TargetResult:
    """Target evidence at an EXPLICIT `calculation_period` -- never
    searched for. The primitive `inflation_what_changed_v1.0`'s target
    and headline-PCE sections need (as opposed to `compute_target`'s
    "latest valid" search, which the Monitor uses).
    `calculation_period=None` yields an unavailable result directly,
    via the same `_build_target_result` assembly `compute_target` uses
    -- no duplicated target-gap formula."""
    index = build_index(observations)
    return _build_target_result(index, calculation_period, fed_objective_percent)


def compute_headline_context(
    headline_pce_observations: list[Observation],
    headline_cpi_observations: list[Observation],
    neutral_band_pp: float = NEUTRAL_BAND_PP,
) -> HeadlineContextResult:
    """Headline PCE and Headline CPI, each independently classified by
    the same methodology as Core PCE/Core CPI. No aggregate
    headline-context state and no majority vote -- deliberately just
    two independent results."""
    return HeadlineContextResult(
        headline_pce=compute_series_momentum(headline_pce_observations, TARGET_SERIES_ID, neutral_band_pp),
        headline_cpi=compute_series_momentum(headline_cpi_observations, HEADLINE_CPI_SERIES_ID, neutral_band_pp),
    )


# ---------------------------------------------------------------------
# What Changed period selection + exact-period construction
# (inflation_what_changed_v1.0 -- docs/methodology/inflation-what-changed-v1.0.md)
#
# These combine period SELECTION (this contract's own, e.g.
# latest_observation_period / latest_shared_observation_period) with
# exact-period EVALUATION (inflation_v1.0's existing, unmodified
# primitives above) -- both legitimately belong to the inflation
# methodology/construction layer per the frozen What Changed contract,
# which explicitly reserves "zero formula knowledge" for the separate
# pure comparator (app.domain.inflation_what_changed) alone. Nothing
# below is reused by, or changes the behavior of, inflation_v1.0's own
# "latest" functions above.
# ---------------------------------------------------------------------


def month_over_month_series_momentum(
    observations: list[Observation],
    series_id: str,
    neutral_band_pp: float = NEUTRAL_BAND_PP,
) -> tuple[date | None, date | None, SeriesMomentumResult | None, SeriesMomentumResult | None]:
    """The exact period pair + exact-period evidence
    `inflation_what_changed_v1.0` needs for one ordinary series
    (primary momentum, headline PCE, or headline CPI):
    `current_period` = this series' own `latest_observation_period`
    (a row exists, regardless of validity -- never
    `latest_valid_state_period`); `previous_period` = the exact
    calendar month before it, never searched. Returns
    `(previous_period, current_period, previous_evidence,
    current_evidence)` -- all four `None` only when the series has no
    observation at all."""
    current_period = latest_observation_date(observations)
    if current_period is None:
        return None, None, None, None
    previous_period = month_before(current_period, 1)
    previous_evidence = compute_series_momentum_at(observations, series_id, previous_period, neutral_band_pp)
    current_evidence = compute_series_momentum_at(observations, series_id, current_period, neutral_band_pp)
    return previous_period, current_period, previous_evidence, current_evidence


def month_over_month_target(
    observations: list[Observation],
    fed_objective_percent: float = FED_OBJECTIVE_PERCENT,
) -> tuple[date | None, date | None, TargetResult | None, TargetResult | None]:
    """The exact period pair + exact-period evidence
    `inflation_what_changed_v1.0`'s target section needs.
    `current_period` = Headline PCE's own `latest_observation_period`;
    `previous_period` = the exact calendar month before it, never
    searched."""
    current_period = latest_observation_date(observations)
    if current_period is None:
        return None, None, None, None
    previous_period = month_before(current_period, 1)
    previous_evidence = compute_target_at(observations, previous_period, fed_objective_percent)
    current_evidence = compute_target_at(observations, current_period, fed_objective_percent)
    return previous_period, current_period, previous_evidence, current_evidence


def month_over_month_confirmation(
    primary_observations: list[Observation],
    confirmation_observations: list[Observation],
    neutral_band_pp: float = NEUTRAL_BAND_PP,
) -> tuple[
    date | None,
    date | None,
    SeriesMomentumResult | None,
    SeriesMomentumResult | None,
    ConfirmationRelationship | None,
    SeriesMomentumResult | None,
    SeriesMomentumResult | None,
    ConfirmationRelationship | None,
]:
    """The exact period pair + exact-period evidence
    `inflation_what_changed_v1.0`'s confirmation section needs.
    `current_confirmation_period` = `latest_shared_observation_period`
    (defined above -- NEVER `inflation_v1.0`'s own
    `latest_common_period`); `previous_confirmation_period` = the exact
    calendar month before it, never searched. Returns
    `(previous_period, current_period, previous_primary_state,
    previous_confirmation_state, previous_relationship,
    current_primary_state, current_confirmation_state,
    current_relationship)` -- all eight `None` only when Core PCE and
    Core CPI share no observation date anywhere in history."""
    current_period = latest_shared_observation_period(primary_observations, confirmation_observations)
    if current_period is None:
        return None, None, None, None, None, None, None, None
    previous_period = month_before(current_period, 1)
    previous_primary, previous_confirmation, previous_relationship = compute_confirmation_at(
        primary_observations, confirmation_observations, previous_period, neutral_band_pp
    )
    current_primary, current_confirmation, current_relationship = compute_confirmation_at(
        primary_observations, confirmation_observations, current_period, neutral_band_pp
    )
    return (
        previous_period,
        current_period,
        previous_primary,
        previous_confirmation,
        previous_relationship,
        current_primary,
        current_confirmation,
        current_relationship,
    )


def compute_inflation_monitor_result(
    primary_observations: list[Observation],
    confirmation_observations: list[Observation],
    target_observations: list[Observation],
    headline_cpi_observations: list[Observation],
    neutral_band_pp: float = NEUTRAL_BAND_PP,
    fed_objective_percent: float = FED_OBJECTIVE_PERCENT,
) -> InflationMonitorResult:
    """Assemble the complete canonical `inflation_v1.0` result from four
    independently-supplied observation lists. `target_observations` and
    `headline_pce_observations` are the same series (`PCEPI`) serving
    two distinct roles (target level vs. headline momentum context, per
    the frozen hierarchy) -- callers pass the same list for both; this
    function never fetches or infers data on its own.

    Pure: no session, no HTTP, no environment access. Given the same
    four observation lists and the same two parameters, always returns
    a result with identical numbers, states, periods, and relationship
    -- run twice, byte-for-byte reproducible after serialization.
    """
    underlying_momentum = compute_series_momentum(primary_observations, PRIMARY_SERIES_ID, neutral_band_pp)
    confirmation = compute_confirmation(primary_observations, confirmation_observations, neutral_band_pp)
    target = compute_target(target_observations, fed_objective_percent)
    headline_context = compute_headline_context(target_observations, headline_cpi_observations, neutral_band_pp)

    coverage = InflationCoverage(
        primary_available=underlying_momentum.state != "INSUFFICIENT_DATA",
        # The confirmation TIER's canonical output is the same-period
        # Core PCE/Core CPI relationship, not Core CPI's own standalone
        # state -- confirmation_available must track whether THAT
        # relationship is calculable, not merely whether Core CPI alone
        # has a valid latest state (Core CPI's own standalone
        # availability is preserved separately, unabridged, in
        # confirmation.confirmation_latest.state).
        confirmation_available=confirmation.relationship != "UNAVAILABLE",
        target_available=target.available,
        headline_cpi_available=headline_context.headline_cpi.state != "INSUFFICIENT_DATA",
    )

    data_through_candidates = (
        underlying_momentum.latest_observation_period,
        confirmation.confirmation_latest.latest_observation_period,
        headline_context.headline_pce.latest_observation_period,
        headline_context.headline_cpi.latest_observation_period,
    )
    data_through = max((d for d in data_through_candidates if d is not None), default=None)

    periods = InflationPeriods(
        latest_common_period=confirmation.latest_common_period,
        data_through=data_through,
    )

    return InflationMonitorResult(
        target=target,
        underlying_momentum=underlying_momentum,
        confirmation=confirmation,
        headline_context=headline_context,
        periods=periods,
        coverage=coverage,
    )
