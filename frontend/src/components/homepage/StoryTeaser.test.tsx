import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { NETWORK_EDGES, NETWORK_NODES } from "../../explainers/rateNetwork";
import { StoryTeaser } from "./StoryTeaser";

function renderTeaser() {
  return render(
    <MemoryRouter>
      <StoryTeaser />
    </MemoryRouter>,
  );
}

describe("the mobile story teaser (#48B)", () => {
  it("is one link to the existing story route", () => {
    const { container } = renderTeaser();
    const links = container.querySelectorAll("a");
    expect(links).toHaveLength(1);
    expect(links[0]).toHaveAttribute("href", "/story/fed-and-mortgage-rates");
  });

  it("uses the reviewed question verbatim", () => {
    renderTeaser();
    expect(screen.getByText("Wait, the Fed doesn't set mortgage rates?")).toBeInTheDocument();
  });

  it("counts from the registry rather than from a literal", () => {
    // The desktop preview dropped its count sentence because the
    // diagram carries it. There is no diagram here, so the count is
    // stated -- and derived, so a seventh actor changes it.
    renderTeaser();
    const sets = NETWORK_EDGES.filter((edge) => edge.kind === "sets").length;
    expect(
      screen.getByText(`${NETWORK_NODES.length} actors, ${sets} of them set by anyone. Tap through the network.`),
    ).toBeInTheDocument();
  });

  it("draws the registry's own edges, and asserts nothing new", () => {
    // The glyph is decorative and aria-hidden, which is not a licence
    // to draw a shape the model does not have.
    const { container } = renderTeaser();
    const svg = container.querySelector("svg");
    expect(svg?.getAttribute("aria-hidden")).toBe("true");
    expect(svg?.querySelectorAll("path")).toHaveLength(NETWORK_EDGES.length);
    // Two circles per node: a halo and a core, drawn in that order.
    // A halo painted over an edge swallows it -- the #46E layering
    // defect -- so the order is part of the assertion, not incidental.
    expect(svg?.querySelectorAll("circle")).toHaveLength(NETWORK_NODES.length * 2);
    const circles = Array.from(svg?.querySelectorAll("circle") ?? []);
    const firstCore = circles.findIndex((c) => Number(c.getAttribute("r")) < 8);
    expect(firstCore).toBe(NETWORK_NODES.length);
  });

  it("IS ONE TARGET: everything inside it is a span (#48C)", () => {
    // The whole strip is clickable and there is exactly one thing to
    // tab to, so the global :focus-visible outline wraps the entire
    // card and no part of it is a dead area under a thumb.
    const { container } = renderTeaser();
    const link = container.querySelector("a") as HTMLElement;
    expect(container.querySelectorAll("a, button, input, [tabindex]")).toHaveLength(1);
    // Nothing inside steals the accessible name or the pointer.
    for (const decorative of Array.from(link.querySelectorAll(".lx-teaser-frame, .lx-teaser-go"))) {
      expect(decorative.tagName).toBe("SPAN");
    }
    expect(link.querySelector(".lx-teaser-go")?.getAttribute("aria-hidden")).toBe("true");
  });

  it("frames the network rather than using it as a bare icon", () => {
    // #48C: the point of the frame is that it reads as a thumbnail of
    // somewhere you can go, not as decoration on a navigation row.
    const { container } = renderTeaser();
    const frame = container.querySelector(".lx-teaser-frame");
    expect(frame).not.toBeNull();
    expect(frame?.querySelector("svg")).not.toBeNull();
  });

  it("is hidden from lg, where the full featured section takes over", () => {
    // Exactly one invitation at every width. Two on one screen would
    // be worse than the problem this solves.
    const { container } = renderTeaser();
    expect(container.querySelector("a")?.className).toContain("lg:hidden");
  });
});
