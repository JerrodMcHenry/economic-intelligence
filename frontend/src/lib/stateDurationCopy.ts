/**
 * Pure, typed presentation copy for State Duration V1 -- converts an
 * already-canonical `StateDurationResult` (app/models/state_duration.py,
 * frozen and normative in docs/product/state-duration-v1.md §37) into
 * the exact frozen display strings. This module calculates nothing: it
 * never walks months, counts duration, derives a boundary type, or
 * infers a transition -- every number/period/state it renders is read
 * directly off the response object, and it performs plain-English
 * string templating only (pluralizing "month"/"months", formatting a
 * period via the existing `formatPeriod` helper).
 *
 * `stateLabel`/`previousStateLabel` are supplied by the CALLER (each
 * monitor's own `inflationStateLabel`/`laborStateLabel`, already
 * resolved to a plain string before this function is called) -- this
 * module has no series/monitor knowledge of its own and never imports
 * either label map, matching the same "zero economic content" boundary
 * the backend's own `app.domain.state_duration.evaluate_state_duration`
 * observes (see that module's own docstring).
 *
 * "Latest-revised reconstruction:" is the load-bearing prefix (§1/§51)
 * -- every non-error, non-CURRENT_INSUFFICIENT sentence below carries
 * it, never omitted for brevity, and no sentence here ever drops the
 * reconstruction qualifier the way "EI has been X since..." would.
 */
import type { StateDurationResult } from "../api/stateDuration.types";
import { formatPeriod } from "./format";

export type StateDurationCopyKind = "EXACT" | "DATA_BOUNDED" | "LOOKBACK_BOUNDED" | "CURRENT_INSUFFICIENT";

export interface StateDurationCopy {
  kind: StateDurationCopyKind;
  headline: string;
  /** EXACT-only, and only when the backend actually populated
   * `previous_state`/`previous_period` -- never fabricated for
   * DATA_BOUNDED/LOOKBACK_BOUNDED (frozen contract §22). */
  previousStateNote: string | null;
}

// §37D -- frozen verbatim. Never treated as an API/infrastructure error.
export const CURRENT_INSUFFICIENT_COPY = "Historical state duration is unavailable because the current state has insufficient data.";

function monthsPhrase(durationMonths: number): string {
  return durationMonths === 1 ? "1 consecutive month" : `${durationMonths} consecutive months`;
}

// §37A -- frozen template: "Latest-revised reconstruction: {State} for
// {N} consecutive month(s), since {Month Year}." `earliest_confirmed_period`
// is the true start here (boundary_type is EXACT) -- never `previous_period`.
function exactHeadline(stateLabel: string, durationMonths: number, earliestConfirmedPeriod: string): string {
  return `Latest-revised reconstruction: ${stateLabel} for ${monthsPhrase(durationMonths)}, since ${formatPeriod(earliestConfirmedPeriod)}.`;
}

// §37B -- frozen template: "... for at least {N} consecutive month(s)."
// A lower bound, never implying N is the true duration.
function dataBoundedHeadline(stateLabel: string, durationMonths: number): string {
  return `Latest-revised reconstruction: ${stateLabel} for at least ${monthsPhrase(durationMonths)}.`;
}

// §37C -- frozen template, same shape as §37B today but kept as a
// SEPARATE function (frozen contract §42: "two distinct copy strings,
// never merged into one generic 'lower bound' string, since the
// reason differs and precision matters") -- DATA_BOUNDED and
// LOOKBACK_BOUNDED must stay independently modifiable, never one
// shared branch a future contract change could silently affect both
// at once.
function lookbackBoundedHeadline(stateLabel: string, durationMonths: number): string {
  return `Latest-revised reconstruction: ${stateLabel} for at least ${monthsPhrase(durationMonths)}.`;
}

/**
 * `result.status === "AVAILABLE"` callers must supply `stateLabel`
 * (their own monitor's label for `result.state`) and, when
 * `result.previous_state` is non-null, `previousStateLabel` (the same
 * label function applied to `previous_state`) -- `null` otherwise.
 * `result.status === "CURRENT_INSUFFICIENT"` ignores both.
 */
export function buildStateDurationCopy(
  result: StateDurationResult,
  stateLabel: string,
  previousStateLabel: string | null,
): StateDurationCopy {
  if (result.status === "CURRENT_INSUFFICIENT") {
    return { kind: "CURRENT_INSUFFICIENT", headline: CURRENT_INSUFFICIENT_COPY, previousStateNote: null };
  }

  switch (result.boundary_type) {
    case "EXACT": {
      const previousStateNote =
        result.previous_state !== null && result.previous_period !== null && previousStateLabel !== null
          ? `Previously ${previousStateLabel}, as of ${formatPeriod(result.previous_period)}.`
          : null;
      return {
        kind: "EXACT",
        headline: exactHeadline(stateLabel, result.duration_months, result.earliest_confirmed_period),
        previousStateNote,
      };
    }
    case "DATA_BOUNDED":
      return { kind: "DATA_BOUNDED", headline: dataBoundedHeadline(stateLabel, result.duration_months), previousStateNote: null };
    case "LOOKBACK_BOUNDED":
      return {
        kind: "LOOKBACK_BOUNDED",
        headline: lookbackBoundedHeadline(stateLabel, result.duration_months),
        previousStateNote: null,
      };
    default: {
      // Exhaustiveness guard (frozen contract's own #24D scope, §20):
      // an unrecognized future `boundary_type` must never silently
      // render misleading historical copy -- fail loudly instead of
      // falling through to an "exact"-shaped default.
      const exhaustive: never = result.boundary_type;
      throw new Error(`Unknown state-duration boundary_type: ${String(exhaustive)}`);
    }
  }
}
