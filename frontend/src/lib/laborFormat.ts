/**
 * Presentation-only formatting for Labor Monitor values -- the Labor
 * sibling of `lib/format.ts`. None of these functions decide whether
 * something changed, which state applies, or perform any economic
 * calculation; every input is already a canonical backend value.
 *
 * PAYEMS units (docs/architecture/labor-ui-v1.md §15, load-bearing):
 * `EmploymentResult.current_3m_avg_jobs`/`prior_3m_avg_jobs`/
 * `momentum_delta_jobs` are ALREADY converted to actual jobs by the
 * backend (the x1000 conversion happens exactly once, in
 * `app.domain.labor.build_jobs_index`, before these fields are ever
 * computed) -- `formatJobs` below must NEVER multiply or divide by
 * 1,000 again. Raw `observations[].value` entries are formatted with
 * `formatRawObservationValue`, which never converts either; callers
 * label the unit beside it. (#56B: employment evidence is already in
 * jobs, so its label is "Jobs" -- see components/labor/EvidenceDisclosure.tsx.)
 */
import { formatPercent, formatPercentagePoints } from "./format";
import { isJobCountField, isPercentagePointDeltaField } from "./laborLabels";

/** -331333.33 -> "-331,333". A fractional job has no meaning, so this
 * always rounds to a whole number -- unlike `formatPercent`, which
 * keeps two decimal places. `null` (unavailable) -> an em dash, the
 * same convention every other formatter in this product uses. */
export function formatJobs(value: number | null): string {
  if (value === null) return "—";
  return Math.round(value).toLocaleString(undefined, { maximumFractionDigits: 0 });
}

/**
 * A raw `LaborObservationEvidence.value` for display -- exactly the
 * persisted FRED-native number, comma-grouped, with NO unit suffix and
 * NO conversion applied (see this module's own docstring). Callers are
 * responsible for showing the correct unit label ("thousands of
 * persons" for PAYEMS, "percent" for UNRATE) beside this value, since
 * that label depends on `series_id`, which this formatter deliberately
 * does not need to know about (it only formats the number).
 */
export function formatRawObservationValue(value: number | null): string {
  if (value === null) return "Unavailable";
  return value.toLocaleString(undefined, { maximumFractionDigits: 3 });
}

/**
 * A `LaborChangeEvent.previous_value`/`current_value` for a numeric
 * field, field-aware (docs/architecture/labor-ui-v1.md §16): Employment's
 * three job-count fields use `formatJobs`; Unemployment's `delta_pp`
 * uses the existing signed `formatPercentagePoints`; its other two
 * numeric fields (`current_3m_avg`/`prior_year_3m_avg`) are plain rate
 * percentages and use the existing `formatPercent`. Never applies job
 * formatting to a percentage field or vice versa.
 */
export function formatLaborMetricValue(field: string, value: number | null): string {
  if (value === null) return "Unavailable";
  if (isJobCountField(field)) return formatJobs(value);
  if (isPercentagePointDeltaField(field)) return formatPercentagePoints(value);
  return formatPercent(value);
}
