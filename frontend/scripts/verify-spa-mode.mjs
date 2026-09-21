/**
 * Framework-level regression guard for local development (#40A).
 *
 * #40 shipped a `loader` export on a route that is only prerendered
 * when an API is reachable. Every unit test passed, the release build
 * passed, and `npm run dev` died on its first request with:
 *
 *   Prerender: 1 invalid route export in `routes/intelligenceObject`
 *   when pre-rendering with `ssr:false`: `loader`.
 *
 * Nothing in a component test can see that, because the validation is
 * React Router's own and runs only when the dev server or the build
 * assembles the route manifest.
 *
 * This script reproduces the broken configuration -- `ssr: false` with
 * NO `VITE_API_BASE_URL`, so nothing is prerendered -- and asserts the
 * framework accepts it. It runs the real `react-router build`, so it
 * tests React Router's rule rather than our restatement of it in
 * `src/routes/ssrFalseExports.test.ts`.
 *
 * Deliberately a build and not a dev server: same validation, no port
 * to bind, no process to babysit, no timing to get wrong.
 */
import { spawnSync } from "node:child_process";

// The exact condition under which the route must NOT export a server
// `loader`. Emptying it is the point of this check, so it is emptied
// explicitly rather than inherited from whatever the shell holds.
const env = { ...process.env, VITE_API_BASE_URL: "", VITE_SITE_URL: "" };

console.log("[spa-mode] building with VITE_API_BASE_URL unset (local-development configuration)…");

const result = spawnSync("npx", ["react-router", "build"], {
  env,
  encoding: "utf8",
  stdio: ["ignore", "pipe", "pipe"],
});

const output = `${result.stdout ?? ""}${result.stderr ?? ""}`;

if (result.status !== 0) {
  console.error("[spa-mode] FAILED — the app cannot build (and therefore cannot `npm run dev`) without an API.");
  console.error(output.split("\n").filter((line) => /invalid|error|prerender/i.test(line)).join("\n") || output);
  process.exit(1);
}

// Belt and braces: the framework can report this without a non-zero
// exit in some code paths, so the text is checked too.
if (/Invalid route exports/i.test(output)) {
  console.error("[spa-mode] FAILED — React Router reported invalid route exports:");
  console.error(output.split("\n").filter((line) => /invalid/i.test(line)).join("\n"));
  process.exit(1);
}

console.log("[spa-mode] OK — `ssr: false` route exports are valid with nothing prerendered.");
