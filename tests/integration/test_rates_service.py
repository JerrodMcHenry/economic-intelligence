"""Integration tests for the Rates domain against a real, isolated
PostgreSQL test database (Increment #29).

Covers what a pure-domain unit test cannot: that `RatesRepository`
persists idempotently and records real provenance, that revisions are
detected and counted, and that `RatesMonitorService` composes real
database reads with the pure domain layer -- including every
unavailability path (series absent, history too short, no exactly
shared date between a derived metric's two inputs).

No FastAPI, no network: the ingestion service is driven with a stub
Treasury client so the upstream boundary stays mocked while every
database interaction below it is real.
"""

from datetime import date, datetime, timezone

import pytest

from app.clients.treasury import NOMINAL_DATASET, REAL_DATASET, TreasuryRateRow, TreasuryTimeoutError
from app.db.models import RatesIngestionRun
from app.models.rates import (
    NOMINAL_10Y_SERIES_ID,
    NOMINAL_2Y_SERIES_ID,
    NOMINAL_30Y_SERIES_ID,
    NOMINAL_5Y_SERIES_ID,
    PROVIDER,
    REAL_10Y_SERIES_ID,
    REAL_5Y_SERIES_ID,
    SERIES_TITLES,
    SERIES_UNITS,
)
from app.repositories.rates_repository import ProvenanceRecord, RatesRepository
from app.services.rates import RatesMonitorService
from app.services.rates_ingestion import RatesIngestionService

RETRIEVED_AT = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)


def _provenance(dataset: str = NOMINAL_DATASET, field: str = "BC_10YEAR", retrieved_at: datetime = RETRIEVED_AT):
    return ProvenanceRecord(
        provider=PROVIDER,
        dataset=dataset,
        source_series_field=field,
        source_url=f"https://home.treasury.gov/...?data={dataset}",
        retrieved_at=retrieved_at,
    )


def _seed(session, series_id: str, points: list[tuple[date, float]], dataset: str = NOMINAL_DATASET) -> None:
    repo = RatesRepository(session)
    series = repo.ensure_series(series_id, SERIES_TITLES[series_id], SERIES_UNITS, PROVIDER)
    for observation_date, value in points:
        repo.upsert_observation(series, observation_date, value, _provenance(dataset))
    session.flush()


def _sessions(count: int, start_day: int = 1) -> list[date]:
    """`count` consecutive weekday-ish dates. Calendar spacing is
    irrelevant to the methodology (windows count observations), which
    these tests rely on deliberately."""
    return [date(2026, 6, start_day + offset) for offset in range(count)]


class StubTreasuryClient:
    """Returns canned rows per dataset; records the calls it received."""

    def __init__(self, rows_by_dataset: dict[str, list[TreasuryRateRow]], fail_datasets: set[str] | None = None):
        self._rows = rows_by_dataset
        self._fail = fail_datasets or set()
        self.calls: list[tuple[str, int, int]] = []

    def get_month(self, dataset: str, year: int, month: int) -> list[TreasuryRateRow]:
        self.calls.append((dataset, year, month))
        if dataset in self._fail:
            raise TreasuryTimeoutError("stub timeout")
        # The stub ignores the month filter: it returns its canned rows
        # on the first call for a dataset and nothing afterwards, so a
        # multi-month sync does not duplicate the same rows.
        rows = self._rows.get(dataset, [])
        self._rows[dataset] = []
        return rows


class TestRepositoryPersistence:
    def test_first_ingestion_inserts_and_records_provenance(self, db_session):
        repo = RatesRepository(db_session)
        series = repo.ensure_series(NOMINAL_10Y_SERIES_ID, "10Y", "Percent", PROVIDER)

        outcome = repo.upsert_observation(series, date(2026, 6, 1), 5.01, _provenance())
        db_session.flush()

        assert outcome == "INSERTED"
        provenance = repo.get_provenance(NOMINAL_10Y_SERIES_ID, date(2026, 6, 1))
        assert provenance is not None
        assert provenance.provider == PROVIDER
        assert provenance.dataset == NOMINAL_DATASET
        assert provenance.source_series_field == "BC_10YEAR"
        assert provenance.source_url.startswith("https://home.treasury.gov/")
        assert provenance.retrieved_at == RETRIEVED_AT
        assert provenance.first_seen_at == RETRIEVED_AT
        assert provenance.revision_count == 0
        assert provenance.last_revised_at is None

    def test_reingesting_the_same_value_is_idempotent(self, db_session):
        repo = RatesRepository(db_session)
        series = repo.ensure_series(NOMINAL_10Y_SERIES_ID, "10Y", "Percent", PROVIDER)
        repo.upsert_observation(series, date(2026, 6, 1), 5.01, _provenance())
        db_session.flush()

        later = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
        outcome = repo.upsert_observation(series, date(2026, 6, 1), 5.01, _provenance(retrieved_at=later))
        db_session.flush()

        assert outcome == "UNCHANGED"
        assert len(repo.get_observations(NOMINAL_10Y_SERIES_ID)) == 1
        provenance = repo.get_provenance(NOMINAL_10Y_SERIES_ID, date(2026, 6, 1))
        # Retrieval time advances; revision history does not inflate.
        assert provenance.retrieved_at == later
        assert provenance.revision_count == 0
        assert provenance.last_revised_at is None

    def test_a_genuinely_changed_value_is_recorded_as_a_revision(self, db_session):
        repo = RatesRepository(db_session)
        series = repo.ensure_series(NOMINAL_10Y_SERIES_ID, "10Y", "Percent", PROVIDER)
        repo.upsert_observation(series, date(2026, 6, 1), 5.01, _provenance())
        db_session.flush()

        later = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
        outcome = repo.upsert_observation(series, date(2026, 6, 1), 5.03, _provenance(retrieved_at=later))
        db_session.flush()

        assert outcome == "REVISED"
        observations = repo.get_observations(NOMINAL_10Y_SERIES_ID)
        assert len(observations) == 1 and observations[0].value == 5.03
        provenance = repo.get_provenance(NOMINAL_10Y_SERIES_ID, date(2026, 6, 1))
        assert provenance.revision_count == 1
        assert provenance.last_revised_at == later
        assert provenance.first_seen_at == RETRIEVED_AT

    def test_provenance_is_absent_for_an_uningested_observation(self, db_session):
        assert RatesRepository(db_session).get_provenance(NOMINAL_10Y_SERIES_ID, date(2026, 6, 1)) is None

    def test_unknown_series_reads_as_empty_not_an_error(self, db_session):
        assert RatesRepository(db_session).get_observations(NOMINAL_30Y_SERIES_ID) == []


class TestIngestionService:
    def test_successful_sync_persists_both_datasets_with_counts(self, db_session):
        client = StubTreasuryClient(
            {
                NOMINAL_DATASET: [
                    TreasuryRateRow(date(2026, 6, 1), {"BC_2YEAR": 4.7, "BC_5YEAR": 4.8, "BC_10YEAR": 5.0, "BC_30YEAR": 5.3}),
                    TreasuryRateRow(date(2026, 6, 2), {"BC_2YEAR": 4.8, "BC_5YEAR": 4.9, "BC_10YEAR": 5.1, "BC_30YEAR": 5.4}),
                ],
                REAL_DATASET: [
                    TreasuryRateRow(date(2026, 6, 1), {"TC_5YEAR": 2.5, "TC_10YEAR": 2.6}),
                    TreasuryRateRow(date(2026, 6, 2), {"TC_5YEAR": 2.55, "TC_10YEAR": 2.65}),
                ],
            }
        )

        result = RatesIngestionService(client).sync(db_session, lookback_months=1)
        db_session.flush()

        assert result.status == "SUCCEEDED"
        assert result.datasets_failed == []
        assert sum(item.observations_inserted for item in result.series) == 12
        assert RatesRepository(db_session).get_observations(NOMINAL_10Y_SERIES_ID)[0].value == 5.0
        assert len(RatesRepository(db_session).get_observations(REAL_5Y_SERIES_ID)) == 2

    def test_rerunning_an_identical_sync_inserts_nothing(self, db_session):
        rows = {
            NOMINAL_DATASET: [TreasuryRateRow(date(2026, 6, 1), {"BC_10YEAR": 5.0})],
            REAL_DATASET: [],
        }
        RatesIngestionService(StubTreasuryClient(dict(rows))).sync(db_session, lookback_months=1)
        db_session.flush()

        second = RatesIngestionService(StubTreasuryClient(dict(rows))).sync(db_session, lookback_months=1)
        db_session.flush()

        assert sum(item.observations_inserted for item in second.series) == 0
        assert sum(item.observations_revised for item in second.series) == 0
        assert len(RatesRepository(db_session).get_observations(NOMINAL_10Y_SERIES_ID)) == 1

    def test_one_dataset_failing_does_not_discard_the_other(self, db_session):
        client = StubTreasuryClient(
            {NOMINAL_DATASET: [TreasuryRateRow(date(2026, 6, 1), {"BC_10YEAR": 5.0})]},
            fail_datasets={REAL_DATASET},
        )

        result = RatesIngestionService(client).sync(db_session, lookback_months=1)
        db_session.flush()

        assert result.status == "PARTIAL_FAILURE"
        assert result.datasets_failed == [REAL_DATASET]
        assert len(RatesRepository(db_session).get_observations(NOMINAL_10Y_SERIES_ID)) == 1

    def test_total_upstream_failure_is_recorded_as_a_failed_run(self, db_session):
        client = StubTreasuryClient({}, fail_datasets={NOMINAL_DATASET, REAL_DATASET})

        result = RatesIngestionService(client).sync(db_session, lookback_months=1)
        db_session.flush()

        assert result.status == "FAILED"
        assert set(result.datasets_failed) == {NOMINAL_DATASET, REAL_DATASET}
        run = db_session.query(RatesIngestionRun).one()
        assert run.status == "FAILED"
        assert run.error_class == "TreasuryTimeoutError"
        assert run.observations_inserted == 0

    def test_every_run_is_recorded_for_diagnosis(self, db_session):
        client = StubTreasuryClient({NOMINAL_DATASET: [TreasuryRateRow(date(2026, 6, 1), {"BC_10YEAR": 5.0})]})
        RatesIngestionService(client).sync(db_session, lookback_months=1)
        db_session.flush()

        run = db_session.query(RatesIngestionRun).one()
        assert run.provider == PROVIDER
        assert run.status == "SUCCEEDED"
        assert run.observations_received == 1
        assert run.observations_inserted == 1
        assert run.duration_ms >= 0
        assert run.error_class is None

    def test_missing_field_for_a_session_is_skipped_never_zero_filled(self, db_session):
        client = StubTreasuryClient(
            {NOMINAL_DATASET: [TreasuryRateRow(date(2026, 6, 1), {"BC_10YEAR": 5.0})]}  # no 2Y/5Y/30Y
        )
        RatesIngestionService(client).sync(db_session, lookback_months=1)
        db_session.flush()

        assert RatesRepository(db_session).get_observations(NOMINAL_2Y_SERIES_ID) == []

    def test_lookback_months_is_validated(self, db_session):
        client = StubTreasuryClient({})
        with pytest.raises(ValueError):
            RatesIngestionService(client).sync(db_session, lookback_months=0)

    def test_requested_months_cover_the_lookback_window(self, db_session):
        client = StubTreasuryClient({})
        RatesIngestionService(client).sync(db_session, lookback_months=3, as_of=date(2026, 1, 15))
        db_session.flush()

        nominal_calls = [call for call in client.calls if call[0] == NOMINAL_DATASET]
        assert nominal_calls == [(NOMINAL_DATASET, 2025, 11), (NOMINAL_DATASET, 2025, 12), (NOMINAL_DATASET, 2026, 1)]


class TestMonitorService:
    def test_empty_database_reports_every_component_unavailable(self, db_session):
        result = RatesMonitorService().get_result(db_session)

        assert result.methodology_id == "rates_v1.0"
        assert result.as_of_date is None
        assert all(level.available is False for level in result.nominal_curve)
        assert all(spread.available is False for spread in result.curve_spreads)
        assert all(item.available is False for item in result.inflation_compensation)
        assert result.curve_spreads[0].unavailable_reason == "NO_OBSERVATIONS_FOR_EITHER_SERIES"

    def test_levels_changes_and_context_from_persisted_data(self, db_session):
        days = _sessions(10)
        _seed(db_session, NOMINAL_10Y_SERIES_ID, [(day, 5.00 + index * 0.01) for index, day in enumerate(days)])

        result = RatesMonitorService().get_result(db_session)
        ten_year = next(level for level in result.nominal_curve if level.series_id == NOMINAL_10Y_SERIES_ID)

        assert ten_year.available is True
        assert ten_year.latest_value == pytest.approx(5.09)
        assert ten_year.latest_date == days[-1]
        one_session = next(change for change in ten_year.changes if change.window == "1_SESSION")
        assert one_session.change_basis_points == pytest.approx(1.0)
        five_session = next(change for change in ten_year.changes if change.window == "5_SESSIONS")
        assert five_session.change_basis_points == pytest.approx(5.0)
        assert ten_year.historical_context.available is True
        assert ten_year.historical_context.observation_count == 4
        assert ten_year.provenance is not None
        assert ten_year.provenance.provider == PROVIDER

    def test_insufficient_history_reports_unavailable_windows_not_zero(self, db_session):
        _seed(db_session, NOMINAL_10Y_SERIES_ID, [(date(2026, 6, 1), 5.0), (date(2026, 6, 2), 5.1)])

        result = RatesMonitorService().get_result(db_session)
        ten_year = next(level for level in result.nominal_curve if level.series_id == NOMINAL_10Y_SERIES_ID)

        assert next(c for c in ten_year.changes if c.window == "1_SESSION").available is True
        for window in ("5_SESSIONS", "21_SESSIONS", "63_SESSIONS"):
            change = next(c for c in ten_year.changes if c.window == window)
            assert change.available is False
            assert change.change_basis_points is None

    def test_curve_spread_is_computed_server_side(self, db_session):
        days = _sessions(3)
        _seed(db_session, NOMINAL_2Y_SERIES_ID, [(day, 4.76) for day in days])
        _seed(db_session, NOMINAL_10Y_SERIES_ID, [(day, 5.01) for day in days])

        result = RatesMonitorService().get_result(db_session)
        spread = next(item for item in result.curve_spreads if item.spread_id == "2s10s")

        assert spread.available is True
        assert spread.kind == "DERIVED"
        assert spread.spread_basis_points == pytest.approx(25.0)
        assert spread.long_value == 5.01 and spread.short_value == 4.76
        assert spread.provenance is not None
        assert spread.provenance.methodology_id == "rates_v1.0"
        assert spread.provenance.input_series_ids == [NOMINAL_10Y_SERIES_ID, NOMINAL_2Y_SERIES_ID]

    def test_inflation_compensation_is_computed_server_side(self, db_session):
        days = _sessions(3)
        _seed(db_session, NOMINAL_10Y_SERIES_ID, [(day, 5.01) for day in days])
        _seed(db_session, REAL_10Y_SERIES_ID, [(day, 2.68) for day in days], dataset=REAL_DATASET)

        result = RatesMonitorService().get_result(db_session)
        compensation = next(item for item in result.inflation_compensation if item.maturity == "10Y")

        assert compensation.available is True
        assert compensation.kind == "DERIVED"
        assert compensation.compensation_percent == pytest.approx(2.33)
        assert compensation.nominal_value == 5.01 and compensation.real_value == 2.68

    def test_non_overlapping_dates_report_an_explicit_alignment_failure(self, db_session):
        """The nominal side has Monday, the real side only Tuesday. The
        honest answer is "no shared date", never a cross-date subtraction."""
        _seed(db_session, NOMINAL_10Y_SERIES_ID, [(date(2026, 6, 1), 5.01)])
        _seed(db_session, REAL_10Y_SERIES_ID, [(date(2026, 6, 2), 2.68)], dataset=REAL_DATASET)

        result = RatesMonitorService().get_result(db_session)
        compensation = next(item for item in result.inflation_compensation if item.maturity == "10Y")

        assert compensation.available is False
        assert compensation.compensation_percent is None
        assert compensation.unavailable_reason == "NO_EXACTLY_SHARED_OBSERVATION_DATE"

    def test_one_missing_side_is_distinguished_from_no_data_at_all(self, db_session):
        _seed(db_session, NOMINAL_5Y_SERIES_ID, [(date(2026, 6, 1), 4.86)])

        result = RatesMonitorService().get_result(db_session)
        compensation = next(item for item in result.inflation_compensation if item.maturity == "5Y")

        assert compensation.unavailable_reason == "NO_OBSERVATIONS_FOR_ONE_SERIES"

    def test_as_of_date_is_the_latest_observed_session(self, db_session):
        _seed(db_session, NOMINAL_2Y_SERIES_ID, [(date(2026, 6, 1), 4.7)])
        _seed(db_session, NOMINAL_10Y_SERIES_ID, [(date(2026, 6, 3), 5.0)])

        assert RatesMonitorService().get_result(db_session).as_of_date == date(2026, 6, 3)

    def test_result_is_deterministic_for_a_fixed_database_state(self, db_session):
        days = _sessions(8)
        _seed(db_session, NOMINAL_10Y_SERIES_ID, [(day, 5.00 + index * 0.02) for index, day in enumerate(days)])

        first = RatesMonitorService().get_result(db_session)
        second = RatesMonitorService().get_result(db_session)

        # `calculated_at` on derived provenance is a real clock read, so
        # compare the economic content, which must be identical.
        assert first.nominal_curve == second.nominal_curve
        assert first.as_of_date == second.as_of_date
