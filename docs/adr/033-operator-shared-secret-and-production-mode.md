# ADR-033: Operational Writes Are Guarded by One Shared Secret, and Production Behaviour Is Derived From a Single Environment Setting

## Status
Accepted

## Context

Increment #34's audit found that the three endpoints which drive
outbound provider traffic and write canonical economic data —
`POST /api/v1/series/{id}/sync`, `/rates/sync`, `/releases/sync` — were
reachable anonymously by anyone who knew the URL. Verified by probe:
each returned 422/404 (validation or business logic), never 401/403,
because no authentication primitive existed anywhere in the
application.

An earlier document reached the opposite conclusion.
`render-production-architecture-v1.md` §55.2/§63 describes these as
"already-public, already-safe" and specifies a plain `curl` from the
operator's machine as the bootstrap mechanism, reasoning from ADR-016
that they are idempotent and cannot corrupt data. That reasoning is
correct as far as it goes and it is not what makes them a problem.
The problem is cost and availability: a third party can drive FRED
quota to exhaustion, issue an unbounded number of Treasury fetches, and
hold database transactions open, none of which requires corrupting
anything. "Cannot break the data" is not the same as "safe to expose".

The same increment found no notion of environment anywhere: no `ENV`,
no `DEBUG`, no production branch. Nothing could conditionally close
`/docs`, require CORS, or change log format, and any such behaviour
would have had to be expressed as scattered string comparisons at each
call site.

MacroChipz's actual access model is unusually simple and worth stating,
because it determines the right size of the control: there are no user
accounts, no personal data, no payments, no sessions. There is **one
privileged actor** (the operator) and everyone else is an anonymous
reader.

## Decision

**One shared secret guards operational writes, and one environment
setting determines every production behaviour.**

- **`OPERATOR_TOKEN`, sent as `X-Operator-Token`, compared with
  `secrets.compare_digest`.** It guards the three sync endpoints and
  nothing else. Not `Authorization`: that header carries bearer/OAuth
  connotations this is not, and proxies sometimes rewrite it.

- **Fail closed in production, open in development.** With the token
  unset and `ENVIRONMENT=production`, those endpoints return `503` for
  everyone. A forgotten variable then produces a failure the operator
  notices immediately, rather than a silent public opening nobody
  notices. Unset in development they are simply open, which is harmless
  on localhost and keeps local work frictionless.

- **Rejections never explain themselves.** Absent, malformed and wrong
  tokens produce one identical response; each distinction is a small
  piece of information a prober would like.

- **`ENVIRONMENT` is the single production switch, and every behaviour
  it affects is derived in `app/core/config.py`.** Production closes
  API docs, requires CORS, fails the operator endpoints closed,
  switches logs to JSON, and refuses to mount the legacy AI route.
  Anything other than the exact string `production` — unset, a typo,
  `prod`, `staging` — is treated as NOT production, which is the safe
  direction: a typo yields an obviously-local app, never a production
  app quietly running development defaults.

- **A production process reports its own misconfiguration at startup**,
  one named error per missing requirement, naming **variables only and
  never values**, so the lines are safe in a deploy log.

- **The superseded `POST /api/v1/ai/query` is not routed.** It accepted
  an unbounded `message` and could issue up to five provider calls per
  request — the largest anonymous cost surface in the application — and
  #33 replaced it. The code stays in the repository; the route does not
  exist unless explicitly enabled outside production.

## Alternatives Considered

- **User accounts with real authentication.** Rejected as
  disproportionate by a wide margin: sessions, password storage, reset
  flows and their combined attack surface, all to protect three
  endpoints used by one person. It would add more risk than it removes.
- **OAuth / JWT.** Same objection plus an identity provider dependency,
  for a system with exactly one identity.
- **IP allowlisting.** Rejected: the operator's address is not stable,
  and the platform's own inbound rules would be the right place for
  this anyway — an application-level list duplicates the edge with a
  second thing to keep in sync.
- **Leaving them public, as `render-production-architecture-v1.md`
  §55.2 concluded.** Rejected on cost and availability grounds stated
  above. The earlier document's data-integrity reasoning is sound; it
  simply answered a different question than "should this be reachable
  by strangers".
- **Removing the sync endpoints entirely and bootstrapping only via
  CLI.** Genuinely tempting, and it would reduce the public surface to
  zero for these operations. Rejected because the frozen bootstrap
  procedure (render §55.2) depends on the HTTP path, and silently
  invalidating a frozen operational contract during a hardening pass is
  worse than guarding it. Worth revisiting deliberately.
- **Deleting the legacy AI code.** Rejected as out of scope: unmounting
  the route removes the exposure, and deleting a superseded subsystem is
  a separate decision with its own review.
- **Inferring production from the presence of `DATABASE_URL` or
  similar.** Rejected: implicit mode detection is exactly how a
  development default becomes a production one. The mode is explicit or
  it is not trustworthy.

## Consequences

- No anonymous caller can trigger ingestion, write canonical data, or
  drive provider quota. Verified by probe: all three endpoints return
  401 anonymously and with a wrong token, and 503 in production with no
  token configured.
- The operator workflow is a `curl` with one extra header — the same
  shape the frozen bootstrap procedure already assumed.
- A single grep for `is_production` shows every behaviour that differs
  in production. There is no scattered string comparison to audit.
- The shared secret is a single credential with no rotation mechanism
  beyond changing the environment variable and redeploying. That is
  acceptable for one operator and would not be for a team; it is the
  first thing to revisit if a second privileged actor ever exists.
- Public reads remain public and unauthenticated, which is the point of
  a portfolio deployment.
