/**
 * Light / Dark / System theme preference (Increment #27B,
 * docs/product/product-ui-ux-v1.md §17). Pure helpers only -- the React
 * wiring lives in ./ThemeProvider.tsx, and the pre-paint copy of
 * `resolveTheme` lives as an inline script in index.html (it must run
 * before the bundle loads to avoid a flash of the wrong theme; see
 * ./theme.test.ts, which keeps the two in agreement).
 *
 * `localStorage` is treated as untrusted input, mirroring
 * lib/sinceLastVisitCheckpoint.ts: a missing key, an unknown value, or
 * `getItem`/`setItem` throwing (private browsing, disabled storage)
 * all degrade to the safe default, `"system"` -- never a thrown error.
 *
 * Theme is purely presentational: it never changes which economic
 * state, label, or tone is shown, only the token values those tones
 * resolve to.
 */

export type ThemePreference = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

export const THEME_PREFERENCES: ReadonlyArray<ThemePreference> = ["light", "dark", "system"];

export const THEME_STORAGE_KEY = "economic-intelligence:theme";

export const DEFAULT_THEME_PREFERENCE: ThemePreference = "system";

export const PREFERS_DARK_QUERY = "(prefers-color-scheme: dark)";

export function parseThemePreference(raw: unknown): ThemePreference {
  return raw === "light" || raw === "dark" || raw === "system" ? raw : DEFAULT_THEME_PREFERENCE;
}

export function readThemePreference(): ThemePreference {
  try {
    return parseThemePreference(window.localStorage.getItem(THEME_STORAGE_KEY));
  } catch {
    return DEFAULT_THEME_PREFERENCE;
  }
}

export function writeThemePreference(preference: ThemePreference): void {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, preference);
  } catch {
    // Storage unavailable: the choice still applies for this session,
    // it simply isn't remembered -- strictly safer than failing.
  }
}

export function resolveTheme(preference: ThemePreference, systemPrefersDark: boolean): ResolvedTheme {
  if (preference === "system") return systemPrefersDark ? "dark" : "light";
  return preference;
}

export function systemPrefersDark(): boolean {
  try {
    return typeof window.matchMedia === "function" && window.matchMedia(PREFERS_DARK_QUERY).matches;
  } catch {
    return false;
  }
}

export function applyResolvedTheme(root: HTMLElement, theme: ResolvedTheme): void {
  root.dataset.theme = theme;
  root.style.colorScheme = theme;
}
