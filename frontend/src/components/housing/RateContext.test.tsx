/**
 * The rate-context section (Increment #45).
 *
 * These assertions are about what the section SAYS, checked against
 * rendered text rather than against source. A substring scan cannot
 * tell "there is no estimated mortgage rate here" — the disclaimer this
 * section exists to make — from an estimated mortgage rate, so the
 * static guard in `src/test/no-housing-derivation.test.ts` covers the
 * structural half (no rates import, no fetch) and the claims are
 * checked here where a sentence can be read in context.
 */
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { RateContext } from "./RateContext";

function renderSection() {
  return render(
    <MemoryRouter>
      <RateContext />
    </MemoryRouter>,
  );
}

describe("what it says about mortgage rates", () => {
  it("states plainly that MacroChipz does not track them", () => {
    const { container } = renderSection();
    expect(container.textContent).toMatch(/MacroChipz does not track mortgage rates/);
  });

  it("names the Treasury yield as what it is", () => {
    const { container } = renderSection();
    expect(container.textContent).toMatch(/Treasury yields/);
    expect(container.textContent).toMatch(/what it costs the federal government to borrow/i);
  });

  it("states that no mortgage rate is estimated and no spread is calculated", () => {
    const { container } = renderSection();
    const text = container.textContent ?? "";
    expect(text).toMatch(/no estimated mortgage rate here/i);
    expect(text).toMatch(/no gap between Treasury yields and mortgage rates is\s+calculated/i);
  });

  it("describes the relationship as loose rather than mechanical", () => {
    const { container } = renderSection();
    expect(container.textContent).toMatch(/relationship is loose and changes over time/i);
  });
});

describe("what it refuses to show", () => {
  it("renders no figure at all", () => {
    // The whole design decision, asserted: two numbers side by side on
    // one page read as connected, and MacroChipz has measured nothing
    // about the connection between housing and rates.
    const { container } = renderSection();
    expect(container.textContent ?? "").not.toMatch(/\d/);
  });

  it("never calls a Treasury yield a mortgage rate", () => {
    const { container } = renderSection();
    const text = (container.textContent ?? "").toLowerCase();
    for (const forbidden of [
      "treasury mortgage rate",
      "mortgage rate of",
      "the mortgage rate is",
      "home loan rate",
      "borrowing rate is",
    ]) {
      expect(text, forbidden).not.toContain(forbidden);
    }
  });

  it("never implies the Fed sets mortgage rates", () => {
    const { container } = renderSection();
    const text = (container.textContent ?? "").toLowerCase();
    for (const forbidden of ["the fed sets", "the fed decides", "when the fed cuts", "fed lowers your"]) {
      expect(text, forbidden).not.toContain(forbidden);
    }
  });
});

describe("where it sends the reader", () => {
  it("links to the Rates world", () => {
    renderSection();
    expect(screen.getByRole("link", { name: /Treasury yields MacroChipz does track/i })).toHaveAttribute(
      "href",
      "/rates",
    );
  });

  it("links to the Fed-and-mortgage-rates explainer", () => {
    renderSection();
    expect(screen.getByRole("link", { name: /the Fed doesn.t set mortgage rates/i })).toHaveAttribute(
      "href",
      "/explain/fed-and-mortgage-rates",
    );
  });
});

describe("accessibility", () => {
  it("is a labelled region", () => {
    renderSection();
    expect(screen.getByRole("region", { name: /What about mortgage rates/i })).toBeInTheDocument();
  });
});
