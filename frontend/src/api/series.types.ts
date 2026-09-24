/**
 * TypeScript mirror of the canonical series-observations response
 * (`GET /api/v1/series/{series_id}/observations`).
 *
 * Field-for-field, name-for-name, verified against the live response.
 * This file derives nothing: an observation is the provider's own
 * published value at a date, and the frontend's only job is to plot it.
 *
 * WHAT THIS ENDPOINT IS NOT. It is not a monitor and carries no
 * methodology, no state, and no rate. A rate computed from these
 * observations by the frontend would be exactly the client-side
 * economics `src/test/no-inflation-derivation.test.ts` and its siblings
 * exist to prevent (Increment #50B).
 */

export interface SeriesObservation {
  date: string;
  value: number;
}

export interface SeriesObservationsResponse {
  series_id: string;
  /** The provider's own title, e.g. "…(Chain-Type Price Index)". */
  title: string;
  /** e.g. "Index 2017=100". Displayed, never converted. */
  units: string;
  source: string;
  observations: SeriesObservation[];
  pagination: { limit: number; offset: number; returned: number; total: number };
}
