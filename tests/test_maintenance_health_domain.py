"""Pure unit tests for Increment #26E's maintenance-health
classification (`app.domain.maintenance_health`). No database, no
clock read -- every `now` is explicit, matching this project's own
established discipline for every other `_at`-suffixed domain function.
"""

from datetime import datetime, timedelta, timezone

from app.domain.maintenance_health import (
    MaintenanceHealthStatus,
    SweepSnapshot,
    classify_maintenance_health,
)

NOW = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)
STALE_THRESHOLD = timedelta(hours=3)
UNFINISHED_GRACE = timedelta(minutes=30)


def _classify(latest, latest_finished, now=NOW, stale_threshold=STALE_THRESHOLD, unfinished_grace=UNFINISHED_GRACE):
    return classify_maintenance_health(latest, latest_finished, now, stale_threshold, unfinished_grace)


class TestNeverRun:
    def test_no_sweeps_at_all_is_never_run(self):
        result = _classify(None, None)
        assert result.status is MaintenanceHealthStatus.NEVER_RUN
        assert result.latest_sweep is None
        assert result.latest_finished_sweep is None

    def test_first_sweep_still_in_progress_with_no_completed_evidence_is_never_run(self):
        in_progress = SweepSnapshot(started_at=NOW - timedelta(minutes=1), finished_at=None, failed_count=None)
        result = _classify(in_progress, None)
        assert result.status is MaintenanceHealthStatus.NEVER_RUN


class TestHealthy:
    def test_recent_finished_sweep_with_zero_failures_is_healthy(self):
        sweep = SweepSnapshot(started_at=NOW - timedelta(minutes=5), finished_at=NOW - timedelta(minutes=4), failed_count=0)
        result = _classify(sweep, sweep)
        assert result.status is MaintenanceHealthStatus.HEALTHY

    def test_recent_finished_sweep_with_zero_due_work_is_still_healthy(self):
        """A successful no-work sweep is still successful worker
        execution (#26E source prompt §25/§14) -- due_count/
        processed_count play no role in this module's own
        classification at all, only failed_count."""
        sweep = SweepSnapshot(started_at=NOW - timedelta(minutes=5), finished_at=NOW - timedelta(minutes=4), failed_count=0)
        result = _classify(sweep, sweep)
        assert result.status is MaintenanceHealthStatus.HEALTHY


class TestDegraded:
    def test_recent_finished_sweep_with_failures_is_degraded_not_stale_or_unfinished(self):
        sweep = SweepSnapshot(started_at=NOW - timedelta(minutes=5), finished_at=NOW - timedelta(minutes=4), failed_count=2)
        result = _classify(sweep, sweep)
        assert result.status is MaintenanceHealthStatus.DEGRADED


class TestStale:
    def test_latest_finished_sweep_older_than_threshold_is_stale(self):
        sweep = SweepSnapshot(started_at=NOW - timedelta(hours=4), finished_at=NOW - timedelta(hours=4), failed_count=0)
        result = _classify(sweep, sweep)
        assert result.status is MaintenanceHealthStatus.STALE

    def test_staleness_is_measured_from_started_at_not_finished_at(self):
        # started 4 hours ago (beyond the 3h threshold) but finished
        # only 1 hour ago (an unusually long-running sweep, used here
        # purely to distinguish the two possible measurement bases) --
        # still STALE, because staleness answers "has the worker
        # attempted a new sweep recently," which `started_at` answers
        # directly; `finished_at` alone (1h ago, within threshold)
        # would incorrectly say "fine."
        sweep = SweepSnapshot(started_at=NOW - timedelta(hours=4), finished_at=NOW - timedelta(hours=1), failed_count=0)
        result = _classify(sweep, sweep)
        assert result.status is MaintenanceHealthStatus.STALE

    def test_exactly_at_threshold_boundary_is_not_yet_stale(self):
        sweep = SweepSnapshot(started_at=NOW - STALE_THRESHOLD, finished_at=NOW - STALE_THRESHOLD, failed_count=0)
        result = _classify(sweep, sweep)
        assert result.status is not MaintenanceHealthStatus.STALE


class TestUnfinished:
    def test_old_unfinished_sweep_beyond_grace_period_is_unfinished(self):
        crashed = SweepSnapshot(started_at=NOW - timedelta(hours=1), finished_at=None, failed_count=None)
        result = _classify(crashed, None)
        assert result.status is MaintenanceHealthStatus.UNFINISHED

    def test_recent_in_progress_sweep_within_grace_period_is_not_prematurely_unfinished(self):
        """#26E source prompt §54: a very recent unfinished sweep may
        simply be running -- must not be classified as crashed."""
        in_progress = SweepSnapshot(started_at=NOW - timedelta(minutes=2), finished_at=None, failed_count=None)
        last_good = SweepSnapshot(started_at=NOW - timedelta(hours=1), finished_at=NOW - timedelta(hours=1), failed_count=0)
        result = _classify(in_progress, last_good)
        assert result.status is not MaintenanceHealthStatus.UNFINISHED
        assert result.status is MaintenanceHealthStatus.HEALTHY  # judged from the last good sweep instead

    def test_in_progress_sweep_falls_back_to_stale_last_good_sweep(self):
        in_progress = SweepSnapshot(started_at=NOW - timedelta(minutes=2), finished_at=None, failed_count=None)
        stale_good = SweepSnapshot(started_at=NOW - timedelta(hours=5), finished_at=NOW - timedelta(hours=5), failed_count=0)
        result = _classify(in_progress, stale_good)
        assert result.status is MaintenanceHealthStatus.STALE

    def test_unfinished_takes_priority_over_a_still_valid_earlier_finished_sweep(self):
        crashed = SweepSnapshot(started_at=NOW - timedelta(hours=1), finished_at=None, failed_count=None)
        earlier_good = SweepSnapshot(started_at=NOW - timedelta(hours=2), finished_at=NOW - timedelta(hours=2), failed_count=0)
        result = _classify(crashed, earlier_good)
        assert result.status is MaintenanceHealthStatus.UNFINISHED

    def test_exactly_at_grace_period_boundary_is_not_yet_unfinished(self):
        boundary = SweepSnapshot(started_at=NOW - UNFINISHED_GRACE, finished_at=None, failed_count=None)
        result = _classify(boundary, None)
        assert result.status is not MaintenanceHealthStatus.UNFINISHED


class TestLatestAttemptVsLatestSuccess:
    def test_both_are_exposed_even_when_they_differ(self):
        crashed = SweepSnapshot(started_at=NOW - timedelta(hours=1), finished_at=None, failed_count=None)
        earlier_good = SweepSnapshot(started_at=NOW - timedelta(hours=3), finished_at=NOW - timedelta(hours=3), failed_count=0)
        result = _classify(crashed, earlier_good)
        assert result.latest_sweep == crashed
        assert result.latest_finished_sweep == earlier_good
