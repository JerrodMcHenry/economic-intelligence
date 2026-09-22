/**
 * What actually reaches your mortgage rate (Increment #44).
 *
 * A conceptual diagram, hand-authored in HTML/CSS. No diagramming
 * library, no chart library, nothing that needs JavaScript.
 *
 * THE SHAPE IS THE ARGUMENT. A single top-to-bottom arrow would say
 * "the Fed decides, and it flows down to you" — the exact belief this
 * explainer exists to correct. So several influences CONVERGE on
 * mortgage pricing instead, and the Fed is one of them rather than the
 * source of the chain.
 *
 * Accessible without colour, without hover and without the visual: the
 * whole thing is a described list, so a screen reader gets the same
 * argument in the same order, and the prose above it stands alone.
 */
export function InfluenceDiagram() {
  const influences = [
    {
      label: "Fed policy",
      detail: "Sets a short-term rate between banks, and shapes what investors expect next.",
    },
    {
      label: "Long-term Treasury yields",
      detail: "What it costs the U.S. government to borrow for years at a time.",
    },
    {
      label: "The market for bundled mortgages",
      detail: "Investors buy pools of home loans, and what they will pay feeds back into pricing.",
    },
    {
      label: "Lender costs and risks",
      detail: "Credit conditions, the chance a loan is repaid early, and what each lender needs to earn.",
    },
  ];

  return (
    <figure className="m-0">
      <figcaption className="type-label text-fg-muted">What reaches your mortgage rate</figcaption>

      <div className="mt-3 rounded-lg border border-line bg-surface p-4 sm:p-5">
        <ul className="grid gap-2 sm:grid-cols-2">
          {influences.map((influence) => (
            <li key={influence.label} className="rounded-md border border-line-subtle p-3">
              <p className="text-sm font-medium text-fg">{influence.label}</p>
              <p className="mt-1 text-sm text-fg-secondary">{influence.detail}</p>
            </li>
          ))}
        </ul>

        {/* Convergence, stated in text rather than drawn with arrows,
            so it survives having no colour and no pointer. */}
        <p aria-hidden="true" className="mt-4 text-center text-2xl leading-none text-fg-muted">
          ↓
        </p>

        <div className="mt-3 rounded-md border border-line-strong bg-surface-secondary p-3 text-center">
          <p className="text-sm font-semibold text-fg">The rate a lender quotes you</p>
          <p className="mt-1 text-sm text-fg-secondary">
            All of the above, plus competition between lenders — which is why two lenders can quote different rates on
            the same day.
          </p>
        </div>
      </div>

      <p className="mt-3 max-w-prose text-xs text-fg-muted">
        These influences interact rather than forming a single chain, and their relative importance changes over time.
        The diagram shows what feeds in, not a formula.
      </p>
    </figure>
  );
}
