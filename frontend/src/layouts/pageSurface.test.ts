import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { surfaceForPath } from "./pageSurface";

describe("page surfaces", () => {
  it("gives the homepage and the rebuilt worlds the cinematic surface", () => {
    expect(surfaceForPath("/")).toBe("cinematic");
    // #49B: Rates joins it. The audit found a reader crossing from the
    // homepage to `/rates` arrived somewhere that looked like a
    // different product. #50B: Inflation, for the same reason.
    expect(surfaceForPath("/rates")).toBe("cinematic");
    expect(surfaceForPath("/inflation")).toBe("cinematic");
    expect(surfaceForPath("/jobs")).toBe("cinematic");
  });

  it("gives every not-yet-rebuilt route no surface at all", () => {
    for (const path of ["/housing", "/calendar", "/explain", "/revisions"]) {
      expect(surfaceForPath(path), path).toBeUndefined();
    }
  });

  it("is owned by <main>, not simulated from inside the content column", () => {
    // #46F: a page faked a full-bleed background with a negative
    // margin that had nothing to cancel, and it dragged the background
    // up through the header's bottom border. The shell owns it now, and
    // this asserts the mechanism rather than the appearance.
    const shell = readFileSync(join(process.cwd(), "src", "layouts", "AppShell.tsx"), "utf8");
    expect(shell).toContain('<main id="main-content" data-surface={surface}');
    expect(shell).not.toMatch(/-m[xy]-\d/);
  });

  it("the cinematic surface's light is its own background, not a positioned element", () => {
    // It first shipped as a `::before` at `z-index: -1` and never
    // appeared: a negative z-index child paints inside the nearest
    // STACKING CONTEXT, which was the root, so it landed beneath
    // `<main>`'s opaque background. Painting it as the surface's own
    // background removes the problem instead of working around it --
    // and makes horizontal overflow impossible, because nothing is
    // positioned.
    // Comments stripped first: this file EXPLAINS the defect at length,
    // and a guard that a comment can trip is a guard nobody keeps.
    const css = readFileSync(join(process.cwd(), "src", "styles", "globals.css"), "utf8").replace(
      /\/\*[\s\S]*?\*\//g,
      "",
    );
    // The surface appears twice: once in the dark-palette selector
    // list, once as its own block. Anchor on the one that declares the
    // ground rather than on whichever comes first.
    const blocks = [...css.matchAll(/\[data-surface="cinematic"\] \{([^}]*)\}/g)];
    const ground = blocks.find((match) => match[1]?.includes("--lx-char:"));
    expect(ground, "no cinematic ground block").toBeDefined();
    const block = ground?.[1] ?? "";
    const scoped = css.slice(css.indexOf('[data-surface="cinematic"]'));
    expect(block).toContain("radial-gradient");
    expect(block).not.toContain("z-index");
    expect(block).not.toContain("position:");
    // And no rule under this surface reintroduces one.
    expect(scoped).not.toMatch(/\.lx-hero::before/);
    expect(scoped).not.toMatch(/z-index:\s*-/);
  });

  it("the header row can wrap, so a long row never becomes page overflow (#48A)", () => {
    // Measured at 768px BEFORE the fix: 705px of usable row against
    // 762px of content -- brand 171, navigation 441, theme-and-menu
    // 102, plus two 24px gaps -- on every page, not only this one.
    // Nothing shrank because `min-width: auto` is a flex item's
    // default and six nav links do not compress.
    //
    // The number that stops it recurring is not the 75px the tagline
    // freed. It is `flex-nowrap` being gone: an over-long row now
    // moves the navigation to a second line instead of widening the
    // document.
    const shell = readFileSync(join(process.cwd(), "src", "layouts", "AppShell.tsx"), "utf8");
    expect(shell).not.toContain("md:flex-nowrap");
    expect(shell).toContain("md:min-h-16");
    expect(shell).not.toContain("md:h-16");
    // The wordmark tagline is duplicated verbatim in the footer, so
    // holding it back until `lg` costs nothing and buys 75px.
    expect(shell).toMatch(/lg:inline">Economic Intelligence</);
  });
});
