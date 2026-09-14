/**
 * Curated, static explanation content for the release calendar.
 * `SCHEDULED_STATUS`/`PAST_DUE_STATUS` deliberately match the frozen
 * spec's own trust language (see
 * docs/architecture/release-intelligence-v1.md #13 and the Increment
 * #17B journal entry) -- PAST_DUE must never sound like "published."
 * Release-type explanations are keyed by the backend's own stable
 * `provider_release_id`, exactly the same identity
 * lib/releasePresentation.ts already keys its short-label/category map
 * by -- never by matching on `name` text.
 */
import type { ScheduleStatus } from "../../api/releases.types";
import type { Explanation } from "./types";

export const ECONOMIC_RELEASE: Explanation = {
  id: "releases.economic-release",
  title: "Economic release",
  definition: "A recurring, scheduled publication of official economic data, such as a monthly inflation or employment report.",
  whyItMatters:
    "Investors, economists, and policymakers watch release calendars because these are the moments new economic information officially becomes available.",
};

export const SCHEDULED_DATE: Explanation = {
  id: "releases.scheduled-date",
  title: "Scheduled date",
  definition: "The calendar date Economic Intelligence's persisted release calendar has on file for this release, sourced from FRED.",
  whyItMatters:
    "It tells you when a release is expected, but a scheduled date on its own does not confirm the release actually happened or that new data has arrived.",
  sourceNote: "Source: FRED release calendar",
};

const SCHEDULE_STATUS_EXPLANATIONS: Record<ScheduleStatus, Explanation> = {
  SCHEDULED: {
    id: "releases.status-scheduled",
    title: "Scheduled",
    definition: "The release is scheduled for this date according to Economic Intelligence's persisted release calendar.",
  },
  PAST_DUE: {
    id: "releases.status-past-due",
    title: "Past due",
    definition:
      "The scheduled release date has passed. This status does not confirm that new data has been published, ingested, or incorporated into Economic Intelligence analysis.",
  },
};

/** The curated explanation for a canonical `ScheduleStatus` value --
 * looked up by the backend's own already-derived value, never used to
 * derive one. */
export function scheduleStatusExplanation(status: ScheduleStatus): Explanation {
  return SCHEDULE_STATUS_EXPLANATIONS[status];
}

const RELEASE_TYPE_EXPLANATIONS: Record<string, Explanation> = {
  "10": {
    id: "releases.type-cpi",
    title: "Consumer Price Index (CPI)",
    definition: "Measures changes in prices paid by consumers for a broad basket of goods and services.",
    whyItMatters: "One of the most widely followed measures of inflation.",
    sourceNote: "Source: FRED release calendar",
  },
  "54": {
    id: "releases.type-personal-income-and-outlays",
    title: "Personal Income and Outlays",
    definition:
      "A monthly report on personal income, consumer spending, and the PCE price index -- the inflation measure the Federal Reserve's 2% objective is defined against.",
    whyItMatters:
      "It's the source of the PCE price data Economic Intelligence uses for its primary inflation target comparison, alongside a read on consumer income and spending.",
    sourceNote: "Source: FRED release calendar",
  },
  "50": {
    id: "releases.type-employment-situation",
    title: "Employment Situation",
    definition: "A monthly labor-market report containing major measures such as payroll employment and the unemployment rate.",
    whyItMatters: "It helps show whether the labor market is strengthening or weakening.",
    sourceNote: "Source: FRED release calendar",
  },
  "192": {
    id: "releases.type-jolts",
    title: "Job Openings and Labor Turnover Survey (JOLTS)",
    definition: "Tracks job openings, hiring, and worker separations.",
    whyItMatters: "It provides another view of labor demand and how easily workers are moving between jobs.",
    sourceNote: "Source: FRED release calendar",
  },
  "53": {
    id: "releases.type-gdp",
    title: "Gross Domestic Product (GDP)",
    definition: "Measures the value of goods and services produced in the economy.",
    whyItMatters: "It is one of the broadest measures of economic activity.",
    sourceNote: "Source: FRED release calendar",
  },
  "9": {
    id: "releases.type-advance-retail-sales",
    title: "Advance Monthly Sales for Retail and Food Services",
    definition: "An early estimate of consumer spending at retail and food-service businesses, published before more complete source data is available.",
    whyItMatters:
      "Because it's released quickly, it's an early signal of consumer spending trends -- though as an early estimate, it's sometimes revised in later reports.",
    sourceNote: "Source: FRED release calendar",
  },
};

/** The curated explanation for a curated V1 release, keyed by the
 * backend's own stable `provider_release_id` -- `null` for any release
 * not in this map (never fabricated). */
export function releaseTypeExplanation(providerReleaseId: string): Explanation | null {
  return RELEASE_TYPE_EXPLANATIONS[providerReleaseId] ?? null;
}
