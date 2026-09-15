import { Disclosure } from "../../components/Disclosure";
import { LATEST_REVISED_DATA, STATE_DURATION_DISCLOSURE } from "../../content/explanations/inflation";

/**
 * Discloses the page's data vintage without implying point-in-time
 * accuracy: every calculation uses the latest revised observations
 * currently available, not what was originally reported at the time.
 * Sourced from the shared `LATEST_REVISED_DATA` explanation (Increment
 * #17C) rather than hardcoding the sentence a second time -- its
 * `definition` field carries this exact, unmodified canonical
 * sentence; `whyItMatters` adds the beginner context for why revisions
 * happen at all.
 *
 * Increment #24D adds one further, additional sentence
 * (`STATE_DURATION_DISCLOSURE`, frozen verbatim in
 * docs/product/state-duration-v1.md §38) alongside the existing two --
 * never replacing them -- covering the one distinction the existing
 * sentence doesn't: State Duration is a reconstruction computed today,
 * not what Economic Intelligence reported in real time as each month
 * occurred. Always rendered (this disclosure has no per-response data
 * dependency, so it never needs its own loading/error state).
 */
export function DataBasisNote() {
  return (
    <Disclosure summary="Latest revised data">
      <p className="max-w-prose text-sm text-neutral-500">{LATEST_REVISED_DATA.definition}</p>
      <p className="mt-2 max-w-prose text-sm text-neutral-500">{LATEST_REVISED_DATA.whyItMatters}</p>
      <p className="mt-2 max-w-prose text-sm text-neutral-500">{STATE_DURATION_DISCLOSURE.definition}</p>
    </Disclosure>
  );
}
