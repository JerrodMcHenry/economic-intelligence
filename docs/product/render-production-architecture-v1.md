# Render Private-Beta Production Architecture — V1 Research & Contract Freeze

**Increment #26F.** Research + architecture + contract freeze only. No deployment performed, no Render resources created, no code modified, no secrets touched. Baseline: HEAD `f7687d2` ("Add maintenance automation readiness and health (#26E)"), clean working tree. Verified fresh this increment: backend 1,605/1,605 passed, 0 skipped; frontend 1,137/1,137; typecheck/lint/build all clean.

This document is the authoritative contract for #26G (Render infrastructure + initial deployment), #26H (production bootstrap + scheduler activation), and #26I (reliability verification + private-beta gate). It settles whether Render is the platform, the exact topology, and — the single most consequential technical question this increment exists to answer — how Increment #26C's own exact-revision-equality schema-compatibility policy interacts with Render's zero-downtime deploy model without silently stranding a serving instance.

---

## §1. Sources consulted (official Render documentation, fetched fresh this increment)

| Topic | Source |
|---|---|
| Docker web services | https://render.com/docs/web-services, https://render.com/docs/docker |
| Deploy process / pre-deploy command | https://render.com/docs/deploys |
| Health checks | https://render.com/docs/health-checks |
| Private networking | https://render.com/docs/private-network |
| Blueprint / render.yaml spec | https://render.com/docs/blueprint-spec |
| Static sites | https://render.com/docs/static-sites |
| Cron jobs | https://render.com/docs/cronjobs, https://render.com/docs/one-off-jobs |
| Postgres backups / PITR | https://render.com/docs/postgresql-backups |
| Postgres external access / IP rules | https://render.com/docs/inbound-ip-rules (via search; direct fetch 404'd, corroborated by multiple independent search results quoting near-identical language) |
| Connection pooling | https://render.com/docs/postgresql-connection-pooling |
| Notifications | https://render.com/docs/notifications |
| Rollbacks | https://render.com/docs/rollbacks |
| Environment variables / secrets | https://render.com/docs/configure-environment-variables, https://render.com/docs/environment-variables |
| Regions | https://render.com/docs/regions |
| SSH / Shell access | https://render.com/docs/ssh |
| Pricing / workspace plans | https://render.com/pricing (JS-rendered; exact figures corroborated via secondary aggregators, flagged §48 as approximate) |

Every capability claim below is either a direct quotation/paraphrase of one of these sources (cited inline by section) or explicitly marked **UNKNOWN** where the fetched material did not settle it. No claim in this document is sourced from model memory alone.

---

## §2. Baseline and fresh repository inspection

`git status --porcelain`: clean. `git log -10`: HEAD `f7687d2` (#26E), confirmed committed. Backend 1,605/1,605, frontend 1,137/1,137, typecheck/lint/build all clean — unchanged from #26E's own final state (this increment made no code changes).

Fresh inspection performed (not from memory): `Dockerfile` (confirmed: `EXPOSE 8000`, exec-form `CMD [..., "--port", "8000"]` — a fixed literal, **never reads any `PORT` environment variable**), `.dockerignore`, `.github/workflows/ci.yml`, `.github/workflows/scheduled-maintenance.yml.disabled`, `app/operations/release.py` (confirmed exact subcommands: `preflight`, `migrate` — no other arguments accepted), `app/operations/run_maintenance.py` (`--as-of-date`, `--retry-window-days`, both optional), `app/operations/maintenance_health.py` (`--json`, `--stale-threshold-hours`, `--unfinished-grace-minutes`), `app/operations/smoke_test.py` (`--base-url`, default `http://localhost:8000`), `app/core/schema_compatibility.py`, `app/main.py` (confirmed: no CORS middleware, `/health` and `/readiness` both present, no PORT-awareness), `app/core/config.py` (confirmed exact 4 backend variable names: `FRED_API_KEY`, `DATABASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL`), `app/api/series.py`/`releases.py` (confirmed exact existing public sync endpoints: `POST /api/v1/series/{series_id}/sync`, `POST /api/v1/releases/sync`), `frontend/vite.config.ts`/`frontend/.env.example` (confirmed `VITE_API_BASE_URL`, build-time only), `pyproject.toml`, `frontend/package.json`.

**One concrete, required Dockerfile fix identified, not performed this increment (research/contract only):** the current `CMD` hardcodes port `8000` and never reads Render's own `PORT` environment variable (§9/§10 below) — this must be corrected in #26G before deployment, not in #26F.

---

## §3. Render fit test

| Capability | Verdict | Evidence |
|---|---|---|
| Docker web service | **PASS** | §9 |
| Static frontend | **PASS** | §6 |
| Managed PostgreSQL | **PASS** | §11 |
| Private DB networking | **PASS** | §13 |
| Explicit migration phase | **PASS** (requires paid plan) | §15/§17 |
| Failed-migration rollout abort | **PASS** | §16 |
| Schema verification | **PASS**, with a designed policy split | §18-21 |
| Cron scheduling | **PASS** | §22 |
| Cron private-network DB access | **PASS** | §13/§22 |
| Cron single-run behavior | **PASS**, platform-guaranteed | §23 |
| Secret injection | **PASS** | §29 |
| Health checks | **PASS**, with a specific endpoint choice required | §10 |
| HTTPS | **PASS**, automatic | §37 |
| Custom domains | **PASS**, not required for V1 | §36 |
| Logs | **PASS**, dashboard-native | §38 |
| Job run history | **PASS** (cron Runs page) | §22 |
| Operator notifications | **PASS**, default email, no paid plan required for the events that matter | §39 |
| Backups | **PASS**, paid plan required | §40 |
| PITR | **PASS**, paid plan required, 3-day window on the free workspace tier | §40 |
| Restore workflow | **PASS**, restore-to-new-instance model | §41 |
| Rollback | **CONDITIONAL** — code-only, never the database; a real interaction requiring explicit design, resolved §18-24 | §18-24 |
| CI integration | **PASS** — CI remains GitHub Actions, unrelated to Render | existing #26D work |
| GitHub deployment integration | **PASS** | §33 |
| Cost | **PASS** for private-beta scale | §48-49 |
| Private-beta operational complexity | **PASS** — smallest viable topology, no HA/staging/previews added speculatively | §50/§53/§54 |

No row is FAIL. One row (Rollback/exact-equality interaction) required real design work, not assumption — resolved, not glossed over, in §18-24.

---

## §4. Freeze / reject decision

**A. FREEZE RENDER.** No hard blocker exists. The one genuinely hard question this document exists to answer — whether exact-revision-equality schema compatibility is safe under Render's zero-downtime deploy model — has a real, verified, non-hand-waved answer (§18-21): it is safe, provided (and only provided) Render's own traffic-routing health check is configured to `/health`, never `/readiness`, and provided the migration chain remains additive-only for as long as this policy holds. Both conditions are freely satisfiable and are frozen here as hard requirements, not left implicit.

---

## §5. Region

**Oregon** (`oregon`), for all three private-network-dependent services (web, Postgres, cron) — Render private networking requires same-region, same-workspace membership (§confirmed, private-network doc: "Other Render services are on the same private network if they're deployed in the same region _and_ they belong to the same workspace"). Five regions are currently available (Oregon, Ohio, Virginia USA; Frankfurt, Germany; Singapore) with no documented service-type restriction found. Oregon is chosen as Render's own original/most-documented US region — a conventional default given the app's actual user base has no evidenced geographic concentration (per this document's own explicit instruction, user location is not used as architecture evidence). Static sites are served globally via CDN regardless of region and are unaffected by this choice.

---

## §6. Frontend (Render Static Site)

Validated against the existing, unmodified frontend build (`frontend/package.json`'s own `"build": "tsc -b && vite build"` script, confirmed producing `dist/index.html` + hashed assets this session, repeatedly).

- **Root directory:** `frontend`
- **Build command:** `npm run build` (existing, unmodified)
- **Publish directory:** `dist` (Vite's own default output directory, confirmed by every local build this session)
- **API base configuration:** `VITE_API_BASE_URL`, set at build time to the deployed backend web service's own public origin — the exact, already-existing mechanism (`frontend/.env.example`), requiring zero frontend code change
- **SPA routing:** React Router (`react-router-dom`, confirmed dependency) requires a rewrite rule — **every path must rewrite to `/index.html`** (not redirect) so client-side routing resolves a direct load of e.g. `/inflation`; Render Static Sites document dashboard-configurable "redirect and rewrite rules" for exactly this purpose (§ static-sites doc) — freeze one rule: `/*` → `/index.html`, rewrite, `200`.
- **HTTPS:** automatic (Let's Encrypt/Google Trust Services, per Render's own docs), no application-level TLS handling.
- **Custom domain:** not required for V1 (§36) — the default `onrender.com` subdomain is sufficient for a private beta.

Not implemented this increment.

---

## §7. Frontend/backend origin model

**Separate origins**, e.g. `economic-intelligence.onrender.com` (static site) and `economic-intelligence-api.onrender.com` (web service) for V1 — no custom domain required yet. This is the natural, zero-extra-complexity shape given Render's own resource model (a Static Site and a Web Service are structurally separate resources with separate URLs by construction; forcing same-origin would require an additional reverse-proxy layer this project has no other reason to build). No accounts/auth exist today, so the usual same-origin-for-cookies argument does not apply; if authentication is ever added, revisit whether cookie-based session auth would want same-origin (or a `app.`/`api.` subdomain pair under one shared parent domain, which preserves independent deployability while easing a future cookie domain decision) — not a V1 concern.

---

## §8. CORS

**Required** — the separate-origin model (§7) means the browser's own same-origin policy applies. **Frozen: explicit, configured allowlist only, never a wildcard.** A new environment variable, `CORS_ALLOWED_ORIGINS` (exact name proposed here, to be added to `app/core/config.py` in #26G's own implementation, not this increment), holding the frontend's own exact deployed origin (e.g. `https://economic-intelligence.onrender.com`) — `CORSMiddleware`'s own `allow_origins` list is built from this single value (or a small comma-separated list, if a future custom domain is added alongside the `onrender.com` one). Not implemented this increment — `production-reliability-deployment-v1.md` §33 already froze this exact requirement; #26F confirms it is still correct and now names the concrete deployed origin it will hold.

---

## §9. Web service

- **Service type:** Web Service, **Docker runtime** — Render "automatically detects Dockerfiles at the root of your repo" (§ web-services doc); the existing `Dockerfile` (#26D) is reused, with one required fix (§2/§10).
- **Runtime:** the existing image, `python:3.12-slim` base, unchanged.
- **Docker command:** default `CMD` (web), unchanged in shape — only the port-binding fix (§10) is required.
- **Port behavior:** Render sets a `PORT` environment variable (default `10000`) and requires the container to bind `0.0.0.0:$PORT`; "Render is _usually_ able to detect and use" a fixed alternate port, but this is not guaranteed — **freeze: the Dockerfile's `CMD` must read `$PORT` explicitly** (e.g. shell-form `CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]`, defaulting to 8000 for unchanged local/Docker-Compose-style usage when `PORT` is unset) — a concrete, named implementation task for #26G, not performed in this contract-only increment.
- **Health-check path:** `/health`, not `/readiness` — §10, the mandatory analysis.
- **Instance count:** **1**, for private beta (§50) — no evidence justifies more.
- **Minimum compute class:** **Starter** (paid) — required, not merely preferred, because **pre-deploy commands are only available for paid web services** ("Pre-deploy commands are available for paid web services, private services, and background workers" — deploys doc) — the migration phase (§15) cannot exist on a free plan at all, settling this choice independent of raw compute need.

Not implemented this increment.

---

## §10. Health-check decision — the mandatory, non-hand-waved analysis

**Frozen: Render's own configured health-check path is `/health`, never `/readiness`.**

Restating the two routes' own frozen meanings (`production-reliability-deployment-v1.md` §15, ADR-027): `/health` = process alive, never touches the database. `/readiness` = safe to route traffic here, includes a live schema-compatibility check.

**The naive instinct — use `/readiness`, since "we generally want incompatible schema to prevent unsafe traffic" — is wrong in this specific deployment architecture, and this document says so explicitly rather than defaulting to the naive answer.** Traced precisely against Render's own documented deploy sequence (health-checks doc, deploys doc):

1. Render's pre-deploy command already runs, and already gates the entire deploy, **before any new instance is ever created**: "If any command fails or times out, the entire deploy fails... your service continues running its most recent successful deploy... with zero downtime." By the time a new instance is built at all, the migration has *already* either fully succeeded (DB now at the new code's own expected head) or the whole deploy has already been aborted with zero instance created. This means `/readiness`'s own schema check adds **no additional protection** for the new instance specifically — the pre-deploy gate already provides that protection, earlier and more completely (it prevents the new instance from ever being built at all on failure, not merely from receiving traffic).
2. Render's own ongoing health monitoring is not deploy-scoped — the health-checks doc describes it generically, for "a running service instance": "If a running service instance fails consecutive health checks for 15 seconds, Render temporarily stops routing traffic to it." Nothing in the documentation exempts an already-serving, previously-healthy instance from this monitoring merely because a *new* deploy is in progress. **This document could not obtain a source stating with total certainty whether Render literally re-polls an old, currently-serving instance's health check during the specific few-second window while a new deploy's pre-deploy command is executing** — marked **UNKNOWN** on that exact timing detail, honestly, rather than assumed either way.
3. Given that genuine uncertainty, the correct engineering response is to choose the option that is safe under **either** interpretation, not the option that is only safe under the optimistic one. If Render does *not* re-poll the old instance during this window, `/health` and `/readiness` are equivalent in effect for the old instance (harmless either way). If Render *does* re-poll it, `/readiness` would begin failing on the old instance the moment the pre-deploy migration completes (its own actual revision, now advanced, no longer equals the old code's own expected head — correctly and honestly classified `SCHEMA_AHEAD` by #26C's own exact-equality policy) — 15 seconds later, Render would stop routing to the old instance, **while the new instance has not yet been built, health-checked, or entered rotation** — a real, self-inflicted availability gap, for a database state that is not actually unsafe for the old code to keep serving against (§21).
4. `/health` is safe under both interpretations, and costs nothing: it never reflects schema state, so it can never cause this specific failure mode, and the actual protection `/readiness`'s check exists to provide is already fully delivered, earlier and more strongly, by the pre-deploy gate (§15-17).

**Frozen role split, made explicit and permanent (not merely an implementation detail):** `/health` is Render's own traffic-routing signal. `/readiness` remains real, correct, and valuable — as the pre-deploy phase's own post-migration verification check (§12 of `production-reliability-deployment-v1.md`, unchanged), and as an operator/monitoring diagnostic (`maintenance_health`, smoke tests, manual inspection) — but it must never again be assumed equivalent to "safe to route live traffic," which is a different, separately-provided property (§21).

---

## §11. Postgres

- **Plan:** paid (Basic tier or equivalent smallest paid instance) — **not free** (§12).
- **Region:** Oregon, matching web/cron (§5).
- **Storage:** smallest available tier sufficient for private-beta data volume — this project's own persisted tables (curated series/observations, release processing audit trail, `RecordedMonitorResult`) are estimated small (`automated-economic-maintenance-v1.md` §49/`recorded-state-history-v1.md` §88, both "qualitative, not measured," consistent with this project's own established estimation discipline) — no specific GB figure is frozen here; monitor actual usage post-launch rather than guessing.
- **Internal connection:** yes, exclusively, for both web and cron (§13).
- **External access policy:** deny by default (§14).
- **TLS:** enforced unconditionally — confirmed, "external connections to your database are always encrypted in transit... Render rejects external connections that set `sslmode=disable`" (inbound-ip-rules research) — internal/private connections are implicitly within Render's own private network and do not need this stated separately.
- **Backup/PITR:** paid instance + Hobby-or-higher workspace already provides logical backups (7-day retention) and PITR (3-day window on Hobby, 7-day on Pro) — §40.
- **Retention:** PITR window is workspace-plan-gated (§40), not instance-plan-gated — confirmed by research.
- **Restore workflow:** restore-to-new-instance (§41).
- **Upgrade behavior:** not required for V1; Render documents that region cannot be changed post-creation ("Render doesn't currently support changing the region for an existing service or database") — worth naming so a future region change is understood to require a genuine migration, not a setting toggle.

**`RecordedMonitorResult` is explicitly, deliberately treated as non-reconstructable historical product data (ADR-025's own already-frozen finding, restated here for infrastructure purposes) — this is the reason Postgres durability is not treated as a place to economize.** A free-tier database, which has *no* backup or PITR capability at all, would put this asset at genuine, uninsured risk from day one.

---

## §12. Free Postgres — explicitly rejected

**No.** Free Render Postgres databases have **zero** backup capability and **zero** PITR ("Render does not create logical backups for databases on the Free compute plan"; "Point-in-time recovery (PITR) is available only on paid plans"). Given §11's own finding (`RecordedMonitorResult` is non-reconstructable), choosing free Postgres to save a few dollars a month would mean the single most durability-sensitive table in this entire system has no recovery mechanism whatsoever from day one of private beta. Rejected on durability grounds, not on a vague "production should be paid" reflex — the specific, named asset at risk is stated explicitly, per this document's own instruction not to choose free "merely to save money."

---

## §13. Internal database connection

**Frozen: both the web service and the cron job connect to Postgres exclusively via Render's own internal/private connection string**, obtained via `fromDatabase: {name, property: connectionString}` in the Blueprint (confirmed exact mechanism, blueprint-spec doc) — never a manually copy-pasted value, and never the external URL for ordinary application traffic (the external URL is slower, "traverses the public internet," per Render's own connectivity guidance, and is reserved for §14's own narrow operator-debug exception). Confirmed: cron jobs *can* originate private-network connections ("Background workers and cron jobs (can only *send* requests, not receive them)" — private-network doc) — exactly the direction needed (cron → Postgres), never the reverse.

---

## §14. External database access policy

**Frozen: deny all external access by default** (`--clear-ip-allow-list`, per Render's own documented mechanism) — the migration phase (§15) runs entirely inside Render's own private network via the pre-deploy command, and neither the web service nor the cron job needs external access at all (§13). The one legitimate exception: an operator's own genuine ad hoc debugging/inspection need (e.g., a direct `psql` session from a laptop) — handled by temporarily adding the operator's own current IP via `--ip-allow-list` (CIDR notation) for the duration of that specific need, then removing it immediately afterward — never left open as a standing exception. Confirmed: even external connections, when explicitly allowed, remain TLS-enforced and credential-gated (never anonymous) — but "requires a password" is not the same as "should be reachable from anywhere," and this document does not weaken database networking merely for convenience, per its own explicit instruction.

---

## §15. Migration phase — the existing command, verified, not guessed

**Render's pre-deploy command field is set to exactly:**

```
python -m app.operations.release migrate
```

Verified directly against `app/operations/release.py`'s own `argparse` definition this turn (§2) — `migrate` is one of exactly two valid subcommands (`preflight`, `migrate`), no other flags exist or are needed; `migrate` already internally runs the identical preflight check first (§26D's own design, unmodified) and refuses to proceed on `SCHEMA_AHEAD`/`SCHEMA_AMBIGUOUS` without ever attempting a downgrade (ADR-028, unchanged). This is the exact command #26D already built and tested against real PostgreSQL (`tests/integration/test_release_cli.py`) — nothing new is invented here; #26F's own job is confirming it fits Render's pre-deploy contract, which it does exactly (a shell command, run once per deploy, before the new instance is built, with a non-zero exit failing the whole deploy).

---

## §16. Pre-deploy failure behavior

Confirmed directly from Render's own docs: "If the pre-deploy command fails, the entire deploy is canceled. Your existing service instance remains unaffected and continues running." This is **exactly** the property `production-reliability-deployment-v1.md` §13 already required ("a migration failure aborts the deployment... the old version keeps serving untouched") — Render's own platform behavior satisfies this contract natively, with zero application-level work required to enforce it.

---

## §17. Pre-deploy plan requirement

Confirmed: pre-deploy commands are available only for **paid** web services, private services, and background workers — not free-tier services. This directly settles §9's own minimum-plan requirement (Starter, paid) — not a compute-capacity decision, a feature-availability one.

---

## §18. The exact-equality / zero-downtime interaction — full analysis

Restated precisely, per this document's own mandatory instruction not to gloss over it: Render's pre-deploy command advances the database to the NEW code's own expected head **before** the new application instance is built. The OLD instance is still serving live traffic during this window and for some additional time afterward (build + health-check-gating of the new instance, per §10's own trace). Under #26C's V1 exact-equality policy, the moment the database reaches the new revision, the OLD instance's own `/readiness` check would correctly, honestly report `SCHEMA_AHEAD` — its own expected revision no longer equals the database's actual one.

**This is a real interaction, not a hypothetical — confirmed directly against this project's own already-implemented, already-tested `check_schema_compatibility` logic** (a revision the old application's own migration graph does not recognize as an ancestor of its own expected head is unconditionally classified `SCHEMA_AHEAD`, per `app/core/schema_compatibility.py`'s own `_is_ancestor` walk, verified in #26C's own real-Postgres test suite).

**Resolution, frozen (§10, restated here as the answer to this section's own question):** this interaction is resolved by **never using `/readiness` as Render's own traffic-routing signal** (`/health` is used instead), combined with **additive-only migrations remaining a hard, continuing requirement** (§7 of `production-reliability-deployment-v1.md`, reconfirmed, never a migration in the actual chain has violated it) — which is what makes the old code's own continued operation against the newer (superset) schema genuinely, functionally safe, not merely unflagged. The compatibility check itself is not weakened, softened, or made less strict anywhere — it continues to correctly, honestly report `SCHEMA_AHEAD` for the old instance during this window; what changes is that this correct, honest report is never wired to a mechanism that would act on it by cutting traffic. This is the option this document's own §18 named as "C. change the compatibility contract" — **explicitly rejected**: the contract's own definition (exact equality) is unchanged; only its **role** (diagnostic/pre-deploy-gate, never live-traffic-routing signal) is newly, formally frozen.

---

## §19. Old-instance behavior — settled

During the transition window, the old instance: (a) continues serving real traffic correctly, because Render's own routing decision is driven by `/health` (always `200`, unaffected by schema state) and because the old code, by construction, never references anything the new, additive-only migration added; (b) would correctly report `SCHEMA_AHEAD` if its own `/readiness` or `maintenance_health` were queried directly during this window — an accurate, honest, non-alarming diagnostic fact, not a production incident. Both are true simultaneously, without contradiction, because "safe to route" and "exactly in sync" are now formally two different questions (§10/§18).

---

## §20. Failed-new-deploy-after-successful-migration — settled

If the pre-deploy migration succeeds (DB now at the new revision) but the subsequent new-instance build/start/health-check fails for an unrelated reason, Render's own documented behavior applies: "if a new instance fails to start, Render cancels the deploy and maintains the previous version." The **old** instance keeps serving (§19) — now durably against a database one revision ahead of its own expectation, exactly as before, and exactly as safely, because of the same two facts (§18). **The correct operator response is to roll forward** — fix the new version's own defect and redeploy; because the database is already at the target revision, the next deploy's own pre-deploy `migrate` call finds `COMPATIBLE` immediately (§26D's own already-tested idempotent-at-head behavior) and performs zero additional migration work. A database downgrade is never the correct or required response to this specific scenario, and none is attempted, matching `docs/operations/production-release-runbook.md`'s own already-frozen rollback philosophy exactly, now confirmed to hold under this specific, concrete Render scenario rather than only in the abstract.

---

## §21. Rollback analysis, reconciling §18-20

Confirmed directly from Render's own rollback documentation: rollback reverts **code and build artifacts only** — "Disks retain state between all deploys and cannot be rolled back," and nothing in Render's own rollback mechanism touches database state at all. **This means a Render rollback to an older application version, performed at any point after a migration has advanced the database, produces the exact same `SCHEMA_AHEAD`-for-the-old-code condition already analyzed in §18-20** — and it is resolved by the identical two facts: `/health`-based routing (the rolled-back instance still serves) and additive-only migrations (it still works correctly while doing so). **This is not a coincidence — it is the same underlying property doing the same job for a third distinct trigger (ordinary rollout, failed rollout, and now operator-initiated rollback all reduce to the identical "older code, newer schema" shape)**, which is exactly why freezing the policy split at the *general* level (§10/§18), rather than patching each trigger individually, is the correct, durable fix. Render's rollback feature is confirmed safe to use for this project, under this design, without qualification beyond the standing "additive migrations only" requirement already in force.

---

## §22. Migration authority — reconfirmed exclusive

**Exactly one authority ever advances schema: Render's pre-deploy phase, running `python -m app.operations.release migrate`.** Verified, not assumed, against every other candidate: GitHub Actions CI (`.github/workflows/ci.yml`) contains zero reference to `app.operations.release`, migrates only its own ephemeral, disposable CI-local database (#26D, architecture-guarded, reconfirmed unchanged this turn); web-process startup imports neither `alembic.command` nor `app.operations.release` (#26C/#26D architecture guards, reconfirmed); the cron job runs only `run_maintenance`, which itself never imports migration machinery (#26E, architecture-guarded); manual maintenance-processing (`process_release`) likewise never migrates. No new authority is introduced by this document.

---

## §23. Cron job architecture

- **Source:** same repository/image as the web service — the existing #26D Dockerfile, unmodified beyond §10's own port fix (which does not affect the cron command path at all, since cron jobs do not bind a port).
- **Region:** Oregon, matching web/Postgres (§5) — required for private-network Postgres access.
- **Command:** exactly `python -m app.operations.run_maintenance` (verified, §2 — no arguments required; `--as-of-date` and `--retry-window-days` both default correctly for production use).
- **Schedule:** `0 * * * *` (hourly, UTC — Render cron expressions are UTC-native, confirmed) — the exact cadence already used, verbatim, in the existing inert template (`.github/workflows/scheduled-maintenance.yml.disabled`, #26E) and matching `automated-economic-maintenance-v1.md` §15's own frozen "hourly-order" cadence precisely, no invented precision.
- **Compute class:** smallest available tier — sweeps are small and bounded (§49 of the maintenance contract), billed per-second with roughly a $1/month practical minimum (§45).
- **Environment:** `DATABASE_URL` (internal, §13), `FRED_API_KEY` (§31).
- **Run history/logs:** Render's own cron Runs page (confirmed: shows run history and logs per run) — no additional tooling required for V1.

**Not activated in #26G** — see §59/§66.

---

## §24. Cron single-run guarantee — confirmed, reinforces #26E

Confirmed directly: "Render guarantees that at most one run of a given cron job is active at a given time." This is a genuine, platform-level, independent confirmation of #26E's own already-frozen decision not to add an application-level sweep lock (ADR-029) — the two guarantees are complementary, not redundant: Render's own guarantee prevents two *scheduled* invocations of the *entire sweep* from running concurrently at all; the existing occurrence-level Postgres advisory lock (ADR-024) remains the correct, independent safeguard against the narrower case of a manual CLI invocation (via SSH, §25) racing a scheduled run. Neither guarantee substitutes for the other; both were already correctly reasoned about independently, and Render's platform behavior now validates rather than changes that reasoning. No sweep-level lock is added.

---

## §25. Cron timeout

Render's own documented ceiling: active cron runs are stopped after **12 hours** — vastly more than this workload could ever need (§49 of the maintenance contract: "almost always zero-to-a-few" provider calls per sweep). No Render-specific timeout configuration is set beyond this platform default; the operationally meaningful timeout signal remains #26E's own application-level `UNFINISHED` classification (default 30-minute grace period, `app/domain/maintenance_health.py`), which fires far sooner than Render's own 12-hour ceiling ever would and is the correct, already-built mechanism for "the sweep is stuck" detection. No new setting is invented.

---

## §26. Maintenance-health access

**Via Render's own SSH/Shell feature, into the running web service instance** (confirmed: `ssh <service>@ssh.<region>.render.com`, or the Dashboard's own Shell tab — "you can initiate a shell session to your Render service from its Shell page") — an operator runs `python -m app.operations.maintenance_health --json` interactively, using the exact same image, environment variables, and private-network database access the web service itself already has, with zero new infrastructure. **Never exposed as a public HTTP endpoint** — unchanged from #26E's own decision, reconfirmed correct and now concretely satisfiable without any exception.

---

## §27. Scheduler failure alerts

Confirmed: Render's own default notifications cover both relevant events without requiring a paid plan — "A cron job execution fails" and "A running service becomes unhealthy" are both named explicitly among Render's standard notification triggers, delivered via email by default (Slack available if the workspace connects it). This satisfies `production-reliability-deployment-v1.md` §39's own minimum operator-alert requirement natively — **no bespoke Slack/webhook integration is built or required for private beta.**

---

## §28. Automatic-maintenance claim threshold — mapped onto real Render evidence

Unchanged in substance from #26E's own already-frozen threshold (ADR-029), now stated in terms of real, checkable Render facts: the "automatically maintained" claim may be made truthfully only once (1) the cron job has been enabled against the real, deployed production database (§59/§66), (2) at least two **genuinely scheduled** runs have occurred — visible on the cron's own Runs page as scheduled, not "Trigger Run"-initiated — without any human manually invoking either one, (3) each produced its own real `MaintenanceSweep` row (confirmed via `maintenance_health`, run via SSH), and (4) a subsequent `python -m app.operations.maintenance_health` run reports `HEALTHY`. A Render "Trigger Run" (the dashboard/API manual-invocation feature) is the direct platform equivalent of `workflow_dispatch` already named in #26E's own threshold — it proves configuration correctness, never scheduled automation, and must never be described as if it did.

---

## §29. Secret model (variable NAMES only)

| Variable | Web | Cron | Frontend build | Migration pre-deploy |
|---|---|---|---|---|
| `DATABASE_URL` | Yes (internal, via `fromDatabase`) | Yes (internal, via `fromDatabase`) | No | Yes (same web-service env, since pre-deploy runs in the web service's own deploy context) |
| `FRED_API_KEY` | **No** — see §31 | Yes | No | No — migration never calls FRED |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | Optional (only if the AI route is ever exposed; may be omitted entirely for private beta) | No | No | No |
| `APP_VERSION` | Yes (§32) | Yes | No | Inherited from web's own build context |
| `CORS_ALLOWED_ORIGINS` | Yes (§8, new, non-secret) | No | No | No |
| `OPERATOR_TOKEN` | Yes (§55.2, Increment #34 — **secret**, `sync: false`; unset in production closes the sync endpoints entirely) | No | **No — never exposed to the browser** | No |
| `ENVIRONMENT` | Yes (`production`, non-secret; see ADR-033) | Yes | No | Inherited from web's own deploy context |
| `VITE_API_BASE_URL` | No | No | Yes (non-secret, the deployed backend's own public URL) | No |
| `PORT` | Render-injected automatically (§10) | No (cron does not bind a port) | No | No |

`sync: false` is used for every genuinely secret value (`DATABASE_URL` is provisioned via `fromDatabase` instead, never `sync: false`, since Render already knows it — §30; `FRED_API_KEY`/`OPENAI_API_KEY` use `sync: false`, prompted once at Blueprint creation, never written into `render.yaml` itself). Never a literal secret value in any file this document produces or that #26G will produce from it.

---

## §30. `DATABASE_URL` sharing mechanism

**Render Blueprint's own `fromDatabase` reference** (confirmed exact syntax, blueprint-spec doc):

```yaml
envVars:
  - key: DATABASE_URL
    fromDatabase:
      name: economic-intelligence-db
      property: connectionString
```

Used identically on the web service and the cron job (once added, §59) — Render resolves this to the database's own internal connection string automatically; the value is never duplicated, typed by hand, or exposed in the Blueprint file itself.

---

## §31. FRED key scope — least privilege, verified against actual code paths

**The web service does not need `FRED_API_KEY` at all.** Verified directly (not assumed) against every web-service route this session has ever built: `GET /api/v1/monitors/{inflation,labor}`, `/since-last-visit`, `/releases`, `/release-processing-read/*` are all database-backed reads, never a live FRED call; `POST /api/v1/series/{id}/sync` and `POST /api/v1/releases/sync` **do** call FRED, but §55/§62 designate them as bootstrap-time, operator-invoked actions (curl'd directly against the deployed web service by an operator during bootstrap), not something the web service needs a *standing* credential for beyond that. Given this is a genuine, if narrow, tension (the sync endpoints DO exist on the web service and DO need the key when invoked) — the resolution is: **the web service DOES receive `FRED_API_KEY`, exactly because these two already-existing, operator-authorized sync endpoints require it to function** (removing it would silently break already-shipped operational functionality) — corrected from an initial narrower instinct ("web never needs it") to the verified truth ("two specific web routes do"). The cron job needs it unconditionally (`run_maintenance` always calls FRED). Neither the frontend build nor the migration pre-deploy phase ever needs it.

> **Increment #34 note.** Those two routes are no longer public: they require the `X-Operator-Token` header (§55.2, ADR-033). That narrows *who* can spend the key but not *which process* needs it, so this section's conclusion is unchanged.

---

## §32. `APP_VERSION` mapping

Render automatically sets `RENDER_GIT_COMMIT` (the deploying commit's own SHA) as a default environment variable in every service's runtime (confirmed, Render changelog/docs research) — `app/core/version.py`'s own existing resolution order (`APP_VERSION` env var, else a local `git rev-parse --short HEAD` subprocess, else `"unknown"`) should be extended, in #26G's own implementation, to check `RENDER_GIT_COMMIT` as a second-priority fallback (after an explicit `APP_VERSION` override, before the local git-subprocess attempt, which would fail anyway inside a container with no `.git` directory, §35/§40 of `production-reliability-deployment-v1.md`, unchanged). **Named as a required, small, additive code change for #26G — not performed in this contract-only increment.** No `.git` directory needs to be copied into the runtime image either way.

---

## §33. Auto-deploy

**Frozen: auto-deploy only after CI checks pass — never bare auto-deploy-on-push, never fully manual.** Render's own auto-deploy triggers on every push to the connected branch by default; this document freezes a **branch-protection-gated** model instead: the production branch (§34) requires the existing GitHub Actions CI workflow (`.github/workflows/ci.yml`, #26D — backend+frontend test/typecheck/lint/build) to pass before a merge/push reaches it, and Render auto-deploys from that already-gated branch. This is the release-safety-over-convenience choice the source prompt explicitly asks for, achieved without adding any new Render-specific gating mechanism — GitHub's own branch protection rules (a repository setting, not a code or infrastructure change) are the natural, zero-new-infrastructure way to enforce "CI passed" as a precondition, layered on top of Render's own simpler default.

---

## §34. Branch

**`main`** — the repository's own existing default branch (confirmed, git status/log throughout this whole session) — no new branching convention or environment-per-branch complexity is introduced. A single production branch matches this project's own actual team size (one operator) and avoids inventing process the private-beta scale does not need.

---

## §35. Frontend/backend deployment coupling

**Independent deployment, same commit.** The static site and the web service are both configured to auto-deploy from the same `main` branch (§33/§34), so a single merged commit triggers both deploys, but they are two separate Render resources with two separate deploy pipelines — a frontend-only change (e.g., a copy fix) does not force a backend redeploy or vice versa, and a backend deploy failure (§16) never blocks or reverts an already-succeeded frontend deploy. API compatibility risk is bounded by this project's own existing, deliberate discipline: the frontend only ever consumes already-versioned, already-stable response contracts (confirmed throughout this whole session's own frontend-backend boundary work) — no explicit versioning scheme beyond that discipline is added for V1.

---

## §36. Domain

**`onrender.com` subdomains are sufficient for private beta — no custom domain required before inviting users.** A custom domain is a pure convenience/branding decision with zero effect on security, reliability, or HTTPS (§37) — deferred until there is a real reason to invest in it (e.g., moving beyond a handful of invited users). HTTPS is unconditional either way (§37).

---

## §37. TLS

**Automatic, platform-managed, unconditional** — confirmed, "Render uses Let's Encrypt and Google Trust Services to automatically issue and renew TLS certificates for every site and service," with HTTP traffic auto-redirected to HTTPS. The application (`app/main.py`, FastAPI/Uvicorn) never terminates TLS itself and no code change is needed to satisfy `production-reliability-deployment-v1.md` §32/§43's own already-frozen "assume TLS termination at the platform edge" requirement — Render's own default behavior already satisfies it exactly.

---

## §38. Logs

Render provides dashboard-native logs for web service requests/output, pre-deploy command output, and cron job run output (confirmed, cron docs: "Your cron job's Runs page shows run history and logs for each run"). **Minimum sufficient for private beta**: default retention/visibility as provided by the chosen workspace plan (Hobby) — no external log aggregation service is added; this project's own existing operational CLIs already print safe, structured, credential-free output (#26D/#26E), which is exactly what ends up in these logs — no new logging code is required to make them useful.

---

## §39. Notifications

Covered fully by §27 — Render's own default email notifications for cron failure and service-unhealthy events, no paid plan required, no bespoke integration built.

---

## §40. Backups

**Frozen minimum for private beta:** a paid Postgres instance (§11/§12) on at least the **Hobby** workspace plan, which already provides 7-day logical backup retention (workspace-plan-independent, confirmed: "Render automatically retains logical backups for seven days after creation, regardless of your workspace plan" — applies once *any* paid instance exists) and a 3-day PITR window (Hobby-specific; Pro extends this to 7 days, not required for V1). **Existence of the feature is not, by itself, treated as satisfying the requirement** (per this document's own explicit instruction) — §41 defines the actual acceptance criterion (a real, performed restore).

---

## §41. Restore rehearsal — designed, not performed

**#26I's own job, not #26F's.** Acceptance criteria frozen here: (1) initiate a PITR or logical-backup restore targeting a **new**, separate Render Postgres instance — never the live production instance; (2) independently verify the restored instance's own data (spot-check `recorded_monitor_results`/`release_check_runs` row counts and a few specific values against what production is known to have contained at the restore point); (3) confirm the restored instance reaches a schema state the current application version considers `COMPATIBLE` (i.e., the restore did not somehow revert schema below what the running code expects); (4) discard the temporary restored instance once verified, without ever repointing any real service at it. A backup that has never been restored this way is not considered verified, per `production-reliability-deployment-v1.md` §29, restated here against a real platform.

---

## §42. Logical backup — sufficiency for V1

**PITR alone is sufficient for private-beta scale; no additional periodic logical export is required.** Render's own logical backups already run automatically (7-day retention, any paid instance) alongside PITR — this is already two independent recovery mechanisms provided by the platform at no extra operational effort; building a third, project-maintained export pipeline would be disproportionate to a 5-user private beta's own actual risk profile. Revisit if/when real user-generated data volume or a compliance requirement (neither exists today) changes this calculus.

---

## §43. Postgres plan

**Smallest paid instance tier available** (Basic/equivalent smallest tier, ~$6-7/month per §48's own sourcing) — sufficient for the small, curated data volume this project persists (§11). Not overprovisioned; monitor actual usage post-bootstrap rather than guessing a larger tier preemptively.

---

## §44. Web plan

**Starter** (smallest paid tier, ~$7/month) — required regardless of raw compute need because pre-deploy commands require a paid plan (§17); "no sleeping" is inherent to any paid web-service tier (free-tier idle-spin-down does not apply once paid); FastAPI's own memory footprint (a synchronous, non-async application per ADR-003/ADR-007, no heavy in-memory caching anywhere in this codebase) comfortably fits the smallest paid instance's own RAM allocation for a 5-user private beta's own traffic volume.

---

## §45. Cron plan

**Smallest available compute tier** — sweeps are short and bounded (§49 of the maintenance contract); Render bills cron per-second with an approximate $1/month practical floor per prior research — no larger tier is justified.

---

## §46. Frontend cost

**$0 compute** — static sites are described by Render as "fast and free to deploy," billed only for outbound bandwidth (workspace-plan-included allocation) — a 5-user private beta's own bandwidth is not expected to exceed any free allocation; flagged as usage-dependent, not a fixed line item.

---

## §47. Workspace plan

**Hobby (free)** is sufficient for private beta. It already provides: 3-day PITR (§40, adequate for early beta — the Pro-tier 7-day extension is a real but non-blocking improvement, not required to start), Blueprint support (confirmed usable in this research), standard notifications (§39), and SSH/Shell access (§26) — none of the Pro-specific features found in this research (unlimited team members at a flat $25/month, longer PITR, preview-environment notifications) are needed by a single-operator project with no team collaboration requirement today. Revisit if a second operator joins, or if the 3-day PITR window proves materially insufficient in practice.

---

## §48. Monthly cost estimate

**Pricing figures below are approximate**, sourced from secondary aggregators cross-referencing Render's own historical/current pricing structure (Render's own `/pricing` page is JS-rendered and did not yield exact figures via direct fetch this turn) — **operator should verify exact current figures directly on render.com/pricing before committing spend.**

| Item | Low estimate | Expected estimate | Notes |
|---|---|---|---|
| Workspace (Hobby) | $0 | $0 | §47 |
| Web service (Starter) | ~$7/mo | ~$7/mo | §44, fixed |
| Postgres (smallest paid) | ~$6/mo | ~$7/mo | §43, fixed compute + small storage |
| Cron job | ~$1/mo | ~$2/mo | §45, usage-dependent, bounded by short sweep duration |
| Static site | $0 | $0 | §46, bandwidth-dependent, expected negligible |
| Bandwidth overage | $0 | $0-2/mo | usage-dependent, private-beta traffic expected trivial |
| **Total** | **~$14/month** | **~$16-18/month** | |

---

## §49. Cost ceiling

**$50/month**, a product-level decision, not a technical one. The expected spend (§48, ~$16-18/month) sits comfortably under this ceiling; the ceiling itself exists to catch a genuine misconfiguration (an oversized instance chosen by mistake, an accidentally-enabled preview environment, unexpectedly high bandwidth) rather than to constrain any planned, deliberate choice this document actually makes. Exceeding it should prompt investigation, not be treated as an emergency on its own.

---

## §50. Scaling

**One web instance, for private beta, unless evidence says otherwise.** No horizontal scaling, no HA Postgres, no autoscaling configuration — none is justified by a 5-user private beta's own expected load, and adding any of it now would be exactly the "HA architecture merely for prestige" this document is explicitly told not to build. **What would trigger scaling, named explicitly:** sustained request latency or error-rate degradation under real usage (would require the monitoring named in §74's own equivalent, once built); a genuine need for zero-downtime deploys with more headroom than one replaced instance provides (not currently a private-beta requirement); more than a handful of concurrent users generating real read load beyond what a single Starter instance can serve.

---

## §51. Connection pooling — still later, now cross-checked

**Confirmed still later, not required for V1** — restated from #26D's own identical finding, now verified against Render's actual capability rather than assumed: Render Postgres supports integrated PgBouncer pooling natively (confirmed, "Render Postgres now supports integrated connection pooling with PgBouncer... at no additional cost") should it ever become necessary, using transaction-mode pooling (`pool_mode = transaction`). **A genuinely useful, freshly-verified compatibility finding, not previously checked:** this project's own occurrence-level locking already uses `pg_try_advisory_xact_lock` — a *transaction-scoped* advisory lock, whose lifetime matches exactly the unit PgBouncer's transaction-mode pooling preserves — meaning if pooling is ever enabled later, this project's own existing locking mechanism remains correct without modification (a session-scoped lock, by contrast, would have broken under transaction pooling — this was verified, not merely hoped for). Not enabled now: a single web instance + a single cron job's own modest connection footprint (SQLAlchemy's own default pool, unmodified since ADR-007) is comfortably within any Render Postgres plan's own direct connection limit.

---

## §52. Database role separation

**Still later, unchanged from #26D's own finding.** Render's own Postgres provisioning does not appear (from this research) to make creating a second, narrower-privileged runtime role meaningfully easier than doing so on any other PostgreSQL host — the decision remains gated on a real operator team and a real production incident history existing first (mirrors ADR-008's own "not a concern at this project's current single-developer stage" reasoning), not on platform capability. Not built now.

---

## §53. Staging

**No standing staging environment.** Production-only, plus the already-existing, already-proven isolated CI database (`TEST_DATABASE_URL`, #26D's own real-Postgres migration tests already exercise fresh-to-head and previous-to-head transitions on every CI run) continues to serve the "does the release process itself work" rehearsal role — a genuine second, standing Render environment would roughly double infrastructure cost and complexity for a 5-user private beta, for a benefit (rehearsing Render-specific deploy mechanics specifically) better served, when truly needed, by a **temporary**, manually created-and-torn-down environment for one specific judged-risky release (§54), not permanent infrastructure.

---

## §54. Preview environments

**Evaluated, not enabled.** Render's own Preview Environments (auto-created per pull request) would add real complexity and cost (confirmed: preview-specific notifications require a Pro workspace) without current value — this is a single-operator project without a multi-reviewer PR workflow today. Deferred; revisit if a real second contributor and a real PR-review process both exist.

---

## §55. Bootstrap — exact commands, verified

Freshly verified against actual code (§2), not guessed:

1. **Release catalog**: already seeded by the migration chain itself (three data migrations, #26D's own confirmed finding, reconfirmed unchanged) — no separate bootstrap step needed for this part.
2. **Economic observations**: `POST /api/v1/series/{series_id}/sync` (confirmed exact path, `app/api/series.py`) — called once per curated series, directly against the deployed web service's own URL. **This endpoint is operator-authorized, not public** (Increment #34, ADR-033): it requires the `X-Operator-Token` request header, whose value is the server-side production secret `OPERATOR_TOKEN`. No SSH is needed, but the header is mandatory.

   ```bash
   # OPERATOR_TOKEN is read from the operator's own environment.
   # Never paste a literal token into a command, a file, or this document.
   curl -X POST \
     -H "X-Operator-Token: $OPERATOR_TOKEN" \
     https://<web-service>.onrender.com/api/v1/series/<series-id>/sync
   ```

   **Supersedes this section's original instruction**, which described a plain unauthenticated `curl` and called this "an already-public, already-safe endpoint per ADR-016's own established rationale." ADR-016's reasoning — the write is idempotent and cannot corrupt canonical data — remains correct and is not what changed. #34's threat-model review rejected the exposure on different grounds: a stranger who knows the URL can exhaust the project's FRED quota, drive unbounded upstream requests, and hold database transactions open, none of which requires corrupting a single row. "Cannot break the data" is not the same as "safe to expose." See ADR-033 and `docs/operations/production-deployment-v1.md` §3-§4.

   Public **read** endpoints are unchanged and remain anonymously public — the monitors, history, releases, series observations and Analyst availability all require no header. Only the three sync/write endpoints are authorized. `OPERATOR_TOKEN` is a server-side secret held by the operator and by the web service's own environment; it is never issued to, needed by, or reachable from the frontend, and no browser user ever possesses it.
3. **Canonical monitor availability**: requires at least one genuine processing pass per relevant release occurrence — `python -m app.operations.process_release --occurrence-id <id>` (confirmed exact flag name), run via SSH/Shell (§26) once per currently-relevant occurrence, until Inflation and Labor both return real (non-`INSUFFICIENT_DATA`) states.

Not performed this increment — this is #26H's own scope.

---

## §56. Cold-start bar

**Frozen, restated exactly per this document's own instruction: no user is invited until Inflation works, Labor works, Releases work, Since Last Visit does not `500`, and Overview works** — verified via `python -m app.operations.smoke_test --base-url <deployed-url>` (§62) returning all-green, with the additional, explicit requirement (beyond #26D's own original smoke-test acceptance, which tolerated an honest `INSUFFICIENT_DATA` `200` on a fresh environment) that bootstrap (§55) has already completed, so the monitors are showing real, non-empty economic content, not merely a technically-successful-but-uninformative response.

---

## §57. First maintenance run — sequencing

**After bootstrap and smoke verification, never before.** Restated from ADR-029/§59-60 below: the cron job resource is not even created until this point (§59), so this is a hard sequencing fact, not merely a preference.

---

## §58. Deployment order (#26G's own exact sequence)

1. Apply the Dockerfile port fix (§9/§10) and add `CORSMiddleware` (§8) — small, named implementation tasks, part of #26G, not #26F.
2. Create/confirm the Render workspace (Hobby, §47).
3. Author `render.yaml` (§59) defining Postgres + Web Service + Static Site — **no cron job yet**.
4. Sync the Blueprint. Render provisions Postgres (empty), then builds and deploys the web service: pre-deploy runs `release migrate` against the fresh (`SCHEMA_UNINITIALIZED`) database — a state §15/§18 of `production-reliability-deployment-v1.md` already classifies as safe to migrate from — reaching `COMPATIBLE` and seeding the release catalog as a side effect (§55.1); the new instance then builds, becomes health-check-`/health`-green, and enters rotation. The static site builds and deploys independently, pointed at the new web service's own public URL via `VITE_API_BASE_URL`.
5. Operator confirms, via SSH (§26): `python -m app.operations.release preflight` reports `COMPATIBLE`; `python -m app.operations.maintenance_health` reports `NEVER_RUN` (correct and expected — §22 of #26E's own prompt, restated).
6. Operator runs `python -m app.operations.smoke_test --base-url <deployed-web-service-url>` from their own machine — expect `/health` `200`, `/readiness` `200` (`ready: true`), and every database-backed route `200` (honestly `INSUFFICIENT_DATA`/empty, since bootstrap has not run yet — acceptable at this stage per #26D's own original smoke-test tolerance, §39 of that contract).
7. **#26G ends here** — infrastructure deployed and verified schema-compatible; zero economic data yet; scheduler not present at all.

---

## §59. Blueprint activation sequencing — the cron-job exclusion, confirmed necessary

**Confirmed, not assumed: "Blueprints cannot create disabled resources — all defined services deploy immediately upon sync"** (blueprint-spec research). This directly answers this section's own question: **yes**, including the cron job in the initial `render.yaml` **would** activate it immediately upon sync — before bootstrap (§55) has run, meaning the very first scheduled sweep(s) would execute against an economically-empty database, and — more importantly — would begin accumulating `MaintenanceSweep` evidence that could later be mistaken for genuine "automatically maintained since launch" history when it actually predates real bootstrap and any human verification that the deployment even works correctly end-to-end. **Frozen: the cron job resource is deliberately excluded from #26G's own `render.yaml` entirely** (not defined with any "disabled" flag, because none exists — simply absent) and is added only in #26H, after §55-57 are already satisfied.

---

## §60. Scheduler activation — the exact split

**#26G deploys infrastructure without activating cron, exactly as this document's own instruction suggests, confirmed necessary rather than merely convenient (§59). #26H owns bootstrap (§55) and scheduler activation together**, in that order: complete bootstrap and re-verify the cold-start bar (§56) first; only then add the cron job to `render.yaml` (or create it directly via the dashboard, equally valid — §59's own constraint is about *timing*, not about which mechanism creates the resource) and sync/enable it. This is the exact split the source prompt itself proposed, confirmed correct by real platform behavior rather than assumed.

---

## §61. Render health-check configuration

`/health` (§10) — configured on the web service directly (Dashboard's own Health Checks section, or `healthCheckPath` in `render.yaml`, both confirmed available).

---

## §62. Smoke test execution model

**From the operator's own machine, against the deployed web service's own public URL** — `python -m app.operations.smoke_test --base-url https://<web-service>.onrender.com` (exact flag name confirmed, §2) — no CI or Render-job involvement required, since the smoke test is already a small, fast, read-only Python script needing only network access to the public HTTPS endpoint, which any operator machine already has. Not run automatically as part of the Render deploy pipeline itself for V1 (Render's own deploy sequence already gates on `/health` before cutover, §10/§61) — a fully automated post-deploy smoke step remains a reasonable future enhancement (e.g., a manually-triggered GitHub Actions `workflow_dispatch` job), not required for private-beta scale where a human operator is already present for every deploy.

---

## §63. Operator access — summary

No public admin API exists or is added. Every operational command (`release preflight`, `maintenance_health`, `process_release`, ad hoc `smoke_test`) runs either (a) via Render SSH/Shell into the web service instance (§26), using the exact same image/environment/private-network access the service already has, or (b) for the three sync endpoints (§55.2), an HTTPS `curl` from the operator's own machine **carrying the `X-Operator-Token` header** (Increment #34, ADR-033). Those endpoints are operator-authorized, not public; with `OPERATOR_TOKEN` unset in a production environment they refuse every request rather than standing open.

---

## §64. Database admin access

**Via Render's own Dashboard "Connect" → external connection, with the operator's own current IP temporarily allowlisted** (§14) — never a standing public opening. For most inspection needs, SSH into the web service (§26/§63) and connect to the *internal* URL directly from there is preferred (no IP-allowlist change needed at all, since the web service is already inside the private network) — the external-access path is reserved for the rarer case of needing a GUI tool (e.g., a local Postgres client) running outside any Render service.

---

## §65-71. Failure walkthroughs

| Failure | Exact behavior |
|---|---|
| **Migration** (§65) | Pre-deploy `release migrate` exits non-zero → Render cancels the entire deploy → old instance (if any) keeps serving unaffected, zero downtime (§16, confirmed platform behavior). Operator diagnoses via the pre-deploy step's own logs (§38), fixes, redeploys. |
| **Web start** (§66) | New instance fails to build/start for a reason unrelated to migration (already-successful) → Render "cancels the deploy and maintains the previous version" (confirmed) → old instance keeps serving, now potentially against an already-advanced schema, safely (§20/§21). |
| **Readiness** (§67) | `/readiness` reporting `503` on any instance is a diagnostic fact only, never a routing input (§10) — an operator investigating (via `maintenance_health`/SSH) sees the exact reason (`schema_mismatch`/`database_unreachable`/`configuration_missing`, unchanged from #26C) and acts per the existing runbook. |
| **Cron** (§68) | A failed run: Render's own default notification fires (§27/§39); the existing `run_maintenance.py` exit-code contract (0/1/2, unchanged) is visible in the run's own logs; `maintenance_health` reflects it (`DEGRADED` for occurrence-level failures, `STALE`/`UNFINISHED` for worker-level problems, unchanged from #26E). |
| **FRED** (§69) | Unchanged, existing deterministic semantics (`automated-economic-maintenance-v1.md`, #25B/#25C): a transient provider failure surfaces as `PARTIAL_FAILURE`/`FAILED_PROVIDER` on the affected `ReleaseCheckRun`(s), never silently treated as `NO_CHANGE`; the cron run itself still completes and records a `MaintenanceSweep` row with `failed_count > 0`, correctly visible via `maintenance_health` as `DEGRADED`. |
| **Database** (§70) | An unreachable database at web-request time already maps to `503` on every existing route (unchanged, established since long before this whole deployment-reliability arc); `/readiness`/`maintenance_health` both report `DATABASE_UNAVAILABLE` distinctly; the cron job and pre-deploy migration both fail loudly (exit 2) rather than silently. |
| **Frontend** (§71) | The static site is a separate resource — a frontend build/deploy failure never affects the backend's own already-serving state (§35); a runtime failure to reach the backend (e.g., a CORS misconfiguration, or the backend genuinely down) is already handled gracefully per-section by the existing `useApiResource` pattern (confirmed live during #26A: independent per-section error+Retry, never a blank page). |

---

## §72. Rollback — reconciled

Application rollback (Render's own feature, §21) remains the first, always-safe response to a bad *code* deploy, under the frozen model (§10/§18): the rolled-back instance serves correctly via `/health`-based routing regardless of the database's own current (possibly newer) revision, safe specifically because migrations stay additive-only. A database downgrade remains a separate, rare, manual, case-by-case operator decision (`docs/operations/production-release-runbook.md`, unchanged) — never automatic, never assumed necessary merely because an application rollback occurred.

---

## §73. Disaster recovery — minimum private-beta process

- **Database loss/corruption**: restore via PITR/logical backup to a new instance (§41's own acceptance criteria), validate, then repoint `DATABASE_URL` (§30) at the restored instance and redeploy.
- **Bad deployment**: application rollback (§21/§72) is the first response; a database downgrade is considered only if a specific, reviewed migration's own `downgrade()` is confirmed safe for the data actually present (unchanged philosophy).
- **Scheduler failure**: `maintenance_health` + Render's own cron-failure notifications (§27) are the detection mechanism; remediation is operator-driven (inspect logs, fix, and either wait for the next scheduled run or use "Trigger Run" for an immediate one, understanding that a triggered run does not itself satisfy the automatic-maintenance claim threshold, §28).

---

## §74. Monitoring — minimum private-beta mapping

| Concern | Mechanism |
|---|---|
| Web health/readiness | Render's own health-check monitoring (`/health`, routing) + manual/SSH `maintenance_health`/`/readiness` checks (diagnostic) |
| Deploy failures | Render's own default email notification |
| Cron failures | Render's own default email notification (§27/§39) |
| Maintenance heartbeat | `python -m app.operations.maintenance_health`, run manually via SSH on whatever cadence an operator chooses to check it (no automated periodic check built this increment — a reasonable #26I/#26E-follow-on enhancement, not required for launch) |
| Database availability | Render's own dashboard database status + the same `DATABASE_UNAVAILABLE` classification already surfaced everywhere else |

No new observability infrastructure beyond what Render already provides and what #26C-E already built.

---

## §75. Analytics

**Still not part of #26F**, restated per instruction. #26A's own runner-up candidate (product analytics + beta feedback) remains correctly sequenced after reliability, unchanged.

---

## §76. Private-beta reliability bar — translated into concrete Render checks

| #26B's own 10-item bar | Concrete Render check |
|---|---|
| All migrations applied | `python -m app.operations.release preflight` (via SSH) reports `COMPATIBLE` |
| Zero known 500s in the smoke path | `smoke_test.py` run against the real deployed URL, all green |
| Scheduler proven over N runs | Cron Runs page shows ≥2 genuinely scheduled runs; `maintenance_health` `HEALTHY` |
| Backup enabled | Paid Postgres instance confirmed in the Render dashboard |
| Restore procedure tested | §41's own rehearsal completed and documented |
| Health/readiness | `/health` configured as Render's routing check (§10/§61); `/readiness` independently confirmed `200` |
| Operator alerting | Render's own default notifications confirmed active (§27/§39) |
| Frontend/backend both deployed | Both resources green in the Render dashboard |
| HTTPS | Automatic, confirmed (§37) |
| Bootstrap complete | Cold-start bar (§56) satisfied, confirmed via smoke test showing real content |

---

## §77. Automatic-maintenance bar — translated

Restated verbatim from §28: cron enabled post-bootstrap; ≥2 genuinely scheduled (not manually triggered) runs observed; ≥2 real `MaintenanceSweep` rows confirmed; a subsequent `maintenance_health` result of `HEALTHY`.

---

## §78. Private-beta gate — what #26I must prove

All of §76 AND §77, together, against the real, deployed Render environment — not against any local or CI database. #26I's own explicit job is executing this checklist and recording the result, not designing it (already fully designed here).

---

## §79. Implementation split

**#26G — Render Infrastructure + Initial Deployment** (§58 steps 1-7: Dockerfile/CORS fixes, `render.yaml` for Postgres+Web+Static Site only, first deploy, schema verification, smoke test against an economically-empty-but-schema-correct environment).

**#26H — Production Bootstrap + Scheduler Activation** (§55 bootstrap commands executed for real; cold-start bar §56 re-verified with real content; cron job added and enabled; §57/§59/§60 sequencing followed exactly).

**#26I — Reliability Verification + Private Beta Gate** (§41 restore rehearsal; §58's own failure drills, now exercisable for real against a real environment; §76-78's own checklist executed and recorded; final GO/NO-GO for inviting the first private-beta users).

Unchanged from the source prompt's own preferred shape — nothing in this research surfaced a reason to reorder it.

---

## §80. Artifact

`docs/product/render-production-architecture-v1.md` — this document. `docs/architecture/current-architecture.md`/`request-flows.md`/`docs/ENGINEERING_JOURNAL.md` **not updated**, per explicit instruction — this is a research/contract freeze, not an implementation record.

---

## §81. GO / STOP

**GO.** Render has no hard blocker (§4). The exact-equality/zero-downtime interaction (§18-21) — explicitly named as more important than price or convenience — has been resolved with a specific, verifiable, non-hand-waved design (`/health` as Render's own routing signal; `/readiness` retained as a pre-deploy-verification and diagnostic tool, never a live-routing input; additive-only migrations continuing as a hard requirement) rather than glossed over. The one genuinely unresolved documentation ambiguity found (§10, whether Render literally re-polls an old, already-serving instance's health check during an active deploy transition) was handled by choosing the option safe under either interpretation, not by assuming the convenient one.

---

## Appendix: secret safety and version control

No `.env`/`.env.*`/credential file, Render secret value, or database password was read, printed, or logged at any point this increment — every finding above needed only variable **names** and publicly documented Render platform behavior. No Render resource was created, connected, or configured. No existing database (development or test) was migrated or otherwise modified. No production application code was changed — the Dockerfile port-binding fix and the CORS middleware addition are both named explicitly as required #26G implementation tasks, not performed here. `.github/workflows/scheduled-maintenance.yml.disabled` was not renamed or activated. Nothing in this document was committed or pushed; the working tree outside this new file was not modified.
