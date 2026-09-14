"""Pure, deterministic domain logic for Increment #18's release-driven
update pipeline. Like every other module in `app/domain/`, this file
has no knowledge of FastAPI, HTTP, FRED, SQLAlchemy, database sessions,
environment variables, or logging, and never mutates global state (see
`tests/test_domain_architectural_independence.py`, which this module is
registered against).

This module contains **zero** Inflation classification/annualization
logic of its own -- it does not reimplement `classify_period`, the
neutral-band comparison, or any formula from `app/domain/inflation.py`,
and (like `app/domain/inflation_what_changed.py`) deliberately does not
import that module either, keeping every domain module in this package
independent of every other one -- the one calendar-arithmetic helper
this module needs (adding N months to a normalized, day-1 monthly
date) is small enough to state once here, self-contained, rather than
creating the first cross-domain-module import in this package. It
otherwise only answers two release-processing-specific questions pure
calendar/equality logic can answer on its own:

1. Given a persisted value and a provider value, what changed?
   (`classify_observation_change`)
2. Given a set of changed observation dates, which Inflation
   evaluation periods could that change affect, and which canonical
   series feed which `inflation_what_changed_v1.0` component?
   (`affected_evaluation_periods`, `components_for_series`)

Everything else -- fetching, persisting, and actually calling
`app.domain.inflation`'s comparison primitives -- belongs to
`app.services.release_processing` (I/O orchestration) and
`app.repositories.release_processing_repository` (persistence), never
here.
"""

from datetime import date
from typing import Literal

from app.models.inflation import (
    CONFIRMATION_SERIES_ID,
    HEADLINE_CPI_SERIES_ID,
    PRIMARY_SERIES_ID,
    TARGET_SERIES_ID,
)
from app.models.inflation_what_changed import ChangeComponent

ObservationChangeType = Literal["NEW", "REVISED", "UNCHANGED"]

# The exact horizons inflation_v1.0 itself defines (contextual 1M plus
# canonical 3M/6M/12M), plus 0 for "the changed date's own period" --
# reused, not reinvented, from docs/methodology/inflation-monitor-v1.0.md's
# "Required observations" table. A changed observation at date D can
# only ever be a required calendar-endpoint for a *later* period at
# exactly these offsets, because inflation_v1.0 defines no other
# horizon.
_AFFECTED_HORIZONS_MONTHS: tuple[int, ...] = (0, 1, 3, 6, 12)

# Mirrors app/services/inflation.py's own, already-existing wiring of
# which canonical series feeds which `inflation_what_changed_v1.0`
# component -- verified directly against that file's
# InflationMonitorService.get_what_changed_result, not invented here.
# PCEPILFE also feeds CONFIRMATION (which is defined over PCEPILFE +
# CPILFESL together) even though it is not the "confirmation series"
# itself. This mapping answers only "which section could this series'
# change affect" -- it carries no notion of economic importance and is
# not read by anything outside this pipeline.
SERIES_TO_COMPONENTS: dict[str, frozenset[ChangeComponent]] = {
    PRIMARY_SERIES_ID: frozenset({"PRIMARY_MOMENTUM", "CONFIRMATION"}),
    CONFIRMATION_SERIES_ID: frozenset({"CONFIRMATION"}),
    TARGET_SERIES_ID: frozenset({"TARGET", "HEADLINE_PCE"}),
    HEADLINE_CPI_SERIES_ID: frozenset({"HEADLINE_CPI"}),
}


def _add_months(period: date, months: int) -> date:
    """`period` shifted forward by exactly `months` calendar months --
    the forward-direction twin of `app.domain.inflation.month_before`
    (which only ever shifts backward), restated here rather than
    imported (see this module's own docstring for why). Assumes `period`
    is already normalized to day 1, exactly as every date this module
    receives already is (FRED's own monthly convention, enforced
    upstream)."""
    total_months = period.year * 12 + (period.month - 1) + months
    year, month0 = divmod(total_months, 12)
    return date(year, month0 + 1, 1)


def components_for_series(series_id: str) -> frozenset[ChangeComponent]:
    """Which `inflation_what_changed_v1.0` components a canonical
    series' change could affect. Empty for any series not among the
    four canonical Inflation inputs (e.g. a future curated series with
    no deterministic consumer yet) -- release processing simply
    computes no analytical consequence for it, never an error."""
    return SERIES_TO_COMPONENTS.get(series_id, frozenset())


def classify_observation_change(
    existed_before: bool,
    previous_value: float | None,
    new_value: float | None,
) -> ObservationChangeType:
    """Deterministic NEW/REVISED/UNCHANGED classification.

    `existed_before=False` is always NEW, regardless of `previous_value`
    (which the caller should pass as `None` in that case -- there is
    nothing to compare against). Otherwise: plain equality on
    already-normalized values -- both `previous_value` and `new_value`
    reach this function having passed through the same deterministic
    provider string -> float parse (`app.services.economic_data._parse_value`)
    used everywhere else in this codebase, so there is no float-vs-float
    rounding-drift risk to guard against with a tolerance (the two
    values were never independently *calculated*, only *parsed*, from
    what is in both cases the same kind of string). `None` participates
    in plain equality exactly as Python defines it: `None == None` is
    `True` (UNCHANGED), `None == 5.0` is `False` (REVISED) -- a
    transition into or out of "missing" is always a REVISED event,
    never silently dropped.
    """
    if not existed_before:
        return "NEW"
    if previous_value == new_value:
        return "UNCHANGED"
    return "REVISED"


def five_year_observation_start(as_of_date: date) -> date:
    """The start of #18's rolling five-year detection horizon: exactly
    five calendar years before `as_of_date`, computed by exact calendar
    arithmetic (`date.replace`), never `365 * 5` days -- a leap day
    five years earlier may not exist (e.g. `2024-02-29` minus 5 calendar
    years has no `2019-02-29`), in which case this falls back to
    `2019-02-28`, the same "nearest valid calendar date" behavior
    `date.replace` documents raising `ValueError` for and this function
    resolves explicitly rather than letting propagate.

    This is a bounded, *ordinary* release-detection window -- newly
    published observations, ordinary recent revisions, and major
    recent seasonal/benchmark revisions. It is deliberately NOT a
    guarantee that every historical revision in a provider's entire
    history is detected by every release check; broad historical
    reconciliation across a provider's full history is an explicitly
    deferred, different future capability (see
    docs/architecture/release-processing-v1.md).
    """
    try:
        return as_of_date.replace(year=as_of_date.year - 5)
    except ValueError:
        # as_of_date is a leap day (Feb 29) and year-5 is not a leap year.
        return as_of_date.replace(year=as_of_date.year - 5, day=28)


def affected_evaluation_periods(
    changed_dates: frozenset[date],
    observation_dates_after: frozenset[date],
) -> frozenset[date]:
    """Every Inflation calculation period whose evidence could differ
    because of the given changed (NEW/REVISED) observation dates.

    For each changed date `D`, that is `D` itself (its own period,
    always affected -- a value that is itself `P_t` for period `D`
    obviously affects `D`'s own evaluation) plus, for each horizon `k`
    in `_AFFECTED_HORIZONS_MONTHS` greater than zero, `D + k` months --
    but only when an observation already exists at that later date
    (`observation_dates_after`), since inflation_v1.0 can only ever
    evaluate a period that has its own `P_t` in the first place. This
    is exact calendar-month arithmetic (`_add_months`), never an
    approximation and never a guess about *when* a later period's data
    will exist -- it only asks whether one already does, in
    already-persisted data.

    This is how #18 correctly handles a batch of several changed dates
    that all feed the SAME later evaluation period (e.g. three
    endpoint revisions that are each some existing period's own
    t-3/t-6/t-12) without evaluating that shared later period more than
    once -- the return value is a set.
    """
    affected: set[date] = set()
    for changed_date in changed_dates:
        affected.add(changed_date)
        for horizon in _AFFECTED_HORIZONS_MONTHS:
            if horizon == 0:
                continue
            candidate = _add_months(changed_date, horizon)
            if candidate in observation_dates_after:
                affected.add(candidate)
    return frozenset(affected)
