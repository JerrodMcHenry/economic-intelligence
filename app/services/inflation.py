"""Application/use-case orchestration for the Inflation Monitor
(`inflation_v1.0`).

Reads the four canonical series' persisted observations via
`SeriesRepository` and delegates every actual calculation to
`app.domain.inflation`'s pure functions -- this service contains no
methodology math of its own. Database-only, read-only: never calls
FRED, never syncs, never triggers ingestion, never mutates
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

from app.domain.inflation import compute_inflation_monitor_result
from app.models.inflation import (
    CONFIRMATION_SERIES_ID,
    HEADLINE_CPI_SERIES_ID,
    InflationMonitorResult,
    PRIMARY_SERIES_ID,
    TARGET_SERIES_ID,
)
from app.models.series import Observation
from app.repositories.series_repository import SeriesRepository


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
