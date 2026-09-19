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
 */
export function ReleaseScheduleDisclosure() {
  return (
    <p className="max-w-prose text-xs text-fg-muted">
      Release dates indicate scheduled publication dates. They do not confirm that new data has been published,
      ingested, or reflected in Economic Intelligence analysis.
    </p>
  );
}
