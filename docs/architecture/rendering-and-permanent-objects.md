# Rendering and Permanent Intelligence Objects

**Status:** implemented (Increment #40), corrected by #40A (§16), consumer presentation pass in #40B (§17), visual evidence in #40C (§18), consumer IA in #41 (§19-20)
**Implements:** ADR-039 (React Router framework mode with prerendering), ADR-041 (charting — not yet exercised)
**Consumes:** #39 Structured Intelligence Layer, #37 measurement foundation
**Supersedes for the frontend shell:** the `index.html` + `main.tsx` SPA bootstrap

---

## 1. What this increment actually did

It gave MacroChipz its first **permanent, shareable, crawlable URL for a single economic fact**:

```
/intelligence/rates%3AUST_NOMINAL_10Y%3A2026-09-18
```

That one sentence hides four separate capabilities that did not exist before:

| Capability | Before #40 | After #40 |
| --- | --- | --- |
| A URL for one fact | none — only world pages | `/intelligence/:id`, permanent |
| HTML a crawler can read | empty `<div id="root">` | full prerendered page |
| Per-page metadata | one site-wide title | per-object title, description, OG, canonical |
| A share affordance | none | Web Share API + clipboard fallback |

Everything else about the product is unchanged. The three world pages, the release pages, the API client, the design system and all existing tests render exactly as they did.

---

## 2. Why the frontend moved to framework mode

The old SPA shipped a single `index.html` whose body was an empty root div. That is fine for an application and fatal for a *publication*. A shared link is scraped by a crawler that may not execute JavaScript, and even when it does, the unfurl is generated from whatever was in the initial HTML.

The alternatives considered and rejected in ADR-039 stay rejected:

- **A Node production runtime / SSR.** Explicitly out of scope: it adds a server to operate, and nothing on this page is personalised or authenticated. Prerendering gives the same HTML with no runtime.
- **Rendering the frontend from FastAPI.** Would put templating in the economic engine, which is exactly the coupling the layering rules exist to prevent.
- **Next.js.** A whole framework migration to obtain one capability React Router already has.

`ssr: false` + `prerender` is the smallest configuration that produces real HTML, and it keeps the deployment a **static bundle on a CDN** — the same deployment model as before.

### 2.1 What the migration changed

| File | Change |
| --- | --- |
| `frontend/index.html` | **deleted** — the document now lives in `src/root.tsx` |
| `frontend/src/main.tsx` | **deleted** — replaced by `src/entry.client.tsx` |
| `src/root.tsx` | new: `<html>` document, `Layout`, site-wide `meta()`, theme bootstrap |
| `src/entry.client.tsx` | new: `hydrateRoot(document, …<HydratedRouter/>…)` |
| `src/routes.ts` | new: route table |
| `src/routes/catchall.tsx` | new: renders the existing `<App/>` and its `<Routes>` tree unchanged |
| `react-router.config.ts` | new: `ssr: false`, `prerender()` |
| `vitest.config.ts` | new — see §11 |

**The existing application was not rewritten.** `src/routes/catchall.tsx` mounts `<App/>` under a `*?` splat, so every pre-#40 route keeps working through the same `<Routes>` tree it always used. Only `/intelligence/:id` is a real framework route. Migrating the rest is optional, incremental, and not required by anything.

### 2.2 The theme bootstrap

The inline script that applies the stored theme before first paint moved from `index.html` into `root.tsx` as the `THEME_BOOTSTRAP` constant, injected with `dangerouslySetInnerHTML`. It is a **hard-coded constant in our own source** — no interpolation, no provider data, no user data. `src/theme/theme.test.ts` asserts its content.

---

## 3. The permanent URL

### 3.1 Shape

```
/intelligence/{urlencoded #39 object id}
```

The id is #39's semantic identifier — `rates:UST_NOMINAL_10Y:2026-09-18` — percent-encoded, so colons become `%3A`. That identifier is **derived from economic facts** (world, concept, effective period), not from a database primary key, which is what makes the URL permanent: it survives a database rebuild, a replay, and a migration, because it is regenerated from the same facts.

### 3.2 Why not a slug

A human-readable slug (`/intelligence/10-year-treasury-yield-sept-18`) would be prettier and would be a **second identity** to keep in sync with the first. #38 exists precisely because a second identity that can drift from the first is a defect factory. If slugs are wanted later they belong as a redirect layer over the canonical id, never as the identity.

### 3.3 Permanence obligations

Because the URL is permanent, three things follow:

1. **The id format cannot change casually.** It is part of `intelligence_v1`. Changing it breaks every link ever shared.
2. **A shared link must not silently become a different fact.** The id encodes the effective period, so `…:2026-09-18` is always the 18th — it can never quietly turn into today.
3. **A revised fact is the same object.** If Treasury revises the 18th's value, the object at that URL changes. That is correct: the URL names *"what MacroChipz knows about the 10-year on 2026-09-18"*, which is exactly what should update. #43 will surface the revision itself.

---

## 4. Build-time data: what the build needs, and what happens when it is missing

Prerendering requires knowing **which paths exist** before the build runs. `react-router.config.ts` asks the API:

```
GET {VITE_API_BASE_URL}/api/v1/intelligence?limit=…
```

filters to `PRERENDERED_TYPES` (today: `RATES_MOVEMENT`), caps at `MAX_PRERENDERED_OBJECTS` (today: 25), and returns the path list.

Three cases, each deliberate:

| Situation | Behaviour | Why |
| --- | --- | --- |
| `VITE_API_BASE_URL` unset | **warn, prerender nothing**, build succeeds, dev server runs | Frontend-only CI, and local `npm run dev`, must not require a database. The site still builds and works as an SPA. (Only true since #40A — see §16.) |
| API reachable, returns objects | prerender them | the normal path |
| API returns a non-OK status | **throw — the build fails loudly** | An unreachable backend during a release build would otherwise ship permanent URLs with nothing behind them. |

The third rule is the one ADR-039 flagged as an open obligation, and it is resolved in the direction of failing loudly. A deploy that half-worked is worse than a deploy that stopped.

**Consequence to be aware of:** the frontend build is now coupled to a reachable API *for release builds only*. `scripts/verify-build-output.mjs` then re-checks the actual output before the build is considered good.

### 4.1 Routes that were not prerendered

An id that exists in the database but was outside the prerender cap still works — the SPA fallback (`__spa-fallback.html`) serves the shell and `clientLoader` fetches the object in the browser. Such a page gets **no baked metadata**, so it is a working page with a poor unfurl. That is the documented trade-off of the cap, not a bug.

### 4.2 `loader` vs `clientLoader` — and why there are two route modules

> **Corrected in #40A.** #40 shipped a single route module exporting both `loader` and `clientLoader`. That configuration builds fine *when an API is reachable* and **cannot start `npm run dev` at all** otherwise. See §16.

React Router's rule, read from the installed `@react-router/dev@7.18.4` (`validateSsrFalsePrerenderExports`), applies whenever `ssr: false` — with or without prerendering configured:

- `action` and `headers` are **always** invalid.
- `loader` is invalid **unless the route is matched by a prerender path in that same invocation**.

A module's export list is static, so *"sometimes prerendered"* cannot be expressed in one module. The route therefore ships as two:

| Module | Exports | Used when |
| --- | --- | --- |
| `routes/intelligenceObject.tsx` | `clientLoader`, `meta`, page, `ErrorBoundary` | nothing is prerendered — `npm run dev`, frontend-only CI |
| `routes/intelligenceObject.prerendered.tsx` | the same, **plus `loader`** | this build prerenders at least one intelligence path |

`src/routes.ts` picks between them at config time. The prerendered variant is a thin re-export — same component, same `meta`, same `ErrorBoundary`, same `clientLoader` object — so the two cannot drift apart, and `src/routes/ssrFalseExports.test.ts` asserts they differ by exactly one export.

The prerendered variant keeps `clientLoader` deliberately: the prerender list is **capped**, so an object beyond the cap still matches this route and must still load in the browser. With `loader` alone React Router would look for a `.data` file the build never wrote.

- `loader` runs **in Node at build time**, for prerendered paths. Under `ssr: false` there is no request-time server, so this is not a runtime data path.
- `clientLoader` runs **in the browser**, for everything else.

Both delegate to one shared `loadIntelligence()`, which converts a 404 into `{ object: null }` — a not-found *state* — and rethrows everything else as a genuine fault. §7 covers why that distinction matters.

#### The decision must be made once

`src/routes.ts` (which module?) and `react-router.config.ts` (which paths?) must agree exactly, or the build fails with the same error. Both read one memoized answer from `src/build/prerenderPaths.ts`. Note the condition is **not** "is `VITE_API_BASE_URL` set" — a reachable API holding no `RATES_MOVEMENT` objects prerenders nothing, and there a `loader` export would be just as invalid as it is locally.

---

## 5. Metadata architecture

`src/lib/intelligenceMetadata.ts` is the single place that turns a #39 object into metadata. It is a **pure function of structured facts**, called from the route's `meta()`.

```
intelligenceMeta(object, id) -> MetaDescriptor[]
```

Rules it enforces:

- **Templates only, no generation.** Title and description are assembled from `headline()` and `summary()` in `src/lib/intelligenceLanguage.ts`, which read fields off the object. No model, no free text.
- **No significance claim.** #39 deliberately publishes no notability threshold, so no metadata may imply one. `intelligenceMetadata.test.ts` fails if the words *significant, notable, surge, plunge, shock, alarming* appear.
- **No internal taxonomy.** `RATES_MOVEMENT` and `METHODOLOGY_DERIVED` are machine vocabulary; the unfurl says "Treasury yield movement" and "Calculated by MacroChipz".
- **The description must stand alone.** A shared link has no surrounding page, so the description repeats the world and the effective period rather than assuming context.
- **A missing object is `noindex`.** A mistyped link must never be indexed as though it were an object.

### 5.1 Absolute URLs are omitted rather than guessed

`VITE_SITE_URL` is build-time configuration, deliberately allowed to be unset. When it is unset, `og:url`, `rel="canonical"` and `og:image` are **omitted entirely**:

> A guessed canonical is worse than none — it tells a crawler the real page lives somewhere it does not.

---

## 6. Open Graph image generation

`frontend/scripts/generate-og-images.mjs`, run after `react-router build`.

**Satori (JSX → SVG) → sharp (SVG → PNG)**, 1200×630, at build time. No headless browser, no page screenshot, no runtime image service — the cards are static assets beside the prerendered HTML, so **nothing new runs in production**.

The card is **composed from the same structured facts the page renders**. It is not a screenshot, and it does not re-implement the design system; it uses a small deliberate token subset (`PALETTE`) so a card is recognisably MacroChipz without dragging Tailwind into an image pipeline.

Failure rules, each chosen so that no card ever lies:

| Failure | Response |
| --- | --- |
| No usable font found anywhere | **fail the build** — every `og:image` would 404 |
| Object missing *optional* facts | generic MacroChipz card — truthful, less specific |
| Object missing *required* facts (no headline) | **skip that card, log it** — a missing card beats a misleading one |

**Determinism** is asserted, not assumed: `scripts/generate-og-images.test.mjs` renders the same facts twice and compares SHA-256 digests, and renders different facts and asserts the bytes differ. Identical facts must always produce an identical card, or the cache behaviour of every social platform becomes unpredictable.

`generate-og-images.mjs` exports `compose`, `render` and `loadFont`, and only executes `main()` when run as the build step (`import.meta.url === pathToFileURL(process.argv[1]).href`) — so importing it for tests never reaches an API or writes into `build/`.

---

## 7. What the page shows: See → Understand → Verify

> **Extended in #40B.** The hierarchy is now six layers, not three — see §17.

| Layer | Component | Answers |
| --- | --- | --- |
| **See** | `IntelligenceSee.tsx` | What is this and what did it do? — concept name, level, headline move |
| **Visual evidence** | `VisualEvidenceChart.tsx` | What has it actually been doing? — the last 63 published sessions |
| **Understand** | curated `Explanation` | Why should I care? — `WHY_THIS_MATTERS_BY_CONCEPT` |
| **Context** | `IntelligenceSee.tsx` | How far did it move, and is this unusual? |
| **Explore** | `IntelligenceSee.tsx` | Where does this sit? — a link into the Rates world |
| **Verify** | `IntelligenceVerify.tsx` | How do you know? — evidence, provider, methodology, limitations |
| **Share** | `ShareButton.tsx` | Can I send this to someone? |

Three properties are enforced by test rather than convention:

1. **Nothing is recalculated.** `src/test/no-intelligence-derivation.test.ts` scans the rendering layer for arithmetic on object fields — change magnitudes, basis-point conversions, percentile computation, world classification, evidence association. The page formats; #39 computes. If the page could derive a number, the page could disagree with the engine.
2. **Nothing is fabricated.** `published_at` is `null` for a Treasury observation, because Treasury does not publish an exact time. The page therefore says *"Not known — the source does not publish an exact time"* rather than substituting `recorded_at`. The guard specifically permits reading the field and rejects assigning one.
3. **No significance is claimed.** The historical percentile is shown with the explicit sentence *"MacroChipz is not claiming that makes it notable"*.

### 7.1 Not-found vs. fault

Deliberately different pages:

- **"No intelligence here"** — the address has nothing behind it. A fact about the world. `noindex`, with a route home.
- **"This could not be loaded"** — the backend was unreachable or unusable. A fault on our side, and it says so: *"This is a problem on our side, not with the link."*

Collapsing these would either blame the reader for our outage or quietly tell a crawler that a real object does not exist.

---

## 8. Sharing

`src/components/ShareButton.tsx`:

1. **Web Share API** where the platform provides it — the native share sheet, which is what a phone reader expects.
2. **Clipboard fallback** otherwise, with a visible "Link copied" confirmation.

Three rules:

- **The URL is shared verbatim.** No `utm_*`, no share id, no per-share token. A permanent URL that accumulates tracking parameters is no longer permanent, and #37's privacy posture forbids building an attribution graph.
- **Analytics can never break sharing.** `track("share_initiated", …)` is called *before* the share attempt and `track()` never throws. Tests assert sharing still works when the provider throws and when analytics is disabled entirely.
- **Only the object type is recorded.** Not the URL, not the title, not the clipboard, not which app was chosen. See §9.

---

## 9. Measurement (#37)

`share_initiated` moves from **Reserved** to **Active** in this increment — the first reserved event to be switched on, and it was switched on because the affordance now exists, which is the rule #37 set.

`ObjectType` gained the four #39 type names and `RouteTemplate` gained `/intelligence/:id`. Both remain **closed unions**, and `normalizeRoute()` collapses `/intelligence/{anything}` to the template:

> The id is deliberately discarded: reporting it would say which specific object a reader opened.

That is the difference between measuring *whether objects are shared* and building a reading history.

---

## 10. SEO foundation

Deliberately minimal — the parts that are hard to retrofit, none of the parts that are speculative.

| Present | Absent, on purpose |
| --- | --- |
| Prerendered HTML with real content | structured data / JSON-LD |
| Per-object `<title>` and description | keyword optimisation |
| `og:*` and `twitter:*` | content farming of thin pages |
| `rel="canonical"` (when origin configured) | link building |
| `sitemap.xml` generated from actual output | any claim of ranking strategy |
| `robots.txt` | |
| `noindex` on not-found | |

`scripts/generate-sitemap.mjs` walks the **actual prerendered output directory** rather than re-querying the API, so the sitemap cannot list a URL the build did not produce.

---

## 11. Testing under framework mode

**Spike answer: `reactRouter()` and Vitest cannot share one Vite config.** With both in `vite.config.ts`, 15 of 54 test files failed with *"React Router Vite plugin can't detect preamble"*. The resolution:

- `vite.config.ts` — `reactRouter()` + `tailwindcss()`, for dev and build.
- `vitest.config.ts` — `@vitejs/plugin-react` + jsdom + the existing setup file, for tests.

This is now recorded in ADR-039's implementation notes so it is not rediscovered.

Route modules are tested with `createRoutesStub` from React Router, which exercises the real component, loader wiring and `ErrorBoundary` without an E2E harness. ADR-039's discipline — *route modules stay thin, testable logic lives in presentational components taking plain props* — is what makes this possible, and it held: all 1,470 frontend tests pass, including every pre-#40 test.

---

## 12. Measured cost

Node 24.21, local backend, cold `build/` each run; prerender timings are the best of three.

**Fixed cost**

| Step | Time |
| --- | --- |
| `react-router typegen` | 1.1 s |
| `tsc -b` | 4.1 s |
| `react-router build` (0 objects) | 1.5 s |
| sitemap + verify | 0.1 s |
| **Full `npm run build`, 6 objects** | **~8.3 s** |

**Marginal cost per prerendered object**

| Component | Cost |
| --- | --- |
| Prerender (HTML + `.data`) | **0.29 s** |
| OG card (Satori + sharp) | **0.017 s** |
| **Total** | **~0.31 s** |

**Page weight**

| Artifact | Size |
| --- | --- |
| One prerendered page | 14.9 KB (4.7 KB gzipped) |
| Its `.data` payload | 2.2 KB |
| One OG card | ~50 KB |
| All JS | 524 KB (153 KB gzipped) |
| All CSS | 34.6 KB |

**JS impact of the migration:** the framework-mode runtime replaced `react-router-dom`'s SPA entry; the shipped bundle is of the same order as before. The page itself adds no charting library and no new runtime dependency — Satori and sharp are **build-time only** and ship nothing.

### 12.1 The rebuild-per-release threshold

Extrapolating from the measured constants:

| Objects | Prerender | Full build |
| --- | --- | --- |
| 25 (today's cap) | 8.7 s | ~15 s |
| 100 | 30 s | ~38 s |
| 250 | 74 s | ~84 s |
| 500 | 147 s | ~161 s |
| 1000 | 292 s | ~314 s |

**Rebuild-per-release stays comfortable to roughly 250 objects (~90 s) and becomes unattractive past ~500 (~3 min).** Two things arrive before that matters:

- MacroChipz produces on the order of a handful of objects per release day, so the cap binds long before the clock does.
- The escape hatch is already decided (ADR-039): flip `ssr: true` in the *same framework*. No migration.

The honest caveat: this is **linear extrapolation from n ≤ 6**. It should be re-measured at n ≈ 100 before anyone plans against the 500 figure.

---

## 13. Operational limitations

Stated plainly, because each is a real constraint someone will hit:

1. **A new object is not visible at a permanent URL until the site is rebuilt.** Prerendering is a build step. Until #41+ changes this, publishing means rebuilding.
2. **Only `RATES_MOVEMENT` is prerendered**, capped at 25. Other #39 types have working pages via `clientLoader` but no baked metadata.
3. **Release builds require a reachable API.** By design (§4), but it makes the backend a deploy dependency.
4. **`VITE_SITE_URL` must be set in production** or canonical and OG image tags are silently omitted. `verify-build-output.mjs` checks them only when the variable is set, so an unset variable is a quiet degradation, not a build failure.
5. **Unfurl behaviour is unverified against real platforms.** ADR-039 listed "publish one test page and run it through each platform's debugger" as a spike. It cannot be done before a public deployment exists, so it remains open. The metadata is correct by construction and by test; whether a given platform *likes* it is unmeasured.
6. **Mobile and accessibility are verified structurally, not visually.** Keyboard operation, focus order and screen-reader direction words are tested; jsdom cannot measure layout, so responsive behaviour rests on mobile-first Tailwind classes and manual inspection.
7. **Local development renders intelligence pages client-side only.** No prerendered HTML and no baked metadata in `npm run dev` — that is the configuration, not a fault. Verify metadata against a real build (`npm run build`), never against the dev server.
8. **The SPA fallback serves an empty shell to a crawler.** Any non-prerendered route — including every pre-#40 page — is still invisible to a crawler that does not run JavaScript. #40 fixed this for one route, not for the site.

---

## 14. What #40 deliberately did not build

Economic worlds (#41), THE LEDE / homepage (#42), the Revision Intelligence experience (#43), the rabbit-hole system (#44), Housing, Follow/email (#46), Radar, Brief. No Node production runtime, no SSR, no Next.js.

---

## 15. Files

```
frontend/
  react-router.config.ts               ssr:false + prerender entry point
  vite.config.ts                       reactRouter() + tailwindcss()
  vitest.config.ts                     plugin-react + jsdom  (see §11)
  public/robots.txt
  scripts/
    generate-og-images.mjs             Satori -> sharp, build time
    generate-og-images.test.mjs        composition + determinism
    generate-sitemap.mjs               walks real output
    verify-build-output.mjs            asserts the built HTML, fails the build
    verify-spa-mode.mjs                #40A: builds with no API, asserts exports valid
  src/
    build/prerenderPaths.ts            build-time only; ONE memoized prerender decision (#40A)
    root.tsx                           document, Layout, site meta, theme bootstrap
    entry.client.tsx                   hydrateRoot(document, …)
    routes.ts
    routes/
      catchall.tsx                     mounts the existing <App/> unchanged
      intelligenceObject.tsx           clientLoader, meta, page, NotFound, ErrorBoundary
      intelligenceObject.prerendered.tsx  the same + build-time `loader`  (#40A)
      ssrFalseExports.test.ts          #40A regression guard
      intelligenceObject.test.tsx
    api/intelligence.ts  intelligence.types.ts
    components/
      ShareButton.tsx
      intelligence/IntelligenceSee.tsx
      intelligence/IntelligenceVerify.tsx
      intelligence/intelligencePage.test.tsx
    lib/
      intelligenceLanguage.ts          taxonomy -> consumer language
      intelligenceMetadata.ts          facts -> metadata
      intelligenceMetadata.test.ts
      siteUrl.ts
    test/no-intelligence-derivation.test.ts   architectural guard
```

---

## 16. #40A — local-development regression and correction

### What was wrong

#40 shipped `routes/intelligenceObject.tsx` exporting **both** `loader` and `clientLoader`. Under `ssr: false` React Router permits `loader` only on a route it is prerendering *in that invocation*, so with `VITE_API_BASE_URL` unset:

```
Prerender: 1 invalid route export in `routes/intelligenceObject` when pre-rendering
with `ssr:false`: `loader`.
Error: Invalid route exports found when prerendering with `ssr:false`
```

**`npm run dev` printed its banner, reached `Local: http://localhost:5173/`, and then died on the first request.** That is why it escaped review: the startup output looked healthy, and the release build — which *does* prerender — was always green.

### Why #40's verification missed it

Three blind spots, each worth naming:

1. **Every automated check ran with an API available.** The release build prerenders the route, which makes `loader` legal. The failing configuration was never built.
2. **Unit tests cannot see this class of defect.** The validation is React Router's own and runs only when the dev server or build assembles the route manifest. All 1,470 tests passed against a broken application.
3. **#40 was verified but never *run*.** The build was inspected; the dev server was not. #40's own documentation asserted that local development worked without a database — an assumption stated as a verified fact.

### The fix

Not "remove `loader`" — that was measured and **breaks release prerendering**: with `clientLoader` alone the prerendered HTML is an empty shell with no `<h1>` and no metadata, caught by `scripts/verify-build-output.mjs`. Both exports are genuinely needed, in different configurations.

So the *module* varies instead (§4.2): two route modules, selected in `src/routes.ts` from one memoized decision in `src/build/prerenderPaths.ts`. SSR stays `false`, prerendering stays, no Node runtime appears, and the client-side variant is also what serves objects beyond the prerender cap.

### The regression coverage added

| Guard | Catches | Cost |
| --- | --- | --- |
| `src/routes/ssrFalseExports.test.ts` | a `loader` (or `action`/`headers`) on the client-side variant; the two variants drifting apart | milliseconds, in the normal suite |
| `npm run verify:spa-mode` | the same thing via **React Router's own validation**, by building with no API | ~2 s |

The second exists because the first is *our restatement* of the framework's rule; if React Router changes the rule, only the second notices. Both were verified to fail when the original defect is reintroduced, and to pass when it is not.

### Tooling warnings investigated at the same time

**`The \`envFile\` option is deprecated, please use \`envDir: false\` instead.`** — **not our configuration.** `@react-router/dev@7.18.4` sets `envFile: false` internally (two call sites in `dist/vite.js`); `vite@8.3.0` deprecated that option. #40 did not introduce it, it *exposed* it by adopting `@react-router/dev`. Patching a dependency to silence it would be worse than the warning. Resolved by the vendor on their own schedule; revisit at the next dependency upgrade.

**React Router v8 future flags** — five are warned about. **None are opted into.** Opting in to silence warnings would change behaviour this increment has not tested:

| Flag | Affects #40? | Decision |
| --- | --- | --- |
| `v8_middleware` | No — MacroChipz uses no route middleware | Defer |
| `v8_splitRouteModules` | Possibly — changes route-module chunking, and #40A now has two variants of one route | Defer; re-test both variants when adopted |
| `v8_viteEnvironmentApi` | No | Defer. **Measured:** enabling it does *not* remove the `envFile` deprecation — the two are unrelated |
| `v8_passThroughRequests` | No — request handling is server-side, and there is no server | Defer |
| `v8_trailingSlashAwareDataRequests` | **Potentially** — changes `.data` request URL formats, which prerendering writes | Defer; must be re-verified against prerendered output when adopted |

All five belong to a future dependency-upgrade increment, adopted one at a time with the build output re-verified, not as a batch to clean up console output.

---

## 17. #40B — consumer presentation pass

#40 proved the architecture. #40B proved the communication model on the same page, changing no architecture: `ssr:false` + prerender, the two route modules from #40A, #39 as the only source of truth.

### 17.1 What changed in the first viewport

| | #40 | #40B |
| --- | --- | --- |
| Heading | `10-Year Treasury Par Yield (Nominal) is 5.01%` | `10-year Treasury yield` |
| Value | inside the heading sentence | its own line, the largest thing on the page |
| Movement | `+36 bp` in a grid of four | `↑ Up 0.05 percentage points over the last 5 trading days` |
| Provider title | the headline | a quiet line beneath, still present |

The provider's own wording did not go away — it moved to where precision is what the reader wants. Nothing was removed from "Check this".

### 17.2 Percentage points, not basis points

Basis points remain the canonical unit in #39 and in `rates_v1.0`. The page converts for display (`formatPercentagePoints`) exactly as it renders `5.01` as `5.01%`, and shows the basis-point figure beside every window for readers who think in them. **No stored value, methodology or payload changed.**

### 17.3 "Why this matters"

Curated static prose in `src/content/explanations/rates.ts` (`WHY_THIS_MATTERS_BY_CONCEPT`), reusing the `Explanation` model the rest of the product already uses, and **selected by exact concept id** — never by a model, never by a heuristic over the series title. A concept with no entry renders **no section at all**, which is the honest failure mode.

Every entry that touches other borrowing costs describes a **benchmark that influences**, never a mechanism that sets. The 10-year entry says outright: *"It is a reference point, not a mechanism: the 10-year does not set any of those rates."* The entries answer why the **indicator** matters — a durable property — and say nothing about why today's number moved, because MacroChipz does not know that.

Guarded by `no-intelligence-derivation.test.ts` (no model, no fetch, no `${}` interpolation, no control verbs).

### 17.4 The historical-context correction

**#40's page said "this level sits at the 57th percentile". That named the wrong quantity.**

`RatesService._historical_context` ranks the **current 5-session change** against every earlier 5-session change (`_CONTEXT_WINDOW = "5_SESSIONS"`). Both ranks are about the **move**; neither is about the level. The page has now been corrected to say so, and the section leads with the consumer question "Is this unusual?":

- **what is compared** — "move over 5 trading days, **not the level itself**";
- **signed vs magnitude** — two labelled rows, "Direction and size together" and "Size alone, ignoring direction", because they answer different questions and can disagree;
- **how much history** — "113 earlier 5-trading-day moves", in the same sentence as the comparison;
- **that this is not long-run context** — "a few months of trading, not decades — it is not a statement about what is normal for this yield over the long run";
- **no label** — "MacroChipz does not label this move unusual or ordinary", because `rates_v1.0` defines no threshold and inventing one in the rendering layer would be a significance methodology smuggled into a component.

The headline move uses the same 5-session window the ranks use, so the headline and the "is this unusual?" answer describe the **same** move.

**Residual:** the #39 payload carries `historical_observation_count` but not the history's start date (`builder.py` forwards three fields of `HistoricalContext`). The page therefore states the count and characterises it as months rather than printing a date range it does not have.

### 17.5 What #40B deliberately did not do

No chart — that waits for a designed visual exploration system. No significance methodology. No new data, no new canonical intelligence, no LLM, no provider call. The other three #39 types keep #40's presentation unchanged (`GenericIntelligence`), because a half-considered consumer treatment would be worse than an honest plain one until each is designed.

### 17.6 Verified rendering

Measured in real Chrome against the dev server, not only in jsdom: at 1440×900 and at a true 390×900 viewport, `document.documentElement.scrollWidth` equals the viewport width and **zero elements overflow** (excluding the evidence table, which scrolls inside its own `overflow-x-auto` container by design). Reading order was also extracted from the prerendered HTML and matches SEE → UNDERSTAND → CONTEXT → EXPLORE → VERIFY → SHARE.

---

## 18. #40C — visual evidence

### 18.1 The rule

> **Visual evidence is part of the intelligence object's evidence contract, not a frontend side-channel into economic data.**

The chart draws `payload.visual_evidence`, which arrives inside the #39 object. This page performs **no fetch of its own** — guarded by `no-intelligence-derivation.test.ts`, which asserts the component contains no `fetch(`, no `useEffect`, no API-client import.

The contract itself is documented in `structured-intelligence.md`.

### 18.2 The chart

Hand-authored SVG per ADR-041. **No charting library**, and no `d3-scale` either: the scales are two linear interpolations, and 15.7 KB for `a + (b - a) * t` is not a trade worth making. ADR-041 permits d3 math; it does not require it.

One series, one neutral stroke. Semantic `state-*` and `feedback-*` colours mean something specific in this design system, and a yield moving up is neither good nor bad — so the line uses `stroke-fg`, and a test fails the build if a semantic or red/green token appears inside the chart.

**X is positioned by date, not by array index.** A publication gap therefore shows as a gap in spacing rather than being silently closed up. That is what "never fabricate missing trading days" means in practice.

**The y-axis is not zero-based**, deliberately. A yield chart forced to a zero baseline compresses every real movement into a flat line, which is its own dishonesty. The axis labels always state the actual values, so the scale is never hidden.

### 18.3 ADR-041's two recorded defects, both addressed

1. **`preserveAspectRatio="none"` distorts at mobile width.** This chart uses `xMidYMid meet` with a **viewBox per breakpoint** — the ADR's own SSR-safe prescription, since `ResizeObserver` would reintroduce the server-rendering failure that disqualified Recharts. Two `<svg>` elements, CSS-swapped; `display: none` keeps the hidden one out of the accessibility tree.

   **Measured in real Chrome:** at 390 px the viewBox aspect is 1.714 and the rendered aspect is 1.714; at 1440 px both are 3.167. Zero distortion.

2. **The ARIA pattern was both decorative-plus-table and labelled-image.** This chart picks one: a labelled image (`role="img"` + `aria-label`), with the numbers available as a real table behind progressive disclosure.

*(The existing `/rates` yield-curve chart still carries defect 1. #40C did not widen its scope to fix it; that remains ADR-041's acceptance criterion for #41.)*

### 18.4 Accessibility

The `aria-label` states exactly the five things a screen-reader user needs: **what** is charted, **over what span**, the **start value**, the **latest value**, and the **direction**. Nothing requires hover; nothing requires a pointer. The full series is also a real `<table>` inside a disclosure — which serves sighted readers wanting exact numbers just as much, and is the same "check this" instinct the rest of the page runs on.

### 18.5 Prerendered, not client-only

With every `<script>` stripped from the built HTML, the page still contains **two chart SVGs, 63 plotted points each, and a 63-row data table**. Asserted on every build by `scripts/verify-build-output.mjs`, which fails if a page has fewer than two chart SVGs, a chart without a plotted line, a chart missing a meaningful `aria-label`, or a chart that does not preserve its aspect ratio.

### 18.6 Measured cost

| | Before #40C | After | Δ |
| --- | --- | --- | --- |
| API payload (one object) | 2,037 B | 5,030 B | **+2,993 B** |
| Page HTML | 21,139 B | 34,195 B | +13,056 B |
| Page HTML, gzipped | 6,443 B | 8,459 B | **+2,016 B** |
| All JS | 531,564 B | 535,834 B | +4,270 B |
| All JS, gzipped | 155,867 B | 157,187 B | **+1,320 B** |
| Build time | 9.67 s | 9.78 s | +0.11 s |
| Chart markup (both viewBoxes) | — | 4,105 B | — |

Over the wire the whole capability costs about **3.3 KB gzipped** per page. The largest single contributor to raw HTML is the 63-row verification table (~9 KB raw, a fraction of that gzipped) — a deliberate purchase: it is what makes the chart checkable rather than merely decorative.

No optimisation was applied, because nothing in these numbers indicates a problem.

### 18.7 OG images

Unchanged. Dynamic chart-in-OG is deferred.

---

## 19. #41 — route migration and what a client-side redirect is not

The consumer IA renamed three public routes:

| Old | New | Why |
| --- | --- | --- |
| `/overview` | `/` | "Overview" named our architecture, not a part of the economy. The page's own docstring already called itself *"the real `/` product page"*. |
| `/labor` | `/jobs` | `labor` is the engineering domain's word. The reader's word is Jobs. |
| `/releases` | `/calendar` | Same reason. |

**Every old URL still works.** `App.tsx` routes each to `<Navigate to="…" replace />`.

### 19.1 What React Router's redirect actually gives us — and what it does not

| | Client-side `<Navigate replace>` | True HTTP 301 |
| --- | --- | --- |
| Reader with an old bookmark lands on the right page | **yes** | yes |
| Old URL removed from browser history | **yes** (`replace`) | yes |
| Requires JavaScript to run | **yes** | no |
| Crawler treats the new URL as canonical | **no** | yes |
| Link equity transferred | **no** | yes |

So the redirects are correct for **people** and incomplete for **crawlers**. A crawler that does not execute JavaScript sees the SPA fallback shell at `/labor` and never learns that `/jobs` exists.

Two things limit the damage today, both deliberate:

- The compatibility routes are **not prerendered**, so they produce no HTML of their own and never enter `sitemap.xml`. Only the five canonical routes do.
- The 404/unknown branch of `catchall.tsx`'s `meta` emits `robots: noindex`.

### 19.2 What still requires the hosting layer — and why it is not configured here

A true permanent redirect must be issued by whatever serves the static bundle:

```
/overview   →  /   301
/labor      →  /jobs      301
/releases   →  /calendar  301
```

**This was not implemented, because there is no deployment target to implement it against.** Verified this increment: there is no Vercel, Netlify, Cloudflare or S3/CloudFront configuration in the repository; the `Dockerfile` does not serve the frontend; `app/main.py` mounts no `StaticFiles`; and CI validates without ever deploying (ADR-028). Writing a `_redirects` or `vercel.json` for a host nobody has chosen would be a guess wearing the costume of completeness.

**Recorded as an explicit, bounded obligation:** whoever chooses the static host owns those three 301s, and the table above is the specification. #41 §22 named this as a stop-and-report condition; this section is the report.

---

## 20. #41 — what the new IA means for rendering

### 20.1 Prerendered now

`STATIC_PATHS` grew from `["/"]` to the five canonical routes: `/`, `/inflation`, `/jobs`, `/rates`, `/calendar`. Each gets real HTML with its own `<title>`, description and Open Graph tags, produced by `catchall.tsx`'s `meta`, which branches on pathname (one module serves all of them).

Verified in the generated HTML:

```
/            MacroChipz — Economic Intelligence
/inflation   Inflation — MacroChipz
/jobs        Jobs — MacroChipz
/rates       Rates — MacroChipz
/calendar    Release calendar — MacroChipz
```

### 20.2 What is still SPA-only, stated plainly

**The BODIES of those five pages are not crawlable.** They fetch through `useApiResource` in the browser, so the prerendered body is the application shell, not a rendered monitor. #41 buys metadata and a non-empty document — not crawler-visible economic content.

Making that content crawlable means giving each world a real framework route with a loader, which is a larger change than #41 owned. The permanent intelligence pages remain the only surfaces whose *content* a non-JavaScript crawler can read.

### 20.3 The permanent page now has a shell

`IntelligenceShell` — brand, world name, one link into that world, and a footer. Deliberately not `AppShell`: a permanent object page is usually the FIRST page someone sees, arriving from a message with no context, and five navigation items above a single Treasury yield would bury the fact. Adds no client-only behaviour, so prerendering and metadata are unchanged (re-verified: title, `og:*`, canonical, both chart SVGs, Check this and Share all still present in the built HTML).
