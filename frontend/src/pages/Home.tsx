import { Link } from "react-router-dom";

import { getInflationMonitor, getInflationWhatChanged } from "../api/inflation";
import { getLaborMonitor, getLaborWhatChanged } from "../api/labor";
import { fetchReleaseProcessingStatus } from "../api/processingStatus";
import { fetchRecentReleases, fetchUpcomingReleases } from "../api/releases";
import { useApiResource } from "../api/useApiResource";
import { useSinceLastVisit } from "../api/useSinceLastVisit";
import { ErrorMessage } from "../components/ErrorMessage";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { CurrentStateSection } from "../components/overview/CurrentStateSection";
import { HowTheyRelate } from "../components/overview/HowTheyRelate";
import { LaborWhatChangedPreview } from "../components/overview/LaborWhatChangedPreview";
import { RecentDataUpdates } from "../components/overview/RecentDataUpdates";
import { RecentReleasePreview } from "../components/overview/RecentReleasePreview";
import { SinceLastVisit } from "../components/overview/SinceLastVisit";
import { UpcomingReleasesPreview } from "../components/overview/UpcomingReleasesPreview";
import { WhatChangedPreview } from "../components/overview/WhatChangedPreview";
import { PageHeader } from "../components/PageHeader";
import { ReleaseScheduleDisclosure } from "../components/releases/ReleaseScheduleDisclosure";

const CHANGES_ERROR_MESSAGE = "What changed could not be loaded.";
const LABOR_CHANGES_ERROR_MESSAGE = "Jobs what changed could not be loaded.";
const PROCESSING_STATUS_ERROR_MESSAGE = "Release-processing status is temporarily unavailable.";
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
export function HomePage() {
  const sinceLastVisit = useSinceLastVisit();
  const monitor = useApiResource(getInflationMonitor);
  const whatChanged = useApiResource(getInflationWhatChanged);
  const laborMonitor = useApiResource(getLaborMonitor);
  const laborWhatChanged = useApiResource(getLaborWhatChanged);
  const processingStatus = useApiResource(fetchReleaseProcessingStatus);
  const upcoming = useApiResource(fetchUpcomingReleases);
  const recent = useApiResource(fetchRecentReleases);

  return (
    <div>
      <PageHeader title="The economy right now" description="Know what changed in the economy — and prove why." />

      <div className="mt-8 divide-y divide-line [&>*]:py-8 [&>*:first-child]:pt-0 [&>*:last-child]:pb-0">
        {/* Since Your Last Check (Increment #25H) -- deliberately first;
            see this page's own docstring for why. */}
        <SinceLastVisit sinceLastVisit={sinceLastVisit} />

        {/* Current State -- Inflation and Labor as independent peers */}
        <CurrentStateSection inflation={monitor} labor={laborMonitor} />

        {/* How They Relate (Increment #23C) -- Relate V1, deterministic
            COMPOSITION only over the same two already-fetched monitor
            resources above; see docs/product/relate-composition-v1.md */}
        <HowTheyRelate inflation={monitor} labor={laborMonitor} />

        {/* What Changed -- same peer structure, one shared heading */}
        <section aria-labelledby="overview-what-changed-heading">
          <h2 id="overview-what-changed-heading" className="text-sm font-medium text-fg-muted">
            What Changed
          </h2>

          <div className="mt-3 space-y-6">
            {whatChanged.status === "loading" && <LoadingSkeleton label="Loading Inflation what changed" heightClassName="h-24" />}
            {whatChanged.status === "error" && <ErrorMessage message={CHANGES_ERROR_MESSAGE} onRetry={whatChanged.reload} />}
            {whatChanged.status === "success" && (
              <WhatChangedPreview
                events={whatChanged.data.changes}
                comparisonAvailable={whatChanged.data.primary_momentum_changes.comparison_available}
              />
            )}

            {laborWhatChanged.status === "loading" && <LoadingSkeleton label="Loading Labor what changed" heightClassName="h-24" />}
            {laborWhatChanged.status === "error" && <ErrorMessage message={LABOR_CHANGES_ERROR_MESSAGE} onRetry={laborWhatChanged.reload} />}
            {laborWhatChanged.status === "success" && (
              <LaborWhatChangedPreview events={laborWhatChanged.data.changes} comparisonAvailable={laborWhatChanged.data.comparison_available} />
            )}
          </div>
        </section>

        {/* Recent Data Updates (renamed/restructured from "Latest Data Detected", Increment #22B) */}
        {processingStatus.status === "loading" && (
          <LoadingSkeleton label="Loading recent data updates" heightClassName="h-32" />
        )}
        {processingStatus.status === "error" && (
          <ErrorMessage message={PROCESSING_STATUS_ERROR_MESSAGE} onRetry={processingStatus.reload} />
        )}
        {processingStatus.status === "success" && <RecentDataUpdates items={processingStatus.data.occurrences} />}

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

          <Link to="/releases" className="mt-3 inline-block text-sm font-medium text-fg-secondary hover:text-fg">
            View release calendar →
          </Link>
        </section>
      </div>
    </div>
  );
}
