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
import { listRatesMovements } from "../api/intelligence";
import { getRatesMonitor } from "../api/rates";
import { RATES_MOVEMENT_LIMITATIONS, buildRatesMovementList } from "../test/fixtures/intelligence";
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
/* #52B. Recorded movements are a SECOND, independent resource. Mocked
   here so every existing test controls it too -- before this, an
   unmocked fetch made the page render a second `role="alert"` and the
   monitor's own error assertion became ambiguous. */
vi.mock("../api/intelligence", () => ({ listRatesMovements: vi.fn() }));

const mockedGetRatesMonitor = vi.mocked(getRatesMonitor);
const mockedListRatesMovements = vi.mocked(listRatesMovements);

beforeEach(() => {
  mockedGetRatesMonitor.mockReset();
  mockedListRatesMovements.mockReset();
  mockedListRatesMovements.mockResolvedValue(buildRatesMovementList());
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
    const table = within(curve).getByRole("table", { name: /Nominal Treasury par yields by maturity/ });
    expect(within(table).getByRole("rowheader", { name: "2Y" })).toBeInTheDocument();
    expect(within(table).getByRole("rowheader", { name: "30Y" })).toBeInTheDocument();
    expect(within(table).getByText("4.76%")).toBeInTheDocument();
    expect(within(table).getByText("5.34%")).toBeInTheDocument();
  });

  it("offers every maturity as a control, and selects the 10-year by default", async () => {
    mockedGetRatesMonitor.mockResolvedValue(buildRatesMonitor());
    renderPage();

    const curve = await screen.findByRole("region", { name: "Treasury curve" });
    // #52B: the curve card also holds the comparison-window controls, so
    // this scopes to the maturity group by name rather than to every
    // button in the section.
    const maturities = within(curve).getByRole("group", { name: "Select a maturity" });
    const controls = within(maturities).getAllByRole("button");
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
    const maturities = within(curve).getByRole("group", { name: "Select a maturity" });
    const twoYear = within(maturities).getByRole("button", { name: /^2Y/ });
    await user.click(twoYear);

    const panel = screen.getByRole("region", { name: "The maturity you selected" });
    expect(within(panel).getByText("4.76%")).toBeInTheDocument();
    expect(twoYear).toHaveAttribute("aria-pressed", "true");
    expect(
      within(maturities)
        .getAllByRole("button")
        .filter((c) => c.getAttribute("aria-pressed") === "true"),
    ).toHaveLength(1);
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
    // #52B: with a comparison active the label describes BOTH curves,
    // so this matches the part that never changes -- the latest date and
    // its published readings.
    const charts = within(section).getAllByRole("img", {
      name: /Sep 18, 2026: 2Y 4\.76%/,
    });
    expect(charts).toHaveLength(2);
    for (const chart of charts) {
      expect(chart).toHaveAttribute("preserveAspectRatio", "xMidYMid meet");
    }

    const table = within(section).getByRole("table", { name: /Nominal Treasury par yields by maturity/ });
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
    const table = within(section).getByRole("table", { name: /Nominal Treasury par yields by maturity/ });
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

/**
 * Increment #52B — the curve, then and now.
 *
 * What these protect is narrow and specific: that the second curve is
 * the backend's published `from_value` on its published `from_date`,
 * that a missing reading breaks the line instead of becoming a zero,
 * that four values from four different days are never drawn as one
 * curve, and that describing a shape never becomes predicting one.
 */
describe("RatesPage curve comparison", () => {
  it("defaults to the longest published window and draws both curves", async () => {
    mockedGetRatesMonitor.mockResolvedValue(buildRatesMonitor());
    renderPage();

    const curve = await screen.findByRole("region", { name: "Treasury curve" });
    const windows = within(curve).getByRole("group", { name: "Compare with an earlier published day" });

    // The DEFAULT is structural -- the widest comparison published --
    // not the window whose story reads best. See the note in Rates.tsx.
    const pressed = within(windows)
      .getAllByRole("button")
      .filter((button) => button.getAttribute("aria-pressed") === "true");
    expect(pressed).toHaveLength(1);
    expect(pressed[0]).toHaveAccessibleName(/63 sessions earlier/);
    expect(pressed[0]).toHaveAccessibleName(/Jun 18, 2026/);

    // Both dates head the accessible table, and every value in the
    // earlier column is the backend's own `from_value`.
    const table = within(curve).getByRole("table", { name: /Nominal Treasury par yields by maturity/ });
    expect(within(table).getByRole("columnheader", { name: "Jun 18, 2026" })).toBeInTheDocument();
    expect(within(table).getByRole("columnheader", { name: "Sep 18, 2026" })).toBeInTheDocument();
    expect(within(table).getByText("4.19%")).toBeInTheDocument();
    expect(within(table).getByText("4.90%")).toBeInTheDocument();
    expect(within(table).getByText("+57 bp")).toBeInTheDocument();
  });

  it("redraws against the window the reader chose, using that window's own published date", async () => {
    const user = userEvent.setup();
    mockedGetRatesMonitor.mockResolvedValue(buildRatesMonitor());
    renderPage();

    const curve = await screen.findByRole("region", { name: "Treasury curve" });
    const windows = within(curve).getByRole("group", { name: "Compare with an earlier published day" });
    await user.click(within(windows).getByRole("button", { name: /21 sessions earlier/ }));

    const table = within(curve).getByRole("table", { name: /Nominal Treasury par yields by maturity/ });
    expect(within(table).getByRole("columnheader", { name: "Aug 19, 2026" })).toBeInTheDocument();
    // 21 sessions, not 63: the 2-year's published `from_value` differs
    // between them, which is the only reason this can distinguish a
    // working selector from one that ignores its argument.
    expect(within(table).getByText("4.35%")).toBeInTheDocument();
    expect(within(table).queryByText("4.23%")).not.toBeInTheDocument();
  });

  it("turns the comparison off entirely, back to one curve and one date", async () => {
    const user = userEvent.setup();
    mockedGetRatesMonitor.mockResolvedValue(buildRatesMonitor());
    renderPage();

    const curve = await screen.findByRole("region", { name: "Treasury curve" });
    const windows = within(curve).getByRole("group", { name: "Compare with an earlier published day" });
    await user.click(within(windows).getByRole("button", { name: /Latest only/ }));

    const table = within(curve).getByRole("table", { name: /Nominal Treasury par yields by maturity/ });
    expect(within(table).getByRole("columnheader", { name: "Yield" })).toBeInTheDocument();
    expect(within(table).queryByRole("columnheader", { name: "Jun 18, 2026" })).not.toBeInTheDocument();
    expect(within(curve).queryByText(/Level/)).not.toBeInTheDocument();
  });

  it("reads the level from every maturity's own published change, and says so when they disagree", async () => {
    const user = userEvent.setup();
    mockedGetRatesMonitor.mockResolvedValue(buildRatesMonitor());
    renderPage();

    const curve = await screen.findByRole("region", { name: "Treasury curve" });
    // 63 sessions: every maturity higher.
    expect(within(curve).getByText(/Every maturity pays more than it did on Jun 18, 2026/)).toBeInTheDocument();

    // 5 sessions: the 30-year fell 1 bp while the other three rose. The
    // page must not flatten that into one direction.
    const windows = within(curve).getByRole("group", { name: "Compare with an earlier published day" });
    await user.click(within(windows).getByRole("button", { name: /5 sessions earlier/ }));
    expect(
      within(curve).getByText(/Some maturities pay more and some pay less than they did on Sep 11, 2026/),
    ).toBeInTheDocument();
  });

  it("describes the shape change from the published spread, never from two yields", async () => {
    const user = userEvent.setup();
    mockedGetRatesMonitor.mockResolvedValue(buildRatesMonitor());
    renderPage();

    const curve = await screen.findByRole("region", { name: "Treasury curve" });
    const windows = within(curve).getByRole("group", { name: "Compare with an earlier published day" });
    await user.click(within(windows).getByRole("button", { name: /21 sessions earlier/ }));

    // 1.00 -> 0.58, published as −42 bp on the 2s30s spread's own
    // change entry. Nothing on this page subtracts 4.19 from 5.19.
    const shape = within(curve).getByText(/The gap between the 2Y and the 30Y is/);
    expect(shape).toHaveTextContent("narrower");
    expect(shape).toHaveTextContent("1.00");
    expect(shape).toHaveTextContent("0.58");
    expect(shape).toHaveTextContent("−42 bp");
  });

  it("breaks the earlier line at a missing reading rather than drawing through a zero", async () => {
    mockedGetRatesMonitor.mockResolvedValue(
      buildRatesMonitor({
        nominal_curve: buildRatesMonitor().nominal_curve.map((level) =>
          level.series_id === "UST_NOMINAL_5Y"
            ? {
                ...level,
                changes: level.changes.map((change) =>
                  change.window === "63_SESSIONS"
                    ? { ...change, available: false, from_value: null, from_date: null, change_basis_points: null }
                    : change,
                ),
              }
            : level,
        ),
      }),
    );
    renderPage();

    const curve = await screen.findByRole("region", { name: "Treasury curve" });

    // The gap is named, with the maturity and the date.
    expect(within(curve).getByText(/Incomplete comparison/)).toBeInTheDocument();
    expect(within(curve).getByText(/No 5Y reading is published for Jun 18, 2026/)).toBeInTheDocument();

    // The dashed line is drawn as TWO subpaths, not one through the
    // gap -- the #51B defect (null coerced to 0) would produce one
    // continuous path dropping to the axis floor.
    // Scoped to the curve region on purpose: the story teaser further
    // down the page draws its own dashed SVG paths, and an unscoped
    // query found four of them.
    const dashed = curve.querySelectorAll("svg path[stroke-dasharray]");
    expect(dashed.length).toBeGreaterThanOrEqual(1);
    for (const path of dashed) {
      expect(path.getAttribute("d")).not.toMatch(/\b0(\.0+)?\b(?!\d)/);
    }

    // And the missing value is stated, never rendered as a reading.
    const table = within(curve).getByRole("table", { name: /Nominal Treasury par yields by maturity/ });
    expect(within(table).getByText("Not available")).toBeInTheDocument();
    expect(within(table).queryByText("0.00%")).not.toBeInTheDocument();
  });

  it("refuses to draw one curve when the maturities resolved to different dates", async () => {
    mockedGetRatesMonitor.mockResolvedValue(
      buildRatesMonitor({
        nominal_curve: buildRatesMonitor().nominal_curve.map((level) =>
          level.series_id === "UST_NOMINAL_2Y"
            ? {
                ...level,
                changes: level.changes.map((change) =>
                  change.window === "63_SESSIONS" ? { ...change, from_date: "2026-06-17" } : change,
                ),
              }
            : level,
        ),
      }),
    );
    renderPage();

    const curve = await screen.findByRole("region", { name: "Treasury curve" });
    expect(within(curve).getByText(/No single earlier curve/)).toBeInTheDocument();
    expect(within(curve).getByText(/Jun 17, 2026, Jun 18, 2026/)).toBeInTheDocument();

    // Nothing dashed is drawn, and the reading is withheld rather than
    // describing a shape nobody published.
    expect(curve.querySelectorAll("svg path[stroke-dasharray]")).toHaveLength(0);
    expect(within(curve).queryByText(/The gap between/)).not.toBeInTheDocument();
  });

  it("offers only the windows something was published for", async () => {
    mockedGetRatesMonitor.mockResolvedValue(
      buildRatesMonitor({
        nominal_curve: buildRatesMonitor().nominal_curve.map((level) => ({
          ...level,
          changes: level.changes.map((change) =>
            change.window === "63_SESSIONS"
              ? { ...change, available: false, from_value: null, from_date: null, change_basis_points: null }
              : change,
          ),
        })),
      }),
    );
    renderPage();

    const curve = await screen.findByRole("region", { name: "Treasury curve" });
    const windows = within(curve).getByRole("group", { name: "Compare with an earlier published day" });
    expect(within(windows).queryByRole("button", { name: /63 sessions earlier/ })).not.toBeInTheDocument();
    // The default falls back to the longest window that IS published.
    const pressed = within(windows)
      .getAllByRole("button")
      .filter((button) => button.getAttribute("aria-pressed") === "true");
    expect(pressed[0]).toHaveAccessibleName(/21 sessions earlier/);
  });

  it("describes a shape without predicting one", async () => {
    mockedGetRatesMonitor.mockResolvedValue(buildRatesMonitor());
    renderPage();

    await screen.findByRole("region", { name: "Treasury curve" });
    const page = (document.body.textContent ?? "").toLowerCase();
    // The same vocabulary the spread card has been guarded against
    // since #30, now asserted with a comparison ACTIVE -- which is the
    // state that invites the claim.
    for (const forbidden of ["recession", "risk-off", "hawkish", "tightening", "easing", "predict", "signals that"]) {
      expect(page).not.toContain(forbidden);
    }
    expect(page).toContain("defines no state label and no forecast");
  });
});

describe("RatesPage recorded movements", () => {
  it("states how many records exist before a reader opens them", async () => {
    mockedGetRatesMonitor.mockResolvedValue(buildRatesMonitor());
    renderPage();

    // Collapsed by default -- six cards measured 1,500px at 390px. The
    // COUNT stays visible, so the disclosure is an offer rather than a
    // hidden section a reader has no reason to open.
    const section = await screen.findByRole("region", { name: "Movements MacroChipz recorded" });
    expect(within(section).getByText("Show all 6 recorded movements")).toBeInTheDocument();
    expect(section.querySelector("details")?.open).toBe(false);
  });

  it("renders every recorded movement, distinguishing what was observed from when it was recorded", async () => {
    const user = userEvent.setup();
    mockedGetRatesMonitor.mockResolvedValue(buildRatesMonitor());
    renderPage();

    const section = await screen.findByRole("region", { name: "Movements MacroChipz recorded" });
    await user.click(within(section).getByText("Show all 6 recorded movements"));

    // Counted by their links rather than by every `<li>`: each card
    // nests the object's own limitations as a list of its own.
    const rows = within(section).getAllByRole("link");
    expect(rows).toHaveLength(6);

    // Ordered by `homepage_presentation_v1.0`, not by arrival: the
    // fixture returns the real yields first and the 10-year third.
    expect(rows[0]).toHaveTextContent("10-year Treasury yield");

    const first = within(rows[0]?.closest("li") as HTMLElement);
    expect(first.getByText("Observed")).toBeInTheDocument();
    expect(first.getByText("Sep 18, 2026")).toBeInTheDocument();
    expect(first.getByText("Recorded")).toBeInTheDocument();
    expect(first.getByText("Sep 20, 2026")).toBeInTheDocument();
  });

  it("reproduces each object's own limitations rather than summarising them", async () => {
    const user = userEvent.setup();
    mockedGetRatesMonitor.mockResolvedValue(buildRatesMonitor());
    renderPage();

    const section = await screen.findByRole("region", { name: "Movements MacroChipz recorded" });
    await user.click(within(section).getByText("Show all 6 recorded movements"));
    await user.click(within(section).getAllByText("Evidence and limitations")[0] as HTMLElement);

    for (const limitation of RATES_MOVEMENT_LIMITATIONS) {
      expect(within(section).getAllByText(limitation).length).toBeGreaterThan(0);
    }
  });

  it("keeps the Treasury curve usable when the movements feed fails", async () => {
    mockedGetRatesMonitor.mockResolvedValue(buildRatesMonitor());
    mockedListRatesMovements.mockRejectedValue(new ApiError("network", "boom"));
    renderPage();

    const curve = await screen.findByRole("region", { name: "Treasury curve" });
    expect(within(curve).getByRole("table", { name: /Nominal Treasury par yields by maturity/ })).toBeInTheDocument();
    expect(within(curve).getByText(/Every maturity pays more than it did/)).toBeInTheDocument();

    const movements = screen.getByRole("region", { name: "Movements MacroChipz recorded" });
    expect(within(movements).getByRole("alert")).toHaveTextContent("Recorded movements could not be loaded.");
  });

  it("still renders recorded movements when the rates monitor fails", async () => {
    mockedGetRatesMonitor.mockRejectedValue(new ApiError("network", "boom"));
    renderPage();

    const movements = await screen.findByRole("region", { name: "Movements MacroChipz recorded" });
    await userEvent.setup().click(within(movements).getByText("Show all 6 recorded movements"));
    expect(within(movements).getAllByRole("link")).toHaveLength(6);
    expect(screen.queryByRole("region", { name: "Treasury curve" })).not.toBeInTheDocument();
  });

  it("says nothing was recorded rather than showing an empty frame", async () => {
    mockedGetRatesMonitor.mockResolvedValue(buildRatesMonitor());
    mockedListRatesMovements.mockResolvedValue(buildRatesMovementList({ items: [], total: 0 }));
    renderPage();

    const section = await screen.findByRole("region", { name: "Movements MacroChipz recorded" });
    expect(within(section).getByText(/has recorded no Treasury movements yet/)).toBeInTheDocument();
  });
});
