import type {
  ComparisonStatus,
  InputComparison,
  InputUnit,
  NotComparableReason,
  NotReplayableReason,
  ReplayOutcome,
} from "../api/monitorHistory.types";
import { formatJobs } from "./laborFormat";

/**
 * Labels and presentation classes for point-in-time intelligence
 * history (Increment #32). Pure lookup tables over backend
 * vocabularies -- nothing here decides anything; every value being
 * labelled was classified server-side.
 *
 * THE DELIBERATE TOKEN CHOICE IN THIS FILE: replay status uses the
 * generic `feedback-*` family, NOT the `state-*` family.
 *
 * `globals.css`'s hard rule keeps those families disjoint because an
 * economic state is a classification, not a verdict -- "Cooling" is not
 * success. A replay outcome is the exact opposite kind of thing: it IS
 * a verdict, about MacroChipz's own integrity rather than about the
 * economy. "This recorded conclusion no longer reproduces from its own
 * inputs" is a genuine error, and dressing it in economic-state colors
 * would understate it. So the two families stay disjoint and each is
 * used for what it is for. Guarded by `historyLabels.test.ts`.
 */

export const REPLAY_OUTCOME_LABEL: Record<ReplayOutcome, string> = {
  MATCH: "Replay verified",
  MISMATCH: "Replay mismatch",
  NOT_REPLAYABLE: "Cannot verify",
};

/**
 * What each outcome actually means, in the user's terms -- never
 * database terms. Used for the accessible description and the
 * disclosure body, so the meaning never depends on the colour.
 */
export const REPLAY_OUTCOME_DESCRIPTION: Record<ReplayOutcome, string> = {
  MATCH: "Recalculating from the data available at the time reproduces this exact result.",
  MISMATCH:
    "Recalculating from the data available at the time does not reproduce this result. This is a data-integrity issue, not an economic signal.",
  NOT_REPLAYABLE: "There is not enough stored history to recalculate this result independently.",
};

export const REPLAY_OUTCOME_CLASSES: Record<ReplayOutcome, string> = {
  MATCH: "bg-feedback-success-subtle text-feedback-success ring-1 ring-inset ring-feedback-success-line",
  MISMATCH: "bg-feedback-error-subtle text-feedback-error ring-1 ring-inset ring-feedback-error-line",
  NOT_REPLAYABLE: "bg-feedback-warning-subtle text-feedback-warning ring-1 ring-inset ring-feedback-warning-line",
};

/** Why verification was impossible, in plain language. */
export const NOT_REPLAYABLE_REASON_COPY: Record<NotReplayableReason, string> = {
  UNKNOWN_RECORDED_RESULT: "The original result could not be found.",
  UNKNOWN_METHODOLOGY_VERSION: "This result used a methodology version MacroChipz no longer runs.",
  NO_VERSION_HISTORY_FOR_INPUTS: "MacroChipz has no stored history for the data this result used.",
  VERSION_HISTORY_STARTS_AFTER_CALCULATION:
    "MacroChipz only began tracking this data after the result was calculated.",
};

export const INPUT_COMPARISON_LABEL: Record<InputComparison, string> = {
  UNCHANGED: "Unchanged",
  REVISED: "Revised",
  ONLY_AVAILABLE_TODAY: "Added since",
  ONLY_AVAILABLE_THEN: "No longer available",
};

export const COMPARISON_STATUS_LABEL: Record<ComparisonStatus, string> = {
  IDENTICAL_INPUTS: "No data changes",
  INPUTS_CHANGED: "Data has changed",
  NOT_COMPARABLE: "Cannot compare",
};

export const NOT_COMPARABLE_REASON_COPY: Record<NotComparableReason, string> = {
  REPLAY_UNAVAILABLE:
    "MacroChipz cannot reconstruct what it knew at the time, so there is nothing to compare today's data against.",
  METHODOLOGY_VERSION_DIFFERS:
    "This result used a different methodology version. Re-running today's methodology would answer a different question, so no comparison is shown.",
};

/** `NEW` / `REVISED` as release processing classified them. */
export function observationChangeLabel(changeType: string): string {
  if (changeType === "NEW") return "New observation";
  if (changeType === "REVISED") return "Revised observation";
  return changeType;
}

/**
 * Format a historical input value in the unit the BACKEND declared.
 * The unit is never inferred from the series id -- that would be
 * re-deriving a methodology decision in React.
 */
export function formatInputValue(value: number | null, unit: InputUnit): string {
  if (value === null) return "Not available";
  if (unit === "JOBS") return formatJobs(value);
  if (unit === "PERCENT") return `${value.toFixed(1)}%`;
  return value.toFixed(3);
}
