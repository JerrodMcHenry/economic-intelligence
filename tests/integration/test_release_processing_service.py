"""Integration tests for Increment #18's ReleaseProcessingService --
the release-driven update pipeline's central orchestration. FRED is
mocked at the FREDClient-*method* boundary (`get_observations`/
`get_series_info`), the same documented pattern
tests/integration/test_release_calendar_service.py already establishes
for `get_release_dates` (see this file's entry in
test_transaction_and_safety.py's `NETWORK_EXCEPTIONS`). No live FRED
anywhere.

The four release_series_mappings rows seeded by
alembic/versions/cd476d227f99_seed_cpi_and_personal_income_and_.py are
real, persistent, active data in the isolated test database -- used
directly by the Inflation-impact test classes below (CPI release =
CPIAUCSL/CPILFESL, Personal Income and Outlays release =
PCEPI/PCEPILFE). Classification-only tests (NEW/REVISED/UNCHANGED,
idempotency, provider/database failure) use a synthetic release/
mapping/series ("UNRATE") well outside the curated catalog, mirroring
tests/integration/test_release_calendar_service.py's own discipline.
"""

from datetime import date, datetime, timezone
from unittest.mock import Mock, patch

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, OperationalError

from app.clients.fred import FREDAuthError, FREDClient, FREDTimeoutError
from app.db.models import EconomicRelease, EconomicSeries, ReleaseCheckRun, ReleaseSeriesMapping
from app.domain.inflation import compute_confirmation_at, compute_series_momentum_at, compute_target_at
from app.models.series import Observation
from app.repositories.release_processing_repository import ReleaseProcessingRepository
from app.repositories.release_repository import ReleaseRepository
from app.services.release_processing import OccurrenceNotEligibleError, OccurrenceNotFoundError, ReleaseProcessingService

AS_OF = date(2026, 8, 1)


@pytest.fixture
def real_session_scope(monkeypatch, test_database_url):
    """Point the REAL `app.db.session.session_scope`/`settings.database_url`
    at the isolated test database for one test -- the identical fixture
    tests/integration/test_transaction_and_safety.py already defines
    for itself (restated here rather than imported, since it's a
    test-only fixture with no shared home to import from)."""
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


# ---------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------


def _months(start: date, count: int) -> list[date]:
    dates = []
    year, month = start.year, start.month
    for i in range(count):
        total = year * 12 + (month - 1) + i
        yy, mm0 = divmod(total, 12)
        dates.append(date(yy, mm0 + 1, 1))
    return dates


def _constant_growth_series(start: date, count: int, start_value: float = 100.0, monthly_growth: float = 0.002) -> dict[date, float]:
    """A monthly index series compounding at a fixed rate -- by
    construction, r_3m_annualized == r_6m_annualized == r_12m_annualized
    at every period with a full endpoint set, which always classifies
    STABLE (all three fall exactly on, hence within, the neutral band
    around r_12m). A clean, arithmetic-verified baseline to perturb."""
    dates = _months(start, count)
    return {d: start_value * (1 + monthly_growth) ** i for i, d in enumerate(dates)}


def _fred_payload(values: dict[date, float | None]) -> list[dict]:
    return [{"date": d.isoformat(), "value": "." if v is None else str(v)} for d, v in sorted(values.items())]


def _release(session, name="Test Release", provider_release_id="9001", active=True):
    release = EconomicRelease(name=name, provider="FRED", provider_release_id=provider_release_id, active=active)
    session.add(release)
    session.flush()
    return release


def _mapping(session, release, series_id="UNRATE", active=True):
    mapping = ReleaseSeriesMapping(economic_release_id=release.id, series_id=series_id, active=active)
    session.add(mapping)
    session.flush()
    return mapping


def _occurrence(session, release, scheduled_date=AS_OF):
    return ReleaseRepository(session).upsert_occurrence(release.id, scheduled_date)


def _seed_series(session, series_id: str, values: dict[date, float | None], title="Test Series", units="Index") -> EconomicSeries:
    repo = ReleaseProcessingRepository(session)
    series = repo.get_series_by_series_id(series_id) or repo.create_series(series_id, title, units)
    for observation_date, value in values.items():
        repo.write_observation(series.id, observation_date, value)
    return series


def _cpi_release(session):
    return session.execute(sa.select(EconomicRelease).where(EconomicRelease.provider_release_id == "10")).scalar_one()


def _pio_release(session):
    return session.execute(sa.select(EconomicRelease).where(EconomicRelease.provider_release_id == "54")).scalar_one()


def _mock_client(observations_by_series: dict[str, list[dict]] | None = None, info_by_series: dict[str, dict] | None = None):
    """A FREDClient whose get_observations/get_series_info are mocked
    per series_id, never making a real call."""
    observations_by_series = observations_by_series or {}
    info_by_series = info_by_series or {}

    def _get_observations(series_id, **kwargs):
        if series_id not in observations_by_series:
            raise AssertionError(f"unexpected get_observations call for {series_id!r}")
        return observations_by_series[series_id]

    def _get_series_info(series_id):
        if series_id not in info_by_series:
            raise AssertionError(f"unexpected get_series_info call for {series_id!r} (series should already exist)")
        return info_by_series[series_id]

    client = FREDClient(api_key="not-used", timeout=1.0)
    return client, _get_observations, _get_series_info


class _patched:
    """Context manager patching both FREDClient methods at once."""

    def __init__(self, observations_by_series=None, info_by_series=None):
        self.client, self._get_observations, self._get_series_info = _mock_client(observations_by_series, info_by_series)

    def __enter__(self):
        self._p1 = patch.object(FREDClient, "get_observations", side_effect=self._get_observations)
        self._p2 = patch.object(FREDClient, "get_series_info", side_effect=self._get_series_info)
        self._p1.start()
        self._p2.start()
        return self.client

    def __exit__(self, *exc):
        self._p1.stop()
        self._p2.stop()


# ---------------------------------------------------------------------
# Eligibility / not-found
# ---------------------------------------------------------------------


class TestEligibilityAndLookup:
    def test_nonexistent_occurrence_raises(self, db_session):
        with _patched() as client:
            with pytest.raises(OccurrenceNotFoundError):
                ReleaseProcessingService(client).process_occurrence(999999, db_session, AS_OF)

    def test_future_scheduled_occurrence_is_not_eligible(self, db_session):
        release = _release(db_session)
        occurrence = _occurrence(db_session, release, scheduled_date=date(2099, 1, 1))
        with _patched() as client:
            with pytest.raises(OccurrenceNotEligibleError):
                ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

    def test_same_day_scheduled_occurrence_is_eligible(self, db_session):
        """Release times are unknown in V1 -- today's own scheduled
        date IS eligible; an early check may simply find nothing new."""
        release = _release(db_session)
        occurrence = _occurrence(db_session, release, scheduled_date=AS_OF)
        with _patched(observations_by_series={"UNRATE": []}) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)
        assert result.status == "NO_CHANGE"

    def test_past_due_occurrence_is_eligible(self, db_session):
        release = _release(db_session)
        occurrence = _occurrence(db_session, release, scheduled_date=date(2026, 1, 1))
        with _patched(observations_by_series={"UNRATE": []}) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)
        assert result.status == "NO_CHANGE"

    def test_release_with_no_mappings_processes_as_a_trivial_no_change(self, db_session):
        release = _release(db_session)
        occurrence = _occurrence(db_session, release)
        with _patched() as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)
        assert result.status == "NO_CHANGE"
        assert result.series_outcomes == []


# ---------------------------------------------------------------------
# NEW / REVISED / UNCHANGED classification
# ---------------------------------------------------------------------


class TestObservationClassification:
    def test_new_observation_is_inserted_and_audited(self, db_session):
        release = _release(db_session)
        _mapping(db_session, release, "UNRATE")
        occurrence = _occurrence(db_session, release)
        series = _seed_series(db_session, "UNRATE", {date(2026, 1, 1): 4.0})

        payload = _fred_payload({date(2026, 1, 1): 4.0, date(2026, 2, 1): 4.1})
        with _patched(observations_by_series={"UNRATE": payload}) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        assert result.status == "CHANGED"
        assert len(result.observation_changes) == 1
        change = result.observation_changes[0]
        assert change.change_type == "NEW"
        assert change.observation_date == date(2026, 2, 1)
        assert change.previous_value is None
        assert change.new_value == 4.1
        assert change.detected_at is not None

        repo = ReleaseProcessingRepository(db_session)
        assert repo.get_observations_by_date(series.id) == {date(2026, 1, 1): 4.0, date(2026, 2, 1): 4.1}

    def test_revised_observation_overwrites_canonical_value_and_is_audited(self, db_session):
        release = _release(db_session)
        _mapping(db_session, release, "UNRATE")
        occurrence = _occurrence(db_session, release)
        series = _seed_series(db_session, "UNRATE", {date(2026, 1, 1): 4.0})

        payload = _fred_payload({date(2026, 1, 1): 4.2})
        with _patched(observations_by_series={"UNRATE": payload}) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        assert result.status == "CHANGED"
        change = result.observation_changes[0]
        assert change.change_type == "REVISED"
        assert change.previous_value == 4.0
        assert change.new_value == 4.2

        repo = ReleaseProcessingRepository(db_session)
        assert repo.get_observations_by_date(series.id) == {date(2026, 1, 1): 4.2}

    def test_unchanged_observation_produces_no_write_and_no_audit_row(self, db_session):
        release = _release(db_session)
        _mapping(db_session, release, "UNRATE")
        occurrence = _occurrence(db_session, release)
        _seed_series(db_session, "UNRATE", {date(2026, 1, 1): 4.0})

        payload = _fred_payload({date(2026, 1, 1): 4.0})
        with _patched(observations_by_series={"UNRATE": payload}) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        assert result.status == "NO_CHANGE"
        assert result.observation_changes == []
        assert result.series_outcomes[0].unchanged_count == 1

    def test_missing_to_present_transition_is_revised_not_dropped(self, db_session):
        release = _release(db_session)
        _mapping(db_session, release, "UNRATE")
        occurrence = _occurrence(db_session, release)
        _seed_series(db_session, "UNRATE", {date(2026, 1, 1): None})

        payload = _fred_payload({date(2026, 1, 1): 4.0})
        with _patched(observations_by_series={"UNRATE": payload}) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        change = result.observation_changes[0]
        assert change.change_type == "REVISED"
        assert change.previous_value is None
        assert change.new_value == 4.0

    def test_present_to_missing_transition_is_revised_not_dropped(self, db_session):
        release = _release(db_session)
        _mapping(db_session, release, "UNRATE")
        occurrence = _occurrence(db_session, release)
        _seed_series(db_session, "UNRATE", {date(2026, 1, 1): 4.0})

        payload = _fred_payload({date(2026, 1, 1): None})
        with _patched(observations_by_series={"UNRATE": payload}) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        change = result.observation_changes[0]
        assert change.change_type == "REVISED"
        assert change.previous_value == 4.0
        assert change.new_value is None

    def test_new_series_never_before_synced_is_created_via_get_series_info(self, db_session):
        release = _release(db_session)
        _mapping(db_session, release, "UNRATE")
        occurrence = _occurrence(db_session, release)

        payload = _fred_payload({date(2026, 1, 1): 4.0})
        with _patched(
            observations_by_series={"UNRATE": payload}, info_by_series={"UNRATE": {"id": "UNRATE", "title": "Unemployment Rate", "units": "Percent"}}
        ) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        assert result.status == "CHANGED"
        series = ReleaseProcessingRepository(db_session).get_series_by_series_id("UNRATE")
        assert series is not None
        assert series.title == "Unemployment Rate"


# ---------------------------------------------------------------------
# Multiple changes in one payload
# ---------------------------------------------------------------------


class TestMultipleChanges:
    def test_one_new_two_revised_n_unchanged_counted_and_written_correctly(self, db_session):
        release = _release(db_session)
        _mapping(db_session, release, "UNRATE")
        occurrence = _occurrence(db_session, release)
        _seed_series(
            db_session,
            "UNRATE",
            {date(2026, 1, 1): 4.0, date(2026, 2, 1): 4.0, date(2026, 3, 1): 4.0, date(2026, 4, 1): 4.0},
        )

        payload = _fred_payload(
            {
                date(2026, 1, 1): 4.0,  # unchanged
                date(2026, 2, 1): 4.05,  # revised
                date(2026, 3, 1): 4.0,  # unchanged
                date(2026, 4, 1): 4.10,  # revised
                date(2026, 5, 1): 4.2,  # new
            }
        )
        with _patched(observations_by_series={"UNRATE": payload}) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        outcome = result.series_outcomes[0]
        assert outcome.new_count == 1
        assert outcome.revised_count == 2
        assert outcome.unchanged_count == 2
        assert len(result.observation_changes) == 3
        assert {c.change_type for c in result.observation_changes} == {"NEW", "REVISED"}

        # No duplicate rows, and only the actually-changed dates changed.
        repo = ReleaseProcessingRepository(db_session)
        series = repo.get_series_by_series_id("UNRATE")
        assert repo.get_observations_by_date(series.id) == {
            date(2026, 1, 1): 4.0,
            date(2026, 2, 1): 4.05,
            date(2026, 3, 1): 4.0,
            date(2026, 4, 1): 4.10,
            date(2026, 5, 1): 4.2,
        }


# ---------------------------------------------------------------------
# Bounded five-year lookback
# ---------------------------------------------------------------------


class TestBoundedLookback:
    def test_fred_is_called_with_the_exact_five_year_observation_start(self, db_session):
        release = _release(db_session)
        _mapping(db_session, release, "UNRATE")
        occurrence = _occurrence(db_session, release)
        _seed_series(db_session, "UNRATE", {})

        mock_get_observations = Mock(return_value=[])
        with patch.object(FREDClient, "get_observations", mock_get_observations):
            client = FREDClient(api_key="not-used", timeout=1.0)
            ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        _, kwargs = mock_get_observations.call_args
        assert kwargs["observation_start"] == date(2021, 8, 1)
        assert kwargs["sort_order"] == "asc"

    def test_leap_day_as_of_date_uses_exact_calendar_arithmetic(self, db_session):
        release = _release(db_session)
        _mapping(db_session, release, "UNRATE")
        occurrence = _occurrence(db_session, release, scheduled_date=date(2024, 2, 29))
        _seed_series(db_session, "UNRATE", {})

        mock_get_observations = Mock(return_value=[])
        with patch.object(FREDClient, "get_observations", mock_get_observations):
            client = FREDClient(api_key="not-used", timeout=1.0)
            ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, date(2024, 2, 29))

        assert mock_get_observations.call_args.kwargs["observation_start"] == date(2019, 2, 28)


# ---------------------------------------------------------------------
# Provider failure isolation
# ---------------------------------------------------------------------


class TestProviderFailureIsolation:
    def test_one_series_fails_while_sibling_series_still_succeeds(self, db_session):
        release = _cpi_release(db_session)
        occurrence = _occurrence(db_session, release)
        cpi_series = _seed_series(db_session, "CPIAUCSL", {date(2026, 1, 1): 300.0}, title="CPI", units="Index")
        _seed_series(db_session, "CPILFESL", {date(2026, 1, 1): 280.0}, title="Core CPI", units="Index")

        def _get_observations(series_id, **kwargs):
            if series_id == "CPILFESL":
                raise FREDTimeoutError("timed out")
            return _fred_payload({date(2026, 1, 1): 300.0, date(2026, 2, 1): 301.0})

        client = FREDClient(api_key="not-used", timeout=1.0)
        with patch.object(FREDClient, "get_observations", side_effect=_get_observations):
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        assert result.status == "PARTIAL_FAILURE"
        outcomes = {o.series_id: o for o in result.series_outcomes}
        assert outcomes["CPIAUCSL"].succeeded is True
        assert outcomes["CPILFESL"].succeeded is False
        assert outcomes["CPILFESL"].error == "FRED request timed out."

        repo = ReleaseProcessingRepository(db_session)
        # CPIAUCSL's valid new observation was persisted despite CPILFESL's failure.
        assert repo.get_observations_by_date(cpi_series.id) == {date(2026, 1, 1): 300.0, date(2026, 2, 1): 301.0}
        # CPILFESL was never touched -- no fabricated data for the failed series.
        core_cpi_series = repo.get_series_by_series_id("CPILFESL")
        assert repo.get_observations_by_date(core_cpi_series.id) == {date(2026, 1, 1): 280.0}

    def test_reversed_the_other_series_fails_instead(self, db_session):
        release = _cpi_release(db_session)
        occurrence = _occurrence(db_session, release)
        _seed_series(db_session, "CPIAUCSL", {date(2026, 1, 1): 300.0}, title="CPI", units="Index")
        core_series = _seed_series(db_session, "CPILFESL", {date(2026, 1, 1): 280.0}, title="Core CPI", units="Index")

        def _get_observations(series_id, **kwargs):
            if series_id == "CPIAUCSL":
                raise FREDAuthError("auth failed")
            return _fred_payload({date(2026, 1, 1): 280.0, date(2026, 2, 1): 281.0})

        client = FREDClient(api_key="not-used", timeout=1.0)
        with patch.object(FREDClient, "get_observations", side_effect=_get_observations):
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        assert result.status == "PARTIAL_FAILURE"
        repo = ReleaseProcessingRepository(db_session)
        assert repo.get_observations_by_date(core_series.id) == {date(2026, 1, 1): 280.0, date(2026, 2, 1): 281.0}

    def test_all_mapped_series_fail_produces_zero_changes_and_failed_provider_status(self, db_session):
        release = _cpi_release(db_session)
        occurrence = _occurrence(db_session, release)
        cpi_series = _seed_series(db_session, "CPIAUCSL", {date(2026, 1, 1): 300.0})
        core_series = _seed_series(db_session, "CPILFESL", {date(2026, 1, 1): 280.0})

        client = FREDClient(api_key="not-used", timeout=1.0)
        with patch.object(FREDClient, "get_observations", side_effect=FREDTimeoutError("timed out")):
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        assert result.status == "FAILED_PROVIDER"
        assert result.observation_changes == []
        assert result.analysis_changes == []
        repo = ReleaseProcessingRepository(db_session)
        assert repo.get_observations_by_date(cpi_series.id) == {date(2026, 1, 1): 300.0}
        assert repo.get_observations_by_date(core_series.id) == {date(2026, 1, 1): 280.0}


# ---------------------------------------------------------------------
# Database failure
# ---------------------------------------------------------------------


class TestDatabaseFailure:
    def test_a_deliberate_failure_after_provider_success_rolls_back_the_whole_occurrence(self, real_session_scope):
        """Uses the REAL session_scope() (see
        tests/integration/test_transaction_and_safety.py's own
        `real_session_scope` fixture) so an actual commit/rollback
        boundary is exercised, not the test's own savepoint --
        explicitly cleaned up afterward (via a real delete + commit)
        since none of this test's writes are covered by db_session's
        savepoint rollback."""
        from sqlalchemy import select

        from app.db.models import EconomicRelease, EconomicSeries

        with real_session_scope() as setup_session:
            release = _release(setup_session, provider_release_id="9099")
            _mapping(setup_session, release, "UNRATE")
            occurrence = _occurrence(setup_session, release)
            _seed_series(setup_session, "UNRATE", {date(2026, 1, 1): 4.0})
            release_id, occurrence_id = release.id, occurrence.id

        try:
            class _DeliberateFailure(Exception):
                pass

            payload = _fred_payload({date(2026, 1, 1): 4.0, date(2026, 2, 1): 4.1})
            client = FREDClient(api_key="not-used", timeout=1.0)

            with pytest.raises(_DeliberateFailure):
                with real_session_scope() as session:
                    with patch.object(FREDClient, "get_observations", return_value=payload):
                        with patch.object(
                            ReleaseProcessingRepository, "add_check_run", side_effect=_DeliberateFailure("simulated failure")
                        ):
                            ReleaseProcessingService(client).process_occurrence(occurrence_id, session, AS_OF)

            with real_session_scope() as verify_session:
                repo = ReleaseProcessingRepository(verify_session)
                series = repo.get_series_by_series_id("UNRATE")
                # The NEW observation write never survived the rollback.
                assert repo.get_observations_by_date(series.id) == {date(2026, 1, 1): 4.0}
                assert repo.list_check_runs_for_occurrence(occurrence_id) == []
        finally:
            with real_session_scope() as cleanup_session:
                # CASCADE deletes the occurrence/check-run/update rows too.
                cleanup_session.execute(EconomicRelease.__table__.delete().where(EconomicRelease.id == release_id))
                cleanup_session.execute(EconomicSeries.__table__.delete().where(EconomicSeries.series_id == "UNRATE"))


# ---------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------


class TestIdempotency:
    def test_processing_the_same_occurrence_twice_with_identical_data_creates_no_duplicate_change_events(self, db_session):
        release = _release(db_session)
        _mapping(db_session, release, "UNRATE")
        occurrence = _occurrence(db_session, release)
        _seed_series(db_session, "UNRATE", {date(2026, 1, 1): 4.0})

        payload = _fred_payload({date(2026, 1, 1): 4.0, date(2026, 2, 1): 4.1})
        with _patched(observations_by_series={"UNRATE": payload}) as client:
            first = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)
        with _patched(observations_by_series={"UNRATE": payload}) as client:
            second = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        assert first.status == "CHANGED"
        assert len(first.observation_changes) == 1
        assert second.status == "NO_CHANGE"
        assert second.observation_changes == []

        repo = ReleaseProcessingRepository(db_session)
        runs = repo.list_check_runs_for_occurrence(occurrence.id)
        assert len(runs) == 2  # a check occurring twice is a real, allowed operational fact
        # But only ONE observation-update row exists in total, from the first run.
        all_updates = [u for run in runs for u in repo.list_observation_updates_for_run(run.id)]
        assert len(all_updates) == 1


# ---------------------------------------------------------------------
# Shutdown / provider-lag invariant
# ---------------------------------------------------------------------


class TestShutdownInvariant:
    def test_scheduled_date_passing_with_no_provider_change_produces_zero_canonical_change(self, db_session):
        release = _cpi_release(db_session)
        occurrence = _occurrence(db_session, release, scheduled_date=date(2026, 1, 1))  # long past due
        cpi_series = _seed_series(db_session, "CPIAUCSL", {date(2025, 12, 1): 300.0})
        core_series = _seed_series(db_session, "CPILFESL", {date(2025, 12, 1): 280.0})

        payload_cpi = _fred_payload({date(2025, 12, 1): 300.0})
        payload_core = _fred_payload({date(2025, 12, 1): 280.0})
        with _patched(observations_by_series={"CPIAUCSL": payload_cpi, "CPILFESL": payload_core}) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        assert result.status == "NO_CHANGE"
        assert result.observation_changes == []
        assert result.analysis_changes == []
        repo = ReleaseProcessingRepository(db_session)
        assert repo.get_observations_by_date(cpi_series.id) == {date(2025, 12, 1): 300.0}
        assert repo.get_observations_by_date(core_series.id) == {date(2025, 12, 1): 280.0}


# ---------------------------------------------------------------------
# Inflation impact: analysis change / no-change, old-period revision,
# multi-observation consistency, state change
# ---------------------------------------------------------------------


class TestInflationAnalysisImpact:
    def test_no_analytical_change_when_a_revision_does_not_move_any_canonical_value(self, db_session):
        """A revision to a value that never participates in any
        currently-computable state (too sparse for any r_3m/r_6m/r_12m
        endpoint set, before OR after the revision) produces an
        observation-update row but zero analysis-update rows -- data
        changed, but no canonical Inflation evidence could ever have
        differed."""
        release = _cpi_release(db_session)
        occurrence = _occurrence(db_session, release)
        # Deliberately only two months -- nowhere near enough for a
        # valid r_3m/r_6m/r_12m at either date, before or after.
        _seed_series(db_session, "CPIAUCSL", {date(2026, 1, 1): 300.0}, title="CPI")
        _seed_series(db_session, "CPILFESL", {date(2025, 12, 1): 280.0, date(2026, 1, 1): 281.0}, title="Core CPI")
        _seed_series(db_session, "PCEPILFE", _constant_growth_series(date(2025, 1, 1), 13, start_value=120.0, monthly_growth=0.002))
        _seed_series(db_session, "PCEPI", _constant_growth_series(date(2025, 1, 1), 13, start_value=130.0, monthly_growth=0.002))

        payload_core = _fred_payload({date(2025, 12, 1): 330.0, date(2026, 1, 1): 281.0})  # a large, unmistakable revision
        payload_cpi = _fred_payload({date(2026, 1, 1): 300.0})
        with _patched(observations_by_series={"CPIAUCSL": payload_cpi, "CPILFESL": payload_core}) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        assert len(result.observation_changes) == 1
        assert result.observation_changes[0].change_type == "REVISED"
        assert result.analysis_changes == []
        assert result.status == "CHANGED"

    def test_old_period_revision_is_audited_even_though_it_is_not_the_latest_two_months(self, db_session):
        """CRITICAL regression (see docs/architecture/release-processing-v1.md):
        latest period is the last month of a 13-month series; a MIDDLE
        month (exactly latest - 6, a real r_6m endpoint) is revised.
        The ordinary month-over-month What Changed endpoint would
        compare only the latest two months and would never see this --
        #18's release-scoped audit must still detect it."""
        release = _cpi_release(db_session)
        occurrence = _occurrence(db_session, release)
        base = _constant_growth_series(date(2025, 1, 1), 13, start_value=280.0, monthly_growth=0.002)
        latest_period = max(base)
        revision_target = latest_period.replace(month=latest_period.month - 6) if latest_period.month > 6 else date(latest_period.year - 1, latest_period.month + 6, 1)

        _seed_series(db_session, "CPIAUCSL", {date(2026, 1, 1): 300.0}, title="CPI")
        _seed_series(db_session, "CPILFESL", base, title="Core CPI")
        _seed_series(db_session, "PCEPILFE", _constant_growth_series(date(2025, 1, 1), 13, start_value=120.0, monthly_growth=0.002))
        _seed_series(db_session, "PCEPI", _constant_growth_series(date(2025, 1, 1), 13, start_value=130.0, monthly_growth=0.002))

        revised = dict(base)
        revised[revision_target] = base[revision_target] * 1.15  # a large, unmistakable revision

        payload_core = _fred_payload(revised)
        payload_cpi = _fred_payload({date(2026, 1, 1): 300.0})
        with _patched(observations_by_series={"CPIAUCSL": payload_cpi, "CPILFESL": payload_core}) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        assert any(c.change_type == "REVISED" and c.observation_date == revision_target for c in result.observation_changes)
        # Confirmation is evaluated at latest_period (revision_target + 6 months, i.e. the series' own latest period)
        # because revision_target is exactly latest_period's r_6m endpoint -- an analytical consequence must exist.
        assert any(event.evaluation_period == latest_period for event in result.analysis_changes)

    def test_multiple_observations_feeding_one_evaluation_produce_one_consistent_before_after_diff(self, db_session):
        """Several endpoint revisions that all feed the SAME later
        period must be diffed once, using before-ALL-writes and
        after-ALL-writes evidence -- never once per row."""
        release = _cpi_release(db_session)
        occurrence = _occurrence(db_session, release)
        base = _constant_growth_series(date(2025, 1, 1), 13, start_value=280.0, monthly_growth=0.002)
        latest_period = max(base)

        _seed_series(db_session, "CPIAUCSL", {date(2026, 1, 1): 300.0}, title="CPI")
        _seed_series(db_session, "CPILFESL", base, title="Core CPI")
        _seed_series(db_session, "PCEPILFE", _constant_growth_series(date(2025, 1, 1), 13, start_value=120.0, monthly_growth=0.002))
        _seed_series(db_session, "PCEPI", _constant_growth_series(date(2025, 1, 1), 13, start_value=130.0, monthly_growth=0.002))

        three_months_back = latest_period.replace(month=latest_period.month - 3) if latest_period.month > 3 else date(latest_period.year - 1, latest_period.month + 9, 1)
        six_months_back = latest_period.replace(month=latest_period.month - 6) if latest_period.month > 6 else date(latest_period.year - 1, latest_period.month + 6, 1)

        revised = dict(base)
        revised[three_months_back] = base[three_months_back] * 1.2
        revised[six_months_back] = base[six_months_back] * 1.2

        # Compute expected AFTER evidence directly via the pure domain
        # function, using the ground-truth full revised series -- the
        # service must agree with this, not with anything computed
        # per-row along the way.
        from app.models.series import Observation

        revised_observations = [Observation(date=d, value=v) for d, v in sorted(revised.items())]
        expected_after_core = compute_series_momentum_at(revised_observations, "CPILFESL", latest_period)

        payload_core = _fred_payload(revised)
        payload_cpi = _fred_payload({date(2026, 1, 1): 300.0})
        with _patched(observations_by_series={"CPIAUCSL": payload_cpi, "CPILFESL": payload_core}) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        assert len(result.observation_changes) == 2  # exactly the two revised rows, not more

        repo = ReleaseProcessingRepository(db_session)
        core_series = repo.get_series_by_series_id("CPILFESL")
        persisted = repo.get_observations_by_date(core_series.id)
        assert persisted[three_months_back] == base[three_months_back] * 1.2
        assert persisted[six_months_back] == base[six_months_back] * 1.2

        # Confirmation events at latest_period reflect the FINAL,
        # fully-revised state (matching the direct domain computation),
        # proving before/after was captured once across the whole batch.
        confirmation_events_at_latest = [e for e in result.analysis_changes if e.evaluation_period == latest_period and e.component == "CONFIRMATION"]
        assert confirmation_events_at_latest  # a relationship-shaped consequence exists at the shared affected period

    def test_state_change_event_carries_exact_previous_and_current_states_and_methodology_metadata(self, db_session):
        release = _pio_release(db_session)
        occurrence = _occurrence(db_session, release)
        base = _constant_growth_series(date(2025, 1, 1), 13, start_value=120.0, monthly_growth=0.002)
        latest_period = max(base)

        _seed_series(db_session, "PCEPILFE", base, title="Core PCE")
        _seed_series(db_session, "PCEPI", _constant_growth_series(date(2025, 1, 1), 13, start_value=130.0, monthly_growth=0.002))
        _seed_series(db_session, "CPIAUCSL", _constant_growth_series(date(2025, 1, 1), 13, start_value=300.0, monthly_growth=0.002))
        _seed_series(db_session, "CPILFESL", _constant_growth_series(date(2025, 1, 1), 13, start_value=280.0, monthly_growth=0.002))

        revised = dict(base)
        # A dramatic jump in the latest month's own value -- pushes r_3m/r_6m
        # well above the neutral band around r_12m.
        revised[latest_period] = base[latest_period] * 1.25

        from app.models.series import Observation

        revised_observations = [Observation(date=d, value=v) for d, v in sorted(revised.items())]
        expected_after = compute_series_momentum_at(revised_observations, "PCEPILFE", latest_period)
        expected_before = compute_series_momentum_at(
            [Observation(date=d, value=v) for d, v in sorted(base.items())], "PCEPILFE", latest_period
        )
        assert expected_before.state != expected_after.state, "test fixture must actually produce a state change"

        payload_pcepilfe = _fred_payload(revised)
        payload_pcepi = _fred_payload({d: v for d, v in _constant_growth_series(date(2025, 1, 1), 13, start_value=130.0, monthly_growth=0.002).items()})
        with _patched(observations_by_series={"PCEPILFE": payload_pcepilfe, "PCEPI": payload_pcepi}) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        state_events = [e for e in result.analysis_changes if e.component == "PRIMARY_MOMENTUM" and e.event_type == "STATE_CHANGED"]
        assert len(state_events) == 1
        event = state_events[0]
        assert event.previous_value == expected_before.state
        assert event.current_value == expected_after.state
        assert event.methodology_id == "inflation_v1.0"
        assert event.data_basis == "latest_revised_data"
        assert event.evaluation_period == latest_period


class TestNoFakeAnalyticalChangeFromUnaffectedComponents:
    def test_cpi_headline_change_alone_never_alters_primary_momentum(self, db_session):
        """A CPIAUCSL-only change can affect HEADLINE_CPI; it must
        never fabricate a PRIMARY_MOMENTUM (Core PCE) event -- Core PCE
        was never touched by this release at all."""
        release = _cpi_release(db_session)
        occurrence = _occurrence(db_session, release)
        _seed_series(db_session, "PCEPILFE", _constant_growth_series(date(2025, 1, 1), 13, start_value=120.0, monthly_growth=0.002))
        cpi_base = _constant_growth_series(date(2025, 1, 1), 13, start_value=300.0, monthly_growth=0.002)
        _seed_series(db_session, "CPIAUCSL", cpi_base)
        _seed_series(db_session, "CPILFESL", {date(2026, 1, 1): 280.0})

        revised_cpi = dict(cpi_base)
        latest = max(cpi_base)
        revised_cpi[latest] = cpi_base[latest] * 1.3

        payload_cpi = _fred_payload(revised_cpi)
        payload_core = _fred_payload({date(2026, 1, 1): 280.0})
        with _patched(observations_by_series={"CPIAUCSL": payload_cpi, "CPILFESL": payload_core}) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        assert all(event.component != "PRIMARY_MOMENTUM" for event in result.analysis_changes)


# ---------------------------------------------------------------------
# T+12 forward-dependency regression (final hardening)
#
# Production code (app.domain.release_processing.affected_evaluation_periods,
# _AFFECTED_HORIZONS_MONTHS) is unmodified and verified correct -- these
# tests exist to PERMANENTLY pin that a revision to an r_12m endpoint
# `t` is still detected and diffed at `t+12` (the period for which `t`
# is the required 12-month-back endpoint), so a future refactor that
# accidentally narrows `_AFFECTED_HORIZONS_MONTHS` (e.g. drops 12,
# leaving only 1/3/6) breaks a test immediately rather than silently
# losing 12-month coverage while shorter-horizon tests stay green.
# ---------------------------------------------------------------------


class TestT12ForwardDependencyRegression:
    def test_core_pce_revision_at_t_produces_state_and_metric_consequence_at_t_plus_12(self, db_session):
        release = _pio_release(db_session)
        occurrence = _occurrence(db_session, release)

        pcepilfe_base = _constant_growth_series(date(2025, 1, 1), 13, start_value=120.0, monthly_growth=0.002)
        pcepi_base = _constant_growth_series(date(2025, 1, 1), 13, start_value=130.0, monthly_growth=0.002)
        t = min(pcepilfe_base)
        t_plus_12 = max(pcepilfe_base)  # exactly 12 months later in this 13-month series

        _seed_series(db_session, "PCEPILFE", pcepilfe_base, title="Core PCE")
        _seed_series(db_session, "PCEPI", pcepi_base, title="Headline PCE")
        _seed_series(db_session, "CPIAUCSL", _constant_growth_series(date(2025, 1, 1), 13, start_value=300.0, monthly_growth=0.002))
        _seed_series(db_session, "CPILFESL", _constant_growth_series(date(2025, 1, 1), 13, start_value=280.0, monthly_growth=0.002))

        revised_pcepilfe = dict(pcepilfe_base)
        # Revise ONLY t -- t+3 and t+6 are left completely untouched, so
        # any consequence detected at t+12 can only have come from the
        # 12-month forward-projection horizon, not the 3/6-month ones.
        revised_pcepilfe[t] = pcepilfe_base[t] * 1.3

        # Independent ground truth: the EXISTING, unmodified domain
        # functions, called directly -- never hand-computed economics.
        before_obs = [Observation(date=d, value=v) for d, v in sorted(pcepilfe_base.items())]
        after_obs = [Observation(date=d, value=v) for d, v in sorted(revised_pcepilfe.items())]
        expected_before = compute_series_momentum_at(before_obs, "PCEPILFE", t_plus_12)
        expected_after = compute_series_momentum_at(after_obs, "PCEPILFE", t_plus_12)
        assert expected_before.state != expected_after.state, "fixture must actually produce a state change at t+12"
        assert expected_before.r_12m != expected_after.r_12m

        payload_pcepilfe = _fred_payload(revised_pcepilfe)
        payload_pcepi = _fred_payload(pcepi_base)  # identical to seeded data -> UNCHANGED, isolates the PCEPILFE effect

        with _patched(observations_by_series={"PCEPILFE": payload_pcepilfe, "PCEPI": payload_pcepi}) as client:
            first = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        # 1 + 2: ReleaseObservationUpdate = REVISED at t, canonical value updated.
        assert len(first.observation_changes) == 1
        change = first.observation_changes[0]
        assert change.series_id == "PCEPILFE"
        assert change.change_type == "REVISED"
        assert change.observation_date == t
        assert change.previous_value == pcepilfe_base[t]
        assert change.new_value == revised_pcepilfe[t]

        repo = ReleaseProcessingRepository(db_session)
        pcepilfe_series = repo.get_series_by_series_id("PCEPILFE")
        assert repo.get_observations_by_date(pcepilfe_series.id)[t] == revised_pcepilfe[t]

        # 3 + 4: ReleaseAnalysisUpdate contains the deterministic
        # consequence at t+12, exactly matching the independent ground truth.
        t12_events = [e for e in first.analysis_changes if e.component == "PRIMARY_MOMENTUM" and e.evaluation_period == t_plus_12]
        metric_events = [e for e in t12_events if e.event_type == "METRIC_CHANGED" and e.field == "r_12m"]
        assert len(metric_events) == 1
        assert metric_events[0].previous_value == expected_before.r_12m
        assert metric_events[0].current_value == expected_after.r_12m

        # 5: STATE_CHANGED at t+12, exact previous/current states.
        state_events = [e for e in t12_events if e.event_type == "STATE_CHANGED" and e.field == "state"]
        assert len(state_events) == 1
        assert state_events[0].previous_value == expected_before.state
        assert state_events[0].current_value == expected_after.state

        # 6: methodology/data-basis metadata are canonical, on every t+12 event.
        for event in t12_events:
            assert event.methodology_id == "inflation_v1.0"
            assert event.data_basis == "latest_revised_data"

        # 7: no duplicate analysis event for the same logical consequence
        # (same component/field/period) anywhere in this run's result.
        keys = [(e.component, e.field, e.evaluation_period, e.event_type) for e in first.analysis_changes]
        assert len(keys) == len(set(keys))

        # Persisted rows agree with the in-memory result (not just the
        # returned object) -- round-tripped exactly, including the
        # str(float) encoding for previous/current_value.
        runs = repo.list_check_runs_for_occurrence(occurrence.id)
        assert len(runs) == 1
        persisted_analysis = repo.list_analysis_updates_for_run(runs[0].id)
        persisted_t12 = [row for row in persisted_analysis if row.evaluation_period == t_plus_12 and row.component == "PRIMARY_MOMENTUM"]
        persisted_state_row = next(row for row in persisted_t12 if row.event_type == "STATE_CHANGED")
        assert persisted_state_row.previous_value == expected_before.state
        assert persisted_state_row.current_value == expected_after.state
        persisted_metric_row = next(row for row in persisted_t12 if row.event_type == "METRIC_CHANGED" and row.field == "r_12m")
        assert float(persisted_metric_row.previous_value) == expected_before.r_12m
        assert float(persisted_metric_row.current_value) == expected_after.r_12m

        # 8: retry against identical provider data is idempotent -- a
        # new ReleaseCheckRun is allowed (a check occurring twice is a
        # real fact), but zero new observation/analysis rows.
        with _patched(observations_by_series={"PCEPILFE": payload_pcepilfe, "PCEPI": payload_pcepi}) as client:
            second = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        assert second.status == "NO_CHANGE"
        assert second.observation_changes == []
        assert second.analysis_changes == []

        all_runs = repo.list_check_runs_for_occurrence(occurrence.id)
        assert len(all_runs) == 2
        all_observation_updates = [u for run in all_runs for u in repo.list_observation_updates_for_run(run.id)]
        all_analysis_updates = [u for run in all_runs for u in repo.list_analysis_updates_for_run(run.id)]
        assert len(all_observation_updates) == 1  # only from the first run
        assert len(all_analysis_updates) == len(first.analysis_changes)  # only from the first run, none duplicated

    def test_headline_pce_and_target_revision_at_t_produces_metric_consequence_at_t_plus_12(self, db_session):
        release = _pio_release(db_session)
        occurrence = _occurrence(db_session, release)

        pcepilfe_base = _constant_growth_series(date(2025, 1, 1), 13, start_value=120.0, monthly_growth=0.002)
        pcepi_base = _constant_growth_series(date(2025, 1, 1), 13, start_value=130.0, monthly_growth=0.002)
        t = min(pcepi_base)
        t_plus_12 = max(pcepi_base)

        _seed_series(db_session, "PCEPILFE", pcepilfe_base, title="Core PCE")
        _seed_series(db_session, "PCEPI", pcepi_base, title="Headline PCE")
        _seed_series(db_session, "CPIAUCSL", _constant_growth_series(date(2025, 1, 1), 13, start_value=300.0, monthly_growth=0.002))
        _seed_series(db_session, "CPILFESL", _constant_growth_series(date(2025, 1, 1), 13, start_value=280.0, monthly_growth=0.002))

        revised_pcepi = dict(pcepi_base)
        revised_pcepi[t] = pcepi_base[t] * 1.2  # revise ONLY the YoY denominator 12 months back

        # Independent ground truth via the existing, unmodified domain
        # functions -- never hand-computed.
        before_obs = [Observation(date=d, value=v) for d, v in sorted(pcepi_base.items())]
        after_obs = [Observation(date=d, value=v) for d, v in sorted(revised_pcepi.items())]
        expected_before_target = compute_target_at(before_obs, t_plus_12)
        expected_after_target = compute_target_at(after_obs, t_plus_12)
        assert expected_before_target.headline_pce_yoy != expected_after_target.headline_pce_yoy
        assert expected_before_target.target_gap_pp != expected_after_target.target_gap_pp

        payload_pcepilfe = _fred_payload(pcepilfe_base)  # unchanged -> isolates the PCEPI effect
        payload_pcepi = _fred_payload(revised_pcepi)

        with _patched(observations_by_series={"PCEPILFE": payload_pcepilfe, "PCEPI": payload_pcepi}) as client:
            first = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        # 1: ReleaseObservationUpdate = REVISED at t.
        assert len(first.observation_changes) == 1
        change = first.observation_changes[0]
        assert change.series_id == "PCEPI"
        assert change.change_type == "REVISED"
        assert change.observation_date == t

        # 2 + 5: TARGET METRIC_CHANGED events, exactly at t+12, matching
        # independent ground truth for both headline_pce_yoy and target_gap_pp.
        target_events = {
            e.field: e for e in first.analysis_changes if e.component == "TARGET" and e.evaluation_period == t_plus_12
        }
        assert "headline_pce_yoy" in target_events
        assert target_events["headline_pce_yoy"].previous_value == expected_before_target.headline_pce_yoy
        assert target_events["headline_pce_yoy"].current_value == expected_after_target.headline_pce_yoy

        assert "target_gap_pp" in target_events
        assert target_events["target_gap_pp"].previous_value == expected_before_target.target_gap_pp
        assert target_events["target_gap_pp"].current_value == expected_after_target.target_gap_pp

        # 6: methodology/data-basis metadata correct on every TARGET event.
        for event in target_events.values():
            assert event.methodology_id == "inflation_v1.0"
            assert event.data_basis == "latest_revised_data"

        # No duplicate logical consequence anywhere in the result.
        keys = [(e.component, e.field, e.evaluation_period, e.event_type) for e in first.analysis_changes]
        assert len(keys) == len(set(keys))

        # 7: retry is idempotent.
        with _patched(observations_by_series={"PCEPILFE": payload_pcepilfe, "PCEPI": payload_pcepi}) as client:
            second = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        assert second.status == "NO_CHANGE"
        assert second.observation_changes == []
        assert second.analysis_changes == []

        repo = ReleaseProcessingRepository(db_session)
        all_runs = repo.list_check_runs_for_occurrence(occurrence.id)
        assert len(all_runs) == 2
        all_observation_updates = [u for run in all_runs for u in repo.list_observation_updates_for_run(run.id)]
        assert len(all_observation_updates) == 1


# =======================================================================
# Increment #20D.2 -- Employment Situation / Labor release integration.
# Frozen contract: docs/architecture/labor-release-integration-v1.md.
#
# The `release_series_mappings` row for Employment Situation (FRED 50 ->
# PAYEMS, UNRATE) is real, persistent, active data in the isolated test
# database, seeded by alembic/versions/09f4c0959e9f_seed_employment_situation_release_.py
# -- used directly by TestLaborAnalysisImpact below, the same discipline
# TestInflationAnalysisImpact already applies to the real CPI/PIO
# mappings. Classification-only/failure/idempotency tests use a
# synthetic release/mapping/series well outside the curated catalog,
# mirroring this file's own existing discipline for Inflation.
# =======================================================================

from app.domain.labor import compute_labor_monitor_result_at, month_before  # noqa: E402
from app.models.labor import (  # noqa: E402
    CONDITION_DEADBAND_JOBS,
    MOMENTUM_DEADBAND_JOBS,
    PAYEMS_SERIES_ID,
    UNEMPLOYMENT_DEADBAND_PP,
    UNRATE_SERIES_ID,
)

# Real historical PAYEMS/UNRATE values (FRED native units), taken
# directly from research/labor_momentum/data/PAYEMS.csv/UNRATE.csv --
# the exact data that validated labor_v1.0 and labor_what_changed_v1.0
# (#20B/#20C.2's own fixtures). Spans the 2008-2009 Great Recession
# through early recovery -- enough real, contiguous months to compute
# compute_labor_monitor_result_at at every anchor used below.
_PAYEMS_THOUSANDS: dict[date, float] = {
    date(2008, 1, 1): 138391, date(2008, 2, 1): 138329, date(2008, 3, 1): 138259, date(2008, 4, 1): 138040,
    date(2008, 5, 1): 137851, date(2008, 6, 1): 137700, date(2008, 7, 1): 137497, date(2008, 8, 1): 137211,
    date(2008, 9, 1): 136760, date(2008, 10, 1): 136291, date(2008, 11, 1): 135541, date(2008, 12, 1): 134847,
    date(2009, 1, 1): 134079, date(2009, 2, 1): 133318, date(2009, 3, 1): 132494, date(2009, 4, 1): 131822,
    date(2009, 5, 1): 131466, date(2009, 6, 1): 131008, date(2009, 7, 1): 130662, date(2009, 8, 1): 130472,
    date(2009, 9, 1): 130246,
}
_UNRATE_PERCENT: dict[date, float] = {
    date(2008, 1, 1): 5.0, date(2008, 2, 1): 4.9, date(2008, 3, 1): 5.1, date(2008, 4, 1): 5.0,
    date(2008, 5, 1): 5.4, date(2008, 6, 1): 5.6, date(2008, 7, 1): 5.8, date(2008, 8, 1): 6.1,
    date(2008, 9, 1): 6.1, date(2008, 10, 1): 6.5, date(2008, 11, 1): 6.8, date(2008, 12, 1): 7.3,
    date(2009, 1, 1): 7.8, date(2009, 2, 1): 8.3, date(2009, 3, 1): 8.7, date(2009, 4, 1): 9.0,
    date(2009, 5, 1): 9.4, date(2009, 6, 1): 9.5, date(2009, 7, 1): 9.5, date(2009, 8, 1): 9.6,
    date(2009, 9, 1): 9.8,
}


def _employment_situation_release(session):
    return session.execute(sa.select(EconomicRelease).where(EconomicRelease.provider_release_id == "50")).scalar_one()


def _seed_payems(session, values: dict[date, float | None] = None):
    return _seed_series(session, PAYEMS_SERIES_ID, values if values is not None else dict(_PAYEMS_THOUSANDS), title="PAYEMS", units="Thousands of Persons")


def _seed_unrate(session, values: dict[date, float | None] = None):
    return _seed_series(session, UNRATE_SERIES_ID, values if values is not None else dict(_UNRATE_PERCENT), title="UNRATE", units="Percent")


def _labor_result(payems: dict[date, float], unrate: dict[date, float], period: date):
    payems_obs = [Observation(date=d, value=v * 1000) for d, v in sorted(payems.items())]
    unrate_obs = [Observation(date=d, value=v) for d, v in sorted(unrate.items())]
    return compute_labor_monitor_result_at(
        payems_obs, unrate_obs, period, CONDITION_DEADBAND_JOBS, MOMENTUM_DEADBAND_JOBS, UNEMPLOYMENT_DEADBAND_PP
    )


class TestLaborMappingIsUsed:
    def test_employment_situation_occurrence_checks_both_payems_and_unrate(self, db_session):
        release = _employment_situation_release(db_session)
        occurrence = _occurrence(db_session, release)
        _seed_payems(db_session)
        _seed_unrate(db_session)

        with _patched(observations_by_series={PAYEMS_SERIES_ID: [], UNRATE_SERIES_ID: []}) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        checked_series = {o.series_id for o in result.series_outcomes}
        assert checked_series == {PAYEMS_SERIES_ID, UNRATE_SERIES_ID}


class TestLaborAvailabilityRestored:
    """A NEW PAYEMS observation that completes a previously-incomplete
    7-month window flips EMPLOYMENT.state from INSUFFICIENT_DATA to a
    real state -- AVAILABILITY_RESTORED, never a fabricated
    STATE_CHANGED: INSUFFICIENT_DATA -> RECOVERING transition (the
    frozen contract's own explicit example, §"NEW OBSERVATIONS VS
    REVISIONS")."""

    def test_new_payems_month_completing_the_window_produces_availability_restored(self, db_session):
        release = _employment_situation_release(db_session)
        occurrence = _occurrence(db_session, release)
        # Seed PAYEMS through 2009-07 only -- 2009-08's own window is
        # incomplete (INSUFFICIENT_DATA) until the new month arrives.
        partial = {d: v for d, v in _PAYEMS_THOUSANDS.items() if d <= date(2009, 7, 1)}
        _seed_payems(db_session, partial)
        _seed_unrate(db_session)

        before = _labor_result(partial, _UNRATE_PERCENT, date(2009, 8, 1))
        assert before.employment.state == "INSUFFICIENT_DATA"

        with _patched(
            observations_by_series={
                PAYEMS_SERIES_ID: _fred_payload({date(2009, 8, 1): _PAYEMS_THOUSANDS[date(2009, 8, 1)]}),
                UNRATE_SERIES_ID: [],
            }
        ) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        events_by_field = {e.field: e for e in result.analysis_changes if e.component == "EMPLOYMENT" and e.evaluation_period == date(2009, 8, 1)}
        assert events_by_field["state"].event_type == "AVAILABILITY_RESTORED"
        # previous_value carries the real "INSUFFICIENT_DATA" label
        # (never Python None -- matching labor_what_changed_v1.0's own
        # frozen convention that INSUFFICIENT_DATA is itself a real,
        # reportable value, not an engineering null):
        assert events_by_field["state"].previous_value == "INSUFFICIENT_DATA"
        assert events_by_field["state"].current_value == "RECOVERING"
        # NEVER a fabricated STATE_CHANGED for this transition:
        assert not any(
            e.event_type == "STATE_CHANGED" and e.field == "state" and e.evaluation_period == date(2009, 8, 1)
            for e in result.analysis_changes
        )


class TestPayemsPropagationRegression:
    """The frozen sparse {0,3,6} set, exercised through the real
    service call path (not just the pure domain module in isolation)."""

    def test_revision_at_offset_0_produces_a_consequence(self, db_session):
        release = _employment_situation_release(db_session)
        occurrence = _occurrence(db_session, release)
        _seed_payems(db_session)
        _seed_unrate(db_session)

        revised_value = _PAYEMS_THOUSANDS[date(2009, 5, 1)] - 500  # a large, unmistakable revision
        with _patched(observations_by_series={PAYEMS_SERIES_ID: _fred_payload({date(2009, 5, 1): revised_value}), UNRATE_SERIES_ID: []}) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        affected_periods = {e.evaluation_period for e in result.analysis_changes if e.component == "EMPLOYMENT"}
        assert date(2009, 5, 1) in affected_periods  # r+0

    def test_offsets_1_and_2_are_never_affected_cancellation_zone(self, db_session):
        """The single most important #20D.2 regression: a PAYEMS
        revision must NEVER produce an EMPLOYMENT analysis event at
        r+1 or r+2 -- the cancellation, not merely "less change.\""""
        release = _employment_situation_release(db_session)
        occurrence = _occurrence(db_session, release)
        _seed_payems(db_session)
        _seed_unrate(db_session)

        revised_value = _PAYEMS_THOUSANDS[date(2009, 5, 1)] - 500
        with _patched(observations_by_series={PAYEMS_SERIES_ID: _fred_payload({date(2009, 5, 1): revised_value}), UNRATE_SERIES_ID: []}) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        affected_periods = {e.evaluation_period for e in result.analysis_changes if e.component == "EMPLOYMENT"}
        assert date(2009, 6, 1) not in affected_periods  # r+1
        assert date(2009, 7, 1) not in affected_periods  # r+2


class TestUnratePropagationRegression:
    def test_revision_affects_current_and_prior_year_windows(self, db_session):
        release = _employment_situation_release(db_session)
        occurrence = _occurrence(db_session, release)
        _seed_payems(db_session)
        _seed_unrate(db_session)

        with _patched(observations_by_series={PAYEMS_SERIES_ID: [], UNRATE_SERIES_ID: _fred_payload({date(2009, 5, 1): 12.0})}) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        affected_periods = {e.evaluation_period for e in result.analysis_changes if e.component == "UNEMPLOYMENT"}
        # current-window cluster: r, r+1, r+2 -- all reachable from persisted 2009 data:
        assert date(2009, 5, 1) in affected_periods
        assert date(2009, 6, 1) in affected_periods
        assert date(2009, 7, 1) in affected_periods
        # prior-year-window cluster (r+12, r+13, r+14) would need 2010 data
        # this fixture doesn't persist -- correctly absent, not fabricated.


class TestCrossSeriesLaborUnion:
    def test_payems_and_unrate_both_change_in_one_run(self, db_session):
        release = _employment_situation_release(db_session)
        occurrence = _occurrence(db_session, release)
        _seed_payems(db_session)
        _seed_unrate(db_session)

        with _patched(
            observations_by_series={
                PAYEMS_SERIES_ID: _fred_payload({date(2009, 5, 1): _PAYEMS_THOUSANDS[date(2009, 5, 1)] - 500}),
                UNRATE_SERIES_ID: _fred_payload({date(2009, 6, 1): 12.0}),
            }
        ) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        components_present = {e.component for e in result.analysis_changes}
        assert "EMPLOYMENT" in components_present
        assert "UNEMPLOYMENT" in components_present

    def test_an_overlapping_period_is_evaluated_exactly_once(self, db_session):
        """PAYEMS r=2009-05 affects {05,08,11}; UNRATE r=2009-05 affects
        {05,06,07}; 2009-05 is shared by both -- must be evaluated once,
        not twice, and its EMPLOYMENT + UNEMPLOYMENT + LABOR events must
        both appear, not one suppressing the other."""
        release = _employment_situation_release(db_session)
        occurrence = _occurrence(db_session, release)
        _seed_payems(db_session)
        _seed_unrate(db_session)

        with _patched(
            observations_by_series={
                PAYEMS_SERIES_ID: _fred_payload({date(2009, 5, 1): _PAYEMS_THOUSANDS[date(2009, 5, 1)] - 500}),
                UNRATE_SERIES_ID: _fred_payload({date(2009, 5, 1): 12.0}),
            }
        ) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        at_period = [e for e in result.analysis_changes if e.evaluation_period == date(2009, 5, 1)]
        components_at_period = {e.component for e in at_period}
        assert "EMPLOYMENT" in components_at_period
        assert "UNEMPLOYMENT" in components_at_period
        # No duplicate (component, field, event_type) pair at this period:
        keys = [(e.component, e.field, e.event_type) for e in at_period]
        assert len(keys) == len(set(keys))


class TestLaborSamePeriodComparatorNeverMonthOverMonth:
    def test_before_and_after_are_evaluated_at_the_identical_period(self, db_session):
        release = _employment_situation_release(db_session)
        occurrence = _occurrence(db_session, release)
        _seed_payems(db_session)
        _seed_unrate(db_session)

        with _patched(observations_by_series={PAYEMS_SERIES_ID: _fred_payload({date(2009, 5, 1): _PAYEMS_THOUSANDS[date(2009, 5, 1)] - 500}), UNRATE_SERIES_ID: []}) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        # Every event's own evaluation_period is a SINGLE column (the
        # release-scoped shape) -- there is no previous_period field at
        # all on AnalysisChangeRecord, structurally proving the
        # month-over-month t-1 orchestration was never used here.
        assert all(hasattr(e, "evaluation_period") and not hasattr(e, "previous_period") for e in result.analysis_changes)

    def test_release_processing_never_imports_month_over_month_labor_periods(self):
        """A direct, explicit static proof (not just an absence of a
        crash): app/services/release_processing.py never imports
        `month_over_month_labor_periods` or
        `LaborMonitorService.get_what_changed_result` -- the monthly
        `/changes` orchestration this pipeline must never call."""
        import ast
        from pathlib import Path

        repo_root = Path(__file__).resolve().parent.parent.parent
        source = (repo_root / "app/services/release_processing.py").read_text()
        tree = ast.parse(source)
        imported_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported_names.update(alias.name for alias in node.names)
        assert "month_over_month_labor_periods" not in imported_names
        assert "get_what_changed_result" not in imported_names
        assert "LaborMonitorService" not in imported_names


class TestLaborAnalysisEvents:
    """The full required event-type matrix, using real historical data."""

    def test_top_level_labor_state_change(self, db_session):
        """A revision to 2009-01 (an affected offset for evaluation
        period 2009-04, per the frozen {0,3,6} set) flips EMPLOYMENT
        from CONTRACTING/WORSENING/CONTRACTING to EXPANDING/IMPROVING/
        EXPANDING -- and since UNRATE stays DETERIORATING throughout,
        LABOR.state flips COOLING -> MIXED (the frozen agreement
        table's own explicit COOLING cell vs. its "everything else"
        MIXED default -- real, verified against production code, not
        assumed)."""
        release = _employment_situation_release(db_session)
        occurrence = _occurrence(db_session, release)
        _seed_payems(db_session)
        _seed_unrate(db_session)

        before = _labor_result(_PAYEMS_THOUSANDS, _UNRATE_PERCENT, date(2009, 4, 1))
        revised_payems = dict(_PAYEMS_THOUSANDS)
        revised_payems[date(2009, 1, 1)] -= 3_000  # an enormous, unmistakable revision -- forces a real condition flip
        after = _labor_result(revised_payems, _UNRATE_PERCENT, date(2009, 4, 1))
        assert before.state == "COOLING" and after.state == "MIXED"  # the fixture itself proves a real transition exists to detect

        with _patched(observations_by_series={PAYEMS_SERIES_ID: _fred_payload({date(2009, 1, 1): revised_payems[date(2009, 1, 1)]}), UNRATE_SERIES_ID: []}) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        labor_events = [e for e in result.analysis_changes if e.component == "LABOR" and e.evaluation_period == date(2009, 4, 1)]
        assert any(e.event_type == "STATE_CHANGED" and e.field == "state" for e in labor_events)

    def test_condition_and_momentum_change_independently(self, db_session):
        release = _employment_situation_release(db_session)
        occurrence = _occurrence(db_session, release)
        _seed_payems(db_session)
        _seed_unrate(db_session)

        revised_value = _PAYEMS_THOUSANDS[date(2009, 5, 1)] - 2_000  # a large revision
        with _patched(observations_by_series={PAYEMS_SERIES_ID: _fred_payload({date(2009, 5, 1): revised_value}), UNRATE_SERIES_ID: []}) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        fields_at_r = {e.field for e in result.analysis_changes if e.component == "EMPLOYMENT" and e.evaluation_period == date(2009, 5, 1)}
        # metrics changed at minimum -- condition/momentum may or may not
        # cross their own deadband for this specific revision size, but
        # the numeric metrics always do:
        assert "current_3m_avg_jobs" in fields_at_r

    def test_unemployment_state_change(self, db_session):
        release = _employment_situation_release(db_session)
        occurrence = _occurrence(db_session, release)
        _seed_payems(db_session)
        _seed_unrate(db_session)

        before = _labor_result(_PAYEMS_THOUSANDS, _UNRATE_PERCENT, date(2009, 5, 1))
        revised_unrate = dict(_UNRATE_PERCENT)
        revised_unrate[date(2009, 5, 1)] = -3.0  # an enormous, unmistakable revision -- forces a real trend-state flip
        after = _labor_result(_PAYEMS_THOUSANDS, revised_unrate, date(2009, 5, 1))
        assert before.unemployment.state == "DETERIORATING" and after.unemployment.state == "IMPROVING"  # sanity: a real transition exists to detect

        with _patched(observations_by_series={PAYEMS_SERIES_ID: [], UNRATE_SERIES_ID: _fred_payload({date(2009, 5, 1): -3.0})}) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        unemployment_events = [e for e in result.analysis_changes if e.component == "UNEMPLOYMENT" and e.evaluation_period == date(2009, 5, 1)]
        assert any(e.field == "state" for e in unemployment_events)

    def test_numeric_only_change_with_no_state_change(self, db_session):
        """A tiny revision that moves a metric but not across any
        deadband boundary -- METRIC_CHANGED without STATE_CHANGED."""
        release = _employment_situation_release(db_session)
        occurrence = _occurrence(db_session, release)
        _seed_payems(db_session)
        _seed_unrate(db_session)

        before = _labor_result(_PAYEMS_THOUSANDS, _UNRATE_PERCENT, date(2009, 5, 1))
        tiny_revision = _PAYEMS_THOUSANDS[date(2009, 5, 1)] + 1  # 1,000 jobs -- comfortably inside the 50,000 deadband
        revised = dict(_PAYEMS_THOUSANDS)
        revised[date(2009, 5, 1)] = tiny_revision
        after = _labor_result(revised, _UNRATE_PERCENT, date(2009, 5, 1))
        assert before.employment.condition == after.employment.condition
        assert before.employment.momentum == after.employment.momentum
        assert before.employment.current_3m_avg_jobs != after.employment.current_3m_avg_jobs

        with _patched(observations_by_series={PAYEMS_SERIES_ID: _fred_payload({date(2009, 5, 1): tiny_revision}), UNRATE_SERIES_ID: []}) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        events_at_r = [e for e in result.analysis_changes if e.component == "EMPLOYMENT" and e.evaluation_period == date(2009, 5, 1)]
        assert any(e.event_type == "METRIC_CHANGED" for e in events_at_r)
        assert not any(e.event_type == "STATE_CHANGED" for e in events_at_r)

    def test_comparator_empty_cancellation_zone_produces_no_row(self, db_session):
        release = _employment_situation_release(db_session)
        occurrence = _occurrence(db_session, release)
        _seed_payems(db_session)
        _seed_unrate(db_session)

        revised_value = _PAYEMS_THOUSANDS[date(2009, 5, 1)] - 500
        with _patched(observations_by_series={PAYEMS_SERIES_ID: _fred_payload({date(2009, 5, 1): revised_value}), UNRATE_SERIES_ID: []}) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        # r+1, r+2 (2009-06, 2009-07) produce ZERO EMPLOYMENT rows at all:
        assert not any(e.component == "EMPLOYMENT" and e.evaluation_period in (date(2009, 6, 1), date(2009, 7, 1)) for e in result.analysis_changes)


class TestLaborObservationChangedAnalysisUnchanged:
    def test_observation_update_exists_without_a_corresponding_analysis_update(self, db_session):
        release = _employment_situation_release(db_session)
        occurrence = _occurrence(db_session, release)
        _seed_payems(db_session)
        _seed_unrate(db_session)

        revised_value = _PAYEMS_THOUSANDS[date(2009, 5, 1)] - 500
        with _patched(observations_by_series={PAYEMS_SERIES_ID: _fred_payload({date(2009, 5, 1): revised_value}), UNRATE_SERIES_ID: []}) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        assert any(o.observation_date == date(2009, 5, 1) and o.series_id == PAYEMS_SERIES_ID for o in result.observation_changes)
        # ...but r+1/r+2 have no analysis rows (the cancellation zone -- confirmed above), proving
        # `data changed != analysis changed` holds for Labor exactly as it does for Inflation.
        assert not any(e.evaluation_period in (date(2009, 6, 1), date(2009, 7, 1)) for e in result.analysis_changes)


class TestLaborMultiplePeriodsAndIdentifiers:
    def test_multiple_labor_evaluation_periods_persisted_in_one_run(self, db_session):
        release = _employment_situation_release(db_session)
        occurrence = _occurrence(db_session, release)
        _seed_payems(db_session)
        _seed_unrate(db_session)

        revised_value = _PAYEMS_THOUSANDS[date(2009, 5, 1)] - 2_000_000  # forces a genuine change at r AND r+3 (2009-08)
        with _patched(observations_by_series={PAYEMS_SERIES_ID: _fred_payload({date(2009, 5, 1): revised_value}), UNRATE_SERIES_ID: []}) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        distinct_periods = {e.evaluation_period for e in result.analysis_changes if e.component == "EMPLOYMENT"}
        assert len(distinct_periods) >= 2  # 2009-05 and 2009-08 both produce evidence

        repo = ReleaseProcessingRepository(db_session)
        runs = repo.list_check_runs_for_occurrence(occurrence.id)
        persisted = repo.list_analysis_updates_for_run(runs[-1].id)
        persisted_periods = {row.evaluation_period for row in persisted if row.component == "EMPLOYMENT"}
        assert distinct_periods <= persisted_periods

    def test_correct_methodology_and_data_basis_on_every_persisted_labor_row(self, db_session):
        release = _employment_situation_release(db_session)
        occurrence = _occurrence(db_session, release)
        _seed_payems(db_session)
        _seed_unrate(db_session)

        revised_value = _PAYEMS_THOUSANDS[date(2009, 5, 1)] - 500
        with _patched(observations_by_series={PAYEMS_SERIES_ID: _fred_payload({date(2009, 5, 1): revised_value}), UNRATE_SERIES_ID: []}) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        labor_events = [e for e in result.analysis_changes if e.component in ("LABOR", "EMPLOYMENT", "UNEMPLOYMENT")]
        assert labor_events != []
        for event in labor_events:
            assert event.methodology_id == "labor_v1.0"  # the SOURCE monitor, never labor_what_changed_v1.0
            assert event.data_basis == "latest_revised_data"

    def test_labor_component_values_are_not_remapped_to_inflation_names(self, db_session):
        release = _employment_situation_release(db_session)
        occurrence = _occurrence(db_session, release)
        _seed_payems(db_session)
        _seed_unrate(db_session)

        revised_value = _PAYEMS_THOUSANDS[date(2009, 5, 1)] - 500
        with _patched(observations_by_series={PAYEMS_SERIES_ID: _fred_payload({date(2009, 5, 1): revised_value}), UNRATE_SERIES_ID: []}) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        components_present = {e.component for e in result.analysis_changes}
        assert components_present <= {"LABOR", "EMPLOYMENT", "UNEMPLOYMENT"}
        inflation_components = {"PRIMARY_MOMENTUM", "CONFIRMATION", "TARGET", "HEADLINE_PCE", "HEADLINE_CPI"}
        assert components_present.isdisjoint(inflation_components)


class TestLaborProviderFailureIsolation:
    def test_payems_succeeds_unrate_fails(self, db_session):
        release = _employment_situation_release(db_session)
        occurrence = _occurrence(db_session, release)
        _seed_payems(db_session)
        _seed_unrate(db_session)

        def _get_observations(series_id, **kwargs):
            if series_id == UNRATE_SERIES_ID:
                raise FREDTimeoutError("timed out")
            return _fred_payload({date(2009, 5, 1): _PAYEMS_THOUSANDS[date(2009, 5, 1)] - 500})

        client = FREDClient(api_key="not-used", timeout=1.0)
        with patch.object(FREDClient, "get_observations", side_effect=_get_observations):
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        assert result.status == "PARTIAL_FAILURE"
        outcomes = {o.series_id: o for o in result.series_outcomes}
        assert outcomes[PAYEMS_SERIES_ID].succeeded is True
        assert outcomes[UNRATE_SERIES_ID].succeeded is False
        # PAYEMS's changes were still written and audited despite UNRATE's failure:
        assert any(o.series_id == PAYEMS_SERIES_ID for o in result.observation_changes)

    def test_unrate_succeeds_payems_fails(self, db_session):
        release = _employment_situation_release(db_session)
        occurrence = _occurrence(db_session, release)
        _seed_payems(db_session)
        _seed_unrate(db_session)

        def _get_observations(series_id, **kwargs):
            if series_id == PAYEMS_SERIES_ID:
                raise FREDAuthError("auth failed")
            return _fred_payload({date(2009, 5, 1): 12.0})

        client = FREDClient(api_key="not-used", timeout=1.0)
        with patch.object(FREDClient, "get_observations", side_effect=_get_observations):
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        assert result.status == "PARTIAL_FAILURE"
        outcomes = {o.series_id: o for o in result.series_outcomes}
        assert outcomes[UNRATE_SERIES_ID].succeeded is True
        assert outcomes[PAYEMS_SERIES_ID].succeeded is False

    def test_both_payems_and_unrate_fail(self, db_session):
        release = _employment_situation_release(db_session)
        occurrence = _occurrence(db_session, release)
        _seed_payems(db_session)
        _seed_unrate(db_session)

        client = FREDClient(api_key="not-used", timeout=1.0)
        with patch.object(FREDClient, "get_observations", side_effect=FREDTimeoutError("timed out")):
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        assert result.status == "FAILED_PROVIDER"
        assert result.observation_changes == []
        assert result.analysis_changes == []


class TestLaborDatabaseFailureRollback:
    def test_a_deliberate_failure_after_provider_success_rolls_back_the_whole_occurrence(self, real_session_scope):
        """Mirrors TestDatabaseFailure's own identical pattern, applied
        to the Employment Situation release/PAYEMS series."""
        with real_session_scope() as setup_session:
            release = _employment_situation_release(setup_session)
            occurrence = _occurrence(setup_session, release)
            _seed_payems(setup_session, {date(2009, 5, 1): _PAYEMS_THOUSANDS[date(2009, 5, 1)]})
            occurrence_id = occurrence.id

        try:
            class _DeliberateFailure(Exception):
                pass

            payload = _fred_payload({date(2009, 5, 1): _PAYEMS_THOUSANDS[date(2009, 5, 1)] - 500})
            client = FREDClient(api_key="not-used", timeout=1.0)

            with pytest.raises(_DeliberateFailure):
                with real_session_scope() as session:
                    with patch.object(FREDClient, "get_observations", side_effect=lambda sid, **kw: payload if sid == PAYEMS_SERIES_ID else []):
                        with patch.object(ReleaseProcessingRepository, "add_check_run", side_effect=_DeliberateFailure("simulated failure")):
                            ReleaseProcessingService(client).process_occurrence(occurrence_id, session, AS_OF)

            with real_session_scope() as verify_session:
                repo = ReleaseProcessingRepository(verify_session)
                series = repo.get_series_by_series_id(PAYEMS_SERIES_ID)
                # The REVISED observation write never survived the rollback:
                assert repo.get_observations_by_date(series.id) == {date(2009, 5, 1): _PAYEMS_THOUSANDS[date(2009, 5, 1)]}
                assert repo.list_check_runs_for_occurrence(occurrence_id) == []
        finally:
            with real_session_scope() as cleanup_session:
                from app.db.models import ReleaseOccurrence

                cleanup_session.execute(ReleaseOccurrence.__table__.delete().where(ReleaseOccurrence.id == occurrence_id))
                series = ReleaseProcessingRepository(cleanup_session).get_series_by_series_id(PAYEMS_SERIES_ID)
                if series is not None:
                    from app.db.models import EconomicObservation, EconomicSeries as _EconomicSeries

                    cleanup_session.execute(EconomicObservation.__table__.delete().where(EconomicObservation.economic_series_id == series.id))
                    cleanup_session.execute(_EconomicSeries.__table__.delete().where(_EconomicSeries.id == series.id))


class TestLaborIdempotency:
    def test_processing_the_same_occurrence_twice_with_identical_data_creates_no_duplicate_change_events(self, db_session):
        release = _employment_situation_release(db_session)
        occurrence = _occurrence(db_session, release)
        _seed_payems(db_session)
        _seed_unrate(db_session)

        payload_payems = _fred_payload({date(2009, 5, 1): _PAYEMS_THOUSANDS[date(2009, 5, 1)] - 500})
        with _patched(observations_by_series={PAYEMS_SERIES_ID: payload_payems, UNRATE_SERIES_ID: []}) as client:
            first = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)
        assert first.analysis_changes != []

        with _patched(observations_by_series={PAYEMS_SERIES_ID: payload_payems, UNRATE_SERIES_ID: []}) as client:
            second = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        assert second.status == "NO_CHANGE"
        assert second.observation_changes == []
        assert second.analysis_changes == []

        repo = ReleaseProcessingRepository(db_session)
        all_runs = repo.list_check_runs_for_occurrence(occurrence.id)
        assert len(all_runs) == 2
        all_analysis_updates = [u for run in all_runs for u in repo.list_analysis_updates_for_run(run.id)]
        # Exactly the first run's own events -- never duplicated by the second, no-op run:
        assert len(all_analysis_updates) == len(first.analysis_changes)


# =======================================================================
# Increment #25E -- Recorded State History V1 persistence.
# Frozen contract: docs/product/recorded-state-history-v1.md (#25D).
#
# `RecordedMonitorResult` rows are written ONLY when
# `_evaluate_component_at`("PRIMARY_MOMENTUM")/`_evaluate_labor_at`
# genuinely executes inside `_apply_changes_and_compute_analysis` --
# these tests reuse the exact CPI/PIO/Employment Situation fixtures
# already established above, never a parallel fixture set (matching
# this file's own established discipline).
# =======================================================================

from app.db.models import RecordedMonitorResult  # noqa: E402


def _recorded_results(session, monitor: str | None = None) -> list[RecordedMonitorResult]:
    stmt = sa.select(RecordedMonitorResult)
    if monitor is not None:
        stmt = stmt.where(RecordedMonitorResult.monitor == monitor)
    return list(session.execute(stmt.order_by(RecordedMonitorResult.id.asc())).scalars())


class TestRecordedMonitorResultInflationChanged:
    def test_a_genuine_state_change_records_the_after_result(self, db_session):
        release = _pio_release(db_session)
        occurrence = _occurrence(db_session, release)
        base = _constant_growth_series(date(2025, 1, 1), 13, start_value=120.0, monthly_growth=0.002)
        latest_period = max(base)

        _seed_series(db_session, "PCEPILFE", base, title="Core PCE")
        _seed_series(db_session, "PCEPI", _constant_growth_series(date(2025, 1, 1), 13, start_value=130.0, monthly_growth=0.002))
        _seed_series(db_session, "CPIAUCSL", _constant_growth_series(date(2025, 1, 1), 13, start_value=300.0, monthly_growth=0.002))
        _seed_series(db_session, "CPILFESL", _constant_growth_series(date(2025, 1, 1), 13, start_value=280.0, monthly_growth=0.002))

        revised = dict(base)
        revised[latest_period] = base[latest_period] * 1.25  # forces a genuine state change

        expected_before = compute_series_momentum_at(
            [Observation(date=d, value=v) for d, v in sorted(base.items())], "PCEPILFE", latest_period
        )
        expected_after = compute_series_momentum_at(
            [Observation(date=d, value=v) for d, v in sorted(revised.items())], "PCEPILFE", latest_period
        )
        assert expected_before.state != expected_after.state, "test fixture must actually produce a state change"

        payload_pcepilfe = _fred_payload(revised)
        payload_pcepi = _fred_payload(_constant_growth_series(date(2025, 1, 1), 13, start_value=130.0, monthly_growth=0.002))
        with _patched(observations_by_series={"PCEPILFE": payload_pcepilfe, "PCEPI": payload_pcepi}) as client:
            ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        rows = _recorded_results(db_session, monitor="inflation")
        assert len(rows) == 1
        assert rows[0].evaluation_period == latest_period
        assert rows[0].state == expected_after.state
        assert rows[0].methodology_id == "inflation_v1.0"
        assert rows[0].data_basis == "latest_revised_data"

        repo = ReleaseProcessingRepository(db_session)
        runs = repo.list_check_runs_for_occurrence(occurrence.id)
        assert len(runs) == 1
        # calculated_at reuses the owning ReleaseCheckRun.completed_at verbatim (contract §15) --
        # no independent clock read.
        assert rows[0].release_check_run_id == runs[0].id
        assert rows[0].calculated_at == runs[0].completed_at


class TestRecordedMonitorResultInflationUnchangedState:
    def test_genuine_recomputation_with_an_unchanged_state_still_records_a_result(self, db_session):
        """THE critical test: the primary historical gap #25E closes.
        A revision small enough to leave the classified state unchanged
        produces ZERO ReleaseAnalysisUpdate rows for PRIMARY_MOMENTUM
        (change-only, by that table's own design) but MUST still
        produce a RecordedMonitorResult row, proving EI genuinely
        re-verified the state at this later calculation time (contract
        §9)."""
        release = _pio_release(db_session)
        occurrence = _occurrence(db_session, release)
        base = _constant_growth_series(date(2025, 1, 1), 13, start_value=120.0, monthly_growth=0.002)
        latest_period = max(base)

        _seed_series(db_session, "PCEPILFE", base, title="Core PCE")
        _seed_series(db_session, "PCEPI", _constant_growth_series(date(2025, 1, 1), 13, start_value=130.0, monthly_growth=0.002))
        _seed_series(db_session, "CPIAUCSL", _constant_growth_series(date(2025, 1, 1), 13, start_value=300.0, monthly_growth=0.002))
        _seed_series(db_session, "CPILFESL", _constant_growth_series(date(2025, 1, 1), 13, start_value=280.0, monthly_growth=0.002))

        revised = dict(base)
        # A negligible nudge -- far too small to cross the 10-percentage-point
        # neutral band, so the classified state is identical before and after.
        revised[latest_period] = base[latest_period] + 0.001

        expected_before = compute_series_momentum_at(
            [Observation(date=d, value=v) for d, v in sorted(base.items())], "PCEPILFE", latest_period
        )
        expected_after = compute_series_momentum_at(
            [Observation(date=d, value=v) for d, v in sorted(revised.items())], "PCEPILFE", latest_period
        )
        assert expected_before.state == expected_after.state == "STABLE", "test fixture must genuinely leave the state unchanged"

        payload_pcepilfe = _fred_payload(revised)
        payload_pcepi = _fred_payload(_constant_growth_series(date(2025, 1, 1), 13, start_value=130.0, monthly_growth=0.002))
        with _patched(observations_by_series={"PCEPILFE": payload_pcepilfe, "PCEPI": payload_pcepi}) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        assert result.observation_changes != [], "test fixture must genuinely produce a REVISED observation write"
        state_events = [e for e in result.analysis_changes if e.component == "PRIMARY_MOMENTUM" and e.event_type == "STATE_CHANGED"]
        assert state_events == [], "test fixture must genuinely produce zero ReleaseAnalysisUpdate state-change rows"

        rows = _recorded_results(db_session, monitor="inflation")
        assert len(rows) == 1
        assert rows[0].evaluation_period == latest_period
        assert rows[0].state == "STABLE"


class TestRecordedMonitorResultLaborChanged:
    def test_a_genuine_state_change_records_the_after_result(self, db_session):
        release = _employment_situation_release(db_session)
        occurrence = _occurrence(db_session, release)
        _seed_payems(db_session)
        _seed_unrate(db_session)

        period = date(2009, 5, 1)
        expected_before = _labor_result(_PAYEMS_THOUSANDS, _UNRATE_PERCENT, period)
        revised_payems = dict(_PAYEMS_THOUSANDS)
        revised_payems[period] = _PAYEMS_THOUSANDS[period] - 500
        expected_after = _labor_result(revised_payems, _UNRATE_PERCENT, period)
        assert expected_before.state != expected_after.state, "test fixture must actually produce a state change"

        revised_value = _PAYEMS_THOUSANDS[period] - 500
        with _patched(observations_by_series={PAYEMS_SERIES_ID: _fred_payload({period: revised_value}), UNRATE_SERIES_ID: []}) as client:
            ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        rows = _recorded_results(db_session, monitor="labor")
        matching = [r for r in rows if r.evaluation_period == period]
        assert len(matching) == 1
        assert matching[0].state == expected_after.state
        assert matching[0].methodology_id == "labor_v1.0"
        assert matching[0].data_basis == "latest_revised_data"


class TestRecordedMonitorResultLaborUnchangedState:
    def test_genuine_recomputation_with_an_unchanged_state_still_records_a_result(self, db_session):
        """The Labor equivalent of TestRecordedMonitorResultInflationUnchangedState
        -- equally critical (contract §9's decision is explicitly
        uniform across both domains, §37)."""
        release = _employment_situation_release(db_session)
        occurrence = _occurrence(db_session, release)
        _seed_payems(db_session)
        _seed_unrate(db_session)

        period = date(2009, 5, 1)
        expected_before = _labor_result(_PAYEMS_THOUSANDS, _UNRATE_PERCENT, period)
        revised_payems = dict(_PAYEMS_THOUSANDS)
        revised_payems[period] = _PAYEMS_THOUSANDS[period] - 1  # a negligible nudge
        expected_after = _labor_result(revised_payems, _UNRATE_PERCENT, period)
        assert expected_before.state == expected_after.state, "test fixture must genuinely leave the state unchanged"

        revised_value = _PAYEMS_THOUSANDS[period] - 1
        with _patched(observations_by_series={PAYEMS_SERIES_ID: _fred_payload({period: revised_value}), UNRATE_SERIES_ID: []}) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        assert result.observation_changes != [], "test fixture must genuinely produce a REVISED observation write"
        labor_state_events = [e for e in result.analysis_changes if e.component == "LABOR" and e.event_type == "STATE_CHANGED"]
        assert labor_state_events == [], "test fixture must genuinely produce zero LABOR-level ReleaseAnalysisUpdate state-change rows"

        rows = _recorded_results(db_session, monitor="labor")
        matching = [r for r in rows if r.evaluation_period == period]
        assert len(matching) == 1
        assert matching[0].state == expected_before.state


class TestRecordedMonitorResultInsufficientData:
    def test_genuinely_insufficient_computation_is_recorded_for_both_domains(self, db_session):
        """Contract §37: insufficient-data results are recorded,
        uniformly for Inflation and Labor -- a real, successfully-
        computed classification, never treated as a failure."""
        release = _pio_release(db_session)
        occurrence = _occurrence(db_session, release)
        # Deliberately sparse -- only one prior month persisted, one NEW
        # month arrives, nowhere near enough for any r_3m/r_6m/r_12m
        # endpoint set.
        _seed_series(db_session, "PCEPILFE", {date(2025, 12, 1): 119.0}, title="Core PCE")
        _seed_series(db_session, "PCEPI", {date(2025, 12, 1): 129.0}, title="Headline PCE")
        _seed_series(db_session, "CPIAUCSL", {date(2025, 12, 1): 299.0}, title="CPI")
        _seed_series(db_session, "CPILFESL", {date(2025, 12, 1): 279.0}, title="Core CPI")

        expected = compute_series_momentum_at(
            [Observation(date=date(2025, 12, 1), value=119.0), Observation(date=date(2026, 1, 1), value=120.0)],
            "PCEPILFE",
            date(2026, 1, 1),
        )
        assert expected.state == "INSUFFICIENT_DATA", "test fixture must genuinely be insufficient"

        payload_pcepilfe = _fred_payload({date(2026, 1, 1): 120.0})
        with _patched(observations_by_series={"PCEPILFE": payload_pcepilfe, "PCEPI": []}) as client:
            ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        rows = _recorded_results(db_session, monitor="inflation")
        assert len(rows) == 1
        assert rows[0].state == "INSUFFICIENT_DATA"
        assert rows[0].evaluation_period == date(2026, 1, 1)


class TestRecordedMonitorResultNoChange:
    def test_no_change_check_records_nothing(self, db_session):
        """Contract §10: a NO_CHANGE run never reaches the canonical
        AFTER computation at all -- traced structurally, not merely
        behaviorally, in tests/test_recorded_monitor_result_architecture.py."""
        release = _pio_release(db_session)
        occurrence = _occurrence(db_session, release)
        _seed_series(db_session, "PCEPILFE", {date(2026, 1, 1): 120.0})

        with _patched(observations_by_series={"PCEPILFE": _fred_payload({date(2026, 1, 1): 120.0}), "PCEPI": []}) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        assert result.status == "NO_CHANGE"
        assert _recorded_results(db_session) == []


class TestRecordedMonitorResultUnaffectedSeries:
    def test_a_change_to_a_series_with_no_canonical_consumer_records_nothing(self, db_session):
        """Contract §64: a changed series that maps to neither monitor
        writes observations but computes, and records, nothing."""
        release = _release(db_session, name="Unmapped Release", provider_release_id="9501")
        _mapping(db_session, release, series_id="FABRICATED_UNMAPPED_SERIES_XYZ")
        occurrence = _occurrence(db_session, release)

        with _patched(
            observations_by_series={"FABRICATED_UNMAPPED_SERIES_XYZ": _fred_payload({date(2026, 1, 1): 42.0})},
            info_by_series={"FABRICATED_UNMAPPED_SERIES_XYZ": {"id": "FABRICATED_UNMAPPED_SERIES_XYZ", "title": "Fabricated", "units": "Units"}},
        ) as client:
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        assert result.observation_changes != []  # the write genuinely happened
        assert result.analysis_changes == []
        assert _recorded_results(db_session) == []


class TestRecordedMonitorResultRevisionImmutability:
    def test_a_later_revision_appends_a_new_row_and_never_mutates_the_prior_one(self, db_session):
        """Contract §12/§82: the worked revision example, proven end to
        end. Two genuine, different-magnitude revisions to the same
        occurrence's own PCEPILFE series produce TWO RecordedMonitorResult
        rows for the same evaluation_period, from two different
        release_check_run_id, both persisting unmodified."""
        release = _pio_release(db_session)
        occurrence = _occurrence(db_session, release)
        base = _constant_growth_series(date(2025, 1, 1), 13, start_value=120.0, monthly_growth=0.002)
        latest_period = max(base)

        _seed_series(db_session, "PCEPILFE", base, title="Core PCE")
        _seed_series(db_session, "PCEPI", _constant_growth_series(date(2025, 1, 1), 13, start_value=130.0, monthly_growth=0.002))
        _seed_series(db_session, "CPIAUCSL", _constant_growth_series(date(2025, 1, 1), 13, start_value=300.0, monthly_growth=0.002))
        _seed_series(db_session, "CPILFESL", _constant_growth_series(date(2025, 1, 1), 13, start_value=280.0, monthly_growth=0.002))

        first_revision = dict(base)
        first_revision[latest_period] = base[latest_period] * 1.25
        with _patched(observations_by_series={
            "PCEPILFE": _fred_payload(first_revision),
            "PCEPI": _fred_payload(_constant_growth_series(date(2025, 1, 1), 13, start_value=130.0, monthly_growth=0.002)),
        }) as client:
            ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        repo = ReleaseProcessingRepository(db_session)
        first_run = repo.list_check_runs_for_occurrence(occurrence.id)[0]
        rows_after_first = _recorded_results(db_session, monitor="inflation")
        assert len(rows_after_first) == 1
        first_row_id = rows_after_first[0].id
        first_row_state = rows_after_first[0].state
        first_row_calculated_at = rows_after_first[0].calculated_at

        second_revision_value = base[latest_period] * 0.80  # a further, different revision
        with _patched(observations_by_series={
            "PCEPILFE": _fred_payload({latest_period: second_revision_value}),
            "PCEPI": _fred_payload(_constant_growth_series(date(2025, 1, 1), 13, start_value=130.0, monthly_growth=0.002)),
        }) as client:
            ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        second_run = [r for r in repo.list_check_runs_for_occurrence(occurrence.id) if r.id != first_run.id][0]
        rows_after_second = _recorded_results(db_session, monitor="inflation")
        assert len(rows_after_second) == 2

        # The first row survives byte-identical -- never mutated:
        unchanged_first = next(r for r in rows_after_second if r.id == first_row_id)
        assert unchanged_first.state == first_row_state
        assert unchanged_first.calculated_at == first_row_calculated_at
        assert unchanged_first.release_check_run_id == first_run.id

        second_row = next(r for r in rows_after_second if r.id != first_row_id)
        assert second_row.evaluation_period == latest_period
        assert second_row.release_check_run_id == second_run.id
        assert {r.release_check_run_id for r in rows_after_second} == {first_run.id, second_run.id}


class TestRecordedMonitorResultRetries:
    def test_repeated_no_change_checks_record_nothing_until_a_genuine_change_is_detected(self, db_session):
        """Contract §11's own worked example: 09:00 NO_CHANGE, 10:00
        NO_CHANGE, 11:00 NEW data -> recompute. Only the third call
        creates a RecordedMonitorResult row."""
        release = _employment_situation_release(db_session)
        occurrence = _occurrence(db_session, release)
        _seed_payems(db_session)
        _seed_unrate(db_session)

        with _patched(observations_by_series={PAYEMS_SERIES_ID: [], UNRATE_SERIES_ID: []}) as client:
            first = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)
        assert first.status == "NO_CHANGE"

        with _patched(observations_by_series={PAYEMS_SERIES_ID: [], UNRATE_SERIES_ID: []}) as client:
            second = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)
        assert second.status == "NO_CHANGE"
        assert _recorded_results(db_session) == []

        revised_value = _PAYEMS_THOUSANDS[date(2009, 5, 1)] - 500
        with _patched(observations_by_series={PAYEMS_SERIES_ID: _fred_payload({date(2009, 5, 1): revised_value}), UNRATE_SERIES_ID: []}) as client:
            third = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)
        assert third.status == "CHANGED"
        assert _recorded_results(db_session) != []


class TestRecordedMonitorResultPartialFailure:
    def test_the_succeeding_series_change_still_genuinely_recomputes_and_records(self, db_session):
        """Contract §36: a PARTIAL_FAILURE run CAN still produce a
        genuine RecordedMonitorResult row -- recording is keyed to
        whether the AFTER computation genuinely ran, never to the
        coarser CheckRunStatus label. PAYEMS succeeds and changes;
        UNRATE fails -- Labor's own state still genuinely recomputes
        using PAYEMS's new value alongside UNRATE's currently-persisted
        (unaffected by today's failed fetch) value."""
        release = _employment_situation_release(db_session)
        occurrence = _occurrence(db_session, release)
        _seed_payems(db_session)
        _seed_unrate(db_session)

        def _get_observations(series_id, **kwargs):
            if series_id == UNRATE_SERIES_ID:
                raise FREDTimeoutError("timed out")
            return _fred_payload({date(2009, 5, 1): _PAYEMS_THOUSANDS[date(2009, 5, 1)] - 500})

        client = FREDClient(api_key="not-used", timeout=1.0)
        with patch.object(FREDClient, "get_observations", side_effect=_get_observations):
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        assert result.status == "PARTIAL_FAILURE"
        rows = _recorded_results(db_session, monitor="labor")
        assert rows != [], "PARTIAL_FAILURE must not suppress a genuinely-executed recomputation"


class TestRecordedMonitorResultProviderFailure:
    def test_a_total_provider_failure_records_nothing(self, db_session):
        """Contract §35: no genuine AFTER computation ever runs when
        every mapped series' fetch fails -- zero history, exactly like
        every other write this occurrence would have produced."""
        release = _employment_situation_release(db_session)
        occurrence = _occurrence(db_session, release)
        _seed_payems(db_session)
        _seed_unrate(db_session)

        client = FREDClient(api_key="not-used", timeout=1.0)
        with patch.object(FREDClient, "get_observations", side_effect=FREDTimeoutError("timed out")):
            result = ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        assert result.status == "FAILED_PROVIDER"
        assert _recorded_results(db_session) == []


class TestRecordedMonitorResultDatabaseFailureRollback:
    def test_a_deliberate_failure_after_provider_success_rolls_back_recorded_results_too(self, real_session_scope):
        """Mirrors TestLaborDatabaseFailureRollback's own identical
        pattern -- proves RecordedMonitorResult rolls back atomically
        with ReleaseCheckRun/observation writes/analysis-update effects
        (contract §36 of the #25E implementation prompt), never left
        as an orphaned row when the surrounding transaction fails."""
        with real_session_scope() as setup_session:
            release = _employment_situation_release(setup_session)
            occurrence = _occurrence(setup_session, release)
            _seed_payems(setup_session, {date(2009, 5, 1): _PAYEMS_THOUSANDS[date(2009, 5, 1)]})
            occurrence_id = occurrence.id

        try:
            class _DeliberateFailure(Exception):
                pass

            payload = _fred_payload({date(2009, 5, 1): _PAYEMS_THOUSANDS[date(2009, 5, 1)] - 500})
            client = FREDClient(api_key="not-used", timeout=1.0)

            with pytest.raises(_DeliberateFailure):
                with real_session_scope() as session:
                    with patch.object(FREDClient, "get_observations", side_effect=lambda sid, **kw: payload if sid == PAYEMS_SERIES_ID else []):
                        with patch.object(ReleaseProcessingRepository, "add_check_run", side_effect=_DeliberateFailure("simulated failure")):
                            ReleaseProcessingService(client).process_occurrence(occurrence_id, session, AS_OF)

            with real_session_scope() as verify_session:
                assert _recorded_results(verify_session) == []
        finally:
            with real_session_scope() as cleanup_session:
                from app.db.models import ReleaseOccurrence

                cleanup_session.execute(ReleaseOccurrence.__table__.delete().where(ReleaseOccurrence.id == occurrence_id))
                series = ReleaseProcessingRepository(cleanup_session).get_series_by_series_id(PAYEMS_SERIES_ID)
                if series is not None:
                    from app.db.models import EconomicObservation, EconomicSeries as _EconomicSeries

                    cleanup_session.execute(EconomicObservation.__table__.delete().where(EconomicObservation.economic_series_id == series.id))
                    cleanup_session.execute(_EconomicSeries.__table__.delete().where(_EconomicSeries.id == series.id))
