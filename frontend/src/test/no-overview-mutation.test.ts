/**
 * Architectural guard for Increment #19A: the Economic Overview
 * (`pages/Overview.tsx` and every `components/overview/*` file) must
 * remain completely read-only. It may only call the four existing
 * canonical read functions (`getInflationMonitor`/
 * `getInflationWhatChanged`/`fetchUpcomingReleases`/`fetchRecentReleases`)
 * -- never a sync/mutation endpoint, never AI, and never `fetch`
 * directly (every network call must go through an `api/*` client
 * module, the same discipline `no-release-sync-or-coupling.test.ts`
 * already enforces for release-calendar files).
 *
 * Deliberately narrow and separate from `no-release-sync-or-coupling.test.ts`:
 * that guard only scans files whose path contains "release" (so it
 * correctly skips `CurrentStateSection.tsx`/`WhatChangedPreview.tsx`/
 * `pages/Overview.tsx`, which legitimately import Inflation types) --
 * this guard instead scans every Overview file specifically, checking
 * a different, narrower property (no mutation, no AI, no direct
 * `fetch`) that applies to all of them regardless of which canonical
 * domain they present.
 */
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const SRC_DIR = join(dirname(fileURLToPath(import.meta.url)), "..");
const OVERVIEW_DIR = join(SRC_DIR, "components", "overview");
const OVERVIEW_PAGE = join(SRC_DIR, "pages", "Overview.tsx");

function collectOverviewFiles(dir: string): string[] {
  const files: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const fullPath = join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...collectOverviewFiles(fullPath));
      continue;
    }
    if (!/\.(ts|tsx)$/.test(entry.name)) continue;
    if (/\.test\.(ts|tsx)$/.test(entry.name)) continue; // exclude test files themselves
    files.push(fullPath);
  }
  return files;
}

const overviewFiles = [...collectOverviewFiles(OVERVIEW_DIR), OVERVIEW_PAGE];

// Import-specifier substrings that would indicate a mutation-capable
// or AI-capable dependency -- matches an actual module path, not any
// file that merely contains a similar word in prose.
const FORBIDDEN_IMPORT_SUBSTRINGS = ["services/ai", "/ai/", "api/ai", "services/news", "/news/"];

describe("Economic Overview is read-only", () => {
  it("scans at least the expected Overview files (guards against an empty/misconfigured scan)", () => {
    expect(overviewFiles.length).toBeGreaterThanOrEqual(5);
  });

  for (const filePath of overviewFiles) {
    const relativePath = filePath.replace(`${SRC_DIR}/`, "src/");
    const contents = readFileSync(filePath, "utf-8");

    it(`${relativePath} imports nothing AI/news-related`, () => {
      const importSpecifiers = [...contents.matchAll(/from\s+["']([^"']+)["']/g)].map((match) => match[1]);
      const violations = importSpecifiers.filter((specifier) =>
        FORBIDDEN_IMPORT_SUBSTRINGS.some((forbidden) => specifier?.includes(forbidden)),
      );
      expect(violations, `${relativePath} imports forbidden module(s): ${violations.join(", ")}`).toEqual([]);
    });

    it(`${relativePath} never references a sync or process endpoint`, () => {
      expect(contents).not.toMatch(/\/sync\b/);
      expect(contents).not.toMatch(/\/releases\/[^"'\s]*\/process\b/);
      expect(contents).not.toMatch(/\bsyncSeries\b|\bsync_series\b/);
    });

    it(`${relativePath} never calls fetch directly (network calls go through api/* client modules only)`, () => {
      expect(contents).not.toMatch(/\bfetch\s*\(/);
    });

    it(`${relativePath} contains no release-processing (#18) identifier -- deferred to #19B/#19C`, () => {
      expect(contents).not.toMatch(/ReleaseCheckRun|ReleaseObservationUpdate|ReleaseAnalysisUpdate/);
    });
  }

  it("Overview page imports only the four documented canonical read functions from api/*", () => {
    const contents = readFileSync(OVERVIEW_PAGE, "utf-8");
    const apiImportLines = contents
      .split("\n")
      .filter((line) => /from\s+["']\.\.\/api\//.test(line));
    const importedNames = apiImportLines.flatMap((line) => {
      const match = /\{([^}]+)\}/.exec(line);
      return match ? match[1]!.split(",").map((name) => name.trim()) : [];
    });
    const allowed = new Set([
      "getInflationMonitor",
      "getInflationWhatChanged",
      "fetchUpcomingReleases",
      "fetchRecentReleases",
      "useApiResource",
    ]);
    const violations = importedNames.filter((name) => name.length > 0 && !allowed.has(name));
    expect(violations, `pages/Overview.tsx imports an undocumented api function: ${violations.join(", ")}`).toEqual([]);
  });
});
