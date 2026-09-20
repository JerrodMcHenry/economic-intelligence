import { getInflationMonitor, getInflationStateDuration, getInflationWhatChanged } from "../api/inflation";
import { getInflationHistory } from "../api/monitorHistory";
import { useApiResource } from "../api/useApiResource";
import { ErrorMessage } from "../components/ErrorMessage";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { IntelligenceHistorySection } from "../components/history/IntelligenceHistorySection";
import { ConfirmationPanel } from "../components/inflation/ConfirmationPanel";
import { DataBasisNote } from "../components/inflation/DataBasisNote";
import { HeadlineContext } from "../components/inflation/HeadlineContext";
import { InflationHero } from "../components/inflation/InflationHero";
import { MethodologyDisclosure } from "../components/inflation/MethodologyDisclosure";
import { MomentumMetrics } from "../components/inflation/MomentumMetrics";
import { TargetPanel } from "../components/inflation/TargetPanel";
import { WhatChangedSection } from "../components/inflation/WhatChangedSection";
import { PageHeader } from "../components/PageHeader";
import { inflationStateLabelOrRaw, inflationStateToneOrNeutral } from "../lib/inflationLabels";

const MONITOR_ERROR_MESSAGE = "Inflation data could not be loaded.";
const CHANGES_ERROR_MESSAGE = "What changed could not be loaded.";

/**
 * The real Inflation Monitor product page. Loads
 * `GET /api/v1/monitors/inflation`, `GET /api/v1/monitors/inflation/changes`,
 * and (Increment #24D) `GET /api/v1/monitors/inflation/state-duration`
 * completely independently (see useApiResource) -- one failing never
 * blanks or fabricates the others. Every economic value, state, and
 * relationship rendered below is exactly what those endpoints
 * returned; this page composes and formats, it does not calculate.
 * `stateDuration` is fetched here (the page), not inside
 * `InflationHero`, matching this page's own established "page owns
 * every resource, components stay dumb" convention -- one clear owner
 * per resource, never re-fetched inside the Hero or its disclosure.
 */
export function InflationPage() {
  const monitor = useApiResource(getInflationMonitor);
  const whatChanged = useApiResource(getInflationWhatChanged);
  const stateDuration = useApiResource(getInflationStateDuration);
  const history = useApiResource(getInflationHistory);

  return (
    <div>
      <PageHeader
        title="Inflation"
        description="Track inflation levels, underlying momentum, confirmation, and the evidence behind each conclusion."
      >
        <DataBasisNote />
      </PageHeader>

      <div className="mt-8 divide-y divide-line [&>*]:py-8 [&>*:first-child]:pt-0 [&>*:last-child]:pb-0">
        {/* 2. Primary underlying momentum state */}
        {monitor.status === "loading" && <LoadingSkeleton label="Loading underlying momentum" heightClassName="h-32" />}
        {monitor.status === "error" && <ErrorMessage message={MONITOR_ERROR_MESSAGE} onRetry={monitor.reload} />}
        {monitor.status === "success" && (
          <InflationHero momentum={monitor.data.underlying_momentum} stateDuration={stateDuration} />
        )}

        {/* 3. What changed */}
        {whatChanged.status === "loading" && <LoadingSkeleton label="Loading what changed" heightClassName="h-48" />}
        {whatChanged.status === "error" && <ErrorMessage message={CHANGES_ERROR_MESSAGE} onRetry={whatChanged.reload} />}
        {whatChanged.status === "success" && <WhatChangedSection whatChanged={whatChanged.data} />}

        {/* 4-7: Core PCE momentum, target/level, confirmation, headline
            context -- all sourced from the monitor resource, whose own
            loading/error UI is already shown once above; nothing
            duplicate renders here while that's the active state. */}
        {monitor.status === "success" && (
          <>
            <MomentumMetrics momentum={monitor.data.underlying_momentum} />
            <TargetPanel target={monitor.data.target} />
            <ConfirmationPanel confirmation={monitor.data.confirmation} />
            <HeadlineContext headlineContext={monitor.data.headline_context} />
          </>
        )}

        {/* 8. Intelligence History (Increment #32) -- recorded
            conclusions and whether they still reproduce. Placed just
            before the methodology disclosure so the page reads
            current -> recent -> historical -> how it works. */}
        <IntelligenceHistorySection
          monitor="inflation"
          history={history}
          headingId="inflation-intelligence-history-heading"
          stateLabel={inflationStateLabelOrRaw}
          stateTone={inflationStateToneOrNeutral}
        />

        {/* 9. Evidence / methodology disclosure */}
        {(monitor.status === "success" || whatChanged.status === "success") && (
          <MethodologyDisclosure
            monitor={monitor.status === "success" ? monitor.data : null}
            whatChanged={whatChanged.status === "success" ? whatChanged.data : null}
          />
        )}
      </div>
    </div>
  );
}
