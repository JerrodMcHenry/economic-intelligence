import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import App from "../App";
import { ThemeProvider } from "../theme/ThemeProvider";
import { THEME_STORAGE_KEY } from "../theme/theme";

/**
 * A controllable `prefers-color-scheme` -- jsdom has no matchMedia, so
 * each test decides what the operating system "prefers" and can flip
 * it mid-test to prove System mode follows live changes.
 */
function installSystemPreference(initiallyDark: boolean) {
  let dark = initiallyDark;
  const listeners = new Set<(event: MediaQueryListEvent) => void>();
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => ({
      get matches() {
        return query === "(prefers-color-scheme: dark)" && dark;
      },
      media: query,
      addEventListener: (_type: string, listener: (event: MediaQueryListEvent) => void) => listeners.add(listener),
      removeEventListener: (_type: string, listener: (event: MediaQueryListEvent) => void) => listeners.delete(listener),
    })),
  );
  return {
    setDark(next: boolean) {
      dark = next;
      act(() => {
        for (const listener of listeners) listener({ matches: next } as MediaQueryListEvent);
      });
    },
  };
}

function renderApp() {
  return render(
    // `ThemeProvider` lives in `root.tsx` in the real application
    // (#40). Supplied here so this harness matches production.
    <MemoryRouter initialEntries={["/"]}>
      <ThemeProvider>
        <App />
      </ThemeProvider>
    </MemoryRouter>,
  );
}

const appliedTheme = () => document.documentElement.dataset.theme;

describe("ThemeToggle", () => {
  beforeEach(() => {
    window.localStorage.clear();
    delete document.documentElement.dataset.theme;
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("is a labelled Light / Dark / System radio group with System selected by default", () => {
    installSystemPreference(false);
    renderApp();
    const group = screen.getByRole("group", { name: "Theme" });
    const options = within(group).getAllByRole("radio");
    expect(options.map((option) => option.getAttribute("value"))).toEqual(["light", "dark", "system"]);
    expect(within(group).getByRole("radio", { name: "Light" })).not.toBeChecked();
    expect(within(group).getByRole("radio", { name: "Dark" })).not.toBeChecked();
    expect(within(group).getByRole("radio", { name: "System" })).toBeChecked();
  });

  it("applies and persists an explicit Dark or Light choice", async () => {
    installSystemPreference(false);
    renderApp();
    const user = userEvent.setup();

    await user.click(screen.getByRole("radio", { name: "Dark" }));
    expect(appliedTheme()).toBe("dark");
    expect(document.documentElement.style.colorScheme).toBe("dark");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");

    await user.click(screen.getByRole("radio", { name: "Light" }));
    expect(appliedTheme()).toBe("light");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
  });

  it("restores a persisted preference on the next visit", () => {
    installSystemPreference(false);
    window.localStorage.setItem(THEME_STORAGE_KEY, "dark");
    renderApp();
    expect(screen.getByRole("radio", { name: "Dark" })).toBeChecked();
    expect(appliedTheme()).toBe("dark");
  });

  it("System follows the operating-system preference, including live changes", async () => {
    const system = installSystemPreference(true);
    renderApp();
    expect(appliedTheme()).toBe("dark");

    system.setDark(false);
    expect(appliedTheme()).toBe("light");

    // An explicit choice stops tracking the OS...
    const user = userEvent.setup();
    await user.click(screen.getByRole("radio", { name: "Dark" }));
    system.setDark(false);
    expect(appliedTheme()).toBe("dark");

    // ...and choosing System again resumes it (and is itself persisted).
    await user.click(screen.getByRole("radio", { name: "System" }));
    expect(appliedTheme()).toBe("light");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("system");
  });

  it("is operable from the keyboard", async () => {
    installSystemPreference(false);
    renderApp();
    const user = userEvent.setup();
    const system = screen.getByRole("radio", { name: "System" });
    system.focus();
    await user.keyboard("{ArrowLeft}");
    expect(screen.getByRole("radio", { name: "Dark" })).toBeChecked();
    expect(appliedTheme()).toBe("dark");
  });

  it("works without matchMedia support, treating the system preference as light", () => {
    vi.stubGlobal("matchMedia", undefined);
    renderApp();
    expect(appliedTheme()).toBe("light");
  });
});
