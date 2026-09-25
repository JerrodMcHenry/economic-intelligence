import type { EmploymentResult } from "../../api/labor.types";
import { EMPLOYMENT, employmentConditionExplanation, employmentMomentumExplanation } from "../../content/explanations/labor";
import { formatPeriod } from "../../lib/format";
import { formatJobs } from "../../lib/laborFormat";
import { employmentConditionLabel, employmentMomentumLabel, employmentStateLabel, employmentStateTone } from "../../lib/laborLabels";
import { ExplanationTrigger } from "../explanations/ExplanationTrigger";
import { Badge } from "../inflation/Badge";
import { EvidenceDisclosure } from "./EvidenceDisclosure";

const METRICS = [
  { key: "current_3m_avg_jobs", label: "Current 3M avg" },
  { key: "prior_3m_avg_jobs", label: "Prior 3M avg" },
  { key: "momentum_delta_jobs", label: "Momentum delta" },
] as const;

/**
 * The Employment section -- PAYEMS's own half of `labor_v1.0`.
 * `EmploymentState` is the single primary result (one badge); condition
 * and momentum are secondary, explanatory TEXT, never equal-weight
 * badges (docs/architecture/labor-ui-v1.md §9, a deliberate,
 * frozen hierarchy decision, not the three-co-equal-badges hypothesis
 * that was explicitly rejected). Every metric is already in actual
 * jobs (not thousands) -- `formatJobs` never converts (§15/§18).
 */
export function EmploymentSection({ employment, methodologyId, dataBasis }: { employment: EmploymentResult; methodologyId: string; dataBasis: string }) {
  return (
    <section aria-labelledby="employment-heading">
      <div className="flex items-center gap-1.5">
        <h2 id="employment-heading" className="text-sm font-medium text-fg-muted">
          Employment
        </h2>
        <ExplanationTrigger explanation={EMPLOYMENT} />
      </div>

      <div className="mt-3">
        <Badge label={employmentStateLabel(employment.state)} tone={employmentStateTone(employment.state)} size="lg" />
      </div>

      <dl className="mt-3 space-y-1 text-sm text-fg-secondary">
        <div className="flex items-center gap-1.5">
          <dt className="text-fg-muted">Current hiring condition:</dt>
          <dd>{employmentConditionLabel(employment.condition)}</dd>
          <ExplanationTrigger explanation={employmentConditionExplanation(employment.condition)} />
        </div>
        <div className="flex items-center gap-1.5">
          <dt className="text-fg-muted">Momentum:</dt>
          <dd>{employmentMomentumLabel(employment.momentum)}</dd>
          <ExplanationTrigger explanation={employmentMomentumExplanation(employment.momentum)} />
        </div>
      </dl>

      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
        {METRICS.map(({ key, label }) => (
          <div key={key} className="rounded-lg border border-line bg-surface p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-fg-muted">{label}</p>
            <p className="mt-1 text-2xl font-semibold tabular-nums text-fg">{formatJobs(employment[key])}</p>
            <p className="mt-1 text-xs text-fg-muted">jobs</p>
          </div>
        ))}
      </div>

      <div className="mt-3 text-xs text-fg-muted">
        {employment.observations.length > 0 && (
          <p>Evaluated using {employment.observations.length} required monthly observations{formatPeriodRange(employment)}.</p>
        )}
      </div>

      <div className="mt-3">
        <EvidenceDisclosure
          label="Employment"
          unitLabel="Jobs"
          observations={employment.observations}
          methodologyId={methodologyId}
          dataBasis={dataBasis}
        />
      </div>
    </section>
  );
}

function formatPeriodRange(employment: EmploymentResult): string {
  if (employment.observations.length === 0) return "";
  const dates = employment.observations.map((o) => o.observation_date).sort();
  const first = dates[0];
  const last = dates[dates.length - 1];
  if (first === undefined || last === undefined) return "";
  return ` (${formatPeriod(first)} – ${formatPeriod(last)})`;
}
