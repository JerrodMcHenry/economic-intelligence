"""HTTP layer for the Housing world and its explicit ingestion path
(Increment #45).

Follows this project's existing route conventions: a read-only
`GET /api/v1/housing` and an explicit, operator-invoked
`POST /api/v1/housing/sync` mirroring `POST /api/v1/rates/sync`. No AI,
no OpenAI dependency, no probabilistic model anywhere in this module's
import graph.

NOT `/monitors/housing`, DELIBERATELY. The three monitor routes return a
methodology's classification of a domain. Housing has no methodology and
no state, so mounting it beside them would promise a conclusion this
world does not produce -- the URL would be making a claim the payload
cannot support.

Division of responsibility, the same as Rates: the GET route reads only
already-persisted observations and never reaches upstream; only the POST
route constructs a `CensusClient`. A read can therefore never trigger
ingestion, and ingestion can never be an accidental side effect of
someone loading `/housing`. That matters more for Census than for
Treasury, because Census requires a credential and a read-triggered
fetch would spend an authenticated quota on every page view.

CREDENTIAL HANDLING. The key is read from configuration and handed to
the client. It is never logged, never returned in a response, and never
included in an error detail -- an authentication failure is reported as
a fixed sentence naming the VARIABLE, never a value.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.api.operator import require_operator
from app.clients.census import CensusAuthError, CensusClient, CensusNotConfiguredError
from app.core.config import settings
from app.db.session import session_scope
from app.models.housing import HousingResult, HousingSyncResponse
from app.services.census_ingestion import (
    DEFAULT_LOOKBACK_MONTHS,
    MAX_LOOKBACK_MONTHS,
    HousingIngestionService,
)
from app.services.housing import HousingReadService

router = APIRouter(prefix="/housing", tags=["housing"])


@router.get("", response_model=HousingResult)
def get_housing() -> HousingResult:
    """The canonical Housing read model: permits, starts and completions,
    each as a seasonally adjusted annual rate and as the month's actual
    unadjusted count, computed entirely from already-persisted
    observations.

    NO STATE IS RETURNED, because none exists. There is no
    `housing_v1.0`, so this response carries source facts and
    deterministic differences between them -- never a rating, a
    direction label, a composite score or a significance judgement.

    Missing data for any measure is NOT an error: it is reported as that
    measure's own `available: false` with an explicit reason inside a
    normal 200 response. Only a genuine database/infrastructure failure
    returns a non-200 -- economic missing data and infrastructure failure
    are deliberately different outcomes.
    """
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="Database is not configured on this server.")

    service = HousingReadService()

    try:
        with session_scope() as session:
            return service.get_result(session)
    except OperationalError:
        raise HTTPException(status_code=503, detail="Database is currently unavailable.")
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error while reading housing data.")


@router.post("/sync", response_model=HousingSyncResponse, dependencies=[Depends(require_operator)])
def sync_housing(
    lookback_months: int = Query(default=DEFAULT_LOOKBACK_MONTHS, ge=1, le=MAX_LOOKBACK_MONTHS),
    full_history: bool = Query(
        default=False,
        description=(
            "Request every period the dataset publishes (1959 onward) rather than a recent window. "
            "What a new environment needs once; a routine sync does not."
        ),
    ),
) -> HousingSyncResponse:
    """Fetch the Census New Residential Construction dataset and upsert
    it idempotently. Explicit only -- never triggered by a read, never
    automatic, never a scheduler.

    An upstream failure is reported as a `FAILED` run inside a 200
    response rather than a 5xx, because the run genuinely happened and is
    recorded -- the same contract `POST /api/v1/rates/sync` uses. The two
    exceptions are configuration failures, which are the operator's to
    fix and are reported as such:

    - **503** when no `CENSUS_API_KEY` is configured on this deployment.
    - **502** when Census rejects the configured key. Distinguished from
      a generic upstream error on purpose: it is the one Census failure
      an operator can act on, and it usually means a newly issued key has
      not been activated from its confirmation email.

    Neither detail message contains any part of the credential.
    """
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="Database is not configured on this server.")

    try:
        client = CensusClient(
            api_key=settings.census_api_key,
            timeout=settings.census_timeout_seconds,
        )
    except CensusNotConfiguredError:
        raise HTTPException(
            status_code=503,
            detail="Housing ingestion is not available: CENSUS_API_KEY is not configured on this server.",
        )

    service = HousingIngestionService(client)

    try:
        with session_scope() as session:
            return service.sync(session, lookback_months=lookback_months, full_history=full_history)
    except CensusAuthError:
        # The service records and reports every Census failure it can,
        # including this one; reaching here means the failure escaped
        # that path. Reported as a configuration problem, with no value.
        raise HTTPException(
            status_code=502,
            detail="Census rejected the configured API key. Check that CENSUS_API_KEY is activated.",
        )
    except OperationalError:
        raise HTTPException(status_code=503, detail="Database is currently unavailable.")
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error while syncing housing data.")
