import { Link } from "react-router-dom";

import type { ChangeEvent } from "../../api/inflation.types";
import { formatMetricValueOrUnavailable } from "../../lib/format";
import {
  CHANGE_COMPONENT_LABELS,
  changeFieldLabel,
  confirmationRelationshipLabelOrRaw,
  inflationStateLabelOrRaw,
} from "../../lib/inflationLabels";

const MAX_EVENTS = 3;

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

/**
 * The Economic Overview's compact Inflation "What Changed" preview --
 * renders ONLY real, backend-returned `ChangeEvent`s from
 * `InflationWhatChangedResult.changes`, the same flat, deterministically-
 * ordered list `inflation_what_changed_v1.0` already assembles across
 * all five sections (component order, then event-type order, then
 * field order -- see app/domain/inflation_what_changed.py). This
 * component only truncates that array (`.slice(0, MAX_EVENTS)`) for
 * display; it never reorders, filters by "importance", or re-ranks it.
 *
 * Deliberately does NOT synthesize a "State remains X" narrative the
 * way `/inflation`'s own `WhatChangedSection` does for its own,
 * separately-reviewed per-section summaries -- that sentence is
 * assembled from the ABSENCE of a `STATE_CHANGED` event, which is a
 * frontend inference, not a backend-emitted fact. Overview must never
 * invent that inference (see docs/ENGINEERING_JOURNAL.md's #19A entry).
 * If `events` is empty, this says only that no changes were reported --
 * true whether because nothing changed or because a comparison was
 * unavailable, never a stronger claim like "Inflation was unchanged."
 *
 * Increment #20E.2: this component's own `<section>`/`<h2>` wrapper was
 * removed -- the shared "What Changed" heading now lives once in
 * pages/Overview.tsx, with this card (labeled "Inflation", a plain
 * `<p>` sub-label, never its own heading -- matching
 * `InflationCurrentStateCard`'s identical convention) and its Labor
 * peer (`LaborWhatChangedPreview`) rendered as two independently-gated
 * sub-blocks beneath it (docs/architecture/labor-ui-v1.md §30).
 */
export function WhatChangedPreview({ events }: { events: readonly ChangeEvent[] }) {
  const shown = events.slice(0, MAX_EVENTS);

  return (
    <div>
      <p className="text-sm font-semibold text-neutral-700">Inflation</p>

      {shown.length === 0 ? (
        <p className="mt-3 text-sm text-neutral-500">No canonical Inflation changes were reported for this comparison.</p>
      ) : (
        <ul className="mt-3 space-y-2.5">
          {shown.map((event, index) => (
            <li key={`${event.component}-${event.event_type}-${event.field}-${index}`} className="text-sm">
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
          ))}
        </ul>
      )}

      <Link to="/inflation" className="mt-4 inline-block text-sm font-medium text-neutral-700 hover:text-neutral-900">
        See full comparison →
      </Link>
    </div>
  );
}
