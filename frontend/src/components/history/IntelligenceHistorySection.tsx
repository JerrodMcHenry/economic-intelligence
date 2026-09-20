import { useState } from "react";

import type { ApiResourceState } from "../../api/useApiResource";
import type { HistoryMonitor, MonitorHistoryResponse, RecordedIntelligenceEntry } from "../../api/monitorHistory.types";
import { formatPeriod } from "../../lib/format";
import * as copy from "../../lib/historyCopy";
import { TONE_CLASSES, type Tone } from "../../design/stateTone";
import { formatCheckedAt } from "../../lib/detectedChangeFormat";
import { ErrorMessage } from "../ErrorMessage";
import { LoadingSkeleton } from "../LoadingSkeleton";
import { HistoricalResultDetail } from "./HistoricalResultDetail";
import { ReplayStatusBadge } from "./ReplayStatusBadge";

/**
 * The Intelligence History section on Inflation and Labor
 * (Increment #32) -- the product surface over Increment #31's temporal
 * foundation.
 *
 * Progressive disclosure is the organizing principle. The default row
 * answers only: what was the conclusion, for which month, and does it
 * still reproduce. Everything heavier -- the exact observations, the
 * then-vs-today comparison, same-run data changes, what "reconstructed"
 * means -- waits behind the row's own disclosure and is not even
 * fetched until a reader opens it.
 *
 * No database vocabulary appears here. "System-time interval",
 * "recorded_to" and "version" are implementation terms; a reader needs
 * to know what the evidence proves, not how it is stored.
 *
 * Every economic judgement on screen was made by the backend. This
 * component formats and arranges.
 */
export function IntelligenceHistorySection({
  monitor,
  history,
  headingId,
  stateLabel,
  stateTone,
  analystAvailable = false,
}: {
  monitor: HistoryMonitor;
  history: ApiResourceState<MonitorHistoryResponse> & { reload: () => void };
  headingId: string;
  stateLabel: (state: string) => string;
  stateTone: (state: string) => Tone;
  /** Increment #33. Defaults to off, so history renders identically on a
      deployment with no Analyst configured. */
  analystAvailable?: boolean;
}) {
  return (
    <section aria-labelledby={headingId}>
      <h2 id={headingId} className="text-sm font-medium text-fg-muted">
        {copy.SECTION_HEADING}
      </h2>
      <p className="mt-2 max-w-2xl text-sm text-fg-secondary">{copy.SECTION_INTRO}</p>

      {history.status === "loading" && (
        <div className="mt-4">
          <LoadingSkeleton label={copy.LOADING_LABEL} heightClassName="h-40" />
        </div>
      )}
      {history.status === "error" && (
        <div className="mt-4">
          <ErrorMessage message={copy.ERROR_MESSAGE} onRetry={history.reload} />
        </div>
      )}
      {history.status === "success" &&
        (history.data.entries.length === 0 ? (
          <p className="mt-4 text-sm text-fg-muted">{copy.EMPTY_HISTORY_COPY}</p>
        ) : (
          <>
            <ul className="mt-4 divide-y divide-line-subtle border-t border-line-subtle">
              {history.data.entries.map((entry) => (
                <HistoryRow
                  key={entry.recorded_result_id}
                  monitor={monitor}
                  entry={entry}
                  stateLabel={stateLabel}
                  stateTone={stateTone}
                  analystAvailable={analystAvailable}
                />
              ))}
            </ul>
            <p className="mt-4 max-w-2xl text-xs text-fg-muted">{copy.REVISION_DISCLOSURE}</p>
          </>
        ))}
    </section>
  );
}

/**
 * One recorded conclusion. A native `<details>/<summary>`, so keyboard
 * and screen-reader behaviour is the browser's own -- the same
 * primitive `Disclosure` uses. Open state is tracked here (rather than
 * left entirely to the DOM) only so the detail request is deferred
 * until a reader actually asks for it.
 */
function HistoryRow({
  monitor,
  entry,
  stateLabel,
  stateTone,
  analystAvailable,
}: {
  monitor: HistoryMonitor;
  entry: RecordedIntelligenceEntry;
  stateLabel: (state: string) => string;
  stateTone: (state: string) => Tone;
  analystAvailable: boolean;
}) {
  const [open, setOpen] = useState(false);
  const label = stateLabel(entry.state);

  return (
    <li>
      <details className="group py-3" onToggle={(event) => setOpen(event.currentTarget.open)}>
        <summary className="flex cursor-pointer select-none list-none flex-wrap items-center gap-x-3 gap-y-2 [&::-webkit-details-marker]:hidden">
          <svg
            viewBox="0 0 16 16"
            aria-hidden="true"
            className="h-3 w-3 flex-none text-fg-muted transition-transform group-open:rotate-90 motion-reduce:transition-none"
          >
            <path
              d="M6 3l5 5-5 5"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>

          <span className="min-w-[7.5rem] text-sm font-medium text-fg">{formatPeriod(entry.evaluation_period)}</span>

          <span
            className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${TONE_CLASSES[stateTone(entry.state)]}`}
          >
            {label}
          </span>

          <ReplayStatusBadge outcome={entry.replay.outcome} />

          {entry.replay.inputs_include_backfilled && (
            <span className="rounded-full bg-surface-secondary px-2 py-0.5 text-xs text-fg-muted">
              {copy.BACKFILL_BADGE_LABEL}
            </span>
          )}

          <span className="ml-auto text-xs text-fg-muted">{copy.calculatedLine(formatCheckedAt(entry.calculated_at))}</span>
        </summary>

        <div className="mt-3 pl-[18px]">
          {entry.previous !== null && (
            <p className="mb-4 text-sm text-fg-muted">
              {copy.previousStateCopy(
                stateLabel(entry.previous.state),
                entry.previous.same_evaluation_period,
                entry.previous.state_changed,
              )}
            </p>
          )}
          <HistoricalResultDetail
            monitor={monitor}
            recordedResultId={entry.recorded_result_id}
            open={open}
            stateLabel={stateLabel}
            analystAvailable={analystAvailable}
          />
        </div>
      </details>
    </li>
  );
}
