"""Integration tests for Increment #25C's operational CLI entry point
(`app.operations.run_maintenance`), exercised via direct function call
(`main(argv)`) against the real, isolated test database -- not a
subprocess, for speed, but the REAL `app.db.session.session_scope()`
(via the same `real_session_scope`-style monkeypatch
`tests/integration/test_process_release_cli.py` already uses), so this
proves the actual production wiring (settings -> FREDClient ->
MaintenanceOrchestrator -> session_scope), not a lookalike. FRED is
mocked at the FREDClient-*method* boundary, never a live call.
"""

from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest

from app.clients.fred import FREDClient, FREDTimeoutError
from app.db.models import EconomicRelease, EconomicSeries, MaintenanceSweep, ReleaseSeriesMapping
from app.operations.run_maintenance import main
from app.repositories.release_repository import ReleaseRepository

AS_OF = datetime.now(timezone.utc).date()


@pytest.fixture
def configured_settings(monkeypatch, test_database_url):
    """FRED_API_KEY set to an obviously-fake, non-secret placeholder --
    never a real key -- plus DATABASE_URL pointed at the test database,
    for the duration of one test. Mirrors
    `tests/integration/test_process_release_cli.py`'s own identical
    fixture exactly."""
    from app.core.config import settings
    from app.db import session as session_module

    monkeypatch.setattr(settings, "fred_api_key", "test-key-not-a-real-secret")
    monkeypatch.setattr(settings, "database_url", test_database_url)
    session_module._get_engine.cache_clear()
    session_module._get_session_factory.cache_clear()
    yield settings
    session_module._get_engine.cache_clear()
    session_module._get_session_factory.cache_clear()


def _seed_release_mapping_and_occurrence(scheduled_date=AS_OF, provider_release_id="9501"):
    from app.db.session import session_scope

    with session_scope() as session:
        release = EconomicRelease(name="Maintenance CLI Test Release", provider="FRED", provider_release_id=provider_release_id, active=True)
        session.add(release)
        session.flush()
        session.add(ReleaseSeriesMapping(economic_release_id=release.id, series_id="UNRATE", active=True))
        occurrence = ReleaseRepository(session).upsert_occurrence(release.id, scheduled_date)
        session.flush()
        return release.id, occurrence.id


def _cleanup(release_id: int, sweep_id: int | None = None):
    from app.db.session import session_scope

    with session_scope() as session:
        session.execute(EconomicRelease.__table__.delete().where(EconomicRelease.id == release_id))
        session.execute(EconomicSeries.__table__.delete().where(EconomicSeries.series_id == "UNRATE"))
        if sweep_id is not None:
            session.execute(MaintenanceSweep.__table__.delete().where(MaintenanceSweep.id == sweep_id))


def _latest_sweep_id() -> int:
    import sqlalchemy as sa

    from app.db.session import session_scope

    with session_scope() as session:
        return session.execute(sa.select(MaintenanceSweep.id).order_by(MaintenanceSweep.id.desc()).limit(1)).scalar_one()


class TestNoDueWork:
    def test_zero_due_work_exits_zero(self, configured_settings, capsys):
        exit_code = main(["--as-of-date", AS_OF.isoformat()])
        sweep_id = _latest_sweep_id()
        try:
            assert exit_code == 0
            out = capsys.readouterr().out
            assert "Due occurrences: 0" in out
            assert "Processed: 0" in out
            assert "Failed: 0" in out
        finally:
            from app.db.session import session_scope

            with session_scope() as session:
                session.execute(MaintenanceSweep.__table__.delete().where(MaintenanceSweep.id == sweep_id))


class TestOneDueOccurrence:
    def test_no_change_occurrence_succeeds_with_zero_exit(self, configured_settings, capsys):
        release_id, occurrence_id = _seed_release_mapping_and_occurrence()
        try:
            with patch.object(FREDClient, "get_observations", return_value=[]):
                exit_code = main(["--as-of-date", AS_OF.isoformat()])
            sweep_id = _latest_sweep_id()

            assert exit_code == 0
            out = capsys.readouterr().out
            assert "Due occurrences: 1" in out
            assert "Processed: 1" in out
            assert "Failed: 0" in out
        finally:
            _cleanup(release_id, sweep_id)


class TestProviderFailure:
    def test_provider_failure_exits_non_zero_and_reports_it_safely(self, configured_settings, capsys):
        release_id, occurrence_id = _seed_release_mapping_and_occurrence()
        try:
            with patch.object(FREDClient, "get_observations", side_effect=FREDTimeoutError("timed out")):
                exit_code = main(["--as-of-date", AS_OF.isoformat()])
            sweep_id = _latest_sweep_id()

            assert exit_code == 1
            out = capsys.readouterr().out
            assert "Failed: 1" in out
        finally:
            _cleanup(release_id, sweep_id)


class TestNotConfigured:
    def test_missing_fred_api_key_exits_two_before_touching_the_database(self, monkeypatch, test_database_url, capsys):
        from app.core.config import settings

        monkeypatch.setattr(settings, "fred_api_key", None)
        monkeypatch.setattr(settings, "database_url", test_database_url)
        exit_code = main([])
        assert exit_code == 2
        err = capsys.readouterr().err
        assert "FRED integration is not configured" in err

    def test_missing_database_url_exits_two(self, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "fred_api_key", "test-key-not-a-real-secret")
        monkeypatch.setattr(settings, "database_url", None)
        exit_code = main([])
        assert exit_code == 2


class TestSafeOutput:
    def test_no_secret_values_ever_appear_in_output(self, configured_settings, capsys):
        exit_code = main(["--as-of-date", AS_OF.isoformat()])
        sweep_id = _latest_sweep_id()
        try:
            captured = capsys.readouterr()
            combined = captured.out + captured.err
            assert "test-key-not-a-real-secret" not in combined
            assert "postgresql" not in combined.lower()
            assert "Traceback" not in combined
        finally:
            from app.db.session import session_scope

            with session_scope() as session:
                session.execute(MaintenanceSweep.__table__.delete().where(MaintenanceSweep.id == sweep_id))


class TestExplicitAsOfDate:
    def test_explicit_as_of_date_is_honored_for_due_work(self, configured_settings, capsys):
        """A same-day-scheduled occurrence, checked with an EARLIER
        explicit as-of-date, must never be treated as due -- proving
        --as-of-date genuinely drives due-work discovery, not just
        cosmetic output."""
        release_id, occurrence_id = _seed_release_mapping_and_occurrence(scheduled_date=date(2026, 8, 10))
        try:
            exit_code = main(["--as-of-date", "2026-08-01"])
            sweep_id = _latest_sweep_id()

            assert exit_code == 0
            out = capsys.readouterr().out
            assert "Due occurrences: 0" in out
        finally:
            _cleanup(release_id, sweep_id)

    def test_invalid_as_of_date_format_is_rejected_by_argument_parsing(self, configured_settings):
        with pytest.raises(SystemExit):
            main(["--as-of-date", "not-a-date"])


class TestRetryWindowArgument:
    def test_custom_retry_window_days_is_honored(self, configured_settings, capsys):
        release_id, occurrence_id = _seed_release_mapping_and_occurrence(scheduled_date=date(2026, 1, 1))
        try:
            # Far outside a 1-day retry window relative to AS_OF -- must not be due.
            exit_code = main(["--as-of-date", AS_OF.isoformat(), "--retry-window-days", "1"])
            sweep_id = _latest_sweep_id()

            assert exit_code == 0
            out = capsys.readouterr().out
            assert "Due occurrences: 0" in out
        finally:
            _cleanup(release_id, sweep_id)
