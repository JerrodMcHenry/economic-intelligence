"""Write the committed first-party schedule into release occurrences, and
say clearly when it has run out (Increment #56B).

Two functions, both deterministic given `today`:

- `schedule_status` -- per release: the next scheduled date, the last
  one, and a status. `OK`; `EXPIRING` when the last date is within
  `EXPIRY_WARNING_DAYS`; `EXPIRED` when every date has passed (the next
  release is unknown, so scheduled updates have stopped); `MISSING` when
  the release has no dates at all or its catalog row does not exist.
  Never silently "fine".
- `sync_schedule` -- idempotently upserts every scheduled date as an
  occurrence of its catalog release. Safe to run on every maintenance
  sweep; re-running writes nothing new.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from sqlalchemy.orm import Session

from app.models.release_schedule import EXPIRY_WARNING_DAYS, RELEASE_SCHEDULE, ScheduledRelease
from app.repositories.release_repository import ReleaseRepository

ScheduleState = Literal["OK", "EXPIRING", "EXPIRED", "MISSING"]


@dataclass(frozen=True)
class ReleaseScheduleStatus:
    provider: str
    provider_release_id: str
    name: str
    next_date: date | None
    last_date: date | None
    state: ScheduleState

    def describe(self) -> str:
        detail = {
            "OK": f"next {self.next_date}, schedule runs to {self.last_date}",
            "EXPIRING": f"next {self.next_date}; schedule ENDS {self.last_date} -- add the next year's dates",
            "EXPIRED": f"no scheduled date after {self.last_date} -- scheduled updates have STOPPED",
            "MISSING": "no schedule -- scheduled updates cannot run",
        }[self.state]
        return f"{self.provider} {self.provider_release_id} ({self.name}): {self.state}: {detail}"


@dataclass(frozen=True)
class ScheduleSyncOutcome:
    occurrences_created: int
    occurrences_existing: int
    missing_catalog_releases: tuple[str, ...]


def schedule_status(
    today: date, schedule: tuple[ScheduledRelease, ...] = RELEASE_SCHEDULE
) -> list[ReleaseScheduleStatus]:
    statuses = []
    for release in schedule:
        upcoming = [scheduled for scheduled in release.dates if scheduled >= today]
        last = max(release.dates) if release.dates else None
        if last is None:
            state: ScheduleState = "MISSING"
        elif not upcoming:
            state = "EXPIRED"
        elif last - today < timedelta(days=EXPIRY_WARNING_DAYS):
            state = "EXPIRING"
        else:
            state = "OK"
        statuses.append(
            ReleaseScheduleStatus(
                provider=release.provider,
                provider_release_id=release.provider_release_id,
                name=release.name,
                next_date=min(upcoming) if upcoming else None,
                last_date=last,
                state=state,
            )
        )
    return statuses


def sync_schedule(session: Session, schedule: tuple[ScheduledRelease, ...] = RELEASE_SCHEDULE) -> ScheduleSyncOutcome:
    repo = ReleaseRepository(session)
    created = existing = 0
    missing: list[str] = []
    for release in schedule:
        catalog_row = repo.get_release_by_provider_identity(release.provider, release.provider_release_id)
        if catalog_row is None or not catalog_row.active:
            # The catalog migration has not run, or someone deactivated
            # the release. Reported, never papered over by inserting one.
            missing.append(f"{release.provider}/{release.provider_release_id}")
            continue
        for scheduled in release.dates:
            if repo.occurrence_exists(catalog_row.id, scheduled):
                existing += 1
            else:
                created += 1
            repo.upsert_occurrence(catalog_row.id, scheduled)
    return ScheduleSyncOutcome(created, existing, tuple(missing))

