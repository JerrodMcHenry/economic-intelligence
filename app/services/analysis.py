"""Application/use-case logic for cross-series (multi-series) analysis.

Coordinates two independent `SeriesRepository` lookups and delegates all
actual math to `app.domain.analysis`'s (and, for pipeline transformations,
`app.domain.transformations`'s) pure functions. Unlike `EconomicDataService`,
this service has no FRED dependency at all -- multi-series analysis only
ever operates on data already persisted in PostgreSQL, so there's nothing
here for a `FREDClient` to do.

`SeriesNotFoundError`/`InvalidDateRangeError`/`InvalidWindowError` are
reused from `app.services.economic_data` rather than redefined here --
they mean the same thing in both places ("a requested series isn't
persisted", "start_date is after end_date", "window is missing/inapplicable
for this transformation"), and giving them separate classes with identical
names would make `except SeriesNotFoundError` (etc.) ambiguous depending
on which module raised it.
"""

from datetime import date

from sqlalchemy.orm import Session

from app.domain.analysis import align_series, calculate_spread, count_usable_pairs, pearson_correlation
from app.domain.transformations import absolute_change, moving_average, percent_change
from app.models.analysis import (
    AnalysisType,
    PipelineRequest,
    PipelineResponse,
    PipelineSeriesSummary,
    SeriesComparisonResponse,
    TransformationSpec,
)
from app.models.series import Observation, SeriesSummary, TransformationMeta
from app.repositories.series_repository import SeriesRepository
from app.services.economic_data import InvalidDateRangeError, InvalidWindowError, SeriesNotFoundError


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

    def pipeline(self, request: PipelineRequest, session: Session) -> PipelineResponse:
        """Execute a structured two-series analysis pipeline: each series is
        optionally transformed independently, then the results are
        exact-date aligned and the requested analysis is performed over
        the final (possibly transformed) values.

        Order of operations (correctness-critical -- see the journal for
        why): (1) validate the whole request -- date range and each side's
        transformation -- before touching the database; (2) look up both
        persisted series; (3)-(6) per series, independently: retrieve the
        requested range, retrieve any preceding context a transformation
        needs, transform, then trim the context back out; (7) exact-date
        align the two *final* series; (8) perform the requested analysis;
        (9) build the response. Database-only: never calls FRED, never
        syncs, never mutates data, and never persists any intermediate or
        final result.
        """
        start_date, end_date = request.start_date, request.end_date
        if start_date is not None and end_date is not None and start_date > end_date:
            raise InvalidDateRangeError("start_date must not be after end_date.")

        self._validate_transformation(request.series_a.transformation)
        self._validate_transformation(request.series_b.transformation)

        repo = SeriesRepository(session)

        series_a = repo.get_series_by_series_id(request.series_a.series_id)
        if series_a is None:
            raise SeriesNotFoundError(f"Series '{request.series_a.series_id}' is not persisted.")

        series_b = repo.get_series_by_series_id(request.series_b.series_id)
        if series_b is None:
            raise SeriesNotFoundError(f"Series '{request.series_b.series_id}' is not persisted.")

        observations_a = self._resolve_observations(
            repo, series_a.id, request.series_a.transformation, start_date, end_date
        )
        observations_b = self._resolve_observations(
            repo, series_b.id, request.series_b.transformation, start_date, end_date
        )

        aligned = align_series(observations_a, observations_b)
        usable_pairs = count_usable_pairs(aligned)

        correlation: float | None = None
        output_observations = aligned

        if request.analysis == "spread":
            output_observations = calculate_spread(aligned)
        elif request.analysis == "correlation":
            correlation = pearson_correlation(aligned)
            output_observations = []

        return PipelineResponse(
            series_a=PipelineSeriesSummary(
                series_id=series_a.series_id,
                title=series_a.title,
                units=series_a.units,
                source=series_a.source,
                transformation=self._transformation_meta(request.series_a.transformation),
            ),
            series_b=PipelineSeriesSummary(
                series_id=series_b.series_id,
                title=series_b.title,
                units=series_b.units,
                source=series_b.source,
                transformation=self._transformation_meta(request.series_b.transformation),
            ),
            analysis=request.analysis,
            matching_pairs=len(aligned),
            usable_pairs=usable_pairs,
            correlation=correlation,
            observations=output_observations,
        )

    @staticmethod
    def _validate_transformation(transformation: TransformationSpec | None) -> None:
        """The same window-applicability rule established for the
        single-series transform endpoint in Increment 005, applied here
        to one side of a pipeline request: `window` is required for
        `moving_average` and inapplicable to the other two types.
        `window`'s own numeric bounds are already enforced structurally
        by `TransformationSpec` (Pydantic `Field(ge=2, le=365)`)."""
        if transformation is None:
            return
        if transformation.type == "moving_average":
            if transformation.window is None:
                raise InvalidWindowError("window is required when type=moving_average.")
        elif transformation.window is not None:
            raise InvalidWindowError(f"window is not applicable to type={transformation.type}.")

    @staticmethod
    def _resolve_observations(
        repo: SeriesRepository,
        economic_series_id: int,
        transformation: TransformationSpec | None,
        start_date: date | None,
        end_date: date | None,
    ) -> list[Observation]:
        """Retrieve one series' final observations for the pipeline: raw
        persisted values if no transformation was requested, or correctly
        boundary-computed transformed values if one was.

        Reuses the same repository methods and pure transformation
        functions Increment 005 already built for the single-series
        transform endpoint (`get_observations_in_range`,
        `get_preceding_observations`, `absolute_change`/`percent_change`/
        `moving_average`) -- the retrieve-context-transform-trim sequence
        itself is intentionally re-expressed here (not extracted into a
        function shared with `EconomicDataService`) so this increment
        doesn't modify Increment 005's already-working code; see the
        journal for the reasoning.
        """
        requested = repo.get_observations_in_range(economic_series_id, start_date, end_date)

        if transformation is None:
            return [Observation(date=obs.observation_date, value=obs.value) for obs in requested]

        context_size = transformation.window - 1 if transformation.type == "moving_average" else 1
        context = (
            repo.get_preceding_observations(economic_series_id, before_date=start_date, count=context_size)
            if start_date is not None
            else []
        )

        combined = [Observation(date=obs.observation_date, value=obs.value) for obs in (context + requested)]

        if transformation.type == "absolute_change":
            transformed = absolute_change(combined)
        elif transformation.type == "percent_change":
            transformed = percent_change(combined)
        else:
            transformed = moving_average(combined, transformation.window)

        # Context observations were only needed to compute correct values
        # at the start of the requested range -- trim them back out
        # *before* alignment, so a context-only date from one series can
        # never accidentally align against the other series' data.
        output = transformed[len(context) :]
        return [Observation(date=point.date, value=point.value) for point in output]

    @staticmethod
    def _transformation_meta(transformation: TransformationSpec | None) -> TransformationMeta | None:
        if transformation is None:
            return None
        return TransformationMeta(type=transformation.type, window=transformation.window)
