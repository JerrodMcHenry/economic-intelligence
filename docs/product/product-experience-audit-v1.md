# Product Experience, Value & Workflow Audit — V1

**Increment #21.** Read-only product audit. No production code changed. Baseline: HEAD `1972a8c` ("Add Labor UI and Overview integration (#20E.2)"), clean working tree. Frontend: 673/673 passed. Backend: 1,173/1,173 passed, 0 skipped (run against the project's established local isolated-Postgres test mechanism).

This document is evidence-based: every claim below is grounded in the current repository's actual code (file/line references given where load-bearing), not in old roadmap docs, not in aspiration. Where a claim about backend logic (e.g. event ordering) determines a UI finding, the backend source is cited directly.

---

## 1. Capability inventory

### User can currently do

- View `/` (Overview): Inflation + Labor current state, Inflation + Labor What Changed (each truncated to 3 events), one Latest-Data-Detected occurrence (system-wide, not per-domain), Upcoming/Recent releases (3/1), a link to `/releases`.
- View `/inflation`: Core PCE state, full What Changed (5 subsections: Core PCE, Confirmation, Target, Headline PCE, Headline CPI), momentum metrics (1M/3M/6M/12M), target/level, confirmation (Core CPI), headline context, per-metric evidence disclosures, page-level methodology disclosure.
- View `/labor`: Labor state, Employment (condition/momentum + 3 summary metrics + evidence), Unemployment (trend + metrics + evidence), full 4-tier What Changed, Employment-Situation-scoped Latest Data Detected, Relevant Release (next/most recent Employment Situation occurrence), methodology disclosure.
- View `/releases`: Upcoming/Recent release schedule, `SCHEDULED`/`PAST_DUE` status, category tags for the six curated releases, the mandatory schedule-vs-publication disclosure sentence.
- Open any of ~30 inline `ExplanationTrigger`/`Disclosure`/`WhyThisState`/`WhyLaborState` progressive-disclosure affordances (click/keyboard, native `<details>`).
- Retry any of the ~16 independent `useApiResource` calls across the four pages on failure.
- Navigate between the four routes via the primary nav or in-page links (Overview→Inflation, Overview→Labor, Overview→Releases, Labor→Releases calendar link, via `RelevantRelease`'s reused `ReleaseRow`, which does not itself link anywhere).

### User cannot currently do

- Compare two series, two monitors, or a series against a monitor, anywhere in the UI.
- See historical context for any number (a range, a percentile, "where was this six months ago") anywhere in the UI.
- See more than one Latest-Data-Detected occurrence at once, on Overview or anywhere else — the selection is a single item, system-wide (`lib/selectLatestDataDetected.ts`), not per-domain and not a list.
- Save, bookmark, watch, or otherwise mark anything for return; no accounts exist.
- See what changed "since I last visited" — only period-over-period (monthly/release-driven) comparison exists, never session-relative.
- Reach `/labor` or `/inflation` by clicking a release row on `/releases` or in `RelevantRelease` — release rows render no link at all (`components/releases/ReleaseRow.tsx`).
- Distinguish, anywhere in the UI, a "this materially matters" change from a "this is a routine numeric update" change — no salience/significance concept exists in the frontend or the backend's response contracts.
- Search or discover a series by name/keyword (the backend can; the UI never calls it).

### Backend can do but UI does not expose

| Capability | Endpoint | Exposure |
|---|---|---|
| Series discovery (local + FRED merge) | `GET /api/v1/series/search` | none |
| Single-series detail / on-demand sync | `GET`, `POST /api/v1/series/{id}` `/sync` | none |
| Historical observation query | `GET /api/v1/series/{id}/observations` | none |
| Deterministic transformation (abs/percent change, moving average) | `GET /api/v1/series/{id}/transform` | none |
| Two-series comparison (aligned / spread / correlation) | `GET /api/v1/analysis/compare` | none |
| Composable multi-step pipeline | `POST /api/v1/analysis/pipeline` | none |
| Read-only AI query (tool-calling over the above) | `POST /api/v1/ai/query` | none |

`app/api/analysis.py:25` confirms `/analysis/compare` is **series-centric**, not monitor-centric: it takes two raw FRED series IDs (`series_a`/`series_b`) and an `AnalysisType` of exactly `"aligned" | "spread" | "correlation"` (`app/models/analysis.py:15`) — it has no concept of "Inflation state" or "Labor state" as a comparable object, and returns no persisted/cached result (recomputed every call). A future Compare *feature* could call this endpoint directly for raw-series correlation, but a genuinely monitor-level statement ("is Inflation cooling while Labor stays strong") is not something this endpoint answers today; it would require new synthesis, not just new UI.

---

## 2. First-60-seconds test

Simulated: a first-time target user opens `/`.

| Question | Verdict | Evidence |
|---|---|---|
| What is happening with inflation? | **CLEAR** | `InflationCurrentStateCard` shows "Inflation" + a large text-first state badge + period, unclicked. |
| What is happening with labor? | **CLEAR** | Identical pattern, `LaborCurrentStateCard`. |
| Did either materially change? | **CONFUSING / TOO SHALLOW** | The "What Changed" cards truncate each domain's flat, canonically-ordered event list to 3 (`components/overview/WhatChangedPreview.tsx:65`, `LaborWhatChangedPreview.tsx`). That canonical order is fixed by **section membership** (`app/domain/inflation_what_changed.py:436-441`: primary momentum → confirmation → target → headline PCE → headline CPI), not by importance. A section with only routine `METRIC_CHANGED` events sorts ahead of a later section carrying a real `STATE_CHANGED` event. Concretely: if Core PCE has zero changes but Confirmation has two metric-only updates and Target has one, those three routine numbers fill the entire Overview preview and a genuine state change three sections later (Headline PCE or Headline CPI) is **invisible** without clicking through to `/inflation`. This is a demonstrated defect, not a hypothetical. |
| Was new economic data recently detected? | **CONFUSING** | "Latest Data Detected" answers this for exactly **one** release occurrence, chosen by a fixed status-priority rule across the *entire* system (not one per domain). If Inflation's own release just landed but Labor's had a `CHANGES_DETECTED` event more recently in priority order, the user sees only Labor's — with no signal that Inflation also has fresh evidence sitting unshown. |
| What important release is next? | **CLEAR** | "Releases" section, 3 upcoming, correctly ordered, with schedule status. |
| Where should I investigate further? | **CLEAR** | Every card ends in an explicit "Open Inflation →" / "Open Labor →" / "View release calendar →" link. |

**Overall verdict: partial pass.** The state layer (top of page) is genuinely clear in 60 seconds. The *change* layer is not reliably trustworthy in 60 seconds — a routine numeric update can visually crowd out a real state change, which directly undercuts the product's own positioning ("know what changed... and prove why") at the exact moment a first-time user is forming their opinion of the product.

---

## 3. "What is happening?" test

**Inflation.** `MIXED`/`COOLING`/etc. communicate a real classification (`content/explanations/inflation.ts`'s `INFLATION_STATE_EXPLANATIONS`), but the badge alone carries no sub-dimension information — the user must open "Why {State}?" (`WhyThisState`, a collapsed `<details>`) to see `r_3m`/`r_6m`/`r_12m` and the neutral band. One click, reasonable, but the badge is not self-explanatory on its own — it names a classification, not a cause.

**Labor.** Same pattern, one layer deeper: `LaborState` is a combination of `EmploymentCondition`, `EmploymentMomentum`, and `UnemploymentTrendState`, and `MIXED` specifically means "these disagree" (curated copy is good — `content/explanations/labor.ts:93-99` explicitly explains why a still-shrinking-but-slowing payroll (`RECOVERING`) can never resolve to `STRENGTHENING`). But this nuance lives one click behind "Why {State}?" too, and on Overview the click depth to reach it is identical to Inflation's.

**Progressive disclosure works mechanically** (native `<details>`, no popover overflow, same pattern reused everywhere — `components/explanations/ExplanationTrigger.tsx`), but it is uniformly **opt-in**: nothing on the primary view volunteers *which* sub-signal is driving a `MIXED`/`COOLING` conclusion without a click. For a first-time user this is acceptable; for a returning user checking in, it means every visit costs at least one extra click to get past "what" to "why," even when "why" hasn't changed.

**Where a user would still need to leave EI:** any request for historical range/normalcy ("is 2.4% high?"), any cross-series/cross-monitor relationship, any comparison against a benchmark not already frozen into the methodology (e.g. neutral bands are shown, but nothing shows where today's reading sits in, say, the last five years).

---

## 4. "What Changed?" test

- **Comparison period:** shown per-section on the full `/inflation`/`/labor` pages (`SectionHeader`'s `periodPair`), **not shown at all** in Overview's compact previews. A user reading Overview cannot tell whether "What Changed" reflects last month or six months ago without clicking through.
- **Change-kind distinction:** genuinely well-built at the type level — `STATE_CHANGED`/`AVAILABILITY_LOST`/`AVAILABILITY_RESTORED`/`METRIC_CHANGED` (Inflation) and the same four plus `LaborChangeEventType`'s equivalent (Labor) are real, separately-labeled event kinds a user can distinguish once looking at them (`changeEventTypeLabel`/`laborChangeFieldLabel` etc. all render real words, not raw enums).
- **Prioritization of meaningful change:** exists on `/labor`'s own full page (the frozen 4-tier presentation priority, `components/labor/WhatChangedSection.tsx`) and implicitly on `/inflation`'s full page (each section renders its own `STATE_CHANGED`-first-or-"remains"-sentence logic). It **does not exist** on Overview's compact previews for either domain — those are a flat `.slice(0, 3)` over canonical (structural, not importance) order. See §2's worked example.
- **Numeric noise:** on the full pages, no — 1M is visually muted as context-only, and metric rows are compact single-line diffs. On Overview's compact preview, potentially yes, per the ordering issue above.
- **"No canonical changes" copy:** correct and honest — "No canonical Inflation changes were reported for this comparison" (never overclaims "Inflation was unchanged," correctly leaves room for "comparison unavailable").
- **Does the user know *why* a state changed?** Only partially — the event shows previous→current values and which field moved, but there's no narrative sentence connecting "Core PCE crossed the neutral band because r_3m fell to X" — the user has to read the raw numbers and already know the classification rule (which is one click away in the same explanation content, but not co-located with the event itself).
- **Does it beat manually checking the latest release?** Yes, clearly, for revision detection and structural classification changes — a manual FRED check would not tell a user "this crossed the neutral band" or "this observation was later revised." That is real, demonstrated value.

**Classification: currently behaves as (C) raw structured change log with (B) structured-change-log-quality labeling on the full pages, degrading toward (C)/(D) — noisy, unprioritized diff — on the Overview preview specifically.** It is not yet "intelligence" (a synthesized, prioritized "here's what actually matters" statement) anywhere in the product.

---

## 5. "How does it relate?" test

This is the least-developed job, confirmed by direct inspection, not assumption.

- Overview places Inflation and Labor **side by side** (`CurrentStateSection`), but side-by-side placement is explicitly *not* relationship analysis — no code anywhere compares one domain's state to another's, and the peer-card architecture was deliberately built to prevent that (`docs/architecture/labor-ui-v1.md`'s absolute prohibition on an aggregate "Economy Score").
- "Is inflation cooling while labor remains strong?" — **not answerable** without the user doing the synthesis themselves by reading two separate badges.
- "Are CPI and PCE telling the same story?" — **partially answerable**, and this is the one real relationship feature in the product: Inflation's `ConfirmationPanel`/Confirmation section explicitly compares Core CPI's state to Core PCE's (`ConfirmationRelationship`: `CONFIRMS`/`DIVERGES`/`UNAVAILABLE`). This is a genuine, if narrow, precedent for relationship UI that already exists and works.
- "Is unemployment deterioration confirming payroll weakness?" — **not answerable** as a single statement; the user can see both `EmploymentState` and `UnemploymentTrendState` in `WhyLaborState`, side by side in a `<dl>`, but nothing states whether they agree or diverge the way Inflation's Confirmation panel does for CPI/PCE. This is a real, addressable gap since `LaborState`'s own combination table already computes agreement/disagreement (`combine_labor_state`) — the raw fact exists in `state` (e.g. `MIXED` already IS "these disagree") but the UI never says *why* in those terms next to the two component readings themselves.
- "What tends to happen when these variables diverge?" — **not answerable**, no historical-regime concept exists anywhere.
- Series-level relationship (e.g. PAYEMS vs. CPIAUCSL directly) — backend-capable (`/analysis/compare`), zero frontend exposure.

**Impact on core value proposition:** moderate-to-significant. The product's own stated core job #3 ("How does it relate?") is close to entirely unserved beyond the one Inflation-internal Confirmation feature. This is a real gap, but per the audit philosophy, not automatically the highest-leverage NEXT step — see §33.

---

## 6. Monitor test

Overview *does* do real work: it aggregates four sections from seven independent endpoints without requiring the user to visit four separate pages, and each section fails independently and truthfully (dedicated cross-domain failure-isolation tests exist and pass). That is genuine monitor value over "check four pages by hand."

It does **not** distinguish IMPORTANT from ROUTINE — no such concept exists in any response contract or any frontend selection logic. The closest thing to it is Labor's own 4-tier What Changed *presentation* priority, which is scoped to `/labor` alone and was never extended to Overview's own previews (see §2, §4). Per the instruction not to invent a scoring system: the fix is not a new score, it is extending the **already-frozen, already-shipped, non-arbitrary event-type tiering** (`STATE_CHANGED`/`AVAILABILITY_*` before `METRIC_CHANGED`) to govern which events Overview's `.slice(0, 3)` keeps — a filter, not a new classification.

---

## 7. Investigate test

Simulated: Overview says "Labor: COOLING," user clicks Labor.

| Question | Answered? | Where |
|---|---|---|
| Why? | Yes | `WhyLaborState` — Employment state, Unemployment trend, evaluation period |
| Which component changed? | Yes | Employment vs. Unemployment badges are visually and semantically separate |
| Which metric changed? | Yes | `EmploymentSection`'s condition/momentum lines + 3 summary metrics |
| Over what period? | Yes | Evaluation period shown at multiple levels; per-metric period range in Employment |
| How large was the change? | Yes | `momentum_delta_jobs`, formatted in actual jobs, not percent |
| What data supports it? | Yes | `EvidenceDisclosure` — per-observation table, series ID, methodology, data basis |
| New data or a revision? | Yes | `Latest Data Detected`'s `change_type` (`NEW`/`REVISED`) on the observation rows |
| What did the previous state look like? | Partial | Previous/current values shown in What Changed events, but not the previous *state label* co-located with the current one in one glance |
| What should I investigate next? | No explicit prompt | No "related" or "next" suggestion anywhere; the page ends at Evidence & methodology |

**Verdict:** the investigation workflow genuinely does not stop early — it is one of the more complete jobs in the product. The one soft stop is the absence of any "what's related" prompt at the end of a page (a dead end in the sense of "no next suggested action," not "broken").

Repeating for Inflation: identical depth (momentum metrics, target, confirmation, headline context, evidence, methodology) — arguably *more* complete than Labor because Confirmation adds one cross-series relationship the Labor page has no equivalent of.

---

## 8. Compare test

Audited directly (`app/api/analysis.py`, `app/services/analysis.py`, `app/models/analysis.py`):

- Capabilities that exist: exact-date alignment, spread, and Pearson correlation, over **any two persisted series by raw FRED ID**, with optional date bounds.
- Usable from frontend today: **no** — zero import of `api/v1/analysis` anywhere in `frontend/src`.
- API contract suitability: workable for a *raw-series* Compare feature (feed it `PAYEMS`/`CPIAUCSL`/etc. directly), but **not suitable as-is** for a *monitor-level* Compare feature — it has no concept of `InflationState`/`LaborState`, canonical periods, or classification. Building "compare Inflation vs. Labor" as a product feature would require new synthesis work above this endpoint, not just a new UI calling it.
- Series-centric or monitor-centric: **series-centric only**, today.
- What's missing for a useful Compare experience: (a) a frontend surface at all, (b) a decision on whether Compare targets raw series (cheap, backend-ready) or canonical monitor states (valuable, not backend-ready), (c) some notion of which series pairs are *meaningful* to compare (the six curated releases' mapped series are a natural starting set, not yet exposed as such).

**Is Compare the highest-leverage missing surface right now?** Valuable, but not the single highest-leverage item — see §33 for why the Overview salience fix ranks above it (smaller, backend-complete, addresses a currently-misleading experience rather than adding a new one).

---

## 9. Save / return test

None of save/bookmark/watch/return-diff exist. Per the audit's own instruction not to assume this is automatically next: given §6's finding that even the *existing* Monitor loop has a demonstrated noise problem, Save is premature — there is limited value in letting a user "save" a view whose own change-surfacing isn't yet reliable. This belongs in RETENTION NEXT, not CORE LOOP NEXT (see §32/§39).

---

## 10. Release experience test

`/releases` is, today, **primarily a calendar** — it answers "what's next" and "what recently happened" (schedule-wise) well, and explicitly, correctly refuses to conflate schedule with publication (`ReleaseScheduleDisclosure`, tested). It does **not** answer "what did EI actually detect" or "what analysis changed after processing" — those live only in Latest Data Detected (Overview, system-wide-one-item) and, for Employment Situation specifically, on `/labor`. There is no path from a release row to its own detected evidence (`ReleaseRow` renders no link, confirmed by direct inspection — §19).

**Terminology clarity among scheduled release / processing status / Latest Data Detected / canonical state / What Changed:** for a user who has not read the architecture docs, these five concepts are genuinely hard to keep straight — the product exposes internal *pipeline stages* (schedule → processing → detected evidence → analysis consequence → canonical state) as if they were user-facing product concepts, rather than presenting one user-facing narrative ("Employment Situation published new payroll data on [date], which moved Labor's state from X to Y"). This is architecture leaking into product surface.

---

## 11. Latest Data Detected test

- Does it mean anything to a user without context? **No, not on first encounter** — it names a *pipeline step* (a check ran and found something), not an economic fact. A user's first reasonable guess ("the newest number") is close but not quite right (it also fires for revisions, and can be silent for a while and then report older evidence explicitly framed as "earlier changes" — correct, but requires reading the fine print).
- Confusable with "latest release," "What Changed," "new observation," "revision," "new state"? **Yes, plausibly with several of these** — it is genuinely adjacent to all of them and the UI's own disclosure copy has to work hard to keep them apart (`content/explanations/processingStatus.ts`'s `TRACKED_ANALYSIS_CHANGE` explanation is a good, honest sentence, but it is one click deep).
- Does it distinguish DATA CHANGED from INTELLIGENCE CHANGED? **Yes, structurally** — "Source data changes" vs. "Tracked analysis changes" are genuinely separate, sibling, never-nested sections (by explicit ADR). This is a real strength once a user notices the two headings.
- **Recommendation (frozen, not implemented this increment):** keep the DATA/INTELLIGENCE structural split — it is correct and valuable. **Rename** the section itself to something that states the user-facing fact rather than the pipeline step (e.g., something oriented around "what data changes were caught," not "detected," which reads like a system log entry). **Restructure** to surface one occurrence per domain rather than one system-wide occurrence, so Inflation's and Labor's own fresh evidence can't silently crowd each other out. Do not change prominence otherwise — its current position (3rd of 4 Overview sections) is reasonable once the above are fixed.

---

## 12. Explainability test

The RESULT → WHAT IS THIS? → WHY DOES IT MATTER? → WHY IS EI SHOWING THIS? → HOW IS IT CALCULATED? → SOURCE model is implemented consistently (`Explanation` type: `title`/`definition`/`whyItMatters`/`sourceNote`), reused identically across Inflation, Labor, Releases, and processing-status content — genuinely one system, not four ad hoc ones.

- Duplication: minimal — result explanations (`WhyThisState`/`WhyLaborState`) and concept explanations (`ExplanationTrigger`) are cleanly separated, no copy is maintained twice.
- Forced clicks: every explanation is opt-in (native `<details>`), never forced — good for experts, but see §3: it also means nothing volunteers itself, so a returning user re-clicks the same disclosures every visit to re-confirm nothing changed.
- Methodology timing: appears last, behind its own disclosure, correctly deprioritized relative to the state/evidence a beginner needs first.
- Beginner comprehension: strong — copy is plain-language, "Mixed is a real, distinct classification, not a data gap" is a genuinely good sentence for a non-expert.
- Expert verifiability: strong — methodology IDs, data basis, per-observation evidence tables, comparison-contract IDs are all present and reachable.
- Evidence rawness: appropriately raw where it should be (FRED-native units correctly and explicitly distinguished from converted units, `EvidenceDisclosure`'s `unitLabel`), not over-simplified.
- Does it serve both audiences without clutter: **yes** — this is one of the product's stronger dimensions.

---

## 13. Trust test

A skeptical user CAN, without reading code, determine: data source (`sourceNote`s cite series IDs and FRED), the period analyzed (shown at multiple levels, though inconsistently — absent from Overview's compact previews, §4), whether data was revised (explicit `REVISED`/`NEW` labeling, explicit revision-history framing), how the state was calculated (via progressive disclosure, always reachable), which methodology version (`methodology_id`, shown verbatim as e.g. `"labor_v1.0"`), and — critically — that AI did **not** generate the conclusion, because no AI-attribution language exists anywhere near a canonical result (correct: there is no AI in this path at all, and nothing implies otherwise).

Overexposure of internal language: some — `data_basis` renders the literal internal string `"latest_revised_data"` verbatim in a `<dd>` (`EvidenceDisclosure.tsx:66`, `MethodologyDisclosure.tsx`), and `methodology_id`/`comparison_contract_id` are internal version-string identifiers shown as-is. These sit behind disclosures (lower severity) but are still genuinely internal-looking to an outside reader.

"Canonical" itself: this exact word does **not** appear in any user-facing copy string found (`grep` of `content/explanations/*` and component JSX) — it is a codebase/architecture-doc term only. Good: the product does not expose it. The *concept* (a reproducible, deterministic, non-AI conclusion) is communicated instead through concrete facts (methodology ID, evidence table, "not derived from AI" by omission) — which is the right way to do it.

---

## 14. FRED differentiation

| Workflow | FRED does | EI does | EI adds |
|---|---|---|---|
| "What's the latest CPI reading?" | Shows the raw series, a chart | Shows a classified state + evidence | A deterministic interpretation layer FRED explicitly does not provide |
| "Did this get revised?" | Requires manually diffing vintages (ALFRED, separate tool) | Explicit `REVISED` vs `NEW` labeling, automatically | Revision detection without manual vintage comparison |
| "What changed since last month?" | Nothing built-in | Structured `ChangeEvent`/`LaborChangeEvent` list | A maintained, structured diff FRED has no equivalent of |
| "Is this a big deal?" | Nothing | Nothing reliable yet (§2/§4/§6) | **Currently no differentiation** — this is the gap |
| Charts / visual history | Yes, extensively | No | **EI currently loses here outright** |

This is not "prettier cards" — the classification + revision-tracking + structured-diff layer is real, demonstrable differentiation for the "what changed and why" jobs. It is not yet differentiation for "how big a deal is it" or "how does this compare historically," where FRED (with charts) currently wins on the historical-context dimension specifically.

---

## 15. Generic-AI differentiation

| Capability | Currently delivered | Aspirational only |
|---|---|---|
| Reproducibility (same input → same output, provably) | **Delivered** — deterministic domain modules, 1,173 backend tests | |
| Deterministic methodology, versioned | **Delivered** — `methodology_id` on every result | |
| Exact, inspectable evidence | **Delivered** — per-metric evidence tables | |
| Continuously maintained state | **Delivered** — release-driven update pipeline (#18/#20D) | |
| Revision tracking | **Delivered** — `NEW`/`REVISED` observation change types | |
| Release monitoring | **Delivered** — `/releases`, processing status | |
| Comparison / relationship reasoning | | **Aspirational** — only Inflation's own CPI/PCE confirmation exists (§5) |
| Provenance | **Delivered** — series IDs, data basis, sourceNotes | |

A user asking ChatGPT "what's happening with inflation" gets a plausible-sounding, non-reproducible, non-versioned, non-evidence-linked answer that may be stale or subtly wrong with no way to verify it. EI's honest, *currently delivered* answer to "why not just ask AI" is genuinely strong: reproducibility + evidence + revision tracking are real and non-trivial to fake. This is the product's clearest, most defensible differentiation today, and the audit should not undersell it — but it is also under-communicated in the primary UI (see §16).

---

## 16. Macro-dashboard / Koyfin-class differentiation

If another product already offers charts, series, dashboards, and a release calendar, what does EI add? The honest answer, from delivered capability: a maintained, deterministic, evidence-linked change-detection layer with revision tracking. **Does the current UI make that difference obvious?** Not reliably — visually, `/`, `/inflation`, `/labor` read as clean, well-organized cards with badges and small disclosures, which is structurally similar to what a smaller macro dashboard looks like at a glance. The differentiating substance (methodology IDs, revision tracking, deterministic-not-AI guarantee) is real but lives *behind* disclosures rather than being asserted anywhere prominent. Nothing on `/` states, even in one sentence, "every number here is reproducible and every classification is deterministic, never AI-generated" — a claim the product can actually back up today and currently doesn't make out loud.

---

## 17. "Why would I pay?" test

Ranked, capabilities that **exist today**:

1. Maintained, deterministic classification (state) that would otherwise require the user to build and maintain their own pipeline.
2. Structured, trustworthy change detection with revision awareness — genuinely hard to replicate by hand reliably.
3. Curated, verifiable evidence trail per metric.
4. A release calendar scoped to what actually matters to the monitored series (curated, not the full FRED release list).

Smallest missing capability that could materially increase willingness to pay: **reliable change salience** (§2/§4/§6) — today, a paying user cannot yet fully trust that "nothing important" on Overview actually means nothing important, which undercuts exactly the "so you don't have to check manually" value proposition that most directly justifies payment. This is a small, well-scoped fix, not a new feature category.

---

## 18. Daily/weekly habit test

Why open EI tomorrow? Because canonical state or evidence may have changed. Why next week? Same. What does EI remember between visits? **Nothing** — no session, no "since you last looked" diff, no proactive surfacing (no notifications, no digest). What work does the user avoid by returning? Manually checking FRED/BLS/BEA release calendars and re-deriving momentum classifications by hand — a real value, but it requires the user to *initiate* the check every time; EI never reaches out.

**Verdict: the retention loop is weak**, exactly as the audit anticipated it might be. The missing mechanism is not automatically "notifications" (correctly flagged as an assumption to avoid) — it could equally be a simple "what changed since you were last here" framing using existing data (a session-local last-visit timestamp compared against already-existing change timestamps) before any push mechanism is justified.

---

## 19. Dead-end audit

| CTA/link | Leads to | User's prior question | Answered? | Next logical action available? |
|---|---|---|---|---|
| Overview → "Open Inflation →" | `/inflation` | "Tell me more about Inflation" | Yes | Yes (page has its own further links to Releases via nothing direct, but Evidence/Methodology) |
| Overview → "Open Labor →" | `/labor` | Same, Labor | Yes | Yes |
| Overview → "See full comparison →" (×2) | `/inflation` or `/labor` What Changed | "Show me everything that changed" | Yes | Yes |
| Overview → "View release calendar →" | `/releases` | "What's coming up" | Yes | Partial — lands on the calendar with no scroll-to/highlight of the specific release that prompted the click |
| State badge → "Why {State}?" | inline expand | "Why is this the state?" | Yes | N/A (terminal, correctly) |
| release row (`ReleaseRow`, on `/releases` and in `RelevantRelease`) | **nowhere** | "What does this release affect / what did EI find for it?" | **No — hard dead end** | **No link exists at all** |
| Latest Data Detected item | **nowhere** (not even to the release itself) | "Tell me more about this detected change" | **No — hard dead end** | None |
| evidence table row | terminal (correctly, it's raw data) | "Is this number right?" | Yes (it IS the answer) | N/A |
| Evidence & methodology disclosure | terminal | "How was this calculated?" | Yes | No link to the actual methodology *document* — only an ID string, not a reference |

**Two real, fixable dead ends:** release rows never link anywhere, and detected-change items never link back to their originating release. Both are small, concrete UI gaps (not backend gaps — the data needed to build both links already exists in the response payloads).

---

## 20. Information density audit

- Whitespace/cards/badges: reasonable, not excessive — each page uses one dominant badge plus compact secondary text, not badge-soup.
- Explanatory prose: appropriately terse in primary copy; longer prose is consistently behind disclosures.
- Disclosures: not excessive on any single page (Inflation: methodology + ~6 per-metric evidence disclosures; Labor: similar) — but *across* the four pages there is real repetition of the same disclosure *shape* (methodology ID / data basis / evaluation period appears near-verbatim three times: Inflation methodology, Labor methodology, per-metric evidence) without being wrong to repeat.
- Methodology exposure: appropriately minimal in primary view, appropriately available on demand.
- Evidence: sufficient depth, not too little.
- **Historical context: too little** — effectively absent everywhere (§22).

No layout redesign is implied by this section; the finding is about what's present, not how it's arranged.

---

## 21. Terminology audit

| Term | Verdict | Note |
|---|---|---|
| Canonical | **HIDE / not user-facing already** | Confirmed absent from all user-facing copy — codebase-only term, correctly kept out. |
| Data basis | **RENAME (behind disclosure)** | Raw value `"latest_revised_data"` shown verbatim; low severity (disclosure-only) but easy to humanize. |
| Latest revised (data) | **KEEP** | The disclosure heading itself ("Latest revised data") plus its prose is clear; this is a good example of the pattern working. |
| Evaluation period | **KEEP, borderline RENAME** | Understandable in context (paired with an actual date range), mildly technical as a standalone label. |
| Processing status | **HIDE BEHIND DISCLOSURE (mostly already is)** | Values are humanized ("Data changes detected," not `CHANGES_DETECTED`) — the *field name* itself never appears in the primary UI, only in disclosure `<dt>`s and the architecture docs. Fine as-is. |
| Latest Data Detected | **RENAME** | Section-heading-level, most prominent occurrence of an internal-sounding term; see §11's specific recommendation. |
| Metric updates | **KEEP** | Plain enough, correctly used as a secondary-disclosure label on `/labor`. |
| Availability restored / lost | **KEEP, with existing framing** | Already correctly explained as "a data-availability fact, not an economic reading" wherever it appears — the term itself is fine given that framing is always co-present. |
| Methodology ID | **KEEP, behind disclosure** | Appropriate for the expert-verification audience it serves; correctly never in primary view. |

---

## 22. Historical context gap

Confirmed absent everywhere: no range, no percentile, no "six months ago," no chart, anywhere in the current UI. A user reading "Core PCE 3M annualized = 2.64%" has no way, inside the product, to know if that's high, low, or typical without leaving. This is a real gap and the audit agrees with the prompt's own framing that it is **not automatically a charts problem** — the cheapest, most in-character-with-the-product's-own-style fix would be a small amount of *textual* historical framing (e.g., the prior period's own value already exists in every `WhyThisState`/`WhyLaborState` payload's implicit prior-state data, or could be added as one more evidence field) before reaching for a charting library.

---

## 23. Change significance gap

Confirmed: EI knows *whether* something changed (`event_type`, `metric_changed`/`state_changed`/`availability_*` flags) but has **no concept of importance** anywhere in a response contract or frontend selection. The one place a significance-like idea exists is Labor's own frozen 4-tier *presentation* priority — which is exactly the right shape of answer (a deterministic, non-scored, event-type-based tiering, not a magic number) — but it is scoped to `/labor`'s full page only and was never extended to Overview.

**Product requirement, not methodology** (per the instruction to describe the requirement before any methodology): Overview's compact previews and Latest Data Detected selection need a deterministic rule that prefers `STATE_CHANGED`/`AVAILABILITY_*`-shaped events over `METRIC_CHANGED`-shaped ones when truncating for display, and prefers a domain's own most-recent-with-real-content occurrence over an older, more "prioritized-by-accident" one. This is a filter over already-existing, already-deterministic fields — not a new scoring system.

---

## 24. Cross-domain synthesis gap

Confirmed: no code anywhere synthesizes Inflation and Labor into a joint statement (correctly — this was explicitly and deliberately prohibited in the frozen Labor UI contract). The value lost is real (§5) but the audit's own caution is warranted: an "Inflation cooling + Labor cooling → X" table is exactly the kind of arbitrary-scoring risk the product has so far correctly avoided (no aggregate Economy Score exists, by design, at three separate frozen decision points across #19A/#20E.1/#20E.2). 

**Assessment: valuable soon, premature now.** With only two domains, a "regime matrix" would cover a small combinatorial space poorly generalized from n=2; it would also compete for attention with the more urgent, better-evidenced §2/§4/§6 fix. Revisit once either a third domain exists or the single-domain Confirmation-style pattern (§5) has been extended to Inflation-vs-Labor specifically as a narrow, non-scored "do these two state trajectories agree or diverge" statement — closer to what Inflation's own CPI/PCE Confirmation already does, not a new scoring framework.

---

## 25. Data coverage (breadth vs. depth) gap

Two domains are enough to validate the *product loop's mechanics* (routing, peer-domain composition, failure isolation, cross-domain testing) — and #20E.2 already did that successfully. They are **not** enough, and arguably already slightly too many, to validate the *Monitor* job specifically, because the noise problem in §2/§4/§6 gets **worse**, not better, as domains are added — more sections competing for the same fixed 3-item truncation increases the odds any one domain's real signal gets crowded out by another's routine noise. **Depth, not breadth, is the current bottleneck.** Adding Growth now would add a third card to an already-demonstrated-imperfect workflow rather than fixing it.

---

## 26. Mobile / responsive audit

Structural: one shared `PageContainer` (`max-w-5xl`, responsive padding `px-4 sm:px-6 lg:px-8`), pages content capped at `max-w-3xl` inside it — a comfortably narrow reading column that should reflow correctly. Grids default to single-column and expand at `sm:` (`EmploymentSection`'s 3-metric grid: `grid-cols-1 sm:grid-cols-3`), the correct mobile-first pattern. One structural risk: `components/labor/EvidenceDisclosure.tsx`'s `<table>` (Period/Value, 2 columns) has no `overflow-x-auto` wrapper — low risk given only two narrow columns, but the one table in the codebase that could theoretically overflow on a very narrow viewport with a long series title. No redesign is implied here; this is a minor, easily-verified-later item.

---

## 27. Error / stale / missing experience audit

Loading, API failure, and "insufficient data" are cleanly, distinctly presented: `LoadingSkeleton` shows no numbers ever (verified by its own docstring guarantee and by dedicated tests), `ErrorMessage` is a distinct `role="alert"` block that never renders transport details, and `INSUFFICIENT_DATA`/`UNAVAILABLE` are real, separately-toned, separately-labeled canonical values — never silently folded into a generic error. `PARTIAL_CHECK` (release processing) and past-due releases are labeled correctly and distinctly from economic states. **No case found where a failure/system state is accidentally presented as an economic one** — this is a real strength, consistent with the "infrastructure failure vs. economic-data unavailability" distinction being enforced architecturally (checked by tests, not just convention).

---

## 28. Product identity test

> "Economic Intelligence is the product I use when I want to **understand what changed in the U.S. inflation and labor data, with a classification I can trust and evidence I can check, without maintaining my own pipeline.**"

> "I would not use Economic Intelligence for **comparing series or monitors against each other, getting historical/percentile context, tracking anything beyond inflation and labor, or getting a proactive heads-up between visits.**"

The first sentence is reasonably specific for what exists *today* — it is not vague, but it is narrower than the product's own stated positioning ("understand what changed... and prove why," across "the economy" generally). The gap between the stated positioning and the currently-true identity sentence is itself a finding: the positioning is aspirationally correct but not yet fully earned by the current surface (two domains, no relate/compare, no historical context).

---

## 29. Moat / compounding-assets test

| Asset | Current | Future compounding |
|---|---|---|
| Versioned methodologies (`inflation_v1.0`, `labor_v1.0`, `*_what_changed_v1.0`) | **Current asset** — real, versioned, tested | Compounds as more versions accumulate and old ones stay reproducible |
| Revision histories (`ReleaseObservationUpdate`, `NEW`/`REVISED`) | **Current asset** — persisted, queryable | Compounds into a genuine vintage-history dataset over time |
| Detected-change histories (`ReleaseAnalysisUpdate`) | **Current asset** — persisted | Compounds into a change log no other product maintains for these specific derived states |
| Release histories (`ReleaseCheckRun`) | **Current asset** | Compounds into an audit trail of EI's own monitoring reliability |
| State histories (a queryable "what was the state on date X") | **Not yet materialized as a user-facing asset** | **Future compounding asset** — the data exists in principle (recomputable at any historical period via `_at`-suffixed functions) but there's no persisted or exposed state-history endpoint/UI today |
| Cross-domain intelligence | Not present | Future, contingent on §24 |
| Saved research / user workflows / provenance-of-user-work | Not present (no accounts) | Future, and the largest genuine "moat" candidate long-term, entirely unbuilt |

Code itself is correctly not claimed as a moat. The real, already-accruing compounding asset is the **revision and change history the pipeline has been persisting since #18** — this is data nobody else is specifically maintaining in this shape, and it grows more valuable the longer the system runs, independent of any UI decision made this increment.

---

## 30. Product-loop scorecard

| Dimension | Score | Evidence |
|---|---|---|
| Monitor | **3/5** | Overview aggregates 4 sections from 7 independent, failure-isolated resources (real work done for the user) — but has a demonstrated signal/noise defect (§2, §4, §6) and shows only one Latest-Data-Detected occurrence system-wide. |
| Investigate | **4/5** | Full component breakdown, per-metric evidence tables, period ranges, revision-vs-new distinction, methodology, all reachable in ≤2 clicks from Overview for both domains (§7). Missing: no "what's related / investigate next" prompt at the end of a page. |
| Compare | **1/5** | Zero frontend surface; backend exists but is raw-series-only, not monitor-level (§8). |
| Save | **1/5** | No accounts, no persistence, no watch, no bookmark (§9). |
| Return/Habit | **2/5** | Nothing changes or is remembered between visits; no since-last-visit diff (§18). |
| Trust | **4/5** | Methodology IDs, data basis, evidence tables, explicit revision framing, provably no AI in the canonical path (§13). Minor: a few raw internal strings shown verbatim behind disclosures. |
| Explainability | **4/5** | One consistent, reused progressive-disclosure system across all domains; good beginner copy; full expert verifiability (§12). Minor: nothing volunteers itself without a click. |
| Differentiation | **3/5** | Real, demonstrable differentiation vs. FRED and generic AI on reproducibility/revision-tracking/evidence (§14, §15) — but not visually asserted anywhere in the primary UI, and currently reads visually like a smaller macro dashboard (§16). |
| Beginner comprehension | **4/5** | Plain-language labels, no misleading color, clear non-jargon primary copy (§3, §12). |
| Expert usefulness | **3/5** | Real evidence and methodology depth for verification, but no historical/percentile context and no cross-series tooling limit how far an expert can go without leaving (§22, §8). |

No arbitrary overall average is given, per instruction — the individual scores and their evidence are the finding.

---

## 31. User journey simulations

**A — "I have 60 seconds. What changed in the economy?"**
START: `/`. STEPS: read Current State, read What Changed (×2 cards). SUCCESS: partial — state layer is clear; change layer risks noise (§2). FRICTION: no comparison period visible on the compact preview. DEAD END: none. MISSING: change-salience filtering.

**B — "Labor says Cooling. Why?"**
START: `/` → click "Open Labor →". STEPS: read Labor state → open "Why Cooling?" → read Employment/Unemployment sections → open per-metric evidence. SUCCESS: yes, fully — this is the product's strongest journey (§7). FRICTION: minimal. DEAD END: none. MISSING: nothing significant.

**C — "Inflation says Mixed. What disagrees?"**
START: `/` → click "Open Inflation →". STEPS: open "Why Mixed?" (see r_3m/r_6m/r_12m vs. neutral band) → optionally check Confirmation section for CPI agreement. SUCCESS: yes, but requires visiting `/inflation` — not resolvable from Overview alone. FRICTION: the word "disagrees" maps onto two different things (internal r_3m/r_6m disagreement vs. CPI/PCE Confirmation disagreement) and the UI doesn't disambiguate which one the user means. DEAD END: none. MISSING: none fatal.

**D — "New Employment Situation data arrived. What changed?"**
START: `/labor` (or notice via Overview's Latest Data Detected, if Labor's occurrence happened to win the system-wide selection). STEPS: check Latest Data Detected (scoped correctly to Employment Situation on `/labor`) → check What Changed. SUCCESS: yes, this is well-built — specifically engineered in #20D/#20E for exactly this journey. FRICTION: if the user starts from Overview and Inflation's release "won" the single system-wide Latest-Data-Detected slot, they may not realize Labor also has fresh evidence without visiting `/labor` directly. DEAD END: none. MISSING: none on `/labor` itself.

**E — "I want to compare inflation and labor."**
START: anywhere. STEPS: none exist. SUCCESS: no. FRICTION: total. DEAD END: **yes, immediate** — no Compare surface anywhere (§8). MISSING: the entire feature.

**F — "I want to come back next week and know what changed since today."**
START: `/`, this week. STEPS: user must manually remember today's state; no save/bookmark exists. Next week: `/` shows current state and period-over-period (monthly/release-driven) What Changed, **not** since-visit diff. SUCCESS: no, not as asked. FRICTION: total — the user is doing the diffing mentally. DEAD END: **yes** — no session memory, no notification, no digest (§18). MISSING: any since-last-visit concept.

---

## 32. Prioritization

**A. FIX NOW** (current product is confusing/broken without this)
- Overview's What Changed preview truncation can surface routine metric noise ahead of a real state change (§2, §4, §6) — directly undercuts the "know what changed" positioning on the first page a user sees.
- Release rows and Latest-Data-Detected items are hard dead ends with no link anywhere, despite the necessary data already existing in the response payload (§19).

**B. CORE LOOP NEXT** (needed to complete Monitor → Investigate → Compare)
- Extend the already-frozen event-type salience tiering (from `/labor`'s own WhatChangedSection) to govern Overview's compact previews and Latest-Data-Detected selection — completing Monitor.
- A first, narrow Compare surface (raw two-series compare, using the existing `/analysis/compare` endpoint as-is) or, alternatively, a narrow Inflation-vs-Labor "agree/diverge" statement modeled on Inflation's own existing Confirmation pattern — completing "How does it relate?" without inventing a scoring system.
- Per-domain (not system-wide) Latest Data Detected, so one domain's fresh evidence cannot hide another's.

**C. RETENTION NEXT** (needed once the core loop is compelling)
- Since-last-visit framing (even lightweight, client-local, no accounts required).
- Save/bookmark/watchlist, once accounts or persistence become worth building.

**D. BREADTH LATER**
- Growth or any third economic domain — explicitly not justified by current evidence (§25); would worsen, not fix, the current bottleneck.

**E. DEFER**
- Cross-domain synthesis/regime matrix (§24) — valuable soon, premature now, real scoring-system risk.
- Historical/percentile context and charts (§22) — real gap, but not the sharpest one; textual framing is a smaller first step than charting.
- Series discovery / transform / pipeline UI exposure — real backend capability, but no demonstrated user-facing job currently blocked on it.
- Terminology renames that are already behind disclosures (§21) — low severity, can ride along with other work rather than justify a dedicated pass.

---

## 33. Next-increment decision

**Recommended: Overview Change Significance — extend the existing, frozen event-type salience tiering to Overview's What Changed previews and Latest Data Detected selection, and close the two hard dead ends in §19.**

**The user problem:** a user relying on Overview — the product's own designed entry point and the one place its positioning ("know what changed... and prove why") is meant to be proven in under a minute — cannot yet trust that what's shown there reflects what actually matters, because routine numeric updates can structurally crowd out real state changes in a fixed 3-item truncation, and because only one release's fresh evidence is ever shown system-wide even when multiple domains have real news.

**Why it is the bottleneck:** it is the only finding in this audit that is (a) concretely demonstrated from actual code logic, not inferred or hypothetical, (b) sitting on the product's own primary landing surface, (c) directly contradicts the stated positioning at the exact moment a new user forms their opinion, and (d) blocks the value of every other page, since Overview is the map a user relies on to decide where to click next.

**Why this increment, not another:** it requires **zero new backend capability** — every field needed (`event_type`, per-domain `release_id`, existing occurrence status) already exists; it reuses a pattern **already designed, frozen, and shipped** for `/labor`'s own WhatChangedSection, so there is no new methodology risk and no new "is this an arbitrary score" question to litigate; and it directly serves the existing thesis rather than expanding the product's surface area.

**Why not the runner-up (Compare):** Compare is real, valuable, and even backend-ready for a narrow raw-series version — but it is a *new* surface with real design decisions still open (raw-series vs. monitor-level, which pairs are meaningful), and per the audit's own philosophy ("does what exists solve the intended job?" before "what else could we build?"), the current *Monitor* job should be made trustworthy before adding a new job on top of it.

**What success looks like:** on Overview, a routine numeric-only update can never occupy one of the 3 visible What Changed slots ahead of an available state/availability event in the same domain's own event list; Latest Data Detected can show fresh evidence for more than one domain without one hiding the other; every release row and every detected-change item has a working link to what it concerns. All three are verifiable by test (mirroring the existing pattern of dedicated ordering/priority tests already used for `/labor`'s own WhatChangedSection).

**What we should explicitly NOT build yet:** any aggregate score, any cross-domain regime matrix, any new backend endpoint, any Compare UI, any charts, any accounts/save/watchlist, any third economic domain, any notifications.

---

## 34. Runner-up

**Runner-up: a narrow, Confirmation-style "How does it relate?" statement for Inflation vs. Labor (or, alternatively, a minimal raw-series Compare view using the existing `/analysis/compare` endpoint as-is).**

This comes second, not first, because: it is genuinely a *new* product surface rather than a repair to an existing one, it carries more open design risk (which of the two shapes — raw-series compare vs. monitor-relationship statement — is worth building first is not yet settled by this audit), and it does not fix the more urgent, already-demonstrated problem that the product's own primary landing page can currently misrepresent what matters. Once Overview's salience/dead-end issues are fixed (§33), this is the natural next step to move the product from "two well-built parallel monitors" toward actually serving its third core job ("how does it relate?").

---

## 35. Product thesis stress test

**Original thesis:** Economic Intelligence should continuously monitor trusted economic data, maintain deterministic analysis, detect meaningful changes, and let users understand what happened and inspect the evidence without manually rebuilding the analysis themselves.

**Classification: STRONGER.**

Why: every clause of the thesis now has *real, tested, working* backing that did not exist before Inflation and Labor coexisted — "continuously monitor" (the release-driven pipeline, #18/#20D), "maintain deterministic analysis" (two independent, versioned, tested methodologies), "detect meaningful changes" (structured `ChangeEvent`/`LaborChangeEvent` machinery, real and correct at the *type* level), "understand what happened and inspect the evidence" (§7, §12 — genuinely one of the product's strongest dimensions). The multi-domain proof this increment's predecessor delivered (#20E.2) is itself evidence the architecture generalizes without a rewrite, which is exactly what a "stronger" thesis needs to demonstrate.

The one word in the thesis genuinely **not yet fully earned** is "meaningful" in "detect meaningful changes" — the product detects *changes* reliably; it does not yet reliably detect which of them are *meaningful*, which is precisely §33's finding. This is a real, identified gap, not a reason to doubt the thesis — it is the natural next problem a thesis this specific and this well-executed should now be confronting. Nothing found in this audit suggests the thesis itself is wrong; the recommended next increment is a direct, narrow continuation of it, not a course correction.

---

## Appendix: web/competitor research disclosure

Per this audit's own rule, no broad internet research was performed — every claim above about FRED, Koyfin, or generic AI assistants is **product reasoning grounded in this repository's own delivered capability**, explicitly separated (§14, §15, §16) into "currently delivered" vs. general reasoning about what those alternatives are understood to offer, not fresh competitive research. Web access was not required to reach any finding in this document.
