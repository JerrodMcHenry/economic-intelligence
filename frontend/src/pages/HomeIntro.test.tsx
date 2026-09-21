import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { AppShell } from "../layouts/AppShell";
import { HomeIntroPage } from "./HomeIntro";
import { ThemeProvider } from "../theme/ThemeProvider";

/**
 * Rendered DIRECTLY rather than through `<App/>`, because #41 moved the
 * live economic surface to `/` and this page is no longer mounted on a
 * route. It is kept, and kept under test, because it is the only place
 * that explains what MacroChipz is and why it can be trusted -- content
 * #42 will want when it designs the real homepage. An untested page
 * rots; a tested one waits.
 */
function renderHome() {
  return render(
    // `ThemeProvider` lives in `root.tsx` in the real application
    // (#40). `AppShell` supplies the `<main>` landmark these tests
    // query through.
    <MemoryRouter initialEntries={["/"]}>
      <ThemeProvider>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<HomeIntroPage />} />
          </Route>
        </Routes>
      </ThemeProvider>
    </MemoryRouter>,
  );
}

const main = () => screen.getByRole("main");

describe("HomeIntroPage", () => {
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

  it("routes the primary call to action to the live economic surface", async () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    renderHome();
    const [primaryCta] = within(main()).getAllByRole("link", { name: /See the economy right now/ });
    expect(primaryCta).toHaveAttribute("href", "/");
    // The destination itself is covered by pages/Home.test.tsx; this
    // harness mounts only the introduction.

    await userEvent.setup().click(primaryCta!);
  });

  it("offers no call to action other than Home and the covered worlds", () => {
    renderHome();
    const destinations = new Set(within(main()).getAllByRole("link").map((link) => link.getAttribute("href")));
    expect(destinations).toEqual(new Set(["/", "/inflation", "/jobs"]));
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

  it("lists only the implemented worlds, Inflation and Jobs, as current coverage", () => {
    renderHome();
    const section = screen.getByRole("region", { name: "Two economic domains, analyzed in depth" });
    const domains = within(section).getAllByRole("heading", { level: 3 }).map((heading) => heading.textContent);
    expect(domains).toEqual(["Inflation", "Jobs"]);
    expect(within(section).getByRole("link", { name: /Open Inflation/ })).toHaveAttribute("href", "/inflation");
    expect(within(section).getByRole("link", { name: /Open Jobs/ })).toHaveAttribute("href", "/jobs");
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
