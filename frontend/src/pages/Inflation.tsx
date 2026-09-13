import { getInflationMonitor, getInflationWhatChanged } from "../api/inflation";
import { useApiResource } from "../api/useApiResource";
import { ErrorMessage } from "../components/ErrorMessage";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { ConfirmationPanel } from "../components/inflation/ConfirmationPanel";
import { DataBasisNote } from "../components/inflation/DataBasisNote";
import { HeadlineContext } from "../components/inflation/HeadlineContext";
import { InflationHero } from "../components/inflation/InflationHero";
import { MethodologyDisclosure } from "../components/inflation/MethodologyDisclosure";
import { MomentumMetrics } from "../components/inflation/MomentumMetrics";
import { TargetPanel } from "../components/inflation/TargetPanel";
import { WhatChangedSection } from "../components/inflation/WhatChangedSection";

const MONITOR_ERROR_MESSAGE = "Inflation data could not be loaded.";
const CHANGES_ERROR_MESSAGE = "What changed could not be loaded.";

/**
 * The real Inflation Monitor product page. Loads
 * `GET /api/v1/monitors/inflation` and `GET /api/v1/monitors/inflation/changes`
 * completely independently (see useApiResource) -- one failing never
 * blanks or fabricates the other. Every economic value, state, and
 * relationship rendered below is exactly what those two endpoints
 * returned; this page composes and formats, it does not calculate.
 */
export function InflationPage() {
  const monitor = useApiResource(getInflationMonitor);
  const whatChanged = useApiResource(getInflationWhatChanged);

  return (
    <div className="max-w-3xl">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-neutral-900">Inflation</h1>
        <p className="mt-2 max-w-prose text-neutral-600">
          Track inflation levels, underlying momentum, confirmation, and the evidence behind each conclusion.
        </p>
        <div className="mt-3">
          <DataBasisNote />
        </div>
      </header>

      <div className="mt-8 divide-y divide-neutral-200 [&>*]:pt-8 [&>*:first-child]:pt-0">
        {/* 2. Primary underlying momentum state */}
        {monitor.status === "loading" && <LoadingSkeleton label="Loading underlying momentum" heightClassName="h-32" />}
        {monitor.status === "error" && <ErrorMessage message={MONITOR_ERROR_MESSAGE} onRetry={monitor.reload} />}
        {monitor.status === "success" && <InflationHero momentum={monitor.data.underlying_momentum} />}

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

        {/* 8. Evidence / methodology disclosure */}
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
