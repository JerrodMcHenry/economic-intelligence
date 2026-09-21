/**
 * Homepage presentation policy (Increment #42).
 *
 * ================================================================
 * THIS IS A PRESENTATION POLICY. IT IS NOT ECONOMIC METHODOLOGY.
 * ================================================================
 *
 * It answers exactly one question:
 *
 *     "What should MacroChipz show first?"
 *
 * It must never be read as answering:
 *
 *     "What is economically most important?"
 *
 * #39 deliberately publishes no significance ranking, and #42 does not
 * add one. There is no score in this file, no weighting, no magnitude
 * threshold, no notion of "big". Ordering is a stable tuple of
 * structural facts, so the same objects always produce the same page —
 * and so that nothing here can quietly become a claim about the
 * economy.
 *
 * WHAT THE LOCAL DATA ACTUALLY LOOKS LIKE (measured, #42 §2)
 * ----------------------------------------------------------
 * 1,899 Structured Intelligence objects:
 *
 *   ANALYSIS_CHANGE      1,532   of which 1,488 are COVERAGE
 *   OBSERVATION_CHANGE     358   ALL `change_type: NEW`, previous NULL
 *   RATES_MOVEMENT           6
 *   RELEASE_PROCESSED        3
 *
 * Two findings shaped every rule below, and neither was obvious from
 * the taxonomy alone:
 *
 * **All 44 "ECONOMIC" analysis changes are `UNAVAILABLE -> something`.**
 * Every one. They record the confirmation relationship becoming
 * computable for the first time during backfill. #39 classifies them
 * ECONOMIC because the field is an economic field — correctly, for its
 * purposes — but "MacroChipz can now calculate this" is an
 * availability event wearing an economic field's clothing. Presenting
 * it as economic news would be false. So the `change_class` filter is
 * necessary and NOT sufficient, which is why `previous_value` is
 * checked too.
 *
 * **All 358 observation changes are first observations**, not
 * revisions: `previous_value` is null throughout. A value arriving for
 * the first time during a backfill is not something that "changed".
 *
 * The honest consequence: **only RATES_MOVEMENT is eligible today**,
 * and the other rules are live but currently select nothing. They are
 * written anyway because they are the rules that stay correct when
 * genuine revisions and genuine state transitions arrive — and because
 * a filter that exists only implicitly is a filter nobody can test.
 *
 * NO CLOCK
 * --------
 * Eligibility and ordering are pure functions of the objects. Nothing
 * reads `Date.now()`, the request time, or the reader's visit history
 * (#42 §5 forbids reviving "days since visit"). That is a correctness
 * property, not a stylistic one: the homepage is prerendered at build
 * time, and a policy that consulted a clock would bake one moment's
 * answer into static HTML and then quietly lie about it.
 *
 * Staleness is therefore communicated by SHOWING the effective period,
 * never by hiding an object for being old.
 */
import type {
  IntelligenceObject,
  IntelligenceWorld,
  RatesMovementIntelligence,
} from "../api/intelligence.types";
import { ECONOMIC_WORLDS } from "../worlds/registry";

/** Bumped when the rules below change in a way that reorders the page. */
export const HOMEPAGE_PRESENTATION_POLICY = "homepage_presentation_v1.0";

/** Why an object was excluded. Reported for tests and documentation. */
export type IneligibleReason =
  | "COVERAGE_CHANGE"
  | "FIRST_COMPUTATION_NOT_A_CHANGE"
  | "FIRST_OBSERVATION_NOT_A_CHANGE"
  | "OPERATIONAL_NOT_ECONOMIC"
  | "NO_CONCEPT";

export interface Eligibility {
  eligible: boolean;
  reason?: IneligibleReason;
}

/**
 * Whether an object may appear on the homepage at all.
 *
 * Structural only. No magnitude, no threshold, no score.
 */
export function eligibility(object: IntelligenceObject): Eligibility {
  if (object.concepts.length === 0) return { eligible: false, reason: "NO_CONCEPT" };

  switch (object.type) {
    case "RATES_MOVEMENT":
      // A published level with its own movement windows, historical
      // context, evidence and (since #40C) a drawable series.
      return { eligible: true };

    case "ANALYSIS_CHANGE": {
      if (object.payload.change_class !== "ECONOMIC") {
        return { eligible: false, reason: "COVERAGE_CHANGE" };
      }
      // See this module's header: ECONOMIC alone is not enough.
      // `UNAVAILABLE -> x` is MacroChipz gaining the ability to
      // compute something, not the economy doing something.
      if (object.payload.previous_value === "UNAVAILABLE" || object.payload.previous_value === null) {
        return { eligible: false, reason: "FIRST_COMPUTATION_NOT_A_CHANGE" };
      }
      return { eligible: true };
    }

    case "OBSERVATION_CHANGE": {
      // A revision is a change. A first arrival is data appearing.
      if (object.payload.change_type === "REVISED") return { eligible: true };
      if (object.payload.previous_value === null) {
        return { eligible: false, reason: "FIRST_OBSERVATION_NOT_A_CHANGE" };
      }
      return { eligible: true };
    }

    case "RELEASE_PROCESSED":
      // "120 observations processed" is a fact about our pipeline, not
      // about the economy. Excluded from the consumer homepage in v1;
      // the Calendar surface is where release activity belongs.
      return { eligible: false, reason: "OPERATIONAL_NOT_ECONOMIC" };
  }
}

/**
 * Declared presentation preference WITHIN a world.
 *
 * Read this as an editorial choice, because that is all it is: when a
 * world publishes several objects for the same period, one has to go
 * first, and picking by magnitude would be inventing significance.
 * The 10-year Treasury leads the rates world because it is the most
 * widely referenced benchmark maturity — a fact about how people talk
 * about rates, not a claim that it moved more or matters more.
 *
 * A concept with no entry sorts last, alphabetically, which keeps the
 * order total without ever being arbitrary.
 */
const CONCEPT_PRESENTATION_ORDER: ReadonlyArray<string> = [
  "UST_NOMINAL_10Y",
  "UST_NOMINAL_2Y",
  "UST_NOMINAL_30Y",
  "UST_NOMINAL_5Y",
  "UST_REAL_10Y",
  "UST_REAL_5Y",
];

const WORLD_ORDER: ReadonlyArray<IntelligenceWorld> = ECONOMIC_WORLDS.map(
  (world) => world.analyticsWorld,
) as ReadonlyArray<IntelligenceWorld>;

function conceptRank(conceptId: string | undefined): number {
  if (conceptId === undefined) return CONCEPT_PRESENTATION_ORDER.length;
  const index = CONCEPT_PRESENTATION_ORDER.indexOf(conceptId);
  return index === -1 ? CONCEPT_PRESENTATION_ORDER.length : index;
}

function worldRank(world: IntelligenceWorld): number {
  const index = WORLD_ORDER.indexOf(world);
  return index === -1 ? WORLD_ORDER.length : index;
}

/**
 * The deterministic order, most-recently-dated first.
 *
 * Four keys, each a structural fact, applied in order:
 *
 *   1. `effective_period` DESC  — the period the data describes.
 *   2. world, in registry order — a declared order so ties resolve the
 *      same way every time. NOT a ranking of which world matters.
 *   3. concept presentation order — see above.
 *   4. object id ASC            — guarantees a TOTAL order, so the
 *                                 result can never depend on input
 *                                 order or sort stability.
 *
 * Deliberately absent: magnitude, percentile, "size of move",
 * recency-of-recording, and anything resembling a score.
 */
export function comparePresentation(a: IntelligenceObject, b: IntelligenceObject): number {
  if (a.effective_period !== b.effective_period) return a.effective_period < b.effective_period ? 1 : -1;

  const world = worldRank(a.world) - worldRank(b.world);
  if (world !== 0) return world;

  const concept = conceptRank(a.concepts[0]) - conceptRank(b.concepts[0]);
  if (concept !== 0) return concept;

  return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
}

export interface HomepageSelection {
  /** The single LEDE slot, or `null` for the quiet state. */
  lede: IntelligenceObject | null;
  /** Bounded recent intelligence, excluding whatever became the lede. */
  whatChanged: IntelligenceObject[];
  /** How many eligible objects existed before bounding. */
  eligibleCount: number;
  policy: string;
}

/** Hard ceiling on the homepage. It is an orientation surface, not a feed. */
export const WHAT_CHANGED_LIMIT = 4;

/**
 * Choose what the homepage shows.
 *
 * One object per CONCEPT: the six Treasury maturities all publish on
 * the same date, and six near-identical cards would be a feed of one
 * fact repeated. Collapsing by concept keeps the page readable without
 * deciding that any maturity matters more than another — every one of
 * them stays one click away in the Rates world.
 */
export function selectHomepage(objects: ReadonlyArray<IntelligenceObject>): HomepageSelection {
  const eligible = objects.filter((object) => eligibility(object).eligible).sort(comparePresentation);

  const seenConcept = new Set<string>();
  const deduped: IntelligenceObject[] = [];
  for (const object of eligible) {
    const concept = object.concepts[0] ?? object.id;
    if (seenConcept.has(concept)) continue;
    seenConcept.add(concept);
    deduped.push(object);
  }

  const [lede, ...rest] = deduped;

  return {
    lede: lede ?? null,
    whatChanged: rest.slice(0, WHAT_CHANGED_LIMIT),
    eligibleCount: eligible.length,
    policy: HOMEPAGE_PRESENTATION_POLICY,
  };
}

/** Narrowing helper: the lede can show a chart only for this type. */
export function isRatesMovement(object: IntelligenceObject): object is RatesMovementIntelligence {
  return object.type === "RATES_MOVEMENT";
}
