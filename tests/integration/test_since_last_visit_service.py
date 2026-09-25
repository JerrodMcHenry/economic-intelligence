"""Integration tests for Increment #25G's `SinceLastVisitService`
against a real, isolated PostgreSQL test database and real release-
processing fixtures -- FRED is mocked at the FREDClient-*method*
boundary, the same documented pattern
tests/integration/test_release_processing_service.py already
establishes (see that file's entry in
test_transaction_and_safety.py's `NETWORK_EXCEPTIONS`).

The real, curated CPI ("10")/Personal Income and Outlays ("54")/
Employment Situation ("50") release→series mappings are seeded,
persistent, active data in the isolated test database -- used here
directly, mirroring test_release_processing_service.py's own
established discipline, so this suite proves the whole #25G pipeline
against genuinely-computed economic results, not synthetic stand-ins.

Frozen contract: docs/product/since-last-visit-v1.md (#25F).
"""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from sqlalchemy import event

from app.clients.fred import FREDClient
from app.db.models import EconomicRelease, EconomicObservation, EconomicSeries, MaintenanceSweep, RecordedMonitorResult, ReleaseAnalysisUpdate, ReleaseCheckRun, ReleaseObservationUpdate
from app.repositories.release_processing_repository import ReleaseProcessingRepository
from app.repositories.release_repository import ReleaseRepository
from app.repositories.since_last_visit_repository import SinceLastVisitRepository
from app.services.release_processing import ReleaseProcessingService
from app.services.since_last_visit import SinceLastVisitService

AS_OF = date(2026, 8, 1)


@pytest.fixture
def real_session_scope(monkeypatch, test_database_url):
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


def _months(start: date, count: int) -> list[date]:
    dates = []
    year, month = start.year, start.month
    for i in range(count):
        total = year * 12 + (month - 1) + i
        yy, mm0 = divmod(total, 12)
        dates.append(date(yy, mm0 + 1, 1))
    return dates


def _constant_growth_series(start: date, count: int, start_value: float = 100.0, monthly_growth: float = 0.002) -> dict[date, float]:
    dates = _months(start, count)
    return {d: start_value * (1 + monthly_growth) ** i for i, d in enumerate(dates)}


def _fred_payload(values: dict[date, float | None]) -> list[dict]:
    return [{"date": d.isoformat(), "value": "." if v is None else str(v)} for d, v in sorted(values.items())]


def _release(session, provider_release_id):
    return session.execute(sa.select(EconomicRelease).where(EconomicRelease.provider_release_id == provider_release_id)).scalar_one()


def _occurrence(session, release, scheduled_date=AS_OF):
    return ReleaseRepository(session).upsert_occurrence(release.id, scheduled_date)


def _seed_series(session, series_id: str, values: dict[date, float | None], title="Test Series", units="Index"):
    repo = ReleaseProcessingRepository(session)
    series = repo.get_series_by_series_id(series_id) or repo.create_series(series_id, title, units)
    for observation_date, value in values.items():
        repo.write_observation(series.id, observation_date, value)
    return series


class _patched:
    def __init__(self, observations_by_series=None, info_by_series=None):
        self._observations = observations_by_series or {}
        self._info = info_by_series or {}
        self.client = FREDClient(api_key="not-used", timeout=1.0)

    def _get_observations(self, series_id, **kwargs):
        if series_id not in self._observations:
            raise AssertionError(f"unexpected get_observations call for {series_id!r}")
        return self._observations[series_id]

    def _get_series_info(self, series_id):
        return self._info.get(series_id, {"id": series_id, "title": series_id, "units": "Index"})

    def __enter__(self):
        self._p1 = patch.object(FREDClient, "get_observations", side_effect=self._get_observations)
        self._p2 = patch.object(FREDClient, "get_series_info", side_effect=self._get_series_info)
        self._p1.start()
        self._p2.start()
        return self.client

    def __exit__(self, *exc):
        self._p1.stop()
        self._p2.stop()


class TestFirstVisitEmptyDatabase:
    def test_no_checkpoint_no_history_returns_a_valid_first_visit_response(self, db_session):
        response = SinceLastVisitService().get_recap(db_session, None)
        assert response.first_visit is True
        assert response.after is None
        assert response.lookback_clamped is False
        assert response.inflation.coverage == "UNKNOWN"
        assert response.labor.coverage == "UNKNOWN"
        assert response.inflation.structural_changes == []
        assert response.inflation.recalculations == []


class TestInflationStructuralChangeEndToEnd:
    def test_a_genuine_state_change_appears_as_a_structural_change(self, db_session):
        release = _release(db_session, "pio")
        occurrence = _occurrence(db_session, release)
        base = _constant_growth_series(date(2025, 1, 1), 13, start_value=120.0, monthly_growth=0.002)
        latest = max(base)
        _seed_series(db_session, "us.pce.core.price-index.sa.monthly", base, title="Core PCE")
        _seed_series(db_session, "us.pce.headline.price-index.sa.monthly", _constant_growth_series(date(2025, 1, 1), 13, start_value=130.0, monthly_growth=0.002))
        _seed_series(db_session, "us.cpi.headline.price-index.sa.monthly", _constant_growth_series(date(2025, 1, 1), 13, start_value=300.0, monthly_growth=0.002))
        _seed_series(db_session, "us.cpi.core.price-index.sa.monthly", _constant_growth_series(date(2025, 1, 1), 13, start_value=280.0, monthly_growth=0.002))

        revised = dict(base)
        revised[latest] = base[latest] * 1.25
        with _patched(observations_by_series={
            "us.pce.core.price-index.sa.monthly": _fred_payload(revised),
            "us.pce.headline.price-index.sa.monthly": _fred_payload(_constant_growth_series(date(2025, 1, 1), 13, start_value=130.0, monthly_growth=0.002)),
        }) as client:
            ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        response = SinceLastVisitService().get_recap(db_session, None)
        inflation_changes = response.inflation.structural_changes
        assert len(inflation_changes) == 1
        assert inflation_changes[0].evaluation_period == latest
        assert inflation_changes[0].event_type == "STATE_CHANGED"


class TestLaborUnchangedConfirmationEndToEnd:
    _PAYEMS_THOUSANDS = {
        date(2008, 1, 1): 138391, date(2008, 2, 1): 138329, date(2008, 3, 1): 138259, date(2008, 4, 1): 138040,
        date(2008, 5, 1): 137851, date(2008, 6, 1): 137700, date(2008, 7, 1): 137497, date(2008, 8, 1): 137211,
        date(2008, 9, 1): 136760, date(2008, 10, 1): 136291, date(2008, 11, 1): 135541, date(2008, 12, 1): 134847,
        date(2009, 1, 1): 134079, date(2009, 2, 1): 133318, date(2009, 3, 1): 132494, date(2009, 4, 1): 131822,
        date(2009, 5, 1): 131466, date(2009, 6, 1): 131008, date(2009, 7, 1): 130662, date(2009, 8, 1): 130472,
        date(2009, 9, 1): 130246,
    }
    _UNRATE_PERCENT = {
        date(2008, 1, 1): 5.0, date(2008, 2, 1): 4.9, date(2008, 3, 1): 5.1, date(2008, 4, 1): 5.0,
        date(2008, 5, 1): 5.4, date(2008, 6, 1): 5.6, date(2008, 7, 1): 5.8, date(2008, 8, 1): 6.1,
        date(2008, 9, 1): 6.1, date(2008, 10, 1): 6.5, date(2008, 11, 1): 6.8, date(2008, 12, 1): 7.3,
        date(2009, 1, 1): 7.8, date(2009, 2, 1): 8.3, date(2009, 3, 1): 8.7, date(2009, 4, 1): 9.0,
        date(2009, 5, 1): 9.4, date(2009, 6, 1): 9.5, date(2009, 7, 1): 9.5, date(2009, 8, 1): 9.8,
    }

    def test_a_genuine_recomputation_with_unchanged_state_appears_as_a_recalculation(self, db_session):
        release = _release(db_session, "empsit")
        occurrence = _occurrence(db_session, release)
        _seed_series(db_session, "us.nonfarm.payroll-employment.sa.monthly", self._PAYEMS_THOUSANDS, title="us.nonfarm.payroll-employment.sa.monthly", units="Thousands of Persons")
        _seed_series(db_session, "us.unemployment-rate.sa.monthly", self._UNRATE_PERCENT, title="us.unemployment-rate.sa.monthly", units="Percent")

        period = date(2009, 5, 1)
        revised_value = self._PAYEMS_THOUSANDS[period] - 1  # negligible, keeps top-level state unchanged
        with _patched(observations_by_series={"us.nonfarm.payroll-employment.sa.monthly": _fred_payload({period: revised_value}), "us.unemployment-rate.sa.monthly": []}) as client:
            ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        response = SinceLastVisitService().get_recap(db_session, None)
        recalcs = response.labor.recalculations
        # Exact FIRST_CALCULATION-vs-UNCHANGED_CONFIRMATION branch logic
        # is already proven precisely, under full control, by
        # tests/test_since_last_visit_domain.py -- this end-to-end test's
        # own job is proving the real pipeline wires a genuine
        # unchanged-state recomputation into SOME recalculation item at
        # all (this shared, long-lived test database may already carry
        # earlier "labor" RecordedMonitorResult rows from other suites'
        # own real_session_scope-based tests, so either classification
        # is a correct outcome here).
        assert len(recalcs) == 1
        assert recalcs[0].kind in ("FIRST_CALCULATION", "UNCHANGED_CONFIRMATION")
        # The revised period (2009-05) propagates forward to {05, 08, 11}
        # per PAYEMS's own frozen {0,3,6}-month propagation -- the
        # current-result-selection rule (contract §68-70) correctly
        # selects the run's own LATEST touched period (2009-11), not the
        # originally-revised date, exactly mirroring #25E's own
        # empirically-discovered propagation behavior. This fixture's
        # own trailing data ends at 2009-09, so 2009-11 is genuinely
        # INSUFFICIENT_DATA -- a real, honestly-recorded classification,
        # not a bug in this test.
        assert recalcs[0].evaluation_period == date(2009, 11, 1)
        assert recalcs[0].state == "INSUFFICIENT_DATA"


class TestReadOnlyGuarantee:
    def test_row_counts_are_unchanged_across_a_request(self, db_session):
        tables = [MaintenanceSweep, ReleaseCheckRun, ReleaseObservationUpdate, ReleaseAnalysisUpdate, RecordedMonitorResult, EconomicObservation]
        before = {t: db_session.execute(sa.select(sa.func.count()).select_from(t)).scalar_one() for t in tables}

        SinceLastVisitService().get_recap(db_session, None)

        after = {t: db_session.execute(sa.select(sa.func.count()).select_from(t)).scalar_one() for t in tables}
        assert before == after


class TestQueryCountBound:
    def test_query_count_does_not_scale_with_number_of_check_runs(self, db_session):
        release = _release(db_session, "empsit")
        occurrence = _occurrence(db_session, release)
        _seed_series(db_session, "us.nonfarm.payroll-employment.sa.monthly", TestLaborUnchangedConfirmationEndToEnd._PAYEMS_THOUSANDS, title="us.nonfarm.payroll-employment.sa.monthly", units="Thousands of Persons")
        _seed_series(db_session, "us.unemployment-rate.sa.monthly", TestLaborUnchangedConfirmationEndToEnd._UNRATE_PERCENT, title="us.unemployment-rate.sa.monthly", units="Percent")

        payems = dict(TestLaborUnchangedConfirmationEndToEnd._PAYEMS_THOUSANDS)
        for i, d in enumerate(sorted(payems)[:5]):
            payems[d] = payems[d] - (i + 1)
            with _patched(observations_by_series={"us.nonfarm.payroll-employment.sa.monthly": _fred_payload({d: payems[d]}), "us.unemployment-rate.sa.monthly": []}) as client:
                ReleaseProcessingService(client).process_occurrence(occurrence.id, db_session, AS_OF)

        statements = []
        listener = lambda conn, cursor, statement, *a: statements.append(statement)
        event.listen(db_session.get_bind(), "before_cursor_execute", listener)
        try:
            SinceLastVisitService().get_recap(db_session, None)
        finally:
            event.remove(db_session.get_bind(), "before_cursor_execute", listener)

        # Bounded, small, fixed query count -- independent of the 5
        # check runs just created (never one query per run).
        assert len(statements) < 20, f"expected a small, bounded query count, got {len(statements)}: {statements}"


class TestRaceSafety:
    def test_an_event_committed_after_through_is_captured_is_excluded_then_included_next_time(self, real_session_scope):
        """Contract §10-13's own central race-safety proof, against a
        real, separately-committing session -- mirroring the exact
        pattern #25C's own concurrency tests already establish for a
        comparable real-database timing guarantee."""
        with real_session_scope() as setup_session:
            release = _release(setup_session, "empsit")
            occurrence = _occurrence(setup_session, release)
            occurrence_id = occurrence.id
            _seed_series(setup_session, "us.nonfarm.payroll-employment.sa.monthly", TestLaborUnchangedConfirmationEndToEnd._PAYEMS_THOUSANDS, title="us.nonfarm.payroll-employment.sa.monthly", units="Thousands of Persons")
            _seed_series(setup_session, "us.unemployment-rate.sa.monthly", TestLaborUnchangedConfirmationEndToEnd._UNRATE_PERCENT, title="us.unemployment-rate.sa.monthly", units="Percent")

        try:
            # Simulate the request's own `through` having been captured
            # strictly BEFORE a concurrent commit lands.
            through_before_commit = datetime.now(timezone.utc)

            revised_value = TestLaborUnchangedConfirmationEndToEnd._PAYEMS_THOUSANDS[date(2009, 5, 1)] - 500
            with real_session_scope() as session:
                with _patched(observations_by_series={"us.nonfarm.payroll-employment.sa.monthly": _fred_payload({date(2009, 5, 1): revised_value}), "us.unemployment-rate.sa.monthly": []}) as client:
                    ReleaseProcessingService(client).process_occurrence(occurrence_id, session, AS_OF)

            with real_session_scope() as verify_session:
                repo = SinceLastVisitRepository(verify_session)
                # The just-committed run must NOT appear in a window
                # whose own `through` predates it:
                rows = repo.list_check_runs_in_window(frozenset({release.id}), None, through_before_commit)
                assert rows == []

                # The identical run MUST appear in a follow-up window
                # using this response's own `through` as the new `after`:
                later_through = datetime.now(timezone.utc)
                rows_next = repo.list_check_runs_in_window(frozenset({release.id}), through_before_commit, later_through)
                assert len(rows_next) == 1
        finally:
            with real_session_scope() as cleanup_session:
                from app.db.models import ReleaseOccurrence

                cleanup_session.execute(ReleaseOccurrence.__table__.delete().where(ReleaseOccurrence.id == occurrence_id))
                # Both seeded rows (#56B: the unemployment row used to be
                # left behind, and a stray concept-keyed row now collides
                # with the first-party import in later tests).
                for series_id in ("us.nonfarm.payroll-employment.sa.monthly", "us.unemployment-rate.sa.monthly"):
                    series = ReleaseProcessingRepository(cleanup_session).get_series_by_series_id(series_id)
                    if series is not None:
                        cleanup_session.execute(EconomicObservation.__table__.delete().where(EconomicObservation.economic_series_id == series.id))
                        cleanup_session.execute(EconomicSeries.__table__.delete().where(EconomicSeries.id == series.id))
