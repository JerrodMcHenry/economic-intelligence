"""Data-access layer for Increment #25G's Since Last Visit V1 read
model -- see docs/product/since-last-visit-v1.md (#25F), specifically
§17/§58-61. Purely read-only: no `add_*`/`write_*`/`create_*` method
anywhere on it, mirroring `ReleaseProcessingReadRepository`'s own
identical #19B precedent exactly (this module's own closest sibling in
shape and purpose).

Deliberately a NEW, separate repository -- not an addition to
`ReleaseProcessingRepository` (#18's own write path) or
`ReleaseProcessingReadRepository` (#19B's own, differently-shaped read
model, scoped to one occurrence's full history rather than a
cross-domain time window). Operates entirely within a caller-provided
`Session` and never calls `commit()`/`rollback()`.

Five bounded query shapes, matching the frozen contract's own §61
architecture exactly: relevant releases (once), settled-release-ids in
the window (once), the event-spine check runs in the window (once),
each child table's rows for that check-run-id set (three `IN (...)`
queries, never per-run), plus sweep-evidence and series-metadata
lookups. No window function, no N+1 -- the identical "fetch the full
candidate set into Python" discipline `ReleaseProcessingReadRepository`
already establishes for #19B.
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    EconomicRelease,
    EconomicSeries,
    MaintenanceSweep,
    RecordedMonitorResult,
    ReleaseAnalysisUpdate,
    ReleaseCheckRun,
    ReleaseObservationUpdate,
    ReleaseOccurrence,
    ReleaseSeriesMapping,
)

# The two CheckRunStatus values that mean "every currently-active
# mapped series in that run was successfully queried" -- reused
# verbatim from `ReleaseProcessingRepository`'s own identical
# `_SETTLED_CHECK_RUN_STATUSES` constant (contract §40's own explicit
# instruction to reuse #25C's frozen settlement definition, never
# re-derive it).
_SETTLED_STATUSES = ("NO_CHANGE", "CHANGED")


class SinceLastVisitRepository:
    def __init__(self, session: Session):
        self._session = session

    # -----------------------------------------------------------------
    # Relevant-release resolution (contract §39 "canonical release→monitor
    # mapping", derived from real, currently-active ReleaseSeriesMapping
    # rows -- never a hard-coded release-id list, never a display
    # category, mirroring the frontend's own `releaseMonitorRelation.ts`
    # in spirit but computed from the actual source data it was itself
    # verified against).
    # -----------------------------------------------------------------

    def relevant_release_ids_by_series(
        self, inflation_series_ids: frozenset[str], labor_series_ids: frozenset[str]
    ) -> tuple[frozenset[int], frozenset[int]]:
        """`(inflation_release_ids, labor_release_ids)` -- every
        `EconomicRelease.id` with at least one currently-active
        `ReleaseSeriesMapping` whose `series_id` belongs to that
        monitor's own canonical series set."""
        rows = self._session.execute(
            select(ReleaseSeriesMapping.economic_release_id, ReleaseSeriesMapping.series_id).where(
                ReleaseSeriesMapping.active.is_(True)
            )
        ).all()
        inflation_ids: set[int] = set()
        labor_ids: set[int] = set()
        for release_id, series_id in rows:
            if series_id in inflation_series_ids:
                inflation_ids.add(release_id)
            if series_id in labor_series_ids:
                labor_ids.add(release_id)
        return frozenset(inflation_ids), frozenset(labor_ids)

    # -----------------------------------------------------------------
    # Event spine (contract §58-59)
    # -----------------------------------------------------------------

    def list_check_runs_in_window(
        self, release_ids: frozenset[int], after: datetime | None, through: datetime
    ) -> list[tuple[ReleaseCheckRun, EconomicRelease]]:
        """Every `ReleaseCheckRun`, with its parent `EconomicRelease`
        inlined, for an occurrence of one of the given releases, with
        `completed_at` in the half-open window `(after, through]`
        (`after is None` means an unbounded lower edge -- the caller
        has already resolved a real `after` via
        `app.domain.since_last_visit.resolve_window` before calling
        this in normal operation; `None` is accepted defensively).
        Ordered `completed_at ASC, id ASC` -- contract §58-59's own
        frozen deterministic ordering."""
        if not release_ids:
            return []
        stmt = (
            select(ReleaseCheckRun, EconomicRelease)
            .join(ReleaseOccurrence, ReleaseCheckRun.release_occurrence_id == ReleaseOccurrence.id)
            .join(EconomicRelease, ReleaseOccurrence.economic_release_id == EconomicRelease.id)
            .where(ReleaseOccurrence.economic_release_id.in_(release_ids), ReleaseCheckRun.completed_at <= through)
            .order_by(ReleaseCheckRun.completed_at.asc(), ReleaseCheckRun.id.asc())
        )
        if after is not None:
            stmt = stmt.where(ReleaseCheckRun.completed_at > after)
        return list(self._session.execute(stmt).all())

    # -----------------------------------------------------------------
    # Children of the selected check runs (three IN(...) queries, never
    # per-run -- mirrors ReleaseProcessingReadRepository's own
    # `list_observation_updates_for_runs`/`list_analysis_updates_for_runs`
    # shape exactly)
    # -----------------------------------------------------------------

    def list_observation_updates_for_runs(self, check_run_ids: list[int]) -> list[ReleaseObservationUpdate]:
        if not check_run_ids:
            return []
        rows = self._session.execute(
            select(ReleaseObservationUpdate).where(ReleaseObservationUpdate.release_check_run_id.in_(check_run_ids))
        ).scalars()
        return list(rows)

    def list_analysis_updates_for_runs(self, check_run_ids: list[int]) -> list[ReleaseAnalysisUpdate]:
        if not check_run_ids:
            return []
        rows = self._session.execute(
            select(ReleaseAnalysisUpdate).where(ReleaseAnalysisUpdate.release_check_run_id.in_(check_run_ids))
        ).scalars()
        return list(rows)

    def list_recorded_results_for_runs(self, check_run_ids: list[int]) -> list[RecordedMonitorResult]:
        if not check_run_ids:
            return []
        rows = self._session.execute(
            select(RecordedMonitorResult).where(RecordedMonitorResult.release_check_run_id.in_(check_run_ids))
        ).scalars()
        return list(rows)

    def list_series_metadata(self, series_ids: list[str]) -> dict[str, EconomicSeries]:
        """Mirrors `ReleaseProcessingReadRepository.list_series_metadata`
        exactly (contract §72-73) -- a `series_id` with no matching row
        simply has no key; the caller renders `None`, never a
        fabricated title."""
        if not series_ids:
            return {}
        rows = self._session.execute(select(EconomicSeries).where(EconomicSeries.series_id.in_(series_ids))).scalars()
        return {row.series_id: row for row in rows}

    # -----------------------------------------------------------------
    # Coverage evidence (contract §40-47)
    # -----------------------------------------------------------------

    def settled_release_ids_in_window(self, release_ids: frozenset[int], after: datetime | None, through: datetime) -> frozenset[int]:
        """Every release id, among the given set, with at least one
        settled (`NO_CHANGE`/`CHANGED`) `ReleaseCheckRun` -- any
        occurrence -- with `completed_at` in `(after, through]`."""
        if not release_ids:
            return frozenset()
        stmt = (
            select(ReleaseOccurrence.economic_release_id)
            .join(ReleaseCheckRun, ReleaseCheckRun.release_occurrence_id == ReleaseOccurrence.id)
            .where(
                ReleaseOccurrence.economic_release_id.in_(release_ids),
                ReleaseCheckRun.status.in_(_SETTLED_STATUSES),
                ReleaseCheckRun.completed_at <= through,
            )
            .distinct()
        )
        if after is not None:
            stmt = stmt.where(ReleaseCheckRun.completed_at > after)
        rows = self._session.execute(stmt).scalars()
        return frozenset(rows)

    def latest_settled_completed_at(self, release_ids: frozenset[int]) -> datetime | None:
        """The most recent settled `ReleaseCheckRun.completed_at`
        across ANY occurrence of the given releases -- system-wide, not
        window-scoped (contract §43's own "last checked" fact must
        remain meaningful even when the window itself shows `GAP`/
        `UNKNOWN` coverage)."""
        if not release_ids:
            return None
        stmt = (
            select(ReleaseCheckRun.completed_at)
            .join(ReleaseOccurrence, ReleaseCheckRun.release_occurrence_id == ReleaseOccurrence.id)
            .where(ReleaseOccurrence.economic_release_id.in_(release_ids), ReleaseCheckRun.status.in_(_SETTLED_STATUSES))
            .order_by(ReleaseCheckRun.completed_at.desc())
            .limit(1)
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def any_sweep_started_in_window(self, after: datetime | None, through: datetime) -> bool:
        """Contract §40/§44: any `MaintenanceSweep` row (finished or
        not -- an unfinished sweep still proves an attempt occurred)
        with `started_at` in `(after, through]`."""
        stmt = select(MaintenanceSweep.id).where(MaintenanceSweep.started_at <= through).limit(1)
        if after is not None:
            stmt = stmt.where(MaintenanceSweep.started_at > after)
        return self._session.execute(stmt).scalar_one_or_none() is not None

    def latest_sweep_finished_at(self) -> datetime | None:
        """System-wide fallback fact for §43's own "last checked" note
        when no settled release check run exists at all for a domain."""
        stmt = (
            select(MaintenanceSweep.finished_at)
            .where(MaintenanceSweep.finished_at.is_not(None))
            .order_by(MaintenanceSweep.finished_at.desc())
            .limit(1)
        )
        return self._session.execute(stmt).scalar_one_or_none()

    # -----------------------------------------------------------------
    # Unchanged-confirmation algorithm support (contract §21 branch 2)
    # -----------------------------------------------------------------

    def earliest_recorded_result_id_by_monitor(self) -> dict[str, int]:
        """`{monitor: earliest ever RecordedMonitorResult.id}` --
        system-wide, never window-scoped (contract §21's own "a single,
        cheap existence check, not a window-scoped one"). One small
        aggregate query, not one per row."""
        rows = self._session.execute(
            select(RecordedMonitorResult.monitor, func.min(RecordedMonitorResult.id)).group_by(RecordedMonitorResult.monitor)
        ).all()
        return {monitor: earliest_id for monitor, earliest_id in rows}
