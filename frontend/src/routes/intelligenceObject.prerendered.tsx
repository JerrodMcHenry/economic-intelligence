/**
 * The permanent intelligence page, PRERENDERED variant (Increment #40A).
 *
 * Identical to `./intelligenceObject` in every respect except one: it
 * additionally exports a server `loader`, which React Router runs in
 * Node at build time to bake the page's HTML and its metadata.
 *
 * `src/routes.ts` selects this module only when the build will actually
 * prerender at least one intelligence path. That condition is not
 * cosmetic — under `ssr: false` React Router REJECTS a `loader` export
 * on any route it is not prerendering, which is exactly the failure
 * #40A fixed. See `src/build/prerenderPaths.ts` for why both files read
 * one memoized answer.
 *
 * The page itself, its language, its metadata and its error states live
 * in the sibling module and are re-exported unchanged. Nothing is
 * duplicated, so the two variants cannot drift apart.
 */

/* oxlint-disable react/only-export-components --
   A React Router FRAMEWORK MODE route module is required by the
   framework to export `loader`, `clientLoader`, `meta` and
   `ErrorBoundary` beside its component; that is the route contract,
   not an accident of organisation. The rule guards Fast Refresh, a
   development-only convenience, and splitting these exports into
   another file would break the contract to satisfy it. */

import { type LoaderData, loadIntelligence } from "./intelligenceObject";

export { ErrorBoundary, clientLoader, meta } from "./intelligenceObject";
export { default } from "./intelligenceObject";

/**
 * Runs in Node AT BUILD TIME, for prerendered paths only.
 *
 * `ssr: false` means there is no request-time server, so this is not a
 * runtime data path — it is how a prerendered page gets its content and
 * its metadata into the HTML a crawler reads.
 *
 * `clientLoader` is exported alongside it deliberately. The prerender
 * list is capped (`MAX_PRERENDERED_OBJECTS`), so an object beyond the
 * cap still matches this route and must still load in the browser. With
 * `loader` alone, React Router would look for a `.data` file the build
 * never produced.
 */
export async function loader({ params }: { params: { intelligenceId?: string } }): Promise<LoaderData> {
  return loadIntelligence(params.intelligenceId ?? "");
}
