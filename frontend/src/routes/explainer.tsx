/**
 * A permanent explainer page (Increment #44).
 *
 * A framework route, PRERENDERED for every slug. Explainers are finite
 * and code-defined, so unlike dynamic intelligence objects there is no
 * build-time data coupling at all — the content is in the bundle. That
 * makes them the one part of MacroChipz whose *substance* a crawler
 * can read without executing JavaScript, which is exactly what a page
 * meant to be found by search or opened from a short video needs.
 *
 * No `loader`. The content is static, so there is nothing to load and
 * none of #40A's `ssr: false` export constraints apply.
 *
 * WRITTEN FOR SOMEONE WITH NO CONTEXT. A visitor arriving from a
 * 30-second video gets the question and the one-sentence answer before
 * anything else — no branding preamble, no methodology, no scrolling
 * to reach the point.
 */

/* oxlint-disable react/only-export-components --
   A React Router FRAMEWORK MODE route module is required by the
   framework to export `meta` and `ErrorBoundary` beside its component;
   that is the route contract, not an accident of organisation. */
import { Link, useParams } from "react-router";

import { Card } from "../components/Card";
import { Disclosure } from "../components/Disclosure";
import { InfluenceDiagram } from "../components/explainers/InfluenceDiagram";
import { IntelligenceShell } from "../components/intelligence/IntelligenceShell";
import { EXPLAINERS, explainerById, explainerBySlug, type Explainer } from "../explainers/registry";
import { absoluteUrl } from "../lib/siteUrl";
import { ECONOMIC_WORLDS, world as worldById } from "../worlds/registry";

const SITE_NAME = "MacroChipz";

/** The basis line, in words a reader can weigh. */
const BASIS_COPY: Readonly<Record<Explainer["basis"], string>> = {
  GENERAL_ECONOMICS:
    "This is general economics — the kind of definition a reference work would give. MacroChipz wrote and reviewed this explanation; it is not a claim about any particular month.",
  MACROCHIPZ_METHODOLOGY:
    "This describes how MacroChipz's own published methodology treats these measures. The behaviour described here is what the engine actually does.",
  INSTITUTIONAL_ROLE:
    "This describes the published role of named institutions and how markets price long-term borrowing in general. MacroChipz wrote and reviewed this explanation.",
};

export function meta({ params }: { params: { slug?: string } }) {
  const explainer = params.slug ? explainerBySlug(params.slug) : undefined;

  if (!explainer) {
    return [
      { title: `Not found — ${SITE_NAME}` },
      { name: "description", content: "No MacroChipz explainer exists at this address." },
      { name: "robots", content: "noindex" },
    ];
  }

  const title = `${explainer.question} — ${SITE_NAME}`;
  const tags: Array<Record<string, string>> = [
    { title },
    { name: "description", content: explainer.answer },
    { property: "og:title", content: explainer.question },
    { property: "og:description", content: explainer.answer },
    { property: "og:type", content: "article" },
    { property: "og:site_name", content: SITE_NAME },
    { name: "twitter:card", content: "summary_large_image" },
    { name: "twitter:title", content: explainer.question },
    { name: "twitter:description", content: explainer.answer },
  ];

  const url = absoluteUrl(`/explain/${explainer.slug}`);
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

export default function ExplainerRoute() {
  const { slug } = useParams();
  const explainer = slug ? explainerBySlug(slug) : undefined;

  if (!explainer) return <NotFound />;

  const homeWorld = explainer.worlds?.[0] ? worldById(explainer.worlds[0]) : undefined;

  return (
    <IntelligenceShell worldLabel={homeWorld?.label} worldRoute={homeWorld?.route}>
      <article className="py-8">
        {/* THE ANSWER FIRST. Everything below is elaboration. */}
        <header>
          <p className="type-label text-fg-muted">Wait, seriously?</p>
          <h1 className="type-page-title mt-2 max-w-3xl">{explainer.question}</h1>
          <p className="mt-4 max-w-prose text-lg text-fg-secondary">{explainer.answer}</p>
        </header>

        {explainer.id === "explain.fed-and-mortgage-rates" && (
          <div className="mt-8 max-w-3xl">
            <InfluenceDiagram />
          </div>
        )}

        <section aria-labelledby="what-heading" className="mt-10">
          <h2 id="what-heading" className="type-section-heading">
            What it actually is
          </h2>
          <p className="mt-2 max-w-prose text-fg-secondary">{explainer.whatItIs}</p>
        </section>

        {explainer.howItWorks && explainer.howItWorks.length > 0 && (
          <section aria-labelledby="how-heading" className="mt-8">
            <h2 id="how-heading" className="type-section-heading">
              How it works
            </h2>
            <ul className="mt-2 max-w-prose list-disc space-y-2 pl-5 text-fg-secondary">
              {explainer.howItWorks.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ul>
          </section>
        )}

        {explainer.misconception && (
          <section aria-labelledby="misconception-heading" className="mt-8">
            <h2 id="misconception-heading" className="type-section-heading">
              What people get wrong
            </h2>
            <p className="mt-2 max-w-prose text-fg-secondary">{explainer.misconception}</p>
          </section>
        )}

        {explainer.whatThisMeansForYou && (
          <Card as="article" className="mt-8 max-w-prose">
            <h2 className="type-section-heading">What this means for you</h2>
            <p className="mt-2 text-sm text-fg-secondary">{explainer.whatThisMeansForYou}</p>
          </Card>
        )}

        {explainer.worlds && explainer.worlds.length > 0 && (
          <section aria-labelledby="watching-heading" className="mt-10">
            <h2 id="watching-heading" className="type-section-heading">
              What MacroChipz is watching
            </h2>
            <p className="mt-2 max-w-prose text-sm text-fg-secondary">
              MacroChipz tracks this part of the economy with published data and a versioned methodology. The
              explanation above is general; the numbers are live.
            </p>
            <ul className="mt-3 flex flex-wrap gap-x-6 gap-y-2">
              {explainer.worlds.map((id) => {
                const entry = ECONOMIC_WORLDS.find((candidate) => candidate.id === id);
                if (!entry) return null;
                return (
                  <li key={id}>
                    <Link
                      to={entry.route}
                      className="text-sm font-medium text-fg-secondary underline-offset-4 hover:text-fg hover:underline"
                    >
                      Explore {entry.label} →
                    </Link>
                  </li>
                );
              })}
            </ul>
          </section>
        )}

        <ExploreNext explainer={explainer} />

        <section aria-labelledby="basis-heading" className="mt-10 border-t border-line pt-6">
          <h2 id="basis-heading" className="type-section-heading">
            How we know
          </h2>
          <p className="mt-2 max-w-prose text-sm text-fg-secondary">{BASIS_COPY[explainer.basis]}</p>

          {explainer.limitations && explainer.limitations.length > 0 && (
            <div className="mt-3">
              <Disclosure summary={`What this does not tell you (${explainer.limitations.length})`}>
                <ul className="list-disc space-y-1 pl-5 text-sm text-fg-secondary">
                  {explainer.limitations.map((limitation) => (
                    <li key={limitation}>{limitation}</li>
                  ))}
                </ul>
              </Disclosure>
            </div>
          )}
        </section>
      </article>
    </IntelligenceShell>
  );
}

/**
 * The rabbit hole. Curated ids, resolved deterministically — no
 * recommender, no ranking, no personalisation, and kept small so it
 * stays a choice rather than a feed.
 */
function ExploreNext({ explainer }: { explainer: Explainer }) {
  const related = explainer.related
    .map((id) => explainerById(id))
    .filter((candidate): candidate is Explainer => candidate !== undefined);

  if (related.length === 0) return null;

  return (
    <section aria-labelledby="explore-heading" className="mt-10">
      <h2 id="explore-heading" className="type-section-heading">
        Explore next
      </h2>
      <ul className="mt-3 grid gap-3 sm:grid-cols-2">
        {related.map((next) => (
          <li key={next.id}>
            <Link
              to={`/explain/${next.slug}`}
              className="block rounded-lg border border-line bg-surface p-4 hover:border-line-strong"
            >
              <p className="text-sm font-medium text-fg">{next.question}</p>
              <p className="mt-1 text-sm text-fg-secondary">{next.shortTitle}</p>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

function NotFound() {
  return (
    <IntelligenceShell>
      <div className="py-16">
        <h1 className="type-page-title">No explainer here</h1>
        <p className="mt-3 max-w-prose text-fg-secondary">
          MacroChipz has nothing written at this address. The link may be mistyped.
        </p>
        <ul className="mt-6 space-y-2">
          {EXPLAINERS.slice(0, 4).map((explainer) => (
            <li key={explainer.id}>
              <Link
                to={`/explain/${explainer.slug}`}
                className="text-sm font-medium text-fg-secondary underline-offset-4 hover:text-fg hover:underline"
              >
                {explainer.question}
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </IntelligenceShell>
  );
}
