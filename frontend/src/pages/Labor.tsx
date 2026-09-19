import { getEmploymentSituationProcessingStatus, getLaborMonitor, getLaborStateDuration, getLaborWhatChanged } from "../api/labor";
import { fetchRecentReleases, fetchUpcomingReleases } from "../api/releases";
import { useApiResource } from "../api/useApiResource";
import { ErrorMessage } from "../components/ErrorMessage";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { DataBasisNote } from "../components/inflation/DataBasisNote";
import { EmploymentSection } from "../components/labor/EmploymentSection";
import { LaborHero } from "../components/labor/LaborHero";
import { LatestDataDetected } from "../components/labor/LatestDataDetected";
import { MethodologyDisclosure } from "../components/labor/MethodologyDisclosure";
import { RelevantRelease } from "../components/labor/RelevantRelease";
import { UnemploymentSection } from "../components/labor/UnemploymentSection";
import { WhatChangedSection } from "../components/labor/WhatChangedSection";
import { PageHeader } from "../components/PageHeader";

const MONITOR_ERROR_MESSAGE = "Labor data could not be loaded.";
const CHANGES_ERROR_MESSAGE = "What changed could not be loaded.";
const PROCESSING_STATUS_ERROR_MESSAGE = "Release-processing status is temporarily unavailable.";
const UPCOMING_ERROR_MESSAGE = "Upcoming releases could not be loaded.";
const RECENT_ERROR_MESSAGE = "Recent releases could not be loaded.";

/**
 * The Labor Market Monitor product page (Increment #20E.2). Loads
 * `GET /api/v1/monitors/labor`, `GET /api/v1/monitors/labor/changes`,
 * `GET /api/v1/monitors/labor/state-duration` (Increment #24D),
 * Upcoming/Recent releases, and Employment Situation's own scoped
 * processing-status evidence -- six completely independent resources
 * (see useApiResource), each with its own loading/error UI; one
 * failing never blanks, blocks, or fabricates any other section, the
 * same discipline /inflation and / already establish. `stateDuration`
 * is fetched here (the page), not inside `LaborHero`, matching this
 * page's own established "page owns every resource, components stay
 * dumb" convention -- one clear owner per resource.
 *
 * Frozen 7-section hierarchy (docs/architecture/labor-ui-v1.md §7):
 * Current State -> Employment -> Unemployment -> What Changed ->
 * Latest Data Detected -> Relevant Release -> Evidence & methodology.
 * State Duration V1 is a new line inside the existing Current State
 * (Hero) section, not an eighth section (frozen contract
 * docs/product/state-duration-v1.md §40). Every economic value, state,
 * and relationship rendered below is exactly what those endpoints
 * returned; this page composes and formats, it does not calculate.
 */
export function LaborPage() {
  const monitor = useApiResource(getLaborMonitor);
  const whatChanged = useApiResource(getLaborWhatChanged);
  const stateDuration = useApiResource(getLaborStateDuration);
  const processingStatus = useApiResource(getEmploymentSituationProcessingStatus);
  const upcoming = useApiResource(fetchUpcomingReleases);
  const recent = useApiResource(fetchRecentReleases);

  return (
    <div>
      <PageHeader
        title="Labor"
        description="Track U.S. labor market conditions -- payroll employment, the unemployment trend, and the evidence behind each conclusion."
      >
        <DataBasisNote />
      </PageHeader>

      <div className="mt-8 divide-y divide-line [&>*]:py-8 [&>*:first-child]:pt-0 [&>*:last-child]:pb-0">
        {/* 1. Current State */}
        {monitor.status === "loading" && <LoadingSkeleton label="Loading current state" heightClassName="h-32" />}
        {monitor.status === "error" && <ErrorMessage message={MONITOR_ERROR_MESSAGE} onRetry={monitor.reload} />}
        {monitor.status === "success" && <LaborHero result={monitor.data} stateDuration={stateDuration} />}

        {/* 2-3. Employment, Unemployment -- both sub-views of the monitor resource */}
        {monitor.status === "success" && (
          <>
            <EmploymentSection employment={monitor.data.employment} methodologyId={monitor.data.methodology_id} dataBasis={monitor.data.data_basis} />
            <UnemploymentSection unemployment={monitor.data.unemployment} methodologyId={monitor.data.methodology_id} dataBasis={monitor.data.data_basis} />
          </>
        )}

        {/* 4. What Changed */}
        {whatChanged.status === "loading" && <LoadingSkeleton label="Loading what changed" heightClassName="h-48" />}
        {whatChanged.status === "error" && <ErrorMessage message={CHANGES_ERROR_MESSAGE} onRetry={whatChanged.reload} />}
        {whatChanged.status === "success" && <WhatChangedSection whatChanged={whatChanged.data} />}

        {/* 5. Latest Data Detected */}
        {processingStatus.status === "loading" && (
          <LoadingSkeleton label="Loading latest data detected" heightClassName="h-32" />
        )}
        {processingStatus.status === "error" && (
          <ErrorMessage message={PROCESSING_STATUS_ERROR_MESSAGE} onRetry={processingStatus.reload} />
        )}
        {processingStatus.status === "success" && <LatestDataDetected items={processingStatus.data.occurrences} />}

        {/* 6. Relevant Release -- upcoming/recent load and fail independently;
            RelevantRelease itself shows whichever side is available. */}
        <div>
          {upcoming.status === "loading" && <LoadingSkeleton label="Loading upcoming releases" heightClassName="h-24" />}
          {upcoming.status === "error" && <ErrorMessage message={UPCOMING_ERROR_MESSAGE} onRetry={upcoming.reload} />}

          {recent.status === "loading" && <LoadingSkeleton label="Loading recent releases" heightClassName="h-8" />}
          {recent.status === "error" && <ErrorMessage message={RECENT_ERROR_MESSAGE} onRetry={recent.reload} />}

          <RelevantRelease
            upcoming={upcoming.status === "success" ? upcoming.data.releases : null}
            recent={recent.status === "success" ? recent.data.releases : null}
          />
        </div>

        {/* 7. Evidence & methodology */}
        {(monitor.status === "success" || whatChanged.status === "success") && (
          <MethodologyDisclosure
            monitor={monitor.status === "success" ? monitor.data : null}
            whatChanged={whatChanged.status === "success" ? whatChanged.data : null}
          />
        )}
      </div>
    </div>
  );
}
