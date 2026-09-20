/**
 * Architectural guard (Increment #30): the Rates UI must never compute
 * a financial value.
 *
 * Every yield, spread, basis-point change, compensation figure and
 * percentile on the Rates page is computed by the deterministic backend
 * under `rates_v1.0`. The frontend formats and lays out those numbers;
 * it must not re-derive them, because a second implementation of the
 * methodology is a second methodology, and the two will disagree the
 * moment one changes.
 *
 * This is a source-text scan of the Rates-specific frontend files only
 * (a repo-wide scan would false-positive on unrelated presentational
 * arithmetic). It targets the shapes a real violation would take --
 * subtracting two rate-ish values, multiplying by 100 to reach basis
 * points, or writing a percentile/mean/ratio by hand.
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const SRC_DIR = join(dirname(fileURLToPath(import.meta.url)), "..");

/** Every Rates-specific source file, excluding tests. */
function ratesSourceFiles(): string[] {
  const files: string[] = [];
  const walk = (dir: string) => {
    for (const entry of readdirSync(dir)) {
      const path = join(dir, entry);
      if (statSync(path).isDirectory()) {
        walk(path);
        continue;
      }
      if (!/\.tsx?$/.test(entry) || /\.test\.tsx?$/.test(entry)) continue;
      const relativePath = relative(SRC_DIR, path);
      const isRatesFile =
        relativePath.includes("rates") || relativePath.includes("Rates") || relativePath.endsWith("ratesFormat.ts");
      if (isRatesFile) files.push(path);
    }
  };
  walk(SRC_DIR);
  return files;
}

const FORBIDDEN_PATTERNS: ReadonlyArray<{ name: string; pattern: RegExp; allow?: RegExp }> = [
  {
    // A spread or compensation: subtracting one value-bearing field from another.
    name: "subtraction of two rate-shaped values (a spread or compensation calculated client-side)",
    pattern:
      /\b\w*(value|yield|rate|nominal|real|long|short|compensation|spread|basis_points|latest)\w*\s*-\s*\w*(value|yield|rate|nominal|real|long|short|compensation|spread|basis_points|latest)\w*\b/i,
  },
  {
    // Percentage points -> basis points is the backend's conversion.
    name: "multiplication by 100 (a percentage-point to basis-point conversion)",
    pattern: /\*\s*100\b(?!\s*\))/,
    // `percentile * 100` is formatting an already-computed 0..1 rank for
    // display, the same class of operation as rendering 0.25 as "25%".
    allow: /(percentile|rank)\s*\*\s*100/i,
  },
  {
    name: "division by 100 (a basis-point to percentage-point conversion)",
    pattern: /\/\s*100\b/,
  },
  {
    name: "a hand-written percentile/rank computation",
    pattern: /\b(percentile|rank)\w*\s*=\s*[^;=]*\b(length|filter|reduce|sort)\b/i,
  },
  {
    name: "an average/mean computed client-side",
    pattern: /\breduce\s*\([^)]*\+[^)]*\)\s*\/\s*\w+\.length/,
  },
];

describe("the Rates UI performs no financial calculation", () => {
  const files = ratesSourceFiles();

  it("finds the Rates source files it is supposed to be guarding", () => {
    const names = files.map((file) => relative(SRC_DIR, file));
    expect(names).toEqual(expect.arrayContaining(["pages/Rates.tsx", "lib/ratesFormat.ts", "api/rates.ts"]));
    expect(files.length).toBeGreaterThanOrEqual(6);
  });

  it.each(FORBIDDEN_PATTERNS)("never contains $name", ({ pattern, allow }) => {
    const offenders: string[] = [];
    for (const file of files) {
      const source = readFileSync(file, "utf8");
      source.split("\n").forEach((line, index) => {
        // Strip comments (prose, not code) and string/JSX literals, so a
        // hyphenated identifier like "rates-nominal-heading" is never
        // mistaken for a subtraction.
        const code = line
          .replace(/\/\/.*$/, "")
          .replace(/^\s*\*.*$/, "")
          .replace(/"[^"]*"/g, '""')
          .replace(/'[^']*'/g, "''")
          .replace(/`[^`]*`/g, "``");
        if (!pattern.test(code)) return;
        if (allow?.test(code)) return;
        offenders.push(`${relative(SRC_DIR, file)}:${index + 1}: ${line.trim()}`);
      });
    }
    expect(offenders).toEqual([]);
  });

  it("renders only backend-supplied change values, never a locally computed delta", () => {
    // `change_basis_points` must be read from the response, never assigned.
    for (const file of files) {
      const source = readFileSync(file, "utf8");
      expect(source).not.toMatch(/change_basis_points\s*[:=]\s*[^,;)\s][^,;)]*[-+*/]/);
    }
  });
});
