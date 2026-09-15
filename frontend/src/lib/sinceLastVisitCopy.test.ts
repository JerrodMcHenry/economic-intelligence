import { describe, expect, it } from "vitest";

import { buildDomainRecap, buildRecalculation, buildSourceUpdate, buildStructuralChange } from "../test/fixtures/sinceLastVisit";
import {
  FIRST_VISIT_HEADING,
  LOOKBACK_CLAMPED_COPY,
  RETURN_VISIT_HEADING,
  coverageDisclosureCopy,
  domainLabel,
  domainZeroStateCopy,
  lastCheckedCopy,
  recalculationCopy,
  sinceLastVisitHeading,
  sourceUpdateCopy,
  structuralChangeCopy,
} from "./sinceLastVisitCopy";

describe("sinceLastVisitHeading", () => {
  it("first visit -> exact frozen heading", () => {
    expect(sinceLastVisitHeading(true)).toBe("Recent Economic Activity");
    expect(sinceLastVisitHeading(true)).toBe(FIRST_VISIT_HEADING);
  });

  it("return visit -> exact frozen heading", () => {
    expect(sinceLastVisitHeading(false)).toBe("Since Your Last Check");
    expect(sinceLastVisitHeading(false)).toBe(RETURN_VISIT_HEADING);
  });
});

describe("domainLabel", () => {
  it("maps machine monitor values to exact display labels", () => {
    expect(domainLabel("inflation")).toBe("Inflation");
    expect(domainLabel("labor")).toBe("Labor");
  });
});

describe("LOOKBACK_CLAMPED_COPY", () => {
  it("is the exact frozen disclosure", () => {
    expect(LOOKBACK_CLAMPED_COPY).toBe("This summary covers the last 90 days — your last visit was longer ago.");
  });
});

describe("coverageDisclosureCopy", () => {
  it("CHECKED -> no extra disclosure", () => {
    expect(coverageDisclosureCopy("CHECKED")).toBeNull();
  });

  it("GAP -> exact frozen soft disclosure", () => {
    expect(coverageDisclosureCopy("GAP")).toBe("Some monitored releases could not be fully checked since your last visit.");
  });

  it("UNKNOWN -> exact frozen disclosure", () => {
    expect(coverageDisclosureCopy("UNKNOWN")).toBe("EI's own automated-checking coverage for this period could not be confirmed.");
  });
});

describe("domainZeroStateCopy", () => {
  it("CHECKED, zero items -> exact §79 row A copy", () => {
    const recap = buildDomainRecap({ monitor: "inflation", coverage: "CHECKED" });
    expect(domainZeroStateCopy(recap)).toBe("No new Inflation activity was detected since your last check.");
  });

  it("CHECKED, has content -> no zero-state copy (real content is the content)", () => {
    const recap = buildDomainRecap({ monitor: "inflation", coverage: "CHECKED", structural_changes: [buildStructuralChange()] });
    expect(domainZeroStateCopy(recap)).toBeNull();
  });

  it("GAP, zero items -> exact §79 row C wording", () => {
    const recap = buildDomainRecap({ monitor: "labor", coverage: "GAP" });
    expect(domainZeroStateCopy(recap)).toBe("No monitored Labor releases were processed since your last check.");
  });

  it("UNKNOWN, zero items -> exact §79 row D wording, never collapsed with GAP or CHECKED", () => {
    const recap = buildDomainRecap({ monitor: "inflation", coverage: "UNKNOWN" });
    expect(domainZeroStateCopy(recap)).toBe("Coverage for Inflation could not be confirmed for this period.");
  });

  it("the three zero-state copies are all distinct strings, never collapsing (contract §79)", () => {
    const checked = domainZeroStateCopy(buildDomainRecap({ coverage: "CHECKED" }));
    const gap = domainZeroStateCopy(buildDomainRecap({ coverage: "GAP" }));
    const unknown = domainZeroStateCopy(buildDomainRecap({ coverage: "UNKNOWN" }));
    expect(new Set([checked, gap, unknown]).size).toBe(3);
  });

  it("recalculations alone (no structural/source) still count as content -- no zero-state copy", () => {
    const recap = buildDomainRecap({ recalculations: [buildRecalculation()] });
    expect(domainZeroStateCopy(recap)).toBeNull();
  });

  it("source updates alone still count as content -- no zero-state copy", () => {
    const recap = buildDomainRecap({ source_updates: [buildSourceUpdate()] });
    expect(domainZeroStateCopy(recap)).toBeNull();
  });
});

describe("lastCheckedCopy", () => {
  it("wraps an already-formatted timestamp in the exact frozen template", () => {
    expect(lastCheckedCopy("Sep 15, 9:04 AM")).toBe("Last checked: Sep 15, 9:04 AM.");
  });

  it("returns null when no timestamp is available -- never a fabricated fact", () => {
    expect(lastCheckedCopy(null)).toBeNull();
  });
});

describe("structuralChangeCopy", () => {
  it("a genuine state transition renders the exact §81 template, verbatim state labels", () => {
    const item = buildStructuralChange({ monitor: "inflation", event_type: "STATE_CHANGED", previous_value: "COOLING", current_value: "STABLE", evaluation_period: "2026-08-01" });
    expect(structuralChangeCopy(item)).toBe("Inflation changed from Cooling to Stable for August 2026.");
  });

  it("a Labor state transition uses Labor's own label map", () => {
    const item = buildStructuralChange({ monitor: "labor", previous_value: "STRENGTHENING", current_value: "COOLING", evaluation_period: "2026-09-01" });
    expect(structuralChangeCopy(item)).toBe("Labor changed from Strengthening to Cooling for September 2026.");
  });

  it("AVAILABILITY_LOST uses the existing non-directional #22B phrasing, never 'changed from X to null'", () => {
    const item = buildStructuralChange({ monitor: "inflation", event_type: "AVAILABILITY_LOST", previous_value: "COOLING", current_value: null, evaluation_period: "2026-08-01" });
    expect(structuralChangeCopy(item)).toBe("Inflation's own state became unavailable for August 2026.");
  });

  it("AVAILABILITY_RESTORED uses the exact mirrored phrasing", () => {
    const item = buildStructuralChange({ monitor: "labor", event_type: "AVAILABILITY_RESTORED", previous_value: null, current_value: "STABLE", evaluation_period: "2026-08-01" });
    expect(structuralChangeCopy(item)).toBe("Labor's own state became available again for August 2026.");
  });

  it("never uses directional/interpretive language beyond the state labels themselves", () => {
    const item = buildStructuralChange();
    const copy = structuralChangeCopy(item);
    expect(copy).not.toMatch(/weaken|improv|worsen|pressure/i);
  });
});

describe("recalculationCopy", () => {
  it("FIRST_CALCULATION never uses 'remains' (contract §22, hard requirement)", () => {
    const item = buildRecalculation({ monitor: "inflation", kind: "FIRST_CALCULATION", state: "COOLING", evaluation_period: "2026-08-01", count: 1 });
    const copy = recalculationCopy(item);
    expect(copy).toBe("Inflation was calculated as Cooling for August 2026.");
    expect(copy).not.toMatch(/remains/i);
  });

  it("UNCHANGED_CONFIRMATION, count 1 -> exact singular template with 'remains'", () => {
    const item = buildRecalculation({ monitor: "inflation", kind: "UNCHANGED_CONFIRMATION", state: "COOLING", evaluation_period: "2026-08-01", count: 1 });
    expect(recalculationCopy(item)).toBe("Inflation was recalculated for August 2026 and remains Cooling.");
  });

  it("UNCHANGED_CONFIRMATION, count > 1 -> exact aggregated template with the count (contract §23)", () => {
    const item = buildRecalculation({ monitor: "labor", kind: "UNCHANGED_CONFIRMATION", state: "STABLE", evaluation_period: "2026-09-01", count: 3 });
    expect(recalculationCopy(item)).toBe("Labor was recalculated 3 times since your last visit and remains Stable (most recently for September 2026).");
  });

  it("INSUFFICIENT_DATA uses the dedicated noun-phrase adaptation, never 'remains Insufficient data'", () => {
    const item = buildRecalculation({ monitor: "labor", kind: "UNCHANGED_CONFIRMATION", state: "INSUFFICIENT_DATA", evaluation_period: "2026-08-01", count: 1 });
    const copy = recalculationCopy(item);
    expect(copy).toBe("Labor was recalculated for August 2026; its state is still insufficient to classify.");
    expect(copy).not.toMatch(/remains/i);
  });

  it("INSUFFICIENT_DATA first calculation still never says 'remains'", () => {
    const item = buildRecalculation({ kind: "FIRST_CALCULATION", state: "INSUFFICIENT_DATA" });
    expect(recalculationCopy(item)).not.toMatch(/remains/i);
  });
});

describe("sourceUpdateCopy", () => {
  it("REVISED -> exact §82 template", () => {
    const item = buildSourceUpdate({ series_title: "Core PCE Price Index", change_type: "REVISED" });
    expect(sourceUpdateCopy(item)).toBe("Core PCE Price Index data was revised.");
  });

  it("NEW -> exact §82 template, distinguished from REVISED (contract §29/§38)", () => {
    const item = buildSourceUpdate({ series_title: "Core PCE Price Index", change_type: "NEW" });
    expect(sourceUpdateCopy(item)).toBe("Core PCE Price Index data was updated.");
  });

  it("falls back to the raw series_id when no title is available -- never a fabricated name (contract §72-73)", () => {
    const item = buildSourceUpdate({ series_title: null, series_id: "FABRICATED_XYZ", change_type: "NEW" });
    expect(sourceUpdateCopy(item)).toBe("FABRICATED_XYZ data was updated.");
  });
});
