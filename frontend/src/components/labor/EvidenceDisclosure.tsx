import { track } from "../../analytics";
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
 * `unitLabel` is caller-provided ("Jobs" for payroll employment,
 * "Percent" for the unemployment rate) rather than inferred here.
 * #56B correction: employment evidence arrives ALREADY in jobs --
 * `app.domain.labor` applies the x1000 once, before evidence is built
 * -- so it was never "thousands of persons", whatever this comment and
 * the label used to say. A real 159,075,000 was being labelled as
 * thousands.
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
    return <p className="text-sm text-fg-muted">No evidence available.</p>;
  }

  return (
    <Disclosure
      summary={`View evidence: ${label}`}
      // See the inflation counterpart: same question, different object
      // kind. Only the kind is recorded.
      onOpen={() => track("evidence_expanded", { object_type: "labor_observation" })}
    >
      <table className="w-full text-left text-sm text-fg-secondary">
        <thead>
          <tr className="text-xs text-fg-muted">
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
      <dl className="mt-3 grid grid-cols-1 sm:grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm text-fg-secondary">
        <dt className="text-fg-muted">Series</dt>
        <dd>{observations[0]?.series_id}</dd>
        <dt className="text-fg-muted">Methodology</dt>
        <dd>{methodologyId}</dd>
        <dt className="text-fg-muted">Data basis</dt>
        <dd>{dataBasis}</dd>
      </dl>
    </Disclosure>
  );
}
