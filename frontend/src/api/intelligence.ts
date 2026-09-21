/**
 * Client for the #39 Structured Intelligence API (Increment #40).
 *
 * Read-only. The frontend consumes these objects and formats them; it
 * never recomputes what they assert.
 */
import { apiGet } from "./client";
import type { IntelligenceListResponse, IntelligenceObject } from "./intelligence.types";

export function getIntelligenceObject(intelligenceId: string): Promise<IntelligenceObject> {
  return apiGet<IntelligenceObject>(`/api/v1/intelligence/${encodeURIComponent(intelligenceId)}`);
}

export function listIntelligence(params: { limit?: number; type?: string } = {}): Promise<IntelligenceListResponse> {
  const query = new URLSearchParams();
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.type !== undefined) query.set("type", params.type);
  const suffix = query.toString();
  return apiGet<IntelligenceListResponse>(`/api/v1/intelligence${suffix ? `?${suffix}` : ""}`);
}
