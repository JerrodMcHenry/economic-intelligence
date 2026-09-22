"""Data-access layer for the Housing world (Increment #45).

Owns all SQLAlchemy work for the canonical Housing series: reading
persisted observations, idempotently upserting an ingested observation
together with its provenance, and recording one ingestion run. Operates
entirely within a caller-provided `Session` and never calls `commit()`
or `rollback()` itself -- the caller owns the transaction boundary,
exactly like `RatesRepository` and every other repository here.

Reuses `economic_series`/`economic_observations`/`observation_provenance`
/`observation_versions` UNCHANGED. A Census housing figure is a dated
observation of a named series with a retrieval event behind it, which is
exactly what those tables model, so the only new table in #45 is the
ingestion-run audit. Nothing about Housing's history is
Housing-specific, which is what lets point-in-time replay (#31) and
Revision Intelligence (#43) work for Housing without knowing Housing
exists.

THE ONE THING THIS REPOSITORY DOES THAT `RatesRepository` DOES NOT
-----------------------------------------------------------------
`upsert_observation` takes a `baseline` flag and passes it to the shared
`ObservationVersionWriter`. Rates has never needed it: #29 began with a
twelve-month window of daily data and the question "did MacroChipz watch
this arrive?" was answerable either way. Housing begins with sixty-seven
years of monthly history imported in one request, and calling that
"observed" would fabricate the one thing #43 exists to protect.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    EconomicObservation,
    EconomicSeries,
    HousingIngestionRun,
    ObservationProvenance,
)
from app.repositories.observation_versions import ORIGIN_HOUSING_INGESTION, ObservationVersionWriter

UpsertOutcome = Literal["INSERTED", "REVISED", "UNCHANGED"]


@dataclass(frozen=True)
class HousingProvenanceRecord:
    """The provenance facts one ingested Housing observation carries.

    `source_series_field` is Census's own identifier for the series
    (`APERMITS/TOTAL`). `source_url` is the program's published landing
    page and NEVER an API URL -- a Census API URL contains the
    credential, so storing one would write a secret into the database.
    """

    provider: str
    dataset: str
    source_series_field: str
    source_url: str
    retrieved_at: datetime


class HousingRepository:
    def __init__(self, session: Session):
        self._session = session

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_series(self, storage_series_id: str) -> EconomicSeries | None:
        return self._session.execute(
            select(EconomicSeries).where(EconomicSeries.series_id == storage_series_id)
        ).scalar_one_or_none()

    def has_observations(self, storage_series_id: str) -> bool:
        """Whether this series holds any observation at all.

        The input to the baseline decision (see
        `app.domain.housing.is_baseline_import`), and a cheap existence
        check rather than a count: the question is "has MacroChipz ever
        stored this series", and loading every row to answer it would
        read tens of thousands of rows on every sync.
        """
        series = self.get_series(storage_series_id)
        if series is None:
            return False
        return (
            self._session.execute(
                select(EconomicObservation.id)
                .where(EconomicObservation.economic_series_id == series.id)
                .limit(1)
            ).scalar_one_or_none()
            is not None
        )

    def latest_observation_date(self, storage_series_id: str) -> date | None:
        """The newest month this series holds, or `None`.

        The second input to the baseline decision: a write for a month
        older than this one is filling history backwards, which
        MacroChipz did not watch happen.
        """
        series = self.get_series(storage_series_id)
        if series is None:
            return None
        return self._session.execute(
            select(EconomicObservation.observation_date)
            .where(EconomicObservation.economic_series_id == series.id)
            .order_by(EconomicObservation.observation_date.desc())
            .limit(1)
        ).scalar_one_or_none()

    def get_observations(self, storage_series_id: str) -> list[EconomicObservation]:
        """Every persisted observation for one Housing series, ascending
        by date. A series never ingested returns an empty list -- not an
        error: missing economic data and infrastructure failure are
        different outcomes."""
        series = self.get_series(storage_series_id)
        return [] if series is None else self.observations_for(series)

    def observations_for(self, series: EconomicSeries) -> list[EconomicObservation]:
        """The same read, for a caller that already holds the series row.

        MEASURED, not guessed (#45 section 20): the read service needs
        both the observations and the provenance of every measure, and
        with only the `storage_series_id` variants it resolved the series
        row twice per measure -- 24 queries for six measures, half of
        them identical lookups. Threading the row through removes twelve
        of them.
        """
        rows = (
            self._session.execute(
                select(EconomicObservation)
                .where(EconomicObservation.economic_series_id == series.id)
                .order_by(EconomicObservation.observation_date.asc())
            )
            .scalars()
            .all()
        )
        return list(rows)

    def get_provenance(self, storage_series_id: str, observation_date: date) -> ObservationProvenance | None:
        series = self.get_series(storage_series_id)
        return None if series is None else self.provenance_for(series, observation_date)

    def provenance_for(
        self, series: EconomicSeries, observation_date: date
    ) -> ObservationProvenance | None:
        """Provenance for one observation of an already-resolved series."""
        return self._session.execute(
            select(ObservationProvenance).where(
                ObservationProvenance.economic_series_id == series.id,
                ObservationProvenance.observation_date == observation_date,
            )
        ).scalar_one_or_none()

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def ensure_series(
        self, storage_series_id: str, concept_id: str, title: str, units: str, source: str
    ) -> EconomicSeries:
        """Get or create the series row.

        `concept_id` is set on creation AND refreshed on an existing row,
        so a Housing series can never end up with a NULL concept and
        therefore can never be mistaken for one of the arbitrary provider
        series the generic sync endpoint accepts (#38). Metadata is
        refreshed too, so a title or unit correction propagates, while
        the row's identity -- and therefore its observations, provenance
        and version history -- is preserved.
        """
        series = self.get_series(storage_series_id)

        if series is None:
            series = EconomicSeries(
                series_id=storage_series_id,
                concept_id=concept_id,
                title=title,
                units=units,
                source=source,
            )
            self._session.add(series)
            self._session.flush()  # assigns series.id
        else:
            series.concept_id = concept_id
            series.title = title
            series.units = units
            series.source = source

        return series

    def upsert_observation(
        self,
        series: EconomicSeries,
        observation_date: date,
        value: float,
        provenance: HousingProvenanceRecord,
        baseline: bool,
    ) -> UpsertOutcome:
        """Idempotently persist one observation and its provenance.

        Returns which of three genuinely different things happened:

        - `INSERTED`: the month had no observation for this series.
        - `REVISED`: an observation existed and Census's value genuinely
          differs -- the stored value is updated, the previous version is
          closed and a new one opened, and the provenance row's
          `revision_count`/`last_revised_at` advance.
        - `UNCHANGED`: the value matches what is already stored. Only
          `retrieved_at` moves, so routine re-syncs never inflate the
          revision history and never write a version row.

        Re-running an identical ingestion therefore writes no new
        observation rows and reports no revisions -- the idempotency
        requirement, enforced here rather than by caller discipline.

        `baseline` marks an INSERT as an imported baseline rather than an
        observed arrival. It has no effect on a revision, by design: see
        `ObservationVersionWriter.__init__`.
        """
        writer = ObservationVersionWriter(
            self._session,
            # `retrieved_at` is reused as `recorded_from` so provenance
            # and version history agree on when this ingestion happened,
            # and so every write in one sync shares one instant.
            recorded_at=provenance.retrieved_at,
            origin=ORIGIN_HOUSING_INGESTION,
            baseline=baseline,
        )
        outcome = writer.apply(series, observation_date, value)
        self._upsert_provenance(series, observation_date, provenance, revised=outcome == "REVISED")
        return outcome

    def _upsert_provenance(
        self,
        series: EconomicSeries,
        observation_date: date,
        provenance: HousingProvenanceRecord,
        revised: bool,
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

        row.provider = provenance.provider
        row.dataset = provenance.dataset
        row.source_series_field = provenance.source_series_field
        row.source_url = provenance.source_url
        row.retrieved_at = provenance.retrieved_at
        if revised:
            row.revision_count = row.revision_count + 1
            row.last_revised_at = provenance.retrieved_at

    def add_ingestion_run(
        self,
        provider: str,
        dataset: str,
        status: str,
        import_mode: str,
        started_at: datetime,
        completed_at: datetime,
        duration_ms: int,
        rows_received: int,
        rows_rejected: int,
        error_measure_rows_ignored: int,
        observations_inserted: int,
        observations_revised: int,
        observations_skipped_missing_value: int,
        error_class: str | None,
    ) -> HousingIngestionRun:
        """Record one ingestion attempt. Counts, a status, an import mode
        and an exception class name only -- never an upstream payload,
        never a response body, never a request URL."""
        run = HousingIngestionRun(
            provider=provider,
            dataset=dataset,
            status=status,
            import_mode=import_mode,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            rows_received=rows_received,
            rows_rejected=rows_rejected,
            error_measure_rows_ignored=error_measure_rows_ignored,
            observations_inserted=observations_inserted,
            observations_revised=observations_revised,
            observations_skipped_missing_value=observations_skipped_missing_value,
            error_class=error_class,
        )
        self._session.add(run)
        self._session.flush()
        return run
