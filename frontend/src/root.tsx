/**
 * The MacroChipz document (Increment #40).
 *
 * This file replaces `index.html`, which React Router's framework mode
 * owns from here on. Everything the old document carried is ported
 * verbatim -- charset, viewport, favicon, colour-scheme, the default
 * description, and the pre-paint theme script -- because none of it was
 * incidental and losing any of it would be a visible regression.
 *
 * `<Meta />` and `<Links />` are where route-specific metadata lands.
 * A route module's `meta` export replaces the defaults below, which is
 * what gives a permanent intelligence page its own title, description
 * and Open Graph tags IN THE GENERATED HTML rather than after
 * hydration.
 */

/* oxlint-disable react/only-export-components --
   A React Router FRAMEWORK MODE route module is required by the
   framework to export `loader`, `clientLoader`, `meta` and
   `ErrorBoundary` beside its component; that is the route contract,
   not an accident of organisation. The rule guards Fast Refresh, a
   development-only convenience, and splitting these exports into
   another file would break the contract to satisfy it. */
import { Links, Meta, Outlet, Scripts, ScrollRestoration } from "react-router";

import { ThemeProvider } from "./theme/ThemeProvider";

import "./styles/globals.css";

/**
 * Applied before first paint, so a dark-theme reader never sees a light
 * flash. Mirrors `src/theme/theme.ts` (THEME_STORAGE_KEY +
 * resolveTheme); `src/theme/theme.test.ts` keeps the two in agreement.
 * Storage is untrusted: any failure falls back to the system
 * preference.
 *
 * Inlined as a string because it must execute before React hydrates --
 * the one place in this codebase where that is the correct tool.
 */
const THEME_BOOTSTRAP = `(function () {
  var preference = "system";
  try {
    var stored = window.localStorage.getItem("economic-intelligence:theme");
    if (stored === "light" || stored === "dark" || stored === "system") preference = stored;
  } catch (e) {}
  var dark = preference === "dark";
  if (preference === "system") {
    try {
      dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    } catch (e) {}
  }
  var root = document.documentElement;
  root.dataset.theme = dark ? "dark" : "light";
  root.style.colorScheme = dark ? "dark" : "light";
})();`;

export function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <meta charSet="UTF-8" />
        <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <meta name="color-scheme" content="light dark" />
        <Meta />
        <Links />
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOTSTRAP }} />
      </head>
      <body>
        {children}
        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  );
}

/**
 * Site-wide defaults. A route that exports its own `meta` replaces
 * these entirely -- React Router uses the LAST matching route's meta,
 * which is exactly the behaviour a permanent object page wants.
 */
export function meta() {
  return [
    { title: "MacroChipz — Economic Intelligence" },
    {
      name: "description",
      content:
        "MacroChipz turns trusted macroeconomic data into reproducible economic analysis — what changed, how conditions are evolving, and the evidence behind each conclusion.",
    },
  ];
}

export default function Root() {
  // Hoisted here from `App.tsx` in #40. Previously every route lived
  // inside `<App />`, so App could own it; the permanent intelligence
  // route is the first route OUTSIDE that tree, and theme is a
  // document-level concern rather than an App-level one.
  //
  // Prerender-safe: `readThemePreference` and `systemPrefersDark` both
  // guard their `window` access, so with no DOM at build time they fall
  // back to the documented default rather than throwing.
  return (
    <ThemeProvider>
      <Outlet />
    </ThemeProvider>
  );
}
