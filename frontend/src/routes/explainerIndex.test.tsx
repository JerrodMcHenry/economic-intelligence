/**
 * The explainer index (Increment #45B).
 *
 * #45A found every explainer reachable only from a world page, so a
 * reader entering at `/` never met educational content. This page is
 * the collection's canonical home — and the tests below hold it to
 * being a curated index rather than a recommender.
 */
import { render, screen, within } from "@testing-library/react";
import { createRoutesStub } from "react-router";
import { describe, expect, it } from "vitest";

import { EXPLAINERS } from "../explainers/registry";
import { ThemeProvider } from "../theme/ThemeProvider";
import { ECONOMIC_WORLDS } from "../worlds/registry";
import ExplainerIndexRoute, { meta } from "./explainerIndex";

/**
 * A framework-route harness, matching `explainer.test.tsx`.
 * `createRoutesStub` from `react-router` -- not `MemoryRouter` from
 * `react-router-dom` -- because this route module imports `Link` from
 * the framework package, and the two carry separate contexts.
 */
function renderIndex() {
  const Stub = createRoutesStub([{ path: "/explain", Component: ExplainerIndexRoute }]);
  return render(
    <ThemeProvider>
      <Stub initialEntries={["/explain"]} />
    </ThemeProvider>,
  );
}

describe("completeness", () => {
  it("lists every explainer in the registry", () => {
    renderIndex();

    for (const explainer of EXPLAINERS) {
      const link = screen.getByRole("link", { name: explainer.question });
      expect(link).toHaveAttribute("href", `/explain/${explainer.slug}`);
    }
  });

  it("renders one link per explainer, with no duplicates", () => {
    const { container } = renderIndex();
    const explainerLinks = [...container.querySelectorAll('a[href^="/explain/"]')];
    expect(explainerLinks).toHaveLength(EXPLAINERS.length);
  });

  it("shows each explainer's one-sentence answer, so the page is useful without clicking", () => {
    renderIndex();
    for (const explainer of EXPLAINERS) {
      expect(screen.getByText(explainer.answer)).toBeInTheDocument();
    }
  });
});

describe("question-led, and curated", () => {
  it("renders the QUESTION rather than a topic label", () => {
    // "The Fed and mortgage rates" is a filing category. "Wait, the Fed
    // doesn't set mortgage rates?" is a reason to click, and it is what
    // the product's strongest asset actually is.
    renderIndex();
    expect(screen.getByRole("link", { name: "Wait, the Fed doesn't set mortgage rates?" })).toBeInTheDocument();
  });

  it("groups by the curated world each explainer declares", () => {
    renderIndex();
    for (const world of ECONOMIC_WORLDS) {
      const hasAny = EXPLAINERS.some((explainer) => explainer.worlds?.includes(world.id));
      if (!hasAny) continue;
      expect(screen.getByRole("heading", { name: world.label, level: 2 })).toBeInTheDocument();
    }
  });

  it("links each group to the live data behind it", () => {
    renderIndex();
    const rates = screen.getByRole("heading", { name: "Rates", level: 2 }).closest("section") as HTMLElement;
    expect(within(rates).getByRole("link", { name: /See the rates data/ })).toHaveAttribute("href", "/rates");
  });

  it("implements no ranking, scoring, popularity or personalisation", () => {
    // The same rule the registry's own `related` field holds itself to.
    const { container } = renderIndex();
    const text = (container.textContent ?? "").toLowerCase();
    // Whole words / whole phrases. "top " matched "what a lender earns
    // on TOP of rising prices" -- the same substring false positive
    // #45 and #45A both hit, and the correction is the same: be
    // precise rather than broad.
    for (const forbidden of ["most popular", "trending", "recommended for", "picked for you", "top picks"]) {
      expect(text, forbidden).not.toContain(forbidden);
    }
  });
});

describe("what the page claims", () => {
  it("states that these are general, not a claim about a month", () => {
    const { container } = renderIndex();
    expect(container.textContent).toMatch(/not a forecast/i);
    expect(container.textContent).toMatch(/do not describe any particular\s+month/i);
  });

  it("makes no economic claim of its own", () => {
    const { container } = renderIndex();
    const text = (container.textContent ?? "").toLowerCase();
    for (const forbidden of ["the economy is", "cooling", "heating", "recession", "soft landing"]) {
      expect(text, forbidden).not.toContain(forbidden);
    }
  });
});

describe("metadata", () => {
  it("has a real title and description for crawlers and unfurls", () => {
    const tags = meta();
    const title = tags.find((tag) => "title" in tag);
    const description = tags.find((tag) => tag.name === "description");

    expect(title?.title).toContain("Questions about the economy");
    expect(description?.content).toBeTruthy();
    expect((description?.content ?? "").length).toBeGreaterThan(60);
  });

  it("emits no absolute URL when no site origin is configured", () => {
    // #40's rule: a guessed canonical tells a crawler the real page
    // lives somewhere it does not.
    const tags = meta();
    const canonical = tags.find((tag) => tag.rel === "canonical");
    expect(canonical).toBeUndefined();
  });
});

describe("accessibility", () => {
  it("uses one h1 and section headings beneath it", () => {
    renderIndex();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getAllByRole("heading", { level: 2 }).length).toBeGreaterThan(0);
  });

  it("renders each group as a list", () => {
    renderIndex();
    expect(screen.getAllByRole("list").length).toBeGreaterThan(0);
  });
});
