import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import App from "../App";

function renderHome() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <App />
    </MemoryRouter>,
  );
}

const main = () => screen.getByRole("main");

describe("HomePage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("presents MacroChipz, the Economic Intelligence category, and the positioning line", () => {
    renderHome();
    expect(within(main()).getByText("MacroChipz")).toBeInTheDocument();
    expect(within(main()).getByText("Economic Intelligence")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 1, name: "Know what changed in the economy — and prove why." }),
    ).toBeInTheDocument();
    expect(
      within(main()).getByText(/turns trusted macroeconomic data into reproducible economic analysis/),
    ).toBeInTheDocument();
  });

  it("is static: renders fully without calling the backend", () => {
    const fetchSpy = vi.fn(() => new Promise(() => {}));
    vi.stubGlobal("fetch", fetchSpy);
    renderHome();
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(within(main()).queryByRole("status")).not.toBeInTheDocument();
    expect(within(main()).queryByRole("alert")).not.toBeInTheDocument();
  });

  it("routes the primary call to action to the Overview", async () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    renderHome();
    const [primaryCta] = within(main()).getAllByRole("link", { name: /Explore the Overview/ });
    expect(primaryCta).toHaveAttribute("href", "/overview");

    await userEvent.setup().click(primaryCta!);
    expect(screen.getByRole("heading", { level: 1, name: "Economic Overview" })).toBeInTheDocument();
  });

  it("offers no call to action other than the Overview and the covered domains", () => {
    renderHome();
    const destinations = new Set(within(main()).getAllByRole("link").map((link) => link.getAttribute("href")));
    expect(destinations).toEqual(new Set(["/overview", "/inflation", "/labor"]));
  });

  it("frames the product around the three core questions", () => {
    renderHome();
    const questions = within(main()).getAllByRole("heading", { level: 3 }).map((heading) => heading.textContent);
    expect(questions.slice(0, 3)).toEqual(["What is happening?", "What changed?", "Why?"]);
  });

  it("shows how it works as the ordered data-to-evidence flow", () => {
    renderHome();
    const section = screen.getByRole("region", { name: "From source data to a conclusion you can check" });
    const steps = within(section).getAllByRole("heading", { level: 3 }).map((heading) => heading.textContent);
    expect(steps).toEqual([
      "Trusted economic data",
      "Deterministic analysis",
      "Economic state",
      "Change detection",
      "Evidence",
    ]);
    expect(within(section).getByText(/not from a black-box model/)).toBeInTheDocument();
  });

  it("explains the trust model, with AI as interpretive rather than authoritative", () => {
    renderHome();
    const section = screen.getByRole("region", {
      name: "Facts are sourced. Calculations are deterministic. AI is interpretive.",
    });
    const principles = within(section).getAllByRole("heading", { level: 3 }).map((heading) => heading.textContent);
    expect(principles).toEqual([
      "Sourced economic data",
      "Deterministic calculations",
      "Versioned methodologies",
      "Reproducible conclusions",
      "Visible supporting evidence",
      "AI is interpretive, not authoritative",
    ]);
    expect(within(section).getByText(/never determines, a canonical conclusion/)).toBeInTheDocument();
  });

  it("lists only the implemented domains, Inflation and Labor, as current coverage", () => {
    renderHome();
    const section = screen.getByRole("region", { name: "Two economic domains, analyzed in depth" });
    const domains = within(section).getAllByRole("heading", { level: 3 }).map((heading) => heading.textContent);
    expect(domains).toEqual(["Inflation", "Labor"]);
    expect(within(section).getByRole("link", { name: /Open Inflation/ })).toHaveAttribute("href", "/inflation");
    expect(within(section).getByRole("link", { name: /Open Labor/ })).toHaveAttribute("href", "/labor");
  });

  it("makes no unfinished domain or unsupported monitoring claim", () => {
    renderHome();
    const text = main().textContent ?? "";
    for (const unavailable of ["Growth", "Housing", "Markets", "Bonds", "Crypto", "Stocks", "Watchlist"]) {
      expect(text).not.toContain(unavailable);
    }
    // Scheduled maintenance is designed but not activated in production
    // (#26E / ADR-029), so Home must not claim ongoing automatic monitoring.
    expect(text).not.toMatch(/continuous|automatic|real[- ]time|always up to date|24\/7/i);
  });

  it("uses one h1 and a named region for each content section", () => {
    renderHome();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(within(main()).getAllByRole("region").length).toBeGreaterThanOrEqual(6);
  });
});
