"""Increment #56B: the schedule inside the database and inside a sweep.

`sync_schedule` against the real migrated catalog (rollback-isolated),
and `run_maintenance` end to end with a controlled schedule: it writes
the occurrences, reports each release's state, and exits 1 -- not 0 --
once scheduled updates have stopped. The provider is never reached: a
controlled schedule far from any due window keeps processing idle.
"""

from datetime import date

import pytest
import sqlalchemy as sa

from app.db.models import EconomicRelease, MaintenanceSweep, ReleaseOccurrence
from app.models.release_schedule import RELEASE_SCHEDULE, ScheduledRelease
from app.services.release_schedule import sync_schedule

pytestmark = pytest.mark.integration


class TestSyncSchedule:
    def test_writes_every_committed_date_as_an_occurrence_of_its_release(self, db_session):
        outcome = sync_schedule(db_session)

        expected = sum(len(r.dates) for r in RELEASE_SCHEDULE)
        assert (outcome.occurrences_created, outcome.occurrences_existing, outcome.missing_catalog_releases) == (
            expected,
            0,
            (),
        )
        rows = db_session.execute(
            sa.select(EconomicRelease.provider_release_id, ReleaseOccurrence.scheduled_date).join(
                ReleaseOccurrence, ReleaseOccurrence.economic_release_id == EconomicRelease.id
            )
        ).all()
        assert ("empsit", date(2026, 10, 2)) in rows and ("pio", date(2026, 9, 30)) in rows
        assert len(rows) == expected

    def test_is_idempotent(self, db_session):
        sync_schedule(db_session)
        again = sync_schedule(db_session)
        assert again.occurrences_created == 0
        assert again.occurrences_existing == sum(len(r.dates) for r in RELEASE_SCHEDULE)

    def test_a_deactivated_release_is_reported_missing_and_never_recreated(self, db_session):
        db_session.execute(
            sa.update(EconomicRelease).where(EconomicRelease.provider_release_id == "pio").values(active=False)
        )
        outcome = sync_schedule(db_session)
        assert outcome.missing_catalog_releases == ("BEA/pio",)
        assert db_session.execute(
            sa.select(sa.func.count()).select_from(EconomicRelease).where(EconomicRelease.provider_release_id == "pio")
        ).scalar_one() == 1


FAR_FUTURE = (
    ScheduledRelease("BLS", "cpi", "Consumer Price Index", "https://www.bls.gov/", (date(2099, 1, 15),)),
    ScheduledRelease("BLS", "empsit", "Employment Situation", "https://www.bls.gov/", (date(2099, 1, 8),)),
    ScheduledRelease("BEA", "pio", "Personal Income and Outlays", "https://www.bea.gov/", (date(2099, 1, 29),)),
)


@pytest.fixture
def configured(monkeypatch, test_database_url):
    from app.core.config import settings
    from app.db import session as session_module

    monkeypatch.setattr(settings, "database_url", test_database_url)
    monkeypatch.setattr(settings, "fred_api_key", None)
    session_module._get_engine.cache_clear()
    session_module._get_session_factory.cache_clear()
    yield
    from app.db.session import session_scope

    with session_scope() as session:
        session.execute(sa.delete(ReleaseOccurrence).where(ReleaseOccurrence.scheduled_date >= date(2099, 1, 1)))
        session.execute(sa.delete(MaintenanceSweep))
    session_module._get_engine.cache_clear()
    session_module._get_session_factory.cache_clear()


def _run(monkeypatch, schedule, as_of):
    import app.operations.run_maintenance as run_maintenance
    from app.services import release_schedule

    monkeypatch.setattr(run_maintenance, "sync_schedule", lambda session: release_schedule.sync_schedule(session, schedule))
    monkeypatch.setattr(run_maintenance, "schedule_status", lambda today: release_schedule.schedule_status(today, schedule))
    return run_maintenance.main(["--as-of-date", as_of])


class TestMaintenanceReportsTheSchedule:
    def test_a_current_schedule_is_written_reported_and_exits_zero(self, configured, monkeypatch, capsys):
        exit_code = _run(monkeypatch, FAR_FUTURE, "2098-06-01")

        captured = capsys.readouterr()
        assert exit_code == 0
        assert "Schedule: BLS cpi (Consumer Price Index): OK: next 2099-01-15" in captured.out
        from app.db.session import session_scope

        with session_scope() as session:
            assert session.execute(
                sa.select(sa.func.count()).select_from(ReleaseOccurrence).where(ReleaseOccurrence.scheduled_date >= date(2099, 1, 1))
            ).scalar_one() == 3

    def test_an_expired_schedule_fails_the_sweep_loudly(self, configured, monkeypatch, capsys):
        exit_code = _run(monkeypatch, FAR_FUTURE, "2099-03-01")

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "EXPIRED" in captured.err and "scheduled updates have STOPPED" in captured.err
        # The sweep itself still ran: an expired schedule stops NEW
        # scheduling, it does not stop processing what is already due.
        assert "Due occurrences: 0" in captured.out

    def test_a_missing_catalog_release_is_reported_as_missing(self, configured, monkeypatch, capsys):
        unknown = (ScheduledRelease("BLS", "not-in-catalog", "Imaginary", "https://www.bls.gov/", (date(2099, 1, 1),)),)
        exit_code = _run(monkeypatch, unknown, "2098-06-01")
        assert exit_code == 1
        assert "MISSING" in capsys.readouterr().err
