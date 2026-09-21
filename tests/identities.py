"""Canonical `SeriesIdentity` fixtures for tests (Increment #38).

Production code NEVER builds an identity from a constant -- it reads one
from the persisted series row, which is the entire point of ADR-034 and
the reason `app/services/series_identity.py` exists. These constants are
deliberately confined to the test tree, where the inputs are synthetic
observation lists with no persisted row behind them and therefore no
provenance to misattribute.

`tests/test_concept_identity_boundary.py` guards the production rule;
this module exists only so a domain test can call a pure function
without standing up a database.
"""

from app.concepts.bindings import active_binding
from app.models.inflation import (
    CONFIRMATION_CONCEPT_ID,
    HEADLINE_CPI_CONCEPT_ID,
    InflationSeriesIdentities,
    PRIMARY_CONCEPT_ID,
    TARGET_CONCEPT_ID,
)
from app.models.labor import EMPLOYMENT_CONCEPT_ID, LaborSeriesIdentities, UNEMPLOYMENT_CONCEPT_ID
from app.models.series import SeriesIdentity


def identity_for(concept_id: str) -> SeriesIdentity:
    """The active binding's identity, as the application would resolve
    it for a concept with nothing yet persisted."""
    binding = active_binding(concept_id)
    return SeriesIdentity(
        concept_id=binding.concept_id,
        provider=binding.provider,
        provider_series_id=binding.provider_series_id,
    )


PRIMARY_IDENTITY = identity_for(PRIMARY_CONCEPT_ID)
CONFIRMATION_IDENTITY = identity_for(CONFIRMATION_CONCEPT_ID)
TARGET_IDENTITY = identity_for(TARGET_CONCEPT_ID)
HEADLINE_CPI_IDENTITY = identity_for(HEADLINE_CPI_CONCEPT_ID)
EMPLOYMENT_IDENTITY = identity_for(EMPLOYMENT_CONCEPT_ID)
UNEMPLOYMENT_IDENTITY = identity_for(UNEMPLOYMENT_CONCEPT_ID)

INFLATION_IDENTITIES = InflationSeriesIdentities(
    primary=PRIMARY_IDENTITY,
    confirmation=CONFIRMATION_IDENTITY,
    target=TARGET_IDENTITY,
    headline_cpi=HEADLINE_CPI_IDENTITY,
)

LABOR_IDENTITIES = LaborSeriesIdentities(
    employment=EMPLOYMENT_IDENTITY,
    unemployment=UNEMPLOYMENT_IDENTITY,
)

#: Identity for an arbitrary stored series that is NOT a registered
#: concept -- the shape the generic series endpoints legitimately
#: produce, and the case canonical paths must reject rather than guess.
def unregistered_identity(series_id: str, provider: str = "FRED") -> SeriesIdentity:
    return SeriesIdentity(concept_id=f"unregistered:{series_id}", provider=provider, provider_series_id=series_id)
