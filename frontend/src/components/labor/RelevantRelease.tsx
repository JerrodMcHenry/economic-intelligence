import type { ReleaseOccurrenceItem } from "../../api/releases.types";
import { ReleaseDateBadge } from "../releases/ReleaseDateBadge";
import { ReleaseRow } from "../releases/ReleaseRow";
import { ReleaseScheduleDisclosure } from "../releases/ReleaseScheduleDisclosure";

// Employment Situation's stable release identity (BLS `empsit` since #56B) -- the same
// `provider_release_id` app/domain/labor_release_processing.py and the
// backend's own curated-catalog migration both key off, never the
// release's display `name` (which could change without changing this
// identity). See docs/architecture/labor-ui-v1.md §4/§24.
const EMPLOYMENT_SITUATION_PROVIDER_RELEASE_ID = "empsit";

function findEmploymentSituation(releases: readonly ReleaseOccurrenceItem[]): ReleaseOccurrenceItem | null {
  return releases.find((r) => r.provider_release_id === EMPLOYMENT_SITUATION_PROVIDER_RELEASE_ID) ?? null;
}

/**
 * The next scheduled AND most recent Employment Situation occurrence,
 * filtered client-side from the Labor page's own already-fetched
 * Upcoming/Recent release arrays -- no new backend endpoint, no
 * server-side filter param (docs/architecture/labor-ui-v1.md §4/§24).
 * Reuses `ReleaseRow`/`ReleaseDateBadge`/`ReleaseScheduleDisclosure`
 * completely unchanged -- every date and `schedule_status` rendered
 * here is exactly what `GET /api/v1/releases` returned; this component
 * never infers publication from a scheduled date.
 *
 * `upcoming`/`recent` are each `null` while that side's own resource is
 * still loading or has errored -- the page renders that side's own
 * loading/error UI separately (failure isolation, per
 * docs/architecture/labor-ui-v1.md §38); this component still shows
 * whichever side IS available rather than waiting for both.
 */
export function RelevantRelease({
  upcoming,
  recent,
}: {
  upcoming: readonly ReleaseOccurrenceItem[] | null;
  recent: readonly ReleaseOccurrenceItem[] | null;
}) {
  const next = upcoming === null ? null : findEmploymentSituation(upcoming);
  const mostRecent = recent === null ? null : findEmploymentSituation(recent);
  const bothLoaded = upcoming !== null && recent !== null;

  return (
    <section aria-labelledby="labor-relevant-release-heading">
      <h2 id="labor-relevant-release-heading" className="text-sm font-medium text-fg-muted">
        Employment Situation release
      </h2>

      {next === null && mostRecent === null ? (
        bothLoaded && <p className="mt-3 text-sm text-fg-muted">No scheduled Employment Situation release in the current window.</p>
      ) : (
        <ul className="mt-3 space-y-4">
          {next && (
            <li className="flex gap-4">
              <ReleaseDateBadge date={next.scheduled_date} />
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium uppercase tracking-wide text-fg-muted">Next scheduled</p>
                <div className="mt-1">
                  <ReleaseRow item={next} />
                </div>
              </div>
            </li>
          )}
          {mostRecent && (
            <li className="flex gap-4">
              <ReleaseDateBadge date={mostRecent.scheduled_date} />
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium uppercase tracking-wide text-fg-muted">Most recent</p>
                <div className="mt-1">
                  <ReleaseRow item={mostRecent} />
                </div>
              </div>
            </li>
          )}
        </ul>
      )}

      <div className="mt-4">
        <ReleaseScheduleDisclosure />
      </div>
    </section>
  );
}
