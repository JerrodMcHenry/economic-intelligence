"""Architectural guards for Increment #18's release-driven update
pipeline, checked statically (AST/source inspection) wherever possible
rather than left to convention -- the same discipline
tests/test_domain_architectural_independence.py and
tests/integration/test_transaction_and_safety.py already apply to
#17A/#17B. No database, no FRED, no FastAPI test client -- every check
here is a plain source/model inspection.
"""

import ast
from pathlib import Path

from app.db.models import EconomicObservation, ReleaseCheckRun, ReleaseSeriesMapping

REPO_ROOT = Path(__file__).resolve().parent.parent

RELEASE_PROCESSING_FILES = [
    Path("app/domain/release_processing.py"),
    Path("app/repositories/release_processing_repository.py"),
    Path("app/services/release_processing.py"),
    Path("app/operations/process_release.py"),
    Path("app/domain/labor_release_processing.py"),
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


class TestNoAIOrNewsImports:
    """Guard #2: the release-processing subsystem contains no AI/news
    imports anywhere in its own files."""

    FORBIDDEN_PREFIXES = ("openai", "app.services.ai", "app.services.news")

    def test_release_processing_files_exist_where_expected(self):
        for file_path in RELEASE_PROCESSING_FILES:
            assert (REPO_ROOT / file_path).is_file(), f"expected {file_path} to exist"

    def test_no_release_processing_file_imports_ai_or_news(self):
        violations = []
        for file_path in RELEASE_PROCESSING_FILES:
            for module_name in _imported_module_names(file_path):
                if any(module_name == p or module_name.startswith(p + ".") for p in self.FORBIDDEN_PREFIXES):
                    violations.append(f"{file_path}: imports '{module_name}'")
        assert violations == [], "release-processing code imports a forbidden dependency:\n" + "\n".join(violations)


class TestScheduleClassificationCannotWriteObservations:
    """Guard #3: app.domain.releases (schedule status derivation) has
    no path to writing an EconomicObservation -- it imports nothing
    beyond the standard library/typing (already proven generally by
    test_domain_architectural_independence.py's allowlist test; this
    restates it narrowly and explicitly for this one guarantee)."""

    def test_schedule_status_module_imports_nothing_that_could_write_data(self):
        imported = _imported_module_names(Path("app/domain/releases.py"))
        forbidden_prefixes = ("sqlalchemy", "app.repositories", "app.db")
        violations = {m for m in imported if any(m == p or m.startswith(p + ".") for p in forbidden_prefixes)}
        assert violations == set(), f"app/domain/releases.py must never import anything write-capable: {violations}"


class TestNoPublicProcessEndpoint:
    """Guard #4: no public HTTP mutation route for release processing
    exists anywhere in the API layer -- checked by parsing every
    app/api/*.py file's route decorators, not by trusting that no one
    added one to app/api/releases.py specifically (a new router file
    could add one just as easily)."""

    def test_no_process_route_registered_anywhere_in_the_api_layer(self):
        api_dir = REPO_ROOT / "app" / "api"
        forbidden_path_fragments = ("/process", "/occurrences", "/checks")
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
                            violations.append(f"{file_path.name}: mutating route '{arg.value}'")
        assert violations == [], "a public HTTP mutation route for release processing exists:\n" + "\n".join(violations)

    def test_release_processing_service_is_never_imported_by_the_api_layer(self):
        """Even a differently-named route can't reach the pipeline if
        nothing in app/api/ imports the service that performs it."""
        api_dir = REPO_ROOT / "app" / "api"
        violations = []
        for file_path in sorted(api_dir.glob("*.py")):
            imported = _imported_module_names(file_path.relative_to(REPO_ROOT))
            if any(m == "app.services.release_processing" or m.startswith("app.services.release_processing.") for m in imported):
                violations.append(file_path.name)
        assert violations == [], f"app/api/ imports app.services.release_processing: {violations}"


class TestExistingComparisonPrimitivesAreReused:
    """Guard #6: release processing calls the EXISTING
    app.domain.inflation_what_changed comparators rather than
    reimplementing comparison logic -- checked directly by asserting
    the service module actually imports those exact three functions."""

    def test_service_imports_the_existing_comparators_by_name(self):
        source = (REPO_ROOT / "app/services/release_processing.py").read_text()
        tree = ast.parse(source)
        imported_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "app.domain.inflation_what_changed":
                imported_names.update(alias.name for alias in node.names)
        required = {"compare_series_momentum_section", "compare_target_section", "compare_confirmation_section"}
        assert required <= imported_names, f"missing reused comparator imports: {required - imported_names}"

    def test_service_imports_the_existing_exact_period_evaluators_by_name(self):
        source = (REPO_ROOT / "app/services/release_processing.py").read_text()
        tree = ast.parse(source)
        imported_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "app.domain.inflation":
                imported_names.update(alias.name for alias in node.names)
        required = {"compute_series_momentum_at", "compute_target_at", "compute_confirmation_at"}
        assert required <= imported_names, f"missing reused evaluator imports: {required - imported_names}"


class TestExistingLaborComparisonPrimitivesAreReused:
    """Guard #6's Increment #20D.2 sibling: release processing calls
    the EXISTING `app.domain.labor`/`app.domain.labor_what_changed`
    primitives rather than reimplementing `labor_v1.0`/
    `labor_what_changed_v1.0` -- checked directly by asserting the
    service module actually imports those exact functions by name,
    mirroring TestExistingComparisonPrimitivesAreReused's identical
    discipline for Inflation."""

    def test_service_imports_the_existing_labor_evaluator_by_name(self):
        source = (REPO_ROOT / "app/services/release_processing.py").read_text()
        tree = ast.parse(source)
        imported_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "app.domain.labor":
                imported_names.update(alias.name for alias in node.names)
        assert "compute_labor_monitor_result_at" in imported_names, (
            f"app/services/release_processing.py must import compute_labor_monitor_result_at from app.domain.labor, "
            f"found: {imported_names}"
        )

    def test_service_imports_the_existing_labor_comparators_by_name(self):
        source = (REPO_ROOT / "app/services/release_processing.py").read_text()
        tree = ast.parse(source)
        imported_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "app.domain.labor_what_changed":
                imported_names.update(alias.name for alias in node.names)
        required = {"compare_employment_section", "compare_unemployment_section", "compare_labor_state"}
        assert required <= imported_names, f"missing reused Labor comparator imports: {required - imported_names}"

    def test_service_imports_the_labor_propagation_functions_by_name(self):
        source = (REPO_ROOT / "app/services/release_processing.py").read_text()
        tree = ast.parse(source)
        imported_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "app.domain.labor_release_processing":
                imported_names.update(alias.name for alias in node.names)
        assert "labor_affected_evaluation_periods" in imported_names, (
            f"app/services/release_processing.py must import labor_affected_evaluation_periods from "
            f"app.domain.labor_release_processing, found: {imported_names}"
        )


class TestNoInflationThresholdOrClassificationLogicInReleaseProcessing:
    """Guard #7: the same forbidden-pattern discipline
    tests/test_domain_architectural_independence.py's spirit and
    frontend/src/test/no-economic-logic.test.ts already apply, restated
    for #18's own new files -- none of them may contain the frozen
    formula/threshold shapes that would mean classification logic was
    reimplemented rather than reused."""

    FORBIDDEN_PATTERNS: list[tuple[str, str]] = [
        ("compounded-annualization exponent (** (12 / n))", r"\*\*\s*\(?\s*12\s*/\s*\d"),
        ("Math.pow-style annualization", r"pow\([^)]*12\s*/"),
        ("frozen 0.10pp neutral-band boundary arithmetic", r"[-+]\s*0\.10\b"),
        (
            "COOLING/HEATING pair-literal confirmation-relationship derivation",
            r'\[\s*["\']COOLING["\']\s*,\s*["\']HEATING["\']\s*\]|\[\s*["\']HEATING["\']\s*,\s*["\']COOLING["\']\s*\]',
        ),
    ]

    def test_no_release_processing_file_contains_a_forbidden_formula_pattern(self):
        import re

        violations = []
        for file_path in RELEASE_PROCESSING_FILES:
            contents = (REPO_ROOT / file_path).read_text()
            for name, pattern in self.FORBIDDEN_PATTERNS:
                if re.search(pattern, contents):
                    violations.append(f"{file_path}: appears to contain {name}")
        assert violations == [], "release-processing code appears to reimplement Inflation logic:\n" + "\n".join(violations)


class TestNoLaborThresholdOrClassificationLogicInReleaseProcessing:
    """Guard #7's Increment #20D.2 sibling: none of the release-
    processing files may contain a hardcoded `labor_v1.0` deadband
    literal, an employment condition/momentum classification, or the
    `EmploymentState`/`LaborState` agreement tables -- release
    processing must only ever REUSE `app.domain.labor`'s existing
    classification primitives (via `compute_labor_monitor_result_at`,
    guarded above), never reimplement them. Mirrors #20C.2's own
    AST-level comparator-purity guard
    (tests/test_labor_architecture.py::TestWhatChangedComparatorNeverKnowsLaborV1Methodology)."""

    def test_no_release_processing_file_hardcodes_a_frozen_labor_deadband_literal(self):
        forbidden_literals = {50_000, 50_000.0, 0.2}
        violations = []
        for file_path in RELEASE_PROCESSING_FILES:
            tree = ast.parse((REPO_ROOT / file_path).read_text(), filename=str(file_path))
            found = {
                node.value
                for node in ast.walk(tree)
                if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and node.value in forbidden_literals
            }
            if found:
                violations.append(f"{file_path}: hardcodes {found}")
        assert violations == [], "release-processing code hardcodes a frozen labor_v1.0 deadband literal:\n" + "\n".join(violations)

    def test_no_release_processing_file_reimplements_the_employment_or_labor_state_tables(self):
        """A cheap, direct proof against the specific failure mode
        this guard exists for: the frozen table cells themselves
        (e.g. "RECOVERING", the state that only `combine_employment_state`
        produces) never appear as a string literal anywhere in
        release-processing's own code -- if they did, that would mean
        a table was copied/reimplemented rather than reached only via
        `compute_labor_monitor_result_at`'s own return value."""
        forbidden_state_literals = ('"RECOVERING"', "'RECOVERING'", '"STRENGTHENING"', "'STRENGTHENING'")
        violations = []
        for file_path in RELEASE_PROCESSING_FILES:
            contents = (REPO_ROOT / file_path).read_text()
            for literal in forbidden_state_literals:
                if literal in contents:
                    violations.append(f"{file_path}: contains {literal}")
        assert violations == [], "release-processing code appears to reimplement a labor_v1.0 state table:\n" + "\n".join(violations)


class TestNoJoltsOrCivpartInReleaseProcessing:
    """Guard: JOLTS/CIVPART remain deferred from Labor's release
    integration too -- neither should appear anywhere in the release-
    processing call graph, mirroring
    tests/test_labor_architecture.py::TestNoJoltsOrCivpartInV1's
    identical discipline for the Labor Monitor itself."""

    def test_no_jolts_series_id_anywhere_in_release_processing_files(self):
        forbidden = ("JTSJOR", "JTSQUR", "JTSHIR", "JTSJOL", "JTSQUL", "JTSHIL", "JTSLDR", "JTSLDL")
        violations = []
        for file_path in RELEASE_PROCESSING_FILES:
            contents = (REPO_ROOT / file_path).read_text()
            for series_id in forbidden:
                if series_id in contents:
                    violations.append(f"{file_path}: references {series_id}")
        assert violations == [], "JOLTS was deferred but appears in release-processing files:\n" + "\n".join(violations)

    def test_no_civpart_anywhere_in_release_processing_files(self):
        violations = [str(f) for f in RELEASE_PROCESSING_FILES if "CIVPART" in (REPO_ROOT / f).read_text()]
        assert violations == [], f"CIVPART was deferred but appears in: {violations}"


class TestNoFullMonitorSnapshot:
    """Guard #8: no full InflationMonitorResult snapshot table/model
    was introduced for #18. Increment #25E introduced exactly ONE
    deliberate, frozen exception -- `recorded_monitor_results` (see
    docs/product/recorded-state-history-v1.md) -- which is explicitly
    NOT a full snapshot (state only; no evidence/metric columns; see
    `tests/test_recorded_monitor_result_architecture.py`'s own
    dedicated shape guard) and is allow-listed here BY NAME, never by
    loosening the substring match itself -- any OTHER table matching
    these substrings still fails this guard."""

    _ALLOWED_MONITOR_RESULT_TABLE = "recorded_monitor_results"

    def test_no_monitor_snapshot_table_exists_on_the_orm_base(self):
        from app.db.base import Base

        forbidden_substrings = ("snapshot", "monitor_result")
        table_names = set(Base.metadata.tables.keys()) - {self._ALLOWED_MONITOR_RESULT_TABLE}
        violations = {name for name in table_names if any(s in name.lower() for s in forbidden_substrings)}
        assert violations == set(), f"a monitor-snapshot-shaped table exists: {violations}"

    def test_release_analysis_update_does_not_embed_a_full_monitor_result(self):
        """Structural proof at the ORM level: ReleaseAnalysisUpdate has
        no column typed to hold a full canonical result object (e.g. a
        JSON/JSONB column) -- every column is a small, typed scalar."""
        from sqlalchemy import Date, DateTime, Float, String

        from app.db.models import ReleaseAnalysisUpdate

        allowed_types = (Date, DateTime, Float, String)
        for column in ReleaseAnalysisUpdate.__table__.columns:
            if column.name in ("id", "release_check_run_id"):
                continue
            assert isinstance(column.type, allowed_types), (
                f"ReleaseAnalysisUpdate.{column.name} has type {column.type!r}, "
                "not a small typed scalar -- looks like a snapshot/JSON escape hatch."
            )


class TestNoRoleEnumOnReleaseSeriesMapping:
    """Guard #9: ReleaseSeriesMapping never gains a role/importance/
    priority/weight column -- it must remain only a "what to check"
    lookup."""

    def test_release_series_mapping_has_exactly_the_frozen_columns(self):
        column_names = {column.name for column in ReleaseSeriesMapping.__table__.columns}
        assert column_names == {"id", "economic_release_id", "series_id", "active", "created_at"}

    def test_release_series_mapping_has_no_role_shaped_column(self):
        forbidden_substrings = ("role", "importance", "priority", "weight", "primary", "supporting")
        column_names = {column.name.lower() for column in ReleaseSeriesMapping.__table__.columns}
        violations = {name for name in column_names if any(s in name for s in forbidden_substrings)}
        assert violations == set(), f"ReleaseSeriesMapping has a role-shaped column: {violations}"


class TestNoEconomicObservationUpdatedAt:
    """Guard #10: EconomicObservation was not given an `updated_at`
    column in #18 -- frozen, see app/db/models.py's own docstring for
    why (a generic row-touch timestamp would be semantically
    misleading given the existing blind-upsert behavior;
    ReleaseObservationUpdate.detected_at is the authoritative record of
    when a change was detected)."""

    def test_economic_observation_has_no_updated_at_column(self):
        column_names = {column.name for column in EconomicObservation.__table__.columns}
        assert "updated_at" not in column_names, "EconomicObservation gained an updated_at column -- this is frozen against #18"

    def test_economic_observation_has_exactly_the_pre_18_columns(self):
        column_names = {column.name for column in EconomicObservation.__table__.columns}
        assert column_names == {"id", "economic_series_id", "observation_date", "value", "created_at"}


class TestCheckRunStatusHasNoNotCheckedValue:
    """Frozen: 'not checked' is represented by absence of a
    ReleaseCheckRun row, never a persisted NOT_CHECKED status value."""

    def test_check_run_status_literal_has_exactly_the_four_frozen_values(self):
        from app.models.release_processing import CheckRunStatus

        # A Literal's allowed values are introspectable via __args__.
        assert set(CheckRunStatus.__args__) == {"NO_CHANGE", "CHANGED", "PARTIAL_FAILURE", "FAILED_PROVIDER"}

    def test_check_run_status_column_is_a_plain_string_not_an_enum_requiring_a_migration_to_extend(self):
        from sqlalchemy import String

        status_column = ReleaseCheckRun.__table__.columns["status"]
        assert isinstance(status_column.type, String)
