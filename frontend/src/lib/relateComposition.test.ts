import { describe, expect, it } from "vitest";

import type { InflationState } from "../api/inflation.types";
import type { EmploymentState, LaborState, UnemploymentTrendState } from "../api/labor.types";
import { composeLaborComponents, composeMonitorRelation } from "./relateComposition";

const ALL_INFLATION_STATES: InflationState[] = ["COOLING", "HEATING", "STABLE", "MIXED", "INSUFFICIENT_DATA"];
const ALL_LABOR_STATES: LaborState[] = ["STRENGTHENING", "COOLING", "STABLE", "MIXED", "INSUFFICIENT_DATA"];
const ALL_EMPLOYMENT_STATES: EmploymentState[] = ["EXPANDING", "COOLING", "STABLE", "CONTRACTING", "RECOVERING", "INSUFFICIENT_DATA"];
const ALL_UNEMPLOYMENT_STATES: UnemploymentTrendState[] = ["IMPROVING", "DETERIORATING", "STABLE", "INSUFFICIENT_DATA"];

// The absolute prohibited-vocabulary list, frozen by
// docs/product/relate-composition-v1.md §2/§21 -- must never appear in
// any composed output, under any state combination.
const PROHIBITED = [
  /agrees?/i,
  /agreement/i,
  /confirms?/i,
  /confirmation/i,
  /diverges?/i,
  /divergence/i,
  /contradicts?/i,
  /contradiction/i,
  /goldilocks/i,
  /soft landing/i,
  /hard landing/i,
  /stagflation/i,
  /recessionary/i,
  /expansionary/i,
  /risk-on/i,
  /risk-off/i,
  /bullish/i,
  /bearish/i,
  /healthy economy/i,
  /favorable environment/i,
  /the economy is/i,
];

function expectNoProhibitedVocabulary(sentence: string) {
  for (const pattern of PROHIBITED) {
    expect(sentence, `"${sentence}" matched prohibited pattern ${pattern}`).not.toMatch(pattern);
  }
}

describe("composeMonitorRelation -- same period (§7)", () => {
  it("uses the exact frozen template with 'while', one shared period", () => {
    const result = composeMonitorRelation(
      { state: "COOLING", period: "2026-07-01" },
      { state: "STRENGTHENING", period: "2026-07-01" },
    );
    expect(result).toEqual({
      kind: "same-period",
      sentence: "As of July 2026, Inflation is Cooling while Jobs is Strengthening.",
    });
  });

  it("is deterministic -- identical inputs produce identical output", () => {
    const a = composeMonitorRelation({ state: "MIXED", period: "2026-01-01" }, { state: "STABLE", period: "2026-01-01" });
    const b = composeMonitorRelation({ state: "MIXED", period: "2026-01-01" }, { state: "STABLE", period: "2026-01-01" });
    expect(a).toEqual(b);
  });
});

describe("composeMonitorRelation -- different period (§8)", () => {
  it("uses the exact frozen template, two sentences, both periods explicit", () => {
    const result = composeMonitorRelation(
      { state: "COOLING", period: "2026-07-01" },
      { state: "STRENGTHENING", period: "2026-08-01" },
    );
    expect(result).toEqual({
      kind: "different-period",
      sentence: "Inflation is Cooling as of July 2026. Jobs is Strengthening as of August 2026.",
    });
  });

  it("never uses 'while', 'together', 'currently', 'at the same time', or 'simultaneously' when periods differ", () => {
    const result = composeMonitorRelation(
      { state: "HEATING", period: "2026-03-01" },
      { state: "COOLING", period: "2026-05-01" },
    );
    for (const forbidden of [/\bwhile\b/i, /\btogether\b/i, /\bcurrently\b/i, /at the same time/i, /simultaneously/i]) {
      expect(result.sentence).not.toMatch(forbidden);
    }
  });

  it("both periods are visible in the rendered sentence", () => {
    const result = composeMonitorRelation(
      { state: "STABLE", period: "2026-02-01" },
      { state: "MIXED", period: "2026-06-01" },
    );
    expect(result.sentence).toContain("February 2026");
    expect(result.sentence).toContain("June 2026");
  });
});

describe("composeMonitorRelation -- insufficient data (§9)", () => {
  it("Inflation insufficient, Labor sufficient -> Labor's own fact first, then the unavailable fragment, no relationship word", () => {
    const result = composeMonitorRelation(
      { state: "INSUFFICIENT_DATA", period: null },
      { state: "COOLING", period: "2026-07-01" },
    );
    expect(result).toEqual({
      kind: "inflation-insufficient",
      sentence: "Jobs is Cooling as of July 2026. Inflation does not currently have enough data to classify its state.",
    });
  });

  it("Labor insufficient, Inflation sufficient -> mirror", () => {
    const result = composeMonitorRelation(
      { state: "HEATING", period: "2026-07-01" },
      { state: "INSUFFICIENT_DATA", period: null },
    );
    expect(result).toEqual({
      kind: "labor-insufficient",
      sentence: "Inflation is Heating as of July 2026. Jobs does not currently have enough data to classify its state.",
    });
  });

  it("both insufficient -> one combined statement, no per-side fragments", () => {
    const result = composeMonitorRelation(
      { state: "INSUFFICIENT_DATA", period: null },
      { state: "INSUFFICIENT_DATA", period: null },
    );
    expect(result).toEqual({
      kind: "both-insufficient",
      sentence: "Not enough data is currently available to describe how Inflation and Jobs relate.",
    });
  });

  it("treats a null period as insufficient even if state is not literally INSUFFICIENT_DATA (defensive, §9)", () => {
    const result = composeMonitorRelation({ state: "COOLING", period: null }, { state: "STABLE", period: "2026-07-01" });
    expect(result.kind).toBe("inflation-insufficient");
  });

  it("never uses 'stable', 'mixed', or 'unknown economic conditions' to describe insufficiency", () => {
    const result = composeMonitorRelation(
      { state: "INSUFFICIENT_DATA", period: null },
      { state: "INSUFFICIENT_DATA", period: null },
    );
    expect(result.sentence).not.toMatch(/\bstable\b/i);
    expect(result.sentence).not.toMatch(/\bmixed\b/i);
    expect(result.sentence).not.toMatch(/unknown economic conditions/i);
  });
});

describe("composeMonitorRelation -- all canonical states accepted, exact existing labels used", () => {
  it.each(ALL_INFLATION_STATES)("Inflation state %s renders its exact existing label, never a raw enum string", (state) => {
    const result = composeMonitorRelation({ state, period: "2026-07-01" }, { state: "STABLE", period: "2026-07-01" });
    if (state === "INSUFFICIENT_DATA") {
      expect(result.kind).toBe("inflation-insufficient");
      return;
    }
    expect(result.sentence).not.toContain(state); // raw enum string never appears
  });

  it.each(ALL_LABOR_STATES)("Labor state %s renders its exact existing label, never a raw enum string", (state) => {
    const result = composeMonitorRelation({ state: "STABLE", period: "2026-07-01" }, { state, period: "2026-07-01" });
    if (state === "INSUFFICIENT_DATA") {
      expect(result.kind).toBe("labor-insufficient");
      return;
    }
    expect(result.sentence).not.toContain(state);
  });
});

describe("composeMonitorRelation -- no new economic conclusion, no prohibited vocabulary", () => {
  it.each(ALL_INFLATION_STATES.flatMap((i) => ALL_LABOR_STATES.map((l) => [i, l] as const)))(
    "Inflation=%s, Labor=%s never contains prohibited cross-domain/regime vocabulary",
    (inflationState, laborState) => {
      const same = composeMonitorRelation({ state: inflationState, period: "2026-07-01" }, { state: laborState, period: "2026-07-01" });
      expectNoProhibitedVocabulary(same.sentence);
      const different = composeMonitorRelation({ state: inflationState, period: "2026-07-01" }, { state: laborState, period: "2026-08-01" });
      expectNoProhibitedVocabulary(different.sentence);
    },
  );
});

describe("composeLaborComponents -- composed (§18/§19)", () => {
  it("uses the exact frozen template, including the LaborState connection clause", () => {
    const result = composeLaborComponents("COOLING", "DETERIORATING", "COOLING");
    expect(result).toEqual({
      kind: "composed",
      sentence: "Employment is Cooling and Unemployment is Deteriorating. Together, MacroChipz classifies Jobs as Cooling.",
    });
  });

  it("LaborState is consumed as a plain input, never recomputed -- passing a value inconsistent with combine_labor_state's own table still reports exactly what was passed", () => {
    // This function has no combination logic of its own (§20) -- it must
    // report whatever laborState it is given, verbatim, proving it never
    // re-derives the value from employment/unemployment itself.
    const result = composeLaborComponents("EXPANDING", "IMPROVING", "MIXED");
    expect(result.kind).toBe("composed");
    expect(result.sentence).toContain("classifies Jobs as Mixed");
  });

  it("is deterministic -- identical inputs produce identical output", () => {
    const a = composeLaborComponents("STABLE", "STABLE", "STABLE");
    const b = composeLaborComponents("STABLE", "STABLE", "STABLE");
    expect(a).toEqual(b);
  });
});

describe("composeLaborComponents -- insufficient data (§21)", () => {
  it("Employment insufficient -> no composition, dedicated fragment, regardless of Unemployment", () => {
    const result = composeLaborComponents("INSUFFICIENT_DATA", "DETERIORATING", "INSUFFICIENT_DATA");
    expect(result).toEqual({
      kind: "employment-insufficient",
      sentence: "Employment does not currently have enough data to classify its state.",
    });
  });

  it("Unemployment insufficient (Employment sufficient) -> dedicated fragment", () => {
    const result = composeLaborComponents("COOLING", "INSUFFICIENT_DATA", "INSUFFICIENT_DATA");
    expect(result).toEqual({
      kind: "unemployment-insufficient",
      sentence: "Unemployment does not currently have enough data to classify its state.",
    });
  });

  it("Employment insufficient takes precedence over Unemployment also being insufficient (frozen ordering, §21)", () => {
    const result = composeLaborComponents("INSUFFICIENT_DATA", "INSUFFICIENT_DATA", "INSUFFICIENT_DATA");
    expect(result.kind).toBe("employment-insufficient");
  });

  it("no LaborState connection clause is produced when either component is insufficient", () => {
    const result = composeLaborComponents("INSUFFICIENT_DATA", "STABLE", "INSUFFICIENT_DATA");
    expect(result.sentence).not.toMatch(/classifies Jobs as/i);
  });
});

describe("composeLaborComponents -- all canonical states accepted, exact existing labels used", () => {
  it.each(ALL_EMPLOYMENT_STATES)("Employment state %s renders its exact existing label, never a raw enum string", (state) => {
    const result = composeLaborComponents(state, "STABLE", state === "INSUFFICIENT_DATA" ? "INSUFFICIENT_DATA" : "STABLE");
    if (state === "INSUFFICIENT_DATA") {
      expect(result.kind).toBe("employment-insufficient");
      return;
    }
    expect(result.sentence).not.toContain(state);
  });

  it.each(ALL_UNEMPLOYMENT_STATES)("Unemployment state %s renders its exact existing label, never a raw enum string", (state) => {
    const result = composeLaborComponents("STABLE", state, state === "INSUFFICIENT_DATA" ? "INSUFFICIENT_DATA" : "STABLE");
    if (state === "INSUFFICIENT_DATA") {
      expect(result.kind).toBe("unemployment-insufficient");
      return;
    }
    expect(result.sentence).not.toContain(state);
  });

  it.each(ALL_LABOR_STATES)("LaborState %s, when reported, renders its exact existing label, never a raw enum string", (state) => {
    const result = composeLaborComponents("STABLE", "STABLE", state);
    expect(result.kind).toBe("composed");
    expect(result.sentence).not.toContain(`as ${state}`);
  });
});

describe("composeLaborComponents -- no prohibited vocabulary, no new combination matrix", () => {
  it.each(ALL_EMPLOYMENT_STATES.filter((s) => s !== "INSUFFICIENT_DATA"))(
    "Employment=%s never produces prohibited vocabulary across all Unemployment/LaborState combinations",
    (employment) => {
      for (const unemployment of ALL_UNEMPLOYMENT_STATES.filter((s) => s !== "INSUFFICIENT_DATA")) {
        for (const laborState of ALL_LABOR_STATES) {
          const result = composeLaborComponents(employment, unemployment, laborState);
          expectNoProhibitedVocabulary(result.sentence);
        }
      }
    },
  );
});
