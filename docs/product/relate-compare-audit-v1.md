# Relate / Compare — Product, Methodology & Architecture Audit — V1

**Increment #23A.** Audit / design / contract-discovery only. No production code changed. Baseline: HEAD `03d0844` ("Define deterministic presentation salience for canonical Inflation and Labor change events" — #22B), clean working tree. Frontend: 731/731 passed. Backend: 1,173/1,173 passed, 0 skipped, against the project's established local isolated-Postgres test mechanism.

**Status of this document: primarily AUDIT, with one narrow CONTRACT FREEZE inside it** (§11, the composition-vs-inference boundary, and §12, the agreement/divergence vocabulary scope) — these two are frozen because they require no new methodology and no new research, only a disciplined reading of contracts that already exist. Everything touching statistics (Compare), history, or cross-domain labeling is left as audit findings with an explicit "not ready, here is what would be required" — never falsely called frozen.

---

## §1. The product problem this audit answers

Re-read directly: `docs/product/product-experience-audit-v1.md` (§5, §8, §30) scored Compare **1/5** ("zero frontend surface; backend exists but is raw-series-only, not monitor-level") and named "How does it relate?" the least-developed of the product's three core jobs — but explicitly warned against solving it with an aggregate score or regime matrix. `docs/product/overview-attention-model-v1.md` deliberately kept Inflation and Labor as separate, never-merged sections throughout (§12: "domain separation is preserved... no fake combined stream"), which is consistent with, not contradictory to, this audit's own findings: separation was right for *change events* (no honest shared timestamp existed); it does not resolve whether the two domains' *current states* can be safely composed into one sentence, which is a different question this document now answers. The exact problem to solve is: **the product has never, anywhere, said anything about how Inflation and Labor relate to each other, only shown them side by side** — and the audit must find the line between safely composing that relationship from existing facts and inventing new economic meaning.

---

## §2. Current relationship inventory (inspected fresh)

| Relationship | Explicit or incidental? | Where |
|---|---|---|
| Core CPI confirms/diverges from Core PCE | **Explicit, canonical, methodology-defined** | `ConfirmationResult.relationship` (`app/domain/inflation.py:391`), rendered on `/inflation`'s `ConfirmationPanel` and Overview's `WhyThisState` |
| Employment state + Unemployment trend → Labor state | **Explicit, canonical, methodology-defined** (a real relationship-fusion, not a display grouping) | `combine_labor_state` (`app/domain/labor.py:288`), rendered as `LaborMonitorResult.state`, drill-down in `WhyLaborState` |
| Release → monitor (which release feeds which monitor) | **Explicit as of #22B**, but narrowly (navigation/attribution only, not an "explains" relationship) | `lib/releaseMonitorRelation.ts`'s `CANONICAL_MONITOR_RELEASE_IDS` |
| Detected observation change → detected analysis change | **Explicit non-relationship** — deliberately presented as two sibling facts, never nested, never implying causation (ADR-023) | `components/overview/LatestDataDetected.tsx` |
| Inflation state ↔ Labor state | **Incidental only** — side-by-side cards under one shared "Current State" heading, zero composed statement anywhere | `CurrentStateSection.tsx` |
| Headline PCE/CPI vs Core PCE | **Incidental** — shown as separate context rows on `/inflation`, no relationship word used between them | `HeadlineContext` |
| Any series vs any other series | **Not exposed at all** | backend-only, `/analysis/compare`/`/analysis/pipeline` |

**Finding:** exactly two real EXPLICIT RELATIONSHIP prototypes exist today, both methodology-backed, both narrow in scope. Everything cross-domain is currently incidental (co-location, not relationship).

---

## §3. Backend Compare capability, inspected fresh

`app/services/analysis.py`'s `AnalysisService.compare`/`pipeline`, backed by `app/domain/analysis.py`'s pure functions (`align_series`, `calculate_spread`, `count_usable_pairs`, `pearson_correlation`).

| Property | Finding |
|---|---|
| Series count | Exactly two, by raw `series_id` — no n-series comparison |
| Alignment | Exact-date inner join only (`align_series`) — never interpolated, forward/backward-filled, or resampled; a matched date can still carry a `None` on either side |
| Missing data | A matched pair with a `None` on either side is excluded from `usable_pairs`/correlation/spread but still counted in `matching_pairs` — both counts returned, never conflated |
| Correlation definition | Pearson product-moment, over usable pairs only, computed **directly on whatever values are supplied** — `/analysis/compare` has no transformation option at all, so it is *always* raw persisted levels; `/analysis/pipeline` can apply a per-side transformation, but nothing requires or defaults to one |
| Minimum sample | **`n ≥ 2` only** (`pearson_correlation` returns `None` below that) — no larger statistical-significance floor exists anywhere; confirmed by the test suite (`tests/test_domain_analysis.py::test_fewer_than_two_usable_pairs_returns_none` is the only sample-size guard) |
| Spread definition | `value_a - value_b`, pure arithmetic, no unit check (`calculate_spread`'s own docstring: "does not check or reconcile the two series' units... its economic meaningfulness is left to the caller to judge") |
| Ordering | Chronologically ascending, always, regardless of input order |
| Filtering | `start_date`/`end_date` only, applied per-series before alignment |
| Persisted vs. provider | Database-only — never calls FRED, never syncs, never persists a result (recomputed every call) |
| Response contract | `SeriesComparisonResponse`/`PipelineResponse`: `series_a`/`series_b` (`SeriesSummary`: `series_id`/`title`/`units`/`source` only), `analysis`, `matching_pairs`, `usable_pairs`, `correlation`, `observations[]` |
| Provenance | Series identity and units only — no frequency, no seasonal adjustment, no vintage/revision marker on the comparison response itself |
| Error behavior | `InvalidDateRangeError`→400, `SeriesNotFoundError`→404, `OperationalError`→503, `SQLAlchemyError`→500 — infrastructure-vs-not-found distinction is clean and correct |

**Verdict: the math is correctly implemented and honestly tested for what it claims to do. It is not, by itself, safe to expose as a generic user-facing feature — see §4.**

---

## §4. Correlation and spread safety audit (critical)

**Correlation.**
- Computed on raw levels by default, with no forced or even suggested detrending — two independently-trending level series (e.g., any two series that have grown over time for unrelated reasons) will produce a high, entirely spurious correlation. This is the exact classic statistical trap named by the audit prompt, and nothing in the current contract prevents it.
- `n ≥ 2` is trivially satisfiable and **mathematically guarantees `|r| = 1.0`** for exactly two points (any two distinct points define a perfect line) — a technically valid computation that is a completely meaningless "signal" if surfaced without a much higher floor.
- No concept-compatibility check: the API has no notion that two series measure the same or comparable things — it will correlate anything against anything.
- No frequency/seasonal-adjustment awareness (and, per §3/§19, mostly cannot have one — that metadata isn't even persisted).
- **Safety verdict: raw correlation must NOT be exposed directly to a beginner today.** Before any generic user-facing correlation surface: (a) a frozen, much higher minimum-usable-pairs floor (e.g., dozens, not 2) as a deterministic product guardrail; (b) either a mandatory transformation (percent-change or similar) or an explicit, unavoidable disclosure when levels are being correlated; (c) ideally, a concept/unit-compatibility signal, which requires new metadata (§19) that does not exist today. None of this is "new methodology" in the economic-conclusion sense — it is a **statistical-method contract** that needs to be defined and frozen before the existing math is exposed generically.

**Spread.**
- Purely arithmetic, no unit check, confirmed directly in `calculate_spread`'s own docstring as a deliberate, explicit non-goal at the domain layer.
- Meaningful only for same-or-directly-comparable units (e.g., two percentage-point rates); meaningless between a percent series and a jobs-count series.
- The API cannot currently detect unit (in)compatibility to refuse or warn — `SeriesSummary.units` is returned but never compared.
- **Safety verdict: generic spread should not be exposed for an arbitrary series pair without a units-compatibility check that does not exist today.** It is safe today only for a **curated** pair the product already knows is unit-compatible.

---

## §5. Frequency / alignment audit

Exact-date alignment is honest — it never fabricates a value — but it is not the same thing as "safe to expose without comment." Monthly-vs-monthly (e.g., PAYEMS vs. UNRATE, both first-of-month) aligns cleanly. Monthly-vs-quarterly or monthly-vs-daily would align only on the sparse set of dates that happen to coincide, producing a technically-correct but visually confusing near-empty comparison with no diagnostic surfaced to explain why. **No interpolation should be introduced** (the existing discipline is correct and should be preserved), but a frequency-mismatch warning is a real, currently-missing product requirement for any Compare surface broader than a curated, pre-vetted, same-frequency pair list.

---

## §6. Transformation readiness

Existing (`app/domain/transformations.py`, exposed via `/series/{id}/transform` and `/analysis/pipeline`): `absolute_change`, `percent_change`, `moving_average` (fixed window). **Missing for a genuinely useful Compare experience**, identified but explicitly not to be built this increment: year-over-year change, annualized 3M/6M rates (the exact shape `inflation_v1.0` already computes internally but does not expose as a generic series transform), basis-point change (for rate-shaped series like UNRATE), index normalization (rebasing two series to a common start value for visual comparison), z-score/standardization (a principled way to compare differently-scaled series without literal unit compatibility). None of these require new economic *methodology* — they are well-defined statistical transformations — but each is a real, currently-absent backend capability.

---

## §7. Metadata readiness

Confirmed by direct inspection of `app/db/models.py`'s `EconomicSeries` table and `app/models/series.py`'s `SeriesSummary`: **the persisted schema stores only `series_id`/`title`/`units`/`source`** — no frequency, no seasonal adjustment, no last-observation-date as a series-level field. `SeriesCandidate` (discovery-only) *can* carry `frequency`/`seasonal_adjustment`/`observation_start`/`observation_end`/`popularity`, but only when the same series was also freshly found via a live FRED catalog search in that same request — confirmed explicitly in that model's own docstring ("the rest simply aren't columns in our local schema"). **This is a real, verified architecture gap**: a Compare/Relate surface that wants to warn about frequency or seasonal-adjustment mismatches cannot do so reliably for a persisted series today without either a schema addition or a live FRED lookup on every request (the latter reintroducing a provider dependency the analysis plane deliberately has none of today).

---

## §8. Series discovery readiness

`app/services/discovery.py`'s `SeriesDiscoveryService.search` merges local persisted metadata with a live FRED catalog search, degrading gracefully if FRED is unreachable — real, deterministic, already-tested capability. A user could plausibly find "Core CPI," "Core PCE," "Unemployment Rate," "Payroll Employment" by name. **Gaps for a Compare-workspace use case**: (a) no confirmation that a discovered series is *already persisted* and thus comparable today without a sync (the model does carry `persisted: bool`, so the frontend *could* filter, but nothing curates "these are the economically sensible choices"); (b) FRED's own catalog genuinely contains many near-duplicate series for a given concept (seasonally adjusted vs. not, different vintages, different index bases) that a beginner could not be expected to distinguish; (c) zero frontend exposure exists today (confirmed, `docs/product/product-experience-audit-v1.md` §1). **A generic, open "search any series and compare" workspace would need a curated allow-list or a much richer disambiguation UI before V1** — raw discovery alone is not sufficient.

---

## §9. Raw Series Compare value test

| Job | Required transformation | Would raw levels mislead? | Would a beginner know the right transformation? | Verdict |
|---|---|---|---|---|
| "Compare Core CPI and Core PCE" | YoY or the existing 3M/6M annualized (already computed by `inflation_v1.0`, not exposed generically) | Yes — both trend upward; levels correlate near 1 regardless of relationship | No | Unsafe without a default |
| "Compare unemployment and payroll growth" | Payroll needs a change transform (level is a raw headcount); unemployment is already rate-shaped | Yes for payroll levels | No | Unsafe without a default |
| "Compare inflation and yields" | Both need care (yields are already a rate; inflation needs YoY/annualized) | Partially | No | Unsafe without a default |
| "Compare two measures over time" | Depends entirely on the pair | Usually | No | Generically unsafe |

**Verdict: an *open* Series Compare workspace would need opinionated, honestly-defined default transformations per series (or per series-type) to avoid being misleading — these defaults do not exist today and would themselves need to be a small, deterministic, documented decision (not "new methodology" in the economic-conclusion sense, but a real statistical-contract decision requiring its own freeze).** Without them, an open compare tool is a real product risk exactly as the prompt's own "Product Risk" section describes: EI would become a smaller, unsafer macro dashboard.

---

## §10. Relate value test — separating the jobs

| User question | Problem class | Answerable today? |
|---|---|---|
| "Are CPI and PCE telling the same story?" | Same-concept confirmation | **Yes, already** — `ConfirmationPanel`/`WhyThisState` |
| "Are payrolls and unemployment confirming each other?" | Within-domain component relationship | **Partially** — both are visible in `WhyLaborState`, but the agreement/disagreement is not stated in words, only implied by `LaborState` itself (see §9 below) |
| "Is inflation cooling while labor remains strong?" | Cross-domain state composition | **Not today** — both facts are visible, nothing states them together |
| "Did both Inflation and Labor change this month?" | Cross-domain change composition | **Partially** — both What Changed cards are visible on Overview, nothing summarizes "both moved" |
| "Are the canonical monitors agreeing or diverging?" | Cross-domain state relationship — **the risky one**, see §12 | **Not today, and only partially answerable safely** |
| "What historically happens when they diverge?" | Historical outcome relationship | **Not ready at all** — see §14 |

**Finding, directly per instruction: these are genuinely different problem classes, and no single feature solves all of them.** The safe, buildable-now subset is composition of already-canonical facts (rows 1, 3, 4); the unsafe-without-more-work subset is statistical/historical (row 6 in part, and anything resembling raw Compare).

---

## §11. Relationship taxonomy (frozen vocabulary, not frozen conclusions)

| Class | Example | In EI now / later / never |
|---|---|---|
| **A. Same-concept confirmation** | Core CPI vs. Core PCE | **Now** — already shipped, the prototype (§12) |
| **B. Within-domain component relationship** | Employment vs. Unemployment | **Now, implicitly** (via `LaborState`); could be **stated more explicitly** with zero new methodology (§13) |
| **C. Cross-domain state relationship** | Inflation vs. Labor | **Now, but composition only** — see §14's frozen boundary; any labeling is deferred |
| **D. Statistical series relationship** | Correlation between transformed series | **Later** — backend exists, unsafe as-is, needs a statistical-method contract first (§4/§9) |
| **E. Temporal/lead-lag relationship** | "Does labor lead or lag inflation?" | **Not now** — no methodology, no research, explicitly out of scope per this prompt |
| **F. Historical outcome relationship** | "What usually happens when they diverge?" | **Not now** — needs state history, empirical validation, look-ahead-bias controls (§17) |

---

## §12. Same-concept confirmation — the prototype, audited

`classify_confirmation_relationship` (`app/domain/inflation.py:391`), inspected fresh: `CONFIRMS` only when both sides are the **literally identical** `InflationState` value and that value is one of `COOLING`/`HEATING`/`STABLE`; `DIVERGES` only for the specific opposite pair `{COOLING, HEATING}`; `MIXED`+`MIXED` is explicitly `INCONCLUSIVE`, never `CONFIRMS` ("confirmation requires directional or STABLE agreement, not merely 'both uncertain'" — the function's own comment); either side `INSUFFICIENT_DATA` or missing → `UNAVAILABLE`.

**Why this is safe, precisely:** both inputs are the **same type** (`InflationState`), measuring the **same concept** (core inflation momentum) via two independently-constructed source series, compared at the **same evaluation period**. The relationship words ("confirms"/"diverges") are legitimate here because equality/opposition of an identical vocabulary is a well-defined, tautological comparison — not an inference about what the agreement *means* economically.

**Lesson for future relationship intelligence:** "confirmation" as a reusable pattern requires all three of those properties (same type, same concept, same period) to stay safe. It is not a generic pattern that can be pointed at any two states — see §14 for exactly where it breaks.

---

## §13. Labor's internal relationship — a second, different prototype

`combine_labor_state` (`app/domain/labor.py:288`): a **fixed lookup table**, only 4 of the 4×5=20 possible `(EmploymentState, UnemploymentTrendState)` pairs map to a clean value (`STRENGTHENING`/`COOLING`×2/`STABLE`); every other pairing — including every `RECOVERING` pairing — defaults to `MIXED`, an explicit, documented, non-arbitrary default (the code's own comment: "No weights, no score, no majority vote, no hidden tie-breaker").

**Is `LaborState` itself already a RELATE result? Yes — and this is the audit's single most important structural finding.** Unlike Confirmation (same-type comparison), this combines **two different enums** (`EmploymentState`, `UnemploymentTrendState`) into a **third, new type** via an explicit table — structurally, this is exactly what a hypothetical "Inflation × Labor matrix" (§16) would look like in shape. It is legitimate here **only** because it is backed by real, separately-conducted research (`research/labor_momentum/LABOR_V1_FROZEN_METHODOLOGY.md`, a versioned, frozen methodology document), not invented during a UI increment.

**Product lesson:** exposing Employment/Unemployment's agreement or disagreement *more explicitly in words* ("Employment and Unemployment are sending consistent signals" / "...disagreeing signals") requires **zero new methodology** — `MIXED` already, by definition, means "these disagree," and the two component states are already both visible in `WhyLaborState`. This is a pure presentation improvement, not a new economic conclusion — a strong, safe, low-risk candidate for inclusion in V1 (see §18).

---

## §14. Cross-domain state relationship — the boundary, frozen

Directly addressing §10/§12 of the source prompt:

- **Composing** "Inflation: COOLING" and "Labor: STRENGTHENING" side by side — already done, safe, unchanged.
- **Composing** them into one plain sentence — "Inflation is cooling while Labor is strengthening" — is **safe and frozen as in-scope for V1**. This is COMPOSITION (§15): concatenating two already-canonical facts with a neutral conjunction, adding zero new economic meaning. No new methodology.
- **Labeling** that combination — "Goldilocks," "Bullish," "Soft Landing," "Risk-On," or any other named regime — is **NOT safe** and is **frozen as out of scope** for any increment until a separately-researched, versioned methodology exists (a real economic literature review, explicit criteria, and ideally some empirical grounding — exactly NEW METHODOLOGY + HISTORICAL VALIDATION REQUIRED per §34's classification). This matches the prompt's own explicit prohibition and #21/#22A/#22B's repeated, standing "no aggregate score, no regime matrix" rule.
- The word "agree"/"diverge" is **not** legitimate for Inflation vs. Labor the way it is for Core CPI vs. Core PCE (§16) — Inflation and Labor do not share a vocabulary or measure the same concept; "Inflation is COOLING and Labor is STRENGTHENING" is not an agreement or a disagreement, it is two independent facts. The product must say exactly that ("independent facts," never "agreement") — see §16.

---

## §15. Composition vs. inference — frozen definitions

> **COMPOSITION**: combining already-canonical facts, drawn verbatim from existing monitor results, into one presentation (a sentence, a card, a list) that adds no new economic meaning beyond what the facts already state independently. A composed sentence may use neutral, meaning-preserving connectives ("while," "and," "but not") — it may **never** use a connective or label that itself asserts a new economic relationship (e.g., "confirming," "contradicting," "favorable for," "at risk of").

> **INFERENCE**: deriving a new economic conclusion — a classification, a directional call, a regime label, an implied recommendation — from the combination of two or more canonical facts, that does not already exist as a canonical, methodology-defined value on either input.

**Composition example (in-scope):** "Inflation is COOLING while Labor is STRENGTHENING." — both states rendered verbatim, "while" used purely as a neutral temporal/contrastive conjunction, no new word invented.

**Inference example (out of scope, requires new methodology):** "This environment is favorable for equities." / "Inflation is COOLING while Labor is STRENGTHENING — a Goldilocks combination." Both assert something neither `InflationState` nor `LaborState` claims on its own.

**Frozen rule for #23-series work:** any feature that stays within COMPOSITION may proceed without a new methodology increment. Any feature that would require INFERENCE must be deferred to its own, explicitly-scoped, separately-researched methodology increment — never quietly folded into a UI increment.

---

## §16. Agreement/divergence vocabulary — where it's legitimate

| Pair | Same type? | Same concept? | Same period mechanism? | "Agree"/"diverge" legitimate? |
|---|---|---|---|---|
| Core CPI vs. Core PCE | Yes (`InflationState` both) | Yes (core inflation momentum) | Yes (`latest_shared_observation_period`) | **Yes** — already shipped (§12) |
| Employment vs. Unemployment | No (`EmploymentState` vs. `UnemploymentTrendState`) | Related but distinct (hiring pace vs. joblessness level) | Yes (Labor's shared `evaluation_period`) | **Partially** — `LaborState`'s own `MIXED` already encodes "disagree" as a fact; a *literal* "agree/disagree" sentence is defensible here precisely because the frozen methodology (§13) already defines what agreement means for this specific pair — do not generalize the word beyond what `combine_labor_state`'s own table defines |
| Inflation vs. Labor | No (`InflationState` vs. `LaborState`) | No (price momentum vs. labor-market momentum — genuinely different concepts) | No shared period guarantee (confirmed, `overview-attention-model-v1.md` §12) | **No** — "agree"/"diverge" would misleadingly imply these measure the same thing; use only composition language ("while," "and"), never agreement language |

**Frozen rule: "agree"/"diverge"/"confirm" vocabulary is legitimate only where a real, versioned methodology already defines what agreement means for that specific pair (today: Core CPI/Core PCE, and, narrowly, Employment/Unemployment via `LaborState`'s own table). It must never be extended to Inflation vs. Labor, and must never become a general-purpose word applied to an arbitrary pair of canonical values.**

---

## §17. The cross-domain matrix temptation — explicitly rejected for now

A literal `Inflation × Labor → label` table (the prompt's own worked example: `COOLING + STRENGTHENING = X`) would require, at minimum: a real economic-literature review of what such combinations are conventionally understood to mean (if anything, consistently); an explicit, versioned methodology document (mirroring `LABOR_V1_FROZEN_METHODOLOGY.md`'s own rigor); ideally some empirical/historical grounding, which itself requires the state-history infrastructure §19 finds doesn't exist yet; and a decision about false precision (there are `5 × 5 = 25` state combinations — most would be arbitrary if forced into a label). **None of this exists today. DEFER — not partially, not "later this increment," fully out of scope until a dedicated research increment exists**, exactly per the prompt's own explicit instruction.

---

## §18. Historical relationship readiness

"What tends to happen when inflation cools and labor weakens?" is a genuinely valuable question, but requires, none of which currently exist: **persisted historical monitor-state history** (confirmed absent, §19); a frozen regime/episode definition (when does an "episode" of cooling-inflation-weakening-labor begin and end?); a frozen outcome definition (what is being measured as "what happens next"?); protection against look-ahead bias (only using information that would have been known at the time); explicit handling of the latest-revised-vs.-as-known-at-the-time boundary (§20 — today's historical reconstructions use latest-revised data, which is not what a user "would have known" historically); a sample-size/statistical-uncertainty disclosure appropriate to how few genuine historical episodes actually exist. **Verdict: not ready. Do not build. This is its own future research increment**, not a #23-series deliverable.

---

## §19. State-history requirement

Confirmed by direct inspection: `EconomicSeries`/`EconomicObservation` persist full historical **series data**, and #18/#20D's release-processing pipeline persists a full history of **detected changes** (`ReleaseObservationUpdate`/`ReleaseAnalysisUpdate`). **No table persists a complete historical time series of `InflationMonitorResult.underlying_momentum.state` or `LaborMonitorResult.state` values in isolation** — every historical state is *recomputable* on demand (via the `_at`-suffixed pure functions each domain module already has), but nothing stores "on this date, Inflation was COOLING" as its own durable row. This does not block **current composition** (§14 — both current states are already fetched live) or **since-last-visit** framing (client-local, doesn't need server-side history). It **does** block any genuine **historical comparison** or **regime analysis** (§18) — those need a real, queryable state-history table, which is a **new persistence requirement**, not something achievable frontend-only or via a backend contract extension alone.

---

## §20. Revision / vintage boundary

Confirmed, consistent with every prior increment's own documented "latest revised data" basis (`DATA_BASIS = "latest_revised_data"`, `app/models/inflation.py`): every historical calculation in this project, including anything a future state-history feature would compute, is a **latest-revised reconstruction** — never what was actually known at the time. This is explicitly, honestly disclosed today (`DataBasisNote`/`LATEST_REVISED_DATA` explanation) for current results. **It becomes a much sharper problem for any historical relationship feature**: a "what happened when X and Y diverged in 2019" query, computed on today's latest-revised data, may not describe what analysts genuinely saw and reacted to in 2019 — the revisions themselves could have changed which periods even qualify as "diverging." **Frozen boundary: any Relate/Compare V1 feature that stays in the *current* period (composition, current-evidence drill-down, curated current-pair compare) is unaffected by this limitation and safe to ship. Anything historical must carry an explicit, prominent latest-revised-reconstruction disclosure, is inherently lower-confidence than a current-period statement, and is exactly why §18 is deferred.**

---

## §21. Beginner and expert experience findings

**Beginner:** should never be required to understand correlation, alignment, or transformation vocabulary to get value from Relate — the composition-only Monitor-level surface (§14/§23) meets this bar entirely: it's two plain-language state badges and one sentence, identical in reading difficulty to what Current State already does today. Any Compare surface with real statistical controls (§4) is, by definition, not beginner-safe without heavy guardrails, and should not be the default entry point.

**Expert:** a curated-only relationship surface would likely feel restrictive to an expert who wants to inspect the actual numbers — but the product already has the right progressive-disclosure precedent (badge → "why" → evidence → methodology, `docs/product/product-experience-audit-v1.md` §12 scored this 4/5, the product's own strongest pattern). The same shape (simple composed relationship → each monitor's own already-existing evidence → eventually, once safe, a deeper series-level compare) satisfies both audiences without turning EI into a statistics course, matching the explicit instruction not to.

---

## §22. Open vs. Curated vs. Hybrid Compare model

| Model | Pros | Risks | V1-ready? |
|---|---|---|---|
| A — Open (any two series) | Maximum flexibility | Meaningless comparisons (§4/§9), transformation burden on the user, generic-dashboard drift (the exact risk the prompt's own "Product Risk" section names) | **No** |
| B — Curated (validated pairs: Core CPI vs. Core PCE, Employment vs. Unemployment, Headline vs. Core within one domain) | Safe today, reuses the existing `/analysis/compare` endpoint as-is for pairs already known to be unit/frequency-compatible, intelligence-oriented | Less flexible | **Yes, for a narrow set** |
| C — Hybrid (curated defaults + advanced custom compare, gated behind disclosure) | Serves both audiences eventually | Requires the statistical-method contract (§4/§9) before the "advanced" half is safe | **Partially** — curated half only, today |

**Recommendation: Hybrid is the correct long-term model; Curated is the only safe V1.** Open compare should not exist until the statistical-method contract in §4/§9 is frozen.

---

## §23. Monitor-level Relate — audited

The prompt's own hypothesis sketch (§22 of the prompt): Inflation/Labor states shown together, one composed sentence, "why" drill-down into each monitor's own evidence, an optional deeper compare. **Audited and endorsed**: this fits EI's identity — deterministic, evidence-linked, no series picker required — far better than starting from a generic series-selection screen, which is exactly the "smaller macro dashboard" risk. It requires **zero new backend calls beyond what Overview already fetches** (both monitors' current results are already on the page) and **zero new methodology** (pure composition, §15). The only genuinely new work is a small, deterministic sentence-template contract (how to phrase "X while Y" for every `(InflationState, LaborState)` pair, honestly, without inventing a label) — a contract-freeze-sized decision, not a research increment.

---

## §24. User journey — Overview to Relate

**START:** Overview shows "Inflation: COOLING" / "Labor: STRENGTHENING." **USER ASKS:** "How should I understand these together?" **SMALLEST USEFUL NEXT STEP:** a composed, plain sentence, either inline on Overview or one click away on a small Relate surface — "Inflation is cooling while Labor is strengthening." — followed by two links, "Why Inflation is Cooling →" and "Why Labor is Strengthening →" (both already-existing evidence, no new methodology). **NOT** a verdict, a score, or investment framing — the sentence stops at composition. This is achievable with existing data and no backend change.

---

## §25. User journey — Inflation internal ("Are CPI and PCE telling the same story?")

**Already answerable today**, fully: `/inflation`'s `ConfirmationPanel` shows exactly this — `ConfirmationRelationship` (`CONFIRMS`/`DIVERGES`/`INCONCLUSIVE`/`UNAVAILABLE`), with both series' own states visible. **Nothing missing for this specific question.** A Compare surface would add only redundant, less-trustworthy raw-correlation noise on top of an already-correct, already-methodology-backed answer — not recommended for this journey specifically.

---

## §26. User journey — Labor internal ("Payrolls are cooling. Is unemployment confirming that?")

**Partially answerable today**: `WhyLaborState` shows both `EmploymentState` and `UnemploymentTrendState` side by side, and `LaborState` itself (via `combine_labor_state`) already encodes whether they're in one of the 4 clean-agreement cells or defaulted to `MIXED` — but the UI never says the word "confirming"/"not confirming" explicitly; the user has to infer it from seeing `MIXED` and reading two badges. **A dedicated, explicit relationship sentence here (reusing §13's finding — zero new methodology) would materially improve comprehension** — this is one of the two safest, highest-value, lowest-cost candidates for V1 alongside §24's cross-domain composition.

---

## §27. User journey — custom series ("Compare unemployment with the 10-year Treasury yield")

**Not supportable today**, and the exact missing pieces are now precisely known: (1) the 10-year Treasury yield series may or may not be persisted (no curated mapping exists for it at all — it's outside the six curated V1 releases); (2) even if persisted, the correlation-safety gaps in §4 apply in full (yield levels are highly non-stationary; a naive correlation would very likely be spurious); (3) no frequency-compatibility signal exists (§5/§7 — yields are typically daily, UNRATE is monthly) to warn the user. **Supporting this today would move EI directly toward the "smaller macro dashboard" risk the prompt warns against, not away from it — this specific journey is a strong argument for NOT building Open Compare in the near term.**

---

## §28. Recommended product surface

**Primary: Option 4 (Overview cross-domain relationship card) as the entry point, backed by Option 3 (relationship content inside monitor pages) for the within-domain half — not a standalone `/compare` or `/relate` route yet.**

| Option | Job solved | Strength | Risk | Backend req. | Methodology req. | Verdict |
|---|---|---|---|---|---|---|
| 1. Standalone `/compare` | Open series compare | Flexible | Unsafe today (§4/§9), premature nav commitment | Statistical-method contract | New statistical contract | **Not V1** |
| 2. Standalone `/relate` | Cross-domain relate as its own destination | Discoverable | Premature — not enough content yet for a whole page; risks feeling like a thin, disconnected surface | None | None (composition only) | **Not V1**, revisit once content grows |
| 3. Relationship sections inside monitor pages | Within-domain relate (§26) | Reuses existing page structure, zero new nav | None significant | None | None | **V1 — Labor page gets an explicit Employment/Unemployment relationship sentence** |
| 4. Overview cross-domain relationship card | Cross-domain compose (§24) | Matches where the user already asks the question; zero new backend | Must stay disciplined to composition, never drift into inference | None | None | **V1 — primary surface** |
| 5. Hybrid progressive model | Long-term target | Serves all audiences eventually | Not achievable until statistical contract + curated compare both exist | Staged | Staged | **Long-term direction, not V1** |

---

## §29. Navigation / IA recommendation

**No new top-level nav item yet.** Both V1 surfaces (§28) live inside existing pages — a new card on Overview, a new sentence/section on `/labor` (and, if warranted later, a parallel one on `/inflation`, though Confirmation already fills that role there). A standalone `/compare` or `/relate` route should wait until either (a) the statistical-method contract makes a real Compare workspace safe, or (b) the composition-only Relate content on Overview/monitor pages grows enough to justify its own destination rather than being a sub-section. Freezing a nav slot now would commit to an IA decision ahead of the content that should justify it.

---

## §30. FRED / generic-AI / chart differentiation

**FRED:** cannot state "Inflation is cooling while Labor is strengthening" as one already-computed fact — a FRED user would have to know to look up two different series, mentally classify each, and combine them themselves. EI's differentiation is real: the *classification* work is already done and maintained.

**Generic AI:** *currently delivered* differentiation — exact evaluation periods, versioned methodology IDs, exact underlying evidence, reproducibility, revision awareness (all real today per the #21 audit's own §15). *Aspirational* — nothing here changes that; a Relate sentence built from already-canonical facts inherits the same currently-delivered guarantees. Generic AI, asked "how are inflation and labor related," would produce a plausible-sounding, non-reproducible, non-evidence-linked answer with no way to verify it against a specific, versioned methodology — EI's composed sentence can always be traced back to two exact `ConfirmationRelationship`/`LaborState` values as of an exact period.

**Chart:** "put two lines on a chart" would show correlation *visually* but would not state, maintain, or explain a *classification* — no chart, by itself, says "these are COOLING and STRENGTHENING as of this period, and here's why, with evidence." The maintained-intelligence layer (classification + evidence + reproducibility) is what a chart cannot replace, confirming the proposed Relate feature clears the "why not just a chart" bar the prompt sets.

---

## §31. Methodology classification by feature (mandatory)

| Feature | Classification |
|---|---|
| Cross-domain state composition (Inflation + Labor sentence, §24) | **NO NEW METHODOLOGY** |
| Explicit Employment/Unemployment agreement sentence (§26) | **NO NEW METHODOLOGY** |
| "Why" drill-down reusing existing evidence | **NO NEW METHODOLOGY** |
| Curated Compare (Core CPI vs. Core PCE, Employment vs. Unemployment, using the existing endpoint as-is) | **NO NEW METHODOLOGY** (existing math; curation is a product decision, not a methodology) |
| Open/generic Series Compare exposed safely | **STATISTICAL METHOD REQUIRED** (minimum-sample floor, transformation defaults/warnings, frequency-compatibility check — all statistical-contract decisions, not economic-conclusion decisions) |
| Cross-domain regime labels (Goldilocks/bullish/etc.) | **NEW METHODOLOGY REQUIRED** (rejected/deferred per explicit instruction) |
| Historical outcome relationships (§18) | **HISTORICAL VALIDATION REQUIRED** (not ready) |
| Lead-lag discovery | **STATISTICAL METHOD REQUIRED + HISTORICAL VALIDATION REQUIRED** (not ready, explicitly out of scope) |

---

## §32. Architecture / data gaps, classified

| Gap | Classification |
|---|---|
| Cross-domain composed sentence on Overview | **Frontend-only** — both states already fetched |
| Explicit Employment/Unemployment relationship sentence on `/labor` | **Frontend-only** — both states already in `LaborMonitorResult` |
| Curated Compare UI (2–3 known-safe pairs) | **Existing backend sufficient** — `/analysis/compare` as-is |
| Minimum-usable-pairs floor for correlation | **Backend contract extension** (a new constant/validation, not a new domain) |
| Default/warned transformation for Compare | **Backend contract extension** (or frontend-enforced default calling `/analysis/pipeline` instead of `/analysis/compare`) |
| Frequency/seasonal-adjustment metadata on persisted series | **New persistence requirement** (schema addition to `EconomicSeries`, or a live FRED lookup per request) |
| Concept/unit-compatibility signal for arbitrary pairs | **New persistence + new deterministic domain logic** |
| Persisted historical monitor-state history | **New persistence requirement** |
| Cross-domain regime methodology | **New deterministic domain methodology** (deferred, needs research first) |
| Historical outcome relationships | **Future vintage/revision + historical-validation requirement** |

---

## §33. State-history requirement (restated per explicit instruction)

See §19 in full. Summary: blocks historical comparison and regime analysis; does **not** block current composition or since-last-visit framing (client-local). This should influence roadmap ordering — state history is a real future increment, but not a prerequisite for the V1 recommended in §35.

---

## §34. Revision / vintage boundary (restated per explicit instruction)

See §20 in full. Summary: current-period composition is unaffected and safe; anything historical needs an explicit, prominent disclosure and is inherently lower-confidence — one more reason §18's historical relationships stay deferred.

---

## §35. Minimum useful V1

**Two small, additive, zero-new-backend features, both composition-only:**

1. **Overview cross-domain relationship line** (§24/§28 Option 4): one composed sentence beneath (or beside) the existing Current State peer cards — "Inflation is {state} while Labor is {state}." — using a small, frozen, exhaustive sentence-template table over `(InflationState, LaborState)` (25 cells, all composition, no labels), each linking to that monitor's own existing "why" evidence. Materially better than FRED (no classification exists there), a chart (no maintained classification), generic AI (not reproducible/versioned), or the current side-by-side cards alone (which state nothing about the *relationship*, only the two facts independently).
2. **Labor page Employment/Unemployment relationship sentence** (§26/§28 Option 3): one sentence inside `WhyLaborState` (or immediately beside it) stating, in plain language, whether Employment and Unemployment are sending a consistent or inconsistent signal — derived entirely from the already-canonical `LaborState` value (MIXED already means "inconsistent"), zero new methodology.

Both are answerable-better-than-FRED/chart/AI/current-cards, both require zero backend changes, and both stay strictly within composition (§15).

---

## §36. Explicit do-not-build list

Cross-domain economic score. Goldilocks/Stagflation/any regime label. Bullish/bearish labels. Market predictions or investment recommendations. Lead-lag discovery. Causal inference of any kind. Automatic correlation mining across arbitrary series. AI-generated relationship narration. Arbitrary open series-vs-series spread. A large charting workspace. Historical backtesting. A standalone `/compare` or `/relate` nav route this increment. Any new backend endpoint, table, or migration this increment.

---

## §37. Implementation readiness classification

- **Cross-domain composition (Overview relationship line) and within-domain Labor relationship sentence: READY FOR IMPLEMENTATION**, pending one narrow contract freeze — the exact sentence-template wording for all 25 `(InflationState, LaborState)` cells and the Labor consistent/inconsistent phrasing — a #23B-sized freeze, not a research increment.
- **Curated Compare (2–3 known-safe pairs): READY FOR IMPLEMENTATION at the backend-reuse level**, but needs its own small contract freeze (exactly which pairs, exact disclosure copy about what correlation over levels does and doesn't mean even for a curated pair) before frontend work.
- **Open/generic Compare: RESEARCH / CONTRACT FREEZE REQUIRED FIRST** — the statistical-method contract in §4/§9 does not exist and must be defined and frozen before any implementation.
- **Cross-domain regime labels, historical relationships, lead-lag: RESEARCH REQUIRED, not sequenced at all in the #23 series.**

---

## §38. Recommended next increment

**#23B — Relate Composition Contract Freeze** (mirrors the #22A pattern: audit-to-freeze, not audit-to-code): freeze the exact sentence-template table for the Overview cross-domain relationship line (all 25 `(InflationState, LaborState)` cells, honest composition-only wording, verified against §15's boundary and §16's vocabulary rule), the exact Labor Employment/Unemployment relationship sentence wording (derived from `LaborState`, verified against §13), placement/heading decisions for both, and a full #23C test matrix — mirroring #22A/#22B's own process. **#23C** then implements it, frontend-only, zero backend change, exactly as #22B did for its own frozen contract.

**Why this is the bottleneck:** it is the smallest, safest, most evidence-grounded step that actually starts answering "How does it relate?" — the product's last unaddressed core job — without touching the two things this audit found genuinely unsafe today (open correlation, cross-domain labeling).

**Why not Compare instead:** Compare's own path (§9/§4) requires a real statistical-method contract (minimum-sample floor, transformation defaults, frequency/unit-compatibility signals) that does not exist yet — building it first would either ship an unsafe raw-correlation tool or consume a full increment on backend/methodology work before any user-visible progress on the actual most-asked question ("how does it relate," not "let me pick two series").

**What success looks like:** a user on Overview can read one sentence that composes Inflation's and Labor's current states without a click, a user on `/labor` can read whether Employment and Unemployment are sending a consistent signal without re-deriving it themselves, and neither sentence ever uses a word not already earned by an existing canonical value.

**What we should explicitly NOT build in #23B/#23C:** everything in §36.

---

## §39. Runner-up

**Curated Compare (Model B, §22/§28)** — reusing the existing `/analysis/compare` endpoint as-is, restricted to a small, hand-picked, pre-vetted-compatible pair list (Core CPI vs. Core PCE at minimum; Employment vs. Unemployment if a rate-normalized pairing can be defined honestly). It comes second, not first, because even the curated version needs its own small contract freeze (exact pairs, exact disclosure copy) that the composition work in §35 does not, and because it adds a genuinely new UI surface (a compare view) rather than extending two pages that already exist — more implementation surface for a comparable amount of user value. Named ahead of historical context, state history, Growth, and retention/save because it is the most direct continuation of this specific audit's own findings and reuses backend capability that already exists and is already safe for this narrow scope.

---

## §40. Product thesis test

**The recommended V1 strengthens, and does not require changing, the current positioning** ("Know what changed in the economy — and prove why.") — both recommended features are instances of "prove why," extended from single-monitor evidence to a composed, honest, two-monitor statement, never a new economic claim. The positioning does **not** need to evolve to the prompt's own suggested alternative ("...understand how it connects...") for this V1 specifically — that broader phrasing would be earned once Compare (§39) or a richer Relate surface exists, not yet. Recommend leaving positioning unchanged for now and revisiting after #23C ships.

---

## §41. GO / STOP standard applied

Per the explicit instruction, GO here means "the audit successfully identified the correct next path," not "ready to code." This audit found a clear, evidence-grounded, safe, zero-new-backend next step (§35/§38) and equally clearly identified what is **not** ready (§4/§9/§17/§18, all requiring their own future research/contract work before implementation). Both halves are necessary for a true GO under this standard, and both are present.

**Classification: READY FOR IMPLEMENTATION for the composition-only Relate work (pending #23B's own narrow sentence-template freeze). RESEARCH / CONTRACT FREEZE REQUIRED FIRST for anything Compare, historical, or cross-domain-labeled.**

---

## Appendix: secret safety and version control

No `.env`/`.env.*`/credential file was read, printed, or logged at any point this increment. The backend test run used the project's established local isolated-Postgres mechanism (trust-auth, no password). Nothing in this document was committed or pushed; the working tree outside this new file was not modified.
