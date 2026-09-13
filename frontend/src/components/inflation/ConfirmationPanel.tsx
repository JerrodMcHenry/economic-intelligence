import type { ConfirmationResult } from "../../api/inflation.types";
import { formatPeriod } from "../../lib/format";
import { confirmationRelationshipLabel, confirmationRelationshipTone, inflationStateLabel, inflationStateTone } from "../../lib/inflationLabels";
import { Badge } from "./Badge";

/**
 * Core PCE is the primary read (shown in InflationHero, above); this
 * section only ever shows whether Core CPI confirms or diverges from
 * it -- never an equal "vote" alongside Core PCE. When `relationship`
 * is UNAVAILABLE, this panel says so plainly; it never affects whether
 * the primary Core PCE state above renders. The "Core CPI confirmation"
 * label sits directly above the relationship badge so it reads
 * unambiguously as Core CPI's status, never as a second, competing
 * reading of the whole monitor.
 */
export function ConfirmationPanel({ confirmation }: { confirmation: ConfirmationResult }) {
  const { confirmation_latest, relationship, latest_common_period } = confirmation;

  return (
    <section aria-labelledby="confirmation-heading">
      <h2 id="confirmation-heading" className="text-sm font-medium text-neutral-500">
        Confirmation
      </h2>
      <p className="mt-1 text-xs text-neutral-400">Core PCE is primary. Core CPI confirms or diverges from it.</p>

      <div className="mt-4">
        <p className="text-xs font-medium uppercase tracking-wide text-neutral-400">Core CPI confirmation</p>
        <div className="mt-1.5">
          <Badge label={confirmationRelationshipLabel(relationship)} tone={confirmationRelationshipTone(relationship)} size="lg" />
        </div>
      </div>

      <dl className="mt-4 flex flex-wrap gap-x-10 gap-y-3">
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-neutral-400">Core CPI state</dt>
          <dd className="mt-1.5">
            <Badge label={inflationStateLabel(confirmation_latest.state)} tone={inflationStateTone(confirmation_latest.state)} />
          </dd>
        </div>
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-neutral-400">Confirmation period</dt>
          <dd className="mt-1.5 text-sm text-neutral-700">{formatPeriod(latest_common_period)}</dd>
        </div>
      </dl>
    </section>
  );
}
