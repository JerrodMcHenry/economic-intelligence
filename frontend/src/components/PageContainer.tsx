import type { ReactNode } from "react";

/**
 * The application's ONE content-width authority (Increment #27B,
 * docs/product/product-ui-ux-v1.md §12): `max-w-app` (76rem, defined
 * once in src/styles/globals.css) plus responsive side gutters. The
 * shell wraps header, main, and footer in it; pages must not add a
 * second, narrower page-level max-width on top (the #27A "double width
 * constraint"). A genuinely prose-shaped element may still cap its own
 * line length with `max-w-prose` -- that is a reading-measure choice
 * for one paragraph, not a page width.
 */
export function PageContainer({ children }: { children: ReactNode }) {
  return <div className="mx-auto w-full max-w-app px-4 sm:px-6 lg:px-8">{children}</div>;
}
