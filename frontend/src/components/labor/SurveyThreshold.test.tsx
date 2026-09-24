import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import {
  buildLaborMonitor,
  buildPayrollObservations,
  buildUnemploymentObservations,
} from "../../test/fixtures/labor";
import { SurveyThreshold } from "./SurveyThreshold";

/*
 * The shared fixture's employment delta (+30,000) sits INSIDE its
 * ±50,000 band, so it cannot exercise the contrast this component
 * exists to show. These tests set a delta outside the band for
 * employment and leave unemployment's inside it — which is also what
 * the live data does.
 */
function outsideTheBand(overrides: Parameters<typeof buildLaborMonitor>[0] = {}) {
  const base = buildLaborMonitor();
  return buildLaborMonitor({
    employment: {
      ...base.employment,
      current_3m_avg_jobs: 71333,
      prior_3m_avg_jobs: 141667,
      momentum_delta_jobs: -70333,
    },
    ...overrides,
  });
}

/** The rendered sentence contains `<span>`s, so match on textContent. */
function hasText(pattern: RegExp): boolean {
  return pattern.test(document.body.textContent ?? "");
}

function renderThreshold(overrides: Parameters<typeof buildLaborMonitor>[0] = {}, opts: { payroll?: boolean; unemployment?: boolean } = {}) {
  return render(
    <SurveyThreshold
      result={outsideTheBand(overrides)}
      payroll={opts.payroll === false ? null : buildPayrollObservations()}
      unemployment={opts.unemployment === false ? null : buildUnemploymentObservations()}
    />,
  );
}

describe("the survey threshold (#51B)", () => {
  it("offers both surveys and opens on the employer survey", () => {
    renderThreshold();
    const controls = screen.getAllByRole("button");
    expect(controls).toHaveLength(2);
    const pressed = controls.filter((c) => c.getAttribute("aria-pressed") === "true");
    expect(pressed).toHaveLength(1);
    expect(pressed[0]).toHaveAccessibleName(/Payroll employment/);
  });

  it("switching keeps exactly one selected and keeps focus on the control", async () => {
    const user = userEvent.setup();
    renderThreshold();
    const household = screen.getByRole("button", { name: /Unemployment rate/ });
    await user.click(household);
    expect(household).toHaveAttribute("aria-pressed", "true");
    expect(household).toHaveFocus();
    expect(screen.getAllByRole("button").filter((c) => c.getAttribute("aria-pressed") === "true")).toHaveLength(1);
  });

  it("gives the neutral band a consumer-readable label with the exact threshold", async () => {
    // #51B refinement 2. The deadband was in the response and never
    // rendered, so a reader could not tell why one move counted and
    // another did not.
    const user = userEvent.setup();
    renderThreshold();
    expect(screen.getByText(/within 50,000 jobs a month either way counts as no real change/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Unemployment rate/ }));
    expect(
      screen.getByText(/within 0.2 percentage points either way counts as no real change/),
    ).toBeInTheDocument();
  });

  it("explains each classification from the backend's own numbers", async () => {
    const user = userEvent.setup();
    renderThreshold();
    expect(hasText(/falls outside that band/)).toBe(true);
    expect(hasText(/71,333/)).toBe(true);
    expect(hasText(/141,667/)).toBe(true);

    await user.click(screen.getByRole("button", { name: /Unemployment rate/ }));
    expect(hasText(/falls inside that band/)).toBe(true);
  });

  it("describes the threshold to assistive technology, band and verdict together", () => {
    const { container } = renderThreshold();
    const label = container.querySelector('svg[role="img"]')?.getAttribute("aria-label") ?? "";
    expect(label).toMatch(/neutral band of 50,000 jobs either way/);
    expect(label).toMatch(/falls outside the band/);
  });

  it("BREAKS THE LINE AT A GAP and never plots a null as a value", async () => {
    // #51B refinement 3. The live UNRATE series carries a null; feeding
    // it to `Math.min` coerces it to 0, which destroys the axis floor
    // AND draws a value the provider never published.
    const user = userEvent.setup();
    const { container } = renderThreshold();
    await user.click(screen.getByRole("button", { name: /Unemployment rate/ }));

    const charts = Array.from(container.querySelectorAll('svg[role="img"]'));
    const series = charts[charts.length - 1]!;
    // One null in the middle of six observations splits the line in two.
    expect(series.querySelectorAll("path")).toHaveLength(2);
    for (const path of Array.from(series.querySelectorAll("path"))) {
      expect(path.getAttribute("d")).not.toMatch(/NaN/);
    }
  });

  it("discloses the gap in words as well as in the drawing", async () => {
    const user = userEvent.setup();
    const { container } = renderThreshold();
    await user.click(screen.getByRole("button", { name: /Unemployment rate/ }));

    expect(screen.getByText("1 month not published")).toBeInTheDocument();
    const charts = Array.from(container.querySelectorAll('svg[role="img"]'));
    expect(charts[charts.length - 1]!.getAttribute("aria-label")).toMatch(
      /1 month in that range has no published value and is left as a gap/,
    );
  });

  it("excludes missing observations from the axis domain", async () => {
    // The fixture's real values run 4.1..4.3. If the null were counted
    // the floor would be 0 and every point would sit in the top sliver.
    const user = userEvent.setup();
    const { container } = renderThreshold();
    await user.click(screen.getByRole("button", { name: /Unemployment rate/ }));

    const charts = Array.from(container.querySelectorAll('svg[role="img"]'));
    const ys = (charts[charts.length - 1]!.innerHTML.match(/[ML] [\d.]+ ([\d.]+)/g) ?? []).map((m) =>
      Number(m.split(" ")[2]),
    );
    expect(ys.length).toBeGreaterThan(0);
    // With a correct domain the series uses most of the plot height.
    expect(Math.max(...ys) - Math.min(...ys)).toBeGreaterThan(40);
  });

  it("says so when a survey's observations are unavailable, and keeps the classification", () => {
    renderThreshold({}, { payroll: false });
    expect(screen.getByText(/published observations for this survey are not available/)).toBeInTheDocument();
    // The monitor's own verdict still renders.
    expect(hasText(/falls outside that band/)).toBe(true);
  });

  it("says so when a classification was not computed, and invents nothing", () => {
    renderThreshold({
      employment: {
        ...buildLaborMonitor().employment,
        current_3m_avg_jobs: null,
        momentum_delta_jobs: null,
      },
    });
    expect(screen.getByText(/has not been computed for this period/)).toBeInTheDocument();
    expect(screen.queryByText("0")).not.toBeInTheDocument();
  });

  it("announces the panel politely", () => {
    const { container } = renderThreshold();
    expect(container.querySelector('[aria-live="polite"]')).not.toBeNull();
  });
});
