"""Data-access layer for the Rates domain (Increment #29).

Owns all SQLAlchemy work for canonical rate series: reading persisted
observations, idempotently upserting an ingested observation together
with its provenance, and recording one ingestion run. Operates entirely
within a caller-provided `Session` and never calls `commit()` or
`rollback()` itself -- the caller owns the transaction boundary, exactly
like `SeriesRepository` and every other repository here.

Reuses `economic_series`/`economic_observations` unchanged: a Treasury
par yield is a dated observation of a named series, which is precisely
what those tables already model. What is genuinely new -- per-observation
provenance and ingestion-run audit -- gets its own tables rather than
being bolted onto the existing ones.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EconomicObservation, EconomicSeries, ObservationProvenance, RatesIngestionRun
from app.repositories.observation_versions import ORIGIN_RATES_INGESTION, ObservationVersionWriter

UpsertOutcome = Literal["INSERTED", "REVISED", "UNCHANGED"]


@dataclass(frozen=True)
class ProvenanceRecord:
    """The provenance facts one ingested observation carries with it."""

    provider: str
    dataset: str
    source_series_field: str
    source_url: str
    retrieved_at: datetime


class RatesRepository:
    def __init__(self, session: Session):
        self._session = session

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_observations(self, series_id: str) -> list[EconomicObservation]:
        """Every persisted observation for one canonical series, in
        ascending date order. A series that has never been ingested
        returns an empty list -- not an error: missing economic data and
        infrastructure failure are different outcomes."""
        series = self._session.execute(
            select(EconomicSeries).where(EconomicSeries.series_id == series_id)
        ).scalar_one_or_none()
        if series is None:
            return []

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

    def get_provenance(self, series_id: str, observation_date: date) -> ObservationProvenance | None:
        """Provenance for one observation, or None when none was
        recorded (every pre-#29 observation, legitimately)."""
        series = self._session.execute(
            select(EconomicSeries).where(EconomicSeries.series_id == series_id)
        ).scalar_one_or_none()
        if series is None:
            return None

        return self._session.execute(
            select(ObservationProvenance).where(
                ObservationProvenance.economic_series_id == series.id,
                ObservationProvenance.observation_date == observation_date,
            )
        ).scalar_one_or_none()

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def ensure_series(self, series_id: str, title: str, units: str, source: str) -> EconomicSeries:
        """Get or create the series row. Metadata is refreshed on an
        existing row so a title/units correction propagates, but the
        row's identity (and therefore its observations) is preserved."""
        series = self._session.execute(
            select(EconomicSeries).where(EconomicSeries.series_id == series_id)
        ).scalar_one_or_none()

        if series is None:
            series = EconomicSeries(series_id=series_id, title=title, units=units, source=source)
            self._session.add(series)
            self._session.flush()  # assigns series.id
        else:
            series.title = title
            series.units = units
            series.source = source

        return series

    def upsert_observation(
        self,
        series: EconomicSeries,
        observation_date: date,
        value: float,
        provenance: ProvenanceRecord,
    ) -> UpsertOutcome:
        """Idempotently persist one observation and its provenance.

        Returns which of three genuinely different things happened:

        - `INSERTED`: the date had no observation for this series.
        - `REVISED`: an observation existed and the provider's value
          genuinely differs -- the stored value is updated, and the
          provenance row's `revision_count`/`last_revised_at` advance.
        - `UNCHANGED`: the value matches what is already stored; only
          `retrieved_at` moves, so routine re-syncs never inflate the
          revision history.

        Re-running an identical ingestion therefore writes no new
        observation rows and reports no revisions -- the increment's
        idempotency requirement, enforced here rather than by caller
        discipline.
        """
        # The canonical write and its system-time version are applied by
        # the one shared writer (Increment #31), so a Treasury revision
        # now preserves its previous value -- #29 recorded only a
        # `revision_count`, which cannot reconstruct anything.
        # `retrieved_at` is reused as `recorded_from` so provenance and
        # version history agree on when this ingestion happened.
        writer = ObservationVersionWriter(
            self._session, recorded_at=provenance.retrieved_at, origin=ORIGIN_RATES_INGESTION
        )
        outcome = writer.apply(series, observation_date, value)
        self._upsert_provenance(series, observation_date, provenance, revised=outcome == "REVISED")
        return outcome

    def _upsert_provenance(
        self,
        series: EconomicSeries,
        observation_date: date,
        provenance: ProvenanceRecord,
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
        datasets_requested: list[str],
        status: str,
        started_at: datetime,
        completed_at: datetime,
        duration_ms: int,
        observations_received: int,
        observations_inserted: int,
        observations_revised: int,
        datasets_failed: list[str],
        error_class: str | None,
    ) -> RatesIngestionRun:
        """Record one ingestion attempt. Counts and an exception class
        name only -- never an upstream payload or response body."""
        run = RatesIngestionRun(
            provider=provider,
            datasets_requested=",".join(datasets_requested),
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            observations_received=observations_received,
            observations_inserted=observations_inserted,
            observations_revised=observations_revised,
            datasets_failed=",".join(datasets_failed) if datasets_failed else None,
            error_class=error_class,
        )
        self._session.add(run)
        self._session.flush()
        return run
