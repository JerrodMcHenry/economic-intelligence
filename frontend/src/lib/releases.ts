/**
 * Presentation-layer helpers for the release calendar: query-window
 * date math, same-date grouping, and compact date display. None of
 * this classifies a release's schedule status -- that's the backend's
 * `schedule_status` field, used as-is everywhere in this UI. This
 * module only decides *which dates to ask the backend about* and *how
 * to lay out what it returns*, never *what a date means economically*.
 *
 * V1 query windows (not frozen by docs/architecture/release-intelligence-v1.md,
 * which leaves the exact range to the product default -- see that
 * spec's #13 and the Increment #17B journal entry for why these
 * specific values were chosen): Upcoming is today through the next 45
 * days; Recent is the previous 30 days through today. Both are small,
 * bounded windows -- nowhere near the entire historical release table.
 */
import type { ReleaseOccurrenceItem } from "../api/releases.types";

const UPCOMING_WINDOW_DAYS = 45;
const RECENT_WINDOW_DAYS = 30;

function addDays(date: Date, days: number): Date {
  const result = new Date(date.getTime());
  result.setDate(result.getDate() + days);
  return result;
}

/** A local calendar date as "YYYY-MM-DD", using the date's own local
 * year/month/day components -- never `toISOString()`, which reports
 * UTC and can roll the date back a day depending on the browser's
 * timezone relative to UTC. */
function toLocalISODate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export interface DateWindow {
  start_date: string;
  end_date: string;
}

/** Today through `UPCOMING_WINDOW_DAYS` days ahead. `today` is an
 * explicit, overridable parameter (defaulting to the real current
 * date) so this is deterministically testable -- this is UI
 * query-window logic only, not a canonical calculation, so a default
 * of `new Date()` is appropriate here (unlike the backend's
 * `classify_schedule_status`, which never defaults `as_of_date`). */
export function upcomingWindow(today: Date = new Date()): DateWindow {
  return { start_date: toLocalISODate(today), end_date: toLocalISODate(addDays(today, UPCOMING_WINDOW_DAYS)) };
}

/** The previous `RECENT_WINDOW_DAYS` days through today, inclusive. */
export function recentWindow(today: Date = new Date()): DateWindow {
  return { start_date: toLocalISODate(addDays(today, -RECENT_WINDOW_DAYS)), end_date: toLocalISODate(today) };
}

export interface ReleaseDateGroup {
  scheduled_date: string;
  items: ReleaseOccurrenceItem[];
}

/**
 * Groups adjacent releases sharing the same `scheduled_date` into one
 * display group -- display-only, never re-sorts: the backend already
 * orders its response by `scheduled_date` first (see
 * ReleaseRepository.list_occurrences), so same-date items are always
 * already adjacent in the input; this never reorders across dates and
 * preserves each date's items in exactly the order the backend
 * returned them.
 */
export function groupReleasesByDate(releases: readonly ReleaseOccurrenceItem[]): ReleaseDateGroup[] {
  const groups: ReleaseDateGroup[] = [];
  for (const release of releases) {
    const lastGroup = groups.at(-1);
    if (lastGroup && lastGroup.scheduled_date === release.scheduled_date) {
      lastGroup.items.push(release);
    } else {
      groups.push({ scheduled_date: release.scheduled_date, items: [release] });
    }
  }
  return groups;
}

const MONTH_ABBREVIATIONS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
] as const;

export interface CompactDateParts {
  month: string;
  day: string;
}

/**
 * "2026-09-17" -> { month: "SEP", day: "17" } for the compact date
 * badge. Parses the ISO date string's own digits directly (the same
 * regex-based approach `lib/format.ts`'s `formatPeriod` already uses)
 * -- never via `new Date(str)`, which parses a date-only ISO string as
 * UTC midnight and can roll the displayed day back one in timezones
 * behind UTC. No year in the compact badge (V1's ~75-day combined
 * window rarely crosses one, and when it does the full ISO date is
 * still available via the `<time dateTime>` element that always
 * accompanies this badge) -- never a fabricated time of day.
 */
export function formatCompactDate(isoDate: string): CompactDateParts {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoDate);
  if (!match) return { month: "", day: isoDate };
  const month = match[2] ?? "";
  const day = match[3] ?? "";
  const monthAbbreviation = MONTH_ABBREVIATIONS[Number(month) - 1];
  return { month: monthAbbreviation ? monthAbbreviation.toUpperCase() : month, day: String(Number(day)) };
}

/** "2026-09-17" -> "September 17, 2026", for full accessible/visible
 * date text -- same digit-parsing discipline as `formatCompactDate`. */
export function formatFullDate(isoDate: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoDate);
  if (!match) return isoDate;
  const [, year, month, day] = match;
  const monthNames = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
  ];
  const monthName = monthNames[Number(month) - 1];
  return monthName ? `${monthName} ${Number(day)}, ${year}` : isoDate;
}
