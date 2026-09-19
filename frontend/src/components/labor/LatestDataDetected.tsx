import type { ReleaseProcessingStatusItem } from "../../api/processingStatus.types";
import { DETECTED_CHANGES_DATA_BASIS, processingStatusExplanation } from "../../content/explanations/processingStatus";
import { formatCheckedAt, processingStatusLabel } from "../../lib/detectedChangeFormat";
import { formatFullDate } from "../../lib/releases";
import { Disclosure } from "../Disclosure";
import { ExplanationTrigger } from "../explanations/ExplanationTrigger";
import { AnalysisChangeRow, ObservationChangeRow } from "../overview/LatestDataDetected";

const MAX_CHANGES = 5;

/**
 * The /labor page's own "Latest Data Detected" section -- scoped to
 * Employment Situation's own occurrences only (the caller fetches with
 * `fetchReleaseProcessingStatus(releaseId)`, docs/architecture/labor-ui-v1.md
 * §5/§23), never the generic cross-release list Overview shows.
 * Because every item this component receives is already scoped to one
 * release, `items[0]` IS the most recent Employment Situation
 * occurrence (the backend orders `scheduled_date DESC, id ASC` --
 * verified in app/repositories/release_processing_read_repository.py)
 * -- `lib/selectLatestDataDetected.ts`'s own "pick one interesting item
 * from a MIXED list" logic does not apply here and is deliberately not
 * reused (it exists specifically for Overview's unscoped list).
 *
 * This describes DETECTION, never causation -- see this section's own
 * copy and components/overview/LatestDataDetected.tsx's identical
 * discipline, which this component otherwise mirrors exactly (same
 * row components, reused unchanged; see docs/architecture/labor-ui-v1.md §22).
 */
export function LatestDataDetected({ items }: { items: readonly ReleaseProcessingStatusItem[] }) {
  const item = items[0] ?? null;

  return (
    <section aria-labelledby="labor-latest-data-detected-heading">
      <h2 id="labor-latest-data-detected-heading" className="text-sm font-medium text-fg-muted">
        Latest data detected
      </h2>

      {item === null ? (
        <p className="mt-3 text-sm text-fg-muted">No tracked release processing records are available yet.</p>
      ) : (
        <SelectedOccurrence item={item} />
      )}
    </section>
  );
}

function SelectedOccurrence({ item }: { item: ReleaseProcessingStatusItem }) {
  const { latest_check: latestCheck } = item;
  const observationChanges = item.detected_observation_changes.slice(0, MAX_CHANGES);
  const analysisChanges = item.detected_analysis_changes.slice(0, MAX_CHANGES);
  const hasAnyEvidence = item.detected_observation_changes.length > 0 || item.detected_analysis_changes.length > 0;

  // Same rule as Overview's own component: `latest_check.status` --
  // and ONLY that field -- controls the primary status message. See
  // components/overview/LatestDataDetected.tsx's own docstring.
  const evidenceIsFromAnEarlierRun = (latestCheck.status === "NO_CHANGE" || latestCheck.status === "CHECK_FAILED") && hasAnyEvidence;

  return (
    <div className="mt-3">
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
