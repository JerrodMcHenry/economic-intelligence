"""Architectural guards for Increment #26E's maintenance-health
check and scheduler template. Same static-inspection discipline every
prior increment's own dedicated guard file already applies. Frozen
contract: docs/product/production-reliability-deployment-v1.md (#26B)
§26/§36-40/§51, docs/product/automated-economic-maintenance-v1.md.
"""

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_DOMAIN_FILE = Path("app/domain/maintenance_health.py")
_SERVICE_FILE = Path("app/services/maintenance_health.py")
_CLI_FILE = Path("app/operations/maintenance_health.py")
_MAIN_FILE = Path("app/main.py")
_CI_WORKFLOW = Path(".github/workflows/ci.yml")
_SCHEDULER_TEMPLATE = Path(".github/workflows/scheduled-maintenance.yml.disabled")


def _source(file_path: Path) -> str:
    return (REPO_ROOT / file_path).read_text()


def _code_only(file_path: Path) -> str:
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


class TestFilesExist:
    def test_all_new_modules_exist(self):
        for file_path in (_DOMAIN_FILE, _SERVICE_FILE, _CLI_FILE):
            assert (REPO_ROOT / file_path).is_file(), f"expected {file_path} to exist"


class TestDomainModuleIsPure:
    """`app/domain/maintenance_health.py` mirrors every other domain
    module in this project (e.g. `app.domain.since_last_visit`): no
    SQLAlchemy, no I/O, no economic dependency, no AI."""

    FORBIDDEN_PREFIXES = (
        "sqlalchemy",
        "app.db",
        "app.repositories",
        "app.services",
        "app.clients",
        "app.api",
        "openai",
    )

    def test_domain_module_imports_nothing_forbidden(self):
        violations = [
            name
            for name in _imported_module_names(_DOMAIN_FILE)
            if any(name == prefix or name.startswith(prefix + ".") for prefix in self.FORBIDDEN_PREFIXES)
        ]
        assert violations == [], f"app/domain/maintenance_health.py imports forbidden module(s): {violations}"

    def test_domain_module_never_reads_the_wall_clock(self):
        """Every `now` this module reasons about must be an explicit
        parameter -- #26E source prompt §60."""
        code = _code_only(_DOMAIN_FILE)
        assert "datetime.now(" not in code
        assert "utcnow(" not in code


class TestServiceAndCliBoundedResponsibility:
    """#26E source prompt §63: health knows operations only -- no
    Inflation/Labor/release-processing/AI dependency, and it never
    calls an external provider (§62)."""

    FORBIDDEN_PREFIXES = (
        "app.services.inflation",
        "app.services.labor",
        "app.services.release_processing",
        "app.services.analysis",
        "app.services.ai",
        "app.services.discovery",
        "app.clients.fred",
        "openai",
    )

    def test_service_module_imports_nothing_forbidden(self):
        violations = [
            name
            for name in _imported_module_names(_SERVICE_FILE)
            if any(name == prefix or name.startswith(prefix + ".") for prefix in self.FORBIDDEN_PREFIXES)
        ]
        assert violations == [], f"app/services/maintenance_health.py imports forbidden module(s): {violations}"

    def test_cli_module_imports_nothing_forbidden(self):
        violations = [
            name
            for name in _imported_module_names(_CLI_FILE)
            if any(name == prefix or name.startswith(prefix + ".") for prefix in self.FORBIDDEN_PREFIXES)
        ]
        assert violations == [], f"app/operations/maintenance_health.py imports forbidden module(s): {violations}"

    def test_service_module_never_references_fred_or_openai_by_name(self):
        code = _code_only(_SERVICE_FILE)
        assert "fred" not in code.lower()
        assert "openai" not in code.lower()


class TestReadOnly:
    """#26E source prompt §18/§61: the health command is read-only --
    no write-shaped call anywhere in the service or CLI."""

    def test_service_module_never_calls_a_write_method(self):
        code = _code_only(_SERVICE_FILE)
        for forbidden in (".add(", ".commit(", ".delete(", ".flush(", "start_sweep(", "finish_sweep("):
            assert forbidden not in code, f"app/services/maintenance_health.py appears to call {forbidden!r}"

    def test_cli_module_never_triggers_a_sweep(self):
        code = _code_only(_CLI_FILE)
        assert "MaintenanceOrchestrator" not in code
        assert "run_sweep" not in code


class TestSharedCompatibilityCheckReused:
    def test_service_reuses_the_shared_schema_compatibility_checker(self):
        imported = _imported_module_names(_SERVICE_FILE)
        assert "app.core.schema_compatibility" in imported


class TestWebNeverStartsScheduler:
    """#26E source prompt §36: FastAPI imports/starts no scheduler --
    reconfirmed here for the maintenance-health module specifically
    (ADR-024's own `TestNoInProcessScheduler` already guards the
    orchestrator itself; this guard covers the new #26E files)."""

    def test_main_module_never_imports_maintenance_health(self):
        imported = _imported_module_names(_MAIN_FILE)
        assert "app.services.maintenance_health" not in imported
        assert "app.operations.maintenance_health" not in imported


class TestNoPublicMaintenanceHealthEndpoint:
    """#26E source prompt §35/§37: maintenance health is operator-only
    -- never added to the public HTTP API."""

    def test_no_api_module_references_maintenance_health(self):
        api_dir = REPO_ROOT / "app" / "api"
        violations = []
        for file_path in sorted(api_dir.glob("*.py")):
            content = file_path.read_text()
            if "maintenance_health" in content:
                violations.append(str(file_path.relative_to(REPO_ROOT)))
        assert violations == [], f"maintenance health referenced from the public API: {violations}"


class TestCiRemainsValidationOnlyNotAScheduler:
    """#26E source prompt §40: adding a scheduler template must never
    put a `schedule:` trigger onto the existing validation CI
    workflow."""

    def test_ci_workflow_has_no_schedule_trigger(self):
        import yaml

        workflow = yaml.safe_load(_source(_CI_WORKFLOW))
        triggers = workflow.get(True, workflow.get("on", {}))
        assert "schedule" not in triggers


class TestSchedulerTemplateIsInertAndCorrect:
    """The scheduler template exists as a `.disabled` file specifically
    so it can never run merely by existing (#26E's own truthfulness
    requirement, taken literally) -- these guards prove its CONTENT is
    still real and correct, without proving activation (which requires
    a real production environment this repository does not have)."""

    def test_template_file_exists_with_the_disabled_suffix(self):
        assert (REPO_ROOT / _SCHEDULER_TEMPLATE).is_file()
        assert not (REPO_ROOT / ".github/workflows/scheduled-maintenance.yml").exists()

    def test_template_is_not_a_recognized_github_actions_workflow_filename(self):
        workflows_dir = REPO_ROOT / ".github" / "workflows"
        recognized = {p.name for p in workflows_dir.glob("*.yml")} | {p.name for p in workflows_dir.glob("*.yaml")}
        assert _SCHEDULER_TEMPLATE.name not in recognized

    def test_template_parses_as_valid_yaml(self):
        import yaml

        workflow = yaml.safe_load(_source(_SCHEDULER_TEMPLATE))
        assert "jobs" in workflow

    def test_template_uses_the_frozen_hourly_order_cadence(self):
        import yaml

        workflow = yaml.safe_load(_source(_SCHEDULER_TEMPLATE))
        triggers = workflow.get(True, workflow.get("on", {}))
        schedules = triggers.get("schedule", [])
        assert schedules != []
        cron = schedules[0]["cron"]
        # Frozen: hourly-order, never sub-hourly (automated-economic-
        # maintenance-v1.md §15) -- the minute field is fixed, every
        # other field is "run every unit of its own kind."
        minute_field = cron.split()[0]
        assert minute_field.isdigit(), f"cadence is not hourly-order: {cron!r}"

    def test_template_invokes_the_exact_production_maintenance_command(self):
        content = str(self._workflow())
        assert "app.operations.run_maintenance" in content

    def test_template_references_secrets_by_name_only_never_a_literal_value(self):
        content = _source(_SCHEDULER_TEMPLATE)
        assert "secrets.DATABASE_URL" in content
        assert "secrets.FRED_API_KEY" in content
        # No literal-looking connection string or key anywhere.
        assert "postgresql://" not in content
        assert "postgresql+psycopg://" not in content

    def test_template_never_runs_a_migration(self):
        content = str(self._workflow())
        assert "app.operations.release" not in content
        assert "alembic" not in content.lower()

    def test_template_never_deploys(self):
        workflow = self._workflow()
        job_names = set(workflow.get("jobs", {}).keys())
        for name in job_names:
            assert "deploy" not in name.lower()

    def _workflow(self) -> dict:
        import yaml

        return yaml.safe_load(_source(_SCHEDULER_TEMPLATE))
