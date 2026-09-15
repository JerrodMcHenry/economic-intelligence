"""Pure, deterministic categorization for Increment #25G's Since Last
Visit V1 read model -- see docs/product/since-last-visit-v1.md (#25F),
specifically §18-21/§64-70. Mirrors `app.domain.state_duration`'s own
precedent (that module's own docstring, `state-duration-v1.md` §29):
pure sequence/membership logic over already-canonical values, zero
economic content, zero I/O -- imports no other domain module, no
SQLAlchemy, no AI.

This module NEVER classifies an economic state, NEVER recomputes a
monitor result, and NEVER decides what "matters" beyond deterministic
tier-membership tests already frozen by `overview-attention-model-v1.md`
§6/§7 and restated here in Python -- never imported cross-language from
the frontend's own `lib/inflationSalience.ts`/`laborSalience.ts` (see
contract §19: "two independent, already-correct restatements, never
one shared abstraction across a language boundary").

Every function here takes already-fetched, already-typed rows (never a
`Session`, never an ORM model) and returns an already-categorized,
already-aggregated result -- the repository/service layer is
responsible for turning real ORM rows into these small input shapes
and for supplying the one piece of state genuinely external to any
single window (`earliest_recorded_result_id`, §21's own system-wide
existence check).
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal

Monitor = Literal["inflation", "labor"]
Coverage = Literal["CHECKED", "GAP", "UNKNOWN"]
RecalculationKind = Literal["FIRST_CALCULATION", "UNCHANGED_CONFIRMATION"]

# Contract §19/§20 -- the identical Tier-1 ("primary domain state")
# predicate `overview-attention-model-v1.md` §6/§7 already froze for
# Inflation's/Labor's own top-level salience tier, restated once here.
# Never a second, competing definition -- PRESENTATION PRIORITY only.
_INFLATION_TIER1_COMPONENT = "PRIMARY_MOMENTUM"
_INFLATION_TIER1_FIELD = "state"
_LABOR_TIER1_COMPONENT = "LABOR"
_TIER1_EVENT_TYPES = frozenset({"STATE_CHANGED", "AVAILABILITY_LOST", "AVAILABILITY_RESTORED"})

# The disjoint component vocabularies each monitor's own `ReleaseAnalysisUpdate`
# rows use -- `app.models.inflation_what_changed.ChangeComponent` /
# `app.models.labor_what_changed.LaborChangeComponent`, restated here
# (never imported: those are frontend-facing Literal types, and this
# module intentionally has no dependency on either monitor's own API
# models -- a plain-string membership test is the smallest correct
# restatement).
INFLATION_COMPONENTS = frozenset({"PRIMARY_MOMENTUM", "CONFIRMATION", "TARGET", "HEADLINE_PCE", "HEADLINE_CPI"})
LABOR_COMPONENTS = frozenset({"LABOR", "EMPLOYMENT", "UNEMPLOYMENT"})

DEFAULT_MAX_LOOKBACK_DAYS = 90


# ---------------------------------------------------------------------
# Input shapes -- small, flat, built by the repository/service layer
# from real ORM rows. Never an ORM model itself (mirrors the existing
# `Observation`/`ObservationChangeRecord` in-memory-transport precedent).
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class AnalysisChangeInput:
    release_check_run_id: int
    component: str
    event_type: str
    field: str
    previous_value: str | None
    current_value: str | None
    evaluation_period: date
    methodology_id: str


@dataclass(frozen=True)
class RecordedResultInput:
    id: int
    release_check_run_id: int
    monitor: Monitor
    evaluation_period: date
    state: str
    methodology_id: str


@dataclass(frozen=True)
class ObservationChangeInput:
    release_check_run_id: int
    series_id: str
    series_title: str | None
    change_type: str  # "NEW" | "REVISED"


# ---------------------------------------------------------------------
# Output shapes
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class StructuralChangeItem:
    """Contract §18 Tier A / §20/§81. One genuine top-level state or
    availability transition, already selected as the "current" fact
    for its own `(release_check_run_id, monitor)` group (§68-70)."""

    release_check_run_id: int
    monitor: Monitor
    event_type: str
    field: str
    previous_value: str | None
    current_value: str | None
    evaluation_period: date
    methodology_id: str
    calculated_at: datetime


@dataclass(frozen=True)
class RecalculationItem:
    """Contract §18 Tier B / §21-23/§80. `kind` distinguishes
    §22's FIRST_CALCULATION (never "remains") from §23's aggregated
    UNCHANGED_CONFIRMATION (`count` >= 1, the number of genuine
    re-verifications this item summarizes)."""

    monitor: Monitor
    kind: RecalculationKind
    state: str
    evaluation_period: date
    count: int
    calculated_at: datetime
    methodology_id: str


@dataclass(frozen=True)
class SourceUpdateItem:
    """Contract §18 Tier C / §28-30/§82. Fires only for a
    `(release_check_run_id, monitor)` pair with zero genuine top-level
    recomputation (§28's own residual-case definition)."""

    monitor: Monitor
    series_id: str
    series_title: str | None
    change_type: str  # "NEW" | "REVISED"
    release_check_run_id: int


@dataclass(frozen=True)
class DomainRecap:
    monitor: Monitor
    coverage: Coverage
    last_checked_at: datetime | None
    structural_changes: list[StructuralChangeItem]
    recalculations: list[RecalculationItem]
    source_updates: list[SourceUpdateItem]


# ---------------------------------------------------------------------
# Window resolution -- contract §50-51/§54, pure (no clock read here;
# `through`/`requested_after` are both supplied by the caller, which
# resolved the real server clock exactly once, §10-13).
# ---------------------------------------------------------------------


def resolve_window(
    requested_after: datetime | None,
    through: datetime,
    max_lookback_days: int = DEFAULT_MAX_LOOKBACK_DAYS,
) -> tuple[datetime, bool, bool]:
    """Returns `(effective_after, first_visit, lookback_clamped)`.
    `effective_after` is ALWAYS a real, usable query boundary --
    never `None` -- a genuine first visit is bounded to the SAME
    default lookback window as any other visit (contract §7/§49/§50:
    "the same tiers and the same default lookback window... never an
    unbounded historical dump"). The caller (the service layer) is
    responsible for reporting `None` in the RESPONSE's own `after`
    field specifically when `first_visit` is true (§55) -- that is a
    presentation decision, distinct from this function's own query
    boundary, which must never be unbounded.

    Contract §7/§54: a missing, malformed, or future `requested_after`
    (the caller has already normalized "malformed" to `None` before
    calling this -- see the service layer) is treated as a genuine
    first visit, never an error. Contract §50-51: a real, past
    `requested_after` older than `max_lookback_days` is clamped to
    `through - max_lookback_days`, with `lookback_clamped=True` so the
    response can disclose this honestly (§86) -- never silently
    presented as if it covered the full, true gap.
    """
    floor = through - timedelta(days=max_lookback_days)
    if requested_after is None or requested_after >= through:
        # A missing checkpoint, or one that is nonsensically in the
        # future relative to the server's own current watermark
        # (clock skew, a corrupted local value) -- both are genuine
        # first-visit conditions per §7/§54, never a fabricated window.
        return floor, True, False
    if requested_after < floor:
        return floor, False, True
    return requested_after, False, False


# ---------------------------------------------------------------------
# Categorization -- contract §18-21/§64-70
# ---------------------------------------------------------------------


def _monitor_for_component(component: str) -> Monitor | None:
    if component in INFLATION_COMPONENTS:
        return "inflation"
    if component in LABOR_COMPONENTS:
        return "labor"
    return None


def _monitor_for_series(series_id: str, inflation_series_ids: frozenset[str], labor_series_ids: frozenset[str]) -> Monitor | None:
    if series_id in inflation_series_ids:
        return "inflation"
    if series_id in labor_series_ids:
        return "labor"
    return None


def _is_tier1(component: str, field_name: str) -> bool:
    if component == _INFLATION_TIER1_COMPONENT and field_name == _INFLATION_TIER1_FIELD:
        return True
    if component == _LABOR_TIER1_COMPONENT:
        return True
    return False


def select_structural_changes(
    analysis_changes: list[AnalysisChangeInput], calculated_at_by_run: dict[int, datetime]
) -> list[StructuralChangeItem]:
    """Contract §20/§68-70: Tier-1-shaped rows only, grouped by
    `(release_check_run_id, monitor)` -- within each group, the row
    with the maximum `evaluation_period` represents that group's own
    "current" fact (§68-70); any other row in the same group (an
    older, propagated-period revision from the same run -- the exact
    scenario #25E's own test suite discovered empirically) is deferred
    (§71), never surfaced."""
    groups: dict[tuple[int, Monitor], list[AnalysisChangeInput]] = {}
    for change in analysis_changes:
        if not (_is_tier1(change.component, change.field) and change.event_type in _TIER1_EVENT_TYPES):
            continue
        monitor = _monitor_for_component(change.component)
        if monitor is None:
            continue
        groups.setdefault((change.release_check_run_id, monitor), []).append(change)

    items: list[StructuralChangeItem] = []
    for (run_id, monitor), changes in groups.items():
        current = max(changes, key=lambda c: (c.evaluation_period, c.field))
        items.append(
            StructuralChangeItem(
                release_check_run_id=run_id,
                monitor=monitor,
                event_type=current.event_type,
                field=current.field,
                previous_value=current.previous_value,
                current_value=current.current_value,
                evaluation_period=current.evaluation_period,
                methodology_id=current.methodology_id,
                calculated_at=calculated_at_by_run[run_id],
            )
        )
    items.sort(key=lambda item: (item.calculated_at, item.release_check_run_id))
    return items


def select_recalculations(
    recorded_results: list[RecordedResultInput],
    calculated_at_by_run: dict[int, datetime],
    changed_run_monitor_pairs: frozenset[tuple[int, Monitor]],
    earliest_recorded_result_id: dict[Monitor, int],
) -> list[RecalculationItem]:
    """Contract §21's exact three-branch algorithm, applied per
    `(release_check_run_id, monitor)` group (current-result selection
    per §68-70 applies here identically to `select_structural_changes`):

    1. A group already present in `changed_run_monitor_pairs` (a
       genuine Tier-A structural change exists for that exact run and
       monitor) is NOT a separate unchanged-confirmation -- skipped
       entirely, no double-reporting (§21 branch 1).
    2. A group whose selected (max-period) row's own `id` equals that
       monitor's system-wide earliest ever `RecordedMonitorResult` id
       is FIRST_CALCULATION (§21 branch 2/§22) -- never aggregated,
       since this can occur for a given monitor at most once, ever.
    3. Every other group is UNCHANGED_CONFIRMATION (§21 branch 3),
       aggregated to at most one item per monitor (§23): `count` is
       the number of qualifying groups; the displayed `state`/
       `evaluation_period`/`calculated_at` come from the
       chronologically most recent one.
    """
    groups: dict[tuple[int, Monitor], list[RecordedResultInput]] = {}
    for row in recorded_results:
        groups.setdefault((row.release_check_run_id, row.monitor), []).append(row)

    first_calculation_by_monitor: dict[Monitor, RecalculationItem] = {}
    unchanged_candidates: dict[Monitor, list[RecordedResultInput]] = {}

    for (run_id, monitor), rows in groups.items():
        if (run_id, monitor) in changed_run_monitor_pairs:
            continue
        current = max(rows, key=lambda r: (r.evaluation_period, r.id))
        if current.id == earliest_recorded_result_id.get(monitor):
            first_calculation_by_monitor[monitor] = RecalculationItem(
                monitor=monitor,
                kind="FIRST_CALCULATION",
                state=current.state,
                evaluation_period=current.evaluation_period,
                count=1,
                calculated_at=calculated_at_by_run[run_id],
                methodology_id=current.methodology_id,
            )
        else:
            unchanged_candidates.setdefault(monitor, []).append(current)

    items: list[RecalculationItem] = list(first_calculation_by_monitor.values())
    for monitor, candidates in unchanged_candidates.items():
        latest = max(candidates, key=lambda r: calculated_at_by_run[r.release_check_run_id])
        items.append(
            RecalculationItem(
                monitor=monitor,
                kind="UNCHANGED_CONFIRMATION",
                state=latest.state,
                evaluation_period=latest.evaluation_period,
                count=len(candidates),
                calculated_at=calculated_at_by_run[latest.release_check_run_id],
                methodology_id=latest.methodology_id,
            )
        )
    items.sort(key=lambda item: (item.monitor, item.kind))
    return items


def select_source_updates(
    observation_changes: list[ObservationChangeInput],
    recomputed_run_monitor_pairs: frozenset[tuple[int, Monitor]],
    inflation_series_ids: frozenset[str],
    labor_series_ids: frozenset[str],
) -> list[SourceUpdateItem]:
    """Contract §28-30: fires only for a `(release_check_run_id,
    monitor)` pair with ZERO genuine top-level recomputation --
    `recomputed_run_monitor_pairs` is the caller-supplied set of every
    pair that has at least one `RecordedMonitorResult` row (the
    already-broader superset structural changes are always drawn from,
    §28's own residual-case reasoning). Deduplicated to one item per
    distinct `(series_id, change_type)` pair within a run."""
    seen: set[tuple[int, str, str]] = set()
    items: list[SourceUpdateItem] = []
    for change in observation_changes:
        monitor = _monitor_for_series(change.series_id, inflation_series_ids, labor_series_ids)
        if monitor is None:
            continue
        if (change.release_check_run_id, monitor) in recomputed_run_monitor_pairs:
            continue
        key = (change.release_check_run_id, change.series_id, change.change_type)
        if key in seen:
            continue
        seen.add(key)
        items.append(
            SourceUpdateItem(
                monitor=monitor,
                series_id=change.series_id,
                series_title=change.series_title,
                change_type=change.change_type,
                release_check_run_id=change.release_check_run_id,
            )
        )
    items.sort(key=lambda item: (item.monitor, item.series_id, item.release_check_run_id))
    return items


def compute_coverage(relevant_release_ids: frozenset[int], settled_release_ids_in_window: frozenset[int], any_sweep_in_window: bool) -> Coverage:
    """Contract §40-41's exact three-value model. `CHECKED` never
    requires sweep evidence (§47) -- it is checked first, purely from
    settlement. `GAP` vs. `UNKNOWN` is decided only for the remaining
    case, using `MaintenanceSweep` evidence exclusively (§42), never
    from the mere existence of automation code."""
    if relevant_release_ids <= settled_release_ids_in_window:
        return "CHECKED"
    if any_sweep_in_window:
        return "GAP"
    return "UNKNOWN"
