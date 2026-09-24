import type { InflationMonitorResult, InflationWhatChangedResult } from "../../api/inflation.types";
import { Disclosure } from "../../components/Disclosure";
import { formatPeriod } from "../../lib/format";

/**
 * The page-level evidence/methodology surface: methodology and
 * comparison-contract IDs, data basis, and canonical monitor periods --
 * shown unobtrusively behind a disclosure, not on the default screen.
 * Per-metric evidence (series/observations/values) lives beside each
 * metric instead (see EvidenceDisclosure); this section is the
 * page-wide summary of what governed the whole page.
 */
export function MethodologyDisclosure({
  monitor,
  whatChanged,
}: {
  monitor: InflationMonitorResult | null;
  whatChanged: InflationWhatChangedResult | null;
}) {
  return (
    <section aria-labelledby="evidence-methodology-heading">
      <h2 id="evidence-methodology-heading" className="text-sm font-medium text-fg-muted">
        Evidence &amp; methodology
      </h2>
      <div className="mt-3">
        <Disclosure summaryClassName="min-h-11" summary="Methodology and coverage detail">
          <dl className="grid grid-cols-1 sm:grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm text-fg-secondary">
            {monitor && (
              <>
                <dt className="text-fg-muted">Monitor methodology</dt>
                <dd>{monitor.methodology_id}</dd>
                <dt className="text-fg-muted">Data basis</dt>
                <dd>{monitor.data_basis}</dd>
                <dt className="text-fg-muted">Latest common period</dt>
                <dd>{formatPeriod(monitor.periods.latest_common_period)}</dd>
                <dt className="text-fg-muted">Data through</dt>
                <dd>{formatPeriod(monitor.periods.data_through)}</dd>
              </>
            )}
            {whatChanged && (
              <>
                <dt className="text-fg-muted">Comparison methodology</dt>
                <dd>{whatChanged.comparison_contract_id}</dd>
                <dt className="text-fg-muted">Comparison type</dt>
                <dd>{whatChanged.comparison_type}</dd>
              </>
            )}
          </dl>
        </Disclosure>
      </div>
    </section>
  );
}
