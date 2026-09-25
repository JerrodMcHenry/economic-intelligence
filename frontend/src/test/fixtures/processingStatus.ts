/**
 * Deterministic test fixtures shaped exactly like the real backend
 * response models (see ../../api/processingStatus.types.ts). Fixture
 * data only -- nothing here calculates anything.
 */
import type {
  DetectedAnalysisChange,
  DetectedObservationChange,
  LatestCheck,
  ReleaseContext,
  ReleaseProcessingStatusItem,
  ReleaseProcessingStatusResponse,
} from "../../api/processingStatus.types";
import type { PaginationMeta } from "../../api/releases.types";

export function buildReleaseContext(overrides: Partial<ReleaseContext> = {}): ReleaseContext {
  return {
    release_id: 1,
    name: "Personal Income and Outlays",
    provider: "BEA",
    provider_release_id: "pio",
    ...overrides,
  };
}

export function buildLatestCheck(overrides: Partial<LatestCheck> = {}): LatestCheck {
  return { status: "NO_CHANGE", checked_at: "2026-09-01T14:30:00+00:00", ...overrides };
}

export function buildDetectedObservationChange(overrides: Partial<DetectedObservationChange> = {}): DetectedObservationChange {
  return {
    series_id: "PCEPILFE",
    series_title: "Core PCE Price Index",
    units: "Index 2017=100",
    change_type: "REVISED",
    observation_date: "2026-07-01",
    previous_value: 120.0,
    new_value: 121.5,
    detected_at: "2026-09-01T14:30:00+00:00",
    ...overrides,
  };
}

export function buildDetectedAnalysisChange(overrides: Partial<DetectedAnalysisChange> = {}): DetectedAnalysisChange {
  return {
    component: "PRIMARY_MOMENTUM",
    event_type: "METRIC_CHANGED",
    field: "r_3m_annualized",
    previous_value: "2.10",
    current_value: "2.55",
    delta: 0.45,
    evaluation_period: "2026-07-01",
    methodology_id: "inflation_v1.0",
    data_basis: "revised",
    recorded_at: "2026-09-01T14:30:00+00:00",
    ...overrides,
  };
}

export function buildReleaseProcessingStatusItem(overrides: Partial<ReleaseProcessingStatusItem> = {}): ReleaseProcessingStatusItem {
  return {
    occurrence_id: 1,
    release: buildReleaseContext(),
    scheduled_date: "2026-08-29",
    latest_check: buildLatestCheck(),
    detected_observation_changes: [],
    detected_analysis_changes: [],
    ...overrides,
  };
}

export function buildProcessingStatusPaginationMeta(overrides: Partial<PaginationMeta> = {}): PaginationMeta {
  return { limit: 20, offset: 0, returned: 1, total: 1, ...overrides };
}

export function buildReleaseProcessingStatusResponse(
  overrides: Partial<ReleaseProcessingStatusResponse> = {},
): ReleaseProcessingStatusResponse {
  const occurrences = overrides.occurrences ?? [buildReleaseProcessingStatusItem()];
  return {
    occurrences,
    pagination: buildProcessingStatusPaginationMeta({ returned: occurrences.length, total: occurrences.length }),
    ...overrides,
  };
}
