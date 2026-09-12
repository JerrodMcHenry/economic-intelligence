"""Architectural guard: the pure domain layer (app.domain.transformations,
app.domain.analysis) must never import a probabilistic, I/O-bearing, or
web-framework dependency. This is a small source/import inspection test,
not an architecture-testing framework -- it parses each module's own
`import`/`from ... import` statements via `ast` (no execution, no
network) and asserts none of them touch a forbidden module.

Purpose: catch future accidental contamination of the deterministic
domain layer (e.g. someone adding "just one FRED call" to a
transformation function) automatically, in CI, rather than relying on
code review alone.
"""

import ast
from pathlib import Path

DOMAIN_FILES = [
    Path("app/domain/transformations.py"),
    Path("app/domain/analysis.py"),
]

# Forbidden if an imported module IS one of these, or is a submodule of
# one of these (e.g. "openai.types" is still forbidden because it starts
# with "openai").
FORBIDDEN_MODULE_PREFIXES = (
    "openai",
    "app.services.ai",  # covers app.services.ai and app.services.ai_tools
    "app.clients.fred",
    "sqlalchemy",
    "fastapi",
    "httpx",  # the transport FREDClient/OpenAI SDK both ultimately use
)


def _imported_module_names(file_path: Path) -> set[str]:
    """Parse a Python file's imports without executing it."""
    tree = ast.parse(file_path.read_text(), filename=str(file_path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _is_forbidden(module_name: str) -> bool:
    return any(module_name == prefix or module_name.startswith(prefix + ".") for prefix in FORBIDDEN_MODULE_PREFIXES)


class TestDomainLayerArchitecturalIndependence:
    def test_domain_files_exist_where_expected(self):
        """Fails loudly (not silently passing on 0 files) if these move."""
        for file_path in DOMAIN_FILES:
            assert file_path.is_file(), f"expected {file_path} to exist"

    def test_no_forbidden_imports_in_domain_layer(self):
        violations = []
        for file_path in DOMAIN_FILES:
            for module_name in _imported_module_names(file_path):
                if _is_forbidden(module_name):
                    violations.append(f"{file_path}: imports '{module_name}'")
        assert violations == [], "domain layer imports a forbidden dependency:\n" + "\n".join(violations)

    def test_domain_layer_imports_are_limited_to_an_explicit_allowlist(self):
        """Stricter than the forbidden-prefix check above: every actual
        import in the domain layer must be either the standard library
        or app.models.* (plain Pydantic data shapes, not FastAPI). This
        catches a new, not-yet-forbidden-by-name dependency too, not
        just the ones already known to be risky."""
        allowed_prefixes = ("app.models.",)
        stdlib_or_builtin_ok = {"typing", "datetime", "__future__"}

        for file_path in DOMAIN_FILES:
            for module_name in _imported_module_names(file_path):
                top_level = module_name.split(".")[0]
                is_allowed = (
                    module_name in stdlib_or_builtin_ok
                    or top_level in stdlib_or_builtin_ok
                    or any(module_name.startswith(p) for p in allowed_prefixes)
                )
                assert is_allowed, f"{file_path}: '{module_name}' is not on the domain-layer allowlist"
