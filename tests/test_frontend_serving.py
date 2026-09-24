"""Increment #55A: serving the built frontend from the API process.

Uses a synthetic build directory shaped like React Router's `ssr: false`
output (`index.html`, `__spa-fallback.html`, prerendered directories,
hashed assets), mounted after a stand-in API route the way `app/main.py`
mounts the real one.
"""

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.web.frontend import CONTENT_SECURITY_POLICY, SPA_FALLBACK, build_frontend_router


@pytest.fixture
def dist(tmp_path):
    root = tmp_path / "client"
    (root / "rates").mkdir(parents=True)
    (root / "assets").mkdir()
    (root / "index.html").write_text("<html>HOME</html>")
    (root / SPA_FALLBACK).write_text("<html>SPA</html>")
    (root / "rates" / "index.html").write_text("<html>RATES</html>")
    (root / "assets" / "entry-abc123.js").write_text("console.log(1)")
    (root / "favicon.svg").write_text("<svg/>")
    # Outside the build: must never be reachable.
    (tmp_path / "secret.txt").write_text("outside")
    return root


@pytest.fixture
def client(dist):
    app = FastAPI()

    @app.get("/api/v1/known")
    def known() -> dict[str, str]:
        return {"ok": "yes"}

    app.include_router(build_frontend_router(dist))
    return TestClient(app)


def test_home_is_the_prerendered_index(client):
    response = client.get("/")
    assert response.text == "<html>HOME</html>"
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["Content-Security-Policy"] == CONTENT_SECURITY_POLICY


@pytest.mark.parametrize("path", ["/rates", "/rates/"])
def test_prerendered_route_is_served_from_its_directory(client, path):
    assert client.get(path).text == "<html>RATES</html>"


@pytest.mark.parametrize("path", ["/revisions", "/intelligence/rates:UST_NOMINAL_10Y:2026-09-23", "/no/such/page"])
def test_other_routes_get_the_spa_fallback_not_the_home_page(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert response.text == "<html>SPA</html>"
    assert response.headers["Content-Security-Policy"] == CONTENT_SECURITY_POLICY


def test_hashed_assets_are_long_lived_but_private(client):
    response = client.get("/assets/entry-abc123.js")
    assert response.headers["content-type"].startswith("text/javascript")
    assert response.headers["Cache-Control"] == "private, max-age=31536000, immutable"
    assert "Content-Security-Policy" not in response.headers


def test_html_is_revalidated_and_private(client):
    assert client.get("/").headers["Cache-Control"] == "private, no-cache"


def test_svg_has_its_real_type(client):
    assert client.get("/favicon.svg").headers["content-type"].startswith("image/svg+xml")


@pytest.mark.parametrize("path", ["/assets/missing-999.js", "/missing.png"])
def test_missing_files_are_404_never_html_in_their_place(client, path):
    assert client.get(path).status_code == 404


@pytest.mark.parametrize("path", ["/api/v1/unknown", "/api", "/api/"])
def test_unknown_api_paths_stay_json_404s(client, path):
    response = client.get(path)
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_api_routes_are_not_shadowed_by_the_catch_all(client):
    assert client.get("/api/v1/known").json() == {"ok": "yes"}


@pytest.mark.parametrize("path", ["/../secret.txt", "/%2e%2e/secret.txt", "/rates/../../secret.txt", "/.env", "/assets/.hidden"])
def test_nothing_outside_the_build_or_hidden_is_reachable(client, path):
    response = client.get(path)
    assert "outside" not in response.text
    assert response.status_code in (404, 200)
    if response.status_code == 200:
        # Normalised by the client/router into an in-build path: must
        # then be build content, never the file outside it.
        assert response.text in {"<html>HOME</html>", "<html>SPA</html>", "<html>RATES</html>"}


def test_head_is_supported(client):
    response = client.head("/rates")
    assert response.status_code == 200
    assert response.text == ""


def test_writes_are_not_accepted(client):
    assert client.post("/rates").status_code == 405


@pytest.mark.parametrize("raw", ["../secret.txt", "rates/../../secret.txt", "..", ".env", "assets/.hidden", "a/../../secret.txt"])
def test_resolver_rejects_traversal_and_dotfiles_given_raw_input(dist, raw):
    """The HTTP layer normalises `..` before routing; this checks the
    resolver itself, so the guarantee does not rest on the client."""
    from app.web.frontend import _resolve

    resolved = _resolve(dist.resolve(), raw)
    assert resolved is None or resolved.is_relative_to(dist.resolve())
    assert resolved is None or resolved.read_text() != "outside"
