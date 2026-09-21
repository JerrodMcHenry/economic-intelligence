import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  DEFAULT_THEME_PREFERENCE,
  PREFERS_DARK_QUERY,
  THEME_PREFERENCES,
  THEME_STORAGE_KEY,
  parseThemePreference,
  readThemePreference,
  resolveTheme,
  writeThemePreference,
  type ThemePreference,
} from "./theme";

//: The document moved from `index.html` into `src/root.tsx` when
//: React Router framework mode landed (#40). This test still checks
//: the script AS SHIPPED -- only its location changed.
const ROOT_TSX = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "..", "root.tsx"), "utf8");

/** The inline pre-paint script from root.tsx, verbatim. */
function prePaintScript(): string {
  const match = ROOT_TSX.match(/const THEME_BOOTSTRAP = `([\s\S]*?)`;/);
  if (!match?.[1]) throw new Error("root.tsx has no inline theme script");
  return match[1];
}

/**
 * Executes the real root.tsx script against a fake window/document,
 * returning the `data-theme` it applied -- so the pre-paint logic is
 * tested as shipped, not re-described.
 */
function runPrePaintScript({
  stored,
  storageThrows = false,
  systemDark,
  matchMediaThrows = false,
}: {
  stored: string | null;
  storageThrows?: boolean;
  systemDark: boolean;
  matchMediaThrows?: boolean;
}): { theme: string | undefined; colorScheme: string } {
  const root = { dataset: {} as Record<string, string>, style: { colorScheme: "" } };
  const fakeWindow = {
    localStorage: {
      getItem: (key: string) => {
        if (storageThrows) throw new Error("storage disabled");
        return key === THEME_STORAGE_KEY ? stored : null;
      },
    },
    matchMedia: (query: string) => {
      if (matchMediaThrows) throw new Error("no matchMedia");
      return { matches: query === PREFERS_DARK_QUERY && systemDark };
    },
  };
  new Function("window", "document", prePaintScript())(fakeWindow, { documentElement: root });
  return { theme: root.dataset.theme, colorScheme: root.style.colorScheme };
}

describe("theme preference", () => {
  afterEach(() => {
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  it("offers exactly Light, Dark, and System, defaulting to System", () => {
    expect(THEME_PREFERENCES).toEqual(["light", "dark", "system"]);
    expect(DEFAULT_THEME_PREFERENCE).toBe("system");
  });

  it("treats any unknown stored value as untrusted and falls back to System", () => {
    for (const raw of [null, undefined, "", "Dark", "blue", 1, {}, "system "]) {
      expect(parseThemePreference(raw)).toBe("system");
    }
    for (const valid of THEME_PREFERENCES) {
      expect(parseThemePreference(valid)).toBe(valid);
    }
  });

  it("persists and restores an explicit preference", () => {
    writeThemePreference("dark");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
    expect(readThemePreference()).toBe("dark");
  });

  it("degrades to System, never throwing, when storage is unavailable", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("SecurityError");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("QuotaExceededError");
    });
    expect(() => writeThemePreference("light")).not.toThrow();
    expect(readThemePreference()).toBe("system");
  });

  it("resolves System from the operating-system preference and explicit choices as-is", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
  });
});

describe("index.html pre-paint theme script", () => {
  it("reads the same storage key and media query as src/theme/theme.ts", () => {
    const script = prePaintScript();
    expect(script).toContain(JSON.stringify(THEME_STORAGE_KEY));
    expect(script).toContain(JSON.stringify(PREFERS_DARK_QUERY));
  });

  it("agrees with resolveTheme for every stored value and system preference", () => {
    const storedValues: Array<string | null> = [...THEME_PREFERENCES, null, "garbage"];
    for (const stored of storedValues) {
      for (const systemDark of [true, false]) {
        const expected = resolveTheme(parseThemePreference(stored) as ThemePreference, systemDark);
        const applied = runPrePaintScript({ stored, systemDark });
        expect(applied.theme, `stored=${String(stored)} systemDark=${systemDark}`).toBe(expected);
        expect(applied.colorScheme).toBe(expected);
      }
    }
  });

  it("still applies a theme when storage or matchMedia throw", () => {
    expect(runPrePaintScript({ stored: "dark", storageThrows: true, systemDark: true }).theme).toBe("dark");
    expect(runPrePaintScript({ stored: "dark", storageThrows: true, systemDark: false }).theme).toBe("light");
    expect(runPrePaintScript({ stored: null, systemDark: true, matchMediaThrows: true }).theme).toBe("light");
  });
});
