/**
 * Client for the #39 Structured Intelligence API (Increment #40).
 *
 * Read-only. The frontend consumes these objects and formats them; it
 * never recomputes what they assert.
 */
import { apiGet } from "./client";
import type { IntelligenceListResponse, IntelligenceObject, IntelligenceWorld } from "./intelligence.types";

export function getIntelligenceObject(intelligenceId: string): Promise<IntelligenceObject> {
  return apiGet<IntelligenceObject>(`/api/v1/intelligence/${encodeURIComponent(intelligenceId)}`);
}

export function listIntelligence(
  params: { limit?: number; type?: string; world?: IntelligenceWorld } = {},
): Promise<IntelligenceListResponse> {
  const query = new URLSearchParams();
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.type !== undefined) query.set("type", params.type);
  if (params.world !== undefined) query.set("world", params.world);
  const suffix = query.toString();
  return apiGet<IntelligenceListResponse>(`/api/v1/intelligence${suffix ? `?${suffix}` : ""}`);
}

/**
 * The bounded slice the homepage selects from (#42).
 *
 * `HOMEPAGE_SCAN_LIMIT` is the service's own maximum page size, not an
 * arbitrary number: the homepage reads ONE page and selects from it,
 * rather than walking 1,899 objects to show five. The consequence is
 * honest and worth stating — if a newly eligible object ever falls
 * outside the newest page, the homepage will not see it until the
 * backend orders or filters on eligibility itself.
 */
export const HOMEPAGE_SCAN_LIMIT = 100;

export function listHomepageIntelligence(): Promise<IntelligenceListResponse> {
  return listIntelligence({ limit: HOMEPAGE_SCAN_LIMIT });
}

/**
 * Every recorded movement for the Rates world (Increment #52B).
 *
 * `world` is the service's own filter parameter, so the Rates page asks
 * for rates objects rather than pulling a page of everything and
 * discarding what it did not want. The ceiling is the same
 * service-maximum the homepage uses; MacroChipz holds six of these
 * today, one per ingested Treasury series.
 *
 * Fetched on its OWN `useApiResource`, deliberately: the Treasury curve
 * and these records are independent facts from independent requests,
 * and neither outage may blank the other.
 */
export function listRatesMovements(): Promise<IntelligenceListResponse> {
  return listIntelligence({ world: "rates", type: "RATES_MOVEMENT", limit: HOMEPAGE_SCAN_LIMIT });
}
