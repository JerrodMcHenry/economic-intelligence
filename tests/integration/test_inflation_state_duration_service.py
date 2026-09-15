"""Integration tests for InflationMonitorService.get_state_duration_result
against a real, isolated PostgreSQL test database -- contract
`docs/product/state-duration-v1.md`. No FastAPI, no OpenAI, no FRED.

These tests exist to prove the SERVICE correctly composes persistence
(SeriesRepository), `compute_series_momentum`/`compute_series_momentum_at`
(app.domain.inflation, unmodified), and the pure sequence helper
(app.domain.state_duration) -- something neither
tests/test_domain_state_duration.py (pure, no database, hand-built
sequences) nor tests/test_domain_inflation.py (pure classification,
no duration concept) can prove on its own. Every fixture below is
hand-constructed so the expected `duration_months`/`boundary_type`
is derivable by hand, not merely reproduced by calling the same code
under test.
"""

from datetime import date

from app.domain.inflation import month_before
from app.models.inflation import (
    CONFIRMATION_SERIES_ID,
    HEADLINE_CPI_SERIES_ID,
    PRIMARY_SERIES_ID,
    TARGET_SERIES_ID,
)
from app.models.series import Observation, SeriesResponse
from app.repositories.series_repository import SeriesRepository
from app.services.inflation import InflationMonitorService

T = date(2026, 1, 1)


def _flat_history(anchor: date, months: int, value: float = 100.0, skip: set[date] | None = None) -> list[tuple[date, float]]:
    """`months` consecutive flat-valued months ending at (and including)
    `anchor`, walking backward via `month_before` -- zero real growth,
    so every reconstructed period's r_3m/r_6m/r_12m are all exactly 0,
    well within any nonzero neutral band -> STABLE at every period,
    unless a `skip`ped date breaks a required endpoint somewhere."""
    skip = skip or set()
    return [(month_before(anchor, n), value) for n in range(months) if month_before(anchor, n) not in skip]


def _seed(db_session, series_id: str, points: list[tuple[date, float]]) -> None:
    SeriesRepository(db_session).save_series(
        SeriesResponse(series_id=series_id, title=series_id, units="Index", observations=[Observation(date=d, value=v) for d, v in points])
    )
    db_session.flush()


class TestExactBoundary:
    def test_a_single_month_spike_produces_a_one_month_exact_run(self, db_session):
        """Hand-verified: flat (100.0) at every month strictly before
        `T`, with a one-time level jump AT `T` itself (100.0 -> 130.0).
        r_3m(T) = ((130/100)**4 - 1)*100 ~= 185.6, r_6m(T) ~= 69.0,
        r_12m(T) = 30.0 -> both r_3m/r_6m far above `r_12m + 0.10` ->
        HEATING at T. One month back (T-1), the entire trailing 12-month
        window is flat pre-jump -> r_3m=r_6m=r_12m=0 -> STABLE, a real,
        differing, non-INSUFFICIENT_DATA state -> EXACT, duration=1."""
        points = _flat_history(month_before(T, 1), 30, value=100.0)
        points.append((T, 130.0))
        _seed(db_session, PRIMARY_SERIES_ID, points)

        result = InflationMonitorService().get_state_duration_result(db_session)

        assert result.status == "AVAILABLE"
        assert result.state == "HEATING"
        assert result.evaluation_period == T
        assert result.duration_months == 1
        assert result.earliest_confirmed_period == T
        assert result.boundary_type == "EXACT"
        assert result.previous_state == "STABLE"
        assert result.previous_period == month_before(T, 1)


class TestDataBounded:
    def test_a_historical_gap_stops_the_walk_at_the_correct_month(self, db_session):
        """Hand-verified: flat (100.0) from 2019-01 through T=2026-01,
        OMITTING 2024-05-01 entirely. Periods T..T-7 (2026-01..2025-06)
        never need 2024-05 as an r_3m/r_6m/r_12m endpoint (their own
        t-3/t-6/t-12 all land elsewhere) -> STABLE, matching. At T-8
        (2025-05), r_12m's own endpoint (2025-05 minus 12 = 2024-05) is
        the missing month -> r_12m unavailable -> INSUFFICIENT_DATA ->
        DATA_BOUNDED, duration_months=8 (T through T-7 inclusive)."""
        missing = date(2024, 5, 1)
        points = _flat_history(T, 85, value=100.0, skip={missing})
        _seed(db_session, PRIMARY_SERIES_ID, points)

        result = InflationMonitorService().get_state_duration_result(db_session)

        assert result.status == "AVAILABLE"
        assert result.state == "STABLE"
        assert result.duration_months == 8
        assert result.earliest_confirmed_period == month_before(T, 7)
        assert result.boundary_type == "DATA_BOUNDED"
        assert result.previous_state is None
        assert result.previous_period is None

    def test_gap_is_never_bridged_past(self, db_session):
        """A real STABLE month reappears further back than the gap
        (2024-01, well beyond 2024-05) -- the walk must not bridge past
        the gap to reach it; duration stays exactly what it was at the
        gap boundary."""
        missing = date(2024, 5, 1)
        points = _flat_history(T, 85, value=100.0, skip={missing})
        _seed(db_session, PRIMARY_SERIES_ID, points)

        result = InflationMonitorService().get_state_duration_result(db_session)
        assert result.boundary_type == "DATA_BOUNDED"
        assert result.duration_months == 8  # not 85 or anything reaching back past the gap


class TestLookbackBounded:
    def test_a_uniform_run_longer_than_the_bound_is_lookback_bounded_at_exactly_sixty(self, db_session):
        """80 consecutive flat months (well past the 60-month bound,
        with enough additional trailing history that period T-59 itself
        still has a full, valid 12-month window) -> every one of the 60
        examined periods is STABLE -> LOOKBACK_BOUNDED, duration=60."""
        points = _flat_history(T, 80, value=100.0)
        _seed(db_session, PRIMARY_SERIES_ID, points)

        result = InflationMonitorService().get_state_duration_result(db_session)

        assert result.status == "AVAILABLE"
        assert result.state == "STABLE"
        assert result.duration_months == 60
        assert result.boundary_type == "LOOKBACK_BOUNDED"
        assert result.earliest_confirmed_period == month_before(T, 59)
        assert result.previous_state is None
        assert result.previous_period is None


class TestCurrentInsufficient:
    def test_nothing_persisted_at_all(self, db_session):
        result = InflationMonitorService().get_state_duration_result(db_session)
        assert result.status == "CURRENT_INSUFFICIENT"
        assert result.methodology_id == "inflation_v1.0"
        assert result.data_basis == "latest_revised_data"

    def test_insufficient_trailing_history_at_the_only_persisted_month(self, db_session):
        """A single observation, nowhere near enough for any r_3m/
        r_6m/r_12m endpoint -> current state itself is
        INSUFFICIENT_DATA -> CURRENT_INSUFFICIENT, no duration."""
        _seed(db_session, PRIMARY_SERIES_ID, [(T, 100.0)])
        result = InflationMonitorService().get_state_duration_result(db_session)
        assert result.status == "CURRENT_INSUFFICIENT"


class TestScopeIsolation:
    def test_duration_reads_only_underlying_momentum_never_confirmation_target_headline(self, db_session):
        """Frozen §24: Confirmation's/Target's/Headline's own
        availability must never affect the computed duration. Same
        Core PCE history, computed once with none of the other three
        series persisted, once with all three fully persisted and
        valid -- the duration result must be byte-identical."""
        points = _flat_history(T, 80, value=100.0)
        _seed(db_session, PRIMARY_SERIES_ID, points)

        without_others = InflationMonitorService().get_state_duration_result(db_session)

        _seed(db_session, CONFIRMATION_SERIES_ID, points)
        _seed(db_session, TARGET_SERIES_ID, points)
        _seed(db_session, HEADLINE_CPI_SERIES_ID, points)

        with_others = InflationMonitorService().get_state_duration_result(db_session)

        assert without_others.model_dump() == with_others.model_dump()


class TestRevisionEffect:
    def test_a_persisted_revision_changes_the_reconstructed_duration(self, db_session):
        """Frozen §26: expected, not a defect. Seed a flat history
        (LOOKBACK_BOUNDED, duration=60); revise one recent month to
        introduce a real state change; a second call reflects the new
        reconstruction."""
        points = _flat_history(T, 80, value=100.0)
        _seed(db_session, PRIMARY_SERIES_ID, points)
        before = InflationMonitorService().get_state_duration_result(db_session)
        assert before.boundary_type == "LOOKBACK_BOUNDED"

        revised = [(d, (130.0 if d == T else v)) for d, v in points]
        _seed(db_session, PRIMARY_SERIES_ID, revised)
        after = InflationMonitorService().get_state_duration_result(db_session)

        assert after.state == "HEATING"
        assert after.boundary_type == "EXACT"
        assert after.duration_months == 1
        assert before.model_dump() != after.model_dump()


class TestContractFields:
    def test_methodology_id_data_basis_history_type_on_available_response(self, db_session):
        points = _flat_history(T, 80, value=100.0)
        _seed(db_session, PRIMARY_SERIES_ID, points)
        result = InflationMonitorService().get_state_duration_result(db_session)
        assert result.methodology_id == "inflation_v1.0"
        assert result.data_basis == "latest_revised_data"
        assert result.history_type == "latest_revised_reconstruction"

    def test_methodology_id_data_basis_on_current_insufficient_response(self, db_session):
        result = InflationMonitorService().get_state_duration_result(db_session)
        assert result.methodology_id == "inflation_v1.0"
        assert result.data_basis == "latest_revised_data"
        assert not hasattr(result, "duration_months")


class TestDeterminismAndNonMutation:
    def test_repeated_calls_are_deterministic(self, db_session):
        points = _flat_history(T, 80, value=100.0)
        _seed(db_session, PRIMARY_SERIES_ID, points)
        service = InflationMonitorService()
        result_1 = service.get_state_duration_result(db_session)
        result_2 = service.get_state_duration_result(db_session)
        assert result_1.model_dump() == result_2.model_dump()

    def test_does_not_modify_persisted_observations(self, db_session):
        from app.db.models import EconomicObservation, EconomicSeries

        points = _flat_history(T, 80, value=100.0)
        _seed(db_session, PRIMARY_SERIES_ID, points)

        series_count_before = db_session.query(EconomicSeries).count()
        observation_count_before = db_session.query(EconomicObservation).count()

        service = InflationMonitorService()
        service.get_state_duration_result(db_session)
        service.get_state_duration_result(db_session)

        assert db_session.query(EconomicSeries).count() == series_count_before
        assert db_session.query(EconomicObservation).count() == observation_count_before
