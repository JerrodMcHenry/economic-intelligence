import { describe, expect, it } from "vitest";

import { buildLatestCheck, buildReleaseProcessingStatusItem } from "../test/fixtures/processingStatus";
import { selectLatestDataDetectedItem } from "./selectLatestDataDetected";

describe("selectLatestDataDetectedItem", () => {
  it("returns null for an empty list", () => {
    expect(selectLatestDataDetectedItem([])).toBeNull();
  });

  it("THE SELECTION-RULE TEST: CHANGES_DETECTED beats a more-recently-scheduled NOT_CHECKED item, without reordering within a tier", () => {
    const futureNotChecked = buildReleaseProcessingStatusItem({
      occurrence_id: 1,
      scheduled_date: "2026-12-01",
      latest_check: buildLatestCheck({ status: "NOT_CHECKED", checked_at: null }),
    });
    const olderChangesDetected = buildReleaseProcessingStatusItem({
      occurrence_id: 2,
      scheduled_date: "2026-07-01",
      latest_check: buildLatestCheck({ status: "CHANGES_DETECTED" }),
    });
    // Backend order: future NOT_CHECKED first (scheduled_date DESC).
    const items = [futureNotChecked, olderChangesDetected];

    const selected = selectLatestDataDetectedItem(items);
    expect(selected?.occurrence_id).toBe(2);
  });

  it("honors the full priority order: CHANGES_DETECTED > PARTIAL_CHECK > CHECK_FAILED > NO_CHANGE > NOT_CHECKED", () => {
    const notChecked = buildReleaseProcessingStatusItem({ occurrence_id: 1, latest_check: buildLatestCheck({ status: "NOT_CHECKED", checked_at: null }) });
    const noChange = buildReleaseProcessingStatusItem({ occurrence_id: 2, latest_check: buildLatestCheck({ status: "NO_CHANGE" }) });
    const checkFailed = buildReleaseProcessingStatusItem({ occurrence_id: 3, latest_check: buildLatestCheck({ status: "CHECK_FAILED" }) });
    const partialCheck = buildReleaseProcessingStatusItem({ occurrence_id: 4, latest_check: buildLatestCheck({ status: "PARTIAL_CHECK" }) });
    const changesDetected = buildReleaseProcessingStatusItem({ occurrence_id: 5, latest_check: buildLatestCheck({ status: "CHANGES_DETECTED" }) });

    expect(selectLatestDataDetectedItem([notChecked, noChange])?.occurrence_id).toBe(2);
    expect(selectLatestDataDetectedItem([noChange, checkFailed])?.occurrence_id).toBe(3);
    expect(selectLatestDataDetectedItem([checkFailed, partialCheck])?.occurrence_id).toBe(4);
    expect(selectLatestDataDetectedItem([partialCheck, changesDetected])?.occurrence_id).toBe(5);
  });

  it("preserves backend order within one status tier (first match wins, never reordered)", () => {
    const first = buildReleaseProcessingStatusItem({ occurrence_id: 10, latest_check: buildLatestCheck({ status: "CHANGES_DETECTED" }) });
    const second = buildReleaseProcessingStatusItem({ occurrence_id: 11, latest_check: buildLatestCheck({ status: "CHANGES_DETECTED" }) });

    expect(selectLatestDataDetectedItem([first, second])?.occurrence_id).toBe(10);
  });

  it("falls back to NOT_CHECKED when it is the only status present", () => {
    const item = buildReleaseProcessingStatusItem({ latest_check: buildLatestCheck({ status: "NOT_CHECKED", checked_at: null }) });
    expect(selectLatestDataDetectedItem([item])?.latest_check.status).toBe("NOT_CHECKED");
  });
});
