/**
 * RATES WORLD PROTOTYPE DATA (#49A).
 *
 * ================================================================
 * EVERY FIGURE BELOW IS REAL AND NONE OF IT IS LIVE
 * ================================================================
 *
 * Generated from `rates-snapshot.json`, which is a capture of
 * `GET /api/v1/monitors/rates` from the running local API. Real values,
 * real as-of date, real Treasury attribution, real provenance.
 *
 * It is a SNAPSHOT and the page says so on its face. The prototype is
 * opened from the filesystem and the API sends no
 * `Access-Control-Allow-Origin` header, so a live fetch would fail --
 * and inventing a curve to avoid that is the single worst thing a
 * product like this could do.
 *
 * NOTHING HERE IS COMPUTED BY THIS FILE. No spread, no basis point, no
 * compensation, no percentile. `rates_v1.0` computed all of it; this is
 * transport.
 */
window.RATES = {
  "_note": "A SNAPSHOT of GET /api/v1/monitors/rates captured from the running local API. Real values, real as-of date, real attribution. NOT live: the prototype is a file:// page and the API sends no Access-Control-Allow-Origin header, so a cross-origin fetch would fail. Every figure below is displayed with this same as-of date on its face.",
  "_captured_at": "2026-09-23T18:50:52+00:00",
  "_endpoint": "GET /api/v1/monitors/rates",
  "methodology_id": "rates_v1.0",
  "data_basis": "latest_published_data",
  "provider": "TREASURY",
  "attribution": "Source: U.S. Department of the Treasury (Daily Treasury Par Yield Curve Rates).",
  "as_of_date": "2026-09-18",
  "nominal": [
    {
      "series_id": "UST_NOMINAL_2Y",
      "title": "2-Year Treasury Par Yield (Nominal)",
      "value": 4.76,
      "available": true,
      "date": "2026-09-18",
      "c1": {
        "available": true,
        "basis_points": 9.0,
        "from_value": 4.67,
        "from_date": "2026-09-17",
        "to_date": "2026-09-18"
      },
      "c5": {
        "available": true,
        "basis_points": 13.0,
        "from_value": 4.63,
        "from_date": "2026-09-11",
        "to_date": "2026-09-18"
      },
      "c21": {
        "available": true,
        "basis_points": 57.0,
        "from_value": 4.19,
        "from_date": "2026-08-19",
        "to_date": "2026-09-18"
      },
      "c63": {
        "available": true,
        "basis_points": 57.0,
        "from_value": 4.19,
        "from_date": "2026-06-18",
        "to_date": "2026-09-18"
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
    {
      "series_id": "UST_NOMINAL_5Y",
      "title": "5-Year Treasury Par Yield (Nominal)",
      "value": 4.86,
      "available": true,
      "date": "2026-09-18",
      "c1": {
        "available": true,
        "basis_points": 8.0,
        "from_value": 4.78,
        "from_date": "2026-09-17",
        "to_date": "2026-09-18"
      },
      "c5": {
        "available": true,
        "basis_points": 8.0,
        "from_value": 4.78,
        "from_date": "2026-09-11",
        "to_date": "2026-09-18"
      },
      "c21": {
        "available": true,
        "basis_points": 51.0,
        "from_value": 4.35,
        "from_date": "2026-08-19",
        "to_date": "2026-09-18"
      },
      "c63": {
        "available": true,
        "basis_points": 63.0,
        "from_value": 4.23,
        "from_date": "2026-06-18",
        "to_date": "2026-09-18"
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
    {
      "series_id": "UST_NOMINAL_10Y",
      "title": "10-Year Treasury Par Yield (Nominal)",
      "value": 5.01,
      "available": true,
      "date": "2026-09-18",
      "c1": {
        "available": true,
        "basis_points": 7.0,
        "from_value": 4.94,
        "from_date": "2026-09-17",
        "to_date": "2026-09-18"
      },
      "c5": {
        "available": true,
        "basis_points": 5.0,
        "from_value": 4.96,
        "from_date": "2026-09-11",
        "to_date": "2026-09-18"
      },
      "c21": {
        "available": true,
        "basis_points": 36.0,
        "from_value": 4.65,
        "from_date": "2026-08-19",
        "to_date": "2026-09-18"
      },
      "c63": {
        "available": true,
        "basis_points": 55.0,
        "from_value": 4.46,
        "from_date": "2026-06-18",
        "to_date": "2026-09-18"
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
    {
      "series_id": "UST_NOMINAL_30Y",
      "title": "30-Year Treasury Par Yield (Nominal)",
      "value": 5.34,
      "available": true,
      "date": "2026-09-18",
      "c1": {
        "available": true,
        "basis_points": 5.0,
        "from_value": 5.29,
        "from_date": "2026-09-17",
        "to_date": "2026-09-18"
      },
      "c5": {
        "available": true,
        "basis_points": -1.0,
        "from_value": 5.35,
        "from_date": "2026-09-11",
        "to_date": "2026-09-18"
      },
      "c21": {
        "available": true,
        "basis_points": 15.0,
        "from_value": 5.19,
        "from_date": "2026-08-19",
        "to_date": "2026-09-18"
      },
      "c63": {
        "available": true,
        "basis_points": 44.0,
        "from_value": 4.9,
        "from_date": "2026-06-18",
        "to_date": "2026-09-18"
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
  ],
  "real": [
    {
      "series_id": "UST_REAL_5Y",
      "title": "5-Year Treasury Par Real Yield (TIPS)",
      "value": 2.55,
      "available": true,
      "date": "2026-09-18",
      "c5": {
        "available": true,
        "basis_points": 17.0,
        "from_value": 2.38,
        "from_date": "2026-09-11",
        "to_date": "2026-09-18"
      }
    },
    {
      "series_id": "UST_REAL_10Y",
      "title": "10-Year Treasury Par Real Yield (TIPS)",
      "value": 2.68,
      "available": true,
      "date": "2026-09-18",
      "c5": {
        "available": true,
        "basis_points": 8.0,
        "from_value": 2.6,
        "from_date": "2026-09-11",
        "to_date": "2026-09-18"
      }
    }
  ],
  "spreads": [
    {
      "spread_id": "2s10s",
      "basis_points": 25.0,
      "available": true,
      "c5": {
        "available": true,
        "basis_points": -8.0,
        "from_value": 0.33,
        "from_date": "2026-09-11",
        "to_date": "2026-09-18"
      },
      "provenance": {
        "methodology_id": "rates_v1.0",
        "calculation": "UST_NOMINAL_10Y - UST_NOMINAL_2Y, in basis points, on one exactly-shared observation date",
        "input_series_ids": [
          "UST_NOMINAL_10Y",
          "UST_NOMINAL_2Y"
        ],
        "input_observation_date": "2026-09-18",
        "calculated_at": "2026-09-23T18:50:37.305819Z"
      }
    },
    {
      "spread_id": "2s30s",
      "basis_points": 58.0,
      "available": true,
      "c5": {
        "available": true,
        "basis_points": -14.0,
        "from_value": 0.72,
        "from_date": "2026-09-11",
        "to_date": "2026-09-18"
      },
      "provenance": {
        "methodology_id": "rates_v1.0",
        "calculation": "UST_NOMINAL_30Y - UST_NOMINAL_2Y, in basis points, on one exactly-shared observation date",
        "input_series_ids": [
          "UST_NOMINAL_30Y",
          "UST_NOMINAL_2Y"
        ],
        "input_observation_date": "2026-09-18",
        "calculated_at": "2026-09-23T18:50:37.305819Z"
      }
    }
  ],
  "compensation": [
    {
      "maturity": "5Y",
      "percent": 2.31,
      "available": true,
      "c5": {
        "available": true,
        "basis_points": -9.0,
        "from_value": 2.4,
        "from_date": "2026-09-11",
        "to_date": "2026-09-18"
      },
      "provenance": {
        "methodology_id": "rates_v1.0",
        "calculation": "UST_NOMINAL_5Y - UST_REAL_5Y, in percentage points, on one exactly-shared observation date; market-implied compensation, not an inflation forecast",
        "input_series_ids": [
          "UST_NOMINAL_5Y",
          "UST_REAL_5Y"
        ],
        "input_observation_date": "2026-09-18",
        "calculated_at": "2026-09-23T18:50:37.305819Z"
      }
    },
    {
      "maturity": "10Y",
      "percent": 2.33,
      "available": true,
      "c5": {
        "available": true,
        "basis_points": -3.0,
        "from_value": 2.36,
        "from_date": "2026-09-11",
        "to_date": "2026-09-18"
      },
      "provenance": {
        "methodology_id": "rates_v1.0",
        "calculation": "UST_NOMINAL_10Y - UST_REAL_10Y, in percentage points, on one exactly-shared observation date; market-implied compensation, not an inflation forecast",
        "input_series_ids": [
          "UST_NOMINAL_10Y",
          "UST_REAL_10Y"
        ],
        "input_observation_date": "2026-09-18",
        "calculated_at": "2026-09-23T18:50:37.305819Z"
      }
    }
  ]
};
