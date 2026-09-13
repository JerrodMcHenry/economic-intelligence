import { describe, expect, it } from "vitest";

import { formatCompactDate, formatFullDate, groupReleasesByDate, recentWindow, upcomingWindow } from "./releases";
import { buildReleaseOccurrenceItem } from "../test/fixtures/releases";

describe("upcomingWindow", () => {
  it("starts today and ends 45 days later, given an explicit reference date", () => {
    expect(upcomingWindow(new Date(2026, 8, 13))).toEqual({ start_date: "2026-09-13", end_date: "2026-10-28" });
  });

  it("crosses a month boundary correctly", () => {
    expect(upcomingWindow(new Date(2026, 0, 20))).toEqual({ start_date: "2026-01-20", end_date: "2026-03-06" });
  });
});

describe("recentWindow", () => {
  it("starts 30 days before today and ends today, given an explicit reference date", () => {
    expect(recentWindow(new Date(2026, 8, 13))).toEqual({ start_date: "2026-08-14", end_date: "2026-09-13" });
  });

  it("crosses a year boundary correctly", () => {
    expect(recentWindow(new Date(2026, 0, 5))).toEqual({ start_date: "2025-12-06", end_date: "2026-01-05" });
  });
});

describe("groupReleasesByDate", () => {
  it("groups adjacent releases sharing the same scheduled_date", () => {
    const releases = [
      buildReleaseOccurrenceItem({ release_id: 1, name: "A", scheduled_date: "2026-09-17" }),
      buildReleaseOccurrenceItem({ release_id: 2, name: "B", scheduled_date: "2026-09-17" }),
      buildReleaseOccurrenceItem({ release_id: 3, name: "C", scheduled_date: "2026-09-20" }),
    ];
    const groups = groupReleasesByDate(releases);
    expect(groups).toHaveLength(2);
    expect(groups[0]).toEqual({ scheduled_date: "2026-09-17", items: [releases[0], releases[1]] });
    expect(groups[1]).toEqual({ scheduled_date: "2026-09-20", items: [releases[2]] });
  });

  it("preserves input order within a date group -- never reorders", () => {
    const releases = [
      buildReleaseOccurrenceItem({ release_id: 5, name: "Z", scheduled_date: "2026-09-17" }),
      buildReleaseOccurrenceItem({ release_id: 2, name: "A", scheduled_date: "2026-09-17" }),
    ];
    const groups = groupReleasesByDate(releases);
    expect(groups[0]?.items.map((r) => r.name)).toEqual(["Z", "A"]);
  });

  it("returns an empty list for an empty input", () => {
    expect(groupReleasesByDate([])).toEqual([]);
  });

  it("gives every release its own group when no two share a date", () => {
    const releases = [
      buildReleaseOccurrenceItem({ release_id: 1, scheduled_date: "2026-09-01" }),
      buildReleaseOccurrenceItem({ release_id: 2, scheduled_date: "2026-09-02" }),
    ];
    expect(groupReleasesByDate(releases)).toHaveLength(2);
  });
});

describe("formatCompactDate", () => {
  it("formats an ISO date as an uppercase month abbreviation and day", () => {
    expect(formatCompactDate("2026-09-17")).toEqual({ month: "SEP", day: "17" });
  });

  it("does not zero-pad the day", () => {
    expect(formatCompactDate("2026-09-01")).toEqual({ month: "SEP", day: "1" });
  });

  it("never includes a time of day", () => {
    const { month, day } = formatCompactDate("2026-09-17");
    expect(`${month} ${day}`).not.toMatch(/\d{1,2}:\d{2}/);
  });
});

describe("formatFullDate", () => {
  it("formats an ISO date as a full month name, day, and year", () => {
    expect(formatFullDate("2026-09-17")).toBe("September 17, 2026");
  });

  it("formats a January date correctly (month-index boundary)", () => {
    expect(formatFullDate("2026-01-01")).toBe("January 1, 2026");
  });
});
