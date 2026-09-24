"""U.S. Bureau of Labor Statistics Public Data API client (Increment #56A).

One method, one POST: monthly observations for up to four series over a
bounded range of calendar years. Everything about the provider's shape
is verified against a real response recorded on 2026-09-24
(`tests/fixtures/bls_v1_2017_2026.json`) and against
`bls.gov/developers/api_faqs.htm`, not assumed:

- **v1, keyless:** 25 queries/day, 25 series per query, 10 years per
  query. **v2, registered key:** 500/day, 50 series, 20 years. The
  import needs exactly one query either way.
- **The key travels in the POST body**, never in a URL, so it cannot
  reach an access log, a proxy log or a chained exception. `__repr__`
  redacts it.
- **Values are the published decimal strings** (`"334.131"`), parsed
  once with `float()`. That is the conversion FRED's path applies, which
  is why the #54B comparison matched 358/358. `"-"` means BLS published
  the period as unavailable (for example October 2025: "Data unavailable
  due to the 2025 lapse in appropriations") and becomes `None`, never
  zero.
- **Only `M01`..`M12` are monthly observations.** `M13` is an annual
  average and is skipped.
- A quota refusal arrives as HTTP 200 with
  `status: REQUEST_NOT_PROCESSED`, so the envelope is checked, not only
  the HTTP status.
"""

import math
import re
from datetime import date

from app.clients.bounded_http import (
    ProviderRateLimitedError,
    ProviderResponseError,
    request,
)
from app.clients.provider_observation import FirstPartyObservation

PROVIDER = "BLS"

V1_URL = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
V2_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

#: Per-query year spans, from the API FAQ. Enforced here so a request the
#: provider would silently truncate is refused before it is sent.
MAX_YEARS_KEYLESS = 10
MAX_YEARS_WITH_KEY = 20

#: Four series over twenty years is ~40 KB; 2 MB is generous headroom and
#: still a hard bound.
MAX_RESPONSE_BYTES = 2 * 1024 * 1024

_SERIES_ID = re.compile(r"^[A-Z0-9]{5,20}$")
_MONTHLY_PERIOD = re.compile(r"^M(0[1-9]|1[0-2])$")
_UNAVAILABLE = "-"


class BLSClient:
    def __init__(self, api_key: str | None = None, timeout: float = 30.0, max_attempts: int = 2):
        self._api_key = api_key or None
        self._timeout = timeout
        self._max_attempts = max_attempts

    def __repr__(self) -> str:
        return f"BLSClient(version={self.api_version!r}, timeout={self._timeout!r}, api_key=<redacted>)"

    __str__ = __repr__

    @property
    def api_version(self) -> str:
        return "v2" if self._api_key else "v1"

    @property
    def max_years(self) -> int:
        return MAX_YEARS_WITH_KEY if self._api_key else MAX_YEARS_KEYLESS

    def get_monthly(self, series_ids: list[str], start_year: int, end_year: int) -> dict[str, list[FirstPartyObservation]]:
        """Monthly observations per requested series, ascending by period.

        Raises `ProviderResponseError` if any requested series is absent
        from an otherwise successful response: a partial answer to a
        request for four named series is not something to guess around.
        """
        if not series_ids or len(series_ids) > 25:
            raise ValueError("between 1 and 25 series per request")
        for series_id in series_ids:
            if not _SERIES_ID.match(series_id):
                raise ValueError(f"not a BLS series id: {series_id!r}")
        if not (1900 < start_year <= end_year):
            raise ValueError("start_year must not be after end_year")
        if end_year - start_year + 1 > self.max_years:
            raise ValueError(f"BLS {self.api_version} serves at most {self.max_years} years per request")

        body: dict[str, object] = {
            "seriesid": list(series_ids),
            "startyear": str(start_year),
            "endyear": str(end_year),
        }
        if self._api_key:
            body["registrationkey"] = self._api_key

        response = request(
            PROVIDER,
            "POST",
            V2_URL if self._api_key else V1_URL,
            json_body=body,
            max_bytes=MAX_RESPONSE_BYTES,
            timeout=self._timeout,
            max_attempts=self._max_attempts,
        )
        return parse_response(response.json(PROVIDER), series_ids)


def parse_response(payload: object, series_ids: list[str]) -> dict[str, list[FirstPartyObservation]]:
    """Validate the documented envelope and extract monthly observations."""
    if not isinstance(payload, dict):
        raise ProviderResponseError(PROVIDER, "response is not a JSON object")

    status = payload.get("status")
    if status == "REQUEST_NOT_PROCESSED":
        # The quota case. BLS's own message is not echoed: it is upstream
        # text, and the class name is what an operator acts on.
        raise ProviderRateLimitedError(PROVIDER, "request not processed (daily query limit or throttling)")
    if status != "REQUEST_SUCCEEDED":
        raise ProviderResponseError(PROVIDER, "unexpected response status")

    results = payload.get("Results")
    series_list = results.get("series") if isinstance(results, dict) else None
    if not isinstance(series_list, list):
        raise ProviderResponseError(PROVIDER, "response has no Results.series list")

    by_id: dict[str, list[FirstPartyObservation]] = {}
    for series in series_list:
        if not isinstance(series, dict) or not isinstance(series.get("data"), list):
            raise ProviderResponseError(PROVIDER, "malformed series entry")
        series_id = series.get("seriesID")
        if series_id not in series_ids:
            continue
        by_id[series_id] = sorted(
            (observation for item in series["data"] if (observation := _observation(item)) is not None),
            key=lambda observation: observation.period,
        )

    missing = [series_id for series_id in series_ids if series_id not in by_id]
    if missing:
        raise ProviderResponseError(PROVIDER, f"response omitted requested series {missing}")
    return by_id


def _observation(item: object) -> FirstPartyObservation | None:
    if not isinstance(item, dict):
        raise ProviderResponseError(PROVIDER, "malformed data point")
    period = item.get("period")
    if not isinstance(period, str) or not _MONTHLY_PERIOD.match(period):
        # M13 (annual average) and any non-monthly period: not an observation.
        return None
    year = item.get("year")
    if not isinstance(year, str) or not year.isdigit():
        raise ProviderResponseError(PROVIDER, "malformed year")

    raw = item.get("value")
    if raw == _UNAVAILABLE:
        value = None
    else:
        try:
            value = float(raw)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            raise ProviderResponseError(PROVIDER, "non-numeric value") from None
        if not math.isfinite(value):
            # `float()` accepts "nan" and "inf"; no statistic is either.
            raise ProviderResponseError(PROVIDER, "non-finite value")

    footnotes = tuple(
        sorted(note["code"] for note in item.get("footnotes") or [] if isinstance(note, dict) and note.get("code"))
    )
    return FirstPartyObservation(period=date(int(year), int(period[1:]), 1), value=value, footnotes=footnotes)
