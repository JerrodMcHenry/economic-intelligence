"""U.S. Bureau of Economic Analysis NIPA client (Increment #56A).

Keyless. Reads BEA's published monthly NIPA flat file,
`https://apps.bea.gov/national/Release/TXT/NipaDataM.txt`, which carries
every monthly NIPA series in one CSV (`%SeriesCode,Period,Value`, rows
such as `DPCERG,2026M07,"131.659"`). Verified against the real file
downloaded on 2026-09-24: 36.7 MB, ~1.48 million lines, HTTP 200 with no
key, and `Last-Modified: Wed, 26 Aug 2026 12:30:02 GMT` -- exactly the
July 2026 Personal Income and Outlays release.

Why the file and not the keyed BEA API (recorded in
docs/architecture/first-party-ingestion-v56a.md §8): the file needs no
credential, is the path verified against real data, and contains every
value the initial import needs. The API needs a registered UserID and
has no recorded response in this repository to test a client against.
It suits the small per-release fetches of #56B; this client does not
pretend to have been verified against it.

The file is STREAMED and filtered: only the requested series codes are
kept, so memory holds a few hundred rows, not 1.5 million. The byte cap
still bounds the download as a whole.
"""

import csv
import math
import re
from datetime import date, datetime
from email.utils import parsedate_to_datetime

from app.clients.bounded_http import ProviderResponseError, stream_lines
from app.clients.provider_observation import FirstPartyObservation

PROVIDER = "BEA"

NIPA_MONTHLY_URL = "https://apps.bea.gov/national/Release/TXT/NipaDataM.txt"
EXPECTED_HEADER = "%SeriesCode,Period,Value"

#: 36.7 MB as published on 2026-09-24. 64 MB leaves room for normal
#: growth and still bounds a runaway or substituted response.
MAX_RESPONSE_BYTES = 64 * 1024 * 1024

_SERIES_CODE = re.compile(r"^[A-Z0-9]{3,16}$")
_MONTHLY_PERIOD = re.compile(r"^(\d{4})M(0[1-9]|1[0-2])$")


class BEAClient:
    def __init__(self, timeout: float = 120.0, max_attempts: int = 2, url: str = NIPA_MONTHLY_URL):
        self._timeout = timeout
        self._max_attempts = max_attempts
        self._url = url

    def __repr__(self) -> str:
        return f"BEAClient(url={self._url!r}, timeout={self._timeout!r})"

    def get_nipa_monthly(
        self, series_codes: list[str], start: date
    ) -> tuple[dict[str, list[FirstPartyObservation]], datetime | None]:
        """Monthly observations from `start` onward for each requested
        code, ascending, plus the file's `Last-Modified` instant (BEA's
        publication time for this vintage, or `None` if absent).

        Raises `ProviderResponseError` if the header is not the
        documented one, a requested row does not parse, or a requested
        code is absent from the whole file.
        """
        if not series_codes:
            raise ValueError("at least one series code")
        for code in series_codes:
            if not _SERIES_CODE.match(code):
                raise ValueError(f"not a NIPA series code: {code!r}")

        wanted = set(series_codes)
        found: dict[str, list[FirstPartyObservation]] = {code: [] for code in series_codes}
        seen: set[str] = set()

        with stream_lines(
            PROVIDER, self._url, max_bytes=MAX_RESPONSE_BYTES, timeout=self._timeout, max_attempts=self._max_attempts
        ) as (headers, lines):
            published_at = _last_modified(headers.get("last-modified"))
            first = next(lines, None)
            if first is None or first.lstrip("﻿").strip() != EXPECTED_HEADER:
                raise ProviderResponseError(PROVIDER, "NIPA file header is not the documented format")

            for line in lines:
                # Cheap prefix test before any CSV parsing: ~1.5M lines,
                # of which a few hundred are wanted.
                code = line.split(",", 1)[0]
                if code not in wanted:
                    continue
                seen.add(code)
                observation = _parse_row(line, start)
                if observation is not None:
                    found[code].append(observation)

        missing = sorted(wanted - seen)
        if missing:
            raise ProviderResponseError(PROVIDER, f"NIPA file does not contain requested series {missing}")
        return {code: sorted(rows, key=lambda row: row.period) for code, rows in found.items()}, published_at


def _parse_row(line: str, start: date) -> FirstPartyObservation | None:
    try:
        fields = next(csv.reader([line]))
    except csv.Error:
        raise ProviderResponseError(PROVIDER, "malformed NIPA row") from None
    if len(fields) != 3:
        raise ProviderResponseError(PROVIDER, "malformed NIPA row")

    match = _MONTHLY_PERIOD.match(fields[1])
    if match is None:
        raise ProviderResponseError(PROVIDER, "malformed NIPA period")
    period = date(int(match.group(1)), int(match.group(2)), 1)
    if period < start:
        return None

    try:
        value = float(fields[2].replace(",", ""))
    except ValueError:
        raise ProviderResponseError(PROVIDER, "non-numeric NIPA value") from None
    if not math.isfinite(value):
        raise ProviderResponseError(PROVIDER, "non-finite NIPA value")
    return FirstPartyObservation(period=period, value=value)


def _last_modified(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
