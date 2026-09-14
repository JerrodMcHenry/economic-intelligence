"""Architectural guards for Increment #20B's Labor Market Monitor
(`labor_v1.0`), checked statically (AST/source inspection) wherever
possible rather than left to convention -- the same discipline
tests/test_release_processing_architecture.py already applies to #18.
No database, no FRED, no FastAPI test client -- every check here is a
plain source/model inspection.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

LABOR_FILES = [
    Path("app/models/labor.py"),
    Path("app/domain/labor.py"),
    Path("app/services/labor.py"),
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


class TestLaborFilesExist:
    def test_labor_files_exist_where_expected(self):
        for file_path in LABOR_FILES:
            assert (REPO_ROOT / file_path).is_file(), f"expected {file_path} to exist"


class TestNoAIOrFREDImports:
    """Guard: the Labor Monitor's whole call graph (models, domain,
    service, API) contains no AI/FRED import anywhere -- it is
    DB-only, always, per LABOR_V1_FROZEN_METHODOLOGY.md §17."""

    FORBIDDEN_PREFIXES = ("openai", "app.services.ai", "app.services.news", "httpx", "app.clients.fred")

    def test_no_labor_file_imports_ai_or_fred(self):
        violations = []
        for file_path in LABOR_FILES:
            for module_name in _imported_module_names(file_path):
                if any(module_name == p or module_name.startswith(p + ".") for p in self.FORBIDDEN_PREFIXES):
                    violations.append(f"{file_path}: imports '{module_name}'")
        assert violations == [], "Labor Monitor imports a forbidden dependency:\n" + "\n".join(violations)


class TestNoReleaseProcessingMutation:
    """Guard: the Labor Monitor's read path never imports anything
    from #18's release-processing write path -- a monitor read must
    never be able to trigger a mutation as a side effect."""

    def test_no_labor_file_imports_release_processing_write_path(self):
        violations = []
        for file_path in LABOR_FILES:
            for module_name in _imported_module_names(file_path):
                if module_name == "app.services.release_processing" or module_name.startswith("app.services.release_processing."):
                    violations.append(f"{file_path}: imports '{module_name}'")
        assert violations == [], "Labor Monitor imports the release-processing write path:\n" + "\n".join(violations)


class TestDomainLayerIsPure:
    """Guard: app/domain/labor.py never imports SQLAlchemy, FastAPI,
    or any database/session module -- it is pure, deterministic
    calculation only."""

    FORBIDDEN_PREFIXES = ("sqlalchemy", "fastapi", "app.db", "app.repositories")

    def test_domain_module_has_no_db_or_web_dependency(self):
        imported = _imported_module_names(Path("app/domain/labor.py"))
        violations = {m for m in imported if any(m == p or m.startswith(p + ".") for p in self.FORBIDDEN_PREFIXES)}
        assert violations == set(), f"app/domain/labor.py imports a forbidden dependency: {violations}"


class TestServiceNeverClassifiesEconomics:
    """Guard: app/services/labor.py delegates every actual
    classification to app.domain.labor -- it must import
    `compute_labor_monitor_result` (the one entry point) and must
    never import the classification primitives directly (which would
    suggest the service is reimplementing/duplicating logic that
    belongs in the domain layer)."""

    def test_service_imports_only_the_top_level_domain_entry_point(self):
        source = (REPO_ROOT / "app/services/labor.py").read_text()
        tree = ast.parse(source)
        imported_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "app.domain.labor":
                imported_names.update(alias.name for alias in node.names)
        assert imported_names == {"compute_labor_monitor_result"}, (
            f"app/services/labor.py should import only compute_labor_monitor_result from app.domain.labor, "
            f"found: {imported_names}"
        )


class TestExactlyOneLaborRoute:
    """Guard: exactly ONE public route exists for the Labor Monitor --
    GET /monitors/labor -- and it is the only route app/api/labor.py
    registers. No POST/PUT/PATCH/DELETE route anywhere in the API
    layer touches Labor."""

    def test_labor_route_module_registers_exactly_one_route(self):
        source = (REPO_ROOT / "app/api/labor.py").read_text()
        tree = ast.parse(source)
        route_decorators = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"get", "post", "put", "patch", "delete"}
        ]
        assert len(route_decorators) == 1, f"expected exactly one route, found {len(route_decorators)}"

    def test_route_path_is_exactly_labor(self):
        from app.api.labor import router

        paths = [route.path for route in router.routes]
        assert paths == ["/monitors/labor"]

    def test_no_labor_mutation_route_exists_anywhere_in_the_api_layer(self):
        api_dir = REPO_ROOT / "app" / "api"
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
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and "labor" in arg.value.lower():
                        violations.append(f"{file_path.name}: mutating route '{arg.value}'")
        assert violations == [], "a public HTTP mutation route for Labor exists:\n" + "\n".join(violations)


class TestNoJoltsOrCivpartInV1:
    """Guard: #20B deliberately defers JOLTS and CIVPART -- neither
    should appear anywhere in the Labor Monitor's own files."""

    def test_no_jolts_series_id_anywhere_in_labor_files(self):
        forbidden = ("JTSJOR", "JTSQUR", "JTSHIR", "JTSJOL", "JTSQUL", "JTSHIL", "JTSLDR", "JTSLDL")
        violations = []
        for file_path in LABOR_FILES:
            contents = (REPO_ROOT / file_path).read_text()
            for series_id in forbidden:
                if series_id in contents:
                    violations.append(f"{file_path}: references {series_id}")
        assert violations == [], "JOLTS was deferred from #20B but appears in Labor files:\n" + "\n".join(violations)

    def test_no_civpart_anywhere_in_labor_files(self):
        violations = [str(f) for f in LABOR_FILES if "CIVPART" in (REPO_ROOT / f).read_text()]
        assert violations == [], f"CIVPART was deferred from #20B but appears in: {violations}"


class TestFrozenVocabularyHasExactlyTheSpecifiedValues:
    """Guard: every enum in `app.models.labor` has exactly the values
    frozen in LABOR_V1_FROZEN_METHODOLOGY.md -- no more, no fewer."""

    def test_employment_condition_vocabulary(self):
        from app.models.labor import EmploymentCondition

        assert set(EmploymentCondition.__args__) == {"EXPANDING", "FLAT", "CONTRACTING", "INSUFFICIENT_DATA"}

    def test_employment_momentum_vocabulary_is_improving_worsening_not_accelerating(self):
        from app.models.labor import EmploymentMomentum

        assert set(EmploymentMomentum.__args__) == {"IMPROVING", "STEADY", "WORSENING", "INSUFFICIENT_DATA"}
        # Explicit negative proof of the discrepancy this spec resolved
        # in the research artifact's favor (LABOR_V1_FROZEN_METHODOLOGY.md
        # §4's own vocabulary note) -- never silently reintroduced.
        assert "ACCELERATING" not in EmploymentMomentum.__args__
        assert "DECELERATING" not in EmploymentMomentum.__args__

    def test_employment_state_vocabulary(self):
        from app.models.labor import EmploymentState

        assert set(EmploymentState.__args__) == {"EXPANDING", "COOLING", "STABLE", "CONTRACTING", "RECOVERING", "INSUFFICIENT_DATA"}

    def test_unemployment_trend_state_vocabulary(self):
        from app.models.labor import UnemploymentTrendState

        assert set(UnemploymentTrendState.__args__) == {"IMPROVING", "DETERIORATING", "STABLE", "INSUFFICIENT_DATA"}

    def test_labor_state_vocabulary(self):
        from app.models.labor import LaborState

        assert set(LaborState.__args__) == {"STRENGTHENING", "COOLING", "STABLE", "MIXED", "INSUFFICIENT_DATA"}

    def test_frozen_deadband_constants(self):
        from app.models.labor import CONDITION_DEADBAND_JOBS, MOMENTUM_DEADBAND_JOBS, UNEMPLOYMENT_DEADBAND_PP

        assert CONDITION_DEADBAND_JOBS == 50_000
        assert MOMENTUM_DEADBAND_JOBS == 50_000
        assert UNEMPLOYMENT_DEADBAND_PP == 0.2

    def test_frozen_methodology_id(self):
        from app.models.labor import METHODOLOGY_ID

        assert METHODOLOGY_ID == "labor_v1.0"
