"""Pure, deterministic Labor-specific release-processing dependency
propagation for Increment #20D.2 -- frozen and normative in
`docs/architecture/labor-release-integration-v1.md`.

Mirrors `app.domain.release_processing`'s own role exactly, scoped to
Labor only: given a set of changed (NEW/REVISED) PAYEMS/UNRATE
observation dates, which `labor_v1.0` evaluation periods could that
change affect? It owns ONLY this dependency-propagation question. Like
every other module in `app/domain/`, this file has no knowledge of
FastAPI, HTTP, FRED, SQLAlchemy, database sessions, environment
variables, or logging, and never mutates global state.

This module contains **zero** `labor_v1.0`/`labor_what_changed_v1.0`
economic logic of its own: no PAYEMS/UNRATE calculation, no condition/
momentum classification, no `EmploymentState`/`LaborState` agreement
table, no What Changed comparison. It does not import
`app.domain.release_processing` (Inflation's own, structurally separate
propagation module -- kept independent for the same reason every other
domain module in this package is independent of every other one, see
`tests/test_domain_architectural_independence.py`), and it does not
import `app.domain.labor`/`app.domain.labor_what_changed` either --
the one calendar-arithmetic helper this module needs (adding N months
to a normalized, day-1 monthly date) is small enough to restate here,
self-contained, exactly mirroring `app.domain.release_processing._add_months`'s
own precedent rather than creating a new cross-domain-module import.

Labor's own affected-period shape is genuinely simpler than Inflation's:
PAYEMS and UNRATE co-own `LaborState` through a single
`compute_labor_monitor_result_at(period)` call that evaluates
`LABOR`+`EMPLOYMENT`+`UNEMPLOYMENT` together, so there is no
per-component dimension the way Inflation's `PRIMARY_MOMENTUM`/`TARGET`/
`CONFIRMATION`/... components (each its own separate domain call)
require. The affected set here is therefore `frozenset[date]` (periods
only) -- never `set[(component, date)]` pairs.
"""

from datetime import date

# The two Labor canonical series -- restated as plain literals here
# These are STORED SERIES identifiers -- the keys the release pipeline
# reports changed observations under -- not MacroChipz's identity for
# the concepts (#38, ADR-034). They are imported from app.models.labor,
# where they are derived from the active provider binding.
#
# Increment #38 changed this. They were previously restated here as
# literals, with a comment conceding they were "kept in sync with
# app.models.labor... by convention" -- a duplication with nothing
# keeping it true, and exactly the leak ADR-034's Invariant A forbids.
# The independence that comment was protecting is worth less than not
# having two sources of truth for the same identifier.
from app.models.labor import PAYEMS_SERIES_ID, UNRATE_SERIES_ID

LABOR_SERIES_IDS: frozenset[str] = frozenset({PAYEMS_SERIES_ID, UNRATE_SERIES_ID})

# The frozen, empirically re-verified `labor_v1.0` affected-horizon
# offsets (docs/architecture/labor-release-integration-v1.md §9/§10).
# PAYEMS is SPARSE (not 0..6) -- a level revision at r shifts
# monthly_change(r) by +delta and monthly_change(r+1) by -delta
# (opposite signs); any 3-month average containing BOTH cancels
# exactly, so offsets 1 and 2 show NO change, not merely "less change."
# Never replace this with a contiguous range.
PAYEMS_AFFECTED_HORIZONS_MONTHS: tuple[int, ...] = (0, 3, 6)

# UNRATE has two DISJOINT clusters -- no cancellation (UNRATE averages
# the rate directly, unlike PAYEMS's differenced series):
# current_3m_avg(t) depends on t-2..t (offsets 0,1,2 from a changed r);
# prior_year_3m_avg(t) depends on t-14..t-12 (offsets 12,13,14).
UNRATE_AFFECTED_HORIZONS_MONTHS: tuple[int, ...] = (0, 1, 2, 12, 13, 14)


def _add_months(period: date, months: int) -> date:
    """`period` shifted forward by exactly `months` calendar months --
    restated independently here rather than imported (see this
    module's own docstring for why), identical in behavior to
    `app.domain.release_processing._add_months`. Assumes `period` is
    already normalized to day 1, exactly as every date this module
    receives already is (FRED's own monthly convention, enforced
    upstream)."""
    total_months = period.year * 12 + (period.month - 1) + months
    year, month0 = divmod(total_months, 12)
    return date(year, month0 + 1, 1)


def payems_affected_evaluation_periods(changed_dates: frozenset[date]) -> frozenset[date]:
    """Every `labor_v1.0` `EmploymentResult`/`LaborMonitorResult`
    evaluation period whose evidence could differ because of the given
    changed (NEW/REVISED) PAYEMS observation dates.

    For each changed date `r`, that is exactly `r + 0`, `r + 3`, and
    `r + 6` months -- the frozen sparse set, never a contiguous `r..r+6`
    range, and never a backward-looking offset. Unlike
    `app.domain.release_processing.affected_evaluation_periods`, this
    function does NOT filter candidates against an
    "already has an observation there" set -- `labor_v1.0`'s own
    `compute_employment_result` already reports `INSUFFICIENT_DATA` for
    a period with no computable evidence rather than requiring the
    caller to pre-filter, so every candidate offset is returned
    unconditionally; the caller (the service layer) is responsible for
    deciding what to do with a period that turns out to have no
    evidence either side of the comparison.

    Union-based: several changed dates that share an affected period
    contribute it only once (the return value is a `frozenset`)."""
    affected: set[date] = set()
    for changed_date in changed_dates:
        for horizon in PAYEMS_AFFECTED_HORIZONS_MONTHS:
            affected.add(_add_months(changed_date, horizon))
    return frozenset(affected)


def unrate_affected_evaluation_periods(changed_dates: frozenset[date]) -> frozenset[date]:
    """Every `labor_v1.0` `UnemploymentResult`/`LaborMonitorResult`
    evaluation period whose evidence could differ because of the given
    changed (NEW/REVISED) UNRATE observation dates.

    For each changed date `r`, that is `r + 0`, `r + 1`, `r + 2`
    (`current_3m_avg`'s own window) AND `r + 12`, `r + 13`, `r + 14`
    (`prior_year_3m_avg`'s own window) -- two disjoint clusters, never
    merged into one contiguous range."""
    affected: set[date] = set()
    for changed_date in changed_dates:
        for horizon in UNRATE_AFFECTED_HORIZONS_MONTHS:
            affected.add(_add_months(changed_date, horizon))
    return frozenset(affected)


def labor_affected_evaluation_periods(
    payems_changed_dates: frozenset[date], unrate_changed_dates: frozenset[date]
) -> frozenset[date]:
    """The complete, deduplicated set of `labor_v1.0` evaluation
    periods release processing must recompute for one check run --
    the UNION of PAYEMS's own affected periods and UNRATE's own
    affected periods (PAYEMS and UNRATE co-own `LaborState`, so either
    series' change can move the shared result).

    Deliberately `frozenset[date]` -- periods only, no component
    dimension -- unlike Inflation's own `set[(component, period)]`
    pairs (see this module's own docstring for why: Labor has no
    per-component evaluation split). The caller sorts this into
    deterministic chronological order before iterating (this function
    itself makes no ordering guarantee, matching
    `affected_evaluation_periods`'s own identical convention)."""
    return payems_affected_evaluation_periods(payems_changed_dates) | unrate_affected_evaluation_periods(unrate_changed_dates)
