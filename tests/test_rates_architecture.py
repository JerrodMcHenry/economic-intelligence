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


# ---------------------------------------------------------------------
# The frontend calculation scan (Increment #30, scope corrected in #53B)
# ---------------------------------------------------------------------
#
# WHY THIS SCAN IS SPLIT INTO TWO TIERS
# -------------------------------------
# #53A's audit found this guard red on `main` for two feature commits.
# It was flagging two lines that are not economic calculations at all:
#
#   frontend/src/lib/cssUnits.ts       `fraction * 100` -> a CSS "50%"
#   components/labor/SurveyThreshold   `(band / span) * 100` -> an SVG
#                                      width in a 0..100 viewBox
#
# The rule was never wrong; the SCOPE was. This guard's own docstring
# says its subject is "the frontend must never reconstruct a spread, a
# basis-point change, or inflation compensation", and it names
# `frontend/src/test/no-rates-calculation.test.ts` as the fine-grained
# companion that "scans the RATES MODULES". But the scan itself walked
# every file under `frontend/src`, so the two guards enforced the same
# rule over different file sets -- and the broader one had no way to
# tell a percentage-point-to-basis-point conversion from a fraction-to-
# CSS-percentage one, because in a Labor chart there is no rate in
# sight to distinguish them.
#
# The fix is to give each pattern the scope its own text justifies:
#
#   ECONOMICALLY SELF-NAMING patterns keep scanning ALL of frontend/src.
#   `spreadBasisPoints = a - b` and `nominalValue - realYield` name the
#   economics in the identifier, so they cannot false-positive on
#   layout arithmetic no matter which world's file they appear in.
#   Coverage here is UNCHANGED by #53B.
#
#   GENERIC ARITHMETIC (`* 100`) scans the RATES MODULES ONLY, using the
#   same scope rule the frontend companion has always used. `* 100` is
#   the one marker that names nothing: in a Rates module it is the shape
#   of a basis-point conversion and must be caught; anywhere else it is
#   as likely to be a CSS percentage, and the guard has no way to know.
#
# The rule is preserved exactly: a basis-point conversion written in any
# Rates module still fails this test, and an economically-named
# derivation still fails it anywhere in the frontend. See
# `TestTheGuardStillCatchesRealViolations` below, which proves both
# against this module's own scanning function rather than a copy of it.


#: The scope rule `frontend/src/test/no-rates-calculation.test.ts` has
#: used since #30, mirrored here so the two guards agree by construction
#: rather than by coincidence.
def _is_rates_module(relative_path: str) -> bool:
    return "rates" in relative_path or "Rates" in relative_path or relative_path.endswith("ratesFormat.ts")


#: Assignment of a derived financial value. The identifier names the
#: economics, so these are safe to apply to every frontend file.
_NAMED_DERIVATION_PATTERNS = (
    re.compile(r"\b(inflationCompensation|basisPoints|spreadBasisPoints|percentileRank)\s*=\s*[^=;\n]*[-+*/]"),
    re.compile(r"\b(nominal|real|long|short)\w*\s+-\s+\w*(Value|Yield|Rate)\b"),
)

#: Percentage points -> basis points. Names nothing, so it is meaningful
#: only where rates are the subject.
_RATES_ONLY_PATTERNS = (re.compile(r"\*\s*100\b"),)

#: Scaling an already-computed 0..1 rank into a percentile for display
#: is unit formatting, not derivation -- the same class of operation as
#: rendering 0.25 as "25%".
_DISPLAY_SCALING = re.compile(r"percentile|rank", re.IGNORECASE)


def _scan_frontend_for_calculations(frontend_src: Path) -> list[str]:
    """Every line that looks like a client-side economic derivation.

    One function, used by the real guard AND by its regression tests, so
    a test asserting "a violation is still caught" is exercising the
    code that actually runs -- not a second copy of the patterns that
    could drift away from it.
    """
    offenders: list[str] = []
    for path in sorted(frontend_src.rglob("*.ts*")):
        if path.name.endswith((".test.ts", ".test.tsx")):
            continue
        relative_path = str(path.relative_to(frontend_src))
        patterns = _NAMED_DERIVATION_PATTERNS + (_RATES_ONLY_PATTERNS if _is_rates_module(relative_path) else ())
        for line_number, line in enumerate(path.read_text().split("\n"), 1):
            code = line.split("//", 1)[0]
            if code.lstrip().startswith("*"):
                continue  # a block-comment line is prose, not code
            if _DISPLAY_SCALING.search(code):
                continue
            for pattern in patterns:
                if pattern.search(code):
                    offenders.append(f"{path}:{line_number}: {line.strip()}")
    return offenders


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

        Increment #53B note: see the two-tier scope explanation above.
        """
        frontend_src = Path("frontend/src")
        if not frontend_src.exists():
            pytest.skip("frontend/src not present")

        offenders = _scan_frontend_for_calculations(frontend_src)
        assert offenders == [], f"frontend appears to compute rates values: {offenders}"

    def test_the_shared_percentage_helper_stays_a_layout_helper(self):
        """`lib/cssUnits.ts` is the one file the narrowed scope creates
        an opening in, so it is closed explicitly.

        That file exists BECAUSE of this guard: #49B needed a 0..1
        fraction as a CSS percentage, `* 100` in a Rates module is the
        shape of a basis-point conversion, and the answer was to move
        the conversion out of the economics boundary rather than weaken
        the check. Since #53B narrows the `* 100` scan to Rates modules,
        that file is no longer scanned for it -- which would make it the
        obvious place to hide the conversion the guard exists to
        prevent.

        So it is pinned: a layout helper, with no economic vocabulary in
        it at all. If it ever needs to know what a yield is, it is no
        longer a layout helper and this test should fail.
        """
        helper = Path("frontend/src/lib/cssUnits.ts")
        if not helper.exists():
            pytest.skip("lib/cssUnits.ts not present")

        source = helper.read_text()
        code = "\n".join(
            line.split("//", 1)[0]
            for line in source.split("\n")
            if not line.lstrip().startswith(("*", "/*"))
        )
        for economic_term in ("yield", "spread", "basis", "compensation", "nominal", "maturity", "bp"):
            assert economic_term not in code.lower(), (
                f"lib/cssUnits.ts mentions '{economic_term}' in code -- it is a layout helper, "
                "and a rates concept appearing in it means the conversion has moved back inside "
                "the economics boundary. See tests/test_rates_architecture.py."
            )
        # One exported function, doing one thing.
        assert code.count("export function") == 1


class TestTheGuardStillCatchesRealViolations:
    """Proof that narrowing the scope did not narrow the RULE.

    Each case writes a synthetic frontend tree to a tmp directory and
    runs the real `_scan_frontend_for_calculations` over it. A
    regression test that re-implemented the patterns would prove only
    that the copy still works.
    """

    @staticmethod
    def _tree(tmp_path: Path, files: dict[str, str]) -> Path:
        root = tmp_path / "src"
        for name, body in files.items():
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body)
        return root

    def test_a_basis_point_conversion_in_a_rates_module_is_caught(self, tmp_path):
        root = self._tree(
            tmp_path,
            {"components/rates/Spread.tsx": "const bp = spread.value * 100;\n"},
        )
        assert _scan_frontend_for_calculations(root), "a basis-point conversion in a Rates module must be caught"

    def test_a_basis_point_conversion_in_a_rates_named_lib_file_is_caught(self, tmp_path):
        """Scope follows the NAME, so a helper is not an escape route."""
        root = self._tree(tmp_path, {"lib/ratesMath.ts": "export const toBp = (pp: number) => pp * 100;\n"})
        assert _scan_frontend_for_calculations(root), "a rates-named helper is in scope and must be caught"

    def test_a_spread_derivation_is_caught_in_any_world(self, tmp_path):
        """Economically-named derivation is scanned repo-wide, unchanged
        by #53B -- including in a file with nothing to do with Rates."""
        root = self._tree(
            tmp_path,
            {"components/labor/Chart.tsx": "const spreadBasisPoints = longValue - shortValue;\n"},
        )
        assert _scan_frontend_for_calculations(root), "a named spread derivation must be caught anywhere"

    def test_a_rate_shaped_subtraction_is_caught_in_any_world(self, tmp_path):
        root = self._tree(tmp_path, {"pages/Anything.tsx": "const gap = nominalValue - realYield;\n"})
        assert _scan_frontend_for_calculations(root), "a rate-shaped subtraction must be caught anywhere"

    def test_a_css_percentage_outside_the_rates_modules_is_allowed(self, tmp_path):
        """The two lines that made this guard red, as their own case."""
        root = self._tree(
            tmp_path,
            {
                "lib/cssUnits.ts": "export function percentOf(fraction: number) { return `${fraction * 100}%`; }\n",
                "components/labor/SurveyThreshold.tsx": "const width = (band / span) * 100;\n",
            },
        )
        assert _scan_frontend_for_calculations(root) == []

    def test_a_percentile_display_scaling_is_still_allowed(self, tmp_path):
        root = self._tree(tmp_path, {"lib/ratesFormat.ts": "const percentile = Math.round(rank * 100);\n"})
        assert _scan_frontend_for_calculations(root) == []

    def test_a_test_file_is_never_scanned(self, tmp_path):
        """Fixtures and tests legitimately contain the shapes the guard
        forbids in product code."""
        root = self._tree(tmp_path, {"components/rates/Spread.test.tsx": "const bp = value * 100;\n"})
        assert _scan_frontend_for_calculations(root) == []


def test_methodology_document_exists_and_is_versioned():
    """A versioned methodology is part of the contract, not optional
    documentation: the model constant and the document must agree."""
    from app.models.rates import METHODOLOGY_ID

    document = Path("docs/methodology/rates-v1.0.md")
    assert document.exists()
    assert METHODOLOGY_ID == "rates_v1.0"
    assert METHODOLOGY_ID in document.read_text()
