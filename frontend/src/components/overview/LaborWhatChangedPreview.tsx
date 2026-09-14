import { Link } from "react-router-dom";

import type { LaborChangeEvent } from "../../api/labor.types";
import { formatLaborMetricValue } from "../../lib/laborFormat";
import {
  employmentConditionLabelOrRaw,
  employmentMomentumLabelOrRaw,
  employmentStateLabelOrRaw,
  laborChangeComponentLabelOrRaw,
  laborChangeFieldLabel,
  laborStateLabelOrRaw,
  unemploymentStateLabelOrRaw,
} from "../../lib/laborLabels";
import { tierLaborChanges } from "../../lib/laborSalience";
import { Disclosure } from "../Disclosure";

function stateValueLabel(event: LaborChangeEvent, value: string): string {
  if (event.component === "LABOR") return laborStateLabelOrRaw(value);
  if (event.field === "condition") return employmentConditionLabelOrRaw(value);
  if (event.field === "momentum") return employmentMomentumLabelOrRaw(value);
  if (event.component === "EMPLOYMENT") return employmentStateLabelOrRaw(value);
  return unemploymentStateLabelOrRaw(value);
}

function formatChangeValue(event: LaborChangeEvent, value: number | string | null): string {
  if (value === null) return "Unavailable";
  if (typeof value === "string") return stateValueLabel(event, value);
  return formatLaborMetricValue(event.field, value);
}

/** Availability is a data fact, never economic direction (docs/product/overview-attention-model-v1.md
 * §8) -- reused verbatim from `/labor`'s own `WhatChangedSection.tsx`. */
function AvailabilitySentence({ event }: { event: LaborChangeEvent }) {
  const componentLabel = laborChangeComponentLabelOrRaw(event.component);
  const fieldLabel = laborChangeFieldLabel(event.field);
  const verb = event.event_type === "AVAILABILITY_LOST" ? "became unavailable" : "became available";
  return (
    <p className="text-sm text-neutral-700">
      {componentLabel} {fieldLabel.toLowerCase()} analysis {verb}.
    </p>
  );
}

/** Tier 1 (LABOR component) rendered as the domain-level headline. */
function Tier1Line({ event }: { event: LaborChangeEvent }) {
  if (event.event_type === "AVAILABILITY_LOST" || event.event_type === "AVAILABILITY_RESTORED") {
    return <AvailabilitySentence event={event} />;
  }
  return (
    <p className="text-sm font-semibold text-neutral-900">
      Labor state: {formatChangeValue(event, event.previous_value)}
      <span aria-hidden="true" className="mx-1.5 text-neutral-400">
        →
      </span>
      {formatChangeValue(event, event.current_value)}
    </p>
  );
}

/** Tier 2 (Employment/Unemployment state) and Tier 3 (condition/momentum)
 * rows -- component-labeled, not domain-level. */
function StructuralRow({ event }: { event: LaborChangeEvent }) {
  if (event.event_type === "AVAILABILITY_LOST" || event.event_type === "AVAILABILITY_RESTORED") {
    return (
      <li>
        <AvailabilitySentence event={event} />
      </li>
    );
  }
  return (
    <li className="text-sm">
      <span className="text-neutral-500">
        {laborChangeComponentLabelOrRaw(event.component)} {laborChangeFieldLabel(event.field)}:{" "}
      </span>
      <span className="font-medium text-neutral-900">{formatChangeValue(event, event.previous_value)}</span>
      <span aria-hidden="true" className="mx-1.5 text-neutral-300">
        →
      </span>
      <span className="font-medium text-neutral-900">{formatChangeValue(event, event.current_value)}</span>
    </li>
  );
}

/** Tier 4 -- numeric-only metric updates, collapsed, always inspectable. */
function MetricRow({ event }: { event: LaborChangeEvent }) {
  return (
    <li className="text-sm">
      <span className="text-neutral-500">
        {laborChangeComponentLabelOrRaw(event.component)} {laborChangeFieldLabel(event.field)}
      </span>
      <span className="ml-2 tabular-nums text-neutral-700">
        {formatChangeValue(event, event.previous_value)}
        <span aria-hidden="true" className="mx-1.5 text-neutral-300">
          →
        </span>
        {formatChangeValue(event, event.current_value)}
      </span>
    </li>
  );
}

/**
 * The Economic Overview's compact Labor "What Changed" preview --
 * frozen by docs/product/overview-attention-model-v1.md §7/§13
 * (Increment #22B, replacing the old fixed `MAX_EVENTS = 3` truncation
 * with the SAME 4-tier PRESENTATION priority `/labor`'s own
 * `WhatChangedSection.tsx` already ships -- reused via
 * `lib/laborSalience.ts`, never a second, potentially-diverging
 * hierarchy). A SEPARATE component from `WhatChangedPreview.tsx`
 * (Inflation's own), rather than a generalized/parameterized shared
 * one -- two monitors don't yet justify that abstraction, mirroring
 * this project's own repeated "no premature generic framework"
 * precedent. Every Tier 1-3 (structural) event renders, uncapped;
 * Tier 4 (routine numeric) events are always collapsed behind a
 * count-labeled disclosure, never capped, never hidden from
 * inspection.
 *
 * No own `<section>`/heading -- the shared "What Changed" heading
 * lives once in pages/Overview.tsx; "Labor" here is a plain `<p>`
 * sub-label, matching its Inflation peer (`WhatChangedPreview`) and
 * `LaborCurrentStateCard`'s identical convention.
 */
export function LaborWhatChangedPreview({ events, comparisonAvailable }: { events: readonly LaborChangeEvent[]; comparisonAvailable: boolean }) {
  const { tier1, tier2, tier3, tier4 } = tierLaborChanges(events);
  const hasStructural = tier1.length + tier2.length + tier3.length > 0;

  return (
    <div>
      <p className="text-sm font-semibold text-neutral-700">Labor</p>

      {!comparisonAvailable ? (
        <p className="mt-3 text-sm text-neutral-500">Previous-period comparison unavailable.</p>
      ) : events.length === 0 ? (
        <p className="mt-3 text-sm text-neutral-500">No canonical Labor changes were reported for this comparison.</p>
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

      <Link to="/labor" className="mt-4 inline-block text-sm font-medium text-neutral-700 hover:text-neutral-900">
        View Labor →
      </Link>
    </div>
  );
}
