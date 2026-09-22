"""The Census provider boundary (Increment #45).

Every test here runs WITHOUT A NETWORK. Responses are captured shapes
fed through `httpx.MockTransport`, so the parser's behaviour on
malformed, missing and error-flagged rows is exercised deterministically
rather than by hoping the live dataset happens to contain them.

`_SENTINEL_KEY` is a synthetic, obviously-fake value. It is never a real
credential, and several tests below assert that it does not appear where
a real one must not -- which is the point of using a recognisable
sentinel rather than a plausible-looking hex string.
"""

import contextlib
import json
import traceback
from datetime import date
from unittest.mock import patch

import httpx
import pytest

from app.clients.census import (
    ALLOWED_DATASETS,
    MAX_RESPONSE_BYTES,
    RESCONST_DATASET,
    CensusAuthError,
    CensusClient,
    CensusNotConfiguredError,
    CensusRejectedRow,
    CensusTimeoutError,
    CensusUpstreamError,
    _parse,
)

_SENTINEL_KEY = "sentinel-not-a-real-census-key-00000000"

_HEADER = [
    "cell_value",
    "data_type_code",
    "time_slot_id",
    "error_data",
    "category_code",
    "seasonally_adj",
    "program_code",
    "geo_level_code",
    "time",
    "us",
]


def _row(
    cell_value="1394",
    data_type_code="TOTAL",
    time_slot_id="0",
    error_data="no",
    category_code="APERMITS",
    seasonally_adj="yes",
    program_code="RESCONST",
    geo_level_code="US",
    time="2026-08",
):
    return [
        cell_value,
        data_type_code,
        time_slot_id,
        error_data,
        category_code,
        seasonally_adj,
        program_code,
        geo_level_code,
        time,
        "1",
    ]


def _payload(*rows):
    return [_HEADER, *rows]


def _json_response(payload, status=200):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=payload)

    return handler


class TestCredentialContainment:
    """The four rules in the module docstring of `app.clients.census`.

    These are the tests that matter most in this file. A parsing bug
    produces a wrong number; a credential leak produces a compromised
    account, and the leak paths are all boring ones -- a repr in a log
    line, an exception message, a chained traceback.
    """

    def test_repr_never_contains_the_key(self) -> None:
        client = CensusClient(api_key=_SENTINEL_KEY)
        assert _SENTINEL_KEY not in repr(client)
        assert "<redacted>" in repr(client)

    def test_str_never_contains_the_key(self) -> None:
        client = CensusClient(api_key=_SENTINEL_KEY)
        assert _SENTINEL_KEY not in str(client)

    def test_format_never_contains_the_key(self) -> None:
        """`logging`'s `%s`/`%r` and f-strings all route here."""
        client = CensusClient(api_key=_SENTINEL_KEY)
        assert _SENTINEL_KEY not in f"{client}"
        assert _SENTINEL_KEY not in f"{client!r}"

    def test_no_instance_attribute_dump_exposes_it_unredacted_in_repr(self) -> None:
        """`vars()` legitimately shows it -- it has to be stored
        somewhere. What must never happen is that the DEFAULT string
        conversions expose it, because those are what end up in logs."""
        client = CensusClient(api_key=_SENTINEL_KEY)
        assert _SENTINEL_KEY in vars(client).values()
        assert _SENTINEL_KEY not in repr(client)

    def test_timeout_error_message_carries_no_key(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectTimeout("timed out", request=request)

        client = CensusClient(api_key=_SENTINEL_KEY, max_attempts=1)
        with _transport(client, handler):
            with pytest.raises(CensusTimeoutError) as exc_info:
                client.get_resconst("2026-08")

        assert _SENTINEL_KEY not in str(exc_info.value)
        assert _SENTINEL_KEY not in _full_traceback_text(exc_info)

    def test_transport_error_message_carries_no_key(self) -> None:
        """The specific trap: `str(httpx.HTTPError)` includes the request
        URL, and this client's request URL contains the key. Interpolating
        the upstream exception -- the obvious thing to do -- would leak it
        into every log line and traceback."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        client = CensusClient(api_key=_SENTINEL_KEY, max_attempts=1)
        with _transport(client, handler):
            with pytest.raises(CensusUpstreamError) as exc_info:
                client.get_resconst("2026-08")

        assert _SENTINEL_KEY not in str(exc_info.value)
        assert _SENTINEL_KEY not in _full_traceback_text(exc_info)

    def test_unexpected_status_message_carries_no_key(self) -> None:
        client = CensusClient(api_key=_SENTINEL_KEY)
        with _transport(client, lambda request: httpx.Response(500, text="boom")):
            with pytest.raises(CensusUpstreamError) as exc_info:
                client.get_resconst("2026-08")

        assert _SENTINEL_KEY not in str(exc_info.value)
        assert _SENTINEL_KEY not in _full_traceback_text(exc_info)

    def test_auth_error_message_carries_no_key_and_no_redirect_target(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(302, headers={"location": "https://api.census.gov/data/invalid_key.html"})

        client = CensusClient(api_key=_SENTINEL_KEY)
        with _transport(client, handler):
            with pytest.raises(CensusAuthError) as exc_info:
                client.get_resconst("2026-08")

        message = str(exc_info.value)
        assert _SENTINEL_KEY not in message
        assert "invalid_key.html" not in message
        assert _SENTINEL_KEY not in _full_traceback_text(exc_info)

    def test_the_key_does_reach_the_request(self) -> None:
        """The complement of every test above: containment must not have
        been achieved by failing to authenticate at all."""
        seen: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["key"] = request.url.params.get("key", "")
            return httpx.Response(200, json=_payload(_row()))

        client = CensusClient(api_key=_SENTINEL_KEY)
        with _transport(client, handler):
            client.get_resconst("2026-08")

        assert seen["key"] == _SENTINEL_KEY


class TestConfiguration:
    def test_no_key_raises_at_construction(self) -> None:
        """Before any request, so a misconfigured deployment fails as a
        configuration problem rather than looking like a provider
        outage."""
        with pytest.raises(CensusNotConfiguredError):
            CensusClient(api_key=None)

    def test_empty_key_raises_at_construction(self) -> None:
        with pytest.raises(CensusNotConfiguredError):
            CensusClient(api_key="")

    def test_max_attempts_below_one_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            CensusClient(api_key=_SENTINEL_KEY, max_attempts=0)


class TestRequestAllowList:
    def test_only_resconst_is_allow_listed(self) -> None:
        assert ALLOWED_DATASETS == {RESCONST_DATASET}

    def test_a_non_allow_listed_dataset_is_refused_before_any_request(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
            raise AssertionError("no request should have been made")

        client = CensusClient(api_key=_SENTINEL_KEY)
        with _transport(client, handler):
            with pytest.raises(ValueError, match="not allow-listed"):
                client.get_resconst("2026-08", dataset="timeseries/eits/marts")

    @pytest.mark.parametrize(
        "expression",
        ["2026-8", "2026", "2026-13", "from 2026", "'; DROP TABLE", "from  2026-01", "2026-01 ", ""],
    )
    def test_a_malformed_time_expression_is_refused_before_any_request(self, expression: str) -> None:
        def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
            raise AssertionError("no request should have been made")

        client = CensusClient(api_key=_SENTINEL_KEY)
        with _transport(client, handler):
            with pytest.raises(ValueError, match="time_expression"):
                client.get_resconst(expression)

    @pytest.mark.parametrize("expression", ["2026-08", "1959-01", "from 1959-01", "from 2026-12"])
    def test_supported_time_expressions_are_accepted(self, expression: str) -> None:
        client = CensusClient(api_key=_SENTINEL_KEY)
        with _transport(client, _json_response(_payload(_row()))):
            accepted, rejected = client.get_resconst(expression)
        assert rejected == []
        assert len(accepted) == 1


class TestAuthenticationDetection:
    """Census answers a credential problem with a 302 to an HTML page, not
    a 401. Following that redirect turns a configuration error into a
    "malformed response", which is the wrong thing to tell an operator."""

    def test_invalid_key_redirect_becomes_an_auth_error(self) -> None:
        client = CensusClient(api_key=_SENTINEL_KEY)
        with _transport(
            client,
            lambda request: httpx.Response(302, headers={"location": "/data/invalid_key.html"}),
        ):
            with pytest.raises(CensusAuthError, match="rejected"):
                client.get_resconst("2026-08")

    def test_missing_key_redirect_becomes_an_auth_error(self) -> None:
        client = CensusClient(api_key=_SENTINEL_KEY)
        with _transport(
            client,
            lambda request: httpx.Response(302, headers={"location": "/data/missing_key.html"}),
        ):
            with pytest.raises(CensusAuthError, match="did not receive"):
                client.get_resconst("2026-08")

    def test_the_auth_error_mentions_activation(self) -> None:
        """The failure an operator actually hits: Census issues a
        correctly-formatted key that is rejected until the confirmation
        email is used. Saying so in the error is the difference between a
        one-minute fix and an afternoon."""
        client = CensusClient(api_key=_SENTINEL_KEY)
        with _transport(
            client,
            lambda request: httpx.Response(302, headers={"location": "/data/invalid_key.html"}),
        ):
            with pytest.raises(CensusAuthError, match="activated"):
                client.get_resconst("2026-08")

    def test_an_unrelated_redirect_is_not_reported_as_authentication(self) -> None:
        client = CensusClient(api_key=_SENTINEL_KEY)
        with _transport(
            client,
            lambda request: httpx.Response(302, headers={"location": "/data/somewhere_else.html"}),
        ):
            with pytest.raises(CensusUpstreamError, match="redirect"):
                client.get_resconst("2026-08")

    def test_redirects_are_never_followed(self) -> None:
        """Nothing is fetched from a URL this client did not build."""
        requested: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requested.append(request.url.path)
            if len(requested) == 1:
                return httpx.Response(302, headers={"location": "/data/invalid_key.html"})
            return httpx.Response(200, json=_payload(_row()))  # pragma: no cover

        client = CensusClient(api_key=_SENTINEL_KEY)
        with _transport(client, handler):
            with pytest.raises(CensusAuthError):
                client.get_resconst("2026-08")

        assert requested == [f"/data/{RESCONST_DATASET}"]


class TestRetry:
    def test_a_timeout_is_retried_up_to_max_attempts(self) -> None:
        attempts: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            attempts.append(1)
            raise httpx.ReadTimeout("slow", request=request)

        client = CensusClient(api_key=_SENTINEL_KEY, max_attempts=2)
        with _transport(client, handler):
            with pytest.raises(CensusTimeoutError):
                client.get_resconst("2026-08")

        assert len(attempts) == 2

    def test_a_retry_that_succeeds_returns_normally(self) -> None:
        attempts: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            attempts.append(1)
            if len(attempts) == 1:
                raise httpx.ReadTimeout("slow", request=request)
            return httpx.Response(200, json=_payload(_row()))

        client = CensusClient(api_key=_SENTINEL_KEY, max_attempts=2)
        with _transport(client, handler):
            accepted, _ = client.get_resconst("2026-08")

        assert len(attempts) == 2
        assert len(accepted) == 1

    def test_an_http_error_status_is_never_retried(self) -> None:
        """Repeating a request the provider already answered is noise
        against a rate limit, and a 500 will not become a 200."""
        attempts: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            attempts.append(1)
            return httpx.Response(503, text="unavailable")

        client = CensusClient(api_key=_SENTINEL_KEY, max_attempts=3)
        with _transport(client, handler):
            with pytest.raises(CensusUpstreamError):
                client.get_resconst("2026-08")

        assert len(attempts) == 1

    def test_an_authentication_failure_is_never_retried(self) -> None:
        attempts: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            attempts.append(1)
            return httpx.Response(302, headers={"location": "/data/invalid_key.html"})

        client = CensusClient(api_key=_SENTINEL_KEY, max_attempts=3)
        with _transport(client, handler):
            with pytest.raises(CensusAuthError):
                client.get_resconst("2026-08")

        assert len(attempts) == 1


class TestResponseBounding:
    def test_an_oversized_response_is_refused(self) -> None:
        oversized = b"[" + b"0" * (MAX_RESPONSE_BYTES + 1) + b"]"

        client = CensusClient(api_key=_SENTINEL_KEY)
        with _transport(client, lambda request: httpx.Response(200, content=oversized)):
            with pytest.raises(CensusUpstreamError, match="byte bound"):
                client.get_resconst("2026-08")

    def test_a_non_json_response_is_refused(self) -> None:
        client = CensusClient(api_key=_SENTINEL_KEY)
        with _transport(client, lambda request: httpx.Response(200, text="<html>nope</html>")):
            with pytest.raises(CensusUpstreamError, match="non-JSON"):
                client.get_resconst("2026-08")


class TestEnvelopeValidation:
    """A broken ENVELOPE raises: nothing in the body can be trusted."""

    @pytest.mark.parametrize("payload", [[], {}, "rows", None])
    def test_an_unexpected_payload_shape_raises(self, payload) -> None:
        with pytest.raises(CensusUpstreamError, match="payload shape|header row"):
            _parse(payload, RESCONST_DATASET)

    def test_an_unreadable_header_raises(self) -> None:
        with pytest.raises(CensusUpstreamError, match="header row"):
            _parse([[1, 2, 3]], RESCONST_DATASET)

    def test_a_missing_expected_column_raises_and_names_it(self) -> None:
        header = [name for name in _HEADER if name != "seasonally_adj"]
        with pytest.raises(CensusUpstreamError, match="seasonally_adj"):
            _parse([header], RESCONST_DATASET)

    def test_a_response_with_only_a_header_is_not_an_error(self) -> None:
        """A period Census has no data for. An ordinary outcome."""
        accepted, rejected = _parse([_HEADER], RESCONST_DATASET)
        assert accepted == []
        assert rejected == []


class TestRowValidation:
    """A broken ROW is rejected and counted: one bad row among 26,773
    must not discard the rest, and must not vanish either."""

    def test_a_valid_row_is_parsed_with_census_vocabulary_intact(self) -> None:
        accepted, rejected = _parse(_payload(_row()), RESCONST_DATASET)
        assert rejected == []
        (row,) = accepted
        assert row.period == date(2026, 8, 1)
        assert row.category_code == "APERMITS"
        assert row.data_type_code == "TOTAL"
        assert row.seasonally_adjusted is True
        assert row.is_error_measure is False
        # NOT converted. The 1000x scaling belongs to the binding.
        assert row.value == 1394.0

    def test_the_period_is_the_first_of_the_month(self) -> None:
        accepted, _ = _parse(_payload(_row(time="1959-01")), RESCONST_DATASET)
        assert accepted[0].period == date(1959, 1, 1)

    def test_an_unadjusted_row_is_flagged_as_such(self) -> None:
        accepted, _ = _parse(
            _payload(_row(category_code="PERMITS", seasonally_adj="no", cell_value="117.4")),
            RESCONST_DATASET,
        )
        assert accepted[0].seasonally_adjusted is False
        assert accepted[0].value == 117.4

    def test_an_error_measure_row_is_flagged_not_dropped(self) -> None:
        """Census's reliability statistics are real output. The boundary
        labels them; the ingestion service decides they are not economic
        observations."""
        accepted, rejected = _parse(
            _payload(_row(data_type_code="E_TOTAL", error_data="yes", cell_value="6")),
            RESCONST_DATASET,
        )
        assert rejected == []
        assert accepted[0].is_error_measure is True

    @pytest.mark.parametrize("raw", [None, "", "   ", "n/a", "(NA)", "-", "1,394"])
    def test_an_unusable_value_becomes_none_and_never_zero(self, raw) -> None:
        """THE most important row-level rule. A missing count and a count
        of zero are different economic facts."""
        accepted, _ = _parse(_payload(_row(cell_value=raw)), RESCONST_DATASET)
        assert accepted[0].value is None
        assert accepted[0].value != 0

    def test_a_numeric_zero_is_preserved_as_zero(self) -> None:
        """The complement: an actual published zero must survive. Guarding
        against a null-handling fix that swallows real zeros too."""
        accepted, _ = _parse(_payload(_row(cell_value="0")), RESCONST_DATASET)
        assert accepted[0].value == 0.0

    def test_a_wrong_length_row_is_rejected(self) -> None:
        accepted, rejected = _parse([_HEADER, ["1394", "TOTAL"]], RESCONST_DATASET)
        assert accepted == []
        assert rejected == [CensusRejectedRow(reason="MALFORMED_ROW", category_code=None, data_type_code=None)]

    def test_a_row_from_another_program_is_rejected(self) -> None:
        accepted, rejected = _parse(_payload(_row(program_code="MARTS")), RESCONST_DATASET)
        assert accepted == []
        assert rejected[0].reason == "UNEXPECTED_PROGRAM"

    def test_a_sub_national_row_is_rejected(self) -> None:
        """#45's scope is national. A regional row joining a national
        series would be a silent aggregation error."""
        accepted, rejected = _parse(_payload(_row(geo_level_code="REGION")), RESCONST_DATASET)
        assert accepted == []
        assert rejected[0].reason == "NON_NATIONAL_GEOGRAPHY"

    def test_a_non_monthly_time_slot_is_rejected(self) -> None:
        accepted, rejected = _parse(_payload(_row(time_slot_id="3")), RESCONST_DATASET)
        assert accepted == []
        assert rejected[0].reason == "NON_MONTHLY_TIME_SLOT"

    @pytest.mark.parametrize("flag_field", ["error_data", "seasonally_adj"])
    def test_an_unrecognised_flag_is_rejected_rather_than_defaulted(self, flag_field: str) -> None:
        """Both flags guard a semantic distinction. Defaulting either one
        could put a seasonally adjusted value into an unadjusted series,
        or a standard error into a housing count."""
        accepted, rejected = _parse(_payload(_row(**{flag_field: "maybe"})), RESCONST_DATASET)
        assert accepted == []
        assert rejected[0].reason == "UNRECOGNISED_FLAG"

    @pytest.mark.parametrize("bad_time", ["2026", "2026-13", "not-a-date", ""])
    def test_an_unparseable_period_is_rejected(self, bad_time: str) -> None:
        accepted, rejected = _parse(_payload(_row(time=bad_time)), RESCONST_DATASET)
        assert accepted == []
        assert rejected[0].reason == "UNPARSEABLE_PERIOD"

    def test_a_row_missing_its_identity_is_rejected(self) -> None:
        accepted, rejected = _parse(_payload(_row(category_code="")), RESCONST_DATASET)
        assert accepted == []
        assert rejected[0].reason == "MISSING_IDENTITY"

    def test_one_bad_row_does_not_discard_the_good_ones(self) -> None:
        accepted, rejected = _parse(
            _payload(
                _row(time="2026-07", cell_value="1433"),
                _row(time="bad"),
                _row(time="2026-08", cell_value="1394"),
            ),
            RESCONST_DATASET,
        )
        assert [row.value for row in accepted] == [1433.0, 1394.0]
        assert len(rejected) == 1

    def test_rejection_reasons_carry_no_provider_text(self) -> None:
        """A reason code is logged and persisted, so it must be a fixed
        vocabulary rather than anything the upstream chose."""
        _, rejected = _parse(_payload(_row(program_code="<script>alert(1)</script>")), RESCONST_DATASET)
        assert rejected[0].reason == "UNEXPECTED_PROGRAM"
        assert "<script>" not in rejected[0].reason


class TestOrdering:
    def test_rows_are_returned_in_a_deterministic_order(self) -> None:
        """Upstream ordering is not guaranteed, and a caller's output
        must not depend on it."""
        accepted, _ = _parse(
            _payload(
                _row(time="2026-08", category_code="ASTARTS"),
                _row(time="2026-07", category_code="APERMITS"),
                _row(time="2026-08", category_code="APERMITS"),
            ),
            RESCONST_DATASET,
        )
        assert [(row.period.isoformat(), row.category_code) for row in accepted] == [
            ("2026-07-01", "APERMITS"),
            ("2026-08-01", "APERMITS"),
            ("2026-08-01", "ASTARTS"),
        ]


class TestParserPurity:
    def test_parsing_needs_no_client_and_no_credential(self) -> None:
        """`_parse` is a module-level function on purpose: it touches no
        socket and no secret, so a captured payload is enough to test it.
        This asserts that property rather than merely relying on it."""
        payload = json.loads(json.dumps(_payload(_row())))
        accepted, rejected = _parse(payload, RESCONST_DATASET)
        assert len(accepted) == 1 and rejected == []


# ----------------------------------------------------------------------
# Transport plumbing
#
# `CensusClient` constructs its own `httpx.Client` inside `_get` -- the
# same shape `TreasuryClient` and `FREDClient` use -- so a mock transport
# is injected by patching the constructor for the duration of a call
# rather than by adding a seam to production code that exists only for
# tests.
# ----------------------------------------------------------------------

@contextlib.contextmanager
def _transport(client: CensusClient, handler):
    real_client = httpx.Client

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    with patch("app.clients.census.httpx.Client", factory):
        yield client


def _full_traceback_text(exc_info) -> str:
    """Every chained exception's text, which is what a traceback actually
    prints. `str(exc)` alone would miss a key leaked via `raise ... from
    exc` on an httpx error carrying the request URL."""
    import traceback

    return "".join(traceback.format_exception(exc_info.value))
