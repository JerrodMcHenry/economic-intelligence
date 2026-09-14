import { describe, expect, it } from "vitest";

import {
  formatAnalysisValue,
  formatCheckedAt,
  formatObservationValue,
  observationChangeTypeLabel,
  processingStatusLabel,
} from "./detectedChangeFormat";

describe("processingStatusLabel", () => {
  it("maps every canonical status to the exact restrained copy", () => {
    expect(processingStatusLabel("NOT_CHECKED")).toBe("Not yet checked by Economic Intelligence.");
    expect(processingStatusLabel("NO_CHANGE")).toBe("No new data detected in the latest check.");
    expect(processingStatusLabel("CHANGES_DETECTED")).toBe("Data changes detected.");
    expect(processingStatusLabel("PARTIAL_CHECK")).toBe("Check incomplete.");
    expect(processingStatusLabel("CHECK_FAILED")).toBe("Check unsuccessful.");
  });
});

describe("observationChangeTypeLabel", () => {
  it("never uses Published/Released/Corrected/Finalized", () => {
    const newLabel = observationChangeTypeLabel("NEW");
    const revisedLabel = observationChangeTypeLabel("REVISED");
    expect(newLabel).toBe("New observation");
    expect(revisedLabel).toBe("Revision detected");
    for (const label of [newLabel, revisedLabel]) {
      expect(label).not.toMatch(/published|released|corrected|finalized/i);
    }
  });
});

describe("formatObservationValue", () => {
  it("returns 'Unavailable' for null, never a fabricated zero", () => {
    expect(formatObservationValue(null, "Percent")).toBe("Unavailable");
  });

  it("appends % only when units indicate percent", () => {
    expect(formatObservationValue(3.9, "Percent")).toBe("3.9%");
  });

  it("shows an index-level value as a plain number, never converted to percent", () => {
    expect(formatObservationValue(121.5, "Index 2017=100")).toBe("121.5");
  });

  it("shows a value with unknown/missing units without an invented suffix", () => {
    expect(formatObservationValue(500, null)).toBe("500");
  });
});

describe("formatAnalysisValue", () => {
  it("returns 'Unavailable' for null", () => {
    expect(formatAnalysisValue("r_3m_annualized", null)).toBe("Unavailable");
  });

  it("looks up a 'state' field through the canonical state label map", () => {
    expect(formatAnalysisValue("state", "HEATING")).toBe("Heating");
  });

  it("looks up a 'relationship' field through the canonical relationship label map", () => {
    expect(formatAnalysisValue("relationship", "DIVERGES")).toBe("Diverges");
  });

  it("shows any other field's value exactly as persisted, never reinterpreted as numeric", () => {
    expect(formatAnalysisValue("r_3m_annualized", "2.55")).toBe("2.55");
  });
});

describe("formatCheckedAt", () => {
  it("formats a timezone-aware ISO datetime without a timezone-rollback bug", () => {
    // A UTC-midnight instant that would roll back a day if ever routed
    // through a date-ONLY parser in a timezone behind UTC -- this
    // function is safe because it always receives an explicit offset.
    const formatted = formatCheckedAt("2026-09-13T21:42:00+00:00");
    expect(formatted).toContain("Sep");
    expect(formatted).not.toMatch(/:\d{2}:\d{2}\s*(AM|PM)?$/); // no seconds
  });

  it("returns the raw string for an unparseable value rather than guessing", () => {
    expect(formatCheckedAt("not-a-date")).toBe("not-a-date");
  });
});
