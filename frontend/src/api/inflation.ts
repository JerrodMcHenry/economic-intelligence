/**
 * Typed callers for the two canonical Inflation Monitor endpoints.
 * Pure network plumbing -- each function issues one GET request and
 * returns the parsed, typed JSON body. Neither function inspects,
 * derives, or interprets anything about the response; that is the
 * presentation layer's job (see components/inflation/).
 */
import { apiGet } from "./client";
import type { InflationMonitorResult, InflationWhatChangedResult } from "./inflation.types";
import type { StateDurationResult } from "./stateDuration.types";

export function getInflationMonitor(): Promise<InflationMonitorResult> {
  return apiGet<InflationMonitorResult>("/api/v1/monitors/inflation");
}

export function getInflationWhatChanged(): Promise<InflationWhatChangedResult> {
  return apiGet<InflationWhatChangedResult>("/api/v1/monitors/inflation/changes");
}

/**
 * State Duration V1 (Increment #24C/#24D, frozen contract
 * docs/product/state-duration-v1.md §31): a latest-revised
 * reconstruction of how long Core PCE's own canonical
 * `underlying_momentum.state` has held -- never recorded history.
 */
export function getInflationStateDuration(): Promise<StateDurationResult> {
  return apiGet<StateDurationResult>("/api/v1/monitors/inflation/state-duration");
}
