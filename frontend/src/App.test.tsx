import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
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
  it("renders", () => {
    renderAt("/");
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("main")).toBeInTheDocument();
  });

  it("shows the application name in the header", () => {
    renderAt("/");
    expect(within(screen.getByRole("banner")).getByText("Economic Intelligence")).toBeInTheDocument();
  });

  it("exposes accessible, keyboard-reachable primary navigation", async () => {
    renderAt("/");
    const nav = screen.getByRole("navigation", { name: "Primary" });
    const overviewLink = within(nav).getByRole("link", { name: "Overview" });
    const inflationLink = within(nav).getByRole("link", { name: "Inflation" });

    expect(overviewLink).toHaveAttribute("href", "/");
    expect(inflationLink).toHaveAttribute("href", "/inflation");

    const user = userEvent.setup();
    await user.tab(); // skip link first
    await user.tab(); // then into nav
    expect(overviewLink).toHaveFocus();
  });

  it("renders the Overview route at /", () => {
    renderAt("/");
    expect(screen.getByRole("heading", { level: 1, name: "Economic Intelligence" })).toBeInTheDocument();
    expect(screen.getByText("Frontend foundation ready.")).toBeInTheDocument();
  });

  it("renders the Inflation placeholder route at /inflation", () => {
    renderAt("/inflation");
    expect(screen.getByRole("heading", { level: 1, name: "Inflation" })).toBeInTheDocument();
    expect(screen.getByText("Not yet implemented.")).toBeInTheDocument();
  });

  it("does not fetch or render any inflation data at /inflation", () => {
    renderAt("/inflation");
    expect(screen.queryByText(/COOLING|HEATING|STABLE|MIXED|CONFIRMS|DIVERGES/i)).not.toBeInTheDocument();
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
