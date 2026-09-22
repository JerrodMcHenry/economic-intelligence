# MacroChipz — Product Cohesion & Data Opportunity Audit V1

**Increment #45A.** Audit and product planning only. No production code changed, no API integrated, no world created, no methodology touched, nothing committed or pushed. Baseline: HEAD `8b09b62` (#45, "feat: add housing intelligence world").

**Method.** The product was walked in a real browser against a live backend (`/`, `/inflation`, `/jobs`, `/rates`, `/housing`, `/calendar`, `/revisions`, a permanent intelligence object, two explainers), and the complete internal link graph was extracted from rendered DOM rather than read from source. Source was consulted only to explain what the walk found. Data-source claims are sourced to official documentation, with API behaviour verified empirically where possible; unresolved rights questions are marked **UNRESOLVED** rather than guessed.

**One environment caveat, stated up front.** `Ask MacroChipz` reports `available: false, reason: NOT_CONFIGURED` in this environment (`OPENAI_MODEL` unset), so the Analyst's *populated* experience could not be audited. Its unavailable state was. And the browser extension could not produce a true mobile viewport, so mobile findings below are partial — see §A.13.

---

## PART A — First-time user audit

### The measurement that explains most of what follows

| | |
|---|---|
| Structured Intelligence objects in the database | **1,899** |
| Eligible for the homepage under `homepage_presentation_v1.0` | **6 (0.3%)** |
| Of those six, how many are Treasury yields | **6** |
| Objects by world | inflation 1,200 · jobs 693 · rates 6 · **housing 0** |

`ANALYSIS_CHANGE` is 1,532 of the 1,899 and is overwhelmingly coverage; all 358 `OBSERVATION_CHANGE` objects are first observations, not changes. The presentation policy correctly filters both out. The consequence is not a policy bug — **it is that the homepage can only ever be a bond page until a second kind of object becomes eligible.**

### A.1 — Can I tell what MacroChipz is in 5–10 seconds? **PARTIAL**

The frame is good: *"The economy right now / Know what changed in the economy — and prove why."* That is the thesis in eleven words, and "prove why" is the differentiator stated plainly.

Then the page immediately contradicts it. The lede is **"10-year Treasury yield — 5.01%"**, followed by "Also recorded": the 2-year, 30-year, 5-year and 10-year inflation-adjusted yields. A first-time consumer's first screen is six bond yields. Nothing on it is a thing they would say out loud.

### A.2 — Can I tell what is happening in the economy? **PARTIAL**

Below the fold, yes: Inflation **Mixed**, Jobs **Mixed**, each with "Why Mixed?" and a link. That is the product working.

But **Housing never appears on the homepage at all** in its active state, and Rates appears only as raw yields. A reader who never scrolls past the lede leaves believing MacroChipz is a Treasury tracker.

### A.3 — Is there an obvious next thing to explore? **STRONG on world pages, WEAK from home**

From `/`: "See the evidence →", "Explore Rates →", "Open Inflation →", "Open Jobs →", "View Calendar →". Real and well-labelled — but every one of them is Rates, Inflation, Jobs or Calendar. There is **no path from the homepage to Housing, to Revisions, or to any explainer.**

### A.4 — Natural discoverability, measured

Extracted from the rendered link graph:

| Capability | Discoverable from | Verdict |
|---|---|---|
| Inflation, Jobs, Rates, Housing, Calendar | Primary nav, every page | **Clearly discoverable** |
| Permanent intelligence objects | **Homepage only** (6 links) | **Contextually discoverable** |
| Evidence / provenance | In-page disclosures on every world page | **Contextually discoverable** |
| Explainers | World pages only (`Understand this`) | **Contextually discoverable** |
| **Revision Intelligence** | **`/inflation` and `/jobs` only** | **Difficult to discover** |
| Intelligence history | Inside `/inflation`, `/jobs` | **Difficult to discover** |
| **Ask MacroChipz** | `/inflation`, `/jobs`, `/rates` — **and unavailable here** | **Difficult to discover** |
| Sharing | Permanent object pages only | **Effectively hidden** |
| Point-in-time / replay | No consumer surface at all | **Orphaned** |

### A.5 — Effectively hidden capabilities

**Revision Intelligence is the headline problem.** It is the product's stated moat — #28 concluded that *"no reviewed product handles point-in-time correctness"* — and it is:

- absent from primary navigation;
- absent from the homepage;
- absent from `/rates` and `/housing` (two of four worlds);
- reachable only by scrolling deep into `/inflation` or `/jobs`.

**Sharing** exists only on permanent object pages, which are themselves homepage-only. So the share affordance sits two hops from the entrance, on the least consumer-legible objects in the product (Treasury yields).

**Point-in-time replay** has no consumer surface whatsoever. Substantial #31 engineering with zero user-facing expression.

### A.6 — Dead ends

**`/calendar` has zero outbound internal links.** Measured, not estimated. A reader who arrives there can only leave via the nav bar. It is the only true dead end in the product — and it is one of six primary nav items.

`/revisions` is a near-dead-end by content rather than structure: it correctly has nothing to show, but it does link back to all four worlds, which is better than Calendar manages.

### A.7 — Strong rabbit holes

Genuinely good, and worth protecting:

- **Explainer pages**: each links to a world page plus 3 related explainers, with "Explore next" and "How we know" sections. This is the best-designed navigation surface in the product.
- **Permanent object pages**: link to their world plus 3 concept-matched explainers, and carry the only Share control.
- **`/housing`**: links to `/rates`, two explainers, and an inline explainer link placed exactly where the confusion occurs.

### A.8 — Do the four worlds feel like one product? **PARTIAL**

Shell, typography, spacing, disclosure patterns and evidence placement are consistent. That part is genuinely well done.

What breaks the illusion is that **the worlds are structurally two different products**:

| | Inflation · Jobs | Rates · Housing |
|---|---|---|
| Has a methodology and a state | Yes | No |
| Homepage Current State card | Yes | No |
| "Why Mixed?" explanation | Yes | n/a |
| Intelligence history section | Yes | No |
| Links to `/revisions` | Yes | **No** |
| Ask MacroChipz | Yes | Rates only |

A reader moving from Jobs to Housing loses four capabilities without being told why. The *reason* is principled — Housing has no methodology and must not invent one — but the product never says so on the pages where the absence is felt.

### A.9 — Terminology and pattern consistency: **PARTIAL**

Consistent: page headers, "What changed", "Evidence & methodology", disclosure behaviour, `Understand this`.

Inconsistent:

- **`Rates Intelligence`** is the only page whose `<h1>` carries a product suffix; the other three are "Inflation", "Jobs", "Housing".
- **"Current state"** (Jobs) vs **"Current State"** (homepage) vs **"Underlying momentum"** (Inflation) for equivalent hierarchy positions.
- **"Intelligence history"** is machine vocabulary in a consumer heading; nothing tells a reader what it is before they open it.
- Housing's evidence disclosure is **"Where these numbers come from"** — the best-worded one in the product — while the other three use **"Evidence & methodology"**. The Housing wording is better; it should win.

### A.10 — Does anything still feel like developer tooling? **YES, in four specific places**

1. **The Calendar shows provider badges.** Every release row displays **`FRED`** as a literal badge. That is the engineering domain's vocabulary on the most consumer-facing schedule surface, and #38 spent an entire increment establishing that provider identity is not MacroChipz's vocabulary.
2. **The Calendar advertises data MacroChipz does not have.** It lists **GDP** (Sep 30), **Personal Income and Outlays**, **JOLTS**, and **Advance Retail Sales** — none of which exist in the product. A reader who clicks through expecting GDP finds nothing. One row is even marked `Past due`, which reads as a system fault rather than a schedule fact.
3. **"Also recorded"** is a database-shaped heading. It means "five more rows from the same query".
4. **Permanent object URLs** are `/intelligence/rates%3AUST_NOMINAL_10Y%3A2026-09-18` — a percent-encoded internal identity, in the address bar, on the pages most likely to be shared.

### A.11 — Duplicate or overlapping surfaces

- **"Also recorded" (homepage) and `/rates`** show the same six yields with different framing.
- **"How They Relate" restates "Current State"** immediately below it: *"Inflation is Mixed as of July 2026. Jobs is Mixed as of August 2026."* — two facts already on screen. **This is not a defect in the code**: `relate-composition-v1.md` (#23C) deliberately freezes this to exactly one composition sentence with no interpretation, and prohibits "confirms"/"diverges"/"Goldilocks"/"soft landing" absolutely. The constraint is right. **The heading is what oversells it** — "How They Relate" promises a relationship the frozen contract correctly refuses to assert.
- **`Intelligence history` and `/revisions`** are adjacent concepts on separate surfaces with no link between them.

### A.12 — Does the homepage represent what MacroChipz has become? **NO**

This is the single clearest finding of the audit. The product contains four worlds, permanent objects, revision intelligence, twelve explainers, provenance and an analyst. The homepage shows **Treasury yields, two state badges, and a release schedule for data the product does not have.**

### A.13 — Mobile: **PARTIALLY AUDITED**

The Chrome extension could not produce a true mobile viewport in this session (`resize_window` succeeded but media queries continued to match desktop). What was verified:

- `/housing` was measured at a genuine 390 px viewport during **#45**: zero horizontal overflow, chart viewBox aspect matching rendered aspect to three decimals at both 390 px and 1440 px.
- A harsher probe run here — every page's desktop layout forced into a 390 px container, so mobile grid classes do *not* apply — shows overflow counts dominated by `sm:grid-cols-*` containers that collapse at phone width. It is an upper bound, not a finding.

**Mobile verification of `/`, `/inflation`, `/jobs`, `/rates`, `/calendar` and `/revisions` at a real phone viewport remains outstanding**, and should be an explicit task in the next implementation increment rather than an assumption.

---

## PART B — SEE → UNDERSTAND → VERIFY matrix

| Surface | SEE | UNDERSTAND | VERIFY |
|---|---|---|---|
| **Home** | **PARTIAL** | **PARTIAL** | **STRONG** |
| **Inflation** | **STRONG** | **STRONG** | **STRONG** |
| **Jobs** | **STRONG** | **STRONG** | **STRONG** |
| **Rates** | **PARTIAL** | **PARTIAL** | **STRONG** |
| **Housing** | **STRONG** | **STRONG** | **STRONG** |
| **Calendar** | **PARTIAL** | **PARTIAL** | **MISSING** |
| **Revision Intelligence** | **MISSING** (no data) | **STRONG** | **MISSING** (no data) |
| **Permanent object** | **STRONG** | **PARTIAL** | **STRONG** |
| **Explainer** | n/a | **STRONG** | **STRONG** |
| **Ask MacroChipz** | — | — | — (unavailable here) |

**Home.** SEE partial: a fact is prominent, but it is the least consumer-relevant fact available. UNDERSTAND partial: "Up 0.05 percentage points over the last 5 trading days" is honest and means little to a consumer; nothing says why a 10-year yield matters. VERIFY strong: "See the evidence →" plus the 63 underlying values behind a disclosure.

**Inflation / Jobs.** The reference implementations. A named state, a "Why Mixed?" explanation in plain language, "What changed", evidence and methodology behind disclosure, and explainers. This is the product's thesis fully realised.

**Rates.** SEE partial: four yield cards with no hierarchy — the page does not say which number matters. UNDERSTAND partial: five strong explainers exist, but the page itself explains structure (curve, real yields, compensation) rather than consequence. VERIFY strong: per-observation provenance, session-window semantics stated, explicit limitations.

**Housing.** SEE strong: one headline figure per stage, the actual monthly count beneath it. UNDERSTAND strong: the pipeline diagram with its correction, plus "Why the big number is not a count of homes". VERIFY strong: concept id beside Census's own identifier, seven canonical limitations, required attribution.

**Calendar.** SEE partial: dates and names are legible. UNDERSTAND partial: `FRED` badges and `Scheduled`/`Past due` chips are system vocabulary, and the listed releases mostly concern data the product does not hold. VERIFY missing: there is no evidence surface — no source link, no explanation of where the schedule comes from.

**Revision Intelligence.** UNDERSTAND is the strongest single piece of writing in the product: it teaches the feature, enumerates what a revision will show, and explains honestly why older revisions cannot be shown. SEE and VERIFY are MISSING only because no revision has been captured yet — which is correct behaviour, not a defect.

**Permanent object.** SEE strong. UNDERSTAND partial: "Why this matters" and "Is this unusual?" are good, but the object is a Treasury yield and the URL is a percent-encoded identifier. VERIFY strong — this is the best VERIFY surface in the product.

---

## PART C — WOW → UNDERSTAND → EXPLORE → SHARE → RETURN

| Stage | State | Where it breaks |
|---|---|---|
| **WOW** | **WEAK** | The first screen is a bond yield. The genuinely surprising assets — *"Wait, the Fed doesn't set mortgage rates?"*, *"1.5 million homes weren't built this month"* — are twelve explainers deep and unreachable from the entrance. |
| **UNDERSTAND** | **STRONG** | Once a reader is on a world page or an explainer, this is excellent and consistent. |
| **EXPLORE** | **PARTIAL** | Strong *within* a world and *between* explainers. Nearly absent *across* worlds, and absent from the homepage. |
| **SHARE** | **WEAK** | The only Share control is on permanent object pages, which are homepage-only and are all Treasury yields. The most shareable things in the product — the explainers — have **no share affordance at all**. |
| **RETURN** | **MISSING** | No follow, no email, no alert, no "what changed since you were here". Nothing in the product asks a reader to come back or gives them a reason to. |

**The loop breaks first at WOW and terminally at RETURN.**

**This directly bears on the #46 Follow question.** Follow addresses RETURN, which is genuinely missing. But a Follow button on today's homepage would ask readers to subscribe to *Treasury yield movements*, because that is the only thing the homepage can currently surface. **Follow built before the WOW and SHARE stages are repaired will convert poorly and will teach us very little** — a weak signup rate would be ambiguous between "nobody wants to return" and "nobody was shown anything worth returning for".

---

## PART D — Explainer discovery

### The measured graph

Twelve explainers. **Zero orphans** — every one has at least one inbound link.

| Explainer | Inbound from | Strength |
|---|---|---|
| `fed-and-mortgage-rates` | `/rates`, `/housing`, object pages, 3 explainers | **Strong** |
| `why-the-10-year-matters` | `/rates`, object pages, 2 explainers | **Strong** |
| `what-is-a-treasury-yield` | `/rates`, object pages, 3 explainers | **Strong** |
| `saar-housing` | `/housing` ×2 (inline + list), 1 explainer | **Strong** |
| `permits-starts-completions` | `/housing`, 1 explainer | Moderate |
| `what-is-the-yield-curve`, `real-yields` | `/rates`, 2 explainers each | Moderate |
| `inflation-vs-prices`, `cpi-vs-pce`, `headline-vs-core` | `/inflation`, 2 explainers each | Moderate |
| `jobs-two-surveys` | `/jobs`, 1 explainer | Moderate |
| `unemployment-without-layoffs` | `/jobs`, 1 explainer | **Weakest** — one world page, one sibling |

### The real finding

The graph is healthy. **The entrance is the problem.** Every inbound path begins on a world page. There is no route to any explainer from `/`, `/calendar` or `/revisions`, and no route between explainers of different worlds except the deliberate `fed-and-mortgage-rates` bridge.

So a reader who arrives at the homepage and does not open a world page **will never encounter educational content at all** — while a reader arriving from a video lands directly on the single best page in the product. The educational layer is currently optimised for external arrival and invisible to internal arrival.

### Does MacroChipz need a Learn section?

**Not as a primary-nav item, and not yet.** Twelve explainers do not justify a top-level destination, and adding "Explainers" to a six-item nav would push the worlds — the actual product — to the side. It would also frame education as a separate place rather than something that happens where the confusion happens, which is the opposite of what the inline `saar-housing` link demonstrates works.

**The information architecture that the evidence actually supports, in order:**

1. **Questions as entry points on the homepage.** Not a section labelled "Explainers" — two or three *questions* ("Wait, the Fed doesn't set mortgage rates?") rendered as the hook they are. This is the WOW fix and the explainer-discovery fix in the same component, and it costs no new route.
2. **`Understand this` on every surface that lacks it** — `/calendar`, `/revisions`, and the homepage.
3. **A `/explain` index, unlinked from primary nav**, existing so the collection has a canonical home for sitemaps, for cross-linking, and for a "more questions →" link at the foot of each explainer. A destination that *exists* is not the same as a destination that *occupies navigation*.

**The right label, if one is eventually needed, is the question form itself, not a noun.** "Learn" and "Guides" both frame it as coursework. The product's own strongest asset is that its explainers are *questions a person already has*. If a section is ever named, name it for that.

---

## PART E — Feature discovery inventory

| Capability | Classification | Evidence |
|---|---|---|
| Four worlds | Clearly discoverable | Primary nav, all pages |
| Calendar | Clearly discoverable | Primary nav |
| Theme control | Clearly discoverable | Header |
| Evidence / provenance | Contextually discoverable | Disclosure on all four world pages |
| Explainers | Contextually discoverable | World pages only |
| Permanent objects | Contextually discoverable | Homepage only |
| "What changed" | Contextually discoverable | Inflation, Jobs, Rates |
| Visual evidence charts | Contextually discoverable | Home, objects, Housing, Rates |
| **Revision Intelligence** | **Difficult** | 2 of 4 worlds; no nav; no homepage link |
| **Intelligence history** | **Difficult** | Inside Inflation and Jobs only |
| **Ask MacroChipz** | **Difficult** + unavailable here | 3 pages, below the fold |
| **Sharing** | **Effectively hidden** | Object pages only; absent from explainers |
| **Point-in-time replay** | **Orphaned** | No consumer surface exists |
| Analytics foundation | Internal (correct) | Not user-facing by design |

**The pattern: every capability that required the most engineering is the hardest to find.** Revision intelligence (#43), point-in-time replay (#31), the Analyst (#33) and sharing (#40) are the four most expensive things in the repository and occupy the bottom four rows of this table.

---

## PART F — Cross-world connections

### What exists

- **`/housing` → `/rates`** — the only genuine cross-world link in the product, and it is done correctly: it names what MacroChipz tracks, names what it does not, and links onward without asserting a relationship.
- **`fed-and-mortgage-rates`** — bridges Rates and Housing through an explainer rather than through a claim.
- **"How They Relate"** — Inflation × Jobs, one composition sentence, no interpretation.

### What does not exist

Rates ↔ Inflation (despite the product computing market-implied inflation compensation, which is literally the two worlds in one number), Jobs ↔ Inflation beyond the frozen sentence, Housing ↔ Inflation, and any path from Rates or Jobs *toward* Housing. **Cross-world linking is currently one-directional and one-instance.**

### The constraint that must be respected

`relate-compare-audit-v1.md` §15/§16 and `relate-composition-v1.md` §2 freeze an absolute prohibition on cross-domain "agrees", "confirms", "diverges", "contradicts", "Goldilocks", "soft landing", "stagflation", "healthy economy", "the economy is [anything]". #28 additionally established that "market vs data" is *same-concept* confirmation (Class A) and therefore legitimate, while "equities confirm labor" is cross-domain and prohibited.

**This audit does not reopen any of that.** Everything recommended below is navigational or educational, not inferential.

### Safe opportunities, in order of value

1. **Reciprocal links.** `/rates` should link to `/housing` as `/housing` links to `/rates`. Pure navigation; asserts nothing.
2. **Market-implied inflation compensation is already a legitimate Class A bridge.** It is a Rates-page metric about *inflation*, computed from two Treasury series. Linking it to `/inflation` — with the existing "this is not a forecast" framing intact — connects two worlds using a number the product already computes, and requires no new claim.
3. **Concept-based "appears in" links.** `UST_NOMINAL_10Y` appears on `/rates`, on an object page, and in three explainers. A reader on any one of those could reach the others *through concept identity* (#38) — a structural relationship, not an economic one.
4. **Shared release surfaces.** The Employment Situation release already appears on `/jobs`; the Calendar knows which releases touch which worlds. Linking a calendar row to the world it affects is a factual mapping the repository already curates (`release_series_mappings`) and carries no causal content.
5. **An explainer that teaches the connection without asserting it.** The `fed-and-mortgage-rates` pattern generalises: an explainer can describe *how* two parts of the economy relate in general terms while MacroChipz's canonical layer asserts nothing about any particular month. This is the safest cross-world mechanism the product has, and it is currently used once.

---

## PART G / H — Data opportunity map

Framed as consumer questions rather than available feeds.

### Licensing summary, verified

| Source | Key | Commercial use | Attribution | Verdict |
|---|---|---|---|---|
| **Treasury Fiscal Data** | None | *"free, without restriction, and available to copy, adapt, redistribute, or otherwise use for non-commercial or commercial purposes"* | Not required | **Cleanest available** |
| **EIA** | Free, required | Public domain; *"U.S. government publications are in the public domain and are not subject to copyright protection"* | *"Source: U.S. Energy Information Administration"* + date; logo is a trademark, may not be used | **Clean** |
| **BLS** | Free (v2) | Public domain | "Source: BLS" + retrieval date + "cannot vouch" disclaimer | **Clean** (already in #28 §11.1) |
| **BEA** | Free | Permitted — terms expressly contemplate *"not-for-profit, commercial or otherwise"* | Verbatim non-endorsement string | **Clean** (verified in #35 §6.3) |
| **Census** (other programs) | Free, required | Permitted; public-domain federal work | Verbatim non-endorsement string | **Clean per program**, each needs its own review |
| **SEC EDGAR** | None | *"All Government-created content on sec.gov and EDGAR public filing content are free to access and reuse"* | — | **Clean, with access rules** |
| **Polymarket** | None for reads | **See §H.7 — REJECT** | — | **Blocked** |

---

### H.1 — BEA

**Consumer questions unlocked:** *"Are Americans spending more?"* · *"Is the economy growing?"* · *"Are people saving or stretching?"*

**Concepts:** real GDP and its components; Personal Consumption Expenditures (level, not just the price index MacroChipz already uses); personal income; the **personal saving rate**; corporate profits.

**Characteristics:** quarterly (GDP) and monthly (personal income/outlays); heavily revised — advance → second → third estimates, plus annual and comprehensive revisions; deep history; JSON API; free key; 100 req/min, 100 MB/min, 30 errors/min, then 429 + `Retry-After`. Current vintage via API only; BEA publishes a separate vintage archive.

**Architectural fit: excellent, with one genuinely new problem.** Provider → binding → observation → versioning fits unchanged. **But GDP is the first series whose revision behaviour is a scheduled, named sequence** (advance/second/third), and #43's `PROSPECTIVE_REVISION` is currently a binary "we watched it change". A GDP revision is not just *a* change — it is a *known stage*. That is the most interesting unbuilt thing in this entire audit: **MacroChipz's revision moat is most valuable precisely on the series that revise most predictably**, and GDP is the canonical example.

**Product value:** enables a **Growth** world and roughly half of a **Consumer** world. The personal saving rate is a strong consumer hook — it is one number, it is intuitive, and it is genuinely revealing.

---

### H.2 — BLS

**Consumer questions unlocked:** *"Is my pay keeping up with prices?"* · *"Is it getting harder to find a job?"* · *"Are people quitting or getting laid off?"*

**Concepts worth having:** average hourly earnings (CES); **JOLTS** — openings, quits, layoffs; average weekly hours; PPI; ECI. **Not worth having:** employment by detailed industry, productivity, and most of the CES universe — metric overload with no consumer question behind it.

**Characteristics:** monthly; 500 queries/day, 50 series/query, 20 years/request with a v2 key; current vintage only; public domain.

**Architectural fit: excellent, and it is the migration the repo already planned.** #28 concluded FRED should leave the critical path and BLS/BEA/Treasury should be sourced directly. Six of the twelve pre-#45 series are FRED-sourced and four of those are BLS or BEA data. **A BLS adapter is simultaneously a new-capability increment and the #M2 migration**, and #38's dual-binding design exists precisely to make that cutover verifiable.

**Product value, ranked by consumer question:**

- **Real wages** — "is my pay keeping up with prices?" is arguably the single best consumer economic question available, and MacroChipz already holds the price half. *Note: this is a Class A same-concept comparison only if framed as two separate series shown together; a computed "real wage" would be a MacroChipz calculation and must be labelled as one.*
- **The quits rate** — the most intuitive labour-market indicator that exists for a non-economist. People quit when they are confident.
- **Openings and layoffs** — completes the Jobs picture that CES and CPS alone cannot give.

---

### H.3 — Census (beyond `resconst`)

**Empirically verified during this audit:** `marts`, `bfs`, `m3`, `advm3`, `ressales` and `qss` all exist in the API, and **`resconst`, `marts`, `bfs`, `m3` and `ressales` share an identical 13-variable schema** — the same `cell_value` / `data_type_code` / `category_code` / `seasonally_adj` / `time_slot_id` / `error_data` structure the #45 adapter already parses and validates.

**This is the strongest architectural-fit finding in the audit.** Each of these programs is an allow-list entry plus concept bindings — **no new adapter, no second architecture, no new credential.**

| Program | Consumer question | Notes |
|---|---|---|
| **`marts`** — Advance Monthly Retail Trade | *"Are Americans spending more?"* | The flagship consumer question. Monthly, revised. Also already appears on the Calendar, which currently promises it and cannot deliver. |
| **`bfs`** — Business Formation Statistics | *"Are people starting businesses?"* | Genuinely under-covered by consumer media; a differentiated hook. Weekly and monthly. |
| **`m3` / `advm3`** — Manufacturers' Shipments, Inventories & Orders | *"Is manufacturing expanding?"* | Durable goods orders. Lower consumer salience; would be metric count more than insight. |
| **`ressales`** — New Home Sales | *"Are homes selling?"* | The natural Housing extension, and **it shares the SAAR trap `saar-housing` already explains** — the explainer would cover it for free. |
| **`intltrade/*`** | *"What are we buying from abroad?"* | Different schema, higher complexity, weakest consumer question. Defer. |

**Caution, as instructed:** `resconst`'s admission is **not** blanket Census approval. Each program above needs its own §11A entry: its own semantic review, its own revision behaviour, its own error/missing-data semantics. The *licensing* answer is likely the same; the *semantic* answer is not.

---

### H.4 — EIA

**Consumer questions unlocked:** *"Why is my gas bill higher?"* · *"What does it cost to fill the tank?"* · *"Is electricity getting more expensive?"*

**Characteristics:** weekly (retail gasoline), monthly (electricity, natural gas); free key required; 2M+ series; rate limits documented as tolerances with automatic temporary suspension; **public domain, commercial reuse and redistribution explicitly permitted**; attribution "Source: U.S. Energy Information Administration" with date; EIA logo is a trademark and must not be used.

**Architectural fit: clean.** A standard keyed JSON provider, structurally simpler than Census EITS.

**Product value: the highest "makes the economy feel alive" score of any source in this audit.** Inflation is an index; a gasoline price is a number people see on a sign on their way to work. It is the most tangible bridge between MacroChipz's abstractions and a reader's actual week — and weekly frequency means the product would have something genuinely new far more often than its current monthly cadence allows.

**The discipline it demands:** gasoline prices are *not* inflation, and a weekly gasoline print must never be presented as an inflation signal. That is a Class C cross-domain inference and is prohibited. Energy belongs beside Inflation as a separate, tangible cost surface — not inside it.

---

### H.5 — Treasury

**Assessment: little to add without metric bloat, with one exception.**

MacroChipz already holds the nominal and real par yield curves, which answer the Rates questions it can legitimately ask. Fiscal Data adds federal debt, spending, revenue and exchange rates — all with the most permissive terms of any source examined (*"without restriction... commercial purposes"*, no key).

**The exception is not a Rates metric at all.** Federal debt and interest costs answer a *different* consumer question — *"what does the government owe, and what does it cost to service?"* — which is a genuine and widely-asked question. It is not a Rates metric; it would be its own small surface, and it should be judged on that question rather than added to `/rates`.

**Recommendation: add nothing to `/rates`.** The page's weakness is hierarchy and consequence, not coverage. More yields would make it worse.

---

### H.6 — SEC EDGAR

**Consumer question:** *"How is the economy showing up in real companies?"*

**Characteristics:** XBRL Company Facts / Company Concept / Frames APIs; **no key**; declared `User-Agent` required; **10 requests/second**; sub-minute freshness; government content free to access and reuse.

**Architectural fit: poor today, and the reasons are structural rather than fixable by effort.**

1. **Grain mismatch.** Everything in MacroChipz is `(concept, date, value)` for a national aggregate. Company facts are `(company, taxonomy tag, period, unit, filing, amendment)`. `economic_observations` cannot hold that without becoming a different table.
2. **Normalisation is the whole problem, not a detail.** XBRL tags vary by filer and by year; companies restate; fiscal calendars differ; the same economic concept appears under different tags across filers. #38's concept/binding model is designed for *one provider series per concept*, not for reconciling thousands of filer-specific tags into one comparable concept. Doing it properly is a research programme.
3. **It changes what MacroChipz is.** Company-level data invites individual-security interpretation, which is adjacent to investment advice — a line the product currently keeps cleanly.

**Recommendation: not now, and not as an extension of the current architecture.** Record it as a genuinely different product capability that would need its own storage model and its own increment, not as a data source to bolt on.

---

### H.7 — Polymarket — **REJECT**

Investigated carefully, as instructed. **The technical answer is yes and the legal answer is no.**

**Technical availability, verified empirically.** `https://gamma-api.polymarket.com/markets` answers unauthenticated with HTTP 200 and rich per-market fields — `bestBid`, `bestAsk`, `conditionId`, `clobTokenIds`, `endDateIso`, `active`, `closed`, `acceptingOrders`, `feeSchedule` and more. The CLOB API, WebSocket streams, and an extensive documented API reference all exist. Discovery, pricing, volume and resolution metadata are all obtainable. **There is no technical obstacle whatsoever.**

**The disqualifying fact.** In October 2025 Intercontinental Exchange announced a strategic investment in Polymarket of up to **$2 billion**, completing a combined **$1.6 billion** cash investment by late March 2026. As part of that transaction, **ICE secured exclusive rights to distribute Polymarket's event-driven data globally**, delivering it through the **ICE Consolidated Feed** alongside securities pricing and reference data, and launched a **Polymarket Signals and Sentiment Tool** packaging those probabilities as institutional market signals.

**Why that is decisive for MacroChipz:**

1. **An exclusive global distribution right has been sold.** A public read API is an access mechanism, not a redistribution licence. Where exclusive distribution rights exist, unlicensed commercial redistribution is *more* hazardous, not less — there is now a counterparty with a $2 billion interest in enforcing them.
2. **ICE is the counterparty this repository has already rejected twice.** #28 §11.2 rejected ICE BofA credit spreads (*"Reproduction… prohibited except with prior written permission"*) and ICE DXY (*"Any use whatsoever of the U.S. Dollar Index, its formulation, components, weightings, values and/or methods of calculation… is strictly prohibited without… express written consent"*). Consistency alone argues against treating ICE-distributed data differently because it arrives via a different pipe.
3. **The CME FedWatch precedent is directly on point.** #28 rejected it because *"derived data is separately licensable, so recomputing and republishing is also barred."* Prediction-market probabilities are exactly that shape: displaying "70%" *is* republishing the derived datum.
4. **Polymarket US is operated by QCX LLC, a CFTC-designated contract market.** Exchange market data conventionally carries entitlement and licensing regimes, whatever the public API suggests.
5. **The terms could not be read.** `polymarket.com/tos` is geo-gated and `polymarket.us/tos` renders client-side; neither yielded readable clauses on commercial use, redistribution, derived data or IP ownership. **UNRESOLVED — and unresolved in the direction of caution, not permission.**

**Verdict: do not build on Polymarket.** Not "defer pending research" — the exclusive-distribution fact is not going to resolve favourably through further reading. It would resolve only through a written licence from ICE or Polymarket, which is a commercial negotiation, not an engineering task.

### H.7b — Expectations is still a good product idea. Its source is the Fed.

The *concept* the user is reaching for — separating **what happened** from **what participants expect** — is sound and valuable. It just does not need a prediction market.

**#28 §11.1 already lists, as MVP-eligible:**

- **FOMC Summary of Economic Projections / the dot plot** (`FEDTARMD` and related) — Fed Board, **public domain**, quarterly, explicitly marked *"MVP (labelled as participants' projections)"*.
- **NY Fed Survey of Consumer Expectations** — business-use licence, monthly, marked "Later".

The SEP is the *better* source for this product regardless of licensing: it is the actual policymakers' own published projections, it is public domain, it is already allow-listed, and it carries no epistemics problem — it is explicitly a set of participants' projections, labelled as such by its publisher.

**If an Expectations surface is ever built, on any source, the separation must be structural:**

- Expectations is a **distinct Structured Intelligence basis**, never `SOURCE_FACT` and never `METHODOLOGY_DERIVED`. A third value — something like `EXPECTATION` — with its own contract fields.
- Every expectation object carries the **question asked**, the **timestamp**, the **resolution criteria**, and the **publisher**.
- **No expectation may ever enter a methodology input, a state calculation, or a canonical conclusion.** The rule to encode: *a probability is never evidence about the present.*
- Presented as *"FOMC participants' median projection"* or *"prediction-market probability: 70%"* — never as *"the economy is X"*.

---

## PART I — Future economic map

| Area | Classification | Reasoning |
|---|---|---|
| **Inflation** | True world | Exists |
| **Jobs** | True world | Exists |
| **Rates** | True world | Exists |
| **Housing** | True world | Exists |
| **Consumer / Spending** | **True world** | Census `marts` + BEA PCE and saving rate. The strongest unbuilt consumer question in the product. |
| **Growth** | **True world, later** | BEA GDP. Real but quarterly, and its best feature (staged revisions) depends on revision intelligence maturing first. |
| **Energy / Cost of living** | **Contextual module, not a world** | EIA is the most tangible data available, but "energy" is not how a reader thinks about it — they think about *cost of living*. It belongs as a tangible-cost surface beside Inflation, not as a fifth nav item. |
| **Business activity** | **Contextual module** | Census `bfs` is a great hook and a thin world. It belongs inside Consumer or Growth. |
| **Expectations** | **Cross-world capability** | It is a *lens* on every world, not a place. And its only licensable source is the Fed's SEP. |
| **Revisions** | **Cross-world capability (exists, under-exposed)** | Already correctly built as cross-world. Needs discovery, not redesign. |
| **Explainers** | **Educational surface** | Needs an index and better entry points, not navigation. |
| **Trade** | **Not worth building now** | Weakest consumer question, different schema, high complexity. |
| **Company-level (SEC)** | **Not worth building now** | Different grain, different product. |
| **Prediction markets** | **Not to be built** | §H.7. |

**Navigation ceiling.** Six primary items today. **Seven is the maximum** this shell should ever carry. That means at most **one** more world reaches the top level — and on the evidence, it should be **Consumer**.

---

## PART J — Content and video connection

The architecture is already unusually well suited to this, and it is largely accidental — a by-product of the permanent-object and explainer work rather than a content strategy.

**What already works:**

- Explainers are **prerendered with real content** (`permits-starts-completions` 2,389 chars, `saar-housing` 2,620 chars of crawlable text), have stable human-readable URLs (`/explain/saar-housing`), carry `<title>` and description metadata, and need no JavaScript to be read. **A video description link lands on a real page, not an app shell.**
- Explainer questions *are* video titles. *"Wait, the Fed doesn't set mortgage rates?"* and *"Wait, 1.5 million homes weren't built this month?"* were written as hooks and work unchanged as thumbnails.
- Each explainer already ends in a rabbit hole — a world page plus 3 related questions.

**The three gaps that matter for this channel:**

1. **No share affordance on explainers.** The most shareable pages in the product cannot be shared from within them. Permanent objects have a Share button; explainers do not.
2. **No return mechanism.** A viewer arrives, reads, and leaves. This is the RETURN gap again, and it is most costly exactly on the traffic a video sends.
3. **No live number on an explainer.** This was a deliberate #44 decision — an explainer that fetches has an empty prerendered shell — and it was the right call. But the *reverse* link is free: an explainer can link to the live page without fetching anything, and `saar-housing` should point at `/housing`'s current figure the way `/housing` points at it.

**Objects that naturally generate content, ranked:** the two Housing explainers (a concrete, checkable, surprising number) · `fed-and-mortgage-rates` (measurably the most common misconception) · `jobs-two-surveys` and `unemployment-without-layoffs` (counter-intuitive and evergreen) · a genuine revision, when one is finally captured — **that is the single most distinctive piece of content this product will ever be able to make**, because almost nobody else can show it.

**Explicitly not recommended:** a CMS, a content model, an editorial calendar in the product, or pausing development to validate through video.

---

## PART K — What NOT to build

1. **More metrics on `/rates`.** Its problem is hierarchy and consequence, not coverage. More yields make it worse.
2. **A Housing state.** All five #45 prerequisites remain unmet.
3. **Any composite index or "economy score".** The single most tempting and most damaging addition available. #39 publishes no significance ranking for principled reasons; a score would undo that in one component.
4. **Cross-world causal language.** The frozen prohibition on "confirms"/"diverges"/"soft landing"/"the economy is X" stands. Cross-world *navigation* is the opportunity; cross-world *inference* is not.
5. **Prediction-market probabilities.** §H.7.
6. **A fifth, sixth and seventh world.** Navigation explosion. One more top-level world at most.
7. **An "Explainers" nav item.** §D.
8. **AI-generated explainers, summaries or headlines.** The explainer layer's value is that every sentence was written and reviewed. Generating them would forfeit exactly the differentiator.
9. **An estimated mortgage rate, or any Treasury→mortgage spread.** Already prohibited; worth restating because a Consumer or Housing expansion will make it tempting again.
10. **SEC company-level data as an extension of the current architecture.** §H.6.
11. **Detailed industry breakdowns from BLS/Census.** Metric overload with no consumer question behind it.
12. **A second "recent activity" surface.** "Also recorded", "What changed", "Latest data detected" and "Intelligence history" already overlap; adding another would compound a consolidation problem the product already has.

---

## PART L — Recommended roadmap

### The evidence

The product's **engine is strong and its entrance is weak.** Four worlds work; the homepage represents one of them. Twelve explainers exist; none is reachable from the homepage. Revision intelligence is the stated moat and is invisible from four of seven surfaces. The behavioural loop breaks at WOW and terminates at RETURN.

**`#46 Follow` should not be next.** Follow addresses RETURN, which is genuinely the most broken stage — but built today it would invite readers to subscribe to Treasury yield movements, because that is all the homepage can surface. The signal from a weak signup rate would be uninterpretable.

### Recommended sequence

**#45B — Product Cohesion** *(next; no new data, no new world)*

The highest-value increment available, because every fix is small and each one unlocks work already paid for.

1. **Make the homepage represent the product.** The lede policy currently admits only `RATES_MOVEMENT`. Either broaden eligibility to a world-summary object type, or add a deterministic "the four worlds, with their latest facts" section above the fold. **No ranking, no score, no "most important".**
2. **Put questions on the homepage.** Two or three explainer questions as entry points. Fixes WOW and explainer discovery together.
3. **Surface Revision Intelligence.** Link it from `/rates`, `/housing` and the homepage. Consider it as a seventh nav item — it is a cross-world capability, which is what the Calendar already is.
4. **Fix the Calendar.** Remove the `FRED` badges; stop advertising releases for data the product does not hold, or mark them explicitly as not-yet-tracked; give it at least one outbound link so it stops being a dead end.
5. **Add sharing to explainers.**
6. **Rename "How They Relate"** to something the frozen contract can actually pay for.
7. **Reciprocal `/rates` ↔ `/housing` links.**
8. **Verify mobile at a real viewport** on all seven surfaces (§A.13).
9. **Consistency pass**: `Rates Intelligence` → `Rates`; adopt Housing's "Where these numbers come from" wording everywhere.

**#46 — Consumer world (Census `marts` + BEA)** *(or BLS real wages — see below)*

Answers *"Are Americans spending more?"*. Reuses the #45 Census adapter against an **empirically verified identical schema**. Gives the homepage a second kind of thing to lead with, and gives Follow something worth following.

**#47 — Follow**

Now meaningful: there is a reason to return, and more than one world to return for.

**#48 — Launch Ready**

### The alternative worth weighing

**BLS before Census.** A BLS adapter delivers real wages and the quits rate — arguably stronger consumer questions than retail sales — *and* simultaneously executes the #M2 migration that #28 said must happen (FRED off the critical path). It is more architectural work for equal-or-better product value, and it retires a known licensing exposure.

**Recommendation: sequence by which unlock the human decision in §M.1 favours.** Both are defensible; Census is faster, BLS is more strategic.

---

## PART M — Unresolved human decisions

1. **Census-first or BLS-first for #46?** Census `marts` is faster (verified identical schema, adapter exists). BLS is more strategic (better consumer questions, retires the FRED dependency #28 flagged). This is a product-strategy call, not an engineering one.
2. **Does Revision Intelligence get a primary-nav slot?** It is the stated moat and currently the least discoverable capability. The counter-argument is that it has nothing to show until a revision is captured.
3. **Is `Ask MacroChipz` part of the launch product?** It is unconfigured in this environment, hard to find where it does exist, and absent from Housing by design. It needs a decision: invest in discovery, or accept it as a secondary feature.
4. **Does the homepage lede policy change, or does the homepage gain a section above it?** Both fix §A.12. The first touches a frozen presentation policy; the second does not.
5. **Is a "cost of living" surface (EIA) a module inside Inflation, or its own thing?** The data is the most tangible available and the framing decision is genuinely open.
6. **Does anyone want to pursue a Polymarket/ICE data licence commercially?** Engineering cannot resolve this. Absent a written licence, the answer is no.
7. **Confirm the seven-item navigation ceiling.** Everything in §I depends on it.

---

## Confirmations

- **No production code changed.** This increment created one document and one journal entry.
- **No API integrated.** Census dataset discovery and EITS schema comparison used **unauthenticated** metadata endpoints only; the Polymarket Gamma probe was an unauthenticated read for licensing assessment. No credential was used, read or accessed.
- **No new world created. No methodology changed. No secrets accessed.**
- **Nothing committed. Nothing pushed.**
