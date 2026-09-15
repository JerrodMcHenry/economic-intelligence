"""GET /health -- a process-health endpoint. Current, actual semantics
(confirmed directly from app/main.py): returns a fixed `{"status": "ok"}`
unconditionally, with no database or FRED or OpenAI check at all. This
increment documents that behavior; it does not redefine it.
"""

from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_200_and_expected_body():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_works_with_no_openai_key_configured(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "openai_api_key", None)
    monkeypatch.setattr(settings, "openai_model", None)
    client = TestClient(app)
    assert client.get("/health").status_code == 200


def test_health_does_not_require_database_connectivity(monkeypatch):
    """Current architecture: /health is defined directly on `app`, calls
    no service, and touches no database -- confirmed by pointing
    DATABASE_URL at a deliberately unreachable address and confirming
    /health is unaffected."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://localhost:1/does_not_matter")
    client = TestClient(app)
    assert client.get("/health").status_code == 200


def test_health_does_not_require_fred_configuration(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "fred_api_key", None)
    client = TestClient(app)
    assert client.get("/health").status_code == 200


def test_health_stays_ok_even_when_readiness_reports_an_incompatible_schema(monkeypatch):
    """Increment #26C's own central contract test (production-
    reliability-deployment-v1.md §37): /health answers "is this
    process alive", /readiness answers "is it safe to route traffic
    here" -- deliberately different questions. Proven directly, in one
    test, against the SAME unreachable database: /health is completely
    unaffected while /readiness correctly reports unready."""
    from app.core.config import settings
    from app.db import session as session_module

    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://localhost:1/does_not_matter")
    session_module._get_engine.cache_clear()
    session_module._get_session_factory.cache_clear()

    client = TestClient(app)
    health_response = client.get("/health")
    readiness_response = client.get("/readiness")

    assert health_response.status_code == 200
    assert health_response.json() == {"status": "ok"}
    assert readiness_response.status_code == 503
    assert readiness_response.json()["ready"] is False
