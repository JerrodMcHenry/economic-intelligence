# Increment #45B — Product Cohesion: Implementation Specification

**Status:** specification, written before implementation. Requirements source: `macrochipz-product-cohesion-data-opportunity-audit-v1.md` (#45A). Baseline: HEAD `2fdde80`.

**Scope discipline.** No new source, no new world, no new canonical methodology, no AI capability, no score, no significance ranking, no data ingestion. `homepage_presentation_v1.0` is **not weakened** — its eligibility rules are untouched. Everything below is navigation, orientation, discovery or copy.

---

## The constraint that shapes the whole increment

#45A measured: 1,899 intelligence objects, **6 homepage-eligible, all Treasury yields**. The eligibility policy is correct — it excludes 1,532 coverage records and 358 first observations. The homepage is an accurate projection of a database whose only *changes* are in one world.

**Therefore the fix is not to widen eligibility.** THE LEDE keeps its policy, its three states and its honesty. What the homepage lacks is a **second, clearly separated layer**: orientation to the four worlds, which is a different claim ("these exist and here is the latest data MacroChipz holds") from the lede's claim ("this changed").

The two must not blur. Orientation carries no change language, no significance, and no state MacroChipz has not already published.

---

## Finding → fix → acceptance → test

### F1 · Homepage does not represent the product (#45A §A.12)

| | |
|---|---|
| **Fix** | New `WorldOrientation` section on `/`, rendered from `ECONOMIC_WORLDS` so it can never drift from the registry. Per world: label, one-line description, latest-data period where the page already knows it, and a link. |
| **Data** | Inflation/Jobs periods from the two monitor resources the page already fetches. Rates from the already-fetched intelligence objects. Housing from **one** new `GET /api/v1/housing` call — an existing endpoint, independently loaded, failure-isolated like every other homepage resource. |
| **Refuses** | No state badges (they already exist in `CurrentStateSection`; duplicating is the surface-duplication #45A §A.11 flagged). No Housing state — none exists. No ordering by importance. No change language. |
| **Acceptance** | All four worlds appear and link correctly; section renders with zero data; a failed housing fetch removes only Housing's period line; no world is described as up/down/good/bad. |
| **Tests** | `Home.test.tsx`: four worlds present and linked; derived from registry length; no significance vocabulary; renders under loading/error. |

### F2 · No educational entry point from home (#45A §D)

| | |
|---|---|
| **Fix** | `HomeQuestions` — a **curated** list of three explainer ids on the homepage. A hand-written constant, not a recommender, not popularity, not similarity. |
| **Acceptance** | Three questions render as links to `/explain/<slug>`; ids are validated against the registry at module load so a typo fails a test rather than rendering a dead link. |
| **Tests** | Curated ids all resolve; links render; no ranking/scoring identifier in the module. |

### F3 · Explainers have no site-level home (#45A §D)

| | |
|---|---|
| **Fix** | New prerendered route **`/explain`** — a question-led index, grouped by world using curated registry data. **Not added to primary navigation** (#45A §D: twelve explainers do not justify a nav slot, and it would push the worlds aside). |
| **Inbound** | From each explainer page ("All questions →"), from the homepage questions section, and from `UnderstandWorld` on each world page. |
| **Acceptance** | `/explain` prerenders with real content; every one of the twelve explainers is reachable from it; primary nav still has six items. |
| **Tests** | Index lists every registry explainer; `EXPLAINER_PATHS` still prerendered; nav item count unchanged; **every explainer has ≥1 intentional inbound path** (registry-level assertion). |

### F4 · Revision Intelligence is undiscoverable (#45A §A.5)

| | |
|---|---|
| **Fix** | A shared `RevisionsLink` rendered on `/` , `/rates` and `/housing` (already present on `/inflation`, `/jobs`). |
| **Housing justification** | Required by the instruction to link Housing "only where the data semantics justify it". They do: Census revises the prior month in **every** monthly release (#45 verified "the revised July rate" in the published release), Housing observations are versioned through the shared `ObservationVersionWriter`, and #45 proved the `PROSPECTIVE_REVISION` path end to end. |
| **Refuses** | Wording is forward-looking — *what MacroChipz will show when one arrives* — never a claim that revisions exist, and never that backfilled baselines prove original published values. |
| **Tests** | Link present on all four worlds + home; copy contains no claim that a revision has occurred; `/revisions` reachable from ≥5 surfaces. |

### F5 · Calendar is a hard dead end (#45A §A.6)

| | |
|---|---|
| **Fix** | Enable onward navigation on calendar rows via the existing frozen `releaseMonitorRelation` mapping — **and** handle its third case honestly. |
| **The honest third case** | GDP, JOLTS and Advance Retail Sales have **zero mapped series** (verified in the seeded migrations). On `/calendar`, `releaseMonitorCta` currently returns "View Calendar →", which is circular. Replaced with an explicit statement that MacroChipz does not yet track this release's data — directly answering #45A §A.10.2 and the instruction "do not claim MacroChipz covers GDP or retail sales when it does not". |
| **Acceptance** | `/calendar` has ≥1 outbound internal link; CPI/PCE rows link to `/inflation`, Employment Situation to `/jobs`; GDP/JOLTS/Retail Sales rows link nowhere and say so. |
| **Tests** | Outbound link count > 0; untracked releases render the not-tracked note and no world link; no route claims coverage it lacks. |

### F6 · `FRED` badge is provider jargon on a consumer surface (#45A §A.10.1)

| | |
|---|---|
| **Fix** | Remove the bare `{item.provider}` token from the row. Provenance is **not hidden** — it moves into the existing `ReleaseScheduleDisclosure`, stated in a sentence a reader can parse. |
| **Refuses** | Deleting provenance. The schedule's source remains inspectable on the same page. |
| **Tests** | No bare provider token in a row; the disclosure names the schedule source; `schedule_status` still rendered from the backend. |

### F7 · Explainers cannot be shared (#45A §C, §J)

| | |
|---|---|
| **Fix** | `ShareButton` on every explainer page, reusing the existing component unchanged in behaviour. |
| **Analytics** | Reuses the existing `share_initiated` event. Requires **one value** added to the closed `ObjectType` union: `"explainer"`. Documented in §Measurement below. No new event, no vendor, no URL, no text. |
| **Type change** | `ShareButton`'s `objectType` prop widens from `IntelligenceType` to the analytics `ObjectType`. Strictly additive. |
| **Tests** | Share renders on explainers; share works when `track` throws; no tracking parameters appended to the URL; correct absolute URL shared. |

### F8 · "How They Relate" oversells a frozen contract (#45A §A.11)

| | |
|---|---|
| **Fix** | Heading only: "How They Relate" → **"Inflation and Jobs, side by side"**. The frozen `relate-composition-v1.md` sentence and component logic are **unchanged**. |
| **Rationale** | The contract juxtaposes two known facts and is explicitly forbidden from asserting a relationship. The heading promised one. |
| **Tests** | Heading renders; composition sentence unchanged; prohibited vocabulary still absent. |

### F9 · Cross-world paths are one-directional (#45A §F)

| | |
|---|---|
| **Fix** | Reciprocal `/rates` → `/housing`; `/inflation` → `/rates` anchored on market-implied inflation compensation, which #28 classifies as **Class A same-concept** and is therefore a legitimate bridge. |
| **Refuses** | Any causal language. Navigation only. The frozen cross-domain prohibition (`relate-compare-audit-v1.md` §15/§16) is untouched. |
| **Tests** | Links present; a vocabulary guard asserts no prohibited cross-domain word appears in the new copy. |

### F10 · Terminology inconsistency (#45A §A.9)

| | |
|---|---|
| **Fix** | `Rates Intelligence` → `Rates` (`<h1>` only; methodology id, endpoint and `RatesState` untouched). Evidence disclosure summaries adopt Housing's better wording, "Where these numbers come from". |
| **Tests** | Page titles match registry labels for all four worlds. |

### F11 · Mobile partially unverified (#45A §A.13)

| | |
|---|---|
| **Fix** | Browser verification at 390px and desktop across Home, four worlds, Calendar, Revisions, a permanent object, an explainer and `/explain`. Report honestly if the viewport cannot be obtained. |
| **Tests** | Where testable in jsdom: no fixed widths introduced; chart `preserveAspectRatio` unchanged. |

### F12 · Analyst (#45A §7)

Inspect only. If `NOT_CONFIGURED`, verify the honest unavailable state renders and **report populated-state testing as incomplete**. No widening of context or capability.

---

## Measurement

Existing closed vocabulary. **One addition, and only one:**

- `ObjectType` gains the value `"explainer"`, used solely by the existing `share_initiated` event.

Justification: `share_initiated` already answers "do objects survive leaving MacroChipz?" and an explainer is exactly such an object. A new event would fragment the same question across two names. No new event name, no new property, no vendor, no raw text, no URL, no query string.

---

## Out of scope, deliberately

- Widening homepage eligibility, or promoting coverage/backfill noise.
- A consumer replay interface (#45A recommends documenting a proposal instead; recorded as deferred).
- A primary-nav slot for explainers or revisions — both are reachable; a nav decision is a human call recorded in #45A §M.
- Any new data source, world, methodology, or Housing state.


---

## Implementation outcome

Every finding above was implemented as specified, with two deviations and one addition, all recorded here rather than left to be discovered.

### Discovery graph, measured before and after

Re-run with the same method #45A used — rendered DOM, live backend.

| Surface | Internal links before | after | Worlds linked before → after | `/revisions` before → after | Explainers before → after |
|---|---|---|---|---|---|
| `/` | 9 | **15** | 3 → **4** | ✗ → **✓** | 0 → **4** |
| `/inflation` | 4 | 5 | 0 → **1** | ✓ → ✓ | 3 → 3 |
| `/jobs` | 3 | 3 | 0 → 0 | ✓ → ✓ | 2 → 2 |
| `/rates` | 5 | **8** | 0 → **2** | ✗ → **✓** | 5 → 5 |
| `/housing` | 4 | 5 | 1 → 1 | ✗ → **✓** | 3 → 3 |
| `/calendar` | **0** | **2** | 0 → **2** | ✗ | 0 |
| `/revisions` | 4 | 4 | 4 → 4 | — | 0 |
| `/explain` | — | **16** | — → **4** | ✗ | **12** |

**The two headline results:** `/calendar` is no longer a dead end, and **all four worlds now link to `/revisions`** where two did.

### Deviations from the specification

1. **`ReleaseScheduleDisclosure` gained a second paragraph, not an appended sentence.** The spec said provenance "moves into" the disclosure. Implementing it as an append edited a sentence frozen by `release-intelligence-v1.md` #2/#13 and broke its exact-text test. Corrected: the frozen sentence renders unchanged in its own element and the provenance line sits beside it. A test now asserts the frozen sentence byte-for-byte.

2. **`IntelligenceShell` also needed the Census attribution.** Not in the spec, and found during verification: #45 added the required non-endorsement notice to `AppShell` only, so permanent object pages and explainer pages — the pages most likely to be a reader's first and only view — carried no Census notice at all. Fixed with the identical verbatim sentence.

### A frozen contract updated deliberately

`overview-attention-model-v1.md` §17 froze "a non-monitor release's next action is `/releases`", which is circular on `/calendar` and was therefore implemented as "no CTA on `/calendar` at all". #45B changes the unconditional half of that rule and records the change as a §17 addendum in that document: a non-monitor release now points nowhere and says MacroChipz does not track it. **§3A's correction is untouched** — navigation still keys off canonical monitor relation, and JOLTS still receives no Jobs attribution.

### Guards that were kept rather than weakened

- The homepage's publication-language guard flagged the word "published" in new copy. The **copy changed**, not the guard: a "Past due" badge beside that word reads as a claim that data arrived, and the guard cannot distinguish a general statement from a specific one.
- The analytics-abstraction guard flagged `ShareButton` importing `analytics/events`. Fixed by importing the type from the analytics **barrel**, which already re-exports it — the guard was right that reaching deeper bypasses the abstraction, type or not.
- Three new assertions initially matched their own explanatory comments. Fixed by stripping comments before scanning, the same discipline #45's Housing guards use.

### Verification

| | |
|---|---|
| Frontend tests | 1,795 → **1,844** (+49), all passing |
| Backend tests | **2,494 passed, 2 skipped** — unchanged, as intended |
| Typecheck · lint · build | clean |
| Prerendered pages | 18 → **19** (`/explain` added, with real content) |
| Client JS | 577,246 → 587,832 B (**+10,586**) |
| Client JS gzipped | 166,611 → 169,083 B (**+2,472**) |
| Accessibility (5 surfaces, real Chrome) | one `h1` each, zero skipped heading levels, zero unresolved region labels, zero horizontal overflow, zero unlabelled links |

**Mobile remains unverified at a real viewport.** The browser tooling reports a successful resize while media queries continue to match desktop — the same limitation #45A hit. Structural assertions were added instead (no fixed pixel widths, mobile-first grid), and a genuine 390px pass across all eight surfaces is still outstanding.

**Analyst populated-state testing is incomplete.** `available: false, reason: NOT_CONFIGURED` in this environment. The honest unavailable state was verified rendering — *"MacroChipz Analyst is unavailable."*, with no input control — and nothing about the Analyst was widened.
