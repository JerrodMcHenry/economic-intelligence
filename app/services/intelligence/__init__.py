"""The Structured Intelligence Layer (Increment #39).

    SOURCE DATA -> DETERMINISTIC ENGINE -> STRUCTURED INTELLIGENCE -> SURFACES

One canonical representation of what MacroChipz knows, so that every
consumer surface renders the same account of reality instead of each
re-deriving it from domain results.

A PROJECTION, never a source of truth. Generated on read from
already-persisted canonical data; nothing here is stored, and nothing
here may invent a fact the engine did not produce.
"""

from app.services.intelligence.builder import IntelligenceBuilder, sort_intelligence
from app.services.intelligence.service import IntelligenceService

__all__ = ["IntelligenceBuilder", "IntelligenceService", "sort_intelligence"]
