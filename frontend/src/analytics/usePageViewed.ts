/**
 * Route-level instrumentation (Increment #37).
 *
 * One hook, mounted once in the application shell, emitting
 * `page_viewed` on every route change -- and `world_opened` when that
 * route is an economic world. Doing both here rather than inside the
 * three world pages keeps the instrumentation in a single place and
 * leaves the pages themselves untouched.
 *
 * Two privacy rules are enforced in this file rather than trusted to
 * callers:
 *
 * - The pathname is NORMALIZED to a known route template before it is
 *   sent. An unrecognised path -- a typo, a crawler, a future route
 *   that has not been added here -- becomes `unknown_route`. A raw
 *   pathname is never emitted, so this can never become a way to
 *   forward whatever is in the address bar.
 * - `document.referrer` is reduced to one of three coarse classes and
 *   the referring URL itself is discarded immediately. Finer
 *   attribution is an analytics provider's own job and does not need
 *   to pass through application code.
 */
import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";

import { ROUTE_TEMPLATES, WORLD_BY_ROUTE, type ReferrerClass, type RouteTemplate } from "./events";
import { track } from "./track";

/**
 * Maps a concrete pathname onto a known route template.
 *
 * A trailing slash is tolerated (`/rates/` and `/rates` are the same
 * page to a reader). Everything unknown collapses to `unknown_route`
 * rather than being passed through.
 */
export function normalizeRoute(pathname: string): RouteTemplate {
  const trimmed = pathname.length > 1 && pathname.endsWith("/") ? pathname.slice(0, -1) : pathname;
  if ((ROUTE_TEMPLATES as ReadonlyArray<string>).includes(trimmed)) return trimmed as RouteTemplate;
  // A permanent intelligence object (#40) collapses to its TEMPLATE.
  // The id is deliberately discarded: reporting it would say which
  // specific object a reader opened.
  if (/^\/intelligence\/[^/]+$/.test(trimmed)) return "/intelligence/:id";
  return "unknown_route";
}

/**
 * Reduces a referrer to one of three classes, keeping no part of the
 * URL. Anything unparseable is treated as `none` -- the least
 * informative answer is the safe default.
 */
export function classifyReferrer(referrer: string, currentOrigin: string): ReferrerClass {
  if (!referrer) return "none";
  try {
    return new URL(referrer).origin === currentOrigin ? "internal" : "external";
  } catch {
    return "none";
  }
}

function readReferrerClass(): ReferrerClass {
  if (typeof document === "undefined" || typeof window === "undefined") return "none";
  return classifyReferrer(document.referrer, window.location.origin);
}

/**
 * Emits `page_viewed` (always) and `world_opened` (for world routes)
 * once per route change.
 *
 * The `lastRoute` ref makes this idempotent across re-renders and
 * across React 19 StrictMode's deliberate double-invocation in
 * development -- without it, every development page view would be
 * counted twice and the numbers would be quietly wrong.
 */
export function usePageViewed(): void {
  const { pathname } = useLocation();
  const lastRoute = useRef<string | null>(null);

  useEffect(() => {
    if (lastRoute.current === pathname) return;
    lastRoute.current = pathname;

    const route = normalizeRoute(pathname);
    track("page_viewed", { route_template: route, referrer_class: readReferrerClass() });

    const world = WORLD_BY_ROUTE[route];
    if (world) track("world_opened", { world });
  }, [pathname]);
}
