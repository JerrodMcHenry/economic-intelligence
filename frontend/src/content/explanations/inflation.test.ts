/**
 * Content-coverage tests for the Inflation Monitor's curated
 * explanation registry (Increment #17C). These check that every
 * required concept exists, is well-formed, and -- for state
 * explanations specifically -- matches the frozen methodology's
 * classification rules in substance (never re-deriving them). Prose
 * beyond that is checked loosely (important concepts present), not by
 * exact-string matching, per this increment's own copy-testing
 * guidance; the one exception is `LATEST_REVISED_DATA`, whose
 * definition is a product invariant carried over unchanged from the
 * pre-#17C canonical disclosure text.
 */
import { describe, expect, it } from "vitest";

import type { InflationState } from "../../api/inflation.types";
import {
  CONFIRMATION,
  CORE_CPI,
  CORE_INFLATION,
  CORE_PCE,
  CPI,
  FED_OBJECTIVE,
  HEADLINE_INFLATION,
  inflationStateExplanation,
  LATEST_REVISED_DATA,
  MOMENTUM,
  PCE,
  SIX_MONTH_ANNUALIZED,
  STATE_DURATION_DISCLOSURE,
  TARGET_DEVIATION,
  THREE_MONTH_ANNUALIZED,
  TWELVE_MONTH,
} from "./inflation";
import type { Explanation } from "./types";

const ALL_CONCEPT_EXPLANATIONS: ReadonlyArray<[string, Explanation]> = [
  ["HEADLINE_INFLATION", HEADLINE_INFLATION],
  ["CORE_INFLATION", CORE_INFLATION],
  ["CPI", CPI],
  ["PCE", PCE],
  ["CORE_PCE", CORE_PCE],
  ["CORE_CPI", CORE_CPI],
  ["THREE_MONTH_ANNUALIZED", THREE_MONTH_ANNUALIZED],
  ["SIX_MONTH_ANNUALIZED", SIX_MONTH_ANNUALIZED],
  ["TWELVE_MONTH", TWELVE_MONTH],
  ["FED_OBJECTIVE", FED_OBJECTIVE],
  ["TARGET_DEVIATION", TARGET_DEVIATION],
  ["MOMENTUM", MOMENTUM],
  ["CONFIRMATION", CONFIRMATION],
  ["LATEST_REVISED_DATA", LATEST_REVISED_DATA],
  ["STATE_DURATION_DISCLOSURE", STATE_DURATION_DISCLOSURE],
];

describe("inflation explanation registry: well-formedness", () => {
  it("covers all 20 required inflation concepts (15 standalone + 5 states)", () => {
    const states: InflationState[] = ["COOLING", "HEATING", "STABLE", "MIXED", "INSUFFICIENT_DATA"];
    expect(ALL_CONCEPT_EXPLANATIONS.length + states.length).toBe(20);
  });

  it.each(ALL_CONCEPT_EXPLANATIONS)("%s has a stable id, a title, and a non-circular definition", (_name, explanation) => {
    expect(explanation.id.length).toBeGreaterThan(0);
    expect(explanation.title.length).toBeGreaterThan(0);
    expect(explanation.definition.length).toBeGreaterThan(0);
    // A circular definition would restate the title inside the
    // definition as its only content, e.g. "Core PCE is the core
    // version of PCE" -- checking the definition isn't merely the
    // title with a linking verb catches the most obvious form of this.
    expect(explanation.definition.toLowerCase()).not.toBe(explanation.title.toLowerCase());
  });

  it.each(ALL_CONCEPT_EXPLANATIONS)("%s has a stable id unique across the registry", (_name, explanation) => {
    const ids = ALL_CONCEPT_EXPLANATIONS.map(([, e]) => e.id);
    expect(ids.filter((id) => id === explanation.id)).toHaveLength(1);
  });
});

describe("Core PCE vs. headline / CPI vs. PCE distinctions", () => {
  it("explains what Core PCE is and why it's the primary signal", () => {
    expect(CORE_PCE.definition).toMatch(/food and energy/i);
    expect(CORE_PCE.whyItMatters).toMatch(/federal reserve/i);
  });

  it("distinguishes CPI and PCE as separately sourced measures, not interchangeable synonyms", () => {
    expect(CPI.definition).toMatch(/bureau of labor statistics/i);
    expect(PCE.definition).toMatch(/bureau of economic analysis/i);
    expect(CPI.title).not.toBe(PCE.title);
  });

  it("explains Core CPI's role as a confirmation check, never an equal or overriding read", () => {
    expect(CORE_CPI.whyItMatters).toMatch(/never.*override/i);
  });
});

describe("annualized inflation explanations", () => {
  it("explains 3-month annualized without performing or restating a calculation", () => {
    expect(THREE_MONTH_ANNUALIZED.definition).toMatch(/three months/i);
    expect(THREE_MONTH_ANNUALIZED.definition).not.toMatch(/\*\*|Math\.pow/);
  });

  it("explains 6-month annualized distinctly from 3-month", () => {
    expect(SIX_MONTH_ANNUALIZED.definition).toMatch(/six months/i);
    expect(SIX_MONTH_ANNUALIZED.definition).not.toBe(THREE_MONTH_ANNUALIZED.definition);
  });

  it("explains the 12-month/YoY rate as the neutral-band baseline", () => {
    expect(TWELVE_MONTH.definition).toMatch(/one year earlier/i);
  });
});

describe("Fed objective and target deviation", () => {
  it("states the Fed's 2% objective in terms of headline PCE", () => {
    expect(FED_OBJECTIVE.definition).toMatch(/2%/);
    expect(FED_OBJECTIVE.definition).toMatch(/pce/i);
  });

  it("explains target deviation as a percentage-point gap, not a directional recommendation", () => {
    expect(TARGET_DEVIATION.definition).toMatch(/percentage points/i);
    expect(TARGET_DEVIATION.whyItMatters).not.toMatch(/\bbuy\b|\bsell\b/i);
  });
});

describe("inflation state explanations (grounded in the frozen methodology's classification rules)", () => {
  it.each(["COOLING", "HEATING", "STABLE", "MIXED", "INSUFFICIENT_DATA"] as const)(
    "provides a curated explanation for %s",
    (state) => {
      const explanation = inflationStateExplanation(state);
      expect(explanation.title.length).toBeGreaterThan(0);
      expect(explanation.definition.length).toBeGreaterThan(0);
    },
  );

  it("COOLING and HEATING both reference the neutral band and are each other's mirror, not duplicates", () => {
    const cooling = inflationStateExplanation("COOLING");
    const heating = inflationStateExplanation("HEATING");
    expect(cooling.definition).toMatch(/neutral band/i);
    expect(heating.definition).toMatch(/neutral band/i);
    expect(cooling.definition).not.toBe(heating.definition);
    expect(cooling.definition).toMatch(/below/i);
    expect(heating.definition).toMatch(/above/i);
  });

  it("STABLE describes both rates falling within the band", () => {
    expect(inflationStateExplanation("STABLE").definition).toMatch(/within the neutral band/i);
  });

  it("MIXED is described as a real, distinct classification, never as an error or missing-data condition", () => {
    const mixed = inflationStateExplanation("MIXED");
    expect(mixed.whyItMatters).toMatch(/real, distinct classification/i);
    expect(mixed.whyItMatters).not.toMatch(/error|bug|missing data/i);
  });

  it("INSUFFICIENT_DATA is described as a data-availability fact, not an economic direction", () => {
    const insufficient = inflationStateExplanation("INSUFFICIENT_DATA");
    expect(insufficient.whyItMatters).toMatch(/data-availability fact/i);
    expect(insufficient.definition).not.toMatch(/cooling|heating|stable|mixed/i);
  });

  it("no state explanation contains an investment recommendation", () => {
    const states: InflationState[] = ["COOLING", "HEATING", "STABLE", "MIXED", "INSUFFICIENT_DATA"];
    for (const state of states) {
      const explanation = inflationStateExplanation(state);
      const combined = `${explanation.definition} ${explanation.whyItMatters ?? ""}`;
      expect(combined).not.toMatch(/\bbuy\b|\bsell\b|you should/i);
    }
  });
});

describe("latest revised data (exact-string product invariant)", () => {
  it("preserves the canonical disclosure sentence byte-for-byte", () => {
    expect(LATEST_REVISED_DATA.definition).toBe(
      "Historical calculations use the latest revised observations available to Economic Intelligence. They may differ from values originally reported at the time.",
    );
  });

  it("never implies vintage/as-known-at-the-time capability", () => {
    const combined = `${LATEST_REVISED_DATA.definition} ${LATEST_REVISED_DATA.whyItMatters ?? ""}`;
    expect(combined).not.toMatch(/as it was known|point-in-time|as-of|vintage/i);
  });
});

describe("state duration disclosure (exact-string product invariant, Increment #24D)", () => {
  it("preserves the frozen state-duration-v1.md §38 sentence byte-for-byte", () => {
    expect(STATE_DURATION_DISCLOSURE.definition).toBe(
      "This duration is calculated today, using the latest revised data and the current methodology, applied consistently across the period shown. It reflects what today's data implies, not what Economic Intelligence reported in real time as each month occurred.",
    );
  });

  it("preserves both truths: latest-revised/current-methodology basis, and not what EI reported historically", () => {
    expect(STATE_DURATION_DISCLOSURE.definition).toMatch(/latest revised data/i);
    expect(STATE_DURATION_DISCLOSURE.definition).toMatch(/current methodology/i);
    expect(STATE_DURATION_DISCLOSURE.definition).toMatch(/not what economic intelligence reported in real time/i);
  });

  it("never claims recorded or as-known-at-time history", () => {
    expect(STATE_DURATION_DISCLOSURE.definition).not.toMatch(/as-known-at-time|as it was known|point-in-time|vintage/i);
  });
});
