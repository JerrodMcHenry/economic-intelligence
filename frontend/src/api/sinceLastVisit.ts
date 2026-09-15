/**
 * Typed caller for Increment #25G's `GET /api/v1/since-last-visit`.
 * Pure network plumbing -- neither inspects, derives, nor interprets
 * anything about the response (see api/client.ts's own docstring).
 *
 * `after`, when provided, must already be the server-issued `through`
 * value a prior successful response returned, verbatim -- this
 * function never computes, defaults, or validates a timestamp itself;
 * that discipline belongs to `lib/sinceLastVisitCheckpoint.ts` (read)
 * and the backend (validation, contract §54: a malformed value the
 * backend can't parse is treated as absent there, never a 400).
 */
import { apiGet } from "./client";
import type { SinceLastVisitResponse } from "./sinceLastVisit.types";

export function getSinceLastVisit(after?: string | null): Promise<SinceLastVisitResponse> {
  const query = after ? `?after=${encodeURIComponent(after)}` : "";
  return apiGet<SinceLastVisitResponse>(`/api/v1/since-last-visit${query}`);
}
