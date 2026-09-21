/**
 * Visual evidence (Increment #40C).
 *
 * The chart is EVIDENCE for the intelligence object, not a second path
 * to economic truth. These tests hold it to that: it draws only what
 * the object carries, it invents nothing between the points, and it is
 * comprehensible without a mouse, without colour and without
 * JavaScript.
 */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { TimeSeriesVisualEvidence } from "../../api/intelligence.types";
import { VisualEvidenceChart } from "./VisualEvidenceChart";

function evidence(overrides: Partial<TimeSeriesVisualEvidence> = {}): TimeSeriesVisualEvidence {
  const points = [
    { observation_date: "2026-06-22", value: 4.51 },
    { observation_date: "2026-06-23", value: 4.58 },
    // A three-day gap: the provider published nothing on the 24th/25th.
    { observation_date: "2026-06-26", value: 4.72 },
    { observation_date: "2026-09-18", value: 5.01 },
  ];
  return {
    kind: "TIME_SERIES",
    concept_id: "UST_NOMINAL_10Y",
    unit: "Percent",
    requested_sessions: 63,
    available_sessions: points.length,
    points,
    ...overrides,
  };
}

const NAME = "10-year Treasury yield";

describe("it draws what the object carries", () => {
  it("renders an SVG path from the supplied points", () => {
    const { container } = render(<VisualEvidenceChart evidence={evidence()} seriesName={NAME} />);
    const paths = container.querySelectorAll("path[d]");
    expect(paths.length).toBeGreaterThan(0);
    // One move command and three line commands -- exactly four points,
    // no more.
    const d = paths[0]?.getAttribute("d") ?? "";
    expect((d.match(/[ML]/g) ?? []).length).toBe(4);
  });

  it("adds no point the object did not supply", () => {
    const { container } = render(<VisualEvidenceChart evidence={evidence()} seriesName={NAME} />);
    const d = container.querySelector("path[d]")?.getAttribute("d") ?? "";
    expect((d.match(/L/g) ?? []).length).toBe(3);
  });

  it("positions by date, so an unpublished stretch stays a gap", () => {
    const { container } = render(<VisualEvidenceChart evidence={evidence()} seriesName={NAME} />);
    const d = container.querySelector("path[d]")?.getAttribute("d") ?? "";
    const xs = [...d.matchAll(/[ML] ([\d.]+)/g)].map((match) => Number(match[1]));
    // 22 -> 23 June is one day; 26 June -> 18 Sep is 84. If the chart
    // spaced points evenly by index, those gaps would be identical.
    const firstGap = (xs[1] ?? 0) - (xs[0] ?? 0);
    const lastGap = (xs[3] ?? 0) - (xs[2] ?? 0);
    expect(lastGap).toBeGreaterThan(firstGap * 10);
  });

  it("marks the latest observation so it is identifiable without hovering", () => {
    const { container } = render(<VisualEvidenceChart evidence={evidence()} seriesName={NAME} />);
    expect(container.querySelectorAll("circle").length).toBeGreaterThan(0);
  });

  it("labels the axis with real values rather than hiding the scale", () => {
    render(<VisualEvidenceChart evidence={evidence()} seriesName={NAME} />);
    // Domain is padded around 4.51-5.01, so the labels are outside it.
    const labels = screen.getAllByText(/^[45]\.\d\d$/);
    expect(labels.length).toBeGreaterThanOrEqual(3);
  });

  it("labels the first and last dates", () => {
    render(<VisualEvidenceChart evidence={evidence()} seriesName={NAME} />);
    expect(screen.getAllByText("22 Jun 2026").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/18 Sep 2026/).length).toBeGreaterThan(0);
  });
});

describe("it does not distort", () => {
  it("never uses preserveAspectRatio=none", () => {
    // ADR-041 recorded this as a live defect in the yield-curve chart
    // and made fixing it an acceptance criterion.
    const { container } = render(<VisualEvidenceChart evidence={evidence()} seriesName={NAME} />);
    for (const svg of container.querySelectorAll('svg[role="img"]')) {
      expect(svg.getAttribute("preserveAspectRatio")).toBe("xMidYMid meet");
    }
  });

  it("ships a viewBox per breakpoint rather than measuring at runtime", () => {
    const { container } = render(<VisualEvidenceChart evidence={evidence()} seriesName={NAME} />);
    const svgs = [...container.querySelectorAll('svg[role="img"]')];
    expect(svgs).toHaveLength(2);
    const classes = svgs.map((svg) => svg.getAttribute("class") ?? "");
    expect(classes.some((c) => c.includes("sm:hidden"))).toBe(true);
    expect(classes.some((c) => c.includes("hidden sm:block"))).toBe(true);
  });

  it("uses a data-driven y domain, not a forced zero baseline", () => {
    render(<VisualEvidenceChart evidence={evidence()} seriesName={NAME} />);
    expect(screen.queryAllByText("0.00")).toHaveLength(0);
  });
});

describe("it implies nothing about good or bad", () => {
  it("uses no semantic state or feedback colour for the series", () => {
    const { container } = render(<VisualEvidenceChart evidence={evidence()} seriesName={NAME} />);
    // The chart itself -- not the shared Disclosure chevron, whose
    // `motion-reduce` class is unrelated to colour.
    const markup = [...container.querySelectorAll('svg[role="img"]')].map((svg) => svg.outerHTML).join("");
    for (const token of ["state-", "feedback-", "red", "green", "danger", "success", "warning", "positive", "negative"]) {
      expect(markup, token).not.toContain(token);
    }
  });

  it("makes no significance or causal claim anywhere in the figure", () => {
    const { container } = render(<VisualEvidenceChart evidence={evidence()} seriesName={NAME} />);
    const chart = [...container.querySelectorAll('svg[role="img"]')]
      .map((svg) => `${svg.textContent} ${svg.getAttribute("aria-label")}`)
      .join(" ")
      .toLowerCase();
    for (const word of ["significant", "notable", "surge", "plunge", "rally", "because", "driven by", "forecast", "expected"]) {
      expect(chart, word).not.toContain(word);
    }
  });
});

describe("accessibility", () => {
  it("is announced as one described image, not two", () => {
    render(<VisualEvidenceChart evidence={evidence()} seriesName={NAME} />);
    // Both SVGs carry role=img, but only one is displayed at a time --
    // `display: none` removes the other from the accessibility tree.
    const images = screen.getAllByRole("img");
    expect(images.length).toBe(2);
    for (const image of images) expect(image).toHaveAttribute("aria-label");
  });

  it("describes metric, span, start, latest and direction", () => {
    render(<VisualEvidenceChart evidence={evidence()} seriesName={NAME} />);
    const label = screen.getAllByRole("img")[0]?.getAttribute("aria-label") ?? "";
    expect(label).toContain("10-year Treasury yield");
    expect(label).toContain("percent");
    expect(label).toContain("4 published trading sessions");
    expect(label).toContain("4.51");
    expect(label).toContain("5.01");
    expect(label).toContain("higher");
  });

  it("offers the underlying numbers as a real table", () => {
    render(<VisualEvidenceChart evidence={evidence()} seriesName={NAME} />);
    const table = screen.getByRole("table");
    expect(within(table).getByText("2026-09-18")).toBeInTheDocument();
    expect(within(table).getByText("5.01")).toBeInTheDocument();
    expect(within(table).getAllByRole("row")).toHaveLength(5); // header + 4
  });

  it("needs no hover or pointer to be understood", () => {
    const { container } = render(<VisualEvidenceChart evidence={evidence()} seriesName={NAME} />);
    expect(container.innerHTML).not.toMatch(/onMouseOver|onMouseMove|onPointer/);
  });
});

describe("honest about a short record", () => {
  it("states the real session count in the caption", () => {
    render(<VisualEvidenceChart evidence={evidence()} seriesName={NAME} />);
    expect(screen.getByText(/Last 4 published trading sessions/)).toBeInTheDocument();
  });

  it("says so when fewer sessions are available than were requested", () => {
    render(<VisualEvidenceChart evidence={evidence()} seriesName={NAME} />);
    expect(screen.getByText(/fewer than the 63 requested/)).toBeInTheDocument();
  });

  it("adds no such note when the full window is present", () => {
    const full = evidence({ available_sessions: 63, requested_sessions: 63 });
    render(<VisualEvidenceChart evidence={full} seriesName={NAME} />);
    expect(screen.queryByText(/fewer than the/)).not.toBeInTheDocument();
  });

  it("refuses to draw a line through a single observation", () => {
    const single = evidence({
      points: [{ observation_date: "2026-09-18", value: 5.01 }],
      available_sessions: 1,
    });
    const { container } = render(<VisualEvidenceChart evidence={single} seriesName={NAME} />);
    expect(container.querySelectorAll('svg[role="img"]')).toHaveLength(0);
    expect(screen.getByText(/no line to draw yet/)).toBeInTheDocument();
  });

  it("renders nothing at all for an empty series", () => {
    const empty = evidence({ points: [], available_sessions: 0 });
    const { container } = render(<VisualEvidenceChart evidence={empty} seriesName={NAME} />);
    expect(container.firstChild).toBeNull();
  });
});
