/**
 * The payroll/unemployment distinction (Increment #41).
 *
 * `app/concepts/registry.py` makes `universe` a REQUIRED field so this
 * difference can never be lost in the backend. Until #41 the frontend
 * lost it anyway, by simply not mentioning it. These tests make the
 * consumer explanation as load-bearing as the backend field.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TwoSurveysNote } from "./TwoSurveysNote";

function text(): string {
  const { container } = render(<TwoSurveysNote />);
  return container.textContent ?? "";
}

describe("the two measures are not presented as the same population", () => {
  it("says plainly that one counts jobs and the other counts people", () => {
    const body = text();
    expect(body).toMatch(/counts\s+jobs/i);
    expect(body).toMatch(/counts\s+people/i);
  });

  it("names both survey programs so the distinction is checkable", () => {
    const body = text();
    expect(body).toContain("Establishment survey (CES)");
    expect(body).toContain("Household survey (CPS)");
  });

  it("gives the concrete consequence of each universe", () => {
    const body = text();
    // NONFARM_PAYROLL_JOBS: a person with two jobs is two jobs.
    expect(body).toMatch(/two jobs counts twice/i);
    // CIVILIAN_LABOR_FORCE_PERSONS: leaving the labour force is not a
    // job lost.
    expect(body).toMatch(/stops looking for work leaves the count/i);
  });

  it("explains that disagreement does not make either wrong", () => {
    expect(text()).toMatch(/different directions in the same month without either being wrong/i);
  });

  it("does not collapse them into one number", () => {
    expect(text()).toMatch(/rather than averaging them into a single number/i);
  });
});

describe("it explains without concluding", () => {
  it("states no economic conclusion and no significance claim", () => {
    const body = text().toLowerCase();
    for (const word of ["significant", "notable", "recession", "strong economy", "weak economy", "because of"]) {
      expect(body, word).not.toContain(word);
    }
  });

  it("does not say which measure is right when they disagree", () => {
    const body = text().toLowerCase();
    for (const claim of ["more accurate", "more reliable", "better measure", "the real", "truer"]) {
      expect(body, claim).not.toContain(claim);
    }
  });

  it("attributes the Mixed classification to the methodology, not to itself", () => {
    expect(text()).toMatch(/MacroChipz keeps them separate/);
    expect(text()).toMatch(/reports the overall Jobs state as\s+Mixed/);
  });
});

describe("progressive disclosure", () => {
  it("starts closed, so the explanation is available without dominating", () => {
    const { container } = render(<TwoSurveysNote />);
    const details = container.querySelector("details");
    expect(details).not.toBeNull();
    expect(details).not.toHaveAttribute("open");
  });

  it("is reachable as a native disclosure rather than a custom widget", () => {
    render(<TwoSurveysNote />);
    expect(screen.getByText("Why these two can tell different stories").tagName).toBe("SUMMARY");
  });
});
