/**
 * Selecting the published past curve (Increment #52B).
 *
 * ================================================================
 * THE WHOLE POINT: THIS MODULE SELECTS, IT NEVER COMPUTES
 * ================================================================
 *
 * `/rates` has drawn one curve since #30 and made it selectable in
 * #49B — always for ONE date, `as_of_date`. #52A's audit found that a
 * second curve has been arriving in the same response the entire time
 * and being rendered as scattered basis-point figures.
 *
 * Every `RateLevel` carries `changes[]`, one entry per session window,
 * and each entry publishes `from_date` and `from_value` alongside
 * `change_basis_points`. The decisive fact, verified against the live
 * API in #52A §2, is that **the `from_date` values are identical across
 * all four nominal maturities** for every window:
 *
 *     1 session   2026-09-17   4.67 4.78 4.94 5.29
 *     5 sessions  2026-09-11   4.63 4.78 4.96 5.35
 *     21 sessions 2026-08-19   4.19 4.35 4.65 5.19
 *     63 sessions 2026-06-18   4.19 4.23 4.46 4.90
 *
 * Four published values sharing one published date IS a curve. So the
 * comparison needs no arithmetic at all: it reads `from_value`, plots
 * it, and prints `change_basis_points` as the backend computed it.
 *
 * ================================================================
 * ALIGNMENT IS CHECKED, NOT ASSUMED
 * ================================================================
 *
 * The alignment above is a property of today's data, not a guarantee of
 * the contract. `rates_v1.0` computes each series' windows from that
 * series' own session history, so a maturity that missed a print could
 * legitimately resolve the same window to a different date.
 *
 * Drawing four values from different dates as one curve would be a
 * fabrication — a shape nobody published. So `selectComparison` returns
 * the set of distinct dates it found and the UI refuses to call it one
 * curve unless there is exactly one. There is no interpolation, no
 * nearest-date matching and no carry-forward anywhere in this file.
 *
 * A maturity whose change is unavailable keeps its place in the array
 * with a `null` value, so the caller can BREAK the line there rather
 * than draw through it. `null` is never coerced to `0` — #51B shipped
 * exactly that defect (a null fell into `Math.min`, dropped the axis
 * floor to zero and drew a line to the bottom of the chart, inventing a
 * reading that did not exist).
 *
 * Guarded by `src/test/no-rates-calculation.test.ts` — the filename
 * begins with `rates` precisely so that scan includes it.
 */
import type { ChangeWindow, CurveSpread, RateChange, RateLevel } from "../api/rates.types";

/** The four windows `rates_v1.0` publishes, in the order they read. */
export const COMPARISON_WINDOWS: ReadonlyArray<ChangeWindow> = [
  "1_SESSION",
  "5_SESSIONS",
  "21_SESSIONS",
  "63_SESSIONS",
];

/** One maturity's published reading on the comparison date. */
export interface ComparisonPoint {
  seriesId: string;
  /** The backend's `from_value`. `null` when that window is unavailable. */
  value: number | null;
  /** The backend's `from_date`. `null` when that window is unavailable. */
  date: string | null;
  /** The backend's `change_basis_points`, rendered verbatim. */
  changeBasisPoints: number | null;
  available: boolean;
}

export interface CurveComparison {
  window: ChangeWindow;
  points: ComparisonPoint[];
  /**
   * The single date every available point shares, or `null` when the
   * points disagree. `null` means "do not draw this as one curve".
   */
  sharedDate: string | null;
  /** Every distinct `from_date` seen. Length > 1 is a genuine misalignment. */
  distinctDates: string[];
  /** Maturities whose reading is missing for this window. */
  unavailableSeriesIds: string[];
  /** At least two available points — fewer cannot form a line segment. */
  drawable: boolean;
}

function changeFor(changes: RateChange[], window: ChangeWindow): RateChange | undefined {
  return changes.find((change) => change.window === window);
}

/**
 * Build the past curve for one window from the levels already on screen.
 *
 * Reads four fields and copies them. That is the entire operation.
 */
export function selectComparison(levels: RateLevel[], window: ChangeWindow): CurveComparison {
  const points: ComparisonPoint[] = levels.map((level) => {
    const change = changeFor(level.changes, window);
    const available = change !== undefined && change.available && change.from_value !== null;
    return {
      seriesId: level.series_id,
      value: available ? change.from_value : null,
      date: available ? change.from_date : null,
      changeBasisPoints: change?.change_basis_points ?? null,
      available,
    };
  });

  const distinctDates = [
    ...new Set(points.filter((point) => point.date !== null).map((point) => point.date as string)),
  ].sort();

  return {
    window,
    points,
    sharedDate: distinctDates.length === 1 ? (distinctDates[0] as string) : null,
    distinctDates,
    unavailableSeriesIds: points.filter((point) => !point.available).map((point) => point.seriesId),
    drawable: points.filter((point) => point.available).length >= 2,
  };
}

/**
 * Whether a window can be offered at all: at least one maturity has a
 * published reading for it. A window nothing published is not a choice.
 */
export function comparisonAvailable(levels: RateLevel[], window: ChangeWindow): boolean {
  return levels.some((level) => {
    const change = changeFor(level.changes, window);
    return change !== undefined && change.available && change.from_value !== null;
  });
}

/**
 * The direction every maturity moved, as a single classification.
 *
 * A sign test over values the backend computed — the same class of
 * operation as `changeDirection` in `lib/ratesFormat.ts`, which has
 * read the sign of `change_basis_points` since #30. Nothing is
 * subtracted, summed or averaged here: `MIXED` is simply the case where
 * the published signs disagree, and it is reported rather than
 * smoothed into a single direction that no field supports.
 */
export type LevelShift = "ALL_HIGHER" | "ALL_LOWER" | "MIXED" | "UNCHANGED" | "UNAVAILABLE";

export function levelShift(comparison: CurveComparison): LevelShift {
  const known = comparison.points
    .map((point) => point.changeBasisPoints)
    .filter((value): value is number => value !== null);
  if (known.length === 0) return "UNAVAILABLE";
  if (known.every((value) => value > 0)) return "ALL_HIGHER";
  if (known.every((value) => value < 0)) return "ALL_LOWER";
  if (known.every((value) => value === 0)) return "UNCHANGED";
  return "MIXED";
}

/**
 * The spread whose published `from_value`/`to_value` describe the SHAPE
 * change for a window.
 *
 * 2s30s spans the widest part of the curve MacroChipz ingests, so it is
 * the one that answers "did the gap between short and long widen?".
 *
 * Returning the backend's own change entry — rather than a number
 * computed here — is what keeps the shape sentence clear of
 * `no-rates-calculation`. The alternative, subtracting the 2-year from
 * the 30-year on two dates, is exactly the operation that guard exists
 * to prevent, and it is not needed: the backend already published it.
 */
export function shapeChange(spreads: CurveSpread[], window: ChangeWindow): RateChange | null {
  const spread = spreads.find((entry) => entry.spread_id === "2s30s");
  if (spread === undefined || !spread.available) return null;
  const change = changeFor(spread.changes, window);
  if (change === undefined || !change.available) return null;
  if (change.from_value === null || change.to_value === null) return null;
  return change;
}
