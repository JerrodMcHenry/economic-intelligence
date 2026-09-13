"""HTTP layer for the Inflation Monitor (`inflation_v1.0`).

One narrow, read-only GET endpoint exposing the deterministic canonical
Inflation Monitor result computed by `InflationMonitorService` from
already-persisted observations. Never calls FRED, never syncs, never
triggers ingestion, never calls OpenAI -- this route has no dependency
on `app.services.ai`/`app.core.config.settings.openai_api_key` at all,
and works with `OPENAI_API_KEY` unset.
"""

from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.core.config import settings
from app.db.session import session_scope
from app.models.inflation import InflationMonitorResult
from app.services.inflation import InflationMonitorService

router = APIRouter(prefix="/monitors", tags=["monitors"])


@router.get("/inflation", response_model=InflationMonitorResult)
def get_inflation_monitor() -> InflationMonitorResult:
    """The canonical, deterministic Inflation Monitor result under
    methodology `inflation_v1.0`: Core PCE momentum (primary), Core CPI
    confirmation, the Headline PCE target gap, and Headline PCE/CPI
    context -- computed entirely from already-persisted observations.

    Missing required data for any component (e.g. a canonical series
    not yet persisted, or insufficient trailing history) is NOT an
    error: it is reported as that component's own
    `INSUFFICIENT_DATA`/`available: false` state within a normal 200
    response, per the frozen specification's missing-data semantics.
    Only a genuine database/infrastructure failure returns a non-200
    response -- economic missing data and infrastructure failure are
    deliberately different outcomes.
    """
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="Database is not configured on this server.")

    service = InflationMonitorService()

    try:
        with session_scope() as session:
            return service.get_result(session)
    except OperationalError:
        raise HTTPException(status_code=503, detail="Database is currently unavailable.")
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error while reading inflation monitor data.")
