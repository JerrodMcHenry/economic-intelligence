"""Architectural guards for the Housing world (Increment #45).

Structural tests -- AST inspection, import-graph inspection, registry
consistency -- following the discipline of
`tests/test_rates_architecture.py` and
`tests/test_concept_identity_boundary.py` rather than grepping prose.

WHAT THESE PROTECT, in the order the increment cared about:

1. **Housing has no state.** No state vocabulary, no score, no weights,
   no composite index, no significance ranking. This is the invariant
   most likely to erode, because "Housing: Cooling" is a genuinely
   tempting thing to add and nothing but a test stops it.
2. **The Census credential never leaves its boundary.** Not into a log,
   not into a response model, not into provenance, not into the database.
3. **A read can never fetch.** The read path holds no provider client
   anywhere in its import graph.
4. **A Treasury yield is never presented as mortgage data.**
5. **Concept identity holds.** Census codes stay in bindings; canonical
   code names concepts.

A NOTE ON HOW THE STATE-VOCABULARY SCAN WORKS, because the obvious
implementation is wrong. Scanning for the word "Cooling" anywhere in the
Housing modules would flag the very docstrings that explain why Housing
has no Cooling state -- the same false positive
`no-economic-logic.test.ts` documents for "bullish"/"bearish". So the
scan looks at NON-DOCSTRING string constants and at DECLARED NAMES,
which is where a state would actually have to live in order to be
returned to anyone.
"""

import ast
from pathlib import Path

import pytest

from app.concepts.bindings import BINDINGS, active_binding
from app.concepts.registry import CONCEPTS, concept
from app.models.housing import (
    HOUSING_CONCEPT_IDS,
    PIPELINE_STAGES,
    PROVIDER,
    PROVIDER_ATTRIBUTION,
    STAGE_CONCEPTS,
    HousingMeasure,
    HousingResult,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Every backend module that is part of Housing.
HOUSING_MODULES: tuple[Path, ...] = (
    Path("app/models/housing.py"),
    Path("app/domain/housing.py"),
    Path("app/services/housing.py"),
    Path("app/services/census_ingestion.py"),
    Path("app/repositories/housing_repository.py"),
    Path("app/api/housing.py"),
    Path("app/clients/census.py"),
)

#: State vocabulary #45 explicitly forbids for Housing, plus the
#: composite-measure words that would smuggle one in.
FORBIDDEN_STATE_WORDS: frozenset[str] = frozenset(
    {
        "strong",
        "weak",
        "cooling",
        "heating",
        "improving",
        "worsening",
        "healthy",
        "unhealthy",
        "expanding",
        "contracting",
        "overheated",
        "booming",
        "slumping",
    }
)

#: Identifier fragments that would mean a score, a ranking or a weighting
#: exists. `#39` publishes no significance score and `#45` adds none.
FORBIDDEN_SCORE_FRAGMENTS: tuple[str, ...] = (
    "score",
    "weight",
    "severity",
    "importance",
    "significance",
    "composite",
    "index_value",
    "rank",
)


def _module_source(relative: Path) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


def _tree(relative: Path) -> ast.Module:
    return ast.parse(_module_source(relative))


def _docstring_nodes(tree: ast.Module) -> set[int]:
    """Every string-constant node that is a docstring, by object id.

    Docstrings are `ast.Constant` strings like any other, so a scan that
    does not exclude them cannot tell a forbidden state label apart from
    a sentence explaining that no such label exists.
    """
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                ids.add(id(body[0].value))
    return ids


def _non_docstring_strings(relative: Path) -> list[str]:
    tree = _tree(relative)
    skip = _docstring_nodes(tree)
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip
    ]


def _declared_names(relative: Path) -> list[str]:
    """Names this module DEFINES: classes, functions, assignment targets,
    annotated assignments, and Pydantic/dataclass field names."""
    names: list[str] = []
    for node in ast.walk(_tree(relative)):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.append(node.name)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.append(node.target.id)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.append(target.id)
        elif isinstance(node, ast.arg):
            names.append(node.arg)
    return names


class TestNoHousingState:
    """#45 section 4: there is no approved `housing_v1.0`, so Housing must
    not acquire a state by accident."""

    @pytest.mark.parametrize("relative", HOUSING_MODULES, ids=lambda path: str(path))
    def test_no_module_declares_a_state_vocabulary(self, relative: Path) -> None:
        offenders = [
            name for name in _declared_names(relative) if name.lower().strip("_") in FORBIDDEN_STATE_WORDS
        ]
        assert offenders == [], f"{relative} declares Housing state name(s): {offenders}"

    @pytest.mark.parametrize("relative", HOUSING_MODULES, ids=lambda path: str(path))
    def test_no_module_contains_a_state_label_as_a_value(self, relative: Path) -> None:
        """A state would have to be a string constant somewhere in order
        to be returned. Docstrings are excluded, so the modules remain
        free to EXPLAIN that no state exists."""
        offenders = [
            text
            for text in _non_docstring_strings(relative)
            if text.strip().lower() in FORBIDDEN_STATE_WORDS
        ]
        assert offenders == [], f"{relative} contains Housing state label(s) as values: {offenders}"

    @pytest.mark.parametrize("relative", HOUSING_MODULES, ids=lambda path: str(path))
    def test_no_module_declares_a_score_weight_or_ranking(self, relative: Path) -> None:
        offenders = [
            name
            for name in _declared_names(relative)
            if any(fragment in name.lower() for fragment in FORBIDDEN_SCORE_FRAGMENTS)
        ]
        assert offenders == [], f"{relative} declares a score/weight/ranking name: {offenders}"

    def test_the_housing_result_contract_has_no_state_field(self) -> None:
        """The response contract is the surface a frontend could render a
        state from. If the field does not exist, no surface can invent
        one from canonical data."""
        fields = set(HousingResult.model_fields) | set(HousingMeasure.model_fields)
        forbidden = {"state", "condition", "rating", "direction", "label", "verdict", "assessment", "outlook"}
        assert fields & forbidden == set()

    def test_the_housing_result_contract_declares_no_methodology(self) -> None:
        """Every other world's result carries a `methodology_id` because a
        frozen methodology produced it. Housing's must not, because none
        did -- and stamping one there would claim a conclusion was
        reached."""
        assert "methodology_id" not in HousingResult.model_fields

    def test_no_housing_methodology_constant_exists(self) -> None:
        import app.models.housing as housing_models

        assert not hasattr(housing_models, "METHODOLOGY_ID")

    def test_no_housing_methodology_document_exists(self) -> None:
        """The five prerequisites for a legitimate Housing state are
        recorded in the 2.0 implementation sequence. Until they are met, a
        `docs/methodology/housing-*.md` existing at all would mean one was
        written without them."""
        methodology_dir = REPO_ROOT / "docs" / "methodology"
        assert list(methodology_dir.glob("housing*")) == []

    def test_the_intelligence_world_union_gained_housing_without_a_methodology_mapping(self) -> None:
        """Housing joined #39's `World` union, but it must NOT appear in
        the methodology->world map: nothing concludes anything about
        Housing, so no methodology can own it."""
        from app.models.intelligence import World
        from app.services.intelligence.builder import _WORLD_BY_METHODOLOGY

        assert "housing" in World.__args__
        assert "housing" not in _WORLD_BY_METHODOLOGY.values()


class TestNoProbabilisticOrGenerativeDependency:
    """#45 section 18: no raw Census-to-model path, and no Housing surface
    that needs a language model to be correct."""

    @pytest.mark.parametrize("relative", HOUSING_MODULES, ids=lambda path: str(path))
    def test_no_housing_module_imports_a_model_sdk(self, relative: Path) -> None:
        imported = _imported_modules(relative)
        forbidden = {"openai", "anthropic", "transformers", "torch", "numpy", "scipy", "sklearn", "random"}
        assert imported & forbidden == set(), f"{relative} imports {imported & forbidden}"

    def test_the_analyst_context_has_no_housing_type(self) -> None:
        """Housing questions remain unsupported until a canonical Housing
        Analyst context exists. Widening the bounded Analyst simply
        because a world appeared is exactly what #45 forbids."""
        from app.models.analyst import AnalystContextType

        assert "HOUSING" not in AnalystContextType.__args__

    def test_the_analyst_context_builder_does_not_read_housing(self) -> None:
        source = _module_source(Path("app/services/analyst_context.py"))
        assert "housing" not in source.lower()


class TestReadPathCannotFetch:
    """#45 section 6 and the `/housing` requirement that no read triggers
    provider traffic. Enforced through the import graph, not convention."""

    def test_the_read_service_module_never_imports_the_census_client(self) -> None:
        imported = _imported_names(Path("app/services/housing.py"))
        assert not any("census" in name.lower() for name in imported)

    def test_the_read_service_takes_no_client_parameter_anywhere(self) -> None:
        """A shared class with an optional `census_client=None` would
        enforce this by convention only. `HousingReadService` has no
        client-shaped parameter for a future edit to wire one into."""
        tree = _tree(Path("app/services/housing.py"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "HousingReadService":
                for item in ast.walk(node):
                    if isinstance(item, ast.arg):
                        assert "client" not in item.arg.lower()
                        assert "census" not in item.arg.lower()

    def test_the_read_service_class_has_no_client_attribute(self) -> None:
        from app.services.housing import HousingReadService

        service = HousingReadService()
        assert not [name for name in vars(service) if "client" in name.lower()]

    def test_the_domain_module_imports_nothing_that_can_do_io(self) -> None:
        imported = _imported_modules(Path("app/domain/housing.py"))
        forbidden = {"httpx", "requests", "sqlalchemy", "app.db", "app.clients", "app.repositories"}
        assert imported & forbidden == set()

    def test_the_domain_module_reads_no_clock(self) -> None:
        """A pure function that reads the clock is not reproducible, and a
        comparison that silently depends on "today" cannot be checked by
        hand."""
        source = _module_source(Path("app/domain/housing.py"))
        for forbidden in ("datetime.now", "date.today", "time.time", "utcnow"):
            assert forbidden not in source


class TestCredentialContainment:
    """#45's hard rule. The client's own tests cover its behaviour; these
    cover the SURROUNDING code, which is where a credential actually gets
    leaked -- into a response, a log field, or a database column."""

    def test_no_response_model_has_a_credential_shaped_field(self) -> None:
        from app.models.housing import HousingSyncResponse, HousingSyncSeriesOutcome

        for model in (HousingResult, HousingMeasure, HousingSyncResponse, HousingSyncSeriesOutcome):
            for name in model.model_fields:
                assert not any(
                    fragment in name.lower() for fragment in ("key", "secret", "token", "credential", "api_key")
                ), f"{model.__name__}.{name} looks credential-shaped"

    def test_the_ingestion_run_table_has_no_credential_shaped_column(self) -> None:
        from app.db.models import HousingIngestionRun

        for column in HousingIngestionRun.__table__.columns:
            assert not any(
                fragment in column.name.lower() for fragment in ("key", "secret", "token", "credential")
            )

    def test_no_housing_module_logs_the_configured_key(self) -> None:
        """`settings.census_api_key` may be READ only where a client is
        constructed. Anywhere else -- and especially inside a log call --
        is a leak."""
        for relative in HOUSING_MODULES:
            source = _module_source(relative)
            if "census_api_key" not in source:
                continue
            assert relative == Path("app/api/housing.py"), (
                f"{relative} reads the configured credential; only the route that constructs "
                f"the client may do that"
            )
            # And in that one module, never inside a logging call.
            for line in source.splitlines():
                if "census_api_key" in line:
                    assert "log" not in line.lower()

    def test_the_stored_source_url_is_not_an_api_url(self) -> None:
        """A Census API URL carries the key, so persisting one would write
        a secret into `observation_provenance`."""
        from app.models.housing import SOURCE_URL

        assert "api.census.gov" not in SOURCE_URL
        assert "key=" not in SOURCE_URL

    def test_the_ingestion_service_logs_only_an_allow_listed_set_of_fields(self) -> None:
        """Inspected as AST, not grepped.

        A grep cannot tell `source_url=SOURCE_URL` -- the public program
        page, which legitimately belongs in provenance -- from a URL being
        written into a log line. So this reads every `logger.*(extra=...)`
        dict in the ingestion service and requires each KEY to be on an
        allow-list of counts, statuses and constants. A new field has to
        be added here deliberately, which is the point.
        """
        allowed = {
            "provider",
            "dataset",
            "status",
            "import_mode",
            "duration_ms",
            "rows_received",
            "rows_rejected",
            "observations_inserted",
            "observations_revised",
            "error_class",
        }
        found: set[str] = set()
        for node in ast.walk(_tree(Path("app/services/census_ingestion.py"))):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if keyword.arg != "extra":
                    continue
                assert isinstance(keyword.value, ast.Dict), "extra must be a literal dict, not assembled"
                for key in keyword.value.keys:
                    assert isinstance(key, ast.Constant) and isinstance(key.value, str)
                    found.add(key.value)

        assert found, "no logging extra fields found -- the scan is misconfigured"
        assert found <= allowed, f"unexpected log field(s): {sorted(found - allowed)}"

    def test_the_ingestion_service_never_touches_a_request_or_a_credential(self) -> None:
        """The narrow grep the AST test above does not cover: names that
        could only appear if request-level detail had reached this layer."""
        source = _module_source(Path("app/services/census_ingestion.py"))
        for forbidden in ("api_key", "response.text", "request.url", "httpx"):
            assert forbidden not in source, f"census_ingestion.py references {forbidden!r}"


class TestConceptIdentity:
    """#45 section 5 / #38: Census identifiers belong in bindings and
    provenance, never in canonical code."""

    def test_every_housing_concept_is_registered_in_the_housing_world(self) -> None:
        for concept_id in HOUSING_CONCEPT_IDS:
            assert concept(concept_id).world == "housing"

    def test_every_housing_concept_has_exactly_one_active_census_binding(self) -> None:
        for concept_id in HOUSING_CONCEPT_IDS:
            binding = active_binding(concept_id)
            assert binding.provider == "CENSUS"
            assert len([b for b in BINDINGS if b.concept_id == concept_id and b.active]) == 1

    def test_no_census_category_code_appears_in_a_domain_module(self) -> None:
        """The exact regression #38 exists to prevent, in Census's
        vocabulary: `APERMITS` is a provider identifier and canonical
        methodology code must never name one."""
        codes = {"APERMITS", "ASTARTS", "ACOMPLETIONS", "PERMITS", "STARTS", "COMPLETIONS", "RESCONST"}
        for path in sorted((REPO_ROOT / "app" / "domain").glob("*.py")):
            leaked = {
                text for text in _non_docstring_strings(path.relative_to(REPO_ROOT)) if text in codes
            }
            assert leaked == set(), f"{path.name} contains provider code literal(s): {leaked}"

    def test_the_stage_map_names_concepts_not_census_codes(self) -> None:
        for stage in PIPELINE_STAGES:
            for concept_id in STAGE_CONCEPTS[stage]:
                assert concept_id in CONCEPTS
                assert concept_id.startswith("us.housing.")

    def test_provider_codes_live_only_in_the_bindings_module(self) -> None:
        """`app/models/housing.py` declares the pipeline and its concepts.
        The Census codes that satisfy them are in `bindings.py`, so a
        provider migration touches one file."""
        strings = _non_docstring_strings(Path("app/models/housing.py"))
        assert "APERMITS" not in strings
        assert "APERMITS/TOTAL" not in strings

    def test_the_seasonal_adjustment_distinction_is_a_registry_fact(self) -> None:
        """Mixing adjusted and unadjusted series is the classic silent
        error. Each stage's two concepts must genuinely disagree on
        `seasonal_adjustment` and on `canonical_unit`."""
        for stage in PIPELINE_STAGES:
            pace_id, actual_id = STAGE_CONCEPTS[stage]
            pace, actual = concept(pace_id), concept(actual_id)
            assert pace.seasonal_adjustment == "SEASONALLY_ADJUSTED"
            assert actual.seasonal_adjustment == "NOT_SEASONALLY_ADJUSTED"
            assert pace.canonical_unit == "HOUSING_UNITS_ANNUAL_RATE"
            assert actual.canonical_unit == "HOUSING_UNITS"
            # Same economic universe, different construction. That is
            # exactly why they are two concepts rather than one.
            assert pace.universe == actual.universe

    def test_permits_and_construction_come_from_different_source_programs(self) -> None:
        """Census: permits are from a non-probability sample not subject
        to sampling error; starts and completions are sample estimates.
        Two reliability regimes, so two programs."""
        permits_pace, permits_actual = STAGE_CONCEPTS["PERMITS"]
        starts_pace, _ = STAGE_CONCEPTS["STARTS"]
        assert concept(permits_pace).source_program == "BPS"
        assert concept(permits_actual).source_program == "BPS"
        assert concept(starts_pace).source_program == "SOC"

    def test_the_unit_conversion_lives_on_the_binding(self) -> None:
        """Census publishes thousands of units. The 1000x scaling is a
        property of the provider, not of the concept."""
        for concept_id in HOUSING_CONCEPT_IDS:
            assert active_binding(concept_id).canonical_unit_factor == 1000.0
            assert active_binding(concept_id).provider_native_unit == "Thousands of Units"

    def test_every_binding_records_a_real_equivalence_basis(self) -> None:
        """No frozen methodology cites these series, so the equivalence
        cannot be recorded from an earlier decision -- it has to be
        justified from Census's own definitions, in words."""
        for concept_id in HOUSING_CONCEPT_IDS:
            basis = active_binding(concept_id).equivalence_basis
            assert len(basis) > 120, f"{concept_id} has a thin equivalence basis"
            assert "resconst" in basis


class TestAttribution:
    """Census's Data API terms require a verbatim non-endorsement notice."""

    def test_the_required_attribution_string_is_exact(self) -> None:
        assert PROVIDER_ATTRIBUTION == (
            "This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau."
        )

    def test_the_attribution_travels_on_the_response(self) -> None:
        """A frontend constant could drift out of sync with the data it
        governs; a response field cannot."""
        assert HousingResult.model_fields["attribution"].default == PROVIDER_ATTRIBUTION

    def test_nothing_claims_census_endorsement(self) -> None:
        for relative in HOUSING_MODULES:
            source = _module_source(relative).lower()
            for claim in ("endorsed by", "certified by census", "in partnership with", "official census product"):
                if claim in source:
                    # The one legitimate occurrence is inside the required
                    # NON-endorsement sentence.
                    assert "not endorsed or certified" in source

    def test_the_joint_publisher_is_named(self) -> None:
        """Census's own release states that Census and HUD jointly
        announce these statistics, so naming Census alone would be
        incomplete."""
        from app.models.housing import SOURCE_STATEMENT

        assert "Census" in SOURCE_STATEMENT
        assert "Housing and Urban Development" in SOURCE_STATEMENT


class TestSaarDiscipline:
    """#45 section 8. The most likely way to publish a false number here."""

    def test_the_saar_explanation_is_canonical_not_presentational(self) -> None:
        from app.models.housing import SAAR_EXPLANATION

        assert HousingResult.model_fields["saar_explanation"].default == SAAR_EXPLANATION

    def test_the_explanation_says_it_is_not_a_monthly_count(self) -> None:
        from app.models.housing import SAAR_EXPLANATION

        lowered = SAAR_EXPLANATION.lower()
        assert "not a count" in lowered
        assert "not a forecast" in lowered
        assert "dividing it by twelve" in lowered

    def test_no_housing_module_divides_by_twelve(self) -> None:
        """Dividing a seasonally adjusted annual rate by twelve and
        presenting the result as monthly production is explicitly
        forbidden: the seasonal adjustment that produced the annual rate
        is exactly what the division throws away."""
        for relative in HOUSING_MODULES:
            tree = _tree(relative)
            for node in ast.walk(tree):
                if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                    right = node.right
                    if isinstance(right, ast.Constant) and right.value in (12, 12.0):
                        raise AssertionError(f"{relative} divides by twelve")

    def test_no_housing_module_multiplies_by_twelve(self) -> None:
        """The inverse fabrication: annualising an unadjusted monthly
        count. Census's annual rate is the SEASONALLY ADJUSTED monthly
        value multiplied by twelve, and MacroChipz has no seasonal
        adjustment of its own."""
        for relative in HOUSING_MODULES:
            for node in ast.walk(_tree(relative)):
                if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
                    for side in (node.left, node.right):
                        if isinstance(side, ast.Constant) and side.value in (12, 12.0):
                            raise AssertionError(f"{relative} multiplies by twelve")


class TestNoMortgageData:
    """#45 section 12. MacroChipz has Treasury yields, not mortgage
    rates, and must never let the first stand in for the second."""

    def test_no_housing_module_mentions_a_mortgage_rate_value(self) -> None:
        for relative in HOUSING_MODULES:
            strings = _non_docstring_strings(relative)
            for text in strings:
                lowered = text.lower()
                for forbidden in ("mortgage rate", "home loan rate", "estimated mortgage", "mortgage spread"):
                    assert forbidden not in lowered, f"{relative} contains {forbidden!r}"

    def test_no_housing_module_declares_a_mortgage_name(self) -> None:
        for relative in HOUSING_MODULES:
            offenders = [name for name in _declared_names(relative) if "mortgage" in name.lower()]
            assert offenders == [], f"{relative} declares {offenders}"

    def test_no_concept_claims_to_be_a_mortgage_rate(self) -> None:
        for concept_obj in CONCEPTS.values():
            assert "mortgage" not in concept_obj.concept_id.lower()
            assert "mortgage" not in concept_obj.name.lower()

    def test_no_binding_treats_a_treasury_series_as_housing(self) -> None:
        """A Treasury yield bound to a housing concept would be exactly
        the substitution #45 forbids."""
        for binding in BINDINGS:
            if binding.provider == "TREASURY":
                assert concept(binding.concept_id).world == "rates"


class TestSmallestCoherentScope:
    """#45 section 3: permits, starts, completions. Nothing added to make
    the page richer."""

    def test_exactly_three_pipeline_stages_exist(self) -> None:
        assert PIPELINE_STAGES == ("PERMITS", "STARTS", "COMPLETIONS")

    def test_exactly_six_housing_concepts_exist(self) -> None:
        """Three stages, two adjustments. Not one more."""
        assert len(HOUSING_CONCEPT_IDS) == 6
        assert len([c for c in CONCEPTS.values() if c.world == "housing"]) == 6

    def test_no_out_of_scope_housing_concept_was_added(self) -> None:
        """The dataset also publishes units under construction and units
        authorized but not started, and other providers publish prices,
        sales and affordability. None of them is in scope."""
        forbidden = ("price", "sales", "affordab", "inventory", "underconst", "authnotstd", "mortgage")
        for concept_obj in CONCEPTS.values():
            if concept_obj.world != "housing":
                continue
            for fragment in forbidden:
                assert fragment not in concept_obj.concept_id.lower()

    def test_only_the_national_geography_is_used(self) -> None:
        for concept_id in HOUSING_CONCEPT_IDS:
            assert concept(concept_id).geography == "US"

    def test_every_housing_concept_is_monthly(self) -> None:
        for concept_id in HOUSING_CONCEPT_IDS:
            assert concept(concept_id).frequency == "MONTHLY"

    def test_the_provider_is_census_and_only_census(self) -> None:
        assert PROVIDER == "CENSUS"
        housing_bindings = [b for b in BINDINGS if concept(b.concept_id).world == "housing"]
        assert {b.provider for b in housing_bindings} == {"CENSUS"}

    def test_no_fred_binding_supplies_housing(self) -> None:
        """#45 rejected FRED as a workaround on licensing grounds. A FRED
        binding appearing for a housing concept would reverse that
        decision silently."""
        for binding in BINDINGS:
            if binding.provider == "FRED":
                assert concept(binding.concept_id).world != "housing"


class TestLimitationsAreHonest:
    """#45 sections 10 and 22: the pipeline must be understandable without
    implying that every permit becomes a start on a schedule."""

    def test_the_pipeline_limitations_refuse_a_fixed_conversion(self) -> None:
        from app.models.housing import PIPELINE_LIMITATIONS

        joined = " ".join(PIPELINE_LIMITATIONS).lower()
        assert "not the same home" in joined
        assert "no fixed share" in joined
        assert "not every authorized home is built" in joined

    def test_the_limitations_state_that_no_state_exists(self) -> None:
        from app.models.housing import PIPELINE_LIMITATIONS

        joined = " ".join(PIPELINE_LIMITATIONS).lower()
        assert "no housing methodology" in joined

    def test_the_limitations_carry_censuss_own_trend_guidance(self) -> None:
        """Census states it may take three months to establish a trend for
        permits and six for starts and completions. Quoting the provider
        is how MacroChipz warns about month-to-month reading without
        inventing a significance test of its own."""
        from app.models.housing import PIPELINE_LIMITATIONS

        joined = " ".join(PIPELINE_LIMITATIONS).lower()
        assert "three months" in joined and "six months" in joined

    def test_the_limitations_disclaim_significance_testing(self) -> None:
        from app.models.housing import PIPELINE_LIMITATIONS

        joined = " ".join(PIPELINE_LIMITATIONS).lower()
        assert "statistically significant" in joined

    def test_the_limitations_name_the_two_reliability_regimes(self) -> None:
        from app.models.housing import PIPELINE_LIMITATIONS

        joined = " ".join(PIPELINE_LIMITATIONS).lower()
        assert "non-probability sample" in joined
        assert "sampling variability" in joined

    def test_the_limitations_state_the_private_only_universe(self) -> None:
        from app.models.housing import PIPELINE_LIMITATIONS

        assert any("publicly-owned" in item.lower() for item in PIPELINE_LIMITATIONS)

    def test_the_result_carries_every_limitation(self) -> None:
        from app.models.housing import PIPELINE_LIMITATIONS

        result = HousingResult(as_of_period=None, stages=[], limitations=list(PIPELINE_LIMITATIONS))
        assert len(result.limitations) == len(PIPELINE_LIMITATIONS)


class TestVersioningIntegration:
    """#45 section 7 / #43: Housing reuses the existing observation
    architecture rather than building its own history."""

    def test_housing_declares_its_own_version_origin(self) -> None:
        from app.repositories.observation_versions import ORIGIN_HOUSING_INGESTION, VALID_ORIGINS

        assert ORIGIN_HOUSING_INGESTION in VALID_ORIGINS

    def test_the_repository_writes_through_the_shared_version_writer(self) -> None:
        """Housing must not get its own history mechanism: point-in-time
        replay (#31) and Revision Intelligence (#43) work for Housing
        precisely because nothing about its history is Housing-specific."""
        imported = _imported_names(Path("app/repositories/housing_repository.py"))
        assert "ObservationVersionWriter" in imported

    def test_no_housing_specific_history_table_exists(self) -> None:
        """One new table, and it is an ingestion-run audit -- not
        observations, not provenance, not versions."""
        from app.db import models as db_models

        housing_tables = [
            name
            for name in dir(db_models)
            if "housing" in name.lower() and isinstance(getattr(db_models, name), type)
        ]
        assert housing_tables == ["HousingIngestionRun"]

    def test_the_baseline_flag_only_applies_to_first_observations(self) -> None:
        """A revision MacroChipz observed is never a baseline, whatever
        the caller asked for -- the writer enforces it rather than
        trusting the call site."""
        source = _module_source(Path("app/repositories/observation_versions.py"))
        assert 'self._baseline and change_type == "NEW"' in source


class TestIntelligenceBoundary:
    """#45 section 9: Housing integrates with #39 by REUSING an existing
    object type, and the backfill must not appear as intelligence."""

    def test_no_housing_specific_intelligence_type_was_added(self) -> None:
        from app.models.intelligence import IntelligenceType

        assert set(IntelligenceType.__args__) == {
            "RELEASE_PROCESSED",
            "OBSERVATION_CHANGE",
            "ANALYSIS_CHANGE",
            "RATES_MOVEMENT",
        }

    def test_the_builder_reads_only_observed_versions_for_housing(self) -> None:
        """The one line that stops 4,644 imported observations becoming
        4,644 "new data point" entries."""
        source = _module_source(Path("app/repositories/observation_versions.py"))
        assert "ObservationVersion.is_backfilled.is_(False)" in source

    def test_the_housing_object_count_is_bounded_at_the_query(self) -> None:
        from app.services.intelligence.builder import IntelligenceBuilder

        assert IntelligenceBuilder.HOUSING_OBJECT_LIMIT <= 100
        source = _module_source(Path("app/repositories/observation_versions.py"))
        assert ".limit(limit)" in source

    def test_the_builder_still_performs_no_provider_io(self) -> None:
        imported = _imported_modules(Path("app/services/intelligence/builder.py"))
        assert "httpx" not in imported
        assert "app.clients.census" not in imported


# ----------------------------------------------------------------------
# Import inspection helpers
# ----------------------------------------------------------------------


def _imported_modules(relative: Path) -> set[str]:
    """Top-level module names this file imports, plus dotted prefixes so
    `app.clients.census` matches a check for `app.clients`."""
    names: set[str] = set()
    for node in ast.walk(_tree(relative)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.add(node.module.split(".")[0])
            parts = node.module.split(".")
            for index in range(1, len(parts)):
                names.add(".".join(parts[:index]))
    return names


def _imported_names(relative: Path) -> set[str]:
    """The names bound by imports -- what the module can actually use."""
    names: set[str] = set()
    for node in ast.walk(_tree(relative)):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add(alias.asname or alias.name)
            if isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module)
    return names
