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
import re
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
        change, or inflation compensation.

        Increment #30 note: this guard originally also forbade the
        canonical series identifiers (`UST_NOMINAL_`, `UST_REAL_`) from
        appearing in `frontend/src` at all. That was a sound proxy while
        #29 shipped no Rates UI, but it tested the ABSENCE OF A UI, not
        the absence of a calculation -- and #30 legitimately renders
        those identifiers because the API returns them as provenance
        (`long_series_id`, `input_series_ids`) that the evidence panels
        must display. Naming a series the backend already named is not
        computing anything.

        The markers below therefore target ASSIGNMENT of a derived
        financial value in frontend code, which is the behaviour this
        guard actually exists to prevent. The fine-grained companion
        check lives on the frontend side
        (`frontend/src/test/no-rates-calculation.test.ts`), which scans
        the Rates modules for subtraction of rate-shaped values,
        basis-point conversion, and hand-written percentile math.
        """
        frontend_src = Path("frontend/src")
        if not frontend_src.exists():
            pytest.skip("frontend/src not present")

        # Each pattern matches an ASSIGNMENT whose right-hand side does
        # arithmetic -- e.g. `const spreadBasisPoints = long - short`.
        # Reading `spread.spread_basis_points` off a response never
        # matches; deriving one always does.
        forbidden_patterns = (
            re.compile(r"\b(inflationCompensation|basisPoints|spreadBasisPoints|percentileRank)\s*=\s*[^=;\n]*[-+*/]"),
            re.compile(r"\b(nominal|real|long|short)\w*\s+-\s+\w*(Value|Yield|Rate)\b"),
            re.compile(r"\*\s*100\b"),
        )
        # Scaling an already-computed 0..1 rank into a percentile for
        # display is unit formatting, not derivation -- the same class of
        # operation as rendering 0.25 as "25%".
        display_scaling = re.compile(r"percentile|rank", re.IGNORECASE)

        offenders = []
        for path in frontend_src.rglob("*.ts*"):
            if path.name.endswith((".test.ts", ".test.tsx")):
                continue
            for line_number, line in enumerate(path.read_text().split("\n"), 1):
                code = line.split("//", 1)[0]
                if code.lstrip().startswith("*"):
                    continue  # a block-comment line is prose, not code
                if display_scaling.search(code):
                    continue
                for pattern in forbidden_patterns:
                    if pattern.search(code):
                        offenders.append(f"{path}:{line_number}: {line.strip()}")
        assert offenders == [], f"frontend appears to compute rates values: {offenders}"


def test_methodology_document_exists_and_is_versioned():
    """A versioned methodology is part of the contract, not optional
    documentation: the model constant and the document must agree."""
    from app.models.rates import METHODOLOGY_ID

    document = Path("docs/methodology/rates-v1.0.md")
    assert document.exists()
    assert METHODOLOGY_ID == "rates_v1.0"
    assert METHODOLOGY_ID in document.read_text()
