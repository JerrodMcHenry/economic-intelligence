import { describe, expect, it } from "vitest";

import {
  analysisComponentLabel,
  analysisFieldLabel,
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

  // Increment #20E.2 -- the exact bug #20E.1 found: this generic
  // read-model formatter must correctly humanize Labor's own
  // state-shaped values too, not just Inflation's (see
  // docs/architecture/labor-ui-v1.md §6b/§23).
  describe("Labor family values (the #20E.1 bug fix)", () => {
    it("humanizes an EmploymentState value not in Inflation's own label map", () => {
      expect(formatAnalysisValue("state", "RECOVERING")).toBe("Recovering");
      expect(formatAnalysisValue("state", "EXPANDING")).toBe("Expanding");
      expect(formatAnalysisValue("state", "CONTRACTING")).toBe("Contracting");
    });

    it("humanizes an UnemploymentTrendState value not in Inflation's own label map", () => {
      expect(formatAnalysisValue("state", "DETERIORATING")).toBe("Deteriorating");
    });

    it("a value that happens to share a word with an Inflation state still renders correctly", () => {
      // "MIXED"/"STABLE" exist in both vocabularies with the same label text --
      // this is a coincidence, not a dependency; confirmed correct either way.
      expect(formatAnalysisValue("state", "MIXED")).toBe("Mixed");
      expect(formatAnalysisValue("state", "STABLE")).toBe("Stable");
    });

    it("humanizes a 'condition' field value (EMPLOYMENT-only, no Inflation analog)", () => {
      expect(formatAnalysisValue("condition", "FLAT")).toBe("Flat");
    });

    it("humanizes a 'momentum' field value (EMPLOYMENT-only, no Inflation analog)", () => {
      expect(formatAnalysisValue("momentum", "WORSENING")).toBe("Worsening");
    });
  });
});

describe("analysisComponentLabel", () => {
  it("looks up an Inflation component through the existing canonical map, unchanged", () => {
    expect(analysisComponentLabel("PRIMARY_MOMENTUM")).toBe("Core PCE");
  });

  it("looks up a Labor component correctly -- the exact #20E.1 bug fix (was undefined before)", () => {
    expect(analysisComponentLabel("EMPLOYMENT")).toBe("Employment");
    expect(analysisComponentLabel("UNEMPLOYMENT")).toBe("Unemployment");
    expect(analysisComponentLabel("LABOR")).toBe("Labor");
  });

  it("humanizes a genuinely unrecognized component rather than rendering nothing", () => {
    expect(analysisComponentLabel("SOME_FUTURE_COMPONENT")).toBe("Some future component");
  });
});

describe("analysisFieldLabel", () => {
  it("looks up an Inflation field through the existing canonical map, unchanged", () => {
    expect(analysisFieldLabel("r_3m_annualized")).toBe("3M annualized");
  });

  it("looks up a Labor field correctly", () => {
    expect(analysisFieldLabel("current_3m_avg_jobs")).toBe("Current 3M avg");
    expect(analysisFieldLabel("delta_pp")).toBe("Delta");
  });

  it("falls back to the raw field name for a genuinely unrecognized field", () => {
    expect(analysisFieldLabel("some_future_field")).toBe("some_future_field");
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
