/**
 * Architectural guard for Increment #23C (Relate V1), frozen by
 * docs/product/relate-composition-v1.md §35. Scoped narrowly to the
 * Relate implementation's own files -- `lib/relateComposition.ts`,
 * `components/overview/HowTheyRelate.tsx`, and
 * `components/labor/WhyLaborState.tsx` (the one existing file this
 * increment extends) -- deliberately NOT a whole-tree scan the way
 * `no-economic-logic.test.ts` is.
 *
 * This narrower scope is intentional, not an oversight: a whole-tree
 * bare-word scan for terms like "bullish"/"bearish" would re-trigger
 * the exact false positive #22B already found and fixed (this
 * project's own CORRECT, existing prose in components/labor/LaborHero.tsx
 * and lib/laborLabels.ts explicitly states the ABSENCE of that framing,
 * using the words themselves to do so). None of the three files this
 * guard scans has any legitimate reason to mention a regime/market
 * term or a cross-domain agreement word at all -- Confirmation
 * (components/inflation/WhyThisState.tsx) is a different file, outside
 * this guard's scope, and is the one place "confirms"/"diverges" are
 * legitimately about Core CPI vs. Core PCE. A bare match inside THIS
 * guard's three files is therefore unambiguous evidence of drift, not
 * a false positive risk.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const SRC_DIR = join(dirname(fileURLToPath(import.meta.url)), "..");

const RELATE_FILES = [
  "lib/relateComposition.ts",
  "components/overview/HowTheyRelate.tsx",
  "components/labor/WhyLaborState.tsx",
].map((relative) => join(SRC_DIR, relative));

// Regime/market labels -- absolute prohibition, no legitimate mention
// (correct or otherwise) belongs in these three files at all.
const REGIME_PATTERNS: ReadonlyArray<{ name: string; pattern: RegExp }> = [
  { name: "Goldilocks", pattern: /goldilocks/i },
  { name: "stagflation", pattern: /stagflation/i },
  { name: "soft landing", pattern: /soft landing/i },
  { name: "hard landing", pattern: /hard landing/i },
  { name: "bullish", pattern: /bullish/i },
  { name: "bearish", pattern: /bearish/i },
  { name: "risk-on", pattern: /risk-on/i },
  { name: "risk-off", pattern: /risk-off/i },
  { name: "recessionary", pattern: /recessionary/i },
  { name: "expansionary", pattern: /expansionary/i },
  { name: "healthy/favorable economy framing", pattern: /healthy economy|favorable environment|the economy is\b/i },
];

// Cross-domain agreement/divergence vocabulary, applied to Inflation
// vs. Labor -- legitimate only for Core CPI vs. Core PCE (a different
// file, out of this guard's scope) and never for these three.
// "agree"/"agreement" deliberately excludes "disagree"/"disagreement" --
// the latter is legitimate, existing, pre-#23C vocabulary describing
// when Employment and Unemployment (or, historically, Core CPI/Core
// PCE) send inconsistent signals (see components/labor/WhyLaborState.tsx's
// own pre-existing docstring, and content/explanations/labor.ts's MIXED
// explanation) -- a real and desired word, not the cross-domain
// "agreement" claim this guard exists to catch.
const AGREEMENT_PATTERNS: ReadonlyArray<{ name: string; pattern: RegExp }> = [
  { name: "agree/agreement (cross-domain claim, excluding the legitimate 'disagree(ment)')", pattern: /(?<!dis)agrees?\b|(?<!dis)agreement/i },
  { name: "confirm/confirmation", pattern: /confirms?\b|confirmation/i },
  { name: "diverge/divergence", pattern: /diverges?\b|divergence/i },
  { name: "contradict/contradiction", pattern: /contradicts?\b|contradiction/i },
];

const STATISTICAL_PATTERNS: ReadonlyArray<{ name: string; pattern: RegExp }> = [
  { name: "correlation identifier", pattern: /correlation/i },
  { name: "spread identifier", pattern: /\bspread\b/i },
  { name: "numeric threshold comparison (a smuggled-in significance/economic threshold)", pattern: /[<>]=?\s*[-+]?\s*\d/ },
];

const ARCHITECTURE_PATTERNS: ReadonlyArray<{ name: string; pattern: RegExp }> = [
  { name: "backend import (from an app/ path)", pattern: /from\s+["'](\.\.\/)*app\// },
  { name: "AI/LLM import", pattern: /\bopenai\b|\banthropic\b|\bllm\b/i },
  { name: "invented economic-methodology identifier (relate_v1.0 or similar)", pattern: /relate_v1\.0|relationship_v1\.0|composition_v1\.0/i },
];

const ALL_PATTERNS = [...REGIME_PATTERNS, ...AGREEMENT_PATTERNS, ...STATISTICAL_PATTERNS, ...ARCHITECTURE_PATTERNS];

describe("Relate V1 implementation contains no inference, no regime labels, no statistical/backend coupling", () => {
  it("scans exactly the three expected Relate implementation files", () => {
    expect(RELATE_FILES.length).toBe(3);
  });

  for (const filePath of RELATE_FILES) {
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
