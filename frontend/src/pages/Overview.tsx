import { Link } from "react-router-dom";

import { getInflationMonitor, getInflationWhatChanged } from "../api/inflation";
import { getLaborMonitor, getLaborWhatChanged } from "../api/labor";
import { fetchReleaseProcessingStatus } from "../api/processingStatus";
import { fetchRecentReleases, fetchUpcomingReleases } from "../api/releases";
import { useApiResource } from "../api/useApiResource";
import { ErrorMessage } from "../components/ErrorMessage";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { CurrentStateSection } from "../components/overview/CurrentStateSection";
import { LaborWhatChangedPreview } from "../components/overview/LaborWhatChangedPreview";
import { LatestDataDetected } from "../components/overview/LatestDataDetected";
import { RecentReleasePreview } from "../components/overview/RecentReleasePreview";
import { UpcomingReleasesPreview } from "../components/overview/UpcomingReleasesPreview";
import { WhatChangedPreview } from "../components/overview/WhatChangedPreview";
import { ReleaseScheduleDisclosure } from "../components/releases/ReleaseScheduleDisclosure";

const CHANGES_ERROR_MESSAGE = "What changed could not be loaded.";
const LABOR_CHANGES_ERROR_MESSAGE = "Labor what changed could not be loaded.";
const PROCESSING_STATUS_ERROR_MESSAGE = "Release-processing status is temporarily unavailable.";
const UPCOMING_ERROR_MESSAGE = "Upcoming releases could not be loaded.";
const RECENT_ERROR_MESSAGE = "Recent releases could not be loaded.";

/**
 * The Economic Overview -- the real `/` product page (Increment #19A),
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
 * Hierarchy: Current State -> What Changed -> Latest Data Detected ->
 * Releases. Inflation and Labor are peers within Current State and
 * What Changed -- never subordinate to one another, and never combined
 * into an aggregate "Economy State"/score (docs/architecture/labor-ui-v1.md
 * §29/§30's own absolute prohibition). Latest Data Detected and
 * Releases remain the SAME generic, already-multi-domain-capable
 * sections #19C/#17B built -- no Labor-specific logic was added to
 * either; Employment Situation's own evidence already flows through
 * them once the generic component-typing fix lands (see
 * components/overview/LatestDataDetected.tsx, lib/detectedChangeFormat.ts).
 * This page composes and formats only -- it never recalculates a
 * metric, reclassifies a state, derives economic significance, ranks
 * importance, or infers publication/data availability.
 */
export function OverviewPage() {
  const monitor = useApiResource(getInflationMonitor);
  const whatChanged = useApiResource(getInflationWhatChanged);
  const laborMonitor = useApiResource(getLaborMonitor);
  const laborWhatChanged = useApiResource(getLaborWhatChanged);
  const processingStatus = useApiResource(fetchReleaseProcessingStatus);
  const upcoming = useApiResource(fetchUpcomingReleases);
  const recent = useApiResource(fetchRecentReleases);

  return (
    <div className="max-w-3xl">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-neutral-900">Economic Overview</h1>
        <p className="mt-2 max-w-prose text-neutral-600">Know what changed in the economy — and prove why.</p>
      </header>

      <div className="mt-8 divide-y divide-neutral-200 [&>*]:pt-8 [&>*:first-child]:pt-0">
        {/* Current State -- Inflation and Labor as independent peers */}
        <CurrentStateSection inflation={monitor} labor={laborMonitor} />

        {/* What Changed -- same peer structure, one shared heading */}
        <section aria-labelledby="overview-what-changed-heading">
          <h2 id="overview-what-changed-heading" className="text-sm font-medium text-neutral-500">
            What Changed
          </h2>

          <div className="mt-3 space-y-6">
            {whatChanged.status === "loading" && <LoadingSkeleton label="Loading Inflation what changed" heightClassName="h-24" />}
            {whatChanged.status === "error" && <ErrorMessage message={CHANGES_ERROR_MESSAGE} onRetry={whatChanged.reload} />}
            {whatChanged.status === "success" && <WhatChangedPreview events={whatChanged.data.changes} />}

            {laborWhatChanged.status === "loading" && <LoadingSkeleton label="Loading Labor what changed" heightClassName="h-24" />}
            {laborWhatChanged.status === "error" && <ErrorMessage message={LABOR_CHANGES_ERROR_MESSAGE} onRetry={laborWhatChanged.reload} />}
            {laborWhatChanged.status === "success" && <LaborWhatChangedPreview events={laborWhatChanged.data.changes} />}
          </div>
        </section>

        {/* Latest Data Detected */}
        {processingStatus.status === "loading" && (
          <LoadingSkeleton label="Loading latest data detected" heightClassName="h-32" />
        )}
        {processingStatus.status === "error" && (
          <ErrorMessage message={PROCESSING_STATUS_ERROR_MESSAGE} onRetry={processingStatus.reload} />
        )}
        {processingStatus.status === "success" && <LatestDataDetected items={processingStatus.data.occurrences} />}

        {/* Releases -- one section, two independently-loading parts */}
        <section aria-labelledby="overview-releases-heading">
          <h2 id="overview-releases-heading" className="text-sm font-medium text-neutral-500">
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

          <Link to="/releases" className="mt-3 inline-block text-sm font-medium text-neutral-700 hover:text-neutral-900">
            View release calendar →
          </Link>
        </section>
      </div>
    </div>
  );
}
