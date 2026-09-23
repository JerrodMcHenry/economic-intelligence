/**
 * BUILD-TIME ONLY. Not application code, and never bundled into the
 * client — it is imported solely by `react-router.config.ts` and
 * `src/routes.ts`, both of which React Router evaluates in Node before
 * a build or a dev server starts.
 *
 * Why this module exists (Increment #40A)
 * ---------------------------------------
 * Under `ssr: false`, React Router validates that a route exports
 * `loader` ONLY IF that route is matched by a prerender path in the
 * SAME invocation (`validateSsrFalsePrerenderExports`). A route module's
 * export list is static, so "sometimes prerendered" is not a thing a
 * single module can express.
 *
 * `src/routes.ts` therefore has to choose WHICH route module to use,
 * and its choice must agree exactly with the paths this build will
 * actually prerender. If the two ever disagree, the build fails with
 * React Router's "Invalid route exports" error — which is precisely the
 * #40A defect.
 *
 * Making both callers read the same memoized answer is what guarantees
 * they cannot disagree.
 */
import { EXPLAINER_PATHS } from "../explainers/registry";

/**
 * How many intelligence objects get permanent prerendered pages.
 *
 * Bounded on purpose. Build time scales with this number, and #39 can
 * currently produce ~1,900 objects, 97% of which are data-coverage
 * records rather than economic news. Prerendering all of them would be
 * a slow build producing thousands of thin pages -- which the Product
 * Constitution forbids independently.
 */
const MAX_PRERENDERED_OBJECTS = 25;

/**
 * Only these types get permanent pages for now.
 *
 * `RATES_MOVEMENT` is the #40 reference type: it is the only type whose
 * objects carry genuine per-observation provider provenance, a real
 * methodology, and deterministic historical context -- so it can
 * demonstrate See -> Understand -> Verify end to end without inventing
 * anything. Other types render correctly at the same route; they are
 * simply not prerendered yet.
 */
const PRERENDERED_TYPES = ["RATES_MOVEMENT"];

/**
 * Canonical public routes that are always prerendered (#41).
 *
 * Each gets real HTML with its own `<title>` and description. Their
 * BODIES are still the application shell -- these pages fetch in the
 * browser -- so this buys metadata and a non-empty document, not
 * crawlable economic content. See `catchall.tsx`.
 *
 * COMPATIBILITY ROUTES ARE DELIBERATELY ABSENT. `/overview`, `/labor`
 * and `/releases` still work for anyone holding an old link, but
 * prerendering them would put them in the sitemap and invite a crawler
 * to treat them as canonical alongside their successors -- which is
 * exactly the duplicate-URL problem the redirects exist to prevent.
 */
export const STATIC_PATHS = [
  "/",
  "/inflation",
  "/jobs",
  "/rates",
  "/housing",
  "/calendar",
  // The explainer index (#45B) and every explainer (#44). Finite,
  // code-defined and static, so unlike the world pages these prerender
  // with their ACTUAL CONTENT rather than an application shell --
  // which is what makes them findable.
  "/explain",
  ...EXPLAINER_PATHS,
  // The #46C story prototype. Static, data-free and therefore
  // prerenderable with its real content, exactly like an explainer.
  // It carries `robots: noindex` and a canonical pointing at
  // `/explain/fed-and-mortgage-rates`, so prerendering it buys a
  // reviewable page without creating a duplicate of the canonical
  // one. Removed when the prototype is accepted or dropped.
  "/story/fed-and-mortgage-rates",
];

let cached: Promise<string[]> | null = null;

/**
 * BUILD-TIME DATA BOUNDARY.
 *
 * Prerendering reads the live Structured Intelligence API, so the build
 * needs `VITE_API_BASE_URL` set to an ABSOLUTE url reachable from the
 * build machine. In the browser the same variable may be empty (the
 * frontend uses relative paths against its own origin); in Node there
 * is no origin to be relative to.
 *
 * Two behaviours, both deliberate:
 *
 * - **Unset** -> intelligence pages are NOT prerendered. The build
 *   succeeds and those routes render client-side. Honest, and it keeps
 *   `npm run dev` and frontend-only CI working with no database.
 * - **Set but unreachable/erroring** -> the build FAILS, loudly. A
 *   half-prerendered deploy that silently lost its permanent pages is
 *   worse than a build that stops and says so (#40 §12).
 *
 * Memoized: React Router asks for the path list more than once per
 * invocation, and `src/routes.ts` asks as well. One answer per process.
 */
export function intelligencePrerenderPaths(): Promise<string[]> {
  cached ??= discover();
  return cached;
}

async function discover(): Promise<string[]> {
  const base = (process.env.VITE_API_BASE_URL ?? "").trim().replace(/\/$/, "");
  if (!base) {
    console.warn(
      "[prerender] VITE_API_BASE_URL is not set — intelligence pages will NOT be prerendered and will " +
        "render client-side instead. Set it to an absolute API URL to prerender them.",
    );
    return [];
  }

  const paths: string[] = [];
  for (const type of PRERENDERED_TYPES) {
    const url = `${base}/api/v1/intelligence?type=${encodeURIComponent(type)}&limit=${MAX_PRERENDERED_OBJECTS}`;
    const response = await fetch(url, { signal: AbortSignal.timeout(30_000) });
    if (!response.ok) {
      throw new Error(
        `[prerender] ${url} returned ${response.status}. Refusing to build: a deploy missing its permanent ` +
          `intelligence pages is worse than a build that stops here.`,
      );
    }
    const body = (await response.json()) as { items: Array<{ id: string }> };
    for (const item of body.items) paths.push(`/intelligence/${encodeURIComponent(item.id)}`);
  }
  return paths.slice(0, MAX_PRERENDERED_OBJECTS);
}

/**
 * Whether THIS invocation will prerender at least one intelligence
 * page — and therefore whether the intelligence route may legally
 * export a server `loader`.
 *
 * Note this is deliberately not "is `VITE_API_BASE_URL` set". A
 * reachable API that currently holds no `RATES_MOVEMENT` objects
 * prerenders nothing, and in that case a `loader` export would be just
 * as invalid as it is in local development.
 */
export async function willPrerenderIntelligence(): Promise<boolean> {
  return (await intelligencePrerenderPaths()).length > 0;
}
