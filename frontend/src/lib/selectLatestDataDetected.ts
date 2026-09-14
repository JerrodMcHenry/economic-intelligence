/**
 * Deterministic UI selection rule for the Overview "Latest Data
 * Detected" section (Increment #19C): which ONE of #19B's returned
 * occurrences to show.
 *
 * The backend orders its response by `scheduled_date DESC` with a
 * deterministic tie-break -- but the most-recently-SCHEDULED occurrence
 * is very often the LEAST informative one to show here: #18/#19B
 * processing is manual/operational-only (no scheduler -- see
 * docs/architecture/release-processing-v1.md #17), so a future
 * `scheduled_date` is essentially always still `NOT_CHECKED`. Showing
 * "first item exactly as returned" would mean this section almost
 * always displays a boring, uninformative NOT_CHECKED row and would
 * bury real, recently-detected evidence beneath it -- defeating the
 * section's whole purpose.
 *
 * This is a PRODUCT PRIORITY rule, not an economic one: it ranks
 * `latest_check.status` values by how actionable/informative they are
 * to show, using ONLY the `status` field the backend already returned
 * -- never a date comparison, never a field this module derives
 * itself. Within one status tier, the backend's own order is preserved
 * exactly (first match wins) -- this function never reorders, dedupes,
 * or drops any field from the chosen item.
 *
 * Because this rule can select an item that is NOT the most recently
 * scheduled occurrence, the section's own copy must never say "latest
 * release" or "most recent release" -- see
 * components/overview/LatestDataDetected.tsx's own supporting copy
 * ("Most recent detected update").
 */
import type { ProcessingStatus, ReleaseProcessingStatusItem } from "../api/processingStatus.types";

/** Most actionable/informative first. Exhaustive over all five public
 * statuses -- a status missing from this list would fall through to
 * `Infinity` below and always sort last, never crash. */
const STATUS_PRIORITY: readonly ProcessingStatus[] = ["CHANGES_DETECTED", "PARTIAL_CHECK", "CHECK_FAILED", "NO_CHANGE", "NOT_CHECKED"];

function priorityRank(status: ProcessingStatus): number {
  const index = STATUS_PRIORITY.indexOf(status);
  return index === -1 ? Number.POSITIVE_INFINITY : index;
}

/**
 * Returns the single highest-priority item, preserving the backend's
 * own relative order among equally-ranked items (a stable selection,
 * not a sort/reorder of the input) -- `null` for an empty list.
 */
export function selectLatestDataDetectedItem(
  items: readonly ReleaseProcessingStatusItem[],
): ReleaseProcessingStatusItem | null {
  let best: ReleaseProcessingStatusItem | null = null;
  let bestRank = Number.POSITIVE_INFINITY;

  for (const item of items) {
    const rank = priorityRank(item.latest_check.status);
    if (rank < bestRank) {
      best = item;
      bestRank = rank;
    }
  }

  return best;
}
