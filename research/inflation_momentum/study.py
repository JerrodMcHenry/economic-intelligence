"""Orchestrates the Inflation Momentum Methodology Study: loads cached
data (see fetch_data.py), computes transformations, runs every
candidate methodology/variant against every series, computes evaluation
metrics, cross-measure agreement, regime coverage, target-gap, and
adversarial cases, and writes every result to research/inflation_momentum/outputs/
as CSV/JSON (stable, inspectable, diffable formats -- no chart is
required to read any conclusion here).

Deterministic: run twice against the same cached data, get byte-
identical output files (verified by tests/research/test_study_outputs.py).
Does not select a winning methodology -- it only measures.

Run:
    .venv/bin/python research/inflation_momentum/study.py
"""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research.inflation_momentum.methodology import (  # noqa: E402
    Observation,
    TransformedRow,
    classify_candidate_a,
    classify_candidate_b,
    classify_candidate_c,
    classify_candidate_d,
    compute_delta_3m,
    compute_transformations,
    latest_available_period,
    latest_common_period,
    load_series,
    load_series_metadata,
)
from research.inflation_momentum.metrics import compute_agreement, compute_state_series_metrics  # noqa: E402
from research.inflation_momentum.regimes import REGIMES, regime_coverage  # noqa: E402

OUTPUTS_DIR = Path(__file__).resolve().parent / "outputs"

CANONICAL_SERIES = {
    "Core PCE": "PCEPILFE",
    "Core CPI": "CPILFESL",
    "Headline PCE": "PCEPI",
    "Headline CPI": "CPIAUCSL",
}

DELTAS = [0.00, 0.10, 0.25, 0.50]
OPPOSITE_PAIRS = {("COOLING", "HEATING"), ("HEATING", "COOLING")}


def _write_json(name: str, data) -> None:
    (OUTPUTS_DIR / name).write_text(json.dumps(data, indent=2, sort_keys=True, default=str))


def _write_csv(name: str, rows: list[dict]) -> None:
    if not rows:
        (OUTPUTS_DIR / name).write_text("")
        return
    # Different candidate families report different state-percentage
    # columns (e.g. Candidate A has pct_STABLE, Candidate B has
    # pct_MIXED_OR_STABLE, Candidate D has pct_ACCELERATING/etc.) -- the
    # union of every row's keys, in first-seen order, so no row's fields
    # are silently dropped and every column's meaning stays traceable to
    # where it came from.
    fieldnames: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    with open(OUTPUTS_DIR / name, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, restval="")
        writer.writeheader()
        for row in sorted(rows, key=lambda r: tuple(str(v) for v in r.values())):
            writer.writerow(row)


def load_all() -> dict[str, list[Observation]]:
    return {label: load_series(series_id) for label, series_id in CANONICAL_SERIES.items()}


def build_rows(all_obs: dict[str, list[Observation]]) -> dict[str, list[TransformedRow]]:
    return {label: compute_transformations(obs) for label, obs in all_obs.items()}


# ---------------------------------------------------------------------
# 1. Data coverage
# ---------------------------------------------------------------------


def data_coverage_report(all_obs: dict[str, list[Observation]]) -> list[dict]:
    rows = []
    for label, series_id in CANONICAL_SERIES.items():
        meta = load_series_metadata(series_id)
        obs = all_obs[label]
        non_missing = [o for o in obs if o.value is not None]
        missing = [o for o in obs if o.value is None]
        rows.append({
            "label": label,
            "series_id": series_id,
            "title": meta.get("title"),
            "units": meta.get("units"),
            "frequency": meta.get("frequency"),
            "seasonal_adjustment": meta.get("seasonal_adjustment"),
            "first_observation": obs[0].date.isoformat() if obs else None,
            "last_observation": obs[-1].date.isoformat() if obs else None,
            "num_observations_used": len(obs),
            "num_missing_observations": len(missing),
            "missing_dates": [o.date.isoformat() for o in missing],
        })
    common = latest_common_period(all_obs)
    return rows, common


# ---------------------------------------------------------------------
# 2. Candidate metrics per series
# ---------------------------------------------------------------------


def candidate_a_states(rows: list[TransformedRow], delta: float) -> list[str | None]:
    return [classify_candidate_a(r, delta) for r in rows]


def candidate_b_states(rows: list[TransformedRow], delta: float) -> list[str | None]:
    return [classify_candidate_b(r, delta) for r in rows]


def candidate_c_states(rows: list[TransformedRow], band: float) -> list[str | None]:
    return [classify_candidate_c(r, band) for r in rows]


def candidate_d_states(rows: list[TransformedRow], flat_band: float = 0.0) -> list[str | None]:
    deltas = compute_delta_3m(rows)
    return [classify_candidate_d(d, flat_band) for d in deltas]


def all_candidate_state_series(rows_by_series: dict[str, list[TransformedRow]]) -> dict[tuple[str, str], list[str | None]]:
    """Every (series_label, candidate_variant_label) -> state series."""
    result: dict[tuple[str, str], list[str | None]] = {}
    for label, rows in rows_by_series.items():
        for delta in DELTAS:
            result[(label, f"A_delta_{delta:.2f}")] = candidate_a_states(rows, delta)
            result[(label, f"B_delta_{delta:.2f}")] = candidate_b_states(rows, delta)
        result[(label, "C_band_0.00")] = candidate_c_states(rows, band=0.0)
        result[(label, "C_band_0.25_exploratory")] = candidate_c_states(rows, band=0.25)
        result[(label, "D_flatband_0.00")] = candidate_d_states(rows, flat_band=0.0)
    return result


def metrics_report(state_series: dict[tuple[str, str], list[str | None]]) -> list[dict]:
    rows = []
    for (label, variant), states in state_series.items():
        m = compute_state_series_metrics(states)
        rows.append({
            "series": label,
            "candidate_variant": variant,
            "total_months": m.total_months,
            "classified_months": m.classified_months,
            "unclassified_months": m.unclassified_months,
            "pct_unclassified": round(m.pct_unclassified, 3),
            **{f"pct_{state}": round(pct, 3) for state, pct in m.state_percentages.items()},
            "num_state_changes": m.num_state_changes,
            "state_change_rate": round(m.state_change_rate, 4),
            "median_state_duration_months": m.median_state_duration,
            "mean_state_duration_months": round(m.mean_state_duration, 3) if m.mean_state_duration else None,
            "num_one_month_reversals": m.num_one_month_reversals,
            "num_two_month_reversals": m.num_two_month_reversals,
            "num_cooling_heating_cooling_whipsaws": m.num_cooling_heating_cooling_whipsaws,
            "num_heating_cooling_heating_whipsaws": m.num_heating_cooling_heating_whipsaws,
            "longest_run_COOLING": m.longest_run_by_state.get("COOLING", 0),
            "longest_run_HEATING": m.longest_run_by_state.get("HEATING", 0),
        })
    return rows


# ---------------------------------------------------------------------
# 3. Cross-measure agreement (representative variants: A/delta=0.25, B/delta=0.25)
# ---------------------------------------------------------------------


def align_two(rows_a: list[TransformedRow], rows_b: list[TransformedRow]) -> tuple[list[TransformedRow], list[TransformedRow]]:
    """Restrict two (possibly differently-dated) row lists to their
    common dates only -- never zip by position."""
    dates_a = {r.date: r for r in rows_a}
    dates_b = {r.date: r for r in rows_b}
    common_dates = sorted(set(dates_a) & set(dates_b))
    return [dates_a[d] for d in common_dates], [dates_b[d] for d in common_dates]


def cross_measure_agreement_report(rows_by_series: dict[str, list[TransformedRow]]) -> list[dict]:
    pairs = [
        ("Core PCE", "Core CPI"),
        ("Headline PCE", "Headline CPI"),
        ("Core PCE", "Headline PCE"),
        ("Core PCE", "Headline CPI"),
    ]
    results = []
    for variant_name, classify_fn, params in [
        ("A_delta_0.25", classify_candidate_a, 0.25),
        ("B_delta_0.25", classify_candidate_b, 0.25),
    ]:
        for a_label, b_label in pairs:
            rows_a, rows_b = align_two(rows_by_series[a_label], rows_by_series[b_label])
            states_a = [classify_fn(r, params) for r in rows_a]
            states_b = [classify_fn(r, params) for r in rows_b]
            agreement = compute_agreement(states_a, states_b, OPPOSITE_PAIRS)
            results.append({
                "candidate_variant": variant_name,
                "series_a": a_label,
                "series_b": b_label,
                "compared_months": agreement.compared_months,
                "same_state_pct": round(agreement.same_state_pct, 3),
                "opposite_state_pct": round(agreement.opposite_state_pct, 3),
                "other_pct": round(agreement.other_pct, 3),
            })

    # All-four agreement (Candidate A, delta=0.25): how often do Core PCE,
    # Core CPI, Headline PCE, Headline CPI ALL share the same classified
    # state on a common date?
    labels = list(CANONICAL_SERIES.keys())
    common_dates = set(r.date for r in rows_by_series[labels[0]])
    for label in labels[1:]:
        common_dates &= set(r.date for r in rows_by_series[label])
    common_dates = sorted(common_dates)
    by_date = {label: {r.date: r for r in rows_by_series[label]} for label in labels}
    all_four_same = 0
    all_four_classified = 0
    hierarchy_divergence = 0  # Core PCE+Core CPI agree, but disagree with Headline PCE+Headline CPI (both same internally)
    for d in common_dates:
        states = {label: classify_candidate_a(by_date[label][d], 0.25) for label in labels}
        if any(s is None for s in states.values()):
            continue
        all_four_classified += 1
        if len(set(states.values())) == 1:
            all_four_same += 1
        core_pce, core_cpi = states["Core PCE"], states["Core CPI"]
        head_pce, head_cpi = states["Headline PCE"], states["Headline CPI"]
        if core_pce == core_cpi and head_pce == head_cpi and core_pce != head_pce and {core_pce, head_pce} == {"COOLING", "HEATING"}:
            hierarchy_divergence += 1

    results.append({
        "candidate_variant": "A_delta_0.25",
        "series_a": "ALL_FOUR",
        "series_b": "ALL_FOUR",
        "compared_months": all_four_classified,
        "same_state_pct": round(all_four_same / all_four_classified * 100, 3) if all_four_classified else None,
        "opposite_state_pct": None,
        "other_pct": None,
        "note": "same_state_pct = % of common, fully-classified months where all four series share one state",
    })
    results.append({
        "candidate_variant": "A_delta_0.25",
        "series_a": "CORE_BLOC_VS_HEADLINE_BLOC",
        "series_b": "hierarchy_divergence_count",
        "compared_months": all_four_classified,
        "same_state_pct": None,
        "opposite_state_pct": round(hierarchy_divergence / all_four_classified * 100, 3) if all_four_classified else None,
        "other_pct": None,
        "note": "% of months where Core PCE=Core CPI (internally agreeing) but strictly opposite Headline PCE=Headline CPI (internally agreeing)",
    })
    return results


# ---------------------------------------------------------------------
# 4. Regime coverage + representative-candidate behavior
# ---------------------------------------------------------------------


def regime_report(all_obs: dict[str, list[Observation]], rows_by_series: dict[str, list[TransformedRow]]) -> list[dict]:
    results = []
    core_pce_rows = {r.date: r for r in rows_by_series["Core PCE"]}
    for regime in REGIMES:
        entry = {"regime": regime.name, "start": regime.start.isoformat(), "end": regime.end.isoformat(), "note": regime.note}
        coverage_by_series = {}
        for label, obs in all_obs.items():
            first = obs[0].date if obs else None
            last = obs[-1].date if obs else None
            coverage_by_series[label] = regime_coverage(regime, first, last)
        entry["coverage_by_series"] = coverage_by_series

        window_states = []
        for d in sorted(core_pce_rows):
            if regime.start <= d <= regime.end:
                state = classify_candidate_a(core_pce_rows[d], delta=0.25)
                window_states.append(state)
        classified = [s for s in window_states if s is not None]
        entry["core_pce_candidate_a_delta_0.25_months_in_window"] = len(window_states)
        entry["core_pce_candidate_a_delta_0.25_classified_months"] = len(classified)
        if classified:
            counts = {}
            for s in classified:
                counts[s] = counts.get(s, 0) + 1
            entry["core_pce_candidate_a_delta_0.25_state_counts"] = counts
            num_changes = sum(1 for i in range(1, len(classified)) if classified[i] != classified[i - 1])
            entry["core_pce_candidate_a_delta_0.25_state_changes_within_window"] = num_changes
        results.append(entry)
    return results


# ---------------------------------------------------------------------
# 5. Target gap (Headline PCE YoY - 2.0)
# ---------------------------------------------------------------------


def target_gap_report(rows_by_series: dict[str, list[TransformedRow]]) -> list[dict]:
    rows = []
    for r in rows_by_series["Headline PCE"]:
        if r.chg_12m_yoy is None:
            continue
        rows.append({"date": r.date.isoformat(), "headline_pce_yoy": round(r.chg_12m_yoy, 4), "target": 2.0, "gap_pp": round(r.chg_12m_yoy - 2.0, 4)})
    return rows


# ---------------------------------------------------------------------
# 6. Adversarial cases (synthetic, deterministic, hand-specified)
# ---------------------------------------------------------------------


def _synthetic_row(chg_3m=None, chg_6m=None, chg_12m=None, d=date(2024, 1, 1)):
    return TransformedRow(date=d, level=None, chg_1m_ann=None, chg_3m_ann=chg_3m, chg_6m_ann=chg_6m, chg_12m_yoy=chg_12m)


def adversarial_cases_report() -> list[dict]:
    cases = []

    def record(case_id, description, row_or_rows, extra=None):
        entry = {"case": case_id, "description": description}
        if extra:
            entry.update(extra)
        cases.append(entry)

    # A. 3M substantially below 12M.
    row = _synthetic_row(chg_3m=0.5, chg_6m=1.5, chg_12m=4.0)
    record("A", "3M substantially below 12M", row, {
        "inputs": asdict(row),
        "candidate_A_delta_0.25": classify_candidate_a(row, 0.25),
        "candidate_B_delta_0.25": classify_candidate_b(row, 0.25),
        "candidate_C_band_0": classify_candidate_c(row, 0.0),
    })

    # B. 3M substantially above 12M.
    row = _synthetic_row(chg_3m=6.0, chg_6m=4.5, chg_12m=2.0)
    record("B", "3M substantially above 12M", row, {
        "inputs": asdict(row),
        "candidate_A_delta_0.25": classify_candidate_a(row, 0.25),
        "candidate_B_delta_0.25": classify_candidate_b(row, 0.25),
        "candidate_C_band_0": classify_candidate_c(row, 0.0),
    })

    # C. 3M approximately equal to 12M.
    row = _synthetic_row(chg_3m=3.0, chg_6m=3.0, chg_12m=3.0)
    record("C", "3M approximately equal to 12M", row, {
        "inputs": asdict(row),
        "candidate_A_delta_0.25": classify_candidate_a(row, 0.25),
        "candidate_B_delta_0.25": classify_candidate_b(row, 0.25),
        "candidate_C_band_0": classify_candidate_c(row, 0.0),
    })

    # D. 3M below 12M but 6M above 12M.
    row = _synthetic_row(chg_3m=1.0, chg_6m=4.0, chg_12m=3.0)
    record("D", "3M below 12M but 6M above 12M (conflicting signals)", row, {
        "inputs": asdict(row),
        "candidate_A_delta_0.25": classify_candidate_a(row, 0.25),
        "candidate_B_delta_0.25": classify_candidate_b(row, 0.25),
        "candidate_C_band_0": classify_candidate_c(row, 0.0),
    })

    # E. 3M above 12M but 6M below 12M.
    row = _synthetic_row(chg_3m=4.0, chg_6m=1.0, chg_12m=3.0)
    record("E", "3M above 12M but 6M below 12M (conflicting signals)", row, {
        "inputs": asdict(row),
        "candidate_A_delta_0.25": classify_candidate_a(row, 0.25),
        "candidate_B_delta_0.25": classify_candidate_b(row, 0.25),
        "candidate_C_band_0": classify_candidate_c(row, 0.0),
    })

    # F/G handled empirically in cross_measure_agreement_report / regime_report using real data;
    # documented here as pointers, not fabricated synthetic examples for real economic series.
    record("F", "Core PCE cooling while Core CPI heating -- see cross_measure_agreement.csv "
                "(opposite_state_pct column, Core PCE vs Core CPI row) for the real, empirically observed rate", None)
    record("G", "Core measures cooling while headline measures heat -- see cross_measure_agreement.csv's "
                "hierarchy_divergence_count row for the real, empirically observed rate", None)

    # H. Missing Core PCE (simulate a release delay: latest month's value is None).
    rows_h = [_synthetic_row(chg_3m=2.0, chg_6m=2.0, chg_12m=3.0, d=date(2024, 1, 1)),
              _synthetic_row(chg_3m=None, chg_6m=None, chg_12m=None, d=date(2024, 2, 1))]
    record("H", "Missing Core PCE (simulated release delay -- latest month unclassifiable)", None, {
        "candidate_A_states": [classify_candidate_a(r, 0.25) for r in rows_h],
        "note": "Latest month correctly returns None rather than reusing the prior month's state or imputing.",
    })

    # I. Missing Core CPI -- same structural behavior as H; documented once, not duplicated with a second synthetic series.
    record("I", "Missing Core CPI -- identical structural handling to case H (None propagates, never imputed)", None)

    # J. Missing one intermediate monthly observation.
    obs_j = [Observation(date(2024, 1, 1), 100.0), Observation(date(2024, 2, 1), None),
             Observation(date(2024, 3, 1), 101.0), Observation(date(2024, 4, 1), 102.0)]
    rows_j = compute_transformations(obs_j)
    record("J", "Missing one intermediate monthly observation", None, {
        "chg_1m_ann_by_month": [(r.date.isoformat(), r.chg_1m_ann) for r in rows_j],
        "note": "March's 1M change is None (Feb is missing); April's 1M change computes normally from March.",
    })

    # K. Negative inflation / deflation.
    row = _synthetic_row(chg_3m=-2.0, chg_6m=-1.0, chg_12m=0.5)
    record("K", "Negative inflation / deflation", row, {
        "inputs": asdict(row),
        "candidate_A_delta_0.25": classify_candidate_a(row, 0.25),
    })

    # L. Extremely large one-month price shock.
    obs_l = [Observation(date(2024, 1, 1), 100.0), Observation(date(2024, 2, 1), 110.0)]  # +10% in one month
    rows_l = compute_transformations(obs_l)
    record("L", "Extremely large one-month price shock (+10% MoM)", None, {
        "chg_1m_annualized": rows_l[1].chg_1m_ann,
        "note": "1M annualized correctly reflects the shock's full compounded magnitude; the study explicitly "
                "requires 1M never independently determine the canonical candidate state.",
    })

    # M. 3M = 2.01, 12M = 2.00 -- delta sensitivity.
    row = _synthetic_row(chg_3m=2.01, chg_6m=2.0, chg_12m=2.00)
    record("M", "3M=2.01, 12M=2.00 (delta sensitivity at a razor-thin margin)", row, {
        "inputs": asdict(row),
        "candidate_A_delta_0.00": classify_candidate_a(row, 0.00),
        "candidate_A_delta_0.10": classify_candidate_a(row, 0.10),
        "candidate_A_delta_0.25": classify_candidate_a(row, 0.25),
        "candidate_A_delta_0.50": classify_candidate_a(row, 0.50),
    })

    # N. Identical inputs run repeatedly.
    row = _synthetic_row(chg_3m=2.0, chg_6m=2.5, chg_12m=3.0)
    first = classify_candidate_a(row, 0.25)
    second = classify_candidate_a(row, 0.25)
    record("N", "Identical inputs run repeatedly", None, {
        "first_run": first, "second_run": second, "identical": first == second,
    })

    # O. Different latest periods across CPI and PCE -- this is an empirically real, current fact, not synthetic.
    record("O", "Different latest periods across CPI and PCE -- empirically true right now "
                "(see data_coverage.json: CPI's latest month is one month ahead of PCE's); "
                "latest_common_period() resolves to the earlier of the two, never comparing mismatched months", None)

    return cases


def main() -> None:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    all_obs = load_all()
    rows_by_series = build_rows(all_obs)

    coverage_rows, common_period = data_coverage_report(all_obs)
    _write_json("data_coverage.json", {"series": coverage_rows, "latest_common_period": common_period.isoformat() if common_period else None})

    state_series = all_candidate_state_series(rows_by_series)
    _write_csv("candidate_metrics.csv", metrics_report(state_series))

    _write_csv("cross_measure_agreement.csv", cross_measure_agreement_report(rows_by_series))

    _write_json("regime_analysis.json", regime_report(all_obs, rows_by_series))

    _write_csv("target_gap_headline_pce.csv", target_gap_report(rows_by_series))

    _write_json("adversarial_cases.json", adversarial_cases_report())

    print("Study complete. Outputs written to", OUTPUTS_DIR)


if __name__ == "__main__":
    main()
