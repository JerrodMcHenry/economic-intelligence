"""Data-access layer for Increment #19B's public release-processing
read model. Purely read-only -- unlike `ReleaseProcessingRepository`
(#18's write path plus a handful of single-occurrence/single-run read
helpers), this repository has no `add_*`/`write_*`/`create_*` method
anywhere on it, and never assigns an identity to a new row the way
`ReleaseProcessingRepository.add_check_run` does.

Deliberately a NEW, separate repository rather than an addition to
`app.repositories.release_processing_repository` (whose whole reason
to exist is to own #18's write path start to finish -- see that
module's own docstring) or `app.repositories.release_repository`
(structurally forbidden from importing anything series/observation-
shaped -- see
`tests/integration/test_transaction_and_safety.py::TestReleaseCalendarStructuralIndependence`).
Mirrors #18's own precedent of a small, independent, narrowly-scoped
module rather than extending a protected or differently-purposed one.

Operates entirely within a caller-provided `Session` and never calls
`commit()`/`rollback()` -- the caller owns the transaction boundary,
the same discipline every repository in this project follows.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    EconomicRelease,
    EconomicSeries,
    ReleaseAnalysisUpdate,
    ReleaseCheckRun,
    ReleaseObservationUpdate,
    ReleaseOccurrence,
    ReleaseSeriesMapping,
)


class ReleaseProcessingReadRepository:
    def __init__(self, session: Session):
        self._session = session

    def list_mapped_occurrences(
        self,
        occurrence_id: int | None = None,
        release_id: int | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[tuple[ReleaseOccurrence, EconomicRelease]]:
        """Every occurrence whose release currently has at least one
        active `ReleaseSeriesMapping` row, with its parent release
        inlined -- an occurrence whose release has zero active mappings
        is excluded here, at the database layer, and never reaches the
        service or the response at all (never assigned a status, never
        a synthetic catch-all status -- see
        `app.models.release_processing_read`'s docstring).

        Ordered by `scheduled_date DESC, id ASC` -- most recent
        occurrence first, deterministic tie-break. Unpaginated: status
        filtering (`CHANGES_DETECTED` etc.) can only be applied after
        deriving each occurrence's latest-run status, which requires
        this repository's `list_check_runs_for_occurrences` first (see
        `app.services.release_processing_read.ReleaseProcessingReadService`).
        V1's mapped-catalog scale (a handful of curated releases, each
        with at most a few dozen occurrences) makes fetching the full
        filtered-but-unpaginated candidate set into Python -- rather
        than expressing "latest run per occurrence" as a SQL window
        function -- the deliberately simpler choice; see
        docs/architecture/release-processing-read-model-v1.md for why
        this is not treated as a premature-optimization concern here.
        """
        mapped_release_ids = (
            select(ReleaseSeriesMapping.economic_release_id).where(ReleaseSeriesMapping.active.is_(True)).distinct()
        )
        stmt = (
            select(ReleaseOccurrence, EconomicRelease)
            .join(EconomicRelease, ReleaseOccurrence.economic_release_id == EconomicRelease.id)
            .where(ReleaseOccurrence.economic_release_id.in_(mapped_release_ids))
            .order_by(ReleaseOccurrence.scheduled_date.desc(), ReleaseOccurrence.id.asc())
        )
        if occurrence_id is not None:
            stmt = stmt.where(ReleaseOccurrence.id == occurrence_id)
        if release_id is not None:
            stmt = stmt.where(ReleaseOccurrence.economic_release_id == release_id)
        if start_date is not None:
            stmt = stmt.where(ReleaseOccurrence.scheduled_date >= start_date)
        if end_date is not None:
            stmt = stmt.where(ReleaseOccurrence.scheduled_date <= end_date)

        rows = self._session.execute(stmt).all()
        return [(row[0], row[1]) for row in rows]

    def list_check_runs_for_occurrences(self, occurrence_ids: list[int]) -> list[ReleaseCheckRun]:
        """Every `ReleaseCheckRun` row for the given occurrences, from
        ANY point in history -- not just the latest per occurrence
        (that selection is the service's job, since it needs the full
        set to preserve retry history in the response's change lists
        too). Ordered `completed_at DESC, id DESC`: the first row per
        `release_occurrence_id` encountered while iterating this list
        is that occurrence's latest run, deterministically."""
        if not occurrence_ids:
            return []
        rows = self._session.execute(
            select(ReleaseCheckRun)
            .where(ReleaseCheckRun.release_occurrence_id.in_(occurrence_ids))
            .order_by(ReleaseCheckRun.completed_at.desc(), ReleaseCheckRun.id.desc())
        ).scalars()
        return list(rows)

    def list_observation_updates_for_runs(self, check_run_ids: list[int]) -> list[ReleaseObservationUpdate]:
        """Every `ReleaseObservationUpdate` row across the given runs --
        deliberately across a caller-chosen SET of run ids (typically
        every run an occurrence ever had), not scoped to one run, so a
        later NO_CHANGE run's absence of new rows never hides an
        earlier run's detected changes. Ordered `detected_at DESC, id
        DESC`."""
        if not check_run_ids:
            return []
        rows = self._session.execute(
            select(ReleaseObservationUpdate)
            .where(ReleaseObservationUpdate.release_check_run_id.in_(check_run_ids))
            .order_by(ReleaseObservationUpdate.detected_at.desc(), ReleaseObservationUpdate.id.desc())
        ).scalars()
        return list(rows)

    def list_analysis_updates_for_runs(self, check_run_ids: list[int]) -> list[ReleaseAnalysisUpdate]:
        """Same shape as `list_observation_updates_for_runs`, for
        `ReleaseAnalysisUpdate`. Ordered `created_at DESC, id DESC` --
        `ReleaseAnalysisUpdate` has no `detected_at` column (see that
        model's own docstring)."""
        if not check_run_ids:
            return []
        rows = self._session.execute(
            select(ReleaseAnalysisUpdate)
            .where(ReleaseAnalysisUpdate.release_check_run_id.in_(check_run_ids))
            .order_by(ReleaseAnalysisUpdate.created_at.desc(), ReleaseAnalysisUpdate.id.desc())
        ).scalars()
        return list(rows)

    def list_series_metadata(self, series_ids: list[str]) -> dict[str, EconomicSeries]:
        """`{series_id: EconomicSeries}` for the given business
        identifiers -- keyed by the string `series_id`
        `ReleaseObservationUpdate.series_id` actually stores (not the
        internal `EconomicSeries.id`). A `series_id` with no matching
        row simply has no key in the returned dict; the caller renders
        `series_title`/`units` as `None` rather than fabricating a
        value (see `app.models.release_processing_read.DetectedObservationChange`)."""
        if not series_ids:
            return {}
        rows = self._session.execute(select(EconomicSeries).where(EconomicSeries.series_id.in_(series_ids))).scalars()
        return {row.series_id: row for row in rows}
