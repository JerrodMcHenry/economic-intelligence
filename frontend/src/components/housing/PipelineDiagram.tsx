import { STAGE_COPY } from "../../lib/housingFormat";

/**
 * Permits → Starts → Completions, made visible (Increment #45).
 *
 * ================================================================
 * THE SHAPE IS THE ARGUMENT, AND SO IS THE SENTENCE UNDER IT
 * ================================================================
 *
 * A reader needs the sequence: a home is authorised, then begun, then
 * finished. Three boxes and two arrows say that in a second.
 *
 * But the same three boxes and two arrows also say something false if
 * nothing stops them — that these are one batch of homes moving along a
 * conveyor, so a permit today is a completion on some predictable
 * schedule. They are not. They are three independent monthly
 * measurements of three different populations of homes, and a permit
 * issued this month has no particular relationship to a start counted
 * this month.
 *
 * So the correction is not a footnote. It is the sentence directly
 * beneath the diagram, in the same block, at the same weight as the
 * boxes — because a reader who takes the picture and skips the caption
 * is the reader this page has to be correct for.
 *
 * Hand-authored HTML/CSS. No diagram library, nothing that needs
 * JavaScript, and it works read aloud in order: the whole thing is a
 * described list, so a screen reader gets the same sequence.
 */

const STAGES = ["PERMITS", "STARTS", "COMPLETIONS"] as const;

export function PipelineDiagram() {
  return (
    <figure className="m-0">
      <figcaption className="type-label text-fg-muted">How a home gets counted</figcaption>

      <div className="mt-3 rounded-lg border border-line bg-surface p-4 sm:p-5">
        <ol className="grid gap-3 sm:grid-cols-[1fr_auto_1fr_auto_1fr] sm:items-stretch">
          {STAGES.map((stage, index) => (
            <li key={stage} className="contents">
              <div className="rounded-md border border-line-subtle p-3">
                <p className="text-sm font-medium text-fg">{STAGE_COPY[stage].name}</p>
                <p className="mt-1 text-sm text-fg-secondary">{STAGE_COPY[stage].meaning}</p>
              </div>
              {index < STAGES.length - 1 && (
                <p
                  aria-hidden="true"
                  className="self-center text-center text-xl leading-none text-fg-muted sm:px-1"
                >
                  <span className="sm:hidden">↓</span>
                  <span className="hidden sm:inline">→</span>
                </p>
              )}
            </li>
          ))}
        </ol>

        <p className="mt-4 max-w-prose text-sm text-fg-secondary">
          <span className="font-medium text-fg">These are three separate counts, not one batch of homes.</span> The
          permits counted this month are not the homes started this month, and not every authorised home is built.
          How long a home takes to go from approved to finished varies, so MacroChipz publishes no expected lag and
          no share of permits that becomes a start.
        </p>
      </div>
    </figure>
  );
}
