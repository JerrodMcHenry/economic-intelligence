/**
 * Content-coverage tests for the Labor Monitor's curated explanation
 * registry (Increment #20E.2), mirroring
 * content/explanations/inflation.test.ts's own discipline exactly:
 * check that every required concept exists, is well-formed, and --
 * for state explanations specifically -- matches the frozen
 * methodology's tables in substance (never re-deriving them, never
 * reproducing exact threshold numbers).
 */
import { describe, expect, it } from "vitest";

import type {
  EmploymentCondition,
  EmploymentMomentum,
  EmploymentState,
  LaborState,
  UnemploymentTrendState,
} from "../../api/labor.types";
import {
  EMPLOYMENT,
  EMPLOYMENT_CONDITION_CONCEPT,
  EMPLOYMENT_MOMENTUM_CONCEPT,
  employmentConditionExplanation,
  employmentMomentumExplanation,
  employmentStateExplanation,
  LABOR_MONITOR,
  laborStateExplanation,
  UNEMPLOYMENT,
  unemploymentTrendExplanation,
} from "./labor";

const LABOR_STATES: readonly LaborState[] = ["STRENGTHENING", "COOLING", "STABLE", "MIXED", "INSUFFICIENT_DATA"];
const EMPLOYMENT_STATES: readonly EmploymentState[] = ["EXPANDING", "COOLING", "STABLE", "CONTRACTING", "RECOVERING", "INSUFFICIENT_DATA"];
const EMPLOYMENT_CONDITIONS: readonly EmploymentCondition[] = ["EXPANDING", "FLAT", "CONTRACTING", "INSUFFICIENT_DATA"];
const EMPLOYMENT_MOMENTA: readonly EmploymentMomentum[] = ["IMPROVING", "STEADY", "WORSENING", "INSUFFICIENT_DATA"];
const UNEMPLOYMENT_STATES: readonly UnemploymentTrendState[] = ["IMPROVING", "DETERIORATING", "STABLE", "INSUFFICIENT_DATA"];

describe("labor explanation registry: well-formedness", () => {
  it.each([
    ["LABOR_MONITOR", LABOR_MONITOR],
    ["EMPLOYMENT", EMPLOYMENT],
    ["UNEMPLOYMENT", UNEMPLOYMENT],
    ["EMPLOYMENT_CONDITION_CONCEPT", EMPLOYMENT_CONDITION_CONCEPT],
    ["EMPLOYMENT_MOMENTUM_CONCEPT", EMPLOYMENT_MOMENTUM_CONCEPT],
  ])("%s has a stable id, a title, and a non-circular definition", (_name, explanation) => {
    expect(explanation.id.length).toBeGreaterThan(0);
    expect(explanation.title.length).toBeGreaterThan(0);
    expect(explanation.definition.length).toBeGreaterThan(0);
    expect(explanation.definition.toLowerCase()).not.toBe(explanation.title.toLowerCase());
  });

  it.each(LABOR_STATES)("provides a curated LaborState explanation for %s", (state) => {
    const explanation = laborStateExplanation(state);
    expect(explanation.title.length).toBeGreaterThan(0);
    expect(explanation.definition.length).toBeGreaterThan(0);
  });

  it.each(EMPLOYMENT_STATES)("provides a curated EmploymentState explanation for %s", (state) => {
    const explanation = employmentStateExplanation(state);
    expect(explanation.title.length).toBeGreaterThan(0);
    expect(explanation.definition.length).toBeGreaterThan(0);
  });

  it.each(EMPLOYMENT_CONDITIONS)("provides a curated EmploymentCondition explanation for %s", (condition) => {
    const explanation = employmentConditionExplanation(condition);
    expect(explanation.title.length).toBeGreaterThan(0);
    expect(explanation.definition.length).toBeGreaterThan(0);
  });

  it.each(EMPLOYMENT_MOMENTA)("provides a curated EmploymentMomentum explanation for %s", (momentum) => {
    const explanation = employmentMomentumExplanation(momentum);
    expect(explanation.title.length).toBeGreaterThan(0);
    expect(explanation.definition.length).toBeGreaterThan(0);
  });

  it.each(UNEMPLOYMENT_STATES)("provides a curated UnemploymentTrendState explanation for %s", (state) => {
    const explanation = unemploymentTrendExplanation(state);
    expect(explanation.title.length).toBeGreaterThan(0);
    expect(explanation.definition.length).toBeGreaterThan(0);
  });
});

describe("no exact threshold numbers leak into explanation content", () => {
  it("no explanation mentions the frozen 50,000-job or 0.2pp deadband values", () => {
    const all = [
      LABOR_MONITOR,
      EMPLOYMENT,
      UNEMPLOYMENT,
      EMPLOYMENT_CONDITION_CONCEPT,
      EMPLOYMENT_MOMENTUM_CONCEPT,
      ...LABOR_STATES.map(laborStateExplanation),
      ...EMPLOYMENT_STATES.map(employmentStateExplanation),
      ...EMPLOYMENT_CONDITIONS.map(employmentConditionExplanation),
      ...EMPLOYMENT_MOMENTA.map(employmentMomentumExplanation),
      ...UNEMPLOYMENT_STATES.map(unemploymentTrendExplanation),
    ];
    for (const explanation of all) {
      const combined = `${explanation.definition} ${explanation.whyItMatters ?? ""}`;
      expect(combined).not.toMatch(/50,000|50000/);
      expect(combined).not.toMatch(/0\.2\s*(percentage point|pp)/i);
    }
  });
});

describe("MIXED (grounded in the frozen agreement table)", () => {
  it("is described as a real, distinct classification, never as an error or missing-data condition", () => {
    const mixed = laborStateExplanation("MIXED");
    expect(mixed.whyItMatters).toMatch(/real, distinct classification/i);
    expect(mixed.whyItMatters).not.toMatch(/error|bug|missing data/i);
  });

  it("never reinterprets MIXED as neutral or uncertain", () => {
    const mixed = laborStateExplanation("MIXED");
    const combined = `${mixed.definition} ${mixed.whyItMatters ?? ""}`;
    expect(combined).not.toMatch(/\bneutral\b/i);
    expect(combined).not.toMatch(/\buncertain\b/i);
  });

  it("explicitly covers the RECOVERING-never-resolves-to-STRENGTHENING rule from the frozen agreement table", () => {
    const mixed = laborStateExplanation("MIXED");
    expect(`${mixed.definition} ${mixed.whyItMatters ?? ""}`).toMatch(/recovering/i);
  });
});

describe("RECOVERING (the exact August 2009 distinction)", () => {
  it("is described as still contracting, not genuine growth", () => {
    const recovering = employmentStateExplanation("RECOVERING");
    expect(recovering.whyItMatters ?? recovering.definition).toMatch(/still.*contracting|contracting.*still/i);
  });
});

describe("INSUFFICIENT_DATA (every enum)", () => {
  it.each([
    ["LaborState", laborStateExplanation("INSUFFICIENT_DATA")],
    ["EmploymentState", employmentStateExplanation("INSUFFICIENT_DATA")],
    ["EmploymentCondition", employmentConditionExplanation("INSUFFICIENT_DATA")],
    ["EmploymentMomentum", employmentMomentumExplanation("INSUFFICIENT_DATA")],
    ["UnemploymentTrendState", unemploymentTrendExplanation("INSUFFICIENT_DATA")],
  ])("%s's INSUFFICIENT_DATA explanation is a data-availability fact, not an economic direction", (_name, explanation) => {
    expect(explanation.definition).toMatch(/does not have/i);
  });
});

describe("no investment advice anywhere in the registry", () => {
  it("no explanation contains a trading/investment recommendation", () => {
    const all = [
      LABOR_MONITOR,
      EMPLOYMENT,
      UNEMPLOYMENT,
      ...LABOR_STATES.map(laborStateExplanation),
      ...EMPLOYMENT_STATES.map(employmentStateExplanation),
    ];
    for (const explanation of all) {
      const combined = `${explanation.definition} ${explanation.whyItMatters ?? ""}`;
      expect(combined).not.toMatch(/\bbuy\b|\bsell\b|you should|risk-on|risk-off|bullish|bearish/i);
    }
  });
});
