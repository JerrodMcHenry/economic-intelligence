/**
 * The MacroChipz explainer registry (Increment #44).
 *
 * ================================================================
 * THREE KINDS OF CONTENT, KEPT APART ON PURPOSE
 * ================================================================
 *
 *   A. CANONICAL INTELLIGENCE   "the 10-year is 5.01%"
 *      Deterministic, versioned, from #39. Authoritative.
 *
 *   B. CURATED EXPLANATION      "what a Treasury yield is"   <- THIS FILE
 *      Written by us, version-controlled, reviewed in code.
 *      General and durable: true last month and next month.
 *
 *   C. GENERATIVE INTERPRETATION  Ask MacroChipz.
 *      Bounded, optional, never authoritative.
 *
 * This file is only ever B. **No explainer prose is generated at
 * runtime**, by a model or otherwise — every sentence below was
 * written, reviewed and committed, and a guard test fails on a model
 * SDK or a `fetch` appearing in this path.
 *
 * WHY A REGISTRY RATHER THAN PROSE IN COMPONENTS
 * ----------------------------------------------
 * The existing 71 curated `Explanation` entries are field-level
 * tooltips bound to specific UI — "what does `r_3m_annualized` mean
 * here". They are good at that and are NOT replaced. What they cannot
 * do is stand alone: a person arriving from a 30-second video has no
 * surrounding page to be a tooltip on. An explainer is a destination;
 * an `Explanation` is an annotation.
 *
 * RELATIONSHIPS ARE CURATED, NEVER COMPUTED
 * -----------------------------------------
 * `related` is a hand-written list of ids. There is no recommender, no
 * popularity ranking, no personalisation and no similarity scoring —
 * the rabbit hole is a path someone chose to dig, not an algorithm's
 * guess. Kept to 2-4 so it stays a choice rather than a feed.
 */
import type { WorldId } from "../worlds/registry";

/**
 * What a claim in an explainer rests on.
 *
 * Deliberately three coarse values rather than a bibliography. The
 * point is to stop an explainer implying institutional backing it does
 * not have, not to build a citation manager.
 */
export type ExplainerBasis =
  /** General economics a reference work would state uncontroversially. */
  | "GENERAL_ECONOMICS"
  /** Describes how MacroChipz's own tracked data or methodology behaves. */
  | "MACROCHIPZ_METHODOLOGY"
  /** A structural fact about a named institution's published role. */
  | "INSTITUTIONAL_ROLE";

export interface Explainer {
  /** Stable identity. Never a provider series id (#38). */
  readonly id: string;
  /** The permanent URL segment. Changing it breaks shared links. */
  readonly slug: string;
  /** The "Wait, seriously?" hook. A real question, never manufactured surprise. */
  readonly question: string;
  /** Short label for cards and related lists. */
  readonly shortTitle: string;
  /**
   * THE ONE-SENTENCE ANSWER. Load-bearing: someone arriving from a
   * video must get the answer before scrolling.
   */
  readonly answer: string;
  readonly whatItIs: string;
  readonly howItWorks?: ReadonlyArray<string>;
  /** Only where there is a defensible consumer connection. */
  readonly whatThisMeansForYou?: string;
  readonly misconception?: string;
  /** Source-neutral concept ids (#38) this connects to. */
  readonly conceptIds?: ReadonlyArray<string>;
  readonly worlds?: ReadonlyArray<WorldId>;
  /** Curated rabbit hole. 2-4 entries. */
  readonly related: ReadonlyArray<string>;
  readonly basis: ExplainerBasis;
  /** What this explainer does NOT establish. */
  readonly limitations?: ReadonlyArray<string>;
}

/**
 * THE SET.
 *
 * Chosen against what MacroChipz can actually show and explain
 * accurately today — not a survey of economics. Each one either
 * corrects something people measurably get wrong, or unlocks a
 * question the product already raises on a page someone is looking at.
 *
 * #45 added the two Housing entries at the end, and only two. Both meet
 * the bar this file sets: each corrects a specific, checkable
 * misreading of a number now on `/housing`, and every claim in them is
 * supportable from Census's own published definitions or from
 * MacroChipz's own behaviour. A general "what is the housing market"
 * explainer was not written, because MacroChipz tracks three
 * construction measures and nothing about prices, sales or
 * affordability — it would have had to describe things this product
 * cannot show.
 *
 * DISCOVERY. Both are reachable from `/housing` through
 * `UnderstandWorld`, which lists every explainer naming a world, and
 * the annual-rate one is additionally linked inline from the section
 * that renders the figure it explains. They also link to each other,
 * and the annual-rate one links onward to the Fed/mortgage explainer
 * that a housing reader is likely to want next. The site-level
 * explainer-library problem that #44 deferred stays deferred.
 */
export const EXPLAINERS: ReadonlyArray<Explainer> = [
  {
    id: "explain.fed-and-mortgage-rates",
    slug: "fed-and-mortgage-rates",
    question: "Wait, the Fed doesn't set mortgage rates?",
    shortTitle: "The Fed and mortgage rates",
    answer:
      "No. The Federal Reserve sets a short-term rate that banks charge each other overnight. Your mortgage rate is set by lenders in a market, and it is a different number reached a different way.",
    whatItIs:
      "The Federal Reserve's policy decision targets the federal funds rate — an overnight rate between banks. A 30-year mortgage is a loan lasting decades, priced by lenders competing in a market. The two are related, but one does not dial the other.",
    howItWorks: [
      "The Fed targets a short-term policy rate, and that decision ripples through what investors expect for the future.",
      "Those expectations show up in longer-term interest rates, including what the U.S. government pays to borrow for ten years.",
      "Lenders price mortgages against long-term borrowing conditions — not against the Fed's overnight rate.",
      "Lenders also add their own costs and risks: the market for bundled mortgage loans, the chance a borrower repays early, credit conditions, and what each lender needs to earn.",
    ],
    whatThisMeansForYou:
      "A Fed announcement does not translate directly into the rate you are quoted, and mortgage rates sometimes move before a Fed meeting or against it afterwards. Comparing lenders matters, because two lenders pricing the same conditions can still quote you different rates.",
    misconception:
      "The common belief is that the Fed sets mortgage rates outright, so a Fed cut should mean a cheaper mortgage that week. It often does not work that way.",
    conceptIds: ["UST_NOMINAL_10Y", "UST_NOMINAL_30Y"],
    worlds: ["RATES"],
    related: ["explain.why-the-10-year-matters", "explain.what-is-a-treasury-yield", "explain.inflation-vs-prices"],
    basis: "INSTITUTIONAL_ROLE",
    limitations: [
      "MacroChipz does not track mortgage rates and makes no forecast about where they are going.",
      "This explains the relationship in general. It does not explain why any particular rate moved on any particular day.",
    ],
  },
  {
    id: "explain.what-is-a-treasury-yield",
    slug: "what-is-a-treasury-yield",
    question: "What is a Treasury yield, really?",
    shortTitle: "Treasury yields",
    answer:
      "It is what it costs the U.S. government to borrow money for a set length of time — and because that borrowing is treated as about as safe as lending gets, it becomes the reference point for almost everything else.",
    whatItIs:
      "When the U.S. government borrows, it issues Treasury securities with a fixed length: two years, ten years, thirty years. The yield is the annual return an investor earns by holding one. MacroChipz records the yield Treasury publishes for each maturity, every business day.",
    howItWorks: [
      "Investors buy and sell Treasuries continuously, and the yield moves with what they are willing to accept.",
      "A longer maturity generally carries a different yield from a shorter one, because lending for thirty years is a different proposition from lending for two.",
      "Because the borrower is the U.S. government, these yields act as a baseline other borrowing is priced against.",
    ],
    conceptIds: ["UST_NOMINAL_2Y", "UST_NOMINAL_5Y", "UST_NOMINAL_10Y", "UST_NOMINAL_30Y"],
    worlds: ["RATES"],
    related: ["explain.why-the-10-year-matters", "explain.what-is-the-yield-curve", "explain.real-yields"],
    basis: "GENERAL_ECONOMICS",
  },
  {
    id: "explain.why-the-10-year-matters",
    slug: "why-the-10-year-matters",
    question: "Why does everyone watch the 10-year Treasury?",
    shortTitle: "Why the 10-year matters",
    answer:
      "Because it is the most widely used reference point for long-term borrowing — so when it moves, the cost of other long-dated debt often moves in the same direction.",
    whatItIs:
      "The 10-year Treasury yield sits in the middle of the range: long enough to reflect views about the years ahead, short enough to stay heavily traded. That combination made it the number people quote.",
    howItWorks: [
      "Lenders and investors price other long-dated debt with reference to it.",
      "It is a reference point, not a mechanism: the 10-year does not set any other rate.",
      "The relationship is loose and changes over time, so other rates do not track it exactly.",
    ],
    conceptIds: ["UST_NOMINAL_10Y"],
    worlds: ["RATES"],
    related: ["explain.fed-and-mortgage-rates", "explain.what-is-the-yield-curve", "explain.what-is-a-treasury-yield"],
    basis: "MACROCHIPZ_METHODOLOGY",
    limitations: ["Being a reference point is not the same as controlling other rates."],
  },
  {
    id: "explain.what-is-the-yield-curve",
    slug: "what-is-the-yield-curve",
    question: "What is the yield curve?",
    shortTitle: "The yield curve",
    answer:
      "It is the shape you get when you line up what the government pays to borrow for two years, five, ten and thirty — and the shape is what people are reading.",
    whatItIs:
      "MacroChipz plots the yields for each maturity on the same day. Usually longer borrowing costs more than shorter. When it does not, the curve is described as inverted.",
    howItWorks: [
      "The difference between two maturities is called a spread — MacroChipz reports the 10-year minus the 2-year, and the 30-year minus the 2-year.",
      "A negative spread means the shorter maturity yields more than the longer one.",
      "MacroChipz reports the number and its sign, and attaches no economic reading to either.",
    ],
    conceptIds: ["UST_NOMINAL_2Y", "UST_NOMINAL_10Y", "UST_NOMINAL_30Y"],
    worlds: ["RATES"],
    related: ["explain.what-is-a-treasury-yield", "explain.why-the-10-year-matters", "explain.real-yields"],
    basis: "MACROCHIPZ_METHODOLOGY",
    limitations: [
      "MacroChipz's rates methodology defines no state label for the curve, so it does not call an inversion a signal of anything.",
    ],
  },
  {
    id: "explain.real-yields",
    slug: "real-yields",
    question: "What is a 'real' yield?",
    shortTitle: "Real yields",
    answer:
      "A yield stated after inflation instead of before it — what a lender earns on top of rising prices, rather than including them.",
    whatItIs:
      "A normal (nominal) yield bundles two things together: the real cost of money, and compensation for expected price changes. Inflation-protected Treasuries separate them, and MacroChipz records both.",
    howItWorks: [
      "The difference between a nominal yield and a real yield at the same maturity is often described loosely as an inflation expectation.",
      "It is not one: the gap also contains a risk premium and a liquidity premium.",
      "MacroChipz reports the measured difference under a name describing exactly what was measured, rather than calling it an expectation.",
    ],
    conceptIds: ["UST_REAL_5Y", "UST_REAL_10Y"],
    worlds: ["RATES"],
    related: ["explain.what-is-a-treasury-yield", "explain.inflation-vs-prices"],
    basis: "MACROCHIPZ_METHODOLOGY",
    limitations: ["Real yields are published for 5-year and longer maturities only."],
  },
  {
    id: "explain.inflation-vs-prices",
    slug: "inflation-vs-prices",
    question: "Wait, inflation falling doesn't mean prices are falling?",
    shortTitle: "Inflation vs prices",
    answer:
      "Correct. Inflation is the rate prices are rising. When inflation falls, prices are still going up — just more slowly than before.",
    whatItIs:
      "Inflation measures change, not level. An inflation rate dropping from 6% to 3% means prices rose half as fast this year as last year. It does not mean anything got cheaper.",
    howItWorks: [
      "For prices in general to fall, the inflation rate would have to go below zero — deflation, which is rare and usually unwelcome.",
      "This is why the cost of living can keep feeling higher even as inflation numbers improve: the increases from earlier years do not reverse.",
    ],
    whatThisMeansForYou:
      "If news reports say inflation is cooling and your shopping still costs more than it used to, both things are true at once. Cooling describes the speed of the increase, not a reversal of it.",
    misconception:
      "Falling inflation is often read as falling prices. It means prices are rising more slowly.",
    conceptIds: ["us.pce.core.price-index.sa.monthly", "us.cpi.headline.price-index.sa.monthly"],
    worlds: ["INFLATION"],
    related: ["explain.cpi-vs-pce", "explain.headline-vs-core", "explain.real-yields"],
    basis: "GENERAL_ECONOMICS",
  },
  {
    id: "explain.cpi-vs-pce",
    slug: "cpi-vs-pce",
    question: "Why are there two different inflation numbers?",
    shortTitle: "CPI vs PCE",
    answer:
      "Because two agencies measure prices in two different ways, and they usually disagree slightly. MacroChipz tracks both and uses one to check the other.",
    whatItIs:
      "CPI and PCE are separate price indexes built from different survey data with different weightings. Neither is wrong; they answer slightly different questions.",
    howItWorks: [
      "MacroChipz uses Core PCE as its primary signal for underlying inflation momentum.",
      "It uses Core CPI only to check whether that reading is corroborated by an independently constructed measure — never to override it.",
      "The Federal Reserve's 2% objective is defined in terms of PCE rather than CPI.",
    ],
    conceptIds: ["us.pce.core.price-index.sa.monthly", "us.cpi.core.price-index.sa.monthly"],
    worlds: ["INFLATION"],
    related: ["explain.headline-vs-core", "explain.inflation-vs-prices"],
    basis: "MACROCHIPZ_METHODOLOGY",
  },
  {
    id: "explain.headline-vs-core",
    slug: "headline-vs-core",
    question: "Why do economists strip out food and energy?",
    shortTitle: "Headline vs core",
    answer:
      "Not because food and energy do not matter — they obviously do — but because their prices swing so sharply month to month that they can hide the underlying trend.",
    whatItIs:
      "Headline inflation includes everything. Core inflation excludes food and energy. MacroChipz tracks both, and leads with core when judging momentum.",
    howItWorks: [
      "A single cold winter or oil-price move can push headline inflation around without telling you much about the broader direction.",
      "Core is steadier, which makes an underlying trend easier to see.",
      "Headline is still what you actually pay, which is why MacroChipz reports both rather than choosing one.",
    ],
    misconception:
      "Core inflation is sometimes read as economists ignoring groceries and fuel. It is a way of separating the trend from the noise, not a claim those costs are unimportant.",
    conceptIds: ["us.pce.core.price-index.sa.monthly", "us.pce.headline.price-index.sa.monthly"],
    worlds: ["INFLATION"],
    related: ["explain.cpi-vs-pce", "explain.inflation-vs-prices"],
    basis: "MACROCHIPZ_METHODOLOGY",
  },
  {
    id: "explain.jobs-two-surveys",
    slug: "jobs-two-surveys",
    question: "Wait, there are two different jobs numbers?",
    shortTitle: "The two jobs surveys",
    answer:
      "Yes — one counts jobs on employer payrolls, the other counts people and asks whether they have work. They measure different populations, so they can disagree without either being wrong.",
    whatItIs:
      "Payroll employment comes from a survey of employers. The unemployment rate comes from a survey of households. MacroChipz keeps them separate for exactly that reason.",
    howItWorks: [
      "The employer survey counts filled jobs, so one person holding two jobs counts twice.",
      "The household survey counts people, so someone who stops looking for work leaves the count entirely rather than appearing as a job lost.",
      "When the two components disagree, MacroChipz reports the overall Jobs state as Mixed rather than averaging them into a number that would describe neither.",
    ],
    misconception:
      "The two numbers are often treated as one 'jobs report' that should agree with itself. They are two measurements of two different populations.",
    conceptIds: ["us.nonfarm.payroll-employment.sa.monthly", "us.unemployment-rate.sa.monthly"],
    worlds: ["JOBS"],
    related: ["explain.unemployment-without-layoffs", "explain.inflation-vs-prices"],
    basis: "MACROCHIPZ_METHODOLOGY",
  },
  {
    id: "explain.unemployment-without-layoffs",
    slug: "unemployment-without-layoffs",
    question: "Wait, unemployment can rise without anyone losing a job?",
    shortTitle: "Unemployment without layoffs",
    answer:
      "Yes. The unemployment rate counts people who are out of work and looking for it — so if more people start looking, the rate can rise even when no one was laid off.",
    whatItIs:
      "To be counted as unemployed, someone must be both without work and actively seeking it. People who are not looking are outside the labour force entirely and are not in the rate at all.",
    howItWorks: [
      "When people who had stopped looking start again, they re-enter the labour force as unemployed, and the rate can go up.",
      "The reverse also happens: when people give up looking, they leave the count, and the rate can fall without anyone finding a job.",
      "This is why the rate alone does not tell you whether the jobs picture improved.",
    ],
    misconception:
      "A rising unemployment rate is usually read as layoffs. It can also mean more people are looking for work than before.",
    conceptIds: ["us.unemployment-rate.sa.monthly"],
    worlds: ["JOBS"],
    related: ["explain.jobs-two-surveys"],
    basis: "GENERAL_ECONOMICS",
  },
  {
    id: "explain.permits-starts-completions",
    slug: "permits-starts-completions",
    question: "What do permits, starts and completions actually mean?",
    shortTitle: "Permits, starts, completions",
    answer:
      "They are three separate counts of homes at three different moments: approved to be built, begun, and finished. They are not the same homes followed through time.",
    whatItIs:
      "Each month the Census Bureau and the Department of Housing and Urban Development jointly publish how many privately-owned homes were authorised by a building permit, how many had construction started, and how many were completed. MacroChipz records all three.",
    howItWorks: [
      "A permit is an approval from a local authority to go ahead with a build. Nothing has been dug.",
      "A start is counted when excavation begins for the footings or foundation.",
      "A completion is counted when the home is finished — Census's test is that all finished flooring has been installed. In a building with several units, the units count as completed when at least half are occupied or ready to be.",
      "The three are counted independently, so the permits counted this month are not the homes started this month.",
    ],
    whatThisMeansForYou:
      "If you want the earliest read on whether more homes are coming, permits is the one that moves first. But a permit is permission, not a house: not every authorised home gets built, and the time from approval to finished varies a great deal.",
    misconception:
      "The three numbers are often read as one batch of homes moving along a conveyor, so that permits today become completions on a predictable schedule. They are three separate measurements of three different groups of homes.",
    conceptIds: [
      "us.housing.units-authorized.saar.monthly",
      "us.housing.units-started.saar.monthly",
      "us.housing.units-completed.saar.monthly",
    ],
    worlds: ["HOUSING"],
    related: ["explain.saar-housing", "explain.fed-and-mortgage-rates"],
    basis: "INSTITUTIONAL_ROLE",
    limitations: [
      "MacroChipz publishes no expected lag between the three stages and no share of permits that becomes a start.",
      "These counts cover privately-owned homes only. Publicly-owned units are excluded by Census.",
      "MacroChipz applies no housing state, score or rating, so this explains what the numbers are — not whether they are good news.",
    ],
  },
  {
    id: "explain.saar-housing",
    slug: "saar-housing",
    question: "Wait, 1.5 million homes weren't built this month?",
    shortTitle: "Annual rates in housing",
    answer:
      "No. That figure is an annual rate: it describes the month's pace of building expressed as a yearly total. The number of homes actually started in a given month is closer to a tenth of it.",
    whatItIs:
      "Housing figures are usually quoted as a seasonally adjusted annual rate. Census calculates it by adjusting the month's figure for normal seasonal patterns and then multiplying by twelve, so one month can be compared with another and with a yearly total.",
    howItWorks: [
      "Construction is strongly seasonal — more homes are started in summer than in winter — so raw monthly figures move for reasons that have nothing to do with the housing market.",
      "Seasonal adjustment removes that expected pattern, and multiplying by twelve puts the result on a yearly scale.",
      "Census is explicit that the annual rate is neither a forecast nor a projection: it describes the pace in the particular month it was calculated for.",
      "You cannot get back to the real monthly count by dividing by twelve. The seasonal adjustment is exactly what that division throws away, which is why MacroChipz shows the actual unadjusted count separately.",
    ],
    whatThisMeansForYou:
      "When a headline says housing starts were 1.3 million, that is a pace, not a month's construction. It is the right number for comparing this month with last month, and the wrong number for picturing how many homes went up.",
    misconception:
      "An annual-rate figure is routinely read as a count of homes in that month. It is a yearly pace, and the month's actual count is published separately and is much smaller.",
    conceptIds: [
      "us.housing.units-started.saar.monthly",
      "us.housing.units-started.nsa.monthly",
    ],
    worlds: ["HOUSING"],
    related: ["explain.permits-starts-completions", "explain.inflation-vs-prices", "explain.fed-and-mortgage-rates"],
    basis: "INSTITUTIONAL_ROLE",
    limitations: [
      "Seasonal adjustment estimates an average seasonal pattern. Census notes it does not account for abnormal weather or year-to-year changes in it.",
      "Census's own guidance is that month-to-month movements in these figures are often irregular, and that establishing an underlying trend can take three to six months.",
      "MacroChipz does not test whether a monthly change is statistically significant.",
    ],
  },
];

const BY_SLUG = new Map(EXPLAINERS.map((explainer) => [explainer.slug, explainer]));
const BY_ID = new Map(EXPLAINERS.map((explainer) => [explainer.id, explainer]));

export function explainerBySlug(slug: string): Explainer | undefined {
  return BY_SLUG.get(slug);
}

export function explainerById(id: string): Explainer | undefined {
  return BY_ID.get(id);
}

/** Every explainer that names this world, in registry order. */
export function explainersForWorld(world: WorldId): Explainer[] {
  return EXPLAINERS.filter((explainer) => explainer.worlds?.includes(world));
}

/** Every explainer naming this concept id, in registry order. */
export function explainersForConcept(conceptId: string): Explainer[] {
  return EXPLAINERS.filter((explainer) => explainer.conceptIds?.includes(conceptId));
}

/** All permanent explainer paths — finite, so all of them are prerendered. */
export const EXPLAINER_PATHS: ReadonlyArray<string> = EXPLAINERS.map(
  (explainer) => `/explain/${explainer.slug}`,
);
