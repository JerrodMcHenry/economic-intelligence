"""HTTP surface for the MacroChipz Analyst (Increment #33).

`GET  /api/v1/analyst/availability`
`POST /api/v1/analyst/explain`

The route's one structural job is the handoff that makes this feature
safe: it opens a session, builds the context packet from canonical
services, and then calls the model-facing service **with the packet
alone**. No `Session` is ever passed to `AnalystService`, so the model
boundary has nothing to read from and nothing to write to.

A client names a context; it never supplies one. `AnalystContextRef`
carries a type, an optional recorded-result id and a monitor -- no
state, no evidence, no numbers. Everything the Analyst treats as an
economic fact is resolved here, server-side, from the same services the
deterministic pages use.

Availability is a normal `200` carrying `available: false`, not an
error: whether an optional integration is configured is not a failure,
and a page asking the question should not have to handle an exception to
learn the answer.
"""

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.api.rate_limit import FixedWindowRateLimiter, client_key
from app.core.config import settings
from app.db.session import session_scope
from app.models.analyst import AnalystAvailability, AnalystExplainRequest, AnalystExplainResponse
from app.services.analyst import (
    AnalystMalformedOutputError,
    AnalystNotConfiguredError,
    AnalystProviderUnavailableError,
    AnalystService,
    analyst_available,
)
from app.services.analyst_context import AnalystContextBuilder, AnalystContextUnavailableError

router = APIRouter(prefix="/analyst", tags=["analyst"])

#: Increment #34. The Analyst is the one endpoint where an anonymous
#: caller can spend real money, so it is the one endpoint rate-limited.
#: In-process and per-instance -- valid only for the single-instance
#: deployment the frozen architecture specifies; see
#: `app/api/rate_limit.py` for the full constraint.
_analyst_rate_limiter = FixedWindowRateLimiter(
    limit=settings.analyst_rate_limit_requests,
    window_seconds=settings.analyst_rate_limit_window_seconds,
)


@router.get("/availability", response_model=AnalystAvailability)
def get_analyst_availability() -> AnalystAvailability:
    """Whether the optional Analyst is usable on this deployment.

    Never raises, never touches the database, and never reveals which
    setting is missing -- only that the feature is or is not available.
    A deployment with no provider configured answers `200` here and every
    canonical page keeps working exactly as before.
    """
    available = analyst_available()
    return AnalystAvailability(available=available, reason=None if available else "NOT_CONFIGURED")


@router.post("/explain", response_model=AnalystExplainResponse)
def explain(request: AnalystExplainRequest, http_request: Request) -> AnalystExplainResponse:
    """Explain MacroChipz's own intelligence for one allow-listed context.

    Read-only end to end. Nothing on this path writes an observation, a
    version, a recorded result, provenance, or a methodology; a repeated
    question may produce another explanation but can never change what
    MacroChipz has concluded.

    An unsupported `context.type` is a 422 from FastAPI's own validation
    before any code here runs -- the allow-list is the Literal type, not
    a runtime check that could be forgotten.
    """
    if not analyst_available():
        raise HTTPException(status_code=503, detail="The MacroChipz Analyst is not configured on this server.")
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="Database is not configured on this server.")

    # Rate limiting happens BEFORE the context packet is assembled, so a
    # throttled caller costs neither a database read nor a provider call.
    key = client_key(
        http_request.client.host if http_request.client else None,
        http_request.headers.get("x-forwarded-for"),
    )
    if not _analyst_rate_limiter.allow(key):
        raise HTTPException(
            status_code=429,
            detail="Too many Analyst requests. Please wait a moment and try again.",
            headers={"Retry-After": str(_analyst_rate_limiter.retry_after_seconds(key))},
        )

    try:
        with session_scope() as session:
            packet = AnalystContextBuilder().build(session, request.context)
    except AnalystContextUnavailableError:
        raise HTTPException(status_code=404, detail="The requested MacroChipz context was not found.")
    except OperationalError:
        raise HTTPException(status_code=503, detail="Database is currently unavailable.")
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error while assembling Analyst context.")

    # The session is closed before the model is ever contacted. The
    # provider call cannot hold a database connection open, and cannot
    # reach one.
    try:
        return AnalystService().explain(
            packet, request.question, request_id=getattr(http_request.state, "request_id", None)
        )
    except AnalystNotConfiguredError:
        raise HTTPException(status_code=503, detail="The MacroChipz Analyst is not configured on this server.")
    except AnalystProviderUnavailableError:
        raise HTTPException(status_code=503, detail="The MacroChipz Analyst is temporarily unavailable.")
    except AnalystMalformedOutputError:
        raise HTTPException(status_code=503, detail="The MacroChipz Analyst could not produce a usable answer.")
