/**
 * Human-readable labels and visual "tone" for values the backend has
 * already classified. These functions map one already-canonical value
 * to display text/styling -- they never inspect a metric, compare two
 * values, or decide which state/relationship applies. `INSUFFICIENT_DATA`
 * and `UNAVAILABLE` always map to the muted "unavailable" tone, never a
 * direction, per the frozen contract's own requirement that missing
 * evidence must never look like an economic conclusion.
 */
import type { ChangeComponent, ConfirmationRelationship, InflationState } from "../api/inflation.types";

export type Tone = "cool" | "neutral" | "warm" | "caution" | "unavailable";

export const TONE_CLASSES: Record<Tone, string> = {
  cool: "bg-sky-50 text-sky-700 ring-1 ring-inset ring-sky-600/20",
  neutral: "bg-neutral-100 text-neutral-700 ring-1 ring-inset ring-neutral-500/20",
  warm: "bg-orange-50 text-orange-700 ring-1 ring-inset ring-orange-600/20",
  caution: "bg-amber-50 text-amber-800 ring-1 ring-inset ring-amber-600/20",
  unavailable: "bg-neutral-50 text-neutral-400 ring-1 ring-inset ring-neutral-300",
};

/** Same five tones as TONE_CLASSES, as plain text color only -- for
 * headline sentences that need tone reinforcement without a pill. */
export const TONE_TEXT_CLASSES: Record<Tone, string> = {
  cool: "text-sky-700",
  neutral: "text-neutral-700",
  warm: "text-orange-700",
  caution: "text-amber-800",
  unavailable: "text-neutral-400",
};

/** Same five tones, as a quiet left-border accent color for grouping a
 * block of related content (e.g. one What Changed subsection). */
export const TONE_BORDER_CLASSES: Record<Tone, string> = {
  cool: "border-sky-300",
  neutral: "border-neutral-300",
  warm: "border-orange-300",
  caution: "border-amber-300",
  unavailable: "border-neutral-200",
};

const INFLATION_STATE_LABELS: Record<InflationState, string> = {
  COOLING: "Cooling",
  STABLE: "Stable",
  HEATING: "Heating",
  MIXED: "Mixed",
  INSUFFICIENT_DATA: "Insufficient data",
};

const INFLATION_STATE_TONE: Record<InflationState, Tone> = {
  COOLING: "cool",
  STABLE: "neutral",
  HEATING: "warm",
  MIXED: "caution",
  INSUFFICIENT_DATA: "unavailable",
};

export function inflationStateLabel(state: InflationState): string {
  return INFLATION_STATE_LABELS[state];
}

export function inflationStateTone(state: InflationState): Tone {
  return INFLATION_STATE_TONE[state];
}

const RELATIONSHIP_LABELS: Record<ConfirmationRelationship, string> = {
  CONFIRMS: "Confirms",
  DIVERGES: "Diverges",
  INCONCLUSIVE: "Inconclusive",
  UNAVAILABLE: "Unavailable",
};

const RELATIONSHIP_TONE: Record<ConfirmationRelationship, Tone> = {
  CONFIRMS: "neutral",
  DIVERGES: "caution",
  INCONCLUSIVE: "neutral",
  UNAVAILABLE: "unavailable",
};

export function confirmationRelationshipLabel(relationship: ConfirmationRelationship): string {
  return RELATIONSHIP_LABELS[relationship];
}

export function confirmationRelationshipTone(relationship: ConfirmationRelationship): Tone {
  return RELATIONSHIP_TONE[relationship];
}

export const CHANGE_COMPONENT_LABELS: Record<ChangeComponent, string> = {
  PRIMARY_MOMENTUM: "Core PCE",
  CONFIRMATION: "Confirmation",
  TARGET: "Target",
  HEADLINE_PCE: "Headline PCE",
  HEADLINE_CPI: "Headline CPI",
};

export const CHANGE_FIELD_LABELS: Record<string, string> = {
  state: "State",
  relationship: "Relationship",
  r_1m_annualized: "1M annualized",
  r_3m_annualized: "3M annualized",
  r_6m_annualized: "6M annualized",
  r_12m: "12M",
  headline_pce_yoy: "Headline PCE YoY",
  target_gap_pp: "Target gap",
};

export function changeFieldLabel(field: string): string {
  return CHANGE_FIELD_LABELS[field] ?? field;
}

/**
 * `ChangeEvent.previous_value`/`current_value` for a "state" or
 * "relationship" field arrive as the raw enum string (the backend
 * doesn't re-type them per-field). These look the value up in the same
 * label maps above when it's a recognized state/relationship, and fall
 * back to the raw string otherwise -- never guessing or reclassifying.
 */
export function inflationStateLabelOrRaw(value: string): string {
  return value in INFLATION_STATE_LABELS ? INFLATION_STATE_LABELS[value as InflationState] : value;
}

export function confirmationRelationshipLabelOrRaw(value: string): string {
  return value in RELATIONSHIP_LABELS ? RELATIONSHIP_LABELS[value as ConfirmationRelationship] : value;
}

/** Same fallback pattern as inflationStateLabelOrRaw, for tone lookups against a ChangeEvent's raw string value. */
export function inflationStateToneOrNeutral(value: string): Tone {
  return value in INFLATION_STATE_TONE ? INFLATION_STATE_TONE[value as InflationState] : "neutral";
}
