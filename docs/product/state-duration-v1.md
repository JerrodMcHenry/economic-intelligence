# State Duration V1 — Contract Freeze

**Increment #24B.** Contract freeze only. No production code changed. Baseline: HEAD `6d35957` ("Add deterministic Relate V1 composition" — #23C). #24A's own artifact (`docs/product/historical-context-state-history-audit-v1.md`) was still untracked when this turn began — same recurring pattern as every prior audit→freeze transition this session; content treated as authoritative. Frontend: 895/895 passed. Backend: 1,173/1,173 passed, 0 skipped.

This document is the authoritative contract for #24C (backend) and #24D (frontend). If implementation reveals that any frozen claim below requires new economic interpretation, recorded (non-reconstructed) history, or as-known-at-time semantics, that implementation must STOP and return here rather than improvise.

---

## §1. The core historical-truth rule, restated as an implementation constraint

State Duration V1 computes and reports **latest-revised reconstruction only**. It never claims, implies, or is worded in a way that could be read as: what EI actually reported historically, what a user saw historically, what data was available historically, or what would have been knowable historically. Every UI string, every field name, and every test in this contract exists partly to enforce this.

---

## §2. Fresh inspection performed this turn

`app/domain/inflation.py` (`compute_series_momentum_at`, `month_before`, `build_index`), `app/domain/labor.py` (`compute_labor_monitor_result_at`, `month_before`, `combine_labor_state`), `app/domain/release_processing.py` (`five_year_observation_start` — cited as direct precedent, §11), `app/repositories/series_repository.py` (`get_observations_in_range`), `app/models/inflation.py`/`labor.py` (exact field names, `DATA_BASIS` constant), `app/api/inflation.py`/`labor.py` (existing HTTP-semantics precedent), `frontend/src/components/inflation/InflationHero.tsx`, `frontend/src/components/labor/LaborHero.tsx`, `frontend/src/components/labor/WhyLaborState.tsx` (post-#23C content, confirmed already carrying a Relate sentence — informs §39/§40's placement decision).

---

## §3. State Duration — exact definition (frozen)

Given a monitor's current canonical state `S` at its current anchor period `t`:

1. Confirm `S` is not `INSUFFICIENT_DATA` and `t` is not null (§14).
2. Load, once, every persisted observation needed to reconstruct up to `LOOKBACK_BOUND` (§11) months before `t` (§30).
3. Walk backward one exact calendar month at a time (`month_before(t, n)`, §7), calling the monitor's own existing, unmodified `_at` function at each step (§6).
4. Count consecutive preceding months (including `t` itself, §20) whose reconstructed state equals `S`, stopping at the first of three conditions (§8/§9/§11).
5. Return a `duration_months` count, an `earliest_confirmed_period` (§21), a `boundary_type` (§13), and — when genuinely known — the differing `previous_state`/`previous_period` (§22).

This produces **a latest-revised reconstructed consecutive-state run** — never "recorded historical duration," never "how long EI has said this."

---

## §4. Canonical subject (frozen, narrow)

State Duration V1 applies **only** to each monitor's top-level canonical state:

- Inflation: `InflationMonitorResult.underlying_momentum.state` (`InflationState`).
- Labor: `LaborMonitorResult.state` (`LaborState`).

**Explicitly excluded from V1**: `HeadlineContextResult`'s own states, `ConfirmationResult.relationship`, `EmploymentState`, `UnemploymentTrendState`, `EmploymentCondition`/`EmploymentMomentum`, and any individual numeric metric. A future increment could extend this pattern to any of them; V1 does not, per the explicit instruction and per §24/§25 below.

---

## §5. Current anchor period (frozen, verified not assumed identical)

- Inflation: `underlying_momentum.calculation_period` — confirmed the exact field already rendered today (`InflationHero.tsx`'s own `` `Core PCE · ${formatPeriod(momentum.calculation_period)}` ``).
- Labor: `LaborMonitorResult.evaluation_period` — confirmed the exact field already rendered today (`LaborHero.tsx`'s own equivalent line).

Different field names on different models, confirmed by direct inspection, not assumed.

---

## §6. Historical reconstruction functions to reuse (frozen — zero new economic logic)

- Inflation: `compute_series_momentum_at(observations, series_id, calculation_period, neutral_band_pp)` (`app/domain/inflation.py:364`) — already exists, already takes an explicit period, already the exact primitive `inflation_what_changed_v1.0`'s own comparator uses. Called against the Core PCE series (`PCEPILFE`) specifically, matching `underlying_momentum`'s own existing series identity.
- Labor: `compute_labor_monitor_result_at(payems_observations, unrate_observations, period, condition_deadband_jobs, momentum_deadband_jobs, unemployment_deadband_pp)` (verified present, `app/domain/labor.py`) — already exists, already takes an explicit period.

**#24C must not duplicate, re-derive, or approximate either monitor's methodology.** Every reconstructed point is produced by calling these exact, unmodified functions.

---

## §7. Exact-calendar stepping (frozen)

Each domain's own existing `month_before(period, months_back)` (present independently in both `app/domain/inflation.py` and `app/domain/labor.py`, pure calendar arithmetic, `months_back=0` returns the period itself) is reused **unmodified, per domain** — no new shared calendar utility, matching this project's own established precedent (`app/domain/labor_release_processing.py`'s own docstring: "re-derives its own tiny calendar-offset helper rather than importing `month_before`" — two independent, already-correct implementations, never one shared one, exactly the same reasoning applies here). Never `- 30 days`, never skip-to-nearest-available, never interpolate.

---

## §8. Boundary: EXACT (frozen)

The walk-back reaches a preceding month whose reconstructed state is a **real, non-`INSUFFICIENT_DATA`** value different from `S`. The consecutive run ending at `t` is exact — `boundary_type = "EXACT"`, and that differing month's state/period are exposed verbatim as `previous_state`/`previous_period` (§22).

---

## §9. Boundary: DATA_BOUNDED (frozen — and unified with the dataset-edge case, §10)

The walk-back reaches a preceding month whose reconstructed state is `INSUFFICIENT_DATA`. **This case is deliberately never distinguished from "ran off the edge of the persisted dataset"** — both produce the identical `INSUFFICIENT_DATA` return value from the same unmodified domain functions in §6 (a month with a genuine mid-history gap and a month simply too early for 12/14 months of trailing data to exist both fail the same required-months check inside those functions). No separate "dataset boundary detection" logic is needed or should be written — this is a real architectural simplification, not a shortcut: `boundary_type = "DATA_BOUNDED"` covers both, honestly, because from the caller's perspective both mean exactly the same thing — "we cannot verify whether the state differed any earlier than this, because of a data limit, not a policy limit." `duration_months`/`earliest_confirmed_period` describe only the confirmed-matching run; `previous_state`/`previous_period` are **not** populated (they are not genuinely known).

---

## §10. Boundary: dataset-edge — resolved, not a fourth case

See §9 — unified into `DATA_BOUNDED` by construction. No separate handling required.

---

## §11. Lookback bound (frozen: 60 months / 5 years, with real precedent)

**Frozen at 60 calendar months.** Not arbitrary: this project has already made, defended, and shipped the identical tradeoff once — `five_year_observation_start` (`app/domain/release_processing.py:124`, Increment #18) defines exactly five calendar years as this project's own established "ordinary economic monitoring window" for release-driven detection, computed via exact calendar arithmetic (`date.replace` with an explicit leap-day fallback, not `365 * 5` days). State Duration's own lookback bound is the same order of problem — how far back is "ordinary" for a monitoring product to reconstruct before diminishing product value (a duration of "at least 5 years" is functionally indistinguishable from "always," for this product's own stated audience) stops justifying additional query/compute cost. Reusing the identical, already-defended number (not the same function — each domain still computes its own bound independently, per §7's own no-shared-utility precedent) avoids inventing a second, unrelated definition of "long enough" inside the same codebase. **This did not require a new measurement increment** — the precedent is real, already shipped, and already defended in this exact repository.

---

## §12. Boundary: LOOKBACK_BOUNDED (frozen)

Every reconstructed month within the 60-month window matches `S` (no `INSUFFICIENT_DATA`, no differing state encountered) and the walk-back reaches the bound. `boundary_type = "LOOKBACK_BOUNDED"`. `previous_state`/`previous_period` are **not** populated (not known — the true prior state could be anything, including still `S`, beyond the window). UI copy must say "for at least N consecutive months" (§37C), never imply N is the true duration.

---

## §13. Exact-vs-lower-bound response model (frozen: three-value enum, not a boolean)

```
boundary_type: "EXACT" | "DATA_BOUNDED" | "LOOKBACK_BOUNDED"
```

A boolean cannot distinguish "we hit a real different state" from "we hit a data limit" from "we hit a policy limit" — all three carry different confidence and require different UI wording (§37). Three values, frozen, no fourth value added without a new contract turn.

---

## §14. Current-insufficient and missing-current-period behavior (frozen, unified)

Verified structurally in #24A's own audit (re-confirmed applicable here): a null current period always co-occurs with `INSUFFICIENT_DATA` in both domains' existing code. **Per the same defensive reasoning already established and shipped in #23B/§9** ("branch on state, never on period presence alone... defensive, not an assumption it relies on"), this contract does the same: if the current top-level state is `INSUFFICIENT_DATA` **or** the current period is null, the response is the single `CURRENT_INSUFFICIENT` status (§32) — no separate "missing period" status is created; it would be a distinction without a behavioral difference and would duplicate logic this project has already decided, twice now, not to duplicate. **No duration is computed or implied in this case** — confirmed against #24A's own finding ("Likely do not [say 'INSUFFICIENT_DATA for 2 months']" — correct, V1 does not).

---

## §15. (Merged into §14 — see above.)

---

## §16. Historical insufficient inside the run — frozen default: stop immediately

Encountering `INSUFFICIENT_DATA` at any point during the backward walk **stops the search immediately** (`DATA_BOUNDED`, §9). Skipping past it and continuing to search further back is explicitly rejected — it would silently bridge an unknown stretch of history and could produce a duration count that overstates confidence (e.g., claiming 8 "consecutive" months across a real 2-month gap). No evidence in this audit or its predecessor justifies the riskier alternative; the conservative default stands as the frozen behavior, not merely the default pending evidence.

---

## §17. Methodology-version behavior (frozen)

V1 reconstructs using **whatever methodology is current at request time**, unconditionally — there is exactly one version of each methodology today, so this is not yet observable, but the contract must hold for when a second version exists. Every response's `methodology_id` field (§32) reflects the methodology **actually used to produce that specific response**, never an implied historical one. **Frozen documentation truth, not a hedge:** if `labor_v1.1` later becomes current, a V1 reconstruction request for the identical period may return a **different** `duration_months`/`boundary_type` than it would have under `labor_v1.0` — even with zero observation revisions in between — purely because the classification rule itself changed. This is correct, expected behavior for a recompute-only, current-methodology contract (per #24A §39/§27), and must never be presented as a data anomaly.

---

## §18. Data basis (frozen)

`data_basis: "latest_revised_data"` — the exact existing constant (`app/models/inflation.py`'s/`labor.py`'s own `DATA_BASIS`), reused verbatim, not a near-duplicate string.

---

## §19. Reconstruction-type field (frozen: included)

**Decision: include `history_type: "latest_revised_reconstruction"`** as an explicit, fixed literal on every `AVAILABLE` response. Audited both ways: `data_basis` alone already implies latest-revised, and a minimal contract would omit this as redundant — but per the prompt's own instruction ("prefer minimal contract, but trust boundaries matter"), this is exactly a trust-boundary field: its entire purpose is to make it structurally awkward for a future recorded-history endpoint to be silently merged into this response shape without a reader noticing the type changed. One field, always the same value in V1, cheap, and directly serves §1's own core rule.

---

## §20. Duration counting (frozen)

The current period counts as one. Three consecutive matching months (current + 2 prior) → `duration_months = 3`. No off-by-one ambiguity: `duration_months` always equals the number of months from `earliest_confirmed_period` to `t` inclusive.

---

## §21. Earliest-period field naming (frozen: `earliest_confirmed_period`, never `start_period`)

**`start_period` is rejected** as a field name — it would overclaim precision identically in all three `boundary_type` cases, when only `EXACT` genuinely knows a true start. **`earliest_confirmed_period`** is frozen instead: it means, consistently across all three boundary types, "the earliest period this response has confirmed shares the current state" — true start when `boundary_type = "EXACT"`, a floor otherwise. One field name, one consistent meaning, `boundary_type` carries the confidence distinction — never two differently-named fields depending on which case applies.

---

## §22. Previous-state / previous-period (frozen: included, EXACT-only)

**Included.** When `boundary_type = "EXACT"`, the walk-back has already computed the differing prior month's full result to detect the boundary in the first place — `previous_state`/`previous_period` cost nothing additional to expose and turn "COOLING for 3 months" into "COOLING for 3 months; previously Stable" at zero extra computation. This is reconstructed canonical evidence (a direct, unmodified `_at` function output), never inference. **Not populated for `DATA_BOUNDED`/`LOOKBACK_BOUNDED`** — genuinely not known in those cases (§9/§12), and populating them with a guess would violate §1.

---

## §23. Transition object (frozen: excluded from V1)

**Excluded.** `previous_state`/`previous_period` (§22) already exposes the one transition adjacent to the current run, which is sufficient value for V1. A full transition-history object (multiple past transitions) is exactly the "transition timeline" #24A explicitly deferred (§22/§47 of that audit) — scope creep for this increment, a natural, cheap future extension once this ships, not a V1 requirement.

---

## §24. Inflation edge cases (frozen behavior)

Duration reads **only** `underlying_momentum.state` — Confirmation's own availability, Headline PCE's own availability, and Headline CPI's own availability **never** affect the computed duration, even if any of them independently becomes unavailable; V1 has no dependency on them at all (§4's own scope boundary, restated as a behavioral guarantee, not just a "V1 doesn't build it" note). A missing required month anywhere in Core PCE's own trailing window produces `INSUFFICIENT_DATA` at that reconstructed point via the existing, unmodified `classify_period` path — triggering `DATA_BOUNDED` per §9, never a crash, never a skip.

---

## §25. Labor edge cases (frozen behavior)

Both PAYEMS's own required-month dependency and UNRATE's own prior-year dependency are already correctly enforced inside `compute_employment_result`/`compute_unemployment_result` (unmodified) — a missing PAYEMS or UNRATE month anywhere in the required window at a given reconstructed period produces `INSUFFICIENT_DATA` for that point via the existing path, triggering `DATA_BOUNDED`, never a silent skip. The real, already-referenced-elsewhere-in-this-codebase UNRATE gap at `2025-10` (used as a concrete worked example in `tests/test_domain_labor_release_processing.py`'s own existing fixtures) is frozen here as the canonical #24C test case for `DATA_BOUNDED`: a walk-back whose window includes that date must stop there, never bridge across it.

---

## §26. Revision effect (frozen: expected, not a defect)

If persisted historical observations are later revised, a subsequent State Duration request for the same monitor may return a different `duration_months`/`boundary_type`/`previous_state` than an earlier request did. **This is correct for V1.** No attempt is made to preserve, cache, or reconcile against a prior computation — V1 has no persistence (§13 of #24A, reaffirmed) and must not grow any merely to paper over this expected variability.

---

## §27. Methodology-change effect (frozen: expected, not a defect)

Restated from §17 as its own explicit guarantee: a current-methodology change can alter a reconstruction's result with zero observation revision involved. Recorded, methodology-version-preserving historical claims are an explicitly separate, deferred future system (#24A §13/§42) — not something V1's recompute-only design attempts to approximate.

---

## §28. Service orchestration architecture (frozen)

`Route → Service → pure Domain`, this project's own standing layering, extended, not replaced. **Two separate, monitor-specific service methods** (an Inflation one, a Labor one) — no shared generic "historical monitor service," matching this project's own repeated, explicit "no premature generic framework" rule (directly precedented: `labor_release_processing.py` as an independent sibling of `release_processing.py`, `laborLabels.ts` as an independent sibling of `inflationLabels.ts`, `laborSalience.ts` as an independent sibling of `inflationSalience.ts` — never one abstraction for two instances). Each service: loads its own series' observations once (§30), builds its own domain-specific reconstructed sequence by calling its own `_at` function repeatedly, then hands that sequence to the one shared pure helper below.

---

## §29. Pure-domain / service boundary (frozen: one narrow shared pure helper, justified precisely)

**One new, small, shared pure function is justified here — narrowly, and for a specific, evidence-based reason different from every rejected "shared abstraction" elsewhere in this project's history.** The walk-back's own *economic* computation (calling `_at` repeatedly) is correctly domain-specific and stays in each service. But the logic that turns "a sequence of (period, state-or-insufficient) results" into `duration_months`/`boundary_type`/`earliest_confirmed_period`/`previous_state` is **pure sequence/counting logic with zero economic content** — it never inspects what `"COOLING"` or `"STRENGTHENING"` mean, only whether two values are equal and whether one equals the literal string `"INSUFFICIENT_DATA"`. This is the same category of already-accepted, genuinely domain-agnostic sharing this project already has precedent for (`app/domain/analysis.py`'s own `align_series`/`pearson_correlation`, which serve every series pair generically, not one economic family). Freeze: a new, small module (e.g. `app/domain/state_duration.py`) exposing one pure function taking a already-reconstructed, chronologically-ordered sequence and the lookback bound, returning the duration/boundary result — **no economic logic, no series knowledge, no methodology knowledge inside it**, verifiable by the same AST-level "imports no other domain module" guard this project already applies elsewhere (`app.domain.labor_what_changed`'s own precedent).

---

## §30. History-generation / query strategy (frozen: load-once, Strategy A)

One `get_observations_in_range` call per required series (already-existing repository method, `app/repositories/series_repository.py:97`, unpaginated, ascending, exactly shaped for this use), bounded to cover the 60-month lookback plus each domain's own trailing-window requirement (Inflation: +12 months; Labor: +14 months, for UNRATE's prior-year dependency) — loaded **once**, then up to 60 pure, in-memory `_at` calls per domain, zero additional database round-trips. Confirmed avoids N+1 queries; no new repository method is required, the existing one already returns exactly the shape needed.

---

## §31. API paths (frozen: narrow, honest, not a generic "history" endpoint)

```
GET /api/v1/monitors/inflation/state-duration
GET /api/v1/monitors/labor/state-duration
```

**Not** `/history` — a generic name would overclaim scope for an endpoint that, in V1, returns exactly one fact. This naming leaves room for a genuinely broader `/history` endpoint later (full monthly sequences, transitions, recorded history) without needing to redefine, version, or deprecate this one — the two are honestly different capabilities and should have honestly different names from the start.

---

## §32. Response contract (frozen)

```
StateDurationResult =
  | {
      status: "AVAILABLE",
      state: InflationState | LaborState,
      evaluation_period: string,          // the current anchor period, §5
      duration_months: int,
      earliest_confirmed_period: string,  // §21
      boundary_type: "EXACT" | "DATA_BOUNDED" | "LOOKBACK_BOUNDED",
      previous_state: InflationState | LaborState | null,   // §22, EXACT-only
      previous_period: string | null,                        // §22, EXACT-only
      methodology_id: string,             // §17
      data_basis: "latest_revised_data",  // §18
      history_type: "latest_revised_reconstruction",  // §19
    }
  | { status: "CURRENT_INSUFFICIENT", methodology_id: string, data_basis: "latest_revised_data" }
```

No field not justified above is included. Existing canonical state types (`InflationState`/`LaborState`) are reused, never redeclared.

---

## §33. HTTP failure behavior (frozen: mirrors existing monitor API philosophy exactly)

Infrastructure failure (database unreachable, `DATABASE_URL` unconfigured) → `503`; other database-layer failure → `500` — the identical pattern every existing monitor/release-processing route already uses. **Every economic-data condition is a `200`**: `CURRENT_INSUFFICIENT`, `DATA_BOUNDED`, `LOOKBACK_BOUNDED` are all successful responses with semantic fields, never HTTP errors — this is not a new decision, it is this project's own repeatedly-proven, repeatedly-tested infrastructure-vs-economic-data distinction, applied here without exception.

---

## §34. Pagination (frozen: none)

One result per request. No `limit`/`offset`/`pagination` object — explicitly unnecessary and explicitly not added.

---

## §35. Read-only guarantee (frozen)

Database-only. No FRED call, no sync, no persistence write, no release-processing trigger, no AI. Identical read-only discipline to every existing monitor `GET` route.

---

## §36. Performance expectation (frozen estimate, no premature optimization)

Per request: 1–2 `get_observations_in_range` calls (1 for Inflation's single series; 2 for Labor's PAYEMS+UNRATE), each returning on the order of 72–74 months of monthly data; up to 60 pure in-memory function calls per domain. No I/O inside the loop. This is estimated, not measured, but the shape (one bounded query, then pure computation) is the same shape every existing `_at`-based comparator in this codebase already uses safely at smaller scale — no caching, no persistence-as-optimization, and no premature measurement increment is justified by this estimate; #24C's own verification (real test-database timing) is the appropriate place to confirm, not this freeze.

---

## §37. Frontend product copy (frozen)

**A — EXACT boundary:**
> "Latest-revised reconstruction: Cooling for 3 consecutive months, since April 2026."

**B — DATA_BOUNDED lower bound:**
> "Latest-revised reconstruction: Cooling for at least 3 consecutive months."

**C — LOOKBACK_BOUNDED lower bound:**
> "Latest-revised reconstruction: Cooling for at least 60 consecutive months."

**D — CURRENT_INSUFFICIENT:**
> "Historical state duration is unavailable because the current state has insufficient data."

State label reused verbatim from the existing label function (`inflationStateLabel`/`laborStateLabel`), matching #23C's own established discipline exactly. "Latest-revised reconstruction:" prefix is load-bearing and appears in every non-error, non-unavailable rendering — never omitted for brevity.

---

## §38. Disclosure (frozen, new sentence, not a production edit this increment)

Existing sentence (`LATEST_REVISED_DATA.definition`) covers the *revision-vintage* half of the claim correctly and is reused unchanged, nearby. It says nothing about reconstruction-vs-recorded, which a metric-only disclosure never needed to. **New, additional sentence, frozen for #24D to add as new copy (not a modification of the existing sentence):**

> "This duration is calculated today, using the latest revised data and the current methodology, applied consistently across the period shown. It reflects what today's data implies, not what Economic Intelligence reported in real time as each month occurred."

Concise, does not duplicate the existing sentence's own revision-vintage claim, adds exactly the one distinction (§1) that claim doesn't cover.

---

## §39. Frontend placement — Inflation (frozen)

**Not** inside `WhyThisState` (rejected — see §40's identical Labor reasoning, applied symmetrically). Placed as a new, single line inside `InflationHero.tsx`, directly after the existing period line (`` `Core PCE · ${formatPeriod(...)}` ``) and before `<WhyThisState>` — the most visible spot, immediately below the badge and period a reader has already seen, above the progressive-disclosure "why" content.

---

## §40. Frontend placement — Labor (frozen)

**Not** inside `WhyLaborState` — inspected fresh (§2) and confirmed already carrying, post-#23C, an evidence `<dl>`, curated explanation text, *and* a Relate composition sentence; adding a fourth element risks exactly the "overloading the disclosure" the prompt warns against. Placed identically to Inflation (§39): a new single line inside `LaborHero.tsx`, directly after the existing period line and before `<WhyLaborState>`.

---

## §41. Overview (frozen: excluded)

**No State Duration on Overview in V1 or in #24D.** Restated from #24A §26/§41 as a hard requirement, not a preference.

---

## §42. Loading / error / unavailable UI states (frozen: five distinct states, never collapsed)

Loading (skeleton, matching every other monitor-page resource); API/infrastructure error (existing `ErrorMessage` pattern, with retry — never described as "historical context unavailable due to data," which would misrepresent an infrastructure failure as an economic-data condition, exactly the distinction §33 protects on the backend and this preserves on the frontend); `CURRENT_INSUFFICIENT` (§37D); `EXACT` (§37A); `DATA_BOUNDED`/`LOOKBACK_BOUNDED` (§37B/§37C — two distinct copy strings, never merged into one generic "lower bound" string, since the reason differs and precision matters per §1).

---

## §43. Beginner verdict

A beginner reads one sentence ("Cooling for 3 consecutive months, since April 2026") and understands the answer without needing to know what "reconstruction," "boundary," or "methodology version" mean technically — the "Latest-revised reconstruction:" prefix carries the honesty without requiring comprehension of *why* it's there; the fuller explanation lives in the disclosure (§38), read only by those who click it. Matches #24A §43's own required verdict.

---

## §44. Expert verdict

Every field in §32 is independently inspectable: `state`, `evaluation_period`, `duration_months`, `boundary_type`, `methodology_id`, `data_basis`, and (EXACT-only) `previous_state`/`previous_period` together let an expert fully verify or reconstruct the claim by hand against the same public FRED data. `previous_state` specifically adds real verification value beyond the duration count alone — an expert can confirm the exact transition, not just trust a number.

---

## §45. Test matrix — pure duration helper (frozen)

Current period counts as 1; a one-month run (current differs from the immediately preceding month) → `duration_months = 1`, `boundary_type = "EXACT"`; a multi-month run; a differing prior state → `EXACT` with correct `previous_state`/`previous_period`; a historical `INSUFFICIENT_DATA` encountered → `DATA_BOUNDED`, no `previous_state`; a sequence that never differs and never hits insufficiency before the bound → `LOOKBACK_BOUNDED`; historical insufficiency is **never** skipped past (a regression test proving a real state match *beyond* a gap does not get bridged); ordering (input sequence must be chronologically consistent, most-recent-to-oldest or the reverse, frozen and tested one way); deterministic — identical input sequence produces identical output on repeated calls; exact-calendar stepping is the CALLER's job, not this pure helper's (it operates over an already-built sequence) — a dedicated guard proves this module imports no other domain module (§29's own architectural claim, tested, not merely asserted).

---

## §46. Test matrix — Inflation (frozen)

A known, hand-constructed historical sequence producing a predictable `EXACT` result; a revision to a historical observation changing the reconstructed duration on a second call (proving §26, not merely asserting it); a missing required month producing `DATA_BOUNDED` at the correct boundary; confirms duration is computed **only** from `underlying_momentum.state` — a test that varies Confirmation's/Headline's own availability while holding Core PCE's own history fixed, and asserts the duration result is unaffected; `methodology_id`/`data_basis`/`history_type` present and correct on every `AVAILABLE` response.

---

## §47. Test matrix — Labor (frozen)

A known, hand-constructed historical sequence; the real `2025-10` UNRATE gap (§25) used as the canonical `DATA_BOUNDED` test case, proving the walk-back stops there rather than bridging it; a missing PAYEMS-only dependency producing `DATA_BOUNDED` independently of UNRATE; a missing UNRATE-only dependency, independently of PAYEMS; no skipping across either gap; shared-evaluation-period correctness (Employment/Unemployment's own already-structurally-guaranteed shared period, reused, never re-verified redundantly since #23C already proved this structurally); a revision changing reconstructed duration; `methodology_id`/`data_basis`/`history_type` present and correct.

---

## §48. Test matrix — API (frozen)

`200` exact; `200` data-bounded; `200` lookback-bounded; `200` current-insufficient; a simulated database failure produces the existing `503`/`500` pattern, never a fabricated economic-data response; no FRED client is ever constructed on this path (structural guard); no mutation of any kind occurs (a test asserting `EconomicObservation`/`EconomicSeries` row counts are unchanged before/after the request); no AI import anywhere in the route's own import graph; two identical, back-to-back requests against unchanged data produce byte-identical responses (determinism); Inflation's and Labor's own endpoints are independently testable and one's failure never affects the other (mirroring this project's own established failure-isolation discipline, restated at the API-test level here for the first time for this specific pair of routes).

---

## §49. Frontend test matrix (for #24D's own freeze, listed now so #24D's scope is unambiguous)

Exact-boundary copy (§37A) byte-identical; data-bounded copy (§37B); lookback-bounded copy (§37C); current-insufficient copy (§37D); API error renders the existing `ErrorMessage` pattern, never the unavailable-data copy; loading renders the existing skeleton pattern; the new disclosure sentence (§38) present and byte-identical, alongside the existing latest-revised sentence, never replacing it; **zero** rendering on Overview (a regression test on `Overview.test.tsx` asserting the new copy strings never appear there); correct placement on `/inflation` (after the period line, before `WhyThisState`) and `/labor` (after the period line, before `WhyLaborState`); the existing page hierarchies (Inflation's sections, Labor's frozen 7) remain unchanged; no chart element renders anywhere; no state is ever recomputed client-side (the frontend renders exactly what the new endpoint returns, never re-derives `duration_months`/`boundary_type` itself).

---

## §50. Architecture guards (frozen requirements for #24C/#24D)

Prove, via dedicated guard tests extending this project's own established patterns: no `FREDClient` import or construction anywhere on the state-duration path (backend); no AI/LLM import (backend and frontend); no `INSERT`/`UPDATE`/session-mutating call on the read path (backend, structural); no new migration, no new table (verified by `git status`/`alembic check`, not a runtime guard); no frontend file performs an economic calculation (extending `no-economic-logic.test.ts`'s existing whole-tree scan naturally, since the new frontend files fall inside its existing collection scope); no silent interpolation or missing-month-skipping (a positive test, §45/§47, not just an absence-of-a-pattern guard — this specific property is better proven by behavior than by grep); no "recorded"/"EI reported"/"EI has said" wording anywhere in the new frontend copy (a narrow, scoped bare-word guard over exactly the new files, mirroring #23C's own `no-relate-inference.test.ts` precedent of narrow scoping to avoid false-positiving on unrelated correct prose elsewhere); no "as of {date}, EI knew" or "as-known-at-time" phrasing; no regime-label vocabulary (reusing the existing #23C prohibited list where applicable); no percentile/statistical-distribution logic anywhere (this module computes counts and equality checks only); no charting import.

---

## §51. Reconstruction-vs-recorded terminology — hard freeze, restated as the final word

**Permitted:** "latest-revised reconstruction," "reconstructed duration," "earliest confirmed matching period," "for at least N consecutive months," any construction that keeps the reconstruction qualifier attached and visible.

**Forbidden, unqualified:** "EI has classified this as X since...," "EI has said X since...," "the state has been X since...," or any construction that drops the reconstruction qualifier — **even if the boundary is `EXACT`**. `EXACT` means "the reconstructed run is exactly N months, with no data gap inside it" — it does **not** mean "this is what EI actually reported at the time," which V1 never claims under any boundary type. This is the single most important sentence in this document and must never be relaxed by a future increment without a new, explicit contract turn.

---

## §52. #24C scope (frozen)

**Backend only.** New: `app/domain/state_duration.py` (one pure, domain-agnostic sequence-evaluation function, §29); an Inflation-specific and a Labor-specific service method each producing a reconstructed sequence via existing, unmodified `_at` functions and handing it to that pure helper; new response models (§32); two new read-only API routes (§31); tests per §45–§48; documentation. **Expected: zero migrations, zero new tables, zero FRED/provider calls, zero frontend production changes, zero methodology change** — every economic calculation this increment performs was already fully implemented before this increment began.

---

## §53. #24D scope (frozen)

**Frontend only**, gated on #24C's own successful completion. New: typed API-client mirrors of §32's response shapes; one small new UI element per monitor page (§39/§40); the new disclosure sentence (§38); tests per §49. **No Overview changes** (§41). **No chart.** No new route, no new top-level nav item.

---

## §54. Explicit deferrals (restated, unchanged from #24A)

Recorded state-history persistence; a full `/history` endpoint; a rendered state timeline; a rendered transition timeline; metric charts; percentiles; "high"/"low"/"unusual" qualitative labels; ALFRED/vintage-data integration; as-known-at-time reconstruction; since-last-visit; notifications; Compare (any form); Growth; AI-generated historical summaries; regime labels; market-outcome/backtesting analysis.

---

## §55. GO / STOP checklist

| # | Item | Status |
|---|---|---|
| 1 | Exact state-duration semantics frozen | ✅ §3 |
| 2 | Exact-calendar stepping frozen | ✅ §7 |
| 3 | Insufficient-gap behavior frozen | ✅ §9/§16 |
| 4 | Exact boundary frozen | ✅ §8 |
| 5 | Data boundary frozen | ✅ §9/§10 (unified) |
| 6 | Lookback boundary frozen | ✅ §11/§12, real precedent cited, no measurement increment needed |
| 7 | Exact vs. lower-bound semantics frozen | ✅ §13 |
| 8 | Duration counting frozen | ✅ §20 |
| 9 | Safe start-period naming frozen | ✅ §21 |
| 10 | Current insufficient frozen | ✅ §14 |
| 11 | Methodology-version behavior frozen | ✅ §17/§27 |
| 12 | Revision behavior frozen | ✅ §26 |
| 13 | Data basis frozen | ✅ §18 |
| 14 | Architecture frozen | ✅ §28/§29 |
| 15 | Bounded query strategy frozen | ✅ §30 |
| 16 | API paths frozen | ✅ §31 |
| 17 | Response models frozen | ✅ §32 |
| 18 | HTTP semantics frozen | ✅ §33 |
| 19 | Frontend copy frozen | ✅ §37 |
| 20 | Disclosure frozen | ✅ §38 |
| 21 | Inflation placement frozen | ✅ §39 |
| 22 | Labor placement frozen | ✅ §40 |
| 23 | Testing frozen | ✅ §45–§49 |
| 24 | #24C backend-only feasible | ✅ §52, zero new domain math |
| 25 | #24D frontend-only feasible | ✅ §53, gated on #24C |
| 26 | No persistence required | ✅ confirmed throughout, recompute-only |
| 27 | No research required | ✅ confirmed, no percentile/regime work in V1 |
| 28 | No vintage data required | ✅ confirmed, as-known-at-time explicitly out of scope |

All twenty-eight resolved. The lookback bound was defensible without a new measurement increment (§11) — no STOP triggered on that basis.

---

## Appendix: secret safety and version control

No `.env`/`.env.*`/credential file was read, printed, or logged at any point this increment. Nothing in this document was committed or pushed; the working tree outside this new file was not modified.
