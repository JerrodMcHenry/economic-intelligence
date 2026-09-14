import type { DetectedAnalysisChange, DetectedObservationChange, ReleaseProcessingStatusItem } from "../../api/processingStatus.types";
import {
  formatAnalysisValue,
  formatCheckedAt,
  formatObservationValue,
  observationChangeTypeLabel,
  processingStatusLabel,
} from "../../lib/detectedChangeFormat";
import { CHANGE_COMPONENT_LABELS, changeEventTypeLabel, changeFieldLabel } from "../../lib/inflationLabels";
import { formatFullDate } from "../../lib/releases";
import { selectLatestDataDetectedItem } from "../../lib/selectLatestDataDetected";
import { DETECTED_CHANGES_DATA_BASIS, processingStatusExplanation } from "../../content/explanations/processingStatus";
import { Disclosure } from "../Disclosure";
import { ExplanationTrigger } from "../explanations/ExplanationTrigger";

const MAX_CHANGES = 3;

/**
 * The Economic Overview's "Latest Data Detected" section (Increment
 * #19C) -- the first frontend surface for Increment #18/#19B's
 * release-driven detected-change/analytical-consequence evidence.
 * Presentation only: this component computes nothing economic. It
 * reads `latest_check.status`, `detected_observation_changes`, and
 * `detected_analysis_changes` exactly as `GET
 * /api/v1/releases/processing-status` returned them (see
 * api/processingStatus.types.ts) and formats them.
 *
 * Receives the raw `items` array (Overview's already-loaded, already-
 * successful #19B response) and picks ONE item to show via
 * `selectLatestDataDetectedItem` (lib/selectLatestDataDetected.ts) --
 * see that module for why "first backend item" would be a poor
 * default. Loading/error states are handled by `pages/Overview.tsx`
 * itself, inline, exactly the same as the other four Overview
 * sections (CurrentStateSection/WhatChangedPreview/
 * UpcomingReleasesPreview/RecentReleasePreview) -- this component only
 * ever receives already-successful data, keeping every section's
 * loading/error handling visibly uniform in one file.
 *
 * CRITICAL, load-bearing rule: `latest_check.status` -- and ONLY that
 * field -- controls the primary status message
 * (`processingStatusLabel`). Historical `detected_observation_changes`/
 * `detected_analysis_changes` are NEVER inspected to override or
 * "upgrade" that message -- a `NO_CHANGE` latest check renders "No new
 * data detected in the latest check." even when earlier runs detected
 * real changes; those are shown separately, explicitly framed as
 * earlier evidence (see `hadNoNewEvidenceThisRun` below), never
 * re-labeled as the current result. This mirrors #19A's own
 * "backend-state-controls-explanation" principle (see
 * docs/ENGINEERING_JOURNAL.md's #19A entry) and is directly required
 * by #19B's own retry-history-preservation guarantee (see
 * docs/architecture/release-processing-read-model-v1.md #5).
 *
 * `detected_observation_changes` and `detected_analysis_changes` are
 * rendered as two separate, sibling sections ("Source data changes"/
 * "Tracked analysis changes") -- never nested, never implying one
 * caused the other (see
 * docs/adr/023-release-processing-read-model-no-causal-nesting.md).
 */
export function LatestDataDetected({ items }: { items: readonly ReleaseProcessingStatusItem[] }) {
  const selected = selectLatestDataDetectedItem(items);

  return (
    <section aria-labelledby="overview-latest-data-detected-heading">
      <h2 id="overview-latest-data-detected-heading" className="text-sm font-medium text-neutral-500">
        Latest Data Detected
      </h2>

      {selected === null ? (
        <p className="mt-3 text-sm text-neutral-500">No tracked release processing records are available yet.</p>
      ) : (
        <SelectedOccurrence item={selected} />
      )}
    </section>
  );
}

function SelectedOccurrence({ item }: { item: ReleaseProcessingStatusItem }) {
  const { latest_check: latestCheck } = item;
  const observationChanges = item.detected_observation_changes.slice(0, MAX_CHANGES);
  const analysisChanges = item.detected_analysis_changes.slice(0, MAX_CHANGES);
  const hasAnyEvidence = item.detected_observation_changes.length > 0 || item.detected_analysis_changes.length > 0;

  // A NO_CHANGE or CHECK_FAILED latest run, by construction, adds no
  // observation/analysis rows of its own (see
  // app/services/release_processing.py's `_determine_status`) -- so
  // any evidence present on this item is necessarily from an earlier
  // run, and it is truthful (not an inference beyond what the status
  // itself already guarantees) to frame it that way explicitly.
  const evidenceIsFromAnEarlierRun = (latestCheck.status === "NO_CHANGE" || latestCheck.status === "CHECK_FAILED") && hasAnyEvidence;

  return (
    <div className="mt-3">
      <p className="text-xs text-neutral-400">Most recent detected update</p>

      <p className="mt-1 text-sm font-semibold text-neutral-700">{item.release.name}</p>
      <p className="text-xs text-neutral-500">{formatFullDate(item.scheduled_date)}</p>

      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <span className="text-sm font-medium text-neutral-800">{processingStatusLabel(latestCheck.status)}</span>
        <ExplanationTrigger explanation={processingStatusExplanation(latestCheck.status)} />
      </div>

      {latestCheck.status === "PARTIAL_CHECK" && (
        <p className="mt-1 text-sm text-neutral-500">Some associated series could not be checked.</p>
      )}
      {latestCheck.status === "CHECK_FAILED" && (
        <p className="mt-1 text-sm text-neutral-500">Economic Intelligence could not complete the latest provider check.</p>
      )}
      {latestCheck.checked_at !== null && (
        <p className="mt-1 text-xs text-neutral-400">Checked {formatCheckedAt(latestCheck.checked_at)}</p>
      )}

      {evidenceIsFromAnEarlierRun && (
        <p className="mt-2 text-xs text-neutral-500">Earlier changes were detected for this release occurrence.</p>
      )}

      {observationChanges.length > 0 && (
        <div className="mt-3">
          <h3 className="text-xs font-medium uppercase tracking-wide text-neutral-400">Source data changes</h3>
          <ul className="mt-2 space-y-2.5">
            {observationChanges.map((change, index) => (
              <ObservationChangeRow key={`${change.series_id}-${change.observation_date}-${index}`} change={change} />
            ))}
          </ul>
          <div className="mt-2">
            <Disclosure summary={DETECTED_CHANGES_DATA_BASIS.title}>
              <p className="max-w-prose text-sm text-neutral-500">{DETECTED_CHANGES_DATA_BASIS.definition}</p>
            </Disclosure>
          </div>
        </div>
      )}

      {(analysisChanges.length > 0 || observationChanges.length > 0) && (
        <div className="mt-3">
          <h3 className="text-xs font-medium uppercase tracking-wide text-neutral-400">Tracked analysis changes</h3>
          {analysisChanges.length > 0 ? (
            <ul className="mt-2 space-y-2.5">
              {analysisChanges.map((change, index) => (
                <AnalysisChangeRow key={`${change.component}-${change.event_type}-${change.field}-${index}`} change={change} />
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-neutral-500">No tracked Inflation evidence changed during this processing history.</p>
          )}
        </div>
      )}
    </div>
  );
}

function ObservationChangeRow({ change }: { change: DetectedObservationChange }) {
  const showPreviousValue = change.change_type === "REVISED" && change.previous_value !== null;

  return (
    <li className="text-sm">
      <span className="font-medium text-neutral-800">{change.series_title ?? change.series_id}</span>
      <div className="text-neutral-500">
        {observationChangeTypeLabel(change.change_type)} · {formatFullDate(change.observation_date)}
      </div>
      <div className="tabular-nums text-neutral-700">
        {showPreviousValue && (
          <>
            {formatObservationValue(change.previous_value, change.units)}
            <span aria-hidden="true" className="mx-1.5 text-neutral-300">
              →
            </span>
          </>
        )}
        {formatObservationValue(change.new_value, change.units)}
      </div>
    </li>
  );
}

function AnalysisChangeRow({ change }: { change: DetectedAnalysisChange }) {
  return (
    <li className="text-sm">
      <div className="text-neutral-500">
        {CHANGE_COMPONENT_LABELS[change.component]} · {changeEventTypeLabel(change.event_type)} · {changeFieldLabel(change.field)}
      </div>
      <div className="tabular-nums text-neutral-700">
        {formatAnalysisValue(change.field, change.previous_value)}
        <span aria-hidden="true" className="mx-1.5 text-neutral-300">
          →
        </span>
        {formatAnalysisValue(change.field, change.current_value)}
      </div>
      <div className="text-xs text-neutral-400">{formatFullDate(change.evaluation_period)}</div>
      <div className="mt-1">
        <Disclosure summary="Details">
          <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm text-neutral-600">
            <dt className="text-neutral-400">Methodology</dt>
            <dd>{change.methodology_id}</dd>
            <dt className="text-neutral-400">Data basis</dt>
            <dd>{change.data_basis}</dd>
          </dl>
        </Disclosure>
      </div>
    </li>
  );
}
