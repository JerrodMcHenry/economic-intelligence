"""Data access for first-party BLS/BEA ingestion (Increment #56A).

The same shape as `HousingRepository`, for the same reason its docstring
gives: a first-party figure is a dated observation of a named series
with a retrieval event behind it, so it reuses `economic_series`,
`economic_observations`, `observation_provenance` and
`observation_versions` unchanged, through the ONE shared
`ObservationVersionWriter`. The only new table is the run audit.

Scoped to concept-keyed first-party rows: `ensure_series` refuses any
source other than BLS or BEA, so this repository cannot create -- or,
through `upsert_observation`, write into -- a FRED row. FRED-derived
history is never relabelled (#56A decision).

Never commits or rolls back; the caller owns the transaction.
"""

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EconomicObservation, EconomicSeries, ObservationProvenance, ProviderIngestionRun
from app.models.first_party import PROVIDER_BEA, PROVIDER_BLS
from app.repositories.observation_versions import ORIGIN_FIRST_PARTY_INGESTION, ObservationVersionWriter, WriteOutcome

FIRST_PARTY_PROVIDERS = frozenset({PROVIDER_BLS, PROVIDER_BEA})


@dataclass(frozen=True)
class FirstPartyProvenanceRecord:
    provider: str
    dataset: str
    #: The provider's own identifier (`CUSR0000SA0`, `DPCERG`).
    source_series_field: str
    #: A public landing page, never an API URL.
    source_url: str
    retrieved_at: datetime


class FirstPartyRepository:
    def __init__(self, session: Session):
        self._session = session

    def get_series(self, storage_series_id: str) -> EconomicSeries | None:
        return self._session.execute(
            select(EconomicSeries).where(EconomicSeries.series_id == storage_series_id)
        ).scalar_one_or_none()

    def has_observations(self, storage_series_id: str) -> bool:
        series = self.get_series(storage_series_id)
        if series is None:
            return False
        return (
            self._session.execute(
                select(EconomicObservation.id).where(EconomicObservation.economic_series_id == series.id).limit(1)
            ).scalar_one_or_none()
            is not None
        )

    def latest_observation_date(self, storage_series_id: str) -> date | None:
        series = self.get_series(storage_series_id)
        if series is None:
            return None
        return self._session.execute(
            select(EconomicObservation.observation_date)
            .where(EconomicObservation.economic_series_id == series.id)
            .order_by(EconomicObservation.observation_date.desc())
            .limit(1)
        ).scalar_one_or_none()

    def ensure_series(self, storage_series_id: str, concept_id: str, title: str, units: str, source: str) -> EconomicSeries:
        """Create the concept-keyed row on first import, or confirm it.

        Refuses to touch a row owned by another source. `storage_series_id`
        is a concept id and no FRED row is keyed by one, so this can only
        fire on a registry bug -- and if it ever does, stopping is the
        only correct response: writing BLS values into a FRED-sourced row
        would relabel FRED history.
        """
        if source not in FIRST_PARTY_PROVIDERS:
            raise ValueError(f"FirstPartyRepository writes only {sorted(FIRST_PARTY_PROVIDERS)} rows, not {source!r}")

        series = self.get_series(storage_series_id)
        if series is None:
            series = EconomicSeries(
                series_id=storage_series_id, concept_id=concept_id, title=title, units=units, source=source
            )
            self._session.add(series)
            self._session.flush()
            return series

        if series.source != source or series.concept_id != concept_id:
            raise ValueError(
                f"Stored series {storage_series_id!r} belongs to source {series.source!r} / concept "
                f"{series.concept_id!r}; refusing to write {source!r} data into it"
            )
        series.title = title
        series.units = units
        return series

    def upsert_observation(
        self,
        series: EconomicSeries,
        observation_date: date,
        value: float | None,
        provenance: FirstPartyProvenanceRecord,
        baseline: bool,
    ) -> WriteOutcome:
        """Persist one observation and its provenance.

        `INSERTED` / `REVISED` / `UNCHANGED` exactly as the shared writer
        defines them. `value=None` is a period the provider published as
        unavailable, and is stored as such -- matching how the FRED path
        stores FRED's own `.` -- so a value appearing later is recorded as
        the genuine revision it is.
        """
        writer = ObservationVersionWriter(
            self._session,
            recorded_at=provenance.retrieved_at,
            origin=ORIGIN_FIRST_PARTY_INGESTION,
            baseline=baseline,
        )
        outcome = writer.apply(series, observation_date, value)
        self._upsert_provenance(series, observation_date, provenance, revised=outcome == "REVISED")
        return outcome

    def _upsert_provenance(
        self, series: EconomicSeries, observation_date: date, provenance: FirstPartyProvenanceRecord, revised: bool
    ) -> None:
        row = self._session.execute(
            select(ObservationProvenance).where(
                ObservationProvenance.economic_series_id == series.id,
                ObservationProvenance.observation_date == observation_date,
            )
        ).scalar_one_or_none()

        if row is None:
            self._session.add(
                ObservationProvenance(
                    economic_series_id=series.id,
                    observation_date=observation_date,
                    provider=provenance.provider,
                    dataset=provenance.dataset,
                    source_series_field=provenance.source_series_field,
                    source_url=provenance.source_url,
                    retrieved_at=provenance.retrieved_at,
                    first_seen_at=provenance.retrieved_at,
                    revision_count=0,
                    last_revised_at=None,
                )
            )
            return

        row.retrieved_at = provenance.retrieved_at
        if revised:
            row.revision_count = row.revision_count + 1
            row.last_revised_at = provenance.retrieved_at

    def add_run(self, **fields: object) -> ProviderIngestionRun:
        """Record one attempt: counts, statuses, modes, a class name."""
        run = ProviderIngestionRun(**fields)
        self._session.add(run)
        self._session.flush()
        return run
