import { Link } from "react-router-dom";

import type { SeriesMomentumResult } from "../../api/inflation.types";
import type { LaborMonitorResult } from "../../api/labor.types";
import type { ApiResourceState } from "../../api/useApiResource";
import { composeMonitorRelation } from "../../lib/relateComposition";
import { ErrorMessage } from "../ErrorMessage";
import { LoadingSkeleton } from "../LoadingSkeleton";

const INFLATION_ERROR_MESSAGE = "Inflation data could not be loaded.";
const LABOR_ERROR_MESSAGE = "Labor data could not be loaded.";

/**
 * The Economic Overview's "How They Relate" section -- Relate V1,
 * frozen by docs/product/relate-composition-v1.md (Increment #23C).
 * Renders exactly one deterministic COMPOSITION sentence over
 * Inflation's and Labor's own already-canonical top-level states
 * (`lib/relateComposition.ts`'s `composeMonitorRelation`) plus the two
 * existing "View {Domain} →" CTAs -- nothing else. No new badges, no
 * score, no chart, no interpretation paragraph, no regime label, no
 * market implication (§12/§14 of the frozen contract).
 *
 * Reuses the SAME two already-fetched monitor resources
 * `pages/Overview.tsx`'s `CurrentStateSection` already consumes -- no
 * new `useApiResource` call, no new network request. Per the frozen
 * contract's own §11: no composed sentence renders until BOTH
 * resources have reached a terminal state (`success` or `error`) --
 * while either is still `loading`, this section shows only the
 * existing `LoadingSkeleton` pattern, never a sentence built from one
 * side's already-resolved state while the other is still pending. Per
 * §10: a resource error is infrastructure failure, never composed into
 * a relationship sentence or into the insufficient-data wording (which
 * requires having successfully learned a state, not merely failed to
 * fetch one) -- the working side's own individual fact still renders
 * verbatim, and the failed side gets its own existing error message,
 * mirroring `CurrentStateSection`'s identical failure-isolation
 * discipline exactly.
 */
export function HowTheyRelate({
  inflation,
  labor,
}: {
  inflation: ApiResourceState<{ underlying_momentum: SeriesMomentumResult }> & { reload: () => void };
  labor: ApiResourceState<LaborMonitorResult> & { reload: () => void };
}) {
  const stillLoading = inflation.status === "loading" || labor.status === "loading";

  return (
    <section aria-labelledby="overview-how-they-relate-heading">
      <h2 id="overview-how-they-relate-heading" className="text-sm font-medium text-neutral-500">
        How They Relate
      </h2>

      <div className="mt-3 space-y-3">
        {stillLoading && <LoadingSkeleton label="Loading how Inflation and Labor relate" heightClassName="h-16" />}

        {!stillLoading && inflation.status === "error" && <ErrorMessage message={INFLATION_ERROR_MESSAGE} onRetry={inflation.reload} />}
        {!stillLoading && labor.status === "error" && <ErrorMessage message={LABOR_ERROR_MESSAGE} onRetry={labor.reload} />}

        {!stillLoading && inflation.status === "success" && labor.status === "success" && (
          <p className="text-sm text-neutral-700">
            {
              composeMonitorRelation(
                { state: inflation.data.underlying_momentum.state, period: inflation.data.underlying_momentum.calculation_period },
                { state: labor.data.state, period: labor.data.evaluation_period },
              ).sentence
            }
          </p>
        )}

        <div className="flex gap-4">
          <Link to="/inflation" className="inline-block text-sm font-medium text-neutral-700 hover:text-neutral-900">
            View Inflation →
          </Link>
          <Link to="/labor" className="inline-block text-sm font-medium text-neutral-700 hover:text-neutral-900">
            View Labor →
          </Link>
        </div>
      </div>
    </section>
  );
}
