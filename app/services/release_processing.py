"""Application/use-case orchestration for Increment #18's release-driven
update pipeline -- the ONE new module that legitimately imports both
the release-calendar side (`app.repositories.release_repository`,
read-only) and the series/Inflation side
(`app.repositories.release_processing_repository`,
`app.domain.inflation`, `app.domain.inflation_what_changed`). This is
deliberate: `app.repositories.release_repository`/`app.services.releases`/
`app.api.releases` remain structurally forbidden from importing
anything series/observation/Inflation-shaped (see
`tests/integration/test_transaction_and_safety.py::TestReleaseCalendarStructuralIndependence`)
-- release processing is a distinct subsystem that bridges the two,
never an addition to either existing one.

High-level flow (see docs/architecture/release-processing-v1.md):

    ReleaseOccurrence (eligibility only -- proves nothing about
    publication)
        -> ReleaseSeriesMapping ("what to check")
        -> bounded, date-based FRED fetch (five-year rolling horizon)
        -> classify each observation NEW / REVISED / UNCHANGED
        -> capture BEFORE Inflation evidence (existing persisted data)
        -> write canonical NEW/REVISED observations
        -> capture AFTER Inflation evidence
        -> diff before/after using EXISTING comparison primitives
           (app.domain.inflation_what_changed) -- never reimplemented
        -> persist ReleaseCheckRun + ReleaseObservationUpdate +
           ReleaseAnalysisUpdate rows, one transaction, one occurrence

The live Inflation Monitor remains stateless and canonical throughout
-- nothing here persists an `InflationMonitorResult` snapshot.
"""

from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.clients.fred import FREDClient, FREDError
from app.domain.inflation import compute_confirmation_at, compute_series_momentum_at, compute_target_at
from app.domain.inflation_what_changed import (
    compare_confirmation_section,
    compare_series_momentum_section,
    compare_target_section,
)
from app.domain.labor import compute_labor_monitor_result_at
from app.domain.labor_release_processing import (
    LABOR_SERIES_IDS,
    labor_affected_evaluation_periods,
)
from app.domain.labor_what_changed import (
    compare_employment_section,
    compare_labor_state,
    compare_unemployment_section,
)
from app.domain.release_processing import (
    affected_evaluation_periods,
    classify_observation_change,
    components_for_series,
    five_year_observation_start,
)
from app.models.inflation import CONFIRMATION_SERIES_ID, HEADLINE_CPI_SERIES_ID, PRIMARY_SERIES_ID, TARGET_SERIES_ID
from app.models.inflation_what_changed import ChangeComponent
from app.models.labor import (
    CONDITION_DEADBAND_JOBS,
    MOMENTUM_DEADBAND_JOBS,
    PAYEMS_SERIES_ID,
    UNEMPLOYMENT_DEADBAND_PP,
    UNRATE_SERIES_ID,
    LaborMonitorResult,
)
from app.models.release_processing import (
    AnalysisChangeRecord,
    CheckRunStatus,
    ObservationChangeRecord,
    ReleaseCheckRunResult,
    SeriesCheckOutcome,
)
from app.models.series import Observation
from app.repositories.release_processing_repository import ReleaseProcessingRepository
from app.repositories.release_repository import ReleaseRepository

# A large, fixed page size, not a per-request tuning knob -- comfortably
# above any realistic monthly canonical series' five-year observation
# count (~60 rows), and well within FRED's own documented maximum page
# size, so the bounded five-year window is never silently truncated.
_OBSERVATION_FETCH_LIMIT = 100_000

# The four canonical Inflation Monitor inputs -- the only series whose
# change this pipeline ever computes an Inflation analytical
# consequence for (see app.domain.release_processing.SERIES_TO_COMPONENTS).
# Loaded for before/after evidence regardless of which of them this
# particular release's own mappings touch, because a change to one
# (e.g. Core PCE) can affect a section (e.g. Confirmation) that also
# depends on another (Core CPI) this release never mapped at all.
#
# Increment #20D.2: Labor's own two canonical inputs
# (LABOR_SERIES_IDS, from app.domain.labor_release_processing) are a
# SEPARATE, independently-checked set -- never merged into this tuple.
# A changed observation's series is checked against BOTH sets
# independently (never `elif`), so a series belonging to both families
# in the future would correctly feed both, per
# docs/architecture/labor-release-integration-v1.md §26.
_CANONICAL_SERIES_IDS: tuple[str, ...] = (PRIMARY_SERIES_ID, CONFIRMATION_SERIES_ID, TARGET_SERIES_ID, HEADLINE_CPI_SERIES_ID)


class OccurrenceNotFoundError(Exception):
    """Raised when the given `release_occurrence_id` does not exist."""


class OccurrenceNotEligibleError(Exception):
    """Raised when the given occurrence's `scheduled_date` is still in
    the future relative to `as_of_date` -- release times are unknown in
    V1 (see docs/architecture/release-intelligence-v1.md #3), so
    today's scheduled date IS eligible (an early same-day check
    returning NO_CHANGE is valid), but a genuinely future-dated
    occurrence is not: there is no provider-side reason to expect new
    data before its own scheduled date has arrived. This mirrors
    `app.domain.releases.classify_schedule_status`'s own boundary
    (`scheduled_date >= as_of_date -> SCHEDULED`) exactly -- eligible
    is `scheduled_date <= as_of_date`, the complement."""


def _safe_error_message(exc: FREDError) -> str:
    """A generic, non-leaking per-failure-kind message -- mirrors the
    same discipline `app.services.releases._safe_sync_error_message`
    already applies, restated independently here rather than imported
    (see this module's own docstring on why release processing stays
    its own, separate subsystem)."""
    from app.clients.fred import FREDAuthError, FREDTimeoutError, FREDUpstreamError

    if isinstance(exc, FREDAuthError):
        return "FRED rejected the configured API key."
    if isinstance(exc, FREDTimeoutError):
        return "FRED request timed out."
    if isinstance(exc, FREDUpstreamError):
        return "FRED returned an unexpected or malformed response."
    return "FRED request failed."


def _parse_value(raw: str) -> float | None:
    """FRED represents a missing observation with the literal string
    '.' -- the identical rule `app.services.economic_data._parse_value`
    already applies, restated independently (see module docstring)."""
    if raw == ".":
        return None
    return float(raw)


class ReleaseProcessingService:
    """Explicit, manually-triggered only -- no scheduler anywhere in
    this class's call graph, and nothing here is ever invoked by a
    read. Requires a `FREDClient` (release processing has no
    meaningful database-only mode, the same reasoning
    `app.services.releases.ReleaseSyncService` already applies)."""

    def __init__(self, fred_client: FREDClient):
        self._fred_client = fred_client

    def process_occurrence(self, occurrence_id: int, session: Session, as_of_date: date) -> ReleaseCheckRunResult:
        """Process one release occurrence: fetch its mapped series over
        a bounded five-year window, classify and persist genuine
        changes, and compute+persist any resulting deterministic
        Inflation analytical consequence -- all within the caller's own
        transaction (the caller owns `session`'s commit/rollback
        boundary via `session_scope()`, exactly like every other
        service in this project; this method never commits or rolls
        back itself).

        Raises `OccurrenceNotFoundError` if `occurrence_id` doesn't
        exist, and `OccurrenceNotEligibleError` if `occurrence`'s
        `scheduled_date` is still in the future relative to
        `as_of_date` (see that exception's own docstring). Provider
        failures for individual mapped series are caught and recorded
        per-series (never raised) -- only a genuine database-layer
        failure propagates, which aborts this whole occurrence's
        transaction (see docs/architecture/release-processing-v1.md's
        transaction section).
        """
        started_at = datetime.now(timezone.utc)

        release_repo = ReleaseRepository(session)
        occurrence = release_repo.get_occurrence_by_id(occurrence_id)
        if occurrence is None:
            raise OccurrenceNotFoundError(f"Release occurrence {occurrence_id} does not exist.")
        if occurrence.scheduled_date > as_of_date:
            raise OccurrenceNotEligibleError(
                f"Release occurrence {occurrence_id} is not yet eligible for checking "
                f"(scheduled {occurrence.scheduled_date.isoformat()}, as-of {as_of_date.isoformat()})."
            )

        repo = ReleaseProcessingRepository(session)
        mappings = repo.get_active_mappings(occurrence.economic_release_id)
        observation_start = five_year_observation_start(as_of_date)

        series_outcomes: list[SeriesCheckOutcome] = []
        observation_changes: list[ObservationChangeRecord] = []
        any_provider_failure = False
        any_provider_success = False

        for mapping in mappings:
            outcome, changes = self._check_one_series(repo, mapping.series_id, observation_start)
            series_outcomes.append(outcome)
            if outcome.succeeded:
                any_provider_success = True
                observation_changes.extend(changes)
            else:
                any_provider_failure = True

        analysis_changes = self._apply_changes_and_compute_analysis(repo, observation_changes)

        completed_at = datetime.now(timezone.utc)
        status = _determine_status(any_provider_failure, any_provider_success, observation_changes)
        check_run = repo.add_check_run(occurrence.id, status, started_at, completed_at)
        for record in observation_changes:
            repo.add_observation_update(check_run.id, record)
        for record in analysis_changes:
            repo.add_analysis_update(check_run.id, record)

        return ReleaseCheckRunResult(
            release_occurrence_id=occurrence.id,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            series_outcomes=series_outcomes,
            observation_changes=observation_changes,
            analysis_changes=analysis_changes,
        )

    # -----------------------------------------------------------------
    # Per-series fetch + classification (no writes -- read-only)
    # -----------------------------------------------------------------

    def _check_one_series(
        self, repo: ReleaseProcessingRepository, series_id: str, observation_start: date
    ) -> tuple[SeriesCheckOutcome, list[ObservationChangeRecord]]:
        try:
            raw_observations = self._fred_client.get_observations(
                series_id, limit=_OBSERVATION_FETCH_LIMIT, observation_start=observation_start, sort_order="asc"
            )
            if not raw_observations:
                # Nothing to classify -- skip the metadata fetch entirely
                # rather than creating an empty EconomicSeries row or
                # spending an extra FRED call for a series with no data
                # in this window at all.
                return (
                    SeriesCheckOutcome(series_id=series_id, succeeded=True, new_count=0, revised_count=0, unchanged_count=0),
                    [],
                )

            economic_series = repo.get_series_by_series_id(series_id)
            if economic_series is None:
                info = self._fred_client.get_series_info(series_id)
                economic_series = repo.create_series(series_id=series_id, title=info["title"], units=info["units"])

            persisted = repo.get_observations_by_date(economic_series.id)
            detected_at = datetime.now(timezone.utc)

            new_count = revised_count = unchanged_count = 0
            changes: list[ObservationChangeRecord] = []
            for raw in raw_observations:
                observation_date = date.fromisoformat(raw["date"])
                new_value = _parse_value(raw["value"])
                existed_before = observation_date in persisted
                previous_value = persisted.get(observation_date)
                change_type = classify_observation_change(existed_before, previous_value, new_value)

                if change_type == "UNCHANGED":
                    unchanged_count += 1
                    continue
                if change_type == "NEW":
                    new_count += 1
                else:
                    revised_count += 1
                changes.append(
                    ObservationChangeRecord(
                        series_id=series_id,
                        observation_date=observation_date,
                        change_type=change_type,
                        previous_value=previous_value,
                        new_value=new_value,
                        detected_at=detected_at,
                    )
                )
        except (FREDError, KeyError, TypeError, ValueError) as exc:
            error = _safe_error_message(exc) if isinstance(exc, FREDError) else "FRED returned malformed observation data."
            return SeriesCheckOutcome(series_id=series_id, succeeded=False, error=error), []

        outcome = SeriesCheckOutcome(
            series_id=series_id,
            succeeded=True,
            new_count=new_count,
            revised_count=revised_count,
            unchanged_count=unchanged_count,
        )
        return outcome, changes

    # -----------------------------------------------------------------
    # Before/after analysis + canonical writes
    # -----------------------------------------------------------------

    def _apply_changes_and_compute_analysis(
        self, repo: ReleaseProcessingRepository, observation_changes: list[ObservationChangeRecord]
    ) -> list[AnalysisChangeRecord]:
        """Captures BEFORE evidence, writes every changed observation,
        captures AFTER evidence, and diffs the two using the existing
        comparison primitives -- exactly once per affected Inflation
        (component, period) pair and exactly once per affected Labor
        period, never once per individual observation row (see
        `app.domain.release_processing.affected_evaluation_periods`'s
        own docstring for why a batch of several changed dates that
        share one affected period must only be evaluated once; Labor's
        own identical property is
        `app.domain.labor_release_processing.labor_affected_evaluation_periods`'s).

        Increment #20D.2: Inflation and Labor are two independent,
        explicitly-dispatched branches (docs/architecture/labor-release-integration-v1.md
        §24) -- never a generic adapter framework, never `elif` between
        them (a series could in principle belong to both in the
        future, per that document's §26)."""
        if not observation_changes:
            return []

        affected_pairs = _affected_component_period_pairs(repo, observation_changes)
        labor_periods = _affected_labor_periods(observation_changes)
        if not affected_pairs and not labor_periods:
            # Every changed observation belongs to a series with no
            # deterministic Inflation OR Labor consumer -- write the
            # data, compute no analysis (there is none to compute).
            for record in observation_changes:
                economic_series = repo.get_series_by_series_id(record.series_id)
                repo.write_observation(economic_series.id, record.observation_date, record.new_value)
            return []

        before_observations = _load_canonical_observations(repo) if affected_pairs else {}
        before_evidence = {pair: _evaluate_component_at(before_observations, pair[0], pair[1]) for pair in affected_pairs}
        before_labor_observations = _load_canonical_labor_observations(repo) if labor_periods else {}
        before_labor_results = {period: _evaluate_labor_at(before_labor_observations, period) for period in labor_periods}

        for record in observation_changes:
            economic_series = repo.get_series_by_series_id(record.series_id)
            repo.write_observation(economic_series.id, record.observation_date, record.new_value)

        after_observations = _load_canonical_observations(repo) if affected_pairs else {}
        after_evidence = {pair: _evaluate_component_at(after_observations, pair[0], pair[1]) for pair in affected_pairs}
        after_labor_observations = _load_canonical_labor_observations(repo) if labor_periods else {}
        after_labor_results = {period: _evaluate_labor_at(after_labor_observations, period) for period in labor_periods}

        analysis_changes: list[AnalysisChangeRecord] = []
        for component, period in sorted(affected_pairs, key=lambda pair: (pair[0], pair[1])):
            analysis_changes.extend(
                _diff_component_at(component, period, before_evidence[(component, period)], after_evidence[(component, period)])
            )
        for period in sorted(labor_periods):
            analysis_changes.extend(_diff_labor_at(period, before_labor_results[period], after_labor_results[period]))
        return analysis_changes


def _determine_status(
    any_provider_failure: bool, any_provider_success: bool, observation_changes: list[ObservationChangeRecord]
) -> CheckRunStatus:
    if any_provider_failure and not any_provider_success:
        return "FAILED_PROVIDER"
    if any_provider_failure and any_provider_success:
        return "PARTIAL_FAILURE"
    return "CHANGED" if observation_changes else "NO_CHANGE"


def _affected_component_period_pairs(
    repo: ReleaseProcessingRepository, observation_changes: list[ObservationChangeRecord]
) -> set[tuple[ChangeComponent, date]]:
    """Every (component, period) pair release processing must evaluate
    before/after, across every changed series in this run -- the union
    naturally deduplicates a period two different series' changes both
    affect (see `_apply_changes_and_compute_analysis`).

    Called before any observation is written, so `repo.get_observations_by_date`
    still reflects pre-write state -- `observation_dates_after` (the set
    `affected_evaluation_periods` checks forward-projected candidates
    against) is the union of THAT persisted set with this run's own
    changed dates: a REVISED date was already in the persisted set; a
    NEW date is added by the union, exactly matching what will actually
    exist once the pending writes are applied."""
    changed_dates_by_series: dict[str, set[date]] = {}
    for record in observation_changes:
        changed_dates_by_series.setdefault(record.series_id, set()).add(record.observation_date)

    pairs: set[tuple[ChangeComponent, date]] = set()
    for series_id, changed_dates in changed_dates_by_series.items():
        components = components_for_series(series_id)
        if not components:
            continue
        economic_series = repo.get_series_by_series_id(series_id)
        persisted_dates = frozenset(repo.get_observations_by_date(economic_series.id).keys()) if economic_series else frozenset()
        dates_after = frozenset(changed_dates) | persisted_dates
        periods = affected_evaluation_periods(frozenset(changed_dates), dates_after)
        for component in components:
            for period in periods:
                pairs.add((component, period))
    return pairs


def _load_canonical_observations(repo: ReleaseProcessingRepository) -> dict[str, list[Observation]]:
    """The four canonical Inflation series' full persisted history,
    read-only -- mirrors `app.services.inflation.InflationMonitorService._load`
    exactly (empty list for a series never persisted, never an error),
    restated independently here (a three-line read, not economic logic)
    rather than importing that service, keeping release processing and
    Inflation Monitor orchestration as two independent callers of the
    same underlying repository-level reads."""
    result: dict[str, list[Observation]] = {}
    for series_id in _CANONICAL_SERIES_IDS:
        series = repo.get_series_by_series_id(series_id)
        if series is None:
            result[series_id] = []
            continue
        by_date = repo.get_observations_by_date(series.id)
        result[series_id] = [Observation(date=observation_date, value=value) for observation_date, value in sorted(by_date.items())]
    return result


def _evaluate_component_at(observations_by_series: dict[str, list[Observation]], component: ChangeComponent, period: date):
    """Dispatches to the EXISTING, unmodified `app.domain.inflation`
    exact-period primitives -- never a release-processing-owned
    reimplementation of any classification/annualization formula."""
    if component == "PRIMARY_MOMENTUM":
        return compute_series_momentum_at(observations_by_series[PRIMARY_SERIES_ID], PRIMARY_SERIES_ID, period)
    if component == "HEADLINE_PCE":
        return compute_series_momentum_at(observations_by_series[TARGET_SERIES_ID], TARGET_SERIES_ID, period)
    if component == "HEADLINE_CPI":
        return compute_series_momentum_at(observations_by_series[HEADLINE_CPI_SERIES_ID], HEADLINE_CPI_SERIES_ID, period)
    if component == "TARGET":
        return compute_target_at(observations_by_series[TARGET_SERIES_ID], period)
    if component == "CONFIRMATION":
        return compute_confirmation_at(observations_by_series[PRIMARY_SERIES_ID], observations_by_series[CONFIRMATION_SERIES_ID], period)
    raise AssertionError(f"unhandled ChangeComponent: {component}")  # pragma: no cover


def _diff_component_at(component: ChangeComponent, period: date, before_evidence, after_evidence) -> list[AnalysisChangeRecord]:
    """Dispatches to the EXISTING, unmodified
    `app.domain.inflation_what_changed` comparators -- `previous_period`
    and `current_period` are both `period` (see
    `app.db.models.ReleaseAnalysisUpdate`'s docstring for why that's
    the honest release-scoped equivalent of month-over-month, not a
    distortion of it)."""
    if component == "CONFIRMATION":
        before_primary, before_confirmation, before_relationship = before_evidence
        after_primary, after_confirmation, after_relationship = after_evidence
        section = compare_confirmation_section(
            period,
            period,
            before_primary,
            before_confirmation,
            before_relationship,
            after_primary,
            after_confirmation,
            after_relationship,
        )
    elif component == "TARGET":
        section = compare_target_section(period, period, before_evidence, after_evidence)
    else:
        section = compare_series_momentum_section(component, period, period, before_evidence, after_evidence)

    return [
        AnalysisChangeRecord(
            component=event.component,
            event_type=event.event_type,
            field=event.field,
            previous_value=event.previous_value,
            current_value=event.current_value,
            delta=event.delta,
            evaluation_period=period,
            methodology_id=event.methodology_id,
            data_basis=event.data_basis,
        )
        for event in section.changes
    ]


# -----------------------------------------------------------------
# Labor branch (Increment #20D.2) -- an explicit, independent sibling
# of the Inflation helpers above, never a modification of them. See
# docs/architecture/labor-release-integration-v1.md §24.
# -----------------------------------------------------------------


def _affected_labor_periods(observation_changes: list[ObservationChangeRecord]) -> frozenset[date]:
    """Every `labor_v1.0` evaluation period release processing must
    evaluate before/after, across PAYEMS and UNRATE changes in this
    run -- the union (via `app.domain.labor_release_processing.labor_affected_evaluation_periods`)
    naturally deduplicates a period both series' changes affect.

    Deliberately does NOT filter candidates against a "does an
    observation already exist there" set the way
    `_affected_component_period_pairs` does -- Labor's own propagation
    functions return every candidate offset unconditionally (see
    `app.domain.labor_release_processing`'s own docstring: `labor_v1.0`
    already reports `INSUFFICIENT_DATA` for a period with no
    computable evidence, so no pre-filter is needed here)."""
    payems_changed = {r.observation_date for r in observation_changes if r.series_id == PAYEMS_SERIES_ID}
    unrate_changed = {r.observation_date for r in observation_changes if r.series_id == UNRATE_SERIES_ID}
    if not payems_changed and not unrate_changed:
        return frozenset()
    return labor_affected_evaluation_periods(frozenset(payems_changed), frozenset(unrate_changed))


def _load_canonical_labor_observations(repo: ReleaseProcessingRepository) -> dict[str, list[Observation]]:
    """PAYEMS/UNRATE's full persisted history, read-only -- the Labor
    analog of `_load_canonical_observations`, independently
    implemented (not a generalization of it) since Labor has its own,
    smaller canonical series set."""
    result: dict[str, list[Observation]] = {}
    for series_id in (PAYEMS_SERIES_ID, UNRATE_SERIES_ID):
        series = repo.get_series_by_series_id(series_id)
        if series is None:
            result[series_id] = []
            continue
        by_date = repo.get_observations_by_date(series.id)
        result[series_id] = [Observation(date=observation_date, value=value) for observation_date, value in sorted(by_date.items())]
    return result


def _evaluate_labor_at(observations_by_series: dict[str, list[Observation]], period: date) -> LaborMonitorResult:
    """Dispatches to the EXISTING, unmodified
    `app.domain.labor.compute_labor_monitor_result_at` -- never a
    release-processing-owned reimplementation of any PAYEMS/UNRATE
    formula. Unlike Inflation's per-component `_evaluate_component_at`,
    this ONE call already produces `LABOR`+`EMPLOYMENT`+`UNEMPLOYMENT`
    together (see `app.domain.labor_release_processing`'s own
    docstring for why Labor has no per-component evaluation split)."""
    payems_observations = observations_by_series.get(PAYEMS_SERIES_ID, [])
    unrate_observations = observations_by_series.get(UNRATE_SERIES_ID, [])
    return compute_labor_monitor_result_at(
        payems_observations,
        unrate_observations,
        period,
        CONDITION_DEADBAND_JOBS,
        MOMENTUM_DEADBAND_JOBS,
        UNEMPLOYMENT_DEADBAND_PP,
    )


def _diff_labor_at(period: date, before_result: LaborMonitorResult, after_result: LaborMonitorResult) -> list[AnalysisChangeRecord]:
    """Dispatches to the EXISTING, unmodified
    `app.domain.labor_what_changed` comparators -- `previous_period`
    and `current_period` are both `period` (the same same-period
    release-scoped convention `_diff_component_at` already uses for
    Inflation; never `month_over_month_labor_periods`/
    `LaborMonitorService.get_what_changed_result`, which answer a
    different question -- see
    docs/architecture/labor-release-integration-v1.md §14).

    Component order (`LABOR`, then `EMPLOYMENT`, then `UNEMPLOYMENT`)
    matches `app.models.labor_what_changed.COMPONENT_ORDER` exactly --
    each comparator call's own `.changes` list is already internally
    ordered by `EVENT_TYPE_ORDER`/`FIELD_ORDER`, so this concatenation
    needs no additional sort."""
    labor_state_changes = compare_labor_state(period, period, before_result.state, after_result.state)
    employment_changes = compare_employment_section(period, period, before_result.employment, after_result.employment)
    unemployment_changes = compare_unemployment_section(period, period, before_result.unemployment, after_result.unemployment)

    return [
        AnalysisChangeRecord(
            component=event.component,
            event_type=event.event_type,
            field=event.field,
            previous_value=event.previous_value,
            current_value=event.current_value,
            delta=event.delta,
            evaluation_period=period,
            methodology_id=event.methodology_id,
            data_basis=event.data_basis,
        )
        for event in [*labor_state_changes, *employment_changes.changes, *unemployment_changes.changes]
    ]


# -----------------------------------------------------------------
# Occurrence-level locking (Increment #25C, frozen contract
# docs/product/automated-economic-maintenance-v1.md §18/§19/§59) --
# the ONE shared entry point both the manual CLI
# (app.operations.process_release) and the automated orchestrator
# (app.services.maintenance.MaintenanceOrchestrator) call, so the two
# paths can never diverge in locking behavior ("Do not maintain one
# safe automatic path and one unsafe manual bypass").
# -----------------------------------------------------------------

# A fixed, documented namespace for the first key of PostgreSQL's
# two-integer advisory-lock keyspace, chosen once and never reused for
# any other lock purpose in this project -- a future, unrelated
# advisory lock (if one is ever added) cannot collide with this one by
# accident. The second key is always the occurrence's own internal id.
_OCCURRENCE_LOCK_NAMESPACE = 725_100


def try_acquire_and_process_occurrence(
    service: ReleaseProcessingService, occurrence_id: int, session: Session, as_of_date: date
) -> ReleaseCheckRunResult | None:
    """Acquire a TRANSACTION-scoped PostgreSQL advisory lock
    (`pg_try_advisory_xact_lock`, keyed by `occurrence_id`) before
    calling the existing, unmodified `service.process_occurrence` --
    never a modification of that method, never a duplication of its
    own economic logic.

    Returns `None`, without calling `process_occurrence` at all, if
    the lock is already held by another session (an automated sweep
    and a manual CLI invocation racing the same occurrence, or two
    overlapping automated sweeps) -- a genuine, expected outcome under
    concurrent execution, never an error (frozen contract's own source
    prompt §20: skip, never block indefinitely; the caller records
    this as "skipped due to lock contention," distinct from either a
    successful process or a failure).

    The lock is transaction-scoped: PostgreSQL releases it
    automatically when `session`'s own transaction commits OR rolls
    back -- including on an unhandled crash, since a dropped
    connection's own advisory locks are released by PostgreSQL itself.
    No explicit release call is needed or provided, and none can leak
    (frozen contract §19's own "zero schema change... session-scoped
    Postgres primitives, not table rows" reasoning, using the stricter,
    automatically-safe transaction-scoped variant rather than the
    session-scoped one, since `process_occurrence`'s own unit of work
    is already exactly one transaction, §20/§21).
    """
    acquired = session.execute(select(func.pg_try_advisory_xact_lock(_OCCURRENCE_LOCK_NAMESPACE, occurrence_id))).scalar_one()
    if not acquired:
        return None
    return service.process_occurrence(occurrence_id, session, as_of_date)
