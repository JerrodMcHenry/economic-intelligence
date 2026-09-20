"""HTTP client for the U.S. Treasury's Daily Treasury Interest Rate
XML feeds (Increment #29).

Owns all Treasury-specific HTTP communication: URL construction,
timeouts, response-size bounding, XML parsing, and translating failures
into a small set of typed exceptions -- mirroring
`app.clients.fred.FREDClient`'s own boundary exactly. Returns normalized
`(date, {field: value})` rows; deciding which fields become which
canonical series, and persisting them, is the service layer's job.

SECURITY (Increment #29's own requirement): the base URL and the set of
requestable datasets are both allow-listed constants in this module. No
caller -- and therefore no user input -- can direct this client at an
arbitrary host, path, or dataset. `dataset` is validated against
`ALLOWED_DATASETS` before any request is built, and the only other
caller-supplied value (`month`) is rendered through strict integer
formatting, never string interpolation of raw input.

No API key: these feeds are unauthenticated. Nothing in this module
reads configuration or secrets.
"""

from dataclasses import dataclass
from datetime import date
from xml.etree import ElementTree

import httpx

TREASURY_BASE_URL = "https://home.treasury.gov"
_XML_PATH = "/resource-center/data-chart-center/interest-rates/pages/xml"

# The ONLY datasets this client may request. Adding one is a deliberate
# code change, reviewed against its licensing, never a runtime decision.
NOMINAL_DATASET = "daily_treasury_yield_curve"
REAL_DATASET = "daily_treasury_real_yield_curve"
ALLOWED_DATASETS: frozenset[str] = frozenset({NOMINAL_DATASET, REAL_DATASET})

# Bounded response: a single month of either feed is ~20-60KB. One
# megabyte is far above any legitimate payload and far below anything
# that could exhaust memory if the upstream misbehaves.
MAX_RESPONSE_BYTES = 1_048_576

_DATA_NS = "{http://schemas.microsoft.com/ado/2007/08/dataservices}"
_METADATA_NS = "{http://schemas.microsoft.com/ado/2007/08/dataservices/metadata}"
_ATOM_NS = "{http://www.w3.org/2005/Atom}"

_DATE_FIELD = "NEW_DATE"


@dataclass(frozen=True)
class TreasuryRateRow:
    """One published business session from one Treasury dataset:
    the observation date plus every rate field present for it.

    `values` holds only fields the feed actually published with a
    parseable numeric value -- a field the feed marked null, omitted, or
    published unparseably is simply absent from the mapping, never
    present as 0.0 or None-as-a-number.
    """

    observation_date: date
    values: dict[str, float]


class TreasuryError(Exception):
    """Base error for all Treasury client failures."""


class TreasuryTimeoutError(TreasuryError):
    """A request to the Treasury feed did not complete within the timeout."""


class TreasuryUpstreamError(TreasuryError):
    """Treasury could not be reached, or returned an unexpected/malformed response."""


class TreasuryClient:
    """Thin synchronous client for the two Treasury rate feeds we use."""

    def __init__(self, base_url: str = TREASURY_BASE_URL, timeout: float = 30.0):
        self._base_url = base_url
        self._timeout = timeout

    def get_month(self, dataset: str, year: int, month: int) -> list[TreasuryRateRow]:
        """Fetch one calendar month of one allow-listed dataset.

        Returns the month's rows in ascending date order. A month the
        feed has no data for returns an empty list -- an ordinary,
        non-exceptional outcome (a future month, or a month before the
        dataset began).
        """
        if dataset not in ALLOWED_DATASETS:
            raise ValueError(f"Dataset '{dataset}' is not allow-listed for the Treasury client")
        if not (1 <= month <= 12):
            raise ValueError("month must be between 1 and 12")
        if not (1990 <= year <= 2999):
            raise ValueError("year is outside the supported range")

        payload = self._get(
            {
                "data": dataset,
                # Strict integer formatting -- never raw caller input.
                "field_tdr_date_value_month": f"{year:04d}{month:02d}",
            }
        )
        return self._parse(payload, dataset)

    def _get(self, params: dict[str, str]) -> bytes:
        url = f"{self._base_url}{_XML_PATH}"
        try:
            with httpx.Client(timeout=self._timeout, follow_redirects=False) as client:
                response = client.get(url, params=params)
        except httpx.TimeoutException as exc:
            raise TreasuryTimeoutError("Treasury request timed out") from exc
        except httpx.HTTPError as exc:
            raise TreasuryUpstreamError(f"Failed to reach the Treasury feed: {exc}") from exc

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise TreasuryUpstreamError(
                f"Treasury returned unexpected status {response.status_code}"
            ) from exc

        content = response.content
        if len(content) > MAX_RESPONSE_BYTES:
            raise TreasuryUpstreamError(
                f"Treasury response exceeded the {MAX_RESPONSE_BYTES}-byte bound"
            )
        return content

    @staticmethod
    def _parse(payload: bytes, dataset: str) -> list[TreasuryRateRow]:
        try:
            root = ElementTree.fromstring(payload)
        except ElementTree.ParseError as exc:
            raise TreasuryUpstreamError(f"Treasury returned malformed XML for '{dataset}'") from exc

        rows: list[TreasuryRateRow] = []
        for properties in root.iter(f"{_METADATA_NS}properties"):
            observation_date = TreasuryClient._parse_date(properties, dataset)
            if observation_date is None:
                continue

            values: dict[str, float] = {}
            for element in properties:
                if not element.tag.startswith(_DATA_NS):
                    continue
                field = element.tag[len(_DATA_NS) :]
                if field == _DATE_FIELD:
                    continue
                if element.get(f"{_METADATA_NS}null") == "true":
                    continue
                text = (element.text or "").strip()
                if not text:
                    continue
                try:
                    values[field] = float(text)
                except ValueError:
                    # A non-numeric rate field is skipped, not guessed
                    # at and not fatal: other fields in the same row may
                    # be perfectly usable.
                    continue

            rows.append(TreasuryRateRow(observation_date=observation_date, values=values))

        if not rows and root.find(f"{_ATOM_NS}entry") is not None:
            raise TreasuryUpstreamError(f"Treasury returned entries without parseable properties for '{dataset}'")

        return sorted(rows, key=lambda row: row.observation_date)

    @staticmethod
    def _parse_date(properties: ElementTree.Element, dataset: str) -> date | None:
        element = properties.find(f"{_DATA_NS}{_DATE_FIELD}")
        if element is None or not (element.text or "").strip():
            return None
        text = element.text.strip()
        # The feed publishes "2026-09-18T00:00:00"; take the date part
        # only -- these are date-level facts with no meaningful time.
        try:
            return date.fromisoformat(text.split("T", 1)[0])
        except ValueError as exc:
            raise TreasuryUpstreamError(f"Treasury returned an unparseable date for '{dataset}'") from exc
