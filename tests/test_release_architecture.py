"""Architectural guards for Increment #26D's deployment release process
(`app.operations.release`, `app.operations.smoke_test`, the Dockerfile,
and the CI workflow) -- the same static-inspection discipline every
prior increment's own dedicated guard file already applies. No
database, no FastAPI test client where avoidable; every check here is
a plain source/config inspection. Frozen contract:
docs/product/production-reliability-deployment-v1.md (#26B) §22/§25-27/
§40/§51-52, ADR-027.
"""

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_RELEASE_FILE = Path("app/operations/release.py")
_SMOKE_TEST_FILE = Path("app/operations/smoke_test.py")
_MAIN_FILE = Path("app/main.py")
_DOCKERFILE = Path("Dockerfile")
_DOCKERIGNORE = Path(".dockerignore")
_PYPROJECT = Path("pyproject.toml")
_CI_WORKFLOW = Path(".github/workflows/ci.yml")


def _source(file_path: Path) -> str:
    return (REPO_ROOT / file_path).read_text()


def _code_only(file_path: Path) -> str:
    """Strips triple-quoted docstrings and `#` comments before a
    pattern check -- this project's own established fix for the
    recurring false-positive shape where a module's own explanatory
    prose correctly names a forbidden term in English (see
    tests/test_schema_compatibility_architecture.py's identical
    helper and its own docstring for the full precedent chain)."""
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
    def test_release_module_exists(self):
        assert (REPO_ROOT / _RELEASE_FILE).is_file()

    def test_smoke_test_module_exists(self):
        assert (REPO_ROOT / _SMOKE_TEST_FILE).is_file()


class TestReleaseCommandBoundedResponsibility:
    """#26D source prompt §52: migration command never invokes
    economic services -- it knows the migration graph and the shared
    compatibility checker, nothing about Inflation, Labor, FRED,
    release processing, or AI."""

    FORBIDDEN_PREFIXES = ("app.services", "app.domain", "app.repositories", "app.clients", "app.api", "openai")

    def test_release_module_imports_nothing_economic_or_ai(self):
        violations = [
            name
            for name in _imported_module_names(_RELEASE_FILE)
            if any(name == prefix or name.startswith(prefix + ".") for prefix in self.FORBIDDEN_PREFIXES)
        ]
        assert violations == [], f"app/operations/release.py imports forbidden module(s): {violations}"

    def test_smoke_test_module_imports_nothing_economic_or_ai(self):
        violations = [
            name
            for name in _imported_module_names(_SMOKE_TEST_FILE)
            if any(name == prefix or name.startswith(prefix + ".") for prefix in self.FORBIDDEN_PREFIXES)
        ]
        assert violations == [], f"app/operations/smoke_test.py imports forbidden module(s): {violations}"


class TestReleaseCommandNeverStartsWebOrMaintenance:
    """#26D source prompt §9/§48: migration command never starts web,
    never runs the scheduler, never invokes maintenance -- and the
    maintenance worker's own entry points remain fully separate from
    the migration command (#26B §52: "maintenance remains separate")."""

    def test_release_module_never_imports_uvicorn_or_the_web_app(self):
        imported = _imported_module_names(_RELEASE_FILE)
        assert "uvicorn" not in imported
        assert "app.main" not in imported

    def test_release_module_never_imports_the_maintenance_orchestrator(self):
        imported = _imported_module_names(_RELEASE_FILE)
        forbidden = ("app.services.maintenance", "app.operations.run_maintenance")
        violations = [name for name in imported if any(name == p or name.startswith(p + ".") for p in forbidden)]
        assert violations == [], f"app/operations/release.py imports the maintenance worker: {violations}"


class TestWebEntrypointNeverMigrates:
    """#26D source prompt §22: container/web startup command must not
    contain `alembic upgrade`, a migration wrapper, or
    `metadata.create_all` -- extended here beyond #26C's own existing
    guard (which checked for the maintenance orchestrator) to also
    cover the NEW migration command this increment introduces."""

    def test_main_module_never_imports_the_release_command(self):
        imported = _imported_module_names(_MAIN_FILE)
        assert "app.operations.release" not in imported

    def test_main_module_never_imports_alembic_command(self):
        imported = _imported_module_names(_MAIN_FILE)
        assert "alembic.command" not in imported
        assert not any(name.startswith("alembic.command.") for name in imported)

    def test_main_module_never_calls_create_all_or_upgrade_or_downgrade(self):
        code = _code_only(_MAIN_FILE)
        for forbidden in ("create_all(", "command.upgrade(", "command.downgrade(", ".upgrade(", ".downgrade("):
            assert forbidden not in code, f"app/main.py appears to call {forbidden!r}"


class TestReleaseCommandOnlyReadsOrDDLs:
    """The release command's own single write capability
    (`alembic.command.upgrade`) is exercised through exactly one call
    site -- never duplicated, never wrapped in a second helper that
    could drift from it."""

    def test_command_upgrade_is_called_exactly_once(self):
        tree = _tree(_RELEASE_FILE)
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "upgrade"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "command"
        ]
        assert len(calls) == 1, f"expected exactly one command.upgrade(...) call site, found {len(calls)}"

    def test_never_calls_alembic_downgrade(self):
        code = _code_only(_RELEASE_FILE)
        assert "command.downgrade(" not in code
        assert ".downgrade(" not in code


class TestSmokeTestIsReadOnly:
    """#26D source prompt §38-39: smoke command issues no `POST`/`PUT`/
    `DELETE`/`PATCH` of any kind."""

    def test_smoke_test_never_issues_a_mutating_http_method(self):
        code = _code_only(_SMOKE_TEST_FILE)
        for forbidden in (".post(", ".put(", ".delete(", ".patch("):
            assert forbidden not in code, f"app/operations/smoke_test.py appears to call {forbidden!r}"

    def test_smoke_test_only_ever_calls_get(self):
        tree = _tree(_SMOKE_TEST_FILE)
        http_method_calls = [
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"get", "post", "put", "delete", "patch"}
        ]
        assert http_method_calls != []
        assert set(http_method_calls) == {"get"}


class TestNoPublicMigrationOrMaintenanceEndpoint:
    """#26D source prompt §27: no processing/migration endpoint is
    ever added to the public HTTP surface -- a route-decorator scan
    across every API module and app/main.py itself."""

    _MUTATING_METHODS = {"post", "put", "delete", "patch"}
    _FORBIDDEN_PATH_FRAGMENTS = ("migrat", "maintenance", "process")

    def _route_paths(self, file_path: Path) -> list[tuple[str, str]]:
        tree = _tree(file_path)
        routes = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                    continue
                method = decorator.func.attr
                if method not in self._MUTATING_METHODS:
                    continue
                for arg in decorator.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        routes.append((method, arg.value))
        return routes

    def test_no_mutating_route_anywhere_references_migration_or_maintenance(self):
        api_dir = REPO_ROOT / "app" / "api"
        violations = []
        for file_path in [*sorted(p.relative_to(REPO_ROOT) for p in api_dir.glob("*.py")), _MAIN_FILE]:
            for method, path in self._route_paths(file_path):
                if any(fragment in path.lower() for fragment in self._FORBIDDEN_PATH_FRAGMENTS):
                    violations.append(f"{file_path}: {method.upper()} {path}")
        assert violations == [], f"a mutating migration/maintenance-shaped route exists: {violations}"


class TestPythonVersionPreserved:
    """#26D source prompt §5: respect the repository's frozen Python
    3.12 decision -- checked both in pyproject.toml (unchanged) and,
    if a Dockerfile exists, in its own base image tag."""

    def test_pyproject_still_requires_python_312(self):
        content = _source(_PYPROJECT)
        assert 'requires-python = ">=3.12"' in content

    def test_dockerfile_pins_python_312(self):
        if not (REPO_ROOT / _DOCKERFILE).is_file():
            return
        content = _source(_DOCKERFILE)
        from_lines = [line for line in content.splitlines() if line.strip().upper().startswith("FROM")]
        assert from_lines != [], "Dockerfile has no FROM instruction"
        assert any("3.12" in line for line in from_lines), f"no FROM line pins Python 3.12: {from_lines}"


class TestProductionArtifactExcludesSecretsAndDevFiles:
    """#26D source prompt §8: production artifact should not
    unnecessarily contain .env, credentials, local caches, .venv,
    node_modules, or unnecessary .git history."""

    def test_dockerignore_exists_and_excludes_env_and_git_and_venv(self):
        assert (REPO_ROOT / _DOCKERIGNORE).is_file()
        content = _source(_DOCKERIGNORE)
        for required in (".env", ".git", ".venv", "__pycache__"):
            assert required in content, f".dockerignore does not exclude {required!r}"

    def test_dockerfile_never_copies_env_or_git_directly(self):
        if not (REPO_ROOT / _DOCKERFILE).is_file():
            return
        code_only = _code_only(_DOCKERFILE)
        copy_lines = [line for line in code_only.splitlines() if line.strip().upper().startswith("COPY")]
        for line in copy_lines:
            assert ".env" not in line, f"Dockerfile COPY references .env directly: {line!r}"
            assert ".git " not in line and not line.strip().upper().endswith(".GIT"), f"Dockerfile COPY references .git directly: {line!r}"


class TestCIGuards:
    """#26D source prompt §51: if CI exists, it must never use the
    production DB, run production migrations, trigger maintenance,
    call a provider with a production key, or deploy on PR
    automatically."""

    def _workflow(self) -> dict:
        import yaml

        return yaml.safe_load(_source(_CI_WORKFLOW))

    def _parsed_content(self) -> str:
        """The workflow re-serialized from its OWN parsed structure --
        `yaml.safe_load` already drops every comment by construction,
        so checking substrings against this (rather than the raw
        source text) is precise against actual, executable workflow
        content only. Fixes the exact false-positive shape this
        project has now hit repeatedly (a file's own explanatory
        comment/docstring correctly NAMING a forbidden term in prose,
        e.g. this very file's own header comment explaining that CI
        must never invoke the release command) -- see
        tests/test_schema_compatibility_architecture.py's `_code_only`
        for the identical precedent applied to Python source instead.
        """
        return str(self._workflow())

    def test_ci_workflow_exists_and_parses(self):
        assert (REPO_ROOT / _CI_WORKFLOW).is_file()
        workflow = self._workflow()
        assert "jobs" in workflow

    def test_ci_never_references_a_github_secret(self):
        """No production credential of any kind is wired into this
        workflow -- confirmed by the complete absence of GitHub's own
        `secrets.` context anywhere in actual, executable workflow
        content."""
        assert "secrets." not in self._parsed_content()

    def test_ci_never_invokes_the_release_migration_command(self):
        content = self._parsed_content()
        assert "app.operations.release" not in content
        assert "release migrate" not in content

    def test_ci_never_invokes_maintenance_or_manual_processing(self):
        content = self._parsed_content()
        assert "run_maintenance" not in content
        assert "process_release" not in content

    def test_ci_database_is_the_ephemeral_service_not_a_real_one(self):
        content = _source(_CI_WORKFLOW)
        assert "TEST_DATABASE_URL" in content
        assert "economic_intelligence_test" in content
        # The project's own established safety convention: a
        # database-backed test run's URL must contain "test".
        assert "postgresql+psycopg://postgres@localhost:5432/economic_intelligence_test" in content

    def test_ci_has_no_deploy_job(self):
        workflow = self._workflow()
        job_names = set(workflow.get("jobs", {}).keys())
        for name in job_names:
            assert "deploy" not in name.lower(), f"a deploy-shaped CI job exists: {name!r}"


class TestDockerfileWebCommandExecutes:
    """#54A: the image's default CMD, EXECUTED by `sh`, hands uvicorn
    exactly the arguments intended -- whatever files sit in the working
    directory.

    Found by the first real run of the CMD: an unquoted
    `${FORWARDED_ALLOW_IPS:-*}` was glob-expanded into the filenames in
    /app, and uvicorn refused to start. A text match on the Dockerfile
    could not have caught that, so this test runs the real CMD string
    through the real shell, with a stub `uvicorn` on PATH that prints
    its own argv instead of serving."""

    #: What the image's own working directory holds after `pip install .`
    #: -- the files a stray `*` would expand into.
    _IMAGE_WORKDIR_ENTRIES = ("alembic", "alembic.ini", "app", "build", "pyproject.toml")

    def _cmd_script(self) -> str:
        import json

        cmd_lines = [line for line in _code_only(_DOCKERFILE).splitlines() if line.strip().startswith("CMD")]
        assert len(cmd_lines) == 1, f"expected exactly one CMD instruction: {cmd_lines}"
        argv = json.loads(cmd_lines[0].strip()[len("CMD") :])
        assert argv[:2] == ["sh", "-c"], f"CMD is no longer `sh -c <script>`: {argv}"
        return argv[2]

    def _run(self, tmp_path: Path, extra_env: dict[str, str]) -> list[str]:
        import subprocess

        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        stub = bin_dir / "uvicorn"
        stub.write_text('#!/bin/sh\nfor arg in "$@"; do printf "%s\\n" "$arg"; done\n')
        stub.chmod(0o755)

        workdir = tmp_path / "workdir"
        workdir.mkdir()
        for name in self._IMAGE_WORKDIR_ENTRIES:
            (workdir / name).touch()

        result = subprocess.run(
            ["sh", "-c", self._cmd_script()],
            cwd=workdir,
            env={"PATH": f"{bin_dir}:/usr/bin:/bin", **extra_env},
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.splitlines()

    def test_defaults_bind_port_8000_and_trust_the_platform_proxy(self, tmp_path):
        assert self._run(tmp_path, {}) == [
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
            "--proxy-headers",
            "--forwarded-allow-ips",
            "*",
        ]

    def test_platform_port_and_explicit_proxy_list_pass_through_unsplit(self, tmp_path):
        argv = self._run(tmp_path, {"PORT": "10000", "FORWARDED_ALLOW_IPS": "10.0.0.1,10.0.0.2"})
        assert argv[argv.index("--port") + 1] == "10000"
        assert argv[argv.index("--forwarded-allow-ips") + 1] == "10.0.0.1,10.0.0.2"
        assert len(argv) == 8, f"unexpected extra arguments reached uvicorn: {argv}"


class TestContainerWorkflowValidatesNeverDeploys:
    """#55A: `.github/workflows/container.yml` migrates and runs the real
    image, so it must be held to the same line as `ci.yml` (ADR-028) --
    stated for THIS workflow's shape: it may migrate, but only the
    job-local service database; it may build an image, but never publish
    one; and it never touches a repository secret."""

    _WORKFLOW = Path(".github/workflows/container.yml")

    def _workflow(self) -> dict:
        import yaml

        return yaml.safe_load(_source(self._WORKFLOW))

    def _executable_text(self) -> str:
        import yaml

        return yaml.safe_dump(self._workflow())

    def test_never_references_a_repository_secret(self):
        assert "secrets." not in self._executable_text()

    def test_never_logs_in_to_or_pushes_to_a_registry(self):
        content = self._executable_text()
        for forbidden in ("docker push", "docker login", "docker/login-action", "docker/build-push-action"):
            assert forbidden not in content, forbidden

    def test_has_no_deploy_job(self):
        for name in self._workflow()["jobs"]:
            assert "deploy" not in name.lower()

    def test_the_only_database_is_the_job_local_service(self):
        job = self._workflow()["jobs"]["image"]
        assert job["env"]["DATABASE_URL"] == "postgresql://postgres@localhost:5432/macrochipz_container_ci"
        assert job["services"]["postgres"]["env"]["POSTGRES_DB"] == "macrochipz_container_ci"
        # No step may point the release command anywhere else.
        for step in job["steps"]:
            assert "DATABASE_URL=" not in step.get("run", ""), step.get("name")

    def test_generated_credentials_are_masked_before_use(self):
        steps = self._workflow()["jobs"]["image"]["steps"]
        generate = next(step for step in steps if "credentials" in step.get("name", "").lower())
        assert "::add-mask::" in generate["run"]
        assert steps.index(generate) < next(i for i, step in enumerate(steps) if "docker build" in step.get("run", ""))


class TestImageCarriesTheFrontend:
    """#55A: the image builds the frontend in a discarded stage and
    serves only its output."""

    def test_node_stage_matches_the_repository_node_contract(self):
        nvmrc = (REPO_ROOT / ".nvmrc").read_text().strip()
        assert f"ARG NODE_VERSION={nvmrc}" in _source(_DOCKERFILE)

    def test_final_stage_copies_only_the_built_client(self):
        code = _code_only(_DOCKERFILE)
        from_frontend = [line for line in code.splitlines() if "--from=frontend" in line]
        assert from_frontend == ["COPY --from=frontend /frontend/build/client ./frontend_dist"]
        assert "ENV FRONTEND_DIST_DIR=/app/frontend_dist" in code

    def test_frontend_build_is_same_origin_and_unindexed(self):
        assert "RUN VITE_API_BASE_URL= VITE_SITE_URL= npm run build" in _code_only(_DOCKERFILE)

    def test_dockerignore_keeps_local_frontend_output_and_env_files_out(self):
        content = _source(_DOCKERIGNORE)
        for required in ("frontend/node_modules/", "frontend/build/", "**/.env"):
            assert required in content, required
