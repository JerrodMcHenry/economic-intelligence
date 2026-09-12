"""Application/use-case logic for cross-series (multi-series) analysis.

Coordinates two independent `SeriesRepository` lookups and delegates all
actual math to `app.domain.analysis`'s pure functions. Unlike
`EconomicDataService`, this service has no FRED dependency at all --
multi-series analysis only ever operates on data already persisted in
PostgreSQL, so there's nothing here for a `FREDClient` to do.

`SeriesNotFoundError`/`InvalidDateRangeError` are reused from
`app.services.economic_data` rather than redefined here -- they mean the
same thing in both places ("a requested series isn't persisted",
"start_date is after end_date"), and giving them separate classes with
identical names would make `except SeriesNotFoundError` ambiguous
depending on which module raised it.
"""

from datetime import date

from sqlalchemy.orm import Session

from app.domain.analysis import align_series, calculate_spread, count_usable_pairs, pearson_correlation
from app.models.analysis import AnalysisType, SeriesComparisonResponse
from app.models.series import Observation, SeriesSummary
from app.repositories.series_repository import SeriesRepository
from app.services.economic_data import InvalidDateRangeError, SeriesNotFoundError


class AnalysisService:
    def compare(
        self,
        series_a_id: str,
        series_b_id: str,
        session: Session,
        analysis: AnalysisType,
        start_date: date | None,
        end_date: date | None,
    ) -> SeriesComparisonResponse:
        """Compare two persisted series: exact-date alignment, spread, or
        Pearson correlation.

        Database-only: never calls FRED, never syncs, never mutates data.
        Date filters are applied per-series *before* alignment. Raises
        `InvalidDateRangeError` if start_date is after end_date, and
        `SeriesNotFoundError` (naming which one) if either series isn't
        persisted.
        """
        if start_date is not None and end_date is not None and start_date > end_date:
            raise InvalidDateRangeError("start_date must not be after end_date.")

        repo = SeriesRepository(session)

        series_a = repo.get_series_by_series_id(series_a_id)
        if series_a is None:
            raise SeriesNotFoundError(f"Series '{series_a_id}' is not persisted.")

        series_b = repo.get_series_by_series_id(series_b_id)
        if series_b is None:
            raise SeriesNotFoundError(f"Series '{series_b_id}' is not persisted.")

        raw_a = repo.get_observations_in_range(series_a.id, start_date, end_date)
        raw_b = repo.get_observations_in_range(series_b.id, start_date, end_date)

        observations_a = [Observation(date=obs.observation_date, value=obs.value) for obs in raw_a]
        observations_b = [Observation(date=obs.observation_date, value=obs.value) for obs in raw_b]

        aligned = align_series(observations_a, observations_b)
        usable_pairs = count_usable_pairs(aligned)

        correlation: float | None = None
        output_observations = aligned

        if analysis == "spread":
            output_observations = calculate_spread(aligned)
        elif analysis == "correlation":
            correlation = pearson_correlation(aligned)
            # A scalar result -- returning every aligned pair alongside it
            # isn't needed and the response contract asks for counts/the
            # result only (see app/models/analysis.py).
            output_observations = []

        return SeriesComparisonResponse(
            series_a=SeriesSummary(
                series_id=series_a.series_id, title=series_a.title, units=series_a.units, source=series_a.source
            ),
            series_b=SeriesSummary(
                series_id=series_b.series_id, title=series_b.title, units=series_b.units, source=series_b.source
            ),
            analysis=analysis,
            matching_pairs=len(aligned),
            usable_pairs=usable_pairs,
            correlation=correlation,
            observations=output_observations,
        )
