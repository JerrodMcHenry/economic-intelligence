/**
 * Deterministic test fixtures shaped exactly like the real backend
 * response models (see ../../api/inflation.types.ts). Every builder
 * returns a complete, valid object with sensible defaults; tests
 * override only the fields a given scenario cares about. Values here
 * are fixture data, not economic logic -- nothing in this file
 * calculates anything.
 */
import type {
  ChangeEvent,
  ConfirmationResult,
  ConfirmationSectionChanges,
  HeadlineContextResult,
  InflationCoverage,
  InflationMetricEvidence,
  InflationMonitorResult,
  InflationPeriods,
  InflationWhatChangedResult,
  SeriesMomentumResult,
  SeriesMomentumSectionChanges,
  TargetResult,
  TargetSectionChanges,
} from "../../api/inflation.types";

export function buildEvidence(overrides: Partial<InflationMetricEvidence> = {}): InflationMetricEvidence {
  return {
    series_id: "PCEPILFE",
    calculation_period: "2026-07-01",
    transformation: "12m",
    endpoint_date_current: "2026-07-01",
    endpoint_date_past: "2025-07-01",
    endpoint_value_current: 100,
    endpoint_value_past: 97.5,
    value: 2.56,
    methodology_id: "inflation_v1.0",
    data_basis: "latest_revised_data",
    ...overrides,
  };
}

export function buildMomentum(overrides: Partial<SeriesMomentumResult> = {}): SeriesMomentumResult {
  return {
    series_id: "PCEPILFE",
    calculation_period: "2026-07-01",
    latest_observation_period: "2026-07-01",
    latest_valid_state_period: "2026-07-01",
    r_1m_annualized: 2.1,
    r_3m_annualized: 2.3,
    r_6m_annualized: 2.4,
    r_12m: 2.56,
    neutral_band_pp: 0.1,
    lower_boundary: 2.46,
    upper_boundary: 2.66,
    state: "STABLE",
    missing_required_metrics: [],
    evidence_1m: buildEvidence({ transformation: "1m_annualized", value: 2.1 }),
    evidence_3m: buildEvidence({ transformation: "3m_annualized", value: 2.3 }),
    evidence_6m: buildEvidence({ transformation: "6m_annualized", value: 2.4 }),
    evidence_12m: buildEvidence({ transformation: "12m", value: 2.56 }),
    ...overrides,
  };
}

export function buildTarget(overrides: Partial<TargetResult> = {}): TargetResult {
  return {
    series_id: "PCEPI",
    calculation_period: "2026-07-01",
    headline_pce_yoy: 2.7,
    fed_objective_percent: 2.0,
    target_gap_pp: 0.7,
    available: true,
    evidence: buildEvidence({ series_id: "PCEPI", value: 2.7 }),
    ...overrides,
  };
}

export function buildConfirmation(overrides: Partial<ConfirmationResult> = {}): ConfirmationResult {
  return {
    confirmation_latest: buildMomentum({ series_id: "CPILFESL" }),
    primary_at_comparison_period: buildMomentum({ series_id: "PCEPILFE" }),
    confirmation_at_comparison_period: buildMomentum({ series_id: "CPILFESL" }),
    latest_common_period: "2026-07-01",
    relationship: "CONFIRMS",
    ...overrides,
  };
}

export function buildHeadlineContext(overrides: Partial<HeadlineContextResult> = {}): HeadlineContextResult {
  return {
    headline_pce: buildMomentum({ series_id: "PCEPI" }),
    headline_cpi: buildMomentum({ series_id: "CPIAUCSL" }),
    ...overrides,
  };
}

export function buildPeriods(overrides: Partial<InflationPeriods> = {}): InflationPeriods {
  return {
    latest_common_period: "2026-07-01",
    data_through: "2026-07-01",
    ...overrides,
  };
}

export function buildCoverage(overrides: Partial<InflationCoverage> = {}): InflationCoverage {
  return {
    primary_available: true,
    confirmation_available: true,
    target_available: true,
    headline_cpi_available: true,
    ...overrides,
  };
}

export function buildMonitor(overrides: Partial<InflationMonitorResult> = {}): InflationMonitorResult {
  return {
    methodology_id: "inflation_v1.0",
    data_basis: "latest_revised_data",
    target: buildTarget(),
    underlying_momentum: buildMomentum(),
    confirmation: buildConfirmation(),
    headline_context: buildHeadlineContext(),
    periods: buildPeriods(),
    coverage: buildCoverage(),
    ...overrides,
  };
}

export function buildChangeEvent(overrides: Partial<ChangeEvent> = {}): ChangeEvent {
  return {
    component: "PRIMARY_MOMENTUM",
    event_type: "METRIC_CHANGED",
    field: "r_3m_annualized",
    previous_value: 2.1,
    current_value: 2.3,
    delta: 0.2,
    previous_period: "2026-06-01",
    current_period: "2026-07-01",
    methodology_id: "inflation_what_changed_v1.0",
    data_basis: "latest_revised_data",
    ...overrides,
  };
}

export function buildMomentumSectionChanges(overrides: Partial<SeriesMomentumSectionChanges> = {}): SeriesMomentumSectionChanges {
  return {
    comparison_available: true,
    previous_period: "2026-06-01",
    current_period: "2026-07-01",
    previous_evidence: buildMomentum({ calculation_period: "2026-06-01" }),
    current_evidence: buildMomentum({ calculation_period: "2026-07-01" }),
    changes: [],
    metric_changed: false,
    state_changed: false,
    availability_lost: false,
    availability_restored: false,
    ...overrides,
  };
}

export function buildTargetSectionChanges(overrides: Partial<TargetSectionChanges> = {}): TargetSectionChanges {
  return {
    comparison_available: true,
    previous_period: "2026-06-01",
    current_period: "2026-07-01",
    previous_evidence: buildTarget({ calculation_period: "2026-06-01" }),
    current_evidence: buildTarget({ calculation_period: "2026-07-01" }),
    changes: [],
    metric_changed: false,
    availability_lost: false,
    availability_restored: false,
    ...overrides,
  };
}

export function buildConfirmationSectionChanges(overrides: Partial<ConfirmationSectionChanges> = {}): ConfirmationSectionChanges {
  return {
    comparison_available: true,
    previous_confirmation_period: "2026-06-01",
    current_confirmation_period: "2026-07-01",
    previous_primary_state: buildMomentum(),
    previous_confirmation_state: buildMomentum({ series_id: "CPILFESL" }),
    previous_relationship: "CONFIRMS",
    current_primary_state: buildMomentum(),
    current_confirmation_state: buildMomentum({ series_id: "CPILFESL" }),
    current_relationship: "CONFIRMS",
    changes: [],
    relationship_changed: false,
    confirmation_availability_lost: false,
    confirmation_availability_restored: false,
    ...overrides,
  };
}

export function buildWhatChanged(overrides: Partial<InflationWhatChangedResult> = {}): InflationWhatChangedResult {
  return {
    methodology_id: "inflation_v1.0",
    comparison_contract_id: "inflation_what_changed_v1.0",
    comparison_type: "MONTH_OVER_MONTH",
    data_basis: "latest_revised_data",
    primary_momentum_changes: buildMomentumSectionChanges(),
    confirmation_changes: buildConfirmationSectionChanges(),
    target_changes: buildTargetSectionChanges(),
    headline_pce_changes: buildMomentumSectionChanges(),
    headline_cpi_changes: buildMomentumSectionChanges(),
    changes: [],
    any_metric_changed: false,
    any_state_changed: false,
    any_availability_changed: false,
    confirmation_changed: false,
    current_monitor_result: null,
    ...overrides,
  };
}
