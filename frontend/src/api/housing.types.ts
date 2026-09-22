/**
 * The Housing read contract (Increment #45).
 *
 * A hand-maintained mirror of `app/models/housing.py`, matching how
 * every other API contract in this directory is declared.
 *
 * ================================================================
 * NOTE WHAT IS NOT HERE
 * ================================================================
 *
 * There is no `state`, no `condition`, no `rating`, no `direction`, no
 * `score` and no `methodology_id`. That is not an omission from the
 * mirror -- the backend contract has none of them, because there is no
 * `housing_v1.0`. A component cannot render a housing state, because
 * nothing in this file could carry one.
 *
 * ================================================================
 * TWO UNITS, AND THE ONE THING A COMPONENT MUST NOT DO WITH THEM
 * ================================================================
 *
 * Each stage arrives twice:
 *
 *   `pace`   HOUSING_UNITS_ANNUAL_RATE -- the seasonally adjusted
 *            annual rate. Comparable month to month. NOT a count of
 *            homes in that month.
 *   `actual` HOUSING_UNITS -- the month's own unadjusted count.
 *
 * A component must branch on `unit`, never on `stage`, when deciding
 * how to word a figure. And it must never compute one from the other:
 * dividing an annual rate by twelve throws away the seasonal adjustment
 * that produced it, and the result is close enough to the real
 * unadjusted figure to look correct while being wrong on principle.
 */

/** The three stages, in pipeline order. An order, not a ranking. */
export type HousingStageId = "PERMITS" | "STARTS" | "COMPLETIONS";

/**
 * The canonical unit of a figure. Load-bearing: the two read completely
 * differently, and mixing them is the most likely way to publish a
 * false number on this page.
 */
export type HousingUnit = "HOUSING_UNITS_ANNUAL_RATE" | "HOUSING_UNITS";

export type HousingSeasonalAdjustment = "SEASONALLY_ADJUSTED" | "NOT_SEASONALLY_ADJUSTED";

/** Where one observation came from. Never an API URL — that would carry a key. */
export interface HousingProvenance {
  readonly provider: string;
  readonly dataset: string;
  /** Census's OWN identifier for the series, e.g. `APERMITS/TOTAL`. */
  readonly provider_series_id: string;
  readonly observation_date: string;
  readonly source_url: string;
  readonly retrieved_at: string;
  readonly revision_count: number;
  readonly last_revised_at: string | null;
}

export interface HousingTrendPoint {
  readonly observation_date: string;
  readonly value: number;
}

/**
 * The bounded recent history behind one measure.
 *
 * `points` contains only published months. A month Census published no
 * usable value for is absent — never interpolated, carried forward or
 * zero-filled — so `available_months` may be smaller than
 * `requested_months`, and the page says so rather than hiding it.
 */
export interface HousingTrend {
  readonly concept_id: string;
  readonly unit: HousingUnit;
  readonly requested_months: number;
  readonly available_months: number;
  readonly points: ReadonlyArray<HousingTrendPoint>;
}

/**
 * One concept's latest published figure and its comparisons.
 *
 * Every comparison is computed by the backend. The frontend renders
 * `change_from_previous`; it never subtracts one field from another
 * (guarded by `src/test/no-economic-logic.test.ts`).
 */
export interface HousingMeasure {
  readonly concept_id: string;
  readonly unit: HousingUnit;
  readonly seasonal_adjustment: HousingSeasonalAdjustment;
  readonly available: boolean;
  readonly unavailable_reason: string | null;

  readonly period: string | null;
  readonly value: number | null;

  readonly previous_period: string | null;
  readonly previous_value: number | null;
  readonly change_from_previous: number | null;
  readonly change_percent_from_previous: number | null;

  readonly year_ago_period: string | null;
  readonly year_ago_value: number | null;
  readonly change_from_year_ago: number | null;
  readonly change_percent_from_year_ago: number | null;

  readonly observation_count: number;
  readonly earliest_period: string | null;

  readonly provenance: HousingProvenance | null;
  readonly trend: HousingTrend | null;
}

export interface HousingStage {
  readonly stage: HousingStageId;
  /** The seasonally adjusted annual rate. */
  readonly pace: HousingMeasure;
  /** The month's own unadjusted count. */
  readonly actual: HousingMeasure;
}

export interface HousingResult {
  readonly contract_version: string;
  readonly data_basis: string;
  readonly provider: string;
  /** Required verbatim by Census's Data API terms. Rendered, never paraphrased. */
  readonly attribution: string;
  readonly source_statement: string;
  readonly source_url: string;

  readonly as_of_period: string | null;
  readonly stages: ReadonlyArray<HousingStage>;
  readonly saar_explanation: string;
  readonly limitations: ReadonlyArray<string>;
}
