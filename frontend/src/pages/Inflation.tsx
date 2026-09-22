import { getInflationMonitor, getInflationStateDuration, getInflationWhatChanged } from "../api/inflation";
import { getAnalystAvailability } from "../api/analyst";
import { getInflationHistory } from "../api/monitorHistory";
import { useApiResource } from "../api/useApiResource";
import { AskMacroChipz } from "../components/analyst/AskMacroChipz";
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
import { UnderstandWorld } from "../components/explainers/UnderstandLinks";
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
  const analyst = useApiResource(getAnalystAvailability);

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
          analystAvailable={analyst.status === "success" && analyst.data.available}
          stateLabel={inflationStateLabelOrRaw}
          stateTone={inflationStateToneOrNeutral}
        />

        {/* 9. Ask MacroChipz (Increment #33) -- an optional interpretive
            layer over everything above. It never affects the canonical
            content: when the Analyst is unconfigured or its availability
            check fails, this renders a short note and nothing else on the
            page changes. */}
        <AskMacroChipz
          contextType="INFLATION"
          contextRef={{ type: "INFLATION" }}
          available={analyst.status === "success" && analyst.data.available}
          headingId="inflation-analyst-heading"
        />

        {/* 10. Evidence / methodology disclosure */}
        {(monitor.status === "success" || whatChanged.status === "success") && (
          <MethodologyDisclosure
            monitor={monitor.status === "success" ? monitor.data : null}
            whatChanged={whatChanged.status === "success" ? whatChanged.data : null}
          />
        )}
      </div>

      {/* Cross-world navigation (#45B). NAVIGATION ONLY.
          Market-implied inflation compensation is a RATES-page metric
          ABOUT inflation, computed from two Treasury series -- #28
          classifies "market vs data" as same-concept (Class A)
          confirmation rather than cross-domain inference, which is why
          a link here is legitimate where "equities confirm labor" is
          not. It still asserts nothing: the frozen prohibition in
          relate-compare-audit-v1.md sections 15/16 on "confirms",
          "diverges" and the rest is untouched, and no sentence here
          claims the two agree, disagree, or move together. */}
      <div className="mt-10 border-t border-line pt-8">
        <h2 className="text-sm font-medium text-fg-muted">Elsewhere in MacroChipz</h2>
        <p className="mt-2 max-w-prose text-sm text-fg-secondary">
          MacroChipz also publishes market-implied inflation compensation — the difference between nominal and
          inflation-protected Treasury yields at the same maturity. It is measured a completely different way from the
          price indexes above, and MacroChipz draws no conclusion from comparing them.
        </p>
        <p className="mt-3">
          <a
            href="/rates"
            className="text-sm font-medium text-fg-secondary underline-offset-4 hover:text-fg hover:underline"
          >
            Explore Rates →
          </a>
        </p>
      </div>

      <div className="mt-10 border-t border-line pt-8">
        <UnderstandWorld world="INFLATION" />
      </div>

      {/* #43. A plain anchor rather than a router Link: this is a
          cross-capability jump out of a world, and it keeps the page
          renderable without router context. */}
      <p className="mt-6">
        <a
          href="/revisions"
          className="text-sm font-medium text-fg-secondary underline-offset-4 hover:text-fg hover:underline"
        >
          Revision history →
        </a>
      </p>
    </div>
  );
}
