import { describe, expect, it } from "vitest";

import type { ChangeEvent } from "../api/inflation.types";
import { tierInflationChanges } from "./inflationSalience";

function event(overrides: Partial<ChangeEvent> = {}): ChangeEvent {
  return {
    component: "PRIMARY_MOMENTUM",
    event_type: "METRIC_CHANGED",
    field: "r_3m_annualized",
    previous_value: 2.1,
    current_value: 2.3,
    delta: 0.2,
    previous_period: "2026-06-01",
    current_period: "2026-07-01",
    methodology_id: "inflation_what_changed_v1.0",
    data_basis: "latest_revised_data",
    ...overrides,
  };
}

describe("Tier 1 -- Primary domain state (docs/product/overview-attention-model-v1.md §6)", () => {
  it("classifies PRIMARY_MOMENTUM's own STATE_CHANGED event as Tier 1", () => {
    const e = event({ component: "PRIMARY_MOMENTUM", event_type: "STATE_CHANGED", field: "state" });
    const { tier1 } = tierInflationChanges([e]);
    expect(tier1).toEqual([e]);
  });

  it("classifies PRIMARY_MOMENTUM's own AVAILABILITY_LOST/RESTORED event (field 'state') as Tier 1, not Tier 2", () => {
    const lost = event({ component: "PRIMARY_MOMENTUM", event_type: "AVAILABILITY_LOST", field: "state" });
    const restored = event({ component: "PRIMARY_MOMENTUM", event_type: "AVAILABILITY_RESTORED", field: "state" });
    expect(tierInflationChanges([lost]).tier1).toEqual([lost]);
    expect(tierInflationChanges([restored]).tier1).toEqual([restored]);
    expect(tierInflationChanges([lost]).tier2).toEqual([]);
  });

  it("does NOT classify PRIMARY_MOMENTUM's own metric-field availability event as Tier 1 -- only field 'state' is Tier 1", () => {
    const e = event({ component: "PRIMARY_MOMENTUM", event_type: "AVAILABILITY_LOST", field: "r_3m_annualized" });
    const { tier1, tier2 } = tierInflationChanges([e]);
    expect(tier1).toEqual([]);
    expect(tier2).toEqual([e]);
  });
});

describe("Tier 2 -- Structural change", () => {
  it("classifies Headline PCE's/Headline CPI's own STATE_CHANGED event as Tier 2", () => {
    const pce = event({ component: "HEADLINE_PCE", event_type: "STATE_CHANGED", field: "state" });
    const cpi = event({ component: "HEADLINE_CPI", event_type: "STATE_CHANGED", field: "state" });
    expect(tierInflationChanges([pce]).tier2).toEqual([pce]);
    expect(tierInflationChanges([cpi]).tier2).toEqual([cpi]);
  });

  it("classifies an AVAILABILITY_LOST/RESTORED event on ANY component (Target, Confirmation, Headline) as Tier 2, per §8", () => {
    const target = event({ component: "TARGET", event_type: "AVAILABILITY_LOST", field: "target_gap_pp" });
    const confirmation = event({ component: "CONFIRMATION", event_type: "AVAILABILITY_RESTORED", field: "relationship" });
    expect(tierInflationChanges([target]).tier2).toEqual([target]);
    expect(tierInflationChanges([confirmation]).tier2).toEqual([confirmation]);
  });
});

describe("Tier 3 -- Secondary/corroborating signal", () => {
  it("classifies CONFIRMATION_CHANGED as Tier 3, never Tier 2", () => {
    const e = event({ component: "CONFIRMATION", event_type: "CONFIRMATION_CHANGED", field: "relationship" });
    const { tier2, tier3 } = tierInflationChanges([e]);
    expect(tier3).toEqual([e]);
    expect(tier2).toEqual([]);
  });
});

describe("Tier 4 -- Metric update", () => {
  it("classifies every remaining METRIC_CHANGED event as Tier 4, including the context-only r_1m_annualized", () => {
    const e = event({ component: "PRIMARY_MOMENTUM", event_type: "METRIC_CHANGED", field: "r_1m_annualized" });
    expect(tierInflationChanges([e]).tier4).toEqual([e]);
  });

  it("Target -- which has no state concept -- only ever contributes Tier 2 (availability) or Tier 4 (metric) events", () => {
    const metric = event({ component: "TARGET", event_type: "METRIC_CHANGED", field: "target_gap_pp" });
    const { tier1, tier2, tier3, tier4 } = tierInflationChanges([metric]);
    expect(tier1).toEqual([]);
    expect(tier2).toEqual([]);
    expect(tier3).toEqual([]);
    expect(tier4).toEqual([metric]);
  });
});

describe("mutual exclusivity and exhaustiveness", () => {
  it("every event lands in exactly one tier -- no duplication, no loss", () => {
    const events = [
      event({ component: "PRIMARY_MOMENTUM", event_type: "STATE_CHANGED", field: "state" }),
      event({ component: "HEADLINE_PCE", event_type: "STATE_CHANGED", field: "state" }),
      event({ component: "HEADLINE_CPI", event_type: "AVAILABILITY_LOST", field: "state" }),
      event({ component: "CONFIRMATION", event_type: "CONFIRMATION_CHANGED", field: "relationship" }),
      event({ component: "TARGET", event_type: "AVAILABILITY_RESTORED", field: "target_gap_pp" }),
      event({ component: "TARGET", event_type: "METRIC_CHANGED", field: "headline_pce_yoy" }),
      event({ component: "HEADLINE_CPI", event_type: "METRIC_CHANGED", field: "r_12m" }),
    ];
    const { tier1, tier2, tier3, tier4 } = tierInflationChanges(events);
    expect(tier1.length + tier2.length + tier3.length + tier4.length).toBe(events.length);
    // No event object appears in more than one tier.
    const allClassified = [...tier1, ...tier2, ...tier3, ...tier4];
    expect(new Set(allClassified).size).toBe(events.length);
  });

  it("never reorders within the input -- classification only, never a sort", () => {
    const a = event({ component: "TARGET", event_type: "METRIC_CHANGED", field: "target_gap_pp", delta: 100 });
    const b = event({ component: "TARGET", event_type: "METRIC_CHANGED", field: "headline_pce_yoy", delta: 0.01 });
    // b has the smaller delta but appears first in the input -- a
    // magnitude-based sort would reorder these; classification must not.
    expect(tierInflationChanges([b, a]).tier4).toEqual([b, a]);
  });

  it("an empty input produces four empty tiers", () => {
    expect(tierInflationChanges([])).toEqual({ tier1: [], tier2: [], tier3: [], tier4: [] });
  });
});
