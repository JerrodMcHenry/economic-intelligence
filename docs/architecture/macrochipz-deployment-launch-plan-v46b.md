# MacroChipz — Deployment & Launch-Blocker Plan

**Increment #46B.** Research, architecture and specification only. No infrastructure provisioned, no service purchased, no credential configured, no migration run, no production code modified, nothing committed or pushed. Baseline: HEAD `d8ea5a8` (#46A).

**Evidence discipline.** Every claim below is marked:

- **VERIFIED** — inspected in this repository this increment, or quoted from official provider documentation fetched this increment.
- **RECOMMENDATION** — an architectural proposal, mine, open to rejection.
- **ASSUMPTION** — a working premise that has not been tested.
- **UNRESOLVED** — a question this increment could not answer, stated as a question rather than smoothed into an answer.

**No unresolved licensing question is presented as resolved.** §D is explicit about what remains open.

---

## §0. The thing to check first

**VERIFIED — nothing has ever been deployed.** The journal's increment sequence runs #26E → #27B. #26F produced a research contract; **#26G (infrastructure), #26H (bootstrap + scheduler activation) and #26I (reliability verification) never executed.** There is no `render.yaml`, no infrastructure-as-code of any kind, no production environment, no domain, no sending identity.

**VERIFIED — one thing #26F called a blocker is already fixed.** #26F §2/§10 recorded that the Dockerfile "hardcodes port 8000 and never reads Render's own `PORT`", naming it a required fix for #26G. It reads `$PORT` today:

```
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips ${FORWARDED_ALLOW_IPS:-*}"]
```

Recorded because the instruction to verify rather than assume cuts both ways: a planned fix can turn out to be done, just as a planned increment can turn out never to have run.

---

## §A. Current deployment readiness

### A.1 — Inventory

| Area | Status | Evidence |
|---|---|---|
| **Frontend build** | **READY** | `npm run build` green; output **928 KB across 37 files** — trivially within any static host's limits |
| **Prerendered routes** | **READY** | 19 pages: `/`, four worlds, `/calendar`, `/explain`, 12 explainers |
| **Prerendered intelligence objects** | **MISSING at build time** | Requires `VITE_API_BASE_URL` pointing at a **reachable** API during the build. Unset → zero object pages prerendered. See §A.2 |
| **SPA fallback** | **READY** | `__spa-fallback.html` emitted; host needs one rewrite rule |
| **FastAPI backend** | **READY** | Dockerfile reads `$PORT`, `--proxy-headers`, `--forwarded-allow-ips` |
| **PostgreSQL + Alembic** | **READY** | 13 migrations, additive-only chain, head `e7b3d51c8a94` |
| **Migration release process** | **READY (code), MISSING (platform)** | `app/operations/release.py` exists; a **pre-deploy hook** must run it, and Render free plans do not support pre-deploy commands |
| **Scheduled ingestion** | **MISSING** | `scheduled-maintenance.yml.disabled` cannot execute by construction (ADR-029). No scheduler exists |
| **Environment contract** | **READY** | `.env.example` documents every variable by name with `[REQUIRED]`/`[OPTIONAL]`/`[DEV ONLY]`/`[TUNING]` markers |
| **Production config guard** | **READY** | `production_configuration_errors()` fails startup loudly and names variables only, never values |
| **CORS** | **READY** | Exact origins only; `*` rejected; required in production |
| **Operator endpoints** | **READY** | `X-Operator-Token`, `secrets.compare_digest`, **fail-closed in production** when unset |
| **Rate limiting** | **PARTIAL — a real gap** | Only `POST /analyst/explain`. See §A.3 |
| **API response sizes** | **PARTIAL** | `/api/v1/housing` 27 KB. **`/api/v1/intelligence` 138 KB, 1,899 objects, 42 queries, ~194 ms** — unbounded by anything but a `limit` the caller chooses |
| **Health / readiness** | **READY** | `/health` unconditionally 200; `/readiness` reports schema compatibility. #26F froze: route traffic on `/health`, never `/readiness` |
| **Logging** | **READY** | Structured JSON in production, request context middleware, values never logged |
| **Monitoring / error reporting** | **MISSING** | No Sentry, no OpenTelemetry, no alerting of any kind |
| **Backups / restore** | **MISSING** | Documented as a platform feature to enable; no database exists to back up; **no restore rehearsal has ever occurred** |
| **CI** | **READY** | Backend suite against real Postgres, frontend tests, typecheck, lint, build |
| **Dependency scanning** | **MISSING** | No `pip-audit`, no `npm audit` in CI, no Dependabot config |
| **Security headers** | **READY (deliberately partial)** | `X-Content-Type-Options`, `X-Frame-Options: DENY`; CSP and HSTS omitted with documented reasoning |
| **SSRF posture** | **READY** | All three provider clients use constant base URLs; Treasury and Census additionally allow-list datasets |
| **Domain / HTTPS** | **MISSING** | No domain registered, no certificate |
| **robots.txt** | **PARTIAL — defective** | Exists, but `Sitemap: /sitemap.xml` is **relative**; the directive requires an absolute URL |
| **sitemap.xml** | **PARTIAL** | Generated only when `VITE_SITE_URL` is set; correctly derived from real prerendered HTML |
| **301 redirects** | **MISSING** | Three promised redirects are client-side `<Navigate>`, which is not a 301. See §C.3 |

### A.2 — The build-order constraint nobody has had to face yet

**VERIFIED.** `frontend/src/build/prerenderPaths.ts` fetches `/api/v1/intelligence` at **build time** to discover which permanent object pages to prerender. Two documented behaviours:

- `VITE_API_BASE_URL` unset → object pages are **not** prerendered, render client-side, build succeeds.
- Set but unreachable → the build **fails loudly**, by design.

**Consequence: the API must be deployed and reachable before the frontend can be built with prerendered object pages.** That is a hard ordering constraint on first deployment — API first, then frontend — and it means the very first frontend build either ships without permanent object pages or waits for the API.

**Why it matters beyond ordering:** permanent objects are the SHARE stage. Without prerendering, a shared link serves an application shell to a social crawler, so the unfurl has no title, no description and no image. #40 built those pages specifically to survive leaving MacroChipz; an unset build variable silently undoes that.

### A.3 — The unprotected expensive endpoint

**VERIFIED.** `GET /api/v1/intelligence` is public, unauthenticated, rate-limited by nothing, and on each call regenerates all 1,899 objects (42 queries, ~194 ms, 138 KB). The homepage calls it on every load.

On a $7 instance this is a cheap cost-and-availability amplifier: a trivial loop saturates one CPU and the workspace's 5 GB included bandwidth. **RECOMMENDATION: this is a launch blocker, not a hardening nicety.**

### A.4 — What genuinely prevents public deployment

Ordered by whether anything can proceed without them:

1. **No hosting account, no domain, no TLS** — nothing else matters first.
2. **No production database**, therefore no backup and no restore rehearsal.
3. **No rate limiting on public reads** (§A.3).
4. **Three unowned 301 redirects** (§C.3).
5. **Object-page prerendering requires a reachable API at build time** (§A.2).
6. **No scheduler** — ingestion would be manual (ADR-029).
7. **Unresolved FRED redistribution rights** for Inflation and Jobs (§D).
8. **Mobile never verified at a real viewport** (§E).

---

## §B. Hosting architecture

### B.1 — Verified provider pricing

All figures fetched from official pages this increment.

**Render** — VERIFIED:

| Resource | Price |
|---|---|
| Hobby workspace | **$0/mo + compute**, 5 GB bandwidth included |
| Pro workspace | $25/mo + compute, 25 GB bandwidth |
| Web service `0.5c-512mb` (Starter) | **$7/mo** |
| Web service `1c-2g` (Standard) | $25/mo |
| Postgres `0.1c-256mb` | **$6/mo**, 256 MB RAM, 100 connections, 1 GB SSD included |
| Postgres `0.5c-1g` | $19/mo, 1 GB RAM |
| Postgres storage beyond included | $0.30/GB |
| Static site | Free (counts against workspace bandwidth) |
| Cron job | Prorated per second, **minimum $1/mo per job** |
| Bandwidth overage | $0.15/GB |

**Render free tier** — VERIFIED, and disqualifying:

- Web services **spin down after 15 minutes idle**, ~1 minute to restart.
- 750 free instance hours per workspace per month.
- **Free Postgres expires 30 days after creation**, 14-day grace, then **deleted with all data**. 1 GB fixed.
- **No pre-deploy commands, no zero-downtime deploys, no persistent disks.** Custom domains and TLS *are* supported.

**Fly.io** — VERIFIED: usage-based, from ~$0.0000008/sec for shared-CPU 256 MB; volumes $0.15/GB-month; egress $0.02/GB (NA/EU); dedicated IPv4 $2/mo; no stated minimum spend. Managed Postgres priced separately by plan and storage (figures not extracted — **UNVERIFIED**).

**Neon Postgres** — VERIFIED: Free 0.5 GB/project, 100 CU-hours, autosuspend after 5 min (cannot be disabled), **PITR 6 hours**. Launch tier pay-as-you-go $0.106/CU-hour + $0.35/GB-month, PITR up to 7 days.

**Cloudflare Pages** — VERIFIED: 500 builds/month free, 20,000 files/site free, 25 MiB per asset, 100 custom domains, `_redirects` supports **2,000 static redirects**. No bandwidth charge documented.

### B.2 — Why the free tier is rejected, on architecture not price

**This is the instruction's point, and here it bites hard.** Render's free tier is not merely limited — it is **incompatible with what MacroChipz is**:

1. **Free Postgres is deleted after 30 days.** MacroChipz's differentiator is `observation_versions` — the append-only record of what it knew and when. A database that self-destructs monthly destroys exactly the asset the product is built on, and destroys it *silently* after a grace period. This alone ends the discussion.
2. **No pre-deploy commands** means the migration release process (#26D) has nowhere to run, and #26F froze exact-revision schema equality as the compatibility policy.
3. **15-minute spin-down with a ~1-minute cold start.** A first-time visitor arriving from a shared link waits a minute for a page that then fires five API calls. #45A already found first-screen comprehension the product's weakest stage; a cold start makes the worst measured problem worse.

### B.3 — Option 1: consolidated on Render (RECOMMENDATION)

```
Cloudflare/Render DNS  →  Render Static Site (frontend, free)
                          Render Web Service   0.5c-512mb   $7
                          Render Postgres      0.1c-256mb   $6
                          Render Cron Job      (ingestion)  $1 min
                          Hobby workspace                   $0
                                                    total ≈ $14/mo
```

| | |
|---|---|
| **Cost** | **≈$14/month** + domain (~$10–15/yr). Matches Render's own published example of ~$13/mo for Starter + Basic-256mb on Hobby. |
| **Overage risk** | Bandwidth beyond 5 GB at $0.15/GB. At 928 KB of static assets plus ~165 KB of API payload per session, **5 GB ≈ 4,500 full sessions/month**. A traffic spike from one video is the realistic overage path — **ASSUMPTION**, since no traffic exists to measure. |
| **Strengths** | One vendor, one bill, private networking between web and database, cron is a first-class resource, pre-deploy hook available on paid plans, automatic TLS, PITR on paid Postgres, deploy from Git. #26F already did the hard architectural analysis against this platform. |
| **Weaknesses** | Single-vendor concentration. Postgres at 256 MB RAM is small — adequate for 4,644 + 1,072 observation rows, **ASSUMPTION** that it stays adequate as history grows. |

### B.4 — Option 2: split hosting

```
Cloudflare Pages (frontend, free)
  + Fly.io or Render web service (API)   ~$5–7
  + Neon Postgres (Launch, pay-as-you-go) ~$5–15
  + a scheduler (GitHub Actions or Fly cron)
                                    total ≈ $10–22/mo
```

| | |
|---|---|
| **Strengths** | Cloudflare Pages is genuinely free with no documented bandwidth charge and a global CDN; `_redirects` handles the three 301s cleanly; Neon gives branching and scale-to-zero. |
| **Weaknesses** | **Three vendors, three failure domains, three billing surfaces.** Neon's autosuspend reintroduces a cold start on the database instead of the app. Neon Free's **6-hour PITR** is materially worse than a paid Render database's. Cross-vendor networking means the database is reachable from the public internet rather than a private network. |
| **Verdict** | Defensible, and genuinely cheaper if Neon stays in free bounds — but it trades operational simplicity for savings of a few dollars at a stage where operator attention is the scarcer resource. |

### B.5 — Recommendation

**RECOMMENDATION: Option 1, Render consolidated, at ≈$14/month.**

The deciding argument is not price — the two differ by single-digit dollars. It is that **#26F already performed the hard analysis against Render** and resolved the one genuinely difficult question in this stack: whether exact-revision schema compatibility is safe under a zero-downtime deploy model. Its answer was yes, conditional on routing health checks at `/health` and keeping the migration chain additive. Re-deriving that for a different platform is real work with no product return.

Cost-consciousness is served by *starting small and upgrading on evidence*: `0.5c-512mb` and `0.1c-256mb` are the entry paid tiers, and both scale up in place.

**The one thing to take from Option 2 regardless:** if static bandwidth ever becomes the cost driver, moving only the static site to Cloudflare Pages is a low-risk change that leaves the API and database untouched.

---

## §C. Public routes, sharing and SEO

### C.1 — Route serving matrix

| Route | Served as | Notes |
|---|---|---|
| `/` | Prerendered HTML shell + client fetch | Title and description baked; body fetches |
| `/inflation`, `/jobs`, `/rates`, `/housing` | Prerendered shell + client fetch | Same |
| `/calendar` | Prerendered shell + client fetch | Same |
| `/revisions` | **Client-rendered only** | **Not in `STATIC_PATHS`** — see C.4 |
| `/explain` | **Prerendered with real content** | #45B |
| `/explain/:slug` × 12 | **Prerendered with real content** | #44 |
| `/intelligence/:id` | **Prerendered only if `VITE_API_BASE_URL` was set and reachable at build** | §A.2 |
| `/overview`, `/labor`, `/releases` | **Client-side `<Navigate replace>`** | Not a 301 — see C.3 |
| Anything else | SPA fallback → 404 page with `robots: noindex` | Correct |

**Required host configuration:** one rewrite rule, `/*` → `/index.html`, **rewrite (200), never redirect** — otherwise a direct load of `/inflation` breaks.

### C.2 — Metadata and crawlers

**READY:** every prerendered route has a baked `<title>`, description, Open Graph and Twitter card tags. Absolute `og:url` and canonical are emitted **only when `VITE_SITE_URL` is configured** — #40's deliberate rule that a guessed canonical tells a crawler the page lives somewhere it does not.

**Therefore `VITE_SITE_URL` must be set at build time**, or the product ships with no canonical URLs and no absolute OG URLs. **Launch blocker.**

### C.3 — The three unowned 301s

**VERIFIED.** `rendering-and-permanent-objects.md` §19 already specifies these and states plainly that the hosting layer owns them:

```
/overview   →  /          301
/labor      →  /jobs      301
/releases   →  /calendar  301
```

A client-side `<Navigate replace>` requires JavaScript, returns 200 for the old URL, and passes no redirect signal to a crawler — so both URLs can be indexed as duplicates, which is the problem the redirects exist to prevent. **Launch blocker**, and cheap: a few lines of host configuration on either candidate platform.

### C.4 — Two defects found this increment

1. **`robots.txt` has a relative sitemap directive.** It reads `Sitemap: /sitemap.xml`; the directive requires an **absolute URL**. As written, crawlers may ignore it entirely. **RECOMMENDATION:** generate `robots.txt` at build time from `VITE_SITE_URL`, the same way the sitemap already is — and skip the directive when the variable is unset rather than emitting a broken one.

2. **`/revisions` is neither prerendered nor in the sitemap.** It is a real public route with substantial written content — #45A called its empty state the strongest single piece of writing in the product — and it is currently invisible to crawlers and unfurls. It is also now linked from all four worlds and the homepage (#45B). **RECOMMENDATION:** add it to `STATIC_PATHS`. One line, and it inherits the existing metadata path.

### C.5 — Sharing limitations to fix before launch

| Limitation | Fix |
|---|---|
| Object pages unfurl as empty shells unless built against a reachable API | Deploy API first; set `VITE_API_BASE_URL`; §A.2 |
| No canonical or absolute OG URLs without `VITE_SITE_URL` | Set it at build |
| OG images are only generated when the same variable is set | Same; `generate-og-images.mjs` skips otherwise |
| `/revisions` has no crawlable presence | C.4 |
| Old URLs indexable as duplicates | C.3 |

---

## §D. Data rights and first-party migration

### D.1 — The rule this section obeys

**Permission for one activity is never inferred from permission for another.** API access does not imply redistribution; website display does not imply email redistribution; commercial use does not imply caching.

There is, however, one legitimate inference that does hold and must be stated precisely: **for a U.S. Government work in the public domain, the underlying data carries no copyright, so the distribution channel is not itself a copyright question.** What travels with it are (a) the *terms of the API used to obtain it*, and (b) *attribution obligations*, which are contractual or policy-based rather than copyright-based.

That distinction is the whole of §D.

### D.2 — Source-by-source

| | FRED | BLS | BEA | Census | Treasury |
|---|---|---|---|---|---|
| **Underlying data** | Redistributes others' works | Public domain | Public domain | Public domain | Public domain |
| **API access** | Key required | v2 key; 500 queries/day, 50 series/query, 20 yr/request | Key; 100 req/min | Key required | **No key** |
| **Internal analysis** | Permitted | Permitted | Permitted | Permitted | Permitted |
| **Public website display** | **See D.3** | Permitted | Permitted | Permitted | Permitted |
| **Commercial website use** | **UNRESOLVED** | Permitted | Permitted — terms expressly contemplate *"not-for-profit, commercial or otherwise"* | Permitted | Permitted |
| **Email / newsletter redistribution** | **UNRESOLVED** | **Permitted** (public domain; attribution travels) | **Permitted** (same) | **Permitted** (same; notice must be displayed) | **Permitted** — Fiscal Data terms state data is *"free, without restriction, and available to copy, adapt, redistribute, or otherwise use for non-commercial or commercial purposes"* |
| **Caching / storage** | Unclear | Permitted | Permitted | Permitted | Permitted |
| **Derived calculations** | Permitted, must be labelled as ours | Permitted, labelled | Permitted, labelled | Permitted, labelled | Permitted, labelled |
| **Attribution** | FRED legend | *"Source: BLS"* + retrieval date + the **"cannot vouch"** disclaimer | Verbatim non-endorsement string | **Verbatim:** *"This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau."* | *"Source: U.S. Department of the Treasury"* |
| **Status** | **UNRESOLVED** | VERIFIED | VERIFIED | VERIFIED (#45) | VERIFIED |

### D.3 — The FRED question, stated as a question

**UNRESOLVED — and it is not resolved by this increment.** #28 recorded two clauses and rated both:

1. Apps may not *"replicate or attempt to replace the essential user experience of the FRED® API, or the FRED® or ALFRED® web sites."* Rated **High** risk. A product whose core is browsing and charting FRED series is exposed; MacroChipz's derived intelligence is differentiated, but this constrains how far it may drift toward "a nicer FRED".
2. *"Individual users of an application must use their own API key."* Rated **Medium-High** and explicitly marked **UNKNOWN — REQUIRES VERIFICATION**. Read literally it is incompatible with a single-key public product.

**What the Brief changes:** a newsletter is an additional publication channel for the same data, which *sharpens* clause 1 rather than softening it. It does not create a new question — it raises the stakes on an existing one that has been open since #28.

**What this increment did NOT do:** contact the St. Louis Fed, obtain written clarification, or read the FRED terms afresh to see whether they have changed. Each is a real action; none is engineering's to take unilaterally.

### D.4 — Which concepts depend on FRED

**VERIFIED — six of eighteen, and they are exactly the two worlds with methodologies:**

| Concept | FRED series | Actual publisher | First-party equivalent |
|---|---|---|---|
| `us.cpi.core.price-index.sa.monthly` | `CPILFESL` | **BLS** (CPI) | BLS API v2 |
| `us.cpi.headline.price-index.sa.monthly` | `CPIAUCSL` | **BLS** (CPI) | BLS API v2 |
| `us.nonfarm.payroll-employment.sa.monthly` | `PAYEMS` | **BLS** (CES) | BLS API v2 |
| `us.unemployment-rate.sa.monthly` | `UNRATE` | **BLS** (CPS) | BLS API v2 |
| `us.pce.core.price-index.sa.monthly` | `PCEPILFE` | **BEA** (NIPA) | BEA API |
| `us.pce.headline.price-index.sa.monthly` | `PCEPI` | **BEA** (NIPA) | BEA API |

Rates (6 concepts) is Treasury-direct. Housing (6 concepts) is Census-direct. **The release calendar is also FRED-sourced** (ADR-020), which is a separate dependency with a separate answer (#M4).

**The decisive observation: every one of the six is a public-domain federal work that FRED merely redistributes.** MacroChipz does not need anything proprietary to FRED. It needs a different pipe to the same public data — which is precisely what #28 recommended, #45A re-recommended, and the #M1–#M4 track already plans.

### D.5 — Migration mapped to launch dependencies

| Track | Scope | Launch dependency? |
|---|---|---|
| **#M1** — source abstraction + FRED adapter | `SeriesSource`/`ReleaseScheduleSource` protocols; pure refactor, zero behaviour change | **Prerequisite for #M2/#M3.** Not itself a launch blocker |
| **#M2** — BLS binding for Labor + cutover | Two series, one agency. Smallest real migration | **Blocker only if the Brief prints Jobs figures** |
| **#M3** — BLS + BEA for Inflation + cutover | Four series, two agencies | **Blocker only if the Brief prints Inflation figures** |
| **#M4** — provider-neutral release calendar | BLS iCal + BEA JSON; supersedes ADR-020 | **Not a launch blocker.** The calendar shows schedules, not data, and #45B already marks untracked releases honestly |

**The sequencing insight: FRED is a blocker for the Brief, not for the website.** A public website displaying FRED-derived figures is the status quo, carrying the same #28 risk it has carried since #29 — real, rated, and already accepted. Pushing those figures into email is the *new* act. So:

- **Website launch may proceed** with the FRED question open, unchanged in risk.
- **The first Brief may not print Inflation or Jobs figures** until #M2/#M3 land — or must scope itself to Rates and Housing figures with Inflation and Jobs limited to state labels and links (#46A §I).

### D.6 — Proposed migration sequence and acceptance criteria

**#M1 — Source abstraction.** *Acceptance:* zero behaviour change; golden vectors byte-identical; no service holds a concrete client type; existing tests unchanged and passing.

**#M2 — BLS for Labor.** *Acceptance:* dual bindings registered with exactly one active (ADR-034 Invariant E); both ingested over overlapping history and compared; **CES units verified against BLS's own documentation, never assumed from FRED's**; `labor_v1.0` output byte-identical across the cutover; cutover is a reversible flag; **no fabricated historical revisions** — a re-pull that changes a stored value is either a genuine revision or a unit error, and the two must be distinguished before cutover, not after.

**#M3 — BLS + BEA for Inflation.** *Acceptance:* as #M2, plus `inflation_v1.0` byte-identical, and a full-history re-pull for every seasonally adjusted series (seasonal factors revise historical values — this is the one place where "the provider changed an old number" is expected rather than alarming, and it must be **detected and versioned, never silently overwritten**).

**#M4 — Provider-neutral calendar.** *Acceptance:* calendar renders from first-party schedules; FRED release ids demoted to bindings; Census handled by an explicit named mechanism; #45B's not-tracked marking preserved.

**Invariants across all four:** source-neutral concept identity preserved (concept ids never change); observation and version semantics unchanged; frozen methodologies untouched; provenance records the *actual* provider that supplied each observation; no fabricated historical revisions.

### D.7 — What requires clarification outside engineering

1. **FRED's per-user API key clause** — written clarification from the St. Louis Fed, or a decision to accept the risk, or completion of #M2/#M3 which removes the question. **UNRESOLVED.**
2. **FRED's "essential user experience" clause** as applied to a derived-intelligence product. **UNRESOLVED.**
3. Whether a legal review is wanted before any commercial use begins at all.

---

## §E. Mobile verification

### E.1 — Why the tooling failed, diagnosed

**VERIFIED symptom**, observed identically in #45A and #45B: `resize_window` returns success, and the page then reports `window.innerWidth: 1719` with `matchMedia('(min-width: 640px)').matches === true`. In one reading `outerWidth` was 686 while `innerWidth` was 1719 — internally inconsistent.

**Diagnosis (ASSUMPTION, consistent with the evidence):** the extension resizes the OS-level browser *window*, but the page's layout viewport is decoupled from it — by a page-zoom level, a `devicePixelRatio` of 2, or because the window is in a state (maximised/fullscreen) where the resize is accepted and not applied. Resizing a window is not the same operation as **device emulation**, which overrides the layout viewport, DPR, user-agent and touch capability together. Media queries key off the layout viewport, so a window resize that does not change it changes nothing that matters.

**The conclusion that matters:** this is not a flaky tool to retry. It is the wrong mechanism, and repeating it a third time would produce the same non-result.

### E.2 — Three reliable methods

| Method | How | Confidence |
|---|---|---|
| **A real phone** | Serve the dev build on the LAN, open on an actual device | **Highest** — real viewport, real DPR, real touch, real fonts. The only one that tests tap targets honestly |
| **Chrome DevTools device toolbar** | Open DevTools, toggle device toolbar, select iPhone 14 (390×844) | High — overrides layout viewport, DPR, UA and touch together. **Manual, and that is fine** |
| **Playwright** | `devices['iPhone 14']`, headless, scripted and repeatable in CI | High — same emulation primitives, automated |

**RECOMMENDATION: DevTools device toolbar for the one-time launch verification, Playwright if mobile regressions ever recur.** Adding a browser-automation dependency to prove one layout correct once is disproportionate; adding it to stop a recurring class of defect would not be.

**The confirmation gate, stated so it cannot be skipped:** before claiming any mobile pass, the page must report `window.innerWidth === 390` **and** `matchMedia('(min-width: 640px)').matches === false`. Both. Neither #45A nor #45B could produce that, and both said so rather than claiming a pass.

### E.3 — The repeatable test

Ten surfaces × eight checks, at 390×844.

**Surfaces:** `/` · `/inflation` · `/jobs` · `/rates` · `/housing` · `/calendar` · `/revisions` · `/explain` · one explainer · one permanent intelligence object.

**Per surface:**

1. **Navigation** — hamburger opens, all six items reachable and tappable, menu closes on selection, focus is managed.
2. **Text readability** — body text ≥16 px effective; no horizontal scroll to read a sentence; 16 px side gutters intact.
3. **Charts** — viewBox aspect equals rendered aspect to three decimals; axis labels legible; the values table opens.
4. **Overflow** — `document.documentElement.scrollWidth <= clientWidth`. Tables scroll within their container, never the page.
5. **Tap targets** — every interactive element ≥44×44 px, with ≥8 px separation.
6. **Layout** — cards stack to one column; no content clipped; the pipeline diagram switches to vertical arrows.
7. **Loading / quiet / error states** — skeletons do not shift layout; the quiet lede renders; a forced API failure shows a retry control that is tappable.
8. **Sharing** — the share control is reachable; the native share sheet opens on a real device (this check is **meaningless under emulation** and requires method A).

**Record for each:** surface, viewport confirmation values, pass/fail per check, and a screenshot. **A check that cannot be performed is recorded as not performed, never as passed.**

---

## §F. Analyst launch decision

**VERIFIED:** `available: false, reason: NOT_CONFIGURED` (`OPENAI_MODEL` unset). The honest unavailable state renders — *"MacroChipz Analyst is unavailable."* with no input control. Its populated behaviour has **never been exercised** in any environment available to this work.

### Option A — Launch with the Analyst enabled

| | |
|---|---|
| **Consumer value** | Real but unmeasured. It answers questions about canonical intelligence already on screen. #45A found it **hard to discover** — three pages, below the fold — and absent from Housing by design |
| **Infrastructure** | An OpenAI key in production secrets; `OPENAI_MODEL` set; no new service |
| **Operating cost** | **The only usage-metered cost in the entire product.** Capped per answer at `ANALYST_MAX_OUTPUT_TOKENS` (700), but total cost scales with traffic and is unpredictable before traffic exists |
| **Rate limits** | 10 requests / 60 s, **in-process and per-instance** — correct only for a single instance, which the frozen architecture specifies. Horizontal scaling silently multiplies the effective limit |
| **Abuse controls** | 500-character question cap, 64 KB body cap, output token cap, bounded context. No per-user identity exists to attribute abuse to |
| **Failure modes** | Provider outage, latency spike, cost spike from scripted abuse, and a model producing a fluent wrong sentence about a number that is right beside it |
| **Testing required before launch** | Configured-state functional testing (**never performed**); refusal behaviour on out-of-context questions; rate-limit enforcement under concurrency; cost-per-answer measurement; prompt-injection resistance via question text; verification that no secret reaches a response or a log |
| **Launch scope impact** | Adds a substantial test programme and the product's only variable cost |

### Option B — Launch without it, defer

| | |
|---|---|
| **Consumer value forgone** | A feature #45A measured as hard to find and which is absent from one of four worlds. The product's thesis — SEE, UNDERSTAND, VERIFY — is carried by the deterministic layer and the explainers, not by the Analyst |
| **Infrastructure** | None. No key in production |
| **Cost** | **$0**, and the product's costs become fully fixed and predictable |
| **Failure modes** | None added |
| **Testing** | None |
| **What ships instead** | The existing honest unavailable state, already verified. **RECOMMENDATION: remove the section from world pages rather than ship a permanently-unavailable heading** — an unavailable feature advertised on three pages is worse than a feature that is absent |
| **Reversibility** | High. Enabling it later is a configuration change plus the test programme above — which would then be run against real traffic patterns rather than guesses |

### Recommendation

**RECOMMENDATION: Option B — launch without the Analyst.**

Three reasons, in order: it is the product's **only unbounded cost** at exactly the moment cost predictability matters most; its populated state has **never been tested anywhere**, so enabling it means shipping untested behaviour into the one surface that can speak in sentences; and #45A found it **barely discoverable anyway**, so the value forgone is small and measurable later.

This is a decision for the human (§L), not for engineering — but it is the one that keeps launch scope honest.

---

## §G. Security and operations

### G.1 — Launch blockers

| Control | Requirement |
|---|---|
| **Secret storage** | Platform environment variables only. Never in the repo, never in an image layer, never in a log. `production_configuration_errors()` already reports missing values **by name only** |
| **Operator endpoints** | `OPERATOR_TOKEN` set to ≥32 bytes of entropy. **VERIFIED fail-closed:** unset in production, the three sync endpoints refuse every request with 503 |
| **Public API rate limits** | **The one genuinely missing control (§A.3).** A per-IP fixed-window limit on public read endpoints, reusing the existing `FixedWindowRateLimiter`, plus a hard server-side ceiling on `/api/v1/intelligence` regardless of the `limit` parameter |
| **CORS** | Exact origins. `*` already rejected at startup |
| **Request validation** | Pydantic throughout; 64 KB body cap; operator routes typed and bounded |
| **SSRF** | **Already adequate.** Constant base URLs in all three clients; Treasury and Census allow-list datasets. The one user-influenced outbound path (`/series/{id}/sync` → FRED) is operator-gated |
| **TLS** | Platform-managed; HTTPS-only |
| **Migrations** | Pre-deploy hook running the existing release process. **Requires a paid plan** |
| **Backups** | Managed Postgres automated backups **enabled and verified present** |
| **Restore rehearsal** | **Restore to a scratch instance and verify row counts before public launch.** A backup that has never been restored is a belief, not a control |
| **Health check routing** | `/health`, never `/readiness` — #26F's frozen requirement |

### G.2 — Safely after launch

Dependency scanning in CI (`pip-audit`, `npm audit`, or Dependabot — **currently absent**) · error reporting (Sentry or equivalent — **currently absent**) · uptime monitoring and alerting · Content-Security-Policy (deliberately omitted today; needs care with the theme-init inline script) · HSTS once the domain is stable · log aggregation beyond platform-native · a documented incident runbook with named severities.

**Deliberately not built:** WAF, DDoS appliance, SIEM, secret-rotation automation, multi-region. #45A's warning against enterprise infrastructure applies to operations as much as to features.

### G.3 — Ingestion and source outages

Already handled in code and needing no new work: per-dataset failure isolation (Rates), typed provider errors with credential redaction (Census), bounded retry on timeout only, run-level audit rows recording status and error **class name** only.

**Missing:** anything that tells a human a sync failed. With no scheduler and no alerting, a failed ingestion is silent until someone looks at a page and notices stale data. **RECOMMENDATION: cron job failure notification is the minimum viable alert**, and Render surfaces job run history natively.

---

## §H. Brief readiness — what must exist before #46C

#46A specified the Brief. These are the deployment decisions that must be settled **now** because retrofitting them is expensive.

| Requirement | Decision needed at deployment time |
|---|---|
| **Persistent storage for `BriefEdition`** | The database must be on a plan with **real backups and PITR** before any edition is sent. An immutable record of what was published is worthless if the store is disposable — and it is the same argument that disqualifies free Postgres (§B.2) |
| **A verified sending domain** | Choose the domain **now**, because SPF, DKIM and DMARC are DNS records on the same domain the site uses. Deciding the domain late means redoing reputation work |
| **Subdomain strategy** | Decide whether mail sends from the apex or a subdomain before DNS is configured. **UNRESOLVED — a human decision** |
| **Double opt-in** | Needs a working outbound path and a public confirmation URL, i.e. the site must be deployed first |
| **Unsubscribe** | Needs a **public endpoint accepting POST** (RFC 8058 one-click). Confirms the API must be publicly routable, not private |
| **Human editorial review** | Needs an operator path to compose, review and approve a draft — the existing operator-token CLI pattern extends to it. **No scheduler required**, which is why #46A sequenced it this way |
| **Idempotent delivery** | `(edition, subscriber)` uniqueness — a database constraint, needing only a migration |
| **Bounce and complaint handling** | Needs a **publicly reachable webhook endpoint** with provider signature verification. A second public surface requiring its own rate limiting |
| **Delivery logs** | Additional rows; negligible storage. Retention policy is a decision, not infrastructure |
| **Evidence links** | **Depends on §A.2 and §C.5.** A Brief links to permanent public pages; if those pages unfurl as empty shells, the Brief's central promise — *here is how you check it yourself* — degrades at exactly the moment it matters |

**Prerequisites for #46C to begin, concretely:** the site is publicly deployed and reachable · a domain is chosen and DNS is controlled · the database is on a backed-up plan with a verified restore · permanent object pages prerender correctly · the FRED question is resolved **or** the first Brief is scoped to Rates and Housing figures.

---

## §I. Implementation roadmap

### 1 — Must complete before public deployment

| Step | Acceptance | Depends on |
|---|---|---|
| **1.1** Choose hosting, register domain, control DNS | Domain resolves; TLS issued | Human decision (§L.1, §L.2) |
| **1.2** Provision Postgres (paid tier), run migrations via pre-deploy | `alembic current` = `e7b3d51c8a94`; `/readiness` reports COMPATIBLE | 1.1 |
| **1.3** Deploy the API; health check on `/health` | `/health` 200; `/api/v1/housing` returns data; CORS allows only the site origin; `OPERATOR_TOKEN` set and an unauthenticated sync attempt returns 401 | 1.2 |
| **1.4** **Add public read rate limiting + a hard server-side cap on `/api/v1/intelligence`** | Limit enforced under concurrency; a request for `limit=100000` is capped; existing tests pass | 1.3 |
| **1.5** Build the frontend with `VITE_API_BASE_URL` and `VITE_SITE_URL` set | ≥1 prerendered object page; canonical and absolute OG on every prerendered route; `sitemap.xml` written | 1.3 |
| **1.6** Deploy the static site with the SPA rewrite and **three 301 redirects** | `curl -I /overview` → `301` with `Location: /` (and `/labor`, `/releases`); a direct load of `/inflation` renders | 1.5 |
| **1.7** Fix `robots.txt` to emit an **absolute** sitemap URL; add `/revisions` to `STATIC_PATHS` | `robots.txt` names an absolute URL; `/revisions` prerenders and appears in the sitemap | 1.5 |
| **1.8** Enable automated backups; **perform a restore rehearsal** | A restore to a scratch instance reproduces row counts; date recorded in the runbook | 1.2 |
| **1.9** **Genuine 390 px mobile verification** across ten surfaces | `innerWidth === 390` **and** `matchMedia('(min-width: 640px)') === false` confirmed; all eight checks recorded per surface | 1.6 |
| **1.10** Smoke test against production | The existing smoke test passes; all four worlds render real data | 1.6 |

### 2 — Must complete before the first Brief

| Step | Acceptance |
|---|---|
| **2.1** Resolve the FRED question, **or** scope the first Brief to Rates and Housing figures | A written decision recorded in §11A of the #28 artifact |
| **2.2** *(if migrating)* #M1 → #M2 → #M3 with §D.6's acceptance criteria | Methodology outputs byte-identical; no fabricated revisions |
| **2.3** Verify the sending domain (SPF, DKIM, DMARC) | Authentication passes on a test send |
| **2.4** Select an email provider and read its permitted-use terms | Terms read and recorded; #46A §E.2 marked them **UNVERIFIED** |
| **2.5** Implement #46C per the #46A specification | #46A §J's acceptance criteria |

### 3 — Can safely follow launch

Dependency scanning in CI · error reporting · uptime alerting · CSP and HSTS · scheduler activation (ADR-029's blocker is resolved once a production database exists, but manual ingestion is acceptable at launch cadence) · #M4 calendar migration · log aggregation · a second region or any scaling work.

### 4 — Requires a human decision

See §L.

**Explicitly NOT in scope:** Consumer, Growth, Energy and Expectations worlds; any new data source beyond the BLS and BEA bindings needed to resolve the FRED blocker; automated Follow; any AI capability.

---

## §J. Cost summary

| Item | Monthly | Confidence |
|---|---|---|
| Render Hobby workspace | $0 | VERIFIED |
| Web service `0.5c-512mb` | $7 | VERIFIED |
| Postgres `0.1c-256mb` | $6 | VERIFIED |
| Cron job (ingestion) | $1 minimum | VERIFIED |
| Static site | $0 | VERIFIED |
| **Subtotal** | **≈$14** | |
| Domain | ~$1/mo amortised | ASSUMPTION |
| Email provider (from #46C) | $0–15 | VERIFIED pricing, plan not chosen |
| Analyst | $0 under Option B | Recommendation |
| **Total at launch** | **≈$15/month** | |

**Overage risks:** bandwidth beyond 5 GB at $0.15/GB — roughly 4,500 sessions/month at measured payload sizes (**ASSUMPTION**: no traffic exists to measure) · Postgres storage beyond 1 GB at $0.30/GB — current data is far below this · a traffic spike from video distribution is the realistic path to both, and §A.3's rate limiting is the mitigation.

---

## §K. Unresolved, carried forward

1. **FRED redistribution rights** (§D.3) — open since #28, now with a second channel depending on it.
2. **Mobile verification** (§E) — failed twice; a method now exists but has not been executed.
3. **Analyst populated-state testing** (§F) — never performed anywhere.
4. **Point-in-time replay has no consumer surface** — deliberately, since #45B.
5. **Email provider permitted-use terms** — #46A marked every candidate **UNVERIFIED**.
6. **No traffic data exists**, so every capacity and bandwidth estimate here is an assumption. The correct response is to launch small and measure, not to estimate harder.

---

## §L. Open decisions requiring approval

1. **Hosting**: Render consolidated at ≈$14/mo (recommended), or split hosting at ≈$10–22/mo across three vendors.
2. **Domain name**, and whether mail sends from the apex or a subdomain (§H).
3. **Analyst at launch**: Option A or **Option B (recommended)** — and if B, whether to remove the section from world pages.
4. **FRED**: seek written clarification · accept the risk for the website and scope the first Brief around it · or fund #M1–#M3 before the Brief.
5. **Who performs the mobile verification**, and on what device.
6. **Whether a legal review is wanted** before commercial operation begins.
7. **Launch gate**: is a verified restore rehearsal a hard blocker? *(Recommendation: yes.)*

---

## Confirmations

- **Nothing deployed, provisioned, purchased or configured.** No credential touched.
- **No production code modified. No migration created. Nothing committed or pushed.**
- **No `.env` value read, printed or exposed.** Environment variables are referred to by name only throughout.
- **No unresolved licensing question is presented as resolved** — §D.3 and §K state the FRED question as open.
- Verified facts, recommendations and assumptions are labelled individually.
