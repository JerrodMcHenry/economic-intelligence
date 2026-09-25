/**
 * Frontend-only presentation aids for the six curated V1 releases:
 * an optional shorter display label, and an economic-category tag.
 *
 * These are UI display decisions, not canonical economic
 * classification, not a release-series mapping, not AI-generated, and
 * not #18 architecture. #18's eventual release-to-series mapping is a
 * backend-owned concept serving a completely different purpose --
 * proving observation availability against specific series so a
 * monitor can be recomputed. This map does none of that: it decides
 * only which short label and category tag one release shows in a
 * list. It is never sent to the backend, never persisted, and never
 * used as a lookup key anywhere else -- every entry here is keyed by
 * the backend's own stable `provider_release_id`, and the canonical
 * `name` from the API is always what's rendered for any release not
 * in this map (including any release curated later that this map
 * hasn't been updated for yet).
 */
import type { ReleaseOccurrenceItem } from "../api/releases.types";

interface ReleasePresentation {
  shortLabel?: string;
  category: string;
}

const RELEASE_PRESENTATION: Record<string, ReleasePresentation> = {
  cpi: { category: "Inflation" }, // Consumer Price Index
  pio: { category: "Inflation / Consumer" }, // Personal Income and Outlays
  empsit: { category: "Labor" }, // Employment Situation
  "192": { shortLabel: "JOLTS", category: "Labor" }, // Job Openings and Labor Turnover Survey
  "53": { shortLabel: "GDP", category: "Growth" }, // Gross Domestic Product
  "9": { shortLabel: "Advance Retail Sales", category: "Consumer" }, // Advance Monthly Sales for Retail and Food Services
};

/** The label to display for a release -- shortened only for the
 * handful of curated releases whose canonical name is long enough to
 * genuinely benefit (see `RELEASE_PRESENTATION`); every other release
 * (including any not in this map at all) shows its real, canonical
 * `name` unchanged. */
export function releaseDisplayLabel(release: Pick<ReleaseOccurrenceItem, "provider_release_id" | "name">): string {
  return RELEASE_PRESENTATION[release.provider_release_id]?.shortLabel ?? release.name;
}

/** Whether `releaseDisplayLabel` actually shortened this release's
 * name -- callers use this to decide whether the full canonical name
 * still needs to be surfaced (accessibly, visibly, or both). */
export function isShortenedLabel(release: Pick<ReleaseOccurrenceItem, "provider_release_id" | "name">): boolean {
  return releaseDisplayLabel(release) !== release.name;
}

/** A presentation-only economic-area tag, or `null` for any release
 * not in the curated V1 map -- never fabricated, never inferred from
 * the release's name or any other field. */
export function releaseCategory(release: Pick<ReleaseOccurrenceItem, "provider_release_id">): string | null {
  return RELEASE_PRESENTATION[release.provider_release_id]?.category ?? null;
}
