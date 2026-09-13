"""GET /api/v1/series/{series_id}/observations and
GET /api/v1/series/{series_id}/transform -- PostgreSQL-only, real
isolated test database, no FRED, no OpenAI.

Locks down the 400 (semantic, application-level) vs 422 (structural,
FastAPI/Pydantic query-parameter validation) distinction precisely.
"""

from app.models.series import Observation, SeriesResponse
from app.repositories.series_repository import SeriesRepository


def _seed(seed_session, series_id="UNRATE", observations=None):
    SeriesRepository(seed_session).save_series(
        SeriesResponse(series_id=series_id, title="Unemployment Rate", units="Percent", observations=observations or [])
    )
    seed_session.commit()


class TestGetObservations:
    def test_known_series_default_pagination(self, client, seed_session):
        _seed(seed_session, observations=[Observation(date="2024-01-01", value=100.0), Observation(date="2024-02-01", value=110.0)])
        response = client.get("/api/v1/series/UNRATE/observations")
        assert response.status_code == 200
        body = response.json()
        assert body["series_id"] == "UNRATE"
        assert body["observations"] == [{"date": "2024-01-01", "value": 100.0}, {"date": "2024-02-01", "value": 110.0}]
        assert body["pagination"] == {"limit": 100, "offset": 0, "returned": 2, "total": 2}

    def test_unknown_series_returns_404(self, client, seed_session):
        response = client.get("/api/v1/series/NOPE/observations")
        assert response.status_code == 404

    def test_custom_limit(self, client, seed_session):
        _seed(seed_session, observations=[Observation(date=f"2024-0{m}-01", value=float(m)) for m in range(1, 4)])
        response = client.get("/api/v1/series/UNRATE/observations", params={"limit": 1})
        body = response.json()
        assert len(body["observations"]) == 1
        assert body["pagination"] == {"limit": 1, "offset": 0, "returned": 1, "total": 3}

    def test_custom_offset(self, client, seed_session):
        _seed(seed_session, observations=[Observation(date=f"2024-0{m}-01", value=float(m)) for m in range(1, 4)])
        response = client.get("/api/v1/series/UNRATE/observations", params={"offset": 1})
        assert [o["date"] for o in response.json()["observations"]] == ["2024-02-01", "2024-03-01"]

    def test_ascending_order(self, client, seed_session):
        _seed(seed_session, observations=[Observation(date="2024-01-01", value=1.0), Observation(date="2024-02-01", value=2.0)])
        response = client.get("/api/v1/series/UNRATE/observations", params={"order": "asc"})
        assert [o["date"] for o in response.json()["observations"]] == ["2024-01-01", "2024-02-01"]

    def test_descending_order(self, client, seed_session):
        _seed(seed_session, observations=[Observation(date="2024-01-01", value=1.0), Observation(date="2024-02-01", value=2.0)])
        response = client.get("/api/v1/series/UNRATE/observations", params={"order": "desc"})
        assert [o["date"] for o in response.json()["observations"]] == ["2024-02-01", "2024-01-01"]

    def test_start_date_filtering(self, client, seed_session):
        _seed(seed_session, observations=[Observation(date=f"2024-0{m}-01", value=float(m)) for m in range(1, 4)])
        response = client.get("/api/v1/series/UNRATE/observations", params={"start_date": "2024-02-01"})
        assert [o["date"] for o in response.json()["observations"]] == ["2024-02-01", "2024-03-01"]

    def test_end_date_filtering(self, client, seed_session):
        _seed(seed_session, observations=[Observation(date=f"2024-0{m}-01", value=float(m)) for m in range(1, 4)])
        response = client.get("/api/v1/series/UNRATE/observations", params={"end_date": "2024-02-01"})
        assert [o["date"] for o in response.json()["observations"]] == ["2024-01-01", "2024-02-01"]

    def test_combined_date_range(self, client, seed_session):
        _seed(seed_session, observations=[Observation(date=f"2024-0{m}-01", value=float(m)) for m in range(1, 5)])
        response = client.get("/api/v1/series/UNRATE/observations", params={"start_date": "2024-02-01", "end_date": "2024-03-01"})
        assert [o["date"] for o in response.json()["observations"]] == ["2024-02-01", "2024-03-01"]

    def test_empty_matching_range_on_existing_series(self, client, seed_session):
        _seed(seed_session, observations=[Observation(date="2024-01-01", value=1.0)])
        response = client.get("/api/v1/series/UNRATE/observations", params={"start_date": "2030-01-01"})
        assert response.status_code == 200
        body = response.json()
        assert body["observations"] == []
        assert body["pagination"] == {"limit": 100, "offset": 0, "returned": 0, "total": 0}


class TestObservationsValidation:
    def test_limit_below_minimum_returns_422(self, client, seed_session):
        _seed(seed_session)
        response = client.get("/api/v1/series/UNRATE/observations", params={"limit": 0})
        assert response.status_code == 422

    def test_limit_above_maximum_returns_422(self, client, seed_session):
        _seed(seed_session)
        response = client.get("/api/v1/series/UNRATE/observations", params={"limit": 1001})
        assert response.status_code == 422

    def test_negative_offset_returns_422(self, client, seed_session):
        _seed(seed_session)
        response = client.get("/api/v1/series/UNRATE/observations", params={"offset": -1})
        assert response.status_code == 422

    def test_invalid_order_returns_422(self, client, seed_session):
        _seed(seed_session)
        response = client.get("/api/v1/series/UNRATE/observations", params={"order": "sideways"})
        assert response.status_code == 422

    def test_malformed_date_returns_422(self, client, seed_session):
        _seed(seed_session)
        response = client.get("/api/v1/series/UNRATE/observations", params={"start_date": "not-a-date"})
        assert response.status_code == 422

    def test_start_after_end_is_400_not_422(self, client, seed_session):
        """Structurally valid dates, semantically invalid relationship --
        FastAPI/Pydantic can't catch this (each date is valid on its
        own); it's EconomicDataService's own InvalidDateRangeError,
        mapped to 400. This distinction is the one this test file exists
        to lock down permanently."""
        _seed(seed_session, observations=[Observation(date="2024-01-01", value=1.0)])
        response = client.get(
            "/api/v1/series/UNRATE/observations", params={"start_date": "2024-03-01", "end_date": "2024-01-01"}
        )
        assert response.status_code == 400


class TestReadPathNonMutation:
    def test_get_observations_does_not_mutate_persisted_data(self, client, seed_session):
        from sqlalchemy import text

        _seed(seed_session, observations=[Observation(date="2024-01-01", value=1.0), Observation(date="2024-02-01", value=2.0)])
        before = seed_session.execute(text("SELECT observation_date, value FROM economic_observations ORDER BY observation_date")).fetchall()

        client.get("/api/v1/series/UNRATE/observations")
        client.get("/api/v1/series/UNRATE/observations", params={"order": "desc"})

        after = seed_session.execute(text("SELECT observation_date, value FROM economic_observations ORDER BY observation_date")).fetchall()
        assert before == after


class TestRepeatedRequestDeterminism:
    def test_same_request_returns_identical_response(self, client, seed_session):
        _seed(seed_session, observations=[Observation(date="2024-01-01", value=1.0), Observation(date="2024-02-01", value=2.0)])
        first = client.get("/api/v1/series/UNRATE/observations").json()
        second = client.get("/api/v1/series/UNRATE/observations").json()
        assert first == second


class TestGetTransform:
    def test_absolute_change(self, client, seed_session):
        _seed(seed_session, observations=[Observation(date="2024-01-01", value=100.0), Observation(date="2024-02-01", value=110.0)])
        response = client.get("/api/v1/series/UNRATE/transform", params={"transformation": "absolute_change"})
        assert response.status_code == 200
        body = response.json()
        assert body["transformation"] == {"type": "absolute_change", "window": None}
        assert body["observations"] == [
            {"date": "2024-01-01", "original_value": 100.0, "value": None},
            {"date": "2024-02-01", "original_value": 110.0, "value": 10.0},
        ]

    def test_percent_change(self, client, seed_session):
        _seed(seed_session, observations=[Observation(date="2024-01-01", value=100.0), Observation(date="2024-02-01", value=110.0)])
        response = client.get("/api/v1/series/UNRATE/transform", params={"transformation": "percent_change"})
        assert response.json()["observations"][1]["value"] == 10.0

    def test_moving_average(self, client, seed_session):
        _seed(seed_session, observations=[Observation(date=f"2024-0{m}-01", value=float(m * 10)) for m in range(1, 4)])
        response = client.get("/api/v1/series/UNRATE/transform", params={"transformation": "moving_average", "window": 2})
        body = response.json()
        assert body["transformation"] == {"type": "moving_average", "window": 2}
        assert [o["value"] for o in body["observations"]] == [None, 15.0, 25.0]

    def test_boundary_context_correctness_through_http(self, client, seed_session):
        """Jan=100, Feb=110, Mar=121; start_date=Feb -> Feb must be
        10.0, not null -- proves preceding-context retrieval works
        through the full HTTP path, not just the service layer directly
        (Increment 011 already proved the service layer)."""
        _seed(seed_session, observations=[
            Observation(date="2024-01-01", value=100.0),
            Observation(date="2024-02-01", value=110.0),
            Observation(date="2024-03-01", value=121.0),
        ])
        response = client.get(
            "/api/v1/series/UNRATE/transform",
            params={"transformation": "percent_change", "start_date": "2024-02-01"},
        )
        body = response.json()
        assert [o["date"] for o in body["observations"]] == ["2024-02-01", "2024-03-01"]  # Jan (context) trimmed
        assert body["observations"][0]["value"] == 10.0
        assert body["observations"][1]["value"] == 10.0

    def test_unknown_series_returns_404(self, client, seed_session):
        response = client.get("/api/v1/series/NOPE/transform", params={"transformation": "percent_change"})
        assert response.status_code == 404

    def test_invalid_date_range_returns_400(self, client, seed_session):
        _seed(seed_session, observations=[Observation(date="2024-01-01", value=1.0)])
        response = client.get(
            "/api/v1/series/UNRATE/transform",
            params={"transformation": "percent_change", "start_date": "2024-03-01", "end_date": "2024-01-01"},
        )
        assert response.status_code == 400

    def test_missing_window_for_moving_average_returns_400(self, client, seed_session):
        _seed(seed_session, observations=[Observation(date="2024-01-01", value=1.0)])
        response = client.get("/api/v1/series/UNRATE/transform", params={"transformation": "moving_average"})
        assert response.status_code == 400

    def test_window_supplied_for_inapplicable_transformation_returns_400(self, client, seed_session):
        _seed(seed_session, observations=[Observation(date="2024-01-01", value=1.0)])
        response = client.get(
            "/api/v1/series/UNRATE/transform", params={"transformation": "percent_change", "window": 5}
        )
        assert response.status_code == 400

    def test_unsupported_transformation_value_returns_422(self, client, seed_session):
        """transformation is a Literal -- an unrecognized value is a
        structural schema violation, not an application semantic one."""
        _seed(seed_session, observations=[Observation(date="2024-01-01", value=1.0)])
        response = client.get("/api/v1/series/UNRATE/transform", params={"transformation": "not_a_real_transform"})
        assert response.status_code == 422

    def test_window_out_of_bounds_returns_422(self, client, seed_session):
        _seed(seed_session, observations=[Observation(date="2024-01-01", value=1.0)])
        response = client.get(
            "/api/v1/series/UNRATE/transform", params={"transformation": "moving_average", "window": 1}
        )
        assert response.status_code == 422  # window ge=2 -- structural bound
