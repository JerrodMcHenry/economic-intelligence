"""HTTP layer for the Structured Intelligence Layer (Increment #39).

Transport only. This module selects, paginates and maps exceptions to
status codes; it never decides what happened in the economy. Every
semantic fact comes from `IntelligenceService`/`IntelligenceBuilder`,
which is the point of the layer -- a surface that reconstructed
intelligence here would be a second, drifting account of reality.

Read-only and database-only: no provider client, no model call, no
ingestion. An intelligence read cannot fail because FRED or Treasury is
down, because it never reaches them.
"""

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.db.session import session_scope
from app.models.intelligence import (
    IntelligenceListResponse,
    IntelligenceObject,
    IntelligenceType,
    World,
)
from app.services.intelligence import IntelligenceService
from app.services.intelligence.service import DEFAULT_LIMIT, MAX_LIMIT

router = APIRouter(prefix="/intelligence", tags=["intelligence"])

_service = IntelligenceService()

#: The longest identifier this endpoint will look up. Stable ids are
#: built from bounded semantic dimensions, so anything longer is not one
#: -- rejected before it reaches a database read.
_MAX_ID_LENGTH = 256


@router.get("", response_model=IntelligenceListResponse)
def list_intelligence(
    world: World | None = Query(default=None, description="Restrict to one economic world."),
    type: IntelligenceType | None = Query(default=None, description="Restrict to one intelligence type."),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> IntelligenceListResponse:
    """A bounded, deterministically ordered page of structured
    intelligence.

    `limit` is bounded twice -- by FastAPI's own `le=MAX_LIMIT` and
    again inside the service -- so no caller can request an unbounded
    payload however the request is shaped.
    """
    try:
        with session_scope() as session:
            return _service.list_intelligence(
                session, world=world, intelligence_type=type, limit=limit, offset=offset
            )
    except OperationalError:
        raise HTTPException(status_code=503, detail="Intelligence is temporarily unavailable.") from None
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Intelligence could not be read.") from None


@router.get("/{intelligence_id}", response_model=IntelligenceObject)
def get_intelligence(intelligence_id: str) -> IntelligenceObject:
    """One intelligence object by its stable id.

    404 for both "no such id" and "malformed id": distinguishing them
    would tell a prober how identifiers are shaped, and the answer is
    the same either way -- there is nothing there.
    """
    if not intelligence_id or len(intelligence_id) > _MAX_ID_LENGTH:
        raise HTTPException(status_code=404, detail="No intelligence with that identifier.")

    try:
        with session_scope() as session:
            found = _service.get_intelligence(session, intelligence_id)
    except OperationalError:
        raise HTTPException(status_code=503, detail="Intelligence is temporarily unavailable.") from None
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Intelligence could not be read.") from None

    if found is None:
        raise HTTPException(status_code=404, detail="No intelligence with that identifier.")
    return found
