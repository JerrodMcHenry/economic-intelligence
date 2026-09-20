import { apiGet } from "./client";
import type { RatesMonitorResult } from "./rates.types";

/**
 * The canonical `rates_v1.0` Rates Monitor result (Increment #29).
 * Read-only: this endpoint never triggers ingestion, and the UI never
 * calls the separate operator-invoked sync route.
 */
export function getRatesMonitor(): Promise<RatesMonitorResult> {
  return apiGet<RatesMonitorResult>("/api/v1/monitors/rates");
}
