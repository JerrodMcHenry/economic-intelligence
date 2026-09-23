/**
 * Integration-level tests for the Economic Overview product page
 * (Increment #19A, extended for #19C and #20E.2). All seven canonical
 * read calls (`getInflationMonitor`/`getInflationWhatChanged`/
 * `getLaborMonitor`/`getLaborWhatChanged`/`fetchReleaseProcessingStatus`/
 * `fetchUpcomingReleases`/`fetchRecentReleases`) are mocked at the
 * module boundary -- no live backend required, the same pattern
 * pages/Inflation.test.tsx, pages/Labor.test.tsx, and
 * pages/Releases.test.tsx already establish. Wrapped in MemoryRouter
 * since Overview links to `/inflation`/`/labor`/`/releases` via
 * react-router's `Link`.
 *
 * Detailed "Latest Data Detected" content rendering (status branches,
 * historical-evidence framing, sibling-structure, truncation) is
 * covered at the component level in
 * components/overview/LatestDataDetected.test.tsx -- this file covers
 * only the integration-level concerns: each resource's independence,
 * section placement, and page structure.
 */
import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { getInflationMonitor, getInflationWhatChanged } from "../api/inflation";
import { getLaborMonitor, getLaborWhatChanged } from "../api/labor";
import { fetchReleaseProcessingStatus } from "../api/processingStatus";
import { fetchRecentReleases, fetchUpcomingReleases } from "../api/releases";
import { getSinceLastVisit } from "../api/sinceLastVisit";
import { buildMomentum, buildMonitor, buildWhatChanged } from "../test/fixtures/inflation";
import { buildLaborMonitor, buildLaborWhatChanged } from "../test/fixtures/labor";
import { buildReleaseProcessingStatusResponse } from "../test/fixtures/processingStatus";
import { buildReleaseListResponse, buildReleaseOccurrenceItem } from "../test/fixtures/releases";
import { buildSinceLastVisitResponse } from "../test/fixtures/sinceLastVisit";
import { HomePage } from "./Home";

vi.mock("../api/inflation", () => ({
  getInflationMonitor: vi.fn(),
  getInflationWhatChanged: vi.fn(),
}));
vi.mock("../api/labor", () => ({
  getLaborMonitor: vi.fn(),
  getLaborWhatChanged: vi.fn(),
}));
vi.mock("../api/processingStatus", () => ({
  fetchReleaseProcessingStatus: vi.fn(),
}));
vi.mock("../api/releases", () => ({
  fetchUpcomingReleases: vi.fn(),
  fetchRecentReleases: vi.fn(),
}));
vi.mock("../api/sinceLastVisit", () => ({
  getSinceLastVisit: vi.fn(),
}));

const mockedGetMonitor = vi.mocked(getInflationMonitor);
const mockedGetWhatChanged = vi.mocked(getInflationWhatChanged);
const mockedGetLaborMonitor = vi.mocked(getLaborMonitor);
const mockedGetLaborWhatChanged = vi.mocked(getLaborWhatChanged);
const mockedFetchProcessingStatus = vi.mocked(fetchReleaseProcessingStatus);
const mockedFetchUpcoming = vi.mocked(fetchUpcomingReleases);
const mockedFetchRecent = vi.mocked(fetchRecentReleases);
const mockedGetSinceLastVisit = vi.mocked(getSinceLastVisit);

beforeEach(() => {
  mockedGetMonitor.mockReset();
  mockedGetWhatChanged.mockReset();
  mockedGetLaborMonitor.mockReset();
  mockedGetLaborWhatChanged.mockReset();
  mockedFetchProcessingStatus.mockReset();
  mockedFetchUpcoming.mockReset();
  mockedFetchRecent.mockReset();
  mockedGetSinceLastVisit.mockReset();
  // A safe default so every pre-existing test -- most of which set up
  // only the ONE resource they're specifically exercising, not every
  // resource via resolveAll() -- doesn't have to know about this new,
  // unrelated resource. Tests that specifically exercise Since Last
  // Visit override this via resolveAll({ sinceLastVisit: ... }) or a
  // direct mockedGetSinceLastVisit call.
  mockedGetSinceLastVisit.mockResolvedValue(buildSinceLastVisitResponse());
  window.localStorage.clear();
});

function resolveAll(overrides: {
  monitor?: ReturnType<typeof buildMonitor>;
  whatChanged?: ReturnType<typeof buildWhatChanged>;
  laborMonitor?: ReturnType<typeof buildLaborMonitor>;
  laborWhatChanged?: ReturnType<typeof buildLaborWhatChanged>;
  processingStatus?: ReturnType<typeof buildReleaseProcessingStatusResponse>;
  upcoming?: ReturnType<typeof buildReleaseListResponse>;
  recent?: ReturnType<typeof buildReleaseListResponse>;
  sinceLastVisit?: ReturnType<typeof buildSinceLastVisitResponse>;
} = {}) {
  mockedGetMonitor.mockResolvedValue(overrides.monitor ?? buildMonitor());
  mockedGetWhatChanged.mockResolvedValue(overrides.whatChanged ?? buildWhatChanged());
  mockedGetLaborMonitor.mockResolvedValue(overrides.laborMonitor ?? buildLaborMonitor());
  mockedGetLaborWhatChanged.mockResolvedValue(overrides.laborWhatChanged ?? buildLaborWhatChanged());
  mockedFetchProcessingStatus.mockResolvedValue(overrides.processingStatus ?? buildReleaseProcessingStatusResponse({ occurrences: [] }));
  mockedFetchUpcoming.mockResolvedValue(overrides.upcoming ?? buildReleaseListResponse({ releases: [] }));
  mockedFetchRecent.mockResolvedValue(overrides.recent ?? buildReleaseListResponse({ releases: [] }));
  mockedGetSinceLastVisit.mockResolvedValue(overrides.sinceLastVisit ?? buildSinceLastVisitResponse());
}

function renderPage() {
  return render(
    <MemoryRouter>
      <HomePage />
    </MemoryRouter>,
  );
}

async function findSection(name: string) {
  const heading = await screen.findByRole("heading", { name });
  return heading.closest("section") as HTMLElement;
}

describe("loading", () => {
  it("shows a stable loading state for every remaining resource, with no fabricated data", () => {
    mockedGetMonitor.mockReturnValue(new Promise(() => {}));
    mockedGetWhatChanged.mockReturnValue(new Promise(() => {}));
    mockedGetLaborMonitor.mockReturnValue(new Promise(() => {}));
    mockedGetLaborWhatChanged.mockReturnValue(new Promise(() => {}));
    mockedFetchProcessingStatus.mockReturnValue(new Promise(() => {}));
    mockedFetchUpcoming.mockReturnValue(new Promise(() => {}));
    mockedFetchRecent.mockReturnValue(new Promise(() => {}));

    renderPage();

    // #42A removed three legacy change surfaces from `/`, and their
    // loading skeletons went with them.
    expect(screen.getAllByRole("status").length).toBeGreaterThanOrEqual(4);
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
  });
});

describe("Current State", () => {
  it("renders Inflation and Labor as two labeled peer dimensions, not as the state of the economy", async () => {
    resolveAll({
      monitor: buildMonitor({ underlying_momentum: buildMomentum({ state: "MIXED" }) }),
      laborMonitor: buildLaborMonitor({ state: "COOLING" }),
    });
    renderPage();

    const section = await findSection("Current State");
    expect(within(section).getByText("Inflation")).toBeInTheDocument();
    expect(within(section).getByText("Mixed", { selector: "span" })).toBeInTheDocument();
    expect(within(section).getByText("Jobs")).toBeInTheDocument();
    expect(within(section).getByText("Cooling", { selector: "span" })).toBeInTheDocument();
    // Never a synthetic economy-wide label, never a combined score.
    expect(screen.queryByText(/Economy:/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Economic State/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Risk Level/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Macro Score/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Economy Score/i)).not.toBeInTheDocument();
  });

  it("THE CONTRADICTORY-EVIDENCE TEST: renders MIXED even when the raw numbers look STABLE", async () => {
    // r_3m/r_6m/r_12m all identical -- a human skimming the numbers
    // could read this as STABLE, but the backend says MIXED, and
    // Overview must show exactly that, never recompute it.
    resolveAll({
      monitor: buildMonitor({
        underlying_momentum: buildMomentum({
          state: "MIXED",
          r_3m_annualized: 2.5,
          r_6m_annualized: 2.5,
          r_12m: 2.5,
          lower_boundary: 2.4,
          upper_boundary: 2.6,
        }),
      }),
    });
    renderPage();

    const section = await findSection("Current State");
    expect(within(section).getByText("Mixed", { selector: "span" })).toBeInTheDocument();
    expect(within(section).queryByText("Stable", { selector: "span" })).not.toBeInTheDocument();
    expect(within(section).getByText("Why Mixed?")).toBeInTheDocument();
  });

  it("THE LABOR CONTRADICTORY-EVIDENCE TEST: renders backend LaborState even when the reader might expect otherwise", async () => {
    resolveAll({ laborMonitor: buildLaborMonitor({ state: "MIXED" }) });
    renderPage();

    const section = await findSection("Current State");
    expect(within(section).getByText("Mixed", { selector: "span" })).toBeInTheDocument();
    expect(within(section).getByText("Why Mixed?")).toBeInTheDocument();
  });

  it("no stale 'first monitor' note -- Labor is a real second monitor, not a placeholder", async () => {
    resolveAll();
    renderPage();

    await findSection("Current State");
    expect(
      screen.queryByText(/Inflation is the first fully deterministic monitor/i),
    ).not.toBeInTheDocument();
    for (const label of ["Growth", "Consumer", "Housing", "Financial Conditions"]) {
      expect(screen.queryByText(new RegExp(`^${label}\\s*(—|-)?\\s*Coming Soon`, "i"))).not.toBeInTheDocument();
    }
  });

  it("links to /inflation via 'Open Inflation' and /jobs via 'Open Jobs'", async () => {
    resolveAll();
    renderPage();

    const section = await findSection("Current State");
    expect(within(section).getByRole("link", { name: "Open Inflation →" })).toHaveAttribute("href", "/inflation");
    expect(within(section).getByRole("link", { name: "Open Jobs →" })).toHaveAttribute("href", "/jobs");
  });

  it("Inflation monitor fails; Labor's own Current State card still renders", async () => {
    mockedGetMonitor.mockRejectedValue(new Error("down"));
    mockedGetWhatChanged.mockResolvedValue(buildWhatChanged());
    mockedGetLaborMonitor.mockResolvedValue(buildLaborMonitor({ state: "STABLE" }));
    mockedGetLaborWhatChanged.mockResolvedValue(buildLaborWhatChanged());
    mockedFetchProcessingStatus.mockResolvedValue(buildReleaseProcessingStatusResponse({ occurrences: [] }));
    mockedFetchUpcoming.mockResolvedValue(buildReleaseListResponse({ releases: [] }));
    mockedFetchRecent.mockResolvedValue(buildReleaseListResponse({ releases: [] }));
    renderPage();

    const section = await findSection("Current State");
    expect(within(section).getByText("Inflation data could not be loaded.")).toBeInTheDocument();
    expect(within(section).getByText("Jobs")).toBeInTheDocument();
    expect(within(section).getByText("Stable", { selector: "span" })).toBeInTheDocument();
  });

  it("Labor monitor fails; Inflation's own Current State card still renders", async () => {
    mockedGetMonitor.mockResolvedValue(buildMonitor({ underlying_momentum: buildMomentum({ state: "STABLE" }) }));
    mockedGetWhatChanged.mockResolvedValue(buildWhatChanged());
    mockedGetLaborMonitor.mockRejectedValue(new Error("down"));
    mockedGetLaborWhatChanged.mockResolvedValue(buildLaborWhatChanged());
    mockedFetchProcessingStatus.mockResolvedValue(buildReleaseProcessingStatusResponse({ occurrences: [] }));
    mockedFetchUpcoming.mockResolvedValue(buildReleaseListResponse({ releases: [] }));
    mockedFetchRecent.mockResolvedValue(buildReleaseListResponse({ releases: [] }));
    renderPage();

    const section = await findSection("Current State");
    expect(within(section).getByText("Jobs data could not be loaded.")).toBeInTheDocument();
    expect(within(section).getByText("Inflation")).toBeInTheDocument();
    expect(within(section).getByText("Stable", { selector: "span" })).toBeInTheDocument();
  });
});

describe("Inflation and Jobs, side by side (Increment #23C; heading corrected in #45B)", () => {
  it("renders the exact same-period composition sentence when both periods match", async () => {
    resolveAll({
      monitor: buildMonitor({ underlying_momentum: buildMomentum({ state: "COOLING", calculation_period: "2026-07-01" }) }),
      laborMonitor: buildLaborMonitor({ state: "STRENGTHENING", evaluation_period: "2026-07-01" }),
    });
    renderPage();

    const section = await findSection("Inflation and Jobs, side by side");
    expect(within(section).getByText("As of July 2026, Inflation is Cooling while Jobs is Strengthening.")).toBeInTheDocument();
  });

  it("renders the exact different-period composition sentence, both periods visible, when periods differ", async () => {
    resolveAll({
      monitor: buildMonitor({ underlying_momentum: buildMomentum({ state: "COOLING", calculation_period: "2026-07-01" }) }),
      laborMonitor: buildLaborMonitor({ state: "STRENGTHENING", evaluation_period: "2026-08-01" }),
    });
    renderPage();

    const section = await findSection("Inflation and Jobs, side by side");
    expect(
      within(section).getByText("Inflation is Cooling as of July 2026. Jobs is Strengthening as of August 2026."),
    ).toBeInTheDocument();
    expect(within(section).queryByText(/\bwhile\b/i)).not.toBeInTheDocument();
  });

  it("Inflation insufficient, Labor sufficient: no relationship sentence, Labor's own fact plus the unavailable fragment", async () => {
    resolveAll({
      monitor: buildMonitor({ underlying_momentum: buildMomentum({ state: "INSUFFICIENT_DATA", calculation_period: null }) }),
      laborMonitor: buildLaborMonitor({ state: "STABLE", evaluation_period: "2026-07-01" }),
    });
    renderPage();

    const section = await findSection("Inflation and Jobs, side by side");
    expect(
      within(section).getByText("Jobs is Stable as of July 2026. Inflation does not currently have enough data to classify its state."),
    ).toBeInTheDocument();
  });

  it("Labor insufficient, Inflation sufficient: mirror", async () => {
    resolveAll({
      monitor: buildMonitor({ underlying_momentum: buildMomentum({ state: "HEATING", calculation_period: "2026-07-01" }) }),
      laborMonitor: buildLaborMonitor({ state: "INSUFFICIENT_DATA", evaluation_period: null }),
    });
    renderPage();

    const section = await findSection("Inflation and Jobs, side by side");
    expect(
      within(section).getByText("Inflation is Heating as of July 2026. Jobs does not currently have enough data to classify its state."),
    ).toBeInTheDocument();
  });

  it("both insufficient: one combined statement, no per-side fragments", async () => {
    resolveAll({
      monitor: buildMonitor({ underlying_momentum: buildMomentum({ state: "INSUFFICIENT_DATA", calculation_period: null }) }),
      laborMonitor: buildLaborMonitor({ state: "INSUFFICIENT_DATA", evaluation_period: null }),
    });
    renderPage();

    const section = await findSection("Inflation and Jobs, side by side");
    expect(
      within(section).getByText("Not enough data is currently available to describe how Inflation and Jobs relate."),
    ).toBeInTheDocument();
  });

  it("Inflation resource error: no relationship sentence, Labor's own fact still renders, existing error message shown", async () => {
    mockedGetMonitor.mockRejectedValue(new Error("down"));
    mockedGetWhatChanged.mockResolvedValue(buildWhatChanged());
    mockedGetLaborMonitor.mockResolvedValue(buildLaborMonitor({ state: "STABLE" }));
    mockedGetLaborWhatChanged.mockResolvedValue(buildLaborWhatChanged());
    mockedFetchProcessingStatus.mockResolvedValue(buildReleaseProcessingStatusResponse({ occurrences: [] }));
    mockedFetchUpcoming.mockResolvedValue(buildReleaseListResponse({ releases: [] }));
    mockedFetchRecent.mockResolvedValue(buildReleaseListResponse({ releases: [] }));
    renderPage();

    const section = await findSection("Inflation and Jobs, side by side");
    expect(within(section).getByText("Inflation data could not be loaded.")).toBeInTheDocument();
    // Not the insufficient-data fragment -- a resource error is a
    // different, distinct case (§10) and must never be composed as if
    // the state had been successfully learned as INSUFFICIENT_DATA.
    expect(within(section).queryByText(/does not currently have enough data/i)).not.toBeInTheDocument();
    expect(within(section).queryByText(/Inflation is/)).not.toBeInTheDocument();
  });

  it("Labor resource error: mirror", async () => {
    mockedGetMonitor.mockResolvedValue(buildMonitor({ underlying_momentum: buildMomentum({ state: "STABLE" }) }));
    mockedGetWhatChanged.mockResolvedValue(buildWhatChanged());
    mockedGetLaborMonitor.mockRejectedValue(new Error("down"));
    mockedGetLaborWhatChanged.mockResolvedValue(buildLaborWhatChanged());
    mockedFetchProcessingStatus.mockResolvedValue(buildReleaseProcessingStatusResponse({ occurrences: [] }));
    mockedFetchUpcoming.mockResolvedValue(buildReleaseListResponse({ releases: [] }));
    mockedFetchRecent.mockResolvedValue(buildReleaseListResponse({ releases: [] }));
    renderPage();

    const section = await findSection("Inflation and Jobs, side by side");
    expect(within(section).getByText("Jobs data could not be loaded.")).toBeInTheDocument();
    expect(within(section).queryByText(/does not currently have enough data/i)).not.toBeInTheDocument();
  });

  it("both resources error: both existing error messages, no relationship sentence", async () => {
    mockedGetMonitor.mockRejectedValue(new Error("down"));
    mockedGetWhatChanged.mockResolvedValue(buildWhatChanged());
    mockedGetLaborMonitor.mockRejectedValue(new Error("down"));
    mockedGetLaborWhatChanged.mockResolvedValue(buildLaborWhatChanged());
    mockedFetchProcessingStatus.mockResolvedValue(buildReleaseProcessingStatusResponse({ occurrences: [] }));
    mockedFetchUpcoming.mockResolvedValue(buildReleaseListResponse({ releases: [] }));
    mockedFetchRecent.mockResolvedValue(buildReleaseListResponse({ releases: [] }));
    renderPage();

    const section = await findSection("Inflation and Jobs, side by side");
    expect(within(section).getByText("Inflation data could not be loaded.")).toBeInTheDocument();
    expect(within(section).getByText("Jobs data could not be loaded.")).toBeInTheDocument();
  });

  it("no partial relationship sentence renders while either resource is still loading", () => {
    mockedGetMonitor.mockReturnValue(new Promise(() => {}));
    mockedGetWhatChanged.mockReturnValue(new Promise(() => {}));
    mockedGetLaborMonitor.mockResolvedValue(buildLaborMonitor({ state: "STRENGTHENING" }));
    mockedGetLaborWhatChanged.mockResolvedValue(buildLaborWhatChanged());
    mockedFetchProcessingStatus.mockResolvedValue(buildReleaseProcessingStatusResponse({ occurrences: [] }));
    mockedFetchUpcoming.mockResolvedValue(buildReleaseListResponse({ releases: [] }));
    mockedFetchRecent.mockResolvedValue(buildReleaseListResponse({ releases: [] }));
    renderPage();

    // Labor's own state is already resolved, but Inflation is still
    // pending -- no sentence naming Labor's state may appear yet.
    expect(screen.queryByText(/Strengthening/)).not.toBeInTheDocument();
  });

  it("composed sentence renders once both resources resolve successfully", async () => {
    resolveAll();
    renderPage();

    const section = await findSection("Inflation and Jobs, side by side");
    expect(await within(section).findByText(/^As of/)).toBeInTheDocument();
  });

  it("links to /inflation and /jobs via 'View Inflation →'/'View Jobs →'", async () => {
    resolveAll();
    renderPage();

    const section = await findSection("Inflation and Jobs, side by side");
    expect(within(section).getByRole("link", { name: "View Inflation →" })).toHaveAttribute("href", "/inflation");
    expect(within(section).getByRole("link", { name: "View Jobs →" })).toHaveAttribute("href", "/jobs");
  });

  it("contains no cross-domain agreement/divergence or regime vocabulary, all canonical Inflation/Labor state pairs", async () => {
    const inflationStates = ["COOLING", "HEATING", "STABLE", "MIXED"] as const;
    const laborStates = ["STRENGTHENING", "COOLING", "STABLE", "MIXED"] as const;
    for (const inflationState of inflationStates) {
      for (const laborState of laborStates) {
        resolveAll({
          monitor: buildMonitor({ underlying_momentum: buildMomentum({ state: inflationState }) }),
          laborMonitor: buildLaborMonitor({ state: laborState }),
        });
        const { unmount } = renderPage();
        const section = await findSection("Inflation and Jobs, side by side");
        const text = section.textContent ?? "";
        for (const forbidden of [/agrees?\b/i, /confirms?\b/i, /diverges?\b/i, /contradicts?\b/i, /goldilocks/i, /bullish/i, /bearish/i]) {
          expect(text).not.toMatch(forbidden);
        }
        unmount();
      }
    }
  });
});

describe("State Duration V1 exclusion (Increment #24D, frozen contract §41)", () => {
  it("never imports the state-duration API clients or presentation modules at the source level", async () => {
    const { readFileSync } = await import("node:fs");
    const { dirname, join } = await import("node:path");
    const { fileURLToPath } = await import("node:url");
    const overviewPath = join(dirname(fileURLToPath(import.meta.url)), "Home.tsx");
    const overviewSource = readFileSync(overviewPath, "utf-8");
    for (const forbidden of ["getInflationStateDuration", "getLaborStateDuration", "StateDurationLine", "stateDurationCopy"]) {
      expect(overviewSource).not.toContain(forbidden);
    }
  });

  it("renders with the two state-duration API clients never invoked", async () => {
    resolveAll();
    renderPage();
    await screen.findByRole("heading", { name: "Inflation and Jobs, side by side" });

    // These are the same api/inflation.ts and api/labor.ts modules
    // Overview already mocks above -- if Overview ever came to import
    // getInflationStateDuration/getLaborStateDuration, the mock
    // factories for those modules (which do not define those exports)
    // would make them `undefined`, and importing them here would throw
    // immediately, failing this test loudly rather than silently.
    const inflationModule = await import("../api/inflation");
    const laborModule = await import("../api/labor");
    expect("getInflationStateDuration" in inflationModule).toBe(false);
    expect("getLaborStateDuration" in laborModule).toBe(false);
  });

  it("never renders any State Duration copy string anywhere on the page", async () => {
    resolveAll();
    renderPage();
    await screen.findByRole("heading", { name: "Inflation and Jobs, side by side" });

    const pageText = document.body.textContent ?? "";
    for (const forbidden of [
      /latest-revised reconstruction/i,
      /consecutive months?/i,
      /historical state duration is unavailable/i,
      /earliest confirmed/i,
    ]) {
      expect(pageText).not.toMatch(forbidden);
    }
  });

  it("the Inflation/Jobs juxtaposition remains exactly as #23C established, unaffected by State Duration's own existence", async () => {
    resolveAll({
      monitor: buildMonitor({ underlying_momentum: buildMomentum({ state: "COOLING", calculation_period: "2026-07-01" }) }),
      laborMonitor: buildLaborMonitor({ state: "STRENGTHENING", evaluation_period: "2026-07-01" }),
    });
    renderPage();

    const section = await findSection("Inflation and Jobs, side by side");
    expect(section.textContent).toMatch(/As of July 2026, Inflation is Cooling while Jobs is Strengthening\./);
  });
});

/*
 * REMOVED IN #42A: the "What Changed" and "Recent Data Updates"
 * integration blocks.
 *
 * Both sections were removed from the HOMEPAGE COMPOSITION because
 * they render coverage/bootstrap events as consumer changes -- see
 * `pages/Home.tsx`'s own header for the full reasoning. Their tests
 * asserted behaviour of a page region that no longer exists, so they
 * were removed with the region rather than rewritten to assert
 * something they no longer describe.
 *
 * The COMPONENTS survive and are untouched. `SinceLastVisit` and the
 * overview `LatestDataDetected` keep their own component tests
 * (components/overview/*.test.tsx). `WhatChangedPreview` and
 * `LaborWhatChangedPreview` are now rendered by no route and have no
 * test of their own -- recorded as a #43 obligation rather than left
 * to be discovered.
 */

describe("Releases", () => {
  it("THE RELEASE-ORDERING TEST: shows the first 3 upcoming occurrences in backend response order, never reordered", async () => {
    const releases = [
      buildReleaseOccurrenceItem({ release_id: 1, name: "Advance Retail Sales", provider_release_id: "9", scheduled_date: "2026-09-16" }),
      buildReleaseOccurrenceItem({ release_id: 2, name: "Job Openings and Labor Turnover Survey", provider_release_id: "192", scheduled_date: "2026-09-29" }),
      buildReleaseOccurrenceItem({ release_id: 3, name: "Gross Domestic Product", provider_release_id: "53", scheduled_date: "2026-09-30" }),
      buildReleaseOccurrenceItem({ release_id: 4, name: "Consumer Price Index", provider_release_id: "10", scheduled_date: "2026-10-14" }),
    ];
    resolveAll({ upcoming: buildReleaseListResponse({ releases }) });
    renderPage();

    const section = await findSection("Releases");
    expect(within(section).getByText("Advance Retail Sales")).toBeInTheDocument();
    expect(within(section).getByText("JOLTS")).toBeInTheDocument();
    expect(within(section).getByText("Gross Domestic Product (GDP)")).toBeInTheDocument();
    // The 4th (CPI) never appears in the upcoming preview.
    expect(within(section).queryByText("Consumer Price Index")).not.toBeInTheDocument();
  });

  it("THE RELEASE-ROW CTA TEST (§17/§21): each row's next action is keyed by canonical monitor relation, never releaseCategory()", async () => {
    const releases = [
      buildReleaseOccurrenceItem({ release_id: 1, name: "Consumer Price Index", provider_release_id: "10", scheduled_date: "2026-09-16" }),
      buildReleaseOccurrenceItem({ release_id: 2, name: "Employment Situation", provider_release_id: "50", scheduled_date: "2026-09-17" }),
      buildReleaseOccurrenceItem({ release_id: 3, name: "Job Openings and Labor Turnover Survey", provider_release_id: "192", scheduled_date: "2026-09-18" }),
    ];
    resolveAll({ upcoming: buildReleaseListResponse({ releases }) });
    renderPage();

    const section = await findSection("Releases");
    const cpiRow = within(section).getByText("Consumer Price Index").closest("li") as HTMLElement;
    expect(within(cpiRow).getByRole("link", { name: "View Inflation →" })).toHaveAttribute("href", "/inflation");

    // "Employment Situation" also appears inside its own collapsed
    // ExplanationTrigger popup content -- [0] is the row's own visible
    // name span, always first in DOM order (same established fix
    // pattern as pages/Labor.test.tsx's identical ambiguity).
    const employmentRow = within(section).getAllByText("Employment Situation")[0]!.closest("li") as HTMLElement;
    expect(within(employmentRow).getByRole("link", { name: "View Jobs →" })).toHaveAttribute("href", "/jobs");

    // JOLTS -- category tag reads "Labor" on this same row, but it has
    // no canonical monitor relation. §3A's correction is unchanged and
    // is if anything asserted more strongly since #45B: it gets NO
    // Jobs link, and no generic link either. It states that MacroChipz
    // does not track it, which is the true thing -- see §17's #45B
    // addendum for why "View Calendar →" was replaced rather than kept.
    const joltsRow = within(section).getByText("JOLTS").closest("li") as HTMLElement;
    expect(within(joltsRow).queryByRole("link", { name: "View Jobs →" })).not.toBeInTheDocument();
    expect(within(joltsRow).queryByRole("link", { name: "View Calendar →" })).not.toBeInTheDocument();
    expect(within(joltsRow).getByText(/Not tracked by MacroChipz yet/)).toBeInTheDocument();
  });

  it("shows at most one recent occurrence as compact context", async () => {
    resolveAll({
      recent: buildReleaseListResponse({
        releases: [
          buildReleaseOccurrenceItem({ release_id: 1, name: "Consumer Price Index", scheduled_date: "2026-09-11", schedule_status: "PAST_DUE" }),
          buildReleaseOccurrenceItem({ release_id: 2, name: "Employment Situation", scheduled_date: "2026-09-04", schedule_status: "PAST_DUE" }),
        ],
      }),
    });
    renderPage();

    const section = await findSection("Releases");
    expect(within(section).getByText("Consumer Price Index")).toBeInTheDocument();
    expect(within(section).queryByText("Employment Situation")).not.toBeInTheDocument();
  });

  it("Employment Situation naturally appears among Releases -- no special-case Labor logic", async () => {
    resolveAll({
      upcoming: buildReleaseListResponse({
        releases: [buildReleaseOccurrenceItem({ release_id: 5, name: "Employment Situation", provider_release_id: "50", scheduled_date: "2026-10-02" })],
      }),
    });
    renderPage();

    const section = await findSection("Releases");
    expect(within(section).getAllByText("Employment Situation").length).toBeGreaterThanOrEqual(1);
  });

  it("THE SCHEDULE-DOES-NOT-MEAN-PUBLICATION TEST: a PAST_DUE release never implies publication/availability", async () => {
    resolveAll({
      recent: buildReleaseListResponse({
        releases: [buildReleaseOccurrenceItem({ schedule_status: "PAST_DUE" })],
      }),
    });
    renderPage();

    await findSection("Releases");
    const forbidden = /\bpublished\b|\breleased\b|data available|data is now available/i;
    // The one sanctioned disclosure sentence itself legitimately negates
    // "published" -- excluded before checking, the same discipline
    // pages/Releases.test.tsx already establishes.
    const disclosure = screen.getByText(/Release dates indicate scheduled publication dates/);
    // #48: the hero's supporting line and the image notice both use
    // "published" about PROVENANCE -- which agency published a figure,
    // and the archive a photograph came from. Neither is about a
    // release occurrence, neither fetches anything, and both are the
    // same two static sentences on every render. Excluded here for the
    // same reason the disclosure sentence already is: the guard exists
    // to stop a SCHEDULED release being described as a published one.
    const exempt = [
      disclosure.textContent ?? "",
      screen.getByText(/Four parts of the U.S. economy/).textContent ?? "",
      screen.getByText(/Carol M. Highsmith Archive, Library of Congress, Prints/).textContent ?? "",
    ];
    let bodyText = document.body.textContent ?? "";
    for (const sentence of exempt) bodyText = bodyText.replace(sentence, "");
    expect(bodyText).not.toMatch(forbidden);
  });

  it("the release schedule disclosure is visible on Overview", async () => {
    resolveAll();
    renderPage();

    expect(
      await screen.findByText(
        "Release dates indicate scheduled publication dates. They do not confirm that new data has been published, ingested, or reflected in Economic Intelligence analysis.",
      ),
    ).toBeInTheDocument();
  });

  it("shows a truthful empty message when there are no upcoming releases", async () => {
    resolveAll({ upcoming: buildReleaseListResponse({ releases: [] }) });
    renderPage();

    const section = await findSection("Releases");
    expect(within(section).getByText("No scheduled releases in this window.")).toBeInTheDocument();
  });

  it("renders nothing extra (no fabricated message) when there is no recent release", async () => {
    resolveAll({ recent: buildReleaseListResponse({ releases: [] }) });
    renderPage();

    const section = await findSection("Releases");
    expect(within(section).queryByText(/^Recently/)).not.toBeInTheDocument();
  });

  it("links to /calendar via 'View release calendar'", async () => {
    resolveAll();
    renderPage();

    const section = await findSection("Releases");
    const link = within(section).getByRole("link", { name: "View release calendar →" });
    expect(link).toHaveAttribute("href", "/calendar");
  });
});

describe("partial failure isolation", () => {
  // Each resource still fails alone. #42A removed the What Changed and
  // Recent Data Updates sections from `/`, so the cases that asserted
  // THEIR isolation went with them; the principle is unchanged and is
  // still proved by the sections that remain.
  it("Inflation monitor fails; everything else still renders", async () => {
    resolveAll();
    mockedGetMonitor.mockRejectedValue(new Error("network down"));
    renderPage();

    // Appears in Current State's own card AND in How They Relate --
    // two independent sections, each reporting its own failure.
    expect((await screen.findAllByText("Inflation data could not be loaded.")).length).toBeGreaterThanOrEqual(1);
    expect(await findSection("Current State")).toBeInTheDocument();
    expect(await findSection("Releases")).toBeInTheDocument();
  });

  it("Upcoming releases fail; Current State and Recent still render", async () => {
    resolveAll();
    mockedFetchUpcoming.mockRejectedValue(new Error("network down"));
    renderPage();

    expect(await screen.findByText("Upcoming releases could not be loaded.")).toBeInTheDocument();
    expect(await findSection("Current State")).toBeInTheDocument();
  });

  it("never renders a single Promise.all-style page-level failure -- each error is local to its own section", async () => {
    resolveAll();
    mockedGetMonitor.mockRejectedValue(new Error("down"));
    mockedGetLaborMonitor.mockRejectedValue(new Error("down"));
    mockedFetchUpcoming.mockRejectedValue(new Error("down"));
    mockedFetchRecent.mockRejectedValue(new Error("down"));
    renderPage();

    expect((await screen.findAllByText("Inflation data could not be loaded.")).length).toBeGreaterThanOrEqual(1);
    expect((await screen.findAllByText("Jobs data could not be loaded.")).length).toBeGreaterThanOrEqual(1);
    expect(await screen.findByText("Upcoming releases could not be loaded.")).toBeInTheDocument();
    expect(await screen.findByText("Recent releases could not be loaded.")).toBeInTheDocument();
  });
});


describe("navigation", () => {
  it("exposes exactly the real CTAs, no dead links", async () => {
    resolveAll();
    renderPage();

    await screen.findByRole("heading", { name: "Current State" });
    expect(screen.getByRole("link", { name: "Open Inflation →" })).toHaveAttribute("href", "/inflation");
    expect(screen.getByRole("link", { name: "Open Jobs →" })).toHaveAttribute("href", "/jobs");
    // #42A: only How They Relate (Increment #23C) still offers these
    // -- Since Your Last Check, What Changed and Recent Data Updates
    // all left `/`.
    const inflationLinks = screen.getAllByRole("link", { name: "View Inflation →" });
    const laborLinks = screen.getAllByRole("link", { name: "View Jobs →" });
    expect(inflationLinks).toHaveLength(1);
    expect(laborLinks).toHaveLength(1);
    for (const link of inflationLinks) expect(link).toHaveAttribute("href", "/inflation");
    for (const link of laborLinks) expect(link).toHaveAttribute("href", "/jobs");
    expect(screen.queryByRole("link", { name: "See full comparison →" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View release calendar →" })).toHaveAttribute("href", "/calendar");
    // No dead/aspirational product surfaces.
    for (const name of ["Explore", "Compare", "Research", "Ask EI", "News", "Watchlist"]) {
      expect(screen.queryByRole("link", { name: new RegExp(name, "i") })).not.toBeInTheDocument();
    }
  });
});

describe("the homepage survives an outage (#48)", () => {
  it("every request fails and the orientation layer is still complete", async () => {
    // The hero fetches nothing, which is the whole reason it is first.
    // An outage is exactly when a reader is most likely to be confused
    // about what this site is.
    mockedGetMonitor.mockRejectedValue(new Error("down"));
    mockedGetWhatChanged.mockRejectedValue(new Error("down"));
    mockedGetLaborMonitor.mockRejectedValue(new Error("down"));
    mockedGetLaborWhatChanged.mockRejectedValue(new Error("down"));
    mockedFetchUpcoming.mockRejectedValue(new Error("down"));
    mockedFetchRecent.mockRejectedValue(new Error("down"));
    renderPage();

    expect(screen.getByRole("heading", { level: 1, name: "Explore the living economy." })).toBeInTheDocument();
    for (const [label, route] of [
      ["Inflation", "/inflation"],
      ["Jobs", "/jobs"],
      ["Rates", "/rates"],
      ["Housing", "/housing"],
    ] as const) {
      expect(screen.getByRole("button", { name: new RegExp(label) })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Open the story" })).toHaveAttribute(
        "href",
        "/story/fed-and-mortgage-rates",
      );
      void route;
    }

    // And the lede says it does not know, rather than saying nothing
    // happened.
    expect(await screen.findByRole("heading", { name: "Not yet known" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "No new tracked change" })).not.toBeInTheDocument();
  });

  it("renders the required image notice verbatim", async () => {
    resolveAll();
    renderPage();
    expect(
      await screen.findByText(/Photographs in the Carol M. Highsmith Archive, Library of Congress/),
    ).toBeInTheDocument();
  });

  it("lists each of the four worlds exactly once", async () => {
    // #48 removed two duplicate world grids. A reader should meet
    // Housing once, not three times in one screen.
    resolveAll();
    renderPage();
    await findSection("Releases");
    for (const label of ["Inflation", "Jobs", "Rates", "Housing"]) {
      // Exactly one control per world. Before #48 there were two world
      // grids below the hero's job -- WorldOrientation's and the quiet
      // lede's -- so Housing could appear three times in one screen.
      expect(screen.getAllByRole("button", { name: new RegExp(label) }), label).toHaveLength(1);
      // At most one link: the selected world's "Open ..." action. The
      // other three offer no link at all until they are selected.
      expect(screen.queryAllByRole("link", { name: new RegExp(`^Open ${label}$`) }).length, label).toBeLessThanOrEqual(
        1,
      );
    }
  });
});

describe("the story is offered exactly once (#48B)", () => {
  it("renders the mobile teaser and the desktop section, each gated to its own width", async () => {
    // jsdom has no viewport, so BOTH are in the tree. What is asserted
    // is that each is gated -- a reader never meets the story twice on
    // one screen, and never fails to meet it at all.
    resolveAll();
    renderPage();
    await findSection("Releases");

    const storyLinks = screen.getAllByRole("link", { name: /the story|Interactive story/ });
    expect(storyLinks.length).toBeGreaterThanOrEqual(1);
    for (const link of storyLinks) expect(link).toHaveAttribute("href", "/story/fed-and-mortgage-rates");

    const teaser = document.querySelector(".lx-teaser");
    expect(teaser?.className).toContain("lg:hidden");
    const featured = screen.getByRole("heading", { name: "Featured discovery" }).closest("div.hidden");
    expect(featured?.className).toContain("lg:block");
  });

  it("puts the teaser before the chart, and the chart is still there", async () => {
    // The measured problem: the story began 1,637px down a 390px
    // page, behind a full screen of chart. Order is the fix; nothing
    // was removed.
    resolveAll();
    renderPage();
    await findSection("Releases");

    const teaser = document.querySelector(".lx-teaser") as HTMLElement;
    const lede = document.getElementById("lede-heading") as HTMLElement;
    expect(teaser).not.toBeNull();
    expect(lede).not.toBeNull();
    expect(teaser.compareDocumentPosition(lede) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // The readings slot is still there and still ahead of everything
    // else on the page. This file does not mock the intelligence
    // endpoint, so the lede renders its unknown state -- which is the
    // point: the teaser does not depend on data arriving.
    expect(lede.textContent).not.toBe("");
  });
});

describe("page structure", () => {
  it("uses one h1 and the exact section heading hierarchy", async () => {
    resolveAll();
    renderPage();

    await screen.findByRole("heading", { name: "Current State" });
    // #48: the hero is the header, and its headline is the h1.
    expect(screen.getByRole("heading", { level: 1, name: "Explore the living economy." })).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    // #42A: "What Changed" and "Recent Data Updates" left `/`.
    // #45B added three: world orientation, curated questions, and the
    // path into Revision Intelligence -- the three #45A findings about
    // what the homepage could not reach. "Inflation and Jobs, side by side" became
    // "Inflation and Jobs, side by side" (heading only; the frozen
    // #23C composition is unchanged).
    for (const name of [
      // #48: "Explore the economy" (WorldOrientation) was retired --
      // the hero does that job -- and "Featured discovery" promotes the
      // mortgage-rate story out of the questions list.
      "Featured discovery",
      "Questions people ask",
      "Current State",
      "Inflation and Jobs, side by side",
      "Releases",
      "When a number changes",
    ]) {
      expect(screen.getByRole("heading", { level: 2, name })).toBeInTheDocument();
    }
  });

  it("shows the supporting line, which states provenance and promises nothing else", async () => {
    // #48 replaced "Know what changed in the economy — and prove why."
    // The new line is narrower on purpose: it describes what the page
    // can show about every figure, rather than what the reader will
    // feel about it.
    resolveAll();
    renderPage();
    expect(
      await screen.findByText(
        "Four parts of the U.S. economy. Every figure traces back to the agency that published it, with the date it was published.",
      ),
    ).toBeInTheDocument();
  });
});
