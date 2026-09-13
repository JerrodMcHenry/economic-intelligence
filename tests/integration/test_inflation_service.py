"""Integration tests for InflationMonitorService against a real,
isolated PostgreSQL test database. No FastAPI, no OpenAI, no FRED --
InflationMonitorService has no FRED dependency at all (see its own
module docstring).

Expected values are independently hand-derived, never obtained by
calling app.domain.inflation functions directly and asserting on their
own output -- these tests exist to prove the SERVICE correctly composes
persistence (SeriesRepository) with the pure domain layer, which a
domain-level unit test (tests/test_domain_inflation.py) cannot prove on
its own -- e.g. that a canonical series which isn't persisted at all
behaves identically to one that is persisted with insufficient history,
using REAL database queries rather than an in-memory observation list.
"""

from datetime import date

from app.models.inflation import (
    CONFIRMATION_SERIES_ID,
    HEADLINE_CPI_SERIES_ID,
    PRIMARY_SERIES_ID,
    TARGET_SERIES_ID,
)
from app.domain.inflation import month_before
from app.models.series import Observation, SeriesResponse
from app.repositories.series_repository import SeriesRepository
from app.services.inflation import InflationMonitorService

# 25 consecutive months (2023-01 .. 2025-01) -- long enough that removing the
# single most-recent month still leaves a genuine earlier period with a full
# 12 months of trailing history of its own (FULL_HISTORY below is deliberately
# shorter and only suitable for tests that don't need to search backward).
LONG_HISTORY = [(month_before(date(2025, 1, 1), -i), 100.0 + i * 0.5) for i in range(-24, 1)]

FULL_HISTORY = [
    (date(2024, 1, 1), 100.0),
    (date(2024, 2, 1), 100.5),
    (date(2024, 3, 1), 101.0),
    (date(2024, 4, 1), 101.5),
    (date(2024, 5, 1), 102.0),
    (date(2024, 6, 1), 102.5),
    (date(2024, 7, 1), 103.0),
    (date(2024, 8, 1), 104.0),
    (date(2024, 9, 1), 105.0),
    (date(2024, 10, 1), 106.0),
    (date(2024, 11, 1), 107.5),
    (date(2024, 12, 1), 109.0),
    (date(2025, 1, 1), 110.0),
]


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


class TestPersistedOnlyCalculation:
    def test_full_result_from_persisted_data_only(self, db_session):
        _seed(db_session, PRIMARY_SERIES_ID, FULL_HISTORY)
        _seed(db_session, CONFIRMATION_SERIES_ID, FULL_HISTORY)
        _seed(db_session, TARGET_SERIES_ID, FULL_HISTORY)
        _seed(db_session, HEADLINE_CPI_SERIES_ID, FULL_HISTORY)

        result = InflationMonitorService().get_result(db_session)

        assert result.methodology_id == "inflation_v1.0"
        assert result.data_basis == "latest_revised_data"
        expected_r3m = ((110.0 / 106.0) ** 4 - 1) * 100
        assert result.underlying_momentum.r_3m_annualized == expected_r3m
        assert result.underlying_momentum.calculation_period == date(2025, 1, 1)
        assert result.coverage.primary_available is True
        assert result.coverage.confirmation_available is True
        assert result.coverage.target_available is True
        assert result.coverage.headline_cpi_available is True

    def test_series_not_persisted_at_all_yields_insufficient_data_not_an_exception(self, db_session):
        """None of the four canonical series are seeded -- the service
        must return a normal result with every component unavailable,
        never raise SeriesNotFoundError or any other exception."""
        result = InflationMonitorService().get_result(db_session)

        assert result.underlying_momentum.state == "INSUFFICIENT_DATA"
        assert result.confirmation.confirmation_latest.state == "INSUFFICIENT_DATA"
        assert result.target.available is False
        assert result.coverage.primary_available is False
        assert result.coverage.confirmation_available is False
        assert result.coverage.target_available is False
        assert result.coverage.headline_cpi_available is False

    def test_one_series_persisted_others_missing_behaves_identically_to_domain_layer(self, db_session):
        """Only Core PCE persisted -- confirmation/target/headline
        should behave exactly as if their observation lists were empty
        (proven at the domain layer in tests/test_domain_inflation.py's
        TestCoverage.test_all_unavailable_when_nothing_persisted), now
        proven end-to-end through a real repository query."""
        _seed(db_session, PRIMARY_SERIES_ID, FULL_HISTORY)

        result = InflationMonitorService().get_result(db_session)

        assert result.coverage.primary_available is True
        assert result.coverage.confirmation_available is False
        assert result.coverage.target_available is False
        assert result.coverage.headline_cpi_available is False
        assert result.confirmation.latest_common_period is None
        assert result.confirmation.relationship == "UNAVAILABLE"


class TestExactCalendarLookupThroughRepository:
    def test_missing_intermediate_month_does_not_invalidate_endpoint_calculation(self, db_session):
        """February is never persisted for Core PCE; April's 3M uses
        January directly (an endpoint calculation) and remains valid --
        proven here through a real repository round-trip, not just an
        in-memory index."""
        points = [
            (date(2024, 1, 1), 100.0),
            # 2024-02-01 never persisted at all
            (date(2024, 3, 1), 101.0),
            (date(2024, 4, 1), 103.0),
        ]
        _seed(db_session, PRIMARY_SERIES_ID, points)

        result = InflationMonitorService().get_result(db_session)

        assert result.underlying_momentum.calculation_period == date(2024, 4, 1)
        expected_r3m = ((103.0 / 100.0) ** 4 - 1) * 100
        assert result.underlying_momentum.r_3m_annualized == expected_r3m


class TestLatestValidResolutionThroughRepository:
    def test_latest_observation_can_differ_from_latest_valid_state_period(self, db_session):
        points = FULL_HISTORY + [(date(2025, 2, 1), 111.0)]
        # 2025-02's t-12 (2024-02) is never persisted -> INSUFFICIENT_DATA there.
        points = [p for p in points if p[0] != date(2024, 2, 1)]
        _seed(db_session, PRIMARY_SERIES_ID, points)

        result = InflationMonitorService().get_result(db_session)

        assert result.underlying_momentum.latest_observation_period == date(2025, 2, 1)
        assert result.underlying_momentum.latest_valid_state_period == date(2025, 1, 1)
        assert result.underlying_momentum.calculation_period == date(2025, 1, 1)


class TestCommonPeriodResolutionThroughRepository:
    def test_confirmation_falls_back_to_earlier_common_period(self, db_session):
        _seed(db_session, PRIMARY_SERIES_ID, LONG_HISTORY)
        # Core CPI: identical dates, but its 2025-01 t-12 (2024-01) is
        # never persisted -- confirmation must fall back to 2024-12,
        # not silently use 2025-01 nor give up entirely.
        cpi_points = [(d, 50.0 + i * 0.2) for i, (d, _) in enumerate(LONG_HISTORY) if d != date(2024, 1, 1)]
        _seed(db_session, CONFIRMATION_SERIES_ID, cpi_points)

        result = InflationMonitorService().get_result(db_session)

        assert result.confirmation.latest_common_period == date(2024, 12, 1)
        assert result.confirmation.relationship in ("CONFIRMS", "DIVERGES", "INCONCLUSIVE")
        assert result.coverage.confirmation_available is True

    def test_cpi_standalone_valid_but_no_common_period_reports_unavailable_coverage(self, db_session):
        """The exact real scenario confirmation_available's original,
        incorrect definition ("Core CPI's own state is calculable")
        got wrong: Core CPI has abundant, fully valid history of its
        own, but it shares NO observation dates with Core PCE, so no
        same-period comparison -- and therefore no confirmation TIER
        result -- is possible. confirmation_available must be False
        here even though Core CPI's own standalone state is not."""
        _seed(db_session, PRIMARY_SERIES_ID, LONG_HISTORY)
        disjoint_cpi_points = [
            (date(2010, 1, 1), 50.0),
            (date(2010, 7, 1), 51.0),
            (date(2010, 10, 1), 52.0),
            (date(2011, 1, 1), 53.0),
        ]
        _seed(db_session, CONFIRMATION_SERIES_ID, disjoint_cpi_points)

        result = InflationMonitorService().get_result(db_session)

        assert result.confirmation.confirmation_latest.state != "INSUFFICIENT_DATA"
        assert result.confirmation.latest_common_period is None
        assert result.confirmation.relationship == "UNAVAILABLE"
        assert result.coverage.confirmation_available is False


class TestMissingDataThroughRepository:
    def test_null_observation_value_propagates_as_insufficient_data_not_a_crash(self, db_session):
        points = LONG_HISTORY[:-1] + [(date(2025, 1, 1), None)]  # latest month's value itself is null
        _seed(db_session, PRIMARY_SERIES_ID, points)

        result = InflationMonitorService().get_result(db_session)

        # A row DOES exist at 2025-01 (a persisted observation, per FRED's own
        # "." convention) -- latest_observation_period must reflect that row's
        # date even though its value is unusable, never silently fall back to
        # an earlier date as if the row didn't exist at all.
        assert result.underlying_momentum.latest_observation_period == date(2025, 1, 1)
        # But 2025-01's null value means it cannot be a calculation period;
        # falls back to 2024-12 (last period with a valid value AND full history).
        assert result.underlying_momentum.latest_valid_state_period == date(2024, 12, 1)
        assert result.underlying_momentum.calculation_period == date(2024, 12, 1)
        assert result.underlying_momentum.state != "INSUFFICIENT_DATA"


class TestNonMutation:
    def test_get_result_does_not_modify_persisted_observations(self, db_session):
        _seed(db_session, PRIMARY_SERIES_ID, FULL_HISTORY)
        _seed(db_session, CONFIRMATION_SERIES_ID, FULL_HISTORY)
        _seed(db_session, TARGET_SERIES_ID, FULL_HISTORY)
        _seed(db_session, HEADLINE_CPI_SERIES_ID, FULL_HISTORY)

        repo = SeriesRepository(db_session)
        series = repo.get_series_by_series_id(PRIMARY_SERIES_ID)
        before, _ = repo.get_observations(series.id, None, None, limit=100, offset=0, order="asc")
        before_values = [(o.observation_date, o.value) for o in before]

        InflationMonitorService().get_result(db_session)
        InflationMonitorService().get_result(db_session)  # twice, to also prove no side effect accumulates

        after, _ = repo.get_observations(series.id, None, None, limit=100, offset=0, order="asc")
        after_values = [(o.observation_date, o.value) for o in after]
        assert before_values == after_values

    def test_repeated_calls_are_deterministic(self, db_session):
        _seed(db_session, PRIMARY_SERIES_ID, FULL_HISTORY)
        _seed(db_session, CONFIRMATION_SERIES_ID, FULL_HISTORY)
        _seed(db_session, TARGET_SERIES_ID, FULL_HISTORY)
        _seed(db_session, HEADLINE_CPI_SERIES_ID, FULL_HISTORY)

        service = InflationMonitorService()
        result_1 = service.get_result(db_session)
        result_2 = service.get_result(db_session)
        assert result_1 == result_2
