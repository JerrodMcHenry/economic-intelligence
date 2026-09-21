import { Disclosure } from "../Disclosure";
import type { DerivedProvenance, SourceProvenance } from "../../api/rates.types";
import { formatObservationDate, formatRetrievedAt } from "../../lib/ratesFormat";

/**
 * Two deliberately different provenance surfaces (Increment #30).
 *
 * The product's core claim is that a sourced observation and a derived
 * value are different kinds of fact, so they are never rendered through
 * one shared component: a source panel names a provider, a dataset and a
 * retrieval; a derived panel names a methodology, a calculation and its
 * inputs — and never a provider, because Treasury did not publish it.
 *
 * Both render exactly what the backend returned. Nothing is recomputed.
 */

export function SourceProvenanceDisclosure({ provenance }: { provenance: SourceProvenance | null }) {
  if (provenance === null) {
    return <p className="type-meta text-fg-muted">No provenance recorded for this observation.</p>;
  }

  return (
    <Disclosure summary="Source &amp; provenance">
      <dl className="grid grid-cols-1 sm:grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm text-fg-secondary">
        <dt className="text-fg-muted">Value type</dt>
        <dd>Published by the source</dd>
        <dt className="text-fg-muted">Provider</dt>
        <dd>{provenance.provider}</dd>
        <dt className="text-fg-muted">Dataset</dt>
        <dd className="break-words">{provenance.dataset}</dd>
        <dt className="text-fg-muted">Series</dt>
        <dd>{provenance.series_id}</dd>
        <dt className="text-fg-muted">Observation date</dt>
        <dd>{formatObservationDate(provenance.observation_date)}</dd>
        <dt className="text-fg-muted">Retrieved</dt>
        <dd>{formatRetrievedAt(provenance.retrieved_at)}</dd>
        <dt className="text-fg-muted">Revisions</dt>
        <dd>
          {provenance.revision_count === 0
            ? "None since first ingested"
            : `${provenance.revision_count} (latest ${formatRetrievedAt(provenance.last_revised_at)})`}
        </dd>
        <dt className="text-fg-muted">Source reference</dt>
        <dd className="break-all">
          <a
            href={provenance.source_url}
            className="text-brand underline underline-offset-2 hover:text-brand-hover"
            target="_blank"
            rel="noreferrer noopener"
          >
            {provenance.source_url}
          </a>
        </dd>
      </dl>
    </Disclosure>
  );
}

export function DerivedProvenanceDisclosure({ provenance }: { provenance: DerivedProvenance | null }) {
  if (provenance === null) {
    return null;
  }

  return (
    <Disclosure summary="How this is calculated">
      <dl className="grid grid-cols-1 sm:grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm text-fg-secondary">
        <dt className="text-fg-muted">Value type</dt>
        <dd>Calculated by MacroChipz, not published by the source</dd>
        <dt className="text-fg-muted">Methodology</dt>
        <dd>{provenance.methodology_id}</dd>
        <dt className="text-fg-muted">Calculation</dt>
        <dd>{provenance.calculation}</dd>
        <dt className="text-fg-muted">Input series</dt>
        <dd>{provenance.input_series_ids.join(", ")}</dd>
        <dt className="text-fg-muted">Input observation date</dt>
        <dd>{formatObservationDate(provenance.input_observation_date)}</dd>
      </dl>
    </Disclosure>
  );
}
