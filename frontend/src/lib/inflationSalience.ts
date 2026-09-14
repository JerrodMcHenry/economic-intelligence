/**
 * Deterministic PRESENTATION salience for Inflation `ChangeEvent`s --
 * frozen by docs/product/overview-attention-model-v1.md §4/§6. A
 * classification of already-canonical events into four fixed
 * presentation tiers, computed only from each event's `component` and
 * `field` -- never a score, never a magnitude comparison, never an
 * inference not already present in the backend's own response. This
 * module orders/groups; it never suppresses an event, never changes
 * an event's own values, and never asserts materiality beyond "this is
 * the kind of event this tier is defined to contain."
 *
 * Tier 1 -- Primary domain state: Core PCE's own state
 * (`component === "PRIMARY_MOMENTUM" && field === "state"`), any
 * event_type (STATE_CHANGED or AVAILABILITY_LOST/RESTORED) -- the
 * single most decision-relevant fact for Inflation, matching what
 * `InflationCurrentStateCard` already shows as "Inflation" on Overview.
 *
 * Tier 2 -- Structural change: Headline PCE's/Headline CPI's own real,
 * independently-classified STATE_CHANGED events, plus ANY
 * AVAILABILITY_LOST/RESTORED event on any component not already in
 * Tier 1 -- an availability transition is always operationally
 * important regardless of which section it's on (§8).
 *
 * Tier 3 -- Secondary/corroborating signal: CONFIRMATION_CHANGED only
 * -- Confirmation is explicitly, by this product's own existing
 * curated copy (content/explanations/inflation.ts's CONFIRMATION
 * explanation), "a separate, secondary signal shown alongside"
 * Core PCE's own state, never a primary classification.
 *
 * Tier 4 -- Metric update: every remaining METRIC_CHANGED event (any
 * component, including the context-only r_1m_annualized).
 *
 * Target never contributes a Tier 1-3 event -- it has no state concept
 * (app/domain/inflation_what_changed.py's own TargetSectionChanges
 * docstring: "Target has no state concept"); it only ever contributes
 * Tier 4 or Tier 2 (availability) events.
 *
 * Mutually exclusive and exhaustive by construction: every `ChangeEvent`
 * the backend can emit has an `event_type` of exactly one of
 * METRIC_CHANGED/STATE_CHANGED/AVAILABILITY_LOST/AVAILABILITY_RESTORED/
 * CONFIRMATION_CHANGED, and STATE_CHANGED only ever occurs on
 * PRIMARY_MOMENTUM/HEADLINE_PCE/HEADLINE_CPI's own "state" field
 * (verified in app/domain/inflation_what_changed.py) -- so each event
 * falls into exactly one tier below, never zero, never more than one.
 */
import type { ChangeEvent } from "../api/inflation.types";

export interface InflationSalienceTiers {
  tier1: ChangeEvent[];
  tier2: ChangeEvent[];
  tier3: ChangeEvent[];
  tier4: ChangeEvent[];
}

export function tierInflationChanges(events: readonly ChangeEvent[]): InflationSalienceTiers {
  const tier1: ChangeEvent[] = [];
  const tier2: ChangeEvent[] = [];
  const tier3: ChangeEvent[] = [];
  const tier4: ChangeEvent[] = [];

  for (const event of events) {
    const isPrimaryState = event.component === "PRIMARY_MOMENTUM" && event.field === "state";
    if (isPrimaryState) {
      tier1.push(event);
      continue;
    }
    if (event.event_type === "AVAILABILITY_LOST" || event.event_type === "AVAILABILITY_RESTORED") {
      tier2.push(event);
      continue;
    }
    if ((event.component === "HEADLINE_PCE" || event.component === "HEADLINE_CPI") && event.event_type === "STATE_CHANGED") {
      tier2.push(event);
      continue;
    }
    if (event.event_type === "CONFIRMATION_CHANGED") {
      tier3.push(event);
      continue;
    }
    // Everything else is METRIC_CHANGED (or an unrecognized future
    // shape) -- routine, never a classification, always Tier 4.
    tier4.push(event);
  }

  return { tier1, tier2, tier3, tier4 };
}
