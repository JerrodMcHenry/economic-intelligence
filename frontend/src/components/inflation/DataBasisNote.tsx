import { Disclosure } from "../../components/Disclosure";

/**
 * Discloses the page's data vintage without implying point-in-time
 * accuracy: every calculation uses the latest revised observations
 * currently available, not what was originally reported at the time.
 */
export function DataBasisNote() {
  return (
    <Disclosure summary="Latest revised data">
      <p className="max-w-prose text-sm text-neutral-500">
        Historical calculations use the latest revised observations available to Economic Intelligence. They may
        differ from values originally reported at the time.
      </p>
    </Disclosure>
  );
}
