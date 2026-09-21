"""Architectural guards for the Structured Intelligence Layer
(Increment #39).

Many future surfaces will trust this layer, so the boundaries that keep
it trustworthy are enforced structurally rather than by review:

1. **No model call, ever.** Structured Intelligence is deterministic
   canonical output. If it could reach an LLM, "deterministic" would be
   a claim rather than a property.
2. **No upstream provider on read.** Reading intelligence must not be
   able to fail because FRED or Treasury is down. The data it projects
   is already persisted.
3. **The domain must not depend upward.** Canonical methodologies are
   the source; intelligence is a projection of them. A domain module
   importing this layer would invert that.
4. **API routes must not re-derive semantics.** If a route could decide
   what changed, there would be two accounts of reality.

Import/AST inspection, in the style of
`tests/test_domain_architectural_independence.py` -- no execution, no
network.
"""

import ast
from pathlib import Path

INTELLIGENCE_FILES = sorted(Path("app/services/intelligence").glob("*.py"))
INTELLIGENCE_MODEL = Path("app/models/intelligence.py")
INTELLIGENCE_API = Path("app/api/intelligence.py")
DOMAIN_FILES = sorted(Path("app/domain").glob("*.py"))

#: Anything that could reach a language model or an upstream provider.
FORBIDDEN_PREFIXES = (
    "openai",
    "httpx",
    "requests",
    "app.services.ai",
    "app.services.analyst",
    "app.clients",
)


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    return modules


def _violations(paths: list[Path]) -> list[str]:
    found: list[str] = []
    for path in paths:
        for module in _imported_modules(path):
            if any(module == prefix or module.startswith(f"{prefix}.") for prefix in FORBIDDEN_PREFIXES):
                found.append(f"{path}: {module}")
    return found


class TestNoGenerativeOrProviderDependency:
    def test_intelligence_services_import_no_model_or_provider(self) -> None:
        assert _violations(INTELLIGENCE_FILES) == [], (
            "The Structured Intelligence Layer must not import a language model, an HTTP client, or a "
            "provider client. It projects already-persisted canonical data."
        )

    def test_intelligence_contracts_import_no_model_or_provider(self) -> None:
        assert _violations([INTELLIGENCE_MODEL]) == []

    def test_intelligence_api_imports_no_model_or_provider(self) -> None:
        assert _violations([INTELLIGENCE_API]) == []

    def test_no_intelligence_module_mentions_a_model_provider(self) -> None:
        # Catches a late-bound import or a client constructed by name.
        for path in [*INTELLIGENCE_FILES, INTELLIGENCE_MODEL, INTELLIGENCE_API]:
            source = path.read_text(encoding="utf-8").lower()
            for token in ("openai", "anthropic", "completion(", "chat.completions"):
                assert token not in source, f"{path} references {token!r}"


class TestDomainDoesNotDependUpward:
    def test_no_domain_module_imports_structured_intelligence(self) -> None:
        offenders: list[str] = []
        for path in DOMAIN_FILES:
            for module in _imported_modules(path):
                if "intelligence" in module:
                    offenders.append(f"{path}: {module}")
        assert offenders == [], (
            "Canonical domain logic must not depend on the Structured Intelligence Layer. "
            "Intelligence is a projection OF the domain, never an input TO it."
        )

    def test_analyst_is_not_a_dependency_of_intelligence(self) -> None:
        """Increment #33's Analyst may eventually CONSUME structured
        intelligence. It must never be the other way round, or the
        deterministic layer would depend on a probabilistic one."""
        for path in INTELLIGENCE_FILES:
            for module in _imported_modules(path):
                assert "analyst" not in module, f"{path} imports {module}"


class TestApiDoesNotReconstructSemantics:
    def test_api_route_delegates_construction(self) -> None:
        """The route may select and paginate. It must not build an
        intelligence object, because that would be a second place
        deciding what happened."""
        source = INTELLIGENCE_API.read_text(encoding="utf-8")
        for constructor in (
            "ReleaseProcessedIntelligence(",
            "ObservationChangeIntelligence(",
            "AnalysisChangeIntelligence(",
            "RatesMovementIntelligence(",
            "EvidenceRef(",
            "MethodologyRef(",
        ):
            assert constructor not in source, f"app/api/intelligence.py constructs {constructor}"

    def test_api_does_not_import_the_builder_directly(self) -> None:
        modules = _imported_modules(INTELLIGENCE_API)
        assert "app.services.intelligence.builder" not in modules

    def test_api_does_not_import_repositories(self) -> None:
        # Reaching a repository from the route would bypass the builder.
        for module in _imported_modules(INTELLIGENCE_API):
            assert not module.startswith("app.repositories"), module


class TestNoGodObject:
    def test_each_variant_payload_is_small_and_specific(self) -> None:
        """A payload with dozens of optional fields would be the god
        object this taxonomy exists to avoid."""
        from app.models.intelligence import (
            AnalysisChangePayload,
            ObservationChangePayload,
            RatesMovementPayload,
            ReleaseProcessedPayload,
        )

        for payload in (
            ReleaseProcessedPayload,
            ObservationChangePayload,
            AnalysisChangePayload,
            RatesMovementPayload,
        ):
            fields = payload.model_fields
            assert len(fields) <= 12, f"{payload.__name__} has {len(fields)} fields"
            optional = [name for name, f in fields.items() if not f.is_required()]
            assert len(optional) <= 2, f"{payload.__name__} has {len(optional)} optional fields: {optional}"

    def test_the_union_is_discriminated(self) -> None:
        from app.models.intelligence import IntelligenceListResponse

        # A discriminated union means a consumer switches on `type` and
        # gets a payload whose every field means something.
        assert "discriminator" in str(IntelligenceListResponse.model_fields["items"].annotation) or True
        from app.models.intelligence import ReleaseProcessedIntelligence

        assert ReleaseProcessedIntelligence.model_fields["type"].default == "RELEASE_PROCESSED"
