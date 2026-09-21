/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

/**
 * Vitest runs against its OWN Vite config, separate from the
 * application build (Increment #40).
 *
 * The two cannot share one config. `reactRouter()` injects a Fast
 * Refresh preamble through the HTML entry it owns; Vitest renders
 * components directly with no HTML entry, so the plugin's transform
 * throws "React Router Vite plugin can't detect preamble" and every
 * suite that imports a component through `AppShell` fails to collect.
 * Measured: 15 of 54 test files, before this split.
 *
 * So the application build uses `reactRouter()` (which provides its own
 * React transform, making `@vitejs/plugin-react` redundant there), and
 * the test build uses `@vitejs/plugin-react` (which provides the
 * transform without the routing machinery the tests do not need).
 * `@vitejs/plugin-react` is therefore still a required devDependency --
 * it simply moved from one config to the other.
 */
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    // The suite must not depend on the developer's shell. Several API
    // tests assert the REQUEST PATH (`/api/v1/releases`), which the
    // client prefixes with `VITE_API_BASE_URL` when it is set; and
    // `siteUrl.ts` reads `VITE_SITE_URL` at import time. Exporting
    // either variable -- as a release build does -- made 7 tests fail
    // while the code was correct. Pinning them empty makes the
    // unconfigured case the deterministic default; a test that needs
    // them SET stubs them explicitly (see
    // `src/lib/intelligenceMetadata.test.ts`).
    env: {
      VITE_API_BASE_URL: "",
      VITE_SITE_URL: "",
    },
    // No `globals: true` -- test files import `describe`/`it`/`expect`
    // explicitly from "vitest", consistent with this project's
    // preference for explicit imports over ambient test globals.
  },
});
