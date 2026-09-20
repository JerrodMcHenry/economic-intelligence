import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import App from "./App";

function renderAt(initialRoute: string) {
  return render(
    <MemoryRouter initialEntries={[initialRoute]}>
      <App />
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
    const overviewLink = within(nav).getByRole("link", { name: "Overview" });
    const inflationLink = within(nav).getByRole("link", { name: "Inflation" });
    const laborLink = within(nav).getByRole("link", { name: "Labor" });
    const ratesLink = within(nav).getByRole("link", { name: "Rates" });
    const releasesLink = within(nav).getByRole("link", { name: "Releases" });

    expect(homeLink).toHaveAttribute("href", "/");
    expect(overviewLink).toHaveAttribute("href", "/overview");
    expect(inflationLink).toHaveAttribute("href", "/inflation");
    expect(laborLink).toHaveAttribute("href", "/labor");
    expect(ratesLink).toHaveAttribute("href", "/rates");
    expect(releasesLink).toHaveAttribute("href", "/releases");
    // Only real, implemented destinations, in order. Rates joined in #30
    // because rates_v1.0 genuinely shipped in #29 -- the condition
    // docs/product/product-ui-ux-v1.md §11 set for adding a nav slot
    // (content first, then the IA commitment). Still no placeholders for
    // future Growth/Housing/Markets/etc.
    const navOrder = within(nav).getAllByRole("link").map((link) => link.textContent);
    expect(navOrder).toEqual(["Home", "Overview", "Inflation", "Labor", "Rates", "Releases"]);

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
    for (const name of ["Home", "Overview", "Labor", "Rates", "Releases"]) {
      expect(within(nav).getByRole("link", { name })).not.toHaveAttribute("aria-current");
    }
  });

  it("marks Home active only on the Home route, never on every page", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    renderAt("/overview");
    const nav = screen.getByRole("navigation", { name: "Primary" });
    expect(within(nav).getByRole("link", { name: "Overview" })).toHaveAttribute("aria-current", "page");
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
    await user.click(within(screen.getByRole("navigation", { name: "Primary" })).getByRole("link", { name: "Labor" }));
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByRole("heading", { level: 1, name: "Labor" })).toBeInTheDocument();
  });

  it("renders the Home route at /", () => {
    renderAt("/");
    expect(
      screen.getByRole("heading", { level: 1, name: "Know what changed in the economy — and prove why." }),
    ).toBeInTheDocument();
  });

  it("renders the Overview route at /overview", () => {
    // Only routing is under test here -- pages/Overview.test.tsx covers
    // the page's own data loading and rendering behavior in full.
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    renderAt("/overview");
    expect(screen.getByRole("heading", { level: 1, name: "Economic Overview" })).toBeInTheDocument();
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

  it("renders the Labor product route at /labor", () => {
    // Only routing is under test here -- the Labor page's own data
    // loading, formatting, and every economic-state rendering path have
    // a dedicated, thoroughly-mocked test suite (see pages/Labor.test.tsx).
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    renderAt("/labor");
    expect(screen.getByRole("heading", { level: 1, name: "Labor" })).toBeInTheDocument();
  });

  it("renders the Releases product route at /releases", () => {
    // Only routing is under test here -- pages/Releases.test.tsx covers
    // the page's own data loading and rendering behavior in full.
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    renderAt("/releases");
    expect(screen.getByRole("heading", { level: 1, name: "Economic Releases" })).toBeInTheDocument();
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
