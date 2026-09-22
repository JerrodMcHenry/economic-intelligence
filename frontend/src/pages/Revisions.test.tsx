/**
 * The Revision Intelligence page (Increment #43).
 *
 * The page is currently in its EMPTY state, because MacroChipz has
 * captured no genuine revision. These tests hold both halves: the empty
 * state must teach rather than apologise, and it must never render a
 * fabricated revision to look populated.
 */
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { IntelligenceObject } from "../api/intelligence.types";
import { ECONOMIC_WORLDS } from "../worlds/registry";
import { RevisionsPage } from "./Revisions";

vi.mock("../api/intelligence");
const api = await import("../api/intelligence");

function observation(payload: Record<string, unknown>): IntelligenceObject {
  return {
    id: "observation:us.unemployment-rate.sa.monthly:2026-08-01:x",
    type: "OBSERVATION_CHANGE",
    world: "jobs",
    concepts: ["us.unemployment-rate.sa.monthly"],
    effective_period: "2026-08-01",
    recorded_at: "2026-09-19T18:46:27Z",
    published_at: null,
    knowledge_basis: "OBSERVED",
    basis: "SOURCE_FACT",
    methodology: null,
    evidence: [],
    relations: [],
    limitations: [],
    contract_version: "intelligence_v1",
    payload: {
      series_title: "Unemployment Rate",
      provider: "FRED",
      provider_series_id: "UNRATE",
      observation_date: "2026-08-01",
      units: "Percent",
      previous_value: null,
      new_value: 4.1,
      delta: null,
      ...payload,
    },
  } as unknown as IntelligenceObject;
}

function respond(items: IntelligenceObject[]) {
  vi.mocked(api.listHomepageIntelligence).mockResolvedValue({
    items,
    total: items.length,
    limit: 100,
    offset: 0,
    contract_version: "intelligence_v1",
  } as never);
}

function renderPage() {
  return render(
    <MemoryRouter>
      <RevisionsPage />
    </MemoryRouter>,
  );
}

beforeEach(() => respond([]));
afterEach(() => vi.clearAllMocks());

describe("the real, empty state", () => {
  it("says MacroChipz is watching, not that the feature is broken", async () => {
    renderPage();
    expect(await screen.findByRole("heading", { name: "MacroChipz is watching for revisions" })).toBeInTheDocument();
  });

  it("renders no revision at all", async () => {
    // Today's actual data: 358 first observations, zero revisions.
    respond([observation({ change_type: "NEW", revision_knowledge: "FIRST_OBSERVATION" })]);
    renderPage();
    await screen.findByRole("heading", { name: "MacroChipz is watching for revisions" });
    expect(screen.queryByText("Originally reported")).not.toBeInTheDocument();
    expect(screen.queryByText("Revised to")).not.toBeInTheDocument();
  });

  it("never fabricates a sample revision to look populated", async () => {
    const { container } = renderPage();
    await screen.findByRole("heading", { name: "MacroChipz is watching for revisions" });
    const text = (container.textContent ?? "").toLowerCase();
    for (const word of ["example", "sample", "for instance", "e.g.", "demo", "placeholder", "3.1%"]) {
      expect(text, word).not.toContain(word);
    }
  });

  it("teaches what will be shown when one arrives", async () => {
    renderPage();
    await screen.findByRole("heading", { name: "MacroChipz is watching for revisions" });
    expect(screen.getByText(/What the number was when MacroChipz first recorded it/)).toBeInTheDocument();
    expect(screen.getByText(/whether MacroChipz’s own conclusion changed/i)).toBeInTheDocument();
  });

  it("still routes into the live economy", async () => {
    renderPage();
    await screen.findByRole("heading", { name: "MacroChipz is watching for revisions" });
    for (const world of ECONOMIC_WORLDS) {
      expect(screen.getByRole("link", { name: `${world.label} →` })).toHaveAttribute("href", world.route);
    }
  });
});

describe("the historical boundary (#43 §18)", () => {
  it("explains why older revisions cannot be shown", async () => {
    renderPage();
    await screen.findByRole("heading", { name: "MacroChipz is watching for revisions" });
    expect(screen.getByText("Why older revisions cannot be shown")).toBeInTheDocument();
    expect(screen.getByText(/imported as a starting baseline/)).toBeInTheDocument();
    expect(screen.getByText(/does not present them as originals/)).toBeInTheDocument();
  });

  it("never claims MacroChipz tracked vintages before point-in-time history began", async () => {
    const { container } = renderPage();
    await screen.findByRole("heading", { name: "MacroChipz is watching for revisions" });
    const text = (container.textContent ?? "").toLowerCase();
    for (const claim of ["always tracked", "complete history", "every revision since", "full revision history"]) {
      expect(text, claim).not.toContain(claim);
    }
  });

  it("states no boundary DATE, because the stored one is a migration timestamp", async () => {
    const { container } = renderPage();
    await screen.findByRole("heading", { name: "MacroChipz is watching for revisions" });
    // A migration timestamp dressed as an economic boundary would be
    // exactly the kind of false precision #43 forbids.
    expect(container.textContent).not.toMatch(/\b20\d\d-\d\d-\d\d\b/);
  });
});

describe("education", () => {
  it("explains revisions generically, without blaming a provider", async () => {
    renderPage();
    await screen.findByRole("heading", { name: "Why economic data gets revised" });
    expect(screen.getByText(/does not automatically mean the first number/i)).toBeInTheDocument();
  });

  it("claims no specific agency's revision policy", async () => {
    const { container } = renderPage();
    await screen.findByRole("heading", { name: "Why economic data gets revised" });
    const text = container.textContent ?? "";
    // MacroChipz holds no first-party documentation of any provider's
    // revision mechanism, so naming one would be inventing source
    // knowledge.
    for (const agency of ["BLS", "BEA", "Bureau of Labor", "Bureau of Economic"]) {
      expect(text, agency).not.toContain(agency);
    }
  });

  it("asserts no cause for any particular revision", async () => {
    const { container } = renderPage();
    await screen.findByRole("heading", { name: "Why economic data gets revised" });
    expect(container.textContent).toMatch(/does not claim to know why a provider revised/i);
  });
});

describe("a populated revision, when one finally exists", () => {
  const GENUINE = observation({
    change_type: "REVISED",
    revision_knowledge: "PROSPECTIVE_REVISION",
    original_value_known: true,
    previous_value: 3.1,
    new_value: 3.0,
    delta: -0.1,
  });

  it("shows originally reported and revised to", async () => {
    respond([GENUINE]);
    renderPage();
    expect(await screen.findByText("Originally reported")).toBeInTheDocument();
    expect(screen.getByText("Revised to")).toBeInTheDocument();
    expect(screen.getByText("3.1")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("states the direction in words, never by colour or arrow alone", async () => {
    respond([GENUINE]);
    renderPage();
    expect(await screen.findByText(/Down 0\.10 percentage points/)).toBeInTheDocument();
  });

  it("uses no good/bad styling for the direction", async () => {
    respond([GENUINE]);
    const { container } = renderPage();
    await screen.findByText("Originally reported");
    const markup = container.innerHTML;
    // A lower number is not inherently good or bad.
    for (const token of ["state-", "feedback-", "text-red", "text-green", "positive", "negative", "danger", "success"]) {
      expect(markup, token).not.toContain(token);
    }
  });

  it("links to the permanent object rather than inventing a second detail URL", async () => {
    respond([GENUINE]);
    renderPage();
    const link = await screen.findByRole("link", { name: /Show the evidence/ });
    expect(link).toHaveAttribute("href", `/intelligence/${encodeURIComponent(GENUINE.id)}`);
  });

  it("shows 'Not recorded' rather than a baseline dressed as an original", async () => {
    respond([
      observation({
        change_type: "REVISED",
        revision_knowledge: "PROSPECTIVE_REVISION",
        original_value_known: false,
        previous_value: 3.1,
        new_value: 3.0,
        delta: -0.1,
      }),
    ]);
    renderPage();
    expect(await screen.findByText("Not recorded")).toBeInTheDocument();
    const originals = screen.queryAllByText("3.1");
    expect(originals).toHaveLength(0);
  });
});

describe("Revision Intelligence is not a world", () => {
  it("is absent from the world registry", () => {
    // The assertion is that Revisions is not a WORLD -- deliberately
    // not a count of worlds, which changes whenever a real world
    // acquires data (Housing did, in #45) and which would make this
    // test fail for a reason that has nothing to do with revisions.
    const text = JSON.stringify(ECONOMIC_WORLDS).toLowerCase();
    expect(text).not.toContain("revision");
    expect(ECONOMIC_WORLDS.some((entry) => entry.route === "/revisions")).toBe(false);
  });
});
