"""Read-only HTTP surface for point-in-time intelligence history
(Increment #32).

`GET /api/v1/monitors/{monitor}/history`
`GET /api/v1/monitors/{monitor}/history/{recorded_result_id}`

Its own router file rather than additions to `app/api/inflation.py` and
`app/api/labor.py` -- the convention those two modules' own docstrings
state, and the reason is structural here: the response shape is
monitor-independent, so one parameterized pair of routes is the honest
expression, while the existing per-monitor routes exist precisely
because `InflationMonitorResult` and `LaborMonitorResult` are different
types.

`{monitor}` is typed as the two-value `HistoryMonitor` literal, so
`/monitors/rates/history` is a 422 from FastAPI's own validation. Rates
has observation versioning (#31) but records no monitor state, and a
route that answered it with an empty list would imply a history that
does not exist.

GET only. Replay never writes, and nothing here can mutate the
append-only recorded history it reads (ADR-025).
"""

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.core.config import settings
from app.db.session import session_scope
from app.models.monitor_history import HistoryMonitor, MonitorHistoryDetail, MonitorHistoryResponse
from app.services.monitor_history import MonitorHistoryService, RecordedResultNotFoundError

router = APIRouter(prefix="/monitors", tags=["monitors"])


@router.get("/{monitor}/history", response_model=MonitorHistoryResponse)
def get_monitor_history(
    monitor: HistoryMonitor,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> MonitorHistoryResponse:
    """One page of what MacroChipz durably concluded, newest first.

    Bounded by the same read-model limits `#19B`'s processing-status
    endpoint uses (default 20, max 100), so history can never be
    requested unbounded.

    A recorded result whose replay fails is a normal 200 carrying a
    `MISMATCH` or `NOT_REPLAYABLE` outcome -- an integrity finding is
    data, not an HTTP error, exactly as an `INSUFFICIENT_DATA` monitor
    state already is.
    """
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="Database is not configured on this server.")
    service = MonitorHistoryService()
    try:
        with session_scope() as session:
            return service.get_history(session, monitor, limit=limit, offset=offset)
    except OperationalError:
        raise HTTPException(status_code=503, detail="Database is currently unavailable.")
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error while reading monitor history.")


@router.get("/{monitor}/history/{recorded_result_id}", response_model=MonitorHistoryDetail)
def get_monitor_history_detail(monitor: HistoryMonitor, recorded_result_id: int) -> MonitorHistoryDetail:
    """One recorded result: what was known then, how it compares with
    today's revised dataset, and what changed in the same run.

    The id is scoped by monitor, so a Labor result requested under
    `/monitors/inflation/...` is a 404 rather than a row rendered under
    the wrong monitor's heading.
    """
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="Database is not configured on this server.")
    service = MonitorHistoryService()
    try:
        with session_scope() as session:
            return service.get_history_detail(session, monitor, recorded_result_id)
    except RecordedResultNotFoundError:
        raise HTTPException(
            status_code=404, detail=f"Recorded result '{recorded_result_id}' was not found for monitor '{monitor}'."
        )
    except OperationalError:
        raise HTTPException(status_code=503, detail="Database is currently unavailable.")
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error while reading monitor history.")
