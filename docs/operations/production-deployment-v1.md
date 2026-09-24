# MacroChipz Production Deployment & Operations — V1

**Increment #34.** The operational companion to
`docs/product/render-production-architecture-v1.md`, which froze the
platform decisions (§1–§81) and remains authoritative for them. That
document named two implementation tasks that were never carried out —
the Dockerfile `$PORT` binding (§9) and `CORS_ALLOWED_ORIGINS` (§8) —
and this increment implements both, plus the controls the #34 audit
found were missing.

---

## §1. Architecture

```
  Browser
     │  HTTPS
     ▼
  Static site  (frontend/dist, built with VITE_API_BASE_URL baked in)
     │  HTTPS, cross-origin XHR
     ▼
  FastAPI web service  (Docker, single instance)
     │  private network
     ▼
  Managed PostgreSQL  (paid tier — backups and PITR)

  Scheduled job (cron) ──► python -m app.operations.run_maintenance
```

Deliberately absent: Kubernetes, Terraform, microservices, a message
queue, and Redis. Each was considered and rejected in ADR-033; the
short version is that a single-instance portfolio deployment gains
nothing from any of them and loses comprehensibility.

---

## §2. Threat model

**Assumed capabilities of an attacker.** Anyone on the internet can
load the frontend, call any reachable backend route directly, send
malicious bodies, attempt prompt injection, call AI endpoints
repeatedly, submit malformed identifiers and extreme pagination, and
scan the application with automated tooling. Upstream providers, the
database and the AI provider may each fail or rate-limit. Logs are read
by a human during incidents.

**Explicitly NOT assumed.** The frontend is not a security boundary. A
button not being rendered does not make an endpoint private. A prompt
is not a security boundary. Clients do not follow intended workflows.

**What is actually worth protecting**, in order:

1. **Canonical economic data.** `recorded_monitor_results` and
   `observation_versions` are non-reconstructable product history
   (ADR-025, ADR-030). Corruption or loss is the worst outcome
   available.
2. **Provider quota and spend.** FRED has a rate limit; OpenAI costs
   money per call. Both were anonymously reachable before #34.
3. **Availability.** A portfolio deployment that is down is worthless,
   but nobody is harmed.

**What is NOT in the threat model.** There are no user accounts, no
personal data, no payments and no authenticated sessions. There is
exactly one privileged actor (the operator) and everyone else is an
anonymous reader. Controls are sized to that, which is why #34 adds a
shared-secret header and not an identity system.

---

## §3. Route exposure matrix

| Route | Class | Protection |
|---|---|---|
| `GET /health` | Public | — (liveness; never touches the DB) |
| `GET /readiness` | Public | — (one indexed read; diagnostic only) |
| `GET /api/v1/monitors/inflation`, `/inflation/changes`, `/inflation/state-duration` | Public read | bounded, read-only |
| `GET /api/v1/monitors/labor`, `/labor/changes`, `/labor/state-duration` | Public read | bounded, read-only |
| `GET /api/v1/monitors/rates` | Public read | bounded, read-only |
| `GET /api/v1/monitors/{monitor}/history[/{id}]` | Public read | `limit` ≤ 100 |
| `GET /api/v1/releases` | Public read | `limit` ≤ 1000 |
| `GET /api/v1/releases/processing-status` | Public read | `limit` ≤ 100 |
| `GET /api/v1/since-last-visit` | Public read | 90-day default lookback |
| `GET /api/v1/series/{id}/observations` | Public read | `limit` ≤ 1000 |
| `GET /api/v1/series/{id}/transform` | Public read | **unpaginated** — see §11 |
| `GET /api/v1/analysis/compare` | Public read | **unpaginated** — see §11 |
| `POST /api/v1/analysis/pipeline` | Public read (compute) | body ≤ 64 KB; no provider call, no write |
| `GET /api/v1/series/search` | Public read + FRED | `limit` ≤ 50 |
| `GET /api/v1/series/{id}` | Public read + FRED | answered from FRED |
| `GET /api/v1/analyst/availability` | Public read | — |
| `POST /api/v1/analyst/explain` | **Public AI** | body ≤ 64 KB, question ≤ 500 chars, ≤ 700 output tokens, rate-limited |
| `POST /api/v1/series/{id}/sync` | **Operator write** | `X-Operator-Token` |
| `POST /api/v1/rates/sync` | **Operator write** | `X-Operator-Token` |
| `POST /api/v1/releases/sync` | **Operator write** | `X-Operator-Token` |
| `POST /api/v1/ai/query` | **Deprecated** | **not routed** (§7) |
| `/docs`, `/redoc`, `/openapi.json` | Dev only | absent in production |

No route is unclassified. Every write to canonical economic data is
either operator-authorized or CLI-only.

---

## §4. Authorization

One shared secret, `OPERATOR_TOKEN`, sent as `X-Operator-Token`,
compared with `secrets.compare_digest`. It guards the three sync
endpoints and nothing else.

```bash
curl -X POST -H "X-Operator-Token: $OPERATOR_TOKEN" \
     https://<api>/api/v1/series/PCEPILFE/sync
```

**Fail closed in production.** With `OPERATOR_TOKEN` unset and
`ENVIRONMENT=production`, those endpoints return `503` for everyone
rather than standing open. A forgotten variable then produces "my sync
returns 503", which an operator notices, instead of "anyone can drive
my FRED quota", which nobody notices.

Rejections never distinguish absent, malformed and wrong.

---

## §5. Environment contract

`.env.example` is the authoritative list with per-variable notes. In
summary:

| Variable | Class | Notes |
|---|---|---|
| `ENVIRONMENT` | Required (prod) | `production` enables closed defaults |
| `DATABASE_URL` | Required | A driverless `postgresql://` / `postgres://` URL (as platforms issue it) is rewritten to the installed psycopg 3 driver (#54A) |
| `FRED_API_KEY` | Required | |
| `CORS_ALLOWED_ORIGINS` | Required (prod) | exact origins; never `*` |
| `OPERATOR_TOKEN` | Required (prod) | else sync endpoints close |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | Optional | both needed; absent ⇒ Analyst unavailable, product unaffected |
| `APP_VERSION` | Optional | build arg; `.git` is not in the image |
| `ANALYST_MAX_OUTPUT_TOKENS`, `ANALYST_RATE_LIMIT_*` | Tuning | |
| `MAX_REQUEST_BODY_BYTES`, `DATABASE_*` | Tuning | |
| `LOG_LEVEL`, `LOG_FORMAT` | Tuning | JSON in production |
| `ENABLE_LEGACY_AI_ROUTE`, `EXPOSE_API_DOCS`, `FORWARDED_ALLOW_IPS` | Dev only | |
| `VITE_API_BASE_URL` | Frontend build | **public** — baked into client JS; never a secret |

On startup a production process logs one named error per missing
requirement. Those lines contain variable **names only**, never values,
so they are safe in a deploy log.

---

## §6. Startup and migration procedure

```
deploy → migrate (pre-deploy) → start application
```

Nothing migrates at application startup, and a test enforces that
(`tests/test_release_architecture.py`).

```bash
python -m app.operations.release preflight   # reports compatibility, changes nothing
python -m app.operations.release migrate     # gated; re-verifies afterwards; never downgrades
```

`migrate` refuses to run from an incompatible state, and exits non-zero
if the post-migration check is not `COMPATIBLE`. On the platform this is
the pre-deploy command, so a failure aborts the whole deploy and the
previous instance keeps serving (render §16).

Migrations are additive-only on the upgrade path — every `drop_*` lives
in a `downgrade()`, and no `downgrade` subcommand is exposed by the CLI.
Rollback of code is therefore always safe against a newer schema, which
is what makes `/health` (not `/readiness`) the correct routing check.

---

## §7. The superseded AI route

`POST /api/v1/ai/query` (Increment 8) is **no longer routed**. It
accepted an unbounded `message` and could issue up to five provider
calls per request, making it the largest anonymous cost surface in the
application, and #33 replaced it. The code remains in the repository —
deleting it is not this increment's job — but `app/main.py` mounts it
only when `ENABLE_LEGACY_AI_ROUTE` is set **and** the environment is not
production. It cannot be enabled in production at all.

---

## §8. Analyst cost controls

| Control | Value | Rationale |
|---|---|---|
| Question length | ≤ 500 chars | #33 |
| Request body | ≤ 64 KB | rejected before parsing |
| Output tokens | ≤ 700 | #33 bounded the input but not the answer |
| Rate limit | 10 / 60 s per client | bounds spend per caller |
| Provider timeout | 30 s | |
| Provider retries | 1, transient only | never re-runs a completed generation |
| Model calls | exactly 1 | #33 architecture |

Throttling happens **before** context assembly, so a throttled request
costs neither a query nor a token.

> **Single-instance constraint.** The rate limiter is in-process and
> per-instance (`app/api/rate_limit.py`). It is correct only for the
> one-instance deployment the frozen architecture specifies. Two
> instances would each allow the full budget. Scaling out requires
> replacing it with a shared store — that file is where the change goes,
> and it says so.

The `X-Forwarded-For` value used for bucketing is client-supplied and
forgeable. Defeating a determined evader requires a platform rate limit
or WAF; this control exists to bound accidental and casual abuse, not
to defeat a motivated attacker, and claiming otherwise would be false.

---

## §9. Health and readiness

- **`GET /health`** — process liveness. Never touches the database,
  never consults a provider, always `200` while the process is up.
  **This is the platform's traffic-routing check** (render §10).
- **`GET /readiness`** — one indexed read of `alembic_version`, compared
  with the packaged head. `200` when exactly equal; `503` with
  `schema_mismatch` / `database_unreachable` / `configuration_missing`
  otherwise. A **diagnostic and pre-deploy verification tool, never a
  routing input.**

Neither depends on FRED, Treasury or OpenAI. The Analyst being down,
unconfigured or rate-limited never makes this instance unready —
verified: with the database unreachable, `/health` stayed `200`,
`/readiness` reported `database_unreachable`, read routes returned a
contained `503`, and `/api/v1/analyst/availability` still answered
`200`.

---

## §10. Scheduler model

There is no in-process scheduler, background thread or task queue.
Maintenance is an external invocation of
`python -m app.operations.run_maintenance`, which runs exactly one
bounded sweep and exits (0 = clean, 1 = an occurrence failed, 2 =
operational failure).

**Assumption, stated explicitly: exactly one scheduler instance.**

If it fired twice anyway, the damage is bounded by an existing control
rather than by luck: each occurrence is processed under a transaction-
scoped `pg_try_advisory_xact_lock`, so the second run records a skip
instead of duplicating work. What it would *not* prevent is two
`MaintenanceSweep` rows for one window, which distorts the heartbeat
reading. That is an accepted, documented limitation and the reason the
single-instance assumption is written down rather than assumed.

No distributed locking was added: the deployment has one scheduler, and
building for a second one that does not exist would be speculative.

---

## §11. Known operational limitations

1. **Rate limiting is per-instance** (§8). Single-instance only.
2. **`GET /series/{id}/transform` and `GET /analysis/compare` are
   unpaginated** with no maximum date span. Bounded in practice because
   every curated series is monthly (hundreds of rows), so the realistic
   worst case is small. Left as-is deliberately: adding pagination to a
   working public contract is a product change, not hardening. Revisit
   before ingesting any daily series at scale.
3. **`offset` has no upper bound** on paginated endpoints. A large
   offset is a cheap indexed scan returning nothing.
4. **A null byte in a path parameter returns 500**, not a 4xx. The body
   is the standard safe static message and nothing leaks; it is a
   cosmetic status-code inaccuracy.
5. **Python build dependencies are unpinned and there is no lockfile.**
   `pip install .` resolves at build time, so two builds of the same
   commit can differ. Deferred: pinning belongs with a deliberate
   dependency-management decision, not a hardening pass.
6. **Frontend deep links need a host rewrite rule** (`/*` → `/index.html`,
   rewrite, 200). Platform configuration, not application code.

---

## §12. Security headers — who owns what

**This API owns** (set on every response, including errors):
`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
`Referrer-Policy: no-referrer`, `Permissions-Policy` denying every
browser capability.

**The API deliberately does NOT set** `Content-Security-Policy` or
`Strict-Transport-Security`. This service returns JSON, never HTML, so
a CSP on its responses protects nothing, and TLS terminates at the
platform edge which issues HSTS itself. Setting either here would be
theatre.

**The static host owns** the headers that matter for the HTML:

```
Content-Security-Policy: default-src 'self';
  script-src 'self' 'unsafe-inline';
  style-src 'self' 'unsafe-inline';
  img-src 'self' data:;
  connect-src 'self' https://<api-origin>;
  frame-ancestors 'none'; base-uri 'self'; object-src 'none'
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
Referrer-Policy: no-referrer
```

`script-src 'unsafe-inline'` is required by the pre-paint theme
bootstrap in `frontend/index.html`, which has no nonce or hash. That is
a real weakening and it is recorded here rather than hidden; removing
it means moving that script to a file or having the host inject a hash.
`connect-src` must name the API origin, since the frontend is
cross-origin by design.

---

## §13. Provider failure behaviour

| Provider | Timeout | Retries | Redirects | Size cap | On failure |
|---|---|---|---|---|---|
| FRED | 10 s | none | not followed | none | typed error → 502/503/504, static detail |
| Treasury | 30 s | none | **explicitly disabled** | 1 MB | typed error → 502, static detail |
| OpenAI | 30 s | 1 (transient only) | n/a | output-token cap | contained 503 |

Allow-lists are unchanged: no user-supplied value reaches the host or
path of any outbound request, Treasury accepts two dataset names and a
bounded month/year, and no provider error message reaches a client.

---

## §14. Observability

One structured line per request (`request_id`, method, route template,
status, duration) and one per Analyst call (request id, context type
and version, prompt version, model, duration, input/output/total
tokens, outcome, failure category, evidence offered/returned/dropped).
**They share the same `request_id`**, so the two can be joined, and it
is returned in the `X-Request-ID` response header so a user reporting a
problem can quote something that finds the exact request.

JSON in production, human-readable locally.

The route **template** is logged, never the raw path: a path contains
user-supplied identifiers and does not aggregate.

Never logged: any secret, the user's question, the model's answer, the
context packet, or any provider payload. The question's *length* is
recorded instead of its text.

> The #34 audit's most consequential finding was that none of this
> reached a handler before now. Under uvicorn's default configuration
> the root logger sits at WARNING with nothing attached to `app.*`, so
> every one of #33's carefully structured telemetry lines was silently
> discarded. `app/core/logging.py` exists to connect instrumentation
> that already existed to an output that can receive it.

---

## §15. Backup and recovery

**Source-recoverable** — re-ingestible from FRED/Treasury: series
metadata, observations, the release calendar.

**Locally unique and NOT reconstructable** — this is what makes the
database worth protecting:

- `recorded_monitor_results` — what MacroChipz concluded, and when
  (ADR-025). Cannot be recomputed, because it records a past judgement.
- `observation_versions` — what MacroChipz knew at each point in time
  (ADR-030). Re-ingestion yields today's values, not the history.
- `release_check_runs` and the release audit trail.

Losing the database therefore loses the entire point-in-time and replay
capability that #31–#32 exist to provide, permanently.

**Expectations**: managed Postgres backups and PITR, on a paid tier.
Free tiers have neither, which is why the frozen architecture rejects
them (render §11/§12). No custom backup infrastructure is built — that
is the hosting provider's job.

**Restore**: restore to a new instance, validate, repoint
`DATABASE_URL`, redeploy. **Rollback**: application rollback first;
migrations are additive-only, so rolled-back code runs safely against a
newer schema. A database downgrade is a separate, manual, case-by-case
decision — never automatic.

---

## §16. Reverse-proxy assumptions

The container binds `0.0.0.0:$PORT` and runs uvicorn with
`--proxy-headers --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-*}"`.
The quotes are load-bearing (#54A): unquoted, `sh` expanded the `*`
default into the working directory's filenames and uvicorn refused to
start.

`*` is correct **only because the platform is the sole ingress** — the
container is never exposed directly, so the only source of forwarded
headers is the platform's own proxy. In any deployment where that is
not true, `FORWARDED_ALLOW_IPS` must name the proxy explicitly.
Trusting arbitrary forwarded headers from an internet-reachable
container would let a caller spoof their apparent address.

No `TrustedHostMiddleware` is configured: the platform routes by host
to this service, so a Host-header mismatch cannot reach it, and adding
an application-level check would duplicate the edge with a second list
to keep in sync.
