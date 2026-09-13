/**
 * TypeScript mirror of the backend's canonical release-calendar
 * Pydantic response models (app/models/releases.py). Field-for-field,
 * built by direct inspection of that file, not inferred or guessed.
 *
 * This file types the JSON shape only -- it derives nothing.
 * `schedule_status` arrives already-classified from the backend
 * (app.domain.releases.classify_schedule_status); nothing in the
 * frontend ever recomputes it. Dates are ISO date strings
 * ("YYYY-MM-DD"), exactly as FastAPI/Pydantic serializes a Python
 * `date`.
 *
 * Only the read contract (`GET /api/v1/releases`) is modeled here --
 * #17B never calls the release calendar's explicit sync write path, so
 * its response shape (`ReleaseSyncResponse` et al.) is deliberately
 * not mirrored.
 */

export type ScheduleStatus = "SCHEDULED" | "PAST_DUE";

export interface ReleaseOccurrenceItem {
  release_id: number;
  name: string;
  provider: string;
  provider_release_id: string;
  official_url: string | null;
  scheduled_date: string;
  schedule_status: ScheduleStatus;
}

export interface PaginationMeta {
  limit: number;
  offset: number;
  returned: number;
  total: number;
}

export interface ReleaseListResponse {
  releases: ReleaseOccurrenceItem[];
  pagination: PaginationMeta;
}
