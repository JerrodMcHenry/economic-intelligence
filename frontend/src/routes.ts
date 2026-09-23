/**
 * Route configuration (Increment #40, corrected in #40A).
 *
 * Deliberately incremental, following React Router's own
 * "Framework Adoption from Component Routes" guide: every existing
 * route keeps working through the catch-all, which renders the
 * unchanged `<App />` and its `<Routes>` tree. Routes graduate out of
 * the catch-all one at a time, when they need something framework mode
 * provides -- prerendering, or route-specific metadata.
 *
 * The permanent intelligence page is the first to graduate, because it
 * needs both.
 *
 * WHY THIS FILE IS ASYNC (#40A)
 * -----------------------------
 * Under `ssr: false`, React Router permits a `loader` export only on a
 * route that THIS invocation actually prerenders. A module's exports
 * are static, so the choice has to be made here, at config time, by
 * selecting a different module:
 *
 * - prerendering this run  -> `intelligenceObject.prerendered.tsx`
 *   (adds the build-time `loader` that bakes HTML and metadata)
 * - not prerendering       -> `intelligenceObject.tsx`
 *   (client-side only, which is what `npm run dev` and frontend-only
 *   CI need, and what serves any object beyond the prerender cap)
 *
 * Both modules render the identical page from the identical data; they
 * differ only in where the fetch happens. `RouteConfig` is typed
 * `ResolvedRouteConfig | Promise<ResolvedRouteConfig>`, so awaiting
 * here is supported rather than a workaround.
 */
import { type RouteConfig, route } from "@react-router/dev/routes";

import { willPrerenderIntelligence } from "./build/prerenderPaths";

const intelligenceModule = (await willPrerenderIntelligence())
  ? "routes/intelligenceObject.prerendered.tsx"
  : "routes/intelligenceObject.tsx";

export default [
  // Explainers (#44) are finite and code-defined, so every one is
  // prerendered -- see `src/build/prerenderPaths.ts`. No loader: the
  // content is in the bundle, so there is nothing to fetch and none of
  // #40A's `ssr: false` export constraints apply.
  // The explainer INDEX (#45B). Deliberately before the slug route so
  // `/explain` resolves to the index rather than to a missing slug.
  // Prerendered with real content, and deliberately NOT in primary
  // navigation -- see the module docstring for why.
  route("explain", "routes/explainerIndex.tsx"),
  route("explain/:slug", "routes/explainer.tsx"),
  // #46C PROTOTYPE. An ADDITIONAL route at its own URL — the
  // explainer above is untouched, still prerendered and still
  // canonical. Deleting this line and the module removes the
  // prototype completely, which is the point of putting it here
  // rather than inside `explainer.tsx` behind a flag.
  route("story/fed-and-mortgage-rates", "routes/story.fedMortgage.tsx"),
  route("intelligence/:intelligenceId", intelligenceModule),
  route("*?", "routes/catchall.tsx"),
] satisfies RouteConfig;
