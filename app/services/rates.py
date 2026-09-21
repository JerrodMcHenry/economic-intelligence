"""Application/use-case orchestration for the Rates Monitor
(`rates_v1.0`).

Reads the six canonical Treasury series' persisted observations via
`RatesRepository` and delegates every actual calculation to
`app.domain.rates`'s pure functions -- this service contains no
methodology math of its own. Database-only, read-only: never calls
Treasury, never syncs, never triggers ingestion, never mutates a row.

A canonical series that is not persisted at all is treated exactly like
one persisted with insufficient history: both resolve to that
component's own `available: false`, never an exception. A genuine
database error still propagates for `app.api.rates` to map to 503/500 --
missing economic data and infrastructure failure are different outcomes,
the same discipline `InflationMonitorService` already follows.
"""

from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.domain.rates import (
    RateObservation,
    to_basis_points,
    change_over_sessions,
    historical_session_changes,
    recent_session_observations,
    inflation_compensation_series,
    latest_observation,
    rank_against,
    spread_series,
)
from app.models.rates import (
    CHANGE_WINDOWS,
    CHANGE_WINDOW_SESSIONS,
    CompensationId,
    CurveSpread,
    DerivedProvenance,
    HistoricalContext,
    InflationCompensation,
    NOMINAL_10Y_SERIES_ID,
    NOMINAL_2Y_SERIES_ID,
    NOMINAL_30Y_SERIES_ID,
    NOMINAL_5Y_SERIES_ID,
    NOMINAL_SERIES_IDS,
    REAL_10Y_SERIES_ID,
    REAL_5Y_SERIES_ID,
    REAL_SERIES_IDS,
    RateChange,
    RateLevel,
    RatesMonitorResult,
    SERIES_TITLES,
    SourceProvenance,
    SpreadId,
)
from app.repositories.rates_repository import RatesRepository

# The window whose historical context is reported alongside each metric.
# One window, chosen once: reporting a rank for every window would
# quadruple the response for no additional decision-relevant content.
_CONTEXT_WINDOW = "5_SESSIONS"

_SPREAD_DEFINITIONS: tuple[tuple[SpreadId, str, str, str], ...] = (
    ("2s10s", "10-Year minus 2-Year", NOMINAL_10Y_SERIES_ID, NOMINAL_2Y_SERIES_ID),
    ("2s30s", "30-Year minus 2-Year", NOMINAL_30Y_SERIES_ID, NOMINAL_2Y_SERIES_ID),
)

_COMPENSATION_DEFINITIONS: tuple[tuple[CompensationId, str, str, str], ...] = (
    ("5Y", "5-Year market-implied inflation compensation", NOMINAL_5Y_SERIES_ID, REAL_5Y_SERIES_ID),
    ("10Y", "10-Year market-implied inflation compensation", NOMINAL_10Y_SERIES_ID, REAL_10Y_SERIES_ID),
)


class RatesMonitorService:
    def get_result(self, session: Session) -> RatesMonitorResult:
        """The complete canonical `rates_v1.0` result, computed entirely
        from whatever is currently persisted. Deterministic for a given
        database state: two calls in immediate succession, with no
        intervening write, return identical results."""
        repo = RatesRepository(session)
        observations = {series_id: self._load(repo, series_id) for series_id in (*NOMINAL_SERIES_IDS, *REAL_SERIES_IDS)}

        nominal_curve = [self._build_level(repo, series_id, observations[series_id]) for series_id in NOMINAL_SERIES_IDS]
        real_curve = [self._build_level(repo, series_id, observations[series_id]) for series_id in REAL_SERIES_IDS]

        calculated_at = datetime.now(timezone.utc)
        spreads = [
            self._build_spread(spread_id, title, long_id, short_id, observations, calculated_at)
            for spread_id, title, long_id, short_id in _SPREAD_DEFINITIONS
        ]
        compensation = [
            self._build_compensation(maturity, title, nominal_id, real_id, observations, calculated_at)
            for maturity, title, nominal_id, real_id in _COMPENSATION_DEFINITIONS
        ]

        return RatesMonitorResult(
            as_of_date=self._as_of_date(observations),
            nominal_curve=nominal_curve,
            real_curve=real_curve,
            curve_spreads=spreads,
            inflation_compensation=compensation,
        )

    def get_recent_observations(
        self,
        session: Session,
        series_id: str,
        sessions: int,
        as_of: date,
    ) -> list[RateObservation]:
        """The latest `sessions` published observations for one canonical
        series, at or before `as_of` (#40C visual evidence).

        Database-only and read-only, exactly like `get_result`: this
        never calls Treasury and never triggers ingestion. It exists so
        that the bounded series a surface DRAWS comes from the same
        canonical service, under the same `usable_observations` rule, as
        the numbers the surface prints -- rather than from a second
        query a frontend made on its own.

        Returns `[]` for a series with no usable history, which callers
        report honestly rather than treating as an error.
        """
        repo = RatesRepository(session)
        return recent_session_observations(self._load(repo, series_id), sessions, as_of)

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    @staticmethod
    def _load(repo: RatesRepository, series_id: str) -> list[RateObservation]:
        return [
            RateObservation(observation_date=row.observation_date, value=row.value)
            for row in repo.get_observations(series_id)
        ]

    @staticmethod
    def _as_of_date(observations: dict[str, list[RateObservation]]) -> date | None:
        """The most recent date any canonical series has a usable value
        for. Deliberately a maximum across series, not a shared date:
        the nominal and real curves publish on the same schedule but a
        derived metric still requires its own exact alignment, which is
        each metric's own job to report."""
        latest_dates = [
            latest.observation_date for latest in (latest_observation(series) for series in observations.values()) if latest
        ]
        return max(latest_dates) if latest_dates else None

    # ------------------------------------------------------------------
    # Assembly
    # ------------------------------------------------------------------

    def _changes(self, observations: list[RateObservation]) -> list[RateChange]:
        changes: list[RateChange] = []
        for window in CHANGE_WINDOWS:
            sessions = CHANGE_WINDOW_SESSIONS[window]
            computed = change_over_sessions(observations, sessions)
            changes.append(
                RateChange(
                    window=window,
                    sessions=sessions,
                    available=computed.available,
                    change_basis_points=computed.change_basis_points,
                    from_date=computed.from_date,
                    from_value=computed.from_value,
                    to_date=computed.to_date,
                    to_value=computed.to_value,
                )
            )
        return changes

    def _historical_context(self, observations: list[RateObservation]) -> HistoricalContext:
        sessions = CHANGE_WINDOW_SESSIONS[_CONTEXT_WINDOW]
        history = historical_session_changes(observations, sessions)
        if not history:
            return HistoricalContext(
                available=False,
                window=_CONTEXT_WINDOW,
                observation_count=0,
                history_start_date=None,
                history_end_date=None,
                percentile_rank=None,
                magnitude_percentile_rank=None,
                minimum_change_basis_points=None,
                maximum_change_basis_points=None,
            )

        current_change = history[-1][1]
        # The current change is ranked against the PRIOR population --
        # a value is never counted as being less than itself, and the
        # rank answers "how does today compare with history", not "how
        # does today compare with history including today".
        population = [value for _, value in history[:-1]]
        rank = rank_against(population, current_change)

        return HistoricalContext(
            available=rank.available,
            window=_CONTEXT_WINDOW,
            observation_count=rank.observation_count,
            history_start_date=history[0][0],
            history_end_date=history[-1][0],
            percentile_rank=rank.percentile_rank,
            magnitude_percentile_rank=rank.magnitude_percentile_rank,
            minimum_change_basis_points=rank.minimum,
            maximum_change_basis_points=rank.maximum,
        )

    def _build_level(self, repo: RatesRepository, series_id: str, observations: list[RateObservation]) -> RateLevel:
        latest = latest_observation(observations)
        provenance = None
        if latest is not None:
            row = repo.get_provenance(series_id, latest.observation_date)
            if row is not None:
                provenance = SourceProvenance(
                    provider=row.provider,
                    dataset=row.dataset,
                    series_id=series_id,
                    observation_date=row.observation_date,
                    source_url=row.source_url,
                    retrieved_at=row.retrieved_at,
                    revision_count=row.revision_count,
                    last_revised_at=row.last_revised_at,
                )

        return RateLevel(
            series_id=series_id,
            title=SERIES_TITLES[series_id],
            available=latest is not None,
            latest_date=latest.observation_date if latest else None,
            latest_value=latest.value if latest else None,
            changes=self._changes(observations),
            historical_context=self._historical_context(observations),
            provenance=provenance,
        )

    def _build_spread(
        self,
        spread_id: SpreadId,
        title: str,
        long_series_id: str,
        short_series_id: str,
        observations: dict[str, list[RateObservation]],
        calculated_at: datetime,
    ) -> CurveSpread:
        series = spread_series(observations[long_series_id], observations[short_series_id])
        latest = latest_observation(series)

        if latest is None:
            return CurveSpread(
                spread_id=spread_id,
                title=title,
                available=False,
                observation_date=None,
                spread_basis_points=None,
                long_series_id=long_series_id,
                short_series_id=short_series_id,
                long_value=None,
                short_value=None,
                unavailable_reason=self._alignment_reason(observations[long_series_id], observations[short_series_id]),
                changes=self._changes(series),
                historical_context=self._historical_context(series),
                provenance=None,
            )

        long_value = self._value_on(observations[long_series_id], latest.observation_date)
        short_value = self._value_on(observations[short_series_id], latest.observation_date)

        return CurveSpread(
            spread_id=spread_id,
            title=title,
            available=True,
            observation_date=latest.observation_date,
            # The spread SERIES is in percentage points (see
            # `spread_series`); the reported LEVEL converts once, here.
            spread_basis_points=to_basis_points(latest.value) if latest.value is not None else None,
            long_series_id=long_series_id,
            short_series_id=short_series_id,
            long_value=long_value,
            short_value=short_value,
            unavailable_reason=None,
            changes=self._changes(series),
            historical_context=self._historical_context(series),
            provenance=DerivedProvenance(
                calculation=f"{long_series_id} - {short_series_id}, in basis points, on one exactly-shared observation date",
                input_series_ids=[long_series_id, short_series_id],
                input_observation_date=latest.observation_date,
                calculated_at=calculated_at,
            ),
        )

    def _build_compensation(
        self,
        maturity: CompensationId,
        title: str,
        nominal_series_id: str,
        real_series_id: str,
        observations: dict[str, list[RateObservation]],
        calculated_at: datetime,
    ) -> InflationCompensation:
        series = inflation_compensation_series(observations[nominal_series_id], observations[real_series_id])
        latest = latest_observation(series)

        if latest is None:
            return InflationCompensation(
                maturity=maturity,
                title=title,
                available=False,
                observation_date=None,
                compensation_percent=None,
                nominal_series_id=nominal_series_id,
                real_series_id=real_series_id,
                nominal_value=None,
                real_value=None,
                unavailable_reason=self._alignment_reason(
                    observations[nominal_series_id], observations[real_series_id]
                ),
                changes=self._changes(series),
                historical_context=self._historical_context(series),
                provenance=None,
            )

        return InflationCompensation(
            maturity=maturity,
            title=title,
            available=True,
            observation_date=latest.observation_date,
            compensation_percent=latest.value,
            nominal_series_id=nominal_series_id,
            real_series_id=real_series_id,
            nominal_value=self._value_on(observations[nominal_series_id], latest.observation_date),
            real_value=self._value_on(observations[real_series_id], latest.observation_date),
            unavailable_reason=None,
            changes=self._changes(series),
            historical_context=self._historical_context(series),
            provenance=DerivedProvenance(
                calculation=(
                    f"{nominal_series_id} - {real_series_id}, in percentage points, on one exactly-shared "
                    "observation date; market-implied compensation, not an inflation forecast"
                ),
                input_series_ids=[nominal_series_id, real_series_id],
                input_observation_date=latest.observation_date,
                calculated_at=calculated_at,
            ),
        )

    @staticmethod
    def _value_on(observations: list[RateObservation], observation_date: date) -> float | None:
        for obs in observations:
            if obs.observation_date == observation_date:
                return obs.value
        return None

    @staticmethod
    def _alignment_reason(first: list[RateObservation], second: list[RateObservation]) -> str:
        """Why a two-series derived metric could not be computed --
        stated precisely, so "we have no data" is never confused with
        "the two sides never line up"."""
        first_latest = latest_observation(first)
        second_latest = latest_observation(second)
        if first_latest is None and second_latest is None:
            return "NO_OBSERVATIONS_FOR_EITHER_SERIES"
        if first_latest is None or second_latest is None:
            return "NO_OBSERVATIONS_FOR_ONE_SERIES"
        return "NO_EXACTLY_SHARED_OBSERVATION_DATE"
