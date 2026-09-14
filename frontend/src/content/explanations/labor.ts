/**
 * Curated, static explanation content for the Labor Market Monitor.
 * Grounded in research/labor_momentum/LABOR_V1_FROZEN_METHODOLOGY.md
 * (frozen) -- every state description below matches that document's
 * own condition/momentum/agreement tables (§3-§7) exactly in substance.
 * This file changes no methodology semantics -- it only writes
 * definitions for concepts the backend already computes
 * deterministically. Exact deadband numbers (50,000 jobs / 0.2
 * percentage points) are deliberately NOT reproduced here -- content
 * describes the methodology conceptually (what is compared, over what
 * window), never the executable threshold logic itself (see
 * docs/architecture/labor-ui-v1.md §13's own "GOOD/BAD" distinction).
 */
import type {
  EmploymentCondition,
  EmploymentMomentum,
  EmploymentState,
  LaborState,
  UnemploymentTrendState,
} from "../../api/labor.types";
import type { Explanation } from "./types";

export const LABOR_MONITOR: Explanation = {
  id: "labor.labor-monitor",
  title: "Labor Monitor",
  definition:
    "Economic Intelligence's deterministic read on U.S. labor market conditions, combining payroll employment trends with the unemployment rate's own trend into one overall Labor state.",
  whyItMatters:
    "The labor market is one of the two mandates the Federal Reserve weighs alongside inflation -- a clear, sourced read on hiring and unemployment trends helps interpret the broader economic picture without waiting for commentary.",
  sourceNote: "Methodology: labor_v1.0",
};

export const EMPLOYMENT: Explanation = {
  id: "labor.employment",
  title: "Employment",
  definition:
    "The payroll employment side of the Labor Monitor, based on Total Nonfarm Payrolls (PAYEMS) -- how many jobs the economy is adding or losing, and whether that pace is improving or worsening.",
  whyItMatters:
    "Payroll employment is one of the most closely watched monthly economic releases, both for its own sake and as an early read on broader economic momentum.",
  sourceNote: "Series: PAYEMS · Methodology: labor_v1.0",
};

export const UNEMPLOYMENT: Explanation = {
  id: "labor.unemployment",
  title: "Unemployment trend",
  definition:
    "The unemployment-rate side of the Labor Monitor, based on the civilian Unemployment Rate (UNRATE) -- comparing its recent average against its own average from a year earlier.",
  whyItMatters:
    "Comparing against a year ago, rather than the prior month, smooths out normal month-to-month noise and shows whether the labor market is trending looser or tighter over a longer horizon.",
  sourceNote: "Series: UNRATE · Methodology: labor_v1.0",
};

export const EMPLOYMENT_CONDITION_CONCEPT: Explanation = {
  id: "labor.employment-condition-concept",
  title: "Employment condition",
  definition:
    "Whether recent average monthly payroll growth is positive, negative, or close to flat, based on the average of the three most recent monthly payroll changes.",
  whyItMatters:
    "Condition answers 'is the level of hiring currently positive or negative' -- a separate question from whether that pace is getting better or worse (see Momentum).",
  sourceNote: "Methodology: labor_v1.0",
};

export const EMPLOYMENT_MOMENTUM_CONCEPT: Explanation = {
  id: "labor.employment-momentum-concept",
  title: "Employment momentum",
  definition:
    "Whether recent payroll growth is accelerating or decelerating, based on comparing the most recent three-month average monthly change with the three-month average immediately before it.",
  whyItMatters:
    "A labor market can be adding jobs (positive condition) while that pace is slowing (worsening momentum), or losing jobs while the pace of loss is easing (improving momentum) -- momentum captures that direction-of-change separately from the current level.",
  sourceNote: "Methodology: labor_v1.0",
};

const LABOR_STATE_EXPLANATIONS: Record<LaborState, Explanation> = {
  STRENGTHENING: {
    id: "labor.state-strengthening",
    title: "Strengthening",
    definition: "Employment is expanding with improving momentum, and the unemployment rate is trending down from a year earlier.",
    whyItMatters: "Both the payroll and unemployment-rate sides of the labor market are pointing the same, favorable direction.",
  },
  COOLING: {
    id: "labor.state-cooling",
    title: "Cooling",
    definition:
      "Employment is either contracting or expanding with worsening momentum, and the unemployment rate is trending up from a year earlier.",
    whyItMatters: "Both sides of the labor market are pointing the same, less-favorable direction.",
  },
  STABLE: {
    id: "labor.state-stable",
    title: "Stable",
    definition: "Employment is essentially flat and the unemployment rate is essentially unchanged from a year earlier.",
    whyItMatters: "Neither side of the labor market is showing a meaningful move in either direction.",
  },
  MIXED: {
    id: "labor.state-mixed",
    title: "Mixed",
    definition:
      "Employment and unemployment are not telling a consistent story this month -- Economic Intelligence classifies that combination as Mixed rather than forcing it into Strengthening, Cooling, or Stable.",
    whyItMatters:
      "Mixed is a real, distinct classification, not a data gap -- it means the payroll and unemployment-rate sides are sending different signals, which is itself useful information. This includes every case where payrolls are recovering from contraction (see Recovering below): a labor market still factually losing jobs is never classified Strengthening just because the pace of loss is improving.",
  },
  INSUFFICIENT_DATA: {
    id: "labor.state-insufficient-data",
    title: "Insufficient data",
    definition: "Economic Intelligence does not have all the persisted observations required to calculate this state.",
    whyItMatters:
      "This is a data-availability fact, not an economic reading -- it's shown so it's never mistaken for a direction like Strengthening, Cooling, or Stable.",
  },
};

export function laborStateExplanation(state: LaborState): Explanation {
  return LABOR_STATE_EXPLANATIONS[state];
}

const EMPLOYMENT_STATE_EXPLANATIONS: Record<EmploymentState, Explanation> = {
  EXPANDING: {
    id: "labor.employment-state-expanding",
    title: "Expanding",
    definition: "Payroll employment is growing at a meaningful positive pace, with steady or improving momentum.",
  },
  COOLING: {
    id: "labor.employment-state-cooling",
    title: "Cooling",
    definition: "Payroll employment is still growing, but the pace of growth is worsening.",
  },
  STABLE: {
    id: "labor.employment-state-stable",
    title: "Stable",
    definition: "Payroll employment is essentially flat, regardless of momentum.",
  },
  CONTRACTING: {
    id: "labor.employment-state-contracting",
    title: "Contracting",
    definition: "Payroll employment is shrinking, and the pace of loss is steady or worsening -- not yet improving.",
  },
  RECOVERING: {
    id: "labor.employment-state-recovering",
    title: "Recovering",
    definition: "Payroll employment is still shrinking, but the pace of loss is improving.",
    whyItMatters:
      "Recovering means employment is still, factually, contracting -- it is deliberately kept distinct from Expanding so an improving-but-still-negative trend is never overstated as genuine growth.",
  },
  INSUFFICIENT_DATA: {
    id: "labor.employment-state-insufficient-data",
    title: "Insufficient data",
    definition: "Economic Intelligence does not have all the persisted PAYEMS observations required to calculate this state.",
  },
};

export function employmentStateExplanation(state: EmploymentState): Explanation {
  return EMPLOYMENT_STATE_EXPLANATIONS[state];
}

const EMPLOYMENT_CONDITION_EXPLANATIONS: Record<EmploymentCondition, Explanation> = {
  EXPANDING: { id: "labor.condition-expanding", title: "Expanding", definition: "Recent average monthly payroll growth is meaningfully positive." },
  FLAT: { id: "labor.condition-flat", title: "Flat", definition: "Recent average monthly payroll growth is close to zero, in either direction." },
  CONTRACTING: { id: "labor.condition-contracting", title: "Contracting", definition: "Recent average monthly payroll growth is meaningfully negative." },
  INSUFFICIENT_DATA: {
    id: "labor.condition-insufficient-data",
    title: "Insufficient data",
    definition: "Economic Intelligence does not have the persisted PAYEMS observations required to calculate condition.",
  },
};

export function employmentConditionExplanation(condition: EmploymentCondition): Explanation {
  return EMPLOYMENT_CONDITION_EXPLANATIONS[condition];
}

const EMPLOYMENT_MOMENTUM_EXPLANATIONS: Record<EmploymentMomentum, Explanation> = {
  IMPROVING: { id: "labor.momentum-improving", title: "Improving", definition: "The recent three-month average payroll change is meaningfully better than the three months before it." },
  STEADY: { id: "labor.momentum-steady", title: "Steady", definition: "The recent three-month average payroll change is close to the three months before it, in either direction." },
  WORSENING: { id: "labor.momentum-worsening", title: "Worsening", definition: "The recent three-month average payroll change is meaningfully worse than the three months before it." },
  INSUFFICIENT_DATA: {
    id: "labor.momentum-insufficient-data",
    title: "Insufficient data",
    definition: "Economic Intelligence does not have the persisted PAYEMS observations required to calculate momentum.",
  },
};

export function employmentMomentumExplanation(momentum: EmploymentMomentum): Explanation {
  return EMPLOYMENT_MOMENTUM_EXPLANATIONS[momentum];
}

const UNEMPLOYMENT_TREND_EXPLANATIONS: Record<UnemploymentTrendState, Explanation> = {
  IMPROVING: { id: "labor.unemployment-improving", title: "Improving", definition: "The unemployment rate's recent three-month average is meaningfully lower than its average from a year earlier." },
  DETERIORATING: { id: "labor.unemployment-deteriorating", title: "Deteriorating", definition: "The unemployment rate's recent three-month average is meaningfully higher than its average from a year earlier." },
  STABLE: { id: "labor.unemployment-stable", title: "Stable", definition: "The unemployment rate's recent three-month average is close to its average from a year earlier." },
  INSUFFICIENT_DATA: {
    id: "labor.unemployment-insufficient-data",
    title: "Insufficient data",
    definition: "Economic Intelligence does not have the persisted UNRATE observations required to calculate this trend.",
  },
};

export function unemploymentTrendExplanation(state: UnemploymentTrendState): Explanation {
  return UNEMPLOYMENT_TREND_EXPLANATIONS[state];
}
