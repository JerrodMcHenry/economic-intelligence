"""Pure, domain-agnostic sequence/counting logic behind State Duration V1
(frozen and normative in `docs/product/state-duration-v1.md`, §29).

This module has zero economic content: it never inspects what any
particular state label from either monitor's own vocabulary means --
it only compares state values to each other for equality and checks them
against the one domain-agnostic sentinel string "INSUFFICIENT_DATA",
which both `app.domain.inflation` and `app.domain.labor` already use
for the identical purpose. Like `app.domain.analysis`'s own
`align_series`/`pearson_correlation` (the direct precedent cited in the
frozen contract), this module serves every monitor generically because
it genuinely contains no monitor-specific knowledge -- not because a
shared abstraction was merely convenient.

No calendar arithmetic here either: exact-calendar stepping
(`month_before`) is each domain's own job (frozen contract §7 -- each
domain module re-derives it independently, never shared). This module
operates over an ALREADY-BUILT, already-ordered sequence the caller
constructs by calling its own monitor-specific `_at` function
repeatedly; it performs no I/O and knows nothing about series IDs,
methodology IDs, or FRED.
"""

from dataclasses import dataclass
from datetime import date
from typing import Literal

BoundaryType = Literal["EXACT", "DATA_BOUNDED", "LOOKBACK_BOUNDED"]

# The one sentinel string this module recognizes -- shared, by pure
# coincidence of spelling, with `InflationState`/`LaborState`'s own
# "INSUFFICIENT_DATA" literal, but this module never imports either of
# those types: it treats the string as an opaque marker, never as a
# member of a known enum.
INSUFFICIENT_DATA_SENTINEL = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class StateDurationPoint:
    """One reconstructed calendar month's own state, already computed by
    the caller's own monitor-specific `_at` function -- this module
    never computes `state` itself, only reads and compares it."""

    period: date
    state: str


@dataclass(frozen=True)
class StateDurationEvaluation:
    """The pure result of walking `sequence` -- see
    `evaluate_state_duration`'s own docstring for field meanings, which
    mirror `docs/product/state-duration-v1.md` §32 field-for-field
    (minus the fields only the caller can supply: `methodology_id`,
    `data_basis`, `history_type`, and the top-level `state`, which is
    just `sequence[0].state` echoed back by the caller)."""

    duration_months: int
    earliest_confirmed_period: date
    boundary_type: BoundaryType
    previous_state: str | None
    previous_period: date | None


def evaluate_state_duration(sequence: list[StateDurationPoint], lookback_bound_months: int) -> StateDurationEvaluation:
    """Count the consecutive run of matching states starting at
    `sequence[0]` (the current period `t`) and walking through
    `sequence[1:]` in order -- `sequence` must already be ordered
    most-recent-first (`sequence[i]` is exactly `i` calendar months
    before `sequence[0]`; frozen contract §45's own "ordering ...
    frozen and tested one way"). Exact-calendar stepping is entirely
    the CALLER's responsibility; this function does no date arithmetic
    of its own and trusts the sequence it is given.

    `sequence[0].state` must be a real, non-`INSUFFICIENT_DATA` value --
    callers must resolve the `CURRENT_INSUFFICIENT` case (frozen
    contract §14) themselves, before ever calling this function; that
    precondition is asserted here, not silently tolerated.

    Stopping rule (frozen contract §8/§9/§12), checked in this exact
    order at each subsequent point:
      1. A real, differing state -> `EXACT`, with that point's own
         state/period exposed verbatim as `previous_state`/
         `previous_period` (§8/§22).
      2. `INSUFFICIENT_DATA` -> `DATA_BOUNDED` (§9 -- deliberately
         unified with "ran off the edge of the persisted dataset"; both
         manifest as this identical sentinel from the caller's own `_at`
         function, so no separate case is needed here).
      3. Neither, and `lookback_bound_months` consecutive matching
         months (including `t` itself) have now been confirmed ->
         `LOOKBACK_BOUNDED` (§12).

    `duration_months` always counts `sequence[0]` as 1 (§20) and never
    includes the differing/insufficient boundary point itself.
    Historical insufficiency is never skipped past: encountering it
    stops the walk immediately, even if a later (older) point would
    have matched `sequence[0].state` again (§16).

    Deterministic: identical input always produces identical output.
    """
    if not sequence:
        raise ValueError("evaluate_state_duration requires at least one point (the current period, t)")

    current_state = sequence[0].state
    if current_state == INSUFFICIENT_DATA_SENTINEL:
        raise ValueError(
            "evaluate_state_duration requires sequence[0]'s state to be a real, non-INSUFFICIENT_DATA "
            "value -- callers must resolve CURRENT_INSUFFICIENT (state-duration-v1.md §14) before calling this function"
        )

    earliest_confirmed_period = sequence[0].period
    duration_months = 1

    for point in sequence[1:]:
        if duration_months >= lookback_bound_months:
            break
        if point.state == INSUFFICIENT_DATA_SENTINEL:
            return StateDurationEvaluation(
                duration_months=duration_months,
                earliest_confirmed_period=earliest_confirmed_period,
                boundary_type="DATA_BOUNDED",
                previous_state=None,
                previous_period=None,
            )
        if point.state != current_state:
            return StateDurationEvaluation(
                duration_months=duration_months,
                earliest_confirmed_period=earliest_confirmed_period,
                boundary_type="EXACT",
                previous_state=point.state,
                previous_period=point.period,
            )
        duration_months += 1
        earliest_confirmed_period = point.period

    return StateDurationEvaluation(
        duration_months=duration_months,
        earliest_confirmed_period=earliest_confirmed_period,
        boundary_type="LOOKBACK_BOUNDED",
        previous_state=None,
        previous_period=None,
    )
