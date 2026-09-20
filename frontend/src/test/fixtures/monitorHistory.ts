import type {
  CurrentComparison,
  HistoricalInput,
  MonitorHistoryDetail,
  MonitorHistoryResponse,
  RecordedIntelligenceEntry,
  RelatedDataChange,
  ReplaySummary,
} from "../../api/monitorHistory.types";

/**
 * Fixtures for point-in-time intelligence history (Increment #32).
 *
 * Complete, valid objects with `...overrides` last, matching every
 * other fixture module here. They contain no economic logic: each is a
 * transcription of a shape the backend really returns, so a test that
 * passes against these is testing rendering, never a calculation the
 * frontend is forbidden from doing.
 *
 * Several builders describe states the local development database
 * cannot currently produce -- a genuine revision, a replay mismatch, a
 * methodology-version difference. Those are exactly the states the UI
 * must handle honestly, and a fixture is the correct way to reach them
 * (the alternative being to corrupt real data to photograph it).
 */

export function buildReplaySummary(overrides: Partial<ReplaySummary> = {}): ReplaySummary {
  return {
    outcome: "MATCH",
    replayed_state: "COOLING",
    reason: null,
    inputs_include_backfilled: false,
    ...overrides,
  };
}

export function buildRecordedEntry(overrides: Partial<RecordedIntelligenceEntry> = {}): RecordedIntelligenceEntry {
  return {
    recorded_result_id: 51,
    monitor: "inflation",
    state: "COOLING",
    evaluation_period: "2026-07-01",
    calculated_at: "2026-08-14T15:30:00+00:00",
    methodology_id: "inflation_v1.0",
    data_basis: "latest_revised_data",
    replay: buildReplaySummary(),
    previous: null,
    ...overrides,
  };
}

export function buildHistoryResponse(overrides: Partial<MonitorHistoryResponse> = {}): MonitorHistoryResponse {
  const entries = overrides.entries ?? [buildRecordedEntry()];
  return {
    monitor: "inflation",
    entries,
    pagination: { limit: 12, offset: 0, returned: entries.length, total: entries.length },
    ...overrides,
  };
}

export function buildEmptyHistoryResponse(monitor: "inflation" | "labor" = "inflation"): MonitorHistoryResponse {
  return { monitor, entries: [], pagination: { limit: 12, offset: 0, returned: 0, total: 0 } };
}

export function buildHistoricalInput(overrides: Partial<HistoricalInput> = {}): HistoricalInput {
  return {
    series_id: "PCEPILFE",
    observation_date: "2026-07-01",
    value_then: 130.658,
    value_today: 130.658,
    value_unit: "INDEX",
    comparison: "UNCHANGED",
    is_backfilled: false,
    ...overrides,
  };
}

export function buildCurrentComparison(overrides: Partial<CurrentComparison> = {}): CurrentComparison {
  return {
    status: "IDENTICAL_INPUTS",
    reason: null,
    current_state: "COOLING",
    state_differs: false,
    methodology_id_then: "inflation_v1.0",
    methodology_id_today: "inflation_v1.0",
    methodology_differs: false,
    changed_input_count: 0,
    ...overrides,
  };
}

export function buildRelatedChange(overrides: Partial<RelatedDataChange> = {}): RelatedDataChange {
  return {
    series_id: "PCEPILFE",
    observation_date: "2026-07-01",
    change_type: "NEW",
    previous_value: null,
    new_value: 130.658,
    detected_at: "2026-08-14T15:30:00+00:00",
    ...overrides,
  };
}

export function buildHistoryDetail(overrides: Partial<MonitorHistoryDetail> = {}): MonitorHistoryDetail {
  return {
    recorded: buildRecordedEntry(),
    historical_inputs: [buildHistoricalInput()],
    current_comparison: buildCurrentComparison(),
    related_changes: [buildRelatedChange()],
    other_changes_in_same_run: 0,
    ...overrides,
  };
}

/** A provider revision landed after the recorded calculation. */
export function buildRevisedDetail(): MonitorHistoryDetail {
  return buildHistoryDetail({
    historical_inputs: [
      buildHistoricalInput({ observation_date: "2025-07-01" }),
      buildHistoricalInput({
        observation_date: "2026-07-01",
        value_then: 130.658,
        value_today: 131.204,
        comparison: "REVISED",
      }),
    ],
    current_comparison: buildCurrentComparison({
      status: "INPUTS_CHANGED",
      current_state: "HEATING",
      state_differs: true,
      changed_input_count: 1,
    }),
    related_changes: [
      buildRelatedChange({ change_type: "REVISED", previous_value: 130.658, new_value: 131.204 }),
    ],
  });
}

/** A recorded conclusion that no longer reproduces -- an integrity issue. */
export function buildMismatchDetail(): MonitorHistoryDetail {
  return buildHistoryDetail({
    recorded: buildRecordedEntry({
      state: "COOLING",
      replay: buildReplaySummary({ outcome: "MISMATCH", replayed_state: "HEATING" }),
    }),
  });
}

/** Not enough stored history to verify. */
export function buildNotReplayableDetail(): MonitorHistoryDetail {
  return buildHistoryDetail({
    recorded: buildRecordedEntry({
      replay: buildReplaySummary({
        outcome: "NOT_REPLAYABLE",
        replayed_state: null,
        reason: "VERSION_HISTORY_STARTS_AFTER_CALCULATION",
      }),
    }),
    historical_inputs: [],
    current_comparison: buildCurrentComparison({
      status: "NOT_COMPARABLE",
      reason: "REPLAY_UNAVAILABLE",
      current_state: "COOLING",
      state_differs: false,
    }),
    related_changes: [],
  });
}

/** Recorded under a methodology version this binary no longer runs. */
export function buildMethodologyDifferenceDetail(): MonitorHistoryDetail {
  return buildHistoryDetail({
    recorded: buildRecordedEntry({ methodology_id: "inflation_v0.9" }),
    current_comparison: buildCurrentComparison({
      status: "NOT_COMPARABLE",
      reason: "METHODOLOGY_VERSION_DIFFERS",
      current_state: null,
      state_differs: null,
      methodology_id_then: "inflation_v0.9",
      methodology_differs: true,
    }),
  });
}
