/**
 * Architectural guard for the MacroChipz Analyst surface
 * (Increment #33).
 *
 * The risk here is subtler than in earlier guards. Previous features
 * risked React quietly re-deriving an economic value. This one adds a
 * component that renders GENERATED PROSE next to evidence -- so the new
 * failure mode is the frontend deciding what the model's answer means:
 * scoring it, filtering its evidence, guessing which citation is real,
 * or composing evidence the backend never validated.
 *
 * The rule is the same one ADR-021 set for curated explanations, now
 * extended to generated ones: explanations never determine canonical
 * results. React collects a question, names the page's context, and
 * renders what came back validated.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const SRC_DIR = join(dirname(fileURLToPath(import.meta.url)), "..");

function analystFiles(): string[] {
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
      const isAnalystFile =
        relativePath.includes("components/analyst/") ||
        relativePath.endsWith("api/analyst.ts") ||
        relativePath.endsWith("api/analyst.types.ts") ||
        relativePath.endsWith("lib/analystCopy.ts");
      if (isAnalystFile) found.push(full);
    }
  }

  walk(SRC_DIR);
  return found;
}

const FORBIDDEN_PATTERNS: ReadonlyArray<{ name: string; pattern: RegExp; allow?: RegExp }> = [
  {
    name: "arithmetic on economic values",
    pattern: /\b\w*(?:value|rate|change|spread|yield|state)\w*\s*[-+*/]\s*\w*(?:value|rate|change|spread|yield)\w*/i,
  },
  { name: "percentage or basis-point conversion", pattern: /[*/]\s*100\b/ },
  {
    name: "filtering or re-validating the evidence the backend already validated",
    pattern: /\bevidence\s*\.\s*(?:filter|find|some|every)\b/i,
  },
  {
    name: "a hand-rolled confidence or quality score for the answer",
    pattern: /\b(?:confidence|certainty|trustScore|qualityScore|reliability)\s*[=:]/i,
  },
  {
    name: "the frontend composing its own evidence entry",
    pattern: /evidence\s*[:=]\s*\[\s*\{/,
  },
  {
    name: "a canonical state literal decided in React",
    pattern: /=\s*["'](?:COOLING|HEATING|STRENGTHENING|MIXED|INSUFFICIENT_DATA)["']/,
  },
];

describe("the Analyst surface derives no economic meaning", () => {
  const files = analystFiles();

  it("scans the files it claims to scan", () => {
    const names = files.map((file) => relative(SRC_DIR, file));
    expect(names).toEqual(
      expect.arrayContaining([
        "api/analyst.ts",
        "api/analyst.types.ts",
        "lib/analystCopy.ts",
        "components/analyst/AskMacroChipz.tsx",
      ]),
    );
    expect(files.length).toBeGreaterThanOrEqual(4);
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

  it("never reaches for a methodology constant or recomputes a methodology", () => {
    for (const file of files) {
      const source = readFileSync(file, "utf8")
        .replace(/\/\*[\s\S]*?\*\//g, "")
        .replace(/^\s*\/\/.*$/gm, "");
      for (const fragment of ["annualiz", "NEUTRAL_BAND", "deadband", "DEADBAND", "50000", "50_000"]) {
        expect(source, `${relative(SRC_DIR, file)} must not mention ${fragment}`).not.toContain(fragment);
      }
    }
  });
});

describe("the browser never supplies canonical truth", () => {
  it("the request type carries no state, evidence, or numbers", () => {
    const types = readFileSync(join(SRC_DIR, "api/analyst.types.ts"), "utf8");
    const requestBlock = types.slice(types.indexOf("interface AnalystContextRef"));
    const contextRef = requestBlock.slice(0, requestBlock.indexOf("}"));

    for (const forbidden of ["state", "evidence", "value", "metric", "methodology", "packet"]) {
      expect(contextRef.toLowerCase()).not.toContain(forbidden);
    }
  });

  it("the client sends exactly a context reference and a question", () => {
    const client = readFileSync(join(SRC_DIR, "api/analyst.ts"), "utf8");
    expect(client).toMatch(/apiPost<AnalystExplainResponse>\(\s*["'][^"']+["'],\s*\{\s*context,\s*question\s*\}/);
  });

  it("no Analyst file posts to any endpoint other than the Analyst's own", () => {
    for (const file of analystFiles()) {
      const source = readFileSync(file, "utf8");
      const posts = [...source.matchAll(/apiPost<[^>]*>\(\s*["']([^"']+)["']/g)].map((match) => match[1]);
      for (const path of posts) {
        expect(path).toBe("/api/v1/analyst/explain");
      }
    }
  });
});

describe("suggested questions are deterministic UI copy", () => {
  it("are defined statically and never requested from the model", async () => {
    const copySource = readFileSync(join(SRC_DIR, "lib/analystCopy.ts"), "utf8");

    expect(copySource).not.toContain("askAnalyst");
    expect(copySource).not.toMatch(/\bfetch\s*\(/);
    expect(copySource).not.toContain("apiPost");
  });

  it("exist for every supported context", async () => {
    const { suggestedQuestions } = await import("../lib/analystCopy");
    for (const context of ["INFLATION", "LABOR", "RATES", "MONITOR_HISTORY"] as const) {
      expect(suggestedQuestions(context).length).toBeGreaterThan(0);
    }
  });
});

describe("the Analyst is optional at the UI layer", () => {
  it("every page passes availability in rather than assuming it", () => {
    for (const page of ["pages/Inflation.tsx", "pages/Jobs.tsx", "pages/Rates.tsx"]) {
      const source = readFileSync(join(SRC_DIR, page), "utf8");
      expect(source, `${page} must render the Analyst surface`).toContain("AskMacroChipz");
      expect(source, `${page} must gate it on availability`).toMatch(/available=\{[^}]*analyst[^}]*\}/);
    }
  });

  it("the Analyst is absent from Home and the product introduction, which stay purely canonical", () => {
    // #41: the live surface moved to `pages/Home.tsx`; the product
    // introduction it replaced is `pages/HomeIntro.tsx`.
    for (const page of ["pages/Home.tsx", "pages/HomeIntro.tsx"]) {
      const source = readFileSync(join(SRC_DIR, page), "utf8");
      expect(source).not.toContain("AskMacroChipz");
      expect(source).not.toContain("api/analyst");
    }
  });

  it("the surface renders an unavailable notice rather than throwing", () => {
    const component = readFileSync(join(SRC_DIR, "components/analyst/AskMacroChipz.tsx"), "utf8");
    expect(component).toMatch(/if\s*\(!available\)/);
    expect(component).toContain("UNAVAILABLE_COPY");
  });

  it("never exposes provider or configuration detail in user-facing copy", async () => {
    const copyModule = await import("../lib/analystCopy");
    const allCopy = (Object.values(copyModule) as unknown[])
      .filter((value): value is string => typeof value === "string")
      .join(" ")
      .toLowerCase();

    for (const leak of ["openai", "gpt", "api key", "api_key", "token", "environment variable", "llm"]) {
      expect(allCopy).not.toContain(leak);
    }
  });
});
