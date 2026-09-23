import { describe, expect, it } from "vitest";
import { existsSync } from "node:fs";
import { join } from "node:path";

import { ECONOMIC_WORLDS } from "../../worlds/registry";
import { IMAGE_CREDITS, WORLD_DISCOVERY, WORLD_IMAGERY } from "./worldImagery";

/**
 * THE RIGHTS RULE, AS A TEST (Increment #48).
 *
 * A photograph can be legally unusable in a way no layout, contrast or
 * accessibility test will ever notice. These assertions are the only
 * mechanism that turns "we checked the licence" from a review habit
 * into something that fails a build.
 */

const PUBLIC_DIR = join(process.cwd(), "public");

describe("world imagery", () => {
  it("covers every world in the registry, and nothing else", () => {
    expect(Object.keys(WORLD_IMAGERY).sort()).toEqual(ECONOMIC_WORLDS.map((w) => w.id).sort());
    expect(Object.keys(WORLD_DISCOVERY).sort()).toEqual(ECONOMIC_WORLDS.map((w) => w.id).sort());
  });

  it("every photograph carries a credit, an alt, a crop and reserved dimensions", () => {
    for (const [id, imagery] of Object.entries(WORLD_IMAGERY)) {
      if (imagery.treatment !== "photograph") continue;
      expect(imagery.credit.trim(), id).not.toBe("");
      expect(imagery.alt.trim(), id).not.toBe("");
      expect(imagery.objectPosition, id).toMatch(/%/);
      // Without these the box cannot be reserved, and the page shifts
      // when the bytes land.
      expect(imagery.width, id).toBeGreaterThan(0);
      expect(imagery.height, id).toBeGreaterThan(0);
    }
  });

  it("every photograph's files actually exist at the paths it names", () => {
    // A 404 renders as empty space rather than as an error, so a typo
    // here would ship silently.
    for (const [id, imagery] of Object.entries(WORLD_IMAGERY)) {
      if (imagery.treatment !== "photograph") continue;
      // Every candidate a browser could choose, in both formats. A
      // 404 renders as empty space rather than as an error, so a typo
      // in one descriptor would ship silently.
      const descriptors = [imagery.srcSet, imagery.webpSrcSet]
        .flatMap((set) => set.split(","))
        .map((part) => part.trim().split(" ")[0] ?? "");
      const sources = [imagery.src, ...descriptors];
      for (const source of sources) {
        expect(source.startsWith("/"), `${id}: ${source}`).toBe(true);
        expect(existsSync(join(PUBLIC_DIR, source)), `${id}: ${source}`).toBe(true);
      }
    }
  });

  it("the alt text describes the photograph and never the economy", () => {
    // An alt attribute is not a place to make an economic claim. A
    // photograph cannot show that anything rose, fell or is high.
    const forbidden = /\b(rising|falling|rose|fell|high|low|surge|plunge|boom|slump|crisis|recession)\b/i;
    for (const [id, imagery] of Object.entries(WORLD_IMAGERY)) {
      if (imagery.treatment !== "photograph") continue;
      expect(imagery.alt, id).not.toMatch(forbidden);
    }
  });

  it("names every credited archive in the full notice", () => {
    // The on-tile chip is a short form; the notice is the notice. The
    // Library of Congress's required line must appear in it verbatim.
    expect(IMAGE_CREDITS).toContain(
      "Photographs in the Carol M. Highsmith Archive, Library of Congress, Prints and Photographs Division",
    );
    for (const imagery of Object.values(WORLD_IMAGERY)) {
      if (imagery.treatment !== "photograph") continue;
      const archive = (imagery.credit.split(",")[0] ?? "").trim();
      expect(IMAGE_CREDITS).toContain(archive);
    }
  });

  it("says plainly that the worlds without a photograph have none", () => {
    // The gradients are not marked "placeholder" on the page, so the
    // notice is where that fact lives. If a fourth photograph is ever
    // added, this assertion is what forces the notice to be updated.
    const gradientWorlds = ECONOMIC_WORLDS.filter((w) => WORLD_IMAGERY[w.id].treatment === "gradient");
    for (const world of gradientWorlds) expect(IMAGE_CREDITS).toContain(world.label);
    expect(IMAGE_CREDITS).toMatch(/no photograph has been licensed/i);
  });

  it("states no figure, direction or date in a discovery line", () => {
    // These lines sit beside photographs on a page whose promise is
    // that every figure traces to a publisher. A number here would
    // trace to nothing.
    for (const [id, line] of Object.entries(WORLD_DISCOVERY)) {
      expect(line, id).not.toMatch(/\d/);
      expect(line.length, id).toBeLessThan(160);
    }
  });
});
