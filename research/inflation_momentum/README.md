# Inflation Momentum Methodology Study

Isolated research code. **Not part of the production application.**
`app/` must never import anything from this directory (enforced by
`tests/research/test_inflation_momentum.py`'s architectural guard), and
nothing here is reachable from any HTTP endpoint.

## Contents

- `fetch_data.py` — one-off data acquisition, reusing the existing
  `app.clients.fred.FREDClient` directly. Writes to `data/*.json` only
  — never to the production PostgreSQL database. Run manually to
  refresh the cache; not run automatically by tests or the study.
- `methodology.py` — deterministic transformation math (compounded
  annualized rates) and the four candidate classification families.
- `metrics.py` — objective behavioral metrics (churn, duration,
  reversals, whipsaws, cross-measure agreement), defined once and
  applied identically to every candidate.
- `regimes.py` — descriptive historical period windows (not
  hindsight-optimized ground truth) for the responsiveness analysis.
- `study.py` — orchestrates everything above and writes every result to
  `outputs/` as CSV/JSON. Deterministic: run it twice against the same
  cached data, get byte-identical files.
- `outputs/` — generated study artifacts (gitignored — regenerable from
  `data/*.json` by re-running `study.py`; not committed as a large,
  effectively-derived dataset).
- `STUDY_RESULTS.md` — the full findings report.

## Running the study

```
.venv/bin/python research/inflation_momentum/fetch_data.py   # once, or to refresh
.venv/bin/python research/inflation_momentum/study.py
```

Tests: `pytest tests/research/` (pure, offline, no network, no database).

## What this is not

This is evidence for human methodology review, not an implemented
product feature. No methodology is selected here. See
`STUDY_RESULTS.md`'s "Questions Requiring Human Decision" section.
