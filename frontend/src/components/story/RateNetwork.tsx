import { Fragment } from "react";

import {
  NETWORK_EDGES,
  NETWORK_NODES,
  type NetworkNode,
  type NodeId,
} from "../../explainers/rateNetwork";

/**
 * THE INTERACTIVE RATE NETWORK (Increment #46E).
 *
 * ================================================================
 * VISUALS ARE SVG. INTERACTION IS HTML.
 * ================================================================
 *
 * The SVG draws the field, halos, edges and node cores, and is
 * `aria-hidden` — it is a picture. Every node is an absolutely
 * positioned HTML `<button>` layered over it at the same percentage
 * coordinates.
 *
 * Three problems disappear at once:
 *
 * 1. **Tap targets stop depending on SVG scale.** #46D shipped 41px
 *    controls because 48 SVG user units looked like 48 pixels. A scaled
 *    `viewBox` makes a user unit a RATIO, not a measurement. An HTML
 *    button with `min-h-11` cannot be shrunk by a viewBox.
 * 2. **Accessibility comes from the platform.** Focus ring, tab order,
 *    Enter/Space activation, `aria-pressed` and an accessible name are
 *    native to `<button>`. An SVG `role="button"` needs all four
 *    hand-built and gets them subtly wrong.
 * 3. **The behaviour becomes testable**, because jsdom has no layout
 *    engine — every assertion about SVG geometry is meaningless there,
 *    while button semantics are fully assertable.
 *
 * ================================================================
 * TWO SVG TRAPS THIS FILE DELIBERATELY AVOIDS
 * ================================================================
 *
 * `filter` and gradients both default to `objectBoundingBox` units, and
 * the Federal-Reserve-to-federal-funds edge is perfectly vertical — a
 * zero-width bounding box. A gradient in bbox units does not render on a
 * zero-area box, and a filter region of 340% of zero is zero. The single
 * most important edge on the page was invisible twice in the mockup
 * before this was understood.
 *
 * So: `gradientUnits="userSpaceOnUse"`, and glow from stacked strokes
 * rather than from a blur filter. Guarded by test.
 *
 * ================================================================
 * WHAT THE PICTURE MAY AND MAY NOT SAY
 * ================================================================
 *
 * An edge means "reaches". It never means "by this much" and never
 * means "in this direction". Edge weight, dash and arrowhead encode only
 * `sets` versus `influences`; nothing encodes magnitude, because the
 * registry holds no magnitude to encode.
 *
 * Dimming is never the only signal. Direct and indirect edges differ by
 * dash pattern and arrowhead as well as brightness, so the distinction
 * survives monochrome, low vision and forced-colours rendering — and
 * unrelated edges dim to a FLOOR rather than to invisibility.
 */

/** The board's coordinate space. Node positions are percentages of it. */
const W = 100;
const H = 100;

/** Radii in board units. The SVG scales; the buttons do not. */
const R = 2.6;
const R_SELECTED = 3.6;
const R_OUTCOME = 3.1;

function radiusFor(node: NetworkNode, selected: boolean): number {
  if (selected) return R_SELECTED;
  return node.outcome ? R_OUTCOME : R;
}

interface EdgeGeometry {
  readonly x1: number;
  readonly y1: number;
  readonly x2: number;
  readonly y2: number;
  /** Arrowhead tip and direction, for `sets` edges only. */
  readonly head: string;
}

/**
 * Trim an edge to the rims of the two nodes it joins, so no line tucks
 * under a glow, and build the arrowhead for a direct edge.
 *
 * The board is not square in screen pixels, so a naive unit vector in
 * board units would skew. `aspect` converts y-units to x-units for the
 * trigonometry and back again afterwards.
 */
function geometryFor(
  from: NetworkNode,
  to: NetworkNode,
  fromR: number,
  toR: number,
  aspect: number,
  arrow: boolean,
): EdgeGeometry {
  const dx = to.x - from.x;
  const dy = (to.y - from.y) / aspect;
  const len = Math.hypot(dx, dy) || 1;
  const ux = dx / len;
  const uy = dy / len;

  const gap = 1.2;
  const headRoom = arrow ? 3.2 : 0;
  const x1 = from.x + ux * (fromR + gap);
  const y1 = from.y + uy * (fromR + gap) * aspect;
  const x2 = to.x - ux * (toR + gap + headRoom);
  const y2 = to.y - uy * (toR + gap + headRoom) * aspect;

  const tipX = to.x - ux * (toR + 1);
  const tipY = to.y - uy * (toR + 1) * aspect;
  const back = 3;
  const wing = 1.6;
  const head = [
    `M ${tipX} ${tipY}`,
    `L ${tipX - ux * back - uy * wing} ${(tipY - uy * back * aspect + ux * wing * aspect).toFixed(3)}`,
    `L ${tipX - ux * back + uy * wing} ${(tipY - uy * back * aspect - ux * wing * aspect).toFixed(3)}`,
    "Z",
  ].join(" ");

  return { x1, y1, x2, y2, head };
}

export function RateNetwork({
  selectedId,
  onSelect,
}: {
  selectedId: NodeId;
  onSelect: (id: NodeId) => void;
}) {
  /**
   * The board is square at every breakpoint, so one constant serves both
   * the SVG geometry and the button positions. Kept here rather than
   * measured, because a measured value would differ between the browser
   * and the prerender — and the two layers must agree exactly or the
   * buttons drift off their dots.
   */
  const aspect = 1;

  const related = new Set<string>();
  for (const edge of NETWORK_EDGES) {
    if (edge.from === selectedId || edge.to === selectedId) {
      related.add(`${edge.from}->${edge.to}`);
    }
  }

  return (
    <div
      /* Fills the width it is given, up to a cap that rises with the
         breakpoint. The earlier 330px phone cap left 110px of a 440px
         screen unused AND made the board shorter, which is what forced
         the node chips close enough together to overlap — a square
         board's width IS its vertical room.
         The `lg` cap is the #46F change: at 1440px the board was 448px,
         31% of the viewport, in a page that never grew past 672px. */
      className="lx-board relative mx-auto w-full max-w-[28rem] lg:max-w-[38rem]"
      data-testid="rate-network"
    >
      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="xMidYMid meet"
        className="lx-svg block h-auto w-full overflow-visible"
        /* Square, not 4:5. Measured at 390px, a 4:5 board was 447px
           tall and pushed the selected-node panel to 1001px — past the
           fold, which the spec forbids. The nodes sit between 11% and
           91% vertically with no two adjacent chips in the same
           horizontal zone, so compressing to 1:1 costs no legibility. */
        style={{ aspectRatio: "1 / 1" }}
        aria-hidden="true"
        focusable="false"
      >
        <defs>
          {/*
            userSpaceOnUse, NOT the default objectBoundingBox. The
            Fed-to-federal-funds edge is perfectly vertical, so its
            bounding box has zero width — and a gradient in bounding-box
            units is not rendered at all on a zero-area box.
          */}
          <linearGradient id="lxEdgeSets" gradientUnits="userSpaceOnUse" x1="10" y1="5" x2="90" y2="95">
            <stop offset="0%" stopColor="#c2caff" />
            <stop offset="100%" stopColor="#ba7af0" />
          </linearGradient>
          <radialGradient id="lxHalo">
            <stop offset="0%" stopColor="#a2b0ff" stopOpacity="0.62" />
            <stop offset="46%" stopColor="#7c60f0" stopOpacity="0.22" />
            <stop offset="100%" stopColor="#7c60f0" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="lxHaloSelected">
            <stop offset="0%" stopColor="#d4d9ff" stopOpacity="0.92" />
            <stop offset="40%" stopColor="#8f7bff" stopOpacity="0.42" />
            <stop offset="100%" stopColor="#8f7bff" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="lxField">
            <stop offset="0%" stopColor="#7c60f0" stopOpacity="0.22" />
            <stop offset="100%" stopColor="#7c60f0" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* ambient bloom under the selection, so the field reacts too */}
        {NETWORK_NODES.filter((n) => n.id === selectedId).map((n) => (
          <ellipse key={n.id} cx={n.x} cy={n.y} rx={34} ry={34 / aspect} fill="url(#lxField)" />
        ))}

        {/*
          Halos sit BELOW the edges. A bloom strong enough to match the
          approved mockup will otherwise swallow a line drawn underneath
          it — which is exactly how the most important edge on the page
          went missing during visual exploration.
        */}
        <g>
          {NETWORK_NODES.map((node) => {
            const selected = node.id === selectedId;
            const r = selected ? 15.5 : 11.5;
            return (
              <ellipse
                key={node.id}
                cx={node.x}
                cy={node.y}
                rx={r}
                ry={r / aspect}
                fill={selected ? "url(#lxHaloSelected)" : "url(#lxHalo)"}
                className="transition-opacity duration-300 motion-reduce:transition-none"
                opacity={selected ? 1 : 0.85}
              />
            );
          })}
        </g>

        <g>
          {NETWORK_EDGES.map((edge) => {
            const from = NETWORK_NODES.find((n) => n.id === edge.from)!;
            const to = NETWORK_NODES.find((n) => n.id === edge.to)!;
            const isRelated = related.has(`${edge.from}->${edge.to}`);
            const sets = edge.kind === "sets";
            const g = geometryFor(
              from,
              to,
              radiusFor(from, from.id === selectedId),
              radiusFor(to, to.id === selectedId),
              aspect,
              sets,
            );
            const d = `M ${g.x1} ${g.y1} L ${g.x2} ${g.y2}`;
            const key = `${edge.from}->${edge.to}`;

            return (
              <g
                key={key}
                data-edge={key}
                data-kind={edge.kind}
                data-state={isRelated ? "related" : "dim"}
                /* The dim value is a FLOOR, not a preference: an
                   unrelated relationship stays visible rather than
                   becoming inaccessible. */
                opacity={isRelated ? 1 : 0.32}
                className="transition-opacity duration-300 motion-reduce:transition-none"
              >
                {sets ? (
                  <>
                    {/* Glow from stacked strokes, never from `filter`:
                        a filter region is a percentage of the bounding
                        box, and a vertical line's box has zero width. */}
                    <path d={d} stroke="url(#lxEdgeSets)" strokeWidth={3} strokeLinecap="round" fill="none" opacity={0.2} />
                    <path d={d} stroke="url(#lxEdgeSets)" strokeWidth={1.6} strokeLinecap="round" fill="none" opacity={0.42} />
                    <path d={d} stroke="url(#lxEdgeSets)" strokeWidth={0.75} strokeLinecap="round" fill="none" />
                    <path d={g.head} fill="#cfd5ff" opacity={0.35} stroke="#cfd5ff" strokeWidth={1.4} strokeLinejoin="round" />
                    <path d={g.head} fill="#e6e9ff" />
                  </>
                ) : (
                  <path
                    d={d}
                    stroke="var(--lx-edge)"
                    strokeWidth={0.62}
                    strokeDasharray="0.7 2.3"
                    strokeLinecap="round"
                    fill="none"
                  />
                )}
              </g>
            );
          })}
        </g>

        <g>
          {NETWORK_NODES.map((node) => {
            const selected = node.id === selectedId;
            const r = radiusFor(node, selected);
            return (
              <g key={node.id} className="transition-all duration-300 motion-reduce:transition-none">
                {selected && (
                  <>
                    <ellipse cx={node.x} cy={node.y} rx={6.6} ry={6.6 / aspect} fill="none" stroke="rgba(196,204,255,.46)" strokeWidth={0.35} />
                    <ellipse cx={node.x} cy={node.y} rx={9.2} ry={9.2 / aspect} fill="none" stroke="rgba(162,176,255,.16)" strokeWidth={0.28} />
                  </>
                )}
                <ellipse
                  cx={node.x}
                  cy={node.y}
                  rx={r}
                  ry={r / aspect}
                  fill="var(--lx-node-core)"
                  stroke={selected ? "#dfe3ff" : "#9facf1"}
                  strokeWidth={selected ? 0.75 : 0.5}
                />
                <ellipse
                  cx={node.x}
                  cy={node.y}
                  rx={selected ? 1.2 : 0.85}
                  ry={(selected ? 1.2 : 0.85) / aspect}
                  fill={selected ? "#ffffff" : "#e4e8ff"}
                />
              </g>
            );
          })}
        </g>
      </svg>

      {/*
        THE INTERACTION LAYER. Real buttons, positioned at the same
        percentages the SVG draws at, so the two cannot drift. `min-h-11`
        and `min-w-11` are 44px and are immune to the viewBox.

        BELOW 312px IT REFLOWS TO A SINGLE COLUMN — see the
        `[data-surface="luminous"]` block in globals.css. The same six
        buttons, in the same DOM order, stop being absolutely positioned
        and become a flex column; the SVG hides and the `lx-link` rows
        appear in its place. One set of controls, no duplicated DOM, no
        JavaScript measurement, and nothing to mismatch at hydration.
      */}
      <div className="lx-layer absolute inset-0">
        {NETWORK_NODES.map((node, index) => {
          const selected = node.id === selectedId;
          const onRight = node.side === "right";
          const previous = index > 0 ? NETWORK_NODES[index - 1]! : null;
          // A connector is drawn only where an edge genuinely joins two
          // ADJACENT rows. Adjacency without a connector therefore means
          // "no relationship", which is true and readable; the two edges
          // that skip a row are carried by the panel's Connections list.
          const link =
            previous === null
              ? undefined
              : NETWORK_EDGES.find(
                  (e) =>
                    (e.from === previous.id && e.to === node.id) ||
                    (e.from === node.id && e.to === previous.id),
                );
          return (
            <Fragment key={node.id}>
              {link && (
                <span className="lx-link" aria-hidden="true">
                  <span
                    className={
                      link.kind === "sets" ? "lx-link-rule lx-link-sets" : "lx-link-rule"
                    }
                  />
                  <span className="lx-link-label">
                    {link.kind === "sets" ? "sets" : "influences"}
                  </span>
                </span>
              )}
            <button
              type="button"
              aria-pressed={selected}
              /* The chip is the short form; the accessible name is the
                 accurate one. A screen reader should hear "Mortgage-backed
                 securities", not whatever fits in the diagram. */
              aria-label={node.label}
              data-node={node.id}
              onClick={() => onSelect(node.id)}
              className={[
                "lx-node flex min-h-11 min-w-11 items-center gap-2 rounded-full px-3 py-1.5",
                "text-left text-[13px] font-semibold leading-tight tracking-tight",
                "transition-colors duration-200 motion-reduce:transition-none",
                onRight ? "flex-row" : "flex-row-reverse",
                selected
                  ? "border border-[rgba(196,204,255,.45)] bg-[rgba(40,30,86,.88)] text-[#f4f5ff]"
                  : "border border-[rgba(255,255,255,.10)] bg-[rgba(18,13,36,.78)] text-fg hover:border-[rgba(196,204,255,.3)]",
              ].join(" ")}
              /*
                The max width has to account for the 14px the chip is
                pushed away from its dot, or it runs off the board. The
                old form used a flat 2% margin, which is 2% of the BOARD
                — smaller than 14px on anything under 700px wide — so at
                320px the `Mortgage-backed securities` chip hung 8px
                outside the diagram. `calc` with the same offset the
                transform uses cannot drift from it.
              */
              data-side={node.side}
              style={
                {
                  "--lx-x": `${node.x}%`,
                  "--lx-x-inv": `${100 - node.x}%`,
                  "--lx-y": `${node.y}%`,
                  "--lx-max": onRight
                    ? `calc(${100 - node.x}% - 18px)`
                    : `calc(${node.x}% - 18px)`,
                } as React.CSSProperties
              }
            >
              <span
                aria-hidden="true"
                className={[
                  "h-1.5 w-1.5 shrink-0 rounded-full",
                  selected ? "bg-[#ffffff]" : "bg-[#9facf1]",
                ].join(" ")}
              />
              <span className="truncate">{node.chip}</span>
            </button>
            </Fragment>
          );
        })}
      </div>
    </div>
  );
}
