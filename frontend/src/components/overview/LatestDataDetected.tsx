import type { DetectedAnalysisChange, DetectedObservationChange, ReleaseProcessingStatusItem } from "../../api/processingStatus.types";
import {
  analysisComponentLabel,
  analysisFieldLabel,
  formatAnalysisValue,
  formatCheckedAt,
  formatObservationValue,
  observationChangeTypeLabel,
  processingStatusLabel,
} from "../../lib/detectedChangeFormat";
import { changeEventTypeLabel } from "../../lib/inflationLabels";
import { formatFullDate } from "../../lib/releases";
import { selectLatestDataDetectedItem } from "../../lib/selectLatestDataDetected";
import { DETECTED_CHANGES_DATA_BASIS, processingStatusExplanation } from "../../content/explanations/processingStatus";
import { Disclosure } from "../Disclosure";
import { ExplanationTrigger } from "../explanations/ExplanationTrigger";

const MAX_CHANGES = 3;

/**
 * The per-occurrence content renderer behind the Economic Overview's
 * "Recent Data Updates" section (Increment #19C, restructured #22B) --
 * the first frontend surface for Increment #18/#19B's release-driven
 * detected-change/analytical-consequence evidence. Presentation only:
 * this component computes nothing economic. It reads
 * `latest_check.status`, `detected_observation_changes`, and
 * `detected_analysis_changes` exactly as `GET
 * /api/v1/releases/processing-status` returned them (see
 * api/processingStatus.types.ts) and formats them.
 *
 * Increment #22B: this component no longer owns its own `<section>`/
 * `<h2>` -- it is now a content-only "slot" renderer, called TWICE by
 * `components/overview/RecentDataUpdates.tsx` (once per canonical
 * monitor domain, each already pre-filtered by
 * `lib/releaseMonitorRelation.ts`'s `CANONICAL_MONITOR_RELEASE_IDS`,
 * never by the broader, unrelated `releaseCategory()` display tag --
 * docs/product/overview-attention-model-v1.md §3A/§14). This file's own
 * name, export, and `items`-array prop shape are otherwise UNCHANGED
 * from #19C -- `RecentDataUpdates.tsx` owns the shared heading and
 * per-domain labeling; this component still receives the raw `items`
 * array for its own domain slot and picks ONE item to show via
 * `selectLatestDataDetectedItem` (lib/selectLatestDataDetected.ts,
 * itself unmodified) -- see that module for why "first backend item"
 * would be a poor default. Loading/error states are handled by
 * `pages/Overview.tsx` itself, inline, exactly the same as every other
 * Overview section (CurrentStateSection/WhatChangedPreview/
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

  return selected === null ? (
    <p className="mt-3 text-sm text-fg-muted">No tracked release processing records are available yet.</p>
  ) : (
    <SelectedOccurrence item={selected} />
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
      <p className="text-xs text-fg-muted">Most recent detected update</p>

      <p className="mt-1 text-sm font-semibold text-fg-secondary">{item.release.name}</p>
      <p className="text-xs text-fg-muted">{formatFullDate(item.scheduled_date)}</p>

      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <span className="text-sm font-medium text-fg">{processingStatusLabel(latestCheck.status)}</span>
        <ExplanationTrigger explanation={processingStatusExplanation(latestCheck.status)} />
      </div>

      {latestCheck.status === "PARTIAL_CHECK" && (
        <p className="mt-1 text-sm text-fg-muted">Some associated series could not be checked.</p>
      )}
      {latestCheck.status === "CHECK_FAILED" && (
        <p className="mt-1 text-sm text-fg-muted">Economic Intelligence could not complete the latest provider check.</p>
      )}
      {latestCheck.checked_at !== null && (
        <p className="mt-1 text-xs text-fg-muted">Checked {formatCheckedAt(latestCheck.checked_at)}</p>
      )}

      {evidenceIsFromAnEarlierRun && (
        <p className="mt-2 text-xs text-fg-muted">Earlier changes were detected for this release occurrence.</p>
      )}

      {observationChanges.length > 0 && (
        <div className="mt-3">
          <h3 className="text-xs font-medium uppercase tracking-wide text-fg-muted">Source data changes</h3>
          <ul className="mt-2 space-y-2.5">
            {observationChanges.map((change, index) => (
              <ObservationChangeRow key={`${change.series_id}-${change.observation_date}-${index}`} change={change} />
            ))}
          </ul>
          <div className="mt-2">
            <Disclosure summary={DETECTED_CHANGES_DATA_BASIS.title}>
              <p className="max-w-prose text-sm text-fg-muted">{DETECTED_CHANGES_DATA_BASIS.definition}</p>
            </Disclosure>
          </div>
        </div>
      )}

      {(analysisChanges.length > 0 || observationChanges.length > 0) && (
        <div className="mt-3">
          <h3 className="text-xs font-medium uppercase tracking-wide text-fg-muted">Tracked analysis changes</h3>
          {analysisChanges.length > 0 ? (
            <ul className="mt-2 space-y-2.5">
              {analysisChanges.map((change, index) => (
                <AnalysisChangeRow key={`${change.component}-${change.event_type}-${change.field}-${index}`} change={change} />
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-fg-muted">No tracked evidence changed during this processing history.</p>
          )}
        </div>
      )}
    </div>
  );
}

/** Exported so components/labor/LatestDataDetected.tsx can reuse this
 * row unchanged -- see this module's own docstring and
 * docs/architecture/labor-ui-v1.md §23. */
export function ObservationChangeRow({ change }: { change: DetectedObservationChange }) {
  const showPreviousValue = change.change_type === "REVISED" && change.previous_value !== null;

  return (
    <li className="text-sm">
      <span className="font-medium text-fg">{change.series_title ?? change.series_id}</span>
      <div className="text-fg-muted">
        {observationChangeTypeLabel(change.change_type)} · {formatFullDate(change.observation_date)}
      </div>
      <div className="tabular-nums text-fg-secondary">
        {showPreviousValue && (
          <>
            {formatObservationValue(change.previous_value, change.units)}
            <span aria-hidden="true" className="mx-1.5 text-fg-faint">
              →
            </span>
          </>
        )}
        {formatObservationValue(change.new_value, change.units)}
      </div>
    </li>
  );
}

/** Exported so components/labor/LatestDataDetected.tsx can reuse this
 * row unchanged -- see this module's own docstring and
 * docs/architecture/labor-ui-v1.md §23. */
export function AnalysisChangeRow({ change }: { change: DetectedAnalysisChange }) {
  return (
    <li className="text-sm">
      <div className="text-fg-muted">
        {analysisComponentLabel(change.component)} · {changeEventTypeLabel(change.event_type)} · {analysisFieldLabel(change.field)}
      </div>
      <div className="tabular-nums text-fg-secondary">
        {formatAnalysisValue(change.field, change.previous_value)}
        <span aria-hidden="true" className="mx-1.5 text-fg-faint">
          →
        </span>
        {formatAnalysisValue(change.field, change.current_value)}
      </div>
      <div className="text-xs text-fg-muted">{formatFullDate(change.evaluation_period)}</div>
      <div className="mt-1">
        <Disclosure summary="Details">
          <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm text-fg-secondary">
            <dt className="text-fg-muted">Methodology</dt>
            <dd>{change.methodology_id}</dd>
            <dt className="text-fg-muted">Data basis</dt>
            <dd>{change.data_basis}</dd>
          </dl>
        </Disclosure>
      </div>
    </li>
  );
}
