/**
 * Integration-level tests for the real Inflation Monitor product page.
 * Both API calls are mocked at the module boundary (../api/inflation)
 * with deterministic fixtures (../test/fixtures/inflation) -- no live
 * backend is required, and every scenario below controls exactly what
 * the two endpoints return.
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../api/errors";
import { getInflationMonitor, getInflationWhatChanged } from "../api/inflation";
import {
  buildChangeEvent,
  buildConfirmation,
  buildConfirmationSectionChanges,
  buildMomentum,
  buildMomentumSectionChanges,
  buildMonitor,
  buildTarget,
  buildWhatChanged,
} from "../test/fixtures/inflation";
import { InflationPage } from "./Inflation";

vi.mock("../api/inflation", () => ({
  getInflationMonitor: vi.fn(),
  getInflationWhatChanged: vi.fn(),
}));

const mockedGetMonitor = vi.mocked(getInflationMonitor);
const mockedGetWhatChanged = vi.mocked(getInflationWhatChanged);

beforeEach(() => {
  mockedGetMonitor.mockReset();
  mockedGetWhatChanged.mockReset();
});

function renderPage() {
  return render(<InflationPage />);
}

/** Scopes queries to the "What changed" section, since some formatted values (e.g. a metric reading) can coincidentally also appear in the monitor-driven sections above it. */
async function findWhatChangedSection(): Promise<HTMLElement> {
  const heading = await screen.findByRole("heading", { name: "What changed" });
  return heading.closest("section") as HTMLElement;
}

/** Resolve both endpoints with defaults, letting the caller override either. */
function resolveBoth(overrides: { monitor?: ReturnType<typeof buildMonitor>; whatChanged?: ReturnType<typeof buildWhatChanged> } = {}) {
  mockedGetMonitor.mockResolvedValue(overrides.monitor ?? buildMonitor());
  mockedGetWhatChanged.mockResolvedValue(overrides.whatChanged ?? buildWhatChanged());
}

describe("loading", () => {
  it("shows a stable loading state for both sections and no fabricated inflation values before data arrives", () => {
    mockedGetMonitor.mockReturnValue(new Promise(() => {}));
    mockedGetWhatChanged.mockReturnValue(new Promise(() => {}));

    renderPage();

    expect(screen.getAllByRole("status").length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
  });
});

describe("primary underlying momentum state", () => {
  it.each(["COOLING", "STABLE", "HEATING", "MIXED", "INSUFFICIENT_DATA"] as const)(
    "renders the canonical %s state under 'Underlying momentum', never remapped to good/bad language",
    async (state) => {
      resolveBoth({ monitor: buildMonitor({ underlying_momentum: buildMomentum({ state }) }) });
      renderPage();

      const heading = await screen.findByRole("heading", { name: "Underlying momentum" });
      const section = heading.closest("section") as HTMLElement;
      const expectedLabel = state === "INSUFFICIENT_DATA" ? "Insufficient data" : state[0] + state.slice(1).toLowerCase();
      expect(within(section).getByText(expectedLabel)).toBeInTheDocument();
    },
  );
});

describe("Core PCE momentum metrics", () => {
  it("renders 3M/6M/12M annualized values, formatted for presentation only", async () => {
    resolveBoth({
      monitor: buildMonitor({
        underlying_momentum: buildMomentum({ r_3m_annualized: 2.345, r_6m_annualized: 2.456, r_12m: 2.643912 }),
      }),
    });
    renderPage();

    const heading = await screen.findByRole("heading", { name: "Core PCE momentum" });
    const section = heading.closest("section") as HTMLElement;
    expect(within(section).getByText("2.35%")).toBeInTheDocument();
    expect(within(section).getByText("2.46%")).toBeInTheDocument();
    expect(within(section).getByText("2.64%")).toBeInTheDocument();
  });

  it("shows 1M annualized as secondary context when present", async () => {
    resolveBoth({ monitor: buildMonitor({ underlying_momentum: buildMomentum({ r_1m_annualized: 1.9 }) }) });
    renderPage();

    expect(await screen.findByText(/1M annualized \(context only\): 1\.90%/)).toBeInTheDocument();
  });

  it("omits the 1M context line when 1M is unavailable, rather than showing a fabricated value", async () => {
    resolveBoth({ monitor: buildMonitor({ underlying_momentum: buildMomentum({ r_1m_annualized: null }) }) });
    renderPage();

    await screen.findByRole("heading", { name: "Core PCE momentum" });
    expect(screen.queryByText(/1M annualized/)).not.toBeInTheDocument();
  });
});

describe("target / level", () => {
  it("shows headline PCE, the Fed objective, and the signed gap using backend-provided values only", async () => {
    resolveBoth({
      monitor: buildMonitor({ target: buildTarget({ headline_pce_yoy: 2.7, fed_objective_percent: 2.0, target_gap_pp: 0.70123 }) }),
    });
    renderPage();

    const heading = await screen.findByRole("heading", { name: "Target / level" });
    const section = heading.closest("section") as HTMLElement;
    // getAllByText, not getByText: the same formatted value can legitimately
    // also appear inside this section's own evidence disclosure.
    expect(within(section).getAllByText("2.70%").length).toBeGreaterThan(0);
    expect(within(section).getAllByText("2.00%").length).toBeGreaterThan(0);
    expect(within(section).getAllByText("+0.70 pp").length).toBeGreaterThan(0);
  });

  it("renders an honest unavailable message, with no numbers, when target.available is false", async () => {
    resolveBoth({ monitor: buildMonitor({ target: buildTarget({ available: false }) }) });
    renderPage();

    expect(await screen.findByText("Target data unavailable.")).toBeInTheDocument();
  });
});

describe("confirmation", () => {
  it.each(["CONFIRMS", "DIVERGES", "INCONCLUSIVE", "UNAVAILABLE"] as const)(
    "renders the canonical %s relationship, never as an equal vote alongside Core PCE",
    async (relationship) => {
      resolveBoth({ monitor: buildMonitor({ confirmation: buildConfirmation({ relationship }) }) });
      renderPage();

      const heading = await screen.findByRole("heading", { level: 2, name: "Confirmation" });
      const section = heading.closest("section") as HTMLElement;
      const expectedLabel = relationship[0] + relationship.slice(1).toLowerCase();
      expect(within(section).getByText(expectedLabel)).toBeInTheDocument();
    },
  );

  it("keeps the primary Core PCE state visible and unchanged when confirmation is UNAVAILABLE", async () => {
    resolveBoth({
      monitor: buildMonitor({
        underlying_momentum: buildMomentum({ state: "COOLING" }),
        confirmation: buildConfirmation({ relationship: "UNAVAILABLE" }),
      }),
    });
    renderPage();

    const heroHeading = await screen.findByRole("heading", { name: "Underlying momentum" });
    expect(within(heroHeading.closest("section") as HTMLElement).getByText("Cooling")).toBeInTheDocument();
  });
});

describe("headline context", () => {
  it("shows headline PCE and headline CPI independently, each with its own period", async () => {
    resolveBoth({
      monitor: buildMonitor({
        headline_context: {
          headline_pce: buildMomentum({ series_id: "PCEPI", calculation_period: "2026-07-01", r_12m: 2.7 }),
          headline_cpi: buildMomentum({ series_id: "CPIAUCSL", calculation_period: "2026-08-01", r_12m: 3.1 }),
        },
      }),
    });
    renderPage();

    const heading = await screen.findByRole("heading", { name: "Headline context" });
    const section = heading.closest("section") as HTMLElement;
    expect(within(section).getByText(/Headline PCE \(PCEPI\)/)).toBeInTheDocument();
    expect(within(section).getByText(/Headline CPI \(CPIAUCSL\)/)).toBeInTheDocument();
    // getAllByText, not getByText: the same period can legitimately also
    // appear inside each card's own evidence disclosure.
    expect(within(section).getAllByText("July 2026").length).toBeGreaterThan(0);
    expect(within(section).getAllByText("August 2026").length).toBeGreaterThan(0);
  });
});

describe("what changed", () => {
  it("renders a METRIC_CHANGED event as an itemized delta using the backend's own delta value", async () => {
    resolveBoth({
      whatChanged: buildWhatChanged({
        primary_momentum_changes: buildMomentumSectionChanges({
          changes: [buildChangeEvent({ field: "r_3m_annualized", previous_value: 2.1, current_value: 2.3, delta: 0.2 })],
        }),
      }),
    });
    renderPage();

    const section = await findWhatChangedSection();
    // The presentation-only #16B.1 polish pass combined the previous/arrow/
    // current values into one grid cell (for column alignment) rather than
    // three separately-queryable text nodes -- match on that cell's own
    // combined, whitespace-normalized text instead.
    expect(
      within(section).getByText(
        (_, element) => element?.tagName === "SPAN" && (element.textContent ?? "").replace(/\s+/g, "").includes("2.10%→2.30%"),
      ),
    ).toBeInTheDocument();
    expect(within(section).getByText("+0.20 pp")).toBeInTheDocument();
  });

  it("explicitly says the state remains unchanged when metrics moved but the state didn't -- never summarized as 'No change'", async () => {
    resolveBoth({
      whatChanged: buildWhatChanged({
        primary_momentum_changes: buildMomentumSectionChanges({
          changes: [buildChangeEvent({ field: "r_1m_annualized", previous_value: 2.0, current_value: 2.1, delta: 0.1 })],
          current_evidence: buildMomentum({ state: "STABLE" }),
        }),
      }),
    });
    renderPage();

    expect(await screen.findByText("State remains Stable.")).toBeInTheDocument();
    expect(screen.queryByText(/No change\b/)).not.toBeInTheDocument();
  });

  it("renders a STATE_CHANGED event as the section's headline transition", async () => {
    resolveBoth({
      whatChanged: buildWhatChanged({
        primary_momentum_changes: buildMomentumSectionChanges({
          changes: [
            buildChangeEvent({ event_type: "STATE_CHANGED", field: "state", previous_value: "STABLE", current_value: "COOLING", delta: null }),
          ],
        }),
      }),
    });
    renderPage();

    expect(await screen.findByText("Core PCE state: Stable → Cooling")).toBeInTheDocument();
  });

  it("renders an AVAILABILITY_LOST state event as a transition into unavailability", async () => {
    resolveBoth({
      whatChanged: buildWhatChanged({
        primary_momentum_changes: buildMomentumSectionChanges({
          changes: [
            buildChangeEvent({
              event_type: "AVAILABILITY_LOST",
              field: "state",
              previous_value: "STABLE",
              current_value: "INSUFFICIENT_DATA",
              delta: null,
            }),
          ],
        }),
      }),
    });
    renderPage();

    expect(await screen.findByText("Core PCE state: Stable → Insufficient data")).toBeInTheDocument();
  });

  it("renders an AVAILABILITY_RESTORED state event as a transition out of unavailability", async () => {
    resolveBoth({
      whatChanged: buildWhatChanged({
        primary_momentum_changes: buildMomentumSectionChanges({
          changes: [
            buildChangeEvent({
              event_type: "AVAILABILITY_RESTORED",
              field: "state",
              previous_value: "INSUFFICIENT_DATA",
              current_value: "STABLE",
              delta: null,
            }),
          ],
        }),
      }),
    });
    renderPage();

    expect(await screen.findByText("Core PCE state: Insufficient data → Stable")).toBeInTheDocument();
  });

  it("renders a CONFIRMATION_CHANGED event as the confirmation section's headline", async () => {
    resolveBoth({
      whatChanged: buildWhatChanged({
        confirmation_changes: buildConfirmationSectionChanges({
          relationship_changed: true,
          previous_relationship: "CONFIRMS",
          current_relationship: "DIVERGES",
          changes: [
            buildChangeEvent({
              component: "CONFIRMATION",
              event_type: "CONFIRMATION_CHANGED",
              field: "relationship",
              previous_value: "CONFIRMS",
              current_value: "DIVERGES",
              delta: null,
            }),
          ],
        }),
      }),
    });
    renderPage();

    expect(await screen.findByText("Confirmation: Confirms → Diverges")).toBeInTheDocument();
  });

  it("says both periods were insufficient rather than misleadingly claiming a state 'remains'", async () => {
    resolveBoth({
      whatChanged: buildWhatChanged({
        primary_momentum_changes: buildMomentumSectionChanges({
          changes: [buildChangeEvent({ field: "r_1m_annualized", previous_value: null, current_value: null, delta: null })],
          previous_evidence: buildMomentum({ state: "INSUFFICIENT_DATA" }),
          current_evidence: buildMomentum({ state: "INSUFFICIENT_DATA" }),
        }),
      }),
    });
    renderPage();

    expect(await screen.findByText("Insufficient data in both periods.")).toBeInTheDocument();
    expect(screen.queryByText(/State remains Insufficient data/)).not.toBeInTheDocument();
  });

  it("shows 'No canonical changes detected.' when comparison_available is true and there are zero change events", async () => {
    resolveBoth({
      whatChanged: buildWhatChanged({ primary_momentum_changes: buildMomentumSectionChanges({ changes: [] }) }),
    });
    renderPage();

    await screen.findByRole("heading", { name: "What changed" });
    expect(screen.getAllByText("No canonical changes detected.").length).toBeGreaterThan(0);
  });

  it("distinguishes comparison_available=false from a true zero-change result, with no alert role", async () => {
    resolveBoth({
      whatChanged: buildWhatChanged({
        primary_momentum_changes: buildMomentumSectionChanges({ comparison_available: false, previous_period: null, current_period: null, previous_evidence: null, current_evidence: null }),
      }),
    });
    renderPage();

    expect(await screen.findByText("Previous-period comparison unavailable.")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("renders independent period pairs per section rather than one global page-wide period", async () => {
    resolveBoth({
      whatChanged: buildWhatChanged({
        primary_momentum_changes: buildMomentumSectionChanges({
          previous_period: "2026-06-01",
          current_period: "2026-07-01",
          changes: [buildChangeEvent({ field: "r_3m_annualized" })],
        }),
        headline_cpi_changes: buildMomentumSectionChanges({
          previous_period: "2026-07-01",
          current_period: "2026-08-01",
          changes: [buildChangeEvent({ field: "r_3m_annualized" })],
        }),
      }),
    });
    renderPage();

    const section = await findWhatChangedSection();
    const corePceHeading = within(section).getByRole("heading", { level: 3, name: "Core PCE" });
    expect(within(corePceHeading.parentElement as HTMLElement).getByText("June 2026 → July 2026")).toBeInTheDocument();

    const headlineCpiHeading = within(section).getByRole("heading", { level: 3, name: "Headline CPI" });
    expect(within(headlineCpiHeading.parentElement as HTMLElement).getByText("July 2026 → August 2026")).toBeInTheDocument();
  });
});

describe("evidence disclosure", () => {
  it("is closed by default and keyboard/click-toggleable to reveal the underlying evidence", async () => {
    resolveBoth();
    renderPage();

    const summary = await screen.findByText("View evidence: Headline PCE YoY");
    const details = summary.closest("details") as HTMLDetailsElement;
    expect(details.open).toBe(false);

    const user = userEvent.setup();
    await user.click(summary);

    expect(details.open).toBe(true);
    expect(within(details).getByText("PCEPI")).toBeInTheDocument();
  });
});

describe("methodology and data-basis disclosure", () => {
  it("shows the 'Latest revised data' disclosure with the required non-vintage-accuracy language", async () => {
    // This disclosure is static header content, independent of either
    // endpoint -- both are still stubbed here only because the hook
    // requires a resolvable fetcher to avoid an unhandled rejection.
    resolveBoth();
    renderPage();
    const summary = await screen.findByText("Latest revised data");
    expect(
      screen.getByText(
        "Historical calculations use the latest revised observations available to Economic Intelligence. They may differ from values originally reported at the time.",
      ),
    ).toBeInTheDocument();
    expect(summary.closest("details")).not.toBeNull();
  });

  it("shows both methodology IDs unobtrusively within the evidence disclosure, not on the default screen", async () => {
    resolveBoth();
    renderPage();

    const heading = await screen.findByRole("heading", { name: "Evidence & methodology" });
    const section = heading.closest("section") as HTMLElement;
    expect(within(section).getByText("inflation_v1.0")).toBeInTheDocument();
    expect(within(section).getByText("inflation_what_changed_v1.0")).toBeInTheDocument();
  });
});

describe("infrastructure failure vs. economic unavailability", () => {
  it("shows a truthful error, with a retry action, when the monitor endpoint fails -- while What Changed still renders (partial success)", async () => {
    mockedGetMonitor.mockRejectedValue(new ApiError("http", "Request failed with status 503.", 503));
    mockedGetWhatChanged.mockResolvedValue(buildWhatChanged());
    renderPage();

    expect(await screen.findByText("Inflation data could not be loaded.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "What changed" })).toBeInTheDocument();
    // Never leaks the underlying status code or URL to the reader.
    expect(screen.queryByText(/503/)).not.toBeInTheDocument();
  });

  it("shows a truthful error for What Changed alone while the monitor sections render fully", async () => {
    mockedGetMonitor.mockResolvedValue(buildMonitor());
    mockedGetWhatChanged.mockRejectedValue(new ApiError("network", "Could not reach the server."));
    renderPage();

    expect(await screen.findByText("What changed could not be loaded.")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Underlying momentum" })).toBeInTheDocument();
  });

  it("shows both error surfaces, and renders nothing else, when both endpoints fail", async () => {
    mockedGetMonitor.mockRejectedValue(new ApiError("network", "Could not reach the server."));
    mockedGetWhatChanged.mockRejectedValue(new ApiError("network", "Could not reach the server."));
    renderPage();

    expect(await screen.findByText("Inflation data could not be loaded.")).toBeInTheDocument();
    expect(await screen.findByText("What changed could not be loaded.")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Underlying momentum" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "What changed" })).not.toBeInTheDocument();
  });

  it("retries the monitor request when Retry is clicked", async () => {
    mockedGetMonitor.mockRejectedValueOnce(new ApiError("http", "Request failed with status 500.", 500));
    mockedGetMonitor.mockResolvedValueOnce(buildMonitor());
    mockedGetWhatChanged.mockResolvedValue(buildWhatChanged());
    renderPage();

    const retryButton = await screen.findByRole("button", { name: "Retry" });
    const user = userEvent.setup();
    await user.click(retryButton);

    expect(await screen.findByRole("heading", { name: "Underlying momentum" })).toBeInTheDocument();
    expect(mockedGetMonitor).toHaveBeenCalledTimes(2);
  });

  it("never renders a canonical INSUFFICIENT_DATA / UNAVAILABLE economic result as an infrastructure error", async () => {
    resolveBoth({
      monitor: buildMonitor({
        underlying_momentum: buildMomentum({ state: "INSUFFICIENT_DATA" }),
        confirmation: buildConfirmation({ relationship: "UNAVAILABLE" }),
      }),
    });
    renderPage();

    expect(await screen.findByText("Insufficient data", { selector: "span" })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("accessibility basics", () => {
  it("uses a single h1 and semantic h2 section headings for the page's structure", async () => {
    resolveBoth();
    renderPage();

    await screen.findByRole("heading", { name: "What changed" });
    expect(screen.getByRole("heading", { level: 1, name: "Inflation" })).toBeInTheDocument();
    for (const name of ["Underlying momentum", "What changed", "Core PCE momentum", "Target / level", "Confirmation", "Headline context"]) {
      expect(screen.getByRole("heading", { level: 2, name })).toBeInTheDocument();
    }
  });
});

describe("explanations (Increment #17C)", () => {
  it("offers a Core PCE explanation next to the primary reading, and opening it never changes the canonical state shown", async () => {
    resolveBoth({ monitor: buildMonitor({ underlying_momentum: buildMomentum({ state: "MIXED" }) }) });
    renderPage();

    const heading = await screen.findByRole("heading", { name: "Underlying momentum" });
    const section = heading.closest("section") as HTMLElement;
    const user = userEvent.setup();
    await user.click(within(section).getByLabelText("What does Core PCE mean?"));

    expect(within(section).getByText(/primary signal for underlying inflation momentum/i)).toBeInTheDocument();
    // The canonical Badge state is unaffected by opening the explanation.
    expect(within(section).getByText("Mixed", { selector: "span" })).toBeInTheDocument();
  });

  it("offers explanations for 3M, 6M, and 12M annualized readings", async () => {
    resolveBoth();
    renderPage();

    const heading = await screen.findByRole("heading", { name: "Core PCE momentum" });
    const section = heading.closest("section") as HTMLElement;
    for (const label of ["What does 3-month annualized rate mean?", "What does 6-month annualized rate mean?", "What does 12-month (year-over-year) rate mean?"]) {
      expect(within(section).getByLabelText(label)).toBeInTheDocument();
    }
  });

  it("offers a Fed objective explanation in the target section", async () => {
    resolveBoth();
    renderPage();

    const heading = await screen.findByRole("heading", { name: "Target / level" });
    const section = heading.closest("section") as HTMLElement;
    const user = userEvent.setup();
    await user.click(within(section).getByLabelText("What does The Fed's 2% objective mean?"));

    expect(within(section).getByText(/2% annual growth in the headline pce price index/i)).toBeInTheDocument();
  });

  it("offers CPI and PCE concept explanations in headline context, distinguishing the two measures", async () => {
    resolveBoth();
    renderPage();

    const heading = await screen.findByRole("heading", { name: "Headline context" });
    const section = heading.closest("section") as HTMLElement;
    const user = userEvent.setup();

    await user.click(within(section).getByLabelText("What does Consumer Price Index (CPI) mean?"));
    expect(within(section).getByText(/bureau of labor statistics/i)).toBeInTheDocument();

    await user.click(within(section).getByLabelText("What does Personal Consumption Expenditures (PCE) price index mean?"));
    expect(within(section).getByText(/bureau of economic analysis/i)).toBeInTheDocument();
  });

  it("'Why is momentum {state}?' shows the exact backend evidence for this response, not a recalculated value", async () => {
    resolveBoth({
      monitor: buildMonitor({
        underlying_momentum: buildMomentum({ state: "HEATING", r_3m_annualized: 3.14, r_6m_annualized: 3.15, r_12m: 2.5 }),
      }),
    });
    renderPage();

    const heading = await screen.findByRole("heading", { name: "Underlying momentum" });
    const section = heading.closest("section") as HTMLElement;
    const user = userEvent.setup();
    const trigger = within(section).getByText("Why Heating?");
    await user.click(trigger);

    // Scoped to the opened evidence panel itself -- the compact 3M/6M/12M
    // strip above it in this same section legitimately shows the same
    // values a second time, so this checks the panel, not the section.
    const panel = trigger.closest("details") as HTMLDetailsElement;
    expect(within(panel).getByText("3.14%")).toBeInTheDocument();
    expect(within(panel).getByText("3.15%")).toBeInTheDocument();
  });

  it("THE CONTRADICTORY-EVIDENCE TEST (page level): the backend says MIXED, so the page says MIXED, even with numbers a human might read as STABLE", async () => {
    resolveBoth({
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

    const heading = await screen.findByRole("heading", { name: "Underlying momentum" });
    const section = heading.closest("section") as HTMLElement;
    expect(within(section).getByText("Mixed", { selector: "span" })).toBeInTheDocument();
    expect(within(section).queryByText("Stable", { selector: "span" })).not.toBeInTheDocument();
    expect(within(section).getByText("Why Mixed?")).toBeInTheDocument();
  });

  it("shows a curated explanation for Core CPI confirmation, alongside (never instead of) the canonical relationship Badge", async () => {
    resolveBoth({ monitor: buildMonitor({ confirmation: buildConfirmation({ relationship: "DIVERGES" }) }) });
    renderPage();

    const heading = await screen.findByRole("heading", { level: 2, name: "Confirmation" });
    const section = heading.closest("section") as HTMLElement;
    expect(within(section).getByText("Diverges", { selector: "span" })).toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(within(section).getByLabelText("What does Confirmation mean?"));
    expect(within(section).getByText(/never to override it/i)).toBeInTheDocument();
  });
});
