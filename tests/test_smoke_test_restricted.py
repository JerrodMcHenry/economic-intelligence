"""Increment #55A: `smoke_test --restricted` proves the access boundary.

A simulated server (httpx.MockTransport) stands in for the deployment,
so every branch -- a correctly gated server, one that leaks, missing
credentials -- runs without a network or database. The real image is
smoke-tested end to end by `.github/workflows/container.yml`.
"""

import base64

import httpx
import pytest

from app.operations import smoke_test

PASSWORD = "synthetic-test-password-0123456789"
EXPECTED_AUTH = "Basic " + base64.b64encode(f"macrochipz:{PASSWORD}".encode()).decode()


def _server(leak: str | None = None):
    seen: list[tuple[str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        authorization = request.headers.get("authorization")
        seen.append((path, authorization))
        if path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        if authorization != EXPECTED_AUTH and path != leak:
            return httpx.Response(401, json={"detail": "Authentication required."})
        if path == "/":
            return httpx.Response(200, html="<html></html>")
        return httpx.Response(200, json={})

    return handler, seen


@pytest.fixture
def serve(monkeypatch):
    def install(handler):
        real_client = httpx.Client
        monkeypatch.setattr(
            smoke_test.httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs)
        )

    return install


def test_a_correctly_gated_deployment_passes(serve, monkeypatch, capsys):
    handler, seen = _server()
    serve(handler)
    monkeypatch.setenv("ACCESS_PASSWORD", PASSWORD)
    monkeypatch.delenv("ACCESS_USERNAME", raising=False)

    assert smoke_test.main(["--base-url", "http://demo.test", "--restricted"]) == 0

    anonymous_paths = {path for path, auth in seen if auth is None}
    assert {"/api/v1/monitors/inflation", "/", "/sitemap.xml", "/health"} <= anonymous_paths
    assert ("/api/v1/housing", EXPECTED_AUTH) in seen
    # The credential is sent, never printed.
    assert PASSWORD not in capsys.readouterr().out


@pytest.mark.parametrize("leak", ["/api/v1/monitors/inflation", "/", "/sitemap.xml"])
def test_a_deployment_that_serves_anything_anonymously_fails(serve, monkeypatch, leak):
    handler, _ = _server(leak=leak)
    serve(handler)
    monkeypatch.setenv("ACCESS_PASSWORD", PASSWORD)

    assert smoke_test.main(["--base-url", "http://demo.test", "--restricted"]) == 1


def test_restricted_without_credentials_refuses_to_run(serve, monkeypatch):
    handler, seen = _server()
    serve(handler)
    monkeypatch.delenv("ACCESS_PASSWORD", raising=False)

    assert smoke_test.main(["--base-url", "http://demo.test", "--restricted"]) == 2
    assert seen == []


def test_unrestricted_mode_against_a_gated_server_fails_loudly(serve, monkeypatch):
    handler, _ = _server()
    serve(handler)

    assert smoke_test.main(["--base-url", "http://demo.test"]) == 1
