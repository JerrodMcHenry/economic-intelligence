"""Structured Intelligence over real persisted canonical data
(Increment #39).

These seed genuine release-processing rows -- an occurrence, a check
run, observation updates, analysis updates -- and assert that what comes
out the other side is the same facts, correctly classified, with
identity and provenance intact.
"""

from datetime import date, datetime, timedelta, timezone

import pytest

from app.db.models import (
    EconomicRelease,
    EconomicSeries,
    ReleaseAnalysisUpdate,
    ReleaseCheckRun,
    ReleaseObservationUpdate,
    ReleaseOccurrence,
    ReleaseSeriesMapping,
)
from app.models.inflation import PRIMARY_CONCEPT_ID, PRIMARY_SERIES_ID
from app.services.intelligence import IntelligenceBuilder, IntelligenceService

SCHEDULED = date(2026, 9, 11)
PERIOD = date(2026, 8, 1)
DETECTED = datetime(2026, 9, 11, 13, 30, 0, tzinfo=timezone.utc)


class _NoRates:
    """A rates service double returning nothing, so the release-derived
    assertions below are not mixed with six rates objects. The real
    service is exercised separately in `TestRatesIntegration`."""

    @staticmethod
    def get_result(session):  # noqa: ANN001 - test double
        from app.models.rates import RatesMonitorResult

        return RatesMonitorResult(
            as_of_date=None,
            nominal_curve=[],
            real_curve=[],
            curve_spreads=[],
            inflation_compensation=[],
        )


@pytest.fixture
def seeded(db_session):
    """One processed CPI occurrence: two observations (one NEW, one
    REVISED) and two analysis updates (one economic, one coverage)."""
    series = db_session.query(EconomicSeries).filter_by(series_id=PRIMARY_SERIES_ID).one_or_none()
    if series is None:
        series = EconomicSeries(
            series_id=PRIMARY_SERIES_ID,
            concept_id=PRIMARY_CONCEPT_ID,
            title="Core PCE",
            units="Index 2017=100",
            source="BEA",
        )
        db_session.add(series)
    else:
        series.concept_id = PRIMARY_CONCEPT_ID

    release = EconomicRelease(
        name="Intelligence Test Release", provider="TESTPROV", provider_release_id="9901", active=True
    )
    db_session.add(release)
    db_session.flush()

    db_session.add(ReleaseSeriesMapping(economic_release_id=release.id, series_id=PRIMARY_SERIES_ID, active=True))
    occurrence = ReleaseOccurrence(
        economic_release_id=release.id, scheduled_date=SCHEDULED, first_seen_at=DETECTED, last_seen_at=DETECTED
    )
    db_session.add(occurrence)
    db_session.flush()

    run = ReleaseCheckRun(
        release_occurrence_id=occurrence.id,
        status="CHANGED",
        started_at=DETECTED,
        completed_at=DETECTED + timedelta(seconds=5),
    )
    db_session.add(run)
    db_session.flush()

    db_session.add_all(
        [
            ReleaseObservationUpdate(
                release_check_run_id=run.id,
                series_id=PRIMARY_SERIES_ID,
                observation_date=PERIOD,
                change_type="NEW",
                previous_value=None,
                new_value=125.5,
                detected_at=DETECTED,
            ),
            ReleaseObservationUpdate(
                release_check_run_id=run.id,
                series_id=PRIMARY_SERIES_ID,
                observation_date=date(2026, 7, 1),
                change_type="REVISED",
                previous_value=124.0,
                new_value=124.5,
                detected_at=DETECTED + timedelta(seconds=1),
            ),
            ReleaseAnalysisUpdate(
                release_check_run_id=run.id,
                component="PRIMARY_MOMENTUM",
                event_type="STATE_CHANGED",
                field="state",
                previous_value="STABLE",
                current_value="COOLING",
                delta=None,
                evaluation_period=PERIOD,
                methodology_id="inflation_v1.0",
                data_basis="latest_revised_data",
            ),
            ReleaseAnalysisUpdate(
                release_check_run_id=run.id,
                component="PRIMARY_MOMENTUM",
                event_type="AVAILABILITY_RESTORED",
                field="availability",
                previous_value=None,
                current_value="available",
                delta=None,
                evaluation_period=PERIOD,
                methodology_id="inflation_v1.0",
                data_basis="latest_revised_data",
            ),
        ]
    )
    db_session.flush()
    return release


@pytest.fixture
def objects(db_session, seeded):
    return IntelligenceBuilder(rates_service=_NoRates()).build_all(db_session)


def _of_type(objects, kind):
    return [obj for obj in objects if obj.type == kind]


def _for_release(objects):
    return [obj for obj in _of_type(objects, "RELEASE_PROCESSED") if obj.payload.provider == "TESTPROV"]


class TestDeterministicGeneration:
    def test_two_builds_over_unchanged_data_are_identical(self, db_session, seeded) -> None:
        builder = IntelligenceBuilder(rates_service=_NoRates())
        first = [obj.model_dump(mode="json") for obj in builder.build_all(db_session)]
        second = [obj.model_dump(mode="json") for obj in builder.build_all(db_session)]
        assert first == second

    def test_ordering_is_total_and_stable(self, db_session, seeded) -> None:
        objects = IntelligenceBuilder(rates_service=_NoRates()).build_all(db_session)
        keys = [(-o.effective_period.toordinal(), -o.recorded_at.timestamp(), o.id) for o in objects]
        assert keys == sorted(keys)

    def test_ids_are_unique(self, db_session, seeded) -> None:
        objects = IntelligenceBuilder(rates_service=_NoRates()).build_all(db_session)
        ids = [obj.id for obj in objects]
        assert len(ids) == len(set(ids))


class TestReleaseIntelligence:
    def test_a_processed_release_becomes_a_source_fact(self, objects) -> None:
        releases = _for_release(objects)
        assert len(releases) == 1
        obj = releases[0]
        assert obj.basis == "SOURCE_FACT"
        assert obj.methodology is None, "a release arriving is not a methodology conclusion"
        assert obj.payload.new_observations == 1
        assert obj.payload.revised_observations == 1

    def test_the_release_has_no_published_at(self, objects) -> None:
        assert _for_release(objects)[0].published_at is None

    def test_world_comes_from_methodology_not_provider(self, objects) -> None:
        assert _for_release(objects)[0].world == "inflation"


class TestObservationChangeIntelligence:
    def _seeded_observations(self, objects):
        return [o for o in _of_type(objects, "OBSERVATION_CHANGE") if o.concepts == [PRIMARY_CONCEPT_ID]]

    def test_a_revision_is_representable_with_both_values(self, objects) -> None:
        revised = [o for o in self._seeded_observations(objects) if o.payload.change_type == "REVISED"]
        assert revised, "the REVISED case must flow through the layer"
        payload = revised[0].payload
        assert payload.previous_value == 124.0
        assert payload.new_value == 124.5
        assert payload.delta == pytest.approx(0.5)

    def test_a_new_observation_has_no_previous_value_and_no_delta(self, objects) -> None:
        new = [o for o in self._seeded_observations(objects) if o.payload.change_type == "NEW"]
        assert new
        assert new[0].payload.previous_value is None
        assert new[0].payload.delta is None

    def test_concept_identity_is_preserved_and_provider_is_actual(self, objects) -> None:
        obj = self._seeded_observations(objects)[0]
        assert obj.concepts == [PRIMARY_CONCEPT_ID]
        # #56B: the row is BEA's, keyed by concept; the object names BEA's
        # own series id, never the storage key.
        assert obj.payload.provider == "BEA"
        assert obj.payload.provider_series_id == "DPCCRG"
        assert obj.payload.provider_series_id not in obj.concepts[0], "concept identity must not be the provider identifier"
        assert obj.evidence[0].provider_series_id == "DPCCRG"

    def test_evidence_resolves_to_the_observation(self, objects) -> None:
        obj = self._seeded_observations(objects)[0]
        assert obj.evidence
        ref = obj.evidence[0]
        assert ref.concept_id == PRIMARY_CONCEPT_ID
        assert (ref.provider, ref.provider_series_id) == ("BEA", "DPCCRG")
        assert ref.observation_date == obj.effective_period
        assert ref.value == obj.payload.new_value

    def test_recorded_at_is_the_detection_time(self, objects) -> None:
        obj = [o for o in self._seeded_observations(objects) if o.payload.change_type == "NEW"][0]
        assert obj.recorded_at == DETECTED


class TestAnalysisChangeIntelligence:
    def _seeded(self, objects):
        return [
            o
            for o in _of_type(objects, "ANALYSIS_CHANGE")
            if o.payload.component == "PRIMARY_MOMENTUM" and o.effective_period == PERIOD
        ]

    def test_economic_and_coverage_changes_are_distinguished(self, objects) -> None:
        classes = {o.payload.event_type: o.payload.change_class for o in self._seeded(objects)}
        assert classes.get("STATE_CHANGED") == "ECONOMIC"
        assert classes.get("AVAILABILITY_RESTORED") == "COVERAGE"

    def test_a_coverage_change_says_so_in_its_limitations(self, objects) -> None:
        coverage = [o for o in self._seeded(objects) if o.payload.change_class == "COVERAGE"][0]
        assert any("COVERAGE" in limitation for limitation in coverage.limitations)

    def test_methodology_version_is_carried(self, objects) -> None:
        obj = self._seeded(objects)[0]
        assert obj.basis == "METHODOLOGY_DERIVED"
        assert obj.methodology is not None
        assert obj.methodology.methodology_id == "inflation_v1.0"

    def test_the_two_event_types_do_not_collide_on_id(self, objects) -> None:
        ids = {o.id for o in self._seeded(objects)}
        assert len(ids) == len(self._seeded(objects))


class TestRatesIntegration:
    def test_rates_movements_are_bounded_and_methodology_derived(self, db_session) -> None:
        """The real rates service, over whatever is persisted. Bounded
        by construction: six canonical series, latest as-of only."""
        objects = [o for o in IntelligenceBuilder().build_all(db_session) if o.type == "RATES_MOVEMENT"]
        assert len(objects) <= 6
        for obj in objects:
            assert obj.world == "rates"
            assert obj.basis == "METHODOLOGY_DERIVED"
            assert obj.methodology is not None
            assert obj.methodology.methodology_id == "rates_v1.0"

    def test_rates_movements_make_no_significance_claim(self, db_session) -> None:
        objects = [o for o in IntelligenceBuilder().build_all(db_session) if o.type == "RATES_MOVEMENT"]
        for obj in objects:
            assert any("no significance claim" in limitation for limitation in obj.limitations)
            assert not hasattr(obj, "score")
            assert not hasattr(obj, "importance")


class TestVisualEvidence:
    """#40C. Visual evidence travels INSIDE the intelligence object, so
    a surface never needs a second query to draw what the object
    describes.

    Seeds a real Treasury series rather than relying on whatever the
    database happens to hold, so these assertions cannot pass
    vacuously.
    """

    #: 80 business days, so the 63-session bound is actually exercised,
    #: with two deliberate gaps: an unpublished value (a real Treasury
    #: occurrence) and a weekend, which the session rule must not
    #: mistake for missing data.
    SESSIONS = 80

    @pytest.fixture
    def seeded_rates(self, db_session):
        from app.clients.treasury import NOMINAL_DATASET
        from app.models.rates import NOMINAL_10Y_SERIES_ID, PROVIDER
        from app.repositories.rates_repository import ProvenanceRecord, RatesRepository

        repo = RatesRepository(db_session)
        series = repo.ensure_series(NOMINAL_10Y_SERIES_ID, "10Y", "Percent", PROVIDER)
        provenance = ProvenanceRecord(
            provider=PROVIDER,
            dataset=NOMINAL_DATASET,
            source_series_field="BC_10YEAR",
            source_url=f"https://home.treasury.gov/...?data={NOMINAL_DATASET}",
            retrieved_at=datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc),
        )

        day = date(2026, 1, 5)  # a Monday
        seeded = 0
        while seeded < self.SESSIONS:
            if day.weekday() < 5:  # business days only, like Treasury
                # One unpublished session, to prove it is dropped and
                # never interpolated across.
                value = None if seeded == 10 else round(4.0 + seeded * 0.01, 4)
                repo.upsert_observation(series, day, value, provenance)
                seeded += 1
            day += timedelta(days=1)
        db_session.flush()
        return NOMINAL_10Y_SERIES_ID

    def _objects(self, db_session):
        return [o for o in IntelligenceBuilder().build_all(db_session) if o.type == "RATES_MOVEMENT"]

    def test_every_rates_object_with_history_carries_its_series(self, db_session, seeded_rates) -> None:
        objects = self._objects(db_session)
        assert objects, "the fixture seeded a series, so an object must exist"
        for obj in objects:
            evidence = obj.payload.visual_evidence
            # A series with no usable history omits the field rather
            # than carrying an empty chart.
            if evidence is None:
                continue
            assert evidence.kind == "TIME_SERIES"
            assert evidence.points

    def test_the_series_is_bounded_at_63_sessions(self, db_session, seeded_rates) -> None:
        for obj in self._objects(db_session):
            evidence = obj.payload.visual_evidence
            if evidence is None:
                continue
            assert evidence.requested_sessions == 63
            assert len(evidence.points) <= 63
            assert evidence.available_sessions == len(evidence.points)

    def test_the_series_is_chronological_and_ends_at_the_effective_date(self, db_session, seeded_rates) -> None:
        for obj in self._objects(db_session):
            evidence = obj.payload.visual_evidence
            if evidence is None:
                continue
            dates = [point.observation_date for point in evidence.points]
            assert dates == sorted(dates)
            assert len(set(dates)) == len(dates), "a date must not appear twice"
            assert dates[-1] == obj.effective_period
            assert all(day <= obj.effective_period for day in dates), "nothing after the effective date"

    def test_the_series_uses_the_objects_own_concept_and_canonical_unit(self, db_session, seeded_rates) -> None:
        for obj in self._objects(db_session):
            evidence = obj.payload.visual_evidence
            if evidence is None:
                continue
            # #38: source-neutral concept identity, not a provider series id.
            assert evidence.concept_id == obj.concepts[0]
            assert evidence.unit == "Percent"

    def test_the_last_point_equals_the_value_the_object_reports(self, db_session, seeded_rates) -> None:
        """The drawn series and the printed number cannot disagree,
        because they come from the same read of the same service."""
        for obj in self._objects(db_session):
            evidence = obj.payload.visual_evidence
            if evidence is None:
                continue
            assert evidence.points[-1].value == obj.payload.latest_value

    def test_is_deterministic_across_two_reads(self, db_session, seeded_rates) -> None:
        first = {o.id: o.payload.visual_evidence for o in self._objects(db_session)}
        second = {o.id: o.payload.visual_evidence for o in self._objects(db_session)}
        assert first == second

    def test_an_unpublished_session_is_dropped_never_interpolated(self, db_session, seeded_rates) -> None:
        evidence = next(
            o.payload.visual_evidence for o in self._objects(db_session) if o.payload.visual_evidence
        )
        # The seeded gap carried `None`. It must be absent entirely --
        # not zero, not carried forward, not averaged across.
        assert all(point.value is not None for point in evidence.points)
        values = [point.value for point in evidence.points]
        assert len(set(values)) == len(values), "a carried-forward value would duplicate"


class TestBounding:
    def test_the_service_caps_limit(self, db_session, seeded) -> None:
        service = IntelligenceService(builder=IntelligenceBuilder(rates_service=_NoRates()))
        page = service.list_intelligence(db_session, limit=10_000)
        assert page.limit == 100
        assert len(page.items) <= 100

    def test_offset_and_limit_paginate_without_overlap(self, db_session, seeded) -> None:
        service = IntelligenceService(builder=IntelligenceBuilder(rates_service=_NoRates()))
        first = service.list_intelligence(db_session, limit=2, offset=0)
        second = service.list_intelligence(db_session, limit=2, offset=2)
        assert {o.id for o in first.items}.isdisjoint({o.id for o in second.items})

    def test_lookup_by_id_returns_the_same_object(self, db_session, seeded) -> None:
        service = IntelligenceService(builder=IntelligenceBuilder(rates_service=_NoRates()))
        page = service.list_intelligence(db_session, limit=1)
        found = service.get_intelligence(db_session, page.items[0].id)
        assert found is not None
        assert found.model_dump(mode="json") == page.items[0].model_dump(mode="json")

    def test_unknown_id_returns_none(self, db_session, seeded) -> None:
        service = IntelligenceService(builder=IntelligenceBuilder(rates_service=_NoRates()))
        assert service.get_intelligence(db_session, "release:NOPE:0:2026-01-01") is None


class TestHonestOmission:
    def test_a_series_without_a_concept_is_omitted_not_guessed(self, db_session, seeded) -> None:
        """An arbitrary provider series someone synced is not MacroChipz
        intelligence. Omitted rather than assigned a concept (#38)."""
        orphan = EconomicSeries(
            series_id="ARBITRARY_SERIES", concept_id=None, title="Arbitrary", units="Units", source="FRED"
        )
        db_session.add(orphan)
        db_session.flush()

        release = db_session.query(EconomicRelease).filter_by(provider_release_id="9901").one()
        run = (
            db_session.query(ReleaseCheckRun)
            .join(ReleaseOccurrence, ReleaseCheckRun.release_occurrence_id == ReleaseOccurrence.id)
            .filter(ReleaseOccurrence.economic_release_id == release.id)
            .first()
        )
        db_session.add(
            ReleaseObservationUpdate(
                release_check_run_id=run.id,
                series_id="ARBITRARY_SERIES",
                observation_date=PERIOD,
                change_type="NEW",
                previous_value=None,
                new_value=1.0,
                detected_at=DETECTED,
            )
        )
        db_session.flush()

        objects = IntelligenceBuilder(rates_service=_NoRates()).build_all(db_session)
        assert not any(
            o.type == "OBSERVATION_CHANGE" and o.payload.provider_series_id == "ARBITRARY_SERIES" for o in objects
        )
