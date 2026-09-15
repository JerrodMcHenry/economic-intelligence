"""Data-access layer for Increment #25C's automated-economic-
maintenance sweep record (`app.db.models.MaintenanceSweep`), frozen and
normative in docs/product/automated-economic-maintenance-v1.md §53/§54.

Deliberately a NEW, separate repository rather than an addition to
`app.repositories.release_processing_repository` -- a `MaintenanceSweep`
row is per-ORCHESTRATOR-RUN, operational-health-shaped data, never the
same concept as a `ReleaseCheckRun` row (per-OCCURRENCE, economic-
check-shaped) -- see `MaintenanceSweep`'s own docstring and frozen
contract §30's explicit "worker health and economic/domain freshness
are two separate concepts, never conflated" rule. Keeping the two in
separate repositories/tables is the same discipline as, not a
duplication of, the existing separation between
`ReleaseProcessingRepository` and `ReleaseRepository`.

Operates entirely within a caller-provided `Session` and never calls
`commit()`/`rollback()` itself -- the caller
(`app.services.maintenance.MaintenanceOrchestrator`) owns the
transaction boundary, the same discipline every other repository in
this project already follows (see `app.db.session.session_scope`).
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import MaintenanceSweep


class MaintenanceRepository:
    def __init__(self, session: Session):
        self._session = session

    def start_sweep(self, started_at: datetime) -> MaintenanceSweep:
        """Insert a new sweep row with `finished_at`/`status`/every
        count column left `NULL` -- committed by the caller
        immediately, in its own transaction, BEFORE any due-work
        discovery or occurrence processing begins (frozen contract
        §25/§52). If the orchestrator crashes anywhere after this
        point, this row survives with `finished_at IS NULL` forever --
        the exact, intentional signal a future health check needs to
        distinguish "a sweep started and crashed" from "no sweep ran
        at all" (no row exists)."""
        sweep = MaintenanceSweep(started_at=started_at)
        self._session.add(sweep)
        self._session.flush()  # assigns sweep.id
        return sweep

    def finish_sweep(
        self,
        sweep_id: int,
        finished_at: datetime,
        status: str,
        due_count: int,
        processed_count: int,
        failed_count: int,
    ) -> None:
        """Finalize an already-started sweep row -- called once, at
        the very end of a bounded sweep, in its OWN transaction,
        separate from `start_sweep`'s own transaction and from every
        per-occurrence `process_occurrence` call (frozen contract §24:
        sweep-level health persistence is never bundled into any
        single occurrence's own transaction, so one occurrence's own
        rollback can never also erase evidence that the sweep itself
        ran)."""
        sweep = self._session.execute(select(MaintenanceSweep).where(MaintenanceSweep.id == sweep_id)).scalar_one()
        sweep.finished_at = finished_at
        sweep.status = status
        sweep.due_count = due_count
        sweep.processed_count = processed_count
        sweep.failed_count = failed_count

    def get_latest_sweep(self) -> MaintenanceSweep | None:
        """The most recent sweep, by `started_at` (ties broken by
        `id`) -- regardless of whether it has finished. The one read
        this repository provides in support of a future CLI health/
        inspection command (frozen contract §31's own explicit
        allowance), without this increment building that command's own
        UI or alerting."""
        return self._session.execute(
            select(MaintenanceSweep).order_by(MaintenanceSweep.started_at.desc(), MaintenanceSweep.id.desc()).limit(1)
        ).scalar_one_or_none()

    def get_latest_finished_sweep(self) -> MaintenanceSweep | None:
        """The most recent sweep that has actually COMPLETED
        (`finished_at IS NOT NULL`) -- distinct from `get_latest_sweep`
        above, which may return a still-in-progress or crashed row.
        Increment #26E's own maintenance-health command needs both: the
        very latest attempt (to detect a crashed/hung sweep,
        `app.domain.maintenance_health`'s own `UNFINISHED` status) and
        the latest genuinely completed one (to judge overall health
        when the very latest attempt simply hasn't concluded yet --
        #26E source prompt §23/§54)."""
        return self._session.execute(
            select(MaintenanceSweep)
            .where(MaintenanceSweep.finished_at.is_not(None))
            .order_by(MaintenanceSweep.started_at.desc(), MaintenanceSweep.id.desc())
            .limit(1)
        ).scalar_one_or_none()
