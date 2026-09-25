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
    """A FRED binding -- INACTIVE since #56B.

    Kept, not deleted, for two reasons: the FRED-sourced rows it names
    still exist wherever FRED data was ever ingested, and their identity
    must stay resolvable so historical evidence keeps naming FRED
    (ADR-034, Invariant D); and a rollback is a flag flip, not a
    reconstruction. No reader resolves it while it is inactive.
    """
    return ProviderBinding(
        concept_id=concept_obj.concept_id,
        provider="FRED",
        provider_series_id=series_id,
        storage_series_id=series_id,
        active=False,
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


def _census_resconst(
    concept_obj: EconomicConcept,
    category_code: str,
    basis: str,
) -> ProviderBinding:
    """One New Residential Construction series (Increment #45).

    `provider_series_id` is Census's OWN vocabulary for the series --
    `category_code` plus `data_type_code`, e.g. `APERMITS/TOTAL` -- and
    it is the only place those codes belong. Nothing in methodology or
    presentation code may read them.

    `storage_series_id` is MacroChipz's concept id. Unlike the FRED
    bindings above (where the two are equal because #38 did not rewrite
    history), a provider added AFTER #38 has no legacy rows to preserve,
    so it stores MacroChipz's own identity from the first write and the
    ambiguity documented in economic-concept-identity.md section 6 is
    not extended to a third shape.

    `canonical_unit_factor` is 1000: Census publishes thousands of
    units, MacroChipz reasons in units. Exactly the conversion the
    `PAYEMS` binding above already performs, and for the same reason --
    the scaling is a property of the provider, not of the concept.
    """
    return ProviderBinding(
        concept_id=concept_obj.concept_id,
        provider="CENSUS",
        provider_series_id=f"{category_code}/TOTAL",
        storage_series_id=concept_obj.concept_id,
        provider_native_unit="Thousands of Units",
        canonical_unit_factor=1000.0,
        equivalence_basis=basis,
    )


def _first_party(
    concept_obj: EconomicConcept,
    provider: str,
    provider_series_id: str,
    native_unit: str,
    factor: float,
    basis: str,
) -> ProviderBinding:
    """A BLS or BEA binding for an Inflation or Jobs concept (Increment
    #56A, audited in #54B).

    ACTIVE since #56B, which moved release processing and the release
    schedule to BLS and BEA and flipped the flag. Every reader now
    resolves these concept-keyed rows; the FRED binding for the same
    concept is kept inactive (see `_fred`). The rows are first populated
    by `app.operations.import_first_party` (a baseline) and then kept
    current by release processing.

    `storage_series_id` is the concept id, as for Census: a provider
    added after #38 has no legacy rows to preserve. FRED's rows keep
    their own ids and their own history; nothing is relabelled.

    Values are stored in the provider's NATIVE unit, exactly as the
    FRED binding for the same concept does, so the conversion factor --
    and therefore `labor_v1.0`'s golden vectors -- is identical across
    the two. (Census converts at write time; copying that here would
    double-convert payrolls.)
    """
    return ProviderBinding(
        concept_id=concept_obj.concept_id,
        provider=provider,
        provider_series_id=provider_series_id,
        storage_series_id=concept_obj.concept_id,
        provider_native_unit=native_unit,
        canonical_unit_factor=factor,
        equivalence_basis=basis,
        active=True,
    )


#: Every binding MacroChipz currently has: six Treasury, six Census and
#: six BLS/BEA (active), and six FRED (inactive since #56B).
#:
#: The BLS and BEA bindings at the end were added by #56A only after
#: #54B verified each identifier against the agency's own documentation
#: and every stored value against the agency's own data -- not from the
#: names. Unverified bindings would be exactly the fabricated equivalence
#: this module exists to prevent.
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
    # ----------------------------------------------------------------
    # Census New Residential Construction (Increment #45).
    #
    # No frozen methodology cites these series, because none exists --
    # so unlike every binding above, the equivalence cannot be recorded
    # from an earlier methodology decision. It is asserted here instead
    # from CENSUS'S OWN PUBLISHED DEFINITIONS, verified against the
    # dataset's live metadata and the monthly release's explanatory
    # notes rather than from the code names, which is what
    # `equivalence_basis` exists to carry.
    # ----------------------------------------------------------------
    _census_resconst(
        CONCEPTS["us.housing.units-authorized.saar.monthly"],
        "APERMITS",
        "Census `resconst` category APERMITS, data type TOTAL, seasonally_adj=yes. A building permit is "
        "\"the approval given by a local jurisdiction to proceed on a construction project\" (Building Permits "
        "Survey definitions); the series counts privately-owned housing units so authorized. Verified against "
        "the New Residential Construction release for August 2026, which reports permits at a seasonally "
        "adjusted annual rate of 1,394,000 and a revised July rate of 1,433,000 -- the exact values this "
        "series carries as 1394 and 1433 thousands of units.",
    ),
    _census_resconst(
        CONCEPTS["us.housing.units-started.saar.monthly"],
        "ASTARTS",
        "Census `resconst` category ASTARTS, data type TOTAL, seasonally_adj=yes. \"Start of construction "
        "occurs when excavation begins for the footings or foundation of a building\" (Survey of Construction "
        "definitions), privately-owned units only. Verified against the August 2026 release: starts at a "
        "seasonally adjusted annual rate of 1,275,000 and a revised July estimate of 1,309,000, matching this "
        "series' 1275 and 1309 thousands of units.",
    ),
    _census_resconst(
        CONCEPTS["us.housing.units-completed.saar.monthly"],
        "ACOMPLETIONS",
        "Census `resconst` category ACOMPLETIONS, data type TOTAL, seasonally_adj=yes. \"A house is defined as "
        "completed when all finished flooring has been installed\"; in buildings with two or more units, all "
        "units count as completed \"when 50 percent or more of the units are occupied or available for "
        "occupancy\" (Survey of Construction definitions). Verified against the August 2026 release: "
        "completions at 1,128,000 and a revised July estimate of 1,280,000, matching 1128 and 1280.",
    ),
    _census_resconst(
        CONCEPTS["us.housing.units-authorized.nsa.monthly"],
        "PERMITS",
        "Census `resconst` category PERMITS, data type TOTAL, seasonally_adj=no. The SAME economic universe as "
        "the APERMITS binding above -- privately-owned housing units authorized -- published as the month's "
        "actual count rather than as a seasonally adjusted annual rate. A DISTINCT concept for that reason: "
        "the two are not interchangeable and must never be compared with each other.",
    ),
    _census_resconst(
        CONCEPTS["us.housing.units-started.nsa.monthly"],
        "STARTS",
        "Census `resconst` category STARTS, data type TOTAL, seasonally_adj=no. The same universe as the "
        "ASTARTS binding, published as the month's actual count. Distinct concept, same reasoning.",
    ),
    _census_resconst(
        CONCEPTS["us.housing.units-completed.nsa.monthly"],
        "COMPLETIONS",
        "Census `resconst` category COMPLETIONS, data type TOTAL, seasonally_adj=no. The same universe as the "
        "ACOMPLETIONS binding, published as the month's actual count. Distinct concept, same reasoning.",
    ),
    # ----------------------------------------------------------------
    # First-party BLS and BEA (Increment #56A; ACTIVE since #56B) -- see
    # `_first_party`. Each basis records what #54B verified: the
    # agency's own identifier and definition, and an exact value match
    # against every stored FRED observation (358 of 358, including the
    # October 2025 gaps), because FRED redistributes exactly these series.
    # ----------------------------------------------------------------
    _first_party(
        CONCEPTS["us.cpi.headline.price-index.sa.monthly"],
        "BLS",
        "CUSR0000SA0",
        "Index 1982-1984=100",
        1.0,
        "BLS CPI series CUSR0000SA0: CPI-U, U.S. city average, all items, seasonally adjusted (S), monthly (R), "
        "1982-84=100 (bls.gov/help/hlpforma.htm series format). The series FRED republishes as CPIAUCSL: all 60 "
        "stored months match exactly, including the October 2025 month BLS did not collect.",
    ),
    _first_party(
        CONCEPTS["us.cpi.core.price-index.sa.monthly"],
        "BLS",
        "CUSR0000SA0L1E",
        "Index 1982-1984=100",
        1.0,
        "BLS CPI series CUSR0000SA0L1E: CPI-U, all items less food and energy (item SA0L1E), seasonally "
        "adjusted, monthly, 1982-84=100. Republished by FRED as CPILFESL; all 60 stored months match exactly.",
    ),
    _first_party(
        CONCEPTS["us.nonfarm.payroll-employment.sa.monthly"],
        "BLS",
        "CES0000000001",
        "Thousands of Persons",
        # Same native unit and factor as the PAYEMS binding: CES publishes
        # total nonfarm employment in thousands (159075 = 159,075,000 jobs).
        1000.0,
        "BLS CES series CES0000000001: Current Employment Statistics, total nonfarm, all employees (data type "
        "01), seasonally adjusted, in thousands. The establishment survey's JOBS count -- the same universe as "
        "the concept, not the household survey. Republished by FRED as PAYEMS; all 60 stored months match.",
    ),
    _first_party(
        CONCEPTS["us.unemployment-rate.sa.monthly"],
        "BLS",
        "LNS14000000",
        "Percent",
        1.0,
        "BLS CPS series LNS14000000: Current Population Survey unemployment rate (U-3), 16 years and over, "
        "seasonally adjusted, percent. Republished by FRED as UNRATE; all 60 stored months match, including "
        "October 2025, which CPS did not collect.",
    ),
    _first_party(
        CONCEPTS["us.pce.headline.price-index.sa.monthly"],
        "BEA",
        "DPCERG",
        "Index 2017=100",
        1.0,
        "BEA NIPA Table 2.8.4 line 1, series DPCERG: chain-type (Fisher) price index for personal consumption "
        "expenditures, seasonally adjusted, monthly, 2017=100 (BEA SeriesRegister). FRED cites the same account "
        "code for PCEPI; all 59 stored months match exactly.",
    ),
    _first_party(
        CONCEPTS["us.pce.core.price-index.sa.monthly"],
        "BEA",
        "DPCCRG",
        "Index 2017=100",
        1.0,
        "BEA NIPA Table 2.8.4 line 25, series DPCCRG: PCE excluding food and energy, chain-type price index, "
        "seasonally adjusted, monthly, 2017=100 (BEA SeriesRegister). Republished by FRED as PCEPILFE; all 59 "
        "stored months match exactly.",
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
