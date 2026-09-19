import { formatCompactDate, formatFullDate } from "../../lib/releases";

/**
 * A compact "SEP 17"-style date badge, date only -- no time, no
 * timezone, no countdown, no "today at..." (see
 * docs/architecture/release-intelligence-v1.md #3/#13: #17A knows only
 * a scheduled *date*, and inventing a time would violate that). The
 * full date (including year) is still always available: `dateTime`
 * carries the exact ISO date machine-readably, and the visible caption
 * spells it out in full -- nothing here is precision visible only to
 * a screen reader or only to sighted users.
 */
export function ReleaseDateBadge({ date }: { date: string }) {
  const { month, day } = formatCompactDate(date);
  const fullDate = formatFullDate(date);
  return (
    <time
      dateTime={date}
      aria-label={fullDate}
      title={fullDate}
      className="flex w-14 flex-none flex-col items-center rounded-md border border-line bg-surface py-1.5 leading-none"
    >
      <span className="text-[0.65rem] font-semibold uppercase tracking-wide text-fg-muted">{month}</span>
      <span className="mt-0.5 text-lg font-semibold text-fg">{day}</span>
    </time>
  );
}
