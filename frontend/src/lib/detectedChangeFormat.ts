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
import { confirmationRelationshipLabelOrRaw, inflationStateLabelOrRaw } from "./inflationLabels";

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
 * docstring). "state"/"relationship" fields are looked up in the same
 * canonical label maps `WhatChangedPreview.tsx` already uses for the
 * identical `ChangeEvent` shape; every other field is shown exactly as
 * stored, never reinterpreted as numeric.
 */
export function formatAnalysisValue(field: string, value: string | null): string {
  if (value === null) return "Unavailable";
  if (field === "state") return inflationStateLabelOrRaw(value);
  if (field === "relationship") return confirmationRelationshipLabelOrRaw(value);
  return value;
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
