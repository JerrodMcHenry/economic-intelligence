/**
 * Deterministic test fixtures shaped exactly like the real backend
 * response models (see ../../api/labor.types.ts). Every builder
 * returns a complete, valid object with sensible defaults; tests
 * override only the fields a given scenario cares about. Values here
 * are fixture data, not economic logic -- nothing in this file
 * calculates anything.
 */
import type {
  EmploymentResult,
  EmploymentSectionChanges,
  LaborChangeEvent,
  LaborMonitorResult,
  LaborObservationEvidence,
  LaborWhatChangedResult,
  UnemploymentResult,
  UnemploymentSectionChanges,
} from "../../api/labor.types";

export function buildObservation(overrides: Partial<LaborObservationEvidence> = {}): LaborObservationEvidence {
  return {
    series_id: "PAYEMS",
    observation_date: "2026-07-01",
    value: 157912,
    ...overrides,
  };
}

export function buildEmploymentResult(overrides: Partial<EmploymentResult> = {}): EmploymentResult {
  return {
    series_id: "PAYEMS",
    current_3m_avg_jobs: 150000,
    prior_3m_avg_jobs: 120000,
    momentum_delta_jobs: 30000,
    condition_deadband_jobs: 50000,
    momentum_deadband_jobs: 50000,
    condition: "EXPANDING",
    momentum: "STEADY",
    state: "EXPANDING",
    observations: [
      buildObservation({ observation_date: "2026-01-01" }),
      buildObservation({ observation_date: "2026-02-01" }),
      buildObservation({ observation_date: "2026-03-01" }),
      buildObservation({ observation_date: "2026-04-01" }),
      buildObservation({ observation_date: "2026-05-01" }),
      buildObservation({ observation_date: "2026-06-01" }),
      buildObservation({ observation_date: "2026-07-01" }),
    ],
    ...overrides,
  };
}

export function buildUnemploymentResult(overrides: Partial<UnemploymentResult> = {}): UnemploymentResult {
  return {
    series_id: "UNRATE",
    current_3m_avg: 4.0,
    prior_year_3m_avg: 4.1,
    delta_pp: -0.1,
    unemployment_deadband_pp: 0.2,
    state: "STABLE",
    observations: [
      buildObservation({ series_id: "UNRATE", observation_date: "2026-05-01", value: 4.0 }),
      buildObservation({ series_id: "UNRATE", observation_date: "2026-06-01", value: 4.0 }),
      buildObservation({ series_id: "UNRATE", observation_date: "2026-07-01", value: 4.0 }),
      buildObservation({ series_id: "UNRATE", observation_date: "2025-05-01", value: 4.1 }),
      buildObservation({ series_id: "UNRATE", observation_date: "2025-06-01", value: 4.1 }),
      buildObservation({ series_id: "UNRATE", observation_date: "2025-07-01", value: 4.1 }),
    ],
    ...overrides,
  };
}

export function buildLaborMonitor(overrides: Partial<LaborMonitorResult> = {}): LaborMonitorResult {
  return {
    methodology_id: "labor_v1.0",
    data_basis: "latest_revised_data",
    state: "STRENGTHENING",
    evaluation_period: "2026-07-01",
    employment: buildEmploymentResult(),
    unemployment: buildUnemploymentResult(),
    ...overrides,
  };
}

export function buildLaborChangeEvent(overrides: Partial<LaborChangeEvent> = {}): LaborChangeEvent {
  return {
    component: "EMPLOYMENT",
    event_type: "METRIC_CHANGED",
    field: "current_3m_avg_jobs",
    previous_value: 120000,
    current_value: 150000,
    delta: 30000,
    previous_period: "2026-06-01",
    current_period: "2026-07-01",
    methodology_id: "labor_v1.0",
    data_basis: "latest_revised_data",
    ...overrides,
  };
}

export function buildEmploymentSectionChanges(overrides: Partial<EmploymentSectionChanges> = {}): EmploymentSectionChanges {
  return {
    previous_evidence: buildEmploymentResult(),
    current_evidence: buildEmploymentResult(),
    changes: [],
    state_changed: false,
    metric_changed: false,
    availability_lost: false,
    availability_restored: false,
    ...overrides,
  };
}

export function buildUnemploymentSectionChanges(overrides: Partial<UnemploymentSectionChanges> = {}): UnemploymentSectionChanges {
  return {
    previous_evidence: buildUnemploymentResult(),
    current_evidence: buildUnemploymentResult(),
    changes: [],
    state_changed: false,
    metric_changed: false,
    availability_lost: false,
    availability_restored: false,
    ...overrides,
  };
}

export function buildLaborWhatChanged(overrides: Partial<LaborWhatChangedResult> = {}): LaborWhatChangedResult {
  return {
    methodology_id: "labor_v1.0",
    comparison_contract_id: "labor_what_changed_v1.0",
    comparison_type: "MONTH_OVER_MONTH",
    data_basis: "latest_revised_data",
    comparison_available: true,
    previous_period: "2026-06-01",
    current_period: "2026-07-01",
    previous_labor_state: "STRENGTHENING",
    current_labor_state: "STRENGTHENING",
    employment_changes: buildEmploymentSectionChanges(),
    unemployment_changes: buildUnemploymentSectionChanges(),
    changes: [],
    any_state_changed: false,
    any_metric_changed: false,
    any_availability_changed: false,
    current_labor_result: null,
    ...overrides,
  };
}

/**
 * Published observations for the two Jobs surveys (#51B).
 *
 * `UNRATE` deliberately carries a NULL in the middle, because the live
 * series does (2025-10-01) and because a null coerced to zero is the
 * defect this fixture exists to keep out: it destroys the axis floor
 * AND draws a value the provider never published.
 */
export function buildPayrollObservations(
  overrides: Partial<import("../../api/series.types").SeriesObservationsResponse> = {},
): import("../../api/series.types").SeriesObservationsResponse {
  const observations = [
    { date: "2026-03-01", value: 158600 },
    { date: "2026-04-01", value: 158750 },
    { date: "2026-05-01", value: 158880 },
    { date: "2026-06-01", value: 158960 },
    { date: "2026-07-01", value: 159020 },
    { date: "2026-08-01", value: 159075 },
  ];
  return {
    series_id: "PAYEMS",
    title: "All Employees, Total Nonfarm",
    units: "Thousands of Persons",
    source: "FRED",
    observations,
    pagination: { limit: 200, offset: 0, returned: observations.length, total: observations.length },
    ...overrides,
  };
}

export function buildUnemploymentObservations(
  overrides: Partial<import("../../api/series.types").SeriesObservationsResponse> = {},
): import("../../api/series.types").SeriesObservationsResponse {
  const observations = [
    { date: "2026-03-01", value: 4.3 },
    { date: "2026-04-01", value: 4.2 },
    { date: "2026-05-01", value: null },
    { date: "2026-06-01", value: 4.2 },
    { date: "2026-07-01", value: 4.1 },
    { date: "2026-08-01", value: 4.1 },
  ] as Array<{ date: string; value: number | null }>;
  return {
    series_id: "UNRATE",
    title: "Unemployment Rate",
    units: "Percent",
    source: "FRED",
    observations: observations as Array<{ date: string; value: number }>,
    pagination: { limit: 200, offset: 0, returned: observations.length, total: observations.length },
    ...overrides,
  };
}
