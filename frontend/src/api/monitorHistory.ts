import { apiGet } from "./client";
import type { HistoryMonitor, MonitorHistoryDetail, MonitorHistoryResponse } from "./monitorHistory.types";

/**
 * Point-in-time intelligence history (Increment #32). Read-only; there
 * is no write counterpart, by design -- recorded history is append-only
 * and written solely by release processing (ADR-025).
 */

/**
 * How many recorded results the history section requests. Well inside
 * the backend's own `le=100` bound, and small enough that the section
 * stays a summary rather than an archive dump.
 */
export const HISTORY_PAGE_SIZE = 12;

function historyPath(monitor: HistoryMonitor): string {
  return `/api/v1/monitors/${monitor}/history`;
}

export function getMonitorHistory(monitor: HistoryMonitor): Promise<MonitorHistoryResponse> {
  return apiGet<MonitorHistoryResponse>(`${historyPath(monitor)}?limit=${HISTORY_PAGE_SIZE}&offset=0`);
}

/**
 * Stable module-level fetchers, one per monitor -- `useApiResource`
 * expects a stable reference and deliberately does not track `fetcher`
 * as an effect dependency.
 */
export const getInflationHistory = (): Promise<MonitorHistoryResponse> => getMonitorHistory("inflation");
export const getLaborHistory = (): Promise<MonitorHistoryResponse> => getMonitorHistory("labor");

export function getMonitorHistoryDetail(
  monitor: HistoryMonitor,
  recordedResultId: number,
): Promise<MonitorHistoryDetail> {
  return apiGet<MonitorHistoryDetail>(`${historyPath(monitor)}/${recordedResultId}`);
}
