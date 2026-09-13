"""Response contracts for economic series discovery.

This is the DISCOVERY PLANE ("what series exist"), deliberately distinct
from `app/models/series.py`/`app/models/analysis.py`'s ANALYSIS PLANE
("what does the persisted data say"). A `SeriesCandidate` is never
invented from a search query's text -- every one originates from either
persisted PostgreSQL metadata or an actual FRED catalog search response
(see `app.services.discovery.SeriesDiscoveryService`).
"""

from typing import Literal

from pydantic import BaseModel

DiscoverySource = Literal["local", "fred", "local_and_fred"]


class SeriesCandidate(BaseModel):
    """One verified candidate series.

    `persisted=True` means the series currently exists in our local
    canonical PostgreSQL persistence and is therefore available to
    persisted-data analytics; `persisted=False` means it's a verified
    catalog metadata candidate -- a real series found via FRED's
    catalog -- that has not been synced into local persistence, so it
    isn't yet available for analytics against persisted data (see
    `app.services.discovery`, which never auto-syncs a discovered
    series).

    `units`/`frequency`/`seasonal_adjustment`/`observation_start`/
    `observation_end`/`popularity` are `None` when unavailable -- `units`
    is the one of these `EconomicSeries` actually persists (see
    `app/db/models.py`); the rest simply aren't columns in our local
    schema. Any of them is filled in when the same series was also found
    via FRED search.
    """

    series_id: str
    title: str
    units: str | None = None
    frequency: str | None = None
    seasonal_adjustment: str | None = None
    observation_start: str | None = None
    observation_end: str | None = None
    popularity: int | None = None
    persisted: bool
    discovery_source: DiscoverySource


class SeriesSearchResponse(BaseModel):
    """Result of a series discovery search.

    `external_search_available=False` means FRED catalog search failed or
    was unreachable for this call -- `candidates` still reflects whatever
    local results were found; this is graceful degradation, not an error
    (see `app.services.discovery.SeriesDiscoveryService.search`).
    """

    query: str
    candidates: list[SeriesCandidate]
    external_search_available: bool
