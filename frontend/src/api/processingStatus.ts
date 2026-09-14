/**
 * Typed caller for Increment #19B's release-processing read model. GET
 * only -- this module has no function that could ever call a write/
 * mutation path (#19B exposes none to the browser at all: no "check
 * now" trigger exists anywhere in this project's public API). Pure
 * network plumbing: this function neither inspects, derives, nor
 * interprets anything about the response; that is entirely the
 * presentation layer's job (see components/overview/LatestDataDetected.tsx,
 * components/labor/LatestDataDetected.tsx).
 *
 * Called with no parameters by default -- Overview's "Latest Data
 * Detected" section needs one bounded, default page (the backend's own
 * default: `limit=20`, ordered `scheduled_date DESC`) to search across
 * for its own deterministic UI selection rule (see
 * lib/selectLatestDataDetected.ts); V1's curated mapping catalog is
 * small enough that 20 occurrences comfortably covers "recent" for
 * every release currently mapped.
 *
 * `releaseId` (Increment #20E.2) forwards to the backend's existing
 * `release_id` query filter (already present in
 * `app/api/release_processing_read.py`, confirmed by direct inspection
 * -- no backend change was needed) -- used by the dedicated `/labor`
 * page (docs/architecture/labor-ui-v1.md §5/§23) to scope the request
 * to Employment Situation's own occurrences only, rather than scanning
 * the generic default page Overview uses. Optional and backward
 * compatible: every existing call site (Overview) keeps working
 * unchanged.
 */
import { apiGet } from "./client";
import type { ReleaseProcessingStatusResponse } from "./processingStatus.types";

export function fetchReleaseProcessingStatus(releaseId?: number): Promise<ReleaseProcessingStatusResponse> {
  const query = releaseId === undefined ? "" : `?release_id=${releaseId}`;
  return apiGet<ReleaseProcessingStatusResponse>(`/api/v1/releases/processing-status${query}`);
}
