"""Increment #25G's public, read-only response contract for
`GET /api/v1/since-last-visit` -- see docs/product/since-last-visit-v1.md
(the frozen #25F contract this module implements verbatim).

Plain Pydantic data, like `app.models.release_processing_read` -- no
SQLAlchemy dependency. Every field here is either copied verbatim from
a persisted row (`app.domain.since_last_visit`'s own already-categorized
output) or a small, honest metadata fact about the window itself
(`after`/`through`/`first_visit`/`lookback_clamped`). This module
defines no new persisted state and computes no economic value.

Discriminated by `kind`/`change_type`/`coverage` fields throughout
(never a bag of nullable fields the frontend must inspect to guess
semantics, per the source prompt's own §69 instruction) -- three
distinct item shapes (`StructuralChange`, `Recalculation`,
`SourceUpdate`), never one generic "event" shape.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

Monitor = Literal["inflation", "labor"]
Coverage = Literal["CHECKED", "GAP", "UNKNOWN"]
RecalculationKind = Literal["FIRST_CALCULATION", "UNCHANGED_CONFIRMATION"]


class StructuralChange(BaseModel):
    """Contract §18 Tier A / §20/§81. One genuine top-level state or
    availability transition for the monitor -- the `(release_check_run_id,
    monitor)` group's own "current" fact (§68-70); a propagated,
    older-period revision from the same run is never a second item."""

    monitor: Monitor
    event_type: str
    field: str
    previous_value: str | None
    current_value: str | None
    evaluation_period: date
    methodology_id: str
    calculated_at: datetime
    release_check_run_id: int


class Recalculation(BaseModel):
    """Contract §18 Tier B / §21-23/§80. `kind` distinguishes a
    genuine first-ever calculation (never "remains") from an
    aggregated, repeated unchanged confirmation (`count` >= 1)."""

    monitor: Monitor
    kind: RecalculationKind
    state: str
    evaluation_period: date
    count: int
    calculated_at: datetime
    methodology_id: str


class SourceUpdate(BaseModel):
    """Contract §18 Tier C / §28-30/§82. Fires only when source data
    changed without reaching a genuine top-level recomputation."""

    monitor: Monitor
    series_id: str
    series_title: str | None
    change_type: Literal["NEW", "REVISED"]
    release_check_run_id: int


class DomainRecap(BaseModel):
    """One monitor's own independent recap -- Inflation and Labor are
    always two separate instances of this model, never merged into a
    cross-domain structure (contract §33-34)."""

    monitor: Monitor
    coverage: Coverage
    last_checked_at: datetime | None
    structural_changes: list[StructuralChange]
    recalculations: list[Recalculation]
    source_updates: list[SourceUpdate]


class SinceLastVisitResponse(BaseModel):
    """`after`/`through` together describe the exact half-open window
    `(after, through]` this response covers (contract §10-13/§55) --
    `after` is the value actually used (post-clamping), never the raw
    client-supplied one. `first_visit` is true whenever no usable prior
    checkpoint was supplied (missing, malformed, or future -- contract
    §7/§54); `lookback_clamped` is true whenever a real, past
    checkpoint was older than the frozen lookback bound and was
    narrowed to it (contract §50-51) -- the two flags are mutually
    exclusive by construction and drive #25H's own distinct copy paths
    (§85 vs. §86)."""

    after: datetime | None
    through: datetime
    first_visit: bool
    lookback_clamped: bool
    inflation: DomainRecap
    labor: DomainRecap
