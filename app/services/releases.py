"""Application/use-case logic for the release calendar.

Deliberately two separate classes rather than one class with an
optional FRED client (the `EconomicDataService` pattern): the frozen
spec requires the read path to be structurally incapable of calling
FRED (see docs/architecture/release-intelligence-v1.md #9/#10), and a
shared class with an optional `fred_client=None` parameter would only
enforce that by convention -- `ReleaseReadService` has no FRED-shaped
parameter anywhere on it for a future edit to accidentally wire one
into.
"""

from datetime import date
from typing import Literal

from sqlalchemy.orm import Session

from app.clients.fred import FREDAuthError, FREDClient, FREDError, FREDTimeoutError, FREDUpstreamError
from app.domain.releases import classify_schedule_status
from app.models.releases import (
    PaginationMeta,
    ReleaseListResponse,
    ReleaseOccurrenceItem,
    ReleaseSyncFailure,
    ReleaseSyncResponse,
    ReleaseSyncSuccess,
)
from app.repositories.release_repository import ReleaseRepository


class InvalidDateRangeError(Exception):
    """Raised when start_date is after end_date."""


class ReleaseReadService:
    """Database-only, always. No method on this class accepts or
    constructs a `FREDClient` -- a persisted, empty, or stale catalog
    still reads successfully (see the frozen spec's #10/#14 acceptance
    invariants)."""

    def list_releases(
        self,
        session: Session,
        start_date: date | None,
        end_date: date | None,
        limit: int,
        offset: int,
        order: Literal["asc", "desc"],
        as_of_date: date,
    ) -> ReleaseListResponse:
        """Query persisted release occurrences, deriving each one's
        schedule status against the given `as_of_date` -- the caller
        (the route) decides what "now" means; this method never reads
        the system clock itself, and neither does
        `classify_schedule_status`.
        """
        if start_date is not None and end_date is not None and start_date > end_date:
            raise InvalidDateRangeError("start_date must not be after end_date.")

        repo = ReleaseRepository(session)
        rows, total = repo.list_occurrences(
            start_date=start_date, end_date=end_date, limit=limit, offset=offset, order=order
        )

        releases = [
            ReleaseOccurrenceItem(
                release_id=release.id,
                name=release.name,
                provider=release.provider,
                provider_release_id=release.provider_release_id,
                official_url=release.official_url,
                scheduled_date=occurrence.scheduled_date,
                schedule_status=classify_schedule_status(occurrence.scheduled_date, as_of_date),
            )
            for release, occurrence in rows
        ]

        return ReleaseListResponse(
            releases=releases,
            pagination=PaginationMeta(limit=limit, offset=offset, returned=len(releases), total=total),
        )


def _safe_sync_error_message(exc: FREDError) -> str:
    """A generic, non-leaking message per failure kind -- mirrors the
    same discipline the HTTP layer already applies to FRED exceptions
    (see app/api/series.py's sync_series route): never the raw
    exception text, which could in principle echo back provider
    response content."""
    if isinstance(exc, FREDAuthError):
        return "FRED rejected the configured API key."
    if isinstance(exc, FREDTimeoutError):
        return "FRED request timed out."
    if isinstance(exc, FREDUpstreamError):
        return "FRED returned an unexpected or malformed response."
    return "FRED request failed."


class ReleaseSyncService:
    """Explicit sync only -- never automatic, never triggered by a
    read, never invoked from anywhere but a deliberate caller. Requires
    a `FREDClient` (unlike `EconomicDataService`'s optional one): sync
    has no meaningful database-only mode."""

    def __init__(self, fred_client: FREDClient):
        self._fred_client = fred_client

    def sync_all(self, session: Session) -> ReleaseSyncResponse:
        """Sync every active curated release independently.

        One release's FRED failure never prevents syncing the others
        (per-release degrade, the same pattern
        `SeriesDiscoveryService.search` already uses for FRED search
        failures), and never touches any previously persisted
        occurrence for ANY release -- a failed call simply upserts
        nothing for that release this run (see
        docs/architecture/release-intelligence-v1.md #8).

        Never ingests an `EconomicObservation`, never recomputes a
        monitor, never calls AI -- there is no import anywhere in this
        method's call graph that could.
        """
        repo = ReleaseRepository(session)
        synced: list[ReleaseSyncSuccess] = []
        failed: list[ReleaseSyncFailure] = []

        for release in repo.get_active_releases():
            try:
                release_dates = self._fred_client.get_release_dates(release.provider_release_id)
            except FREDError as exc:
                failed.append(
                    ReleaseSyncFailure(release_id=release.id, name=release.name, error=_safe_sync_error_message(exc))
                )
                continue

            for release_date in release_dates:
                repo.upsert_occurrence(economic_release_id=release.id, scheduled_date=release_date.date)

            synced.append(
                ReleaseSyncSuccess(release_id=release.id, name=release.name, occurrences_seen=len(release_dates))
            )

        return ReleaseSyncResponse(synced=synced, failed=failed)
