/**
 * Architectural guard for the measurement boundary (Increment #37).
 *
 * The risk this guards is specific and, unlike the economic guards
 * around it, mostly a privacy one. Analytics is the one subsystem
 * whose whole purpose is to send things elsewhere, so the moment a
 * component can reach a vendor SDK directly, two things stop being
 * true at once: the allowlist in `track()` stops being the only path
 * out, and "swap or remove the provider" stops being a one-file change.
 *
 * So the rule is narrow and structural: application code may import
 * `src/analytics` (the abstraction) and nothing deeper.
 *
 * Deliberately NOT guarded: test files reaching for the provider seam,
 * and the `src/analytics/` directory talking to itself. A guard that
 * forbade those would be brittle without protecting anything.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const SRC_DIR = join(dirname(fileURLToPath(import.meta.url)), "..");
const ANALYTICS_DIR = join(SRC_DIR, "analytics");

/**
 * Vendor analytics SDKs. Empty of real entries today because #37
 * deliberately shipped no provider -- the list exists so that adding
 * one has an obvious, single place to be declared, and so this guard
 * starts protecting it on the same commit.
 */
const PROVIDER_SDK_PACKAGES: ReadonlyArray<string> = [
  "plausible-tracker",
  "@plausible/tracker",
  "posthog-js",
  "@amplitude/analytics-browser",
  "mixpanel-browser",
  "@segment/analytics-next",
  "@vercel/analytics",
  "react-ga4",
  "@umami/node",
];

function sourceFiles(includeTests: boolean): string[] {
  const found: string[] = [];

  function walk(directory: string): void {
    for (const entry of readdirSync(directory)) {
      const full = join(directory, entry);
      if (statSync(full).isDirectory()) {
        walk(full);
        continue;
      }
      if (!/\.tsx?$/.test(full)) continue;
      const isTest = /\.test\.tsx?$/.test(full) || `${sep}test${sep}`.length > 0 && relative(SRC_DIR, full).startsWith(`test${sep}`);
      if (!includeTests && isTest) continue;
      found.push(full);
    }
  }

  walk(SRC_DIR);
  return found;
}

function importedSpecifiers(filePath: string): string[] {
  const source = readFileSync(filePath, "utf8");
  const specifiers: string[] = [];
  const pattern = /(?:from\s+|import\s*\(\s*)["']([^"']+)["']/g;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(source)) !== null) {
    const specifier = match[1];
    if (specifier !== undefined) specifiers.push(specifier);
  }
  return specifiers;
}

function isInsideAnalytics(filePath: string): boolean {
  return !relative(ANALYTICS_DIR, filePath).startsWith("..");
}

describe("analytics provider isolation", () => {
  it("keeps every vendor SDK out of application code", () => {
    const offenders: string[] = [];

    for (const file of sourceFiles(false)) {
      if (isInsideAnalytics(file)) continue;
      for (const specifier of importedSpecifiers(file)) {
        if (PROVIDER_SDK_PACKAGES.some((pkg) => specifier === pkg || specifier.startsWith(`${pkg}/`))) {
          offenders.push(`${relative(SRC_DIR, file)} imports ${specifier}`);
        }
      }
    }

    expect(offenders).toEqual([]);
  });

  it("never lets application code reach past the analytics abstraction", () => {
    const offenders: string[] = [];

    for (const file of sourceFiles(false)) {
      if (isInsideAnalytics(file)) continue;
      for (const specifier of importedSpecifiers(file)) {
        if (!specifier.includes("analytics")) continue;

        // Allowed: the directory itself (`../analytics`,
        // `../../analytics`). Forbidden: anything deeper, which would
        // mean a component naming a provider or a transport.
        const deeper = /analytics\/(?!index(?:\.[jt]sx?)?$).+/.test(specifier);
        if (deeper) offenders.push(`${relative(SRC_DIR, file)} imports ${specifier}`);
      }
    }

    expect(offenders).toEqual([]);
  });

  it("keeps the test-only provider seam out of application code", () => {
    const offenders: string[] = [];

    for (const file of sourceFiles(false)) {
      if (isInsideAnalytics(file)) continue;
      if (readFileSync(file, "utf8").includes("__setProviderForTests")) {
        offenders.push(relative(SRC_DIR, file));
      }
    }

    expect(offenders).toEqual([]);
  });

  it("does not re-export the provider module from the public analytics surface", () => {
    // `track` and `usePageViewed` are the surface. A component that can
    // import a provider can bypass the allowlist.
    const index = readFileSync(join(ANALYTICS_DIR, "index.ts"), "utf8");
    expect(index).not.toMatch(/export\s+\{[^}]*\bresolveProvider\b/);
    expect(index).not.toMatch(/export\s+\{[^}]*Provider\b[^}]*\}\s+from\s+["']\.\/provider["']/);
  });
});

describe("route vocabulary stays in step with the router", () => {
  it("has a route template for every path the application routes", () => {
    // If a route is added without a template, `page_viewed` silently
    // reports `unknown_route` and the new page becomes invisible to
    // measurement. Better to fail here than to discover it in the data.
    const app = readFileSync(join(SRC_DIR, "App.tsx"), "utf8");
    const events = readFileSync(join(ANALYTICS_DIR, "events.ts"), "utf8");

    // A COMPATIBILITY REDIRECT is not a page (#41). `<Route
    // path="labor" element={<Navigate to="/jobs" replace />} />`
    // renders nothing and immediately navigates away, so the reader is
    // measured at `/jobs` -- its destination -- and giving the old path
    // its own template would report a page view nobody ever saw.
    const routed = [...app.matchAll(/<Route\s+path="([^"]+)"\s+element=\{(<[A-Za-z]+)/g)]
      .filter((match) => match[2] !== "<Navigate")
      .map((match) => match[1])
      .filter((path): path is string => path !== undefined && path !== "*");

    expect(routed.length, "the route scan matched nothing -- the regex has drifted from App.tsx").toBeGreaterThan(0);

    const missing = routed.filter((path) => !events.includes(`"/${path}"`));
    expect(missing).toEqual([]);
  });
});
