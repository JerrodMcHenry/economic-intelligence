"""HTTP layer for economic data series endpoints.

Responsible for request/response handling and translating service-layer
failures into appropriate HTTP status codes. No FRED- or business-logic
details live here.
"""

from fastapi import APIRouter, HTTPException

from app.clients.fred import (
    FREDAuthError,
    FREDClient,
    FREDSeriesNotFoundError,
    FREDTimeoutError,
    FREDUpstreamError,
)
from app.core.config import settings
from app.models.series import SeriesResponse
from app.services.economic_data import EconomicDataService

router = APIRouter(prefix="/series", tags=["series"])


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
