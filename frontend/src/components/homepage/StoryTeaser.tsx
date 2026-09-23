import { Link } from "react-router-dom";

import { explainerById } from "../../explainers/registry";
import { NETWORK_EDGES, NETWORK_NODES, networkNode } from "../../explainers/rateNetwork";

/**
 * THE MOBILE STORY TEASER (Increment #48B).
 *
 * ================================================================
 * THE MEASURED PROBLEM
 * ================================================================
 *
 * At a 390x844 viewport the featured story sat 1,637px down the page
 * — two full screens, the second of which is a Treasury chart. The
 * one genuinely interactive thing MacroChipz has built was therefore
 * invisible to anyone who did not scroll past the data, which is the
 * opposite of the ordering Constitution §3 asks for: the mortgage-rate
 * misconception is the acquisition wedge.
 *
 * So on phones the story is offered immediately after the hero's
 * discovery strip and BEFORE the chart. The chart is not moved, not
 * shrunk and not hidden; something short is simply placed in front of
 * it.
 *
 * ================================================================
 * IT IS A TEASER, AND IT APPEARS EXACTLY ONCE
 * ================================================================
 *
 * This renders below `lg`; `FeaturedStory` renders from `lg`. A reader
 * on a phone meets the story here and nowhere else, and a reader on a
 * desktop meets it in the editorial position it already had. Two
 * copies on one screen would be worse than the problem.
 *
 * ================================================================
 * EVERY WORD IS ALREADY REVIEWED
 * ================================================================
 *
 * The question is the #44 explainer registry's own. The count comes
 * from `rateNetwork`, which is the same curated registry the story and
 * the desktop preview read — so if a seventh actor were ever added,
 * this line changes with it rather than going quietly stale.
 *
 * NO NEW CAUSAL CLAIM IS MADE HERE. It states how many actors there
 * are and how many of them anyone sets. The glyph draws the registry's
 * real edges and nothing else — decorative and `aria-hidden`, which is
 * not a licence to draw a shape the model does not have.
 */

const ACTOR_COUNT = NETWORK_NODES.length;
const SET_EDGES = NETWORK_EDGES.filter((edge) => edge.kind === "sets");

export function StoryTeaser() {
  const explainer = explainerById("explain.fed-and-mortgage-rates");
  if (explainer === undefined) return null;

  return (
    <Link
      to="/story/fed-and-mortgage-rates"
      /*
       * ONE ELEMENT, AND IT IS THE WHOLE STRIP. Everything inside is a
       * `<span>`, so there is exactly one thing to tab to, one focus
       * ring — the global `:focus-visible` outline wraps the entire
       * card — and no dead area a thumb can miss.
       *
       * #48C: it read as a navigation row with a picture next to it.
       * The network is now framed as a thing you open rather than an
       * icon that decorates a link, and the arrow became a round
       * affordance. No prose was added and the height did not move.
       */
      className="lx-teaser group flex items-center gap-3.5 rounded-xl px-3.5 py-3.5 transition-colors motion-reduce:transition-none lg:hidden"
    >
      {/*
       * The network, framed, with the affordance ON the frame.
       *
       * The arrow first sat at the far right of the strip, and the
       * 56px frame plus a 28px chip plus their gaps took 36px off the
       * text column — enough to push the meta line to three lines and
       * the strip from 133px to 153. Putting the badge on the corner
       * of the thumbnail, the way a play badge sits on a video still,
       * gives all of that back AND ties the affordance to the thing it
       * opens.
       */}
      <span className="lx-teaser-frame relative flex h-14 w-14 flex-none items-center justify-center rounded-lg">
        <TeaserGlyph />

        {/*
         * TOP-RIGHT, and that corner is chosen rather than default.
         *
         * Bottom-right is the conventional place for an action badge,
         * and it sat directly on top of the `mortgage-rate` node --
         * the registry puts that one at x 78, y 92. Covering a node of
         * a six-node diagram to make room for decoration is the wrong
         * trade. The top-right of the board is empty: the nearest node
         * is `treasury` at y 41.6, well clear.
         *
         * Visual only. The link's own text is its accessible name, and
         * a second arrow in the accessibility tree would be noise.
         */}
        <span
          aria-hidden="true"
          className="lx-teaser-go absolute -right-1.5 -top-1.5 flex h-6 w-6 items-center justify-center rounded-full text-[12px] leading-none"
        >
          →
        </span>
      </span>

      <span className="min-w-0 flex-1">
        <span className="type-label block text-[color:var(--mc-brand)]">Interactive story</span>
        <span className="mt-1 block text-[15px] font-semibold leading-snug text-fg">{explainer.question}</span>
        <span className="mt-0.5 block type-meta text-fg-muted">
          {ACTOR_COUNT} actors, {SET_EDGES.length} of them set by anyone. Tap through the network.
        </span>
      </span>

    </Link>
  );
}

/**
 * The network at thumbnail scale: the real nodes and the two real
 * `sets` edges, read from the registry rather than drawn by hand.
 *
 * Decorative and `aria-hidden` — the link's own text carries the
 * meaning. It is drawn from the registry anyway, because a glyph that
 * implied a shape the model does not have would be a claim, and a
 * decorative one is no more excusable than a large one.
 */
function TeaserGlyph() {
  return (
    <svg
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      aria-hidden="true"
      /* Inset inside its frame so the outermost nodes are not clipped
         by the rounded corners: the registry's `x` runs 15 to 85 and
         its `y` 8 to 92, and a node is drawn with a halo around it. */
      className="h-[42px] w-[38px] flex-none"
    >
      {NETWORK_EDGES.map((edge) => {
        const from = networkNode(edge.from);
        const to = networkNode(edge.to);
        const d = `M ${from.x} ${from.y} L ${to.x} ${to.y}`;
        return edge.kind === "sets" ? (
          <path key={d} d={d} stroke="var(--mc-brand)" strokeWidth={6} strokeLinecap="round" fill="none" />
        ) : (
          <path
            key={d}
            d={d}
            stroke="var(--lx-edge)"
            strokeWidth={3}
            strokeDasharray="6 10"
            strokeLinecap="round"
            fill="none"
          />
        );
      })}
      {/* Halo then core, in that order: a halo drawn over an edge
          swallows it, which is the #46E layering defect. */}
      {NETWORK_NODES.map((node) => (
        <circle key={`halo-${node.id}`} cx={node.x} cy={node.y} r={11} fill="rgba(162,176,255,0.20)" />
      ))}
      {NETWORK_NODES.map((node) => (
        <circle key={node.id} cx={node.x} cy={node.y} r={6.5} fill="#e9ecff" />
      ))}
    </svg>
  );
}
