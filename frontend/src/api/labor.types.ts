/**
 * TypeScript mirror of the backend's canonical Labor Monitor and "What
 * Changed?" Pydantic response models (app/models/labor.py,
 * app/models/labor_what_changed.py).
 *
 * This file types the JSON shape only -- it derives nothing. Every
 * field name, optionality, and enum below is copied field-for-field
 * from the real backend models AND verified against a live response
 * (see docs/architecture/labor-ui-v1.md §3), not guessed. Do not add,
 * rename, or infer a field that isn't in those models; if the UI needs
 * something these types don't have, that's a backend gap to report,
 * not a reason to invent a client-side field.
 *
 * Dates are ISO date strings ("YYYY-MM-DD"), exactly as FastAPI/Pydantic
 * serializes a Python `date`.
 */

// --- labor_v1.0 (app/models/labor.py) ---

export type EmploymentCondition = "EXPANDING" | "FLAT" | "CONTRACTING" | "INSUFFICIENT_DATA";
export type EmploymentMomentum = "IMPROVING" | "STEADY" | "WORSENING" | "INSUFFICIENT_DATA";
export type EmploymentState = "EXPANDING" | "COOLING" | "STABLE" | "CONTRACTING" | "RECOVERING" | "INSUFFICIENT_DATA";
export type UnemploymentTrendState = "IMPROVING" | "DETERIORATING" | "STABLE" | "INSUFFICIENT_DATA";
export type LaborState = "STRENGTHENING" | "COOLING" | "STABLE" | "MIXED" | "INSUFFICIENT_DATA";

export interface LaborObservationEvidence {
  series_id: string;
  observation_date: string;
  value: number | null;
}

export interface EmploymentResult {
  series_id: string;
  current_3m_avg_jobs: number | null;
  prior_3m_avg_jobs: number | null;
  momentum_delta_jobs: number | null;
  condition_deadband_jobs: number;
  momentum_deadband_jobs: number;
  condition: EmploymentCondition;
  momentum: EmploymentMomentum;
  state: EmploymentState;
  observations: LaborObservationEvidence[];
}

export interface UnemploymentResult {
  series_id: string;
  current_3m_avg: number | null;
  prior_year_3m_avg: number | null;
  delta_pp: number | null;
  unemployment_deadband_pp: number;
  state: UnemploymentTrendState;
  observations: LaborObservationEvidence[];
}

export interface LaborMonitorResult {
  methodology_id: string;
  data_basis: string;
  state: LaborState;
  evaluation_period: string | null;
  employment: EmploymentResult;
  unemployment: UnemploymentResult;
}

// --- labor_what_changed_v1.0 (app/models/labor_what_changed.py) ---

export type LaborChangeComponent = "LABOR" | "EMPLOYMENT" | "UNEMPLOYMENT";
export type LaborChangeEventType = "STATE_CHANGED" | "AVAILABILITY_LOST" | "AVAILABILITY_RESTORED" | "METRIC_CHANGED";

export interface LaborChangeEvent {
  component: LaborChangeComponent;
  event_type: LaborChangeEventType;
  field: string;
  previous_value: number | string | null;
  current_value: number | string | null;
  delta: number | null;
  previous_period: string | null;
  current_period: string | null;
  methodology_id: string;
  data_basis: string;
}

export interface EmploymentSectionChanges {
  previous_evidence: EmploymentResult;
  current_evidence: EmploymentResult;
  changes: LaborChangeEvent[];
  state_changed: boolean;
  metric_changed: boolean;
  availability_lost: boolean;
  availability_restored: boolean;
}

export interface UnemploymentSectionChanges {
  previous_evidence: UnemploymentResult;
  current_evidence: UnemploymentResult;
  changes: LaborChangeEvent[];
  state_changed: boolean;
  metric_changed: boolean;
  availability_lost: boolean;
  availability_restored: boolean;
}

export interface LaborWhatChangedResult {
  methodology_id: string;
  comparison_contract_id: string;
  comparison_type: string;
  data_basis: string;
  comparison_available: boolean;
  previous_period: string | null;
  current_period: string | null;
  previous_labor_state: LaborState;
  current_labor_state: LaborState;
  employment_changes: EmploymentSectionChanges;
  unemployment_changes: UnemploymentSectionChanges;
  changes: LaborChangeEvent[];
  any_state_changed: boolean;
  any_metric_changed: boolean;
  any_availability_changed: boolean;
  current_labor_result: LaborMonitorResult | null;
}
