"""Application/use-case logic for Increment #19B's public
release-processing read model.

Deliberately a NEW class, NOT a reuse of `ReleaseProcessingService`
(#18's write orchestrator) -- the same "structurally incapable, not
just conventionally disciplined" reasoning
`app.services.releases.ReleaseReadService`'s own docstring gives for
being separate from `ReleaseSyncService`. `ReleaseProcessingReadService`
has no `FREDClient`-shaped parameter anywhere on it for a future edit
to accidentally wire one into, and imports nothing from
`app.clients.fred`.

The central guarantee this service exists to provide: **retry-history
preservation**. `latest_check.status` reflects only the occurrence's
most recently completed `ReleaseCheckRun` (deterministic
`completed_at DESC, id DESC` tie-break), but
`detected_observation_changes`/`detected_analysis_changes` are the
UNION of every such row across EVERY run the occurrence has ever had --
a later `NO_CHANGE` (or `CHECK_FAILED`) run's own absence of new rows
never erases an earlier run's detected evidence from the response.
This is the reason #19B exists at all: a naive "read the latest run's
own rows" projection would silently discard exactly the evidence a
retry-history read model is supposed to preserve.

No domain math: mapping the internal 4-value `CheckRunStatus` to the
public 5-value `ProcessingStatus` (`_STATUS_MAP` below) is a pure,
static presentation relabeling -- a dict lookup, never a recomputation
of any economic value, threshold, or classification.
"""

from collections import defaultdict
from datetime import date

from sqlalchemy.orm import Session

from app.db.models import ReleaseAnalysisUpdate, ReleaseCheckRun, ReleaseObservationUpdate
from app.models.release_processing import CheckRunStatus
from app.models.release_processing_read import (
    DetectedAnalysisChange,
    DetectedObservationChange,
    LatestCheck,
    ProcessingStatus,
    ReleaseContext,
    ReleaseProcessingStatusItem,
    ReleaseProcessingStatusResponse,
)
from app.models.releases import PaginationMeta
from app.repositories.release_processing_read_repository import ReleaseProcessingReadRepository

_STATUS_MAP: dict[CheckRunStatus, ProcessingStatus] = {
    "NO_CHANGE": "NO_CHANGE",
    "CHANGED": "CHANGES_DETECTED",
    "PARTIAL_FAILURE": "PARTIAL_CHECK",
    "FAILED_PROVIDER": "CHECK_FAILED",
}


class InvalidDateRangeError(Exception):
    """Raised when start_date is after end_date."""


class ReleaseProcessingReadService:
    """Database-only, always. No method on this class accepts or
    constructs a `FREDClient`."""

    def get_processing_status(
        self,
        session: Session,
        occurrence_id: int | None,
        release_id: int | None,
        status: ProcessingStatus | None,
        start_date: date | None,
        end_date: date | None,
        limit: int,
        offset: int,
    ) -> ReleaseProcessingStatusResponse:
        if start_date is not None and end_date is not None and start_date > end_date:
            raise InvalidDateRangeError("start_date must not be after end_date.")

        repo = ReleaseProcessingReadRepository(session)
        candidates = repo.list_mapped_occurrences(
            occurrence_id=occurrence_id, release_id=release_id, start_date=start_date, end_date=end_date
        )
        occurrence_ids = [occurrence.id for occurrence, _release in candidates]

        # Every run for every candidate occurrence, already ordered
        # `completed_at DESC, id DESC` by the repository -- so the
        # first run encountered per occurrence, below, is that
        # occurrence's latest.
        all_runs = repo.list_check_runs_for_occurrences(occurrence_ids)
        runs_by_occurrence: dict[int, list[ReleaseCheckRun]] = defaultdict(list)
        for run in all_runs:
            runs_by_occurrence[run.release_occurrence_id].append(run)

        # Derive each candidate's public status + latest run (None if
        # never checked) before any pagination -- status filtering
        # depends on this and must see the whole candidate set.
        derived: list[tuple[object, object, ProcessingStatus, ReleaseCheckRun | None]] = []
        for occurrence, release in candidates:
            occurrence_runs = runs_by_occurrence.get(occurrence.id, [])
            latest_run = occurrence_runs[0] if occurrence_runs else None
            public_status: ProcessingStatus = "NOT_CHECKED" if latest_run is None else _STATUS_MAP[latest_run.status]
            derived.append((occurrence, release, public_status, latest_run))

        if status is not None:
            derived = [entry for entry in derived if entry[2] == status]

        total = len(derived)
        page = derived[offset : offset + limit]

        # Bounded, page-scoped fetch of history: every run belonging to
        # an occurrence that made it onto this page (all of them, not
        # just each occurrence's latest -- see this module's docstring).
        page_run_ids: list[int] = []
        for occurrence, _release, _status, _latest_run in page:
            page_run_ids.extend(run.id for run in runs_by_occurrence.get(occurrence.id, []))

        run_to_occurrence_id = {run.id: run.release_occurrence_id for run in all_runs}

        observation_updates = repo.list_observation_updates_for_runs(page_run_ids)
        analysis_updates = repo.list_analysis_updates_for_runs(page_run_ids)

        observations_by_occurrence: dict[int, list[ReleaseObservationUpdate]] = defaultdict(list)
        for update in observation_updates:
            observations_by_occurrence[run_to_occurrence_id[update.release_check_run_id]].append(update)

        analyses_by_occurrence: dict[int, list[ReleaseAnalysisUpdate]] = defaultdict(list)
        for update in analysis_updates:
            analyses_by_occurrence[run_to_occurrence_id[update.release_check_run_id]].append(update)

        series_metadata = repo.list_series_metadata(sorted({update.series_id for update in observation_updates}))

        items = [
            ReleaseProcessingStatusItem(
                occurrence_id=occurrence.id,
                release=ReleaseContext(
                    release_id=release.id,
                    name=release.name,
                    provider=release.provider,
                    provider_release_id=release.provider_release_id,
                ),
                scheduled_date=occurrence.scheduled_date,
                latest_check=LatestCheck(
                    status=public_status,
                    checked_at=latest_run.completed_at if latest_run is not None else None,
                ),
                detected_observation_changes=[
                    DetectedObservationChange(
                        series_id=update.series_id,
                        series_title=series_metadata[update.series_id].title if update.series_id in series_metadata else None,
                        units=series_metadata[update.series_id].units if update.series_id in series_metadata else None,
                        change_type=update.change_type,
                        observation_date=update.observation_date,
                        previous_value=update.previous_value,
                        new_value=update.new_value,
                        detected_at=update.detected_at,
                    )
                    for update in observations_by_occurrence.get(occurrence.id, [])
                ],
                detected_analysis_changes=[
                    DetectedAnalysisChange(
                        component=update.component,
                        event_type=update.event_type,
                        field=update.field,
                        previous_value=update.previous_value,
                        current_value=update.current_value,
                        delta=update.delta,
                        evaluation_period=update.evaluation_period,
                        methodology_id=update.methodology_id,
                        data_basis=update.data_basis,
                        recorded_at=update.created_at,
                    )
                    for update in analyses_by_occurrence.get(occurrence.id, [])
                ],
            )
            for occurrence, release, public_status, latest_run in page
        ]

        return ReleaseProcessingStatusResponse(
            occurrences=items,
            pagination=PaginationMeta(limit=limit, offset=offset, returned=len(items), total=total),
        )
