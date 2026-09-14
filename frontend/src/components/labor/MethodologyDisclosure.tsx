import type { LaborMonitorResult, LaborWhatChangedResult } from "../../api/labor.types";
import { Disclosure } from "../../components/Disclosure";
import { formatPeriod } from "../../lib/format";

/**
 * The page-level evidence/methodology surface for /labor -- methodology
 * and comparison-contract IDs, data basis, and the canonical evaluation
 * period, shown unobtrusively behind a disclosure. Mirrors
 * components/inflation/MethodologyDisclosure.tsx exactly. Per-metric
 * evidence (series/observations/values) lives beside each metric
 * instead (see components/labor/EvidenceDisclosure.tsx); this section
 * is the page-wide summary of what governed the whole page.
 */
export function MethodologyDisclosure({
  monitor,
  whatChanged,
}: {
  monitor: LaborMonitorResult | null;
  whatChanged: LaborWhatChangedResult | null;
}) {
  return (
    <section aria-labelledby="labor-evidence-methodology-heading">
      <h2 id="labor-evidence-methodology-heading" className="text-sm font-medium text-neutral-500">
        Evidence &amp; methodology
      </h2>
      <div className="mt-3">
        <Disclosure summary="Methodology and coverage detail">
          <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm text-neutral-600">
            {monitor && (
              <>
                <dt className="text-neutral-400">Monitor methodology</dt>
                <dd>{monitor.methodology_id}</dd>
                <dt className="text-neutral-400">Data basis</dt>
                <dd>{monitor.data_basis}</dd>
                <dt className="text-neutral-400">Evaluation period</dt>
                <dd>{formatPeriod(monitor.evaluation_period)}</dd>
              </>
            )}
            {whatChanged && (
              <>
                <dt className="text-neutral-400">Comparison methodology</dt>
                <dd>{whatChanged.comparison_contract_id}</dd>
                <dt className="text-neutral-400">Comparison type</dt>
                <dd>{whatChanged.comparison_type}</dd>
              </>
            )}
          </dl>
        </Disclosure>
      </div>
    </section>
  );
}
