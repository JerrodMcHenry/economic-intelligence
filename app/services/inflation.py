"""Application/use-case orchestration for the Inflation Monitor
(`inflation_v1.0`) and its "What Changed?" comparison layer
(`inflation_what_changed_v1.0`).

Reads the four canonical series' persisted observations via
`SeriesRepository` and delegates every actual calculation to
`app.domain.inflation`'s pure functions -- this service contains no
methodology math and no comparison logic of its own (comparison is
`app.domain.inflation_what_changed`'s job, with zero knowledge of how
the evidence it compares was computed). Database-only, read-only: never
calls FRED, never syncs, never triggers ingestion, never mutates
`EconomicSeries`/`EconomicObservation`.

A canonical series that is not persisted at all is treated exactly like
one that is persisted but has zero or insufficient observations -- both
resolve to that component's own `INSUFFICIENT_DATA`/`available: false`
state, never an exception. Missing economic data and infrastructure
failure are different outcomes (see
`docs/methodology/inflation-monitor-v1.0.md`'s "Infrastructure failure
vs. economic insufficiency"): a genuine database error still propagates
as a real exception for `app.api.inflation` to map to a 503/500,
exactly like every other database-backed route in this project.
"""

from sqlalchemy.orm import Session

from app.domain.inflation import (
    compute_inflation_monitor_result,
    compute_series_momentum,
    compute_series_momentum_at,
    month_before,
    month_over_month_confirmation,
    month_over_month_series_momentum,
    month_over_month_target,
)
from app.domain.inflation_what_changed import (
    assemble_what_changed_result,
    compare_confirmation_section,
    compare_series_momentum_section,
    compare_target_section,
)
from app.domain.state_duration import StateDurationPoint, evaluate_state_duration
from app.models.inflation import (
    CONFIRMATION_SERIES_ID,
    DATA_BASIS,
    HEADLINE_CPI_SERIES_ID,
    InflationMonitorResult,
    METHODOLOGY_ID,
    PRIMARY_SERIES_ID,
    TARGET_SERIES_ID,
)
from app.models.inflation_what_changed import InflationWhatChangedResult
from app.models.series import Observation
from app.models.state_duration import HISTORY_TYPE, StateDurationAvailable, StateDurationCurrentInsufficient, StateDurationResult
from app.repositories.series_repository import SeriesRepository

# Frozen (`docs/product/state-duration-v1.md` §11): 60 calendar months,
# the same order-of-magnitude tradeoff already defended and shipped by
# `app.domain.release_processing.five_year_observation_start`. Defined
# independently here (not imported from a shared location) -- the same
# "no shared calendar/policy utility, each domain computes its own"
# discipline `month_before`'s own per-domain duplication already
# established (§7/§11).
_STATE_DURATION_LOOKBACK_BOUND_MONTHS = 60


class InflationMonitorService:
    def get_result(self, session: Session) -> InflationMonitorResult:
        """The complete canonical `inflation_v1.0` result, computed
        entirely from whatever is currently persisted for the four
        canonical series. Deterministic for a given database state:
        two calls in immediate succession, with no intervening write,
        return identical results."""
        repo = SeriesRepository(session)
        primary_observations = self._load(repo, PRIMARY_SERIES_ID)
        confirmation_observations = self._load(repo, CONFIRMATION_SERIES_ID)
        target_observations = self._load(repo, TARGET_SERIES_ID)
        headline_cpi_observations = self._load(repo, HEADLINE_CPI_SERIES_ID)

        return compute_inflation_monitor_result(
            primary_observations=primary_observations,
            confirmation_observations=confirmation_observations,
            target_observations=target_observations,
            headline_cpi_observations=headline_cpi_observations,
        )

    def get_what_changed_result(self, session: Session) -> InflationWhatChangedResult:
        """The complete canonical `inflation_what_changed_v1.0` result:
        a month-over-month comparison, section by section, each
        independently anchored per the frozen contract (ordinary
        series at their own `latest_observation_period`; confirmation
        at `latest_shared_observation_period`, never
        `inflation_v1.0`'s own `latest_common_period`). Every economic
        evaluation is delegated to `app.domain.inflation`'s existing
        primitives at explicit periods this method selects; every
        comparison is delegated to `app.domain.inflation_what_changed`,
        which never sees a raw observation. Deterministic for a given
        database state, same guarantee as `get_result`."""
        repo = SeriesRepository(session)
        primary_observations = self._load(repo, PRIMARY_SERIES_ID)
        confirmation_observations = self._load(repo, CONFIRMATION_SERIES_ID)
        target_observations = self._load(repo, TARGET_SERIES_ID)
        headline_cpi_observations = self._load(repo, HEADLINE_CPI_SERIES_ID)

        primary_previous_period, primary_current_period, primary_previous_evidence, primary_current_evidence = (
            month_over_month_series_momentum(primary_observations, PRIMARY_SERIES_ID)
        )
        primary_momentum_changes = compare_series_momentum_section(
            "PRIMARY_MOMENTUM", primary_previous_period, primary_current_period, primary_previous_evidence, primary_current_evidence
        )

        target_previous_period, target_current_period, target_previous_evidence, target_current_evidence = (
            month_over_month_target(target_observations)
        )
        target_changes = compare_target_section(
            target_previous_period, target_current_period, target_previous_evidence, target_current_evidence
        )

        # Headline PCE is the same series (PCEPI) as target, evaluated
        # independently for its own momentum context -- its period pair
        # will in practice coincide with target's (same raw data), an
        # emergent consequence of sharing a series, not a forced rule.
        headline_pce_previous_period, headline_pce_current_period, headline_pce_previous_evidence, headline_pce_current_evidence = (
            month_over_month_series_momentum(target_observations, TARGET_SERIES_ID)
        )
        headline_pce_changes = compare_series_momentum_section(
            "HEADLINE_PCE",
            headline_pce_previous_period,
            headline_pce_current_period,
            headline_pce_previous_evidence,
            headline_pce_current_evidence,
        )

        headline_cpi_previous_period, headline_cpi_current_period, headline_cpi_previous_evidence, headline_cpi_current_evidence = (
            month_over_month_series_momentum(headline_cpi_observations, HEADLINE_CPI_SERIES_ID)
        )
        headline_cpi_changes = compare_series_momentum_section(
            "HEADLINE_CPI",
            headline_cpi_previous_period,
            headline_cpi_current_period,
            headline_cpi_previous_evidence,
            headline_cpi_current_evidence,
        )

        (
            confirmation_previous_period,
            confirmation_current_period,
            confirmation_previous_primary_state,
            confirmation_previous_confirmation_state,
            confirmation_previous_relationship,
            confirmation_current_primary_state,
            confirmation_current_confirmation_state,
            confirmation_current_relationship,
        ) = month_over_month_confirmation(primary_observations, confirmation_observations)
        confirmation_changes = compare_confirmation_section(
            confirmation_previous_period,
            confirmation_current_period,
            confirmation_previous_primary_state,
            confirmation_previous_confirmation_state,
            confirmation_previous_relationship,
            confirmation_current_primary_state,
            confirmation_current_confirmation_state,
            confirmation_current_relationship,
        )

        current_monitor_result = compute_inflation_monitor_result(
            primary_observations=primary_observations,
            confirmation_observations=confirmation_observations,
            target_observations=target_observations,
            headline_cpi_observations=headline_cpi_observations,
        )

        return assemble_what_changed_result(
            primary_momentum_changes=primary_momentum_changes,
            confirmation_changes=confirmation_changes,
            target_changes=target_changes,
            headline_pce_changes=headline_pce_changes,
            headline_cpi_changes=headline_cpi_changes,
            current_monitor_result=current_monitor_result,
        )

    def get_state_duration_result(self, session: Session) -> StateDurationResult:
        """The complete canonical State Duration V1 result
        (`docs/product/state-duration-v1.md`) for Inflation's own
        top-level canonical state -- `underlying_momentum.state`
        (`InflationState`), the current anchor period being
        `underlying_momentum.calculation_period` (frozen contract §4/§5).
        Latest-revised reconstruction only (§1): every reconstructed
        point below is produced by `compute_series_momentum_at`,
        unmodified, never a new formula or a second methodology. Reads
        only Core PCE's (`PCEPILFE`) own observations -- Confirmation's,
        Target's, and Headline's own availability never affect this
        result (§24), and this method never touches those series.
        """
        repo = SeriesRepository(session)
        primary_observations = self._load(repo, PRIMARY_SERIES_ID)

        current = compute_series_momentum(primary_observations, PRIMARY_SERIES_ID)
        if current.state == "INSUFFICIENT_DATA" or current.calculation_period is None:
            # Unified per §14: a null current period always co-occurs
            # with INSUFFICIENT_DATA in this domain's existing code; no
            # duration is computed or implied in this case.
            return StateDurationCurrentInsufficient(methodology_id=METHODOLOGY_ID, data_basis=DATA_BASIS)

        anchor_period = current.calculation_period

        # Load-once strategy (§30): `primary_observations` was already
        # fetched by the single `_load` call above; every point below
        # is a pure, in-memory `_at` call over that same list -- zero
        # additional database round-trips.
        sequence: list[StateDurationPoint] = []
        for months_back in range(_STATE_DURATION_LOOKBACK_BOUND_MONTHS):
            period = month_before(anchor_period, months_back)
            result_at = compute_series_momentum_at(primary_observations, PRIMARY_SERIES_ID, period)
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
    def _load(repo: SeriesRepository, series_id: str) -> list[Observation]:
        """A canonical series that is not persisted at all yields an
        empty observation list -- deliberately NOT a
        `SeriesNotFoundError` -- so a missing series behaves exactly
        like a persisted series with no usable observations, per the
        frozen specification's missing-data semantics (a component's
        own unavailability is reported inside a normal 200 response,
        never as an HTTP error)."""
        series = repo.get_series_by_series_id(series_id)
        if series is None:
            return []
        raw = repo.get_observations_in_range(series.id, start_date=None, end_date=None)
        return [Observation(date=obs.observation_date, value=obs.value) for obs in raw]
