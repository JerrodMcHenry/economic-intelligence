/**
 * Typed caller for Increment #19B's release-processing read model. GET
 * only -- this module has no function that could ever call a write/
 * mutation path (#19B exposes none to the browser at all: no "check
 * now" trigger exists anywhere in this project's public API). Pure
 * network plumbing: this function neither inspects, derives, nor
 * interprets anything about the response; that is entirely the
 * presentation layer's job (see components/overview/LatestDataDetected.tsx).
 *
 * Called with no parameters -- Overview's "Latest Data Detected"
 * section needs one bounded, default page (the backend's own default:
 * `limit=20`, ordered `scheduled_date DESC`) to search across for its
 * own deterministic UI selection rule (see
 * lib/selectLatestDataDetected.ts); V1's curated mapping catalog is
 * small enough that 20 occurrences comfortably covers "recent" for
 * every release currently mapped. If a future increment needs
 * filtering (e.g. a release-detail surface), extend this function's
 * parameters then, deliberately -- do not add unused filter plumbing
 * speculatively now.
 */
import { apiGet } from "./client";
import type { ReleaseProcessingStatusResponse } from "./processingStatus.types";

export function fetchReleaseProcessingStatus(): Promise<ReleaseProcessingStatusResponse> {
  return apiGet<ReleaseProcessingStatusResponse>("/api/v1/releases/processing-status");
}
