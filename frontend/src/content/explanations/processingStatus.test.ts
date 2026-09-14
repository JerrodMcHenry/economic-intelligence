/**
 * Content-coverage tests for Increment #19C's curated explanation
 * registry, mirroring content/explanations/releases.test.ts's own
 * discipline: exact-string checks for product invariants, concept
 * checks for everything else.
 */
import { describe, expect, it } from "vitest";

import {
  CHECK_INCOMPLETE,
  DETECTED_CHANGES_DATA_BASIS,
  NEW_OBSERVATION,
  processingStatusExplanation,
  REVISION_DETECTED,
  TRACKED_ANALYSIS_CHANGE,
} from "./processingStatus";

const ALL_STATUSES = ["NOT_CHECKED", "NO_CHANGE", "CHANGES_DETECTED", "PARTIAL_CHECK", "CHECK_FAILED"] as const;

describe("processingStatusExplanation", () => {
  it.each(ALL_STATUSES)("resolves a well-formed explanation for %s", (status) => {
    const explanation = processingStatusExplanation(status);
    expect(explanation.id.length).toBeGreaterThan(0);
    expect(explanation.title.length).toBeGreaterThan(0);
    expect(explanation.definition.length).toBeGreaterThan(0);
  });

  it("NOT_CHECKED never claims EI has never attempted a check -- only that no durable record exists", () => {
    const explanation = processingStatusExplanation("NOT_CHECKED");
    expect(explanation.definition).not.toMatch(/never (checked|attempted)/i);
    expect(explanation.definition).toMatch(/no durable processing record/i);
  });

  it("CHECK_FAILED never mentions provider error internals", () => {
    const explanation = processingStatusExplanation("CHECK_FAILED");
    expect(explanation.definition).not.toMatch(/exception|stack trace|error code|timeout/i);
  });

  it("PARTIAL_CHECK reuses the exact CHECK_INCOMPLETE explanation", () => {
    expect(processingStatusExplanation("PARTIAL_CHECK")).toBe(CHECK_INCOMPLETE);
  });
});

describe("standalone explanations", () => {
  it("NEW_OBSERVATION and REVISION_DETECTED's own definitions never claim publication/correction/finalization", () => {
    // `definition` is the claim this project makes about what #18/#19B
    // actually detected; `whyItMatters` may still use "published" in
    // its ordinary, descriptive sense (e.g. explaining why revisions
    // happen after a provider's original publication) without
    // asserting that #19C's own detection IS a publication event.
    for (const explanation of [NEW_OBSERVATION, REVISION_DETECTED]) {
      expect(explanation.definition).not.toMatch(/published|corrected|finalized/i);
    }
  });

  it("TRACKED_ANALYSIS_CHANGE explicitly states the two evidence lists are not one-to-one cause and effect", () => {
    expect(TRACKED_ANALYSIS_CHANGE.whyItMatters).toMatch(/not a one-to-one cause and effect/i);
  });

  it("DETECTED_CHANGES_DATA_BASIS states EI does not reconstruct the original historical release vintage", () => {
    expect(DETECTED_CHANGES_DATA_BASIS.definition).toMatch(/do not reconstruct the original historical release vintage/i);
  });
});
