"""The canonical economic concept registry (Increment #38, ADR-034).

A CONCEPT is what MacroChipz means, independent of who publishes it.
A BINDING is where a compatible observation currently comes from.
Keeping those apart is the whole point of this module: before #38,
`PAYEMS` -- a FRED identifier -- was MacroChipz's canonical identity for
total nonfarm employment, so migrating the source would have meant
migrating the identity, and evidence would have gone on naming FRED for
numbers FRED no longer supplied.

Code-defined, not database-defined, and deliberately so. Frozen
methodologies depend on these identities, so they must be type-checked,
versioned with the code that uses them, and incapable of changing
without a deploy and a test run. The database records which concept a
stored series BELONGS to (`economic_series.concept_id`); it does not get
to decide what a concept IS.

Two rules that matter more than the table below:

1. A concept identifier is OPAQUE. It is readable for a human reading a
   log, but nothing parses it to recover an attribute -- attributes are
   fields. Discovering that an attribute was wrong must not force a
   rename of an identifier that is supposed to be stable forever.

2. Equivalence is asserted from SEMANTICS, never from label similarity.
   BLS's own documentation is explicit that CES counts *jobs* ("multiple
   jobholders are counted for each nonfarm payroll job") while CPS counts
   *employed people* ("counted only once"). A registry that cannot
   express that distinction will eventually be used to assert something
   false, which is why `universe` is a required field rather than a
   comment.
"""

from dataclasses import dataclass


class UnknownConceptError(LookupError):
    """A concept identifier that is not registered. Always an error --
    never a `None` that flows onward as missing data."""


@dataclass(frozen=True, slots=True)
class EconomicConcept:
    """One economic idea MacroChipz has a canonical opinion about.

    Every field exists to prevent an accidental semantic substitution.
    Two series are interchangeable only when all of these agree, and
    `ProviderBinding` records the evidence that they do.
    """

    concept_id: str
    #: Human-readable, for logs and documentation. Never an identity.
    name: str
    #: The MacroChipz economic world this belongs to.
    world: str
    #: MONTHLY | DAILY_BUSINESS -- the publication frequency the
    #: methodologies assume. A monthly methodology fed a daily series
    #: would compute confidently and wrongly.
    frequency: str
    #: The unit MacroChipz reasons in. A binding declares the provider's
    #: native unit and the conversion, so the conversion lives with the
    #: provider rather than with the concept.
    canonical_unit: str
    #: SEASONALLY_ADJUSTED | NOT_SEASONALLY_ADJUSTED | NOT_APPLICABLE.
    #: Mixing adjusted and unadjusted series in one methodology is a
    #: classic, silent, entirely plausible error.
    seasonal_adjustment: str
    geography: str
    #: WHAT is counted -- jobs, people, prices, yields. The CES/CPS
    #: distinction above lives here.
    universe: str
    #: The statistical program that defines the concept (CES, CPS, CPI,
    #: PCE, TREASURY_PAR_YIELD). Two programs measuring "employment" do
    #: not measure the same thing.
    source_program: str


# --------------------------------------------------------------------
# Inflation (inflation_v1.0)
# --------------------------------------------------------------------

CORE_PCE_PRICE_INDEX = EconomicConcept(
    concept_id="us.pce.core.price-index.sa.monthly",
    name="Core PCE price index (excluding food and energy)",
    world="inflation",
    frequency="MONTHLY",
    canonical_unit="INDEX",
    seasonal_adjustment="SEASONALLY_ADJUSTED",
    geography="US",
    universe="PERSONAL_CONSUMPTION_PRICES_EX_FOOD_ENERGY",
    source_program="PCE",
)

CORE_CPI_PRICE_INDEX = EconomicConcept(
    concept_id="us.cpi.core.price-index.sa.monthly",
    name="Core CPI-U price index (excluding food and energy)",
    world="inflation",
    frequency="MONTHLY",
    canonical_unit="INDEX",
    seasonal_adjustment="SEASONALLY_ADJUSTED",
    geography="US",
    universe="URBAN_CONSUMER_PRICES_EX_FOOD_ENERGY",
    source_program="CPI",
)

HEADLINE_PCE_PRICE_INDEX = EconomicConcept(
    concept_id="us.pce.headline.price-index.sa.monthly",
    name="Headline PCE price index",
    world="inflation",
    frequency="MONTHLY",
    canonical_unit="INDEX",
    seasonal_adjustment="SEASONALLY_ADJUSTED",
    geography="US",
    universe="PERSONAL_CONSUMPTION_PRICES_ALL_ITEMS",
    source_program="PCE",
)

HEADLINE_CPI_PRICE_INDEX = EconomicConcept(
    concept_id="us.cpi.headline.price-index.sa.monthly",
    name="Headline CPI-U price index (all items)",
    world="inflation",
    frequency="MONTHLY",
    canonical_unit="INDEX",
    seasonal_adjustment="SEASONALLY_ADJUSTED",
    geography="US",
    universe="URBAN_CONSUMER_PRICES_ALL_ITEMS",
    source_program="CPI",
)

# --------------------------------------------------------------------
# Labor (labor_v1.0)
# --------------------------------------------------------------------

NONFARM_PAYROLL_EMPLOYMENT = EconomicConcept(
    concept_id="us.nonfarm.payroll-employment.sa.monthly",
    name="Total nonfarm payroll employment",
    world="labor",
    frequency="MONTHLY",
    # The methodology reasons in jobs; the FRED binding declares the
    # thousands-of-persons conversion. Units belong to the binding.
    canonical_unit="JOBS",
    seasonal_adjustment="SEASONALLY_ADJUSTED",
    geography="US",
    # JOBS, not PEOPLE. This is the CES/CPS distinction, and it is the
    # reason a "total employment" series from the household survey is
    # NOT a valid alternative binding for this concept.
    universe="NONFARM_PAYROLL_JOBS",
    source_program="CES",
)

UNEMPLOYMENT_RATE = EconomicConcept(
    concept_id="us.unemployment-rate.sa.monthly",
    name="Unemployment rate (U-3)",
    world="labor",
    frequency="MONTHLY",
    canonical_unit="PERCENT",
    seasonal_adjustment="SEASONALLY_ADJUSTED",
    geography="US",
    # PEOPLE, from the household survey -- deliberately a different
    # universe from the payroll concept above.
    universe="CIVILIAN_LABOR_FORCE_PERSONS",
    source_program="CPS",
)

# --------------------------------------------------------------------
# Rates (rates_v1.0)
#
# These concept identifiers deliberately REUSE the identifiers Increment
# #29 already chose (`UST_NOMINAL_10Y`, never FRED's `DGS10`). They were
# already source-neutral, MacroChipz-owned identities -- #29 solved this
# problem correctly for Rates before it was named -- and they are
# persisted in `economic_series.series_id`. Renaming them would be a
# data migration that buys nothing but naming symmetry, which §9 of the
# #38 brief explicitly rules out.
# --------------------------------------------------------------------


def _treasury_par_yield(concept_id: str, name: str, universe: str) -> EconomicConcept:
    return EconomicConcept(
        concept_id=concept_id,
        name=name,
        world="rates",
        frequency="DAILY_BUSINESS",
        canonical_unit="PERCENT",
        seasonal_adjustment="NOT_APPLICABLE",
        geography="US",
        universe=universe,
        source_program="TREASURY_PAR_YIELD",
    )


NOMINAL_2Y = _treasury_par_yield("UST_NOMINAL_2Y", "2-year Treasury par yield (nominal)", "TREASURY_NOMINAL_PAR_YIELD")
NOMINAL_5Y = _treasury_par_yield("UST_NOMINAL_5Y", "5-year Treasury par yield (nominal)", "TREASURY_NOMINAL_PAR_YIELD")
NOMINAL_10Y = _treasury_par_yield("UST_NOMINAL_10Y", "10-year Treasury par yield (nominal)", "TREASURY_NOMINAL_PAR_YIELD")
NOMINAL_30Y = _treasury_par_yield("UST_NOMINAL_30Y", "30-year Treasury par yield (nominal)", "TREASURY_NOMINAL_PAR_YIELD")
REAL_5Y = _treasury_par_yield("UST_REAL_5Y", "5-year Treasury par real yield (TIPS)", "TREASURY_REAL_PAR_YIELD")
REAL_10Y = _treasury_par_yield("UST_REAL_10Y", "10-year Treasury par real yield (TIPS)", "TREASURY_REAL_PAR_YIELD")


#: Every concept MacroChipz currently has a canonical opinion about.
#: Deliberately not "every concept we might one day want" -- an
#: unregistered concept is an error, and a registry full of aspirational
#: entries cannot distinguish the two.
CONCEPTS: dict[str, EconomicConcept] = {
    concept.concept_id: concept
    for concept in (
        CORE_PCE_PRICE_INDEX,
        CORE_CPI_PRICE_INDEX,
        HEADLINE_PCE_PRICE_INDEX,
        HEADLINE_CPI_PRICE_INDEX,
        NONFARM_PAYROLL_EMPLOYMENT,
        UNEMPLOYMENT_RATE,
        NOMINAL_2Y,
        NOMINAL_5Y,
        NOMINAL_10Y,
        NOMINAL_30Y,
        REAL_5Y,
        REAL_10Y,
    )
}


def concept(concept_id: str) -> EconomicConcept:
    """The registered concept, or `UnknownConceptError`.

    Raising rather than returning `None` is deliberate: an unregistered
    concept is a programming error, and letting it flow onward as
    missing data would produce a confident `INSUFFICIENT_DATA` that
    looks like an economic finding.
    """
    try:
        return CONCEPTS[concept_id]
    except KeyError:
        raise UnknownConceptError(f"Unregistered economic concept: {concept_id!r}") from None
