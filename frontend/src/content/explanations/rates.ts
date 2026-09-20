/**
 * Curated, static explanation content for the Rates Intelligence UI
 * (Increment #30), following the same content model every other domain
 * uses (see ./types.ts and ./inflation.ts).
 *
 * Every sentence here is traceable to `docs/methodology/rates-v1.0.md`.
 * This file introduces NO new economic claim, no forecast, no regime
 * name, and no direction-is-good/bad framing. Where the methodology
 * refuses a claim (notably: a breakeven is not an inflation forecast),
 * this copy refuses it in the same words.
 */

import type { Explanation } from "./types";

const METHODOLOGY_NOTE = "Methodology: rates_v1.0";

export const NOMINAL_YIELD: Explanation = {
  id: "rates.nominal-yield",
  title: "Nominal Treasury par yield",
  definition:
    "The yield a Treasury security of this maturity would carry if it were priced at par. Treasury derives these rates from indicative market quotations collected each business day.",
  whyItMatters:
    "Nominal yields are the baseline cost of borrowing for the U.S. government at each maturity, and the reference point most other fixed-income pricing is quoted against.",
  sourceNote: METHODOLOGY_NOTE,
};

export const REAL_YIELD: Explanation = {
  id: "rates.real-yield",
  title: "Real Treasury par yield",
  definition:
    "The par yield on Treasury Inflation-Protected Securities (TIPS) of this maturity — a yield stated after inflation compensation, rather than before it.",
  whyItMatters:
    "A real yield shows the return available above realized inflation, so it separates how much of a nominal yield reflects compensation for expected price changes from the underlying real cost of money. Real yields are published for 5-year and longer maturities only.",
  sourceNote: METHODOLOGY_NOTE,
};

export const CURVE_SPREAD: Explanation = {
  id: "rates.curve-spread",
  title: "Curve spread",
  definition:
    "The difference between two maturities' nominal par yields on the same observation date, reported in basis points. 2s10s is the 10-year yield minus the 2-year; 2s30s is the 30-year minus the 2-year.",
  whyItMatters:
    "A curve spread describes the shape of the yield curve — whether longer maturities yield more or less than shorter ones. A negative spread is an inversion. MacroChipz reports the number and its sign; rates_v1.0 defines no state label, and attaches no economic reading, to either.",
  sourceNote: METHODOLOGY_NOTE,
};

export const INFLATION_COMPENSATION: Explanation = {
  id: "rates.inflation-compensation",
  title: "Market-implied inflation compensation",
  definition:
    "The nominal Treasury par yield minus the real (TIPS) par yield at the same maturity, on the same observation date, reported in percentage points.",
  whyItMatters:
    "It is often described loosely as an inflation expectation, but it is not one. The difference also contains an inflation risk premium and a TIPS liquidity premium, and TIPS are linked to CPI while the Federal Reserve's target is defined on PCE. rates_v1.0 does not separate those components, so MacroChipz reports the measured difference under a name that describes exactly what was measured.",
  sourceNote: METHODOLOGY_NOTE,
};

export const SESSION_WINDOW: Explanation = {
  id: "rates.session-window",
  title: "Session windows",
  definition:
    "A change window counts published business sessions, not calendar days. A 5-session change compares the latest observation with the one five published sessions earlier, whatever calendar dates those are.",
  whyItMatters:
    "Treasury publishes on business days only, so a calendar rule would need a fallback for weekends, holidays and missing prints — and that fallback, rather than the definition, would decide the number you read. Counting sessions needs no fallback. It also means 21 sessions is approximately, not exactly, one month, which is why these windows are never labelled in months.",
  sourceNote: METHODOLOGY_NOTE,
};

export const HISTORICAL_PERCENTILE: Explanation = {
  id: "rates.historical-percentile",
  title: "Historical context",
  definition:
    "Every 5-session change available in the stored history is computed, and the latest change is ranked against all prior ones. The signed rank asks how this move compares by direction and size together; the magnitude rank asks only how large it was, ignoring direction.",
  whyItMatters:
    "The two ranks answer different questions and can disagree sharply: a large fall is unremarkable in signed terms and extreme in magnitude. Both are shown with the number of observations and the start of the history, because a percentile over a few months is a different claim from one over decades.",
  sourceNote: METHODOLOGY_NOTE,
};

export const DATA_FRESHNESS: Explanation = {
  id: "rates.data-freshness",
  title: "Observation date",
  definition:
    "Treasury publishes these rates once per business day, derived from quotations collected at approximately 3:30 PM ET. MacroChipz shows the latest observation date it has ingested.",
  whyItMatters:
    "This is a daily published dataset, not a streaming market feed. The date shown is the date the values belong to — not the moment you loaded the page.",
  sourceNote: METHODOLOGY_NOTE,
};
