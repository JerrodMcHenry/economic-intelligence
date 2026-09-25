import { describe, expect, it } from "vitest";

import { CANONICAL_MONITOR_RELEASE_IDS, canonicalMonitorDomain, releaseMonitorCta } from "./releaseMonitorRelation";

describe("CANONICAL_MONITOR_RELEASE_IDS -- migration-verified, not releaseCategory()-derived (docs/product/overview-attention-model-v1.md §3A)", () => {
  it("maps CPI ('cpi') and Personal Income and Outlays ('pio') to Inflation", () => {
    expect(CANONICAL_MONITOR_RELEASE_IDS.INFLATION.has("cpi")).toBe(true);
    expect(CANONICAL_MONITOR_RELEASE_IDS.INFLATION.has("pio")).toBe(true);
  });

  it("maps Employment Situation ('empsit') to Labor", () => {
    expect(CANONICAL_MONITOR_RELEASE_IDS.LABOR.has("empsit")).toBe(true);
  });

  it("THE JOLTS REGRESSION TEST: '192' is in neither set, despite releaseCategory() tagging it 'Labor'", () => {
    expect(CANONICAL_MONITOR_RELEASE_IDS.INFLATION.has("192")).toBe(false);
    expect(CANONICAL_MONITOR_RELEASE_IDS.LABOR.has("192")).toBe(false);
  });

  it("GDP ('53') and Advance Retail Sales ('9') are in neither set", () => {
    for (const id of ["53", "9"]) {
      expect(CANONICAL_MONITOR_RELEASE_IDS.INFLATION.has(id)).toBe(false);
      expect(CANONICAL_MONITOR_RELEASE_IDS.LABOR.has(id)).toBe(false);
    }
  });
});

describe("canonicalMonitorDomain", () => {
  it("returns INFLATION for CPI and Personal Income and Outlays", () => {
    expect(canonicalMonitorDomain("cpi")).toBe("INFLATION");
    expect(canonicalMonitorDomain("pio")).toBe("INFLATION");
  });

  it("returns LABOR for Employment Situation", () => {
    expect(canonicalMonitorDomain("empsit")).toBe("LABOR");
  });

  it("returns null for JOLTS, GDP, Advance Retail Sales, and any unmapped release", () => {
    for (const id of ["192", "53", "9", "999"]) {
      expect(canonicalMonitorDomain(id)).toBeNull();
    }
  });
});

describe("releaseMonitorCta -- the frozen exact per-release navigation table (§17)", () => {
  it("CPI ('cpi') -> View Inflation -> /inflation", () => {
    expect(releaseMonitorCta("cpi")).toEqual({ label: "View Inflation →", to: "/inflation" });
  });

  it("Personal Income and Outlays ('pio') -> View Inflation -> /inflation", () => {
    expect(releaseMonitorCta("pio")).toEqual({ label: "View Inflation →", to: "/inflation" });
  });

  it("Employment Situation ('empsit') -> View Jobs -> /jobs", () => {
    expect(releaseMonitorCta("empsit")).toEqual({ label: "View Jobs →", to: "/jobs" });
  });

  it("JOLTS ('192') -> View Calendar -> /calendar -- never /labor", () => {
    expect(releaseMonitorCta("192")).toEqual({ label: "View Calendar →", to: "/calendar" });
  });

  it("GDP ('53') -> View Calendar -> /calendar", () => {
    expect(releaseMonitorCta("53")).toEqual({ label: "View Calendar →", to: "/calendar" });
  });

  it("Advance Retail Sales ('9') -> View Calendar -> /calendar", () => {
    expect(releaseMonitorCta("9")).toEqual({ label: "View Calendar →", to: "/calendar" });
  });

  it("an unmapped release ID also gets the honest /releases fallback, never a dead end", () => {
    expect(releaseMonitorCta("does-not-exist")).toEqual({ label: "View Calendar →", to: "/calendar" });
  });
});
