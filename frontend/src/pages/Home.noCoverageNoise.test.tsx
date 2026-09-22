/**
 * `/` shows no coverage/bootstrap noise (Increment #42A).
 *
 * #42 established that 1,488 of the 1,899 local Structured
 * Intelligence objects are COVERAGE, and that all 44 "ECONOMIC"
 * analysis changes are `UNAVAILABLE -> x` first computations.
 * `homepage_presentation_v1.0` keeps that class of event out of THE
 * LEDE -- but three LEGACY sections below it rendered the same events
 * unfiltered, which made the policy decorative.
 *
 * Those sections were removed from the homepage composition in #42A.
 * These tests keep them out.
 *
 * They render the page with backend fixtures that deliberately CONTAIN
 * the noise, so a regression cannot pass by the fixtures being clean.
 */
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { HomePage } from "./Home";
import { ThemeProvider } from "../theme/ThemeProvider";
import { buildLaborMonitor, buildLaborWhatChanged } from "../test/fixtures/labor";
import { buildMonitor, buildWhatChanged } from "../test/fixtures/inflation";
import { buildReleaseListResponse } from "../test/fixtures/releases";

vi.mock("../api/inflation");
vi.mock("../api/labor");
vi.mock("../api/processingStatus");
vi.mock("../api/releases");
vi.mock("../api/sinceLastVisit");
vi.mock("../api/intelligence");

const inflation = await import("../api/inflation");
const labor = await import("../api/labor");
const processingStatus = await import("../api/processingStatus");
const releases = await import("../api/releases");
const sinceLastVisit = await import("../api/sinceLastVisit");
const intelligence = await import("../api/intelligence");

/** An `UNAVAILABLE -> raw float` analysis change, exactly as recorded. */
const AVAILABILITY_RESTORED = {
  id: "analysis:inflation:HEADLINE_CPI:2026-08-01",
  type: "ANALYSIS_CHANGE",
  world: "inflation",
  concepts: ["us.cpi.headline.price-index.sa.monthly"],
  effective_period: "2026-08-01",
  recorded_at: "2026-09-19T18:46:27Z",
  published_at: null,
  knowledge_basis: "OBSERVED",
  basis: "METHODOLOGY_DERIVED",
  methodology: null,
  evidence: [],
  relations: [],
  limitations: [],
  contract_version: "intelligence_v1",
  payload: {
    component: "HEADLINE_CPI",
    event_type: "AVAILABILITY_RESTORED",
    change_class: "ECONOMIC",
    field: "r_12m",
    previous_value: "UNAVAILABLE",
    current_value: "3.353016322755642",
    delta: null,
    evaluation_period: "2026-08-01",
  },
};

const COVERAGE = { ...AVAILABILITY_RESTORED, id: "analysis:coverage", payload: { ...AVAILABILITY_RESTORED.payload, change_class: "COVERAGE" } };

beforeEach(() => {
  vi.mocked(inflation.getInflationMonitor).mockResolvedValue(buildMonitor());
  vi.mocked(inflation.getInflationWhatChanged).mockResolvedValue(buildWhatChanged());
  vi.mocked(labor.getLaborMonitor).mockResolvedValue(buildLaborMonitor());
  vi.mocked(labor.getLaborWhatChanged).mockResolvedValue(buildLaborWhatChanged());
  vi.mocked(releases.fetchUpcomingReleases).mockResolvedValue(buildReleaseListResponse({ releases: [] }));
  vi.mocked(releases.fetchRecentReleases).mockResolvedValue(buildReleaseListResponse({ releases: [] }));
  // Every noisy object the policy is supposed to exclude.
  vi.mocked(intelligence.listHomepageIntelligence).mockResolvedValue({
    items: [AVAILABILITY_RESTORED, COVERAGE],
    total: 2,
    limit: 100,
    offset: 0,
    contract_version: "intelligence_v1",
  } as never);
});

afterEach(() => vi.clearAllMocks());

async function renderHome(): Promise<string> {
  const { container } = render(
    <MemoryRouter>
      <ThemeProvider>
        <HomePage />
      </ThemeProvider>
    </MemoryRouter>,
  );
  await screen.findByRole("heading", { name: "Current State" });
  return container.textContent ?? "";
}

describe("the homepage renders no bootstrap noise", () => {
  it("never shows an `Unavailable →` transition", async () => {
    const text = await renderHome();
    expect(text).not.toContain("Unavailable →");
    expect(text).not.toContain("Unavailable ->");
  });

  it("never shows a raw unformatted internal value", async () => {
    const text = await renderHome();
    expect(text).not.toContain("3.353016322755642");
    // No bare long float anywhere on the page.
    expect(text).not.toMatch(/\d\.\d{8,}/);
  });

  it("never presents an availability-restored event as an economic change", async () => {
    const text = await renderHome();
    for (const phrase of ["Availability restored", "Availability lost", "became available", "Tracked analysis changes"]) {
      expect(text, phrase).not.toContain(phrase);
    }
  });

  it("does not render the delisted legacy sections", async () => {
    await renderHome();
    for (const heading of ["What Changed", "Recent Data Updates", "Since Your Last Check", "Recent Economic Activity"]) {
      expect(screen.queryByRole("heading", { name: heading }), heading).not.toBeInTheDocument();
    }
  });

  it("shows the quiet lede rather than promoting the noise into THE LEDE", async () => {
    // Both fixtures are ineligible, so nothing qualifies. The page must
    // not fall back to showing the freshest ineligible object.
    await renderHome();
    expect(screen.getByRole("heading", { name: "No new tracked change" })).toBeInTheDocument();
  });

  it("still orients the reader with canonical state and real paths", async () => {
    await renderHome();
    expect(screen.getByRole("heading", { name: "Current State" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Inflation and Jobs, side by side" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Inflation →" })).toHaveAttribute("href", "/inflation");
    expect(screen.getByRole("link", { name: "Open Jobs →" })).toHaveAttribute("href", "/jobs");
  });

  it("requests no release-processing status at all", async () => {
    await renderHome();
    // The section that consumed it is gone, so the homepage should not
    // still be paying for the request.
    expect(processingStatus.fetchReleaseProcessingStatus).not.toHaveBeenCalled();
    expect(sinceLastVisit.getSinceLastVisit).not.toHaveBeenCalled();
  });
});
