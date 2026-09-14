"""Data-access layer for the release calendar.

Owns all SQLAlchemy query/persistence operations against
`economic_releases` and `release_occurrences`. Operates entirely within
a caller-provided `Session` and never calls `commit()`/`rollback()`
itself -- the caller owns the transaction boundary (see
`app.db.session.session_scope`), same discipline as `SeriesRepository`
(see docs/adr/009-repository-boundary.md).

Never imports `app.clients.fred` or `httpx` (checked by
`tests/integration/test_transaction_and_safety.py`), and never touches
`EconomicSeries`/`EconomicObservation` -- structurally incapable of
writing canonical economic data (see
docs/architecture/release-intelligence-v1.md #2).
"""

from datetime import date, datetime, timezone
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import EconomicRelease, ReleaseOccurrence


class ReleaseRepository:
    def __init__(self, session: Session):
        self._session = session

    def get_active_releases(self) -> list[EconomicRelease]:
        """The curated, active release catalog -- deterministic order
        (by name) so callers iterating it (e.g. sync) behave
        reproducibly across runs."""
        rows = self._session.execute(
            select(EconomicRelease).where(EconomicRelease.active.is_(True)).order_by(EconomicRelease.name.asc())
        ).scalars()
        return list(rows)

    def get_release_by_provider_identity(self, provider: str, provider_release_id: str) -> EconomicRelease | None:
        """Look up a persisted release by its provider identity -- the
        same separation `SeriesRepository.get_series_by_series_id`
        already applies between EI's own `id` and a provider's business
        identifier."""
        return self._session.execute(
            select(EconomicRelease).where(
                EconomicRelease.provider == provider,
                EconomicRelease.provider_release_id == provider_release_id,
            )
        ).scalar_one_or_none()

    def get_occurrence_by_id(self, occurrence_id: int) -> ReleaseOccurrence | None:
        """Look up one persisted occurrence by its own internal id --
        added for Increment #18's operational entry point (see
        `app.services.release_processing`), which is given an explicit
        occurrence identifier and needs its `scheduled_date` (for
        eligibility) and parent `EconomicRelease` (via the existing
        `release` relationship). A plain, read-only query -- adds no
        write capability and does not change this class's existing
        read-only-for-calendar-metadata character."""
        return self._session.execute(
            select(ReleaseOccurrence).where(ReleaseOccurrence.id == occurrence_id)
        ).scalar_one_or_none()

    def upsert_occurrence(self, economic_release_id: int, scheduled_date: date) -> ReleaseOccurrence:
        """Idempotent upsert keyed on `(economic_release_id, scheduled_date)`
        -- the frozen occurrence identity (see
        docs/architecture/release-intelligence-v1.md #6/#8).

        An already-persisted occurrence has only `last_seen_at` refreshed;
        `first_seen_at` is preserved forever, and there is no other
        mutable field to update (the frozen contract carries no time,
        timezone, or status column). A new occurrence is inserted with
        `first_seen_at == last_seen_at`. Never deletes anything.
        """
        now = datetime.now(timezone.utc)
        existing = self._session.execute(
            select(ReleaseOccurrence).where(
                ReleaseOccurrence.economic_release_id == economic_release_id,
                ReleaseOccurrence.scheduled_date == scheduled_date,
            )
        ).scalar_one_or_none()

        if existing is not None:
            existing.last_seen_at = now
            return existing

        occurrence = ReleaseOccurrence(
            economic_release_id=economic_release_id,
            scheduled_date=scheduled_date,
            first_seen_at=now,
            last_seen_at=now,
        )
        self._session.add(occurrence)
        self._session.flush()  # assigns occurrence.id
        return occurrence

    def list_occurrences(
        self,
        start_date: date | None,
        end_date: date | None,
        limit: int,
        offset: int,
        order: Literal["asc", "desc"],
    ) -> tuple[list[tuple[EconomicRelease, ReleaseOccurrence]], int]:
        """Query persisted occurrences joined to their release,
        filtered/ordered/paginated. Returns `(page, total)`, where
        `total` is the count matching the date filters *before*
        `limit`/`offset` -- same pattern as
        `SeriesRepository.get_observations`, so the two always agree.

        Ordering is fully deterministic: `scheduled_date` in the
        requested direction, then `EconomicRelease.name` and
        `ReleaseOccurrence.id` ascending as stable tie-breakers (two
        different releases can legitimately share a `scheduled_date`,
        unlike `EconomicObservation.observation_date`, which is unique
        per series).
        """
        conditions = []
        if start_date is not None:
            conditions.append(ReleaseOccurrence.scheduled_date >= start_date)
        if end_date is not None:
            conditions.append(ReleaseOccurrence.scheduled_date <= end_date)

        total = self._session.execute(
            select(func.count()).select_from(ReleaseOccurrence).where(*conditions)
        ).scalar_one()

        scheduled_date_order = (
            ReleaseOccurrence.scheduled_date.asc() if order == "asc" else ReleaseOccurrence.scheduled_date.desc()
        )
        rows = self._session.execute(
            select(EconomicRelease, ReleaseOccurrence)
            .join(ReleaseOccurrence, ReleaseOccurrence.economic_release_id == EconomicRelease.id)
            .where(*conditions)
            .order_by(scheduled_date_order, EconomicRelease.name.asc(), ReleaseOccurrence.id.asc())
            .limit(limit)
            .offset(offset)
        ).all()

        return [(row[0], row[1]) for row in rows], total
