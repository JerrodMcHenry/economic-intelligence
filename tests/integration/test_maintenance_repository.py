"""Integration tests for `app.repositories.maintenance_repository.MaintenanceRepository`
against a real, isolated PostgreSQL test database (see tests/conftest.py).
No FastAPI, no OpenAI, no FRED -- this repository has no dependency on
any of them. Frozen contract:
docs/product/automated-economic-maintenance-v1.md §53/§54.
"""

from datetime import datetime, timezone

from app.db.models import MaintenanceSweep
from app.repositories.maintenance_repository import MaintenanceRepository


class TestStartSweep:
    def test_start_sweep_persists_started_at_with_everything_else_null(self, db_session):
        started_at = datetime.now(timezone.utc)
        sweep = MaintenanceRepository(db_session).start_sweep(started_at)

        assert sweep.id is not None
        assert sweep.started_at == started_at
        assert sweep.finished_at is None
        assert sweep.status is None
        assert sweep.due_count is None
        assert sweep.processed_count is None
        assert sweep.failed_count is None

    def test_a_started_never_finished_sweep_is_queryable_by_id(self, db_session):
        """The exact, intentional signal a crashed/still-running sweep
        produces (frozen §52/§25) -- a row exists, `finished_at IS
        NULL`, discoverable via a plain query, not merely in-memory."""
        started_at = datetime.now(timezone.utc)
        sweep = MaintenanceRepository(db_session).start_sweep(started_at)
        db_session.flush()

        found = db_session.get(MaintenanceSweep, sweep.id)
        assert found is not None
        assert found.finished_at is None


class TestFinishSweep:
    def test_finish_sweep_sets_every_field_together(self, db_session):
        started_at = datetime.now(timezone.utc)
        repo = MaintenanceRepository(db_session)
        sweep = repo.start_sweep(started_at)
        finished_at = datetime.now(timezone.utc)

        repo.finish_sweep(sweep.id, finished_at=finished_at, status="SUCCEEDED", due_count=3, processed_count=2, failed_count=1)

        assert sweep.finished_at == finished_at
        assert sweep.status == "SUCCEEDED"
        assert sweep.due_count == 3
        assert sweep.processed_count == 2
        assert sweep.failed_count == 1

    def test_zero_due_work_is_a_genuine_success_not_a_special_case(self, db_session):
        """Frozen §30: a sweep that finds zero due work and does
        nothing is healthy -- "no work" is a success outcome, never a
        failure or a suspicious no-op."""
        started_at = datetime.now(timezone.utc)
        repo = MaintenanceRepository(db_session)
        sweep = repo.start_sweep(started_at)
        finished_at = datetime.now(timezone.utc)

        repo.finish_sweep(sweep.id, finished_at=finished_at, status="SUCCEEDED", due_count=0, processed_count=0, failed_count=0)

        assert sweep.status == "SUCCEEDED"
        assert sweep.due_count == 0


class TestGetLatestSweep:
    def test_returns_none_when_no_sweep_exists(self, db_session):
        # db_session is rolled back per-test, so this table is
        # guaranteed empty for a fresh test unless this test itself
        # seeds a row.
        assert MaintenanceRepository(db_session).get_latest_sweep() is None

    def test_returns_the_most_recently_started_sweep(self, db_session):
        repo = MaintenanceRepository(db_session)
        earlier = repo.start_sweep(datetime(2026, 8, 1, 12, tzinfo=timezone.utc))
        later = repo.start_sweep(datetime(2026, 8, 2, 12, tzinfo=timezone.utc))

        latest = repo.get_latest_sweep()
        assert latest is not None
        assert latest.id == later.id
        assert latest.id != earlier.id

    def test_tie_broken_by_id_when_started_at_is_identical(self, db_session):
        repo = MaintenanceRepository(db_session)
        same_time = datetime(2026, 8, 1, 12, tzinfo=timezone.utc)
        repo.start_sweep(same_time)
        second = repo.start_sweep(same_time)

        latest = repo.get_latest_sweep()
        assert latest is not None
        assert latest.id == second.id
