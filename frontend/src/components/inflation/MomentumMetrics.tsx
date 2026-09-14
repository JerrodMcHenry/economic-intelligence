import type { SeriesMomentumResult } from "../../api/inflation.types";
import { SIX_MONTH_ANNUALIZED, THREE_MONTH_ANNUALIZED, TWELVE_MONTH } from "../../content/explanations/inflation";
import { formatPercent, formatPeriod } from "../../lib/format";
import { ExplanationTrigger } from "../explanations/ExplanationTrigger";
import { EvidenceDisclosure } from "./EvidenceDisclosure";

const METRICS = [
  { key: "r_3m_annualized", evidenceKey: "evidence_3m", label: "3M annualized", explanation: THREE_MONTH_ANNUALIZED },
  { key: "r_6m_annualized", evidenceKey: "evidence_6m", label: "6M annualized", explanation: SIX_MONTH_ANNUALIZED },
  { key: "r_12m", evidenceKey: "evidence_12m", label: "12M", explanation: TWELVE_MONTH },
] as const;

/**
 * The three headline Core PCE readings the frozen methodology
 * classifies on (3M/6M/12M). 1M is shown once, separately, as secondary
 * context only, matching its role in the methodology. Every value,
 * period, and evidence record here is exactly what the backend
 * returned -- no client-side annualization or rounding-for-comparison.
 */
export function MomentumMetrics({ momentum }: { momentum: SeriesMomentumResult }) {
  const hasBand = momentum.lower_boundary !== null && momentum.upper_boundary !== null;

  return (
    <section aria-labelledby="momentum-metrics-heading">
      <h2 id="momentum-metrics-heading" className="text-sm font-medium text-neutral-500">
        Core PCE momentum
      </h2>
      <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-3">
        {METRICS.map(({ key, evidenceKey, label, explanation }) => (
          <div key={key} className="rounded-lg border border-neutral-200 bg-white p-4">
            <div className="flex items-center gap-1.5">
              <p className="text-xs font-medium uppercase tracking-wide text-neutral-400">{label}</p>
              <ExplanationTrigger explanation={explanation} />
            </div>
            <p className="mt-1 text-2xl font-semibold tabular-nums text-neutral-900">{formatPercent(momentum[key])}</p>
            <p className="mt-1 text-xs text-neutral-500">{formatPeriod(momentum.calculation_period)}</p>
            {key === "r_12m" && hasBand && (
              <p className="mt-1 text-xs text-neutral-400">
                Neutral band: {formatPercent(momentum.lower_boundary)} to {formatPercent(momentum.upper_boundary)} (
                {momentum.neutral_band_pp} pp)
              </p>
            )}
            <div className="mt-3">
              <EvidenceDisclosure label={label} evidence={momentum[evidenceKey]} />
            </div>
          </div>
        ))}
      </div>
      {momentum.r_1m_annualized !== null && (
        <p className="mt-3 text-sm text-neutral-500">1M annualized (context only): {formatPercent(momentum.r_1m_annualized)}</p>
      )}
    </section>
  );
}
