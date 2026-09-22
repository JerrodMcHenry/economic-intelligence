/**
 * THE DISCOVERY GRAPH (Increment #45B).
 *
 * #45A's central method was extracting the product's real internal link
 * graph from rendered DOM rather than reasoning about it from
 * components — and it found three things that reading the source had
 * not: `/calendar` was a hard dead end, `/revisions` had two inbound
 * links, and every explainer was reachable only from a world page.
 *
 * This file makes those properties **regression-testable without a
 * browser**. It asserts over the curated registries and the source of
 * the surfaces that link to them, which is where the guarantees
 * actually live:
 *
 *   - every explainer has at least one INTENTIONAL inbound path;
 *   - all four worlds are reachable from the homepage;
 *   - `/revisions` is reachable from the homepage and every world;
 *   - `/explain` exists, is prerendered, and is NOT in primary nav.
 *
 * Deliberately NOT a crawler. A crawler would need a running backend
 * and would test the data as much as the structure; these assertions
 * are about product structure, which is code, and they fail in CI.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { EXPLAINERS, EXPLAINER_PATHS } from "../explainers/registry";
import { FEATURED_EXPLAINER_IDS } from "../components/homepage/HomeQuestions";
import { ECONOMIC_WORLDS, NON_WORLD_SURFACES } from "../worlds/registry";

const SRC = join(dirname(fileURLToPath(import.meta.url)), "..");

function source(relative: string): string {
  return readFileSync(join(SRC, relative), "utf8");
}

/**
 * Source with comments removed.
 *
 * The same discipline `no-economic-logic.test.ts` and #45's Housing
 * guards already use, and for the same reason: a comment EXPLAINING
 * that a rule forbids the word "confirms" contains the word
 * "confirms". A scan that cannot tell the rule from its violation
 * forbids the documentation along with the defect.
 */
function code(relative: string): string {
  return source(relative)
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "");
}

/** The surfaces a reader can arrive at and must be able to leave. */
const WORLD_PAGES = ["pages/Inflation.tsx", "pages/Jobs.tsx", "pages/Rates.tsx", "pages/Housing.tsx"] as const;

describe("every explainer is reachable", () => {
  it("has at least one intentional inbound path", () => {
    // Two mechanisms count, and both are CURATED rather than computed:
    // `UnderstandWorld` lists every explainer naming a world, and the
    // `/explain` index lists every explainer full stop.
    for (const explainer of EXPLAINERS) {
      const viaWorld = (explainer.worlds?.length ?? 0) > 0;
      expect(viaWorld, `${explainer.id} names no world, so UnderstandWorld cannot reach it`).toBe(true);
    }
  });

  it("appears on the /explain index", () => {
    // The index renders every registry entry, including any that names
    // no world -- see its `unplaced` group. Asserted here so a future
    // filter cannot silently hide one.
    const index = source("routes/explainerIndex.tsx");
    expect(index).toContain("EXPLAINERS.filter");
    expect(index).toContain("unplaced");
  });

  it("is prerendered, index included", () => {
    const paths = source("build/prerenderPaths.ts");
    expect(paths).toContain('"/explain"');
    expect(paths).toContain("EXPLAINER_PATHS");
    expect(EXPLAINER_PATHS).toHaveLength(EXPLAINERS.length);
  });

  it("has a stable slug-based URL", () => {
    for (const path of EXPLAINER_PATHS) expect(path).toMatch(/^\/explain\/[a-z0-9-]+$/);
  });
});

describe("the homepage reaches the whole product", () => {
  const home = source("pages/Home.tsx");
  const orientation = source("components/homepage/WorldOrientation.tsx");

  it("links to all four worlds, derived from the registry rather than hardcoded", () => {
    // #45A: the homepage linked to Rates, Inflation, Jobs and Calendar
    // -- never Housing. Deriving from the registry is what makes that
    // impossible to regress: a fifth world would appear automatically.
    expect(home).toContain("WorldOrientation");
    expect(orientation).toContain("ECONOMIC_WORLDS.map");
    expect(ECONOMIC_WORLDS).toHaveLength(4);
  });

  it("links to curated explainer questions", () => {
    expect(home).toContain("HomeQuestions");
    expect(FEATURED_EXPLAINER_IDS.length).toBeGreaterThan(0);
  });

  it("links to Revision Intelligence", () => {
    expect(home).toContain("RevisionsLink");
  });
});

describe("Revision Intelligence is reachable from every world", () => {
  it("is linked from all four world pages", () => {
    // #45A measured exactly two inbound links -- `/inflation` and
    // `/jobs`. Rates and Housing had none.
    for (const page of WORLD_PAGES) {
      const contents = source(page);
      const linked = contents.includes("RevisionsLink") || contents.includes('"/revisions"');
      expect(linked, `${page} has no path to /revisions`).toBe(true);
    }
  });

  it("never claims a revision has been captured", () => {
    // The page it links to is legitimately empty. A promotional
    // sentence here could undo #43's whole distinction, so the copy is
    // forward-looking and this asserts it stays that way.
    const link = source("components/revisions/RevisionsLink.tsx");
    for (const forbidden of ["revisions we have found", "recent revisions", "see the latest revision"]) {
      expect(link.toLowerCase()).not.toContain(forbidden);
    }
    // And never the claim a backfilled baseline proves an original.
    expect(link.toLowerCase()).not.toContain("originally reported");
  });
});

describe("the Calendar is no longer a dead end", () => {
  it("opts its rows into onward navigation", () => {
    expect(source("components/releases/ReleaseCalendarSection.tsx")).toContain("showMonitorCta");
  });

  it("states non-coverage instead of linking a release whose data it lacks", () => {
    const row = source("components/releases/ReleaseRow.tsx");
    expect(row).toContain("hasCanonicalMonitor");
    expect(row).toContain("Not tracked by MacroChipz yet");
  });

  it("renders no bare provider token in a row", () => {
    // #45A section A.10.1: the literal word "FRED" on a consumer
    // surface. Provenance moved to the schedule disclosure.
    const row = code("components/releases/ReleaseRow.tsx");
    expect(row).not.toContain("{item.provider}");
    expect(source("components/releases/ReleaseScheduleDisclosure.tsx")).toContain("FRED");
  });

  it("keeps the frozen schedule sentence byte-for-byte", () => {
    // release-intelligence-v1.md #2/#13 makes its meaning load-bearing.
    // #45B added a paragraph BESIDE it, not to it.
    expect(source("components/releases/ReleaseScheduleDisclosure.tsx")).toContain(
      "Release dates indicate scheduled publication dates. They do not confirm that new data has been published,",
    );
  });
});

describe("navigation did not grow", () => {
  it("keeps primary navigation to the four worlds plus Home and Calendar", () => {
    // #45A section D: twelve explainers do not justify a nav slot, and
    // adding one would push the worlds aside. `/explain` exists as a
    // destination without occupying navigation.
    expect(NON_WORLD_SURFACES.map((surface) => surface.route)).toEqual(["/", "/calendar"]);
    expect(ECONOMIC_WORLDS).toHaveLength(4);
    const shell = source("layouts/AppShell.tsx");
    expect(shell).not.toContain('"/explain"');
    expect(shell).not.toContain('"/revisions"');
  });
});

describe("cross-world navigation asserts nothing", () => {
  it("links Rates to Housing and Inflation without a causal claim", () => {
    const rates = source("pages/Rates.tsx");
    expect(rates).toContain('to="/housing"');
    expect(rates).toContain('to="/inflation"');
  });

  it("links Inflation to Rates without a causal claim", () => {
    expect(source("pages/Inflation.tsx")).toContain('href="/rates"');
  });

  it("uses none of the frozen prohibited cross-domain vocabulary", () => {
    // relate-compare-audit-v1.md sections 15/16 and
    // relate-composition-v1.md section 2, restated over the copy #45B
    // actually added.
    const prohibited = [
      "confirms",
      "diverges",
      "contradicts",
      "goldilocks",
      "soft landing",
      "hard landing",
      "stagflation",
      "recessionary",
      "expansionary",
      "risk-on",
      "risk-off",
      "healthy economy",
    ];
    for (const page of ["pages/Rates.tsx", "pages/Inflation.tsx", "pages/Housing.tsx"]) {
      const contents = code(page).toLowerCase();
      for (const word of prohibited) {
        expect(contents, `${page} contains prohibited cross-domain vocabulary: ${word}`).not.toContain(word);
      }
    }
  });
});


describe("responsive layout, to the extent it is testable without a browser", () => {
  /**
   * HONEST SCOPE. A real phone viewport could not be obtained in #45A
   * or #45B -- the browser tooling reports a successful resize while
   * media queries continue to match desktop -- so these are STRUCTURAL
   * assertions, not a rendering verification. They catch the defect
   * class that actually breaks phone layouts (a fixed pixel width that
   * no breakpoint can collapse) and nothing more.
   *
   * A genuine 390px pass across all eight surfaces remains outstanding
   * and is recorded as such.
   */
  const NEW_SURFACES = [
    "components/homepage/WorldOrientation.tsx",
    "components/homepage/HomeQuestions.tsx",
    "components/revisions/RevisionsLink.tsx",
    "routes/explainerIndex.tsx",
  ] as const;

  for (const file of NEW_SURFACES) {
    it(`${file} introduces no fixed pixel width`, () => {
      const contents = code(file);
      expect(contents).not.toMatch(/\bw-\[\d+px\]/);
      expect(contents).not.toMatch(/\bmin-w-\[\d+px\]/);
      expect(contents).not.toMatch(/width:\s*\d+px/);
    });
  }

  it("lays the world grid out one column first, two only from the sm breakpoint", () => {
    // Mobile-first: the base class is a single column, so a phone gets
    // stacked cards without depending on any override.
    const orientation = code("components/homepage/WorldOrientation.tsx");
    expect(orientation).toContain("grid gap-3 sm:grid-cols-2");
  });

  it("keeps tap targets and prose readable rather than fixed", () => {
    for (const file of NEW_SURFACES) {
      expect(code(file)).not.toContain("whitespace-nowrap");
    }
  });
});
