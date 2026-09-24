import { getInflationMonitor, getInflationStateDuration, getInflationWhatChanged } from "../api/inflation";
import { getCorePceObservations } from "../api/series";
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
import { PriceClimb } from "../components/inflation/PriceClimb";
import { Disclosure } from "../components/Disclosure";
import { TargetPanel } from "../components/inflation/TargetPanel";
import { WhatChangedSection } from "../components/inflation/WhatChangedSection";
import { UnderstandWorld } from "../components/explainers/UnderstandLinks";
import { inflationStateLabelOrRaw, inflationStateToneOrNeutral } from "../lib/inflationLabels";
import { formatPeriod } from "../lib/format";

const MONITOR_ERROR_MESSAGE = "Inflation data could not be loaded.";
const CHANGES_ERROR_MESSAGE = "What changed could not be loaded.";
const CLIMB_ERROR_MESSAGE = "The price level could not be loaded.";

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
  /* #50B: the PRICE LEVEL. An existing endpoint, already serving 59
     monthly Core PCE observations. Independently loaded like every
     other resource on this page — the climb failing never blanks the
     rates, and the rates failing never blanks the climb. */
  const climb = useApiResource(getCorePceObservations);

  return (
    <div>
      {/*
       * THE HERO (#50B), replacing `PageHeader`.
       *
       * The standfirst is VERBATIM from `explain.inflation-vs-prices`
       * — the reviewed sentence that makes the whole distinction. Its
       * "6% to 3%" is an ILLUSTRATION and is labelled as one below, so
       * it can never be mistaken for a current observation.
       *
       * The old standfirst named four constructs ("levels, underlying
       * momentum, confirmation, and the evidence behind each
       * conclusion") and defined none of them.
       */}
      <header>
        <p className="type-label text-fg-muted">Inflation</p>
        <h1 className="type-page-title mt-2 max-w-3xl text-balance">Prices are a level. Inflation is its slope.</h1>
        <p className="mt-3 max-w-prose text-fg-secondary">
          Inflation measures change, not level. It tells you how fast prices are rising, not how far they have already
          risen.
        </p>

        {/* Plain language first; identifiers live in the provenance
            disclosure at the foot of the page. */}
        {monitor.status === "success" && (
          <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-2 text-sm text-fg-muted">
            <span className="inline-flex items-center gap-2 rounded-full border border-line px-3 py-1">
              <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-brand" />
              Core prices through {formatPeriod(monitor.data.underlying_momentum.calculation_period)}
            </span>
            <span>Published by the U.S. Bureau of Economic Analysis, via FRED</span>
          </div>
        )}
        <div className="mt-3">
          <DataBasisNote />
        </div>
      </header>

      <div className="mt-8 space-y-8">
        {/* 1. THE CLIMB — the price level, and the rate as its slope. */}
        <section aria-labelledby="inflation-climb-heading">
          <h2 id="inflation-climb-heading" className="text-sm font-medium text-fg-muted">
            The climb
          </h2>
          <div className="mt-3">
            {(monitor.status === "loading" || climb.status === "loading") && (
              <LoadingSkeleton label="Loading the price level" heightClassName="h-80" />
            )}
            {climb.status === "error" && <ErrorMessage message={CLIMB_ERROR_MESSAGE} onRetry={climb.reload} />}
            {monitor.status === "error" && <ErrorMessage message={MONITOR_ERROR_MESSAGE} onRetry={monitor.reload} />}
            {monitor.status === "success" && climb.status === "success" && (
              <PriceClimb momentum={monitor.data.underlying_momentum} series={climb.data} />
            )}
          </div>
        </section>

        {/* 2. The misconception, in the reviewed words, once. */}
        <section aria-labelledby="inflation-means-heading">
          <h2 id="inflation-means-heading" className="text-sm font-medium text-fg-muted">
            What that actually means
          </h2>
          <div className="lx-card mt-3 rounded-xl p-5 sm:p-6">
            <p className="type-label text-[color:var(--mc-brand)]">
              Wait, inflation falling doesn&rsquo;t mean prices are falling?
            </p>
            <p className="mt-2 max-w-prose text-base font-semibold text-fg sm:text-lg">
              Correct. Inflation is the rate prices are rising. When inflation falls, prices are still going up — just
              more slowly than before.
            </p>
            <p className="mt-3 max-w-prose text-sm text-fg-secondary">
              If news reports say inflation is cooling and your shopping still costs more than it used to, both things
              are true at once. Cooling describes the speed of the increase, not a reversal of it.
            </p>
            {/*
             * AN ILLUSTRATION, MARKED AS ONE, AND ONLY ONCE THERE IS
             * SOMETHING TO CONTRAST IT WITH.
             *
             * The numbers are an example from the reviewed explainer,
             * not observations. The label alone is not enough: this
             * page's own loading guard forbids ANY percentage before
             * data arrives, and it is right to — "6% to 3%" on an
             * otherwise empty Inflation page reads as a reading no
             * matter what the sentence beside it says.
             *
             * IT WAITS FOR THE CLIMB, NOT JUST THE MONITOR (#50B
             * verification). With the monitor resolved and the price
             * series failed, a reader saw "The price level could not
             * be loaded" and, an inch below it, "6% to 3%". The
             * example exists to contrast with the LEVEL the climb
             * draws; with no climb there is nothing for it to anchor
             * to, and an unanchored pair of percentages beside an
             * error message is precisely the misreading this guard
             * exists to prevent.
             *
             * The two reviewed sentences above carry the lesson
             * meanwhile, and they contain no figures.
             */}
            {monitor.status === "success" && climb.status === "success" && (
              <p className="mt-4 max-w-prose rounded-lg border border-line-subtle bg-surface-subtle p-3 text-sm text-fg-muted">
                <span className="font-semibold text-fg-secondary">For example, not a current reading: </span>
                an inflation rate dropping from 6% to 3% means prices rose half as fast this year as last year. It does
                not mean anything got cheaper.
              </p>
            )}
          </div>
        </section>

        {/* 3. Headline and core, each with its own observation month. */}
        {monitor.status === "success" && <HeadlineContext headlineContext={monitor.data.headline_context} />}

        {/* 4. The classification and everything technical behind it.
               #50A found "Mixed" rendered fourteen times and the state
               badge as the largest element on the first screen. It is a
               CONCLUSION, so it now sits after the thing it classifies
               — and its supporting detail is one disclosure rather than
               four full-width sections. */}
        {monitor.status === "success" && (
          <section aria-labelledby="inflation-classification-heading">
            <h2 id="inflation-classification-heading" className="text-sm font-medium text-fg-muted">
              How MacroChipz classifies this
            </h2>
            <div className="mt-3">
              <InflationHero momentum={monitor.data.underlying_momentum} stateDuration={stateDuration} />
            </div>
            <div className="mt-4 max-w-3xl">
              <Disclosure summary="The metrics behind the classification" summaryClassName="min-h-11">
                <div className="space-y-8 pb-2 pt-2">
                  <MomentumMetrics momentum={monitor.data.underlying_momentum} />
                  <TargetPanel target={monitor.data.target} />
                  <ConfirmationPanel confirmation={monitor.data.confirmation} />
                </div>
              </Disclosure>
            </div>
          </section>
        )}

        {/* 5. WHAT THIS CANNOT TELL YOU (#50B).
               New. #50A found nothing on the page stating that a
               national index is not a reader's own cost of living —
               conspicuous on a world whose subject is "why does my
               shopping cost more". */}
        {monitor.status === "success" && (
          <section aria-labelledby="inflation-limits-heading">
            <h2 id="inflation-limits-heading" className="text-sm font-medium text-fg-muted">
              What this cannot tell you
            </h2>
            <ul className="lx-card mt-3 list-disc space-y-2.5 rounded-xl p-5 pl-9 sm:p-6 sm:pl-10">
              <li className="max-w-prose text-sm text-fg-secondary">
                This is a national price index. It is not your cost of living, and MacroChipz does not estimate one —
                what you actually spend depends on what you buy, which this data does not know.
              </li>
              <li className="max-w-prose text-sm text-fg-secondary">
                There are no category figures here: no groceries, rent, fuel or transport. The index is published as one
                number and MacroChipz does not break it apart.
              </li>
              <li className="max-w-prose text-sm text-fg-secondary">
                A falling rate is not a falling price level. For the climb above to come down, the rate would have to go
                below zero — a different thing, with a different name.
              </li>
              <li className="max-w-prose text-sm text-fg-secondary">
                Core prices and headline CPI are published for different months, so the two figures above do not
                describe the same period.
              </li>
            </ul>
          </section>
        )}

        {/* 6. What changed — evidence, below the orientation. */}
        {whatChanged.status === "loading" && <LoadingSkeleton label="Loading what changed" heightClassName="h-48" />}
        {whatChanged.status === "error" && <ErrorMessage message={CHANGES_ERROR_MESSAGE} onRetry={whatChanged.reload} />}
        {whatChanged.status === "success" && <WhatChangedSection whatChanged={whatChanged.data} />}

        {/* 7. Intelligence History (Increment #32) -- recorded
               conclusions and whether they still reproduce.
               BEHIND A DISCLOSURE (#50B): #50A measured it at 1,125px,
               22% of a phone page, for twelve recorded classifications.
               It is a genuinely rare product property and it is not
               orientation. Nothing was removed and nothing was
               summarised -- the whole section is one tap away. */}
        <div className="max-w-3xl">
          <Disclosure summary="Recorded conclusions, and whether they still reproduce" summaryClassName="min-h-11">
            <div className="pt-2">
              <IntelligenceHistorySection
                monitor="inflation"
                history={history}
                headingId="inflation-intelligence-history-heading"
                analystAvailable={analyst.status === "success" && analyst.data.available}
                stateLabel={inflationStateLabelOrRaw}
                stateTone={inflationStateToneOrNeutral}
              />
            </div>
          </Disclosure>
        </div>

        {/* 8. Ask MacroChipz (Increment #33) -- an optional interpretive
            layer over everything above. It never affects the canonical
            content. */}
        <AskMacroChipz
          contextType="INFLATION"
          contextRef={{ type: "INFLATION" }}
          available={analyst.status === "success" && analyst.data.available}
          headingId="inflation-analyst-heading"
        />

        {/* 9. Evidence / methodology disclosure */}
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
            className="inline-flex min-h-11 items-center text-sm font-medium text-fg-secondary underline-offset-4 hover:text-fg hover:underline"
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
          className="inline-flex min-h-11 items-center text-sm font-medium text-fg-secondary underline-offset-4 hover:text-fg hover:underline"
        >
          Revision history →
        </a>
      </p>
    </div>
  );
}
