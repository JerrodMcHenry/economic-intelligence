"""Transaction semantics, database-failure behavior, and the
AI-orchestration/network independence guards for this integration
suite.

Does not redesign app/db/session.py's transaction ownership -- these
tests exercise the REAL, unmodified `session_scope()` against the
isolated test database (via a scoped, auto-reverting monkeypatch of
`settings.database_url` and the two lru_cache'd singletons it feeds,
restored after each test) rather than reimplementing its logic
separately, so what's proven here is the actual production code path,
not a lookalike.
"""

import ast
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.db.models import EconomicObservation, EconomicSeries
from app.models.series import Observation, SeriesResponse
from app.repositories.series_repository import SeriesRepository
from app.services.economic_data import EconomicDataService

REPO_ROOT = Path(__file__).resolve().parents[2]
INTEGRATION_DIR = Path(__file__).resolve().parent


@pytest.fixture
def real_session_scope(monkeypatch, test_database_url):
    """Point the REAL `app.db.session.session_scope`/`settings.database_url`
    at the isolated test database for the duration of one test only.
    `monkeypatch` auto-reverts the attribute; the two lru_cache'd
    singletons (`_get_engine`/`_get_session_factory`) are explicitly
    cleared both before (so the patched URL takes effect) and after (so
    the next real use of the app anywhere in this process re-resolves
    against the actual configured DATABASE_URL, never the test one)."""
    from app.core.config import settings
    from app.db import session as session_module

    monkeypatch.setattr(settings, "database_url", test_database_url)
    session_module._get_engine.cache_clear()
    session_module._get_session_factory.cache_clear()
    try:
        yield session_module.session_scope
    finally:
        session_module._get_engine.cache_clear()
        session_module._get_session_factory.cache_clear()


class TestTransactionBehavior:
    def test_successful_block_commits(self, real_session_scope, db_session):
        with real_session_scope() as session:
            SeriesRepository(session).save_series(
                SeriesResponse(series_id="TXCOMMIT", title="t", units="u", observations=[])
            )
        # Verify via a SEPARATE session/connection (db_session's own
        # transaction), proving the write is actually durable, not just
        # visible within the same in-flight transaction.
        found = db_session.execute(select(EconomicSeries).where(EconomicSeries.series_id == "TXCOMMIT")).scalar_one_or_none()
        assert found is not None
        # Cleaned up through a REAL session: `db_session` is rolled back at
        # teardown, so deleting through it never removed this row (#56B
        # found TXCOMMIT left in the test database by every run).
        with real_session_scope() as cleanup:
            cleanup.execute(EconomicSeries.__table__.delete().where(EconomicSeries.series_id == "TXCOMMIT"))

    def test_exception_inside_block_causes_rollback(self, real_session_scope, db_session):
        class _DeliberateFailure(Exception):
            pass

        with pytest.raises(_DeliberateFailure):
            with real_session_scope() as session:
                SeriesRepository(session).save_series(
                    SeriesResponse(series_id="TXROLLBACK", title="t", units="u", observations=[])
                )
                raise _DeliberateFailure("simulated mid-operation failure")

        found = db_session.execute(
            select(EconomicSeries).where(EconomicSeries.series_id == "TXROLLBACK")
        ).scalar_one_or_none()
        assert found is None  # no partial write left behind

    def test_partial_multi_step_write_is_not_left_behind_after_rollback(self, real_session_scope, db_session):
        """A series row AND its observations, written in one block that
        then fails -- neither should survive, not just the last step."""
        class _DeliberateFailure(Exception):
            pass

        with pytest.raises(_DeliberateFailure):
            with real_session_scope() as session:
                repo = SeriesRepository(session)
                repo.save_series(
                    SeriesResponse(
                        series_id="TXPARTIAL",
                        title="t",
                        units="u",
                        observations=[Observation(date=__import__("datetime").date(2024, 1, 1), value=1.0)],
                    )
                )
                session.flush()
                raise _DeliberateFailure("fail after the write, before commit")

        series_found = db_session.execute(
            select(EconomicSeries).where(EconomicSeries.series_id == "TXPARTIAL")
        ).scalar_one_or_none()
        assert series_found is None
        obs_count = db_session.execute(
            select(EconomicObservation).join(EconomicSeries).where(EconomicSeries.series_id == "TXPARTIAL")
        ).all()
        assert obs_count == []


class TestDatabaseFailureBehavior:
    def test_unavailable_database_propagates_operational_error_unmapped(self):
        """Service/repository layer does not catch OperationalError --
        that mapping is Increment 012's job (HTTP layer), not this
        layer's. A deliberately unreachable port (not a real host/creds
        issue) proves this safely and fast, with no real credentials
        anywhere in this test."""
        broken_engine = create_engine("postgresql+psycopg://localhost:1/economic_intelligence_test", pool_pre_ping=False)
        broken_session = Session(bind=broken_engine)
        try:
            with pytest.raises(OperationalError):
                SeriesRepository(broken_session).get_series_by_series_id("UNRATE")
        finally:
            broken_session.close()
            broken_engine.dispose()

    def test_integrity_constraint_on_duplicate_observation_date(self, db_session):
        """The real DB-level UNIQUE(economic_series_id, observation_date)
        constraint (app/db/models.py) is enforced by PostgreSQL itself,
        not merely assumed -- bypassing save_series's own upsert-checking
        logic by inserting duplicate raw ORM rows directly."""
        import datetime

        series = EconomicSeries(series_id="DUPTEST", title="t", units="u", source="FRED")
        db_session.add(series)
        db_session.flush()
        db_session.add(EconomicObservation(economic_series_id=series.id, observation_date=datetime.date(2024, 1, 1), value=1.0))
        db_session.flush()
        db_session.add(EconomicObservation(economic_series_id=series.id, observation_date=datetime.date(2024, 1, 1), value=2.0))
        with pytest.raises(IntegrityError):
            db_session.flush()


def _imported_module_names(file_path: Path) -> set[str]:
    tree = ast.parse(file_path.read_text(), filename=str(file_path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


class TestAIAndNetworkIndependence:
    # AI is forbidden everywhere in this suite, without exception --
    # nothing repository/service/discovery-level ever needs it.
    AI_FORBIDDEN_PREFIXES = ("openai", "app.services.ai")
    # httpx/FREDClient are forbidden everywhere EXCEPT test_discovery_service.py
    # (Increment 013) and test_release_calendar_service.py (Increment
    # #17A): each legitimately imports FREDClient only to mock one of
    # its methods (`patch.object(FREDClient, "search_series", ...)` /
    # `patch.object(FREDClient, "get_release_dates", ...)`, per each
    # increment's explicit "mock at the FREDClient boundary"
    # requirement) -- neither ever constructs a client that makes a
    # real call. Every one of their tests runs in well under a second
    # against only the local isolated Postgres test database, with no
    # other network configured, which this repo's automated tests never
    # have access to -- circumstantial but consistent confirmation
    # alongside the mocking pattern itself that no live call occurs.
    # These exclusions existed before their respective increments only
    # in the sense that no file needed them yet; they do not weaken the
    # guarantee for any other file in this directory, which remains
    # absolute.
    NETWORK_FORBIDDEN_PREFIXES = ("httpx", "app.clients.fred")
    # Increment #18: test_release_processing_service.py and
    # test_process_release_cli.py legitimately import FREDClient only
    # to mock get_observations/get_series_info
    # (`patch.object(FREDClient, "get_observations", ...)`), the same
    # documented, narrow pattern test_release_calendar_service.py
    # already established for get_release_dates -- neither ever
    # constructs a client that makes a real call.
    NETWORK_EXCEPTIONS = {
        "test_discovery_service.py",
        "test_release_calendar_service.py",
        "test_release_processing_service.py",
        "test_process_release_cli.py",
        # Increment #25C: these mock FREDClient at the exact same
        # method boundary (get_observations/get_series_info) as
        # test_release_processing_service.py/test_process_release_cli.py
        # already do -- never a live call -- to prove the automated
        # maintenance orchestrator and its own CLI entry point compose
        # correctly with the existing, unmodified release-processing
        # service.
        "test_maintenance_orchestrator.py",
        "test_run_maintenance_cli.py",
        # Increment #25G: same exact method-boundary mock, to prove the
        # Since Last Visit read model correctly reflects real
        # release-processing output -- never a live call.
        "test_since_last_visit_service.py",
    }

    def test_no_integration_test_file_imports_ai(self):
        """Static guard: no file in tests/integration/ imports openai or
        app.services.ai(_tools) -- checked by parsing imports, not by
        trusting a comment."""
        violations = []
        for file_path in sorted(INTEGRATION_DIR.glob("*.py")):
            for module_name in _imported_module_names(file_path):
                if any(module_name == p or module_name.startswith(p + ".") for p in self.AI_FORBIDDEN_PREFIXES):
                    violations.append(f"{file_path.name}: imports '{module_name}'")
        assert violations == [], "integration test file imports AI:\n" + "\n".join(violations)

    def test_no_integration_test_file_imports_fred_or_http_except_the_documented_discovery_mock(self):
        """Static guard: no file in tests/integration/ imports httpx or
        FREDClient, except test_discovery_service.py, which imports
        FREDClient only to mock its search_series method -- see this
        class's NETWORK_EXCEPTIONS docstring above for why that one,
        narrow exception is safe."""
        violations = []
        for file_path in sorted(INTEGRATION_DIR.glob("*.py")):
            if file_path.name in self.NETWORK_EXCEPTIONS:
                continue
            for module_name in _imported_module_names(file_path):
                if any(module_name == p or module_name.startswith(p + ".") for p in self.NETWORK_FORBIDDEN_PREFIXES):
                    violations.append(f"{file_path.name}: imports '{module_name}'")
        assert violations == [], "integration test file imports a forbidden network dependency:\n" + "\n".join(violations)

    def test_economic_data_service_constructed_without_fred_client_in_this_suite(self):
        """Every EconomicDataService() constructed in this suite is
        given no FREDClient -- confirmed directly, not just by absence
        of an import: its FRED-backed methods (get_series/sync_series)
        would fail loudly (AttributeError on None) if ever accidentally
        invoked here, since none of this suite's tests call them."""
        service = EconomicDataService()
        assert service._fred_client is None


class TestReleaseCalendarStructuralIndependence:
    """Increment #17A's permanent invariant (see
    docs/architecture/release-intelligence-v1.md #2), checked
    structurally rather than left to convention: release-calendar code
    cannot write an economic observation, recompute a monitor, or call
    AI/news, because none of the modules that could do those things are
    ever imported by it. A file that can't import
    `app.services.economic_data` can't call `sync_series`; one that
    can't import `app.repositories.series_repository` can't write
    `EconomicObservation` directly either."""

    RELEASE_CALENDAR_FILES = [
        Path("app/repositories/release_repository.py"),
        Path("app/services/releases.py"),
        Path("app/api/releases.py"),
    ]

    FORBIDDEN_PREFIXES = (
        "openai",
        "app.services.ai",  # covers app.services.ai and app.services.ai_tools
        "app.services.economic_data",  # owns sync_series / observation writes
        "app.services.inflation",  # owns monitor recomputation
        "app.repositories.series_repository",  # owns EconomicObservation writes directly
        "app.domain.inflation",  # covers app.domain.inflation and app.domain.inflation_what_changed
        "app.services.news",  # doesn't exist yet -- forbidden in advance, not just once added
    )

    def test_release_calendar_files_exist_where_expected(self):
        for file_path in self.RELEASE_CALENDAR_FILES:
            assert (REPO_ROOT / file_path).is_file(), f"expected {file_path} to exist"

    def test_no_release_calendar_file_imports_ai_observation_writes_or_monitor_recomputation(self):
        violations = []
        for file_path in self.RELEASE_CALENDAR_FILES:
            for module_name in _imported_module_names(REPO_ROOT / file_path):
                if any(module_name == p or module_name.startswith(p + ".") for p in self.FORBIDDEN_PREFIXES):
                    violations.append(f"{file_path}: imports '{module_name}'")
        assert violations == [], "release-calendar code imports a forbidden dependency:\n" + "\n".join(violations)

    def test_release_repository_never_imports_fred_or_http(self):
        """Stricter than the general network guard above: the
        repository specifically -- the layer closest to the database --
        must never import FRED/httpx at all, not even via a documented
        test exception (that exception is for the sync *service*, which
        legitimately talks to FRED; the repository never should)."""
        network_prefixes = TestAIAndNetworkIndependence.NETWORK_FORBIDDEN_PREFIXES
        imported = _imported_module_names(REPO_ROOT / "app/repositories/release_repository.py")
        forbidden = {m for m in imported if m in network_prefixes or any(m.startswith(p + ".") for p in network_prefixes)}
        assert forbidden == set(), f"app/repositories/release_repository.py must never import FRED/httpx: {forbidden}"
