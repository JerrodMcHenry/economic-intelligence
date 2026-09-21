"""Read-side orchestration for Structured Intelligence (Increment #39).

Thin by design: the builder owns construction, this owns bounding and
lookup. Keeping them apart is what lets the API route stay a transport
concern -- it selects and paginates, it never decides what happened.
"""

from sqlalchemy.orm import Session

from app.models.intelligence import IntelligenceListResponse, IntelligenceObject, IntelligenceType, World
from app.services.intelligence.builder import IntelligenceBuilder

#: Hard ceiling on a single page. A collection endpoint over canonical
#: data must never be able to return an unbounded payload, however the
#: caller asks.
MAX_LIMIT = 100
DEFAULT_LIMIT = 25


class IntelligenceService:
    def __init__(self, builder: IntelligenceBuilder | None = None) -> None:
        self._builder = builder or IntelligenceBuilder()

    def list_intelligence(
        self,
        session: Session,
        *,
        world: World | None = None,
        intelligence_type: IntelligenceType | None = None,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
    ) -> IntelligenceListResponse:
        """A bounded, deterministically ordered page.

        Filtering happens after generation because generation is cheap
        and deterministic; pushing filters into the builder would give
        two code paths that could disagree about what exists.
        """
        bounded_limit = max(1, min(limit, MAX_LIMIT))
        bounded_offset = max(0, offset)

        objects = self._builder.build_all(session)
        if world is not None:
            objects = [obj for obj in objects if obj.world == world]
        if intelligence_type is not None:
            objects = [obj for obj in objects if obj.type == intelligence_type]

        return IntelligenceListResponse(
            items=objects[bounded_offset : bounded_offset + bounded_limit],
            total=len(objects),
            limit=bounded_limit,
            offset=bounded_offset,
        )

    def get_intelligence(self, session: Session, intelligence_id: str) -> IntelligenceObject | None:
        """One object by its stable id, or `None`.

        Looked up by regenerating and matching rather than by parsing
        the id: an id is an identifier, not a query language, and
        decoding one would make the format load-bearing in a second
        place.
        """
        for obj in self._builder.build_all(session):
            if obj.id == intelligence_id:
                return obj
        return None
