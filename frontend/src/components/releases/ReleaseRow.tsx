import type { ReleaseOccurrenceItem } from "../../api/releases.types";
import { releaseTypeExplanation, scheduleStatusExplanation } from "../../content/explanations/releases";
import { isShortenedLabel, releaseCategory, releaseDisplayLabel } from "../../lib/releasePresentation";
import { ExplanationTrigger } from "../explanations/ExplanationTrigger";
import { ScheduleStatusBadge } from "./ScheduleStatusBadge";

/**
 * One release within a date group: category (if curated), name
 * (canonical, or a shortened presentation label with the full
 * canonical name preserved as the row's accessible name), then
 * provider and the backend's own `schedule_status` -- never a
 * client-derived one. No date here; the parent group's
 * `ReleaseDateBadge` already shows it once for every release sharing
 * that date. `releaseTypeExplanation` is keyed by the same
 * `provider_release_id` `releasePresentation.ts` already uses -- `null`
 * for any release not in the curated V1 set, in which case no trigger
 * renders rather than showing an empty/fabricated one.
 */
export function ReleaseRow({ item }: { item: ReleaseOccurrenceItem }) {
  const label = releaseDisplayLabel(item);
  const category = releaseCategory(item);
  const shortened = isShortenedLabel(item);
  const typeExplanation = releaseTypeExplanation(item.provider_release_id);
  const statusExplanation = scheduleStatusExplanation(item.schedule_status);

  return (
    <div>
      {category && <p className="text-xs font-medium uppercase tracking-wide text-neutral-400">{category}</p>}
      {/* <details> (inside ExplanationTrigger) is block-level content and
          cannot legally nest inside <p>, so these rows use <div> even
          though they hold a single line of text -- same reason
          Disclosure.tsx never nests inside a <p> either. */}
      <div className="mt-0.5 flex items-center gap-1.5">
        <span className="font-medium text-neutral-900" {...(shortened ? { title: item.name, "aria-label": item.name } : {})}>
          {label}
        </span>
        {typeExplanation && <ExplanationTrigger explanation={typeExplanation} />}
      </div>
      <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-neutral-500">
        <span>{item.provider}</span>
        <span className="inline-flex items-center gap-1">
          <ScheduleStatusBadge status={item.schedule_status} />
          <ExplanationTrigger explanation={statusExplanation} />
        </span>
      </div>
    </div>
  );
}
