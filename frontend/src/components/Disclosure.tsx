import type { ReactNode } from "react";

/**
 * Generic, keyboard-accessible progressive-disclosure primitive built on
 * native `<details>/<summary>` -- no custom focus management needed, and
 * it degrades to plain content if JavaScript never runs. Used both for
 * "Latest revised data" and for evidence panels; carries no economic
 * meaning of its own.
 */
export function Disclosure({
  summary,
  children,
  onOpen,
  summaryClassName = "",
}: {
  summary: ReactNode;
  children: ReactNode;
  /**
   * Called when the reader OPENS this disclosure (not when they close
   * it). Optional, and deliberately meaningless to this component:
   * `Disclosure` is used for evidence, methodology, data-basis notes
   * and change lists alike, so only the call site knows which of those
   * a given instance is. Keeping the semantics at the call site is
   * what lets one primitive serve several different product events --
   * see Increment #37's event vocabulary.
   */
  onOpen?: () => void;
  /**
   * Extra classes for the `<summary>` (#46C).
   *
   * Added because the summary row is 20px tall, which is a fine reading
   * affordance and a poor TAP target — measured at a genuine 390px
   * viewport, it is less than half the 44px a thumb needs. Rather than
   * change every existing call site at once, call sites that have been
   * checked on a phone opt in.
   *
   * Deliberately additive: the default is the exact markup every
   * existing caller already renders.
   */
  summaryClassName?: string;
}) {
  return (
    <details
      className="group"
      onToggle={(event) => {
        if (event.currentTarget.open) onOpen?.();
      }}
    >
      <summary
        className={`flex cursor-pointer select-none list-none items-center gap-1.5 text-sm font-medium text-fg-secondary hover:text-fg [&::-webkit-details-marker]:hidden ${summaryClassName}`}
      >
        <svg
          viewBox="0 0 16 16"
          aria-hidden="true"
          className="h-3 w-3 flex-none text-fg-muted transition-transform group-open:rotate-90 motion-reduce:transition-none"
        >
          <path d="M6 3l5 5-5 5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        {summary}
      </summary>
      <div className="mt-2 pl-[18px]">{children}</div>
    </details>
  );
}
