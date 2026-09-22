import { useCallback, useState } from "react";

import { track, type ObjectType } from "../analytics";

/**
 * One share control (Increment #40).
 *
 * Deliberately one button, not a row of network logos. It prefers the
 * platform's own share sheet and falls back to copying the permanent
 * URL, so there is no third-party SDK anywhere in the path and nothing
 * to consent to.
 *
 * Three rules this component keeps:
 *
 * 1. **Sharing never depends on analytics.** `track()` is fire-and-
 *    forget and cannot throw (#37), but the call is also placed so that
 *    even a hard failure inside it could not prevent the share. Tested.
 * 2. **No tracking parameters.** The URL shared is the permanent URL,
 *    unmodified. Nothing is appended.
 * 3. **Nothing private is measured.** The event records the object type
 *    only -- never the URL, the share text, the clipboard, or which
 *    app the reader chose.
 */
export function ShareButton({
  objectType,
  title,
  url,
}: {
  /** The closed analytics vocabulary's object type (#37). Widened from
   * `IntelligenceType` in #45B so permanent EXPLAINERS can share too --
   * they are the most shareable pages in the product and were the only
   * ones without the affordance. */
  objectType: ObjectType;
  title: string;
  /** The permanent URL. Passed in rather than read from `location` so
   * the component is testable and so prerendering cannot bake in a
   * build-time host. */
  url: string;
}) {
  const [copied, setCopied] = useState(false);

  const share = useCallback(async () => {
    // Measured first, and deliberately outside the try: this records
    // that the reader INTENDED to share, which is the product question.
    // Whether the OS sheet was then dismissed is not ours to know.
    track("share_initiated", { object_type: objectType });

    const nav = typeof navigator === "undefined" ? undefined : navigator;
    if (nav?.share) {
      try {
        await nav.share({ title, url });
        return;
      } catch {
        // Dismissed, or unavailable despite being present. Fall through
        // to copy rather than leaving the reader with nothing.
      }
    }

    try {
      await nav?.clipboard?.writeText(url);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2_000);
    } catch {
      // Clipboard denied. The URL is in the address bar and is visible
      // on the page, so there is nothing further to do and nothing
      // worth interrupting the reader about.
    }
  }, [objectType, title, url]);

  return (
    <div className="flex items-center gap-3">
      <button
        type="button"
        onClick={() => void share()}
        className="inline-flex min-h-11 items-center gap-2 rounded-md border border-line px-4 py-2 text-sm font-medium text-fg-secondary transition-colors hover:bg-surface-secondary hover:text-fg motion-reduce:transition-none"
      >
        <svg viewBox="0 0 16 16" aria-hidden="true" className="h-4 w-4">
          <path
            d="M8 10V2m0 0L5 5m3-3l3 3M3 9v3.5A1.5 1.5 0 004.5 14h7a1.5 1.5 0 001.5-1.5V9"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        Share
      </button>
      {/* Announced to screen readers, not signalled by colour alone. */}
      <span aria-live="polite" className="text-sm text-fg-muted">
        {copied ? "Link copied" : ""}
      </span>
    </div>
  );
}
