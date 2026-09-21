# The MacroChipz Homepage and THE LEDE

**Status:** implemented (Increment #42); legacy change surfaces removed from `/` in #42A (§10)
**Policy:** `homepage_presentation_v1.0` (`frontend/src/homepage/presentationPolicy.ts`)
**Consumes:** #39 Structured Intelligence · #40C visual evidence · #41 Economic Worlds

---

## 1. The boundary this document exists to defend

```
CANONICAL INTELLIGENCE                 HOMEPAGE PRESENTATION
(#39, frozen methodologies)            (#42, this document)
--------------------------             ----------------------
What is true about the economy    →    What MacroChipz shows first
```

**THE LEDE is a presentation decision. It is not a canonical economic conclusion.**

The homepage may decide *"what should MacroChipz show first?"*. It may **not** decide *"what is economically most important?"* — because #39 deliberately publishes no significance ranking, and #42 did not add one.

Nothing on the homepage says *most important*, *biggest*, *major*, *significant*, *breaking* or *urgent*. Tests fail on every one of those words.

---

## 2. What the data actually looks like

Measured before any code was written (#42 §2). **1,899 objects:**

| Type | Count | Notes |
| --- | --- | --- |
| `ANALYSIS_CHANGE` | 1,532 | **1,488 COVERAGE**, 44 ECONOMIC |
| `OBSERVATION_CHANGE` | 358 | **all `NEW`**, `previous_value` null throughout |
| `RATES_MOVEMENT` | 6 | real Treasury levels, 2026-09-18 |
| `RELEASE_PROCESSED` | 3 | operational counts |

Two findings changed the design, and neither is visible from the taxonomy alone:

**1. All 44 "ECONOMIC" changes are `UNAVAILABLE → something`.** Every one records the confirmation relationship becoming computable during backfill. #39 classifies them ECONOMIC correctly for its own purposes — the field *is* an economic field — but *"MacroChipz can now calculate this"* is an availability event. **So `change_class` is necessary but NOT sufficient**, and the policy checks `previous_value` too.

**2. All 358 observation changes are first observations, not revisions.** A value arriving for the first time during backfill is not something that changed.

**Without a policy, the homepage would have led with eight COVERAGE jobs events dated 2027** — future periods, from the default ordering.

---

## 3. Eligibility

Structural only. No magnitude, no threshold, no score.

| Type | Rule | Today |
| --- | --- | --- |
| `RATES_MOVEMENT` | always eligible | **6 objects** |
| `ANALYSIS_CHANGE` | ECONOMIC **and** `previous_value` not `UNAVAILABLE`/null | 0 |
| `OBSERVATION_CHANGE` | `REVISED`, or `previous_value` not null | 0 |
| `RELEASE_PROCESSED` | never (v1) — *"120 observations processed"* describes our pipeline, not the economy | 0 |

The rules that currently select nothing are written anyway: they are what stays correct when genuine revisions and state transitions arrive, and a filter that exists only implicitly is one nobody can test.

---

## 4. Ordering

A stable tuple of structural facts, applied in order:

1. `effective_period` **descending**
2. **world**, in registry order — a *declared* order so ties resolve identically, **not** a ranking of which world matters
3. **concept presentation order** — the 10-year Treasury leads rates because it is the most widely referenced benchmark. That is a fact about how people talk about rates, **not** a claim it moved more
4. **object id ascending** — guarantees a *total* order, so the result can never depend on input order or sort stability

Deliberately absent: magnitude, percentile, size-of-move, recency-of-recording, and anything resembling a score.

**Deduplication:** one object per concept. The six maturities publish on the same date; six near-identical cards would be one fact repeated. Every maturity stays one click away in the Rates world.

---

## 5. No clock

Eligibility and ordering read no `Date.now()`, no request time, and no visit history (#42 §5 forbids reviving "days since visit").

This is a **correctness** property, not a stylistic one: the homepage is prerendered, and a policy that consulted a clock would bake one moment's answer into static HTML and then quietly lie about it. Staleness is communicated by *showing* the effective period, never by hiding an object for being old.

It is possible only because the 10 future-dated objects are all COVERAGE, so the coverage filter already excludes them.

---

## 6. Freshness semantics

MacroChipz holds several distinct times and the homepage never collapses them:

| Concept | State locally | Used for display? |
| --- | --- | --- |
| `effective_period` | real | **yes — the only anchor shown** |
| `published_at` | **null on every object** | no |
| `recorded_at` | spans 2 days (backfill) | no |
| browser/request time | available | **never** |

So the homepage cannot honestly say *today*, *new*, *just released* or *latest* — and does not. It says the period the data describes: *"Rates · 2026-09-18"*.

---

## 7. THE LEDE's three states

| State | When | What it says |
| --- | --- | --- |
| **Active** | an eligible object exists | name, number, movement, chart, evidence + world links |
| **Quiet** | resolved, nothing eligible | *"No new tracked change"* + *"not a claim that the economy is quiet"* + all three worlds + calendar |
| **Unknown** | not resolved yet | *"The economy right now"* + worlds. **Asserts nothing.** |

The third state was added after measuring the build output. The homepage fetches in the browser, so the prerendered HTML has no data — and rendering the *quiet* state there would bake **"No new tracked change"** into static HTML for every crawler, publishing a claim MacroChipz had never checked. *Unknown is not quiet.*

The quiet state also refuses the tempting fallback of showing the freshest *ineligible* object, which by definition is one of the 1,488 coverage events the policy exists to exclude. **A quiet day is a valid product state; an invented headline is not.**

---

## 8. Rendering and SEO

Prerendered and verified in the generated HTML for all five canonical routes:

- `<title>` per route · description · `og:title/description/type/site_name` · `twitter:*`
- `rel="canonical"` and `og:url` **only when `VITE_SITE_URL` is set** (a guessed canonical is worse than none)
- `og:image` reuses #40's existing `/og/default.png` — **no graphics system was added and nothing is screenshotted**
- `/overview` appears in **no** sitemap entry and is not prerendered

**What is NOT crawlable, stated plainly:** THE LEDE's *content*. The homepage fetches through `useApiResource` in the browser, so the prerendered body carries the page structure and the Unknown state, not the active lede. Making it crawlable means giving `/` a real loader — which would couple every build to the API and bake a specific day's lede into static HTML. That trade was evaluated and declined; see §5 on why the policy is clock-free but the *data* is not.

---

## 9. What the homepage explicitly does not claim

- That the shown object is the most important thing in the economy.
- That anything is *significant*, *major* or *breaking*.
- Any cause for any movement.
- Any whole-economy verdict — no score, no *healthy/unhealthy/strong/weak*.
- That MacroChipz monitors everything.
- That data is newer than its stated effective period.

---

## 10. #42A — legacy change surfaces removed from `/`

`homepage_presentation_v1.0` kept coverage and bootstrap events out of THE LEDE. Three **legacy** sections below it rendered the same events unfiltered, which made the policy decorative.

They were **removed from the homepage composition only** — not redesigned, not deleted, and no component was changed.

| Removed from `/` | Why it was incompatible |
| --- | --- |
| **Since Your Last Check** | Recapped whatever the backend had detected, which locally means coverage: *"Core CPI became available for July 2026"*. |
| **What Changed** (`WhatChangedPreview`, `LaborWhatChangedPreview`) | Renders `AVAILABILITY_LOST` / `AVAILABILITY_RESTORED` rows as changes, and prints a null value as the bare word *"Unavailable"*. |
| **Recent Data Updates** (`RecentDataUpdates` → overview `LatestDataDetected`) | Rendered "Tracked analysis changes" as `previous → current`, which on this data reads **`Unavailable → 3.353016322755642`**. |

Each exposed exactly the class of event #42 measured and excluded: 1,488 of 1,899 objects are COVERAGE, and all 44 "ECONOMIC" analysis changes are `UNAVAILABLE → x` first computations.

**Nothing replaced them.** The homepage did not gain another feed. **#43 still owns the Revision Intelligence experience** that should eventually present this material honestly, and these components are the raw material it will reuse or retire deliberately.

### What `/` now contains

THE LEDE → "Also recorded" (bounded, policy-selected) → Current State → How They Relate → Releases preview → paths into Inflation, Jobs, Rates and Calendar.

### Preserved, not deleted

Every component still exists. `components/labor/LatestDataDetected.tsx` is a **different** component and is untouched — the Jobs page still renders it. `SinceLastVisit` and the overview `LatestDataDetected` keep their own component tests.

### Side effects

- Three fewer API requests on `/` (`getInflationWhatChanged`, `getLaborWhatChanged`, `fetchReleaseProcessingStatus`, plus `getSinceLastVisit`), asserted by test.
- Two stale links fixed: the homepage release CTA and `releaseMonitorCta` still pointed at `/releases`, sending readers through a #41 compatibility redirect to reach a canonical page. Both now point at `/calendar`.
- `homepage_presentation_v1.0` is **unchanged**. The cleanup revealed no policy bug — the policy was already correct; the legacy sections simply bypassed it.

### Coverage note

`WhatChangedPreview` and `LaborWhatChangedPreview` are now rendered by no route and have no test of their own (their coverage was via Home integration tests, removed with the section). Recorded as a **#43 obligation** rather than left to be discovered.
