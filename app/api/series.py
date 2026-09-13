"""HTTP layer for economic data series endpoints.

Responsible for request/response handling and translating service-layer
failures into appropriate HTTP status codes. No FRED- or business-logic
details live here.
"""

from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError

from app.clients.fred import (
    FREDAuthError,
    FREDClient,
    FREDSeriesNotFoundError,
    FREDTimeoutError,
    FREDUpstreamError,
)
from app.core.config import settings
from app.db.session import session_scope
from app.models.discovery import SeriesSearchResponse
from app.models.series import SeriesObservationsResponse, SeriesResponse, SeriesTransformResponse, TransformationType
from app.services.discovery import SeriesDiscoveryService
from app.services.economic_data import (
    EconomicDataService,
    InvalidDateRangeError,
    InvalidWindowError,
    SeriesNotFoundError,
)

router = APIRouter(prefix="/series", tags=["series"])


@router.get("/search", response_model=SeriesSearchResponse)
def search_series(
    q: str = Query(..., min_length=1, max_length=200, description="An economic concept or phrase, e.g. 'unemployment'."),
    limit: int = Query(default=10, ge=1, le=50),
) -> SeriesSearchResponse:
    """Discover candidate economic series by concept or phrase -- no AI
    required. Searches locally persisted metadata and (if FRED is
    configured) FRED's public catalog, merged into one deduplicated,
    deterministically ranked list.

    This is discovery, not semantic judgment: it finds real, verified
    candidates and reports each one's actual metadata (including
    whether it's already persisted, i.e. usable by the other endpoints
    in this router right now) -- it never decides which candidate is
    "the" correct answer to a concept, never invents a series, and
    never persists anything. `persisted=False` candidates are reported
    exactly as such; discovering one never syncs it (see
    `POST /{series_id}/sync` for the explicit, separate action that
    does). Declared before `/{series_id}` in this router so `search`
    itself is never captured as a `series_id` path parameter.

    Read-only and database-backed for local metadata; FRED reachability
    is optional here (unlike `GET /{series_id}`/`POST /{series_id}/sync`,
    where it's required) -- a search with no `FRED_API_KEY` configured,
    or with FRED unreachable, degrades to local-only results rather
    than failing (see `SeriesDiscoveryService.search`).
    """
    query = q.strip()
    if not query:
        raise HTTPException(status_code=400, detail="q must contain non-whitespace text.")

    if not settings.database_url:
        raise HTTPException(status_code=503, detail="Database is not configured on this server.")

    fred_client = FREDClient(api_key=settings.fred_api_key, timeout=settings.fred_timeout_seconds) if settings.fred_api_key else None
    service = SeriesDiscoveryService(fred_client)

    try:
        with session_scope() as session:
            return service.search(query, limit, session)
    except OperationalError:
        raise HTTPException(status_code=503, detail="Database is currently unavailable.")
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error while searching series metadata.")


@router.get("/{series_id}", response_model=SeriesResponse)
def get_series(series_id: str) -> SeriesResponse:
    if not settings.fred_api_key:
        raise HTTPException(
            status_code=503,
            detail="FRED integration is not configured on this server.",
        )

    client = FREDClient(api_key=settings.fred_api_key, timeout=settings.fred_timeout_seconds)
    service = EconomicDataService(client)

    try:
        return service.get_series(series_id)
    except FREDSeriesNotFoundError:
        raise HTTPException(status_code=404, detail=f"Series '{series_id}' was not found.")
    except FREDAuthError:
        raise HTTPException(
            status_code=503,
            detail="Economic data integration is currently unavailable.",
        )
    except FREDTimeoutError:
        raise HTTPException(status_code=504, detail="Upstream FRED request timed out.")
    except FREDUpstreamError:
        raise HTTPException(status_code=502, detail="Upstream FRED service error.")


@router.post("/{series_id}/sync", response_model=SeriesResponse)
def sync_series(series_id: str) -> SeriesResponse:
    """Fetch a series from FRED and persist it to the database.

    Idempotent: existing series metadata and observations for the same
    series/date are updated in place rather than duplicated.
    """
    if not settings.fred_api_key:
        raise HTTPException(
            status_code=503,
            detail="FRED integration is not configured on this server.",
        )
    if not settings.database_url:
        raise HTTPException(
            status_code=503,
            detail="Database is not configured on this server.",
        )

    client = FREDClient(api_key=settings.fred_api_key, timeout=settings.fred_timeout_seconds)
    service = EconomicDataService(client)

    try:
        with session_scope() as session:
            return service.sync_series(series_id, session)
    except FREDSeriesNotFoundError:
        raise HTTPException(status_code=404, detail=f"Series '{series_id}' was not found.")
    except FREDAuthError:
        raise HTTPException(
            status_code=503,
            detail="Economic data integration is currently unavailable.",
        )
    except FREDTimeoutError:
        raise HTTPException(status_code=504, detail="Upstream FRED request timed out.")
    except FREDUpstreamError:
        raise HTTPException(status_code=502, detail="Upstream FRED service error.")
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Series data conflict; please retry.")
    except OperationalError:
        raise HTTPException(status_code=503, detail="Database is currently unavailable.")
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error while persisting series data.")


@router.get("/{series_id}/observations", response_model=SeriesObservationsResponse)
def get_series_observations(
    series_id: str,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    order: Literal["asc", "desc"] = Query(default="asc"),
) -> SeriesObservationsResponse:
    """Query persisted historical observations for a series from PostgreSQL.

    Database-only: never calls FRED, never syncs, never mutates data. Use
    POST /{series_id}/sync to populate/refresh what this endpoint reads.
    """
    if not settings.database_url:
        raise HTTPException(
            status_code=503,
            detail="Database is not configured on this server.",
        )

    service = EconomicDataService()

    try:
        with session_scope() as session:
            return service.get_observations(
                series_id,
                session,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                offset=offset,
                order=order,
            )
    except InvalidDateRangeError:
        raise HTTPException(status_code=400, detail="start_date must not be after end_date.")
    except SeriesNotFoundError:
        raise HTTPException(status_code=404, detail=f"Series '{series_id}' was not found.")
    except OperationalError:
        raise HTTPException(status_code=503, detail="Database is currently unavailable.")
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error while reading series data.")


@router.get("/{series_id}/transform", response_model=SeriesTransformResponse)
def get_series_transform(
    series_id: str,
    transformation: TransformationType = Query(...),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    window: int | None = Query(default=None, ge=2, le=365),
) -> SeriesTransformResponse:
    """Compute a derived series over persisted historical observations.

    Database-only: never calls FRED, never syncs, never mutates data, and
    never persists the derived result -- it's recomputed on every call
    from raw observations already in PostgreSQL. Not paginated (see
    EconomicDataService.get_transformed_observations for why).
    """
    if not settings.database_url:
        raise HTTPException(
            status_code=503,
            detail="Database is not configured on this server.",
        )

    service = EconomicDataService()

    try:
        with session_scope() as session:
            return service.get_transformed_observations(
                series_id,
                session,
                transformation=transformation,
                start_date=start_date,
                end_date=end_date,
                window=window,
            )
    except InvalidDateRangeError:
        raise HTTPException(status_code=400, detail="start_date must not be after end_date.")
    except InvalidWindowError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except SeriesNotFoundError:
        raise HTTPException(status_code=404, detail=f"Series '{series_id}' was not found.")
    except OperationalError:
        raise HTTPException(status_code=503, detail="Database is currently unavailable.")
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error while reading series data.")
