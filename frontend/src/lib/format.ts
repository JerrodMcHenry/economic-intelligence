/**
 * Presentation-only formatting. Every function here takes an
 * already-canonical value (a rate, a period string, a gap) and returns
 * display text -- none of them decide whether something changed, which
 * state applies, or perform any economic calculation. Rounding here is
 * for display only; canonical comparisons/classifications happened on
 * the backend, on the unrounded values, before this module ever sees
 * them.
 */

const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
] as const;

/**
 * "2026-07-01" -> "July 2026". Parses the ISO date string's own digits
 * directly -- deliberately never routed through `Date`/`toLocaleDateString`,
 * which apply the browser's local timezone to a UTC-midnight instant
 * and can silently roll the displayed month back a day in timezones
 * behind UTC. `null` (no observation/calculation period at all) is
 * rendered as an honest "No data available", never a fabricated date.
 */
export function formatPeriod(period: string | null): string {
  if (period === null) return "No data available";
  const match = /^(\d{4})-(\d{2})-\d{2}$/.exec(period);
  if (!match) return period; // unrecognized shape -- show the raw value rather than guessing
  const [, year, month] = match;
  const monthName = MONTH_NAMES[Number(month) - 1];
  return monthName ? `${monthName} ${year}` : period;
}

/** A single period as "Month Year", or a "Month Year → Month Year" pair when both are present and differ. */
export function formatPeriodPair(previous: string | null, current: string | null): string {
  if (previous === null && current === null) return formatPeriod(null);
  if (previous === current) return formatPeriod(current);
  return `${formatPeriod(previous)} → ${formatPeriod(current)}`;
}

/** 2.643912 -> "2.64%". `null` (unavailable) -> an em dash, never "0%" or a fabricated value. */
export function formatPercent(value: number | null, fractionDigits = 2): string {
  if (value === null) return "—";
  return `${value.toFixed(fractionDigits)}%`;
}

/**
 * 0.70123 -> "+0.70 pp"; -0.2 -> "-0.20 pp". Used both for a
 * percentage-point delta and for a signed gap (e.g. `target_gap_pp`) --
 * both are inherently signed-relative-to-something quantities, unlike
 * a plain rate reading (`formatPercent`, above), which is not
 * force-signed.
 */
export function formatPercentagePoints(value: number | null, fractionDigits = 2): string {
  if (value === null) return "—";
  const magnitude = value.toFixed(fractionDigits);
  return value >= 0 ? `+${magnitude} pp` : `${magnitude} pp`;
}

/**
 * Formats a `ChangeEvent`'s already-numeric `previous_value`/
 * `current_value`/`delta` for display. Presentation only -- the values
 * themselves are exactly what the backend returned.
 */
export function formatMetricValueOrUnavailable(value: number | string | null): string {
  if (value === null) return "Unavailable";
  if (typeof value === "number") return formatPercent(value);
  return value;
}
