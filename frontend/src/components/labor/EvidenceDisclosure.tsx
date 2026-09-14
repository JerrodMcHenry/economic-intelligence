import type { LaborObservationEvidence } from "../../api/labor.types";
import { Disclosure } from "../../components/Disclosure";
import { formatPeriod } from "../../lib/format";
import { formatRawObservationValue } from "../../lib/laborFormat";

/**
 * Renders a canonical `LaborObservationEvidence[]` list verbatim (the
 * exact required calendar months, and exactly what the backend
 * persisted for each -- `null` for a genuinely missing month, never
 * omitted). Purely presentational -- nothing here is recalculated or
 * re-derived.
 *
 * `unitLabel` is caller-provided (e.g. "Thousands of persons" for
 * PAYEMS, "Percent" for UNRATE) rather than inferred here -- these raw
 * values are FRED-native, NOT the already-converted actual-jobs unit
 * the summary metrics use (docs/architecture/labor-ui-v1.md §15,
 * load-bearing) -- explicit labeling is what prevents a reader from
 * assuming a raw `130,472` here means the same thing as an
 * already-converted `-331,333` in the summary tier above it.
 */
export function EvidenceDisclosure({
  label,
  unitLabel,
  observations,
  methodologyId,
  dataBasis,
}: {
  label: string;
  unitLabel: string;
  observations: LaborObservationEvidence[];
  methodologyId: string;
  dataBasis: string;
}) {
  if (observations.length === 0) {
    return <p className="text-sm text-neutral-400">No evidence available.</p>;
  }

  return (
    <Disclosure summary={`View evidence: ${label}`}>
      <table className="w-full text-left text-sm text-neutral-600">
        <thead>
          <tr className="text-xs text-neutral-400">
            <th scope="col" className="pr-4 font-medium">
              Period
            </th>
            <th scope="col" className="font-medium">
              Value ({unitLabel})
            </th>
          </tr>
        </thead>
        <tbody>
          {observations.map((observation) => (
            <tr key={observation.observation_date}>
              <td className="pr-4">{formatPeriod(observation.observation_date)}</td>
              <td className="tabular-nums">{formatRawObservationValue(observation.value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <dl className="mt-3 grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm text-neutral-600">
        <dt className="text-neutral-400">Series</dt>
        <dd>{observations[0]?.series_id}</dd>
        <dt className="text-neutral-400">Methodology</dt>
        <dd>{methodologyId}</dd>
        <dt className="text-neutral-400">Data basis</dt>
        <dd>{dataBasis}</dd>
      </dl>
    </Disclosure>
  );
}
