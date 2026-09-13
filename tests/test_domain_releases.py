"""Pure domain tests for app.domain.releases -- no DB, no FRED, no
FastAPI, no system clock. Mirrors the style of
tests/test_domain_inflation.py's classification tests.
"""

import inspect
from datetime import date, timedelta

from app.domain.releases import classify_schedule_status


class TestClassifyScheduleStatus:
    def test_future_scheduled_date_is_scheduled(self):
        assert classify_schedule_status(date(2026, 8, 1), as_of_date=date(2026, 7, 1)) == "SCHEDULED"

    def test_scheduled_date_equal_to_as_of_date_is_scheduled(self):
        assert classify_schedule_status(date(2026, 8, 1), as_of_date=date(2026, 8, 1)) == "SCHEDULED"

    def test_scheduled_date_before_as_of_date_is_past_due(self):
        assert classify_schedule_status(date(2026, 8, 1), as_of_date=date(2026, 8, 2)) == "PAST_DUE"

    def test_repeated_calls_with_identical_inputs_produce_identical_results(self):
        result_1 = classify_schedule_status(date(2025, 10, 15), as_of_date=date(2026, 1, 1))
        result_2 = classify_schedule_status(date(2025, 10, 15), as_of_date=date(2026, 1, 1))
        assert result_1 == result_2 == "PAST_DUE"

    def test_only_scheduled_and_past_due_are_ever_produced(self):
        """No third value (UNKNOWN/CANCELLED) is reachable -- swept
        across a wide range of (scheduled_date, as_of_date) offsets."""
        scheduled = date(2026, 1, 15)
        results = {classify_schedule_status(scheduled, scheduled + timedelta(days=offset)) for offset in range(-10, 11)}
        assert results <= {"SCHEDULED", "PAST_DUE"}
        assert results == {"SCHEDULED", "PAST_DUE"}  # both are actually reachable, not just permitted

    def test_as_of_date_has_no_default_and_must_be_passed_explicitly(self):
        """Structural proof there is no hidden `date.today()` fallback:
        a caller cannot omit `as_of_date` and get an implicit "now"."""
        signature = inspect.signature(classify_schedule_status)
        assert signature.parameters["as_of_date"].default is inspect.Parameter.empty

    def test_domain_module_never_reads_the_system_clock(self):
        """Source-level guard: neither `date.today()` nor `datetime.now()`
        appears anywhere in this module -- the only way "now" can ever
        enter this function is as an explicit argument from the caller."""
        import app.domain.releases as releases_module

        source = inspect.getsource(releases_module)
        assert "today(" not in source
        assert "now(" not in source
