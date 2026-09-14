import type { SeriesMomentumResult } from "../../api/inflation.types";
import { inflationStateExplanation } from "../../content/explanations/inflation";
import { formatPercent } from "../../lib/format";
import { inflationStateLabel } from "../../lib/inflationLabels";

/**
 * "Why is momentum {State}?" -- a result explanation, not a concept
 * one: it combines the curated explanation for the backend's own
 * `state` with the exact backend evidence (r_3m/r_6m/r_12m, neutral
 * band) already present on this response. It never re-derives the
 * state -- if the numbers looked to a human like they might suggest a
 * different classification, this still shows exactly what the backend
 * classified, because that classification is the only canonical
 * answer (see docs/methodology/inflation-monitor-v1.0.md's
 * "Classification rules"). No `if (r3m < ...)` logic exists here or
 * anywhere in this file's import graph.
 */
export function WhyThisState({ momentum }: { momentum: SeriesMomentumResult }) {
  const explanation = inflationStateExplanation(momentum.state);
  const hasBand = momentum.lower_boundary !== null && momentum.upper_boundary !== null;

  return (
    <details className="group mt-3">
      <summary className="inline-flex cursor-pointer select-none list-none items-center gap-1 text-sm font-medium text-neutral-600 hover:text-neutral-900 [&::-webkit-details-marker]:hidden">
        Why {inflationStateLabel(momentum.state)}?
      </summary>
      <div className="mt-2 max-w-sm rounded-md border border-neutral-200 bg-white p-3 text-sm">
        <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-neutral-600">
          <dt className="text-neutral-400">3M annualized</dt>
          <dd className="text-right tabular-nums">{formatPercent(momentum.r_3m_annualized)}</dd>
          <dt className="text-neutral-400">6M annualized</dt>
          <dd className="text-right tabular-nums">{formatPercent(momentum.r_6m_annualized)}</dd>
          <dt className="text-neutral-400">12M</dt>
          <dd className="text-right tabular-nums">{formatPercent(momentum.r_12m)}</dd>
          {hasBand && (
            <>
              <dt className="text-neutral-400">Neutral band</dt>
              <dd className="text-right tabular-nums">
                {formatPercent(momentum.lower_boundary)} – {formatPercent(momentum.upper_boundary)}
              </dd>
            </>
          )}
        </dl>
        <p className="mt-3 text-neutral-700">{explanation.definition}</p>
        {explanation.whyItMatters && (
          <p className="mt-2 text-neutral-600">
            <span className="font-medium text-neutral-500">Why it matters: </span>
            {explanation.whyItMatters}
          </p>
        )}
      </div>
    </details>
  );
}
