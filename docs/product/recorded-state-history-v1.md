# Recorded State History V1 — Product & Architecture Contract Freeze

**Increment #25D.** Contract freeze only. No production code changed. Baseline: HEAD `37995db` ("Add automated economic maintenance (#25C)"), clean working tree. Frontend: 1,032/1,032 passed. Backend: 1,324/1,324 passed, 0 skipped, against the project's established local isolated-Postgres test mechanism.

This document is the authoritative contract for #25E. It settles exactly when a durable record is created, what it may and may not claim, and its exact schema/service/repository shape — it never redesigns automated maintenance (#25B/#25C), never touches economic methodology, and never builds persistence, a migration, an API, or frontend UI itself.

---

## §1. Authoritative material reviewed this turn

Read in full: `docs/product/historical-context-state-history-audit-v1.md` (#24A), `docs/product/state-duration-v1.md` (#24B), `docs/product/post-state-duration-product-loop-retention-audit-v1.md` (#25A), `docs/product/automated-economic-maintenance-v1.md` (#25B). Inspected `docs/adr/024-automated-maintenance-scheduler-orchestrator-separation.md` in full. `docs/architecture/current-architecture.md`, `docs/architecture/request-flows.md`, `docs/ENGINEERING_JOURNAL.md` inspected for their #25C entries specifically (already in context from #25C's own work this session).

---

## §2. Fresh implementation inspection performed this turn

`app/db/models.py` (all nine tables, full file); `app/db/session.py` (`session_scope`, full file); `app/services/release_processing.py` (full file — `process_occurrence`, `_apply_changes_and_compute_analysis`, `_evaluate_component_at`, `_evaluate_labor_at`, `_diff_component_at`, `_diff_labor_at`, `try_acquire_and_process_occurrence`); `app/repositories/release_processing_repository.py` (full file — `add_check_run`'s exact flush/id-assignment order, `list_due_occurrence_ids`); `app/services/maintenance.py` and `app/repositories/maintenance_repository.py` (full files — confirmed no `sweep_id` is threaded into `process_occurrence` or `try_acquire_and_process_occurrence`); `app/models/inflation.py`/`labor.py` (exact `InflationState`/`LaborState` literals, `METHODOLOGY_ID`/`DATA_BASIS` constants, nullability of `calculation_period`/`evaluation_period`). Not re-derived from summary — every claim below citing a specific code behavior was re-confirmed against the file directly, this turn.

---

## §3. Current persisted-evidence inventory (re-confirmed against #25C's own additions)

| Table | Append-only? | Carries monitor state? | What it proves | What it does NOT prove |
|---|---|---|---|---|
| `EconomicObservation` | No — in-place overwrite | No | The current, latest-revised value | Any prior value, or when it changed |
| `ReleaseCheckRun` | Yes | No (`status` only) | A check was attempted, and its provider-fetch outcome | Whether the canonical monitor state changed, stayed the same, or was even recomputed |
| `ReleaseObservationUpdate` | Yes, change-only | No | An observation changed value during one specific check | Nothing about canonical monitor state at all |
| `ReleaseAnalysisUpdate` | Yes, **diff-only** | Only the specific field that *changed* | A canonical fact changed from A to B during one check | **Whether the canonical state was recomputed and found unchanged** — this case writes zero rows (§4) |
| `MaintenanceSweep` (#25C) | Yes | No | An orchestrator run started/finished, with due/processed/failed counts | Anything about any individual occurrence's own economic outcome (deliberately — §30 of #25B) |

**Confirmed, unchanged from #24A/#25B: no table anywhere stores a complete snapshot of `InflationMonitorResult`/`LaborMonitorResult` at any cadence.** #25C added operational provenance (a sweep genuinely ran); it added zero new *economic* recording capability — confirmed directly, `git diff` between #25B's own baseline and #25C's HEAD touches only `app/db/models.py` (adds `MaintenanceSweep`), `app/repositories/{release_processing_repository,maintenance_repository}.py`, `app/services/{release_processing,maintenance}.py`, `app/operations/{process_release,run_maintenance}.py` — no change to `_apply_changes_and_compute_analysis`'s own recording behavior.

---

## §4. The gap, re-confirmed against the exact current code path (not re-derived from #25B's own citation)

Traced fresh, `app/services/release_processing.py:301-355` (`_apply_changes_and_compute_analysis`):

- If `observation_changes` is empty (a `NO_CHANGE` run — every mapped series fetched successfully with nothing new), the function returns `[]` **immediately, at line 321, before calling any `_evaluate_component_at`/`_evaluate_labor_at`.** Canonical monitor computation genuinely does not run at all.
- If `observation_changes` is non-empty but none of the changed series map to a canonical component (`affected_pairs`/`labor_periods` both empty, lines 325-332), observations are written but, again, no canonical computation runs.
- If `affected_pairs`/`labor_periods` is non-empty, `_evaluate_component_at`/`_evaluate_labor_at` genuinely run — **twice each, once for BEFORE and once for AFTER** (lines 335-346) — producing a real, in-memory canonical result. This is diffed (`_diff_component_at`/`_diff_labor_at`, lines 349-354) against `compare_series_momentum_section`/`compare_labor_state`/etc. **If the diff finds zero differences (e.g., the AFTER state is still `COOLING`, exactly as BEFORE), `analysis_changes` gains zero entries for that pair — the genuinely-computed AFTER result is discarded the moment the function returns.**

**Worked answer to the prompt's own named question (§4 of the source prompt):** if EI processes a release at time T, recomputes Inflation as COOLING, and Inflation was already COOLING — **no durable row anywhere proves "EI calculated COOLING at T."** The AFTER evidence was genuinely, correctly computed in memory (line 344/346) and then thrown away, uncaptured, the instant the diff found nothing new. This is the exact, precise gap Recorded State History V1 closes — not a hypothesis, a directly-traced fact about the current, running code.

---

## §5. Recorded State — frozen definition

> **A `RecordedMonitorResult` is an immutable record that Economic Intelligence's own canonical monitor computation genuinely executed — as a real, in-process function call inside a committed release-processing transaction — producing state `S` (or `INSUFFICIENT_DATA`) for evaluation period `P`, under methodology `M`, at calculation time `T`, sourced from the specific `ReleaseCheckRun` whose processing produced it.**

It means, precisely: "EI's own code ran the classification at this exact moment and got this exact answer." It does **not** mean: the objectively correct economy state; the state a provider originally published; the state a user viewed; the state EI would calculate today (that is State Duration's/the live monitor's own job, both unchanged, both untouched by this contract); or an as-known-at-time provider vintage (§23).

---

## §6. "Actually calculated" — the operative test (frozen)

**A state is recorded only when `_evaluate_component_at` (Inflation, `PRIMARY_MOMENTUM` only) or `_evaluate_labor_at` (Labor) is genuinely invoked and returns, inside `process_occurrence`'s own transaction, as the AFTER-evidence half of an existing before/after comparison already performed for `ReleaseAnalysisUpdate`'s own purposes.** No new call is added anywhere in the domain layer to make this true — the computation this document persists is the exact same call `_apply_changes_and_compute_analysis` already makes today, at line 344/346, for a purpose (diffing) that currently discards the AFTER value the moment the diff is empty. **Never synthesize a record from a reconstruction, a backfill, or any code path outside this one, existing, already-transactional call site.**

---

## §7. Recording trigger (frozen, no ties)

**Every time `_evaluate_component_at`/`_evaluate_labor_at` genuinely computes an AFTER result for a `(monitor, evaluation_period)` pair — regardless of whether the subsequent diff against BEFORE produces any `ReleaseAnalysisUpdate` row.** This is a refinement of candidate D ("every canonical monitor recomputation") from the source prompt's own list, made exact by direct code inspection rather than chosen abstractly. **One rule, not two**: this single condition simultaneously answers §9 (unchanged-state: YES, recorded — the AFTER call still ran) and §10 (unchanged-data/`NO_CHANGE`: NO, never recorded — the AFTER call never runs at all, §4) without any separate branch, mirroring this project's own repeated "one condition covers both cases" idiom (e.g. #25C's own "settled today" query, `release_processing_repository.py:236-277`).

---

## §8. Relevant-release rule (frozen: canonical series membership, not display categories)

A monitor is recorded from a given check run only when that run's `observation_changes` include a series that is a genuine input to that monitor's top-level canonical computation, exactly as already encoded by the existing, unmodified machinery:

- **Inflation**: `affected_pairs` (`_affected_component_period_pairs`, `release_processing.py:368-399`, via `components_for_series`) contains a `("PRIMARY_MOMENTUM", period)` entry — which happens precisely when `PRIMARY_SERIES_ID` (Core PCE, `PCEPILFE`) itself changed. A CPI-only or confirmation-only change (Headline CPI, `CONFIRMATION_SERIES_ID`) never touches `PRIMARY_MOMENTUM` and therefore never records an Inflation state — the exact same narrow scoping State Duration V1 already froze (§4/§24 of `state-duration-v1.md`), reused, not reinvented.
- **Labor**: `labor_periods` (`_affected_labor_periods`, via `labor_affected_evaluation_periods`) is non-empty — which happens whenever PAYEMS or UNRATE changed. `_evaluate_labor_at` always computes the full `LaborMonitorResult` (state + evaluation_period) in one call, so any qualifying period records Labor's own top-level `state`.

No "release category" concept is invented or consulted — membership is exactly the existing series→component mapping already used for `ReleaseAnalysisUpdate`, reused verbatim.

---

## §9. Unchanged-state semantics (frozen: YES, recorded — this is where V1 earns its value)

**Recorded, unconditionally, whenever §7's trigger fires** — including when the AFTER state exactly equals the BEFORE state. This is not meaningless duplication: each such row is a genuinely new, independently-dated proof that EI *re-verified* the state at a later calculation time, something no existing table can express (§4). "Confirmed unchanged three times over two months" and "computed once and never re-checked" are observably different claims once this exists — they are indistinguishable today.

---

## §10. Unchanged-data semantics (frozen: NO — traced directly to code, not inferred)

**A `NO_CHANGE` `ReleaseCheckRun` (zero `observation_changes`) never reaches `_evaluate_component_at`/`_evaluate_labor_at` at all** (§4) — canonical computation genuinely does not run, so nothing is recorded. This is a hard structural fact, not a policy choice this contract is free to override: recording a state here would require inventing a fabricated computation event that never executed, violating §6 directly.

---

## §11. Retry semantics (frozen, derived from §7/§10, no new logic needed)

Worked example (source prompt's own): 09:00 `NO_CHANGE`, 10:00 `NO_CHANGE`, 11:00 `NEW` data → recompute. **Only the 11:00 run creates any `RecordedMonitorResult` rows** — the two `NO_CHANGE` runs never reach the recomputation step (§10), so nothing is ever recorded for them, and no attempt is ever "claimed" that didn't genuinely occur.

---

## §12. Revision semantics (frozen: append-only, required default)

A later provider revision to a period a prior `RecordedMonitorResult` already covers **never updates or deletes that row.** The revision's own reprocessing produces a new `ReleaseCheckRun` and — if it re-triggers `_evaluate_*_at` for that period (which a genuine revision to a required input month always will) — a **new** `RecordedMonitorResult` row, at a new `calculated_at`, for the same `(monitor, evaluation_period)`. Both rows persist forever, side by side. This is not merely permitted by the schema (§13) — it is the entire reason recorded history has value that reconstruction does not (#24A §35).

---

## §13. Same-evaluation-period, multiple-calculations — identity (frozen)

**Identity is `(release_check_run_id, monitor, evaluation_period)`, enforced as a `UNIQUE` constraint — never `(monitor, evaluation_period, methodology_id)`,** which the source prompt correctly flags as destructive: it would collide across every legitimate repeat (a later release, a revision reprocessing, a manual retry after automation). `release_check_run_id` is the one thing that is always unique per genuine processing attempt (§17 of #25B — `ReleaseCheckRun` rows are never deduplicated), so keying off it, plus the monitor and the specific period this call evaluated, prevents only the one genuine bug case (accidentally writing the same monitor+period twice *within one call's own loop*) while never blocking the many legitimate cross-run repeats this feature exists to capture.

**Multiple periods within one run are real and expected**, not an edge case: a Labor benchmark revision to PAYEMS can legitimately affect evaluation periods `{t, t+3, t+6}` in a single `process_occurrence` call (`labor_affected_evaluation_periods`'s own existing propagation, unmodified) — producing up to three `RecordedMonitorResult` rows for `monitor="labor"` from one `release_check_run_id`, correctly distinguished by `evaluation_period`. The unique constraint's three-column shape is required precisely because of this, not a defensive afterthought.

---

## §14. Observation-time vs. evaluation-period distinction (frozen, reused verbatim from #24A/#24B's own already-frozen vocabulary)

`calculated_at` (when EI ran the computation) and `evaluation_period` (which calendar month the computation is about) are structurally independent fields, exactly as `state-duration-v1.md` §5 and `historical-context-state-history-audit-v1.md` §14 already established for their own objects. A row calculated on `2026-09-15` can describe `evaluation_period = 2026-08-01` (this month's release covers last month's data) — never conflated, never derived one from the other.

---

## §15. `calculated_at` — exact definition (frozen: the SAME timestamp as the owning `ReleaseCheckRun.completed_at`, not a new clock read)

**Frozen: `calculated_at` reuses the exact `completed_at` value already captured once in `process_occurrence`** (`release_processing.py:211`, `datetime.now(timezone.utc)`), applied to every `RecordedMonitorResult` row written during that same call. **No new clock read is added anywhere** — this directly honors #25B's own §57 clock-injection discipline ("the orchestrator's own 'now' must be resolved exactly once... never re-read ad hoc at multiple points"), extended here to the service layer for the first time it becomes relevant at this grain. All AFTER-evidence computation for one occurrence happens synchronously, inside one transaction, before `completed_at` is captured at line 211 — using that single value for every row this call writes is both simpler and more honest than pretending sub-transaction timing precision the product has no use for.

---

## §16. `recorded_at` — decision (frozen: not a separate field)

**Not needed as an independent column.** Persistence occurs atomically, inside the same transaction as the computation it describes (§65) — `calculated_at` and "when this row became durable" are the same instant by construction, so a second timestamp would be redundant, not merely unused. The standard `created_at` bookkeeping column (server-default `func.now()`, present on every table in this schema) is retained for schema consistency, exactly as `ReleaseCheckRun` already carries both a semantic `completed_at` and a mechanical `created_at` side by side — but `created_at` here is DB-insert bookkeeping only, never treated as a second semantic timestamp a caller should read.

---

## §17. Methodology provenance (frozen)

`methodology_id` is copied directly from the domain result the genuinely-executed computation returned (`METHODOLOGY_ID` constant, `"inflation_v1.0"`/`"labor_v1.0"`, already present on every `InflationMomentumResult`/`LaborMonitorResult`-shaped object) — never inferred, never defaulted, never re-derived from "whatever is current now" at read time.

---

## §18. Future methodology-version behavior (frozen, restated from #24B §17/§27, now for recorded rather than reconstructed rows)

A future `inflation_v1.1` never rewrites `inflation_v1.0`-tagged rows. A query spanning the transition returns **mixed** `methodology_id` values honestly — a future consumer must group or label by `methodology_id`, never assume a query's results share one methodology. No migration/backfill of old rows' `methodology_id` is ever performed.

---

## §19. State storage strategy (frozen)

`state`: a plain `String`, storing the domain's own literal value verbatim (`"COOLING"`, `"STABLE"`, `"INSUFFICIENT_DATA"`, etc. — `InflationState`/`LaborState`'s own existing literals, §20 of `state-duration-v1.md`'s own precedent for reuse). **Never a native database `ENUM` type** — confirmed by inspecting every existing status/state column in `app/db/models.py` (`ReleaseCheckRun.status`, `ReleaseAnalysisUpdate.component`/`event_type`/`field`) — none use a Postgres enum; all are plain `String`, so a future new state value never requires a migration, and an old row's value is never silently reinterpreted or normalized when the application-level literal set evolves.

---

## §20. Monitor/subject identity (frozen)

`monitor`: a plain `String`, values `"inflation"` / `"labor"` — matching the lower-case, stable, internal-identifier convention this codebase already uses for `component` values (`"PRIMARY_MOMENTUM"`, `"CONFIRMATION"`, etc. are upper-case internal identifiers; monitor names follow the page-route-shaped lower-case convention instead, since these two literal strings will appear in a future read-API path parameter, mirroring `/monitors/inflation`/`/monitors/labor` exactly). Never a UI label. Not generalized to an arbitrary future subject list beyond these two — no third value is anticipated or reserved.

---

## §21. Evaluation-period representation (frozen: always the requested period, never a possibly-null echoed field)

**`evaluation_period` is a `Date`, `NOT NULL` — always the specific period `_evaluate_component_at`/`_evaluate_labor_at` was explicitly asked to evaluate** (the loop variable from `affected_pairs`/`labor_periods`, always a concrete date, never derived from searching). This is a deliberate, load-bearing distinction from the domain result's *own* `calculation_period`/`evaluation_period` field, which both domains null out specifically when the computed state is `INSUFFICIENT_DATA` (confirmed, `state-duration-v1.md` §14, `app/models/labor.py:120-123`) — that nulling reflects "no meaningful period to speak of" for the *live/reconstructed* case, but Recorded State always knows, with certainty, which period it evaluated, because it never searches for one; it is handed one. Persisting the requested period (not the domain object's own possibly-null echo) keeps `evaluation_period` reliably queryable even for `INSUFFICIENT_DATA` rows (§37/§83).

---

## §22. Data-basis terminology (frozen: reused verbatim)

`data_basis: "latest_revised_data"` — the exact existing `DATA_BASIS` constant, unchanged, carrying its existing meaning: the observations persisted in `EconomicObservation` **at the moment of this specific calculation**, not any provider vintage. Because `EconomicObservation` itself mutates in place (§3), this field's honest meaning is precisely "whatever EI currently had on file when it calculated this" — not a promise that those exact numeric inputs remain reconstructable later (§23).

---

## §23. As-known-at-time boundary (frozen: explicitly NOT claimed)

**Recorded State proves EI's own OUTPUT at time T. It does not, and cannot, prove EI's exact INPUT values at time T were the exact values a later observer could reconstruct** — because `EconomicObservation` overwrites in place (§3/§4A of #24A) and no ALFRED/vintage integration exists (§15 of #24A, unchanged). If a later revision changes the same input the row's own computation used, the row's `state` remains a true historical fact ("EI calculated COOLING using whatever data was on file then") while the exact numeric inputs behind it are no longer independently reconstructable from `EconomicObservation` alone. This boundary must be stated explicitly in any future disclosure (§88) — never blurred into an "as-known-at-time" claim.

---

## §24. Source-event provenance (frozen: `ReleaseCheckRun`, exclusively)

`release_check_run_id`, `NOT NULL`, `FOREIGN KEY → release_check_runs.id`. This is the one row that (a) already exists, atomically, inside the exact same transaction as the computation (§4), (b) is created identically regardless of manual or automated origin (§27), and (c) already proves "a check occurred at this exact moment, for this exact occurrence." No stronger or weaker provenance is needed or justified.

---

## §25. `ReleaseCheckRun` FK finding (frozen: no sequencing change required, contra the source prompt's own worry)

**Traced precisely, this turn: `ReleaseCheckRun` is created (and flushed, obtaining a real id) at `release_processing.py:213` — AFTER `_apply_changes_and_compute_analysis` (line 209) has already computed the AFTER evidence in memory.** The source prompt's own §104 anticipated this might require restructuring the transaction (creating the run earlier, or flushing mid-computation). **It does not.** The existing, correct sequencing is preserved exactly: `_apply_changes_and_compute_analysis` is extended to also *return* the recordable results it already computes in memory (a second return value, not a new call), and `process_occurrence` persists them in a new step immediately after `check_run = repo.add_check_run(...)` already obtains `check_run.id` — the identical pattern already used for `add_observation_update`/`add_analysis_update`, which also wait for that same id. **`ReleaseCheckRun`'s own meaning, timing, and creation order are unchanged by this feature, exactly as §105 of the source prompt requires.**

---

## §26. `MaintenanceSweep` provenance (frozen: not used, correctly)

**Confirmed, fresh, this turn: no `sweep_id` is threaded into `try_acquire_and_process_occurrence` or `process_occurrence` anywhere in the current #25C implementation** (`app/services/maintenance.py:114-121` calls `try_acquire_and_process_occurrence(self._service, occurrence_id, session, as_of_date)` — no sweep identifier passed). This is not a gap to fix here — it is the *correct* consequence of §55/§48 of #25B's own frozen scheduler/orchestrator boundary (the orchestrator must never leak into, or be required by, `process_occurrence`'s own signature) and of §27 below (manual processing must produce equally valid Recorded State, and manual processing has no sweep at all). `ReleaseCheckRun` alone is sufficient provenance (§24); `MaintenanceSweep` is never referenced by `RecordedMonitorResult`.

---

## §27. Manual-processing behavior (frozen: YES, identical)

`try_acquire_and_process_occurrence` is the ONE shared entry point both `app/operations/process_release.py` (manual CLI) and `MaintenanceOrchestrator.run_sweep` (automated) call (confirmed, ADR-024). Because Recorded State's own persistence step lives inside `process_occurrence` itself (§25), **a manual CLI invocation produces exactly the same `RecordedMonitorResult` rows an automated sweep processing the identical occurrence would** — no special-casing, no origin check, no different code path. This is a direct, structural consequence of §25/§62, not a policy this document imposes separately.

---

## §28. Automated-vs-manual distinction (frozen: NOT recorded — a named, accepted V1 limitation)

Given §26/§27, **`RecordedMonitorResult` cannot, and does not attempt to, prove whether a given row's originating check was triggered automatically or manually.** Adding a boolean or enum for this would require either (a) plumbing a new parameter through `process_occurrence`'s own signature (a real, if small, change to an already-frozen, tested #25C entry point, not justified by this increment's own evidence — the source prompt's own §28 explicitly warns "do not add fields without product value"), or (b) inferring it unreliably from context. **No product requirement identified in this document needs this distinction** — Recorded State's own value proposition (§9) is about *what was calculated*, never *who triggered it*. Deferred, not solved, named explicitly rather than silently omitted.

---

## §29. Processing-origin enum (frozen: not introduced, consistent with §28)

No `processing_origin` field. If a future increment identifies a real product need for this distinction, it must be solved at `process_occurrence`'s own call-site boundary (an explicit parameter passed by each of the two callers, who already know their own identity), never inferred from `RecordedMonitorResult`'s own absence of a `MaintenanceSweep` FK — inference would be exactly the kind of guess §29 of the source prompt warns against.

---

## §30. Immutability (frozen: INSERT-only through normal application code; no UPDATE/DELETE exposed)

The repository method set exposes exactly one write operation — `add_recorded_monitor_result` — mirroring `ReleaseObservationUpdate`/`ReleaseAnalysisUpdate`'s own repository, which likewise expose only `add_*` methods, never `update_*`/`delete_*` (direct, already-existing precedent, re-confirmed this turn, `release_processing_repository.py:170-200`). No application code path ever mutates or removes a `RecordedMonitorResult` row. A database-level `DELETE`/`UPDATE` remains physically possible (Postgres does not enforce application-level immutability) but is never exercised by any shipped code — the same honest boundary every other append-only table in this schema already accepts.

---

## §31. Correction policy (frozen V1 limitation, named explicitly)

**No invalidation mechanism ships in V1.** If a genuine software defect is later discovered to have produced an incorrect row (a true bug, not a provider revision or methodology change — §100), the only V1-supported remedy is a controlled, out-of-band database correction performed by an operator — never a silent application-level rewrite. This is an accepted, explicitly-named limitation, not an oversight: `invalidated_at`/`superseded_by`-shaped correction machinery is a real future possibility, deliberately deferred (mirrors this project's own repeated "name the limitation, don't half-build the fix" discipline, e.g. #25C §23's own accepted database-failure gap).

---

## §32. Duplicate-retry / idempotency (frozen: zero duplicate rows, inherited for free)

Two mechanisms already guarantee this without any new logic:

1. **Sequential duplicate retry** (identical processing invoked twice with no new provider data in between): the second call finds `observation_changes` empty (everything was already written by the first call) → `NO_CHANGE` → §10's early-return path fires → zero rows, for the same structural reason `ReleaseObservationUpdate`/`ReleaseAnalysisUpdate` already don't duplicate (§17 of #25B).
2. **Concurrent duplicate** (two overlapping attempts against the *same* occurrence): the advisory lock (`try_acquire_and_process_occurrence`, unmodified) already prevents a second concurrent call from ever reaching `process_occurrence` at all — it returns `None` before any computation runs. Recorded State inherits this concurrency protection automatically, since its own write step lives entirely inside the code the lock already gates.

No new deduplication logic is required or written.

---

## §33. Computation-event identity (frozen, restated from §13)

`(release_check_run_id, monitor, evaluation_period)`, `UNIQUE`. Confirmed against §13's own worked reasoning: allows the same evaluation period to legitimately recur across different check runs (revisions, retries, multiple releases) while preventing a genuine bug from writing the same monitor+period twice within one call's own loop.

---

## §34. Release checks with multiple monitors (frozen: schema allows it; not exercised by today's curated mappings)

The `monitor` column (§20), combined with §33's own three-column uniqueness, already allows one `release_check_run_id` to produce rows for both `"inflation"` and `"labor"` — no one-to-one assumption is hard-coded anywhere in the schema. **Today's curated release→series mappings never actually exercise this** (Inflation's four canonical series and Labor's two are disjoint sets, per #21's own release inventory, re-confirmed unchanged) — but the schema does not assume or require that disjointness to remain true.

---

## §35. Failed-processing behavior (frozen: zero rows, by construction)

If the surrounding transaction fails for any reason before commit, `RecordedMonitorResult` rows (like `ReleaseCheckRun`/`ReleaseObservationUpdate`/`ReleaseAnalysisUpdate` rows from the same attempt) never durably exist — `session_scope`'s own rollback-on-exception behavior (§2, re-confirmed) applies uniformly to every write inside the transaction, with no special handling needed or added.

---

## §36. Partial-failure behavior (frozen: keyed to genuine execution, not to the overall `CheckRunStatus` label — a nuance worth stating explicitly)

**A `PARTIAL_FAILURE` run CAN still produce a genuine `RecordedMonitorResult` row.** Traced precisely: if PAYEMS's fetch succeeds and changes while UNRATE's fetch fails, `observation_changes` still contains PAYEMS's own changes (`release_processing.py:200-208`, only a *failed* series is excluded from `observation_changes`) — `_affected_labor_periods` still fires, and `_evaluate_labor_at` still genuinely computes Labor's full state using PAYEMS's newly-written value alongside UNRATE's currently-persisted (unaffected by today's failed fetch) value. **This is a real, successfully-executed computation** — the fact that UNRATE's fetch failed today doesn't retroactively make the Labor state calculation itself synthetic. Recording is keyed to §7's own trigger (did `_evaluate_*_at` genuinely run), never to the coarser `CheckRunStatus` label — these are related but distinct facts, and conflating them would either under-record (skip a genuine computation because the overall run was labeled partial) or over-record (nothing here risks over-recording, since §7's own trigger already requires genuine execution).

---

## §37. Insufficient-data decision (frozen: YES, recorded — uniformly for both domains)

Both `_evaluate_component_at`(`PRIMARY_MOMENTUM`) and `_evaluate_labor_at` can genuinely return an `INSUFFICIENT_DATA` state as a real, successfully-computed classification (not a crash, not a skip — the exact same "a real, non-error return value" property `state-duration-v1.md` §8/§9 already established and relied on). **Decision: record it, identically for Inflation and Labor** — no domain-specific asymmetry, because nothing in the underlying code treats the two differently at this level. `state = "INSUFFICIENT_DATA"` is stored as an ordinary literal value (§19) — no separate nullable "status" column is needed, since the domain's own state enum already encodes this distinction, and `evaluation_period` remains non-null regardless (§21).

---

## §38. Availability-history consequence (frozen: accepted, intentional)

Because §37 records `INSUFFICIENT_DATA` rows, `RecordedMonitorResult` is, honestly, **canonical-result history, not narrowly "state-only" history** — it can prove "EI calculated and found insufficient evidence at T," which a state-only design would silently lose. This consequence is intentional, not incidental — it directly serves a real future capability (proving *when* a monitor's own data availability transitioned into or out of `INSUFFICIENT_DATA`) that a narrower design would foreclose for no compensating benefit.

---

## §39. Domain model name (frozen: `RecordedMonitorResult`)

Evaluated: `RecordedMonitorResult`, `MonitorCalculationRecord`, `CanonicalMonitorRecord`, `RecordedState`. **`RecordedState` is rejected** — too narrow now that §38 confirms `INSUFFICIENT_DATA` rows are in scope (this is a *result*, not always a *state*). **`RecordedMonitorResult` is frozen**: it directly extends this codebase's own established `*Result` naming idiom (`InflationMonitorResult`, `LaborMonitorResult`, `ReleaseCheckRunResult`) — "the output of a canonical computation" — rather than inventing new vocabulary, and does not overclaim precision the way "Snapshot" would (this is a single state value, not a multi-field point-in-time dump — §40-44). Table name: `recorded_monitor_results`.

---

## §40. Minimal persisted fields (frozen)

```
id                    PK
release_check_run_id  FK -> release_check_runs.id, NOT NULL      (§24)
monitor               String(16), NOT NULL     "inflation" | "labor"     (§20)
evaluation_period     Date, NOT NULL                                      (§21)
state                 String(32), NOT NULL     incl. "INSUFFICIENT_DATA"  (§19/§37)
methodology_id        String(32), NOT NULL                                (§17)
data_basis            String(32), NOT NULL     "latest_revised_data"      (§22)
calculated_at         DateTime(timezone=True), NOT NULL                   (§15)
created_at            DateTime(timezone=True), server_default=func.now(), NOT NULL   (§16, bookkeeping only)
```

No field not justified above is included.

---

## §41. Metric persistence decision (frozen: NO, V1)

3M/12M Core PCE, payroll averages, and similar numeric evidence are **not** persisted. Arguments for (stronger auditability) were weighed against arguments against (scope explosion; raw observations already exist but themselves revise, so a metric snapshot alone would not achieve genuine point-in-time input fidelity without also solving §23's own vintage-data gap, which this increment does not attempt). **V1 persists the classified output only.**

---

## §42. Evidence persistence decision (frozen: NO, V1 — state only)

No machine-readable evidence payload, no JSON blob, no per-component breakdown. Matches §41's own reasoning exactly and the same minimal-contract discipline `state-duration-v1.md` §32 already applied to its own response shape.

---

## §43. State-only limitation (frozen, stated explicitly, accepted)

**V1 can prove:** "EI classified Inflation COOLING at T, for evaluation period P, under methodology M." **V1 cannot prove:** "these exact input values caused it" — that would require either persisting the metric evidence (§41/§42, deferred) or a genuine vintage-data system (§23, deferred, out of scope entirely per #24A §15/§47). **This is acceptable for V1**: the state itself is the asset #24A §35 identified as genuinely non-reproducible; the supporting evidence remains reconstructable-but-not-recorded, an honest, named, bounded gap — not a silent one.

---

## §44. Future evidence snapshots — schema non-blocking (confirmed)

§40's schema does not prevent a **future**, additive sibling table (e.g. `recorded_monitor_evidence`, keyed by `recorded_monitor_result_id`) from later adding metric-level detail, input provenance, or vintage data, without ever needing to alter or reinterpret any V1 row. No column in §40 is a placeholder pretending future capability it doesn't have — the schema is honestly minimal today and honestly extensible later.

---

## §45. Relation to `ReleaseAnalysisUpdate` (frozen: distinct, not a replacement)

`ReleaseAnalysisUpdate` represents a **change event** (field X went from A to B); `RecordedMonitorResult` represents a **calculation result** (the state was S), written regardless of whether anything changed (§9). Neither replaces the other — `ReleaseAnalysisUpdate` remains the fine-grained, field-level diff audit trail exactly as it is today; `RecordedMonitorResult` is a new, coarser, always-written top-level fact. Both are populated from the same `_apply_changes_and_compute_analysis` call, from the same BEFORE/AFTER evidence, without duplicating each other's own purpose.

---

## §46. Relation to What Changed (frozen: distinct, not replaced)

What Changed (`inflation_what_changed_v1.0`/`labor_what_changed_v1.0`) computes live, on-demand, period-over-period comparisons — it is not persisted, and this contract does not persist it either. `RecordedMonitorResult` could, in a **future** increment, power a genuinely new historical transition stream (walking ordered rows to find state changes, §93) — but V1 does not build that, and What Changed's own existing live-comparison behavior is completely unchanged by this document.

---

## §47. Relation to State Duration (frozen: distinct, State Duration unaffected)

State Duration (#24C/#24D) is a **latest-revised reconstruction** — recompute-only, no persistence, reflecting today's data reapplied uniformly across history (§40 of `state-duration-v1.md`). `RecordedMonitorResult` is the **recorded** half of the same distinction #24A's own vocabulary (§37 there) already drew and this contract inherits unchanged. They will disagree, by design, exactly as #24A §12 already predicted — a future UI could show both side by side (out of scope here) without ever blending them into one number. Zero code in `app/domain/state_duration.py` or the state-duration service methods is touched by this increment.

---

## §48. Relation to Since Last Visit (frozen: the unlock, stated precisely)

Once #25E ships, a future Since Last Visit increment gains a genuinely new, truthful capability it does not have today: **"was Inflation recalculated since your last visit, and did it change or stay the same?"** — answerable by querying `RecordedMonitorResult` rows with `calculated_at` after the viewer's own last-visit timestamp, distinguishing "recalculated, unchanged" (§9's own value) from "recalculated, changed" (already partially visible via `ReleaseAnalysisUpdate`) from "not recalculated at all" (no row — visible for the first time). This document does not design Since Last Visit's own UI/copy/semantics — those remain a future increment's job, unblocked, not accelerated, by this one.

---

## §49. Relation to automation (frozen: neither implies the other, restated precisely)

Automation (#25C) provides *opportunities* for genuine recomputation to happen more regularly; Recorded State *captures* whatever computation genuinely executes, from either origin (§27). Automation does not need Recorded State to function (it already runs without it, per current HEAD); Recorded State does not need automation to function (manual processing produces identical rows, §27) — but Recorded State's own *comprehensiveness*, as an asset, depends on automation running reliably over time, exactly as #25B §35/§42/§65 already reasoned and this document does not re-litigate.

---

## §50. First-recording date (frozen: deployment date of #25E, no earlier)

Recorded history begins the moment #25E's migration and code are deployed and the first qualifying `process_occurrence` call runs afterward. No earlier date is ever implied.

---

## §51. No-backfill rule (frozen, hard)

**Historical calculations performed after #25E's deployment may be reconstructed (via State Duration or a future history endpoint), but must never be inserted into `recorded_monitor_results` as though they had been contemporaneously recorded.** No script, migration, or one-time job may synthesize `RecordedMonitorResult` rows for periods processed before #25E existed. If a future increment ever wants to surface pre-#25E reconstructed history alongside recorded history, it must do so through a visibly different, honestly-labeled path (§47) — never by backfilling this table.

---

## §52. Pre-recorded era (frozen: distinguishable, by absence)

A query for `(monitor, evaluation_period)` rows before #25E's own deployment date returns **zero rows** — indistinguishable, by row content alone, from "EI genuinely never recalculated this period" versus "recording didn't exist yet." A future consumer (e.g. Since Last Visit) must treat any period before #25E's deployment as `UNKNOWN` coverage, never `STALE` and never "confirmed unchanged" — mirroring #25B §29's own already-frozen three-state discipline (`UNKNOWN` vs. `FRESH` vs. `STALE`) applied here to recorded-state coverage specifically. #25E should document its own deployment date/first-observed-row timestamp in the engineering journal so a future increment has a concrete boundary to reference, without adding any new column for it (an application-level fact, not a schema-worthy one, mirroring #25B §51's identical reasoning for `automation_started_at`).

---

## §53. Coverage-gap semantics (frozen: automation gaps produce real gaps, never filled)

If the scheduler is down for three days, `RecordedMonitorResult` simply has no rows for whatever recomputations would have happened in that window — an honest gap, never filled by reconstruction-labeled-as-recorded (§51's own rule applies identically here, not just at the pre-deployment boundary). A future consumer distinguishes a genuine gap from "nothing needed recomputing" only by cross-referencing `MaintenanceSweep`'s own coverage (§26 — no direct FK is needed for this; a future read layer can correlate by time range, since both tables carry real timestamps) — this document does not build that correlation, only confirms the schema does not block it.

---

## §54. Manual-fill-during-gap behavior (frozen: creates a real record, at the real later time — restated precisely)

If an operator manually processes a missed occurrence after a scheduler outage, that call is processed by the identical `process_occurrence` path (§27) and creates a genuine `RecordedMonitorResult` at **the actual calculation time it ran**, never backdated to when the scheduler should have run. The gap between the missed scheduled date and the actual manual-fill `calculated_at` remains visible and honest in the data.

---

## §55. Future read-contract shape (described, not implemented)

If a future increment builds `GET /api/v1/monitors/{monitor}/recorded-history`, the natural response shape, informed by §40's own schema: a bounded, paginated list of `{evaluation_period, state, methodology_id, calculated_at, release_check_run_id}` ordered per §61, filterable by a `calculated_at` range and/or `evaluation_period` range, never unbounded (matching this project's own established pagination discipline, `state-duration-v1.md` §34's identical reasoning applied here in reverse — this future endpoint genuinely needs pagination, since it returns a list, unlike State Duration's own single-fact response). **Not designed further, not implemented, not scheduled by this document** — explicitly left to whichever future increment (Since Last Visit, or a dedicated history-API increment) first needs it (§56 report item / §108 below).

---

## §56. Query/index requirements (frozen)

Two genuinely useful query dimensions, both directly supported by §40's schema without over-indexing:

- **`monitor` + `calculated_at` range** (§58 report item) — the primary dimension for "what did EI record recently" / Since Last Visit's own future needs. Index: `(monitor, calculated_at)`.
- **`monitor` + `evaluation_period`** (§59 report item) — "show every time EI calculated August 2026." Index: `(monitor, evaluation_period)`.
- **`release_check_run_id`** (§60 report item, provenance/debugging) — already covered by the FK's own implicit index plus the `UNIQUE(release_check_run_id, monitor, evaluation_period)` constraint's own composite index, no separate index needed.

No third index is added speculatively — two targeted composite indexes, matching exactly the two query shapes named above, nothing broader.

---

## §57. Latest-recorded-result query readiness (confirmed supported)

"Latest result before timestamp X" / "results after timestamp X" (a future Since Last Visit need) are both directly served by the `(monitor, calculated_at)` index (§56) with a simple range filter plus `ORDER BY calculated_at DESC LIMIT 1` (latest) or `WHERE calculated_at > X` (since). No additional schema is required for this readiness.

---

## §58. Deterministic ordering (frozen)

**`calculated_at DESC, id DESC`** — matching `MaintenanceRepository.get_latest_sweep`'s own identical tie-break convention (`started_at.desc(), id.desc()`), reused for consistency rather than inventing a different convention for a structurally similar "most recent, tie-broken by insertion order" query.

---

## §59. Persistence location (frozen: inside `process_occurrence`, same transaction — restated precisely per §25/§65)

Persisted from within `app/services/release_processing.py`'s own `process_occurrence`, immediately after `check_run = repo.add_check_run(...)` obtains a real id (§25/§103) — never from a route, never from a read endpoint, never from the orchestrator.

---

## §60. Domain/service boundary (frozen)

`app/domain/inflation.py`/`labor.py` are **completely unmodified** by this feature — they already return everything needed (`state`, the period they were asked to evaluate, `methodology_id`, `data_basis`) as part of their existing, unmodified result objects. All new logic — deciding *which* AFTER results are recordable and building the small in-memory objects to persist — lives in the service layer (`release_processing.py`), never in the domain layer. This is the same Route → Service → pure Domain layering every prior increment already applies, restated for a new write path, not a new principle.

---

## §61. Repository boundary (frozen: extend `ReleaseProcessingRepository` — NOT a new, separate repository)

**Decision, made against fresh code evidence, not by reflex-following a "likely dedicated repository" hint:** `ReleaseObservationUpdate`/`ReleaseAnalysisUpdate` — the two existing tables `RecordedMonitorResult` is most directly analogous to (both are per-`ReleaseCheckRun`, append-only, audit-shaped) — already live inside `ReleaseProcessingRepository` itself, not their own separate repositories (confirmed, `release_processing_repository.py:170-200`). A new `add_recorded_monitor_result` method is added to that **same** repository, sharing its existing `Session`, its existing transaction-boundary discipline (§8 of that file's own docstring: never calls `commit()`/`rollback()` itself), and its existing FK (`release_check_run_id`). **This is a different, more precedented answer than `MaintenanceSweep`'s own separate-repository choice** — `MaintenanceSweep` earned its own repository because it is genuinely a different-shaped concept with its own independent transaction lifecycle (§53 of #25B); `RecordedMonitorResult` shares its transaction, its FK, and its closest sibling tables' own repository placement, so it belongs there instead.

---

## §62. Transaction atomicity (frozen, hard constraint, directly satisfied)

`RecordedMonitorResult` rows commit in the exact same transaction as the `ReleaseCheckRun`/`ReleaseObservationUpdate`/`ReleaseAnalysisUpdate` rows from the same call — no new transaction boundary is introduced anywhere. This directly satisfies #25B §41's own forward-looking hard constraint, frozen specifically for whenever this increment arrived: "the snapshot write must occur inside the same transaction as the successful analysis recomputation it describes."

---

## §63. Read-side prohibition (frozen: `GET` never writes)

`GET /api/v1/monitors/inflation`/`/labor` (the live monitor endpoints) and any future State Duration/history read endpoint **never** call `process_occurrence`, `_apply_changes_and_compute_analysis`, or the new repository write method — confirmed structurally true today (these routes only ever construct read-only services, per every prior increment's own architecture guards) and must remain true. **Hard architecture guard required for #25E**: no route module imports `add_recorded_monitor_result` or constructs `ReleaseProcessingRepository` for a write.

---

## §64. Other write-path behavior (frozen: none, confirmed)

Plain series sync (`SeriesRepository._upsert_observations`, `/series/{id}/sync`) never invokes any monitor computation at all (#24A §4, re-confirmed unchanged) — no Recorded State there. `POST /releases/sync` (calendar sync) never touches observations. No other write path in this codebase calls a canonical `_at` function. Confirmed by the same full-repository inspection performed for #25C's own architecture guards, applied here.

---

## §65. Canonical scope (frozen: Inflation Monitor + Labor Monitor top-level state only — the same narrow subject State Duration V1 already froze)

Reuses `state-duration-v1.md` §4's own exact scope, not a broader "full `InflationMonitorResult`" interpretation: `underlying_momentum.state`/`calculation_period` (Inflation), `LaborMonitorResult.state`/`evaluation_period` (Labor). **Excluded, explicitly, matching §4 there exactly:** `HeadlineContextResult`, `ConfirmationResult.relationship`, `EmploymentState`, `UnemploymentTrendState`, `EmploymentCondition`/`EmploymentMomentum`, any individual numeric metric.

---

## §66. Relate exclusion (frozen)

Relate's composed sentence is never itself recorded — it composes two independently-recorded facts (§72 of the source prompt's own framing) and stays fully live/on-demand, unchanged.

---

## §67. State Duration exclusion (frozen, restated from §47)

Never snapshotted. State Duration's own recompute-only architecture (`state-duration-v1.md` §40) is untouched.

---

## §68. Salience exclusion (frozen)

Salience tiers (#22B) are a presentation-layer concept, never persisted as historical canonical output — no relationship to this table at all.

---

## §69. What Changed exclusion (frozen, restated from §46)

Kept fully distinct — event vs. result, as already established.

---

## §70. Sweep-with-no-work / no-observation-change behavior (frozen, restated precisely from §10)

A `MaintenanceSweep` finding zero due work creates zero `RecordedMonitorResult` rows (nothing was processed at all). A processed occurrence whose check is `NO_CHANGE` likewise creates zero rows (§10) — both are correct, expected, zero-row outcomes, never worked around or papered over with a placeholder row.

---

## §71. Storage type (frozen: plain columns, no JSON, no native enum)

Every column in §40 is a plain scalar type (`Integer`, `String`, `Date`, `DateTime`) — no `JSON`/`JSONB` column anywhere, matching §42's own state-only decision, and no native Postgres `ENUM` type anywhere, matching §19's own reasoning and this schema's own 100%-consistent existing convention (confirmed, no `ENUM` type is used anywhere in `app/db/models.py` today).

---

## §72. Generic-vs-per-monitor decision (frozen: ONE generic table)

`recorded_monitor_results`, not `inflation_recorded_results`/`labor_recorded_results`. Justified, not by reflex genericization, but by the fact that §40's own field set is already 100% identical in shape and meaning across both domains — `monitor` is the only column that varies, and it is exactly the kind of narrow, justified discriminator column this project already uses elsewhere for genuinely domain-agnostic data (e.g. `ReleaseAnalysisUpdate.component` already spans both Inflation's and Labor's own component vocabularies in one table). This is a different situation from the "no premature generic framework" rule's own usual target (independent *economic logic*, e.g. `labor_release_processing.py` staying separate from `release_processing.py`) — here there is no economic logic to keep separate; the two domains produce byte-identical-shaped facts.

---

## §73. Schema-evolution finding (confirmed: stable, extensible)

If a future monitor (e.g. Growth) needs a structurally different result shape, §72's own generic table remains sufficient as long as the new monitor's own top-level result is still expressible as `(state, evaluation_period, methodology_id, data_basis)` — true of every canonical monitor this project has built so far (Inflation, Labor) and a reasonable expectation for a plausible future one, since every canonical monitor result in this codebase already carries exactly this quartet of fields as part of its own existing contract.

---

## §74. FK delete behavior (frozen: `ondelete="CASCADE"`, matching sibling tables exactly)

`release_check_run_id` cascades from `release_check_runs.id`, mirroring `ReleaseObservationUpdate.release_check_run_id`/`ReleaseAnalysisUpdate.release_check_run_id`'s own already-established `ondelete="CASCADE"` exactly (§80/§81 of the source prompt's own caution against silent cascade-delete is noted, but **no code path anywhere in this repository ever deletes a `ReleaseCheckRun`, `ReleaseOccurrence`, or `EconomicRelease` row** — confirmed, no delete endpoint/CLI/migration-time deletion exists for any of these entities across the whole session's own inspection — so this is a theoretical consistency choice, not a live risk, and diverging from the two closest sibling tables' own already-accepted convention for a merely theoretical concern would be inconsistent without cause).

---

## §75. Uniqueness (frozen, restated from §13/§33)

`UNIQUE(release_check_run_id, monitor, evaluation_period)`.

---

## §76. Nullability / status representation (frozen, restated from §19/§21/§37)

`evaluation_period`, `state` (and every other column in §40) are **all `NOT NULL`** — no field in this schema is ever null. `INSUFFICIENT_DATA` is represented as an ordinary, non-null literal value of `state` (§19/§37), not as a null `state` with a separate nullable status column — the domain's own existing representation is reused exactly, never re-invented at the persistence layer.

---

## §77. Inflation recording path (frozen, exact — restated compactly from §8/§65)

Triggers exactly when `PRIMARY_SERIES_ID` (Core PCE, `PCEPILFE`) changes and is written during `_apply_changes_and_compute_analysis`; records `state`/period from `_evaluate_component_at(observations, "PRIMARY_MOMENTUM", period)`'s own AFTER call, for each period in `affected_pairs` where `component == "PRIMARY_MOMENTUM"`. Never triggered by a Headline CPI-only or Confirmation-only change (§8). `INSUFFICIENT_DATA` recorded per §37.

---

## §78. Labor recording path (frozen, exact — restated compactly from §8/§65)

Triggers exactly when PAYEMS or UNRATE changes; records `after_result.state` from `_evaluate_labor_at`'s own AFTER call, for each period in `labor_periods`, using the loop's own requested period (§21) rather than `after_result.evaluation_period`. `INSUFFICIENT_DATA` recorded per §37, uniformly with Inflation (§37's own decision, no asymmetry).

---

## §79. Cross-period behavior (frozen: moot for this narrow scope, by construction)

Because §65 scopes recording to each domain's own single top-level state (not Confirmation/Headline CPI/Headline PCE, which can genuinely run at different latest periods), the cross-period skew the source prompt's own §87 worries about never arises for what this contract actually records — `PRIMARY_MOMENTUM`'s own period is the only period Inflation ever records, exactly matching `state-duration-v1.md` §24's own identical finding for State Duration's own narrow scope.

---

## §80. Disclosure (frozen language, drafted, not shipped as production copy — mirroring `state-duration-v1.md` §38's own identical non-shipping stance)

> "This is what Economic Intelligence itself calculated and recorded at the time it processed this release — not necessarily what today's latest-revised reconstruction shows, and not a guarantee that the exact underlying data inputs from that moment remain independently reconstructable."

Two distinct claims in one sentence, matching §23's own boundary precisely: (1) recorded ≠ reconstructed (§47), (2) recorded output ≠ a fully vintage-reconstructable input set (§23). Not written into any production file this increment.

---

## §81. Terminology (frozen)

**Preferred:** "recorded by Economic Intelligence," "EI's own recorded history," "Economic Intelligence's calculation history." **Forbidden:** "real-time history" (implies a speed/latency guarantee this system never makes), "as originally reported" (implies provider-vintage fidelity, §23), "point-in-time data" (implies the *inputs*, not just the *output*, are preserved — false, §23).

---

## §82. Worked revision example (frozen, matching real current code semantics — not the source prompt's own illustrative dates, recomputed against this project's real behavior)

On `2026-09-15`, EI processes a curated CPI/PCE release occurrence. `PCEPILFE`'s own August observation is NEW; `_evaluate_component_at("PRIMARY_MOMENTUM", 2026-08-01)` genuinely computes and returns `COOLING`. A row is written: `monitor="inflation", evaluation_period=2026-08-01, state="COOLING", methodology_id="inflation_v1.0", calculated_at=2026-09-15T…Z, release_check_run_id=<run A>`.

On `2026-10-15`, a provider revision changes August's `PCEPILFE` value. EI reprocesses; `_evaluate_component_at("PRIMARY_MOMENTUM", 2026-08-01)` runs again, genuinely, and this time returns `STABLE`. A **second** row is written: `monitor="inflation", evaluation_period=2026-08-01, state="STABLE", methodology_id="inflation_v1.0", calculated_at=2026-10-15T…Z, release_check_run_id=<run B>` — legal under §13's own identity rule (different `release_check_run_id`), never colliding with the first row.

**Both rows persist, unmodified, forever.** A future query for "what did EI record for August 2026" returns both, ordered by `calculated_at` (§58) — honestly showing that EI's own view of August evolved between two real processing events, never silently replacing the first with the second (§12). Today's State Duration reconstruction for August might show a third, different answer again — all three (the two recorded rows, the one reconstructed value) can coexist and disagree, each honestly labeled by its own kind (§47).

---

## §83. Future revision-difference readiness (confirmed: schema-supported, not designed)

§82's own worked example already proves the schema can support a future "recorded vs. current reconstruction" comparison UI — both values are independently queryable by their own honest label (recorded row vs. live State Duration call) — without this document designing that UI.

---

## §84. Future Since Last Visit query readiness (confirmed, restated from §48/§56/§57)

`(monitor, calculated_at)` indexing directly supports "results recorded after timestamp T."

---

## §85. State-change derivation (frozen: derived at read time, never persisted as its own field)

"Which recorded results changed state from the previous recorded result for the same monitor" is derivable by ordering rows (`monitor`, `calculated_at ASC`) and comparing each to its predecessor at read time — no `previous_state`/`transition` column is added to `RecordedMonitorResult` itself, avoiding exactly the kind of derived-field staleness risk this project has repeatedly avoided elsewhere (e.g. `state-duration-v1.md` §26's own explicit "no persistence... would need to paper over expected variability" reasoning, applied here to a different but structurally similar derived fact).

---

## §86. Confirmed-unchanged capability (confirmed: directly answerable, the feature's own core value — restated from §9)

"Was Inflation recalculated but remained COOLING?" — yes, directly, by finding two or more consecutive `(monitor="inflation", evaluation_period=X)` rows with identical `state` and different `calculated_at`/`release_check_run_id`. This is precisely §9's own frozen decision, now confirmed as a genuinely answerable future query, not merely an abstract justification.

---

## §87. Coverage-query capability (confirmed: distinguishable, per §52/§53)

"No calculation" (zero rows for a period) vs. "calculated insufficient" (`state="INSUFFICIENT_DATA"` rows exist) vs. "calculated same state" (§86) are all three distinguishable by row presence and content alone — the three-way distinction the source prompt's own §95 requires.

---

## §88. Storage growth (qualitative, not measured — consistent with this project's own established estimation discipline)

Bounded by the same small, curated release set #25B §49 already estimated (six curated releases, four canonical Inflation series, two canonical Labor series) — at most a handful of new rows per qualifying `process_occurrence` call (Inflation: at most one period per call in ordinary operation; Labor: at most three, under a benchmark-revision propagation, §13). Not prematurely optimized, matching `state-duration-v1.md` §36's own identical "estimated, not measured" framing.

---

## §89. Privacy (confirmed)

No user data of any kind. No auth dependency. Every field in §40 is either an internal id, a public economic classification, or a timestamp — identical privacy posture to every existing release-processing table.

---

## §90. AI boundary (frozen, architecture guard required for #25E)

AI cannot create, update, or delete any `RecordedMonitorResult` row — the write path lives entirely inside `ReleaseProcessingRepository`/`release_processing.py`, neither of which imports any AI/OpenAI/LLM dependency today, and a dedicated guard must confirm this remains true (mirroring `test_maintenance_architecture.py::TestNoAIOrNewsImports`'s own precedent, extended to the new model/repository method). A future increment may let AI *explain* recorded history in prose — it may never write it.

---

## §91. Methodology boundary (frozen)

This increment introduces **zero new economic methodology.** `app/domain/inflation.py`/`labor.py` are unmodified (§60); `RecordedMonitorResult` persists an existing, already-computed classification verbatim — it never classifies, thresholds, or interprets anything itself.

---

## §92. Correction-vs-revision distinction (frozen, three-way)

**Provider revision** (new evidence arrives): the old record remains untouched; a new record is written at the new calculation time (§12/§82) — this is the *normal*, *expected*, *frequent* case. **Methodology revision** (a new version ships): the old record remains untouched, tagged with its own original `methodology_id` (§18) — also normal and expected, just rarer. **Software/data-integrity correction** (a genuine EI bug produced a wrong row): **not** silently rewritten by any normal application flow (§31) — requires out-of-band, operator-performed correction; V1 provides no in-application mechanism for this third case, and this is the one case genuinely different in kind from the other two.

---

## §93. V1 correction limitation (frozen, restated from §31 for completeness of the final-report numbering)

No `invalidated_at`/`superseded_by` mechanism ships. Documented explicitly as a named V1 limitation, not a silent gap.

---

## §94. Conceptual database schema (restated compactly, full detail in §40/§56/§74/§75)

```
CREATE TABLE recorded_monitor_results (
  id                    SERIAL PRIMARY KEY,
  release_check_run_id  INTEGER NOT NULL REFERENCES release_check_runs(id) ON DELETE CASCADE,
  monitor               VARCHAR(16) NOT NULL,
  evaluation_period     DATE NOT NULL,
  state                 VARCHAR(32) NOT NULL,
  methodology_id        VARCHAR(32) NOT NULL,
  data_basis            VARCHAR(32) NOT NULL,
  calculated_at         TIMESTAMPTZ NOT NULL,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (release_check_run_id, monitor, evaluation_period)
);
CREATE INDEX ix_recorded_monitor_results_monitor_calculated_at ON recorded_monitor_results (monitor, calculated_at);
CREATE INDEX ix_recorded_monitor_results_monitor_evaluation_period ON recorded_monitor_results (monitor, evaluation_period);
```

Not implemented this increment — no migration exists, per the explicit instruction.

---

## §95. Proposed #25E service flow (frozen, exact, grounded in real current ordering — not the source prompt's own hypothetical example)

```
process_occurrence(occurrence_id, session, as_of_date):
  1. Look up occurrence, check eligibility                          [unchanged]
  2. Load active mappings                                            [unchanged]
  3. Per-series fetch + classify NEW/REVISED/UNCHANGED               [unchanged]
  4. _apply_changes_and_compute_analysis(repo, observation_changes):
       a. observation_changes empty -> return ([], [])               [NEW 2nd return value: always empty here]
       b. affected_pairs/labor_periods both empty -> write obs, return ([], [])   [NEW: still empty]
       c. capture BEFORE evidence                                     [unchanged]
       d. write observations                                          [unchanged]
       e. capture AFTER evidence (PRIMARY_MOMENTUM + labor)            [unchanged call; THIS is §7's trigger]
       f. NEW: build recordable_results from (e)'s own already-computed
          AFTER values, one per (monitor, period) pair evaluated
       g. diff BEFORE vs AFTER -> analysis_changes                     [unchanged]
       h. return (analysis_changes, recordable_results)                [NEW 2nd return value]
  5. completed_at = now()                                              [unchanged, same call site]
  6. status = _determine_status(...)                                  [unchanged]
  7. check_run = repo.add_check_run(...)                              [UNCHANGED position -- still after analysis]
  8. NEW: for r in recordable_results: repo.add_recorded_monitor_result(check_run.id, r, calculated_at=completed_at)
  9. for record in observation_changes: repo.add_observation_update(...)   [unchanged]
  10. for record in analysis_changes: repo.add_analysis_update(...)    [unchanged]
  11. return ReleaseCheckRunResult(...)                                [unchanged]
```

**One small, shared, cross-domain persistence helper is justified** (mirroring `state-duration-v1.md` §29's own identically-reasoned precedent for its pure sequence-evaluation helper): the logic that turns an already-computed `(monitor, period, state, methodology_id, data_basis)` tuple into a persisted row has zero economic content — it never inspects what `"COOLING"` means — so ONE small function serves both domains, while the *computation* producing that tuple (step 4e) correctly stays domain-specific and dispatched exactly as it is today.

---

## §96. FK-ordering decision (frozen, restated precisely from §25)

No restructuring required. `ReleaseCheckRun`'s own creation point (`release_processing.py:213`) is unchanged; the new write step is inserted immediately after it, exactly where `add_observation_update`/`add_analysis_update` already wait for the same id.

---

## §97. `ReleaseCheckRun` semantics preserved (confirmed, YES)

Zero change to when, how, or why `ReleaseCheckRun` is created, what its `status` means, or its own existing four-value vocabulary.

---

## §98. Alternative provenance finding (frozen: not needed, restated from §26/§29)

`release_occurrence_id`, `maintenance_sweep_id`, and a synthetic `calculation_event` UUID were all evaluated conceptually. **`ReleaseCheckRun` alone is correct and sufficient** — it already exists atomically in the same transaction, already carries a real, flushed id at the exact point this feature needs one, and already works identically for both manual and automated origin (§27). No alternative is adopted.

---

## §99. Exact #25E scope (frozen)

Migration (one new table, per §94); ORM model (`RecordedMonitorResult` in `app/db/models.py`); one new repository method (`add_recorded_monitor_result`, added to `ReleaseProcessingRepository`, §61); service integration inside `release_processing.py` (§95's exact flow, including the one small shared persistence helper); Inflation and Labor recording logic (dispatched from the existing, unmodified `_evaluate_component_at`/`_evaluate_labor_at` call sites, §77/§78); tests (§101); architecture guards (§102); documentation updates (`ENGINEERING_JOURNAL.md`, `current-architecture.md`, `request-flows.md`). **No migration to any existing table.** **No change to `MaintenanceOrchestrator`, `run_maintenance.py`, or any #25C file.**

---

## §100. Read API decision (frozen: NOT included in #25E)

Persistence-only. A future increment (whichever one first genuinely needs to read this data — most plausibly a future Since Last Visit or dedicated history-API increment) designs and builds the read contract, informed by §55's own described-but-undesigned shape. Building the read API now, ahead of a concrete consumer, risks freezing response semantics (pagination shape, filter parameters) before any real product requirement has exercised them.

---

## §101. Frontend decision (frozen: NOT included in #25E)

Expected NO, confirmed: recorded history should begin accumulating before any UX is built on top of it (mirroring #25A §59's own original sequencing logic, now correctly reapplied here) — building UI against zero accumulated rows would have nothing real to show and no way to validate the schema's own usefulness against real data.

---

## §102. Deployment-ordering recommendation (frozen, operational, not enforced by code)

**Recommend #25E's migration and code deploy as soon as practical after this contract freeze** — automation (#25C) is already live as of the current HEAD (`37995db`), meaning the gap named in #25B §37/§42 (unchanged-state recomputations going unrecorded) has been silently accruing since that commit. This is not a new urgency invented by this document — it is #25B's own already-quantified, already-accepted "small and bounded" delay cost (§42 there), now with a concrete start date. No code enforces this ordering; it is a recommendation for the human operator sequencing increments, consistent with every deployment-ordering note in this project's own prior documents.

---

## §103. #25E test matrix (frozen)

Inflation state changed (recorded); Inflation state unchanged after genuine recomputation (recorded, §9); Labor state changed; Labor state unchanged; `INSUFFICIENT_DATA` result (recorded, both domains, §37); `NO_CHANGE` provider check (zero rows, §10); a `NEW` observation triggering recomputation; a `REVISED` observation triggering recomputation; the same evaluation period recorded across two different `release_check_run_id`s (both rows persist, §13); a duplicate identical retry (zero new rows, §32); manual CLI processing (creates identical rows to automated processing, §27); automated sweep processing (identical); provider failure with zero mapped-monitor impact (zero rows); `PARTIAL_FAILURE` where the succeeding series' change still genuinely recomputes (recorded, §36); a genuine database failure mid-transaction (zero rows survive, §35); a simulated crash (zero rows survive, inherits #25C's own crash-safety, no new logic); `methodology_id` correctly captured and preserved; `evaluation_period` correctly equals the requested (not echoed) period, including for an `INSUFFICIENT_DATA` result (§21); `calculated_at` equals the owning `ReleaseCheckRun.completed_at` exactly (§15); immutability (no code path updates or deletes a row); a provider revision does not mutate the prior row (§12); a future-methodology simulation does not mutate a prior row's `methodology_id` (§18); deterministic ordering (`calculated_at DESC, id DESC`); a query by `(monitor, calculated_at range)`; a query by `(monitor, evaluation_period)`; a `GET` monitor-endpoint request creates zero rows (§63, structural); a plain series `/sync` request creates zero rows (§64); a State Duration request creates zero rows (§47/§67); a Relate/salience computation creates zero rows (§66/§68); a Labor benchmark-revision run producing multiple affected periods in one call correctly writes multiple rows, one per period, all sharing one `release_check_run_id` (§13); no frontend file references the new model/repository at all (a structural absence check, since no frontend work exists in #25E).

---

## §104. Architecture guards (frozen, for #25E)

Extending this project's own established, dedicated-guard-test pattern: `app/domain/inflation.py`/`labor.py` unmodified by this increment (a `git diff`-shaped guard, or an equivalent AST check confirming no new call is added inside either domain module); the new repository method never calls `commit()`/`rollback()` (mirrors every existing repository guard); no route module (`app/api/*.py`) imports `add_recorded_monitor_result` or constructs a `ReleaseProcessingRepository` for a write (§63); the State Duration service/domain modules (`app/domain/state_duration.py`, its two service methods) never import the new model or repository method (§47/§67); no AI/OpenAI/LLM import anywhere in the new model/repository/service code (§90); the new persistence step never runs unless `_evaluate_component_at`/`_evaluate_labor_at` was genuinely called in that same code path (a structural, not merely behavioral, guard — confirming the recordable-results list is only ever populated from step 4e's own already-computed values, never independently recomputed a second time); no `UPDATE`/`DELETE` statement targets `recorded_monitor_results` anywhere in the codebase (a grep-level guard, mirroring the append-only discipline already checked for `ReleaseObservationUpdate`/`ReleaseAnalysisUpdate` if such a guard exists, or newly added here as the first of its kind for this specific append-only property).

---

## §105. Explicit deferrals (restated, comprehensive)

Read API (any shape); frontend UI (any shape); Since Last Visit itself (a separate future increment, unlocked but not built here); Watchlist; accounts; notifications; metric/evidence persistence (§41/§42); vintage/ALFRED data (§23); correction/invalidation machinery (§31/§93); automated-vs-manual provenance field (§28/§29); `MaintenanceSweep` linkage (§26); a generic multi-subject history framework beyond Inflation/Labor (§20); percentile/regime/"unusual" language (unrelated, still out of scope per #24A's own standing deferral); AI-generated historical summaries; Growth; Compare.

---

## §106. GO / STOP checklist

| # | Item | Status |
|---|---|---|
| 1 | What a recorded result proves / does not prove | ✅ §5/§23/§43 |
| 2 | What execution creates one | ✅ §6/§7 |
| 3 | Unchanged-state decision | ✅ §9 |
| 4 | Unchanged-data decision | ✅ §10, traced to exact code |
| 5 | Retry semantics | ✅ §11/§32 |
| 6 | Insufficient-data semantics | ✅ §37/§38 |
| 7 | Identity/uniqueness | ✅ §13/§33/§75 |
| 8 | Methodology provenance | ✅ §17/§18 |
| 9 | Evaluation-period provenance | ✅ §21 |
| 10 | Calculation-time semantics | ✅ §15/§16 |
| 11 | Data-basis truth boundary | ✅ §22/§23 |
| 12 | Source-event provenance | ✅ §24/§25/§26 |
| 13 | Manual/automatic behavior | ✅ §27/§28/§29 |
| 14 | Immutability | ✅ §30 |
| 15 | Correction limitation | ✅ §31/§93 |
| 16 | Revision behavior | ✅ §12/§82 |
| 17 | Repeated same-period behavior | ✅ §13 |
| 18 | Minimal fields | ✅ §40 |
| 19 | Metric/evidence persistence | ✅ §41/§42/§44 |
| 20 | Transaction location | ✅ §59/§62 |
| 21 | FK/provenance architecture | ✅ §25/§96/§97/§98 |
| 22 | Query/index requirements | ✅ §56-§58 |
| 23 | No-backfill semantics | ✅ §51 |
| 24 | Exact #25E scope | ✅ §99 |
| 25 | Deployment order | ✅ §102 |
| 26 | Tests | ✅ §103 |
| 27 | Guards | ✅ §104 |
| 28 | Domain model name / schema | ✅ §39/§94 |

All twenty-eight resolved. No item required a database read, a secret value, or a decision this document deferred to guesswork — every non-obvious choice above is either grounded in a directly re-inspected code fact (§4, §25, §26, §36) or an explicit, reasoned tradeoff (§41-44, §65, §72).

---

## Appendix: secret safety and version control

No `.env`/`.env.*`/credential file was read, printed, or logged at any point this increment. The backend/frontend test runs used the project's established local isolated-Postgres mechanism (trust-auth, no password) and the standard `npm test` runner. No production code, migration, model, repository, service, route, or frontend file was created or modified this increment — only this new document. Nothing was committed or pushed; the working tree outside this new file was not modified.
