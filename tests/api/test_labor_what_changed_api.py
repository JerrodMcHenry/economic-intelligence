"""GET /api/v1/monitors/labor/changes -- PostgreSQL-only, real
isolated test database, no FRED, no OpenAI. Contract
`labor_what_changed_v1.0`. Covers exact response contract, no query
parameters, availability loss/restoration, no-change, sparse/empty
data, DB infrastructure failure (503/500), safe error bodies,
determinism, non-mutation, and independence from OpenAI/FRED.
"""

from datetime import date
from unittest.mock import patch

from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.clients.fred import FREDClient
from app.domain.labor import month_before
from app.models.labor import PAYEMS_SERIES_ID, UNRATE_SERIES_ID
from app.models.series import Observation, SeriesResponse
from app.repositories.series_repository import SeriesRepository
from app.services.labor import LaborMonitorService

ANCHOR = date(2025, 8, 1)


def _payems_history(anchor: date, count: int = 20) -> list[Observation]:
    return [Observation(date=month_before(anchor, n), value=150_000.0 - n * 0.3 - (n * n) * 0.01) for n in range(count)]


def _unrate_history(anchor: date, count: int = 20) -> list[Observation]:
    return [Observation(date=month_before(anchor, n), value=4.0 + n * 0.02) for n in range(count)]


def _seed(seed_session, series_id: str, observations: list[Observation]) -> None:
    units = "Thousands of Persons" if series_id == PAYEMS_SERIES_ID else "Percent"
    SeriesRepository(seed_session).save_series(SeriesResponse(series_id=series_id, title=series_id, units=units, observations=observations))
    seed_session.commit()


class TestSuccessAndContract:
    def test_success_with_full_data(self, client, seed_session):
        _seed(seed_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        _seed(seed_session, UNRATE_SERIES_ID, _unrate_history(ANCHOR))

        response = client.get("/api/v1/monitors/labor/changes")
        assert response.status_code == 200
        body = response.json()
        assert body["methodology_id"] == "labor_v1.0"
        assert body["comparison_contract_id"] == "labor_what_changed_v1.0"
        assert body["comparison_type"] == "MONTH_OVER_MONTH"
        assert body["data_basis"] == "latest_revised_data"
        assert body["comparison_available"] is True
        assert body["current_period"] == ANCHOR.isoformat()
        assert body["previous_period"] == month_before(ANCHOR, 1).isoformat()

    def test_no_query_parameters_accepted_or_required(self, client, seed_session):
        """A ?period= or similar parameter is silently ignored (FastAPI
        routes with no declared query params simply don't bind unknown
        ones) -- the response is identical with or without junk params,
        proving the route genuinely takes none."""
        _seed(seed_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        _seed(seed_session, UNRATE_SERIES_ID, _unrate_history(ANCHOR))
        plain = client.get("/api/v1/monitors/labor/changes").json()
        with_junk_param = client.get("/api/v1/monitors/labor/changes?period=2020-01-01").json()
        assert plain == with_junk_param

    def test_exact_top_level_contract(self, client, seed_session):
        _seed(seed_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        body = client.get("/api/v1/monitors/labor/changes").json()
        assert set(body.keys()) == {
            "methodology_id",
            "comparison_contract_id",
            "comparison_type",
            "data_basis",
            "comparison_available",
            "previous_period",
            "current_period",
            "previous_labor_state",
            "current_labor_state",
            "employment_changes",
            "unemployment_changes",
            "changes",
            "any_state_changed",
            "any_metric_changed",
            "any_availability_changed",
            "current_labor_result",
        }

    def test_employment_section_contract(self, client, seed_session):
        _seed(seed_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        _seed(seed_session, UNRATE_SERIES_ID, _unrate_history(ANCHOR))
        section = client.get("/api/v1/monitors/labor/changes").json()["employment_changes"]
        assert set(section.keys()) == {
            "previous_evidence",
            "current_evidence",
            "changes",
            "state_changed",
            "metric_changed",
            "availability_lost",
            "availability_restored",
        }
        # No per-section period/comparison_available triplet (Labor's own
        # documented simplification vs. Inflation -- frozen contract §10):
        assert "comparison_available" not in section
        assert "previous_period" not in section
        assert "current_period" not in section

    def test_unemployment_section_contract(self, client, seed_session):
        _seed(seed_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        _seed(seed_session, UNRATE_SERIES_ID, _unrate_history(ANCHOR))
        section = client.get("/api/v1/monitors/labor/changes").json()["unemployment_changes"]
        assert set(section.keys()) == {
            "previous_evidence",
            "current_evidence",
            "changes",
            "state_changed",
            "metric_changed",
            "availability_lost",
            "availability_restored",
        }

    def test_change_event_contract(self, client, seed_session):
        history = [(d, (v + 500_000.0 if d == ANCHOR else v)) for d, v in [(o.date, o.value) for o in _payems_history(ANCHOR)]]
        _seed(seed_session, PAYEMS_SERIES_ID, [Observation(date=d, value=v) for d, v in history])
        _seed(seed_session, UNRATE_SERIES_ID, _unrate_history(ANCHOR))
        body = client.get("/api/v1/monitors/labor/changes").json()
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
        assert event["methodology_id"] == "labor_v1.0"  # the SOURCE monitor, never the comparator's own id

    def test_no_interpretation_heavy_fields_anywhere(self, client, seed_session):
        _seed(seed_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        _seed(seed_session, UNRATE_SERIES_ID, _unrate_history(ANCHOR))
        body = client.get("/api/v1/monitors/labor/changes").json()
        body_text = str(body).upper()
        for forbidden in ("IMPROVED", "WORSENED", "GOOD_NEWS", "BAD_NEWS", "SHARP_DROP", "SIGNIFICANT_CHANGE", "ACCELERATING", "DECELERATING", "CONFIRMATION_CHANGED"):
            assert forbidden not in body_text

    def test_no_jolts_or_civpart_anywhere(self, client, seed_session):
        _seed(seed_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        _seed(seed_session, UNRATE_SERIES_ID, _unrate_history(ANCHOR))
        body_text = str(client.get("/api/v1/monitors/labor/changes").json())
        for forbidden in ("JTSJOR", "JTSQUR", "JTSHIR", "CIVPART"):
            assert forbidden not in body_text


class TestAvailabilityTransitions:
    def test_employment_availability_loss(self, client, seed_session):
        points = [Observation(date=o.date, value=(None if o.date == ANCHOR else o.value)) for o in _payems_history(ANCHOR)]
        _seed(seed_session, PAYEMS_SERIES_ID, points)
        _seed(seed_session, UNRATE_SERIES_ID, _unrate_history(ANCHOR))
        body = client.get("/api/v1/monitors/labor/changes").json()
        section = body["employment_changes"]
        assert section["availability_lost"] is True
        assert section["current_evidence"]["state"] == "INSUFFICIENT_DATA"
        assert body["current_labor_state"] == "INSUFFICIENT_DATA"
        assert body["any_availability_changed"] is True

    def test_employment_availability_restoration(self, client, seed_session):
        # Offset 4 from ANCHOR -- inside previous_period's (ANCHOR-1's)
        # own required window {0,1,2,3} relative to itself, but OUTSIDE
        # ANCHOR's own required window {0,1,2,3} relative to ANCHOR --
        # so only previous_evidence loses availability, never current_evidence.
        gapped_month = month_before(ANCHOR, 4)
        points = [Observation(date=o.date, value=(None if o.date == gapped_month else o.value)) for o in _payems_history(ANCHOR)]
        _seed(seed_session, PAYEMS_SERIES_ID, points)
        _seed(seed_session, UNRATE_SERIES_ID, _unrate_history(ANCHOR))
        section = client.get("/api/v1/monitors/labor/changes").json()["employment_changes"]
        assert section["availability_restored"] is True
        assert section["previous_evidence"]["state"] == "INSUFFICIENT_DATA"

    def test_unemployment_unaffected_by_a_payems_only_gap(self, client, seed_session):
        points = [Observation(date=o.date, value=(None if o.date == ANCHOR else o.value)) for o in _payems_history(ANCHOR)]
        _seed(seed_session, PAYEMS_SERIES_ID, points)
        _seed(seed_session, UNRATE_SERIES_ID, _unrate_history(ANCHOR))
        section = client.get("/api/v1/monitors/labor/changes").json()["unemployment_changes"]
        assert section["availability_lost"] is False
        assert section["availability_restored"] is False


class TestNoChangeCase:
    def test_identical_metrics_and_state_yields_empty_changes(self, client, seed_session):
        # Constant month-over-month level -- current_3m_avg_jobs is 0.0
        # every month, comfortably FLAT/STEADY/STABLE both periods:
        flat = [Observation(date=o.date, value=150_000.0) for o in _payems_history(ANCHOR)]
        _seed(seed_session, PAYEMS_SERIES_ID, flat)
        flat_unrate = [Observation(date=o.date, value=4.0) for o in _unrate_history(ANCHOR)]
        _seed(seed_session, UNRATE_SERIES_ID, flat_unrate)

        body = client.get("/api/v1/monitors/labor/changes").json()
        assert body["comparison_available"] is True
        assert body["changes"] == []
        assert body["any_state_changed"] is False
        assert body["any_metric_changed"] is False
        assert body["any_availability_changed"] is False


class TestSparseAndEmptyData:
    def test_sparse_data_reports_insufficient_data_not_an_error(self, client, seed_session):
        _seed(seed_session, PAYEMS_SERIES_ID, [Observation(date=ANCHOR, value=150_000.0)])
        response = client.get("/api/v1/monitors/labor/changes")
        assert response.status_code == 200
        section = response.json()["employment_changes"]
        assert section["current_evidence"]["state"] == "INSUFFICIENT_DATA"

    def test_empty_database_returns_200_with_comparison_unavailable(self, client, seed_session):
        response = client.get("/api/v1/monitors/labor/changes")
        assert response.status_code == 200
        body = response.json()
        assert body["comparison_available"] is False
        assert body["previous_period"] is None
        assert body["current_period"] is None
        assert body["previous_labor_state"] == "INSUFFICIENT_DATA"
        assert body["current_labor_state"] == "INSUFFICIENT_DATA"
        assert body["changes"] == []
        assert body["any_state_changed"] is False
        assert body["any_metric_changed"] is False
        assert body["any_availability_changed"] is False
        assert body["employment_changes"]["previous_evidence"]["observations"] == []
        assert body["unemployment_changes"]["current_evidence"]["observations"] == []


class TestDatabaseInfrastructureFailure:
    def test_operational_error_returns_503(self, client, seed_session):
        _seed(seed_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        with patch.object(LaborMonitorService, "get_what_changed_result", side_effect=OperationalError("s", {}, Exception("down"))):
            response = client.get("/api/v1/monitors/labor/changes")
        assert response.status_code == 503
        assert "down" not in response.text

    def test_generic_sqlalchemy_error_returns_500(self, client, seed_session):
        _seed(seed_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        with patch.object(LaborMonitorService, "get_what_changed_result", side_effect=SQLAlchemyError("synthetic failure")):
            response = client.get("/api/v1/monitors/labor/changes")
        assert response.status_code == 500

    def test_no_stack_trace_or_internal_detail_in_500_response(self, client, seed_session):
        with patch.object(
            LaborMonitorService,
            "get_what_changed_result",
            side_effect=SQLAlchemyError("SELECT * FROM secret_table; password=hunter2 host=db.internal"),
        ):
            response = client.get("/api/v1/monitors/labor/changes")
        body_text = response.text.lower()
        for forbidden in ("traceback", "site-packages", "/users/", "hunter2", "secret_table", "password="):
            assert forbidden not in body_text

    def test_database_not_configured_returns_503(self, client, monkeypatch, test_database_url):
        from app.core.config import settings

        monkeypatch.setattr(settings, "database_url", None)
        response = client.get("/api/v1/monitors/labor/changes")
        assert response.status_code == 503


class TestDeterminismAndNonMutation:
    def test_repeated_requests_return_identical_body(self, client, seed_session):
        _seed(seed_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        _seed(seed_session, UNRATE_SERIES_ID, _unrate_history(ANCHOR))
        r1 = client.get("/api/v1/monitors/labor/changes")
        r2 = client.get("/api/v1/monitors/labor/changes")
        assert r1.json() == r2.json()

    def test_request_does_not_mutate_persisted_observations(self, client, seed_session):
        _seed(seed_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        before = client.get(f"/api/v1/series/{PAYEMS_SERIES_ID}/observations").json()

        client.get("/api/v1/monitors/labor/changes")
        client.get("/api/v1/monitors/labor/changes")

        after = client.get(f"/api/v1/series/{PAYEMS_SERIES_ID}/observations").json()
        assert before == after


class TestAIAndFredIndependence:
    def test_works_without_openai_key(self, client, seed_session, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "openai_api_key", None)
        _seed(seed_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        response = client.get("/api/v1/monitors/labor/changes")
        assert response.status_code == 200

    def test_never_constructs_a_fred_client(self, client, seed_session):
        """A fail-fast fake FRED boundary: if the changes path ever
        tried to construct a FREDClient, this raises immediately and
        the request would come back as a 500 -- the 200 assertion below
        would otherwise be unreachable."""
        _seed(seed_session, PAYEMS_SERIES_ID, _payems_history(ANCHOR))
        with patch.object(FREDClient, "__init__", side_effect=AssertionError("FREDClient must never be constructed here")):
            response = client.get("/api/v1/monitors/labor/changes")
        assert response.status_code == 200

    def test_no_synchronization_or_ingestion_side_effect(self, client, seed_session):
        response = client.get("/api/v1/monitors/labor/changes")
        assert response.status_code == 200
        lookup = client.get(f"/api/v1/series/{PAYEMS_SERIES_ID}/observations")
        assert lookup.status_code == 404
