"""Our application's public data contract for economic data series.

Deliberately decoupled from FRED's raw response shape.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel


class Observation(BaseModel):
    date: date
    value: float | None  # None represents a missing/unreported observation


class SeriesIdentity(BaseModel):
    """Who a list of observations actually is (Increment #38, ADR-034).

    Before #38 this did not exist, and the consequence was a latent
    provenance lie: `Observation` carries only a date and a value, so a
    methodology stamped its evidence from a module-level constant
    (`series_id=PAYEMS_SERIES_ID`). Had the provider changed, the
    observations would have flowed through unchanged -- they are only
    dates and values -- and the evidence would have gone on naming
    `PAYEMS` for numbers BLS supplied.

    So identity travels WITH the data now, resolved from the persisted
    series row rather than from whatever constant the calling module
    happens to know. All three fields are read from storage:

    - `concept_id`     what MacroChipz means (source-neutral, stable)
    - `provider`       who actually supplied THIS observation
    - `provider_series_id`  their identifier for it

    Carrying all three is what makes a provider cutover honest: old
    observations keep naming the provider that produced them while
    sharing a concept with the new ones (ADR-034, Invariant D).

    One identity describes one list of observations, not one
    observation -- every value in a canonical series comes from the same
    persisted series row, so per-observation repetition would be noise.
    """

    concept_id: str
    provider: str
    provider_series_id: str


class SeriesSummary(BaseModel):
    """A series' identifying metadata, with no observations attached.

    Used where series metadata needs to appear as a *nested* value (e.g.
    `series_a`/`series_b` in a comparison response) rather than as the
    top-level fields `SeriesResponse` reuses via inheritance -- inheritance
    doesn't help when the metadata needs to be embedded as its own object.
    """

    series_id: str
    title: str
    units: str
    source: str = "FRED"


class SeriesResponse(BaseModel):
    series_id: str
    title: str
    units: str
    source: str = "FRED"
    observations: list[Observation]


class PaginationMeta(BaseModel):
    limit: int
    offset: int
    returned: int
    total: int


class SeriesObservationsResponse(SeriesResponse):
    """Response contract for a paginated historical observations query.

    Extends `SeriesResponse` (reusing its fields) with pagination metadata,
    rather than duplicating series_id/title/units/source/observations.
    """

    pagination: PaginationMeta


TransformationType = Literal["absolute_change", "percent_change", "moving_average"]


class TransformedObservation(BaseModel):
    """One dated point of a derived series: the source value alongside
    the computed transformed value (null where the transformation engine
    could not compute one -- see app.domain.transformations)."""

    date: date
    original_value: float | None
    value: float | None


class TransformationMeta(BaseModel):
    type: TransformationType
    window: int | None = None


class SeriesTransformResponse(BaseModel):
    """Response contract for GET /series/{series_id}/transform.

    Not built on SeriesResponse: its `observations` are TransformedObservation
    (original_value + value), a genuinely different shape from SeriesResponse's
    plain Observation, so overriding that field via inheritance would be
    more confusing than reusing it. series_id/title/units/source are
    duplicated here as plain fields rather than restructuring the existing
    models to share a common base.
    """

    series_id: str
    title: str
    units: str
    source: str = "FRED"
    transformation: TransformationMeta
    observations: list[TransformedObservation]
