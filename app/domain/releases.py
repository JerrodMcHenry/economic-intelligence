"""Pure release-calendar domain logic. Frozen contract: see
docs/architecture/release-intelligence-v1.md #7.

Same no-I/O discipline as every other module in this package (see
tests/test_domain_architectural_independence.py, which this file is
registered against): no database, no FRED, no FastAPI, no OpenAI, no
environment access, no system clock. A status is a pure function of two
already-known dates, nothing else.
"""

from datetime import date
from typing import Literal

ScheduleStatus = Literal["SCHEDULED", "PAST_DUE"]


def classify_schedule_status(scheduled_date: date, as_of_date: date) -> ScheduleStatus:
    """Derive a release occurrence's schedule status.

    Deliberately takes `as_of_date` as an explicit parameter rather than
    reading the system clock itself -- every call
    site (the service layer, per the frozen spec) decides what "now"
    means and passes it in, which is what makes this function
    reproducible: the same two inputs always produce the same output,
    with no hidden dependency on when the test happens to run.

    Only two statuses exist in #17A -- `CANCELLED` and `UNKNOWN` are not
    defined here because nothing in this scope can reliably source a
    cancellation fact or ever produces an occurrence without a known
    date (see the frozen spec #7 for why neither is a gap).
    """
    if scheduled_date >= as_of_date:
        return "SCHEDULED"
    return "PAST_DUE"
