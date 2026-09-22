# MacroChipz 2.0 — Implementation Sequence

**Increment #36A.** Specification only. No production code, no behaviour change, nothing committed.

**This is the authoritative implementation roadmap.** It supersedes the build sequence in the Product Constitution's Appendix A, which was written before #36A's four decisions. The Constitution remains authoritative for *what* MacroChipz is; this document is authoritative for *the order we build it in*.

Companions: [`macrochipz-2.0-architecture.md`](macrochipz-2.0-architecture.md) · [`macrochipz-product-constitution-v1.md`](../product/macrochipz-product-constitution-v1.md) · ADR-034 (concept identity) · ADR-039 (rendering).

---

## 1. The decision that reshaped the roadmap

#36 sequenced four source-migration increments (#38–#41) ahead of all product work. **#36A rejects that ordering.**

Once economic concepts are separated from provider series identity (ADR-034), **FRED becomes one binding behind a stable vocabulary.** Every layer above the binding — the Structured Intelligence Layer, rendering, information architecture, the homepage, Revision Intelligence — depends on *concepts*, which do not change when the provider does.

**The seven questions #36A was asked to answer:**

| Question | Answer |
|---|---|
| Must BLS labor migration complete before Structured Intelligence can exist? | **No.** The Intelligence Layer projects from canonical results, which are concept-addressed. |
| Must BLS/BEA inflation migration complete first? | **No.** Same reason. |
| Must calendar migration complete before homepage/product work? | **No.** The calendar read model is provider-agnostic already; only the *sync* path knows FRED. |
| Can FRED-backed data temporarily satisfy provider-neutral interfaces? | **Yes — that is precisely the point of the abstraction**, and Treasury already proves the pattern works. |
| What technical debt does that create? | Three items, all bounded — §1.1. |
| What tests prevent provider assumptions leaking upward? | Four guards — §1.2. |
| Are there licensing or operational deadlines that make a migration genuinely blocking? | **One, and it blocks launch, not development** — §1.3. |

### 1.1 The technical debt this accepts, stated honestly

1. **Dual bindings during cutover.** Two `economic_series` rows share a `concept_id`, one active for reads. This is deliberate — it is the verification and rollback mechanism — but it is state that must be cleaned up after each migration, not left indefinitely.
2. **Evidence must carry both identities before bindings multiply.** If a second binding is added while evidence still stamps identity from a module constant, evidence starts lying. **This is why #38 precedes the migration track and is not negotiable.**
3. **Public launch is blocked on licensing, not on architecture.** Building on FRED is fine. Launching publicly on it is not.

### 1.2 The guards that keep the abstraction honest

| Guard | What it prevents |
|---|---|
| **Extend `tests/test_domain_architectural_independence.py` with a literal check** | A provider-shaped string reappearing in `app/domain/*` — exactly the `"PAYEMS"`/`"UNRATE"` leak found in `labor_release_processing.py:47-48` |
| **Every concept resolves to exactly one active binding at startup** | A concept silently reading `None` at runtime |
| **Golden-vector equality across bindings** | A migration that changes canonical output while appearing to succeed |
| **Evidence provenance test** | Evidence asserting a provider identity the observation did not come from |

### 1.3 The one real deadline

**There is no hard external deadline on the migration track.** #35 flagged the Federal Reserve Board's Data Download Program retiring the week of 9 November; **that applies to H.15, and this repository has no Fed Board client** — rates come from Treasury directly, verified. The concern does not apply.

**FRED's licensing does block public launch** (four independent clauses, #35 §6.7). The migration track must therefore complete before launch, and #47 gates on it. It blocks nothing before that.

---

## 2. Milestones — the seven sightings

| # | Milestone | Increment |
|---|---|---|
| 1 | **The new MacroChipz homepage** | **#42** |
| 2 | **The first complete rabbit-hole experience** | **#44** |
| 3 | **The first permanent shareable intelligence object** | **#40** |
| 4 | **Revision Intelligence as a first-class experience** | **#43** |
| 5 | **Housing** | **#45** |
| 6 | **Follow / email** | **#46** |
| 7 | **Launch-ready MacroChipz 2.0** | **#47** |

**Product becomes visible at #40 and recognisable at #42** — three increments earlier than #36's plan, because four migration increments moved off the critical path.

---

## 3. Phase 0 — Foundations

### #37 — Measurement Foundation

| | |
|---|---|
| **Purpose** | Establish the event contract, the privacy rules and a non-blocking transport. Nothing more. |
| **User value** | None directly. Honest: this increment is for us. |
| **Architectural value** | Every subsequent increment instruments as it is built instead of being retrofitted. The contract is cheap now and expensive later. |
| **Dependencies** | None. Fully independent. |

**Scope — exactly ten events.** Each exists only because it answers a product question.

| Event | Properties | The question it answers |
|---|---|---|
| `page_viewed` | `route_template`, `referrer_class`, `days_since_last_visit_bucket` | Which surfaces are used at all; do people come back? |
| `world_opened` | `world` | Does anyone explore past the homepage? |
| `evidence_expanded` | `object_type` | **Does anyone verify? — the headline metric. §2's central bet rests on this.** |
| `revision_opened` | — | Is the signature capability used? |
| `explainer_opened` | `slug` | Does education land, and which misconception? |
| `related_followed` | `from_type`, `to_type` | Do rabbit holes actually work? |
| `share_initiated` | `object_type` | Do objects leave? |
| `analyst_asked` | `context_type` | Is AI wanted where we placed it? |
| `follow_signup` | `target` | Is there a legitimate reason to return? |
| `empty_state_viewed` | `surface` | **Does honest absence retain or repel? — uniquely MacroChipz's question.** |

**Deliberately excluded:** time-on-page and scroll depth (engagement proxies, not product questions — and §31 forbids optimising for them) · calendar interaction (folds into `related_followed`) · video (does not exist) · anything per-user.

**Return measurement without identity.** `Since Last Visit` already stores a checkpoint in `localStorage`, client-side only, with no server-side per-user state. `days_since_last_visit_bucket` is derived from it and sent as a **coarse bucket**, never a timestamp and never an identifier. No cookie, no fingerprint, no identity graph.

**Acceptance criteria**

- A `track(event, props)` wrapper is the only call site; no component imports a vendor SDK.
- **Default transport is a no-op.** Provider selection is configuration and can change without touching call sites.
- Analytics is **fire-and-forget**: no `await`, no render blocking, no error surfacing. A test proves the page renders correctly when the transport throws and when it is absent entirely.
- No cookies. No personal data. No cross-site tracking. No fingerprinting.
- Disabled by default in development and test; a test asserts no event fires under test.
- Every event is documented with its product question. **An event without one does not ship.**
- Events are additive-only — no event is repurposed once named.

**Explicitly not in #37:** Open Graph tags, `sitemap.xml`, `robots.txt` (these move to #40, where they belong architecturally) · email capture (moves to #46) · dashboards, funnels, experimentation, cohorts.

---

### #38 — Economic Concept Identity

| | |
|---|---|
| **Purpose** | Separate what MacroChipz means from who publishes it. Implements ADR-034. |
| **User value** | None directly — but evidence stops being able to lie about its source, which is the product's core promise. |
| **Architectural value** | **The keystone.** It is what moves four migration increments off the critical path and makes each migration a reversible flag flip. |
| **Dependencies** | None. |

**Scope**

1. A **code-defined concept registry** — typed constants with explicit attributes (concept, geography, seasonal adjustment, frequency, canonical unit, **universe**, source program). The identifier is an opaque slug; nothing parses it.
2. **Role constants change value, not name.** `PRIMARY_SERIES_ID` → a concept identity. The 32 files referencing them keep their imports.
3. **The two literals in `app/domain/labor_release_processing.py:47-48` are removed.**
4. **Evidence carries both identities** — concept, plus the provider series the number actually came from, read from the observation's provenance rather than stamped from a constant.
5. **One additive column**: `economic_series.concept_id`, nullable → backfilled → non-null.
6. **FRED remains the only binding.** No migration happens here.
7. **Units move to the binding.** `PAYEMS_JOBS_PER_NATIVE_UNIT` becomes a property of the FRED binding, not of the concept.

**Acceptance criteria**

- Existing canonical outputs are **byte-identical on all existing fields**; golden vectors pass with only additive changes.
- The extended AST guard fails if any `app/domain/*` module contains a provider-shaped literal.
- A test asserts every concept resolves to exactly one active binding, and that startup fails loudly otherwise.
- A test asserts evidence's provider identity comes from observation provenance, **not** from a module constant — i.e. it would catch the `PAYEMS`-after-BLS-swap defect.
- No behaviour change is observable through any HTTP endpoint except the additive evidence field.

---

## 4. Phase 1 — The system becomes real

### #39 — Structured Intelligence Layer

| | |
|---|---|
| **Purpose** | One canonical representation that every surface renders. Implements ADR-036/037/038. |
| **User value** | None directly; every subsequent increment's value depends on it. |
| **Architectural value** | Prevents each surface inventing its own account of reality. |
| **Dependencies** | **#38 only.** Explicitly **not** any migration. |

**Scope:** the `IntelligenceObject` projection over existing monitor, what-changed, history and release-processing services, with types `STATE`, `CHANGE`, `REVISION`, `RELEASE`, `CONTEXT`, `EXPLAINER`. Required fields include `surfacing_rule`, `threshold_cleared`, `knowledge_basis` and `limitations`.

**Acceptance criteria**

- **It adds no economic logic.** An AST guard asserts `app/services/intelligence/*` performs no arithmetic on economic values — it projects.
- Every object is **recomputable** from canonical facts + methodology version + data vintage; a test recomputes and compares.
- `knowledge_basis` propagates, and a **mixed-basis object takes the weakest basis of its inputs** — tested directly.
- **An object without a `surfacing_rule` cannot be surfaced** — enforced by the type, not by convention.
- `limitations` is required, not optional.
- **"Nothing significant" is a typed value**, not an empty list.
- Analyst context packets are projections of the same object.

---

### #40 — Rendering Foundation + First Permanent Object

**🏁 Milestone 3 — the first permanent shareable intelligence object.**

| | |
|---|---|
| **Purpose** | Adopt React Router framework mode and prove the entire vertical stack on **one** object type. Implements ADR-039. |
| **User value** | A release page that is permanent, shareable, indexable, and lands on its own evidence. |
| **Architectural value** | Proves routing + prerender + metadata + OG + evidence end-to-end before scaling to every object. |
| **Dependencies** | #39. |

**Scope**

1. Framework-mode adoption via the vendor's component-routes guide, **on the v7 line** (avoiding the v8 import codemod): `react-router.config.ts` with `ssr: false`, `root.tsx`, `entry.client.tsx`, existing `<Routes>` preserved under a catch-all.
2. **One route migrated fully**: the release page, at its permanent URL, with a `meta` export.
3. **Build-time prerendering** with the path list fetched from the API.
4. **OG image generation** at build time — Satori → `sharp`.
5. `sitemap.xml` and `robots.txt`.

**Vertical, not horizontal — deliberately.** One object type proves the whole stack; #41 then scales a proven pattern rather than a hoped-for one.

**Acceptance criteria**

- A release page returns **server-visible** `<title>`, description, canonical, OG and Twitter metadata in the initial HTML.
- Its OG image is generated from the canonical object and carries the object's as-of date.
- Sharing the URL produces a correct preview card; **verified empirically against each platform's own debugger** (this also resolves the open question of whether unfurl crawlers execute JavaScript).
- **The static-site deployment is unchanged** — no Node runtime in production, no third deployable.
- All 821+ existing tests pass. If the `reactRouter()` plugin conflicts with the inline Vitest config, `vitest.config.ts` is split out.
- Evidence is reachable from the page in one interaction.
- **`vite build` wall-clock time is measured and recorded** — it is the input to whether the rebuild-per-release loop holds (ADR-039).
- Route modules stay thin: loader + `meta` only, all testable logic in presentational components taking plain props.

---

### #41 — Information Architecture, Routing, Worlds

| | |
|---|---|
| **Purpose** | The full URL scheme, redirects, and the three existing worlds as destinations. |
| **User value** | `/jobs` instead of `/labor`; permanent indicator, revision and explainer URLs; worlds that feel like places. |
| **Architectural value** | URLs stabilise once. Retrofitting permanent URLs later is far more expensive than getting them right now. |
| **Dependencies** | #40. |

**Scope:** all route types from Constitution §26 · 301s from `/labor` → `/jobs`, `/overview` → `/`, `/releases` → `/calendar` · world pages evolved from the existing Inflation/Labor/Rates pages · declared cross-world relationships, **typed by kind** (mechanical, identity, causal, empirical, correlational, contextual).

**Acceptance criteria**

- Every route type resolves, prerenders, and carries correct metadata.
- **Every old URL 301s**; a test asserts no previously-valid URL 404s.
- Every world page has **≥3 outbound contextual links**, asserted by test.
- Relationship *kind* is carried through to the UI — a mechanical relationship and a correlation do not render identically.
- `/evidence/{id}` is `noindex`.
- No thin pages; no programmatic mass generation.

---

### #42 — Homepage 2.0

**🏁 Milestone 1 — the new MacroChipz homepage.**

| | |
|---|---|
| **Purpose** | THE LEDE, Pulse, What Changed, Explore, What's Next. |
| **User value** | **This is where MacroChipz 2.0 becomes recognisable.** |
| **Architectural value** | Proves deterministic significance ranking drives presentation. |
| **Dependencies** | #41. |

**Much of this already exists on `/overview`:** `CurrentStateSection` → Pulse; the two what-changed previews → What Changed; `UpcomingReleasesPreview` → What's Next; `SinceLastVisit` and `HowTheyRelate` survive unchanged. **This increment is largely re-composition, not construction.**

**Acceptance criteria**

- **THE LEDE is selected deterministically** by published significance rank — never by editorial choice, never by a model. Tested against fixtures including a day with no release.
- **THE LEDE is never empty**: with no release and no revision, an explainer bound to current data occupies it.
- **No block exists whose honest state is usually empty.** Radar gets no standing block.
- Every block has a designed, tested empty state.
- The quiet-day homepage is a **designed state**, tested explicitly, and names the next scheduled event.
- **First screen legible at 390px**; Pulse is a horizontal scroll, not a grid pushing content below the fold.
- The page is complete and correct with the Analyst unavailable.
- No chat box in the hero.

---

### #43 — Revision Intelligence

**🏁 Milestone 4 — the signature capability.**

| | |
|---|---|
| **Purpose** | The thing nobody else has built. Time Machine Stage 1. |
| **User value** | "The number you remember was wrong — here's what it actually says, and what we concluded at each point." |
| **Architectural value** | Turns `observation_versions` and `ReplayService` from infrastructure into product. |
| **Dependencies** | #42. |

**Scope:** prominent revision marking on every revisable figure · permanent revision pages · a new `revision_significance_v1.0` methodology (binomial sign test on revision direction; published-distribution comparison for magnitude) · methodology-then vs methodology-now via replay · **agency-published thresholds shown inline** ("BLS's own standard is that a change under 122,000 can't be told apart from zero — this month's was 85,000").

**Acceptance criteria**

- `revision_significance_v1.0` is published as a methodology document before code depends on it.
- **A routine revision is explicitly not narrated as news** — a test asserts a sub-threshold revision is recorded and not surfaced.
- Every historical claim renders its `knowledge_basis`; `OBSERVED` and `BACKFILLED` are **visually distinguishable, not footnoted**.
- A point-in-time claim with any `BACKFILLED` input **refuses rather than degrades**.
- The four time concepts are never conflated — tested.
- **Genuine prospective vintage capture begins**, regardless of when Stage 2 ships.

---

### #44 — Wait, Seriously? + Rabbit-Hole Linking

**🏁 Milestone 2 — the first complete rabbit-hole experience.**

| | |
|---|---|
| **Purpose** | The education layer and the linking rules that make exploration real. |
| **User value** | The acquisition wedge, and the content that carries the ~two-thirds of days with no release. |
| **Architectural value** | Proves explainer↔live-data binding — the Politano "link-the-claim" pattern, which nobody has built tooling for. |
| **Dependencies** | #43. |

**Scope:** five launch explainers (the Fed doesn't set your mortgage rate · falling inflation ≠ falling prices · why data gets revised · what CPI measures · why GDP can look fine while your life doesn't) · the linking rules from Constitution §27 · term definitions in place.

**`src/content/explanations/` already holds 34 curated `Explanation` constants and 8 lookup functions** — curated, never AI-generated, never canonical. The infrastructure substantially exists; this increment makes it addressable and binds it to live data.

**Acceptance criteria**

- **Every explainer links ≥1 claim to a live figure that updates** — tested, not asserted.
- The two designed loops in Constitution §27 are traversable end-to-end, **asserted by test**.
- Titles and slugs avoid ambiguous head terms ("inflation", "recession"); clean terms only.
- Every explainer reaches CONCEPT → CURRENT DATA → RELATED WORLD → EVIDENCE.
- Explainers are permanent, prerendered, shareable and indexable.

---

### #45 — Housing World

**🏁 Milestone 5.**

| | |
|---|---|
| **Purpose** | The first genuinely new data source, serving the acquisition wedge. |
| **User value** | The world the wedge audience arrives looking for. |
| **Architectural value** | Proves the concept/binding design against a source that was never FRED. |
| **Dependencies** | #44; Census adapter from the migration track. |

**Scope:** Census housing starts and permits · `UST_NOMINAL_10Y` presented as an explicitly **labelled proxy** for mortgage rates · **no canonical housing state.**

**Acceptance criteria**

- **Housing ships with data and no state.** A test asserts no state is rendered for Housing. The limitation is stated in the interface, not buried.
- The 10Y proxy is labelled wherever it appears, and the page explains *why* — "that's what actually moves your mortgage rate, and the survey number isn't ours to republish."
- **No Freddie Mac PMMS data** is fetched, stored or displayed, by any path.
- Census attribution renders verbatim from provenance.

### DELIVERED as Increment #45 — with two deliberate departures

**Met:** Housing ships with data and no state, asserted by tests on both sides. No Freddie Mac PMMS data is fetched, stored or displayed by any path. Census attribution renders verbatim, in the site footer on every page and on the `/housing` response.

**Departure 1 — completions were added.** Scope above says "starts and permits". #45 ingested **completions** as well, because the pipeline question the page answers (*are more homes entering construction?*) is incoherent with only two of its three stages: permits and starts alone show what is beginning and nothing about what is finishing. Three stages from one dataset, one release and one licensing review is not scope creep; it is the smallest coherent version of the question.

**Departure 2 — the 10Y proxy was NOT shipped, and the acceptance criterion about labelling it is therefore moot.** The reasoning is recorded in `housing-world.md` §10, and it is not that the label would be inaccurate. **Two numbers side by side on one page read as connected**, whatever the caption says. MacroChipz publishes no housing-to-rates relationship, no elasticity and no lag, so a Treasury yield rendered beside permits and starts would be the page asserting something its own data has measured nothing about. The rate-context section contains no figure at all: it names what MacroChipz tracks, names what it does not, and links to `/rates` and to the Fed/mortgage explainer.

**Also added, beyond scope:** the unadjusted monthly counts alongside the seasonally adjusted annual rates. Not richness — the pair is what makes the annual rate explicable rather than mysterious, and it is what the `saar-housing` explainer rests on.

**What `housing_v1.0` would require before it could legitimately exist:** a defensible state vocabulary grounded in housing economics rather than chosen for visual symmetry; sufficient history for any historical-position claim (Census starts go back to 1959, so depth is available once ingested); a published methodology document; golden vectors; and a defensible answer to what "housing is cooling" means when starts, permits, prices and rates can move in opposite directions simultaneously. **Until all five exist, Housing has no state.**

---

### #46 — Follow + Email

**🏁 Milestone 6.**

| | |
|---|---|
| **Purpose** | The only owned, algorithm-independent return channel. |
| **User value** | "Tell me when MacroChipz processes this" — one notification, at a known time, for a thing they asked about. |
| **Architectural value** | First anonymous write surface; first personal data. |
| **Dependencies** | #45. |

**Scope:** email capture with double opt-in · world- and release-level follows · release-driven triggers from significance-gated objects · a hard per-subscriber frequency ceiling.

**Acceptance criteria**

- **A change that did not clear its threshold cannot notify** — tested.
- The frequency ceiling is **enforced in the system**, not by editorial restraint — tested.
- Every notification states why it fired and links to evidence.
- One-click unsubscribe, honoured immediately.
- Rate-limited, validated, double opt-in. Storage is an email address and subscriptions — **nothing else**.
- **Nothing cleared a threshold → nothing sends.** No digest-to-stay-present.

---

### #47 — Launch Readiness

**🏁 Milestone 7 — launch-ready MacroChipz 2.0.**

| | |
|---|---|
| **Purpose** | Close everything that must be true before the public sees it. |
| **Dependencies** | #46 **and the entire migration track (#M1–#M4)**. |

**Scope:** full accessibility audit against WCAG 2.2 AA · performance pass · methodology and corrections pages · the source-derived attribution block · sponsorship-separation statement · **verification that no FRED dependency remains in any path serving public traffic.**

**Acceptance criteria**

- **No FRED call occurs in any code path**; the FRED client is removed and the AST guard forbids reimporting it.
- Attribution renders **from provenance data**, per source, verbatim where BEA and Census require it. The hardcoded FRED footer string is gone.
- WCAG 2.2 AA verified, including non-colour-only state communication and chart text alternatives.
- Every page works with the Analyst unavailable and degrades legibly with the database unavailable.
- `/methodology` and `/corrections` exist and are reachable.
- **A launch checklist records the unresolved licensing questions** (§6) and confirms none blocks launch on the sources actually in use.

---

## 5. The migration track — parallel, not blocking

**These must complete before public launch. They block no product increment.** Schedule them whenever convenient before #47.

| # | Increment | Purpose | Acceptance |
|---|---|---|---|
| **#M1** | **Source abstraction + FRED adapter** | `SeriesSource` / `ReleaseScheduleSource` protocols; `FREDSource` implements them. Pure refactor. | Zero behaviour change; golden vectors byte-identical; no service depends on a concrete client |
| **#M2** | **BLS binding for labor + cutover** | Smallest real migration — two series, one agency. | Dual bindings compared over overlapping history; `labor_v1.0` byte-identical from BLS; **CES units verified against BLS's own documentation, not assumed from FRED's**; cutover is a reversible flag |
| **#M3** | **BLS + BEA bindings for inflation + cutover** | Four series, two agencies. | `inflation_v1.0` byte-identical; **full-history re-pull implemented for every seasonally adjusted series** (ADR-043 candidate); revisions detected rather than overwritten |
| **#M4** | **Provider-neutral release calendar** | BLS iCal + BEA JSON. **Supersedes ADR-020.** | Calendar renders from first-party schedules; FRED release IDs demoted to bindings; Census handled by an explicit, named mechanism |

**Why #M2 before #M3:** two series and one agency is a smaller blast radius than four series and two agencies, and #M2 is where the dual-binding cutover mechanism gets proven. **Why the whole track after #38:** without concept identity, each migration is a rewrite instead of a flag flip.

**The seasonally-adjusted re-pull rule is the highest-risk correctness item in the entire roadmap.** CES recomputes its seasonal adjustment concurrently every month and CPI SA is revised five years back annually. A pipeline that appends rather than re-pulls will silently drift every January — and on a product that claims determinism, that is worse than never having claimed it.

---

## 6. Post-launch

Unchanged from Constitution §36, in dependency order: deep historical re-ingestion → the Brief → Consumer and Growth worlds → **Radar registry with offline evaluation only** → Time Machine Stage 2 → **Radar user-facing, conditional on evaluation** → content system and video.

**Radar cannot skip its offline evaluation period.** An unevaluated detector reaching users would damage the trust position more than shipping no Radar at all.

---

## 7. Unresolved licensing questions

Carried forward unresolved. **None blocks product development; one gates launch.**

| Question | Status | Effect |
|---|---|---|
| Would the St. Louis Fed grant written permission for FRED/ALFRED? | **Unresolved.** One email. | A yes makes the backward Time Machine immediately buildable and reduces migration urgency. Does not block anything. |
| Does FRED's per-user-key clause bind a cached server-side architecture? | **Unresolved. ⚖️ Legal question.** | A favourable reading would change the migration's necessity. **Assume unfavourable.** |
| Would Freddie Mac license PMMS? | **Unresolved.** One email. | Would let Housing show actual mortgage rates. Until then, the labelled 10Y proxy. |
| Census 500/IP/day threshold | **Unconfirmed from any first-party page.** | Infrastructure sizing only. |
| Does the Treasury fiscaldata grant extend to home.treasury.gov? | **Unresolved.** | Almost certainly yes; one-line confirmation. |

**No legal certainty is asserted anywhere in this roadmap.** #47's checklist records what is still open at launch rather than pretending it closed.

---

## 8. Open technical questions, with owners and cost

| Question | Resolved by | Cost |
|---|---|---|
| Do social unfurl crawlers execute JavaScript? | **#40**, empirically — publish a test page, run each platform's debugger | Minutes |
| Does `reactRouter()` coexist with the inline Vitest config? | **#40** spike | ~1 hour |
| `@vitejs/plugin-react` alongside `reactRouter()`? (vendor's guide and template disagree) | **#40** | Minutes |
| Is `vite build` fast enough for rebuild-per-release? | **#40** — measured, recorded | Free; it is a build |
| Charting: hand-rolled SVG or a library? | **Resolved — ADR-041, §9** | — |
| When does the in-process Analyst rate limiter become wrong? | At the first multi-instance deployment | Not now |

---

## 9. Charting — decided (ADR-041)

**Hand-authored SVG over d3 math primitives** (`d3-scale`, `d3-shape`, `d3-time-format`, +15.7 KB gzip measured). **No charting library for in-page charts.** ECharts is reserved for **server-side rendering only** and is forbidden in the client bundle by guard test.

The SSR requirement from ADR-039 did most of the deciding, and it eliminated the obvious answer. Measured against React 19.2.8 with no DOM globals, **Recharts emits a 127-byte empty `<div>` containing zero `<svg>` elements** — a tracked regression from 2.x, still unfixed fifteen months after 3.0. uPlot, Chart.js, Observable Plot, visx's `XYChart` and Nivo's `ResponsiveLine` fail the same requirement.

**visx *primitives* pass SSR and remain the designated escape hatch. Trigger: touch tooltips needed on more than one chart** — that single capability is what justifies the cost over d3 math alone. It is the first thing to reconsider in #41.

**Two existing defects become #41 acceptance criteria:**

- **The chart is not `aria-hidden`**, despite its own doc comment, this project's #35 research and #36's architecture all saying so. It uses `role="img"` + `aria-label` **plus** an `sr-only` `<figcaption>` **plus** the table. #41 picks one pattern — decorative-plus-table, or labelled-image — not all three.
- **`preserveAspectRatio="none"` squashes the chart ~37% horizontally at 390px.** The SSR-safe fix is a viewBox per breakpoint with `xMidYMid meet`; `ResizeObserver` measurement would reintroduce exactly the server-rendering failure that disqualified Recharts.

**A chart primitive set must be designed rather than accreted** — axis, line, band, annotation, revision overlay — or six worlds will produce six divergent implementations.

---

## 10. Sequence rules

1. **#37 and #38 are first**, and they are independent of each other.
2. **#38 precedes the migration track absolutely.** Without concept identity, evidence starts lying the moment a second binding exists.
3. **#39 precedes every surface.** Surfaces built before the object each invent their own reality.
4. **#40 precedes #41** — prove the vertical stack on one object before scaling it.
5. **#41 precedes #42** — URLs stabilise once; redirects are cheap early and expensive later.
6. **The migration track blocks only #47.**
7. **Nothing post-launch begins until launch has been measured** long enough to say something.
8. **Accessibility, mobile-first layout, evidence completeness and the architectural guards are acceptance criteria on every increment**, not increments of their own. An increment shipping an inaccessible surface, a desktop-first layout, or a claim without evidence is not finished.

---

**This document is authoritative for MacroChipz 2.0 implementation order.** It is amended by explicit increment. Where an increment discovers a better sequence, take it — and record why here.
