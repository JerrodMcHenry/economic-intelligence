import { Link } from "react-router-dom";

import { explainerById } from "../../explainers/registry";
import {
  NETWORK_EDGES,
  NETWORK_NODES,
  NETWORK_STANDFIRST,
  networkNode,
  type NetworkEdge,
  type NetworkNode,
} from "../../explainers/rateNetwork";
import { describeNetwork } from "./networkPreviewDescription";

/**
 * FEATURED DISCOVERY — the mortgage-rate story (Increment #48).
 *
 * ================================================================
 * WHY THIS ONE, AND WHY IT GETS ITS OWN BAND
 * ================================================================
 *
 * Product Constitution §3: the mortgage-rate misconception is the
 * acquisition wedge. #45A measured that the question a reader arrives
 * searching for — *"Wait, the Fed doesn't set mortgage rates?"* — sat
 * twelve explainers deep while the first screen showed a Treasury
 * yield. `HomeQuestions` fixed reachability; this promotes the one
 * genuinely interactive thing MacroChipz has built from a list item to
 * its own band.
 *
 * ================================================================
 * THE PREVIEW IS THE REAL GRAPH, OR IT IS NOT DRAWN
 * ================================================================
 *
 * Every node and every edge below comes from `explainers/rateNetwork.ts`
 * — the curated registry the story itself renders, whose `role` strings
 * are each required to be a contiguous substring of reviewed copy. This
 * component defines NO economic relationship of its own and no
 * component-local list of actors to drift from it.
 *
 * `fed-funds → treasury` is deliberately absent from that registry. A
 * decorative preview that "tidied up" the diagram by joining them would
 * assert exactly the causal chain the story exists to correct — so the
 * edges are read, never redrawn.
 *
 * ================================================================
 * NO TEXT INSIDE THE SVG. THE LABELS ARE HTML.
 * ================================================================
 *
 * #46D shipped a diagram whose 48-unit tap targets rendered at 41px,
 * because SVG units are not CSS pixels. Text has exactly the same
 * problem: a `font-size` inside a `viewBox` shrinks with the box.
 *
 * The preview first shipped with no labels at all -- six dots and a
 * legend -- and that is not a preview of anything. So the labels are
 * now an HTML layer positioned over the SVG at the registry's own
 * percentage coordinates, which is the split the story page already
 * uses: VISUALS ARE SVG, EVERYTHING WITH A TYPE SIZE IS HTML. Their
 * size is in CSS pixels and does not scale with the board.
 *
 * The whole figure carries one accessible name built from the
 * registry, and the SVG and the label layer are both `aria-hidden` --
 * otherwise a screen reader hears six names with no relationships,
 * which is worse than the description.
 */

/*
 * #48B REMOVED A SENTENCE, NOT A FACT.
 *
 * "Six actors sit between a Federal Reserve decision and the rate a
 * lender quotes you. Only two of them are set by anyone at all." was
 * true, registry-derived and entirely redundant beside a diagram that
 * names six actors and a list that shows exactly two of them being
 * set. The network carries the explanation; the full detail is in the
 * story, which is where someone who wants it is going.
 *
 * The COUNT still appears on the mobile teaser, where there is no
 * diagram to carry it -- see `StoryTeaser`.
 */

export function FeaturedStory() {
  const explainer = explainerById("explain.fed-and-mortgage-rates");

  // The registry is the source of the question. If the entry were ever
  // removed, the band removes itself rather than rendering a dead link.
  if (explainer === undefined) return null;

  return (
    <section aria-labelledby="featured-heading">
      <h2 id="featured-heading" className="text-sm font-medium text-fg-muted">
        Featured discovery
      </h2>

      <div className="lx-card mt-4 grid gap-5 rounded-xl p-5 sm:p-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,17rem)] lg:items-center lg:gap-10">
        <div>
          <p className="type-label text-fg-muted">Interactive story</p>

          <h3 className="mt-2 text-xl font-semibold tracking-tight text-fg sm:text-2xl">{explainer.question}</h3>

          <p className="mt-3 max-w-prose text-fg-secondary">{NETWORK_STANDFIRST}</p>

          {/*
           * WHO SETS WHAT, IN WORDS. Composed from the registry's own
           * `setBy` field -- not written here -- so the sentence and
           * the solid edges above it cannot disagree. This is the line
           * that makes the preview answer its own question without a
           * click: two of six, and which two.
           */}
          <dl className="mt-3 space-y-1.5">
            {NETWORK_EDGES.filter((edge) => edge.kind === "sets").map((edge) => {
              const target = networkNode(edge.to);
              return (
                <div key={edge.to} className="flex flex-wrap gap-x-1.5 type-meta">
                  <dt className="font-semibold text-fg-secondary">{target.label}</dt>
                  <dd className="text-fg-muted">set by {target.setBy ?? networkNode(edge.from).label}</dd>
                </div>
              );
            })}
          </dl>

          <Link
            to="/story/fed-and-mortgage-rates"
            className="mt-5 inline-flex min-h-11 items-center gap-2 rounded-lg border border-[color:var(--lx-card-hi)] bg-[color:var(--lx-selected)] px-4 text-sm font-semibold text-fg transition-colors hover:bg-[color:var(--lx-selected-hover)] motion-reduce:transition-none"
          >
            Open the story
            <span aria-hidden="true">→</span>
          </Link>
        </div>

        <div>
          <NetworkPreview />
          <ul className="mt-4 flex flex-wrap gap-x-4 gap-y-1 type-meta text-fg-muted">
            <li className="flex items-center gap-1.5">
              <span aria-hidden="true" className="inline-block h-0.5 w-5 rounded-full bg-[color:var(--mc-brand)]" />
              Someone sets it
            </li>
            <li className="flex items-center gap-1.5">
              <span
                aria-hidden="true"
                className="inline-block h-0.5 w-5 rounded-full"
                style={{
                  backgroundImage:
                    "repeating-linear-gradient(90deg, var(--lx-edge) 0 3px, transparent 3px 7px)",
                }}
              />
              It feeds in
            </li>
          </ul>
        </div>
      </div>
    </section>
  );
}

/**
 * The six actors at preview scale, positioned by the registry's own
 * `x`/`y` percentages so the preview and the story cannot disagree
 * about the shape of the thing.
 */
function NetworkPreview() {
  return (
    <div
      role="img"
      aria-label={describeNetwork()}
      /*
       * Square on a phone, taller from `sm`. The registry's `y` spans
       * 8 to 92 against an `x` of only 15 to 85, so the board wants to
       * be tall -- but at 390px a 5:6 box is 361px of diagram before
       * the legend, and the six rows stay legible at 302px: 16.8
       * percentage points of vertical spacing is 51px there, against
       * labels that wrap to at most 26.
       */
      className="relative mx-auto aspect-square w-full max-w-[19rem] sm:aspect-[5/6] lg:max-w-none"
    >
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true" className="absolute inset-0 h-full w-full">
        {/* `gradientUnits="userSpaceOnUse"`, and not by preference: the
            default `objectBoundingBox` gives a perfectly vertical line a
            zero-width box, and the gradient then paints nothing. That
            defect shipped twice in the #46E mockups. */}
        <linearGradient id="featured-edge" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="100" y2="100">
          <stop offset="0%" stopColor="#c2caff" />
          <stop offset="100%" stopColor="#ba7af0" />
        </linearGradient>

        {NETWORK_EDGES.map((edge) => (
          <Edge key={`${edge.from}-${edge.to}`} edge={edge} />
        ))}
      </svg>

      {/* The dots are drawn in HTML too, so they stay round under the
          board's non-uniform scale -- `preserveAspectRatio="none"` is
          what lets the edges reach the real coordinates, and it would
          have turned an SVG circle into an ellipse. */}
      {NETWORK_NODES.map((node) => (
        <NodeLabel key={node.id} node={node} />
      ))}
    </div>
  );
}

/**
 * One node: a dot at the registry's coordinates, and its short name
 * beside it on the side the registry chose.
 *
 * The label is capped at the distance to the board edge so a long name
 * -- "Mortgage-backed securities" is the one that tests this -- wraps
 * rather than hanging outside the figure. The cap is computed from the
 * SAME offset the dot uses, so the two cannot drift apart; a flat
 * percentage margin was the #46E defect that let the longest chip hang
 * 8px outside the board at 320px.
 */
function NodeLabel({ node }: { node: NetworkNode }) {
  const onRight = node.side === "right";
  return (
    <span
      aria-hidden="true"
      className="absolute flex -translate-y-1/2 items-center gap-1.5"
      style={{
        top: `${node.y}%`,
        ...(onRight ? { left: `${node.x}%` } : { right: `${100 - node.x}%`, flexDirection: "row-reverse" }),
        maxWidth: onRight ? `calc(${100 - node.x}% - 4px)` : `calc(${node.x}% - 4px)`,
      }}
    >
      <span className="h-2 w-2 flex-none rounded-full bg-[#e4e8ff] ring-[3px] ring-[rgba(162,176,255,0.22)]" />
      <span
        className={`min-w-0 text-[11px] font-semibold leading-tight text-fg-secondary ${
          onRight ? "text-left" : "text-right"
        }`}
      >
        {node.chip}
      </span>
    </span>
  );
}

function Edge({ edge }: { edge: NetworkEdge }) {
  const from = networkNode(edge.from);
  const to = networkNode(edge.to);
  const d = `M ${from.x} ${from.y} L ${to.x} ${to.y}`;

  // `sets` is drawn solid and lit; `influences` is dashed and quiet.
  // The distinction is the story's entire point, so it is carried by
  // stroke pattern AND weight, never by colour alone.
  if (edge.kind === "sets") {
    return (
      <>
        <path d={d} stroke="url(#featured-edge)" strokeWidth={2.6} strokeLinecap="round" fill="none" opacity={0.28} />
        <path d={d} stroke="url(#featured-edge)" strokeWidth={0.9} strokeLinecap="round" fill="none" />
      </>
    );
  }

  return (
    <path d={d} stroke="var(--lx-edge)" strokeWidth={0.6} strokeDasharray="1.4 3.2" strokeLinecap="round" fill="none" />
  );
}
