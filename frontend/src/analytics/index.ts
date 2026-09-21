/**
 * The public analytics surface (Increment #37).
 *
 * Application code imports from here and nowhere else in this
 * directory. `provider.ts` and the test-only seam in `track.ts` are
 * deliberately NOT re-exported: a component has no reason to know
 * which service receives an event, or to replace it.
 *
 * See docs/architecture/product-measurement.md for the event
 * vocabulary, the product question behind each event, the data we
 * collect, and the data we refuse to.
 */
export { track } from "./track";
export { usePageViewed } from "./usePageViewed";
export type {
  AnalyticsEventName,
  AnalyticsEventProperties,
  Monitor,
  ObjectType,
  ReferrerClass,
  RouteTemplate,
  World,
} from "./events";
