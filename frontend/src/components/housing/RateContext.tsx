import { Link } from "react-router-dom";

/**
 * Rate context on the Housing page (Increment #45).
 *
 * ================================================================
 * THIS SECTION DELIBERATELY CONTAINS NO NUMBER
 * ================================================================
 *
 * Every reader of a housing page is thinking about mortgage rates. The
 * honest answer is that **MacroChipz does not track mortgage rates.**
 * It tracks U.S. Treasury yields, which are a different thing measured
 * a different way, and the two are related loosely rather than
 * mechanically.
 *
 * #45 permits a restrained rate-context section. The restrained version
 * is this one, and the reasoning is specific: putting a live 10-year
 * Treasury yield beside permits and starts would *visually assert a
 * relationship* — two numbers side by side on one page read as
 * connected — that MacroChipz has measured nothing about. It publishes
 * no housing-to-rates relationship, no elasticity and no lag, so
 * placing the figures together would be the page making a claim its own
 * data cannot support.
 *
 * So this is a signpost, not a readout. It names what MacroChipz has,
 * names what it does not have, and sends the reader to the surface
 * where the actual number lives with its own methodology and provenance
 * around it.
 *
 * FOUR THINGS THIS COMPONENT MUST NEVER DO, all of them tested:
 * call a Treasury yield a mortgage rate; estimate a mortgage rate;
 * compute a Treasury-to-mortgage spread; or imply the Fed sets mortgage
 * rates.
 */
export function RateContext() {
  return (
    <section aria-labelledby="housing-rates-heading">
      <h2 id="housing-rates-heading" className="text-sm font-medium text-fg-muted">
        What about mortgage rates?
      </h2>
      <div className="mt-3 max-w-prose space-y-3 text-sm text-fg-secondary">
        <p>
          <span className="font-medium text-fg">MacroChipz does not track mortgage rates.</span> It tracks U.S.
          Treasury yields — what it costs the federal government to borrow — which is a different number, set in a
          different market, and published by a different source.
        </p>
        <p>
          Lenders do price long-term loans against long-term borrowing conditions, so the two tend to move in
          related ways. But that relationship is loose and changes over time, and MacroChipz measures nothing about
          it: there is no estimated mortgage rate here, and no gap between Treasury yields and mortgage rates is
          calculated anywhere in this product.
        </p>
        <ul className="space-y-1.5">
          <li>
            <Link
              to="/rates"
              className="font-medium text-fg-secondary underline-offset-4 hover:text-fg hover:underline"
            >
              See the Treasury yields MacroChipz does track →
            </Link>
          </li>
          <li>
            <a
              href="/explain/fed-and-mortgage-rates"
              className="font-medium text-fg-secondary underline-offset-4 hover:text-fg hover:underline"
            >
              Wait, the Fed doesn&rsquo;t set mortgage rates?
            </a>
          </li>
        </ul>
      </div>
    </section>
  );
}
