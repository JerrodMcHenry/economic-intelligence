"""Contract and identity guarantees for Structured Intelligence
(Increment #39).

Pure unit tests -- no database, no session. Everything here is about
what the contract permits and what the identity scheme promises.
"""

from datetime import date, datetime, timezone

import pytest

from app.models.intelligence import (
    AnalysisChangeIntelligence,
    AnalysisChangePayload,
    EvidenceRef,
    MethodologyRef,
    ObservationChangeIntelligence,
    ObservationChangePayload,
    ReleaseProcessedIntelligence,
    ReleaseProcessedPayload,
)
from app.services.intelligence.identity import (
    IntelligenceIdentityError,
    analysis_change_id,
    observation_change_id,
    rates_movement_id,
    release_processed_id,
)

PERIOD = date(2026, 8, 1)
DETECTED = datetime(2026, 9, 19, 18, 46, 27, 419986, tzinfo=timezone.utc)


class TestStableIdentity:
    def test_ids_are_deterministic(self) -> None:
        assert release_processed_id("FRED", "10", PERIOD) == release_processed_id("FRED", "10", PERIOD)
        assert observation_change_id("c", PERIOD, DETECTED) == observation_change_id("c", PERIOD, DETECTED)

    def test_ids_are_readable_and_prefixed_by_type(self) -> None:
        assert release_processed_id("FRED", "10", PERIOD).startswith("release:")
        assert observation_change_id("c", PERIOD, DETECTED).startswith("observation:")
        assert analysis_change_id("m", "C", "f", PERIOD, "E").startswith("analysis:")
        assert rates_movement_id("UST_NOMINAL_10Y", PERIOD).startswith("rates:")

    def test_a_timestamp_dimension_is_encoded_without_the_separator(self) -> None:
        """ISO-8601 contains colons, which are this format's separator.
        The compact encoding exists so the guard below never has to
        fire in production."""
        identifier = observation_change_id("c", PERIOD, DETECTED)
        assert identifier.count(":") == 3
        assert "20260919T184627419986Z" in identifier

    def test_a_dimension_containing_the_separator_is_rejected(self) -> None:
        with pytest.raises(IntelligenceIdentityError):
            release_processed_id("FRED", "10:extra", PERIOD)

    def test_an_empty_or_missing_dimension_is_rejected(self) -> None:
        with pytest.raises(IntelligenceIdentityError):
            release_processed_id("", "10", PERIOD)
        with pytest.raises(IntelligenceIdentityError):
            rates_movement_id("UST_NOMINAL_10Y", None)  # type: ignore[arg-type]

    def test_differing_dimensions_produce_differing_ids(self) -> None:
        """Collision resistance across every identity dimension of each
        variant."""
        base = analysis_change_id("labor_v1.0", "EMPLOYMENT", "state", PERIOD, "STATE_CHANGED")
        variants = {
            base,
            analysis_change_id("inflation_v1.0", "EMPLOYMENT", "state", PERIOD, "STATE_CHANGED"),
            analysis_change_id("labor_v1.0", "UNEMPLOYMENT", "state", PERIOD, "STATE_CHANGED"),
            analysis_change_id("labor_v1.0", "EMPLOYMENT", "momentum", PERIOD, "STATE_CHANGED"),
            analysis_change_id("labor_v1.0", "EMPLOYMENT", "state", date(2026, 7, 1), "STATE_CHANGED"),
            analysis_change_id("labor_v1.0", "EMPLOYMENT", "state", PERIOD, "AVAILABILITY_RESTORED"),
        }
        assert len(variants) == 6

    def test_a_methodology_change_mints_a_new_conclusion_id(self) -> None:
        """A conclusion reached under a different methodology is a
        different conclusion, so it gets a different identity."""
        assert analysis_change_id("labor_v1.0", "C", "f", PERIOD, "E") != analysis_change_id(
            "labor_v2.0", "C", "f", PERIOD, "E"
        )

    def test_identity_is_keyed_on_concept_not_provider(self) -> None:
        """A provider migration must not change what an object IS
        (#38). The id carries the concept, so it survives the source
        moving from FRED to BLS."""
        assert observation_change_id("us.nonfarm.payroll-employment.sa.monthly", PERIOD, DETECTED) == (
            observation_change_id("us.nonfarm.payroll-employment.sa.monthly", PERIOD, DETECTED)
        )
        assert "PAYEMS" not in observation_change_id("us.nonfarm.payroll-employment.sa.monthly", PERIOD, DETECTED)


def _release(**overrides: object) -> ReleaseProcessedIntelligence:
    defaults = dict(
        id="release:FRED:10:2026-09-11",
        world="inflation",
        concepts=["us.cpi.core.price-index.sa.monthly"],
        effective_period=PERIOD,
        recorded_at=DETECTED,
        knowledge_basis="OBSERVED",
        basis="SOURCE_FACT",
        payload=ReleaseProcessedPayload(
            release_name="Consumer Price Index",
            provider="FRED",
            provider_release_id="10",
            scheduled_date=PERIOD,
            status="CHANGED",
            observation_changes=2,
            new_observations=2,
            revised_observations=0,
        ),
    )
    defaults.update(overrides)
    return ReleaseProcessedIntelligence(**defaults)  # type: ignore[arg-type]


class TestSourceFactVersusMethodologyDerived:
    def test_a_source_fact_carries_no_methodology(self) -> None:
        """A release arriving is not a conclusion about the economy.
        Stamping a methodology id here would claim one was reached."""
        obj = _release()
        assert obj.basis == "SOURCE_FACT"
        assert obj.methodology is None

    def test_a_methodology_derived_object_carries_its_version(self) -> None:
        obj = AnalysisChangeIntelligence(
            id="analysis:labor_v1.0:EMPLOYMENT:state:2026-08-01:STATE_CHANGED",
            world="jobs",
            concepts=["us.nonfarm.payroll-employment.sa.monthly"],
            effective_period=PERIOD,
            recorded_at=DETECTED,
            knowledge_basis="OBSERVED",
            basis="METHODOLOGY_DERIVED",
            methodology=MethodologyRef(methodology_id="labor_v1.0", data_basis="latest_revised_data"),
            payload=AnalysisChangePayload(
                component="EMPLOYMENT",
                event_type="STATE_CHANGED",
                change_class="ECONOMIC",
                field="state",
                previous_value="STABLE",
                current_value="EXPANDING",
                delta=None,
                evaluation_period=PERIOD,
            ),
        )
        assert obj.methodology is not None
        assert obj.methodology.methodology_id == "labor_v1.0"
        assert obj.payload.change_class == "ECONOMIC"


class TestHonestAbsence:
    def test_a_new_observation_has_no_previous_value_and_no_delta(self) -> None:
        """A first observation is not a revision. `None` rather than a
        fabricated zero, and no delta against a substituted default."""
        payload = ObservationChangePayload(
            change_type="NEW",
            previous_value=None,
            new_value=161.5,
            delta=None,
            observation_date=PERIOD,
            provider="FRED",
            provider_series_id="PAYEMS",
            series_title="All Employees, Total Nonfarm",
            units="Thousands of Persons",
        )
        assert payload.previous_value is None
        assert payload.delta is None

    def test_a_revision_carries_both_values_and_a_real_delta(self) -> None:
        """The representation Increment #43 will need: previously
        recorded value, current value, magnitude and direction."""
        payload = ObservationChangePayload(
            change_type="REVISED",
            previous_value=159_000.0,
            new_value=158_000.0,
            delta=-1000.0,
            observation_date=PERIOD,
            provider="FRED",
            provider_series_id="PAYEMS",
            series_title="All Employees, Total Nonfarm",
            units="Thousands of Persons",
        )
        assert payload.change_type == "REVISED"
        assert payload.delta == -1000.0
        assert payload.delta < 0  # direction is readable from the magnitude

    def test_published_at_defaults_to_none_rather_than_a_substitute(self) -> None:
        """This project's calendar gives a scheduled DATE, and a release
        date is not proof of publication. `None` is the honest answer;
        `created_at` must never stand in for it."""
        assert _release().published_at is None

    def test_knowledge_basis_is_explicit_and_required(self) -> None:
        with pytest.raises(Exception):
            ReleaseProcessedIntelligence(  # type: ignore[call-arg]
                id="release:FRED:10:2026-09-11",
                world="inflation",
                concepts=[],
                effective_period=PERIOD,
                recorded_at=DETECTED,
                basis="SOURCE_FACT",
                payload=_release().payload,
            )

    def test_backfilled_is_representable_and_distinct(self) -> None:
        assert _release(knowledge_basis="BACKFILLED").knowledge_basis == "BACKFILLED"
        assert _release().knowledge_basis == "OBSERVED"


class TestEvidenceCarriesIdentity:
    def test_evidence_keeps_concept_and_actual_provider(self) -> None:
        """#38's identity triple, unchanged: what it is, who supplied
        it, and their own identifier for it."""
        ref = EvidenceRef(
            concept_id="us.nonfarm.payroll-employment.sa.monthly",
            provider="FRED",
            provider_series_id="PAYEMS",
            observation_date=PERIOD,
            value=158_000.0,
        )
        assert ref.concept_id != ref.provider_series_id
        assert ref.provider == "FRED"


class TestSerialization:
    def test_serialization_is_stable_and_leaks_no_implementation(self) -> None:
        dumped = _release().model_dump(mode="json")
        assert dumped["type"] == "RELEASE_PROCESSED"
        assert dumped["contract_version"] == "intelligence_v1"
        # Two dumps of the same object are byte-identical.
        assert dumped == _release().model_dump(mode="json")
        for key in dumped:
            assert not key.startswith("_")

    def test_limitations_are_part_of_the_contract(self) -> None:
        assert "limitations" in _release().model_dump(mode="json")
