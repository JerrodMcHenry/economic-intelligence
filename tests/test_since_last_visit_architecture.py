"""Architectural guards for Increment #25G's Since Last Visit V1
backend read model, checked statically (AST/source inspection)
wherever possible -- the same discipline
`tests/test_recorded_monitor_result_architecture.py`/
`tests/test_maintenance_architecture.py` already apply to #25E/#25C.
No database, no FRED, no FastAPI test client -- every check here is a
plain source/model inspection. Frozen contract:
docs/product/since-last-visit-v1.md (#25F).
"""

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SLV_FILES = [
    Path("app/domain/since_last_visit.py"),
    Path("app/repositories/since_last_visit_repository.py"),
    Path("app/services/since_last_visit.py"),
    Path("app/api/since_last_visit.py"),
    Path("app/models/since_last_visit.py"),
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


class TestFilesExist:
    def test_since_last_visit_files_exist_where_expected(self):
        for file_path in SLV_FILES:
            assert (REPO_ROOT / file_path).is_file(), f"expected {file_path} to exist"


class TestNoAIImport:
    """Contract §119: no AI/LLM import anywhere in the new module set."""

    FORBIDDEN_PREFIXES = ("openai", "app.services.ai")

    def test_no_since_last_visit_file_imports_ai(self):
        violations = []
        for file_path in SLV_FILES:
            for module_name in _imported_module_names(file_path):
                if any(module_name == p or module_name.startswith(p + ".") for p in self.FORBIDDEN_PREFIXES):
                    violations.append(f"{file_path}: imports '{module_name}'")
        assert violations == [], "since-last-visit code imports a forbidden AI dependency:\n" + "\n".join(violations)


class TestReadOnlyNoWritePath:
    """Contract §4/§67/§129: this feature creates zero economic
    history -- structurally proven, not just tested behaviorally."""

    FORBIDDEN_CALLS = (
        "add_recorded_monitor_result", "add_analysis_update", "add_observation_update", "add_check_run",
        "write_observation", "create_series",
    )

    def test_no_since_last_visit_file_calls_a_write_method(self):
        violations = []
        for file_path in SLV_FILES:
            source = (REPO_ROOT / file_path).read_text()
            for name in self.FORBIDDEN_CALLS:
                if f"{name}(" in source:
                    violations.append(f"{file_path}: calls '{name}('")
        assert violations == [], "since-last-visit code calls a write method:\n" + "\n".join(violations)

    def test_repository_never_calls_commit_or_rollback(self):
        source = (REPO_ROOT / "app/repositories/since_last_visit_repository.py").read_text()
        assert re.search(r"\.commit\s*\(", source) is None
        assert re.search(r"\.rollback\s*\(", source) is None

    def test_repository_imports_no_write_repository(self):
        """Never imports `ReleaseProcessingRepository` (the #18 write
        path) -- this feature reads persisted rows directly via the
        ORM models, never through a write-capable repository."""
        imported = _imported_module_names(Path("app/repositories/since_last_visit_repository.py"))
        assert "app.repositories.release_processing_repository" not in imported


class TestNoDomainMethodologyImport:
    """Contract §47/§103/§129: this is a persisted-history projection
    -- it never imports or calls Inflation/Labor/State Duration's own
    canonical computation, and never reconstructs via State Duration."""

    FORBIDDEN_MODULES = ("app.domain.inflation", "app.domain.labor", "app.domain.state_duration", "app.domain.labor_release_processing", "app.domain.release_processing")

    def test_no_since_last_visit_file_imports_a_canonical_domain_module(self):
        violations = []
        for file_path in SLV_FILES:
            imported = _imported_module_names(file_path)
            for forbidden in self.FORBIDDEN_MODULES:
                if any(m == forbidden or m.startswith(forbidden + ".") for m in imported):
                    violations.append(f"{file_path}: imports '{forbidden}'")
        assert violations == [], "since-last-visit code imports a canonical domain module:\n" + "\n".join(violations)

    def test_no_since_last_visit_file_imports_state_duration_service_methods(self):
        violations = []
        for file_path in SLV_FILES:
            source = (REPO_ROOT / file_path).read_text()
            if "get_state_duration_result" in source or "evaluate_state_duration" in source:
                violations.append(str(file_path))
        assert violations == [], f"since-last-visit code references State Duration: {violations}"


class TestNoMaintenanceTrigger:
    """Contract §42/§129: coverage is derived exclusively from
    persisted `MaintenanceSweep` rows -- this code never imports or
    calls the orchestrator/CLI that WOULD create one."""

    def test_no_since_last_visit_file_imports_the_maintenance_orchestrator(self):
        violations = []
        for file_path in SLV_FILES:
            imported = _imported_module_names(file_path)
            if any(m in ("app.services.maintenance", "app.operations.run_maintenance") for m in imported):
                violations.append(str(file_path))
        assert violations == [], f"since-last-visit code imports the maintenance orchestrator: {violations}"

    def test_no_since_last_visit_file_imports_release_processing_service(self):
        """Never triggers release processing itself either (no FRED
        call, no process_occurrence)."""
        violations = []
        for file_path in SLV_FILES:
            imported = _imported_module_names(file_path)
            if "app.services.release_processing" in imported:
                violations.append(str(file_path))
        assert violations == [], f"since-last-visit code imports the release-processing service: {violations}"

    def test_no_since_last_visit_file_imports_the_fred_client(self):
        violations = []
        for file_path in SLV_FILES:
            imported = _imported_module_names(file_path)
            if any(m == "app.clients.fred" or m.startswith("app.clients.fred.") for m in imported):
                violations.append(str(file_path))
        assert violations == [], f"since-last-visit code imports the FRED client: {violations}"


class TestReadOnlyRoute:
    """Contract §129: `GET /since-last-visit` is the only new route,
    and it is read-only -- no POST/PUT/PATCH/DELETE exists anywhere in
    the new router, mirroring `TestNoPublicMaintenanceMutationEndpoint`'s
    own established precedent."""

    def test_the_new_router_defines_exactly_one_get_route_and_no_mutation_verb(self):
        source = (REPO_ROOT / "app/api/since_last_visit.py").read_text()
        mutation_verbs = ("@router.post(", "@router.put(", "@router.patch(", "@router.delete(")
        for verb in mutation_verbs:
            assert verb not in source, f"since_last_visit.py contains a mutation route: {verb}"
        assert source.count("@router.get(") == 1

    def test_the_router_prefix_is_since_last_visit_not_overview(self):
        source = (REPO_ROOT / "app/api/since_last_visit.py").read_text()
        assert 'prefix="/since-last-visit"' in source
        assert 'prefix="/overview"' not in source


class TestNoAccountOrAuthDependency:
    """Contract §97/§129: no user identity anywhere in V1."""

    FORBIDDEN_SUBSTRINGS = ("user_id", "account_id", "session_id", "Depends(get_current_user", "cookie")

    def test_no_since_last_visit_file_references_user_identity(self):
        violations = []
        for file_path in SLV_FILES:
            source = (REPO_ROOT / file_path).read_text()
            for substring in self.FORBIDDEN_SUBSTRINGS:
                if substring in source:
                    violations.append(f"{file_path}: contains '{substring}'")
        assert violations == [], "since-last-visit code references user identity:\n" + "\n".join(violations)


class TestNoGenericEventLedger:
    """Contract §57/§126/§129: `ReleaseCheckRun` remains the event
    spine -- no new, generic "activity"/"event log" table or module is
    introduced anywhere."""

    def test_no_migration_creates_a_generic_event_or_activity_table(self):
        forbidden_substrings = ("event_log", "activity_log", "activity_feed", "user_events", "audit_log")
        violations = []
        for path in (REPO_ROOT / "alembic/versions").glob("*.py"):
            contents = path.read_text().lower()
            for substring in forbidden_substrings:
                if substring in contents:
                    violations.append(f"{path.name}: contains '{substring}'")
        assert violations == [], f"a generic event-ledger-shaped migration exists: {violations}"

    def test_no_since_last_visit_migration_exists_at_all(self):
        """Contract §125: zero migration is required -- every table
        this reads already exists."""
        matches = [
            path.name for path in (REPO_ROOT / "alembic/versions").glob("*.py")
            if "since_last_visit" in path.read_text().lower() or "since-last-visit" in path.read_text().lower()
        ]
        assert matches == [], f"an unexpected since-last-visit migration exists: {matches}"


class TestPureDomainModuleHasNoIO:
    """Contract §62/§81: the categorization module is pure -- no
    SQLAlchemy, no Session, no database I/O of any kind."""

    def test_domain_module_imports_no_sqlalchemy_or_orm_model(self):
        imported = _imported_module_names(Path("app/domain/since_last_visit.py"))
        violations = {m for m in imported if m.startswith("sqlalchemy") or m.startswith("app.db")}
        assert violations == set(), f"the pure domain module imports persistence code: {violations}"

    def test_domain_module_defines_no_session_parameter(self):
        """A source-level substring check would false-positive on this
        module's own docstrings (which correctly explain, in prose,
        that no `Session` is ever accepted) -- an AST check for an
        actual `Session`-typed parameter is the precise guard."""
        tree = ast.parse((REPO_ROOT / "app/domain/since_last_visit.py").read_text())
        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for arg in node.args.args:
                    if arg.annotation is not None and "Session" in ast.dump(arg.annotation):
                        violations.append(f"{node.name}({arg.arg})")
        assert violations == [], f"a pure domain function accepts a Session-typed parameter: {violations}"
