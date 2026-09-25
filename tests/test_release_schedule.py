"""Increment #56B: the committed first-party release schedule and its
status. Pure -- no database, no network."""

from datetime import date, timedelta

import pytest

from app.models.release_schedule import EXPIRY_WARNING_DAYS, RELEASE_SCHEDULE, ScheduledRelease
from app.services.release_schedule import schedule_status


def _one(*dates: str) -> tuple[ScheduledRelease, ...]:
    return (
        ScheduledRelease("BLS", "cpi", "Consumer Price Index", "https://www.bls.gov/schedule/news_release/cpi.htm",
                         tuple(date.fromisoformat(d) for d in dates)),
    )


class TestTheCommittedSchedule:
    def test_it_covers_exactly_the_three_releases_that_drive_data(self):
        assert sorted((r.provider, r.provider_release_id) for r in RELEASE_SCHEDULE) == [
            ("BEA", "pio"),
            ("BLS", "cpi"),
            ("BLS", "empsit"),
        ]

    def test_every_date_cites_the_agency_page_it_came_from(self):
        for release in RELEASE_SCHEDULE:
            host = "bls.gov" if release.provider == "BLS" else "bea.gov"
            assert host in release.source_url
            assert "stlouisfed" not in release.source_url

    def test_dates_are_sorted_unique_and_2026(self):
        for release in RELEASE_SCHEDULE:
            assert list(release.dates) == sorted(set(release.dates))
            assert all(d.year == 2026 for d in release.dates)

    @pytest.mark.parametrize(
        "provider_release_id, known",
        [
            # Spot checks against the agencies' published tables.
            ("cpi", date(2026, 9, 11)),
            ("cpi", date(2026, 10, 14)),
            ("empsit", date(2026, 9, 4)),
            ("empsit", date(2026, 10, 2)),
            ("pio", date(2026, 9, 30)),
            ("pio", date(2026, 12, 23)),
        ],
    )
    def test_known_published_dates_are_present(self, provider_release_id, known):
        release = next(r for r in RELEASE_SCHEDULE if r.provider_release_id == provider_release_id)
        assert known in release.dates


class TestStatus:
    def test_ok_while_the_schedule_runs_well_ahead(self):
        (status,) = schedule_status(date(2026, 3, 1), _one("2026-03-10", "2026-12-10"))
        assert (status.state, status.next_date, status.last_date) == ("OK", date(2026, 3, 10), date(2026, 12, 10))

    def test_expiring_inside_the_warning_window(self):
        today = date(2026, 12, 10) - timedelta(days=EXPIRY_WARNING_DAYS - 1)
        (status,) = schedule_status(today, _one("2026-12-10"))
        assert status.state == "EXPIRING"
        assert "ENDS 2026-12-10" in status.describe()

    def test_the_last_scheduled_day_itself_is_still_upcoming(self):
        (status,) = schedule_status(date(2026, 12, 10), _one("2026-12-10"))
        assert status.state == "EXPIRING" and status.next_date == date(2026, 12, 10)

    def test_expired_once_every_date_has_passed(self):
        (status,) = schedule_status(date(2026, 12, 11), _one("2026-12-10"))
        assert (status.state, status.next_date) == ("EXPIRED", None)
        assert "STOPPED" in status.describe()

    def test_no_dates_is_missing_never_ok(self):
        (status,) = schedule_status(date(2026, 1, 1), _one())
        assert status.state == "MISSING"

    def test_the_real_schedule_expires_after_its_last_2026_date(self):
        states = {s.provider_release_id: s.state for s in schedule_status(date(2027, 1, 1))}
        assert states == {"cpi": "EXPIRED", "empsit": "EXPIRED", "pio": "EXPIRED"}
