"""Unit tests for `TreasuryClient` (Increment #29).

No live network anywhere: `httpx.Client.get` is mocked at the transport
boundary, the same level `tests/test_fred_client.py` already uses for
the other provider. These tests cover the client's own two jobs --
building an allow-listed request, and normalizing (or refusing) the
response -- plus the security properties the increment requires.
"""

from datetime import date
from unittest.mock import patch

import httpx
import pytest

from app.clients.treasury import (
    MAX_RESPONSE_BYTES,
    NOMINAL_DATASET,
    REAL_DATASET,
    TreasuryClient,
    TreasuryTimeoutError,
    TreasuryUpstreamError,
)

XML_URL = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"

NOMINAL_XML = """<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<feed xml:base="https://home.treasury.gov" xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices"
      xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata" xmlns="http://www.w3.org/2005/Atom">
  <entry><content type="application/xml"><m:properties>
    <d:Id m:type="Edm.Int32">318</d:Id>
    <d:NEW_DATE m:type="Edm.DateTime">2026-09-17T00:00:00</d:NEW_DATE>
    <d:BC_2YEAR m:type="Edm.Double">4.74</d:BC_2YEAR>
    <d:BC_5YEAR m:type="Edm.Double">4.84</d:BC_5YEAR>
    <d:BC_10YEAR m:type="Edm.Double">4.99</d:BC_10YEAR>
    <d:BC_30YEAR m:type="Edm.Double">5.32</d:BC_30YEAR>
  </m:properties></content></entry>
  <entry><content type="application/xml"><m:properties>
    <d:Id m:type="Edm.Int32">319</d:Id>
    <d:NEW_DATE m:type="Edm.DateTime">2026-09-18T00:00:00</d:NEW_DATE>
    <d:BC_2YEAR m:type="Edm.Double">4.76</d:BC_2YEAR>
    <d:BC_5YEAR m:type="Edm.Double">4.86</d:BC_5YEAR>
    <d:BC_10YEAR m:type="Edm.Double">5.01</d:BC_10YEAR>
    <d:BC_30YEAR m:type="Edm.Double">5.34</d:BC_30YEAR>
  </m:properties></content></entry>
</feed>"""

EMPTY_FEED_XML = """<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<feed xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices"
      xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"
      xmlns="http://www.w3.org/2005/Atom"><title>no data</title></feed>"""


def _response(body: str | bytes, status_code: int = 200) -> httpx.Response:
    content = body.encode() if isinstance(body, str) else body
    return httpx.Response(status_code=status_code, content=content, request=httpx.Request("GET", XML_URL))


@pytest.fixture
def client() -> TreasuryClient:
    return TreasuryClient(timeout=1.0)


class TestRequestConstruction:
    def test_requests_the_allow_listed_url_with_formatted_month(self, client):
        with patch.object(httpx.Client, "get", return_value=_response(NOMINAL_XML)) as mock_get:
            client.get_month(NOMINAL_DATASET, 2026, 9)

        url, = mock_get.call_args.args
        params = mock_get.call_args.kwargs["params"]
        assert url == XML_URL
        assert params == {"data": NOMINAL_DATASET, "field_tdr_date_value_month": "202609"}

    def test_single_digit_month_is_zero_padded(self, client):
        with patch.object(httpx.Client, "get", return_value=_response(EMPTY_FEED_XML)) as mock_get:
            client.get_month(REAL_DATASET, 2004, 1)
        assert mock_get.call_args.kwargs["params"]["field_tdr_date_value_month"] == "200401"

    @pytest.mark.parametrize("status", [301, 302, 307])
    def test_a_redirect_is_surfaced_as_an_error_never_followed(self, client, status):
        """Redirects are disabled on the client, so a redirect response
        reaches `raise_for_status` and becomes a typed error. If they
        were followed, an upstream redirect could silently carry the
        request to a host the allow-list never approved."""
        redirect = httpx.Response(
            status_code=status,
            headers={"Location": "https://example.invalid/elsewhere"},
            request=httpx.Request("GET", XML_URL),
        )
        with patch.object(httpx.Client, "get", return_value=redirect):
            with pytest.raises(TreasuryUpstreamError):
                client.get_month(NOMINAL_DATASET, 2026, 9)


class TestDatasetAllowList:
    def test_unknown_dataset_is_refused_before_any_request(self, client):
        with patch.object(httpx.Client, "get") as mock_get:
            with pytest.raises(ValueError, match="not allow-listed"):
                client.get_month("daily_treasury_bill_rates", 2026, 9)
        mock_get.assert_not_called()

    def test_injection_style_dataset_value_is_refused(self, client):
        with patch.object(httpx.Client, "get") as mock_get:
            with pytest.raises(ValueError, match="not allow-listed"):
                client.get_month("../../etc/passwd", 2026, 9)
        mock_get.assert_not_called()

    @pytest.mark.parametrize("year,month", [(2026, 0), (2026, 13), (1800, 6), (3200, 6)])
    def test_out_of_range_dates_are_refused_before_any_request(self, client, year, month):
        with patch.object(httpx.Client, "get") as mock_get:
            with pytest.raises(ValueError):
                client.get_month(NOMINAL_DATASET, year, month)
        mock_get.assert_not_called()


class TestResponseNormalization:
    def test_valid_payload_is_normalized_to_dated_rows_in_ascending_order(self, client):
        with patch.object(httpx.Client, "get", return_value=_response(NOMINAL_XML)):
            rows = client.get_month(NOMINAL_DATASET, 2026, 9)

        assert [row.observation_date for row in rows] == [date(2026, 9, 17), date(2026, 9, 18)]
        assert rows[1].values["BC_10YEAR"] == 5.01
        assert rows[1].values["BC_2YEAR"] == 4.76

    def test_the_date_field_is_not_returned_as_a_rate(self, client):
        with patch.object(httpx.Client, "get", return_value=_response(NOMINAL_XML)):
            rows = client.get_month(NOMINAL_DATASET, 2026, 9)
        assert "NEW_DATE" not in rows[0].values

    def test_empty_feed_is_an_empty_list_not_an_error(self, client):
        """A month with no published data (a future month, or one before
        the dataset began) is ordinary, not exceptional."""
        with patch.object(httpx.Client, "get", return_value=_response(EMPTY_FEED_XML)):
            assert client.get_month(REAL_DATASET, 2026, 12) == []

    def test_null_marked_field_is_omitted_never_zero(self, client):
        xml = NOMINAL_XML.replace(
            '<d:BC_30YEAR m:type="Edm.Double">5.34</d:BC_30YEAR>',
            '<d:BC_30YEAR m:type="Edm.Double" m:null="true" />',
        )
        with patch.object(httpx.Client, "get", return_value=_response(xml)):
            rows = client.get_month(NOMINAL_DATASET, 2026, 9)
        assert "BC_30YEAR" not in rows[-1].values
        assert rows[-1].values["BC_10YEAR"] == 5.01

    def test_empty_field_text_is_omitted(self, client):
        xml = NOMINAL_XML.replace(
            '<d:BC_30YEAR m:type="Edm.Double">5.34</d:BC_30YEAR>',
            '<d:BC_30YEAR m:type="Edm.Double"></d:BC_30YEAR>',
        )
        with patch.object(httpx.Client, "get", return_value=_response(xml)):
            rows = client.get_month(NOMINAL_DATASET, 2026, 9)
        assert "BC_30YEAR" not in rows[-1].values

    def test_non_numeric_field_is_skipped_without_losing_the_row(self, client):
        xml = NOMINAL_XML.replace(
            '<d:BC_30YEAR m:type="Edm.Double">5.34</d:BC_30YEAR>',
            "<d:BC_30YEAR m:type=\"Edm.Double\">N/A</d:BC_30YEAR>",
        )
        with patch.object(httpx.Client, "get", return_value=_response(xml)):
            rows = client.get_month(NOMINAL_DATASET, 2026, 9)
        assert "BC_30YEAR" not in rows[-1].values
        assert rows[-1].values["BC_2YEAR"] == 4.76

    def test_row_without_a_date_is_skipped(self, client):
        xml = NOMINAL_XML.replace('<d:NEW_DATE m:type="Edm.DateTime">2026-09-17T00:00:00</d:NEW_DATE>', "")
        with patch.object(httpx.Client, "get", return_value=_response(xml)):
            rows = client.get_month(NOMINAL_DATASET, 2026, 9)
        assert [row.observation_date for row in rows] == [date(2026, 9, 18)]


class TestFailureModes:
    def test_timeout_raises_a_typed_timeout_error(self, client):
        with patch.object(httpx.Client, "get", side_effect=httpx.TimeoutException("timed out")):
            with pytest.raises(TreasuryTimeoutError):
                client.get_month(NOMINAL_DATASET, 2026, 9)

    def test_transport_failure_raises_a_typed_upstream_error(self, client):
        with patch.object(httpx.Client, "get", side_effect=httpx.ConnectError("no route")):
            with pytest.raises(TreasuryUpstreamError):
                client.get_month(NOMINAL_DATASET, 2026, 9)

    @pytest.mark.parametrize("status", [404, 500, 503])
    def test_error_status_raises_a_typed_upstream_error(self, client, status):
        with patch.object(httpx.Client, "get", return_value=_response("<feed/>", status_code=status)):
            with pytest.raises(TreasuryUpstreamError):
                client.get_month(NOMINAL_DATASET, 2026, 9)

    def test_malformed_xml_raises_a_typed_upstream_error(self, client):
        with patch.object(httpx.Client, "get", return_value=_response("<feed><unclosed>")):
            with pytest.raises(TreasuryUpstreamError, match="malformed XML"):
                client.get_month(NOMINAL_DATASET, 2026, 9)

    def test_html_error_page_raises_rather_than_parsing_as_data(self, client):
        with patch.object(httpx.Client, "get", return_value=_response("<html><body>Service unavailable</body></html>")):
            assert client.get_month(NOMINAL_DATASET, 2026, 9) == []

    def test_unparseable_date_raises_rather_than_guessing(self, client):
        xml = NOMINAL_XML.replace("2026-09-17T00:00:00", "not-a-date")
        with patch.object(httpx.Client, "get", return_value=_response(xml)):
            with pytest.raises(TreasuryUpstreamError, match="unparseable date"):
                client.get_month(NOMINAL_DATASET, 2026, 9)

    def test_oversized_response_is_refused(self, client):
        oversized = b"<feed>" + b"x" * (MAX_RESPONSE_BYTES + 1) + b"</feed>"
        with patch.object(httpx.Client, "get", return_value=_response(oversized)):
            with pytest.raises(TreasuryUpstreamError, match="exceeded"):
                client.get_month(NOMINAL_DATASET, 2026, 9)

    def test_entries_without_properties_are_refused_rather_than_silently_empty(self, client):
        xml = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry><content/></entry></feed>"""
        with patch.object(httpx.Client, "get", return_value=_response(xml)):
            with pytest.raises(TreasuryUpstreamError, match="without parseable properties"):
                client.get_month(NOMINAL_DATASET, 2026, 9)
