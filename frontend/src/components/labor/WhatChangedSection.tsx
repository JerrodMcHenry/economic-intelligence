import type { LaborChangeEvent, LaborWhatChangedResult } from "../../api/labor.types";
import { Disclosure } from "../../components/Disclosure";
import { formatPeriodPair } from "../../lib/format";
import { formatLaborMetricValue } from "../../lib/laborFormat";
import { tierLaborChanges } from "../../lib/laborSalience";
import {
  employmentConditionLabelOrRaw,
  employmentMomentumLabelOrRaw,
  employmentStateLabelOrRaw,
  laborChangeComponentLabelOrRaw,
  laborChangeFieldLabel,
  laborStateLabelOrRaw,
  unemploymentStateLabelOrRaw,
} from "../../lib/laborLabels";

/**
 * `LaborChangeEvent.previous_value`/`current_value` for a state-shaped
 * field ("state"/"condition"/"momentum"), dispatched by component AND
 * field -- LABOR's own "state" is a `LaborState`, EMPLOYMENT's is an
 * `EmploymentState` (a different vocabulary sharing some of the same
 * words), UNEMPLOYMENT's is an `UnemploymentTrendState`. Never guesses:
 * every (component, field) pair this function receives is one of the
 * five state-shaped fields `labor_what_changed_v1.0` actually defines
 * (docs/architecture/labor-ui-v1.md §17).
 */
function stateValueLabel(event: LaborChangeEvent, value: string): string {
  if (event.component === "LABOR") return laborStateLabelOrRaw(value);
  if (event.field === "condition") return employmentConditionLabelOrRaw(value);
  if (event.field === "momentum") return employmentMomentumLabelOrRaw(value);
  if (event.component === "EMPLOYMENT") return employmentStateLabelOrRaw(value);
  return unemploymentStateLabelOrRaw(value);
}

/** One event's own value, formatted per its actual shape -- state-shaped
 * fields use the component/field-aware label lookup above; numeric
 * fields use `formatLaborMetricValue` (job counts vs. percentages,
 * never blanket-formatted). */
function formatEventValue(event: LaborChangeEvent, value: number | string | null): string {
  if (value === null) return "Unavailable";
  if (typeof value === "string") return stateValueLabel(event, value);
  return formatLaborMetricValue(event.field, value);
}

function AvailabilitySentence({ event }: { event: LaborChangeEvent }) {
  const componentLabel = laborChangeComponentLabelOrRaw(event.component);
  const fieldLabel = laborChangeFieldLabel(event.field);
  // Availability is a data fact, never economic direction (docs/architecture/labor-ui-v1.md §19) --
  // "became unavailable"/"became available", never "improved"/"worsened".
  const verb = event.event_type === "AVAILABILITY_LOST" ? "became unavailable" : "became available";
  return (
    <p className="text-sm text-fg-secondary">
      {componentLabel} {fieldLabel.toLowerCase()} analysis {verb}.
    </p>
  );
}

function StateChangeRow({ event }: { event: LaborChangeEvent }) {
  const componentLabel = laborChangeComponentLabelOrRaw(event.component);
  const fieldLabel = laborChangeFieldLabel(event.field);
  return (
    <li className="text-sm">
      <span className="text-fg-muted">
        {componentLabel} {fieldLabel}:{" "}
      </span>
      <span className="font-medium text-fg">{formatEventValue(event, event.previous_value)}</span>
      <span aria-hidden="true" className="mx-1.5 text-fg-faint">
        →
      </span>
      <span className="font-medium text-fg">{formatEventValue(event, event.current_value)}</span>
    </li>
  );
}

function MetricChangeRow({ event }: { event: LaborChangeEvent }) {
  return (
    <li className="text-sm">
      <span className="text-fg-muted">
        {laborChangeComponentLabelOrRaw(event.component)} {laborChangeFieldLabel(event.field)}:{" "}
      </span>
      <span className="tabular-nums text-fg-secondary">
        {formatEventValue(event, event.previous_value)}
        <span aria-hidden="true" className="mx-1.5 text-fg-faint">
          →
        </span>
        {formatEventValue(event, event.current_value)}
      </span>
    </li>
  );
}

/**
 * The full `/labor` "What Changed" section, consuming
 * `GET /api/v1/monitors/labor/changes` verbatim. Renders the frozen
 * 4-tier PRESENTATION priority (docs/architecture/labor-ui-v1.md §17)
 * -- this is a presentation-only re-grouping of the backend's own
 * flattened, deterministically-ordered `changes[]` array; it never
 * reorders, mutates, or drops an event from that array itself, and
 * every event remains reachable in the tiered lists below (tier
 * membership is a filter, not a deletion -- an event appears in
 * exactly one tier, and every tier is always rendered when non-empty).
 *
 * The four-tier filter itself lives in `lib/laborSalience.ts`
 * (Increment #22B) -- extracted, not reimplemented, so Overview's own
 * compact preview (`components/overview/LaborWhatChangedPreview.tsx`)
 * reuses the identical, already-tested logic rather than a second,
 * potentially-diverging copy (docs/product/overview-attention-model-v1.md
 * §7/§20).
 */
export function WhatChangedSection({ whatChanged }: { whatChanged: LaborWhatChangedResult }) {
  const events = whatChanged.changes;

  const { tier1: laborTier, tier2: stateTier, tier3: conditionMomentumTier, tier4: metricTier } = tierLaborChanges(events);

  const periodPair = formatPeriodPair(whatChanged.previous_period, whatChanged.current_period);

  return (
    <section aria-labelledby="labor-what-changed-heading">
      <div className="flex max-w-3xl flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 id="labor-what-changed-heading" className="text-sm font-medium text-fg-muted">
          What changed
        </h2>
        {whatChanged.comparison_available && <span className="text-xs font-medium tabular-nums text-fg-muted">{periodPair}</span>}
      </div>

      {!whatChanged.comparison_available ? (
        <p className="mt-3 text-sm text-fg-muted">Previous-period comparison unavailable.</p>
      ) : events.length === 0 ? (
        <p className="mt-3 text-sm text-fg-muted">No canonical Labor changes were reported for this comparison.</p>
      ) : (
        <div className="mt-3 max-w-3xl space-y-4">
          {/* Tier 1: top-level LABOR state/availability */}
          {laborTier.map((event, index) =>
            event.event_type === "STATE_CHANGED" ? (
              <p key={index} className="text-sm font-semibold text-fg">
                Labor state: {formatEventValue(event, event.previous_value)}
                <span aria-hidden="true" className="mx-1.5 text-fg-muted">
                  →
                </span>
                {formatEventValue(event, event.current_value)}
              </p>
            ) : (
              <AvailabilitySentence key={index} event={event} />
            ),
          )}

          {/* Tier 2: Employment/Unemployment state changes and availability */}
          {stateTier.length > 0 && (
            <ul className="space-y-2">
              {stateTier.map((event, index) =>
                event.event_type === "STATE_CHANGED" ? (
                  <StateChangeRow key={index} event={event} />
                ) : (
                  <li key={index}>
                    <AvailabilitySentence event={event} />
                  </li>
                ),
              )}
            </ul>
          )}

          {/* Tier 3: condition/momentum, reported independently -- never suppressed */}
          {conditionMomentumTier.length > 0 && (
            <ul className="space-y-2">
              {conditionMomentumTier.map((event, index) =>
                event.event_type === "STATE_CHANGED" ? (
                  <StateChangeRow key={index} event={event} />
                ) : (
                  <li key={index}>
                    <AvailabilitySentence event={event} />
                  </li>
                ),
              )}
            </ul>
          )}

          {/* Tier 4: numeric metric updates -- secondary, behind a disclosure */}
          {metricTier.length > 0 && (
            <Disclosure summary={`Metric updates (${metricTier.length})`}>
              <ul className="space-y-2">
                {metricTier.map((event, index) => (
                  <MetricChangeRow key={index} event={event} />
                ))}
              </ul>
            </Disclosure>
          )}
        </div>
      )}
    </section>
  );
}
