# Living Economy v2 → production: integration plan

**Increment #48, production preparation.** Plan only. No production route,
component or methodology was touched by this task.
**Date:** 2026-09-22
**Prototype:** `docs/product/mockups/v48/index.html`
**Target route:** `/` (`frontend/src/pages/Home.tsx`)

---

## 0. The finding that shapes everything below

**The frontend currently contains zero images.** `grep -rn "<img\|<picture\|srcset" frontend/src` returns
**0 matches**, and `frontend/public/` holds exactly `favicon.svg` and
`robots.txt`. There is no image component, no `srcset` convention, no
art-direction pattern, no asset-size budget and no CDN.

So the cinematic direction is not a restyle of the homepage. It introduces a
**new asset class** into an application that has never shipped one. Most of the
cost below is that, not the layout.

The good news, and it is genuine: **`sharp` is already a devDependency** (satori
uses it for OG images). Build-time derivative generation needs **no new
dependency**.

---

## 1. Components to retain, replace, add

### Retain unchanged — no edits, no wrapper

| Component | Why it must not be touched |
|---|---|
| `homepage/presentationPolicy.ts` (`selectHomepage`, `isRatesMovement`) | `homepage_presentation_v1.0`. The eligibility model is the honest core. v48 changes *presentation*, and the moment a visual requirement reaches into this file the policy has become decorative. |
| `api/*` and every `useApiResource` call | Seven independent failure-isolated resources. The new hero adds none. |
| The Census non-endorsement sentence in `AppShell.tsx:148` and `IntelligenceShell.tsx:113` | Verbatim, required by Census's Data API terms, already duplicated deliberately. Do not centralise it as part of this work — that is a separate change with its own risk. |
| `worlds/registry.ts` | The hero reads `label`, `route` and `description` from it. It gains **nothing**: an `image` field here would make the registry an asset manifest, and §"Not a CMS" in its own header forbids that. Image mapping lives in the hero's own module. |
| `ReleaseScheduleDisclosure` | Frozen sentence. |

### Replace

| Existing | Replaced by | Note |
|---|---|---|
| `PageHeader title="The economy right now"` | The hero. The headline becomes **"Explore the living economy."** | The old title is the page's current `<h1>`; the hero must supply exactly one `<h1>` or `verify-build-output.mjs:73` fails the build. |
| `components/homepage/WorldOrientation.tsx` | `LivingEconomyHero` | Its job — name four worlds, show each one's latest data line — splits: naming moves to the hero, the data lines move into the world tiles or are dropped. **It has a test file (`WorldOrientation.test.tsx`); retire both together or neither.** |

### Retain but move

`RecentIntelligence`, `HomeQuestions`, `CurrentStateSection`, `HowTheyRelate`,
the Releases section and `RevisionsLink` all keep their current props and
behaviour, reordered per the v47 §2 hierarchy. **No prop changes.** If a move
requires a prop change, the move is wrong.

### Add — five new modules

| New | Responsibility |
|---|---|
| `components/homepage/LivingEconomyHero.tsx` | Four world tiles + selection state + panel. Registry-driven. Fetches nothing. |
| `components/homepage/worldImagery.ts` | The `WorldId → {src, credit, objectPosition, status}` map, plus the placeholder variant. **The single place a rights-bearing asset is named.** `status: "verified" \| "placeholder"` so a placeholder cannot be shipped silently. |
| `components/Figure.tsx` (or `WorldImage`) | The application's first image primitive: explicit `width`/`height` to reserve layout, `object-position`, the tint overlay, `loading="eager"` + `fetchPriority="high"` for the hero and lazy for the rest, and **a required `credit` prop**. Making credit a required prop is the mechanism that stops an uncredited asset shipping. |
| `components/homepage/QuietPanel` treatment | The compact quiet state with two weighted actions. May live inside `TheLede.tsx` rather than as a new file — `TheLede`'s four states already exist and only their styling changes. |
| `public/img/worlds/*` | The assets. |

---

## 2. Data: what the prototype shows and what production can actually supply

| Prototype element | Production source | Status |
|---|---|---|
| Four world tiles (label, description, route) | `ECONOMIC_WORLDS` | **Available. Static, no request.** |
| Quiet / unknown / development lede | `selectHomepage(intelligence)` | **Available, unchanged.** |
| Treasury curve snapshot visual | `GET /api/v1/series/UST_NOMINAL_10Y/observations` + the rates monitor | **Available but NOT currently fetched by the homepage.** |
| Per-world "latest figure" on a tile | — | **Does not exist.** Same gap v47 §12.1 named. |

### 2.1 The two data decisions that need making

**(a) The curve visual costs a new request.** The prototype renders from a
captured snapshot (`v48/rates-snapshot.json`) because the API sends no
`Access-Control-Allow-Origin` header, so a file-origin prototype cannot fetch
it. Production is same-origin and can. But it means an **eighth** independent
resource on `Home.tsx`. That is affordable under the existing failure-isolation
pattern; what is not affordable is letting it block the hero. **The hero must
render completely with the visual absent**, and the visual's own loading state
must not reserve a large empty box above the fold.

**Recommendation:** ship the hero in phase 1 **without** the curve visual, and
add it as a separate increment. The hero's value is orientation; the visual is
enrichment, and pairing them puts a network dependency in front of the one
section that currently survives an outage.

**(b) A figure on a tile needs an as-of date beside it.** v47 §7 forbids implying
currency. If tiles ever carry values, each needs its effective period rendered —
four values plus four dates is a different tile design from the one approved.
Not in scope; noted so it is not discovered later.

---

## 3. Images: the actual work

### 3.1 Placement and serving

Assets go in `frontend/public/img/worlds/`. Consequence to accept
deliberately: **Vite copies `public/` verbatim and does not fingerprint it.**
A `/img/worlds/rates.jpg` URL is therefore cacheable-forever-or-not-at-all. Two
options:

- **Import through Vite** (`import ratesJpg from "../../assets/worlds/rates.jpg"`)
  — gets a content hash, so `immutable` caching is safe. Preferred.
- **Keep in `public/` and version the filename** (`rates-treasury-highsm-16870.jpg`,
  as the prototype already does) — simpler, and the filename already carries
  the LOC digital id, which is useful provenance in itself.

Either is defensible. The hashed import is the better default because it makes
the cache header safe without a convention nobody will remember.

### 3.2 Derivatives and budget

The verified source is 1900 × 1460, 356 KB. Ship three widths (≈480 / 960 /
1440) as WebP with a JPEG fallback, generated with the **already-present
`sharp`** in a small `scripts/build-images.mjs`, committed as output so no build
step depends on the network.

**Budget:** ≤ 120 KB for the largest hero derivative, ≤ 60 KB for a tile. The
hero image becomes the LCP element, and the homepage is prerendered, so it must
be in the initial HTML with `width`/`height` set and a `<link rel="preload">` on
the hero source only.

### 3.3 The rights mechanism

`worldImagery.ts` carries `status` and `credit`. `Figure` requires `credit`.
Then one test — `worldImagery.test.ts` — asserts that every entry with
`status: "verified"` has a non-empty `credit`, and that a `placeholder` entry
renders the visible PLACEHOLDER treatment. That converts the rights rule from a
review habit into a build failure.

**Today that test would pass with one verified and three placeholders.** See
`docs/product/mockups/v48/ASSETS.md` — Inflation, Jobs and Housing have no
verified asset, and the honest production launch either ships three placeholders
or ships the gradient-only treatment for those three. **Recommendation: the
gradient treatment, not a visible "PLACEHOLDER" chip.** A prototype should
announce its gaps; a production homepage should not have a chip on it saying so.

---

## 4. Responsive and shell

The hero sits inside `PageContainer` (`max-w-app` 76rem, `px-4 sm:px-6 lg:px-8`)
and must **not** add a second width constraint — the #27A double-width rule.

A full-bleed hero therefore needs the same treatment #46F used for the story
page: the surface goes on `<main>` via `IntelligenceShell`'s existing
`surface?: "luminous"` prop, extended with a second value rather than by adding
negative margins. `AppShell` is the shell `/` uses and has **no** `surface`
prop — adding one there is part of this work, and it must reuse
`IntelligenceShell`'s pattern rather than inventing a second one.

Breakpoints per v47 §9. Mobile is the design, not a compression.

---

## 5. Acceptance tests

New:

1. `worldImagery.test.ts` — every `verified` entry has a credit; every
   `placeholder` entry renders its treatment; no entry lacks `objectPosition`.
2. `LivingEconomyHero.test.tsx` — four worlds present; exactly one selected on
   load; selecting each updates the panel; every tile links to its registry
   `route`; **no `<line>`, `<path>` or arrow is drawn between worlds** (v47
   §3.2's no-edges rule, asserted not assumed); `aria-pressed` on the controls;
   panel is `aria-live="polite"`.
3. `Home.tsx` — exactly one `<h1>`, and it is "Explore the living economy."
4. Hero renders fully when **every** `useApiResource` is in `error`.
5. Each image has explicit `width` and `height`.
6. The lede's quiet state renders no fabricated figure; unknown ≠ quiet
   (existing assertions, retained).

Existing that must keep passing: `Home.test.tsx`,
`Home.noCoverageNoise.test.tsx`, `HomeIntro.test.tsx`, `TheLede.test.tsx`,
`Housing.test.tsx`'s Census assertions, and `verify-build-output.mjs` —
which will fail the build if `/` loses its baked `<h1>`.

Manual, measured not eyeballed: 390 / 440 / 768 / 1024 / 1440px — zero
horizontal overflow on rendered bounds, zero targets under 44px, contrast of
text over photography ≥ 4.5:1 **measured against the tinted composite**, and
`prefers-reduced-motion` honoured.

---

## 6. Dependencies

**None added.** `sharp` is already in devDependencies. No image library, no
lightbox, no carousel, no animation library.

---

## 7. Sequencing

| Phase | Contents | Gate |
|---|---|---|
| **1** | `Figure`, `worldImagery`, hero with the one verified asset and gradient treatment for the other three, headline change, compact quiet panel, reorder | Design review |
| **2** | Retire `WorldOrientation` + its test | Phase 1 accepted |
| **3** | Curve visual as an eighth isolated resource | Its own review |
| **4** | Remaining three assets, when rights are verified | ASSETS.md gaps closed |

Phase 1 is shippable with one image. That is the point of separating it.

---

## 8. Risks

1. **Text-over-photo contrast is the likeliest regression.** A tint that works
   on the Treasury colonnade will not work on a bright subject. Mitigation: the
   tint is a property of the entry in `worldImagery.ts`, not a global.
2. **LCP.** The homepage currently has no image and therefore a trivially fast
   LCP. Measure before and after; the budget in §3.2 is the line.
3. **Three unverified worlds.** The honest options are gradient-only or delay.
   Shipping an unlicensed image is not among them.
4. **Scope creep into the lede.** Every visual improvement to the quiet state is
   welcome; any change to *which* object is eligible is out of bounds.
