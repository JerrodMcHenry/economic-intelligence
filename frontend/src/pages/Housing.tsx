import { getHousing } from "../api/housing";
import type { HousingResult } from "../api/housing.types";
import { useApiResource } from "../api/useApiResource";
import { ErrorMessage } from "../components/ErrorMessage";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { PageHeader } from "../components/PageHeader";
import { UnderstandWorld } from "../components/explainers/UnderstandLinks";
import { HousingEvidence } from "../components/housing/HousingEvidence";
import { HousingPipelineChart } from "../components/housing/HousingPipelineChart";
import { HousingStageCard } from "../components/housing/HousingStageCard";
import { PipelineDiagram } from "../components/housing/PipelineDiagram";
import { RateContext } from "../components/housing/RateContext";
import { formatPeriod } from "../lib/format";

const ERROR_MESSAGE = "Housing data could not be loaded.";

/**
 * The Housing world (Increment #45) — MacroChipz's fourth.
 *
 * ================================================================
 * THE WORLD WITH NO STATE
 * ================================================================
 *
 * Inflation, Jobs and Rates each render a conclusion a frozen
 * methodology reached. This page renders none, because there is no
 * `housing_v1.0` and nothing concluded anything. What it shows is what
 * Census published and the arithmetic between those figures.
 *
 * That is a harder page to write than a graded one, and the temptation
 * it creates is real: "Permits −2.7%" wants a word next to it, and the
 * word would be invented. So the page answers a narrower question than
 * a state would — **how many homes are entering the pipeline** — and
 * leaves the reader to draw the conclusion, which is the only honest
 * arrangement available until a housing methodology exists.
 *
 * Every number on this page is rendered exactly as the backend computed
 * it. This module and every component it uses perform no economic
 * arithmetic whatsoever: no change, no percentage, no annualisation, no
 * de-annualisation. That boundary is enforced by
 * `src/test/no-economic-logic.test.ts` and
 * `src/test/no-housing-derivation.test.ts`, not merely by convention.
 *
 * ================================================================
 * PAGE ORDER
 * ================================================================
 *
 * Answers the reader's questions in the order they ask them: what do
 * these words mean, what are the numbers, what do they look like over
 * time, why is the big number not a count of homes, what about mortgage
 * rates, and where did all of it come from.
 *
 * NO ASK MACROCHIPZ, DELIBERATELY. The bounded Analyst has no canonical
 * Housing context (#33's context types are Inflation, Labor, Rates and
 * monitor history), and widening it simply because a world appeared is
 * what #45 forbids. Housing questions are unsupported rather than
 * answered from a context that does not exist.
 */
function HousingContent({ result }: { result: HousingResult }) {
  const hasAnyData = result.as_of_period !== null;

  if (!hasAnyData) {
    return (
      <div className="mt-8 rounded-lg border border-line bg-surface p-6">
        <h2 className="type-card-heading text-fg">No housing data yet</h2>
        <p className="mt-2 max-w-prose text-sm text-fg-secondary">
          No Census New Residential Construction observations have been ingested into this environment yet, so no
          permits, starts or completions can be shown. Nothing here is estimated in the meantime.
        </p>
        <p className="mt-2 max-w-prose type-meta text-fg-muted">{result.attribution}</p>
      </div>
    );
  }

  return (
    <div className="mt-8 divide-y divide-line [&>*]:py-8 [&>*:first-child]:pt-0 [&>*:last-child]:pb-0">
      {/* 1. What the three words mean, and what they do not mean. */}
      <section aria-labelledby="housing-pipeline-heading">
        <h2 id="housing-pipeline-heading" className="text-sm font-medium text-fg-muted">
          The construction pipeline
        </h2>
        <div className="mt-3">
          <PipelineDiagram />
        </div>
      </section>

      {/* 2. The figures. */}
      <section aria-labelledby="housing-latest-heading">
        <h2 id="housing-latest-heading" className="text-sm font-medium text-fg-muted">
          Latest published figures
        </h2>
        <p className="mt-2 max-w-prose text-sm text-fg-secondary">
          The large figure in each card is a seasonally adjusted annual rate — the month&rsquo;s pace of building,
          expressed as a yearly total. The figure beneath it is how many homes were actually counted that month.
        </p>
        <ul className="mt-4 grid gap-4 lg:grid-cols-3">
          {result.stages.map((stage) => (
            <HousingStageCard key={stage.stage} stage={stage} />
          ))}
        </ul>
      </section>

      {/* 3. The same three measures over time, on one axis. */}
      <section aria-labelledby="housing-trend-heading">
        <h2 id="housing-trend-heading" className="text-sm font-medium text-fg-muted">
          Over the last five years
        </h2>
        <div className="mt-3 rounded-lg border border-line bg-surface p-5 sm:p-6">
          <HousingPipelineChart stages={result.stages} />
        </div>
      </section>

      {/* 4. The explanation the big number cannot do without. Rendered
             from the response rather than written here, because it is a
             canonical statement about what the figure means, not
             presentation copy. */}
      <section aria-labelledby="housing-saar-heading">
        <h2 id="housing-saar-heading" className="text-sm font-medium text-fg-muted">
          Why the big number is not a count of homes
        </h2>
        <p className="mt-3 max-w-prose text-sm text-fg-secondary">{result.saar_explanation}</p>
        <p className="mt-3">
          <a
            href="/explain/saar-housing"
            className="text-sm font-medium text-fg-secondary underline-offset-4 hover:text-fg hover:underline"
          >
            Wait, 1.5 million homes weren&rsquo;t built this month? →
          </a>
        </p>
      </section>

      {/* 5. The question every reader of this page is already asking. */}
      <RateContext />

      {/* 6. Verify. */}
      <section aria-labelledby="housing-evidence-heading">
        <h2 id="housing-evidence-heading" className="text-sm font-medium text-fg-muted">
          Evidence &amp; limitations
        </h2>
        <div className="mt-3 max-w-3xl">
          <HousingEvidence result={result} />
        </div>
      </section>
    </div>
  );
}

export function HousingPage() {
  const housing = useApiResource(getHousing);

  return (
    <div>
      <PageHeader
        title="Housing"
        description="How many homes are being authorised, started and finished across the country — and what those numbers do and do not tell you."
      >
        {housing.status === "success" && housing.data.as_of_period !== null && (
          <p className="type-meta text-fg-muted">
            Latest published month: {formatPeriod(housing.data.as_of_period)}
          </p>
        )}
      </PageHeader>

      {housing.status === "loading" && (
        <div className="mt-8">
          <LoadingSkeleton label="Loading housing data" heightClassName="h-64" />
        </div>
      )}
      {housing.status === "error" && (
        <div className="mt-8">
          <ErrorMessage message={ERROR_MESSAGE} onRetry={housing.reload} />
        </div>
      )}
      {housing.status === "success" && <HousingContent result={housing.data} />}

      <div className="mt-10 border-t border-line pt-8">
        <UnderstandWorld world="HOUSING" />
      </div>
    </div>
  );
}
