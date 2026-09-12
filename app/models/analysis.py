"""Response contract for cross-series (multi-series) analysis.

Distinct from `app/models/series.py`, which covers single-series
contracts. `SeriesSummary` is reused from there rather than duplicated.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel

from app.models.series import SeriesSummary

AnalysisType = Literal["aligned", "spread", "correlation"]


class ComparisonObservation(BaseModel):
    """One exact-date-matched pair between two series.

    `spread` is populated only for `analysis=spread`; it stays `None` for
    `analysis=aligned` rather than existing as a separate, near-duplicate
    model. `value_a`/`value_b` may themselves be `None` even though the
    *date* matched -- an exact-date match does not guarantee both series
    reported a non-missing value for it.
    """

    date: date
    value_a: float | None
    value_b: float | None
    spread: float | None = None


class SeriesComparisonResponse(BaseModel):
    """Response contract for GET /api/v1/analysis/compare.

    `matching_pairs` counts exact-date matches (regardless of nulls);
    `usable_pairs` counts matches where both values are non-null -- the
    population actually used for `spread`/`correlation` math.
    `observations` holds the per-date pairs for `aligned`/`spread`, and is
    empty for `correlation` (a scalar result), per the response contract.
    """

    series_a: SeriesSummary
    series_b: SeriesSummary
    analysis: AnalysisType
    matching_pairs: int
    usable_pairs: int
    correlation: float | None = None
    observations: list[ComparisonObservation] = []
