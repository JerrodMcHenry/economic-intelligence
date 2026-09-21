"""Provider bindings: where a compatible observation currently comes
from (Increment #38, ADR-034).

A binding is a claim of SEMANTIC EQUIVALENCE between one provider's
series and one MacroChipz concept, and `equivalence_basis` is where that
claim has to be justified in words. "The names match" is not a
justification. Every binding below cites the frozen methodology that
already uses that series for that role -- which is the strongest
possible basis, because the equivalence is not being asserted now, it is
being *recorded* from a decision the methodology froze earlier.

Bindings live here rather than inside provider adapters only because no
adapters exist yet (they arrive in #M1). When they do, each binding
moves next to the adapter that uses it. The shape is already the one
Rates proved in #29: `app/models/rates.py`'s `NOMINAL_FIELD_MAP` is "the
one place the provider's own column vocabulary is mapped into ours", and
this module generalises it rather than inventing a second style.

DUAL BINDINGS are supported by design (ADR-034, Invariant E): a concept
may have more than one registered binding, exactly one of which is
`active`. That is how a future BLS migration gets verified -- ingest
both, compare over overlapping history, flip the flag -- and how it gets
rolled back if the comparison fails.
"""

from dataclasses import dataclass

from app.concepts.registry import CONCEPTS, EconomicConcept, concept


class UnknownBindingError(LookupError):
    """No registered binding matches. Never silently treated as "no data"."""


class AmbiguousBindingError(LookupError):
    """More than one active binding for a concept, or one stored series
    claimed by two concepts. Always a registry bug, never something to
    resolve by picking the first match."""


@dataclass(frozen=True, slots=True)
class ProviderBinding:
    """One provider's series, bound to one MacroChipz concept."""

    concept_id: str
    #: The provider that publishes it: FRED, TREASURY, and later BLS/BEA/CENSUS.
    provider: str
    #: How the PROVIDER identifies this series in its own vocabulary.
    #: For FRED that is `PAYEMS`. For Treasury it is the XML column
    #: `BC_10YEAR` -- not `UST_NOMINAL_10Y`, which is ours.
    provider_series_id: str
    #: The value stored in `economic_series.series_id` for this binding.
    #:
    #: For FRED these are equal, because #38 did not rewrite historical
    #: rows. For Treasury they differ, because #29 stored MacroChipz's
    #: own identifier there. That asymmetry is a real, pre-existing
    #: ambiguity in `economic_series.series_id`, documented rather than
    #: migrated -- see docs/architecture/economic-concept-identity.md.
    storage_series_id: str
    #: The unit the provider publishes in, before any conversion to the
    #: concept's `canonical_unit`.
    provider_native_unit: str
    #: Multiply a provider value by this to reach the canonical unit.
    #: Exactly 1.0 where no conversion is needed. The conversion belongs
    #: to the binding because a different provider may publish the same
    #: concept in different units.
    canonical_unit_factor: float
    #: Why this provider series genuinely measures this concept.
    equivalence_basis: str
    #: Exactly one active binding per concept.
    active: bool = True


def _fred(concept_obj: EconomicConcept, series_id: str, native_unit: str, factor: float, basis: str) -> ProviderBinding:
    return ProviderBinding(
        concept_id=concept_obj.concept_id,
        provider="FRED",
        provider_series_id=series_id,
        storage_series_id=series_id,
        provider_native_unit=native_unit,
        canonical_unit_factor=factor,
        equivalence_basis=basis,
    )


def _treasury(concept_obj: EconomicConcept, field: str, basis: str) -> ProviderBinding:
    return ProviderBinding(
        concept_id=concept_obj.concept_id,
        provider="TREASURY",
        provider_series_id=field,
        storage_series_id=concept_obj.concept_id,
        provider_native_unit="Percent",
        canonical_unit_factor=1.0,
        equivalence_basis=basis,
    )


#: Every binding MacroChipz currently has. Twelve, matching the twelve
#: series actually persisted -- six FRED, six Treasury.
#:
#: No speculative BLS or BEA bindings appear here. Their identifiers and
#: unit semantics have not been verified against the agencies' own
#: documentation, and inventing them would be exactly the fabricated
#: equivalence this module exists to prevent. #M2/#M3 add them, with
#: evidence.
BINDINGS: tuple[ProviderBinding, ...] = (
    _fred(
        CONCEPTS["us.pce.core.price-index.sa.monthly"],
        "PCEPILFE",
        "Index 2017=100",
        1.0,
        "inflation_v1.0 uses this series as its PRIMARY underlying-momentum input "
        "(docs/methodology/inflation-monitor-v1.0.md). Core PCE, seasonally adjusted, monthly index.",
    ),
    _fred(
        CONCEPTS["us.cpi.core.price-index.sa.monthly"],
        "CPILFESL",
        "Index 1982-1984=100",
        1.0,
        "inflation_v1.0 uses this series as its CONFIRMATION input. Core CPI-U, seasonally adjusted, "
        "monthly index. Confirms Core PCE; never substitutes for it -- different program, different basket.",
    ),
    _fred(
        CONCEPTS["us.pce.headline.price-index.sa.monthly"],
        "PCEPI",
        "Index 2017=100",
        1.0,
        "inflation_v1.0 uses this series for BOTH the Fed-objective target comparison and headline PCE "
        "momentum context -- two roles, one series, as the frozen hierarchy specifies.",
    ),
    _fred(
        CONCEPTS["us.cpi.headline.price-index.sa.monthly"],
        "CPIAUCSL",
        "Index 1982-1984=100",
        1.0,
        "inflation_v1.0 uses this series for headline CPI context only. All items, urban consumers, "
        "seasonally adjusted.",
    ),
    _fred(
        CONCEPTS["us.nonfarm.payroll-employment.sa.monthly"],
        "PAYEMS",
        "Thousands of Persons",
        # The ONE conversion constant labor_v1.0 depends on, moved here
        # from `app/models/labor.py` where it was documented as "FRED's
        # native Thousands of Persons" -- i.e. it was always a property
        # of the provider, not of the concept.
        1000.0,
        "labor_v1.0's employment component is defined over this series (research/labor_momentum/"
        "LABOR_V1_FROZEN_METHODOLOGY.md §2). CES establishment survey: nonfarm payroll JOBS, not persons.",
    ),
    _fred(
        CONCEPTS["us.unemployment-rate.sa.monthly"],
        "UNRATE",
        "Percent",
        1.0,
        "labor_v1.0's unemployment component is defined over this series. CPS household survey, U-3, "
        "seasonally adjusted, already a rate -- no conversion.",
    ),
    _treasury(
        CONCEPTS["UST_NOMINAL_2Y"],
        "BC_2YEAR",
        "rates_v1.0 nominal curve; mapped from the Treasury daily par yield XML field by "
        "app/models/rates.py's NOMINAL_FIELD_MAP (Increment #29).",
    ),
    _treasury(
        CONCEPTS["UST_NOMINAL_5Y"],
        "BC_5YEAR",
        "rates_v1.0 nominal curve; NOMINAL_FIELD_MAP (Increment #29).",
    ),
    _treasury(
        CONCEPTS["UST_NOMINAL_10Y"],
        "BC_10YEAR",
        "rates_v1.0 nominal curve; NOMINAL_FIELD_MAP (Increment #29).",
    ),
    _treasury(
        CONCEPTS["UST_NOMINAL_30Y"],
        "BC_30YEAR",
        "rates_v1.0 nominal curve; NOMINAL_FIELD_MAP (Increment #29).",
    ),
    _treasury(
        CONCEPTS["UST_REAL_5Y"],
        "TC_5YEAR",
        "rates_v1.0 real curve; mapped by REAL_FIELD_MAP (Increment #29). TIPS par real yield.",
    ),
    _treasury(
        CONCEPTS["UST_REAL_10Y"],
        "TC_10YEAR",
        "rates_v1.0 real curve; REAL_FIELD_MAP (Increment #29). TIPS par real yield.",
    ),
)


def active_binding(concept_id: str) -> ProviderBinding:
    """The single active binding for a concept.

    Raises rather than returning `None`: a concept with no active
    binding is a startup-time configuration error (ADR-034, Invariant 6),
    not a runtime absence of data.
    """
    concept(concept_id)  # Validates the concept exists first, with a better error.
    matches = [binding for binding in BINDINGS if binding.concept_id == concept_id and binding.active]
    if not matches:
        raise UnknownBindingError(f"No active provider binding for concept {concept_id!r}")
    if len(matches) > 1:
        raise AmbiguousBindingError(
            f"{len(matches)} active bindings for concept {concept_id!r}; exactly one must be active"
        )
    return matches[0]


def bindings_for_concept(concept_id: str) -> tuple[ProviderBinding, ...]:
    """Every binding for a concept, active or not -- the dual-binding
    view a migration comparison reads."""
    concept(concept_id)
    return tuple(binding for binding in BINDINGS if binding.concept_id == concept_id)


def concept_id_for_stored_series(storage_series_id: str) -> str:
    """The concept a persisted `economic_series` row belongs to.

    This is the function the backfill uses, and it is deliberately
    strict: an unmapped or doubly-claimed stored series raises rather
    than guessing. Inferring identity from a display label is exactly
    what ADR-034 forbids.
    """
    matches = {binding.concept_id for binding in BINDINGS if binding.storage_series_id == storage_series_id}
    if not matches:
        raise UnknownBindingError(f"No concept binding for stored series {storage_series_id!r}")
    if len(matches) > 1:
        raise AmbiguousBindingError(
            f"Stored series {storage_series_id!r} is claimed by {len(matches)} concepts: {sorted(matches)}"
        )
    return matches.pop()
