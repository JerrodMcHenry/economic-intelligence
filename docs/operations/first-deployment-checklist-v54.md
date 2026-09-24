# MacroChipz — Restricted Deployment Checklist (#54A → #55A)

**Increment #55A — preparation only. Nothing deployed, provisioned,
purchased or configured; nothing committed or pushed.**
- Baseline `7c7e5ce`: CI green (run 36049522444).
- #54A evidence (§1–§2) is unchanged below.
- #55A **replaces #54A's Rates + Housing-only plan** with a restricted
  deployment of all four worlds. Inflation and Jobs stay FRED-sourced
  (the #54B migration is audited, not approved), so nothing may be
  served without authentication.

Decision record: `docs/adr/042-restricted-demo-access-gate.md`. The
platform decisions in `render-production-architecture-v1.md` (#26F)
stand, except where ADR-042 supersedes them: a single web service
serves the frontend; there is no static site.

**Evidence labels:**
- **VERIFIED** = executed this increment.
- **DOCS** = quoted from official Render/Cloudflare documentation,
  fetched 2026-09-24.
- **ASSUMPTION** = must be confirmed at deploy time.
- **CI** = exercised by `.github/workflows/container.yml`; runs on the
  next push, so no result exists yet.

---

## Part A — #54A evidence (unchanged)

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

### §1b. What #55A executed

| Check | Result | Label |
|---|---|---|
| CI on `7c7e5ce` | `CI` run 36049522444 success | VERIFIED |
| Docker build / container run | **No Docker daemon on this machine.** `container.yml` added; it runs on the next push | CI (pending) |
| Frontend built exactly as the image's stage does | `VITE_API_BASE_URL= VITE_SITE_URL= npm run build`: green, **no sitemap**, 0 object pages | VERIFIED |
| Image-equivalent process, production mode, gate on | Production-only venv, the Dockerfile's own `CMD`, `postgresql://` URL, no CORS, restored copy of the dev DB (all four worlds) | VERIFIED |
| `verify_container.py` (the CI checks) | **41/41** configured, **5/5** misconfigured | VERIFIED |
| `smoke_test --restricted` | **13/13** | VERIFIED |
| Startup log | 0 configuration problems; the access password and operator token appear 0 times | VERIFIED |
| Real browser, same frontend + CSP (gate off: browser rules forbid me entering a password) | `/inflation`, `/jobs` (live data), `/revisions`, `/intelligence/<id>` (SPA fallback) render. Zero cross-origin requests, zero CSP violations, zero errors | VERIFIED |
| Browser Basic-auth prompt and credential reuse on `fetch` | Standard browser behaviour, **not exercised here** — check at step §6.7 | ASSUMPTION |
| Test suites | Backend **2596 passed, 2 skipped**; frontend **2016 passed**; typecheck + lint clean | VERIFIED |


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

## Part B — #55A restricted deployment

## §3. Access architecture (ADR-042)

```
  Reviewer's browser ──HTTPS──► Render edge (TLS, HTTP→HTTPS redirect)
                                   │
                                   ▼
             ONE Docker web service  (0.5c-512mb, 1 instance)
             ┌───────────────────────────────────────────────┐
             │ RequestContext → BodySize → SecurityHeaders    │
             │   → AccessGate (HTTP Basic; only /health open)  │
             │       → /api/v1/…  (FastAPI routes)             │
             │       → /…         (built frontend, SPA fallback)│
             └───────────────────────────────────────────────┘
                                   │ private network
                                   ▼
                     Render Postgres 0.1c-256mb (internal only)
```

What Render offers for access control (DOCS):
- **No visitor authentication** for static sites or web services.
- **Inbound IP rules** for web and static services require the **Scale
  plan ($499/month)**.
- **Private services** have no public URL.
- The **`onrender.com` subdomain** can be disabled once a custom domain
  exists.

That is why the frontend moves into the web service. **A Render Static
Site cannot be private**, so it is not used.

**Upgrade path:**
- Cloudflare Access is free up to 50 users (DOCS).
- It requires a Cloudflare-hosted custom domain,
  `renderSubdomainPolicy: disabled`, and origin validation of
  `Cf-Access-Jwt-Assertion` (DOCS) — which would be added to the same
  middleware.

**What is gated — VERIFIED:**
- Every API route: enumerated by `tests/test_access_gate.py` from
  FastAPI's own route table, not a hand-kept list.
- `/readiness`: it reveals the version and schema.
- Every frontend page, prerendered page, share page (`/intelligence/…`),
  asset, `robots.txt` and unknown path.

**Open:** `/health` only (`{"status":"ok"}`, required by the platform
health check).

**Not generated:** the image's frontend build sets no `VITE_SITE_URL`,
so there is no `sitemap.xml`, no absolute canonical, no OG images and
no prerendered object pages (CI asserts the sitemap's absence).

**Fail closed — VERIFIED:** with `ACCESS_PASSWORD` unset or shorter than
16 characters in production, everything except `/health` returns 503.

---

## §4. Remaining blockers and decisions

**Blocking:**
- **R1 — Docker CI has not run yet.** `container.yml` runs on the next
  push. Its Docker steps (build, image contents, migrate, start, logs)
  have never executed. The HTTP checks it runs were executed locally
  against the image-equivalent process, 41/41 + 5/5 (§1b). **Do not
  deploy until that workflow is green.**
- **R2 — FRED terms under restriction (DECISION).** Restricting access
  reduces exposure to a handful of invited reviewers. It does **not**
  resolve FRED's API terms (#46B §D.3), which is a human decision.
  Record the decision before deploying.
- **R3 — public repository contains FRED-derived snapshots.**
  - `docs/product/mockups/v50a/inflation-snapshot.json` and `data.js`
    (from `9b97f16`), and `v51a/jobs-snapshot.json`, `data.js` and
    `index.html` (from `afa3f89`), are real API captures.
  - The repository is **public** (VERIFIED via the GitHub API).
  - They are not in the image (`docs/` is dockerignored) and no route
    serves them, but they sit outside any access boundary.
  - Removing them from the tree is simple. Removing them from history
    rewrites public history — a DECISION, not done here.

**Not blocking, recorded:**
- Basic auth has no logout, and all reviewers share one credential.
- The lockout counter is per process and keyed on a forgeable
  `X-Forwarded-For`; password length is the real defence (ADR-042).
- Rates sync is still ~7.5 min in one request; never deploy during a
  sync (§8).
- Access-log route templates omit the `/api/v1` prefix. Root cause
  found: this FastAPI version wraps included routers in a private
  `_IncludedRouter`, which is also why route enumeration uses the
  OpenAPI schema.
- **Correction to #54A §5:** its static-site rewrite (`/*` →
  `/index.html`) was wrong. Non-prerendered routes must receive
  `__spa-fallback.html` (React Router changelog), which is what
  `app/web/frontend.py` does.
- #54A §6 assumed `psql` in a Render Shell; the image has none. §7
  uses Python instead.

---

## §5. Configuration — one web service, one database

**Web service** (Docker, repo root `Dockerfile`, `0.5c-512mb`, Oregon, 1
instance, branch `main`, **auto-deploy off**):

| Variable | Value | Secret |
|---|---|---|
| `ENVIRONMENT` | `production` | no |
| `DATABASE_URL` | `fromDatabase: {name: macrochipz-db, property: connectionString}` (internal; `postgresql://` accepted since #54A) | platform-managed |
| `ACCESS_USERNAME` | e.g. `reviewer` | no |
| `ACCESS_PASSWORD` | `python -c "import secrets; print(secrets.token_urlsafe(24))"` (32 chars), `sync: false` | **yes** |
| `OPERATOR_TOKEN` | `python -c "import secrets; print(secrets.token_urlsafe(32))"`, `sync: false` | **yes** |
| `FRED_API_KEY` | FRED key, `sync: false` — needed for Inflation/Jobs ingestion (R2) | **yes** |
| `CENSUS_API_KEY` | Census key, `sync: false` | **yes** |
| `CORS_ALLOWED_ORIGINS` | **unset** — the frontend is same-origin | — |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | **unset** — Analyst stays disabled (VERIFIED: `available: false`) | — |
| `FRONTEND_DIST_DIR` | **do not set** — the image sets it | — |
| `FORWARDED_ALLOW_IPS`, `EXPOSE_API_DOCS`, `ENABLE_LEGACY_AI_ROUTE` | **unset** | — |

- **Pre-deploy command:** `python -m app.operations.release migrate`
  (paid plans only — DOCS).
- **Health check path:** `/health`.
- **Shutdown delay:** leave at the default 30 s.
- `APP_VERSION`: confirm `/readiness` reports the deployed SHA; if
  empty, add a build arg from `RENDER_GIT_COMMIT` (ASSUMPTION, #54A §5).

**Postgres:** `0.1c-256mb`, 1 GB, Oregon, pinned major version,
**`ipAllowList: []`** (open to all IPs by default — DOCS).

**No static site. No cron job at first** (§7.4).

---

## §6. Deployment sequence

Prerequisites: R1 green, and R2 and R3 decided.

1. **Workspace:** Hobby. Enable deploy-failure email notifications.
2. **Postgres:** create per §5. Confirm the Recovery page shows PITR.
3. **Web service:** create per §5. **Stop for review before this
   step** — it is the first resource that serves traffic.
4. **First deploy.** Expect in the pre-deploy log:
   `Status: SCHEMA_UNINITIALIZED` → 12 upgrades →
   `Migration verified: database is COMPATIBLE.` Expect **no**
   `production configuration problem` line at startup.
5. **Boundary check from the operator's machine** (read-only), with
   `ACCESS_USERNAME` and `ACCESS_PASSWORD` exported:
   ```bash
   APP=https://<service>.onrender.com
   curl -s -o /dev/null -w '%{http_code}\n' $APP/health                          # 200
   curl -s -o /dev/null -w '%{http_code}\n' $APP/                                # 401
   curl -s -o /dev/null -w '%{http_code}\n' $APP/api/v1/monitors/inflation       # 401
   curl -s -o /dev/null -w '%{http_code}\n' http://<service>.onrender.com/health  # 301/308 to https
   python -m app.operations.smoke_test --base-url $APP --restricted             # all pass (empty data OK)
   ```
6. **Initial data** — §7.
7. **Smoke with data:** rerun the smoke test. Then sign in through a
   browser and confirm all four worlds show real states:
   - `/`, `/inflation`, `/jobs`, `/rates`, `/housing`, `/calendar`,
     `/revisions`
   - one explainer
   - one `/intelligence/<id>` page
8. **Backup rehearsal A** (§9). The deployment is not complete until it
   passes.
9. **Share access:** send reviewers the URL and credentials through
   separate channels. Record the deploy SHA, pre-deploy log excerpt,
   smoke output and rehearsal fingerprints in the journal.

---

## §7. Initial data

All HTTP calls carry both boundaries: the access credential and the
operator token. To keep secrets out of `argv` and shell history, put
them in a curl config file that is never committed:

```bash
umask 077
printf 'user = "%s:%s"\nheader = "X-Operator-Token: %s"\n' \
  "$ACCESS_USERNAME" "$ACCESS_PASSWORD" "$OPERATOR_TOKEN" > ~/.macrochipz-operator.curlrc
```

1. **Rates** (~8 min; do not deploy meanwhile):
   `curl -X POST -K ~/.macrochipz-operator.curlrc $APP/api/v1/rates/sync`
   → `"status": "SUCCEEDED"`.
2. **Housing:**
   `curl -X POST -K ~/.macrochipz-operator.curlrc "$APP/api/v1/housing/sync?full_history=true"`
   → `SUCCEEDED`.
3. **Release calendar (FRED):**
   `curl -X POST -K ~/.macrochipz-operator.curlrc $APP/api/v1/releases/sync`.
4. **Inflation and Jobs.**
   - Process the most recent past CPI (10), Employment Situation (50)
     and Personal Income and Outlays (54) occurrence.
   - Open a Render Shell on the web service and list the occurrences
     with the snippet below (VERIFIED locally through the
     production-only environment).

```sh
python - <<'PY'
from sqlalchemy import text
from app.db.session import session_scope
with session_scope() as s:
    rows = s.execute(text("""
        select distinct on (r.provider_release_id) r.provider_release_id, r.name, o.id, o.scheduled_date
        from release_occurrences o join economic_releases r on r.id = o.economic_release_id
        where r.provider_release_id in ('10', '54', '50') and o.scheduled_date <= current_date
        order by r.provider_release_id, o.scheduled_date desc"""))
    for release, name, occurrence_id, day in rows:
        print(f"{release:>3}  {day}  occurrence {occurrence_id}  {name}")
PY
```

   - Then, for each id:
     `python -m app.operations.process_release --occurrence-id <id>`.
     Each fetches the 5-year window and records a monitor result.
5. **Verify:** `/api/v1/monitors/inflation` and `/monitors/labor` return
   states other than `INSUFFICIENT_DATA`.
   - State duration may still report insufficient history: 60 stored
     months against about 73 needed (existing, #54B T4).
6. **Ongoing refresh (manual at first):**
   - Rates weekly.
   - Housing monthly.
   - `releases/sync` monthly.
   - `python -m app.operations.run_maintenance` after each CPI,
     Employment Situation or PIO release day. It processes occurrences
     due within a 7-day window.
   - A Render Cron Job for `run_maintenance` is optional: ≥ $1/month
     (DOCS), same image, and `FRED_API_KEY` + `DATABASE_URL` only.

## §8. Ingestion: interruption, detection, retry

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

## §9. Backup and restore rehearsal

**Platform (DOCS):**
- PITR on paid Postgres, 3 days on Hobby. A restore creates a **new**
  instance, and not within 10 minutes of now.
- Logical exports on demand, `.dir.tar.gz`, retained 7 days.

**Fingerprint.** Run in a Render Shell on the web service. The image
has no `psql`, so this is Python (VERIFIED locally). Point it at the
restored instance by prefixing `DATABASE_URL=<restore internal URL>`:

```sh
python - <<'PY'
from sqlalchemy import text
from app.db.session import session_scope
TABLES = ["economic_series", "economic_observations", "observation_versions", "observation_provenance",
          "rates_ingestion_runs", "housing_ingestion_runs", "recorded_monitor_results", "economic_releases",
          "release_occurrences", "release_series_mappings", "release_check_runs", "maintenance_sweeps"]
with session_scope() as s:
    print("alembic_version", s.execute(text("select version_num from alembic_version")).scalar())
    for table in TABLES:
        print(table, s.execute(text(f"select count(*) from {table}")).scalar())
    print("max_observation_date", s.execute(text("select max(observation_date) from economic_observations")).scalar())
PY
```

**Rehearsal A — PITR:**
1. Once data is loaded, wait ≥ 10 min. Fingerprint the live database
   and record the UTC time *T*.
2. Restore to *T* as the new instance `macrochipz-db-restore-test`.
3. Run the fingerprint snippet above with `DATABASE_URL=<restore internal URL>`
   prefixed to `python -` → identical output.
4. `DATABASE_URL=<restore internal URL> python -m app.operations.release preflight`
   → `COMPATIBLE`. Never repoint the live service at the restore.
5. Delete the restore instance (it bills while it exists) and record
   the results.

**Rehearsal B — logical export:**
- Create an export and download it (local machine).
- `pg_restore --no-owner --no-privileges --exit-on-error` into a scratch
  local database, using `pg_restore` ≥ the server's major version.
- Run the same fingerprint through the repository's venv.
- Drop the scratch database and delete the file.
- #54A rehearsed this mechanically: identical fingerprints (VERIFIED,
  PG 14).

---

## §10. Rollback and failure recovery

| Failure | Response |
|---|---|
| Pre-deploy `migrate` fails | Deploy cancelled; previous version keeps serving (DOCS). Fix and redeploy. |
| New instance fails `/health` | Cancelled after 15 min; previous version keeps serving (DOCS). |
| Bad release, schema fine | Render rollback. Safe because migrations are additive-only (#26F §21). Never downgrade the DB. |
| Gate misconfigured (password missing or short) | The site returns 503 everywhere except `/health` — closed, not open. Fix the variable; a restart applies it. |
| Credential leaked | Replace `ACCESS_PASSWORD` (and `OPERATOR_TOKEN` if affected) and redeploy; the old value stops working at cutover. Tell reviewers. |
| Reviewer locked out (429) | Wait 5 minutes (per-process counter); a restart also clears it. |
| Ingestion interrupted or `FAILED` | §8: check run rows, re-run. |
| Data loss or corruption | PITR to a new instance → fingerprint → `preflight` `COMPATIBLE` → repoint `DATABASE_URL` → redeploy. |
| Emergency: take everything offline | Suspend the web service in the dashboard, or unset `ACCESS_PASSWORD` (fails closed). |

---

## §11. Recurring cost

| Item | Monthly | Label |
|---|---|---|
| Hobby workspace | $0 (5 GB bandwidth, 3-day PITR) | DOCS |
| Web `0.5c-512mb` (API + frontend) | $7 | DOCS |
| Postgres `0.1c-256mb`, 1 GB | $6 (+$0.30/GB) | DOCS |
| Static site | not used | — |
| Cron (optional) | ≥ $1 | DOCS |
| Access control | $0 (application gate) | VERIFIED |
| Alternative: Render IP rules | Scale plan, $499/mo | DOCS |
| Alternative: Cloudflare Access | $0 up to 50 users, plus a domain | DOCS |
| **Total** | **≈ $13–14/month** | |

The image build uses pipeline minutes: Hobby includes 500/month, and a
build is capped at 120 minutes (DOCS). The frontend stage adds `npm ci`
and a build to every deploy.
