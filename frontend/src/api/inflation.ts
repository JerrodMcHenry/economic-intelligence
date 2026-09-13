/**
 * Typed callers for the two canonical Inflation Monitor endpoints.
 * Pure network plumbing -- each function issues one GET request and
 * returns the parsed, typed JSON body. Neither function inspects,
 * derives, or interprets anything about the response; that is the
 * presentation layer's job (see components/inflation/).
 */
import { apiGet } from "./client";
import type { InflationMonitorResult, InflationWhatChangedResult } from "./inflation.types";

export function getInflationMonitor(): Promise<InflationMonitorResult> {
  return apiGet<InflationMonitorResult>("/api/v1/monitors/inflation");
}

export function getInflationWhatChanged(): Promise<InflationWhatChangedResult> {
  return apiGet<InflationWhatChangedResult>("/api/v1/monitors/inflation/changes");
}
