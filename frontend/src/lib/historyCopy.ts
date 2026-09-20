/**
 * Every user-facing sentence in the point-in-time intelligence history
 * experience (Increment #32), as frozen templates.
 *
 * Copy lives here, not inline in components, for the same reason
 * `sinceLastVisitCopy.ts` exists: the wording carries the product's
 * honesty guarantees, and a guarantee scattered across five components
 * is one edit away from being lost.
 *
 * Two rules govern everything in this file.
 *
 * 1. **Never imply that today's revised data was known then.** The two
 *    views get permanently distinct headings -- "What MacroChipz knew
 *    then" versus "Using today's revised data" -- and no sentence
 *    describing the current reconstruction uses a past-tense knowing
 *    verb.
 *
 * 2. **Never use database vocabulary in the primary experience.**
 *    "System-time interval", "recorded_to", "temporal version" and
 *    "backfill" are implementation terms. What a reader needs is what
 *    the evidence does and does not prove, in ordinary words.
 */

export const SECTION_HEADING = "Intelligence history";

export const SECTION_INTRO =
  "What MacroChipz concluded each time it ran, and whether those conclusions can still be reproduced from the data available at the time.";

export const EMPTY_HISTORY_COPY =
  "MacroChipz has not recorded any conclusions for this monitor yet. Entries appear here once a release has been processed.";

export const LOADING_LABEL = "Loading intelligence history";

export const ERROR_MESSAGE = "Intelligence history could not be loaded.";

export const DETAIL_ERROR_MESSAGE = "This result's details could not be loaded.";

export const DETAIL_LOADING_LABEL = "Loading result details";

/** The two permanently distinct headings. */
export const THEN_HEADING = "What MacroChipz knew then";
export const TODAY_HEADING = "Using today's revised data";

export const INPUTS_HEADING = "Data available then";
export const RELATED_CHANGES_HEADING = "Data changes in the same run";

/**
 * The standing disclosure that economic data is revised after
 * publication. Without it, a reader has no way to know that "then" and
 * "today" can legitimately disagree.
 */
export const REVISION_DISCLOSURE =
  "Economic data is often revised after it is first published. A conclusion MacroChipz recorded in the past used the data available at that moment, which may differ from the data available now.";

/**
 * The backfill disclosure. Deliberately not alarming -- backfilled
 * history is real evidence -- and deliberately not hidden, because it
 * proves strictly less than observed history does.
 *
 * Tracks the boundary frozen in
 * `docs/product/recorded-state-history-v1.md` §23: reproducible from
 * MacroChipz's own stored data, but not proof of the provider's
 * originally published values.
 */
export const BACKFILL_DISCLOSURE =
  "Some values here were reconstructed from data MacroChipz had already stored when it began tracking revisions. This result can be reproduced from that stored data, but MacroChipz cannot prove those were the provider's originally published figures.";

export const BACKFILL_BADGE_LABEL = "Reconstructed inputs";

/** Short, neutral note on what a same-run change is — and is not. */
export const RELATED_CHANGES_NOTE =
  "These source-data changes were processed in the same run that produced this result. MacroChipz records that they happened together; it does not record that one caused the other.";

export function otherChangesCopy(count: number): string | null {
  if (count <= 0) return null;
  const plural = count === 1 ? "change" : "changes";
  return `${count} further source-data ${plural} in the same run did not feed this result.`;
}

/** "August 2026 · calculated Sep 14, 2026" style supporting line. */
export function calculatedLine(formattedCalculatedAt: string): string {
  return `Calculated ${formattedCalculatedAt}`;
}

/**
 * How this entry relates to the previously recorded one. The two cases
 * are genuinely different and the copy keeps them apart: a new month
 * classified differently is not MacroChipz changing its mind.
 */
export function previousStateCopy(
  previousStateLabel: string,
  sameEvaluationPeriod: boolean,
  stateChanged: boolean,
): string {
  if (!stateChanged) {
    return sameEvaluationPeriod
      ? "Recalculated for the same period; the conclusion did not change."
      : `Unchanged from the previous period (${previousStateLabel}).`;
  }
  return sameEvaluationPeriod
    ? `Revised conclusion for the same period; previously ${previousStateLabel}.`
    : `Changed from ${previousStateLabel} in the previous period.`;
}

/**
 * The then-vs-today summary sentence. `stateDiffers` is the backend's
 * own comparison; this function only chooses wording for it.
 */
export function comparisonSummaryCopy(stateDiffers: boolean, currentStateLabel: string): string {
  return stateDiffers
    ? `Using today's revised data, the same period would now be classified ${currentStateLabel}.`
    : `Today's revised data still produces ${currentStateLabel} for this period.`;
}

export function changedInputsCopy(count: number): string {
  if (count === 0) return "None of the values this result used have changed since.";
  const plural = count === 1 ? "value has" : "values have";
  return `${count} of the ${plural} changed since this result was calculated.`;
}

export const METHODOLOGY_DIFFERS_NOTE =
  "Because the methodology version also differs, any difference may reflect changed data, changed methodology, or both.";
