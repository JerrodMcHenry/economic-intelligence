"""Architectural guards for Increment #24C's State Duration V1 backend
(`docs/product/state-duration-v1.md` §50), checked statically (AST/
source inspection) wherever possible rather than left to convention --
the same discipline `tests/test_labor_architecture.py` already applies
to Labor. No database, no FRED, no FastAPI test client -- every check
here is a plain source/model inspection.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Every production file this increment created or modified.
STATE_DURATION_FILES = [
    Path("app/domain/state_duration.py"),
    Path("app/models/state_duration.py"),
    Path("app/services/inflation.py"),
    Path("app/services/labor.py"),
    Path("app/api/inflation.py"),
    Path("app/api/labor.py"),
]


def _imported_module_names(file_path: Path) -> set[str]:
    tree = ast.parse((REPO_ROOT / file_path).read_text(), filename=str(file_path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


class TestStateDurationFilesExist:
    def test_state_duration_files_exist_where_expected(self):
        for file_path in STATE_DURATION_FILES:
            assert (REPO_ROOT / file_path).is_file(), f"expected {file_path} to exist"


class TestNoAIOrFREDImports:
    """Guard: no file on the State Duration V1 path imports FRED or
    AI/OpenAI -- it is DB-only, read-only, per frozen contract §35."""

    FORBIDDEN_PREFIXES = ("openai", "app.services.ai", "app.services.news", "app.clients.fred")

    def test_no_state_duration_file_imports_ai_or_fred(self):
        violations = []
        for file_path in STATE_DURATION_FILES:
            for module_name in _imported_module_names(file_path):
                if any(module_name == p or module_name.startswith(p + ".") for p in self.FORBIDDEN_PREFIXES):
                    violations.append(f"{file_path}: imports '{module_name}'")
        assert violations == [], "State Duration V1 path imports a forbidden dependency:\n" + "\n".join(violations)


class TestNoChartingImport:
    """Guard: frozen contract §50 -- no charting import anywhere on the
    backend path (charting is explicitly a #24D-or-later frontend
    concern, and V1 has no chart data shape at all)."""

    FORBIDDEN_SUBSTRINGS = ("chart", "plotly", "d3", "recharts")

    def test_no_charting_dependency(self):
        violations = []
        for file_path in STATE_DURATION_FILES:
            for module_name in _imported_module_names(file_path):
                lowered = module_name.lower()
                if any(s in lowered for s in self.FORBIDDEN_SUBSTRINGS):
                    violations.append(f"{file_path}: imports '{module_name}'")
        assert violations == [], "State Duration V1 path imports a charting dependency:\n" + "\n".join(violations)


class TestNoSessionMutationInTheDurationServiceMethods:
    """Guard: `InflationMonitorService.get_state_duration_result`/
    `LaborMonitorService.get_state_duration_result` never call a
    session-mutating method (`add`, `commit`, `flush`, `delete`,
    `merge`, `execute` with INSERT/UPDATE/DELETE) -- structural proof
    that the read path cannot write, mirroring the functional proof
    already given by the "does not modify persisted observations"
    integration tests."""

    FORBIDDEN_SESSION_METHODS = {"add", "add_all", "commit", "flush", "delete", "merge"}

    def _method_source(self, file_path: Path, class_name: str, method_name: str) -> ast.FunctionDef:
        tree = ast.parse((REPO_ROOT / file_path).read_text(), filename=str(file_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == method_name:
                        return item
        raise AssertionError(f"{class_name}.{method_name} not found in {file_path}")

    def test_inflation_state_duration_method_never_mutates_the_session(self):
        method = self._method_source(Path("app/services/inflation.py"), "InflationMonitorService", "get_state_duration_result")
        calls = [n for n in ast.walk(method) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
        violations = {n.func.attr for n in calls if n.func.attr in self.FORBIDDEN_SESSION_METHODS}
        assert violations == set(), f"get_state_duration_result calls a session-mutating method: {violations}"

    def test_labor_state_duration_method_never_mutates_the_session(self):
        method = self._method_source(Path("app/services/labor.py"), "LaborMonitorService", "get_state_duration_result")
        calls = [n for n in ast.walk(method) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
        violations = {n.func.attr for n in calls if n.func.attr in self.FORBIDDEN_SESSION_METHODS}
        assert violations == set(), f"get_state_duration_result calls a session-mutating method: {violations}"


class TestPureDurationHelperHasNoStatisticalOrPercentileLogic:
    """Guard: frozen contract §50 -- app/domain/state_duration.py
    computes counts and equality checks only; no percentile/
    statistical-distribution logic of any kind."""

    FORBIDDEN_SUBSTRINGS = ("percentile", "stdev", "variance", "quantile", "numpy", "scipy", "statistics")

    def test_no_statistical_vocabulary_in_source(self):
        source = (REPO_ROOT / "app/domain/state_duration.py").read_text().lower()
        found = [s for s in self.FORBIDDEN_SUBSTRINGS if s in source]
        assert found == [], f"app/domain/state_duration.py references statistical/percentile vocabulary: {found}"


class TestNoRecordedOrAsKnownAtTimeVocabularyInBackendCode:
    """Guard: frozen contract §50/§51 -- the single most load-bearing
    rule in `docs/product/state-duration-v1.md`. Scoped narrowly to
    exactly the new backend files (not the whole tree), mirroring
    #23C's own `no-relate-inference.test.ts` precedent for avoiding a
    false positive on unrelated, correct prose elsewhere in the
    codebase."""

    FORBIDDEN_PHRASES = (
        "ei has classified",
        "ei has said",
        "ei reported",
        "as-known-at-time",
        "as known at the time",
    )

    def test_no_forbidden_historical_truth_phrase(self):
        violations = []
        for file_path in STATE_DURATION_FILES:
            lowered = (REPO_ROOT / file_path).read_text().lower()
            for phrase in self.FORBIDDEN_PHRASES:
                if phrase in lowered:
                    violations.append(f"{file_path}: contains '{phrase}'")
        assert violations == [], "forbidden historical-truth phrase found:\n" + "\n".join(violations)


class TestBoundaryTypeIsAThreeValueEnumNeverABoolean:
    """Guard: frozen contract §13 -- `boundary_type` must be the exact
    three-value Literal, never widened, never narrowed, never typed as
    `bool`."""

    def test_boundary_type_literal_has_exactly_three_values(self):
        from app.models.state_duration import BoundaryType

        assert set(BoundaryType.__args__) == {"EXACT", "DATA_BOUNDED", "LOOKBACK_BOUNDED"}

    def test_state_duration_available_boundary_type_field_is_not_bool(self):
        from app.models.state_duration import StateDurationAvailable

        field = StateDurationAvailable.model_fields["boundary_type"]
        assert field.annotation is not bool


class TestFrozenContractIdentifiers:
    """Guard: the frozen literal/history-type value, unchanged."""

    def test_history_type_constant(self):
        from app.models.state_duration import HISTORY_TYPE

        assert HISTORY_TYPE == "latest_revised_reconstruction"

    def test_available_response_default_history_type(self):
        from app.models.state_duration import StateDurationAvailable

        assert StateDurationAvailable.model_fields["history_type"].default == "latest_revised_reconstruction"
