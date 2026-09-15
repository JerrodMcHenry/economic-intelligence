"""Architectural guards for Increment #25E's Recorded State History V1
persistence, checked statically (AST/source inspection) wherever
possible rather than left to convention -- the same discipline
`tests/test_maintenance_architecture.py`/
`tests/test_release_processing_architecture.py` already apply to
#25C/#18. No database, no FRED, no FastAPI test client -- every check
here is a plain source/model inspection. Frozen contract:
docs/product/recorded-state-history-v1.md (#25D).
"""

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DOMAIN_FILES = [
    Path("app/domain/inflation.py"),
    Path("app/domain/labor.py"),
]
API_FILES = sorted((REPO_ROOT / "app/api").glob("*.py"))
STATE_DURATION_FILES = [
    Path("app/domain/state_duration.py"),
    # State Duration's own service methods live inside each existing
    # monitor service (contract §47/§67; state-duration-v1.md §28's own
    # "two separate, monitor-specific service methods added to the
    # existing service" decision -- there is no standalone
    # app/services/state_duration.py module).
    Path("app/services/inflation.py"),
    Path("app/services/labor.py"),
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
    def test_recorded_monitor_result_files_exist_where_expected(self):
        assert "class RecordedMonitorResult" in (REPO_ROOT / "app/db/models.py").read_text()
        assert "class RecordableMonitorResult" in (REPO_ROOT / "app/models/release_processing.py").read_text()
        assert "def add_recorded_monitor_result" in (REPO_ROOT / "app/repositories/release_processing_repository.py").read_text()

    def test_exactly_one_migration_creates_recorded_monitor_results(self):
        matches = [
            path for path in (REPO_ROOT / "alembic/versions").glob("*.py")
            if "create_table('recorded_monitor_results'" in path.read_text()
        ]
        assert len(matches) == 1, f"expected exactly one migration creating recorded_monitor_results, found: {matches}"


class TestDomainPurity:
    """Contract §60/§83: `app/domain/inflation.py`/`labor.py` are
    completely unmodified by this feature -- they must know nothing
    about SQLAlchemy, `RecordedMonitorResult`, or any repository."""

    def test_domain_modules_import_no_persistence_or_recorded_result_code(self):
        violations = []
        for file_path in DOMAIN_FILES:
            for module_name in _imported_module_names(file_path):
                if module_name.startswith("sqlalchemy") or module_name.startswith("app.repositories") or module_name.startswith("app.db"):
                    violations.append(f"{file_path}: imports '{module_name}'")
        assert violations == [], "a pure domain module imports persistence code:\n" + "\n".join(violations)

    def test_domain_modules_never_reference_recorded_monitor_result_by_name(self):
        violations = []
        for file_path in DOMAIN_FILES:
            contents = (REPO_ROOT / file_path).read_text()
            if "RecordedMonitorResult" in contents or "RecordableMonitorResult" in contents:
                violations.append(str(file_path))
        assert violations == [], f"a pure domain module references the recorded-result type: {violations}"


class TestRepositoryNeverCommitsOrRollsBack:
    """Contract §61: the repository never calls commit()/rollback()
    itself -- the caller owns the transaction boundary, exactly like
    every other repository in this project."""

    def test_release_processing_repository_never_commits_or_rolls_back(self):
        source = (REPO_ROOT / "app/repositories/release_processing_repository.py").read_text()
        assert re.search(r"\.commit\s*\(", source) is None
        assert re.search(r"\.rollback\s*\(", source) is None


class TestReadSideNeverWrites:
    """Contract §63: a hard architecture guard -- no route module
    imports `add_recorded_monitor_result` or constructs
    `ReleaseProcessingRepository` for a write."""

    def test_no_api_route_references_the_recorded_result_write_path(self):
        violations = []
        for file_path in API_FILES:
            contents = file_path.read_text()
            if "add_recorded_monitor_result" in contents:
                violations.append(str(file_path.relative_to(REPO_ROOT)))
        assert violations == [], f"a route module references the recorded-result write method: {violations}"

    def test_no_api_route_imports_release_processing_repository(self):
        violations = []
        for file_path in API_FILES:
            module_names = _imported_module_names(Path(file_path.relative_to(REPO_ROOT)))
            if any(m == "app.repositories.release_processing_repository" for m in module_names):
                violations.append(str(file_path.relative_to(REPO_ROOT)))
        assert violations == [], f"a route module imports ReleaseProcessingRepository: {violations}"


class TestStateDurationNeverWritesRecordedMonitorResult:
    """Contract §47/§67: State Duration remains recompute-only -- it
    must never import the recorded-result type or its write path."""

    def test_state_duration_files_do_not_reference_recorded_monitor_result(self):
        violations = []
        for file_path in STATE_DURATION_FILES:
            full_path = REPO_ROOT / file_path
            if not full_path.is_file():
                continue
            contents = full_path.read_text()
            if "RecordedMonitorResult" in contents or "add_recorded_monitor_result" in contents:
                violations.append(str(file_path))
        assert violations == [], f"a State Duration file references RecordedMonitorResult: {violations}"


class TestRelateAndSalienceNeverWriteRecordedMonitorResult:
    """Contract §66/§68: Relate composition and Salience tiering are
    presentation/composition-layer concepts -- neither may ever create
    history."""

    def test_relate_files_do_not_reference_recorded_monitor_result(self):
        candidates = list((REPO_ROOT / "app/domain").glob("relate*.py")) + list((REPO_ROOT / "app/services").glob("relate*.py"))
        violations = [str(p.relative_to(REPO_ROOT)) for p in candidates if "RecordedMonitorResult" in p.read_text()]
        assert violations == [], f"a Relate file references RecordedMonitorResult: {violations}"

    def test_no_frontend_salience_file_references_recorded_monitor_result(self):
        frontend_src = REPO_ROOT / "frontend/src"
        if not frontend_src.is_dir():
            return
        violations = []
        for path in frontend_src.rglob("*alience*"):
            if path.is_file() and "RecordedMonitorResult" in path.read_text(errors="ignore"):
                violations.append(str(path.relative_to(REPO_ROOT)))
        assert violations == [], f"a frontend salience file references RecordedMonitorResult: {violations}"


class TestNoAIImport:
    """Contract §90: AI cannot create, update, or delete any
    RecordedMonitorResult row -- the write path imports no AI/OpenAI/
    LLM dependency."""

    FORBIDDEN_PREFIXES = ("openai", "app.services.ai")

    def test_release_processing_repository_imports_no_ai_dependency(self):
        violations = []
        for module_name in _imported_module_names(Path("app/repositories/release_processing_repository.py")):
            if any(module_name == p or module_name.startswith(p + ".") for p in self.FORBIDDEN_PREFIXES):
                violations.append(module_name)
        assert violations == [], f"the repository imports a forbidden AI dependency: {violations}"

    def test_release_processing_service_imports_no_ai_dependency(self):
        violations = []
        for module_name in _imported_module_names(Path("app/services/release_processing.py")):
            if any(module_name == p or module_name.startswith(p + ".") for p in self.FORBIDDEN_PREFIXES):
                violations.append(module_name)
        assert violations == [], f"the service imports a forbidden AI dependency: {violations}"


class TestAppendOnlyThroughNormalApplicationCode:
    """Contract §30/§53/§88: no update/delete method exists anywhere
    in the repository layer for RecordedMonitorResult, and no
    application code issues an UPDATE/DELETE statement against the
    table."""

    def test_no_update_or_delete_method_exists_for_recorded_monitor_result(self):
        source = (REPO_ROOT / "app/repositories/release_processing_repository.py").read_text()
        forbidden = ("update_recorded", "upsert_recorded", "replace_recorded", "delete_recorded_monitor_result")
        violations = [name for name in forbidden if name in source]
        assert violations == [], f"an update/delete-shaped method name exists for RecordedMonitorResult: {violations}"

    def test_no_application_file_issues_a_raw_update_or_delete_against_the_table(self):
        violations = []
        for path in (REPO_ROOT / "app").rglob("*.py"):
            contents = path.read_text()
            if "recorded_monitor_results" not in contents:
                continue
            if re.search(r"(?i)\bUPDATE\s+recorded_monitor_results\b", contents) or re.search(
                r"(?i)\bDELETE\s+FROM\s+recorded_monitor_results\b", contents
            ):
                violations.append(str(path.relative_to(REPO_ROOT)))
        assert violations == [], f"a raw UPDATE/DELETE against recorded_monitor_results exists: {violations}"


class TestNoBackfill:
    """Contract §51: no migration-time historical rows, no
    reconstruction-to-recording utility, no historical loop inserting
    old monitor results."""

    def test_the_migration_only_creates_schema_never_inserts_data(self):
        matches = [
            path for path in (REPO_ROOT / "alembic/versions").glob("*.py")
            if "create_table('recorded_monitor_results'" in path.read_text()
        ]
        assert len(matches) == 1
        source = matches[0].read_text()
        assert "op.bulk_insert" not in source
        assert "INSERT INTO recorded_monitor_results" not in source
        assert re.search(r"(?i)insert\s+into\s+recorded_monitor_results", source) is None

    def test_no_backfill_or_reconstruction_to_recording_utility_exists(self):
        violations = []
        for path in (REPO_ROOT / "app").rglob("*.py"):
            name = path.name.lower()
            if "backfill" in name and "RecordedMonitorResult" in path.read_text():
                violations.append(str(path.relative_to(REPO_ROOT)))
        assert violations == [], f"a backfill-shaped file references RecordedMonitorResult: {violations}"


class TestGenuineExecutionOnly:
    """Contract §6/§7: recording is reachable ONLY from the existing,
    genuinely-executed AFTER-evidence call site -- structurally proven
    by confirming the repository's write method is invoked from
    exactly one production call site (`process_occurrence`), never
    from a second, independent, or speculative path."""

    def test_add_recorded_monitor_result_is_called_from_exactly_one_production_file(self):
        call_sites = []
        for path in (REPO_ROOT / "app").rglob("*.py"):
            if path.name == "release_processing_repository.py":
                continue  # the method's own definition, not a call site
            if "add_recorded_monitor_result(" in path.read_text():
                call_sites.append(str(path.relative_to(REPO_ROOT)))
        assert call_sites == ["app/services/release_processing.py"], (
            f"add_recorded_monitor_result should be called from exactly one production file "
            f"(app/services/release_processing.py), found: {call_sites}"
        )

    def test_recordable_results_are_built_only_inside_apply_changes_and_compute_analysis(self):
        """Both per-domain builder helpers must be called only from
        inside `_apply_changes_and_compute_analysis` -- never from a
        second, independent computation path. Each helper's own
        `def` line is excluded from the whole-file count (a
        definition is not a call)."""
        source = (REPO_ROOT / "app/services/release_processing.py").read_text()
        tree = ast.parse(source)
        method_source = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_apply_changes_and_compute_analysis":
                method_source = ast.get_source_segment(source, node)
        assert method_source is not None

        for helper in ("_build_inflation_recordable_result", "_build_labor_recordable_result"):
            calls_inside_method = method_source.count(f"{helper}(")
            assert calls_inside_method == 1, f"{helper} must be called exactly once inside _apply_changes_and_compute_analysis"

            calls_in_whole_file = len(re.findall(rf"(?<!def ){re.escape(helper)}\(", source))
            assert calls_in_whole_file == calls_inside_method, (
                f"{helper} is called from somewhere other than _apply_changes_and_compute_analysis"
            )
