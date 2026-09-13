import { describe, expect, it } from "vitest";

import { isShortenedLabel, releaseCategory, releaseDisplayLabel } from "./releasePresentation";
import { buildReleaseOccurrenceItem } from "../test/fixtures/releases";

describe("releaseDisplayLabel", () => {
  it("shortens the curated long names the map defines", () => {
    const jolts = buildReleaseOccurrenceItem({
      provider_release_id: "192",
      name: "Job Openings and Labor Turnover Survey",
    });
    expect(releaseDisplayLabel(jolts)).toBe("JOLTS");

    const retailSales = buildReleaseOccurrenceItem({
      provider_release_id: "9",
      name: "Advance Monthly Sales for Retail and Food Services",
    });
    expect(releaseDisplayLabel(retailSales)).toBe("Advance Retail Sales");
  });

  it("falls back to the canonical name for a curated release with no shortLabel entry", () => {
    const cpi = buildReleaseOccurrenceItem({ provider_release_id: "10", name: "Consumer Price Index" });
    expect(releaseDisplayLabel(cpi)).toBe("Consumer Price Index");
  });

  it("falls back to the canonical name for a release not in the presentation map at all", () => {
    const unknown = buildReleaseOccurrenceItem({ provider_release_id: "999", name: "Some Future Release" });
    expect(releaseDisplayLabel(unknown)).toBe("Some Future Release");
  });

  it("never mutates the canonical name -- the source object is untouched", () => {
    const jolts = buildReleaseOccurrenceItem({ provider_release_id: "192", name: "Job Openings and Labor Turnover Survey" });
    releaseDisplayLabel(jolts);
    expect(jolts.name).toBe("Job Openings and Labor Turnover Survey");
  });
});

describe("isShortenedLabel", () => {
  it("is true when a shortLabel entry actually changes the displayed text", () => {
    const jolts = buildReleaseOccurrenceItem({ provider_release_id: "192", name: "Job Openings and Labor Turnover Survey" });
    expect(isShortenedLabel(jolts)).toBe(true);
  });

  it("is false when the canonical name is shown as-is", () => {
    const cpi = buildReleaseOccurrenceItem({ provider_release_id: "10", name: "Consumer Price Index" });
    expect(isShortenedLabel(cpi)).toBe(false);
  });

  it("is false for a release not in the presentation map", () => {
    const unknown = buildReleaseOccurrenceItem({ provider_release_id: "999", name: "Some Future Release" });
    expect(isShortenedLabel(unknown)).toBe(false);
  });
});

describe("releaseCategory", () => {
  it.each([
    ["10", "Inflation"],
    ["54", "Inflation / Consumer"],
    ["50", "Labor"],
    ["192", "Labor"],
    ["53", "Growth"],
    ["9", "Consumer"],
  ] as const)("maps curated provider_release_id %s to category %s", (provider_release_id, expected) => {
    expect(releaseCategory({ provider_release_id })).toBe(expected);
  });

  it("returns null for a release not in the curated V1 category map", () => {
    expect(releaseCategory({ provider_release_id: "999" })).toBeNull();
  });
});
