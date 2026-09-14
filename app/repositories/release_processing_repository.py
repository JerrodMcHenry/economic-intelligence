"""Data-access layer for Increment #18's release-driven update
pipeline. Owns all SQLAlchemy query/persistence operations against
`release_series_mappings`, `release_check_runs`,
`release_observation_updates`, and `release_analysis_updates`, plus the
one #18-owned canonical-observation write path (`write_observation`).

Operates entirely within a caller-provided `Session` and never calls
`commit()`/`rollback()` itself -- the caller (`app.services.release_processing`)
owns the transaction boundary, the same discipline every other
repository in this project already follows (see
`app.db.session.session_scope`, `docs/adr/009-repository-boundary.md`).

Deliberately a NEW, separate repository rather than an addition to
`app.repositories.release_repository` (which is structurally forbidden
from importing anything series/observation-shaped -- see
`tests/integration/test_transaction_and_safety.py::TestReleaseCalendarStructuralIndependence`)
or `app.repositories.series_repository` (whose `_upsert_observations`
must keep meaning exactly what it means for the plain,
pre-existing `/series/{id}/sync` endpoint, never silently start
emitting release-audit side effects). `write_observation` is a
deliberately small, independent reimplementation of the same basic
upsert-by-date shape `SeriesRepository._upsert_observations` already
uses -- the classification DECISION (NEW/REVISED/UNCHANGED) is made by
the caller before this method is ever called (see
`app.domain.release_processing.classify_observation_change`), never
inside it; this method only performs the mechanical write once that
decision has already been made elsewhere.
"""

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    EconomicObservation,
    EconomicSeries,
    ReleaseAnalysisUpdate,
    ReleaseCheckRun,
    ReleaseObservationUpdate,
    ReleaseSeriesMapping,
)
from app.models.release_processing import AnalysisChangeRecord, CheckRunStatus, ObservationChangeRecord


class ReleaseProcessingRepository:
    def __init__(self, session: Session):
        self._session = session

    # -----------------------------------------------------------------
    # ReleaseSeriesMapping (read-only here -- seeded by migration only)
    # -----------------------------------------------------------------

    def get_active_mappings(self, economic_release_id: int) -> list[ReleaseSeriesMapping]:
        """Every active curated mapping for one release, deterministic
        order (by `series_id`) so callers iterating them behave
        reproducibly across runs -- the same discipline
        `ReleaseRepository.get_active_releases` already applies."""
        rows = self._session.execute(
            select(ReleaseSeriesMapping)
            .where(ReleaseSeriesMapping.economic_release_id == economic_release_id, ReleaseSeriesMapping.active.is_(True))
            .order_by(ReleaseSeriesMapping.series_id.asc())
        ).scalars()
        return list(rows)

    # -----------------------------------------------------------------
    # EconomicSeries / EconomicObservation (canonical write path)
    # -----------------------------------------------------------------

    def get_series_by_series_id(self, series_id: str) -> EconomicSeries | None:
        """Read-only lookup -- mirrors `SeriesRepository.get_series_by_series_id`
        exactly (kept as a separate, independent read here rather than
        importing `SeriesRepository`, since this repository's whole
        reason to exist is to own #18's own, independently-auditable
        write path start to finish)."""
        return self._session.execute(select(EconomicSeries).where(EconomicSeries.series_id == series_id)).scalar_one_or_none()

    def create_series(self, series_id: str, title: str, units: str, source: str = "FRED") -> EconomicSeries:
        """Insert a new `EconomicSeries` row -- called only when
        `get_series_by_series_id` found nothing, i.e. this is the first
        time ANY code path (ordinary sync or release processing) has
        ever persisted this canonical series. `title`/`units` come from
        a real `FREDClient.get_series_info` call (see
        `app.services.release_processing`) -- never a fabricated
        placeholder."""
        series = EconomicSeries(series_id=series_id, title=title, units=units, source=source)
        self._session.add(series)
        self._session.flush()  # assigns series.id
        return series

    def get_observations_by_date(self, economic_series_id: int) -> dict[date, float | None]:
        """Every persisted observation for a series, as a `{date: value}`
        map -- the "before" comparison baseline release processing
        classifies each provider observation against."""
        rows = self._session.execute(
            select(EconomicObservation).where(EconomicObservation.economic_series_id == economic_series_id)
        ).scalars()
        return {row.observation_date: row.value for row in rows}

    def write_observation(self, economic_series_id: int, observation_date: date, value: float | None) -> None:
        """Insert-or-overwrite one observation's current value --
        mechanical only, no classification. The caller has already
        decided (via `app.domain.release_processing.classify_observation_change`,
        evaluated against `get_observations_by_date`'s snapshot) that
        this write is a genuine NEW or REVISED change; an UNCHANGED
        observation is never passed here at all.

        Flushes immediately (Increment #20D.2 fix -- this project's own
        session factory sets `autoflush=False`, see `app.db.session`).
        A REVISED write mutates an already-identity-mapped object
        in-place, so the caller's later `get_observations_by_date`
        re-read happened to see it correctly even without a flush
        (same Python object, same session); a genuinely NEW observation
        has no such object to mutate, so its `session.add(...)` alone
        was invisible to a later `select()`-based "after" evidence read
        without an explicit flush here -- silently producing an empty
        before/after diff for exactly the case
        `labor_what_changed_v1.0`'s own `AVAILABILITY_RESTORED` event
        exists to detect. This was a latent defect in #18's own shared
        write path (present for Inflation too, never previously
        exercised by any existing Inflation test, all of which revise
        already-persisted observations only) -- fixing it here benefits
        both families identically, not a Labor-specific workaround."""
        existing = self._session.execute(
            select(EconomicObservation).where(
                EconomicObservation.economic_series_id == economic_series_id,
                EconomicObservation.observation_date == observation_date,
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing.value = value
        else:
            self._session.add(
                EconomicObservation(economic_series_id=economic_series_id, observation_date=observation_date, value=value)
            )
        self._session.flush()

    # -----------------------------------------------------------------
    # ReleaseCheckRun / ReleaseObservationUpdate / ReleaseAnalysisUpdate
    # -----------------------------------------------------------------

    def add_check_run(
        self,
        release_occurrence_id: int,
        status: CheckRunStatus,
        started_at: datetime,
        completed_at: datetime,
    ) -> ReleaseCheckRun:
        run = ReleaseCheckRun(
            release_occurrence_id=release_occurrence_id, status=status, started_at=started_at, completed_at=completed_at
        )
        self._session.add(run)
        self._session.flush()  # assigns run.id, needed by the update rows below
        return run

    def add_observation_update(self, release_check_run_id: int, record: ObservationChangeRecord) -> None:
        self._session.add(
            ReleaseObservationUpdate(
                release_check_run_id=release_check_run_id,
                series_id=record.series_id,
                observation_date=record.observation_date,
                change_type=record.change_type,
                previous_value=record.previous_value,
                new_value=record.new_value,
                detected_at=record.detected_at,
            )
        )

    def add_analysis_update(self, release_check_run_id: int, record: AnalysisChangeRecord) -> None:
        # ChangeEvent.previous_value/current_value are `float | str | None`;
        # str(float) round-trips exactly (see ReleaseAnalysisUpdate's own
        # docstring), so a single nullable String column holds either.
        self._session.add(
            ReleaseAnalysisUpdate(
                release_check_run_id=release_check_run_id,
                component=record.component,
                event_type=record.event_type,
                field=record.field,
                previous_value=None if record.previous_value is None else str(record.previous_value),
                current_value=None if record.current_value is None else str(record.current_value),
                delta=record.delta,
                evaluation_period=record.evaluation_period,
                methodology_id=record.methodology_id,
                data_basis=record.data_basis,
            )
        )

    # -----------------------------------------------------------------
    # Read helpers (tests, and groundwork for a future read endpoint --
    # see docs/architecture/release-processing-v1.md's deferred scope)
    # -----------------------------------------------------------------

    def list_check_runs_for_occurrence(self, release_occurrence_id: int) -> list[ReleaseCheckRun]:
        rows = self._session.execute(
            select(ReleaseCheckRun)
            .where(ReleaseCheckRun.release_occurrence_id == release_occurrence_id)
            .order_by(ReleaseCheckRun.id.asc())
        ).scalars()
        return list(rows)

    def list_observation_updates_for_run(self, release_check_run_id: int) -> list[ReleaseObservationUpdate]:
        rows = self._session.execute(
            select(ReleaseObservationUpdate)
            .where(ReleaseObservationUpdate.release_check_run_id == release_check_run_id)
            .order_by(ReleaseObservationUpdate.id.asc())
        ).scalars()
        return list(rows)

    def list_analysis_updates_for_run(self, release_check_run_id: int) -> list[ReleaseAnalysisUpdate]:
        rows = self._session.execute(
            select(ReleaseAnalysisUpdate)
            .where(ReleaseAnalysisUpdate.release_check_run_id == release_check_run_id)
            .order_by(ReleaseAnalysisUpdate.id.asc())
        ).scalars()
        return list(rows)
