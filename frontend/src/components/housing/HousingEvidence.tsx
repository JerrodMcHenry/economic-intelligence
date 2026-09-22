import type { HousingResult } from "../../api/housing.types";
import { Disclosure } from "../Disclosure";
import { formatPeriod } from "../../lib/format";
import { formatObservationDate } from "../../lib/ratesFormat";

/**
 * Evidence and limitations for the Housing world (Increment #45).
 *
 * The VERIFY half of See → Understand → Verify. Everything rendered
 * here comes from the response: the provenance of the latest
 * observation of each measure, the limitations the backend attached,
 * and Census's required attribution.
 *
 * TWO THINGS THIS PANEL DOES THAT THE OTHER WORLDS' DO NOT
 * --------------------------------------------------------
 * 1. **There is no methodology row**, because there is no methodology.
 *    Rates shows `rates_v1.0`; Housing shows the data basis and stops.
 *    A "Methodology: —" row would imply one is coming; its absence says
 *    what is true.
 * 2. **The attribution is rendered from the response**, verbatim, not
 *    from a constant in this file. Census's terms require that exact
 *    sentence, and a frontend string can drift out of sync with the
 *    data it governs.
 */
export function HousingEvidence({ result }: { result: HousingResult }) {
  const provenances = result.stages
    .flatMap((stage) => [stage.pace, stage.actual])
    .filter((measure) => measure.provenance !== null);

  return (
    <Disclosure summary="Where these numbers come from">
      <div className="space-y-3 text-sm text-fg-secondary">
        <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1">
          <dt className="text-fg-muted">Source</dt>
          <dd>{result.source_statement}</dd>
          <dt className="text-fg-muted">Data basis</dt>
          <dd>{result.data_basis}</dd>
          <dt className="text-fg-muted">Latest period</dt>
          <dd>{formatPeriod(result.as_of_period)}</dd>
          <dt className="text-fg-muted">Published at</dt>
          <dd>
            <a
              href={result.source_url}
              className="underline underline-offset-4 hover:text-fg"
              rel="noreferrer"
              target="_blank"
            >
              census.gov/construction/nrc
            </a>
          </dd>
        </dl>

        {provenances.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <caption className="sr-only">
                Retrieval provenance for the latest observation of each Housing measure
              </caption>
              <thead>
                <tr className="type-label text-fg-muted">
                  <th scope="col" className="pb-1 pr-4 font-semibold">
                    MacroChipz concept
                  </th>
                  <th scope="col" className="pb-1 pr-4 font-semibold">
                    Census series
                  </th>
                  <th scope="col" className="pb-1 pr-4 font-semibold">
                    Observation
                  </th>
                  <th scope="col" className="pb-1 font-semibold">
                    Retrieved
                  </th>
                </tr>
              </thead>
              <tbody>
                {provenances.map((measure) => (
                  <tr key={measure.concept_id} className="align-top">
                    {/* The source-neutral concept id (#38) beside the
                        provider's own identifier -- which is the whole
                        point of keeping them apart. */}
                    <td className="py-0.5 pr-4 font-mono text-xs">{measure.concept_id}</td>
                    <td className="py-0.5 pr-4 font-mono text-xs">
                      {measure.provenance?.provider_series_id}
                    </td>
                    <td className="py-0.5 pr-4">{formatPeriod(measure.provenance?.observation_date ?? null)}</td>
                    <td className="py-0.5">{formatObservationDate(measure.provenance?.retrieved_at?.slice(0, 10) ?? null)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div>
          <p className="font-medium text-fg">What this does not establish</p>
          <ul className="mt-1.5 list-disc space-y-1.5 pl-5">
            {result.limitations.map((limitation) => (
              <li key={limitation}>{limitation}</li>
            ))}
          </ul>
        </div>

        {/* Required verbatim by the Census Data API terms of service.
            Rendered from the response, never paraphrased, never
            abbreviated. */}
        <p className="type-meta text-fg-muted">{result.attribution}</p>
      </div>
    </Disclosure>
  );
}
