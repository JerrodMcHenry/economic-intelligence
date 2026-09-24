"""Increment #56A: structural guards for first-party ingestion.

Source inspection, in the style of the other `*_architecture` tests.
"""

import ast
from pathlib import Path

import pytest

from app.concepts.bindings import BINDINGS
from app.models.first_party import FIRST_PARTY_CONCEPT_IDS, SOURCES, source_url

REPO_ROOT = Path(__file__).resolve().parent.parent
FIRST_PARTY_MODULES = [
    "app/clients/bounded_http.py",
    "app/clients/bls.py",
    "app/clients/bea.py",
    "app/models/first_party.py",
    "app/repositories/first_party_repository.py",
    "app/services/first_party_ingestion.py",
    "app/operations/import_first_party.py",
]


def _imports(path: str) -> set[str]:
    tree = ast.parse((REPO_ROOT / path).read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


@pytest.mark.parametrize("path", FIRST_PARTY_MODULES)
def test_first_party_code_never_touches_fred(path):
    assert not any(name.startswith("app.clients.fred") for name in _imports(path)), path


def test_no_http_route_can_trigger_a_first_party_import():
    """The import is operator-only, via the CLI. #54A measured a long
    ingestion request being killed by a deploy; this one downloads ~37 MB."""
    for route_module in (REPO_ROOT / "app" / "api").glob("*.py"):
        imported = _imports(str(route_module.relative_to(REPO_ROOT)))
        assert "app.services.first_party_ingestion" not in imported, route_module.name
        assert "app.operations.import_first_party" not in imported, route_module.name


def test_the_bls_key_appears_only_as_a_request_body_field():
    source = (REPO_ROOT / "app/clients/bls.py").read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        # No URL is ever built by formatting: both endpoints are constants.
        if isinstance(node, ast.JoinedStr):
            rendered = ast.unparse(node)
            assert "http" not in rendered, rendered
    assert source.count('body["registrationkey"] = self._api_key') == 1


@pytest.mark.parametrize("concept_id", FIRST_PARTY_CONCEPT_IDS)
def test_provenance_urls_are_landing_pages_never_api_endpoints(concept_id):
    binding = next(b for b in BINDINGS if b.concept_id == concept_id and b.provider in {"BLS", "BEA"})
    url = source_url(binding.provider, binding.provider_series_id)
    assert url.startswith("https://")
    assert "api.bls.gov" not in url and "/api/" not in url and "UserID" not in url
    assert SOURCES[concept_id].provider == binding.provider
