import type { Explanation } from "../../content/explanations/types";

/**
 * A small, reusable "ⓘ" explanation affordance -- native
 * `<details>/<summary>`, the same accessible, no-framework foundation
 * `components/Disclosure.tsx` already uses, styled compactly for
 * inline placement next to a value or label rather than Disclosure's
 * block-level, left-aligned treatment. Click or keyboard (Enter/Space,
 * both native to `<summary>`) toggles it; nothing here depends on
 * hover, and `aria-expanded` is exposed to assistive tech
 * automatically by the browser's own `<details>` semantics -- this
 * component never manages that state itself. Content expands in
 * normal document flow (never an absolutely-positioned popover), so it
 * can never cause horizontal overflow the way a floating panel could
 * on a narrow screen.
 *
 * Reused identically across Inflation and Releases -- see
 * components/inflation/WhyThisState.tsx for the one place a *result*
 * explanation (backend evidence + a state's curated meaning) is
 * composed instead of this generic concept trigger.
 */
export function ExplanationTrigger({ explanation }: { explanation: Explanation }) {
  return (
    <details className="group inline-block align-middle">
      <summary
        aria-label={`What does ${explanation.title} mean?`}
        className="inline-flex h-4 w-4 cursor-pointer select-none list-none items-center justify-center rounded-full text-[0.65rem] font-semibold leading-none text-neutral-400 ring-1 ring-inset ring-neutral-300 hover:text-neutral-600 hover:ring-neutral-400 group-open:bg-neutral-100 group-open:text-neutral-700 [&::-webkit-details-marker]:hidden"
      >
        i
      </summary>
      <div className="mt-2 max-w-sm rounded-md border border-neutral-200 bg-white p-3 text-sm">
        <p className="font-semibold text-neutral-900">{explanation.title}</p>
        <p className="mt-1 text-neutral-700">{explanation.definition}</p>
        {explanation.whyItMatters && (
          <p className="mt-2 text-neutral-600">
            <span className="font-medium text-neutral-500">Why it matters: </span>
            {explanation.whyItMatters}
          </p>
        )}
        {explanation.sourceNote && <p className="mt-2 text-xs text-neutral-400">{explanation.sourceNote}</p>}
      </div>
    </details>
  );
}
