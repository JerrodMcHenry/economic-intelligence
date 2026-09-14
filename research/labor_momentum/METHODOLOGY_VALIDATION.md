# Labor Momentum Methodology Validation — Increment #20A.1

| | |
|---|---|
| Status | **NOT FROZEN — STOP, redesign required** |
| Scope | `employment_momentum` (PAYEMS) and `unemployment_trend` (UNRATE) only, exactly as specified by the #20A.1 prompt |
| Formulas changed during validation | No (one units-conversion bug in this study's own orchestration code was fixed — see "Errors and fixes" — the formula itself was never altered) |
| Data source | FRED public CSV export (`fredgraph.csv`), no API key |
| Data basis | Latest revised data only (see "Latest-revised-data limitation") |
| History | PAYEMS/UNRATE, 1990-01 through 2026-08 (latest available at time of study) |

## 1. Why this document exists

Increment #20A proposed an architecture (PAYEMS employment momentum +
UNRATE unemployment trend, JOLTS confirmation-only) and two provisional
tolerances (`δ_payroll = 50,000`, `δ_unemployment = 0.2pp`), explicitly
flagged as **not yet validated** against historical data the way
Inflation's own `δ = 0.10pp` was validated in `research/inflation_momentum/`
before being frozen. This document is that validation. Per its own
governing brief, this is methodology *validation*, not model fitting:
no threshold was chosen by searching for the best-looking historical
result, no accuracy/precision/recall/recession-prediction score was
computed, and the five-value candidate grid for each tolerance was
declared before any result was examined.

## 2. Data source and coverage

`PAYEMS` and `UNRATE`, downloaded via FRED's public, unauthenticated
`fredgraph.csv` export (the same CSV a browser gets from the "Download"
button on any FRED series page) — no `FRED_API_KEY`, no `.env`, no
project secret of any kind was read or required. `PAYEMS`: 1939-01
through 2026-08 (1,052 observations, all used from 1990-01 onward per
the brief's requested window). `UNRATE`: 1948-01 through 2026-08 (944
observations). One genuine missing observation was found in the cached
data — `UNRATE` for 2025-10 is blank in FRED's own export, coinciding
with a real BLS household-survey collection gap that month; this is
handled by the existing missing-data rule (that exact calendar month
is simply unavailable to any calculation needing it), not patched or
imputed.

## 3. Latest-revised-data limitation (stated prominently, as required)

Economic Intelligence does not maintain historical vintages. Every
number in this study is FRED's **current, latest-revised** value for
each historical month — including months whose original, as-first-
published values (before subsequent monthly re-estimates and, for
PAYEMS, the annual benchmark revision) were sometimes materially
different. **This study evaluates how `labor_v1.0`'s candidate
formulas behave when applied consistently to the latest-revised
series available today. It does NOT evaluate, and makes no claim
about, what a real-time system would have classified using the data
actually available at each historical point in time.** This is the
same explicit limitation Inflation's own methodology carries, restated
here because payroll's benchmark revision (see #20A §20) makes it more
consequential for this specific series.

## 4. Candidate thresholds (predeclared, unmodified after seeing results)

`δ_payroll ∈ {0, 25,000, 50,000, 75,000, 100,000}` jobs/month.
`δ_unemployment ∈ {0.0, 0.1, 0.2, 0.3, 0.4}` percentage points. 25
combinations, evaluated identically across the full history and five
named sub-windows (2000–2003, 2007–2010, 2015–2019, 2020–2022,
2022–latest). No candidate was added after inspecting results.

## 5. Errors and fixes (full disclosure)

**A real bug was found and fixed during this study's first run**, in
the study's own orchestration code — not in the formula as specified.
`PAYEMS` is natively expressed in **thousands of persons**, so
`avg_3m`/`avg_6m`/`avg_12m` (computed directly from PAYEMS's own
values) are themselves in thousands. The candidate deltas as declared
by the #20A.1 prompt (`25,000`, `50,000`, ...) are stated in whole
jobs. The first run of `study.py` passed those raw values directly
into the classification functions without converting to PAYEMS's
native unit — producing a tolerance band nominally "25,000" but
actually meaning 25,000 **thousand** jobs (25 million), a band no real
monthly average could ever fall outside of. The symptom was
unambiguous and caught immediately: **every `δ_payroll ≥ 25,000`
produced 0% STRENGTHENING and 0% COOLING across all 36 years of
history.** Fixed by converting every declared payroll-delta candidate
to PAYEMS's native thousands-of-jobs unit (`÷ 1,000`) before it
reaches `classify_employment_momentum` — see `study.py`'s own
`to_native_payroll_units` and its docstring. All results in this
document reflect the corrected code; the pre-fix numbers were
discarded, not reported.

## 6. Payroll structural analysis — **two confirmed defects**

### 6.1 Not sign-aware: "STRENGTHENING" during ongoing, substantial job losses

Real 2009 data, `δ_payroll = 50,000` (the proposed value):

| period | avg_3m | avg_6m | avg_12m | classification |
|---|---|---|---|---|
| 2009-08 | **−331,333** | −474,333 | −561,583 | **STRENGTHENING** |
| 2009-09 | **−254,000** | −374,667 | −542,833 | **STRENGTHENING** |
| 2009-10 | **−200,333** | −293,500 | −519,167 | **STRENGTHENING** |

August 2009: the U.S. economy lost roughly 331,000 jobs on average
over the prior three months — and the methodology, exactly as
specified, labels this "STRENGTHENING." The formula only compares
`avg_3m`/`avg_6m` to a tolerance band around `avg_12m` — it never
checks whether `avg_3m` is itself positive (net hiring) or negative
(net job losses). A deceleration of contraction is a real, legitimate
economic signal (an early-warning "less bad" reading), but labeling it
identically to genuine job growth is a material overclaim a reader
would reasonably find misleading.

### 6.2 Rolling 12-month baseline contamination after an extreme shock

Real 2021 data, `δ_payroll = 50,000`:

| period | avg_3m | avg_12m (baseline) | classification |
|---|---|---|---|
| 2021-04 | **+574,667** | 1,180,083 | **COOLING** |
| 2021-05 | **+561,667** | 1,002,083 | **COOLING** |
| 2021-06 | +529,333 | 679,083 | **COOLING** |

April–June 2021: the U.S. economy added roughly 530,000–575,000 jobs
per month on average — among the strongest sustained monthly job-gain
readings in the entire 1990–2026 historical record — and the
methodology labels this **"COOLING."** The cause is mechanical: the
rolling 12-month baseline at this point still contains the 2020
collapse-and-rebound months (a −7.2 million single-month low followed
by multi-million-job rebound months), inflating `avg_12m` to
1,000,000–1,180,000/month — a figure no ordinary expansion has ever
sustained — against which genuinely robust growth looks weak by pure
arithmetic comparison. The full `covid_contamination.csv` output shows
this distortion (state flips driven by the contaminated baseline
rather than genuine economic change) persisting from 2020-04 through
at least 2022-05 — a full **25 months**, consistent with this study's
own #20A-derived structural prediction (a shock's influence on the
12-month AVERAGE baseline propagates for up to 12 months per
occurrence, and 2020 had multiple extreme months in sequence,
compounding the window).

### 6.3 Diagnostic: does a simple, sign-aware alternative avoid both defects?

Per the brief's allowance to compare one or two simple alternatives
*for diagnosis only* once a structural defect is found (never as a
silent replacement): a lightweight, sign-aware 3M-vs-6M comparison
(`avg_3m > 0` required for any "strengthening" label; direction judged
by `avg_3m` vs. `avg_6m` rather than vs. the shock-prone `avg_12m`)
was checked against the same critical months:

| period | avg_3m | avg_6m | sign-aware would say | #20A.1 formula said |
|---|---|---|---|---|
| 2009-08 | −331,333 | −474,333 | decelerating **contraction** (not positive) | STRENGTHENING |
| 2021-04 | +574,667 | +354,500 | accelerating **growth** (positive, 3m > 6m) | COOLING |
| 2021-05 | +561,667 | +388,667 | accelerating **growth** | COOLING |

The diagnostic avoids both confirmed defects on these exact months —
not proof that this specific alternative is the right redesign, but
concrete evidence that **the defects are fixable with a structurally
different (not merely re-tuned) formula**, supporting a redesign
recommendation over an "insufficient evidence" one.

## 7. Unemployment structural analysis

Spot-checked against the two clearest historical turning points
available in this window, at `δ_unemployment = 0.2pp`:

- **2001 recession** (NBER start: 2001-03): `state` flips to
  DETERIORATING exactly in **2001-03**, the recession's own official
  start month.
- **2007–2009 recession** (NBER start: 2007-12): `state` flips to
  DETERIORATING in **2007-11**, one month *ahead* of the official
  start.

No evidence of the "steadily deteriorating but still looks better than
a year ago" pathology named as a risk in the #20A.1 brief was found in
either spot check — both turning points are caught promptly, not
lagged. **`unemployment_trend`, as specified, is not judged to need
redesign based on this study's evidence** — the confirmed structural
defects are isolated to `employment_momentum`.

## 8. COVID contamination analysis

See §6.2 above for the concrete finding. Summary: the extreme
2020-03–2021-06 window is NOT removed from the canonical sequence
anywhere in this study (per the brief's explicit instruction) — it
remains, and its mechanical effect on the rolling 12-month payroll
baseline is the direct, confirmed cause of a genuinely misleading
COOLING label on some of the strongest job-growth months in the
historical record. This is reported as a structural finding, not
patched by adjusting `δ_payroll` (a wider or narrower band around an
already-contaminated baseline does not fix a contaminated baseline).

## 9. Payroll-scale-over-decades analysis

`50,000 / PAYEMS_level` (jobs, as a percent of total nonfarm
employment), at representative dates:

| period | PAYEMS level (thousands) | 50K as % of level |
|---|---|---|
| 1990-01 | 109,196 | 0.0458% |
| 2000-01 | 131,011 | 0.0382% |
| 2010-01 | 129,802 | 0.0385% |
| 2020-01 | 152,031 | 0.0329% |
| 2026-08 | 159,075 | 0.0314% |

A fixed 50,000-job tolerance has shrunk from ~0.046% to ~0.031% of
total employment over 36 years — a real, ~31% relative drift, exactly
the concern #20A raised. This is a genuine, worth-tracking structural
consideration for a future frozen version, but on its own it is
**not** severe enough over a 36-year window to independently justify a
STOP — it is a secondary finding beside §6's two confirmed defects,
noted here for completeness and for whoever redesigns this formula
next.

## 10. State distributions by candidate (full history, all 25 combinations)

Full table in `outputs/state_distribution_by_candidate.csv`. At the
proposed pair (`δ_payroll=50,000`, `δ_unemployment=0.2`): STRENGTHENING
2.50%, COOLING 7.50%, STABLE 5.68%, MIXED **83.64%**, INSUFFICIENT_DATA
0.68%. MIXED dominates at **every** candidate combination tested and
in **every** analytical sub-window (ranging 70.8%–94.6% MIXED across
the 25×6 grid) — never once does any candidate pair produce a
"typical" month landing cleanly in STRENGTHENING/COOLING/STABLE more
often than in MIXED.

## 11. Transition/churn analysis

At the proposed pair, full history: 51 top-level state transitions
over 440 months, 14 of them one-month reversals (A→B→A). Sub-state
churn is markedly asymmetric: `employment_momentum`'s own MIXED rate
is 25.23% (its dual-confirmation, 3m-vs-6m-vs-band structure genuinely
disagrees with itself a quarter of the time at this tolerance), while
`unemployment_trend` never internally disagrees by construction (a
single comparison has no internal-MIXED state) — see §12.

## 12. Disagreement/MIXED analysis — a second, systemic contributor

Active opposite-direction disagreement (one owner STRENGTHENING/
IMPROVING, the other COOLING/DETERIORATING) accounts for only 10.76 of
the 83.64 MIXED percentage points at the proposed pair — the
**majority** of MIXED months are not active disagreement but a
"neither side lands on the exact same cell" outcome, driven by a real
asymmetry in how often each owner reaches STABLE: at
`δ_payroll=50,000`, `employment_momentum` is STABLE 51.36% of the
time, while at `δ_unemployment=0.2`, `unemployment_trend` is STABLE
only 12.95% of the time (IMPROVING dominates at 58.18%, simply because
most of U.S. economic history is expansion, not contraction). The two
owners' "quiet" states rarely land in the same month because their
underlying definitions have structurally different baselines (a
self-updating rolling average for payrolls vs. a fixed year-ago point
for unemployment) — a second, independent contributor to MIXED-
dominance beside §6's direct defects, worth the redesign's attention
but not itself a blocking defect the way §6 is.

## 13. Threshold sensitivity

`δ_payroll`: moving 0→25,000 changes 16.8% of all months' top-level
state; 25,000→50,000 changes 13.9%; 50,000→75,000 changes 5.2%;
75,000→100,000 changes 5.0% — sensitivity clearly decreases as the
band widens, with no single step producing an implausible jump.
`δ_unemployment`: 0.0→0.1 changes 2.3%; 0.1→0.2 changes 4.6%; 0.2→0.3
changes 10.7%; 0.3→0.4 changes 8.0% — a mild, not alarming, uptick in
sensitivity around 0.2–0.3pp. Neither axis shows chaotic, cliff-like
behavior at the proposed values; the *number of transitions* problem
found in this study is not a sensitivity/threshold problem at all
(see §6, §12) — no choice within this predeclared grid resolves it.

## 14. Historical regime review

Full month-by-month detail in `outputs/regime_review.csv` for all
eight named regimes. Headline findings: the depths of the 2007–2009
recession (2008-05 through 2009-05) are classified **COOLING** cleanly
and without a single reversal — a genuinely reassuring result showing
the methodology is NOT broken at its core, it correctly and
confidently recognizes an unambiguous, severe contraction. The
2009-06–2009-12 "jobless recovery" period (payrolls still shrinking,
unemployment still rising) correctly resolves to MIXED — an honest,
economically defensible read of a genuinely transitional period, not
a flaw. The COVID collapse (2020-03/04) is correctly, immediately
COOLING. The two confirmed defects (§6) both manifest inside the
"COVID rehiring surge" and following regime windows in this table.

## 15. Proposed δ_payroll = 50,000 assessment

Statistically well-grounded on its own terms (§20A §17 — BLS's own
published ±122,000 90% CI for a one-month change, conservatively
scaled for a 3-month average) and shows reasonable, non-chaotic
sensitivity behavior (§13). **It cannot rescue the formula it is
plugged into** — §6's two defects occur regardless of which of the
five predeclared payroll tolerances is chosen (the diagnostic table in
§6.1/§6.2 used 50,000 specifically, but the defects are structural to
comparing against a sign-blind, shock-prone `avg_12m`, not an artifact
of this particular band width).

## 16. Proposed δ_unemployment = 0.2pp assessment

Also well-grounded (§20A §17) and, unlike its payroll counterpart, is
paired with a formula that passed both historical spot-checks in §7
without incident. No defect was found that would require abandoning
`unemployment_trend`'s current structure. This tolerance can likely
carry forward largely as-is once the payroll side is redesigned and
re-validated together.

## 17. JOLTS deadband research

Per the brief, this turn does not tune JOLTS. A brief check for a
published JOLTS-rate sampling-error figure analogous to BLS's own
PAYEMS/UNRATE confidence intervals (§20A §17) did not surface an
authoritative, readily-citable BLS figure of the same caliber within
this turn's scope — JOLTS is a newer, smaller survey with materially
less publicly-discussed measurement-error literature than the flagship
CES/CPS releases. **Recommendation: Option A — confirmation direction
with no numeric deadband** (or the smallest deliberately-provisional
deadband, clearly labeled as unvalidated) is preferable to inventing an
unfounded tolerance; Option B (defer confirmation entirely from #20B)
remains acceptable too. Given confirmation never owns canonical state,
this is explicitly **not** a blocker for the PAYEMS/UNRATE decision
below.

## 18. Structural flaws discovered (summary)

1. **`employment_momentum` is not sign-aware** — a month of net job
   LOSSES can be classified STRENGTHENING purely by deceleration
   relative to baseline (confirmed, 2009-08 through 2009-10).
2. **`employment_momentum`'s rolling 12-month baseline is contaminated
   by extreme shock months for well over a year afterward** — genuine,
   robust job growth can be classified COOLING purely by comparison to
   a shock-distorted baseline (confirmed, 2021-04 through at least
   2022-05, 25 consecutive months of demonstrated contamination
   effects in `covid_contamination.csv`).
3. Both defects share one root cause: an unmodified rolling AVERAGE
   used as a comparison baseline, with no sign-check and no robustness
   to extreme outlier months inside its own window.
4. A lightweight, sign-aware, shorter-window (3M-vs-6M) diagnostic
   avoids both defects on the exact months where the specified formula
   fails (§6.3) — evidence a redesign is tractable, not that the whole
   architecture (owners, confirmation role, combination table,
   missing-data rules, period alignment) needs to be reconsidered.
5. `unemployment_trend` shows no comparable defect in this study's
   spot checks (§7) and needs no redesign on the evidence gathered
   here.

## 19. Recommendation

**STOP — CANONICAL FORMULA NEEDS REDESIGN**, scoped narrowly:
`employment_momentum`'s comparison-to-rolling-12M-baseline formula, as
literally specified by #20A.1, must be redesigned before any
`δ_payroll` is frozen — no threshold in the predeclared grid, or
outside it, can repair a baseline that is itself sign-blind and
shock-contaminated. `unemployment_trend` and `δ_unemployment = 0.2pp`
are NOT implicated by this finding and do not need to be redesigned
alongside it; #20A's overall architecture (two owners, JOLTS
confirmation-only, missing-data rules, period alignment, evidence
schema) is likewise not implicated — the defect is narrow and
specific to one formula's own internal comparison logic.

## 20. Justification

Not a threshold-tuning outcome dressed up as a structural one: §6.1
and §6.2 each cite specific, real, latest-revised historical months
where the exact #20A.1-specified formula produces a classification a
reasonably informed reader would call actively misleading (calling
substantial ongoing job losses "STRENGTHENING"; calling some of the
strongest sustained job growth on record "COOLING"), and §6.3
demonstrates a structurally different (not merely re-tuned) approach
avoids both on the same months. This satisfies the brief's own bar for
STOP-B over STOP-C ("threshold evidence insufficient" would apply if
the formula looked coherent but no *number* could be defended; here
the formula itself is not coherent at any number in the tested range).

## 21. Remaining limitations

- Findings rest on **latest-revised** data only (§3) — not a claim
  about real-time performance.
- The §6.3 diagnostic is illustrative, not a fully-specified
  replacement formula — a genuine #20A redesign pass (with its own
  historical validation, mirroring this one) is still required before
  any new payroll formula is frozen.
- JOLTS deadband remains unresolved (§17), independently of this
  turn's PAYEMS/UNRATE finding.
- The §9 payroll-scale-over-decades drift (~31% relative shrinkage of
  a fixed 50K tolerance since 1990) was not independently blocking but
  should inform whatever redesign follows — a formula expressed as a
  fraction of contemporaneous employment, or one otherwise scale-
  robust, may resolve both this concern and §6 simultaneously.
- Unemployment's own structural soundness (§7) rests on two spot
  checks (2001, 2007–2008), not an exhaustive regime-by-regime audit
  the way payrolls received in §6 — reasonable given this study's
  time budget and the brief's own "do not spend this turn on JOLTS"
  prioritization, but worth a fuller look if payroll's redesign pass
  ends up touching the combination table too.

## 22. Reproducibility

```
.venv/bin/python research/labor_momentum/fetch_data.py
.venv/bin/python -m research.labor_momentum.study
```
Verified deterministic during this study: running `study.py` twice
against the same cached `data/*.csv` produced byte-identical files in
`outputs/` (`diff -q` clean across all seven output files).
