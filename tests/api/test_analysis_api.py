"""GET /api/v1/analysis/compare and POST /api/v1/analysis/pipeline --
PostgreSQL-only, real isolated test database, no FRED, no OpenAI.

Pipeline is the richest deterministic public contract in this project;
its section here is the largest, including the decisive transformation-
before-alignment ordering test carried through the full HTTP path.
"""

from sqlalchemy import text

from app.models.series import Observation, SeriesResponse
from app.repositories.series_repository import SeriesRepository


def _seed(seed_session, series_id, observations):
    SeriesRepository(seed_session).save_series(
        SeriesResponse(series_id=series_id, title=series_id, units="Index", observations=observations)
    )
    seed_session.commit()


class TestCompare:
    def test_aligned_exact_date_alignment(self, client, seed_session):
        _seed(seed_session, "A", [Observation(date="2024-01-01", value=1.0), Observation(date="2024-02-01", value=2.0), Observation(date="2024-03-01", value=3.0)])
        _seed(seed_session, "B", [Observation(date="2024-01-01", value=10.0), Observation(date="2024-03-01", value=30.0), Observation(date="2024-04-01", value=40.0)])
        response = client.get("/api/v1/analysis/compare", params={"series_a": "A", "series_b": "B", "analysis": "aligned"})
        assert response.status_code == 200
        body = response.json()
        assert [o["date"] for o in body["observations"]] == ["2024-01-01", "2024-03-01"]
        assert body["matching_pairs"] == 2

    def test_spread_values(self, client, seed_session):
        _seed(seed_session, "A", [Observation(date="2024-01-01", value=10.0)])
        _seed(seed_session, "B", [Observation(date="2024-01-01", value=4.0)])
        response = client.get("/api/v1/analysis/compare", params={"series_a": "A", "series_b": "B", "analysis": "spread"})
        assert response.json()["observations"][0]["spread"] == 6.0

    def test_correlation(self, client, seed_session):
        _seed(seed_session, "A", [Observation(date=f"2024-0{m}-01", value=float(m)) for m in range(1, 5)])
        _seed(seed_session, "B", [Observation(date=f"2024-0{m}-01", value=float(2 * m)) for m in range(1, 5)])
        response = client.get("/api/v1/analysis/compare", params={"series_a": "A", "series_b": "B", "analysis": "correlation"})
        assert response.json()["correlation"] == 1.0

    def test_missing_dates_excluded(self, client, seed_session):
        _seed(seed_session, "A", [Observation(date="2024-01-01", value=1.0)])
        _seed(seed_session, "B", [Observation(date="2024-02-01", value=2.0)])
        response = client.get("/api/v1/analysis/compare", params={"series_a": "A", "series_b": "B", "analysis": "aligned"})
        assert response.json()["observations"] == []
        assert response.json()["matching_pairs"] == 0

    def test_null_values_preserved(self, client, seed_session):
        _seed(seed_session, "A", [Observation(date="2024-01-01", value=None)])
        _seed(seed_session, "B", [Observation(date="2024-01-01", value=5.0)])
        response = client.get("/api/v1/analysis/compare", params={"series_a": "A", "series_b": "B", "analysis": "aligned"})
        body = response.json()
        assert body["observations"][0]["value_a"] is None and body["observations"][0]["value_b"] == 5.0
        assert body["matching_pairs"] == 1 and body["usable_pairs"] == 0

    def test_date_filtering(self, client, seed_session):
        _seed(seed_session, "A", [Observation(date=f"2024-0{m}-01", value=float(m)) for m in range(1, 5)])
        _seed(seed_session, "B", [Observation(date=f"2024-0{m}-01", value=float(m)) for m in range(1, 5)])
        response = client.get(
            "/api/v1/analysis/compare",
            params={"series_a": "A", "series_b": "B", "analysis": "aligned", "start_date": "2024-02-01", "end_date": "2024-03-01"},
        )
        assert [o["date"] for o in response.json()["observations"]] == ["2024-02-01", "2024-03-01"]

    def test_unknown_series_a_returns_404(self, client, seed_session):
        _seed(seed_session, "B", [Observation(date="2024-01-01", value=1.0)])
        response = client.get("/api/v1/analysis/compare", params={"series_a": "NOPE", "series_b": "B", "analysis": "aligned"})
        assert response.status_code == 404

    def test_unknown_series_b_returns_404(self, client, seed_session):
        _seed(seed_session, "A", [Observation(date="2024-01-01", value=1.0)])
        response = client.get("/api/v1/analysis/compare", params={"series_a": "A", "series_b": "NOPE", "analysis": "aligned"})
        assert response.status_code == 404

    def test_invalid_date_range_returns_400(self, client, seed_session):
        _seed(seed_session, "A", [Observation(date="2024-01-01", value=1.0)])
        _seed(seed_session, "B", [Observation(date="2024-01-01", value=1.0)])
        response = client.get(
            "/api/v1/analysis/compare",
            params={"series_a": "A", "series_b": "B", "analysis": "aligned", "start_date": "2024-03-01", "end_date": "2024-01-01"},
        )
        assert response.status_code == 400

    def test_invalid_analysis_value_returns_422(self, client, seed_session):
        _seed(seed_session, "A", [Observation(date="2024-01-01", value=1.0)])
        _seed(seed_session, "B", [Observation(date="2024-01-01", value=1.0)])
        response = client.get("/api/v1/analysis/compare", params={"series_a": "A", "series_b": "B", "analysis": "not_real"})
        assert response.status_code == 422

    def test_missing_required_query_param_returns_422(self, client, seed_session):
        response = client.get("/api/v1/analysis/compare", params={"series_a": "A", "analysis": "aligned"})
        assert response.status_code == 422


def _pipeline_body(series_a_id, series_b_id, analysis="aligned", transform_a=None, transform_b=None, start_date=None, end_date=None):
    return {
        "series_a": {"series_id": series_a_id, "transformation": transform_a},
        "series_b": {"series_id": series_b_id, "transformation": transform_b},
        "analysis": analysis,
        "start_date": start_date,
        "end_date": end_date,
    }


class TestPipeline:
    def test_raw_raw(self, client, seed_session):
        _seed(seed_session, "A", [Observation(date="2024-01-01", value=1.0)])
        _seed(seed_session, "B", [Observation(date="2024-01-01", value=10.0)])
        response = client.post("/api/v1/analysis/pipeline", json=_pipeline_body("A", "B"))
        assert response.status_code == 200
        body = response.json()
        assert body["observations"][0]["value_a"] == 1.0 and body["observations"][0]["value_b"] == 10.0
        assert body["series_a"]["transformation"] is None

    def test_raw_transformed(self, client, seed_session):
        _seed(seed_session, "A", [Observation(date="2024-01-01", value=1.0), Observation(date="2024-02-01", value=2.0)])
        _seed(seed_session, "B", [Observation(date="2024-01-01", value=100.0), Observation(date="2024-02-01", value=110.0)])
        response = client.post("/api/v1/analysis/pipeline", json=_pipeline_body("A", "B", transform_b={"type": "percent_change"}))
        by_date = {o["date"]: o for o in response.json()["observations"]}
        assert by_date["2024-02-01"]["value_b"] == 10.0

    def test_transformed_raw(self, client, seed_session):
        _seed(seed_session, "A", [Observation(date="2024-01-01", value=100.0), Observation(date="2024-02-01", value=110.0)])
        _seed(seed_session, "B", [Observation(date="2024-01-01", value=1.0), Observation(date="2024-02-01", value=2.0)])
        response = client.post("/api/v1/analysis/pipeline", json=_pipeline_body("A", "B", transform_a={"type": "percent_change"}))
        by_date = {o["date"]: o for o in response.json()["observations"]}
        assert by_date["2024-02-01"]["value_a"] == 10.0

    def test_transformed_transformed(self, client, seed_session):
        _seed(seed_session, "A", [Observation(date="2024-01-01", value=100.0), Observation(date="2024-02-01", value=110.0)])
        _seed(seed_session, "B", [Observation(date="2024-01-01", value=200.0), Observation(date="2024-02-01", value=210.0)])
        response = client.post(
            "/api/v1/analysis/pipeline",
            json=_pipeline_body("A", "B", transform_a={"type": "percent_change"}, transform_b={"type": "percent_change"}),
        )
        by_date = {o["date"]: o for o in response.json()["observations"]}
        assert by_date["2024-02-01"]["value_a"] == 10.0
        assert by_date["2024-02-01"]["value_b"] == 5.0

    def test_absolute_change(self, client, seed_session):
        _seed(seed_session, "A", [Observation(date="2024-01-01", value=100.0), Observation(date="2024-02-01", value=110.0)])
        _seed(seed_session, "B", [Observation(date="2024-01-01", value=1.0), Observation(date="2024-02-01", value=2.0)])
        response = client.post("/api/v1/analysis/pipeline", json=_pipeline_body("A", "B", transform_a={"type": "absolute_change"}))
        by_date = {o["date"]: o for o in response.json()["observations"]}
        assert by_date["2024-02-01"]["value_a"] == 10.0

    def test_moving_average(self, client, seed_session):
        _seed(seed_session, "A", [Observation(date=f"2024-0{m}-01", value=float(m * 10)) for m in range(1, 4)])
        _seed(seed_session, "B", [Observation(date=f"2024-0{m}-01", value=1.0) for m in range(1, 4)])
        response = client.post(
            "/api/v1/analysis/pipeline", json=_pipeline_body("A", "B", transform_a={"type": "moving_average", "window": 2})
        )
        by_date = {o["date"]: o for o in response.json()["observations"]}
        assert by_date["2024-03-01"]["value_a"] == 25.0

    def test_transformation_before_alignment_through_http(self, client, seed_session):
        """The same decisive ordering test from Increment 011, now
        through the full HTTP path. A=[Jan:100,Feb:110,Mar:121],
        B=[Jan:10,Mar:30] (missing Feb). Correct (transform-before-
        align) answer for A's Mar percent_change: 10.0. Wrong (align-
        before-transform) answer: 21.0."""
        _seed(seed_session, "A", [Observation(date="2024-01-01", value=100.0), Observation(date="2024-02-01", value=110.0), Observation(date="2024-03-01", value=121.0)])
        _seed(seed_session, "B", [Observation(date="2024-01-01", value=10.0), Observation(date="2024-03-01", value=30.0)])
        response = client.post("/api/v1/analysis/pipeline", json=_pipeline_body("A", "B", transform_a={"type": "percent_change"}))
        by_date = {o["date"]: o for o in response.json()["observations"]}
        assert by_date["2024-03-01"]["value_a"] == 10.0  # NOT 21.0

    def test_boundary_context_independent_per_series_through_http(self, client, seed_session):
        _seed(seed_session, "A", [Observation(date="2024-01-01", value=100.0), Observation(date="2024-02-01", value=110.0)])
        _seed(seed_session, "B", [Observation(date="2024-01-01", value=5.0), Observation(date="2024-02-01", value=8.0)])
        response = client.post(
            "/api/v1/analysis/pipeline",
            json=_pipeline_body(
                "A", "B", transform_a={"type": "percent_change"}, transform_b={"type": "percent_change"}, start_date="2024-02-01"
            ),
        )
        body = response.json()
        assert len(body["observations"]) == 1
        assert body["observations"][0]["value_a"] == 10.0
        assert body["observations"][0]["value_b"] == 60.0

    def test_aligned_analysis(self, client, seed_session):
        _seed(seed_session, "A", [Observation(date="2024-01-01", value=1.0)])
        _seed(seed_session, "B", [Observation(date="2024-01-01", value=2.0)])
        response = client.post("/api/v1/analysis/pipeline", json=_pipeline_body("A", "B", analysis="aligned"))
        assert response.json()["observations"][0]["value_a"] == 1.0

    def test_spread_analysis(self, client, seed_session):
        _seed(seed_session, "A", [Observation(date="2024-01-01", value=10.0)])
        _seed(seed_session, "B", [Observation(date="2024-01-01", value=4.0)])
        response = client.post("/api/v1/analysis/pipeline", json=_pipeline_body("A", "B", analysis="spread"))
        assert response.json()["observations"][0]["spread"] == 6.0

    def test_correlation_analysis(self, client, seed_session):
        _seed(seed_session, "A", [Observation(date=f"2024-0{m}-01", value=float(m)) for m in range(1, 5)])
        _seed(seed_session, "B", [Observation(date=f"2024-0{m}-01", value=float(2 * m)) for m in range(1, 5)])
        response = client.post("/api/v1/analysis/pipeline", json=_pipeline_body("A", "B", analysis="correlation"))
        body = response.json()
        assert body["correlation"] == 1.0
        assert body["observations"] == []


class TestPipelineValidation:
    def _valid_body(self):
        return _pipeline_body("A", "B")

    def test_unknown_top_level_field_returns_422(self, client, seed_session):
        body = self._valid_body()
        body["unexpected_field"] = "x"
        response = client.post("/api/v1/analysis/pipeline", json=body)
        assert response.status_code == 422

    def test_unknown_series_spec_field_returns_422(self, client, seed_session):
        body = self._valid_body()
        body["series_a"]["debug"] = True
        response = client.post("/api/v1/analysis/pipeline", json=body)
        assert response.status_code == 422

    def test_unknown_transformation_field_returns_422(self, client, seed_session):
        body = self._valid_body()
        body["series_a"]["transformation"] = {"type": "percent_change", "unexpected_field": "x"}
        response = client.post("/api/v1/analysis/pipeline", json=body)
        assert response.status_code == 422

    def test_invalid_transformation_type_returns_422(self, client, seed_session):
        body = self._valid_body()
        body["series_a"]["transformation"] = {"type": "not_a_real_transform"}
        response = client.post("/api/v1/analysis/pipeline", json=body)
        assert response.status_code == 422

    def test_invalid_analysis_type_returns_422(self, client, seed_session):
        body = self._valid_body()
        body["analysis"] = "not_real"
        response = client.post("/api/v1/analysis/pipeline", json=body)
        assert response.status_code == 422

    def test_moving_average_window_out_of_bounds_returns_422(self, client, seed_session):
        body = self._valid_body()
        body["series_a"]["transformation"] = {"type": "moving_average", "window": 1}
        response = client.post("/api/v1/analysis/pipeline", json=body)
        assert response.status_code == 422  # structural bound (ge=2)

    def test_missing_moving_average_window_returns_400(self, client, seed_session):
        """Structurally valid (window is optional in the schema);
        semantically invalid (moving_average requires one) --
        AnalysisService's own InvalidWindowError, mapped to 400."""
        _seed(seed_session, "A", [Observation(date="2024-01-01", value=1.0)])
        _seed(seed_session, "B", [Observation(date="2024-01-01", value=1.0)])
        body = self._valid_body()
        body["series_a"]["transformation"] = {"type": "moving_average"}
        response = client.post("/api/v1/analysis/pipeline", json=body)
        assert response.status_code == 400

    def test_window_supplied_for_inapplicable_transformation_returns_400(self, client, seed_session):
        _seed(seed_session, "A", [Observation(date="2024-01-01", value=1.0)])
        _seed(seed_session, "B", [Observation(date="2024-01-01", value=1.0)])
        body = self._valid_body()
        body["series_a"]["transformation"] = {"type": "percent_change", "window": 5}
        response = client.post("/api/v1/analysis/pipeline", json=body)
        assert response.status_code == 400

    def test_malformed_date_returns_422(self, client, seed_session):
        body = self._valid_body()
        body["start_date"] = "not-a-date"
        response = client.post("/api/v1/analysis/pipeline", json=body)
        assert response.status_code == 422

    def test_invalid_date_relationship_returns_400(self, client, seed_session):
        _seed(seed_session, "A", [Observation(date="2024-01-01", value=1.0)])
        _seed(seed_session, "B", [Observation(date="2024-01-01", value=1.0)])
        body = self._valid_body()
        body["start_date"] = "2024-03-01"
        body["end_date"] = "2024-01-01"
        response = client.post("/api/v1/analysis/pipeline", json=body)
        assert response.status_code == 400

    def test_unknown_series_returns_404(self, client, seed_session):
        _seed(seed_session, "B", [Observation(date="2024-01-01", value=1.0)])
        response = client.post("/api/v1/analysis/pipeline", json=_pipeline_body("NOPE", "B"))
        assert response.status_code == 404


class TestAnalysisApiReadPathNonMutationAndDeterminism:
    def test_compare_and_pipeline_do_not_mutate_persisted_data(self, client, seed_session):
        _seed(seed_session, "A", [Observation(date="2024-01-01", value=1.0)])
        _seed(seed_session, "B", [Observation(date="2024-01-01", value=10.0)])
        before = seed_session.execute(text("SELECT observation_date, value FROM economic_observations ORDER BY observation_date")).fetchall()

        client.get("/api/v1/analysis/compare", params={"series_a": "A", "series_b": "B", "analysis": "correlation"})
        client.post("/api/v1/analysis/pipeline", json=_pipeline_body("A", "B", transform_a={"type": "percent_change"}))

        after = seed_session.execute(text("SELECT observation_date, value FROM economic_observations ORDER BY observation_date")).fetchall()
        assert before == after

    def test_repeated_pipeline_request_returns_identical_response(self, client, seed_session):
        _seed(seed_session, "A", [Observation(date="2024-01-01", value=1.0), Observation(date="2024-02-01", value=2.0)])
        _seed(seed_session, "B", [Observation(date="2024-01-01", value=10.0), Observation(date="2024-02-01", value=20.0)])
        body = _pipeline_body("A", "B", transform_a={"type": "percent_change"})
        first = client.post("/api/v1/analysis/pipeline", json=body).json()
        second = client.post("/api/v1/analysis/pipeline", json=body).json()
        assert first == second

    def test_repeated_compare_request_returns_identical_response(self, client, seed_session):
        _seed(seed_session, "A", [Observation(date="2024-01-01", value=1.0)])
        _seed(seed_session, "B", [Observation(date="2024-01-01", value=10.0)])
        params = {"series_a": "A", "series_b": "B", "analysis": "correlation"}
        first = client.get("/api/v1/analysis/compare", params=params).json()
        second = client.get("/api/v1/analysis/compare", params=params).json()
        assert first == second
