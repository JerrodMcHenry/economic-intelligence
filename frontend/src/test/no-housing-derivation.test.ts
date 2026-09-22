/**
 * Architectural guard: the Housing surface renders canonical figures and
 * derives none of them (Increment #45).
 *
 * The sibling of `no-rates-calculation.test.ts`, and it exists for a
 * sharper reason. Rates has a frozen methodology, so a frontend
 * recalculation would disagree with a published one. Housing has NO
 * methodology — which means a number computed here would not merely
 * disagree with the backend, it would be the only place that number
 * existed, and MacroChipz would be publishing an economic figure nobody
 * reviewed.
 *
 * THE SPECIFIC ARITHMETIC THIS FORBIDS
 * ------------------------------------
 * 1. **Dividing an annual rate by twelve.** 1,394,000 / 12 is 116,167,
 *    and the real unadjusted August figure is 117,400. Close enough to
 *    look right; wrong on principle, because the seasonal adjustment
 *    that produced the annual rate is exactly what the division throws
 *    away. This is the single most plausible mistake on this page.
 * 2. **Multiplying a monthly count by twelve**, the same error inverted.
 *    MacroChipz has no seasonal adjustment of its own, so it cannot
 *    produce an annual rate from an unadjusted figure.
 * 3. **Recomputing a change or a percentage** from two fields the
 *    response already carries as computed values.
 * 4. **Inventing a housing state**, a score, or a direction verdict.
 */
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const SRC = join(dirname(fileURLToPath(import.meta.url)), "..");

/** Every Housing-owned module. */
const HOUSING_FILES: ReadonlyArray<string> = [
  "pages/Housing.tsx",
  "lib/housingFormat.ts",
  "api/housing.ts",
  "api/housing.types.ts",
  ...readdirSync(join(SRC, "components/housing"))
    .filter((name) => /\.tsx?$/.test(name) && !/\.test\./.test(name))
    .map((name) => `components/housing/${name}`),
];

function source(relative: string): string {
  return readFileSync(join(SRC, relative), "utf8");
}

/** Source with comments removed, so prose explaining a rule never trips it. */
function code(relative: string): string {
  return source(relative)
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "");
}

describe("the Housing surface scans the files it thinks it does", () => {
  it("finds every Housing module", () => {
    expect(HOUSING_FILES.length).toBeGreaterThanOrEqual(7);
    for (const relative of HOUSING_FILES) expect(source(relative).length).toBeGreaterThan(0);
  });
});

describe("no annualisation or de-annualisation", () => {
  for (const relative of HOUSING_FILES) {
    it(`${relative} never divides by twelve`, () => {
      expect(code(relative)).not.toMatch(/\/\s*12\b/);
    });

    it(`${relative} never multiplies by twelve`, () => {
      expect(code(relative)).not.toMatch(/\*\s*12\b|\b12\s*\*/);
    });
  }
});

describe("no client-side economic derivation", () => {
  for (const relative of HOUSING_FILES) {
    it(`${relative} recomputes no change from two values`, () => {
      const contents = code(relative);
      // The same shapes `no-economic-logic.test.ts` forbids globally,
      // restated for the fields this world actually carries.
      expect(contents).not.toMatch(/value\s*-\s*previous_value|previous_value\s*-\s*value/i);
      expect(contents).not.toMatch(/value\s*-\s*year_ago_value/i);
      expect(contents).not.toMatch(/change_from_previous\s*\/\s*previous_value/i);
    });

    it(`${relative} derives no percentage of its own`, () => {
      expect(code(relative)).not.toMatch(/\*\s*100\b/);
    });
  }
});

describe("no invented housing state", () => {
  for (const relative of HOUSING_FILES) {
    it(`${relative} declares no state vocabulary`, () => {
      const contents = code(relative).toLowerCase();
      for (const forbidden of ["cooling", "heating", "overheated", "healthy", "unhealthy", "worsening", "improving"]) {
        expect(contents, forbidden).not.toMatch(new RegExp(`\\b${forbidden}\\b`));
      }
    });

    it(`${relative} declares no score, weight or ranking`, () => {
      const contents = code(relative);
      for (const forbidden of ["housingScore", "Score(", "weight", "severity", "significance"]) {
        expect(contents, forbidden).not.toContain(forbidden);
      }
      // A MAGNITUDE-keyed sort, not any sort. The chart legitimately
      // sorts table rows by month -- chronological order is the axis,
      // not a ranking -- and the exact shape forbidden here is the one
      // `no-economic-logic.test.ts` forbids globally: ordering by how
      // big a change is, which would be a significance ranking smuggled
      // in under a layout concern.
      expect(contents).not.toMatch(/\.sort\([^)]*\b(delta|change|Math\.abs|value)\b/);
    });
  }
});

describe("no mortgage data, real or estimated", () => {
  // WHAT THIS BLOCK CHECKS, AND WHAT IT DELIBERATELY DOES NOT.
  //
  // A substring scan cannot tell "there is no estimated mortgage rate
  // here" -- the disclaimer the rate-context section exists to make --
  // from an estimated mortgage rate. So the CLAIMS these components
  // make are asserted against RENDERED TEXT in
  // `components/housing/RateContext.test.tsx`, where a sentence can be
  // read in context. What remains here is the structural half: no
  // component may import a rates figure or bind one to a housing
  // figure, which no amount of careful wording can make acceptable.
  for (const relative of HOUSING_FILES) {
    it(`${relative} imports no rates data to place beside a housing figure`, () => {
      const contents = code(relative);
      for (const forbidden of ["api/rates", "getRatesMonitor", "RatesMonitorResult", "UST_NOMINAL"]) {
        expect(contents, forbidden).not.toContain(forbidden);
      }
    });
  }

  it("the rate-context section fetches and computes nothing", () => {
    const contents = code("components/housing/RateContext.tsx");
    // It renders no figure at all -- see the module's own docstring for
    // why a live yield beside housing figures would assert a
    // relationship MacroChipz has not measured.
    expect(contents).not.toMatch(/useApiResource|getRates|fetch\(/);
  });
});

describe("no provider access from the browser", () => {
  for (const relative of HOUSING_FILES) {
    it(`${relative} never reaches a provider directly`, () => {
      const contents = source(relative).toLowerCase();
      for (const forbidden of ["api.census.gov", "census_api_key", "census.gov/data", "api_key"]) {
        expect(contents, forbidden).not.toContain(forbidden);
      }
    });
  }

  it("the only network call is to MacroChipz's own API", () => {
    expect(code("api/housing.ts")).toContain("/api/v1/housing");
    expect(code("api/housing.ts")).not.toContain("http");
  });

  it("the page never calls the operator sync route", () => {
    for (const relative of HOUSING_FILES) {
      expect(code(relative), relative).not.toContain("/housing/sync");
    }
  });
});

describe("the chart draws only what it was given", () => {
  const chart = code("components/housing/HousingPipelineChart.tsx");

  it("interpolates, smooths and extrapolates nothing", () => {
    for (const forbidden of ["interpolat", "smooth", "extrapolat", "movingAverage", "curveBasis", "curveCardinal"]) {
      expect(chart.toLowerCase(), forbidden).not.toContain(forbidden.toLowerCase());
    }
  });

  it("adds no charting library", () => {
    for (const library of ["recharts", "chart.js", "echarts", "nivo", "victory", "plotly", "@visx", "d3-"]) {
      expect(chart.toLowerCase(), library).not.toContain(library);
    }
  });

  it("never distorts the aspect ratio", () => {
    // ADR-041's recorded defect: `preserveAspectRatio="none"` squashed
    // the yield curve ~37% horizontally at phone width.
    expect(chart).toContain('preserveAspectRatio="xMidYMid meet"');
    expect(chart).not.toContain('preserveAspectRatio="none"');
  });

  it("renders a viewBox per breakpoint rather than measuring at runtime", () => {
    // ADR-041: `ResizeObserver` measurement would reintroduce the
    // server-rendering failure that disqualified Recharts.
    expect(chart).not.toContain("ResizeObserver");
    expect(chart).toMatch(/const DESKTOP/);
    expect(chart).toMatch(/const MOBILE/);
  });

  it("depends on no hover or pointer interaction", () => {
    for (const forbidden of ["onMouseOver", "onMouseMove", "onPointer", "onHover", "tooltip"]) {
      expect(chart.toLowerCase(), forbidden).not.toContain(forbidden.toLowerCase());
    }
  });

  it("uses no red/green or other state semantics for direction", () => {
    for (const forbidden of ["feedback-success", "feedback-error", "state-warm", "state-cool", "text-red", "text-green"]) {
      expect(chart, forbidden).not.toContain(forbidden);
    }
  });
});
