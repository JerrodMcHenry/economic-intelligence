/**
 * TypeScript mirror of the backend's point-in-time intelligence history
 * response models (`app/models/monitor_history.py`, Increment #32),
 * copied field-for-field from the real backend models (verified by
 * inspection, not guessed).
 *
 * Do not add, rename, or infer a field that isn't in those models; if
 * the UI needs something these types don't have, that's a backend gap
 * to report.
 *
 * Two shapes here are deliberately NOT collapsed into one another,
 * because collapsing them is exactly the misleading thing this feature
 * must not do:
 *
 * - `RecordedIntelligenceEntry.state` is HISTORY -- what MacroChipz
 *   concluded and durably wrote at `calculated_at`.
 * - `CurrentComparison.current_state` is a RECONSTRUCTION computed from
 *   today's revised dataset at request time.
 *
 * The second is never rendered as something MacroChipz "knew".
 */

import type { PaginationMeta } from "./releases.types";

export type HistoryMonitor = "inflation" | "labor";

/** Increment #31's own replay vocabulary, reused verbatim. */
export type ReplayOutcome = "MATCH" | "MISMATCH" | "NOT_REPLAYABLE";

export type NotReplayableReason =
  | "UNKNOWN_RECORDED_RESULT"
  | "UNKNOWN_METHODOLOGY_VERSION"
  | "NO_VERSION_HISTORY_FOR_INPUTS"
  | "VERSION_HISTORY_STARTS_AFTER_CALCULATION";

export type InputComparison = "UNCHANGED" | "REVISED" | "ONLY_AVAILABLE_TODAY" | "ONLY_AVAILABLE_THEN";

/**
 * The methodology's own canonical unit for a value -- supplied by the
 * backend precisely so the frontend never infers it. `labor_v1.0`
 * reports PAYEMS as actual jobs while FRED publishes thousands.
 */
export type InputUnit = "INDEX" | "JOBS" | "PERCENT";

export type ComparisonStatus = "IDENTICAL_INPUTS" | "INPUTS_CHANGED" | "NOT_COMPARABLE";

export type NotComparableReason = "REPLAY_UNAVAILABLE" | "METHODOLOGY_VERSION_DIFFERS";

export interface ReplaySummary {
  outcome: ReplayOutcome;
  replayed_state: string | null;
  reason: NotReplayableReason | null;
  inputs_include_backfilled: boolean;
}

export interface PreviousRecordedResult {
  recorded_result_id: number;
  state: string;
  evaluation_period: string;
  calculated_at: string;
  /** True when this is a revised conclusion about the SAME month. */
  same_evaluation_period: boolean;
  state_changed: boolean;
}

export interface RecordedIntelligenceEntry {
  recorded_result_id: number;
  monitor: HistoryMonitor;
  state: string;
  evaluation_period: string;
  calculated_at: string;
  methodology_id: string;
  data_basis: string;
  replay: ReplaySummary;
  previous: PreviousRecordedResult | null;
}

export interface HistoricalInput {
  series_id: string;
  observation_date: string;
  value_then: number | null;
  value_today: number | null;
  value_unit: InputUnit;
  comparison: InputComparison;
  is_backfilled: boolean;
}

export interface CurrentComparison {
  status: ComparisonStatus;
  reason: NotComparableReason | null;
  current_state: string | null;
  state_differs: boolean | null;
  methodology_id_then: string;
  methodology_id_today: string;
  methodology_differs: boolean;
  changed_input_count: number;
}

export interface RelatedDataChange {
  series_id: string;
  observation_date: string;
  change_type: string;
  previous_value: number | null;
  new_value: number | null;
  detected_at: string;
}

export interface MonitorHistoryResponse {
  monitor: HistoryMonitor;
  entries: RecordedIntelligenceEntry[];
  pagination: PaginationMeta;
}

export interface MonitorHistoryDetail {
  recorded: RecordedIntelligenceEntry;
  historical_inputs: HistoricalInput[];
  current_comparison: CurrentComparison;
  related_changes: RelatedDataChange[];
  other_changes_in_same_run: number;
}
