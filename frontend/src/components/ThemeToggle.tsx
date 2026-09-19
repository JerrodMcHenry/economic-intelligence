import type { ReactNode } from "react";

import { THEME_PREFERENCES, type ThemePreference } from "../theme/theme";
import { useTheme } from "../theme/themeContext";

const LABELS: Record<ThemePreference, string> = {
  light: "Light",
  dark: "Dark",
  system: "System",
};

const ICON_PATHS: Record<ThemePreference, ReactNode> = {
  light: (
    <>
      <circle cx="10" cy="10" r="3.25" />
      <path d="M10 2.5v1.5M10 16v1.5M2.5 10H4M16 10h1.5M4.7 4.7l1.06 1.06M14.24 14.24l1.06 1.06M4.7 15.3l1.06-1.06M14.24 5.76l1.06-1.06" />
    </>
  ),
  dark: <path d="M15.5 12.3A6.25 6.25 0 0 1 7.7 4.5a6.25 6.25 0 1 0 7.8 7.8Z" />,
  system: (
    <>
      <rect x="2.75" y="3.75" width="14.5" height="10" rx="1.5" />
      <path d="M7 16.75h6M10 13.75v3" />
    </>
  ),
};

/**
 * Light / Dark / System as a native radio group: arrow-key navigation,
 * a checked state screen readers announce, and a group name ("Theme")
 * all come from the platform rather than custom ARIA. Visually a
 * compact icon segment control; every option still carries a real
 * text name (visually hidden) plus a tooltip.
 */
export function ThemeToggle() {
  const { preference, setPreference } = useTheme();

  return (
    <fieldset className="flex items-center rounded-md border border-line bg-surface-secondary p-0.5">
      <legend className="sr-only">Theme</legend>
      {THEME_PREFERENCES.map((option) => (
        <label
          key={option}
          title={`${LABELS[option]} theme`}
          className="relative flex h-7 w-8 cursor-pointer items-center justify-center rounded-[5px] text-fg-muted transition-colors hover:text-fg has-[:checked]:bg-surface-elevated has-[:checked]:text-fg has-[:checked]:shadow-xs has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-1 has-[:focus-visible]:outline-focus motion-reduce:transition-none"
        >
          <input
            type="radio"
            name="theme-preference"
            value={option}
            checked={preference === option}
            onChange={() => setPreference(option)}
            className="sr-only"
          />
          <svg
            viewBox="0 0 20 20"
            aria-hidden="true"
            className="h-4 w-4"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            {ICON_PATHS[option]}
          </svg>
          <span className="sr-only">{LABELS[option]}</span>
        </label>
      ))}
    </fieldset>
  );
}
