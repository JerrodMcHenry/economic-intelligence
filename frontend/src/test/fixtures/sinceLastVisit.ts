/**
 * Deterministic test fixtures shaped exactly like the real backend
 * response models (see ../../api/sinceLastVisit.types.ts). Fixture
 * data only -- nothing here calculates anything.
 */
import type {
  DomainRecap,
  Recalculation,
  SinceLastVisitResponse,
  SourceUpdate,
  StructuralChange,
} from "../../api/sinceLastVisit.types";

export function buildStructuralChange(overrides: Partial<StructuralChange> = {}): StructuralChange {
  return {
    monitor: "inflation",
    event_type: "STATE_CHANGED",
    field: "state",
    previous_value: "COOLING",
    current_value: "STABLE",
    evaluation_period: "2026-08-01",
    methodology_id: "inflation_v1.0",
    calculated_at: "2026-09-10T14:30:00Z",
    release_check_run_id: 1,
    ...overrides,
  };
}

export function buildRecalculation(overrides: Partial<Recalculation> = {}): Recalculation {
  return {
    monitor: "inflation",
    kind: "UNCHANGED_CONFIRMATION",
    state: "COOLING",
    evaluation_period: "2026-08-01",
    count: 1,
    calculated_at: "2026-09-10T14:30:00Z",
    methodology_id: "inflation_v1.0",
    ...overrides,
  };
}

export function buildSourceUpdate(overrides: Partial<SourceUpdate> = {}): SourceUpdate {
  return {
    monitor: "inflation",
    series_id: "PCEPILFE",
    series_title: "Core PCE Price Index",
    change_type: "REVISED",
    release_check_run_id: 1,
    ...overrides,
  };
}

export function buildDomainRecap(overrides: Partial<DomainRecap> = {}): DomainRecap {
  return {
    monitor: "inflation",
    coverage: "CHECKED",
    last_checked_at: "2026-09-15T08:04:00Z",
    structural_changes: [],
    recalculations: [],
    source_updates: [],
    ...overrides,
  };
}

export function buildSinceLastVisitResponse(overrides: Partial<SinceLastVisitResponse> = {}): SinceLastVisitResponse {
  return {
    after: "2026-09-08T00:00:00Z",
    through: "2026-09-15T09:00:00Z",
    first_visit: false,
    lookback_clamped: false,
    inflation: buildDomainRecap({ monitor: "inflation" }),
    labor: buildDomainRecap({ monitor: "labor" }),
    ...overrides,
  };
}
