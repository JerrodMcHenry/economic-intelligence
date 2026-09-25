"""Architectural guards for the economic concept identity boundary
(Increment #38, ADR-034).

The boundary these protect:

    CANONICAL METHODOLOGY -> ECONOMIC CONCEPT -> PROVIDER BINDING -> FRED / TREASURY / ...

Before #38 that boundary did not exist. `PAYEMS` -- a FRED identifier --
was MacroChipz's canonical identity for total nonfarm employment, and
because `Observation` carries only a date and a value, evidence was
stamped from a module-level constant. A provider migration would have
left evidence naming FRED for numbers FRED no longer supplied.

These are structural tests (AST imports, registry consistency, model
field inspection), not text searches over prose, following the same
discipline as `test_domain_architectural_independence.py`.
"""

import ast
from pathlib import Path

import pytest

from app.concepts.bindings import (
    BINDINGS,
    AmbiguousBindingError,
    UnknownBindingError,
    active_binding,
    bindings_for_concept,
    concept_id_for_stored_series,
)
from app.concepts.registry import CONCEPTS, UnknownConceptError, concept
from app.models.inflation import InflationMetricEvidence, SeriesMomentumResult
from app.models.labor import LaborObservationEvidence
from app.models.series import SeriesIdentity

#: Every provider-shaped identifier that used to be a canonical identity.
#: A canonical methodology module naming one of these as a literal is the
#: exact regression #38 exists to prevent.
PROVIDER_SERIES_LITERALS = frozenset(
    {"PAYEMS", "UNRATE", "PCEPILFE", "CPILFESL", "PCEPI", "CPIAUCSL"}
)

DOMAIN_DIR = Path("app/domain")


def _string_literals(path: Path) -> set[str]:
    """Every string constant in a module, without executing it."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}


class TestInvariantA:
    """Canonical methodology code depends on concept identity, not
    provider-specific series identity."""

    def test_no_domain_module_contains_a_provider_series_literal(self) -> None:
        offenders: list[str] = []
        for path in sorted(DOMAIN_DIR.glob("*.py")):
            leaked = _string_literals(path) & PROVIDER_SERIES_LITERALS
            if leaked:
                offenders.append(f"{path}: {sorted(leaked)}")

        # `app/domain/labor_release_processing.py` carried
        # `PAYEMS_SERIES_ID = "PAYEMS"` and `UNRATE_SERIES_ID = "UNRATE"`,
        # duplicated from app.models.labor "by convention" with nothing
        # keeping the two in agreement. This is the guard that would
        # have caught it.
        assert offenders == [], (
            "Provider-shaped series identifiers found as literals in the pure domain layer. "
            "Canonical methodologies must name CONCEPTS; the provider identifier belongs below "
            "the binding boundary (app/concepts/bindings.py). Offenders: " + "; ".join(offenders)
        )

    def test_no_domain_module_imports_a_provider_client(self) -> None:
        offenders: list[str] = []
        for path in sorted(DOMAIN_DIR.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                module = None
                if isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                elif isinstance(node, ast.Import):
                    module = ",".join(alias.name for alias in node.names)
                if module and ("clients" in module or "concepts.bindings" in module):
                    offenders.append(f"{path}: {module}")

        assert offenders == [], (
            "The pure domain layer must not reach a provider client or the binding table directly. "
            "Offenders: " + "; ".join(offenders)
        )


class TestInvariantBSemanticEquivalence:
    """Bindings represent verified semantic equivalence, not label
    similarity."""

    def test_every_binding_names_a_registered_concept(self) -> None:
        for binding in BINDINGS:
            assert binding.concept_id in CONCEPTS, binding.concept_id

    def test_every_concept_has_exactly_one_active_binding(self) -> None:
        for concept_id in CONCEPTS:
            binding = active_binding(concept_id)
            assert binding.concept_id == concept_id

    def test_every_binding_justifies_its_equivalence_claim(self) -> None:
        # "The names match" is not a justification. Each basis cites the
        # frozen methodology that already uses that series for that role.
        for binding in BINDINGS:
            assert len(binding.equivalence_basis) > 40, binding.concept_id

    def test_concepts_record_the_dimensions_that_prevent_substitution(self) -> None:
        for concept_obj in CONCEPTS.values():
            for field in ("frequency", "canonical_unit", "seasonal_adjustment", "geography", "universe", "source_program"):
                assert getattr(concept_obj, field), f"{concept_obj.concept_id}.{field}"

    def test_employment_and_unemployment_are_different_universes(self) -> None:
        """CES counts JOBS; CPS counts PEOPLE. A registry that cannot
        express this would eventually be used to assert something
        false -- and #35's Radar research found that conflating the two
        is exactly what makes a cross-survey 'divergence' an artifact."""
        employment = concept("us.nonfarm.payroll-employment.sa.monthly")
        unemployment = concept("us.unemployment-rate.sa.monthly")
        assert employment.universe != unemployment.universe
        assert employment.source_program == "CES"
        assert unemployment.source_program == "CPS"

    def test_unit_conversion_belongs_to_the_binding_not_the_concept(self) -> None:
        """A different provider may publish the same concept in
        different units, so the conversion is a property of where the
        value came from."""
        binding = active_binding("us.nonfarm.payroll-employment.sa.monthly")
        assert binding.provider_native_unit == "Thousands of Persons"
        assert binding.canonical_unit_factor == 1000.0
        assert concept(binding.concept_id).canonical_unit == "JOBS"


class TestInvariantCEvidenceCarriesBothIdentities:
    def test_inflation_evidence_carries_concept_provider_and_series(self) -> None:
        fields = set(InflationMetricEvidence.model_fields)
        assert {"concept_id", "provider", "series_id"} <= fields

    def test_labor_evidence_carries_concept_provider_and_series(self) -> None:
        fields = set(LaborObservationEvidence.model_fields)
        assert {"concept_id", "provider", "series_id"} <= fields

    def test_momentum_result_distinguishes_concept_from_stored_series(self) -> None:
        fields = set(SeriesMomentumResult.model_fields)
        assert {"concept_id", "series_id"} <= fields

    def test_series_identity_carries_all_three(self) -> None:
        fields = set(SeriesIdentity.model_fields)
        assert fields == {"concept_id", "provider", "provider_series_id"}


class TestInvariantEDualBindings:
    """A concept may hold more than one binding so a migration can be
    verified before cutover."""

    def test_bindings_for_concept_returns_every_binding(self) -> None:
        for concept_id in CONCEPTS:
            all_bindings = bindings_for_concept(concept_id)
            assert len(all_bindings) >= 1
            assert sum(1 for b in all_bindings if b.active) == 1

    def test_the_dual_binding_resolves_to_the_agency_and_keeps_fred_inactive(self) -> None:
        """The dual-binding shape ADR-034 designed, after #56B flipped it:
        two bindings for one concept, exactly one active -- now BLS -- and
        FRED kept, inactive, on its own row so its history stays FRED's."""
        concept_id = "us.nonfarm.payroll-employment.sa.monthly"
        pair = bindings_for_concept(concept_id)

        assert sorted((b.provider, b.active) for b in pair) == [("BLS", True), ("FRED", False)]
        assert active_binding(concept_id).provider == "BLS"
        assert active_binding(concept_id).storage_series_id == concept_id
        # Separate rows, so FRED history is never relabelled.
        assert {b.storage_series_id for b in pair} == {"PAYEMS", concept_id}

    def test_every_inflation_and_jobs_concept_resolves_to_bls_or_bea_never_fred(self) -> None:
        """#56B's first requirement, for all six at once."""
        first_party = [b for b in BINDINGS if b.provider in {"BLS", "BEA"}]
        assert len(first_party) == 6
        for binding in first_party:
            resolved = active_binding(binding.concept_id)
            assert resolved == binding
            assert resolved.storage_series_id == binding.concept_id
            fred = [b for b in bindings_for_concept(binding.concept_id) if b.provider == "FRED"]
            assert len(fred) == 1 and not fred[0].active
            # Native units and factors identical to FRED's, so the
            # methodologies cannot tell the two rows apart.
            assert binding.provider_native_unit == fred[0].provider_native_unit
            assert binding.canonical_unit_factor == fred[0].canonical_unit_factor
        assert not any(b.active for b in BINDINGS if b.provider == "FRED")


class TestAmbiguityCannotSilentlySucceed:
    def test_unregistered_concept_raises(self) -> None:
        with pytest.raises(UnknownConceptError):
            concept("us.not-a-real-concept.monthly")

    def test_unregistered_concept_binding_raises(self) -> None:
        with pytest.raises(UnknownConceptError):
            active_binding("us.not-a-real-concept.monthly")

    def test_unmapped_stored_series_raises_rather_than_guessing(self) -> None:
        """An arbitrary provider series synced through the generic
        endpoint has no concept, and inferring one from a label is
        exactly what ADR-034 forbids."""
        with pytest.raises(UnknownBindingError):
            concept_id_for_stored_series("SOME_ARBITRARY_FRED_SERIES")

    def test_a_doubly_claimed_stored_series_raises(self) -> None:
        from dataclasses import replace

        import app.concepts.bindings as bindings_module

        duplicate = replace(BINDINGS[0], concept_id="us.cpi.core.price-index.sa.monthly")
        original = bindings_module.BINDINGS
        bindings_module.BINDINGS = (*original, duplicate)
        try:
            with pytest.raises(AmbiguousBindingError):
                concept_id_for_stored_series(BINDINGS[0].storage_series_id)
        finally:
            bindings_module.BINDINGS = original


class TestBackfillIsDeterministic:
    def test_every_stored_series_maps_to_exactly_one_concept(self) -> None:
        """The backfill's own rule, asserted independently of the
        migration: each stored identifier resolves to one concept, or
        raises."""
        seen: dict[str, str] = {}
        for binding in BINDINGS:
            concept_id = concept_id_for_stored_series(binding.storage_series_id)
            assert concept_id == binding.concept_id
            assert binding.storage_series_id not in seen
            seen[binding.storage_series_id] = concept_id
        assert len(seen) == len(BINDINGS)
