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

const MAX_EVENTS = 3;

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

/**
 * The Economic Overview's compact Labor "What Changed" preview -- the
 * peer of `WhatChangedPreview.tsx` (Inflation's own), a SEPARATE
 * component rather than a generalized/parameterized shared one (two
 * monitors don't yet justify that abstraction, mirroring this
 * project's own repeated "no premature generic framework" precedent --
 * docs/architecture/labor-ui-v1.md §30/§45). Renders ONLY real,
 * backend-returned `LaborChangeEvent`s from
 * `LaborWhatChangedResult.changes`, the same flat, deterministically-
 * ordered list `labor_what_changed_v1.0` already assembles. This
 * component only truncates that array (`.slice(0, MAX_EVENTS)`) for
 * display; it never reorders, filters by "importance", or re-ranks it
 * -- the full 4-tier presentation priority lives on /labor's own
 * WhatChangedSection instead. No own `<section>`/heading -- the shared
 * "What Changed" heading lives once in pages/Overview.tsx; "Labor"
 * here is a plain `<p>` sub-label, matching its Inflation peer
 * (`WhatChangedPreview`) and `LaborCurrentStateCard`'s identical
 * convention.
 */
export function LaborWhatChangedPreview({ events }: { events: readonly LaborChangeEvent[] }) {
  const shown = events.slice(0, MAX_EVENTS);

  return (
    <div>
      <p className="text-sm font-semibold text-neutral-700">Labor</p>

      {shown.length === 0 ? (
        <p className="mt-3 text-sm text-neutral-500">No canonical Labor changes were reported for this comparison.</p>
      ) : (
        <ul className="mt-3 space-y-2.5">
          {shown.map((event, index) => (
            <li key={`${event.component}-${event.event_type}-${event.field}-${index}`} className="text-sm">
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
          ))}
        </ul>
      )}

      <Link to="/labor" className="mt-4 inline-block text-sm font-medium text-neutral-700 hover:text-neutral-900">
        See full comparison →
      </Link>
    </div>
  );
}
