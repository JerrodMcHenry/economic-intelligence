"""Source-neutral economic concept identity (Increment #38, ADR-034).

The boundary this package establishes:

    CANONICAL METHODOLOGY
            |  depends on
            v
    ECONOMIC CONCEPT        (registry.py -- what MacroChipz means)
            |  resolved through
            v
    PROVIDER BINDING        (bindings.py -- where a value comes from)
            |
            v
    FRED / TREASURY / future BLS, BEA, Census

Canonical methodology code must not need to know that FRED supplied a
value, and a provider adapter must not get to decide what a methodology
means. Everything above the binding layer speaks in concepts.

Pure: no session, no HTTP, no environment access, no I/O of any kind.
"""

from app.concepts.bindings import (
    AmbiguousBindingError,
    BINDINGS,
    ProviderBinding,
    UnknownBindingError,
    active_binding,
    bindings_for_concept,
    concept_id_for_stored_series,
)
from app.concepts.registry import CONCEPTS, EconomicConcept, UnknownConceptError, concept

__all__ = [
    "AmbiguousBindingError",
    "BINDINGS",
    "CONCEPTS",
    "EconomicConcept",
    "ProviderBinding",
    "UnknownBindingError",
    "UnknownConceptError",
    "active_binding",
    "bindings_for_concept",
    "concept",
    "concept_id_for_stored_series",
]
