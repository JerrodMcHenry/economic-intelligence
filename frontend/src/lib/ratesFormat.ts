/**
 * Presentation-only formatting for the Rates Intelligence UI
 * (Increment #30).
 *
 * HARD BOUNDARY, enforced by `src/test/no-rates-calculation.test.ts`:
 * nothing in this module (or anywhere in the frontend) performs a
 * financial or economic calculation. There is no subtraction of two
 * yields, no basis-point conversion, no percentile computation, no
 * spread, no compensation. Every number rendered by the Rates page is
 * a number the backend already computed under `rates_v1.0`; these
 * functions only decide how it reads.
 *
 * The one arithmetic operation this module does perform is
 * `percentile * 100` for display ("0.566" -> "57th"), which is unit
 * formatting of an already-computed rank, not a derivation -- the same
 * class of operation as rendering 0.25 as "25%".
 */

import type { ChangeWindow, UnavailableReason } from "../api/rates.types";

const MONTH_ABBREVIATIONS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

/**
 * "2026-09-18" -> "Sep 18, 2026". Parses the ISO string's digits
 * directly rather than via `Date`, for the same timezone-safety reason
 * `lib/format.ts`'s `formatPeriod` does: a UTC-midnight instant
 * rendered in a timezone behind UTC silently shows the previous day.
 *
 * Rates are DAILY facts, so this is day-precision -- unlike
 * `formatPeriod`, which renders month-precision economic periods.
 */
export function formatObservationDate(value: string | null): string {
  if (value === null) return "No data available";
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!match) return value;
  const [, year, month, day] = match;
  const monthName = MONTH_ABBREVIATIONS[Number(month) - 1];
  if (!monthName) return value;
  return `${monthName} ${Number(day)}, ${year}`;
}

/** "2026-09-19T17:04:54.461189-07:00" -> "Sep 19, 2026". Date part only. */
export function formatRetrievedAt(value: string | null): string {
  return formatObservationDate(value);
}

/**
 * A yield or compensation level: 4.76 -> "4.76%". `null` renders as an
 * em dash -- never "0.00%", which would read as a real reading of zero.
 */
export function formatRateValue(value: number | null, fractionDigits = 2): string {
  if (value === null) return "—";
  return `${value.toFixed(fractionDigits)}%`;
}

/**
 * A signed change in basis points: 25 -> "+25 bp", -2 -> "−2 bp",
 * 0 -> "0 bp" (unsigned, because zero has no direction).
 *
 * Uses a true minus sign (U+2212) rather than a hyphen so a negative
 * figure reads correctly at a glance and aligns in a tabular column.
 * `null` renders as an em dash, never "0 bp".
 */
export function formatBasisPoints(value: number | null): string {
  if (value === null) return "—";
  const rounded = Number(value.toFixed(1));
  const magnitude = Number.isInteger(rounded) ? String(Math.abs(rounded)) : Math.abs(rounded).toFixed(1);
  if (rounded > 0) return `+${magnitude} bp`;
  if (rounded < 0) return `−${magnitude} bp`;
  return "0 bp";
}

/** An unsigned basis-point level, for a spread: 25 -> "25 bp", -8 -> "−8 bp". */
export function formatBasisPointLevel(value: number | null): string {
  if (value === null) return "—";
  const rounded = Number(value.toFixed(1));
  const magnitude = Number.isInteger(rounded) ? String(Math.abs(rounded)) : Math.abs(rounded).toFixed(1);
  return rounded < 0 ? `−${magnitude} bp` : `${magnitude} bp`;
}

/**
 * The direction of a change, for choosing a neutral visual treatment
 * and an accessible text label. Deliberately NOT "good"/"bad": a rising
 * yield is neither, and `rates_v1.0` assigns no such meaning.
 */
export type ChangeDirection = "up" | "down" | "flat" | "unavailable";

export function changeDirection(changeBasisPoints: number | null): ChangeDirection {
  if (changeBasisPoints === null) return "unavailable";
  if (changeBasisPoints > 0) return "up";
  if (changeBasisPoints < 0) return "down";
  return "flat";
}

/** Screen-reader text for a direction, so meaning never depends on color or a glyph alone. */
export function describeDirection(direction: ChangeDirection): string {
  switch (direction) {
    case "up":
      return "higher";
    case "down":
      return "lower";
    case "flat":
      return "unchanged";
    case "unavailable":
      return "not available";
  }
}

/**
 * Window labels preserve the backend's SESSION semantics exactly.
 * `rates_v1.0` §4 counts published sessions, not calendar days, so
 * "21 sessions" is never relabelled "1 month" -- the equivalence does
 * not hold across holidays and missing prints, and the methodology
 * explicitly refuses it.
 */
const WINDOW_LABELS: Record<ChangeWindow, string> = {
  "1_SESSION": "1 session",
  "5_SESSIONS": "5 sessions",
  "21_SESSIONS": "21 sessions",
  "63_SESSIONS": "63 sessions",
};

export function formatChangeWindow(window: ChangeWindow): string {
  return WINDOW_LABELS[window];
}

/**
 * An already-computed rank (0..1) as an ordinal for display:
 * 0.566 -> "57th". Rounds to the nearest whole percentile; 0 and 1
 * become "0th" and "100th" rather than being clamped away, because both
 * are genuine, meaningful outcomes of the backend's strict-comparison
 * ranking.
 */
export function formatPercentileOrdinal(rank: number | null): string {
  if (rank === null) return "—";
  const percentile = Math.round(rank * 100);
  const lastTwo = percentile % 100;
  const last = percentile % 10;
  let suffix = "th";
  if (lastTwo < 11 || lastTwo > 13) {
    if (last === 1) suffix = "st";
    else if (last === 2) suffix = "nd";
    else if (last === 3) suffix = "rd";
  }
  return `${percentile}${suffix}`;
}

/**
 * Plain-language text for why a derived metric is unavailable. Each
 * maps one backend reason code to one sentence -- no reason is invented
 * and no case falls through to a vague default.
 */
const UNAVAILABLE_REASON_TEXT: Record<UnavailableReason, string> = {
  NO_OBSERVATIONS_FOR_EITHER_SERIES: "Neither input series has been ingested yet.",
  NO_OBSERVATIONS_FOR_ONE_SERIES: "One of the two input series has no observations yet.",
  NO_EXACTLY_SHARED_OBSERVATION_DATE:
    "The two input series have no observation on the same date, so this value is not calculated rather than estimated.",
};

export function describeUnavailableReason(reason: UnavailableReason | null): string {
  if (reason === null) return "This value is not available.";
  return UNAVAILABLE_REASON_TEXT[reason];
}

/**
 * A short maturity label for a canonical series id: "UST_NOMINAL_10Y"
 * -> "10Y". Pure string handling over an identifier the backend owns.
 */
export function maturityLabel(seriesId: string): string {
  const match = /_(\d+Y)$/.exec(seriesId);
  return match?.[1] ?? seriesId;
}
