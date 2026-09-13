import type { HeadlineContextResult, SeriesMomentumResult } from "../../api/inflation.types";
import { formatPercent, formatPeriod } from "../../lib/format";
import { inflationStateLabel, inflationStateTone } from "../../lib/inflationLabels";
import { Badge } from "./Badge";
import { EvidenceDisclosure } from "./EvidenceDisclosure";

function HeadlineSeriesCard({ title, series }: { title: string; series: SeriesMomentumResult }) {
  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-neutral-400">
        {title} ({series.series_id})
      </p>
      <div className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <Badge label={inflationStateLabel(series.state)} tone={inflationStateTone(series.state)} />
        <span className="text-xl font-semibold tabular-nums text-neutral-900">{formatPercent(series.r_12m)}</span>
        <span className="text-xs text-neutral-500">12M</span>
      </div>
      <p className="mt-1 text-xs text-neutral-500">{formatPeriod(series.calculation_period)}</p>
      <div className="mt-2">
        <EvidenceDisclosure label={`${title} 12M`} evidence={series.evidence_12m} />
      </div>
    </div>
  );
}

/**
 * Headline PCE and headline CPI shown as secondary, independent
 * context -- each with its own state, value, and period. No combined
 * score, consensus, or aggregate state is derived across them or with
 * the primary Core PCE read above.
 */
export function HeadlineContext({ headlineContext }: { headlineContext: HeadlineContextResult }) {
  return (
    <section aria-labelledby="headline-context-heading">
      <h2 id="headline-context-heading" className="text-sm font-medium text-neutral-500">
        Headline context
      </h2>
      <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <HeadlineSeriesCard title="Headline PCE" series={headlineContext.headline_pce} />
        <HeadlineSeriesCard title="Headline CPI" series={headlineContext.headline_cpi} />
      </div>
    </section>
  );
}
