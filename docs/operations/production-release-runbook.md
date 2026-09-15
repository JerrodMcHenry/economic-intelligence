# Production Release Runbook

**Increment #26D.** Operator-facing, not product/architecture prose — this document answers the specific questions an operator has at the moment of a release, a failure, or an incident. The authoritative *design* contract remains `docs/product/production-reliability-deployment-v1.md` (#26B) and `docs/adr/027-schema-compatibility-exact-equality-and-readiness-split.md` (ADR-027); this document is the operational companion, not a replacement.

---

## How do I validate a release?

Run the existing test suites — nothing #26D adds changes this:

```
TEST_DATABASE_URL=postgresql+psycopg://<user>@localhost:5432/economic_intelligence_test pytest tests/ -q
cd frontend && npm test -- --run && npm run typecheck && npm run lint && npm run build
```

If CI (`.github/workflows/ci.yml`) is configured for this repository, a green run on the commit being released is the same validation, run automatically on push/PR — CI **never** touches a production database, and it never deploys anything on its own (see "Why don't I automatically deploy from CI?" below).

---

## How do I migrate?

**One command, run as its own, explicit, separate step — never folded into starting the web process:**

```
python -m app.operations.release preflight   # read-only: reports whether it is safe to proceed
python -m app.operations.release migrate     # applies + verifies, in one step
```

`migrate` internally runs the identical preflight first — running `preflight` by hand first is optional (useful in a dry-run/gate check, e.g. a deploy pipeline step that wants to fail fast before doing anything else), never required.

`DATABASE_URL` must point at the target environment's own database before running either command — this command uses the exact same configuration (`app.core.config.settings`) every other part of this application already reads.

---

## How do I verify?

`migrate` already verifies its own result internally (it re-runs the compatibility check after applying migrations and refuses to report success unless the database is `COMPATIBLE`) — a `0` exit code from `migrate` **is** the verification.

To verify independently, at any later time, against a running instance: `GET /readiness` — `200 {"ready": true, ...}` means the instance's own configured database is compatible right now. This is the same check `migrate` itself uses internally, never a second, different one.

---

## How do I start web?

```
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

(or, from the container image: `docker run <image>` — this is the image's own default `CMD`). **Never** run a migration command as part of, or before, this command in the same invocation — migration is always its own separate, prior step (see "How do I migrate?" above). Web startup does not check compatibility at process-start time either — it becomes observable, per-request, via `/readiness` the moment the process is up.

---

## How do I smoke test?

```
python -m app.operations.smoke_test --base-url https://<deployed-api-origin>
```

Read-only: `GET`s `/health`, `/readiness`, both canonical monitor endpoints, `/since-last-visit`, and `/releases`. Exits `0` only if every check passes, including `/readiness` itself reporting `ready: true` — a smoke test against an unready instance is a **failure**, not a partial success. An honest `INSUFFICIENT_DATA`/empty-content `200` on a freshly bootstrapped environment is acceptable (see "What about a fresh, empty database?" below) — only an unexpected `4xx`/`5xx`, or an unready `/readiness`, fails the check.

---

## What if migration fails?

The command exits non-zero and prints a safe, generic failure message (the exception *type* only, never its message, never any connection detail). **The new application version must not be deployed.** Because every migration in this project's own chain runs inside Postgres's own transactional DDL, a failed migration leaves the database at whatever revision it last successfully reached — the **currently-running, old** application version (already compatible with that revision, since it was serving traffic successfully before the release began) is **completely unaffected** and keeps serving normally. Diagnose the failure from the operator's own logs/terminal (never from the command's own stdout/stderr, which deliberately never includes the underlying exception message), fix the migration, and re-run `preflight` then `migrate` once the fix is in place.

---

## What if readiness is 503?

Read the response body — it already tells you which of three things is wrong, without needing database access to find out:

- `"reason": "schema_mismatch"` → the database has not been migrated to this application version's own expected head. Run `python -m app.operations.release preflight` against the same `DATABASE_URL` for the full detail (expected vs. actual revision); if the actual revision is genuinely *behind* (or the database was never initialized), run `migrate`. **If `preflight` itself refuses** (see "What if the database is ahead?" below), do not attempt to force it.
- `"reason": "database_unreachable"` → the database is not reachable at all from this instance. This is an infrastructure problem (network, firewall, the database is down) — application-level tooling cannot fix it; escalate to whoever owns the database/network.
- `"reason": "configuration_missing"` → `DATABASE_URL` is not set on this instance at all. A deployment/configuration error — fix the environment configuration for this instance and restart it (no migration is needed; this has nothing to do with the schema).

---

## What if the database is ahead?

**This tool refuses outright — it never attempts an automatic downgrade or any other automatic correction.** `preflight`/`migrate` both exit non-zero with `SCHEMA_AHEAD` reported explicitly. This situation means the database's own tracked revision is not a recognized ancestor of this application version's expected head — most plausibly, a newer application version was already migrated against this database, and the code now running is older than that. The correct response is almost always to deploy the newer application version that matches the database, not to touch the database. If this is genuinely unexpected, stop and investigate before doing anything else — do not run `alembic downgrade` by hand against a production database without first understanding exactly why the state diverged.

---

## What if the database is unavailable?

Both `preflight`/`migrate` and `/readiness` report this distinctly (`DATABASE_UNAVAILABLE`) rather than as a generic failure. This is an infrastructure problem, not a schema problem — check the database is running, reachable, and that `DATABASE_URL` is correct for this environment; no application-level command will resolve it.

---

## How do I roll back application?

**Redeploy the prior build/container version.** This is always safe *as long as every migration remains purely additive* (true of every migration in this chain today, per `production-reliability-deployment-v1.md` §7) — the old application code simply never references the new table/column it doesn't know about, so it keeps working correctly against the now-advanced schema. Application rollback is **always** the first response to a bad release; it never requires touching the database.

---

## Why don't I automatically downgrade the database?

Because `alembic downgrade` is **not** a safe, general-purpose "undo my release" mechanism — restated from `production-reliability-deployment-v1.md` §31: it happens to be safe for *every migration in this project's chain today* (each one's own `downgrade()` was written and reviewed carefully), but a future migration involving a genuine data transformation or a destructive schema change could make its own downgrade lossy or outright wrong. The safe, general rule is: **prefer application rollback (always safe, never touches the database) over a database downgrade (only situationally safe, and never assumed to be by default)**. A database downgrade is a deliberate, case-by-case operator decision — reviewed against that *specific* migration's own downgrade path — never an automatic response to a bad release, and this project provides no command that performs one automatically for exactly that reason.

---

## What about a fresh, empty database?

Migrating a genuinely fresh database (`migrate` from `SCHEMA_UNINITIALIZED`) already seeds the curated release catalog — that part of "bootstrap" is free, bundled into the migration chain itself (three of the eight migrations are data-seeding migrations). It does **not** seed any actual economic observation data or produce a non-`INSUFFICIENT_DATA` monitor state — that requires a real sync against FRED and at least one processing pass (`python -m app.operations.process_release`), which is **#26F's own scope, not #26D's**. Do not invite beta users to an environment that has only been migrated, never bootstrapped — its monitors will honestly, correctly, but unhelpfully show `INSUFFICIENT_DATA` everywhere.

---

## Migration locking / concurrency

No advisory lock is added around the migration step. `production-reliability-deployment-v1.md`'s own release process is already a single, serialized pipeline phase — migrations are never expected to run concurrently with themselves. If a genuinely concurrent invocation somehow occurred, Postgres's own transactional DDL fails loudly (a real database error, safely reported, never silent corruption) rather than corrupting the schema. Revisit if a genuinely concurrent-deploy-capable pipeline is ever introduced (see `app/operations/release.py`'s own docstring for the full reasoning).

---

## Backups

`production-reliability-deployment-v1.md` §28-30 already froze the requirement: automated backups plus a verified restore rehearsal, required before private beta, and a fresh backup/snapshot immediately before any *destructive* migration specifically (every migration in the current chain is additive, so none has required this yet). **#26D does not implement a backup mechanism** — that is a managed-database/hosting-platform feature to enable once a production database exists (see "Production database" below), not application code to write. Before running a migration that is NOT purely additive (drops/renames/data transformations), confirm a recent, verified backup exists first — this is a manual operator checklist item, not something `preflight`/`migrate` can check on their own.

---

## Production database

Managed PostgreSQL is the recommended shape (automated backups, TLS, a published connection limit, all handled by the platform) — no vendor is chosen or provisioned by this document. Whatever platform is eventually chosen, `DATABASE_URL` is the one configuration value this whole release process (and the application itself) depends on; nothing else about `release.py`/`smoke_test.py`/`/readiness` needs to change based on which platform is chosen.

---

## Environment variables (names only)

| Variable | Required for | Notes |
|---|---|---|
| `DATABASE_URL` | Web process (to become ready), migration command, maintenance/manual-processing CLIs | Absence → `/readiness` reports `configuration_missing`; the web process itself still starts (`/health` stays `200`) |
| `FRED_API_KEY` | Maintenance CLI, manual release-processing CLI | **Not** required for the web process to serve any read-only route (monitors, since-last-visit, releases all read from the database only) |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | AI query route only | Absence → AI features report themselves unconfigured; nothing else is affected |
| `APP_VERSION` | Optional, `/readiness`'s own `version` field | Falls back to a local `git rev-parse --short HEAD` if unset — set this explicitly in any environment whose own container/artifact does not include a `.git` directory |
| `VITE_API_BASE_URL` | Frontend build only (build-time, not runtime) | The deployed backend's own public origin — configuration, not a secret |

No variable value is ever printed by any command in this project — only names, exactly as this table lists them.

---

## CORS

Same-origin local development requires no CORS configuration (the Vite dev server proxies `/api/*`). **The moment frontend and backend are deployed to different origins** (the expected production shape, given `VITE_API_BASE_URL`'s own build-time-configurable design), CORS middleware must be added with an explicit, narrow `allow_origins` list containing exactly the deployed frontend's own origin(s) — never a wildcard. **Not implemented in #26D** — this repository's packaging decision (frontend built and deployed independently as static assets, §6) makes cross-origin deployment the expected shape, but the actual origin(s) are not known until a real hosting choice is made; add the middleware at that point, following `production-reliability-deployment-v1.md` §33 exactly.

---

## HTTPS

Required for any private beta (`production-reliability-deployment-v1.md` §32/§43). Not managed by this application — assume TLS termination at whatever reverse proxy/platform edge the eventual hosting choice provides; FastAPI itself never manages a certificate.

---

## Scheduler / automation status

**Increment #26E's verdict: B — IMPLEMENTATION READY, NOT ACTIVATED.** Every portable piece exists and is tested against real PostgreSQL: `python -m app.operations.run_maintenance` (unchanged, one bounded sweep per invocation, already gated by the schema-compatibility preflight), `python -m app.operations.maintenance_health` (new — the operator-facing heartbeat query, below), and a reviewable, syntactically-valid scheduler template (`.github/workflows/scheduled-maintenance.yml.disabled`). **Nothing in this repository currently invokes the maintenance command on a real, external schedule.**

**Why not activated:** activation requires a real, network-reachable production database, and this project has never been deployed anywhere. The scheduler *mechanism* (GitHub Actions, chosen because it needs no hosting decision of its own) is not the blocker — the blocker is a genuinely unanswered security question: can a scheduler reach that database without weakening its own network/access controls? GitHub-hosted runners have broad, shared, non-allowlistable IP ranges; answering "yes, safely" requires a real database with a real network boundary to reason about, which does not exist yet. Fabricating an active `schedule:` trigger against nothing would be exactly the "code existence is not automation" mistake this increment's own truthfulness requirement forbids — so the template file is named with a `.disabled` suffix specifically so GitHub Actions cannot recognize or run it at all, regardless of its own content, until an operator deliberately renames it after that security question has a real answer for a real environment (see the template's own header comment for the exact activation checklist).

**The automatic-maintenance claim threshold, restated and now made checkable:** the product may only be described as "automatically maintained" once (1) the template is renamed and its secrets configured against a real database, (2) at least two separate scheduled (never merely `workflow_dispatch`-triggered) invocations have occurred without a human manually triggering either one, (3) each produced its own `MaintenanceSweep` row, and (4) `python -m app.operations.maintenance_health` reports `HEALTHY` against that same database afterward. A manual test run (`workflow_dispatch`, or running the command by hand) proves the *configuration* works — it does not, on its own, prove *scheduled* automation, and must never be described as if it did.

### Maintenance-worker health — the operator's own heartbeat query

```
python -m app.operations.maintenance_health [--json] [--stale-threshold-hours N] [--unfinished-grace-minutes N]
```

Read-only; checks schema compatibility first (refusing to interpret sweep history at all if incompatible — the exact same shared check `/readiness` uses) and then classifies the worker's own recent history from persisted `MaintenanceSweep` evidence alone:

| Status | Meaning | Exit code |
|---|---|---|
| `HEALTHY` | A sweep completed within the last 3 hours (default), with zero occurrence failures. | `0` |
| `DEGRADED` | A sweep completed within the last 3 hours, but `failed_count > 0` — the worker itself is fine; at least one occurrence's own processing failed. | `1` |
| `STALE` | The most recent *completed* sweep's own `started_at` is older than 3 hours (default) — the scheduler may have stopped firing. | `1` |
| `UNFINISHED` | The most recent sweep started more than 30 minutes ago (default) and still has not finished — plausibly crashed or hung, not merely still running. | `1` |
| `NEVER_RUN` | Zero sweep rows exist at all. **Expected and normal before activation** — never treat this the same as a broken, previously-working scheduler. | `1` |
| *(schema incompatible / DB unavailable / config missing)* | Reported directly, sweep history not interpreted at all. | `2` |

Both thresholds (3 hours staleness, 30 minutes unfinished-grace) are operator-tunable via the flags above — derived from, not empirically measured against, the frozen hourly-order sweep cadence (`automated-economic-maintenance-v1.md` §15); adjust them if the real cadence chosen for a given environment differs materially from hourly. `--json` emits one machine-readable object for a monitoring/alerting integration to consume instead of parsing human-readable text.

### Minimum private-beta operator alerts (semantics frozen, no paging infrastructure built)

- The scheduled job itself exits non-zero, or times out (bound the job at the scheduler/platform level — no arbitrary economic timeout is invented; the underlying due-work volume is small, §49 of the maintenance contract, so a generous bound like 15-30 minutes is a safety net, not a tight economic constraint).
- `maintenance_health` reports anything other than `HEALTHY` when checked on a regular cadence (a second, independent scheduled check, or folded into the same job as an informational, non-blocking step — see the template's own final step).
- `/readiness` fails, if the hosting platform's own monitoring supports checking it.

No specific alert destination (Slack/email/PagerDuty) is chosen or wired here — whatever notification mechanism the eventual scheduler platform already provides (GitHub Actions' own default failure email, for instance) is sufficient for private beta; do not build a bespoke integration speculatively.

### Sweep-level locking: deliberately not added

Occurrence-level advisory locking (ADR-024) already prevents the one dangerous outcome (duplicate audit rows for the same occurrence). Two full sweeps overlapping in time is not itself prevented, and is not given its own lock: the frozen hourly-order cadence against a small, typically-seconds-long sweep duration (§49) makes genuine overlap implausible in practice, and — per this project's own repeated "do not add locking reflexively" discipline (see `app/operations/release.py`'s identical reasoning for the migration step) — no observed problem currently justifies the added complexity. Revisit only if real operational evidence of overlap-caused confusion appears.

---

## Current known development database status

The developer's own local `economic_intelligence` database remains exactly as Increment #26A found it — one migration behind head (`09f4c0959e9f`, missing `recorded_monitor_results`). **Not repaired by #26D.** To fix it, run, against that specific database:

```
DATABASE_URL=<the real local DATABASE_URL> python -m app.operations.release migrate
```

This is the exact command this runbook documents for any environment — the local development database is not a special case, only one this project has deliberately left unfixed as ongoing, live proof that the diagnosis (`/readiness`) and remediation (`release migrate`) both work as designed.
