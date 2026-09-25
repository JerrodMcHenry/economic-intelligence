"""Increment #56A: the BLS and BEA clients and their bounded transport.

No network. The real clients run end to end against `httpx.MockTransport`
serving:

- `fixtures/bls_v1_2017_2026.json` -- a REAL BLS v1 response, recorded
  2026-09-24 for the four series (public-domain BLS data);
- `fixtures/bea_nipa_monthly_excerpt.txt` -- lines copied verbatim from
  BEA's real `NipaDataM.txt` of the same day: its header, rows with
  thousands separators, and both PCE series from 2016.

The published values asserted below are the ones #54B compared with
every stored FRED value (358/358 exact).
"""

import json
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from app.clients import bounded_http
from app.clients.bea import BEAClient, NIPA_MONTHLY_URL
from app.clients.bls import V1_URL, V2_URL, BLSClient
from app.clients.bounded_http import (
    ProviderRateLimitedError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

FIXTURES = Path(__file__).parent / "fixtures"
BLS_RESPONSE = (FIXTURES / "bls_v1_2017_2026.json").read_bytes()
BEA_FILE = (FIXTURES / "bea_nipa_monthly_excerpt.txt").read_bytes()
BLS_SERIES = ["CUSR0000SA0", "CUSR0000SA0L1E", "CES0000000001", "LNS14000000"]
#: A synthetic sentinel -- never a real key.
FAKE_KEY = "synthetic-bls-key-0000000000000000"


def serve(handler):
    """Replace the transport's client factory so every request reaches
    `handler` -- the same redirect/timeout settings, a mock transport."""

    def factory(timeout):
        return httpx.Client(timeout=timeout, follow_redirects=False, transport=httpx.MockTransport(handler))

    return patch.object(bounded_http, "_new_client", factory)


class Recorder:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        response = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(response, Exception):
            raise response
        return response


# ---------------------------------------------------------------------
# BLS
# ---------------------------------------------------------------------


class TestBLSParsesTheRealResponse:
    @pytest.fixture
    def result(self):
        with serve(Recorder(httpx.Response(200, content=BLS_RESPONSE))):
            return BLSClient().get_monthly(BLS_SERIES, 2017, 2026)

    def test_every_series_and_every_month(self, result):
        assert sorted(result) == sorted(BLS_SERIES)
        for series_id in BLS_SERIES:
            periods = [item.period for item in result[series_id]]
            assert periods == sorted(periods)
            assert periods[0] == date(2017, 1, 1)
            assert periods[-1] == date(2026, 8, 1)
            assert len(periods) == 116

    def test_published_values_exactly(self, result):
        latest = {series_id: result[series_id][-1] for series_id in BLS_SERIES}
        assert latest["CUSR0000SA0"].value == 334.131
        assert latest["CUSR0000SA0L1E"].value == 337.765
        # Thousands of persons, UNCONVERTED -- the binding carries the x1000.
        assert latest["CES0000000001"].value == 159075.0
        assert latest["LNS14000000"].value == 4.1

    def test_preliminary_values_keep_their_footnote(self, result):
        assert result["CES0000000001"][-1].footnotes == ("P",)

    @pytest.mark.parametrize("series_id", ["CUSR0000SA0", "CUSR0000SA0L1E", "LNS14000000"])
    def test_the_uncollected_october_2025_is_unavailable_never_zero(self, result, series_id):
        october = next(item for item in result[series_id] if item.period == date(2025, 10, 1))
        assert october.value is None
        assert october.footnotes

    def test_payrolls_were_published_for_october_2025(self, result):
        october = next(item for item in result["CES0000000001"] if item.period == date(2025, 10, 1))
        assert october.value == 158408.0


class TestBLSRequestShape:
    def test_keyless_uses_v1_and_sends_no_key(self):
        recorder = Recorder(httpx.Response(200, content=BLS_RESPONSE))
        with serve(recorder):
            BLSClient().get_monthly(BLS_SERIES, 2017, 2026)

        (request,) = recorder.requests
        assert str(request.url) == V1_URL
        assert request.method == "POST"
        body = json.loads(request.content)
        assert body == {"seriesid": BLS_SERIES, "startyear": "2017", "endyear": "2026"}

    def test_a_key_moves_to_v2_and_travels_only_in_the_body(self):
        recorder = Recorder(httpx.Response(200, content=BLS_RESPONSE))
        with serve(recorder):
            BLSClient(api_key=FAKE_KEY).get_monthly(BLS_SERIES, 2017, 2026)

        (request,) = recorder.requests
        assert str(request.url) == V2_URL
        assert FAKE_KEY not in str(request.url)
        assert json.loads(request.content)["registrationkey"] == FAKE_KEY

    def test_the_key_is_redacted_from_repr(self):
        client = BLSClient(api_key=FAKE_KEY)
        assert FAKE_KEY not in repr(client) and FAKE_KEY not in str(client)

    def test_keyless_refuses_more_than_ten_years_before_any_request(self):
        recorder = Recorder(httpx.Response(200, content=BLS_RESPONSE))
        with serve(recorder), pytest.raises(ValueError):
            BLSClient().get_monthly(BLS_SERIES, 2016, 2026)
        assert recorder.requests == []

    def test_a_key_allows_twenty_years(self):
        with serve(Recorder(httpx.Response(200, content=BLS_RESPONSE))):
            BLSClient(api_key=FAKE_KEY).get_monthly(BLS_SERIES, 2007, 2026)

    @pytest.mark.parametrize("bad", ["", "cusr0000sa0", "CUSR0000SA0; DROP", "A" * 30])
    def test_series_ids_are_validated(self, bad):
        with pytest.raises(ValueError):
            BLSClient().get_monthly([bad], 2020, 2021)


def _bls_payload(data, status="REQUEST_SUCCEEDED", series_id="CUSR0000SA0"):
    return {"status": status, "Results": {"series": [{"seriesID": series_id, "data": data}]}}


class TestBLSRefusesWhatItCannotTrust:
    def _get(self, payload, series=("CUSR0000SA0",)):
        with serve(Recorder(httpx.Response(200, json=payload))):
            return BLSClient().get_monthly(list(series), 2025, 2026)

    def test_the_daily_limit_is_a_rate_limit_error(self):
        with pytest.raises(ProviderRateLimitedError):
            self._get({"status": "REQUEST_NOT_PROCESSED", "message": ["daily threshold"]})

    def test_an_unknown_status_is_refused(self):
        with pytest.raises(ProviderResponseError):
            self._get({"status": "SOMETHING_NEW"})

    def test_a_missing_requested_series_is_refused(self):
        with pytest.raises(ProviderResponseError, match="omitted"):
            self._get(_bls_payload([]), series=("CUSR0000SA0", "LNS14000000"))

    @pytest.mark.parametrize("value", ["abc", "nan", "inf", None])
    def test_a_non_numeric_or_non_finite_value_is_refused(self, value):
        with pytest.raises(ProviderResponseError):
            self._get(_bls_payload([{"year": "2026", "period": "M01", "value": value}]))

    def test_annual_averages_are_not_monthly_observations(self):
        result = self._get(
            _bls_payload(
                [
                    {"year": "2025", "period": "M13", "value": "300.0"},
                    {"year": "2025", "period": "M12", "value": "301.5"},
                ]
            )
        )
        assert [item.period for item in result["CUSR0000SA0"]] == [date(2025, 12, 1)]

    def test_non_json_is_refused(self):
        with serve(Recorder(httpx.Response(200, content=b"<html>maintenance</html>"))):
            with pytest.raises(ProviderResponseError):
                BLSClient().get_monthly(["CUSR0000SA0"], 2025, 2026)


# ---------------------------------------------------------------------
# The bounded transport, exercised through the BLS client
# ---------------------------------------------------------------------


class TestTransportBounds:
    def test_a_5xx_is_retried_once_then_succeeds(self):
        recorder = Recorder(httpx.Response(503), httpx.Response(200, content=BLS_RESPONSE))
        with serve(recorder):
            BLSClient().get_monthly(BLS_SERIES, 2017, 2026)
        assert len(recorder.requests) == 2

    def test_persistent_5xx_is_unavailable_after_the_allowed_attempts(self):
        recorder = Recorder(httpx.Response(502))
        with serve(recorder), pytest.raises(ProviderUnavailableError):
            BLSClient().get_monthly(BLS_SERIES, 2017, 2026)
        assert len(recorder.requests) == 2

    def test_a_timeout_is_retried_once_then_reported(self):
        recorder = Recorder(httpx.ReadTimeout("slow"))
        with serve(recorder), pytest.raises(ProviderTimeoutError):
            BLSClient().get_monthly(BLS_SERIES, 2017, 2026)
        assert len(recorder.requests) == 2

    def test_a_connection_failure_is_retried_once_then_reported(self):
        recorder = Recorder(httpx.ConnectError("refused"))
        with serve(recorder), pytest.raises(ProviderUnavailableError):
            BLSClient().get_monthly(BLS_SERIES, 2017, 2026)
        assert len(recorder.requests) == 2

    def test_429_is_never_retried(self):
        recorder = Recorder(httpx.Response(429))
        with serve(recorder), pytest.raises(ProviderRateLimitedError):
            BLSClient().get_monthly(BLS_SERIES, 2017, 2026)
        assert len(recorder.requests) == 1

    @pytest.mark.parametrize("status", [400, 403, 404])
    def test_4xx_is_never_retried(self, status):
        recorder = Recorder(httpx.Response(status))
        with serve(recorder), pytest.raises(ProviderResponseError):
            BLSClient().get_monthly(BLS_SERIES, 2017, 2026)
        assert len(recorder.requests) == 1

    def test_a_redirect_is_not_followed(self):
        recorder = Recorder(httpx.Response(302, headers={"Location": "https://elsewhere.example/"}))
        with serve(recorder), pytest.raises(ProviderResponseError):
            BLSClient().get_monthly(BLS_SERIES, 2017, 2026)
        assert len(recorder.requests) == 1

    def test_a_declared_oversize_body_is_refused(self):
        recorder = Recorder(httpx.Response(200, headers={"Content-Length": str(50 * 1024 * 1024)}, content=b"{}"))
        with serve(recorder), pytest.raises(ProviderResponseError, match="byte bound"):
            BLSClient().get_monthly(BLS_SERIES, 2017, 2026)

    def test_an_undeclared_oversize_body_is_cut_off_while_streaming(self, monkeypatch):
        monkeypatch.setattr("app.clients.bls.MAX_RESPONSE_BYTES", 1024)

        def chunks():
            for _ in range(100):
                yield b"x" * 100

        with serve(Recorder(httpx.Response(200, content=chunks()))), pytest.raises(ProviderResponseError, match="byte bound"):
            BLSClient().get_monthly(BLS_SERIES, 2017, 2026)

    def test_errors_never_carry_the_key_or_a_url(self):
        recorder = Recorder(httpx.ConnectError(f"failed to reach {V2_URL}?k={FAKE_KEY}"))
        with serve(recorder), pytest.raises(ProviderUnavailableError) as caught:
            BLSClient(api_key=FAKE_KEY).get_monthly(BLS_SERIES, 2017, 2026)
        assert FAKE_KEY not in f"{caught.value!s} {caught.value!r}"
        assert "https://" not in str(caught.value)
        # Raised `from None`: no chained httpx exception (whose text is the
        # request URL) can appear in a traceback.
        assert caught.value.__cause__ is None
        assert caught.value.__suppress_context__ is True


# ---------------------------------------------------------------------
# BEA
# ---------------------------------------------------------------------


def _bea_response(content=BEA_FILE, last_modified="Wed, 26 Aug 2026 12:30:02 GMT"):
    headers = {"Last-Modified": last_modified} if last_modified else {}
    return httpx.Response(200, headers=headers, content=content)


class TestBEAParsesTheRealFileFormat:
    @pytest.fixture
    def result(self):
        recorder = Recorder(_bea_response())
        with serve(recorder):
            data, published = BEAClient().get_nipa_monthly(["DPCERG", "DPCCRG"], date(2017, 1, 1))
        assert str(recorder.requests[0].url) == NIPA_MONTHLY_URL
        return data, published

    def test_window_and_ordering(self, result):
        data, _ = result
        for code in ("DPCERG", "DPCCRG"):
            periods = [item.period for item in data[code]]
            assert periods == sorted(periods)
            assert periods[0] == date(2017, 1, 1)  # 2016 rows in the file are excluded
            assert periods[-1] == date(2026, 7, 1)
            assert len(periods) == 115

    def test_published_values_exactly(self, result):
        data, _ = result
        assert data["DPCERG"][-1].value == 131.659
        assert data["DPCCRG"][-1].value == 130.658

    def test_the_october_2025_value_bea_imputed_is_present(self, result):
        data, _ = result
        assert next(item for item in data["DPCERG"] if item.period == date(2025, 10, 1)).value is not None

    def test_the_vintage_comes_from_last_modified(self, result):
        _, published = result
        assert published == datetime(2026, 8, 26, 12, 30, 2, tzinfo=timezone.utc)

    def test_thousands_separators_are_parsed(self):
        with serve(Recorder(_bea_response())):
            data, _ = BEAClient().get_nipa_monthly(["A015RC"], date(1967, 1, 1))
        assert data["A015RC"][0].value == 22068.0

    def test_a_missing_last_modified_is_none_not_a_guess(self):
        with serve(Recorder(_bea_response(last_modified=None))):
            _, published = BEAClient().get_nipa_monthly(["DPCERG"], date(2026, 1, 1))
        assert published is None


class TestBEARefusesWhatItCannotTrust:
    def test_a_changed_header_is_refused(self):
        with serve(Recorder(_bea_response(content=b"SeriesCode,Period,Value\nDPCERG,2026M07,\"1\"\n"))):
            with pytest.raises(ProviderResponseError, match="header"):
                BEAClient().get_nipa_monthly(["DPCERG"], date(2026, 1, 1))

    def test_a_series_absent_from_the_file_is_refused(self):
        with serve(Recorder(_bea_response())), pytest.raises(ProviderResponseError, match="does not contain"):
            BEAClient().get_nipa_monthly(["DPCERG", "NOTREAL"], date(2026, 1, 1))

    @pytest.mark.parametrize(
        "row", [b'DPCERG,2026-07,"1.0"', b'DPCERG,2026M07,"n/a"', b"DPCERG,2026M07", b'DPCERG,2026M07,"inf"']
    )
    def test_a_malformed_requested_row_is_refused(self, row):
        content = b"%SeriesCode,Period,Value\n" + row + b"\n"
        with serve(Recorder(_bea_response(content=content))), pytest.raises(ProviderResponseError):
            BEAClient().get_nipa_monthly(["DPCERG"], date(2026, 1, 1))

    def test_malformed_rows_of_other_series_are_ignored(self):
        content = BEA_FILE + b"ZZZ,garbage\n"
        with serve(Recorder(_bea_response(content=content))):
            data, _ = BEAClient().get_nipa_monthly(["DPCERG"], date(2026, 1, 1))
        assert data["DPCERG"]

    def test_the_download_is_bounded_while_streaming(self, monkeypatch):
        monkeypatch.setattr("app.clients.bea.MAX_RESPONSE_BYTES", 2048)
        with serve(Recorder(_bea_response(content=BEA_FILE))), pytest.raises(ProviderResponseError, match="byte bound"):
            BEAClient().get_nipa_monthly(["DPCERG"], date(2017, 1, 1))

    @pytest.mark.parametrize("bad", ["", "dpcerg", "DPC-ERG"])
    def test_series_codes_are_validated(self, bad):
        with pytest.raises(ValueError):
            BEAClient().get_nipa_monthly([bad], date(2026, 1, 1))
