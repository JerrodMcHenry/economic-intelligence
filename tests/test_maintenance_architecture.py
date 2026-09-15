"""Architectural guards for Increment #25C's automated economic
maintenance, checked statically (AST/source inspection) wherever
possible rather than left to convention -- the same discipline
`tests/test_release_processing_architecture.py` already applies to
#18. No database, no FRED, no FastAPI test client -- every check here
is a plain source/model inspection. Frozen contract:
docs/product/automated-economic-maintenance-v1.md.
"""

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

MAINTENANCE_FILES = [
    Path("app/services/maintenance.py"),
    Path("app/repositories/maintenance_repository.py"),
    Path("app/operations/run_maintenance.py"),
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
    def test_maintenance_files_exist_where_expected(self):
        for file_path in MAINTENANCE_FILES:
            assert (REPO_ROOT / file_path).is_file(), f"expected {file_path} to exist"


class TestNoAIOrNewsImports:
    """The maintenance orchestrator contains no AI/news imports
    anywhere in its own files -- frozen contract §48/§71."""

    FORBIDDEN_PREFIXES = ("openai", "app.services.ai", "app.services.news")

    def test_no_maintenance_file_imports_ai_or_news(self):
        violations = []
        for file_path in MAINTENANCE_FILES:
            for module_name in _imported_module_names(file_path):
                if any(module_name == p or module_name.startswith(p + ".") for p in self.FORBIDDEN_PREFIXES):
                    violations.append(f"{file_path}: imports '{module_name}'")
        assert violations == [], "maintenance code imports a forbidden dependency:\n" + "\n".join(violations)


class TestOrchestratorNeverReimplementsEconomicLogic:
    """Guard: `app.services.maintenance` must delegate every actual
    economic/persistence decision to the EXISTING, unmodified
    `ReleaseProcessingService`/`try_acquire_and_process_occurrence` --
    it must import only those top-level entry points from
    `app.services.release_processing`, never a classification
    primitive, never `app.domain.inflation`/`app.domain.labor`
    directly (frozen contract §48's own "must not calculate any
    economic value, classify any monitor state" boundary)."""

    def test_orchestrator_imports_only_the_existing_service_and_lock_wrapper(self):
        source = (REPO_ROOT / "app/services/maintenance.py").read_text()
        tree = ast.parse(source)
        imported_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "app.services.release_processing":
                imported_names.update(alias.name for alias in node.names)
        assert imported_names == {"ReleaseProcessingService", "try_acquire_and_process_occurrence"}, (
            f"app/services/maintenance.py should import only the existing service and its shared lock "
            f"wrapper from app.services.release_processing, found: {imported_names}"
        )

    def test_orchestrator_imports_no_domain_module_directly(self):
        """The orchestrator must never import app.domain.inflation,
        app.domain.labor, or any other domain module -- every economic
        computation belongs entirely to the service it wraps."""
        imported = _imported_module_names(Path("app/services/maintenance.py"))
        forbidden = {m for m in imported if m.startswith("app.domain.")}
        assert forbidden == set(), f"app/services/maintenance.py must not import a domain module directly: {forbidden}"

    FORBIDDEN_PATTERNS: list[tuple[str, str]] = [
        ("compounded-annualization exponent (** (12 / n))", r"\*\*\s*\(?\s*12\s*/\s*\d"),
        ("frozen 0.10pp neutral-band boundary arithmetic", r"[-+]\s*0\.10\b"),
        ("frozen 50,000-job deadband comparison", r"[<>]=?\s*[-+]?\s*50[,_]?000\b"),
        ("frozen 0.2pp unemployment deadband comparison", r"[<>]=?\s*[-+]?\s*0\.2\b"),
    ]

    def test_no_maintenance_file_contains_a_forbidden_formula_pattern(self):
        violations = []
        for file_path in MAINTENANCE_FILES:
            contents = (REPO_ROOT / file_path).read_text()
            for name, pattern in self.FORBIDDEN_PATTERNS:
                if re.search(pattern, contents):
                    violations.append(f"{file_path}: appears to contain {name}")
        assert violations == [], "maintenance code appears to reimplement economic logic:\n" + "\n".join(violations)


class TestNoPublicMaintenanceMutationEndpoint:
    """Guard: no public HTTP route exists anywhere for triggering
    maintenance/processing -- frozen contract §46/§48/§60/§61.
    Automation is operational CLI + external scheduler only."""

    def test_no_maintenance_route_registered_anywhere_in_the_api_layer(self):
        api_dir = REPO_ROOT / "app" / "api"
        forbidden_path_fragments = ("/maintenance", "/sweep", "/process")
        violations = []
        for file_path in sorted(api_dir.glob("*.py")):
            contents = file_path.read_text()
            tree = ast.parse(contents, filename=str(file_path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if not (isinstance(node.func, ast.Attribute) and node.func.attr in {"post", "put", "patch", "delete"}):
                    continue
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        if any(fragment in arg.value for fragment in forbidden_path_fragments):
                            violations.append(f"{file_path.name}: route '{arg.value}'")
        assert violations == [], "a public HTTP route for maintenance exists:\n" + "\n".join(violations)

    def test_maintenance_orchestrator_is_never_imported_by_the_api_layer(self):
        """Even a differently-named route can't reach the sweep if
        nothing in app/api/ imports the orchestrator that runs it."""
        api_dir = REPO_ROOT / "app" / "api"
        violations = []
        for file_path in sorted(api_dir.glob("*.py")):
            imported = _imported_module_names(file_path.relative_to(REPO_ROOT))
            if any(m == "app.services.maintenance" or m.startswith("app.services.maintenance.") for m in imported):
                violations.append(file_path.name)
        assert violations == [], f"app/api/ imports app.services.maintenance: {violations}"


class TestNoInProcessScheduler:
    """Guard: no scheduler dependency, and no scheduler-shaped code, is
    added to the FastAPI application itself -- frozen contract §45/§49.
    The scheduler is external; `app.main`'s own startup must remain
    unaware of maintenance entirely."""

    def test_no_scheduler_dependency_declared(self):
        pyproject = (REPO_ROOT / "pyproject.toml").read_text()
        forbidden = ("apscheduler", "celery", "redis", "rq")
        found = [name for name in forbidden if name in pyproject.lower()]
        assert found == [], f"a scheduler/job-queue dependency was added: {found}"

    def test_fastapi_app_module_never_imports_the_maintenance_orchestrator(self):
        main_source = (REPO_ROOT / "app/main.py").read_text()
        assert "maintenance" not in main_source.lower(), (
            "app/main.py references 'maintenance' -- the orchestrator must never be wired into the "
            "web process's own startup/lifecycle (frozen contract §45)"
        )


class TestNoRecordedStatePersistence:
    """Guard: #25C deliberately does not introduce recorded-canonical-
    state/monitor-snapshot persistence -- frozen contract §35/§43/§46,
    explicitly deferred to a future, separate increment. Mirrors
    `tests/test_release_processing_architecture.py::TestNoFullMonitorSnapshot`'s
    identical discipline, extended to this increment's own new table."""

    def test_no_monitor_or_state_snapshot_table_exists_on_the_orm_base(self):
        from app.db.base import Base

        forbidden_substrings = ("snapshot", "monitor_result", "recorded_state", "historical_state")
        table_names = set(Base.metadata.tables.keys())
        violations = {name for name in table_names if any(s in name.lower() for s in forbidden_substrings)}
        assert violations == set(), f"a monitor-snapshot-shaped table exists: {violations}"

    def test_maintenance_sweep_has_exactly_the_frozen_operational_columns(self):
        """A structural proof that `maintenance_sweeps` stays
        operational-health-shaped -- no economic/state-shaped column
        was smuggled in."""
        from app.db.models import MaintenanceSweep

        column_names = {column.name for column in MaintenanceSweep.__table__.columns}
        assert column_names == {
            "id",
            "started_at",
            "finished_at",
            "status",
            "due_count",
            "processed_count",
            "failed_count",
            "created_at",
        }


class TestNoSinceLastVisitOrWatchlist:
    """Guard: no session/user/localStorage-shaped persistence or API
    surface is introduced -- frozen contract §47/§72, #25D's own scope."""

    def test_no_since_last_visit_or_user_shaped_table_exists(self):
        from app.db.base import Base

        forbidden_substrings = ("last_visit", "watchlist", "user_", "account")
        table_names = set(Base.metadata.tables.keys())
        violations = {name for name in table_names if any(s in name.lower() for s in forbidden_substrings)}
        assert violations == set(), f"a Since-Last-Visit/Watchlist/account-shaped table exists: {violations}"


class TestOccurrenceLockingIsStructural:
    """Guard: every path that calls `ReleaseProcessingService.process_occurrence`
    outside of tests does so via the shared, lock-acquiring wrapper --
    never a direct call that would bypass locking (frozen contract
    §18/§19/§59's own "one safe path, never two" requirement)."""

    def test_process_release_cli_calls_the_lock_wrapper_not_the_bare_service_method(self):
        source = (REPO_ROOT / "app/operations/process_release.py").read_text()
        assert "try_acquire_and_process_occurrence" in source
        assert re.search(r"\bservice\.process_occurrence\(", source) is None, (
            "app/operations/process_release.py calls service.process_occurrence directly -- "
            "it must go through try_acquire_and_process_occurrence so the manual and automated "
            "paths can never diverge in locking behavior (§59)"
        )

    def test_orchestrator_calls_the_lock_wrapper_not_the_bare_service_method(self):
        source = (REPO_ROOT / "app/services/maintenance.py").read_text()
        assert "try_acquire_and_process_occurrence" in source
        assert re.search(r"self\._service\.process_occurrence\(", source) is None, (
            "app/services/maintenance.py calls self._service.process_occurrence directly -- "
            "it must go through try_acquire_and_process_occurrence (§18/§19)"
        )


class TestNoServerLocalTimezoneDependence:
    """Guard: no bare, timezone-naive `datetime.now()`/`date.today()`
    call exists anywhere in the new orchestration code -- frozen
    contract §16/§57. Every clock read must be explicit and UTC-aware."""

    NAIVE_CLOCK_PATTERN = re.compile(r"\bdatetime\.now\(\)|(?<!timezone\.utc\))\bdate\.today\(\)")

    def test_no_naive_clock_read_in_maintenance_files(self):
        violations = []
        for file_path in MAINTENANCE_FILES:
            contents = (REPO_ROOT / file_path).read_text()
            if re.search(r"\bdatetime\.now\(\)", contents):
                violations.append(f"{file_path}: bare datetime.now() (no explicit timezone)")
            if re.search(r"\bdate\.today\(\)", contents):
                violations.append(f"{file_path}: bare date.today() (server-local, no explicit UTC)")
        assert violations == [], "server-local/timezone-naive clock read found:\n" + "\n".join(violations)

    def test_every_datetime_now_call_passes_timezone_utc_explicitly(self):
        violations = []
        for file_path in MAINTENANCE_FILES:
            contents = (REPO_ROOT / file_path).read_text()
            for match in re.finditer(r"datetime\.now\(([^)]*)\)", contents):
                if "timezone.utc" not in match.group(1):
                    violations.append(f"{file_path}: datetime.now({match.group(1)}) without timezone.utc")
        assert violations == [], "a datetime.now() call without an explicit timezone.utc argument found:\n" + "\n".join(violations)


class TestNoJoltsOrCivpartInMaintenance:
    """JOLTS/CIVPART remain deferred -- neither should appear anywhere
    in the maintenance call graph, mirroring
    `tests/test_release_processing_architecture.py::TestNoJoltsOrCivpartInReleaseProcessing`'s
    identical discipline."""

    def test_no_jolts_or_civpart_anywhere_in_maintenance_files(self):
        forbidden = ("JTSJOR", "JTSQUR", "JTSHIR", "JTSJOL", "JTSQUL", "JTSHIL", "JTSLDR", "JTSLDL", "CIVPART")
        violations = []
        for file_path in MAINTENANCE_FILES:
            contents = (REPO_ROOT / file_path).read_text()
            for term in forbidden:
                if term in contents:
                    violations.append(f"{file_path}: references {term}")
        assert violations == [], "JOLTS/CIVPART deferred but appear in maintenance files:\n" + "\n".join(violations)


class TestMaintenanceSweepStatusVocabulary:
    """Frozen contract §54: the sweep record's own `status` column is a
    plain string, not an enum requiring a migration to extend --
    mirrors `ReleaseCheckRun.status`'s own identical, already-frozen
    precedent."""

    def test_status_column_is_a_plain_string(self):
        from sqlalchemy import String

        from app.db.models import MaintenanceSweep

        status_column = MaintenanceSweep.__table__.columns["status"]
        assert isinstance(status_column.type, String)

    def test_finished_at_status_and_counts_are_all_nullable(self):
        """Structural proof of §52/§25's own "started but never
        finished" signal: every field written only at completion must
        be nullable, so a crash mid-sweep leaves an honestly incomplete
        row rather than a fabricated default."""
        from app.db.models import MaintenanceSweep

        nullable_columns = {"finished_at", "status", "due_count", "processed_count", "failed_count"}
        for column_name in nullable_columns:
            column = MaintenanceSweep.__table__.columns[column_name]
            assert column.nullable, f"MaintenanceSweep.{column_name} must be nullable"
        assert not MaintenanceSweep.__table__.columns["started_at"].nullable
