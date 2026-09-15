"""Typed, application-owned result models for Increment #18's
release-driven update pipeline.

Plain Pydantic data, like `app.models.inflation`/`app.models.inflation_what_changed`
-- no FastAPI, no SQLAlchemy dependency. This is the shape the service
layer (`app.services.release_processing`) returns, the repository
(`app.repositories.release_processing_repository`) persists from, and
the operational CLI (`app.operations.process_release`) renders --
never a full `InflationMonitorResult` snapshot, and never arbitrary
JSON. `AnalysisChangeRecord` mirrors
`app.models.inflation_what_changed.ChangeEvent`'s own field set with
one deliberate adaptation (`evaluation_period` instead of
`previous_period`/`current_period` -- see that model's own docstring
and `app.db.models.ReleaseAnalysisUpdate`'s for why).
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.models.inflation import DATA_BASIS, METHODOLOGY_ID
from app.models.inflation_what_changed import ChangeEventType

ObservationChangeType = Literal["NEW", "REVISED"]
CheckRunStatus = Literal["NO_CHANGE", "CHANGED", "PARTIAL_FAILURE", "FAILED_PROVIDER"]

# Increment #25E: the two canonical monitors Recorded State History V1
# covers -- see docs/product/recorded-state-history-v1.md §20/§65.
# Deliberately narrow, never generalized to an arbitrary future
# subject list.
RecordedMonitor = Literal["inflation", "labor"]


class SeriesCheckOutcome(BaseModel):
    """One mapped series' outcome within a check run. `error` is always
    a safe, generic message (mirroring
    `app.services.releases._safe_sync_error_message`'s existing
    convention) -- never a raw provider response body."""

    series_id: str
    succeeded: bool
    error: str | None = None
    new_count: int = 0
    revised_count: int = 0
    unchanged_count: int = 0


class ObservationChangeRecord(BaseModel):
    """One detected NEW/REVISED observation -- the in-memory shape
    persisted as one `ReleaseObservationUpdate` row."""

    series_id: str
    observation_date: date
    change_type: ObservationChangeType
    previous_value: float | None
    new_value: float | None
    detected_at: datetime


class AnalysisChangeRecord(BaseModel):
    """One structured, typed analytical consequence -- the in-memory
    shape persisted as one `ReleaseAnalysisUpdate` row. Reuses the
    frozen `inflation_what_changed_v1.0`/`labor_what_changed_v1.0`
    event vocabularies verbatim (`component`/`event_type`/`field` from
    `app.models.inflation_what_changed.ChangeEvent`/
    `app.models.labor_what_changed.LaborChangeEvent`); never a new,
    parallel taxonomy.

    `component` is deliberately plain `str`, NOT `ChangeComponent`
    (Increment #20D.2) -- this release-processing record is generic
    transport/provenance metadata, not the owner of any analysis
    family's semantic vocabulary. Each comparator's own model
    (`ChangeComponent` for Inflation, `LaborChangeComponent` for Labor)
    remains strongly typed at its own layer; widening this one boundary
    field is what lets a `ReleaseAnalysisUpdate` row carry EITHER
    family's component values (`"PRIMARY_MOMENTUM"` or `"EMPLOYMENT"`,
    for example) without a union type that grows a new member every
    time a future third monitor is integrated. See
    docs/architecture/labor-release-integration-v1.md §17. `event_type`
    stays `ChangeEventType` -- Inflation's own vocabulary is already a
    strict superset of Labor's four-value vocabulary, so no widening is
    needed there."""

    component: str
    event_type: ChangeEventType
    field: str
    previous_value: float | str | None
    current_value: float | str | None
    delta: float | None
    evaluation_period: date
    methodology_id: str = METHODOLOGY_ID
    data_basis: str = DATA_BASIS


class RecordableMonitorResult(BaseModel):
    """Increment #25E: the in-memory shape of one genuinely-executed
    canonical monitor AFTER result, ready to persist as one
    `RecordedMonitorResult` row -- see
    docs/product/recorded-state-history-v1.md (the frozen #25D
    contract), specifically §5/§7/§40. Built ONLY from the existing,
    unmodified `_evaluate_component_at`("PRIMARY_MOMENTUM")/
    `_evaluate_labor_at` AFTER-evidence call each domain branch of
    `ReleaseProcessingService._apply_changes_and_compute_analysis`
    already makes for `ReleaseAnalysisUpdate`'s own purposes -- never
    a second, independent computation.

    Deliberately does NOT carry `calculated_at` -- that value is the
    owning `ReleaseCheckRun.completed_at`, not known until after this
    object is built (contract §15); it is passed as a separate
    argument to `ReleaseProcessingRepository.add_recorded_monitor_result`
    instead, once available."""

    monitor: RecordedMonitor
    evaluation_period: date
    state: str
    methodology_id: str
    data_basis: str


class ReleaseCheckRunResult(BaseModel):
    """The complete, structured outcome of one #18 release-processing
    run. Returned by `ReleaseProcessingService.process_occurrence`,
    persisted by `ReleaseProcessingRepository`, and rendered by the
    operational CLI. Deliberately NOT a full `InflationMonitorResult`
    snapshot -- only the structured evidence this contract requires."""

    release_occurrence_id: int
    status: CheckRunStatus
    started_at: datetime
    completed_at: datetime
    series_outcomes: list[SeriesCheckOutcome]
    observation_changes: list[ObservationChangeRecord]
    analysis_changes: list[AnalysisChangeRecord]
