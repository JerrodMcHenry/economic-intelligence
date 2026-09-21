import type { ReactNode } from "react";
import { Link } from "react-router";

import { PageContainer } from "../PageContainer";

/**
 * A deliberately thin shell for a permanent intelligence page
 * (Increment #41).
 *
 * #40 shipped these pages with no shell at all, which was right at the
 * time -- there was no product IA to join. The cost showed up as soon
 * as someone arrived cold from a shared link: nothing on the page said
 * whose page it was, or that anything else existed.
 *
 * Now that #41 has a navigation, this supplies the three things a cold
 * visitor needs and nothing more:
 *
 *   1. WHERE THEY ARE  -- the MacroChipz brand, linking home.
 *   2. WHAT THIS IS    -- the world this object belongs to, named.
 *   3. WHERE TO GO     -- one link into that world.
 *
 * NOT the full `AppShell`. A permanent object page is usually the
 * FIRST page someone sees, arriving from a message with no context,
 * and the fact should be the loudest thing on it. Five navigation
 * items and a theme control above a single Treasury yield would
 * reverse that -- so this is a single row, and the deeper route into
 * the product stays where #40B put it: after the reader has actually
 * read the thing.
 *
 * Adds no client-only behaviour, so the page stays prerenderable and
 * its metadata is untouched.
 */
export function IntelligenceShell({
  worldLabel,
  worldRoute,
  children,
}: {
  worldLabel?: string;
  worldRoute?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col bg-canvas text-fg">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-surface-elevated focus:px-4 focus:py-2 focus:text-fg focus:shadow"
      >
        Skip to main content
      </a>

      <header className="border-b border-line bg-surface">
        <PageContainer>
          <div className="flex h-14 items-center gap-3">
            <Link to="/" className="flex items-baseline gap-2 rounded-sm">
              <span className="text-base font-semibold tracking-tight text-fg">
                Macro<span className="text-brand">Chipz</span>
              </span>
            </Link>

            {worldLabel && worldRoute && (
              <>
                <span aria-hidden="true" className="text-fg-muted">
                  /
                </span>
                <Link
                  to={worldRoute}
                  className="rounded-sm text-sm font-medium text-fg-secondary underline-offset-4 hover:text-fg hover:underline"
                >
                  {worldLabel}
                </Link>
              </>
            )}
          </div>
        </PageContainer>
      </header>

      <main id="main-content" className="flex-1">
        <PageContainer>{children}</PageContainer>
      </main>

      <footer className="border-t border-line">
        <PageContainer>
          <div className="flex flex-col gap-1 py-6 type-meta text-fg-muted sm:flex-row sm:items-center sm:justify-between">
            <p>
              <span className="font-semibold text-fg-secondary">MacroChipz</span> · Economic Intelligence
            </p>
            <p>Source data: U.S. Department of the Treasury; FRED®, Federal Reserve Bank of St. Louis.</p>
          </div>
        </PageContainer>
      </footer>
    </div>
  );
}
