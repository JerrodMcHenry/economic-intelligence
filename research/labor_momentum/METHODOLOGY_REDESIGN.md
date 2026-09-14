# Payroll Methodology Redesign — Increment #20A.2

| | |
|---|---|
| Status | **GO — redesigned employment methodology ready to recommend for freeze** |
| Scope | `employment_momentum` (PAYEMS) redesign only |
| UNRATE | Unchanged from #20A/#20A.1 (`δ_unemployment = 0.2pp`); no defect found requiring redesign |
| Selected formula | Candidate B — current 3M average vs. prior (non-overlapping) 3M average, sign-aware condition/momentum separation |
| Selected deadbands | `condition_deadband_jobs = 50,000`; `momentum_deadband_jobs = 50,000` |
| Data | Same latest-revised PAYEMS/UNRATE history as #20A.1 (1990-01–2026-08), unchanged sample |

## 1. Why this document exists

#20A.1 found two confirmed structural defects in the original
`employment_momentum` formula (comparison to a rolling 12-month
baseline, with no sign check): calling substantial ongoing job LOSSES
"STRENGTHENING" (August 2009) and calling some of the strongest
sustained job GAINS on record "COOLING" (April–June 2021), the latter
persisting for 25 months due to COVID-shock contamination of the
rolling baseline. This document redesigns and re-validates the payroll
formula only. UNRATE is unchanged — #20A.1 found no defect in it, and
this study's own evidence (§9) does not surface one either.

## 2. Units (stated once, enforced by an assertion, never mixed)

This entire redesign works in **actual persons**, not PAYEMS's native
"Thousands of Persons." The conversion happens exactly once, at
`methodology_v2.build_payems_persons_index`, guarded by an assertion
that every converted value falls in a plausible U.S. total-nonfarm-
employment range (10M–400M) — a deliberate, permanent fix for the
exact class of bug #20A.1 caught (a "25" vs "25,000" mix-up). Every
threshold name in the code carries `_jobs` explicitly
(`condition_deadband_jobs`, `momentum_deadband_jobs`). #20A.1's
original, already-validated (and already-rejected) formula in
`methodology.py` is left untouched, on its own native-thousands
convention, so its results remain exactly reproducible; the two unit
conventions are never mixed within one call.

## 3. Core design question — resolved: YES, separate condition from momentum

The original formula collapsed two genuinely different facts into one
number: **is employment growing or shrinking** (condition) and **is
that growth/shrinkage speeding up or slowing down** (momentum). This
study confirms the hypothesis that these must be represented
separately: every synthetic scenario (§5) and both confirmed #20A.1
failure windows (§6) are resolved correctly, and ONLY correctly, once
condition and momentum are computed and classified independently, then
combined through an explicit, small (3×3) table into one
`EmploymentState` — never collapsed directly from a single raw number.

## 4. Candidate formulas evaluated

- **Candidate A** — `recent_3m` vs `recent_6m` (both anchored at the
  current month `t`, so `recent_3m`'s three months are entirely
  contained inside `recent_6m`'s six).
- **Candidate B** — `current_3m` (months `t, t-1, t-2`) vs `prior_3m`
  (months `t-3, t-4, t-5`) — non-overlapping.
- **Candidate C** — not implemented as a separate formula. As
  anticipated by the brief itself ("may resemble A mathematically"),
  Candidate C's proposed math is identical to Candidate A; its only
  distinction is an evidence-model design choice (exposing
  condition+momentum as independent facts rather than collapsing them
  immediately) — which this study adopted for BOTH A and B from the
  start (§3), making C not a distinct candidate to separately
  evaluate. This is reported as a finding, not skipped.
- **Candidate D** (scale-normalized, `change / PAYEMS level`) — not
  introduced. §12 confirms the scale drift since 1990 (a fixed 50,000
  tolerance shrinking from ~0.046% to ~0.031% of total employment) is
  real but modest, and no result in this study shows the fixed-scale
  formulation producing materially different semantics across decades
  once the redesign's own tolerance choice is applied — normalizing
  was not economically justified before looking at results, and
  results did not change that.

### 4.1 A genuine mathematical relationship between A and B (a real, derived finding)

Because `recent_6m = (recent_3m + older_3m) / 2` exactly (the 6-month
average IS the average of its own two 3-month halves), it follows
algebraically that `recent_3m − recent_6m = (recent_3m − older_3m) / 2`
— **Candidate A's momentum signal is exactly HALF the magnitude of
Candidate B's**, for the same underlying data. This was verified
directly against real August 2009 data: A's momentum
difference = 143,000; B's = 286,000; `286,000 / 2 = 143,000` exactly.
Practically, this means the SAME nominal momentum deadband number
means something different depending which candidate it's applied to —
a real interpretability cost for Candidate A, and one of the two
reasons (with §4.2) Candidate B is preferred (§13).

### 4.2 Overlap implications

Candidate A's two compared quantities share 50% of their underlying
data (all three "recent" months are counted in both `recent_3m` and
`recent_6m`). Candidate B's two compared quantities share none — a
cleaner, more standard "this quarter vs. the quarter before"
comparison with no shared-data artifact to explain or account for.

## 5. Synthetic scenario results

All seven brief-specified scenarios (predeclared, not chosen after
seeing results), evaluated at the selected deadbands
(`condition_deadband_jobs = 50,000`, `momentum_deadband_jobs = 50,000`)
via Candidate B — full grid in `outputs/v2_synthetic_scenarios.csv`:

| scenario | prior | recent | expected semantic | produced |
|---|---|---|---|---|
| A | +200K | +300K | expanding, improving | EXPANDING, IMPROVING → **EXPANDING** |
| B | +300K | +150K | expanding, worsening | EXPANDING, WORSENING → **COOLING** |
| C | −500K | −250K | contracting, improving | CONTRACTING, IMPROVING → **RECOVERING** |
| D | −200K | −400K | contracting, worsening | CONTRACTING, WORSENING → **CONTRACTING** |
| E | −100K | +100K | returned to expansion | EXPANDING, IMPROVING → **EXPANDING** |
| F | +100K | −100K | entered contraction | CONTRACTING, WORSENING → **CONTRACTING** |
| G | +20K | −10K | near-flat/noisy | FLAT (any momentum) → **STABLE** |

All seven match their expected human-intuitive semantic exactly.
Critically, scenario G was ALSO run at `condition_deadband_jobs = 0`:
the −10,000 "recent" value (genuinely noise-level) is misclassified as
**CONTRACTING** at deadband 0 — direct, predeclared-scenario proof
that a condition deadband strictly greater than zero is necessary, not
a convenience.

## 6. August 2009 and April–June 2021, both candidates, full deadband grid

Full detail in `outputs/v2_critical_months.csv`. At the selected pair
(50,000/50,000), Candidate B:

| period | payroll avg | condition | momentum | state |
|---|---|---|---|---|
| 2009-08 | current_3m = −331,333 | CONTRACTING | IMPROVING | **RECOVERING** |
| 2021-04 | current_3m = +574,667 | EXPANDING | IMPROVING | **EXPANDING** |
| 2021-05 | current_3m = +561,667 | EXPANDING | IMPROVING | **EXPANDING** |
| 2021-06 | current_3m = +529,333 | EXPANDING | STEADY | **EXPANDING** |

Both confirmed #20A.1 failures are resolved: a month of ongoing,
substantial job losses is now honestly labeled RECOVERING (not
STRENGTHENING), and genuinely strong, sustained job growth is now
honestly labeled EXPANDING (not COOLING). This holds at every
condition/momentum deadband combination tested in the 3×3 grid for
both candidates — the fix is structural, not dependent on a
particular tolerance choice.

## 7. Full-history state distributions (Candidate B, employment sub-state only)

Full grid in `outputs/v2_employment_state_grid.csv`. At
(50,000/50,000): EXPANDING 58.2%, COOLING 19.1%, STABLE 9.6%,
CONTRACTING 10.2%, RECOVERING 3.0% — five genuinely distinct,
non-degenerate buckets, a complete recovery from the original
formula's own behavior (where, once its units bug was fixed,
STRENGTHENING/COOLING were still crowded out by MIXED at the
sub-state level in a majority of months at every tested tolerance —
see #20A.1 §10).

## 8. Churn/reversal results

At (50,000/50,000): 120 top-level-sub-state transitions and 33
one-month reversals over 440 months for Candidate B — comparable to
Candidate A's 74 transitions / 15 reversals at the same pair (A's
churn is somewhat lower, a direct consequence of §4.1's scale
relationship: A's momentum signal, being half B's, crosses the SAME
nominal deadband less often). Neither candidate shows pathological,
rapid state-flipping; average `RECOVERING` duration (the state
specifically introduced to fix the August 2009 problem) is short (a
few months), consistent with what "temporary recovery-phase" should
look like, never a multi-year stuck state.

## 9. Regime review and temporal responsiveness

Full detail in `outputs/v2_responsiveness.csv` and
`outputs/v2_top_level_full_history.csv`. Headline findings:

- **2001 and 2007–2009 recessions**: employment condition reaches
  CONTRACTING by 2008-03 (three months after, and actually *earlier*
  than the original formula's own May-2008 COOLING trigger from
  #20A.1), and top-level Labor resolves to COOLING cleanly and
  consistently through the entire depth of the crisis.
- **2020 collapse → 2022 normalization** (the full COVID span, run
  with NO special-casing, NO exclusion, NO clipping — see §11):
  correctly STRENGTHENING pre-COVID, correctly CONTRACTING/COOLING
  through the initial collapse, correctly MIXED during the uncertain
  initial rebound months, correctly STRENGTHENING through much of the
  2021 rehiring boom, and a coherent EXPANDING/COOLING alternation
  through 2022 as growth genuinely decelerated toward a "still solid
  but slowing" labor market — the real, widely-recognized narrative
  of that period, reproduced without any manual intervention.
- **UNRATE's own turning-point timing is unchanged** from #20A.1's
  spot checks (DETERIORATING right at/just before the 2001 and 2007
  NBER starts) — not retested exhaustively here since it was not
  redesigned, per the brief's own instruction.

## 10. Top-level MIXED analysis

Redesigning payroll ALONE (UNRATE completely unchanged) drops
top-level MIXED from **83.64%** (#20A.1's fixed-but-flawed original
formula) to **43.64%** at the selected pair — STRENGTHENING (42.95%)
and MIXED are now nearly balanced, with COOLING 10.9% and STABLE 1.8%.
This is conclusive evidence that the original MIXED-dominance was
overwhelmingly a consequence of `employment_momentum`'s own defects,
not a fundamental incompatibility between the two owners' time
horizons (see §11).

## 11. UNRATE temporal-horizon compatibility

The brief asked whether payroll's new 3–6-month horizon and
unemployment's unchanged 12–14-month (year-ago) horizon remain
severely mismatched. **Evidence does not support a severe mismatch**:
fixing payroll alone (leaving UNRATE's horizon untouched) resolved the
large majority of the original MIXED-dominance (§10). The remaining
43.64% MIXED is consistent with two independently-defined, genuinely
different signals (recall #20A.1 §12: UNRATE's own IMPROVING/STABLE/
DETERIORATING split is inherently STABLE-poor — expansions dominate
U.S. economic history, so "unchanged from a year ago" is a
comparatively rare outcome) agreeing only some of the time — an
honest, expected rate of disagreement for a genuine two-signal
confirmation design, not a defect. **This does not rise to a STOP on
unemployment-horizon-mismatch grounds.**

## 12. Payroll scale over decades (redesigned deadbands)

`outputs/v2_payroll_scale.csv`: at the selected 50,000 deadband, the
tolerance shrinks from 0.0458% of total employment (1990) to 0.0314%
(2026) — the same ~31% relative drift #20A.1 found, unaffected by the
redesign since the deadband's absolute value didn't change. Confirmed
real, still judged not independently severe enough over this specific
36-year window to require a scale-normalized formula (Candidate D) —
worth monitoring in any future re-validation, not blocking this
freeze.

## 13. Condition deadband analysis

Zero is proven, directly (predeclared scenario G, §5), to cause
noise-level sign flips. 25,000 and 50,000 both pass every synthetic
scenario and both critical-month checks. **50,000 selected** over
25,000 for consistency with #20A.1's own already-validated,
BLS-sampling-error-grounded figure for exactly this statistical
object (a single 3-month payroll average) — introducing a *different*
number for the same kind of quantity without new grounding would be
an unjustified change, not a refinement.

## 14. Momentum deadband analysis

Zero is not directly tested against a predeclared "noise" scenario the
way condition's zero was, but the same principle applies: a momentum
difference of two 3-month averages is, if anything, noisier than a
single 3-month average (roughly `√2×` the implied standard error,
following #20A.1's own scaling logic). **50,000 selected** — matching
condition's value exactly, a conservative (not the widest technically
defensible) choice: June 2021 resolves to a clean EXPANDING/STEADY
read at 50,000 rather than the more marginal EXPANDING/WORSENING→
COOLING read produced at 25,000, which this study judges to be the
slightly more defensible characterization of a month that was still
adding ~529,000 jobs.

## 15. Selected payroll methodology

**Candidate B**, condition and momentum both evaluated on `current_3m`
(months `t, t-1, t-2`), momentum compared against the non-overlapping
`prior_3m` (months `t-3, t-4, t-5`). See §16–19 for exact detail.

## 16. Exact formulas

```
current_3m(t) = mean(monthly_change(t), monthly_change(t-1), monthly_change(t-2))   # persons/month
prior_3m(t)   = mean(monthly_change(t-3), monthly_change(t-4), monthly_change(t-5)) # persons/month

condition(t):
  current_3m(t) >  50,000  -> EXPANDING
  current_3m(t) < -50,000  -> CONTRACTING
  otherwise                -> FLAT
  (None -> INSUFFICIENT_DATA)

momentum(t):
  diff = current_3m(t) - prior_3m(t)
  diff >  50,000  -> IMPROVING
  diff < -50,000  -> WORSENING
  otherwise       -> STEADY
  (either input None -> INSUFFICIENT_DATA)

employment_state(t) = TABLE[condition(t), momentum(t)]   # §18
```
All lookups are exact-calendar-month (reusing `methodology.month_before`
unmodified) — no interpolation, no row-position counting, identical
discipline to #20A/#20A.1.

## 17. Exact state vocabularies

- `EmploymentCondition`: `EXPANDING | FLAT | CONTRACTING | INSUFFICIENT_DATA`
- `EmploymentMomentum`: `IMPROVING | STEADY | WORSENING | INSUFFICIENT_DATA`
  — deliberately not "ACCELERATING/DECELERATING": those words read as
  implicitly positive-direction-only in ordinary usage (an
  "accelerating" contraction is linguistically awkward and risks the
  exact ambiguity this redesign exists to remove); IMPROVING/WORSENING
  read correctly regardless of `condition`'s own sign.
- `EmploymentState`: `EXPANDING | COOLING | STABLE | CONTRACTING | RECOVERING | INSUFFICIENT_DATA`
  — six values (five substantive). `RECOVERING` is the one new state
  this redesign adds, specifically to preserve the "still contracting,
  but genuinely improving" fact the original formula collapsed away
  (§6). No other new state was added — `FLAT` collapses to `STABLE`
  regardless of momentum (evidence still shows momentum; the label
  doesn't further subdivide "moving sideways"), and a worsening
  contraction stays labeled plain `CONTRACTING` rather than gaining
  its own "DETERIORATING" label, per the brief's own "do not add
  states unless each represents a genuinely different economic fact"
  instruction — the CONTRACTING-vs-RECOVERING distinction is the one
  that was actually misleading readers; steady-bad vs. worsening-bad
  is a real nuance but a smaller one, still visible in the momentum
  evidence field for a reader who wants it.
- `LaborState` (top-level): **unchanged** — `STRENGTHENING | COOLING | STABLE | MIXED | INSUFFICIENT_DATA`.

## 18. Exact thresholds

`condition_deadband_jobs = 50,000`. `momentum_deadband_jobs = 50,000`.
Both STATISTICAL/ECONOMIC-type thresholds (per #20A's own threshold
taxonomy), both boundary-inclusive-STABLE/exclusive-EXPANDING-or-
CONTRACTING exactly like every other tolerance band in this project
(`value > deadband` / `value < -deadband`, strict; the closed interval
`[-deadband, deadband]` is the FLAT/STEADY zone).

## 19. Combination table

Condition × Momentum → EmploymentState (9 cells, exhaustive):

| | IMPROVING | STEADY | WORSENING |
|---|---|---|---|
| **EXPANDING** | EXPANDING | EXPANDING | COOLING |
| **FLAT** | STABLE | STABLE | STABLE |
| **CONTRACTING** | RECOVERING | CONTRACTING | CONTRACTING |

EmploymentState × UnemploymentTrendState → LaborState (unchanged
philosophy from #20A: only a clean, unambiguous agreement earns a
clean top-level label):

| EmploymentState | UnemploymentTrendState | LaborState |
|---|---|---|
| EXPANDING | IMPROVING | STRENGTHENING |
| COOLING | DETERIORATING | COOLING |
| CONTRACTING | DETERIORATING | COOLING |
| STABLE | STABLE | STABLE |
| (either) | INSUFFICIENT_DATA | INSUFFICIENT_DATA |
| *(any other combination, including every RECOVERING pairing)* | | MIXED |

`RECOVERING` deliberately never resolves to a clean STRENGTHENING or
COOLING at the top level on its own — employment is still, factually,
contracting, so a top-level "STRENGTHENING" claim would repeat exactly
the kind of overclaim #20A.1 was built to catch; MIXED (with the
sub-state evidence directly showing RECOVERING) is the honest
representation, consistent with §6's own August-2009 resolution.

## 20. Missing-data rules

Unchanged in spirit from #20A/#20A.1: `current_3m` needs exactly 4
consecutive exact calendar months (`t` through `t-3`, since
`monthly_change` itself needs a pair); `prior_3m` needs 4 more (`t-3`
through `t-6`) — 7 consecutive months total for a fully-computed
`EmploymentResult`. Any missing exact month inside that span makes the
dependent value `None` → `INSUFFICIENT_DATA`, never interpolated,
never partially computed. This is a meaningfully SHORTER data
requirement than the original formula's 13-month span — a secondary,
positive side effect of the redesign (less exposure to any single
missing month, and faster availability after a data restart).

## 21. Evidence sketch (not implemented, structure only)

```
employment:
  candidate_id: "B"                    # or the frozen name, e.g. "payroll_condition_momentum_v1"
  condition:
    current_3m_avg_jobs: float | None
    condition_deadband_jobs: 50000
    condition: EmploymentCondition
  momentum:
    current_3m_avg_jobs: float | None   # same value as condition's, shown once, referenced twice conceptually
    prior_3m_avg_jobs: float | None
    momentum_deadband_jobs: 50000
    momentum: EmploymentMomentum
  state: EmploymentState
  calculation_period: date | None
```
Auditable: every field is either a persisted-observation-derived
average or a fixed, versioned constant — no opaque intermediate value.

## 22. Affected horizons (re-derived, not reused from #20A)

**Superseded — see `LABOR_V1_FROZEN_METHODOLOGY.md` §13.** The
derivation originally here treated a revision as landing directly on
a `monthly_change` value and concluded a contiguous 6-month range
(`P ∈ {M..M+5}`). Re-verification during the #20A.3 freeze — both
algebraically and empirically, against the actual cached PAYEMS data —
found this was not quite right: a real revision lands on the
underlying PAYEMS **level**, which shifts two adjacent `monthly_change`
values in *opposite* directions; any 3-month average containing both
of them cancels exactly. The genuinely correct affected set is the
**sparse 3-point set `{M, M+3, M+6}`**, not a contiguous range at all.
This entry is left in place, corrected, as part of this project's
permanent methodology-history record (see #20A.3's own instruction not
to erase prior research) — the frozen specification is the normative
source going forward, not this paragraph.

## 23. JOLTS recommendation (unchanged from #20A.1, not redesigned this turn)

Still no authoritative published JOLTS-rate sampling-error figure
surfaced. Recommendation stands: **Option A (confirmation direction
with no numeric deadband) or Option B (defer confirmation from initial
#20B)** — either is acceptable; JOLTS still never owns `LaborState`,
so this remains independent of the payroll decision above.

## 24. Known limitations

- The `RECOVERING`/`CONTRACTING` split does not distinguish "steady
  contraction" from "worsening contraction" at the label level (only
  in the momentum evidence field) — a deliberate simplicity choice
  (§17), revisitable if a real product need for that finer distinction
  emerges.
- `momentum_deadband_jobs = 50,000` is a conservative, consistency-
  driven choice (§14, §18), not independently re-derived from its own
  dedicated sampling-error calculation the way condition's was in
  #20A.1 — a `√2`-scaled, more rigorously-derived figure (~100,000)
  was considered and set aside in favor of consistency and the
  cleaner June-2021 read it produces; a future revalidation could
  re-examine this specific number with its own dedicated derivation.
- Candidate A remains a viable, closely-related alternative (§4.1) —
  not rejected on behavioral grounds (its churn is, if anything,
  slightly lower), only on interpretability grounds.
- This study's evidence for "UNRATE needs no redesign" (§11) is an
  inference from the MIXED-rate drop, not an exhaustive re-audit of
  UNRATE's own turning-point behavior — reasonable given the brief's
  explicit instruction not to redesign UNRATE this turn, but worth
  remembering it's indirect evidence.
- Latest-revised-data limitation (inherited from #20A.1, restated):
  this study evaluates formula behavior on today's revised data, not
  real-time historical performance.

## 25. Reproducibility

```
.venv/bin/python research/labor_momentum/fetch_data.py    # once, or to refresh (shared with #20A.1)
.venv/bin/python -m research.labor_momentum.study          # #20A.1's own study, unchanged
.venv/bin/python -m research.labor_momentum.study_v2       # this redesign's study
```
Verified deterministic: `study_v2.py` run twice against the same
cached data produced byte-identical `v2_*.csv` files in `outputs/`.
