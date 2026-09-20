"""Tests for the Increment #34 production controls.

Every test here corresponds to a specific finding in the #34 audit. The
rule applied throughout: a control is only worth having if its absence
would be caught, so each control is tested in BOTH directions —
rejected without it, accepted with it.
"""

import json

import pytest
from starlette.testclient import TestClient

from app.api.middleware import REQUEST_ID_HEADER, SECURITY_HEADERS
from app.api.operator import OPERATOR_TOKEN_HEADER
from app.core.config import Settings, production_configuration_errors

pytestmark = pytest.mark.api

OPERATOR_ENDPOINTS = [
    ("POST", "/api/v1/series/PCEPILFE/sync"),
    ("POST", "/api/v1/rates/sync"),
    ("POST", "/api/v1/releases/sync"),
]

PUBLIC_READ_ENDPOINTS = [
    "/api/v1/monitors/inflation",
    "/api/v1/monitors/labor",
    "/api/v1/monitors/rates",
    "/api/v1/monitors/inflation/history",
    "/api/v1/releases",
    "/api/v1/analyst/availability",
    "/health",
    "/readiness",
]


@pytest.fixture
def operator_token(monkeypatch):
    """A synthetic, non-secret sentinel — never a real token."""
    from app.core.config import settings

    token = "test-operator-token-not-a-real-secret"
    monkeypatch.setattr(settings, "operator_token", token)
    return token


class TestOperatorEndpointsAreNotAnonymouslyPublic:
    """The #34 audit's highest-severity functional finding: three
    endpoints that drive outbound provider traffic and write canonical
    economic data were reachable by anyone who knew the URL."""

    @pytest.mark.parametrize(("method", "path"), OPERATOR_ENDPOINTS)
    def test_rejected_without_a_token(self, client, operator_token, method, path):
        response = client.request(method, path)

        assert response.status_code == 401
        assert "authorization" in response.json()["detail"].lower()

    @pytest.mark.parametrize(("method", "path"), OPERATOR_ENDPOINTS)
    def test_rejected_with_a_wrong_token(self, client, operator_token, method, path):
        response = client.request(method, path, headers={OPERATOR_TOKEN_HEADER: "wrong-token"})

        assert response.status_code == 401

    @pytest.mark.parametrize(("method", "path"), OPERATOR_ENDPOINTS)
    def test_accepted_with_the_correct_token(self, client, operator_token, monkeypatch, method, path):
        """Authorization passes; the request then proceeds on its own
        merits. What matters here is only that it is no longer a 401.

        No real provider is contacted: FRED is unconfigured (so its two
        routes stop at their own configuration guard) and the Treasury
        client -- which needs no API key and would otherwise perform a
        genuine multi-month ingestion -- is replaced with one that
        fails immediately.
        """
        from app.clients.treasury import TreasuryUpstreamError
        from app.core.config import settings

        monkeypatch.setattr(settings, "fred_api_key", None)

        def _refuse(*args, **kwargs):
            raise TreasuryUpstreamError("stubbed: no live provider call in tests")

        monkeypatch.setattr("app.clients.treasury.TreasuryClient.get_month", _refuse)

        response = client.request(method, path, headers={OPERATOR_TOKEN_HEADER: operator_token})

        assert response.status_code != 401

    @pytest.mark.parametrize(("method", "path"), OPERATOR_ENDPOINTS)
    def test_production_without_a_token_fails_closed_not_open(self, client, monkeypatch, method, path):
        """A forgotten environment variable must not leave these
        standing open on the public internet."""
        from app.core.config import settings

        monkeypatch.setattr(settings, "operator_token", None)
        monkeypatch.setattr(settings, "environment", "production")

        response = client.request(method, path)

        assert response.status_code == 503
        assert "not available" in response.json()["detail"].lower()

    def test_the_rejection_never_says_why(self, client, operator_token):
        """Absent, malformed and wrong are each information a prober
        would like; all three produce the same answer."""
        bodies = {
            client.post("/api/v1/rates/sync").json()["detail"],
            client.post("/api/v1/rates/sync", headers={OPERATOR_TOKEN_HEADER: ""}).json()["detail"],
            client.post("/api/v1/rates/sync", headers={OPERATOR_TOKEN_HEADER: "nope"}).json()["detail"],
        }
        assert len(bodies) == 1


class TestPublicReadsRemainPublic:
    @pytest.mark.parametrize("path", PUBLIC_READ_ENDPOINTS)
    def test_no_token_required(self, client, operator_token, path):
        """Hardening must not have closed the product itself."""
        assert client.get(path).status_code == 200


class TestLegacyAiRouteIsNotExposed:
    def test_the_superseded_tool_calling_route_is_unmounted(self, client):
        """#33 replaced it; it accepted an unbounded message and could
        issue up to five provider calls per request."""
        assert client.post("/api/v1/ai/query", json={"message": "hello"}).status_code == 404

    def test_it_cannot_be_enabled_in_production(self, monkeypatch):
        from app.core.config import Settings

        candidate = Settings()
        monkeypatch.setattr(candidate, "environment", "production")
        monkeypatch.setattr(candidate, "enable_legacy_ai_route", True)
        # main.py's guard is `enabled and not is_production`.
        assert not (candidate.enable_legacy_ai_route and not candidate.is_production)


class TestRequestSizeLimit:
    def test_an_oversized_declared_body_is_rejected_before_parsing(self, client):
        from app.core.config import settings

        oversized = "x" * (settings.max_request_body_bytes + 1024)
        response = client.post(
            "/api/v1/analyst/explain",
            content=json.dumps({"context": {"type": "INFLATION"}, "question": oversized}),
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 413
        assert "limit" in response.json()["detail"].lower()

    def test_a_normal_body_passes(self, client):
        response = client.post("/api/v1/analyst/explain", json={"context": {"type": "INFLATION"}, "question": "Why?"})

        assert response.status_code != 413


class TestSecurityHeaders:
    @pytest.mark.parametrize("header", sorted(SECURITY_HEADERS))
    def test_present_on_a_successful_response(self, client, header):
        assert client.get("/health").headers.get(header) == SECURITY_HEADERS[header]

    @pytest.mark.parametrize("header", sorted(SECURITY_HEADERS))
    def test_present_on_an_error_response(self, client, header):
        """An error response is exactly where a missing header matters."""
        assert client.get("/api/v1/monitors/nope/history").headers.get(header) == SECURITY_HEADERS[header]

    def test_no_content_security_policy_is_claimed_by_the_api(self):
        """This service returns JSON, never HTML. A CSP here would
        protect nothing; the one that matters belongs to the static host
        and is specified in the deployment document."""
        assert "Content-Security-Policy" not in SECURITY_HEADERS
        assert "Strict-Transport-Security" not in SECURITY_HEADERS


class TestRequestCorrelation:
    def test_every_response_carries_a_request_id(self, client):
        assert client.get("/health").headers.get(REQUEST_ID_HEADER)

    def test_an_inbound_request_id_is_echoed(self, client):
        response = client.get("/health", headers={REQUEST_ID_HEADER: "caller-supplied-id"})

        assert response.headers[REQUEST_ID_HEADER] == "caller-supplied-id"

    def test_an_absurdly_long_inbound_id_is_truncated(self, client):
        """It lands in a log line and a response header; neither should
        accept unbounded caller-supplied text."""
        response = client.get("/health", headers={REQUEST_ID_HEADER: "z" * 500})

        assert len(response.headers[REQUEST_ID_HEADER]) <= 64

    def test_ids_differ_between_requests(self, client):
        first = client.get("/health").headers[REQUEST_ID_HEADER]
        second = client.get("/health").headers[REQUEST_ID_HEADER]

        assert first != second

    def test_a_request_is_logged_with_route_template_not_the_raw_path(self, client, caplog):
        """A raw path contains user-supplied identifiers and does not
        aggregate; the template does both correctly."""
        import logging

        logger = logging.getLogger("app.api.request")
        logger.disabled = False
        with caplog.at_level(logging.INFO, logger="app.api.request"):
            client.get("/api/v1/monitors/inflation/history/999999")

        record = next(r for r in caplog.records if r.message == "request")
        # The mount prefix is absent from `path_format` in this FastAPI
        # version (routers are expanded lazily), so the assertion is on
        # the property that matters rather than the exact string: a
        # parameterised template carrying no caller-supplied value.
        assert record.route.endswith("/monitors/{monitor}/history/{recorded_result_id}")
        assert "999999" not in record.route
        assert record.status_code == 404
        assert record.duration_ms >= 0


class TestErrorResponsesDoNotLeakInternals:
    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/series/PCEPILFE%00/observations",  # null byte -> DB error
            "/api/v1/monitors/inflation/history/999999",  # not found
            "/api/v1/releases?limit=99999999",  # validation
        ],
    )
    def test_no_internal_detail_reaches_the_client(self, client, path):
        body = client.get(path).text.lower()

        for leak in ("traceback", "psycopg", "sqlalchemy", "postgresql://", "/users/", "site-packages", "api_key"):
            assert leak not in body


class TestProductionConfigurationErrors:
    def test_development_reports_nothing(self):
        candidate = Settings()
        candidate.environment = "development"
        assert production_configuration_errors(candidate) == []

    def test_production_requires_cors_and_reports_the_variable_name_only(self):
        candidate = Settings()
        candidate.environment = "production"
        candidate.database_url = "postgresql+psycopg://u:p@h/db"
        candidate.cors_allowed_origins = []
        candidate.operator_token = "set"

        errors = production_configuration_errors(candidate)

        assert any("CORS_ALLOWED_ORIGINS" in error for error in errors)
        # A name, never a value — these lines end up in deploy logs.
        assert not any("postgresql://" in error or "u:p" in error for error in errors)

    def test_production_rejects_a_wildcard_origin(self):
        candidate = Settings()
        candidate.environment = "production"
        candidate.database_url = "x"
        candidate.cors_allowed_origins = ["*"]
        candidate.operator_token = "set"

        assert any("'*' is never accepted" in error for error in production_configuration_errors(candidate))

    def test_production_warns_when_the_operator_token_is_missing(self):
        candidate = Settings()
        candidate.environment = "production"
        candidate.database_url = "x"
        candidate.cors_allowed_origins = ["https://example.test"]
        candidate.operator_token = None

        assert any("OPERATOR_TOKEN" in error for error in production_configuration_errors(candidate))


class TestDeploymentModeDefaults:
    def test_a_typo_is_not_production(self):
        """The safe direction: an unrecognised value yields a permissive
        local app, never a production app running development defaults."""
        for value in ("", "prod", "Production ", "developmnet", "staging"):
            candidate = Settings()
            candidate.environment = value.strip().lower()
            assert candidate.is_production is (value.strip().lower() == "production")

    def test_docs_are_exposed_in_development_and_closed_in_production(self, monkeypatch):
        monkeypatch.delenv("EXPOSE_API_DOCS", raising=False)
        development = Settings()
        development.environment = "development"
        production = Settings()
        production.environment = "production"

        assert development.expose_api_docs is True
        assert production.expose_api_docs is False

    def test_logs_are_json_in_production_and_readable_locally(self, monkeypatch):
        monkeypatch.delenv("LOG_FORMAT", raising=False)
        development = Settings()
        development.environment = "development"
        production = Settings()
        production.environment = "production"

        assert production.log_format_json is True
        assert development.log_format_json is False


class TestCors:
    """CORS is built from configuration at import time, so these assert
    the middleware's own behaviour against a purpose-built app rather
    than re-importing the real one."""

    @staticmethod
    def _app(origins: list[str]):
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware

        app = FastAPI()
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type", "X-Operator-Token", "X-Request-ID"],
        )

        @app.get("/probe")
        def probe():
            return {"ok": True}

        return TestClient(app)

    def test_an_allowed_origin_receives_the_header(self):
        probe = self._app(["https://allowed.example"])

        response = probe.get("/probe", headers={"Origin": "https://allowed.example"})

        assert response.headers["access-control-allow-origin"] == "https://allowed.example"

    def test_a_disallowed_origin_receives_no_allow_header(self):
        probe = self._app(["https://allowed.example"])

        response = probe.get("/probe", headers={"Origin": "https://evil.example"})

        assert "access-control-allow-origin" not in response.headers

    def test_credentials_are_never_allowed(self):
        probe = self._app(["https://allowed.example"])

        response = probe.get("/probe", headers={"Origin": "https://allowed.example"})

        assert "access-control-allow-credentials" not in response.headers

    def test_the_real_app_never_configures_a_wildcard(self):
        from app.core.config import settings

        assert "*" not in settings.cors_allowed_origins


class TestAnalystTelemetryIsCorrelatedAndEmitted:
    """Two #34 findings about #33's instrumentation, both verified.

    The telemetry was correct code that reached no handler (the root
    logger sits at WARNING with none attached), and it carried its own
    identifier rather than the request's, so the Analyst line and the
    access line for one request could not be joined.
    """

    def test_the_analyst_line_shares_the_request_id_with_the_access_line(
        self, client, monkeypatch, caplog
    ):
        import json as _json
        import logging

        from app.core.config import settings

        monkeypatch.setattr(settings, "openai_api_key", "test-sentinel-not-a-real-key")
        monkeypatch.setattr(settings, "openai_model", "test-model")

        class _Responses:
            @staticmethod
            def create(**kwargs):
                class _R:
                    output_text = _json.dumps({"answer": "ok", "evidence_references": [], "limitations": []})
                    usage = None

                return _R()

        class _Client:
            responses = _Responses()

        monkeypatch.setattr("app.services.analyst.OpenAI", lambda **kwargs: _Client())
        for name in ("app.services.analyst", "app.api.request"):
            logging.getLogger(name).disabled = False

        with caplog.at_level(logging.INFO):
            response = client.post(
                "/api/v1/analyst/explain", json={"context": {"type": "INFLATION"}, "question": "Why?"}
            )

        assert response.status_code == 200
        analyst = next(r for r in caplog.records if r.message == "analyst explain")
        access = next(r for r in caplog.records if r.message == "request")

        assert analyst.request_id == access.request_id
        assert analyst.request_id == response.headers[REQUEST_ID_HEADER]

    def test_the_analyst_line_still_carries_every_contracted_field(self, client, monkeypatch, caplog):
        """#34 must not have weakened #33's instrumentation."""
        import json as _json
        import logging

        from app.core.config import settings

        monkeypatch.setattr(settings, "openai_api_key", "test-sentinel-not-a-real-key")
        monkeypatch.setattr(settings, "openai_model", "test-model")

        class _Client:
            class responses:
                @staticmethod
                def create(**kwargs):
                    class _R:
                        output_text = _json.dumps({"answer": "ok", "evidence_references": [], "limitations": []})
                        usage = None

                    return _R()

        monkeypatch.setattr("app.services.analyst.OpenAI", lambda **kwargs: _Client())
        logging.getLogger("app.services.analyst").disabled = False

        with caplog.at_level(logging.INFO, logger="app.services.analyst"):
            client.post("/api/v1/analyst/explain", json={"context": {"type": "INFLATION"}, "question": "Why?"})

        record = next(r for r in caplog.records if r.message == "analyst explain")
        for field in (
            "model", "prompt_version", "context_version", "context_type", "duration_ms",
            "outcome", "evidence_references_returned", "evidence_references_dropped", "question_length",
        ):
            assert hasattr(record, field), f"#33 telemetry lost the {field!r} field"

    def test_application_logs_reach_a_handler_at_all(self):
        """The root cause of the finding: before #34 nothing did."""
        import logging

        from app.core.logging import configure_logging

        configure_logging()
        app_logger = logging.getLogger("app")

        assert app_logger.handlers, "the `app` logger namespace has no handler"
        assert logging.getLogger("app.services.analyst").isEnabledFor(logging.INFO)

    def test_extra_fields_survive_formatting(self):
        """The repo's logging convention is a static message plus
        structured `extra`; the stdlib's default formatter drops it."""
        import logging

        from app.core.logging import JsonFormatter

        record = logging.LogRecord("app.test", logging.INFO, __file__, 1, "analyst explain", None, None)
        record.model = "some-model"
        record.total_tokens = 2096

        rendered = JsonFormatter().format(record)

        assert '"model": "some-model"' in rendered
        assert '"total_tokens": 2096' in rendered
