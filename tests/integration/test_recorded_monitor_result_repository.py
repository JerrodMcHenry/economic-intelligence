"""Integration tests for Increment #25E's `RecordedMonitorResult`
model and `ReleaseProcessingRepository.add_recorded_monitor_result`
against a real, isolated PostgreSQL test database (see
tests/conftest.py). Frozen contract:
docs/product/recorded-state-history-v1.md (#25D).

Mirrors tests/integration/test_release_processing_repository.py's own
established fixture/mapping discipline -- a synthetic release/mapping
well outside the real curated range ("9601"+), never the real curated
CPI/PIO/Employment Situation mappings (those are exercised, with real
economic behavior, by the RecordedMonitorResult test classes appended
to tests/integration/test_release_processing_service.py instead).
"""

from datetime import date, datetime, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app.db.models import EconomicRelease, RecordedMonitorResult, ReleaseCheckRun
from app.models.release_processing import RecordableMonitorResult
from app.repositories.release_processing_repository import ReleaseProcessingRepository
from app.repositories.release_repository import ReleaseRepository

AS_OF = date(2026, 8, 1)


def _release(session, name="Recorded Result Test Release", provider_release_id="9601", active=True):
    release = EconomicRelease(name=name, provider="FRED", provider_release_id=provider_release_id, active=active)
    session.add(release)
    session.flush()
    return release


def _occurrence(session, release, scheduled_date=AS_OF):
    return ReleaseRepository(session).upsert_occurrence(release.id, scheduled_date)


def _check_run(session, occurrence, status="CHANGED"):
    now = datetime.now(timezone.utc)
    return ReleaseProcessingRepository(session).add_check_run(occurrence.id, status, now, now)


class TestModelShapeAndDefaults:
    def test_insert_and_read_round_trips_every_field(self, db_session):
        release = _release(db_session)
        occurrence = _occurrence(db_session, release)
        run = _check_run(db_session, occurrence)
        calculated_at = datetime.now(timezone.utc)

        ReleaseProcessingRepository(db_session).add_recorded_monitor_result(
            run.id,
            RecordableMonitorResult(
                monitor="inflation",
                evaluation_period=date(2026, 6, 1),
                state="COOLING",
                methodology_id="inflation_v1.0",
                data_basis="latest_revised_data",
            ),
            calculated_at,
        )
        db_session.flush()

        row = db_session.execute(
            sa.select(RecordedMonitorResult).where(RecordedMonitorResult.release_check_run_id == run.id)
        ).scalar_one()
        assert row.monitor == "inflation"
        assert row.evaluation_period == date(2026, 6, 1)
        assert row.state == "COOLING"
        assert row.methodology_id == "inflation_v1.0"
        assert row.data_basis == "latest_revised_data"
        assert row.calculated_at == calculated_at
        assert row.created_at is not None  # server-default bookkeeping only, never a second semantic timestamp

    def test_insufficient_data_is_a_plain_non_null_state_value(self, db_session):
        """Contract §76: INSUFFICIENT_DATA is stored as an ordinary,
        non-null literal value of `state` -- never a null state with a
        separate nullable status column."""
        release = _release(db_session)
        occurrence = _occurrence(db_session, release)
        run = _check_run(db_session, occurrence)

        ReleaseProcessingRepository(db_session).add_recorded_monitor_result(
            run.id,
            RecordableMonitorResult(
                monitor="labor",
                evaluation_period=date(2026, 6, 1),
                state="INSUFFICIENT_DATA",
                methodology_id="labor_v1.0",
                data_basis="latest_revised_data",
            ),
            datetime.now(timezone.utc),
        )
        db_session.flush()

        row = db_session.execute(
            sa.select(RecordedMonitorResult).where(RecordedMonitorResult.release_check_run_id == run.id)
        ).scalar_one()
        assert row.state == "INSUFFICIENT_DATA"
        assert row.evaluation_period is not None


class TestUniqueConstraint:
    def test_duplicate_run_monitor_period_is_rejected_by_postgres(self, db_session):
        """Contract §13/§33/§75: UNIQUE(release_check_run_id, monitor,
        evaluation_period) -- the ONE genuine bug case this prevents.
        Proven against real PostgreSQL, not an application-level check."""
        release = _release(db_session)
        occurrence = _occurrence(db_session, release)
        run = _check_run(db_session, occurrence)
        record = RecordableMonitorResult(
            monitor="inflation", evaluation_period=date(2026, 6, 1), state="COOLING",
            methodology_id="inflation_v1.0", data_basis="latest_revised_data",
        )
        repo = ReleaseProcessingRepository(db_session)
        repo.add_recorded_monitor_result(run.id, record, datetime.now(timezone.utc))
        db_session.flush()

        repo.add_recorded_monitor_result(run.id, record, datetime.now(timezone.utc))
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_same_period_across_two_different_check_runs_is_legitimate(self, db_session):
        """The exact case the three-column shape must NOT block: the
        same (monitor, evaluation_period) recorded again by a later,
        independent ReleaseCheckRun (contract §13's own worked
        reasoning)."""
        release = _release(db_session)
        occurrence = _occurrence(db_session, release)
        run_a = _check_run(db_session, occurrence)
        run_b = _check_run(db_session, occurrence)
        repo = ReleaseProcessingRepository(db_session)
        record = RecordableMonitorResult(
            monitor="inflation", evaluation_period=date(2026, 6, 1), state="COOLING",
            methodology_id="inflation_v1.0", data_basis="latest_revised_data",
        )
        repo.add_recorded_monitor_result(run_a.id, record, datetime.now(timezone.utc))
        repo.add_recorded_monitor_result(run_b.id, record, datetime.now(timezone.utc))
        db_session.flush()  # must not raise

        rows = db_session.execute(
            sa.select(RecordedMonitorResult).where(RecordedMonitorResult.evaluation_period == date(2026, 6, 1))
        ).scalars().all()
        assert {row.release_check_run_id for row in rows} == {run_a.id, run_b.id}

    def test_different_monitors_same_run_and_period_are_both_legitimate(self, db_session):
        """Contract §34: schema allows one ReleaseCheckRun to produce
        rows for both monitors -- never a hard-coded one-to-one
        assumption."""
        release = _release(db_session)
        occurrence = _occurrence(db_session, release)
        run = _check_run(db_session, occurrence)
        repo = ReleaseProcessingRepository(db_session)
        repo.add_recorded_monitor_result(
            run.id,
            RecordableMonitorResult(monitor="inflation", evaluation_period=date(2026, 6, 1), state="COOLING", methodology_id="inflation_v1.0", data_basis="latest_revised_data"),
            datetime.now(timezone.utc),
        )
        repo.add_recorded_monitor_result(
            run.id,
            RecordableMonitorResult(monitor="labor", evaluation_period=date(2026, 6, 1), state="STABLE", methodology_id="labor_v1.0", data_basis="latest_revised_data"),
            datetime.now(timezone.utc),
        )
        db_session.flush()  # must not raise

        rows = db_session.execute(
            sa.select(RecordedMonitorResult).where(RecordedMonitorResult.release_check_run_id == run.id)
        ).scalars().all()
        assert {row.monitor for row in rows} == {"inflation", "labor"}


class TestForeignKeyBehavior:
    def test_release_check_run_id_is_required(self, db_session):
        with pytest.raises(IntegrityError):
            db_session.add(
                RecordedMonitorResult(
                    release_check_run_id=None, monitor="inflation", evaluation_period=date(2026, 6, 1),
                    state="COOLING", methodology_id="inflation_v1.0", data_basis="latest_revised_data",
                    calculated_at=datetime.now(timezone.utc),
                )
            )
            db_session.flush()

    def test_a_nonexistent_release_check_run_id_is_rejected(self, db_session):
        with pytest.raises(IntegrityError):
            db_session.add(
                RecordedMonitorResult(
                    release_check_run_id=999_999_999, monitor="inflation", evaluation_period=date(2026, 6, 1),
                    state="COOLING", methodology_id="inflation_v1.0", data_basis="latest_revised_data",
                    calculated_at=datetime.now(timezone.utc),
                )
            )
            db_session.flush()

    def test_deleting_the_owning_check_run_cascades(self, db_session):
        """Contract §74: ondelete=CASCADE, matching
        ReleaseObservationUpdate/ReleaseAnalysisUpdate's own already-
        established convention exactly -- no application code path
        ever deletes a ReleaseCheckRun, but the FK behavior itself is
        proven directly here, not merely asserted."""
        release = _release(db_session)
        occurrence = _occurrence(db_session, release)
        run = _check_run(db_session, occurrence)
        repo = ReleaseProcessingRepository(db_session)
        repo.add_recorded_monitor_result(
            run.id,
            RecordableMonitorResult(monitor="inflation", evaluation_period=date(2026, 6, 1), state="COOLING", methodology_id="inflation_v1.0", data_basis="latest_revised_data"),
            datetime.now(timezone.utc),
        )
        db_session.flush()

        db_session.execute(ReleaseCheckRun.__table__.delete().where(ReleaseCheckRun.id == run.id))
        db_session.flush()

        remaining = db_session.execute(
            sa.select(RecordedMonitorResult).where(RecordedMonitorResult.release_check_run_id == run.id)
        ).scalars().all()
        assert remaining == []


class TestNullability:
    def test_every_column_is_not_null(self, db_session):
        """Contract §76: every column is NOT NULL -- no field in this
        schema is ever null, including evaluation_period for an
        INSUFFICIENT_DATA row (contract §21)."""
        columns = {c.name: c for c in RecordedMonitorResult.__table__.columns}
        for name, column in columns.items():
            assert column.nullable is False, f"{name} must be NOT NULL per the frozen contract"


class TestOrdering:
    def test_default_query_ordering_is_calculated_at_desc_then_id_desc(self, db_session):
        """Contract §58/§61: deterministic ordering for a future
        consumer -- proven here as a query shape, not exposed as a new
        repository read method (per the explicit #25E instruction not
        to build a speculative read repository)."""
        release = _release(db_session)
        occurrence = _occurrence(db_session, release)
        run_a = _check_run(db_session, occurrence)
        run_b = _check_run(db_session, occurrence)
        repo = ReleaseProcessingRepository(db_session)
        t1 = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
        repo.add_recorded_monitor_result(
            run_a.id,
            RecordableMonitorResult(monitor="inflation", evaluation_period=date(2026, 5, 1), state="COOLING", methodology_id="inflation_v1.0", data_basis="latest_revised_data"),
            t1,
        )
        repo.add_recorded_monitor_result(
            run_b.id,
            RecordableMonitorResult(monitor="inflation", evaluation_period=date(2026, 6, 1), state="STABLE", methodology_id="inflation_v1.0", data_basis="latest_revised_data"),
            t2,
        )
        db_session.flush()

        rows = db_session.execute(
            sa.select(RecordedMonitorResult)
            .where(RecordedMonitorResult.monitor == "inflation", RecordedMonitorResult.release_check_run_id.in_([run_a.id, run_b.id]))
            .order_by(RecordedMonitorResult.calculated_at.desc(), RecordedMonitorResult.id.desc())
        ).scalars().all()
        assert [row.evaluation_period for row in rows] == [date(2026, 6, 1), date(2026, 5, 1)]


class TestNoUpdateOrDeleteMethod:
    def test_the_repository_exposes_no_update_or_delete_method_for_recorded_monitor_result(self):
        """Contract §30/§53: append-only through normal application
        code -- structural proof, not merely an absence-of-a-test."""
        method_names = [name for name in dir(ReleaseProcessingRepository) if not name.startswith("_")]
        forbidden = ("update_recorded", "upsert_recorded", "replace_recorded", "delete_recorded_monitor_result")
        violations = [name for name in method_names if any(name.startswith(prefix) for prefix in forbidden)]
        assert violations == [], f"an update/delete path for RecordedMonitorResult exists: {violations}"
