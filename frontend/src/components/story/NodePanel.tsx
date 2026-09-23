import { connectionsFor, networkNode, type NodeId } from "../../explainers/rateNetwork";

/**
 * The selected-node panel (Increment #46E).
 *
 * ================================================================
 * A PANEL, NOT A BOTTOM SHEET
 * ================================================================
 *
 * The brief allowed either. A sheet was rejected for one reason: it
 * overlays the bottom of the viewport, which at 390px is exactly where
 * the lower half of the diagram lives — so the thing describing a node
 * would cover the node. The brief forbids obscuring the selection, and
 * an overlay that must be dismissed to see what it is talking about also
 * costs an interaction on every selection.
 *
 * So the panel sits directly under the diagram, and the two are sized so
 * both fit above 844px at 390px.
 *
 * ================================================================
 * WHY IT DOES NOT TAKE FOCUS
 * ================================================================
 *
 * Selecting a node is not navigation. Moving focus here would strand a
 * keyboard user who wanted to try the next node, and it would fight a
 * screen-reader user's own reading position. Instead the panel is a
 * polite live region: focus stays on the button, and the new content is
 * announced.
 *
 * ================================================================
 * THE ONE THING IT MUST ALWAYS SAY
 * ================================================================
 *
 * Whether anybody sets this number. `setBy` is `null` for four of the
 * six nodes and that is the substantive finding of the whole story, so
 * the absence is stated in words rather than left as a missing row.
 */
export function NodePanel({ selectedId }: { selectedId: NodeId }) {
  const node = networkNode(selectedId);
  const links = connectionsFor(selectedId);

  const reaches = [...links.sets, ...links.influences];
  const fedFrom = [...links.setBy, ...links.influencedBy];

  return (
    <section
      aria-live="polite"
      aria-label="Selected node"
      /* A floor on the height, so switching between a long role and a
         short one does not shunt everything below the panel up and down
         the page on every tap. Re-measured at 390px after the
         connections list moved behind a disclosure. */
      className="lx-card lx-card-selected min-h-[172px] rounded-2xl p-3.5 sm:min-h-0 sm:p-5"
    >
      <p className="type-label flex items-center gap-2 text-[#a2b0ff]">
        <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-[#a2b0ff]" />
        Selected
      </p>

      <h2 className="mt-1.5 text-lg font-semibold leading-snug tracking-tight text-fg sm:text-xl">
        {node.label}
      </h2>

      <p className="mt-1.5 max-w-prose text-[13.5px] leading-snug text-fg-secondary">{node.role}</p>

      <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1.5 border-t border-white/10 pt-2.5">
        {node.setBy === null ? (
          <>
            <span className="inline-flex shrink-0 items-center rounded-full border border-dashed border-white/25 px-2.5 py-1 text-[10.5px] font-bold uppercase tracking-widest text-fg-secondary">
              Nobody sets it
            </span>
            <span className="text-xs text-fg-muted">it is priced in a market</span>
          </>
        ) : (
          <>
            <span className="inline-flex shrink-0 items-center rounded-full border border-[rgba(162,176,255,.38)] bg-[rgba(124,96,240,.26)] px-2.5 py-1 text-[10.5px] font-bold uppercase tracking-widest text-[#dfe4ff]">
              Directly set
            </span>
            <span className="text-xs text-fg-muted">{node.setBy}</span>
          </>
        )}
      </div>

      {/*
        COMPACT BY DEFAULT, EXPANDABLE ON DEMAND.

        The role and whether anybody sets this number are the answer, and
        they are always visible — the point of tapping a node is to read
        them without scrolling. The connection lists are a second-order
        detail AND are already shown in the diagram by the highlight, so
        they fold away. That keeps the panel short enough to land fully
        on screen right after a tap, which is what the brief asked for.

        Still a real disclosure, not a hidden feature: it is a native
        `<details>`, so it is keyboard-operable, announced, and readable
        for anyone who cannot see the highlighted edges.
      */}
      {(reaches.length > 0 || fedFrom.length > 0) && (
        <details className="group mt-1.5">
          <summary className="flex min-h-11 cursor-pointer list-none items-center gap-1.5 text-xs text-fg-muted [&::-webkit-details-marker]:hidden">
            <svg
              viewBox="0 0 16 16"
              aria-hidden="true"
              className="h-3 w-3 flex-none transition-transform group-open:rotate-90 motion-reduce:transition-none"
            >
              <path
                d="M6 3l5 5-5 5"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            Connections
          </summary>
          <dl className="grid gap-1 pb-0.5 text-xs">
            {fedFrom.length > 0 && (
              <div className="flex gap-2">
                <dt className="shrink-0 text-fg-muted">Fed by</dt>
                <dd className="text-fg-secondary">{fedFrom.map((n) => n.label).join(", ")}</dd>
              </div>
            )}
            {reaches.length > 0 && (
              <div className="flex gap-2">
                <dt className="shrink-0 text-fg-muted">Reaches</dt>
                <dd className="text-fg-secondary">{reaches.map((n) => n.label).join(", ")}</dd>
              </div>
            )}
          </dl>
        </details>
      )}
    </section>
  );
}
