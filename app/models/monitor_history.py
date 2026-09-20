"""The public, read-only response contract for
`GET /api/v1/monitors/{monitor}/history` and
`.../history/{recorded_result_id}` (Increment #32).

Plain Pydantic, no FastAPI and no SQLAlchemy -- the same discipline every
other module here follows.

This contract exists to make Increment #31's temporal foundation
*usable* without making the user learn temporal databases. Three
distinctions are load-bearing, and each is expressed in the types rather
than left to the frontend:

1. **What MacroChipz knew THEN vs. what today's revised data says.**
   These are different questions with different answers, and conflating
   them would be the single most misleading thing this feature could do.
   `RecordedIntelligenceEntry.state` is history: what MacroChipz actually
   concluded and durably wrote. `CurrentComparison.current_state` is a
   reconstruction computed at request time from today's dataset. The
   second is never presented as something MacroChipz "knew".

2. **Observed vs. reconstructed provenance.** `inputs_include_backfilled`
   rides on every replay summary. A replay over migration-time backfill
   rests on "this value existed by this timestamp", not on a write this
   system watched happen -- materially weaker evidence, and never hidden.
   See `docs/product/recorded-state-history-v1.md` §23, whose boundary
   #31 moved but did not erase.

3. **Correlation vs. causation.** `RelatedDataChange` rows are changes
   recorded against the *same* `ReleaseCheckRun` as the result -- a real
   persisted link, not temporal proximity. That still does not prove one
   caused the other, so every field name here is descriptive
   (`related_changes`), never causal. ADR-023's "no causal nesting"
   applies unchanged.

No field in this module is computed by the frontend. Economic meaning --
whether values differ, whether a state changed, whether a comparison is
even valid -- is decided here, server-side, and rendered verbatim.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.models.releases import PaginationMeta
from app.models.replay import NotReplayableReason, ReplayOutcome

#: The monitors that durably record their own results. Deliberately the
#: same two-value vocabulary `app/models/release_processing.py` already
#: froze -- Rates has observation versioning (#31) but records no monitor
#: state, so it is absent here rather than represented by empty history.
HistoryMonitor = Literal["inflation", "labor"]

#: How one observation the methodology used compares between the
#: historical reconstruction and today's dataset.
#:
#: `ONLY_AVAILABLE_TODAY` is the honest name for an observation the
#: methodology needs that had no value then and has one now -- the
#: common shape of a late-arriving or first-published data point. Its
#: mirror, `ONLY_AVAILABLE_THEN`, would mean a value was withdrawn.
InputComparison = Literal["UNCHANGED", "REVISED", "ONLY_AVAILABLE_TODAY", "ONLY_AVAILABLE_THEN"]

#: The unit a `HistoricalInput` value carries.
#:
#: Supplied by the backend because these are the METHODOLOGY's canonical
#: units, which are not always the provider's: `labor_v1.0` reports
#: PAYEMS evidence as actual jobs (158,268,000) while FRED publishes
#: thousands. A frontend inferring the unit from a series id would be
#: re-deriving a methodology decision; naming it here keeps that
#: decision server-side and leaves the frontend with pure formatting.
InputUnit = Literal["INDEX", "JOBS", "PERCENT"]

#: Whether a then-vs-today comparison could be made at all.
#:
#: `NOT_COMPARABLE` is a real outcome, not a failure to try: comparing
#: across methodology versions, or against a replay that never ran,
#: would produce a confident number with no meaning.
ComparisonStatus = Literal["IDENTICAL_INPUTS", "INPUTS_CHANGED", "NOT_COMPARABLE"]

#: Why no comparison was attempted.
NotComparableReason = Literal["REPLAY_UNAVAILABLE", "METHODOLOGY_VERSION_DIFFERS"]


class ReplaySummary(BaseModel):
    """Increment #31's `ReplayResult`, narrowed to what a reader needs.

    `outcome` is reported verbatim -- in particular a `MISMATCH` is
    surfaced, never smoothed into "unverified". A recorded conclusion
    that no longer reproduces from its own inputs is an integrity
    finding, and the product's job is to show it.
    """

    outcome: ReplayOutcome
    #: The independently recomputed state. `None` when replay could not
    #: run -- never the recorded state echoed back, which would make a
    #: failed replay look like a successful one.
    replayed_state: str | None
    reason: NotReplayableReason | None
    #: True when ANY input came from #31's migration backfill.
    inputs_include_backfilled: bool


class PreviousRecordedResult(BaseModel):
    """The recorded result immediately preceding this one in the same
    total order the history list uses (`calculated_at` desc, then `id`
    desc).

    `same_evaluation_period` disambiguates the two genuinely different
    things a state change can mean, which a bare "MIXED -> COOLING"
    arrow would blur: a *new month* classified differently
    (`False`), versus MacroChipz reaching a *different conclusion about
    the same month* (`True`). Only the second is a revised opinion.
    """

    recorded_result_id: int
    state: str
    evaluation_period: date
    calculated_at: datetime
    same_evaluation_period: bool
    state_changed: bool


class RecordedIntelligenceEntry(BaseModel):
    """One durably recorded monitor conclusion, plus whether it still
    reproduces. The list row and the detail view's header are the same
    shape, so the two can never drift apart."""

    recorded_result_id: int
    monitor: HistoryMonitor
    #: What MacroChipz concluded at the time. Never recomputed.
    state: str
    evaluation_period: date
    #: When the computation ran -- structurally independent of
    #: `evaluation_period` (recorded-state-history-v1.md §14).
    calculated_at: datetime
    methodology_id: str
    data_basis: str
    replay: ReplaySummary
    previous: PreviousRecordedResult | None


class HistoricalInput(BaseModel):
    """One observation the methodology actually consumed, as it stood
    then and as it stands now.

    The set of rows is not a window this module chose. It is read off
    the methodology's own evidence -- `InflationMetricEvidence`'s exact
    calendar endpoints, `LaborObservationEvidence`'s required months --
    so it is exactly what the calculation used, including months that
    were missing (`value_then = None`).
    """

    series_id: str
    observation_date: date
    #: Both values are in the methodology's own canonical unit (see
    #: `value_unit`), never the raw persisted figure -- so `value_then`
    #: and `value_today` are always directly comparable.
    value_then: float | None
    value_today: float | None
    value_unit: InputUnit
    comparison: InputComparison
    #: Whether the THEN value came from #31's backfill rather than an
    #: observed write. Per-input, not merely per-result, so a reader can
    #: see precisely which numbers carry the weaker claim.
    is_backfilled: bool


class CurrentComparison(BaseModel):
    """What today's revised dataset says about the SAME evaluation
    period, under the SAME methodology.

    "Today" means the current canonical dataset available to MacroChipz
    at request time -- never the calendar date, and never a claim about
    what was known at any other moment.
    """

    status: ComparisonStatus
    reason: NotComparableReason | None
    #: The methodology re-run at the recorded evaluation period against
    #: current observations. A RECONSTRUCTION, not history.
    current_state: str | None
    #: Whether that reconstruction differs from what was recorded. `None`
    #: when no comparison was possible -- never defaulted to `False`,
    #: which would read as "nothing changed".
    state_differs: bool | None
    methodology_id_then: str
    methodology_id_today: str
    #: When true, any difference above may reflect changed data, changed
    #: methodology, or both -- and must never be attributed to data
    #: alone.
    methodology_differs: bool
    changed_input_count: int


class RelatedDataChange(BaseModel):
    """A source-data change recorded against the same `ReleaseCheckRun`
    as this result.

    Deliberately named for what the evidence supports. The shared check
    run is a real persisted link, so these are not merely contemporaneous
    -- but the database records no causal edge between a change and a
    computation, and this contract asserts none (ADR-023).
    """

    series_id: str
    observation_date: date
    #: `NEW` or `REVISED`, exactly as release processing classified it.
    change_type: str
    previous_value: float | None
    new_value: float | None
    detected_at: datetime


class MonitorHistoryResponse(BaseModel):
    monitor: HistoryMonitor
    entries: list[RecordedIntelligenceEntry]
    pagination: PaginationMeta


class MonitorHistoryDetail(BaseModel):
    """One recorded result, opened up.

    `related_changes` is restricted to changes touching observations
    this result's methodology actually used; `other_changes_in_same_run`
    counts the rest rather than dropping them silently, so a reader is
    never told a run was quieter than it was.
    """

    recorded: RecordedIntelligenceEntry
    historical_inputs: list[HistoricalInput]
    current_comparison: CurrentComparison
    related_changes: list[RelatedDataChange]
    other_changes_in_same_run: int
