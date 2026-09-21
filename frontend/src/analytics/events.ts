/**
 * The MacroChipz measurement vocabulary (Increment #37).
 *
 * Every event in this file exists because it answers a specific
 * product question, and the question is written next to it. An event
 * without a question does not belong here -- see
 * docs/architecture/product-measurement.md for the full rationale and
 * the privacy rules this module enforces.
 *
 * Two properties of this design matter more than the list itself:
 *
 * 1. The vocabulary is a CLOSED union. `AnalyticsEventName` is the
 *    only set of names that exist, and each name is tied to its own
 *    property shape, so an unknown event or a mismatched property is a
 *    type error rather than a runtime surprise.
 *
 * 2. Property values are constrained to a small set of literal unions
 *    wherever the value is ours to choose. A free-form `string` is
 *    used only where the value is a stable identifier we already own
 *    (an explanation id), never for anything a user typed, a URL, or a
 *    query string.
 *
 * `EVENT_PROPERTY_ALLOWLIST` is the runtime half of the same rule. The
 * type system stops a developer writing the wrong property; the
 * allowlist stops anything else reaching a provider if a value is ever
 * assembled dynamically or a type is widened by accident. Defence in
 * depth, deliberately duplicated.
 */

/** The six MacroChipz economic worlds. Only three exist today. */
export type World = "inflation" | "labor" | "rates";

/**
 * The kind of thing an interaction was about. Deliberately coarse:
 * enough to tell an evidence panel from a revision, not enough to
 * identify which reader opened which one.
 */
export type ObjectType =
  | "inflation_metric"
  | "labor_observation"
  | "monitor_state"
  | "revision"
  | "release"
  // Added in #40: the Structured Intelligence types (#39) a
  // permanent object page can share. Still a closed set -- an
  // arbitrary string can never reach a provider.
  | "RELEASE_PROCESSED"
  | "OBSERVATION_CHANGE"
  | "ANALYSIS_CHANGE"
  | "RATES_MOVEMENT";

/** Which monitor's recorded-intelligence history was opened. */
export type Monitor = "inflation" | "labor";

/**
 * Where the reader arrived from, at the coarsest useful resolution.
 * Deliberately NOT the referring URL, and deliberately not split into
 * search/social -- finer attribution is the analytics provider's own
 * job and does not need to pass through application code.
 */
export type ReferrerClass = "none" | "internal" | "external";

/**
 * Normalized route identities. A route TEMPLATE, never a concrete URL
 * and never a query string: `page_viewed` must not become a way to
 * exfiltrate whatever happens to be in the address bar.
 *
 * `unknown_route` is the deliberate catch-all. Anything not on this
 * list -- including a 404 path a crawler or a typo produced -- is
 * reported as `unknown_route` rather than sent verbatim.
 */
export type RouteTemplate =
  | "/"
  | "/overview"
  | "/inflation"
  | "/labor"
  | "/rates"
  | "/releases"
  // A permanent intelligence object page (#40). The TEMPLATE, never a
  // concrete id -- an id is a semantic identifier, and sending it would
  // report which specific object a reader opened.
  | "/intelligence/:id"
  | "unknown_route";

export interface AnalyticsEventMap {
  /**
   * Q: Which surfaces are used at all?
   * Emitted on every route change, including the first render.
   */
  page_viewed: { route_template: RouteTemplate; referrer_class: ReferrerClass };

  /**
   * Q: Does anyone explore past the homepage, and into which world?
   *
   * Overlaps `page_viewed` today, because worlds are routes today.
   * Kept as its own event because it is the one that survives the
   * planned `/labor` -> `/jobs` rename and the 2.0 designs where a
   * world opens without a route change. The `world` property is
   * self-describing; a route template requires knowing which routes
   * are worlds.
   */
  world_opened: { world: World };

  /**
   * Q: Does anyone actually verify?
   *
   * THE HEADLINE METRIC. The Product Constitution's central bet is
   * that provenance, not clarity, is the differentiator. If this
   * number is near zero after launch, that bet is wrong and the
   * product strategy needs revisiting -- not the instrumentation.
   */
  evidence_expanded: { object_type: ObjectType };

  /** Q: Is the signature capability -- recorded intelligence and how it changed -- actually used? */
  revision_opened: { monitor: Monitor };

  /**
   * Q: Does in-place education land, and which concepts do readers
   * stop to look up?
   *
   * `explainer_id` is a curated identifier from
   * `src/content/explanations/`, authored by us. It is never user
   * input.
   */
  explainer_opened: { explainer_id: string };

  /** Q: Do rabbit holes work -- does anyone follow a link between related economic ideas? */
  related_followed: { from_type: World; to_type: World };

  /**
   * Q: Is the Analyst wanted where we placed it?
   *
   * Records ONLY the page context the question was asked from. The
   * question text, the answer text, and any evidence are never sent --
   * see `docs/architecture/product-measurement.md` "Prohibited data".
   */
  analyst_asked: { context_type: string };

  /**
   * ACTIVE since Increment #40.
   * Q: Do objects survive leaving MacroChipz?
   *
   * Emitted when a reader INTENTIONALLY initiates sharing -- never on
   * page view, never on hover. Records the object type only: not the
   * URL, not the share text, not the clipboard, not which app was
   * chosen.
   */
  share_initiated: { object_type: ObjectType };

  /**
   * RESERVED -- not emitted today. Follow/email does not exist yet
   * (Increment #46).
   * Q: Is there a legitimate reason to return?
   */
  follow_signup: { target: World | "all" };

  /**
   * RESERVED -- not emitted today, deliberately.
   * Q: Does honest absence retain or repel?
   *
   * Today's empty states are data-availability artifacts ("no rates
   * data yet"). The question this event exists to answer is about the
   * DESIGNED honest-absence state -- "nothing meaningful changed
   * today" -- which arrives with What Changed in Increment #42.
   * Emitting it now would answer a different question and quietly
   * poison the baseline.
   */
  empty_state_viewed: { surface: string };
}

export type AnalyticsEventName = keyof AnalyticsEventMap;

export type AnalyticsEventProperties<N extends AnalyticsEventName> = AnalyticsEventMap[N];

/**
 * The runtime property allowlist -- the second half of the two-layer
 * rule described in this module's header.
 *
 * `track()` drops any key not listed here for the event being sent.
 * Keeping this beside the types (rather than deriving it from them,
 * which TypeScript cannot do at runtime) means a new property must be
 * added in two places on purpose, which is the point.
 *
 * `src/analytics/events.test.ts` fails if a key in `AnalyticsEventMap`
 * has no entry here.
 */
export const EVENT_PROPERTY_ALLOWLIST: {
  readonly [N in AnalyticsEventName]: ReadonlyArray<keyof AnalyticsEventMap[N] & string>;
} = {
  page_viewed: ["route_template", "referrer_class"],
  world_opened: ["world"],
  evidence_expanded: ["object_type"],
  revision_opened: ["monitor"],
  explainer_opened: ["explainer_id"],
  related_followed: ["from_type", "to_type"],
  analyst_asked: ["context_type"],
  share_initiated: ["object_type"],
  follow_signup: ["target"],
  empty_state_viewed: ["surface"],
};

export const ANALYTICS_EVENT_NAMES = Object.keys(EVENT_PROPERTY_ALLOWLIST) as ReadonlyArray<AnalyticsEventName>;

/**
 * The known route templates, used to normalize a concrete pathname
 * into one of them. Anything else becomes `unknown_route`.
 */
export const ROUTE_TEMPLATES: ReadonlyArray<Exclude<RouteTemplate, "unknown_route">> = [
  "/",
  "/overview",
  "/inflation",
  "/labor",
  "/rates",
  "/releases",
  "/intelligence/:id",
];

/** Which route templates are economic worlds, and which world each is. */
export const WORLD_BY_ROUTE: Readonly<Partial<Record<RouteTemplate, World>>> = {
  "/inflation": "inflation",
  "/labor": "labor",
  "/rates": "rates",
};
