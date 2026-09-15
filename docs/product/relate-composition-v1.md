# Relate V1 — Composition Contract Freeze

**Increment #23B.** Contract freeze only. No production code changed this increment. Baseline: HEAD `03d0844` ("Define deterministic presentation salience for canonical Inflation and Labor change events" — #22B). #23A's own artifact (`docs/product/relate-compare-audit-v1.md`) was still untracked when this turn began — same recurring pattern as #20E.1/#20E.2 and #22A/#22B; its content was fully available and is treated as authoritative. Frontend: 731/731 passed. Backend: 1,173/1,173 passed, 0 skipped, against the established local isolated-Postgres mechanism.

This document is the authoritative contract for Increment #23C. #23C implements it by exact transcription. If any sentence template below turns out, on implementation, to require new economic interpretation, #23C must STOP and remove that sentence rather than improvise.

---

## §1. Authoritative inputs, read in full

`docs/product/relate-compare-audit-v1.md`, `docs/product/overview-attention-model-v1.md`, `docs/product/product-experience-audit-v1.md` — read in full before drafting. Current contracts inspected fresh, not from memory (evidence below cites exact files/lines).

---

## §2. Composition vs. inference — frozen boundary

> **COMPOSITION**: combining two or more already-canonical facts, verbatim, into one human-readable statement that assigns no new economic meaning to their combination. A composed sentence may state facts side by side, may state which period each fact is as of, and may use a neutral conjunction — it may never use a word or structure that itself asserts a relationship the backend has not already computed.

> **INFERENCE**: creating a new conclusion from the combination — a label, a relationship claim ("agree"/"diverge"/"confirm"/"contradict" across domains), a directional/economic judgment ("healthy," "favorable," "risk-on"), or any regime name.

**Frozen prohibited vocabulary, cross-domain (Inflation × Labor), absolute:** "agrees," "confirms," "diverges," "contradicts," "Goldilocks," "soft landing," "hard landing," "stagflation," "recessionary," "expansionary," "risk-on," "risk-off," "bullish," "bearish," "healthy economy," "favorable environment," "the economy is [anything]." None of these may appear anywhere in a #23C-generated string, under any state combination. This restates and extends `docs/product/relate-compare-audit-v1.md` §15/§16's own frozen finding — not a new decision, a transcription of an already-frozen one.

---

## §3. Canonical inputs, inspected fresh

**Inflation** (`frontend/src/api/inflation.types.ts`, verified against `app/domain/inflation.py`): `InflationMonitorResult.underlying_momentum.state: InflationState` (`"COOLING"|"HEATING"|"STABLE"|"MIXED"|"INSUFFICIENT_DATA"`), `underlying_momentum.calculation_period: string | null` — the exact field already rendered today (`components/overview/InflationCurrentStateCard.tsx:45`, `components/inflation/InflationHero.tsx:40`: `` `Core PCE · ${formatPeriod(momentum.calculation_period)}` ``).

**Labor** (`frontend/src/api/labor.types.ts`): `LaborMonitorResult.state: LaborState` (`"STRENGTHENING"|"COOLING"|"STABLE"|"MIXED"|"INSUFFICIENT_DATA"`), `LaborMonitorResult.evaluation_period: string | null` (already rendered identically, `LaborCurrentStateCard.tsx`/`LaborHero.tsx`). `EmploymentResult.state: EmploymentState` (`"EXPANDING"|"COOLING"|"STABLE"|"CONTRACTING"|"RECOVERING"|"INSUFFICIENT_DATA"`), `UnemploymentResult.state: UnemploymentTrendState` (`"IMPROVING"|"DETERIORATING"|"STABLE"|"INSUFFICIENT_DATA"`) — **neither carries its own period field**; both are evaluated under Labor's one shared `evaluation_period` (see §17).

**Existing label functions, reused verbatim, zero new label maps:** `inflationStateLabel` (`lib/inflationLabels.ts`), `laborStateLabel`/`employmentStateLabel`/`unemploymentStateLabel` (`lib/laborLabels.ts`) — each already returns the exact display string used everywhere else in the product ("Cooling," "Strengthening," "Expanding," "Deteriorating," "Insufficient data").

---

## §4. Canonical state-label handling — frozen

**Every state word in a composed sentence is the byte-identical output of the existing label function** — never re-cased, never abbreviated, never a new synonym. Where a state's label reads grammatically as an adjective/participle (`"Cooling"`, `"Strengthening"`, `"Expanding"`, `"Deteriorating"`, `"Stable"`, `"Mixed"`), it is embedded directly: "Inflation is Cooling." Capitalization is preserved exactly as the label function returns it (Title-Case-first-letter) rather than re-lowercased mid-sentence — reusing the label verbatim, unmodified, is a stricter, more conservative, and more easily-tested guarantee than introducing a second casing rule that could silently drift from the canonical label over time. `"Insufficient data"` is the one label that does **not** fit the "X is {label}" template grammatically (it is a noun phrase, not an adjective) — it is handled by a dedicated sentence fragment instead (§9), not by embedding the raw label into a broken sentence.

---

## §5. Overview surface — the job, and the heading

**Exact user question, frozen:** "How should I understand Inflation and Labor together right now?" — V1 may answer with composition only, never inference.

**Heading, frozen: "How They Relate."** Rejected: "Relate" alone (a bare verb, inconsistent with the noun-phrase shape of every existing Overview heading — "Current State," "What Changed," "Recent Data Updates," "Releases"); "Current Signals" (risks a trading/market-signal connotation this product explicitly and repeatedly avoids — no investment implication, anywhere); "Economic Relationship"/"Across the Economy" (both risk implying a deeper, possibly causal or statistical relationship than composition actually offers — exactly the overclaim §5's own instruction warns against); "Together" (too vague, reads like a UI label for something else). "How They Relate" directly answers the framed question, implies no causal/statistical analysis, and is legible to a beginner without any prior vocabulary.

---

## §6/§25. Overview content structure and duplication audit

**Structure (frozen):**

```
HOW THEY RELATE                                  (new <h2>)

  [composed sentence — §7/§8/§9]

  View Inflation →      View Labor →             (CTA, §15, reused verbatim)
```

**Duplication audit, per §25's explicit requirement:** Current State already shows both badges with their own periods and their own "Why" drill-downs — this surface must not merely restate that. **What the sentence adds that the two cards do not:** the two cards are read independently, in sequence; nothing on the page currently states the two facts *together*, in one sentence, with explicit honesty about whether they describe the same moment in time (§7/§8) or a different one. That synthesis — "these two facts, read together, as of these exact periods" — is new cognitive work the cards alone do not perform, and it is exactly, and only, composition (§2). This clears the duplication bar. It must **not** grow beyond one sentence plus the two existing CTAs — anything more (evidence tables, additional badges) would start duplicating Current State/monitor pages and is explicitly out of scope for V1.

---

## §7. Period alignment — same-period rule and template (frozen)

**Rule:** when `underlying_momentum.calculation_period === LaborMonitorResult.evaluation_period` (exact string equality on the ISO date), the sentence may use one shared, single period reference and the neutral conjunction "while" — safe here specifically because the periods genuinely do coincide, so no false contemporaneity is implied.

**Exact template:**
```
As of {Month Year}, Inflation is {InflationStateLabel} while Labor is {LaborStateLabel}.
```
Example: "As of July 2026, Inflation is Cooling while Labor is Strengthening."

---

## §8. Period alignment — different-period rule and template (frozen, mandatory)

**Rule:** when the two periods differ (or either is present while the other is absent for a reason other than insufficiency — not a real case per §3's structural coupling, but the rule is written to be safe regardless), the sentence **must never** use "while," "and," "meanwhile," or any other word implying simultaneity. Each fact gets its own independent, explicit period, in two separate sentences.

**Exact template:**
```
Inflation is {InflationStateLabel} as of {Month Year (Inflation)}. Labor is {LaborStateLabel} as of {Month Year (Labor)}.
```
Example: "Inflation is Cooling as of July 2026. Labor is Strengthening as of August 2026."

**"as of" is used uniformly in both templates** (§7 and §8), not the prompt's own sketch word "through" — verified against the actual data shape: `calculation_period`/`evaluation_period` are each a single anchor month, not a multi-month range (confirmed: `formatPeriod` converts one ISO date to one "Month Year" string). "Through July" would misleadingly suggest a window ending in July; "as of July" accurately describes a single-point classification anchor. This is a deliberate, evidence-grounded correction of the prompt's own illustrative sketch, not a deviation from its intent.

---

## §9. Insufficient-data behavior (frozen)

Verified structurally (`app/domain/inflation.py:281/291`, `app/domain/labor.py:343`): a `null` period always co-occurs with `INSUFFICIENT_DATA`, but the reverse does not always hold — a component can be individually `INSUFFICIENT_DATA` (e.g., Employment lacking enough consecutive required months) while `LaborMonitorResult.evaluation_period` is still non-null. **The frozen rule therefore branches on STATE, never on period presence** — robust regardless of the exact underlying coupling.

| Case | Behavior |
|---|---|
| Inflation `INSUFFICIENT_DATA`, Labor has a real state | No relationship sentence. Show Labor's own individual fact with its period (using the "X is {label} as of {period}" fragment from §8), plus: "Inflation does not currently have enough data to classify its state." — new wording for this fragment only, matching the established, already-shipped explanatory pattern for this exact condition (`content/explanations/inflation.ts`'s own `INSUFFICIENT_DATA` explanation: "does not have all the persisted observations required to calculate this state"), not an invented synonym |
| Labor `INSUFFICIENT_DATA`, Inflation has a real state | Mirror of the above, Labor's own explanatory fragment: "Labor does not currently have enough data to classify its state." |
| Both `INSUFFICIENT_DATA` | No relationship sentence and no per-side fragments either — one combined statement: "Not enough data is currently available to describe how Inflation and Labor relate." |

**No relationship word ("while," "as of... and as of...") is ever used when either side is insufficient** — composing a relationship out of one real state and one absent one would misrepresent what is actually known.

---

## §10. Resource failure vs. insufficient data (frozen)

**Distinct, never conflated.** `INSUFFICIENT_DATA` is a successful, canonical `200` response — a real economic-data-availability fact. A resource **error** (network/HTTP failure on `getInflationMonitor`/`getLaborMonitor`) is an infrastructure failure and must never be composed into any sentence, including the insufficient-data fragments in §9 (those require having successfully learned that a state is `INSUFFICIENT_DATA`; an error means the state was never learned at all).

| Case | Behavior |
|---|---|
| One resource errors, the other succeeds | No relationship sentence. Show the successful side's own individual fact (its own existing `ErrorMessage`-pattern ["Inflation/Labor data could not be loaded."] already established by `CurrentStateSection`/`WhatChangedPreview`), reused verbatim for the failed side, mirroring the exact failure-isolation discipline already proven for Current State — the working side is never blocked by the failed one |
| Both resources error | No relationship sentence, two existing error messages, exactly as Current State already does today |

---

## §11. Loading behavior (frozen)

**No composed sentence renders until both `getInflationMonitor` and `getLaborMonitor` have reached a terminal state (`success` or `error`) for that render.** While either is still `loading`, the section shows the existing `LoadingSkeleton` pattern (matching every other Overview section) — never a sentence built from one side's already-resolved state while the other is still pending, which would misrepresent a real relationship as known before it actually is.

---

## §12. "While" semantics — audited and settled

"While" is contrastive-simultaneous in ordinary English and does genuinely imply "at the same time" — safe **only** in §7's same-period case, where that implication is true. §8's different-period template deliberately avoids it (and avoids "and," "meanwhile," a semicolon-joined single clause, or any other construction that reads as one moment) by using two separate, independently period-stamped sentences. This fully resolves the prompt's own explicit audit question: "while" is retained, but only where it is literally accurate.

---

## §13. No agreement/divergence cross-domain (restated, frozen)

Already frozen in `docs/product/relate-compare-audit-v1.md` §16: "agree"/"diverge"/"confirm"/"contradict" are legitimate only for Core CPI vs. Core PCE (same type, same concept, same period) and, narrowly, for Employment vs. Unemployment via `LaborState`'s own existing table. **They are never legitimate for Inflation vs. Labor**, restated in §2's prohibited-vocabulary list above, regardless of whether the two states happen to look directionally similar in a given month.

---

## §14. No regime labels (restated, frozen)

Restated from §2 — absolute prohibition, no exceptions, until a separately-researched, versioned economic methodology exists (none does today, and none is created by this increment).

---

## §15. Overview CTA (frozen)

**"View Inflation →" / "View Labor →"**, reused verbatim from the existing, already-shipped, already-tested #22B convention (`components/overview/WhatChangedPreview.tsx`/`LaborWhatChangedPreview.tsx`/`RecentDataUpdates.tsx`, targets `/inflation`/`/labor`), not a new "Why Inflation?" label. This is the smallest-diff choice, reuses established route vocabulary exactly as instructed, and keeps every Overview section's "go deeper" action worded identically.

---

## §16. Labor internal surface — the job

**Exact user question, frozen:** "How are Employment and Unemployment contributing to the Labor state?"

Current `/labor` UI already shows: the top-level `LaborState` badge (Hero), Employment's own condition/momentum/state (its own section), Unemployment's own trend state (its own section), and — inside `WhyLaborState`'s existing disclosure — both component states plus the evaluation period, already side by side in a `<dl>`. **What the composition sentence adds:** none of the above currently states, in one sentence, that these two facts *combine into* the page's own Hero badge — the reader has to notice that connection themselves. Stating it explicitly is the added value, and it requires zero new methodology (see §19).

---

## §17. Labor shared-period verification (verified in production code, not assumed)

Verified directly, not assumed: `compute_employment_result(index, t, ...)` and `compute_unemployment_result(index, t, ...)` (`app/domain/labor.py:168`/`244`) both take the identical explicit parameter `t`, and `compute_labor_monitor_result_at` (`app/domain/labor.py:349`) calls both with the same `period` value. **Employment and Unemployment cannot diverge in period within one `LaborMonitorResult` — this is structurally guaranteed by the function signatures, not an assumption.** The composition sentence therefore needs only one period reference (Labor's own `evaluation_period`), never two.

---

## §18. Labor composition — exact template (frozen)

```
{Employment} is {EmploymentStateLabel} and {Unemployment} is {UnemploymentTrendStateLabel}.
```
Example: "Employment is Cooling and Unemployment is Deteriorating."

This is pure composition — two already-canonical facts, joined by the neutral "and" (safe here because both are guaranteed same-period, §17, unlike the cross-domain case). **No appended conclusion clause** ("...which is weakening the labor market") is added at this step — any such clause would be inference unless it is itself a verbatim report of an existing canonical value, which is handled separately in §19.

---

## §19. LaborState connection — audited and frozen

**Decision: permitted, with exact wording.** `LaborState` is not a new conclusion this sentence invents — it is the page's own existing Hero badge, already computed by the frozen `combine_labor_state` methodology (`app/domain/labor.py:288`, backed by `research/labor_momentum/LABOR_V1_FROZEN_METHODOLOGY.md`). Reporting it alongside its two inputs is composition, not inference — **provided the wording makes clear this is a report of an existing fact, not a conclusion this sentence is drawing**.

**Exact template (appended to §18):**
```
Employment is {EmploymentStateLabel} and Unemployment is {UnemploymentTrendStateLabel}. Together, Economic Intelligence classifies Labor as {LaborStateLabel}.
```
Example: "Employment is Cooling and Unemployment is Deteriorating. Together, Economic Intelligence classifies Labor as Cooling."

"classifies... as" is not invented phrasing — it is the exact verb pattern the product's own existing curated copy already uses for this identical concept (`content/explanations/labor.ts`'s `MIXED` explanation: "Economic Intelligence classifies that combination as Mixed"). Reusing it here is precedent-matching, not new vocabulary. **Deliberately not "canonical"** — confirmed absent from all user-facing copy today (`docs/product/product-experience-audit-v1.md` §13), and this sentence does not introduce it.

**Critical asymmetry with the Overview template (§7/§8), stated explicitly so #23C never conflates the two:** Labor's internal sentence may name a real, existing combined conclusion (`LaborState`) because one genuinely exists, computed by a real methodology. The Overview cross-domain sentence has **no such existing combined conclusion** to name — Inflation and Labor have never been combined into anything — and must never acquire one; inventing an analogous "Together, Economic Intelligence classifies the economy as X" for Overview would be exactly the forbidden regime label (§14). One pattern is safe because the fact it reports already exists; the other would be unsafe for the opposite reason.

---

## §20. Labor state combination matrix — explicit non-decision

No new matrix is created. `combine_labor_state`'s existing 4-cell-plus-`MIXED`-default table (`app/domain/labor.py:280`) is the sole source of the value reported in §19 — the frontend composition module never re-implements, re-derives, or extends it in any way; it only reads the already-computed `LaborMonitorResult.state` field.

---

## §21. Labor insufficient-data behavior (frozen)

| Case | Behavior |
|---|---|
| Employment `INSUFFICIENT_DATA` (Unemployment may or may not be) | No composed sentence. Fragment: "Employment does not currently have enough data to classify its state." (mirrors §9's pattern and existing precedent) |
| Unemployment `INSUFFICIENT_DATA` (Employment may or may not be) | Fragment: "Unemployment does not currently have enough data to classify its state." |
| Both sufficient but `LaborState` itself somehow `INSUFFICIENT_DATA` | Not a reachable case per `combine_labor_state`'s own logic (it returns `INSUFFICIENT_DATA` if *either* input is `INSUFFICIENT_DATA`, never otherwise) — no separate handling needed; this is fully subsumed by the two rows above |

No relationship — and no §19 `LaborState`-connection clause — is ever composed when either component is insufficient.

---

## §22. Labor placement (frozen)

**Not a new, 8th top-level section.** The composition sentence (§18/§19) is appended to the **existing** `WhyLaborState` disclosure (`components/labor/WhyLaborState.tsx`), directly after its existing evidence `<dl>` (Employment state / Unemployment trend / evaluation period) and its existing curated `definition`/`whyItMatters` text — not before. This directly resolves §16's own explicit "do not duplicate the top-level Labor methodology explanation unnecessarily" concern: `WhyLaborState` is already the page's existing "why is Labor in this state" surface; the composed sentence belongs there, not in a new section competing with it. The frozen 7-section `/labor` hierarchy (Current State → Employment → Unemployment → What Changed → Latest Data Detected → Relevant Release → Evidence & methodology) is **unchanged** — no new heading, no renumbering.

---

## §23. Overview placement (frozen)

**New position: Current State → How They Relate (new) → What Changed → Recent Data Updates → Releases.** "How They Relate" is a natural extension of "what is happening" (both are current-state questions), belongs immediately after Current State and before "what changed" (a different question class), and does not disturb the #22A/#22B attention hierarchy for What Changed/Recent Data Updates/Releases, which keep their existing relative order and their own already-frozen internal behavior untouched.

---

## §24. Labor interaction/CTA (frozen)

**No new interaction mechanism.** The composition sentence lives inside the already-existing, already-interactive `WhyLaborState` `<details>` disclosure — opening it (the existing "Why {LaborState}?" toggle) reveals the sentence alongside the evidence that already lives there. No new link, no new anchor, no new route. This is the smallest useful interaction, per the explicit instruction, and requires zero new routing mechanism.

---

## §25. Duplication audit — see §6 above (Overview) — Labor result

**Labor:** the composition sentence's only new cognitive work is naming the connection between the two component states and the Hero badge the reader has already seen — genuinely new synthesis, not a restatement of what `WhyLaborState`'s existing `<dl>` already shows numerically/categorically. Passes the duplication bar for the identical reason Overview's does (§6).

---

## §26. Beginner test (frozen requirement)

**Required answer is yes, and is met**: every template (§7/§8/§9/§18/§19/§21) uses only plain English connectives ("as of," "while," "and," "Together... classifies... as") and existing, already-beginner-tested state labels. No correlation, spread, regime theory, or statistical vocabulary appears anywhere in any template.

---

## §27. Expert verifiability (frozen requirement, clause-by-clause)

| Clause | Canonical source |
|---|---|
| Inflation state word | `InflationMonitorResult.underlying_momentum.state` |
| Inflation period | `InflationMonitorResult.underlying_momentum.calculation_period` |
| Labor state word | `LaborMonitorResult.state` |
| Labor period | `LaborMonitorResult.evaluation_period` |
| Employment state word | `LaborMonitorResult.employment.state` |
| Unemployment state word | `LaborMonitorResult.unemployment.state` |
| "classifies Labor as" clause | `LaborMonitorResult.state` (same field as row 3 — restated, not re-derived) |

No clause in any template lacks a named canonical source. No template performs, or implies, any calculation.

---

## §28. Revision disclosure (frozen: no new disclosure)

The Relate sentences introduce no new numeric evidence and no new data-vintage claim beyond what's already stated adjacent to them (`DataBasisNote` on Overview's own header, the existing evidence/methodology disclosures on `/labor`). Adding a second, duplicate "latest revised data" notice directly on the Relate sentence itself would be exactly the unnecessary clutter the instruction warns against. **No new disclosure text is added anywhere by this contract.**

---

## §29. Methodology / versioning decision (frozen)

**No new economic methodology, and no `relate_v1.0` methodology identifier.** Composition is not an economic conclusion and must not be versioned as though it were one — doing so would misleadingly place it alongside `inflation_v1.0`/`labor_v1.0`/`labor_what_changed_v1.0`, which are real, researched, frozen economic methodologies. #23C's implementation module is identified only by its own file/module name (`lib/relateComposition.ts`) — an ordinary software artifact, versioned (if at all) the same way every other frontend `lib/*.ts` module is, never as a methodology document.

---

## §30/§31. Template architecture — frozen

**`frontend/src/lib/relateComposition.ts`**, two pure, typed functions, no backend imports, no economic calculation, no score, no LLM:

```ts
composeMonitorRelation(
  inflation: { state: InflationState; period: string | null },
  labor: { state: LaborState; period: string | null },
): MonitorRelateComposition

composeLaborComponents(
  employment: EmploymentState,
  unemployment: UnemploymentTrendState,
  laborState: LaborState,
): LaborRelateComposition
```

**Structured output, not a bare string** (frozen per §31's own steer toward the smallest *testable* contract):

```ts
type MonitorRelateComposition =
  | { kind: "same-period"; sentence: string }
  | { kind: "different-period"; sentence: string }
  | { kind: "inflation-insufficient"; sentence: string }
  | { kind: "labor-insufficient"; sentence: string }
  | { kind: "both-insufficient"; sentence: string };

type LaborRelateComposition =
  | { kind: "composed"; sentence: string }
  | { kind: "employment-insufficient"; sentence: string }
  | { kind: "unemployment-insufficient"; sentence: string };
```

`kind` lets #23C's tests assert deterministic branch selection without brittle string-matching, while `sentence` is the one already-composed string the component renders directly — no template re-assembly in the component layer, no risk of a component silently reintroducing "while" in a different-period case. This is the smallest contract that is still fully unit-testable per case, not a generic templating framework.

---

## §32. Accessibility / responsive (frozen requirement)

The relationship sentence is a plain text node, readable start-to-end by a screen reader with no dependency on left/right card position (unlike the peer-card layout above it, which is spatial). No color is used to carry the state (already established product-wide convention — Labor carries no directional color at all; Inflation's cool/warm tones are reinforcement only, never the sole carrier — and this sentence carries the state as text regardless). No icon is required to understand any clause. This requirement is inherited from, not additional to, precedent already established throughout the product.

---

## §33. Test matrix — Overview (frozen)

- Same-period composition renders exactly the §7 template, both states correct
- Different-period composition renders exactly the §8 template, never "while"
- Inflation `INSUFFICIENT_DATA`, Labor sufficient → §9 row 1 exactly
- Labor `INSUFFICIENT_DATA`, Inflation sufficient → §9 row 2 exactly
- Both `INSUFFICIENT_DATA` → §9 row 3 exactly, no per-side fragments
- Inflation resource error → §10 row 1, Labor's own fact still renders, no relationship sentence
- Labor resource error → mirror
- Both resource errors → both existing error messages, no relationship sentence
- Either resource still loading → skeleton only, no partial sentence
- Both resolved (success) → composed sentence renders
- All five `InflationState` values render their exact existing label, never a raw enum string
- All five `LaborState` values render their exact existing label
- No cross-domain agreement/divergence word anywhere in any rendered output (regex-level assertion across all fixtures)
- No regime-label word anywhere in any rendered output
- Correct period(s) shown, correctly formatted, matching `formatPeriod`'s existing output exactly
- "View Inflation →"/"View Labor →" present, correct hrefs
- Semantics (which state belongs to which domain) survive with CSS/positioning stripped (jsdom text-content assertion, not a layout assertion)

## §34. Test matrix — Labor (frozen)

- Employment + Unemployment composition (§18) renders exactly, both sufficient
- All five `EmploymentState` values render their exact existing label
- All four `UnemploymentTrendState` values render their exact existing label
- `LaborState` displayed in the §19 clause is byte-identical to `LaborMonitorResult.state`'s own existing label, verified against the Hero badge already on the same page (a regression-style test: the composition's own state word must equal the Hero's)
- Shared period: no second period rendered in the composition (only one, per §17)
- Employment `INSUFFICIENT_DATA` → §21 row 1
- Unemployment `INSUFFICIENT_DATA` → §21 row 2
- No new combination matrix exists in the frontend module (structural/import-boundary guard, §35)
- No inference clause beyond the verbatim `LaborState` report (regex/string guard for forbidden vocabulary, same list as §33)
- Existing evidence (`EvidenceDisclosure`, observation tables) remains the unmodified source of truth — this sentence never replaces or summarizes it away

**Explicit exhaustiveness note, per instruction:** rather than Cartesian-testing all `5 × 4 = 20` `(EmploymentState, UnemploymentTrendState)` pairs, #23C should prove exhaustiveness at the type level (the function signature accepts only the closed union) plus one test per individual state value on each side (covering label correctness) plus the four cases above (covering branch logic) — the composition function has no per-pair branching logic of its own to Cartesian-test (see §20: it only reads `LaborState`, never re-derives it from the pair).

---

## §35. Architecture guards (frozen)

A new guard test (extending `frontend/src/test/no-economic-logic.test.ts`'s established pattern) must prove `lib/relateComposition.ts` (and any component consuming it) contains none of: `Goldilocks`, `stagflation`, `soft landing`, `hard landing`, `bullish`, `bearish`, `risk-on`, `risk-off` (bare-word patterns are acceptable here specifically because these are invented regime-label terms with no legitimate reason to appear anywhere in this module's own code or comments, unlike #22B's own "bullish"/"bearish" near-miss, which occurred in *unrelated* files' correct prose explaining their absence — a risk this new module does not share, since it has no reason to discuss regime labels at all, correctly or otherwise); a cross-domain agreement/divergence word (`agrees`, `confirms`, `diverges`, `contradicts`) used on Inflation/Labor values specifically; any correlation/spread identifier; any numeric threshold comparison (mirroring the existing deadband-comparison guard shape); no import from `app/` or any backend path; no import of an AI/LLM module; no new backend endpoint call (extending `no-overview-mutation.test.ts`'s "exactly N documented read functions" count only if #23C adds a genuinely new *existing* call — none is expected, since both monitors are already fetched); no new `methodology_id`-shaped string literal resembling `relate_v1.0` or similar (per §29).

---

## §36. #23C scope (frozen)

**Frontend-only.** In scope: `lib/relateComposition.ts` + its own unit test file; a new `components/overview/HowTheyRelate.tsx` (or equivalently named) section component; one small extension to `components/labor/WhyLaborState.tsx`; `pages/Overview.tsx` wiring (new section between Current State and What Changed, no new `useApiResource` call — reuses the two already-fetched monitor resources); `Overview.test.tsx` extensions (heading-sequence array gains one entry) and `Labor.test.tsx` extensions; the new architecture guard (§35). **Expected: zero backend production changes, zero backend test changes, zero migrations, zero new route, zero new top-level nav item** — confirmed achievable, since every input this contract needs (`state`, `calculation_period`/`evaluation_period`, component states) is already present on `InflationMonitorResult`/`LaborMonitorResult` as fetched today by `pages/Overview.tsx` and `pages/Labor.tsx`.

---

## §37. Explicit deferrals (restated from #23A, unchanged)

Series Compare UI (open or curated), charts, correlation/spread display, cross-domain labels, historical relationships, lead-lag, causal inference, investment implications, AI narration, a new economic domain, state-history persistence. None of these are touched, enabled, or brought closer by this contract.

---

## §38. GO / STOP checklist

| # | Item | Status |
|---|---|---|
| 1 | Composition/inference boundary exact | ✅ §2 |
| 2 | Same-period template frozen | ✅ §7 |
| 3 | Different-period template frozen | ✅ §8 |
| 4 | Missing-period behavior frozen | ✅ §9 (subsumed by state-branching, verified structurally) |
| 5 | Insufficient behavior frozen | ✅ §9, §21 |
| 6 | Resource failure behavior frozen | ✅ §10 |
| 7 | Loading behavior frozen | ✅ §11 |
| 8 | Cross-domain vocabulary safe | ✅ §2, §13 |
| 9 | Overview placement frozen | ✅ §23 |
| 10 | Overview CTA frozen | ✅ §15 |
| 11 | Labor shared-period behavior verified | ✅ §17, verified in production code |
| 12 | Labor composition frozen | ✅ §18 |
| 13 | LaborState connection frozen | ✅ §19 |
| 14 | Labor placement frozen | ✅ §22 |
| 15 | Duplication concern resolved | ✅ §6, §25 |
| 16 | Revision disclosure frozen | ✅ §28 (none needed) |
| 17 | No new economic methodology needed | ✅ §29, confirmed for every template |
| 18 | Frontend architecture frozen | ✅ §30/§31 |
| 19 | Test matrix complete | ✅ §33/§34 |
| 20 | #23C frontend-only scope feasible | ✅ §36 |

All twenty resolved. No sentence in this contract requires new economic interpretation — every clause traces to an existing canonical field (§27), and the one clause that reports a combined conclusion (§19) reports a conclusion that already existed before this contract, never one this contract invents.

---

## Appendix: secret safety and version control

No `.env`/`.env.*`/credential file was read, printed, or logged at any point this increment. Nothing in this document was committed or pushed; the working tree outside this new file was not modified.
