import { Link } from "react-router-dom";

import { getHousing } from "../api/housing";
import { getInflationMonitor } from "../api/inflation";
import { getLaborMonitor } from "../api/labor";
import { listHomepageIntelligence } from "../api/intelligence";
import { fetchRecentReleases, fetchUpcomingReleases } from "../api/releases";
import { useApiResource } from "../api/useApiResource";
import { ErrorMessage } from "../components/ErrorMessage";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { CurrentStateSection } from "../components/overview/CurrentStateSection";
import { HowTheyRelate } from "../components/overview/HowTheyRelate";
import { RecentReleasePreview } from "../components/overview/RecentReleasePreview";
import { UpcomingReleasesPreview } from "../components/overview/UpcomingReleasesPreview";
import { PageHeader } from "../components/PageHeader";
import { HomeQuestions } from "../components/homepage/HomeQuestions";
import { RecentIntelligence } from "../components/homepage/RecentIntelligence";
import { TheLede } from "../components/homepage/TheLede";
import { WorldOrientation } from "../components/homepage/WorldOrientation";
import { RevisionsLink } from "../components/revisions/RevisionsLink";
import { selectHomepage } from "../homepage/presentationPolicy";
import { ReleaseScheduleDisclosure } from "../components/releases/ReleaseScheduleDisclosure";

const UPCOMING_ERROR_MESSAGE = "Upcoming releases could not be loaded.";
const RECENT_ERROR_MESSAGE = "Recent releases could not be loaded.";

/**
 * MacroChipz Home -- the live economic surface (Increment #19A as
 * Overview; moved to its canonical `/` route in #41),
 * extended in #20E.2 to be genuinely multi-domain. Composes SEVEN
 * independent canonical read endpoints
 * (`getInflationMonitor`/`getInflationWhatChanged`/`getLaborMonitor`/
 * `getLaborWhatChanged`/`fetchReleaseProcessingStatus`/
 * `fetchUpcomingReleases`/`fetchRecentReleases`), each loaded via its
 * own independent `useApiResource` call. There is no aggregate
 * `GET /api/v1/overview` endpoint and no `Promise.all`: one resource
 * failing never blanks, blocks, or fabricates any other section (see
 * docs/ENGINEERING_JOURNAL.md's #19A entry for why an aggregate
 * endpoint was deliberately not built) -- Inflation's monitor failing
 * never hides Labor's card, and vice versa, at every section
 * (docs/architecture/labor-ui-v1.md §33/§38).
 *
 * Hierarchy: Since Your Last Check -> Current State -> How They Relate
 * -> What Changed -> Recent Data Updates -> Releases. "Since Your Last
 * Check" (Increment #25H, frozen by docs/product/since-last-visit-v1.md)
 * is deliberately FIRST -- a returning-user orientation layer over a
 * dedicated, already-categorized backend recap
 * (`GET /api/v1/since-last-visit`, #25G) plus a local, server-watermark-
 * driven checkpoint (`useSinceLastVisit`, `lib/sinceLastVisitCheckpoint.ts`)
 * -- this page never re-derives a transition, a coverage state, or an
 * evaluation period from raw data; it renders the backend's own
 * already-categorized response verbatim (contract §63). "How They
 * Relate" (Increment #23C,
 * frozen by docs/product/relate-composition-v1.md) renders exactly one
 * deterministic COMPOSITION sentence over Inflation's and Labor's own
 * already-canonical states -- never a new economic conclusion, never
 * an aggregate score, never a regime label; see
 * components/overview/HowTheyRelate.tsx and lib/relateComposition.ts.
 * Inflation and Labor are peers within Current State, How They Relate,
 * What Changed, AND (Increment #22B) Recent Data Updates -- never
 * subordinate to one another, and never combined into an aggregate
 * "Economy State"/score (docs/architecture/labor-ui-v1.md §29/§30's own
 * absolute prohibition, restated and extended by
 * docs/product/overview-attention-model-v1.md and
 * docs/product/relate-composition-v1.md). What Changed
 * (Increment #22B) renders a deterministic 4-tier PRESENTATION
 * salience over each domain's own already-canonical `changes[]`
 * (lib/inflationSalience.ts/lib/laborSalience.ts) instead of a flat
 * truncation -- never a score, never a magnitude ranking, never new
 * economic semantics; see docs/product/overview-attention-model-v1.md
 * for the frozen contract. Recent Data Updates (renamed from "Latest
 * Data Detected", #19C) is restructured to one slot per canonical
 * monitor domain (components/overview/RecentDataUpdates.tsx), keyed by
 * `lib/releaseMonitorRelation.ts`'s migration-verified
 * `CANONICAL_MONITOR_RELEASE_IDS` -- never the broader, unrelated
 * `releaseCategory()` display tag. This page composes and formats
 * only -- it never recalculates a metric, reclassifies a state,
 * derives economic significance, ranks importance, or infers
 * publication/data availability.
 */
/**
 * LEGACY CHANGE SURFACES WERE REMOVED FROM THIS PAGE IN #42A.
 *
 * Three sections used to sit below THE LEDE and were removed from the
 * HOMEPAGE COMPOSITION ONLY -- not redesigned, not deleted, and their
 * components remain in the tree:
 *
 * - **Since Your Last Check** recapped whatever the backend had
 *   detected, which locally means coverage events: "Core CPI became
 *   available for July 2026".
 * - **What Changed** (`WhatChangedPreview` / `LaborWhatChangedPreview`)
 *   renders `AVAILABILITY_LOST` / `AVAILABILITY_RESTORED` rows as
 *   changes, and prints a null value as the bare word "Unavailable".
 * - **Recent Data Updates** (`RecentDataUpdates` -> the overview
 *   `LatestDataDetected`) rendered "Tracked analysis changes" as
 *   `previous -> current`, which on this data reads
 *   `Unavailable -> 3.353016322755642`.
 *
 * Each is incompatible with what #42 decided a consumer homepage may
 * show: 1,488 of the 1,899 local intelligence objects are COVERAGE,
 * and all 44 "ECONOMIC" analysis changes are `UNAVAILABLE -> x` first
 * computations. `homepage_presentation_v1.0` excludes exactly that
 * class of event from THE LEDE; leaving the same events rendered
 * unfiltered two sections lower would have made the policy decorative.
 *
 * Nothing replaced them. #43 owns the Revision Intelligence experience
 * that should, and these components are the raw material it will reuse
 * or retire deliberately. `components/labor/LatestDataDetected.tsx` is
 * a DIFFERENT component and is untouched -- the Jobs page still uses it.
 */
export function HomePage() {
  const monitor = useApiResource(getInflationMonitor);
  const laborMonitor = useApiResource(getLaborMonitor);
  const upcoming = useApiResource(fetchUpcomingReleases);
  const recent = useApiResource(fetchRecentReleases);
  // ONE request for the homepage's own selection (#42). The list
  // endpoint is bounded and paged; the page does not walk the
  // intelligence history to show a handful of things.
  const intelligence = useApiResource(listHomepageIntelligence);
  // #45B: one additional INDEPENDENT resource, for the world
  // orientation section's Housing line only. Failure-isolated like
  // every other resource on this page -- a Housing outage removes one
  // line of metadata and touches nothing else.
  const housing = useApiResource(getHousing);

  // THE LEDE is chosen by `homepage_presentation_v1.0` -- a
  // deterministic PRESENTATION policy, never a claim about economic
  // importance. A failed or pending request renders the QUIET state,
  // which is a valid product state rather than an error.
  const selection = selectHomepage(intelligence.status === "success" ? intelligence.data.items : []);

  return (
    <div>
      <PageHeader title="The economy right now" description="Know what changed in the economy — and prove why." />

      <div className="mt-8 divide-y divide-line [&>*]:py-8 [&>*:first-child]:pt-0 [&>*:last-child]:pb-0">
        <TheLede object={selection.lede} status={intelligence.status === "success" ? "resolved" : "unknown"} />

        <RecentIntelligence objects={selection.whatChanged} />

        {/* ORIENTATION (#45B). A DIFFERENT CLAIM from THE LEDE's: the
            lede says "this changed" under `homepage_presentation_v1.0`;
            this says "these exist, and here is the latest data on
            file". #45A found the homepage could only ever show Treasury
            yields, because 6 of 1,899 objects are eligible and all six
            are rates. The eligibility policy is correct and untouched;
            what was missing was a second, clearly separated layer. */}
        <WorldOrientation
          inflation={monitor}
          labor={laborMonitor}
          housing={housing}
          intelligence={intelligence.status === "success" ? intelligence.data.items : []}
        />

        {/* Curated educational entry points (#45B). Fixes the weakest
            stage of the loop -- #45A found the surprising questions
            MacroChipz has written were unreachable from the entrance. */}
        <HomeQuestions />

        {/* Current State -- Inflation and Labor as independent peers */}
        <CurrentStateSection inflation={monitor} labor={laborMonitor} />

        {/* How They Relate (Increment #23C) -- Relate V1, deterministic
            COMPOSITION only over the same two already-fetched monitor
            resources above; see docs/product/relate-composition-v1.md */}
        <HowTheyRelate inflation={monitor} labor={laborMonitor} />

        {/* Releases -- one section, two independently-loading parts */}
        <section aria-labelledby="overview-releases-heading">
          <h2 id="overview-releases-heading" className="text-sm font-medium text-fg-muted">
            Releases
          </h2>

          {upcoming.status === "loading" && <LoadingSkeleton label="Loading upcoming releases" heightClassName="h-24" />}
          {upcoming.status === "error" && <ErrorMessage message={UPCOMING_ERROR_MESSAGE} onRetry={upcoming.reload} />}
          {upcoming.status === "success" && <UpcomingReleasesPreview releases={upcoming.data.releases} />}

          {recent.status === "loading" && <LoadingSkeleton label="Loading recent releases" heightClassName="h-8" />}
          {recent.status === "error" && <ErrorMessage message={RECENT_ERROR_MESSAGE} onRetry={recent.reload} />}
          {recent.status === "success" && <RecentReleasePreview releases={recent.data.releases} />}

          <div className="mt-4">
            <ReleaseScheduleDisclosure />
          </div>

          <Link to="/calendar" className="mt-3 inline-block text-sm font-medium text-fg-secondary hover:text-fg">
            View release calendar →
          </Link>
        </section>

        {/* Revision Intelligence (#45B). #45A measured exactly two
            inbound links to `/revisions`, neither from here. The copy
            is forward-looking by design -- see RevisionsLink. */}
        <RevisionsLink />
      </div>
    </div>
  );
}
