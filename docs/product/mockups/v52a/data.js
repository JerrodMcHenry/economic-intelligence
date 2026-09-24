/**
 * RATES WORLD PROTOTYPE DATA (#52A).
 *
 * ================================================================
 * EVERY FIGURE IS REAL AND NONE OF IT IS LIVE
 * ================================================================
 *
 * Captured 2026-09-24 from three real endpoints on the running local
 * API: the rates monitor, six Treasury series observation feeds, and
 * the rates intelligence stream. The verbatim responses sit beside
 * this file in `rates-snapshot-2026-09-24.json`; this module is a
 * reshaping of them for the prototype and nothing more.
 *
 * NOTHING HERE IS COMPUTED BY THIS FILE, and that is the whole point
 * of the design it feeds. The "today" curve is four published
 * `latest_value` fields. Each "then" curve is four published
 * `changes[].from_value` fields on one published `changes[].from_date`
 * -- and those dates are ALIGNED across all four maturities, which is
 * what makes a second curve drawable without subtracting anything.
 * The widening/narrowing sentence reads the published 2s30s spread's
 * own `from_value` and `to_value`; even that comparison is a field,
 * not a subtraction.
 *
 * `rates_v1.0` computed every derived number. Treasury published every
 * observation. This is transport.
 *
 * WHAT IS DELIBERATELY ABSENT: there is no spread history series
 * (four candidate ids all 404), no `/api/v1/monitors/rates/history`
 * (422 -- the route accepts only inflation and labor) and no
 * `/monitors/rates/changes`. Only six maturities are ingested. The
 * `unavailable` block below records each gap so the prototype can say
 * so rather than simulate it.
 */
window.RATES = {
  "_note": "SNAPSHOT of real MacroChipz API responses captured 2026-09-24 from the running local backend. Real values, real observation dates, real Treasury attribution. NOT LIVE and NOT a MacroChipz publication. The full verbatim responses are beside this file in rates-snapshot-2026-09-24.json.",
  "_captured_at": "2026-09-24T16:38:02Z",
  "_endpoints": [
    "GET /api/v1/monitors/rates",
    "GET /api/v1/series/{series_id}/observations?limit=400 (six Treasury series)",
    "GET /api/v1/intelligence?world=rates&limit=50"
  ],
  "methodology_id": "rates_v1.0",
  "data_basis": "latest_published_data",
  "provider": "TREASURY",
  "attribution": "Source: U.S. Department of the Treasury (Daily Treasury Par Yield Curve Rates).",
  "as_of_date": "2026-09-18",
  "today_curve": [
    {
      "series_id": "UST_NOMINAL_2Y",
      "label": "2Y",
      "years": 2,
      "value": 4.76,
      "date": "2026-09-18",
      "title": "2-Year Treasury Par Yield (Nominal)"
    },
    {
      "series_id": "UST_NOMINAL_5Y",
      "label": "5Y",
      "years": 5,
      "value": 4.86,
      "date": "2026-09-18",
      "title": "5-Year Treasury Par Yield (Nominal)"
    },
    {
      "series_id": "UST_NOMINAL_10Y",
      "label": "10Y",
      "years": 10,
      "value": 5.01,
      "date": "2026-09-18",
      "title": "10-Year Treasury Par Yield (Nominal)"
    },
    {
      "series_id": "UST_NOMINAL_30Y",
      "label": "30Y",
      "years": 30,
      "value": 5.34,
      "date": "2026-09-18",
      "title": "30-Year Treasury Par Yield (Nominal)"
    }
  ],
  "comparisons": [
    {
      "window": "1_SESSION",
      "window_label": "1 session",
      "aligned": true,
      "from_date": "2026-09-17",
      "points": [
        {
          "series_id": "UST_NOMINAL_2Y",
          "label": "2Y",
          "years": 2,
          "value": 4.67,
          "date": "2026-09-17",
          "change_basis_points": 9.0,
          "available": true
        },
        {
          "series_id": "UST_NOMINAL_5Y",
          "label": "5Y",
          "years": 5,
          "value": 4.78,
          "date": "2026-09-17",
          "change_basis_points": 8.0,
          "available": true
        },
        {
          "series_id": "UST_NOMINAL_10Y",
          "label": "10Y",
          "years": 10,
          "value": 4.94,
          "date": "2026-09-17",
          "change_basis_points": 7.0,
          "available": true
        },
        {
          "series_id": "UST_NOMINAL_30Y",
          "label": "30Y",
          "years": 30,
          "value": 5.29,
          "date": "2026-09-17",
          "change_basis_points": 5.0,
          "available": true
        }
      ],
      "spread_2s10s": {
        "from_value_percentage_points": 0.27,
        "to_value_percentage_points": 0.25,
        "change_basis_points": -2.0,
        "from_date": "2026-09-17",
        "to_date": "2026-09-18"
      },
      "spread_2s30s": {
        "from_value_percentage_points": 0.62,
        "to_value_percentage_points": 0.58,
        "change_basis_points": -4.0,
        "from_date": "2026-09-17",
        "to_date": "2026-09-18"
      }
    },
    {
      "window": "5_SESSIONS",
      "window_label": "5 sessions",
      "aligned": true,
      "from_date": "2026-09-11",
      "points": [
        {
          "series_id": "UST_NOMINAL_2Y",
          "label": "2Y",
          "years": 2,
          "value": 4.63,
          "date": "2026-09-11",
          "change_basis_points": 13.0,
          "available": true
        },
        {
          "series_id": "UST_NOMINAL_5Y",
          "label": "5Y",
          "years": 5,
          "value": 4.78,
          "date": "2026-09-11",
          "change_basis_points": 8.0,
          "available": true
        },
        {
          "series_id": "UST_NOMINAL_10Y",
          "label": "10Y",
          "years": 10,
          "value": 4.96,
          "date": "2026-09-11",
          "change_basis_points": 5.0,
          "available": true
        },
        {
          "series_id": "UST_NOMINAL_30Y",
          "label": "30Y",
          "years": 30,
          "value": 5.35,
          "date": "2026-09-11",
          "change_basis_points": -1.0,
          "available": true
        }
      ],
      "spread_2s10s": {
        "from_value_percentage_points": 0.33,
        "to_value_percentage_points": 0.25,
        "change_basis_points": -8.0,
        "from_date": "2026-09-11",
        "to_date": "2026-09-18"
      },
      "spread_2s30s": {
        "from_value_percentage_points": 0.72,
        "to_value_percentage_points": 0.58,
        "change_basis_points": -14.0,
        "from_date": "2026-09-11",
        "to_date": "2026-09-18"
      }
    },
    {
      "window": "21_SESSIONS",
      "window_label": "21 sessions",
      "aligned": true,
      "from_date": "2026-08-19",
      "points": [
        {
          "series_id": "UST_NOMINAL_2Y",
          "label": "2Y",
          "years": 2,
          "value": 4.19,
          "date": "2026-08-19",
          "change_basis_points": 57.0,
          "available": true
        },
        {
          "series_id": "UST_NOMINAL_5Y",
          "label": "5Y",
          "years": 5,
          "value": 4.35,
          "date": "2026-08-19",
          "change_basis_points": 51.0,
          "available": true
        },
        {
          "series_id": "UST_NOMINAL_10Y",
          "label": "10Y",
          "years": 10,
          "value": 4.65,
          "date": "2026-08-19",
          "change_basis_points": 36.0,
          "available": true
        },
        {
          "series_id": "UST_NOMINAL_30Y",
          "label": "30Y",
          "years": 30,
          "value": 5.19,
          "date": "2026-08-19",
          "change_basis_points": 15.0,
          "available": true
        }
      ],
      "spread_2s10s": {
        "from_value_percentage_points": 0.46,
        "to_value_percentage_points": 0.25,
        "change_basis_points": -21.0,
        "from_date": "2026-08-19",
        "to_date": "2026-09-18"
      },
      "spread_2s30s": {
        "from_value_percentage_points": 1.0,
        "to_value_percentage_points": 0.58,
        "change_basis_points": -42.0,
        "from_date": "2026-08-19",
        "to_date": "2026-09-18"
      }
    },
    {
      "window": "63_SESSIONS",
      "window_label": "63 sessions",
      "aligned": true,
      "from_date": "2026-06-18",
      "points": [
        {
          "series_id": "UST_NOMINAL_2Y",
          "label": "2Y",
          "years": 2,
          "value": 4.19,
          "date": "2026-06-18",
          "change_basis_points": 57.0,
          "available": true
        },
        {
          "series_id": "UST_NOMINAL_5Y",
          "label": "5Y",
          "years": 5,
          "value": 4.23,
          "date": "2026-06-18",
          "change_basis_points": 63.0,
          "available": true
        },
        {
          "series_id": "UST_NOMINAL_10Y",
          "label": "10Y",
          "years": 10,
          "value": 4.46,
          "date": "2026-06-18",
          "change_basis_points": 55.0,
          "available": true
        },
        {
          "series_id": "UST_NOMINAL_30Y",
          "label": "30Y",
          "years": 30,
          "value": 4.9,
          "date": "2026-06-18",
          "change_basis_points": 44.0,
          "available": true
        }
      ],
      "spread_2s10s": {
        "from_value_percentage_points": 0.27,
        "to_value_percentage_points": 0.25,
        "change_basis_points": -2.0,
        "from_date": "2026-06-18",
        "to_date": "2026-09-18"
      },
      "spread_2s30s": {
        "from_value_percentage_points": 0.71,
        "to_value_percentage_points": 0.58,
        "change_basis_points": -13.0,
        "from_date": "2026-06-18",
        "to_date": "2026-09-18"
      }
    }
  ],
  "levels": {
    "UST_NOMINAL_2Y": {
      "label": "2Y",
      "title": "2-Year Treasury Par Yield (Nominal)",
      "latest_value": 4.76,
      "latest_date": "2026-09-18",
      "changes": {
        "1_SESSION": {
          "change_basis_points": 9.0,
          "from_value": 4.67,
          "from_date": "2026-09-17",
          "to_value": 4.76,
          "to_date": "2026-09-18",
          "available": true
        },
        "5_SESSIONS": {
          "change_basis_points": 13.0,
          "from_value": 4.63,
          "from_date": "2026-09-11",
          "to_value": 4.76,
          "to_date": "2026-09-18",
          "available": true
        },
        "21_SESSIONS": {
          "change_basis_points": 57.0,
          "from_value": 4.19,
          "from_date": "2026-08-19",
          "to_value": 4.76,
          "to_date": "2026-09-18",
          "available": true
        },
        "63_SESSIONS": {
          "change_basis_points": 57.0,
          "from_value": 4.19,
          "from_date": "2026-06-18",
          "to_value": 4.76,
          "to_date": "2026-09-18",
          "available": true
        }
      },
      "historical_context": {
        "available": true,
        "window": "5_SESSIONS",
        "observation_count": 113,
        "history_start_date": "2026-04-08",
        "history_end_date": "2026-09-18",
        "percentile_rank": 0.831858,
        "magnitude_percentile_rank": 0.80531,
        "minimum_change_basis_points": -14.0,
        "maximum_change_basis_points": 31.0
      },
      "provenance": {
        "provider": "TREASURY",
        "dataset": "daily_treasury_yield_curve",
        "series_id": "UST_NOMINAL_2Y",
        "observation_date": "2026-09-18",
        "source_url": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve",
        "retrieved_at": "2026-09-19T17:04:54.461189-07:00",
        "revision_count": 0,
        "last_revised_at": null
      }
    },
    "UST_NOMINAL_5Y": {
      "label": "5Y",
      "title": "5-Year Treasury Par Yield (Nominal)",
      "latest_value": 4.86,
      "latest_date": "2026-09-18",
      "changes": {
        "1_SESSION": {
          "change_basis_points": 8.0,
          "from_value": 4.78,
          "from_date": "2026-09-17",
          "to_value": 4.86,
          "to_date": "2026-09-18",
          "available": true
        },
        "5_SESSIONS": {
          "change_basis_points": 8.0,
          "from_value": 4.78,
          "from_date": "2026-09-11",
          "to_value": 4.86,
          "to_date": "2026-09-18",
          "available": true
        },
        "21_SESSIONS": {
          "change_basis_points": 51.0,
          "from_value": 4.35,
          "from_date": "2026-08-19",
          "to_value": 4.86,
          "to_date": "2026-09-18",
          "available": true
        },
        "63_SESSIONS": {
          "change_basis_points": 63.0,
          "from_value": 4.23,
          "from_date": "2026-06-18",
          "to_value": 4.86,
          "to_date": "2026-09-18",
          "available": true
        }
      },
      "historical_context": {
        "available": true,
        "window": "5_SESSIONS",
        "observation_count": 113,
        "history_start_date": "2026-04-08",
        "history_end_date": "2026-09-18",
        "percentile_rank": 0.681416,
        "magnitude_percentile_rank": 0.539823,
        "minimum_change_basis_points": -15.0,
        "maximum_change_basis_points": 26.0
      },
      "provenance": {
        "provider": "TREASURY",
        "dataset": "daily_treasury_yield_curve",
        "series_id": "UST_NOMINAL_5Y",
        "observation_date": "2026-09-18",
        "source_url": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve",
        "retrieved_at": "2026-09-19T17:04:54.461189-07:00",
        "revision_count": 0,
        "last_revised_at": null
      }
    },
    "UST_NOMINAL_10Y": {
      "label": "10Y",
      "title": "10-Year Treasury Par Yield (Nominal)",
      "latest_value": 5.01,
      "latest_date": "2026-09-18",
      "changes": {
        "1_SESSION": {
          "change_basis_points": 7.0,
          "from_value": 4.94,
          "from_date": "2026-09-17",
          "to_value": 5.01,
          "to_date": "2026-09-18",
          "available": true
        },
        "5_SESSIONS": {
          "change_basis_points": 5.0,
          "from_value": 4.96,
          "from_date": "2026-09-11",
          "to_value": 5.01,
          "to_date": "2026-09-18",
          "available": true
        },
        "21_SESSIONS": {
          "change_basis_points": 36.0,
          "from_value": 4.65,
          "from_date": "2026-08-19",
          "to_value": 5.01,
          "to_date": "2026-09-18",
          "available": true
        },
        "63_SESSIONS": {
          "change_basis_points": 55.0,
          "from_value": 4.46,
          "from_date": "2026-06-18",
          "to_value": 5.01,
          "to_date": "2026-09-18",
          "available": true
        }
      },
      "historical_context": {
        "available": true,
        "window": "5_SESSIONS",
        "observation_count": 113,
        "history_start_date": "2026-04-08",
        "history_end_date": "2026-09-18",
        "percentile_rank": 0.566372,
        "magnitude_percentile_rank": 0.39823,
        "minimum_change_basis_points": -19.0,
        "maximum_change_basis_points": 21.0
      },
      "provenance": {
        "provider": "TREASURY",
        "dataset": "daily_treasury_yield_curve",
        "series_id": "UST_NOMINAL_10Y",
        "observation_date": "2026-09-18",
        "source_url": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve",
        "retrieved_at": "2026-09-19T17:04:54.461189-07:00",
        "revision_count": 0,
        "last_revised_at": null
      }
    },
    "UST_NOMINAL_30Y": {
      "label": "30Y",
      "title": "30-Year Treasury Par Yield (Nominal)",
      "latest_value": 5.34,
      "latest_date": "2026-09-18",
      "changes": {
        "1_SESSION": {
          "change_basis_points": 5.0,
          "from_value": 5.29,
          "from_date": "2026-09-17",
          "to_value": 5.34,
          "to_date": "2026-09-18",
          "available": true
        },
        "5_SESSIONS": {
          "change_basis_points": -1.0,
          "from_value": 5.35,
          "from_date": "2026-09-11",
          "to_value": 5.34,
          "to_date": "2026-09-18",
          "available": true
        },
        "21_SESSIONS": {
          "change_basis_points": 15.0,
          "from_value": 5.19,
          "from_date": "2026-08-19",
          "to_value": 5.34,
          "to_date": "2026-09-18",
          "available": true
        },
        "63_SESSIONS": {
          "change_basis_points": 44.0,
          "from_value": 4.9,
          "from_date": "2026-06-18",
          "to_value": 5.34,
          "to_date": "2026-09-18",
          "available": true
        }
      },
      "historical_context": {
        "available": true,
        "window": "5_SESSIONS",
        "observation_count": 113,
        "history_start_date": "2026-04-08",
        "history_end_date": "2026-09-18",
        "percentile_rank": 0.327434,
        "magnitude_percentile_rank": 0.035398,
        "minimum_change_basis_points": -17.0,
        "maximum_change_basis_points": 19.0
      },
      "provenance": {
        "provider": "TREASURY",
        "dataset": "daily_treasury_yield_curve",
        "series_id": "UST_NOMINAL_30Y",
        "observation_date": "2026-09-18",
        "source_url": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve",
        "retrieved_at": "2026-09-19T17:04:54.461189-07:00",
        "revision_count": 0,
        "last_revised_at": null
      }
    }
  },
  "real_curve": [
    {
      "series_id": "UST_REAL_5Y",
      "title": "5-Year Treasury Par Real Yield (TIPS)",
      "latest_value": 2.55,
      "latest_date": "2026-09-18",
      "available": true
    },
    {
      "series_id": "UST_REAL_10Y",
      "title": "10-Year Treasury Par Real Yield (TIPS)",
      "latest_value": 2.68,
      "latest_date": "2026-09-18",
      "available": true
    }
  ],
  "derived": {
    "spreads": [
      {
        "spread_id": "2s10s",
        "title": "10-Year minus 2-Year",
        "spread_basis_points": 25.0,
        "observation_date": "2026-09-18",
        "long_value": 5.01,
        "short_value": 4.76,
        "long_series_id": "UST_NOMINAL_10Y",
        "short_series_id": "UST_NOMINAL_2Y",
        "calculation": "UST_NOMINAL_10Y - UST_NOMINAL_2Y, in basis points, on one exactly-shared observation date"
      },
      {
        "spread_id": "2s30s",
        "title": "30-Year minus 2-Year",
        "spread_basis_points": 58.0,
        "observation_date": "2026-09-18",
        "long_value": 5.34,
        "short_value": 4.76,
        "long_series_id": "UST_NOMINAL_30Y",
        "short_series_id": "UST_NOMINAL_2Y",
        "calculation": "UST_NOMINAL_30Y - UST_NOMINAL_2Y, in basis points, on one exactly-shared observation date"
      }
    ],
    "inflation_compensation": [
      {
        "maturity": "5Y",
        "title": "5-Year market-implied inflation compensation",
        "compensation_percent": 2.31,
        "observation_date": "2026-09-18",
        "nominal_value": 4.86,
        "real_value": 2.55,
        "calculation": "UST_NOMINAL_5Y - UST_REAL_5Y, in percentage points, on one exactly-shared observation date; market-implied compensation, not an inflation forecast"
      },
      {
        "maturity": "10Y",
        "title": "10-Year market-implied inflation compensation",
        "compensation_percent": 2.33,
        "observation_date": "2026-09-18",
        "nominal_value": 5.01,
        "real_value": 2.68,
        "calculation": "UST_NOMINAL_10Y - UST_REAL_10Y, in percentage points, on one exactly-shared observation date; market-implied compensation, not an inflation forecast"
      }
    ]
  },
  "movements": [
    {
      "id": "rates:UST_REAL_10Y:2026-09-18",
      "concepts": [
        "UST_REAL_10Y"
      ],
      "effective_period": "2026-09-18",
      "recorded_at": "2026-09-20T00:06:45.423250Z",
      "type": "RATES_MOVEMENT",
      "evidence": [
        {
          "concept_id": "UST_REAL_10Y",
          "provider": "TREASURY",
          "provider_series_id": "UST_REAL_10Y",
          "observation_date": "2026-09-18",
          "value": 2.68
        }
      ],
      "limitations": [
        "Carries no significance claim: rates_v1.0 defines no notability threshold, so this reports the movement and its own historical position, not that the movement matters.",
        "Change windows are counted in trading SESSIONS, never calendar days.",
        "Treasury observations are stored under MacroChipz's own series identifiers, so `provider_series_id` here is the stored identifier rather than Treasury's own XML field name; that field is recorded in observation_provenance.source_series_field. See docs/architecture/economic-concept-identity.md section 6."
      ],
      "methodology": {
        "methodology_id": "rates_v1.0",
        "data_basis": "latest_published_data"
      }
    },
    {
      "id": "rates:UST_REAL_5Y:2026-09-18",
      "concepts": [
        "UST_REAL_5Y"
      ],
      "effective_period": "2026-09-18",
      "recorded_at": "2026-09-20T00:06:45.423250Z",
      "type": "RATES_MOVEMENT",
      "evidence": [
        {
          "concept_id": "UST_REAL_5Y",
          "provider": "TREASURY",
          "provider_series_id": "UST_REAL_5Y",
          "observation_date": "2026-09-18",
          "value": 2.55
        }
      ],
      "limitations": [
        "Carries no significance claim: rates_v1.0 defines no notability threshold, so this reports the movement and its own historical position, not that the movement matters.",
        "Change windows are counted in trading SESSIONS, never calendar days.",
        "Treasury observations are stored under MacroChipz's own series identifiers, so `provider_series_id` here is the stored identifier rather than Treasury's own XML field name; that field is recorded in observation_provenance.source_series_field. See docs/architecture/economic-concept-identity.md section 6."
      ],
      "methodology": {
        "methodology_id": "rates_v1.0",
        "data_basis": "latest_published_data"
      }
    },
    {
      "id": "rates:UST_NOMINAL_10Y:2026-09-18",
      "concepts": [
        "UST_NOMINAL_10Y"
      ],
      "effective_period": "2026-09-18",
      "recorded_at": "2026-09-20T00:04:54.461189Z",
      "type": "RATES_MOVEMENT",
      "evidence": [
        {
          "concept_id": "UST_NOMINAL_10Y",
          "provider": "TREASURY",
          "provider_series_id": "UST_NOMINAL_10Y",
          "observation_date": "2026-09-18",
          "value": 5.01
        }
      ],
      "limitations": [
        "Carries no significance claim: rates_v1.0 defines no notability threshold, so this reports the movement and its own historical position, not that the movement matters.",
        "Change windows are counted in trading SESSIONS, never calendar days.",
        "Treasury observations are stored under MacroChipz's own series identifiers, so `provider_series_id` here is the stored identifier rather than Treasury's own XML field name; that field is recorded in observation_provenance.source_series_field. See docs/architecture/economic-concept-identity.md section 6."
      ],
      "methodology": {
        "methodology_id": "rates_v1.0",
        "data_basis": "latest_published_data"
      }
    },
    {
      "id": "rates:UST_NOMINAL_2Y:2026-09-18",
      "concepts": [
        "UST_NOMINAL_2Y"
      ],
      "effective_period": "2026-09-18",
      "recorded_at": "2026-09-20T00:04:54.461189Z",
      "type": "RATES_MOVEMENT",
      "evidence": [
        {
          "concept_id": "UST_NOMINAL_2Y",
          "provider": "TREASURY",
          "provider_series_id": "UST_NOMINAL_2Y",
          "observation_date": "2026-09-18",
          "value": 4.76
        }
      ],
      "limitations": [
        "Carries no significance claim: rates_v1.0 defines no notability threshold, so this reports the movement and its own historical position, not that the movement matters.",
        "Change windows are counted in trading SESSIONS, never calendar days.",
        "Treasury observations are stored under MacroChipz's own series identifiers, so `provider_series_id` here is the stored identifier rather than Treasury's own XML field name; that field is recorded in observation_provenance.source_series_field. See docs/architecture/economic-concept-identity.md section 6."
      ],
      "methodology": {
        "methodology_id": "rates_v1.0",
        "data_basis": "latest_published_data"
      }
    },
    {
      "id": "rates:UST_NOMINAL_30Y:2026-09-18",
      "concepts": [
        "UST_NOMINAL_30Y"
      ],
      "effective_period": "2026-09-18",
      "recorded_at": "2026-09-20T00:04:54.461189Z",
      "type": "RATES_MOVEMENT",
      "evidence": [
        {
          "concept_id": "UST_NOMINAL_30Y",
          "provider": "TREASURY",
          "provider_series_id": "UST_NOMINAL_30Y",
          "observation_date": "2026-09-18",
          "value": 5.34
        }
      ],
      "limitations": [
        "Carries no significance claim: rates_v1.0 defines no notability threshold, so this reports the movement and its own historical position, not that the movement matters.",
        "Change windows are counted in trading SESSIONS, never calendar days.",
        "Treasury observations are stored under MacroChipz's own series identifiers, so `provider_series_id` here is the stored identifier rather than Treasury's own XML field name; that field is recorded in observation_provenance.source_series_field. See docs/architecture/economic-concept-identity.md section 6."
      ],
      "methodology": {
        "methodology_id": "rates_v1.0",
        "data_basis": "latest_published_data"
      }
    },
    {
      "id": "rates:UST_NOMINAL_5Y:2026-09-18",
      "concepts": [
        "UST_NOMINAL_5Y"
      ],
      "effective_period": "2026-09-18",
      "recorded_at": "2026-09-20T00:04:54.461189Z",
      "type": "RATES_MOVEMENT",
      "evidence": [
        {
          "concept_id": "UST_NOMINAL_5Y",
          "provider": "TREASURY",
          "provider_series_id": "UST_NOMINAL_5Y",
          "observation_date": "2026-09-18",
          "value": 4.86
        }
      ],
      "limitations": [
        "Carries no significance claim: rates_v1.0 defines no notability threshold, so this reports the movement and its own historical position, not that the movement matters.",
        "Change windows are counted in trading SESSIONS, never calendar days.",
        "Treasury observations are stored under MacroChipz's own series identifiers, so `provider_series_id` here is the stored identifier rather than Treasury's own XML field name; that field is recorded in observation_provenance.source_series_field. See docs/architecture/economic-concept-identity.md section 6."
      ],
      "methodology": {
        "methodology_id": "rates_v1.0",
        "data_basis": "latest_published_data"
      }
    }
  ],
  "observation_coverage": {
    "UST_NOMINAL_2Y": {
      "returned": 119,
      "total": 119,
      "first_date": "2026-04-01",
      "last_date": "2026-09-18",
      "nulls": 0,
      "units": "Percent",
      "source": "TREASURY"
    },
    "UST_NOMINAL_5Y": {
      "returned": 119,
      "total": 119,
      "first_date": "2026-04-01",
      "last_date": "2026-09-18",
      "nulls": 0,
      "units": "Percent",
      "source": "TREASURY"
    },
    "UST_NOMINAL_10Y": {
      "returned": 119,
      "total": 119,
      "first_date": "2026-04-01",
      "last_date": "2026-09-18",
      "nulls": 0,
      "units": "Percent",
      "source": "TREASURY"
    },
    "UST_NOMINAL_30Y": {
      "returned": 119,
      "total": 119,
      "first_date": "2026-04-01",
      "last_date": "2026-09-18",
      "nulls": 0,
      "units": "Percent",
      "source": "TREASURY"
    },
    "UST_REAL_5Y": {
      "returned": 119,
      "total": 119,
      "first_date": "2026-04-01",
      "last_date": "2026-09-18",
      "nulls": 0,
      "units": "Percent",
      "source": "TREASURY"
    },
    "UST_REAL_10Y": {
      "returned": 119,
      "total": 119,
      "first_date": "2026-04-01",
      "last_date": "2026-09-18",
      "nulls": 0,
      "units": "Percent",
      "source": "TREASURY"
    }
  },
  "unavailable": {
    "spread_history_series": [
      "UST_SPREAD_2s10s",
      "2s10s",
      "UST_2s10s",
      "T10Y2Y"
    ],
    "monitors_rates_history": "GET /api/v1/monitors/rates/history -> 422; the path parameter accepts only 'inflation' or 'labor'.",
    "rates_changes_endpoint": "GET /api/v1/monitors/rates/changes -> 404 (inflation and labor both have one).",
    "maturities_not_ingested": [
      "1M",
      "3M",
      "6M",
      "1Y",
      "3Y",
      "7Y",
      "20Y",
      "real 20Y",
      "real 30Y"
    ],
    "note": "Recorded so the prototype never fills a gap with an estimate."
  }
};
