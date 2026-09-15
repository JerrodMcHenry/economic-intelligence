/**
 * Deterministic test fixtures shaped exactly like the real backend
 * response models (see ../../api/stateDuration.types.ts). Every
 * builder returns a complete, valid object with sensible defaults;
 * tests override only the fields a given scenario cares about. Values
 * here are fixture data, not economic logic -- nothing in this file
 * calculates anything.
 */
import type { StateDurationAvailable, StateDurationCurrentInsufficient } from "../../api/stateDuration.types";

export function buildStateDurationAvailable(overrides: Partial<StateDurationAvailable> = {}): StateDurationAvailable {
  return {
    status: "AVAILABLE",
    state: "COOLING",
    evaluation_period: "2026-07-01",
    duration_months: 3,
    earliest_confirmed_period: "2026-05-01",
    boundary_type: "EXACT",
    previous_state: "STABLE",
    previous_period: "2026-04-01",
    methodology_id: "inflation_v1.0",
    data_basis: "latest_revised_data",
    history_type: "latest_revised_reconstruction",
    ...overrides,
  };
}

export function buildStateDurationCurrentInsufficient(
  overrides: Partial<StateDurationCurrentInsufficient> = {},
): StateDurationCurrentInsufficient {
  return {
    status: "CURRENT_INSUFFICIENT",
    methodology_id: "inflation_v1.0",
    data_basis: "latest_revised_data",
    ...overrides,
  };
}
