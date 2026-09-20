"""HTTP contract tests for the Rates routes (Increment #29).

Exercises the real ASGI app end to end against the isolated test
database: `GET /api/v1/monitors/rates` (read-only, never upstream) and
`POST /api/v1/rates/sync` (explicit ingestion, Treasury client mocked at
the client-method boundary -- never a real network call).

The contract these tests protect is the one the frontend depends on:
every financial quantity arrives already computed, and every
unavailability is explicit rather than implied by a zero.
"""

from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.clients.treasury import NOMINAL_DATASET, REAL_DATASET, TreasuryClient, TreasuryRateRow, TreasuryTimeoutError
from app.models.rates import (
    NOMINAL_10Y_SERIES_ID,
    NOMINAL_2Y_SERIES_ID,
    PROVIDER,
    REAL_10Y_SERIES_ID,
    SERIES_TITLES,
    SERIES_UNITS,
)
from app.repositories.rates_repository import ProvenanceRecord, RatesRepository

RATES_URL = "/api/v1/monitors/rates"
SYNC_URL = "/api/v1/rates/sync"


@pytest.fixture(autouse=True)
def _clean_ingestion_runs(test_database_url: str):
    """`seed_session`'s TRUNCATE cascades from economic_series, which
    reaches observation_provenance but not the standalone ingestion-run
    audit table -- cleaned here so run-count assertions stay isolated."""
    yield
    engine = create_engine(test_database_url)
    with Session(bind=engine) as session:
        session.execute(text("TRUNCATE TABLE rates_ingestion_runs RESTART IDENTITY"))
        session.commit()
    engine.dispose()


def _seed(seed_session, series_id: str, points: list[tuple[date, float]], dataset: str = NOMINAL_DATASET) -> None:
    repo = RatesRepository(seed_session)
    series = repo.ensure_series(series_id, SERIES_TITLES[series_id], SERIES_UNITS, PROVIDER)
    for observation_date, value in points:
        repo.upsert_observation(
            series,
            observation_date,
            value,
            ProvenanceRecord(
                provider=PROVIDER,
                dataset=dataset,
                source_series_field="BC_10YEAR" if dataset == NOMINAL_DATASET else "TC_10YEAR",
                source_url=f"https://home.treasury.gov/...?data={dataset}",
                retrieved_at=datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc),
            ),
        )
    seed_session.commit()


class TestGetRatesMonitor:
    def test_empty_database_returns_200_with_explicit_unavailability(self, client):
        response = client.get(RATES_URL)

        assert response.status_code == 200
        body = response.json()
        assert body["methodology_id"] == "rates_v1.0"
        assert body["provider"] == "TREASURY"
        assert body["as_of_date"] is None
        assert all(level["available"] is False for level in body["nominal_curve"])
        assert all(item["available"] is False for item in body["inflation_compensation"])

    def test_response_exposes_the_full_canonical_set(self, client):
        body = client.get(RATES_URL).json()

        assert [level["series_id"] for level in body["nominal_curve"]] == [
            "UST_NOMINAL_2Y",
            "UST_NOMINAL_5Y",
            "UST_NOMINAL_10Y",
            "UST_NOMINAL_30Y",
        ]
        assert [level["series_id"] for level in body["real_curve"]] == ["UST_REAL_5Y", "UST_REAL_10Y"]
        assert [spread["spread_id"] for spread in body["curve_spreads"]] == ["2s10s", "2s30s"]
        assert [item["maturity"] for item in body["inflation_compensation"]] == ["5Y", "10Y"]

    def test_computed_values_arrive_ready_for_display(self, client, seed_session):
        """The frontend must never have to subtract, convert to basis
        points, or rank anything -- every one of those arrives done."""
        days = [date(2026, 6, day) for day in range(1, 8)]
        _seed(seed_session, NOMINAL_2Y_SERIES_ID, [(day, 4.70 + i * 0.01) for i, day in enumerate(days)])
        _seed(seed_session, NOMINAL_10Y_SERIES_ID, [(day, 5.00 + i * 0.02) for i, day in enumerate(days)])
        _seed(seed_session, REAL_10Y_SERIES_ID, [(day, 2.60) for day in days], dataset=REAL_DATASET)

        body = client.get(RATES_URL).json()

        ten_year = next(level for level in body["nominal_curve"] if level["series_id"] == NOMINAL_10Y_SERIES_ID)
        assert ten_year["available"] is True
        assert ten_year["latest_value"] == pytest.approx(5.12)
        assert ten_year["kind"] == "SOURCE_OBSERVATION"
        assert next(c for c in ten_year["changes"] if c["window"] == "1_SESSION")["change_basis_points"] == pytest.approx(2.0)
        assert next(c for c in ten_year["changes"] if c["window"] == "5_SESSIONS")["change_basis_points"] == pytest.approx(10.0)

        spread = next(item for item in body["curve_spreads"] if item["spread_id"] == "2s10s")
        assert spread["kind"] == "DERIVED"
        assert spread["spread_basis_points"] == pytest.approx(36.0)  # 5.12 - 4.76 = 0.36pp

        compensation = next(item for item in body["inflation_compensation"] if item["maturity"] == "10Y")
        assert compensation["compensation_percent"] == pytest.approx(2.52)
        assert compensation["kind"] == "DERIVED"

    def test_source_observations_carry_provenance(self, client, seed_session):
        _seed(seed_session, NOMINAL_10Y_SERIES_ID, [(date(2026, 6, 1), 5.01)])

        body = client.get(RATES_URL).json()
        ten_year = next(level for level in body["nominal_curve"] if level["series_id"] == NOMINAL_10Y_SERIES_ID)

        provenance = ten_year["provenance"]
        assert provenance["provider"] == "TREASURY"
        assert provenance["dataset"] == NOMINAL_DATASET
        assert provenance["source_url"].startswith("https://home.treasury.gov/")
        assert provenance["observation_date"] == "2026-06-01"
        assert provenance["revision_count"] == 0

    def test_derived_metrics_carry_methodology_provenance_not_source_provenance(self, client, seed_session):
        """A derived value must never masquerade as a directly sourced
        observation: its provenance names the methodology and inputs."""
        _seed(seed_session, NOMINAL_2Y_SERIES_ID, [(date(2026, 6, 1), 4.76)])
        _seed(seed_session, NOMINAL_10Y_SERIES_ID, [(date(2026, 6, 1), 5.01)])

        spread = next(
            item for item in client.get(RATES_URL).json()["curve_spreads"] if item["spread_id"] == "2s10s"
        )

        assert spread["provenance"]["methodology_id"] == "rates_v1.0"
        assert spread["provenance"]["input_series_ids"] == [NOMINAL_10Y_SERIES_ID, NOMINAL_2Y_SERIES_ID]
        assert "provider" not in spread["provenance"]

    def test_unaligned_inputs_report_a_reason_rather_than_a_number(self, client, seed_session):
        _seed(seed_session, NOMINAL_10Y_SERIES_ID, [(date(2026, 6, 1), 5.01)])
        _seed(seed_session, REAL_10Y_SERIES_ID, [(date(2026, 6, 2), 2.68)], dataset=REAL_DATASET)

        compensation = next(
            item for item in client.get(RATES_URL).json()["inflation_compensation"] if item["maturity"] == "10Y"
        )

        assert compensation["available"] is False
        assert compensation["compensation_percent"] is None
        assert compensation["unavailable_reason"] == "NO_EXACTLY_SHARED_OBSERVATION_DATE"

    def test_route_is_read_only_and_never_reaches_upstream(self, client, seed_session):
        _seed(seed_session, NOMINAL_10Y_SERIES_ID, [(date(2026, 6, 1), 5.01)])

        with patch.object(TreasuryClient, "get_month") as mock_get_month:
            assert client.get(RATES_URL).status_code == 200

        mock_get_month.assert_not_called()

    def test_database_not_configured_is_503(self, client, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "database_url", None)
        response = client.get(RATES_URL)

        assert response.status_code == 503
        assert response.json()["detail"] == "Database is not configured on this server."


class TestPostRatesSync:
    def test_successful_sync_returns_counts_and_persists(self, client, seed_session):
        rows = {
            NOMINAL_DATASET: [TreasuryRateRow(date(2026, 6, 1), {"BC_10YEAR": 5.0, "BC_2YEAR": 4.7})],
            REAL_DATASET: [TreasuryRateRow(date(2026, 6, 1), {"TC_10YEAR": 2.6})],
        }

        def fake_get_month(self, dataset, year, month):
            result = rows.get(dataset, [])
            rows[dataset] = []
            return result

        with patch.object(TreasuryClient, "get_month", fake_get_month):
            response = client.post(f"{SYNC_URL}?lookback_months=1")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "SUCCEEDED"
        assert body["datasets_failed"] == []
        assert sum(item["observations_inserted"] for item in body["series"]) == 3
        assert client.get(RATES_URL).json()["as_of_date"] == "2026-06-01"

    def test_partial_upstream_failure_is_reported_not_raised(self, client, seed_session):
        def fake_get_month(self, dataset, year, month):
            if dataset == REAL_DATASET:
                raise TreasuryTimeoutError("upstream slow")
            return [TreasuryRateRow(date(2026, 6, 1), {"BC_10YEAR": 5.0})]

        with patch.object(TreasuryClient, "get_month", fake_get_month):
            response = client.post(f"{SYNC_URL}?lookback_months=1")

        assert response.status_code == 200
        assert response.json()["status"] == "PARTIAL_FAILURE"
        assert response.json()["datasets_failed"] == [REAL_DATASET]

    def test_total_upstream_failure_reports_a_failed_run(self, client, seed_session):
        with patch.object(TreasuryClient, "get_month", side_effect=TreasuryTimeoutError("down")):
            response = client.post(f"{SYNC_URL}?lookback_months=1")

        assert response.status_code == 200
        assert response.json()["status"] == "FAILED"

    @pytest.mark.parametrize("value", [0, -1, 241, "abc"])
    def test_invalid_lookback_is_rejected_with_422(self, client, value):
        with patch.object(TreasuryClient, "get_month") as mock_get_month:
            response = client.post(f"{SYNC_URL}?lookback_months={value}")

        assert response.status_code == 422
        mock_get_month.assert_not_called()

    def test_database_not_configured_is_503(self, client, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "database_url", None)
        response = client.post(SYNC_URL)

        assert response.status_code == 503

    def test_sync_requires_no_api_key(self, client, seed_session, monkeypatch):
        """These feeds are unauthenticated public government data: the
        route must work with no FRED/OpenAI credential configured."""
        from app.core.config import settings

        monkeypatch.setattr(settings, "fred_api_key", None)
        monkeypatch.setattr(settings, "openai_api_key", None)

        with patch.object(TreasuryClient, "get_month", return_value=[]):
            response = client.post(f"{SYNC_URL}?lookback_months=1")

        assert response.status_code == 200
