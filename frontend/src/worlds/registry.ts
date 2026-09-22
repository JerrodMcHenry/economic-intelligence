/**
 * The Economic World registry (Increment #41).
 *
 * MacroChipz 2.0's organising idea is that **the economy is the
 * product**: a reader explores parts of the economy, not parts of our
 * architecture. A "world" is one such part. This file is where a world's
 * identity is defined -- once -- so that navigation, routing, page
 * headers, analytics and the permanent-object back-link all agree.
 *
 * WHAT A WORLD IS NOT
 * -------------------
 * - Not a database table. Worlds are code, because they change when the
 *   product changes, not when data changes.
 * - Not a CMS. There is no generic content model here, no slots, no
 *   component configuration. A world carries identity and language;
 *   each world page owns its own economics.
 * - Not a provider or a series. `id` is a MacroChipz concept of a part
 *   of the economy; provider series ids never appear here (#38).
 * - Not a methodology. No thresholds, no states, no calculation. A
 *   world names a subject; `inflation_v1.0`, `labor_v1.0` and
 *   `rates_v1.0` decide what is true about it.
 * - Not a fetcher. Nothing in this module touches the network.
 *
 * ENGINEERING NAMES AND CONSUMER NAMES ARE ALLOWED TO DIFFER
 * ----------------------------------------------------------
 * The Jobs world is served by the `labor` engineering domain:
 * `labor_v1.0`, `app/domain/labor.py`, `/api/v1/monitors/labor`,
 * `LaborState`. #41 renames the PRODUCT, not the domain -- so `JOBS`
 * carries `engineeringDomain: "labor"` and the rename stops at the
 * edge of the UI. Renaming a frozen methodology to improve a heading
 * would be the tail wagging the dog.
 *
 * ADDING A WORLD LATER
 * --------------------
 * Housing arrived in #45, and it cost exactly one entry below -- no
 * shell redesign, no navigation rework, no per-surface edit. That was
 * the extensibility this registry existed to provide, and it held:
 * navigation, route metadata, world links, analytics vocabulary and the
 * homepage's world ordering all derive from this array, so Housing
 * appeared in every one of them without any of them being touched.
 *
 * It was deliberately absent until then rather than present-and-empty:
 * an inactive world with no data is a promise the product cannot keep,
 * and #27A §11 already froze the rule that a navigation slot follows
 * content rather than preceding it.
 *
 * A WORLD IN THIS ARRAY IS A SUBJECT, NOT A VERDICT. Housing is the
 * first entry with no methodology behind it: `inflation_v1.0`,
 * `labor_v1.0` and `rates_v1.0` decide what is true about the other
 * three, and nothing decides anything about Housing. `/housing` shows
 * figures Census published and the arithmetic between them, and no
 * state. That is why `EconomicWorld` has no "has a state" field --
 * a world does not promise one.
 */

/** Stable identity for a part of the economy MacroChipz covers. */
export type WorldId = "INFLATION" | "JOBS" | "RATES" | "HOUSING";

export interface EconomicWorld {
  /** Stable, internal. Never a provider id, never a route. */
  readonly id: WorldId;
  /** What a reader calls it. Appears in navigation and page headers. */
  readonly label: string;
  /** The canonical public route. */
  readonly route: string;
  /**
   * One plain sentence: what part of the economy this is. Written for
   * someone with no economics background.
   */
  readonly description: string;
  /**
   * The value #37 reports for `world_opened` / `world` properties.
   * Held here so the measurement vocabulary and the product vocabulary
   * cannot drift apart.
   */
  readonly analyticsWorld: "inflation" | "jobs" | "rates" | "housing";
  /**
   * The engineering domain that serves this world, where it differs
   * from the consumer name. `undefined` means they are the same word.
   * Documentation, not dispatch -- nothing routes on this.
   */
  readonly engineeringDomain?: string;
}

/**
 * The worlds that exist today, in navigation order.
 *
 * Ordered deliberately: Inflation and Jobs are the two questions a
 * general reader already has, Rates is the one they arrive at through
 * them, and Housing is where several of those questions end up --
 * placed last because it is the newest and the only one without a
 * state, not because it matters least. This array is a navigation
 * order, never a ranking of importance.
 */
export const ECONOMIC_WORLDS: ReadonlyArray<EconomicWorld> = [
  {
    id: "INFLATION",
    label: "Inflation",
    route: "/inflation",
    description: "Whether prices across the economy are rising faster or more slowly.",
    analyticsWorld: "inflation",
  },
  {
    id: "JOBS",
    label: "Jobs",
    route: "/jobs",
    description: "Whether employers are adding jobs, and how many people are out of work.",
    analyticsWorld: "jobs",
    engineeringDomain: "labor",
  },
  {
    id: "RATES",
    label: "Rates",
    route: "/rates",
    description: "What it costs the U.S. government to borrow, and what that says about longer-term borrowing.",
    analyticsWorld: "rates",
  },
  {
    id: "HOUSING",
    label: "Housing",
    route: "/housing",
    description: "How many homes are being authorised, started and finished across the country.",
    analyticsWorld: "housing",
  },
];

const BY_ID = new Map(ECONOMIC_WORLDS.map((world) => [world.id, world]));
const BY_ROUTE = new Map(ECONOMIC_WORLDS.map((world) => [world.route, world]));

export function world(id: WorldId): EconomicWorld {
  const found = BY_ID.get(id);
  // Unreachable through the type system; thrown rather than defaulted
  // so a future mistake surfaces here instead of rendering a blank
  // heading somewhere far away.
  if (!found) throw new Error(`Unknown economic world: ${id}`);
  return found;
}

/** The world a route belongs to, or `undefined` for a non-world surface. */
export function worldForRoute(route: string): EconomicWorld | undefined {
  return BY_ROUTE.get(route);
}

/**
 * Surfaces that are part of the product but are NOT economic worlds.
 *
 * Calendar is the clear case: it is a schedule of releases across every
 * world, so treating it as a world would make "which world is this?"
 * unanswerable. It appears in primary navigation beside the worlds
 * without being one, and no `world_opened` event is emitted for it.
 */
export const NON_WORLD_SURFACES: ReadonlyArray<{ label: string; route: string }> = [
  { label: "Home", route: "/" },
  { label: "Calendar", route: "/calendar" },
];
