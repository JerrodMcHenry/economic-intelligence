/**
 * Unit tests for `lib/ratesFormat` (Increment #30).
 *
 * These functions decide how a backend number READS; they never decide
 * what it is. The properties worth protecting are therefore: a missing
 * value never becomes a zero, a sign is never lost, a session window is
 * never relabelled as a calendar period, and a date never shifts by a
 * timezone.
 */
import { describe, expect, it } from "vitest";

import {
  changeDirection,
  describeDirection,
  describeUnavailableReason,
  formatBasisPointLevel,
  formatBasisPoints,
  formatChangeWindow,
  formatObservationDate,
  formatPercentileOrdinal,
  formatRateValue,
  maturityLabel,
} from "./ratesFormat";

describe("formatObservationDate", () => {
  it("renders a day-precision date", () => {
    expect(formatObservationDate("2026-09-18")).toBe("Sep 18, 2026");
    expect(formatObservationDate("2026-01-05")).toBe("Jan 5, 2026");
  });

  it("takes the date part of a timestamp without shifting it", () => {
    // An ISO timestamp with a negative offset must not roll back a day.
    expect(formatObservationDate("2026-09-19T17:04:54.461189-07:00")).toBe("Sep 19, 2026");
    expect(formatObservationDate("2026-01-01T00:00:00Z")).toBe("Jan 1, 2026");
  });

  it("says so honestly when there is no date", () => {
    expect(formatObservationDate(null)).toBe("No data available");
  });

  it("shows an unrecognized value rather than guessing", () => {
    expect(formatObservationDate("not-a-date")).toBe("not-a-date");
  });
});

describe("formatRateValue", () => {
  it("renders a yield to two decimals", () => {
    expect(formatRateValue(5.01)).toBe("5.01%");
    expect(formatRateValue(2.5)).toBe("2.50%");
  });

  it("renders an unavailable value as a dash, never as zero", () => {
    expect(formatRateValue(null)).toBe("—");
    expect(formatRateValue(null)).not.toBe("0.00%");
  });

  it("renders a genuine zero as zero", () => {
    expect(formatRateValue(0)).toBe("0.00%");
  });
});

describe("formatBasisPoints", () => {
  it("signs a change explicitly", () => {
    expect(formatBasisPoints(25)).toBe("+25 bp");
    expect(formatBasisPoints(-2)).toBe("−2 bp");
  });

  it("uses a true minus sign rather than a hyphen", () => {
    expect(formatBasisPoints(-14)).toContain("−");
    expect(formatBasisPoints(-14)).not.toContain("-");
  });

  it("renders no change as an unsigned zero", () => {
    expect(formatBasisPoints(0)).toBe("0 bp");
  });

  it("renders unavailable as a dash, never as 0 bp", () => {
    expect(formatBasisPoints(null)).toBe("—");
  });

  it("keeps one decimal only when it carries information", () => {
    expect(formatBasisPoints(7.0)).toBe("+7 bp");
    expect(formatBasisPoints(7.5)).toBe("+7.5 bp");
  });
});

describe("formatBasisPointLevel", () => {
  it("renders a spread level unsigned when positive", () => {
    expect(formatBasisPointLevel(25)).toBe("25 bp");
  });

  it("renders an inversion as negative", () => {
    expect(formatBasisPointLevel(-42)).toBe("−42 bp");
  });

  it("renders unavailable as a dash", () => {
    expect(formatBasisPointLevel(null)).toBe("—");
  });
});

describe("direction", () => {
  it("classifies a change without implying good or bad", () => {
    expect(changeDirection(5)).toBe("up");
    expect(changeDirection(-5)).toBe("down");
    expect(changeDirection(0)).toBe("flat");
    expect(changeDirection(null)).toBe("unavailable");
  });

  it("describes direction in neutral words", () => {
    expect(describeDirection("up")).toBe("higher");
    expect(describeDirection("down")).toBe("lower");
    expect(describeDirection("flat")).toBe("unchanged");
    // Never "improved"/"worsened"/"positive"/"negative".
    for (const direction of ["up", "down", "flat"] as const) {
      expect(describeDirection(direction)).not.toMatch(/good|bad|positive|negative|improv|worse/i);
    }
  });
});

describe("formatChangeWindow", () => {
  it("preserves session semantics exactly", () => {
    expect(formatChangeWindow("1_SESSION")).toBe("1 session");
    expect(formatChangeWindow("5_SESSIONS")).toBe("5 sessions");
    expect(formatChangeWindow("21_SESSIONS")).toBe("21 sessions");
    expect(formatChangeWindow("63_SESSIONS")).toBe("63 sessions");
  });

  it("never relabels a window as a calendar period", () => {
    for (const window of ["1_SESSION", "5_SESSIONS", "21_SESSIONS", "63_SESSIONS"] as const) {
      expect(formatChangeWindow(window)).not.toMatch(/day|week|month|year/i);
    }
  });
});

describe("formatPercentileOrdinal", () => {
  it("renders an already-computed rank as an ordinal", () => {
    expect(formatPercentileOrdinal(0.566372)).toBe("57th");
    expect(formatPercentileOrdinal(0.01)).toBe("1st");
    expect(formatPercentileOrdinal(0.02)).toBe("2nd");
    expect(formatPercentileOrdinal(0.03)).toBe("3rd");
    expect(formatPercentileOrdinal(0.21)).toBe("21st");
  });

  it("handles the teens correctly", () => {
    expect(formatPercentileOrdinal(0.11)).toBe("11th");
    expect(formatPercentileOrdinal(0.12)).toBe("12th");
    expect(formatPercentileOrdinal(0.13)).toBe("13th");
  });

  it("keeps the extremes rather than clamping them away", () => {
    expect(formatPercentileOrdinal(0)).toBe("0th");
    expect(formatPercentileOrdinal(1)).toBe("100th");
  });

  it("renders unavailable as a dash", () => {
    expect(formatPercentileOrdinal(null)).toBe("—");
  });
});

describe("describeUnavailableReason", () => {
  it("explains a missing shared date as not-calculated rather than estimated", () => {
    expect(describeUnavailableReason("NO_EXACTLY_SHARED_OBSERVATION_DATE")).toContain("not calculated rather than estimated");
  });

  it("distinguishes one missing series from both", () => {
    expect(describeUnavailableReason("NO_OBSERVATIONS_FOR_ONE_SERIES")).toContain("One of the two");
    expect(describeUnavailableReason("NO_OBSERVATIONS_FOR_EITHER_SERIES")).toContain("Neither");
  });
});

describe("maturityLabel", () => {
  it("shortens a canonical series id", () => {
    expect(maturityLabel("UST_NOMINAL_10Y")).toBe("10Y");
    expect(maturityLabel("UST_REAL_5Y")).toBe("5Y");
  });

  it("falls back to the id it was given", () => {
    expect(maturityLabel("SOMETHING_ELSE")).toBe("SOMETHING_ELSE");
  });
});
