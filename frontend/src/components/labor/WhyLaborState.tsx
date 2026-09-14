import type { LaborMonitorResult } from "../../api/labor.types";
import { laborStateExplanation } from "../../content/explanations/labor";
import { formatPeriod } from "../../lib/format";
import { employmentStateLabel, laborStateLabel, unemploymentStateLabel } from "../../lib/laborLabels";

/**
 * "Why is Labor {State}?" -- a result explanation, not a concept one:
 * it combines the curated explanation for the backend's own `state`
 * with the exact backend evidence already present on this response
 * (Employment's own state, Unemployment's own trend, the shared
 * evaluation period). It never re-derives the state, and it never
 * hides disagreement -- both component states are always shown,
 * including (especially) when `state === "MIXED"`, so contradictory
 * evidence is visible rather than papered over (see
 * docs/architecture/labor-ui-v1.md §11/§14). No `if (metric < ...)`
 * logic exists here or anywhere in this file's import graph -- this
 * mirrors components/inflation/WhyThisState.tsx exactly.
 */
export function WhyLaborState({ result }: { result: LaborMonitorResult }) {
  const explanation = laborStateExplanation(result.state);

  return (
    <details className="group mt-3">
      <summary className="inline-flex cursor-pointer select-none list-none items-center gap-1 text-sm font-medium text-neutral-600 hover:text-neutral-900 [&::-webkit-details-marker]:hidden">
        Why {laborStateLabel(result.state)}?
      </summary>
      <div className="mt-2 max-w-sm rounded-md border border-neutral-200 bg-white p-3 text-sm">
        <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-neutral-600">
          <dt className="text-neutral-400">Employment</dt>
          <dd className="text-right">{employmentStateLabel(result.employment.state)}</dd>
          <dt className="text-neutral-400">Unemployment trend</dt>
          <dd className="text-right">{unemploymentStateLabel(result.unemployment.state)}</dd>
          <dt className="text-neutral-400">Evaluation period</dt>
          <dd className="text-right">{formatPeriod(result.evaluation_period)}</dd>
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
