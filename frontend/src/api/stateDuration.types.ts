/**
 * TypeScript mirror of the backend's State Duration V1 discriminated-
 * union response contract (app/models/state_duration.py), frozen and
 * normative in docs/product/state-duration-v1.md §32.
 *
 * This file types the JSON shape only -- it derives nothing. Every
 * field name below is copied field-for-field from the real backend
 * model (verified by inspection, not guessed). A genuine two-shape
 * union, mirrored exactly: `CURRENT_INSUFFICIENT` carries no
 * duration/period/boundary fields at all, never nulled placeholders --
 * do not flatten this into one interface with everything optional.
 *
 * One shared type serves BOTH `GET /api/v1/monitors/inflation/state-duration`
 * and `GET /api/v1/monitors/labor/state-duration` -- the backend
 * itself returns the identical Pydantic union from both routes (its
 * own `state`/`previous_state` fields are typed `InflationState |
 * LaborState`), so this file mirrors that one shared shape rather than
 * declaring two near-duplicate per-monitor types.
 *
 * Dates are ISO date strings ("YYYY-MM-DD"), exactly as FastAPI/Pydantic
 * serializes a Python `date`.
 */
import type { InflationState } from "./inflation.types";
import type { LaborState } from "./labor.types";

export type StateDurationBoundaryType = "EXACT" | "DATA_BOUNDED" | "LOOKBACK_BOUNDED";

export interface StateDurationAvailable {
  status: "AVAILABLE";
  state: InflationState | LaborState;
  evaluation_period: string;
  duration_months: number;
  earliest_confirmed_period: string;
  boundary_type: StateDurationBoundaryType;
  previous_state: InflationState | LaborState | null;
  previous_period: string | null;
  methodology_id: string;
  data_basis: string;
  history_type: "latest_revised_reconstruction";
}

export interface StateDurationCurrentInsufficient {
  status: "CURRENT_INSUFFICIENT";
  methodology_id: string;
  data_basis: string;
}

export type StateDurationResult = StateDurationAvailable | StateDurationCurrentInsufficient;
