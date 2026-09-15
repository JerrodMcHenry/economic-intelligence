"""Application/use-case orchestration for Increment #26E's maintenance
worker health check -- the durable heartbeat this project's own
`MaintenanceSweep` table already provides, made operator-queryable for
the first time. Frozen contract:
docs/product/production-reliability-deployment-v1.md (#26B) §26/§54.

Read-only, always: this service issues no write of any kind, calls no
external provider, and performs no economic calculation. It knows
exactly two things -- schema compatibility (reused, unmodified, from
Increment #26C) and `MaintenanceSweep` evidence (via the existing,
unmodified `MaintenanceRepository`) -- and delegates the actual
classification to the pure `app.domain.maintenance_health` module,
never re-implementing that logic here.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.core.schema_compatibility import SchemaCompatibilityResult, SchemaCompatibilityStatus, check_schema_compatibility
from app.db.session import session_scope
from app.domain.maintenance_health import (
    MaintenanceHealthResult,
    SweepSnapshot,
    classify_maintenance_health,
)
from app.repositories.maintenance_repository import MaintenanceRepository

# Frozen (docs/product/production-reliability-deployment-v1.md §26,
# restated per #26E source prompt §20): a tunable operational
# parameter, derived from -- not empirically measured against --
# `automated-economic-maintenance-v1.md` §15's own frozen "hourly-order
# to a-few-times-daily" sweep cadence. Three times the shortest
# expected interval (hourly) gives real tolerance for scheduler jitter,
# a slow provider round-trip, or a single missed firing, without
# masking a scheduler that has genuinely stopped for an extended
# period. Matches this project's own repeated "principle frozen,
# exact number left tunable, never pretended to be empirically
# precise" discipline (e.g. the retry window, the sweep cadence
# itself).
DEFAULT_STALE_THRESHOLD = timedelta(hours=3)

# Frozen (#26E source prompt §10/§54): how long a sweep may run before
# an unfinished row is treated as crashed/hung rather than "plausibly
# still in progress." `automated-economic-maintenance-v1.md` §49's own
# volume estimate ("almost always zero-to-a-few" FRED calls per sweep)
# implies ordinary sweeps complete in well under a minute; 30 minutes
# is a deliberately generous operational tolerance for provider
# latency or a larger-than-usual due-work set, not an economic fact.
DEFAULT_UNFINISHED_GRACE_PERIOD = timedelta(minutes=30)


@dataclass(frozen=True)
class MaintenanceHealthCheckResult:
    """The complete result this service returns -- schema
    compatibility is checked FIRST and reported distinctly; sweep
    history is only interpreted once the schema is confirmed
    compatible (#26E source prompt §21: "if schema incompatible,
    report that before interpreting sweep history")."""

    schema_compatibility: SchemaCompatibilityResult
    health: MaintenanceHealthResult | None  # None whenever schema_compatibility is not COMPATIBLE


def check_maintenance_health(
    now: datetime | None = None,
    stale_threshold: timedelta = DEFAULT_STALE_THRESHOLD,
    unfinished_grace_period: timedelta = DEFAULT_UNFINISHED_GRACE_PERIOD,
) -> MaintenanceHealthCheckResult:
    """`now` defaults to the real UTC wall clock, resolved exactly
    once, here -- never read a second time anywhere downstream
    (mirrors `automated-economic-maintenance-v1.md` §57's own frozen
    clock discipline). Tests inject an explicit `now` instead
    (#26E source prompt §60)."""
    resolved_now = now if now is not None else datetime.now(timezone.utc)

    compatibility = check_schema_compatibility()
    if compatibility.status is not SchemaCompatibilityStatus.COMPATIBLE:
        return MaintenanceHealthCheckResult(schema_compatibility=compatibility, health=None)

    with session_scope() as session:
        repo = MaintenanceRepository(session)
        latest = repo.get_latest_sweep()
        latest_finished = repo.get_latest_finished_sweep()

    health = classify_maintenance_health(
        latest_sweep=_snapshot(latest),
        latest_finished_sweep=_snapshot(latest_finished),
        now=resolved_now,
        stale_threshold=stale_threshold,
        unfinished_grace_period=unfinished_grace_period,
    )
    return MaintenanceHealthCheckResult(schema_compatibility=compatibility, health=health)


def _snapshot(sweep) -> SweepSnapshot | None:
    if sweep is None:
        return None
    return SweepSnapshot(started_at=sweep.started_at, finished_at=sweep.finished_at, failed_count=sweep.failed_count)
