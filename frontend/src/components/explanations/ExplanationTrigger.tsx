import { track } from "../../analytics";
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
    <details
      className="group inline-block align-middle"
      // Increment #37: unlike the generic `Disclosure`, this component
      // has exactly one meaning wherever it appears -- a reader
      // stopping to look up a term -- so the event lives here rather
      // than at its sixteen call sites. `explanation.id` is a curated
      // identifier from `src/content/explanations/`, authored by us and
      // never user input.
      onToggle={(event) => {
        if (event.currentTarget.open) track("explainer_opened", { explainer_id: explanation.id });
      }}
    >
      <summary
        aria-label={`What does ${explanation.title} mean?`}
        className="inline-flex h-4 w-4 cursor-pointer select-none list-none items-center justify-center rounded-full text-[0.65rem] font-semibold leading-none text-fg-muted ring-1 ring-inset ring-line-strong hover:text-fg-secondary hover:ring-fg-muted group-open:bg-surface-secondary group-open:text-fg-secondary [&::-webkit-details-marker]:hidden"
      >
        i
      </summary>
      <div className="mt-2 max-w-sm rounded-md border border-line bg-surface p-3 text-sm">
        <p className="font-semibold text-fg">{explanation.title}</p>
        <p className="mt-1 text-fg-secondary">{explanation.definition}</p>
        {explanation.whyItMatters && (
          <p className="mt-2 text-fg-secondary">
            <span className="font-medium text-fg-muted">Why it matters: </span>
            {explanation.whyItMatters}
          </p>
        )}
        {explanation.sourceNote && <p className="mt-2 text-xs text-fg-muted">{explanation.sourceNote}</p>}
      </div>
    </details>
  );
}
