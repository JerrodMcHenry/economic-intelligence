import type { ReleaseOccurrenceItem } from "../../api/releases.types";
import { groupReleasesByDate } from "../../lib/releases";
import { ReleaseDateBadge } from "../releases/ReleaseDateBadge";
import { ReleaseRow } from "../releases/ReleaseRow";

const MAX_UPCOMING = 3;

/**
 * The first `MAX_UPCOMING` occurrences from `/releases`' own ordered
 * response, unreordered and unranked -- `.slice(0, 3)` on the raw,
 * backend-ordered array, THEN grouped by date only for display (the
 * same `groupReleasesByDate` `/releases` itself uses), so two of the
 * three previewed occurrences sharing one date still render under one
 * compact date badge rather than as a fourth visual row. Reuses
 * `ReleaseDateBadge`/`ReleaseRow` unmodified -- no second presentation
 * of a release's name, category, provider, or schedule status exists
 * here; this is exactly what `/releases` already renders, only fewer
 * of them.
 *
 * Increment #22B: the one context where `ReleaseRow`'s optional
 * `showMonitorCta` renders (docs/product/overview-attention-model-v1.md
 * §17) -- a row shown here always has a useful, non-circular next
 * action (Overview is never itself `/inflation`/`/labor`/`/releases`),
 * unlike `ReleaseCalendarSection` (already on `/releases`) or
 * `RelevantRelease` (already on `/labor`), where the identical CTA
 * would be circular and is deliberately omitted.
 */
export function UpcomingReleasesPreview({ releases }: { releases: readonly ReleaseOccurrenceItem[] }) {
  const preview = releases.slice(0, MAX_UPCOMING);

  if (preview.length === 0) {
    return <p className="mt-3 text-sm text-fg-muted">No scheduled releases in this window.</p>;
  }

  const groups = groupReleasesByDate(preview);

  return (
    <ol className="mt-3 divide-y divide-line">
      {groups.map((group) => (
        <li key={group.scheduled_date} className="flex gap-4 py-3 first:pt-0">
          <ReleaseDateBadge date={group.scheduled_date} />
          <ul className="min-w-0 flex-1 space-y-3">
            {group.items.map((item) => (
              <li key={`${item.release_id}-${item.scheduled_date}`}>
                <ReleaseRow item={item} showMonitorCta />
              </li>
            ))}
          </ul>
        </li>
      ))}
    </ol>
  );
}
