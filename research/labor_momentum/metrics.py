"""Objective behavioral metrics for the Labor Momentum Methodology
Validation -- defined once, applied identically to every candidate
threshold pair. Deliberately contains no accuracy/precision/recall/F1/
ROC/AUC/recession-prediction score of any kind: there is no ground-
truth monthly label for "Labor is COOLING," so none is computed (see
the #20A.1 brief's own "DO NOT SCORE ACCURACY" section).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median

from research.labor_momentum.methodology import LaborMonthResult, LaborState


@dataclass(frozen=True)
class StateSeriesMetrics:
    n_months: int
    state_counts: dict[str, int]
    state_pct: dict[str, float]
    n_transitions: int
    durations_by_state: dict[str, list[int]]
    avg_duration_by_state: dict[str, float]
    median_duration_by_state: dict[str, float]
    one_month_reversals: int  # A -> B -> A, run length of B == 1
    reversal_examples: list[tuple[str, str, str]] = field(default_factory=list)  # (period, A, B) at the reversal midpoint


def _runs(states: list[str]) -> list[tuple[str, int]]:
    """Collapse a state sequence into (state, run_length) pairs, e.g.
    [A,A,B,A,A] -> [(A,2),(B,1),(A,2)]."""
    if not states:
        return []
    runs: list[tuple[str, int]] = []
    current_state = states[0]
    current_len = 1
    for s in states[1:]:
        if s == current_state:
            current_len += 1
        else:
            runs.append((current_state, current_len))
            current_state = s
            current_len = 1
    runs.append((current_state, current_len))
    return runs


def compute_state_series_metrics(results: list[LaborMonthResult]) -> StateSeriesMetrics:
    states = [r.state for r in results]
    n = len(states)

    counts: dict[str, int] = {}
    for s in states:
        counts[s] = counts.get(s, 0) + 1
    pct = {s: (c / n * 100 if n else 0.0) for s, c in counts.items()}

    runs = _runs(states)
    n_transitions = max(len(runs) - 1, 0)

    durations: dict[str, list[int]] = {}
    for state, length in runs:
        durations.setdefault(state, []).append(length)
    avg_duration = {s: sum(lengths) / len(lengths) for s, lengths in durations.items()}
    median_duration = {s: float(median(lengths)) for s, lengths in durations.items()}

    # One-month reversals: a run of length 1 strictly between two runs
    # of the SAME state on either side (A, B[len=1], A).
    reversals = 0
    examples: list[tuple[str, str, str]] = []
    period_offset = 0
    run_start_indices = []
    idx = 0
    for state, length in runs:
        run_start_indices.append(idx)
        idx += length
    for i in range(1, len(runs) - 1):
        prev_state, _ = runs[i - 1]
        this_state, this_len = runs[i]
        next_state, _ = runs[i + 1]
        if this_len == 1 and prev_state == next_state and prev_state != this_state:
            reversals += 1
            reversal_period = results[run_start_indices[i]].period.isoformat()
            examples.append((reversal_period, prev_state, this_state))

    return StateSeriesMetrics(
        n_months=n,
        state_counts=counts,
        state_pct=pct,
        n_transitions=n_transitions,
        durations_by_state=durations,
        avg_duration_by_state=avg_duration,
        median_duration_by_state=median_duration,
        one_month_reversals=reversals,
        reversal_examples=examples,
    )


def disagreement_frequency(results: list[LaborMonthResult]) -> float:
    """Percentage of months where the two owners' sub-states are in
    active, opposite disagreement (one STRENGTHENING/IMPROVING side,
    the other COOLING/DETERIORATING) -- the specific MIXED cause this
    brief calls out, distinct from a MIXED caused by one side being
    STABLE while the other moves."""
    disagreeing = 0
    total = 0
    opposite_pairs = {
        ("STRENGTHENING", "DETERIORATING"),
        ("COOLING", "IMPROVING"),
    }
    for r in results:
        if r.employment.state == "INSUFFICIENT_DATA" or r.unemployment.state == "INSUFFICIENT_DATA":
            continue
        total += 1
        if (r.employment.state, r.unemployment.state) in opposite_pairs:
            disagreeing += 1
    return (disagreeing / total * 100) if total else 0.0


def payroll_boundary_near_frequency(results: list[LaborMonthResult], near_margin: float) -> float:
    """Percentage of months where `avg_3m` or `avg_6m` falls within
    `near_margin` (absolute jobs/month) of either tolerance-band edge
    -- "close calls" where the classification could plausibly flip
    under a small change to the tolerance. Diagnostic only, not a
    pass/fail test."""
    near = 0
    total = 0
    for r in results:
        e = r.employment
        if e.lower_boundary is None or e.upper_boundary is None or e.avg_3m is None or e.avg_6m is None:
            continue
        total += 1
        near_3m = abs(e.avg_3m - e.lower_boundary) <= near_margin or abs(e.avg_3m - e.upper_boundary) <= near_margin
        near_6m = abs(e.avg_6m - e.lower_boundary) <= near_margin or abs(e.avg_6m - e.upper_boundary) <= near_margin
        if near_3m or near_6m:
            near += 1
    return (near / total * 100) if total else 0.0


def unemployment_boundary_near_frequency(results: list[LaborMonthResult], tolerance: float, near_margin: float) -> float:
    """Percentage of months where `delta` falls within `near_margin`
    (absolute percentage points) of either `+tolerance`/`-tolerance`
    edge."""
    near = 0
    total = 0
    for r in results:
        u = r.unemployment
        if u.delta is None:
            continue
        total += 1
        if abs(u.delta - tolerance) <= near_margin or abs(u.delta + tolerance) <= near_margin:
            near += 1
    return (near / total * 100) if total else 0.0


def sensitivity_count(results_a: list[LaborMonthResult], results_b: list[LaborMonthResult]) -> int:
    """Number of months whose top-level `state` differs between two
    candidate runs over the identical period -- the raw count behind
    "how many classifications change when moving one candidate step."""
    assert len(results_a) == len(results_b)
    return sum(1 for a, b in zip(results_a, results_b) if a.state != b.state)
