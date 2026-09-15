"""Architectural guards for Increment #26C's schema compatibility
checking, checked statically (AST/source inspection) wherever possible
-- the same discipline every prior increment's own dedicated guard
file already applies. No database, no FRED, no FastAPI test client;
every check here is a plain source/model inspection. Frozen contract:
docs/product/production-reliability-deployment-v1.md (#26B) §12/§51/
§52/§53/§54/§55/§60.
"""

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_SCHEMA_COMPATIBILITY_FILE = Path("app/core/schema_compatibility.py")
_VERSION_FILE = Path("app/core/version.py")
_MAIN_FILE = Path("app/main.py")
_PROCESS_RELEASE_FILE = Path("app/operations/process_release.py")
_RUN_MAINTENANCE_FILE = Path("app/operations/run_maintenance.py")


def _source(file_path: Path) -> str:
    return (REPO_ROOT / file_path).read_text()


def _code_only(file_path: Path) -> str:
    """Strips triple-quoted docstrings and `#` comments before a
    pattern check -- this project's own established fix (Increment
    #25E's `Session`-in-docstring guard, #25H's `Date.now()`-in-
    docstring guard) for the same recurring false-positive shape: a
    module's own explanatory prose correctly NAMES a forbidden term in
    English (to explain why the code below never does it), which a raw
    substring match against the whole file would otherwise flag."""
    source = _source(file_path)
    without_triple_quoted = re.sub(r'"""[\s\S]*?"""', "", source)
    without_triple_quoted = re.sub(r"'''[\s\S]*?'''", "", without_triple_quoted)
    return re.sub(r"^\s*#.*$", "", without_triple_quoted, flags=re.MULTILINE)


def _tree(file_path: Path) -> ast.Module:
    return ast.parse(_source(file_path), filename=str(file_path))


def _imported_module_names(file_path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(_tree(file_path)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


class TestFileExists:
    def test_schema_compatibility_module_exists(self):
        assert (REPO_ROOT / _SCHEMA_COMPATIBILITY_FILE).is_file()


class TestBoundedResponsibility:
    """#26C source prompt §12: the compatibility module knows the
    Alembic migration graph and a database's own `alembic_version`
    table -- nothing about Inflation, Labor, FRED, economic releases,
    Recorded State History, Since Last Visit, or AI."""

    FORBIDDEN_PREFIXES = (
        "app.services",
        "app.domain",
        "app.repositories",
        "app.clients",
        "app.api",
        "openai",
    )

    def test_schema_compatibility_module_imports_nothing_economic_or_ai(self):
        violations = [
            name
            for name in _imported_module_names(_SCHEMA_COMPATIBILITY_FILE)
            if any(name == prefix or name.startswith(prefix + ".") for prefix in self.FORBIDDEN_PREFIXES)
        ]
        assert violations == [], f"app/core/schema_compatibility.py imports forbidden module(s): {violations}"

    def test_version_module_imports_nothing_economic_or_ai(self):
        violations = [
            name
            for name in _imported_module_names(_VERSION_FILE)
            if any(name == prefix or name.startswith(prefix + ".") for prefix in self.FORBIDDEN_PREFIXES)
        ]
        assert violations == [], f"app/core/version.py imports forbidden module(s): {violations}"


class TestNoMutationCapability:
    """#26C source prompt §51: the compatibility module must not
    import/call `alembic.command.upgrade`, `metadata.create_all`, or
    any other DDL-issuing helper -- it only ever reads."""

    def test_never_imports_alembic_command(self):
        imported = _imported_module_names(_SCHEMA_COMPATIBILITY_FILE)
        assert "alembic.command" not in imported
        assert not any(name.startswith("alembic.command.") for name in imported)

    def test_never_calls_create_all_or_upgrade_or_downgrade(self):
        code = _code_only(_SCHEMA_COMPATIBILITY_FILE)
        for forbidden in ("create_all(", "command.upgrade(", "command.downgrade(", ".upgrade(", ".downgrade("):
            assert forbidden not in code, f"app/core/schema_compatibility.py appears to call {forbidden!r}"

    def test_only_select_statements_are_issued(self):
        """Every `text(...)` SQL literal in this module is a read-only
        SELECT -- a structural proxy for "never issues DDL/DML"."""
        tree = _tree(_SCHEMA_COMPATIBILITY_FILE)
        sql_literals = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "text":
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        sql_literals.append(arg.value)
        assert sql_literals != [], "expected at least one text(...) SQL literal in this module"
        for literal in sql_literals:
            assert literal.strip().upper().startswith("SELECT"), f"non-SELECT SQL literal found: {literal!r}"


class TestReadinessRouteBoundedResponsibility:
    """#26C source prompt §53: the readiness route may call the
    compatibility service (and the version helper) only -- no economic
    service, no FRED client, no AI service."""

    FORBIDDEN_NAMES = (
        "FREDClient",
        "AIService",
        "ReleaseProcessingService",
        "MaintenanceOrchestrator",
        "SinceLastVisitService",
        "InflationMonitorService",
        "LaborMonitorService",
        "AnalysisService",
        "SeriesDiscoveryService",
        "ReleaseReadService",
        "ReleaseSyncService",
        "EconomicDataService",
        "ReleaseProcessingReadService",
        "openai",
    )

    def _readiness_function_source(self) -> str:
        tree = _tree(_MAIN_FILE)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "readiness":
                segment = ast.get_source_segment(_source(_MAIN_FILE), node)
                assert segment is not None
                return segment
        raise AssertionError("could not find a `readiness` function in app/main.py")

    def test_readiness_function_exists(self):
        assert self._readiness_function_source() != ""

    def test_readiness_function_body_references_no_forbidden_service(self):
        body = self._readiness_function_source()
        violations = [name for name in self.FORBIDDEN_NAMES if name in body]
        assert violations == [], f"/readiness route references forbidden service(s): {violations}"

    def test_readiness_function_never_calls_an_external_provider(self):
        body = self._readiness_function_source()
        code_only = re.sub(r'"""[\s\S]*?"""', "", body)
        assert "fred" not in code_only.lower()
        assert "openai" not in code_only.lower()


class TestWorkerPreflightOrder:
    """#26C source prompt §54: the compatibility check occurs BEFORE
    any economic processing could begin -- proven structurally by
    comparing source-line position of the compatibility-check call
    against the first economic-service construction, inside each
    CLI's own `main()` function."""

    def _main_function(self, file_path: Path) -> ast.FunctionDef:
        tree = _tree(file_path)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "main":
                return node
        raise AssertionError(f"could not find a `main` function in {file_path}")

    def _first_call_lineno(self, function: ast.FunctionDef, call_name: str) -> int | None:
        linenos = [
            node.lineno
            for node in ast.walk(function)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == call_name
        ]
        return min(linenos) if linenos else None

    def test_process_release_checks_compatibility_before_constructing_fred_client(self):
        main_function = self._main_function(_PROCESS_RELEASE_FILE)
        compatibility_line = self._first_call_lineno(main_function, "check_schema_compatibility")
        fred_client_line = self._first_call_lineno(main_function, "FREDClient")
        assert compatibility_line is not None
        assert fred_client_line is not None
        assert compatibility_line < fred_client_line

    def test_run_maintenance_checks_compatibility_before_constructing_fred_client(self):
        main_function = self._main_function(_RUN_MAINTENANCE_FILE)
        compatibility_line = self._first_call_lineno(main_function, "check_schema_compatibility")
        fred_client_line = self._first_call_lineno(main_function, "FREDClient")
        assert compatibility_line is not None
        assert fred_client_line is not None
        assert compatibility_line < fred_client_line

    def test_run_maintenance_checks_compatibility_before_constructing_the_orchestrator(self):
        main_function = self._main_function(_RUN_MAINTENANCE_FILE)
        compatibility_line = self._first_call_lineno(main_function, "check_schema_compatibility")
        orchestrator_line = self._first_call_lineno(main_function, "MaintenanceOrchestrator")
        assert compatibility_line is not None
        assert orchestrator_line is not None
        assert compatibility_line < orchestrator_line

    def test_both_clis_import_the_one_shared_checker_not_a_second_implementation(self):
        for file_path in (_PROCESS_RELEASE_FILE, _RUN_MAINTENANCE_FILE):
            imported = _imported_module_names(file_path)
            assert "app.core.schema_compatibility" in imported, f"{file_path} does not import the shared checker"


class TestSafeErrorOutput:
    """#26C source prompt §55/§60: schema-mismatch diagnostics must be
    possible without ever interpolating a connection string or
    credential into any message, log line, or response body."""

    def test_schema_compatibility_module_never_references_the_raw_database_url(self):
        code = _code_only(_SCHEMA_COMPATIBILITY_FILE)
        assert "settings.database_url" not in code
        assert "DATABASE_URL" not in code

    def test_cli_preflight_failure_messages_never_interpolate_settings_database_url(self):
        for file_path in (_PROCESS_RELEASE_FILE, _RUN_MAINTENANCE_FILE):
            code = _code_only(file_path)
            # The existing, established messages for missing
            # configuration already avoid this; the new schema-mismatch
            # message must too -- checked by absence of the one pattern
            # that would leak it (formatting settings.database_url
            # directly into an f-string/print call).
            assert "{settings.database_url}" not in code
            assert "settings.database_url}" not in code
