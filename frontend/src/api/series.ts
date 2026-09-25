import { apiGet } from "./client";
import type { SeriesObservationsResponse } from "./series.types";

/**
 * Published observations for one canonical series (Increment #50B).
 *
 * The Inflation world needs the PRICE LEVEL, not another rate: #50A
 * measured that `/inflation` rendered 41 percentages, zero charts, and
 * never once showed a price — even though the monitor's own evidence
 * already carried the index at both ends of every window.
 *
 * This is an EXISTING endpoint, already serving 59 monthly Core PCE
 * observations. No backend change, no new contract, no new
 * calculation: the frontend plots what the provider published.
 */
const MAX_OBSERVATIONS = 200;

export function getSeriesObservations(seriesId: string): Promise<SeriesObservationsResponse> {
  return apiGet<SeriesObservationsResponse>(
    `/api/v1/series/${encodeURIComponent(seriesId)}/observations?limit=${MAX_OBSERVATIONS}`,
  );
}

/**
 * The series `inflation_v1.0` leads with, and therefore the one the
 * climb draws. Named here rather than at the call site so the page
 * never hardcodes a provider id inline.
 *
 * #56B: these are MacroChipz STORAGE ids (concept ids), not provider
 * ids -- the rows now hold BEA and BLS data. The agency series id
 * (`DPCCRG`, `CES0000000001`, `LNS14000000`) arrives on every
 * observation as `series_id` evidence from the monitor endpoints.
 */
export const CORE_PCE_SERIES_ID = "us.pce.core.price-index.sa.monthly";

export function getCorePceObservations(): Promise<SeriesObservationsResponse> {
  return getSeriesObservations(CORE_PCE_SERIES_ID);
}

/** The employer survey MacroChipz plots on `/jobs` (#51B). */
export const PAYROLL_SERIES_ID = "us.nonfarm.payroll-employment.sa.monthly";
/** The household survey. Carries a published gap; see `SurveyThreshold`. */
export const UNEMPLOYMENT_SERIES_ID = "us.unemployment-rate.sa.monthly";

export function getPayrollObservations(): Promise<SeriesObservationsResponse> {
  return getSeriesObservations(PAYROLL_SERIES_ID);
}

export function getUnemploymentObservations(): Promise<SeriesObservationsResponse> {
  return getSeriesObservations(UNEMPLOYMENT_SERIES_ID);
}
