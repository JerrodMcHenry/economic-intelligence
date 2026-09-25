/**
 * The one mandatory, page-wide release-calendar disclosure -- centralized
 * here (Increment #19A) so `/releases` and the Economic Overview render
 * the exact same sentence rather than two independently-typed copies
 * that could drift. Byte-for-byte unchanged from the sentence #17B
 * originally hardcoded inline in `pages/Releases.tsx`; this is a
 * presentation-only extraction, never a wording change (see
 * docs/architecture/release-intelligence-v1.md #2/#13 for why this
 * sentence's meaning -- a scheduled date is not proof of data
 * availability -- is load-bearing, not stylistic).
 *
 * #45B ADDED A SECOND PARAGRAPH BESIDE IT, naming the schedule's
 * source. The frozen sentence is untouched and still renders as its
 * own element, so an exact-text assertion against it still passes --
 * that was deliberate, not incidental. This is the other half of
 * removing the bare "FRED" token from every calendar row (#45A section
 * A.10.1): a provider identifier is consumer-facing jargon in a row,
 * but it is real provenance, so it moves here rather than being
 * deleted -- stated where a reader can actually parse it.
 */
export function ReleaseScheduleDisclosure() {
  return (
    <>
      {/* The frozen sentence, byte-for-byte. Not edited, not merged
          with the provenance line below -- #17B hardcoded it and
          release-intelligence-v1.md #2/#13 makes its meaning
          load-bearing, so #45B adds beside it rather than to it. */}
      <p className="max-w-prose text-xs text-fg-muted">
        Release dates indicate scheduled publication dates. They do not confirm that new data has been published,
        ingested, or reflected in Economic Intelligence analysis.
      </p>
      <p className="mt-1 max-w-prose text-xs text-fg-muted">
        Schedules are the publishers' own: the U.S. Bureau of Labor Statistics and the U.S. Bureau of Economic Analysis.
      </p>
    </>
  );
}
