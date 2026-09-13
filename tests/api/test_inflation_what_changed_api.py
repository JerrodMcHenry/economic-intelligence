"""GET /api/v1/monitors/inflation/changes -- PostgreSQL-only, real
isolated test database, no FRED, no OpenAI. Contract
`inflation_what_changed_v1.0`. Covers exact response contract,
availability loss/restoration, relationship loss/restoration, no-change,
sparse data, empty DB, DB infrastructure failure (503/500), safe error
bodies, determinism, non-mutation, and independence from OpenAI/FRED.
"""

from datetime import date
from unittest.mock import patch

from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.clients.fred import FREDClient
from app.domain.inflation import month_before
from app.models.inflation import CONFIRMATION_SERIES_ID, HEADLINE_CPI_SERIES_ID, PRIMARY_SERIES_ID, TARGET_SERIES_ID
from app.models.series import Observation, SeriesResponse
from app.repositories.series_repository import SeriesRepository
from app.services.inflation import InflationMonitorService

LONG_HISTORY = [
    Observation(date=month_before(date(2025, 2, 1), -i), value=100.0 + i * 0.5) for i in range(-25, 1)
]  # 2023-01 .. 2025-02


def _seed(seed_session, series_id: str, observations: list[Observation]) -> None:
    SeriesRepository(seed_session).save_series(
        SeriesResponse(series_id=series_id, title=series_id, units="Index", observations=observations)
    )
    seed_session.commit()


class TestSuccessAndContract:
    def test_success_with_full_data(self, client, seed_session):
        _seed(seed_session, PRIMARY_SERIES_ID, LONG_HISTORY)
        _seed(seed_session, CONFIRMATION_SERIES_ID, LONG_HISTORY)
        _seed(seed_session, TARGET_SERIES_ID, LONG_HISTORY)
        _seed(seed_session, HEADLINE_CPI_SERIES_ID, LONG_HISTORY)

        response = client.get("/api/v1/monitors/inflation/changes")
        assert response.status_code == 200
        body = response.json()
        assert body["methodology_id"] == "inflation_v1.0"
        assert body["comparison_contract_id"] == "inflation_what_changed_v1.0"
        assert body["comparison_type"] == "MONTH_OVER_MONTH"
        assert body["data_basis"] == "latest_revised_data"

    def test_exact_top_level_contract(self, client, seed_session):
        _seed(seed_session, PRIMARY_SERIES_ID, LONG_HISTORY)
        body = client.get("/api/v1/monitors/inflation/changes").json()
        assert set(body.keys()) == {
            "methodology_id",
            "comparison_contract_id",
            "comparison_type",
            "data_basis",
            "primary_momentum_changes",
            "confirmation_changes",
            "target_changes",
            "headline_pce_changes",
            "headline_cpi_changes",
            "changes",
            "any_metric_changed",
            "any_state_changed",
            "any_availability_changed",
            "confirmation_changed",
            "current_monitor_result",
        }

    def test_primary_momentum_section_contract(self, client, seed_session):
        _seed(seed_session, PRIMARY_SERIES_ID, LONG_HISTORY)
        section = client.get("/api/v1/monitors/inflation/changes").json()["primary_momentum_changes"]
        assert set(section.keys()) == {
            "comparison_available",
            "previous_period",
            "current_period",
            "previous_evidence",
            "current_evidence",
            "changes",
            "metric_changed",
            "state_changed",
            "availability_lost",
            "availability_restored",
        }
        assert section["comparison_available"] is True
        assert section["current_period"] == "2025-02-01"
        assert section["previous_period"] == "2025-01-01"

    def test_confirmation_section_contract(self, client, seed_session):
        _seed(seed_session, PRIMARY_SERIES_ID, LONG_HISTORY)
        _seed(seed_session, CONFIRMATION_SERIES_ID, LONG_HISTORY)
        section = client.get("/api/v1/monitors/inflation/changes").json()["confirmation_changes"]
        assert set(section.keys()) == {
            "comparison_available",
            "previous_confirmation_period",
            "current_confirmation_period",
            "previous_primary_state",
            "previous_confirmation_state",
            "previous_relationship",
            "current_primary_state",
            "current_confirmation_state",
            "current_relationship",
            "changes",
            "relationship_changed",
            "confirmation_availability_lost",
            "confirmation_availability_restored",
        }

    def test_change_event_contract(self, client, seed_session):
        points = LONG_HISTORY[:-1] + [Observation(date=date(2025, 2, 1), value=200.0)]  # forces a metric change
        _seed(seed_session, PRIMARY_SERIES_ID, points)
        body = client.get("/api/v1/monitors/inflation/changes").json()
        assert len(body["changes"]) > 0
        event = body["changes"][0]
        assert set(event.keys()) == {
            "component",
            "event_type",
            "field",
            "previous_value",
            "current_value",
            "delta",
            "previous_period",
            "current_period",
            "methodology_id",
            "data_basis",
        }

    def test_no_interpretation_heavy_fields_anywhere(self, client, seed_session):
        _seed(seed_session, PRIMARY_SERIES_ID, LONG_HISTORY)
        body = client.get("/api/v1/monitors/inflation/changes").json()
        body_text = str(body).upper()
        for forbidden in ("IMPROVED", "WORSENED", "GOOD_NEWS", "BAD_NEWS", "SHARP_DROP", "SIGNIFICANT_CHANGE"):
            assert forbidden not in body_text


class TestAvailabilityAndRelationshipTransitions:
    def test_availability_loss(self, client, seed_session):
        points = LONG_HISTORY[:-1] + [Observation(date=date(2025, 2, 1), value=None)]
        _seed(seed_session, PRIMARY_SERIES_ID, points)
        section = client.get("/api/v1/monitors/inflation/changes").json()["primary_momentum_changes"]
        assert section["availability_lost"] is True
        assert section["current_evidence"]["state"] == "INSUFFICIENT_DATA"

    def test_availability_restoration(self, client, seed_session):
        points = [o for o in LONG_HISTORY if o.date != date(2025, 1, 1)]
        _seed(seed_session, PRIMARY_SERIES_ID, points)
        section = client.get("/api/v1/monitors/inflation/changes").json()["primary_momentum_changes"]
        assert section["availability_restored"] is True
        assert section["previous_evidence"]["state"] == "INSUFFICIENT_DATA"

    def test_confirmation_relationship_loss(self, client, seed_session):
        _seed(seed_session, PRIMARY_SERIES_ID, LONG_HISTORY)
        cpi_points = [Observation(date=o.date, value=o.value * 0.5) for o in LONG_HISTORY if o.date != date(2025, 2, 1)]
        cpi_points.append(Observation(date=date(2025, 2, 1), value=None))
        _seed(seed_session, CONFIRMATION_SERIES_ID, cpi_points)

        section = client.get("/api/v1/monitors/inflation/changes").json()["confirmation_changes"]
        assert section["current_confirmation_period"] == "2025-02-01"
        assert section["current_relationship"] == "UNAVAILABLE"
        assert section["confirmation_availability_lost"] is True
        assert section["relationship_changed"] is True

    def test_confirmation_relationship_restoration(self, client, seed_session):
        _seed(seed_session, PRIMARY_SERIES_ID, LONG_HISTORY)
        cpi_points = [Observation(date=o.date, value=o.value * 0.5) for o in LONG_HISTORY if o.date != date(2025, 1, 1)]
        _seed(seed_session, CONFIRMATION_SERIES_ID, cpi_points)

        section = client.get("/api/v1/monitors/inflation/changes").json()["confirmation_changes"]
        assert section["current_confirmation_period"] == "2025-02-01"
        assert section["previous_relationship"] == "UNAVAILABLE"
        assert section["confirmation_availability_restored"] is True


class TestNoChangeCase:
    def test_identical_metrics_and_state_yields_empty_changes(self, client, seed_session):
        # Flat, constant index level -- every horizon's rate is 0.0, identical
        # month to month, comfortably STABLE both periods:
        flat = [Observation(date=o.date, value=100.0) for o in LONG_HISTORY]
        _seed(seed_session, PRIMARY_SERIES_ID, flat)
        section = client.get("/api/v1/monitors/inflation/changes").json()["primary_momentum_changes"]
        assert section["comparison_available"] is True
        assert section["changes"] == []
        assert section["metric_changed"] is False
        assert section["state_changed"] is False


class TestSparseAndEmptyData:
    def test_sparse_data_reports_insufficient_data_not_an_error(self, client, seed_session):
        _seed(seed_session, PRIMARY_SERIES_ID, [Observation(date=date(2025, 1, 1), value=100.0)])
        response = client.get("/api/v1/monitors/inflation/changes")
        assert response.status_code == 200
        section = response.json()["primary_momentum_changes"]
        assert section["comparison_available"] is True
        assert section["current_evidence"]["state"] == "INSUFFICIENT_DATA"

    def test_empty_database_returns_200_with_comparison_unavailable_everywhere(self, client, seed_session):
        response = client.get("/api/v1/monitors/inflation/changes")
        assert response.status_code == 200
        body = response.json()
        for section_name in ("primary_momentum_changes", "target_changes", "headline_pce_changes", "headline_cpi_changes"):
            section = body[section_name]
            assert section["comparison_available"] is False
            assert section["current_period"] is None
            assert section["previous_period"] is None
            assert section["changes"] == []
        confirmation = body["confirmation_changes"]
        assert confirmation["comparison_available"] is False
        assert confirmation["current_confirmation_period"] is None
        assert body["changes"] == []
        assert body["any_metric_changed"] is False
        assert body["any_state_changed"] is False
        assert body["any_availability_changed"] is False
        assert body["confirmation_changed"] is False


class TestDatabaseInfrastructureFailure:
    def test_operational_error_returns_503(self, client, seed_session):
        _seed(seed_session, PRIMARY_SERIES_ID, LONG_HISTORY)
        with patch.object(InflationMonitorService, "get_what_changed_result", side_effect=OperationalError("s", {}, Exception("down"))):
            response = client.get("/api/v1/monitors/inflation/changes")
        assert response.status_code == 503
        assert "down" not in response.text

    def test_generic_sqlalchemy_error_returns_500(self, client, seed_session):
        _seed(seed_session, PRIMARY_SERIES_ID, LONG_HISTORY)
        with patch.object(InflationMonitorService, "get_what_changed_result", side_effect=SQLAlchemyError("synthetic failure")):
            response = client.get("/api/v1/monitors/inflation/changes")
        assert response.status_code == 500

    def test_no_stack_trace_or_internal_detail_in_500_response(self, client, seed_session):
        with patch.object(
            InflationMonitorService,
            "get_what_changed_result",
            side_effect=SQLAlchemyError("SELECT * FROM secret_table; password=hunter2 host=db.internal"),
        ):
            response = client.get("/api/v1/monitors/inflation/changes")
        body_text = response.text.lower()
        for forbidden in ("traceback", "site-packages", "/users/", "hunter2", "secret_table", "password="):
            assert forbidden not in body_text

    def test_database_not_configured_returns_503(self, client, monkeypatch, test_database_url):
        from app.core.config import settings

        monkeypatch.setattr(settings, "database_url", None)
        response = client.get("/api/v1/monitors/inflation/changes")
        assert response.status_code == 503


class TestDeterminismAndNonMutation:
    def test_repeated_requests_return_identical_body(self, client, seed_session):
        _seed(seed_session, PRIMARY_SERIES_ID, LONG_HISTORY)
        _seed(seed_session, CONFIRMATION_SERIES_ID, LONG_HISTORY)
        r1 = client.get("/api/v1/monitors/inflation/changes")
        r2 = client.get("/api/v1/monitors/inflation/changes")
        assert r1.json() == r2.json()

    def test_request_does_not_mutate_persisted_observations(self, client, seed_session):
        _seed(seed_session, PRIMARY_SERIES_ID, LONG_HISTORY)
        before = client.get(f"/api/v1/series/{PRIMARY_SERIES_ID}/observations").json()

        client.get("/api/v1/monitors/inflation/changes")
        client.get("/api/v1/monitors/inflation/changes")

        after = client.get(f"/api/v1/series/{PRIMARY_SERIES_ID}/observations").json()
        assert before == after


class TestAIAndFredIndependence:
    def test_works_without_openai_key(self, client, seed_session, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "openai_api_key", None)
        _seed(seed_session, PRIMARY_SERIES_ID, LONG_HISTORY)
        response = client.get("/api/v1/monitors/inflation/changes")
        assert response.status_code == 200

    def test_never_constructs_a_fred_client(self, client, seed_session):
        """A fail-fast fake FRED boundary: if the changes path ever
        tried to construct a FREDClient, this raises immediately and
        the request would come back as a 500 -- the 200 assertion below
        would otherwise be unreachable."""
        _seed(seed_session, PRIMARY_SERIES_ID, LONG_HISTORY)
        with patch.object(FREDClient, "__init__", side_effect=AssertionError("FREDClient must never be constructed here")):
            response = client.get("/api/v1/monitors/inflation/changes")
        assert response.status_code == 200

    def test_no_synchronization_or_ingestion_side_effect(self, client, seed_session):
        response = client.get("/api/v1/monitors/inflation/changes")
        assert response.status_code == 200
        lookup = client.get(f"/api/v1/series/{PRIMARY_SERIES_ID}/observations")
        assert lookup.status_code == 404
