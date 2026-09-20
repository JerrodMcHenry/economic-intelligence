/**
 * Deterministic `rates_v1.0` fixtures for the Rates Intelligence UI
 * tests (Increment #30).
 *
 * Values mirror a real response observed from the live backend, so a
 * test asserting "25 bp" is asserting against a shape the API genuinely
 * produces. Every builder takes overrides, so an individual test can
 * express exactly the condition it cares about (unavailable, no shared
 * date, insufficient history) without restating a whole payload.
 */

import type {
  ChangeWindow,
  CurveSpread,
  DerivedProvenance,
  HistoricalContext,
  InflationCompensation,
  RateChange,
  RateLevel,
  RatesMonitorResult,
  SourceProvenance,
} from "../../api/rates.types";

export function buildSourceProvenance(overrides: Partial<SourceProvenance> = {}): SourceProvenance {
  return {
    provider: "TREASURY",
    dataset: "daily_treasury_yield_curve",
    series_id: "UST_NOMINAL_10Y",
    observation_date: "2026-09-18",
    source_url:
      "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve",
    retrieved_at: "2026-09-19T17:04:54.461189-07:00",
    revision_count: 0,
    last_revised_at: null,
    ...overrides,
  };
}

export function buildDerivedProvenance(overrides: Partial<DerivedProvenance> = {}): DerivedProvenance {
  return {
    methodology_id: "rates_v1.0",
    calculation: "UST_NOMINAL_10Y - UST_NOMINAL_2Y, in basis points, on one exactly-shared observation date",
    input_series_ids: ["UST_NOMINAL_10Y", "UST_NOMINAL_2Y"],
    input_observation_date: "2026-09-18",
    calculated_at: "2026-09-20T01:12:42.117367Z",
    ...overrides,
  };
}

export function buildRateChange(window: ChangeWindow, overrides: Partial<RateChange> = {}): RateChange {
  const sessions = { "1_SESSION": 1, "5_SESSIONS": 5, "21_SESSIONS": 21, "63_SESSIONS": 63 }[window];
  return {
    window,
    sessions,
    available: true,
    change_basis_points: 7.0,
    from_date: "2026-09-17",
    from_value: 4.94,
    to_date: "2026-09-18",
    to_value: 5.01,
    ...overrides,
  };
}

export function buildAllChanges(overrides: Partial<RateChange> = {}): RateChange[] {
  return (["1_SESSION", "5_SESSIONS", "21_SESSIONS", "63_SESSIONS"] as ChangeWindow[]).map((window) =>
    buildRateChange(window, overrides),
  );
}

export function buildHistoricalContext(overrides: Partial<HistoricalContext> = {}): HistoricalContext {
  return {
    available: true,
    window: "5_SESSIONS",
    observation_count: 113,
    history_start_date: "2026-04-08",
    history_end_date: "2026-09-18",
    percentile_rank: 0.566372,
    magnitude_percentile_rank: 0.39823,
    minimum_change_basis_points: -19.0,
    maximum_change_basis_points: 21.0,
    ...overrides,
  };
}

export function buildRateLevel(overrides: Partial<RateLevel> = {}): RateLevel {
  return {
    series_id: "UST_NOMINAL_10Y",
    title: "10-Year Treasury Par Yield (Nominal)",
    units: "Percent",
    kind: "SOURCE_OBSERVATION",
    available: true,
    latest_date: "2026-09-18",
    latest_value: 5.01,
    changes: buildAllChanges(),
    historical_context: buildHistoricalContext(),
    provenance: buildSourceProvenance(),
    ...overrides,
  };
}

export function buildCurveSpread(overrides: Partial<CurveSpread> = {}): CurveSpread {
  return {
    spread_id: "2s10s",
    title: "10-Year minus 2-Year",
    kind: "DERIVED",
    available: true,
    observation_date: "2026-09-18",
    spread_basis_points: 25.0,
    long_series_id: "UST_NOMINAL_10Y",
    short_series_id: "UST_NOMINAL_2Y",
    long_value: 5.01,
    short_value: 4.76,
    unavailable_reason: null,
    changes: buildAllChanges({ change_basis_points: -2.0, from_value: 0.27, to_value: 0.25 }),
    historical_context: buildHistoricalContext(),
    provenance: buildDerivedProvenance(),
    ...overrides,
  };
}

export function buildInflationCompensation(overrides: Partial<InflationCompensation> = {}): InflationCompensation {
  return {
    maturity: "10Y",
    title: "10-Year market-implied inflation compensation",
    kind: "DERIVED",
    available: true,
    observation_date: "2026-09-18",
    compensation_percent: 2.33,
    nominal_series_id: "UST_NOMINAL_10Y",
    real_series_id: "UST_REAL_10Y",
    nominal_value: 5.01,
    real_value: 2.68,
    unavailable_reason: null,
    changes: buildAllChanges({ change_basis_points: 0.0, from_value: 2.33, to_value: 2.33 }),
    historical_context: buildHistoricalContext(),
    provenance: buildDerivedProvenance({
      calculation:
        "UST_NOMINAL_10Y - UST_REAL_10Y, in percentage points, on one exactly-shared observation date; market-implied compensation, not an inflation forecast",
      input_series_ids: ["UST_NOMINAL_10Y", "UST_REAL_10Y"],
    }),
    ...overrides,
  };
}

/** A complete, fully-populated response mirroring the live shape. */
export function buildRatesMonitor(overrides: Partial<RatesMonitorResult> = {}): RatesMonitorResult {
  return {
    methodology_id: "rates_v1.0",
    data_basis: "latest_published_data",
    provider: "TREASURY",
    attribution: "Source: U.S. Department of the Treasury (Daily Treasury Par Yield Curve Rates).",
    as_of_date: "2026-09-18",
    nominal_curve: [
      buildRateLevel({
        series_id: "UST_NOMINAL_2Y",
        title: "2-Year Treasury Par Yield (Nominal)",
        latest_value: 4.76,
        changes: buildAllChanges({ change_basis_points: 9.0, from_value: 4.67, to_value: 4.76 }),
        provenance: buildSourceProvenance({ series_id: "UST_NOMINAL_2Y" }),
      }),
      buildRateLevel({
        series_id: "UST_NOMINAL_5Y",
        title: "5-Year Treasury Par Yield (Nominal)",
        latest_value: 4.86,
        provenance: buildSourceProvenance({ series_id: "UST_NOMINAL_5Y" }),
      }),
      buildRateLevel({ series_id: "UST_NOMINAL_10Y", latest_value: 5.01 }),
      buildRateLevel({
        series_id: "UST_NOMINAL_30Y",
        title: "30-Year Treasury Par Yield (Nominal)",
        latest_value: 5.34,
        provenance: buildSourceProvenance({ series_id: "UST_NOMINAL_30Y" }),
      }),
    ],
    real_curve: [
      buildRateLevel({
        series_id: "UST_REAL_5Y",
        title: "5-Year Treasury Par Real Yield (TIPS)",
        latest_value: 2.55,
        provenance: buildSourceProvenance({ series_id: "UST_REAL_5Y", dataset: "daily_treasury_real_yield_curve" }),
      }),
      buildRateLevel({
        series_id: "UST_REAL_10Y",
        title: "10-Year Treasury Par Real Yield (TIPS)",
        latest_value: 2.68,
        provenance: buildSourceProvenance({ series_id: "UST_REAL_10Y", dataset: "daily_treasury_real_yield_curve" }),
      }),
    ],
    curve_spreads: [
      buildCurveSpread(),
      buildCurveSpread({
        spread_id: "2s30s",
        title: "30-Year minus 2-Year",
        spread_basis_points: 58.0,
        long_series_id: "UST_NOMINAL_30Y",
        long_value: 5.34,
        provenance: buildDerivedProvenance({
          calculation: "UST_NOMINAL_30Y - UST_NOMINAL_2Y, in basis points, on one exactly-shared observation date",
          input_series_ids: ["UST_NOMINAL_30Y", "UST_NOMINAL_2Y"],
        }),
      }),
    ],
    inflation_compensation: [
      buildInflationCompensation({
        maturity: "5Y",
        title: "5-Year market-implied inflation compensation",
        compensation_percent: 2.31,
        nominal_series_id: "UST_NOMINAL_5Y",
        real_series_id: "UST_REAL_5Y",
        nominal_value: 4.86,
        real_value: 2.55,
      }),
      buildInflationCompensation(),
    ],
    ...overrides,
  };
}

/** A response from an environment where nothing has been ingested yet. */
export function buildEmptyRatesMonitor(): RatesMonitorResult {
  const unavailableLevel = (seriesId: string, title: string): RateLevel =>
    buildRateLevel({
      series_id: seriesId,
      title,
      available: false,
      latest_date: null,
      latest_value: null,
      changes: buildAllChanges({ available: false, change_basis_points: null, from_value: null, to_value: null }),
      historical_context: buildHistoricalContext({
        available: false,
        observation_count: 0,
        history_start_date: null,
        percentile_rank: null,
        magnitude_percentile_rank: null,
      }),
      provenance: null,
    });

  return buildRatesMonitor({
    as_of_date: null,
    nominal_curve: [
      unavailableLevel("UST_NOMINAL_2Y", "2-Year Treasury Par Yield (Nominal)"),
      unavailableLevel("UST_NOMINAL_5Y", "5-Year Treasury Par Yield (Nominal)"),
      unavailableLevel("UST_NOMINAL_10Y", "10-Year Treasury Par Yield (Nominal)"),
      unavailableLevel("UST_NOMINAL_30Y", "30-Year Treasury Par Yield (Nominal)"),
    ],
    real_curve: [
      unavailableLevel("UST_REAL_5Y", "5-Year Treasury Par Real Yield (TIPS)"),
      unavailableLevel("UST_REAL_10Y", "10-Year Treasury Par Real Yield (TIPS)"),
    ],
    curve_spreads: [
      buildCurveSpread({
        available: false,
        observation_date: null,
        spread_basis_points: null,
        long_value: null,
        short_value: null,
        unavailable_reason: "NO_OBSERVATIONS_FOR_EITHER_SERIES",
        provenance: null,
      }),
    ],
    inflation_compensation: [
      buildInflationCompensation({
        available: false,
        observation_date: null,
        compensation_percent: null,
        nominal_value: null,
        real_value: null,
        unavailable_reason: "NO_OBSERVATIONS_FOR_EITHER_SERIES",
        provenance: null,
      }),
    ],
  });
}
