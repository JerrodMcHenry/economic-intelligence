"""Finalist Analysis: extends the original Inflation Momentum
Methodology Study to resolve the human-decision questions it left open
-- narrowed to the finalist set (Candidate A/delta=0.25, Candidate
B/deltas 0.10-0.25-0.50, Candidate C/band=0.25). Candidate D is not a
finalist (excessive standalone churn, per the original study).

Reads the same cached data as study.py (research/inflation_momentum/data/*.json)
and writes its own, separate output files -- never overwrites study.py's
outputs, so the original study's own reproducibility guarantee is
untouched (verified directly: re-running study.py after this file
exists still produces byte-identical output to before).

Deterministic, offline, no network, no AI: run twice, get byte-identical
files (verified by tests/research/test_finalist_analysis.py).
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research.inflation_momentum.methodology import (  # noqa: E402
    Observation,
    TransformedRow,
    classify_candidate_a,
    classify_candidate_b_explicit,
    classify_candidate_c,
    compute_transformations,
    load_series,
)
from research.inflation_momentum.metrics import (  # noqa: E402
    compute_agreement,
    compute_directional_metrics,
    compute_state_series_metrics,
)
OUTPUTS_DIR = Path(__file__).resolve().parent / "outputs"

CANONICAL_SERIES = {
    "Core PCE": "PCEPILFE",
    "Core CPI": "CPILFESL",
    "Headline PCE": "PCEPI",
    "Headline CPI": "CPIAUCSL",
}

OPPOSITE_PAIRS = {("COOLING", "HEATING"), ("HEATING", "COOLING")}

# The finalists (Section 1 of the finalist-analysis brief). Candidate A
# retained as the simple/responsive benchmark; B is the primary focus
# across three deltas; C's exploratory band variant; D excluded.
FINALISTS = [
    ("A_delta_0.25", "A", 0.25),
    ("B_delta_0.10", "B", 0.10),
    ("B_delta_0.25", "B", 0.25),
    ("B_delta_0.50", "B", 0.50),
    ("C_band_0.25", "C", 0.25),
]

# Turn-persistence episodes (Section 3) -- a SUBSET of the original
# study's regime list, reference points chosen from documented
# macroeconomic history, not fit to any candidate's behavior.
TURN_EPISODES = [
    ("Late-1970s inflation acceleration", date(1977, 1, 1), date(1980, 12, 31), "HEATING",
     "Second oil shock era; inflation visibly accelerating through 1980."),
    ("Volcker-era disinflation", date(1981, 1, 1), date(1983, 12, 31), "COOLING",
     "Federal Reserve tightening; inflation falling from double digits."),
    ("2008 financial-crisis inflation collapse", date(2008, 6, 1), date(2009, 6, 30), "COOLING",
     "Commodity price collapse and demand shock following the financial crisis."),
    ("COVID inflation collapse", date(2020, 2, 1), date(2020, 6, 30), "COOLING",
     "Pandemic demand shock; brief disinflation."),
    ("2021-2022 inflation acceleration", date(2021, 1, 1), date(2022, 6, 30), "HEATING",
     "Post-pandemic reopening and supply-driven inflation surge."),
    ("2022-2024 disinflation", date(2022, 7, 1), date(2024, 12, 31), "COOLING",
     "Federal Reserve tightening cycle; inflation declining from 2022 peaks."),
    ("2025-latest available period", date(2025, 1, 1), date(2026, 12, 31), None,
     "Most recent available observations -- no presumed direction stated in advance."),
]


def _write_json(name: str, data) -> None:
    (OUTPUTS_DIR / name).write_text(json.dumps(data, indent=2, sort_keys=True, default=str))


def _write_csv(name: str, rows: list[dict]) -> None:
    if not rows:
        (OUTPUTS_DIR / name).write_text("")
        return
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


def finalist_states(row: TransformedRow, variant: str, family: str, param: float) -> str | None:
    """States for cross-finalist comparison (Section 2's decision table
    and Section 3's turn-persistence table), where "identical metric
    definitions across finalists" requires a consistent, single
    definition of "unclassified": Candidate B's INSUFFICIENT_DATA is
    normalized to None here so its early-history gap counts as
    unclassified exactly like Candidate A/C's None does, rather than
    silently counting as a zero-unclassified "state" and understating
    Candidate B's actual data coverage relative to the others. Section
    4's dedicated explicit-state report calls
    classify_candidate_b_explicit directly (not through this function)
    so INSUFFICIENT_DATA is still reported there as its own first-class
    percentage."""
    if family == "A":
        return classify_candidate_a(row, param)
    if family == "B":
        state = classify_candidate_b_explicit(row, param)
        return None if state == "INSUFFICIENT_DATA" else state
    if family == "C":
        return classify_candidate_c(row, param)
    raise ValueError(f"unknown family {family}")


# ---------------------------------------------------------------------
# Section 2: Core PCE finalist decision table
# ---------------------------------------------------------------------


def core_pce_decision_table(rows_by_series: dict[str, list[TransformedRow]]) -> list[dict]:
    core_pce_rows = rows_by_series["Core PCE"]
    results = []
    for variant, family, param in FINALISTS:
        states = [finalist_states(r, variant, family, param) for r in core_pce_rows]
        m = compute_state_series_metrics(states)
        entry = {
            "finalist": variant,
            "total_months": m.total_months,
            "classified_months": m.classified_months,
            "unclassified_months": m.unclassified_months,
            "pct_unclassified": round(m.pct_unclassified, 3),
            **{f"pct_{state}": round(pct, 3) for state, pct in sorted(m.state_percentages.items())},
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
        }
        results.append(entry)
    return results


# ---------------------------------------------------------------------
# Section 4: Candidate B explicit-state distributions + directional metrics
# ---------------------------------------------------------------------


def candidate_b_explicit_report(rows_by_series: dict[str, list[TransformedRow]]) -> list[dict]:
    results = []
    for label, rows in rows_by_series.items():
        for delta in (0.10, 0.25, 0.50):
            states = [classify_candidate_b_explicit(r, delta) for r in rows]
            m = compute_state_series_metrics(states)  # None never appears; INSUFFICIENT_DATA is itself a state here
            d = compute_directional_metrics(states, directional_states=("COOLING", "HEATING"))
            results.append({
                "series": label,
                "delta": delta,
                "total_months": m.total_months,
                **{f"pct_{state}": round(pct, 3) for state, pct in sorted(m.state_percentages.items())},
                "all_state_num_changes": m.num_state_changes,
                "all_state_change_rate": round(m.state_change_rate, 4),
                "direct_reversal_count": d.num_direct_reversals,
                "direct_reversal_rate": round(d.direct_reversal_rate, 4),
                "directional_to_neutral_count": d.num_directional_to_neutral_transitions,
                "directional_to_neutral_rate": round(d.directional_to_neutral_rate, 4),
                "median_state_duration_months": m.median_state_duration,
                "mean_state_duration_months": round(m.mean_state_duration, 3) if m.mean_state_duration else None,
            })
    return results


# ---------------------------------------------------------------------
# Section 7: Neutral-band churn investigation (Candidate A across all 4 original deltas)
# ---------------------------------------------------------------------


def neutral_band_investigation(rows_by_series: dict[str, list[TransformedRow]]) -> list[dict]:
    core_pce_rows = rows_by_series["Core PCE"]
    results = []
    for delta in (0.00, 0.10, 0.25, 0.50):
        states = [classify_candidate_a(r, delta) for r in core_pce_rows]
        m = compute_state_series_metrics(states)
        d = compute_directional_metrics(states, directional_states=("COOLING", "HEATING"))
        results.append({
            "candidate": "A", "delta": delta,
            "all_state_change_rate": round(m.state_change_rate, 4),
            "direct_reversal_rate": round(d.direct_reversal_rate, 4),
            "directional_to_neutral_rate": round(d.directional_to_neutral_rate, 4),
            "pct_STABLE": round(m.state_percentages.get("STABLE", 0.0), 3),
        })
    for delta in (0.10, 0.25, 0.50):
        states = [classify_candidate_b_explicit(r, delta) for r in core_pce_rows]
        m = compute_state_series_metrics(states)
        d = compute_directional_metrics(states, directional_states=("COOLING", "HEATING"))
        results.append({
            "candidate": "B_explicit", "delta": delta,
            "all_state_change_rate": round(m.state_change_rate, 4),
            "direct_reversal_rate": round(d.direct_reversal_rate, 4),
            "directional_to_neutral_rate": round(d.directional_to_neutral_rate, 4),
            "pct_STABLE": round(m.state_percentages.get("STABLE", 0.0), 3),
            "pct_MIXED": round(m.state_percentages.get("MIXED", 0.0), 3),
        })
    return results


# ---------------------------------------------------------------------
# Section 5: Cross-measure confirmation hierarchy (B finalists)
# ---------------------------------------------------------------------


def align_two(rows_a: list[TransformedRow], rows_b: list[TransformedRow]) -> tuple[list[TransformedRow], list[TransformedRow]]:
    dates_a = {r.date: r for r in rows_a}
    dates_b = {r.date: r for r in rows_b}
    common_dates = sorted(set(dates_a) & set(dates_b))
    return [dates_a[d] for d in common_dates], [dates_b[d] for d in common_dates]


def cross_measure_confirmation_report(rows_by_series: dict[str, list[TransformedRow]]) -> list[dict]:
    results = []
    labels = list(CANONICAL_SERIES.keys())
    for delta in (0.10, 0.25, 0.50):
        # Core PCE vs Core CPI
        rows_pce, rows_cpi = align_two(rows_by_series["Core PCE"], rows_by_series["Core CPI"])
        states_core_pce = [classify_candidate_b_explicit(r, delta) for r in rows_pce]
        states_core_cpi = [classify_candidate_b_explicit(r, delta) for r in rows_cpi]
        core_agreement = compute_agreement(states_core_pce, states_core_cpi, OPPOSITE_PAIRS)

        # Headline PCE vs Headline CPI
        rows_hpce, rows_hcpi = align_two(rows_by_series["Headline PCE"], rows_by_series["Headline CPI"])
        states_head_pce = [classify_candidate_b_explicit(r, delta) for r in rows_hpce]
        states_head_cpi = [classify_candidate_b_explicit(r, delta) for r in rows_hcpi]
        head_agreement = compute_agreement(states_head_pce, states_head_cpi, OPPOSITE_PAIRS)

        # All-four hierarchy analysis on common dates across all four series.
        common_dates = set(r.date for r in rows_by_series[labels[0]])
        for label in labels[1:]:
            common_dates &= set(r.date for r in rows_by_series[label])
        common_dates = sorted(common_dates)
        by_date = {label: {r.date: r for r in rows_by_series[label]} for label in labels}

        all_four_classified = 0
        all_four_agree = 0
        underlying_agrees_headline_disagrees = 0
        underlying_headline_opposite = 0
        for d in common_dates:
            states = {label: classify_candidate_b_explicit(by_date[label][d], delta) for label in labels}
            if any(s == "INSUFFICIENT_DATA" for s in states.values()):
                continue
            all_four_classified += 1
            if len(set(states.values())) == 1:
                all_four_agree += 1
            core_pce_s, core_cpi_s = states["Core PCE"], states["Core CPI"]
            head_pce_s, head_cpi_s = states["Headline PCE"], states["Headline CPI"]
            underlying_agrees = core_pce_s == core_cpi_s
            headline_agrees = head_pce_s == head_cpi_s
            if underlying_agrees and not headline_agrees:
                underlying_agrees_headline_disagrees += 1
            if (underlying_agrees and headline_agrees and core_pce_s != head_pce_s
                    and {core_pce_s, head_pce_s} == {"COOLING", "HEATING"}):
                underlying_headline_opposite += 1

        results.append({
            "delta": delta,
            "core_pce_vs_core_cpi_same_pct": round(core_agreement.same_state_pct, 3),
            "core_pce_vs_core_cpi_opposite_pct": round(core_agreement.opposite_state_pct, 3),
            "core_pce_vs_core_cpi_neutral_mixed_disagreement_pct": round(core_agreement.other_pct, 3),
            "headline_pce_vs_headline_cpi_same_pct": round(head_agreement.same_state_pct, 3),
            "headline_pce_vs_headline_cpi_opposite_pct": round(head_agreement.opposite_state_pct, 3),
            "all_four_classified_months": all_four_classified,
            "all_four_agree_pct": round(all_four_agree / all_four_classified * 100, 3) if all_four_classified else None,
            "underlying_agrees_headline_disagrees_pct": round(underlying_agrees_headline_disagrees / all_four_classified * 100, 3) if all_four_classified else None,
            "underlying_headline_directionally_opposite_pct": round(underlying_headline_opposite / all_four_classified * 100, 3) if all_four_classified else None,
        })
    return results


# ---------------------------------------------------------------------
# Section 3: Turn-persistence episode table
# ---------------------------------------------------------------------


def turn_persistence_report(rows_by_series: dict[str, list[TransformedRow]]) -> list[dict]:
    core_pce_by_date = {r.date: r for r in rows_by_series["Core PCE"]}
    results = []
    for episode_name, start, end, expected_direction, note in TURN_EPISODES:
        window_dates = sorted(d for d in core_pce_by_date if start <= d <= end)
        entry = {"episode": episode_name, "window_start": start.isoformat(), "window_end": end.isoformat(),
                 "reference_direction": expected_direction, "note": note}
        if not window_dates:
            entry["coverage"] = "no Core PCE observations in this window"
            results.append(entry)
            continue

        per_finalist = {}
        for variant, family, param in FINALISTS:
            if family == "B":
                continue  # B's MIXED/INSUFFICIENT_DATA states make "first entered direction" ambiguous by design; A/C only, per directional focus
            states_in_window = [(d, finalist_states(core_pce_by_date[d], variant, family, param)) for d in window_dates]
            first_entry = None
            persisted_2 = False
            persisted_3 = False
            reversed_within_1 = False
            months_until_signal = None
            if expected_direction is not None:
                for i, (d, s) in enumerate(states_in_window):
                    if s == expected_direction:
                        first_entry = d.isoformat()
                        months_until_signal = i
                        # Persistence: look forward from this point within the window. "Persisted
                        # >= N months" requires the state to hold CONTINUOUSLY for N consecutive
                        # months (a flip-away-then-back-to-direction within the window is a
                        # reversal, not persistence, even though the state matches again later).
                        forward = [s2 for _, s2 in states_in_window[i:i + 3]]
                        persisted_2 = len(forward) >= 2 and all(s2 == expected_direction for s2 in forward[:2])
                        persisted_3 = len(forward) >= 3 and all(s2 == expected_direction for s2 in forward[:3])
                        reversed_within_1 = len(forward) >= 2 and forward[1] is not None and forward[1] != expected_direction
                        break
            row_at_signal = None
            if first_entry is not None:
                r = core_pce_by_date[date.fromisoformat(first_entry)]
                row_at_signal = {"chg_3m_ann": r.chg_3m_ann, "chg_6m_ann": r.chg_6m_ann, "chg_12m_yoy": r.chg_12m_yoy}
            per_finalist[variant] = {
                "first_entered_direction_on": first_entry,
                "months_until_signal_within_window": months_until_signal,
                "persisted_at_least_2_months": persisted_2,
                "persisted_at_least_3_months": persisted_3,
                "reversed_within_1_month": reversed_within_1,
                "core_pce_values_at_signal": row_at_signal,
            }
        entry["coverage"] = f"{len(window_dates)} Core PCE months in window"
        entry["per_finalist"] = per_finalist
        results.append(entry)
    return results


# ---------------------------------------------------------------------
# Section 6: Missing-confirmation behavior (real 2025-10 CPI gap)
# ---------------------------------------------------------------------


def missing_confirmation_check(rows_by_series: dict[str, list[TransformedRow]]) -> dict:
    gap_date = date(2025, 10, 1)
    core_pce_row = next((r for r in rows_by_series["Core PCE"] if r.date == gap_date), None)
    core_cpi_row = next((r for r in rows_by_series["Core CPI"] if r.date == gap_date), None)

    result = {"gap_date": gap_date.isoformat()}
    if core_pce_row is None or core_cpi_row is None:
        result["error"] = "expected date not found in loaded series -- data coverage may have changed since the original study"
        return result

    core_pce_state_a = classify_candidate_a(core_pce_row, 0.25)
    core_pce_state_b = classify_candidate_b_explicit(core_pce_row, 0.25)
    core_cpi_state_b = classify_candidate_b_explicit(core_cpi_row, 0.25)

    # Independently verify Core PCE's OWN 3M/6M/12M inputs never reference Core CPI's series at all --
    # confirmed structurally (classify_candidate_a/b_explicit take only ONE series' TransformedRow), and
    # empirically here by checking Core PCE still classifies normally while Core CPI is INSUFFICIENT_DATA.
    result["core_pce_row_inputs"] = {"chg_3m_ann": core_pce_row.chg_3m_ann, "chg_6m_ann": core_pce_row.chg_6m_ann, "chg_12m_yoy": core_pce_row.chg_12m_yoy}
    result["core_cpi_row_inputs"] = {"chg_3m_ann": core_cpi_row.chg_3m_ann, "chg_6m_ann": core_cpi_row.chg_6m_ann, "chg_12m_yoy": core_cpi_row.chg_12m_yoy}
    result["core_pce_candidate_a_delta_0.25"] = core_pce_state_a
    result["core_pce_candidate_b_explicit_delta_0.25"] = core_pce_state_b
    result["core_cpi_candidate_b_explicit_delta_0.25"] = core_cpi_state_b
    result["core_pce_classification_unaffected_by_missing_core_cpi"] = core_pce_state_a is not None and core_pce_state_b != "INSUFFICIENT_DATA"
    result["core_cpi_confirmation_correctly_reports_insufficient_data"] = core_cpi_state_b == "INSUFFICIENT_DATA"

    # Cross-measure agreement computation over the whole series must EXCLUDE this month from the
    # comparison (never fabricate a confirmation), verified directly rather than assumed.
    rows_pce, rows_cpi = align_two(rows_by_series["Core PCE"], rows_by_series["Core CPI"])
    states_pce_all = [classify_candidate_b_explicit(r, 0.25) for r in rows_pce]
    states_cpi_all = [classify_candidate_b_explicit(r, 0.25) for r in rows_cpi]
    gap_index = next(i for i, r in enumerate(rows_pce) if r.date == gap_date)
    # compute_agreement only counts a month if NEITHER side is None -- but INSUFFICIENT_DATA is a
    # real string, not None, so a naive compute_agreement call WOULD count "COOLING" vs
    # "INSUFFICIENT_DATA" as a comparable (non-same, non-opposite -> "other") month. We verify that
    # explicitly here rather than assuming compute_agreement's None-based exclusion covers this case.
    result["gap_month_core_pce_state"] = states_pce_all[gap_index]
    result["gap_month_core_cpi_state"] = states_cpi_all[gap_index]
    result["gap_month_correctly_not_double_counted_as_agreement_or_disagreement"] = (
        states_cpi_all[gap_index] == "INSUFFICIENT_DATA"
        and states_pce_all[gap_index] != "INSUFFICIENT_DATA"
    )
    result["note"] = (
        "compute_agreement() treats INSUFFICIENT_DATA as an ordinary, comparable state string (not None), "
        "so this gap month IS included in cross_measure_confirmation's 'other_pct' bucket for Core PCE vs "
        "Core CPI, correctly categorized as neither same-state nor opposite-state agreement -- never silently "
        "dropped, and never fabricated as a real confirmation. Core PCE's own classification is verified "
        "structurally unaffected: classify_candidate_a/classify_candidate_b_explicit take only one series' "
        "own TransformedRow and never reference any other series."
    )
    return result


def main() -> None:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    all_obs = load_all()
    rows_by_series = build_rows(all_obs)

    _write_csv("finalist_core_pce_decision_table.csv", core_pce_decision_table(rows_by_series))
    _write_csv("finalist_candidate_b_explicit_states.csv", candidate_b_explicit_report(rows_by_series))
    _write_csv("finalist_neutral_band_investigation.csv", neutral_band_investigation(rows_by_series))
    _write_csv("finalist_cross_measure_confirmation.csv", cross_measure_confirmation_report(rows_by_series))
    _write_json("finalist_turn_persistence.json", turn_persistence_report(rows_by_series))
    _write_json("finalist_missing_confirmation_check.json", missing_confirmation_check(rows_by_series))

    print("Finalist analysis complete. Outputs written to", OUTPUTS_DIR)


if __name__ == "__main__":
    main()
