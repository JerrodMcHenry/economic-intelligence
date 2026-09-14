/**
 * Integration-level tests for the Economic Overview product page
 * (Increment #19A). All four canonical read calls
 * (`getInflationMonitor`/`getInflationWhatChanged`/
 * `fetchUpcomingReleases`/`fetchRecentReleases`) are mocked at the
 * module boundary -- no live backend required, the same pattern
 * pages/Inflation.test.tsx and pages/Releases.test.tsx already
 * establish. Wrapped in MemoryRouter since Overview links to
 * `/inflation`/`/releases` via react-router's `Link`.
 */
import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { getInflationMonitor, getInflationWhatChanged } from "../api/inflation";
import { fetchRecentReleases, fetchUpcomingReleases } from "../api/releases";
import {
  buildChangeEvent,
  buildMomentum,
  buildMonitor,
  buildWhatChanged,
} from "../test/fixtures/inflation";
import { buildReleaseListResponse, buildReleaseOccurrenceItem } from "../test/fixtures/releases";
import { OverviewPage } from "./Overview";

vi.mock("../api/inflation", () => ({
  getInflationMonitor: vi.fn(),
  getInflationWhatChanged: vi.fn(),
}));
vi.mock("../api/releases", () => ({
  fetchUpcomingReleases: vi.fn(),
  fetchRecentReleases: vi.fn(),
}));

const mockedGetMonitor = vi.mocked(getInflationMonitor);
const mockedGetWhatChanged = vi.mocked(getInflationWhatChanged);
const mockedFetchUpcoming = vi.mocked(fetchUpcomingReleases);
const mockedFetchRecent = vi.mocked(fetchRecentReleases);

beforeEach(() => {
  mockedGetMonitor.mockReset();
  mockedGetWhatChanged.mockReset();
  mockedFetchUpcoming.mockReset();
  mockedFetchRecent.mockReset();
});

function resolveAll(overrides: {
  monitor?: ReturnType<typeof buildMonitor>;
  whatChanged?: ReturnType<typeof buildWhatChanged>;
  upcoming?: ReturnType<typeof buildReleaseListResponse>;
  recent?: ReturnType<typeof buildReleaseListResponse>;
} = {}) {
  mockedGetMonitor.mockResolvedValue(overrides.monitor ?? buildMonitor());
  mockedGetWhatChanged.mockResolvedValue(overrides.whatChanged ?? buildWhatChanged());
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
  it("shows a stable loading state for all four sections with no fabricated data", () => {
    mockedGetMonitor.mockReturnValue(new Promise(() => {}));
    mockedGetWhatChanged.mockReturnValue(new Promise(() => {}));
    mockedFetchUpcoming.mockReturnValue(new Promise(() => {}));
    mockedFetchRecent.mockReturnValue(new Promise(() => {}));

    renderPage();

    expect(screen.getAllByRole("status").length).toBeGreaterThanOrEqual(4);
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
  });
});

describe("Current State", () => {
  it("renders Inflation as a labeled dimension, not as the state of the economy", async () => {
    resolveAll({ monitor: buildMonitor({ underlying_momentum: buildMomentum({ state: "MIXED" }) }) });
    renderPage();

    const section = await findSection("Current State");
    expect(within(section).getByText("Inflation")).toBeInTheDocument();
    expect(within(section).getByText("Mixed", { selector: "span" })).toBeInTheDocument();
    // Never a synthetic economy-wide label.
    expect(screen.queryByText(/Economy:/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Economic State/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Risk Level/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Macro Score/i)).not.toBeInTheDocument();
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

  it("shows the restrained 'more dimensions' note, never five fake dimension cards", async () => {
    resolveAll();
    renderPage();

    const section = await findSection("Current State");
    expect(
      within(section).getByText(
        "Inflation is the first fully deterministic monitor. More are being added as their methodologies are built.",
      ),
    ).toBeInTheDocument();
    for (const label of ["Labor", "Growth", "Consumer", "Housing", "Financial Conditions"]) {
      expect(screen.queryByText(new RegExp(`^${label}\\s*(—|-)?\\s*Coming Soon`, "i"))).not.toBeInTheDocument();
    }
  });

  it("links to /inflation via 'Open Inflation'", async () => {
    resolveAll();
    renderPage();

    const section = await findSection("Current State");
    const link = within(section).getByRole("link", { name: "Open Inflation →" });
    expect(link).toHaveAttribute("href", "/inflation");
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
    const items = within(section).getAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(items[0]!.textContent).toMatch(/Headline CPI/);
    expect(items[1]!.textContent).toMatch(/Core PCE/);
    expect(items[2]!.textContent).toMatch(/Target/);
    // The 4th event (Confirmation) never appears.
    expect(within(section).queryByText(/Confirmation/)).not.toBeInTheDocument();
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

  it("shows a precise, non-inventive empty-state message when zero events are reported", async () => {
    resolveAll({ whatChanged: buildWhatChanged({ changes: [] }) });
    renderPage();

    const section = await findSection("What Changed");
    expect(within(section).getByText("No canonical Inflation changes were reported for this comparison.")).toBeInTheDocument();
    expect(within(section).queryByText(/Inflation was unchanged/i)).not.toBeInTheDocument();
  });

  it("links to /inflation via 'See full comparison'", async () => {
    resolveAll();
    renderPage();

    const section = await findSection("What Changed");
    const link = within(section).getByRole("link", { name: "See full comparison →" });
    expect(link).toHaveAttribute("href", "/inflation");
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
  it("Inflation monitor fails; What Changed and Releases still render", async () => {
    mockedGetMonitor.mockRejectedValue(new Error("network down"));
    mockedGetWhatChanged.mockResolvedValue(buildWhatChanged());
    mockedFetchUpcoming.mockResolvedValue(buildReleaseListResponse({ releases: [] }));
    mockedFetchRecent.mockResolvedValue(buildReleaseListResponse({ releases: [] }));
    renderPage();

    expect(await screen.findByText("Inflation data could not be loaded.")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "What Changed" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Releases" })).toBeInTheDocument();
  });

  it("What Changed fails; Current State and Releases still render", async () => {
    mockedGetMonitor.mockResolvedValue(buildMonitor());
    mockedGetWhatChanged.mockRejectedValue(new Error("network down"));
    mockedFetchUpcoming.mockResolvedValue(buildReleaseListResponse({ releases: [] }));
    mockedFetchRecent.mockResolvedValue(buildReleaseListResponse({ releases: [] }));
    renderPage();

    expect(await screen.findByText("What changed could not be loaded.")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Current State" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Releases" })).toBeInTheDocument();
  });

  it("Upcoming releases fail; Current State, What Changed, and Recent still render", async () => {
    mockedGetMonitor.mockResolvedValue(buildMonitor());
    mockedGetWhatChanged.mockResolvedValue(buildWhatChanged());
    mockedFetchUpcoming.mockRejectedValue(new Error("network down"));
    mockedFetchRecent.mockResolvedValue(buildReleaseListResponse({ releases: [buildReleaseOccurrenceItem()] }));
    renderPage();

    expect(await screen.findByText("Upcoming releases could not be loaded.")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Current State" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "What Changed" })).toBeInTheDocument();
    expect(await screen.findByText("Consumer Price Index")).toBeInTheDocument();
  });

  it("Recent releases fail; Upcoming still renders", async () => {
    mockedGetMonitor.mockResolvedValue(buildMonitor());
    mockedGetWhatChanged.mockResolvedValue(buildWhatChanged());
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
    mockedFetchUpcoming.mockRejectedValue(new Error("down"));
    mockedFetchRecent.mockRejectedValue(new Error("down"));
    renderPage();

    expect(await screen.findByText("Inflation data could not be loaded.")).toBeInTheDocument();
    expect(await screen.findByText("What changed could not be loaded.")).toBeInTheDocument();
    expect(await screen.findByText("Upcoming releases could not be loaded.")).toBeInTheDocument();
    expect(await screen.findByText("Recent releases could not be loaded.")).toBeInTheDocument();
    // Still exactly one page title, not a blanked/crashed page.
    expect(screen.getByRole("heading", { level: 1, name: "Economic Overview" })).toBeInTheDocument();
  });
});

describe("navigation", () => {
  it("exposes exactly the three real CTAs, no dead links", async () => {
    resolveAll();
    renderPage();

    await screen.findByRole("heading", { name: "Current State" });
    expect(screen.getByRole("link", { name: "Open Inflation →" })).toHaveAttribute("href", "/inflation");
    expect(screen.getByRole("link", { name: "See full comparison →" })).toHaveAttribute("href", "/inflation");
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
    for (const name of ["Current State", "What Changed", "Releases"]) {
      expect(screen.getByRole("heading", { level: 2, name })).toBeInTheDocument();
    }
  });

  it("shows the tagline", async () => {
    resolveAll();
    renderPage();
    expect(await screen.findByText("Know what changed in the economy — and prove why.")).toBeInTheDocument();
  });
});
