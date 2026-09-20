/**
 * TypeScript mirror of `app/models/rates.py` -- the canonical
 * `rates_v1.0` response contract (Increment #29), consumed by the Rates
 * Intelligence UI (#30).
 *
 * Field-for-field, name-for-name. Nothing here reshapes, renames, or
 * reinterprets a backend field: if the backend calls it
 * `compensation_percent`, so does this file. Every number arrives
 * already computed -- the frontend's only job is formatting (see
 * lib/ratesFormat.ts) and layout.
 *
 * Two structurally distinct provenance shapes, deliberately not unified:
 * a value the provider published (`SourceProvenance`) and a value this
 * product derived (`DerivedProvenance`) are different kinds of fact, and
 * the UI must never present the second as though Treasury published it.
 */

/** Change windows are counted in published sessions, never calendar days. */
export type ChangeWindow = "1_SESSION" | "5_SESSIONS" | "21_SESSIONS" | "63_SESSIONS";

export type MetricKind = "SOURCE_OBSERVATION" | "DERIVED";

export type SpreadId = "2s10s" | "2s30s";

export type CompensationId = "5Y" | "10Y";

/** Why a derived metric could not be computed. Never a fabricated zero. */
export type UnavailableReason =
  | "NO_OBSERVATIONS_FOR_EITHER_SERIES"
  | "NO_OBSERVATIONS_FOR_ONE_SERIES"
  | "NO_EXACTLY_SHARED_OBSERVATION_DATE";

export interface SourceProvenance {
  provider: string;
  dataset: string;
  series_id: string;
  observation_date: string;
  source_url: string;
  retrieved_at: string;
  revision_count: number;
  last_revised_at: string | null;
}

export interface DerivedProvenance {
  methodology_id: string;
  calculation: string;
  input_series_ids: string[];
  input_observation_date: string;
  calculated_at: string;
}

export interface RateChange {
  window: ChangeWindow;
  sessions: number;
  available: boolean;
  change_basis_points: number | null;
  from_date: string | null;
  from_value: number | null;
  to_date: string | null;
  to_value: number | null;
}

export interface HistoricalContext {
  available: boolean;
  window: ChangeWindow;
  observation_count: number;
  history_start_date: string | null;
  history_end_date: string | null;
  /** Rank of the current change in SIGNED terms. Distinct from the next field. */
  percentile_rank: number | null;
  /** Rank of the current change by ABSOLUTE size. Never conflate the two. */
  magnitude_percentile_rank: number | null;
  minimum_change_basis_points: number | null;
  maximum_change_basis_points: number | null;
}

export interface RateLevel {
  series_id: string;
  title: string;
  units: string;
  kind: MetricKind;
  available: boolean;
  latest_date: string | null;
  latest_value: number | null;
  changes: RateChange[];
  historical_context: HistoricalContext;
  provenance: SourceProvenance | null;
}

export interface CurveSpread {
  spread_id: SpreadId;
  title: string;
  kind: MetricKind;
  available: boolean;
  observation_date: string | null;
  spread_basis_points: number | null;
  long_series_id: string;
  short_series_id: string;
  long_value: number | null;
  short_value: number | null;
  unavailable_reason: UnavailableReason | null;
  changes: RateChange[];
  historical_context: HistoricalContext;
  provenance: DerivedProvenance | null;
}

export interface InflationCompensation {
  maturity: CompensationId;
  title: string;
  kind: MetricKind;
  available: boolean;
  observation_date: string | null;
  compensation_percent: number | null;
  nominal_series_id: string;
  real_series_id: string;
  nominal_value: number | null;
  real_value: number | null;
  unavailable_reason: UnavailableReason | null;
  changes: RateChange[];
  historical_context: HistoricalContext;
  provenance: DerivedProvenance | null;
}

export interface RatesMonitorResult {
  methodology_id: string;
  data_basis: string;
  provider: string;
  attribution: string;
  as_of_date: string | null;
  nominal_curve: RateLevel[];
  real_curve: RateLevel[];
  curve_spreads: CurveSpread[];
  inflation_compensation: InflationCompensation[];
}
