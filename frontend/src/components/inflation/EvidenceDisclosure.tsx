import { track } from "../../analytics";
import { Disclosure } from "../../components/Disclosure";
import type { InflationMetricEvidence } from "../../api/inflation.types";
import { formatPercent, formatPeriod } from "../../lib/format";

/**
 * Renders one canonical `InflationMetricEvidence` object verbatim
 * (series, period, transformation, the two endpoint observations it was
 * computed from, and the methodology/data-basis it was computed under).
 * Purely presentational -- every value shown here is exactly what the
 * backend returned; nothing is recalculated or re-derived.
 */
export function EvidenceDisclosure({ label, evidence }: { label: string; evidence: InflationMetricEvidence | null }) {
  if (evidence === null) {
    return <p className="text-sm text-fg-muted">No evidence available.</p>;
  }

  return (
    <Disclosure summaryClassName="min-h-11"
      summary={`View evidence: ${label}`}
      // Increment #37's headline measurement: does anyone actually
      // verify? Only the object kind is recorded -- never which metric,
      // never the values on screen.
      onOpen={() => track("evidence_expanded", { object_type: "inflation_metric" })}
    >
      <dl className="grid grid-cols-1 sm:grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm text-fg-secondary">
        <dt className="text-fg-muted">Series</dt>
        <dd>{evidence.series_id}</dd>
        <dt className="text-fg-muted">Calculation period</dt>
        <dd>{formatPeriod(evidence.calculation_period)}</dd>
        <dt className="text-fg-muted">Transformation</dt>
        <dd>{evidence.transformation}</dd>
        <dt className="text-fg-muted">Current observation</dt>
        <dd>
          {formatPeriod(evidence.endpoint_date_current)} &mdash;{" "}
          {evidence.endpoint_value_current === null ? "Unavailable" : evidence.endpoint_value_current}
        </dd>
        <dt className="text-fg-muted">Prior observation</dt>
        <dd>
          {formatPeriod(evidence.endpoint_date_past)} &mdash;{" "}
          {evidence.endpoint_value_past === null ? "Unavailable" : evidence.endpoint_value_past}
        </dd>
        <dt className="text-fg-muted">Value</dt>
        <dd>{formatPercent(evidence.value)}</dd>
        <dt className="text-fg-muted">Methodology</dt>
        <dd>{evidence.methodology_id}</dd>
        <dt className="text-fg-muted">Data basis</dt>
        <dd>{evidence.data_basis}</dd>
      </dl>
    </Disclosure>
  );
}
