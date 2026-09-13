import type { SeriesMomentumResult } from "../../api/inflation.types";
import { formatPercent, formatPeriod } from "../../lib/format";
import { inflationStateLabel, inflationStateTone } from "../../lib/inflationLabels";
import { Badge } from "./Badge";

const HERO_METRICS = [
  { key: "r_3m_annualized", label: "3M" },
  { key: "r_6m_annualized", label: "6M" },
  { key: "r_12m", label: "12M" },
] as const;

/**
 * The primary, strongest visual element on the page: Core PCE's
 * canonical `state` (never re-labeled as good/bad/bullish/bearish),
 * scaled up as the page's single dominant object rather than sharing
 * top billing with a specific rate reading. `INSUFFICIENT_DATA` renders
 * through the same muted "unavailable" tone as every other unavailable
 * value on the page -- it must read as missing evidence, not a
 * direction. A compact 3M/6M/12M strip gives an at-a-glance read of
 * what's behind the state; the full metrics with evidence live in
 * MomentumMetrics below, not duplicated here.
 */
export function InflationHero({ momentum }: { momentum: SeriesMomentumResult }) {
  return (
    <section aria-labelledby="underlying-momentum-heading">
      <h2 id="underlying-momentum-heading" className="text-sm font-medium text-neutral-500">
        Underlying momentum
      </h2>
      <div className="mt-3">
        <Badge label={inflationStateLabel(momentum.state)} tone={inflationStateTone(momentum.state)} size="xl" />
      </div>
      <p className="mt-2 text-sm text-neutral-500">
        Core PCE{momentum.calculation_period ? ` · ${formatPeriod(momentum.calculation_period)}` : ""}
      </p>

      <dl className="mt-6 flex flex-wrap gap-x-10 gap-y-3">
        {HERO_METRICS.map(({ key, label }) => (
          <div key={key}>
            <dt className="text-xs font-medium uppercase tracking-wide text-neutral-400">{label}</dt>
            <dd className="mt-0.5 text-lg font-semibold tabular-nums text-neutral-900">{formatPercent(momentum[key])}</dd>
          </div>
        ))}
      </dl>

      {momentum.missing_required_metrics.length > 0 && (
        <p className="mt-3 text-sm text-neutral-500">Missing required data: {momentum.missing_required_metrics.join(", ")}</p>
      )}
    </section>
  );
}
