import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { NETWORK_EDGES, NETWORK_NODES } from "../../explainers/rateNetwork";
import { FeaturedStory } from "./FeaturedStory";
import { describeNetwork } from "./networkPreviewDescription";

function renderFeatured() {
  return render(
    <MemoryRouter>
      <FeaturedStory />
    </MemoryRouter>,
  );
}

describe("the featured story band", () => {
  it("leads with the question a reader arrives searching for", () => {
    renderFeatured();
    expect(screen.getByRole("heading", { name: "Wait, the Fed doesn't set mortgage rates?" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open the story" })).toHaveAttribute(
      "href",
      "/story/fed-and-mortgage-rates",
    );
  });

  it("lets the diagram carry the count instead of restating it in prose", () => {
    // #48B: "Six actors sit between... only two of them are set by
    // anyone" was registry-derived and true, and redundant beside a
    // diagram naming six actors and a list showing exactly two being
    // set. The FACT is still asserted -- against the registry and
    // against what is rendered -- only the sentence is gone.
    const { container } = renderFeatured();
    expect(NETWORK_NODES).toHaveLength(6);
    expect(NETWORK_EDGES.filter((edge) => edge.kind === "sets")).toHaveLength(2);

    const figure = container.querySelector('[role="img"]') as HTMLElement;
    expect(within(figure).getAllByText(/\S/).length).toBeGreaterThanOrEqual(NETWORK_NODES.length);
    expect(container.querySelectorAll("dl > div")).toHaveLength(2);
    expect(screen.queryByText(/actors sit between/)).not.toBeInTheDocument();
  });

  it("draws exactly the registry's edges, and invents none", () => {
    const { container } = renderFeatured();
    const paths = Array.from(container.querySelectorAll("path"));
    // `sets` edges are drawn twice (a halo and a core); `influences`
    // once. Any other count means an edge was added or dropped.
    const sets = NETWORK_EDGES.filter((edge) => edge.kind === "sets").length;
    const influences = NETWORK_EDGES.filter((edge) => edge.kind === "influences").length;
    expect(paths).toHaveLength(sets * 2 + influences);
  });

  it("NEVER JOINS THE FED FUNDS RATE TO TREASURY YIELDS", () => {
    // The absence of that edge is the entire point of the story: the
    // Fed's overnight rate does not reach into the Treasury market as
    // a chain. A "tidier" preview that connected them would assert the
    // misconception the story exists to correct.
    const direct = NETWORK_EDGES.some(
      (edge) =>
        (edge.from === "fed-funds" && edge.to === "treasury") || (edge.from === "treasury" && edge.to === "fed-funds"),
    );
    expect(direct).toBe(false);

    const { container } = renderFeatured();
    const fedFunds = NETWORK_NODES.find((n) => n.id === "fed-funds")!;
    const treasury = NETWORK_NODES.find((n) => n.id === "treasury")!;
    const joining = `M ${fedFunds.x} ${fedFunds.y} L ${treasury.x} ${treasury.y}`;
    for (const path of Array.from(container.querySelectorAll("path"))) {
      expect(path.getAttribute("d")).not.toBe(joining);
    }
  });

  it("describes the diagram in words, because its labels are not drawn", () => {
    const description = describeNetwork();
    for (const node of NETWORK_NODES) expect(description).toContain(node.label);
    expect(description).toContain("is set by");
    // The distinction between setting and feeding in must survive into
    // the accessible description, not only the stroke pattern.
    expect(description).toMatch(/feeding into another, not one setting another/);
  });

  it("NAMES EVERY ACTOR, so the preview is readable without clicking", () => {
    // It first shipped as six unlabelled dots and a legend, which is
    // not a preview of anything. The names are HTML rather than SVG
    // text: a `font-size` inside a `viewBox` shrinks with the box, and
    // #46D already shipped one diagram whose 48-unit targets rendered
    // at 41px.
    const { container } = renderFeatured();
    const figure = container.querySelector('[role="img"]') as HTMLElement;
    for (const node of NETWORK_NODES) {
      expect(within(figure).getByText(node.chip), node.id).toBeInTheDocument();
    }
  });

  it("states who sets the two that anyone sets, composed from the registry", () => {
    const { container } = renderFeatured();
    const list = container.querySelector("dl") as HTMLElement;
    for (const edge of NETWORK_EDGES.filter((e) => e.kind === "sets")) {
      const target = NETWORK_NODES.find((n) => n.id === edge.to)!;
      // Two of the six names appear twice -- once labelling the dot,
      // once explaining the solid edge. That is the repetition doing
      // work, so the assertion is scoped rather than relaxed.
      expect(within(list).getByText(target.label)).toBeInTheDocument();
      // `setBy` verbatim -- never a sentence written in this component.
      expect(within(list).getByText(`set by ${target.setBy}`)).toBeInTheDocument();
    }
  });

  it("carries one accessible name and hides the decorative layers from it", () => {
    // Six names with no relationships is worse than the description,
    // so the svg and the label layer are both aria-hidden and the
    // figure speaks once.
    const { container } = renderFeatured();
    const figure = container.querySelector('[role="img"]');
    expect(figure?.getAttribute("aria-label")).toBe(describeNetwork());
    expect(figure?.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
    for (const label of Array.from(figure?.querySelectorAll(":scope > span") ?? [])) {
      expect(label.getAttribute("aria-hidden")).toBe("true");
    }
  });

  it("puts no text inside the svg", () => {
    // SVG units are not CSS pixels. #46D shipped 48-unit tap targets
    // that rendered at 41px; text has the same failure at preview size.
    const { container } = renderFeatured();
    expect(container.querySelectorAll("svg text")).toHaveLength(0);
  });

  it("uses userSpaceOnUse for the edge gradient", () => {
    // `objectBoundingBox` gives a perfectly vertical line a zero-width
    // box, and the gradient paints nothing. That defect shipped twice.
    const { container } = renderFeatured();
    const gradient = container.querySelector("linearGradient");
    expect(gradient?.getAttribute("gradientUnits")).toBe("userSpaceOnUse");
  });
});
