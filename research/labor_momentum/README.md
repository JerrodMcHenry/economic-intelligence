# Labor Momentum Methodology Validation

Isolated research code for Increments #20A.1, #20A.2, and #20A.3.
**Not part of the production application.** `app/` must never import
anything from this directory, and nothing here is reachable from any
HTTP endpoint. No production code, migration, test, or frontend file
was touched to produce any of the three.

## Frozen methodology

**`LABOR_V1_FROZEN_METHODOLOGY.md`** (Increment #20A.3) is the
normative specification `labor_v1.0` — the document any future
implementation increment (`#20B`) must implement exactly. It
transcribes the validated formulas/tables directly from
`methodology_v2.py`'s actual committed code (not from prose summaries
of it), corrects one genuine error caught while writing it (the PAYEMS
revision-propagation affected-horizon set is a sparse `{0,3,6}`, not
either previously-reported contiguous range — see its own §13 for the
full account), and records the rejected-then-fixed methodology history
permanently.

## Result

**#20A.1** found the original `employment_momentum` formula
(comparing 3M/6M average monthly PAYEMS change against a rolling
12M-average baseline) had two confirmed, data-verified structural
defects and returned **STOP — CANONICAL FORMULA NEEDS REDESIGN**. See
`METHODOLOGY_VALIDATION.md`.

**#20A.2** redesigned the payroll formula (condition/momentum
separation, non-overlapping 3M-vs-prior-3M windows, sign-aware
classification, a new `RECOVERING` state) and re-validated it against
the same history plus a predeclared synthetic scenario matrix. Both
confirmed #20A.1 failures are resolved, full-history top-level MIXED
drops from 83.6% to 43.6%, and no new absurdity was found across every
named historical regime, run with no COVID special-casing. Result:
**GO — redesigned employment methodology ready to recommend for
freeze**, condition/momentum deadband = 50,000 jobs/month each. UNRATE
is unchanged (#20A.1 found no defect in it, and #20A.2's own evidence
does not support an unemployment-horizon mismatch severe enough to
require redesign either). See `METHODOLOGY_REDESIGN.md`.

## Contents

- `fetch_data.py` — one-off data acquisition via FRED's public
  `fredgraph.csv` export (no API key, no `.env`, no project secret --
  see that file's own docstring for why this deliberately does NOT
  reuse `app.clients.fred.FREDClient`). Writes `data/*.csv` only.
  Shared by both studies.
- `methodology.py` — #20A.1's original, now-rejected formulas, kept
  exactly as validated (native PAYEMS thousands-of-persons unit) so
  its own results stay reproducible. Not used by any recommended
  methodology going forward.
- `methodology_v2.py` — #20A.2's redesigned condition/momentum
  formulas (Candidates A and B), the `EmploymentState`/`LaborState`
  combination tables, and the one-time PAYEMS thousands-to-persons
  conversion (with an assertion guard against ever mixing the two
  unit conventions -- see that module's own docstring).
- `metrics.py` — objective behavioral metrics (state distribution,
  transitions, durations, one-month reversals, disagreement, boundary-
  near frequency, sensitivity), shared by both studies. Deliberately
  contains no accuracy/precision/recall/F1/recession-prediction score
  of any kind.
- `regimes.py` — descriptive historical windows and NBER recession
  dates, used only as report structure and context overlay, never as a
  target label. Shared by both studies.
- `study.py` — #20A.1's orchestration, unchanged, still reproducible.
- `study_v2.py` — #20A.2's orchestration: synthetic scenarios, the two
  critical failure months, full-history distributions/churn for both
  redesigned candidates across a predeclared deadband grid, regime
  review, temporal responsiveness, and payroll scale.
- `outputs/` — generated CSVs from both studies (gitignored —
  regenerable from `data/*.csv`).
- `data/` — cached raw FRED CSVs (gitignored — regenerable by
  re-running `fetch_data.py`).
- `METHODOLOGY_VALIDATION.md` — #20A.1's full findings report.
- `METHODOLOGY_REDESIGN.md` — #20A.2's full findings report.

## Running the studies

```
.venv/bin/python research/labor_momentum/fetch_data.py   # once, or to refresh (shared)
.venv/bin/python -m research.labor_momentum.study          # #20A.1
.venv/bin/python -m research.labor_momentum.study_v2        # #20A.2
```

## Latest-revised-data limitation

Both studies use ONLY the latest-revised historical observations FRED
serves today. Neither evaluates what a real-time system would have
said using vintage (as-originally-published) data, and no claim of
real-time predictive/detection performance is made anywhere in either
study.

## What this is not

`labor_v1.0` is now a frozen methodology specification
(`LABOR_V1_FROZEN_METHODOLOGY.md`), but it is still only a
specification — this directory contains no implemented Labor Monitor.
`app/` has no Labor module of any kind as of this increment; building
one is a separate, not-yet-authorized task (`#20B`).
