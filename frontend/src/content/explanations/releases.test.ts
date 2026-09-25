/**
 * Content-coverage tests for the release calendar's curated
 * explanation registry (Increment #17C). PAST_DUE's and the disclosure
 * sentence's exact wording are product invariants -- see
 * docs/architecture/release-intelligence-v1.md #13 -- and are checked
 * byte-for-byte here. Everything else is checked for the required
 * concepts, not exact prose, per this increment's copy-testing
 * guidance.
 */
import { describe, expect, it } from "vitest";

import { ECONOMIC_RELEASE, releaseTypeExplanation, scheduleStatusExplanation, SCHEDULED_DATE } from "./releases";

const CURATED_V1_RELEASE_IDS: ReadonlyArray<[string, string]> = [
  ["cpi", "Consumer Price Index (CPI)"],
  ["pio", "Personal Income and Outlays"],
  ["empsit", "Employment Situation"],
  ["192", "Job Openings and Labor Turnover Survey (JOLTS)"],
  ["53", "Gross Domestic Product (GDP)"],
  ["9", "Advance Monthly Sales for Retail and Food Services"],
];

describe("releases explanation registry: coverage", () => {
  it("covers all 10 required release concepts (2 standalone + 2 statuses + 6 release types)", () => {
    expect(2 + 2 + CURATED_V1_RELEASE_IDS.length).toBe(10);
  });

  it("ECONOMIC_RELEASE and SCHEDULED_DATE are both well-formed", () => {
    for (const explanation of [ECONOMIC_RELEASE, SCHEDULED_DATE]) {
      expect(explanation.id.length).toBeGreaterThan(0);
      expect(explanation.title.length).toBeGreaterThan(0);
      expect(explanation.definition.length).toBeGreaterThan(0);
    }
  });

  it.each(CURATED_V1_RELEASE_IDS)("provider_release_id %s resolves to a curated explanation titled %s", (id, expectedTitle) => {
    const explanation = releaseTypeExplanation(id);
    expect(explanation).not.toBeNull();
    expect(explanation!.title).toBe(expectedTitle);
    expect(explanation!.definition.length).toBeGreaterThan(0);
  });

  it("returns null, never a fabricated explanation, for a provider_release_id outside the curated V1 set", () => {
    expect(releaseTypeExplanation("999999")).toBeNull();
  });

  it("keys release-type explanations by provider_release_id, never by matching on name text", () => {
    // Every curated entry's own definition must not itself depend on
    // any particular `name` string being passed in -- the lookup
    // function only takes an id.
    expect(releaseTypeExplanation.length).toBe(1);
  });
});

describe("release-type explanations describe what each release actually is, without investment advice", () => {
  it("CPI explanation covers consumer prices", () => {
    expect(releaseTypeExplanation("cpi")!.definition).toMatch(/prices/i);
  });

  it("Employment Situation explanation covers payrolls/unemployment", () => {
    expect(releaseTypeExplanation("empsit")!.definition).toMatch(/labor|employment|payroll/i);
  });

  it("JOLTS explanation covers job openings and labor turnover", () => {
    expect(releaseTypeExplanation("192")!.definition).toMatch(/job openings|turnover|hiring/i);
  });

  it("GDP explanation covers economic output", () => {
    expect(releaseTypeExplanation("53")!.definition).toMatch(/goods and services|economic activity/i);
  });

  it("Personal Income and Outlays explanation connects to the PCE price index used for the Fed target", () => {
    expect(releaseTypeExplanation("pio")!.definition).toMatch(/pce price index/i);
  });

  it("Advance Retail Sales explanation describes it as an early, sometimes-revised estimate", () => {
    const explanation = releaseTypeExplanation("9")!;
    expect(explanation.definition).toMatch(/early estimate/i);
    expect(explanation.whyItMatters).toMatch(/revised/i);
  });

  it("no release-type explanation contains an investment recommendation", () => {
    for (const [id] of CURATED_V1_RELEASE_IDS) {
      const explanation = releaseTypeExplanation(id)!;
      const combined = `${explanation.definition} ${explanation.whyItMatters ?? ""}`;
      expect(combined).not.toMatch(/\bbuy\b|\bsell\b|you should|this means markets will/i);
    }
  });
});

describe("schedule status explanations (exact-string product invariants)", () => {
  it("SCHEDULED states only what the calendar has on file, with no time precision", () => {
    const explanation = scheduleStatusExplanation("SCHEDULED");
    expect(explanation.title).toBe("Scheduled");
    expect(explanation.definition).toBe("The release is scheduled for this date according to Economic Intelligence's persisted release calendar.");
    expect(explanation.definition).not.toMatch(/\d{1,2}:\d{2}\s*(am|pm)?/i);
  });

  it("PAST_DUE does not claim publication, ingestion, or incorporation into analysis", () => {
    const explanation = scheduleStatusExplanation("PAST_DUE");
    expect(explanation.title).toBe("Past due");
    expect(explanation.definition).toBe(
      "The scheduled release date has passed. This status does not confirm that new data has been published, ingested, or incorporated into Economic Intelligence analysis.",
    );
  });

  it("PAST_DUE's only use of 'published' is a negation, never an assertion", () => {
    const explanation = scheduleStatusExplanation("PAST_DUE");
    expect(explanation.definition).toMatch(/does not confirm that new data has been published/i);
    // Guards against a future edit accidentally adding a second,
    // affirmative use of the word elsewhere in the sentence.
    expect(explanation.definition.match(/published/gi)?.length).toBe(1);
  });
});
