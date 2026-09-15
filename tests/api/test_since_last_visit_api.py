"""HTTP-level tests for Increment #25G's `GET /api/v1/since-last-visit`
-- reuses tests/api/conftest.py's `client`/`_redirect_database`
fixtures (real ASGI app, real isolated test database). Frozen
contract: docs/product/since-last-visit-v1.md (#25F), specifically
§54/§78.
"""


class TestRequestValidation:
    def test_no_after_returns_200_first_visit(self, client):
        response = client.get("/api/v1/since-last-visit")
        assert response.status_code == 200
        body = response.json()
        assert body["first_visit"] is True
        assert body["after"] is None
        assert body["through"] is not None

    def test_malformed_after_is_never_a_400_falls_back_to_first_visit(self, client):
        response = client.get("/api/v1/since-last-visit", params={"after": "not-a-real-timestamp"})
        assert response.status_code == 200
        assert response.json()["first_visit"] is True

    def test_future_after_is_never_a_400_falls_back_to_first_visit(self, client):
        response = client.get("/api/v1/since-last-visit", params={"after": "2099-01-01T00:00:00+00:00"})
        assert response.status_code == 200
        assert response.json()["first_visit"] is True

    def test_timezone_naive_after_is_treated_as_unusable(self, client):
        """A naive timestamp is genuinely ambiguous -- never guessed as
        UTC (contract §65's own "no browser time" discipline, extended
        defensively to any ambiguous client input)."""
        response = client.get("/api/v1/since-last-visit", params={"after": "2026-09-01T00:00:00"})
        assert response.status_code == 200
        assert response.json()["first_visit"] is True

    def test_a_valid_recent_after_is_honored(self, client):
        response = client.get("/api/v1/since-last-visit", params={"after": "2026-09-01T00:00:00+00:00"})
        assert response.status_code == 200
        body = response.json()
        assert body["first_visit"] is False
        assert body["after"] == "2026-09-01T00:00:00Z"

    def test_a_very_old_after_is_clamped_and_disclosed(self, client):
        response = client.get("/api/v1/since-last-visit", params={"after": "2020-01-01T00:00:00+00:00"})
        assert response.status_code == 200
        body = response.json()
        assert body["first_visit"] is False
        assert body["lookback_clamped"] is True


class TestEmptyWindow:
    def test_an_empty_window_is_a_valid_typed_response_never_a_404(self, client):
        response = client.get("/api/v1/since-last-visit", params={"after": "2026-09-14T00:00:00+00:00"})
        assert response.status_code == 200
        body = response.json()
        for domain_key in ("inflation", "labor"):
            assert body[domain_key]["structural_changes"] == []
            assert body[domain_key]["recalculations"] == []
            assert body[domain_key]["source_updates"] == []


class TestResponseShape:
    def test_response_has_exactly_the_frozen_top_level_fields(self, client):
        response = client.get("/api/v1/since-last-visit")
        body = response.json()
        assert set(body.keys()) == {"after", "through", "first_visit", "lookback_clamped", "inflation", "labor"}

    def test_each_domain_recap_has_exactly_the_frozen_fields(self, client):
        response = client.get("/api/v1/since-last-visit")
        body = response.json()
        for domain_key in ("inflation", "labor"):
            assert set(body[domain_key].keys()) == {
                "monitor", "coverage", "last_checked_at", "structural_changes", "recalculations", "source_updates",
            }
            assert body[domain_key]["coverage"] in ("CHECKED", "GAP", "UNKNOWN")

    def test_domains_are_never_merged_into_one_structure(self, client):
        response = client.get("/api/v1/since-last-visit")
        body = response.json()
        assert body["inflation"]["monitor"] == "inflation"
        assert body["labor"]["monitor"] == "labor"
