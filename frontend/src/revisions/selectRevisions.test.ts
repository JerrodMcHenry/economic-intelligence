/**
 * What counts as a revision (Increment #43).
 *
 * MEASURED BEFORE IMPLEMENTATION: 1,072 versioned observation rows, all
 * `is_backfilled = true`; zero observations with a second version; zero
 * superseded rows; all 358 `OBSERVATION_CHANGE` objects `NEW`.
 * **MacroChipz has captured no genuine revision.** These tests exist so
 * that when the first one arrives it is recognised — and so that the
 * three things routinely mistaken for revisions never are.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import type { IntelligenceObject } from "../api/intelligence.types";
import { isGenuineRevision, selectRevisions } from "./selectRevisions";

const HERE = dirname(fileURLToPath(import.meta.url));

function observation(payload: Record<string, unknown>, overrides: Record<string, unknown> = {}): IntelligenceObject {
  return {
    id: `observation:${JSON.stringify(payload).slice(0, 24)}`,
    type: "OBSERVATION_CHANGE",
    world: "jobs",
    concepts: ["us.unemployment-rate.sa.monthly"],
    effective_period: "2026-08-01",
    recorded_at: "2026-09-19T18:46:27Z",
    published_at: null,
    knowledge_basis: "OBSERVED",
    basis: "SOURCE_FACT",
    methodology: null,
    evidence: [],
    relations: [],
    limitations: [],
    contract_version: "intelligence_v1",
    payload: {
      series_title: "Unemployment Rate",
      provider: "FRED",
      provider_series_id: "UNRATE",
      observation_date: "2026-08-01",
      units: "Percent",
      new_value: 4.1,
      delta: null,
      previous_value: null,
      ...payload,
    },
    ...overrides,
  } as unknown as IntelligenceObject;
}

const GENUINE = observation({
  change_type: "REVISED",
  revision_knowledge: "PROSPECTIVE_REVISION",
  original_value_known: true,
  previous_value: 3.1,
  new_value: 3.0,
  delta: -0.1,
});

describe("the three things that are NOT revisions", () => {
  it("a first observation is not a revision", () => {
    // All 358 local observation changes are this.
    expect(isGenuineRevision(observation({ change_type: "NEW", revision_knowledge: "FIRST_OBSERVATION" }))).toBe(false);
  });

  it("a backfilled baseline is not a revision, even when marked REVISED", () => {
    // THE DANGEROUS CASE: `change_type` says REVISED, but the earlier
    // value was imported at migration time. Filtering on change_type
    // alone would present a database event as economic history.
    expect(
      isGenuineRevision(
        observation({
          change_type: "REVISED",
          revision_knowledge: "BACKFILLED_BASELINE",
          original_value_known: false,
          previous_value: 3.1,
        }),
      ),
    ).toBe(false);
  });

  it("an analysis or state change is not an observation revision", () => {
    const analysis = { ...GENUINE, type: "ANALYSIS_CHANGE" } as unknown as IntelligenceObject;
    expect(isGenuineRevision(analysis)).toBe(false);
  });

  it("an object with no knowledge state claims nothing", () => {
    // Pre-#43 objects omit the field entirely.
    expect(isGenuineRevision(observation({ change_type: "REVISED", previous_value: 3.1 }))).toBe(false);
  });
});

describe("what IS a revision", () => {
  it("recognises a value MacroChipz recorded and then saw change", () => {
    expect(isGenuineRevision(GENUINE)).toBe(true);
  });

  it("selects it and nothing else from a realistic mixed list", () => {
    const list = [
      observation({ change_type: "NEW", revision_knowledge: "FIRST_OBSERVATION" }),
      observation({ change_type: "REVISED", revision_knowledge: "BACKFILLED_BASELINE", previous_value: 3.1 }),
      GENUINE,
    ];
    expect(selectRevisions(list)).toEqual([GENUINE]);
  });

  it("returns nothing for today's actual data shape", () => {
    // 358 NEW observations and nothing else.
    const local = Array.from({ length: 5 }, () =>
      observation({ change_type: "NEW", revision_knowledge: "FIRST_OBSERVATION" }),
    );
    expect(selectRevisions(local)).toEqual([]);
  });
});

describe("ordering", () => {
  it("is by detection time, most recent first", () => {
    const older = { ...GENUINE, id: "a", recorded_at: "2026-09-01T00:00:00Z" } as IntelligenceObject;
    const newer = { ...GENUINE, id: "b", recorded_at: "2026-09-20T00:00:00Z" } as IntelligenceObject;
    expect(selectRevisions([older, newer]).map((r) => r.id)).toEqual(["b", "a"]);
  });

  it("breaks ties by id, never by size of revision", () => {
    const small = { ...GENUINE, id: "aaa", payload: { ...GENUINE.payload, delta: -0.1 } } as IntelligenceObject;
    const large = { ...GENUINE, id: "bbb", payload: { ...GENUINE.payload, delta: -9.9 } } as IntelligenceObject;
    // The larger revision does NOT come first.
    expect(selectRevisions([large, small]).map((r) => r.id)).toEqual(["aaa", "bbb"]);
  });

  it("is deterministic regardless of input order", () => {
    const list = [
      { ...GENUINE, id: "a", recorded_at: "2026-09-01T00:00:00Z" },
      { ...GENUINE, id: "b", recorded_at: "2026-09-20T00:00:00Z" },
    ] as IntelligenceObject[];
    expect(selectRevisions(list)).toEqual(selectRevisions([...list].reverse()));
  });
});

describe("the module claims nothing it cannot prove", () => {
  const source = readFileSync(join(HERE, "selectRevisions.ts"), "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "");

  it("ranks by no magnitude and no significance", () => {
    for (const token of ["Math.abs", "significance", "score", "importance", "magnitude", "rank", "biggest"]) {
      expect(source, token).not.toContain(token);
    }
  });

  it("never treats recorded time as publication time", () => {
    expect(source).not.toContain("published_at");
    expect(source).toContain("recorded_at");
  });

  it("reconstructs no revision truth of its own", () => {
    // It reads the backend's knowledge state; it does not infer one
    // from raw values or version endpoints.
    expect(source).toContain("revision_knowledge");
    for (const token of ["observation_versions", "recorded_from", "recorded_to", "is_backfilled", "fetch("]) {
      expect(source, token).not.toContain(token);
    }
  });

  it("calls no model and no provider", () => {
    for (const token of ["openai", "anthropic", "axios"]) {
      expect(source.toLowerCase(), token).not.toContain(token);
    }
  });
});
