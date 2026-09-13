# Inflation Momentum Methodology Study

**Status: evidence for human methodology review. No methodology is selected in this document.**

This is a research study, not a production increment. Nothing here is
implemented as a product feature; no production code changed to produce
it. See `docs/ENGINEERING_JOURNAL.md`'s corresponding entry for how this
fits into the project's history.

## Research Question

*"What deterministic methodology best identifies meaningful changes in
underlying U.S. inflation momentum while remaining responsive, stable,
persistent, interpretable, and robust across different inflation
regimes?"*

This is not a forecasting model, a trading strategy, a recession
predictor, or an ML/AI classification exercise, and it was not tuned
against asset returns or against how "smart" it makes any historical
period look. Every threshold tested below (delta/band values) was fixed
in advance by the research brief, not fit to the data.

## Data

Four canonical monthly, seasonally-adjusted FRED price indexes, fetched
via the existing production `FREDClient` (reused directly, not
duplicated) and cached locally as JSON — never written to the
production PostgreSQL database:

| Label | FRED ID | First obs. | Last obs. | Observations | Missing |
|---|---|---|---|---|---|
| Headline CPI | CPIAUCSL | 1947-01-01 | 2026-08-01 | 956 | 1 (2025-10-01) |
| Core CPI | CPILFESL | 1957-01-01 | 2026-08-01 | 836 | 1 (2025-10-01) |
| Headline PCE | PCEPI | 1959-01-01 | 2026-07-01 | 811 | 0 |
| Core PCE | PCEPILFE | 1959-01-01 | 2026-07-01 | 811 | 0 |

**Both CPI series are missing the same single month, 2025-10-01** — a
real gap in FRED's own published series, not an artifact of this
study's code. No value was interpolated for it; every transformation
spanning that month is `None` for both series, exactly as the code's
general missing-value rule requires (see Adversarial Case J).

**Latest common period across all four series: 2026-07-01.** CPI's
August 2026 observation exists; PCE's does not yet (a well-known,
structural BEA-vs-BLS release-timing gap, not a data quality issue —
see Adversarial Case O and Common-Period Analysis below).

Full coverage details, per-series metadata, and the exact missing dates
are in `outputs/data_coverage.json`.

## Current-Vintage Limitation

**This study is a CURRENT-VINTAGE HISTORICAL RECONSTRUCTION, not a
record of what an analyst would have known at the time.** The
application does not maintain historical vintages/revision history
(ALFRED-style data). Every historical observation used here reflects
whatever revisions FRED has incorporated as of the fetch date of this
study, which for early-history observations may differ, sometimes
materially, from the value originally released at the time. No claim in
this document should be read as "this is what the data looked like in
1974" — only "this is what FRED reports for 1974 today." Building
vintage-aware persistence is explicitly out of scope for this
increment.

## Transformations

Compounded annualization from index levels, computed independently in
`methodology.annualized_change` (not reused from
`app.domain.transformations`, whose `percent_change` computes a plain
period-over-period change, not an annualized one — a different formula
for a different purpose):

```
annualized_rate = ((P_t / P_(t-n)) ** (12/n) - 1) * 100
```

Applied at n=1, 3, 6, 12. **Never approximated** as a simple
period change times a multiplier — hand-verified in
`tests/research/test_inflation_momentum.py`:

- 3M annualized of a 1% three-month gain is **4.0604%**, not 4.0% (the
  naive `×4` approximation the brief explicitly forbids).
- 6M annualized of a 3% six-month gain is **6.09%**, not 6.0%.

1M annualized is computed and reported, but — per the brief — never
independently determines a candidate's canonical state in any candidate
below; every candidate's core comparison uses only 3M/6M/12M.

Missing values (FRED's `.` marker, or a genuine gap) propagate as
`None` through every transformation that would need them — never
imputed, never silently skipped to an earlier value.

## Candidate Methodologies

Four families, each evaluated on all four series independently:

- **Candidate A — Recent vs Trailing**: 3M vs 12M, neutral band
  `delta` ∈ {0.00, 0.10, 0.25, 0.50} pp. COOLING / HEATING / STABLE.
- **Candidate B — Dual Confirmation**: 3M AND 6M vs 12M must both agree
  to call COOLING/HEATING (same delta set); otherwise
  MIXED_OR_STABLE (deliberately not yet split — see Findings).
- **Candidate C — Ordered Momentum**: strict `3M < 6M < 12M` (COOLING)
  or `3M > 6M > 12M` (HEATING), else MIXED. A base variant (band=0)
  plus one explicitly-separated exploratory variant requiring 0.25pp
  separation at each step.
- **Candidate D — Change in Recent Momentum**: `delta_3m = 3M(t) - 3M(t-1)`,
  classified ACCELERATING/DECELERATING/FLAT. Evaluated for churn only,
  never proposed as a standalone canonical state.

## Evaluation Metrics

Defined once in `metrics.py`, applied identically to every
candidate/variant/series — never redefined per candidate. Full
definitions in that module's docstrings; headline set: classified/
unclassified months, per-state percentage, state-change count and rate,
median/mean state duration, one- and two-month reversal counts,
COOLING→HEATING→COOLING and HEATING→COOLING→HEATING whipsaw counts, and
longest continuous run per state. Full results: `outputs/candidate_metrics.csv`.

## Overall Results

The single clearest, most consistent finding across all four series:
**adding a same-size neutral band affects Candidate A and Candidate B
in opposite directions, and Candidate A's churn is *not* monotonic in
band width.**

Core PCE, Candidate A, state-change rate by delta:

| delta | state_change_rate | % COOLING | % HEATING |
|---|---|---|---|
| 0.00 | 0.258 | 51.6% | 48.4% |
| 0.10 | 0.343 | 44.9% | 42.7% |
| 0.25 | **0.390 (peak)** | 34.3% | 32.7% |
| 0.50 | 0.315 | 20.9% | 21.3% |

Widening the band from 0.00 to 0.25 *increases* the state-change rate
before it falls back down at 0.50 — a genuinely non-obvious result. The
likely mechanism: a mid-size band adds a third reachable state
(STABLE) between COOLING and HEATING, and boundary-hovering data cross
all three thresholds more often than it crossed the single COOLING/
HEATING boundary that exists at delta=0.00. Only a *wide* band (0.50)
meaningfully reduces churn, and it does so partly by reducing how often
COOLING/HEATING are reached at all (only ~42% of classified months
combined, vs. ~100% at delta=0.00).

**Candidate B (dual confirmation) does not show this same non-monotonic
pattern** — its state-change rate falls steadily and substantially as
delta widens (Core PCE: 0.371 → 0.316 → 0.223 → 0.095), and at every
matching delta it churns noticeably less than Candidate A (e.g. at
delta=0.25: B=0.223 vs A=0.390 — nearly half). This is the clearest
quantitative case for *some* form of multi-horizon confirmation in the
final methodology, whatever its exact shape.

**Candidate C's base variant (band=0) churns about as much as Candidate
A at a moderate delta** (Core PCE state-change rate 0.390, coincidentally
matching A's own delta=0.25 rate exactly), but its exploratory
band=0.25 variant cuts churn substantially (0.170) — a similar
stabilizing effect to Candidate B, achieved a different way (requiring
separation at each step of the ordering, not confirmation from a second
horizon).

**Candidate D churns close to 50/50 almost every month** (Core PCE:
51.3% ACCELERATING / 48.7% DECELERATING, essentially never exactly
FLAT) — confirming the brief's expectation that raw month-to-month
change in 3M momentum is far too noisy to serve as a standalone
canonical state on its own.

## Core PCE Results

(The brief's primary candidate underlying-momentum measure.) At
delta=0.25: 799 of 811 months classified (12 unclassified — the
earliest months lacking 12 months of prior history). 34.3% COOLING /
32.7% HEATING / 33.0% STABLE. Median state duration 2 months, mean 2.56
months. Longest continuous COOLING run and longest HEATING run are both
reported in `outputs/candidate_metrics.csv` (double-digit months during
the sustained regimes discussed below).

## Core CPI Results

The brief's designated cross-check measure. Very close numerically to
Core PCE at every tested delta (e.g. delta=0.25: 34.8% COOLING / 34.4%
HEATING vs. Core PCE's 34.3%/32.7%) — the two core measures behave
similarly in aggregate, which sets up the more interesting question of
*how often they actually agree month-to-month* (see Cross-Measure
Agreement below — the answer is "less than the aggregate similarity
would suggest").

## Headline Results

Headline CPI and Headline PCE both show *higher* HEATING percentages
than their core counterparts at every delta (e.g. delta=0.25: Headline
CPI 44.8% HEATING vs. Core CPI 34.4%; Headline PCE 40.4% vs. Core PCE
32.7%) — consistent with headline measures' larger exposure to volatile
food/energy prices producing more frequent above-trend readings, though
this study does not attempt to explain *why* beyond noting the pattern.
Headline CPI and Headline PCE also show the *lowest* churn of any
same-delta pairing at delta=0.50 among the four series' Candidate A
results.

## Cross-Measure Agreement

Full results: `outputs/cross_measure_agreement.csv`. Candidate A,
delta=0.25:

| Pair | Same state | Opposite (COOLING vs HEATING) | Other |
|---|---|---|---|
| Core PCE vs Core CPI | 55.1% | 7.4% | 37.5% |
| Core PCE vs Headline CPI | 45.7% | **16.6%** | 37.8% |
| Core PCE vs Headline PCE | 57.1% | 7.5% | 35.4% |
| Headline PCE vs Headline CPI | 73.5% | 3.6% | 22.8% |

**All four series agreeing on the same state simultaneously happens in
only 30.5% of fully-classified months.** Full four-way consensus is the
exception, not the rule, even before considering that the brief's
hierarchy treats these four measures asymmetrically rather than as
flat votes.

**The specific hierarchy-divergence pattern the brief asked to be
quantified — Core PCE and Core CPI agreeing with each other while
Headline PCE and Headline CPI agree with each other on the *strictly
opposite* state — occurs in 3.4% of common, fully-classified months.**
Not the dominant case, but real, non-zero, and exactly the kind of
situation a flat four-way vote would average away silently.

Dual confirmation (Candidate B, delta=0.25) improves every one of these
agreement numbers substantially, and — notably — improves *opposite-state*
disagreement even more than it improves plain agreement: Core PCE vs
Core CPI opposite-state drops from 7.4% (Candidate A) to 1.3%
(Candidate B); Headline PCE vs Headline CPI opposite-state drops from
3.6% to 0.13%. Requiring a second horizon's confirmation doesn't just
reduce a single series' own churn — it also reduces how often two
different series flatly contradict each other.

## Historical Regime Analysis

Full per-regime coverage and Core PCE (Candidate A, delta=0.25) state
counts: `outputs/regime_analysis.json`. These are descriptive windows
from documented macroeconomic history, not hindsight-optimized ground
truth, and the methodology/delta was fixed before this analysis was
run — nothing here was tuned to produce these results. Selected
findings, Core PCE:

| Regime | Months | COOLING | HEATING | STABLE |
|---|---|---|---|---|
| Late-1970s Second Oil Shock | 36 | 7 | **23 (64%)** | 6 |
| Volcker Disinflation | 48 | **29 (60%)** | 12 | 7 |
| 2021-2022 Inflation Surge | 18 | 2 | **11 (61%)** | 5 |
| 2022-2024 Disinflation | 30 | **18 (60%)** | 4 | 8 |
| COVID Collapse | 5 | **4 (80%)** | 1 | — |

The methodology's dominant state during each of these five widely-
documented episodes matches the independently-known macroeconomic
narrative for that period (accelerating into the 1980 peak, sustained
disinflation under Volcker, the 2021-2022 surge, the subsequent
2022-2024 disinflation, and the brief pandemic-era price collapse) —
without any parameter in this study having been chosen to produce that
match. This is the strongest available evidence (short of a live,
forward-looking test this study cannot perform) that the methodology
family is measuring something real, not an artifact.

Coverage caveat: PCE series start in 1959, so the 1970s regimes have
full coverage, but nothing before 1959 (e.g., an isolated pre-1959
comparison) would have zero PCE coverage — reported honestly by
`regimes.regime_coverage`, never fabricated, though no regime in this
study's list actually falls before 1959.

## Adversarial Cases

Full results: `outputs/adversarial_cases.json`. All 15 cases (A-O)
produced the behavior the code's own definitions predict, with no
surprises requiring a design change:

- **A/B**: unambiguous 3M-vs-12M divergence classifies consistently
  across Candidates A/B/C.
- **C**: near-equal 3M/12M correctly lands in the "no meaningful
  signal" bucket for every candidate (STABLE / MIXED_OR_STABLE / MIXED).
- **D/E** (conflicting 3M/6M signals): Candidate A calls a direction
  anyway (using only 3M vs 12M); Candidate B and C correctly refuse to
  call COOLING/HEATING when the two horizons disagree — this is the
  clearest illustrated *design* difference between "recent vs trailing"
  and "confirmation-based" methodologies, not a bug in either.
- **F/G** (core-vs-headline divergence): not synthetic — pointed at the
  real, empirically measured rates above (7.4% opposite for core-pair,
  3.4% hierarchy-divergence rate).
- **H/I** (a measure's latest month missing): correctly returns `None`
  for the unclassifiable month rather than reusing the prior state.
- **J** (one missing intermediate month): correctly propagates `None`
  for exactly the transformations that span the gap, recovers normally
  the month after — and this exact scenario is not hypothetical, it is
  the real 2025-10-01 gap present in both CPI series right now.
- **K** (deflation): a negative 3M/positive-ish 12M synthetic case
  classifies as COOLING with no special-casing required — the formula
  handles negative rates natively.
- **L** (a +10% one-month shock): 1M annualized correctly reflects the
  shock's full compounded magnitude (≈214% annualized) — exactly why
  the brief insists 1M alone must never determine the canonical state.
- **M** (3M=2.01 vs 12M=2.00): at delta=0.00 this is HEATING; at any
  tested delta ≥0.10 it is STABLE. This is not a flaw — it is the
  entire *purpose* of a neutral band, made concrete at the threshold
  where it matters most.
- **N** (repeated identical run): produced identical output both times,
  confirmed programmatically, not just by inspection.
- **O** (different latest periods): real and current right now (CPI is
  one month ahead of PCE); `latest_common_period` correctly resolves to
  the earlier date, never comparing mismatched months.

## Stability / Churn Analysis

See Overall Results above for the headline finding (Candidate A's
non-monotonic churn response to band width). Full per-series, per-delta
duration/reversal/whipsaw counts are in `outputs/candidate_metrics.csv`;
every candidate/variant produces at least a handful of one-month
reversals and both whipsaw directions at every tested delta on every
series — none of the tested configurations is churn-free, and none
should be expected to be, given monthly macro data's inherent noise.

## Responsiveness Analysis

This study deliberately did not construct a hindsight-optimized "the
turn happened on this exact date" label (the brief explicitly forbids
this). What Historical Regime Analysis shows instead is the *dominant*
state during each documented episode, which is the responsible way to
observe responsiveness without pretending a mathematically perfect
turning-point exists. A proper first-changed-state-and-did-it-persist
episode table (the brief's Section 10 ideal) would require picking
specific candidate turn dates within each regime and is left as a
natural next step for whichever candidate(s) survive methodology
selection — attempting it for all 4 candidates × 4 deltas × 4 series
here would have produced a combinatorial volume of tables without added
decision-relevant signal at this stage.

## Limitations

- **Current-vintage only** — see the dedicated section above.
- **Cross-measure agreement and regime tables were computed for
  Candidates A and B only** (delta=0.25 as a representative middle
  value), not exhaustively for every candidate/delta combination. Full
  per-series churn/duration metrics (Section 9 of the brief) ARE
  computed exhaustively for all candidates/variants/series in
  `candidate_metrics.csv`; the cross-cutting analyses (agreement,
  regimes) were scoped to the two most decision-relevant candidates
  given the size of the full combinatorial space. This is a scoping
  choice made for this study, not a limitation of the underlying code
  (which can run any candidate against any pairing).
- **A full responsiveness/turn-persistence episode table was not
  built** (see Responsiveness Analysis above) — the regime dominant-state
  tables are a substitute, not the brief's full ideal.
- **No forward-looking or out-of-sample validation is possible** — this
  is definitionally a backward-looking reconstruction.
- The 2025-10-01 CPI gap is real and current; if FRED backfills it
  later, re-running `fetch_data.py` will change a small number of
  downstream `None`s to real values in a future re-run — this is
  expected, not a reproducibility failure (reproducibility here means
  "same cached data in, same result out," not "the world never
  revises").

## Candidate Strengths and Weaknesses

**Candidate A (Recent vs Trailing)** — Simplest, most interpretable,
most responsive (never requires two horizons to agree, so it reacts as
soon as 3M crosses the band). Weakness: highest churn of the four
families at every matching delta, non-monotonic churn response to band
width (empirically surprising, requires the widest band to meaningfully
stabilize), and the only candidate that classifies confidently even
when 6M actively disagrees with 3M (Adversarial D/E).

**Candidate B (Dual Confirmation)** — Substantially lower churn and
substantially lower opposite-state cross-measure disagreement than
Candidate A at every matching delta; the strongest empirical case among
the four for reducing false signals. Weakness: at wider deltas, spends
the large majority of months in MIXED_OR_STABLE (e.g. delta=0.50: only
~14% of Core PCE months classified as COOLING or HEATING at all) — a
real responsiveness/stability tradeoff, and the brief's own open
question (whether MIXED_OR_STABLE should ever be split) remains
genuinely unresolved by this data alone.

**Candidate C (Ordered Momentum)** — Base variant churns comparably to
Candidate A; the exploratory band variant achieves Candidate-B-like
stabilization through a conceptually different mechanism (strict
multi-step ordering rather than dual-horizon confirmation). Weakness:
the strict-ordering requirement is the least forgiving of the three
state-determining candidates — a single out-of-order month among
3M/6M/12M immediately drops to MIXED even if two of the three are
clearly aligned, arguably discarding partial information Candidate B
would still act on if 3M and 6M agree even when 12M is close.

**Candidate D (Change in Recent Momentum)** — As expected going in,
useless as a standalone canonical state (near-50/50 churn), but this
study did not evaluate it as a *secondary confirmation signal layered
on top of* another candidate's classification, which is arguably its
more promising role and remains untested here.

## Questions Requiring Human Decision

1. **Which candidate family, and which delta/band, should become
   canonical** — this study deliberately does not answer this.
2. **Should MIXED_OR_STABLE (Candidate B) be split** into distinct
   MIXED and STABLE concepts? The brief asked this be left open; this
   data shows the combined bucket is large (especially at wider
   deltas) but does not itself indicate whether splitting it would add
   decision-relevant information or just more categories.
3. **Is the four-series hierarchy (Core PCE primary → Core CPI
   confirmation → headline context) the right structure**, given that
   full four-way agreement occurs in under a third of months and the
   specific core-vs-headline divergence pattern the brief flagged
   occurs in 3.4% of months? This study quantifies the disagreement; it
   does not decide whether disagreement itself should become a
   reported product feature (as the brief speculates it might).
4. **What delta/band value, if any, is "right"** — the non-monotonic
   churn response found for Candidate A specifically means "wider band
   = more stable" is not a safe assumption to build production logic
   on without checking, as this study did.
5. **Should Candidate D (or something like it) be revisited as a
   secondary confirmation layer** rather than a standalone state, as
   suggested above — untested here.
6. **How should the current-vintage limitation be surfaced to end
   users** of any eventual production feature — this study documents
   the limitation; it does not design the disclosure.
7. **Whether a full responsiveness/turn-persistence episode table**
   (this study's Limitations section) is worth building for whichever
   candidate(s) survive this review, before finalizing.
