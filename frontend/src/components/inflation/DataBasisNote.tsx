import { Disclosure } from "../../components/Disclosure";
import { LATEST_REVISED_DATA } from "../../content/explanations/inflation";

/**
 * Discloses the page's data vintage without implying point-in-time
 * accuracy: every calculation uses the latest revised observations
 * currently available, not what was originally reported at the time.
 * Sourced from the shared `LATEST_REVISED_DATA` explanation (Increment
 * #17C) rather than hardcoding the sentence a second time -- its
 * `definition` field carries this exact, unmodified canonical
 * sentence; `whyItMatters` adds the beginner context for why revisions
 * happen at all.
 */
export function DataBasisNote() {
  return (
    <Disclosure summary="Latest revised data">
      <p className="max-w-prose text-sm text-neutral-500">{LATEST_REVISED_DATA.definition}</p>
      <p className="mt-2 max-w-prose text-sm text-neutral-500">{LATEST_REVISED_DATA.whyItMatters}</p>
    </Disclosure>
  );
}
