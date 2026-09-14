/**
 * Architectural guard for Increment #17C (Explainability & Economic
 * Education UX Foundation): the explanation system -- content and
 * components under `content/explanations/` and
 * `components/explanations/`, plus the one result-explanation
 * component `components/inflation/WhyThisState.tsx` -- is curated,
 * static, and deterministic. It must never become a second, competing
 * source of economic truth alongside the backend. See
 * docs/architecture/current-architecture.md's explanation-system
 * section and this increment's own stated principle:
 *
 *   "Explanations NEVER determine canonical results. Facts are
 *   sourced. Calculations are deterministic. Canonical classifications
 *   are deterministic. Explanations describe those results."
 *
 * `content/explanations/inflation.ts` and
 * `components/inflation/WhyThisState.tsx` are already covered by the
 * general recursive scans in `no-economic-logic.test.ts` (annualization
 * exponent, neutral-band arithmetic, delta recomputation, confirmation
 * pair-literal) and `content/explanations/releases.ts` /
 * `components/releases/ReleaseRow.tsx` are already covered by
 * `no-release-sync-or-coupling.test.ts` (no `/releases/sync` reference,
 * no inflation/AI/news import). This file adds the checks specific to
 * the explanation system itself and is deliberately narrow: it scans
 * only the explanation modules, not the whole repository.
 */
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const SRC_DIR = join(dirname(fileURLToPath(import.meta.url)), "..");

const EXPLANATION_DIRS = [
  join(SRC_DIR, "content", "explanations"),
  join(SRC_DIR, "components", "explanations"),
];
const EXPLANATION_EXTRA_FILES = [join(SRC_DIR, "components", "inflation", "WhyThisState.tsx")];

function collectSourceFiles(dir: string): string[] {
  const files: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const fullPath = join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...collectSourceFiles(fullPath));
      continue;
    }
    if (!/\.(ts|tsx)$/.test(entry.name)) continue;
    if (/\.test\.(ts|tsx)$/.test(entry.name)) continue; // exclude test files themselves
    files.push(fullPath);
  }
  return files;
}

const explanationFiles = [...EXPLANATION_DIRS.flatMap(collectSourceFiles), ...EXPLANATION_EXTRA_FILES];

// Import-specifier substrings that would indicate an AI/LLM dependency
// or a network call this static content system has no business making.
const FORBIDDEN_IMPORT_SUBSTRINGS = ["openai", "anthropic", "/ai/", "services/ai", "llm"];

// Non-type imports from api/* -- explanation modules may import API
// *types* (e.g. `SeriesMomentumResult`, `ScheduleStatus`) to describe
// the shape of evidence they display, but must never import an API
// *function* (fetch/mutate/sync) themselves; only page/container
// components own network calls.
const API_VALUE_IMPORT = /import\s+(?!type\s)\{[^}]*\}\s+from\s+["'][^"']*\/api\//;

describe("explanation system contains no AI dependency, no network calls, and no classification logic", () => {
  it("scans at least the expected explanation modules (guards against an empty/misconfigured scan)", () => {
    expect(explanationFiles.length).toBeGreaterThanOrEqual(5);
  });

  for (const filePath of explanationFiles) {
    const relativePath = filePath.replace(`${SRC_DIR}/`, "src/");
    const contents = readFileSync(filePath, "utf-8");

    it(`${relativePath} imports no AI/LLM module`, () => {
      const importSpecifiers = [...contents.matchAll(/from\s+["']([^"']+)["']/g)].map((match) => match[1]);
      const violations = importSpecifiers.filter((specifier) =>
        FORBIDDEN_IMPORT_SUBSTRINGS.some((forbidden) => specifier?.toLowerCase().includes(forbidden)),
      );
      expect(violations, `${relativePath} imports forbidden module(s): ${violations.join(", ")}`).toEqual([]);
    });

    it(`${relativePath} never calls the release sync endpoint or fetch/axios directly`, () => {
      expect(contents).not.toMatch(/\/releases\/sync/);
      expect(contents).not.toMatch(/\bfetch\s*\(/);
      expect(contents).not.toMatch(/\baxios\b/);
    });

    it(`${relativePath} imports only API types, never an API function`, () => {
      expect(API_VALUE_IMPORT.test(contents), `${relativePath} imports a non-type binding from api/`).toBe(false);
    });

    it(`${relativePath} never assigns into a prop/parameter object (no result mutation)`, () => {
      // Catches the shape of mutating a passed-in object, e.g.
      // `momentum.state = ...` or `explanation.title = ...`. Does not
      // flag `===`/`!==` comparisons (require a single `=` at the
      // match) or object-literal property definitions.
      expect(contents).not.toMatch(/\b\w+\.\w+\s=(?!=)/);
    });
  }
});
