"""Application/use-case orchestration for the Labor Market Monitor
(`labor_v1.0`) and its "What Changed?" comparison layer
(`labor_what_changed_v1.0`).

Reads PAYEMS/UNRATE's persisted observations via the existing, generic
`SeriesRepository` -- no Labor-specific repository was needed, the
same "reuse existing generic persistence, don't invent a parallel one"
discipline `app.services.inflation.InflationMonitorService` already
follows for the same reason -- and delegates every actual calculation
to `app.domain.labor`'s pure functions, and every comparison to
`app.domain.labor_what_changed`'s pure functions (which never sees a
raw observation). This service contains no methodology math and no
comparison logic of its own. Database-only, read-only: never calls
FRED, never syncs, never triggers ingestion, never mutates
`EconomicSeries`/`EconomicObservation`.

A canonical series (PAYEMS or UNRATE) that is not persisted at all is
treated exactly like one that is persisted but has zero observations
-- both resolve to `LaborMonitorResult`'s own `INSUFFICIENT_DATA`
outcome, never an exception (mirroring
`InflationMonitorService._load`'s identical precedent). A genuine
database error still propagates as a real exception for
`app.api.labor` to map to a 503/500, exactly like every other
database-backed route in this project.
"""

from sqlalchemy.orm import Session

from app.domain.labor import (
    compute_labor_monitor_result,
    compute_labor_monitor_result_at,
    month_before,
    month_over_month_labor_periods,
)
from app.domain.labor_what_changed import (
    assemble_labor_what_changed_result,
    compare_employment_section,
    compare_labor_state,
    compare_unemployment_section,
)
from app.domain.state_duration import StateDurationPoint, evaluate_state_duration
from app.models.labor import (
    CONDITION_DEADBAND_JOBS,
    DATA_BASIS,
    EMPLOYMENT_CONCEPT_ID,
    LaborMonitorResult,
    LaborSeriesIdentities,
    METHODOLOGY_ID,
    MOMENTUM_DEADBAND_JOBS,
    PAYEMS_SERIES_ID,
    UNEMPLOYMENT_CONCEPT_ID,
    UNEMPLOYMENT_DEADBAND_PP,
    UNRATE_SERIES_ID,
)
from app.models.labor_what_changed import LaborWhatChangedResult
from app.models.series import Observation
from app.models.state_duration import HISTORY_TYPE, StateDurationAvailable, StateDurationCurrentInsufficient, StateDurationResult
from app.repositories.series_repository import SeriesRepository
from app.services.series_identity import resolve_identity

# Frozen (`docs/product/state-duration-v1.md` §11): the identical 60
# calendar months as `InflationMonitorService`'s own constant, defined
# independently here (not imported from a shared location) -- same
# "no shared calendar/policy utility" discipline as `month_before`'s
# own per-domain duplication (§7/§11).
_STATE_DURATION_LOOKBACK_BOUND_MONTHS = 60


class LaborMonitorService:
    def get_result(self, session: Session) -> LaborMonitorResult:
        """The complete canonical `labor_v1.0` result, computed
        entirely from whatever is currently persisted for PAYEMS and
        UNRATE. Deterministic for a given database state: two calls in
        immediate succession, with no intervening write, return
        identical results."""
        repo = SeriesRepository(session)
        payems_observations = self._load(repo, PAYEMS_SERIES_ID)
        unrate_observations = self._load(repo, UNRATE_SERIES_ID)
        identities = self._identities(repo)

        return compute_labor_monitor_result(
            payems_observations=payems_observations,
            unrate_observations=unrate_observations,
            condition_deadband_jobs=CONDITION_DEADBAND_JOBS,
            momentum_deadband_jobs=MOMENTUM_DEADBAND_JOBS,
            unemployment_deadband_pp=UNEMPLOYMENT_DEADBAND_PP,
            identities=identities,
        )

    def get_what_changed_result(self, session: Session) -> LaborWhatChangedResult:
        """The complete canonical `labor_what_changed_v1.0` result: a
        month-over-month comparison of PAYEMS/UNRATE's shared
        `evaluation_period` against exactly the calendar month before
        it. Every economic evaluation is delegated to
        `app.domain.labor`'s existing primitives at explicit periods
        this method selects (`month_over_month_labor_periods`,
        `compute_labor_monitor_result_at`); every comparison is
        delegated to `app.domain.labor_what_changed`, which never sees
        a raw observation. Deterministic for a given database state,
        same guarantee as `get_result`.

        When no evaluation period exists at all (neither PAYEMS nor
        UNRATE has any persisted observation), `previous_period` and
        `current_period` are both `None` and there is exactly ONE
        `compute_labor_monitor_result` call, its single
        `INSUFFICIENT_DATA`-shaped result reused for BOTH sides of the
        comparison -- there is no second, different period to compute
        a distinct "previous" from (frozen contract §13 step 3). When
        an evaluation period does exist, BOTH sides are always computed
        via `compute_labor_monitor_result_at`, never a mix of the plain
        and `_at` variants (frozen contract §13's own emphasis) --
        one code path, no risk of subtle divergence.
        """
        repo = SeriesRepository(session)
        payems_observations = self._load(repo, PAYEMS_SERIES_ID)
        unrate_observations = self._load(repo, UNRATE_SERIES_ID)
        identities = self._identities(repo)

        previous_period, current_period = month_over_month_labor_periods(payems_observations, unrate_observations)

        if current_period is None:
            degenerate_result = compute_labor_monitor_result(
                payems_observations=payems_observations,
                unrate_observations=unrate_observations,
                identities=identities,
                condition_deadband_jobs=CONDITION_DEADBAND_JOBS,
                momentum_deadband_jobs=MOMENTUM_DEADBAND_JOBS,
                unemployment_deadband_pp=UNEMPLOYMENT_DEADBAND_PP,
            )
            previous_result = degenerate_result
            current_result = degenerate_result
        else:
            previous_result = compute_labor_monitor_result_at(
                payems_observations, unrate_observations, previous_period,
                CONDITION_DEADBAND_JOBS, MOMENTUM_DEADBAND_JOBS, UNEMPLOYMENT_DEADBAND_PP,
                identities=identities,
            )
            current_result = compute_labor_monitor_result_at(
                payems_observations, unrate_observations, current_period,
                CONDITION_DEADBAND_JOBS, MOMENTUM_DEADBAND_JOBS, UNEMPLOYMENT_DEADBAND_PP,
                identities=identities,
            )

        employment_changes = compare_employment_section(
            previous_period, current_period, previous_result.employment, current_result.employment
        )
        unemployment_changes = compare_unemployment_section(
            previous_period, current_period, previous_result.unemployment, current_result.unemployment
        )
        labor_state_changes = compare_labor_state(
            previous_period, current_period, previous_result.state, current_result.state
        )

        return assemble_labor_what_changed_result(
            previous_period=previous_period,
            current_period=current_period,
            previous_labor_state=previous_result.state,
            current_labor_state=current_result.state,
            labor_state_changes=labor_state_changes,
            employment_changes=employment_changes,
            unemployment_changes=unemployment_changes,
            current_labor_result=current_result,
        )

    def get_state_duration_result(self, session: Session) -> StateDurationResult:
        """The complete canonical State Duration V1 result
        (`docs/product/state-duration-v1.md`) for Labor's own top-level
        canonical state -- `LaborMonitorResult.state` (`LaborState`),
        the current anchor period being `LaborMonitorResult.evaluation_period`
        (frozen contract §4/§5). Latest-revised reconstruction only
        (§1): every reconstructed point below is produced by
        `compute_labor_monitor_result_at`, unmodified, never a new
        formula or a second methodology. Reads only PAYEMS's and
        UNRATE's own observations, already-loaded once (§30, below).
        """
        repo = SeriesRepository(session)
        payems_observations = self._load(repo, PAYEMS_SERIES_ID)
        unrate_observations = self._load(repo, UNRATE_SERIES_ID)
        identities = self._identities(repo)

        current = compute_labor_monitor_result(
            payems_observations=payems_observations,
            unrate_observations=unrate_observations,
            identities=identities,
            condition_deadband_jobs=CONDITION_DEADBAND_JOBS,
            momentum_deadband_jobs=MOMENTUM_DEADBAND_JOBS,
            unemployment_deadband_pp=UNEMPLOYMENT_DEADBAND_PP,
        )
        if current.state == "INSUFFICIENT_DATA" or current.evaluation_period is None:
            # Unified per §14: a null current period always co-occurs
            # with INSUFFICIENT_DATA in this domain's existing code; no
            # duration is computed or implied in this case.
            return StateDurationCurrentInsufficient(methodology_id=METHODOLOGY_ID, data_basis=DATA_BASIS)

        anchor_period = current.evaluation_period

        # Load-once strategy (§30): `payems_observations`/
        # `unrate_observations` were already fetched by the two `_load`
        # calls above (one call per required series); every point below
        # is a pure, in-memory `_at` call over those same lists -- zero
        # additional database round-trips.
        sequence: list[StateDurationPoint] = []
        for months_back in range(_STATE_DURATION_LOOKBACK_BOUND_MONTHS):
            period = month_before(anchor_period, months_back)
            result_at = compute_labor_monitor_result_at(
                payems_observations,
                unrate_observations,
                period,
                CONDITION_DEADBAND_JOBS,
                MOMENTUM_DEADBAND_JOBS,
                UNEMPLOYMENT_DEADBAND_PP,
                identities=identities,
            )
            sequence.append(StateDurationPoint(period=period, state=result_at.state))

        evaluation = evaluate_state_duration(sequence, _STATE_DURATION_LOOKBACK_BOUND_MONTHS)

        return StateDurationAvailable(
            state=current.state,
            evaluation_period=anchor_period,
            duration_months=evaluation.duration_months,
            earliest_confirmed_period=evaluation.earliest_confirmed_period,
            boundary_type=evaluation.boundary_type,
            previous_state=evaluation.previous_state,
            previous_period=evaluation.previous_period,
            methodology_id=METHODOLOGY_ID,
            data_basis=DATA_BASIS,
            history_type=HISTORY_TYPE,
        )

    @staticmethod
    def _identities(repo: SeriesRepository) -> LaborSeriesIdentities:
        """Who `labor_v1.0`'s two inputs actually are, read from the
        persisted rows (#38) rather than from module constants -- so the
        evidence this monitor stamps names the provider that genuinely
        supplied each observation."""
        return LaborSeriesIdentities(
            employment=resolve_identity(repo, EMPLOYMENT_CONCEPT_ID),
            unemployment=resolve_identity(repo, UNEMPLOYMENT_CONCEPT_ID),
        )

    @staticmethod
    def _load(repo: SeriesRepository, series_id: str) -> list[Observation]:
        """A canonical series that is not persisted at all yields an
        empty observation list -- deliberately NOT a
        `SeriesNotFoundError` -- so a missing series behaves exactly
        like a persisted series with no usable observations, per the
        frozen specification's missing-data semantics (identical
        precedent: `InflationMonitorService._load`)."""
        series = repo.get_series_by_series_id(series_id)
        if series is None:
            return []
        raw = repo.get_observations_in_range(series.id, start_date=None, end_date=None)
        return [Observation(date=obs.observation_date, value=obs.value) for obs in raw]
