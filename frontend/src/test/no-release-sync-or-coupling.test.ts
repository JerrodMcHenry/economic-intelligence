/**
 * Architectural guard for Increment #17B: release-calendar frontend
 * code must never reference the sync endpoint -- the browser is
 * read-only for releases (see
 * docs/architecture/release-intelligence-v1.md #9: "External refresh
 * ... is a wholly separate, explicit write path ... never invoked
 * implicitly by a read") -- and must never import inflation-domain,
 * AI, or news code; release presentation is a separate, independent
 * surface from all three.
 *
 * Deliberately narrow (mirrors src/test/no-economic-logic.test.ts's
 * own scoping discipline): scans only the actual release-related
 * files, not every file in the project, and checks for specific
 * architectural paths/patterns rather than broad words that could
 * false-positive on harmless text.
 */
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const SRC_DIR = join(dirname(fileURLToPath(import.meta.url)), "..");

function collectReleaseFiles(dir: string): string[] {
  const files: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const fullPath = join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...collectReleaseFiles(fullPath));
      continue;
    }
    if (!/\.(ts|tsx)$/.test(entry.name)) continue;
    if (/\.test\.(ts|tsx)$/.test(entry.name)) continue; // exclude test files themselves
    if (!fullPath.toLowerCase().includes("release")) continue;
    files.push(fullPath);
  }
  return files;
}

// Import-specifier substrings, not bare words -- matches an actual
// module path a release file could import, not any file that merely
// contains a word like "container" or "domain" somewhere unrelated.
const FORBIDDEN_IMPORT_SUBSTRINGS = [
  "components/inflation",
  "api/inflation",
  "lib/inflationLabels",
  "services/ai",
  "/ai/",
  "services/news",
  "/news/",
];

describe("release calendar frontend code is read-only and self-contained", () => {
  const releaseFiles = collectReleaseFiles(SRC_DIR);

  it("scans at least the expected release-related files (guards against an empty/misconfigured scan)", () => {
    expect(releaseFiles.length).toBeGreaterThanOrEqual(5);
  });

  for (const filePath of releaseFiles) {
    const relativePath = filePath.replace(`${SRC_DIR}/`, "src/");
    const contents = readFileSync(filePath, "utf-8");

    it(`${relativePath} never references the release sync endpoint`, () => {
      expect(contents).not.toMatch(/\/releases\/sync/);
    });

    it(`${relativePath} imports nothing inflation/AI/news-related`, () => {
      const importSpecifiers = [...contents.matchAll(/from\s+["']([^"']+)["']/g)].map((match) => match[1]);
      const violations = importSpecifiers.filter((specifier) =>
        FORBIDDEN_IMPORT_SUBSTRINGS.some((forbidden) => specifier?.includes(forbidden)),
      );
      expect(violations, `${relativePath} imports forbidden module(s): ${violations.join(", ")}`).toEqual([]);
    });

    it(`${relativePath} contains no release-series-mapping identifier`, () => {
      expect(contents).not.toMatch(/ReleaseSeriesMapping|release[-_]series[-_]mapping/i);
    });
  }
});
