/**
 * Deterministic PRESENTATION salience for Labor `LaborChangeEvent`s --
 * frozen by docs/product/overview-attention-model-v1.md §4/§7. This is
 * a refactor-for-reuse, NOT a new hierarchy: `/labor`'s own
 * `components/labor/WhatChangedSection.tsx` already implemented and
 * shipped this exact four-way filter (Increment #20E.2); it is
 * extracted here, verbatim, so Overview's own compact preview can
 * reuse the identical, already-tested logic instead of a second,
 * potentially-diverging copy. `WhatChangedSection.tsx` itself is
 * updated to call this function rather than inlining the filters --
 * behavior-preserving, not a rewrite.
 *
 * Tier 1 -- Primary domain state: the LABOR component's own state or
 * availability transition (any event_type) -- the single most
 * decision-relevant fact for Labor.
 *
 * Tier 2 -- Structural change: EMPLOYMENT's/UNEMPLOYMENT's own real
 * `field === "state"` classification changes (STATE_CHANGED or
 * AVAILABILITY_LOST/RESTORED).
 *
 * Tier 3 -- Secondary/corroborating signal: EMPLOYMENT's own
 * `condition`/`momentum` fields, reported independently, never
 * suppressed by a co-occurring Tier 1/2 event on the same evidence.
 *
 * Tier 4 -- Metric update: every remaining METRIC_CHANGED event (any
 * component).
 *
 * Mutually exclusive and exhaustive by construction, identical to the
 * shipped `/labor` filters: `field` for a state-shaped comparison is
 * one of "state"/"condition"/"momentum" (LABOR only ever uses "state"),
 * and `condition`/`momentum` belong to EMPLOYMENT alone -- see
 * app/domain/labor_what_changed.py.
 */
import type { LaborChangeEvent } from "../api/labor.types";

export interface LaborSalienceTiers {
  tier1: LaborChangeEvent[];
  tier2: LaborChangeEvent[];
  tier3: LaborChangeEvent[];
  tier4: LaborChangeEvent[];
}

export function tierLaborChanges(events: readonly LaborChangeEvent[]): LaborSalienceTiers {
  return {
    tier1: events.filter((e) => e.component === "LABOR"),
    tier2: events.filter((e) => e.component !== "LABOR" && e.field === "state" && e.event_type !== "METRIC_CHANGED"),
    tier3: events.filter((e) => e.field === "condition" || e.field === "momentum"),
    tier4: events.filter((e) => e.event_type === "METRIC_CHANGED"),
  };
}
