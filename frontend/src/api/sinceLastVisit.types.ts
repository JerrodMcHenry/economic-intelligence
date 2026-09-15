/**
 * TypeScript mirror of the backend's Since Last Visit V1 read model
 * (app/models/since_last_visit.py, Increment #25G), field-for-field,
 * built by direct inspection of that file, not inferred or guessed.
 * This file types the JSON shape only -- it derives nothing. Frozen
 * contract: docs/product/since-last-visit-v1.md (#25F).
 *
 * Three distinct, discriminated item shapes -- never one generic
 * "event" shape a component must inspect nullable fields to classify
 * (contract §69 of the source prompt): `StructuralChange` (Tier A),
 * `Recalculation` (Tier B, `kind` distinguishes FIRST_CALCULATION from
 * UNCHANGED_CONFIRMATION), `SourceUpdate` (Tier C). Every backend
 * timestamp (`through`/`calculated_at`/`last_checked_at`) is a full
 * ISO-8601 UTC datetime with an explicit `Z`/offset, exactly as
 * FastAPI/Pydantic serializes a timezone-aware Python `datetime` --
 * `evaluation_period` is a bare ISO date ("YYYY-MM-DD"), kept
 * textually and semantically distinct from calculation-time fields
 * everywhere this module is consumed (contract §74).
 */

export type Monitor = "inflation" | "labor";
export type Coverage = "CHECKED" | "GAP" | "UNKNOWN";
export type RecalculationKind = "FIRST_CALCULATION" | "UNCHANGED_CONFIRMATION";
export type SourceUpdateChangeType = "NEW" | "REVISED";

export interface StructuralChange {
  monitor: Monitor;
  event_type: string;
  field: string;
  previous_value: string | null;
  current_value: string | null;
  evaluation_period: string;
  methodology_id: string;
  calculated_at: string;
  release_check_run_id: number;
}

export interface Recalculation {
  monitor: Monitor;
  kind: RecalculationKind;
  state: string;
  evaluation_period: string;
  count: number;
  calculated_at: string;
  methodology_id: string;
}

export interface SourceUpdate {
  monitor: Monitor;
  series_id: string;
  series_title: string | null;
  change_type: SourceUpdateChangeType;
  release_check_run_id: number;
}

export interface DomainRecap {
  monitor: Monitor;
  coverage: Coverage;
  last_checked_at: string | null;
  structural_changes: StructuralChange[];
  recalculations: Recalculation[];
  source_updates: SourceUpdate[];
}

export interface SinceLastVisitResponse {
  after: string | null;
  through: string;
  first_visit: boolean;
  lookback_clamped: boolean;
  inflation: DomainRecap;
  labor: DomainRecap;
}
