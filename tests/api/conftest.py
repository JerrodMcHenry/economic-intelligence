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


#: The six approved V1 curated releases, seeded once by
#: alembic/versions/fbbe6b1ab8d9_seed_curated_v1_release_catalog.py and
#: expected to exist for the lifetime of the whole test session, the
#: same as any other migrated schema/data fact -- NOT test data this
#: fixture owns or should ever remove. Identified here only by their
#: (provider, provider_release_id) identity so `release_seed_session`'s
#: cleanup can tell curated rows apart from ones a test created.
_CURATED_RELEASE_PROVIDER_IDENTITIES = {"9", "10", "50", "53", "54", "192"}
#: #56B: the ACTIVE catalog -- the publishers' own releases. The FRED
#: rows above are the migrated baseline too, but INACTIVE since #56B.
_FIRST_PARTY_RELEASE_IDENTITIES = {("BLS", "cpi"), ("BLS", "empsit"), ("BEA", "pio")}


@pytest.fixture
def release_seed_session(test_database_url: str):
    """Same reasoning as `seed_session` above, scoped to the release
    calendar tables instead of series/observations -- a real, committing
    session so an HTTP request's own separate connection can actually
    see what this fixture seeds.

    Cleanup is deliberately NOT a blanket `TRUNCATE economic_releases`:
    the migration-seeded curated catalog (see
    `_CURATED_RELEASE_PROVIDER_IDENTITIES`) must persist for the whole
    test session like any other migrated data, not get wiped out by the
    first test that uses this fixture. `release_occurrences` has no
    baseline data at all (the seed migration creates none), so it's
    still safe to truncate in full. Cleanup restores the catalog's
    migrated activity (#56B: first-party active, FRED inactive) -- a
    sync-path test may change it on purpose (to isolate itself), and
    that must never leak into the next test.
    """
    engine = create_engine(test_database_url)
    session = Session(bind=engine)
    try:
        yield session
    finally:
        session.rollback()
        session.execute(text("TRUNCATE TABLE release_occurrences RESTART IDENTITY CASCADE"))
        # Restore the MIGRATED baseline exactly (#56B): the curated FRED
        # rows present but inactive, the first-party rows present and
        # active with active mappings, and nothing else.
        placeholders = ", ".join(f"'{provider_release_id}'" for provider_release_id in _CURATED_RELEASE_PROVIDER_IDENTITIES)
        first_party = " OR ".join(
            f"(provider = '{provider}' AND provider_release_id = '{release_id}')"
            for provider, release_id in sorted(_FIRST_PARTY_RELEASE_IDENTITIES)
        )
        session.execute(
            text(
                f"DELETE FROM economic_releases WHERE NOT ((provider = 'FRED' AND provider_release_id IN ({placeholders})) "
                f"OR {first_party})"
            )
        )
        session.execute(
            text(f"UPDATE economic_releases SET active = false WHERE provider = 'FRED' AND provider_release_id IN ({placeholders})")
        )
        session.execute(text(f"UPDATE economic_releases SET active = true WHERE {first_party}"))
        session.execute(
            text(
                "UPDATE release_series_mappings SET active = true WHERE economic_release_id IN "
                f"(SELECT id FROM economic_releases WHERE {first_party})"
            )
        )
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


@pytest.fixture(autouse=True)
def _reset_analyst_rate_limiter():
    """Clear the Analyst rate limiter between API tests (Increment #34).

    The limiter is module-level in-process state, so without this it
    accumulates across the whole suite and an unrelated test eventually
    receives a 429 instead of the status it asserts. That is not a test
    smell to paper over -- it is the same per-process accumulation the
    limiter is supposed to have in production, surfacing correctly here.
    """
    from app.api.analyst import _analyst_rate_limiter

    _analyst_rate_limiter.reset()
    yield
    _analyst_rate_limiter.reset()
