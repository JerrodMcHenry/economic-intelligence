/**
 * Unit tests for the pure State Duration V1 copy helper
 * (lib/stateDurationCopy.ts), frozen contract
 * docs/product/state-duration-v1.md §37/§42/§51.
 */
import { describe, expect, it } from "vitest";

import { buildStateDurationAvailable, buildStateDurationCurrentInsufficient } from "../test/fixtures/stateDuration";
import { buildStateDurationCopy, CURRENT_INSUFFICIENT_COPY } from "./stateDurationCopy";

describe("AVAILABLE + EXACT", () => {
  it("renders the exact frozen §37A template", () => {
    const result = buildStateDurationAvailable({
      boundary_type: "EXACT",
      duration_months: 3,
      earliest_confirmed_period: "2026-04-01",
      state: "COOLING",
    });
    const copy = buildStateDurationCopy(result, "Cooling", null);
    expect(copy.kind).toBe("EXACT");
    expect(copy.headline).toBe("Latest-revised reconstruction: Cooling for 3 consecutive months, since April 2026.");
  });

  it("pluralizes a one-month duration correctly", () => {
    const result = buildStateDurationAvailable({ boundary_type: "EXACT", duration_months: 1, earliest_confirmed_period: "2026-07-01" });
    const copy = buildStateDurationCopy(result, "Cooling", null);
    expect(copy.headline).toBe("Latest-revised reconstruction: Cooling for 1 consecutive month, since July 2026.");
  });

  it("includes a previous-state note when previous_state/previous_period are both populated", () => {
    const result = buildStateDurationAvailable({
      boundary_type: "EXACT",
      previous_state: "STABLE",
      previous_period: "2026-04-01",
    });
    const copy = buildStateDurationCopy(result, "Cooling", "Stable");
    expect(copy.previousStateNote).toBe("Previously Stable, as of April 2026.");
  });

  it("never fabricates a previous-state note when the backend didn't populate one", () => {
    const result = buildStateDurationAvailable({ boundary_type: "EXACT", previous_state: null, previous_period: null });
    const copy = buildStateDurationCopy(result, "Cooling", null);
    expect(copy.previousStateNote).toBeNull();
  });

  it("does not overclaim recorded history -- the sentence never drops the reconstruction qualifier", () => {
    const result = buildStateDurationAvailable({ boundary_type: "EXACT" });
    const copy = buildStateDurationCopy(result, "Cooling", null);
    expect(copy.headline).toMatch(/^Latest-revised reconstruction:/);
    expect(copy.headline).not.toMatch(/EI has been|has been classified as|EI has said|EI has classified/i);
  });
});

describe("AVAILABLE + DATA_BOUNDED", () => {
  it("renders the exact frozen §37B template with lower-bound semantics ('at least')", () => {
    const result = buildStateDurationAvailable({ boundary_type: "DATA_BOUNDED", duration_months: 3, state: "COOLING" });
    const copy = buildStateDurationCopy(result, "Cooling", null);
    expect(copy.kind).toBe("DATA_BOUNDED");
    expect(copy.headline).toBe("Latest-revised reconstruction: Cooling for at least 3 consecutive months.");
    expect(copy.headline).toMatch(/at least/);
  });

  it("never populates a previous-state note", () => {
    const result = buildStateDurationAvailable({ boundary_type: "DATA_BOUNDED", previous_state: null, previous_period: null });
    const copy = buildStateDurationCopy(result, "Cooling", null);
    expect(copy.previousStateNote).toBeNull();
  });

  it("does not display earliest_confirmed_period as an exact start claim", () => {
    const result = buildStateDurationAvailable({ boundary_type: "DATA_BOUNDED", earliest_confirmed_period: "2020-01-01" });
    const copy = buildStateDurationCopy(result, "Cooling", null);
    expect(copy.headline).not.toMatch(/2020|January/);
  });
});

describe("AVAILABLE + LOOKBACK_BOUNDED", () => {
  it("renders the exact frozen §37C template with lower-bound semantics ('at least')", () => {
    const result = buildStateDurationAvailable({ boundary_type: "LOOKBACK_BOUNDED", duration_months: 60, state: "COOLING" });
    const copy = buildStateDurationCopy(result, "Cooling", null);
    expect(copy.kind).toBe("LOOKBACK_BOUNDED");
    expect(copy.headline).toBe("Latest-revised reconstruction: Cooling for at least 60 consecutive months.");
    expect(copy.headline).toMatch(/at least/);
  });

  it("never populates a previous-state note", () => {
    const result = buildStateDurationAvailable({ boundary_type: "LOOKBACK_BOUNDED", previous_state: null, previous_period: null });
    const copy = buildStateDurationCopy(result, "Cooling", null);
    expect(copy.previousStateNote).toBeNull();
  });

  it("never implies the state began at the oldest searched month", () => {
    const result = buildStateDurationAvailable({ boundary_type: "LOOKBACK_BOUNDED", earliest_confirmed_period: "2021-08-01" });
    const copy = buildStateDurationCopy(result, "Cooling", null);
    expect(copy.headline).not.toMatch(/2021|August/);
    expect(copy.headline).not.toMatch(/since/);
  });
});

describe("CURRENT_INSUFFICIENT", () => {
  it("renders the exact frozen §37D copy", () => {
    const result = buildStateDurationCurrentInsufficient();
    const copy = buildStateDurationCopy(result, "", null);
    expect(copy.kind).toBe("CURRENT_INSUFFICIENT");
    expect(copy.headline).toBe(CURRENT_INSUFFICIENT_COPY);
    expect(copy.headline).toBe("Historical state duration is unavailable because the current state has insufficient data.");
  });

  it("never populates a previous-state note", () => {
    const copy = buildStateDurationCopy(buildStateDurationCurrentInsufficient(), "", null);
    expect(copy.previousStateNote).toBeNull();
  });

  it("never computes or implies a duration", () => {
    const copy = buildStateDurationCopy(buildStateDurationCurrentInsufficient(), "", null);
    expect(copy.headline).not.toMatch(/\d+ (consecutive )?months?/);
  });
});

describe("forbidden overclaiming vocabulary -- never present in any rendered copy", () => {
  const FORBIDDEN = [/EI has classified/i, /EI has said/i, /EI reported/i, /as-known-at-time/i, /as of \{?date\}?, EI knew/i];

  it.each([
    ["EXACT", buildStateDurationAvailable({ boundary_type: "EXACT" })],
    ["DATA_BOUNDED", buildStateDurationAvailable({ boundary_type: "DATA_BOUNDED" })],
    ["LOOKBACK_BOUNDED", buildStateDurationAvailable({ boundary_type: "LOOKBACK_BOUNDED" })],
    ["CURRENT_INSUFFICIENT", buildStateDurationCurrentInsufficient()],
  ] as const)("%s copy contains no forbidden historical-truth phrase", (_label, result) => {
    const copy = buildStateDurationCopy(result, "Cooling", "Stable");
    const combined = `${copy.headline} ${copy.previousStateNote ?? ""}`;
    for (const pattern of FORBIDDEN) {
      expect(combined).not.toMatch(pattern);
    }
  });
});

describe("exhaustive boundary_type handling", () => {
  it("throws rather than silently rendering misleading copy for an unrecognized boundary_type", () => {
    const result = buildStateDurationAvailable({ boundary_type: "UNKNOWN_FUTURE_VALUE" as never });
    expect(() => buildStateDurationCopy(result, "Cooling", null)).toThrow(/Unknown state-duration boundary_type/);
  });
});

describe("determinism", () => {
  it("identical input produces identical output on repeated calls", () => {
    const result = buildStateDurationAvailable({ boundary_type: "EXACT" });
    const first = buildStateDurationCopy(result, "Cooling", "Stable");
    const second = buildStateDurationCopy(result, "Cooling", "Stable");
    expect(first).toEqual(second);
  });
});
