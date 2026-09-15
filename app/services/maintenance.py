"""Application/use-case orchestration for Increment #25C's automated
economic maintenance -- the ONE new module whose job is to discover
which release occurrences are due for a check and invoke the EXISTING,
unmodified `app.services.release_processing.ReleaseProcessingService`
for each. Frozen and normative in
docs/product/automated-economic-maintenance-v1.md.

This module contains NO economic logic, NO classification, and NO
methodology of its own (frozen contract §48's own "orchestrator
responsibilities" boundary, restated as this module's own docstring
contract, not merely a comment). It is a pure trigger-and-record
layer: discover due work (§8, `ReleaseProcessingRepository.list_due_occurrence_ids`,
unmodified by this module), acquire an occurrence-scoped PostgreSQL
advisory lock before processing (§18/§19,
`app.services.release_processing.try_acquire_and_process_occurrence`,
shared with the manual CLI), call the existing service once per
occurrence inside its own `session_scope()` (§20/§21, preserved
unmodified -- one transaction per occurrence, never batched), and
record sweep-level operational health separately (§30/§53) -- never
conflated with any individual occurrence's own economic freshness.

Deliberately not a scheduler: `MaintenanceOrchestrator.run_sweep` runs
exactly ONE bounded sweep and returns -- it never loops, never sleeps,
never schedules itself (frozen contract §17/§45/§55: the SCHEDULER
decides WHEN this runs; this class decides WHAT due work exists and
processes it, exactly once per call).
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.clients.fred import FREDClient
from app.db.session import session_scope
from app.repositories.maintenance_repository import MaintenanceRepository
from app.repositories.release_processing_repository import ReleaseProcessingRepository
from app.services.release_processing import ReleaseProcessingService, try_acquire_and_process_occurrence

# Frozen (docs/product/automated-economic-maintenance-v1.md §14): a
# tunable, operator-configurable retry window, deliberately NOT an
# empirically measured economic fact -- "about a business week" past
# an occurrence's own scheduled_date. This same bound also serves
# §50's own bounded-backfill requirement for free: any occurrence
# older than this window is never surfaced as due, so automation never
# processes ancient history on first launch.
DEFAULT_RETRY_WINDOW_DAYS = 7

# The two CheckRunStatus values that count as a genuine processing
# failure for this sweep's own `failed_count` -- mirrors
# `app.operations.process_release._FAILURE_STATUSES` exactly (kept as
# an independent, duplicated constant rather than an import, matching
# this project's own established "two independent, small,
# already-correct call sites, never one shared abstraction for a
# two-line constant" precedent -- e.g. `month_before` reimplemented
# per domain, `app.domain.labor_release_processing`'s own calendar
# helper).
_FAILURE_STATUSES = frozenset({"PARTIAL_FAILURE", "FAILED_PROVIDER"})


@dataclass
class MaintenanceSweepOutcome:
    """The complete, structured result of one bounded sweep -- returned
    to the CLI (`app.operations.run_maintenance`) for safe, structured
    printing and exit-code selection. Never itself persisted verbatim;
    `sweep_id` is the one field that lets a caller cross-reference the
    already-persisted `MaintenanceSweep` row this outcome describes."""

    sweep_id: int
    started_at: datetime
    finished_at: datetime
    due_count: int
    processed_count: int
    skipped_lock_count: int
    failed_count: int
    database_failure_occurrence_ids: list[int] = field(default_factory=list)


class MaintenanceOrchestrator:
    def __init__(self, fred_client: FREDClient):
        self._service = ReleaseProcessingService(fred_client)

    def run_sweep(self, as_of_date: date, retry_window_days: int = DEFAULT_RETRY_WINDOW_DAYS) -> MaintenanceSweepOutcome:
        """Run exactly one bounded sweep: start a sweep record, discover
        due occurrences (§8), process each one individually (advisory-
        locked, one `session_scope()` per occurrence, §18-§21), and
        finish the sweep record with truthful counts (§53/§54).

        A database-layer failure processing one occurrence (a genuine
        `OperationalError`/`SQLAlchemyError`, §23) is caught per-
        occurrence here -- the exact gap the frozen contract names: no
        `ReleaseCheckRun` row exists for that attempt at all, so this
        sweep's own in-memory accounting, folded into `failed_count`
        and `database_failure_occurrence_ids` below and printed by the
        CLI, is the only surviving evidence. One occurrence's own
        database failure never aborts the sweep as a whole -- the loop
        continues to the next due occurrence, and the sweep record is
        still finished truthfully at the end (§30: worker health is
        never conflated with any individual occurrence's own outcome).
        """
        started_at = datetime.now(timezone.utc)
        with session_scope() as session:
            sweep = MaintenanceRepository(session).start_sweep(started_at)
            sweep_id = sweep.id

        with session_scope() as session:
            due_occurrence_ids = ReleaseProcessingRepository(session).list_due_occurrence_ids(as_of_date, retry_window_days)

        processed_count = 0
        skipped_lock_count = 0
        failed_count = 0
        database_failure_occurrence_ids: list[int] = []

        for occurrence_id in due_occurrence_ids:
            try:
                with session_scope() as session:
                    result = try_acquire_and_process_occurrence(self._service, occurrence_id, session, as_of_date)
            except (OperationalError, SQLAlchemyError):
                failed_count += 1
                database_failure_occurrence_ids.append(occurrence_id)
                continue

            if result is None:
                # Advisory lock not acquired -- another process
                # (automated or manual) is already handling this
                # occurrence. Not a failure; deferred to the next
                # sweep, per try_acquire_and_process_occurrence's own
                # docstring.
                skipped_lock_count += 1
                continue

            processed_count += 1
            if result.status in _FAILURE_STATUSES:
                failed_count += 1

        finished_at = datetime.now(timezone.utc)
        with session_scope() as session:
            MaintenanceRepository(session).finish_sweep(
                sweep_id,
                finished_at=finished_at,
                status="SUCCEEDED",
                due_count=len(due_occurrence_ids),
                processed_count=processed_count,
                failed_count=failed_count,
            )

        return MaintenanceSweepOutcome(
            sweep_id=sweep_id,
            started_at=started_at,
            finished_at=finished_at,
            due_count=len(due_occurrence_ids),
            processed_count=processed_count,
            skipped_lock_count=skipped_lock_count,
            failed_count=failed_count,
            database_failure_occurrence_ids=database_failure_occurrence_ids,
        )
