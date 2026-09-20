"""HTTP layer for the release calendar.

`GET /releases` is database-only and never calls FRED (see
docs/architecture/release-intelligence-v1.md #9/#10). `POST
/releases/sync` is the one explicit, separate write path that does --
mirroring `POST /series/{series_id}/sync`'s existing shape (the frozen
spec's #9), adjusted for syncing the whole curated catalog in one call
rather than one resource at a time: release sync has no single-release
entry point from the frontend, unlike series sync.
"""

from datetime import date, datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.clients.fred import FREDClient
from app.api.operator import require_operator
from app.core.config import settings
from app.db.session import session_scope
from app.models.releases import ReleaseListResponse, ReleaseSyncResponse
from app.services.releases import InvalidDateRangeError, ReleaseReadService, ReleaseSyncService

router = APIRouter(prefix="/releases", tags=["releases"])


@router.get("", response_model=ReleaseListResponse)
def list_releases(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    order: Literal["asc", "desc"] = Query(default="asc"),
) -> ReleaseListResponse:
    """Query the persisted release calendar from PostgreSQL.

    Database-only: never calls FRED, never syncs, never mutates data.
    Use `POST /releases/sync` to populate/refresh what this endpoint
    reads. Succeeds with whatever is persisted (possibly nothing) even
    if FRED is unreachable, unconfigured, or has never been synced.
    """
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="Database is not configured on this server.")

    service = ReleaseReadService()
    as_of_date = datetime.now(timezone.utc).date()

    try:
        with session_scope() as session:
            return service.list_releases(
                session,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                offset=offset,
                order=order,
                as_of_date=as_of_date,
            )
    except InvalidDateRangeError:
        raise HTTPException(status_code=400, detail="start_date must not be after end_date.")
    except OperationalError:
        raise HTTPException(status_code=503, detail="Database is currently unavailable.")
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error while reading the release calendar.")


@router.post("/sync", response_model=ReleaseSyncResponse, dependencies=[Depends(require_operator)])
def sync_releases() -> ReleaseSyncResponse:
    """Fetch each active curated release's dates from FRED and upsert
    them idempotently. Explicit only -- never triggered by a read,
    never automatic, never a scheduler.

    Never fails as a whole for one release's FRED failure -- see
    `ReleaseSyncService.sync_all`. Only a configuration or database
    failure raises here. Never ingests an observation, never recomputes
    a monitor.
    """
    if not settings.fred_api_key:
        raise HTTPException(status_code=503, detail="FRED integration is not configured on this server.")
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="Database is not configured on this server.")

    client = FREDClient(api_key=settings.fred_api_key, timeout=settings.fred_timeout_seconds)
    service = ReleaseSyncService(client)

    try:
        with session_scope() as session:
            return service.sync_all(session)
    except OperationalError:
        raise HTTPException(status_code=503, detail="Database is currently unavailable.")
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error while syncing the release calendar.")
