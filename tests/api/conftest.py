"""Fixtures specific to the HTTP API suite (Increment 012).

Reuses tests/conftest.py's `test_database_url` safety guard and
migration setup unchanged -- see that module's docstring. What's unique
to this suite:

- `client`: a FastAPI `TestClient` calling the real ASGI app in-process
  (no real HTTP server, no browser tooling).
- `_redirect_database` (autouse): every API test's request handling goes
  through the REAL, unmodified route -> `session_scope()` path, which
  reads `app.core.config.settings.database_url` at connection time --
  redirected to the isolated test database for this test's duration
  only, via `monkeypatch` (auto-reverts) plus explicit
  `lru_cache.cache_clear()` on the two singletons `app/db/session.py`
  owns (cleared both before, so the redirect takes effect, and after,
  so later use anywhere in this process re-resolves against the real
  configured `DATABASE_URL`, never the test one).
- `seed_session`: deliberately NOT the rollback-isolated `db_session`
  fixture from tests/conftest.py. An HTTP request handled by a real
  FastAPI route opens its OWN, separate PostgreSQL connection via
  `session_scope()` -- a second connection cannot see another
  connection's uncommitted (even SAVEPOINT-released) transaction, so
  seeding data the request needs to actually find requires a REAL
  commit. Isolation here comes from explicit cleanup (`TRUNCATE ...
  RESTART IDENTITY CASCADE`) after each test instead of rollback --
  exactly the "otherwise use explicit safe cleanup against the TEST
  database only" alternative named for this situation.
- `fred_configured`: sets `settings.fred_api_key` to a synthetic,
  non-secret sentinel value (never a real key) so FRED-backed routes
  pass their "is FRED configured at all" check, while `FREDClient`'s
  actual HTTP methods are mocked per-test at the class level (never a
  real network call) -- the narrowest sensible external boundary.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def _redirect_database(monkeypatch, test_database_url):
    from app.core.config import settings
    from app.db import session as session_module

    monkeypatch.setattr(settings, "database_url", test_database_url)
    session_module._get_engine.cache_clear()
    session_module._get_session_factory.cache_clear()
    yield
    session_module._get_engine.cache_clear()
    session_module._get_session_factory.cache_clear()


@pytest.fixture
def seed_session(test_database_url: str):
    """A REAL, committing session against the isolated test database --
    for seeding data an HTTP request (its own separate connection) must
    actually be able to see. Cleans up via TRUNCATE after the test,
    never via rollback (see this module's docstring for why rollback
    isolation doesn't apply here)."""
    engine = create_engine(test_database_url)
    session = Session(bind=engine)
    try:
        yield session
    finally:
        session.rollback()
        session.execute(text("TRUNCATE TABLE economic_observations, economic_series RESTART IDENTITY CASCADE"))
        session.commit()
        session.close()
        engine.dispose()


@pytest.fixture
def fred_configured(monkeypatch):
    """A synthetic, non-secret sentinel -- never a real FRED API key --
    just enough to pass the routes' "is FRED configured" check. Every
    actual FREDClient method call in these tests is separately mocked
    per test; this fixture never causes a real network call on its own."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "fred_api_key", "test-sentinel-not-a-real-key")
