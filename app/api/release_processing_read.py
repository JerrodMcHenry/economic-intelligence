"""HTTP layer for Increment #19B's public release-processing read
model.

Deliberately a NEW, separate router file rather than an addition to
`app.api.releases` -- mirroring `app.services.release_processing`'s own
#18 precedent of a new, separate bridging module rather than extending
a file `tests/integration/test_transaction_and_safety.py::TestReleaseCalendarStructuralIndependence`
protects. `app.services.release_processing_read` (and, transitively,
`app.repositories.release_processing_read_repository`) imports
series/observation-shaped SQLAlchemy models (`EconomicSeries`,
`ReleaseObservationUpdate`, ...) that guard's forbidden-import list was
never meant to allow into `app/api/releases.py`; keeping this route in
its own file means that guard's protection stays meaningful without
needing to grow its enumerated exceptions.

The collection route below is database-only and never calls FRED or
AI -- see `app.services.release_processing_read.ReleaseProcessingReadService`'s
own docstring. This is the only route registered in this file: no
single-occurrence detail route exists in #19B (see
docs/architecture/release-processing-read-model-v1.md).
"""

from datetime import date

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.core.config import settings
from app.db.session import session_scope
from app.models.release_processing_read import ProcessingStatus, ReleaseProcessingStatusResponse
from app.services.release_processing_read import InvalidDateRangeError, ReleaseProcessingReadService

router = APIRouter(prefix="/releases", tags=["releases"])


@router.get("/processing-status", response_model=ReleaseProcessingStatusResponse)
def get_release_processing_status(
    occurrence_id: int | None = Query(default=None),
    release_id: int | None = Query(default=None),
    status: ProcessingStatus | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ReleaseProcessingStatusResponse:
    """Query #18's persisted release-processing evidence as a read
    model.

    Database-only: never calls FRED, never calls AI, never mutates
    data, never triggers a check. A persisted `CHECK_FAILED`/
    `PARTIAL_CHECK` result is itself successfully-read product data --
    it returns HTTP 200, the same as any other status (see
    `ReleaseProcessingReadService`). Only a request-shape problem
    (400/422) or a genuine database failure (503/500) is an HTTP
    error here.

    Only mapped release occurrences (at least one active
    `ReleaseSeriesMapping`) ever appear in this resource -- an
    unmapped release's occurrences are excluded entirely, never given
    any status (see `app.models.release_processing_read`'s docstring
    for why there is no sixth, catch-all status for that case).
    """
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="Database is not configured on this server.")

    service = ReleaseProcessingReadService()

    try:
        with session_scope() as session:
            return service.get_processing_status(
                session,
                occurrence_id=occurrence_id,
                release_id=release_id,
                status=status,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                offset=offset,
            )
    except InvalidDateRangeError:
        raise HTTPException(status_code=400, detail="start_date must not be after end_date.")
    except OperationalError:
        raise HTTPException(status_code=503, detail="Database is currently unavailable.")
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error while reading release processing status.")
