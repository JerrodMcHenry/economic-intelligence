"""Integration tests for Increment #25C's `MaintenanceOrchestrator`
against a real, isolated PostgreSQL test database. FRED is mocked at
the FREDClient-*method* boundary, never a live call -- the same
documented pattern `tests/integration/test_release_processing_service.py`
already establishes.

`MaintenanceOrchestrator.run_sweep` calls the REAL
`app.db.session.session_scope()` internally (multiple times per
sweep: sweep-start, due-work discovery, one call per occurrence,
sweep-finish -- frozen contract §20/§21/§24) rather than accepting an
injected session, exactly mirroring how the real CLI
(`app.operations.run_maintenance`) will call it in production -- so
these tests use the same `real_session_scope`-style monkeypatch
`tests/integration/test_transaction_and_safety.py`/
`test_process_release_cli.py` already use, proving the actual
production wiring, not a lookalike. Every test that writes durable
data cleans it up explicitly afterward (`real_session_scope` bypasses
the per-test `db_session` rollback).

Frozen contract: docs/product/automated-economic-maintenance-v1.md.
"""

from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest
import sqlalchemy as sa

from app.clients.fred import FREDAuthError, FREDClient, FREDTimeoutError
from app.db.models import EconomicRelease, EconomicSeries, MaintenanceSweep, ReleaseCheckRun, ReleaseSeriesMapping
from app.repositories.release_repository import ReleaseRepository
from app.services.maintenance import MaintenanceOrchestrator
from app.services.release_processing import _OCCURRENCE_LOCK_NAMESPACE

# `ReleaseProcessingService.process_occurrence`'s own `started_at`/
# `completed_at` are always the REAL wall clock (`datetime.now(timezone.utc)`),
# never derived from the caller-supplied `as_of_date` -- correct,
# existing, frozen behavior (a check's own timestamp is genuinely when
# it ran). Tests that call `run_sweep` more than once and assert on
# "already checked today" (§10's own settlement rule) therefore need
# `AS_OF` to be TODAY'S real UTC date, exactly as production always
# calls it (`app.operations.run_maintenance` defaults `as_of_date` to
# `datetime.now(timezone.utc).date()` when not explicitly overridden)
# -- never a fixed historical date, which would never line up with a
# real `completed_at` value and would make every occurrence look
# perpetually unsettled.
AS_OF = datetime.now(timezone.utc).date()


@pytest.fixture
def real_session_scope(monkeypatch, test_database_url):
    """Point the REAL `app.db.session.session_scope`/`settings.database_url`
    at the isolated test database for one test -- the identical fixture
    `tests/integration/test_transaction_and_safety.py` already defines
    for itself (restated here rather than imported, per that fixture's
    own precedent of having no shared home to import from)."""
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


def _seed_release_mapping_and_occurrence(session_scope, scheduled_date=AS_OF, provider_release_id="9401", series_id="UNRATE"):
    with session_scope() as session:
        release = EconomicRelease(name="Maintenance Test Release", provider="FRED", provider_release_id=provider_release_id, active=True)
        session.add(release)
        session.flush()
        session.add(ReleaseSeriesMapping(economic_release_id=release.id, series_id=series_id, active=True))
        occurrence = ReleaseRepository(session).upsert_occurrence(release.id, scheduled_date)
        session.flush()
        return release.id, occurrence.id


def _cleanup(session_scope, release_id: int, series_ids: tuple[str, ...] = ("UNRATE",)) -> None:
    with session_scope() as session:
        session.execute(EconomicRelease.__table__.delete().where(EconomicRelease.id == release_id))
        for series_id in series_ids:
            session.execute(EconomicSeries.__table__.delete().where(EconomicSeries.series_id == series_id))


def _cleanup_sweeps(session_scope, sweep_ids: list[int]) -> None:
    if not sweep_ids:
        return
    with session_scope() as session:
        session.execute(MaintenanceSweep.__table__.delete().where(MaintenanceSweep.id.in_(sweep_ids)))


def _mock_client():
    return FREDClient(api_key="not-used", timeout=1.0)


class TestNoDueWork:
    def test_zero_eligible_occurrences_is_a_successful_sweep(self, real_session_scope):
        orchestrator = MaintenanceOrchestrator(_mock_client())
        outcome = orchestrator.run_sweep(AS_OF)
        try:
            assert outcome.due_count == 0
            assert outcome.processed_count == 0
            assert outcome.failed_count == 0
            assert outcome.skipped_lock_count == 0

            with real_session_scope() as session:
                sweep = session.get(MaintenanceSweep, outcome.sweep_id)
                assert sweep.status == "SUCCEEDED"
                assert sweep.finished_at is not None
                assert sweep.due_count == 0
        finally:
            _cleanup_sweeps(real_session_scope, [outcome.sweep_id])


class TestOneDueOccurrence:
    def test_no_change_occurrence_processes_successfully(self, real_session_scope):
        release_id, occurrence_id = _seed_release_mapping_and_occurrence(real_session_scope, provider_release_id="9402")
        orchestrator = MaintenanceOrchestrator(_mock_client())
        try:
            with patch.object(FREDClient, "get_observations", return_value=[]):
                outcome = orchestrator.run_sweep(AS_OF)

            assert outcome.due_count == 1
            assert outcome.processed_count == 1
            assert outcome.failed_count == 0

            with real_session_scope() as session:
                runs = session.execute(
                    sa.select(ReleaseCheckRun).where(ReleaseCheckRun.release_occurrence_id == occurrence_id)
                ).scalars().all()
                assert len(runs) == 1
                assert runs[0].status == "NO_CHANGE"
        finally:
            _cleanup(real_session_scope, release_id)
            _cleanup_sweeps(real_session_scope, [outcome.sweep_id])

    def test_changed_occurrence_writes_a_new_observation(self, real_session_scope):
        release_id, occurrence_id = _seed_release_mapping_and_occurrence(real_session_scope, provider_release_id="9403")
        orchestrator = MaintenanceOrchestrator(_mock_client())
        payload = [{"date": "2026-01-01", "value": "4.1"}]
        try:
            with patch.object(FREDClient, "get_observations", return_value=payload):
                with patch.object(FREDClient, "get_series_info", return_value={"id": "UNRATE", "title": "Unemployment Rate", "units": "Percent"}):
                    outcome = orchestrator.run_sweep(AS_OF)

            assert outcome.processed_count == 1
            assert outcome.failed_count == 0

            with real_session_scope() as session:
                runs = session.execute(
                    sa.select(ReleaseCheckRun).where(ReleaseCheckRun.release_occurrence_id == occurrence_id)
                ).scalars().all()
                assert runs[0].status == "CHANGED"
        finally:
            _cleanup(real_session_scope, release_id)
            _cleanup_sweeps(real_session_scope, [outcome.sweep_id])


class TestMultipleDueOccurrences:
    def test_each_occurrence_is_processed_independently(self, real_session_scope):
        release_id_a, occurrence_id_a = _seed_release_mapping_and_occurrence(
            real_session_scope, provider_release_id="9404", series_id="UNRATE"
        )
        release_id_b, occurrence_id_b = _seed_release_mapping_and_occurrence(
            real_session_scope, provider_release_id="9405", series_id="PAYEMS"
        )
        orchestrator = MaintenanceOrchestrator(_mock_client())
        try:
            with patch.object(FREDClient, "get_observations", return_value=[]):
                outcome = orchestrator.run_sweep(AS_OF)

            assert outcome.due_count == 2
            assert outcome.processed_count == 2
            assert outcome.failed_count == 0

            with real_session_scope() as session:
                for occurrence_id in (occurrence_id_a, occurrence_id_b):
                    runs = session.execute(
                        sa.select(ReleaseCheckRun).where(ReleaseCheckRun.release_occurrence_id == occurrence_id)
                    ).scalars().all()
                    assert len(runs) == 1
                    assert runs[0].status == "NO_CHANGE"
        finally:
            _cleanup(real_session_scope, release_id_a, series_ids=("UNRATE",))
            _cleanup(real_session_scope, release_id_b, series_ids=("PAYEMS",))
            _cleanup_sweeps(real_session_scope, [outcome.sweep_id])

    def test_one_occurrence_failing_does_not_abort_the_others(self, real_session_scope):
        """Frozen §30: worker health is never conflated with any
        individual occurrence's own outcome -- one failure must not
        stop the sweep from processing the remaining due occurrences."""
        release_id_a, occurrence_id_a = _seed_release_mapping_and_occurrence(
            real_session_scope, provider_release_id="9406", series_id="UNRATE"
        )
        release_id_b, occurrence_id_b = _seed_release_mapping_and_occurrence(
            real_session_scope, provider_release_id="9407", series_id="PAYEMS"
        )
        orchestrator = MaintenanceOrchestrator(_mock_client())

        def _side_effect(series_id, **kwargs):
            if series_id == "UNRATE":
                raise FREDTimeoutError("timed out")
            return []

        try:
            with patch.object(FREDClient, "get_observations", side_effect=_side_effect):
                outcome = orchestrator.run_sweep(AS_OF)

            assert outcome.due_count == 2
            assert outcome.processed_count == 2
            assert outcome.failed_count == 1

            with real_session_scope() as session:
                run_a = session.execute(
                    sa.select(ReleaseCheckRun).where(ReleaseCheckRun.release_occurrence_id == occurrence_id_a)
                ).scalar_one()
                assert run_a.status == "FAILED_PROVIDER"
                run_b = session.execute(
                    sa.select(ReleaseCheckRun).where(ReleaseCheckRun.release_occurrence_id == occurrence_id_b)
                ).scalar_one()
                assert run_b.status == "NO_CHANGE"
        finally:
            _cleanup(real_session_scope, release_id_a, series_ids=("UNRATE",))
            _cleanup(real_session_scope, release_id_b, series_ids=("PAYEMS",))
            _cleanup_sweeps(real_session_scope, [outcome.sweep_id])


class TestProviderFailureRetrySurfacing:
    def test_failed_provider_occurrence_remains_due_on_the_next_sweep(self, real_session_scope):
        release_id, occurrence_id = _seed_release_mapping_and_occurrence(real_session_scope, provider_release_id="9408")
        orchestrator = MaintenanceOrchestrator(_mock_client())
        try:
            with patch.object(FREDClient, "get_observations", side_effect=FREDTimeoutError("timed out")):
                first = orchestrator.run_sweep(AS_OF)
            assert first.failed_count == 1

            # A second sweep, same day: the occurrence never settled
            # (§10/§12), so it remains due -- proving same-day retry
            # (§14) actually works end-to-end through the orchestrator,
            # not just at the repository-query level.
            with patch.object(FREDClient, "get_observations", return_value=[]):
                second = orchestrator.run_sweep(AS_OF)
            assert second.due_count == 1
            assert second.processed_count == 1
            assert second.failed_count == 0

            with real_session_scope() as session:
                runs = session.execute(
                    sa.select(ReleaseCheckRun).where(ReleaseCheckRun.release_occurrence_id == occurrence_id)
                ).scalars().all()
                assert len(runs) == 2
                assert {run.status for run in runs} == {"FAILED_PROVIDER", "NO_CHANGE"}
        finally:
            _cleanup(real_session_scope, release_id)
            _cleanup_sweeps(real_session_scope, [first.sweep_id, second.sweep_id])

    def test_settled_occurrence_is_not_due_again_the_same_day(self, real_session_scope):
        release_id, occurrence_id = _seed_release_mapping_and_occurrence(real_session_scope, provider_release_id="9409")
        orchestrator = MaintenanceOrchestrator(_mock_client())
        try:
            with patch.object(FREDClient, "get_observations", return_value=[]):
                first = orchestrator.run_sweep(AS_OF)
            assert first.processed_count == 1

            second = orchestrator.run_sweep(AS_OF)
            assert second.due_count == 0
            assert second.processed_count == 0
        finally:
            _cleanup(real_session_scope, release_id)
            _cleanup_sweeps(real_session_scope, [first.sweep_id, second.sweep_id])


class TestAuthFailure:
    def test_auth_failure_is_recorded_as_failed_provider_like_any_other_provider_failure(self, real_session_scope):
        """Frozen §13: FREDAuthError is NOT retryable by waiting and
        should escalate faster -- but at the CheckRunStatus level it
        still surfaces as the same, existing FAILED_PROVIDER status;
        the escalation distinction is an operator-visibility concern
        (§63), not a different persisted status this increment invents."""
        release_id, occurrence_id = _seed_release_mapping_and_occurrence(real_session_scope, provider_release_id="9410")
        orchestrator = MaintenanceOrchestrator(_mock_client())
        try:
            with patch.object(FREDClient, "get_observations", side_effect=FREDAuthError("bad key")):
                outcome = orchestrator.run_sweep(AS_OF)

            assert outcome.failed_count == 1
            with real_session_scope() as session:
                run = session.execute(
                    sa.select(ReleaseCheckRun).where(ReleaseCheckRun.release_occurrence_id == occurrence_id)
                ).scalar_one()
                assert run.status == "FAILED_PROVIDER"
        finally:
            _cleanup(real_session_scope, release_id)
            _cleanup_sweeps(real_session_scope, [outcome.sweep_id])


class TestSweepRecord:
    def test_sweep_counts_reflect_orchestrator_work_not_economic_significance(self, real_session_scope):
        release_id, occurrence_id = _seed_release_mapping_and_occurrence(real_session_scope, provider_release_id="9411")
        orchestrator = MaintenanceOrchestrator(_mock_client())
        payload = [{"date": "2026-01-01", "value": "4.1"}, {"date": "2026-02-01", "value": "4.2"}]
        try:
            with patch.object(FREDClient, "get_observations", return_value=payload):
                with patch.object(FREDClient, "get_series_info", return_value={"id": "UNRATE", "title": "t", "units": "u"}):
                    outcome = orchestrator.run_sweep(AS_OF)

            # Two observation changes in ONE occurrence -- due/processed
            # counts still describe orchestrator work (1 occurrence),
            # never the number of changed observations.
            assert outcome.due_count == 1
            assert outcome.processed_count == 1
        finally:
            _cleanup(real_session_scope, release_id)
            _cleanup_sweeps(real_session_scope, [outcome.sweep_id])

    def test_sweep_row_persists_even_when_zero_occurrences_are_due(self, real_session_scope):
        orchestrator = MaintenanceOrchestrator(_mock_client())
        outcome = orchestrator.run_sweep(AS_OF)
        try:
            with real_session_scope() as session:
                sweep = session.get(MaintenanceSweep, outcome.sweep_id)
                assert sweep is not None
                assert sweep.due_count == 0
                assert sweep.status == "SUCCEEDED"
        finally:
            _cleanup_sweeps(real_session_scope, [outcome.sweep_id])


class TestLockingAndConcurrency:
    def test_two_sweeps_processing_the_same_occurrence_never_both_succeed(self, real_session_scope):
        """A direct proof of the PostgreSQL advisory lock (frozen
        §18/§19): hold the lock open in one real session (simulating an
        in-flight sweep), then attempt to process the SAME occurrence
        through `try_acquire_and_process_occurrence` in a second,
        independent session -- the second must be refused (`None`),
        never allowed to race the first."""
        from app.services.release_processing import ReleaseProcessingService, try_acquire_and_process_occurrence

        release_id, occurrence_id = _seed_release_mapping_and_occurrence(real_session_scope, provider_release_id="9412")
        service = ReleaseProcessingService(_mock_client())
        try:
            with real_session_scope() as holder_session:
                acquired = holder_session.execute(
                    sa.select(sa.func.pg_try_advisory_xact_lock(_OCCURRENCE_LOCK_NAMESPACE, occurrence_id))
                ).scalar_one()
                assert acquired is True

                # While the FIRST transaction (and its lock) is still
                # open, a SECOND, independent session must be refused.
                with real_session_scope() as contender_session:
                    with patch.object(FREDClient, "get_observations", return_value=[]):
                        result = try_acquire_and_process_occurrence(service, occurrence_id, contender_session, AS_OF)
                    assert result is None
                # holder_session's own transaction commits here, releasing the lock.

            # After the lock is released, processing succeeds normally.
            with real_session_scope() as session:
                with patch.object(FREDClient, "get_observations", return_value=[]):
                    result = try_acquire_and_process_occurrence(service, occurrence_id, session, AS_OF)
                assert result is not None
                assert result.status == "NO_CHANGE"
        finally:
            _cleanup(real_session_scope, release_id)

    def test_different_occurrences_are_not_serialized_by_the_same_lock(self, real_session_scope):
        """Frozen §19's own explicit requirement: the lock key includes
        `occurrence_id`, so two DIFFERENT occurrences must remain
        independently processable even while one's own lock is held."""
        from app.services.release_processing import ReleaseProcessingService, try_acquire_and_process_occurrence

        release_id_a, occurrence_id_a = _seed_release_mapping_and_occurrence(
            real_session_scope, provider_release_id="9413", series_id="UNRATE"
        )
        release_id_b, occurrence_id_b = _seed_release_mapping_and_occurrence(
            real_session_scope, provider_release_id="9414", series_id="PAYEMS"
        )
        service = ReleaseProcessingService(_mock_client())
        try:
            with real_session_scope() as holder_session:
                acquired = holder_session.execute(
                    sa.select(sa.func.pg_try_advisory_xact_lock(_OCCURRENCE_LOCK_NAMESPACE, occurrence_id_a))
                ).scalar_one()
                assert acquired is True

                with real_session_scope() as other_session:
                    with patch.object(FREDClient, "get_observations", return_value=[]):
                        result = try_acquire_and_process_occurrence(service, occurrence_id_b, other_session, AS_OF)
                    assert result is not None
                    assert result.status == "NO_CHANGE"
        finally:
            _cleanup(real_session_scope, release_id_a, series_ids=("UNRATE",))
            _cleanup(real_session_scope, release_id_b, series_ids=("PAYEMS",))

    def test_lock_contention_is_recorded_as_skipped_not_failed(self, real_session_scope):
        """The orchestrator's own accounting distinguishes "skipped due
        to lock contention" from a genuine processing failure -- a
        contended occurrence is neither `processed_count` nor
        `failed_count`, and the sweep itself still succeeds overall."""
        release_id, occurrence_id = _seed_release_mapping_and_occurrence(real_session_scope, provider_release_id="9415")
        orchestrator = MaintenanceOrchestrator(_mock_client())
        try:
            with real_session_scope() as holder_session:
                acquired = holder_session.execute(
                    sa.select(sa.func.pg_try_advisory_xact_lock(_OCCURRENCE_LOCK_NAMESPACE, occurrence_id))
                ).scalar_one()
                assert acquired is True

                outcome = orchestrator.run_sweep(AS_OF)

            assert outcome.due_count == 1
            assert outcome.processed_count == 0
            assert outcome.failed_count == 0
            assert outcome.skipped_lock_count == 1
        finally:
            _cleanup(real_session_scope, release_id)
            _cleanup_sweeps(real_session_scope, [outcome.sweep_id])


class TestManualAndAutomaticCoexistence:
    def test_manual_cli_path_and_automated_path_share_the_same_lock(self, real_session_scope):
        """Frozen §59: the manual CLI must use the SAME advisory lock
        an automated run would -- proven here by holding the lock via
        the manual CLI's own shared entry point
        (`try_acquire_and_process_occurrence`) and confirming a
        concurrent orchestrator sweep correctly skips it."""
        from app.services.release_processing import ReleaseProcessingService, try_acquire_and_process_occurrence

        release_id, occurrence_id = _seed_release_mapping_and_occurrence(real_session_scope, provider_release_id="9416")
        service = ReleaseProcessingService(_mock_client())
        orchestrator = MaintenanceOrchestrator(_mock_client())
        try:
            with real_session_scope() as manual_session:
                with patch.object(FREDClient, "get_observations", return_value=[]):
                    manual_result = try_acquire_and_process_occurrence(service, occurrence_id, manual_session, AS_OF)
                assert manual_result is not None

                # Lock is released the instant manual_session's own
                # transaction commits (end of this `with` block), so a
                # sweep AFTER this block succeeds normally -- proving
                # the two paths interoperate rather than merely coexist
                # in source code.
            outcome = orchestrator.run_sweep(AS_OF)
            # Already settled by the manual run above -- correctly not due again today.
            assert outcome.due_count == 0
        finally:
            _cleanup(real_session_scope, release_id)
            _cleanup_sweeps(real_session_scope, [outcome.sweep_id])


class TestDatabaseFailure:
    def test_a_database_failure_processing_one_occurrence_is_recorded_and_does_not_abort_the_sweep(self, real_session_scope):
        """Frozen §23/§48: a genuine database-layer failure durably
        persists no `ReleaseCheckRun` row at all -- the sweep's own
        in-memory accounting is the only surviving evidence for that
        specific occurrence, and the sweep itself still completes and
        records truthful counts."""
        from sqlalchemy.exc import OperationalError

        release_id, occurrence_id = _seed_release_mapping_and_occurrence(real_session_scope, provider_release_id="9417")
        orchestrator = MaintenanceOrchestrator(_mock_client())
        try:
            with patch(
                "app.services.release_processing.ReleaseProcessingService.process_occurrence",
                side_effect=OperationalError("statement", {}, Exception("connection lost")),
            ):
                outcome = orchestrator.run_sweep(AS_OF)

            assert outcome.due_count == 1
            assert outcome.processed_count == 0
            assert outcome.failed_count == 1
            assert outcome.database_failure_occurrence_ids == [occurrence_id]

            with real_session_scope() as session:
                runs = session.execute(
                    sa.select(ReleaseCheckRun).where(ReleaseCheckRun.release_occurrence_id == occurrence_id)
                ).scalars().all()
                assert runs == []

            # The sweep record itself still exists and is finished truthfully.
            with real_session_scope() as session:
                sweep = session.get(MaintenanceSweep, outcome.sweep_id)
                assert sweep.status == "SUCCEEDED"
                assert sweep.finished_at is not None
                assert sweep.failed_count == 1
        finally:
            _cleanup(real_session_scope, release_id)
            _cleanup_sweeps(real_session_scope, [outcome.sweep_id])


class TestCrashRecovery:
    def test_a_crash_mid_sweep_leaves_the_sweep_row_unfinished_and_the_next_sweep_recovers_cleanly(self, real_session_scope):
        """Simulates a crash between sweep-start and sweep-finish (the
        due-work discovery itself raises) -- the started sweep row must
        survive with `finished_at IS NULL` (frozen §52/§25's own
        intentional signal), and a subsequent, ordinary sweep must
        recover cleanly with zero special-cased logic (frozen §20)."""
        release_id, occurrence_id = _seed_release_mapping_and_occurrence(real_session_scope, provider_release_id="9418")
        orchestrator = MaintenanceOrchestrator(_mock_client())

        class _SimulatedCrash(Exception):
            pass

        try:
            with patch(
                "app.repositories.release_processing_repository.ReleaseProcessingRepository.list_due_occurrence_ids",
                side_effect=_SimulatedCrash("simulated crash"),
            ):
                with pytest.raises(_SimulatedCrash):
                    orchestrator.run_sweep(AS_OF)

            with real_session_scope() as session:
                crashed_sweep = session.execute(
                    sa.select(MaintenanceSweep).order_by(MaintenanceSweep.id.desc()).limit(1)
                ).scalar_one()
                assert crashed_sweep.finished_at is None
                assert crashed_sweep.status is None
            crashed_sweep_id = crashed_sweep.id

            # The next, ordinary sweep recovers cleanly -- no special
            # recovery logic needed, exactly per §20's own finding.
            with patch.object(FREDClient, "get_observations", return_value=[]):
                recovery_outcome = orchestrator.run_sweep(AS_OF)
            assert recovery_outcome.due_count == 1
            assert recovery_outcome.processed_count == 1
        finally:
            _cleanup(real_session_scope, release_id)
            _cleanup_sweeps(real_session_scope, [crashed_sweep_id, recovery_outcome.sweep_id])


class TestClockInjection:
    def test_as_of_date_is_threaded_explicitly_never_a_bare_system_clock_read(self, real_session_scope):
        """An occurrence scheduled in the future relative to an
        EXPLICITLY injected `as_of_date` must never be treated as due,
        proving `as_of_date` genuinely drives eligibility end-to-end
        through the orchestrator, not just cosmetically (frozen
        §16/§56/§57)."""
        release_id, occurrence_id = _seed_release_mapping_and_occurrence(
            real_session_scope, scheduled_date=date(2026, 9, 1), provider_release_id="9419"
        )
        orchestrator = MaintenanceOrchestrator(_mock_client())
        earlier_as_of = date(2026, 8, 1)
        outcome = orchestrator.run_sweep(earlier_as_of)
        try:
            assert outcome.due_count == 0
        finally:
            _cleanup(real_session_scope, release_id)
            _cleanup_sweeps(real_session_scope, [outcome.sweep_id])


class TestNoLiveFredCall:
    def test_never_makes_a_real_network_request(self, real_session_scope):
        """A fail-fast fake network boundary: if the orchestrator ever
        tried a real HTTP call, this would raise immediately instead of
        silently attempting a network request in a sandboxed test
        environment."""
        release_id, occurrence_id = _seed_release_mapping_and_occurrence(real_session_scope, provider_release_id="9420")
        orchestrator = MaintenanceOrchestrator(_mock_client())
        try:
            with patch("httpx.Client.request", side_effect=AssertionError("a real network request must never happen in tests")):
                with patch.object(FREDClient, "get_observations", return_value=[]):
                    outcome = orchestrator.run_sweep(AS_OF)
            assert outcome.processed_count == 1
        finally:
            _cleanup(real_session_scope, release_id)
            _cleanup_sweeps(real_session_scope, [outcome.sweep_id])
