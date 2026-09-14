/**
 * Human-readable labels and visual "tone" for Labor values the backend
 * has already classified -- the Labor sibling of `lib/inflationLabels.ts`,
 * deliberately a separate file/map set rather than a shared generic
 * lookup (two monitors don't yet justify one abstraction, mirroring
 * this project's own repeated "no premature generic framework"
 * precedent -- see docs/architecture/labor-ui-v1.md §45).
 *
 * Tone decision (frozen, docs/architecture/labor-ui-v1.md §8): no
 * directional good/bad or bullish/bearish color-coding anywhere in
 * Labor's own presentation. `STRENGTHENING`/`COOLING`/`STABLE` (and
 * every real `EmploymentState`/`UnemploymentTrendState` value) share
 * ONE neutral tone -- text alone carries the distinction. `MIXED` uses
 * `caution` (the same bucket Inflation's own `MIXED` already uses,
 * since both represent genuine disagreement, not a data problem).
 * `INSUFFICIENT_DATA` uses `unavailable`, matching every other
 * unavailable value in the product. These functions map an
 * already-classified value to display text/styling only -- they never
 * inspect a metric, compare two values, or decide which state applies.
 */
import type {
  EmploymentCondition,
  EmploymentMomentum,
  EmploymentState,
  LaborChangeComponent,
  LaborState,
  UnemploymentTrendState,
} from "../api/labor.types";
import type { Tone } from "./inflationLabels";

const LABOR_STATE_LABELS: Record<LaborState, string> = {
  STRENGTHENING: "Strengthening",
  COOLING: "Cooling",
  STABLE: "Stable",
  MIXED: "Mixed",
  INSUFFICIENT_DATA: "Insufficient data",
};

const LABOR_STATE_TONE: Record<LaborState, Tone> = {
  STRENGTHENING: "neutral",
  COOLING: "neutral",
  STABLE: "neutral",
  MIXED: "caution",
  INSUFFICIENT_DATA: "unavailable",
};

export function laborStateLabel(state: LaborState): string {
  return LABOR_STATE_LABELS[state];
}

export function laborStateTone(state: LaborState): Tone {
  return LABOR_STATE_TONE[state];
}

export function laborStateLabelOrRaw(value: string): string {
  return value in LABOR_STATE_LABELS ? LABOR_STATE_LABELS[value as LaborState] : value;
}

const EMPLOYMENT_STATE_LABELS: Record<EmploymentState, string> = {
  EXPANDING: "Expanding",
  COOLING: "Cooling",
  STABLE: "Stable",
  CONTRACTING: "Contracting",
  RECOVERING: "Recovering",
  INSUFFICIENT_DATA: "Insufficient data",
};

const EMPLOYMENT_STATE_TONE: Record<EmploymentState, Tone> = {
  EXPANDING: "neutral",
  COOLING: "neutral",
  STABLE: "neutral",
  CONTRACTING: "neutral",
  RECOVERING: "neutral",
  INSUFFICIENT_DATA: "unavailable",
};

export function employmentStateLabel(state: EmploymentState): string {
  return EMPLOYMENT_STATE_LABELS[state];
}

export function employmentStateTone(state: EmploymentState): Tone {
  return EMPLOYMENT_STATE_TONE[state];
}

export function employmentStateLabelOrRaw(value: string): string {
  return value in EMPLOYMENT_STATE_LABELS ? EMPLOYMENT_STATE_LABELS[value as EmploymentState] : value;
}

const EMPLOYMENT_CONDITION_LABELS: Record<EmploymentCondition, string> = {
  EXPANDING: "Expanding",
  FLAT: "Flat",
  CONTRACTING: "Contracting",
  INSUFFICIENT_DATA: "Insufficient data",
};

export function employmentConditionLabel(condition: EmploymentCondition): string {
  return EMPLOYMENT_CONDITION_LABELS[condition];
}

export function employmentConditionLabelOrRaw(value: string): string {
  return value in EMPLOYMENT_CONDITION_LABELS ? EMPLOYMENT_CONDITION_LABELS[value as EmploymentCondition] : value;
}

const EMPLOYMENT_MOMENTUM_LABELS: Record<EmploymentMomentum, string> = {
  IMPROVING: "Improving",
  STEADY: "Steady",
  WORSENING: "Worsening",
  INSUFFICIENT_DATA: "Insufficient data",
};

export function employmentMomentumLabel(momentum: EmploymentMomentum): string {
  return EMPLOYMENT_MOMENTUM_LABELS[momentum];
}

export function employmentMomentumLabelOrRaw(value: string): string {
  return value in EMPLOYMENT_MOMENTUM_LABELS ? EMPLOYMENT_MOMENTUM_LABELS[value as EmploymentMomentum] : value;
}

const UNEMPLOYMENT_TREND_STATE_LABELS: Record<UnemploymentTrendState, string> = {
  IMPROVING: "Improving",
  DETERIORATING: "Deteriorating",
  STABLE: "Stable",
  INSUFFICIENT_DATA: "Insufficient data",
};

const UNEMPLOYMENT_TREND_STATE_TONE: Record<UnemploymentTrendState, Tone> = {
  IMPROVING: "neutral",
  DETERIORATING: "neutral",
  STABLE: "neutral",
  INSUFFICIENT_DATA: "unavailable",
};

export function unemploymentStateLabel(state: UnemploymentTrendState): string {
  return UNEMPLOYMENT_TREND_STATE_LABELS[state];
}

export function unemploymentStateTone(state: UnemploymentTrendState): Tone {
  return UNEMPLOYMENT_TREND_STATE_TONE[state];
}

export function unemploymentStateLabelOrRaw(value: string): string {
  return value in UNEMPLOYMENT_TREND_STATE_LABELS ? UNEMPLOYMENT_TREND_STATE_LABELS[value as UnemploymentTrendState] : value;
}

export const LABOR_CHANGE_COMPONENT_LABELS: Record<LaborChangeComponent, string> = {
  LABOR: "Labor",
  EMPLOYMENT: "Employment",
  UNEMPLOYMENT: "Unemployment",
};

export function laborChangeComponentLabelOrRaw(value: string): string {
  return value in LABOR_CHANGE_COMPONENT_LABELS ? LABOR_CHANGE_COMPONENT_LABELS[value as LaborChangeComponent] : value;
}

const LABOR_CHANGE_FIELD_LABELS: Record<string, string> = {
  state: "State",
  condition: "Condition",
  momentum: "Momentum",
  current_3m_avg_jobs: "Current 3M avg",
  prior_3m_avg_jobs: "Prior 3M avg",
  momentum_delta_jobs: "Momentum delta",
  current_3m_avg: "Current 3M avg",
  prior_year_3m_avg: "Prior-year 3M avg",
  delta_pp: "Delta",
};

export function laborChangeFieldLabel(field: string): string {
  return LABOR_CHANGE_FIELD_LABELS[field] ?? field;
}

/**
 * A field is "job-count shaped" (needs comma-grouped `formatJobs`,
 * never `formatPercent`) exactly when it belongs to the Employment
 * section's own three numeric metrics -- see
 * docs/architecture/labor-ui-v1.md §15/§16. Unemployment's own three
 * numeric fields (`current_3m_avg`/`prior_year_3m_avg`/`delta_pp`) are
 * percentage-point shaped instead and are NOT in this set.
 */
const JOB_COUNT_FIELDS = new Set(["current_3m_avg_jobs", "prior_3m_avg_jobs", "momentum_delta_jobs"]);

export function isJobCountField(field: string): boolean {
  return JOB_COUNT_FIELDS.has(field);
}

const PERCENTAGE_POINT_DELTA_FIELDS = new Set(["delta_pp"]);

export function isPercentagePointDeltaField(field: string): boolean {
  return PERCENTAGE_POINT_DELTA_FIELDS.has(field);
}
