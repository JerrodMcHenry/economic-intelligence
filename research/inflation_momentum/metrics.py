"""Objective behavioral metrics for one candidate methodology's state
series. Definitions are fixed here, in one place, and applied
identically to every candidate/variant/series -- never redefined or
tuned per candidate (Section 9 of the research brief: "Do not
manipulate definitions between candidates").

A "state series" is a chronologically-sorted list of `str | None`
values, one per date, where `None` means "insufficient history to
classify" (never treated as a state of its own, never imputed).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean, median


@dataclass
class RunLength:
    state: str
    length: int
    start_index: int


@dataclass
class StateSeriesMetrics:
    total_months: int
    classified_months: int
    unclassified_months: int
    pct_unclassified: float
    state_counts: dict[str, int]
    state_percentages: dict[str, float]
    num_state_changes: int
    state_change_rate: float  # changes / classified_months (classified transitions only)
    median_state_duration: float | None
    mean_state_duration: float | None
    num_one_month_reversals: int
    num_two_month_reversals: int
    num_cooling_heating_cooling_whipsaws: int
    num_heating_cooling_heating_whipsaws: int
    longest_run_by_state: dict[str, int]


def _runs(states: list[str | None]) -> list[RunLength]:
    """Contiguous runs of the same non-None state. A None breaks a run
    without itself starting one (it is not a state)."""
    runs: list[RunLength] = []
    current_state: str | None = None
    current_length = 0
    current_start = 0
    for i, s in enumerate(states):
        if s is None:
            if current_state is not None:
                runs.append(RunLength(current_state, current_length, current_start))
            current_state = None
            current_length = 0
            continue
        if s == current_state:
            current_length += 1
        else:
            if current_state is not None:
                runs.append(RunLength(current_state, current_length, current_start))
            current_state = s
            current_length = 1
            current_start = i
    if current_state is not None:
        runs.append(RunLength(current_state, current_length, current_start))
    return runs


def compute_state_series_metrics(states: list[str | None]) -> StateSeriesMetrics:
    total = len(states)
    classified = [s for s in states if s is not None]
    n_classified = len(classified)
    n_unclassified = total - n_classified

    state_counts: dict[str, int] = {}
    for s in classified:
        state_counts[s] = state_counts.get(s, 0) + 1
    state_percentages = {k: (v / n_classified * 100 if n_classified else 0.0) for k, v in state_counts.items()}

    # Month-to-month changes: only counted between two CONSECUTIVE
    # classified months (a None in between breaks contemporaneity, so
    # it's not counted as "no change" nor as "a change").
    num_changes = 0
    consecutive_classified_pairs = 0
    for i in range(1, total):
        if states[i] is None or states[i - 1] is None:
            continue
        consecutive_classified_pairs += 1
        if states[i] != states[i - 1]:
            num_changes += 1
    state_change_rate = num_changes / consecutive_classified_pairs if consecutive_classified_pairs else 0.0

    runs = _runs(states)
    durations = [r.length for r in runs]
    median_duration = median(durations) if durations else None
    mean_duration = mean(durations) if durations else None

    longest_run_by_state: dict[str, int] = {}
    for r in runs:
        longest_run_by_state[r.state] = max(longest_run_by_state.get(r.state, 0), r.length)

    # Reversals: a run of length <= N sandwiched between two runs of a
    # DIFFERENT, shared state on both sides (e.g. X, Y, X where Y is the
    # short reversal) is not required here -- a "one-month reversal" is
    # simply a run of exactly 1 month; a "two-month reversal" a run of
    # exactly 2 months. Defined on ALL runs, not just COOLING/HEATING,
    # since MIXED/STABLE/etc. can just as validly reverse briefly.
    num_one_month_reversals = sum(1 for r in runs if r.length == 1)
    num_two_month_reversals = sum(1 for r in runs if r.length == 2)

    # Whipsaws: three consecutive runs A, B, A where A is COOLING/HEATING
    # (the two states this is meaningful for) and B is anything else.
    num_cooling_heating_cooling = 0
    num_heating_cooling_heating = 0
    for i in range(len(runs) - 2):
        a, b, c = runs[i], runs[i + 1], runs[i + 2]
        if a.state == "COOLING" and c.state == "COOLING" and b.state == "HEATING":
            num_cooling_heating_cooling += 1
        if a.state == "HEATING" and c.state == "HEATING" and b.state == "COOLING":
            num_heating_cooling_heating += 1

    return StateSeriesMetrics(
        total_months=total,
        classified_months=n_classified,
        unclassified_months=n_unclassified,
        pct_unclassified=(n_unclassified / total * 100 if total else 0.0),
        state_counts=state_counts,
        state_percentages=state_percentages,
        num_state_changes=num_changes,
        state_change_rate=state_change_rate,
        median_state_duration=median_duration,
        mean_state_duration=mean_duration,
        num_one_month_reversals=num_one_month_reversals,
        num_two_month_reversals=num_two_month_reversals,
        num_cooling_heating_cooling_whipsaws=num_cooling_heating_cooling,
        num_heating_cooling_heating_whipsaws=num_heating_cooling_heating,
        longest_run_by_state=longest_run_by_state,
    )


@dataclass
class AgreementMetrics:
    compared_months: int
    same_state_pct: float
    opposite_state_pct: float
    other_pct: float  # neither same nor strictly opposite (e.g. one COOLING, one MIXED/STABLE)


def compute_agreement(
    states_a: list[str | None],
    states_b: list[str | None],
    opposite_pairs: set[tuple[str, str]],
) -> AgreementMetrics:
    """Agreement between two equal-length, date-aligned state series.
    `opposite_pairs` defines exactly which (state_a, state_b) pairs
    count as "opposite" (e.g. {("COOLING","HEATING"), ("HEATING","COOLING")})
    -- narrow by design, per the brief: COOLING vs STABLE is never
    "opposite", only ever "other"."""
    assert len(states_a) == len(states_b)
    compared = [(a, b) for a, b in zip(states_a, states_b) if a is not None and b is not None]
    n = len(compared)
    if n == 0:
        return AgreementMetrics(0, 0.0, 0.0, 0.0)
    same = sum(1 for a, b in compared if a == b)
    opposite = sum(1 for a, b in compared if (a, b) in opposite_pairs)
    other = n - same - opposite
    return AgreementMetrics(
        compared_months=n,
        same_state_pct=same / n * 100,
        opposite_state_pct=opposite / n * 100,
        other_pct=other / n * 100,
    )


@dataclass
class DirectionalMetrics:
    """Separates "all-state churn" (any consecutive classified state
    change, including a move into/out of a neutral state like STABLE or
    MIXED) from "direct reversals" (a flip STRAIGHT from one directional
    state to the other, e.g. COOLING -> HEATING with no neutral month in
    between) -- added for the finalist analysis to investigate the
    first study's non-monotonic churn finding (Section 7 of that
    brief): a wider neutral band can increase all-state churn via more
    neutral-state transitions even while it decreases direct reversals,
    and conflating the two would hide that mechanism."""

    consecutive_classified_pairs: int
    num_direct_reversals: int
    direct_reversal_rate: float  # same denominator as all-state churn, for direct side-by-side comparison
    num_directional_to_neutral_transitions: int
    directional_to_neutral_rate: float


def compute_directional_metrics(
    states: list[str | None],
    directional_states: tuple[str, str] = ("COOLING", "HEATING"),
) -> DirectionalMetrics:
    """`directional_states` names the two states treated as "a
    direction" (COOLING/HEATING in every candidate in this study); every
    other non-None state (STABLE, MIXED, MIXED_OR_STABLE,
    INSUFFICIENT_DATA, ...) is "neutral" for this metric's purposes.
    `None` is excluded from consideration entirely, exactly as
    `compute_state_series_metrics` already does for its own churn rate,
    so the two rates share a denominator and are directly comparable."""
    consecutive_pairs = 0
    direct_reversals = 0
    to_neutral_transitions = 0
    for i in range(1, len(states)):
        a, b = states[i - 1], states[i]
        if a is None or b is None:
            continue
        consecutive_pairs += 1
        a_directional = a in directional_states
        b_directional = b in directional_states
        if a_directional and b_directional and a != b:
            direct_reversals += 1
        elif a_directional != b_directional:
            to_neutral_transitions += 1
    return DirectionalMetrics(
        consecutive_classified_pairs=consecutive_pairs,
        num_direct_reversals=direct_reversals,
        direct_reversal_rate=(direct_reversals / consecutive_pairs if consecutive_pairs else 0.0),
        num_directional_to_neutral_transitions=to_neutral_transitions,
        directional_to_neutral_rate=(to_neutral_transitions / consecutive_pairs if consecutive_pairs else 0.0),
    )
