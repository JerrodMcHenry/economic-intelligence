/**
 * Which Structured Intelligence objects are genuine revisions (#43).
 *
 * ================================================================
 * A REVISION IS SOMETHING MACROCHIPZ WATCHED HAPPEN.
 * ================================================================
 *
 * Three things are routinely mistaken for revisions and are not:
 *
 * 1. **A first observation.** MacroChipz learned a value. Nothing
 *    changed; there was nothing to change from. 358 of the 358 local
 *    `OBSERVATION_CHANGE` objects are this.
 * 2. **A backfilled baseline.** #31 imported 1,072 observations when
 *    point-in-time tracking began. MacroChipz knows the value as of
 *    that import and cannot say what the provider had published
 *    before it. Every one of those 1,072 version rows carries
 *    `is_backfilled = true`.
 * 3. **A methodology or state change with no source revision.** The
 *    number did not move; the conclusion did.
 *
 * Only `PROSPECTIVE_REVISION` -- MacroChipz recorded A, then observed
 * the provider publish B -- supports the sentence "originally
 * reported". This module is where that distinction is enforced, and it
 * reads the backend's own `revision_knowledge`: the frontend never
 * infers revision truth from raw values or version endpoints.
 *
 * MEASURED 2026-09-21: this selects **zero** objects, because no
 * genuine revision has ever been captured. That is a fact about how
 * young the pipeline is, and `/revisions` says so rather than
 * manufacturing one.
 */
import type { IntelligenceObject, ObservationChangeIntelligence } from "../api/intelligence.types";

export function isGenuineRevision(object: IntelligenceObject): object is ObservationChangeIntelligence {
  if (object.type !== "OBSERVATION_CHANGE") return false;
  // Both conditions, deliberately. `REVISED` alone would admit a
  // migration baseline; the knowledge state alone would be trusting a
  // field to mean more than it says.
  return object.payload.change_type === "REVISED" && object.payload.revision_knowledge === "PROSPECTIVE_REVISION";
}

/**
 * Genuine revisions, most recently DETECTED first.
 *
 * `recorded_at` is when MacroChipz detected the change -- the only
 * time it can prove. It is never relabelled as a publication time,
 * because the provider's publication instant is not recorded anywhere
 * (`published_at` is null on every object MacroChipz holds).
 *
 * Ordering is by time and then by id, and by nothing else. There is no
 * ranking by size of revision: #43 adds no significance methodology,
 * so "the biggest revision" is not a sentence MacroChipz can say.
 */
export function selectRevisions(objects: ReadonlyArray<IntelligenceObject>): ObservationChangeIntelligence[] {
  return objects.filter(isGenuineRevision).sort((a, b) => {
    if (a.recorded_at !== b.recorded_at) return a.recorded_at < b.recorded_at ? 1 : -1;
    return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
  });
}
