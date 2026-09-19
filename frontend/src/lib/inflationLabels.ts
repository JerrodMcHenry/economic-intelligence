/**
 * Human-readable labels and visual "tone" for values the backend has
 * already classified. These functions map one already-canonical value
 * to display text/styling -- they never inspect a metric, compare two
 * values, or decide which state/relationship applies. `INSUFFICIENT_DATA`
 * and `UNAVAILABLE` always map to the muted "unavailable" tone, never a
 * direction, per the frozen contract's own requirement that missing
 * evidence must never look like an economic conclusion.
 */
import type { ChangeComponent, ChangeEventType, ConfirmationRelationship, InflationState } from "../api/inflation.types";
import type { Tone } from "../design/stateTone";

// The tone taxonomy and its token-backed class maps live in the design
// layer (Increment #27B); re-exported here so existing domain imports
// keep working unchanged.
export type { Tone } from "../design/stateTone";
export { TONE_BORDER_CLASSES, TONE_CLASSES, TONE_TEXT_CLASSES } from "../design/stateTone";

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
 * Labels for `ChangeEvent.event_type` (Increment #16B) and
 * `DetectedAnalysisChange.event_type` (Increment #19C -- reuses this
 * exact type, see api/processingStatus.types.ts's own docstring for
 * why). Added here rather than in a separate #19C-only module so every
 * `ChangeComponent`/`ChangeEventType` label lookup stays in this one
 * canonical place, regardless of which increment's UI consumes it.
 */
export const CHANGE_EVENT_TYPE_LABELS: Record<ChangeEventType, string> = {
  METRIC_CHANGED: "Metric changed",
  STATE_CHANGED: "State changed",
  AVAILABILITY_LOST: "Availability lost",
  AVAILABILITY_RESTORED: "Availability restored",
  CONFIRMATION_CHANGED: "Confirmation changed",
};

export function changeEventTypeLabel(eventType: ChangeEventType): string {
  return CHANGE_EVENT_TYPE_LABELS[eventType];
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
