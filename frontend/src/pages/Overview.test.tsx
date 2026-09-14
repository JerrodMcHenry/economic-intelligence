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
import {
  buildChangeEvent,
  buildMomentum,
  buildMonitor,
  buildWhatChanged,
} from "../test/fixtures/inflation";
import { buildLaborChangeEvent, buildLaborMonitor, buildLaborWhatChanged } from "../test/fixtures/labor";
import { buildLatestCheck, buildReleaseProcessingStatusItem, buildReleaseProcessingStatusResponse } from "../test/fixtures/processingStatus";
import { buildReleaseListResponse, buildReleaseOccurrenceItem } from "../test/fixtures/releases";
import { OverviewPage } from "./Overview";

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

const mockedGetMonitor = vi.mocked(getInflationMonitor);
const mockedGetWhatChanged = vi.mocked(getInflationWhatChanged);
const mockedGetLaborMonitor = vi.mocked(getLaborMonitor);
const mockedGetLaborWhatChanged = vi.mocked(getLaborWhatChanged);
const mockedFetchProcessingStatus = vi.mocked(fetchReleaseProcessingStatus);
const mockedFetchUpcoming = vi.mocked(fetchUpcomingReleases);
const mockedFetchRecent = vi.mocked(fetchRecentReleases);

beforeEach(() => {
  mockedGetMonitor.mockReset();
  mockedGetWhatChanged.mockReset();
  mockedGetLaborMonitor.mockReset();
  mockedGetLaborWhatChanged.mockReset();
  mockedFetchProcessingStatus.mockReset();
  mockedFetchUpcoming.mockReset();
  mockedFetchRecent.mockReset();
});

function resolveAll(overrides: {
  monitor?: ReturnType<typeof buildMonitor>;
  whatChanged?: ReturnType<typeof buildWhatChanged>;
  laborMonitor?: ReturnType<typeof buildLaborMonitor>;
  laborWhatChanged?: ReturnType<typeof buildLaborWhatChanged>;
  processingStatus?: ReturnType<typeof buildReleaseProcessingStatusResponse>;
  upcoming?: ReturnType<typeof buildReleaseListResponse>;
  recent?: ReturnType<typeof buildReleaseListResponse>;
} = {}) {
  mockedGetMonitor.mockResolvedValue(overrides.monitor ?? buildMonitor());
  mockedGetWhatChanged.mockResolvedValue(overrides.whatChanged ?? buildWhatChanged());
  mockedGetLaborMonitor.mockResolvedValue(overrides.laborMonitor ?? buildLaborMonitor());
  mockedGetLaborWhatChanged.mockResolvedValue(overrides.laborWhatChanged ?? buildLaborWhatChanged());
  mockedFetchProcessingStatus.mockResolvedValue(overrides.processingStatus ?? buildReleaseProcessingStatusResponse({ occurrences: [] }));
  mockedFetchUpcoming.mockResolvedValue(overrides.upcoming ?? buildReleaseListResponse({ releases: [] }));
  mockedFetchRecent.mockResolvedValue(overrides.recent ?? buildReleaseListResponse({ releases: [] }));
}

function renderPage() {
  return render(
    <MemoryRouter>
      <OverviewPage />
    </MemoryRouter>,
  );
}

async function findSection(name: string) {
  const heading = await screen.findByRole("heading", { name });
  return heading.closest("section") as HTMLElement;
}

describe("loading", () => {
  it("shows a stable loading state for all seven resources with no fabricated data", () => {
    mockedGetMonitor.mockReturnValue(new Promise(() => {}));
    mockedGetWhatChanged.mockReturnValue(new Promise(() => {}));
    mockedGetLaborMonitor.mockReturnValue(new Promise(() => {}));
    mockedGetLaborWhatChanged.mockReturnValue(new Promise(() => {}));
    mockedFetchProcessingStatus.mockReturnValue(new Promise(() => {}));
    mockedFetchUpcoming.mockReturnValue(new Promise(() => {}));
    mockedFetchRecent.mockReturnValue(new Promise(() => {}));

    renderPage();

    expect(screen.getAllByRole("status").length).toBeGreaterThanOrEqual(7);
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
    expect(within(section).getByText("Labor")).toBeInTheDocument();
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

  it("links to /inflation via 'Open Inflation' and /labor via 'Open Labor'", async () => {
    resolveAll();
    renderPage();

    const section = await findSection("Current State");
    expect(within(section).getByRole("link", { name: "Open Inflation →" })).toHaveAttribute("href", "/inflation");
    expect(within(section).getByRole("link", { name: "Open Labor →" })).toHaveAttribute("href", "/labor");
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
    expect(within(section).getByText("Labor")).toBeInTheDocument();
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
    expect(within(section).getByText("Labor data could not be loaded.")).toBeInTheDocument();
    expect(within(section).getByText("Inflation")).toBeInTheDocument();
    expect(within(section).getByText("Stable", { selector: "span" })).toBeInTheDocument();
  });
});

describe("What Changed", () => {
  it("renders only actual backend ChangeEvents, never an invented 'State remains X' narrative", async () => {
    // State is MIXED, but the flat `changes` list contains ONLY metric
    // events -- no STATE_CHANGED event at all. Overview must not
    // synthesize a "remained"/"stayed" sentence from that absence.
    resolveAll({
      monitor: buildMonitor({ underlying_momentum: buildMomentum({ state: "MIXED" }) }),
      whatChanged: buildWhatChanged({
        changes: [buildChangeEvent({ component: "PRIMARY_MOMENTUM", event_type: "METRIC_CHANGED", field: "r_3m_annualized" })],
      }),
    });
    renderPage();

    const section = await findSection("What Changed");
    expect(within(section).getByText(/3M annualized/)).toBeInTheDocument();
    expect(screen.queryByText(/remains mixed/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/state remains/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/unchanged/i)).not.toBeInTheDocument();
  });

  it("THE EVENT-ORDERING TEST: takes the first 3 canonical events, in the exact returned order, never reordered", async () => {
    const events = [
      buildChangeEvent({ component: "HEADLINE_CPI", event_type: "METRIC_CHANGED", field: "r_6m_annualized" }),
      buildChangeEvent({ component: "PRIMARY_MOMENTUM", event_type: "STATE_CHANGED", field: "state", previous_value: "COOLING", current_value: "MIXED" }),
      buildChangeEvent({ component: "TARGET", event_type: "METRIC_CHANGED", field: "target_gap_pp" }),
      buildChangeEvent({ component: "CONFIRMATION", event_type: "CONFIRMATION_CHANGED", field: "relationship", previous_value: "CONFIRMS", current_value: "DIVERGES" }),
    ];
    resolveAll({ whatChanged: buildWhatChanged({ changes: events }) });
    renderPage();

    const section = await findSection("What Changed");
    // Scope to the Inflation card specifically -- the shared section
    // also contains Labor's own (empty, by default) list.
    const inflationCard = within(section).getByText("Inflation").closest("div") as HTMLElement;
    const items = within(inflationCard).getAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(items[0]!.textContent).toMatch(/Headline CPI/);
    expect(items[1]!.textContent).toMatch(/Core PCE/);
    expect(items[2]!.textContent).toMatch(/Target/);
    // The 4th event (Confirmation) never appears.
    expect(within(inflationCard).queryByText(/Confirmation/)).not.toBeInTheDocument();
  });

  it("THE LABOR EVENT-ORDERING TEST: takes the first 3 canonical Labor events, in the exact returned order", async () => {
    const events = [
      buildLaborChangeEvent({ component: "LABOR", event_type: "STATE_CHANGED", field: "state", previous_value: "COOLING", current_value: "MIXED" }),
      buildLaborChangeEvent({ component: "EMPLOYMENT", event_type: "STATE_CHANGED", field: "condition", previous_value: "FLAT", current_value: "EXPANDING" }),
      buildLaborChangeEvent({ component: "UNEMPLOYMENT", event_type: "METRIC_CHANGED", field: "delta_pp" }),
      buildLaborChangeEvent({ component: "EMPLOYMENT", event_type: "METRIC_CHANGED", field: "momentum_delta_jobs" }),
    ];
    resolveAll({ laborWhatChanged: buildLaborWhatChanged({ changes: events }) });
    renderPage();

    const section = await findSection("What Changed");
    const laborCard = within(section).getByText("Labor").closest("div") as HTMLElement;
    const items = within(laborCard).getAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(items[0]!.textContent).toMatch(/Labor/);
    expect(items[1]!.textContent).toMatch(/Employment/);
    expect(items[2]!.textContent).toMatch(/Unemployment/);
  });

  it("renders a state-field event using the existing state label, never the raw backend enum string alone", async () => {
    resolveAll({
      whatChanged: buildWhatChanged({
        changes: [
          buildChangeEvent({ component: "PRIMARY_MOMENTUM", event_type: "STATE_CHANGED", field: "state", previous_value: "COOLING", current_value: "MIXED" }),
        ],
      }),
    });
    renderPage();

    const section = await findSection("What Changed");
    expect(within(section).getByText(/Cooling/)).toBeInTheDocument();
    expect(within(section).getByText(/Mixed/)).toBeInTheDocument();
  });

  it("shows a precise, non-inventive empty-state message when zero Inflation events are reported", async () => {
    resolveAll({ whatChanged: buildWhatChanged({ changes: [] }) });
    renderPage();

    const section = await findSection("What Changed");
    expect(within(section).getByText("No canonical Inflation changes were reported for this comparison.")).toBeInTheDocument();
    expect(within(section).queryByText(/Inflation was unchanged/i)).not.toBeInTheDocument();
  });

  it("shows a precise, non-inventive empty-state message when zero Labor events are reported", async () => {
    resolveAll({ laborWhatChanged: buildLaborWhatChanged({ changes: [] }) });
    renderPage();

    const section = await findSection("What Changed");
    expect(within(section).getByText("No canonical Labor changes were reported for this comparison.")).toBeInTheDocument();
    expect(within(section).queryByText(/Labor was unchanged/i)).not.toBeInTheDocument();
  });

  it("links to /inflation and /labor via their own 'See full comparison'", async () => {
    resolveAll();
    renderPage();

    const section = await findSection("What Changed");
    const links = within(section).getAllByRole("link", { name: "See full comparison →" });
    expect(links).toHaveLength(2);
    const hrefs = links.map((link) => link.getAttribute("href"));
    expect(hrefs).toContain("/inflation");
    expect(hrefs).toContain("/labor");
  });

  it("Inflation changes fails; Labor's own What Changed card still renders", async () => {
    mockedGetMonitor.mockResolvedValue(buildMonitor());
    mockedGetWhatChanged.mockRejectedValue(new Error("down"));
    mockedGetLaborMonitor.mockResolvedValue(buildLaborMonitor());
    mockedGetLaborWhatChanged.mockResolvedValue(
      buildLaborWhatChanged({ changes: [buildLaborChangeEvent({ component: "EMPLOYMENT", field: "condition" })] }),
    );
    mockedFetchProcessingStatus.mockResolvedValue(buildReleaseProcessingStatusResponse({ occurrences: [] }));
    mockedFetchUpcoming.mockResolvedValue(buildReleaseListResponse({ releases: [] }));
    mockedFetchRecent.mockResolvedValue(buildReleaseListResponse({ releases: [] }));
    renderPage();

    const section = await findSection("What Changed");
    expect(within(section).getByText("What changed could not be loaded.")).toBeInTheDocument();
    expect(within(section).getByText(/Condition/)).toBeInTheDocument();
  });

  it("Labor changes fails; Inflation's own What Changed card still renders", async () => {
    mockedGetMonitor.mockResolvedValue(buildMonitor());
    mockedGetWhatChanged.mockResolvedValue(
      buildWhatChanged({ changes: [buildChangeEvent({ component: "TARGET", field: "target_gap_pp" })] }),
    );
    mockedGetLaborMonitor.mockResolvedValue(buildLaborMonitor());
    mockedGetLaborWhatChanged.mockRejectedValue(new Error("down"));
    mockedFetchProcessingStatus.mockResolvedValue(buildReleaseProcessingStatusResponse({ occurrences: [] }));
    mockedFetchUpcoming.mockResolvedValue(buildReleaseListResponse({ releases: [] }));
    mockedFetchRecent.mockResolvedValue(buildReleaseListResponse({ releases: [] }));
    renderPage();

    const section = await findSection("What Changed");
    expect(within(section).getByText("Labor what changed could not be loaded.")).toBeInTheDocument();
    expect(within(section).getByText(/Target/)).toBeInTheDocument();
  });
});

describe("Latest Data Detected", () => {
  it("is its own independent resource: renders real backend evidence between What Changed and Releases", async () => {
    resolveAll({
      processingStatus: buildReleaseProcessingStatusResponse({
        occurrences: [buildReleaseProcessingStatusItem({ latest_check: buildLatestCheck({ status: "CHANGES_DETECTED" }) })],
      }),
    });
    renderPage();

    const section = await findSection("Latest Data Detected");
    expect(within(section).getByText("Data changes detected.")).toBeInTheDocument();

    const headings = screen.getAllByRole("heading", { level: 2 }).map((heading) => heading.textContent);
    expect(headings).toEqual(["Current State", "What Changed", "Latest Data Detected", "Releases"]);
  });

  it("shows the empty-state message when the backend returns zero mapped occurrences", async () => {
    resolveAll({ processingStatus: buildReleaseProcessingStatusResponse({ occurrences: [] }) });
    renderPage();

    const section = await findSection("Latest Data Detected");
    expect(within(section).getByText("No tracked release processing records are available yet.")).toBeInTheDocument();
  });

  it("renders a Labor component value (EMPLOYMENT/UNEMPLOYMENT/LABOR) naturally, no special-case code needed", async () => {
    resolveAll({
      processingStatus: buildReleaseProcessingStatusResponse({
        occurrences: [
          buildReleaseProcessingStatusItem({
            latest_check: buildLatestCheck({ status: "CHANGES_DETECTED" }),
            detected_analysis_changes: [
              {
                component: "EMPLOYMENT",
                event_type: "STATE_CHANGED",
                field: "state",
                previous_value: "CONTRACTING",
                current_value: "RECOVERING",
                delta: null,
                evaluation_period: "2026-07-01",
                methodology_id: "labor_v1.0",
                data_basis: "latest_revised_data",
                recorded_at: "2026-07-05T12:00:00+00:00",
              },
            ],
          }),
        ],
      }),
    });
    renderPage();

    const section = await findSection("Latest Data Detected");
    expect(within(section).getByText(/Employment/)).toBeInTheDocument();
    expect(within(section).getByText(/Recovering/)).toBeInTheDocument();
    expect(within(section).getByText(/Contracting/)).toBeInTheDocument();
  });
});

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
    const bodyText = (document.body.textContent ?? "").replace(disclosure.textContent ?? "", "");
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

  it("links to /releases via 'View release calendar'", async () => {
    resolveAll();
    renderPage();

    const section = await findSection("Releases");
    const link = within(section).getByRole("link", { name: "View release calendar →" });
    expect(link).toHaveAttribute("href", "/releases");
  });
});

describe("partial failure isolation", () => {
  it("Inflation monitor fails; everything else still renders", async () => {
    mockedGetMonitor.mockRejectedValue(new Error("network down"));
    mockedGetWhatChanged.mockResolvedValue(buildWhatChanged());
    mockedGetLaborMonitor.mockResolvedValue(buildLaborMonitor());
    mockedGetLaborWhatChanged.mockResolvedValue(buildLaborWhatChanged());
    mockedFetchProcessingStatus.mockResolvedValue(buildReleaseProcessingStatusResponse({ occurrences: [] }));
    mockedFetchUpcoming.mockResolvedValue(buildReleaseListResponse({ releases: [] }));
    mockedFetchRecent.mockResolvedValue(buildReleaseListResponse({ releases: [] }));
    renderPage();

    expect(await screen.findByText("Inflation data could not be loaded.")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "What Changed" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Latest Data Detected" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Releases" })).toBeInTheDocument();
  });

  it("What Changed fails; Current State, Latest Data Detected, and Releases still render", async () => {
    mockedGetMonitor.mockResolvedValue(buildMonitor());
    mockedGetWhatChanged.mockRejectedValue(new Error("network down"));
    mockedGetLaborMonitor.mockResolvedValue(buildLaborMonitor());
    mockedGetLaborWhatChanged.mockResolvedValue(buildLaborWhatChanged());
    mockedFetchProcessingStatus.mockResolvedValue(buildReleaseProcessingStatusResponse({ occurrences: [] }));
    mockedFetchUpcoming.mockResolvedValue(buildReleaseListResponse({ releases: [] }));
    mockedFetchRecent.mockResolvedValue(buildReleaseListResponse({ releases: [] }));
    renderPage();

    expect(await screen.findByText("What changed could not be loaded.")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Current State" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Latest Data Detected" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Releases" })).toBeInTheDocument();
  });

  it("Release-processing status fails; Current State, What Changed, and Releases still render normally", async () => {
    mockedGetMonitor.mockResolvedValue(buildMonitor());
    mockedGetWhatChanged.mockResolvedValue(buildWhatChanged());
    mockedGetLaborMonitor.mockResolvedValue(buildLaborMonitor());
    mockedGetLaborWhatChanged.mockResolvedValue(buildLaborWhatChanged());
    mockedFetchProcessingStatus.mockRejectedValue(new Error("network down"));
    mockedFetchUpcoming.mockResolvedValue(buildReleaseListResponse({ releases: [buildReleaseOccurrenceItem()] }));
    mockedFetchRecent.mockResolvedValue(buildReleaseListResponse({ releases: [] }));
    renderPage();

    expect(await screen.findByText("Release-processing status is temporarily unavailable.")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Current State" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "What Changed" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Releases" })).toBeInTheDocument();
    expect(await screen.findByText("Consumer Price Index")).toBeInTheDocument();
  });

  it("Latest Data Detected still renders when every OTHER resource fails", async () => {
    mockedGetMonitor.mockRejectedValue(new Error("down"));
    mockedGetWhatChanged.mockRejectedValue(new Error("down"));
    mockedGetLaborMonitor.mockRejectedValue(new Error("down"));
    mockedGetLaborWhatChanged.mockRejectedValue(new Error("down"));
    mockedFetchProcessingStatus.mockResolvedValue(
      buildReleaseProcessingStatusResponse({ occurrences: [buildReleaseProcessingStatusItem({ latest_check: buildLatestCheck({ status: "NO_CHANGE" }) })] }),
    );
    mockedFetchUpcoming.mockRejectedValue(new Error("down"));
    mockedFetchRecent.mockRejectedValue(new Error("down"));
    renderPage();

    const section = await findSection("Latest Data Detected");
    expect(within(section).getByText("No new data detected in the latest check.")).toBeInTheDocument();
  });

  it("Upcoming releases fail; Current State, What Changed, Latest Data Detected, and Recent still render", async () => {
    mockedGetMonitor.mockResolvedValue(buildMonitor());
    mockedGetWhatChanged.mockResolvedValue(buildWhatChanged());
    mockedGetLaborMonitor.mockResolvedValue(buildLaborMonitor());
    mockedGetLaborWhatChanged.mockResolvedValue(buildLaborWhatChanged());
    mockedFetchProcessingStatus.mockResolvedValue(buildReleaseProcessingStatusResponse({ occurrences: [] }));
    mockedFetchUpcoming.mockRejectedValue(new Error("network down"));
    mockedFetchRecent.mockResolvedValue(buildReleaseListResponse({ releases: [buildReleaseOccurrenceItem()] }));
    renderPage();

    expect(await screen.findByText("Upcoming releases could not be loaded.")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Current State" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "What Changed" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Latest Data Detected" })).toBeInTheDocument();
    expect(await screen.findByText("Consumer Price Index")).toBeInTheDocument();
  });

  it("Recent releases fail; Upcoming still renders", async () => {
    mockedGetMonitor.mockResolvedValue(buildMonitor());
    mockedGetWhatChanged.mockResolvedValue(buildWhatChanged());
    mockedGetLaborMonitor.mockResolvedValue(buildLaborMonitor());
    mockedGetLaborWhatChanged.mockResolvedValue(buildLaborWhatChanged());
    mockedFetchProcessingStatus.mockResolvedValue(buildReleaseProcessingStatusResponse({ occurrences: [] }));
    mockedFetchUpcoming.mockResolvedValue(
      buildReleaseListResponse({ releases: [buildReleaseOccurrenceItem({ name: "Advance Retail Sales" })] }),
    );
    mockedFetchRecent.mockRejectedValue(new Error("network down"));
    renderPage();

    expect(await screen.findByText("Recent releases could not be loaded.")).toBeInTheDocument();
    expect(await screen.findByText("Advance Retail Sales")).toBeInTheDocument();
  });

  it("never renders a single Promise.all-style page-level failure -- each error is local to its own section", async () => {
    mockedGetMonitor.mockRejectedValue(new Error("down"));
    mockedGetWhatChanged.mockRejectedValue(new Error("down"));
    mockedGetLaborMonitor.mockRejectedValue(new Error("down"));
    mockedGetLaborWhatChanged.mockRejectedValue(new Error("down"));
    mockedFetchProcessingStatus.mockRejectedValue(new Error("down"));
    mockedFetchUpcoming.mockRejectedValue(new Error("down"));
    mockedFetchRecent.mockRejectedValue(new Error("down"));
    renderPage();

    expect(await screen.findByText("Inflation data could not be loaded.")).toBeInTheDocument();
    expect(await screen.findByText("What changed could not be loaded.")).toBeInTheDocument();
    expect(await screen.findByText("Labor data could not be loaded.")).toBeInTheDocument();
    expect(await screen.findByText("Labor what changed could not be loaded.")).toBeInTheDocument();
    expect(await screen.findByText("Release-processing status is temporarily unavailable.")).toBeInTheDocument();
    expect(await screen.findByText("Upcoming releases could not be loaded.")).toBeInTheDocument();
    expect(await screen.findByText("Recent releases could not be loaded.")).toBeInTheDocument();
    // Still exactly one page title, not a blanked/crashed page.
    expect(screen.getByRole("heading", { level: 1, name: "Economic Overview" })).toBeInTheDocument();
  });
});

describe("navigation", () => {
  it("exposes exactly the real CTAs, no dead links", async () => {
    resolveAll();
    renderPage();

    await screen.findByRole("heading", { name: "Current State" });
    expect(screen.getByRole("link", { name: "Open Inflation →" })).toHaveAttribute("href", "/inflation");
    expect(screen.getByRole("link", { name: "Open Labor →" })).toHaveAttribute("href", "/labor");
    expect(screen.getAllByRole("link", { name: "See full comparison →" }).length).toBe(2);
    expect(screen.getByRole("link", { name: "View release calendar →" })).toHaveAttribute("href", "/releases");
    // No dead/aspirational product surfaces.
    for (const name of ["Explore", "Compare", "Research", "Ask EI", "News", "Watchlist"]) {
      expect(screen.queryByRole("link", { name: new RegExp(name, "i") })).not.toBeInTheDocument();
    }
  });
});

describe("page structure", () => {
  it("uses one h1 and the exact section heading hierarchy", async () => {
    resolveAll();
    renderPage();

    await screen.findByRole("heading", { name: "Current State" });
    expect(screen.getByRole("heading", { level: 1, name: "Economic Overview" })).toBeInTheDocument();
    for (const name of ["Current State", "What Changed", "Latest Data Detected", "Releases"]) {
      expect(screen.getByRole("heading", { level: 2, name })).toBeInTheDocument();
    }
  });

  it("shows the tagline", async () => {
    resolveAll();
    renderPage();
    expect(await screen.findByText("Know what changed in the economy — and prove why.")).toBeInTheDocument();
  });
});
