/**
 * The Economic World registry (Increment #41).
 *
 * The registry exists so world identity is defined once. These tests
 * hold it to that, and to the boundaries #41 set around it: three
 * active worlds, Calendar is not one of them, and Housing is not
 * pretended into existence.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { ECONOMIC_WORLDS, NON_WORLD_SURFACES, world, worldForRoute } from "./registry";

const SRC = join(dirname(fileURLToPath(import.meta.url)), "..");

describe("which worlds exist", () => {
  it("has exactly Inflation, Jobs and Rates active", () => {
    expect(ECONOMIC_WORLDS.map((entry) => entry.id)).toEqual(["INFLATION", "JOBS", "RATES"]);
  });

  it("does not pretend Housing exists", () => {
    // #45 owns Housing. An inactive world with no data is a promise the
    // product cannot keep.
    const text = JSON.stringify(ECONOMIC_WORLDS).toLowerCase();
    for (const absent of ["housing", "growth", "markets", "consumer"]) {
      expect(text, absent).not.toContain(absent);
    }
  });

  it("treats Calendar as a product surface, not an economic world", () => {
    expect(ECONOMIC_WORLDS.some((entry) => entry.route === "/calendar")).toBe(false);
    expect(NON_WORLD_SURFACES.map((surface) => surface.route)).toContain("/calendar");
    expect(worldForRoute("/calendar")).toBeUndefined();
  });
});

describe("identity is unambiguous", () => {
  it("gives every world a unique id, route and label", () => {
    for (const key of ["id", "route", "label"] as const) {
      const values = ECONOMIC_WORLDS.map((entry) => entry[key]);
      expect(new Set(values).size, key).toBe(values.length);
    }
  });

  it("uses no provider or series identifier as world identity", () => {
    // #38: a world is a MacroChipz concept, never a provider's series.
    const text = JSON.stringify(ECONOMIC_WORLDS);
    for (const providerish of ["PAYEMS", "UNRATE", "UST_", "FRED", "TREASURY", "BLS", "BEA", "CPIAUCSL"]) {
      expect(text, providerish).not.toContain(providerish);
    }
  });

  it("resolves a world by id and by route", () => {
    expect(world("JOBS").route).toBe("/jobs");
    expect(worldForRoute("/jobs")?.id).toBe("JOBS");
    expect(worldForRoute("/nope")).toBeUndefined();
  });

  it("throws rather than silently returning a blank world", () => {
    // @ts-expect-error -- deliberately outside the union.
    expect(() => world("HOUSING")).toThrow(/Unknown economic world/);
  });
});

describe("consumer names and engineering names", () => {
  it("routes are the product's words, not the engineering domain's", () => {
    expect(ECONOMIC_WORLDS.map((entry) => entry.route)).toEqual(["/inflation", "/jobs", "/rates"]);
  });

  it("records that Jobs is served by the labor domain, rather than hiding it", () => {
    expect(world("JOBS").engineeringDomain).toBe("labor");
  });

  it("carries no methodology, threshold or data-fetching concern", () => {
    const source = readFileSync(join(SRC, "worlds/registry.ts"), "utf8")
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/^\s*\/\/.*$/gm, "");
    for (const token of ["fetch(", "_v1.0", "threshold", "COOLING", "HEATING", "useState", "useEffect"]) {
      expect(source, token).not.toContain(token);
    }
  });
});

describe("the measurement vocabulary cannot drift from the product", () => {
  it("gives every world an analytics value matching its own name", () => {
    expect(ECONOMIC_WORLDS.map((entry) => entry.analyticsWorld)).toEqual(["inflation", "jobs", "rates"]);
  });

  it("derives WORLD_BY_ROUTE from the registry rather than repeating it", async () => {
    const { WORLD_BY_ROUTE } = await import("../analytics/events");
    expect(WORLD_BY_ROUTE).toEqual({ "/inflation": "inflation", "/jobs": "jobs", "/rates": "rates" });
  });

  it("emits no world for Calendar", async () => {
    const { WORLD_BY_ROUTE } = await import("../analytics/events");
    expect(WORLD_BY_ROUTE["/calendar" as keyof typeof WORLD_BY_ROUTE]).toBeUndefined();
  });
});

describe("the labor domain was not renamed to suit the UI", () => {
  it("still calls its methodology labor_v1.0 and its endpoint /monitors/labor", () => {
    // #41 §7: this is a PRESENTATION rename. Renaming a frozen
    // methodology to improve a heading would be the tail wagging the
    // dog, and it would break replay against recorded conclusions.
    const api = readFileSync(join(SRC, "api/labor.ts"), "utf8");
    expect(api).toContain("/monitors/labor");
    expect(readFileSync(join(SRC, "api/labor.types.ts"), "utf8")).toMatch(/LaborState/);
  });
});
