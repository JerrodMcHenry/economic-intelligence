import { Link } from "react-router-dom";

import { getInflationMonitor, getInflationWhatChanged } from "../api/inflation";
import { fetchRecentReleases, fetchUpcomingReleases } from "../api/releases";
import { useApiResource } from "../api/useApiResource";
import { ErrorMessage } from "../components/ErrorMessage";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { CurrentStateSection } from "../components/overview/CurrentStateSection";
import { RecentReleasePreview } from "../components/overview/RecentReleasePreview";
import { UpcomingReleasesPreview } from "../components/overview/UpcomingReleasesPreview";
import { WhatChangedPreview } from "../components/overview/WhatChangedPreview";
import { ReleaseScheduleDisclosure } from "../components/releases/ReleaseScheduleDisclosure";

const MONITOR_ERROR_MESSAGE = "Inflation data could not be loaded.";
const CHANGES_ERROR_MESSAGE = "What changed could not be loaded.";
const UPCOMING_ERROR_MESSAGE = "Upcoming releases could not be loaded.";
const RECENT_ERROR_MESSAGE = "Recent releases could not be loaded.";

/**
 * The Economic Overview -- the real `/` product page (Increment #19A),
 * replacing the Increment #16A placeholder. Composes exactly four
 * EXISTING, unmodified canonical read endpoints
 * (`getInflationMonitor`/`getInflationWhatChanged`/
 * `fetchUpcomingReleases`/`fetchRecentReleases`), each loaded via its
 * own independent `useApiResource` call -- the same pattern `/inflation`
 * already uses for two resources, extended here to four. There is no
 * aggregate `GET /api/v1/overview` endpoint and no `Promise.all`: one
 * resource failing never blanks, blocks, or fabricates any other
 * section (see docs/ENGINEERING_JOURNAL.md's #19A entry for why an
 * aggregate endpoint was deliberately not built).
 *
 * Hierarchy: Current State -> What Changed -> Releases. This page
 * composes and formats only -- it never recalculates a metric,
 * reclassifies a state, derives economic significance, ranks
 * importance, or infers publication/data availability. Increment #18's
 * release-driven detected-change/analytical-consequence evidence is
 * deliberately NOT surfaced here -- that is #19B/#19C's job, once a
 * read-only endpoint for it exists (none does today).
 */
export function OverviewPage() {
  const monitor = useApiResource(getInflationMonitor);
  const whatChanged = useApiResource(getInflationWhatChanged);
  const upcoming = useApiResource(fetchUpcomingReleases);
  const recent = useApiResource(fetchRecentReleases);

  return (
    <div className="max-w-3xl">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-neutral-900">Economic Overview</h1>
        <p className="mt-2 max-w-prose text-neutral-600">Know what changed in the economy — and prove why.</p>
      </header>

      <div className="mt-8 divide-y divide-neutral-200 [&>*]:pt-8 [&>*:first-child]:pt-0">
        {/* Current State */}
        {monitor.status === "loading" && <LoadingSkeleton label="Loading current state" heightClassName="h-32" />}
        {monitor.status === "error" && <ErrorMessage message={MONITOR_ERROR_MESSAGE} onRetry={monitor.reload} />}
        {monitor.status === "success" && <CurrentStateSection momentum={monitor.data.underlying_momentum} />}

        {/* What Changed */}
        {whatChanged.status === "loading" && <LoadingSkeleton label="Loading what changed" heightClassName="h-24" />}
        {whatChanged.status === "error" && <ErrorMessage message={CHANGES_ERROR_MESSAGE} onRetry={whatChanged.reload} />}
        {whatChanged.status === "success" && <WhatChangedPreview events={whatChanged.data.changes} />}

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
