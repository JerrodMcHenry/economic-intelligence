# MacroChipz — First Production Deployment Checklist (#54A → #54B)

**Increment #54A — preparation only. Nothing was deployed, provisioned,
purchased or configured.** Baseline: `bd49a45` (#53B), clean tree, CI
green on that commit (verified — see §1).

**Launch scope: Rates and Housing only.** Inflation and Jobs must not be
publicly accessible until FRED redistribution rights are resolved
(`macrochipz-deployment-launch-plan-v46b.md` §D). The Analyst ships
disabled (no `OPENAI_*` in production).

This document supersedes nothing. The platform decisions remain frozen
in `docs/product/render-production-architecture-v1.md` (#26F) and the
controls in `docs/operations/production-deployment-v1.md` (#34). What
this document adds is (a) what was actually *executed* in #54A, (b) what
a Rates + Housing-only launch changes in that plan, and (c) the exact
#54B sequence.

**Evidence labels:** **VERIFIED** = executed or read this increment ·
**DOCS** = quoted from official Render documentation fetched
2026-09-24 · **ASSUMPTION** = must be confirmed during #54B.

---

## §1. What #54A executed

| Check | Result | Label |
|---|---|---|
| CI on `bd49a45` (#53B) | Run 36043618403: `backend` success, `frontend` success (public GitHub API) | VERIFIED |
| `docker build` / `docker run` | **Not performed — no container runtime on this machine** (no Docker, Colima, Podman or OrbStack). The image itself remains unverified. | — |
| Image-equivalent run | Fresh Python 3.12 venv, `pip install .` of exactly the Dockerfile's `COPY` set (no `dev` extra; pytest absent), cleared environment, no `.env`, the Dockerfile's own `CMD` string executed by `sh` | VERIFIED |
| Web `CMD` as written | **Failed to start** — defect D1 (§2), fixed | VERIFIED |
| Platform-style `DATABASE_URL` | **Every DB route 500, migrate crashed** — defect D2 (§2), fixed | VERIFIED |
| Fresh-DB migration | `preflight` → `SCHEMA_UNINITIALIZED`; `migrate` → 12 revisions → `COMPATIBLE` (`e7b3d51c8a94`); second `migrate` is a no-op | VERIFIED |
| `/health`, `/readiness` | 200 / 200 `ready: true`, version reported from `APP_VERSION` | VERIFIED |
| Production mode, config missing | Startup logs one named line per missing variable (names only); all four sync routes **503**; `/docs` + `/openapi.json` 404; legacy `/ai/query` 404 | VERIFIED |
| Production mode, configured | Operator routes 401 without/with wrong token; CORS preflight allowed for the configured origin, **400 and no ACAO** for a foreign origin | VERIFIED |
| Security headers, request id | `nosniff`, `DENY`, `no-referrer`, `Permissions-Policy`, `X-Request-ID` on every response; inbound id echoed | VERIFIED |
| Rates ingestion without FRED | Authorised `POST /rates/sync` → `SUCCEEDED`, 6 series × 245 observations, **449.8 s in one request / one transaction** | VERIFIED |
| Interrupted ingestion | SIGKILL of the web process 290 s into a sync → Postgres rolled back; no run row, no partial rows, no lingering backend (§7) | VERIFIED |
| Backup → restore | `pg_dump -Fc` → `pg_restore` into a new DB → row counts identical across 11 tables + `alembic_version`; `preflight` `COMPATIBLE` on the restored copy (§6) | VERIFIED (locally, PG 14) |
| Frontend production build, API-first | `VITE_API_BASE_URL` → live prod-mode API, `VITE_SITE_URL` set: 27 HTML pages, **6 permanent Rates object pages prerendered**, sitemap + verify steps green, 1.9 MB | VERIFIED |
| Test suites (after both fixes) | Backend **2513 passed, 2 skipped** (PG 14); frontend **2016 passed**, typecheck + lint clean, production build green | VERIFIED |

Housing ingestion was **not** exercised: it needs `CENSUS_API_KEY`, and
no secret was read in this increment.

---

## §2. Defects found and fixed in #54A

**D1 — the image could not start.** `CMD` passed
`--forwarded-allow-ips ${FORWARDED_ALLOW_IPS:-*}` unquoted to `sh -c`.
With the variable unset (the documented default), `sh` glob-expanded
`*` into the working directory's filenames, and uvicorn exited with
`Got unexpected extra arguments (alembic.ini app build … pyproject.toml)`.
`/app` in the image contains exactly those files, so the first Render
deploy would have failed its health check. Fixed by quoting both
expansions. Pinned by `TestDockerfileWebCommandExecutes`, which runs the
real `CMD` string through `sh` with a stub `uvicorn` — it fails on the
old `CMD` (verified) and passes on the new one.

**D2 — a platform-issued `DATABASE_URL` broke every database path.**
Render's `connectionString` is `postgresql://…` (ASSUMPTION on the
exact prefix; either form is now handled). SQLAlchemy maps that scheme
to psycopg2, which is not installed (the app ships psycopg 3):
`release migrate` crashed with a traceback and `/readiness` plus every
DB route returned **500**, not the contained 503. `postgres://` failed
differently — misreported as `DATABASE_UNAVAILABLE`. #26F §13 forbids
the obvious workaround (hand-pasting an edited credential), so
`Settings.database_url` now rewrites a driverless Postgres scheme to
`postgresql+psycopg://` and leaves anything naming a driver untouched.
Pinned by `tests/test_database_url_normalisation.py`, which resolves the
dialect the way `create_engine` does.

---

## §3. What a Rates + Housing launch changes in the frozen plan

| Frozen plan (#26F / #46B) | Rates + Housing launch |
|---|---|
| `FRED_API_KEY` required | **Do not set it.** Without it `/series/{id}` returns 503 and `/series/search` returns local results only (VERIFIED). |
| Bootstrap = FRED series sync + `process_release` | **Bootstrap = `POST /rates/sync` + `POST /housing/sync?full_history=true`.** No FRED call of any kind. |
| Cron job runs `run_maintenance` | **No cron job.** `run_maintenance` is FRED-only and exits 2 without the key. Rates/Housing have no CLI or scheduler yet — ingestion is operator-triggered (§7). |
| Cold-start bar: Inflation, Labor, Releases working | **Rates and Housing return real data; Inflation/Jobs/Calendar are not reachable** (blocker B1). |
| `smoke_test.py` checks inflation, labor, since-last-visit, releases | Those checks must change with B1 — they pass today only because an empty DB answers 200. |
| Automatic-maintenance claim (§77) | **Not claimable.** Nothing is scheduled. |

---

## §4. Production blockers — must be closed before #54B deploys

**B1 — Inflation and Jobs are publicly reachable. No gate exists
anywhere.** Not ingesting FRED data makes them *empty*, not
*inaccessible*: the pages, navigation, explainers and sitemap still
publish them. The #54A build's sitemap lists `/inflation`, `/jobs`,
`/calendar` and five Inflation/Jobs explainers (VERIFIED). This needs its
own increment before #54B. Minimum scope:

- *Backend* — unregister or 404 in production: `monitors/inflation*`,
  `monitors/labor*`, `monitors/{monitor}/history*` (inflation/labor
  only), `since-last-visit`, `releases`, `releases/processing-status`,
  `series/{id}` and `series/search` (live FRED proxies); restrict
  `series/{id}/observations|transform` and `analysis/*` to Treasury and
  Census series; filter `intelligence` to `rates` + `housing`; restrict
  the Analyst's context types to `RATES` (it ships disabled anyway).
  One `ENABLED_WORLDS`-style setting derived in `app/core/config.py`,
  matching ADR-033's "one switch, derived in one place" rule.
- *Frontend* — `ECONOMIC_WORLDS` (`worlds/registry.ts`) drives nav,
  hero, explainer index, chips and metadata in one place; plus the
  `App.tsx` routes (`inflation`, `jobs`, `labor`, `calendar`,
  `releases`), `STATIC_PATHS`, the five Inflation/Jobs explainers and
  their `related` links, the homepage's inflation/labor/releases
  sections, hard links (`Rates.tsx` "Explore Inflation", `/calendar`
  links), the footer's FRED attribution, and the home meta description.
  `routes.ts` states a preference for removing routes over flagging
  them — the increment must decide which, explicitly.
- *Smoke test* — check `/monitors/rates`, `/housing`, `/intelligence`,
  and assert the gated routes are **not** served.
- *Acceptance* — `curl` of each gated API route returns 404; the built
  sitemap contains no gated URL; a direct load of `/inflation` renders
  the 404 page.

**B2 — `robots.txt` has a relative `Sitemap:` directive** (#46B §C.4,
still unfixed; VERIFIED in the #54A build). Generate it from
`VITE_SITE_URL`. Small; fold into B1.

**B3 — human decisions still open:** Render account/workspace, domain
(or accept `*.onrender.com` for the first deploy), and explicit
confirmation that the Analyst stays off.

### Known risks accepted for a portfolio launch (not blockers)

- **Rates sync takes ~7.5 min in one HTTP request and one transaction,
  idle-in-transaction across network fetches.** Render sends SIGTERM to
  the old instance 60 s after cutover and SIGKILL after the shutdown
  delay (default 30 s, max 300 s) (DOCS) — at most ~360 s, less than
  the sync. Rule: **never deploy while a sync is running.** An
  interrupted sync is harmless (§7), just wasted. Follow-up: a
  `python -m app.operations.sync_rates|sync_housing` CLI so ingestion
  can run as a Render job/cron instead of a long HTTP request.
- **No rate limit on public reads.** With FRED data absent the
  intelligence set is small (6 objects after a Rates sync, versus 1,899
  in #46B's measurement), so per-call cost is low. Revisit on real traffic.
- **uvicorn's plain-text access log duplicates the JSON request line and
  records the raw path**, contrary to `production-deployment-v1.md`
  §14's intent. The JSON line's `route` also omits the `/api/v1` prefix.
  Cosmetic; `--no-access-log` is the one-flag fix.
- **Alembic reads the URL through `configparser`**, so a `%` in the
  password (e.g. a URL-encoded character) would break `migrate`.
  ASSUMPTION: Render-generated passwords are alphanumeric. Confirm at
  #54B; if not, escape `%` in `alembic/env.py`.
- **Local verification used PostgreSQL 14; Render defaults to 18**
  (DOCS). CI uses 16. `pg_dump` must be ≥ the server's major version.
- **Dependencies are unpinned** (`production-deployment-v1.md` §11.5):
  the image Render builds may differ from what was tested.

---

## §5. Minimum configuration — single instance

**Web service** (Docker, `0.5c-512mb`, 1 instance, region Oregon):

| Variable | Value | Secret? |
|---|---|---|
| `ENVIRONMENT` | `production` | no |
| `DATABASE_URL` | `fromDatabase: {name, property: connectionString}` (internal URL) | yes (platform-managed) |
| `CORS_ALLOWED_ORIGINS` | the static site's exact origin, e.g. `https://<site>.onrender.com` | no |
| `OPERATOR_TOKEN` | ≥ 32 random bytes, `sync: false` | **yes** |
| `CENSUS_API_KEY` | Census key, `sync: false` | **yes** |
| `APP_VERSION` | commit SHA — see note | no |
| `FRED_API_KEY`, `OPENAI_API_KEY`, `OPENAI_MODEL` | **unset** | — |
| `FORWARDED_ALLOW_IPS`, `EXPOSE_API_DOCS`, `ENABLE_LEGACY_AI_ROUTE` | **unset** | — |

- Pre-deploy command: `python -m app.operations.release migrate`
- Health check path: `/health` (never `/readiness` — #26F §10)
- `APP_VERSION`: Render injects service env vars as Docker build args
  (DOCS) and exposes `RENDER_GIT_COMMIT` at build and runtime (DOCS).
  Whether `RENDER_GIT_COMMIT` itself arrives as a build arg is
  ASSUMPTION — confirm by checking `/readiness`'s `version` after the
  first deploy.

**Postgres**: `0.1c-256mb`, 1 GB, same region, **`ipAllowList: []`**
(external access is open to any IP by default — DOCS). Pin
`postgresMajorVersion` explicitly.

**Static site**: build `npm ci && npm run build` in `frontend/`, publish
`frontend/build/client`, env `VITE_API_BASE_URL=https://<api>.onrender.com`
and `VITE_SITE_URL=https://<site>`. Routes: rewrite `/*` → `/index.html`
(DOCS: rules are not applied where a file exists, so prerendered pages
win). Redirects (301): `/overview` → `/`. `/labor` → `/jobs` and
`/releases` → `/calendar` must **not** be added while B1 gates their
targets. Headers: the CSP/HSTS set in `production-deployment-v1.md` §12
with `connect-src` naming the API origin. Whether `VITE_*` env vars
reach the static build is ASSUMPTION (DOCS show build-time variables
but do not say so explicitly) — the build log's `[prerender]` line
proves it either way.

---

## §6. Backup and restore rehearsal (executable in #54B)

**Platform** (DOCS): paid Postgres only — PITR 3 days on Hobby (restore
creates a **new** instance; not within 10 minutes of now); logical
exports on demand from the Recovery page, downloadable `.dir.tar.gz`,
retained 7 days.

**Row-count fingerprint** — run against source and restored DB; outputs
must be identical:

```sql
select 'alembic_version', (select version_num from alembic_version)
union all select t, n::text from (values
 ('economic_series',(select count(*) from economic_series)),
 ('economic_observations',(select count(*) from economic_observations)),
 ('observation_versions',(select count(*) from observation_versions)),
 ('observation_provenance',(select count(*) from observation_provenance)),
 ('rates_ingestion_runs',(select count(*) from rates_ingestion_runs)),
 ('housing_ingestion_runs',(select count(*) from housing_ingestion_runs)),
 ('recorded_monitor_results',(select count(*) from recorded_monitor_results)),
 ('economic_releases',(select count(*) from economic_releases)),
 ('release_series_mappings',(select count(*) from release_series_mappings)),
 ('maintenance_sweeps',(select count(*) from maintenance_sweeps))) v(t,n)
union all select 'max_observation_date', (select max(observation_date)::text from economic_observations)
order by 1;
```

**Rehearsal A — PITR (the real recovery path):**
1. After bootstrap (§8 step 9), wait ≥ 10 min; record the fingerprint
   and the UTC time *T*.
2. Dashboard → database → Recovery → restore to *T* as a new instance
   `macrochipz-db-restore-test`.
3. Run the fingerprint against it (Render Shell on the web service →
   `psql` with the restore instance's internal URL). Must match step 1.
4. From the same shell: `DATABASE_URL=<restore internal URL> python -m app.operations.release preflight`
   → `COMPATIBLE`. Never repoint the live service at it.
5. Delete the restore instance (it bills while it exists). Record date,
   *T*, and both fingerprints in the journal.

**Rehearsal B — logical export (the off-platform copy):** Create export
→ download → `tar -xzf` → `createdb macrochipz_restore_check` locally →
`pg_restore --no-owner --no-privileges --exit-on-error -d macrochipz_restore_check <dir>`
using a `pg_restore` whose major version ≥ the server's → fingerprint →
drop the local DB. Delete the downloaded file afterwards.

#54A rehearsed B's mechanics locally (`pg_dump -Fc`, PG 14): identical
fingerprints, restored copy `COMPATIBLE`.

**A backup that has never been restored is a belief, not a control**
(#46B). The launch is not complete until A has passed.

---

## §7. Ingestion: interruption, detection, retry

**Behaviour (VERIFIED for Rates; Housing is the same shape in code).**
Each sync is one transaction: observations, versions, provenance and the
`*_ingestion_runs` audit row commit together at the end, or not at all.
An interrupted sync (killed instance, dropped connection, deploy
cutover) is rolled back by Postgres and leaves **no trace** — no partial
rows and no run row.

**Detection.** Because an interrupted run writes nothing, it is
detected by **absence**:

```sql
select status, completed_at, observations_inserted, datasets_failed
from rates_ingestion_runs order by completed_at desc limit 5;
-- same for housing_ingestion_runs
```

- No new row after a sync you started → it was interrupted or never ran.
- `PARTIAL_FAILURE` / `FAILED` → a provider dataset failed; the others
  committed.
- `pg_stat_activity` with `application_name = 'macrochipz-api'` in
  `idle in transaction` for minutes = a sync in flight — **do not deploy**.

**Retry.** Re-run the same request. Upserts are idempotent — re-ingesting an
unchanged value inserts nothing and records no revision
(`RatesIngestionService.sync` docstring;
`tests/integration/test_rates_service.py::test_reingesting_the_same_value_is_idempotent`)
— so a retry after an interruption or a partial failure is safe.

**Staleness with nothing scheduled.** No alert exists. Treasury
publishes daily, Census monthly. Until a scheduler exists, the operator
checks the latest `completed_at` weekly and re-syncs.

---

## §8. #54B deployment sequence

Prerequisites: B1 and B2 merged, CI green on the deploy commit, and B3
decided.

1. **Render workspace** (Hobby). Enable email notifications for deploy
   failures.
2. **Postgres**: create `macrochipz-db`, `0.1c-256mb`, Oregon, pinned
   major version, `ipAllowList: []`. Confirm "Recovery" shows PITR available.
3. **Web service** from the repo (Docker, `0.5c-512mb`, Oregon, 1
   instance, branch `main`, **auto-deploy off**), env per §5,
   pre-deploy `python -m app.operations.release migrate`, health check `/health`.
4. **First deploy.** Expect in the pre-deploy log:
   `SCHEMA_UNINITIALIZED` → 12 upgrades → `Migration verified: database is COMPATIBLE.`
   Expect **no** `production configuration problem` line at startup.
5. **API checks** from the operator machine:
   ```bash
   API=https://<api>.onrender.com
   curl -s $API/health                                  # {"status":"ok"}
   curl -s $API/readiness                               # ready:true, version = deployed SHA
   curl -s -o /dev/null -w '%{http_code}\n' $API/docs   # 404
   curl -s -o /dev/null -w '%{http_code}\n' -X POST $API/api/v1/rates/sync   # 401
   curl -s -o /dev/null -w '%{http_code}\n' $API/api/v1/monitors/inflation   # 404 (B1)
   ```
6. **Bootstrap Rates** (≈ 8 min; no deploy while it runs):
   `curl -X POST -H "X-Operator-Token: $OPERATOR_TOKEN" $API/api/v1/rates/sync`
   → `status: SUCCEEDED`, six series with observations.
7. **Bootstrap Housing**:
   `curl -X POST -H "X-Operator-Token: $OPERATOR_TOKEN" "$API/api/v1/housing/sync?full_history=true"`
   → `SUCCEEDED`. The token comes from the operator's environment and is
   never pasted into a file or a document.
8. **Static site**, env per §5, rewrite/redirect/header rules. The build
   log must show 6+ prerendered `/intelligence/…` pages — API-first
   ordering is load-bearing (#46B §A.2).
9. **Smoke** — `python -m app.operations.smoke_test --base-url $API`
   (post-B1 version), then in a browser: `/`, `/rates`, `/housing`,
   one `/intelligence/<id>`, one explainer. `curl -I` a prerendered
   object URL and confirm the HTML `<title>` is the object's — the
   directories are named `rates%3A…` and the host's handling of `:` in
   paths is ASSUMPTION. Confirm `/inflation` and `/jobs` show the 404
   page, and that `sitemap.xml` and `robots.txt` are correct.
10. **CORS from the real origin**: page loads with no console CORS
    errors; from a foreign origin, preflight is rejected.
11. **Backup rehearsal A** (§6). Launch is not complete until it passes.
12. **Record** in the journal: deploy SHA, pre-deploy log excerpt,
    smoke output, fingerprints, rehearsal time.

**Stop for review before step 3** — the first step that creates a
billable resource that serves traffic.

---

## §9. Rollback and failure recovery

| Failure | Response |
|---|---|
| Pre-deploy `migrate` fails | Deploy cancelled; previous version keeps serving (DOCS). Read the pre-deploy log, fix, redeploy. |
| New instance fails `/health` | Cancelled after 15 min; previous version keeps serving (DOCS). First deploy: nothing serves — check the startup log. |
| Bad release, schema fine | Render rollback to the previous deploy. Safe because migrations are additive-only (#26F §21). Never downgrade the DB. |
| `/readiness` 503 `schema_mismatch` on an old instance | Expected during the post-migrate window; diagnostic only, not a routing input. |
| Sync interrupted or `FAILED` | §7: check run rows, re-run. |
| Data loss / corruption | PITR to a new instance → fingerprint → preflight `COMPATIBLE` → repoint `DATABASE_URL` → redeploy. |
| Frontend build fails | Backend unaffected; previous static deploy keeps serving. `[prerender] … Refusing to build` means the API was unreachable from the build — fix the API first. |
| `OPERATOR_TOKEN` leaked | Replace the env var and redeploy; the old value stops working at cutover. |

---

## §10. Recurring cost

| Item | Monthly | Label |
|---|---|---|
| Hobby workspace | $0 (5 GB bandwidth, 3-day PITR) | DOCS |
| Web `0.5c-512mb` | $7 | DOCS |
| Postgres `0.1c-256mb`, 1 GB | $6 (+$0.30/GB beyond) | DOCS |
| Static site | $0 (counts against the 5 GB) | DOCS |
| Cron job | $0 — none at launch (≥ $1/mo each when added) | DOCS |
| Analyst | $0 — disabled | decision |
| **Total** | **≈ $13/month** + optional domain (~$1/mo) | |

Overage risk: bandwidth beyond 5 GB at $0.15/GB — the #54A build is
1.9 MB of static assets, so a viral spike is the realistic path.
Temporary restore instances are billed while they exist; delete them.
