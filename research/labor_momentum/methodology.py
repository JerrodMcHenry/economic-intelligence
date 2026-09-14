"""Deterministic transformation and classification functions for the
Labor Momentum Methodology Validation (Increment #20A.1).

Isolated research code: imports nothing from `app/`, and nothing in
`app/` imports this module -- same discipline
`research/inflation_momentum/methodology.py` already established.

Implements EXACTLY the formulas frozen by the #20A.1 prompt itself
(the "EXACT CANDIDATE METHODOLOGY" section), not the #20A audit's own
prose restatement of them, and not reinterpreted or "improved" in any
way. If a genuine structural flaw is found during validation, this
file is not edited to route around it silently -- the finding is
reported instead (see METHODOLOGY_VALIDATION.md).

All functions are pure: same input, same output, every time. No
interpolation, no imputation -- a required exact calendar month
missing from the input index makes the dependent value `None`, never
approximated.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date as Date
from pathlib import Path
from typing import Literal

DATA_DIR = Path(__file__).resolve().parent / "data"

EmploymentMomentumState = Literal["STRENGTHENING", "COOLING", "STABLE", "MIXED", "INSUFFICIENT_DATA"]
UnemploymentTrendState = Literal["IMPROVING", "DETERIORATING", "STABLE", "INSUFFICIENT_DATA"]
LaborState = Literal["STRENGTHENING", "COOLING", "STABLE", "MIXED", "INSUFFICIENT_DATA"]


@dataclass(frozen=True)
class Observation:
    date: Date
    value: float | None  # None = missing (FRED's "." or a genuine gap)


def load_series(series_id: str) -> list[Observation]:
    """Load one series' cached CSV (see fetch_data.py) into a
    date-sorted Observation list. FRED's own missing-value marker "."
    becomes `None` -- never coerced to zero or dropped from the list
    (a missing month is still a real, present-but-unusable row)."""
    path = DATA_DIR / f"{series_id}.csv"
    observations: list[Observation] = []
    with path.open(newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        assert header[1] == series_id, f"unexpected column header {header!r} in {path}"
        for row in reader:
            if not row:
                continue
            date_str, value_str = row[0], row[1]
            # FRED's own missing-value marker is "." in its API
            # payloads; this CSV export instead leaves the cell empty
            # (observed directly in the cached UNRATE data at
            # 2025-10-01, coinciding with a real BLS household-survey
            # collection gap) -- both are treated identically as
            # missing, never coerced to zero.
            value = None if value_str in ("", ".") else float(value_str)
            observations.append(Observation(date=Date.fromisoformat(date_str), value=value))
    return sorted(observations, key=lambda o: o.date)


def build_index(observations: list[Observation]) -> dict[Date, float]:
    """A `{month: value}` map of every OBSERVED, numerically present
    value. A `None`/missing observation is simply excluded, exactly
    `app.domain.inflation.build_index`'s own discipline -- never
    coerced, never left in the map as a value a lookup could mistake
    for present."""
    return {o.date: o.value for o in observations if o.value is not None}


def month_before(period: Date, months_back: int) -> Date:
    """The exact calendar month `months_back` months before `period`,
    both normalized to day 1 -- identical arithmetic to
    `app.domain.inflation.month_before`, reimplemented here rather
    than imported (isolated research code, see this module's own
    docstring)."""
    total_months = period.year * 12 + (period.month - 1) - months_back
    year, month0 = divmod(total_months, 12)
    return Date(year, month0 + 1, 1)


# ---------------------------------------------------------------------
# Employment momentum (PAYEMS)
# ---------------------------------------------------------------------


def monthly_change(index: dict[Date, float], t: Date) -> float | None:
    """PAYEMS[t] - PAYEMS[t-1]. `None` if either exact calendar month
    is missing from the index."""
    current = index.get(t)
    past = index.get(month_before(t, 1))
    if current is None or past is None:
        return None
    return current - past


def average_monthly_change(index: dict[Date, float], t: Date, n_months: int) -> float | None:
    """The average of `monthly_change` over the `n_months` calendar
    months ending at (and including) `t` -- e.g. n_months=3 averages
    monthly_change(t), monthly_change(t-1), monthly_change(t-2),
    requiring exactly n_months+1 consecutive index entries
    (t through t-n_months). `None` if ANY of the n_months monthly
    changes in the window is unavailable -- never averaged over a
    partial window."""
    changes: list[float] = []
    for offset in range(n_months):
        month = month_before(t, offset)
        change = monthly_change(index, month)
        if change is None:
            return None
        changes.append(change)
    return sum(changes) / len(changes)


@dataclass(frozen=True)
class EmploymentMomentumResult:
    period: Date
    avg_3m: float | None
    avg_6m: float | None
    avg_12m: float | None
    lower_boundary: float | None
    upper_boundary: float | None
    state: EmploymentMomentumState


def classify_employment_momentum(index: dict[Date, float], t: Date, delta_payroll: float) -> EmploymentMomentumResult:
    avg_3m = average_monthly_change(index, t, 3)
    avg_6m = average_monthly_change(index, t, 6)
    avg_12m = average_monthly_change(index, t, 12)

    if avg_3m is None or avg_6m is None or avg_12m is None:
        return EmploymentMomentumResult(t, avg_3m, avg_6m, avg_12m, None, None, "INSUFFICIENT_DATA")

    lower = avg_12m - delta_payroll
    upper = avg_12m + delta_payroll

    if avg_3m < lower and avg_6m < lower:
        state: EmploymentMomentumState = "COOLING"
    elif avg_3m > upper and avg_6m > upper:
        state = "STRENGTHENING"
    elif lower <= avg_3m <= upper and lower <= avg_6m <= upper:
        state = "STABLE"
    else:
        state = "MIXED"

    return EmploymentMomentumResult(t, avg_3m, avg_6m, avg_12m, lower, upper, state)


# ---------------------------------------------------------------------
# Unemployment trend (UNRATE)
# ---------------------------------------------------------------------


def average_rate(index: dict[Date, float], start: Date, n_months: int) -> float | None:
    """Mean of `index[start], index[start-1], ..., index[start-(n_months-1)]`
    -- `None` if any of those n_months exact calendar months is
    missing."""
    values: list[float] = []
    for offset in range(n_months):
        month = month_before(start, offset)
        value = index.get(month)
        if value is None:
            return None
        values.append(value)
    return sum(values) / len(values)


@dataclass(frozen=True)
class UnemploymentTrendResult:
    period: Date
    current_3m: float | None
    prior_year_3m: float | None
    delta: float | None
    state: UnemploymentTrendState


def classify_unemployment_trend(index: dict[Date, float], t: Date, delta_unemployment: float) -> UnemploymentTrendResult:
    current_3m = average_rate(index, t, 3)
    prior_year_3m = average_rate(index, month_before(t, 12), 3)

    if current_3m is None or prior_year_3m is None:
        return UnemploymentTrendResult(t, current_3m, prior_year_3m, None, "INSUFFICIENT_DATA")

    delta = current_3m - prior_year_3m

    if delta > delta_unemployment:
        state: UnemploymentTrendState = "DETERIORATING"
    elif delta < -delta_unemployment:
        state = "IMPROVING"
    else:
        state = "STABLE"

    return UnemploymentTrendResult(t, current_3m, prior_year_3m, delta, state)


# ---------------------------------------------------------------------
# Top-level combination
# ---------------------------------------------------------------------

_AGREE: dict[tuple[EmploymentMomentumState, UnemploymentTrendState], LaborState] = {
    ("STRENGTHENING", "IMPROVING"): "STRENGTHENING",
    ("COOLING", "DETERIORATING"): "COOLING",
    ("STABLE", "STABLE"): "STABLE",
}


def combine_top_level(employment: EmploymentMomentumResult, unemployment: UnemploymentTrendResult) -> LaborState:
    if employment.state == "INSUFFICIENT_DATA" or unemployment.state == "INSUFFICIENT_DATA":
        return "INSUFFICIENT_DATA"
    return _AGREE.get((employment.state, unemployment.state), "MIXED")


@dataclass(frozen=True)
class LaborMonthResult:
    period: Date
    employment: EmploymentMomentumResult
    unemployment: UnemploymentTrendResult
    state: LaborState


def evaluate_month(
    payems_index: dict[Date, float],
    unrate_index: dict[Date, float],
    t: Date,
    delta_payroll: float,
    delta_unemployment: float,
) -> LaborMonthResult:
    employment = classify_employment_momentum(payems_index, t, delta_payroll)
    unemployment = classify_unemployment_trend(unrate_index, t, delta_unemployment)
    state = combine_top_level(employment, unemployment)
    return LaborMonthResult(t, employment, unemployment, state)


def month_range(start: Date, end: Date) -> list[Date]:
    """Every first-of-month date from `start` through `end`, inclusive,
    both normalized to day 1."""
    months: list[Date] = []
    current = Date(start.year, start.month, 1)
    end_normalized = Date(end.year, end.month, 1)
    while current <= end_normalized:
        months.append(current)
        total = current.year * 12 + (current.month - 1) + 1
        year, month0 = divmod(total, 12)
        current = Date(year, month0 + 1, 1)
    return months
