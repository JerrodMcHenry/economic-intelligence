"""Application/use-case orchestration for Increment #25G's Since Last
Visit V1 read model -- see docs/product/since-last-visit-v1.md (#25F),
the frozen contract this module implements verbatim.

`SinceLastVisitService.get_recap` is a pure READ: it never calls FRED,
never writes `RecordedMonitorResult`/`ReleaseCheckRun`/`MaintenanceSweep`,
never triggers release processing or maintenance, and never persists a
user checkpoint (checkpoint storage is #25H's own client-side
responsibility, contract §67/§91). It captures the server's own UTC
`through` watermark exactly once, before any query executes (contract
§10-13's own race-safety requirement), resolves the effective window
via the pure `app.domain.since_last_visit.resolve_window`, fetches the
bounded candidate set via `SinceLastVisitRepository` (five query
shapes, §61), and hands everything to the pure, deterministic
categorization functions in `app.domain.since_last_visit` -- this
module itself performs no categorization logic of its own, only
orchestration and ORM-row-to-input-shape translation.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

import app.domain.since_last_visit as domain
from app.models.inflation import CONFIRMATION_SERIES_ID, HEADLINE_CPI_SERIES_ID, PRIMARY_SERIES_ID, TARGET_SERIES_ID
from app.models.labor import PAYEMS_SERIES_ID, UNRATE_SERIES_ID
from app.models.since_last_visit import DomainRecap, Recalculation, SinceLastVisitResponse, SourceUpdate, StructuralChange
from app.repositories.since_last_visit_repository import SinceLastVisitRepository

INFLATION_SERIES_IDS: frozenset[str] = frozenset(
    {PRIMARY_SERIES_ID, CONFIRMATION_SERIES_ID, TARGET_SERIES_ID, HEADLINE_CPI_SERIES_ID}
)
LABOR_SERIES_IDS: frozenset[str] = frozenset({PAYEMS_SERIES_ID, UNRATE_SERIES_ID})


class SinceLastVisitService:
    def get_recap(self, session: Session, requested_after: datetime | None) -> SinceLastVisitResponse:
        # The one, single clock read for this entire request -- captured
        # BEFORE any query executes (contract §10-13's own central
        # race-safety requirement: capturing `through` first, then
        # filtering `completed_at <= through`, guarantees no event this
        # response might miss is ever permanently lost).
        through = datetime.now(timezone.utc)

        effective_after, first_visit, lookback_clamped = domain.resolve_window(requested_after, through)
        # `effective_after` is always a real, bounded query boundary
        # (contract §7/§49 -- even a first visit is bounded to the
        # default lookback window, never unbounded). The RESPONSE's own
        # `after` field is `None` specifically on a first visit (§55) --
        # a presentation fact distinct from the query boundary itself.
        after = None if first_visit else effective_after

        repo = SinceLastVisitRepository(session)
        inflation_release_ids, labor_release_ids = repo.relevant_release_ids_by_series(INFLATION_SERIES_IDS, LABOR_SERIES_IDS)
        all_release_ids = inflation_release_ids | labor_release_ids

        check_run_rows = repo.list_check_runs_in_window(all_release_ids, effective_after, through)
        check_run_ids = [run.id for run, _release in check_run_rows]
        calculated_at_by_run = {run.id: run.completed_at for run, _release in check_run_rows}

        observation_rows = repo.list_observation_updates_for_runs(check_run_ids)
        analysis_rows = repo.list_analysis_updates_for_runs(check_run_ids)
        recorded_rows = repo.list_recorded_results_for_runs(check_run_ids)

        series_ids = sorted({row.series_id for row in observation_rows})
        series_metadata = repo.list_series_metadata(series_ids)

        earliest_recorded_result_id = repo.earliest_recorded_result_id_by_monitor()

        analysis_inputs = [
            domain.AnalysisChangeInput(
                release_check_run_id=row.release_check_run_id,
                component=row.component,
                event_type=row.event_type,
                field=row.field,
                previous_value=row.previous_value,
                current_value=row.current_value,
                evaluation_period=row.evaluation_period,
                methodology_id=row.methodology_id,
            )
            for row in analysis_rows
        ]
        recorded_inputs = [
            domain.RecordedResultInput(
                id=row.id,
                release_check_run_id=row.release_check_run_id,
                monitor=row.monitor,
                evaluation_period=row.evaluation_period,
                state=row.state,
                methodology_id=row.methodology_id,
            )
            for row in recorded_rows
        ]
        observation_inputs = [
            domain.ObservationChangeInput(
                release_check_run_id=row.release_check_run_id,
                series_id=row.series_id,
                series_title=series_metadata[row.series_id].title if row.series_id in series_metadata else None,
                change_type=row.change_type,
            )
            for row in observation_rows
        ]

        structural_changes = domain.select_structural_changes(analysis_inputs, calculated_at_by_run)
        changed_run_monitor_pairs = frozenset((item.release_check_run_id, item.monitor) for item in structural_changes)
        recalculations = domain.select_recalculations(
            recorded_inputs, calculated_at_by_run, changed_run_monitor_pairs, earliest_recorded_result_id
        )
        recomputed_run_monitor_pairs = frozenset((row.release_check_run_id, row.monitor) for row in recorded_inputs)
        source_updates = domain.select_source_updates(
            observation_inputs, recomputed_run_monitor_pairs, INFLATION_SERIES_IDS, LABOR_SERIES_IDS
        )

        inflation_recap = self._build_domain_recap(
            "inflation", inflation_release_ids, effective_after, through, structural_changes, recalculations, source_updates, repo
        )
        labor_recap = self._build_domain_recap(
            "labor", labor_release_ids, effective_after, through, structural_changes, recalculations, source_updates, repo
        )

        return SinceLastVisitResponse(
            after=after,
            through=through,
            first_visit=first_visit,
            lookback_clamped=lookback_clamped,
            inflation=inflation_recap,
            labor=labor_recap,
        )

    @staticmethod
    def _build_domain_recap(
        monitor: domain.Monitor,
        release_ids: frozenset[int],
        after: datetime,
        through: datetime,
        structural_changes: list[domain.StructuralChangeItem],
        recalculations: list[domain.RecalculationItem],
        source_updates: list[domain.SourceUpdateItem],
        repo: SinceLastVisitRepository,
    ) -> DomainRecap:
        settled_ids_in_window = repo.settled_release_ids_in_window(release_ids, after, through)
        any_sweep = repo.any_sweep_started_in_window(after, through)
        coverage = domain.compute_coverage(release_ids, settled_ids_in_window, any_sweep)

        last_checked_at = repo.latest_settled_completed_at(release_ids)
        if last_checked_at is None:
            last_checked_at = repo.latest_sweep_finished_at()

        return DomainRecap(
            monitor=monitor,
            coverage=coverage,
            last_checked_at=last_checked_at,
            structural_changes=[
                StructuralChange(
                    monitor=item.monitor,
                    event_type=item.event_type,
                    field=item.field,
                    previous_value=item.previous_value,
                    current_value=item.current_value,
                    evaluation_period=item.evaluation_period,
                    methodology_id=item.methodology_id,
                    calculated_at=item.calculated_at,
                    release_check_run_id=item.release_check_run_id,
                )
                for item in structural_changes
                if item.monitor == monitor
            ],
            recalculations=[
                Recalculation(
                    monitor=item.monitor,
                    kind=item.kind,
                    state=item.state,
                    evaluation_period=item.evaluation_period,
                    count=item.count,
                    calculated_at=item.calculated_at,
                    methodology_id=item.methodology_id,
                )
                for item in recalculations
                if item.monitor == monitor
            ],
            source_updates=[
                SourceUpdate(
                    monitor=item.monitor,
                    series_id=item.series_id,
                    series_title=item.series_title,
                    change_type=item.change_type,
                    release_check_run_id=item.release_check_run_id,
                )
                for item in source_updates
                if item.monitor == monitor
            ],
        )
