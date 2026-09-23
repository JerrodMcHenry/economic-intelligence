import type { LaborMonitorResult } from "../../api/labor.types";
import type { SeriesMomentumResult } from "../../api/inflation.types";
import type { ApiResourceState } from "../../api/useApiResource";
import { ErrorMessage } from "../ErrorMessage";
import { LoadingSkeleton } from "../LoadingSkeleton";
import { InflationCurrentStateCard } from "./InflationCurrentStateCard";
import { LaborCurrentStateCard } from "./LaborCurrentStateCard";

const MONITOR_ERROR_MESSAGE = "Inflation data could not be loaded.";
const LABOR_ERROR_MESSAGE = "Jobs data could not be loaded.";

/**
 * The Economic Overview's "Current State" section (Increment #20E.2:
 * converted from an Inflation-only section into a true peer-domain
 * presentation, docs/architecture/labor-ui-v1.md §29). Inflation and
 * Labor each render inside their OWN independent
 * `loading`/`error`/`success` branch, driven by their own already-loaded
 * `useApiResource` state -- Inflation's monitor failing never hides
 * Labor's card, and vice versa (§38's own failure-isolation table).
 *
 * Deliberately no aggregate "Economy State", no score, no averaging of
 * the two domains' own states -- two independent, sourced readings,
 * shown side by side, never combined (mission's own absolute
 * prohibition). The stale "Inflation is the first fully deterministic
 * monitor..." sentence this section used to carry is REMOVED, not
 * replaced -- there is no natural monitor-count sentence that wouldn't
 * itself go stale again at a third monitor (see
 * docs/ENGINEERING_JOURNAL.md's #20E.2 entry).
 */
export function CurrentStateSection({
  inflation,
  labor,
}: {
  inflation: ApiResourceState<{ underlying_momentum: SeriesMomentumResult }> & { reload: () => void };
  labor: ApiResourceState<LaborMonitorResult> & { reload: () => void };
}) {
  return (
    <section aria-labelledby="overview-current-state-heading">
      <h2 id="overview-current-state-heading" className="text-sm font-medium text-fg-muted">
        Current State
      </h2>

      {/*
       * #48A: two peers, side by side from `md`, each in its own card.
       * They were stacked in a `space-y-6` with no surface of their
       * own, which on a page of glass cards read as loose text rather
       * than as two readings.
       *
       * FAILURE ISOLATION IS UNCHANGED, and the grid is why this is
       * stated: each domain keeps its own cell and its own
       * loading/error/success branch, so Inflation failing still
       * leaves Jobs rendered in place rather than collapsing the row.
       */}
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <div className="lx-card rounded-xl p-4 sm:p-5">
          {inflation.status === "loading" && <LoadingSkeleton label="Loading Inflation current state" heightClassName="h-32" />}
          {inflation.status === "error" && <ErrorMessage message={MONITOR_ERROR_MESSAGE} onRetry={inflation.reload} />}
          {inflation.status === "success" && <InflationCurrentStateCard momentum={inflation.data.underlying_momentum} />}
        </div>

        <div className="lx-card rounded-xl p-4 sm:p-5">
          {labor.status === "loading" && <LoadingSkeleton label="Loading Labor current state" heightClassName="h-32" />}
          {labor.status === "error" && <ErrorMessage message={LABOR_ERROR_MESSAGE} onRetry={labor.reload} />}
          {labor.status === "success" && <LaborCurrentStateCard result={labor.data} />}
        </div>
      </div>
    </section>
  );
}
