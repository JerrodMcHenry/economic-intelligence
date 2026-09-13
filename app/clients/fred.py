"""HTTP client for the FRED (Federal Reserve Economic Data) REST API.

Owns all FRED-specific HTTP communication: request construction, auth,
timeouts, and translating FRED's error responses into a small set of
typed exceptions. Returns raw (but response-shape-checked) dictionaries;
normalizing that data into our own response contract is the caller's
(service layer's) job.
"""

from dataclasses import dataclass
from datetime import date

import httpx

FRED_BASE_URL = "https://api.stlouisfed.org/fred"


@dataclass(frozen=True)
class FredReleaseDate:
    """One normalized `(release_id, date)` pair from FRED's release-dates
    data -- schedule metadata only. FRED's raw payload also carries
    `release_name`, `realtime_start`/`realtime_end`, and (for some
    requests) `release_last_updated`; none of those cross the client
    boundary here (see docs/architecture/release-intelligence-v1.md #3),
    and this being present is never proof that observation data is
    actually available -- it is a schedule fact only."""

    release_id: str
    date: date


class FREDError(Exception):
    """Base error for all FRED client failures."""


class FREDSeriesNotFoundError(FREDError):
    """The requested series does not exist in FRED."""


class FREDAuthError(FREDError):
    """FRED rejected our API key (missing, malformed, or not registered)."""


class FREDTimeoutError(FREDError):
    """A request to FRED did not complete within the configured timeout."""


class FREDUpstreamError(FREDError):
    """FRED could not be reached, or returned an unexpected/malformed response."""


class FREDClient:
    """Thin synchronous client for the parts of the FRED REST API we use."""

    def __init__(self, api_key: str, base_url: str = FRED_BASE_URL, timeout: float = 10.0):
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout

    def get_series_info(self, series_id: str) -> dict:
        """Fetch series metadata (title, units, etc.) for a series."""
        data = self._get("/series", {"series_id": series_id})
        series_list = data.get("seriess") or []
        if not series_list:
            raise FREDUpstreamError(f"FRED returned no metadata for series '{series_id}'")
        return series_list[0]

    def get_observations(self, series_id: str, limit: int = 10) -> list[dict]:
        """Fetch the most recent `limit` observations for a series, newest first."""
        data = self._get(
            "/series/observations",
            {"series_id": series_id, "limit": limit, "sort_order": "desc"},
        )
        observations = data.get("observations")
        if observations is None:
            raise FREDUpstreamError(f"FRED returned no observations payload for series '{series_id}'")
        return observations

    def search_series(self, search_text: str, limit: int = 5) -> list[dict]:
        """Full-text search FRED's series catalog (fred/series/search) --
        metadata only (id, title, frequency, units, seasonal_adjustment,
        observation_start/end, popularity, ...), never observation values.

        An empty/zero-match search is a normal, successful outcome (FRED
        returns `200` with an empty `seriess` list) -- returns `[]`, not
        an error.
        """
        data = self._get(
            "/series/search",
            {
                "search_text": search_text,
                "search_type": "full_text",
                "limit": limit,
                "order_by": "search_rank",
                "sort_order": "desc",
            },
        )
        return data.get("seriess") or []

    def get_release_dates(self, release_id: str) -> list[FredReleaseDate]:
        """Fetch one release's scheduled/published dates, date-level only
        (see `FredReleaseDate`).

        Requests dates FRED has not yet attached data to as well as ones
        it has (`include_release_dates_with_no_data`) -- otherwise
        upcoming/scheduled occurrences would never be visible, only past
        ones. A returned date is a schedule fact only; it does not mean
        data is available for that date (see
        docs/architecture/release-intelligence-v1.md #3).
        """
        data = self._get(
            "/release/dates",
            {"release_id": release_id, "include_release_dates_with_no_data": "true"},
        )
        raw_dates = data.get("release_dates")
        if raw_dates is None:
            raise FREDUpstreamError(f"FRED returned no release-dates payload for release '{release_id}'")

        try:
            return [FredReleaseDate(release_id=str(entry["release_id"]), date=date.fromisoformat(entry["date"])) for entry in raw_dates]
        except (KeyError, TypeError, ValueError) as exc:
            raise FREDUpstreamError(f"FRED returned malformed release-dates data for release '{release_id}'") from exc

    def _get(self, path: str, params: dict) -> dict:
        query = {**params, "api_key": self._api_key, "file_type": "json"}

        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.get(f"{self._base_url}{path}", params=query)
        except httpx.TimeoutException as exc:
            raise FREDTimeoutError(f"FRED request to '{path}' timed out") from exc
        except httpx.HTTPError as exc:
            raise FREDUpstreamError(f"Failed to reach FRED API at '{path}': {exc}") from exc

        if response.status_code == 400:
            raise self._error_for_bad_request(response)

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise FREDUpstreamError(
                f"FRED returned unexpected status {response.status_code} for '{path}'"
            ) from exc

        try:
            return response.json()
        except ValueError as exc:
            raise FREDUpstreamError(f"FRED returned a non-JSON response for '{path}'") from exc

    @staticmethod
    def _error_for_bad_request(response: httpx.Response) -> FREDError:
        # FRED reports both invalid series IDs and API key problems as
        # HTTP 400, distinguished only by error_message text.
        try:
            message = response.json().get("error_message", "")
        except ValueError:
            message = ""

        lowered = message.lower()
        if "api_key" in lowered:
            return FREDAuthError(message or "FRED rejected the configured API key")
        if "series" in lowered:
            return FREDSeriesNotFoundError(message or "Series not found")
        return FREDUpstreamError(message or "FRED rejected the request")
