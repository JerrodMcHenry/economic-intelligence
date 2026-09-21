# ADR-039: Rendering Is React Router Framework Mode with Pre-Rendering, Not FastAPI-Served HTML

## Status
Proposed (Increment #36A). **Supersedes the ADR-039 candidate named in `macrochipz-2.0-architecture.md` §29**, which proposed serving the document head from FastAPI.

## Context

The Product Constitution requires server-visible HTML for anything shareable or indexable (§23, §33, §34). Increment #36 recommended serving the HTML shell from FastAPI with a per-route rendered `<head>`. #36A was asked to challenge that, and it does not survive.

### What the repository actually is

Verified 2026-09-21, and two findings changed the analysis:

- **The frontend is Vite 8.3 + React 19.2 + `react-router-dom` 7.18.3 in declarative mode.** There is no Next.js anywhere, despite the brief's framing.
- **The production container is Python-only.** The `Dockerfile` copies `pyproject.toml`, `app/`, `alembic/` and runs `uvicorn`. No Node, no frontend build, no `StaticFiles` mount. CI references "Render's Static Site build", and `render-production-architecture-v1.md` §6 freezes the frontend as a Render Static Site with `/*` → `/index.html`.

**So the real deployment shape is a backend container plus a separate static site on a separate origin** — which is why #34 needed a CORS allowlist and why `VITE_API_BASE_URL` exists. **Any option requiring a runtime Node server introduces a third deployable that does not exist today.** That cost is invisible from a "single container image" framing and it dominates the comparison.

Three further facts:

- **The router surface in use is tiny.** Across 21 files: `BrowserRouter`, `Routes`, `Route`, `Link`, `NavLink`, `Outlet`, `MemoryRouter`. No `useNavigate`, `useParams`, `useSearchParams`, `useLocation`. All 7 routes are static paths.
- **The routes 2.0 needs do not exist yet.** There are no release-detail, revision or explainer routes. They will be written fresh whatever we choose — which lowers the cost of choosing a data-aware router now and raises the cost of choosing one later.
- **React Router's current major is 8**, and **`react-router-dom` has no 8.x release** (the package is superseded by `react-router`). The repo is on the v7 line.

### The constraint that turned out to be smaller than assumed

**React 19 hoists `<title>` and `<meta>` from anywhere in the tree into the document head**, natively, with no framework and no library ([react.dev/reference/react-dom/components/title](https://react.dev/reference/react-dom/components/title), retrieved 2026-09-21).

**Per-route dynamic metadata therefore requires no architectural change at all.** What it does *not* provide is metadata in the **initial HTML byte stream**. Googlebot does execute JavaScript, though its own documentation warns a page "may stay on this queue for a few seconds, but it can take longer than that." **Whether the social unfurl crawlers execute JavaScript could not be established from any official source** — Meta's crawler documentation does not say, and X's cards documentation returned 404. That is recorded as UNKNOWN and as a cheap empirical spike, not asserted either way.

This matters for sequencing: dynamic head is available immediately and independently; pre-rendered HTML is a second, separable step.

## Decision

**Adopt React Router framework mode (`@react-router/dev`) on the v7 line, configured `ssr: false` with `prerender`, migrated incrementally via the vendor's own component-routes guide. Generate Open Graph images at build time with Satori. Do not move presentation into FastAPI.**

### Why not FastAPI-served HTML

Route definitions and metadata would exist in Python *and* in React, with nothing keeping them in agreement. A shared secret between two languages, maintained by convention, drifting silently — on a product whose differentiator is that its claims are checkable. It also means the Python image must build and serve frontend assets, collapsing a clean separation for no product gain. **Server-rendered `<head>` alone never justified this, and the brief was right to say so.**

### Why framework mode specifically

- **The vendor publishes a migration guide from exactly our starting point** — "Framework Adoption from Component Routes." Existing `<Routes>` keep working under a catch-all route while routes migrate one at a time.
- **The official template pins our exact stack**: `vite ^8.0.3`, `react ^19.2.8`, `@tailwindcss/vite ^4.2.2`, `tailwindcss ^4.2.2`.
- **The `meta` export covers every requirement**: title, description, Open Graph, Twitter card, plus canonical links via `tagName: "link"` and JSON-LD via `script:ld+json`. Last matching route wins.
- **The competing option withdraws in our favour.** `vite-react-ssg`'s own README tells React Router v7+ users to use React Router's built-in SSG instead.

### Why the v7 line, not v8

`@react-router/dev@7.18.4` declares `vite: ^5 || ^6 || ^7 || ^8`. **Framework mode is therefore available on Vite 8 without the v8 major**, which would require rewriting `react-router-dom` imports across 21 source files plus `MemoryRouter` in the test suite.

**This decouples two migrations that have no reason to be coupled.** Adopt framework mode now; take v8 later as an isolated, mechanical codemod.

### Why `ssr: false` + `prerender`

- **It preserves the Render Static Site deployment exactly**, including the frozen `/*` rewrite (retargeted to the SPA fallback). **No Node runtime in production. No third deployable. No second runtime to patch.**
- Pre-rendering emits static HTML plus a data payload per path. Paths not pre-rendered fall back to the SPA shell.
- **Content changes on an economic release schedule — roughly 60 days a year.** A rebuild triggered by the release pipeline matches that cadence naturally.

**The decision is reversible inside the same framework.** Pre-rendered and server-rendered paths are mixable: setting `ssr: true` later turns unrendered paths into server-rendered ones with no framework migration. **That reversibility is the strongest argument here** — we are choosing the cheapest point on a path we can move along, not committing to an endpoint.

### Why not Next.js

Next.js is the most mature option and that is not in dispute. It is disproportionate here:

- **Its own migration guide deletes `vite.config.ts`**, which currently holds three unrelated concerns: the Tailwind v4 plugin, the `/api` dev proxy to FastAPI, and the entire Vitest configuration. All three must be relocated.
- **Vitest cannot test async Server Components, per Next.js's own documentation**, which recommends E2E instead. Against 821+ test declarations in 51 files, that is a larger testing regression than framework mode's.
- **ISR — the main capability Next.js offers over React Router — requires a running Node server**, is unavailable under static export, and is per-instance without a shared cache handler. At ~60 release days a year, **a rebuild covers the same ground**, and ISR may be solving a problem we do not have.
- It permanently diverges build tooling (Turbopack) from test tooling (Vite/Vitest).

### Why not Vike or TanStack Start

Vike (0.4.266) and `vite-react-ssg` (0.9.2) are both pre-1.0, and the latter defers to React Router. TanStack Start describes itself as **Release Candidate, pre-1.0**, requires discarding `react-router-dom` entirely, rewriting all routes as file-based TanStack routes, and re-harnessing ~51 test files — the largest rewrite of the four, from the least-proven option, offering nothing framework mode does not except server functions we do not need (we have FastAPI).

### Open Graph images

**Generate at build time: Satori (JSX → SVG) → `sharp` (SVG → PNG), written as static assets.**

- Satori has **zero peer dependencies** and explicitly runs in plain Node — it is not coupled to Next.js.
- **`sharp` rather than resvg**: `@resvg/resvg-js` has had **no stable release since 2024-03-26** (only alphas since), which is a supply-chain observation worth acting on. `sharp` is actively released and accepts SVG input.
- **Build time, not runtime** — no new production runtime, and OG images regenerate on exactly the same cadence as the pages they belong to.
- Authoring cards in JSX preserves design-token fidelity, which a Python-side generator would lose by duplicating token values.

**Rejected alternative worth recording: generating OG images in FastAPI.** It is genuinely attractive — zero new infrastructure on a service already running on the release schedule — and it remains the fallback if build-time generation proves painful. It was not chosen because it would duplicate the `--mc-*` design tokens into Python, creating exactly the two-language drift this ADR rejects elsewhere.

## Consequences

**Preserved:** Vite 8, Vitest + jsdom + Testing Library, `@tailwindcss/vite`, all Tailwind CSS, TypeScript 6, oxlint, the `/api` dev proxy, every presentational component, all API-client code, the static-site deployment, and the CORS/`VITE_API_BASE_URL` split.

**Changed:** `index.html` → `root.tsx`; `main.tsx` → `entry.client.tsx`; `<Routes>` → `routes.ts`, incrementally; dev/build scripts; a new `react-router.config.ts`.

**New obligations:**

1. **Build-time pre-rendering couples the frontend build to a reachable API** for the path list. CI currently validates the frontend in isolation; a build-time API outage becomes a deploy failure. Needs an explicit fallback — pre-render a known-good static subset and let the rest fall back to the SPA shell.
2. **Route modules must stay thin.** React Router's own testing guidance pushes route-module tests toward E2E, a tooling category this project does not have. Keeping loaders and `meta` in route modules and all testable logic in presentational components taking plain props keeps the existing unit tests valid. **This is a discipline we impose, not something the framework provides.**
3. **Measure `vite build` time before committing to the rebuild-per-release loop.** If build time times the pre-rendered path count becomes unacceptable, flip `ssr: true` — same framework.

**Unknowns accepted, to be resolved by spike rather than assumption:**

- Whether social unfurl crawlers execute JavaScript. Determines how urgent pre-rendering is for OG specifically. **Publish one test page and run it through each platform's debugger.**
- Whether the `reactRouter()` Vite plugin coexists with the Vitest config in the same `vite.config.ts`. May require splitting `vitest.config.ts` out. One hour.
- Whether `@vitejs/plugin-react` should sit alongside `reactRouter()` — the vendor's upgrade guide and its own default template disagree.

**Trigger to revisit:** pre-render build time becoming unacceptable, or a genuine need for per-request rendering (personalization, authenticated views). Both are handled by `ssr: true` within this same framework, which is why this decision is cheap to hold.

---

## Implementation notes (Increment #40)

Implemented as specified. `ssr: false` + `prerender`, static bundle, no Node production runtime. Full detail in `docs/architecture/rendering-and-permanent-objects.md`.

### The three open unknowns, resolved

**1. Can `reactRouter()` and Vitest share one `vite.config.ts`? — No.**

With both plugins in one config, 15 of 54 test files failed with *"React Router Vite plugin can't detect preamble"*. The configs are now split: `vite.config.ts` carries `reactRouter()` + `tailwindcss()` for dev and build; a new `vitest.config.ts` carries `@vitejs/plugin-react` + jsdom + the existing setup file for tests. Estimated at one hour; that was accurate.

**2. Should `@vitejs/plugin-react` sit alongside `reactRouter()`? — No, and it must not.**

The vendor's upgrade guide and its own default template disagree because they are answering different questions. `reactRouter()` supplies its own React transform; adding `plugin-react` beside it is what produces the preamble error. `plugin-react` belongs in the *Vitest* config, where `reactRouter()` is absent. This resolves the disagreement: neither document is wrong, they describe different configs.

**3. Do social unfurl crawlers execute JavaScript? — Still open, and now unblockable.**

This requires a public deployment to test against each platform's debugger. The metadata is correct by construction and asserted by `intelligenceMetadata.test.ts` and `scripts/verify-build-output.mjs`, but no real platform has scraped it. Carried forward as an operational limitation, not as an architectural risk — prerendering makes the answer irrelevant for correctness, only for urgency.

### The three new obligations, discharged

**1. "Build-time prerendering couples the frontend build to a reachable API. Needs an explicit fallback."**

Resolved as a three-case rule rather than one fallback: an **unset** `VITE_API_BASE_URL` prerenders nothing and the build succeeds (frontend-only CI and local dev must not need a database); a **reachable** API prerenders its objects; a **failing** API throws and fails the build. Silently shipping permanent URLs with nothing behind them is worse than a stopped deploy. `scripts/verify-build-output.mjs` then re-checks the real output — metadata present, body non-empty, no secret-shaped strings — and fails the build if not.

**2. "Route modules must stay thin."**

Held. `intelligenceObject.tsx` contains only `loader`, `clientLoader`, `meta`, the component, and two state components; every piece of logic lives in `src/lib/intelligenceLanguage.ts`, `src/lib/intelligenceMetadata.ts` and the two presentational components, all taking plain props. Consequence: no E2E harness was needed — `createRoutesStub` tests the route, and all 1,470 frontend tests including every pre-#40 test still pass.

**3. "Measure `vite build` time before committing to the rebuild-per-release loop."**

Measured. Fixed cost ~8.3 s; **marginal cost 0.31 s per object** (0.29 s prerender + 0.017 s OG card). Extrapolated: ~15 s at the current cap of 25, ~84 s at 250, ~161 s at 500. Rebuild-per-release is comfortable to roughly 250 objects and unattractive past ~500. Caveat: linear extrapolation from n ≤ 6, to be re-measured at n ≈ 100.

**The trigger to revisit is unchanged and remains cheap:** flip `ssr: true` in the same framework. Nothing in this implementation depends on `ssr: false` beyond the absence of a server.

### One correction to the ADR's "Changed" list

The ADR anticipated `<Routes>` → `routes.ts` "incrementally". In practice the existing `<App/>` tree was preserved *wholesale* under a `*?` splat route (`src/routes/catchall.tsx`), so no pre-existing route was migrated at all. Only `/intelligence/:id` is a real framework route. This is a stronger outcome than the ADR predicted: the migration's blast radius was the application shell, not the routes.

### Correction (Increment #40A)

The implementation notes above were written after a green build and were **wrong on one point**: they implied local development had been verified. It had not been run.

`npm run dev` could not serve a request. Under `ssr: false` React Router permits a `loader` export only on a route it prerenders in that same invocation, and with no `VITE_API_BASE_URL` nothing is prerendered — so the dev server printed its banner and then threw *"Invalid route exports found when prerendering with `ssr:false`"* on the first request.

This does not change the decision. `ssr: false` + prerendering stands, no Node runtime was introduced, and the escape hatch is untouched. It adds one constraint the ADR did not anticipate:

> **A route that is prerendered in some configurations and client-rendered in others cannot be a single module.** Export lists are static; React Router's validation is per-invocation. The choice must be made in `routes.ts`, which is why `src/routes.ts` is now async and reads one memoized decision shared with `react-router.config.ts`.

Removing `loader` was measured and rejected: `clientLoader` alone prerenders an empty shell with no metadata, which defeats the purpose of the ADR.

It also revises the "new obligations" scoring above. Obligation 1 (*"build-time prerendering couples the frontend build to a reachable API — needs an explicit fallback"*) was reported as discharged. It was only **half** discharged: the *build* fallback worked; the *development* fallback did not exist, because the ADR framed the coupling as a CI-and-deploy concern and never asked what a developer with no database would experience. The lesson is narrow and worth keeping: an "explicit fallback" is not verified until the fallback configuration has actually been run, not merely built.

Guarded since by `src/routes/ssrFalseExports.test.ts` and `npm run verify:spa-mode`.
