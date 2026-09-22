/**
 * The explainer index — `/explain` (Increment #45B).
 *
 * ================================================================
 * WHY THIS EXISTS, AND WHY IT IS NOT IN PRIMARY NAVIGATION
 * ================================================================
 *
 * #44 shipped twelve permanent explainers and deliberately deferred
 * site-level discovery. #45A then measured the consequence: every
 * inbound link to every explainer originates on a world page, so a
 * reader who lands on `/` and does not open a world **never encounters
 * educational content at all**.
 *
 * This page closes that gap without taking a navigation slot. Twelve
 * questions do not justify a top-level destination, and adding
 * "Explainers" beside the four worlds would push the actual product to
 * the side — #45A §D is explicit about this. A destination that
 * *exists* is not the same as one that *occupies navigation*: this is
 * where "All questions →" goes from an explainer, where the homepage's
 * curated questions point onward, and what a sitemap can list.
 *
 * ================================================================
 * QUESTION-LED, AND CURATED
 * ================================================================
 *
 * Grouped by world, in registry order, and each entry is rendered as
 * the QUESTION rather than as a topic label. That is not decoration:
 * the product's strongest educational asset is that its explainers are
 * questions a reader already has, and "The Fed and mortgage rates" is a
 * filing category where "Wait, the Fed doesn't set mortgage rates?" is
 * a reason to click.
 *
 * There is **no recommender here** — no ranking, no popularity, no
 * similarity scoring, no personalisation. Ordering is registry order,
 * and grouping is the curated `worlds` field each explainer already
 * declares. The rabbit hole is a path someone chose to dig.
 *
 * PRERENDERED with real content, like the explainers themselves, so a
 * crawler reads the questions rather than an application shell. No
 * `loader`: everything is in the bundle.
 */

/* oxlint-disable react/only-export-components --
   A React Router FRAMEWORK MODE route module is required by the
   framework to export `meta` beside its component; that is the route
   contract, not an accident of organisation. */
import { Link } from "react-router";

import { IntelligenceShell } from "../components/intelligence/IntelligenceShell";
import { EXPLAINERS, type Explainer } from "../explainers/registry";
import { absoluteUrl } from "../lib/siteUrl";
import { ECONOMIC_WORLDS } from "../worlds/registry";

const SITE_NAME = "MacroChipz";
const TITLE = `Questions about the economy — ${SITE_NAME}`;
const DESCRIPTION =
  "Plain answers to the questions people actually ask about inflation, jobs, interest rates and housing — written and reviewed by MacroChipz, with the live data one click away.";

export function meta() {
  const tags: Array<Record<string, string>> = [
    { title: TITLE },
    { name: "description", content: DESCRIPTION },
    { property: "og:title", content: TITLE },
    { property: "og:description", content: DESCRIPTION },
    { property: "og:type", content: "website" },
    { property: "og:site_name", content: SITE_NAME },
    { name: "twitter:card", content: "summary_large_image" },
    { name: "twitter:title", content: TITLE },
    { name: "twitter:description", content: DESCRIPTION },
  ];

  // Absolute URLs only where the deployment origin is configured --
  // the same rule #40 set. A guessed canonical tells a crawler the real
  // page lives somewhere it does not.
  const url = absoluteUrl("/explain");
  if (url !== null) {
    tags.push({ property: "og:url", content: url });
    tags.push({ tagName: "link", rel: "canonical", href: url });
    const image = absoluteUrl("/og/default.png");
    if (image !== null) {
      tags.push({ property: "og:image", content: image });
      tags.push({ name: "twitter:image", content: image });
    }
  }
  return tags;
}

/**
 * Explainers grouped by the world each one declares.
 *
 * Registry order within a group, registry order between groups. An
 * explainer naming no world would fall through to `unplaced` and be
 * rendered anyway rather than silently dropped — a question that
 * exists but cannot be reached is exactly the defect this page was
 * built to remove, and hiding one here would recreate it.
 */
function grouped(): { label: string; route: string; explainers: Explainer[] }[] {
  const groups = ECONOMIC_WORLDS.map((world) => ({
    label: world.label,
    route: world.route,
    explainers: EXPLAINERS.filter((explainer) => explainer.worlds?.includes(world.id)),
  })).filter((group) => group.explainers.length > 0);

  const placed = new Set(groups.flatMap((group) => group.explainers.map((explainer) => explainer.id)));
  const unplaced = EXPLAINERS.filter((explainer) => !placed.has(explainer.id));
  if (unplaced.length > 0) {
    groups.push({ label: "More questions", route: "", explainers: unplaced });
  }
  return groups;
}

export default function ExplainerIndexRoute() {
  const groups = grouped();

  return (
    <IntelligenceShell>
      <article>
        <p className="type-label text-fg-muted">Understand the economy</p>

        <h1 className="type-page-title mt-2 max-w-3xl">Questions people actually ask</h1>

        <p className="mt-4 max-w-prose text-lg text-fg-secondary">
          Short, plain answers — no economics background needed. Each one is written and reviewed by MacroChipz, and
          each links to the live data behind it.
        </p>

        <div className="mt-10 space-y-10">
          {groups.map((group) => (
            <section key={group.label} aria-labelledby={`group-${group.label.toLowerCase()}`}>
              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                <h2 id={`group-${group.label.toLowerCase()}`} className="type-section-heading">
                  {group.label}
                </h2>
                {group.route !== "" && (
                  <Link
                    to={group.route}
                    className="text-sm font-medium text-fg-secondary underline-offset-4 hover:text-fg hover:underline"
                  >
                    See the {group.label.toLowerCase()} data →
                  </Link>
                )}
              </div>

              <ul className="mt-3 divide-y divide-line-subtle border-t border-line-subtle">
                {group.explainers.map((explainer) => (
                  <li key={explainer.id} className="py-3">
                    <Link
                      to={`/explain/${explainer.slug}`}
                      className="font-medium text-fg underline-offset-4 hover:underline"
                    >
                      {explainer.question}
                    </Link>
                    <p className="mt-1 max-w-prose text-sm text-fg-secondary">{explainer.answer}</p>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>

        <p className="mt-12 border-t border-line pt-6 max-w-prose text-sm text-fg-muted">
          These explain how things work in general. They are not a forecast, and they do not describe any particular
          month — the world pages carry the current figures, with their sources and methodology.
        </p>
      </article>
    </IntelligenceShell>
  );
}
