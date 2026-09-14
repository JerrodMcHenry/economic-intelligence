import { describe, expect, it } from "vitest";

import { formatJobs, formatLaborMetricValue, formatRawObservationValue } from "./laborFormat";

describe("formatJobs -- already-converted actual-jobs summary metrics (docs/architecture/labor-ui-v1.md §15/§18)", () => {
  it("comma-groups a large negative job count, rounded to a whole number", () => {
    expect(formatJobs(-331333.33)).toBe("-331,333");
  });

  it("comma-groups a large positive job count", () => {
    expect(formatJobs(286000)).toBe("286,000");
  });

  it("never divides by 1,000 -- the backend value is already actual jobs", () => {
    // The exact real August 2009 current_3m_avg_jobs value from the
    // frozen research (research/labor_momentum/outputs/v2_critical_months.csv):
    // -331,333.33 actual jobs, NOT -331.33 (which would be the still-in-thousands value).
    const formatted = formatJobs(-331333.33);
    expect(formatted).not.toBe("-331");
    expect(formatted).not.toBe("-331.33");
  });

  it("renders null as an em dash, never a fabricated zero", () => {
    expect(formatJobs(null)).toBe("—");
  });

  it("rounds a fractional job count to a whole number -- a fractional job has no meaning", () => {
    expect(formatJobs(1234.7)).toBe("1,235");
  });
});

describe("formatRawObservationValue -- raw FRED-native evidence, never converted (§15)", () => {
  it("formats a raw PAYEMS thousands-of-persons value verbatim, comma-grouped, no conversion", () => {
    // The real August 2009 PAYEMS raw observation: 130,472 (thousands
    // of persons) -- must render as-is, never multiplied by 1,000 into
    // "130,472,000" and never confused with the actual-jobs summary tier.
    expect(formatRawObservationValue(130472)).toBe("130,472");
  });

  it("never multiplies a raw value by 1,000", () => {
    expect(formatRawObservationValue(130472)).not.toBe("130,472,000");
  });

  it("renders null as 'Unavailable', matching the evidence-table convention", () => {
    expect(formatRawObservationValue(null)).toBe("Unavailable");
  });
});

describe("formatLaborMetricValue -- field-aware dispatch, never blanket percent formatting (§16)", () => {
  it("formats Employment's job-count fields with formatJobs, never formatPercent", () => {
    const formatted = formatLaborMetricValue("current_3m_avg_jobs", -331333.33);
    expect(formatted).toBe("-331,333");
    expect(formatted).not.toMatch(/%/);
  });

  it("formats momentum_delta_jobs with formatJobs", () => {
    expect(formatLaborMetricValue("momentum_delta_jobs", 286000)).toBe("286,000");
  });

  it("formats Unemployment's delta_pp with the signed percentage-point formatter", () => {
    expect(formatLaborMetricValue("delta_pp", -0.2)).toBe("-0.20 pp");
    expect(formatLaborMetricValue("delta_pp", 0.35)).toBe("+0.35 pp");
  });

  it("formats Unemployment's current_3m_avg/prior_year_3m_avg as plain rate percentages", () => {
    expect(formatLaborMetricValue("current_3m_avg", 4.0)).toBe("4.00%");
    expect(formatLaborMetricValue("prior_year_3m_avg", 4.1)).toBe("4.10%");
  });

  it("never applies job-count formatting to a percentage field", () => {
    const formatted = formatLaborMetricValue("current_3m_avg", 4.0);
    expect(formatted).not.toBe("4");
  });

  it("renders null as 'Unavailable' regardless of field", () => {
    expect(formatLaborMetricValue("current_3m_avg_jobs", null)).toBe("Unavailable");
    expect(formatLaborMetricValue("delta_pp", null)).toBe("Unavailable");
  });
});
