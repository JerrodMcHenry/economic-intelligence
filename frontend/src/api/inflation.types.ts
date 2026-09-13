/**
 * TypeScript mirror of the backend's canonical Inflation Monitor and
 * "What Changed?" Pydantic response models
 * (app/models/inflation.py, app/models/inflation_what_changed.py).
 *
 * This file types the JSON shape only -- it derives nothing. Every
 * field name, optionality, and enum below is copied field-for-field
 * from the real backend models (verified by inspection, not guessed).
 * Do not add, rename, or infer a field that isn't in those models; if
 * the UI needs something these types don't have, that's a backend gap
 * to report, not a reason to invent a client-side field.
 *
 * Dates are ISO date strings ("YYYY-MM-DD"), exactly as FastAPI/Pydantic
 * serializes a Python `date`.
 */

// --- inflation_v1.0 (app/models/inflation.py) ---

export type InflationState = "COOLING" | "HEATING" | "STABLE" | "MIXED" | "INSUFFICIENT_DATA";
export type ConfirmationRelationship = "CONFIRMS" | "DIVERGES" | "INCONCLUSIVE" | "UNAVAILABLE";
export type InflationTransformation = "1m_annualized" | "3m_annualized" | "6m_annualized" | "12m";

export interface InflationMetricEvidence {
  series_id: string;
  calculation_period: string;
  transformation: InflationTransformation;
  endpoint_date_current: string;
  endpoint_date_past: string;
  endpoint_value_current: number | null;
  endpoint_value_past: number | null;
  value: number | null;
  methodology_id: string;
  data_basis: string;
}

export interface SeriesMomentumResult {
  series_id: string;
  calculation_period: string | null;
  latest_observation_period: string | null;
  latest_valid_state_period: string | null;
  r_1m_annualized: number | null;
  r_3m_annualized: number | null;
  r_6m_annualized: number | null;
  r_12m: number | null;
  neutral_band_pp: number;
  lower_boundary: number | null;
  upper_boundary: number | null;
  state: InflationState;
  missing_required_metrics: string[];
  evidence_1m: InflationMetricEvidence | null;
  evidence_3m: InflationMetricEvidence | null;
  evidence_6m: InflationMetricEvidence | null;
  evidence_12m: InflationMetricEvidence | null;
}

export interface TargetResult {
  series_id: string;
  calculation_period: string | null;
  headline_pce_yoy: number | null;
  fed_objective_percent: number;
  target_gap_pp: number | null;
  available: boolean;
  evidence: InflationMetricEvidence | null;
}

export interface ConfirmationResult {
  confirmation_latest: SeriesMomentumResult;
  primary_at_comparison_period: SeriesMomentumResult | null;
  confirmation_at_comparison_period: SeriesMomentumResult | null;
  latest_common_period: string | null;
  relationship: ConfirmationRelationship;
}

export interface HeadlineContextResult {
  headline_pce: SeriesMomentumResult;
  headline_cpi: SeriesMomentumResult;
}

export interface InflationPeriods {
  latest_common_period: string | null;
  data_through: string | null;
}

export interface InflationCoverage {
  primary_available: boolean;
  confirmation_available: boolean;
  target_available: boolean;
  headline_cpi_available: boolean;
}

export interface InflationMonitorResult {
  methodology_id: string;
  data_basis: string;
  target: TargetResult;
  underlying_momentum: SeriesMomentumResult;
  confirmation: ConfirmationResult;
  headline_context: HeadlineContextResult;
  periods: InflationPeriods;
  coverage: InflationCoverage;
}

// --- inflation_what_changed_v1.0 (app/models/inflation_what_changed.py) ---

export type ChangeComponent = "PRIMARY_MOMENTUM" | "CONFIRMATION" | "TARGET" | "HEADLINE_PCE" | "HEADLINE_CPI";
export type ChangeEventType =
  | "METRIC_CHANGED"
  | "STATE_CHANGED"
  | "AVAILABILITY_LOST"
  | "AVAILABILITY_RESTORED"
  | "CONFIRMATION_CHANGED";

export interface ChangeEvent {
  component: ChangeComponent;
  event_type: ChangeEventType;
  field: string;
  previous_value: number | string | null;
  current_value: number | string | null;
  delta: number | null;
  previous_period: string | null;
  current_period: string | null;
  methodology_id: string;
  data_basis: string;
}

export interface SeriesMomentumSectionChanges {
  comparison_available: boolean;
  previous_period: string | null;
  current_period: string | null;
  previous_evidence: SeriesMomentumResult | null;
  current_evidence: SeriesMomentumResult | null;
  changes: ChangeEvent[];
  metric_changed: boolean;
  state_changed: boolean;
  availability_lost: boolean;
  availability_restored: boolean;
}

export interface TargetSectionChanges {
  comparison_available: boolean;
  previous_period: string | null;
  current_period: string | null;
  previous_evidence: TargetResult | null;
  current_evidence: TargetResult | null;
  changes: ChangeEvent[];
  metric_changed: boolean;
  availability_lost: boolean;
  availability_restored: boolean;
}

export interface ConfirmationSectionChanges {
  comparison_available: boolean;
  previous_confirmation_period: string | null;
  current_confirmation_period: string | null;
  previous_primary_state: SeriesMomentumResult | null;
  previous_confirmation_state: SeriesMomentumResult | null;
  previous_relationship: ConfirmationRelationship | null;
  current_primary_state: SeriesMomentumResult | null;
  current_confirmation_state: SeriesMomentumResult | null;
  current_relationship: ConfirmationRelationship | null;
  changes: ChangeEvent[];
  relationship_changed: boolean;
  confirmation_availability_lost: boolean;
  confirmation_availability_restored: boolean;
}

export interface InflationWhatChangedResult {
  methodology_id: string;
  comparison_contract_id: string;
  comparison_type: string;
  data_basis: string;
  primary_momentum_changes: SeriesMomentumSectionChanges;
  confirmation_changes: ConfirmationSectionChanges;
  target_changes: TargetSectionChanges;
  headline_pce_changes: SeriesMomentumSectionChanges;
  headline_cpi_changes: SeriesMomentumSectionChanges;
  changes: ChangeEvent[];
  any_metric_changed: boolean;
  any_state_changed: boolean;
  any_availability_changed: boolean;
  confirmation_changed: boolean;
  current_monitor_result: InflationMonitorResult | null;
}
