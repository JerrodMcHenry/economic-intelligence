"""Integration tests for LaborMonitorService.get_what_changed_result
against a real, isolated PostgreSQL test database -- contract
`labor_what_changed_v1.0`. No FastAPI, no OpenAI, no FRED.

These tests exist to prove the SERVICE correctly composes persistence
(the existing, generic SeriesRepository) with
`month_over_month_labor_periods`/`compute_labor_monitor_result_at`
(app.domain.labor) and the comparator (app.domain.labor_what_changed),
using REAL database queries -- something neither
tests/test_domain_labor_what_changed.py (pure, no database) nor
tests/integration/test_labor_service.py (#20B's own `get_result` only)
can prove on its own.
"""

from datetime import date

from app.db.models import EconomicObservation, EconomicSeries
from app.domain.labor import month_before
from app.models.labor import PAYEMS_SERIES_ID, UNRATE_SERIES_ID
from app.models.series import Observation, SeriesResponse
from app.repositories.series_repository import SeriesRepository
from app.services.labor import LaborMonitorService

# Same shape as tests/integration/test_labor_service.py's own fixtures
# (genuinely expanding, non-degenerate month-over-month changes),
# redefined locally rather than imported -- test files in this project
# are kept independent of one another, the same discipline
# tests/integration/test_inflation_what_changed_service.py already
# follows relative to its own sibling Monitor test file.
ANCHOR = date(2025, 8, 1)


def _payems_history(anchor: date, count: int = 20) -> list[tuple[date, float]]:
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


class TestOrdinaryComparison:
    def test_current_and_previous_periods_are_exact_calendar_months_apart(self, db_session):
        _seed(db_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        _seed(db_session, UNRATE_SERIES_ID, _unrate_history(ANCHOR))

        result = LaborMonitorService().get_what_changed_result(db_session)

        assert result.comparison_available is True
        assert result.current_period == ANCHOR
        assert result.previous_period == month_before(ANCHOR, 1)

    def test_top_level_contract_fields(self, db_session):
        _seed(db_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        _seed(db_session, UNRATE_SERIES_ID, _unrate_history(ANCHOR))
        result = LaborMonitorService().get_what_changed_result(db_session)
        assert result.methodology_id == "labor_v1.0"
        assert result.comparison_contract_id == "labor_what_changed_v1.0"
        assert result.comparison_type == "MONTH_OVER_MONTH"
        assert result.data_basis == "latest_revised_data"

    def test_previous_and_current_labor_state_are_real_states_not_insufficient(self, db_session):
        _seed(db_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        _seed(db_session, UNRATE_SERIES_ID, _unrate_history(ANCHOR))
        result = LaborMonitorService().get_what_changed_result(db_session)
        assert result.previous_labor_state != "INSUFFICIENT_DATA"
        assert result.current_labor_state != "INSUFFICIENT_DATA"

    def test_employment_and_unemployment_sections_share_the_same_period_pair(self, db_session):
        """No per-section period fields exist (Labor's own documented
        simplification vs. Inflation) -- verify the SHARED periods are
        actually what every section's embedded evidence was computed
        at, via the observation dates each section's own evidence
        lists."""
        _seed(db_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        _seed(db_session, UNRATE_SERIES_ID, _unrate_history(ANCHOR))
        result = LaborMonitorService().get_what_changed_result(db_session)

        employment_current_dates = {o.observation_date for o in result.employment_changes.current_evidence.observations}
        unemployment_current_dates = {o.observation_date for o in result.unemployment_changes.current_evidence.observations}
        assert max(employment_current_dates) == result.current_period
        assert max(unemployment_current_dates) == result.current_period

        employment_previous_dates = {o.observation_date for o in result.employment_changes.previous_evidence.observations}
        assert max(employment_previous_dates) == result.previous_period


class TestNoDataAtAll:
    def test_neither_series_persisted_yields_comparison_unavailable(self, db_session):
        result = LaborMonitorService().get_what_changed_result(db_session)
        assert result.comparison_available is False
        assert result.previous_period is None
        assert result.current_period is None
        assert result.previous_labor_state == "INSUFFICIENT_DATA"
        assert result.current_labor_state == "INSUFFICIENT_DATA"
        assert result.changes == []
        assert result.any_state_changed is False
        assert result.any_metric_changed is False
        assert result.any_availability_changed is False

    def test_no_data_at_all_still_embeds_insufficient_data_shaped_evidence_not_none(self, db_session):
        result = LaborMonitorService().get_what_changed_result(db_session)
        assert result.employment_changes.previous_evidence.state == "INSUFFICIENT_DATA"
        assert result.employment_changes.current_evidence.state == "INSUFFICIENT_DATA"
        assert result.employment_changes.previous_evidence.observations == []
        assert result.unemployment_changes.current_evidence.observations == []


class TestAvailabilityTransitionAcrossTheServiceLayer:
    def test_a_gap_at_the_current_period_produces_employment_availability_lost(self, db_session):
        # A NULL-valued row at ANCHOR itself (not an omitted row) --
        # the row still exists (so determine_evaluation_period, which
        # only looks at which dates are PERSISTED, still resolves to
        # ANCHOR), but its value is unusable, so
        # current_3m_avg_jobs(ANCHOR) loses one of its four required
        # points and goes unavailable -- while
        # current_3m_avg_jobs(month_before(ANCHOR, 1)) (the PREVIOUS
        # period's own requirement) never touches ANCHOR at all, so it
        # stays fully available.
        history = [(d, (None if d == ANCHOR else v)) for d, v in _payems_history(ANCHOR)]
        _seed(db_session, PAYEMS_SERIES_ID, history)
        _seed(db_session, UNRATE_SERIES_ID, _unrate_history(ANCHOR))

        result = LaborMonitorService().get_what_changed_result(db_session)
        assert result.current_period == ANCHOR  # determine_evaluation_period is unaffected by a value-only gap...
        assert result.employment_changes.current_evidence.state == "INSUFFICIENT_DATA"
        assert result.employment_changes.previous_evidence.state != "INSUFFICIENT_DATA"
        assert result.employment_changes.availability_lost is True
        # LABOR.state co-occurring loss, from the same root cause:
        assert result.current_labor_state == "INSUFFICIENT_DATA"
        assert result.any_availability_changed is True
        # UNEMPLOYMENT is entirely unaffected by a PAYEMS-only gap:
        assert result.unemployment_changes.availability_lost is False


class TestRevisionsReflectedDeterministically:
    def test_a_persisted_revision_changes_the_comparison_deterministically(self, db_session):
        _seed(db_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        _seed(db_session, UNRATE_SERIES_ID, _unrate_history(ANCHOR))

        before = LaborMonitorService().get_what_changed_result(db_session)

        # Revise the ANCHOR month's own PAYEMS observation (offset 0,
        # one of the frozen {0,3,6} genuinely-affected offsets) --
        # exactly test_labor_service.py's own precedent, applied here
        # at the What Changed layer.
        revised_history = [(d, (v + 500_000.0 if d == ANCHOR else v)) for d, v in _payems_history(ANCHOR)]
        _seed(db_session, PAYEMS_SERIES_ID, revised_history)

        after = LaborMonitorService().get_what_changed_result(db_session)

        assert before.employment_changes.current_evidence.current_3m_avg_jobs != after.employment_changes.current_evidence.current_3m_avg_jobs
        # The comparator itself (before vs. after, applied via two
        # separate service calls, is NOT a same-period-revision
        # comparison -- both are still month-over-month) still behaves
        # deterministically:
        again = LaborMonitorService().get_what_changed_result(db_session)
        assert after.model_dump() == again.model_dump()


class TestNoMutation:
    def test_get_what_changed_result_does_not_modify_persisted_observations(self, db_session):
        _seed(db_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        _seed(db_session, UNRATE_SERIES_ID, _unrate_history(ANCHOR))

        series_count_before = db_session.query(EconomicSeries).count()
        observation_count_before = db_session.query(EconomicObservation).count()

        service = LaborMonitorService()
        service.get_what_changed_result(db_session)
        service.get_what_changed_result(db_session)  # twice, to also prove no side effect accumulates

        series_count_after = db_session.query(EconomicSeries).count()
        observation_count_after = db_session.query(EconomicObservation).count()
        assert series_count_before == series_count_after
        assert observation_count_before == observation_count_after

    def test_repeated_calls_are_deterministic(self, db_session):
        _seed(db_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        _seed(db_session, UNRATE_SERIES_ID, _unrate_history(ANCHOR))

        service = LaborMonitorService()
        result_1 = service.get_what_changed_result(db_session)
        result_2 = service.get_what_changed_result(db_session)
        assert result_1.model_dump() == result_2.model_dump()


class TestCurrentLaborResultAttached:
    def test_current_labor_result_matches_a_separate_get_result_call(self, db_session):
        _seed(db_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        _seed(db_session, UNRATE_SERIES_ID, _unrate_history(ANCHOR))

        service = LaborMonitorService()
        what_changed = service.get_what_changed_result(db_session)
        monitor_result = service.get_result(db_session)

        assert what_changed.current_labor_result is not None
        assert what_changed.current_labor_result.model_dump() == monitor_result.model_dump()


# No FREDClient fail-fast mock here -- LaborMonitorService has no FRED
# dependency at all (see its own module docstring), the identical
# reasoning tests/integration/test_labor_service.py's own trailing
# comment already gives for `get_result`. The equivalent proof for
# this feature lives at the HTTP layer instead
# (tests/api/test_labor_what_changed_api.py).
