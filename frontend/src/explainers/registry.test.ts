/**
 * The explainer registry (Increment #44).
 *
 * Curated economic explanation is a different kind of content from
 * canonical intelligence, and these tests keep the boundary intact:
 * nothing here is generated, ranked, personalised, or allowed to claim
 * more than it can support.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { EXPLAINERS, EXPLAINER_PATHS, explainerById, explainerBySlug, explainersForConcept, explainersForWorld } from "./registry";

const HERE = dirname(fileURLToPath(import.meta.url));
const SOURCE = readFileSync(join(HERE, "registry.ts"), "utf8");
const CODE = SOURCE.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");

describe("identity", () => {
  it("gives every explainer a unique id and slug", () => {
    for (const key of ["id", "slug"] as const) {
      const values = EXPLAINERS.map((explainer) => explainer[key]);
      expect(new Set(values).size, key).toBe(values.length);
    }
  });

  it("uses no provider identifier as explainer identity", () => {
    // #38: identity is a MacroChipz concept, never a provider's series.
    for (const explainer of EXPLAINERS) {
      // Provider SERIES identifiers specifically. The word "treasury"
      // is the subject of an explainer, not an identity -- what must
      // never appear is a provider's own series code.
      for (const seriesId of ["PAYEMS", "UNRATE", "CPIAUCSL", "PCEPI", "UST_NOMINAL", "UST_REAL"]) {
        expect(explainer.id, seriesId).not.toContain(seriesId);
        expect(explainer.slug, seriesId).not.toContain(seriesId.toLowerCase());
      }
    }
  });

  it("uses URL-safe slugs that will not need changing", () => {
    for (const explainer of EXPLAINERS) {
      expect(explainer.slug, explainer.slug).toMatch(/^[a-z0-9-]+$/);
      expect(encodeURIComponent(explainer.slug)).toBe(explainer.slug);
    }
  });

  it("resolves by slug and by id", () => {
    expect(explainerBySlug("fed-and-mortgage-rates")?.id).toBe("explain.fed-and-mortgage-rates");
    expect(explainerById("explain.cpi-vs-pce")?.slug).toBe("cpi-vs-pce");
    expect(explainerBySlug("nope")).toBeUndefined();
  });
});

describe("the rabbit hole is curated, not computed", () => {
  it("resolves every related id to a real explainer", () => {
    const dangling: string[] = [];
    for (const explainer of EXPLAINERS) {
      for (const id of explainer.related) {
        if (!explainerById(id)) dangling.push(`${explainer.id} -> ${id}`);
      }
    }
    expect(dangling).toEqual([]);
  });

  it("never links an explainer to itself", () => {
    for (const explainer of EXPLAINERS) {
      expect(explainer.related, explainer.id).not.toContain(explainer.id);
    }
  });

  it("keeps the onward choice small rather than a feed", () => {
    for (const explainer of EXPLAINERS) {
      expect(explainer.related.length, explainer.id).toBeGreaterThan(0);
      expect(explainer.related.length, explainer.id).toBeLessThanOrEqual(4);
    }
  });

  it("is deterministic — the same explainer always offers the same next steps", () => {
    const first = explainerBySlug("fed-and-mortgage-rates")?.related;
    const second = explainerBySlug("fed-and-mortgage-rates")?.related;
    expect(first).toEqual(second);
  });

  it("implements no ranking, scoring, recommendation or personalisation", () => {
    for (const token of ["score", "rank", "popular", "trending", "recommend", "similar", "personal", "Math.random", "sort("]) {
      expect(CODE.toLowerCase(), token).not.toContain(token.toLowerCase());
    }
  });
});

describe("curated, never generated", () => {
  it("calls no model", () => {
    for (const token of ["openai", "anthropic", "chat.completions", "prompt", "generate"]) {
      expect(CODE.toLowerCase(), token).not.toContain(token);
    }
  });

  it("fetches nothing — an explanation needs no network", () => {
    for (const token of ["fetch(", "axios", "XMLHttpRequest", "useEffect", "import("]) {
      expect(CODE, token).not.toContain(token);
    }
  });

  it("interpolates no runtime value into its prose", () => {
    // A curated sentence that can embed a live number could contradict
    // the page it sits on. Scoped to the CONTENT: the path helper at
    // the foot of the module legitimately builds `/explain/${slug}`.
    const content = CODE.slice(CODE.indexOf("export const EXPLAINERS"), CODE.indexOf("const BY_SLUG"));
    expect(content).not.toMatch(/\$\{/);
  });

  it("computes no economic value", () => {
    for (const token of ["Math.abs", "Math.round", "annualized(", "* 100", "/ 100"]) {
      expect(CODE, token).not.toContain(token);
    }
  });
});

describe("what the content may and may not say", () => {
  // The prose a reader sees. `limitations` are excluded because they
  // legitimately DISCLAIM the things below -- "makes no forecast" is
  // not a forecast.
  const all = JSON.stringify(
    EXPLAINERS.map(({ limitations: _limitations, ...rest }) => rest),
  ).toLowerCase();

  it("makes no forecast", () => {
    for (const word of ["will rise", "will fall", "we expect", "forecast", "predict", "is likely to"]) {
      expect(all, word).not.toContain(word);
    }
  });

  it("claims no significance ranking", () => {
    for (const word of ["most important", "biggest", "critical", "shocking", "alarming"]) {
      expect(all, word).not.toContain(word);
    }
  });

  it("gives no financial advice", () => {
    for (const word of ["you should buy", "you should sell", "we recommend", "best time to"]) {
      expect(all, word).not.toContain(word);
    }
  });

  it("states a basis for every explainer", () => {
    for (const explainer of EXPLAINERS) {
      expect(["GENERAL_ECONOMICS", "MACROCHIPZ_METHODOLOGY", "INSTITUTIONAL_ROLE"]).toContain(explainer.basis);
    }
  });

  it("gives every explainer a question and a one-sentence answer", () => {
    for (const explainer of EXPLAINERS) {
      expect(explainer.question, explainer.id).toMatch(/\?$/);
      expect(explainer.answer.length, explainer.id).toBeGreaterThan(40);
    }
  });
});

describe("THE MORTGAGE CORRECTNESS BOUNDARY (#44 §9)", () => {
  const flagship = explainerBySlug("fed-and-mortgage-rates")!;

  /**
   * The fields that ASSERT things, excluding `misconception`.
   *
   * The distinction matters: an explainer correcting a false belief has
   * to be able to state the belief. "The common belief is that the Fed
   * sets mortgage rates outright" is the thing being corrected, not a
   * claim -- so it is tested separately, below.
   */
  const claims = JSON.stringify({
    answer: flagship.answer,
    whatItIs: flagship.whatItIs,
    howItWorks: flagship.howItWorks,
    whatThisMeansForYou: flagship.whatThisMeansForYou,
  }).toLowerCase();
  const text = claims;

  it("never asserts that the Fed sets mortgage rates", () => {
    expect(claims).not.toMatch(/fed (sets|determines|controls|dictates) (the )?mortgage/);
    // ...and answers the question directly.
    expect(flagship.answer.toLowerCase()).toContain("no.");
  });

  it("states the misconception only as a belief it goes on to correct", () => {
    const misconception = flagship.misconception ?? "";
    expect(misconception).toMatch(/common belief|people (think|believe)|is often (read|thought)/i);
    expect(misconception).toMatch(/it often does not work that way|does not/i);
  });

  it("never says the 10-year sets mortgage rates", () => {
    expect(text).not.toMatch(/10-year (sets|determines|controls)/);
    expect(text).not.toMatch(/treasury (sets|determines|controls) (the )?mortgage/);
  });

  it("never claims a fixed spread over the 10-year", () => {
    for (const claim of ["plus a fixed spread", "equals the 10-year", "tracks the 10-year exactly"]) {
      expect(text, claim).not.toContain(claim);
    }
  });

  it("never claims the Fed is unrelated to mortgage rates", () => {
    for (const claim of ["no effect", "unrelated", "nothing to do with"]) {
      expect(text, claim).not.toContain(claim);
    }
    // It must describe the INDIRECT relationship instead.
    expect(text).toContain("expect");
  });

  it("names more than one influence, so it cannot read as a single chain", () => {
    expect(flagship.howItWorks?.length ?? 0).toBeGreaterThanOrEqual(3);
    expect(text).toContain("lenders");
  });

  it("states that MacroChipz does not track mortgage rates", () => {
    expect(flagship.limitations?.join(" ")).toMatch(/does not track mortgage rates/);
  });

  it("quotes no survey statistic", () => {
    // The #35 misconception figure is grade-B evidence (n=400, a
    // lender-marketing survey via a trade publication). Documented in
    // the repo, but not strong enough to state publicly as fact -- and
    // the explainer does not need it.
    expect(JSON.stringify(flagship)).not.toMatch(/\d\d%/);
  });
});

describe("integration surfaces", () => {
  it("offers explainers for each active world", () => {
    for (const world of ["INFLATION", "JOBS", "RATES"] as const) {
      expect(explainersForWorld(world).length, world).toBeGreaterThan(0);
    }
  });

  it("matches explainers to concepts by source-neutral id", () => {
    expect(explainersForConcept("UST_NOMINAL_10Y").map((e) => e.slug)).toContain("fed-and-mortgage-rates");
    expect(explainersForConcept("us.unemployment-rate.sa.monthly").length).toBeGreaterThan(0);
    expect(explainersForConcept("not-a-concept")).toEqual([]);
  });

  it("exposes one permanent path per explainer", () => {
    expect(EXPLAINER_PATHS).toHaveLength(EXPLAINERS.length);
    expect(new Set(EXPLAINER_PATHS).size).toBe(EXPLAINERS.length);
    for (const path of EXPLAINER_PATHS) expect(path).toMatch(/^\/explain\/[a-z0-9-]+$/);
  });

  it("does not introduce Housing", () => {
    expect(JSON.stringify(EXPLAINERS)).not.toMatch(/housing/i);
  });
});
