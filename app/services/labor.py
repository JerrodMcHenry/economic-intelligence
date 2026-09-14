"""Application/use-case orchestration for the Labor Market Monitor
(`labor_v1.0`).

Reads PAYEMS/UNRATE's persisted observations via the existing, generic
`SeriesRepository` -- no Labor-specific repository was needed, the
same "reuse existing generic persistence, don't invent a parallel one"
discipline `app.services.inflation.InflationMonitorService` already
follows for the same reason -- and delegates every actual calculation
to `app.domain.labor`'s pure functions. This service contains no
methodology math of its own. Database-only, read-only: never calls
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

from app.domain.labor import compute_labor_monitor_result
from app.models.labor import (
    CONDITION_DEADBAND_JOBS,
    LaborMonitorResult,
    MOMENTUM_DEADBAND_JOBS,
    PAYEMS_SERIES_ID,
    UNEMPLOYMENT_DEADBAND_PP,
    UNRATE_SERIES_ID,
)
from app.models.series import Observation
from app.repositories.series_repository import SeriesRepository


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

        return compute_labor_monitor_result(
            payems_observations=payems_observations,
            unrate_observations=unrate_observations,
            condition_deadband_jobs=CONDITION_DEADBAND_JOBS,
            momentum_deadband_jobs=MOMENTUM_DEADBAND_JOBS,
            unemployment_deadband_pp=UNEMPLOYMENT_DEADBAND_PP,
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
