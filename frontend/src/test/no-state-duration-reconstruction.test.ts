/**
 * Architectural guard for Increment #24D (State Duration V1 frontend),
 * frozen by docs/product/state-duration-v1.md §50/§51. Scoped narrowly
 * to the State Duration implementation's own COMPUTING/RENDERING files
 * -- api/stateDuration.types.ts, lib/stateDurationCopy.ts, and
 * components/StateDurationLine.tsx -- deliberately NOT a whole-tree
 * scan (test/no-economic-logic.test.ts already covers the whole tree
 * for reimplemented backend math) and deliberately NOT including
 * InflationHero.tsx/LaborHero.tsx/DataBasisNote.tsx/
 * content/explanations/inflation.ts, which legitimately reference
 * "Economic Intelligence reported" as part of the frozen §38 sentence
 * NEGATING that exact claim -- a bare substring match there would
 * false-positive on the correct, required prose, the same class of
 * false positive #22B/#23C/#24C already found and fixed elsewhere in
 * this project (see content/explanations/inflation.test.ts's own
 * dedicated exact-string test for that sentence instead).
 *
 * The three files this guard scans have NO legitimate reason to
 * contain any historical-overclaim phrase (qualified or not), any
 * regime-label vocabulary, or any date-arithmetic/month-walking logic
 * at all -- they only ever read already-computed fields off a
 * `StateDurationResult` and build fixed template strings.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const SRC_DIR = join(dirname(fileURLToPath(import.meta.url)), "..");

const STATE_DURATION_FILES = ["api/stateDuration.types.ts", "lib/stateDurationCopy.ts", "components/StateDurationLine.tsx"].map(
  (relative) => join(SRC_DIR, relative),
);

const HISTORICAL_OVERCLAIM_PATTERNS: ReadonlyArray<{ name: string; pattern: RegExp }> = [
  { name: "EI has classified", pattern: /EI has classified/i },
  { name: "EI has said", pattern: /EI has said/i },
  { name: "EI reported", pattern: /EI reported/i },
  { name: "Economic Intelligence reported (unqualified recorded-history claim)", pattern: /Economic Intelligence reported/i },
  { name: "the state has been X since (unqualified)", pattern: /the state has been\b/i },
  { name: "as-known-at-time", pattern: /as-known-at-time/i },
  { name: "as of {date}, EI knew", pattern: /as of .*, EI knew/i },
  { name: "recorded history claim", pattern: /\brecorded history\b/i },
];

const REGIME_PATTERNS: ReadonlyArray<{ name: string; pattern: RegExp }> = [
  { name: "Goldilocks", pattern: /goldilocks/i },
  { name: "stagflation", pattern: /stagflation/i },
  { name: "bullish", pattern: /bullish/i },
  { name: "bearish", pattern: /bearish/i },
  { name: "risk-on", pattern: /risk-on/i },
  { name: "risk-off", pattern: /risk-off/i },
  { name: "healthy/favorable economy framing", pattern: /healthy economy|favorable environment|the economy is\b/i },
];

const STATISTICAL_PATTERNS: ReadonlyArray<{ name: string; pattern: RegExp }> = [
  { name: "percentile", pattern: /percentile/i },
  { name: "quantile", pattern: /quantile/i },
  { name: "standard deviation identifier", pattern: /stddev|stdev|standard deviation/i },
];

const DATE_ARITHMETIC_PATTERNS: ReadonlyArray<{ name: string; pattern: RegExp }> = [
  { name: "month-walking Date mutation (setMonth)", pattern: /\.setMonth\(/ },
  { name: "month-walking Date read (getMonth) -- formatPeriod's own string parsing lives elsewhere, never here", pattern: /\.getMonth\(\)/ },
  { name: "a declared month_before-shaped helper (re-deriving backend calendar stepping)", pattern: /(function\s+|const\s+)month_?[Bb]efore\b/ },
];

const ARCHITECTURE_PATTERNS: ReadonlyArray<{ name: string; pattern: RegExp }> = [
  { name: "backend import (from an app/ path)", pattern: /from\s+["'](\.\.\/)*app\// },
  { name: "AI/LLM import", pattern: /\bopenai\b|\banthropic\b|\bllm\b/i },
  { name: "charting import", pattern: /\b(chart\.js|recharts|d3|plotly)\b/i },
  { name: "FRED import", pattern: /\bfred\b/i },
];

const ALL_PATTERNS = [
  ...HISTORICAL_OVERCLAIM_PATTERNS,
  ...REGIME_PATTERNS,
  ...STATISTICAL_PATTERNS,
  ...DATE_ARITHMETIC_PATTERNS,
  ...ARCHITECTURE_PATTERNS,
];

describe("State Duration V1 frontend implementation contains no reconstruction, no overclaim, no regime labels", () => {
  it("scans exactly the three expected computing/rendering files", () => {
    expect(STATE_DURATION_FILES.length).toBe(3);
  });

  for (const filePath of STATE_DURATION_FILES) {
    const relativePath = filePath.replace(`${SRC_DIR}/`, "src/");

    it(`${relativePath} exists and is readable`, () => {
      expect(() => readFileSync(filePath, "utf-8")).not.toThrow();
    });

    for (const { name, pattern } of ALL_PATTERNS) {
      it(`${relativePath} contains no: ${name}`, () => {
        const contents = readFileSync(filePath, "utf-8");
        expect(pattern.test(contents), `${relativePath} appears to contain: ${name}`).toBe(false);
      });
    }
  }
});
