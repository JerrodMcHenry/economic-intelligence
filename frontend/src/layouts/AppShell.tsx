import { NavLink, Outlet } from "react-router-dom";

import { PageContainer } from "../components/PageContainer";

/**
 * The application's minimal, reusable shell: a skip link, a header
 * with the product name and primary navigation, and a main landmark
 * that renders the active route. Navigation is intentionally limited
 * to real product destinations -- see docs/architecture/current-architecture.md
 * for what each route actually implements.
 */
const NAV_LINKS: ReadonlyArray<{ to: string; label: string; end?: boolean }> = [
  { to: "/", label: "Overview", end: true },
  { to: "/inflation", label: "Inflation" },
  { to: "/releases", label: "Releases" },
];

function navLinkClassName({ isActive }: { isActive: boolean }): string {
  return [
    "rounded-md px-3 py-2 text-sm font-medium transition-colors",
    isActive ? "bg-neutral-900 text-white" : "text-neutral-600 hover:bg-neutral-100 hover:text-neutral-900",
  ].join(" ");
}

export function AppShell() {
  return (
    <div className="min-h-screen bg-neutral-50 text-neutral-900">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-white focus:px-4 focus:py-2 focus:shadow"
      >
        Skip to main content
      </a>

      <header className="border-b border-neutral-200 bg-white">
        <PageContainer>
          <div className="flex h-16 items-center justify-between">
            <span className="text-base font-semibold tracking-tight text-neutral-900">Economic Intelligence</span>
            <nav aria-label="Primary">
              <ul className="flex items-center gap-1">
                {NAV_LINKS.map((link) => (
                  <li key={link.to}>
                    <NavLink to={link.to} end={link.end} className={navLinkClassName}>
                      {link.label}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </nav>
          </div>
        </PageContainer>
      </header>

      <main id="main-content">
        <PageContainer>
          <div className="py-8">
            <Outlet />
          </div>
        </PageContainer>
      </main>
    </div>
  );
}
