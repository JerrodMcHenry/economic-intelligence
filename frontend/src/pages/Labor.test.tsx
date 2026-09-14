/**
 * Integration-level tests for the real Labor Market Monitor product
 * page (Increment #20E.2). Every network call is mocked at the module
 * boundary (../api/labor, ../api/releases) with deterministic fixtures
 * (../test/fixtures/labor, ../test/fixtures/releases) -- no live
 * backend required, mirroring pages/Inflation.test.tsx's own
 * established pattern exactly.
 */
import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { getEmploymentSituationProcessingStatus, getLaborMonitor, getLaborWhatChanged } from "../api/labor";
import { fetchRecentReleases, fetchUpcomingReleases } from "../api/releases";
import {
  buildEmploymentResult,
  buildLaborChangeEvent,
  buildLaborMonitor,
  buildLaborWhatChanged,
  buildUnemploymentResult,
} from "../test/fixtures/labor";
import { buildLatestCheck, buildReleaseProcessingStatusItem, buildReleaseProcessingStatusResponse } from "../test/fixtures/processingStatus";
import { buildReleaseListResponse, buildReleaseOccurrenceItem } from "../test/fixtures/releases";
import { LaborPage } from "./Labor";

vi.mock("../api/labor", () => ({
  getLaborMonitor: vi.fn(),
  getLaborWhatChanged: vi.fn(),
  getEmploymentSituationProcessingStatus: vi.fn(),
}));
vi.mock("../api/releases", () => ({
  fetchUpcomingReleases: vi.fn(),
  fetchRecentReleases: vi.fn(),
}));

const mockedGetMonitor = vi.mocked(getLaborMonitor);
const mockedGetWhatChanged = vi.mocked(getLaborWhatChanged);
const mockedGetProcessingStatus = vi.mocked(getEmploymentSituationProcessingStatus);
const mockedFetchUpcoming = vi.mocked(fetchUpcomingReleases);
const mockedFetchRecent = vi.mocked(fetchRecentReleases);

beforeEach(() => {
  mockedGetMonitor.mockReset();
  mockedGetWhatChanged.mockReset();
  mockedGetProcessingStatus.mockReset();
  mockedFetchUpcoming.mockReset();
  mockedFetchRecent.mockReset();
});

function resolveAll(overrides: {
  monitor?: ReturnType<typeof buildLaborMonitor>;
  whatChanged?: ReturnType<typeof buildLaborWhatChanged>;
  processingStatus?: ReturnType<typeof buildReleaseProcessingStatusResponse>;
  upcoming?: ReturnType<typeof buildReleaseListResponse>;
  recent?: ReturnType<typeof buildReleaseListResponse>;
} = {}) {
  mockedGetMonitor.mockResolvedValue(overrides.monitor ?? buildLaborMonitor());
  mockedGetWhatChanged.mockResolvedValue(overrides.whatChanged ?? buildLaborWhatChanged());
  mockedGetProcessingStatus.mockResolvedValue(overrides.processingStatus ?? buildReleaseProcessingStatusResponse({ occurrences: [] }));
  mockedFetchUpcoming.mockResolvedValue(overrides.upcoming ?? buildReleaseListResponse({ releases: [] }));
  mockedFetchRecent.mockResolvedValue(overrides.recent ?? buildReleaseListResponse({ releases: [] }));
}

function renderPage() {
  return render(
    <MemoryRouter>
      <LaborPage />
    </MemoryRouter>,
  );
}

async function findSection(name: string): Promise<HTMLElement> {
  const heading = await screen.findByRole("heading", { name });
  return heading.closest("section") as HTMLElement;
}

describe("loading", () => {
  it("shows a stable loading state for all five resources with no fabricated data", () => {
    mockedGetMonitor.mockReturnValue(new Promise(() => {}));
    mockedGetWhatChanged.mockReturnValue(new Promise(() => {}));
    mockedGetProcessingStatus.mockReturnValue(new Promise(() => {}));
    mockedFetchUpcoming.mockReturnValue(new Promise(() => {}));
    mockedFetchRecent.mockReturnValue(new Promise(() => {}));

    renderPage();

    expect(screen.getAllByRole("status").length).toBeGreaterThanOrEqual(5);
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
  });
});

describe("frozen 7-section hierarchy", () => {
  it("renders the exact seven sections, in the exact order frozen by docs/architecture/labor-ui-v1.md §7", async () => {
    resolveAll({
      upcoming: buildReleaseListResponse({ releases: [buildReleaseOccurrenceItem({ provider_release_id: "50" })] }),
    });
    renderPage();

    await screen.findByRole("heading", { name: "Current state" });
    const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(headings).toEqual([
      "Current state",
      "Employment",
      "Unemployment",
      "What changed",
      "Latest data detected",
      "Employment Situation release",
      "Evidence & methodology",
    ]);
  });

  it("WhyLaborState is presented as part of Current State, not a separate top-level section", async () => {
    resolveAll();
    renderPage();

    const currentState = await findSection("Current state");
    // WhyLaborState renders no h2 of its own -- it lives inside LaborHero's
    // <section>, never as its own top-level entry in the heading list above.
    expect(within(currentState).queryAllByRole("heading", { level: 2 })).toHaveLength(1);
  });
});

describe("Current State", () => {
  it.each(["STRENGTHENING", "COOLING", "STABLE", "MIXED", "INSUFFICIENT_DATA"] as const)(
    "renders canonical LaborState %s exactly as returned, never recomputed or reinterpreted",
    async (state) => {
      resolveAll({ monitor: buildLaborMonitor({ state }) });
      renderPage();

      const section = await findSection("Current state");
      const label = state === "INSUFFICIENT_DATA" ? "Insufficient data" : state.charAt(0) + state.slice(1).toLowerCase();
      // Scoped to the primary badge specifically -- the same label text
      // can legitimately also appear inside the collapsed "Why" explanation
      // (e.g. Unemployment's own default state), which is not what this
      // test is checking.
      expect(within(section).getByText(label, { selector: "span" })).toBeInTheDocument();
    },
  );

  it("MIXED is never reinterpreted as Neutral or Uncertain", async () => {
    resolveAll({ monitor: buildLaborMonitor({ state: "MIXED" }) });
    renderPage();

    const section = await findSection("Current state");
    expect(within(section).getByText("Mixed", { selector: "span" })).toBeInTheDocument();
    expect(within(section).queryByText(/neutral/i)).not.toBeInTheDocument();
    expect(within(section).queryByText(/uncertain/i)).not.toBeInTheDocument();
  });

  it("THE CONTRADICTORY-EVIDENCE TEST: backend says COOLING even when Employment condition alone looks expansionary", async () => {
    resolveAll({
      monitor: buildLaborMonitor({
        state: "COOLING",
        employment: buildEmploymentResult({ condition: "EXPANDING", momentum: "WORSENING", state: "COOLING" }),
      }),
    });
    renderPage();

    const section = await findSection("Current state");
    expect(within(section).getByText("Cooling", { selector: "span" })).toBeInTheDocument();
    expect(within(section).queryByText("Strengthening", { selector: "span" })).not.toBeInTheDocument();
  });

  it("shows both Employment and Unemployment's own canonical states in the 'Why' explanation, including for MIXED", async () => {
    resolveAll({
      monitor: buildLaborMonitor({
        state: "MIXED",
        employment: buildEmploymentResult({ state: "RECOVERING" }),
        unemployment: buildUnemploymentResult({ state: "STABLE" }),
      }),
    });
    renderPage();

    const section = await findSection("Current state");
    const why = within(section).getByText("Why Mixed?");
    why.click();
    expect(await within(section).findByText("Recovering")).toBeInTheDocument();
    expect(within(section).getByText("Stable")).toBeInTheDocument();
  });

  it("no directional color-only signal -- state is always shown as text", async () => {
    resolveAll({ monitor: buildLaborMonitor({ state: "STRENGTHENING" }) });
    renderPage();

    const section = await findSection("Current state");
    expect(within(section).getByText("Strengthening", { selector: "span" })).toBeInTheDocument();
  });
});

describe("Employment", () => {
  it.each(["EXPANDING", "COOLING", "STABLE", "CONTRACTING", "RECOVERING", "INSUFFICIENT_DATA"] as const)(
    "renders canonical EmploymentState %s",
    async (state) => {
      resolveAll({ monitor: buildLaborMonitor({ employment: buildEmploymentResult({ state }) }) });
      renderPage();

      const section = await findSection("Employment");
      const label = state === "INSUFFICIENT_DATA" ? "Insufficient data" : state.charAt(0) + state.slice(1).toLowerCase();
      expect(within(section).getByText(label, { selector: "span" })).toBeInTheDocument();
    },
  );

  it("renders EmploymentState as the single primary badge, with condition/momentum as secondary text -- never three co-equal badges", async () => {
    resolveAll({ monitor: buildLaborMonitor({ employment: buildEmploymentResult({ condition: "EXPANDING", momentum: "STEADY", state: "EXPANDING" }) }) });
    renderPage();

    const section = await findSection("Employment");
    expect(within(section).getByText("Expanding", { selector: "span" })).toBeInTheDocument();
    expect(within(section).getByText("Steady", { selector: "dd" })).toBeInTheDocument();
    // Only one badge-shaped pill element should be the primary
    // EmploymentState -- condition/momentum are plain text, never
    // additional badges. `Badge` renders as a `<span class="rounded-full">`;
    // `ExplanationTrigger`'s own circular "i" icon also uses
    // `rounded-full` but renders as a `<summary>`, so scoping by tag
    // correctly isolates just the Badge.
    const badges = section.querySelectorAll("span.rounded-full");
    expect(badges.length).toBe(1);
  });

  it("summary metrics use actual-jobs formatting, never percent", async () => {
    resolveAll({
      monitor: buildLaborMonitor({
        employment: buildEmploymentResult({ current_3m_avg_jobs: -331333.33, prior_3m_avg_jobs: -617333.33, momentum_delta_jobs: 286000 }),
      }),
    });
    renderPage();

    const section = await findSection("Employment");
    expect(within(section).getByText("-331,333")).toBeInTheDocument();
    expect(within(section).getByText("-617,333")).toBeInTheDocument();
    expect(within(section).getByText("286,000")).toBeInTheDocument();
    expect(within(section).queryByText(/-331,333%/)).not.toBeInTheDocument();
  });

  it("raw evidence observations render in thousands-of-persons, never converted, distinctly labeled from the summary tier", async () => {
    resolveAll({
      monitor: buildLaborMonitor({
        employment: buildEmploymentResult({
          observations: [{ series_id: "PAYEMS", observation_date: "2009-08-01", value: 130472 }],
        }),
      }),
    });
    renderPage();

    const section = await findSection("Employment");
    const disclosure = within(section).getByText("View evidence: Employment");
    disclosure.click();
    expect(await within(section).findByText("130,472")).toBeInTheDocument();
    expect(within(section).getByText(/Thousands of persons/)).toBeInTheDocument();
    // Never silently multiplied by 1,000 into an actual-jobs-shaped number.
    expect(within(section).queryByText("130,472,000")).not.toBeInTheDocument();
  });
});

describe("Unemployment", () => {
  it.each(["IMPROVING", "DETERIORATING", "STABLE", "INSUFFICIENT_DATA"] as const)(
    "renders canonical UnemploymentTrendState %s",
    async (state) => {
      resolveAll({ monitor: buildLaborMonitor({ unemployment: buildUnemploymentResult({ state }) }) });
      renderPage();

      const section = await findSection("Unemployment");
      const label = state === "INSUFFICIENT_DATA" ? "Insufficient data" : state.charAt(0) + state.slice(1).toLowerCase();
      expect(within(section).getByText(label, { selector: "span" })).toBeInTheDocument();
    },
  );

  it("formats current_3m_avg/prior_year_3m_avg as percentages and delta_pp with a signed pp suffix", async () => {
    resolveAll({
      monitor: buildLaborMonitor({ unemployment: buildUnemploymentResult({ current_3m_avg: 4.0, prior_year_3m_avg: 4.2, delta_pp: -0.2 }) }),
    });
    renderPage();

    const section = await findSection("Unemployment");
    expect(within(section).getByText("4.00%")).toBeInTheDocument();
    expect(within(section).getByText("4.20%")).toBeInTheDocument();
    expect(within(section).getByText("-0.20 pp")).toBeInTheDocument();
  });

  it("never treats the unemployment rate alone as the whole Labor state -- shows the combining relationship", async () => {
    resolveAll();
    renderPage();

    const section = await findSection("Unemployment");
    expect(within(section).getByText(/Labor combines this unemployment trend with the Employment section/)).toBeInTheDocument();
  });
});

describe("What Changed", () => {
  it("shows the exact required copy when zero events are reported, never 'Labor remained stable'", async () => {
    resolveAll({ whatChanged: buildLaborWhatChanged({ changes: [] }) });
    renderPage();

    const section = await findSection("What changed");
    expect(within(section).getByText("No canonical Labor changes were reported for this comparison.")).toBeInTheDocument();
    expect(within(section).queryByText(/labor remained stable/i)).not.toBeInTheDocument();
  });

  it("renders a top-level LABOR state event as the tier-1 headline", async () => {
    resolveAll({
      whatChanged: buildLaborWhatChanged({
        changes: [buildLaborChangeEvent({ component: "LABOR", event_type: "STATE_CHANGED", field: "state", previous_value: "COOLING", current_value: "MIXED" })],
      }),
    });
    renderPage();

    const section = await findSection("What changed");
    expect(within(section).getByText(/Labor state:/)).toBeInTheDocument();
    expect(within(section).getByText(/Cooling/)).toBeInTheDocument();
    expect(within(section).getByText(/Mixed/)).toBeInTheDocument();
  });

  it("renders EMPLOYMENT/UNEMPLOYMENT state events at tier 2", async () => {
    resolveAll({
      whatChanged: buildLaborWhatChanged({
        changes: [buildLaborChangeEvent({ component: "EMPLOYMENT", event_type: "STATE_CHANGED", field: "state", previous_value: "CONTRACTING", current_value: "RECOVERING" })],
      }),
    });
    renderPage();

    const section = await findSection("What changed");
    expect(within(section).getByText(/Contracting/)).toBeInTheDocument();
    expect(within(section).getByText(/Recovering/)).toBeInTheDocument();
  });

  it("renders condition/momentum events independently -- never suppressed by a co-occurring state change", async () => {
    resolveAll({
      whatChanged: buildLaborWhatChanged({
        changes: [
          buildLaborChangeEvent({ component: "EMPLOYMENT", event_type: "STATE_CHANGED", field: "state", previous_value: "CONTRACTING", current_value: "RECOVERING" }),
          buildLaborChangeEvent({ component: "EMPLOYMENT", event_type: "STATE_CHANGED", field: "momentum", previous_value: "STEADY", current_value: "IMPROVING" }),
        ],
      }),
    });
    renderPage();

    const section = await findSection("What changed");
    expect(within(section).getByText(/Steady/)).toBeInTheDocument();
    expect(within(section).getByText(/Improving/)).toBeInTheDocument();
  });

  it("renders AVAILABILITY_LOST/RESTORED as data-availability facts, never economic direction", async () => {
    resolveAll({
      whatChanged: buildLaborWhatChanged({
        changes: [buildLaborChangeEvent({ component: "EMPLOYMENT", event_type: "AVAILABILITY_RESTORED", field: "state", previous_value: "INSUFFICIENT_DATA", current_value: "RECOVERING" })],
      }),
    });
    renderPage();

    const section = await findSection("What changed");
    expect(within(section).getByText(/became available/)).toBeInTheDocument();
    expect(within(section).queryByText(/improved/i)).not.toBeInTheDocument();
    expect(within(section).queryByText(/strengthened/i)).not.toBeInTheDocument();
  });

  it("places numeric METRIC_CHANGED events behind a secondary 'Metric updates' disclosure", async () => {
    resolveAll({
      whatChanged: buildLaborWhatChanged({
        changes: [buildLaborChangeEvent({ component: "EMPLOYMENT", event_type: "METRIC_CHANGED", field: "current_3m_avg_jobs", previous_value: 100000, current_value: 150000, delta: 50000 })],
      }),
    });
    renderPage();

    const section = await findSection("What changed");
    expect(within(section).getByText(/Metric updates/)).toBeInTheDocument();
  });

  it("every backend event remains inspectable -- multiple simultaneous events all render somewhere on the page", async () => {
    resolveAll({
      whatChanged: buildLaborWhatChanged({
        changes: [
          buildLaborChangeEvent({ component: "LABOR", event_type: "STATE_CHANGED", field: "state", previous_value: "COOLING", current_value: "MIXED" }),
          buildLaborChangeEvent({ component: "EMPLOYMENT", event_type: "STATE_CHANGED", field: "condition", previous_value: "FLAT", current_value: "EXPANDING" }),
          buildLaborChangeEvent({ component: "UNEMPLOYMENT", event_type: "METRIC_CHANGED", field: "delta_pp", previous_value: -0.1, current_value: 0.3, delta: 0.4 }),
        ],
      }),
    });
    renderPage();

    const section = await findSection("What changed");
    expect(within(section).getByText(/Labor state:/)).toBeInTheDocument();
    expect(within(section).getByText(/Condition/)).toBeInTheDocument();
    expect(within(section).getByText(/Metric updates/)).toBeInTheDocument();
  });
});

describe("Latest Data Detected", () => {
  it("renders the scoped Employment Situation processing-status evidence", async () => {
    resolveAll({
      processingStatus: buildReleaseProcessingStatusResponse({
        occurrences: [buildReleaseProcessingStatusItem({ latest_check: buildLatestCheck({ status: "CHANGES_DETECTED" }) })],
      }),
    });
    renderPage();

    const section = await findSection("Latest data detected");
    expect(within(section).getByText("Data changes detected.")).toBeInTheDocument();
  });

  it("shows the empty-state message when there is no tracked processing record", async () => {
    resolveAll({ processingStatus: buildReleaseProcessingStatusResponse({ occurrences: [] }) });
    renderPage();

    const section = await findSection("Latest data detected");
    expect(within(section).getByText("No tracked release processing records are available yet.")).toBeInTheDocument();
  });
});

describe("Relevant Release", () => {
  it("shows the next scheduled Employment Situation occurrence, reusing the existing release row", async () => {
    resolveAll({
      upcoming: buildReleaseListResponse({
        releases: [buildReleaseOccurrenceItem({ name: "Employment Situation", provider_release_id: "50", scheduled_date: "2026-10-02" })],
      }),
    });
    renderPage();

    expect(await screen.findByText("Next scheduled")).toBeInTheDocument();
    expect(screen.getAllByText("Employment Situation").length).toBeGreaterThanOrEqual(1);
  });

  it("Increment #22B: never renders ReleaseRow's per-row 'View Labor →' CTA here -- it would be circular, already on /labor", async () => {
    resolveAll({
      upcoming: buildReleaseListResponse({
        releases: [buildReleaseOccurrenceItem({ name: "Employment Situation", provider_release_id: "50", scheduled_date: "2026-10-02" })],
      }),
    });
    renderPage();

    await screen.findByText("Next scheduled");
    expect(screen.queryByRole("link", { name: "View Labor →" })).not.toBeInTheDocument();
  });

  it("the mandatory release schedule disclosure is byte-identical to the canonical sentence", async () => {
    resolveAll();
    renderPage();

    expect(
      await screen.findByText(
        "Release dates indicate scheduled publication dates. They do not confirm that new data has been published, ingested, or reflected in Economic Intelligence analysis.",
      ),
    ).toBeInTheDocument();
  });
});

describe("Evidence & methodology", () => {
  it("shows methodology_id, data_basis, and comparison_contract_id unobtrusively behind a disclosure", async () => {
    resolveAll();
    renderPage();

    const section = await findSection("Evidence & methodology");
    const disclosure = within(section).getByText("Methodology and coverage detail");
    disclosure.click();
    expect(await within(section).findByText("labor_v1.0")).toBeInTheDocument();
    expect(within(section).getByText("labor_what_changed_v1.0")).toBeInTheDocument();
    expect(within(section).getByText("latest_revised_data")).toBeInTheDocument();
  });
});

describe("failure isolation", () => {
  it("Labor monitor fails; What Changed, Latest Data Detected, and Relevant Release still render", async () => {
    mockedGetMonitor.mockRejectedValue(new Error("down"));
    mockedGetWhatChanged.mockResolvedValue(buildLaborWhatChanged());
    mockedGetProcessingStatus.mockResolvedValue(buildReleaseProcessingStatusResponse({ occurrences: [] }));
    mockedFetchUpcoming.mockResolvedValue(buildReleaseListResponse({ releases: [] }));
    mockedFetchRecent.mockResolvedValue(buildReleaseListResponse({ releases: [] }));
    renderPage();

    expect(await screen.findByText("Labor data could not be loaded.")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "What changed" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Latest data detected" })).toBeInTheDocument();
  });

  it("Labor changes fails; Current State, Employment, Unemployment still render", async () => {
    mockedGetMonitor.mockResolvedValue(buildLaborMonitor());
    mockedGetWhatChanged.mockRejectedValue(new Error("down"));
    mockedGetProcessingStatus.mockResolvedValue(buildReleaseProcessingStatusResponse({ occurrences: [] }));
    mockedFetchUpcoming.mockResolvedValue(buildReleaseListResponse({ releases: [] }));
    mockedFetchRecent.mockResolvedValue(buildReleaseListResponse({ releases: [] }));
    renderPage();

    expect(await screen.findByText("What changed could not be loaded.")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Current state" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Employment" })).toBeInTheDocument();
  });

  it("processing status fails; Current State and What Changed still render", async () => {
    mockedGetMonitor.mockResolvedValue(buildLaborMonitor());
    mockedGetWhatChanged.mockResolvedValue(buildLaborWhatChanged());
    mockedGetProcessingStatus.mockRejectedValue(new Error("down"));
    mockedFetchUpcoming.mockResolvedValue(buildReleaseListResponse({ releases: [] }));
    mockedFetchRecent.mockResolvedValue(buildReleaseListResponse({ releases: [] }));
    renderPage();

    expect(await screen.findByText("Release-processing status is temporarily unavailable.")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Current state" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "What changed" })).toBeInTheDocument();
  });

  it("upcoming releases fail; recent-release evidence (if any) still renders", async () => {
    mockedGetMonitor.mockResolvedValue(buildLaborMonitor());
    mockedGetWhatChanged.mockResolvedValue(buildLaborWhatChanged());
    mockedGetProcessingStatus.mockResolvedValue(buildReleaseProcessingStatusResponse({ occurrences: [] }));
    mockedFetchUpcoming.mockRejectedValue(new Error("down"));
    mockedFetchRecent.mockResolvedValue(
      buildReleaseListResponse({ releases: [buildReleaseOccurrenceItem({ name: "Employment Situation", provider_release_id: "50" })] }),
    );
    renderPage();

    expect(await screen.findByText("Upcoming releases could not be loaded.")).toBeInTheDocument();
    expect(await screen.findByText("Most recent")).toBeInTheDocument();
  });

  it("never renders a single page-level failure -- each error is local to its own section", async () => {
    mockedGetMonitor.mockRejectedValue(new Error("down"));
    mockedGetWhatChanged.mockRejectedValue(new Error("down"));
    mockedGetProcessingStatus.mockRejectedValue(new Error("down"));
    mockedFetchUpcoming.mockRejectedValue(new Error("down"));
    mockedFetchRecent.mockRejectedValue(new Error("down"));
    renderPage();

    expect(await screen.findByText("Labor data could not be loaded.")).toBeInTheDocument();
    expect(await screen.findByText("What changed could not be loaded.")).toBeInTheDocument();
    expect(await screen.findByText("Release-processing status is temporarily unavailable.")).toBeInTheDocument();
    expect(await screen.findByText("Upcoming releases could not be loaded.")).toBeInTheDocument();
    expect(await screen.findByText("Recent releases could not be loaded.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Labor" })).toBeInTheDocument();
  });
});

describe("accessibility basics", () => {
  it("uses a single h1 and semantic h2 section headings for the page's structure", async () => {
    resolveAll();
    renderPage();

    await screen.findByRole("heading", { name: "Current state" });
    expect(screen.getByRole("heading", { level: 1, name: "Labor" })).toBeInTheDocument();
    for (const name of ["Current state", "Employment", "Unemployment", "What changed", "Latest data detected", "Evidence & methodology"]) {
      expect(screen.getByRole("heading", { level: 2, name })).toBeInTheDocument();
    }
  });
});
