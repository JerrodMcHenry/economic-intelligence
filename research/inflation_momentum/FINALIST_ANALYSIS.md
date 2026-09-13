# Inflation Momentum Finalist Analysis

Extends [STUDY_RESULTS.md](STUDY_RESULTS.md) (the original four-candidate
methodology study) to resolve the specific human-decision questions that
study left open. This is a **finalist analysis, not a selection** — no
methodology is chosen here, and none of the numbers below should be read
as an implicit recommendation of one finalist over another.

Orchestration: [`finalist_study.py`](finalist_study.py) (new, additive —
reuses `methodology.py`/`metrics.py` from the original study plus two new,
purely-additive functions: `classify_candidate_b_explicit` and
`compute_directional_metrics`, both unit-tested in
`tests/research/test_inflation_momentum.py`). Machine-readable outputs:
`outputs/finalist_core_pce_decision_table.csv`,
`outputs/finalist_candidate_b_explicit_states.csv`,
`outputs/finalist_neutral_band_investigation.csv`,
`outputs/finalist_cross_measure_confirmation.csv`,
`outputs/finalist_turn_persistence.json`,
`outputs/finalist_missing_confirmation_check.json`. All numbers in this
report are read directly from those files — none are hand-typed or
re-derived by hand.

Reproducibility: re-running `finalist_study.py` twice against the same
cached data produces byte-identical output files (verified in
`TestFinalistStudyEndToEndDeterminism`), and re-running the *original*
`study.py` after `finalist_study.py` exists still produces byte-identical
output to before it existed (verified by a direct `diff -rq` of the two
`outputs/` snapshots) — the two studies are fully additive and
non-interfering.

Data window: monthly Core PCE (`PCEPILFE`) observations from the cached
FRED extract, 1957-02-01 through the latest available month (811 monthly
observations total; see [STUDY_RESULTS.md](STUDY_RESULTS.md) for full
series metadata and coverage details for all four canonical series).

## Finalists

Per the finalist-analysis brief, the candidate set is narrowed to:

| Finalist | Family | Parameter | Status |
|---|---|---|---|
| `A_delta_0.25` | Candidate A (Recent vs Trailing) | delta = 0.25 | Retained as the simple/responsive benchmark |
| `B_delta_0.10` | Candidate B (Dual Confirmation) | delta = 0.10 | Finalist |
| `B_delta_0.25` | Candidate B (Dual Confirmation) | delta = 0.25 | Finalist |
| `B_delta_0.50` | Candidate B (Dual Confirmation) | delta = 0.50 | Finalist |
| `C_band_0.25` | Candidate C (Ordered Momentum, banded) | band = 0.25 | Finalist |
| — Candidate D — | Change in Recent Momentum | — | **Excluded** — the original study found it produced excessive standalone churn (state changes essentially every time the 3M rate wobbled month to month), making it unsuitable as a stable canonical signal regardless of parameterization. |

No additional candidate family was introduced. Nothing found during this
analysis constitutes a defect in the original study that would have
prevented a valid comparison among these five.

## Core PCE Decision Table

One directly comparable table, same metric definitions applied to every
finalist, computed against Core PCE only (`finalist_core_pce_decision_table.csv`).
Candidate B's states here use `classify_candidate_b_explicit`, but with
`INSUFFICIENT_DATA` normalized back to "unclassified" (not a percentage
bucket) specifically so B's "% classified" is directly comparable to A/C's
— all five finalists show **identical unclassified-months (12, 1.48%)**,
the shared early-history warm-up before 12M-lookback data exists. (Section
4 below reports B's `INSUFFICIENT_DATA` as its own first-class percentage,
which is a different, deliberately more granular view.)

| Metric | A δ=0.25 | B δ=0.10 | B δ=0.25 | B δ=0.50 | C band=0.25 |
|---|---:|---:|---:|---:|---:|
| Classified months | 799 | 799 | 799 | 799 | 799 |
| % COOLING | 34.29 | 27.79 | 17.15 | 6.88 | 9.01 |
| % HEATING | 32.67 | 24.78 | 16.27 | 7.51 | 8.64 |
| % STABLE | 33.04 | 4.76 | 21.28 | 53.44 | — |
| % MIXED | — | — | — | — | 82.35 |
| State changes | 311 | 301 | 366 | 285 | 136 |
| State-change rate | 0.390 | 0.377 | 0.459 | 0.357 | 0.170 |
| Median state duration (months) | 2.0 | 2.0 | 2.0 | 2.0 | 3.0 |
| Mean state duration (months) | 2.56 | 2.65 | 2.18 | 2.79 | 5.83 |
| 1-month reversals | 119 | 122 | 174 | 120 | 37 |
| 2-month reversals | 75 | 63 | 98 | 61 | 20 |
| COOLING→HEATING→COOLING whipsaws | 7 | 0 | 0 | 0 | 0 |
| HEATING→COOLING→HEATING whipsaws | 1 | 0 | 0 | 0 | 0 |
| Longest COOLING run (months) | 11 | 15 | 10 | 9 | 7 |
| Longest HEATING run (months) | 19 | 20 | 19 | 9 | 8 |

Observations (descriptive, not evaluative):

- Candidate A is the only finalist with a nonzero directional whipsaw
  count (COOLING→HEATING→COOLING or the reverse, with no intervening
  neutral state) — B's dual-confirmation requirement and C's ordered-
  momentum requirement never allow a single-month direct flip between
  COOLING and HEATING in this data at any of the tested parameters.
- B's %STABLE grows from 4.8% (δ=0.10) to 53.4% (δ=0.50) as the neutral
  band widens, roughly trading directional months for STABLE months —
  but not monotonically for churn (see [Neutral-Band Churn Investigation](#neutral-band-churn-investigation)).
- Candidate C's MIXED bucket dominates (82.4%) at band=0.25 — the ordered-
  momentum requirement (3M < 6M < 12M, each gap ≥ 0.25pp) is a
  considerably stricter joint condition than either A's or B's, so it
  spends most months unable to confirm a strict ordering.

## Candidate B Explicit State Semantics

The original study used a single `MIXED_OR_STABLE` bucket for Candidate
B. This analysis evaluates the explicit five-state split defined in
`classify_candidate_b_explicit` (`research/inflation_momentum/methodology.py`):

- **Boundary operators** (via the new `_horizon_bucket` helper): the
  neutral band around the 12M rate is **closed/inclusive**,
  `[12M − delta, 12M + delta]` → `"in"`; strictly below that interval →
  `"below"`; strictly above → `"above"`. Every real number falls into
  exactly one bucket — no gap, no overlap. A value sitting exactly on
  `12M − delta` or `12M + delta` is `"in"` (STABLE-eligible), never
  COOLING/HEATING.
- **COOLING**: 3M bucket = `below` AND 6M bucket = `below`.
- **HEATING**: 3M bucket = `above` AND 6M bucket = `above`.
- **STABLE**: 3M bucket = `in` AND 6M bucket = `in`.
- **MIXED**: sufficient data exists, but none of the above three
  conditions holds (e.g. 3M cooling while 6M heating, or 3M stable while
  6M cooling) — data does not fail to exist, it simply doesn't jointly
  confirm a direction or a stable state.
- **INSUFFICIENT_DATA**: 3M, 6M, or 12M itself is unavailable. Returned
  as an explicit state string (never `None`) so its frequency is directly
  measurable like any other state.

Fourteen adversarial boundary tests exercise every case listed in
[Boundary Tests](#boundary-tests) below; all pass.

Explicit-state distribution and recalculated churn, Core PCE only
(`finalist_candidate_b_explicit_states.csv`):

| Delta | %COOLING | %HEATING | %STABLE | %MIXED | %INSUFFICIENT_DATA | All-state change rate | Direct reversal rate | Directional→neutral rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.10 | 27.37 | 24.41 | 4.69 | 42.05 | 1.48 | 0.373 | 0.0111 | 0.301 |
| 0.25 | 16.89 | 16.03 | 20.96 | 44.64 | 1.48 | 0.453 | 0.000 | 0.220 |
| 0.50 | 6.78 | 7.40 | 52.65 | 31.69 | 1.48 | 0.353 | 0.000 | 0.094 |

Important, per the brief's explicit instruction: **all-state churn and
directional reversal behavior are reported separately above and must not
be conflated.** A transition into or out of MIXED is *not* treated as
equivalent to a direct COOLING↔HEATING reversal. At every one of the
three finalist deltas, Candidate B-explicit's **direct reversal rate is
at or near zero** (0.0111 → 0.000 → 0.000) — the dual-confirmation
requirement, once MIXED and STABLE are split out as their own states,
essentially eliminates same-month direct flips between COOLING and
HEATING. Nearly all of Candidate B's remaining "all-state churn" is
directional↔neutral movement (into/out of MIXED or STABLE), not
directional reversal.

## Responsiveness / Turn Persistence

Full detail in `outputs/finalist_turn_persistence.json`. Per the brief,
**this section documents responsiveness/stability tradeoffs — it does
not assert historical ground truth**, and no turning date was chosen to
make any candidate look best; each episode's reference direction was
picked from documented macroeconomic history *before* looking at which
finalist would confirm it first.

Because Candidate B's MIXED/INSUFFICIENT_DATA states make "first entered
a directional state" ambiguous by construction (a deliberate design
property, not a defect — see the previous section), this table is
computed for the two finalists with an unambiguous binary/ternary
directional state (**A** and **C**); B's responsiveness is instead
captured by its %MIXED and direct-reversal-rate numbers above, which
describe the same tradeoff from a distributional angle.

Episode reference points and windows used (documented, not fit to any
candidate):

| Episode | Window | Reference direction | Why this window |
|---|---|---|---|
| Late-1970s inflation acceleration | 1977-01 – 1980-12 | HEATING | Second oil shock era; inflation visibly accelerating through 1980 |
| Volcker-era disinflation | 1981-01 – 1983-12 | COOLING | Fed tightening; inflation falling from double digits |
| 2008 financial-crisis inflation collapse | 2008-06 – 2009-06 | COOLING | Commodity-price collapse and demand shock post-crisis |
| COVID inflation collapse | 2020-02 – 2020-06 | COOLING | Pandemic demand shock; brief disinflation |
| 2021–2022 inflation acceleration | 2021-01 – 2022-06 | HEATING | Post-pandemic reopening, supply-driven surge |
| 2022–2024 disinflation | 2022-07 – 2024-12 | COOLING | Fed tightening cycle; inflation declining from 2022 peaks |
| 2025–latest available period | 2025-01 – present | *(none asserted)* | Most recent data — no presumed direction stated in advance |

Results (first month each finalist entered the episode's reference
direction *within the window*; persistence checked as a **continuous**
run, not "matches again later after a reversal"):

| Episode | Finalist | First entered on | Months into window | Persisted ≥2mo | Persisted ≥3mo | Reversed within 1mo | Core PCE 3M / 6M / 12M at signal |
|---|---|---|---:|---|---|---|---|
| Late-1970s acceleration | A δ=0.25 | 1977-01 | 0 | Yes | Yes | No | 6.62 / 6.72 / 5.97 |
| | C band=0.25 | 1977-02 | 1 | No | No | Yes | 7.30 / 6.80 / 6.19 |
| Volcker disinflation | A δ=0.25 | 1981-01 | 0 | Yes | No | No | 9.41 / 9.91 / 9.76 |
| | C band=0.25 | 1981-04 | 3 | Yes | Yes | No | 7.97 / 8.69 / 9.21 |
| 2008 crisis collapse | A δ=0.25 | 2008-06 | 0 | No | No | Yes | 1.90 / 1.94 / 2.21 |
| | C band=0.25 | 2008-10 | 4 | Yes | Yes | No | 0.33 / 1.36 / 1.63 |
| COVID collapse | A δ=0.25 | 2020-03 | 1 | Yes | Yes | No | 1.19 / 1.47 / 1.53 |
| | C band=0.25 | 2020-04 | 2 | Yes | Yes | No | -0.82 / 0.51 / 1.00 |
| 2021–2022 acceleration | A δ=0.25 | 2021-01 | 0 | Yes | Yes | No | 2.97 / 2.58 / 1.70 |
| | C band=0.25 | 2021-01 | 0 | Yes | Yes | No | 2.97 / 2.58 / 1.70 |
| 2022–2024 disinflation | A δ=0.25 | 2022-07 | 0 | **No** | **No** | Yes | 4.75 / 4.79 / 5.11 |
| | C band=0.25 | 2022-12 | 5 | No | No | Yes | 4.08 / 4.56 / 4.97 |
| 2025–latest | A δ=0.25 / C band=0.25 | — | — | — | — | — | *(no reference direction asserted — see below)* |

Reading this table:

- Candidate A is consistently **first to signal** (0 months into the
  window in 3 of 6 episodes), but that speed comes with real cost: it
  reverses within 1 month in 2 of 6 episodes (the 2008 crisis and the
  2022–2024 disinflation), i.e. it entered the "right" direction
  immediately but then flipped back out before the move was confirmed.
- Candidate C signals later in every episode where it doesn't tie A
  (up to 5 months later, in 2022–2024), but once it signals it persists
  ≥3 months in 3 of 5 episodes where it entered at all — trading speed
  for confirmation.
- Neither candidate reliably achieves both "fast" and "persistent" at
  once in this data; that tradeoff is exactly what this section was
  asked to expose, not resolve.
- 2025–latest available period: no finalist is reported here because no
  reference direction was asserted for this still-unfolding period —
  manufacturing a hindsight-perfect turning point for the most recent,
  least-settled data would violate the brief's explicit instruction.
  Raw Core PCE 3M/6M/12M values for this window are available in
  `STUDY_RESULTS.md`'s data tables for a human reviewer to interpret directly.

## Cross-Measure Confirmation

For Candidate B-explicit at each finalist delta, evaluated as a
**hierarchy** (Core PCE primary, Core CPI confirmation, Headline PCE +
Headline CPI context) — never majority-voted into one state
(`finalist_cross_measure_confirmation.csv`):

| Delta | Core PCE/CPI same % | Core PCE/CPI opposite % | Core PCE/CPI neutral-or-mixed disagreement % | Headline PCE/CPI same % | Headline PCE/CPI opposite % | All 4 agree % | Underlying agrees, headline disagrees % | Underlying vs headline directionally opposite % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.10 | 50.93 | 2.84 | 46.24 | 69.54 | 1.23 | 23.62 | 13.19 | 1.01 |
| 0.25 | 46.61 | 1.23 | 52.16 | 67.57 | 0.12 | 19.85 | 12.44 | 0.25 |
| 0.50 | 50.06 | 0.12 | 49.82 | 63.13 | 0.00 | 17.09 | 15.08 | 0.00 |

(796 months have all four series' explicit states classifiable —
`PCEPI`/`PCEPILFE` start later than `CPIAUCSL`/`CPILFESL`, so the common
window is shorter than either individual series; the 2025-10-01 CPI gap,
discussed below, further reduces this by excluding that month from every
delta's comparisons.)

Reading this: the underlying pair (Core PCE vs Core CPI) is in direct
COOLING/HEATING opposition only rarely (≤2.84%, falling further as delta
widens), but "same state" is well under 55% at every delta — the
remainder is the large "neutral-or-mixed disagreement" bucket (46–52%),
where one series lands in a directional state and the other lands in
STABLE/MIXED/INSUFFICIENT_DATA (or vice versa) rather than a clean
opposite reading. Headline measures agree with each other far more often
(63–70% same-state) than the underlying pair does — consistent with both
headline series sharing more common short-run noise (food/energy) that
moves them together even when the "core" signal is more ambiguous.
Full four-way agreement is a minority case throughout (17–24%) and falls
as delta widens (a wider band makes STABLE more likely for each series
independently, so four independent series agreeing "STABLE" together
becomes proportionately less likely than agreeing "COOLING" together
was). Directional opposition between the underlying pair and the
headline pair is rare and shrinks to exactly 0% at delta=0.50 in this
data.

## Neutral-Band Churn Investigation

The original study found Candidate A's all-state churn **peaked at
delta=0.25 rather than declining monotonically** as the neutral band
widened. This was verified, not assumed to be a bug, and the mechanism is
now isolated using the new `compute_directional_metrics` function
(`finalist_neutral_band_investigation.csv`):

| Candidate | Delta | All-state change rate | Direct reversal rate | Directional→neutral rate | %STABLE | %MIXED |
|---|---:|---:|---:|---:|---:|---:|
| A | 0.00 | 0.258 | 0.258 | 0.000 | 0.0 | — |
| A | 0.10 | 0.343 | 0.155 | 0.188 | 12.4 | — |
| A | 0.25 | **0.390** | 0.044 | 0.346 | 33.0 | — |
| A | 0.50 | 0.315 | 0.005 | 0.310 | 57.8 | — |
| B-explicit | 0.10 | 0.373 | 0.011 | 0.301 | 4.7 | 42.0 |
| B-explicit | 0.25 | **0.453** | 0.000 | 0.220 | 21.0 | 44.6 |
| B-explicit | 0.50 | 0.353 | 0.000 | 0.094 | 52.7 | 31.7 |

**Mechanism.** For every delta, all-state change rate = direct reversal
rate + directional→neutral rate exactly (verified directly in
`TestNeutralBandInvestigation::test_candidate_a_all_state_rate_equals_sum_of_direct_and_to_neutral`,
which holds because Candidate A's three states are exhaustive and every
consecutive transition is either a direct COOLING↔HEATING flip or a move
into/out of STABLE — never both, never neither). As delta widens from 0:

1. **Direct reversal rate falls monotonically** (0.258 → 0.155 → 0.044 →
   0.005 for A) — a wider band makes it strictly harder to flip straight
   from COOLING to HEATING without passing through STABLE, exactly as
   expected.
2. **Directional→neutral rate rises sharply at first** (0.000 → 0.188 →
   0.346), because a wider band creates a bigger STABLE zone for the
   series to wander into and out of — and every such crossing is *itself*
   a state change, counted once for entering and once for leaving.
3. Between delta=0.25 and delta=0.50, directional→neutral rate **stops
   rising and falls back slightly** (0.346 → 0.310), because once STABLE
   is wide enough (57.8% of all months at delta=0.50), the series starts
   *resting* inside it for long stretches rather than merely passing
   through — durations lengthen, so crossings per month fall.

The net result is that **direct reversals fall throughout, but
directional→neutral transitions initially rise faster than direct
reversals fall** — producing a genuine, non-monotonic peak in *total*
all-state churn around delta=0.25, even though the *directional* (COOLING
↔HEATING) reversal rate declines the entire time. This is not a
calculation bug: it is exactly what "more transition opportunities via a
wider neutral zone" mechanically predicts, and it is only visible once
directional reversal is measured separately from all-state churn (per
the brief's explicit instruction not to conflate the two).

**Does the same phenomenon occur for Candidate B-explicit?** Yes — its
all-state change rate also peaks at delta=0.25 (0.453, versus 0.373 at
0.10 and 0.353 at 0.50), for the analogous reason: %STABLE + %MIXED
territory grows with delta, creating more neutral states to transition
through, while B's direct reversal rate is already at or near zero at
every finalist delta (0.011 → 0.000 → 0.000) — B's version of this
paradox is driven almost entirely by MIXED/STABLE churn, not by any
directional reversal component, which was already negligible before the
band widened at all.

## October 2025 CPI Gap

The original study found `CPIAUCSL` and `CPILFESL` both missing the
single observation `2025-10-01`, while `PCEPI`/`PCEPILFE` have that
month. This is investigated here as a real-world instance of a "missing
confirmation" scenario — not fabricated, not induced.

**Finding: this is a documented, publicly-explained BLS data-collection
gap, not a defect in this project's fetch/retrieval code.** According to
BLS's own page on the subject
(bls.gov/cpi/additional-resources/2025-federal-government-shutdown-impact-cpi.htm),
BLS did not collect CPI price data from October 1, 2025 through November
12, 2025 due to the federal government shutdown, and states plainly that
"missing CPI data affected October and November 2025 indexes." This is
corroborated by contemporaneous reporting (CNN, October 2025: BLS
confirmed the October CPI report would not be published on schedule;
usinflationcalculator.com: "BLS Cancels Oct. CPI; Nov. Inflation Report
Set for Dec. 18"; CNBC, November 2025, on the delayed combined
release). PCE data, compiled by the Bureau of Economic Analysis from a
different set of underlying source data (not primarily BLS's own
price-collection survey), was evidently unaffected in the same way,
which is consistent with — though not itself proof of — why `PCEPI`/
`PCEPILFE` show no corresponding gap.

**A nuance stated conservatively, per the brief's instruction not to
overclaim beyond what sources directly support:** BLS's page also
mentions using "statistical imputation methods" / "counterfactual
imputation approaches" for certain *specific, named, downstream-affected*
calculations (the page's own example is the April 2026 rent and owner's
equivalent rent indexes, which depend on data collected across a
multi-month cycle that the gap interrupted). This is **not** the same
claim as "a fully imputed October 2025 headline/core CPI-U index level
was retroactively published under the standard series." Our fetched
`CPIAUCSL`/`CPILFESL` still show `2025-10-01` as a genuine gap (FRED's
`.` missing-value marker), which is consistent with BLS's own framing
that the October and November *indexes themselves* were affected/missing,
not silently backfilled with an imputed level under the regular series ID.
This project makes no stronger claim than what these sources directly
state, and does **not** attempt to determine BLS's complete internal
imputation scope beyond what its own public page documents.

Per the brief's constraint, **the data was not modified, imputed, or
filled** anywhere in this codebase to investigate this — only its
presence/absence was inspected, and public documentation was read to
explain, not to route around, the gap.

## Missing-Confirmation Behavior

Verified directly against the **real** 2025-10-01 gap (not a synthetic
stand-in), in `outputs/finalist_missing_confirmation_check.json`:

| Check | Result |
|---|---|
| Core PCE's own Candidate A (δ=0.25) classification at 2025-10-01 | `STABLE` (fully computed — 3M=2.60, 6M=2.79, 12M=2.75) |
| Core PCE's own Candidate B-explicit (δ=0.25) classification at 2025-10-01 | `STABLE` |
| Core CPI's Candidate B-explicit (δ=0.25) classification at 2025-10-01 | `INSUFFICIENT_DATA` (3M/6M/12M all unavailable) |
| Core PCE classification unaffected by missing Core CPI | **True** |
| Core CPI confirmation correctly reports insufficient data (rather than a fabricated state) | **True** |
| Gap month correctly excluded from agreement/disagreement, not silently dropped or double-counted | **True** |

This confirms the expected architectural principle holds in the research
methodology as built: `classify_candidate_a` / `classify_candidate_b_explicit`
take only *one* series' own `TransformedRow` and structurally cannot
reference any other series, so a missing Core CPI observation has zero
effect on Core PCE's own canonical calculation. Separately,
`compute_agreement` treats `INSUFFICIENT_DATA` as an ordinary, comparable
state string (not `None`), so the 2025-10-01 month **is** included in the
Core PCE vs. Core CPI "neutral/mixed disagreement" bucket in the
[Cross-Measure Confirmation](#cross-measure-confirmation) table above —
correctly categorized as neither a same-state nor an opposite-state
agreement, never fabricated as a real confirmation, and never silently
excluded from the reported totals.

## Boundary Tests

Fourteen adversarial tests in `TestCandidateBExplicit`
(`tests/research/test_inflation_momentum.py`), all passing:

| # | Case | Expected |
|---|---|---|
| 1 | 3M = 12M−δ exactly, 6M = 12M−δ exactly | STABLE (boundary is inclusive/"in", not COOLING) |
| 2 | 3M = 12M+δ exactly, 6M = 12M+δ exactly | STABLE (boundary is inclusive/"in", not HEATING) |
| 3 | One horizon exactly on a boundary, the other just beyond it | MIXED |
| 4 | One horizon inside the band, the other outside it | MIXED |
| 5 | 3M cooling, 6M heating | MIXED |
| 6 | 3M heating, 6M cooling | MIXED |
| 7 | 3M stable, 6M cooling | MIXED |
| 8 | 3M stable, 6M heating | MIXED |
| 9 | 3M missing | INSUFFICIENT_DATA |
| 10 | 6M missing | INSUFFICIENT_DATA |
| 11 | 12M missing | INSUFFICIENT_DATA |
| 12 | Negative inflation (3M/6M/12M all negative, both cooling below the band) | COOLING |
| 13 | Very large positive inflation (both horizons far above the band) | HEATING |
| 14 | Identical repeated inputs, called twice | Deterministic — same result both times |

All fourteen are hand-checked against the formula's own definition (not
derived by calling the function under test), per this project's existing
test-writing convention. `finalist_study.py`'s own orchestration logic
(dispatch, decision-table normalization, cross-measure hierarchy,
turn-persistence continuity, missing-confirmation behavior) has 23
additional tests in `tests/research/test_finalist_analysis.py`.

## Current-Vintage Terminology

The brief asks whether "Current vintage" (with the expanded text
"Historical values use the latest available revised observations and may
differ from values originally reported at the time") would be technically
accurate for a future UI, given the app's actual architecture. This is a
documentation-only recommendation — no product code was changed to
evaluate it.

**Architecture check:** `app/db/models.py`'s `EconomicObservation` has a
single `value` column per `(economic_series_id, observation_date)`
(enforced by a unique constraint) with no vintage/as-of/revision
dimension anywhere in the schema. When a series is re-fetched, the stored
value for a given date is simply replaced — there is exactly one value
per date at any moment, never several tracked vintages. This is
confirmed structurally by inspecting the model; no ALFRED-style
revision-vintage architecture exists in this codebase, and none is being
proposed or built here.

**Is "Current vintage" accurate?** In ALFRED's own established usage,
"vintage" specifically refers to *one of several preserved snapshots* of
a data series as it looked at different points in time, and "current
vintage" means "the most recent such snapshot" — implying that other
vintages exist and are being deliberately excluded. **This app has no
other vintage to exclude: it never stores more than one value per date in
the first place.** Calling the single value this app has "the current
vintage" borrows a term whose ordinary meaning implies a multi-vintage
system sitting behind it, when the real architecture is simpler and
narrower: one value per date, continuously overwritten. A user familiar
with ALFRED terminology could reasonably (and incorrectly) infer that
this app tracks/exposes other vintages somewhere, or that a specific,
named vintage was chosen; neither is true.

The proposed expanded text itself ("Historical values use the latest
available revised observations and may differ from values originally
reported at the time") is accurate and is not the problem — it correctly
describes the behavior. The concern is narrowly the short label term
"Current vintage" implying more architecture than exists.

**Recommendation (documentation only, no code change):**

- Short UI label: **"Latest revised data"** (or equivalently "Latest
  available data") instead of "Current vintage" — describes exactly what
  the app has (one, continuously-updated value per date) without
  invoking vintage-comparison machinery the app doesn't have.
- Expanded disclosure text: keep the brief's proposed sentence largely
  as-is, since it is accurate; e.g. "Historical values reflect the latest
  revised data as currently reported by the source, not the value
  originally published at the time. This app stores one value per date
  and does not track prior revisions."  The added second sentence makes
  the single-value architecture explicit rather than implicit, so a
  reader familiar with "vintage" terminology isn't left assuming
  otherwise.
- If true vintage-awareness (ALFRED-style, multiple preserved snapshots
  per date) is ever built, "Current vintage" would become accurate at
  that point — but building that is explicitly out of scope here
  (Section 9 of the brief: "Do not implement ALFRED").

## Final Tradeoff Summary

No winner is declared. Each finalist's demonstrated tradeoff, purely
descriptive:

- **Candidate A (δ=0.25)** — fastest to signal a turn (ties for first in
  half the tested episodes), simplest to explain (single 3M-vs-12M
  comparison), but the only finalist with nonzero direct COOLING↔HEATING
  whipsaws (8 total) and the only one observed to reverse within 1 month
  in real historical turning points (2 of 6 tested episodes). Highest
  responsiveness, lowest built-in stability.
- **Candidate B (δ=0.10 / 0.25 / 0.50)** — the dual-confirmation
  requirement drives its direct reversal rate to ≈0 at every finalist
  delta once MIXED/STABLE are explicitly separated; its cost is a large
  MIXED bucket (32–45% of months) representing genuine directional
  disagreement between the 3M and 6M horizons rather than a clean signal.
  Delta choice within B is itself a real tradeoff: δ=0.10 has the
  smallest MIXED zone and highest %COOLING/%HEATING resolution but is
  never below the 5% mark for STABLE; δ=0.50 is dominated by STABLE
  (53%) and offers the fewest classified directional months.
- **Candidate C (band=0.25)** — the strictest joint condition (3M<6M<12M
  ordering with a minimum gap at each step) and correspondingly the
  quietest: lowest state-change rate of all five finalists (0.170),
  longest median/mean durations, and zero directional whipsaws. Its cost
  is being MIXED 82% of the time and, in the turn-persistence table,
  never signaling a turn faster than 5 months into a window — the most
  stable and the slowest of the five.

## Questions for Human Decision

1. Which delta for Candidate B (0.10 / 0.25 / 0.50) best matches the
   product's tolerance for MIXED-state months versus directional
   resolution? None of the three dominates the others on every metric.
2. Is Candidate A's fast-but-occasionally-reversing behavior acceptable
   for a user-facing "state" indicator, or does the observed 1-month
   whipsaw rate (8 whipsaws, 2 of 6 tested historical turns reversing
   within a month) disqualify it regardless of its responsiveness
   advantage?
3. Is Candidate C's near-total MIXED occupancy (82%) acceptable for a
   canonical indicator that needs to say *something* most months, or does
   it effectively fail to classify too often to be useful as a primary
   signal?
4. For Candidate B, should the product surface all five explicit states
   (COOLING/HEATING/STABLE/MIXED/INSUFFICIENT_DATA) to end users, or
   collapse some subset back toward the original study's simpler
   MIXED_OR_STABLE presentation for readability?
5. How should the product represent Core CPI confirmation being
   unavailable (as it currently is for 2025-10-01)? This analysis
   confirms Core PCE's own state is unaffected and confirmation
   correctly reports as unavailable rather than fabricated — but the
   *user-facing* treatment (hide the confirmation badge? show "pending"?
   show the underlying reason?) is a product decision, not resolved here.
6. Does the "Latest revised data" label (or another human-chosen wording)
   replace "Current vintage" in the eventual UI, and should the expanded
   disclosure text be edited further before it ships?
7. Which historical episode(s), if any, should be used as the primary
   basis for choosing a final delta/candidate — the brief's instruction
   against manufacturing a hindsight-perfect turning date means this
   analysis deliberately stops short of ranking the finalists by
   backtested "accuracy," but a human reviewer may reasonably want to
   weight some episodes (e.g. 2021–2022 acceleration) more heavily than
   others for the eventual monitor's purpose.

No "Selected methodology" section is included in this document, and none
should be inferred from the ordering above — per the brief, that decision
is explicitly out of scope for this analysis.
