import type { HistoryMonitor, MonitorHistoryDetail } from "../../api/monitorHistory.types";
import { useMonitorHistoryDetail } from "../../api/useMonitorHistoryDetail";
import { formatPeriod } from "../../lib/format";
import * as copy from "../../lib/historyCopy";
import {
  COMPARISON_STATUS_LABEL,
  INPUT_COMPARISON_LABEL,
  NOT_COMPARABLE_REASON_COPY,
  NOT_REPLAYABLE_REASON_COPY,
  formatInputValue,
  observationChangeLabel,
} from "../../lib/historyLabels";
import { formatObservationDate } from "../../lib/ratesFormat";
import { ErrorMessage } from "../ErrorMessage";
import { LoadingSkeleton } from "../LoadingSkeleton";

/**
 * One recorded result opened up (Increment #32): what MacroChipz knew
 * then, what today's revised data says about the same period, and which
 * source-data changes were processed in the same run.
 *
 * Renders backend conclusions verbatim. It does not compare values,
 * decide whether a comparison is valid, classify a revision, or infer a
 * cause -- all of that arrives already decided in
 * `MonitorHistoryDetail`.
 *
 * Fetches only once its row is opened; see `useMonitorHistoryDetail`.
 */
export function HistoricalResultDetail({
  monitor,
  recordedResultId,
  open,
  stateLabel,
}: {
  monitor: HistoryMonitor;
  recordedResultId: number;
  open: boolean;
  stateLabel: (state: string) => string;
}) {
  const detail = useMonitorHistoryDetail(monitor, recordedResultId, open);

  if (detail.status === "idle") return null;
  if (detail.status === "loading") {
    return <LoadingSkeleton label={copy.DETAIL_LOADING_LABEL} heightClassName="h-32" />;
  }
  if (detail.status === "error") {
    return <ErrorMessage message={copy.DETAIL_ERROR_MESSAGE} />;
  }
  return <DetailBody detail={detail.data} stateLabel={stateLabel} />;
}

function SubHeading({ children }: { children: React.ReactNode }) {
  return <h4 className="text-xs font-medium uppercase tracking-wide text-fg-muted">{children}</h4>;
}

function DetailBody({
  detail,
  stateLabel,
}: {
  detail: MonitorHistoryDetail;
  stateLabel: (state: string) => string;
}) {
  const { recorded, historical_inputs, current_comparison, related_changes, other_changes_in_same_run } = detail;
  const otherChanges = copy.otherChangesCopy(other_changes_in_same_run);

  return (
    <div className="space-y-5 text-sm">
      {/* ---------- What MacroChipz knew then ---------- */}
      <div>
        <SubHeading>{copy.THEN_HEADING}</SubHeading>
        <dl className="mt-2 grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-fg-secondary">
          <dt className="text-fg-muted">Conclusion</dt>
          <dd>{stateLabel(recorded.state)}</dd>
          <dt className="text-fg-muted">Period</dt>
          <dd>{formatPeriod(recorded.evaluation_period)}</dd>
          <dt className="text-fg-muted">Methodology</dt>
          <dd className="tabular-nums">{recorded.methodology_id}</dd>
        </dl>
        {recorded.replay.outcome === "NOT_REPLAYABLE" && recorded.replay.reason !== null && (
          <p className="mt-2 text-fg-muted">{NOT_REPLAYABLE_REASON_COPY[recorded.replay.reason]}</p>
        )}
        {recorded.replay.outcome === "MISMATCH" && recorded.replay.replayed_state !== null && (
          <p className="mt-2 text-feedback-error">
            Recalculating from the data available then produces {stateLabel(recorded.replay.replayed_state)}, not{" "}
            {stateLabel(recorded.state)}.
          </p>
        )}
      </div>

      {/* ---------- Data available then, vs today ---------- */}
      {historical_inputs.length > 0 && (
        <div>
          <SubHeading>{copy.INPUTS_HEADING}</SubHeading>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full min-w-[30rem] text-left">
              <thead>
                <tr className="text-xs text-fg-muted">
                  <th scope="col" className="py-1 pr-4 font-medium">
                    Observation
                  </th>
                  <th scope="col" className="py-1 pr-4 font-medium">
                    Then
                  </th>
                  <th scope="col" className="py-1 pr-4 font-medium">
                    Today
                  </th>
                  <th scope="col" className="py-1 font-medium">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="text-fg-secondary">
                {historical_inputs.map((input) => (
                  <tr key={`${input.series_id}-${input.observation_date}`} className="border-t border-line-subtle">
                    <th scope="row" className="py-1.5 pr-4 font-normal text-fg-muted">
                      {input.series_id} · {formatPeriod(input.observation_date)}
                    </th>
                    <td className="py-1.5 pr-4 tabular-nums">{formatInputValue(input.value_then, input.value_unit)}</td>
                    <td className="py-1.5 pr-4 tabular-nums">
                      {formatInputValue(input.value_today, input.value_unit)}
                    </td>
                    <td className="py-1.5">{INPUT_COMPARISON_LABEL[input.comparison]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ---------- Using today's revised data ---------- */}
      <div>
        <SubHeading>{copy.TODAY_HEADING}</SubHeading>
        <p className="mt-2 text-fg-secondary">
          {COMPARISON_STATUS_LABEL[current_comparison.status]}
          {current_comparison.status !== "NOT_COMPARABLE" && (
            <> · {copy.changedInputsCopy(current_comparison.changed_input_count)}</>
          )}
        </p>
        {current_comparison.reason !== null && (
          <p className="mt-1 text-fg-muted">{NOT_COMPARABLE_REASON_COPY[current_comparison.reason]}</p>
        )}
        {current_comparison.current_state !== null && current_comparison.state_differs !== null && (
          <p className="mt-1 text-fg-secondary">
            {copy.comparisonSummaryCopy(
              current_comparison.state_differs,
              stateLabel(current_comparison.current_state),
            )}
          </p>
        )}
        {current_comparison.methodology_differs && (
          <p className="mt-1 text-fg-muted">
            {copy.METHODOLOGY_DIFFERS_NOTE} Recorded under {current_comparison.methodology_id_then}; MacroChipz now runs{" "}
            {current_comparison.methodology_id_today}.
          </p>
        )}
      </div>

      {/* ---------- Same-run source changes ---------- */}
      {(related_changes.length > 0 || otherChanges !== null) && (
        <div>
          <SubHeading>{copy.RELATED_CHANGES_HEADING}</SubHeading>
          {related_changes.length > 0 && (
            <ul className="mt-2 space-y-1.5 text-fg-secondary">
              {related_changes.map((change) => (
                <li key={`${change.series_id}-${change.observation_date}-${change.change_type}`}>
                  <span className="text-fg-muted">
                    {observationChangeLabel(change.change_type)} · {change.series_id} ·{" "}
                    {formatPeriod(change.observation_date)}
                  </span>
                  <span className="ml-2 tabular-nums">
                    {change.previous_value !== null && (
                      <>
                        {change.previous_value}
                        <span aria-hidden="true" className="mx-1.5 text-fg-faint">
                          →
                        </span>
                      </>
                    )}
                    {change.new_value ?? "—"}
                  </span>
                  <span className="ml-2 text-xs text-fg-muted">
                    detected {formatObservationDate(change.detected_at.slice(0, 10))}
                  </span>
                </li>
              ))}
            </ul>
          )}
          <p className="mt-2 text-xs text-fg-muted">{copy.RELATED_CHANGES_NOTE}</p>
          {otherChanges !== null && <p className="mt-1 text-xs text-fg-muted">{otherChanges}</p>}
        </div>
      )}

      {/* ---------- Reconstructed-input disclosure ---------- */}
      {recorded.replay.inputs_include_backfilled && (
        <p className="border-l-2 border-line pl-3 text-xs text-fg-muted">{copy.BACKFILL_DISCLOSURE}</p>
      )}
    </div>
  );
}
