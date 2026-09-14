import { describe, expect, it } from "vitest";

import type { LaborChangeEvent } from "../api/labor.types";
import { tierLaborChanges } from "./laborSalience";

function event(overrides: Partial<LaborChangeEvent> = {}): LaborChangeEvent {
  return {
    component: "EMPLOYMENT",
    event_type: "METRIC_CHANGED",
    field: "current_3m_avg_jobs",
    previous_value: 120000,
    current_value: 150000,
    delta: 30000,
    previous_period: "2026-06-01",
    current_period: "2026-07-01",
    methodology_id: "labor_v1.0",
    data_basis: "latest_revised_data",
    ...overrides,
  };
}

describe("Tier 1 -- Primary domain state (docs/product/overview-attention-model-v1.md §7)", () => {
  it("classifies any LABOR-component event as Tier 1, regardless of event_type", () => {
    const stateChanged = event({ component: "LABOR", event_type: "STATE_CHANGED", field: "state" });
    const lost = event({ component: "LABOR", event_type: "AVAILABILITY_LOST", field: "state" });
    expect(tierLaborChanges([stateChanged]).tier1).toEqual([stateChanged]);
    expect(tierLaborChanges([lost]).tier1).toEqual([lost]);
  });
});

describe("Tier 2 -- Structural change", () => {
  it("classifies EMPLOYMENT's/UNEMPLOYMENT's own field:'state' STATE_CHANGED/AVAILABILITY_* event as Tier 2", () => {
    const employment = event({ component: "EMPLOYMENT", event_type: "STATE_CHANGED", field: "state" });
    const unemployment = event({ component: "UNEMPLOYMENT", event_type: "AVAILABILITY_RESTORED", field: "state" });
    expect(tierLaborChanges([employment]).tier2).toEqual([employment]);
    expect(tierLaborChanges([unemployment]).tier2).toEqual([unemployment]);
  });

  it("does not classify a LABOR-component field:'state' event as Tier 2 -- it is Tier 1", () => {
    const e = event({ component: "LABOR", event_type: "STATE_CHANGED", field: "state" });
    expect(tierLaborChanges([e]).tier2).toEqual([]);
  });
});

describe("Tier 3 -- Secondary/corroborating signal", () => {
  it("classifies EMPLOYMENT's own condition/momentum fields as Tier 3, reported independently", () => {
    const condition = event({ component: "EMPLOYMENT", event_type: "STATE_CHANGED", field: "condition" });
    const momentum = event({ component: "EMPLOYMENT", event_type: "STATE_CHANGED", field: "momentum" });
    expect(tierLaborChanges([condition]).tier3).toEqual([condition]);
    expect(tierLaborChanges([momentum]).tier3).toEqual([momentum]);
    // Both present simultaneously -- neither suppresses the other.
    const both = tierLaborChanges([condition, momentum]).tier3;
    expect(both).toHaveLength(2);
  });
});

describe("Tier 4 -- Metric update", () => {
  it("classifies every METRIC_CHANGED event, any component, as Tier 4", () => {
    const employment = event({ component: "EMPLOYMENT", event_type: "METRIC_CHANGED", field: "momentum_delta_jobs" });
    const unemployment = event({ component: "UNEMPLOYMENT", event_type: "METRIC_CHANGED", field: "delta_pp" });
    expect(tierLaborChanges([employment]).tier4).toEqual([employment]);
    expect(tierLaborChanges([unemployment]).tier4).toEqual([unemployment]);
  });
});

describe("mirrors /labor's own shipped WhatChangedSection.tsx filters exactly (§7/§20 -- refactor for reuse, not a new hierarchy)", () => {
  it("every event lands in exactly one tier for a realistic multi-event comparison", () => {
    const events = [
      event({ component: "LABOR", event_type: "STATE_CHANGED", field: "state" }),
      event({ component: "EMPLOYMENT", event_type: "STATE_CHANGED", field: "state" }),
      event({ component: "UNEMPLOYMENT", event_type: "STATE_CHANGED", field: "state" }),
      event({ component: "EMPLOYMENT", event_type: "STATE_CHANGED", field: "condition" }),
      event({ component: "EMPLOYMENT", event_type: "STATE_CHANGED", field: "momentum" }),
      event({ component: "EMPLOYMENT", event_type: "METRIC_CHANGED", field: "momentum_delta_jobs" }),
      event({ component: "UNEMPLOYMENT", event_type: "METRIC_CHANGED", field: "delta_pp" }),
    ];
    const { tier1, tier2, tier3, tier4 } = tierLaborChanges(events);
    expect(tier1).toHaveLength(1);
    expect(tier2).toHaveLength(2);
    expect(tier3).toHaveLength(2);
    expect(tier4).toHaveLength(2);
    expect(tier1.length + tier2.length + tier3.length + tier4.length).toBe(events.length);
  });

  it("an empty input produces four empty tiers", () => {
    expect(tierLaborChanges([])).toEqual({ tier1: [], tier2: [], tier3: [], tier4: [] });
  });
});
