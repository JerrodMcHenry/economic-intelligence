/**
 * Integration-level tests for the Rates Intelligence page
 * (Increment #30). The network is mocked at the module boundary
 * (../api/rates) with fixtures mirroring the live response shape, the
 * same pattern pages/Labor.test.tsx already uses.
 *
 * What these tests actually protect: that every displayed number is the
 * backend's number, that session windows keep their session semantics,
 * that a missing value never becomes a zero, and that a derived value is
 * never presented as something Treasury published.
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { ApiError } from "../api/errors";
import { getRatesMonitor } from "../api/rates";
import {
  buildAllChanges,
  buildCurveSpread,
  buildEmptyRatesMonitor,
  buildHistoricalContext,
  buildInflationCompensation,
  buildRateLevel,
  buildRatesMonitor,
} from "../test/fixtures/rates";
import { RatesPage } from "./Rates";

vi.mock("../api/rates", () => ({ getRatesMonitor: vi.fn() }));

const mockedGetRatesMonitor = vi.mocked(getRatesMonitor);

beforeEach(() => {
  mockedGetRatesMonitor.mockReset();
});

function renderPage() {
  return render(
    <MemoryRouter>
      <RatesPage />
    </MemoryRouter>,
  );
}

describe("RatesPage header and freshness", () => {
  it("identifies itself and describes the domain", async () => {
    mockedGetRatesMonitor.mockResolvedValue(buildRatesMonitor());
    renderPage();

    // #49B: the h1 is a definition rather than the world's name, and
    // the name survives as the kicker above it. The standfirst is now
    // verbatim reviewed copy from `explain.what-is-a-treasury-yield` --
    // a Treasury yield is the return an investor earns on a security
    // trading in the market, NOT the government's exact cost of any
    // new borrowing.
    expect(
      await screen.findByRole("heading", { level: 1, name: "What investors earn on U.S. government debt." }),
    ).toBeInTheDocument();
    expect(screen.getByText("Rates", { selector: "p" })).toBeInTheDocument();
    expect(
      screen.getByText(/The yield is the annual return an investor earns by holding one/),
    ).toBeInTheDocument();
  });

  it("states the latest observation date rather than implying a live feed", async () => {
    mockedGetRatesMonitor.mockResolvedValue(buildRatesMonitor());
    renderPage();

    // #49B: "Latest available" became "Latest published", beside a
    // human-readable source. The three machine identifiers that used to
    // sit here are still published verbatim in the methodology
    // disclosure.
    expect(await screen.findByText(/Latest published: Sep 18, 2026/)).toBeInTheDocument();
    expect(screen.getByText(/Published by the U.S. Department of the Treasury/)).toBeInTheDocument();
    // The page must not claim a cadence the source does not have. The
    // explanation copy may legitimately say what this is NOT ("not a
    // streaming market feed"), so these assert positive claims only.
    const page = document.body.textContent ?? "";
    expect(page).not.toMatch(/\bLive\b/);
    expect(page).not.toMatch(/\breal-time\b/i);
    expect(page).not.toContain("Current market rates");
  });
});

describe("RatesPage nominal yields", () => {
  /*
   * #49B: the four maturities are one selectable curve plus a panel for
   * the selected one, instead of four simultaneous cards. Every value
   * is still published — the chart's accessible table carries all four
   * at once, and the panel carries the selected one in full. The
   * assertions below check the same facts in their new homes.
   */
  it("publishes every canonical maturity with the backend's own value", async () => {
    mockedGetRatesMonitor.mockResolvedValue(buildRatesMonitor());
    renderPage();

    const curve = await screen.findByRole("region", { name: "Treasury curve" });
    const table = within(curve).getByRole("table", { name: "Nominal Treasury par yields by maturity" });
    expect(within(table).getByRole("rowheader", { name: "2Y" })).toBeInTheDocument();
    expect(within(table).getByRole("rowheader", { name: "30Y" })).toBeInTheDocument();
    expect(within(table).getByText("4.76%")).toBeInTheDocument();
    expect(within(table).getByText("5.34%")).toBeInTheDocument();
  });

  it("offers every maturity as a control, and selects the 10-year by default", async () => {
    mockedGetRatesMonitor.mockResolvedValue(buildRatesMonitor());
    renderPage();

    const curve = await screen.findByRole("region", { name: "Treasury curve" });
    const controls = within(curve).getAllByRole("button");
    expect(controls).toHaveLength(4);
    const pressed = controls.filter((c) => c.getAttribute("aria-pressed") === "true");
    expect(pressed).toHaveLength(1);
    expect(pressed[0]).toHaveAccessibleName(/10Y/);

    const panel = await screen.findByRole("region", { name: "The maturity you selected" });
    expect(within(panel).getByText("5.01%")).toBeInTheDocument();
  });

  it("selecting a maturity shows that maturity, and only one is ever selected", async () => {
    const user = userEvent.setup();
    mockedGetRatesMonitor.mockResolvedValue(buildRatesMonitor());
    renderPage();

    const curve = await screen.findByRole("region", { name: "Treasury curve" });
    const twoYear = within(curve).getByRole("button", { name: /^2Y/ });
    await user.click(twoYear);

    const panel = screen.getByRole("region", { name: "The maturity you selected" });
    expect(within(panel).getByText("4.76%")).toBeInTheDocument();
    expect(twoYear).toHaveAttribute("aria-pressed", "true");
    expect(within(curve).getAllByRole("button").filter((c) => c.getAttribute("aria-pressed") === "true")).toHaveLength(
      1,
    );
    // Selection is not navigation: focus stays where the reader put it.
    expect(twoYear).toHaveFocus();
  });

  it("keeps an unavailable maturity as a labelled, disabled control rather than hiding it", async () => {
    mockedGetRatesMonitor.mockResolvedValue(
      buildRatesMonitor({
        nominal_curve: [
          buildRateLevel({ series_id: "UST_NOMINAL_2Y", latest_value: 4.76 }),
          buildRateLevel({ series_id: "UST_NOMINAL_30Y", available: false, latest_value: null, provenance: null }),
        ],
      }),
    );
    renderPage();

    const curve = await screen.findByRole("region", { name: "Treasury curve" });
    const missing = within(curve).getByRole("button", { name: /30Y, not yet ingested/ });
    expect(missing).toBeDisabled();
    // And no zero is invented for it anywhere.
    expect(document.body.textContent).not.toContain("0.00%");
  });

  it("labels change windows in sessions, never in calendar periods", async () => {
    mockedGetRatesMonitor.mockResolvedValue(buildRatesMonitor());
    renderPage();

    const section = await screen.findByRole("region", { name: "The maturity you selected" });
    expect(within(section).getAllByText("1 session").length).toBeGreaterThan(0);
    expect(within(section).getAllByText("21 sessions").length).toBeGreaterThan(0);
    expect(within(section).getAllByText("63 sessions").length).toBeGreaterThan(0);

    // A window is never RELABELLED as a calendar period. (The session
    // explanation may still discuss months in prose -- that copy exists
    // precisely to say 21 sessions is not exactly one month.)
    const page = document.body.textContent ?? "";
    for (const forbidden of ["1 week", "1 month", "3 months"]) {
      expect(page).not.toContain(forbidden);
    }
  });

  it("renders basis-point changes with direction, signed as the backend supplied them", async () => {
    mockedGetRatesMonitor.mockResolvedValue(buildRatesMonitor());
    renderPage();

    // The selected maturity carries its own four windows. The fixture
    // gives every maturity the same change, so this asserts the sign
    // and unit survive the backend's value unmodified.
    const section = await screen.findByRole("region", { name: "The maturity you selected" });
    expect(within(section).getAllByText("+7 bp").length).toBeGreaterThan(0);
  });

  it("conveys direction with text, not by color alone", async () => {
    mockedGetRatesMonitor.mockResolvedValue(
      buildRatesMonitor({
        nominal_curve: [buildRateLevel({ changes: buildAllChanges({ change_basis_points: -12.0 }) })],
      }),
    );
    renderPage();

    const section = await screen.findByRole("region", { name: "The maturity you selected" });
    expect(within(section).getAllByText("lower").length).toBeGreaterThan(0);
  });
});

describe("RatesPage curve and spreads", () => {
  it("draws the curve and publishes the same values as an accessible table", async () => {
    mockedGetRatesMonitor.mockResolvedValue(buildRatesMonitor());
    renderPage();

    const section = await screen.findByRole("region", { name: "Treasury curve" });
    // Two renderings since #41 -- one viewBox per breakpoint, which is
    // how the chart scales uniformly instead of distorting (ADR-041).
    // Only one is ever displayed, so a screen reader still hears one
    // chart: `display: none` removes the other from the a11y tree.
    const charts = within(section).getAllByRole("img", {
      name: /Nominal Treasury yield curve as of Sep 18, 2026/,
    });
    expect(charts).toHaveLength(2);
    for (const chart of charts) {
      expect(chart).toHaveAttribute("preserveAspectRatio", "xMidYMid meet");
    }

    const table = within(section).getByRole("table", { name: "Nominal Treasury par yields by maturity" });
    expect(within(table).getByRole("rowheader", { name: "10Y" })).toBeInTheDocument();
    expect(within(table).getByText("5.01%")).toBeInTheDocument();
  });

  it("omits a maturity with no value from the curve instead of interpolating one", async () => {
    mockedGetRatesMonitor.mockResolvedValue(
      buildRatesMonitor({
        nominal_curve: [
          buildRateLevel({ series_id: "UST_NOMINAL_2Y", latest_value: 4.76 }),
          buildRateLevel({ series_id: "UST_NOMINAL_10Y", available: false, latest_value: null, provenance: null }),
        ],
      }),
    );
    renderPage();

    const section = await screen.findByRole("region", { name: "Treasury curve" });
    const table = within(section).getByRole("table", { name: "Nominal Treasury par yields by maturity" });
    expect(within(table).getByRole("rowheader", { name: "2Y" })).toBeInTheDocument();
    expect(within(table).queryByRole("rowheader", { name: "10Y" })).not.toBeInTheDocument();
  });

  it("shows both spreads from backend-supplied values", async () => {
    mockedGetRatesMonitor.mockResolvedValue(buildRatesMonitor());
    renderPage();

    // #49B: spreads sit in "Calculated from the curve" and lead with
    // the backend's own `title` -- "2s10s" is a trading desk's word.
    // The identifier is still printed, directly beneath.
    const section = await screen.findByRole("region", { name: "Calculated from the curve" });
    expect(within(section).getByRole("heading", { level: 3, name: "10-Year minus 2-Year" })).toBeInTheDocument();
    expect(within(section).getByText("2s10s")).toBeInTheDocument();
    expect(within(section).getByText("25 bp")).toBeInTheDocument();
    expect(within(section).getByText("58 bp")).toBeInTheDocument();
  });

  it("renders an inverted spread as a negative number with no regime label", async () => {
    mockedGetRatesMonitor.mockResolvedValue(
      buildRatesMonitor({ curve_spreads: [buildCurveSpread({ spread_basis_points: -42.0 })] }),
    );
    renderPage();

    const section = await screen.findByRole("region", { name: "Calculated from the curve" });
    expect(within(section).getByText("−42 bp")).toBeInTheDocument();
    const page = document.body.textContent ?? "";
    for (const forbidden of ["recession", "risk-off", "hawkish", "tightening", "easing"]) {
      expect(page.toLowerCase()).not.toContain(forbidden);
    }
  });
});

describe("RatesPage real yields and inflation compensation", () => {
  it("shows both real yields", async () => {
    mockedGetRatesMonitor.mockResolvedValue(buildRatesMonitor());
    renderPage();

    const section = await screen.findByRole("region", { name: "Real yields" });
    expect(within(section).getByText("2.55%")).toBeInTheDocument();
    expect(within(section).getByText("2.68%")).toBeInTheDocument();
  });

  it("shows compensation using the methodology's own terminology", async () => {
    mockedGetRatesMonitor.mockResolvedValue(buildRatesMonitor());
    renderPage();

    const section = await screen.findByRole("region", { name: "Calculated from the curve" });
    expect(within(section).getByText("2.31%")).toBeInTheDocument();
    expect(within(section).getByText("2.33%")).toBeInTheDocument();
    // Never renamed to the claim the methodology refuses.
    expect(document.body.textContent).not.toContain("Inflation Expectations");
  });

  it("shows the inputs behind a compensation value", async () => {
    mockedGetRatesMonitor.mockResolvedValue(buildRatesMonitor());
    renderPage();

    const section = await screen.findByRole("region", { name: "Calculated from the curve" });
    expect(within(section).getByText(/5\.01% nominal/)).toBeInTheDocument();
    expect(within(section).getByText(/2\.68% real/)).toBeInTheDocument();
  });
});

describe("RatesPage source vs derived distinction", () => {
  it("marks every derived value as calculated rather than published", async () => {
    mockedGetRatesMonitor.mockResolvedValue(buildRatesMonitor());
    renderPage();

    await screen.findByRole("region", { name: "Calculated from the curve" });
    // Two spreads + two compensation cards.
    expect(screen.getAllByText("Calculated by MacroChipz")).toHaveLength(4);
  });

  it("gives a sourced observation provider provenance", async () => {
    mockedGetRatesMonitor.mockResolvedValue(buildRatesMonitor());
    renderPage();

    const section = await screen.findByRole("region", { name: "The maturity you selected" });
    const disclosures = within(section).getAllByText("Source & provenance");
    await userEvent.setup().click(disclosures[0]!);

    expect(within(section).getAllByText("Published by the source").length).toBeGreaterThan(0);
    expect(within(section).getAllByText("TREASURY").length).toBeGreaterThan(0);
    expect(within(section).getAllByText("daily_treasury_yield_curve").length).toBeGreaterThan(0);
  });

  it("gives a derived value methodology provenance, never a provider", async () => {
    mockedGetRatesMonitor.mockResolvedValue(buildRatesMonitor());
    renderPage();

    const section = await screen.findByRole("region", { name: "Calculated from the curve" });
    await userEvent.setup().click(within(section).getAllByText("How this is calculated")[0]!);

    expect(within(section).getAllByText("Calculated by MacroChipz, not published by the source").length).toBeGreaterThan(0);
    expect(within(section).getAllByText("rates_v1.0").length).toBeGreaterThan(0);
    expect(within(section).getByText("UST_NOMINAL_10Y, UST_NOMINAL_2Y")).toBeInTheDocument();
  });
});

describe("RatesPage historical context", () => {
  it("reports both ranks separately and never merges them", async () => {
    mockedGetRatesMonitor.mockResolvedValue(buildRatesMonitor());
    renderPage();

    // #49B: the selected maturity shows its own historical context for
    // the first time. `RateLevelCard` is rendered with
    // `showContext={false}` on this page, so this data has been fetched
    // and discarded since #30.
    const panel = await screen.findByRole("region", { name: "The maturity you selected" });
    expect(within(panel).getAllByText(/57th/).length).toBeGreaterThan(0);
    expect(within(panel).getAllByText(/40th/).length).toBeGreaterThan(0);
    expect(within(panel).getAllByText(/113 prior 5 sessions changes/).length).toBeGreaterThan(0);

    const derived = screen.getByRole("region", { name: "Calculated from the curve" });
    expect(within(derived).getAllByText(/57th/).length).toBeGreaterThan(0);
  });

  it("says context is unavailable rather than inventing a rank", async () => {
    mockedGetRatesMonitor.mockResolvedValue(
      buildRatesMonitor({
        curve_spreads: [
          buildCurveSpread({
            historical_context: buildHistoricalContext({
              available: false,
              observation_count: 0,
              percentile_rank: null,
              magnitude_percentile_rank: null,
            }),
          }),
        ],
      }),
    );
    renderPage();

    const section = await screen.findByRole("region", { name: "Calculated from the curve" });
    expect(within(section).getByText(/needs more history than is currently stored/)).toBeInTheDocument();
  });
});

describe("RatesPage unavailable data never becomes zero", () => {
  it("renders an unavailable derived metric with its reason", async () => {
    mockedGetRatesMonitor.mockResolvedValue(
      buildRatesMonitor({
        inflation_compensation: [
          buildInflationCompensation({
            available: false,
            compensation_percent: null,
            nominal_value: null,
            real_value: null,
            unavailable_reason: "NO_EXACTLY_SHARED_OBSERVATION_DATE",
            provenance: null,
          }),
        ],
      }),
    );
    renderPage();

    const section = await screen.findByRole("region", { name: "Calculated from the curve" });
    expect(within(section).getByText("Not available")).toBeInTheDocument();
    expect(within(section).getByText(/no observation on the same date, so this value is not calculated/)).toBeInTheDocument();
    expect(within(section).queryByText("0.00%")).not.toBeInTheDocument();
    expect(within(section).queryByText("0 bp")).not.toBeInTheDocument();
  });

  it("renders an unavailable change window as insufficient history, not as no change", async () => {
    mockedGetRatesMonitor.mockResolvedValue(
      buildRatesMonitor({
        nominal_curve: [
          buildRateLevel({
            changes: [
              ...buildAllChanges().slice(0, 2),
              ...buildAllChanges({ available: false, change_basis_points: null, from_value: null, to_value: null }).slice(2),
            ],
          }),
        ],
      }),
    );
    renderPage();

    const section = await screen.findByRole("region", { name: "The maturity you selected" });
    expect(within(section).getAllByText("Not enough history").length).toBeGreaterThan(0);
  });

  it("handles a partially-ingested environment without failing the page", async () => {
    mockedGetRatesMonitor.mockResolvedValue(
      buildRatesMonitor({
        real_curve: [
          buildRateLevel({
            series_id: "UST_REAL_5Y",
            title: "5-Year Treasury Par Real Yield (TIPS)",
            available: false,
            latest_value: null,
            latest_date: null,
            provenance: null,
          }),
        ],
      }),
    );
    renderPage();

    const realSection = await screen.findByRole("region", { name: "Real yields" });
    expect(within(realSection).getByText("Not available")).toBeInTheDocument();
    // The rest of the page still renders.
    expect(screen.getByRole("region", { name: "Treasury curve" })).toBeInTheDocument();
  });
});

describe("RatesPage what changed", () => {
  /*
   * #49B REMOVED THE "What changed" TABLE, AND NOT THE FACT.
   *
   * It printed all ten metrics' 5-session change in one place --
   * duplicating a change every card already carried, with the same
   * "(Sep 11, 2026 - Sep 18, 2026)" on every row. #49A measured the
   * page at 6,777px on a phone and this table as 559 of them.
   *
   * What it guarded is that EVERY metric publishes its change over a
   * window labelled in sessions. That is asserted here against the
   * cards and the panel, which is where those changes now live -- and
   * where each metric carries all four windows rather than one.
   */
  it("publishes every metric's change over windows labelled in sessions", async () => {
    mockedGetRatesMonitor.mockResolvedValue(buildRatesMonitor());
    renderPage();

    const panel = await screen.findByRole("region", { name: "The maturity you selected" });
    const real = screen.getByRole("region", { name: "Real yields" });
    const derived = screen.getByRole("region", { name: "Calculated from the curve" });

    for (const section of [panel, real, derived]) {
      expect(within(section).getAllByText("5 sessions").length).toBeGreaterThan(0);
      expect(within(section).getAllByText("63 sessions").length).toBeGreaterThan(0);
    }

    // Still never relabelled as a calendar period.
    const page = document.body.textContent ?? "";
    for (const forbidden of ["1 week", "1 month", "3 months"]) {
      expect(page).not.toContain(forbidden);
    }
  });
});

describe("RatesPage methodology discovery", () => {
  it("exposes rates_v1.0 and its key rules behind a disclosure", async () => {
    mockedGetRatesMonitor.mockResolvedValue(buildRatesMonitor());
    renderPage();

    const section = await screen.findByRole("region", { name: "Evidence & methodology" });
    await userEvent.setup().click(within(section).getByText("Where these numbers come from"));

    expect(within(section).getByText(/Changes count published business sessions/)).toBeInTheDocument();
    expect(within(section).getByText(/never interpolated or carried/)).toBeInTheDocument();
    expect(within(section).getAllByText(/U.S. Department of the Treasury/).length).toBeGreaterThan(0);
  });
});

describe("RatesPage product states", () => {
  it("shows a loading state first", () => {
    mockedGetRatesMonitor.mockReturnValue(new Promise(() => {}));
    renderPage();

    expect(screen.getByRole("status", { name: "Loading rates intelligence" })).toBeInTheDocument();
  });

  it("shows an error state with a retry that refetches", async () => {
    mockedGetRatesMonitor.mockRejectedValue(new ApiError("network", "boom"));
    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent("Rates intelligence could not be loaded.");

    mockedGetRatesMonitor.mockResolvedValue(buildRatesMonitor());
    await userEvent.setup().click(screen.getByRole("button", { name: "Retry" }));

    expect(await screen.findByRole("region", { name: "Treasury curve" })).toBeInTheDocument();
  });

  it("shows an explicit empty state when nothing has been ingested", async () => {
    mockedGetRatesMonitor.mockResolvedValue(buildEmptyRatesMonitor());
    renderPage();

    expect(await screen.findByText("No rates data yet")).toBeInTheDocument();
    expect(screen.getByText(/Nothing here is estimated in the meantime/)).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Treasury curve" })).not.toBeInTheDocument();
  });
});

describe("RatesPage accessibility semantics", () => {
  it("uses one h1 and a named region per section", async () => {
    mockedGetRatesMonitor.mockResolvedValue(buildRatesMonitor());
    renderPage();

    await screen.findByRole("region", { name: "Treasury curve" });
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    // #49B section list: four nominal maturities became one curve plus
    // one panel, and the two derived sections merged into one.
    for (const name of [
      "Treasury curve",
      "The maturity you selected",
      "Real yields",
      "Calculated from the curve",
      "Where these numbers come up",
      "Evidence & methodology",
    ]) {
      expect(screen.getByRole("region", { name })).toBeInTheDocument();
    }
  });
});

describe("RatesPage emits valid HTML nesting", () => {
  /**
   * Regression for a pre-#33 defect found while reviewing the Analyst
   * UI: the page header wrapped `ExplanationTrigger` -- a native
   * `<details>/<summary>` disclosure -- in a `<p>`. A paragraph may
   * contain only phrasing content, so React logged four invalid-nesting
   * errors (`<details>`, `<summary>`, `<div>` and `<p>` inside `<p>`)
   * and warned of a hydration mismatch.
   *
   * These assert the rendered DOM rather than the source, so they fail
   * whichever component reintroduces the problem -- not only the one
   * that caused it the first time.
   */
  const FORBIDDEN_IN_PARAGRAPH = ["details", "summary", "div", "p", "ul", "ol", "section", "table"];

  async function renderLoadedPage() {
    mockedGetRatesMonitor.mockResolvedValue(buildRatesMonitor());
    const { container } = renderPage();
    await screen.findByRole("region", { name: "Treasury curve" });
    return container;
  }

  it("never nests flow content inside a paragraph", async () => {
    const container = await renderLoadedPage();

    const offenders: string[] = [];
    for (const paragraph of container.querySelectorAll("p")) {
      for (const tag of FORBIDDEN_IN_PARAGRAPH) {
        if (paragraph.querySelector(tag)) {
          offenders.push(`<p> contains <${tag}>: ${paragraph.textContent?.slice(0, 60)}`);
        }
      }
    }

    expect(offenders).toEqual([]);
  });

  it("renders the data-freshness note and its explanation as siblings, not nested in a paragraph", async () => {
    const container = await renderLoadedPage();

    const trigger = screen.getByLabelText("What does Observation date mean?");
    expect(trigger.closest("p")).toBeNull();
    // The note itself still renders, so the fix did not remove content.
    expect(screen.getByText(/Latest published:/)).toBeInTheDocument();
    expect(container.querySelector("details")).not.toBeNull();
  });

  it("keeps the freshness explanation operable from the keyboard", async () => {
    await renderLoadedPage();

    const trigger = screen.getByLabelText("What does Observation date mean?");
    const details = trigger.closest("details") as HTMLElement;
    expect(details).not.toHaveAttribute("open");

    await userEvent.click(trigger);

    expect(details).toHaveAttribute("open");
  });
});
