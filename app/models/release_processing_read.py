"""Increment #19B: the public, read-only response contract for
`GET /api/v1/releases/processing-status`.

Plain Pydantic data, like `app.models.release_processing` -- no
FastAPI, no SQLAlchemy dependency. This is a PROJECTION over #18's
already-persisted `ReleaseCheckRun`/`ReleaseObservationUpdate`/
`ReleaseAnalysisUpdate` rows (see `app.repositories.release_processing_read_repository`
and `app.services.release_processing_read`) -- it defines no new
persisted state and computes no economic value; every field here is
either copied verbatim from a persisted row or a pure presentation
relabeling (the 4-value internal `CheckRunStatus` -> the 5-value public
`ProcessingStatus`, see `app.services.release_processing_read._STATUS_MAP`).

Two frozen, non-negotiable shape decisions (see
docs/adr/023-release-processing-read-model-no-causal-nesting.md):

1. `detected_observation_changes` and `detected_analysis_changes` are
   SIBLING arrays on `ReleaseProcessingStatusItem`, never nested inside
   each other. Neither `ReleaseObservationUpdate` nor
   `ReleaseAnalysisUpdate` carries a persisted foreign key or causal
   link to the other (both only reference `release_check_run_id`) --
   manufacturing a wrapper object that nests one array inside the
   other here would assert a causal relationship the database does
   not actually record.
2. Exactly FIVE public statuses: `NOT_CHECKED`, `NO_CHANGE`,
   `CHANGES_DETECTED`, `PARTIAL_CHECK`, `CHECK_FAILED`. There is no
   sixth, catch-all status for an unmapped release -- an occurrence
   whose release has zero active `ReleaseSeriesMapping` rows is
   excluded from this resource entirely (filtered out at the
   repository layer), never assigned any status at all.

Both arrays reflect ALL historical runs for the occurrence, not just
the latest one -- the central reason #19B exists: a later `NO_CHANGE`
run must never erase an earlier run's detected changes from this read
model (see `ReleaseProcessingReadService`'s own docstring for the
retry-history-preservation guarantee this enforces).

`successful_series_count`/`failed_series_count` are deliberately
NOT part of this contract: `SeriesCheckOutcome` (the in-memory
per-series result) is never persisted anywhere -- `ReleaseCheckRun`
carries no per-series breakdown, and a series checked successfully
with zero changes leaves no row in `ReleaseObservationUpdate` either.
There is no way to reconstruct these counts from persisted data alone
without fabricating them, so V1 omits them rather than approximate
(see docs/ENGINEERING_JOURNAL.md's #19B entry for the full reasoning).
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.models.inflation_what_changed import ChangeComponent, ChangeEventType
from app.models.release_processing import ObservationChangeType
from app.models.releases import PaginationMeta

ProcessingStatus = Literal["NOT_CHECKED", "NO_CHANGE", "CHANGES_DETECTED", "PARTIAL_CHECK", "CHECK_FAILED"]


class LatestCheck(BaseModel):
    """The occurrence's most recently completed check run only --
    `completed_at DESC, id DESC` tie-broken (deterministic even when
    two runs somehow share a timestamp). `checked_at` is `None` only
    when `status == "NOT_CHECKED"` (no `ReleaseCheckRun` row exists for
    this occurrence at all -- absence is never conflated with a
    NO_CHANGE result)."""

    status: ProcessingStatus
    checked_at: datetime | None


class ReleaseContext(BaseModel):
    """The parent release's curated identity, inlined -- the same
    flat-not-nested choice `app.models.releases.ReleaseOccurrenceItem`
    already makes for the same reason (every consumer needs the
    release identity alongside the occurrence)."""

    release_id: int
    name: str
    provider: str
    provider_release_id: str


class DetectedObservationChange(BaseModel):
    """One persisted `ReleaseObservationUpdate` row, from ANY run ever
    recorded for the occurrence -- not just the latest. `series_title`/
    `units` are looked up from `EconomicSeries` by `series_id` at
    response time (a plain string column, not a foreign key -- see
    `app.db.models.ReleaseObservationUpdate`'s own docstring) and are
    `None`, never fabricated, if that lookup finds nothing."""

    series_id: str
    series_title: str | None
    units: str | None
    change_type: ObservationChangeType
    observation_date: date
    previous_value: float | None
    new_value: float | None
    detected_at: datetime


class DetectedAnalysisChange(BaseModel):
    """One persisted `ReleaseAnalysisUpdate` row, from ANY run ever
    recorded for the occurrence -- not just the latest.
    `previous_value`/`current_value` are exposed as-persisted (`str |
    None`, mirroring `ReleaseAnalysisUpdate`'s own nullable String
    column) rather than coerced to a number -- the field can legitimately
    hold a non-numeric state label (e.g. "COOLING"/"HEATING"), and `delta`
    already carries the numeric change when one exists. `recorded_at` is
    `ReleaseAnalysisUpdate.created_at` -- named differently from
    `DetectedObservationChange.detected_at` because `ReleaseAnalysisUpdate`
    has no `detected_at` column at all (see that model's docstring)."""

    component: ChangeComponent
    event_type: ChangeEventType
    field: str
    previous_value: str | None
    current_value: str | None
    delta: float | None
    evaluation_period: date
    methodology_id: str
    data_basis: str
    recorded_at: datetime


class ReleaseProcessingStatusItem(BaseModel):
    """One mapped release occurrence's processing status. `schedule_status`
    (SCHEDULED/PAST_DUE) is deliberately NOT included here -- that is
    `app.domain.releases.classify_schedule_status`'s concept, belongs to
    the release-calendar resource (`GET /releases`), and this resource
    has no need to re-derive it; a consumer that needs both can already
    look up an occurrence by `occurrence_id`."""

    occurrence_id: int
    release: ReleaseContext
    scheduled_date: date
    latest_check: LatestCheck
    detected_observation_changes: list[DetectedObservationChange]
    detected_analysis_changes: list[DetectedAnalysisChange]


class ReleaseProcessingStatusResponse(BaseModel):
    occurrences: list[ReleaseProcessingStatusItem]
    pagination: PaginationMeta
