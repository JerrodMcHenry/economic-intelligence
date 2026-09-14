import { Link } from "react-router-dom";

import type { ChangeEvent } from "../../api/inflation.types";
import { formatMetricValueOrUnavailable } from "../../lib/format";
import {
  CHANGE_COMPONENT_LABELS,
  changeFieldLabel,
  confirmationRelationshipLabelOrRaw,
  inflationStateLabelOrRaw,
} from "../../lib/inflationLabels";
import { tierInflationChanges } from "../../lib/inflationSalience";
import { Disclosure } from "../Disclosure";

/**
 * A `ChangeEvent.previous_value`/`current_value` for a "state" or
 * "relationship" field arrives as the raw backend enum string -- look
 * it up in the same label maps `/inflation`'s own WhatChangedSection
 * uses for exactly this case, rather than showing the raw string or
 * (worse) reformatting it as if it were numeric. Every other field is
 * numeric and already handled by `formatMetricValueOrUnavailable`.
 */
function formatChangeValue(field: string, value: number | string | null): string {
  if (typeof value !== "string") return formatMetricValueOrUnavailable(value);
  if (field === "state") return inflationStateLabelOrRaw(value);
  if (field === "relationship") return confirmationRelationshipLabelOrRaw(value);
  return value;
}

/** Availability is a data fact, never economic direction (docs/product/overview-attention-model-v1.md
 * §8) -- "became unavailable"/"became available", never "improved"/"worsened",
 * mirroring `/labor`'s own identical sentence shape verbatim. */
function AvailabilitySentence({ event }: { event: ChangeEvent }) {
  const componentLabel = CHANGE_COMPONENT_LABELS[event.component];
  const fieldLabel = changeFieldLabel(event.field);
  const verb = event.event_type === "AVAILABILITY_LOST" ? "became unavailable" : "became available";
  return (
    <p className="text-sm text-neutral-700">
      {componentLabel} {fieldLabel.toLowerCase()} analysis {verb}.
    </p>
  );
}

/** Tier 1's own event, rendered as the domain-level headline -- "Inflation
 * state: X → Y" -- the single most decision-relevant fact for this
 * domain, mirroring `/labor`'s own Tier 1 "Labor state: ..." headline. */
function Tier1Line({ event }: { event: ChangeEvent }) {
  if (event.event_type === "AVAILABILITY_LOST" || event.event_type === "AVAILABILITY_RESTORED") {
    return <AvailabilitySentence event={event} />;
  }
  return (
    <p className="text-sm font-semibold text-neutral-900">
      Inflation state: {formatChangeValue(event.field, event.previous_value)}
      <span aria-hidden="true" className="mx-1.5 text-neutral-400">
        →
      </span>
      {formatChangeValue(event.field, event.current_value)}
    </p>
  );
}

/** Tier 2 (Headline PCE/CPI state changes, any-component availability)
 * and Tier 3 (Confirmation) rows -- component-labeled, not domain-level.
 * Confirmation renders as "Confirmation: X → Y" rather than
 * "Confirmation Relationship: X → Y" -- the field name is implied. */
function StructuralRow({ event }: { event: ChangeEvent }) {
  if (event.event_type === "AVAILABILITY_LOST" || event.event_type === "AVAILABILITY_RESTORED") {
    return (
      <li>
        <AvailabilitySentence event={event} />
      </li>
    );
  }
  const label = event.event_type === "CONFIRMATION_CHANGED" ? CHANGE_COMPONENT_LABELS[event.component] : `${CHANGE_COMPONENT_LABELS[event.component]} ${changeFieldLabel(event.field)}`;
  return (
    <li className="text-sm">
      <span className="text-neutral-500">{label}: </span>
      <span className="font-medium text-neutral-900">{formatChangeValue(event.field, event.previous_value)}</span>
      <span aria-hidden="true" className="mx-1.5 text-neutral-300">
        →
      </span>
      <span className="font-medium text-neutral-900">{formatChangeValue(event.field, event.current_value)}</span>
    </li>
  );
}

/** Tier 4 -- numeric-only metric updates, collapsed behind a
 * count-labeled disclosure, always inspectable, never capped. */
function MetricRow({ event }: { event: ChangeEvent }) {
  return (
    <li className="text-sm">
      <span className="text-neutral-500">
        {CHANGE_COMPONENT_LABELS[event.component]} {changeFieldLabel(event.field)}
      </span>
      <span className="ml-2 tabular-nums text-neutral-700">
        {formatChangeValue(event.field, event.previous_value)}
        <span aria-hidden="true" className="mx-1.5 text-neutral-300">
          →
        </span>
        {formatChangeValue(event.field, event.current_value)}
      </span>
    </li>
  );
}

/**
 * The Economic Overview's compact Inflation "What Changed" preview --
 * frozen by docs/product/overview-attention-model-v1.md §6/§13
 * (Increment #22B, replacing the old fixed `MAX_EVENTS = 3` truncation
 * with a deterministic 4-tier PRESENTATION priority). Renders ONLY
 * real, backend-returned `ChangeEvent`s from
 * `InflationWhatChangedResult.changes`, the same flat,
 * deterministically-ordered list `inflation_what_changed_v1.0` already
 * assembles -- this component classifies those events into tiers
 * (`lib/inflationSalience.ts`), it never reorders, filters out, or
 * re-ranks by magnitude. Every Tier 1-3 (structural) event renders,
 * uncapped -- truncating a structural event to make room would
 * reintroduce the exact noise-ordering defect this increment exists to
 * fix (docs/product/product-experience-audit-v1.md §2/§4/§6). Tier 4
 * (routine numeric) events are always collapsed behind a
 * count-labeled disclosure, never capped, never hidden from
 * inspection.
 *
 * Four distinct quiet states, never conflated (§10): comparison
 * unavailable, zero events at all, structural-no-change-but-metrics-moved,
 * and (unchanged, out of scope here) insufficient data on the Current
 * State card above. "No structural change." is used ONLY when Tiers
 * 1-3 are empty AND Tier 4 is not -- never when there are truly zero
 * events (a different, more honest "nothing happened at all" case),
 * and never replaced with "Stable" or any canonical-state word unless
 * the backend's own current state field literally equals that value.
 *
 * No own `<section>`/heading -- the shared "What Changed" heading
 * lives once in pages/Overview.tsx; "Inflation" here is a plain `<p>`
 * sub-label, matching its Labor peer (`LaborWhatChangedPreview`) and
 * `InflationCurrentStateCard`'s identical convention.
 */
export function WhatChangedPreview({ events, comparisonAvailable }: { events: readonly ChangeEvent[]; comparisonAvailable: boolean }) {
  const { tier1, tier2, tier3, tier4 } = tierInflationChanges(events);
  const structural = [...tier1, ...tier2, ...tier3];
  const hasStructural = structural.length > 0;

  return (
    <div>
      <p className="text-sm font-semibold text-neutral-700">Inflation</p>

      {!comparisonAvailable ? (
        <p className="mt-3 text-sm text-neutral-500">Previous-period comparison unavailable.</p>
      ) : events.length === 0 ? (
        <p className="mt-3 text-sm text-neutral-500">No canonical Inflation changes were reported for this comparison.</p>
      ) : (
        <div className="mt-3 space-y-2">
          {!hasStructural && <p className="text-sm text-neutral-500">No structural change.</p>}

          {tier1.map((event, index) => (
            <Tier1Line key={`tier1-${index}`} event={event} />
          ))}

          {(tier2.length > 0 || tier3.length > 0) && (
            <ul className="space-y-2">
              {[...tier2, ...tier3].map((event, index) => (
                <StructuralRow key={`tier23-${index}`} event={event} />
              ))}
            </ul>
          )}

          {tier4.length > 0 && (
            <Disclosure summary={`Metric updates (${tier4.length})`}>
              <ul className="space-y-2">
                {tier4.map((event, index) => (
                  <MetricRow key={`tier4-${index}`} event={event} />
                ))}
              </ul>
            </Disclosure>
          )}
        </div>
      )}

      <Link to="/inflation" className="mt-4 inline-block text-sm font-medium text-neutral-700 hover:text-neutral-900">
        View Inflation →
      </Link>
    </div>
  );
}
