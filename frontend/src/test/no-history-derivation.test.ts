/**
 * Architectural guard for the point-in-time intelligence history
 * experience (Increment #32).
 *
 * The temptation this guard exists to block is specific and real: once
 * a component holds both `value_then` and `value_today`, subtracting
 * them, or comparing them to decide whether something was "revised", is
 * two characters of work. Doing it would move a methodology decision
 * into React -- and worse, it would hide unit mismatches, which is
 * exactly how the backend's own first version of this comparison went
 * wrong (`labor_v1.0` reports PAYEMS in jobs while storage holds
 * thousands).
 *
 * So: the frontend renders `comparison`, `state_differs`,
 * `changed_input_count` and `status` verbatim. It never computes them.
 *
 * Same mechanics as `no-rates-calculation.test.ts` -- a per-line scan
 * with string literals stripped first, offenders collected with
 * file:line so a failure is actionable.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const SRC_DIR = join(dirname(fileURLToPath(import.meta.url)), "..");

/** Every non-test source file belonging to this feature. */
function historyFiles(): string[] {
  const found: string[] = [];

  function walk(directory: string): void {
    for (const entry of readdirSync(directory)) {
      const full = join(directory, entry);
      if (statSync(full).isDirectory()) {
        walk(full);
        continue;
      }
      if (!/\.tsx?$/.test(full) || /\.test\.tsx?$/.test(full)) continue;

      const relativePath = relative(SRC_DIR, full);
      const isHistoryFile =
        relativePath.includes("components/history/") ||
        relativePath.endsWith("api/monitorHistory.ts") ||
        relativePath.endsWith("api/monitorHistory.types.ts") ||
        relativePath.endsWith("api/useMonitorHistoryDetail.ts") ||
        relativePath.endsWith("lib/historyCopy.ts") ||
        relativePath.endsWith("lib/historyLabels.ts");
      if (isHistoryFile) found.push(full);
    }
  }

  walk(SRC_DIR);
  return found;
}

const FORBIDDEN_PATTERNS: ReadonlyArray<{ name: string; pattern: RegExp; allow?: RegExp }> = [
  {
    name: "subtraction of then/today or previous/new values",
    pattern: /\b\w*(?:then|today|previous|current|new)\w*\s*-\s*\w*(?:then|today|previous|current|new)\w*/i,
  },
  {
    name: "an equality comparison used to decide whether a value was revised",
    // The backend's `comparison` field is the only authority on this.
    pattern: /value_(?:then|today)\s*[!=]==?\s*\w*\.?value_(?:then|today)/,
  },
  {
    name: "a hand-computed count of changed inputs",
    pattern: /\b\w*(?:changed|revised|differs)\w*\s*=\s*[^;=]*\b(?:filter|reduce|length)\b/i,
    // Reading the backend's own count, or mapping over rows to render
    // them, is fine; deriving the count is not.
    allow: /changed_input_count|historical_inputs\.map|related_changes\.map/,
  },
  {
    name: "a state comparison deciding whether the conclusion differs",
    pattern: /\b(?:recorded|replayed|current)_?state\w*\s*[!=]==?\s*\w*_?state/i,
  },
  {
    name: "basis-point or percentage arithmetic",
    pattern: /[*/]\s*100\b/,
  },
  {
    name: "a hand-rolled replay verdict",
    // "MATCH"/"MISMATCH" must arrive from the backend, never be decided here.
    pattern: /=\s*["'](?:MATCH|MISMATCH|NOT_REPLAYABLE)["']/,
  },
];

describe("the history experience derives no economic meaning", () => {
  const files = historyFiles();

  it("scans the files it claims to scan", () => {
    const names = files.map((file) => relative(SRC_DIR, file));
    expect(names).toEqual(
      expect.arrayContaining([
        "api/monitorHistory.ts",
        "api/monitorHistory.types.ts",
        "api/useMonitorHistoryDetail.ts",
        "lib/historyCopy.ts",
        "lib/historyLabels.ts",
        "components/history/IntelligenceHistorySection.tsx",
        "components/history/HistoricalResultDetail.tsx",
        "components/history/ReplayStatusBadge.tsx",
      ]),
    );
    expect(files.length).toBeGreaterThanOrEqual(8);
  });

  it.each(FORBIDDEN_PATTERNS)("never contains $name", ({ pattern, allow }) => {
    const offenders: string[] = [];

    for (const file of files) {
      readFileSync(file, "utf8")
        .split("\n")
        .forEach((line, index) => {
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

  it("never re-runs a methodology or reaches for a domain constant", () => {
    const forbidden = [
      "annualiz",
      "neutral_band",
      "NEUTRAL_BAND",
      "deadband",
      "DEADBAND",
      "compute_series_momentum",
      "compute_labor_monitor",
      "50000",
      "50_000",
    ];
    for (const file of files) {
      const source = readFileSync(file, "utf8")
        .replace(/\/\*[\s\S]*?\*\//g, "")
        .replace(/^\s*\/\/.*$/gm, "");
      for (const fragment of forbidden) {
        expect(source, `${relative(SRC_DIR, file)} must not mention ${fragment}`).not.toContain(fragment);
      }
    }
  });
});

describe("replay status is presented as an integrity verdict, not an economic state", () => {
  it("colours replay outcomes from the feedback family only", () => {
    const source = readFileSync(join(SRC_DIR, "lib/historyLabels.ts"), "utf8");
    const classBlock = source.slice(source.indexOf("REPLAY_OUTCOME_CLASSES"));
    const classes = classBlock.slice(0, classBlock.indexOf("};"));

    // An economic-state token here would say "Cooling is success",
    // which `globals.css`'s hard rule exists to prevent.
    expect(classes).not.toMatch(/\bstate-(?:cool|warm|neutral|caution|unavailable)\b/);
    expect(classes).toMatch(/feedback-success/);
    expect(classes).toMatch(/feedback-error/);
  });

  it("gives every replay outcome a text label and a plain-language description", async () => {
    const { REPLAY_OUTCOME_DESCRIPTION, REPLAY_OUTCOME_LABEL } = await import("../lib/historyLabels");
    const outcomes = ["MATCH", "MISMATCH", "NOT_REPLAYABLE"] as const;

    for (const outcome of outcomes) {
      expect(REPLAY_OUTCOME_LABEL[outcome].length).toBeGreaterThan(0);
      expect(REPLAY_OUTCOME_DESCRIPTION[outcome].length).toBeGreaterThan(0);
    }
    // A mismatch must read as an integrity problem, not a market signal.
    expect(REPLAY_OUTCOME_DESCRIPTION.MISMATCH).toMatch(/integrity/i);
  });
});

describe("user-facing copy avoids database vocabulary", () => {
  it("never uses temporal-database terms in the copy module", async () => {
    const copy = await import("../lib/historyCopy");
    const allCopy = (Object.values(copy) as unknown[])
      .filter((value): value is string => typeof value === "string")
      .join(" ")
      .toLowerCase();

    for (const term of ["recorded_to", "recorded_from", "system-time", "temporal", "observation_version", "half-open", "bitemporal"]) {
      expect(allCopy).not.toContain(term);
    }
  });

  it("keeps the then and today headings permanently distinct", async () => {
    const { THEN_HEADING, TODAY_HEADING } = await import("../lib/historyCopy");

    expect(THEN_HEADING).not.toEqual(TODAY_HEADING);
    expect(THEN_HEADING.toLowerCase()).toContain("knew");
    expect(TODAY_HEADING.toLowerCase()).toContain("today");
    // Today's reconstruction must never be described as something
    // MacroChipz knew at the time.
    expect(TODAY_HEADING.toLowerCase()).not.toContain("knew");
  });

  it("discloses that stored data can be revised, and what reconstructed inputs do not prove", async () => {
    const { BACKFILL_DISCLOSURE, REVISION_DISCLOSURE } = await import("../lib/historyCopy");

    expect(REVISION_DISCLOSURE.toLowerCase()).toContain("revised");
    expect(BACKFILL_DISCLOSURE.toLowerCase()).toContain("cannot prove");
  });
});
