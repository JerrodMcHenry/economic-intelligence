import type { ReactNode } from "react";

/**
 * Generic, keyboard-accessible progressive-disclosure primitive built on
 * native `<details>/<summary>` -- no custom focus management needed, and
 * it degrades to plain content if JavaScript never runs. Used both for
 * "Latest revised data" and for evidence panels; carries no economic
 * meaning of its own.
 */
export function Disclosure({ summary, children }: { summary: ReactNode; children: ReactNode }) {
  return (
    <details className="group">
      <summary className="flex cursor-pointer select-none list-none items-center gap-1.5 text-sm font-medium text-fg-secondary hover:text-fg [&::-webkit-details-marker]:hidden">
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
