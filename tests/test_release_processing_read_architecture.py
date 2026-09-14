"""Architectural guards for Increment #19B's public release-processing
read model, checked statically (AST/source inspection) wherever
possible rather than left to convention -- the same discipline
tests/test_release_processing_architecture.py already applies to #18.
No database, no FRED, no FastAPI test client -- every check here is a
plain source/model inspection.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

READ_MODEL_FILES = [
    Path("app/models/release_processing_read.py"),
    Path("app/repositories/release_processing_read_repository.py"),
    Path("app/services/release_processing_read.py"),
    Path("app/api/release_processing_read.py"),
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


class TestReadModelFilesExist:
    def test_read_model_files_exist_where_expected(self):
        for file_path in READ_MODEL_FILES:
            assert (REPO_ROOT / file_path).is_file(), f"expected {file_path} to exist"


class TestNoFREDOrAIImports:
    """Guard: the #19B read model contains no FRED/AI/news imports
    anywhere in its own files -- it is database-only, always."""

    FORBIDDEN_PREFIXES = ("openai", "app.services.ai", "app.services.news", "httpx", "app.clients.fred")

    def test_no_read_model_file_imports_fred_ai_or_news(self):
        violations = []
        for file_path in READ_MODEL_FILES:
            for module_name in _imported_module_names(file_path):
                if any(module_name == p or module_name.startswith(p + ".") for p in self.FORBIDDEN_PREFIXES):
                    violations.append(f"{file_path}: imports '{module_name}'")
        assert violations == [], "release-processing read model imports a forbidden dependency:\n" + "\n".join(violations)


class TestReadServiceDoesNotReuseWriteService:
    """Guard: `ReleaseProcessingReadService` is a distinct class from
    `ReleaseProcessingService` (#18's write orchestrator) -- checked
    directly by confirming the read service module never imports it."""

    def test_read_service_does_not_import_the_write_service(self):
        imported = _imported_module_names(Path("app/services/release_processing_read.py"))
        assert "app.services.release_processing" not in imported

    def test_read_repository_does_not_import_the_write_repository(self):
        imported = _imported_module_names(Path("app/repositories/release_processing_read_repository.py"))
        assert "app.repositories.release_processing_repository" not in imported


class TestReadRepositoryHasNoWriteMethod:
    """Guard: `ReleaseProcessingReadRepository` has no method that
    could mutate the database -- checked structurally by scanning its
    own method names, not left to convention."""

    def test_read_repository_has_no_write_shaped_method_name(self):
        from app.repositories.release_processing_read_repository import ReleaseProcessingReadRepository

        forbidden_prefixes = ("add_", "write_", "create_", "update_", "delete_", "upsert_")
        method_names = [name for name in dir(ReleaseProcessingReadRepository) if not name.startswith("_")]
        violations = [name for name in method_names if any(name.startswith(p) for p in forbidden_prefixes)]
        assert violations == [], f"ReleaseProcessingReadRepository has a write-shaped method: {violations}"

    def test_read_repository_never_calls_flush_commit_or_rollback(self):
        source = (REPO_ROOT / "app/repositories/release_processing_read_repository.py").read_text()
        for forbidden in (".flush(", ".commit(", ".rollback(", "session.add(", "session.delete("):
            assert forbidden not in source, f"read repository calls {forbidden!r} -- must remain read-only"


class TestExactlyOneProcessingStatusEndpoint:
    """Guard: exactly ONE public route exists for this resource --
    `GET /releases/processing-status` -- and specifically NOT an
    occurrence-detail route (`GET /releases/{occurrence_id}/processing-status`),
    which the frozen #19B spec explicitly defers."""

    def test_route_module_registers_exactly_one_route(self):
        source = (REPO_ROOT / "app/api/release_processing_read.py").read_text()
        tree = ast.parse(source)
        route_decorators = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Attribute) and node.func.attr in {"get", "post", "put", "patch", "delete"}:
                route_decorators.append(node)
        assert len(route_decorators) == 1, f"expected exactly one route, found {len(route_decorators)}"

    def test_no_occurrence_scoped_processing_status_route_exists_anywhere(self):
        api_dir = REPO_ROOT / "app" / "api"
        violations = []
        for file_path in sorted(api_dir.glob("*.py")):
            contents = file_path.read_text()
            if "{occurrence_id}" in contents and "processing-status" in contents:
                violations.append(file_path.name)
        assert violations == [], f"an occurrence-scoped processing-status route exists: {violations}"

    def test_route_path_is_exactly_processing_status(self):
        from app.api.release_processing_read import router

        paths = [route.path for route in router.routes]
        assert paths == ["/releases/processing-status"]


class TestNoNotApplicableStatus:
    """Guard: the public `ProcessingStatus` enum has exactly the five
    frozen values -- no `NOT_APPLICABLE`."""

    def test_processing_status_literal_has_exactly_the_five_frozen_values(self):
        from app.models.release_processing_read import ProcessingStatus

        assert set(ProcessingStatus.__args__) == {
            "NOT_CHECKED",
            "NO_CHANGE",
            "CHANGES_DETECTED",
            "PARTIAL_CHECK",
            "CHECK_FAILED",
        }

    def test_no_read_model_file_mentions_not_applicable(self):
        for file_path in READ_MODEL_FILES:
            contents = (REPO_ROOT / file_path).read_text()
            assert "NOT_APPLICABLE" not in contents, f"{file_path} mentions NOT_APPLICABLE -- frozen against #19B"


class TestNoCausalNestingBetweenObservationAndAnalysisChanges:
    """Guard: `ReleaseProcessingStatusItem` exposes
    `detected_observation_changes`/`detected_analysis_changes` as
    SIBLING top-level fields -- never one nested inside the other, and
    never a `detected_change` wrapper object."""

    def test_item_has_both_arrays_as_top_level_sibling_fields(self):
        from app.models.release_processing_read import ReleaseProcessingStatusItem

        field_names = set(ReleaseProcessingStatusItem.model_fields.keys())
        assert {"detected_observation_changes", "detected_analysis_changes"} <= field_names

    def test_analysis_change_model_has_no_reference_to_an_observation_update(self):
        from app.models.release_processing_read import DetectedAnalysisChange

        field_names = set(DetectedAnalysisChange.model_fields.keys())
        forbidden_substrings = ("observation", "release_observation_update")
        violations = {name for name in field_names if any(s in name.lower() for s in forbidden_substrings)}
        assert violations == set(), f"DetectedAnalysisChange references an observation update: {violations}"

    def test_observation_change_model_has_no_reference_to_an_analysis_update(self):
        from app.models.release_processing_read import DetectedObservationChange

        field_names = set(DetectedObservationChange.model_fields.keys())
        forbidden_substrings = ("analysis", "release_analysis_update")
        violations = {name for name in field_names if any(s in name.lower() for s in forbidden_substrings)}
        assert violations == set(), f"DetectedObservationChange references an analysis update: {violations}"

    def test_no_read_model_file_mentions_a_detected_change_wrapper(self):
        # "detected_change" (singular, no "s") never appears as its own
        # identifier fragment in any read-model file -- the rejected
        # `detected_change { observation, analysis_consequences[] }`
        # wrapper shape from the #19B audit, and "analysis_consequences"
        # specifically, must never resurface here.
        forbidden_substrings = ("detected_change(", "detected_change:", "detected_change =", "analysis_consequences")
        for file_path in READ_MODEL_FILES:
            contents = (REPO_ROOT / file_path).read_text()
            violations = [s for s in forbidden_substrings if s in contents]
            assert violations == [], f"{file_path} references a rejected causal-nesting shape: {violations}"


class TestNoSuccessFailureCountFabrication:
    """Guard: `LatestCheck` carries no `successful_series_count`/
    `failed_series_count` -- V1 deliberately omits them rather than
    approximate (see app/models/release_processing_read.py's
    docstring)."""

    def test_latest_check_has_no_series_count_field(self):
        from app.models.release_processing_read import LatestCheck

        field_names = {name.lower() for name in LatestCheck.model_fields.keys()}
        violations = {name for name in field_names if "count" in name}
        assert violations == set(), f"LatestCheck has an unexpected count field: {violations}"
