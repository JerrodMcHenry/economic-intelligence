import type { Config } from "@react-router/dev/config";

import { STATIC_PATHS, intelligencePrerenderPaths } from "./src/build/prerenderPaths";

/**
 * React Router framework mode, static output (Increment #40, ADR-039).
 *
 * `ssr: false` is deliberate and load-bearing: the build emits static
 * HTML only, the server bundle is discarded, and MacroChipz keeps its
 * existing static-site deployment with NO Node runtime in production.
 * Framework mode is adopted for prerendering and route metadata, not
 * for server rendering.
 *
 * The path list and the build-time data boundary live in
 * `src/build/prerenderPaths.ts`, because `src/routes.ts` has to read
 * the SAME answer to pick a route module — see #40A and that file's
 * header.
 */
export default {
  appDirectory: "src",
  ssr: false,
  async prerender() {
    return [...STATIC_PATHS, ...(await intelligencePrerenderPaths())];
  },
} satisfies Config;
