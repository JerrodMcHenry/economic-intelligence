/**
 * Curated, static explanation content for Increment #19C's "Latest
 * Data Detected" section -- keyed by the backend's own already-derived
 * enum values, exactly the pattern content/explanations/releases.ts
 * already establishes for `ScheduleStatus`. Never AI-generated, never
 * backend-mutating.
 *
 * `DETECTED_CHANGES_DATA_BASIS` is deliberately its own, more precise
 * sentence rather than a reuse of `LATEST_REVISED_DATA`
 * (content/explanations/inflation.ts): that sentence describes
 * Inflation *calculations*' data vintage, while this section can show
 * raw persisted *source* values with no calculation involved at all --
 * "does not reconstruct the original historical release vintage" is a
 * narrower, more accurate claim for what #18/#19B actually persist
 * (EI's own before/after observation values, never a reconstruction of
 * what a provider originally published on a historical date).
 */
import type { ProcessingStatus } from "../../api/processingStatus.types";
import type { Explanation } from "./types";

export const DETECTED_CHANGES_DATA_BASIS: Explanation = {
  id: "processing-status.detected-changes-data-basis",
  title: "How detected changes are compared",
  definition:
    "Detected changes compare Economic Intelligence's persisted observations before and after processing. They do not reconstruct the original historical release vintage.",
  whyItMatters:
    "A \"revision detected\" here means EI's own stored value for that date changed -- not that EI has recovered a full history of every value a provider has ever published for it.",
};

export const NEW_OBSERVATION: Explanation = {
  id: "processing-status.new-observation",
  title: "New observation",
  definition: "Economic Intelligence detected and persisted a value for a date it had no prior value for.",
};

export const REVISION_DETECTED: Explanation = {
  id: "processing-status.revision-detected",
  title: "Revision detected",
  definition: "Economic Intelligence detected that a provider's value for a date it already had a value for has changed, and persisted the new value.",
  whyItMatters: "Government economic data is often revised after it's first published, as more complete survey responses come in.",
};

export const TRACKED_ANALYSIS_CHANGE: Explanation = {
  id: "processing-status.tracked-analysis-change",
  title: "Tracked analysis change",
  definition:
    "A change to one of Economic Intelligence's own deterministic metrics or classifications (Inflation or Labor), computed the same way as the live monitor and What Changed pages -- never a separate calculation.",
  whyItMatters:
    "Source data can change without moving a tracked metric or state (small revisions that don't cross a threshold), and a tracked metric can be affected by a revision to any of several source dates -- the two lists on this page are independent facts, not a one-to-one cause and effect.",
};

export const CHECK_INCOMPLETE: Explanation = {
  id: "processing-status.check-incomplete",
  title: "Check incomplete",
  definition:
    "Economic Intelligence successfully checked at least one series mapped to this release, but at least one other mapped series could not be checked in the same run.",
};

const PROCESSING_STATUS_EXPLANATIONS: Record<ProcessingStatus, Explanation> = {
  NOT_CHECKED: {
    id: "processing-status.status-not-checked",
    title: "Not yet checked",
    definition: "Economic Intelligence has no durable processing record for this release occurrence yet.",
  },
  NO_CHANGE: {
    id: "processing-status.status-no-change",
    title: "No new data detected",
    definition: "Economic Intelligence's most recent check for this release occurrence found no new or revised source data.",
  },
  CHANGES_DETECTED: {
    id: "processing-status.status-changes-detected",
    title: "Data changes detected",
    definition: "Economic Intelligence's most recent check for this release occurrence found at least one new or revised source observation.",
  },
  PARTIAL_CHECK: CHECK_INCOMPLETE,
  CHECK_FAILED: {
    id: "processing-status.status-check-failed",
    title: "Check unsuccessful",
    definition: "Economic Intelligence's most recent check for this release occurrence could not be completed.",
  },
};

/** The curated explanation for a canonical `ProcessingStatus` value --
 * looked up by the backend's own already-derived value, never used to
 * derive one. */
export function processingStatusExplanation(status: ProcessingStatus): Explanation {
  return PROCESSING_STATUS_EXPLANATIONS[status];
}
