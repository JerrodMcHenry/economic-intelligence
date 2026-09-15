"""HTTP layer for the Inflation Monitor (`inflation_v1.0`) and its
"What Changed?" comparison layer (`inflation_what_changed_v1.0`).

Two narrow, read-only GET endpoints exposing deterministic canonical
results computed by `InflationMonitorService` from already-persisted
observations. Neither route calls FRED, syncs, triggers ingestion, or
calls OpenAI -- this module has no dependency on
`app.services.ai`/`app.core.config.settings.openai_api_key` at all, and
both routes work with `OPENAI_API_KEY` unset.
"""

from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.core.config import settings
from app.db.session import session_scope
from app.models.inflation import InflationMonitorResult
from app.models.inflation_what_changed import InflationWhatChangedResult
from app.models.state_duration import StateDurationResult
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


@router.get("/inflation/changes", response_model=InflationWhatChangedResult)
def get_inflation_what_changed() -> InflationWhatChangedResult:
    """The canonical, deterministic "What Changed?" result under
    contract `inflation_what_changed_v1.0`: a month-over-month
    comparison of Core PCE momentum, Core CPI confirmation, the
    Headline PCE target gap, and Headline PCE/CPI context, each
    independently anchored per the frozen contract -- computed entirely
    from already-persisted observations, by re-evaluating
    `inflation_v1.0`'s own existing classification rules at explicit
    calendar periods (never a second methodology).

    Missing required data for any section (e.g. a canonical series not
    yet persisted, or an unclassifiable current or previous calendar
    month) is NOT an error: it is reported as that section's own
    `comparison_available`/`INSUFFICIENT_DATA`/`UNAVAILABLE` evidence
    within a normal 200 response. Only a genuine database/infrastructure
    failure returns a non-200 response.
    """
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="Database is not configured on this server.")

    service = InflationMonitorService()

    try:
        with session_scope() as session:
            return service.get_what_changed_result(session)
    except OperationalError:
        raise HTTPException(status_code=503, detail="Database is currently unavailable.")
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error while reading inflation what-changed data.")


@router.get("/inflation/state-duration", response_model=StateDurationResult)
def get_inflation_state_duration() -> StateDurationResult:
    """The canonical State Duration V1 result
    (`docs/product/state-duration-v1.md`) for Inflation's own top-level
    canonical state (`underlying_momentum.state`) -- a **latest-revised
    reconstruction only** (§1 of the frozen contract): never recorded
    history, never a reconstruction of what was knowable at the time.
    Computed entirely from
    already-persisted Core PCE observations, by re-evaluating
    `inflation_v1.0`'s own existing, unmodified classification rule
    (`compute_series_momentum_at`) at explicit prior calendar periods --
    never a second methodology.

    The current state itself being `INSUFFICIENT_DATA` (or having no
    evaluable period) is NOT an error: it is reported as
    `status: "CURRENT_INSUFFICIENT"` within a normal 200 response.
    Every other outcome (`EXACT`/`DATA_BOUNDED`/`LOOKBACK_BOUNDED`
    boundary types) is also a normal 200 response. Only a genuine
    database/infrastructure failure returns a non-200 response.
    """
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="Database is not configured on this server.")

    service = InflationMonitorService()

    try:
        with session_scope() as session:
            return service.get_state_duration_result(session)
    except OperationalError:
        raise HTTPException(status_code=503, detail="Database is currently unavailable.")
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error while reading inflation state duration data.")
