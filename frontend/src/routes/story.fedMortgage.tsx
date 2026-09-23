/**
 * THE RATE NETWORK STORY — `/story/fed-and-mortgage-rates` (#46E).
 *
 * ================================================================
 * WHAT THIS IS
 * ================================================================
 *
 * One interactive economic network: six actors, six relationships, and
 * the distinction the whole story turns on — who SETS a number versus
 * what merely INFLUENCES it. Tap a node, read its role, see which
 * connections are its own.
 *
 * It replaces #46C's six-scene article-with-a-quiz at this same URL, per
 * the #46E brief: the central object is a network, not a scrolling
 * article. `RateAuthorityQuiz` and `InfluenceExplorer` are gone and
 * every reviewed sentence they carried now lives in
 * `explainers/rateNetwork.ts`.
 *
 * ================================================================
 * WHAT IS UNCHANGED, AND MUST STAY UNCHANGED
 * ================================================================
 *
 * `/explain/fed-and-mortgage-rates` is untouched: still prerendered,
 * still canonical, still the URL in every inbound link. This route keeps
 * `robots: noindex` and a canonical pointing at it, stays out of
 * navigation and out of the sitemap, and remains deletable in one
 * commit.
 *
 * ================================================================
 * STATE
 * ================================================================
 *
 * One `useState`. Selection is ephemeral view state, not a location: it
 * is deliberately NOT in the URL, because a shareable link whose
 * canonical target is a different page is a trap.
 *
 * It is never null. A diagram that opens with nothing selected opens by
 * explaining nothing, and the prerendered HTML would ship an empty
 * panel — so it opens on the federal funds rate, the node the
 * misconception is actually about.
 *
 * ================================================================
 * NO LIVE DATA, DELIBERATELY
 * ================================================================
 *
 * Not one figure, not one fetch. The route prerenders whole and has
 * nothing that can fail. Constitution §19.1 asks an explainer to bind a
 * claim to a live figure; this satisfies the required movement by
 * LANDING the reader on `/rates` and `/housing` rather than by
 * embedding, which is a narrower reading — recorded in the #46E spec
 * §3.6 rather than quietly assumed.
 */

/* oxlint-disable react/only-export-components --
   A React Router FRAMEWORK MODE route module is required by the
   framework to export `meta` beside its component; that is the route
   contract, not an accident of organisation. */
import { useState } from "react";
import { Link } from "react-router";

import { Disclosure } from "../components/Disclosure";
import { ShareButton } from "../components/ShareButton";
import { IntelligenceShell } from "../components/intelligence/IntelligenceShell";
import { NodePanel } from "../components/story/NodePanel";
import { RateNetwork } from "../components/story/RateNetwork";
import {
  DEFAULT_SELECTED_ID,
  NETWORK_CAVEAT,
  NETWORK_STANDFIRST,
  type NodeId,
} from "../explainers/rateNetwork";
import { explainerById } from "../explainers/registry";
import { absoluteUrl } from "../lib/siteUrl";
import { BASIS_COPY } from "./explainer";

const SITE_NAME = "MacroChipz";
const EXPLAINER_ID = "explain.fed-and-mortgage-rates";
const EXPLAINER_PATH = "/explain/fed-and-mortgage-rates";
const STORY_PATH = "/story/fed-and-mortgage-rates";

/** The one line the story leaves you with. Reviewed copy, compressed. */
const TAKEAWAY = "The one rate the Fed sets is the one you never pay.";


export function meta() {
  const explainer = explainerById(EXPLAINER_ID);
  const title = `${explainer?.question ?? "The Fed and mortgage rates"} — ${SITE_NAME}`;
  const description = explainer?.answer ?? "";

  const tags: Array<Record<string, string>> = [
    { title },
    { name: "description", content: description },
    { property: "og:title", content: title },
    { property: "og:description", content: description },
    { property: "og:type", content: "article" },
    { property: "og:site_name", content: SITE_NAME },
    { name: "twitter:card", content: "summary_large_image" },
    { name: "twitter:title", content: title },
    { name: "twitter:description", content: description },
    // PROTOTYPE ONLY. The canonical URL for this content is the
    // explainer; this route must never compete with it in search, and
    // must never be indexed as a duplicate of it.
    { name: "robots", content: "noindex" },
  ];

  const canonical = absoluteUrl(EXPLAINER_PATH);
  if (canonical !== null) tags.push({ tagName: "link", rel: "canonical", href: canonical });

  return tags;
}

export default function RateNetworkStoryRoute() {
  const explainer = explainerById(EXPLAINER_ID);
  const [selectedId, setSelectedId] = useState<NodeId>(DEFAULT_SELECTED_ID);

  if (!explainer) return null;

  /*
   * The URL the Share button hands over.
   *
   * `absoluteUrl` returns null when no deployment origin is configured,
   * and the old fallback was the bare path — which copies
   * "/story/fed-and-mortgage-rates" into someone's clipboard and is
   * useless when pasted. The honest fallback is the origin the page is
   * ACTUALLY being served from, read at render time in the browser.
   * That is not a fabricated production domain; it is where this page
   * genuinely is.
   *
   * During prerender there is no `window`, and the value is never
   * rendered into the HTML — it is only read inside the click handler —
   * so this cannot cause a hydration mismatch.
   */
  const shareUrl =
    absoluteUrl(STORY_PATH) ??
    (typeof window === "undefined" ? STORY_PATH : `${window.location.origin}${STORY_PATH}`);

  return (
    <IntelligenceShell worldLabel="Rates" worldRoute="/rates" surface="luminous">
      <div>
        {/*
            672px at every width was this page's single biggest defect:
            at 1440px it left 768px of empty field beside a narrow
            column, and the network could never exceed 31% of the
            viewport. The column stays for reading widths and opens up
            at `lg`, where the diagram and its explanation sit side by
            side instead of stacked.
          */}
        <article className="mx-auto max-w-2xl lg:max-w-6xl">
          {/* ---------------- HOOK: two lines, then the network -------- */}
          <header>
            <p className="type-label text-[#a2b0ff]">The living economy</p>
            <h1 className="mt-1.5 text-[28px] font-bold leading-[1.05] tracking-[-0.03em] text-fg text-balance sm:text-4xl">
              {explainer.question}
            </h1>
            {/* One line, not three. The standfirst carries the tap
                affordance rather than a separate hint paragraph beneath
                it — the board grew to fix the chip overlap, and the
                intro is where that height comes from. */}
            <p className="mt-2 max-w-[38ch] text-[14.5px] leading-snug text-fg-secondary">
              {NETWORK_STANDFIRST} <span className="text-fg-muted">Tap any node.</span>
            </p>
          </header>

          {/* ---------------- THE NETWORK ------------------------------ */}
          {/*
            One grid, two behaviours. Below `lg` it is ordinary block
            flow — diagram, legend, panel, caveat — which is exactly the
            order #46E verified at 294 to 440px. At `lg` the same DOM
            becomes two columns: the diagram takes the space it has
            always deserved, and the explanation moves beside it rather
            than 650px down the page.
          */}
          <div className="mt-2 lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(0,25rem)] lg:items-start lg:gap-10">
            <div>
              <RateNetwork selectedId={selectedId} onSelect={setSelectedId} />

              {/* The legend is not decoration: the two `sets` edges at
                  opposite ends with influence between them ARE the story. */}
              <ul className="mt-0.5 flex flex-wrap gap-x-5 gap-y-1 text-[11.5px] text-fg-muted">
                <li className="flex items-center gap-2">
                  <span aria-hidden="true" className="h-0.5 w-5 rounded bg-[#a2b0ff]" />
                  Sets it directly
                </li>
                <li className="flex items-center gap-2">
                  <span
                    aria-hidden="true"
                    className="h-0 w-5 border-t-2 border-dashed border-[rgba(159,172,241,.55)]"
                  />
                  Influences it
                </li>
              </ul>
            </div>

            {/* Sticky, so a reader comparing one node against another on
                a tall screen keeps the explanation in view. */}
            <div className="mt-2.5 lg:sticky lg:top-6 lg:mt-0">
              <NodePanel selectedId={selectedId} />
              <p className="mt-3 max-w-prose text-xs leading-relaxed text-fg-muted">
                {NETWORK_CAVEAT}
              </p>
            </div>
          </div>

          {/* ---------------- TAKEAWAY --------------------------------- */}
          <section className="lx-card mt-5 max-w-3xl rounded-2xl p-4 sm:p-5 lg:mt-8">
            <div
              aria-hidden="true"
              className="h-0.5 w-11 rounded bg-gradient-to-r from-[#a2b0ff] to-[rgba(186,122,240,.2)]"
            />
            <h2 className="mt-3 text-xl font-bold leading-tight tracking-tight text-fg text-balance">
              {TAKEAWAY}
            </h2>
            <p className="mt-2 max-w-prose text-sm leading-relaxed text-fg-secondary">
              {explainer.whatItIs}
            </p>
          </section>

          {/* ---------------- VERIFY ----------------------------------- */}
          <section className="mt-5 max-w-3xl lg:mt-8" aria-labelledby="how-we-know">
            <h2 id="how-we-know" className="type-label text-[#a2b0ff]">
              How we know
            </h2>
            <p className="mt-2 max-w-prose text-sm leading-relaxed text-fg-secondary">
              {BASIS_COPY[explainer.basis]}
            </p>

            <div className="mt-3 max-w-prose">
              <Disclosure summary="The sources behind this" summaryClassName="min-h-11">
                <div className="space-y-3 text-sm text-fg-secondary">
                  <p>
                    <span className="font-medium text-fg">Fannie Mae</span>, <em>What Determines the
                    Rate on a 30-Year Mortgage?</em> — describes the 30-year rate as benchmarked to the
                    10-year Treasury with two spreads layered on: a primary-secondary spread reflecting
                    origination costs, servicing and guaranty fees and lender profit, and a secondary
                    spread compensating investors for prepayment and credit risk.
                  </p>
                  <p>
                    <span className="font-medium text-fg">Federal Reserve Bank of New York</span>, Staff
                    Report 674, <em>Understanding Mortgage Spreads</em> — finds that yield spreads on
                    agency mortgage-backed securities are a key determinant of homeowners&rsquo; funding
                    costs.{" "}
                    <span className="text-fg-muted">
                      A Staff Report is research by its authors and is not a position of the Bank or the
                      Federal Reserve System, so it corroborates rather than establishes.
                    </span>
                  </p>
                  <p>
                    <span className="font-medium text-fg">Consumer Financial Protection Bureau</span> —
                    finds mortgage price dispersion often around 50 basis points of the annual percentage
                    rate across virtually every segment of the market, and that most recent borrowers
                    believed they would pay the same price whichever lender they chose.
                  </p>
                </div>
              </Disclosure>
            </div>

            <div className="mt-2 max-w-prose">
              <Disclosure
                summary={`What this does not tell you (${explainer.limitations?.length ?? 0})`}
                summaryClassName="min-h-11"
              >
                <ul className="list-disc space-y-1 pl-5 text-sm text-fg-secondary">
                  {explainer.limitations?.map((limitation) => <li key={limitation}>{limitation}</li>)}
                </ul>
              </Disclosure>
            </div>
          </section>

          {/* ---------------- CONTINUE --------------------------------- */}
          <section className="mt-6 lg:mt-10" aria-labelledby="keep-going">
            <h2 id="keep-going" className="type-label text-[#a2b0ff]">
              Keep going
            </h2>
            <ul className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              <li>
                <Link
                  to="/rates"
                  className="lx-card flex min-h-14 flex-col justify-center rounded-2xl px-4 py-3 transition-colors hover:border-[rgba(196,204,255,.3)] motion-reduce:transition-none"
                >
                  <span className="text-sm font-semibold text-fg">The Treasury yields we track</span>
                  <span className="mt-0.5 text-xs text-fg-muted">
                    Live figures. MacroChipz does not track mortgage rates.
                  </span>
                </Link>
              </li>
              <li>
                <Link
                  to="/housing"
                  className="lx-card flex min-h-14 flex-col justify-center rounded-2xl px-4 py-3 transition-colors hover:border-[rgba(196,204,255,.3)] motion-reduce:transition-none"
                >
                  <span className="text-sm font-semibold text-fg">How many homes are being built</span>
                  <span className="mt-0.5 text-xs text-fg-muted">Permits, starts and completions.</span>
                </Link>
              </li>
              {explainer.related.map((id) => {
                const next = explainerById(id);
                if (!next) return null;
                return (
                  <li key={id}>
                    <Link
                      to={`/explain/${next.slug}`}
                      className="lx-card flex min-h-14 flex-col justify-center rounded-2xl px-4 py-3 transition-colors hover:border-[rgba(196,204,255,.3)] motion-reduce:transition-none"
                    >
                      <span className="text-sm font-semibold text-fg">{next.question}</span>
                      <span className="mt-0.5 text-xs text-fg-muted">{next.shortTitle}</span>
                    </Link>
                  </li>
                );
              })}
            </ul>

            <div className="mt-5">
              <ShareButton objectType="explainer" title={explainer.question} url={shareUrl} />
            </div>
          </section>

          <p className="mt-8 flex flex-wrap items-center gap-x-1.5 text-xs text-fg-muted lg:mt-12">
            <span>Prototype (#46F). The canonical version lives at</span>
            <Link
              to={EXPLAINER_PATH}
              className="inline-flex min-h-11 items-center underline underline-offset-4 hover:text-fg"
            >
              {EXPLAINER_PATH}
            </Link>
          </p>
        </article>
      </div>
    </IntelligenceShell>
  );
}
