import type { ReleaseOccurrenceItem } from "../../api/releases.types";
import { groupReleasesByDate } from "../../lib/releases";
import { ReleaseDateBadge } from "./ReleaseDateBadge";
import { ReleaseRow } from "./ReleaseRow";

/**
 * One release-calendar section (Upcoming or Recent) -- identical
 * structure for both; only the heading, empty-state copy, and the
 * already-ordered `releases` array passed in differ per caller. Order
 * is never touched here: the backend's `order` query parameter (asc
 * for Upcoming, desc for Recent) already produced the chronology this
 * renders; only same-date grouping is display logic.
 */
export function ReleaseCalendarSection({
  sectionId,
  heading,
  emptyMessage,
  releases,
}: {
  sectionId: string;
  heading: string;
  emptyMessage: string;
  releases: readonly ReleaseOccurrenceItem[];
}) {
  const groups = groupReleasesByDate(releases);
  const headingId = `${sectionId}-releases-heading`;

  return (
    <section aria-labelledby={headingId}>
      <h2 id={headingId} className="text-sm font-medium text-neutral-500">
        {heading}
      </h2>

      {groups.length === 0 ? (
        <p className="mt-3 text-sm text-neutral-500">{emptyMessage}</p>
      ) : (
        <ol className="mt-3 divide-y divide-neutral-200">
          {groups.map((group) => (
            <li key={group.scheduled_date} className="flex gap-4 py-4 first:pt-0">
              <ReleaseDateBadge date={group.scheduled_date} />
              <ul className="min-w-0 flex-1 space-y-3">
                {group.items.map((item) => (
                  <li key={`${item.release_id}-${item.scheduled_date}`}>
                    <ReleaseRow item={item} />
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
