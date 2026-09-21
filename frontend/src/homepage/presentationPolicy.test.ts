/**
 * Homepage presentation policy (Increment #42).
 *
 * The policy decides what MacroChipz shows first. These tests hold the
 * line that it never decides what matters most: no score, no
 * randomness, no clock, and no route by which a coverage event or a
 * first-time backfill value can reach a consumer as "news".
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import type { IntelligenceObject } from "../api/intelligence.types";
import {
  HOMEPAGE_PRESENTATION_POLICY,
  WHAT_CHANGED_LIMIT,
  comparePresentation,
  eligibility,
  selectHomepage,
} from "./presentationPolicy";

const HERE = dirname(fileURLToPath(import.meta.url));

function base(overrides: Partial<IntelligenceObject> = {}) {
  return {
    id: "rates:UST_NOMINAL_10Y:2026-09-18",
    world: "rates",
    concepts: ["UST_NOMINAL_10Y"],
    effective_period: "2026-09-18",
    recorded_at: "2026-09-20T00:04:54.461189Z",
    published_at: null,
    knowledge_basis: "OBSERVED",
    basis: "METHODOLOGY_DERIVED",
    methodology: { methodology_id: "rates_v1.0", data_basis: "latest_published_data" },
    evidence: [],
    relations: [],
    limitations: [],
    contract_version: "intelligence_v1",
    ...overrides,
  };
}

function rates(overrides: Record<string, unknown> = {}): IntelligenceObject {
  return base({
    type: "RATES_MOVEMENT",
    payload: {
      series_title: "10-Year Treasury Par Yield (Nominal)",
      latest_value: 5.01,
      changes: [],
      historical_percentile_rank: null,
      historical_magnitude_percentile_rank: null,
      historical_observation_count: 0,
    },
    ...overrides,
  } as Partial<IntelligenceObject>) as IntelligenceObject;
}

function analysis(changeClass: string, previous: string | null): IntelligenceObject {
  return base({
    id: `analysis:${changeClass}:${previous}`,
    type: "ANALYSIS_CHANGE",
    world: "inflation",
    concepts: ["us.pce.core.price-index.sa.monthly"],
    payload: {
      component: "CONFIRMATION",
      event_type: "CONFIRMATION_CHANGED",
      change_class: changeClass,
      field: "relationship",
      previous_value: previous,
      current_value: "CONFIRMS",
      delta: null,
      evaluation_period: "2026-07-01",
    },
  } as Partial<IntelligenceObject>) as IntelligenceObject;
}

function observation(changeType: string, previous: number | null): IntelligenceObject {
  return base({
    id: `observation:${changeType}:${previous}`,
    type: "OBSERVATION_CHANGE",
    world: "jobs",
    concepts: ["us.unemployment-rate.sa.monthly"],
    payload: {
      series_title: "Unemployment Rate",
      provider_series_id: "UNRATE",
      change_type: changeType,
      previous_value: previous,
      new_value: 4.1,
      delta: null,
    },
  } as Partial<IntelligenceObject>) as IntelligenceObject;
}

describe("eligibility: what may reach the homepage", () => {
  it("admits a rates movement", () => {
    expect(eligibility(rates()).eligible).toBe(true);
  });

  it("excludes every COVERAGE change", () => {
    // 1,488 of the 1,899 local objects. Without this the homepage is
    // a list of "MacroChipz can now compute this".
    expect(eligibility(analysis("COVERAGE", "STABLE"))).toEqual({
      eligible: false,
      reason: "COVERAGE_CHANGE",
    });
  });

  it("excludes an ECONOMIC change that is only a first computation", () => {
    // THE FINDING THAT MATTERS: all 44 local ECONOMIC changes are
    // `UNAVAILABLE -> x`. `change_class` alone would let every one of
    // them onto the page as economic news.
    expect(eligibility(analysis("ECONOMIC", "UNAVAILABLE"))).toEqual({
      eligible: false,
      reason: "FIRST_COMPUTATION_NOT_A_CHANGE",
    });
    expect(eligibility(analysis("ECONOMIC", null)).eligible).toBe(false);
  });

  it("admits a genuine ECONOMIC transition between two known states", () => {
    expect(eligibility(analysis("ECONOMIC", "CONFIRMS")).eligible).toBe(true);
  });

  it("excludes a first observation but admits a revision", () => {
    expect(eligibility(observation("NEW", null))).toEqual({
      eligible: false,
      reason: "FIRST_OBSERVATION_NOT_A_CHANGE",
    });
    expect(eligibility(observation("REVISED", 4.0)).eligible).toBe(true);
  });

  it("excludes release processing as operational rather than economic", () => {
    const release = base({
      id: "release:CPI:2026-09-11",
      type: "RELEASE_PROCESSED",
      world: "inflation",
      payload: { release_name: "Consumer Price Index", observation_changes: 120, revised_observations: 0 },
    } as Partial<IntelligenceObject>) as IntelligenceObject;
    expect(eligibility(release)).toEqual({ eligible: false, reason: "OPERATIONAL_NOT_ECONOMIC" });
  });

  it("excludes an object with no concept", () => {
    expect(eligibility(rates({ concepts: [] })).reason).toBe("NO_CONCEPT");
  });
});

describe("ordering is deterministic and total", () => {
  it("puts the most recent effective period first", () => {
    const older = rates({ id: "a", effective_period: "2026-09-17" });
    const newer = rates({ id: "b", effective_period: "2026-09-18" });
    expect([older, newer].sort(comparePresentation)[0]).toBe(newer);
  });

  it("never depends on input order", () => {
    const objects = [
      rates({ id: "c", concepts: ["UST_NOMINAL_30Y"] }),
      rates({ id: "a", concepts: ["UST_NOMINAL_10Y"] }),
      rates({ id: "b", concepts: ["UST_NOMINAL_2Y"] }),
    ];
    const forward = [...objects].sort(comparePresentation).map((object) => object.id);
    const backward = [...objects].reverse().sort(comparePresentation).map((object) => object.id);
    expect(forward).toEqual(backward);
  });

  it("breaks a complete tie by id, so the order is total", () => {
    const first = rates({ id: "aaa", concepts: ["X"] });
    const second = rates({ id: "bbb", concepts: ["X"] });
    expect(comparePresentation(first, second)).toBeLessThan(0);
    expect(comparePresentation(second, first)).toBeGreaterThan(0);
    expect(comparePresentation(first, first)).toBe(0);
  });

  it("produces the same page on repeated runs", () => {
    const objects = [rates({ id: "a" }), rates({ id: "b", concepts: ["UST_NOMINAL_2Y"] })];
    expect(selectHomepage(objects)).toEqual(selectHomepage(objects));
  });
});

describe("selection", () => {
  const six = ["UST_NOMINAL_10Y", "UST_NOMINAL_2Y", "UST_NOMINAL_30Y", "UST_NOMINAL_5Y", "UST_REAL_10Y", "UST_REAL_5Y"].map(
    (concept) => rates({ id: `rates:${concept}:2026-09-18`, concepts: [concept] }),
  );

  it("leads with the declared benchmark maturity", () => {
    // A presentation preference, not a claim that it moved most.
    expect(selectHomepage(six).lede?.concepts[0]).toBe("UST_NOMINAL_10Y");
  });

  it("bounds What Changed and never repeats the lede", () => {
    const selection = selectHomepage(six);
    expect(selection.whatChanged.length).toBeLessThanOrEqual(WHAT_CHANGED_LIMIT);
    expect(selection.whatChanged).not.toContainEqual(selection.lede);
  });

  it("shows one object per concept rather than the same fact repeated", () => {
    const duplicated = [...six, ...six];
    const selection = selectHomepage(duplicated);
    const concepts = [selection.lede, ...selection.whatChanged].map((object) => object?.concepts[0]);
    expect(new Set(concepts).size).toBe(concepts.length);
  });

  it("is quiet when nothing qualifies, rather than falling back to noise", () => {
    const noise = [analysis("COVERAGE", "STABLE"), analysis("ECONOMIC", "UNAVAILABLE"), observation("NEW", null)];
    const selection = selectHomepage(noise);
    expect(selection.lede).toBeNull();
    expect(selection.whatChanged).toEqual([]);
    expect(selection.eligibleCount).toBe(0);
  });

  it("is quiet for an empty input", () => {
    expect(selectHomepage([]).lede).toBeNull();
  });

  it("reports the policy version it applied", () => {
    expect(selectHomepage([]).policy).toBe(HOMEPAGE_PRESENTATION_POLICY);
    expect(HOMEPAGE_PRESENTATION_POLICY).toMatch(/^homepage_presentation_v\d+\.\d+$/);
  });
});

describe("the policy is a presentation policy, not a methodology", () => {
  const source = readFileSync(join(HERE, "presentationPolicy.ts"), "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "");

  it("computes no score, weight or ranking number", () => {
    for (const token of ["score", "weight", "importance", "priority", "significance", "severity"]) {
      expect(source.toLowerCase(), token).not.toContain(token);
    }
  });

  it("uses no randomness", () => {
    expect(source).not.toContain("Math.random");
  });

  it("reads no clock, so a prerendered page cannot go quietly stale", () => {
    for (const token of ["Date.now", "new Date", "Date(", "performance.now"]) {
      expect(source, token).not.toContain(token);
    }
  });

  it("infers nothing from the size of a move", () => {
    for (const token of ["change_basis_points", "percentile", "magnitude", "Math.abs", "Math.max", "delta"]) {
      expect(source, token).not.toContain(token);
    }
  });

  it("calls no model and no provider", () => {
    for (const token of ["openai", "anthropic", "fetch(", "axios"]) {
      expect(source.toLowerCase(), token).not.toContain(token.toLowerCase());
    }
  });

  it("derives no economic conclusion of its own", () => {
    // It may read `change_class` and `previous_value`; it may not
    // compute what they should have been.
    expect(source).not.toMatch(/change_class\s*=\s*["'`]/);
    expect(source).not.toMatch(/state\s*=\s*["'`](COOLING|HEATING|STABLE|MIXED)/);
  });
});
