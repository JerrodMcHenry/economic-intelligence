"""Integration tests for Increment #18's operational CLI entry point
(`app.operations.process_release`), exercised via direct function call
(`main(argv)`) against the real, isolated test database -- not a
subprocess, for speed, but the REAL `app.db.session.session_scope()`
(via the same `real_session_scope`-style monkeypatch
tests/integration/test_transaction_and_safety.py and
test_release_processing_service.py already use), so this proves the
actual production wiring (settings -> FREDClient -> session_scope ->
service), not a lookalike. FRED is mocked at the FREDClient-*method*
boundary, never a live call (see this file's entry in
test_transaction_and_safety.py's `NETWORK_EXCEPTIONS`).
"""

from datetime import date
from unittest.mock import patch

import pytest

from app.clients.fred import FREDClient, FREDTimeoutError
from app.db.models import EconomicRelease, EconomicSeries, ReleaseSeriesMapping
from app.operations.process_release import main
from app.repositories.release_repository import ReleaseRepository

AS_OF = date(2026, 8, 1)


@pytest.fixture
def configured_settings(monkeypatch, test_database_url):
    """FRED_API_KEY set to an obviously-fake, non-secret placeholder --
    never a real key -- plus DATABASE_URL pointed at the test database,
    for the duration of one test."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "fred_api_key", "test-key-not-a-real-secret")
    monkeypatch.setattr(settings, "database_url", test_database_url)
    from app.db import session as session_module

    session_module._get_engine.cache_clear()
    session_module._get_session_factory.cache_clear()
    yield settings
    session_module._get_engine.cache_clear()
    session_module._get_session_factory.cache_clear()


def _seed_release_mapping_and_occurrence(scheduled_date=AS_OF, provider_release_id="9201"):
    from app.db.session import session_scope

    with session_scope() as session:
        release = EconomicRelease(name="CLI Test Release", provider="FRED", provider_release_id=provider_release_id, active=True)
        session.add(release)
        session.flush()
        session.add(ReleaseSeriesMapping(economic_release_id=release.id, series_id="UNRATE", active=True))
        occurrence = ReleaseRepository(session).upsert_occurrence(release.id, scheduled_date)
        session.flush()
        return release.id, occurrence.id


def _cleanup(release_id: int):
    from app.db.session import session_scope

    with session_scope() as session:
        session.execute(EconomicRelease.__table__.delete().where(EconomicRelease.id == release_id))
        session.execute(EconomicSeries.__table__.delete().where(EconomicSeries.series_id == "UNRATE"))


def _seed_employment_situation_occurrence(scheduled_date=AS_OF):
    """The REAL Employment Situation release (FRED 50), already mapped
    to PAYEMS/UNRATE by migration 09f4c0959e9f -- not a synthetic
    release, proving Increment #20D.2's own mapping is processable
    through this exact same CLI entrypoint with zero code change to
    this file (docs/architecture/labor-release-integration-v1.md §23)."""
    import sqlalchemy as sa

    from app.db.session import session_scope

    with session_scope() as session:
        release = session.execute(sa.select(EconomicRelease).where(EconomicRelease.provider_release_id == "50")).scalar_one()
        occurrence = ReleaseRepository(session).upsert_occurrence(release.id, scheduled_date)
        session.flush()
        return occurrence.id


def _cleanup_employment_situation_occurrence(occurrence_id: int):
    from app.db.models import ReleaseOccurrence
    from app.db.session import session_scope

    with session_scope() as session:
        session.execute(ReleaseOccurrence.__table__.delete().where(ReleaseOccurrence.id == occurrence_id))


class TestEmploymentSituationProcessableThroughTheSameCli:
    def test_employment_situation_occurrence_processes_successfully(self, configured_settings, capsys):
        occurrence_id = _seed_employment_situation_occurrence()
        try:
            with patch.object(FREDClient, "get_observations", return_value=[]):
                exit_code = main(["--occurrence-id", str(occurrence_id), "--as-of-date", AS_OF.isoformat()])
        finally:
            _cleanup_employment_situation_occurrence(occurrence_id)

        assert exit_code == 0
        out = capsys.readouterr().out
        assert "Status: NO_CHANGE" in out
        assert f"Release occurrence: {occurrence_id}" in out


class TestValidOccurrence:
    def test_valid_occurrence_no_change_succeeds_with_zero_exit(self, configured_settings, capsys):
        release_id, occurrence_id = _seed_release_mapping_and_occurrence()
        try:
            # No observations returned -- nothing to classify, so the
            # pipeline never needs get_series_info at all (unmocked
            # here deliberately: if it were called, it would attempt a
            # real network request and this test would fail/hang,
            # which is exactly the proof this behavior is correct).
            with patch.object(FREDClient, "get_observations", return_value=[]):
                exit_code = main(["--occurrence-id", str(occurrence_id), "--as-of-date", AS_OF.isoformat()])
        finally:
            _cleanup(release_id)

        assert exit_code == 0
        out = capsys.readouterr().out
        assert "Status: NO_CHANGE" in out
        assert f"Release occurrence: {occurrence_id}" in out

    def test_valid_occurrence_with_a_new_observation_succeeds_and_summarizes_it(self, configured_settings, capsys):
        release_id, occurrence_id = _seed_release_mapping_and_occurrence()
        payload = [{"date": "2026-01-01", "value": "4.1"}]
        try:
            with patch.object(FREDClient, "get_observations", return_value=payload):
                with patch.object(FREDClient, "get_series_info", return_value={"id": "UNRATE", "title": "Unemployment Rate", "units": "Percent"}):
                    exit_code = main(["--occurrence-id", str(occurrence_id), "--as-of-date", AS_OF.isoformat()])
        finally:
            _cleanup(release_id)

        assert exit_code == 0
        out = capsys.readouterr().out
        assert "Status: CHANGED" in out
        assert "New observation count: 1" in out
        assert "1 new observation detected" in out


class TestInvalidOccurrence:
    def test_nonexistent_occurrence_id_exits_non_zero_with_safe_message(self, configured_settings, capsys):
        exit_code = main(["--occurrence-id", "999999999", "--as-of-date", AS_OF.isoformat()])
        assert exit_code == 1
        err = capsys.readouterr().err
        assert "999999999" in err
        assert "does not exist" in err


class TestIneligibleOccurrence:
    def test_future_scheduled_occurrence_exits_non_zero_with_safe_message(self, configured_settings, capsys):
        release_id, occurrence_id = _seed_release_mapping_and_occurrence(scheduled_date=date(2099, 1, 1))
        try:
            exit_code = main(["--occurrence-id", str(occurrence_id), "--as-of-date", AS_OF.isoformat()])
        finally:
            _cleanup(release_id)

        assert exit_code == 1
        err = capsys.readouterr().err
        assert "not yet eligible" in err


class TestProviderFailure:
    def test_provider_failure_exits_non_zero_and_reports_it_safely(self, configured_settings, capsys):
        release_id, occurrence_id = _seed_release_mapping_and_occurrence()
        try:
            with patch.object(FREDClient, "get_observations", side_effect=FREDTimeoutError("timed out")):
                exit_code = main(["--occurrence-id", str(occurrence_id), "--as-of-date", AS_OF.isoformat()])
        finally:
            _cleanup(release_id)

        assert exit_code == 1
        out = capsys.readouterr().out
        assert "Status: FAILED_PROVIDER" in out
        assert "provider check failed" in out
        assert "FRED request timed out." in out


class TestNotConfigured:
    def test_missing_fred_api_key_exits_non_zero_before_touching_the_database(self, monkeypatch, test_database_url, capsys):
        from app.core.config import settings

        monkeypatch.setattr(settings, "fred_api_key", None)
        monkeypatch.setattr(settings, "database_url", test_database_url)
        exit_code = main(["--occurrence-id", "1"])
        assert exit_code == 1
        err = capsys.readouterr().err
        assert "FRED integration is not configured" in err

    def test_missing_database_url_exits_non_zero(self, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "fred_api_key", "test-key-not-a-real-secret")
        monkeypatch.setattr(settings, "database_url", None)
        exit_code = main(["--occurrence-id", "1"])
        assert exit_code == 1


class TestSafeOutput:
    def test_no_secret_values_ever_appear_in_output(self, configured_settings, capsys):
        release_id, occurrence_id = _seed_release_mapping_and_occurrence()
        try:
            with patch.object(FREDClient, "get_observations", return_value=[]):
                main(["--occurrence-id", str(occurrence_id), "--as-of-date", AS_OF.isoformat()])
        finally:
            _cleanup(release_id)

        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "test-key-not-a-real-secret" not in combined
        assert "postgresql" not in combined.lower()
        assert "Traceback" not in combined

    def test_provider_failure_output_never_leaks_a_stack_trace(self, configured_settings, capsys):
        release_id, occurrence_id = _seed_release_mapping_and_occurrence()
        try:
            with patch.object(FREDClient, "get_observations", side_effect=FREDTimeoutError("timed out")):
                main(["--occurrence-id", str(occurrence_id), "--as-of-date", AS_OF.isoformat()])
        finally:
            _cleanup(release_id)

        combined = "".join(capsys.readouterr())
        assert "Traceback" not in combined
        assert "File \"" not in combined


class TestLockContention:
    """Increment #25C: the manual CLI now shares the same PostgreSQL
    advisory lock the automated orchestrator uses (frozen contract
    §59) -- proven here by holding the lock via a second, independent
    session before invoking `main()`."""

    def test_occurrence_already_locked_by_another_process_exits_non_zero_with_a_safe_message(self, configured_settings, capsys):
        import sqlalchemy as sa

        from app.db.session import session_scope
        from app.services.release_processing import _OCCURRENCE_LOCK_NAMESPACE

        release_id, occurrence_id = _seed_release_mapping_and_occurrence()
        try:
            with session_scope() as holder_session:
                acquired = holder_session.execute(
                    sa.select(sa.func.pg_try_advisory_xact_lock(_OCCURRENCE_LOCK_NAMESPACE, occurrence_id))
                ).scalar_one()
                assert acquired is True

                exit_code = main(["--occurrence-id", str(occurrence_id), "--as-of-date", AS_OF.isoformat()])
        finally:
            _cleanup(release_id)

        assert exit_code == 1
        err = capsys.readouterr().err
        assert "already being processed" in err


class TestExplicitAsOfDate:
    def test_explicit_as_of_date_is_honored_for_eligibility(self, configured_settings, capsys):
        """A same-day-scheduled occurrence, checked with an EARLIER
        explicit as-of-date, must be rejected as not yet eligible --
        proving --as-of-date genuinely drives the eligibility decision,
        not just cosmetic output."""
        release_id, occurrence_id = _seed_release_mapping_and_occurrence(scheduled_date=date(2026, 8, 10))
        try:
            exit_code = main(["--occurrence-id", str(occurrence_id), "--as-of-date", "2026-08-01"])
        finally:
            _cleanup(release_id)

        assert exit_code == 1
        assert "not yet eligible" in capsys.readouterr().err

    def test_invalid_as_of_date_format_is_rejected_by_argument_parsing(self, configured_settings):
        with pytest.raises(SystemExit):
            main(["--occurrence-id", "1", "--as-of-date", "not-a-date"])
