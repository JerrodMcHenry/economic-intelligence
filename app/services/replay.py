"""Deterministic point-in-time replay (Increment #31).

Answers the question that separates a stored output from a reproducible
one:

    data known THEN + methodology used THEN + deterministic code
        = the result recorded THEN?

`RecordedMonitorResult` has proven since #25E *what* MacroChipz
concluded. It could never prove *why*, because the observations behind
it were overwritten in place. Now that every write path records a
system-time version (`app.repositories.observation_versions`), the
inputs can be reconstructed exactly as they stood at the recorded
result's own `calculated_at`, and the conclusion re-derived.

Three properties this module is careful about:

1. **It re-executes; it does not read back.** The recorded state is
   loaded only to compare against. If this module merely returned the
   stored row it would be a lookup wearing the word "replay".

2. **It cannot silently consume later revisions.** Inputs come from
   `ObservationVersionRepository.get_observations_as_of`, which never
   falls back to current values. A revision recorded after the anchor is
   invisible by construction, not by discipline.

3. **It refuses rather than guesses.** Insufficient version history, or
   a methodology version this code no longer implements, yields an
   explicit `NOT_REPLAYABLE` outcome with a reason -- never a
   recomputation over whatever data happened to be available, which
   would produce a confident, meaningless answer.

The deterministic functions called here are the same
`app.domain.inflation`/`app.domain.labor` exact-period primitives that
release processing itself used to produce the recorded row. They are
imported directly from the domain rather than through release
processing's own private wrappers, so replay depends on the methodology,
not on another service's internals.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import RecordedMonitorResult
from app.domain.inflation import compute_series_momentum_at
from app.domain.labor import compute_labor_monitor_result_at
from app.models.inflation import (
    CONFIRMATION_CONCEPT_ID,
    HEADLINE_CPI_CONCEPT_ID,
    InflationSeriesIdentities,
    METHODOLOGY_ID as INFLATION_METHODOLOGY_ID,
    PRIMARY_CONCEPT_ID,
    PRIMARY_SERIES_ID,
    SeriesMomentumResult,
    TARGET_CONCEPT_ID,
)
from app.models.labor import (
    EMPLOYMENT_CONCEPT_ID,
    LaborSeriesIdentities,
    UNEMPLOYMENT_CONCEPT_ID,
    CONDITION_DEADBAND_JOBS,
    LaborMonitorResult,
    METHODOLOGY_ID as LABOR_METHODOLOGY_ID,
    MOMENTUM_DEADBAND_JOBS,
    PAYEMS_SERIES_ID,
    UNEMPLOYMENT_DEADBAND_PP,
    UNRATE_SERIES_ID,
)
from app.models.replay import ReplayResult
from app.models.series import Observation
from app.repositories.series_repository import SeriesRepository
from app.services.series_identity import resolve_identity
from app.repositories.observation_versions import AsOfObservation, ObservationVersionRepository

#: Which canonical series each recorded monitor's own state depends on.
#: Inflation's recorded state is Core PCE's momentum state (see
#: `_build_inflation_recordable_result`); Labor's combines PAYEMS and
#: UNRATE.
_MONITOR_INPUT_SERIES: dict[str, tuple[str, ...]] = {
    "inflation": (PRIMARY_SERIES_ID,),
    "labor": (PAYEMS_SERIES_ID, UNRATE_SERIES_ID),
}

#: What `_recompute` hands back: the monitor's own canonical result
#: type. Both already carry their exact inputs as evidence.
RecomputedResult = SeriesMomentumResult | LaborMonitorResult

_MONITOR_METHODOLOGY: dict[str, str] = {
    "inflation": INFLATION_METHODOLOGY_ID,
    "labor": LABOR_METHODOLOGY_ID,
}


def _as_observations(rows: list[AsOfObservation]) -> list[Observation]:
    """Translate as-of rows into the shape the domain already consumes.
    No filtering, no substitution: a null value stays null, exactly as
    the methodology's own missing-data rules expect."""
    return [Observation(date=row.observation_date, value=row.value) for row in rows]


class ReplayService:
    """Read-only. Never writes, and in particular never updates the
    recorded result it is checking -- `recorded_monitor_results` stays
    append-only and immutable (ADR-025), so a replay can disagree with
    history but can never quietly rewrite it."""

    def replay_recorded_result(self, session: Session, recorded_monitor_result_id: int) -> ReplayResult:
        recorded = session.get(RecordedMonitorResult, recorded_monitor_result_id)
        if recorded is None:
            return ReplayResult(
                recorded_monitor_result_id=recorded_monitor_result_id,
                monitor="unknown",
                evaluation_period=None,
                methodology_id="unknown",
                anchor=None,
                recorded_state=None,
                replayed_state=None,
                outcome="NOT_REPLAYABLE",
                reason="UNKNOWN_RECORDED_RESULT",
            )

        anchor = recorded.calculated_at
        series_ids = _MONITOR_INPUT_SERIES.get(recorded.monitor, ())
        base = {
            "recorded_monitor_result_id": recorded.id,
            "monitor": recorded.monitor,
            "evaluation_period": recorded.evaluation_period,
            "methodology_id": recorded.methodology_id,
            "anchor": anchor,
            "recorded_state": recorded.state,
            "input_series_ids": list(series_ids),
        }

        # A recorded row may name a methodology this code no longer
        # implements. Only one version of each exists today, so any
        # mismatch means the row predates or postdates this binary --
        # either way, re-running today's code would be answering a
        # different question.
        expected_methodology = _MONITOR_METHODOLOGY.get(recorded.monitor)
        if expected_methodology is None or recorded.methodology_id != expected_methodology:
            return ReplayResult(**base, replayed_state=None, outcome="NOT_REPLAYABLE", reason="UNKNOWN_METHODOLOGY_VERSION")

        versions = ObservationVersionRepository(session)

        coverage = self._coverage(versions, series_ids, anchor)
        if coverage is not None:
            return ReplayResult(**base, replayed_state=None, outcome="NOT_REPLAYABLE", reason=coverage)

        as_of: dict[str, list[AsOfObservation]] = {
            series_id: versions.get_observations_as_of(series_id, anchor) for series_id in series_ids
        }
        observation_count = sum(len(rows) for rows in as_of.values())
        includes_backfilled = any(row.is_backfilled for rows in as_of.values() for row in rows)

        replayed_state = self._recompute(recorded, as_of, *self._identities(session)).state

        return ReplayResult(
            **base,
            replayed_state=replayed_state,
            outcome="MATCH" if replayed_state == recorded.state else "MISMATCH",
            input_observation_count=observation_count,
            inputs_include_backfilled=includes_backfilled,
        )

    @staticmethod
    def _coverage(versions: ObservationVersionRepository, series_ids: tuple[str, ...], anchor: datetime) -> str | None:
        """Whether version history can honestly answer for this anchor.

        Returning an empty as-of set to the methodology would produce a
        confident `INSUFFICIENT_DATA` that looks like an economic
        finding but is really a storage gap -- so coverage is checked
        explicitly, before any calculation runs.
        """
        earliest_values = [versions.earliest_recorded_from(series_id) for series_id in series_ids]
        if not series_ids or all(value is None for value in earliest_values):
            return "NO_VERSION_HISTORY_FOR_INPUTS"
        if any(value is None or value > anchor for value in earliest_values):
            return "VERSION_HISTORY_STARTS_AFTER_CALCULATION"
        return None

    @staticmethod
    def _identities(session: Session) -> tuple[InflationSeriesIdentities, LaborSeriesIdentities]:
        """Identity for a REPLAY is read from the persisted series rows
        (#38), never from the active binding. That distinction is the
        whole of ADR-034's Invariant D: after a future provider cutover,
        replaying a historical conclusion must still name the provider
        that actually produced those observations, not whichever
        provider is current."""
        repo = SeriesRepository(session)
        return (
            InflationSeriesIdentities(
                primary=resolve_identity(repo, PRIMARY_CONCEPT_ID),
                confirmation=resolve_identity(repo, CONFIRMATION_CONCEPT_ID),
                target=resolve_identity(repo, TARGET_CONCEPT_ID),
                headline_cpi=resolve_identity(repo, HEADLINE_CPI_CONCEPT_ID),
            ),
            LaborSeriesIdentities(
                employment=resolve_identity(repo, EMPLOYMENT_CONCEPT_ID),
                unemployment=resolve_identity(repo, UNEMPLOYMENT_CONCEPT_ID),
            ),
        )

    @staticmethod
    def _recompute(
        recorded: RecordedMonitorResult,
        as_of: dict[str, list[AsOfObservation]],
        inflation_identities: InflationSeriesIdentities,
        labor_identities: LaborSeriesIdentities,
    ) -> RecomputedResult:
        """Re-run the SAME deterministic primitive that produced the
        recorded row, returning the WHOLE result rather than only its
        state. No new economic logic lives here.

        The full object is returned because the methodology's own
        evidence fields already name the exact observations it consumed
        (`InflationMetricEvidence.endpoint_date_*`,
        `LaborObservationEvidence.observation_date`). Any caller needing
        "which inputs produced this?" reads them off the result instead
        of re-deriving a window, which would be a second, drift-prone
        definition of the methodology's own input set.
        """
        period = recorded.evaluation_period

        if recorded.monitor == "inflation":
            return compute_series_momentum_at(
                _as_observations(as_of[PRIMARY_SERIES_ID]), inflation_identities.primary, period
            )

        return compute_labor_monitor_result_at(
            _as_observations(as_of[PAYEMS_SERIES_ID]),
            _as_observations(as_of[UNRATE_SERIES_ID]),
            period,
            CONDITION_DEADBAND_JOBS,
            MOMENTUM_DEADBAND_JOBS,
            UNEMPLOYMENT_DEADBAND_PP,
            identities=labor_identities,
        )

    def replay_with_recomputed_result(
        self, session: Session, recorded_monitor_result_id: int
    ) -> tuple[ReplayResult, RecomputedResult | None]:
        """`replay_recorded_result`, plus the recomputed methodology
        result itself when replay actually ran (Increment #32).

        Additive: `replay_recorded_result` keeps its exact #31 contract,
        and both paths share one code path, so the outcome a caller sees
        here can never disagree with the outcome #31's own verification
        reports. The second element is `None` for every
        `NOT_REPLAYABLE` outcome -- there is no honest recomputation to
        hand back.
        """
        replayed = self.replay_recorded_result(session, recorded_monitor_result_id)
        if replayed.outcome == "NOT_REPLAYABLE":
            return replayed, None

        recorded = session.get(RecordedMonitorResult, recorded_monitor_result_id)
        assert recorded is not None  # narrows; a missing row is already NOT_REPLAYABLE above
        versions = ObservationVersionRepository(session)
        series_ids = _MONITOR_INPUT_SERIES[recorded.monitor]
        as_of = {series_id: versions.get_observations_as_of(series_id, recorded.calculated_at) for series_id in series_ids}
        return replayed, self._recompute(recorded, as_of, *self._identities(session))

    def list_replayable_results(self, session: Session, monitor: str | None = None, limit: int = 50) -> list[int]:
        """Recorded-result ids, newest first -- the entry point for
        verifying replay over real history without exposing a route."""
        statement = select(RecordedMonitorResult.id).order_by(RecordedMonitorResult.calculated_at.desc()).limit(limit)
        if monitor is not None:
            statement = statement.where(RecordedMonitorResult.monitor == monitor)
        return list(session.execute(statement).scalars().all())
