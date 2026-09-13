import { describe, expect, it } from "vitest";

import { formatMetricValueOrUnavailable, formatPercent, formatPercentagePoints, formatPeriod, formatPeriodPair } from "./format";

describe("formatPeriod", () => {
  it("formats an ISO date as Month Year", () => {
    expect(formatPeriod("2026-07-01")).toBe("July 2026");
  });

  it("formats a January date correctly (month-index boundary)", () => {
    expect(formatPeriod("2026-01-01")).toBe("January 2026");
  });

  it("formats a December date correctly (month-index boundary)", () => {
    expect(formatPeriod("2026-12-01")).toBe("December 2026");
  });

  it("renders null as an honest 'no data' message, never a fabricated date", () => {
    expect(formatPeriod(null)).toBe("No data available");
  });

  it("falls back to the raw string for an unrecognized shape rather than guessing", () => {
    expect(formatPeriod("not-a-date")).toBe("not-a-date");
  });
});

describe("formatPeriodPair", () => {
  it("renders a single period when previous and current are the same", () => {
    expect(formatPeriodPair("2026-07-01", "2026-07-01")).toBe("July 2026");
  });

  it("renders an arrow pair when previous and current differ", () => {
    expect(formatPeriodPair("2026-06-01", "2026-07-01")).toBe("June 2026 → July 2026");
  });

  it("renders the null message when both periods are null", () => {
    expect(formatPeriodPair(null, null)).toBe("No data available");
  });
});

describe("formatPercent", () => {
  it("rounds a raw rate to two decimal places with a trailing percent sign", () => {
    expect(formatPercent(2.643912)).toBe("2.64%");
  });

  it("does not force a leading sign on a positive value", () => {
    expect(formatPercent(2.64)).toBe("2.64%");
  });

  it("preserves a negative sign naturally without forcing it", () => {
    expect(formatPercent(-0.5)).toBe("-0.50%");
  });

  it("renders null as an em dash, never a fabricated 0%", () => {
    expect(formatPercent(null)).toBe("—");
  });
});

describe("formatPercentagePoints", () => {
  it("force-signs a positive delta with a leading plus and a pp suffix", () => {
    expect(formatPercentagePoints(0.70123)).toBe("+0.70 pp");
  });

  it("force-signs a negative delta with a leading minus", () => {
    expect(formatPercentagePoints(-0.2)).toBe("-0.20 pp");
  });

  it("force-signs exactly zero as positive", () => {
    expect(formatPercentagePoints(0)).toBe("+0.00 pp");
  });

  it("renders null as an em dash", () => {
    expect(formatPercentagePoints(null)).toBe("—");
  });
});

describe("formatMetricValueOrUnavailable", () => {
  it("formats a numeric ChangeEvent value as a percent", () => {
    expect(formatMetricValueOrUnavailable(2.5)).toBe("2.50%");
  });

  it("passes a string ChangeEvent value through unchanged", () => {
    expect(formatMetricValueOrUnavailable("STABLE")).toBe("STABLE");
  });

  it("renders null as 'Unavailable', distinct from a numeric zero", () => {
    expect(formatMetricValueOrUnavailable(null)).toBe("Unavailable");
  });
});
