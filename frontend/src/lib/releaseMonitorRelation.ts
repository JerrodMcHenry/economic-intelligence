/**
 * CANONICAL MONITOR RELATION -- whether a release's own mapped series
 * are actually consumed by a canonical EI monitor's calculation.
 * Frozen by docs/product/overview-attention-model-v1.md §3A, as a
 * deliberate correction of an earlier draft that conflated this with
 * `lib/releasePresentation.ts`'s `releaseCategory()` -- a broad,
 * editorial DISPLAY grouping that is honest as a label but was never
 * verified against which series a release actually feeds. The two
 * must never be conflated again: `releaseCategory()` stays exactly
 * what it always was (a `/releases` display tag); this module answers
 * a narrower, different question ("does this release's data reach a
 * monitor's canonical calculation") and only this module may answer
 * it.
 *
 * `CANONICAL_MONITOR_RELEASE_IDS` restates, as a small frontend
 * constant, a fact already true and committed in the backend's own
 * seeded release-to-series mapping data migrations -- verified
 * directly by inspection, not guessed:
 *   - alembic/versions/cd476d227f99_seed_cpi_and_personal_income_and_.py:
 *     CURATED_MAPPINGS = {"10": ["CPIAUCSL", "CPILFESL"], "54": ["PCEPI", "PCEPILFE"]}
 *   - alembic/versions/09f4c0959e9f_seed_employment_situation_release_.py:
 *     CURATED_MAPPINGS = {"50": ["PAYEMS", "UNRATE"]}
 * JOLTS ("192"), GDP ("53"), and Advance Monthly Retail Sales ("9")
 * appear in NEITHER seeded migration -- zero mapped-series rows exist
 * for any of the three. JOLTS in particular is deferred
 * from `labor_v1.0` and must never be attributed to the Labor monitor
 * despite its `releaseCategory()` display tag reading "Labor".
 *
 * This is not new backend information and not an unsupported
 * inference -- it mirrors the identical, already-shipped pattern
 * `components/labor/RelevantRelease.tsx` already uses for Employment
 * Situation alone (`EMPLOYMENT_SITUATION_PROVIDER_RELEASE_ID = "50"`).
 * Zero backend change; this is a presentation/navigation restatement
 * only, deliberately not an extensible taxonomy framework -- exactly
 * two fixed sets, not a generic n-domain registry.
 */
export const CANONICAL_MONITOR_RELEASE_IDS = {
  INFLATION: new Set<string>(["10", "54"]), // Consumer Price Index; Personal Income and Outlays
  LABOR: new Set<string>(["50"]), // Employment Situation
} as const;

export type CanonicalMonitorDomain = "INFLATION" | "LABOR";

/** Which canonical monitor, if any, a release's own mapped series feed
 * -- `null` for a release with no canonical monitor relation (JOLTS,
 * GDP, Advance Retail Sales, or any future uncurated release). Never
 * derived from `releaseCategory()`. */
export function canonicalMonitorDomain(providerReleaseId: string): CanonicalMonitorDomain | null {
  if (CANONICAL_MONITOR_RELEASE_IDS.INFLATION.has(providerReleaseId)) return "INFLATION";
  if (CANONICAL_MONITOR_RELEASE_IDS.LABOR.has(providerReleaseId)) return "LABOR";
  return null;
}

/** The frozen per-release navigation rule (docs/product/overview-attention-model-v1.md
 * §17's exact table): a release with a canonical monitor relation
 * points at that monitor's own page; a release with none still gets an
 * honest next action -- the release calendar -- never a hard dead end
 * and never a fabricated deep link. */
export function releaseMonitorCta(providerReleaseId: string): { label: string; to: string } {
  const domain = canonicalMonitorDomain(providerReleaseId);
  if (domain === "INFLATION") return { label: "View Inflation →", to: "/inflation" };
  if (domain === "LABOR") return { label: "View Labor →", to: "/labor" };
  return { label: "View Releases →", to: "/releases" };
}
