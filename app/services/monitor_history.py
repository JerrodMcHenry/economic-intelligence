"""Point-in-time intelligence history (Increment #32).

Turns Increment #31's temporal foundation into an answerable product
question set:

    What did MacroChipz know at time T?
    What did it conclude?
    Does that conclusion still reproduce?
    What does today's revised data say about the same period?
    Why might the two differ?

Every economic judgement the UI renders is made here. The frontend
formats; it never compares values, classifies a revision, decides
whether a comparison is valid, or re-runs a methodology.

Three deliberate restraints:

1. **The methodology names its own inputs.** `historical_inputs` is read
   off the recomputed result's evidence
   (`InflationMetricEvidence.endpoint_date_*`,
   `LaborObservationEvidence.observation_date`) rather than from a
   lookback window this module invents. A second definition of "which
   observations matter" would be a second methodology, free to drift
   from the real one.

2. **Then and today are computed by the SAME function at the SAME
   period.** `compute_series_momentum_at` / `compute_labor_monitor_result_at`
   are called twice -- once over as-of data, once over current data --
   so any difference is attributable to the data, never to two code
   paths that merely resemble each other.

3. **A comparison is refused rather than faked.** Across methodology
   versions, today's binary answers a different question, so no
   `current_state` is produced at all.
"""

from datetime import date, datetime

from sqlalchemy.orm import Session

from app.db.models import RecordedMonitorResult
from app.domain.inflation import compute_series_momentum_at
from app.domain.labor import compute_labor_monitor_result_at
from app.models.inflation import (
    PRIMARY_CONCEPT_ID,
    METHODOLOGY_ID as INFLATION_METHODOLOGY_ID,
    PRIMARY_SERIES_ID,
    SeriesMomentumResult,
)
from app.models.labor import (
    EMPLOYMENT_CONCEPT_ID,
    LaborSeriesIdentities,
    UNEMPLOYMENT_CONCEPT_ID,
    CONDITION_DEADBAND_JOBS,
    METHODOLOGY_ID as LABOR_METHODOLOGY_ID,
    MOMENTUM_DEADBAND_JOBS,
    PAYEMS_SERIES_ID,
    UNEMPLOYMENT_DEADBAND_PP,
    UNRATE_SERIES_ID,
)
from app.models.monitor_history import (
    ComparisonStatus,
    CurrentComparison,
    HistoricalInput,
    HistoryMonitor,
    InputComparison,
    InputUnit,
    MonitorHistoryDetail,
    MonitorHistoryResponse,
    PreviousRecordedResult,
    RecordedIntelligenceEntry,
    RelatedDataChange,
    ReplaySummary,
)
from app.models.releases import PaginationMeta
from app.models.replay import ReplayResult
from app.repositories.series_repository import SeriesRepository
from app.services.series_identity import resolve_identity
from app.repositories.monitor_history_repository import MonitorHistoryRepository
from app.repositories.observation_versions import ObservationVersionRepository
from app.services.replay import RecomputedResult, ReplayService

#: The canonical series each monitor's own recorded state depends on --
#: the same mapping replay uses, restated here because this service
#: also needs it for the "today" side, which replay has no part in.
_MONITOR_INPUT_SERIES: dict[str, tuple[str, ...]] = {
    "inflation": (PRIMARY_SERIES_ID,),
    "labor": (PAYEMS_SERIES_ID, UNRATE_SERIES_ID),
}

#: Each canonical input series' unit AS THE METHODOLOGY REPORTS IT --
#: not as the provider publishes it. `labor_v1.0` converts PAYEMS from
#: FRED-native thousands into actual jobs before putting it in evidence
#: (`app/domain/labor.py`'s `build_jobs_index`), so JOBS is the honest
#: label for what `value_then`/`value_today` carry here.
_SERIES_UNIT: dict[str, InputUnit] = {
    PRIMARY_SERIES_ID: "INDEX",
    PAYEMS_SERIES_ID: "JOBS",
    UNRATE_SERIES_ID: "PERCENT",
}

#: The methodology version THIS binary implements for each monitor.
_MONITOR_METHODOLOGY: dict[str, str] = {
    "inflation": INFLATION_METHODOLOGY_ID,
    "labor": LABOR_METHODOLOGY_ID,
}


class RecordedResultNotFoundError(Exception):
    """A well-formed id that names no recorded result for this monitor.
    Mapped to 404 at the route boundary, exactly as
    `SeriesNotFoundError` already is."""


def _used_observations(result: RecomputedResult) -> dict[tuple[str, date], float | None]:
    """Which exact observations this methodology consumed, and what it
    saw at each.

    Read off the result's own evidence -- never re-derived. A month the
    methodology required but could not find is present with a `None`
    value rather than omitted, because "we needed this and it was
    missing" is one of the more important things a reader can learn.
    """
    used: dict[tuple[str, date], float | None] = {}

    if isinstance(result, SeriesMomentumResult):
        for evidence in (result.evidence_1m, result.evidence_3m, result.evidence_6m, result.evidence_12m):
            if evidence is None:
                continue
            used[(evidence.series_id, evidence.endpoint_date_past)] = evidence.endpoint_value_past
            used[(evidence.series_id, evidence.endpoint_date_current)] = evidence.endpoint_value_current
        return used

    for observation in (*result.employment.observations, *result.unemployment.observations):
        used[(observation.series_id, observation.observation_date)] = observation.value
    return used


def _classify_input(value_then: float | None, value_today: float | None, exists_today: bool) -> InputComparison:
    """One observation's then-vs-today relationship.

    `exists_today` is passed separately from `value_today` because a
    row that exists carrying a null value is a different fact from no
    row at all, and collapsing the two would report a withdrawal that
    never happened.
    """
    if value_then is None and not exists_today:
        return "UNCHANGED"
    if value_then is None:
        return "ONLY_AVAILABLE_TODAY" if value_today is not None else "UNCHANGED"
    if not exists_today or value_today is None:
        return "ONLY_AVAILABLE_THEN"
    return "UNCHANGED" if value_today == value_then else "REVISED"


class MonitorHistoryService:
    """Read-only. Never writes, and in particular never touches
    `recorded_monitor_results`, which stays append-only (ADR-025)."""

    def get_history(
        self, session: Session, monitor: HistoryMonitor, limit: int, offset: int
    ) -> MonitorHistoryResponse:
        repo = MonitorHistoryRepository(session)
        replay = ReplayService()

        total = repo.count_recorded_results(monitor)
        results = repo.list_recorded_results(monitor, limit=limit, offset=offset)
        previous_by_id = repo.get_previous_recorded_results(monitor, results)

        entries = [
            self._entry(recorded, replay.replay_recorded_result(session, recorded.id), previous_by_id.get(recorded.id))
            for recorded in results
        ]

        return MonitorHistoryResponse(
            monitor=monitor,
            entries=entries,
            pagination=PaginationMeta(limit=limit, offset=offset, returned=len(entries), total=total),
        )

    def get_history_detail(
        self, session: Session, monitor: HistoryMonitor, recorded_result_id: int
    ) -> MonitorHistoryDetail:
        repo = MonitorHistoryRepository(session)
        recorded = repo.get_recorded_result(monitor, recorded_result_id)
        if recorded is None:
            raise RecordedResultNotFoundError(recorded_result_id)

        replayed, recomputed_then = ReplayService().replay_with_recomputed_result(session, recorded.id)
        previous = repo.get_previous_recorded_result(monitor, recorded.calculated_at, recorded.id)
        entry = self._entry(recorded, replayed, previous)

        then_inputs = _used_observations(recomputed_then) if recomputed_then is not None else {}
        recomputed_today = self._recompute_on_current_data(session, repo, recorded)

        historical_inputs = self._compare_inputs(session, recorded, then_inputs, recomputed_today)
        comparison = self._build_comparison(recorded, replayed, recomputed_today, historical_inputs)
        related, other_count = self._related_changes(repo, recorded, then_inputs)

        return MonitorHistoryDetail(
            recorded=entry,
            historical_inputs=historical_inputs,
            current_comparison=comparison,
            related_changes=related,
            other_changes_in_same_run=other_count,
        )

    # -----------------------------------------------------------------
    # Assembly
    # -----------------------------------------------------------------

    @staticmethod
    def _entry(
        recorded: RecordedMonitorResult,
        replayed: ReplayResult,
        previous: RecordedMonitorResult | None,
    ) -> RecordedIntelligenceEntry:
        return RecordedIntelligenceEntry(
            recorded_result_id=recorded.id,
            monitor=recorded.monitor,
            state=recorded.state,
            evaluation_period=recorded.evaluation_period,
            calculated_at=recorded.calculated_at,
            methodology_id=recorded.methodology_id,
            data_basis=recorded.data_basis,
            replay=ReplaySummary(
                outcome=replayed.outcome,
                replayed_state=replayed.replayed_state,
                reason=replayed.reason,
                inputs_include_backfilled=replayed.inputs_include_backfilled,
            ),
            previous=None
            if previous is None
            else PreviousRecordedResult(
                recorded_result_id=previous.id,
                state=previous.state,
                evaluation_period=previous.evaluation_period,
                calculated_at=previous.calculated_at,
                same_evaluation_period=previous.evaluation_period == recorded.evaluation_period,
                state_changed=previous.state != recorded.state,
            ),
        )

    @staticmethod
    def _recompute_on_current_data(
        session: Session, repo: MonitorHistoryRepository, recorded: RecordedMonitorResult
    ) -> RecomputedResult | None:
        """The same methodology, the same evaluation period, today's
        canonical observations.

        Returns `None` when the recorded row names a methodology this
        binary does not implement -- running today's code would answer
        a different question, and a number produced that way would be
        worse than no number.
        """
        if recorded.methodology_id != _MONITOR_METHODOLOGY.get(recorded.monitor):
            return None

        if recorded.monitor == "inflation":
            return compute_series_momentum_at(
                repo.list_current_observations(PRIMARY_SERIES_ID),
                resolve_identity(SeriesRepository(session), PRIMARY_CONCEPT_ID),
                recorded.evaluation_period,
            )

        return compute_labor_monitor_result_at(
            repo.list_current_observations(PAYEMS_SERIES_ID),
            repo.list_current_observations(UNRATE_SERIES_ID),
            recorded.evaluation_period,
            CONDITION_DEADBAND_JOBS,
            MOMENTUM_DEADBAND_JOBS,
            UNEMPLOYMENT_DEADBAND_PP,
            identities=LaborSeriesIdentities(
                employment=resolve_identity(SeriesRepository(session), EMPLOYMENT_CONCEPT_ID),
                unemployment=resolve_identity(SeriesRepository(session), UNEMPLOYMENT_CONCEPT_ID),
            ),
        )

    @staticmethod
    def _compare_inputs(
        session: Session,
        recorded: RecordedMonitorResult,
        then_inputs: dict[tuple[str, date], float | None],
        recomputed_today: RecomputedResult | None,
    ) -> list[HistoricalInput]:
        """Pair each observation the methodology used then with what the
        same methodology sees at that observation now.

        BOTH sides are read from methodology evidence -- never one side
        from evidence and the other from a raw `economic_observations`
        read. That symmetry is a correctness requirement, not tidiness:
        `labor_v1.0`'s PAYEMS evidence carries the canonical jobs value
        (158,268,000) while the persisted row carries FRED-native
        thousands (158,268), so comparing evidence against raw storage
        reported every single Labor input as REVISED by a factor of
        1,000. Comparing like with like makes a unit mismatch
        structurally impossible.

        Both date sets are derived from the same evaluation period by
        the same code, so they coincide by construction; the union is
        taken anyway rather than assumed, because silently dropping an
        unpaired date would hide exactly the kind of discrepancy this
        feature exists to reveal.
        """
        if not then_inputs:
            return []

        today_inputs = _used_observations(recomputed_today) if recomputed_today is not None else {}

        versions = ObservationVersionRepository(session)
        backfilled: dict[tuple[str, date], bool] = {}
        for series_id in _MONITOR_INPUT_SERIES.get(recorded.monitor, ()):
            for row in versions.get_observations_as_of(series_id, recorded.calculated_at):
                backfilled[(series_id, row.observation_date)] = row.is_backfilled

        inputs: list[HistoricalInput] = []
        for key in sorted(set(then_inputs) | set(today_inputs)):
            series_id, observation_date = key
            value_then = then_inputs.get(key)
            value_today = today_inputs.get(key)
            inputs.append(
                HistoricalInput(
                    series_id=series_id,
                    observation_date=observation_date,
                    value_then=value_then,
                    value_today=value_today,
                    value_unit=_SERIES_UNIT.get(series_id, "INDEX"),
                    comparison=_classify_input(value_then, value_today, key in today_inputs),
                    is_backfilled=backfilled.get(key, False),
                )
            )
        return inputs

    @staticmethod
    def _build_comparison(
        recorded: RecordedMonitorResult,
        replayed: ReplayResult,
        recomputed_today: RecomputedResult | None,
        historical_inputs: list[HistoricalInput],
    ) -> CurrentComparison:
        methodology_today = _MONITOR_METHODOLOGY.get(recorded.monitor, "unknown")
        methodology_differs = recorded.methodology_id != methodology_today

        # Across methodology versions there is nothing honest to
        # compute: today's code implements different rules, so its
        # answer is not "the same analysis on newer data".
        if methodology_differs or recomputed_today is None:
            return CurrentComparison(
                status="NOT_COMPARABLE",
                reason="METHODOLOGY_VERSION_DIFFERS",
                current_state=None,
                state_differs=None,
                methodology_id_then=recorded.methodology_id,
                methodology_id_today=methodology_today,
                methodology_differs=methodology_differs,
                changed_input_count=0,
            )

        # Today's reconstruction stands on its own and is reported even
        # when replay could not run -- but with no historical inputs to
        # compare against, the INPUT comparison is genuinely unavailable
        # rather than "nothing changed".
        current_state = recomputed_today.state
        state_differs = current_state != recorded.state

        if replayed.outcome == "NOT_REPLAYABLE":
            return CurrentComparison(
                status="NOT_COMPARABLE",
                reason="REPLAY_UNAVAILABLE",
                current_state=current_state,
                state_differs=state_differs,
                methodology_id_then=recorded.methodology_id,
                methodology_id_today=methodology_today,
                methodology_differs=False,
                changed_input_count=0,
            )

        changed = sum(1 for row in historical_inputs if row.comparison != "UNCHANGED")
        status: ComparisonStatus = "IDENTICAL_INPUTS" if changed == 0 else "INPUTS_CHANGED"
        return CurrentComparison(
            status=status,
            reason=None,
            current_state=current_state,
            state_differs=state_differs,
            methodology_id_then=recorded.methodology_id,
            methodology_id_today=methodology_today,
            methodology_differs=False,
            changed_input_count=changed,
        )

    @staticmethod
    def _related_changes(
        repo: MonitorHistoryRepository,
        recorded: RecordedMonitorResult,
        then_inputs: dict[tuple[str, date], float | None],
    ) -> tuple[list[RelatedDataChange], int]:
        """Source-data changes from the same check run, narrowed to the
        observations this result's methodology actually used.

        The narrowing is what makes the list meaningful rather than
        merely true: a bootstrap run can carry years of changes, and
        attaching all of them to every result would drown the handful
        that bear on this one. The remainder is counted, not hidden.
        """
        updates = repo.list_observation_updates_for_run(recorded.release_check_run_id)
        used_keys = set(then_inputs)

        related = [
            RelatedDataChange(
                series_id=update.series_id,
                observation_date=update.observation_date,
                change_type=update.change_type,
                previous_value=update.previous_value,
                new_value=update.new_value,
                detected_at=update.detected_at,
            )
            for update in updates
            if (update.series_id, update.observation_date) in used_keys
        ]
        return related, len(updates) - len(related)
