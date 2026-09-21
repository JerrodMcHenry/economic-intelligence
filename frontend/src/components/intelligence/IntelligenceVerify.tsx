import { track } from "../../analytics";
import type { IntelligenceObject } from "../../api/intelligence.types";
import { basisLabel, knowledgeLabel } from "../../lib/intelligenceLanguage";
import { Disclosure } from "../Disclosure";

/**
 * VERIFY (Increment #40).
 *
 * Progressive disclosure, never a dumped API response. A reader who
 * does not open this should still have understood the page; a reader
 * who does should be able to check every claim on it.
 *
 * Everything here is rendered FROM the #39 object. Nothing is
 * recomputed, and `published_at` is shown as genuinely unknown rather
 * than substituted.
 */
export function IntelligenceVerify({ object }: { object: IntelligenceObject }) {
  return (
    <section aria-labelledby="verify-heading" className="mt-10 border-t border-line pt-6">
      <h2 id="verify-heading" className="type-section-heading">
        Check this
      </h2>
      <p className="mt-1 text-sm text-fg-muted">Every figure above comes from the record below.</p>

      <div className="mt-4 space-y-3">
        <Disclosure
          summary={`Evidence (${object.evidence.length})`}
          onOpen={() => track("evidence_expanded", { object_type: object.type })}
        >
          {object.evidence.length === 0 ? (
            <p className="text-sm text-fg-muted">
              This object records that something happened rather than a measured value, so it carries no
              observation-level evidence of its own.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-fg-secondary">
                <caption className="sr-only">Observations this conclusion was computed from</caption>
                <thead>
                  <tr className="text-xs text-fg-muted">
                    <th scope="col" className="pr-4 font-medium">What it measures</th>
                    <th scope="col" className="pr-4 font-medium">Source</th>
                    <th scope="col" className="pr-4 font-medium">Their series</th>
                    <th scope="col" className="pr-4 font-medium">Period</th>
                    <th scope="col" className="font-medium">Value</th>
                  </tr>
                </thead>
                <tbody>
                  {object.evidence.map((reference) => (
                    <tr key={`${reference.concept_id}-${reference.observation_date}`} className="align-top">
                      <td className="pr-4 py-1">{reference.concept_id}</td>
                      <td className="pr-4 py-1">{reference.provider}</td>
                      <td className="pr-4 py-1">{reference.provider_series_id}</td>
                      <td className="pr-4 py-1">
                        <time dateTime={reference.observation_date}>{reference.observation_date}</time>
                      </td>
                      <td className="py-1 type-numeric">{reference.value ?? "not reported"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Disclosure>

        <Disclosure summary="How MacroChipz knows this">
          <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm text-fg-secondary">
            <dt className="text-fg-muted">Where it comes from</dt>
            <dd>{basisLabel(object)}</dd>

            <dt className="text-fg-muted">How it was recorded</dt>
            <dd>{knowledgeLabel(object)}</dd>

            <dt className="text-fg-muted">MacroChipz recorded it</dt>
            <dd>
              <time dateTime={object.recorded_at}>{object.recorded_at.replace("T", " ").slice(0, 19)} UTC</time>
            </dd>

            <dt className="text-fg-muted">Source published it</dt>
            <dd>
              {object.published_at === null ? (
                <span className="text-fg-muted">Not known — the source does not publish an exact time</span>
              ) : (
                <time dateTime={object.published_at}>{object.published_at}</time>
              )}
            </dd>

            {object.methodology !== null && (
              <>
                <dt className="text-fg-muted">Methodology</dt>
                <dd>
                  {object.methodology.methodology_id} ({object.methodology.data_basis})
                </dd>
              </>
            )}

            <dt className="text-fg-muted">Permanent id</dt>
            <dd className="break-all">{object.id}</dd>
          </dl>
        </Disclosure>

        <Disclosure summary={`What this does not tell you (${object.limitations.length})`}>
          <ul className="list-disc space-y-1 pl-5 text-sm text-fg-secondary">
            {object.limitations.map((limitation) => (
              <li key={limitation}>{limitation}</li>
            ))}
          </ul>
        </Disclosure>
      </div>
    </section>
  );
}
