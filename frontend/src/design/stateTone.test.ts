/**
 * Regression guard (Increment #27B): economic-state presentation must
 * stay semantically separate from generic success/error feedback.
 *
 * Economic states are domain-neutral classifications. Cooling inflation
 * is not universally "good" and a warming economy is not universally
 * "bad" -- so `state-cool` must never collapse into success/positive,
 * and `state-warm` must never collapse into error/negative, whether by a
 * tone map pointing at feedback classes, a CSS token aliasing a
 * feedback token, or two families quietly sharing identical values.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { inflationStateTone } from "../lib/inflationLabels";
import { employmentStateTone, laborStateTone, unemploymentStateTone } from "../lib/laborLabels";
import { TONES, TONE_BORDER_CLASSES, TONE_CLASSES, TONE_TEXT_CLASSES, type Tone } from "./stateTone";

const SRC_DIR = join(dirname(fileURLToPath(import.meta.url)), "..");
const GLOBALS_CSS = readFileSync(join(SRC_DIR, "styles", "globals.css"), "utf8");

const FEEDBACK_OR_VERDICT = /feedback|success|error|danger|positive|negative|good|bad|green|red/i;

/** `--mc-*` custom properties declared inside the first block matching `selector`. */
function themeBlock(selector: string): Map<string, string> {
  const start = GLOBALS_CSS.indexOf(`${selector} {`);
  if (start === -1) throw new Error(`no ${selector} block in globals.css`);
  const body = GLOBALS_CSS.slice(start, GLOBALS_CSS.indexOf("\n}", start));
  return new Map([...body.matchAll(/--mc-([\w-]+):\s*([^;]+);/g)].map((m) => [m[1]!, m[2]!.trim()]));
}

const LIGHT = themeBlock(":root");
const DARK = new Map([...LIGHT, ...themeBlock(':root[data-theme="dark"]')]);

describe("economic state tones are domain-neutral", () => {
  it.each(TONES)("the %s tone uses only its own state-%s tokens", (tone: Tone) => {
    for (const classes of [TONE_CLASSES[tone], TONE_TEXT_CLASSES[tone], TONE_BORDER_CLASSES[tone]]) {
      expect(classes).not.toMatch(FEEDBACK_OR_VERDICT);
      const colorTokens = classes.split(/\s+/).filter((cls) => /^(bg|text|ring|border)-(?!1$|inset$)/.test(cls));
      expect(colorTokens.length).toBeGreaterThan(0);
      for (const cls of colorTokens) {
        expect(cls, `${tone}: ${cls}`).toMatch(new RegExp(`^(bg|text|ring|border)-state-${tone}(-subtle|-line)?$`));
      }
    }
  });

  it("maps cool and warm to distinct, non-feedback presentations", () => {
    expect(TONE_CLASSES.cool).not.toEqual(TONE_CLASSES.warm);
    expect(TONE_CLASSES.cool).toContain("state-cool");
    expect(TONE_CLASSES.warm).toContain("state-warm");
  });

  it("never assigns a directional tone to a Labor state (improving/deteriorating are not verdicts either)", () => {
    // labor-ui-v1.md §8: Labor states, even EXPANDING/CONTRACTING or
    // IMPROVING/DETERIORATING, are presented as neutral classifications.
    const directional = new Set<Tone>(["cool", "warm"]);
    for (const state of ["STRENGTHENING", "COOLING", "STABLE", "MIXED", "INSUFFICIENT_DATA"] as const) {
      expect(directional.has(laborStateTone(state))).toBe(false);
    }
    for (const state of ["EXPANDING", "COOLING", "STABLE", "CONTRACTING", "RECOVERING", "INSUFFICIENT_DATA"] as const) {
      expect(directional.has(employmentStateTone(state))).toBe(false);
    }
    for (const state of ["IMPROVING", "DETERIORATING", "STABLE", "INSUFFICIENT_DATA"] as const) {
      expect(directional.has(unemploymentStateTone(state))).toBe(false);
    }
  });

  it("keeps Inflation's cool/warm tones tied to Cooling/Heating, and missing data never directional", () => {
    expect(inflationStateTone("COOLING")).toBe("cool");
    expect(inflationStateTone("HEATING")).toBe("warm");
    expect(inflationStateTone("INSUFFICIENT_DATA")).toBe("unavailable");
  });
});

describe("state tokens are defined independently of feedback tokens", () => {
  it.each([
    ["light", LIGHT],
    ["dark", DARK],
  ] as const)("%s theme: every state token is its own literal color, never a feedback alias", (_name, tokens) => {
    const stateEntries = [...tokens].filter(([name]) => name.startsWith("state-"));
    expect(stateEntries.length).toBe(TONES.length * 3);
    for (const [name, value] of stateEntries) {
      expect(value, name).toMatch(/^oklch\(/);
      expect(value, name).not.toMatch(/var\(/);
    }
  });

  it.each([
    ["light", LIGHT],
    ["dark", DARK],
  ] as const)("%s theme: no state token shares a value with any feedback token", (_name, tokens) => {
    const feedbackValues = new Set([...tokens].filter(([name]) => name.startsWith("feedback-")).map(([, value]) => value));
    expect(feedbackValues.size).toBeGreaterThan(0);
    for (const [name, value] of tokens) {
      if (name.startsWith("state-")) expect(feedbackValues.has(value), `${name} duplicates a feedback color`).toBe(false);
    }
    expect(tokens.get("state-cool")).not.toBe(tokens.get("feedback-success"));
    expect(tokens.get("state-warm")).not.toBe(tokens.get("feedback-error"));
  });

  it("binds each Tailwind state color to its own state variable", () => {
    for (const tone of TONES) {
      for (const suffix of ["", "-subtle", "-line"]) {
        expect(GLOBALS_CSS).toContain(`--color-state-${tone}${suffix}: var(--mc-state-${tone}${suffix});`);
      }
    }
  });
});

describe("no source file presents an economic state with feedback styling", () => {
  function sourceFiles(dir: string): string[] {
    return readdirSync(dir).flatMap((entry) => {
      const path = join(dir, entry);
      if (statSync(path).isDirectory()) return sourceFiles(path);
      return /\.(ts|tsx)$/.test(entry) && !/\.test\.tsx?$/.test(entry) ? [path] : [];
    });
  }

  it("never pairs a state-* class with a feedback-* class", () => {
    for (const file of sourceFiles(SRC_DIR)) {
      for (const line of readFileSync(file, "utf8").split("\n")) {
        const mixes = /\bstate-(cool|neutral|warm|caution|unavailable)\b/.test(line) && /\bfeedback-/.test(line);
        expect(mixes, `${relative(SRC_DIR, file)}: ${line.trim()}`).toBe(false);
      }
    }
  });
});
