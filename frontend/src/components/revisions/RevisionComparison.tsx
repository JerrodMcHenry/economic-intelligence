import type { ObservationChangeIntelligence } from "../../api/intelligence.types";

/**
 * ORIGINALLY REPORTED → REVISED TO (Increment #43).
 *
 * The visual heart of a revision. Two values side by side on a wide
 * screen, stacked on a narrow one, with the change stated in words
 * beneath.
 *
 * COLOUR CARRIES NO JUDGEMENT. A downward revision is not bad news and
 * an upward one is not good news — unemployment falling and inflation
 * falling are opposite sentiments from identical arithmetic, and
 * MacroChipz has no methodology that ranks either. So both values use
 * the same neutral token, the direction is carried by the WORD "Down"
 * or "Up" (never by colour, and never by an arrow alone, which a
 * screen reader would not announce), and a test fails if a semantic
 * `state-*` or `feedback-*` token appears here.
 *
 * "Originally reported" renders as **Not recorded** unless the backend
 * says the original value is genuinely known. A value imported at
 * migration time is not an original reading, and showing it under that
 * heading would be inventing economic history.
 */
export function RevisionComparison({ object }: { object: ObservationChangeIntelligence }) {
  const { previous_value, new_value, delta, units, original_value_known } = object.payload;

  const direction = delta === null || delta === 0 ? "unchanged" : delta > 0 ? "up" : "down";
  const unit = (units ?? "").toLowerCase();
  const unitWord = unit === "percent" ? "percentage points" : unit || "units";

  return (
    <div>
      <dl className="grid gap-4 sm:grid-cols-[1fr_auto_1fr] sm:items-end">
        <div>
          <dt className="type-label text-fg-muted">Originally reported</dt>
          <dd className="type-numeric mt-1 text-4xl font-semibold text-fg sm:text-5xl">
            {original_value_known === true && previous_value !== null ? (
              previous_value
            ) : (
              <span className="text-xl font-normal text-fg-muted">Not recorded</span>
            )}
          </dd>
        </div>

        <div aria-hidden="true" className="hidden pb-3 text-2xl text-fg-muted sm:block">
          →
        </div>

        <div>
          <dt className="type-label text-fg-muted">Revised to</dt>
          <dd className="type-numeric mt-1 text-4xl font-semibold text-fg sm:text-5xl">
            {new_value === null ? <span className="text-xl font-normal text-fg-muted">Not reported</span> : new_value}
          </dd>
        </div>
      </dl>

      {delta !== null && direction !== "unchanged" && (
        <p className="mt-4 text-lg text-fg-secondary">
          <span className="font-medium text-fg">
            {direction === "down" ? "Down" : "Up"} {Math.abs(delta).toFixed(2)} {unitWord}
          </span>{" "}
          from what MacroChipz first recorded
        </p>
      )}
      {delta !== null && direction === "unchanged" && (
        <p className="mt-4 text-lg text-fg-secondary">The value did not change.</p>
      )}
      {delta === null && (
        <p className="mt-4 max-w-prose text-sm text-fg-muted">
          MacroChipz cannot state the size of this change, because it does not hold both values.
        </p>
      )}
    </div>
  );
}
