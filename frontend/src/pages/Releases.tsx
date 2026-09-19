import { fetchRecentReleases, fetchUpcomingReleases } from "../api/releases";
import { useApiResource } from "../api/useApiResource";
import { ErrorMessage } from "../components/ErrorMessage";
import { ExplanationTrigger } from "../components/explanations/ExplanationTrigger";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { PageHeader } from "../components/PageHeader";
import { ReleaseCalendarSection } from "../components/releases/ReleaseCalendarSection";
import { ReleaseScheduleDisclosure } from "../components/releases/ReleaseScheduleDisclosure";
import { ECONOMIC_RELEASE } from "../content/explanations/releases";

const UPCOMING_ERROR_MESSAGE = "Upcoming releases could not be loaded.";
const RECENT_ERROR_MESSAGE = "Recent releases could not be loaded.";

/**
 * The release calendar product page. Loads Upcoming and Recent
 * independently (see useApiResource) -- one failing never blanks or
 * fabricates the other, the same partial-failure resilience already
 * established on /inflation. Every date and `schedule_status` rendered
 * below is exactly what `GET /api/v1/releases` returned; this page
 * composes and formats, it never classifies. GET only -- nothing here,
 * anywhere in its import graph, calls the release calendar's explicit
 * sync write path (see frontend/src/test/no-release-sync-or-coupling.test.ts).
 */
export function ReleasesPage() {
  const upcoming = useApiResource(fetchUpcomingReleases);
  const recent = useApiResource(fetchRecentReleases);

  return (
    <div>
      <PageHeader
        title="Economic Releases"
        titleAdornment={<ExplanationTrigger explanation={ECONOMIC_RELEASE} />}
        description="Scheduled dates for the economic releases Economic Intelligence tracks."
      >
        <ReleaseScheduleDisclosure />
      </PageHeader>

      <div className="mt-8 divide-y divide-line [&>*]:py-8 [&>*:first-child]:pt-0 [&>*:last-child]:pb-0">
        {upcoming.status === "loading" && <LoadingSkeleton label="Loading upcoming releases" heightClassName="h-40" />}
        {upcoming.status === "error" && <ErrorMessage message={UPCOMING_ERROR_MESSAGE} onRetry={upcoming.reload} />}
        {upcoming.status === "success" && (
          <ReleaseCalendarSection
            sectionId="upcoming"
            heading="Upcoming Releases"
            emptyMessage="No scheduled releases in this window."
            releases={upcoming.data.releases}
          />
        )}

        {recent.status === "loading" && <LoadingSkeleton label="Loading recent releases" heightClassName="h-40" />}
        {recent.status === "error" && <ErrorMessage message={RECENT_ERROR_MESSAGE} onRetry={recent.reload} />}
        {recent.status === "success" && (
          <ReleaseCalendarSection
            sectionId="recent"
            heading="Recent Releases"
            emptyMessage="No recently scheduled releases in this window."
            releases={recent.data.releases}
          />
        )}
      </div>
    </div>
  );
}
