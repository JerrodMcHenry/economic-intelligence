"""Unit tests for `FREDClient`'s release-date capability (Increment
#17A). No live network anywhere: `httpx.Client.get` is mocked directly
at the transport boundary -- one level below the FREDClient-*method*-
level mocking `tests/integration/test_discovery_service.py` already
uses (that level is right for proving a *service* composes FREDClient
calls correctly; this level proves the *client's* own request
construction and response normalization is correct, which nothing in
this project tested directly before this file).
"""

from datetime import date
from unittest.mock import Mock, patch

import httpx
import pytest

from app.clients.fred import FREDAuthError, FREDClient, FREDTimeoutError, FREDUpstreamError, FredReleaseDate

RELEASE_DATES_URL = "https://api.stlouisfed.org/fred/release/dates"


def _response(json_body: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code=status_code, json=json_body, request=httpx.Request("GET", RELEASE_DATES_URL))


@pytest.fixture
def client() -> FREDClient:
    return FREDClient(api_key="test-key-not-a-real-secret", timeout=1.0)


class TestGetReleaseDates:
    def test_normal_payload_is_normalized_into_release_date_and_date_only(self, client):
        payload = {
            "release_dates": [
                {"release_id": 10, "release_name": "Consumer Price Index", "date": "2026-08-13"},
                {"release_id": 10, "release_name": "Consumer Price Index", "date": "2026-09-11"},
            ]
        }
        with patch.object(httpx.Client, "get", return_value=_response(payload)):
            result = client.get_release_dates("10")

        assert result == [
            FredReleaseDate(release_id="10", date=date(2026, 8, 13)),
            FredReleaseDate(release_id="10", date=date(2026, 9, 11)),
        ]

    def test_raw_provider_fields_never_cross_the_client_boundary(self, client):
        """release_name/release_last_updated (and any other raw FRED
        field) must not survive normalization -- FredReleaseDate has
        exactly two fields, so there is no attribute for them to land
        in even if present in the raw payload."""
        payload = {
            "release_dates": [
                {
                    "release_id": 10,
                    "release_name": "Consumer Price Index",
                    "date": "2026-08-13",
                    "release_last_updated": "2026-08-13 08:30:00-05",
                }
            ]
        }
        with patch.object(httpx.Client, "get", return_value=_response(payload)):
            result = client.get_release_dates("10")

        assert result == [FredReleaseDate(release_id="10", date=date(2026, 8, 13))]
        assert set(vars(result[0]).keys()) == {"release_id", "date"}

    def test_empty_list_is_a_normal_successful_result_not_an_error(self, client):
        with patch.object(httpx.Client, "get", return_value=_response({"release_dates": []})):
            assert client.get_release_dates("10") == []

    def test_missing_release_dates_key_raises_upstream_error(self, client):
        with patch.object(httpx.Client, "get", return_value=_response({})):
            with pytest.raises(FREDUpstreamError):
                client.get_release_dates("10")

    def test_malformed_date_raises_upstream_error(self, client):
        payload = {"release_dates": [{"release_id": 10, "date": "not-a-date"}]}
        with patch.object(httpx.Client, "get", return_value=_response(payload)):
            with pytest.raises(FREDUpstreamError):
                client.get_release_dates("10")

    def test_missing_date_key_raises_upstream_error(self, client):
        payload = {"release_dates": [{"release_id": 10}]}
        with patch.object(httpx.Client, "get", return_value=_response(payload)):
            with pytest.raises(FREDUpstreamError):
                client.get_release_dates("10")

    def test_missing_release_id_key_raises_upstream_error(self, client):
        payload = {"release_dates": [{"date": "2026-08-13"}]}
        with patch.object(httpx.Client, "get", return_value=_response(payload)):
            with pytest.raises(FREDUpstreamError):
                client.get_release_dates("10")

    def test_auth_error_maps_to_fred_auth_error(self, client):
        body = {
            "error_code": 400,
            "error_message": "Bad Request. The value for variable api_key is not a 32 character alpha-numeric lower-case string.",
        }
        with patch.object(httpx.Client, "get", return_value=_response(body, status_code=400)):
            with pytest.raises(FREDAuthError):
                client.get_release_dates("10")

    def test_timeout_maps_to_fred_timeout_error(self, client):
        with patch.object(httpx.Client, "get", side_effect=httpx.TimeoutException("timed out")):
            with pytest.raises(FREDTimeoutError):
                client.get_release_dates("10")

    def test_upstream_5xx_maps_to_fred_upstream_error(self, client):
        with patch.object(httpx.Client, "get", return_value=_response({}, status_code=500)):
            with pytest.raises(FREDUpstreamError):
                client.get_release_dates("10")

    def test_requests_dates_without_data_and_the_requested_release_id(self, client):
        """Proves the request actually asks FRED for dates that don't
        have data yet -- otherwise scheduled/upcoming occurrences would
        never be visible, only past ones (see
        docs/architecture/release-intelligence-v1.md #9)."""
        mock_get = Mock(return_value=_response({"release_dates": []}))
        with patch.object(httpx.Client, "get", mock_get):
            client.get_release_dates("10")

        params = mock_get.call_args.kwargs["params"]
        assert params["release_id"] == "10"
        assert params["include_release_dates_with_no_data"] == "true"
