/**
 * Typed callers for the two canonical Labor Monitor endpoints. Pure
 * network plumbing -- each function issues one GET request and returns
 * the parsed, typed JSON body. Neither function inspects, derives, or
 * interprets anything about the response; that is the presentation
 * layer's job (see components/labor/).
 */
import { apiGet } from "./client";
import type { LaborMonitorResult, LaborWhatChangedResult } from "./labor.types";
import { fetchReleaseProcessingStatus } from "./processingStatus";
import type { ReleaseProcessingStatusResponse } from "./processingStatus.types";
import { fetchRecentReleases, fetchUpcomingReleases } from "./releases";

export function getLaborMonitor(): Promise<LaborMonitorResult> {
  return apiGet<LaborMonitorResult>("/api/v1/monitors/labor");
}

export function getLaborWhatChanged(): Promise<LaborWhatChangedResult> {
  return apiGet<LaborWhatChangedResult>("/api/v1/monitors/labor/changes");
}

// Employment Situation's stable FRED identity -- see
// components/labor/RelevantRelease.tsx's own identical constant and
// docs/architecture/labor-ui-v1.md §4/§24.
const EMPLOYMENT_SITUATION_PROVIDER_RELEASE_ID = "50";

/**
 * Employment Situation's own processing-status evidence, scoped via
 * the backend's existing `release_id` query filter (confirmed in
 * `app/api/release_processing_read.py` -- no backend change needed,
 * docs/architecture/labor-ui-v1.md §5/§23). The filter takes the
 * *internal* `release_id`, which isn't statically known to the
 * frontend, so this composes: resolve it from the Upcoming/Recent
 * release windows already used elsewhere on this page (any occurrence
 * of Employment Situation reveals its own `release_id`), then issue
 * the scoped request. Still pure plumbing plus ID resolution -- no
 * economic interpretation happens here. If Employment Situation has no
 * occurrence in either window (a genuine edge case), this resolves to
 * an empty result rather than falling back to the unscoped default
 * page, which could silently show a DIFFERENT release's evidence.
 */
export async function getEmploymentSituationProcessingStatus(): Promise<ReleaseProcessingStatusResponse> {
  const [upcoming, recent] = await Promise.all([fetchUpcomingReleases(), fetchRecentReleases()]);
  const match = [...upcoming.releases, ...recent.releases].find(
    (release) => release.provider_release_id === EMPLOYMENT_SITUATION_PROVIDER_RELEASE_ID,
  );
  if (match === undefined) {
    return { occurrences: [], pagination: { limit: 0, offset: 0, returned: 0, total: 0 } };
  }
  return fetchReleaseProcessingStatus(match.release_id);
}
