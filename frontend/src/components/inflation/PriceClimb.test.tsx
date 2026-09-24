import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { buildCorePceObservations, buildEvidence, buildMomentum } from "../../test/fixtures/inflation";
import type { SeriesMomentumResult } from "../../api/inflation.types";
import { PriceClimb } from "./PriceClimb";

/*
 * The shared `buildMomentum` gives all four windows the SAME evidence
 * dates and values, which is fine for the pages that only print rates
 * and useless here — the whole point of the climb is that each window
 * brackets a different span. So this file supplies distinct endpoints
 * that line up with `buildCorePceObservations`.
 */
function momentumWithDistinctWindows(overrides: Partial<SeriesMomentumResult> = {}): SeriesMomentumResult {
  return buildMomentum({
    r_1m_annualized: 2.99,
    r_3m_annualized: 3.05,
    r_6m_annualized: 3.46,
    r_12m: 3.34,
    evidence_1m: buildEvidence({
      transformation: "1m_annualized", value: 2.99,
      endpoint_date_past: "2026-06-01", endpoint_value_past: 130.338,
      endpoint_date_current: "2026-07-01", endpoint_value_current: 130.658,
    }),
    evidence_3m: buildEvidence({
      transformation: "3m_annualized", value: 3.05,
      endpoint_date_past: "2026-04-01", endpoint_value_past: 129.681,
      endpoint_date_current: "2026-07-01", endpoint_value_current: 130.658,
    }),
    evidence_6m: buildEvidence({
      transformation: "6m_annualized", value: 3.46,
      endpoint_date_past: "2026-01-01", endpoint_value_past: 128.455,
      endpoint_date_current: "2026-07-01", endpoint_value_current: 130.658,
    }),
    evidence_12m: buildEvidence({
      transformation: "12m", value: 3.34,
      endpoint_date_past: "2025-07-01", endpoint_value_past: 126.43,
      endpoint_date_current: "2026-07-01", endpoint_value_current: 130.658,
    }),
    ...overrides,
  });
}

function renderClimb(overrides: Partial<SeriesMomentumResult> = {}) {
  return render(<PriceClimb momentum={momentumWithDistinctWindows(overrides)} series={buildCorePceObservations()} />);
}

describe("the climb (#50B)", () => {
  it("plots the price LEVEL, which the page never showed before", () => {
    // #50A: 41 percentages, zero charts, and the index nowhere — while
    // the monitor's own evidence carried it.
    const { container } = renderClimb();
    const chart = within(container).getByRole("img", { name: /Chain-Type Price Index/ });
    expect(chart.getAttribute("aria-label")).toContain("Index 2017=100");
    expect(chart.getAttribute("aria-label")).toContain("6 monthly observations");
    expect(chart.getAttribute("aria-label")).toContain("126.43");
    expect(chart.getAttribute("aria-label")).toContain("130.658");
  });

  it("defaults to the 12-month window", () => {
    renderClimb();
    const pressed = screen.getAllByRole("button").filter((b) => b.getAttribute("aria-pressed") === "true");
    expect(pressed).toHaveLength(1);
    expect(pressed[0]).toHaveAccessibleName(/12 months/);
  });

  it("shows each window's backend rate AND its real index endpoints", async () => {
    const user = userEvent.setup();
    renderClimb();

    // 12-month, the default: the fixture's evidence_12m endpoints.
    expect(screen.getByText("126.43")).toBeInTheDocument();
    expect(screen.getAllByText("130.658").length).toBeGreaterThan(0);

    await user.click(screen.getByRole("button", { name: /1 month/ }));
    // The 1-month window's OWN endpoints, not the 12-month ones.
    expect(screen.getByText("130.338")).toBeInTheDocument();
    expect(screen.queryByText("126.43")).not.toBeInTheDocument();
  });

  it("keeps exactly one window selected and focus on the control", async () => {
    const user = userEvent.setup();
    renderClimb();
    const threeMonth = screen.getByRole("button", { name: /3 months/ });
    await user.click(threeMonth);
    expect(threeMonth).toHaveAttribute("aria-pressed", "true");
    expect(threeMonth).toHaveFocus();
    expect(screen.getAllByRole("button").filter((b) => b.getAttribute("aria-pressed") === "true")).toHaveLength(1);
  });

  it("labels annualised windows as annualised and the 12-month one as not", async () => {
    const user = userEvent.setup();
    renderClimb();
    expect(screen.getByText(/the change over twelve months/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /6 months/ }));
    expect(screen.getByText(/annualised — the recent pace expressed as a yearly rate/)).toBeInTheDocument();
  });

  it("disables a window with no computed rate and invents nothing for it", () => {
    renderClimb({ r_1m_annualized: null, evidence_1m: null });
    const oneMonth = screen.getByRole("button", { name: /1 month/ });
    expect(oneMonth).toBeDisabled();
    expect(within(oneMonth).getByText("n/a")).toBeInTheDocument();
    // And no zero is fabricated in its place.
    expect(screen.queryByText("0.00%")).not.toBeInTheDocument();
  });

  it("falls back to a computed window rather than opening empty", () => {
    // If the 12-month window were ever absent, the panel must still
    // have something real to show.
    renderClimb({ r_12m: null, evidence_12m: null });
    const pressed = screen.getAllByRole("button").filter((b) => b.getAttribute("aria-pressed") === "true");
    expect(pressed).toHaveLength(1);
    expect(pressed[0]).not.toHaveAccessibleName(/12 months/);
  });

  it("draws NO rate line — the API publishes no rate history", () => {
    // Deriving one from these levels would be client-side economics.
    // The dependency is documented in the #50A spec, not simulated.
    const { container } = renderClimb();
    const paths = Array.from(container.querySelectorAll("path"));
    // Area + base line + the selected span. Nothing else.
    expect(paths.length).toBeLessThanOrEqual(3);
  });

  it("uses HTML endpoint markers, which stay round on a stretched board", () => {
    // `preserveAspectRatio="none"` turns an SVG circle into an ellipse
    // (#48B, and again in the #50A prototype).
    const { container } = renderClimb();
    expect(container.querySelectorAll("svg circle")).toHaveLength(0);
    expect(container.querySelectorAll("span.rounded-full").length).toBeGreaterThanOrEqual(2);
  });

  it("announces the reading politely", () => {
    const { container } = renderClimb();
    expect(container.querySelector('[aria-live="polite"]')).not.toBeNull();
  });
});
