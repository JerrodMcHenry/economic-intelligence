/**
 * Route export validity under `ssr: false` (Increment #40A regression
 * guard).
 *
 * WHAT WENT WRONG IN #40
 * ----------------------
 * The whole #40 suite passed, the production build passed, and
 * `npm run dev` still could not serve a single request. React Router
 * validates route exports against the rendering mode at DEV-SERVER and
 * BUILD time, not at unit-test time, so no component test could see it.
 *
 * The rule, read from the installed
 * `@react-router/dev@7.18.4` (`validateSsrFalsePrerenderExports`):
 *
 *   - `action` and `headers` are ALWAYS invalid when `ssr: false`.
 *   - `loader` is invalid unless the route is matched by a prerender
 *     path in THAT SAME invocation.
 *
 * Because a module's export list is static, "sometimes prerendered"
 * cannot be expressed in one module. #40A therefore ships two modules
 * and picks between them in `src/routes.ts`.
 *
 * These tests encode that rule directly, so re-adding a `loader` to the
 * client-side variant fails in milliseconds instead of at the next
 * person's `npm run dev`.
 */
import { describe, expect, it } from "vitest";

import * as clientVariant from "./intelligenceObject";
import * as prerenderedVariant from "./intelligenceObject.prerendered";

/** Exports React Router rejects outright whenever `ssr: false`. */
const ALWAYS_INVALID_UNDER_SSR_FALSE = ["action", "headers"] as const;

describe("the client-side variant (used by `npm run dev` and no-API builds)", () => {
  it("does NOT export `loader`", () => {
    // This is the #40A defect itself. This route is not prerendered in
    // that mode, so a `loader` export makes React Router throw
    // "Invalid route exports found when prerendering with `ssr:false`"
    // and kill the dev server on its first request.
    expect(Object.keys(clientVariant)).not.toContain("loader");
  });

  it("exports `clientLoader`, which is how it loads at all", () => {
    expect(typeof clientVariant.clientLoader).toBe("function");
  });

  it("exports nothing that is invalid under `ssr: false`", () => {
    for (const name of ALWAYS_INVALID_UNDER_SSR_FALSE) {
      expect(Object.keys(clientVariant), name).not.toContain(name);
    }
  });
});

describe("the prerendered variant (used only when the build prerenders this route)", () => {
  it("exports `loader`, which is what bakes HTML and metadata", () => {
    expect(typeof prerenderedVariant.loader).toBe("function");
  });

  it("ALSO exports `clientLoader`, for objects beyond the prerender cap", () => {
    // The prerender list is capped. An object outside the cap still
    // matches this route and must still load in the browser; with
    // `loader` alone React Router would look for a `.data` file the
    // build never wrote.
    expect(typeof prerenderedVariant.clientLoader).toBe("function");
  });

  it("exports nothing that is invalid under `ssr: false`", () => {
    for (const name of ALWAYS_INVALID_UNDER_SSR_FALSE) {
      expect(Object.keys(prerenderedVariant), name).not.toContain(name);
    }
  });
});

describe("the two variants cannot drift apart", () => {
  it("render the same page, from the same module", () => {
    expect(prerenderedVariant.default).toBe(clientVariant.default);
  });

  it("share meta, ErrorBoundary and clientLoader by re-export, not by copy", () => {
    expect(prerenderedVariant.meta).toBe(clientVariant.meta);
    expect(prerenderedVariant.ErrorBoundary).toBe(clientVariant.ErrorBoundary);
    expect(prerenderedVariant.clientLoader).toBe(clientVariant.clientLoader);
  });

  it("differ by exactly one export: `loader`", () => {
    const extra = Object.keys(prerenderedVariant).filter((key) => !Object.keys(clientVariant).includes(key));
    expect(extra).toEqual(["loader"]);
  });
});
