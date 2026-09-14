"""HTTP layer for the Labor Market Monitor (`labor_v1.0`).

One narrow, read-only GET endpoint exposing a deterministic canonical
result computed by `LaborMonitorService` from already-persisted
observations. Never calls FRED, syncs, triggers ingestion, or calls
OpenAI -- this module has no dependency on
`app.services.ai`/`app.core.config.settings.openai_api_key` at all.

Deliberately a NEW, separate router file rather than an addition to
`app.api.inflation` -- the frozen spec's own "no premature generic
monitor framework" instruction: Labor is implemented independently as
the second monitor, not folded into Inflation's own file merely
because both mount under the same `/monitors` prefix. Both routers
share that prefix; FastAPI composes them without conflict since their
literal registered paths (`/monitors/inflation*` vs.
`/monitors/labor`) never collide.
"""

from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.core.config import settings
from app.db.session import session_scope
from app.models.labor import LaborMonitorResult
from app.models.labor_what_changed import LaborWhatChangedResult
from app.services.labor import LaborMonitorService

router = APIRouter(prefix="/monitors", tags=["monitors"])


@router.get("/labor", response_model=LaborMonitorResult)
def get_labor_monitor() -> LaborMonitorResult:
    """The canonical, deterministic Labor Monitor result under
    methodology `labor_v1.0`: PAYEMS employment condition/momentum and
    UNRATE unemployment trend, combined into one top-level `LaborState`
    -- computed entirely from already-persisted observations.

    Missing required data for either component (e.g. PAYEMS or UNRATE
    not yet persisted, or insufficient trailing history at the shared
    evaluation period) is NOT an error: it is reported as that
    component's own `INSUFFICIENT_DATA` state -- and, if neither
    series has any persisted observation at all, as the whole result's
    `INSUFFICIENT_DATA` state with `evaluation_period: null` -- within
    a normal 200 response, per the frozen specification's missing-data
    semantics. Only a genuine database/infrastructure failure returns
    a non-200 response.
    """
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="Database is not configured on this server.")

    service = LaborMonitorService()

    try:
        with session_scope() as session:
            return service.get_result(session)
    except OperationalError:
        raise HTTPException(status_code=503, detail="Database is currently unavailable.")
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error while reading labor monitor data.")


@router.get("/labor/changes", response_model=LaborWhatChangedResult)
def get_labor_what_changed() -> LaborWhatChangedResult:
    """The canonical, deterministic "What Changed?" result under
    contract `labor_what_changed_v1.0`: a month-over-month comparison
    of PAYEMS employment condition/momentum/state and UNRATE
    unemployment trend/state, plus the top-level `LaborState`, each
    compared independently -- computed entirely from already-persisted
    observations, by re-evaluating `labor_v1.0`'s own existing
    classification rules at explicit calendar periods (never a second
    methodology).

    Missing required data (e.g. PAYEMS or UNRATE not yet persisted, or
    no evaluable period at all) is NOT an error: it is reported as
    `comparison_available: false` with `previous_period`/
    `current_period: null` within a normal 200 response, per the
    frozen contract's missing-data semantics. Only a genuine
    database/infrastructure failure returns a non-200 response.

    No query parameters -- always the latest evaluable period against
    exactly the calendar month before it, mirroring
    `GET /monitors/inflation/changes`'s identical, parameter-free
    shape.
    """
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="Database is not configured on this server.")

    service = LaborMonitorService()

    try:
        with session_scope() as session:
            return service.get_what_changed_result(session)
    except OperationalError:
        raise HTTPException(status_code=503, detail="Database is currently unavailable.")
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error while reading labor what-changed data.")
