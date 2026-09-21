/**
 * Consumer language for Structured Intelligence (Increment #40,
 * consumer pass in #40B).
 *
 * #39's taxonomy is machine vocabulary: `RATES_MOVEMENT`,
 * `METHODOLOGY_DERIVED`, `OBSERVED`. It is precise and it is canonical,
 * and a reader arriving from a text message should never have to see
 * it. This module maps that vocabulary to plain English.
 *
 * THE MAPPING IS PRESENTATION, NOT CANON. Three rules keep it honest:
 *
 * 1. **Deterministic, total mappings only.** Lookup tables and
 *    templates over structured facts -- no model, no heuristics, no
 *    inference. The same object always produces the same words.
 * 2. **It never changes meaning.** "Treasury yield movement" is what
 *    `RATES_MOVEMENT` means; it is a translation, not a reinterpretation.
 * 3. **It never becomes canonical.** Nothing here is written back, and
 *    no other module derives a fact from these strings. The machine
 *    taxonomy remains the source of truth.
 *
 * This is deliberately not a CMS, and it does not duplicate the 34
 * curated `Explanation` entries in `src/content/explanations/` -- those
 * explain economic CONCEPTS and are reused as-is where a term needs
 * defining.
 */
import type { ChangeClass, IntelligenceObject, IntelligenceType, IntelligenceWorld } from "../api/intelligence.types";

const WORLD_LABELS: Record<IntelligenceWorld, string> = {
  inflation: "Inflation",
  jobs: "Jobs",
  rates: "Rates",
};

const TYPE_LABELS: Record<IntelligenceType, string> = {
  RELEASE_PROCESSED: "Economic release processed",
  OBSERVATION_CHANGE: "New data point",
  ANALYSIS_CHANGE: "Methodology conclusion changed",
  RATES_MOVEMENT: "Treasury yield movement",
};

/** How a session-counted window reads to someone who is not a trader. */
const WINDOW_LABELS: Record<string, string> = {
  "1_SESSION": "1 trading session",
  "5_SESSIONS": "5 trading sessions",
  "21_SESSIONS": "21 trading sessions",
  "63_SESSIONS": "63 trading sessions",
};

export function worldLabel(world: IntelligenceWorld): string {
  return WORLD_LABELS[world];
}

export function typeLabel(type: IntelligenceType): string {
  return TYPE_LABELS[type];
}

export function windowLabel(window: string): string {
  return WINDOW_LABELS[window] ?? window;
}

/**
 * Where a claim comes from, in words a reader can act on.
 *
 * The distinction matters to a reader, not just to the system: one is
 * "a source published this", the other is "MacroChipz concluded this".
 */
export function basisLabel(object: IntelligenceObject): string {
  return object.basis === "SOURCE_FACT"
    ? "Reported by the source"
    : `Calculated by MacroChipz${object.methodology ? ` (${object.methodology.methodology_id})` : ""}`;
}

/** Whether MacroChipz genuinely recorded this, said plainly. */
export function knowledgeLabel(object: IntelligenceObject): string {
  return object.knowledge_basis === "OBSERVED"
    ? "MacroChipz recorded this directly"
    : "Reconstructed from later data, not recorded at the time";
}

export function changeClassLabel(changeClass: ChangeClass): string {
  return changeClass === "ECONOMIC"
    ? "A change in the economy"
    : "A change in what MacroChipz can measure, not in the economy";
}

/** A signed basis-point figure, e.g. `+33 bp` / `−7 bp`. */
export function formatBasisPoints(value: number | null): string | null {
  if (value === null) return null;
  const rounded = Math.round(value);
  if (rounded === 0) return "unchanged";
  return `${rounded > 0 ? "+" : "−"}${Math.abs(rounded)} bp`;
}

/**
 * Short, plain-English names for the economic concepts a permanent
 * object can be about (#40B).
 *
 * `payload.series_title` is the provider-faithful name --
 * "10-Year Treasury Par Yield (Nominal)" -- and it stays visible in
 * "Check this", where precision matters. It is the wrong first thing
 * for a reader arriving from a text message, who needs to know what
 * they are looking at before they need to know how Treasury words it.
 *
 * Curated, total over the concepts MacroChipz tracks, and falling back
 * to the provider title rather than to a guess.
 */
const CONCEPT_SHORT_NAMES: Record<string, string> = {
  UST_NOMINAL_2Y: "2-year Treasury yield",
  UST_NOMINAL_5Y: "5-year Treasury yield",
  UST_NOMINAL_10Y: "10-year Treasury yield",
  UST_NOMINAL_30Y: "30-year Treasury yield",
  UST_REAL_5Y: "5-year inflation-adjusted Treasury yield",
  UST_REAL_10Y: "10-year inflation-adjusted Treasury yield",
};

/**
 * The consumer headline name, e.g. "10-year Treasury yield".
 *
 * Falls back to the provider's own title when a concept has no curated
 * short name, which is honest rather than clever: an unlabelled concept
 * gets the precise name instead of an invented friendly one.
 */
export function conceptShortName(conceptId: string | undefined, fallback: string): string {
  if (conceptId === undefined) return fallback;
  return CONCEPT_SHORT_NAMES[conceptId] ?? fallback;
}

/**
 * A movement in PERCENTAGE POINTS, e.g. `+0.05 percentage points`.
 *
 * Basis points are the canonical unit and remain so -- this converts
 * for display only, exactly as `5.01` is displayed as `5.01%`. One
 * basis point is one hundredth of a percentage point; that is a unit
 * definition, not an economic derivation, and the underlying
 * `change_basis_points` is never modified.
 *
 * Two decimal places, because one basis point is 0.01 points and
 * rounding further would make a real move read as "unchanged".
 */
export function formatPercentagePoints(basisPoints: number | null): string | null {
  if (basisPoints === null) return null;
  const points = basisPoints / 100;
  if (Math.abs(basisPoints) < 0.5) return "unchanged";
  return `${points > 0 ? "+" : "−"}${Math.abs(points).toFixed(2)} percentage points`;
}

/**
 * How a session window reads inside a sentence, e.g. "the last 5
 * trading days".
 *
 * "Trading days" rather than "sessions": a session IS a trading day,
 * and one of these words needs explaining to a general reader while
 * the other does not. The distinction the methodology actually cares
 * about -- trading days are not calendar days -- is preserved, and
 * stated outright beneath the figures.
 */
export function windowConsumerLabel(sessions: number): string {
  return sessions === 1 ? "the last trading day" : `the last ${sessions} trading days`;
}

/**
 * Which change window leads the page.
 *
 * Deterministic and documented, because "the headline move" is a
 * presentation choice and must not look like a judgement: prefer the
 * 5-session window -- about one trading week, and the same window
 * `rates_v1.0` ranks its historical context against, so the headline
 * and the "is this unusual?" answer describe the SAME move -- and fall
 * back to the shortest window actually available.
 *
 * Returns `null` when the object carries no usable change at all.
 */
export function headlineChange<T extends { window: string; sessions: number; available: boolean }>(
  changes: ReadonlyArray<T>,
): T | null {
  const available = changes.filter((change) => change.available);
  if (available.length === 0) return null;
  const preferred = available.find((change) => change.window === "5_SESSIONS");
  if (preferred) return preferred;
  return available.reduce((shortest, change) => (change.sessions < shortest.sessions ? change : shortest));
}

/**
 * A stored 0-1 rank written as a percentage, e.g. `57%`.
 *
 * Used in the sentence "larger than 57% of them", which is what the
 * rank actually means: the share of the prior population this value
 * exceeds. The older phrasing "sits at the 57th percentile" is more
 * compact and is reliably misread as a statement about the LEVEL and
 * about long-run history; #40B says the longer thing instead.
 *
 * Writing a stored rank as a percentage is a unit label, not a
 * derivation -- the object carries the rank and presentation only
 * chooses how to write it.
 */
export function rankPercent(rank: number): string {
  return `${Math.round(rank * 100)}%`;
}

/** Direction as a WORD, never colour alone -- see the accessibility rules. */
export function directionWord(value: number | null): "up" | "down" | "unchanged" | null {
  if (value === null) return null;
  if (Math.round(value) === 0) return "unchanged";
  return value > 0 ? "up" : "down";
}

/**
 * The page's headline: what happened, in one sentence.
 *
 * Built from structured facts by template. Every number comes straight
 * off the object; nothing is derived here.
 */
export function headline(object: IntelligenceObject): string {
  switch (object.type) {
    case "RATES_MOVEMENT": {
      const value = object.payload.latest_value;
      return value === null
        ? `${object.payload.series_title}`
        : `${object.payload.series_title} is ${value.toFixed(2)}%`;
    }
    case "OBSERVATION_CHANGE": {
      const name = object.payload.series_title ?? object.payload.provider_series_id;
      return object.payload.change_type === "REVISED"
        ? `${name} was revised`
        : `New ${name} data`;
    }
    case "ANALYSIS_CHANGE":
      return `${object.payload.component.replace(/_/g, " ").toLowerCase()} — ${object.payload.field.replace(/_/g, " ")}`;
    case "RELEASE_PROCESSED":
      return `${object.payload.release_name} processed`;
  }
}

/**
 * One sentence of context. Deliberately narrow: where MacroChipz cannot
 * deterministically support "why this matters", it says what the object
 * IS rather than inventing a reason. No causal claims are made here,
 * and none can be -- there is no input to this function that carries
 * causation.
 */
export function summary(object: IntelligenceObject): string {
  switch (object.type) {
    case "RATES_MOVEMENT": {
      const twentyOne = object.payload.changes.find((change) => change.window === "21_SESSIONS");
      const move = twentyOne && twentyOne.available ? formatBasisPoints(twentyOne.change_basis_points) : null;
      const base = `The latest published yield for this Treasury maturity, with how far it has moved over MacroChipz's four tracked windows.`;
      return move && move !== "unchanged"
        ? `${base} Over 21 trading sessions it is ${move}.`
        : base;
    }
    case "OBSERVATION_CHANGE":
      return object.payload.change_type === "REVISED"
        ? "The provider published a different value for a period it had already reported. MacroChipz keeps both."
        : "A value for a new period arrived from the provider and was recorded.";
    case "ANALYSIS_CHANGE":
      return object.payload.change_class === "ECONOMIC"
        ? "A MacroChipz methodology reached a different conclusion than it did for the previous period."
        : "MacroChipz gained or lost the ability to compute this. The economy did not necessarily change.";
    case "RELEASE_PROCESSED":
      return "MacroChipz checked this scheduled release and processed whatever data had arrived.";
  }
}
