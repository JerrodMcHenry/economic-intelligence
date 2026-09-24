"""First-party Inflation and Jobs ingestion from BLS and BEA (Increment #56A).

Populates the concept-keyed BLS/BEA rows behind the six INACTIVE
bindings in `app/concepts/bindings.py`. Nothing reads those rows yet:
monitors, intelligence and every API resolve storage through
`active_binding()`, which remains FRED until #56B. So this service can
run against a live database without changing a single response.

Modelled on `HousingIngestionService`, whose docstring explains the two
rules that matter most here:

- **A first import is a baseline, not a history of observed events.**
  Ten years learned at one instant are recorded `is_backfilled`, decided
  per observation by the same pure `is_baseline_import` Housing uses. So
  the import produces no revision evidence, no intelligence objects, and
  cannot produce a false revision: a revision needs an earlier value in
  the same row, and these rows start empty.
- **Nothing missing is invented.** A period the provider published as
  unavailable is stored as NULL -- exactly as the FRED path stores
  FRED's `.` -- never zero and never carried forward.

Providers are isolated: BLS and BEA are fetched separately, and a
failure in one records a FAILED run for it and writes none of its
observations, while the other proceeds. The caller's single transaction
still makes an interrupted run leave no trace at all (#54A §7).
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.clients.bea import BEAClient
from app.clients.bls import BLSClient
from app.clients.bounded_http import ProviderError
from app.clients.provider_observation import FirstPartyObservation
from app.concepts.bindings import ProviderBinding, UnknownBindingError, bindings_for_concept
from app.domain.housing import is_baseline_import
from app.models.first_party import (
    BEA_CONCEPT_IDS,
    BLS_CONCEPT_IDS,
    DEFAULT_IMPORT_YEARS,
    PROVIDER_BEA,
    PROVIDER_BLS,
    SOURCES,
    source_url,
)
from app.repositories.first_party_repository import FirstPartyProvenanceRecord, FirstPartyRepository

logger = logging.getLogger(__name__)


@dataclass
class SeriesOutcome:
    concept_id: str
    provider_series_id: str
    import_mode: str = "BASELINE_BACKFILL"
    received: int = 0
    inserted: int = 0
    revised: int = 0
    unchanged: int = 0
    unavailable: int = 0
    first_period: date | None = None
    last_period: date | None = None


@dataclass
class ProviderRunOutcome:
    provider: str
    access_mode: str
    status: str
    import_mode: str
    window_start: date
    window_end: date
    source_published_at: datetime | None
    error_class: str | None
    series: list[SeriesOutcome] = field(default_factory=list)


def first_party_binding(concept_id: str, provider: str) -> ProviderBinding:
    """The (inactive) BLS/BEA binding for a concept. Read from the binding
    table, never reconstructed, so the provider identifier has exactly
    one home (ADR-034)."""
    matches = [binding for binding in bindings_for_concept(concept_id) if binding.provider == provider]
    if len(matches) != 1:
        raise UnknownBindingError(f"expected one {provider} binding for {concept_id!r}, found {len(matches)}")
    return matches[0]


class FirstPartyIngestionService:
    def __init__(self, bls_client: BLSClient, bea_client: BEAClient):
        self._bls = bls_client
        self._bea = bea_client

    def import_history(
        self,
        session: Session,
        years: int = DEFAULT_IMPORT_YEARS,
        as_of: date | None = None,
        providers: tuple[str, ...] = (PROVIDER_BLS, PROVIDER_BEA),
    ) -> list[ProviderRunOutcome]:
        """Import `years` calendar years, ending with `as_of`'s year.

        Idempotent: an identical re-run inserts nothing, revises nothing
        and writes no version rows. A later genuine provider revision is
        recorded as the observed REVISED version it is.
        """
        if years < 1:
            raise ValueError("years must be at least 1")
        if PROVIDER_BLS in providers and years > self._bls.max_years:
            raise ValueError(
                f"BLS {self._bls.api_version} serves at most {self._bls.max_years} years per request "
                f"(set BLS_API_KEY for up to 20)"
            )
        unknown = set(providers) - {PROVIDER_BLS, PROVIDER_BEA}
        if unknown:
            raise ValueError(f"unknown providers: {sorted(unknown)}")

        today = as_of or datetime.now(timezone.utc).date()
        window_start = date(today.year - (years - 1), 1, 1)
        repo = FirstPartyRepository(session)

        outcomes = []
        if PROVIDER_BLS in providers:
            outcomes.append(self._run(repo, PROVIDER_BLS, BLS_CONCEPT_IDS, window_start, today))
        if PROVIDER_BEA in providers:
            outcomes.append(self._run(repo, PROVIDER_BEA, BEA_CONCEPT_IDS, window_start, today))
        return outcomes

    # ------------------------------------------------------------------

    def _run(
        self, repo: FirstPartyRepository, provider: str, concept_ids: tuple[str, ...], window_start: date, window_end: date
    ) -> ProviderRunOutcome:
        started_at = datetime.now(timezone.utc)
        bindings = {concept_id: first_party_binding(concept_id, provider) for concept_id in concept_ids}
        if provider == PROVIDER_BLS:
            access_mode = "KEYED_V2" if self._bls.api_version == "v2" else "KEYLESS_V1"
        else:
            access_mode = "FLAT_FILE"

        published_at: datetime | None = None
        error_class: str | None = None
        fetched: dict[str, list[FirstPartyObservation]] = {}
        try:
            provider_series_ids = [binding.provider_series_id for binding in bindings.values()]
            fetched, published_at = self._fetch(provider, provider_series_ids, window_start, window_end)
        except ProviderError as exc:
            error_class = type(exc).__name__
            logger.warning(
                "first-party ingestion: fetch failed", extra={"provider": provider, "error_class": error_class}
            )

        series_outcomes: list[SeriesOutcome] = []
        if error_class is None:
            for concept_id, binding in bindings.items():
                observations = [
                    observation
                    for observation in fetched[binding.provider_series_id]
                    if window_start <= observation.period <= window_end
                ]
                series_outcomes.append(self._persist(repo, concept_id, binding, observations, started_at))

        if error_class is not None:
            status = "FAILED"
        elif any(outcome.received == 0 for outcome in series_outcomes):
            # Reached the provider and parsed it, but a series came back
            # empty for the window: not an exception, and not healthy.
            status = "PARTIAL_FAILURE"
        else:
            status = "SUCCEEDED"
        import_mode = (
            "BASELINE_BACKFILL"
            if any(outcome.import_mode == "BASELINE_BACKFILL" for outcome in series_outcomes)
            else "INCREMENTAL"
        )
        completed_at = datetime.now(timezone.utc)

        repo.add_run(
            provider=provider,
            dataset="+".join(sorted({SOURCES[concept_id].dataset for concept_id in concept_ids})),
            access_mode=access_mode,
            status=status,
            import_mode=import_mode if series_outcomes else "NONE",
            window_start=window_start,
            window_end=window_end,
            source_published_at=published_at,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=int((completed_at - started_at).total_seconds() * 1000),
            series_requested=len(concept_ids),
            observations_received=sum(item.received for item in series_outcomes),
            observations_inserted=sum(item.inserted for item in series_outcomes),
            observations_revised=sum(item.revised for item in series_outcomes),
            observations_unchanged=sum(item.unchanged for item in series_outcomes),
            observations_unavailable=sum(item.unavailable for item in series_outcomes),
            error_class=error_class,
        )
        logger.info(
            "first-party ingestion complete",
            extra={
                "provider": provider,
                "status": status,
                "access_mode": access_mode,
                "observations_inserted": sum(item.inserted for item in series_outcomes),
                "observations_revised": sum(item.revised for item in series_outcomes),
            },
        )
        return ProviderRunOutcome(
            provider=provider,
            access_mode=access_mode,
            status=status,
            import_mode=import_mode if series_outcomes else "NONE",
            window_start=window_start,
            window_end=window_end,
            source_published_at=published_at,
            error_class=error_class,
            series=series_outcomes,
        )

    def _fetch(
        self, provider: str, provider_series_ids: list[str], window_start: date, window_end: date
    ) -> tuple[dict[str, list[FirstPartyObservation]], datetime | None]:
        if provider == PROVIDER_BLS:
            return self._bls.get_monthly(provider_series_ids, window_start.year, window_end.year), None
        return self._bea.get_nipa_monthly(provider_series_ids, window_start)

    def _persist(
        self,
        repo: FirstPartyRepository,
        concept_id: str,
        binding: ProviderBinding,
        observations: list[FirstPartyObservation],
        retrieved_at: datetime,
    ) -> SeriesOutcome:
        storage_series_id = binding.storage_series_id
        # Baseline inputs read ONCE, before any write -- after the first
        # insert the row is no longer empty (the Housing rule).
        had_observations = repo.has_observations(storage_series_id)
        latest_stored = repo.latest_observation_date(storage_series_id)

        outcome = SeriesOutcome(
            concept_id=concept_id,
            provider_series_id=binding.provider_series_id,
            import_mode="INCREMENTAL" if had_observations else "BASELINE_BACKFILL",
            received=len(observations),
        )
        if not observations:
            return outcome

        source = SOURCES[concept_id]
        series = repo.ensure_series(
            storage_series_id=storage_series_id,
            concept_id=concept_id,
            title=source.title,
            units=source.units,
            source=binding.provider,
        )
        provenance = FirstPartyProvenanceRecord(
            provider=binding.provider,
            dataset=source.dataset,
            source_series_field=binding.provider_series_id,
            source_url=source_url(binding.provider, binding.provider_series_id),
            retrieved_at=retrieved_at,
        )

        for observation in observations:
            if observation.value is None:
                outcome.unavailable += 1
            written = repo.upsert_observation(
                series=series,
                observation_date=observation.period,
                # Native unit, unconverted: the binding's factor is applied
                # by the methodology, exactly as for the FRED row.
                value=observation.value,
                provenance=provenance,
                baseline=is_baseline_import(had_observations, latest_stored, observation.period),
            )
            if written == "INSERTED":
                outcome.inserted += 1
            elif written == "REVISED":
                outcome.revised += 1
            else:
                outcome.unchanged += 1

        outcome.first_period = observations[0].period
        outcome.last_period = observations[-1].period
        return outcome
