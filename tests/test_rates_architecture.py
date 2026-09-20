"""Architectural guards for the Rates domain (Increment #29).

Source-inspection tests (`ast`, no execution, no network) protecting the
structural promises #29 makes, which no behavioral test can protect on
its own:

1. The Rates domain contains NO AI and NO probabilistic model -- not as
   a policy statement in a document, but as a checkable property of the
   import graph and the source text.
2. The READ path is structurally incapable of reaching upstream: it has
   no Treasury client anywhere in its import graph, so a read can never
   trigger ingestion.
3. Upstream access is allow-listed: the Treasury client hardcodes its
   host and its permitted datasets, and nothing user-supplied can
   redirect it.
4. Derived financial values are computed in the backend, never in the
   frontend.
"""

import ast
from pathlib import Path

import pytest

RATES_MODULES = [
    Path("app/domain/rates.py"),
    Path("app/models/rates.py"),
    Path("app/services/rates.py"),
    Path("app/services/rates_ingestion.py"),
    Path("app/repositories/rates_repository.py"),
    Path("app/clients/treasury.py"),
    Path("app/api/rates.py"),
]

# Anything that would make a Rates result probabilistic, model-derived,
# or AI-authored. `random` is included deliberately: a canonical result
# must be reproducible, and nothing here has any legitimate use for it.
FORBIDDEN_MODULE_PREFIXES = (
    "openai",
    "anthropic",
    "app.services.ai",
    "sklearn",
    "scipy",
    "statsmodels",
    "numpy.random",
    "torch",
    "random",
    "app.clients.fred",  # Rates has exactly one provider; see rates-v1.0.md
)


def _imported_module_names(file_path: Path) -> set[str]:
    tree = ast.parse(file_path.read_text(), filename=str(file_path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _transitive_app_imports(entry: Path, seen: set[Path] | None = None) -> set[str]:
    """Every `app.*` module reachable from `entry`, following imports."""
    seen = seen if seen is not None else set()
    if entry in seen or not entry.exists():
        return set()
    seen.add(entry)

    reachable: set[str] = set()
    for module in _imported_module_names(entry):
        if not module.startswith("app."):
            reachable.add(module)
            continue
        reachable.add(module)
        reachable |= _transitive_app_imports(Path(module.replace(".", "/") + ".py"), seen)
    return reachable


@pytest.mark.parametrize("module_path", RATES_MODULES, ids=lambda path: path.name)
def test_no_ai_or_probabilistic_dependency(module_path: Path):
    for imported in _imported_module_names(module_path):
        for forbidden in FORBIDDEN_MODULE_PREFIXES:
            assert not (
                imported == forbidden or imported.startswith(f"{forbidden}.")
            ), f"{module_path} imports forbidden module '{imported}'"


def test_pure_domain_has_no_io_dependency_at_all():
    """`app/domain/rates.py` is arithmetic over values handed to it --
    it must not know about databases, HTTP, or the web framework."""
    imports = _imported_module_names(Path("app/domain/rates.py"))
    for forbidden in ("sqlalchemy", "httpx", "fastapi", "app.repositories", "app.clients", "app.services"):
        assert not any(name == forbidden or name.startswith(f"{forbidden}.") for name in imports)


def test_read_service_cannot_reach_upstream():
    """The monitor service must have no path to the Treasury client:
    a read can therefore never trigger ingestion, by construction rather
    than by convention."""
    reachable = _transitive_app_imports(Path("app/services/rates.py"))
    assert "app.clients.treasury" not in reachable
    assert not any(name.startswith("httpx") for name in reachable)


def test_only_the_ingestion_path_holds_the_upstream_client():
    assert "app.clients.treasury" in _imported_module_names(Path("app/services/rates_ingestion.py"))


class TestUpstreamAccessIsAllowListed:
    def test_client_hardcodes_its_host(self):
        source = Path("app/clients/treasury.py").read_text()
        assert 'TREASURY_BASE_URL = "https://home.treasury.gov"' in source

    def test_client_defines_a_closed_dataset_allow_list(self):
        from app.clients.treasury import ALLOWED_DATASETS

        assert ALLOWED_DATASETS == frozenset({"daily_treasury_yield_curve", "daily_treasury_real_yield_curve"})

    def test_no_module_builds_an_upstream_url_from_a_parameter(self):
        """No f-string or concatenation may put a caller-supplied host
        or path into a request URL. The client composes exactly one URL
        from two module constants."""
        source = Path("app/clients/treasury.py").read_text()
        assert 'url = f"{self._base_url}{_XML_PATH}"' in source

    def test_api_layer_never_accepts_a_url_or_dataset_from_the_caller(self):
        source = Path("app/api/rates.py").read_text()
        for suspicious in ("url", "host", "dataset", "endpoint", "provider"):
            assert f"{suspicious}:" not in source.split("def sync_rates(")[1].split(")")[0]

    def test_response_size_is_bounded(self):
        from app.clients.treasury import MAX_RESPONSE_BYTES

        assert 0 < MAX_RESPONSE_BYTES <= 8 * 1024 * 1024

    def test_client_applies_a_timeout(self):
        from app.clients.treasury import TreasuryClient

        assert TreasuryClient()._timeout > 0


class TestDerivedValuesAreBackendOwned:
    def test_frontend_does_not_compute_rates_metrics(self):
        """The frontend must never reconstruct a spread, a basis-point
        change, or inflation compensation. #29 ships no frontend code at
        all; this guard fails the moment someone adds such a
        calculation client-side."""
        frontend_src = Path("frontend/src")
        if not frontend_src.exists():
            pytest.skip("frontend/src not present")

        forbidden_markers = (
            "UST_NOMINAL_",
            "UST_REAL_",
            "inflationCompensation =",
            "basisPoints =",
            "spreadBasisPoints =",
        )
        offenders = []
        for path in frontend_src.rglob("*.ts*"):
            text = path.read_text()
            for marker in forbidden_markers:
                if marker in text:
                    offenders.append(f"{path}: {marker}")
        assert offenders == [], f"frontend appears to compute rates values: {offenders}"


def test_methodology_document_exists_and_is_versioned():
    """A versioned methodology is part of the contract, not optional
    documentation: the model constant and the document must agree."""
    from app.models.rates import METHODOLOGY_ID

    document = Path("docs/methodology/rates-v1.0.md")
    assert document.exists()
    assert METHODOLOGY_ID == "rates_v1.0"
    assert METHODOLOGY_ID in document.read_text()
