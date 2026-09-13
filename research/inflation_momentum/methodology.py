"""Deterministic transformation and candidate-methodology functions for
the Inflation Momentum Methodology Study.

Isolated research code: imports nothing from `app/`, and nothing in
`app/` imports this module (enforced by
tests/research/test_inflation_momentum.py's architectural guard). This
module recomputes annualized-rate math independently rather than reusing
`app.domain.transformations` deliberately -- this study's exact formula
(compounded annualization, `((P_t / P_(t-n)) ** (12/n) - 1) * 100`) is
not what `app.domain.transformations.percent_change` computes (a plain
period-over-period percent change, not annualized), and the research
brief is explicit: build isolated research helpers rather than alter or
overload a production function to serve a research-specific formula.

All functions here are pure: given the same input list, they return the
same output, always. Dates are sorted explicitly wherever a list is
consumed instead of relying on input order (Reproducibility, Section 14
of the research brief).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date as Date
from pathlib import Path
from typing import Literal

DATA_DIR = Path(__file__).resolve().parent / "data"

CandidateAState = Literal["COOLING", "HEATING", "STABLE"]
CandidateBState = Literal["COOLING", "HEATING", "MIXED_OR_STABLE"]
CandidateBExplicitState = Literal["COOLING", "HEATING", "STABLE", "MIXED", "INSUFFICIENT_DATA"]
CandidateCState = Literal["COOLING", "HEATING", "MIXED"]
CandidateDState = Literal["ACCELERATING", "DECELERATING", "FLAT"]

HorizonBucket = Literal["below", "in", "above"]


@dataclass(frozen=True)
class Observation:
    date: Date
    value: float | None  # None = missing (FRED's "." or a genuine gap)


@dataclass(frozen=True)
class TransformedRow:
    """One month's index level plus every annualized-rate transformation
    computable from it, given enough history. `None` means "not
    computable" (insufficient history or a missing input value) --
    never approximated, never imputed."""

    date: Date
    level: float | None
    chg_1m_ann: float | None
    chg_3m_ann: float | None
    chg_6m_ann: float | None
    chg_12m_yoy: float | None


def load_series(series_id: str) -> list[Observation]:
    """Load one series' cached observations (see fetch_data.py),
    parsing FRED's "." missing-value marker to None, and sorting
    explicitly by date -- never trusting file order."""
    path = DATA_DIR / f"{series_id}.json"
    raw = json.loads(path.read_text())
    observations = [
        Observation(date=Date.fromisoformat(o["date"]), value=None if o["value"] == "." else float(o["value"]))
        for o in raw["observations"]
    ]
    return sorted(observations, key=lambda o: o.date)


def load_series_metadata(series_id: str) -> dict:
    path = DATA_DIR / f"{series_id}.json"
    raw = json.loads(path.read_text())
    return {k: v for k, v in raw.items() if k != "observations"}


def annualized_change(current: float | None, past: float | None, n_months: int) -> float | None:
    """`((current / past) ** (12 / n_months) - 1) * 100`.

    None (never NaN, never a substituted 0, never an approximation) if
    either input is missing, or `past` is not strictly positive (a
    price index is never legitimately <= 0; guards a hypothetical
    malformed input rather than raising).
    """
    if current is None or past is None or past <= 0:
        return None
    return ((current / past) ** (12 / n_months) - 1) * 100


def compute_transformations(observations: list[Observation]) -> list[TransformedRow]:
    """One TransformedRow per input observation, in the same
    (explicitly sorted) chronological order. A transformation at index
    `i` uses `observations[i - n]` as its base; `None` when that index
    doesn't exist or either endpoint's value is missing."""
    ordered = sorted(observations, key=lambda o: o.date)
    rows: list[TransformedRow] = []
    for i, obs in enumerate(ordered):
        def _lookback(n: int) -> float | None:
            if i - n < 0:
                return None
            return annualized_change(obs.value, ordered[i - n].value, n)

        rows.append(
            TransformedRow(
                date=obs.date,
                level=obs.value,
                chg_1m_ann=_lookback(1),
                chg_3m_ann=_lookback(3),
                chg_6m_ann=_lookback(6),
                chg_12m_yoy=_lookback(12),
            )
        )
    return rows


# ---------------------------------------------------------------------
# Candidate A: Recent vs Trailing (3M annualized vs 12M)
# ---------------------------------------------------------------------


def classify_candidate_a(row: TransformedRow, delta: float) -> CandidateAState | None:
    if row.chg_3m_ann is None or row.chg_12m_yoy is None:
        return None
    if row.chg_3m_ann < row.chg_12m_yoy - delta:
        return "COOLING"
    if row.chg_3m_ann > row.chg_12m_yoy + delta:
        return "HEATING"
    return "STABLE"


# ---------------------------------------------------------------------
# Candidate B: Dual Confirmation (3M AND 6M vs 12M)
# ---------------------------------------------------------------------


def classify_candidate_b(row: TransformedRow, delta: float) -> CandidateBState | None:
    if row.chg_3m_ann is None or row.chg_6m_ann is None or row.chg_12m_yoy is None:
        return None
    cooling = row.chg_3m_ann < row.chg_12m_yoy - delta and row.chg_6m_ann < row.chg_12m_yoy - delta
    heating = row.chg_3m_ann > row.chg_12m_yoy + delta and row.chg_6m_ann > row.chg_12m_yoy + delta
    if cooling:
        return "COOLING"
    if heating:
        return "HEATING"
    return "MIXED_OR_STABLE"


def _horizon_bucket(value: float, center: float, delta: float) -> HorizonBucket:
    """Which of three, mutually exclusive, jointly exhaustive buckets a
    single horizon's annualized rate falls into relative to `center`
    (the 12M rate) and the neutral band `delta`:

        below:  value <  center - delta            (strict)
        in:     center - delta <= value <= center + delta   (closed/inclusive on both ends)
        above:  value >  center + delta            (strict)

    Every real number falls into exactly one bucket -- there is no gap
    and no overlap between "below"/"in" or "in"/"above": the boundary
    value `center - delta` itself is "in" (not "below"), and
    `center + delta` itself is "in" (not "above"). This is the exact
    operator choice Section 4/8 of the finalist-analysis brief requires
    to be unambiguous.
    """
    if value < center - delta:
        return "below"
    if value > center + delta:
        return "above"
    return "in"


def classify_candidate_b_explicit(row: TransformedRow, delta: float) -> CandidateBExplicitState:
    """The explicit five-state split of Candidate B evaluated in the
    finalist analysis (COOLING / HEATING / STABLE / MIXED /
    INSUFFICIENT_DATA), as an alternative to the original study's single
    MIXED_OR_STABLE bucket. Additive: `classify_candidate_b` above is
    unchanged, so the original study's outputs remain byte-identical to
    a re-run.

    Built from the same `_horizon_bucket` classification applied
    independently to 3M and 6M against the 12M center:

        COOLING            : 3M bucket == "below" AND 6M bucket == "below"
        HEATING            : 3M bucket == "above" AND 6M bucket == "above"
        STABLE             : 3M bucket == "in"    AND 6M bucket == "in"
        MIXED              : any other combination of two buckets
                              (sufficient data exists, but the two
                              horizons neither jointly confirm a
                              direction nor jointly sit inside the band)
        INSUFFICIENT_DATA  : 3M, 6M, or 12M is unavailable

    Never returns `None` -- `INSUFFICIENT_DATA` is itself a state here,
    unlike every other candidate in this module, precisely so the
    finalist analysis can measure its own frequency as a first-class
    percentage rather than an implicit "missing" that could be
    conflated with the classified states in a chart or a naive average.
    """
    if row.chg_3m_ann is None or row.chg_6m_ann is None or row.chg_12m_yoy is None:
        return "INSUFFICIENT_DATA"
    bucket_3m = _horizon_bucket(row.chg_3m_ann, row.chg_12m_yoy, delta)
    bucket_6m = _horizon_bucket(row.chg_6m_ann, row.chg_12m_yoy, delta)
    if bucket_3m == "below" and bucket_6m == "below":
        return "COOLING"
    if bucket_3m == "above" and bucket_6m == "above":
        return "HEATING"
    if bucket_3m == "in" and bucket_6m == "in":
        return "STABLE"
    return "MIXED"


# ---------------------------------------------------------------------
# Candidate C: Ordered Momentum (3M < 6M < 12M, or reverse)
# ---------------------------------------------------------------------


def classify_candidate_c(row: TransformedRow, band: float = 0.0) -> CandidateCState | None:
    """`band=0.0` is the base candidate (strict ordering). A positive
    `band` is the explicitly-separated exploratory variant requiring
    each step of the ordering to differ by at least `band` percentage
    points, not just be strictly less/greater."""
    if row.chg_3m_ann is None or row.chg_6m_ann is None or row.chg_12m_yoy is None:
        return None
    if row.chg_3m_ann < row.chg_6m_ann - band and row.chg_6m_ann < row.chg_12m_yoy - band:
        return "COOLING"
    if row.chg_3m_ann > row.chg_6m_ann + band and row.chg_6m_ann > row.chg_12m_yoy + band:
        return "HEATING"
    return "MIXED"


# ---------------------------------------------------------------------
# Candidate D: Change in Recent Momentum (delta of 3M annualized)
# ---------------------------------------------------------------------


def compute_delta_3m(rows: list[TransformedRow]) -> list[float | None]:
    """`3M_annualized(t) - 3M_annualized(t-1)` for each row (None if
    either month's 3M annualized rate is unavailable)."""
    ordered = sorted(rows, key=lambda r: r.date)
    result: list[float | None] = []
    for i, row in enumerate(ordered):
        if i == 0 or row.chg_3m_ann is None or ordered[i - 1].chg_3m_ann is None:
            result.append(None)
        else:
            result.append(row.chg_3m_ann - ordered[i - 1].chg_3m_ann)
    return result


def classify_candidate_d(delta_3m: float | None, flat_band: float = 0.0) -> CandidateDState | None:
    if delta_3m is None:
        return None
    if delta_3m > flat_band:
        return "ACCELERATING"
    if delta_3m < -flat_band:
        return "DECELERATING"
    return "FLAT"


# ---------------------------------------------------------------------
# Common-period alignment
# ---------------------------------------------------------------------


def latest_available_period(observations: list[Observation]) -> Date | None:
    non_missing = [o for o in observations if o.value is not None]
    if not non_missing:
        return None
    return max(o.date for o in non_missing)


def latest_common_period(series_observations: dict[str, list[Observation]]) -> Date | None:
    """The latest date for which EVERY given series has a non-missing
    observation -- never comparing, e.g., July PCE to August CPI as if
    contemporaneous."""
    latest_dates = [latest_available_period(obs) for obs in series_observations.values()]
    if any(d is None for d in latest_dates):
        return None
    return min(latest_dates)  # type: ignore[arg-type]
