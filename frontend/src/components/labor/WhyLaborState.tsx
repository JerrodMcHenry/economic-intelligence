import type { LaborMonitorResult } from "../../api/labor.types";
import { laborStateExplanation } from "../../content/explanations/labor";
import { formatPeriod } from "../../lib/format";
import { employmentStateLabel, laborStateLabel, unemploymentStateLabel } from "../../lib/laborLabels";
import { composeLaborComponents } from "../../lib/relateComposition";

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
 *
 * Increment #23C (Relate V1, frozen by
 * docs/product/relate-composition-v1.md §16/§18/§19/§22): appended
 * after the existing evidence `<dl>` and curated explanation text is
 * one deterministic COMPOSITION sentence
 * (`lib/relateComposition.ts`'s `composeLaborComponents`) stating
 * Employment's and Unemployment's own states plus a verbatim report of
 * the top-level `LaborState` they feed into -- reusing, never
 * re-deriving, `combine_labor_state`'s own existing backend result.
 * Deliberately placed inside this ALREADY-EXISTING disclosure rather
 * than as a new eighth `/labor` page section, so it does not duplicate
 * the top-level Labor methodology explanation this component already
 * exists to provide.
 */
export function WhyLaborState({ result }: { result: LaborMonitorResult }) {
  const explanation = laborStateExplanation(result.state);
  const relate = composeLaborComponents(result.employment.state, result.unemployment.state, result.state);

  return (
    <details className="group mt-3">
      <summary className="inline-flex cursor-pointer select-none list-none items-center gap-1 text-sm font-medium text-fg-secondary hover:text-fg [&::-webkit-details-marker]:hidden">
        Why {laborStateLabel(result.state)}?
      </summary>
      <div className="mt-2 max-w-sm rounded-md border border-line bg-surface p-3 text-sm">
        <dl className="grid grid-cols-1 sm:grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-fg-secondary">
          <dt className="text-fg-muted">Employment</dt>
          <dd className="text-right">{employmentStateLabel(result.employment.state)}</dd>
          <dt className="text-fg-muted">Unemployment trend</dt>
          <dd className="text-right">{unemploymentStateLabel(result.unemployment.state)}</dd>
          <dt className="text-fg-muted">Evaluation period</dt>
          <dd className="text-right">{formatPeriod(result.evaluation_period)}</dd>
        </dl>
        <p className="mt-3 text-fg-secondary">{explanation.definition}</p>
        {explanation.whyItMatters && (
          <p className="mt-2 text-fg-secondary">
            <span className="font-medium text-fg-muted">Why it matters: </span>
            {explanation.whyItMatters}
          </p>
        )}
        <p className="mt-3 text-fg-secondary">{relate.sentence}</p>
      </div>
    </details>
  );
}
