import { Link } from "react-router-dom";

import type { ReleaseProcessingStatusItem } from "../../api/processingStatus.types";
import { CANONICAL_MONITOR_RELEASE_IDS } from "../../lib/releaseMonitorRelation";
import { LatestDataDetected } from "./LatestDataDetected";

/**
 * The Economic Overview's "Recent Data Updates" section -- Increment
 * #19C's own "Latest Data Detected" concept, RENAMED and RESTRUCTURED
 * per docs/product/overview-attention-model-v1.md §14 (Increment
 * #22B). "Recent Data Updates" was chosen because it is the smallest
 * diff removing the pipeline-step word ("Detected") while matching the
 * naming convention this exact page already uses one section below it
 * ("Upcoming Releases"/"Recent Releases" -- pages/Releases.tsx). The
 * section's prominence and its DATA-changed vs. INTELLIGENCE-changed
 * structural split are both correct and are preserved exactly, inside
 * `LatestDataDetected.tsx` (unmodified in substance) -- only the
 * heading, and the selection cardinality below, change.
 *
 * Restructured from a single system-wide selection to one slot per
 * canonical monitor domain, mirroring `CurrentStateSection`'s own
 * peer-card pattern exactly: one shared `<h2>`, two independently-
 * gated `<div>` sub-blocks, neither owning the heading. Each slot
 * pre-filters the already-loaded `items` array by CANONICAL MONITOR
 * RELATION (`lib/releaseMonitorRelation.ts`'s
 * `CANONICAL_MONITOR_RELEASE_IDS`) -- NEVER by `releaseCategory()`,
 * the broader, unrelated `/releases` display tag that would (and, in
 * an earlier draft of this contract, incorrectly did) attribute JOLTS
 * to the Labor monitor despite JOLTS feeding zero canonical series
 * (docs/product/overview-attention-model-v1.md §3A). An item whose
 * release has no canonical monitor relation (JOLTS, GDP, Advance
 * Retail Sales) surfaces in neither slot -- an explicit, frozen scope
 * boundary matching today's real, migration-verified canonical inputs,
 * not an oversight.
 *
 * `selectLatestDataDetectedItem` itself (inside `LatestDataDetected.tsx`)
 * is completely unmodified -- this is a pure call-site change: filter,
 * then render the same slot-content component twice.
 */
export function RecentDataUpdates({ items }: { items: readonly ReleaseProcessingStatusItem[] }) {
  const inflationItems = items.filter((item) => CANONICAL_MONITOR_RELEASE_IDS.INFLATION.has(item.release.provider_release_id));
  const laborItems = items.filter((item) => CANONICAL_MONITOR_RELEASE_IDS.LABOR.has(item.release.provider_release_id));

  return (
    <section aria-labelledby="overview-recent-data-updates-heading">
      <h2 id="overview-recent-data-updates-heading" className="text-sm font-medium text-fg-muted">
        Recent Data Updates
      </h2>

      <div className="mt-3 space-y-6">
        <div>
          <p className="text-sm font-semibold text-fg-secondary">Inflation</p>
          <LatestDataDetected items={inflationItems} />
          <Link to="/inflation" className="mt-4 inline-block text-sm font-medium text-fg-secondary hover:text-fg">
            View Inflation →
          </Link>
        </div>

        <div>
          <p className="text-sm font-semibold text-fg-secondary">Labor</p>
          <LatestDataDetected items={laborItems} />
          <Link to="/labor" className="mt-4 inline-block text-sm font-medium text-fg-secondary hover:text-fg">
            View Labor →
          </Link>
        </div>
      </div>
    </section>
  );
}
