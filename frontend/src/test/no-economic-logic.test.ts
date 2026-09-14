/**
 * Architectural guard: the frontend foundation modules (api client,
 * layout, pages, components) must never reimplement backend economic
 * logic -- see docs/methodology/inflation-monitor-v1.0.md's
 * "Non-negotiable architecture" and this increment's own hard rules.
 *
 * Extended for Increment #16B (Inflation Monitor product UI): the new
 * inflation display components read `state`/`relationship`/`delta` and
 * other already-canonical fields straight off the API response -- they
 * must never re-derive them. The three patterns added below guard the
 * specific reimplementation shapes #16B call out:
 *   - subtracting a "current" value from a "previous" one instead of
 *     using the backend-provided `ChangeEvent.delta`,
 *   - the COOLING/HEATING pair-literal shape the backend's own
 *     DIVERGES-detection uses to derive a confirmation relationship,
 *   - declaring a function named after the backend's period-selection
 *     helpers (latest common/shared observation period) -- reading
 *     those fields off a response object is fine and does not match
 *     this pattern; only a client-side re-implementation would.
 *
 * Patterns are deliberately few and specific (not a broad repository
 * grep) -- each one targets a shape that could only plausibly appear
 * if backend calculation code were copied into TypeScript:
 *   - the compounded-annualization exponent shape `** (12 / n)` (or
 *     the `Math.pow` equivalent) that computes r_1m/r_3m/r_6m/r_12m,
 *   - the frozen 0.10 percentage-point neutral-band constant applied
 *     as boundary arithmetic (`r_12m - 0.10` / `r_12m + 0.10`),
 *   - client-side delta recomputation (`current... - previous...`),
 *   - the COOLING/HEATING pair-literal confirmation-relationship shape,
 *   - a declared function named after a backend period-selection helper.
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
  {
    name: "client-side delta recomputation (current... - previous... or vice versa)",
    pattern: /current\w*\s*-\s*previous\w*|previous\w*\s*-\s*current\w*/i,
  },
  {
    name: "COOLING/HEATING pair-literal confirmation-relationship derivation",
    pattern: /\[\s*["']COOLING["']\s*,\s*["']HEATING["']\s*\]|\[\s*["']HEATING["']\s*,\s*["']COOLING["']\s*\]/,
  },
  {
    name: "declared period-selection helper function (re-deriving a common/shared period client-side)",
    pattern: /(function\s+|const\s+)(findLatestCommonPeriod|find_latest_common_period|latestSharedObservationPeriod|latest_shared_observation_period)\b/,
  },
  // Increment #20E.2 -- the identical guard the backend's own
  // AST-level test applies (tests/test_labor_architecture.py::TestWhatChangedComparatorNeverKnowsLaborV1Methodology),
  // restated here as a regex-level check for the frontend: a
  // COMPARISON against the frozen labor_v1.0 deadband literals
  // (50,000 jobs / 0.2 percentage points) would mean condition/
  // momentum/unemployment-trend classification logic was reimplemented
  // client-side rather than reused from the backend's own already-
  // classified `condition`/`momentum`/`state` fields. Deliberately
  // requires an adjacent comparison operator (`<`/`>`/`<=`/`>=`) --
  // NOT a bare occurrence of the number -- so it never false-positives
  // on a test fixture mirroring the backend's own
  // `condition_deadband_jobs`/`unemployment_deadband_pp` response
  // fields (plain data, never a comparison) or a docstring mentioning
  // the values in prose.
  {
    name: "frozen 50,000-job condition/momentum deadband comparison",
    pattern: /[<>]=?\s*[-+]?\s*50[,_]?000\b/,
  },
  {
    name: "frozen 0.2pp unemployment-trend deadband comparison",
    pattern: /[<>]=?\s*[-+]?\s*0\.2\b/,
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
