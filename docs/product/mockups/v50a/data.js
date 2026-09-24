/**
 * INFLATION WORLD PROTOTYPE DATA (#50A).
 *
 * ================================================================
 * EVERY FIGURE IS REAL AND NONE OF IT IS LIVE
 * ================================================================
 *
 * Generated from `inflation-snapshot.json`, a capture of four real
 * endpoints on the running local API. Real values, real observation
 * dates, real FRED attribution, real recorded state history.
 *
 * It is a SNAPSHOT and the page says so on its face. Inventing a price
 * series to avoid that would be the single worst thing a product like
 * this could do.
 *
 * NOTHING HERE IS COMPUTED BY THIS FILE. No rate, no annualisation, no
 * gap to target, no state. `inflation_v1.0` computed all of it; the
 * index levels are the provider's own observations. This is transport.
 *
 * WHAT IS DELIBERATELY ABSENT: a rate-over-time series. The API
 * publishes rates for ONE period (four windows) and states for twelve.
 * Deriving a rate history from the index levels below would be exactly
 * the client-side economics the product forbids. See the spec's data
 * dependencies.
 */
window.INFLATION = {
  "_note": "SNAPSHOT of the MacroChipz API captured from the running local instance. Real values, real observation dates, real attribution. NOT LIVE: the prototype is opened from the filesystem and the API sends no Access-Control-Allow-Origin header. Every figure is displayed with its own as-of date.",
  "_captured_at": "2026-09-23T21:37:12+00:00",
  "_endpoints": [
    "GET /api/v1/monitors/inflation",
    "GET /api/v1/series/PCEPILFE/observations?limit=200",
    "GET /api/v1/series/CPIAUCSL/observations?limit=200",
    "GET /api/v1/monitors/inflation/history?limit=12&offset=0"
  ],
  "methodology_id": "inflation_v1.0",
  "data_basis": "latest_revised_data",
  "periods": {
    "latest_common_period": "2026-07-01",
    "data_through": "2026-08-01"
  },
  "coverage": {
    "primary_available": true,
    "confirmation_available": true,
    "target_available": true,
    "headline_cpi_available": true
  },
  "momentum": {
    "series_id": "PCEPILFE",
    "calculation_period": "2026-07-01",
    "latest_observation_period": "2026-07-01",
    "state": "MIXED",
    "r_1m_annualized": 2.986296846977332,
    "r_3m_annualized": 3.0477755322693367,
    "r_6m_annualized": 3.4594071030808804,
    "r_12m": 3.3441430040338282,
    "neutral_band_pp": 0.1,
    "lower_boundary": 3.244143004033828,
    "upper_boundary": 3.4441430040338283,
    "missing_required_metrics": [],
    "evidence": {
      "1m": {
        "series_id": "PCEPILFE",
        "transformation": "1m_annualized",
        "calculation_period": "2026-07-01",
        "endpoint_date_past": "2026-06-01",
        "endpoint_value_past": 130.338,
        "endpoint_date_current": "2026-07-01",
        "endpoint_value_current": 130.658,
        "value": 2.986296846977332,
        "methodology_id": "inflation_v1.0",
        "data_basis": "latest_revised_data"
      },
      "3m": {
        "series_id": "PCEPILFE",
        "transformation": "3m_annualized",
        "calculation_period": "2026-07-01",
        "endpoint_date_past": "2026-04-01",
        "endpoint_value_past": 129.681,
        "endpoint_date_current": "2026-07-01",
        "endpoint_value_current": 130.658,
        "value": 3.0477755322693367,
        "methodology_id": "inflation_v1.0",
        "data_basis": "latest_revised_data"
      },
      "6m": {
        "series_id": "PCEPILFE",
        "transformation": "6m_annualized",
        "calculation_period": "2026-07-01",
        "endpoint_date_past": "2026-01-01",
        "endpoint_value_past": 128.455,
        "endpoint_date_current": "2026-07-01",
        "endpoint_value_current": 130.658,
        "value": 3.4594071030808804,
        "methodology_id": "inflation_v1.0",
        "data_basis": "latest_revised_data"
      },
      "12m": {
        "series_id": "PCEPILFE",
        "transformation": "12m",
        "calculation_period": "2026-07-01",
        "endpoint_date_past": "2025-07-01",
        "endpoint_value_past": 126.43,
        "endpoint_date_current": "2026-07-01",
        "endpoint_value_current": 130.658,
        "value": 3.3441430040338282,
        "methodology_id": "inflation_v1.0",
        "data_basis": "latest_revised_data"
      }
    }
  },
  "target": {
    "series_id": "PCEPI",
    "calculation_period": "2026-07-01",
    "headline_pce_yoy": 3.7011657214870874,
    "fed_objective_percent": 2.0,
    "target_gap_pp": 1.7011657214870874,
    "available": true,
    "evidence": {
      "concept_id": "us.pce.headline.price-index.sa.monthly",
      "provider": "FRED",
      "series_id": "PCEPI",
      "calculation_period": "2026-07-01",
      "transformation": "12m",
      "endpoint_date_current": "2026-07-01",
      "endpoint_date_past": "2025-07-01",
      "endpoint_value_current": 131.659,
      "endpoint_value_past": 126.96,
      "value": 3.7011657214870874,
      "methodology_id": "inflation_v1.0",
      "data_basis": "latest_revised_data"
    }
  },
  "headline": {
    "pce": {
      "series_id": "PCEPI",
      "calculation_period": "2026-07-01",
      "r_12m": 3.7011657214870874,
      "state": "MIXED"
    },
    "cpi": {
      "series_id": "CPIAUCSL",
      "calculation_period": "2026-08-01",
      "r_12m": 3.353016322755642,
      "state": "MIXED"
    }
  },
  "confirmation": {
    "series_id": "CPILFESL",
    "state": "MIXED",
    "relationship": "INCONCLUSIVE",
    "latest_common_period": "2026-07-01",
    "r_12m": 2.4461631786472537
  },
  "level_series": {
    "core_pce": {
      "series_id": "PCEPILFE",
      "title": "Personal Consumption Expenditures Excluding Food and Energy (Chain-Type Price Index)",
      "units": "Index 2017=100",
      "source": "FRED",
      "observations": [
        {
          "date": "2021-09-01",
          "value": 109.641
        },
        {
          "date": "2021-10-01",
          "value": 110.188
        },
        {
          "date": "2021-11-01",
          "value": 110.77
        },
        {
          "date": "2021-12-01",
          "value": 111.418
        },
        {
          "date": "2022-01-01",
          "value": 111.976
        },
        {
          "date": "2022-02-01",
          "value": 112.468
        },
        {
          "date": "2022-03-01",
          "value": 112.914
        },
        {
          "date": "2022-04-01",
          "value": 113.307
        },
        {
          "date": "2022-05-01",
          "value": 113.703
        },
        {
          "date": "2022-06-01",
          "value": 114.376
        },
        {
          "date": "2022-07-01",
          "value": 114.628
        },
        {
          "date": "2022-08-01",
          "value": 115.276
        },
        {
          "date": "2022-09-01",
          "value": 115.788
        },
        {
          "date": "2022-10-01",
          "value": 116.204
        },
        {
          "date": "2022-11-01",
          "value": 116.539
        },
        {
          "date": "2022-12-01",
          "value": 116.952
        },
        {
          "date": "2023-01-01",
          "value": 117.505
        },
        {
          "date": "2023-02-01",
          "value": 117.929
        },
        {
          "date": "2023-03-01",
          "value": 118.315
        },
        {
          "date": "2023-04-01",
          "value": 118.734
        },
        {
          "date": "2023-05-01",
          "value": 119.083
        },
        {
          "date": "2023-06-01",
          "value": 119.39
        },
        {
          "date": "2023-07-01",
          "value": 119.556
        },
        {
          "date": "2023-08-01",
          "value": 119.689
        },
        {
          "date": "2023-09-01",
          "value": 120.058
        },
        {
          "date": "2023-10-01",
          "value": 120.241
        },
        {
          "date": "2023-11-01",
          "value": 120.374
        },
        {
          "date": "2023-12-01",
          "value": 120.592
        },
        {
          "date": "2024-01-01",
          "value": 121.217
        },
        {
          "date": "2024-02-01",
          "value": 121.537
        },
        {
          "date": "2024-03-01",
          "value": 122.009
        },
        {
          "date": "2024-04-01",
          "value": 122.304
        },
        {
          "date": "2024-05-01",
          "value": 122.383
        },
        {
          "date": "2024-06-01",
          "value": 122.677
        },
        {
          "date": "2024-07-01",
          "value": 122.911
        },
        {
          "date": "2024-08-01",
          "value": 123.128
        },
        {
          "date": "2024-09-01",
          "value": 123.466
        },
        {
          "date": "2024-10-01",
          "value": 123.832
        },
        {
          "date": "2024-11-01",
          "value": 123.962
        },
        {
          "date": "2024-12-01",
          "value": 124.196
        },
        {
          "date": "2025-01-01",
          "value": 124.587
        },
        {
          "date": "2025-02-01",
          "value": 125.145
        },
        {
          "date": "2025-03-01",
          "value": 125.267
        },
        {
          "date": "2025-04-01",
          "value": 125.502
        },
        {
          "date": "2025-05-01",
          "value": 125.79
        },
        {
          "date": "2025-06-01",
          "value": 126.121
        },
        {
          "date": "2025-07-01",
          "value": 126.43
        },
        {
          "date": "2025-08-01",
          "value": 126.714
        },
        {
          "date": "2025-09-01",
          "value": 126.954
        },
        {
          "date": "2025-10-01",
          "value": 127.243
        },
        {
          "date": "2025-11-01",
          "value": 127.469
        },
        {
          "date": "2025-12-01",
          "value": 127.886
        },
        {
          "date": "2026-01-01",
          "value": 128.455
        },
        {
          "date": "2026-02-01",
          "value": 128.961
        },
        {
          "date": "2026-03-01",
          "value": 129.343
        },
        {
          "date": "2026-04-01",
          "value": 129.681
        },
        {
          "date": "2026-05-01",
          "value": 130.147
        },
        {
          "date": "2026-06-01",
          "value": 130.338
        },
        {
          "date": "2026-07-01",
          "value": 130.658
        }
      ]
    },
    "headline_cpi": {
      "series_id": "CPIAUCSL",
      "title": "Consumer Price Index for All Urban Consumers: All Items in U.S. City Average",
      "units": "Index 1982-1984=100",
      "source": "FRED",
      "observations": [
        {
          "date": "2021-09-01",
          "value": 273.91
        },
        {
          "date": "2021-10-01",
          "value": 276.55
        },
        {
          "date": "2021-11-01",
          "value": 278.919
        },
        {
          "date": "2021-12-01",
          "value": 280.845
        },
        {
          "date": "2022-01-01",
          "value": 282.543
        },
        {
          "date": "2022-02-01",
          "value": 284.5
        },
        {
          "date": "2022-03-01",
          "value": 287.674
        },
        {
          "date": "2022-04-01",
          "value": 288.561
        },
        {
          "date": "2022-05-01",
          "value": 291.298
        },
        {
          "date": "2022-06-01",
          "value": 294.957
        },
        {
          "date": "2022-07-01",
          "value": 294.913
        },
        {
          "date": "2022-08-01",
          "value": 295.097
        },
        {
          "date": "2022-09-01",
          "value": 296.349
        },
        {
          "date": "2022-10-01",
          "value": 298.007
        },
        {
          "date": "2022-11-01",
          "value": 298.786
        },
        {
          "date": "2022-12-01",
          "value": 298.832
        },
        {
          "date": "2023-01-01",
          "value": 300.42
        },
        {
          "date": "2023-02-01",
          "value": 301.45
        },
        {
          "date": "2023-03-01",
          "value": 301.821
        },
        {
          "date": "2023-04-01",
          "value": 302.845
        },
        {
          "date": "2023-05-01",
          "value": 303.334
        },
        {
          "date": "2023-06-01",
          "value": 304.014
        },
        {
          "date": "2023-07-01",
          "value": 304.609
        },
        {
          "date": "2023-08-01",
          "value": 306.082
        },
        {
          "date": "2023-09-01",
          "value": 307.276
        },
        {
          "date": "2023-10-01",
          "value": 307.696
        },
        {
          "date": "2023-11-01",
          "value": 308.148
        },
        {
          "date": "2023-12-01",
          "value": 308.741
        },
        {
          "date": "2024-01-01",
          "value": 309.698
        },
        {
          "date": "2024-02-01",
          "value": 310.967
        },
        {
          "date": "2024-03-01",
          "value": 312.345
        },
        {
          "date": "2024-04-01",
          "value": 313.023
        },
        {
          "date": "2024-05-01",
          "value": 313.175
        },
        {
          "date": "2024-06-01",
          "value": 313.044
        },
        {
          "date": "2024-07-01",
          "value": 313.569
        },
        {
          "date": "2024-08-01",
          "value": 314.062
        },
        {
          "date": "2024-09-01",
          "value": 314.732
        },
        {
          "date": "2024-10-01",
          "value": 315.631
        },
        {
          "date": "2024-11-01",
          "value": 316.528
        },
        {
          "date": "2024-12-01",
          "value": 317.604
        },
        {
          "date": "2025-01-01",
          "value": 318.961
        },
        {
          "date": "2025-02-01",
          "value": 319.679
        },
        {
          "date": "2025-03-01",
          "value": 319.785
        },
        {
          "date": "2025-04-01",
          "value": 320.302
        },
        {
          "date": "2025-05-01",
          "value": 320.62
        },
        {
          "date": "2025-06-01",
          "value": 321.435
        },
        {
          "date": "2025-07-01",
          "value": 322.169
        },
        {
          "date": "2025-08-01",
          "value": 323.291
        },
        {
          "date": "2025-09-01",
          "value": 324.245
        },
        {
          "date": "2025-10-01",
          "value": null
        },
        {
          "date": "2025-11-01",
          "value": 325.063
        },
        {
          "date": "2025-12-01",
          "value": 326.031
        },
        {
          "date": "2026-01-01",
          "value": 326.588
        },
        {
          "date": "2026-02-01",
          "value": 327.46
        },
        {
          "date": "2026-03-01",
          "value": 330.293
        },
        {
          "date": "2026-04-01",
          "value": 332.407
        },
        {
          "date": "2026-05-01",
          "value": 333.979
        },
        {
          "date": "2026-06-01",
          "value": 332.568
        },
        {
          "date": "2026-07-01",
          "value": 332.813
        },
        {
          "date": "2026-08-01",
          "value": 334.131
        }
      ]
    }
  },
  "state_history": [
    {
      "evaluation_period": "2026-07-01",
      "state": "MIXED",
      "replay_outcome": "MATCH"
    },
    {
      "evaluation_period": "2026-06-01",
      "state": "MIXED",
      "replay_outcome": "MATCH"
    },
    {
      "evaluation_period": "2026-05-01",
      "state": "HEATING",
      "replay_outcome": "MATCH"
    },
    {
      "evaluation_period": "2026-04-01",
      "state": "HEATING",
      "replay_outcome": "MATCH"
    },
    {
      "evaluation_period": "2026-03-01",
      "state": "HEATING",
      "replay_outcome": "MATCH"
    },
    {
      "evaluation_period": "2026-02-01",
      "state": "HEATING",
      "replay_outcome": "MATCH"
    },
    {
      "evaluation_period": "2026-01-01",
      "state": "HEATING",
      "replay_outcome": "MATCH"
    },
    {
      "evaluation_period": "2025-12-01",
      "state": "MIXED",
      "replay_outcome": "MATCH"
    },
    {
      "evaluation_period": "2025-11-01",
      "state": "COOLING",
      "replay_outcome": "MATCH"
    },
    {
      "evaluation_period": "2025-10-01",
      "state": "MIXED",
      "replay_outcome": "MATCH"
    },
    {
      "evaluation_period": "2025-09-01",
      "state": "COOLING",
      "replay_outcome": "MATCH"
    },
    {
      "evaluation_period": "2025-08-01",
      "state": "MIXED",
      "replay_outcome": "MATCH"
    }
  ]
};
