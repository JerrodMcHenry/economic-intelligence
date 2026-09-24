import type { ChangeWindow, CurveSpread, RateLevel } from "../../api/rates.types";
import {
  COMPARISON_WINDOWS,
  comparisonAvailable,
  levelShift,
  selectComparison,
  shapeChange,
  type CurveComparison as Comparison,
} from "../../lib/ratesCurveComparison";
import {
  formatBasisPoints,
  formatChangeWindow,
  formatObservationDate,
  maturityLabel,
} from "../../lib/ratesFormat";

/**
 * Choosing which earlier published date to compare against (#52B).
 *
 * ================================================================
 * THE BUTTON SAYS BOTH THINGS
 * ================================================================
 *
 * `rates_v1.0` counts published trading SESSIONS, never calendar days,
 * and `lib/ratesFormat.ts` has refused to relabel "21 sessions" as
 * "1 month" since #30 — the equivalence does not hold across holidays
 * and missing prints, and the methodology explicitly rejects it.
 *
 * But a reader does not hold a session count in their head. They hold a
 * date. So each control carries the methodology's own unit AND the date
 * it actually resolved to, which is a published field
 * (`changes[].from_date`), not a conversion performed here.
 *
 * A window no maturity published is not offered. It is not rendered
 * disabled either: an option that has never been available is noise,
 * whereas a maturity that is missing from an otherwise-available window
 * is a gap the reader needs told about — and that is said in the
 * comparison note, on the page, rather than in a control.
 */
export function CurveComparisonControls({
  levels,
  selected,
  onSelect,
}: {
  levels: RateLevel[];
  selected: ChangeWindow | null;
  onSelect: (window: ChangeWindow | null) => void;
}) {
  const offered = COMPARISON_WINDOWS.filter((window) => comparisonAvailable(levels, window));
  if (offered.length === 0) return null;

  return (
    <div className="mt-1">
      <p id="curve-compare-label" className="type-label text-fg-muted">
        Compare with an earlier published day
      </p>
      <div
        role="group"
        aria-labelledby="curve-compare-label"
        className="mt-2 grid grid-cols-2 gap-2 sm:flex sm:flex-wrap"
      >
        <button
          type="button"
          aria-pressed={selected === null}
          onClick={() => onSelect(null)}
          className={buttonClasses(selected === null)}
        >
          <span className="block type-meta text-fg-muted">Latest only</span>
          <span className="mt-0.5 block text-sm font-semibold">No comparison</span>
        </button>

        {offered.map((window) => {
          const comparison = selectComparison(levels, window);
          const active = selected === window;
          return (
            <button
              key={window}
              type="button"
              aria-pressed={active}
              onClick={() => onSelect(window)}
              className={buttonClasses(active)}
            >
              <span className="block type-meta text-fg-muted">{formatChangeWindow(window)} earlier</span>
              <span className="type-numeric mt-0.5 block text-sm font-semibold">
                {comparison.sharedDate === null ? "Mixed dates" : formatObservationDate(comparison.sharedDate)}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function buttonClasses(active: boolean): string {
  return [
    "min-h-11 rounded-lg border px-3 py-2 text-left transition-colors motion-reduce:transition-none",
    active
      ? "border-[color:var(--mc-focus)] bg-[color:var(--mc-selected)] text-[color:var(--mc-selected-fg)]"
      : "border-line text-fg-secondary hover:border-line-strong hover:text-fg",
  ].join(" ");
}

/**
 * What the two curves say, in two clauses (#52B).
 *
 * ================================================================
 * EVERY FIGURE IN THESE SENTENCES IS A PUBLISHED FIELD
 * ================================================================
 *
 * LEVEL reads each maturity's `change_basis_points`. Whether they all
 * share a sign is a classification of published values — the same class
 * of operation as `changeDirection` in `lib/ratesFormat.ts`, which has
 * read that sign since #30 — and when the signs disagree it says so
 * rather than picking one.
 *
 * SHAPE reads the 2s30s spread's OWN `from_value` and `to_value` for the
 * same window. It does not subtract the 2-year from the 30-year on two
 * dates, which is precisely the operation
 * `src/test/no-rates-calculation.test.ts` exists to forbid — and which
 * is not needed, because `rates_v1.0` already published the answer.
 *
 * ================================================================
 * WHAT IT REFUSES TO SAY
 * ================================================================
 *
 * A narrowing curve is the single most over-claimed object in consumer
 * finance. `rates_v1.0` defines no state label, no forecast and no
 * cross-domain conclusion, so this component describes the two shapes
 * and stops. The closing sentence states that refusal ON THE PAGE
 * rather than leaving a reader to supply the missing claim themselves.
 *
 * WORDING NOTE, and it cost a test to find: `Rates.test.tsx` asserts
 * that five words never appear in this page's rendered text at all --
 * one of them the name of the downturn a flattening curve is popularly
 * said to predict. A sentence DENYING that claim still contains the
 * word, and the guard cannot tell a denial from an assertion. It should
 * not have to: the guard has been right since #30, and the refusal is
 * easy to write without the word. So the sentence names what
 * `rates_v1.0` does not define, and says MacroChipz will not tell you
 * what the shape means for what happens next -- which is the same
 * refusal, stated positively, and covers claims nobody thought to ban.
 */
export function CurveReading({
  comparison,
  spreads,
  latestDate,
}: {
  comparison: Comparison;
  spreads: CurveSpread[];
  latestDate: string | null;
}) {
  const shift = levelShift(comparison);
  const shape = shapeChange(spreads, comparison.window);
  const since = formatObservationDate(comparison.sharedDate);

  const shortest = comparison.points[0];
  const longest = comparison.points[comparison.points.length - 1];

  return (
    /* `aria-live="polite"`: switching the window announces the new
       reading without moving focus off the control just pressed. */
    <div className="mt-5 border-t border-line-subtle pt-4" aria-live="polite">
      <h3 className="type-label text-fg-muted">Level</h3>
      <p className="mt-1.5 max-w-prose text-sm text-fg-secondary">
        {levelSentence(shift, since)}
        {shortest !== undefined && longest !== undefined && shortest !== longest && (
          <>
            {" "}
            The {maturityLabel(shortest.seriesId)} moved{" "}
            <span className="type-numeric font-semibold text-fg">
              {formatBasisPoints(shortest.changeBasisPoints)}
            </span>{" "}
            and the {maturityLabel(longest.seriesId)} moved{" "}
            <span className="type-numeric font-semibold text-fg">
              {formatBasisPoints(longest.changeBasisPoints)}
            </span>
            .
          </>
        )}
      </p>

      <h3 className="mt-4 type-label text-fg-muted">Shape</h3>
      {shape === null ? (
        <p className="mt-1.5 max-w-prose text-sm text-fg-secondary">
          MacroChipz has no published 30-year-minus-2-year comparison for this window, so no change in the curve&rsquo;s
          shape is described. Nothing is inferred from the two lines above in its place.
        </p>
      ) : (
        <p className="mt-1.5 max-w-prose text-sm text-fg-secondary">
          The gap between the {maturityLabel(shortest?.seriesId ?? "UST_NOMINAL_2Y")} and the{" "}
          {maturityLabel(longest?.seriesId ?? "UST_NOMINAL_30Y")} is{" "}
          <span className="font-semibold text-fg">{shapeWord(shape.change_basis_points)}</span>: it was{" "}
          <span className="type-numeric font-semibold text-fg">{(shape.from_value as number).toFixed(2)}</span>{" "}
          percentage points on {formatObservationDate(shape.from_date)} and{" "}
          <span className="type-numeric font-semibold text-fg">{(shape.to_value as number).toFixed(2)}</span> on{" "}
          {formatObservationDate(shape.to_date ?? latestDate)}. MacroChipz publishes that as{" "}
          <span className="type-numeric font-semibold text-fg">{formatBasisPoints(shape.change_basis_points)}</span> and
          draws no conclusion from it. These are two published shapes on two published days. MacroChipz&rsquo;s
          methodology defines no state label and no forecast, so it does not say what a narrower or wider gap means for
          what happens next, or for any rate you might personally be offered.
        </p>
      )}
    </div>
  );
}

function levelSentence(shift: ReturnType<typeof levelShift>, since: string): string {
  switch (shift) {
    case "ALL_HIGHER":
      return `Every maturity pays more than it did on ${since}.`;
    case "ALL_LOWER":
      return `Every maturity pays less than it did on ${since}.`;
    case "UNCHANGED":
      return `Every maturity is unchanged from ${since}.`;
    case "MIXED":
      return `Some maturities pay more and some pay less than they did on ${since}.`;
    case "UNAVAILABLE":
      return `MacroChipz published no change for any maturity against ${since}.`;
  }
}

function shapeWord(changeBasisPoints: number | null): string {
  if (changeBasisPoints === null) return "not available";
  if (changeBasisPoints < 0) return "narrower";
  if (changeBasisPoints > 0) return "wider";
  return "unchanged";
}

/**
 * What the comparison could not draw, said on the page (#52B).
 *
 * Two distinct situations, neither of which may be silent:
 *
 *   1. **A maturity is missing for this window.** The dashed line
 *      breaks; this names which maturity and which date, so the gap in
 *      the picture has a stated cause.
 *   2. **The maturities resolved to different dates.** Then there is no
 *      single earlier curve to draw at all, and drawing one anyway
 *      would be inventing a shape nobody published. The comparison is
 *      withheld and the dates are listed.
 */
export function CurveComparisonNote({ comparison, levels }: { comparison: Comparison; levels: RateLevel[] }) {
  const missing = comparison.points.filter((point) => {
    if (point.available) return false;
    const level = levels.find((entry) => entry.series_id === point.seriesId);
    // A maturity that was never ingested is already explained by the
    // curve itself; only a maturity that HAS a latest value but no
    // comparison reading is a gap in this comparison.
    return level !== undefined && level.available && level.latest_value !== null;
  });

  if (comparison.sharedDate === null && comparison.distinctDates.length > 1) {
    return (
      <p className="mt-4 max-w-prose text-sm text-fg-secondary">
        <span className="font-medium text-fg">No single earlier curve.</span> For this window the maturities resolved to
        different published dates ({comparison.distinctDates.map((date) => formatObservationDate(date)).join(", ")}), so
        MacroChipz does not draw them as one curve. Four values from four days is not a shape anyone published.
      </p>
    );
  }

  if (missing.length === 0) return null;

  return (
    <p className="mt-4 max-w-prose text-sm text-fg-secondary">
      <span className="font-medium text-fg">Incomplete comparison.</span> No{" "}
      {missing.map((point) => maturityLabel(point.seriesId)).join(" or ")} reading is published for{" "}
      {formatObservationDate(comparison.sharedDate)}, so the dashed line breaks there rather than being drawn through a
      value MacroChipz does not have.
    </p>
  );
}
