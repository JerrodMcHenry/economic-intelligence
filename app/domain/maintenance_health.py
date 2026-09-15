"""Pure classification logic for Increment #26E's maintenance-worker
heartbeat/health check. No SQLAlchemy, no I/O, no wall-clock read --
every `now` this module ever reasons about is an explicit parameter,
mirroring this project's own established discipline (every `_at`-
suffixed domain function already takes its reference point explicitly;
`automated-economic-maintenance-v1.md` §57's own "clock resolved once,
threaded explicitly" rule, restated here for a new, read-only
consumer).

Frozen contract: docs/product/production-reliability-deployment-v1.md
(#26B) §26/§54; `docs/product/automated-economic-maintenance-v1.md`
§30 ("WORKER HEALTH and ECONOMIC/DOMAIN FRESHNESS are two separate
concepts, never conflated") -- this module answers ONLY the first
question. It has no opinion about, and never reads, any economic data.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class MaintenanceHealthStatus(str, Enum):
    """Every distinguishable outcome of asking "is the maintenance
    worker healthy" from persisted `MaintenanceSweep` evidence alone.

    `NEVER_RUN` is EXPECTED, not a failure, before the scheduler is
    activated (#26E source prompt §22) -- callers that want to
    distinguish "not yet activated" from "activated and broken" should
    do so using this specific status value, not by inventing a
    separate signal.
    """

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    UNFINISHED = "UNFINISHED"
    NEVER_RUN = "NEVER_RUN"


@dataclass(frozen=True)
class SweepSnapshot:
    """The minimal facts about one persisted `MaintenanceSweep` row
    this module needs -- never the ORM row itself, keeping this module
    free of any SQLAlchemy dependency."""

    started_at: datetime
    finished_at: datetime | None
    failed_count: int | None


@dataclass(frozen=True)
class MaintenanceHealthResult:
    """`latest_sweep`/`latest_finished_sweep` are exposed alongside the
    single overall `status` (#26E source prompt §23: "latest attempt
    failed, latest successful run 3 hours ago" is operationally useful
    information a single enum value alone would discard)."""

    status: MaintenanceHealthStatus
    latest_sweep: SweepSnapshot | None
    latest_finished_sweep: SweepSnapshot | None


def classify_maintenance_health(
    latest_sweep: SweepSnapshot | None,
    latest_finished_sweep: SweepSnapshot | None,
    now: datetime,
    stale_threshold: timedelta,
    unfinished_grace_period: timedelta,
) -> MaintenanceHealthResult:
    """The one, shared classification rule.

    Deliberately does NOT treat "the very latest sweep hasn't finished
    yet" as automatically unhealthy (#26E source prompt §54: "a very
    recent unfinished sweep may simply be running... do not
    prematurely classify as crashed") -- only a latest sweep that has
    been running longer than `unfinished_grace_period` is classified
    `UNFINISHED`. Short of that, overall health is judged from the
    most recent sweep that has actually COMPLETED (`latest_finished_sweep`,
    or `latest_sweep` itself if it happens to already be the finished
    one) -- a genuinely in-progress sweep never masks or overrides
    still-valid, still-recent evidence from the one before it.

    `NEVER_RUN` covers both "zero sweeps ever" and "the very first
    sweep is still in progress, with no completed evidence yet" --
    both are honestly "no proof of successful automation exists yet,"
    the exact, correct pre-activation state (#26E source prompt §22).
    """
    if latest_sweep is None:
        return MaintenanceHealthResult(MaintenanceHealthStatus.NEVER_RUN, None, None)

    if latest_sweep.finished_at is None and (now - latest_sweep.started_at) > unfinished_grace_period:
        return MaintenanceHealthResult(MaintenanceHealthStatus.UNFINISHED, latest_sweep, latest_finished_sweep)

    reference = latest_sweep if latest_sweep.finished_at is not None else latest_finished_sweep
    if reference is None:
        return MaintenanceHealthResult(MaintenanceHealthStatus.NEVER_RUN, latest_sweep, latest_finished_sweep)

    if (now - reference.started_at) > stale_threshold:
        return MaintenanceHealthResult(MaintenanceHealthStatus.STALE, latest_sweep, latest_finished_sweep)

    if reference.failed_count is not None and reference.failed_count > 0:
        return MaintenanceHealthResult(MaintenanceHealthStatus.DEGRADED, latest_sweep, latest_finished_sweep)

    return MaintenanceHealthResult(MaintenanceHealthStatus.HEALTHY, latest_sweep, latest_finished_sweep)
