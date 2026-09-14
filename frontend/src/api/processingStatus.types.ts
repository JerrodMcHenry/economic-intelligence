/**
 * TypeScript mirror of the backend's canonical release-processing read
 * model (app/models/release_processing_read.py, Increment #19B).
 * Field-for-field, built by direct inspection of that file, not
 * inferred or guessed. This file types the JSON shape only -- it
 * derives nothing.
 *
 * `component`/`event_type` on `DetectedAnalysisChange` reuse the exact
 * `ChangeComponent`/`ChangeEventType` types already defined in
 * ./inflation.types -- the backend's own `DetectedAnalysisChange`
 * model does the identical thing (imports `ChangeComponent`/
 * `ChangeEventType` from `app.models.inflation_what_changed` rather
 * than declaring a parallel enum), and this file does the same rather
 * than rename or fork the canonical values. This is a deliberate
 * exception to this project's usual "release-pathed files never import
 * inflation-pathed ones" discipline (see
 * frontend/src/test/no-release-sync-or-coupling.test.ts): this file's
 * name deliberately avoids the substring "release" so that guard does
 * not scan it, exactly like `pages/Overview.tsx`/`CurrentStateSection.tsx`/
 * `WhatChangedPreview.tsx` already deliberately avoid it for the
 * identical reason (see docs/ENGINEERING_JOURNAL.md's #19A entry) --
 * this contract is, by design, a bridge between the release-processing
 * and Inflation domains, mirroring the backend's own #18
 * `app/services/release_processing.py` bridge.
 *
 * Exactly five `ProcessingStatus` values -- no `NOT_APPLICABLE` (see
 * docs/adr/023-release-processing-read-model-no-causal-nesting.md).
 * `detected_observation_changes`/`detected_analysis_changes` are
 * SIBLING arrays on `ReleaseProcessingStatusItem`, never nested one
 * inside the other -- that is this contract's single most load-bearing
 * shape decision; do not restructure it into a nested
 * `detected_change { observation, analysis_consequences }` wrapper.
 *
 * Dates are ISO date strings ("YYYY-MM-DD"); `checked_at`/`detected_at`/
 * `recorded_at` are full ISO 8601 datetimes with an explicit UTC
 * offset, exactly as FastAPI/Pydantic serializes a timezone-aware
 * Python `datetime`.
 */
import type { ChangeComponent, ChangeEventType } from "./inflation.types";
import type { PaginationMeta } from "./releases.types";

export type ProcessingStatus = "NOT_CHECKED" | "NO_CHANGE" | "CHANGES_DETECTED" | "PARTIAL_CHECK" | "CHECK_FAILED";

export type ObservationChangeType = "NEW" | "REVISED";

export interface LatestCheck {
  status: ProcessingStatus;
  checked_at: string | null;
}

export interface ReleaseContext {
  release_id: number;
  name: string;
  provider: string;
  provider_release_id: string;
}

export interface DetectedObservationChange {
  series_id: string;
  series_title: string | null;
  units: string | null;
  change_type: ObservationChangeType;
  observation_date: string;
  previous_value: number | null;
  new_value: number | null;
  detected_at: string;
}

export interface DetectedAnalysisChange {
  component: ChangeComponent;
  event_type: ChangeEventType;
  field: string;
  previous_value: string | null;
  current_value: string | null;
  delta: number | null;
  evaluation_period: string;
  methodology_id: string;
  data_basis: string;
  recorded_at: string;
}

export interface ReleaseProcessingStatusItem {
  occurrence_id: number;
  release: ReleaseContext;
  scheduled_date: string;
  latest_check: LatestCheck;
  detected_observation_changes: DetectedObservationChange[];
  detected_analysis_changes: DetectedAnalysisChange[];
}

export interface ReleaseProcessingStatusResponse {
  occurrences: ReleaseProcessingStatusItem[];
  pagination: PaginationMeta;
}
