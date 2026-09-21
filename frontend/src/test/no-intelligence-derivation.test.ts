/**
 * Architectural guard: the frontend CONSUMES Structured Intelligence,
 * it never recreates it (Increment #40).
 *
 * #39 exists so every surface renders the same account of reality. A
 * page that computed its own change magnitude, revision amount or
 * economic state would be a second account -- and the one users see.
 *
 * Formatting is allowed. Recalculation is not.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const SRC = join(dirname(fileURLToPath(import.meta.url)), "..");

function intelligenceFiles(): string[] {
  const found: string[] = [];
  function walk(directory: string): void {
    for (const entry of readdirSync(directory)) {
      const full = join(directory, entry);
      if (statSync(full).isDirectory()) {
        walk(full);
        continue;
      }
      if (!/\.tsx?$/.test(full) || /\.test\.tsx?$/.test(full)) continue;
      const rel = relative(SRC, full);
      if (
        rel.includes("components/intelligence/") ||
        rel.endsWith("routes/intelligenceObject.tsx") ||
        rel.endsWith("lib/intelligenceLanguage.ts") ||
        rel.endsWith("lib/intelligenceMetadata.ts")
      ) {
        found.push(full);
      }
    }
  }
  walk(SRC);
  return found;
}

const FORBIDDEN: ReadonlyArray<{ name: string; pattern: RegExp }> = [
  {
    // Subtracting one economic value from another is deriving a change
    // the object already carries as `delta` / `change_basis_points`.
    name: "arithmetic between economic values",
    pattern: /\b\w*(?:value|rate|change|yield|delta|previous|current)\w*\s*[-+*/]\s*\w*(?:value|rate|change|yield|delta|previous|current)\w*/i,
  },
  {
    // Deriving basis points from a rate would be recomputing a change
    // the object already supplies as `change_basis_points`.
    //
    // `* 100` is deliberately NOT forbidden: rendering an already-
    // computed 0-1 percentile rank as a percentage is a unit label, not
    // a derivation. The object carries the rank; presentation chooses
    // how to write it.
    name: "deriving basis points from a rate",
    pattern: /[*/]\s*10000\b/,
  },
  {
    name: "re-deriving world or basis from anything but the object's own field",
    pattern: /world\s*=\s*(?!object\.world)["'`]/,
  },
  {
    name: "re-deriving knowledge basis",
    pattern: /knowledge_basis\s*=(?!=)\s*["'`]/,
  },
  {
    name: "fabricating a publication time",
    // `[:=](?!=)` so a COMPARISON (`published_at === null`) is not
    // mistaken for an assignment. Reading the field is the correct
    // behaviour; inventing a value for it is the defect.
    pattern: /published_at\s*[:=](?!=)\s*(?!object\.published_at|null|data)/,
  },
];

describe("the frontend does not recreate canonical intelligence", () => {
  it("has intelligence presentation files to guard", () => {
    expect(intelligenceFiles().length).toBeGreaterThan(0);
  });

  it("performs no canonical calculation in intelligence presentation code", () => {
    const offenders: string[] = [];
    for (const file of intelligenceFiles()) {
      const source = readFileSync(file, "utf8");
      for (const rule of FORBIDDEN) {
        // Strip comments: prose about arithmetic is not arithmetic.
        const code = source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
        if (rule.pattern.test(code)) offenders.push(`${relative(SRC, file)}: ${rule.name}`);
      }
    }
    expect(offenders).toEqual([]);
  });

  it("imports no model or provider SDK into rendering", () => {
    for (const file of intelligenceFiles()) {
      const source = readFileSync(file, "utf8").toLowerCase();
      for (const token of ["openai", "anthropic", "chat.completions"]) {
        expect(source).not.toContain(token);
      }
    }
  });
});

/**
 * The curated explanation content the page selects from (#40B).
 *
 * "Why this matters" is static prose written by us and chosen by exact
 * concept id. It is guarded separately from the rendering files because
 * the risk is different: not arithmetic, but the content quietly
 * becoming generated or fetched at some later point.
 */
describe("curated explanations stay curated", () => {
  const rates = readFileSync(join(SRC, "content/explanations/rates.ts"), "utf8");

  it("uses no model", () => {
    const lower = rates.toLowerCase();
    for (const token of ["openai", "anthropic", "chat.completions", "generatetext", "prompt"]) {
      expect(lower, token).not.toContain(token);
    }
  });

  it("fetches nothing and reads no live value", () => {
    for (const token of ["fetch(", "axios", "XMLHttpRequest", "import("]) {
      expect(rates, token).not.toContain(token);
    }
  });

  it("is static text, not a template over runtime data", () => {
    // A curated explanation must not interpolate the object's own
    // numbers -- that would make it a generated sentence wearing
    // curated clothing, and it could then contradict the page.
    const whySection = rates.slice(rates.indexOf("WHY_THIS_MATTERS_BY_CONCEPT"));
    expect(whySection).not.toMatch(/\$\{/);
  });

  it("describes benchmark relationships as influence, never as control", () => {
    const whySection = rates.slice(rates.indexOf("WHY_THIS_MATTERS_BY_CONCEPT")).toLowerCase();
    for (const claim of ["determines", "sets mortgage", "controls", "drives mortgage", "dictates"]) {
      expect(whySection, claim).not.toContain(claim);
    }
  });
});

/**
 * Visual evidence is part of the intelligence object's evidence
 * contract, not a frontend side-channel into economic data (#40C).
 *
 * The chart draws `payload.visual_evidence`, which arrives inside the
 * object. If this page ever fetched observations itself, the drawn
 * series and the printed numbers could disagree -- two accounts of
 * reality, with the chart being the one users believe.
 */
describe("the chart is evidence, not a second data path", () => {
  const chart = readFileSync(join(SRC, "components/intelligence/VisualEvidenceChart.tsx"), "utf8");

  it("reads its series from the intelligence object it was given", () => {
    expect(chart).toMatch(/evidence\.points/);
  });

  it("fetches nothing itself", () => {
    for (const token of ["fetch(", "axios", "XMLHttpRequest", "useEffect", "EventSource", "WebSocket"]) {
      expect(chart, token).not.toContain(token);
    }
  });

  it("imports no API client, repository or provider module", () => {
    const imports = [...chart.matchAll(/from\s+["']([^"']+)["']/g)].map((match) => match[1] ?? "");
    for (const specifier of imports) {
      expect(specifier, specifier).not.toMatch(/api\/(?!intelligence\.types)/);
      expect(specifier, specifier).not.toMatch(/observations|treasury|fred|repository/i);
    }
  });

  it("interpolates, smooths, forecasts and extrapolates nothing", () => {
    const code = chart.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
    for (const token of ["interpolate", "curveBasis", "curveCatmull", "smooth", "forecast", "extrapolate", "fillMissing", "forwardFill"]) {
      expect(code.toLowerCase(), token).not.toContain(token.toLowerCase());
    }
  });

  it("adds no charting library", () => {
    const imports = [...chart.matchAll(/from\s+["']([^"']+)["']/g)].map((match) => match[1] ?? "");
    for (const library of ["recharts", "chart.js", "echarts", "nivo", "victory", "plotly", "visx"]) {
      expect(imports.some((specifier) => specifier.includes(library)), library).toBe(false);
    }
  });

  it("never distorts the aspect ratio", () => {
    // ADR-041 recorded that defect, and this module's header explains
    // it in prose -- so comments are stripped before matching. Writing
    // about the bug is not the bug.
    const code = chart.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
    expect(code).not.toMatch(/preserveAspectRatio=["{]?["']?none/);
    expect(code).toMatch(/preserveAspectRatio="xMidYMid meet"/);
  });

  it("uses no model", () => {
    for (const token of ["openai", "anthropic", "chat.completions"]) {
      expect(chart.toLowerCase(), token).not.toContain(token);
    }
  });
});

describe("sharing does not depend on analytics", () => {
  const share = readFileSync(join(SRC, "components/ShareButton.tsx"), "utf8");

  it("never awaits the analytics call", () => {
    expect(share).not.toMatch(/await\s+track\(/);
  });

  it("does not gate the share on analytics succeeding", () => {
    // `track()` must not appear inside a condition that could skip the
    // share, nor inside the try that performs it.
    expect(share).not.toMatch(/if\s*\([^)]*track\(/);
  });

  it("shares the permanent URL with no tracking parameters appended", () => {
    expect(share).not.toMatch(/utm_/);
    expect(share).not.toMatch(/url\s*\+\s*["'`]\?/);
  });
});

describe("OG generation consumes structured facts, not screenshots", () => {
  // Comments stripped: this module's own docstring explains WHY it does
  // not take screenshots, and prose about a risk is not the risk.
  const og = readFileSync(join(SRC, "..", "scripts", "generate-og-images.mjs"), "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "");

  it("uses no headless browser or page screenshot", () => {
    for (const token of ["puppeteer", "playwright", "screenshot", "chromium"]) {
      expect(og.toLowerCase()).not.toContain(token);
    }
  });

  it("renders from the object's own payload", () => {
    expect(og).toMatch(/object\.payload/);
  });
});
