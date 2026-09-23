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

/** A second reading for the same period, from the existing fixture. */
function otherReading(id: string, value: number, title: string): IntelligenceObject {
  return {
    ...RATES,
    id,
    payload: { ...(RATES as { payload: Record<string, unknown> }).payload, latest_value: value, series_title: title },
  } as unknown as IntelligenceObject;
}

describe("the readings composition (#48A)", () => {
  it("renders the other readings INSIDE the lede rather than as a second section", () => {
    const other = otherReading("rates:UST_NOMINAL_2Y:2026-09-18", 4.76, "2-Year Treasury Par Yield (Nominal)");
    const { container } = render(
      <MemoryRouter>
        <TheLede object={RATES} status="resolved" alsoRecorded={[other]} />
      </MemoryRouter>,
    );

    const lede = container.querySelector("section");
    expect(lede).not.toBeNull();
    // One card, and the readings are within it.
    expect(within(lede as HTMLElement).getByRole("heading", { name: "Also recorded" })).toBeInTheDocument();
    // Demoted to h3: it is now inside the lede's h2, and it is still a
    // DIFFERENT selection, so it keeps a heading of its own.
    expect(within(lede as HTMLElement).getByRole("heading", { name: "Also recorded" }).tagName).toBe("H3");
    expect(screen.getByText("4.76%")).toBeInTheDocument();
  });

  it("renders no rail, and no empty divider, when there is nothing else on file", () => {
    const { container } = render(
      <MemoryRouter>
        <TheLede object={RATES} status="resolved" alsoRecorded={[]} />
      </MemoryRouter>,
    );
    expect(screen.queryByRole("heading", { name: "Also recorded" })).not.toBeInTheDocument();
    expect(container.querySelector(".border-t")).toBeNull();
  });

  it("keeps every value, its world and its as-of date", () => {
    const other = otherReading("rates:UST_NOMINAL_30Y:2026-09-18", 5.34, "30-Year Treasury Par Yield (Nominal)");
    render(
      <MemoryRouter>
        <TheLede object={RATES} status="resolved" alsoRecorded={[other]} />
      </MemoryRouter>,
    );
    expect(screen.getByText("5.34%")).toBeInTheDocument();
    expect(screen.getAllByText(/Rates/).length).toBeGreaterThan(0);
    expect(screen.getAllByText("2026-09-18").length).toBeGreaterThan(0);
  });
});

describe("UNKNOWN lede (before the answer is in)", () => {
  it("does not assert the quiet state before MacroChipz has checked", () => {
    // This is what the PRERENDERED html contains, since the homepage
    // fetches in the browser. Baking "No new tracked change" into
    // static HTML would publish a claim nobody verified.
    const { container } = renderLede(null, "unknown");
    expect(container.textContent).not.toContain("No new tracked change");
    // #48: "The economy right now" was the old page h1, reused here as
    // a holding heading. The state now names itself, which is the point
    // of it being distinct from quiet at all.
    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent("Not yet known");
  });

  it("offers something to do while it waits, without claiming an answer", () => {
    // #48: the four-world grid left this component -- the Living
    // Economy hero renders it directly above, and twice within one
    // screen was the duplication the increment set out to remove. What
    // replaced it is two real routes.
    renderLede(null, "unknown");
    expect(screen.getByRole("link", { name: /next data is scheduled/ })).toHaveAttribute("href", "/calendar");
    expect(screen.getByRole("link", { name: /How every figure is produced/ })).toHaveAttribute("href", "/explain");
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

  it("offers two real routes, weighted rather than footnoted", () => {
    // #48: quiet is the MAJORITY state -- roughly two thirds of
    // business days carry no scheduled release -- so its actions are
    // buttons rather than a trailing link, and both routes exist.
    renderLede(null);
    expect(screen.getByRole("link", { name: /next data is scheduled/ })).toHaveAttribute("href", "/calendar");
    expect(screen.getByRole("link", { name: /How every figure is produced/ })).toHaveAttribute("href", "/explain");
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

  it("no longer repeats the world grid the hero already renders", () => {
    // #48. The worlds are still derived from the registry -- that
    // property moved to `LivingEconomyHero`, where its own test asserts
    // it. What is asserted HERE is that they are not listed twice.
    const { container } = renderLede(null);
    expect(within(container).queryAllByRole("listitem")).toHaveLength(0);
    for (const world of ECONOMIC_WORLDS) {
      expect(container.textContent, world.label).not.toContain(world.label);
    }
  });
});
