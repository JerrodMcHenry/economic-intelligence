/**
 * JOBS WORLD PROTOTYPE DATA (#51A).
 *
 * ================================================================
 * EVERY FIGURE IS REAL AND NONE OF IT IS LIVE
 * ================================================================
 *
 * Captured from four real endpoints on the running local API: the
 * labor monitor, 60 monthly PAYEMS observations, 60 monthly UNRATE
 * observations, and twelve recorded states.
 *
 * NOTHING HERE IS COMPUTED BY THIS FILE. No average, no delta, no
 * deadband test, no state. `labor_v1.0` computed all of it; the two
 * series are the provider's own observations. This is transport.
 *
 * WHAT IS DELIBERATELY ABSENT: participation, the U-6 rate, job
 * openings and initial claims. Every one of those returns 404 from
 * this API today. A page about how hard it is to find a job would
 * want them, and the prototype documents the gap rather than
 * simulating it.
 */
window.JOBS = {
  "_note": "SNAPSHOT of the MacroChipz API captured from the running local instance. Real values, real observation dates, real FRED attribution. NOT LIVE: the prototype is served from the filesystem and the API sends no Access-Control-Allow-Origin header.",
  "_captured_at": "2026-09-24T02:44:22+00:00",
  "_endpoints": [
    "GET /api/v1/monitors/labor",
    "GET /api/v1/series/PAYEMS/observations?limit=200",
    "GET /api/v1/series/UNRATE/observations?limit=200",
    "GET /api/v1/monitors/labor/history?limit=12&offset=0"
  ],
  "methodology_id": "labor_v1.0",
  "data_basis": "latest_revised_data",
  "state": "MIXED",
  "evaluation_period": "2026-08-01",
  "employment": {
    "series_id": "PAYEMS",
    "current_3m_avg_jobs": 71333.33333333333,
    "prior_3m_avg_jobs": 141666.66666666666,
    "momentum_delta_jobs": -70333.33333333333,
    "condition_deadband_jobs": 50000.0,
    "momentum_deadband_jobs": 50000.0,
    "condition": "EXPANDING",
    "momentum": "WORSENING",
    "state": "COOLING",
    "observations": [
      {
        "concept_id": "us.nonfarm.payroll-employment.sa.monthly",
        "provider": "FRED",
        "series_id": "PAYEMS",
        "observation_date": "2026-08-01",
        "value": 159075000.0
      },
      {
        "concept_id": "us.nonfarm.payroll-employment.sa.monthly",
        "provider": "FRED",
        "series_id": "PAYEMS",
        "observation_date": "2026-07-01",
        "value": 158913000.0
      },
      {
        "concept_id": "us.nonfarm.payroll-employment.sa.monthly",
        "provider": "FRED",
        "series_id": "PAYEMS",
        "observation_date": "2026-06-01",
        "value": 158892000.0
      },
      {
        "concept_id": "us.nonfarm.payroll-employment.sa.monthly",
        "provider": "FRED",
        "series_id": "PAYEMS",
        "observation_date": "2026-05-01",
        "value": 158861000.0
      },
      {
        "concept_id": "us.nonfarm.payroll-employment.sa.monthly",
        "provider": "FRED",
        "series_id": "PAYEMS",
        "observation_date": "2026-04-01",
        "value": 158798000.0
      },
      {
        "concept_id": "us.nonfarm.payroll-employment.sa.monthly",
        "provider": "FRED",
        "series_id": "PAYEMS",
        "observation_date": "2026-03-01",
        "value": 158650000.0
      },
      {
        "concept_id": "us.nonfarm.payroll-employment.sa.monthly",
        "provider": "FRED",
        "series_id": "PAYEMS",
        "observation_date": "2026-02-01",
        "value": 158436000.0
      }
    ]
  },
  "unemployment": {
    "series_id": "UNRATE",
    "current_3m_avg": 4.133333333333333,
    "prior_year_3m_avg": 4.233333333333333,
    "delta_pp": -0.10000000000000053,
    "unemployment_deadband_pp": 0.2,
    "state": "STABLE",
    "observations": [
      {
        "concept_id": "us.unemployment-rate.sa.monthly",
        "provider": "FRED",
        "series_id": "UNRATE",
        "observation_date": "2026-08-01",
        "value": 4.1
      },
      {
        "concept_id": "us.unemployment-rate.sa.monthly",
        "provider": "FRED",
        "series_id": "UNRATE",
        "observation_date": "2026-07-01",
        "value": 4.1
      },
      {
        "concept_id": "us.unemployment-rate.sa.monthly",
        "provider": "FRED",
        "series_id": "UNRATE",
        "observation_date": "2026-06-01",
        "value": 4.2
      },
      {
        "concept_id": "us.unemployment-rate.sa.monthly",
        "provider": "FRED",
        "series_id": "UNRATE",
        "observation_date": "2025-08-01",
        "value": 4.3
      },
      {
        "concept_id": "us.unemployment-rate.sa.monthly",
        "provider": "FRED",
        "series_id": "UNRATE",
        "observation_date": "2025-07-01",
        "value": 4.3
      },
      {
        "concept_id": "us.unemployment-rate.sa.monthly",
        "provider": "FRED",
        "series_id": "UNRATE",
        "observation_date": "2025-06-01",
        "value": 4.1
      }
    ]
  },
  "series": {
    "payems": {
      "series_id": "PAYEMS",
      "title": "All Employees, Total Nonfarm",
      "units": "Thousands of Persons",
      "source": "FRED",
      "observations": [
        {
          "date": "2021-09-01",
          "value": 147771.0
        },
        {
          "date": "2021-10-01",
          "value": 148572.0
        },
        {
          "date": "2021-11-01",
          "value": 149230.0
        },
        {
          "date": "2021-12-01",
          "value": 149816.0
        },
        {
          "date": "2022-01-01",
          "value": 150006.0
        },
        {
          "date": "2022-02-01",
          "value": 150825.0
        },
        {
          "date": "2022-03-01",
          "value": 151315.0
        },
        {
          "date": "2022-04-01",
          "value": 151623.0
        },
        {
          "date": "2022-05-01",
          "value": 151924.0
        },
        {
          "date": "2022-06-01",
          "value": 152358.0
        },
        {
          "date": "2022-07-01",
          "value": 153072.0
        },
        {
          "date": "2022-08-01",
          "value": 153362.0
        },
        {
          "date": "2022-09-01",
          "value": 153582.0
        },
        {
          "date": "2022-10-01",
          "value": 153939.0
        },
        {
          "date": "2022-11-01",
          "value": 154242.0
        },
        {
          "date": "2022-12-01",
          "value": 154342.0
        },
        {
          "date": "2023-01-01",
          "value": 154776.0
        },
        {
          "date": "2023-02-01",
          "value": 155066.0
        },
        {
          "date": "2023-03-01",
          "value": 155134.0
        },
        {
          "date": "2023-04-01",
          "value": 155375.0
        },
        {
          "date": "2023-05-01",
          "value": 155655.0
        },
        {
          "date": "2023-06-01",
          "value": 155880.0
        },
        {
          "date": "2023-07-01",
          "value": 156043.0
        },
        {
          "date": "2023-08-01",
          "value": 156261.0
        },
        {
          "date": "2023-09-01",
          "value": 156417.0
        },
        {
          "date": "2023-10-01",
          "value": 156576.0
        },
        {
          "date": "2023-11-01",
          "value": 156703.0
        },
        {
          "date": "2023-12-01",
          "value": 156857.0
        },
        {
          "date": "2024-01-01",
          "value": 157032.0
        },
        {
          "date": "2024-02-01",
          "value": 157238.0
        },
        {
          "date": "2024-03-01",
          "value": 157466.0
        },
        {
          "date": "2024-04-01",
          "value": 157530.0
        },
        {
          "date": "2024-05-01",
          "value": 157608.0
        },
        {
          "date": "2024-06-01",
          "value": 157695.0
        },
        {
          "date": "2024-07-01",
          "value": 157748.0
        },
        {
          "date": "2024-08-01",
          "value": 157757.0
        },
        {
          "date": "2024-09-01",
          "value": 157912.0
        },
        {
          "date": "2024-10-01",
          "value": 157945.0
        },
        {
          "date": "2024-11-01",
          "value": 158079.0
        },
        {
          "date": "2024-12-01",
          "value": 158316.0
        },
        {
          "date": "2025-01-01",
          "value": 158268.0
        },
        {
          "date": "2025-02-01",
          "value": 158310.0
        },
        {
          "date": "2025-03-01",
          "value": 158377.0
        },
        {
          "date": "2025-04-01",
          "value": 158485.0
        },
        {
          "date": "2025-05-01",
          "value": 158498.0
        },
        {
          "date": "2025-06-01",
          "value": 158478.0
        },
        {
          "date": "2025-07-01",
          "value": 158542.0
        },
        {
          "date": "2025-08-01",
          "value": 158472.0
        },
        {
          "date": "2025-09-01",
          "value": 158548.0
        },
        {
          "date": "2025-10-01",
          "value": 158408.0
        },
        {
          "date": "2025-11-01",
          "value": 158449.0
        },
        {
          "date": "2025-12-01",
          "value": 158432.0
        },
        {
          "date": "2026-01-01",
          "value": 158592.0
        },
        {
          "date": "2026-02-01",
          "value": 158436.0
        },
        {
          "date": "2026-03-01",
          "value": 158650.0
        },
        {
          "date": "2026-04-01",
          "value": 158798.0
        },
        {
          "date": "2026-05-01",
          "value": 158861.0
        },
        {
          "date": "2026-06-01",
          "value": 158892.0
        },
        {
          "date": "2026-07-01",
          "value": 158913.0
        },
        {
          "date": "2026-08-01",
          "value": 159075.0
        }
      ]
    },
    "unrate": {
      "series_id": "UNRATE",
      "title": "Unemployment Rate",
      "units": "Percent",
      "source": "FRED",
      "observations": [
        {
          "date": "2021-09-01",
          "value": 4.7
        },
        {
          "date": "2021-10-01",
          "value": 4.5
        },
        {
          "date": "2021-11-01",
          "value": 4.1
        },
        {
          "date": "2021-12-01",
          "value": 3.9
        },
        {
          "date": "2022-01-01",
          "value": 4.0
        },
        {
          "date": "2022-02-01",
          "value": 3.9
        },
        {
          "date": "2022-03-01",
          "value": 3.7
        },
        {
          "date": "2022-04-01",
          "value": 3.7
        },
        {
          "date": "2022-05-01",
          "value": 3.6
        },
        {
          "date": "2022-06-01",
          "value": 3.6
        },
        {
          "date": "2022-07-01",
          "value": 3.5
        },
        {
          "date": "2022-08-01",
          "value": 3.6
        },
        {
          "date": "2022-09-01",
          "value": 3.5
        },
        {
          "date": "2022-10-01",
          "value": 3.6
        },
        {
          "date": "2022-11-01",
          "value": 3.6
        },
        {
          "date": "2022-12-01",
          "value": 3.5
        },
        {
          "date": "2023-01-01",
          "value": 3.5
        },
        {
          "date": "2023-02-01",
          "value": 3.6
        },
        {
          "date": "2023-03-01",
          "value": 3.5
        },
        {
          "date": "2023-04-01",
          "value": 3.4
        },
        {
          "date": "2023-05-01",
          "value": 3.6
        },
        {
          "date": "2023-06-01",
          "value": 3.6
        },
        {
          "date": "2023-07-01",
          "value": 3.5
        },
        {
          "date": "2023-08-01",
          "value": 3.7
        },
        {
          "date": "2023-09-01",
          "value": 3.7
        },
        {
          "date": "2023-10-01",
          "value": 3.9
        },
        {
          "date": "2023-11-01",
          "value": 3.7
        },
        {
          "date": "2023-12-01",
          "value": 3.8
        },
        {
          "date": "2024-01-01",
          "value": 3.7
        },
        {
          "date": "2024-02-01",
          "value": 3.9
        },
        {
          "date": "2024-03-01",
          "value": 3.9
        },
        {
          "date": "2024-04-01",
          "value": 3.9
        },
        {
          "date": "2024-05-01",
          "value": 3.9
        },
        {
          "date": "2024-06-01",
          "value": 4.1
        },
        {
          "date": "2024-07-01",
          "value": 4.2
        },
        {
          "date": "2024-08-01",
          "value": 4.2
        },
        {
          "date": "2024-09-01",
          "value": 4.1
        },
        {
          "date": "2024-10-01",
          "value": 4.1
        },
        {
          "date": "2024-11-01",
          "value": 4.2
        },
        {
          "date": "2024-12-01",
          "value": 4.1
        },
        {
          "date": "2025-01-01",
          "value": 4.0
        },
        {
          "date": "2025-02-01",
          "value": 4.2
        },
        {
          "date": "2025-03-01",
          "value": 4.2
        },
        {
          "date": "2025-04-01",
          "value": 4.2
        },
        {
          "date": "2025-05-01",
          "value": 4.3
        },
        {
          "date": "2025-06-01",
          "value": 4.1
        },
        {
          "date": "2025-07-01",
          "value": 4.3
        },
        {
          "date": "2025-08-01",
          "value": 4.3
        },
        {
          "date": "2025-09-01",
          "value": 4.4
        },
        {
          "date": "2025-10-01",
          "value": null
        },
        {
          "date": "2025-11-01",
          "value": 4.5
        },
        {
          "date": "2025-12-01",
          "value": 4.4
        },
        {
          "date": "2026-01-01",
          "value": 4.3
        },
        {
          "date": "2026-02-01",
          "value": 4.4
        },
        {
          "date": "2026-03-01",
          "value": 4.3
        },
        {
          "date": "2026-04-01",
          "value": 4.3
        },
        {
          "date": "2026-05-01",
          "value": 4.3
        },
        {
          "date": "2026-06-01",
          "value": 4.2
        },
        {
          "date": "2026-07-01",
          "value": 4.1
        },
        {
          "date": "2026-08-01",
          "value": 4.1
        }
      ]
    }
  },
  "state_history": [
    {
      "evaluation_period": "2027-10-01",
      "state": "INSUFFICIENT_DATA",
      "replay_outcome": "MATCH"
    },
    {
      "evaluation_period": "2027-09-01",
      "state": "INSUFFICIENT_DATA",
      "replay_outcome": "MATCH"
    },
    {
      "evaluation_period": "2027-08-01",
      "state": "INSUFFICIENT_DATA",
      "replay_outcome": "MATCH"
    },
    {
      "evaluation_period": "2027-07-01",
      "state": "INSUFFICIENT_DATA",
      "replay_outcome": "MATCH"
    },
    {
      "evaluation_period": "2027-06-01",
      "state": "INSUFFICIENT_DATA",
      "replay_outcome": "MATCH"
    },
    {
      "evaluation_period": "2027-05-01",
      "state": "INSUFFICIENT_DATA",
      "replay_outcome": "MATCH"
    },
    {
      "evaluation_period": "2027-04-01",
      "state": "INSUFFICIENT_DATA",
      "replay_outcome": "MATCH"
    },
    {
      "evaluation_period": "2027-03-01",
      "state": "INSUFFICIENT_DATA",
      "replay_outcome": "MATCH"
    },
    {
      "evaluation_period": "2027-02-01",
      "state": "INSUFFICIENT_DATA",
      "replay_outcome": "MATCH"
    },
    {
      "evaluation_period": "2027-01-01",
      "state": "INSUFFICIENT_DATA",
      "replay_outcome": "MATCH"
    },
    {
      "evaluation_period": "2026-12-01",
      "state": "INSUFFICIENT_DATA",
      "replay_outcome": "MATCH"
    },
    {
      "evaluation_period": "2026-11-01",
      "state": "INSUFFICIENT_DATA",
      "replay_outcome": "MATCH"
    }
  ]
};
