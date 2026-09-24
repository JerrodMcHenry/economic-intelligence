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

/**
 * The four windows with a DIFFERENT published `from_date` and
 * `from_value` each (Increment #52B).
 *
 * ================================================================
 * WHY `buildAllChanges` WAS NOT ENOUGH
 * ================================================================
 *
 * `buildAllChanges` applies ONE override object to all four windows, so
 * every window in the old fixture resolved to `from_date: "2026-09-17"`
 * and one `from_value`. Every test written before #52B was correct with
 * that, because none of them read those two fields as anything but
 * inputs to a basis-point figure the backend had already computed.
 *
 * #52B draws `from_value` AS A CURVE, and then the flat fixture was
 * actively misleading in two ways at once. All four windows landing on
 * one date meant a test could not tell a correct window selector from
 * one that ignored its argument. And because `buildRateLevel`'s default
 * change carries `from_value: 4.94` while the 5-year's latest value is
 * 4.86, the fixture described a maturity that had FALLEN 8 bp while its
 * own `change_basis_points` said it had risen 7 — a shape no real
 * response can produce.
 *
 * The values below are the live API's own, captured 2026-09-24 and
 * recorded in `docs/product/mockups/v52a/rates-snapshot-2026-09-24.json`:
 * four distinct session dates, shared across every maturity, with each
 * maturity's `from_value` and `change_basis_points` consistent with its
 * latest reading.
 *
 * The lesson is #51B's, arriving again in a different costume: a
 * fixture adequate for the tests that already exist is not
 * automatically adequate for a component that asks a new question of
 * the same data.
 */
const WINDOW_DATES: Record<ChangeWindow, string> = {
  "1_SESSION": "2026-09-17",
  "5_SESSIONS": "2026-09-11",
  "21_SESSIONS": "2026-08-19",
  "63_SESSIONS": "2026-06-18",
};

export function buildWindowedChanges(
  readings: Record<ChangeWindow, { from_value: number; change_basis_points: number }>,
  toValue: number,
  toDate = "2026-09-18",
): RateChange[] {
  return (["1_SESSION", "5_SESSIONS", "21_SESSIONS", "63_SESSIONS"] as ChangeWindow[]).map((window) =>
    buildRateChange(window, {
      from_date: WINDOW_DATES[window],
      from_value: readings[window].from_value,
      change_basis_points: readings[window].change_basis_points,
      to_date: toDate,
      to_value: toValue,
    }),
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
        changes: buildWindowedChanges(
          {
            "1_SESSION": { from_value: 4.67, change_basis_points: 9.0 },
            "5_SESSIONS": { from_value: 4.63, change_basis_points: 13.0 },
            "21_SESSIONS": { from_value: 4.19, change_basis_points: 57.0 },
            "63_SESSIONS": { from_value: 4.19, change_basis_points: 57.0 },
          },
          4.76,
        ),
        provenance: buildSourceProvenance({ series_id: "UST_NOMINAL_2Y" }),
      }),
      buildRateLevel({
        series_id: "UST_NOMINAL_5Y",
        title: "5-Year Treasury Par Yield (Nominal)",
        latest_value: 4.86,
        changes: buildWindowedChanges(
          {
            "1_SESSION": { from_value: 4.78, change_basis_points: 8.0 },
            "5_SESSIONS": { from_value: 4.78, change_basis_points: 8.0 },
            "21_SESSIONS": { from_value: 4.35, change_basis_points: 51.0 },
            "63_SESSIONS": { from_value: 4.23, change_basis_points: 63.0 },
          },
          4.86,
        ),
        provenance: buildSourceProvenance({ series_id: "UST_NOMINAL_5Y" }),
      }),
      buildRateLevel({
        series_id: "UST_NOMINAL_10Y",
        latest_value: 5.01,
        changes: buildWindowedChanges(
          {
            "1_SESSION": { from_value: 4.94, change_basis_points: 7.0 },
            "5_SESSIONS": { from_value: 4.96, change_basis_points: 5.0 },
            "21_SESSIONS": { from_value: 4.65, change_basis_points: 36.0 },
            "63_SESSIONS": { from_value: 4.46, change_basis_points: 55.0 },
          },
          5.01,
        ),
      }),
      buildRateLevel({
        series_id: "UST_NOMINAL_30Y",
        title: "30-Year Treasury Par Yield (Nominal)",
        latest_value: 5.34,
        /* The 30-year FELL over five sessions while the other three
           rose. That disagreement is real (it is what the live API
           published on 2026-09-18) and it is the only reason a test can
           exercise the MIXED level reading at all. */
        changes: buildWindowedChanges(
          {
            "1_SESSION": { from_value: 5.29, change_basis_points: 5.0 },
            "5_SESSIONS": { from_value: 5.35, change_basis_points: -1.0 },
            "21_SESSIONS": { from_value: 5.19, change_basis_points: 15.0 },
            "63_SESSIONS": { from_value: 4.9, change_basis_points: 44.0 },
          },
          5.34,
        ),
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
      buildCurveSpread({
        changes: buildWindowedChanges(
          {
            "1_SESSION": { from_value: 0.27, change_basis_points: -2.0 },
            "5_SESSIONS": { from_value: 0.33, change_basis_points: -8.0 },
            "21_SESSIONS": { from_value: 0.46, change_basis_points: -21.0 },
            "63_SESSIONS": { from_value: 0.27, change_basis_points: -2.0 },
          },
          0.25,
        ),
      }),
      buildCurveSpread({
        spread_id: "2s30s",
        title: "30-Year minus 2-Year",
        spread_basis_points: 58.0,
        long_series_id: "UST_NOMINAL_30Y",
        long_value: 5.34,
        /* The published shape change, per window. #52B's SHAPE sentence
           reads `from_value`/`to_value` from here rather than
           subtracting the 2-year from the 30-year itself. */
        changes: buildWindowedChanges(
          {
            "1_SESSION": { from_value: 0.62, change_basis_points: -4.0 },
            "5_SESSIONS": { from_value: 0.72, change_basis_points: -14.0 },
            "21_SESSIONS": { from_value: 1.0, change_basis_points: -42.0 },
            "63_SESSIONS": { from_value: 0.71, change_basis_points: -13.0 },
          },
          0.58,
        ),
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
