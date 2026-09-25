/**
 * Curated, static explanation content for the Inflation Monitor.
 * Grounded in docs/methodology/inflation-monitor-v1.0.md (frozen) --
 * every state description below matches that document's
 * "Classification rules" section exactly in substance (COOLING/HEATING
 * require both r_3m and r_6m strictly outside the neutral band around
 * r_12m; STABLE requires both inside it, inclusive; MIXED is
 * everything else with valid data). This file changes no methodology
 * semantics -- it only writes definitions for concepts the backend
 * already computes deterministically.
 */
import type { InflationState } from "../../api/inflation.types";
import type { Explanation } from "./types";

export const HEADLINE_INFLATION: Explanation = {
  id: "inflation.headline-inflation",
  title: "Headline inflation",
  definition:
    "The overall rate of price change across all the goods and services in a price index, with nothing excluded.",
  whyItMatters:
    "It reflects the full cost of living, but food and energy prices can swing sharply from month to month and obscure the underlying trend -- which is why Economic Intelligence also tracks core inflation separately.",
};

export const CORE_INFLATION: Explanation = {
  id: "inflation.core-inflation",
  title: "Core inflation",
  definition:
    "Inflation measured after excluding food and energy prices, which are volatile and can move for reasons unrelated to broader price pressure.",
  whyItMatters:
    "Excluding food and energy makes the underlying trend in prices easier to see. It's the primary basis for Economic Intelligence's inflation momentum reading.",
};

export const CPI: Explanation = {
  id: "inflation.cpi",
  title: "Consumer Price Index (CPI)",
  definition:
    "A measure of the average change in prices paid by consumers for a broad basket of goods and services, published by the Bureau of Labor Statistics.",
  whyItMatters:
    "It's one of the most widely followed inflation measures in the United States. Economic Intelligence uses Core CPI to check whether Core PCE's momentum reading is confirmed by a second, independently constructed measure.",
  sourceNote: "Series: CUSR0000SA0 (headline) / CUSR0000SA0L1E (core) · Source: U.S. Bureau of Labor Statistics",
};

export const PCE: Explanation = {
  id: "inflation.pce",
  title: "Personal Consumption Expenditures (PCE) price index",
  definition:
    "A measure of the average change in prices paid by or on behalf of consumers, published by the Bureau of Economic Analysis, based on what people actually buy.",
  whyItMatters:
    "The Federal Reserve's 2% inflation objective is defined in terms of PCE, not CPI -- which is why Economic Intelligence uses Headline PCE for the target comparison and Core PCE as its primary momentum signal.",
  sourceNote: "Series: DPCERG (headline) / DPCCRG (core) · Source: U.S. Bureau of Economic Analysis",
};

export const CORE_PCE: Explanation = {
  id: "inflation.core-pce",
  title: "Core PCE",
  definition:
    "The PCE price index excluding food and energy -- Economic Intelligence's primary signal for underlying inflation momentum.",
  whyItMatters:
    "It's the measure the Federal Reserve itself weighs most heavily when judging underlying inflation pressure, which is why it's Economic Intelligence's primary series rather than a secondary one.",
  sourceNote: "Series: DPCCRG (BEA) · Methodology: inflation_v1.0",
};

export const CORE_CPI: Explanation = {
  id: "inflation.core-cpi",
  title: "Core CPI",
  definition:
    "The Consumer Price Index excluding food and energy -- a second, independently constructed measure of underlying inflation.",
  whyItMatters:
    "Because Core CPI comes from different survey data than Core PCE, Economic Intelligence uses it only to check whether Core PCE's momentum reading is corroborated -- never to override it.",
  sourceNote: "Series: CUSR0000SA0L1E (BLS) · Methodology: inflation_v1.0",
};

export const THREE_MONTH_ANNUALIZED: Explanation = {
  id: "inflation.3m-annualized",
  title: "3-month annualized rate",
  definition:
    "The rate at which prices would rise over a full year if the pace of change over the most recent three months continued unchanged.",
  whyItMatters:
    "It reacts faster than the 12-month rate, which makes it useful for spotting a recent acceleration or slowdown in inflation before it shows up in slower-moving measures.",
  sourceNote: "Methodology: inflation_v1.0",
};

export const SIX_MONTH_ANNUALIZED: Explanation = {
  id: "inflation.6m-annualized",
  title: "6-month annualized rate",
  definition:
    "The rate at which prices would rise over a full year if the pace of change over the most recent six months continued unchanged.",
  whyItMatters:
    "It sits between the fast-moving 3-month rate and the slower 12-month rate, helping confirm whether a recent move is a brief blip or a more sustained shift.",
  sourceNote: "Methodology: inflation_v1.0",
};

export const TWELVE_MONTH: Explanation = {
  id: "inflation.12m",
  title: "12-month (year-over-year) rate",
  definition: "The percentage change in prices compared with the same month one year earlier.",
  whyItMatters:
    "It's the slowest-moving, most widely quoted inflation rate, and it's also the baseline Economic Intelligence's neutral band is built around when classifying momentum.",
  sourceNote: "Methodology: inflation_v1.0",
};

export const FED_OBJECTIVE: Explanation = {
  id: "inflation.fed-objective",
  title: "The Fed's 2% objective",
  definition: "The Federal Reserve's longer-run inflation goal, expressed as 2% annual growth in the headline PCE price index.",
  whyItMatters:
    "It's the benchmark investors and economists compare current inflation against when judging the likely direction of monetary policy.",
};

export const TARGET_DEVIATION: Explanation = {
  id: "inflation.target-deviation",
  title: "Target gap",
  definition:
    "The difference, in percentage points, between the current Headline PCE year-over-year rate and the Fed's 2% objective.",
  whyItMatters:
    "A positive gap means inflation is running above the Fed's goal; a negative gap means it's running below. The size of the gap, not just its direction, is part of how policy discussions are framed.",
};

export const MOMENTUM: Explanation = {
  id: "inflation.momentum",
  title: "Underlying inflation momentum",
  definition:
    "Economic Intelligence's classification of the recent direction of Core PCE inflation -- cooling, heating, stable, or mixed -- based on comparing its 3-month and 6-month annualized rates with its 12-month rate.",
  whyItMatters:
    "A single month's reading can be noisy. Momentum looks at multiple horizons together to give a more reliable read on which direction underlying inflation is actually moving.",
  sourceNote: "Methodology: inflation_v1.0",
};

export const CONFIRMATION: Explanation = {
  id: "inflation.confirmation",
  title: "Confirmation",
  definition:
    "Whether Core CPI's own momentum state agrees with Core PCE's, based on the same neutral-band comparison applied independently to each series.",
  whyItMatters:
    "Two independently constructed measures pointing the same direction is stronger evidence than one alone. Confirmation never changes Core PCE's own state -- it's a separate, secondary signal shown alongside it.",
  sourceNote: "Methodology: inflation_v1.0",
};

export const LATEST_REVISED_DATA: Explanation = {
  id: "inflation.latest-revised-data",
  title: "Latest revised data",
  definition:
    "Historical calculations use the latest revised observations available to Economic Intelligence. They may differ from values originally reported at the time.",
  whyItMatters:
    "Government economic data is often revised in the weeks and months after it's first published, as more complete survey responses come in. A figure shown here reflects the best currently available data for that period -- not a snapshot of what was known on the day it was first reported.",
};

/**
 * State Duration V1's own additional disclosure sentence (Increment
 * #24D, frozen verbatim in docs/product/state-duration-v1.md §38) --
 * NOT a modification of `LATEST_REVISED_DATA` above, a genuinely new,
 * additional sentence shown alongside it (see `DataBasisNote.tsx`).
 * `LATEST_REVISED_DATA` covers the revision-vintage half of the claim;
 * this sentence adds the one distinction that claim doesn't cover --
 * reconstruction today vs. what was reported in real time (§1).
 * Monitor-agnostic: shared, unchanged, by both /inflation and /labor
 * (the same DataBasisNote component renders on both pages), so it
 * lives alongside LATEST_REVISED_DATA here rather than being
 * duplicated per-monitor.
 */
export const STATE_DURATION_DISCLOSURE: Explanation = {
  id: "state-duration.disclosure",
  title: "How duration is calculated",
  definition:
    "This duration is calculated today, using the latest revised data and the current methodology, applied consistently across the period shown. It reflects what today's data implies, not what Economic Intelligence reported in real time as each month occurred.",
};

const INFLATION_STATE_EXPLANATIONS: Record<InflationState, Explanation> = {
  COOLING: {
    id: "inflation.state-cooling",
    title: "Cooling",
    definition: "Both the 3-month and 6-month annualized rates are running below the neutral band around the 12-month rate.",
    whyItMatters: "This is Economic Intelligence's signal that recent underlying inflation is decelerating relative to its own trailing trend.",
  },
  HEATING: {
    id: "inflation.state-heating",
    title: "Heating",
    definition: "Both the 3-month and 6-month annualized rates are running above the neutral band around the 12-month rate.",
    whyItMatters: "This is Economic Intelligence's signal that recent underlying inflation is accelerating relative to its own trailing trend.",
  },
  STABLE: {
    id: "inflation.state-stable",
    title: "Stable",
    definition: "Both the 3-month and 6-month annualized rates fall within the neutral band around the 12-month rate.",
    whyItMatters:
      "Recent inflation is tracking closely enough to its trailing 12-month pace that Economic Intelligence doesn't classify it as clearly accelerating or decelerating.",
  },
  MIXED: {
    id: "inflation.state-mixed",
    title: "Mixed",
    definition:
      "The 3-month and 6-month annualized rates aren't consistently above, below, or within the neutral band together, so the result doesn't meet the requirements for cooling, heating, or stable.",
    whyItMatters:
      "Mixed is a real, distinct classification, not a data gap -- it means the short- and medium-term measures are sending different signals about direction, which is itself useful information.",
  },
  INSUFFICIENT_DATA: {
    id: "inflation.state-insufficient-data",
    title: "Insufficient data",
    definition: "Economic Intelligence does not have all the persisted observations required to calculate this state.",
    whyItMatters:
      "This is a data-availability fact, not an economic reading -- it's shown so it's never mistaken for a direction like cooling, heating, or stable.",
  },
};

/** The curated explanation for a canonical `InflationState` value --
 * looked up by the backend's own already-classified value, never used
 * to derive one. */
export function inflationStateExplanation(state: InflationState): Explanation {
  return INFLATION_STATE_EXPLANATIONS[state];
}
