/**
 * Architectural guard: the frontend foundation modules (api client,
 * layout, pages, components) must never reimplement backend economic
 * logic -- see docs/methodology/inflation-monitor-v1.0.md's
 * "Non-negotiable architecture" and this increment's own hard rules.
 *
 * Scoped narrowly and honestly to what exists right now: #16A adds no
 * inflation-specific display code at all (that's #16B), so this test
 * currently passes by verifying absence across the real foundation
 * source tree, not as a placeholder. It exists as a durable regression
 * guard -- once #16B adds inflation display components, an analogous,
 * similarly narrow guard should be added scoped to those new files
 * (see docs/architecture/current-architecture.md).
 *
 * Patterns are deliberately few and specific (not a broad repository
 * grep) -- each one targets a shape that could only plausibly appear
 * if backend calculation code were copied into TypeScript:
 *   - the compounded-annualization exponent shape `** (12 / n)` (or
 *     the `Math.pow` equivalent) that computes r_1m/r_3m/r_6m/r_12m,
 *   - the frozen 0.10 percentage-point neutral-band constant applied
 *     as boundary arithmetic (`r_12m - 0.10` / `r_12m + 0.10`).
 */
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const SRC_DIR = join(dirname(fileURLToPath(import.meta.url)), "..");

const FORBIDDEN_PATTERNS: ReadonlyArray<{ name: string; pattern: RegExp }> = [
  {
    name: "compounded-annualization exponent (** (12 / n))",
    pattern: /\*\*\s*\(?\s*12\s*\/\s*\d/,
  },
  {
    name: "Math.pow-based annualization (Math.pow(x, 12 / n))",
    pattern: /Math\.pow\([^)]*12\s*\//,
  },
  {
    name: "frozen 0.10pp neutral-band boundary arithmetic",
    pattern: /[-+]\s*0\.10\b/,
  },
];

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

describe("frontend foundation contains no economic calculation logic", () => {
  const sourceFiles = collectSourceFiles(SRC_DIR);

  it("scans at least the expected foundation modules (guards against an empty/misconfigured scan)", () => {
    expect(sourceFiles.length).toBeGreaterThanOrEqual(8);
  });

  for (const filePath of sourceFiles) {
    const relativePath = filePath.replace(`${SRC_DIR}/`, "src/");

    it(`${relativePath} contains no forbidden economic-formula pattern`, () => {
      const contents = readFileSync(filePath, "utf-8");
      for (const { name, pattern } of FORBIDDEN_PATTERNS) {
        expect(pattern.test(contents), `${relativePath} appears to contain: ${name}`).toBe(false);
      }
    });
  }
});
