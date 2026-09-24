/**
 * Structured Intelligence fixtures for the Rates world (Increment #52B).
 *
 * Shaped from the live `/api/v1/intelligence?world=rates` response
 * captured 2026-09-24 — six `RATES_MOVEMENT` objects, one per ingested
 * Treasury series. Nothing here computes anything: the limitation
 * strings in particular are the backend's own words, reproduced
 * verbatim, because the page renders them verbatim and a paraphrase in
 * the fixture would let a paraphrase in the product pass unnoticed.
 */
import type { IntelligenceListResponse, RatesMovementIntelligence } from "../../api/intelligence.types";

/** Verbatim from the live response. The first one is the load-bearing one. */
export const RATES_MOVEMENT_LIMITATIONS: ReadonlyArray<string> = [
  "Carries no significance claim: rates_v1.0 defines no notability threshold, so this reports the movement and its own historical position, not that the movement matters.",
  "Change windows are counted in trading SESSIONS, never calendar days.",
];

export function buildRatesMovement(
  overrides: Partial<RatesMovementIntelligence> = {},
): RatesMovementIntelligence {
  return {
    id: "rates:UST_NOMINAL_10Y:2026-09-18",
    type: "RATES_MOVEMENT",
    world: "rates",
    concepts: ["UST_NOMINAL_10Y"],
    effective_period: "2026-09-18",
    recorded_at: "2026-09-20T00:04:54.461189Z",
    published_at: null,
    knowledge_basis: "OBSERVED",
    basis: "METHODOLOGY_DERIVED",
    methodology: { methodology_id: "rates_v1.0", data_basis: "latest_published_data" },
    evidence: [
      {
        concept_id: "UST_NOMINAL_10Y",
        provider: "TREASURY",
        provider_series_id: "UST_NOMINAL_10Y",
        observation_date: "2026-09-18",
        value: 5.01,
      },
    ],
    relations: [
      { kind: "CONCERNS_CONCEPT", target: "UST_NOMINAL_10Y" },
      { kind: "AFFECTS_WORLD", target: "rates" },
    ],
    limitations: [...RATES_MOVEMENT_LIMITATIONS],
    contract_version: "intelligence_v1",
    payload: {
      series_title: "10-Year Treasury Par Yield (Nominal)",
      latest_value: 5.01,
      changes: [
        {
          window: "1_SESSION",
          sessions: 1,
          available: true,
          change_basis_points: 7.0,
          from_date: "2026-09-17",
          from_value: 4.94,
        },
      ],
      historical_percentile_rank: 0.566372,
      historical_magnitude_percentile_rank: 0.39823,
      historical_observation_count: 113,
    },
    ...overrides,
  };
}

/**
 * The six objects the live API returns for `world=rates`, in the order
 * it returns them — which is NOT the order the page shows them in. The
 * page applies `homepage_presentation_v1.0`'s ordering, and a fixture
 * that arrived pre-sorted could not prove that.
 */
export function buildRatesMovementList(
  overrides: Partial<IntelligenceListResponse> = {},
): IntelligenceListResponse {
  const series: ReadonlyArray<[string, string, number]> = [
    ["UST_REAL_10Y", "10-Year Treasury Par Real Yield (TIPS)", 2.68],
    ["UST_REAL_5Y", "5-Year Treasury Par Real Yield (TIPS)", 2.55],
    ["UST_NOMINAL_10Y", "10-Year Treasury Par Yield (Nominal)", 5.01],
    ["UST_NOMINAL_2Y", "2-Year Treasury Par Yield (Nominal)", 4.76],
    ["UST_NOMINAL_30Y", "30-Year Treasury Par Yield (Nominal)", 5.34],
    ["UST_NOMINAL_5Y", "5-Year Treasury Par Yield (Nominal)", 4.86],
  ];

  const items = series.map(([conceptId, title, value]) =>
    buildRatesMovement({
      id: `rates:${conceptId}:2026-09-18`,
      concepts: [conceptId],
      evidence: [
        {
          concept_id: conceptId,
          provider: "TREASURY",
          provider_series_id: conceptId,
          observation_date: "2026-09-18",
          value,
        },
      ],
      payload: { ...buildRatesMovement().payload, series_title: title, latest_value: value },
    }),
  );

  return {
    items,
    total: items.length,
    limit: 100,
    offset: 0,
    contract_version: "intelligence_v1",
    ...overrides,
  };
}
