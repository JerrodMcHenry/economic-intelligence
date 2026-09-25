"""The first-party release schedule (Increment #56B).

WHY A COMMITTED SCHEDULE, AND NOT A FEED. Release processing is
triggered by release occurrences. Until #56B they came from FRED's
calendar API. The two replacements that exist are:

- **BEA** publishes `apps.bea.gov/API/signup/release_dates.json`
  (keyless, machine-readable, verified 2026-09-24).
- **BLS** publishes an iCalendar feed that refuses non-browser clients
  ("Access Denied" to a scripted request, #54B). Working around a
  publisher's bot protection is not something this project does.

Three releases a month, published a year at a time, do not justify a
feed client for one agency and a scraper for the other. The minimum
reliable mechanism is this file: every date copied from the agency's own
schedule page, reviewed in code, and refreshed once a year when the
agencies publish the next year (BLS and BEA both publish in the autumn).
When it runs out, `app.services.release_schedule.schedule_status` says so
loudly -- EXPIRING 45 days ahead, EXPIRED once the last date has passed
-- and the manual path (`python -m app.operations.import_first_party`)
keeps the data current in the meantime.

Dates are the agencies' calendar dates (all 8:30 a.m. Eastern). The
time of day is not modelled: release processing treats a scheduled
date as eligible from the start of that day, as it always has.
"""

from dataclasses import dataclass
from datetime import date

#: When these dates were last checked against the agencies' pages.
SCHEDULE_VERIFIED_ON = date(2026, 9, 24)

#: EXPIRING when the last scheduled date is closer than this.
EXPIRY_WARNING_DAYS = 45


@dataclass(frozen=True)
class ScheduledRelease:
    provider: str
    provider_release_id: str
    name: str
    #: Where the dates below were copied from.
    source_url: str
    dates: tuple[date, ...]


def _dates(*values: str) -> tuple[date, ...]:
    return tuple(sorted(date.fromisoformat(value) for value in values))


RELEASE_SCHEDULE: tuple[ScheduledRelease, ...] = (
    ScheduledRelease(
        provider="BLS",
        provider_release_id="cpi",
        name="Consumer Price Index",
        source_url="https://www.bls.gov/schedule/news_release/cpi.htm",
        dates=_dates(
            "2026-01-13", "2026-02-13", "2026-03-11", "2026-04-10", "2026-05-12", "2026-06-10",
            "2026-07-14", "2026-08-12", "2026-09-11", "2026-10-14", "2026-11-10", "2026-12-10",
        ),
    ),
    ScheduledRelease(
        provider="BLS",
        provider_release_id="empsit",
        name="Employment Situation",
        source_url="https://www.bls.gov/schedule/news_release/empsit.htm",
        dates=_dates(
            "2026-01-09", "2026-02-11", "2026-03-06", "2026-04-03", "2026-05-08", "2026-06-05",
            "2026-07-02", "2026-08-07", "2026-09-04", "2026-10-02", "2026-11-06", "2026-12-04",
        ),
    ),
    ScheduledRelease(
        provider="BEA",
        provider_release_id="pio",
        name="Personal Income and Outlays",
        source_url="https://apps.bea.gov/API/signup/release_dates.json",
        # Thirteen dates in 2026, exactly as BEA's schedule lists them
        # (including both April 9 and April 30). Not reconciled against
        # anything but BEA's own file.
        dates=_dates(
            "2026-01-22", "2026-02-20", "2026-03-13", "2026-04-09", "2026-04-30", "2026-05-28", "2026-06-25",
            "2026-07-30", "2026-08-26", "2026-09-30", "2026-10-29", "2026-11-25", "2026-12-23",
        ),
    ),
)
