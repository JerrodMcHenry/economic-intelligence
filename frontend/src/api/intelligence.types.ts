/**
 * The #39 Structured Intelligence contract, as consumed by the
 * frontend (Increment #40).
 *
 * A faithful mirror of `app/models/intelligence.py`. The frontend is a
 * CONSUMER of this contract -- it formats these facts, and never
 * recomputes any of them. `src/test/no-intelligence-derivation.test.ts`
 * enforces that.
 */

export type IntelligenceWorld = "inflation" | "jobs" | "rates";

export type IntelligenceType =
  | "RELEASE_PROCESSED"
  | "OBSERVATION_CHANGE"
  | "ANALYSIS_CHANGE"
  | "RATES_MOVEMENT";

/** Whether a source published this, or a MacroChipz methodology concluded it. */
export type IntelligenceBasis = "SOURCE_FACT" | "METHODOLOGY_DERIVED";

/** Whether MacroChipz genuinely recorded this, or reconstructed it. */
export type KnowledgeBasis = "OBSERVED" | "BACKFILLED";

/** Whether a methodology change is about the economy or about data coverage. */
export type ChangeClass = "ECONOMIC" | "COVERAGE";

export interface MethodologyRef {
  methodology_id: string;
  data_basis: string;
}

export interface EvidenceRef {
  concept_id: string;
  provider: string;
  provider_series_id: string;
  observation_date: string;
  value: number | null;
}

export interface IntelligenceRelation {
  kind: string;
  target: string;
}

interface IntelligenceEnvelope {
  id: string;
  world: IntelligenceWorld;
  concepts: string[];
  effective_period: string;
  recorded_at: string;
  /** `null` whenever the provider's publication time is not genuinely known. */
  published_at: string | null;
  knowledge_basis: KnowledgeBasis;
  basis: IntelligenceBasis;
  /** Present if and only if `basis === "METHODOLOGY_DERIVED"`. */
  methodology: MethodologyRef | null;
  evidence: EvidenceRef[];
  relations: IntelligenceRelation[];
  limitations: string[];
  contract_version: string;
}

export interface ReleaseProcessedIntelligence extends IntelligenceEnvelope {
  type: "RELEASE_PROCESSED";
  payload: {
    release_name: string;
    provider: string;
    provider_release_id: string;
    scheduled_date: string;
    status: string;
    observation_changes: number;
    new_observations: number;
    revised_observations: number;
  };
}

export interface ObservationChangeIntelligence extends IntelligenceEnvelope {
  type: "OBSERVATION_CHANGE";
  payload: {
    change_type: "NEW" | "REVISED";
    previous_value: number | null;
    new_value: number | null;
    delta: number | null;
    observation_date: string;
    provider: string;
    provider_series_id: string;
    series_title: string | null;
    units: string | null;
  };
}

export interface AnalysisChangeIntelligence extends IntelligenceEnvelope {
  type: "ANALYSIS_CHANGE";
  payload: {
    component: string;
    event_type: string;
    change_class: ChangeClass;
    field: string;
    previous_value: string | null;
    current_value: string | null;
    delta: number | null;
    evaluation_period: string;
  };
}

export interface RatesChangeRef {
  window: string;
  sessions: number;
  available: boolean;
  change_basis_points: number | null;
  from_date: string | null;
  from_value: number | null;
}

/**
 * One observed value on one date. Nothing else -- no coordinate, no
 * colour, no flag for how it should be drawn (#40C).
 */
export interface VisualEvidencePoint {
  observation_date: string;
  value: number;
}

/**
 * The bounded observation series behind an intelligence object, carried
 * INSIDE the object (#40C).
 *
 * This is evidence, not a chart. The backend supplies economic facts in
 * canonical units; this frontend decides how to draw them. A chart
 * assembled from a second query would be a second account of reality
 * and could disagree with the object it sits under.
 *
 * `points` contains only published observations -- a date the provider
 * published nothing for is ABSENT, never interpolated or carried
 * forward -- so `available_sessions` may be less than
 * `requested_sessions`.
 */
export interface TimeSeriesVisualEvidence {
  kind: "TIME_SERIES";
  /** Source-neutral concept identity (#38), never a provider series id. */
  concept_id: string;
  /** Canonical unit of `value`, e.g. "Percent". */
  unit: string;
  requested_sessions: number;
  available_sessions: number;
  /** Chronologically ascending, ending at the object's effective date. */
  points: VisualEvidencePoint[];
}

export interface RatesMovementIntelligence extends IntelligenceEnvelope {
  type: "RATES_MOVEMENT";
  payload: {
    series_title: string;
    latest_value: number | null;
    changes: RatesChangeRef[];
    historical_percentile_rank: number | null;
    historical_magnitude_percentile_rank: number | null;
    historical_observation_count: number;
    /**
     * Additive in #40C and optional: an object built before that
     * increment, or a series with no usable history, simply omits it.
     */
    visual_evidence?: TimeSeriesVisualEvidence | null;
  };
}

export type IntelligenceObject =
  | ReleaseProcessedIntelligence
  | ObservationChangeIntelligence
  | AnalysisChangeIntelligence
  | RatesMovementIntelligence;

export interface IntelligenceListResponse {
  items: IntelligenceObject[];
  total: number;
  limit: number;
  offset: number;
  contract_version: string;
}
