# Historical Context & State History — Product, Data & Architecture Audit — V1

**Increment #24A.** Audit only. No production code changed. Baseline: HEAD `6d35957` ("Add deterministic Relate V1 composition" — #23C), clean working tree. Frontend: 895/895 passed. Backend: 1,173/1,173 passed, 0 skipped, against the established local isolated-Postgres mechanism.

---

## §1. Authoritative inputs

`docs/product/product-experience-audit-v1.md`, `docs/product/relate-compare-audit-v1.md`, `docs/product/relate-composition-v1.md` read in full; `docs/architecture/current-architecture.md`, `docs/architecture/request-flows.md`, `docs/ENGINEERING_JOURNAL.md` inspected for the release-processing/persistence/revision-handling sections specifically. Backend persistence (`app/db/models.py`), the release-processing write path (`app/repositories/release_processing_repository.py`), the plain series-sync write path (`app/repositories/series_repository.py`), and both domains' `_at`-suffixed period-explicit functions (`app/domain/inflation.py`, `app/domain/labor.py`) were inspected fresh, in full, this turn — not from memory.

---

## §2. Historical question taxonomy (frozen vocabulary)

| Class | Example | Status |
|---|---|---|
| **A. Historical raw observation** | "What is today's revised value for CPI in Jan 2024?" | **Supported now** — `EconomicObservation` persists it; `/series/{id}/observations` already exposes it generically |
| **B. Historical derived metric** | "Using today's revised history, what was Core PCE 3M annualized at Jan 2024?" | **Reconstructable now** — `compute_series_momentum_at` already exists and takes an explicit period |
| **C. Historical reconstructed canonical state** | "Using today's data and `labor_v1.0`, what does Jan 2024 reconstruct to?" | **Reconstructable now** — both domains have `_at`-suffixed pure functions taking an explicit period |
| **D. Recorded EI state** | "What state did EI actually report on Jan 2024?" | **Partially supported, sparse and incomplete** — only reconstructable from `ReleaseAnalysisUpdate`'s change-only, manually-triggered audit trail (§5) |
| **E. As-known-at-time state** | "What would EI have concluded using only data available as of Jan 2024?" | **Requires new architecture (vintage data)** — not achievable at all today (§15) |
| **F. State duration / transition history** | "How long has Inflation been COOLING?" | **Reconstructable now**, with a mandatory reconstruction qualifier (§11) |
| **G. Historical distribution / relative position** | "Is today's value historically high?" | **Reconstructable now for the raw numbers; needs its own small statistical contract (window, percentile method) before exposing as "high/low"** (§17/§18) |
| **H. Historical outcome / regime analysis** | "What usually happened after this combination?" | **Not ready** — requires empirical validation, state-history persistence, look-ahead-bias controls (unchanged from #23A's own finding) |
| **I. Since-last-visit** | "What changed since I last checked?" | **Requires new architecture** (client-local timestamp at minimum; server persistence for anything cross-device) (§29) |

---

## §3. Current persistence inventory (inspected fresh, exact)

| Table | Append-only or mutable? | Carries before/after? | Carries monitor state? |
|---|---|---|---|
| `EconomicSeries` | Mutable (`updated_at` on change) | No | No |
| `EconomicObservation` | **Mutable, in-place overwrite** (`UniqueConstraint(economic_series_id, observation_date)`, no `updated_at` column at all) | **No** | No |
| `EconomicRelease` | Mutable | No | No |
| `ReleaseOccurrence` | Mutable (`first_seen_at`/`last_seen_at`) | No | No |
| `ReleaseSeriesMapping` | Mutable (`active` toggle) | No | No |
| `ReleaseCheckRun` | **Append-only** (a retry creates a new row) | No (records only `status`/`started_at`/`completed_at`) | No |
| `ReleaseObservationUpdate` | **Append-only**, but only written for a detected NEW/REVISED change during a release-processing check | **Yes** (`previous_value`/`new_value`) | No |
| `ReleaseAnalysisUpdate` | **Append-only**, but only written for a detected canonical-fact change during a release-processing check | **Yes** (`previous_value`/`current_value`, both as `String`) | **Only the specific field that changed**, not a full snapshot — `component`/`field`/`evaluation_period`/`methodology_id`/`data_basis` are all present per row |

**What does NOT exist, confirmed by full-file inspection:** any table storing a complete, regular, or scheduled snapshot of `InflationMonitorResult`/`LaborMonitorResult` at any cadence. The closest thing is `ReleaseAnalysisUpdate`'s sparse, change-only trail (§5).

---

## §4. Observation revision semantics (proven, not inferred)

Two write paths, both inspected directly:

- **Release-processing path** (`ReleaseProcessingRepository.write_observation`, `app/repositories/release_processing_repository.py:100`): `existing.value = value` — a hard in-place mutation. The prior value is preserved **only** in a sibling `ReleaseObservationUpdate` row, written by the *caller* (the service layer), never by this method itself, and only when the caller had already classified the write as NEW/REVISED (an UNCHANGED value is never passed here at all).
- **Plain sync path** (`SeriesRepository._upsert_observations`, `app/repositories/series_repository.py:189`): the identical `existing.value = observation.value` mutation, but with **zero audit trail of any kind** — no `ReleaseObservationUpdate` row, no `ReleaseAnalysisUpdate` row, nothing. A revision synced through `POST /series/{id}/sync` (the generic, non-release-driven sync endpoint) is silently, permanently overwritten with no record the old value ever existed.

**Conclusion: revision history is real but not comprehensive.** It exists only for the subset of observations that were (a) mapped to a curated release (`ReleaseSeriesMapping`) and (b) touched through the release-processing CLI (`python -m app.operations.process_release`) specifically, which is manual/operational-only — confirmed by every prior increment's own documentation, no scheduler exists. A revision to an unmapped series, or to a mapped series synced via the plain endpoint instead, leaves no trace.

---

## §5. Release-history capability (precise)

Reconstructing from `ReleaseCheckRun`/`ReleaseObservationUpdate`/`ReleaseAnalysisUpdate` can answer: "on this specific date, a manual check ran, and this specific canonical fact changed from A to B." It **cannot** answer, on its own:

- **"Can we reconstruct every past monitor state?"** No — only the states that happen to bracket a *detected change*. A month where nothing changed produces zero rows in `ReleaseAnalysisUpdate` (by design — "a check run producing zero analytical consequences... simply has zero rows here, never a synthetic 'no change' row," the model's own docstring) — so the trail cannot distinguish "nothing changed because I never checked" from "nothing changed because I checked and confirmed."
- **"Can we know a monitor stayed unchanged?"** Only indirectly, and only for periods with an actual `ReleaseCheckRun` of status `NO_CHANGE` — and even that only tells you the *mapped source observations* didn't change, not that the canonical *monitor* state was re-verified (a `NO_CHANGE` observation check never even calls into the Inflation/Labor domain layer — confirmed by `app/services/release_processing.py`'s own branching, which only computes before/after monitor evidence when a change was actually detected).
- **"Can we know what happened before release processing existed?"** No — `ReleaseCheckRun`'s own rows only exist from Increment #18 onward; there is no retroactive backfill.
- **"Can retries create ambiguity?"** No — confirmed safe by design: a retry creates a new `ReleaseCheckRun` row, but `ReleaseObservationUpdate`/`ReleaseAnalysisUpdate` are keyed to detected changes within that specific run, and (per `app/repositories/release_processing_repository.py`'s own unique constraints) a repeat check against unchanged data produces no duplicate audit rows.
- **"Can a same-period revision be reconstructed?"** Yes, for the audit trail's own purposes — `ReleaseAnalysisUpdate.evaluation_period` records the exact period a change applied to, and multiple revisions to the same period across different check runs each get their own row, in order.
- **"Does `ReleaseAnalysisUpdate` preserve enough before/after evidence?"** For the *specific field* it records (state/condition/momentum/metric), yes, with exact values. It is explicitly, by design, **not** a full monitor snapshot — no adjacent fields that didn't change are recorded alongside it.

**Bottom line: this is a real, honest, working change-detection audit log — never a state-history table, and was never intended to be one** (`ReleaseAnalysisUpdate`'s own docstring: "NOT a full `InflationMonitorResult` snapshot, and never arbitrary JSON").

---

## §6. Inflation historical computability

`compute_series_momentum_at(observations, series_id, calculation_period, neutral_band_pp)` (`app/domain/inflation.py:364`) already exists, already takes an **explicit** period (never searched), and is already the exact primitive `inflation_what_changed_v1.0`'s own comparator uses to evaluate two explicit periods. It requires, as input, every persisted observation for that series (it internally computes 1M/3M/6M/12M windows, so at minimum 13 months of history ending at the target period, more if computing a sequence). **No new domain logic is required** to compute Core PCE's (or any of the four canonical series') state at an arbitrary past month — only a new service-level orchestration (call this function once per month of interest) and a new API surface to expose it, neither of which exist today. Confirmation's own shared-period logic and Headline PCE/CPI's independent tracks all reuse this same primitive, so a full historical `InflationMonitorResult` reconstruction is mechanically the same shape as the current one, just parameterized by period instead of "latest."

---

## §7. Labor historical computability

Identically, `compute_labor_monitor_result_at` (verified in earlier increments' own inspection of `app/domain/labor.py:349`, re-confirmed present) takes an explicit `period` and computes Employment/Unemployment/Labor state at it. Two Labor-specific complications, both already correctly handled by the existing frozen methodology, not new problems this audit introduces: PAYEMS benchmark/monthly revisions propagate through a sparse, non-contiguous set of affected horizons (`{0,3,6}` months forward from a revision, per `labor_release_processing.py`'s own frozen constants) rather than uniformly, and UNRATE depends on a prior-year window (`t-12` through `t-14`), so a historical UNRATE reconstruction at month `t` requires observations reaching back a full 14+ months from `t`, not just 3. Both are already correctly implemented in the existing domain functions — reconstruction reuses them unmodified.

---

## §8. Reconstruction terminology (frozen recommendation)

**A value computed today, from today's persisted observations, at a past `evaluation_period`, is a "latest-revised reconstruction" — never "the state in {period}" without that qualifier, and never "what EI said" or "what EI knew."** This is not a new invention — it is the direct extension of the exact distinction the product's own existing disclosure already draws for *current* calculations ("Historical calculations use the latest revised observations available to Economic Intelligence"), now applied to a *state*, not just a metric value. The qualifier must be load-bearing in the UI, not a footnote — see §38.

---

## §9. Methodology-version problem — audited, not solved

Today there is exactly one version of each methodology (`methodology_id` is a plain constant, `"inflation_v1.0"`/`"labor_v1.0"`, everywhere it appears — monitor results, What Changed results, and every `ReleaseAnalysisUpdate` row). The three-way ambiguity the prompt raises (reconstruct with current methodology vs. the historical methodology vs. report what was actually classified at the time) is **real but latent** — it cannot manifest until a second methodology version ships. **Requirement for any future historical-state architecture, frozen here as a constraint, not a design**: any persisted or computed historical state must carry its own `methodology_id` explicitly, never assume "current" implicitly. This is already trivially satisfiable — every relevant response contract already carries `methodology_id` as a field — the requirement is behavioral discipline (never drop it), not new schema.

---

## §10. Inflation-specific historical findings

Calendar dependencies: r_12m needs 12 prior months, r_6m/r_3m need less, all anchored at the SAME `calculation_period` per series. Missing-data behavior at any past month falls back to `classify_period`'s own existing `INSUFFICIENT_DATA` handling — no new missing-data logic needed. Confirmation's shared period (`latest_shared_observation_period`) is itself computed relative to whatever period is being evaluated, so a full historical Confirmation reconstruction is possible but requires computing it at each historical point, not just reading a single "latest" value. Headline PCE/CPI track independently and could show different historical periods available than Core PCE at the same calendar month, exactly as they can today. Methodology version: one, stable. Revision limitation: any reconstruction is latest-revised, per §8. **Honestly answerable today, if built:** "was Core PCE's reconstructed momentum COOLING at any given past month," "how has reconstructed 3M/6M/12M moved over the last N months," "how long has the reconstructed state held."

---

## §11. Labor-specific historical findings

PAYEMS benchmark revisions (the annual, larger revision FRED periodically applies) and ordinary monthly revisions both propagate through the same sparse `{0,3,6}` horizon logic already frozen and tested — a historical Labor reconstruction inherits this correctly by construction, no new propagation logic needed. UNRATE's prior-year dependency means Labor reconstructions further back in history need proportionally more preceding observations loaded. Shared evaluation period: verified structurally in #23C's own audit (`compute_employment_result`/`compute_unemployment_result` share the identical explicit period parameter) — still true, unchanged, and directly reusable for historical reconstruction (one period parameter drives both components at any past month, exactly as it does today). **Honestly answerable today, if built:** the Labor-equivalent of §10's list, plus (uniquely to Labor) a reconstructed Employment/Unemployment agreement history, reusing the exact same composition pattern #23C already shipped for the current period.

---

## §12. "Since when?" — reconstructed vs. recorded, and why they can disagree

Two genuinely different sources, both real:

- **(A) Reconstruct a monthly state sequence** by calling the `_at` functions at each preceding month until the state differs from today's — always available, always complete (bounded only by how far back observations exist), always latest-revised.
- **(B) Use the recorded `ReleaseAnalysisUpdate` history** — only tells you when a *detected, manually-checked* change happened to occur, with real gaps wherever the CLI wasn't run or a mapped series wasn't involved.

**They can disagree, and the reason is precise, not hypothetical:** (A) reflects today's revised data reapplied uniformly across history — if a revision changed which month a state transition "really" happened at, (A) reflects that corrected transition point immediately. (B) reflects whatever was true (or was checked) *at the time each historical check ran*, using whatever data existed then — it can show an older, now-superseded transition date, or show no transition at all in a stretch that was never checked. **"How long has this state lasted?" answered via (A) is a reconstruction claim ("under today's data, this state has held continuously since X"); answered via (B) is a much weaker, gappy claim ("EI's own manual checks detected a change most recently on X, but earlier periods were not all checked").** A V1 feature must pick one source, name it accurately, and never blend them into one number.

---

## §13. State-history persistence — verdict

**Valuable, but only going forward, and only for a purpose §12(B) cannot retroactively provide.** Persisting nothing today does not block the reconstruction-based features in §2's classes B/C/F (all computable on demand from what's already persisted). It **does** block: an accurate, gap-free "what EI actually reported" record; since-last-visit across devices; genuine notifications on state transitions; future historical-outcome research requiring a real "what was known when" trail. **Recommend planning for forward-only snapshot persistence as a distinct, later increment — not required for, and should not block, the V1 recommended in §41.**

---

## §14. Minimum snapshot semantics (described, not schema'd)

If forward persistence is later built, the smallest useful object is an **EVALUATION SNAPSHOT**: identity = `(monitor, evaluation_period, methodology_id)`; payload = the canonical state plus enough evidence to explain it, plus `data_basis` and a `calculated_at` timestamp recording when *this row* was written (distinct from the economic `evaluation_period` it describes). This single semantic object can serve "what EI reported" (query by monitor+period, ordered by `calculated_at`, take the first — the earliest real report for that period), state-duration-as-recorded (§12(B), now gap-aware since a written row proves a check occurred), and (with a viewer-side timestamp compared client-locally) since-last-visit. The prompt's own OBSERVATION-TIME and USER-VIEW snapshot variants are **not separately needed** — OBSERVATION-TIME is exactly what `calculated_at` already captures on the one object above; USER-VIEW is a client-local concern, not a server snapshot type at all. RELEASE-UPDATE SNAPSHOT already exists today, unchanged, as `ReleaseAnalysisUpdate` — no new type needed for that purpose.

---

## §15. As-known-at-time requirement — audited, confirmed not achievable

Would require: vintage (as-originally-published) observation values, not just latest-revised ones; provider publication timestamps per vintage; the ability to answer "which vintage would have been the latest available as of date X." **None of this exists in the current FRED integration** — `FREDClient` fetches current, latest-revised series values only; there is no ALFRED (FRED's own vintage-data service) integration anywhere in this codebase, confirmed by inspecting `app/clients/fred.py`'s own call surface (`get_observations`, `get_release_dates`, `search_series` — no vintage-dated variant of any of them). This class of question is **not answerable today at any reconstruction fidelity** — it requires a genuinely new provider integration, explicitly out of scope for this audit to design and explicitly not recommended to build now (§47).

---

## §16. Latest-revised historical context — real value, not dismissed

Explicitly not assumed useless: a reconstructed trend, a reconstructed state sequence, and "is today's reading higher/lower than N months ago" are all honest, real, valuable answers *as long as they are correctly labeled as latest-revised reconstructions*. The product's own existing precedent (every current monitor result is already a latest-revised calculation, clearly disclosed) is direct evidence this framing works in practice — users are not confused by "the latest-revised current state," and the same clarity extends to "the latest-revised reconstructed history."

---

## §17. Historical metric-context — statistical/product safety

A raw number (current value, 5-year median, min/max, current minus median) requires no new methodology — it is arithmetic over already-computed values, using existing transform-style primitives. A **percentile** requires a small, explicit, frozen statistical contract: window length (how many years back), sample construction (monthly reconstructed values, computed how), and tie-handling — none of which exist today and none of which should be improvised inside a UI component. This is a real, if small, "STATISTICAL METHOD REQUIRED" item (§43), not a "no new methodology" one — smaller than Compare's own correlation-safety problem (#23A §4), but not zero.

---

## §18. "Unusual"/"high"/"low" language — boundary

**"82nd percentile over the reconstructed latest-revised 10-year history" is a safe, fully-attributable, composition-shaped statement** — every word traces to a defined, disclosed computation, exactly the same discipline #23C's Relate sentences already use. **"Unusually high" is not safe without a separately frozen threshold** (what percentile counts as "unusual"? that is an interpretive line this project has never drawn, and drawing it now would be exactly the kind of ungrounded interpretive threshold `no-economic-logic.test.ts`'s own guards exist to catch). Frozen boundary: report the number and its defined statistical position; never translate that position into a qualitative label without a dedicated, separately-frozen methodology decision.

---

## §19. Chart analysis — deferred, audited only per instruction

A monitor-state timeline chart, a metric line chart, state-band shading, and revision markers all answer real questions, but every one of them **visually risks implying more certainty or more contemporaneous knowledge than a reconstruction actually carries** unless labeling is unusually disciplined (a chart's own visual authority tends to read as "this is what happened," not "this is what today's data implies happened," in a way plain text does not). A latest-revised reconstruction *could* be charted safely with sufficiently prominent, persistent labeling, but this project has no charting library today (confirmed absent, per every prior audit), and introducing one is explicitly out of scope for this increment and for the recommended V1 (§41). Defer entirely; text-first is safer and is already this product's established idiom.

---

## §20. State timeline — reconstructed vs. recorded, terminology requirement

A rendered "Jan COOLING / Feb COOLING / Mar STABLE / Apr HEATING" table is useful but is a **bigger surface than V1 needs** and inherits every §12 ambiguity at once, multiplied across every row. If built later, each row must be legible as either purely reconstructed (computed now, from now's data) or purely recorded (drawn from a durable snapshot with its own `calculated_at`) — never silently mixed. Not recommended for V1 (§41); the smaller state-duration fact (§11 of the source prompt) captures most of the same value with a fraction of the surface and ambiguity.

---

## §21. Metric trend — audited as the alternative smallest V1

Existing domain computation is sufficient (§6/§7); API requirement is a new, thin endpoint or query parameter accepting a date range and returning a list of already-computed metric values; frontend requirement is a simple list/line of numbers (no new label maps); revision disclosure reuses the existing sentence near-verbatim (§16); missing data at any historical point falls back to existing `INSUFFICIENT_DATA`-shaped handling. **This is the safer, smaller sibling to state duration** — considered seriously as the primary V1 candidate, ultimately ranked second (§41) because it answers a narrower, less-often-asked question than "since when" per the prompt's own framing, while costing almost the same to build.

---

## §22. Transition timeline — same reconstructed/recorded split as §20

A list of "COOLING → MIXED, MIXED → HEATING" transitions can be derived either from walking the same reconstructed monthly sequence (§20's data, filtered to just the months where state changed) or from `ReleaseAnalysisUpdate`'s own recorded, gappy trail. Same terminology discipline applies. Not recommended as its own V1 surface — it is a natural, cheap *future* extension of the state-duration walk-back this audit does recommend (§41), once that exists, not a separate feature to build first.

---

## §23. Release revision markers — audited, deferred

"July payrolls revised by −X" is answerable today from `ReleaseObservationUpdate` for series that were touched through release processing (§4/§5) — real, honest, but incomplete coverage (only mapped series, only CLI-triggered checks) makes it a poor candidate to surface prominently as if it were a complete revision history. Valuable as a *future* companion to a real state/metric timeline, not as V1 on its own.

---

## §24. Current API readiness

| Capability | Exists today | Gap |
|---|---|---|
| Raw historical observations | `GET /series/{id}/observations` | Not monitor-scoped (caller must know the right FRED series ID) |
| Transform | `GET /series/{id}/transform` | Only 3 transform types, none produce a monitor-methodology metric directly |
| Pipeline | `POST /analysis/pipeline` | Two-series only, no monitor-state concept |
| Monitor (current) | `GET /monitors/inflation`/`/labor` | No period parameter — always "latest" |
| What Changed (current comparison) | `GET /monitors/*/changes` | Exactly two periods, never a range/series |
| Release processing status | `GET /releases/processing-status` | Sparse, change-only, as documented (§5) |
| **Metric history** | **Missing entirely** | New endpoint or query-param extension required |
| **Reconstructed monitor history** | **Missing entirely** | New endpoint required; underlying domain functions already exist (§6/§7) |
| **Recorded monitor history** | **Missing entirely** (only reconstructable, sparsely, from existing release-processing tables) | New read-service required over existing tables — no new persistence needed for what little recorded history already exists |
| **Transition history** | **Missing entirely** | Derived from whichever of the above is built first |

---

## §25. Frontend placement readiness (inspected, not modified)

`/inflation` and `/labor` each already have an established progressive-disclosure slot (`WhyThisState`/`WhyLaborState`) that #23C already extended once for exactly this kind of "additional composed context" purpose. A small historical-context addition (state duration, or a compact metric-trend line) fits naturally as a further extension of that same disclosure, or as one small new subsection near the Hero badge — not a new page, not a new route. A full History section or standalone route would be justified only once the surface grows past what a disclosure can hold (matching the exact reasoning that kept Relate out of a new `/relate` route in #23B).

---

## §26. Overview historical context — verdict

**Does not belong on Overview V1.** Overview's own job (proven repeatedly, `overview-attention-model-v1.md`) is a sub-minute answer to "what is happening" and "what changed" — a reconstruction-qualified duration clause ("Inflation has been COOLING for a reconstructed 3 months") adds real value but also real reading load and a new disclosure burden to the one page explicitly optimized against clutter. State duration belongs on the monitor pages, exactly where Relate's own richer Labor content already lives (§25).

---

## §27. Inflation user journeys

| Journey | Answerable now? | Semantics | Architecture needed |
|---|---|---|---|
| A. "COOLING. Since when?" | Reconstructable, not yet built | Reconstructed duration | New service + endpoint, no new domain logic |
| B. "Is 3M lower than six months ago?" | Reconstructable, not yet built | Reconstructed metric comparison | Same as A |
| C. "How has momentum changed this year?" | Reconstructable, not yet built | Reconstructed metric trend | Same as A |
| D. "Was EI calling it COOLING in January?" | **Not honestly answerable today** except sparsely via §5's recorded trail | Recorded (gappy) vs. reconstructed (smooth, but not "what EI said") | Recorded: read-service over existing tables, honest about gaps. Reconstructed: same as A, but must never be presented as an answer to this specific question |

---

## §28. Labor user journeys

Structurally identical to §27, substituting Labor's own domain functions; D's answer is, if anything, sparser for Labor than Inflation, since Labor's own release-processing integration (#20D.2) is newer and has had less real-world manual-check history accumulate.

---

## §29. Since-last-visit requirements

Requires, at minimum: a per-viewer timestamp (client-local `localStorage` is sufficient for a single-device version, requiring no accounts); comparison against *something* recorded — either §14's future snapshot object, or (a weaker, still-honest version) reusing already-existing `ReleaseAnalysisUpdate`/`ReleaseCheckRun` timestamps to say "N changes were detected since {last-visit timestamp}," which is buildable **today**, with no new persistence, entirely from existing release-processing history, scoped honestly to "detected changes," not "everything that changed." A cross-device version requires real accounts, explicitly out of scope. **Recommendation: state-history work should keep this future use case in mind (favor a design where a snapshot's `calculated_at` is queryable by range) but does not need to build it now, and a client-local, existing-data-only version is plausible as an even smaller future increment independent of state-history persistence entirely.**

---

## §30. Notification / monitoring implications

"Tell me when Inflation changes state" needs a REAL trigger, and release processing is manual today (confirmed again, unchanged from every prior increment's own documentation — no scheduler, no cron, no authentication for any write path). State-history persistence (§13) would make a transition *detectable* the next time the monitor is evaluated, but does not itself create the trigger to evaluate it regularly or the delivery mechanism to notify anyone. **This is explicitly two separate future problems** (a scheduler/operational concern, and a notification-delivery concern), neither solved by, nor a prerequisite for, this audit's own V1 recommendation.

---

## §31. Historical Context vs. Curated Compare

| Dimension | Historical Context (State Duration V1) | Curated Compare (#23A runner-up) |
|---|---|---|
| Strengthens current loop | Directly — extends Monitor/Investigate with a "how long" answer nothing today provides | Adds a new, separate capability (Compare) rather than deepening the existing loop |
| Differentiation | High — a maintained, methodology-defined reconstruction FRED/generic-AI cannot reproduce reliably (§33/§34) | Lower — reuses existing correlation math directly; #23A already found this reads as "prettier FRED" without more work |
| Semantic risk | Low, if terminology (§8) is held strictly | Low for a pre-vetted pair, but the underlying correlation-on-levels risk (#23A §4) still requires its own disclosure discipline |
| Architecture reuse | High — zero new domain logic, reuses existing `_at` functions unmodified | High — reuses existing `/analysis/compare` endpoint unmodified |
| Willingness to pay | Real — "how long has this been true" is a genuinely hard thing to self-maintain, directly serving the product's own "without maintaining your own spreadsheet" positioning | Real but smaller — FRED usability, not new intelligence |
| Compounding moat | **High, specifically for the future recorded-history half (§35)** | Low — correlation is recomputed fresh every time, nothing compounds |

**Recommendation: Historical Context (State Duration) ranks above Curated Compare** on every dimension except pure implementation simplicity (both are comparably simple). Curated Compare remains the runner-up (§50).

---

## §32. Historical Context vs. Growth

Re-evaluated, not assumed: #21's own depth-before-breadth finding was that Overview's noise problem would *worsen* with a third domain before it was fixed — that specific problem is now fixed (#22B). The question is genuinely re-open. But the evidence gathered *this* audit still favors depth: Growth would need an entirely new domain methodology (real research, a new frozen contract, new backend work, new frontend work) before it could even reach parity with what Inflation/Labor already have — whereas Historical Context adds real, high-value depth to the two existing domains using data and domain logic that **already exist**, at a fraction of the cost. **Growth remains lower priority than deepening Inflation/Labor further.**

---

## §33. FRED differentiation

FRED already provides historical charts — so "EI has history too" is not differentiation by itself, exactly as the prompt anticipates. What EI could add above FRED: a **methodology-defined reconstructed state** (FRED shows numbers; it does not classify COOLING/HEATING/STRENGTHENING for any period, past or present), a **state-duration answer** (FRED requires the user to eyeball a chart and decide for themselves when a trend "started"), and — once §13's forward persistence exists — **recorded, non-reconstructable history** FRED can never retroactively offer at all, for any user, ever (§35).

---

## §34. Generic-AI differentiation

Current, delivered capability only: a reconstructed historical state or duration, if built, would carry the exact same reproducibility/versioned-methodology/exact-evidence guarantees every other canonical EI result already carries (#21 §15's own finding, inherited automatically) — generic AI cannot reliably reproduce a specific, versioned, re-runnable classification for an arbitrary past month. This is a *current-capability* claim once §41's V1 ships, not an aspirational one.

---

## §35. Moat analysis — the key distinction

**Raw historical data copied from FRED is not proprietary — anyone can fetch it.** A *reconstruction* computed from that public data, using EI's own public-ish methodology, is also not secret and could in principle be reproduced by a sufficiently motivated third party. **What genuinely cannot be reproduced by anyone, ever, after the fact, is a RECORDED snapshot of what a monitoring system concluded in real time, before later revisions occurred.** This is the one clause in this entire audit that identifies a truly compounding, non-reproducible asset: every day EI does *not* start recording durable evaluation snapshots (§14) is a day of that asset that can never be retroactively created. Reconstruction (available today, no new persistence) has real user value but is not itself the moat; the moat is the *recording*, which requires the persistence work explicitly deferred past V1 (§13).

---

## §36. Minimum useful historical V1 — decision

Weighed against truthfulness, user value, differentiation, architecture reuse, and future compounding value (not visual impressiveness, per instruction): **State Duration** (candidate A) — a single, reconstructed fact ("Inflation has been Cooling for a reconstructed 3 months") — ranks highest. It directly answers the prompt's own named highest-value question, costs almost exactly what the smaller Metric Trend (candidate C) costs to build, requires no new statistical contract (unlike candidate D), no new persistence (unlike candidate E's fuller ambitions), and sets up, rather than forecloses, the future recorded-history moat in §35.

---

## §37. Terminology (frozen recommendation)

| Term | Meaning | Never conflate with |
|---|---|---|
| **Latest-revised reconstruction** | A value/state computed today from today's persisted (latest-revised) observations, at an explicit past period | "What EI said/knew/reported" |
| **Recorded state** | A value read from a durable row EI actually wrote at some point in the past (today: only the sparse `ReleaseAnalysisUpdate` trail; future: §14's snapshot object) | A reconstruction — recorded state can be incomplete and can disagree with what reconstruction shows today (§12) |
| **As-known-at-time state** | What EI would have concluded using ONLY data that existed as of a specific past date (vintage-aware) | Both of the above — not achievable today (§15) |
| **State duration** | A count of consecutive reconstructed (or, later, recorded) periods sharing the same state, ending at the present | An implied causal or economically significant "streak" — it is a count, nothing more |
| **Transition** | A single (period, previous state, current state) triple, drawn from either a reconstructed sequence or a recorded trail — its own source must always be named |

---

## §38. Disclosure requirements

The existing sentence ("Historical calculations use the latest revised observations available to Economic Intelligence. They may differ from values originally reported at the time.") **is necessary but not sufficient** for reconstructed *state* history — it correctly covers the revision-vintage half of the claim but says nothing about the reconstruction-vs-recorded distinction itself, which a metric-only disclosure never needed to address. **Recommended additional wording (a new sentence, not a replacement, to be formally frozen in a future contract turn, not written into production copy here):** something to the effect of "This duration is calculated today, using the latest revised data, applied consistently across the period shown — it reflects what today's data implies, not necessarily what Economic Intelligence reported in real time as each month occurred." Not modified in production copy this increment, per the explicit instruction.

---

## §39. Methodology-versioning recommendation

Given exactly one methodology version exists today, V1 may compute historical reconstructions using the current methodology unconditionally, **provided every returned historical point still carries an explicit `methodology_id` field** (already true of the domain functions' own output shape) so that a future second version never has to guess which methodology produced an already-returned historical point. UI copy should state which methodology produced the shown reconstruction whenever methodology detail is already shown elsewhere on the page (it already is, via the existing Evidence & methodology disclosure) — no new UI surface required for this, just field-level discipline in the new endpoint's response.

---

## §40. Recompute-vs-persist recommendation

**Recompute on demand for V1.** Correctness: recompute always reflects the latest revisions, no staleness risk. Performance: bounded — a monthly walk-back over, at most, a few years of monthly data is cheap (dozens of pure-function calls, no I/O beyond the observations already being fetched). Revision propagation: automatic, free, by construction (§8). Methodology changes: trivially safe, since nothing is persisted to go stale. Auditability/since-last-visit: **recompute cannot serve these** — this is precisely why §13 recommends *later*, forward-only persistence as a distinct follow-on, not a V1 prerequisite. Complexity: recompute is unambiguously the smaller, safer V1 choice.

---

## §41. Backend contract options (evaluated, not frozen)

Plausible future shape, evaluated for evidence-sufficiency, not committed: `GET /api/v1/monitors/inflation/history` / `.../labor/history`, parameterized by a bounded date range (never unbounded — matching this project's own existing pagination/bounding discipline elsewhere), returning a list of `{evaluation_period, state, methodology_id, data_basis}` (state only — evidence and full metric detail deliberately excluded from a first history contract, to keep the response small and the disclosure story simple; a caller wanting evidence for one specific historical period can request it via the existing period-explicit machinery separately, once such an endpoint exists). Whether the endpoint should return every month or transitions-only is genuinely undecided by this audit and correctly left for the contract-freeze increment — both are trivially derivable from the same underlying monthly sequence, so the decision affects response size and frontend logic, not architecture.

---

## §42. Future persistence semantics (described, not designed)

If §13's forward snapshot is eventually built, its required identity dimensions are: `monitor`, `evaluation_period`, `methodology_id`, `calculated_at`, `data_basis`. Two genuinely distinct historical concepts must never share one table without a discriminating field: **reconstructed canonical history** (always derivable, never itself worth persisting, since it can be recomputed identically at any time) and **recorded EI history** (the one thing worth durably writing, precisely because it cannot be recreated later). No column list is frozen here — that is explicitly a future increment's job, not this audit's.

---

## §43. Research requirements

Percentile/distribution windows (§17) need a defined, frozen statistical contract before any "82nd percentile" claim ships — not empirical *research* in the historical-validation sense, but a real design decision this audit does not make. "Unusual" thresholds, historical regime labels, and state-duration *interpretation* ("is 3 months a long time?") all require genuine empirical/economic research this project has never conducted and this audit does not attempt. None of these block the V1 recommended in §36/§41, which uses none of them.

---

## §44. Product surface options

| Option | Verdict |
|---|---|
| 1. Small historical context inside monitor pages | **Recommended for V1** — smallest, reuses the exact disclosure pattern #23C already established |
| 2. Full History section inside monitor pages | Premature — bigger surface than the evidence justifies yet |
| 3. Overview historical summary | Rejected (§26) — wrong page for this job |
| 4. Standalone History route | Premature — no content yet to justify a new route, mirroring #23B's own reasoning against a standalone `/relate` route |
| 5. Charts-first workspace | Rejected (§19) — no charting library, disciplined-labeling risk, explicitly deferred |

---

## §45. Deterministic testing requirements (for a future implementation increment)

Exact calendar periods (a walk-back must never search, only take explicit periods, mirroring every `_at` function's own existing discipline); a missing month inside the walk-back range (must surface as its own `INSUFFICIENT_DATA` point, never silently skipped, never breaking the duration count incorrectly); a revision changing historical reconstruction (a before/after test proving yesterday's reconstruction and today's, after a synthetic revision, can legitimately differ — and that this is expected, not a bug); methodology version carried on every point; state transitions correctly detected at exact boundaries; duration calculated as an exact consecutive-count, never an estimate; ordering (oldest-to-newest or newest-to-oldest, frozen, consistent); pagination/bounding if the range is large; the latest-revised disclosure copy present; Inflation and Labor reconstructions computed and tested fully independently (no shared "history" abstraction premature at two domains, mirroring this project's own repeated "no premature generic framework" rule).

---

## §46. Architecture boundary (frozen recommendation)

Historical computation must follow the same Route → Service → pure Domain layering every other deterministic capability in this project already uses — a new service method (or extension) orchestrating repeated calls to the *already-existing, unmodified* `_at` domain functions, never new economic logic in the route layer, never in the frontend, never via AI, never via interpolation, never inferring a value or a state from a chart or from adjacent points. This is not a new principle — it is this project's own standing rule, restated for a new capability shape.

---

## §47. Explicit deferrals

Full vintage/ALFRED system, as-known-at-time backtesting, regime labels, recession prediction, historical market-outcome analysis, causal analysis, AI historical summaries, arbitrary percentile-derived qualitative labels ("unusual," "extreme") without a frozen threshold methodology, a large charting workspace, user accounts, notifications, Growth, Compare (any form). None of these are touched, enabled, or brought meaningfully closer by this audit's own V1 recommendation, beyond the general architectural readiness (existing `_at` functions, existing disclosure pattern) that was already true before this audit.

---

## §48. Readiness classification

**READY FOR CONTRACT FREEZE** for State Duration V1 (§36/§41) — no research, no persistence, and no provider/vintage integration are required first; the one remaining gap is a product/architecture contract (exact endpoint shape, exact terminology enforcement, exact disclosure wording, exact edge-case behavior), which is a normal next-increment freeze turn, not a blocker. **RESEARCH REQUIRED FIRST** for any percentile/"unusual" language (§17/§18/§43) and for any historical-outcome/regime work (§2 class H) — do not sequence these into the V1 path. **PERSISTENCE REQUIRED FIRST** for recorded-history/since-last-visit/notifications at full fidelity (§13/§29/§30) — explicitly a later increment, not a V1 prerequisite. **PROVIDER/VINTAGE DATA REQUIRED FIRST**, and not recommended to pursue at all in the near term, for as-known-at-time claims (§15).

---

## §49. Recommended next increment

**#24B — Historical Reconstruction Contract Freeze** (mirrors the #22A/#23B pattern): freeze the exact backend contract shape from §41 (endpoint path, response fields, bounding rules), the exact terminology enforcement from §37/§38 (including the new disclosure sentence, drafted but not shipped as production copy by this audit), exact edge-case behavior (missing months, insufficient-data points, methodology-version field discipline per §39), and a full #24C/#24D test matrix. **#24C — Backend implementation** (new service orchestration over the already-existing, unmodified domain `_at` functions; a new thin API surface; zero new domain methodology; zero schema/migration, since V1 is recompute-only per §40). **#24D — Frontend implementation** (the state-duration fact placed inside each monitor page's existing disclosure, per §25/§44, with the frozen disclosure sentence).

---

## §50. Runner-up

**Curated Compare** (#23A's own runner-up, re-affirmed here per §31's direct comparison) — reusing the existing `/analysis/compare` endpoint for a small, pre-vetted, unit/frequency-compatible pair list. It remains second, not first, for the same reason §31 concludes: lower differentiation, no compounding-moat property, and it opens a genuinely new UI surface (a compare view) rather than deepening the two pages that already exist.

---

## §51. Thesis test

**Strengthens the existing positioning without requiring it to change.** "Know what changed in the economy — and prove why" already implies durability and evidence; a truthful, reconstruction-qualified "how long has this been true" is a direct, natural extension of "prove why," not a new promise. The prompt's own suggested evolved phrasing — "Know what changed, how long it has been changing, and prove why" — is a reasonable *future* articulation once §36's V1 ships, but is **not necessary to adopt now**; recommend leaving positioning unchanged through #24C/#24D and revisiting only if historical context becomes a headline capability rather than a supporting one.

---

## Appendix: secret safety and version control

No `.env`/`.env.*`/credential file was read, printed, or logged at any point this increment. The backend test run used the project's established local isolated-Postgres mechanism (trust-auth, no password). Nothing in this document was committed or pushed; the working tree outside this new file was not modified.
