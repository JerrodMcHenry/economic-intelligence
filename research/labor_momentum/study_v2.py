"""Orchestrates the Increment #20A.2 payroll methodology redesign
study: synthetic scenarios, the two critical #20A.1 failure windows,
full-history state distributions/churn for Candidates A and B across a
predeclared deadband grid, regime review, temporal responsiveness,
COVID robustness, payroll scale, and UNRATE temporal-horizon
compatibility. Writes every result to `outputs/` as CSV, alongside
#20A.1's own (unmodified) outputs.

Run:
    .venv/bin/python research/labor_momentum/fetch_data.py   # once, or to refresh
    .venv/bin/python -m research.labor_momentum.study_v2
"""

from __future__ import annotations

import csv
from datetime import date as Date
from pathlib import Path

from research.labor_momentum.methodology import (
    build_index,
    classify_unemployment_trend,
    load_series,
    month_range,
)
from research.labor_momentum.methodology_v2 import (
    build_payems_persons_index,
    classify_condition,
    classify_momentum,
    combine_employment_state,
    combine_labor_state,
    evaluate_candidate_a,
    evaluate_candidate_b,
)
from research.labor_momentum.metrics import compute_state_series_metrics
from research.labor_momentum.regimes import NBER_RECESSIONS, in_any_window

OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"
FULL_HISTORY_START = Date(1990, 1, 1)
FULL_HISTORY_END = Date(2026, 8, 1)

# Predeclared deadband grid -- small, stated before any result was
# examined. Same candidate values used for both condition and momentum
# (a deliberate simplification, not a claim the two need identical
# grounding -- see METHODOLOGY_REDESIGN.md's own limitations section).
CONDITION_DEADBAND_CANDIDATES: tuple[float, ...] = (0, 25_000, 50_000)
MOMENTUM_DEADBAND_CANDIDATES: tuple[float, ...] = (0, 25_000, 50_000)

# The single pair carried into the deeper regime/temporal/COVID
# sections below -- chosen only after §14 (deadband analysis) in
# METHODOLOGY_REDESIGN.md, never before: 50,000 for both, consistent
# with #20A.1's own BLS-sampling-error-grounded figure for a single
# 3-month payroll average (condition), conservatively carried over to
# momentum (a difference of two such averages, with correspondingly
# higher implied variance -- see METHODOLOGY_REDESIGN.md's own
# threshold-grounding section for the full reasoning).
WORKING_CONDITION_DEADBAND = 50_000
WORKING_MOMENTUM_DEADBAND = 50_000
UNEMPLOYMENT_DEADBAND = 0.2  # unchanged from #20A/#20A.1; not redesigned this turn

CRITICAL_MONTHS: tuple[Date, ...] = (Date(2009, 8, 1), Date(2021, 4, 1), Date(2021, 5, 1), Date(2021, 6, 1))

SYNTHETIC_SCENARIOS: tuple[tuple[str, float, float, str], ...] = (
    # (label, prior_jobs, recent_jobs, expected_semantic)
    ("A", 200_000, 300_000, "expanding, improving (accelerating)"),
    ("B", 300_000, 150_000, "expanding, worsening (decelerating)"),
    ("C", -500_000, -250_000, "contracting, improving -> RECOVERING"),
    ("D", -200_000, -400_000, "contracting, worsening"),
    ("E", -100_000, 100_000, "returned to expansion"),
    ("F", 100_000, -100_000, "entered contraction"),
    ("G", 20_000, -10_000, "near-flat / noisy boundary"),
)


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    print(f"wrote {path} ({len(rows)} rows)")


def _fmt(x: float | None) -> str:
    return "" if x is None else f"{x:.1f}"


class _StateOnly:
    """Adapts a bare state string (plus its period) into the
    `.state`/`.period`-attribute shape `compute_state_series_metrics`
    expects, without needing a full `LaborMonthResult`/`EmploymentResult`
    for a metrics-only pass."""

    def __init__(self, state: str, period: Date) -> None:
        self.state = state
        self.period = period


# ---------------------------------------------------------------------
# 1. Synthetic scenario matrix
# ---------------------------------------------------------------------


def run_synthetic_scenarios() -> None:
    rows: list[dict] = []
    for label, prior, recent, expected in SYNTHETIC_SCENARIOS:
        # Candidate B's "current_3m"/"prior_3m" map directly onto the
        # scenario's own recent/prior values. Candidate A's
        # recent_6m = mean(recent_3m, older_3m) -- the two non-
        # overlapping 3-month blocks the scenario already describes.
        recent_6m = (recent + prior) / 2
        for cd in CONDITION_DEADBAND_CANDIDATES:
            for md in MOMENTUM_DEADBAND_CANDIDATES:
                cond_b = classify_condition(recent, cd)
                mom_b = classify_momentum(recent, prior, md)
                state_b = combine_employment_state(cond_b, mom_b)

                cond_a = classify_condition(recent, cd)
                mom_a = classify_momentum(recent, recent_6m, md)
                state_a = combine_employment_state(cond_a, mom_a)

                rows.append({
                    "scenario": label, "prior_jobs": prior, "recent_jobs": recent, "expected_semantic": expected,
                    "condition_deadband_jobs": cd, "momentum_deadband_jobs": md,
                    "candidate_B_condition": cond_b, "candidate_B_momentum": mom_b, "candidate_B_state": state_b,
                    "candidate_A_condition": cond_a, "candidate_A_momentum": mom_a, "candidate_A_state": state_a,
                })
    write_csv(OUTPUT_DIR / "v2_synthetic_scenarios.csv", rows, list(rows[0].keys()))


# ---------------------------------------------------------------------
# 2. Critical #20A.1 failure months, both candidates, full deadband grid
# ---------------------------------------------------------------------


def run_critical_months(payems_index) -> None:
    rows: list[dict] = []
    for t in CRITICAL_MONTHS:
        for cd in CONDITION_DEADBAND_CANDIDATES:
            for md in MOMENTUM_DEADBAND_CANDIDATES:
                a = evaluate_candidate_a(payems_index, t, cd, md)
                b = evaluate_candidate_b(payems_index, t, cd, md)
                rows.append({
                    "period": t.isoformat(), "condition_deadband_jobs": cd, "momentum_deadband_jobs": md,
                    "A_condition_value": _fmt(a.condition_value), "A_momentum_recent": _fmt(a.momentum_recent), "A_momentum_older": _fmt(a.momentum_older),
                    "A_condition": a.condition, "A_momentum": a.momentum, "A_state": a.state,
                    "B_condition_value": _fmt(b.condition_value), "B_momentum_recent": _fmt(b.momentum_recent), "B_momentum_older": _fmt(b.momentum_older),
                    "B_condition": b.condition, "B_momentum": b.momentum, "B_state": b.state,
                })
    write_csv(OUTPUT_DIR / "v2_critical_months.csv", rows, list(rows[0].keys()))


# ---------------------------------------------------------------------
# 3. Full-history state distributions / churn, both candidates, full grid
# ---------------------------------------------------------------------


def run_full_history_grid(payems_index) -> None:
    months = month_range(FULL_HISTORY_START, FULL_HISTORY_END)
    rows: list[dict] = []
    for candidate_name, evaluate in (("A", evaluate_candidate_a), ("B", evaluate_candidate_b)):
        for cd in CONDITION_DEADBAND_CANDIDATES:
            for md in MOMENTUM_DEADBAND_CANDIDATES:
                results = [evaluate(payems_index, t, cd, md) for t in months]
                states = [r.state for r in results]
                counts: dict[str, int] = {}
                for s in states:
                    counts[s] = counts.get(s, 0) + 1
                n = len(states)

                metrics = compute_state_series_metrics([_StateOnly(s, t) for s, t in zip(states, months)])  # type: ignore[arg-type]

                rows.append({
                    "candidate": candidate_name, "condition_deadband_jobs": cd, "momentum_deadband_jobs": md,
                    "n_months": n,
                    **{f"pct_{k}": round(v / n * 100, 2) for k, v in counts.items()},
                    "n_transitions": metrics.n_transitions,
                    "one_month_reversals": metrics.one_month_reversals,
                    "avg_duration_CONTRACTING": round(metrics.avg_duration_by_state.get("CONTRACTING", 0.0), 2),
                    "avg_duration_RECOVERING": round(metrics.avg_duration_by_state.get("RECOVERING", 0.0), 2),
                    "avg_duration_EXPANDING": round(metrics.avg_duration_by_state.get("EXPANDING", 0.0), 2),
                    "median_duration_RECOVERING": metrics.median_duration_by_state.get("RECOVERING", 0.0),
                })

    all_keys: set[str] = set()
    for r in rows:
        all_keys.update(r.keys())
    fieldnames = ["candidate", "condition_deadband_jobs", "momentum_deadband_jobs", "n_months"] + sorted(
        k for k in all_keys if k not in ("candidate", "condition_deadband_jobs", "momentum_deadband_jobs", "n_months")
    )
    for r in rows:
        for k in fieldnames:
            r.setdefault(k, 0.0)
    write_csv(OUTPUT_DIR / "v2_employment_state_grid.csv", rows, fieldnames)


# ---------------------------------------------------------------------
# 4. Top-level Labor state, working candidate, full history + regimes
# ---------------------------------------------------------------------


def run_top_level(payems_index, unrate_index) -> None:
    months = month_range(FULL_HISTORY_START, FULL_HISTORY_END)
    rows: list[dict] = []
    for t in months:
        emp = evaluate_candidate_b(payems_index, t, WORKING_CONDITION_DEADBAND, WORKING_MOMENTUM_DEADBAND)
        unemp = classify_unemployment_trend(unrate_index, t, UNEMPLOYMENT_DEADBAND)
        labor = combine_labor_state(emp.state, unemp.state)
        nber = in_any_window(t, NBER_RECESSIONS)
        rows.append({
            "period": t.isoformat(),
            "nber_recession_context": nber or "",
            "employment_condition": emp.condition,
            "employment_momentum": emp.momentum,
            "employment_state": emp.state,
            "unemployment_state": unemp.state,
            "labor_state": labor,
        })
    write_csv(OUTPUT_DIR / "v2_top_level_full_history.csv", rows, list(rows[0].keys()))

    # Top-level state distribution + MIXED analysis summary
    states = [r["labor_state"] for r in rows]
    counts: dict[str, int] = {}
    for s in states:
        counts[s] = counts.get(s, 0) + 1
    n = len(states)
    summary_rows = [{"labor_state": k, "pct": round(v / n * 100, 2), "n": v} for k, v in counts.items()]
    write_csv(OUTPUT_DIR / "v2_top_level_distribution.csv", summary_rows, ["labor_state", "pct", "n"])


# ---------------------------------------------------------------------
# 5. Temporal responsiveness around named regimes
# ---------------------------------------------------------------------

RESPONSIVENESS_WINDOWS: tuple[tuple[str, Date, Date], ...] = (
    ("2001 recession onset", Date(2000, 9, 1), Date(2001, 12, 1)),
    ("2003-2004 recovery", Date(2003, 1, 1), Date(2004, 12, 1)),
    ("2007-2009 recession onset", Date(2007, 6, 1), Date(2008, 12, 1)),
    ("2009-2011 recovery", Date(2009, 6, 1), Date(2011, 12, 1)),
    ("2015-2016 slowdown", Date(2015, 6, 1), Date(2016, 12, 1)),
    ("2018-2019 late cycle", Date(2018, 1, 1), Date(2019, 12, 1)),
    ("2020 collapse", Date(2020, 1, 1), Date(2020, 6, 1)),
    ("2020-2022 rehiring", Date(2020, 7, 1), Date(2022, 6, 1)),
    ("2022-2024 normalization", Date(2022, 7, 1), Date(2024, 12, 1)),
    ("latest period", Date(2025, 1, 1), Date(2026, 8, 1)),
)


def run_responsiveness(payems_index, unrate_index) -> None:
    rows: list[dict] = []
    for name, start, end in RESPONSIVENESS_WINDOWS:
        months = month_range(start, end)
        for t in months:
            emp = evaluate_candidate_b(payems_index, t, WORKING_CONDITION_DEADBAND, WORKING_MOMENTUM_DEADBAND)
            unemp = classify_unemployment_trend(unrate_index, t, UNEMPLOYMENT_DEADBAND)
            labor = combine_labor_state(emp.state, unemp.state)
            rows.append({
                "regime": name, "period": t.isoformat(),
                "employment_state": emp.state, "unemployment_state": unemp.state, "labor_state": labor,
            })
    write_csv(OUTPUT_DIR / "v2_responsiveness.csv", rows, list(rows[0].keys()))


# ---------------------------------------------------------------------
# 6. Payroll scale check (redesigned deadbands, persons units)
# ---------------------------------------------------------------------


def run_scale_check(payems_index) -> None:
    representative_dates = [Date(y, 1, 1) for y in (1990, 2000, 2010, 2020, 2025)] + [Date(2026, 8, 1)]
    rows: list[dict] = []
    for t in representative_dates:
        level = payems_index.get(t)
        if level is None:
            continue
        rows.append({
            "period": t.isoformat(),
            "payems_level_persons": round(level),
            "condition_deadband_25k_as_pct_of_level": round(25_000 / level * 100, 4),
            "condition_deadband_50k_as_pct_of_level": round(50_000 / level * 100, 4),
        })
    write_csv(OUTPUT_DIR / "v2_payroll_scale.csv", rows, list(rows[0].keys()))


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payems_index = build_payems_persons_index(load_series("PAYEMS"))
    unrate_index = build_index(load_series("UNRATE"))

    run_synthetic_scenarios()
    run_critical_months(payems_index)
    run_full_history_grid(payems_index)
    run_top_level(payems_index, unrate_index)
    run_responsiveness(payems_index, unrate_index)
    run_scale_check(payems_index)


if __name__ == "__main__":
    main()
