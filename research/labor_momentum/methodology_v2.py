"""Redesigned PAYEMS (payroll) methodology candidates for Increment
#20A.2, following #20A.1's finding that the original
`employment_momentum` formula (see `methodology.py`) has two confirmed
structural defects: it is not sign-aware, and its rolling 12-month
baseline is contaminated by extreme shock months for well over a year
afterward.

Isolated research code, same discipline as `methodology.py`: imports
nothing from `app/`, nothing in `app/` imports this.

UNITS (read this before touching any function below): every function
in this module operates on a PAYEMS index expressed in ACTUAL PERSONS
(not FRED's native "Thousands of Persons"), built by
`build_payems_persons_index` below -- the ONE place the ×1,000
conversion happens, with an assertion guard against ever feeding it an
already-converted or wrongly-scaled index. This is a deliberate,
permanent departure from `methodology.py`'s own convention (which
keeps #20A.1's original, already-validated functions on PAYEMS's
native thousands-of-persons unit, unchanged, so #20A.1's results stay
exactly reproducible) -- #20A.1 caught a real units bug from exactly
this kind of ambiguity, and converting once, at the loading boundary,
to whole persons removes the ambiguity class entirely rather than
merely fixing one call site. Every threshold name in this module
carries `_jobs` explicitly (e.g. `condition_deadband_jobs`) to make a
future native-vs-converted mix-up structurally harder to write by
accident.

`monthly_change`/`average_monthly_change`/`month_before` are reused
directly from `methodology.py` unmodified -- they are pure arithmetic
over whatever index dict they are given, with no unit assumption
baked in, so they are correct here as long as this module's own
CALLERS only ever pass them the persons-unit index built below.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date
from typing import Literal

from research.labor_momentum.methodology import (
    Observation,
    UnemploymentTrendState,
    average_monthly_change,
    month_before,
)

PAYEMS_PERSONS_PER_NATIVE_UNIT = 1000

EmploymentCondition = Literal["EXPANDING", "FLAT", "CONTRACTING", "INSUFFICIENT_DATA"]
EmploymentMomentum = Literal["IMPROVING", "STEADY", "WORSENING", "INSUFFICIENT_DATA"]
EmploymentState = Literal["EXPANDING", "COOLING", "STABLE", "CONTRACTING", "RECOVERING", "INSUFFICIENT_DATA"]
LaborState = Literal["STRENGTHENING", "COOLING", "STABLE", "MIXED", "INSUFFICIENT_DATA"]


def build_payems_persons_index(observations: list[Observation]) -> dict[Date, float]:
    """The ONE conversion point: FRED's native "Thousands of Persons"
    -> actual persons. Every value that survives this function is
    guaranteed (by the assertion below) to be in the hundred-million
    range real U.S. total nonfarm employment actually occupies -- a
    caller that accidentally passed already-converted or wrongly-
    scaled data will fail loudly here, not silently produce a
    100,000x-off tolerance comparison the way #20A.1's own first run
    did."""
    index: dict[Date, float] = {}
    for o in observations:
        if o.value is None:
            continue
        persons = o.value * PAYEMS_PERSONS_PER_NATIVE_UNIT
        # Bounds deliberately loose (covers PAYEMS's full published
        # history, 1939's ~30M through 2026's ~159M) -- this is a
        # units-mixup guard (catches an un-converted native-thousands
        # value, ~30K-~159K, or an accidental double conversion, tens
        # of billions), not a precise range check.
        assert 10_000_000 <= persons <= 400_000_000, (
            f"PAYEMS value {o.value!r} at {o.date} converts to {persons:,.0f} persons, "
            "outside the plausible U.S. total-nonfarm-employment range -- "
            "check for a units mix-up before trusting this index."
        )
        index[o.date] = persons
    return index


# ---------------------------------------------------------------------
# Condition / momentum classification (shared by both candidates)
# ---------------------------------------------------------------------


def classify_condition(value: float | None, deadband_jobs: float) -> EmploymentCondition:
    if value is None:
        return "INSUFFICIENT_DATA"
    if value > deadband_jobs:
        return "EXPANDING"
    if value < -deadband_jobs:
        return "CONTRACTING"
    return "FLAT"


def classify_momentum(recent: float | None, older: float | None, deadband_jobs: float) -> EmploymentMomentum:
    """`recent`/`older` are both already-computed average monthly
    changes (in persons/month) -- this function only compares them.
    IMPROVING means the trend got better regardless of condition's own
    sign (faster growth OR slower contraction); WORSENING is the
    symmetric opposite. Deliberately NOT "ACCELERATING"/"DECELERATING"
    -- those words read as implicitly positive-direction-only in
    ordinary usage, which would be exactly the kind of ambiguous
    labeling #20A.1 was built to catch (see this module's own
    docstring and METHODOLOGY_REDESIGN.md's "Vocabulary" section)."""
    if recent is None or older is None:
        return "INSUFFICIENT_DATA"
    diff = recent - older
    if diff > deadband_jobs:
        return "IMPROVING"
    if diff < -deadband_jobs:
        return "WORSENING"
    return "STEADY"


# Explicit, small, full truth table -- 3x3 plus INSUFFICIENT_DATA
# propagation, never a formula/heuristic computed inline. FLAT
# collapses every momentum value to STABLE: momentum evidence is still
# reported (see EmploymentResult below), but a v1 state label doesn't
# further subdivide "moving sideways" by its own second derivative --
# deliberately avoiding the "too many states" trap named in the
# #20A.2 brief.
_CONDITION_MOMENTUM_TABLE: dict[tuple[EmploymentCondition, EmploymentMomentum], EmploymentState] = {
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
    return _CONDITION_MOMENTUM_TABLE[(condition, momentum)]


@dataclass(frozen=True)
class EmploymentResult:
    period: Date
    candidate: str
    condition_value: float | None  # persons/month, the value condition was judged on
    momentum_recent: float | None  # persons/month
    momentum_older: float | None  # persons/month
    condition: EmploymentCondition
    momentum: EmploymentMomentum
    state: EmploymentState


# ---------------------------------------------------------------------
# Candidate A -- recent 3M vs recent 6M (overlapping windows)
# ---------------------------------------------------------------------


def evaluate_candidate_a(
    index: dict[Date, float], t: Date, condition_deadband_jobs: float, momentum_deadband_jobs: float
) -> EmploymentResult:
    recent_3m = average_monthly_change(index, t, 3)
    recent_6m = average_monthly_change(index, t, 6)
    condition = classify_condition(recent_3m, condition_deadband_jobs)
    momentum = classify_momentum(recent_3m, recent_6m, momentum_deadband_jobs)
    state = combine_employment_state(condition, momentum)
    return EmploymentResult(t, "A", recent_3m, recent_3m, recent_6m, condition, momentum, state)


# ---------------------------------------------------------------------
# Candidate B -- current 3M vs prior 3M (non-overlapping windows)
# ---------------------------------------------------------------------


def evaluate_candidate_b(
    index: dict[Date, float], t: Date, condition_deadband_jobs: float, momentum_deadband_jobs: float
) -> EmploymentResult:
    current_3m = average_monthly_change(index, t, 3)
    prior_3m = average_monthly_change(index, month_before(t, 3), 3)
    condition = classify_condition(current_3m, condition_deadband_jobs)
    momentum = classify_momentum(current_3m, prior_3m, momentum_deadband_jobs)
    state = combine_employment_state(condition, momentum)
    return EmploymentResult(t, "B", current_3m, current_3m, prior_3m, condition, momentum, state)


# ---------------------------------------------------------------------
# Top-level Labor state -- Architecture 1 (condition+momentum already
# collapsed into EmploymentState; this table only combines the two
# OWNERS' states, mirroring #20A's original philosophy exactly: only
# a clean, unambiguous agreement earns a clean top-level label).
# ---------------------------------------------------------------------

_LABOR_AGREEMENT_TABLE: dict[tuple[EmploymentState, UnemploymentTrendState], LaborState] = {
    ("EXPANDING", "IMPROVING"): "STRENGTHENING",
    ("COOLING", "DETERIORATING"): "COOLING",
    ("CONTRACTING", "DETERIORATING"): "COOLING",
    ("STABLE", "STABLE"): "STABLE",
}


def combine_labor_state(employment_state: EmploymentState, unemployment_state: UnemploymentTrendState) -> LaborState:
    if employment_state == "INSUFFICIENT_DATA" or unemployment_state == "INSUFFICIENT_DATA":
        return "INSUFFICIENT_DATA"
    return _LABOR_AGREEMENT_TABLE.get((employment_state, unemployment_state), "MIXED")
