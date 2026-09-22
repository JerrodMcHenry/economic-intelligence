import { apiGet } from "./client";
import type { HousingResult } from "./housing.types";

/**
 * The canonical Housing read model (Increment #45).
 *
 * Read-only. This endpoint never triggers ingestion, and the UI never
 * calls the separate operator-invoked sync route — which matters more
 * for Census than for any previous provider, because Census requires a
 * credential and a read-triggered fetch would spend an authenticated
 * quota on every page view.
 */
export function getHousing(): Promise<HousingResult> {
  return apiGet<HousingResult>("/api/v1/housing");
}
