# Production Reliability, Migration & Deployment Architecture — V1

**Increment #26B.** Audit / design / contract freeze only. No production code changed, no migrations run against any existing database, no Dockerfile/CI/deployment manifest/scheduler configuration/readiness endpoint/monitoring added, no frontend code, no economic functionality, no AI. Baseline: HEAD `793eb79` ("Audit post-return-loop commercial readiness (#26A)"), clean working tree. Verified fresh this increment: backend 1,463/1,463 passed, 0 skipped; frontend 1,137/1,137 passed; `tsc -b --noEmit` clean; `oxlint` clean; `vite build` clean.

This document is the authoritative contract for the #26C→#26F implementation sequence (§61). It designs the smallest reliable production operating model that makes the #26A incident structurally impossible to repeat silently — it does not implement that model, and it does not casually run the migration that would currently fix the symptom.

---

## §1. Incident, restated precisely (from #26A, re-verified this turn — see §3)

`GET /api/v1/since-last-visit` returned HTTP 500 against the running local dev instance. Root cause: the application's code (HEAD, Alembic head `f5420059a092`) expects `recorded_monitor_results` (created by that migration); the database the running instance was pointed at was still at `09f4c0959e9f`, one migration behind. The table did not exist. The symptom (a single broken Overview card) was narrow; the underlying condition (nothing on the path from "code is deployed" to "code is serving traffic" ever checks that the database agrees with the code) is systemic, not specific to this one table or this one feature.

---

## §2. Core principle, adopted and validated against this repository (not frozen by reflex)

**Deployment is part of product correctness.** Validated, not merely asserted: this project's own `ADR-008` already established a directly adjacent principle — "Application startup never calls `Base.metadata.create_all()`" — precisely because letting the running process's own model definitions silently dictate schema state loses the reviewable, ordered migration history the whole Alembic decision exists to provide. That decision already implies schema state must come from a deliberate, external, auditable act, never an implicit one — this document extends the *same* discipline to a case ADR-008 didn't yet cover: what happens when the deliberate act (running the migration) is simply forgotten. The target invariant, validated against the repository and adopted verbatim:

> **Traffic may reach an application instance only when: the application starts successfully AND the database is reachable AND the database schema is compatible with that application version AND required runtime configuration exists.**

No part of this wording needed revision — every clause maps onto a real, separately-checkable fact this repository already has the pieces to compute (§14/§15 below).

---

## §3. Baseline

`git status --porcelain`: clean. `git log -12 --oneline`: HEAD `793eb79` ("Audit post-return-loop commercial readiness (#26A)"), #26A committed as instructed. Backend: `TEST_DATABASE_URL=... pytest tests/ -q` → **1,463 passed, 0 skipped**. Frontend: `npm test -- --run` → **1,137 passed**; `npm run typecheck` → clean; `npm run lint` → clean; `npm run build` → clean (100 modules, ~140ms). The dev database was **not** touched before or during this inspection (§50).

---

## §4. Required reading (§1 of the source prompt)

Read in full this turn: `docs/product/post-return-loop-commercial-readiness-audit-v1.md` (#26A), `docs/product/automated-economic-maintenance-v1.md` (#25B), `docs/product/recorded-state-history-v1.md` (#25D), `docs/product/since-last-visit-v1.md` (#25F). Read relevant sections of `docs/architecture/current-architecture.md`, `docs/architecture/request-flows.md`, `docs/ENGINEERING_JOURNAL.md` (targeted, keyword-scoped — these documents already exceed single-read size; every deployment/migration-relevant passage in each was located and read). ADRs read in full: **006** (PostgreSQL persistence), **007** (synchronous SQLAlchemy — transactions), **008** (Alembic migrations), **024** (scheduler/orchestrator separation), **025** (Recorded State History append-only persistence), **026** (Since Last Visit server watermark/event spine).

**One directly load-bearing fact recovered from the journal that no #26A document mentioned:** this exact failure class already happened once before, earlier in this project's history (documented at `ENGINEERING_JOURNAL.md:7071-7096`). A prior increment's own visual review found "the dev database was found not migrated past an old #17A-era revision... a pre-existing gap unrelated to this increment," and was resolved, at the time, by the operator explicitly approving a manual `alembic upgrade head` mid-session. **This is the second time this exact operational gap has produced a live failure — not a first-time fluke.** This materially strengthens §55/§56 below: the gap is recurring and systemic, not a one-off lapse.

---

## §5. Deployment surface inventory (fresh, broader than #26A's own search)

| Item | Status |
|---|---|
| Dockerfile / docker-compose | Absent |
| Procfile / render.yaml / fly.toml / railway config / Vercel config | Absent |
| GitHub Actions / any CI | Absent |
| Deployment scripts | Absent |
| Makefile / Justfile / Taskfile | Absent |
| Startup scripts | Absent (app runs via bare `uvicorn`) |
| Migration scripts beyond `alembic` itself | Absent — `alembic upgrade head` is the only mechanism, always run by hand |
| Environment docs | `.env.example` exists (4 variable **names**: `FRED_API_KEY`, `DATABASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL`); `frontend/.env.example` separately governs `VITE_API_BASE_URL` |
| Production README | Absent — `README.md` covers local dev setup only |
| Health check | **`GET /health` exists** (`app/main.py:27-29`) — returns `{"status": "ok"}` unconditionally; process-liveness only, no DB call, no schema check, no version info. **Not found or mentioned by #26A's own search** — confirms the instruction that #26A's absence search was not exhaustive. |
| Readiness check | Absent — no route distinguishes "alive" from "safe to serve" |
| Scheduler / cron configuration | Absent |
| Worker configuration | Absent (`app/operations/run_maintenance.py` exists as a one-shot CLI, §23 — nothing invokes it periodically) |
| Logging | Absent beyond uvicorn's own default access logs and `run_maintenance.py`'s own safe, structured `_print_summary` stdout output |
| Monitoring / error reporting / APM | Absent |
| Backup configuration | Absent — no evidence of any backup mechanism for the local dev database, and no production database exists yet to back up |
| CORS configuration | **Absent** — no `CORSMiddleware`, no `allow_origins` anywhere in `app/`. Works today only because the Vite dev server proxies `/api/*` same-origin (`frontend/vite.config.ts`); the moment frontend and backend deploy to different origins (the shape `VITE_API_BASE_URL`'s own existing build-time design already anticipates), every request will fail until CORS is explicitly configured (§33). |

---

## §6. Incident reproduction, read-only, re-confirmed this turn (§3 of the source prompt)

```
$ .venv/bin/alembic current   →  09f4c0959e9f
$ .venv/bin/alembic heads     →  f5420059a092 (head)
$ psql ... \dt                →  recorded_monitor_results NOT present
```

Unchanged from #26A — the environment has not been touched since. **Not upgraded.** No `alembic upgrade` command was run against this database at any point in this increment; the incident remains exactly as #26A left it, preserved for whoever performs the actual remediation (§50).

---

## §7. Migration chain audit (§4 of the source prompt)

Eight migrations, traced by `revision`/`down_revision` in every file — **a single, strictly linear chain, no branches, no merge revisions:**

```
6412695f6f9d  create economic_series, economic_observations
     ↓
42114760e4c8  create economic_releases, release_occurrences
     ↓
fbbe6b1ab8d9  SEED: 6 curated V1 releases                          [data migration]
     ↓
dbd9a2889ef3  create release_series_mappings, release_check_runs,
              release_analysis_updates, release_observation_updates
     ↓
cd476d227f99  SEED: CPI + Personal Income and Outlays mappings      [data migration]
     ↓
09f4c0959e9f  SEED: Employment Situation mapping                    [data migration]
              ← THE RUNNING DEV DATABASE IS HERE
     ↓
f12b7ec0d626  create maintenance_sweeps
     ↓
f5420059a092  create recorded_monitor_results                       [HEAD]
```

Every schema-creating migration is **purely additive** — `op.create_table`/`op.create_index` only, never `alter_column`, never `drop_column`, never a type change, never a nullable→non-null tightening of an existing populated table. Every data migration (`fbbe6b1ab8d9`/`cd476d227f99`/`09f4c0959e9f`) inserts a small, fixed, named row set and its own `downgrade()` deletes **only those exact rows**, by exact `(provider, provider_release_id)`/`(release_id, series_id)` identity — never a blanket `DELETE FROM`, confirmed by direct inspection of every `downgrade()` body. **Every migration has a real, correct, tested-shape `downgrade()`.** No lock-risk operation exists anywhere in the chain: every `CREATE TABLE`/`CREATE INDEX` targets a table with zero rows at creation time (a brand-new table), which in PostgreSQL takes an `ACCESS EXCLUSIVE` lock but for a negligible duration against an empty relation — no `CREATE INDEX CONCURRENTLY` need has ever existed here, and none will until a migration targets an already-large, already-live table. `alembic.ini`/`env.py` confirm transactional DDL is assumed (`Will assume transactional DDL` — logged directly during this turn's own `alembic current` run) — **a failed migration in this chain rolls back atomically at the database level**, never leaving a half-applied table. **Verdict: the migration chain itself is clean, safe, and not the problem.** The incident is 100% an *application* gap (nothing checks whether the migration ran), never a *migration-quality* gap.

---

## §8. Alembic head as compatibility contract, and future rolling-deployment consideration (§5 of the source prompt)

**For V1: database revision must equal the packaged application's own Alembic head, exactly.** Chosen deliberately, not by default — evaluated against this project's actual current shape: single developer, single environment, no rolling deploys, no more than one application version ever intentionally live at once (confirmed, §5). Under these conditions equality is strictly simpler than a range and loses nothing, because there is no scenario today where two different application versions legitimately need to tolerate two different schema states simultaneously.

**This does not scale forever, and this document says so explicitly (§32):** the moment either (a) a future migration needs to drop, rename, or narrow something an *old, still-running* application version depends on, or (b) a rolling/blue-green deployment means old and new application code may run concurrently against one database for any window of time, exact equality becomes too strict (a perfectly fine old instance would report itself incompatible against a schema that is a strict superset of what it needs) and the policy must generalize to a **minimum-compatible-revision** range (§32).

---

## §9. Schema compatibility strategy — options compared, V1 chosen (§6 of the source prompt)

| Option | Description | V1 fit |
|---|---|---|
| **A. Exact revision equality** | `db_revision == app_expected_head` | **Chosen for V1** — matches §8's own reasoning exactly; every migration so far is additive, so equality never produces a false incompatibility against real data |
| B. Minimum compatible revision | `db_revision >= app_min_required` | Requires a second, tracked value (`min_required_revision`) per app version with no current need to track it — premature |
| C. Explicit compatibility range | `app_min <= db_revision <= app_max` | Solves a problem (forward-compatibility with a *newer* schema an older app doesn't yet know about) this project does not have yet — no scenario today deploys an old app against a newer DB deliberately |
| D. Expand/contract | Two-phase migrations, app tolerates both old and new shape across a deploy window | The **correct future model** (§32), not V1 — no rolling deploy exists yet to require it |

**V1 = Option A**, with the explicit, documented commitment to migrate to Option D (not B or C) once §8's trigger conditions are met — B/C are evaluated and rejected as intermediate steps that would need to be re-litigated anyway once real expand/contract becomes necessary; going straight to D when the need arises is simpler than climbing through B/C first.

---

## §10. Should web startup mutate schema? (§7/§8 of the source prompt)

**NO — explicit, validated against the repository, not merely the audit's own prior.** ADR-008 already established the adjacent, directly-supporting precedent (§2). Web startup mutating schema is additionally unsafe for a reason ADR-008 didn't need to consider (a single-process, single-instance world): **any future world with more than one running web replica would have every replica attempt to run `alembic upgrade head` concurrently at boot** — Alembic does take its own migration lock (a Postgres advisory lock under the hood) so this would not corrupt the schema, but it would make deploy timing non-deterministic (whichever replica boots first "wins" the migration, others block or fail depending on timeout), couple a routine web-process restart to a schema-mutation risk it has no business carrying, and make a failed migration indistinguishable from a failed web boot in the operator's own mental model. **Frozen: web startup only ever *validates* compatibility (§14) — it never runs `alembic upgrade`, `alembic downgrade`, or any DDL, under any condition.**

---

## §11. Startup-migration architecture — options compared, one chosen (§7 of the source prompt)

| Option | V1 fit |
|---|---|
| A. Every web process runs `alembic upgrade head` at startup | **Rejected** — §10 |
| **B. One release-phase/job runs migrations before rollout** | **Chosen** — the correct production shape; a single, explicit, ordered step: migrate → THEN deploy/route traffic to the new app version. Concretely for V1 (before any real CI/CD exists, §61's #26D): a human operator, running `alembic upgrade head` by hand against the target database, as a deliberate, separate, named step preceding any code deploy — not folded into "start the app." Once a real CI/CD pipeline exists (#26D), this becomes an explicit pipeline stage (§12), not a change in *philosophy*, only in *who/what* performs the already-frozen step. |
| C. Manual migration command | This **is** Option B today, for a single developer with no pipeline — named as the same thing, not a fourth option, to avoid manufacturing a false distinction |
| D. Dedicated migration container/job | The natural evolution of B once a real deployment platform exists (§42) — not chosen now because no platform has been chosen yet; consistent with B, not a competing option |
| E. Other | None identified |

**Frozen: Option B, in its "explicit human/operator step today, an explicit pipeline stage tomorrow" form.** This directly resolves the #26A incident's own root cause going forward: the missing step (§1) becomes a *named, required, ordered* step rather than an implicit assumption.

---

## §12. Deployment pipeline — exact phases, frozen (§12 of the source prompt)

```
1. Build         (application artifact — a container image once #26D exists; today, "the committed code at a specific SHA")
2. Test          (the existing backend + frontend suites, unchanged — already comprehensive, §7 confirms migrations
                   are already exercised correctly by the test fixture itself)
3. Migration preflight   (compute target DB's current revision; compare to the artifact's own expected head;
                           if ALREADY equal, skip step 4 — idempotent, never re-run migrations that already applied)
4. Apply migration        (`alembic upgrade head` against the target database — the ONE place schema ever changes)
5. Verify schema           (re-read the DB's revision; confirm it now equals the artifact's expected head; ABORT
                            the whole deployment if not — §13)
6. Deploy web               (roll out the new application artifact — only ever reached after step 5 succeeds)
7. Readiness check           (the new instance(s) must self-report ready — §14 — before receiving real traffic)
8. Activate traffic            (a load balancer/router directs traffic only to instances that passed step 7)
9. Verify maintenance worker     (confirm the scheduler invoking `run_maintenance` is pointed at the same,
                                  now-migrated database and is itself compatible — §20)
```

**Frozen ordering rule: migration (3-5) always precedes application rollout (6), never the reverse, and never concurrent with it.** This single ordering rule is the direct, structural fix for the #26A incident — the incident occurred precisely because step 3-5 was never performed as its own, verified, gating step at all.

---

## §13. Migration failure behavior (§13 of the source prompt)

**Frozen: a migration failure aborts the deployment. New application code must never be deployed to serve traffic against a database whose migration attempt failed or is unverified.** Because Postgres DDL is transactional here (§7 — confirmed, "Will assume transactional DDL"), a failed migration leaves the database at its **prior, still-valid** revision — the **currently-running, old application version** (which was already compatible with that prior revision by construction, since it was serving traffic successfully before the deploy began) **continues serving traffic completely unaffected.** No traffic is ever routed to the new, undeployed code; no manual intervention is required to "protect" users from a failed migration — they simply never see the attempt. Manual operator intervention **is** required to diagnose and fix the migration itself before the deploy can proceed — this is intentional friction, not a gap.

---

## §14. Application readiness — defined (§14 of the source prompt)

**Readiness = process alive AND database reachable AND database schema revision compatible (§9) AND required runtime configuration present.** Concretely, for V1's exact-equality policy: `alembic_version` table's current revision (read via a plain, cheap `SELECT`, not by shelling out to the `alembic` CLI) equals the application artifact's own known-at-build-time expected head; `DATABASE_URL` resolves to a live, connectable database (a single lightweight `SELECT 1`); `DATABASE_URL` itself is present (§34). **Readiness must NOT call FRED or require any external provider to succeed** — validated directly against this project's own already-frozen, directly-analogous precedent: `automated-economic-maintenance-v1.md` §30's "WORKER HEALTH vs. ECONOMIC FRESHNESS are separate concepts, never conflated" rule, generalized here to "REQUEST-SERVING READINESS vs. DATA FRESHNESS are separate concepts" — a FRED outage should never make the entire application report itself unready to serve already-persisted data, exactly as a `MaintenanceSweep` finding zero due work is correctly a *success*, not a *failure*, per that same document.

---

## §15. Health vs. readiness — exact V1 API semantics (§15 of the source prompt)

| | `/health` (unchanged, already exists) | `/readiness` (new, described here — not implemented) |
|---|---|---|
| **Question answered** | Is the process alive and able to handle an HTTP request at all? | Is it safe to route real application traffic to this instance? |
| **Checks performed** | None — a bare, unconditional `{"status": "ok"}` | Database reachability (`SELECT 1`), schema-revision compatibility (§9/§14), required configuration presence (§34) |
| **External provider calls** | Never | Never (§14) |
| **Response on success** | `200 {"status": "ok"}` (unchanged) | `200` with a boolean/enum-shaped body (§19) |
| **Response on failure** | N/A — a process that can answer `/health` is, by definition, "alive" | `503`, with a machine-readable reason (`"schema_mismatch"` / `"database_unreachable"` / `"configuration_missing"`) — never a raw stack trace, never a connection string (§19) |
| **Used by** | A liveness probe / process supervisor deciding "should this process be restarted" | A load balancer / orchestrator / operator deciding "should traffic reach this instance" |

**Not implemented this increment** — this is the exact contract #26C must build.

---

## §16. Schema-mismatch response (§16 of the source prompt)

Four options were weighed:

- **Fail startup entirely** (crash the process) — rejected: makes a schema mismatch indistinguishable from a genuine code defect in process supervision/orchestrator logs, and is actively hostile to local development (a developer whose dev DB is one migration behind, exactly today's own incident, should get a clear, actionable, non-crashing signal, not an unlaunchable app they must debug via crash logs).
- **Remain alive but unready** — **chosen.** The process starts normally (`/health` stays `200 ok` — the process genuinely is alive), but `/readiness` reports `503` with the specific reason. This is the standard, well-understood shape for exactly this situation (a liveness/readiness split exists in essentially every real orchestration platform precisely to make this distinction possible) and is the only option that serves **both** the production case (an orchestrator/load balancer withholds traffic from an unready instance automatically, without ever needing to kill and restart it — a schema mismatch is not fixed by a restart) **and** the local-development case (a developer sees a clear, queryable, non-crashing "not ready: schema_mismatch" signal instead of a mysterious 500 deep inside one feature, exactly the improvement #26A's own incident needed).
- **Serve limited routes** — rejected as unnecessary complexity for V1: this project has no per-route criticality tiering today, and inventing one specifically to decide which routes are "safe" under a schema mismatch is speculative, unjustified scope — the correct mechanism is upstream (§15's readiness gate stops traffic from reaching *any* route of an unready instance once a real orchestrator exists), not a per-route allowlist inside the app itself.
- **Return 503 (from every route)** — this is effectively what "remain alive but unready" achieves once an orchestrator or load balancer honors `/readiness`; naming it as a fourth, distinct option would double-count it.

**Frozen: remain alive, report unready via `/readiness`, never crash-loop, never silently serve a broken route as if nothing were wrong.**

---

## §17. Frontend failure experience, audited (§17 of the source prompt)

Confirmed live and by source inspection (`api/useApiResource.ts`, and the #26A live reproduction of the Since Last Visit 500 itself): **the current frontend already degrades well.** Each Overview section fetches independently; a failed section renders its own `ErrorMessage` (a distinct `role="alert"` block with a Retry button) while every other section renders normally — directly observed live during #26A (the broken "Recent Economic Activity" card sat above a perfectly normal Current State/What Changed/Relate/Releases). **No frontend change is required by this document.** One real gap, named but not built: there is no *global* "the backend appears to be entirely unreachable" banner — if every section failed simultaneously (a true full-outage, not today's single-route incident), a user would see four to six independent, repetitive error+Retry blocks rather than one clear, unified message. **Not a blocker** — the current per-section behavior is honest and non-broken even in that case, just less polished; named as a LATER candidate, not required for #26C-F. **Frontend/backend deployment coupling is not needed**: `VITE_API_BASE_URL`'s existing build-time design already assumes and correctly supports independently-deployed frontend and backend origins (§40).

---

## §18. Code/schema version provenance — minimal design (§18 of the source prompt)

An operator (or an automated smoke test, §48/§49) must be able to determine, without reading source: the running application's own git SHA (or short version identifier), the Alembic revision that application version **expects**, and the Alembic revision the connected database **actually has**. **Minimal design: surface all three on `/readiness`'s own response body** (§15/§19) — no new endpoint is needed beyond the one already being built for readiness itself. The git SHA can be baked into the build artifact at build time (a build-time environment variable or a generated file, mirroring how `VITE_API_BASE_URL` is already resolved at frontend build time) — not designed further here, left to #26C's own implementation.

---

## §19. Public vs. operator visibility (§19 of the source prompt)

This project has **no authentication mechanism anywhere** (confirmed, `current-architecture.md`'s own explicit "Authentication/authorization — the API is unauthenticated" line, unchanged this whole session) — building an operator-only auth-gated diagnostics channel would itself be new, unjustified scope (a new authentication mechanism, explicitly out of bounds for this audit-only increment, and arguably premature before this project has any real auth story at all). **Frozen: `/readiness` may be public, mirroring the rest of this API's own existing no-auth posture — but its response body is restricted to boolean/enum-shaped facts and coarse identifiers only:** `ready: true|false`, a `reason` enum (`schema_mismatch`/`database_unreachable`/`configuration_missing`), the application's own git SHA, and the expected/actual Alembic revision **strings** (short hex identifiers — schema version labels, not sensitive data on their own, and already visible to anyone with `git log` access to this public-by-convention-in-this-project repository). **Never** exposed anywhere in an HTTP response: a stack trace, a connection string, a raw exception message, any environment variable's actual value, row counts, or any economic data. This mirrors `app/operations/run_maintenance.py`'s own already-established "never prints an API key, a database URL, a raw provider response body, or a stack trace" discipline, applied here to a new HTTP surface rather than CLI stdout. Detailed, fuller diagnostics belong only in platform/process logs (§36), never in any response body, for as long as no operator-only channel exists.

---

## §20. Maintenance worker compatibility (§20 of the source prompt)

**Yes — the worker must perform the identical schema-compatibility preflight the web readiness check performs, before doing any work.** `app/operations/run_maintenance.py` already has the exact right shape for this: it already checks `settings.fred_api_key`/`settings.database_url` presence and exits `2` with a safe, non-leaking message before doing anything else (§23) — schema-compatibility becomes a **third** preflight check of the identical shape, reusing the same small compatibility-check function `/readiness` uses (§14), not a second, independently-written check. **Frozen: on a schema mismatch, `run_maintenance`/`process_release` print the same class of safe "Operational failure: database schema is not compatible with this application version" message and exit non-zero using each CLI's own already-established convention** — the existing, already-frozen "fatal/configuration failure" exit code, not a new one; a schema-incompatible worker run is conceptually identical to a missing-configuration run (§13/§39 of `automated-economic-maintenance-v1.md`'s own already-frozen exit-code contract), never allowed to proceed and produce a raw, undiagnosed `SQLAlchemyError` traceback mid-sweep the way it silently would today. **Genuine factual correction, made during #26C's own implementation, recorded here rather than silently overridden:** this paragraph's own first-drafted wording named exit code `2` uniformly for both CLIs; direct inspection of `process_release.py` during implementation found it has never had a distinct fatal/configuration exit code — every operational failure there has always returned `1`, unlike `run_maintenance.py`'s own three-value (`0`/`1`/`2`) convention. #26C implements the preflight for both CLIs exactly as this section requires, with each CLI reusing its own already-established exit code for the new case (`run_maintenance.py` → `2`, `process_release.py` → `1`) rather than inventing a new value for one file inconsistent with its own 100% pre-existing convention.

---

## §21. Scheduler architecture — reconfirmed (§21 of the source prompt)

**ADR-024's scheduler/orchestrator separation is reconfirmed correct, unchanged, not revisited.** Re-verified directly against current code this turn (`app/services/maintenance.py`, `app/operations/run_maintenance.py`) rather than assumed from the ADR's own text: the orchestrator remains a pure, bounded, one-shot sweep with zero self-scheduling logic; `app/main.py` has zero awareness of maintenance (confirmed, §5's own re-read of `main.py` — no import, no reference). **Do not move scheduling into FastAPI for deployment convenience** — §10's own reasoning against in-process schema mutation applies with equal force to an in-process scheduler: it would couple maintenance's lifecycle to the web process's own restart/redeploy cadence and reintroduce, self-inflicted, the exact multi-instance concurrency risk ADR-024 already named and rejected once.

---

## §22. Scheduler options — deployment-neutral, none chosen (§22 of the source prompt)

| Option | Deployment-neutral? | Notes |
|---|---|---|
| Platform cron (a PaaS's own scheduled-task feature) | Yes, once a platform is chosen (§42) | The likely eventual choice; not selectable before §42 |
| GitHub Actions scheduled workflow (`on: schedule`) | Yes — works **today**, with zero hosting decision required | Genuinely available immediately: it only needs network access to the production database and `FRED_API_KEY`, both already externally-reachable secrets a CI secret store can hold; does not require choosing a hosting platform first |
| System cron (on a persistent VM/host) | Yes, if a persistent host exists | Only applicable once a hosting shape with a persistent, always-on machine is chosen |
| Dedicated cloud scheduler service invoking a job | Yes, once a platform is chosen | Same category as platform cron |

**No vendor is chosen here, per instruction.** Named explicitly: **GitHub Actions' own scheduled-workflow trigger is the one option that requires zero hosting decision and could, in principle, activate the scheduler before any hosting platform is chosen at all** — worth flagging to whichever future increment (#26D/#26E) makes the concrete choice, not decided here. **Reconfirmed, per §46 of the source prompt: processing must never be exposed as a public, unauthenticated HTTP action** — every option above invokes the existing CLI entry point directly (a scheduled job running a command), never a public route; this constraint is unaffected by which option is eventually chosen.

---

## §23. Maintenance command production-readiness audit (§23 of the source prompt)

Audited fresh against the actual file (`app/operations/run_maintenance.py`), not assumed from #25B/#25C's own contract prose:

| Property | Status |
|---|---|
| Exit codes | **Already production-shaped**: `0` clean, `1` completed-with-failures (`failed_count > 0`), `2` fatal/configuration failure — an external scheduler can already distinguish all three |
| Logging | `_print_summary` prints a safe, structured summary (sweep id, started/finished, due/processed/skipped/failed counts, any database-layer-failure occurrence ids) — no secret ever printed, confirmed by direct read |
| Bounded work | Yes — one sweep, terminates, never loops or sleeps (confirmed, module docstring and `main()` body) |
| Locking | Occurrence-level advisory lock via the shared `try_acquire_and_process_occurrence` (ADR-024) — already correct, unmodified by this document |
| Failure semantics | `OperationalError`/`SQLAlchemyError` around the whole sweep → exit `2`, safe message, no traceback; a schema-incompatible database currently falls into this same generic bucket with an unhelpfully generic message (§20's own one small, precise addition) |
| Configuration | Already checks `fred_api_key`/`database_url` presence before doing anything, exits `2` if either is missing |
| Timeout behavior | No explicit timeout exists — a sweep bounds itself naturally by the size of the due-work set (small, per `automated-economic-maintenance-v1.md` §49's own estimate), not by a wall-clock cutoff; not flagged as a gap at current, small data volume |

**Verdict: already substantially production-ready.** The **one** prerequisite this document adds is §20's schema-compatibility preflight — a small, additive third check reusing the existing exit-code-2 pattern, not a redesign.

---

## §24. Scheduler overlap (§24 of the source prompt)

**Two whole sweeps CAN overlap in wall-clock time; this is acceptable and requires no new lock.** Traced precisely: each sweep's own due-work discovery is an independent read; when two overlapping sweeps both attempt to process the *same* occurrence, the existing, unmodified occurrence-level advisory lock (`pg_try_advisory_xact_lock`, ADR-024) ensures the second attempt simply skips that occurrence (`skipped_lock_count`, already a field on `MaintenanceSweepOutcome`, confirmed by direct read of `run_maintenance.py`'s own `_print_summary`) rather than double-processing it. **No sweep-level lock is added** — directly reusing #25B's own already-reasoned rejection of row-level claiming for the identical reason (unjustified complexity for a single-scheduler-invoking-a-single-script deployment shape); a sweep-level lock would only earn its cost once genuinely distributed, multiple-scheduler concurrency becomes real, which it is not today.

---

## §25. Maintenance cadence — reconfirmed (§25 of the source prompt)

**Unchanged from `automated-economic-maintenance-v1.md` §15: an hourly-order sweep interval, operator-tunable, not empirically pretended-precise.** Nothing in this increment's own findings changes that reasoning — economic releases remain monthly-or-slower, the release calendar remains date-only (no time-of-day precision to poll against, §6 of the same document), and inventing a faster cadence would optimize for a responsiveness the underlying data cannot support.

---

## §26. Maintenance failure observability — minimum V1 (§26 of the source prompt)

**"Who watches the watcher" requires evidence independent of any individual sweep's own success, because a scheduler that stops firing entirely leaves zero rows anywhere** (`automated-economic-maintenance-v1.md` §52, reconfirmed unchanged). Two complementary mechanisms, both minimum-V1, neither requiring a hosting decision first:

1. **Platform job-failure alerting** — once a real scheduler mechanism is chosen (§22), use whatever failure-notification the scheduling platform itself already offers (a failed GitHub Actions run already emails/notifies by default; a PaaS's own scheduled-task feature typically offers the same) — free, requires no new code.
2. **A sweep-heartbeat check** — a small, cheap, deployment-neutral query: "does a `MaintenanceSweep` row with `started_at` within the last `2 × expected_interval` exist?" Exposed as one more fact on `/readiness` (§15/§19, as a non-gating informational field, never itself causing a `503` — worker silence is a *maintenance* freshness concern, not a *request-serving* readiness concern, per §14's own separation) or as a tiny, separate operator-facing check. **Not built this increment** — the check's own shape is frozen; its implementation belongs to #26E.

---

## §27. User-facing maintenance truth — confirmed unaffected (§27 of the source prompt)

**No new product claim is required or introduced.** `since-last-visit-v1.md` §43/§64's own already-shipped, already-frozen "last checked: {time}" language remains the correct, complete, honest claim — this document adds *operational* reliability underneath it, it does not change what the product is permitted to *say*. "Up to date" remains permanently forbidden (`automated-economic-maintenance-v1.md` §27, restated, not re-litigated).

---

## §28. Database backups — minimum requirement, frozen (§28 of the source prompt)

**`RecordedMonitorResult` (#25D/#25E) is now a compounding, non-reconstructable historical asset** — its own ADR-025 says so explicitly ("Cost: ... a genuinely non-reproducible asset"; every row is proof of a real, past computation event no later recomputation can regenerate). **Frozen minimum for any environment invited users will touch:** automated daily backups, retained for at least 7 days (enough to recover from a slow-discovered issue, not merely an instant crash), stored independently of the primary database instance (never "a backup that lives on the same disk/volume as the thing it backs up"). No specific vendor mechanism is chosen — most managed PostgreSQL offerings provide this as a checkbox-level feature (§44), which is itself a reason to prefer managed hosting over self-hosting for the production database.

---

## §29. Restore readiness — minimum requirement, frozen (§29 of the source prompt)

**A backup that has never been restored is not a verified backup.** Frozen minimum: at least one full restore-to-a-scratch-database rehearsal, performed and confirmed successful, **before** private beta (§56) — not merely "backups are enabled," but "a restore was actually attempted and produced a working database." Recurring cadence (e.g., before each subsequent major schema change, or on a fixed calendar interval) is recommended but the exact cadence is left to whichever future increment operates the production environment, consistent with this project's own established "principle frozen, number left tunable" discipline (`automated-economic-maintenance-v1.md` §14's identical pattern, reused here).

---

## §30. Migration-specific backup policy (§30 of the source prompt)

**Every migration in the current chain is additive (§7) — none of them require a pre-migration backup on safety grounds alone** (a failed additive migration rolls back cleanly, §13; there is nothing destructive to protect against yet). **Frozen, forward-looking policy for whenever that changes:** any future migration that drops a column/table, renames anything, or performs a data transformation that cannot be trivially reconstructed from source data **must** be preceded by a fresh, verified backup/snapshot as an explicit, named pre-condition of running it — never assumed safe merely because prior migrations were.

---

## §31. Rollback philosophy — three concepts, kept explicitly separate (§31 of the source prompt)

- **Application rollback** (redeploy the prior build artifact): **always safe, always the first response to a bad deploy**, and — because of §32's own expand-first discipline — never requires a corresponding database change to be safe, as long as every migration remains additive-only in the sense §8 already established (old code simply never touches a new table/column it doesn't know about).
- **Database migration downgrade** (`alembic downgrade`): **NOT assumed safe as a routine production rollback mechanism, even though every `downgrade()` in the current chain is, in fact, safe today** (§7 confirms this for the *existing* chain specifically). The moment a future migration includes a genuine data transformation or a destructive change, its own `downgrade()` may be lossy, expensive, or outright impossible to make correct — the *general* philosophy must never depend on downgrade always being safe, even though today's specific chain happens to qualify.
- **Data rollback** (restoring from a backup, §28/§29): the **last resort**, reserved for genuine data corruption or an unrecoverable bad migration — never used as a routine "undo the last deploy" mechanism, because it necessarily loses any legitimate write that happened after the backup was taken.

**Frozen ordering of preference: application rollback first, always; database downgrade only when the specific migration's own downgrade is independently confirmed safe for the data actually present; data/backup restore only as a genuine last resort.**

---

## §32. Expand/contract — when V1's exact-equality policy must change (§32 of the source prompt)

Documented explicitly, per instruction, even though V1 does not need it yet: **the moment either (a) a future migration must remove or narrow something an old, still-serving application version depends on, or (b) more than one application version may legitimately run concurrently against one database (rolling deploys, blue-green, horizontal scaling with staggered restarts) — this project must move from single-migration, all-additive changes to genuine two-phase expand/contract migrations**: an *expand* migration adds the new shape alongside the old (new nullable column/table, dual-write if needed) and ships with application code that can operate against *either* shape; a later, separate *contract* migration removes the old shape only once no deployed application version depends on it any longer. At that point, §9's compatibility policy must also generalize from exact equality (Option A) to a genuine minimum-compatible-revision range (Option B), since two different, both-valid application versions may then need to tolerate two different, both-valid schema states simultaneously.

---

## §33. CORS / HTTPS / origins (§33 of the source prompt)

**CORS middleware is confirmed absent** (§5) — safe only because local development never crosses an origin boundary (§17). **Frozen requirement for any deployment where frontend and backend do not share an origin** (the default expectation, given `VITE_API_BASE_URL`'s own existing build-time-configurable design, §40): explicit `CORSMiddleware` configuration with a **narrow, explicit `allow_origins` allowlist containing exactly the deployed frontend's own origin(s)** — never `allow_origins=["*"]`. Lower-severity than it would be for a typical application (this API has no authentication and no user-specific state to leak — every response is already, today, safe to serve to any origin, per the standing "unauthenticated by design" posture), but wildcard CORS is still avoided on general hygiene grounds, not because a specific exploit is named here. **HTTPS is a hard, non-negotiable requirement for any private beta** (§56) — no implementation decision is needed here; virtually every modern managed-hosting option terminates TLS at the edge automatically once a domain is attached (§43), so this is a configuration/provider-selection matter for #26D, not a code change.

---

## §34. Environment configuration contract (§34 of the source prompt)

Variable **names only**, confirmed by direct inspection of `.env.example`/`app/core/config.py` (no value read, ever): `FRED_API_KEY`, `DATABASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL` (backend); `VITE_API_BASE_URL` (frontend build-time, via `frontend/.env.example`, not re-inspected for values this turn either); `BACKEND_PROXY_TARGET` (frontend **dev-only**, Node-side, never bundled into client JS — confirmed by `vite.config.ts`'s own comment).

**Current behavior: 100% lazy/optional, confirmed by direct read of `app/core/config.py`.** Nothing fails fast at import or process-start time — `DatabaseNotConfiguredError` is only ever raised on the *first actual database operation* (`app/db/session.py`'s own explicit, deliberate design, per its own docstring: "importing this module... never fails"). This is a reasonable, deliberate local-development convenience; it is also precisely why a misconfigured production deployment could start "successfully" (`/health` → `200 ok`) while being unable to serve any real request — exactly the gap `/readiness` (§14/§15) exists to close.

**Frozen fail-fast policy, layered on top of the existing lazy design rather than replacing it:** `DATABASE_URL` absence must cause `/readiness` to report `configuration_missing` (never crash the process, per §16); `FRED_API_KEY` absence is acceptable for the **web** process (every read-only monitor/history/Overview route remains fully servable without it) but must remain a hard, already-correctly-enforced precondition for the **maintenance worker** specifically (already true, §23 — unchanged); `OPENAI_API_KEY`/`OPENAI_MODEL` remain fully optional everywhere, unchanged — an unset value already, correctly, just disables AI features rather than erroring (`app/core/config.py`'s own explicit comment, re-confirmed this turn).

---

## §35. Secret management — expectation only, no values touched (§35 of the source prompt)

No committed `.env` (confirmed: `.env` is present locally but is not a tracked file — `git status --porcelain` at baseline shows it absent from version control, consistent with a standard `.gitignore` entry). **Frozen expectation for production: secret values are injected via the hosting platform's own environment/secret-store mechanism** (every mainstream PaaS/container platform provides one) — **never** a committed file, never a value hardcoded in a Dockerfile/CI config/deployment manifest once those exist (#26D). No secret value was read, displayed, or required to reach any conclusion in this document — every finding above needed only variable **names**, matching `app/operations/process_release.py`'s/`run_maintenance.py`'s own already-established discipline for referencing configuration.

---

## §36. Logging — minimum required before beta (§36 of the source prompt)

Current state, confirmed by full-tree search: **no structured logging exists anywhere** beyond uvicorn's own default access-log lines and `run_maintenance.py`'s own safe, already-adequate `_print_summary` stdout output. **No correlation currently exists** between a web request, a maintenance sweep, and a release-check failure — an operator investigating an incident today has only timestamps to cross-reference by hand (exactly how #26A's own incident was actually root-caused this session — by hand, via `alembic current`/`\dt`/`curl`, not via any log correlation). **Minimum required before private beta, frozen:** structured (one-line, machine-parseable) log output from the maintenance CLI (extending, not replacing, `_print_summary`'s own already-safe shape) plus the web process's own existing default access logs — sufficient at private-beta's own expected traffic volume for a human operator to correlate events by timestamp alone. **A full request-correlation-ID system is explicitly NOT required for V1** — named as a LATER item, revisit once real, concurrent, multi-user traffic volume makes timestamp-only correlation unreliable (§57).

---

## §37. Error reporting — evaluated, not required for private beta (§37 of the source prompt)

**Not required before private beta.** At private-beta's own expected scale (a small, invited user count, §56), platform logs plus the tiny user count are sufficient for a human operator to notice and diagnose a problem by direct inspection — exactly the same scale-appropriate reasoning this project has already applied elsewhere (e.g. `automated-economic-maintenance-v1.md` §49's own "small, curated, low-volume" provider-load estimate). A dedicated error-reporting service (Sentry-class) is a reasonable, cheap future addition, **not** a private-beta gate — named explicitly as a public-beta-tier item (§57), not silently dropped.

---

## §38. Monitoring — minimum private-beta scope, not enterprise observability (§38 of the source prompt)

**Minimum, frozen:** (1) basic web availability, via whatever uptime-check feature the eventual hosting platform provides pointed at `/readiness` (not `/health` — a process that is merely "alive" but schema-incompatible should register as down for this purpose); (2) the sweep-heartbeat fact (§26); (3) periodic manual review of `maintenance_sweeps`/`release_check_runs` — genuinely sufficient, given expected private-beta traffic and change volume, without needing a dashboard, metrics pipeline, or tracing system. **Explicitly not designed here:** any enterprise-grade observability stack (metrics aggregation, distributed tracing, SLO dashboards) — unjustified scope at this stage, named as a public-beta-or-later concern (§57).

---

## §39. Operator alerts — minimum set, frozen (§39 of the source prompt)

Distinct from any future *user*-facing economic alert (out of scope, unrelated, never built by this document). Minimum operator-notification set, frozen: a migration that fails during deployment (§13 — the deploy pipeline itself should fail loudly, visible to whoever runs it); the scheduler/maintenance job failing to run at all within its own expected interval (§26); the maintenance CLI exiting `2` (fatal/configuration failure, already a distinct, already-meaningful signal, §23); a sustained `/readiness` failure (the instance has been unready for longer than one deploy cycle reasonably takes). **No alerting mechanism (email/Slack/paging) is built this increment** — these are the semantics a future, separate alerting integration (#26E or later) should wire up, mirroring `automated-economic-maintenance-v1.md` §63's own identical "semantics frozen, mechanism deferred" precedent.

---

## §40. Frontend deployment (§40 of the source prompt)

Build artifact: `vite build` → static `dist/` (confirmed this turn, clean build, `index.html` + hashed JS/CSS assets, ~360KB JS gzipped to ~103KB — genuinely small, no unusual bundle-size concern). **API-base coupling is already correctly designed for independent deployment**: `VITE_API_BASE_URL`, resolved at **build time** (`import.meta.env.VITE_API_BASE_URL ?? ""`), lets a production build point at a separately-hosted backend origin without any code change — the empty-string fallback is exactly what makes local dev's own same-origin Vite-proxy setup (§5/§17) work without needing the variable set at all locally. **No further design decision is required here** — the existing mechanism is already sufficient; #26D's own job is choosing where the static `dist/` output is actually hosted (a static host/CDN, not designed further here) and wiring the build-time variable to the real backend URL.

---

## §41. Backend deployment (§41 of the source prompt)

Runtime command, confirmed unchanged and already correct: `uvicorn app.main:app` (or an equivalent ASGI-server invocation) — a single-process, synchronous-database (ADR-007), synchronous-HTTP-client (ADR-003) application; nothing about this document's own findings requires moving to multiple worker processes or an async rewrite before private beta. **No vendor/process-manager is selected here**, per instruction — left to #26D once a hosting platform is chosen (§42).

---

## §42. Hosting decision — kept platform-neutral for #26C (§42 of the source prompt)

**No.** Nothing in this repository's current requirements forces a hosting choice now, and choosing prematurely would risk freezing an infrastructure decision ahead of the operational *contract* this document exists to freeze first (the same "design before implementation, freeze the contract before committing to a specific mechanism" discipline this whole project has applied at every prior persistence/operational decision this session). **If/when a future increment does choose one, the selection criteria this document's own findings already imply:** managed PostgreSQL with automated backups (§28/§44); a way to run a one-shot scheduled job without requiring a persistent always-on process (§22); environment/secret injection without committing values (§35); and either a native container/build pipeline or straightforward compatibility with one (§61's own #26D). **#26C remains fully platform-neutral** — everything it freezes (compatibility policy, readiness semantics, worker preflight) works identically regardless of which platform is eventually chosen, mirroring `automated-economic-maintenance-v1.md` §62's own identical "orchestrator logic identical everywhere, only the scheduler varies" precedent, generalized here to the whole deployment model.

---

## §43. Domain / TLS (§43 of the source prompt)

**HTTPS is a frozen, hard requirement for private beta** (§56) — restated from §33, not re-litigated. No domain is purchased or configured by this document; this is a procurement/provider-configuration step for #26D, not an architecture decision.

---

## §44. Production database requirements (§44 of the source prompt)

**Managed PostgreSQL is preferred over self-hosting**, evaluated against this project's own actual operating capacity (a single developer, §7 of ADR-008) rather than assumed: self-hosting would require this project to independently solve backups (§28), TLS (§33), and patching/availability — problems essentially every managed offering solves as a checkbox feature. **Frozen requirements, vendor-neutral:** automated backups with restore capability (§28/§29); TLS for the database connection itself (distinct from, and in addition to, the application's own public-facing HTTPS, §43); a reasonable, published connection limit compatible with this application's own modest connection-pool footprint (§45); and a connection/role with sufficient privilege to run Alembic migrations (§46). No vendor is named.

---

## §45. Connection pooling (§45 of the source prompt)

Audited directly, `app/db/session.py`: `create_engine(settings.database_url, pool_pre_ping=True)` — **no explicit `pool_size`/`max_overflow`/`pool_timeout`**, meaning SQLAlchemy's own defaults apply (`pool_size=5`, `max_overflow=10` → up to 15 connections per process). **For private beta, a single application instance: not a blocker** — 15 connections is comfortably within essentially every managed Postgres tier's own default connection limit. **Becomes a real concern only once the instance count exceeds one** (horizontal scaling would multiply this per-instance ceiling directly against the database's own total connection cap) — named explicitly as a **LATER** optimization, revisit at the same trigger point §32/§57 already name (real multi-instance deployment), not before.

---

## §46. Migration permissions (§46 of the source prompt)

Evaluated: a dedicated migration-only database role (DDL-capable) separate from the application's own runtime role (DML-only, no `CREATE`/`ALTER`/`DROP` grants) is real, standard, least-privilege hardening. **Decision: not required for private beta — overengineering at this project's current, single-developer, single-environment stage** (mirroring ADR-008's own explicit "not a concern at this project's current single-developer, single-branch stage" reasoning for a directly analogous question, migration-conflict tooling). **Named explicitly as a public-beta-or-later hardening step** (§57), not silently dropped: once real external users and a real production incident surface exist, narrowing the runtime role's own privileges so a compromised or buggy web process cannot alter schema becomes a genuinely justified, not speculative, improvement.

---

## §47. Normal release process — operator steps (§47 of the source prompt)

Goal: boring, repeatable, verifiable. Frozen steps (mirrors §12's own pipeline, restated as an operator's own checklist rather than a system's own phase list):

1. Confirm the target environment's current Alembic revision (`alembic current` against that environment's `DATABASE_URL`).
2. Confirm the new code's own expected head (`alembic heads` against the same codebase).
3. If they already match, skip to step 6 (no migration needed this release).
4. Apply the migration (`alembic upgrade head`) against the target database, **before** deploying any new code.
5. Re-confirm the target database's revision now equals the expected head (§12 step 5) — abort and investigate if not, never proceed.
6. Deploy the new application code.
7. Confirm `/readiness` reports `ready: true` on the newly-deployed instance(s) before considering the release complete.
8. Run the smoke suite (§48).

---

## §48. Post-deploy smoke test — minimum suite, frozen (§48 of the source prompt)

Never mutates economic state (no `POST`, no `/sync`, no processing trigger). Minimum suite: `GET /health` → `200`; `GET /readiness` → `200, ready: true`; `GET /api/v1/monitors/inflation` → `200`; `GET /api/v1/monitors/labor` → `200`; `GET /api/v1/since-last-visit` → `200` (the exact route #26A's own incident broke — deliberately included by name, not merely implied by "Overview APIs"); `GET /api/v1/releases` (or the equivalent upcoming/recent releases route) → `200`. **A maintenance dry/controlled verification** is limited to confirming the CLI's own exit code and summary output against the now-migrated database (`python -m app.operations.run_maintenance`, expect exit `0` or `1`, never `2`) — never run in a way that issues real, uncontrolled FRED calls as part of an automated smoke gate beyond what a genuinely due sweep would already do in the ordinary course of operation.

---

## §49. Migration verification — proving expected vs. actual match after deploy (§49 of the source prompt)

**Frozen: step 7 of §47/§12's own pipeline (re-reading the database's revision and comparing it to the code's own expected head) is itself the migration-verification step** — no separate mechanism is needed beyond what `/readiness`'s own compatibility check (§14/§15) already computes on every request. Post-deploy verification is therefore just "call `/readiness` and confirm `ready: true`," reusing the same function the running application itself continuously relies on, never a second, independently-written check that could drift from the first.

---

## §50. Current dev database remediation — specified, NOT executed (§50 of the source prompt)

**Not fixed in this increment, per explicit instruction.** The exact, safe, minimal remediation, for whoever performs it later:

1. `pg_dump` the current dev database first, only if its current data is considered worth preserving (a local dev database with synthetic/test-shaped data likely is not — operator judgment, not this document's own call).
2. `alembic current` — confirm still `09f4c0959e9f` (unchanged from §6).
3. `alembic upgrade head` — applies exactly one migration (`f5420059a092`, purely additive, §7), creating `recorded_monitor_results` and its two indexes.
4. `alembic current` — confirm now `f5420059a092`.
5. `psql ... \dt` — confirm `recorded_monitor_results` now exists.
6. Re-run the exact failing request (`curl http://localhost:8000/api/v1/since-last-visit`) — confirm `200`, not `500`.

This mirrors, almost exactly, the resolution this project already performed once before for the same failure class (§4 — the `ENGINEERING_JOURNAL.md:7071-7096` precedent: "With the user's explicit approval, `alembic upgrade head` was run against the dev database... no new migration written, no migration file touched"). **Not executed here** — left for the user's own explicit approval, exactly as that precedent required it the first time.

---

## §51. Production data seeding / bootstrap (§51 of the source prompt)

**A genuinely useful, previously-unnoticed property, confirmed by §7's own migration audit: the release *catalog* bootstrap is already fully bundled into the ordinary migration chain itself** — `fbbe6b1ab8d9`/`cd476d227f99`/`09f4c0959e9f` seed the six curated releases and their series mappings as data migrations, meaning `alembic upgrade head` alone already leaves a fresh database with a complete, correct release catalog — no separate seeding script or workflow is needed for that part. **What migrations do NOT provide, and a fresh production database genuinely needs before it is useful:** actual `EconomicObservation` rows (raw series data, requires a real FRED-reachable sync — either `POST /series/{id}/sync` per curated series, or the release-processing pipeline's own first run) and at least one successful `process_occurrence`/`run_maintenance` pass per monitor to move Inflation/Labor out of a data-less state. **No implementation is built here** — the workflow is: migrate (seeds catalog) → sync each curated series once → run one manual (not yet scheduled) processing pass per relevant occurrence → verify monitors return real states (§52) → **only then** activate the recurring scheduler (§53).

---

## §52. Cold-start product experience (§52 of the source prompt)

**Before initial sync/processing, monitors will honestly show `INSUFFICIENT_DATA`/empty states** — never fabricated, per this project's own standing, tested `INSUFFICIENT_DATA` discipline (confirmed live during #26A: the current dev database's own Labor monitor already demonstrates exactly this honest, non-broken cold/data-scarce presentation). **This is correct behavior, not a bug**, but it is **not an acceptable state to invite beta users into** — a stranger's first visit to a genuinely cold-started product would see "Insufficient data" everywhere and reasonably conclude the product doesn't work. **Frozen: bootstrap (§51) must complete, and be verified to have produced real, non-`INSUFFICIENT_DATA` states for both monitors, before any beta user is invited** — named explicitly as a private-beta go/no-go gate item (§56).

---

## §53. Automation start order (§53 of the source prompt)

Frozen, exact: **migrate → deploy (web instance ready but not yet inviting real usage) → bootstrap (§51: sync + one manual processing pass per relevant occurrence) → verify (§52/§54) → activate the recurring scheduler.** Recorded history (`RecordedMonitorResult`, #25E) begins accumulating the moment the first qualifying `process_occurrence` call runs after deployment (`recorded-state-history-v1.md` §50, reused verbatim) — meaning the manual bootstrap processing pass in this sequence is itself already the first recorded-history-producing event, genuinely starting "before automated processing" exactly as the source prompt's own instruction asks, with zero special-casing required to make that true.

---

## §54. Scheduler activation proof — acceptance criteria, frozen (§54 of the source prompt)

**Not "the code exists and passed tests." Acceptance requires observing, against the real, deployed `maintenance_sweeps` table:** at least a handful of consecutive `MaintenanceSweep` rows (recommended: enough to span 48-72 hours of real, continuous operation, not a single manual invocation) each with `finished_at IS NOT NULL`, `status` indicating a clean completion, and due/processed/failed counts that are individually sane (not, for example, `due_count` silently always `0` in a way that would suggest the due-work query itself is broken rather than genuinely finding nothing due). Only once this has been directly observed does §55's own claim become truthful.

---

## §55. "Automatically maintained" claim — exact truth threshold (§55 of the source prompt)

**Code existence is explicitly insufficient** — restated and sharpened by this document's own §4 finding: the *exact* automation this project already built once before (release processing, §4's precedent) has already, once, silently gone unmigrated in a real environment despite passing every test — proof that "the code exists, the tests pass" is not equivalent to "this is genuinely running against this environment right now." **The claim "Economic Intelligence is automatically checked against mapped economic releases on a regular schedule" (`automated-economic-maintenance-v1.md` §66's own already-frozen, safest phrasing — reused verbatim, not restated more strongly) may be made truthfully only once §54's own live-observation criterion has actually been satisfied in the specific environment being described** — never merely because the orchestrator/scheduler code has shipped and passed CI.

---

## §56. Private beta reliability bar — exact, measurable go/no-go criteria (§56 of the source prompt)

All of the following, ANDed — none optional, none satisfied by "the code is written":

1. Target database's Alembic revision equals the deployed application's own expected head (§9), verified via `/readiness` reporting `ready: true`, not by developer assertion.
2. Zero known `500`s anywhere in the post-deploy smoke suite (§48), run and passed on the actual deployed environment.
3. Scheduler activation proof satisfied (§54) — a real, observed, multi-sweep operating history, not a single manual run.
4. Automated backups enabled AND at least one successful restore rehearsal completed (§28/§29).
5. `/health` and `/readiness` both implemented and both correctly distinguishing "alive" from "ready" (§15).
6. Operator alerting for at least the minimum set (§39) wired to *something* a human will actually see (even a plain email, if that's all that exists yet — the mechanism can be minimal, but silence is not acceptable).
7. Frontend and backend both deployed, reachable over HTTPS, and correctly configured for cross-origin operation if they do not share an origin (§33/§40).
8. Bootstrap complete and verified (§51/§52) — both monitors showing real, non-`INSUFFICIENT_DATA` states before any invited user's first visit.
9. This document's own migration-failure-aborts-deployment behavior (§13) has been exercised at least once in a non-production environment (a deliberate, controlled test of what happens when a migration fails) — not merely designed on paper.
10. The current dev-database incident (§1/§50) has been remediated in whichever specific environment is being promoted to "private beta," with the fix verified by re-running the exact previously-failing request (§50 step 6).

---

## §57. Public beta — distinguished from private, not overbuilt now (§57 of the source prompt)

Briefly, added on top of §56, not designed in full: real (not manual/spot-check) monitoring and error reporting (§37/§38, deferred from private beta specifically because a small, known user count makes manual inspection sufficient — a larger, unknown public user base does not); request-correlation logging (§36, deferred from private beta for the same reason); least-privilege migration-vs-runtime database roles (§46); genuine readiness for the connection-pooling and expand/contract concerns named as "revisit when multi-instance" (§32/§45), since public beta is the first point multi-instance scaling becomes plausible; a considered CORS/rate-limiting posture appropriate to unauthenticated public traffic at real volume (§33, revisited — not rewritten — once real scale exists). **Not designed further here** — named to distinguish the tier, not to freeze its own contract prematurely.

---

## §58. Failure drills — minimum set before private beta (§58 of the source prompt)

1. **Kill the database mid-request** — confirm `/readiness` correctly flips to `503` and in-flight/new requests fail cleanly (a mapped infrastructure error, per this project's own existing, tested `OperationalError`→503 convention across every route — unchanged, just newly also reflected in `/readiness`), never a raw, unhandled traceback.
2. **Deliberately point the application at a schema-behind database** — literally reproduce this increment's own #26A incident on purpose, in a non-production environment, and confirm the **new** readiness/preflight mechanism (§14/§20) catches it and reports `schema_mismatch` **before** any user-facing request fails, rather than after, as happened for real.
3. **Kill FRED reachability** — confirm `/readiness` is completely unaffected (per §14's own "readiness must not call an external provider" rule) while `run_maintenance`/`process_release` correctly report `PARTIAL_FAILURE`/`FAILED_PROVIDER`, unchanged from #25B's own already-tested behavior.
4. **Stop the scheduler entirely for a period spanning the heartbeat threshold** — confirm §26's own sweep-heartbeat mechanism actually notices and surfaces it, rather than silently reading as "no work due."

---

## §59. Reliability test matrix — frozen for #26C+ (§59 of the source prompt)

| # | Test |
|---|---|
| 1 | Schema exact match → compatibility check reports compatible |
| 2 | Schema one revision behind → compatibility check reports `schema_mismatch` (the literal #26A reproduction, §58.2) |
| 3 | Schema ahead of the app's own expected head (a newer DB than this app version knows about) → reports incompatible under V1's exact-equality policy (§9), not silently treated as fine |
| 4 | Database completely unavailable → `/readiness` reports `database_unreachable`, never hangs, never a raw exception |
| 5 | A successful migration run → target revision matches expected head afterward |
| 6 | A failing migration (simulated against a disposable database) → deployment pipeline aborts, prior application version keeps serving (§13) |
| 7 | Migration idempotency — running `alembic upgrade head` twice in a row against an already-current database is a safe no-op |
| 8 | Web readiness — `/readiness` returns `200 ready:true` only when every one of §14's conditions genuinely holds |
| 9 | Worker compatibility — `run_maintenance`/`process_release` exit non-zero (each CLI's own established convention, §20) with a safe message on a schema mismatch, never proceed |
| 10 | `/health` is independent of database state — remains `200 ok` even while `/readiness` reports `503` (proves the two are genuinely decoupled, not accidentally sharing an implementation) |
| 11 | `/readiness`'s database dependency — confirmed to actually perform a live check, not a cached/stale one |
| 12 | `/readiness` never calls FRED/any external provider — a structural/architecture guard (§60), not just a behavioral test |
| 13 | Deployment preflight — the pipeline's own step-3 compatibility check correctly computes "already at head, skip migration" vs. "migration needed" |
| 14 | Post-migration verification — step 5 of §12 correctly detects and aborts on a migration that silently failed to reach the expected revision |
| 15 | A genuinely fresh database, migrated from zero (`alembic upgrade head` from an empty database) reaches the identical end schema as any other environment — a real round-trip test, not assumed |
| 16 | Upgrade from the specific, real previous revision (`09f4c0959e9f` → `f5420059a092`) — the literal migration this incident needed, exercised directly, not only "from zero" |
| 17 | Downgrade/upgrade round-trip, for every migration in the chain where downgrade is expected to be safe (all of them today, §7) |
| 18 | Scheduler command (`run_maintenance`) success/failure exit codes — already covered by #25C's own test matrix; reconfirmed here specifically for the **new** schema-mismatch case (exit `2`, §20) |
| 19 | Maintenance heartbeat — a stale/missing recent `MaintenanceSweep` row is correctly distinguishable from "sweep found nothing due" (§26) |
| 20 | No secret leakage — `/readiness`'s response body, and every new log line, contain no connection string, no API key, no raw exception text (a grep-level guard, mirroring `run_maintenance.py`'s own already-established discipline) |

---

## §60. Architecture guards — frozen for #26C+ (§60 of the source prompt)

- Web startup (`app/main.py`, any FastAPI startup event) **never** calls `alembic upgrade`/`command.upgrade`/any DDL-issuing function — a structural, AST/import-level guard, not merely a behavioral test (§10).
- No route ever reports `ready: true` while the schema-compatibility check itself has not genuinely run for that specific request/instance-state — never a cached-true-forever value.
- The maintenance worker's own entry points (`process_release.py`/`run_maintenance.py`) cannot reach `ReleaseProcessingService`/`MaintenanceOrchestrator` without the schema-compatibility preflight (§20) having run first — a structural call-order guard, mirroring ADR-024's own existing `TestOccurrenceLockingIsStructural` precedent applied to a new precondition.
- `/readiness`'s own implementation imports no FRED client, no `app.clients.fred` module at all — a structural guard proving §14's "never calls an external provider" rule, not just a behavioral one.
- No migration file, and no migration-tooling module, imports anything from `app.services.ai`/`app.clients.openai` or any AI/LLM dependency — mirrors every prior increment's own established AI-boundary guard, applied to the one area of the codebase (migrations) that has never needed it stated explicitly before.
- No migration file, deployment script, or CI configuration (once #26D exists) ever contains a literal secret value — enforced by review discipline today; a future automated secret-scan is a reasonable #26D addition, not designed further here.
- The maintenance orchestrator remains external, one-shot, and never self-schedules — ADR-024's own existing guard (`TestNoInProcessScheduler`), reconfirmed still required and unmodified by this document.
- No public, unauthenticated HTTP route triggers release *processing* — ADR-024's own existing guard (`TestNoPublicMaintenanceMutationEndpoint`), reconfirmed unmodified; `/readiness` itself performs no mutation of any kind, so its own public exposure (§19) does not weaken this guard.
- No frontend file constructs, calls, or references an Alembic migration, a database connection string, or any deployment/CI configuration — migrations and deployment remain exclusively a backend/operations concern, mirroring this project's own repeated, already-established frontend/backend boundary discipline.

---

## §61. Implementation split (§61 of the source prompt)

**Chosen, in this exact order — each increment's own scope kept intentionally small, mirroring this project's own established "one dedicated contract per persistence/operational decision" discipline:**

1. **#26C — Schema Compatibility + Readiness.** `/readiness` route; the compatibility-check function (§9/§14) shared by both the web route and the worker preflight (§20); version-provenance fields (§18/§19); the reliability test matrix items directly testable without a real deployment pipeline (§59.1-12); the architecture guards directly enforceable today (§60, most of them). **No Dockerfile, no CI, no hosting decision.**
2. **#26D — Deployment Packaging + Migration Release Process.** A Dockerfile (or equivalent build artifact definition); a CI pipeline implementing §12's exact phase ordering, including the migration-preflight/apply/verify steps (§12 steps 3-5) and the post-deploy smoke suite (§48); secret-injection wiring (§35) against whatever hosting platform is chosen (§42, decided *within* this increment, not before it, now that the operational contract is frozen); CORS configuration (§33) for the real, deployed cross-origin shape.
3. **#26E — Maintenance Scheduler Activation + Operator Observability.** Choosing and wiring an actual scheduler mechanism (§22); structured maintenance logging (§36); the sweep-heartbeat check (§26); minimum operator alerting (§39) wired to a real notification channel.
4. **#26F — Production Bootstrap + Reliability Verification.** The cold-start bootstrap workflow (§51/§52) executed for real; backup/restore rehearsal (§28/§29); the failure drills (§58); scheduler activation proof observed live (§54); final private-beta go/no-go checklist (§56) executed and signed off.

**Rejected alternative: one large #26C covering all four.** Rejected for the same reason this project has rejected it every prior time the question has come up this session (#22A→B, #23A→B→C, #24A→B→C→D, #25B→C, #25D→E, #25F→G→H): each of the four phases above has its own, independently-verifiable done-condition, and bundling them risks the same "too large to verify cleanly" failure mode this project has consistently avoided elsewhere.

---

## §62. Artifact

`docs/product/production-reliability-deployment-v1.md` — this document. `docs/architecture/current-architecture.md`/`request-flows.md`/`ENGINEERING_JOURNAL.md` **not updated**, per explicit instruction — this is a contract freeze, not an implementation record.

---

## §63. GO / STOP checklist

| # | Item | Status |
|---|---|---|
| 1 | Why the live 500 happened | ✅ §1/§6 |
| 2 | Why tests didn't prevent it | ✅ §11 (below) |
| 3 | Schema compatibility rule | ✅ §8/§9 |
| 4 | Who applies migrations | ✅ §11/§47 |
| 5 | When migrations run | ✅ §12/§13 |
| 6 | Whether web startup mutates schema | ✅ §10 — NO |
| 7 | What happens on migration failure | ✅ §13 |
| 8 | Health semantics | ✅ §15 |
| 9 | Readiness semantics | ✅ §14/§15 |
| 10 | Schema mismatch behavior | ✅ §16 |
| 11 | Worker compatibility behavior | ✅ §20 |
| 12 | Scheduler architecture | ✅ §21 |
| 13 | Maintenance overlap | ✅ §24 |
| 14 | Maintenance cadence | ✅ §25 |
| 15 | Operator failure detection | ✅ §26/§39 |
| 16 | Backup requirement | ✅ §28 |
| 17 | Restore requirement | ✅ §29 |
| 18 | Rollback philosophy | ✅ §31 |
| 19 | HTTPS requirement | ✅ §33/§43 |
| 20 | Production config behavior | ✅ §34 |
| 21 | Secret management | ✅ §35 |
| 22 | Logging requirement | ✅ §36 |
| 23 | Monitoring requirement | ✅ §38 |
| 24 | Hosting decision | ✅ §42 — deliberately deferred, reasoned |
| 25 | Production DB requirement | ✅ §44 |
| 26 | Deployment order | ✅ §12/§53 |
| 27 | Smoke test | ✅ §48 |
| 28 | Bootstrap | ✅ §51/§52 |
| 29 | Scheduler activation proof | ✅ §54 |
| 30 | Automatic-maintenance claim threshold | ✅ §55 |
| 31 | Private-beta reliability bar | ✅ §56 |
| 32 | Failure drills | ✅ §58 |
| 33 | Tests | ✅ §59 |
| 34 | Guards | ✅ §60 |
| 35 | Implementation split | ✅ §61 |

**§11 test/incident question, answered directly and separately here since it governs the whole document's own credibility:** the backend test suite passed 1,463/1,463 while the live database was one migration behind because `tests/conftest.py`'s own `_apply_migrations` fixture **runs `alembic upgrade head` against the isolated test database once, automatically, before any test executes** (confirmed by direct read this turn) — every test therefore verifies *application code correctness against a schema the test harness itself guarantees is current*, by design, correctly. **No test, in the traditional pytest sense, could ever have caught this incident** — it is not a code-correctness gap the existing suite failed to cover; it is the complete *absence*, in the running application itself, of any mechanism that checks whether a **specific, real, already-deployed instance's own database** matches what the code expects. The "missing test class" this document freezes is therefore not a retroactive gap-filler for the existing suite (§59.1-12 are new tests *of the new compatibility-check mechanism* #26C builds, not tests that could have existed before that mechanism did) — it is, honestly, a previously-nonexistent category of check (a runtime readiness probe and a deploy-time verification step, §14/§49) that this document is the first thing in this project to specify.

All thirty-five items are resolved with a specific, evidence-grounded decision. None remain materially ambiguous.

---

## Appendix: secret safety and version control

No `.env`/`.env.*`/credential file was read, printed, or logged at any point this increment — only variable **names**, already-referenced identically by existing, already-committed code, were used anywhere in this document. The dev database was inspected exactly as far as `alembic current`/`alembic heads`/`psql \dt` (already known, unchanged, from #26A) — **no migration was run, no schema was altered, no data was modified.** Nothing in this document was committed or pushed; no production code, migration, Dockerfile, CI configuration, deployment manifest, scheduler configuration, readiness endpoint, monitoring configuration, frontend file, or economic/AI functionality was created or modified this increment — only this new document.
