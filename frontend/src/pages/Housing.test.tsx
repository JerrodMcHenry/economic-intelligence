/**
 * The Housing page (Increment #45).
 *
 * The figures used are the ones Census actually published for July and
 * August 2026, so an assertion here that disagrees with the release
 * disagrees with the source rather than with itself.
 */
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { HousingMeasure, HousingResult, HousingStageId } from "../api/housing.types";
import { HousingPage } from "./Housing";

afterEach(() => {
  vi.unstubAllGlobals();
});

function measure(overrides: Partial<HousingMeasure> = {}): HousingMeasure {
  return {
    concept_id: "us.housing.units-authorized.saar.monthly",
    unit: "HOUSING_UNITS_ANNUAL_RATE",
    seasonal_adjustment: "SEASONALLY_ADJUSTED",
    available: true,
    unavailable_reason: null,
    period: "2026-08-01",
    value: 1_394_000,
    previous_period: "2026-07-01",
    previous_value: 1_433_000,
    change_from_previous: -39_000,
    change_percent_from_previous: -2.721563,
    year_ago_period: "2025-08-01",
    year_ago_value: 1_347_000,
    change_from_year_ago: 47_000,
    change_percent_from_year_ago: 3.489235,
    observation_count: 800,
    earliest_period: "1960-01-01",
    provenance: {
      provider: "CENSUS",
      dataset: "timeseries/eits/resconst",
      provider_series_id: "APERMITS/TOTAL",
      observation_date: "2026-08-01",
      source_url: "https://www.census.gov/construction/nrc/",
      retrieved_at: "2026-09-21T12:00:00Z",
      revision_count: 0,
      last_revised_at: null,
    },
    trend: {
      concept_id: "us.housing.units-authorized.saar.monthly",
      unit: "HOUSING_UNITS_ANNUAL_RATE",
      requested_months: 60,
      available_months: 3,
      points: [
        { observation_date: "2026-06-01", value: 1_400_000 },
        { observation_date: "2026-07-01", value: 1_433_000 },
        { observation_date: "2026-08-01", value: 1_394_000 },
      ],
    },
    ...overrides,
  };
}

/** The real values from the August 2026 release, per stage. */
const STAGE_FIGURES: Record<HousingStageId, { pace: number; actual: number; previous: number }> = {
  PERMITS: { pace: 1_394_000, actual: 117_400, previous: 1_433_000 },
  STARTS: { pace: 1_275_000, actual: 110_500, previous: 1_309_000 },
  COMPLETIONS: { pace: 1_128_000, actual: 100_100, previous: 1_280_000 },
};

function result(overrides: Partial<HousingResult> = {}): HousingResult {
  return {
    contract_version: "housing_v1_data",
    data_basis: "latest_published_data",
    provider: "CENSUS",
    attribution:
      "This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau.",
    source_statement:
      "Source: U.S. Census Bureau and U.S. Department of Housing and Urban Development, New Residential Construction.",
    source_url: "https://www.census.gov/construction/nrc/",
    as_of_period: "2026-08-01",
    stages: (["PERMITS", "STARTS", "COMPLETIONS"] as const).map((stage) => ({
      stage,
      pace: measure({
        value: STAGE_FIGURES[stage].pace,
        previous_value: STAGE_FIGURES[stage].previous,
        concept_id: `us.housing.${stage.toLowerCase()}.saar.monthly`,
        trend: {
          concept_id: `us.housing.${stage.toLowerCase()}.saar.monthly`,
          unit: "HOUSING_UNITS_ANNUAL_RATE",
          requested_months: 60,
          available_months: 3,
          points: [
            { observation_date: "2026-06-01", value: STAGE_FIGURES[stage].previous - 20_000 },
            { observation_date: "2026-07-01", value: STAGE_FIGURES[stage].previous },
            { observation_date: "2026-08-01", value: STAGE_FIGURES[stage].pace },
          ],
        },
      }),
      actual: measure({
        concept_id: `us.housing.${stage.toLowerCase()}.nsa.monthly`,
        unit: "HOUSING_UNITS",
        seasonal_adjustment: "NOT_SEASONALLY_ADJUSTED",
        value: STAGE_FIGURES[stage].actual,
      }),
    })),
    saar_explanation:
      "A seasonally adjusted annual rate describes the pace of building in one month, expressed as what a full year at that pace would total. It is not a count of homes in that month, it is not a forecast, and dividing it by twelve does not give the month's actual figure.",
    limitations: [
      "Permits, starts and completions are three separate measurements, not one cohort followed through time.",
      "MacroChipz applies no state, score, rating or direction label to Housing.",
    ],
    ...overrides,
  };
}

function renderPage(payload: HousingResult | null) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      payload === null
        ? new Response("boom", { status: 500 })
        : new Response(JSON.stringify(payload), { status: 200, headers: { "Content-Type": "application/json" } }),
    ),
  );
  return render(
    <MemoryRouter>
      <HousingPage />
    </MemoryRouter>,
  );
}

describe("the figures", () => {
  it("renders the published annual rate for each stage", async () => {
    renderPage(result());

    // Each appears twice by design: as the card's headline figure and
    // as the latest row of the chart's own value table, which is the
    // accessible alternative to the line. Both are the same canonical
    // number, which is the point.
    for (const figure of ["1,394,000", "1,275,000", "1,128,000"]) {
      expect((await screen.findAllByText(figure)).length, figure).toBeGreaterThan(0);
    }
  });

  it("renders the month's actual count beside the annual rate", async () => {
    // The figure that stops the big one being misread.
    renderPage(result());

    expect((await screen.findAllByText(/117,400/)).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/110,500/).length).toBeGreaterThan(0);
  });

  it("renders the backend's percentage change rather than deriving one", async () => {
    renderPage(result());

    // -2.721563 -> "−2.7%", the figure Census's own release quotes.
    expect(await screen.findAllByText(/−2\.7%/)).not.toHaveLength(0);
  });

  it("labels the annual rate as an annual rate, never as homes built", async () => {
    renderPage(result());
    await screen.findAllByText("1,394,000");

    // Scoped to the figures section: the pipeline diagram above also
    // has a "Permits" list item, and it deliberately carries no figure.
    const figures = screen.getByRole("region", { name: /Latest published figures/i });
    const permits = within(figures)
      .getAllByRole("listitem")
      .find((card) => within(card).queryByText("Permits"));
    expect(permits).toBeDefined();
    expect(permits!.textContent).toMatch(/at an annual rate/);
    // The sentence this page must never say about an annual rate.
    expect(permits!.textContent).not.toMatch(/1,394,000 homes/);
  });
});

describe("no housing state is rendered", () => {
  it("shows no state, rating or verdict anywhere", async () => {
    const payload = result();
    const { container } = renderPage(payload);
    await screen.findAllByText("1,394,000");

    // The backend's LIMITATIONS are stripped first, for the reason the
    // explainer registry's own guard gives: they legitimately disclaim
    // the things forbidden here ("MacroChipz applies no state, score,
    // rating..."), and a scan that flagged the disclaimer would forbid
    // the page from saying the true thing.
    let text = (container.textContent ?? "").toLowerCase();
    for (const limitation of payload.limitations) text = text.replace(limitation.toLowerCase(), "");

    for (const forbidden of ["cooling", "heating", "strong", "weak", "healthy", "score", "rating"]) {
      expect(text, forbidden).not.toMatch(new RegExp(`\\b${forbidden}\\b`));
    }
  });

  it("shows no methodology identifier, because there is none", async () => {
    const { container } = renderPage(result());
    await screen.findAllByText("1,394,000");

    expect(container.textContent).not.toMatch(/housing_v1\.0/);
  });

  it("does not offer the Analyst, which has no Housing context", async () => {
    renderPage(result());
    await screen.findAllByText("1,394,000");

    expect(screen.queryByText(/Ask MacroChipz/i)).not.toBeInTheDocument();
  });
});

describe("the annual-rate explanation", () => {
  it("renders the backend's explanation verbatim", async () => {
    const payload = result();
    const { container } = renderPage(payload);
    await screen.findAllByText("1,394,000");

    expect(container.textContent).toContain(payload.saar_explanation);
  });

  it("links to the explainer that corrects the misreading", async () => {
    renderPage(result());
    await screen.findAllByText("1,394,000");

    // Two paths to it by design: inline beside the figure it explains,
    // and in the page's "Understand this" list.
    const links = screen.getAllByRole("link", { name: /1\.5 million homes weren.t built this month/i });
    expect(links.length).toBeGreaterThanOrEqual(1);
    for (const link of links) expect(link).toHaveAttribute("href", "/explain/saar-housing");
  });
});

describe("the pipeline is explained without implying a conveyor", () => {
  it("names the three stages in plain English", async () => {
    renderPage(result());
    await screen.findAllByText("1,394,000");

    // Once in the diagram and once on the card -- the same words in
    // both places, which is why they live in one constant.
    for (const meaning of [
      "Homes authorised for construction.",
      "Homes where construction has begun.",
      "Homes finished.",
    ]) {
      expect(screen.getAllByText(meaning).length, meaning).toBeGreaterThan(0);
    }
  });

  it("states that the three are separate counts, in the diagram itself", async () => {
    const { container } = renderPage(result());
    await screen.findAllByText("1,394,000");

    expect(container.textContent).toMatch(/three separate counts, not one batch of homes/i);
    expect(container.textContent).toMatch(/not every authorised home is built/i);
  });

  it("promises no fixed lag or conversion rate", async () => {
    const { container } = renderPage(result());
    await screen.findAllByText("1,394,000");

    expect(container.textContent).toMatch(/no expected lag/i);
  });
});

describe("evidence and attribution", () => {
  it("renders Census's required attribution verbatim", async () => {
    const { container } = renderPage(result());
    await screen.findAllByText("1,394,000");

    expect(container.textContent).toContain(
      "This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau.",
    );
  });

  it("names both publishers", async () => {
    const { container } = renderPage(result());
    await screen.findAllByText("1,394,000");

    expect(container.textContent).toMatch(/Housing and Urban Development/);
  });

  it("shows the concept id beside Census's own series identifier", async () => {
    const { container } = renderPage(result());
    await screen.findAllByText("1,394,000");

    expect(container.textContent).toContain("APERMITS/TOTAL");
    expect(container.textContent).toMatch(/us\.housing\./);
  });

  it("renders every limitation the backend attached", async () => {
    const payload = result();
    const { container } = renderPage(payload);
    await screen.findAllByText("1,394,000");

    for (const limitation of payload.limitations) {
      expect(container.textContent, limitation).toContain(limitation);
    }
  });
});

describe("honest absence", () => {
  it("says so plainly when nothing has been ingested", async () => {
    renderPage(result({ as_of_period: null }));

    expect(await screen.findByText(/No housing data yet/)).toBeInTheDocument();
    expect(screen.getByText(/Nothing here is estimated in the meantime/)).toBeInTheDocument();
  });

  it("still carries the attribution when there is no data", async () => {
    const { container } = renderPage(result({ as_of_period: null }));
    await screen.findByText(/No housing data yet/);

    expect(container.textContent).toContain("not endorsed or certified by the Census Bureau");
  });

  it("reports an unavailable measure with its reason rather than a zero", async () => {
    const payload = result();
    const stages = payload.stages.map((stage, index) =>
      index === 0
        ? {
            ...stage,
            pace: measure({
              available: false,
              unavailable_reason: "No Census data has been ingested for this measure.",
              value: null,
              period: null,
              trend: null,
              provenance: null,
            }),
          }
        : stage,
    );
    const { container } = renderPage({ ...payload, stages });
    await screen.findAllByText("1,275,000");

    expect(container.textContent).toContain("No Census data has been ingested for this measure.");
    // Never a zero standing in for a missing figure.
    const permitsCard = screen.getAllByRole("listitem").find((card) => within(card).queryByText("Permits"));
    expect(permitsCard!.textContent).not.toMatch(/\b0\b/);
  });

  it("shows a retryable error when the API fails", async () => {
    renderPage(null);

    expect(await screen.findByText(/Housing data could not be loaded/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });
});

describe("accessibility", () => {
  it("gives every section a heading its region is labelled by", async () => {
    renderPage(result());
    await screen.findAllByText("1,394,000");

    for (const region of screen.getAllByRole("region")) {
      expect(region).toHaveAccessibleName();
    }
  });

  it("describes the chart as a single labelled image", async () => {
    renderPage(result());
    await screen.findAllByText("1,394,000");

    const chart = screen.getAllByRole("img")[0];
    expect(chart).toBeDefined();
    expect(chart).toHaveAccessibleName(/permits, starts and completions/i);
  });

  it("puts every charted value in a real table behind a disclosure", async () => {
    renderPage(result());
    await screen.findAllByText("1,394,000");

    expect(screen.getByText("The values behind this chart")).toBeInTheDocument();
    const tables = screen.getAllByRole("table", { hidden: true });
    expect(tables.length).toBeGreaterThan(0);
  });

  it("uses one h1 and no skipped heading level", async () => {
    renderPage(result());
    await screen.findAllByText("1,394,000");

    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    const levels = screen
      .getAllByRole("heading", { hidden: true })
      .map((heading) => Number(heading.tagName.slice(1)));
    for (let index = 1; index < levels.length; index += 1) {
      expect(levels[index]! - levels[index - 1]!).toBeLessThanOrEqual(1);
    }
  });
});

describe("explainer discovery", () => {
  it("offers both Housing explainers from the page", async () => {
    renderPage(result());
    await screen.findAllByText("1,394,000");

    expect(
      screen.getByRole("link", { name: /What do permits, starts and completions actually mean\?/ }),
    ).toHaveAttribute("href", "/explain/permits-starts-completions");
    expect(
      screen.getAllByRole("link", { name: /1\.5 million homes weren.t built this month/i })[0],
    ).toHaveAttribute("href", "/explain/saar-housing");
  });
});
