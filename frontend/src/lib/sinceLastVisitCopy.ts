/**
 * Pure, typed presentation copy for Since Last Visit V1 -- converts an
 * already-categorized `SinceLastVisitResponse` (app/models/since_last_visit.py,
 * frozen and normative in docs/product/since-last-visit-v1.md §79-86)
 * into the exact frozen display strings. This module calculates
 * NOTHING economic: it never compares `previous_value`/`current_value`
 * to decide whether something changed, never selects which item
 * "matters," never picks an evaluation period, and never infers a
 * `RecalculationKind` -- every classification it renders was already
 * made by the backend (contract §63/§24-28 of the source prompt). It
 * only templates already-canonical fields into the frozen sentences,
 * mirroring `lib/stateDurationCopy.ts`'s own identical "zero economic
 * content" boundary exactly.
 *
 * State words reuse the existing label functions verbatim
 * (`inflationStateLabelOrRaw`/`laborStateLabelOrRaw`) -- never
 * re-cased, abbreviated, or given a new synonym (contract §81,
 * mirroring `relate-composition-v1.md` §4's own already-frozen
 * discipline).
 */
import type { Coverage, DomainRecap, Monitor, Recalculation, SourceUpdate, StructuralChange } from "../api/sinceLastVisit.types";
import { inflationStateLabelOrRaw } from "./inflationLabels";
import { laborStateLabelOrRaw } from "./laborLabels";
import { formatPeriod } from "./format";

const DOMAIN_LABELS: Record<Monitor, string> = { inflation: "Inflation", labor: "Labor" };

export function domainLabel(monitor: Monitor): string {
  return DOMAIN_LABELS[monitor];
}

function domainStateLabel(monitor: Monitor, value: string | null): string {
  if (value === null) return "Unavailable";
  return monitor === "inflation" ? inflationStateLabelOrRaw(value) : laborStateLabelOrRaw(value);
}

// §85 -- frozen verbatim, first visit only (response.first_visit === true).
export const FIRST_VISIT_HEADING = "Recent Economic Activity";
export const FIRST_VISIT_ORIENTATION_COPY =
  "This is your first visit — future visits will show what's changed since you were last here.";

// §76 -- frozen verbatim, every return visit.
export const RETURN_VISIT_HEADING = "Since Your Last Check";

export function sinceLastVisitHeading(firstVisit: boolean): string {
  return firstVisit ? FIRST_VISIT_HEADING : RETURN_VISIT_HEADING;
}

// §86 -- frozen verbatim.
export const LOOKBACK_CLAMPED_COPY = "This summary covers the last 90 days — your last visit was longer ago.";

// §84 -- frozen verbatim, shown alongside real content when coverage
// narrows it (never for CHECKED, which needs no extra disclosure
// beyond the neutral "Last checked" fact below).
export function coverageDisclosureCopy(coverage: Coverage): string | null {
  if (coverage === "GAP") return "Some monitored releases could not be fully checked since your last visit.";
  if (coverage === "UNKNOWN") return "EI's own automated-checking coverage for this period could not be confirmed.";
  return null;
}

/**
 * §79's four-row table, resolved from the three real backend
 * `coverage` values plus item presence -- this contract's own §37-39
 * table describes "never processed" as its own product-level row, but
 * the frozen §40-41 coverage model (the one the backend actually
 * implements, confirmed by direct inspection of `app/domain/since_last_visit.py`'s
 * `compute_coverage`) already folds that case into `GAP` (a release
 * with zero settled runs is exactly one way `GAP`'s own "at least one
 * relevant release has no settled run" condition can be satisfied) --
 * no separate machine signal exists for it, and inventing one on the
 * frontend would be exactly the kind of derived truth the frontend
 * must never manufacture (contract §63). `GAP` + zero items therefore
 * reuses row C's own frozen wording verbatim, honestly covering both
 * of GAP's real underlying causes (zero checks, or checks that failed
 * to settle) without overclaiming which one occurred.
 */
export function domainZeroStateCopy(recap: DomainRecap): string | null {
  const hasContent = recap.structural_changes.length > 0 || recap.recalculations.length > 0 || recap.source_updates.length > 0;
  if (hasContent) return null;
  const label = domainLabel(recap.monitor);
  if (recap.coverage === "UNKNOWN") return `Coverage for ${label} could not be confirmed for this period.`;
  if (recap.coverage === "GAP") return `No monitored ${label} releases were processed since your last check.`;
  return `No new ${label} activity was detected since your last check.`;
}

// §43/§84 -- a neutral, non-evaluative timestamp fact only, never
// "up to date"/"fresh"/"stale". `formattedTimestamp` is supplied by
// the caller (the existing `formatCheckedAt`, `lib/detectedChangeFormat.ts`
// -- reused verbatim rather than a redundant new formatter; see this
// increment's own final report for why #25F's own §74 anticipation of
// a "new" formatter was superseded by this already-existing one).
export function lastCheckedCopy(formattedTimestamp: string | null): string | null {
  if (formattedTimestamp === null) return null;
  return `Last checked: ${formattedTimestamp}.`;
}

// §81 -- frozen template. Availability transitions use #22B's own
// already-shipped, non-directional phrasing verbatim (contract §26) --
// never "improved"/"worsened", never folded into the "changed from X
// to Y" template (which would misleadingly imply a real state value on
// the missing side).
export function structuralChangeCopy(item: StructuralChange): string {
  const label = domainLabel(item.monitor);
  const period = formatPeriod(item.evaluation_period);
  if (item.event_type === "AVAILABILITY_LOST") return `${label}'s own state became unavailable for ${period}.`;
  if (item.event_type === "AVAILABILITY_RESTORED") return `${label}'s own state became available again for ${period}.`;
  const previous = domainStateLabel(item.monitor, item.previous_value);
  const current = domainStateLabel(item.monitor, item.current_value);
  return `${label} changed from ${previous} to ${current} for ${period}.`;
}

// §80 -- frozen templates, exact. `INSUFFICIENT_DATA` never uses the
// "remains {label}" adjective template (that label is a noun phrase,
// not an adjective -- mirrors `relate-composition-v1.md` §4's own
// identical precedent).
export function recalculationCopy(item: Recalculation): string {
  const label = domainLabel(item.monitor);
  const period = formatPeriod(item.evaluation_period);
  if (item.kind === "FIRST_CALCULATION") {
    return `${label} was calculated as ${domainStateLabel(item.monitor, item.state)} for ${period}.`;
  }
  if (item.state === "INSUFFICIENT_DATA") {
    return `${label} was recalculated for ${period}; its state is still insufficient to classify.`;
  }
  const stateLabel = domainStateLabel(item.monitor, item.state);
  if (item.count <= 1) {
    return `${label} was recalculated for ${period} and remains ${stateLabel}.`;
  }
  return `${label} was recalculated ${item.count} times since your last visit and remains ${stateLabel} (most recently for ${period}).`;
}

// §82 -- frozen templates, exact. The NEW/REVISED distinction is
// preserved verbatim, directly from `change_type` -- never both
// collapsed to "updated" (contract §29/§38).
export function sourceUpdateCopy(item: SourceUpdate): string {
  const subject = item.series_title ?? item.series_id;
  return item.change_type === "REVISED" ? `${subject} data was revised.` : `${subject} data was updated.`;
}
