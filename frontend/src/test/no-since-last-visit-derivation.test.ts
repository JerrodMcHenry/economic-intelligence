/**
 * Architectural guards, Increment #25H: the Since Last Visit V1
 * frontend renders truth, it does not derive truth (contract §63 of
 * docs/product/since-last-visit-v1.md). Every guard here is a plain
 * source-text/AST inspection of the new module set -- no database, no
 * network, no component rendering.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const SRC_DIR = join(dirname(fileURLToPath(import.meta.url)), "..");

const SLV_FILES = [
  "api/sinceLastVisit.ts",
  "api/sinceLastVisit.types.ts",
  "api/useSinceLastVisit.ts",
  "lib/sinceLastVisitCheckpoint.ts",
  "lib/sinceLastVisitCopy.ts",
  "components/overview/SinceLastVisit.tsx",
].map((relative) => join(SRC_DIR, relative));

function read(relativePath: string): string {
  return readFileSync(join(SRC_DIR, relativePath), "utf-8");
}

// Strips block comments and line comments before a pattern check --
// this module's own docstrings correctly explain, in prose, exactly
// which browser APIs must never appear in the CODE below them;
// matching against raw source text (including comments) would
// false-positive on that explanatory prose itself.
function readCodeOnly(relativePath: string): string {
  return read(relativePath)
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "");
}

describe("Since Last Visit files exist where expected", () => {
  it("every frozen new file is present", () => {
    for (const filePath of SLV_FILES) {
      expect(() => readFileSync(filePath, "utf-8"), `expected ${filePath} to exist`).not.toThrow();
    }
  });
});

describe("no browser clock is ever used to construct a checkpoint value (contract §8/§10-13, hard requirement)", () => {
  it("lib/sinceLastVisitCheckpoint.ts contains no bare Date.now()/new Date()/performance.now() call", () => {
    const source = readCodeOnly("lib/sinceLastVisitCheckpoint.ts");
    expect(source).not.toMatch(/\bDate\.now\s*\(/);
    expect(source).not.toMatch(/\bnew\s+Date\s*\(/);
    expect(source).not.toMatch(/\bperformance\.now\s*\(/);
  });

  it("api/useSinceLastVisit.ts (the checkpoint-write orchestration) contains no bare Date.now()/new Date() either", () => {
    const source = readCodeOnly("api/useSinceLastVisit.ts");
    expect(source).not.toMatch(/\bDate\.now\s*\(/);
    expect(source).not.toMatch(/\bnew\s+Date\s*\(/);
  });

  it("the checkpoint module's only write function accepts its value as a parameter, never constructing one internally", () => {
    const source = read("lib/sinceLastVisitCheckpoint.ts");
    const match = /export function writeSinceLastVisitCheckpoint\(([^)]*)\)/.exec(source);
    expect(match).not.toBeNull();
    expect(match?.[1]).toMatch(/through/);
  });
});

describe("no transition/coverage/aggregation derivation on the frontend (contract §24-28 of the source prompt)", () => {
  it("no file compares previous_value/current_value to decide whether something changed", () => {
    for (const filePath of SLV_FILES) {
      const source = readFileSync(filePath, "utf-8");
      expect(source, filePath).not.toMatch(/previous_value\s*[!=]==?\s*current_value|current_value\s*[!=]==?\s*previous_value/);
    }
  });

  it("no file sorts or filters by evaluation_period to select a 'current' item (contract §26/§108 -- #25G already selected it)", () => {
    for (const filePath of SLV_FILES) {
      const source = readFileSync(filePath, "utf-8");
      expect(source, filePath).not.toMatch(/\.sort\s*\([^)]*evaluation_period/);
      expect(source, filePath).not.toMatch(/Math\.max\s*\([^)]*evaluation_period/);
    }
  });

  it("no file recomputes a RecalculationKind (FIRST_CALCULATION/UNCHANGED_CONFIRMATION) from raw values -- only renders the backend-provided kind", () => {
    for (const filePath of SLV_FILES) {
      const source = readFileSync(filePath, "utf-8");
      // Assigning/comparing a literal recalculation-kind string is fine
      // (rendering it); constructing one from a boolean expression is not.
      expect(source, filePath).not.toMatch(/=\s*\([^)]*\)\s*\?\s*["']FIRST_CALCULATION["']/);
    }
  });

  it("no file deduplicates or groups items by hand -- only .map()s over the already-grouped backend arrays", () => {
    for (const filePath of SLV_FILES) {
      const source = readFileSync(filePath, "utf-8");
      expect(source, filePath).not.toMatch(/new Set\(|\.reduce\s*\(/);
    }
  });

  it("no file ranks items by economic significance (no numeric magnitude sort, no severity/score literal)", () => {
    for (const filePath of SLV_FILES) {
      const source = readFileSync(filePath, "utf-8");
      expect(source, filePath).not.toMatch(/\bsignificance\b|\bseverity\b|\bimportance[Ss]core\b/);
      expect(source, filePath).not.toMatch(/\.sort\s*\([^)]*delta/);
    }
  });
});

describe("no forbidden imports anywhere in the new module set", () => {
  const FORBIDDEN_IMPORT_SUBSTRINGS = [
    "services/ai",
    "/ai/",
    "api/ai",
    "clients/fred",
    "api/inflation\"",
    "api/labor\"",
  ];

  it("imports nothing AI/provider-shaped", () => {
    for (const filePath of SLV_FILES) {
      const source = readFileSync(filePath, "utf-8");
      const importSpecifiers = [...source.matchAll(/from\s+["']([^"']+)["']/g)].map((match) => match[1]);
      const violations = importSpecifiers.filter((specifier) =>
        FORBIDDEN_IMPORT_SUBSTRINGS.some((forbidden) => specifier?.includes(forbidden)),
      );
      expect(violations, `${filePath} imports forbidden module(s): ${violations.join(", ")}`).toEqual([]);
    }
  });

  it("never calls fetch directly outside api/sinceLastVisit.ts (all network calls go through the typed client)", () => {
    for (const filePath of SLV_FILES) {
      if (filePath.endsWith("api/sinceLastVisit.ts")) continue; // owns apiGet, which itself wraps fetch
      const source = readFileSync(filePath, "utf-8");
      expect(source, filePath).not.toMatch(/\bfetch\s*\(/);
    }
  });

  it("no file references a write-capable backend call (add_recorded_monitor_result, process_occurrence, sync, etc.)", () => {
    for (const filePath of SLV_FILES) {
      const source = readFileSync(filePath, "utf-8");
      expect(source, filePath).not.toMatch(/\/sync\b|process_occurrence|add_recorded_monitor_result|run_maintenance/);
    }
  });
});

describe("no account/auth dependency anywhere in the new code (contract §97, V1 scope)", () => {
  it("no user/account/session identity reference", () => {
    for (const filePath of SLV_FILES) {
      const source = readFileSync(filePath, "utf-8");
      expect(source, filePath).not.toMatch(/user_id|account_id|session_id|Authorization|Bearer\s/);
    }
  });
});
