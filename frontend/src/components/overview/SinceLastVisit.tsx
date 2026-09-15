import { Link } from "react-router-dom";

import type { DomainRecap, Monitor, SinceLastVisitResponse } from "../../api/sinceLastVisit.types";
import type { ApiResourceState } from "../../api/useApiResource";
import { formatCheckedAt } from "../../lib/detectedChangeFormat";
import {
  FIRST_VISIT_ORIENTATION_COPY,
  LOOKBACK_CLAMPED_COPY,
  coverageDisclosureCopy,
  domainLabel,
  domainZeroStateCopy,
  lastCheckedCopy,
  recalculationCopy,
  sinceLastVisitHeading,
  sourceUpdateCopy,
  structuralChangeCopy,
} from "../../lib/sinceLastVisitCopy";
import { ErrorMessage } from "../ErrorMessage";
import { LoadingSkeleton } from "../LoadingSkeleton";

const ERROR_MESSAGE = "Recent activity could not be loaded.";

const DOMAIN_CTA: Record<Monitor, { label: string; to: string }> = {
  inflation: { label: "View Inflation →", to: "/inflation" },
  labor: { label: "View Labor →", to: "/labor" },
};

/**
 * The Economic Overview's return-orientation section -- Since Last
 * Visit V1, frozen by docs/product/since-last-visit-v1.md (Increment
 * #25F/#25G/#25H). Renders a deterministic recap of canonical
 * economic-intelligence activity, EXACTLY as the backend already
 * categorized it (contract §63 -- this component classifies nothing:
 * no transition derivation, no "remains" inference, no evaluation-
 * period selection, no salience recomputation, no deduplication).
 *
 * `sinceLastVisit` is the `useSinceLastVisit()` hook's own resource
 * state, supplied by `pages/Overview.tsx` -- this component itself
 * never reads/writes the local checkpoint and never calls the API
 * directly; it is a mostly-pure renderer over an already-resolved
 * resource, mirroring `HowTheyRelate`'s own identical boundary.
 */
export function SinceLastVisit({ sinceLastVisit }: { sinceLastVisit: ApiResourceState<SinceLastVisitResponse> & { reload: () => void } }) {
  return (
    <section aria-labelledby="overview-since-last-visit-heading">
      {sinceLastVisit.status === "loading" && (
        <>
          <h2 id="overview-since-last-visit-heading" className="text-sm font-medium text-neutral-500">
            {sinceLastVisitHeading(true)}
          </h2>
          <div className="mt-3">
            <LoadingSkeleton label="Loading recent activity" heightClassName="h-32" />
          </div>
        </>
      )}

      {sinceLastVisit.status === "error" && (
        <>
          <h2 id="overview-since-last-visit-heading" className="text-sm font-medium text-neutral-500">
            {sinceLastVisitHeading(true)}
          </h2>
          <div className="mt-3">
            <ErrorMessage message={ERROR_MESSAGE} onRetry={sinceLastVisit.reload} />
          </div>
        </>
      )}

      {sinceLastVisit.status === "success" && <SinceLastVisitContent response={sinceLastVisit.data} />}
    </section>
  );
}

function SinceLastVisitContent({ response }: { response: SinceLastVisitResponse }) {
  const heading = sinceLastVisitHeading(response.first_visit);

  return (
    <>
      <h2 id="overview-since-last-visit-heading" className="text-sm font-medium text-neutral-500">
        {heading}
      </h2>

      <div className="mt-3 space-y-4">
        {response.first_visit && <p className="text-sm text-neutral-600">{FIRST_VISIT_ORIENTATION_COPY}</p>}
        {response.lookback_clamped && <p className="text-sm text-neutral-600">{LOOKBACK_CLAMPED_COPY}</p>}

        <DomainRecapBlock recap={response.inflation} />
        <DomainRecapBlock recap={response.labor} />
      </div>
    </>
  );
}

function DomainRecapBlock({ recap }: { recap: DomainRecap }) {
  const label = domainLabel(recap.monitor);
  const cta = DOMAIN_CTA[recap.monitor];
  const hasContent = recap.structural_changes.length > 0 || recap.recalculations.length > 0 || recap.source_updates.length > 0;
  const lastChecked = recap.last_checked_at === null ? null : lastCheckedCopy(formatCheckedAt(recap.last_checked_at));
  const coverageNote = hasContent ? coverageDisclosureCopy(recap.coverage) : null;
  const zeroState = domainZeroStateCopy(recap);

  return (
    <div>
      <p className="text-sm font-semibold text-neutral-800">{label}</p>
      <div className="mt-1 space-y-1 text-sm text-neutral-700">
        {lastChecked && <p className="text-xs text-neutral-500">{lastChecked}</p>}
        {coverageNote && <p className="text-neutral-600">{coverageNote}</p>}

        {recap.structural_changes.map((item) => (
          <p key={`structural-${item.release_check_run_id}-${item.monitor}-${item.field}`}>{structuralChangeCopy(item)}</p>
        ))}
        {recap.recalculations.map((item) => (
          <p key={`recalculation-${item.monitor}-${item.kind}`}>{recalculationCopy(item)}</p>
        ))}
        {recap.source_updates.map((item) => (
          <p key={`source-${item.release_check_run_id}-${item.series_id}-${item.change_type}`}>{sourceUpdateCopy(item)}</p>
        ))}

        {zeroState && <p>{zeroState}</p>}
      </div>
      <Link to={cta.to} className="mt-2 inline-block text-sm font-medium text-neutral-700 hover:text-neutral-900">
        {cta.label}
      </Link>
    </div>
  );
}
