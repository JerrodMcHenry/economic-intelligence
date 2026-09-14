# Labor Release Integration V1 — Frozen Contract

**Increment #20D.1 (audit / design / freeze only — no implementation).**
Freezes how Increment #18's release-driven update pipeline integrates
Employment Situation (FRED release 50) with `labor_v1.0` and
`labor_what_changed_v1.0`, for Increment #20D.2 to implement exactly.

Location note: placed under `docs/architecture/` (not
`docs/methodology/`) because this is an *integration* contract, not an
economic methodology — mirroring where `release-processing-v1.md` and
`release-processing-read-model-v1.md` already live, not
`docs/methodology/inflation-what-changed-v1.0.md`'s own location.

---

## 1. Mission recap

```
Employment Situation
        │
        ├── PAYEMS
        └── UNRATE
             │
             ▼
    persisted observation updates
             │
             ▼
       labor_v1.0 before / after
             │
             ▼
 labor_what_changed_v1.0 (same-period comparison)
             │
             ▼
 ReleaseAnalysisUpdate evidence
```

**RELEASE PROCESSING ORCHESTRATES. LABOR MONITOR CALCULATES ECONOMICS.
LABOR WHAT CHANGED COMPARES CANONICAL RESULTS.** No layer duplicates
another layer's methodology — every finding below was audited against
this rule.

## 2. Baseline

- `git status --porcelain`: clean.
- `git log -1 --oneline`: `5c93c22 Add deterministic Labor What Changed V1 (#20C)`.
- Full backend suite before any change: **1,111 passed, 0 skipped, 0
  failed.**

## 3. Files inspected

**Labor:** `research/labor_momentum/LABOR_V1_FROZEN_METHODOLOGY.md`,
`research/labor_momentum/LABOR_WHAT_CHANGED_V1_FROZEN_METHODOLOGY.md`,
`app/models/labor.py`, `app/domain/labor.py`, `app/services/labor.py`,
`app/api/labor.py`, `app/models/labor_what_changed.py`,
`app/domain/labor_what_changed.py`.

**#18 release processing (production):** `app/db/models.py`
(`EconomicRelease`, `ReleaseOccurrence`, `ReleaseSeriesMapping`,
`ReleaseCheckRun`, `ReleaseObservationUpdate`, `ReleaseAnalysisUpdate`),
`app/models/release_processing.py`, `app/domain/release_processing.py`,
`app/services/release_processing.py`,
`app/repositories/release_processing_repository.py`,
`app/operations/process_release.py`,
`alembic/versions/dbd9a2889ef3_*.py` (schema),
`alembic/versions/cd476d227f99_*.py` (CPI/PIO mapping seed),
`alembic/versions/fbbe6b1ab8d9_*.py` (curated release catalog seed).

**#18 tests (all read):**
`tests/integration/test_release_processing_service.py`,
`tests/integration/test_release_processing_repository.py`,
`tests/integration/test_process_release_cli.py`,
`tests/test_domain_release_processing.py`,
`tests/test_release_processing_architecture.py`.

**#19B read model:** `app/models/release_processing_read.py`,
`app/repositories/release_processing_read_repository.py`,
`app/services/release_processing_read.py`,
`tests/api/test_release_processing_read_api.py`.

**Docs/ADRs:** `docs/ENGINEERING_JOURNAL.md` (#18/#19B/#20B/#20C.1/#20C.2
entries), `docs/architecture/current-architecture.md`,
`docs/architecture/request-flows.md`, `docs/adr/022-release-processing-audit-without-monitor-snapshots.md`,
`docs/adr/023-release-processing-read-model-no-causal-nesting.md`.

## 4. Employment Situation release identity (frozen)

Already seeded, unchanged by this audit: `EconomicRelease` row with
`provider="FRED"`, `provider_release_id="50"`, `name="Employment
Situation"` (migration `fbbe6b1ab8d9`). The *internal* identity
`#20D.2` must join against is `EconomicRelease.id`, resolved at
migration-run time via `(provider, provider_release_id)` — never a
hardcoded integer — mirroring `cd476d227f99`'s own exact lookup
pattern (`sa.select(economic_releases.c.id).where(provider == "FRED",
provider_release_id == "50")`).

## 5. Series mapping — frozen

`#20D.2` adds **exactly**:

```
Employment Situation (FRED 50) → PAYEMS
Employment Situation (FRED 50) → UNRATE
```

No CIVPART, no JOLTS, no wages/claims/hours/earnings/other CES series
— none is a `labor_v1.0` dependency. Mirrors `cd476d227f99`'s exact
pattern: a new **data migration** (not schema), `down_revision =
'cd476d227f99'` (current head), inserting into the existing
`release_series_mappings` table via the release's resolved id. This is
the established, correct #20D.2 mechanism — not a schema migration.

## 6. Mapping semantics — frozen

`ReleaseSeriesMapping` means **"this series is eligible to be checked
when this release occurrence is processed."** It does NOT mean "this
release caused every observation change" or "every changed observation
was newly published by this occurrence." No change to this semantics
is needed for Labor — `app/repositories/release_processing_repository.py`
already reads mappings generically (`get_active_mappings`, ordered by
`series_id`, no Inflation-specific filtering).

## 7. Observation fetch horizon — audited, unchanged

`app.domain.release_processing.five_year_observation_start` is a
plain, monitor-agnostic calendar calculation (exactly 5 years before
`as_of_date`, leap-day-safe). It is (A) the provider fetch horizon —
entirely separate from (B) NEW/REVISED/UNCHANGED classification and
(C) affected-evaluation-period propagation. A 5-year window does not
imply 5 years of evaluation periods get recomputed — only the specific
sparse offsets in §9/§10 below do. **No change needed**: 5 years
comfortably covers PAYEMS's 7-month and UNRATE's 15-month trailing
dependency windows for any period whose own observations fall inside
the fetch window.

**Historical-data precondition (frozen):** release processing is not
responsible for bootstrapping an empty database. It relies on
previously-synchronized historical observations already being
persisted (exactly as #18 already relies on this for Inflation). If
insufficient history exists for a newly-affected period, `labor_v1.0`
reports that period `INSUFFICIENT_DATA` — never backfilled or
interpolated inside the comparator or the release-processing pipeline.

## 8. NEW / REVISED / UNCHANGED — audited, unchanged

`app.domain.release_processing.classify_observation_change` is already
completely generic (plain equality on parsed floats, `existed_before`
flag, no series-specific logic anywhere). **No change needed.** Frozen
for Labor exactly as for Inflation: UNCHANGED creates no
`ReleaseObservationUpdate` row; NEW/REVISED do; observation writes
occur strictly after BEFORE-evidence capture and strictly before
AFTER-evidence capture (§11); transaction semantics are unchanged.

## 9. PAYEMS affected-period derivation — re-verified against production code

**Frozen set: `{0, 3, 6}`** (sparse, not contiguous) — because a level
revision at month `r` shifts `monthly_change(r)` by `+δ` and
`monthly_change(r+1)` by `-δ` (opposite signs); any 3-month average
containing BOTH cancels exactly, so only offsets 0, 3, and 6 (where the
window contains exactly one of the two) show genuine change.

**Directionality, re-derived by direct execution against
`app.domain.labor.compute_employment_result` on a real synthetic index
(not copied from #20B's own report):**

```
PAYEMS observation revised at r = 2015-03-01 (a quiet, non-COVID period)
→ evaluation periods t that differ:  t = r,     2015-03-01
                                      t = r+3,   2015-06-01
                                      t = r+6,   2015-09-01
→ t = r+1 (2015-04-01) and t = r+2 (2015-05-01): confirmed UNCHANGED
  (the cancellation itself, not merely "less change")
```

**A revision at `r` affects evaluation periods `t = r`, `t = r+3`, `t =
r+6` — always FORWARD from `r`, never backward** — the identical
forward-only convention `app.domain.release_processing._AFFECTED_HORIZONS_MONTHS`
already uses for Inflation (`D + k`, `k ≥ 0`).

## 10. UNRATE affected-period derivation — re-verified against production code

**Frozen set: `{0, 1, 2} ∪ {12, 13, 14}`** (two disjoint clusters — no
cancellation; UNRATE averages the rate directly, unlike PAYEMS's
differenced series) — because `current_3m_avg(t)` needs `t, t-1, t-2`
(so a change at `r` affects any `t` with `r ∈ {t, t-1, t-2}`, i.e. `t ∈
{r, r+1, r+2}`), and `prior_year_3m_avg(t)` needs `t-12, t-13, t-14`
(so `t ∈ {r+12, r+13, r+14}`).

**Directionality, re-derived by direct execution against
`app.domain.labor.compute_unemployment_result`:**

```
UNRATE observation revised at r = 2015-03-01
→ evaluation periods t that differ:  t = r,     2015-03-01   (current window)
                                      t = r+1,   2015-04-01   (current window)
                                      t = r+2,   2015-05-01   (current window)
                                      t = r+12,  2016-03-01   (prior-year window)
                                      t = r+13,  2016-04-01   (prior-year window)
                                      t = r+14,  2016-05-01   (prior-year window)
```

Both clusters are forward-only from `r`, matching PAYEMS's own
directionality and Inflation's existing convention.

**Real-world worked example (the exact gap #20A.1/#20B/#20C.2 already
established):** if UNRATE's 2025-10 observation is NEW/REVISED, the
affected evaluation periods are 2025-10, 2025-11, 2025-12 (current
window) and 2026-10, 2026-11, 2026-12 (prior-year window) — exactly the
three-consecutive-anchor persistence #20C.2's own fixture test proved.

## 11. Multiple changed observations — union/dedup, frozen

For one series (e.g. three revised PAYEMS months in one run), each
changed date `r` contributes its own `{r, r+3, r+6}` (or UNRATE's set);
the **union** of all contributions across every changed date in that
series is taken, exactly mirroring
`app.domain.release_processing.affected_evaluation_periods`'s own
existing "several changed dates sharing one affected period must be
evaluated only once" property (already proven by
`TestInflationAnalysisImpact::test_multiple_observations_feeding_one_evaluation_produce_one_consistent_before_after_diff`).
Ordering: sorted chronologically (`sorted(periods)`), matching
`_apply_changes_and_compute_analysis`'s existing `sorted(affected_pairs,
key=...)` discipline.

## 12. Cross-series union — frozen

PAYEMS and UNRATE co-own `LaborState`, so the full set of Labor
evaluation periods to recompute is the **union** of PAYEMS's affected
periods and UNRATE's affected periods:

```
PAYEMS revision affects   {t1, t2, t3}
UNRATE revision affects   {t2, t4, t5}
Labor recomputation set:  {t1, t2, t3, t4, t5}, t2 evaluated exactly once
```

This is a genuine, real architectural **simplification versus
Inflation**, not an extra complexity: Inflation's own
`_affected_component_period_pairs` returns `set[(component, period)]`
because different Inflation components (`PRIMARY_MOMENTUM`, `TARGET`,
`CONFIRMATION`, …) are evaluated by *separate* domain calls. Labor has
no such split — `compute_labor_monitor_result_at(period)` computes
`LABOR`+`EMPLOYMENT`+`UNEMPLOYMENT` together in ONE call, and all three
comparator functions (`compare_employment_section`,
`compare_unemployment_section`, `compare_labor_state`) run against that
SAME before/after pair. **Labor's affected set is therefore `frozenset[date]`
(periods only, no component dimension) — not `set[(component, date)]`
pairs.** This must not be forced into Inflation's pair-shaped
structure.

## 13. Before/after sequence — reused verbatim, frozen

`app.services.release_processing.ReleaseProcessingService._apply_changes_and_compute_analysis`
already implements exactly the safe sequence the mission's own §"BEFORE
SNAPSHOT" section sketches, verified by direct inspection:

1. Determine affected pairs/periods from **pre-write** persisted state
   (`_affected_component_period_pairs`, called before any
   `write_observation`).
2. Load BEFORE evidence for every affected period.
3. Write every NEW/REVISED observation.
4. Load AFTER evidence for every affected period (same reads,
   post-write).
5. Diff BEFORE vs. AFTER via the existing comparator, once per affected
   unit.
6. Persist `ReleaseObservationUpdate` + `ReleaseAnalysisUpdate` rows,
   in the SAME transaction as the observation writes.

**Frozen for Labor: reuse this exact sequence, not a second
orchestration model.** The only new work is *what* gets loaded/evaluated
at steps 2 and 4 (Labor's own before/after `LaborMonitorResult` pair
per affected period) and *how* it gets diffed at step 5 (Labor's own
three comparator calls) — never a redesign of the sequence itself.

## 14. Same-period comparator reuse — frozen, this is why #20C.2 supports it

For an affected period `t`:

```
before_result = compute_labor_monitor_result_at(payems_before, unrate_before, t, ...)
after_result  = compute_labor_monitor_result_at(payems_after,  unrate_after,  t, ...)

employment_events    = compare_employment_section(t, t, before_result.employment, after_result.employment)
unemployment_events  = compare_unemployment_section(t, t, before_result.unemployment, after_result.unemployment)
labor_events         = compare_labor_state(t, t, before_result.state, after_result.state)
```

`previous_period = current_period = t` — this is EXACTLY the
same-period revision support #20C.2's own comparator was built and
tested for (`previous_period == current_period`, no ordering assertion
anywhere in the comparator — verified in #20C.2's own test suite).
**Release processing must NOT call `month_over_month_labor_periods` or
`LaborMonitorService.get_what_changed_result`** (the monthly `/changes`
orchestration) — that answers a different question ("current vs. one
month before") than release processing's own question ("what did this
persisted write change about period `t` specifically"). Mirrors
`_diff_component_at`'s own existing `period, period` call shape
exactly.

## 15. `ReleaseAnalysisUpdate` persistence rule — frozen

**Persist an analysis update when the comparator produces at least one
event for that period** — confirmed as the existing Inflation
precedent by direct inspection of
`TestInflationAnalysisImpact::test_no_analytical_change_when_a_revision_does_not_move_any_canonical_value`
(`result.analysis_changes == []` even though `observation_changes` has
one entry, whenever the revision doesn't move anything the comparator
can see). **No special-casing is needed for Labor's own cancellation
zone** (PAYEMS offsets 1, 2 relative to a revision) — it falls out for
free: `compare_employment_section` at an unaffected offset naturally
returns `changes == []` since before/after evidence is bit-identical,
so zero `AnalysisChangeRecord` rows are ever constructed for that
period. **Top-level `LaborState` changing is never required** — a
`METRIC_CHANGED`-only event (no `STATE_CHANGED` anywhere) still
produces a row, exactly matching `labor_what_changed_v1.0`'s own
no-suppression principle (#20C.2).

**Observation changed but analysis unchanged (frozen, explicit):** a
`ReleaseObservationUpdate` row can exist for a period with **zero**
corresponding `ReleaseAnalysisUpdate` rows. This is not a bug — it is
`data changed ≠ analysis changed`, already the established #18
invariant for Inflation.

## 16. Persistence cardinality — audited, **no schema change required**

Direct inspection of migration `dbd9a2889ef3`: `release_analysis_updates`
has **no uniqueness constraint** across `(release_check_run_id,
component, event_type, field, evaluation_period)` — it is a flat,
append-only event table where **`evaluation_period` is a column on
every row**, not implied by the check run. This means **one release
occurrence already supports arbitrarily many distinct evaluation
periods, and arbitrarily many events per period, with zero schema
change.** Cardinality model: `release_check_run_id × component ×
event_type × field × evaluation_period` → one row (not literally
unique-constrained, but never duplicated in practice because a given
before/after diff at a given period is computed exactly once per run).
**No STOP required here — the schema already supports multi-period
Labor evidence.**

## 17. Analysis type / methodology identifiers — audited, ONE real blocker found

`AnalysisChangeRecord.methodology_id: str = METHODOLOGY_ID` and
`.data_basis: str = DATA_BASIS` are plain `str` fields with an
Inflation-sourced *default* — **not blockers**; a Labor-producing code
path simply passes `methodology_id="labor_v1.0"` explicitly (the
SOURCE monitor, per #20C.2's own established convention — the
comparator's own id, `labor_what_changed_v1.0`, is never persisted
per-event, exactly mirroring Inflation's identical rule that
`ReleaseAnalysisUpdate` has no persisted `comparison_contract_id`
column either — release-scoped evidence never needed it).

**Real blocker found:** `AnalysisChangeRecord.component: ChangeComponent`
(and `app.models.release_processing_read.DetectedAnalysisChange.component`,
the #19B read-model twin) are typed with **Inflation's own** `Literal`
(`app.models.inflation_what_changed.ChangeComponent =
"PRIMARY_MOMENTUM"|"CONFIRMATION"|"TARGET"|"HEADLINE_PCE"|"HEADLINE_CPI"`).
Labor's own `LaborChangeComponent = "LABOR"|"EMPLOYMENT"|"UNEMPLOYMENT"`
shares **zero** members with it — constructing `AnalysisChangeRecord(component="EMPLOYMENT",
...)` today raises a Pydantic `ValidationError`. This is exactly the
"response/persistence schema that only happens to work for Inflation"
the audit was asked to search for.

The underlying DB column (`component: String(32)`, no CHECK
constraint — confirmed in `dbd9a2889ef3`) does **not** enforce this
restriction; it is a pure application-model type limitation, fixable
without any migration. `event_type: ChangeEventType` is **not** a
blocker — Inflation's `ChangeEventType` (`METRIC_CHANGED|STATE_CHANGED|
AVAILABILITY_LOST|AVAILABILITY_RESTORED|CONFIRMATION_CHANGED`) is a
strict superset of Labor's own four-value vocabulary; every Labor
event type Pydantic-validates against it unchanged today.

**Frozen fix for #20D.2 (smallest change, no migration):** widen
`AnalysisChangeRecord.component` and `DetectedAnalysisChange.component`
from `ChangeComponent` to plain `str` in both
`app/models/release_processing.py` and
`app/models/release_processing_read.py`. Do **not** introduce a shared
union type or a generic "AnalysisComponent" abstraction — a plain,
already-precedented `str` (exactly what the DB column already is, and
what `field`/`previous_value`/`current_value` already are on this same
model) is the smallest fix and stays forward-compatible with a future
third monitor's own component vocabulary without another union-member
edit each time.

## 18. No-causal-overclaiming — audited, unchanged, applies identically

The public/internal framing is already safe and generic: "EI detected
these changes while processing this release occurrence" — no file
inspected claims economic causality anywhere. Nothing here is
Inflation-specific wording; it applies to Labor verbatim, no change
needed.

## 19. Partial provider failure — audited directly, behavior confirmed by existing tests

`TestProviderFailureIsolation` (already using UNRATE as one of its two
example series) proves, directly, without any Labor-specific code:
per-series failure isolation is already correct and monitor-agnostic.

| Scenario | Confirmed existing behavior |
|---|---|
| PAYEMS succeeds, UNRATE fails | `PARTIAL_FAILURE`; PAYEMS's changes written and audited; UNRATE untouched |
| UNRATE succeeds, PAYEMS fails | Same, reversed |
| Both fail | `FAILED_PROVIDER`; zero writes; zero analysis |
| Both succeed | Normal `CHANGED`/`NO_CHANGE` per §8 |
| One has changes, one unchanged | The changed one drives affected-period computation; the unchanged one contributes nothing, correctly |

**No new behavior needed** — `_check_one_series` already operates
per-mapping, independent of which release or monitor owns the series.

## 20. DB failure / transaction semantics — audited, unchanged

`TestDatabaseFailure::test_a_deliberate_failure_after_provider_success_rolls_back_the_whole_occurrence`
proves the whole-occurrence transaction rollback already works
correctly and generically (real `session_scope()`, a mid-pipeline
failure after a successful provider fetch and observation write still
leaves **zero** durable trace — no check run, no observation write
survives). Frozen for Labor unchanged: the SAME transaction boundary
(one `session_scope()` per occurrence, owned by the caller) covers both
Inflation's and Labor's writes when a release maps series from both
families in one occurrence (not a concern for Employment Situation
specifically, since it maps only Labor series, but the boundary must
remain occurrence-wide, not per-family).

## 21. Retry idempotency — audited, unchanged

`TestIdempotency::test_processing_the_same_occurrence_twice_with_identical_data_creates_no_duplicate_change_events`
already proves this generically (uses UNRATE as its example series).
Re-processing with identical provider data produces zero duplicate
`ReleaseObservationUpdate`/`ReleaseAnalysisUpdate` rows because
`classify_observation_change` returns `UNCHANGED` for every observation
the second time, so `observation_changes` (and therefore
`analysis_changes`, which is entirely derived from it) is empty. No
Labor-specific idempotency risk exists beyond this already-proven
mechanism. `#20D.2` should still add a Labor-specific instance of this
exact test (per §24's test matrix), not because the mechanism differs,
but because #20D.2 introduces the first real code path that could
regress it for Labor specifically.

## 22. Processing-status (#19B) compatibility — audited, ONE real blocker found (same root cause as §17)

`app/repositories/release_processing_read_repository.py` and
`app/services/release_processing_read.py` contain **zero** Inflation-
specific logic (grepped directly — no match for "Inflation",
"PRIMARY_SERIES", "ChangeComponent", or any hardcoded series/component
string). They are pure, already-generic projections over persisted
rows. **Adding Labor `ReleaseAnalysisUpdate` rows will flow through
`detected_analysis_changes` automatically** — with one exception:
`app.models.release_processing_read.DetectedAnalysisChange.component`
has the **identical** `ChangeComponent` type blocker as §17's
`AnalysisChangeRecord` — a persisted Labor row would fail to
deserialize into this response model today. **Frozen fix: the same
`str` widening from §17, applied here too.** No other #19B change
needed; `#19B` itself is not modified beyond this one field's type on
this one model.

## 23. CLI / operational entrypoint — audited, unchanged

`app/operations/process_release.py` is already completely generic — it
calls `ReleaseProcessingService.process_occurrence` once and renders
whatever `result.analysis_changes`/`result.observation_changes`
contain via plain attribute access (`event.component`,
`event.event_type`, …), with no Inflation-specific branch anywhere.
**Zero behavior change needed** for Employment Situation occurrences to
be processable through this exact same mechanism. Only its own
docstring/`argparse` description text says "Inflation analytical
consequence" — a cosmetic wording update for #20D.2, not a functional
one. No new endpoint, scheduler, worker, cron, or frontend button is
introduced, per the mission's explicit prohibition.

## 24. Genericization decision — explicit dispatch, no adapter framework

**Decision: explicit dispatch, not a generic adapter/registry
framework.** Concretely, for #20D.2:

- `app/domain/release_processing.py` (Inflation's own domain layer)
  stays **completely unchanged** — its `SERIES_TO_COMPONENTS`,
  `affected_evaluation_periods`, and `_AFFECTED_HORIZONS_MONTHS` remain
  Inflation-only, exactly as today.
- A new, separate, small domain module —
  **`app/domain/labor_release_processing.py`** — mirrors
  `app/domain/release_processing.py`'s own role, scoped to Labor only:
  `LABOR_SERIES_IDS = frozenset({PAYEMS_SERIES_ID, UNRATE_SERIES_ID})`,
  `payems_affected_evaluation_periods(changed_dates) -> frozenset[date]`
  (the `{0,3,6}` forward rule, §9), `unrate_affected_evaluation_periods(changed_dates)
  -> frozenset[date]` (the `{0,1,2}∪{12,13,14}` forward rule, §10), and
  a small combining helper for the cross-series union (§12). This
  module must not import `app.domain.release_processing` or
  `app.domain.labor`/`app.domain.labor_what_changed` (mirrors every
  existing domain-module-independence guard) — it re-derives its own
  tiny calendar-offset logic exactly as `app.domain.release_processing`
  already does rather than importing `month_before`.
- `app/services/release_processing.py`'s
  `_apply_changes_and_compute_analysis` gains a small, explicit
  partition step: observation changes are split by `series_id`
  membership in `_CANONICAL_SERIES_IDS` (existing, Inflation) vs.
  `LABOR_SERIES_IDS` (new). The existing Inflation branch runs
  unchanged; a new, parallel Labor branch (new private helper
  functions in the same service file, or a small
  `app/services/labor_release_processing.py` sibling if the file grows
  unwieldy — #20D.2's own implementation-time judgment call, not
  frozen here) runs the §13/§14 sequence for Labor. Both branches'
  `AnalysisChangeRecord` lists are concatenated before persistence.

**Rejected:** a `ReleaseAnalysisAdapter` / `GenericEconomicMonitor`-style
plugin framework. Two concrete integrations (Inflation, Labor) do not
justify one, per this project's own repeatedly-applied "no premature
generic framework" principle (#20A/#20B/#20C.1/#20C.2 all reached the
identical conclusion for the monitor layer itself). A third future
integration reusing this exact same explicit-dispatch shape a second
time (not a third-time-generalize-preemptively decision) would be the
appropriate trigger to reconsider.

## 25. Analysis registry — the two frozensets above ARE the registry

No separate "series → analysis family" registry table or module is
needed beyond `_CANONICAL_SERIES_IDS` (existing) and
`LABOR_SERIES_IDS` (new, §24) — both are plain, explicit, compile-time
constants, not a runtime-configurable registry. This directly answers
the mission's own "Analysis Registry Question": the smallest correct
answer is two frozensets and an `if series_id in X` partition, not a
dictionary-of-adapters abstraction.

## 26. Future cross-domain compatibility — stress-tested, no incompatibility found

The §24 explicit-dispatch design does not assume "one release → one
analysis family" (Employment Situation could, in principle, gain a
THIRD mapped series belonging to a future different family without
any structural change — the partition step just gains a third
branch) nor "one series → one analysis family" in a way that's
structurally hard to revisit (a series appearing in two families'
frozensets would simply run both branches for it — the union-based
period logic in §11/§12 already tolerates a series contributing to
multiple downstream consumers, exactly as `PRIMARY_SERIES_ID` already
does for Inflation's own `{"PRIMARY_MOMENTUM", "CONFIRMATION"}` dual
membership today). No permanent one-to-one assumption is introduced.

## 27. #20D.2 implementation changes required (complete list)

1. **New data migration** (`down_revision='cd476d227f99'`): seed
   `Employment Situation → PAYEMS`, `Employment Situation → UNRATE`
   mappings, mirroring `cd476d227f99` exactly (§5).
2. **`app/models/release_processing.py`**: widen
   `AnalysisChangeRecord.component` from `ChangeComponent` to `str`
   (§17).
3. **`app/models/release_processing_read.py`**: widen
   `DetectedAnalysisChange.component` from `ChangeComponent` to `str`
   (§22).
4. **New file `app/domain/labor_release_processing.py`**: PAYEMS/UNRATE
   affected-period derivation, forward-only, sparse (§9/§10/§24).
5. **`app/services/release_processing.py`**: add the Labor branch to
   `_apply_changes_and_compute_analysis` (or an equivalent explicit
   split), reusing `compute_labor_monitor_result_at` and the three
   `app.domain.labor_what_changed` comparator functions by name, never
   reimplementing them (§13/§14/§24).
6. **Cosmetic**: update `app/operations/process_release.py`'s
   docstring/`argparse` description ("Inflation" → "Inflation or Labor")
   (§23).
7. **Test/architecture guards**: extend
   `tests/test_release_processing_architecture.py`'s
   `TestExistingComparisonPrimitivesAreReused` with a Labor-analog
   guard (imports `compute_labor_monitor_result_at`,
   `compare_employment_section`, `compare_unemployment_section`,
   `compare_labor_state` by name) and extend
   `TestNoInflationThresholdOrClassificationLogicInReleaseProcessing`'s
   forbidden-pattern list with Labor's own frozen deadband literals
   (`50_000`, `0.2`), mirroring #20C.2's own AST-level comparator
   guard.

**No schema migration.** No frontend change. No JOLTS/CIVPART/AI. No
public mutation endpoint.

## 28. #20D.2 test matrix (frozen, per the mission's own required matrix)

**Mappings:** Employment Situation maps exactly PAYEMS+UNRATE; no
CIVPART/JOLTS/wages; mapping idempotency (migration re-run safety, same
pattern as existing `cd476d227f99` `UniqueConstraint`-backed
idempotency).

**Observation changes:** new/revised/unchanged PAYEMS; new/revised/
unchanged UNRATE; multiple revisions in one run.

**PAYEMS propagation:** exact `{0,3,6}` sparse set (§9); the offset-1/
offset-2 cancellation-zone regression (mirrors #20B's own
`TestPayemsAffectedHorizons::test_offsets_1_and_2_are_unaffected_by_cancellation`);
multiple changed PAYEMS observations union/dedup; deterministic
chronological ordering.

**UNRATE propagation:** exact `{0,1,2}∪{12,13,14}` set (§10); both
current-window and prior-year-window dependencies independently;
multiple changed UNRATE observations union/dedup.

**Cross-series:** PAYEMS+UNRATE changes in the same run; overlapping
affected periods evaluated exactly once; non-overlapping periods all
evaluated; stable order (§12).

**Before/after:** capture before mutation; calculate after mutation;
same-period comparator (`previous_period == current_period == t`); a
direct negative test proving the monthly `/changes` orchestration
(`month_over_month_labor_periods`) is never called from release
processing (§14).

**Analysis events:** top-level `LABOR.state` change; `EMPLOYMENT.state`
change; `EMPLOYMENT.condition` change; `EMPLOYMENT.momentum` change
(independently, per #20C.2's own no-suppression rule); `UNEMPLOYMENT.state`
change; numeric-only (`METRIC_CHANGED`) change with no state change;
`AVAILABILITY_RESTORED` (a NEW observation making a previously
`INSUFFICIENT_DATA` period sufficient — never `STATE_CHANGED:
INSUFFICIENT_DATA → COOLING`); zero comparator events (cancellation
zone, §15).

**Persistence:** observation changed + analysis changed; observation
changed + analysis unchanged (§15); multiple Labor evaluation periods
in one check run (§16); correct `methodology_id="labor_v1.0"` /
`data_basis="latest_revised_data"` on every persisted row; no duplicate
updates on retry.

**Failures:** PAYEMS provider failure; UNRATE provider failure; both
fail; partial success; DB failure mid-Labor-branch rolls back the
WHOLE occurrence (both Inflation and Labor writes, if both were
touched) — never a partial commit (§19/§20).

**Idempotency:** successful run; exact retry, no duplicate evidence;
retry after a partial provider failure produces only the previously-
missing series' evidence, never re-emitting evidence for the
already-recorded one (§21).

**Processing status (#19B):** `CHANGES_DETECTED`/`NO_CHANGE`/
`PARTIAL_CHECK`/`CHECK_FAILED` all surface correctly for an Employment
Situation occurrence through the existing, unmodified read path once
§17/§22's `str` widening lands; historical detected observation/analysis
changes preserved across retries (§22).

**Architecture:** release processor contains zero `labor_v1.0`/
`labor_what_changed_v1.0` formula literals of its own (AST-level guard,
mirroring #20C.2's own comparator-purity guard); Labor comparator
remains pure (unchanged, already guarded); no AI; no public mutation
endpoint; no frontend dependency; no JOLTS/CIVPART string anywhere in
the new files (mirrors `TestNoJoltsOrCivpartInV1`).

**Regression:** every existing Inflation release-processing test
unchanged and still passing; every Labor monitor (#20B) and Labor What
Changed (#20C.2) test unchanged and still passing; #19B read-model
tests unchanged except the one `component` type-widening assertion.

## 29. GO / STOP criteria — all resolved

| # | Item | Status |
|---|---|---|
| 1 | Exact Employment Situation mapping | Resolved — §5 |
| 2 | Exact PAYEMS propagation direction | Resolved, re-verified computationally — §9 |
| 3 | Exact UNRATE propagation direction | Resolved, re-verified computationally — §10 |
| 4 | Multi-observation union/dedup | Resolved — §11 |
| 5 | Cross-series union/dedup | Resolved — §12 |
| 6 | Before-snapshot timing | Resolved, reuses #18 exactly — §13 |
| 7 | After-snapshot timing | Resolved, reuses #18 exactly — §13 |
| 8 | Same-period comparator reuse | Resolved — §14 |
| 9 | Exact `ReleaseAnalysisUpdate` persistence rule | Resolved — §15 |
| 10 | Persistence cardinality supports multiple Labor periods | Resolved, **no schema change** — §16 |
| 11 | Failure semantics | Resolved, reuses #18 exactly — §19 |
| 12 | Transaction semantics | Resolved, reuses #18 exactly — §20 |
| 13 | Retry idempotency | Resolved, reuses #18 exactly — §21 |
| 14 | #19B compatibility | Resolved, one `str`-widening fix identified — §22 |
| 15 | Seed/migration strategy | Resolved, data migration only — §5 |
| 16 | No hidden Inflation-only blocker | Found and resolved (component type) — §17 |
| 17 | No Labor formulas required in release orchestration | Confirmed — §13/§14 (reuse only) |
| 18 | No unresolved schema limitation | Confirmed — §16 |

No item requires a STOP. No item requires a schema migration.

## 30. Explicitly deferred (unchanged from #20B/#20C.2, not reopened here)

JOLTS confirmation, `CIVPART` context, any Overview frontend surface
for Labor, cross-monitor aggregation, any public HTTP mutation
endpoint, scheduler/worker/cron. Also newly deferred by this audit: a
generic adapter/registry framework (§24, rejected for V1, not merely
postponed for lack of time); reconciling `event_type`'s shared-Literal
convenience into a fully monitor-agnostic vocabulary type (not needed —
already a strict superset that validates Labor's four values as-is).
