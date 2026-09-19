import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import { ThemeContext } from "./themeContext";
import {
  PREFERS_DARK_QUERY,
  applyResolvedTheme,
  readThemePreference,
  resolveTheme,
  systemPrefersDark,
  writeThemePreference,
  type ThemePreference,
} from "./theme";

/**
 * Owns the user's theme preference for the whole app. The initial
 * `data-theme` attribute is already set before first paint by
 * index.html's inline script; this provider takes over from there --
 * keeping the attribute in sync with the chosen preference and, while
 * the preference is "system", with live `prefers-color-scheme` changes.
 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [preference, setPreferenceState] = useState<ThemePreference>(readThemePreference);
  const [prefersDark, setPrefersDark] = useState<boolean>(systemPrefersDark);

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const query = window.matchMedia(PREFERS_DARK_QUERY);
    const onChange = (event: MediaQueryListEvent) => setPrefersDark(event.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  const resolvedTheme = resolveTheme(preference, prefersDark);

  useEffect(() => {
    applyResolvedTheme(document.documentElement, resolvedTheme);
  }, [resolvedTheme]);

  const setPreference = useCallback((next: ThemePreference) => {
    setPreferenceState(next);
    writeThemePreference(next);
  }, []);

  const value = useMemo(() => ({ preference, resolvedTheme, setPreference }), [preference, resolvedTheme, setPreference]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
