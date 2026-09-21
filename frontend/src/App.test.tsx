import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import App from "./App";
import { ThemeProvider } from "./theme/ThemeProvider";

function renderAt(initialRoute: string) {
  return render(
    // `ThemeProvider` lives in `root.tsx` in the real application
    // (#40). Supplied here so this harness matches production.
    <MemoryRouter initialEntries={[initialRoute]}>
      <ThemeProvider>
        <App />
      </ThemeProvider>
    </MemoryRouter>,
  );
}

describe("App", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders", () => {
    // The Overview route now fetches real data (Increment #19A) --
    // stubbed to never resolve, since only the shell landmarks are
    // under test here (see pages/Overview.test.tsx for data behavior).
    // Overview's own page <header> (nested in <main>, matching the
    // same per-page-header convention Inflation.tsx/Releases.tsx
    // already use) is also picked up as an additional "banner" by this
    // testing environment's role computation -- getAllByRole scopes to
    // the outer, site-wide one deliberately, first in document order.
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    renderAt("/overview");
    expect(screen.getAllByRole("banner")[0]).toBeInTheDocument();
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(screen.getByRole("contentinfo")).toBeInTheDocument();
  });

  it("shows the MacroChipz brand in the header, linking Home, with Economic Intelligence as its category", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    renderAt("/overview");
    // Increment #27B: MacroChipz is the public brand; "Economic
    // Intelligence" remains the category descriptor beside it.
    const header = screen.getAllByRole("banner")[0]!;
    const brandLink = within(header).getByRole("link", { name: /MacroChipz/ });
    expect(brandLink).toHaveAttribute("href", "/");
    expect(brandLink).toHaveTextContent("MacroChipz");
    expect(brandLink).toHaveTextContent("Economic Intelligence");
  });

  it("exposes accessible, keyboard-reachable primary navigation", async () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    renderAt("/");
    const nav = screen.getByRole("navigation", { name: "Primary" });
    const homeLink = within(nav).getByRole("link", { name: "Home" });

    expect(homeLink).toHaveAttribute("href", "/");
    expect(within(nav).getByRole("link", { name: "Inflation" })).toHaveAttribute("href", "/inflation");
    expect(within(nav).getByRole("link", { name: "Jobs" })).toHaveAttribute("href", "/jobs");
    expect(within(nav).getByRole("link", { name: "Rates" })).toHaveAttribute("href", "/rates");
    expect(within(nav).getByRole("link", { name: "Calendar" })).toHaveAttribute("href", "/calendar");

    // The consumer IA (#41): the economy, plus the two product surfaces
    // that are not worlds. "Overview" named our architecture rather
    // than a part of the economy and its content is now simply what `/`
    // is; "Labor" and "Releases" were the engineering domain's words.
    // Still no placeholders -- Housing arrives with #45, not before.
    const navOrder = within(nav).getAllByRole("link").map((link) => link.textContent);
    expect(navOrder).toEqual(["Home", "Inflation", "Jobs", "Rates", "Calendar"]);

    for (const gone of ["Overview", "Labor", "Releases", "Housing"]) {
      expect(within(nav).queryByRole("link", { name: gone }), gone).not.toBeInTheDocument();
    }

    const user = userEvent.setup();
    await user.tab(); // skip link first
    await user.tab(); // then the MacroChipz brand link
    expect(within(screen.getAllByRole("banner")[0]!).getByRole("link", { name: /MacroChipz/ })).toHaveFocus();
    // Theme control and the (mobile-only) menu toggle come before the
    // nav list in DOM order; tabbing onward reaches the nav's first link.
    await user.tab(); // theme radio group (one tab stop for the whole group)
    await user.tab(); // menu toggle button
    expect(screen.getByRole("button", { name: "Menu" })).toHaveFocus();
    await user.tab();
    expect(homeLink).toHaveFocus();
  });

  it("marks exactly the current destination as the active navigation item", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    renderAt("/inflation");
    const nav = screen.getByRole("navigation", { name: "Primary" });
    expect(within(nav).getByRole("link", { name: "Inflation" })).toHaveAttribute("aria-current", "page");
    for (const name of ["Home", "Jobs", "Rates", "Calendar"]) {
      expect(within(nav).getByRole("link", { name })).not.toHaveAttribute("aria-current");
    }
  });

  it("marks Home active only on the Home route, never on every page", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    renderAt("/calendar");
    const nav = screen.getByRole("navigation", { name: "Primary" });
    expect(within(nav).getByRole("link", { name: "Calendar" })).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("link", { name: "Home" })).not.toHaveAttribute("aria-current");
  });

  it("collapses navigation behind an accessible menu toggle that Escape closes", async () => {
    renderAt("/");
    const user = userEvent.setup();
    const toggle = screen.getByRole("button", { name: "Menu" });
    const list = document.getElementById(toggle.getAttribute("aria-controls")!);
    expect(list).not.toBeNull();
    expect(toggle).toHaveAttribute("aria-expanded", "false");

    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");

    await user.keyboard("{Escape}");
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(toggle).toHaveFocus();
  });

  it("closes the mobile menu after a navigation choice", async () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    renderAt("/");
    const user = userEvent.setup();
    const toggle = screen.getByRole("button", { name: "Menu" });
    await user.click(toggle);
    await user.click(within(screen.getByRole("navigation", { name: "Primary" })).getByRole("link", { name: "Jobs" }));
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByRole("heading", { level: 1, name: "Jobs" })).toBeInTheDocument();
  });

  it("renders the live economic surface at /", () => {
    // Only routing is under test here -- pages/Home.test.tsx covers the
    // page's own data loading and rendering behavior in full.
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    renderAt("/");
    expect(screen.getByRole("heading", { level: 1, name: "The economy right now" })).toBeInTheDocument();
  });

  describe("old URLs keep working (#41)", () => {
    // Links shared before #41 are not the reader's mistake. Each old
    // path lands on its successor's content rather than a 404.
    it.each([
      ["/overview", "The economy right now"],
      ["/labor", "Jobs"],
      ["/releases", "Release calendar"],
    ])("redirects %s to its successor", (from, heading) => {
      vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
      renderAt(from);
      expect(screen.getByRole("heading", { level: 1, name: heading })).toBeInTheDocument();
    });

    it("does not leave the old path in the reader's history", () => {
      vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
      renderAt("/labor");
      // `replace` rather than `push`: going Back must not bounce them
      // through the redirect a second time.
      expect(window.location.pathname).not.toBe("/labor");
    });
  });

  it("renders the Inflation product route at /inflation", () => {
    // Only routing is under test here -- the Inflation page's own data
    // loading, formatting, and every economic-state rendering path have
    // a dedicated, thoroughly-mocked test suite (see pages/Inflation.test.tsx).
    // Stubbing fetch to never resolve keeps this test from making a real
    // network call while still exercising the real page component.
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    renderAt("/inflation");
    expect(screen.getByRole("heading", { level: 1, name: "Inflation" })).toBeInTheDocument();
  });

  it("renders the Jobs product route at /jobs", () => {
    // Only routing is under test here -- the Jobs page's own data
    // loading, formatting, and every economic-state rendering path have
    // a dedicated, thoroughly-mocked test suite (see pages/Jobs.test.tsx).
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    renderAt("/jobs");
    expect(screen.getByRole("heading", { level: 1, name: "Jobs" })).toBeInTheDocument();
  });

  it("renders the Calendar product route at /calendar", () => {
    // Only routing is under test here -- pages/Calendar.test.tsx covers
    // the page's own data loading and rendering behavior in full.
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    renderAt("/calendar");
    expect(screen.getByRole("heading", { level: 1, name: "Release calendar" })).toBeInTheDocument();
  });

  it("renders the Rates product route at /rates", () => {
    // Only routing is under test here -- pages/Rates.test.tsx covers the
    // page's own data loading and rendering behavior in full.
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    renderAt("/rates");
    expect(screen.getByRole("heading", { level: 1, name: "Rates Intelligence" })).toBeInTheDocument();
  });

  it("renders a deterministic not-found page for an unknown route", () => {
    renderAt("/this-route-does-not-exist");
    expect(screen.getByRole("heading", { level: 1, name: "Page not found" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Go to Home/ })).toHaveAttribute("href", "/");
  });

  it("renders the same not-found page deterministically for a second unknown route", () => {
    renderAt("/another-unknown-route");
    expect(screen.getByRole("heading", { level: 1, name: "Page not found" })).toBeInTheDocument();
  });
});
