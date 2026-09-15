"""HTTP layer for Increment #25G's Since Last Visit V1 read model --
see docs/product/since-last-visit-v1.md (#25F), the frozen contract
this module implements verbatim.

One narrow, read-only GET endpoint exposing a deterministic recap
computed by `SinceLastVisitService` from already-persisted operational
evidence. It never calls FRED, never triggers release processing or
maintenance, never calls OpenAI, and never persists anything --
checkpoint storage belongs to #25H's own client-side code (contract
§67).

Deliberately its own, new top-level resource (`/since-last-visit`,
contract §53) -- not nested under `/monitors` (this answers a
cross-domain question, not one monitor's own) and not under
`/releases`/`/overview` (no aggregate `/overview` resource exists or
is resurrected here, per `frontend/src/pages/Overview.tsx`'s own #19A
decision).
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.core.config import settings
from app.db.session import session_scope
from app.models.since_last_visit import SinceLastVisitResponse
from app.services.since_last_visit import SinceLastVisitService

router = APIRouter(prefix="/since-last-visit", tags=["since-last-visit"])


def _parse_after(raw: str | None) -> datetime | None:
    """Contract §54: a missing, malformed, or otherwise unparseable
    `after` is NEVER a `400`/`422` -- it is treated as absent, falling
    back to first-visit behavior (`app.domain.since_last_visit.resolve_window`
    treats `None` as a genuine first visit). A broken client-supplied
    value (a corrupted `localStorage` value, in practice) is a data
    condition to handle gracefully, exactly like every other
    infrastructure-vs-data-condition boundary this project already
    draws -- never a reason to hard-fail the request."""
    if raw is None or raw == "":
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        # A timezone-naive value is genuinely ambiguous -- never
        # guessed as UTC. Treated as unusable, same as a malformed one.
        return None
    return parsed


@router.get("", response_model=SinceLastVisitResponse)
def get_since_last_visit(
    after: str | None = Query(default=None, description="ISO-8601 UTC datetime of the last acknowledged checkpoint, if any."),
) -> SinceLastVisitResponse:
    """A deterministic recap of canonical economic-intelligence activity
    recorded strictly after `after` (or a bounded default window if
    omitted or unusable), through the server's own current watermark --
    never a claim about the whole economy, never AI-generated, never an
    economic-significance score. See the frozen contract for the exact
    truth semantics this endpoint implements.
    """
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="Database is not configured on this server.")

    parsed_after = _parse_after(after)
    service = SinceLastVisitService()

    try:
        with session_scope() as session:
            return service.get_recap(session, parsed_after)
    except OperationalError:
        raise HTTPException(status_code=503, detail="Database is currently unavailable.")
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error while reading since-last-visit data.")
