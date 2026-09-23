/**
 * THE RATE NETWORK (Increment #46E).
 *
 * ================================================================
 * WHAT THIS IS
 * ================================================================
 *
 * A curated educational diagram of who sets what between a Federal
 * Reserve decision and the rate a lender quotes you. Six actors, six
 * relationships, and one distinction that is the whole point:
 *
 *   SETS        — someone decides this number.
 *   INFLUENCES  — it feeds in, and nobody decides it from here.
 *
 * There are exactly two `sets` edges and they sit at opposite ends of
 * the graph with nothing but influence between them. **That shape is
 * the explanation.** It is also why the legend is not decoration.
 *
 * ================================================================
 * WHAT THIS IS NOT
 * ================================================================
 *
 * Not a causal model. Not a formula. Not exhaustive. An edge means
 * "reaches", never "by this much" and never "in this direction". The
 * reviewed caveat — that these interact rather than forming a single
 * chain, and that their relative importance changes over time — ships
 * with the diagram and is not optional chrome.
 *
 * ================================================================
 * THE TRACEABILITY RULE
 * ================================================================
 *
 * **Every sentence below is a contiguous substring of something that was
 * already written and reviewed** — either the #44 explainer registry
 * entry or the #46C story copy. Trimming a clause is allowed, because
 * deleting words cannot add a claim. Rewording is not allowed, because
 * it can. `rateNetwork.test.ts` checks this mechanically against
 * REVIEWED_SOURCES, so a new claim cannot enter by being typed here.
 *
 * This file replaces the prose that lived in #46C's `RateAuthorityQuiz`
 * and `InfluenceExplorer`, which the network supersedes. Nothing those
 * components said is lost; it is all below.
 */
import { explainerById } from "./registry";

export type NodeId =
  | "fed-policy"
  | "fed-funds"
  | "treasury"
  | "mbs"
  | "lenders"
  | "mortgage-rate";

/** `sets` = someone decides this number. `influences` = it feeds in. */
export type EdgeKind = "sets" | "influences";

export interface NetworkNode {
  readonly id: NodeId;
  /** The accurate name, used as the button's accessible name. */
  readonly label: string;
  /** A shorter form for the diagram chip where the full name will not fit. */
  readonly chip: string;
  /** Plain-English role. Traceable to reviewed copy — see the rule above. */
  readonly role: string;
  /** Who decides it, when anyone does. `null` where nobody sets it directly. */
  readonly setBy: string | null;
  /** Position in the diagram's 0-100 coordinate space (percent of the board). */
  readonly x: number;
  readonly y: number;
  /** Which side of the dot the label chip sits on. */
  readonly side: "left" | "right";
  /** The rate a lender quotes you: the thing the whole story is about. */
  readonly outcome?: boolean;
}

export interface NetworkEdge {
  readonly from: NodeId;
  readonly to: NodeId;
  readonly kind: EdgeKind;
}

/**
 * The reviewed strings every `role` must be found inside.
 *
 * The first entries are pulled live from the #44 registry, so if that
 * copy is ever edited this file's guard fails rather than silently
 * drifting. The remainder are the #46C strings, which lived in
 * components this increment removes and are therefore reproduced here as
 * their new canonical home.
 */
const explainer = explainerById("explain.fed-and-mortgage-rates");

export const REVIEWED_SOURCES: ReadonlyArray<string> = [
  explainer?.answer ?? "",
  explainer?.whatItIs ?? "",
  explainer?.misconception ?? "",
  explainer?.whatThisMeansForYou ?? "",
  ...(explainer?.howItWorks ?? []),
  ...(explainer?.limitations ?? []),
  // --- #46C, reviewed: the four influences -------------------------
  "Sets a short-term rate between banks, and shapes what investors expect next.",
  "What it costs the U.S. government to borrow for years at a time.",
  "Investors buy pools of home loans, and what they will pay feeds back into pricing.",
  "Credit conditions, the chance a loan is repaid early, and what each lender needs to earn.",
  "All of the above, plus competition between lenders — which is why two lenders can quote different rates on the same day.",
  "These interact rather than forming a single chain, and their relative importance changes over time. This shows what feeds in, not a formula.",
  // --- #46C, reviewed: who sets which rate --------------------------
  "Lenders set this, competing with each other. This is the number the whole misconception is about — and two lenders can quote you different rates on the same day.",
  "This is the one. The Fed's committee sets a target range for it — the rate banks charge each other for lending overnight. You never pay it, and you will probably never see it quoted anywhere.",
  "Investors set this by buying and selling government debt. The Fed's decisions shape what investors expect, but the Fed does not choose the number.",
  "Your bank chooses this. It moves with conditions the Fed influences, but no one at the Fed decides what your account earns.",
];

/**
 * Positions are percentages of the board, not pixels.
 *
 * #46D shipped 41px tap targets because 48 SVG user units looked like 48
 * pixels — a scaled `viewBox` makes a user unit a ratio rather than a
 * measurement. Percentages are honest about that: the SVG draws at these
 * coordinates and the HTML buttons are positioned at the same
 * percentages, so the two layers cannot drift and the buttons keep a
 * real pixel minimum whatever the board's width.
 *
 * ================================================================
 * WHY THE VERTICAL SPACING IS EVEN (#46E responsive pass)
 * ================================================================
 *
 * The first layout placed nodes at 11/25/39/58/70/91. Two of those —
 * 58 and 70 — are twelve percentage points apart, and a 44px tap target
 * needs 44px of separation. On a 330px board twelve points is 40px, so
 * `Mortgage-backed securities` and `Mortgage lenders` OVERLAPPED BY 5px.
 * Not intermittently: always, by arithmetic, and worse as the board
 * narrowed. At 320px three pairs collided.
 *
 * Document `scrollWidth` reported zero overflow throughout, which is why
 * it went unnoticed — a control can sit on top of another without the
 * document being any wider.
 *
 * So the six nodes are now EVENLY spaced at 16.8 points. The minimum
 * separation is therefore 0.168 x boardWidth, which clears 44px for any
 * board at least 262px wide — every viewport down to about 294px CSS,
 * i.e. a 390px phone at 133% browser zoom. That is a property of the
 * numbers rather than of the current type size, and
 * `rateNetwork.test.ts` asserts it.
 *
 * ================================================================
 * WHY THE ORDER IS WHAT IT IS
 * ================================================================
 *
 * Registry order, DOM order, top-to-bottom visual order and the narrow
 * single-column order are all THE SAME SEQUENCE. That is deliberate:
 * tab order then matches what a sighted user sees in the scatter
 * layout, and the narrow column reads as a sequence rather than as six
 * items in an arbitrary order.
 *
 * `fed-policy` and `fed-funds` share an x on purpose, so the one edge
 * that matters most is perfectly vertical — which is the geometry that
 * exposed the zero-width-bounding-box bug in SVG gradients and filters.
 * `rateNetwork.test.ts` asserts a vertical `sets` edge still exists, so
 * that regression keeps a live example to fail against.
 */
export const NETWORK_NODES: ReadonlyArray<NetworkNode> = [
  {
    id: "fed-policy",
    label: "Federal Reserve policy",
    chip: "Federal Reserve",
    role: "Sets a short-term rate between banks, and shapes what investors expect next.",
    setBy: null,
    x: 15,
    y: 8,
    side: "right",
  },
  {
    id: "fed-funds",
    label: "Federal funds rate",
    chip: "Federal funds rate",
    role: "The Fed's committee sets a target range for it — the rate banks charge each other for lending overnight. You never pay it, and you will probably never see it quoted anywhere.",
    setBy: "The Federal Open Market Committee, as a target range",
    x: 15,
    y: 24.8,
    side: "right",
  },
  {
    id: "treasury",
    label: "Treasury yields",
    chip: "Treasury yields",
    role: "Investors set this by buying and selling government debt. The Fed's decisions shape what investors expect, but the Fed does not choose the number.",
    setBy: null,
    x: 85,
    y: 41.6,
    side: "left",
  },
  {
    id: "mbs",
    label: "Mortgage-backed securities",
    chip: "Mortgage-backed securities",
    role: "Investors buy pools of home loans, and what they will pay feeds back into pricing.",
    setBy: null,
    x: 85,
    y: 58.4,
    side: "left",
  },
  {
    id: "lenders",
    label: "Mortgage lenders",
    chip: "Mortgage lenders",
    role: "Credit conditions, the chance a loan is repaid early, and what each lender needs to earn.",
    setBy: null,
    x: 22,
    y: 75.2,
    side: "right",
  },
  {
    id: "mortgage-rate",
    label: "Mortgage rates",
    chip: "Your mortgage rate",
    role: "Lenders set this, competing with each other. This is the number the whole misconception is about — and two lenders can quote you different rates on the same day.",
    setBy: "Mortgage lenders, competing with each other",
    x: 78,
    y: 92,
    side: "left",
    outcome: true,
  },
];

/**
 * EDGES CARRY NO PROSE, deliberately.
 *
 * A `kind` and two endpoints, and nothing else. Every explanation lives
 * on a node, which makes it structurally impossible for an edge to
 * acquire a claim that was never reviewed.
 *
 * `fed-funds → treasury` is DELIBERATELY ABSENT. The mockup drew it, but
 * the reviewed copy routes the Fed's effect on long-term rates through
 * expectations — "that decision ripples through what investors expect
 * for the future" — rather than through the funds rate itself. Drawing
 * the shortcut would assert a mechanism the sources do not.
 */
export const NETWORK_EDGES: ReadonlyArray<NetworkEdge> = [
  { from: "fed-policy", to: "fed-funds", kind: "sets" },
  { from: "fed-policy", to: "treasury", kind: "influences" },
  { from: "treasury", to: "mbs", kind: "influences" },
  { from: "treasury", to: "lenders", kind: "influences" },
  { from: "mbs", to: "lenders", kind: "influences" },
  { from: "lenders", to: "mortgage-rate", kind: "sets" },
];

/**
 * The diagram opens on the federal funds rate.
 *
 * Not on nothing. A diagram that starts with nothing selected starts by
 * explaining nothing, and the prerendered HTML would ship an empty
 * panel. The funds rate is the node the misconception is actually about.
 */
export const DEFAULT_SELECTED_ID: NodeId = "fed-funds";

/** The caveat that ships with the diagram, never as optional chrome. */
export const NETWORK_CAVEAT =
  "These interact rather than forming a single chain, and their relative importance changes over time. This shows what feeds in, not a formula.";

/**
 * Deliberately NOT "six things decide what you are quoted", which the
 * #46E brief called out: that phrasing implies both an exhaustive list
 * and a deciding mechanism, and the diagram is neither.
 */
export const NETWORK_STANDFIRST =
  "Some of what reaches the rate you're quoted — and which parts anyone actually sets.";

export function networkNode(id: NodeId): NetworkNode {
  const found = NETWORK_NODES.find((n) => n.id === id);
  if (!found) throw new Error(`unknown network node: ${id}`);
  return found;
}

/** Every edge touching `id`, in registry order. */
export function edgesTouching(id: NodeId): ReadonlyArray<NetworkEdge> {
  return NETWORK_EDGES.filter((e) => e.from === id || e.to === id);
}

/** What this node sets, what sets it, and what it merely feeds into. */
export function connectionsFor(id: NodeId): {
  readonly sets: ReadonlyArray<NetworkNode>;
  readonly setBy: ReadonlyArray<NetworkNode>;
  readonly influences: ReadonlyArray<NetworkNode>;
  readonly influencedBy: ReadonlyArray<NetworkNode>;
} {
  const touching = edgesTouching(id);
  return {
    sets: touching.filter((e) => e.kind === "sets" && e.from === id).map((e) => networkNode(e.to)),
    setBy: touching.filter((e) => e.kind === "sets" && e.to === id).map((e) => networkNode(e.from)),
    influences: touching
      .filter((e) => e.kind === "influences" && e.from === id)
      .map((e) => networkNode(e.to)),
    influencedBy: touching
      .filter((e) => e.kind === "influences" && e.to === id)
      .map((e) => networkNode(e.from)),
  };
}
