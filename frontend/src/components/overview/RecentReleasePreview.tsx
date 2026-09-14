import type { ReleaseOccurrenceItem } from "../../api/releases.types";
import { formatCompactDate } from "../../lib/releases";
import { isShortenedLabel, releaseDisplayLabel } from "../../lib/releasePresentation";
import { ScheduleStatusBadge } from "../releases/ScheduleStatusBadge";

const MAX_RECENT = 1;

/**
 * At most one recent occurrence, rendered as one compact line -- never
 * a second "Recent Releases" list (that stays `/releases`' own job).
 * Uses the backend's own response order (the caller already requested
 * `order=desc`, so `releases[0]` is already the most recent), never
 * re-sorted here. Renders `schedule_status` via the same
 * `ScheduleStatusBadge` `/releases` uses -- verbatim, never re-labeled.
 * If nothing exists in the recent window, this renders nothing at all
 * (never a fabricated "no recent activity" claim) -- absence here is
 * silent, matching how the rest of Overview never states a negative
 * fact that would need its own justification.
 */
export function RecentReleasePreview({ releases }: { releases: readonly ReleaseOccurrenceItem[] }) {
  const preview = releases.slice(0, MAX_RECENT);
  if (preview.length === 0) return null;

  const item = preview[0]!;
  const { month, day } = formatCompactDate(item.scheduled_date);
  const shortened = isShortenedLabel(item);

  return (
    <p className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-neutral-500">
      <span className="font-medium text-neutral-400">Recently</span>
      <span className="text-neutral-700" {...(shortened ? { title: item.name, "aria-label": item.name } : {})}>
        {releaseDisplayLabel(item)}
      </span>
      <span>
        · {month} {day} ·
      </span>
      <ScheduleStatusBadge status={item.schedule_status} />
    </p>
  );
}
