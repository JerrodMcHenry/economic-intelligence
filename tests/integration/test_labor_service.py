"""Integration tests for LaborMonitorService against a real, isolated
PostgreSQL test database. No FastAPI, no OpenAI, no FRED --
LaborMonitorService has no FRED dependency at all (see its own module
docstring).

These tests exist to prove the SERVICE correctly composes persistence
(the existing, generic SeriesRepository) with the pure domain layer,
which a domain-level unit test (tests/test_domain_labor.py) cannot
prove on its own -- e.g. that a canonical series which isn't persisted
at all behaves identically to one that is persisted with insufficient
history, using REAL database queries rather than an in-memory
observation list, and that the shared-evaluation-period rule works
against actually-persisted, independently-queried series.
"""

from datetime import date

from app.domain.labor import month_before
from app.models.labor import PAYEMS_SERIES_ID, UNRATE_SERIES_ID
from app.models.series import Observation, SeriesResponse
from app.repositories.series_repository import SeriesRepository
from app.services.labor import LaborMonitorService

# 20 consecutive months, 2024-01 through 2025-08 -- comfortably more
# than UNRATE's own 15-month span (t through t-14) and PAYEMS's
# 7-month span (t through t-6), with margin. Chosen so both a complete
# evaluation at the anchor AND an individual-missing-month test remain
# possible without running out of history.
ANCHOR = date(2025, 8, 1)


def _payems_history(anchor: date, count: int = 20) -> list[tuple[date, float]]:
    # 150,000 (thousands) at the anchor, growing by 300/month going
    # backward -- i.e. genuinely expanding, non-degenerate month-over-
    # month changes (never a flat/linear-cancels-out sequence).
    return [(month_before(anchor, n), 150_000.0 - n * 0.3 - (n * n) * 0.01) for n in range(count)]


def _unrate_history(anchor: date, count: int = 20) -> list[tuple[date, float]]:
    return [(month_before(anchor, n), 4.0 + n * 0.02) for n in range(count)]


def _seed(db_session, series_id: str, points: list[tuple[date, float | None]]) -> None:
    SeriesRepository(db_session).save_series(
        SeriesResponse(
            series_id=series_id,
            title=series_id,
            units="Thousands of Persons" if series_id == PAYEMS_SERIES_ID else "Percent",
            observations=[Observation(date=d, value=v) for d, v in points],
        )
    )
    db_session.flush()


class TestCompleteHistory:
    def test_full_result_from_persisted_data_only(self, db_session):
        _seed(db_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        _seed(db_session, UNRATE_SERIES_ID, _unrate_history(ANCHOR))

        result = LaborMonitorService().get_result(db_session)

        assert result.methodology_id == "labor_v1.0"
        assert result.data_basis == "latest_revised_data"
        assert result.evaluation_period == ANCHOR
        assert result.state != "INSUFFICIENT_DATA"
        assert result.employment.state != "INSUFFICIENT_DATA"
        assert result.unemployment.state != "INSUFFICIENT_DATA"
        assert len(result.employment.observations) == 7
        assert len(result.unemployment.observations) == 6

    def test_never_mutates_persisted_data(self, db_session):
        _seed(db_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        _seed(db_session, UNRATE_SERIES_ID, _unrate_history(ANCHOR))

        from app.db.models import EconomicObservation, EconomicSeries

        series_count_before = db_session.query(EconomicSeries).count()
        observation_count_before = db_session.query(EconomicObservation).count()

        LaborMonitorService().get_result(db_session)
        LaborMonitorService().get_result(db_session)

        series_count_after = db_session.query(EconomicSeries).count()
        observation_count_after = db_session.query(EconomicObservation).count()

        assert series_count_before == series_count_after
        assert observation_count_before == observation_count_after


class TestSeriesNotPersisted:
    def test_neither_series_persisted_yields_insufficient_data_not_an_exception(self, db_session):
        result = LaborMonitorService().get_result(db_session)
        assert result.state == "INSUFFICIENT_DATA"
        assert result.evaluation_period is None
        assert result.employment.observations == []
        assert result.unemployment.observations == []

    def test_only_payems_persisted_unrate_missing_entirely(self, db_session):
        _seed(db_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        result = LaborMonitorService().get_result(db_session)
        assert result.state == "INSUFFICIENT_DATA"
        assert result.evaluation_period is None

    def test_only_unrate_persisted_payems_missing_entirely(self, db_session):
        _seed(db_session, UNRATE_SERIES_ID, _unrate_history(ANCHOR))
        result = LaborMonitorService().get_result(db_session)
        assert result.state == "INSUFFICIENT_DATA"
        assert result.evaluation_period is None


class TestSharedEvaluationPeriod:
    def test_payems_newer_than_unrate_bounds_by_unrate(self, db_session):
        _seed(db_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        unrate_anchor = month_before(ANCHOR, 2)  # UNRATE two months behind
        _seed(db_session, UNRATE_SERIES_ID, _unrate_history(unrate_anchor))

        result = LaborMonitorService().get_result(db_session)
        assert result.evaluation_period == unrate_anchor
        # Both components evaluated at the SAME period -- never two
        # different reference months in one result.
        assert max(o.observation_date for o in result.employment.observations) == unrate_anchor

    def test_unrate_newer_than_payems_bounds_by_payems(self, db_session):
        payems_anchor = month_before(ANCHOR, 3)  # PAYEMS three months behind
        _seed(db_session, PAYEMS_SERIES_ID, _payems_history(payems_anchor))
        _seed(db_session, UNRATE_SERIES_ID, _unrate_history(ANCHOR))

        result = LaborMonitorService().get_result(db_session)
        assert result.evaluation_period == payems_anchor


class TestMissingRequiredMonth:
    def test_missing_required_payems_month_is_employment_insufficient_data(self, db_session):
        history = [(d, v) for d, v in _payems_history(ANCHOR) if d != month_before(ANCHOR, 4)]
        _seed(db_session, PAYEMS_SERIES_ID, history)
        _seed(db_session, UNRATE_SERIES_ID, _unrate_history(ANCHOR))

        result = LaborMonitorService().get_result(db_session)
        assert result.evaluation_period == ANCHOR  # still the latest common date
        assert result.employment.state == "INSUFFICIENT_DATA"
        assert result.state == "INSUFFICIENT_DATA"
        # The gap is visible directly in the returned evidence.
        gap_entries = [o for o in result.employment.observations if o.observation_date == month_before(ANCHOR, 4)]
        assert gap_entries and gap_entries[0].value is None

    def test_missing_required_unrate_month_is_unemployment_insufficient_data(self, db_session):
        history = [(d, v) for d, v in _unrate_history(ANCHOR) if d != month_before(ANCHOR, 13)]
        _seed(db_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        _seed(db_session, UNRATE_SERIES_ID, history)

        result = LaborMonitorService().get_result(db_session)
        assert result.unemployment.state == "INSUFFICIENT_DATA"
        assert result.state == "INSUFFICIENT_DATA"
        # Employment is entirely unaffected by UNRATE's own gap.
        assert result.employment.state != "INSUFFICIENT_DATA"


class TestKnownHistoricalGapShape:
    def test_a_gap_outside_the_required_window_does_not_affect_the_result(self, db_session):
        """Mirrors the real UNRATE 2025-10 gap #20A.1's own research
        found: a missing month that does not fall inside the CURRENT
        evaluation's required 6-month set must never affect the
        result -- no special-case hack anywhere in this call chain."""
        far_gap = month_before(ANCHOR, 8)  # outside {0,1,2,12,13,14}
        unrate_history = [(d, v) for d, v in _unrate_history(ANCHOR) if d != far_gap]
        _seed(db_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        _seed(db_session, UNRATE_SERIES_ID, unrate_history)

        result = LaborMonitorService().get_result(db_session)
        assert result.unemployment.state != "INSUFFICIENT_DATA"


class TestRevisionsReflectedDeterministically:
    def test_a_persisted_revision_changes_the_result_deterministically(self, db_session):
        _seed(db_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        _seed(db_session, UNRATE_SERIES_ID, _unrate_history(ANCHOR))

        before = LaborMonitorService().get_result(db_session)

        # Revise the ANCHOR month's own PAYEMS observation (offset 0)
        # -- re-upsert via the same SeriesRepository write path any
        # real ingestion would use. Deliberately NOT offset 1 or 2:
        # per LABOR_V1_FROZEN_METHODOLOGY.md §13, a revision at
        # `month_before(ANCHOR, 1)` falls exactly in the cancellation
        # zone for `current_3m_avg_jobs(ANCHOR)` (its opposite-signed
        # effect on two adjacent monthly-change values cancels
        # exactly) -- offset 0 is one of the two offsets (§13's frozen
        # `{0, 3, 6}`) genuinely affected, avoiding a false failure.
        revised_history = [(d, (v + 500_000.0 if d == ANCHOR else v)) for d, v in _payems_history(ANCHOR)]
        _seed(db_session, PAYEMS_SERIES_ID, revised_history)

        after = LaborMonitorService().get_result(db_session)

        assert before.employment.current_3m_avg_jobs != after.employment.current_3m_avg_jobs
        # Calling again with no further write is stable.
        again = LaborMonitorService().get_result(db_session)
        assert after.model_dump() == again.model_dump()
