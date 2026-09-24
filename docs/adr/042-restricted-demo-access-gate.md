# ADR-042: The First Deployment Is Restricted, Enforced by an Application Access Gate in Front of a Single Same-Origin Web Service

## Status
Accepted (#55A)

## Context

The first deployment exists to demonstrate the engineering, not to
launch a public product. It must keep all four worlds. Inflation and
Jobs are built on FRED-distributed data whose redistribution terms are
unresolved (#46B §D). The migration to BLS and BEA (#54B) is audited
but not approved. So **nothing the deployment holds may reach someone
who has not authenticated**: not the API, not the frontend shell, not a
generated share page, not the sitemap, not a static asset.

Not access control: an unlisted URL, `robots.txt`, `noindex`, or a
login screen drawn by the frontend. Each leaves every byte one `curl`
away.

What Render provides (official documentation, fetched 2026-09-24,
recorded in the #55A journal entry):

- **No visitor authentication for static sites or web services.** The
  only authentication features are for the Render dashboard (SSO, 2FA,
  protected environments).
- **Inbound IP rules for web services and static sites require the
  Scale plan ($499/month).** They are also allowlists, unsuited to
  reviewers on changing networks.
- **Private services are not internet-reachable**, so something public
  must still front them.
- The `onrender.com` subdomain can be disabled once a custom domain
  exists.

Cloudflare Access (free up to 50 users) can put identity in front of a
custom domain. Cloudflare's own documentation still requires the origin
to validate `Cf-Access-Jwt-Assertion` on every request, because the
origin can be reached directly. And it needs a domain on Cloudflare,
which this project does not have.

## Decision

1. **One Docker web service serves both the API and the built
   frontend.** The Render Static Site is dropped. A static site cannot
   authenticate, and the frontend is the thing most worth protecting:
   it is what renders FRED data for humans. The image builds the
   frontend in a discarded Node stage (`VITE_API_BASE_URL` empty, so
   every browser call is same-origin; no `VITE_SITE_URL`, so no sitemap
   or absolute canonical is generated). `app/web/frontend.py` serves it
   the way a static host would, with `__spa-fallback.html` for
   non-prerendered routes.
2. **`AccessGateMiddleware` runs in front of every route.** HTTP Basic
   authentication over Render's TLS; the only exemption is `/health`,
   for the platform health check. A test enumerates every route the
   application exposes and fails if any other path answers without
   credentials.
3. **Production is always restricted and fails closed.** No setting
   makes production public. With `ACCESS_PASSWORD` unset or shorter
   than 16 characters, everything except `/health` returns 503. Making
   the site public later is a deliberate code change, made once the
   data-rights question is closed.
4. **The operator boundary stays beneath it.** Reviewer credentials do
   not authorise ingestion; the sync routes still require
   `X-Operator-Token`.

## Why HTTP Basic

- It is the smallest control that is real. It is browser-native (no
  login page, no session store, no frontend change).
- The browser resends it on the frontend's own same-origin `fetch`
  calls.
- It works unchanged from `curl -u` and from the smoke test.
- It is stateless, so it survives restarts and deploys.

## Consequences

- **Accepted costs:**
  - No logout short of closing the browser.
  - One shared credential; rotation is changing an environment variable
    and redeploying.
  - The in-process lockout (10 presented-and-wrong attempts per client
    per 5 minutes) is per instance and keyed on a forgeable
    `X-Forwarded-For`. It bounds casual guessing only; the password's
    length and randomness are the real defence. Requests carrying *no*
    credentials are not counted, so anonymous traffic sharing a
    reviewer's address cannot lock the reviewer out.
- **No share-page unfurls.** Social crawlers cannot authenticate. That
  is correct for a restricted demo, and it removes the need for the API
  to be reachable at frontend build time (#46B §A.2).
- **HSTS is now sent by the application in production.** Render's
  documentation does not say its edge sends it.
- **CSP is now this service's job** (`production-deployment-v1.md` §12
  had assigned it to the static host). The same `'unsafe-inline'`
  script weakening applies.
- **Supersedes** the separate-static-site shape of #26F §6/§7 and #54A
  §5 *for restricted deployments*. It also corrects #54A's rewrite rule
  (`/*` → `/index.html`), which would not hydrate non-prerendered routes.

## Alternatives rejected

- **Render Static Site + client-side encryption (Render's blog suggests
  PageCrypt).** It protects HTML, not the API the page calls. The data
  would stay public.
- **Render inbound IP rules.** $499/month, and an allowlist rather than
  authentication.
- **Cloudflare Access alone.** Needs a Cloudflare-hosted domain, and
  the origin must still validate Cloudflare's token. A reasonable
  upgrade later: add JWT validation to this same middleware and set
  `renderSubdomainPolicy: disabled`. Nothing else changes.
- **A gateway service (Caddy/nginx with auth) in front of a private
  API.** A second billable service and a second image, to do what one
  middleware does.
- **Login form and session cookie.** Needs a login page (frontend
  change), CSRF handling and session storage — more attack surface for
  no benefit at this scale.

## Revisit when

- The FRED question is resolved (#54B migration or written
  clarification) and a public launch is intended.
- More than a handful of reviewers need individual credentials or
  revocation. Move to Cloudflare Access, or to per-reviewer credentials.
- More than one instance is run: the lockout counter is per process.
