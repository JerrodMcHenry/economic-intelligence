# Automated Economic Maintenance — Operational Design & Contract Freeze — V1

**Increment #25B.** Operational design / contract freeze only. No production code changed. Baseline: HEAD `0024e19` ("Add State Duration V1 backend #24C"), clean working tree except the untracked #25A artifact. Frontend: 1,032/1,032 passed. Backend: 1,256/1,256 passed, 0 skipped, against the project's established local isolated-Postgres test mechanism.

This document is the authoritative contract for #25C. It freezes *how* release processing runs without a human invoking the CLI by hand — never changes *what* release processing means. Every finding below is grounded in direct inspection of the current implementation this turn, not assumption.

---

## §1. Core principle, restated as an operational constraint

**Automation may trigger deterministic work. Automation may not change the meaning of that work.** Every conclusion below either reuses `ReleaseProcessingService.process_occurrence` and its existing status/outcome model completely unmodified, or explicitly names the one new discovery query required to find *which* occurrence to call it on. No economic logic, no classification rule, and no new response field changes as a result of this document.

---

## §2. Current pipeline — exact execution flow (inspected fresh, in full, this turn)

`app/services/release_processing.py`'s `ReleaseProcessingService.process_occurrence(occurrence_id, session, as_of_date)`:

1. Look up the `ReleaseOccurrence` by id; raise `OccurrenceNotFoundError` if absent, `OccurrenceNotEligibleError` if `scheduled_date > as_of_date`.
2. Load that occurrence's active `ReleaseSeriesMapping` rows (`ReleaseProcessingRepository.get_active_mappings`).
3. For each mapped series: fetch from FRED over a bounded five-year window (`five_year_observation_start`), classify every returned observation `NEW`/`REVISED`/`UNCHANGED` against currently-persisted values (`classify_observation_change`), catching `FREDError`/malformed-payload errors *per series* (never raised out of the loop).
4. Compute the affected `(component, period)` pairs (Inflation) and affected periods (Labor) the changed observations touch, using the existing, unmodified `affected_evaluation_periods`/`labor_affected_evaluation_periods`.
5. Capture BEFORE evidence via the existing `_at`-suffixed domain functions, write every changed observation (`write_observation`, flush-immediate), capture AFTER evidence the same way, diff via the existing, unmodified `inflation_what_changed`/`labor_what_changed` comparators.
6. Determine one overall `CheckRunStatus` (`_determine_status`, §7 below) and persist exactly one `ReleaseCheckRun` row plus zero-or-more `ReleaseObservationUpdate`/`ReleaseAnalysisUpdate` rows, all inside the caller's own transaction.
7. Return a structured `ReleaseCheckRunResult`.

**All of §2 happens inside exactly one caller-owned `session_scope()` block** (confirmed directly, `app/db/session.py`: one commit on success, one rollback on any exception, `finally: session.close()`). This single fact governs the crash-recovery and transaction findings below (§20/§21) and must not change.

---

## §3. Current manual entry point (frozen, exact)

```
python -m app.operations.process_release --occurrence-id <id> [--as-of-date YYYY-MM-DD]
```

- `--occurrence-id` is **required** — there is no bulk or "find work" mode today.
- `--as-of-date` defaults to `datetime.now(timezone.utc).date()` if omitted — **UTC is already the project's own established operational timezone** (confirmed directly; see §16).
- It processes exactly one occurrence, never discovers what should be processed.
- `PAST_DUE` eligibility is enforced by the service (`scheduled_date <= as_of_date`), not the CLI.
- If nothing changed: `NO_CHANGE`, exit code `0` — a genuine success, not an error.
- If a provider call fails (for one or all mapped series): `PARTIAL_FAILURE`/`FAILED_PROVIDER`, exit code `1`.
- If a real database error occurs: the exception propagates to `main()`, the transaction rolls back, and — critically — **no `ReleaseCheckRun` row is ever written for that attempt** (see §23).

---

## §4. Automation unit (frozen: individual release occurrence)

**Option A — individual release occurrence.** This is the unit `process_occurrence` already operates on, unmodified. Rejected alternatives: **B (release ID)** — too coarse; a release has many occurrences over time, and eligibility/status is inherently per-occurrence. **D (per-series sync)** — a different, already-existing, separate concern (`SeriesRepository`'s own plain `/sync` path) with no release-processing audit trail; conflating the two was explicitly rejected at the architecture level in #18/#20D.2 (release processing owns its own independent write path precisely so the plain sync path's behavior is never touched). **E (monitor refresh)** — does not exist as its own operation; monitors are always computed live from persisted data, never cached or explicitly "refreshed." **C (a periodic "find due work" sweep)** is not an alternative to A — it is the *discovery* mechanism that decides which individual occurrences (A) to process. Frozen: **the orchestrator discovers due occurrences (C) and processes each one individually via the unmodified per-occurrence unit (A).**

---

## §5. Push vs. poll (frozen: hybrid, release-aware polling)

**No web research was required or performed** — this is conclusively answered by direct repository evidence. `app/clients/fred.py`'s entire method surface (`get_series_info`, `get_observations`, `search_series`, `get_release_dates`) is exclusively request/response — no webhook registration, no subscription, no push capability exists anywhere in this codebase's provider integration, and none is assumed. **FRED cannot push a completion event into this application.** Frozen: **Option C — scheduled, release-aware polling.** Not naive fixed-interval polling of everything (wasteful, and provides no signal about *which* occurrences are actually due); not attempted real-time/sub-hour polling (economic releases are not a real-time system — see §15). The orchestrator's own due-work query (§8) is what makes this "release-aware" rather than blind: a uniform sweep cadence, filtered by a smart due-work query, naturally concentrates provider calls around occurrences that are actually `PAST_DUE` and unsettled, without needing a separate per-release cron schedule.

---

## §6. Date-only release catalog — consequences (audited, not invented)

Confirmed directly, `app/db/models.py`'s `ReleaseOccurrence` docstring: **deliberately no time-of-day, timezone, cancellation, or status column** — "FRED's release-dates data cannot reliably source any of those... inventing one would violate this project's 'missing precision stays explicit, never fabricated' invariant." **Consequence for automation, frozen:** EI cannot know a release's true publication *time*, only its scheduled *date*. Safe strategy: **check periodically, starting on the scheduled date, until the occurrence settles (§10) or its retry window is exhausted (§14) — never assume or infer a specific publication time.** This is a direct, unmodified extension of a decision this project already made once (release-intelligence-v1.md #3) applied to a new consumer (automation) of the same, already-correct data shape.

---

## §7. `SCHEDULED`/`PAST_DUE` semantics (frozen, precisely)

`app/domain/releases.py`'s `classify_schedule_status`, inspected fresh: `scheduled_date >= as_of_date → SCHEDULED`, else `PAST_DUE`. **`PAST_DUE` means, exactly and only, "the scheduled date has passed" — it does NOT mean "the provider now contains new data."** This is the exact same boundary `OccurrenceNotEligibleError` already enforces at the service layer (`scheduled_date <= as_of_date` is eligible, the complement of `SCHEDULED`). Frozen: **automation may safely use `PAST_DUE` (or, equivalently, the service's own existing eligibility check) as "may now be checked," never as "is now confirmed updated."** Conflating the two would be exactly the over-claim §9/§10/§27 all warn against.

---

## §8. Due-work discovery — conceptual rules (frozen; query described, not implemented)

An occurrence is **due for a check** when, conceptually:

1. It has at least one active `ReleaseSeriesMapping` (an unmapped occurrence has nothing for release processing to check at all — this is already implicitly true of every occurrence the manual CLI is ever pointed at).
2. `scheduled_date <= as_of_date` (eligible, per §7 — the existing `OccurrenceNotEligibleError` boundary, unmodified).
3. It has **not yet reached settlement** (§10) — either no `ReleaseCheckRun` exists for it at all, or its latest run's status warrants another look within the frozen retry window (§14).

**No such query exists today** (confirmed: `ReleaseRepository`/`ReleaseProcessingRepository` have `get_occurrence_by_id`/`list_occurrences`/`list_check_runs_for_occurrence` — nothing joins occurrences against their own latest check run to filter for "not yet settled"). This is the one genuinely new read query #25C must add — a straightforward `LEFT JOIN` extension of existing query patterns (mirroring the already-established "latest run per occurrence" tie-break convention, `completed_at DESC, id DESC`, already used by `release_processing_read_repository.py`), **not new domain logic.**

---

## §9. `NO_CHANGE` vs. completion (frozen distinction — critical)

`_determine_status` (`app/services/release_processing.py`, inspected fresh): `NO_CHANGE` fires when every mapped series' provider fetch **succeeded** and zero observations were classified `NEW`/`REVISED`. **`NO_CHANGE` is a real, successful, complete CHECK — it proves EI successfully asked every mapped series for its latest data and got nothing new back at that moment.** It does **not** prove the release's true new data has been published yet (§6/§7 — the pipeline has no concept of "the value FRED will eventually publish for this period," only what FRED returns *right now*). Frozen terminology: **CHECK SUCCEEDED** (a real, provable, per-run fact) is distinct from **RELEASE SETTLED** (§10 — a provisional, conservative inference, never a certainty) — the two must never be presented as the same thing in any future UI or freshness claim.

---

## §10. Release settlement (frozen, conservatively — no invented completeness)

**What can be proven, precisely:** that a given run queried *every currently-active mapped series* for the occurrence's release and received a definitive answer (succeeded-with-or-without-a-change, or failed) for each. **What cannot be proven, and must never be invented:** whether the "expected" observation for this occurrence's own period has actually arrived — the pipeline has no concept of an occurrence's own expected calendar period (confirmed, §6) to check that against. Frozen settlement rule, deliberately conservative:

> **An occurrence is provisionally settled when it has at least one `ReleaseCheckRun` whose status is `NO_CHANGE` or `CHANGED` (never `PARTIAL_FAILURE`/`FAILED_PROVIDER`) in which every currently-active mapped series was successfully queried.**

This does **not** claim "the true new data has landed" — only "EI successfully checked everything it knows to check, at least once, since this occurrence became eligible." Automation should stop *routine* re-checking of a settled occurrence but — per the same conservative discipline — should still re-check it a small, bounded number of additional times within the retry window (§14), since a genuinely late-arriving revision immediately after an apparent `NO_CHANGE` settlement is a real, known pattern this project's own domain layer already anticipates (revisions arrive after initial publication as a matter of course). **Do not invent a stronger completeness claim than this.**

---

## §11. Multi-series releases (frozen behavior, re-confirmed against code)

Employment Situation → PAYEMS + UNRATE, checked in one shared per-occurrence run (`process_occurrence` loops over ALL of that occurrence's mappings in one call — confirmed, §2 step 3). **If PAYEMS updates before UNRATE does** (a real, plausible provider-side skew), a single run legitimately reports `CHANGED` (PAYEMS's own change) while UNRATE independently reports `UNCHANGED` in the *same* run — this is not an error and requires no special casing: `NO_CHANGE`/`UNCHANGED` at the per-series level is a completely ordinary, expected outcome, not a failure. **`PARTIAL_CHECK`'s existing meaning (`PARTIAL_FAILURE` at the write layer) is about fetch success/failure, never about "not every series had new data yet"** — confirmed precisely: `_determine_status` sets `PARTIAL_FAILURE` only when `any_provider_failure and any_provider_success` (at least one series' *fetch itself* failed while another succeeded) — a series that fetched successfully and simply had no new data does not contribute to this condition at all. **Must automation retry if one series lags another?** Yes, naturally, via the ordinary due-work/settlement mechanism (§8/§10) — since the run in that scenario is `CHANGED` (not yet fully settled per §10's own multi-series-aware wording "every currently-active mapped series was successfully queried" — which UNRATE was, just with no change), the occurrence is technically settled by §10's own conservative rule the moment all mapped series are successfully queried in one run, **even if only one of them changed.** This is intentional: settlement is about "did we successfully ask everyone," not "did everyone answer with a change" — UNRATE answering "no change" is still a complete, successful answer.

---

## §12. `PARTIAL_FAILURE` — exact meaning, retry implications

Re-confirmed: `PARTIAL_FAILURE` = at least one mapped series' *provider fetch* failed while at least one other succeeded, **in the same run**. **Can it drive retries?** Yes — it is, by definition, an incomplete check (§10's settlement rule explicitly excludes it). **Could a run be technically successful but operationally incomplete?** Only in the sense that individual series-level fetch failures are always caught and recorded per-series (never crash the whole run) — the run as a *database transaction* always either fully commits or fully rolls back (§21); "partial" here describes provider-fetch coverage, never a partially-committed database state, which cannot occur by construction.

---

## §13. `FAILED_PROVIDER` — exact meaning

Every mapped series' fetch failed. Distinguish the underlying cause, per `_safe_error_message`'s own existing branching (`app/services/release_processing.py`): `FREDTimeoutError`/`FREDUpstreamError` (transient, provider-side — **retryable**, ordinary sweep cadence is the retry); `FREDAuthError` (a rejected API key — **not retryable by waiting**; retrying will not help, and this should escalate to operator attention faster than an ordinary transient failure, §63). A genuine `OperationalError`/`SQLAlchemyError` (database-layer) is a *different* category entirely — see §23, it never even reaches a persisted `CheckRunStatus` at all.

---

## §14. Retry policy — principles frozen, numbers left tunable (per instruction)

- **Same-day retry:** permitted, bounded by ordinary sweep cadence (§15) — no special same-day-specific logic needed; the due-work query (§8) already re-surfaces an unsettled occurrence at the next sweep regardless of how many hours have elapsed.
- **Cross-day retry:** permitted, for a **configurable maximum number of days past `scheduled_date`** — recommended default on the order of "about a business week," explicitly **not empirically measured, and explicitly a tunable operational parameter**, not a frozen economic fact.
- **Maximum attempts / maximum age:** frozen as a *principle* (retries must stop eventually, to bound both provider load and stale-occurrence noise) with the exact number left to operator configuration, per the explicit instruction not to pretend empirical certainty here.
- **Backoff:** **not** classic exponential backoff — this is not a high-frequency-retry scenario. The sweep's own cadence (§15) *is* the backoff, by construction: a modest, uniform sweep interval naturally spaces retries without any additional logic.
- **Retry exhaustion:** an occurrence that reaches its maximum retry age without settling (§10) is marked, conceptually, **retry-exhausted** — operator-visible (§31/§63), never silently dropped from consideration, never silently reported as settled.

---

## §15. Automation cadence (frozen: hourly-order sweep, release-aware filtering does the real work)

Economic releases are monthly-or-slower; nothing here is a real-time system, and forcing sub-hour polling would optimize for a cadence the underlying data cannot support. Frozen: **a uniform sweep interval on the order of hourly-to-a-few-times-daily**, left as an operator-tunable parameter, not empirically derived here (mirroring §14's own discipline). The *actual* freshness responsiveness comes from the due-work query (§8) correctly filtering to only `PAST_DUE`, unsettled, mapped occurrences — a SCHEDULED occurrence is never polled at all before its date, and a settled occurrence stops being surfaced (§10) — so a coarse, cheap sweep interval is sufficient without wasting provider calls on irrelevant checks. **No fake real-time behavior is recommended or implied.**

---

## §16. Timezone (frozen: UTC, already established — no new decision required)

Confirmed directly: `process_release.py`'s own default (`datetime.now(timezone.utc).date()`), and `ReleaseCheckRun`'s own `DateTime(timezone=True)` columns, already establish UTC as this project's operational timezone. **Frozen: automation's own "today"/`as_of_date` and every retry-window calculation use UTC uniformly, exactly matching existing code — no server-local timezone dependency is introduced anywhere, and none should be.** This is a continuity finding, not a new decision.

---

## §17. Idempotency (frozen finding, re-confirmed against code)

**Data writes are idempotent by construction:** an `UNCHANGED` classification is never passed to `write_observation` at all (confirmed, §2 step 3/§9) — repeating a check against genuinely unchanged provider data writes nothing. **`ReleaseCheckRun` rows are deliberately NOT deduplicated:** re-checking an occurrence, even with identical results, always creates a new row (confirmed, `app/db/models.py`'s own docstring: "Retrying an occurrence is expected to create a new row — 'a check occurred' is itself a real, repeatable operational fact"). **This is correct, existing, frozen behavior — automation must not attempt to suppress it.** `ReleaseObservationUpdate`/`ReleaseAnalysisUpdate` rows, by contrast, are only ever written when an actual difference is detected *in that specific run* — under normal (non-concurrent) operation, repeating a check against unchanged data produces zero new rows of either kind, correctly. **This safety property depends entirely on runs not overlapping in time against the same occurrence** — see §18.

---

## §18. Concurrency risk (audited, real, unresolved without §19)

**If two workers (or an automated sweep and a manual CLI invocation) process the same occurrence concurrently, real corruption is possible.** Traced precisely: both transactions would, under ordinary `READ COMMITTED` isolation, each read the *same* pre-change "before" observation state (since neither has committed yet), each independently detect the *same* real-world `NEW`/`REVISED` changes, each write (harmless for the final *value*, since both write the same fetched number), but **each would also independently create its own `ReleaseCheckRun` row plus its own `ReleaseObservationUpdate`/`ReleaseAnalysisUpdate` rows for what is, in reality, one single economic event.** This is genuine **audit-data duplication** — not a data-correctness bug (the final observation values remain correct), but a real corruption of the *event log* any future consumer (Since Last Visit, future Recorded State History) would rely on to count or list distinct changes. **Concurrency protection is required before automation runs with any realistic possibility of overlap** — and overlap is realistic even with a single scheduled worker, via two ordinary paths: (a) a run taking longer than the sweep interval, causing the next sweep to start while the prior one is still active; (b) a manual operator CLI invocation coinciding with an automated sweep (explicitly a scenario this project must keep safe, §59).

---

## §19. Locking / claiming (frozen: Postgres advisory lock, keyed by occurrence id)

Evaluated conceptually, not implemented: a **database advisory lock** (`pg_try_advisory_lock`, keyed by `occurrence_id`), held for the duration of `process_occurrence` and released on completion (success or failure), is the smallest robust model. **Why this over the alternatives:** requires **zero schema change** (advisory locks are session-scoped Postgres primitives, not table rows — no migration needed for the locking mechanism itself); directly available via the existing SQLAlchemy/psycopg stack already in `pyproject.toml`; naturally covers both realistic overlap scenarios in §18 (two automated sweeps, or an automated sweep racing a manual CLI run) without requiring either caller to know about the other in advance. **Row-level claiming** (a `claimed_by`/`claimed_at` column) is evaluated and explicitly **not** recommended for V1 — it would require a migration and only becomes valuable once multiple concurrent WORKERS (plural, distributed) need observability into "who is working on what," which is not this project's actual deployment shape (§44) and should not be built ahead of that need. **Frozen: do not rely on "we only plan to run one worker" as a substitute for locking** — per the instruction, and per §18's own realistic overlap scenarios, this would be an unsafe assumption even in a nominally single-worker design.

---

## §20. Crash recovery (frozen finding — a genuine, strong, pre-existing property)

Traced precisely against `session_scope`'s own implementation (§2/§21): every occurrence's processing happens inside exactly one transaction, committed exactly once at the very end, rolled back on any exception, and — critically — **if the process is killed outright (SIGKILL, OOM, power loss) before that commit, PostgreSQL itself discards the entire in-flight, never-committed transaction automatically.** There is no intermediate durable state possible at any point inside `process_occurrence` — not after `ReleaseCheckRun` creation-in-memory, not after an observation write-in-memory, not after analysis computation. **A crash at any point during one occurrence's processing leaves zero durable trace; the next attempt starts completely clean, with no special recovery logic required.** This is a strong, already-correct property automation must *preserve*, not solve — the one design constraint it implies is that **the orchestrator must give each occurrence its own `session_scope()` (§2's existing shape), never batch multiple occurrences into one shared transaction**, which would break this exact guarantee for every occurrence bundled into that shared transaction.

---

## §21. Transaction semantics (frozen finding, no change required)

Inspected fully (§2/§20): one `session_scope()` per occurrence; `write_observation` flushes immediately within that transaction (an intentional, already-shipped #20D.2 fix, unrelated to automation); `add_check_run`/`add_observation_update`/`add_analysis_update` all occur inside the same transaction, committed together or not at all. **No transaction-boundary change is required for automation** — the orchestrator's own responsibility is purely to call `process_occurrence` once per due occurrence, each inside its own `session_scope()`, exactly as the manual CLI already does per invocation.

---

## §22. Provider failure — required behavior (frozen, re-confirmed)

**Automation must never let a provider outage present as `NO_CHANGE`.** Confirmed already correctly enforced: a `FREDError` during fetch is caught and recorded as `succeeded=False` on that series' own `SeriesCheckOutcome` (never silently treated as "no observations returned" — the two code paths are structurally distinct: an empty *successful* response short-circuits to a genuine, `succeeded=True`, zero-change outcome; a *failed* fetch always produces `succeeded=False`). `_determine_status` then correctly surfaces this as `PARTIAL_FAILURE`/`FAILED_PROVIDER`, never `NO_CHANGE`. **No change required — freezing this as a requirement the orchestrator must not accidentally violate** (e.g., a naive "catch everything and log NO_CHANGE" wrapper around the existing service would violate this; the orchestrator must let `PARTIAL_FAILURE`/`FAILED_PROVIDER` propagate as their own distinct outcomes).

---

## §23. Database failure — required behavior (frozen, with a real gap named)

**If the provider fetch succeeds but persistence subsequently fails** (a genuine `OperationalError`/`SQLAlchemyError` mid-transaction): the whole transaction rolls back (§20/§21) — the fetched provider result is *not* durably lost in the sense of corrupting data, because nothing was ever committed, and a retry will simply re-fetch cleanly. **However: no `ReleaseCheckRun` row exists for that failed attempt at all** (confirmed: the exception is caught in `process_release.py`'s `main()`, entirely outside the service/transaction — nothing about the attempt is ever persisted). **This is a real, named gap for automation specifically** (not for the manual CLI, whose operator sees the failure printed to `stderr` directly): a database failure during an automated sweep is invisible to any *database* query — the only place it can ever be observed is the orchestrator's own external logging, or a separate sweep-record mechanism (§53). **Frozen requirement: the orchestrator must independently, durably log (outside the per-occurrence transaction) that an attempt was made and failed at the database layer**, since the database itself cannot be relied on to prove this happened.

---

## §24. Analysis failure — required behavior (frozen finding: structurally cannot occur independently today)

Traced precisely: `_apply_changes_and_compute_analysis` runs entirely inside the *same* transaction as the observation writes it depends on — there is no separate commit boundary between "observations written" and "analysis computed" (§21). **If analysis computation were to raise for any reason (a genuine defect — today's domain functions are pure and exception-free by design, so this is a theoretical category, not an observed one), the entire transaction — including the observation writes that had already happened in-memory — rolls back together.** Concretely: **"data fresh but intelligence stale" cannot occur for a single occurrence's own processing under the current transaction design** — it is all-or-nothing per occurrence, which is a stronger, cleaner guarantee than the prompt's own hypothetical concern anticipated. **Named explicitly as a positive finding, not a gap to fill:** automation inherits this guarantee for free, provided §20's one-transaction-per-occurrence constraint is preserved.

---

## §25. Data freshness vs. intelligence freshness (frozen definitions)

- **DATA FRESHNESS:** provider observations have been checked as of a specific time — proxied by the most recent `ReleaseCheckRun.completed_at` for a mapped occurrence whose status was `NO_CHANGE` or `CHANGED` (i.e., a genuinely successful check, never a `PARTIAL_FAILURE`/`FAILED_PROVIDER`).
- **INTELLIGENCE FRESHNESS:** whether the canonical monitor analysis reflects those observations. **For the LIVE monitor endpoints (`GET /monitors/inflation`/`/labor`), this is trivially always true** — every canonical result is computed fresh, on every request, from whatever is currently persisted (confirmed, unchanged architectural fact across every prior increment this session). **For the release-processing AUDIT TRAIL specifically**, intelligence freshness is bundled into the same all-or-nothing transaction as data freshness (§24) — so, given §20/§24's own findings, **the two concepts collapse into one provable fact for this pipeline's own purposes: "was this occurrence's most recent check both fetched successfully and (if applicable) analyzed successfully" — a single boolean, not two independently-failing ones.** Recorded here as a genuine simplification the architecture already provides, not assumed away.

---

## §26. Freshness model — semantics determined, fields not yet frozen (per instruction)

Semantics established above; exact field names/shapes are explicitly **not frozen here** (per the instruction to determine semantics before fields) and are left to #25C's own implementation-level design, informed by:

- A **"last checked" fact** (§25's DATA FRESHNESS) is the one genuinely new, safe, useful signal this increment's evidence supports.
- A separate **"last analysis success" fact is not needed** as an independent field — §24/§25 show it is redundant with "last checked successfully" under the current transaction design; freezing it as a *distinct* field would imply a distinction the architecture does not actually have, an honesty risk in its own right.
- **`next_scheduled_release`** requires no new field at the data layer — it is already derivable from existing `ReleaseOccurrence`/`classify_schedule_status` data via the existing read model.
- **`maintenance_status`** (a rollup like FRESH/STALE/UNKNOWN) is a *derived* concept, computed from the above at read time — never itself a stored, potentially-stale field.

---

## §27. "Up to date" — truth boundary (frozen: extremely conservative)

**Frozen: EI may never claim "up to date" unconditionally, in #25C or after.** Per §10's own conservative settlement rule, "every mapped occurrence has been successfully checked" is provable; "the economy's true current data is fully reflected" is not, because the pipeline has no concept of a release's own expected period to verify completeness against (§6/§10). **The only claim #25C should ever expose is a neutral factual timestamp — "last checked: {time}" — never an evaluative claim like "up to date" or "current."** This sidesteps the over-claim risk entirely by never attempting the stronger claim.

---

## §28. Stale — semantics (frozen, conservative, provable)

An occurrence (or, by extension, a monitor domain) may be flagged **STALE** when any of the following, all directly provable from existing/soon-to-exist data, hold: a mapped, `PAST_DUE` occurrence has **no** successful (`NO_CHANGE`/`CHANGED`) `ReleaseCheckRun` at all; its most recent run was `PARTIAL_FAILURE`/`FAILED_PROVIDER`; it is within its retry window but has not yet settled (§10); or **the automation sweep itself has not run within its own expected interval** (§30 — worker silence, a different failure mode than any individual occurrence's own status).

---

## §29. Unknown — a genuine third state (frozen: required)

**Frozen: a genuine `UNKNOWN` freshness state is required**, distinct from both FRESH and STALE, for: occurrences that predate automation's own deployment (§51 — no way to know whether or when a human last checked them); any period where the sweep-record mechanism itself (§53) is unavailable or not yet deployed. **`UNKNOWN` must never be silently defaulted to either FRESH or STALE** — collapsing it into either would be exactly the kind of dishonest freshness claim §27 forbids.

---

## §30. Automation health vs. economic freshness (frozen: two separate concepts, never conflated)

- **WORKER HEALTH:** did the scheduled sweep actually run and complete without an unhandled orchestrator-level error. **A sweep that finds zero due work and does nothing is healthy** — "no work" is a success outcome, not a failure or a no-op to be suspicious of.
- **ECONOMIC/DOMAIN FRESHNESS:** whether a *specific* mapped occurrence is checked/settled (§28). **A perfectly healthy sweep can coexist with a specific occurrence stuck in `PARTIAL_FAILURE` across several sweeps**, needing operator attention (§63) — this must never be summarized away into one combined "everything is fine" status.

---

## §31. Operator visibility (frozen: minimum, no monitoring infrastructure built)

Minimum observability #25C must provide, all achievable with existing patterns: **structured logs** from the orchestrator (start/finish, due-count, processed-count, failure-count per sweep — mirroring `_print_summary`'s own existing, already-safe, non-leaking output shape); **database-queryable status** via the existing `ReleaseCheckRun`/`ReleaseProcessingReadService` machinery, unmodified; a **CLI health/inspection command** (a thin, read-only extension of the existing operational-CLI pattern, not a new subsystem) is a reasonable, small addition for #25C to consider, **not** a new admin UI or external monitoring integration — both are explicitly out of scope (§72).

---

## §32. User visibility (frozen: smallest truthful signal, no UI built)

Per §27's own conservative boundary, the smallest truthful user-facing signal worth exposing, ahead of Since Last Visit (#25D/E), is: **a single "last checked: {time}" fact**, per domain or globally — nothing evaluative, nothing implying completeness. This is deliberately the *same* signal §19 of the #25A audit already identified as necessary for Since Last Visit's own honesty — one mechanism serves both purposes. **No UI is implemented this increment** — this is a semantic/data requirement freeze for #25D/E to consume, not a #25C or #25B deliverable.

---

## §33. Since Last Visit dependency (frozen: the narrower, honest promise)

**What automation must guarantee before Since Last Visit can honestly say "changes detected since you last checked":** that "last checked" (§26/§32) reflects a genuinely recent, reliable cadence — not that every economic event in the world has been captured. **It does NOT need to guarantee "every event in the economy"** — per #25A §19's own already-frozen truth boundary, re-confirmed here: the promise is scoped to *EI's own detected changes*, always paired with the freshness fact, never overclaimed as economic completeness.

---

## §34. Existing event-stream capability, and what remains missing

`ReleaseCheckRun` (append-only, has run timestamps), `ReleaseObservationUpdate`/`ReleaseAnalysisUpdate` (append-only, real before/after evidence) are all real, usable event sources today (§21 of the source #25A audit, re-confirmed by fresh inspection this turn). **Does automated execution alone make these sufficiently complete going forward?** For "was a check attempted and did it succeed" — yes, once automation runs reliably. **For "did the canonical state actually change, including the common case where it was recomputed and confirmed unchanged" — no** (§37 below) — that specific gap survives automation unchanged, because it is a *recording* gap (what gets written), not a *cadence* gap (how often checks happen).

---

## §35. Recorded-state-history question — evaluated rigorously, not deferred by reflex

**Reasons to bundle minimal snapshot persistence into #25C:** every day without it is a day of genuinely non-reconstructable history lost (#24A §35, re-confirmed §20 of the #25A audit); automation's own AFTER-evidence computation (§2 step 5) already computes exactly the canonical result a snapshot write would need, at effectively zero marginal compute cost.

**Reasons against:** this increment is explicitly scoped to OPERATIONAL DESIGN — the frozen instruction at the top of this document's own source prompt is "DO NOT create database migrations. DO NOT create persistence"; snapshot semantics have never been frozen anywhere in this project (#24A §14 only *described* them, explicitly not as schema; #25A explicitly deferred them to a later, dedicated increment); this project's own four-times-proven discipline (#22A→B, #23A→B→C, #24A→B→C→D) is to freeze persistence-shaped decisions in their *own* dedicated contract turn, never fold them into an already-large adjacent increment; and — the decisive point — **the marginal benefit of bundling it into #25C rather than a follow-up #25-series increment is small and bounded** (on the order of one increment-cycle's worth of additional missed moments, not months), because reliability itself only accrues gradually regardless of when the schema ships.

**Decision, frozen: OPTION A — #25C is automation only.** Snapshot/recorded-state persistence is deliberately deferred to its own future, dedicated contract-freeze increment, sequenced *after* #25C so automation has a reliable cadence to record *against*. This is not scope-minimization by reflex — both sides were argued, and the delay-cost side, while real, is explicitly small and stated as such (§47 restated below), not hand-waved.

---

## §36. What `ReleaseAnalysisUpdate` actually preserves (re-confirmed against code, this turn)

Exact fields, from `ReleaseProcessingRepository.add_analysis_update`: `component`, `event_type`, `field`, `previous_value`/`current_value` (stringified), `delta`, `evaluation_period`, `methodology_id`, `data_basis` — tied to a `release_check_run_id`. **It preserves before/after evidence for the specific field that changed, with exact values, methodology, and period. It does not preserve a full monitor snapshot, and it is written only when `compare_*_section` actually detects a difference** (§37).

---

## §37. The unchanged-state problem (re-confirmed directly against the exact code path this turn)

Traced precisely: `_apply_changes_and_compute_analysis` only appends to `analysis_changes` when `_diff_component_at`/`_diff_labor_at`'s underlying `compare_*_section` calls produce a non-empty `.changes` list. **If a mapped observation changes (triggering a `CHANGED`-status `ReleaseCheckRun`, possibly `ReleaseObservationUpdate` rows) but the recomputed canonical state is unchanged (e.g., still `COOLING`), zero `ReleaseAnalysisUpdate` rows are written.** Confirmed: **there is no durable row anywhere proving "EI recomputed and confirmed COOLING at time S"** for this — the common — case. This directly re-confirms #24A §5/§12(B)'s own finding, now pinned to the exact code path. **This gap survives automation unchanged** (§34) — automation improves how *often* checks happen, not *what gets recorded* when a check confirms no change. This is the single strongest piece of evidence for why recorded-state persistence remains valuable, and why it is nonetheless correctly sequenced after (§35), not instead of, automation: automation is what makes future snapshot-writing *worth doing regularly* in the first place.

---

## §38. Minimum recorded snapshot semantics (described only, per §35's own decision — not designed, not scheduled)

If and when a future increment builds this, the smallest useful object (restating #24A §14, re-confirmed sound, not re-litigated here beyond restatement): identity = `(monitor, evaluation_period, methodology_id)`; payload = canonical state plus a `calculated_at` timestamp distinct from the economic `evaluation_period` it describes, plus `data_basis`. **Not designed further here** — that is explicitly the future increment's own job (§35).

---

## §39. Snapshot frequency (evaluated, not decided — deferred with §35)

Evaluated conceptually only, per the same deferral: "only on state change" would under-capture the exact unchanged-state problem §37 names (the whole point of a snapshot is to prove "confirmed unchanged," which a change-only trigger cannot do); "every automation run" would preserve the asset most completely but at the cost of write volume; "only when the relevant release is processed" is the natural middle ground. **This tradeoff is real and is exactly the kind of decision that belongs in the future snapshot-specific contract freeze (§35), not this one.**

---

## §40. Snapshot duplication (evaluated, not decided — deferred with §35)

Repeatedly retrying an occurrence with unchanged data would, under an "every run" trigger, write an identical snapshot every time — noisy, though not incorrect. A "write only on a genuinely new settled check" rule would need its own careful definition. **Deferred with §35/§39** — flagged here so the future increment inherits this open question explicitly rather than rediscovering it.

---

## §41. Automation + snapshot transaction requirement (a hard constraint for whenever §35's future increment lands)

**Frozen requirement, for the future increment, stated now so it is never lost:** if snapshot persistence is ever built, the snapshot write **must** occur inside the *same* transaction as the successful analysis recomputation it describes (§21/§24's own existing one-transaction-per-occurrence discipline extends naturally to this) — otherwise a recorded snapshot could durably claim "EI calculated X" for a computation that was later rolled back, which would be a direct, active violation of the historical-truth discipline this entire project holds itself to (§1/§51 of `state-duration-v1.md`, restated here as a forward-looking constraint).

---

## §42. Delay cost (quantified, not hand-waved)

**If automation ships in #25C but recorded-state persistence does not ship until a later, dedicated increment, what is permanently lost?** Precisely: every occurrence-check that happens between #25C's deployment and the future snapshot increment's own deployment, for which the canonical state was recomputed and confirmed *unchanged* (§37's own gap), leaves no durable trace of that confirmation. **How strategically important is that?** Real, but bounded and small in absolute terms — this project's own increment cadence (observed directly this session: #24A through #24D, and now #25A/#25B, all completed within one continuous working session) suggests the gap between #25C and a follow-on snapshot increment is realistically short, not months. **This is the honest, quantified answer §35 already reasoned from — restated here explicitly per the prompt's own separate instruction to answer it on its own.**

---

## §43. #25C scope decision (frozen, no ties)

**OPTION A — #25C = automation only.** Justified fully in §35/§42. Recorded-state/snapshot persistence is explicitly deferred to its own future, dedicated contract-freeze increment, not abandoned.

---

## §44. Automation hosting model (audited, grounded in confirmed repo evidence — no assumption)

**Confirmed directly, this turn:** `pyproject.toml` declares exactly `fastapi`, `uvicorn[standard]`, `httpx`, `python-dotenv`, `sqlalchemy`, `alembic`, `psycopg[binary]`, `openai` — **no job-queue, scheduler, or background-worker dependency of any kind** (no Celery, no Redis, no APScheduler, no RQ). No `Dockerfile`, `Procfile`, `docker-compose.yml`, or any deployment configuration exists anywhere in the repository root (confirmed by direct listing). **This project has no deployment/hosting story today, full stop — this is the single largest genuine unknown, named honestly rather than assumed away.** Given this, the correct design principle is: **choose the option that assumes the least about where or how this application will eventually be hosted.**

---

## §45. In-process scheduler — explicitly evaluated and rejected

An APScheduler-style in-process scheduler (started at FastAPI's own startup) is evaluated and **rejected for V1**: it couples release processing's lifecycle to the *web* process's lifecycle (restarts, redeploys, and — critically — **any future horizontal scaling to multiple web worker processes would multiply the scheduler itself**, silently reintroducing exactly the concurrency risk §18 already names, now self-inflicted by the architecture rather than by an external actor). Given §44's own finding (no deployment story exists, so scaling assumptions cannot be ruled out), this risk is real, not hypothetical, and the smaller, safer alternative (§47) has no such coupling at all.

---

## §46. Scheduled HTTP endpoint — explicitly evaluated and rejected for release *processing*, distinguished from release *calendar sync*

A dedicated `POST /maintenance/run` (or similar) endpoint, triggered by an external scheduler over HTTP, is evaluated and **rejected for release processing specifically** — it would require either a new authentication mechanism (this project has none, anywhere, by explicit design — `app/operations/process_release.py`'s own docstring states plainly why release processing was deliberately kept off the public HTTP surface) or accept an unauthenticated public mutation endpoint that issues external provider requests and canonical database writes, which is exactly the risk this project already refused once, explicitly, for the manual CLI's own design. **Important, precisely-confirmed asymmetry, discovered this turn:** `POST /api/v1/releases/sync` (the release *calendar* sync — discovering/upserting `ReleaseOccurrence` dates from FRED) **already is** a real, existing, unauthenticated HTTP mutation endpoint (`app/api/releases.py`, confirmed fresh) — deliberately safe to expose because it only writes idempotent catalog *metadata* (dates), never canonical economic observations or analysis. **This means automation has two different, correctly-differentiated safety postures for its two different needs: the calendar half may safely be scheduled via the existing public `/releases/sync` endpoint (or an equivalent direct service call) exactly as it already could be triggered manually today; the processing half must not become a public endpoint and should be scheduled via the CLI-shaped path instead (§47).**

---

## §47. Existing CLI reuse — frozen as the smallest viable architecture

**Frozen: the smallest, most portable architecture is a platform-agnostic scheduler (any of: a developer's own local cron, a future PaaS's own scheduled-task feature, a CI system's scheduled workflow, or a simple long-lived polling loop process — genuinely any of these, since none is assumed by this decision) invoking a new "process all due occurrences" CLI mode** that reuses `ReleaseProcessingService`/`process_occurrence` completely unmodified, looping over the due-work query's own results (§8). This requires **zero new runtime dependency**, **zero new deployment infrastructure**, and is portable across local, staging, and any future production environment (§62) without the application itself needing to know *how* it is being invoked. The existing single-occurrence CLI mode (`--occurrence-id`) remains, unmodified, for manual/operator use (§59). The **new** mode is additive — described here as "the orchestrator" (§48), not yet named or implemented.

---

## §48. Orchestrator responsibilities (frozen boundary)

The orchestrator (new, #25C's own work):

- **Must:** discover due work (§8), acquire the advisory lock per occurrence before processing it (§19), invoke the existing, unmodified `ReleaseProcessingService.process_occurrence` once per occurrence inside its own `session_scope()` (§20/§21), record the outcome (reusing the existing `ReleaseCheckRun` model, unmodified), emit structured operational status (§31), and independently, durably log any occurrence for which even the database layer itself failed (§23).
- **Must not:** calculate any economic value, classify any monitor state, modify any methodology, or interpret any result — it is a pure trigger-and-record layer around economics that already, correctly, lives entirely in `app.domain`/`app.services.release_processing`, unchanged.

---

## §49. Provider load / rate safety (estimated, not measured — consistent with this project's own prior practice)

Mapped releases are currently few (six curated releases per #21's own inventory, feeding four canonical series total). An hourly-order sweep (§15), filtered to only `PAST_DUE`, unsettled, mapped occurrences (§8), produces a genuinely small, bounded number of FRED calls per sweep — almost always zero-to-a-few, since most occurrences are either `SCHEDULED` (not yet checked) or already settled (§10, no longer re-checked). **No exact cost optimization is claimed or required** — this is an estimate, matching this project's own established discipline (e.g., `state-duration-v1.md` §36's identical "estimated, not measured" framing) of not pretending false precision where none is needed.

---

## §50. Backfill policy (frozen: bounded, forward-looking only at launch)

**Frozen: automation, on first launch, must NOT attempt to process every historical `PAST_DUE` occurrence.** That would be dangerous (a large, un-throttled burst of provider calls against occurrences whose economic relevance has long since passed) and unnecessary (historical occurrences already either have a manual `ReleaseCheckRun` from before automation, or genuinely were never checked, in which case processing them now adds no meaningful current value). Frozen launch behavior: **the due-work query (§8) is naturally scoped to occurrences from automation's own deployment date forward, plus any genuinely recent, still-unresolved occurrence within the ordinary retry window (§14)** — no special backfill mode, no separate large-batch job.

---

## §51. Pre-automation history — provenance (frozen: needed, described)

Occurrences and checks that predate automation must never be silently presented as if they had the same reliability guarantee as automation-covered ones. Frozen: an **`automation_started_at`-shaped operational fact** (exact representation left to #25C — could be as simple as a documented deployment date, or a small config value; not schema-worthy on its own) is required so any future freshness/history feature can correctly treat pre-automation gaps as `UNKNOWN` (§29), never `STALE` (which would incorrectly imply automation *should* have caught something it was never running to catch) and never `FRESH` (which would overclaim coverage that never existed).

---

## §52. Deployment/scheduler-silence detection (frozen: requires §53)

**If the scheduler itself stops firing entirely, the database shows nothing — no failed runs, because nothing ran at all.** This is invisible to any query over `ReleaseCheckRun` alone, and is a fundamentally different failure mode from "a run happened and failed" (§13/§23). **This absence-of-evidence problem is exactly why §53's sweep record is required**, not optional.

---

## §53. Sweep record (frozen: required, new and distinct from `ReleaseCheckRun`)

**Frozen: yes, a separate, lightweight record is required** — without it, worker health (§30) cannot be distinguished from worker silence (§52), and "zero due work found" cannot be distinguished from "the sweep never ran." This is conceptually **not** the same object as `ReleaseCheckRun` (which is per-occurrence, economic-check-shaped); this is per-sweep, operational-health-shaped. **This does require a small new persisted table — a real migration for #25C** (§68), named here explicitly rather than avoided to keep the implementation artificially small, per the instruction not to dodge a necessary migration.

---

## §54. Sweep/automation-run record — semantics (frozen; schema left to #25C)

If built (§53 says it must be): `started_at`, `finished_at`, `status` (did the orchestrator itself complete without an unhandled error), `due_count` (occurrences found due), `processed_count`, `failed_count` (occurrences ending `PARTIAL_FAILURE`/`FAILED_PROVIDER` this sweep). **Concept frozen as necessary; exact column list/schema is #25C's own implementation-level decision**, not designed further here.

---

## §55. Scheduler vs. orchestrator boundary (frozen)

**SCHEDULER** decides *when* code runs — cron, a platform's own scheduled-task feature, or any future equivalent (§47); intentionally kept swappable. **ORCHESTRATOR** decides *what* due work exists and processes it (§48) — the due-work query, the locking, the per-occurrence invocation, the sweep record. **Frozen: these must remain decoupled** — the scheduler's only job is to periodically invoke the orchestrator's own entry point (the new CLI mode, §47); it must never itself contain due-work logic, locking logic, or any economic awareness. This lets the scheduling mechanism change freely in the future (local cron today, a platform scheduler tomorrow) without ever touching the orchestrator's own, stable, tested logic.

---

## §56. Testability (frozen: explicit injection boundaries required)

The orchestrator must be testable without a real clock or real network, mirroring this project's own established discipline (every `_at`-suffixed domain function already takes its reference point as an explicit parameter, never reads the system clock internally). Frozen injection boundaries for #25C: **current date/time** (an explicit `as_of_date`/`now` parameter, exactly matching `process_occurrence`'s own existing shape — never a bare `date.today()`/`datetime.now()` scattered through new orchestration code); **the FRED client** (already injectable, unmodified — `ReleaseProcessingService.__init__(self, fred_client)`); **the repository/session** (already injectable via `session_scope()`, unmodified). **No new testability primitive is required — the orchestrator should be built to the same discipline the service it wraps already demonstrates.**

---

## §57. Clock (frozen: single explicit input, never scattered)

Direct consequence of §16/§56: the orchestrator's own "now" must be resolved exactly once, at its own entry point, and threaded explicitly through the due-work query and every `process_occurrence` call as `as_of_date` — never re-read ad hoc at multiple points inside one sweep (which would risk a sweep spanning a UTC-date boundary mid-run producing subtly inconsistent eligibility decisions within the same sweep). **Frozen requirement, not yet a concern in the existing single-occurrence CLI** (which only ever resolves "now" once, trivially) but newly relevant now that one orchestrator run will evaluate many occurrences together.

---

## §58. Reentrancy (frozen: safe by construction, given §19/§20)

A sweep running twice (back-to-back, or overlapping) must safely find: no work (if the prior sweep already settled everything, §10); unresolved work (correctly re-surfaced, §8); retryable work (correctly re-attempted within the retry window, §14) — **without corrupting state, provided the advisory lock (§19) is held per occurrence.** Given §17/§20's own already-confirmed idempotency and crash-safety properties, reentrancy is safe **once concurrency protection (§19) is in place** — it is not an independent new risk beyond what §18 already names.

---

## §59. Manual CLI coexistence (frozen: must remain safe and available)

**The existing manual, single-occurrence CLI path must remain available after automation ships** — for recovery, testing, and deliberate operator intervention (e.g., forcing an immediate check ahead of the next sweep). **Frozen requirement: the manual path must acquire the same advisory lock (§19) an automated run would**, so a manual invocation and an automated sweep can never race against the same occurrence — this is the one small, necessary extension to the *existing* CLI entry point automation requires (acquiring/releasing the lock), not a new mode or a behavior change to what it computes.

---

## §60. User-triggered processing (frozen: explicitly not exposed)

**Frozen: release processing is never exposed to ordinary end users, in this increment or any planned future one.** No public route, no button, no user-facing trigger of any kind — consistent with, and unchanged from, this project's own standing security posture (§46).

---

## §61. Security (frozen: minimizes new surface, reuses existing posture)

Automation, per §46/§47's own decision, introduces **no new public HTTP mutation endpoint** for release processing itself — the orchestrator is invoked by a scheduler in the same trust boundary as the existing manual CLI (an operational action, outside normal end-user HTTP traffic, exactly per `process_release.py`'s own existing docstring). The release *calendar* sync half may continue to use its own already-existing, deliberately-unauthenticated `/releases/sync` endpoint, whose safety rationale (idempotent metadata only, never canonical economic writes) is unchanged by this document. **No secret value was read, inspected, or required to reach this conclusion** — only the *existence* and *names* of configuration variables (`fred_api_key`, `database_url`) were referenced, exactly as `process_release.py`'s own existing code already does, never their values.

---

## §62. Deployment portability (frozen: orchestrator logic identical everywhere; only the scheduler varies)

Given §55's own scheduler/orchestrator separation: the orchestrator's own logic (due-work discovery, locking, per-occurrence processing, sweep recording) is **identical** whether it runs locally, in staging, or in a future production environment — only the *scheduling mechanism* invoking it varies (a developer's own cron locally, a platform's scheduled-task feature elsewhere). **Frozen: no economic semantics may ever depend on which scheduler is in use.**

---

## §63. Failure escalation (frozen: semantics only, no alerting infrastructure built)

Escalation to "operator attention required" is warranted, conceptually, when: an occurrence reaches retry exhaustion (§14) without settling; a `FAILED_PROVIDER` outcome's underlying cause is `FREDAuthError` (§13 — not retryable by waiting); the sweep record (§53) shows the orchestrator itself failing repeatedly, or (§52) shows the scheduler has gone silent longer than its own expected interval. **No alerting mechanism (email, Slack, paging) is built this increment** — these semantics are frozen so a future, separate operational-alerting increment has a well-defined signal to act on, not invented ad hoc later.

---

## §64. Since-Last-Visit readiness after #25C (frozen)

**Safe claim after #25C:** *"Economic Intelligence detected these changes since your last visit, as of its last successful check at {time}."* — the freshness fact (§26/§32) makes this honest without requiring perfection. **Still unsafe after #25C, and not claimed:** "everything that changed in the economy" (never claimed, per §27/§33, regardless of automation); "up to date" as an unconditional claim (§27, permanently out of scope for this mechanism); a claim that a `NO_CHANGE` result during any period preceding automation's own deployment reflects a reliable check (§29/§51 — that period is `UNKNOWN`, not confirmed-quiet).

---

## §65. Recorded-history readiness after #25C (frozen)

**After #25C, will EI have begun accumulating recorded canonical history? No — by design (§35/§43), snapshot persistence is deliberately not part of #25C.** What #25C *does* provide, forward-looking: a reliable, regular cadence of checks against which a *future* snapshot mechanism could be triggered with real, non-gap-prone regularity (§42) — the prerequisite made real, not the asset itself. Exact delay cost: bounded and small (§42, quantified, not hand-waved).

---

## §66. "Continuously maintained" — truthful claim after #25C (frozen language)

**Still not "continuously maintained" in the strongest sense** — automation checks on a scheduled cadence (§15), it does not achieve true real-time currency (nor should it, §15). **Safer, accurate language, frozen as the recommended phrase:** *"automatically checked against mapped economic releases on a regular schedule"* — true, specific, and does not imply a stronger guarantee (instantaneous, complete, or gap-free) than the architecture actually provides. Reaffirms and sharpens #25A §23's own prior recommendation, now backed by this increment's own concrete design rather than a general caution.

---

## §67. Freshness UX prerequisite and sequencing (frozen)

**Yes, the frontend must eventually expose freshness (§32) before Since Last Visit's own honesty is complete** — this belongs conceptually to **#25D (Since Last Visit's own product contract freeze)**, not to #25C, because it is a *product/UX* decision (exact copy, exact placement) built on top of the *data* semantics this document freezes (§26), not an operational-design decision itself. **#25C's own job is only to make the underlying "last checked" fact reliably queryable** — presenting it is out of this document's and #25C's scope.

---

## §68. Database migration decision (frozen: required, named explicitly)

**This increment (#25B) creates no migration**, per its own explicit constraint. **#25C will require one migration** — for the sweep/automation-run record (§53/§54), which cannot be represented without a new table. **No migration is required for locking (§19, an advisory lock, not schema) or for the due-work discovery query (§8, a read-only join over existing tables).** Named explicitly, not avoided merely to keep #25C's own footprint artificially small, per the source prompt's own instruction.

---

## §69. Architecture Decision Record recommendation

**Recommend one ADR** for the durable decision this document makes that most affects future work: **the scheduler/orchestrator separation (§55) and the choice of platform-agnostic CLI-reuse over an in-process scheduler or a public HTTP trigger (§45–§47)** — this is the one choice future increments (and any future deployment-model decision) will need to remain compatible with, mirroring this project's own existing ADR practice for comparably load-bearing boundary decisions (e.g., ADR-009's repository boundary, ADR-016's discovery-sync boundary). **Not created in this increment** (per the instruction that a contract-freeze audit recommends, rather than creates, unless repository convention says otherwise) — recommended for #25C's own implementation turn to add alongside the code it governs.

---

## §70. #25C test matrix (frozen)

No due work found (sweep completes cleanly, sweep record shows zero processed); one due occurrence (happy path, `NO_CHANGE`); one due occurrence, `CHANGED`; multiple due occurrences in one sweep, processed independently; an occurrence already settled (§10) is correctly excluded from due-work discovery; `NEW` observation; `REVISED` observation; an occurrence that reaches settlement after a prior `NO_CHANGE` still gets at least its retry-window allotment (§10's own conservative extra checks); `PARTIAL_FAILURE` (mixed per-series outcomes in one run, re-surfaced as due next sweep); `FAILED_PROVIDER` (all series fail, `FREDAuthError` escalates differently from `FREDTimeoutError`, §13); a genuine database failure mid-run (transaction rolls back, no `ReleaseCheckRun` row exists, orchestrator's own external log still records the attempt, §23); two sweeps racing the same occurrence (advisory lock correctly prevents duplicate audit rows, §18/§19); a manual CLI invocation racing an automated sweep (same lock, same safety, §59); a simulated crash mid-occurrence (next sweep recovers cleanly with zero special-cased logic, §20); explicit clock/`as_of_date` injection, never a bare system-clock read, across a UTC-date boundary (§16/§57); manual and automated paths coexisting in the same test run without interference (§59); no AI import anywhere in the orchestrator's own import graph; no economic-formula reimplementation anywhere in the orchestrator (an architecture guard, not just a test); provider-call count stays bounded for a realistic due-work set (§49, a sanity bound, not a strict performance test); sweep-record fields correctly reflect due/processed/failed counts; a scheduler-silence scenario (no sweep record for longer than the expected interval) is distinguishable, by a read-model test, from "zero due work this sweep."

---

## §71. Architecture guards (frozen, for #25C)

Extending this project's own established, dedicated-guard-test pattern: the orchestrator module imports no AI/OpenAI/LLM dependency; the orchestrator implements no economic formula, threshold, or classification of its own (an AST-level "imports only the existing service's public entry point" guard, mirroring `tests/test_labor_architecture.py::TestServiceNeverClassifiesEconomics`'s own precedent); the scheduler-invocation mechanism (whatever it turns out to be, §47) never itself contains due-work or locking logic (§55, structurally enforced, not just documented); no public, unauthenticated HTTP route is added for release *processing* specifically (§46/§60 — a route-count/route-path guard mirroring `tests/test_labor_architecture.py`'s own `TestExactlyThreeLaborRoutes`-style precedent, applied to confirm no new mutation route appears under `app/api/`); no silent provider-failure-as-`NO_CHANGE` collapse (§22, a structural/behavioral guard, not a grep); no silent partial-as-complete collapse (§10/§12, likewise behavioral); no server-local (non-UTC) timezone dependency anywhere in the new orchestration code (§16, a targeted grep for a bare `datetime.now()` without an explicit `timezone.utc` argument, scoped to the new files only, mirroring this project's own established narrow-scoping discipline for guards); no occurrence processed without first acquiring its advisory lock (§19, a structural guard on the orchestrator's own call shape, not just a test of the happy path).

---

## §72. Explicit deferrals (do not build, this increment or #25C)

Since Last Visit UI (#25D/E's own scope); Watchlist; accounts; notifications (needs automation as a prerequisite trigger, per #25A §26, but is not itself in scope here); Growth; Compare; AI; a full historical timeline; ALFRED/vintage data; a generic, reusable job-queue framework; a distributed event bus; microservices; Celery/Redis (explicitly not required — §44/§47's own smallest-viable-architecture finding); Kubernetes; real-time streaming. **Recorded-state/snapshot persistence** is deferred per §35/§43's own explicit, reasoned decision — named here again for completeness, not merely implied by omission.

---

## §73. GO / STOP standard applied

Every numbered question in the source prompt's own §74 checklist is answered with a specific, evidence-grounded, frozen decision above: automation unit (§4), due-work discovery (§8), `NO_CHANGE` vs. completion (§9), settlement (§10), partial-update behavior (§11/§12), retries (§14), timezone (§16), idempotency (§17), concurrency protection (§18/§19), crash recovery (§20), freshness semantics (§25–§29), worker-health semantics (§30), scheduler/orchestrator boundary (§55), deployment model (§44/§47), whether recorded-state persistence ships with automation (§35/§43 — explicitly NO, with reasoning), exact #25C scope (§43), migration expectations (§68), tests (§70), guards (§71), and truthful claims after implementation (§64–§66). **None of these remain materially ambiguous.**

---

## Appendix: secret safety and version control

No `.env`/`.env.*`/credential file was read, printed, or logged at any point this increment — only filenames and the *names* (never values) of configuration variables already referenced by existing, already-committed code (`fred_api_key`, `database_url`) were used, exactly mirroring how `app/operations/process_release.py` itself already references them. `pyproject.toml`, `alembic.ini`, and the repository root's own file listing were inspected only for dependency/deployment-tooling *presence*, never for secret content. Nothing in this document was committed or pushed; no production architecture doc (`current-architecture.md`, `request-flows.md`, `ENGINEERING_JOURNAL.md`) was modified this increment, per instruction; the working tree outside this new file was not modified.
