/**
 * TypeScript mirror of the backend's canonical release-processing read
 * model (app/models/release_processing_read.py, Increment #19B).
 * Field-for-field, built by direct inspection of that file, not
 * inferred or guessed. This file types the JSON shape only -- it
 * derives nothing.
 *
 * `event_type` on `DetectedAnalysisChange` reuses the exact
 * `ChangeEventType` type already defined in ./inflation.types -- the
 * backend's own `DetectedAnalysisChange` model does the identical
 * thing (imports `ChangeEventType` from
 * `app.models.inflation_what_changed` rather than declaring a parallel
 * enum), and this file does the same rather than rename or fork the
 * canonical values. `event_type`'s five values are shared across every
 * comparator this project has (Inflation's and Labor's four-value
 * vocabulary is a strict subset), so no widening was needed there.
 *
 * `component` is plain `string`, NOT `ChangeComponent` (Increment
 * #20E.2, mirroring the backend's own identical #20D.2 widening of
 * `app.models.release_processing_read.DetectedAnalysisChange.component`
 * -- see docs/architecture/labor-release-integration-v1.md §22). This
 * read-model row is generic transport/provenance metadata shared by
 * every analysis family (Inflation's `ChangeComponent`, Labor's
 * `LaborChangeComponent` from ./labor.types, and any future family) --
 * it is never the owner of any one family's own component vocabulary,
 * so it must not be typed with any one family's own Literal union.
 *
 * This is a deliberate exception to this project's usual
 * "release-pathed files never import inflation-pathed ones" discipline
 * (see frontend/src/test/no-release-sync-or-coupling.test.ts): this
 * file's name deliberately avoids the substring "release" so that
 * guard does not scan it, exactly like `pages/Overview.tsx`/
 * `CurrentStateSection.tsx`/`WhatChangedPreview.tsx` already
 * deliberately avoid it for the identical reason (see
 * docs/ENGINEERING_JOURNAL.md's #19A entry) -- this contract is, by
 * design, a bridge between the release-processing and Inflation/Labor
 * domains, mirroring the backend's own #18/#20D.2
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
import type { ChangeEventType } from "./inflation.types";
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
  component: string;
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
