/**
 * Presentation-only formatting for Increment #19C's "Latest Data
 * Detected" section. Every function here takes an already-canonical
 * value the backend returned and produces display text -- none of
 * them classify, calculate, annualize, normalize, or recompute a
 * delta. `previous_value`/`current_value` on a detected analysis
 * change are persisted strings (see
 * api/processingStatus.types.ts's `DetectedAnalysisChange`) and are
 * shown faithfully, reinterpreted only for the two enum-shaped fields
 * ("state"/"relationship") this project already has a canonical label
 * map for -- never coerced into a number.
 */
import type { ObservationChangeType, ProcessingStatus } from "../api/processingStatus.types";
import { humanizeEnumValue } from "./format";
import { CHANGE_COMPONENT_LABELS, CHANGE_FIELD_LABELS, confirmationRelationshipLabelOrRaw, inflationStateLabelOrRaw } from "./inflationLabels";
import { laborChangeComponentLabelOrRaw, laborChangeFieldLabel } from "./laborLabels";

/** Restrained, backend-status-controlled primary copy -- see
 * docs/ENGINEERING_JOURNAL.md's #19C entry and
 * components/overview/LatestDataDetected.tsx's own docstring for why
 * this mapping must never be overridden by inspecting detected-change
 * history (a NO_CHANGE latest check stays "No new data detected..."
 * even when earlier runs found real changes). */
const PROCESSING_STATUS_LABELS: Record<ProcessingStatus, string> = {
  NOT_CHECKED: "Not yet checked by Economic Intelligence.",
  NO_CHANGE: "No new data detected in the latest check.",
  CHANGES_DETECTED: "Data changes detected.",
  PARTIAL_CHECK: "Check incomplete.",
  CHECK_FAILED: "Check unsuccessful.",
};

export function processingStatusLabel(status: ProcessingStatus): string {
  return PROCESSING_STATUS_LABELS[status];
}

const OBSERVATION_CHANGE_TYPE_LABELS: Record<ObservationChangeType, string> = {
  NEW: "New observation",
  REVISED: "Revision detected",
};

/** Never "Published"/"Released"/"Corrected"/"Finalized" -- none of
 * those are supported by what #18/#19B actually detect (a persisted
 * observation write, not a provider publication event). */
export function observationChangeTypeLabel(changeType: ObservationChangeType): string {
  return OBSERVATION_CHANGE_TYPE_LABELS[changeType];
}

function isPercentUnits(units: string | null): boolean {
  return units !== null && units.toLowerCase().includes("percent");
}

/**
 * A `DetectedObservationChange.previous_value`/`new_value` for
 * display. Appends "%" only when `units` (the backend's own
 * `EconomicSeries.units` string) says so -- never inferred from the
 * field/series name. An index-level or dollar-denominated value is
 * shown as a plain formatted number, exactly as persisted -- never
 * converted to a percent change, annualized, or normalized.
 */
export function formatObservationValue(value: number | null, units: string | null): string {
  if (value === null) return "Unavailable";
  const formatted = value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  return isPercentUnits(units) ? `${formatted}%` : formatted;
}

/**
 * A `DetectedAnalysisChange.previous_value`/`current_value` for
 * display -- both are persisted strings (see this module's own
 * docstring). This row can come from ANY analysis family (Inflation's
 * own five components, or Labor's `LABOR`/`EMPLOYMENT`/`UNEMPLOYMENT`,
 * or a future family) -- this function does not need to know which,
 * because the value itself is self-describing: "state" is tried
 * against Inflation's own state map first (preserving exact existing
 * behavior for every Inflation row, byte-for-byte), and if the value
 * isn't one of those five, it falls back to a generic, presentation-safe
 * humanization (`humanizeEnumValue`) rather than the raw uppercase
 * string -- this is what fixes Labor's own `EXPANDING`/`RECOVERING`/
 * `DETERIORATING`/etc. rendering correctly without hardcoding Labor's
 * vocabulary into a shared, family-agnostic function (Increment
 * #20E.2, see docs/architecture/labor-ui-v1.md §6b/§23). "condition"/
 * "momentum" (fields that exist only for Labor's EMPLOYMENT component)
 * are humanized the same way. "relationship" (Inflation-only) is
 * unaffected. Every other field is shown exactly as stored, never
 * reinterpreted as numeric.
 */
export function formatAnalysisValue(field: string, value: string | null): string {
  if (value === null) return "Unavailable";
  if (field === "state") {
    const inflationLabel = inflationStateLabelOrRaw(value);
    return inflationLabel !== value ? inflationLabel : humanizeEnumValue(value);
  }
  if (field === "relationship") return confirmationRelationshipLabelOrRaw(value);
  if (field === "condition" || field === "momentum") return humanizeEnumValue(value);
  return value;
}

/**
 * A `DetectedAnalysisChange.component` for display -- tries Inflation's
 * own component map first (preserving exact existing behavior), then
 * Labor's, then falls back to a generic humanization rather than
 * rendering nothing (the real bug #20E.1 found:
 * `CHANGE_COMPONENT_LABELS[change.component]` alone returns `undefined`
 * for a Labor component value). See this module's own docstring on
 * `formatAnalysisValue` for the identical reasoning.
 */
export function analysisComponentLabel(component: string): string {
  if (component in CHANGE_COMPONENT_LABELS) return CHANGE_COMPONENT_LABELS[component as keyof typeof CHANGE_COMPONENT_LABELS];
  const laborLabel = laborChangeComponentLabelOrRaw(component);
  return laborLabel !== component ? laborLabel : humanizeEnumValue(component);
}

/**
 * A `DetectedAnalysisChange.field` for display -- tries Inflation's own
 * field-label map first (preserving exact existing behavior), then
 * Labor's own (e.g. "current_3m_avg_jobs" -> "Current 3M avg"), then
 * falls back to the raw field name (existing behavior for a field
 * neither map recognizes) -- never `undefined`.
 */
export function analysisFieldLabel(field: string): string {
  return CHANGE_FIELD_LABELS[field] ?? laborChangeFieldLabel(field);
}

const CHECKED_AT_FORMATTER = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
});

/**
 * "2026-07-01T21:42:00+00:00" -> "Sep 13, 9:42 PM" (viewer's local
 * time/locale). Unlike `lib/releases.ts`'s date-ONLY formatters, this
 * is safe to parse via `new Date(...)`: `checked_at` always carries an
 * explicit UTC offset (a timezone-aware Python `datetime`, not a bare
 * calendar date), so there is no local-midnight rollback risk. No
 * seconds -- avoids false precision a "check" timestamp doesn't need.
 * An unparseable value renders as-is rather than guessing.
 */
export function formatCheckedAt(isoDatetime: string): string {
  const date = new Date(isoDatetime);
  if (Number.isNaN(date.getTime())) return isoDatetime;
  return CHECKED_AT_FORMATTER.format(date);
}
