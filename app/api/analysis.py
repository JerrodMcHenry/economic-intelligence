"""HTTP layer for cross-series (multi-series) analysis endpoints.

Responsible for request/response handling and translating service-layer
failures into appropriate HTTP status codes. No SQL or analysis math
lives here. A separate router (distinct from `app/api/series.py`) because
it's a genuinely different resource/prefix (`/analysis`, not `/series`),
mirroring this project's one-router-file-per-resource-area convention
rather than adding an unrelated prefix into the existing series router.
"""

from datetime import date

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.core.config import settings
from app.db.session import session_scope
from app.models.analysis import AnalysisType, SeriesComparisonResponse
from app.services.analysis import AnalysisService
from app.services.economic_data import InvalidDateRangeError, SeriesNotFoundError

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/compare", response_model=SeriesComparisonResponse)
def compare_series(
    series_a: str = Query(...),
    series_b: str = Query(...),
    analysis: AnalysisType = Query(...),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
) -> SeriesComparisonResponse:
    """Compare two persisted series: exact-date alignment, spread, or
    Pearson correlation.

    Database-only: never calls FRED, never syncs, never mutates data, and
    never persists the analysis result -- it's recomputed on every call
    from raw observations already in PostgreSQL. Not paginated: date
    filtering is the only supported way to narrow the compared range (see
    AnalysisService.compare for why pagination isn't offered here).
    """
    if not settings.database_url:
        raise HTTPException(
            status_code=503,
            detail="Database is not configured on this server.",
        )

    service = AnalysisService()

    try:
        with session_scope() as session:
            return service.compare(
                series_a,
                series_b,
                session,
                analysis=analysis,
                start_date=start_date,
                end_date=end_date,
            )
    except InvalidDateRangeError:
        raise HTTPException(status_code=400, detail="start_date must not be after end_date.")
    except SeriesNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except OperationalError:
        raise HTTPException(status_code=503, detail="Database is currently unavailable.")
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error while reading series data.")
