/**
 * #56C: "Latest data detected" on /jobs must describe the most recent
 * Employment Situation occurrence that has ARRIVED -- never a scheduled
 * future one. Found in browser acceptance: the page read "Latest data
 * detected: December 4, 2026 -- Not yet checked" in September, because
 * the backend lists future occurrences first and the component took
 * `items[0]`.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { buildLatestCheck, buildReleaseProcessingStatusItem } from "../../test/fixtures/processingStatus";
import { LatestDataDetected } from "./LatestDataDetected";

const future = buildReleaseProcessingStatusItem({
  scheduled_date: "2026-12-04",
  latest_check: buildLatestCheck({ status: "NOT_CHECKED", checked_at: null }),
});
const arrived = buildReleaseProcessingStatusItem({
  scheduled_date: "2026-09-04",
  latest_check: buildLatestCheck({ status: "NO_CHANGE", checked_at: "2026-09-04T13:00:00Z" }),
});

describe("labor LatestDataDetected", () => {
  it("skips scheduled future occurrences and shows the latest that has arrived", () => {
    render(<LatestDataDetected items={[future, arrived]} today="2026-09-25" />);

    expect(screen.getByText(/September 4, 2026/)).toBeInTheDocument();
    expect(screen.queryByText(/December 4, 2026/)).not.toBeInTheDocument();
  });

  it("counts an occurrence scheduled today as arrived", () => {
    render(<LatestDataDetected items={[future, arrived]} today="2026-12-04" />);
    expect(screen.getByText(/December 4, 2026/)).toBeInTheDocument();
  });

  it("says so honestly when nothing has arrived yet", () => {
    render(<LatestDataDetected items={[future]} today="2026-09-25" />);
    expect(screen.getByText("No tracked release processing records are available yet.")).toBeInTheDocument();
  });
});
