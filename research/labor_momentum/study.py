"""Orchestrates the Labor Momentum Methodology Validation (Increment
#20A.1): loads cached FRED data, runs the #20A.1-declared 5x5
threshold grid plus the structural diagnostics, and writes every
result to `outputs/` as CSV. Deterministic -- run it twice against the
same cached data, get byte-identical files (the same guarantee
`research/inflation_momentum/study.py` makes).

Run:
    .venv/bin/python research/labor_momentum/fetch_data.py   # once, or to refresh
    .venv/bin/python research/labor_momentum/study.py
"""

from __future__ import annotations

import csv
from datetime import date as Date
from pathlib import Path

from research.labor_momentum.methodology import (
    LaborMonthResult,
    build_index,
    classify_unemployment_trend,
    evaluate_month,
    load_series,
    month_before,
    month_range,
)
from research.labor_momentum.metrics import (
    compute_state_series_metrics,
    disagreement_frequency,
    payroll_boundary_near_frequency,
    sensitivity_count,
    unemployment_boundary_near_frequency,
)
from research.labor_momentum.regimes import (
    ANALYTICAL_WINDOWS,
    COVID_EXTREME_WINDOW,
    NBER_RECESSIONS,
    REGIME_REVIEW_WINDOWS,
    in_any_window,
)

OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"

# Predeclared candidate set -- exactly as specified by the #20A.1
# prompt (in whole jobs), before any result was examined. Not modified
# after seeing results.
PAYROLL_CANDIDATES: tuple[float, ...] = (0, 25_000, 50_000, 75_000, 100_000)
UNEMPLOYMENT_CANDIDATES: tuple[float, ...] = (0.0, 0.1, 0.2, 0.3, 0.4)

PROPOSED_PAYROLL = 50_000
PROPOSED_UNEMPLOYMENT = 0.2

FULL_HISTORY_START = Date(1990, 1, 1)

# PAYEMS's own native unit is "Thousands of Persons" -- every
# avg_3m/avg_6m/avg_12m value coming out of classify_employment_momentum
# is therefore already expressed in THOUSANDS of jobs, not single jobs.
# The #20A.1 prompt's candidate deltas (0/25,000/50,000/75,000/100,000)
# are stated in whole jobs, so they must be converted to PAYEMS's native
# thousands-of-jobs unit (divide by 1,000) before being passed to any
# classification function -- passing the raw jobs-unit value directly
# would compare a same-order-of-magnitude monthly average (tens to a
# few thousand, in PAYEMS's native units) against a tolerance nominally
# "25,000" but actually meaning 25,000 THOUSAND jobs (25 million), which
# no real monthly average could ever exceed. This was caught as a real
# bug during this study's own first run (every δ_payroll >= 25,000
# produced 0% STRENGTHENING/COOLING across 36 years of history) --
# fixed here, not silently worked around; see
# METHODOLOGY_VALIDATION.md's "Errors and fixes" section.
PAYEMS_THOUSANDS_PER_JOB = 1000


def to_native_payroll_units(delta_jobs: float) -> float:
    return delta_jobs / PAYEMS_THOUSANDS_PER_JOB


def evaluate_range(payems_index, unrate_index, months: list[Date], delta_payroll_jobs: float, delta_unemployment: float) -> list[LaborMonthResult]:
    delta_payroll_native = to_native_payroll_units(delta_payroll_jobs)
    return [evaluate_month(payems_index, unrate_index, t, delta_payroll_native, delta_unemployment) for t in months]


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    print(f"wrote {path} ({len(rows)} rows)")


# ---------------------------------------------------------------------
# 1. State distribution / churn / disagreement, per candidate, per window
# ---------------------------------------------------------------------


def run_candidate_grid(payems_index, unrate_index) -> None:
    rows: list[dict] = []
    for window in ANALYTICAL_WINDOWS:
        months = month_range(window.start, window.end)
        for dp in PAYROLL_CANDIDATES:
            for du in UNEMPLOYMENT_CANDIDATES:
                results = evaluate_range(payems_index, unrate_index, months, dp, du)
                metrics = compute_state_series_metrics(results)
                disagreement = disagreement_frequency(results)
                payroll_near = payroll_boundary_near_frequency(results, near_margin=to_native_payroll_units(5_000))
                unemployment_near = unemployment_boundary_near_frequency(results, tolerance=du, near_margin=0.02)

                row = {
                    "window": window.name,
                    "delta_payroll": dp,
                    "delta_unemployment": du,
                    "n_months": metrics.n_months,
                    "pct_STRENGTHENING": round(metrics.state_pct.get("STRENGTHENING", 0.0), 2),
                    "pct_COOLING": round(metrics.state_pct.get("COOLING", 0.0), 2),
                    "pct_STABLE": round(metrics.state_pct.get("STABLE", 0.0), 2),
                    "pct_MIXED": round(metrics.state_pct.get("MIXED", 0.0), 2),
                    "pct_INSUFFICIENT_DATA": round(metrics.state_pct.get("INSUFFICIENT_DATA", 0.0), 2),
                    "n_transitions": metrics.n_transitions,
                    "avg_duration_STRENGTHENING": round(metrics.avg_duration_by_state.get("STRENGTHENING", 0.0), 2),
                    "avg_duration_COOLING": round(metrics.avg_duration_by_state.get("COOLING", 0.0), 2),
                    "avg_duration_STABLE": round(metrics.avg_duration_by_state.get("STABLE", 0.0), 2),
                    "avg_duration_MIXED": round(metrics.avg_duration_by_state.get("MIXED", 0.0), 2),
                    "median_duration_STRENGTHENING": metrics.median_duration_by_state.get("STRENGTHENING", 0.0),
                    "median_duration_COOLING": metrics.median_duration_by_state.get("COOLING", 0.0),
                    "median_duration_STABLE": metrics.median_duration_by_state.get("STABLE", 0.0),
                    "median_duration_MIXED": metrics.median_duration_by_state.get("MIXED", 0.0),
                    "one_month_reversals": metrics.one_month_reversals,
                    "disagreement_pct": round(disagreement, 2),
                    "payroll_boundary_near_pct": round(payroll_near, 2),
                    "unemployment_boundary_near_pct": round(unemployment_near, 2),
                }
                rows.append(row)

    write_csv(OUTPUT_DIR / "state_distribution_by_candidate.csv", rows, list(rows[0].keys()))


# ---------------------------------------------------------------------
# 2. Sub-state distributions, per candidate, full history
# ---------------------------------------------------------------------


def run_substate_distribution(payems_index, unrate_index) -> None:
    months = month_range(FULL_HISTORY_START, Date(2026, 8, 1))
    rows: list[dict] = []
    for dp in PAYROLL_CANDIDATES:
        results = evaluate_range(payems_index, unrate_index, months, dp, PROPOSED_UNEMPLOYMENT)
        counts: dict[str, int] = {}
        for r in results:
            counts[r.employment.state] = counts.get(r.employment.state, 0) + 1
        n = len(results)
        rows.append({
            "component": "employment_momentum", "varying": "delta_payroll", "value": dp,
            **{f"pct_{k}": round(v / n * 100, 2) for k, v in counts.items()},
        })
    for du in UNEMPLOYMENT_CANDIDATES:
        results = evaluate_range(payems_index, unrate_index, months, PROPOSED_PAYROLL, du)
        counts = {}
        for r in results:
            counts[r.unemployment.state] = counts.get(r.unemployment.state, 0) + 1
        n = len(results)
        rows.append({
            "component": "unemployment_trend", "varying": "delta_unemployment", "value": du,
            **{f"pct_{k}": round(v / n * 100, 2) for k, v in counts.items()},
        })

    all_keys: set[str] = set()
    for r in rows:
        all_keys.update(r.keys())
    fieldnames = ["component", "varying", "value"] + sorted(k for k in all_keys if k.startswith("pct_"))
    for r in rows:
        for k in fieldnames:
            r.setdefault(k, 0.0)
    write_csv(OUTPUT_DIR / "substate_distribution.csv", rows, fieldnames)


# ---------------------------------------------------------------------
# 3. Sensitivity: months that flip when moving one candidate step
# ---------------------------------------------------------------------


def run_sensitivity(payems_index, unrate_index) -> None:
    months = month_range(FULL_HISTORY_START, Date(2026, 8, 1))
    rows: list[dict] = []

    # Vary payroll delta, hold unemployment delta at the proposed 0.2pp.
    payroll_runs = {dp: evaluate_range(payems_index, unrate_index, months, dp, PROPOSED_UNEMPLOYMENT) for dp in PAYROLL_CANDIDATES}
    for i in range(len(PAYROLL_CANDIDATES) - 1):
        a, b = PAYROLL_CANDIDATES[i], PAYROLL_CANDIDATES[i + 1]
        n_changed = sensitivity_count(payroll_runs[a], payroll_runs[b])
        rows.append({
            "axis": "delta_payroll", "from": a, "to": b, "unemployment_delta_held_at": PROPOSED_UNEMPLOYMENT,
            "n_months_changed": n_changed, "pct_months_changed": round(n_changed / len(months) * 100, 2),
        })

    # Vary unemployment delta, hold payroll delta at the proposed 50K.
    unemployment_runs = {du: evaluate_range(payems_index, unrate_index, months, PROPOSED_PAYROLL, du) for du in UNEMPLOYMENT_CANDIDATES}
    for i in range(len(UNEMPLOYMENT_CANDIDATES) - 1):
        a, b = UNEMPLOYMENT_CANDIDATES[i], UNEMPLOYMENT_CANDIDATES[i + 1]
        n_changed = sensitivity_count(unemployment_runs[a], unemployment_runs[b])
        rows.append({
            "axis": "delta_unemployment", "from": a, "to": b, "payroll_delta_held_at": PROPOSED_PAYROLL,
            "n_months_changed": n_changed, "pct_months_changed": round(n_changed / len(months) * 100, 2),
        })

    fieldnames = ["axis", "from", "to", "unemployment_delta_held_at", "payroll_delta_held_at", "n_months_changed", "pct_months_changed"]
    for r in rows:
        r.setdefault("unemployment_delta_held_at", "")
        r.setdefault("payroll_delta_held_at", "")
    write_csv(OUTPUT_DIR / "sensitivity.csv", rows, fieldnames)


# ---------------------------------------------------------------------
# 4. Regime review, proposed candidate only
# ---------------------------------------------------------------------


def run_regime_review(payems_index, unrate_index) -> None:
    rows: list[dict] = []
    for window in REGIME_REVIEW_WINDOWS:
        months = month_range(window.start, window.end)
        for t in months:
            r = evaluate_month(payems_index, unrate_index, t, to_native_payroll_units(PROPOSED_PAYROLL), PROPOSED_UNEMPLOYMENT)
            nber_context = in_any_window(t, NBER_RECESSIONS)
            rows.append({
                "regime": window.name,
                "period": t.isoformat(),
                "nber_recession_context": nber_context or "",
                "payems_avg_3m": _fmt(r.employment.avg_3m),
                "payems_avg_6m": _fmt(r.employment.avg_6m),
                "payems_avg_12m": _fmt(r.employment.avg_12m),
                "employment_momentum_state": r.employment.state,
                "unrate_current_3m": _fmt(r.unemployment.current_3m),
                "unrate_prior_year_3m": _fmt(r.unemployment.prior_year_3m),
                "unrate_delta": _fmt(r.unemployment.delta),
                "unemployment_trend_state": r.unemployment.state,
                "labor_state": r.state,
            })
    fieldnames = list(rows[0].keys())
    write_csv(OUTPUT_DIR / "regime_review.csv", rows, fieldnames)


def _fmt(x: float | None) -> str:
    return "" if x is None else f"{x:.4f}"


# ---------------------------------------------------------------------
# 5. COVID 12-month-baseline contamination
# ---------------------------------------------------------------------


def run_covid_contamination(payems_index, unrate_index) -> None:
    months = month_range(Date(2020, 1, 1), Date(2023, 6, 1))
    rows: list[dict] = []
    for t in months:
        r = evaluate_month(payems_index, unrate_index, t, to_native_payroll_units(PROPOSED_PAYROLL), PROPOSED_UNEMPLOYMENT)
        window_12m_start = month_before(t, 11)
        contaminated = window_12m_start <= COVID_EXTREME_WINDOW.end and t >= COVID_EXTREME_WINDOW.start
        rows.append({
            "period": t.isoformat(),
            "avg_12m_window_start": window_12m_start.isoformat(),
            "covid_extreme_window_in_12m_baseline": contaminated,
            "payems_avg_3m": _fmt(r.employment.avg_3m),
            "payems_avg_12m": _fmt(r.employment.avg_12m),
            "employment_momentum_state": r.employment.state,
            "labor_state": r.state,
        })
    write_csv(OUTPUT_DIR / "covid_contamination.csv", rows, list(rows[0].keys()))


# ---------------------------------------------------------------------
# 6. Payroll scale over decades
# ---------------------------------------------------------------------


def run_payroll_scale(payems_index) -> None:
    representative_dates = [Date(y, 1, 1) for y in (1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025)] + [Date(2026, 8, 1)]
    rows: list[dict] = []
    for t in representative_dates:
        level = payems_index.get(t)
        if level is None:
            continue
        rows.append({
            "period": t.isoformat(),
            "payems_level_thousands": level,
            "delta_50k_as_pct_of_level": round(50_000 / (level * 1000) * 100, 4),
        })
    write_csv(OUTPUT_DIR / "payroll_scale_over_decades.csv", rows, list(rows[0].keys()))


# ---------------------------------------------------------------------
# 7. Unemployment year-ago-comparison lag check
# ---------------------------------------------------------------------


def run_unemployment_lag_check(unrate_index) -> None:
    """For every month in the full history, report UNRATE's own level
    alongside classify_unemployment_trend's `current_3m`/`delta` at the
    proposed tolerance -- lets the report inspect, e.g., a steadily
    rising-unemployment period where the level is nonetheless still
    below where it was a year ago (see METHODOLOGY_VALIDATION.md)."""
    months = month_range(FULL_HISTORY_START, Date(2026, 8, 1))
    rows: list[dict] = []
    for t in months:
        level = unrate_index.get(t)
        r_unemployment = classify_unemployment_trend(unrate_index, t, PROPOSED_UNEMPLOYMENT)
        rows.append({
            "period": t.isoformat(),
            "unrate_level": _fmt(level),
            "current_3m": _fmt(r_unemployment.current_3m),
            "prior_year_3m": _fmt(r_unemployment.prior_year_3m),
            "delta": _fmt(r_unemployment.delta),
            "state": r_unemployment.state,
        })
    write_csv(OUTPUT_DIR / "unemployment_lag_check.csv", rows, list(rows[0].keys()))


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payems_index = build_index(load_series("PAYEMS"))
    unrate_index = build_index(load_series("UNRATE"))

    run_candidate_grid(payems_index, unrate_index)
    run_substate_distribution(payems_index, unrate_index)
    run_sensitivity(payems_index, unrate_index)
    run_regime_review(payems_index, unrate_index)
    run_covid_contamination(payems_index, unrate_index)
    run_payroll_scale(payems_index)
    run_unemployment_lag_check(unrate_index)


if __name__ == "__main__":
    main()
