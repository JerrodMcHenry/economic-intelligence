"""HTTP layer for the Rates Monitor (`rates_v1.0`) and its explicit
ingestion path (Increment #29).

Follows this project's existing route conventions exactly: a read-only
`GET /api/v1/monitors/rates` alongside the Inflation and Labor monitors,
and an explicit, operator-invoked `POST /api/v1/rates/sync` mirroring
`POST /api/v1/releases/sync`. No AI, no OpenAI dependency, no
probabilistic model anywhere in this module's import graph.

Division of responsibility, deliberately: the GET route reads only
already-persisted observations and never reaches upstream; only the POST
route holds a `TreasuryClient`. A read can therefore never trigger
ingestion, and ingestion can never be an accidental side effect of
someone loading a page.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.clients.treasury import TreasuryClient, TreasuryError
from app.api.operator import require_operator
from app.core.config import settings
from app.db.session import session_scope
from app.models.rates import RatesMonitorResult, RatesSyncResponse
from app.services.rates import RatesMonitorService
from app.services.rates_ingestion import DEFAULT_LOOKBACK_MONTHS, MAX_LOOKBACK_MONTHS, RatesIngestionService

monitors_router = APIRouter(prefix="/monitors", tags=["monitors"])
rates_router = APIRouter(prefix="/rates", tags=["rates"])


@monitors_router.get("/rates", response_model=RatesMonitorResult)
def get_rates_monitor() -> RatesMonitorResult:
    """The canonical, deterministic Rates Monitor result under
    methodology `rates_v1.0`: the nominal Treasury curve (2Y/5Y/10Y/30Y),
    real yields (5Y/10Y), derived curve spreads, and derived
    market-implied inflation compensation -- computed entirely from
    already-persisted observations.

    Missing data for any component (a series never ingested,
    insufficient history for a window, or no exactly-shared observation
    date between a derived metric's two inputs) is NOT an error: it is
    reported as that component's own `available: false` with an explicit
    reason inside a normal 200 response. Only a genuine
    database/infrastructure failure returns a non-200 -- economic
    missing data and infrastructure failure are deliberately different
    outcomes.
    """
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="Database is not configured on this server.")

    service = RatesMonitorService()

    try:
        with session_scope() as session:
            return service.get_result(session)
    except OperationalError:
        raise HTTPException(status_code=503, detail="Database is currently unavailable.")
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error while reading rates monitor data.")


@rates_router.post("/sync", response_model=RatesSyncResponse, dependencies=[Depends(require_operator)])
def sync_rates(
    lookback_months: int = Query(default=DEFAULT_LOOKBACK_MONTHS, ge=1, le=MAX_LOOKBACK_MONTHS),
) -> RatesSyncResponse:
    """Fetch the canonical Treasury rate datasets and upsert them
    idempotently. Explicit only -- never triggered by a read, never
    automatic, never a scheduler.

    Per-dataset failure isolation: one dataset failing upstream does not
    discard the other's ingested observations; the response reports
    `PARTIAL_FAILURE` and names the failed dataset. A total upstream
    failure is reported as a `FAILED` run rather than a 5xx, because the
    run genuinely happened and is recorded -- only a configuration or
    database failure raises here.

    No API key is required: these feeds are unauthenticated public
    U.S. Government data.
    """
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="Database is not configured on this server.")

    client = TreasuryClient(timeout=settings.treasury_timeout_seconds)
    service = RatesIngestionService(client)

    try:
        with session_scope() as session:
            return service.sync(session, lookback_months=lookback_months)
    except TreasuryError:
        # Every per-dataset failure is already caught and recorded by the
        # service; reaching here means an unexpected client-level failure.
        raise HTTPException(status_code=502, detail="Upstream Treasury data source error.")
    except OperationalError:
        raise HTTPException(status_code=503, detail="Database is currently unavailable.")
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error while syncing rates data.")
