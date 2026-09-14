# Overview Attention Model — V1 (FROZEN CONTRACT)

**Increment #22A, corrected.** Audit + contract freeze only. No production code changed this increment. Baseline: HEAD `53fb64d` ("Add Economic Intelligence product experience audit (#21)"), clean working tree. Frontend: 673/673 passed (one transient failure on the very first run of the session did not reproduce across seven subsequent full runs — treated as environment flake, not a regression; see §0). Backend: 1,173/1,173 passed, 0 skipped, against the project's established local isolated-Postgres test mechanism.

This document is the authoritative contract for Increment #22B. #22B implements it by exact transcription. If #22B's own prompt conflicts with this document on a product decision, this document wins; a genuine factual correction to this document requires a STOP and re-freeze, not a silent reinterpretation.

**Correction record:** the salience model (§4–§13, §19–§20) was approved as originally frozen and is unchanged. §14's selection rule and §17's `ReleaseRow` navigation rule originally conflated *release category* (a broad, editorial display tag) with *canonical monitor relation* (whether a release's mapped series actually feed a monitor's calculation) — concretely, JOLTS was incorrectly treated as Labor-monitor evidence. §3A freezes the corrected distinction; §14 and §17 are corrected to match, verified directly against the backend's own seeded `ReleaseSeriesMapping` migrations rather than trusted from any prompt.

---

## §0. Baseline note: the transient frontend failure

The first `npx vitest run` of this session reported 671 passed / 2 failed. Two immediate re-runs, unmodified working tree, both reported 673/673 passed with no failures. No file was edited between runs. This is recorded for transparency (report outcomes faithfully) but is not treated as a defect of the current implementation — nothing in this increment depends on it, and it is not reproducible. If #22B's own verification pass reproduces a real failure, that is a new finding, not something this document waives.

**Exact failing test names: not recoverable.** The initial failing run's output was summarized (pass/fail counts only) rather than captured in full at the time, and the failure did not reproduce across seven subsequent full-suite runs performed while investigating this correction (two during the original freeze, five more during this correction pass). No test name, file, or error message from that one run exists in this session's record to report, and none will be invented. **#22B flake watchlist:** if any frontend test fails on #22B's own required verification runs, capture the full `vitest run` output (not just the summary line) before concluding it's a repeat of this flake — this one specific incident cannot be matched against a future failure without a name, so treat any recurrence as a new, unidentified finding requiring its own investigation, not an assumed match to this entry.

---

## §1. #21 findings this increment addresses (and does not broaden beyond)

Extracted directly from `docs/product/product-experience-audit-v1.md`:

- **§2/§4/§6 (the core defect):** Overview's `WhatChangedPreview`/`LaborWhatChangedPreview` truncate each domain's flat, **canonically** (structurally, not importance) ordered `changes[]` to 3 items. Canonical order is fixed by component/section membership (`app/domain/inflation_what_changed.py:436-441`: primary momentum → confirmation → target → headline PCE → headline CPI), not by importance. A section with only routine `METRIC_CHANGED` events can occupy all 3 visible slots ahead of a real `STATE_CHANGED` event in a later section. This is the increment's primary target.
- **§11:** "Latest Data Detected" is too pipeline-oriented a name; the DATA-changed vs. INTELLIGENCE-changed structural split is correct and must be preserved, not collapsed.
- **§17/§18 (implicit in §2/§11):** Latest Data Detected selects exactly **one** occurrence system-wide (`lib/selectLatestDataDetected.ts`), so one domain's fresh evidence can silently hide another's.
- **§19/§24 (dead ends):** release rows (`components/releases/ReleaseRow.tsx`) render no link anywhere; Latest-Data-Detected items render no link anywhere — despite the data needed to build both links already existing in the response payloads.
- **§23 (significance gap):** no importance concept exists anywhere; the correct fix is a deterministic, non-scored *filter* over already-canonical fields — exactly the shape `/labor`'s own `WhatChangedSection.tsx` already implements and ships today, just not yet extended to Overview.

**Explicitly out of scope, confirmed by re-reading §7/§12 of the #21 audit:** `/inflation`'s and `/labor`'s own full pages are not broken — Investigate (4/5) and Explainability (4/5) were the audit's strongest scores. This increment does not redesign either full page. Its target is Overview's compact previews, Overview's Latest Data Detected, and the two dead-end links — nothing else.

---

## §2. Current implementation, inspected fresh this turn

**`frontend/src/pages/Overview.tsx`** (current, unmodified): seven independent `useApiResource` calls (`getInflationMonitor`, `getInflationWhatChanged`, `getLaborMonitor`, `getLaborWhatChanged`, `fetchReleaseProcessingStatus`, `fetchUpcomingReleases`, `fetchRecentReleases`). Four `<h2>` sections: Current State, What Changed, Latest Data Detected, Releases — exact heading text asserted by `Overview.test.tsx:385`: `["Current State", "What Changed", "Latest Data Detected", "Releases"]`. This test **must be updated** in #22B if the Latest Data Detected heading text changes (§9 decides it does).

**`components/overview/WhatChangedPreview.tsx`** (Inflation): `events.slice(0, MAX_EVENTS)` where `MAX_EVENTS = 3`, over `InflationWhatChangedResult.changes` verbatim — no tiering, no reordering, first 3 in canonical order.

**`components/overview/LaborWhatChangedPreview.tsx`** (Labor): identical shape — `events.slice(0, MAX_EVENTS)` over `LaborWhatChangedResult.changes`, no tiering.

**`components/overview/LatestDataDetected.tsx`**: renders exactly one item, chosen by `selectLatestDataDetectedItem(items)` over the *entire* unfiltered `items` array (all domains pooled) — no per-domain concept exists.

**`components/overview/CurrentStateSection.tsx`**: the established peer-card precedent this contract reuses — one shared `<h2>`, two independently-gated `<div>` sub-cards (`InflationCurrentStateCard`, `LaborCurrentStateCard`), neither owning the heading, each rendering only when its own resource has succeeded.

**`components/releases/ReleaseRow.tsx`**: renders category tag, name, provider, schedule-status badge — **no `<a>`/`<Link>` anywhere in the component**, confirmed by direct inspection. A hard dead end.

**`lib/selectLatestDataDetected.ts`**: `STATUS_PRIORITY = ["CHANGES_DETECTED", "PARTIAL_CHECK", "CHECK_FAILED", "NO_CHANGE", "NOT_CHECKED"]`, a stable single-winner selection preserving backend order within a tier. Already correct; §9 reuses it unchanged, called once per domain bucket instead of once globally.

**`lib/releasePresentation.ts`**: the already-shipped, already-user-facing (`/releases`'s own category tags) `RELEASE_PRESENTATION` map: `"10"→"Inflation"`, `"54"→"Inflation / Consumer"`, `"50"→"Labor"`, `"192"→"Labor"` (JOLTS), `"53"→"Growth"` (GDP), `"9"→"Consumer"` (Advance Retail Sales). This is an honest *display* grouping, already shown to users on `/releases` — but, per §3A's correction, it is **not** a safe basis for a monitor-relation claim (its `"192"→"Labor"` entry is exactly the case that turned out to be wrong for that purpose: JOLTS has no canonical series mapping at all). §14/§17 use a separate, narrower, migration-verified constant instead — see §3A.

**`pages/Inflation.tsx`**: confirmed, by direct inspection, to have **no** Latest-Data-Detected / processing-status section of any kind — that surface exists only on `/labor` (built in #20E.2). This asymmetry is real and is disclosed explicitly in §14 rather than silently assumed away.

---

## §3. Canonical event contracts, inspected fresh this turn

### Inflation (`app/models/inflation_what_changed.py`, mirrored in `frontend/src/api/inflation.types.ts`)

`ChangeComponent = "PRIMARY_MOMENTUM" | "CONFIRMATION" | "TARGET" | "HEADLINE_PCE" | "HEADLINE_CPI"`
`ChangeEventType = "METRIC_CHANGED" | "STATE_CHANGED" | "AVAILABILITY_LOST" | "AVAILABILITY_RESTORED" | "CONFIRMATION_CHANGED"`

`ChangeEvent { component, event_type, field, previous_value, current_value, delta, previous_period, current_period, methodology_id, data_basis }`

Verified structural facts (from `app/domain/inflation_what_changed.py`):
- `PRIMARY_MOMENTUM`/`HEADLINE_PCE`/`HEADLINE_CPI` sections can each independently emit `STATE_CHANGED` (field `"state"`) or `AVAILABILITY_LOST`/`RESTORED` (field `"state"`), plus `METRIC_CHANGED` on `r_1m_annualized`/`r_3m_annualized`/`r_6m_annualized`/`r_12m`.
- `CONFIRMATION` never emits `STATE_CHANGED` — only `CONFIRMATION_CHANGED` (field `"relationship"`) or `AVAILABILITY_LOST`/`RESTORED`.
- `TARGET` never emits `STATE_CHANGED` or `CONFIRMATION_CHANGED` — only `METRIC_CHANGED`/`AVAILABILITY_LOST`/`RESTORED` on `headline_pce_yoy`/`target_gap_pp`.
- Availability events are **not** limited to state-shaped fields — `_metric_events` (line 51) emits them for any numeric field whose null-ness flips, confirmed for Target's own metrics.
- Top-level `changes[]` order is a fixed concatenation: `[*primary_momentum, *confirmation, *target, *headline_pce, *headline_cpi]` — component identity, not importance.

### Labor (`app/models/labor_what_changed.py`, mirrored in `frontend/src/api/labor.types.ts`)

`LaborChangeComponent = "LABOR" | "EMPLOYMENT" | "UNEMPLOYMENT"`
`LaborChangeEventType = "STATE_CHANGED" | "AVAILABILITY_LOST" | "AVAILABILITY_RESTORED" | "METRIC_CHANGED"`

`LaborChangeEvent { component, event_type, field, previous_value, current_value, delta, previous_period, current_period, methodology_id, data_basis }`

Verified structural facts (from `app/domain/labor_what_changed.py`):
- `field` for a state-shaped comparison is one of `"state"` (LABOR's own, and each of EMPLOYMENT's/UNEMPLOYMENT's own), `"condition"`, `"momentum"` — **all reuse `event_type: "STATE_CHANGED"` (or `AVAILABILITY_*`)**; there is no separate `CONDITION_CHANGED`/`MOMENTUM_CHANGED` event type. Distinguishing "a component's own state changed" from "condition/momentum changed" requires checking `field`, not just `event_type` — confirmed at `app/domain/labor_what_changed.py:276` (`state_changed = any(e.event_type == "STATE_CHANGED" and e.field == "state" ...)`).
- This is exactly what `/labor`'s own shipped `WhatChangedSection.tsx` already does (transcribed verbatim below) — no new logic needs to be invented for Labor, only reused.

### Release processing (`app/models/release_processing_read.py`, mirrored in `frontend/src/api/processingStatus.types.ts`)

`DetectedObservationChange { series_id, series_title, units, change_type: "NEW"|"REVISED", observation_date, previous_value, new_value, detected_at }`

`DetectedAnalysisChange { component: string, event_type: ChangeEventType, field, previous_value, current_value, delta, evaluation_period, methodology_id, data_basis, recorded_at }` — `component` is plain `string` (generic transport boundary, #20D.2/#20E.2), `event_type` reuses Inflation's 5-value union (a strict superset of Labor's 4).

`ReleaseProcessingStatusItem { occurrence_id, release: { release_id, name, provider, provider_release_id }, scheduled_date, latest_check: { status, checked_at }, detected_observation_changes[], detected_analysis_changes[] }`

**Confirmed absent:** no `domain` field, no `monitor` field, anywhere on this contract. `release.provider_release_id` is the only stable identity available — domain grouping, where used at all, must go through an honest, verified basis (§3A corrects an earlier draft of this document that conflated two different such bases).

---

## §3A. CORRECTION — release category vs. canonical monitor relation

**This section corrects §14 and §17 as originally frozen.** The original freeze used `releasePresentation.ts`'s `releaseCategory()` — a broad, editorial, user-facing display grouping — as if it were equivalent to "this release's data feeds a canonical EI monitor." It is not, and conflating the two produced one factually wrong navigation/attribution rule (JOLTS). Corrected by direct inspection of the actual seeded release→series mappings, not by trusting the display category string.

**Two distinct concepts, not to be conflated:**

- **RELEASE CATEGORY** (`lib/releasePresentation.ts`'s `RELEASE_PRESENTATION` map, `category` field) — a broad, frontend-only, editorial economic-area tag shown on `/releases` for human scanning. It is honest as a *display* label but was never verified against, and is not guaranteed to track, which series a release actually feeds into a canonical monitor.
- **CANONICAL MONITOR RELATION** — whether a release's own mapped series (`ReleaseSeriesMapping`, seeded by the backend's own data migrations) are actually consumed by `inflation_v1.0`'s or `labor_v1.0`'s canonical calculation. This is verifiable directly from the two seeded migrations, inspected fresh for this correction:

  - `alembic/versions/cd476d227f99_seed_cpi_and_personal_income_and_.py`: `CURATED_MAPPINGS = {"10": ["CPIAUCSL", "CPILFESL"], "54": ["PCEPI", "PCEPILFE"]}` — CPI ("10") and Personal Income and Outlays ("54") map to `CPIAUCSL`/`CPILFESL`/`PCEPI`/`PCEPILFE`, all four of which are confirmed Inflation-canonical inputs (`app/models/inflation.py`; PCEPI/PCEPILFE via `underlying_momentum`/headline PCE, CPIAUCSL/CPILFESL via `headline_context`/confirmation).
  - `alembic/versions/09f4c0959e9f_seed_employment_situation_release_.py`: `CURATED_MAPPINGS = {"50": ["PAYEMS", "UNRATE"]}` — Employment Situation ("50") maps to `PAYEMS`/`UNRATE`, confirmed Labor-canonical (`app/domain/labor_release_processing.py`'s `LABOR_SERIES_IDS`).
  - **JOLTS ("192"), GDP ("53"), and Advance Retail Sales ("9") appear in neither seeded migration.** Grepped directly, confirmed absent — zero `ReleaseSeriesMapping` rows exist for any of the three. JOLTS is deferred from Labor V1 (per the frozen `labor_v1.0` methodology's own explicit scope) and, whatever its display category says, **currently feeds no canonical monitor at all** — it cannot detect a change, let alone attribute one to Labor.

**Frozen rule:** navigation and attribution decisions in this contract (§14, §17) must use CANONICAL MONITOR RELATION, never RELEASE CATEGORY, whenever the claim being made is "this release affects monitor X." RELEASE CATEGORY remains exactly what it always was — a display tag on `/releases` — and this correction does not touch that existing, unrelated use.

**Implementation note (no backend change):** the frontend has no endpoint exposing `ReleaseSeriesMapping` (confirmed absent, `docs/product/product-experience-audit-v1.md` §1's inventory). Canonical monitor relation must therefore be encoded as a small, explicit, frontend-curated constant set — `{"10", "54"} → Inflation`, `{"50"} → Labor` — mirroring the exact pattern this codebase already uses for the identical problem: `components/labor/RelevantRelease.tsx`'s own `EMPLOYMENT_SITUATION_PROVIDER_RELEASE_ID = "50"` constant, doc-commented as keying off the same ID the backend's own migration uses. This is not new backend information and is not an unsupported inference — it is a frontend constant restating a fact already true and verified directly in the backend's own committed migration files, exactly as precedent already does for Employment Situation alone. §17's implementation scope is unchanged by this correction (still frontend-only, still zero backend change); only which lookup table drives monitor-relation decisions changes.

---

## §4. Definition of salience (frozen)

> **Salience is a deterministic presentation priority over already-canonical change events, computed only from each event's `component` and `field` membership in a fixed, per-domain, auditable tier table — never from a magnitude, a probability, a score, or any inference not already present in the backend's own response.**

The frontend orders, groups, collapses, and progressively discloses. It never suppresses an event from being reachable, never changes an event's `event_type`/`field`/values, never infers that one event *caused* another, and never asserts materiality beyond "this is the kind of event this tier is defined to contain."

### Explicit non-goals (rejected outright, per instruction)

- No 0–100 importance score, no High/Medium/Low economic-impact label, no severity number, no confidence number.
- No market-impact prediction, no bullish/bearish framing, no directional "good/bad" language beyond what the existing tone system (`Tone`: neutral/caution/unavailable) already does.
- No AI ranking of any kind.
- No magnitude-based ranking (a large `delta` does not outrank a small one within Tier 4 — see §11; sorting by magnitude would itself be a quiet reintroduction of a significance score by another name).
- If the product later needs a genuine notion of "material change" (e.g., a magnitude-aware significance concept), that is an explicit **future, separate methodology problem**, requiring its own audit/freeze increment — not something this document defines or that #22B may quietly build toward.

---

## §5. Shared tier vocabulary, domain-specific mappings

**Finding (per instruction to determine, not assume, a shared model):** a shared **tier vocabulary** — four named tiers — is valid and adopted. The concrete event→tier **mapping** is not identical between domains, because the two domains' contracts are not structurally identical (Inflation has a Confirmation relationship and two independent headline-series states with no analog in Labor; Labor has an explicit condition/momentum split with no analog in Inflation). Per-domain mappings are frozen separately below, both expressed over the same four tier names so the two domains remain comparable in kind without being forced into one literal rule.

| Tier | Name | Contains |
|---|---|---|
| 1 | **Primary domain state** | The top-level domain's own state/availability transition — the single most decision-relevant fact for that domain |
| 2 | **Structural change** | Other components' own real, independently-classified state changes, plus **any** availability transition not already in Tier 1 |
| 3 | **Secondary / corroborating signal** | Signals that explain or corroborate the primary state without being a classification of their own top-level standing |
| 4 | **Metric update** | Numeric-only changes, no classification attached |

---

## §6. Inflation hierarchy (frozen)

Audited independently, not derived from Labor's shape.

| Tier | Rule (over `ChangeEvent`) | Rationale |
|---|---|---|
| 1 | `component === "PRIMARY_MOMENTUM" && field === "state"` (any `event_type` among `STATE_CHANGED`/`AVAILABILITY_LOST`/`AVAILABILITY_RESTORED`) | Core PCE's own state is `InflationMonitorResult.underlying_momentum.state` — the exact value `InflationCurrentStateCard` shows as "Inflation" on Overview today. This is Inflation's literal top-level signal. |
| 2 | `event_type in {STATE_CHANGED, AVAILABILITY_LOST, AVAILABILITY_RESTORED}` on `component in {HEADLINE_PCE, HEADLINE_CPI}` **OR** any `AVAILABILITY_LOST`/`AVAILABILITY_RESTORED` event on any component not already in Tier 1 | Headline PCE/CPI carry their own real, independently-computed `SeriesMomentumResult.state` — a genuine classification, not raw metric noise. Any availability transition (per §10) is operationally important regardless of which section it's on. |
| 3 | `event_type === "CONFIRMATION_CHANGED"` (component `CONFIRMATION`, field `"relationship"`) | Confirmation is explicitly, by the product's own existing curated copy (`content/explanations/inflation.ts`'s `CONFIRMATION.whyItMatters`: "Confirmation never changes Core PCE's own state — it's a separate, secondary signal shown alongside it"), a corroborating fact, not a primary classification. This placement is evidence-grounded, not copied from the prompt's own sketch. |
| 4 | Every remaining `METRIC_CHANGED` event (any component, including the context-only `r_1m_annualized`) | Numeric-only, no classification. |

**Target** never contributes a Tier 1–3 event (it has no state concept, confirmed §3) — it only ever contributes Tier 4 (`METRIC_CHANGED`) or Tier 2 (`AVAILABILITY_*`) events.

---

## §7. Labor hierarchy (frozen — reuses shipped logic, does not invent a new one)

`/labor`'s own `WhatChangedSection.tsx` already implements this exact tiering today, verified by direct inspection (transcribed filters, verbatim):

```
laborTier            = events.filter(e => e.component === "LABOR")
stateTier             = events.filter(e => e.component !== "LABOR" && e.field === "state" && e.event_type !== "METRIC_CHANGED")
conditionMomentumTier = events.filter(e => e.field === "condition" || e.field === "momentum")
metricTier            = events.filter(e => e.event_type === "METRIC_CHANGED")
```

Mapped onto the shared vocabulary:

| Tier | Shipped filter | 
|---|---|
| 1 — Primary domain state | `laborTier` (component `LABOR`, any event_type — state or availability) |
| 2 — Structural change | `stateTier` (EMPLOYMENT's/UNEMPLOYMENT's own `field === "state"`, `STATE_CHANGED` or `AVAILABILITY_*`) |
| 3 — Secondary / corroborating | `conditionMomentumTier` (`field === "condition"` or `"momentum"`, EMPLOYMENT only) |
| 4 — Metric update | `metricTier` (`event_type === "METRIC_CHANGED"`, any component) |

**#22B does not reimplement this** for `/labor` itself — it already exists and is already tested. #22B's job is to reuse the identical filter shapes (as a shared helper, or parallel per-domain helpers per §20) to drive **Overview's** compact preview, which today has no tiering at all.

---

## §8. Availability events (frozen)

Per §10's instruction, audited explicitly rather than assumed:

- **Availability restoration/loss on the primary domain's own top-level state outranks everything** — it is Tier 1 by both domains' existing rules (Labor: `laborTier` includes it unconditionally; Inflation: Tier 1's rule includes `AVAILABILITY_LOST`/`RESTORED` on `PRIMARY_MOMENTUM`/`field === "state"`).
- **Availability restoration/loss anywhere else outranks a routine metric change but does not outrank a domain-state change** — frozen as Tier 2, confirmed correct because it is *always* a real fact about whether the data underlying a classification can currently be trusted, which is strictly more decision-relevant than "a number moved."
- **No positive/negative economic language is used for availability**, matching the existing, correct `/labor` precedent verbatim: `"{component} {field} analysis became unavailable/available"` — never "improved"/"worsened"/"lost ground." This sentence shape is reused for Inflation's own availability events too (a new but trivial, non-semantic-inventing extension — Inflation currently has no equivalent sentence at all on Overview since no tiering exists there yet).

---

## §9. Metric-only months (frozen)

When a domain's Tier 1–3 are all empty but Tier 4 is not:

- Overview shows: **"No structural change"** (exact copy, see §10) as the domain's headline line, followed by a collapsed, count-labeled disclosure — reusing `/labor`'s exact existing pattern verbatim: `Metric updates (N)`.
- All Tier 4 events remain individually inspectable inside that disclosure — no cap, no further truncation (per the explicit "all metric updates must remain inspectable" instruction).
- This applies identically to both domains — Inflation gets the same `Metric updates (N)` disclosure shape Labor already has, extended to Overview specifically (not to `/inflation`'s own full page, which is out of scope, §1).

---

## §10. Quiet-state / zero-event / structural-no-change copy (frozen, exact wording)

Four genuinely distinct states, each requiring its own copy — never conflated:

| State | Condition | Exact copy |
|---|---|---|
| **Comparison unavailable** | `comparison_available === false` (or, for Inflation, a section's own `comparison_available === false`) | *"Previous-period comparison unavailable."* (already existing, unchanged copy — reused verbatim, both domains) |
| **Zero events at all** | `changes.length === 0` and comparison is available | *"No canonical {Inflation/Labor} changes were reported for this comparison."* (already existing Overview copy — unchanged; this is the literal "nothing happened" case) |
| **Structural no-change, metrics did move** | Tier 1–3 empty, Tier 4 non-empty | *"No structural change."* followed by the `Metric updates (N)` disclosure (§9). **Never** "Nothing changed" (false — metrics did change) and **never** "Stable"/any canonical-state word unless the backend's own current state field literally equals that value. |
| **Insufficient data** | The domain's own current state is `INSUFFICIENT_DATA` | Unchanged — this is a data-availability fact handled by the existing `unavailable` tone and existing copy, never folded into "no structural change" (a genuinely different condition: one means "nothing worth reporting moved," the other means "we cannot currently classify this domain at all"). |

---

## §11. Multiple high-salience events in one comparison (frozen)

Per §12's instruction, nothing is arbitrarily hidden:

- **All Tier 1 and Tier 2 events are always shown**, uncapped — both domains' contracts bound this to a small number by construction (Inflation: at most 1 Tier-1 + up to 4 Tier-2 events across Headline PCE/CPI/Target/Confirmation-availability; Labor: at most 1 Tier-1 + up to 2 Tier-2 events across Employment/Unemployment state). No numeric truncation is applied to these tiers — truncating a structural event to make room would directly reintroduce the exact defect this increment exists to fix.
- **Tier 3 events are always shown**, similarly uncapped (bounded to at most 2 for Labor's condition+momentum, at most 1 for Inflation's confirmation).
- **Tier 4 is always collapsed** behind the count-labeled disclosure (§9), regardless of how many Tier 1–3 events exist alongside it.
- **No duplicate semantic statements:** each event renders exactly once, in exactly the tier its `(component, field, event_type)` triple maps to — the existing `/labor` filters already guarantee this by construction (each filter's predicate is mutually exclusive with the others, verified by re-reading the four filter expressions in §7); the Inflation mapping in §6 is written to preserve the same mutual-exclusivity property.
- The old fixed `MAX_EVENTS = 3` truncation constant is **retired** for Tiers 1–3; it no longer governs which structural events are visible. It has no equivalent role to play in Tier 4, which is already uncapped-but-collapsed.

---

## §12. Cross-domain ordering (frozen)

**Decision: domain separation is preserved. No merged chronological stream is built.**

Rationale, confirmed by contract inspection: neither `ChangeEvent` nor `LaborChangeEvent` carries a true event timestamp usable for a fair cross-domain interleave — `previous_period`/`current_period` are comparison-period bounds, not detection timestamps, and the two domains' comparison periods are not guaranteed to align (Inflation's primary momentum period and Labor's evaluation period are independently determined). Building one fake combined stream would require either inventing an ordering key the backend doesn't provide or silently picking one domain's period semantics as authoritative for both — both are exactly the kind of "created new economic truth" this increment must not do. The existing per-domain sub-card structure (`CurrentStateSection`'s precedent) is correct and is reused unchanged in shape.

---

## §13. Overview "What Changed" contract (frozen)

```
WHAT CHANGED                                    (one shared <h2>, unchanged)

  Inflation                                      (plain <p> sub-label, unchanged pattern)
    [Tier 1 event, if any]                       e.g. "Inflation state: Mixed → Cooling"
    [Tier 2 events, if any]                       e.g. "Headline PCE state: ... "
    [Tier 3 event, if any]                        e.g. "Confirmation: Confirms → Diverges"
    (if Tiers 1-3 all empty, Tier 4 non-empty:)   "No structural change."
    (if zero events at all:)                      "No canonical Inflation changes were reported..."
    Metric updates (N)                            [collapsed disclosure, Tier 4, always present when N > 0]
    View Inflation →                              (CTA, §17)

  Labor                                           (identical shape, independently gated)
    ...
    View Labor →
```

This is the **minimal, evidence-grounded version** of the sketch in the #22A prompt, not a verbatim copy of it: the prompt's own sketch is confirmed structurally correct for both domains once mapped through §6/§7's explicit per-domain tables, with the "Secondary structural changes" line split honestly into this contract's own Tier 2 (structural) and Tier 3 (secondary/corroborating) rather than merged, because merging them would erase the real distinction §6/§7 establish (a Headline-PCE state change is a different *kind* of fact from a Confirmation-relationship change, even though the original sketch's plain-English label doesn't distinguish them).

Each domain sub-block's internal ordering is **Tier 1, then Tier 2, then Tier 3, then the Tier 4 disclosure** — always in that order, never re-sorted within a tier (within-tier order is the backend's own already-deterministic order, preserved exactly, mirroring `/labor`'s existing precedent of never reordering within a filtered bucket).

---

## §14. Latest Data Detected — naming, restructuring, selection (frozen)

**Decision: RENAME + RESTRUCTURE.** (Not KEEP-as-is, not DE-EMPHASIZE — the section's prominence and its DATA/INTELLIGENCE structural split are both correct and stay exactly where they are; only its name and its single-item-system-wide selection change.)

**New name: "Recent Data Updates."** Chosen over the other candidates in the #21 audit and this prompt because it is the smallest possible diff that removes the pipeline-step word ("Detected") while matching the *already-established* naming convention this exact page already uses one section below it ("Upcoming Releases"/"Recent Releases" — `pages/Releases.tsx`). "New Data & Revisions" was considered and rejected as redundant with the "Source data changes" sub-heading already rendered one level down inside the section. "Recently Updated" was rejected as too vague (doesn't say *what* updated). "Economic Data Updates" was rejected as redundant ("Economic" is true of the entire product, not a distinguishing word here).

**Restructuring — selection model, CORRECTED per §3A:** replace the single system-wide `selectLatestDataDetectedItem(items)` call with **the same function, called twice**, once per domain, pre-filtered by **canonical monitor relation, not release category**:

- `selectLatestDataDetectedItem(items.filter(i => CANONICAL_MONITOR_RELEASE_IDS.INFLATION.has(i.release.provider_release_id)))`
- `selectLatestDataDetectedItem(items.filter(i => CANONICAL_MONITOR_RELEASE_IDS.LABOR.has(i.release.provider_release_id)))`

where `CANONICAL_MONITOR_RELEASE_IDS = { INFLATION: new Set(["10", "54"]), LABOR: new Set(["50"]) }` — the frontend-curated constant frozen in §3A, mirroring the backend's own actual seeded `ReleaseSeriesMapping` migrations, **not** `releaseCategory()`. Using `releaseCategory()` here (the original, now-corrected draft of this section) would have attributed JOLTS ("192", category `"Labor"`) evidence to the Labor monitor despite JOLTS feeding zero canonical series — a real, demonstrated-by-migration-inspection error, not a hypothetical one.

Each result renders independently, in its own gated slot, mirroring `CurrentStateSection`'s already-established peer-card pattern exactly (one domain's absence or failure never hides the other's presence). Items whose release is not in either `CANONICAL_MONITOR_RELEASE_IDS` set (JOLTS, GDP, Advance Retail Sales, or any future uncurated release) are **not surfaced in this section** in #22B — an explicit, frozen scope boundary, not an oversight: today's real, migration-verified canonical inputs are exactly `{CPI, Personal Income and Outlays} → Inflation` and `{Employment Situation} → Labor`; nothing else currently feeds either monitor, so this boundary matches actual capability rather than the broader, unverified category grouping. `selectLatestDataDetectedItem` itself is unmodified — this is a pure call-site change (filter, then call twice), requiring **zero backend change** and zero change to the selection function's own logic or tests. **Can current contracts support this honestly?** Yes — confirmed in §3A: the constant restates an already-true, already-committed backend fact; no new backend field, endpoint, or inference is required.

**Naming disclosure required:** any test asserting the literal string "Latest Data Detected" (`Overview.test.tsx:385`'s heading-sequence array, and any component test asserting that heading text) must be updated in #22B to "Recent Data Updates" — flagged explicitly here so #22B's regression pass expects and makes this change deliberately, not as a surprise.

---

## §15. Data-changed vs. intelligence-changed presentation (frozen — preserved, not altered)

The existing structural split (`detected_observation_changes` / `detected_analysis_changes` as sibling, never-nested arrays, per ADR-023) is correct and is **preserved exactly as built**. §9's earlier analysis (`app/services/release_processing.py`'s `_determine_status`) already guarantees: a `NO_CHANGE`/`CHECK_FAILED` latest run contributes no new rows to either list; a `CHANGES_DETECTED` run can populate observation changes alone (A: data changed, no tracked metric/state crossed a threshold), both lists (B: data changed and a tracked metric/state moved), or in principle analysis changes without observation changes only if a prior run's persisted data was reclassified by a later methodology reference — not currently a real path, so not claimed. The existing UI copy already states this correctly ("Tracked analysis change... computed the same way as the live monitor... the two lists on this page are independent facts, not a one-to-one cause and effect" — `content/explanations/processingStatus.ts`'s `TRACKED_ANALYSIS_CHANGE`). **No copy or structure change required here** — this was already correctly built; §14 only changes selection cardinality (one → up to two) and the section's own name, never this internal distinction.

---

## §16. Processing-status values on Overview (frozen — unchanged)

All five `ProcessingStatus` values (`NOT_CHECKED`, `NO_CHANGE`, `CHANGES_DETECTED`, `PARTIAL_CHECK`, `CHECK_FAILED`) remain on Overview, exactly as today — none removed, none reinterpreted as an economic condition. The existing `STATUS_PRIORITY` ordering (`CHANGES_DETECTED > PARTIAL_CHECK > CHECK_FAILED > NO_CHANGE > NOT_CHECKED`) is reused unchanged, now applied within each domain's own filtered bucket (§14) rather than globally. Primary presentation remains the selected status's own humanized label (`processingStatusLabel`); secondary presentation remains the existing evidence lists behind their existing counts/disclosures. No change to `content/explanations/processingStatus.ts` is required.

---

## §17. Navigation / CTA rules (frozen)

| Surface | Target | Rule |
|---|---|---|
| What Changed, any tier, any event, Inflation domain block | `/inflation` | Existing CTA, unchanged — "View Inflation →" (renamed from "See full comparison →", §18) |
| What Changed, any tier, any event, Labor domain block | `/labor` | Existing CTA, unchanged — "View Labor →" |
| Recent Data Updates, Inflation slot | `/inflation` | **New.** General navigation only — `/inflation` has **no** scoped detected-changes subsection to deep-link into (confirmed absent, §2); the CTA honestly lands on the general Inflation page, not a specific evidence anchor. This asymmetry with Labor (below) is disclosed, not hidden, and is **explicitly out of scope to fix in #22B** — building an `/inflation`-side equivalent of Labor's scoped Latest Data Detected section would be new frontend feature work beyond what #21 demonstrated as broken. |
| Recent Data Updates, Labor slot | `/labor` | `/labor` already has its own scoped Latest Data Detected section (built #20E.2) — the CTA lands on a page that genuinely contains the matching evidence, not just the domain in general. |
| Release row (`ReleaseRow`) | `/inflation`, `/labor`, or `/releases` | **CORRECTED per §3A** — keyed by **canonical monitor relation** (`CANONICAL_MONITOR_RELEASE_IDS`, §14), never `releaseCategory()`. See the exact per-release table below. Never a hard dead end: a release with no canonical monitor relation still gets an honest next action, `/releases`, rather than no link at all (the original draft's "no domain-page link" was itself an unnecessary dead end, corrected here) — `/releases` is the smallest honest destination given the current route surface, and no release detail page is built in #22B. |
| Detected-change item (`ObservationChangeRow`/`AnalysisChangeRow`, inside Recent Data Updates) | inherits its parent occurrence's own domain-slot CTA | No new per-row link is added inside the section — the section-level "View {Domain} →" CTA (already present per §14's restructuring) is the single, honest next action; a per-row link would either duplicate that CTA or require inventing a deep-link anchor the backend does not support. |

**Exact per-release `ReleaseRow` navigation table (frozen, replaces the original draft):**

| Release | `provider_release_id` | Canonical monitor relation | CTA label | Target |
|---|---|---|---|---|
| Consumer Price Index (CPI) | `"10"` | Inflation (`CPIAUCSL`/`CPILFESL`) | "View Inflation →" | `/inflation` |
| Personal Income and Outlays (PIO) | `"54"` | Inflation (`PCEPI`/`PCEPILFE`) | "View Inflation →" | `/inflation` |
| Employment Situation | `"50"` | Labor (`PAYEMS`/`UNRATE`) | "View Labor →" | `/labor` |
| JOLTS | `"192"` | **None** — deferred from Labor V1, zero seeded series mapping | "View Releases →" | `/releases` |
| GDP | `"53"` | None | "View Releases →" | `/releases` |
| Advance Monthly Retail Sales | `"9"` | None | "View Releases →" | `/releases` |

**Rendering-context note (found during this correction, not previously surfaced):** `ReleaseRow` is used in four places, not two — `ReleaseCalendarSection.tsx` (on `/releases` itself), `RelevantRelease.tsx` (on `/labor`, Employment-Situation-only), `UpcomingReleasesPreview.tsx` (on `/`, the general curated list, where JOLTS/GDP/Retail Sales rows genuinely can appear), and `ReleaseRow.test.tsx`. A `"View Releases →"` CTA is a real, useful next action everywhere except when the row is already rendered on `/releases` itself (via `ReleaseCalendarSection`), where it would be circular. #22B must render that CTA conditionally on the row's own hosting context (omit it inside `ReleaseCalendarSection`, include it inside `UpcomingReleasesPreview`) — this is an implementation-level rendering detail, not a deviation from the frozen navigation rule itself, which is unconditional ("a non-monitor release's next action is `/releases`").

**No deep-link query params are introduced anywhere** — every target above is a plain, existing route.

---

## §18. CTA wording (frozen)

| Old copy | New copy | Why |
|---|---|---|
| "See full comparison →" (Inflation), "See full comparison →" (Labor) | **"View Inflation →" / "View Labor →"** | More specific than "comparison" (which undersells that the destination page also has current state, evidence, and methodology, not just a diff), matches the existing, already-correct wording `InflationCurrentStateCard`/`LaborCurrentStateCard` use ("Open Inflation →"/"Open Labor →") for the *other* Overview section pointing at the same pages — this freeze additionally aligns the two so the same destination is never announced with two different verbs on the same page. **Open** vs. **View**: kept as `Open Inflation →` / `Open Labor →` on Current State (unchanged) and `View Inflation →` / `View Labor →` on What Changed and Recent Data Updates — this asymmetry is deliberate, not sloppy: "Open" reads naturally for a card that's showing a compact state and inviting deeper exploration; "View" reads naturally for a change list inviting a fuller list. Both avoid "Learn more"/"See details" (rejected explicitly, per instruction) in favor of naming the actual destination. |
| "View release calendar →" | unchanged | Already specific and accurate — no change. This remains the section-level CTA at the bottom of Overview's own Releases section; it is a different UI element from the new per-row CTA below and is not replaced by it. |
| *(none — new)* | **"View Releases →"** | New, per-row CTA (§17) for a `ReleaseRow` whose release has no canonical monitor relation (JOLTS, GDP, Advance Retail Sales). Deliberately parallel to "View Inflation →"/"View Labor →" — completes a consistent three-way "View {Destination} →" pattern rather than reusing the longer, section-level "View release calendar →" wording verbatim in a compact per-row context. |

---

## §19. Routine vs. attention-worthy taxonomy (frozen, presentation-only)

Defined strictly in presentation terms, never called "economic importance":

- **Attention-worthy (Tiers 1–3):** any state-shaped classification change (top-level or component-level), any availability transition, any corroborating/secondary signal change (Confirmation, condition, momentum).
- **Routine (Tier 4):** numeric-only changes with no classification attached.

This is the same boundary already implicit in `/labor`'s shipped filters (§7); §6 makes it explicit and auditable for Inflation for the first time. The taxonomy is a **filter name**, not an importance claim — nothing in the UI copy uses the words "important," "significant," or "major" anywhere (§23's explicit prohibition), and no icon/color beyond the existing, already-frozen `Tone` system is introduced.

---

## §20. Shared vs. domain-specific implementation architecture (frozen decision for #22B)

**Decision: a shared tier *type* (the four-name enum in §5) plus explicit, separate per-domain mapping functions — not one generic parameterized salience engine.**

This mirrors the project's own repeated, explicit precedent ("two instances don't justify one abstraction" — already applied to `labor_release_processing.py` as a sibling of `release_processing.py`, to `laborLabels.ts` as a sibling of `inflationLabels.ts`, and to `LaborWhatChangedPreview.tsx` as a sibling of `WhatChangedPreview.tsx`). Two domains, with genuinely different field shapes (§3's confirmed asymmetry — Inflation has no condition/momentum, Labor has no Confirmation-equivalent), do not yet justify a single generic `classifySalience<T>(event)` abstraction; forcing one now would either require a lowest-common-denominator interface that hides the real per-domain differences §6/§7 just established, or a configuration object that is itself a quiet reimplementation of the same per-domain table in a more abstract, harder-to-audit shape. A third domain reusing the identical shape would be the trigger to reconsider, exactly per this project's own standing rule.

`/labor`'s existing four `.filter()` expressions (§7) are reused **verbatim**, factored out of `WhatChangedSection.tsx` into a small `lib/laborSalience.ts` (or equivalent) only if needed to share them between `/labor`'s own page and Overview's new preview — a refactor-for-reuse, not a rewrite. Inflation gets an analogous new `lib/inflationSalience.ts` implementing §6's table for the first time (today, no Inflation salience/tiering code exists anywhere — `/inflation`'s own full page uses fixed section order, not tiering, and is out of scope, §1).

**Canonical monitor relation (§3A) is its own, separate, small constant** — not part of either salience module, since it answers a different question ("which monitor, if any, does this *release* feed") from what §6/§7's tiering answers ("how should this *event*, already known to belong to a domain, be prioritized"). It belongs beside `lib/releasePresentation.ts` (same file, or an adjacent sibling module), explicitly named to avoid any reader conflating it with `releaseCategory()` again — e.g. `CANONICAL_MONITOR_RELEASE_IDS`, not `releaseCategory2` or a same-named overload.

---

## §21. Backend-change requirement (frozen: ZERO)

Every decision above is implementable using fields and endpoints that already exist:
- Tiering (§6/§7) uses only `component`/`field`/`event_type`, already present on every event.
- Per-domain Recent Data Updates selection (§14) uses only `release.provider_release_id`, already present, matched against the already-existing, already-frontend-owned `releasePresentation.ts` map — no backend change, no new query parameter, no new endpoint.
- Release-row navigation (§17) uses the same already-existing map.
- No new field, no new endpoint, no new query parameter, and no schema/migration is required anywhere in this contract. **The STOP condition in the #22A prompt (current APIs cannot support the contract honestly) is not triggered.**

---

## §22. #22B implementation scope (frozen boundary)

**In scope:** `components/overview/WhatChangedPreview.tsx`, `LaborWhatChangedPreview.tsx`, `LatestDataDetected.tsx` (Overview's own, not Labor's page-scoped one), `components/releases/ReleaseRow.tsx` (add the frozen conditional link, context-aware per §17's rendering-context note), `components/overview/UpcomingReleasesPreview.tsx` (the one context where the new per-row CTA actually renders), `pages/Overview.tsx` (heading rename, CTA wording), two new small salience-mapping modules plus the new `CANONICAL_MONITOR_RELEASE_IDS` constant (§20, §3A), `Overview.test.tsx`'s heading-sequence assertion (must be updated for the rename), plus new/extended tests per §23.

**Out of scope (explicitly, do not implement in #22B):** any change to `/inflation`'s or `/labor`'s own full pages' What Changed sections (both already correct, §1); any backend file; any new API; any Growth/third domain; any chart; any AI; any notification; any account/save/watchlist; any aggregate score or cross-domain synthesis; a release detail page; an `/inflation`-side scoped Latest-Data-Detected section (the asymmetry in §17 is disclosed, not fixed, this increment).

---

## §23. #22B test matrix (frozen)

**INFLATION SALIENCE**
- Tier 1 (`PRIMARY_MOMENTUM`/`state`) outranks a Tier 4 metric event in ordering/grouping.
- Tier 2 events (`HEADLINE_PCE`/`HEADLINE_CPI` state changes; any-component availability) render as structural, not folded into Tier 4.
- Tier 3 (`CONFIRMATION_CHANGED`) renders separately from Tier 2.
- `AVAILABILITY_LOST`/`RESTORED` on `TARGET`'s own metric field is Tier 2, not Tier 4.
- Metric-only month (`Tiers 1-3` empty, Tier 4 non-empty) renders "No structural change." plus `Metric updates (N)`.
- Zero events renders the existing "No canonical Inflation changes..." copy, never "No structural change."
- Multiple simultaneous Tier 1–3 events (e.g., primary state change **and** a headline state change **and** a confirmation change in one comparison) all render, none hidden, none duplicated.
- Every event, in every tier, remains individually reachable (byte-identical values to the raw `ChangeEvent`, no lossy summarization).

**LABOR SALIENCE**
- Tier 1 (`LABOR` component) outranks a Tier 4 metric event.
- Tier 2 (`EMPLOYMENT`/`UNEMPLOYMENT` `field === "state"`) ordering, including a simultaneous Employment-state-change + Unemployment-state-change case.
- Tier 3 (`condition`/`momentum`) ordering, reported independently, never suppressed by a co-occurring Tier 1/2 event on the same underlying evidence.
- `AVAILABILITY_LOST`/`RESTORED` on `EMPLOYMENT`/`UNEMPLOYMENT` is Tier 2; on `LABOR` is Tier 1.
- Metric-only month renders "No structural change." plus `Metric updates (N)`.
- Zero events renders the existing "No canonical Labor changes..." copy.
- Multiple simultaneous structural events (the prompt's own worked example: Labor COOLING→MIXED, Employment EXPANDING→COOLING, Unemployment STABLE→DETERIORATING) all render, none hidden.
- Every event remains individually reachable.

**OVERVIEW**
- Inflation and Labor remain two separate, independently-gated blocks under one shared heading — no merged chronology (verify no code path interleaves the two domains' `changes` arrays).
- Each domain shows at most one Tier-1 event, all applicable Tier-2/3 events, and a Tier-4 disclosure with an accurate count.
- Quiet-state copy is exact per §10's table, for all four distinct states, both domains.
- "View Inflation →"/"View Labor →" link to the correct route (regression + new wording assertions).

**RECENT DATA UPDATES (Latest Data Detected, renamed/restructured)**
- Section heading renders "Recent Data Updates," not "Latest Data Detected" (and `Overview.test.tsx`'s heading-sequence array is updated to match, per §14).
- Inflation slot selects the correct occurrence when only items with `provider_release_id` `"10"` or `"54"` exist.
- Labor slot selects the correct occurrence when only items with `provider_release_id` `"50"` exist.
- Both slots render independently when both have items; one domain's absence never blanks the other (mirrors `CurrentStateSection`'s existing failure-isolation pattern).
- **CORRECTED per §3A:** an item for JOLTS (`"192"`) does **not** appear in the Labor slot despite `releaseCategory()` tagging it `"Labor"` — an explicit negative test asserting `CANONICAL_MONITOR_RELEASE_IDS`, not `releaseCategory()`, drives this selection (this is the specific regression this correction exists to prevent; a test that only checks GDP/Retail-Sales exclusion would not catch a JOLTS-via-category bug).
- An item whose release has no canonical monitor relation at all (JOLTS, GDP, Advance Retail Sales) does not appear in either slot.
- `selectLatestDataDetectedItem`'s own existing unit tests remain unmodified and passing (the function itself is not changed).
- Observation-changed-only (A), observation-and-analysis-changed (B), `NO_CHANGE` (E), `PARTIAL_CHECK` (C), `CHECK_FAILED` (D) all render distinctly, per domain slot.
- All evidence (both lists, every row) remains inspectable, per slot.

**NAVIGATION**
- What Changed event → correct domain route, no query params.
- Recent Data Updates slot CTA → correct domain route, no query params, no fabricated deep link.
- Release row → `/inflation` for CPI and Personal Income and Outlays, `/labor` for Employment Situation, `/releases` for JOLTS/GDP/Advance Retail Sales (explicit negative assertions too: JOLTS must NOT link to `/labor` despite its category tag; PIO must NOT be left unlinked despite its compound category string).
- `ReleaseRow`'s new "View Releases →" CTA renders inside `UpcomingReleasesPreview` but not inside `ReleaseCalendarSection` (the circular-link case, §17).
- No test asserts a route or query param not already in `App.tsx`'s existing route table.

**ARCHITECTURE GUARDS**
- No numeric magnitude-based sort exists in the new salience modules (an AST/regex guard analogous to the project's existing `no-economic-logic.test.ts` deadband guards — check for a `.sort(...)` keyed by `delta`/`Math.abs`, which would be a smuggled-in significance score).
- No 0–100/high-medium-low/severity/confidence literal appears in the new modules' logic (guard, not docstring-mention).
- No new backend file is imported by any new frontend module (structural import guard, mirroring `no-release-sync-or-coupling.test.ts`'s existing pattern).
- No new API call is added anywhere (`no-overview-mutation.test.ts`'s existing "exactly N documented read functions" guard, count updated only if a genuinely new *existing* endpoint is newly called — none is expected).
- No aggregate "Economy State"/score is introduced (regression assertion, mirroring the existing explicit prohibition already tested).
- **New guard (§3A):** `releaseCategory()`/`RELEASE_PRESENTATION` is never imported by, or used to drive, any monitor-relation or navigation decision in the new salience/Recent-Data-Updates/`ReleaseRow` code — only `CANONICAL_MONITOR_RELEASE_IDS` may. A structural check (grep/AST) for `releaseCategory` inside the new modules should return zero matches; its only legitimate remaining use in the codebase is the pre-existing, unrelated display-tag rendering on `/releases` itself.

**REGRESSION**
- Full existing `Overview.test.tsx` suite, updated only where §14/§18 require an exact-copy change, otherwise passing unmodified.
- `/inflation`, `/labor`, `/releases` pages' own test suites unmodified and passing (confirms no out-of-scope change leaked).
- Full frontend suite run twice, identical counts.
- Full backend suite confirmed unchanged (zero backend files touched — this contract requires none).

---

## §24. Product success criteria (frozen, restated precisely)

#22B succeeds if a target user can open Overview and, within seconds, correctly answer "what changed that deserves my attention" — meaning: every structural (Tier 1–3) change for both domains is visible without a click, no routine (Tier 4) numeric update ever occupies a slot ahead of an available structural change in the same domain, a quiet month is described honestly and specifically (§10), all evidence remains one click away, and every surfaced item has a correct, working next action (§17). Success explicitly does **not** mean the UI predicts market impact, scores severity, or recommends a trade — those remain, and must remain, entirely absent.

---

## §25. GO / STOP checklist

| # | Item | Status |
|---|---|---|
| 1 | Current ordering defect understood | ✅ §1, §2, §3 (root-caused to fixed component-concatenation order, not importance) |
| 2 | Salience definition frozen | ✅ §4 |
| 3 | No score required | ✅ §4 non-goals, confirmed no canonical score exists in either backend contract |
| 4 | Inflation hierarchy frozen | ✅ §6 |
| 5 | Labor hierarchy frozen | ✅ §7 (reuses shipped logic) |
| 6 | Availability handling frozen | ✅ §8 |
| 7 | Metric-only behavior frozen | ✅ §9 |
| 8 | Zero-event behavior frozen | ✅ §10 |
| 9 | Multiple-high-salience behavior frozen | ✅ §11 |
| 10 | Cross-domain separation frozen | ✅ §12 |
| 11 | Overview What Changed contract frozen | ✅ §13 |
| 12 | Latest Data Detected naming decision frozen | ✅ §14 (RENAME + RESTRUCTURE, "Recent Data Updates") |
| 13 | Data-vs-analysis distinction frozen | ✅ §15 (preserved unchanged) |
| 14 | Selection behavior frozen | ✅ §14, **corrected §3A** (per-domain, reuses existing function unmodified, now keyed by canonical monitor relation, not release category) |
| 15 | CTA/navigation rules frozen | ✅ §17, §18, **corrected §3A** (release-row target table fixed: JOLTS no longer routes to `/labor`, PIO no longer left unlinked, non-monitor releases get `/releases` instead of a dead end) |
| 16 | Dead-end fixes frozen | ✅ §17 (release rows — now zero hard dead ends, not just fewer), §14 (Recent Data Updates CTA) |
| 17 | Routine-vs-attention taxonomy frozen | ✅ §19 |
| 18 | Shared/domain-specific architecture frozen | ✅ §20 (shared vocabulary, separate per-domain maps) |
| 19 | No backend production change required | ✅ §21 (confirmed, zero) |
| 20 | Complete #22B test matrix frozen | ✅ §23 |

All twenty resolved. No current API fails to support this contract honestly (§21). No decision above requires calculating economic significance — every tier boundary is a membership test over fields the backend already returns.

---

## Appendix: secret safety and version control

No `.env`/`.env.*`/credential file was read, printed, or logged at any point this increment. The backend test run used the project's established local isolated-Postgres mechanism (trust-auth, no password). Nothing in this document was committed or pushed; the working tree outside this new file was not modified.
