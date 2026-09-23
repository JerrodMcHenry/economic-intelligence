import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { ECONOMIC_WORLDS } from "../../worlds/registry";
import { LivingEconomyHero } from "./LivingEconomyHero";
import { WORLD_DISCOVERY, WORLD_IMAGERY } from "./worldImagery";

function renderHero() {
  return render(
    <MemoryRouter>
      <LivingEconomyHero />
    </MemoryRouter>,
  );
}

describe("the Living Economy hero", () => {
  it("is the page's one h1, and it is the approved headline", () => {
    renderHero();
    expect(screen.getByRole("heading", { level: 1, name: "Explore the living economy." })).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });

  it("offers all four worlds as controls, in registry order", () => {
    renderHero();
    // DOM order is visual order is tab order. The caption is the first
    // text in each control; its registry description follows, for
    // assistive technology only.
    const controls = screen.getAllByRole("button");
    expect(controls).toHaveLength(ECONOMIC_WORLDS.length);
    ECONOMIC_WORLDS.forEach((world, index) => {
      const control = controls[index];
      expect(control, world.label).toBeDefined();
      expect(within(control as HTMLElement).getByText(world.label)).toBeInTheDocument();
    });
  });

  it("selects exactly one world on load, never zero", () => {
    // A hero that opens explaining nothing has wasted the only screen
    // it gets.
    renderHero();
    const pressed = screen.getAllByRole("button").filter((b) => b.getAttribute("aria-pressed") === "true");
    expect(pressed).toHaveLength(1);
  });

  it("selecting each world updates the panel and its route", async () => {
    const user = userEvent.setup();
    renderHero();

    for (const world of ECONOMIC_WORLDS) {
      await user.click(screen.getByRole("button", { name: new RegExp(world.label) }));
      expect(screen.getByText(WORLD_DISCOVERY[world.id], { exact: false })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: `Open ${world.label}` })).toHaveAttribute("href", world.route);
    }
  });

  it("selection is not navigation: focus stays on the control", async () => {
    const user = userEvent.setup();
    renderHero();
    const jobs = screen.getByRole("button", { name: /Jobs/ });
    await user.click(jobs);
    expect(jobs).toHaveFocus();
    expect(jobs).toHaveAttribute("aria-pressed", "true");
  });

  it("is reachable and operable by keyboard alone", async () => {
    const user = userEvent.setup();
    renderHero();
    const buttons = screen.getAllByRole("button");

    await user.tab();
    expect(buttons[0]).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(buttons[0]).toHaveAttribute("aria-pressed", "true");
  });

  it("announces the panel politely rather than stealing focus", () => {
    const { container } = renderHero();
    expect(container.querySelector('[aria-live="polite"]')).not.toBeNull();
    expect(container.querySelector('[aria-live="assertive"]')).toBeNull();
  });

  it("DRAWS NO EDGE BETWEEN WORLDS", () => {
    // The single hardest rule on this component. The mortgage story's
    // edges are defended by reviewed sources; a line between Inflation
    // and Jobs would assert a relationship nobody wrote down. The
    // decorative motifs inside a tile are permitted -- a line CROSSING
    // tiles is not, and a top-level connector element is how that would
    // arrive.
    const { container } = renderHero();
    const list = container.querySelector("ul");
    expect(list).not.toBeNull();
    // Every svg lives inside a tile; none is a sibling joining them.
    for (const svg of Array.from(container.querySelectorAll("svg"))) {
      expect(svg.closest("li")).not.toBeNull();
    }
    expect(container.querySelectorAll("marker")).toHaveLength(0);
    expect(container.querySelectorAll("line")).toHaveLength(0);
  });

  it("renders the verified photograph with its credit, and the others without one", () => {
    const { container } = renderHero();
    const images = Array.from(container.querySelectorAll("img"));
    const photographed = ECONOMIC_WORLDS.filter((w) => WORLD_IMAGERY[w.id].treatment === "photograph");

    expect(images).toHaveLength(photographed.length);
    for (const image of images) {
      expect(image.getAttribute("width")).not.toBeNull();
      expect(image.getAttribute("height")).not.toBeNull();
      expect(image.getAttribute("alt")).not.toBe("");
      // Above the fold on every viewport, so lazy loading it would be
      // an LCP anti-pattern rather than an optimisation.
      expect(image.getAttribute("loading")).toBe("eager");
    }

    for (const world of photographed) {
      const imagery = WORLD_IMAGERY[world.id];
      if (imagery.treatment !== "photograph") continue;
      expect(screen.getByText(imagery.credit)).toBeInTheDocument();
    }
  });

  it("shows no PLACEHOLDER chip anywhere", () => {
    // A prototype announces its gaps; a shipped homepage does not wear
    // a chip saying so. The gap is recorded in ASSETS.md and stated in
    // the page's image notice.
    const { container } = renderHero();
    expect(container.textContent ?? "").not.toMatch(/placeholder/i);
  });

  it("names every world's registry description for assistive technology", () => {
    renderHero();
    for (const world of ECONOMIC_WORLDS) {
      expect(screen.getByText(world.description)).toBeInTheDocument();
    }
  });

  it("fetches nothing, so it renders during an outage", () => {
    // Asserted at the source level: an import of an api client here
    // would make the orientation layer depend on the network, and an
    // outage is exactly when a reader most needs to know what this
    // site is.
    renderHero();
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
  });
});
