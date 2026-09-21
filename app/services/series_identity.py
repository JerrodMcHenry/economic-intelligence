"""Resolving who a canonical series actually is (Increment #38, ADR-034).

One small helper, used by every service that feeds a frozen methodology.
It exists because the answer has two cases and only one of them is
about data:

- The series IS persisted. Identity comes entirely from the stored row:
  the concept it supplies, the provider that supplied it, and that
  provider's own identifier. This is the honest case, and it is what
  makes a future provider cutover safe -- observations written by FRED
  keep naming FRED even after the active binding moves to BLS.

- The series is NOT persisted at all. There are no observations, so no
  provenance claim is being made about any real value. Identity falls
  back to the ACTIVE BINDING: "this is the concept we looked for, at the
  provider we would have looked at, and nothing was there." The
  methodologies already treat an absent series exactly like a persisted
  one with no usable observations, and this keeps that behaviour intact
  rather than raising in a path whose whole purpose is to return
  `INSUFFICIENT_DATA`.

The distinction matters: the fallback may never be used for a series
that DOES have observations, because that is precisely how evidence
would start naming a provider that did not supply the data.
"""

from app.concepts.bindings import active_binding
from app.models.series import SeriesIdentity
from app.repositories.series_repository import SeriesRepository


def resolve_identity(repo: SeriesRepository, concept_id: str) -> SeriesIdentity:
    """The stored identity for a concept, or the active binding's
    identity when nothing is persisted for it yet."""
    binding = active_binding(concept_id)
    stored = repo.get_identity(binding.storage_series_id)
    if stored is not None:
        return stored
    return SeriesIdentity(
        concept_id=binding.concept_id,
        provider=binding.provider,
        provider_series_id=binding.provider_series_id,
    )


def expected_identity(concept_id: str) -> SeriesIdentity:
    """The active binding's identity, without touching the database.

    For paths that genuinely have no session-backed series row to read
    -- and therefore no observations whose provenance could be
    misattributed. Never a substitute for `resolve_identity` where a row
    is available.
    """
    binding = active_binding(concept_id)
    return SeriesIdentity(
        concept_id=binding.concept_id,
        provider=binding.provider,
        provider_series_id=binding.provider_series_id,
    )
