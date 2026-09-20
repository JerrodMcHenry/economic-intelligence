"""Architectural guards for point-in-time intelligence history
(Increment #32).

Pure source/AST inspection -- no database, no network, no TestClient.

The invariant worth protecting here is narrow and specific: this feature
reads history and re-executes frozen methodologies, and it must never
acquire the ability to write any of it. A read surface that can write to
`recorded_monitor_results` or `observation_versions` would quietly turn
append-only evidence into something a page view can edit.
"""

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

#: The #32 quartet -- models, repository, service, router. Listed
#: explicitly (the convention every other per-increment guard here
#: follows) so adding a file to this feature is a deliberate act that
#: shows up in review.
MONITOR_HISTORY_FILES = [
    REPO_ROOT / "app/models/monitor_history.py",
    REPO_ROOT / "app/repositories/monitor_history_repository.py",
    REPO_ROOT / "app/services/monitor_history.py",
    REPO_ROOT / "app/api/monitor_history.py",
]

#: Calls that would make this read surface a writer.
FORBIDDEN_CALLS = (
    "add_recorded_monitor_result",
    "add_observation_update",
    "add_analysis_update",
    "add_check_run",
    "write_observation",
    "create_series",
)

#: An AI/probabilistic dependency has no place in a deterministic
#: reproduction surface.
FORBIDDEN_MODULE_PREFIXES = ("openai", "app.services.ai", "app.clients.fred", "app.clients.treasury")


def _code_only(path: Path) -> str:
    """Source with docstrings and comments removed, so a guard matching
    a forbidden name cannot be tripped by prose that merely explains
    why the name is forbidden."""
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant):
                if isinstance(node.body[0].value.value, str):
                    node.body.pop(0)
    return ast.unparse(tree)


def _imported_module_names(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_every_declared_file_exists():
    """A guard listing files that do not exist proves nothing."""
    missing = [str(path.relative_to(REPO_ROOT)) for path in MONITOR_HISTORY_FILES if not path.exists()]
    assert missing == []


@pytest.mark.parametrize("path", MONITOR_HISTORY_FILES, ids=lambda p: p.name)
def test_no_ai_or_provider_client_in_the_history_surface(path):
    imported = _imported_module_names(path)
    offenders = [name for name in imported for prefix in FORBIDDEN_MODULE_PREFIXES if name.startswith(prefix)]
    assert offenders == []


@pytest.mark.parametrize("path", MONITOR_HISTORY_FILES, ids=lambda p: p.name)
def test_the_history_surface_never_calls_a_write_path(path):
    code = _code_only(path)
    offenders = [name for name in FORBIDDEN_CALLS if name in code]
    assert offenders == []


def test_the_repository_exposes_no_write_shaped_method_and_owns_no_transaction():
    """Mirrors `#19B`'s own read-repository guard: transaction control
    belongs to `session_scope()`, and a read model has no business
    holding it."""
    path = REPO_ROOT / "app/repositories/monitor_history_repository.py"
    tree = ast.parse(path.read_text())
    classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    methods = [item.name for cls in classes for item in cls.body if isinstance(item, ast.FunctionDef)]

    write_shaped = [
        name
        for name in methods
        if not name.startswith("_")
        and name.split("_")[0] in {"add", "write", "create", "update", "delete", "upsert", "set"}
    ]
    assert write_shaped == []

    code = _code_only(path)
    for fragment in (".flush(", ".commit(", ".rollback(", "session.add(", "session.delete("):
        assert fragment not in code, f"{fragment} must not appear in a read repository"


def test_the_service_never_imports_a_write_repository():
    imported = _imported_module_names(REPO_ROOT / "app/services/monitor_history.py")
    assert "app.repositories.release_processing_repository" not in imported
    assert "app.services.release_processing" not in imported


def test_the_router_is_read_only():
    """GET only. History is evidence; an HTTP verb that could alter it
    must not exist."""
    source = (REPO_ROOT / "app/api/monitor_history.py").read_text()
    for verb in ("@router.post(", "@router.put(", "@router.patch(", "@router.delete("):
        assert verb not in source
    assert source.count("@router.get(") == 2


def test_the_route_paths_are_exactly_the_two_contracted_ones():
    from app.api.monitor_history import router

    assert sorted(route.path for route in router.routes) == [
        "/monitors/{monitor}/history",
        "/monitors/{monitor}/history/{recorded_result_id}",
    ]


def test_rates_is_absent_from_the_history_monitor_vocabulary():
    """Rates has observation versioning (#31) but records no monitor
    state. Adding it here would require inventing one."""
    from app.models.monitor_history import HistoryMonitor

    assert set(HistoryMonitor.__args__) == {"inflation", "labor"}


def test_the_contracted_enumerations_are_frozen():
    from app.models.monitor_history import ComparisonStatus, InputComparison, InputUnit, NotComparableReason

    assert set(InputComparison.__args__) == {"UNCHANGED", "REVISED", "ONLY_AVAILABLE_TODAY", "ONLY_AVAILABLE_THEN"}
    assert set(ComparisonStatus.__args__) == {"IDENTICAL_INPUTS", "INPUTS_CHANGED", "NOT_COMPARABLE"}
    assert set(NotComparableReason.__args__) == {"REPLAY_UNAVAILABLE", "METHODOLOGY_VERSION_DIFFERS"}
    assert set(InputUnit.__args__) == {"INDEX", "JOBS", "PERCENT"}


def test_replay_outcomes_are_reused_verbatim_rather_than_redefined():
    """The surface must not invent its own vocabulary for replay --
    a frontend-visible "VERIFIED" that is not one of #31's own outcomes
    would be a claim the engine never made."""
    from app.models.monitor_history import ReplaySummary
    from app.models.replay import ReplayOutcome

    annotation = ReplaySummary.model_fields["outcome"].annotation
    assert annotation is ReplayOutcome or set(getattr(annotation, "__args__", ())) == set(ReplayOutcome.__args__)


def test_no_field_in_the_contract_asserts_causation():
    """The database records no causal edge between a data change and a
    computation (ADR-023). Field names must not imply one."""
    source = (REPO_ROOT / "app/models/monitor_history.py").read_text()
    tree = ast.parse(source)
    field_names = {
        item.target.id
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
        for item in node.body
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
    }
    causal = {name for name in field_names if any(word in name for word in ("caused", "cause", "because", "due_to", "triggered_by"))}
    assert causal == set()


def test_the_models_module_has_no_framework_or_orm_dependency():
    imported = _imported_module_names(REPO_ROOT / "app/models/monitor_history.py")
    assert not any(name.startswith(("fastapi", "sqlalchemy", "app.db")) for name in imported)
