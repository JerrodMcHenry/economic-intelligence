/**
 * The public origin MacroChipz is served from (Increment #40).
 *
 * Needed for canonical links and Open Graph URLs, which must be
 * ABSOLUTE to be useful to a crawler or an unfurl.
 *
 * `VITE_SITE_URL` is build-time configuration, not a secret, and it is
 * deliberately allowed to be unset: when it is, canonical and `og:url`
 * tags are OMITTED rather than emitted pointing at a guessed origin. A
 * wrong canonical is worse than none -- it tells a crawler the real
 * page lives somewhere it does not.
 */
export const SITE_URL: string | null = (import.meta.env.VITE_SITE_URL ?? "").trim().replace(/\/$/, "") || null;

export function absoluteUrl(path: string): string | null {
  return SITE_URL === null ? null : `${SITE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

export function intelligencePath(intelligenceId: string): string {
  return `/intelligence/${encodeURIComponent(intelligenceId)}`;
}
