"""Increment #25E: proves the hard read-side prohibition frozen in
docs/product/recorded-state-history-v1.md §63 -- `GET` monitor/state-
duration/what-changed routes never create a `RecordedMonitorResult`
row, no matter how many times they're called. Reuses tests/api/conftest.py's
`client`/`_redirect_database` fixtures (real ASGI app, real isolated
test database, no FRED/AI dependency for these routes).
"""

from sqlalchemy import create_engine, text


def _recorded_monitor_result_count(test_database_url: str) -> int:
    engine = create_engine(test_database_url)
    try:
        with engine.connect() as connection:
            return connection.execute(text("SELECT COUNT(*) FROM recorded_monitor_results")).scalar_one()
    finally:
        engine.dispose()


class TestGetRoutesNeverWriteRecordedMonitorResult:
    def test_inflation_monitor_get_does_not_create_a_row(self, client, test_database_url):
        before = _recorded_monitor_result_count(test_database_url)
        response = client.get("/api/v1/monitors/inflation")
        assert response.status_code == 200
        after = _recorded_monitor_result_count(test_database_url)
        assert after == before

    def test_labor_monitor_get_does_not_create_a_row(self, client, test_database_url):
        before = _recorded_monitor_result_count(test_database_url)
        response = client.get("/api/v1/monitors/labor")
        assert response.status_code == 200
        after = _recorded_monitor_result_count(test_database_url)
        assert after == before

    def test_inflation_state_duration_get_does_not_create_a_row(self, client, test_database_url):
        before = _recorded_monitor_result_count(test_database_url)
        response = client.get("/api/v1/monitors/inflation/state-duration")
        assert response.status_code == 200
        after = _recorded_monitor_result_count(test_database_url)
        assert after == before

    def test_labor_state_duration_get_does_not_create_a_row(self, client, test_database_url):
        before = _recorded_monitor_result_count(test_database_url)
        response = client.get("/api/v1/monitors/labor/state-duration")
        assert response.status_code == 200
        after = _recorded_monitor_result_count(test_database_url)
        assert after == before

    def test_inflation_what_changed_get_does_not_create_a_row(self, client, test_database_url):
        before = _recorded_monitor_result_count(test_database_url)
        response = client.get("/api/v1/monitors/inflation/changes")
        assert response.status_code == 200
        after = _recorded_monitor_result_count(test_database_url)
        assert after == before

    def test_labor_what_changed_get_does_not_create_a_row(self, client, test_database_url):
        before = _recorded_monitor_result_count(test_database_url)
        response = client.get("/api/v1/monitors/labor/changes")
        assert response.status_code == 200
        after = _recorded_monitor_result_count(test_database_url)
        assert after == before

    def test_calling_every_get_route_repeatedly_still_creates_nothing(self, client, test_database_url):
        before = _recorded_monitor_result_count(test_database_url)
        for _ in range(3):
            assert client.get("/api/v1/monitors/inflation").status_code == 200
            assert client.get("/api/v1/monitors/labor").status_code == 200
            assert client.get("/api/v1/monitors/inflation/state-duration").status_code == 200
            assert client.get("/api/v1/monitors/labor/state-duration").status_code == 200
        after = _recorded_monitor_result_count(test_database_url)
        assert after == before
