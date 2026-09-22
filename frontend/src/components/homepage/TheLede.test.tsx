/**
 * THE LEDE (Increment #42).
 *
 * Two states, both valid. These tests hold the line that the active
 * state states a fact without claiming importance, and that the quiet
 * state orients without manufacturing activity.
 */
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import type { IntelligenceObject } from "../../api/intelligence.types";
import { ECONOMIC_WORLDS } from "../../worlds/registry";
import { TheLede } from "./TheLede";

const RATES = {
  id: "rates:UST_NOMINAL_10Y:2026-09-18",
  type: "RATES_MOVEMENT",
  world: "rates",
  concepts: ["UST_NOMINAL_10Y"],
  effective_period: "2026-09-18",
  recorded_at: "2026-09-20T00:04:54.461189Z",
  published_at: null,
  knowledge_basis: "OBSERVED",
  basis: "METHODOLOGY_DERIVED",
  methodology: { methodology_id: "rates_v1.0", data_basis: "latest_published_data" },
  evidence: [],
  relations: [],
  limitations: [],
  contract_version: "intelligence_v1",
  payload: {
    series_title: "10-Year Treasury Par Yield (Nominal)",
    latest_value: 5.01,
    changes: [{ window: "5_SESSIONS", sessions: 5, available: true, change_basis_points: 5, from_date: "2026-09-11", from_value: 4.96 }],
    historical_percentile_rank: 0.566,
    historical_magnitude_percentile_rank: 0.398,
    historical_observation_count: 113,
    visual_evidence: {
      kind: "TIME_SERIES",
      concept_id: "UST_NOMINAL_10Y",
      unit: "Percent",
      requested_sessions: 63,
      available_sessions: 3,
      points: [
        { observation_date: "2026-06-22", value: 4.51 },
        { observation_date: "2026-08-10", value: 4.72 },
        { observation_date: "2026-09-18", value: 5.01 },
      ],
    },
  },
} as unknown as IntelligenceObject;

/**
 * THE LEDE's own copy, excluding the embedded chart figure.
 *
 * `VisualEvidenceChart` carries its own honest caption -- which
 * legitimately contains words like "because" when explaining why a
 * series is shorter than requested -- and it has its own tests. What is
 * under test here is what the LEDE itself says.
 */
function ledeCopy(container: HTMLElement): string {
  const clone = container.cloneNode(true) as HTMLElement;
  clone.querySelectorAll("figure").forEach((figure) => figure.remove());
  return (clone.textContent ?? "").toLowerCase();
}

function renderLede(object: IntelligenceObject | null, status: "unknown" | "resolved" = "resolved") {
  return render(
    <MemoryRouter>
      <TheLede object={object} status={status} />
    </MemoryRouter>,
  );
}

describe("ACTIVE lede", () => {
  it("leads with a recognisable name and the number", () => {
    renderLede(RATES);
    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent("10-year Treasury yield");
    expect(screen.getByText("5.01%")).toBeInTheDocument();
  });

  it("states the movement in plain units", () => {
    renderLede(RATES);
    expect(screen.getByText(/Up 0\.05 percentage points/)).toBeInTheDocument();
    expect(screen.getByText(/over the last 5 trading days/)).toBeInTheDocument();
  });

  it("anchors time to the period the data describes, not to now", () => {
    const { container } = renderLede(RATES);
    expect(screen.getAllByText("2026-09-18").length).toBeGreaterThan(0);
    const text = ledeCopy(container);
    // `published_at` is null on every local object and `recorded_at`
    // is a backfill timestamp, so none of these can be justified.
    for (const word of ["today", "just released", "breaking", "moments ago", "this morning", "latest news"]) {
      expect(text, word).not.toContain(word);
    }
  });

  it("makes no claim about importance", () => {
    const { container } = renderLede(RATES);
    const text = ledeCopy(container);
    for (const word of ["most important", "biggest", "major", "significant", "notable", "top story", "headline", "urgent", "alert"]) {
      expect(text, word).not.toContain(word);
    }
  });

  it("asserts no cause", () => {
    const { container } = renderLede(RATES);
    const text = ledeCopy(container);
    for (const word of ["because", "driven by", "caused by", "due to", "in response", "after the fed", "on fears"]) {
      expect(text, word).not.toContain(word);
    }
  });

  it("leads into the evidence and into the world", () => {
    renderLede(RATES);
    expect(screen.getByRole("link", { name: /See the evidence/ })).toHaveAttribute(
      "href",
      "/intelligence/rates%3AUST_NOMINAL_10Y%3A2026-09-18",
    );
    expect(screen.getByRole("link", { name: /Explore Rates/ })).toHaveAttribute("href", "/rates");
  });

  it("shows the series the object already carries, fetching nothing itself", () => {
    const { container } = renderLede(RATES);
    expect(container.querySelectorAll('svg[role="img"]').length).toBeGreaterThan(0);
  });

  it("shows no chart when the object carries no visual evidence", () => {
    const withoutChart = { ...RATES, payload: { ...RATES.payload, visual_evidence: null } } as IntelligenceObject;
    const { container } = renderLede(withoutChart);
    expect(container.querySelectorAll('svg[role="img"]')).toHaveLength(0);
    // ...and the rest of the lede is unaffected.
    expect(screen.getByText("5.01%")).toBeInTheDocument();
  });
});

describe("UNKNOWN lede (before the answer is in)", () => {
  it("does not assert the quiet state before MacroChipz has checked", () => {
    // This is what the PRERENDERED html contains, since the homepage
    // fetches in the browser. Baking "No new tracked change" into
    // static HTML would publish a claim nobody verified.
    const { container } = renderLede(null, "unknown");
    expect(container.textContent).not.toContain("No new tracked change");
    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent("The economy right now");
  });

  it("still opens every world while it waits", () => {
    renderLede(null, "unknown");
    expect(screen.getByRole("link", { name: /Inflation/ })).toHaveAttribute("href", "/inflation");
  });
});

describe("QUIET lede", () => {
  it("does not say nothing is happening", () => {
    const { container } = renderLede(null);
    const text = (container.textContent ?? "").toLowerCase();
    for (const phrase of ["nothing is happening", "no news", "all quiet", "nothing to report"]) {
      expect(text, phrase).not.toContain(phrase);
    }
  });

  it("says what MacroChipz actually knows, and what it does not claim", () => {
    renderLede(null);
    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent("No new tracked change");
    expect(screen.getByText(/not a claim that the economy is quiet/)).toBeInTheDocument();
  });

  it("still opens every world", () => {
    renderLede(null);
    const worlds: ReadonlyArray<readonly [string, string]> = [
      ["Inflation", "/inflation"],
      ["Jobs", "/jobs"],
      ["Rates", "/rates"],
    ];
    for (const [name, href] of worlds) {
      expect(screen.getByRole("link", { name: new RegExp(name) })).toHaveAttribute("href", href);
    }
  });

  it("points at the calendar rather than at a fabricated event", () => {
    renderLede(null);
    expect(screen.getByRole("link", { name: /next data is scheduled/ })).toHaveAttribute("href", "/calendar");
  });

  it("uses no visit-time language", () => {
    // #42 §5: the previously rejected "days since visit" logic must
    // not return, and browser time is not economic freshness.
    const { container } = renderLede(null);
    const text = (container.textContent ?? "").toLowerCase();
    for (const phrase of ["since your last visit", "days since", "while you were away", "welcome back"]) {
      expect(text, phrase).not.toContain(phrase);
    }
  });

  it("names every active world, and only worlds that have data", () => {
    // Derived from the registry rather than hardcoded, which is the
    // property #45 relied on: Housing appeared here through one registry
    // entry, with no change to `homepage_presentation_v1.0` and no
    // Housing-specific code on the homepage.
    const { container } = renderLede(null);
    const items = within(container).getAllByRole("listitem");
    expect(items).toHaveLength(ECONOMIC_WORLDS.length);
    for (const world of ECONOMIC_WORLDS) {
      expect(container.textContent, world.label).toContain(world.label);
    }
    // A world with no data still gets no slot.
    for (const absent of ["Consumer", "Growth"]) {
      expect(container.textContent, absent).not.toMatch(new RegExp(absent, "i"));
    }
  });
});
