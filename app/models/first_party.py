"""First-party Inflation and Jobs sources (Increment #56A).

Everything about WHERE a first-party value came from that provenance
records, keyed by concept. Provider series identifiers are NOT here --
they live in `app/concepts/bindings.py`, the one place provider
vocabulary is allowed (ADR-034); this module reads them from there.
"""

from dataclasses import dataclass

PROVIDER_BLS = "BLS"
PROVIDER_BEA = "BEA"

#: Calendar years imported by default, counting the current one: 2017
#: onward as of 2026. Exactly BLS v1's per-query maximum, so the keyless
#: path needs one request.
DEFAULT_IMPORT_YEARS = 10


@dataclass(frozen=True)
class FirstPartySource:
    provider: str
    #: The survey or table, in the provider's own terms.
    dataset: str
    title: str
    #: Stored on the series row -- the provider's native unit, as the
    #: FRED row for the same concept stores it.
    units: str


BLS_CONCEPT_IDS: tuple[str, ...] = (
    "us.cpi.headline.price-index.sa.monthly",
    "us.cpi.core.price-index.sa.monthly",
    "us.nonfarm.payroll-employment.sa.monthly",
    "us.unemployment-rate.sa.monthly",
)

BEA_CONCEPT_IDS: tuple[str, ...] = (
    "us.pce.headline.price-index.sa.monthly",
    "us.pce.core.price-index.sa.monthly",
)

FIRST_PARTY_CONCEPT_IDS: tuple[str, ...] = (*BLS_CONCEPT_IDS, *BEA_CONCEPT_IDS)

SOURCES: dict[str, FirstPartySource] = {
    "us.cpi.headline.price-index.sa.monthly": FirstPartySource(
        PROVIDER_BLS, "CPI-U", "Consumer Price Index, All Urban Consumers: All Items (SA)", "Index 1982-1984=100"
    ),
    "us.cpi.core.price-index.sa.monthly": FirstPartySource(
        PROVIDER_BLS,
        "CPI-U",
        "Consumer Price Index, All Urban Consumers: All Items Less Food and Energy (SA)",
        "Index 1982-1984=100",
    ),
    "us.nonfarm.payroll-employment.sa.monthly": FirstPartySource(
        PROVIDER_BLS, "CES", "All Employees, Total Nonfarm (SA)", "Thousands of Persons"
    ),
    "us.unemployment-rate.sa.monthly": FirstPartySource(
        PROVIDER_BLS, "CPS", "Unemployment Rate, 16 Years and Over (SA)", "Percent"
    ),
    "us.pce.headline.price-index.sa.monthly": FirstPartySource(
        PROVIDER_BEA,
        "NIPA T20804",
        "Personal Consumption Expenditures: Chain-type Price Index (SA)",
        "Index 2017=100",
    ),
    "us.pce.core.price-index.sa.monthly": FirstPartySource(
        PROVIDER_BEA,
        "NIPA T20804",
        "PCE Excluding Food and Energy: Chain-type Price Index (SA)",
        "Index 2017=100",
    ),
}


def source_url(provider: str, provider_series_id: str) -> str:
    """A public landing page for provenance -- never an API endpoint, so
    a stored URL can never carry a credential."""
    if provider == PROVIDER_BLS:
        return f"https://data.bls.gov/timeseries/{provider_series_id}"
    if provider == PROVIDER_BEA:
        from app.clients.bea import NIPA_MONTHLY_URL

        return NIPA_MONTHLY_URL
    raise ValueError(f"not a first-party provider: {provider!r}")
