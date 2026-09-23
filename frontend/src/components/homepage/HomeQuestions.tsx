import { Link } from "react-router-dom";

import { explainerById } from "../../explainers/registry";

/**
 * Curated questions on the homepage (Increment #45B).
 *
 * ================================================================
 * THE MEASURED PROBLEM THIS SOLVES
 * ================================================================
 *
 * #45A extracted the site's real link graph and found that **every
 * inbound link to every explainer originates on a world page**. Zero
 * orphans, which is good — but a reader who lands on `/` and does not
 * open a world never encounters educational content at all. The
 * educational layer was optimised for arriving from a video and
 * invisible to arriving from the front door.
 *
 * It is also the fix for the weakest stage of the behavioural loop.
 * #45A found WOW broken: the first screen is a Treasury yield, while
 * the genuinely surprising things MacroChipz has written — *"Wait, the
 * Fed doesn't set mortgage rates?"* — sat twelve explainers deep.
 * Those questions ARE the hook, and they were unreachable from the
 * entrance.
 *
 * ================================================================
 * CURATED, NOT COMPUTED
 * ================================================================
 *
 * `FEATURED` is a hand-written list of three ids. There is no
 * recommender here, no popularity, no similarity scoring, no
 * personalisation and no ranking — the same rule the explainer
 * registry's own `related` field already holds itself to.
 *
 * Three, deliberately. Enough to show the product has a voice; few
 * enough that it stays an offer rather than a feed, and that the
 * homepage does not become the dashboard #45A warned against.
 *
 * Chosen for what each one corrects, not for what it covers:
 * one crosses two worlds, one corrects the misreading created by a
 * number on a MacroChipz page, and one corrects the most common
 * misunderstanding of the word "inflation" itself.
 *
 * An id that does not resolve is DROPPED rather than rendered as a
 * dead link, and a test asserts all three resolve — so a typo fails
 * the suite instead of shipping.
 */
/*
 * #48 REPLACED ONE ID, AND ONLY FOR DUPLICATION.
 *
 * `explain.fed-and-mortgage-rates` left this list because the
 * interactive story built on it now has its own featured band directly
 * above — the same question twice within one screen is exactly the
 * repetition #48 set out to remove. It is not demoted: it moved up.
 *
 * `explain.why-the-10-year-matters` takes the slot because it is the
 * question a reader has immediately AFTER the story answers the first
 * one, which keeps this list a path rather than a menu.
 */
const FEATURED: ReadonlyArray<string> = [
  "explain.why-the-10-year-matters",
  "explain.saar-housing",
  "explain.inflation-vs-prices",
];

export function HomeQuestions() {
  const questions = FEATURED.map((id) => explainerById(id)).filter(
    (explainer): explainer is NonNullable<typeof explainer> => explainer !== undefined,
  );

  if (questions.length === 0) return null;

  return (
    <section aria-labelledby="questions-heading">
      <h2 id="questions-heading" className="text-sm font-medium text-fg-muted">
        Questions people ask
      </h2>
      <p className="mt-2 max-w-prose text-sm text-fg-secondary">
        Short, plain answers — no economics background needed.
      </p>

      <ul className="mt-4 space-y-2">
        {questions.map((explainer) => (
          <li key={explainer.id}>
            <Link
              to={`/explain/${explainer.slug}`}
              className="font-medium text-fg underline-offset-4 hover:underline"
            >
              {explainer.question}
            </Link>
            <p className="mt-0.5 max-w-prose text-sm text-fg-secondary">{explainer.answer}</p>
          </li>
        ))}
      </ul>

      <Link
        to="/explain"
        className="mt-4 inline-block text-sm font-medium text-fg-secondary underline-offset-4 hover:text-fg hover:underline"
      >
        All questions →
      </Link>
    </section>
  );
}

/** Exported for the test that asserts every featured id resolves. */
export const FEATURED_EXPLAINER_IDS = FEATURED;
