import type { RateLevel } from "../../api/rates.types";
import type { Explanation } from "../../content/explanations/types";
import { formatObservationDate, formatRateValue, maturityLabel } from "../../lib/ratesFormat";
import { ExplanationTrigger } from "../explanations/ExplanationTrigger";
import { HistoricalContextNote } from "./HistoricalContextNote";
import { RateChangeList } from "./RateChangeList";
import { SourceProvenanceDisclosure } from "./RateProvenance";

/**
 * The maturity a reader selected on the curve (Increment #49B).
 *
 * ================================================================
 * WHAT IT REPLACED, AND WHY
 * ================================================================
 *
 * `/rates` used to render all four nominal maturities as four
 * simultaneous `RateLevelCard`s. #49A measured the consequence: 4.76
 * appeared SIX times in one page's rendered text — the card, the
 * chart's plotted label, the chart's table, the spread card's working
 * and the "What changed" row — and the page was 6,777px on a phone.
 *
 * One maturity at a time, chosen by the reader, says the same thing
 * once. Nothing is hidden: the other three are one tap away on the
 * curve, and all four are still published in the chart's table.
 *
 * ================================================================
 * IT SHOWS MORE THAN THE CARD DID, NOT LESS
 * ================================================================
 *
 * `RateLevelCard` is rendered on this page with `showContext={false}`,
 * so `historical_context` has been fetched and thrown away since #30.
 * With one maturity on screen there is room for it, and it is shown.
 *
 * NO ARITHMETIC HAPPENS HERE. Every figure is the backend's own, and
 * `src/test/no-rates-calculation.test.ts` enforces that this file
 * cannot change that.
 */

/**
 * What a maturity IS, in the reader's words.
 *
 * Composed from the #44 explainer registry's reviewed copy rather than
 * written here. `explain.what-is-a-treasury-yield` says: "The yield is
 * the annual return an investor earns by holding one." That is the
 * precise framing — a market yield on a security, NOT the government's
 * exact cost of any new borrowing — and it is what these lines carry.
 *
 * The 10-year's extra clause is a contiguous substring of
 * `explain.why-the-10-year-matters`.
 */
const MATURITY_YEARS: Readonly<Record<string, string>> = {
  UST_NOMINAL_2Y: "two years",
  UST_NOMINAL_5Y: "five years",
  UST_NOMINAL_10Y: "ten years",
  UST_NOMINAL_30Y: "thirty years",
  UST_REAL_5Y: "five years",
  UST_REAL_10Y: "ten years",
};

function plainIdentity(seriesId: string): string | null {
  const years = MATURITY_YEARS[seriesId];
  if (years === undefined) return null;
  const base = `The annual return an investor earns by holding a Treasury security that matures in ${years}.`;
  return seriesId === "UST_NOMINAL_10Y"
    ? `${base} It is the most widely used reference point for long-term borrowing.`
    : base;
}

export function SelectedMaturityPanel({ level, explanation }: { level: RateLevel; explanation: Explanation }) {
  const maturity = maturityLabel(level.series_id);
  const identity = plainIdentity(level.series_id);

  return (
    /* `aria-live="polite"`: a reader hears the new maturity without
       being pulled out of the curve they are still exploring. Focus
       stays on the control they pressed. */
    <div className="lx-card rounded-xl p-5 sm:p-6" aria-live="polite">
      <div className="flex items-center gap-1.5">
        <h3 className="type-label text-fg-muted">{maturity}</h3>
        <ExplanationTrigger explanation={explanation} />
      </div>

      {level.available ? (
        <>
          <p className="type-numeric mt-2 text-4xl font-semibold tracking-tight text-fg sm:text-5xl">
            {formatRateValue(level.latest_value)}
          </p>
          <p className="mt-2 text-sm text-fg-secondary">
            {level.title} · observed {formatObservationDate(level.latest_date)}
          </p>
          {identity && <p className="mt-3 max-w-prose text-sm text-fg-secondary">{identity}</p>}

          <div className="mt-5">
            <RateChangeList changes={level.changes} label={maturity} />
          </div>

          {/* Fetched since #30 and never shown on this page until now. */}
          <div className="mt-5 border-t border-line-subtle pt-4">
            <HistoricalContextNote context={level.historical_context} />
          </div>

          <div className="mt-4">
            <SourceProvenanceDisclosure provenance={level.provenance} />
          </div>
        </>
      ) : (
        <>
          <p className="mt-2 text-lg font-medium text-fg-muted">Not available</p>
          <p className="mt-1 max-w-prose type-meta text-fg-muted">
            {level.title} has not been ingested yet, so no level, change, or context can be shown for it.
          </p>
        </>
      )}
    </div>
  );
}
