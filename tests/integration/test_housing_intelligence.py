"""Housing in the Structured Intelligence layer (Increment #45, #39, #43).

The question these answer: does Housing produce honest intelligence
objects, and — the one that matters most — does its 4,644-observation
baseline import stay invisible?

A backfill that surfaced as 4,644 "new data point" entries would be
MacroChipz reporting its own migration as economic news. #39's builder
docstring already records the precedent (1,488 of 1,532 persisted
analysis updates are coverage records from one bootstrap run), and
Housing arrives with three times that volume at once.
"""

from datetime import date, datetime, timedelta, timezone

import pytest

from app.clients.census import CensusResconstRow
from app.services.census_ingestion import HousingIngestionService
from app.services.intelligence.builder import IntelligenceBuilder

pytestmark = pytest.mark.integration

PERMITS_SAAR = "us.housing.units-authorized.saar.monthly"
PERMITS_NSA = "us.housing.units-authorized.nsa.monthly"


class StubCensusClient:
    def __init__(self, rows):
        self._rows = rows

    def get_resconst(self, time_expression: str, dataset: str | None = None):
        return list(self._rows), []


def _row(period: date, value: float, category_code="APERMITS", seasonally_adjusted=True) -> CensusResconstRow:
    return CensusResconstRow(
        period=period,
        category_code=category_code,
        data_type_code="TOTAL",
        seasonally_adjusted=seasonally_adjusted,
        is_error_measure=False,
        value=value,
    )


def _sync(session, rows) -> None:
    HousingIngestionService(StubCensusClient(rows)).sync(session)


def _housing_objects(session):
    return [obj for obj in IntelligenceBuilder().build_all(session) if obj.world == "housing"]


class TestTheBackfillIsInvisible:
    """#43's rule at the one place it could be broken at scale."""

    def test_a_baseline_import_produces_no_intelligence_objects(self, db_session) -> None:
        _sync(db_session, [_row(date(2026, month, 1), 1400.0 + month) for month in range(1, 9)])

        assert _housing_objects(db_session) == []

    def test_a_large_baseline_import_still_produces_none(self, db_session) -> None:
        """Sixty-seven years of monthly history, which is what the real
        import is."""
        rows = [
            _row(date(1960 + (index // 12), (index % 12) + 1, 1), 1000.0 + index)
            for index in range(240)
        ]
        _sync(db_session, rows)

        assert _housing_objects(db_session) == []


class TestGenuinelyObservedArrivals:
    def test_a_new_month_arriving_later_produces_one_object(self, db_session) -> None:
        _sync(db_session, [_row(date(2026, 8, 1), 1394.0)])
        _sync(db_session, [_row(date(2026, 8, 1), 1394.0), _row(date(2026, 9, 1), 1410.0)])

        objects = _housing_objects(db_session)
        assert len(objects) == 1
        (obj,) = objects
        assert obj.effective_period == date(2026, 9, 1)
        assert obj.payload.change_type == "NEW"
        assert obj.payload.revision_knowledge == "FIRST_OBSERVATION"

    def test_the_object_reuses_the_existing_observation_change_type(self, db_session) -> None:
        """No `HOUSING_OBSERVATION` variant was invented: the semantics
        match exactly, and a type differing only by which table it came
        from would make the taxonomy describe plumbing."""
        _sync(db_session, [_row(date(2026, 8, 1), 1394.0)])
        _sync(db_session, [_row(date(2026, 9, 1), 1410.0)])

        (obj,) = _housing_objects(db_session)
        assert obj.type == "OBSERVATION_CHANGE"

    def test_the_object_is_a_source_fact_with_no_methodology(self, db_session) -> None:
        """Housing is the first world where this is true of every object:
        there IS no housing methodology, so there is no conclusion to
        attribute."""
        _sync(db_session, [_row(date(2026, 8, 1), 1394.0)])
        _sync(db_session, [_row(date(2026, 9, 1), 1410.0)])

        (obj,) = _housing_objects(db_session)
        assert obj.basis == "SOURCE_FACT"
        assert obj.methodology is None

    def test_knowledge_basis_is_observed_and_recorded_at_is_real(self, db_session) -> None:
        before = datetime.now(timezone.utc) - timedelta(seconds=5)
        _sync(db_session, [_row(date(2026, 8, 1), 1394.0)])
        _sync(db_session, [_row(date(2026, 9, 1), 1410.0)])
        after = datetime.now(timezone.utc) + timedelta(seconds=5)

        (obj,) = _housing_objects(db_session)
        assert obj.knowledge_basis == "OBSERVED"
        assert before <= obj.recorded_at <= after

    def test_no_publication_time_is_claimed(self, db_session) -> None:
        _sync(db_session, [_row(date(2026, 8, 1), 1394.0)])
        _sync(db_session, [_row(date(2026, 9, 1), 1410.0)])

        (obj,) = _housing_objects(db_session)
        assert obj.published_at is None

    def test_the_concept_is_source_neutral_and_the_evidence_names_census(self, db_session) -> None:
        _sync(db_session, [_row(date(2026, 8, 1), 1394.0)])
        _sync(db_session, [_row(date(2026, 9, 1), 1410.0)])

        (obj,) = _housing_objects(db_session)
        assert obj.concepts == [PERMITS_SAAR]
        (evidence,) = obj.evidence
        assert evidence.concept_id == PERMITS_SAAR
        assert evidence.provider == "CENSUS"
        # Census's OWN identifier, from stored provenance -- not
        # MacroChipz's concept id wearing a provider label.
        assert evidence.provider_series_id == "APERMITS/TOTAL"
        assert evidence.value == 1_410_000.0

    def test_the_relations_point_at_the_concept_and_the_world(self, db_session) -> None:
        _sync(db_session, [_row(date(2026, 8, 1), 1394.0)])
        _sync(db_session, [_row(date(2026, 9, 1), 1410.0)])

        (obj,) = _housing_objects(db_session)
        kinds = {(relation.kind, relation.target) for relation in obj.relations}
        assert ("CONCERNS_CONCEPT", PERMITS_SAAR) in kinds
        assert ("AFFECTS_WORLD", "housing") in kinds
        # No release relation: Housing has no calendar entry, and
        # inventing one would be a fabricated provenance.
        assert not any(relation.kind == "PART_OF_RELEASE" for relation in obj.relations)

    def test_the_identity_is_stable_across_reads(self, db_session) -> None:
        _sync(db_session, [_row(date(2026, 8, 1), 1394.0)])
        _sync(db_session, [_row(date(2026, 9, 1), 1410.0)])

        first = _housing_objects(db_session)[0].id
        second = _housing_objects(db_session)[0].id
        assert first == second
        assert first.startswith("observation:us.housing.")


class TestGenuineRevisions:
    """#45 section 15: representable without Housing-specific frontend
    logic, and proven before Census publishes one."""

    def test_an_observed_revision_produces_a_prospective_revision_object(self, db_session) -> None:
        _sync(db_session, [_row(date(2026, 8, 1), 1394.0)])  # baseline
        _sync(db_session, [_row(date(2026, 9, 1), 1410.0)])  # observed arrival
        _sync(db_session, [_row(date(2026, 9, 1), 1425.0)])  # observed revision

        revisions = [obj for obj in _housing_objects(db_session) if obj.payload.change_type == "REVISED"]
        assert len(revisions) == 1
        (revision,) = revisions
        assert revision.payload.revision_knowledge == "PROSPECTIVE_REVISION"
        assert revision.payload.previous_value == 1_410_000.0
        assert revision.payload.new_value == 1_425_000.0
        assert revision.payload.delta == 15_000.0
        assert revision.payload.original_value_known is True

    def test_a_revision_of_a_backfilled_baseline_is_not_a_prospective_revision(self, db_session) -> None:
        """The distinction the whole of #43 rests on. MacroChipz holds the
        earlier value, but it IMPORTED it -- so it cannot say that value
        was what Census originally published."""
        _sync(db_session, [_row(date(2026, 8, 1), 1394.0)])  # imported baseline
        _sync(db_session, [_row(date(2026, 8, 1), 1400.0)])  # Census revises it

        revisions = [obj for obj in _housing_objects(db_session) if obj.payload.change_type == "REVISED"]
        (revision,) = revisions
        assert revision.payload.revision_knowledge == "BACKFILLED_BASELINE"
        assert revision.payload.original_value_known is False
        assert any("imported" in item.lower() or "baseline" in item.lower() for item in revision.limitations)

    def test_the_existing_revision_selector_picks_it_up_with_no_housing_logic(self, db_session) -> None:
        """#43's selector is world-agnostic, which is the requirement: a
        Housing revision must need no Housing-specific frontend code. This
        applies the same two conditions the frontend applies."""
        _sync(db_session, [_row(date(2026, 8, 1), 1394.0)])
        _sync(db_session, [_row(date(2026, 9, 1), 1410.0)])
        _sync(db_session, [_row(date(2026, 9, 1), 1425.0)])

        genuine = [
            obj
            for obj in IntelligenceBuilder().build_all(db_session)
            if obj.type == "OBSERVATION_CHANGE"
            and obj.payload.change_type == "REVISED"
            and obj.payload.revision_knowledge == "PROSPECTIVE_REVISION"
        ]
        assert [obj.world for obj in genuine] == ["housing"]

    def test_an_unchanged_resync_produces_no_new_object(self, db_session) -> None:
        _sync(db_session, [_row(date(2026, 8, 1), 1394.0)])
        _sync(db_session, [_row(date(2026, 9, 1), 1410.0)])
        before = len(_housing_objects(db_session))

        _sync(db_session, [_row(date(2026, 9, 1), 1410.0)])

        assert len(_housing_objects(db_session)) == before


class TestSaarLabelling:
    def test_an_annual_rate_object_carries_the_saar_explanation(self, db_session) -> None:
        _sync(db_session, [_row(date(2026, 8, 1), 1394.0)])
        _sync(db_session, [_row(date(2026, 9, 1), 1410.0)])

        (obj,) = _housing_objects(db_session)
        joined = " ".join(obj.limitations).lower()
        assert "annual rate" in joined
        assert "not a count of homes" in joined

    def test_an_unadjusted_object_does_not_carry_it(self, db_session) -> None:
        """Attaching the annual-rate explanation to a plain monthly count
        would be its own confusion."""
        _sync(db_session, [_row(date(2026, 8, 1), 117.4, category_code="PERMITS", seasonally_adjusted=False)])
        _sync(db_session, [_row(date(2026, 9, 1), 120.0, category_code="PERMITS", seasonally_adjusted=False)])

        (obj,) = _housing_objects(db_session)
        assert obj.concepts == [PERMITS_NSA]
        assert not any("annual rate" in item.lower() for item in obj.limitations)

    def test_every_object_disclaims_a_housing_state(self, db_session) -> None:
        _sync(db_session, [_row(date(2026, 8, 1), 1394.0)])
        _sync(db_session, [_row(date(2026, 9, 1), 1410.0)])

        (obj,) = _housing_objects(db_session)
        assert any("no housing state" in item.lower() for item in obj.limitations)


class TestBounding:
    def test_the_object_count_is_capped(self, db_session) -> None:
        """A projection over an append-only table must be bounded, or the
        payload grows with the database."""
        _sync(db_session, [_row(date(2026, 1, 1), 1000.0)])
        # Sixty separately-observed arrivals, each its own sync.
        for index in range(60):
            month = (index % 12) + 1
            year = 2027 + (index // 12)
            _sync(db_session, [_row(date(year, month, 1), 1100.0 + index)])

        objects = _housing_objects(db_session)
        assert len(objects) <= IntelligenceBuilder.HOUSING_OBJECT_LIMIT

    def test_the_most_recently_recorded_arrivals_are_the_ones_kept(self, db_session) -> None:
        _sync(db_session, [_row(date(2026, 1, 1), 1000.0)])
        for month in range(2, 9):
            _sync(db_session, [_row(date(2026, month, 1), 1000.0 + month)])

        objects = _housing_objects(db_session)
        assert objects[0].effective_period == date(2026, 8, 1)


class TestOtherWorldsAreUnaffected:
    def test_adding_housing_does_not_change_other_worlds_objects(self, db_session) -> None:
        before = [obj.id for obj in IntelligenceBuilder().build_all(db_session) if obj.world != "housing"]

        _sync(db_session, [_row(date(2026, 8, 1), 1394.0)])
        _sync(db_session, [_row(date(2026, 9, 1), 1410.0)])

        after = [obj.id for obj in IntelligenceBuilder().build_all(db_session) if obj.world != "housing"]
        assert before == after

    def test_ordering_remains_deterministic_with_housing_present(self, db_session) -> None:
        _sync(db_session, [_row(date(2026, 8, 1), 1394.0)])
        _sync(db_session, [_row(date(2026, 9, 1), 1410.0)])

        first = [obj.id for obj in IntelligenceBuilder().build_all(db_session)]
        second = [obj.id for obj in IntelligenceBuilder().build_all(db_session)]
        assert first == second

    def test_the_world_filter_selects_housing(self, db_session) -> None:
        from app.services.intelligence.service import IntelligenceService

        _sync(db_session, [_row(date(2026, 8, 1), 1394.0)])
        _sync(db_session, [_row(date(2026, 9, 1), 1410.0)])

        response = IntelligenceService().list_intelligence(db_session, world="housing")
        assert response.total == 1
        assert response.items[0].world == "housing"
