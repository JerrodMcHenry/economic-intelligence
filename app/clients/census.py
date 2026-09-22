"""HTTP client for the U.S. Census Bureau Data API, New Residential
Construction (`timeseries/eits/resconst`) — Increment #45.

Owns all Census-specific HTTP communication: URL construction,
authentication, timeouts, response-size bounding, the API's tabular
JSON shape, and translating failures into a small set of typed
exceptions. Mirrors `app.clients.treasury.TreasuryClient`'s boundary
exactly. Returns validated `CensusResconstRow` records; deciding which
rows become which canonical series, and persisting them, is the
service layer's job.

THE CREDENTIAL (the one thing this module does that Treasury's does not)
-----------------------------------------------------------------------
Census requires an API key — an unkeyed request is redirected to
Census's own "Missing Key" page rather than served — so this is the
first provider client here that holds a secret. Four rules, each with a
test:

1. **The key is passed as a request parameter and never stored
   anywhere else.** It is not written to provenance, not returned in a
   response model, and not recorded on an ingestion run.
2. **No exception message this module raises contains it.** Every
   message is built from a status code, a dataset name, or a fixed
   string. `httpx`'s own exception text is never interpolated for a
   request this client built with a key, because `httpx.HTTPError`'s
   `str()` includes the full request URL.
3. **`__repr__` and `__str__` are overridden** so a client instance
   cannot leak the key into a log line, a traceback frame summary, or a
   debugger session.
4. **Redirects are not followed.** Census answers a bad key with
   `302 -> /data/invalid_key.html`, so refusing to follow the redirect
   turns an authentication failure into a typed `CensusAuthError`
   detected from the redirect's PATH — and means no response body is
   ever fetched from a URL this client did not construct.

SECURITY (the allow-list discipline #29 established)
----------------------------------------------------
The base URL and the set of requestable datasets are both allow-listed
constants. No caller — and therefore no user input — can direct this
client at an arbitrary host, path, or dataset. The only caller-supplied
value is a time expression, which is validated against a strict pattern
before any request is built, never string-interpolated raw.

WHAT THIS CLIENT REFUSES TO DO
------------------------------
It never converts a unit, never scales a value, and never decides that
a row belongs to a concept. It validates the provider's own contract —
the fields it was told to expect are present, the program is the one
requested, the geography is national, the period is monthly — and
hands rows onward. A row that fails validation is REJECTED and
reported, never repaired and never silently dropped.
"""

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx

CENSUS_BASE_URL = "https://api.census.gov"

#: The ONLY dataset this client may request. Adding one is a deliberate
#: code change, reviewed against its licensing and its semantics, never
#: a runtime decision. Census approval (#45) covers the reviewed
#: program; it is not blanket permission to ingest arbitrary Census
#: datasets.
RESCONST_DATASET = "timeseries/eits/resconst"
ALLOWED_DATASETS: frozenset[str] = frozenset({RESCONST_DATASET})

#: The program this dataset must report. A row claiming another program
#: means the dataset's contents changed underneath us.
RESCONST_PROGRAM_CODE = "RESCONST"

#: National only (#45's declared scope). Census exposes `geo_level_code`
#: on every row, so this is checked rather than assumed.
NATIONAL_GEO_LEVEL_CODE = "US"

#: Monthly. EITS uses `time_slot_id` to distinguish periodicities within
#: one dataset; every monthly `resconst` row carries `0`. A row with any
#: other slot is a different periodicity and must not join a monthly
#: series.
MONTHLY_TIME_SLOT_ID = "0"

#: The fields requested, in request order. `time` is deliberately absent:
#: it is the request's own predicate and Census rejects it as an unknown
#: variable when it also appears in `get`, returning it as an automatic
#: trailing column instead.
REQUESTED_FIELDS: tuple[str, ...] = (
    "cell_value",
    "data_type_code",
    "time_slot_id",
    "error_data",
    "category_code",
    "seasonally_adj",
    "program_code",
    "geo_level_code",
)

#: Columns Census appends to every response regardless of `get`.
_APPENDED_FIELDS: tuple[str, ...] = ("time", "us")

#: Bounded response. The entire dataset from 1959-01 onward measures
#: ~1.5 MB across 26,773 rows (measured, #45), which is the single
#: largest request the baseline import makes. 8 MB is far above any
#: legitimate payload and far below anything that could exhaust memory
#: if the upstream misbehaves.
MAX_RESPONSE_BYTES = 8_388_608

#: `2026-08`, or `from 1959-01`. The two forms this client supports, and
#: the only two the ingestion service needs. Anything else is refused
#: before a request exists.
_TIME_EXPRESSION = re.compile(r"^(?:from )?[12][0-9]{3}-(?:0[1-9]|1[0-2])$")

#: Census's own period format, `YYYY-MM`.
_PERIOD = re.compile(r"^([12][0-9]{3})-(0[1-9]|1[0-2])$")

#: The paths Census redirects to when authentication fails. Matched on
#: the PATH only -- the redirect target is never logged, and the
#: original request URL never leaves this module.
_INVALID_KEY_PATH = "/data/invalid_key.html"
_MISSING_KEY_PATH = "/data/missing_key.html"


@dataclass(frozen=True)
class CensusResconstRow:
    """One validated `resconst` observation row.

    Carries Census's own vocabulary unchanged — `category_code`,
    `data_type_code`, `seasonally_adj` — because that is precisely what
    a provider boundary should hand onward: the provider's terms, for
    the binding layer to map. Nothing here is a MacroChipz concept.

    `value` is `None` when Census published the row with no usable
    numeric value. That is a REAL, distinct outcome from the row being
    absent, and it is never a zero: a missing count and a count of zero
    are different economic facts, and this dataclass refuses to blur
    them.

    `is_error_measure` is `True` for the rows Census publishes as
    reliability statistics rather than estimates (`error_data == "yes"`,
    carried under `data_type_code` values prefixed `E_`). They are real
    Census output and are parsed rather than discarded at the HTTP
    layer, but they are NOT economic observations, and a caller that
    treats one as a housing count would publish a standard error as if
    it were a number of homes.
    """

    period: date
    category_code: str
    data_type_code: str
    seasonally_adjusted: bool
    is_error_measure: bool
    value: float | None


@dataclass(frozen=True)
class CensusRejectedRow:
    """One row this client refused, and why.

    Rejections are RETURNED rather than raised: a single malformed row
    in a 26,773-row response must not discard the rest, and it must not
    vanish either. The ingestion service reports the count, so a
    provider contract change is visible in a sync result instead of
    being silently absorbed.

    `reason` is a fixed vocabulary, never provider text — so it is safe
    to log and cannot carry an upstream payload.
    """

    reason: str
    category_code: str | None
    data_type_code: str | None


class CensusError(Exception):
    """Base error for all Census client failures."""


class CensusNotConfiguredError(CensusError):
    """No Census API key is configured. Raised at construction, so a
    misconfigured deployment fails before any request is attempted
    rather than looking like an upstream outage."""


class CensusAuthError(CensusError):
    """Census rejected, or did not receive, the configured API key.

    A DISTINCT error class on purpose: this is the one Census failure an
    operator can actually fix, and it must never be reported as a
    generic upstream outage. Its message names no credential.
    """


class CensusTimeoutError(CensusError):
    """A request to the Census API did not complete within the timeout."""


class CensusUpstreamError(CensusError):
    """Census could not be reached, or returned an unexpected or
    malformed response. Distinct from a row-level rejection: this means
    the RESPONSE could not be trusted, not that one row could not."""


class CensusClient:
    """Thin synchronous client for the one Census dataset MacroChipz uses.

    Constructed with an explicit key rather than reading configuration
    itself, following `FREDClient`: a client that reads global settings
    cannot be tested without a global, and the injection point is where
    the "never logged" guarantee is verified.
    """

    def __init__(
        self,
        api_key: str | None,
        base_url: str = CENSUS_BASE_URL,
        timeout: float = 60.0,
        max_attempts: int = 2,
    ):
        if not api_key:
            raise CensusNotConfiguredError("No Census API key is configured.")
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_attempts = max_attempts

    # ------------------------------------------------------------------
    # Credential containment
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        """Never the key. A client instance appears in tracebacks, in
        `logging`'s `%r` formatting and in debugger output, and the
        default `object.__repr__` would be safe only by accident -- a
        future `@dataclass` decorator or a `vars()` dump would not be.
        Stating the redaction explicitly makes it a tested property."""
        return f"CensusClient(base_url={self._base_url!r}, timeout={self._timeout!r}, api_key=<redacted>)"

    __str__ = __repr__

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_resconst(
        self, time_expression: str, dataset: str = RESCONST_DATASET
    ) -> tuple[list[CensusResconstRow], list[CensusRejectedRow]]:
        """Fetch New Residential Construction rows for one time expression.

        `time_expression` is either a single month (`2026-08`) or an
        open-ended range (`from 1959-01`). Both are Census's own syntax,
        validated against `_TIME_EXPRESSION` before a request exists.

        Returns `(accepted, rejected)`. A period Census has no data for
        yields an empty accepted list -- an ordinary, non-exceptional
        outcome (a future month, or a month before a series began),
        exactly as `TreasuryClient.get_month` treats an empty month.

        Rows arrive in no guaranteed order and are returned sorted by
        `(period, category_code, data_type_code)` so a caller's own
        output is deterministic regardless of upstream ordering.
        """
        if dataset not in ALLOWED_DATASETS:
            raise ValueError(f"Dataset '{dataset}' is not allow-listed for the Census client")
        if not _TIME_EXPRESSION.match(time_expression):
            raise ValueError(
                "time_expression must be 'YYYY-MM' or 'from YYYY-MM'; "
                f"received {time_expression!r}"
            )

        payload = self._get(dataset, time_expression)
        return _parse(payload, dataset)

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    def _get(self, dataset: str, time_expression: str) -> Any:
        """One authenticated request, with a bounded retry.

        RETRY POLICY, and why it is this narrow: a retry is attempted
        only for a TIMEOUT or a TRANSPORT failure, which are the two
        failures that are plausibly transient and that cost nothing to
        repeat -- the request is a pure read. A 4xx is never retried
        (the request or the key is wrong, and repeating it is noise
        against a rate limit), and neither is a malformed body (it will
        parse identically the second time). One extra attempt, not an
        exponential ladder: the caller is an operator-invoked sync, and
        an unavailable provider should be reported quickly rather than
        held open.
        """
        url = f"{self._base_url}/data/{dataset}"
        params = {
            "get": ",".join(REQUESTED_FIELDS),
            "for": "us:*",
            "time": time_expression,
            # The credential. This dict is the ONLY place it appears
            # outside `self`, it is never logged, and it is not
            # reachable from any exception raised below.
            "key": self._api_key,
        }

        last_timeout: httpx.TimeoutException | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                with httpx.Client(timeout=self._timeout, follow_redirects=False) as client:
                    response = client.get(url, params=params)
            except httpx.TimeoutException as exc:
                last_timeout = exc
                if attempt < self._max_attempts:
                    continue
                # `from None`, not `from exc`: httpx's TimeoutException
                # carries the request -- and therefore the key-bearing
                # URL -- and chaining it would print that URL in any
                # traceback this error reaches.
                raise CensusTimeoutError(
                    f"Census request for '{dataset}' timed out after {self._max_attempts} attempt(s)"
                ) from None
            except httpx.HTTPError:
                if attempt < self._max_attempts:
                    continue
                # Deliberately NOT `f"...: {exc}"`. `httpx.HTTPError`'s
                # string form includes the full request URL, which for
                # this client contains the API key.
                raise CensusUpstreamError(f"Failed to reach the Census API for '{dataset}'") from None
            break
        else:  # pragma: no cover - the loop always breaks or raises
            raise CensusTimeoutError("Census request timed out") from last_timeout

        self._raise_for_auth_redirect(response)

        if response.status_code >= 400:
            raise CensusUpstreamError(
                f"Census returned unexpected status {response.status_code} for '{dataset}'"
            )
        if response.status_code >= 300:
            # A redirect that is not one of Census's two key pages. Not
            # followed, because this client only ever reads URLs it
            # built itself.
            raise CensusUpstreamError(
                f"Census unexpectedly redirected the request for '{dataset}' "
                f"(status {response.status_code})"
            )

        content = response.content
        if len(content) > MAX_RESPONSE_BYTES:
            raise CensusUpstreamError(
                f"Census response for '{dataset}' exceeded the {MAX_RESPONSE_BYTES}-byte bound"
            )

        try:
            return response.json()
        except ValueError:
            raise CensusUpstreamError(f"Census returned a non-JSON response for '{dataset}'") from None

    @staticmethod
    def _raise_for_auth_redirect(response: httpx.Response) -> None:
        """Turn Census's key redirects into a typed authentication error.

        Census does not use 401. A bad key is `302` to
        `/data/invalid_key.html` and an absent one `302` to
        `/data/missing_key.html`, both of which render as an HTTP 200
        HTML page if the redirect is followed -- which is exactly how a
        careless client ends up trying to JSON-parse an error page and
        reporting "malformed response" for what is really a
        configuration problem.

        Only the redirect's PATH is inspected, and nothing about the
        location is included in the raised message.
        """
        if response.status_code not in (301, 302, 303, 307, 308):
            return
        location = response.headers.get("location", "")
        path = httpx.URL(location).path if location else ""
        if path == _INVALID_KEY_PATH:
            raise CensusAuthError(
                "Census rejected the configured API key. A newly issued key must be activated from "
                "the confirmation email before it will be accepted."
            )
        if path == _MISSING_KEY_PATH:
            raise CensusAuthError("Census did not receive an API key with the request.")


# ----------------------------------------------------------------------
# Parsing
#
# A module-level function rather than a method: it touches no
# credential, no socket and no instance state, so it is directly
# testable against a captured payload with no client at all.
# ----------------------------------------------------------------------


def _parse(payload: Any, dataset: str) -> tuple[list[CensusResconstRow], list[CensusRejectedRow]]:
    """Validate the response envelope, then every row.

    The ENVELOPE raises: Census's tabular JSON is a list whose first
    element is the header, and a payload that is not that shape, or
    whose header is missing a requested column, means the provider's
    contract changed and nothing in the body can be trusted.

    A ROW is rejected: one bad row among thousands is a data problem,
    not a contract problem, and discarding the whole response over it
    would make the pipeline brittle in the wrong direction.
    """
    if not isinstance(payload, list) or not payload:
        raise CensusUpstreamError(f"Census returned an unexpected payload shape for '{dataset}'")

    header = payload[0]
    if not isinstance(header, list) or not all(isinstance(name, str) for name in header):
        raise CensusUpstreamError(f"Census returned an unreadable header row for '{dataset}'")

    index = {name: position for position, name in enumerate(header)}
    missing = [name for name in REQUESTED_FIELDS + _APPENDED_FIELDS if name not in index]
    if missing:
        raise CensusUpstreamError(
            f"Census response for '{dataset}' is missing expected column(s): {', '.join(sorted(missing))}"
        )

    accepted: list[CensusResconstRow] = []
    rejected: list[CensusRejectedRow] = []

    for row in payload[1:]:
        if not isinstance(row, list) or len(row) != len(header):
            rejected.append(CensusRejectedRow(reason="MALFORMED_ROW", category_code=None, data_type_code=None))
            continue

        def field(name: str) -> Any:
            return row[index[name]]

        category_code = _text(field("category_code"))
        data_type_code = _text(field("data_type_code"))

        def reject(reason: str) -> None:
            rejected.append(
                CensusRejectedRow(reason=reason, category_code=category_code, data_type_code=data_type_code)
            )

        if not category_code or not data_type_code:
            reject("MISSING_IDENTITY")
            continue
        if _text(field("program_code")) != RESCONST_PROGRAM_CODE:
            reject("UNEXPECTED_PROGRAM")
            continue
        if _text(field("geo_level_code")) != NATIONAL_GEO_LEVEL_CODE:
            # Not national. #45's scope is national, and a sub-national
            # row joining a national series would be a silent
            # aggregation error.
            reject("NON_NATIONAL_GEOGRAPHY")
            continue
        if _text(field("time_slot_id")) != MONTHLY_TIME_SLOT_ID:
            reject("NON_MONTHLY_TIME_SLOT")
            continue

        seasonally_adjusted = _yes_no(_text(field("seasonally_adj")))
        is_error_measure = _yes_no(_text(field("error_data")))
        if seasonally_adjusted is None or is_error_measure is None:
            # `seasonally_adj` and `error_data` are yes/no flags whose
            # meaning is load-bearing. An unrecognised value cannot be
            # defaulted in either direction without risking a
            # seasonally adjusted value entering an unadjusted series,
            # or a standard error entering a count.
            reject("UNRECOGNISED_FLAG")
            continue

        period = _period(_text(field("time")))
        if period is None:
            reject("UNPARSEABLE_PERIOD")
            continue

        accepted.append(
            CensusResconstRow(
                period=period,
                category_code=category_code,
                data_type_code=data_type_code,
                seasonally_adjusted=seasonally_adjusted,
                is_error_measure=is_error_measure,
                # A row Census published without a usable number is
                # accepted with `value=None`. "Census published nothing
                # here" is a fact worth carrying; zero would be a lie.
                value=_number(field("cell_value")),
            )
        )

    accepted.sort(key=lambda item: (item.period, item.category_code, item.data_type_code))
    return accepted, rejected


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _yes_no(value: str) -> bool | None:
    """Census's own flag vocabulary. `None` for anything else -- never a
    default, because both of this function's callers guard a semantic
    distinction that must not be guessed."""
    lowered = value.lower()
    if lowered == "yes":
        return True
    if lowered == "no":
        return False
    return None


def _period(value: str) -> date | None:
    """`2026-08` -> `2026-08-01`.

    Monthly observations are stored on the first of the month, matching
    every other monthly series MacroChipz persists. The day carries no
    information and is never presented as one.
    """
    match = _PERIOD.match(value)
    if match is None:
        return None
    return date(int(match.group(1)), int(match.group(2)), 1)


def _number(value: Any) -> float | None:
    """The published value, or `None`.

    `None` for null, empty, and unparseable alike: every one of those
    means Census did not publish a usable number, and the distinction
    between them is not economically meaningful. What matters is that
    none of them becomes `0.0`.
    """
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None
