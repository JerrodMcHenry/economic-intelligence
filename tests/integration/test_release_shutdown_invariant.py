"""Dedicated regression test for the permanent shutdown/missing-data
invariant (see docs/architecture/release-intelligence-v1.md #2/#11): a
scheduled release date passing must never itself cause an
`EconomicObservation` write or a monitor state change.

Deliberately structural, not an inflation-domain test -- this proves
the tables never move; it does not exercise `inflation_v1.0`'s own
classification logic at all (see
tests/integration/test_transaction_and_safety.py's
`TestReleaseCalendarStructuralIndependence` for the general, import-
level version of the same proof).
"""

from datetime import date

from sqlalchemy import select

from app.db.models import EconomicObservation, EconomicRelease
from app.domain.releases import classify_schedule_status
from app.repositories.release_repository import ReleaseRepository


def test_a_scheduled_date_passing_never_writes_an_observation_or_changes_the_occurrence(db_session):
    """The October 2025 CPI-style scenario, in miniature:

    1. A release occurrence is scheduled.
    2. `as_of_date` moves past it -- derived status becomes PAST_DUE.
    3. Zero `EconomicObservation` rows exist before or after this --
       nothing about the schedule date passing ever created one.
    4. The occurrence itself is unchanged by the status derivation --
       there is no persisted status column on it for anything to have
       flipped; `classify_schedule_status` is a pure, read-only
       computation with no write path at all.
    """
    # A synthetic identity, not the real curated CPI row (provider_release_id
    # "10", seeded by alembic/versions/fbbe6b1ab8d9_*.py) -- this test
    # proves the structural invariant with its own isolated fixture data,
    # not by depending on (or colliding with) the real curated catalog.
    release = EconomicRelease(name="Consumer Price Index (test fixture)", provider="FRED", provider_release_id="9001")
    db_session.add(release)
    db_session.flush()

    scheduled_date = date(2025, 10, 15)  # the real October 2025 CPI-style scheduled date
    repo = ReleaseRepository(db_session)
    occurrence = repo.upsert_occurrence(release.id, scheduled_date)
    db_session.flush()

    assert db_session.execute(select(EconomicObservation)).first() is None

    as_of_date_before = date(2025, 10, 1)
    as_of_date_after = date(2025, 11, 1)  # the scheduled date has now passed, with nothing published

    assert classify_schedule_status(occurrence.scheduled_date, as_of_date_before) == "SCHEDULED"
    assert classify_schedule_status(occurrence.scheduled_date, as_of_date_after) == "PAST_DUE"

    # The status derivation above is a pure computation over already-
    # persisted values -- it wrote nothing. Still zero observations,
    # and the occurrence's own scheduled_date is exactly what was
    # persisted, never rewritten to hide that the date passed.
    assert db_session.execute(select(EconomicObservation)).first() is None
    rows, total = repo.list_occurrences(start_date=None, end_date=None, limit=10, offset=0, order="asc")
    assert total == 1
    assert rows[0][1].scheduled_date == scheduled_date
