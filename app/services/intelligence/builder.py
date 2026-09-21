"""Construction of Structured Intelligence Objects (Increment #39).

THE one place intelligence objects are built. API routes ask for them;
they never assemble one themselves, and they never re-derive what
happened from domain results.

What this builder is allowed to do: read already-persisted canonical
data and project it. What it must never do -- guarded structurally by
`tests/test_intelligence_architecture.py`:

- call a language model, or import anything that can
- call an upstream provider (FRED, Treasury, anything)
- infer a fact the canonical data does not contain
- fabricate a timestamp, a value, or a provenance
- mutate canonical data in order to produce a presentation object

Generation is ON READ. Every object here is reconstructable from
canonical stored rows -- check runs, observation updates, analysis
updates, observations and provenance -- so nothing new is persisted and
no object can drift from the facts it claims. See
docs/architecture/structured-intelligence.md §"Persistence decision".
"""

from collections import defaultdict
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import EconomicSeries, ReleaseAnalysisUpdate, ReleaseCheckRun, ReleaseObservationUpdate
from app.models.inflation import (
    CONFIRMATION_CONCEPT_ID,
    HEADLINE_CPI_CONCEPT_ID,
    METHODOLOGY_ID as INFLATION_METHODOLOGY_ID,
    PRIMARY_CONCEPT_ID,
    TARGET_CONCEPT_ID,
)
from app.models.intelligence import (
    AnalysisChangeIntelligence,
    AnalysisChangePayload,
    ChangeClass,
    EvidenceRef,
    IntelligenceObject,
    MethodologyRef,
    ObservationChangeIntelligence,
    ObservationChangePayload,
    RatesChangeRef,
    RevisionKnowledge,
    TimeSeriesVisualEvidence,
    VisualEvidencePoint,
    RatesMovementIntelligence,
    RatesMovementPayload,
    Relation,
    ReleaseProcessedIntelligence,
    ReleaseProcessedPayload,
    World,
)
from app.models.labor import (
    EMPLOYMENT_CONCEPT_ID,
    METHODOLOGY_ID as LABOR_METHODOLOGY_ID,
    UNEMPLOYMENT_CONCEPT_ID,
)
from app.models.rates import METHODOLOGY_ID as RATES_METHODOLOGY_ID
from app.repositories.observation_versions import ObservationVersionRepository
from app.repositories.release_processing_read_repository import ReleaseProcessingReadRepository
from app.services.intelligence.identity import (
    analysis_change_id,
    observation_change_id,
    rates_movement_id,
    release_processed_id,
)
from app.services.rates import RatesMonitorService

#: Methodology -> world. Derived from DOMAIN semantics, never from a
#: provider identifier (#39 §12): `labor_v1.0` is the jobs world because
#: of what it measures, not because FRED happens to publish its inputs.
_WORLD_BY_METHODOLOGY: dict[str, World] = {
    INFLATION_METHODOLOGY_ID: "inflation",
    LABOR_METHODOLOGY_ID: "jobs",
    RATES_METHODOLOGY_ID: "rates",
}

#: Methodology component -> the concepts it is about.
#:
#: These follow the frozen methodologies' own role assignments -- the
#: same roles `app/models/inflation.py` and `app/models/labor.py` name.
#: Concept constants are imported rather than restated, so this cannot
#: drift from #38's registry.
_CONCEPTS_BY_COMPONENT: dict[str, tuple[str, ...]] = {
    "PRIMARY_MOMENTUM": (PRIMARY_CONCEPT_ID,),
    "CONFIRMATION": (PRIMARY_CONCEPT_ID, CONFIRMATION_CONCEPT_ID),
    "TARGET": (TARGET_CONCEPT_ID,),
    "HEADLINE_PCE": (TARGET_CONCEPT_ID,),
    "HEADLINE_CPI": (HEADLINE_CPI_CONCEPT_ID,),
    "EMPLOYMENT": (EMPLOYMENT_CONCEPT_ID,),
    "UNEMPLOYMENT": (UNEMPLOYMENT_CONCEPT_ID,),
    # LABOR is the combined top-level state, co-owned by both components.
    "LABOR": (EMPLOYMENT_CONCEPT_ID, UNEMPLOYMENT_CONCEPT_ID),
}

#: Which analysis event types are about the ECONOMY and which are about
#: MacroChipz's own data COVERAGE. See `ChangeClass` for why this
#: distinction is carried as a typed field rather than left to
#: presentation.
_COVERAGE_EVENT_TYPES = frozenset({"AVAILABILITY_LOST", "AVAILABILITY_RESTORED"})


def _change_class(event_type: str) -> ChangeClass:
    return "COVERAGE" if event_type in _COVERAGE_EVENT_TYPES else "ECONOMIC"


def _utc(value: datetime) -> datetime:
    """Normalise to UTC so identity dimensions are stable regardless of
    how the driver returned the timestamp."""
    return value.astimezone(timezone.utc) if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


class IntelligenceBuilder:
    """Builds every Structured Intelligence Object from canonical data.

    Read-only. Holds no state between calls, so two calls against an
    unchanged database return identical objects.
    """

    def __init__(self, rates_service: RatesMonitorService | None = None) -> None:
        # Injected so a test can exercise the rates path without a
        # database; defaults to the real read-only service, which itself
        # has no provider client and is structurally incapable of
        # calling Treasury.
        self._rates_service = rates_service or RatesMonitorService()

    # -- public ------------------------------------------------------

    def build_all(self, session: Session) -> list[IntelligenceObject]:
        """Every intelligence object the current canonical data
        supports, in deterministic order.

        Ordered by `effective_period DESC, recorded_at DESC, id ASC` --
        time first, then a total tiebreak on the stable id. There is no
        relevance ordering, because the engine defines no deterministic
        notion of relevance (see the module contract).
        """
        objects: list[IntelligenceObject] = []
        objects.extend(self._release_intelligence(session))
        objects.extend(self._rates_intelligence(session))
        return sort_intelligence(objects)

    # -- release-derived ---------------------------------------------

    def _release_intelligence(self, session: Session) -> list[IntelligenceObject]:
        """`RELEASE_PROCESSED`, `OBSERVATION_CHANGE` and
        `ANALYSIS_CHANGE`, all from persisted release-processing rows.

        Every row read here was written by a real check run, so these
        objects are `OBSERVED`: MacroChipz genuinely detected them, at
        the timestamps recorded.
        """
        repo = ReleaseProcessingReadRepository(session)
        pairs = repo.list_mapped_occurrences()
        if not pairs:
            return []

        occurrence_ids = [occurrence.id for occurrence, _ in pairs]
        runs = repo.list_check_runs_for_occurrences(occurrence_ids)
        if not runs:
            return []

        run_ids = [run.id for run in runs]
        observation_updates = repo.list_observation_updates_for_runs(run_ids)
        analysis_updates = repo.list_analysis_updates_for_runs(run_ids)

        # One batched metadata read rather than a lookup per update --
        # the N+1 this endpoint would otherwise have.
        series_ids = sorted({update.series_id for update in observation_updates})
        series_by_id = repo.list_series_metadata(series_ids) if series_ids else {}

        runs_by_occurrence: dict[int, list[ReleaseCheckRun]] = defaultdict(list)
        for run in runs:
            runs_by_occurrence[run.release_occurrence_id].append(run)

        observations_by_run: dict[int, list[ReleaseObservationUpdate]] = defaultdict(list)
        for update in observation_updates:
            observations_by_run[update.release_check_run_id].append(update)

        analyses_by_run: dict[int, list[ReleaseAnalysisUpdate]] = defaultdict(list)
        for update in analysis_updates:
            analyses_by_run[update.release_check_run_id].append(update)

        completed_at_by_run = {run.id: _utc(run.completed_at) for run in runs}

        objects: list[IntelligenceObject] = []

        for occurrence, release in pairs:
            occurrence_runs = runs_by_occurrence.get(occurrence.id, [])
            if not occurrence_runs:
                # No check run means MacroChipz has not processed this
                # occurrence. There is no intelligence to report, and a
                # placeholder would be manufactured activity.
                continue

            latest = max(occurrence_runs, key=lambda run: (run.completed_at, run.id))
            own_observations = observations_by_run.get(latest.id, [])
            world = self._release_world(own_observations, series_by_id, analyses_by_run.get(latest.id, []))
            if world is None:
                continue

            new_count = sum(1 for update in own_observations if update.change_type == "NEW")
            revised_count = sum(1 for update in own_observations if update.change_type == "REVISED")

            objects.append(
                ReleaseProcessedIntelligence(
                    id=release_processed_id(release.provider, release.provider_release_id, occurrence.scheduled_date),
                    world=world,
                    concepts=sorted(self._concepts_for_series(own_observations, series_by_id)),
                    effective_period=occurrence.scheduled_date,
                    recorded_at=completed_at_by_run[latest.id],
                    # The calendar gives a scheduled DATE, and this
                    # project's own FRED client documents that a release
                    # date is not proof data was published. Claiming a
                    # publication time here would be a fabrication.
                    published_at=None,
                    knowledge_basis="OBSERVED",
                    basis="SOURCE_FACT",
                    methodology=None,
                    relations=[Relation(kind="AFFECTS_WORLD", target=world)],
                    limitations=[
                        "Reports that MacroChipz checked and processed this release. It makes no claim "
                        "about what the economy did -- any methodology conclusions appear as separate "
                        "ANALYSIS_CHANGE objects.",
                        "The scheduled date is the provider's published schedule, not a confirmed "
                        "publication time.",
                    ],
                    payload=ReleaseProcessedPayload(
                        release_name=release.name,
                        provider=release.provider,
                        provider_release_id=release.provider_release_id,
                        scheduled_date=occurrence.scheduled_date,
                        status=latest.status,
                        observation_changes=len(own_observations),
                        new_observations=new_count,
                        revised_observations=revised_count,
                    ),
                )
            )

            release_id = release_processed_id(
                release.provider, release.provider_release_id, occurrence.scheduled_date
            )

            for update in own_observations:
                obj = self._observation_change(session, update, series_by_id, release_id)
                if obj is not None:
                    objects.append(obj)

            for run in occurrence_runs:
                for analysis in analyses_by_run.get(run.id, []):
                    obj = self._analysis_change(analysis, completed_at_by_run[run.id], release_id)
                    if obj is not None:
                        objects.append(obj)

        return objects

    def _observation_change(
        self,
        session: Session,
        update: ReleaseObservationUpdate,
        series_by_id: dict[str, EconomicSeries],
        release_id: str,
    ) -> ObservationChangeIntelligence | None:
        series = series_by_id.get(update.series_id)
        if series is None or series.concept_id is None:
            # An observation on a series with no registered concept is
            # not MacroChipz intelligence -- it is an arbitrary provider
            # series someone synced. Omitted rather than guessed (#38).
            return None

        delta = (
            update.new_value - update.previous_value
            if update.new_value is not None and update.previous_value is not None
            else None
        )
        world = _WORLD_BY_METHODOLOGY.get(self._methodology_for_concept(series.concept_id) or "")
        if world is None:
            return None

        detected_at = _utc(update.detected_at)
        limitations = [
            "Records that MacroChipz detected this observation, not that the provider published it "
            "at this instant.",
        ]
        if update.change_type == "NEW":
            limitations.append("A first observation, not a revision: there was no previous value to compare.")

        knowledge = self._revision_knowledge(session, series.series_id, update)
        if knowledge == "BACKFILLED_BASELINE":
            limitations.append(
                "MacroChipz imported this value when point-in-time tracking began, so it cannot establish "
                "what the provider had published for this period before then."
            )

        return ObservationChangeIntelligence(
            id=observation_change_id(series.concept_id, update.observation_date, detected_at),
            world=world,
            concepts=[series.concept_id],
            effective_period=update.observation_date,
            recorded_at=detected_at,
            published_at=None,
            knowledge_basis="OBSERVED",
            basis="SOURCE_FACT",
            methodology=None,
            evidence=[
                EvidenceRef(
                    concept_id=series.concept_id,
                    # Identity read from the stored series row (#38),
                    # never from a module constant.
                    provider=series.source,
                    provider_series_id=series.series_id,
                    observation_date=update.observation_date,
                    value=update.new_value,
                )
            ],
            relations=[
                Relation(kind="PART_OF_RELEASE", target=release_id),
                Relation(kind="CONCERNS_CONCEPT", target=series.concept_id),
                Relation(kind="AFFECTS_WORLD", target=world),
            ],
            limitations=limitations,
            payload=ObservationChangePayload(
                change_type="REVISED" if update.change_type == "REVISED" else "NEW",
                revision_knowledge=knowledge,
                # An original value is "known" only when MacroChipz
                # actually recorded it BEFORE the change -- never when
                # it was imported as a baseline.
                original_value_known=knowledge == "PROSPECTIVE_REVISION" and update.previous_value is not None,
                previous_value=update.previous_value,
                new_value=update.new_value,
                delta=delta,
                observation_date=update.observation_date,
                provider=series.source,
                provider_series_id=series.series_id,
                series_title=series.title,
                units=series.units,
            ),
        )

    def _analysis_change(
        self, update: ReleaseAnalysisUpdate, recorded_at: datetime, release_id: str
    ) -> AnalysisChangeIntelligence | None:
        world = _WORLD_BY_METHODOLOGY.get(update.methodology_id)
        if world is None:
            # A methodology this binary does not recognise. Omitted
            # rather than assigned to a world by guesswork.
            return None

        concepts = list(_CONCEPTS_BY_COMPONENT.get(update.component, ()))
        change_class = _change_class(update.event_type)

        limitations = [
            f"A conclusion of {update.methodology_id}, recorded during release processing.",
        ]
        if change_class == "COVERAGE":
            limitations.append(
                "A DATA COVERAGE change, not an economic one: it records that MacroChipz gained or "
                "lost the ability to compute this, not that the economy moved."
            )

        return AnalysisChangeIntelligence(
            id=analysis_change_id(
                update.methodology_id,
                update.component,
                update.field,
                update.evaluation_period,
                update.event_type,
            ),
            world=world,
            concepts=concepts,
            effective_period=update.evaluation_period,
            recorded_at=recorded_at,
            published_at=None,
            knowledge_basis="OBSERVED",
            basis="METHODOLOGY_DERIVED",
            methodology=MethodologyRef(methodology_id=update.methodology_id, data_basis=update.data_basis),
            relations=(
                [Relation(kind="PART_OF_RELEASE", target=release_id), Relation(kind="AFFECTS_WORLD", target=world)]
                + [Relation(kind="CONCERNS_CONCEPT", target=concept) for concept in concepts]
            ),
            limitations=limitations,
            payload=AnalysisChangePayload(
                component=update.component,
                event_type=update.event_type,
                change_class=change_class,
                field=update.field,
                previous_value=update.previous_value,
                current_value=update.current_value,
                delta=update.delta,
                evaluation_period=update.evaluation_period,
            ),
        )

    # -- rates-derived -----------------------------------------------

    def _rates_intelligence(self, session: Session) -> list[IntelligenceObject]:
        """One `RATES_MOVEMENT` per canonical Treasury series, at the
        latest as-of date only.

        Bounded by construction: `rates_v1.0` has six canonical series,
        so this contributes at most six objects however much history
        exists. Emitting one per series per historical date would be
        data, not intelligence.
        """
        result = self._rates_service.get_result(session)
        if result.as_of_date is None:
            return []

        objects: list[IntelligenceObject] = []
        for level in list(result.nominal_curve) + list(result.real_curve):
            if not level.available or level.latest_date is None:
                # No usable observation: nothing honest to report.
                continue

            provenance = level.provenance
            evidence = (
                [
                    EvidenceRef(
                        concept_id=level.series_id,
                        provider=provenance.provider,
                        provider_series_id=provenance.series_id,
                        observation_date=level.latest_date,
                        value=level.latest_value,
                    )
                ]
                if provenance is not None
                else []
            )

            limitations = [
                "Carries no significance claim: rates_v1.0 defines no notability threshold, so this "
                "reports the movement and its own historical position, not that the movement matters.",
                "Change windows are counted in trading SESSIONS, never calendar days.",
                "Treasury observations are stored under MacroChipz's own series identifiers, so "
                "`provider_series_id` here is the stored identifier rather than Treasury's own XML "
                "field name; that field is recorded in observation_provenance.source_series_field. "
                "See docs/architecture/economic-concept-identity.md section 6.",
            ]
            if provenance is None:
                limitations.append("No retrieval provenance is recorded for this observation.")

            objects.append(
                RatesMovementIntelligence(
                    id=rates_movement_id(level.series_id, level.latest_date),
                    world="rates",
                    concepts=[level.series_id],
                    effective_period=level.latest_date,
                    recorded_at=_utc(provenance.retrieved_at)
                    if provenance is not None
                    else datetime.combine(level.latest_date, datetime.min.time(), tzinfo=timezone.utc),
                    published_at=None,
                    knowledge_basis="OBSERVED" if provenance is not None else "BACKFILLED",
                    basis="METHODOLOGY_DERIVED",
                    methodology=MethodologyRef(
                        methodology_id=result.methodology_id, data_basis=result.data_basis
                    ),
                    evidence=evidence,
                    relations=[
                        Relation(kind="CONCERNS_CONCEPT", target=level.series_id),
                        Relation(kind="AFFECTS_WORLD", target="rates"),
                    ],
                    limitations=limitations,
                    payload=RatesMovementPayload(
                        series_title=level.title,
                        latest_value=level.latest_value,
                        changes=[
                            RatesChangeRef(
                                window=change.window,
                                sessions=change.sessions,
                                available=change.available,
                                change_basis_points=change.change_basis_points,
                                from_date=change.from_date,
                                from_value=change.from_value,
                            )
                            for change in level.changes
                        ],
                        historical_percentile_rank=level.historical_context.percentile_rank,
                        historical_magnitude_percentile_rank=level.historical_context.magnitude_percentile_rank,
                        historical_observation_count=level.historical_context.observation_count,
                        visual_evidence=self._rates_visual_evidence(
                            session, level.series_id, level.units, level.latest_date
                        ),
                    ),
                )
            )
        return objects

    #: How much recent history a RATES_MOVEMENT object carries for
    #: display (#40C). 63 published sessions, because that is already a
    #: `rates_v1.0` comparison window -- roughly three months of
    #: trading, enough to show shape, and bounded so the payload cannot
    #: grow with the database. It is NOT called "3 months" anywhere: it
    #: is a session count, and the calendar span it covers varies.
    VISUAL_EVIDENCE_SESSIONS = 63

    def _rates_visual_evidence(
        self,
        session: Session,
        series_id: str,
        unit: str,
        as_of: date,
    ) -> TimeSeriesVisualEvidence | None:
        """The bounded recent series behind one RATES_MOVEMENT object.

        Sourced from the canonical rates service, so the drawn series
        and the printed numbers cannot disagree. `None` when no usable
        history exists -- an object with nothing to show says so by
        omitting the field rather than carrying an empty chart.
        """
        observations = self._rates_service.get_recent_observations(
            session, series_id, self.VISUAL_EVIDENCE_SESSIONS, as_of
        )
        if not observations:
            return None

        points = [
            VisualEvidencePoint(observation_date=obs.observation_date, value=obs.value)
            for obs in observations
            if obs.value is not None
        ]
        if not points:
            return None

        return TimeSeriesVisualEvidence(
            concept_id=series_id,
            unit=unit,
            requested_sessions=self.VISUAL_EVIDENCE_SESSIONS,
            available_sessions=len(points),
            points=points,
        )

    @staticmethod
    def _revision_knowledge(
        session: Session, series_id: str, update: ReleaseObservationUpdate
    ) -> RevisionKnowledge:
        """What MacroChipz can honestly claim about this value's history.

        `change_type` alone is not enough, and the difference is the
        whole point of #43: a REVISED update whose earlier value was
        imported at migration time is NOT a revision MacroChipz
        watched happen, and calling it one would invent economic
        history. So the stored version rows are consulted, and the
        conservative answer is returned whenever they cannot prove
        otherwise.
        """
        if update.change_type != "REVISED":
            return "FIRST_OBSERVATION"

        versions = ObservationVersionRepository(session).list_versions(series_id, update.observation_date)
        if not versions:
            # No version history at all: nothing proves MacroChipz held
            # the earlier value prospectively.
            return "BACKFILLED_BASELINE"

        earliest = min(versions, key=lambda row: row.recorded_from)
        return "BACKFILLED_BASELINE" if earliest.is_backfilled else "PROSPECTIVE_REVISION"

    # -- helpers -----------------------------------------------------

    @staticmethod
    def _methodology_for_concept(concept_id: str) -> str | None:
        if concept_id in (PRIMARY_CONCEPT_ID, CONFIRMATION_CONCEPT_ID, TARGET_CONCEPT_ID, HEADLINE_CPI_CONCEPT_ID):
            return INFLATION_METHODOLOGY_ID
        if concept_id in (EMPLOYMENT_CONCEPT_ID, UNEMPLOYMENT_CONCEPT_ID):
            return LABOR_METHODOLOGY_ID
        return None

    @staticmethod
    def _concepts_for_series(
        updates: list[ReleaseObservationUpdate], series_by_id: dict[str, EconomicSeries]
    ) -> set[str]:
        concepts: set[str] = set()
        for update in updates:
            series = series_by_id.get(update.series_id)
            if series is not None and series.concept_id is not None:
                concepts.add(series.concept_id)
        return concepts

    def _release_world(
        self,
        observations: list[ReleaseObservationUpdate],
        series_by_id: dict[str, EconomicSeries],
        analyses: list[ReleaseAnalysisUpdate],
    ) -> World | None:
        """The world a processed release belongs to, from domain
        semantics only.

        Preference order: the methodologies that actually recorded a
        conclusion, then the concepts of the observations that changed.
        A release whose world cannot be established from either is
        omitted rather than assigned one.
        """
        for analysis in analyses:
            world = _WORLD_BY_METHODOLOGY.get(analysis.methodology_id)
            if world is not None:
                return world
        for concept_id in sorted(self._concepts_for_series(observations, series_by_id)):
            methodology = self._methodology_for_concept(concept_id)
            if methodology is not None:
                world = _WORLD_BY_METHODOLOGY.get(methodology)
                if world is not None:
                    return world
        return None


def sort_intelligence(objects: list[IntelligenceObject]) -> list[IntelligenceObject]:
    """`effective_period DESC, recorded_at DESC, id ASC`.

    The id tiebreak makes the order total, so two calls over identical
    data return an identical sequence -- which is what lets a consumer
    paginate without items shifting between pages.
    """
    return sorted(objects, key=lambda obj: (-obj.effective_period.toordinal(), -obj.recorded_at.timestamp(), obj.id))
