/**
 * Typed callers for the release calendar. GET only -- this module
 * deliberately has no function that could ever call the release
 * calendar's explicit sync write path; the browser is read-only for
 * releases (see docs/architecture/release-intelligence-v1.md #9). Pure network
 * plumbing: neither function inspects, derives, or interprets
 * anything about the response.
 */
import { apiGet } from "./client";
import type { ReleaseListResponse } from "./releases.types";
import { recentWindow, upcomingWindow } from "../lib/releases";

export interface GetReleasesParams {
  start_date?: string;
  end_date?: string;
  limit?: number;
  offset?: number;
  order?: "asc" | "desc";
}

export function getReleases(params: GetReleasesParams = {}): Promise<ReleaseListResponse> {
  const query = new URLSearchParams();
  if (params.start_date !== undefined) query.set("start_date", params.start_date);
  if (params.end_date !== undefined) query.set("end_date", params.end_date);
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.offset !== undefined) query.set("offset", String(params.offset));
  if (params.order !== undefined) query.set("order", params.order);

  const queryString = query.toString();
  return apiGet<ReleaseListResponse>(`/api/v1/releases${queryString ? `?${queryString}` : ""}`);
}

// A generously large limit relative to the actual V1 curated catalog's
// occurrence density in either window (well under 20 in practice, see
// docs/ENGINEERING_JOURNAL.md's #17B entry) -- comfortably one request,
// no "Load more" UI needed for V1.
const RELEASE_LIST_LIMIT = 100;

/** Upcoming Releases: today through the bounded upcoming window (see
 * lib/releases.ts), ascending -- the earliest scheduled date first. */
export function fetchUpcomingReleases(): Promise<ReleaseListResponse> {
  const { start_date, end_date } = upcomingWindow();
  return getReleases({ start_date, end_date, order: "asc", limit: RELEASE_LIST_LIMIT });
}

/** Recent Releases: the bounded recent window through today, descending
 * -- the most recently scheduled date first. */
export function fetchRecentReleases(): Promise<ReleaseListResponse> {
  const { start_date, end_date } = recentWindow();
  return getReleases({ start_date, end_date, order: "desc", limit: RELEASE_LIST_LIMIT });
}
