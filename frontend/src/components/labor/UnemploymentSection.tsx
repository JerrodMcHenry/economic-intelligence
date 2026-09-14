import type { UnemploymentResult } from "../../api/labor.types";
import { UNEMPLOYMENT } from "../../content/explanations/labor";
import { formatPercent, formatPercentagePoints } from "../../lib/format";
import { unemploymentStateLabel, unemploymentStateTone } from "../../lib/laborLabels";
import { ExplanationTrigger } from "../explanations/ExplanationTrigger";
import { Badge } from "../inflation/Badge";
import { EvidenceDisclosure } from "./EvidenceDisclosure";

/**
 * The Unemployment section -- UNRATE's own half of `labor_v1.0`.
 * `UnemploymentTrendState` is the primary (and only) result for this
 * owner -- there is no condition/momentum split here (see
 * docs/architecture/labor-ui-v1.md §10). `current_3m_avg`/
 * `prior_year_3m_avg` are genuine rate percentages (`formatPercent`);
 * `delta_pp` is a signed percentage-point delta
 * (`formatPercentagePoints`) -- never `formatJobs`, which is
 * Employment-only.
 */
export function UnemploymentSection({ unemployment, methodologyId, dataBasis }: { unemployment: UnemploymentResult; methodologyId: string; dataBasis: string }) {
  return (
    <section aria-labelledby="unemployment-heading">
      <div className="flex items-center gap-1.5">
        <h2 id="unemployment-heading" className="text-sm font-medium text-neutral-500">
          Unemployment
        </h2>
        <ExplanationTrigger explanation={UNEMPLOYMENT} />
      </div>

      <div className="mt-3">
        <Badge label={unemploymentStateLabel(unemployment.state)} tone={unemploymentStateTone(unemployment.state)} size="lg" />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-lg border border-neutral-200 bg-white p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-neutral-400">Current 3M avg</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums text-neutral-900">{formatPercent(unemployment.current_3m_avg)}</p>
        </div>
        <div className="rounded-lg border border-neutral-200 bg-white p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-neutral-400">Prior-year 3M avg</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums text-neutral-900">{formatPercent(unemployment.prior_year_3m_avg)}</p>
        </div>
        <div className="rounded-lg border border-neutral-200 bg-white p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-neutral-400">Delta</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums text-neutral-900">{formatPercentagePoints(unemployment.delta_pp)}</p>
        </div>
      </div>

      <p className="mt-3 max-w-prose text-sm text-neutral-500">
        Labor combines this unemployment trend with the Employment section above into one overall Labor state.
      </p>

      {unemployment.observations.length > 0 && (
        <p className="mt-2 text-xs text-neutral-400">
          Evaluated using {unemployment.observations.length} required monthly observations.
        </p>
      )}

      <div className="mt-3">
        <EvidenceDisclosure
          label="Unemployment"
          unitLabel="Percent"
          observations={unemployment.observations}
          methodologyId={methodologyId}
          dataBasis={dataBasis}
        />
      </div>
    </section>
  );
}
