/**
 * The rate network registry (Increment #46E).
 *
 * The important test in this file is the traceability one. A diagram is
 * a very easy place to smuggle in a claim: an edge looks like a fact,
 * and a confident sentence under a glowing node looks reviewed whether
 * or not it is. So the rule is mechanical —
 *
 *   every user-visible sentence about the economy must be a CONTIGUOUS
 *   SUBSTRING of a string that was already written and reviewed
 *
 * — which permits trimming a clause (deleting words cannot add a claim)
 * and forbids rewording (which can).
 */
import { describe, expect, it } from "vitest";

import {
  DEFAULT_SELECTED_ID,
  NETWORK_CAVEAT,
  NETWORK_EDGES,
  NETWORK_NODES,
  NETWORK_STANDFIRST,
  REVIEWED_SOURCES,
  connectionsFor,
  edgesTouching,
  networkNode,
  type NetworkEdge,
} from "./rateNetwork";

/** Quote characters differ between sources; compare on the words. */
function normalise(text: string): string {
  return text
    .replace(/[‘’]/g, "'")
    .replace(/[“”]/g, '"')
    .replace(/\s+/g, " ")
    .trim();
}

describe("every economic sentence traces to reviewed copy", () => {
  const sources = REVIEWED_SOURCES.map(normalise);

  it("has reviewed sources to check against", () => {
    // If the #44 registry entry were ever renamed, the pulled strings
    // would be empty and this suite would pass vacuously.
    expect(sources.filter((s) => s.length > 0).length).toBeGreaterThanOrEqual(14);
  });

  it.each(NETWORK_NODES.map((n) => [n.id, n.role] as const))(
    "%s: role is a contiguous substring of a reviewed string",
    (_id, role) => {
      const needle = normalise(role);
      expect(sources.some((source) => source.includes(needle))).toBe(true);
    },
  );

  it("the caveat is reviewed copy, unmodified", () => {
    expect(sources).toContain(normalise(NETWORK_CAVEAT));
  });

  it("carries no edge prose at all", () => {
    // An edge with a description is an edge that can acquire a claim.
    for (const edge of NETWORK_EDGES) {
      expect(Object.keys(edge).sort()).toEqual(["from", "kind", "to"]);
    }
  });

  it("drops the phrasing the brief called out as exhaustive", () => {
    expect(NETWORK_STANDFIRST).not.toMatch(/six things decide/i);
    // ...and does not simply reword the same implication.
    expect(NETWORK_STANDFIRST).not.toMatch(/\bdecide[sd]?\b|\bdetermine[sd]?\b|\ball of\b/i);
  });
});

describe("the shape of the graph is the explanation", () => {
  it("has six nodes and six edges", () => {
    expect(NETWORK_NODES).toHaveLength(6);
    expect(NETWORK_EDGES).toHaveLength(6);
  });

  it("has exactly two direct edges, at opposite ends", () => {
    const sets = NETWORK_EDGES.filter((e) => e.kind === "sets");
    expect(sets).toHaveLength(2);
    expect(sets.map((e: NetworkEdge) => `${e.from}->${e.to}`)).toEqual([
      "fed-policy->fed-funds",
      "lenders->mortgage-rate",
    ]);
  });

  it("does NOT draw the fed-funds to Treasury shortcut", () => {
    // The reviewed copy routes the Fed's effect on long-term rates
    // through expectations, not through the funds rate itself. Drawing
    // it would assert a mechanism the sources do not.
    expect(
      NETWORK_EDGES.some((e) => e.from === "fed-funds" && e.to === "treasury"),
    ).toBe(false);
  });

  it("names a setter only where one exists", () => {
    const withSetter = NETWORK_NODES.filter((n) => n.setBy !== null).map((n) => n.id);
    expect(withSetter.sort()).toEqual(["fed-funds", "mortgage-rate"]);
  });

  it("agrees with itself: every node with a setter is the target of a `sets` edge", () => {
    for (const node of NETWORK_NODES) {
      const isSetTarget = NETWORK_EDGES.some((e) => e.kind === "sets" && e.to === node.id);
      expect(isSetTarget, node.id).toBe(node.setBy !== null);
    }
  });

  it("references only ids that exist", () => {
    const ids = new Set(NETWORK_NODES.map((n) => n.id));
    for (const edge of NETWORK_EDGES) {
      expect(ids.has(edge.from), edge.from).toBe(true);
      expect(ids.has(edge.to), edge.to).toBe(true);
    }
  });

  it("leaves every node reachable — nothing floats unconnected", () => {
    for (const node of NETWORK_NODES) {
      expect(edgesTouching(node.id).length, node.id).toBeGreaterThan(0);
    }
  });

  it("opens on a node that explains the misconception", () => {
    expect(DEFAULT_SELECTED_ID).toBe("fed-funds");
    expect(networkNode(DEFAULT_SELECTED_ID).setBy).not.toBeNull();
  });

  it("keeps every pair of node chips 44px apart on any supported board", () => {
    // THE DEFECT THIS EXISTS FOR: at 11/25/39/58/70/91 two nodes sat 12
    // points apart, which on a 330px board is 40px — less than the 44px
    // tap target they each occupy, so two controls overlapped by 5px on
    // every render. Document scrollWidth reported zero overflow, because
    // one control sitting on another does not make the page any wider.
    //
    // Even spacing makes the guarantee arithmetic rather than lucky.
    const ys = NETWORK_NODES.map((n) => n.y).sort((a, b) => a - b);
    const gaps = ys.slice(1).map((y, i) => y - ys[i]!);
    const smallest = Math.min(...gaps);

    // 262px is the narrowest board that still clears 44px at this
    // spacing, which is roughly a 390px phone at 133% browser zoom.
    const NARROWEST_BOARD_PX = 262;
    expect((smallest / 100) * NARROWEST_BOARD_PX).toBeGreaterThanOrEqual(44);
  });

  it("keeps one direct edge perfectly vertical", () => {
    // Not cosmetic. A vertical line has a ZERO-WIDTH bounding box, and
    // both SVG gradients and SVG filters default to objectBoundingBox
    // units — so on this edge, and only on this edge, a bbox-relative
    // gradient or filter renders nothing at all. It hid the most
    // important relationship on the page twice during exploration.
    //
    // Keeping a vertical `sets` edge in the registry means the guard in
    // `story.fedMortgage.test.tsx` has a live example to fail against
    // rather than a rule nobody can trigger.
    const vertical = NETWORK_EDGES.filter((e) => e.kind === "sets").filter(
      (e) => networkNode(e.from).x === networkNode(e.to).x,
    );
    expect(vertical.length).toBeGreaterThanOrEqual(1);
  });

  it("reads in one order everywhere: registry, DOM, top-to-bottom and the narrow column", () => {
    // Tab order follows the DOM, which follows this array. If the array
    // were not also in visual order, a keyboard user would tab around
    // the diagram in a sequence nobody else can see — and the
    // single-column fallback, which reuses the same DOM order, would
    // read as six items in no particular order.
    const ys = NETWORK_NODES.map((n) => n.y);
    expect(ys).toEqual([...ys].sort((a, b) => a - b));
  });

  it("leaves room for a chip at the top and bottom of the board", () => {
    // A chip is centred on its node, so a node too close to an edge
    // pushes half a chip outside the diagram.
    for (const node of NETWORK_NODES) {
      expect(node.y, node.id).toBeGreaterThanOrEqual(7);
      expect(node.y, node.id).toBeLessThanOrEqual(93);
    }
  });

  it("positions every node inside the board", () => {
    for (const node of NETWORK_NODES) {
      expect(node.x, node.id).toBeGreaterThan(0);
      expect(node.x, node.id).toBeLessThan(100);
      expect(node.y, node.id).toBeGreaterThan(0);
      expect(node.y, node.id).toBeLessThan(100);
    }
  });
});

describe("connectionsFor", () => {
  it("separates what a node sets from what it merely feeds", () => {
    const fed = connectionsFor("fed-policy");
    expect(fed.sets.map((n) => n.id)).toEqual(["fed-funds"]);
    expect(fed.influences.map((n) => n.id)).toEqual(["treasury"]);
    expect(fed.setBy).toEqual([]);
  });

  it("knows the mortgage rate is set, not merely influenced", () => {
    const rate = connectionsFor("mortgage-rate");
    expect(rate.setBy.map((n) => n.id)).toEqual(["lenders"]);
    expect(rate.sets).toEqual([]);
  });

  it("knows Treasury yields are set by nobody in this graph", () => {
    const ust = connectionsFor("treasury");
    expect(ust.setBy).toEqual([]);
    expect(ust.influencedBy.map((n) => n.id)).toEqual(["fed-policy"]);
    expect(ust.influences.map((n) => n.id)).toEqual(["mbs", "lenders"]);
  });
});

describe("no claim the sources do not support", () => {
  const allText = [
    ...NETWORK_NODES.map((n) => `${n.label} ${n.chip} ${n.role} ${n.setBy ?? ""}`),
    NETWORK_CAVEAT,
    NETWORK_STANDFIRST,
  ].join(" ");

  it("quantifies nothing", () => {
    expect(allText).not.toMatch(/\d+(\.\d+)?\s*(%|percent|basis points?|bps)/i);
  });

  it("forecasts nothing", () => {
    expect(allText).not.toMatch(/(?<!no )(?<!not )\bforecasts?\b|\bwill likely\b|\bpredicts?\b/i);
  });

  it("asserts no direction of movement", () => {
    expect(allText).not.toMatch(/\b(?:rises?|falls?|drops?|increases?|decreases?) when\b/i);
    expect(allText).not.toMatch(/\bcauses?\b|\bguarantee[sd]?\b/i);
  });
});
