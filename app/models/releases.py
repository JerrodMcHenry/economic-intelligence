"""Our application's public data contract for the release calendar.

Frozen fields only -- see docs/architecture/release-intelligence-v1.md
#4/#5/#7/#9. `schedule_status` is computed at response time from
`app.domain.releases.classify_schedule_status`; it is never a persisted
column, and this module has no knowledge of how it's derived.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel

ScheduleStatus = Literal["SCHEDULED", "PAST_DUE"]


class ReleaseOccurrenceItem(BaseModel):
    """One release occurrence, with its parent release's curated
    identity inlined -- deliberately flat (no nested `release` object)
    since #17A has exactly one occurrence-shaped list endpoint and
    every consumer needs the release identity alongside the date."""

    release_id: int
    name: str
    provider: str
    provider_release_id: str
    official_url: str | None
    scheduled_date: date
    schedule_status: ScheduleStatus


class PaginationMeta(BaseModel):
    limit: int
    offset: int
    returned: int
    total: int


class ReleaseListResponse(BaseModel):
    releases: list[ReleaseOccurrenceItem]
    pagination: PaginationMeta


class ReleaseSyncSuccess(BaseModel):
    """One curated release whose FRED release-dates call succeeded and
    was upserted. `occurrences_seen` is how many dates the provider
    returned for this release on this sync, not how many were newly
    inserted -- upserts of already-seen occurrences count too, since
    the point is to report what sync actually observed."""

    release_id: int
    name: str
    occurrences_seen: int


class ReleaseSyncFailure(BaseModel):
    """One curated release whose FRED call failed. `error` is always a
    safe, generic message (mirroring the existing FRED failure-mapping
    convention) -- never a raw provider response body, URL, or key."""

    release_id: int
    name: str
    error: str


class ReleaseSyncResponse(BaseModel):
    """Result of one explicit sync run. A release appears in exactly
    one of `synced`/`failed`, never both, never neither -- see
    app.services.releases.ReleaseSyncService."""

    synced: list[ReleaseSyncSuccess]
    failed: list[ReleaseSyncFailure]
