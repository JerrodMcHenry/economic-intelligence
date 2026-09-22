/**
 * Presentation-only formatting for the Housing world (Increment #45).
 *
 * HARD BOUNDARY, the same one `lib/ratesFormat.ts` holds: nothing here
 * performs an economic calculation. There is no subtraction of two
 * figures, no percentage derived from two values, no annualisation and
 * no de-annualisation. Every number the Housing page renders is one the
 * backend already computed; these functions only decide how it reads.
 *
 * ================================================================
 * THE ONE RULE THIS MODULE EXISTS TO ENFORCE
 * ================================================================
 *
 * A seasonally adjusted annual rate and a monthly count are formatted
 * DIFFERENTLY, because they mean different things, and the words around
 * a figure are the only thing standing between a reader and the
 * conclusion that 1,394,000 homes were built in August.
 *
 * So `formatHousingUnits` takes the unit, and every caller passes the
 * measure's own `unit` field rather than assuming one. A figure without
 * its unit's framing is not a smaller mistake here — it is the mistake.
 */

import type { HousingMeasure, HousingStageId, HousingUnit } from "../api/housing.types";

/**
 * 1394000 -> "1,394,000". Grouped, never abbreviated to "1.4M": the
 * published figure is exact and a reader comparing it with Census's own
 * release should see the same digits.
 *
 * `null` renders as an em dash, never "0" — a missing count and a count
 * of zero are different economic facts.
 */
export function formatHousingUnits(value: number | null): string {
  if (value === null) return "—";
  return Math.round(value).toLocaleString("en-US");
}

/**
 * The words that must accompany a figure in each unit.
 *
 * `annualRate` deliberately does not contain the word "homes" on its
 * own: "1,394,000 homes" is precisely the sentence this page must not
 * say about an annual rate.
 */
export function unitCaption(unit: HousingUnit): string {
  return unit === "HOUSING_UNITS_ANNUAL_RATE" ? "at an annual rate" : "homes, that month";
}

/** A short label for the unit, for table headers and chart captions. */
export function unitLabel(unit: HousingUnit): string {
  return unit === "HOUSING_UNITS_ANNUAL_RATE" ? "Annual rate" : "Actual homes";
}

/**
 * The consumer name of a pipeline stage, and the plain sentence
 * defining it.
 *
 * These are the definitions #45 asked for, in the reader's words rather
 * than Census's: "Start of construction occurs when excavation begins
 * for the footings or foundation of a building" is accurate and is not
 * how anyone speaks. The precise Census definitions remain one click
 * away in the explainer.
 */
export const STAGE_COPY: Readonly<
  Record<HousingStageId, { readonly name: string; readonly meaning: string; readonly detail: string }>
> = {
  PERMITS: {
    name: "Permits",
    meaning: "Homes authorised for construction.",
    detail: "A local authority has approved the build. Nothing has been dug yet.",
  },
  STARTS: {
    name: "Starts",
    meaning: "Homes where construction has begun.",
    detail: "Ground has been broken — Census counts a start when excavation for the foundation begins.",
  },
  COMPLETIONS: {
    name: "Completions",
    meaning: "Homes finished.",
    detail: "The home is done and ready to be lived in.",
  },
};

/**
 * "+39,000" / "-39,000" / "no change".
 *
 * Signed, because direction is the point, and spelled out at zero
 * because "+0" reads as a rounding artefact rather than as a real
 * unchanged figure. The SIGN is all this returns — no word like "rose"
 * or "improved", because a change in housing figures is neither good
 * nor bad and MacroChipz's methodology says nothing about it.
 */
export function formatHousingChange(value: number | null): string {
  if (value === null) return "—";
  const rounded = Math.round(value);
  if (rounded === 0) return "no change";
  return `${rounded > 0 ? "+" : "−"}${Math.abs(rounded).toLocaleString("en-US")}`;
}

/** "-2.7%" / "+3.5%". `null` -> an em dash, never "0%". */
export function formatHousingPercent(value: number | null): string {
  if (value === null) return "—";
  const rounded = Number(value.toFixed(1));
  if (rounded === 0) return "0.0%";
  return `${rounded > 0 ? "+" : "−"}${Math.abs(rounded).toFixed(1)}%`;
}

/**
 * Whether a measure has enough for the page to show a comparison at
 * all. A predicate over already-computed fields — it decides what to
 * RENDER, never what is true.
 */
export function hasPreviousComparison(measure: HousingMeasure): boolean {
  return measure.available && measure.previous_period !== null && measure.change_from_previous !== null;
}

export function hasYearAgoComparison(measure: HousingMeasure): boolean {
  return measure.available && measure.year_ago_period !== null && measure.change_from_year_ago !== null;
}
