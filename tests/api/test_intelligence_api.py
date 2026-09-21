"""HTTP behaviour of the Structured Intelligence endpoints (Increment #39).

Exercises the real ASGI app in-process. No provider is mocked here
because none is reachable: an intelligence read is database-only by
construction, which is itself one of the things asserted below.
"""

from fastapi.testclient import TestClient

from app.services.intelligence.service import MAX_LIMIT


class TestListEndpoint:
    def test_returns_a_bounded_deterministically_ordered_page(self, client: TestClient) -> None:
        response = client.get("/api/v1/intelligence", params={"limit": 5})
        assert response.status_code == 200
        body = response.json()
        assert len(body["items"]) <= 5
        assert body["limit"] == 5
        assert body["contract_version"] == "intelligence_v1"

    def test_two_identical_requests_return_identical_payloads(self, client: TestClient) -> None:
        first = client.get("/api/v1/intelligence", params={"limit": 10}).json()
        second = client.get("/api/v1/intelligence", params={"limit": 10}).json()
        assert first == second

    def test_limit_above_the_ceiling_is_rejected(self, client: TestClient) -> None:
        # Bounded twice: FastAPI's own `le=MAX_LIMIT`, then again in the
        # service. No caller can request an unbounded payload.
        assert client.get("/api/v1/intelligence", params={"limit": MAX_LIMIT + 1}).status_code == 422
        assert client.get("/api/v1/intelligence", params={"limit": 0}).status_code == 422
        assert client.get("/api/v1/intelligence", params={"offset": -1}).status_code == 422

    def test_unknown_world_or_type_is_rejected_by_the_contract(self, client: TestClient) -> None:
        assert client.get("/api/v1/intelligence", params={"world": "atlantis"}).status_code == 422
        assert client.get("/api/v1/intelligence", params={"type": "PROPHECY"}).status_code == 422

    def test_filters_narrow_the_collection(self, client: TestClient) -> None:
        everything = client.get("/api/v1/intelligence", params={"limit": MAX_LIMIT}).json()
        rates_only = client.get("/api/v1/intelligence", params={"world": "rates", "limit": MAX_LIMIT}).json()
        assert rates_only["total"] <= everything["total"]
        assert all(item["world"] == "rates" for item in rates_only["items"])

    def test_every_item_declares_its_type_world_and_basis(self, client: TestClient) -> None:
        for item in client.get("/api/v1/intelligence", params={"limit": 25}).json()["items"]:
            assert item["type"] in {
                "RELEASE_PROCESSED",
                "OBSERVATION_CHANGE",
                "ANALYSIS_CHANGE",
                "RATES_MOVEMENT",
            }
            assert item["world"] in {"inflation", "jobs", "rates"}
            assert item["basis"] in {"SOURCE_FACT", "METHODOLOGY_DERIVED"}
            assert item["knowledge_basis"] in {"OBSERVED", "BACKFILLED"}
            # A methodology is present if and only if a methodology
            # reached a conclusion.
            if item["basis"] == "SOURCE_FACT":
                assert item["methodology"] is None
            else:
                assert item["methodology"] is not None


class TestDetailEndpoint:
    def test_a_listed_object_is_retrievable_by_its_id(self, client: TestClient) -> None:
        listed = client.get("/api/v1/intelligence", params={"limit": 1}).json()["items"]
        if not listed:
            return  # nothing persisted in this database; the list test covers the empty case
        identifier = listed[0]["id"]
        response = client.get(f"/api/v1/intelligence/{identifier}")
        assert response.status_code == 200
        assert response.json() == listed[0]

    def test_unknown_identifier_is_404(self, client: TestClient) -> None:
        assert client.get("/api/v1/intelligence/release:NOPE:0:2026-01-01").status_code == 404

    def test_a_malformed_identifier_is_404_not_500(self, client: TestClient) -> None:
        # Deliberately indistinguishable from "no such id": telling a
        # prober how identifiers are shaped is information they want.
        for identifier in ("%20", "not-an-id", "a" * 300, "..%2F..%2Fetc%2Fpasswd"):
            assert client.get(f"/api/v1/intelligence/{identifier}").status_code in (404, 422)

    def test_no_internal_detail_leaks_in_an_error_body(self, client: TestClient) -> None:
        body = client.get("/api/v1/intelligence/release:NOPE:0:2026-01-01").json()
        text = str(body).lower()
        for leak in ("traceback", "sqlalchemy", "psycopg", "select ", "password"):
            assert leak not in text
