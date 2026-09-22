/**
 * World orientation on the homepage (Increment #45B).
 *
 * The thing this section must never become is a second lede. It makes
 * a different claim — "these exist, here is the latest data on file" —
 * and the tests below are mostly about what it refuses to say.
 */
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import type { HousingResult } from "../../api/housing.types";
import type { InflationMonitorResult } from "../../api/inflation.types";
import type { IntelligenceObject } from "../../api/intelligence.types";
import type { LaborMonitorResult } from "../../api/labor.types";
import type { ApiResourceState } from "../../api/useApiResource";
import { ECONOMIC_WORLDS } from "../../worlds/registry";
import { WorldOrientation } from "./WorldOrientation";

const loading = { status: "loading" } as const;
const failed = { status: "error", error: { kind: "network", message: "x" } } as unknown as ApiResourceState<never>;

function inflation(period: string | null): ApiResourceState<InflationMonitorResult> {
  return {
    status: "success",
    data: { underlying_momentum: { calculation_period: period } },
  } as unknown as ApiResourceState<InflationMonitorResult>;
}

function labor(period: string | null): ApiResourceState<LaborMonitorResult> {
  return { status: "success", data: { evaluation_period: period } } as unknown as ApiResourceState<LaborMonitorResult>;
}

function housing(period: string | null): ApiResourceState<HousingResult> {
  return { status: "success", data: { as_of_period: period } } as unknown as ApiResourceState<HousingResult>;
}

function ratesObject(period: string): IntelligenceObject {
  return { world: "rates", effective_period: period } as unknown as IntelligenceObject;
}

function renderSection(overrides: Partial<Parameters<typeof WorldOrientation>[0]> = {}) {
  return render(
    <MemoryRouter>
      <WorldOrientation
        inflation={loading as ApiResourceState<InflationMonitorResult>}
        labor={loading as ApiResourceState<LaborMonitorResult>}
        housing={loading as ApiResourceState<HousingResult>}
        intelligence={[]}
        {...overrides}
      />
    </MemoryRouter>,
  );
}

describe("every world is reachable", () => {
  it("renders all four worlds with their canonical routes", () => {
    renderSection();

    for (const world of ECONOMIC_WORLDS) {
      const link = screen.getByRole("link", { name: new RegExp(world.label) });
      expect(link).toHaveAttribute("href", world.route);
    }
  });

  it("is derived from the registry, so a world cannot be omitted by hand", () => {
    renderSection();
    expect(screen.getAllByRole("listitem")).toHaveLength(ECONOMIC_WORLDS.length);
  });

  it("renders completely before any resource resolves", () => {
    // The grid is registry-driven, so a slow or dead backend never
    // costs the reader their route into the product.
    renderSection();
    expect(screen.getAllByRole("listitem")).toHaveLength(4);
    expect(screen.getByRole("link", { name: /Housing/ })).toBeInTheDocument();
  });
});

describe("latest-data lines", () => {
  it("shows each world's period once its own resource resolves", () => {
    renderSection({
      inflation: inflation("2026-07-01"),
      labor: labor("2026-08-01"),
      housing: housing("2026-08-01"),
      intelligence: [ratesObject("2026-09-18")],
    });

    expect(screen.getByText("Latest data: July 2026")).toBeInTheDocument();
    expect(screen.getAllByText("Latest data: August 2026")).toHaveLength(2);
    expect(screen.getByText("Latest data: September 2026")).toBeInTheDocument();
  });

  it("takes the newest rates period from objects already fetched", () => {
    renderSection({ intelligence: [ratesObject("2026-09-10"), ratesObject("2026-09-18")] });
    expect(screen.getByText("Latest data: September 2026")).toBeInTheDocument();
  });

  it("omits one world's line without touching the others", () => {
    // Failure isolation, the same property every other homepage
    // resource has.
    renderSection({
      inflation: inflation("2026-07-01"),
      housing: failed as ApiResourceState<HousingResult>,
    });

    expect(screen.getByText("Latest data: July 2026")).toBeInTheDocument();
    const housingCard = screen.getByRole("link", { name: /Housing/ });
    expect(within(housingCard).queryByText(/Latest data/)).not.toBeInTheDocument();
    // Housing is still a route the reader can take.
    expect(housingCard).toHaveAttribute("href", "/housing");
  });

  it("shows no line at all rather than an absence notice", () => {
    renderSection({ housing: housing(null) });
    expect(screen.queryByText(/No data available/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Latest data/)).not.toBeInTheDocument();
  });
});

describe("what it refuses to say", () => {
  const fullyResolved = {
    inflation: inflation("2026-07-01"),
    labor: labor("2026-08-01"),
    housing: housing("2026-08-01"),
    intelligence: [ratesObject("2026-09-18")],
  };

  it("publishes no state, score or rating", () => {
    // `CurrentStateSection` owns the canonical states. Repeating them
    // here would make two surfaces responsible for one fact.
    const { container } = renderSection(fullyResolved);
    const text = (container.textContent ?? "").toLowerCase();
    for (const forbidden of ["mixed", "cooling", "heating", "strong", "weak", "score", "rating"]) {
      expect(text, forbidden).not.toMatch(new RegExp(`\\b${forbidden}\\b`));
    }
  });

  it("uses no change or direction language", () => {
    const { container } = renderSection(fullyResolved);
    const text = (container.textContent ?? "").toLowerCase();
    for (const forbidden of ["rose", "fell", "up ", "down ", "increased", "decreased", "improved", "worsened"]) {
      expect(text, forbidden).not.toContain(forbidden);
    }
  });

  it("claims no significance or ranking", () => {
    const { container } = renderSection(fullyResolved);
    const text = (container.textContent ?? "").toLowerCase();
    for (const forbidden of ["most important", "biggest", "top ", "leading", "headline"]) {
      expect(text, forbidden).not.toContain(forbidden);
    }
  });

  it("never asserts the economy is quiet", () => {
    // The unresolved state is "MacroChipz has not loaded this yet",
    // which is not the same claim and must never be rendered as one.
    const { container } = renderSection();
    const text = (container.textContent ?? "").toLowerCase();
    for (const forbidden of ["nothing happened", "no change", "quiet", "nothing new"]) {
      expect(text, forbidden).not.toContain(forbidden);
    }
  });
});

describe("accessibility", () => {
  it("is a labelled region with a real heading", () => {
    renderSection();
    expect(screen.getByRole("region", { name: "Explore the economy" })).toBeInTheDocument();
  });

  it("uses a list, so the four worlds are announced as a set", () => {
    renderSection();
    expect(screen.getByRole("list")).toBeInTheDocument();
  });
});
