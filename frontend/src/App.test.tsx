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
    renderAt("/");
    expect(screen.getAllByRole("banner")[0]).toBeInTheDocument();
    expect(screen.getByRole("main")).toBeInTheDocument();
  });

  it("shows the application name in the header", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    renderAt("/");
    // "Economic Intelligence" (the site name) is unique on the page --
    // Overview's own <h1> reads "Economic Overview", a different string.
    expect(screen.getByText("Economic Intelligence")).toBeInTheDocument();
  });

  it("exposes accessible, keyboard-reachable primary navigation", async () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    renderAt("/");
    const nav = screen.getByRole("navigation", { name: "Primary" });
    const overviewLink = within(nav).getByRole("link", { name: "Overview" });
    const inflationLink = within(nav).getByRole("link", { name: "Inflation" });
    const releasesLink = within(nav).getByRole("link", { name: "Releases" });

    expect(overviewLink).toHaveAttribute("href", "/");
    expect(inflationLink).toHaveAttribute("href", "/inflation");
    expect(releasesLink).toHaveAttribute("href", "/releases");

    const user = userEvent.setup();
    await user.tab(); // skip link first
    await user.tab(); // then into nav
    expect(overviewLink).toHaveFocus();
  });

  it("renders the Overview route at /", () => {
    // Only routing is under test here -- pages/Overview.test.tsx covers
    // the page's own data loading and rendering behavior in full.
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    renderAt("/");
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

  it("renders the Releases product route at /releases", () => {
    // Only routing is under test here -- pages/Releases.test.tsx covers
    // the page's own data loading and rendering behavior in full.
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    renderAt("/releases");
    expect(screen.getByRole("heading", { level: 1, name: "Economic Releases" })).toBeInTheDocument();
  });

  it("renders a deterministic not-found page for an unknown route", () => {
    renderAt("/this-route-does-not-exist");
    expect(screen.getByRole("heading", { level: 1, name: "Page not found" })).toBeInTheDocument();
  });

  it("renders the same not-found page deterministically for a second unknown route", () => {
    renderAt("/another-unknown-route");
    expect(screen.getByRole("heading", { level: 1, name: "Page not found" })).toBeInTheDocument();
  });
});
