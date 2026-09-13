import type { ReleaseOccurrenceItem } from "../../api/releases.types";
import { isShortenedLabel, releaseCategory, releaseDisplayLabel } from "../../lib/releasePresentation";
import { ScheduleStatusBadge } from "./ScheduleStatusBadge";

/**
 * One release within a date group: category (if curated), name
 * (canonical, or a shortened presentation label with the full
 * canonical name preserved as the row's accessible name), then
 * provider and the backend's own `schedule_status` -- never a
 * client-derived one. No date here; the parent group's
 * `ReleaseDateBadge` already shows it once for every release sharing
 * that date.
 */
export function ReleaseRow({ item }: { item: ReleaseOccurrenceItem }) {
  const label = releaseDisplayLabel(item);
  const category = releaseCategory(item);
  const shortened = isShortenedLabel(item);

  return (
    <div>
      {category && <p className="text-xs font-medium uppercase tracking-wide text-neutral-400">{category}</p>}
      <p className="mt-0.5 font-medium text-neutral-900" {...(shortened ? { title: item.name, "aria-label": item.name } : {})}>
        {label}
      </p>
      <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-neutral-500">
        <span>{item.provider}</span>
        <ScheduleStatusBadge status={item.schedule_status} />
      </p>
    </div>
  );
}
