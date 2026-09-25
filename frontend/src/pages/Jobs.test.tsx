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

import { getAnalystAvailability } from "../api/analyst";

import { getEmploymentSituationProcessingStatus, getLaborMonitor, getLaborStateDuration, getLaborWhatChanged } from "../api/labor";
import { getLaborHistory } from "../api/monitorHistory";
import { fetchRecentReleases, fetchUpcomingReleases } from "../api/releases";
import {
  buildEmploymentResult,
  buildLaborChangeEvent,
  buildLaborMonitor,
  buildLaborWhatChanged,
  buildUnemploymentResult,
} from "../test/fixtures/labor";
import { buildPayrollObservations, buildUnemploymentObservations } from "../test/fixtures/labor";
import { getPayrollObservations, getUnemploymentObservations } from "../api/series";
import { buildEmptyHistoryResponse } from "../test/fixtures/monitorHistory";
import { buildLatestCheck, buildReleaseProcessingStatusItem, buildReleaseProcessingStatusResponse } from "../test/fixtures/processingStatus";
import { buildReleaseListResponse, buildReleaseOccurrenceItem } from "../test/fixtures/releases";
import { buildStateDurationAvailable, buildStateDurationCurrentInsufficient } from "../test/fixtures/stateDuration";
import { JobsPage } from "./Jobs";

vi.mock("../api/labor", () => ({
  getLaborMonitor: vi.fn(),
  getLaborWhatChanged: vi.fn(),
  getEmploymentSituationProcessingStatus: vi.fn(),
  getLaborStateDuration: vi.fn(),
}));
vi.mock("../api/releases", () => ({
  fetchUpcomingReleases: vi.fn(),
  fetchRecentReleases: vi.fn(),
}));
vi.mock("../api/analyst", () => ({ getAnalystAvailability: vi.fn() }));
vi.mock("../api/monitorHistory", () => ({ getLaborHistory: vi.fn() }));
// #51B: the two published series are a seventh and eighth independent
// resource. Resolved defaults so no pre-existing test hangs on a
// section it is not about.
vi.mock("../api/series", () => ({ getPayrollObservations: vi.fn(), getUnemploymentObservations: vi.fn() }));

const mockedGetMonitor = vi.mocked(getLaborMonitor);
const mockedGetWhatChanged = vi.mocked(getLaborWhatChanged);
const mockedGetProcessingStatus = vi.mocked(getEmploymentSituationProcessingStatus);
const mockedFetchUpcoming = vi.mocked(fetchUpcomingReleases);
const mockedFetchRecent = vi.mocked(fetchRecentReleases);
const mockedGetStateDuration = vi.mocked(getLaborStateDuration);
const mockedGetAnalyst = vi.mocked(getAnalystAvailability);
const mockedGetHistory = vi.mocked(getLaborHistory);
const mockedGetPayroll = vi.mocked(getPayrollObservations);
const mockedGetUnemploymentSeries = vi.mocked(getUnemploymentObservations);

beforeEach(() => {
  mockedGetMonitor.mockReset();
  mockedGetWhatChanged.mockReset();
  mockedGetProcessingStatus.mockReset();
  mockedFetchUpcoming.mockReset();
  mockedFetchRecent.mockReset();
  mockedGetStateDuration.mockReset();
  // Resolved, non-hanging default for every test unless overridden --
  // State Duration is scoped to its own dedicated describe block below.
  mockedGetPayroll.mockReset();
  mockedGetUnemploymentSeries.mockReset();
  mockedGetPayroll.mockResolvedValue(buildPayrollObservations());
  mockedGetUnemploymentSeries.mockResolvedValue(buildUnemploymentObservations());
  mockedGetStateDuration.mockResolvedValue(buildStateDurationCurrentInsufficient({ methodology_id: "labor_v1.0" }));
  // Increment #32's Intelligence History -- a seventh independent
  // resource, resolved by default so no pre-existing test hangs on or
  // sees an error from a section it is not about. Its own behavior is
  // covered in components/history/IntelligenceHistorySection.test.tsx.
  // Increment #33: the Analyst is optional. Default these page tests
  // to "not configured", which is the shape every pre-existing
  // assertion here was written against -- the surface then renders one
  // unavailable line and changes nothing else.
  mockedGetAnalyst.mockReset();
  mockedGetAnalyst.mockResolvedValue({ available: false, reason: "NOT_CONFIGURED" });
  mockedGetHistory.mockReset();
  mockedGetHistory.mockResolvedValue(buildEmptyHistoryResponse("labor"));
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
      <JobsPage />
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
  it("renders the frozen seven monitor sections in order, plus #44's page-level footer", async () => {
    resolveAll({
      upcoming: buildReleaseListResponse({ releases: [buildReleaseOccurrenceItem({ provider_release_id: "empsit" })] }),
    });
    renderPage();

    await screen.findByRole("heading", { name: "Two surveys, side by side" });
    const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    // #51B: the two surveys became one switch, the state became a
    // conclusion after the evidence, and each survey's full detail
    // moved behind a disclosure. Nothing was removed.
    expect(headings).toEqual([
      "Two surveys, side by side",
      "What MacroChipz concludes",
      "Current state",
      "Each survey in full",
      "Employment",
      "Unemployment",
      "What this page does not have",
      "What changed",
      "Latest data detected",
      "Employment Situation release",
      "Intelligence history",
      "Ask MacroChipz",
      "Evidence & methodology",
      // #44 appended a page-level footer offering explainers. The
      // SEVEN MONITOR SECTIONS frozen by docs/architecture/labor-ui-v1.md
      // §7 are unchanged above it -- this sits outside that hierarchy,
      // after the evidence, and is recorded in that document.
      "Understand this",
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

describe("State Duration V1 (Increment #24D)", () => {
  it("shows a loading skeleton for state duration independently of the monitor resource", async () => {
    resolveAll();
    mockedGetStateDuration.mockReturnValue(new Promise(() => {}));
    renderPage();

    const section = await findSection("Current state");
    expect(within(section).getAllByRole("status").length).toBeGreaterThanOrEqual(1);
  });

  it("renders the exact frozen EXACT copy, using duration_months/earliest_confirmed_period/state exactly as supplied", async () => {
    resolveAll();
    mockedGetStateDuration.mockResolvedValue(
      buildStateDurationAvailable({
        state: "STRENGTHENING",
        boundary_type: "EXACT",
        duration_months: 4,
        earliest_confirmed_period: "2026-03-01",
        methodology_id: "labor_v1.0",
      }),
    );
    renderPage();

    expect(
      await screen.findByText("Latest-revised reconstruction: Strengthening for 4 consecutive months, since March 2026."),
    ).toBeInTheDocument();
  });

  it("renders the exact frozen DATA_BOUNDED lower-bound copy", async () => {
    resolveAll();
    mockedGetStateDuration.mockResolvedValue(
      buildStateDurationAvailable({ state: "COOLING", boundary_type: "DATA_BOUNDED", duration_months: 3, methodology_id: "labor_v1.0" }),
    );
    renderPage();

    expect(await screen.findByText("Latest-revised reconstruction: Cooling for at least 3 consecutive months.")).toBeInTheDocument();
  });

  it("renders the exact frozen LOOKBACK_BOUNDED lower-bound copy", async () => {
    resolveAll();
    mockedGetStateDuration.mockResolvedValue(
      buildStateDurationAvailable({ state: "COOLING", boundary_type: "LOOKBACK_BOUNDED", duration_months: 60, methodology_id: "labor_v1.0" }),
    );
    renderPage();

    expect(await screen.findByText("Latest-revised reconstruction: Cooling for at least 60 consecutive months.")).toBeInTheDocument();
  });

  it("renders the exact frozen CURRENT_INSUFFICIENT copy, never a fabricated duration", async () => {
    resolveAll();
    mockedGetStateDuration.mockResolvedValue(buildStateDurationCurrentInsufficient({ methodology_id: "labor_v1.0" }));
    renderPage();

    expect(
      await screen.findByText("Historical state duration is unavailable because the current state has insufficient data."),
    ).toBeInTheDocument();
  });

  it("renders the existing ErrorMessage/retry pattern on infrastructure failure -- never the CURRENT_INSUFFICIENT copy", async () => {
    resolveAll();
    mockedGetStateDuration.mockRejectedValue(new Error("network"));
    renderPage();

    expect(await screen.findByText("Historical state duration could not be loaded.")).toBeInTheDocument();
    expect(screen.queryByText(/insufficient data/i)).not.toBeInTheDocument();
  });

  it("a state-duration API failure never breaks the canonical Labor state or WhyLaborState", async () => {
    resolveAll({ monitor: buildLaborMonitor({ state: "STRENGTHENING" }) });
    mockedGetStateDuration.mockRejectedValue(new Error("network"));
    renderPage();

    await screen.findByText("Historical state duration could not be loaded.");
    const section = await findSection("Current state");
    expect(within(section).getByText("Strengthening", { selector: "span" })).toBeInTheDocument();
    expect(within(section).getByText("Why Strengthening?")).toBeInTheDocument();
  });

  it("shows previous_state/previous_period only for EXACT, never fabricated for DATA_BOUNDED", async () => {
    resolveAll();
    mockedGetStateDuration.mockResolvedValue(
      buildStateDurationAvailable({
        boundary_type: "EXACT",
        previous_state: "STABLE",
        previous_period: "2026-02-01",
        methodology_id: "labor_v1.0",
      }),
    );
    renderPage();

    expect(await screen.findByText("Previously Stable, as of February 2026.")).toBeInTheDocument();
  });

  it("never shows a previous-state note for DATA_BOUNDED", async () => {
    resolveAll();
    mockedGetStateDuration.mockResolvedValue(
      buildStateDurationAvailable({ boundary_type: "DATA_BOUNDED", previous_state: null, previous_period: null, methodology_id: "labor_v1.0" }),
    );
    renderPage();

    await screen.findByText(/Latest-revised reconstruction/);
    expect(screen.queryByText(/^Previously/)).not.toBeInTheDocument();
  });

  it("renders directly inside the Current State Hero section, before WhyLaborState -- not a new page section", async () => {
    resolveAll();
    mockedGetStateDuration.mockResolvedValue(buildStateDurationAvailable({ boundary_type: "EXACT", methodology_id: "labor_v1.0" }));
    renderPage();

    const section = await findSection("Current state");
    const durationText = within(section).getByText(/Latest-revised reconstruction/);
    const whyToggle = within(section).getByText("Why Strengthening?");
    expect(durationText.compareDocumentPosition(whyToggle) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // State Duration contributes NO section heading of its own -- the
    // point of this assertion. (Increment #32 later added a genuine
    // "Intelligence history" section, which is a different feature and
    // is excluded here rather than allowed to mask a #24D regression.)
    const stateDurationHeadings = screen
      .getAllByRole("heading", { level: 2 })
      .map((heading) => heading.textContent)
      .filter((text) => text !== null && /duration|history of/i.test(text));
    expect(stateDurationHeadings).toEqual([]);
  });

  it("preserves the existing #23C Relate composition sentence inside WhyLaborState, unaffected by State Duration", async () => {
    resolveAll();
    mockedGetStateDuration.mockResolvedValue(buildStateDurationAvailable({ boundary_type: "EXACT", methodology_id: "labor_v1.0" }));
    renderPage();

    const section = await findSection("Current state");
    const why = within(section).getByText("Why Strengthening?");
    why.click();
    expect(await within(section).findByText(/Together, MacroChipz classifies Jobs/)).toBeInTheDocument();
  });

  it("leaves the canonical current state and evaluation period completely unchanged", async () => {
    resolveAll({ monitor: buildLaborMonitor({ state: "COOLING", evaluation_period: "2026-09-01" }) });
    mockedGetStateDuration.mockResolvedValue(buildStateDurationAvailable({ state: "COOLING", boundary_type: "EXACT", methodology_id: "labor_v1.0" }));
    renderPage();

    const section = await findSection("Current state");
    expect(within(section).getByText("Cooling", { selector: "span" })).toBeInTheDocument();
    expect(within(section).getByText(/Jobs · September 2026/)).toBeInTheDocument();
  });
});

describe("Relate V1 composition, inside the existing WhyLaborState disclosure (Increment #23C)", () => {
  it("appears inside the existing 'Why {state}?' disclosure, not as a new page section", async () => {
    resolveAll({
      monitor: buildLaborMonitor({
        state: "COOLING",
        employment: buildEmploymentResult({ state: "COOLING" }),
        unemployment: buildUnemploymentResult({ state: "DETERIORATING" }),
      }),
    });
    renderPage();

    // The frozen 7-section hierarchy (see the "frozen 7-section
    // hierarchy" describe block above) gains no new heading.
    await screen.findByRole("heading", { name: "Two surveys, side by side" });
    const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    // #51B: the two surveys became one switch, the state became a
    // conclusion after the evidence, and each survey's full detail
    // moved behind a disclosure. Nothing was removed.
    expect(headings).toEqual([
      "Two surveys, side by side",
      "What MacroChipz concludes",
      "Current state",
      "Each survey in full",
      "Employment",
      "Unemployment",
      "What this page does not have",
      "What changed",
      "Latest data detected",
      "Employment Situation release",
      "Intelligence history",
      "Ask MacroChipz",
      "Evidence & methodology",
      // #44 appended a page-level footer offering explainers. The
      // SEVEN MONITOR SECTIONS frozen by docs/architecture/labor-ui-v1.md
      // §7 are unchanged above it -- this sits outside that hierarchy,
      // after the evidence, and is recorded in that document.
      "Understand this",
    ]);

    const section = await findSection("Current state");
    within(section).getByText("Why Cooling?").click();
    expect(await within(section).findByText("Employment is Cooling and Unemployment is Deteriorating. Together, MacroChipz classifies Jobs as Cooling.")).toBeInTheDocument();
  });

  it("exact Employment/Unemployment/LaborState clause, verbatim", async () => {
    resolveAll({
      monitor: buildLaborMonitor({
        state: "STRENGTHENING",
        employment: buildEmploymentResult({ state: "EXPANDING" }),
        unemployment: buildUnemploymentResult({ state: "IMPROVING" }),
      }),
    });
    renderPage();

    const section = await findSection("Current state");
    within(section).getByText("Why Strengthening?").click();
    expect(
      await within(section).findByText("Employment is Expanding and Unemployment is Improving. Together, MacroChipz classifies Jobs as Strengthening."),
    ).toBeInTheDocument();
  });

  it("the LaborState reported in the sentence is byte-identical to the Hero badge's own state -- never re-derived", async () => {
    resolveAll({
      monitor: buildLaborMonitor({
        state: "MIXED",
        employment: buildEmploymentResult({ state: "RECOVERING" }),
        unemployment: buildUnemploymentResult({ state: "STABLE" }),
      }),
    });
    renderPage();

    const section = await findSection("Current state");
    // The Hero badge itself.
    expect(within(section).getByText("Mixed", { selector: "span" })).toBeInTheDocument();
    within(section).getByText("Why Mixed?").click();
    expect(await within(section).findByText(/classifies Jobs as Mixed\.$/)).toBeInTheDocument();
  });

  it("Employment insufficient: no composed sentence, dedicated fragment only", async () => {
    resolveAll({
      monitor: buildLaborMonitor({
        state: "INSUFFICIENT_DATA",
        employment: buildEmploymentResult({ state: "INSUFFICIENT_DATA" }),
        unemployment: buildUnemploymentResult({ state: "DETERIORATING" }),
      }),
    });
    renderPage();

    const section = await findSection("Current state");
    within(section).getByText("Why Insufficient data?").click();
    expect(await within(section).findByText("Employment does not currently have enough data to classify its state.")).toBeInTheDocument();
    expect(within(section).queryByText(/classifies Jobs as/i)).not.toBeInTheDocument();
  });

  it("Unemployment insufficient (Employment sufficient): dedicated fragment only", async () => {
    resolveAll({
      monitor: buildLaborMonitor({
        state: "INSUFFICIENT_DATA",
        employment: buildEmploymentResult({ state: "STABLE" }),
        unemployment: buildUnemploymentResult({ state: "INSUFFICIENT_DATA" }),
      }),
    });
    renderPage();

    const section = await findSection("Current state");
    within(section).getByText("Why Insufficient data?").click();
    expect(await within(section).findByText("Unemployment does not currently have enough data to classify its state.")).toBeInTheDocument();
    expect(within(section).queryByText(/classifies Jobs as/i)).not.toBeInTheDocument();
  });

  it("does not remove or replace the existing evidence table -- Employment/Unemployment/evaluation period dl remains the source of truth", async () => {
    resolveAll({
      monitor: buildLaborMonitor({
        state: "COOLING",
        employment: buildEmploymentResult({ state: "COOLING" }),
        unemployment: buildUnemploymentResult({ state: "DETERIORATING" }),
        evaluation_period: "2026-07-01",
      }),
    });
    renderPage();

    const section = await findSection("Current state");
    within(section).getByText("Why Cooling?").click();
    expect(await within(section).findByText("Employment")).toBeInTheDocument();
    expect(within(section).getByText("Unemployment trend")).toBeInTheDocument();
    expect(within(section).getByText("Evaluation period")).toBeInTheDocument();
    // Both the dl AND the new composed sentence coexist.
    expect(within(section).getByText(/Together, MacroChipz classifies Jobs as/)).toBeInTheDocument();
  });

  it("no new CTA is introduced by the composition sentence", async () => {
    resolveAll({ monitor: buildLaborMonitor({ state: "STABLE" }) });
    renderPage();

    const section = await findSection("Current state");
    within(section).getByText("Why Stable?").click();
    await within(section).findByText(/Together, MacroChipz classifies Jobs as/);
    expect(within(section).queryByRole("link")).not.toBeInTheDocument();
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

  it("raw evidence observations render as jobs, labelled Jobs, with the BLS series id", async () => {
    // #56B: the API has always delivered employment evidence in JOBS
    // (the x1000 is applied once, in app.domain.labor, before evidence is
    // built) -- the old "Thousands of persons" label made a real
    // 159,075,000 read as 159 billion. The label now matches the value.
    resolveAll({
      monitor: buildLaborMonitor({
        employment: buildEmploymentResult({
          observations: [{ series_id: "CES0000000001", observation_date: "2009-08-01", value: 130472000 }],
        }),
      }),
    });
    renderPage();

    const section = await findSection("Employment");
    const disclosure = within(section).getByText("View evidence: Employment");
    disclosure.click();
    expect(await within(section).findByText("130,472,000")).toBeInTheDocument();
    expect(within(section).getByText(/Value \(Jobs\)/)).toBeInTheDocument();
    expect(within(section).queryByText(/Thousands of persons/)).not.toBeInTheDocument();
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
    expect(within(section).getByText(/MacroChipz combines this unemployment trend with the Employment section/)).toBeInTheDocument();
  });
});

describe("What Changed", () => {
  it("shows the exact required copy when zero events are reported, never 'Jobs remained stable'", async () => {
    resolveAll({ whatChanged: buildLaborWhatChanged({ changes: [] }) });
    renderPage();

    const section = await findSection("What changed");
    expect(within(section).getByText("No canonical Jobs changes were reported for this comparison.")).toBeInTheDocument();
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
    expect(within(section).getByText(/Jobs state:/)).toBeInTheDocument();
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
    expect(within(section).getByText(/Jobs state:/)).toBeInTheDocument();
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
        releases: [buildReleaseOccurrenceItem({ name: "Employment Situation", provider_release_id: "empsit", scheduled_date: "2026-10-02" })],
      }),
    });
    renderPage();

    expect(await screen.findByText("Next scheduled")).toBeInTheDocument();
    expect(screen.getAllByText("Employment Situation").length).toBeGreaterThanOrEqual(1);
  });

  it("Increment #22B: never renders ReleaseRow's per-row 'View Labor →' CTA here -- it would be circular, already on /labor", async () => {
    resolveAll({
      upcoming: buildReleaseListResponse({
        releases: [buildReleaseOccurrenceItem({ name: "Employment Situation", provider_release_id: "empsit", scheduled_date: "2026-10-02" })],
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

    expect(await screen.findByText("Jobs data could not be loaded.")).toBeInTheDocument();
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
      buildReleaseListResponse({ releases: [buildReleaseOccurrenceItem({ name: "Employment Situation", provider_release_id: "empsit" })] }),
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

    expect(await screen.findByText("Jobs data could not be loaded.")).toBeInTheDocument();
    expect(await screen.findByText("What changed could not be loaded.")).toBeInTheDocument();
    expect(await screen.findByText("Release-processing status is temporarily unavailable.")).toBeInTheDocument();
    expect(await screen.findByText("Upcoming releases could not be loaded.")).toBeInTheDocument();
    expect(await screen.findByText("Recent releases could not be loaded.")).toBeInTheDocument();
    // #51B: the h1 is the two-survey distinction; the world's name
    // survives as the kicker above it.
    expect(screen.getByRole("heading", { level: 1, name: "Two surveys. Two answers." })).toBeInTheDocument();
  });
});

describe("accessibility basics", () => {
  it("uses a single h1 and semantic h2 section headings for the page's structure", async () => {
    resolveAll();
    renderPage();

    await screen.findByRole("heading", { name: "Two surveys, side by side" });
    expect(screen.getByRole("heading", { level: 1, name: "Two surveys. Two answers." })).toBeInTheDocument();
    for (const name of ["Two surveys, side by side", "What MacroChipz concludes", "Current state", "Employment", "Unemployment", "What changed", "Latest data detected", "Evidence & methodology"]) {
      expect(screen.getByRole("heading", { level: 2, name })).toBeInTheDocument();
    }
  });
});
