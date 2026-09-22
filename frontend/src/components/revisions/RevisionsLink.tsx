import { Link } from "react-router-dom";

/**
 * The one intentional path into Revision Intelligence (Increment #45B).
 *
 * ================================================================
 * WHY THIS COMPONENT EXISTS
 * ================================================================
 *
 * #45A measured that `/revisions` had exactly **two** inbound links —
 * from `/inflation` and `/jobs`. Not from `/rates`, not from
 * `/housing`, not from the homepage, and not from navigation. Revision
 * Intelligence is the product's stated moat (#28 concluded that no
 * reviewed competitor handles point-in-time correctness) and it was
 * the least discoverable thing in the product.
 *
 * ================================================================
 * THE COPY IS THE CAREFUL PART
 * ================================================================
 *
 * This is a link to a page that currently has **nothing to show**, and
 * that is the honest state: MacroChipz has never captured a genuine
 * revision. So every word here is forward-looking.
 *
 * It says what MacroChipz WILL show when a revision arrives. It never
 * says a revision has happened, never implies the page contains
 * examples, and — the one that matters most — never suggests that a
 * backfilled baseline proves what a provider originally published.
 * #43's whole distinction rests on that, and a promotional sentence
 * here could undo it in one line.
 *
 * `context` names the world so the sentence is specific without
 * asserting anything about that world's data.
 *
 * WORDING NOTE: "after they first come out" rather than "after they are
 * first published". The homepage carries a guard forbidding
 * publication/availability language outside one sanctioned disclosure
 * -- a "Past due" release badge beside the word "published" reads as a
 * claim that the data arrived. The guard cannot tell a general
 * statement from a claim about a specific release, and it should not
 * have to: it is easier to say this without the word than to weaken a
 * guard that exists for a good reason.
 */
export function RevisionsLink({ context }: { context?: string }) {
  return (
    <section aria-labelledby="revisions-link-heading">
      <h2 id="revisions-link-heading" className="text-sm font-medium text-fg-muted">
        When a number changes
      </h2>
      <p className="mt-2 max-w-prose text-sm text-fg-secondary">
        {context
          ? `${context} figures are often revised after they first come out. `
          : "Official economic figures are often revised after they first come out. "}
        MacroChipz records what it knew at each point in time, so when a figure changes it can show you the change
        rather than quietly replacing the old value.
      </p>
      <Link
        to="/revisions"
        className="mt-3 inline-block text-sm font-medium text-fg-secondary underline-offset-4 hover:text-fg hover:underline"
      >
        How MacroChipz handles revisions →
      </Link>
    </section>
  );
}
