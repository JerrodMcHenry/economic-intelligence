"""Read-side orchestration for the Housing world (Increment #45).

Assembles `HousingResult` from already-persisted observations and their
provenance. Deliberately a SEPARATE class from the ingestion service
rather than a mode on it -- the same structural separation
`RatesMonitorService`/`RatesIngestionService` and
`ReleaseReadService`/`ReleaseSyncService` already use: NO METHOD ON THIS
CLASS ACCEPTS OR CONSTRUCTS A `CensusClient`, so it is *incapable* of
calling upstream, not merely discouraged from it. A page load can
therefore never drive provider traffic, and ingestion can never be an
accidental side effect of someone reading.

That property matters more here than it did for Rates: Census requires a
credential, so an accidental read-triggered fetch would burn an
authenticated quota on every page view.

WHAT THIS SERVICE COMPUTES: nothing. Every number it returns comes from
`app.domain.housing`'s pure functions over stored rows. It orchestrates,
shapes and reports availability; it does no arithmetic of its own.
"""

from datetime import date

from sqlalchemy.orm import Session

from app.concepts.bindings import active_binding
from app.concepts.registry import concept
from app.db.models import EconomicSeries
from app.domain.housing import (
    HousingObservation,
    latest,
    preceding_comparison,
    recent_window,
    year_ago_comparison,
)
from app.models.housing import (
    HOUSING_CONCEPT_IDS,
    PIPELINE_LIMITATIONS,
    PIPELINE_STAGES,
    STAGE_CONCEPTS,
    TREND_MONTHS,
    HousingMeasure,
    HousingProvenance,
    HousingResult,
    HousingStage,
    HousingTrend,
    HousingTrendPoint,
)
from app.repositories.housing_repository import HousingRepository

#: Why a measure has no figure. A fixed vocabulary of sentences, because
#: "unavailable" with no reason is indistinguishable from a bug, and a
#: reason assembled from provider text could carry anything.
NEVER_INGESTED = (
    "No Census New Residential Construction data has been ingested into this environment for this measure."
)
NO_USABLE_VALUE = (
    "MacroChipz holds observations for this measure but none carries a published value."
)


class HousingReadService:
    """Database-only, always."""

    def get_result(self, session: Session) -> HousingResult:
        """The canonical Housing read model.

        A measure with no data is reported as `available: false` with a
        reason inside a normal result -- never an exception, and never a
        zero. Only a genuine database failure is an error, and that is
        the route's concern.
        """
        repo = HousingRepository(session)
        measures = {concept_id: self._measure(repo, concept_id) for concept_id in HOUSING_CONCEPT_IDS}

        stages = []
        for stage in PIPELINE_STAGES:
            pace_concept_id, actual_concept_id = STAGE_CONCEPTS[stage]
            stages.append(
                HousingStage(
                    stage=stage,
                    pace=measures[pace_concept_id],
                    actual=measures[actual_concept_id],
                )
            )

        # The newest month ANY measure has a value for. Not the newest
        # month every measure has: completions history begins in 1968 and
        # permits in 1959, and requiring agreement would hide a perfectly
        # good figure behind a series that simply starts later.
        periods = [measure.period for measure in measures.values() if measure.period is not None]

        return HousingResult(
            as_of_period=max(periods) if periods else None,
            stages=stages,
            limitations=list(PIPELINE_LIMITATIONS),
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _measure(self, repo: HousingRepository, concept_id: str) -> HousingMeasure:
        concept_obj = concept(concept_id)
        binding = active_binding(concept_id)

        series = repo.get_series(binding.storage_series_id)
        rows = [] if series is None else repo.observations_for(series)
        observations = [
            HousingObservation(observation_date=row.observation_date, value=row.value)
            for row in rows
            if row.value is not None
        ]

        if series is None or not rows:
            return HousingMeasure(
                concept_id=concept_id,
                unit=concept_obj.canonical_unit,
                seasonal_adjustment=concept_obj.seasonal_adjustment,
                available=False,
                unavailable_reason=NEVER_INGESTED,
            )
        if not observations:
            return HousingMeasure(
                concept_id=concept_id,
                unit=concept_obj.canonical_unit,
                seasonal_adjustment=concept_obj.seasonal_adjustment,
                available=False,
                unavailable_reason=NO_USABLE_VALUE,
                observation_count=0,
            )

        newest = latest(observations)
        assert newest is not None  # non-empty by the guard above
        preceding = preceding_comparison(observations)
        year_ago = year_ago_comparison(observations)
        window = recent_window(observations, TREND_MONTHS)

        return HousingMeasure(
            concept_id=concept_id,
            unit=concept_obj.canonical_unit,
            seasonal_adjustment=concept_obj.seasonal_adjustment,
            available=True,
            period=newest.observation_date,
            value=newest.value,
            previous_period=preceding.period,
            previous_value=preceding.value,
            change_from_previous=preceding.change,
            change_percent_from_previous=preceding.change_percent,
            year_ago_period=year_ago.period,
            year_ago_value=year_ago.value,
            change_from_year_ago=year_ago.change,
            change_percent_from_year_ago=year_ago.change_percent,
            observation_count=len(observations),
            earliest_period=min(item.observation_date for item in observations),
            provenance=self._provenance(repo, series, newest.observation_date),
            trend=HousingTrend(
                concept_id=concept_id,
                unit=concept_obj.canonical_unit,
                requested_months=TREND_MONTHS,
                available_months=len(window),
                points=[
                    HousingTrendPoint(observation_date=item.observation_date, value=item.value)
                    for item in window
                ],
            ),
        )

    @staticmethod
    def _provenance(
        repo: HousingRepository, series: EconomicSeries, observation_date: date
    ) -> HousingProvenance | None:
        row = repo.provenance_for(series, observation_date)
        if row is None:
            # Legitimately possible: an observation written by some other
            # path, or one whose provenance row was never created. A
            # missing row means "not recorded", never a source silently
            # assumed.
            return None
        return HousingProvenance(
            provider=row.provider,
            dataset=row.dataset,
            # Census's own identifier for the series, read from the
            # stored row rather than from a module constant (#38).
            provider_series_id=row.source_series_field,
            observation_date=row.observation_date,
            source_url=row.source_url,
            retrieved_at=row.retrieved_at,
            revision_count=row.revision_count,
            last_revised_at=row.last_revised_at,
        )
