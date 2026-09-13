"""Response contract for cross-series (multi-series) analysis.

Distinct from `app/models/series.py`, which covers single-series
contracts. `SeriesSummary` and `TransformationType`/`TransformationMeta`
are reused from there rather than duplicated.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.series import SeriesSummary, TransformationMeta, TransformationType

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


class TransformationSpec(BaseModel):
    """A requested transformation for one side of a pipeline request.

    Only structural validation lives here (`window`'s numeric bounds,
    applied by Pydantic whenever a value is supplied at all). Whether
    `window` is *required* (moving_average) or *inapplicable* (the other
    two types) is a cross-field rule, not a shape rule -- it's enforced by
    `AnalysisService` raising the same `InvalidWindowError` (-> 400)
    already established for the single-series transform endpoint in
    Increment 005, rather than a second, differently-coded validation
    path for the identical rule.

    `extra="forbid"`: fail-closed validation for this public request
    contract -- an unexpected field is rejected outright with a clear
    validation error, rather than silently dropped.
    """

    model_config = ConfigDict(extra="forbid")

    type: TransformationType
    window: int | None = Field(default=None, ge=2, le=365)


class PipelineSeriesSpec(BaseModel):
    """One side of a pipeline request: which persisted series, and
    optionally what to transform it by before analysis. Absent/null
    `transformation` means "use raw persisted observations".

    `extra="forbid"`: see `TransformationSpec` -- same rationale."""

    model_config = ConfigDict(extra="forbid")

    series_id: str
    transformation: TransformationSpec | None = None


class PipelineRequest(BaseModel):
    """Request body for POST /api/v1/analysis/pipeline.

    `extra="forbid"`: see `TransformationSpec` -- same rationale. A
    legitimate client never needed to send an unrecognized field either,
    so one is rejected outright rather than silently ignored."""

    model_config = ConfigDict(extra="forbid")

    series_a: PipelineSeriesSpec
    series_b: PipelineSeriesSpec
    analysis: AnalysisType
    start_date: date | None = None
    end_date: date | None = None


class PipelineSeriesSummary(SeriesSummary):
    """`SeriesSummary` plus which transformation (if any) was applied to
    this side of a pipeline request -- kept as its own model rather than
    added onto `SeriesSummary` itself, so `GET /analysis/compare`'s
    existing response (which never transforms) doesn't gain an always-null
    field it has no use for."""

    transformation: TransformationMeta | None = None


class PipelineResponse(SeriesComparisonResponse):
    """Response contract for POST /api/v1/analysis/pipeline.

    Reuses everything from `SeriesComparisonResponse` (analysis,
    matching_pairs, usable_pairs, correlation, observations) and narrows
    `series_a`/`series_b` to `PipelineSeriesSummary` so each side can
    report the transformation actually applied to it.
    """

    series_a: PipelineSeriesSummary
    series_b: PipelineSeriesSummary
