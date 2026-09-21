/**
 * Relate V1 — deterministic PRESENTATION composition of already-canonical
 * facts, frozen by docs/product/relate-composition-v1.md. This module
 * performs COMPOSITION only, never INFERENCE (that document's own §2
 * boundary): every sentence below combines values already present on
 * `InflationMonitorResult`/`LaborMonitorResult` verbatim, through the
 * SAME label functions already used everywhere else in the product
 * (`inflationStateLabel`/`laborStateLabel`/`employmentStateLabel`/
 * `unemploymentStateLabel`), and asserts no new economic meaning about
 * their combination. No backend import, no network access, no economic
 * calculation, no threshold, no score, no AI. This is an ordinary
 * software presentation module, not an economic methodology -- unlike
 * `inflation_v1.0`/`labor_v1.0`, it carries no versioned methodology
 * identifier of its own (see the frozen contract's own §29).
 */
import type { InflationState } from "../api/inflation.types";
import type { EmploymentState, LaborState, UnemploymentTrendState } from "../api/labor.types";
import { formatPeriod } from "./format";
import { inflationStateLabel } from "./inflationLabels";
import { employmentStateLabel, laborStateLabel, unemploymentStateLabel } from "./laborLabels";

export type MonitorRelateComposition =
  | { kind: "same-period"; sentence: string }
  | { kind: "different-period"; sentence: string }
  | { kind: "inflation-insufficient"; sentence: string }
  | { kind: "labor-insufficient"; sentence: string }
  | { kind: "both-insufficient"; sentence: string };

export type LaborRelateComposition =
  | { kind: "composed"; sentence: string }
  | { kind: "employment-insufficient"; sentence: string }
  | { kind: "unemployment-insufficient"; sentence: string };

/**
 * Composes Inflation's and Labor's own already-canonical top-level
 * states into one honest, period-aware sentence -- frozen contract
 * §7/§8/§9. Branches on STATE, never on period presence alone
 * (`docs/product/relate-composition-v1.md` §9: a `null` period always
 * co-occurs with `INSUFFICIENT_DATA` in the backend's own domain code,
 * but the reverse doesn't always hold, so this function additionally
 * treats a null period as insufficient even if a future backend change
 * ever decoupled the two -- defensive, not an assumption it relies on).
 *
 * "while" is used ONLY when both periods are the exact same ISO date
 * (§7) -- it genuinely implies simultaneity there. Any period mismatch
 * uses two independent, explicitly period-stamped sentences (§8),
 * never a word that could imply the two facts are contemporaneous.
 *
 * There is deliberately no branch here that reports a combined
 * "Inflation+Labor" conclusion the way `composeLaborComponents` below
 * reports `LaborState` -- no such canonical combined value exists for
 * Inflation and Labor (unlike Employment+Unemployment -> LaborState),
 * and inventing one would be exactly the forbidden regime label this
 * module must never produce (§19's own explicit asymmetry).
 */
export function composeMonitorRelation(
  inflation: { state: InflationState; period: string | null },
  labor: { state: LaborState; period: string | null },
): MonitorRelateComposition {
  const inflationSufficient = inflation.state !== "INSUFFICIENT_DATA" && inflation.period !== null;
  const laborSufficient = labor.state !== "INSUFFICIENT_DATA" && labor.period !== null;

  if (!inflationSufficient && !laborSufficient) {
    return {
      kind: "both-insufficient",
      sentence: "Not enough data is currently available to describe how Inflation and Jobs relate.",
    };
  }

  if (!inflationSufficient) {
    return {
      kind: "inflation-insufficient",
      sentence: `Jobs is ${laborStateLabel(labor.state)} as of ${formatPeriod(labor.period)}. Inflation does not currently have enough data to classify its state.`,
    };
  }

  if (!laborSufficient) {
    return {
      kind: "labor-insufficient",
      sentence: `Inflation is ${inflationStateLabel(inflation.state)} as of ${formatPeriod(inflation.period)}. Jobs does not currently have enough data to classify its state.`,
    };
  }

  if (inflation.period === labor.period) {
    return {
      kind: "same-period",
      sentence: `As of ${formatPeriod(inflation.period)}, Inflation is ${inflationStateLabel(inflation.state)} while Jobs is ${laborStateLabel(labor.state)}.`,
    };
  }

  return {
    kind: "different-period",
    sentence: `Inflation is ${inflationStateLabel(inflation.state)} as of ${formatPeriod(inflation.period)}. Jobs is ${laborStateLabel(labor.state)} as of ${formatPeriod(labor.period)}.`,
  };
}

/**
 * Composes Employment's and Unemployment's own already-canonical
 * states, plus a verbatim report of the top-level `LaborState` they
 * feed into -- frozen contract §18/§19/§20/§21. `laborState` is a
 * plain input, read directly from `LaborMonitorResult.state`; this
 * function contains no combination logic of its own and never
 * recomputes, re-derives, or re-implements `combine_labor_state`'s own
 * existing table (`app/domain/labor.py`) -- the one canonical source of
 * that value remains the backend, exclusively.
 *
 * Employment and Unemployment are guaranteed to share one evaluation
 * period within a single `LaborMonitorResult` (verified directly in
 * `app/domain/labor.py`'s `compute_employment_result`/
 * `compute_unemployment_result`/`compute_labor_monitor_result_at`, all
 * three taking/passing the identical explicit period parameter) -- so,
 * unlike `composeMonitorRelation`, this function never needs to reason
 * about period alignment at all.
 */
export function composeLaborComponents(
  employment: EmploymentState,
  unemployment: UnemploymentTrendState,
  laborState: LaborState,
): LaborRelateComposition {
  if (employment === "INSUFFICIENT_DATA") {
    return {
      kind: "employment-insufficient",
      sentence: "Employment does not currently have enough data to classify its state.",
    };
  }

  if (unemployment === "INSUFFICIENT_DATA") {
    return {
      kind: "unemployment-insufficient",
      sentence: "Unemployment does not currently have enough data to classify its state.",
    };
  }

  // A top-level LaborState of INSUFFICIENT_DATA while both components
  // are sufficient is not reachable -- combine_labor_state itself
  // returns INSUFFICIENT_DATA if, and only if, either input is (see
  // app/domain/labor.py's own combine_labor_state) -- so no separate
  // branch is needed here; both prior guards above already cover every
  // path that could produce it.
  return {
    kind: "composed",
    sentence: `Employment is ${employmentStateLabel(employment)} and Unemployment is ${unemploymentStateLabel(unemployment)}. Together, MacroChipz classifies Jobs as ${laborStateLabel(laborState)}.`,
  };
}
