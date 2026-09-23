/**
 * Which pages own a page-level surface (Increment #48).
 *
 * ================================================================
 * WHY THE SHELL DECIDES AND NOT THE PAGE
 * ================================================================
 *
 * The surface is a full-bleed background on `<main>`. Only the shell
 * renders `<main>`, so only the shell can set it — and the #46F defect
 * is the argument against every alternative: that page tried to own a
 * full-bleed background from inside the content column using a
 * negative margin, the margin had nothing to cancel, and it dragged
 * the background up through the header's bottom border.
 *
 * A context or a layout effect would work too, and both would paint
 * the wrong background first and correct it after hydration. This is a
 * pure function of the pathname, so the prerendered HTML is already
 * right.
 *
 * It is a MAP AND NOT A CONDITION so that adding a surface later is a
 * one-line data change, and so a test can assert exactly which routes
 * have one.
 */
export type PageSurface = "cinematic";

const SURFACE_BY_PATH: Readonly<Record<string, PageSurface>> = {
  /** The Living Economy homepage. Charcoal, midnight and violet. */
  "/": "cinematic",
};

export function surfaceForPath(pathname: string): PageSurface | undefined {
  return SURFACE_BY_PATH[pathname];
}
