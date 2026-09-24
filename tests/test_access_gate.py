"""Increment #55A: the restricted-demo access gate.

The property that matters is not "the login works" but "nothing is
served without it". So the central test enumerates EVERY route the
application registers -- including ones added after this file was
written -- and asserts each refuses an unauthenticated request, unless
it is the one documented exemption. Frontend paths (share pages,
sitemap, assets) are covered by probing paths the API does not own: the
gate runs before routing, so it answers them the same way.

No database is needed: a refused request never reaches a route, and the
pass-through checks use `/readiness`, which reports
`configuration_missing` without one.
"""

import base64
import logging
import re

import pytest
from fastapi.routing import APIRoute
from starlette.routing import Route
from starlette.testclient import TestClient

from app.api import access_gate
from app.core.config import MIN_ACCESS_PASSWORD_LENGTH, Settings, production_configuration_errors, settings
from app.main import app

USERNAME = "reviewer"
#: A synthetic sentinel, never a real credential.
PASSWORD = "synthetic-test-password-0123456789"

FRONTEND_AND_STATIC_PROBES = [
    "/",
    "/inflation",
    "/jobs",
    "/rates",
    "/housing",
    "/calendar",
    "/revisions",
    "/explain/cpi-vs-pce",
    "/intelligence/rates:UST_NOMINAL_10Y:2026-09-23",
    "/sitemap.xml",
    "/robots.txt",
    "/__spa-fallback.html",
    "/assets/index-abc123.js",
    "/og/default.png",
    "/api/v1/does-not-exist",
]


def _basic(username: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


@pytest.fixture(autouse=True)
def _clean_limiter():
    access_gate.reset_failed_attempts()
    yield
    access_gate.reset_failed_attempts()


@pytest.fixture
def restricted(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "access_username", USERNAME)
    monkeypatch.setattr(settings, "access_password", PASSWORD)
    monkeypatch.setattr(settings, "database_url", None)


@pytest.fixture
def client():
    return TestClient(app)


def _concrete_requests():
    """(method, path) for every route the application exposes, path
    parameters filled with a harmless placeholder.

    Enumerated from FastAPI's own OpenAPI generator, which is the
    supported view of the EFFECTIVE routes (with router prefixes
    applied). `app.routes` is not: this FastAPI version wraps each
    included router in a private `_IncludedRouter`, so walking it finds
    only the handful of routes declared directly on the app. Routes
    excluded from the schema (the docs pages) are added from
    `app.routes` directly.
    """
    seen: set[tuple[str, str]] = set()
    for path, operations in app.openapi()["paths"].items():
        for method in operations:
            seen.add((method.upper(), path))
    for route in app.routes:
        if isinstance(route, Route) and not isinstance(route, APIRoute):
            for method in (route.methods or set()) - {"HEAD", "OPTIONS"}:
                seen.add((method, route.path))
    for method, path in sorted(seen):
        yield method, re.sub(r"\{[^}]+\}", "probe", path)


class TestNothingIsServedWithoutAuthentication:
    def test_every_registered_route_refuses_an_anonymous_request(self, restricted, client):
        checked = 0
        for method, path in _concrete_requests():
            if path in access_gate.EXEMPT_PATHS:
                continue
            # Each probe is one anonymous failure; reset so the lockout
            # (tested separately below) does not turn later probes into 429s.
            access_gate.reset_failed_attempts()
            response = client.request(method, path)
            assert response.status_code == 401, f"{method} {path} answered {response.status_code} without credentials"
            assert response.json() == {"detail": "Authentication required."}, f"{method} {path} leaked a body"
            checked += 1
        # Guards against the enumeration silently finding nothing.
        assert checked >= 30

    @pytest.mark.parametrize("path", FRONTEND_AND_STATIC_PROBES)
    def test_frontend_share_pages_sitemap_and_assets_are_gated(self, restricted, client, path):
        response = client.get(path)

        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"].startswith("Basic ")

    def test_health_is_the_only_exemption_and_carries_no_data(self, restricted, client):
        assert access_gate.EXEMPT_PATHS == frozenset({"/health"})
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_readiness_is_gated_because_it_reveals_version_and_schema(self, restricted, client):
        assert client.get("/readiness").status_code == 401


class TestCredentials:
    def test_correct_credentials_reach_the_application(self, restricted, client):
        response = client.get("/readiness", headers=_basic(USERNAME, PASSWORD))
        # Past the gate: the route itself answers (no database here).
        assert response.status_code == 503
        assert response.json()["reason"] == "configuration_missing"
        assert response.headers["X-Robots-Tag"] == "noindex, nofollow"

    @pytest.mark.parametrize(
        "headers",
        [
            {},
            _basic(USERNAME, "wrong-password-wrong-password"),
            _basic("someone-else", PASSWORD),
            _basic(USERNAME, PASSWORD + "x"),
            {"Authorization": f"Bearer {PASSWORD}"},
            {"Authorization": "Basic not-base64!!"},
            {"Authorization": "Basic " + base64.b64encode(PASSWORD.encode()).decode()},
        ],
    )
    def test_absent_malformed_and_wrong_credentials_are_indistinguishable(self, restricted, client, headers):
        response = client.get("/api/v1/monitors/rates", headers=headers)

        assert response.status_code == 401
        assert response.json() == {"detail": "Authentication required."}

    def test_refusals_carry_security_headers_request_id_and_no_store(self, restricted, client):
        response = client.get("/api/v1/monitors/inflation")

        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Cache-Control"] == "no-store"
        assert response.headers["X-Robots-Tag"] == "noindex, nofollow"
        assert response.headers["X-Request-ID"]

    def test_credentials_never_reach_a_log_line(self, restricted, client, caplog):
        with caplog.at_level(logging.DEBUG):
            client.get("/api/v1/monitors/rates", headers=_basic(USERNAME, "a-wrong-guess-that-is-long"))
            client.get("/readiness", headers=_basic(USERNAME, PASSWORD))

        rendered = " ".join(f"{record.getMessage()} {record.__dict__}" for record in caplog.records)
        assert PASSWORD not in rendered
        assert "a-wrong-guess-that-is-long" not in rendered
        assert base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode() not in rendered


class TestGuessingIsBounded:
    def test_a_locked_out_client_is_refused_even_with_the_right_password(self, restricted, client):
        for _ in range(access_gate.FAILED_ATTEMPTS_PER_WINDOW):
            assert client.get("/api/v1/monitors/rates", headers=_basic(USERNAME, "wrong-wrong-wrong-wrong")).status_code == 401

        # The correct password is not even checked: a guess that happens
        # to be right must look exactly like one that is wrong.
        response = client.get("/readiness", headers=_basic(USERNAME, PASSWORD))
        assert response.status_code == 429
        assert int(response.headers["Retry-After"]) > 0

    def test_anonymous_requests_do_not_consume_the_failure_budget(self, restricted, client):
        """A request with no credentials is the challenge handshake, not a
        guess: unfurlers and monitors behind a reviewer's NAT must not
        lock the reviewer out."""
        for _ in range(access_gate.FAILED_ATTEMPTS_PER_WINDOW * 3):
            assert client.get("/").status_code == 401

        assert client.get("/readiness", headers=_basic(USERNAME, PASSWORD)).status_code == 503

    def test_successful_requests_do_not_consume_the_failure_budget(self, restricted, client):
        for _ in range(access_gate.FAILED_ATTEMPTS_PER_WINDOW * 2):
            assert client.get("/readiness", headers=_basic(USERNAME, PASSWORD)).status_code == 503


class TestFailsClosed:
    @pytest.mark.parametrize("password", [None, "", "x" * (MIN_ACCESS_PASSWORD_LENGTH - 1)])
    def test_production_without_a_usable_password_serves_nothing(self, monkeypatch, client, password):
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "access_password", password)

        assert client.get("/api/v1/monitors/rates").status_code == 503
        assert client.get("/sitemap.xml").status_code == 503
        # Even a caller who knows the short password gets nothing.
        if password:
            assert client.get("/readiness", headers=_basic(settings.access_username, password)).status_code == 503
        assert client.get("/health").status_code == 200

    def test_production_reports_the_missing_password_by_name_only(self):
        candidate = Settings()
        candidate.environment = "production"
        candidate.database_url = "postgresql+psycopg://u@h/db"
        candidate.cors_allowed_origins = ["https://example.test"]
        candidate.operator_token = "set"
        candidate.access_password = "short"

        errors = production_configuration_errors(candidate)

        assert any("ACCESS_PASSWORD" in error for error in errors)
        assert not any("short" in error.replace("shorter", "") for error in errors)

    def test_same_origin_frontend_removes_the_cors_requirement(self, tmp_path):
        (tmp_path / "index.html").write_text("<!doctype html>")
        candidate = Settings()
        candidate.environment = "production"
        candidate.database_url = "postgresql+psycopg://u@h/db"
        candidate.cors_allowed_origins = []
        candidate.operator_token = "set"
        candidate.access_password = PASSWORD
        candidate.frontend_dist_dir = str(tmp_path)

        assert production_configuration_errors(candidate) == []

    def test_a_frontend_directory_without_a_build_is_reported(self, tmp_path):
        candidate = Settings()
        candidate.environment = "production"
        candidate.database_url = "postgresql+psycopg://u@h/db"
        candidate.operator_token = "set"
        candidate.access_password = PASSWORD
        candidate.frontend_dist_dir = str(tmp_path)

        assert any("FRONTEND_DIST_DIR" in error for error in production_configuration_errors(candidate))


class TestDevelopmentIsUnchanged:
    def test_no_password_outside_production_means_no_gate(self, monkeypatch, client):
        monkeypatch.setattr(settings, "environment", "development")
        monkeypatch.setattr(settings, "access_password", None)
        monkeypatch.setattr(settings, "database_url", None)

        assert client.get("/readiness").status_code == 503  # the route, not the gate
        assert "X-Robots-Tag" not in client.get("/health").headers


def test_production_responses_carry_hsts(restricted, client):
    assert client.get("/health").headers["Strict-Transport-Security"] == "max-age=31536000"
    assert client.get("/sitemap.xml").headers["Strict-Transport-Security"] == "max-age=31536000"


def test_development_responses_do_not_carry_hsts(monkeypatch, client):
    monkeypatch.setattr(settings, "environment", "development")
    assert "Strict-Transport-Security" not in client.get("/health").headers
