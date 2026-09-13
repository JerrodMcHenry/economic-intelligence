"""Integration tests for InflationMonitorService.get_what_changed_result
against a real, isolated PostgreSQL test database -- contract
`inflation_what_changed_v1.0`. No FastAPI, no OpenAI, no live FRED.

Expected values are independently hand-derived, never obtained by
calling app.domain.inflation/app.domain.inflation_what_changed
functions directly and asserting on their own output -- these tests
exist to prove the SERVICE correctly composes persistence
(SeriesRepository) with the exact-period construction and comparison
layers, using REAL database queries.
"""

from datetime import date

from app.domain.inflation import month_before
from app.models.inflation import CONFIRMATION_SERIES_ID, HEADLINE_CPI_SERIES_ID, PRIMARY_SERIES_ID, TARGET_SERIES_ID
from app.models.series import Observation, SeriesResponse
from app.repositories.series_repository import SeriesRepository
from app.services.inflation import InflationMonitorService

# 26 consecutive months (2023-01 .. 2025-02) -- long enough that a full
# 12 months of trailing history exists for every month from 2024-01
# onward, so a single null-valued final month still leaves a genuinely
# valid earlier period to compare against.
LONG_HISTORY = [(month_before(date(2025, 2, 1), -i), 100.0 + i * 0.5) for i in range(-25, 1)]


def _seed(db_session, series_id: str, points: list[tuple[date, float | None]]) -> None:
    SeriesRepository(db_session).save_series(
        SeriesResponse(
            series_id=series_id,
            title=series_id,
            units="Index",
            observations=[Observation(date=d, value=v) for d, v in points],
        )
    )
    db_session.flush()


class TestOrdinarySectionAnchors:
    def test_current_period_is_latest_observation_not_latest_valid(self, db_session):
        """The exact bug this contract fixes: the true latest month
        (August-equivalent, null-valued) must be selected as
        current_period, never silently resolved back to July-equivalent."""
        points = LONG_HISTORY[:-1] + [(date(2025, 2, 1), None)]
        _seed(db_session, PRIMARY_SERIES_ID, points)

        result = InflationMonitorService().get_what_changed_result(db_session)

        section = result.primary_momentum_changes
        assert section.current_period == date(2025, 2, 1)
        assert section.previous_period == date(2025, 1, 1)
        assert section.current_evidence.state == "INSUFFICIENT_DATA"
        assert section.previous_evidence.state != "INSUFFICIENT_DATA"
        assert section.availability_lost is True

    def test_previous_is_exact_calendar_month_before_current(self, db_session):
        _seed(db_session, PRIMARY_SERIES_ID, LONG_HISTORY)
        result = InflationMonitorService().get_what_changed_result(db_session)
        section = result.primary_momentum_changes
        assert section.previous_period == month_before(section.current_period, 1)

    def test_valid_to_valid_no_state_change_but_metric_may_change(self, db_session):
        _seed(db_session, PRIMARY_SERIES_ID, LONG_HISTORY)
        result = InflationMonitorService().get_what_changed_result(db_session)
        section = result.primary_momentum_changes
        assert section.comparison_available is True
        assert section.previous_evidence.state != "INSUFFICIENT_DATA"
        assert section.current_evidence.state != "INSUFFICIENT_DATA"


class TestValidUnavailableTransitions:
    def test_valid_to_unavailable(self, db_session):
        points = LONG_HISTORY[:-1] + [(date(2025, 2, 1), None)]
        _seed(db_session, HEADLINE_CPI_SERIES_ID, points)
        result = InflationMonitorService().get_what_changed_result(db_session)
        section = result.headline_cpi_changes
        assert section.availability_lost is True
        assert section.availability_restored is False
        assert section.state_changed is False

    def test_unavailable_to_valid(self, db_session):
        # Latest month (2025-02) is valid; the one before it (2025-01)
        # is missing its own t-12 endpoint (2024-01) is fine here since
        # full monthly coverage exists -- instead null out 2025-01 itself.
        points = [(d, v) for d, v in LONG_HISTORY if d != date(2025, 1, 1)]
        _seed(db_session, HEADLINE_CPI_SERIES_ID, points)
        result = InflationMonitorService().get_what_changed_result(db_session)
        section = result.headline_cpi_changes
        assert section.current_period == date(2025, 2, 1)
        assert section.previous_period == date(2025, 1, 1)
        assert section.previous_evidence.state == "INSUFFICIENT_DATA"
        assert section.current_evidence.state != "INSUFFICIENT_DATA"
        assert section.availability_restored is True


class TestConfirmationAnchor:
    def test_anchors_to_latest_shared_observation_period_not_latest_common_period(self, db_session):
        """The exact scenario the frozen contract's worked example
        describes: Core CPI has an observation in the latest shared
        month, but its own required endpoint is missing there --
        inflation_v1.0's Monitor still reports an earlier
        latest_common_period as CONFIRMS, while What Changed correctly
        anchors to the later, shared-but-unavailable month."""
        _seed(db_session, PRIMARY_SERIES_ID, LONG_HISTORY)
        cpi_points = [(d, v * 0.5) for d, v in LONG_HISTORY if d != date(2025, 2, 1)]
        cpi_points_with_gap = cpi_points + [(date(2025, 2, 1), None)]
        _seed(db_session, CONFIRMATION_SERIES_ID, cpi_points_with_gap)

        service = InflationMonitorService()
        monitor_result = service.get_result(db_session)
        what_changed_result = service.get_what_changed_result(db_session)

        # Monitor's own confirmation still anchors to the latest VALID common period:
        assert monitor_result.confirmation.latest_common_period == date(2025, 1, 1)
        assert monitor_result.confirmation.relationship != "UNAVAILABLE"

        # What Changed anchors later, to the latest SHARED observation:
        confirmation_section = what_changed_result.confirmation_changes
        assert confirmation_section.current_confirmation_period == date(2025, 2, 1)
        assert confirmation_section.current_confirmation_period > monitor_result.confirmation.latest_common_period
        assert confirmation_section.current_relationship == "UNAVAILABLE"
        assert confirmation_section.previous_confirmation_period == date(2025, 1, 1)
        assert confirmation_section.previous_relationship != "UNAVAILABLE"
        assert confirmation_section.confirmation_availability_lost is True

    def test_no_shared_observation_period_at_all(self, db_session):
        _seed(db_session, PRIMARY_SERIES_ID, LONG_HISTORY)
        _seed(db_session, CONFIRMATION_SERIES_ID, [(date(2010, 1, 1), 50.0), (date(2010, 7, 1), 51.0)])

        result = InflationMonitorService().get_what_changed_result(db_session)
        section = result.confirmation_changes
        assert section.comparison_available is False
        assert section.current_confirmation_period is None
        assert section.previous_confirmation_period is None
        assert section.changes == []

    def test_both_series_evaluated_at_the_exact_same_period(self, db_session):
        _seed(db_session, PRIMARY_SERIES_ID, LONG_HISTORY)
        _seed(db_session, CONFIRMATION_SERIES_ID, [(d, v * 0.5) for d, v in LONG_HISTORY])
        result = InflationMonitorService().get_what_changed_result(db_session)
        section = result.confirmation_changes
        assert section.current_primary_state.calculation_period == section.current_confirmation_state.calculation_period
        assert section.previous_primary_state.calculation_period == section.previous_confirmation_state.calculation_period


class TestDifferingHeadlineAnchors:
    def test_headline_pce_and_cpi_use_independent_periods(self, db_session):
        _seed(db_session, TARGET_SERIES_ID, LONG_HISTORY)  # headline PCE, latest = 2025-02
        cpi_points = [p for p in LONG_HISTORY if p[0] != date(2025, 2, 1)]  # headline CPI, latest = 2025-01
        _seed(db_session, HEADLINE_CPI_SERIES_ID, cpi_points)

        result = InflationMonitorService().get_what_changed_result(db_session)
        assert result.headline_pce_changes.current_period == date(2025, 2, 1)
        assert result.headline_cpi_changes.current_period == date(2025, 1, 1)
        # never substituted for each other:
        assert result.headline_pce_changes.current_period != result.headline_cpi_changes.current_period


class TestNoBackwardSkipping:
    def test_july_august_september_missing_month_never_bridged(self, db_session):
        months = [month_before(date(2025, 1, 1), -i) for i in range(-24, 3)]  # 2023-01 .. 2025-03
        points = [(d, 100.0 + i * 0.5) for i, d in enumerate(months)]
        # 2025-02 (August-equivalent): value null -> INSUFFICIENT_DATA there
        points = [(d, None if d == date(2025, 2, 1) else v) for d, v in points]
        _seed(db_session, PRIMARY_SERIES_ID, points)

        result = InflationMonitorService().get_what_changed_result(db_session)
        section = result.primary_momentum_changes
        # Latest observation is 2025-03 (September-equivalent) -- current, not searched past:
        assert section.current_period == date(2025, 3, 1)
        assert section.previous_period == date(2025, 2, 1)
        assert section.availability_restored is True
        assert section.state_changed is False
        # 2025-01 (July-equivalent) never appears anywhere in this comparison:
        for event in section.changes:
            assert event.previous_period == date(2025, 2, 1)
            assert event.current_period == date(2025, 3, 1)


class TestNoMutation:
    def test_get_what_changed_result_does_not_modify_persisted_observations(self, db_session):
        _seed(db_session, PRIMARY_SERIES_ID, LONG_HISTORY)
        _seed(db_session, CONFIRMATION_SERIES_ID, [(d, v * 0.5) for d, v in LONG_HISTORY])
        _seed(db_session, TARGET_SERIES_ID, LONG_HISTORY)
        _seed(db_session, HEADLINE_CPI_SERIES_ID, LONG_HISTORY)

        repo = SeriesRepository(db_session)
        series = repo.get_series_by_series_id(PRIMARY_SERIES_ID)
        before, _ = repo.get_observations(series.id, None, None, limit=200, offset=0, order="asc")
        before_values = [(o.observation_date, o.value) for o in before]

        service = InflationMonitorService()
        service.get_what_changed_result(db_session)
        service.get_what_changed_result(db_session)  # twice, to also prove no side effect accumulates

        after, _ = repo.get_observations(series.id, None, None, limit=200, offset=0, order="asc")
        after_values = [(o.observation_date, o.value) for o in after]
        assert before_values == after_values

    def test_repeated_calls_are_deterministic(self, db_session):
        _seed(db_session, PRIMARY_SERIES_ID, LONG_HISTORY)
        _seed(db_session, CONFIRMATION_SERIES_ID, [(d, v * 0.5) for d, v in LONG_HISTORY])
        _seed(db_session, TARGET_SERIES_ID, LONG_HISTORY)
        _seed(db_session, HEADLINE_CPI_SERIES_ID, LONG_HISTORY)

        service = InflationMonitorService()
        result_1 = service.get_what_changed_result(db_session)
        result_2 = service.get_what_changed_result(db_session)
        assert result_1 == result_2


# No FREDClient fail-fast mock here: tests/integration/ has an existing,
# deliberately narrow architectural guard (only test_discovery_service.py
# may import FREDClient -- see
# TestAIAndNetworkIndependence.NETWORK_EXCEPTIONS in
# test_transaction_and_safety.py). The equivalent proof for this feature
# lives at the HTTP layer instead
# (tests/api/test_inflation_what_changed_api.py::TestAIAndFredIndependence),
# which already exercises this exact same service method end-to-end.
