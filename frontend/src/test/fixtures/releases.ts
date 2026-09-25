/**
 * Deterministic test fixtures shaped exactly like the real backend
 * response models (see ../../api/releases.types.ts). Fixture data
 * only -- nothing here calculates anything.
 */
import type { PaginationMeta, ReleaseListResponse, ReleaseOccurrenceItem } from "../../api/releases.types";

export function buildReleaseOccurrenceItem(overrides: Partial<ReleaseOccurrenceItem> = {}): ReleaseOccurrenceItem {
  return {
    release_id: 1,
    name: "Consumer Price Index",
    provider: "BLS",
    provider_release_id: "cpi",
    official_url: null,
    scheduled_date: "2026-09-17",
    schedule_status: "SCHEDULED",
    ...overrides,
  };
}

export function buildPaginationMeta(overrides: Partial<PaginationMeta> = {}): PaginationMeta {
  return { limit: 100, offset: 0, returned: 1, total: 1, ...overrides };
}

export function buildReleaseListResponse(overrides: Partial<ReleaseListResponse> = {}): ReleaseListResponse {
  const releases = overrides.releases ?? [buildReleaseOccurrenceItem()];
  return {
    releases,
    pagination: buildPaginationMeta({ returned: releases.length, total: releases.length }),
    ...overrides,
  };
}
