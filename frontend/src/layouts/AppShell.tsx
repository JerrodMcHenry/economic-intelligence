import { useState, type KeyboardEvent } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";

import { usePageViewed } from "../analytics";
import { ECONOMIC_WORLDS } from "../worlds/registry";
import { PageContainer } from "../components/PageContainer";
import { ThemeToggle } from "../components/ThemeToggle";

/**
 * The shared MacroChipz application shell (Increment #27B): skip link,
 * a header with the brand, primary navigation, and theme control, the
 * main landmark rendering the active route, and a quiet footer. It owns
 * the global background, the single content width (PageContainer), page
 * spacing, and responsive navigation -- pages render only their content.
 *
 * Navigation lists only real, implemented destinations -- no
 * placeholders for future domains. #27A §11 froze five; Rates joins
 * them in #30 because the domain now genuinely exists (rates_v1.0,
 * shipped in #29), which is exactly the condition §11 set for adding
 * a nav slot: content first, then the IA commitment.
 * Below the `md` breakpoint the same single list collapses behind a
 * disclosure button rather than shrinking the desktop row.
 *
 * CONSUMER IA (#41). The primary navigation is now the economy plus
 * two product surfaces, and nothing else:
 *
 *     Home · Inflation · Jobs · Rates · Calendar
 *
 * The three worlds come from `ECONOMIC_WORLDS` rather than being
 * retyped here, so a world's label and route are defined once. What
 * LEFT is as deliberate as what stayed: "Overview" was a name for our
 * own architecture ("the intelligence workspace") rather than for a
 * part of the economy, and its content is now simply what `/` is.
 * "Labor" and "Releases" were the engineering domain's words; the
 * reader's words are Jobs and Calendar.
 */
const NAV_LINKS: ReadonlyArray<{ to: string; label: string; end?: boolean }> = [
  { to: "/", label: "Home", end: true },
  ...ECONOMIC_WORLDS.map((world) => ({ to: world.route, label: world.label })),
  { to: "/calendar", label: "Calendar" },
];

const NAV_LIST_ID = "primary-navigation-list";

function navLinkClassName({ isActive }: { isActive: boolean }): string {
  return [
    "block rounded-md px-3 py-2 text-sm transition-colors motion-reduce:transition-none",
    isActive
      ? "bg-selected font-semibold text-selected-fg"
      : "font-medium text-fg-secondary hover:bg-surface-secondary hover:text-fg",
  ].join(" ");
}

export function AppShell() {
  const [menuOpen, setMenuOpen] = useState(false);

  // Route-level measurement (Increment #37). Mounted once here rather
  // than in each page, so the pages stay unaware of analytics and a
  // future route is instrumented by existing here at all. Emits
  // nothing unless a provider is configured; never blocks rendering.
  usePageViewed();

  function onHeaderKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.key === "Escape" && menuOpen) {
      setMenuOpen(false);
      document.getElementById("primary-navigation-toggle")?.focus();
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-canvas text-fg">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-surface-elevated focus:px-4 focus:py-2 focus:text-fg focus:shadow"
      >
        Skip to main content
      </a>

      <header className="sticky top-0 z-40 border-b border-line bg-surface" onKeyDown={onHeaderKeyDown}>
        <PageContainer>
          <div className="flex flex-wrap items-center gap-x-6 py-3 md:h-16 md:flex-nowrap md:py-0">
            <Link to="/" className="group flex items-baseline gap-2 rounded-sm">
              <span className="text-lg font-semibold tracking-tight text-fg">
                Macro<span className="text-brand">Chipz</span>
              </span>
              <span className="hidden text-xs font-medium text-fg-muted sm:inline">Economic Intelligence</span>
            </Link>

            <div className="ml-auto flex items-center gap-2 md:order-last md:ml-0">
              <ThemeToggle />
              <button
                id="primary-navigation-toggle"
                type="button"
                aria-expanded={menuOpen}
                aria-controls={NAV_LIST_ID}
                onClick={() => setMenuOpen((open) => !open)}
                className="flex h-8 items-center gap-1.5 rounded-md border border-line px-2.5 text-sm font-medium text-fg-secondary hover:bg-surface-secondary hover:text-fg md:hidden"
              >
                <svg viewBox="0 0 20 20" aria-hidden="true" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                  {menuOpen ? <path d="M5 5l10 10M15 5L5 15" /> : <path d="M3.5 6h13M3.5 10h13M3.5 14h13" />}
                </svg>
                Menu
              </button>
            </div>

            <nav aria-label="Primary" className="w-full md:ml-auto md:w-auto">
              <ul
                id={NAV_LIST_ID}
                className={`${menuOpen ? "flex" : "hidden"} flex-col gap-1 border-t border-line-subtle pb-2 pt-3 md:flex md:flex-row md:items-center md:border-0 md:p-0`}
              >
                {NAV_LINKS.map((link) => (
                  <li key={link.to}>
                    <NavLink to={link.to} end={link.end} className={navLinkClassName} onClick={() => setMenuOpen(false)}>
                      {link.label}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </nav>
          </div>
        </PageContainer>
      </header>

      <main id="main-content" className="flex-1">
        <PageContainer>
          <div className="py-8 sm:py-10">
            <Outlet />
          </div>
        </PageContainer>
      </main>

      <footer className="border-t border-line">
        <PageContainer>
          <div className="flex flex-col gap-1 py-6 type-meta text-fg-muted sm:flex-row sm:items-center sm:justify-between">
            <p>
              <span className="font-semibold text-fg-secondary">MacroChipz</span> · Economic Intelligence
            </p>
            {/* Required attributions. The Census sentence is VERBATIM
                and mandatory: its Data API terms require the
                non-endorsement notice to be displayed, and #45 found it
                rendered only inside a collapsed disclosure on
                `/housing`, which is not a display. It lives here, on
                every page, for the same reason the FRED and Treasury
                lines do. */}
            <p className="sm:max-w-xl sm:text-right">
              Source data: FRED®, Federal Reserve Bank of St. Louis; U.S. Department of the Treasury; U.S. Census
              Bureau and U.S. Department of Housing and Urban Development. This product uses the Census Bureau Data
              API but is not endorsed or certified by the Census Bureau.
            </p>
          </div>
        </PageContainer>
      </footer>
    </div>
  );
}
