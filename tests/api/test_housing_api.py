"""The Housing HTTP surface (Increment #45).

Two routes, and the division between them is the point: the GET holds no
provider client and can never fetch; the POST is operator-only and is the
only place a credential is read.
"""

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import text

from app.repositories.housing_repository import HousingProvenanceRecord, HousingRepository

pytestmark = pytest.mark.api

PERMITS_SAAR = "us.housing.units-authorized.saar.monthly"
HOUSING_URL = "/api/v1/housing"
SYNC_URL = "/api/v1/housing/sync"


@pytest.fixture
def housing_seed_session(seed_session):
    """`seed_session` truncates series/observations; Housing also writes
    provenance, versions and ingestion runs, so those are cleaned too."""
    yield seed_session
    seed_session.rollback()
    seed_session.execute(
        text(
            "TRUNCATE TABLE observation_provenance, observation_versions, housing_ingestion_runs "
            "RESTART IDENTITY CASCADE"
        )
    )
    seed_session.commit()


def _seed(session, values: dict[date, float]) -> None:
    repo = HousingRepository(session)
    series = repo.ensure_series(
        storage_series_id=PERMITS_SAAR,
        concept_id=PERMITS_SAAR,
        title="Privately-owned housing units authorized by building permits (seasonally adjusted annual rate)",
        units="Housing units, seasonally adjusted annual rate",
        source="CENSUS",
    )
    for period, value in sorted(values.items()):
        repo.upsert_observation(
            series=series,
            observation_date=period,
            value=value,
            provenance=HousingProvenanceRecord(
                provider="CENSUS",
                dataset="timeseries/eits/resconst",
                source_series_field="APERMITS/TOTAL",
                source_url="https://www.census.gov/construction/nrc/",
                retrieved_at=datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc),
            ),
            baseline=True,
        )
    session.commit()


class TestRead:
    def test_an_empty_environment_returns_200_not_an_error(self, client) -> None:
        """Missing economic data and infrastructure failure are different
        outcomes, and only the second is an error."""
        response = client.get(HOUSING_URL)

        assert response.status_code == 200
        body = response.json()
        assert body["as_of_period"] is None
        assert len(body["stages"]) == 3
        assert all(stage["pace"]["available"] is False for stage in body["stages"])

    def test_it_returns_the_published_figures(self, client, housing_seed_session) -> None:
        _seed(housing_seed_session, {date(2026, 7, 1): 1_433_000.0, date(2026, 8, 1): 1_394_000.0})

        body = client.get(HOUSING_URL).json()

        permits = next(stage for stage in body["stages"] if stage["stage"] == "PERMITS")["pace"]
        assert permits["available"] is True
        assert permits["value"] == 1_394_000.0
        assert round(permits["change_percent_from_previous"], 1) == -2.7

    def test_the_response_carries_no_state_or_methodology(self, client) -> None:
        body = client.get(HOUSING_URL).json()

        assert "state" not in body
        assert "methodology_id" not in body
        for stage in body["stages"]:
            for measure in (stage["pace"], stage["actual"]):
                assert "state" not in measure
                assert "score" not in measure

    def test_the_response_carries_the_census_attribution_verbatim(self, client) -> None:
        body = client.get(HOUSING_URL).json()

        assert body["attribution"] == (
            "This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau."
        )

    def test_the_response_carries_the_saar_explanation(self, client) -> None:
        body = client.get(HOUSING_URL).json()
        assert "not a count of homes" in body["saar_explanation"]

    def test_the_response_names_both_publishers(self, client) -> None:
        body = client.get(HOUSING_URL).json()
        assert "Housing and Urban Development" in body["source_statement"]

    def test_the_route_is_not_mounted_under_monitors(self, client) -> None:
        """Housing has no methodology and no state, so mounting it beside
        the three monitor routes would make the URL promise a conclusion
        the payload cannot support."""
        assert client.get("/api/v1/monitors/housing").status_code == 404

    def test_no_credential_appears_anywhere_in_the_response(self, client, housing_seed_session) -> None:
        _seed(housing_seed_session, {date(2026, 8, 1): 1_394_000.0})

        raw = client.get(HOUSING_URL).text

        assert "key=" not in raw
        assert "api.census.gov" not in raw
        assert "CENSUS_API_KEY" not in raw

    def test_the_read_never_reaches_census(self, client, housing_seed_session, monkeypatch) -> None:
        """Structurally guaranteed by the import graph; asserted
        behaviourally here as well, because this is the property that
        stops a page view spending an authenticated quota."""
        import app.clients.census as census_module

        def explode(*args, **kwargs):  # pragma: no cover
            raise AssertionError("the read path constructed a Census client")

        monkeypatch.setattr(census_module, "CensusClient", explode)
        _seed(housing_seed_session, {date(2026, 8, 1): 1_394_000.0})

        assert client.get(HOUSING_URL).status_code == 200

    def test_the_read_writes_nothing(self, client, housing_seed_session) -> None:
        _seed(housing_seed_session, {date(2026, 8, 1): 1_394_000.0})
        before = housing_seed_session.execute(text("SELECT count(*) FROM observation_versions")).scalar_one()

        client.get(HOUSING_URL)
        client.get(HOUSING_URL)

        after = housing_seed_session.execute(text("SELECT count(*) FROM observation_versions")).scalar_one()
        assert before == after


class TestSyncAuthorization:
    def test_sync_requires_the_operator_token_when_one_is_configured(self, client, monkeypatch) -> None:
        from app.core.config import settings

        monkeypatch.setattr(settings, "operator_token", "test-sentinel-operator-token")

        assert client.post(SYNC_URL).status_code == 401

    def test_a_wrong_operator_token_is_rejected(self, client, monkeypatch) -> None:
        from app.core.config import settings

        monkeypatch.setattr(settings, "operator_token", "test-sentinel-operator-token")

        response = client.post(SYNC_URL, headers={"X-Operator-Token": "wrong"})
        assert response.status_code == 401


class TestSyncConfiguration:
    def test_sync_without_a_census_key_is_503_and_names_the_variable(self, client, monkeypatch) -> None:
        """A configuration problem, reported as one -- and the detail names
        the VARIABLE, never a value."""
        from app.core.config import settings

        monkeypatch.setattr(settings, "census_api_key", None)

        response = client.post(SYNC_URL)

        assert response.status_code == 503
        assert "CENSUS_API_KEY" in response.json()["detail"]

    def test_the_unconfigured_error_reveals_no_value(self, client, monkeypatch) -> None:
        from app.core.config import settings

        monkeypatch.setattr(settings, "census_api_key", None)

        detail = client.post(SYNC_URL).json()["detail"]
        assert "=" not in detail.replace("CENSUS_API_KEY", "")

    def test_census_configured_is_a_boolean_not_the_value(self) -> None:
        """The only thing any caller outside the client needs to know
        about the credential, and safe to log or return."""
        from app.core.config import Settings

        settings = Settings()
        settings.census_api_key = "sentinel-not-a-real-key"
        assert settings.census_configured is True
        settings.census_api_key = None
        assert settings.census_configured is False


class TestSyncBehaviour:
    def test_a_successful_sync_reports_counts_and_no_credential(
        self, client, housing_seed_session, monkeypatch
    ) -> None:
        from datetime import date as date_type

        import app.api.housing as housing_api
        from app.clients.census import CensusResconstRow

        class StubClient:
            def __init__(self, *args, **kwargs):
                pass

            def get_resconst(self, time_expression, dataset=None):
                return (
                    [
                        CensusResconstRow(
                            period=date_type(2026, 8, 1),
                            category_code="APERMITS",
                            data_type_code="TOTAL",
                            seasonally_adjusted=True,
                            is_error_measure=False,
                            value=1394.0,
                        )
                    ],
                    [],
                )

        monkeypatch.setattr(housing_api, "CensusClient", StubClient)
        monkeypatch.setattr("app.core.config.settings.census_api_key", "sentinel-not-a-real-key")

        response = client.post(SYNC_URL)

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "SUCCEEDED"
        assert body["provider"] == "CENSUS"
        assert body["rows_received"] == 1
        assert "sentinel-not-a-real-key" not in response.text
        assert "key" not in body

    def test_an_upstream_failure_is_a_recorded_failed_run_not_a_5xx(
        self, client, housing_seed_session, monkeypatch
    ) -> None:
        """The run genuinely happened, so it is reported -- the same
        contract `POST /api/v1/rates/sync` uses."""
        import app.api.housing as housing_api
        from app.clients.census import CensusUpstreamError

        class StubClient:
            def __init__(self, *args, **kwargs):
                pass

            def get_resconst(self, time_expression, dataset=None):
                raise CensusUpstreamError("upstream is unhappy")

        monkeypatch.setattr(housing_api, "CensusClient", StubClient)
        monkeypatch.setattr("app.core.config.settings.census_api_key", "sentinel-not-a-real-key")

        response = client.post(SYNC_URL)

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "FAILED"
        assert body["error_class"] == "CensusUpstreamError"
        # A class name, never the exception's message.
        assert "upstream is unhappy" not in response.text

    @pytest.mark.parametrize("lookback", [0, 241])
    def test_an_out_of_range_lookback_is_rejected_by_validation(
        self, client, monkeypatch, lookback: int
    ) -> None:
        monkeypatch.setattr("app.core.config.settings.census_api_key", "sentinel-not-a-real-key")

        assert client.post(f"{SYNC_URL}?lookback_months={lookback}").status_code == 422


class TestIntelligenceSurface:
    def test_the_intelligence_endpoint_accepts_housing_as_a_world_filter(self, client) -> None:
        response = client.get("/api/v1/intelligence?world=housing")
        assert response.status_code == 200
        assert response.json()["items"] == []

    def test_an_unknown_world_is_still_rejected(self, client) -> None:
        """The world union stays closed: adding Housing must not have
        widened it to arbitrary strings."""
        assert client.get("/api/v1/intelligence?world=crypto").status_code == 422


class TestOtherRoutesUnaffected:
    @pytest.mark.parametrize(
        "url",
        [
            "/api/v1/monitors/rates",
            "/api/v1/monitors/inflation",
            "/api/v1/monitors/labor",
            "/api/v1/intelligence",
            "/health",
        ],
    )
    def test_existing_routes_still_respond(self, client, url: str) -> None:
        assert client.get(url).status_code == 200
