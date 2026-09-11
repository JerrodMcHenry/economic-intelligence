"""Our application's public data contract for economic data series.

Deliberately decoupled from FRED's raw response shape.
"""

from datetime import date

from pydantic import BaseModel


class Observation(BaseModel):
    date: date
    value: float | None  # None represents a missing/unreported observation


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
