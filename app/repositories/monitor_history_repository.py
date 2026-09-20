"""All SQL for the point-in-time intelligence history read model
(Increment #32).

A new, read-only repository rather than methods bolted onto
`ReleaseProcessingRepository` -- the same separation `#19B`'s
`ReleaseProcessingReadRepository` and `#25G`'s
`SinceLastVisitRepository` already established, and for the same reason:
a module that can only read cannot accidentally grow a write path into
append-only history (ADR-025).

Every method takes the caller's `Session` and never commits, rolls back,
flushes, or adds -- transaction control belongs to `session_scope()` at
the route boundary (ADR-009).
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    EconomicObservation,
    EconomicSeries,
    RecordedMonitorResult,
    ReleaseObservationUpdate,
)
from app.models.series import Observation


class MonitorHistoryRepository:
    """Read-only access to recorded monitor results and the evidence
    surrounding them."""

    def __init__(self, session: Session):
        self._session = session

    # -----------------------------------------------------------------
    # Recorded results
    # -----------------------------------------------------------------

    def count_recorded_results(self, monitor: str) -> int:
        """Total matching rows BEFORE limit/offset -- the `total` every
        other paginated endpoint here reports."""
        return int(
            self._session.execute(
                select(func.count()).select_from(RecordedMonitorResult).where(RecordedMonitorResult.monitor == monitor)
            ).scalar_one()
        )

    def list_recorded_results(self, monitor: str, limit: int, offset: int) -> list[RecordedMonitorResult]:
        """One page of recorded results, newest first.

        The ordering is `calculated_at DESC, id DESC`, and the `id`
        tiebreak is load-bearing rather than defensive: every result a
        single processing run writes shares one `calculated_at`
        verbatim (recorded-state-history-v1.md §15), so a bootstrap run
        can produce dozens of rows at the exact same instant. Without a
        total order, paging would be free to return the same row twice
        and skip another.
        """
        return list(
            self._session.execute(
                select(RecordedMonitorResult)
                .where(RecordedMonitorResult.monitor == monitor)
                .order_by(RecordedMonitorResult.calculated_at.desc(), RecordedMonitorResult.id.desc())
                .limit(limit)
                .offset(offset)
            )
            .scalars()
            .all()
        )

    def get_recorded_result(self, monitor: str, recorded_result_id: int) -> RecordedMonitorResult | None:
        """Scoped by monitor as well as id, so a Labor id requested
        under `/monitors/inflation/history/...` is a 404 rather than a
        row served under the wrong monitor's heading."""
        return self._session.execute(
            select(RecordedMonitorResult).where(
                RecordedMonitorResult.id == recorded_result_id,
                RecordedMonitorResult.monitor == monitor,
            )
        ).scalar_one_or_none()

    def get_previous_recorded_result(
        self, monitor: str, calculated_at: datetime, recorded_result_id: int
    ) -> RecordedMonitorResult | None:
        """The row immediately before this one in the SAME total order
        `list_recorded_results` uses, so "previous" means the same thing
        in the list and in the detail view."""
        return self._session.execute(
            select(RecordedMonitorResult)
            .where(
                RecordedMonitorResult.monitor == monitor,
                (RecordedMonitorResult.calculated_at < calculated_at)
                | (
                    (RecordedMonitorResult.calculated_at == calculated_at)
                    & (RecordedMonitorResult.id < recorded_result_id)
                ),
            )
            .order_by(RecordedMonitorResult.calculated_at.desc(), RecordedMonitorResult.id.desc())
            .limit(1)
        ).scalar_one_or_none()

    def get_previous_recorded_results(
        self, monitor: str, results: list[RecordedMonitorResult]
    ) -> dict[int, RecordedMonitorResult]:
        """`get_previous_recorded_result` for a whole page, without one
        query per row.

        Because the page is already in the canonical total order, each
        entry's predecessor is simply the next entry -- except for the
        last one, whose predecessor lies outside the page and needs the
        single-row query. So a page of N costs one extra query, not N.
        """
        if not results:
            return {}
        previous_by_id = {results[index].id: results[index + 1] for index in range(len(results) - 1)}
        last = results[-1]
        beyond_page = self.get_previous_recorded_result(monitor, last.calculated_at, last.id)
        if beyond_page is not None:
            previous_by_id[last.id] = beyond_page
        return previous_by_id

    # -----------------------------------------------------------------
    # Surrounding evidence
    # -----------------------------------------------------------------

    def list_observation_updates_for_run(self, release_check_run_id: int) -> list[ReleaseObservationUpdate]:
        """Source-data changes recorded against one check run, newest
        detection first -- the same ordering `#19B`'s own read
        repository uses for these rows."""
        return list(
            self._session.execute(
                select(ReleaseObservationUpdate)
                .where(ReleaseObservationUpdate.release_check_run_id == release_check_run_id)
                .order_by(ReleaseObservationUpdate.detected_at.desc(), ReleaseObservationUpdate.id.desc())
            )
            .scalars()
            .all()
        )

    def list_current_observations(self, series_id: str) -> list[Observation]:
        """One series' CURRENT canonical values -- the "today" side of
        the comparison.

        Reads `economic_observations`, which #31 deliberately left as
        the current-value cache (ADR-030). Ordered ascending because
        that is the shape both methodologies' own index builders
        expect.
        """
        rows = self._session.execute(
            select(EconomicObservation.observation_date, EconomicObservation.value)
            .join(EconomicSeries, EconomicSeries.id == EconomicObservation.economic_series_id)
            .where(EconomicSeries.series_id == series_id)
            .order_by(EconomicObservation.observation_date.asc())
        ).all()
        return [Observation(date=observation_date, value=value) for observation_date, value in rows]
