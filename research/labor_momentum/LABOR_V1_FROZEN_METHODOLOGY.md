# Economic Intelligence — Labor Market Monitor Methodology Specification v1.0

| | |
|---|---|
| Methodology ID | `labor_v1.0` |
| Specification version | 1.0 |
| Status | **FROZEN** |
| Methodology type | Deterministic |
| AI dependency | None |
| Canonical geography | United States |
| Data basis | Latest revised data |
| Primary frequency | Monthly |
| Canonical owners | `PAYEMS` (employment) + `UNRATE` (unemployment) |
| Confirmation | JOLTS — **deferred from #20B** (see §7) |
| Context only | `CIVPART` — **deferred from #20B** (see §8) |

> **This document is normative.** Production behavior for Increment
> #20B MUST conform to this specification exactly. Where
> implementation convenience conflicts with this specification, this
> specification wins. Implementation must not reinterpret, extend,
> simplify, or improve the economic methodology.

This document is documentation only. It does not implement, and must
not be read as authorizing implementation of, any production code,
API endpoint, service, repository, or domain module. Production
implementation is a separate, explicitly authorized task ("Increment
#20B") and has not begun.

This methodology was selected through repository-based historical
research (`research/labor_momentum/`, see §14 "Methodology History")
rather than intuition — the choice of formula and thresholds below
records that research's conclusion, it does not re-derive it. Every
numeric claim in this document was re-verified directly against the
actual committed research code (`research/labor_momentum/methodology_v2.py`
and `methodology.py`) while writing this freeze, not transcribed from
prose summaries of it.

---

## 1. Why this document exists

Increment #20A designed the Labor Monitor's architecture (two owning
components — payroll and unemployment — plus JOLTS confirmation).
#20A.1 historically validated the originally-proposed payroll formula
and found it structurally defective (not sign-aware; its rolling
12-month baseline was contaminated by the 2020 COVID shock for well
over a year afterward — see §14). #20A.2 redesigned and re-validated
the payroll formula. This document converts that validated research
result into one frozen, implementable specification.

## 2. Units (frozen, non-negotiable)

PAYEMS is represented **in actual persons**, never FRED's native
"Thousands of Persons," anywhere inside the Labor methodology. The
×1,000 conversion happens exactly once, at the data/logic boundary
(mirroring `research/labor_momentum/methodology_v2.build_payems_persons_index`),
with an implementation-time sanity assertion recommended (a converted
value implausibly outside the actual range of U.S. total nonfarm
employment should fail loudly, not silently produce a wrong-by-orders-
of-magnitude tolerance comparison — this is exactly the class of bug
#20A.1's own research caught and fixed). Every threshold in this
document is stated in actual jobs/persons unless explicitly marked
otherwise (UNRATE's own threshold is percentage points, since UNRATE
is already a rate).

## 3. PAYEMS — Employment Condition

```
current_3m_avg_jobs(t) = mean(
    monthly_change(t),
    monthly_change(t-1),
    monthly_change(t-2),
)
where monthly_change(m) = PAYEMS_persons[m] - PAYEMS_persons[m-1]
```

Requires exact PAYEMS observations at `t, t-1, t-2, t-3` (4 consecutive
levels, to compute 3 monthly changes). Missing any one of these four
exact calendar months makes `current_3m_avg_jobs` — and therefore
`condition` — unavailable; never interpolated, never computed from a
partial window.

**`condition_deadband_jobs = 50,000`**

```
current_3m_avg_jobs(t) >  +50,000  -> EXPANDING
current_3m_avg_jobs(t) <  -50,000  -> CONTRACTING
otherwise (-50,000 <= value <= +50,000)  -> FLAT
```
Boundary inclusive for `FLAT` on both ends — a value exactly at either
edge is `FLAT`, never nudged by an added epsilon (the same convention
`inflation_v1.0`'s own boundary uses).

## 4. PAYEMS — Employment Momentum

Non-overlapping 3-month windows:

```
prior_3m_avg_jobs(t) = mean(
    monthly_change(t-3),
    monthly_change(t-4),
    monthly_change(t-5),
)

momentum_delta_jobs(t) = current_3m_avg_jobs(t) - prior_3m_avg_jobs(t)
```

`current_3m_avg_jobs` needs PAYEMS at `t..t-3`; `prior_3m_avg_jobs`
needs PAYEMS at `t-3..t-6`. Together, `momentum_delta_jobs` (and
therefore any usable `EmploymentState`) requires exact PAYEMS
observations at **`t` through `t-6`** — 7 consecutive calendar months.
Missing any one of the seven makes momentum, and therefore
`EmploymentState`, `INSUFFICIENT_DATA`.

**`momentum_deadband_jobs = 50,000`**

```
momentum_delta_jobs(t) >  +50,000  -> vocabulary value #1 (see note below)
momentum_delta_jobs(t) <  -50,000  -> vocabulary value #2
otherwise (-50,000 <= delta <= +50,000)  -> vocabulary value #3 (STEADY)
```
Boundary inclusive for the "no meaningful change" (`STEADY`) case.

**Vocabulary note — a discrepancy between this increment's own prose
and the actual validated research artifact, resolved in the
artifact's favor:** this increment's framing prose used
`ACCELERATING`/`DECELERATING` for the two directional momentum values.
The actual, validated, committed research code
(`research/labor_momentum/methodology_v2.py::classify_momentum`) uses
**`IMPROVING`/`WORSENING`** instead, with an explicit, reasoned
docstring justification: "ACCELERATING"/"DECELERATING" read as
implicitly positive-direction-only in ordinary usage (an
"accelerating contraction" is linguistically confusing), while
IMPROVING/WORSENING read correctly regardless of `condition`'s own
sign — this is precisely the kind of ambiguity #20A.1's own findings
exist to prevent. Per this increment's own instruction to "transcribe
exactly" from the research artifact rather than reinterpret from
prose, **this freeze adopts the artifact's actual vocabulary,
`IMPROVING`/`STEADY`/`WORSENING`**, not `ACCELERATING`/`STEADY`/
`DECELERATING`. If `ACCELERATING`/`DECELERATING` is preferred for
product-facing display copy later, that is a presentation-layer label
mapping over this same canonical value, decided separately — the
canonical enum value itself is `IMPROVING`/`STEADY`/`WORSENING`.

```
momentum_delta_jobs(t) >  +50,000  -> IMPROVING
momentum_delta_jobs(t) <  -50,000  -> WORSENING
otherwise                           -> STEADY
```

## 5. Employment State (frozen vocabulary and table)

`EmploymentState`: `EXPANDING | COOLING | STABLE | CONTRACTING | RECOVERING | INSUFFICIENT_DATA`

The table below is transcribed **exactly** from
`methodology_v2._CONDITION_MOMENTUM_TABLE`, all 9 cells present and
unambiguous (a Python dict over the full 3×3 domain, so no cell could
be silently missing):

| Condition \ Momentum | IMPROVING | STEADY | WORSENING |
|---|---|---|---|
| **EXPANDING** | EXPANDING | EXPANDING | COOLING |
| **FLAT** | STABLE | STABLE | STABLE |
| **CONTRACTING** | RECOVERING | CONTRACTING | CONTRACTING |

`condition == INSUFFICIENT_DATA OR momentum == INSUFFICIENT_DATA` →
`EmploymentState = INSUFFICIENT_DATA` (checked before the table
lookup).

Required invariants (re-verified directly against this exact table,
not re-derived from prose): `CONTRACTING + IMPROVING -> RECOVERING` ✓;
`CONTRACTING + WORSENING -> CONTRACTING` ✓; `EXPANDING + IMPROVING ->
EXPANDING` ✓; `EXPANDING + WORSENING -> COOLING` ✓; `FLAT + STEADY ->
STABLE` ✓. All five hold exactly as stated (using this document's own
frozen `IMPROVING`/`WORSENING` vocabulary in place of the prompt's
`ACCELERATING`/`DECELERATING`, per §4's note).

## 6. UNRATE — Unemployment Trend (unchanged from #20A/#20A.1)

```
current_3m_avg(t)    = mean(UNRATE[t], UNRATE[t-1], UNRATE[t-2])
prior_year_3m_avg(t) = mean(UNRATE[t-12], UNRATE[t-13], UNRATE[t-14])
delta_pp(t) = current_3m_avg(t) - prior_year_3m_avg(t)
```
Requires exact UNRATE observations at `t, t-1, t-2, t-12, t-13, t-14`
(six specific calendar months — not all 15 intervening months).
Missing any one of the six makes `delta_pp`, and therefore
`UnemploymentTrendState`, `INSUFFICIENT_DATA`.

**`unemployment_deadband_pp = 0.2`**

```
delta_pp(t) >  +0.2  -> DETERIORATING
delta_pp(t) <  -0.2  -> IMPROVING
otherwise (-0.2 <= delta_pp <= +0.2)  -> STABLE
```
Boundary inclusive for `STABLE`. Verified directly against
`methodology.classify_unemployment_trend` — matches exactly.

## 7. Top-Level Labor State (frozen vocabulary and table)

`LaborState`: `STRENGTHENING | COOLING | STABLE | MIXED | INSUFFICIENT_DATA`

Transcribed **exactly** from `methodology_v2._LABOR_AGREEMENT_TABLE`
and its surrounding `combine_labor_state` logic — a complete,
exhaustive, deterministic function over all `6 × 4 = 24`
`(EmploymentState, UnemploymentTrendState)` combinations (verified:
this is not an ambiguous or partial table — every combination not
explicitly listed resolves to the stated, explicit `MIXED` default,
and `INSUFFICIENT_DATA` is checked first and takes priority over
everything else):

```
if EmploymentState == INSUFFICIENT_DATA or UnemploymentTrendState == INSUFFICIENT_DATA:
    LaborState = INSUFFICIENT_DATA
```

Full table for the remaining `5 × 3 = 15` substantive combinations:

| Employment \ Unemployment | IMPROVING | DETERIORATING | STABLE |
|---|---|---|---|
| **EXPANDING** | STRENGTHENING | MIXED | MIXED |
| **COOLING** | MIXED | COOLING | MIXED |
| **STABLE** | MIXED | MIXED | STABLE |
| **CONTRACTING** | MIXED | COOLING | MIXED |
| **RECOVERING** | MIXED | MIXED | MIXED |

Only four combinations produce a clean, non-`MIXED`, non-`INSUFFICIENT_DATA`
result: `(EXPANDING, IMPROVING) -> STRENGTHENING`; `(COOLING,
DETERIORATING) -> COOLING`; `(CONTRACTING, DETERIORATING) -> COOLING`;
`(STABLE, STABLE) -> STABLE`. Every other combination — including
**every** `RECOVERING` pairing — is `MIXED`. This is deliberate:
`RECOVERING` means employment is still, factually, contracting, so no
combination involving it may resolve to a clean `STRENGTHENING` at the
top level without repeating the exact overclaim #20A.1 was built to
catch. No weights, no score, no majority vote, no hidden tie-breaker
anywhere in this table — a plain, small, explicit lookup with one
documented default.

## 8. JOLTS and CIVPART decisions

**JOLTS: deferred entirely from #20B.** #20A.1 could not ground a
defensible confirmation deadband from any published, authoritative
sampling-error figure; #20A.2 did not revisit this (out of scope for
the payroll redesign) and reaffirmed the same recommendation. Per this
increment's own stated strong preference, JOLTS confirmation is
deferred to a future, dedicated confirmation increment rather than
implemented with an invented threshold. `LaborState` never depends on
JOLTS in #20B.

**CIVPART: deferred entirely from #20B**, including from the #20B
evidence contract (§9) — not merely "context, but included." CIVPART
never determines `LaborState` under any circumstance (frozen, §3–§7
never reference it), and the frozen evidence contract below (§9) is
deliberately minimal, containing only the fields actually needed to
reconstruct `employment`/`unemployment`/`LaborState` — adding a
context-only field with zero state-determining value would violate
this specification's own "do not overbuild" instruction. Including
`CIVPART` as a documented context addition is left to a #20B.1-style
follow-on, exactly the same precedent #17A's own curated-catalog
follow-on already established for this project.

## 9. Missing-data rules (restated precisely)

- `EmploymentState = INSUFFICIENT_DATA` unless all 7 exact PAYEMS
  calendar months `t..t-6` are present (§4).
- `UnemploymentTrendState = INSUFFICIENT_DATA` unless all 6 exact
  UNRATE calendar months `{t,t-1,t-2,t-12,t-13,t-14}` are present (§6).
- `LaborState = INSUFFICIENT_DATA` if either owner is
  `INSUFFICIENT_DATA` (§7).
- No forward-fill, backfill, interpolation, nearest-date substitution,
  or partial-window averaging anywhere in this methodology, at any
  step.

## 10. Period semantics — the shared `evaluation_period` rule

PAYEMS and UNRATE are both part of the Employment Situation release
and, under ordinary operation, share the same latest reference month.
This methodology freezes exactly one `evaluation_period` per
`LaborMonitorResult` — **never** a result where `employment` and
`unemployment` were evaluated at two different reference months.

**Rule:** `evaluation_period` = the most recent calendar month `T`
such that a *complete* `EmploymentState` (all 7 required PAYEMS
months present) **and** a *complete* `UnemploymentTrendState` (all 6
required UNRATE months present) can both be computed as-of `T`. If the
two series' own latest persisted observation dates differ for any
reason (e.g. an ingestion gap advances one series ahead of the other),
`evaluation_period` is bounded by the **earlier** of the two series'
own latest usable month — the service never advances one owner's
evaluation ahead of the other's. If no such common month exists at
all, the service does not silently retry an earlier month to "find
one that works" — `LaborState = INSUFFICIENT_DATA` is the correct,
honest result for the (otherwise) latest month, exactly like every
other missing-data case in this specification.

## 11. Data basis and revision disclosure

`data_basis = "Latest revised data"` — the existing project-wide
convention: *"Historical calculations use the latest revised
observations available to Economic Intelligence and may differ from
values originally reported at the time."*

**Labor-specific addition (frozen, required in any consumer-facing
disclosure of this methodology):** *"Payroll employment is subject to
monthly revisions and annual benchmark revisions, which can materially
change recent employment estimates."* This is a stronger, more
specific caveat than the generic sentence above — #20A.1's own
research directly measured multi-hundred-thousand-job benchmark
revisions in recent cycles, materially larger than this methodology's
own `condition_deadband_jobs`/`momentum_deadband_jobs`.

## 12. Evidence contract (frozen structure, minimal)

```
LaborMonitorResult
  methodology_id: "labor_v1.0"
  data_basis: "Latest revised data"
  state: LaborState
  evaluation_period: date

  employment:
    series_id: "PAYEMS"
    condition: EmploymentCondition
    momentum: EmploymentMomentum
    state: EmploymentState
    current_3m_avg_jobs: float | None
    prior_3m_avg_jobs: float | None
    momentum_delta_jobs: float | None
    condition_deadband_jobs: 50000
    momentum_deadband_jobs: 50000
    # + the exact source PAYEMS observation dates/values (t through
    #   t-6) needed to fully reconstruct the above without a second
    #   database query

  unemployment:
    series_id: "UNRATE"
    state: UnemploymentTrendState
    current_3m_avg: float | None
    prior_year_3m_avg: float | None
    delta_pp: float | None
    unemployment_deadband_pp: 0.2
    # + the exact source UNRATE observation dates/values (the six
    #   exact months from §6) needed to fully reconstruct the above

  provenance: [...]   # per-input series_id/observation_date/value/data_basis records, the same shape discipline app.models.inflation.InflationMetricEvidence already establishes -- a NEW, independently-defined Labor-specific model, not a shared base class with Inflation's own (see #20A §23's own reasoning, unchanged)
```

No JOLTS field (§8). No CIVPART field (§8). No speculative field for
any not-yet-built consumer.

## 13. Affected horizons — re-derived from exact dependencies, corrected from #20A.2's own report

**PAYEMS / `EmploymentState`.** A revision changes a persisted PAYEMS
**level** at some calendar month `M` (BLS revises levels, not
differences). Because `monthly_change(m) = PAYEMS[m] - PAYEMS[m-1]`,
a level revision at `M` (by amount `δ`) shifts exactly **two**
adjacent monthly-change values in **opposite directions**:
`monthly_change(M)` by `+δ` (uses `PAYEMS[M]` as its endpoint) and
`monthly_change(M+1)` by `-δ` (uses `PAYEMS[M]` as its base).

This opposite-sign pairing has a real, non-obvious consequence: **any
3-month average that contains BOTH `monthly_change(M)` and
`monthly_change(M+1)` is exactly unaffected — the `+δ` and `-δ`
contributions cancel algebraically inside the sum.** Only an average
containing exactly ONE of the two (not both, not neither) shows a
genuine net change. Tracing `current_3m_avg_jobs(t)` (window
`{t,t-1,t-2}`) across `t`: it contains only `monthly_change(M)` at
`t=M`; contains BOTH `monthly_change(M)` and `monthly_change(M+1)`
(cancels) at `t=M+1` and `t=M+2`; contains only `monthly_change(M+1)`
at `t=M+3`; contains neither beyond that. So `current_3m_avg_jobs(t)`
is genuinely affected only at **`t ∈ {M, M+3}`** — not the full
`{M,M+1,M+2,M+3}` a naive "window overlap" argument would suggest.
The same shape, shifted, applies to `prior_3m_avg_jobs(t)` (window
`{t-3,t-4,t-5}`): genuinely affected only at **`t ∈ {M+3, M+6}`**.

**Union — `EmploymentState(t)` is genuinely affected by a revision at
`M` only at `t ∈ {M, M+3, M+6}` — three discrete evaluation periods,
each three months apart, NOT a contiguous range.**

This was verified empirically, not just algebraically: a synthetic
revision applied directly to the actual cached PAYEMS index (both at
`2020-06` and, to rule out any COVID-period coincidence, independently
at the quiet `2015-03`) and evaluated across a two-year window around
each showed `EmploymentResult` changing (in its raw averages, not just
its discretized state) at exactly offsets `{0, 3, 6}` and at no other
offset in either window.

This differs from **both** `METHODOLOGY_REDESIGN.md §22`'s originally-
reported "0–5" contiguous range **and** this document's own
first-drafted "0–6" contiguous correction (an intermediate, still-
incomplete re-derivation made while writing this freeze, which
correctly identified the wider true dependency window but missed the
internal cancellation and so overstated it as fully contiguous). **This
freeze adopts the empirically-verified `{0, 3, 6}` sparse set as
final** — the discrepancy with both prior figures is disclosed here
rather than silently carried forward, per this increment's own
explicit instruction to re-derive and verify rather than copy.

**UNRATE / `UnemploymentTrendState`.** UNRATE's own formula never
differences two levels — both `current_3m_avg`/`prior_year_3m_avg` are
plain averages of the rate itself, so a revision at `M` only affects
averages that directly contain `M`, with no adjacent-value propagation
(unlike PAYEMS's level-vs-change distinction above):

- `current_3m_avg(t)` affected whenever `t ∈ {M, M+1, M+2}`.
- `prior_year_3m_avg(t)` affected whenever `t ∈ {M+12, M+13, M+14}`.
- Union: `t ∈ {0,1,2} ∪ {12,13,14}` — **two disjoint 3-month clusters**,
  unchanged from #20A's own original derivation (UNRATE was not
  redesigned, so this dependency structure never changed).

These two affected-horizon sets are structurally different from each
other (PAYEMS's `{0,3,6}` sparse 3-point set, driven by the
cancellation effect above; UNRATE's `{0,1,2}∪{12,13,14}` disjoint
3+3 cluster, with no cancellation since it averages the rate directly
rather than a differenced quantity) and both different from #18's own
`(0,1,3,6,12)` sparse set for Inflation — a future release-processing
integration for Labor must derive its own propagation logic from these
exact dependency structures, never port either #18's or #20A's own
sets forward by assumption.

## 14. Methodology history (preserved, not erased)

**Originally proposed** (Increment #20A): `employment_momentum` as
3M/6M average monthly PAYEMS change compared, with a dual-confirmation
structure, against a **rolling 12-month average baseline**
(`δ_payroll = 50,000`, provisional).

**Rejected** (Increment #20A.1, historical validation): two confirmed,
data-verified structural defects — (1) not sign-aware: August 2009
(payrolls still falling ~331,000/month) was classified
"STRENGTHENING" purely because the decline had decelerated relative to
an even-more-negative rolling baseline; (2) 12-month baseline
contamination: April–June 2021 (genuinely robust job growth,
~530,000–575,000/month, among the strongest sustained readings in the
36-year historical record) was classified "COOLING" because the
rolling baseline still contained the 2020 COVID collapse-and-rebound
months, a distortion measured persisting for 25 consecutive months.
Full account: `METHODOLOGY_VALIDATION.md`.

**Validated replacement** (Increment #20A.2): condition/momentum
separation using short, non-overlapping 3-month windows (§3–§5 above),
adding one new state (`RECOVERING`) specifically to preserve the
"still contracting, but genuinely improving" fact the original formula
collapsed away. Both confirmed #20A.1 failures resolved; full-history
top-level `MIXED` dropped from 83.6% to 43.6% from the payroll fix
alone (UNRATE unchanged); the entire 2020–2022 COVID span reproduces
its real, recognized narrative with no special-casing, exclusion, or
clipping. Full account: `METHODOLOGY_REDESIGN.md`.

This provenance — including the rejected formula and exactly why it
was rejected — is permanent project history, not superseded
documentation to be deleted; both research documents remain in
`research/labor_momentum/` unmodified by this freeze.

## 15. Future What Changed (principle only, not implemented)

A future Labor What Changed comparator compares two already-computed
`LaborMonitorResult` snapshots' evidence — it never recalculates
`current_3m_avg_jobs`, `delta_pp`, or any other formula value itself,
the same lesson `inflation_what_changed_v1.0` already established.
Event families expected to apply cleanly, without inventing a new
taxonomy: `METRIC_CHANGED`, `STATE_CHANGED`, `AVAILABILITY_LOST`,
`AVAILABILITY_RESTORED`. `CONFIRMATION_CHANGED` is not frozen for
Labor's initial scope (no confirmation source is implemented — §8);
add it only once JOLTS confirmation itself is implemented, not before.

## 16. Future Overview (principle only, not implemented)

Labor appears beside Inflation as its own, independent entry (e.g.
`Inflation  MIXED` / `Labor  <state>`), each backed by its own
methodology and evidence. **No aggregate/weighted economy-wide state,
now or later** — unchanged from #20A §28's own strong recommendation.

## 17. Architecture (principle only, not implemented)

Route → Service → pure Labor domain module, mirroring Inflation's own
layering exactly. Canonical monitor reads persisted database
observations only — no FRED call during a read, no AI anywhere in the
call graph, no release-processing mutation from a read path, no
economic logic duplicated into the frontend.

## 18. #20B test requirements (frozen, not implemented)

At minimum, #20B's test suite must include:

**Payroll:** `EXPANDING`+`IMPROVING`; `EXPANDING`+`WORSENING` →
`COOLING`; `CONTRACTING`+`IMPROVING` → `RECOVERING`;
`CONTRACTING`+`WORSENING`; `FLAT`+`STEADY` → `STABLE`; every remaining
table cell (§5) at least once; exact `±50,000` boundary-inclusive
proofs for both condition and momentum; missing each of the 7 required
exact PAYEMS months independently; a units-conversion proof (an
assertion-style guard against a native-thousands value ever reaching
the classification functions unconverted); repeated deterministic
evaluation.

**Unemployment:** `IMPROVING`; `DETERIORATING`; `STABLE`; exact `±0.2pp`
boundary-inclusive proofs; missing each of the 6 required exact UNRATE
months independently.

**Top level:** every one of the 4 explicit agreement-table rows, plus
at least one representative `MIXED` case per `EmploymentState` row
(§7); `EmploymentState = INSUFFICIENT_DATA` propagation; `UnemploymentTrendState
= INSUFFICIENT_DATA` propagation; the shared-`evaluation_period` rule
(§10) under a simulated series-availability mismatch.

**Historical regression (frozen expected values):** August 2009 must
classify `RECOVERING` (never `STRENGTHENING`/`EXPANDING`); April 2021,
May 2021, and June 2021 must not reproduce the rejected `COOLING`
artifact (per `METHODOLOGY_REDESIGN.md §6`, April/May classify
`EXPANDING`+`IMPROVING`, June classifies `EXPANDING`+`STEADY` at the
frozen 50,000/50,000 deadbands — an exact-value regression test, not
merely "not COOLING").

**Revision propagation:** a revised PAYEMS observation must correctly
propagate through exactly the empirically-verified `{0, 3, 6}` sparse
affected-period set (§13) — not the 5-period or 6-period contiguous
ranges either previously reported or briefly (incorrectly) drafted
during this freeze, and not #18's or #20A's own horizon sets; this is
the single most important regression test this specification requires
(it protects a genuinely non-obvious, easy-to-get-wrong-again
property, and this document itself got it wrong twice before
verifying against real code — see §13's own account). A revised
UNRATE observation must propagate through exactly the
`{0,1,2}∪{12,13,14}` range (§13, unchanged).

**Architecture:** no AI import anywhere in the Labor call graph; no
FRED/provider call during a monitor read; DB-only canonical
evaluation; every field of `LaborMonitorResult` reconstructable from
persisted observations alone (an evidence-completeness proof, the same
discipline `#19B`'s own test suite already applies to its read model).

## 19. Known limitations (carried forward, not resolved by this freeze)

- `momentum_deadband_jobs = 50,000` is a consistency-driven choice,
  not independently re-derived from its own dedicated sampling-error
  calculation (see `METHODOLOGY_REDESIGN.md §24`) — a real, disclosed,
  not-yet-closed gap.
- JOLTS confirmation and `CIVPART` context are both deferred, not
  resolved (§8).
- This methodology reflects latest-revised data only; it makes no
  claim about real-time historical performance (inherited from
  #20A.1/#20A.2, restated here as it applies to the now-frozen
  version too).
- The `CONTRACTING`/`RECOVERING` split does not further distinguish
  "steady contraction" from "worsening contraction" at the label
  level — a deliberate v1 simplicity choice (visible in the momentum
  evidence field regardless), revisitable if a real product need
  emerges.
