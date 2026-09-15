# Post-Return-Loop Product & Commercial Readiness Audit — V1

**Increment #26A.** Read-only product and commercial audit. No production code changed, no migrations added, no APIs created, no AI added, no new methodology, nothing committed, nothing pushed. Baseline: HEAD `f1006d3` ("Add Since Last Visit V1 frontend (#25H)"), clean working tree. Verified fresh this increment: backend 1,463/1,463 passed twice, 0 skipped; frontend 1,137/1,137 passed twice; `tsc -b --noEmit` clean; `oxlint` clean; `vite build` clean.

This audit is evidence-based, not backend-capability-driven: every claim is grounded either in the actual running product (the local dev frontend at `localhost:5173` against the local dev backend at `localhost:8000`, inspected live via browser automation this increment) or in current repository source, with file/line references where load-bearing. Where the two disagree — code says one thing, the running app does another — the running app wins, and the disagreement is itself reported as a finding.

---

## 1. Required reading — what changed since each prior audit

All seven required documents were read in full this increment: `product-experience-audit-v1.md` (#21), `relate-compare-audit-v1.md` (#23A), `historical-context-state-history-audit-v1.md` (#24-series), `post-state-duration-product-loop-retention-audit-v1.md`, `automated-economic-maintenance-v1.md` (#25A/B), `recorded-state-history-v1.md` (#25D), `since-last-visit-v1.md` (#25F). Two more, not in the required list but directly load-bearing for the capability inventory, were also consulted fresh from source: `relate-composition-v1.md` (#23B) and `state-duration-v1.md`.

| Prior finding | Status now |
|---|---|
| #21 §33: Overview's What Changed preview can crowd out real state changes with routine noise (salience gap) | **SOLVED** — `overview-attention-model-v1.md`'s salience tiering shipped (confirmed live: Overview's "What Changed" cards now say "No structural change. Metric updates (14)" rather than listing 14 routine rows, and "Previous-period comparison unavailable" for Labor rather than noise) |
| #21 §19: release rows and Latest-Data-Detected items are hard dead ends | **PARTIALLY SOLVED** — `ReleaseRow`'s `showMonitorCta` (§22B) adds a working "View Inflation →"/"View Labor →" link, but confirmed by fresh code read (§2 below) that this CTA is opt-in and rendered **only** by Overview's `UpcomingReleasesPreview`; `/releases` itself (`ReleaseCalendarSection`) and Overview's own "Recently" row (`RecentReleasePreview`) still render no link. The dead end is narrowed, not closed. |
| #21 §5/§30: "How does it relate?" scored 1/5, least-developed job | **MATERIALLY IMPROVED** — Relate Composition V1 (#23B/#23C) shipped and confirmed live: Overview now renders "Inflation is Mixed as of July 2026. Labor does not currently have enough data to classify its state." Composition-only, exactly as `relate-compare-audit-v1.md` §14/§15 froze it. Re-scored in §7 below. |
| #21 §22: historical context ("is this number high or low?") entirely absent | **PARTIALLY SOLVED** — State Duration V1 shipped and confirmed live on `/inflation`: "Mixed for 2 consecutive months, since June 2026. Previously Heating, as of May 2026." This is temporal self-context (how long has this been true, what was it before), not range/percentile context — `historical-context-state-history-audit-v1.md`'s own scoped distinction, still accurate. |
| #21 §18/§32C: no since-last-visit concept, retention loop weak | **BUILT, BUT NOT CURRENTLY WORKING IN THE RUNNING APP** — see §2's critical finding. The backend (#25G) and frontend (#25H) are both fully implemented, fully tested (88 + 105 new tests), and architecturally sound per fresh code review. The live dev deployment returns **HTTP 500** on every request to it right now. |
| #25D/#25E: Recorded State History — durable proof EI's own canonical computation genuinely ran | **SHIPPED, BACKEND-ONLY, NOT PRODUCTIZED** — no frontend surface exists or was ever planned for #25E itself; correctly scoped as history-recording infrastructure for #25G/#25H to consume, which they now do. Reassessed as its own candidate in §13. |
| `relate-compare-audit-v1.md` §35/§38: recommended Relate Composition as next move, Curated Compare as runner-up | Relate Composition **shipped** (#23C). Curated Compare **still not built** — reassessed fresh in §13. |
| `automated-economic-maintenance-v1.md`: automated scheduler/orchestrator design | **SHIPPED, but activation status could not be confirmed to be running continuously in this environment** — see §15. |

**No prior finding was found to be wrong.** One prior finding (`since-last-visit-v1.md`'s own "READY FOR #25H" and #25H's own "RETURN LOOP CLOSED" verdict) is **superseded by fresh evidence**: the loop is closed in code and tests, not in the actual deployed product a target user would open today.

---

## 2. Live product inspection — what actually happens when a user opens the app

Both the frontend dev server (`localhost:5173`) and backend (`localhost:8000`) were already running against the project's local dev PostgreSQL database (`economic_intelligence` — distinct from the `economic_intelligence_test` database the test suite uses). The product was inspected as a user would: real navigation, real page loads, real network requests, screenshots taken.

### 2.1 Critical finding: Since Last Visit is broken in the running app

Opening `/` (Overview) — the product's own designated entry point — shows, as the very first section on the page, above Current State:

> **Recent Economic Activity**
> Recent activity could not be loaded.
> [Retry]

Network inspection confirms `GET /api/v1/since-last-visit` returns **HTTP 500**, body `{"detail":"Database error while reading since-last-visit data."}`. Root-caused, read-only, without modifying anything: `alembic current` against the dev database reports `09f4c0959e9f`; `alembic heads` reports `f5420059a092` (the #25E migration that creates `recorded_monitor_results`). Direct `\dt` inspection of the dev database confirms `recorded_monitor_results` does not exist there — the table `SinceLastVisitRepository` queries for every request is simply missing from the database the live app is pointed at. The `economic_intelligence_test` database used by the pytest suite **is** at head, which is exactly why every automated test passed while the actual running product fails on the first thing it shows a user.

**This was not fixed as part of this audit** (no migrations, no infrastructure changes — audit is read-only), but it is reported here as the single most consequential fact this increment discovered, because:

- It is **not a design flaw** — the #25F/#25G/#25H contract, code, and tests are all correct; this is a **deployment-application gap**, a schema that was never migrated forward after being created.
- It is **not hypothetical** — it was reproduced twice, directly, against the actual running instance, mid-audit.
- It directly breaks the **headline feature of the last three increments** (#25D→#25H), on the **first thing a real user sees**, in a way that visually looks exactly like a generic error card, not a "there's nothing new to report" empty state — a first-time visitor cannot distinguish "the return loop is broken" from "there's genuinely nothing to show."
- It is caused by the complete **absence of any migration-on-deploy automation** (§14 confirms: no CI, no Dockerfile, no deploy manifest of any kind exists in this repository) — meaning this exact failure mode will recur for every future migration unless a real deployment pipeline is built, not just this one table.

This finding directly informs the winner selection in §29-32 and the Return Loop verdict in §35.

### 2.2 Rest of the product, live-confirmed

- **Overview**, below the broken Since-Last-Visit card: Current State (Inflation "Mixed", Labor "Insufficient data" — a genuinely live `INSUFFICIENT_DATA` state, honestly presented, not a bug), How They Relate (correctly composed sentence, correctly degrades to "does not currently have enough data to classify" for Labor rather than fabricating a relationship), What Changed (correctly shows "No structural change. Metric updates (14)" for Inflation — the #22 salience fix visibly working — and "Previous-period comparison unavailable" for Labor), Recent Data Updates (both domains, both "Not yet checked by Economic Intelligence" — meaning automation has not run against this dev database's current data either, consistent with §2.1's finding that this environment isn't being kept current), Releases (3 upcoming + 1 recent, correctly labeled).
- **Inflation**: full depth confirmed live exactly as `product-experience-audit-v1.md` §7 described, **plus** the new State Duration line ("Mixed for 2 consecutive months, since June 2026. Previously Heating, as of May 2026.") rendering correctly above the "Why Mixed?" disclosure.
- **Labor**: every section reads "Insufficient data" — Employment, Unemployment, momentum deltas all `—`, "No evidence available." This is the live data's genuine state (the dev database's labor fixture data does not currently support a classification), honestly presented per the architecture's own INSUFFICIENT_DATA discipline — not a bug, but it does mean this specific environment cannot currently demonstrate Labor's investigation depth to a live viewer; that depth was confirmed instead by direct source inspection (unchanged since #21 §7).
- **Releases**: calendar now spans more categories than two monitors would suggest — CONSUMER (Advance Retail Sales), LABOR (JOLTS, Employment Situation), GROWTH (GDP), INFLATION/CONSUMER (Personal Income and Outlays), INFLATION (CPI) all appear with real scheduled/past-due dates. **The release calendar already tracks Growth- and Consumer-category releases that no monitor consumes** — a real, concrete asymmetry between data breadth (already broad) and monitor breadth (still two), relevant to candidate B/G reassessment in §13.
- **Navigation**: exactly four destinations exist — Overview, Inflation, Labor, Releases (`layouts/AppShell.tsx`'s `NAV_LINKS`, confirmed both from source and the rendered header). No Search, Compare, Save, Account, or Settings entry anywhere.
- **Dead-end re-audit**: release rows on `/releases` itself and Overview's "Recently" row remain non-clickable (confirmed both live and in `ReleaseRow.tsx`/`RecentReleasePreview.tsx` source — only `UpcomingReleasesPreview` opts into `showMonitorCta`). Narrower than #21 found, not closed.

---

## 3. Full capability inventory

Classification key: **SHIPPED+USEFUL** (built, correct, and currently valuable to a target user) · **SHIPPED+WEAK** (built and reachable, but thin, unreliable, or low-value as shipped) · **TECHNICALLY PRESENT, NOT PRODUCTIZED** (real backend/domain capability with no frontend surface a user can reach) · **BACKEND ONLY** (exists purely as infrastructure/API, was never intended to be user-facing) · **PLANNED-ABSENT** (does not exist in any form).

| Capability | Classification | Evidence |
|---|---|---|
| Overview (aggregated current state) | **SHIPPED+USEFUL** | 4-section live page, failure-isolated per section, confirmed live |
| Inflation monitor | **SHIPPED+USEFUL** | Full depth confirmed live: state, momentum, target, confirmation, headline context, evidence, methodology, state duration |
| Labor monitor | **SHIPPED+USEFUL** (architecturally) | Full depth confirmed by source (unchanged since #21); this specific environment's data currently renders it as `INSUFFICIENT_DATA` throughout |
| What Changed (salience-tiered) | **SHIPPED+USEFUL** | #22's fix confirmed live — routine noise no longer crowds out structural change on Overview |
| Recent Data Updates / Latest Data Detected | **SHIPPED+WEAK** | Structurally sound (DATA vs. INTELLIGENCE split, per-domain since #22), but #21 §11's rename recommendation was never acted on — still reads as a pipeline-log entry ("Not yet checked by Economic Intelligence") rather than a user-facing fact |
| Releases calendar | **SHIPPED+USEFUL** | Correct schedule-vs-publication discipline, confirmed live, now spans more categories than monitors exist for |
| How They Relate (Relate V1) | **SHIPPED+USEFUL** | Confirmed live, composition-only, exactly matches its frozen contract; correctly degrades under `INSUFFICIENT_DATA` |
| State Duration | **SHIPPED+USEFUL** | Confirmed live on Inflation; answers "how long has this been true / what was it before" — a real, if narrow, historical-context win |
| Since Last Visit (return loop) | **SHIPPED, CURRENTLY NON-FUNCTIONAL IN THE RUNNING APP** | See §2.1 — the one capability in this inventory whose code/test status and live status genuinely diverge |
| Recorded State History (backend persistence) | **BACKEND ONLY** (by design) | No frontend surface exists or was ever scoped for #25E itself; consumed internally by #25G/#25H |
| Progressive-disclosure explanation system | **SHIPPED+USEFUL** | One consistent system across all four pages, unchanged strength from #21 §12 |
| Series discovery / search | **TECHNICALLY PRESENT, NOT PRODUCTIZED** | `GET /api/v1/series/search` real and tested; zero frontend import anywhere |
| Raw series compare / correlation / spread | **TECHNICALLY PRESENT, NOT PRODUCTIZED** | `/analysis/compare`, `/analysis/pipeline` real; zero frontend import; `relate-compare-audit-v1.md` §4 found raw correlation unsafe to expose as-is without a statistical-method contract |
| Deterministic transformations (pct change, moving average) | **TECHNICALLY PRESENT, NOT PRODUCTIZED** | `/series/{id}/transform` real, tested, unused by frontend |
| AI query (read-only, tool-calling, grounded) | **BACKEND ONLY** | `/api/v1/ai/query` registered and routed (`app/main.py`); zero frontend reference outside architecture-guard test files that assert it must stay that way |
| Automated release-driven maintenance | **SHIPPED, ACTIVATION UNCONFIRMED IN THIS ENVIRONMENT** | Scheduler/orchestrator code and tests are real (#25A/B); this dev environment's own Overview shows "Not yet checked by Economic Intelligence" against September/December dates already past, and the dev DB is behind on migrations — together suggesting this particular instance is not being kept continuously current, though that is an environment fact, not a code defect |
| Save / Watchlist | **PLANNED-ABSENT** | No accounts, no persistence layer, no UI |
| Accounts / cross-device | **PLANNED-ABSENT** | Confirmed absent everywhere, zero auth code, zero session concept |
| Notifications / alerts | **PLANNED-ABSENT** | Confirmed absent |
| Search/Explore frontend | **PLANNED-ABSENT** | No route, no UI, despite a real backend behind it |
| Charts / visualization | **PLANNED-ABSENT** | Confirmed absent from every page; all values are numbers/badges/text |
| Growth monitor | **PLANNED-ABSENT** | No domain module, no methodology; GDP release dates are tracked in the calendar with no monitor to attach to |
| Rates / Financial Conditions monitor | **PLANNED-ABSENT** | No domain module, no series curated for it |
| Market layer (equities/yields/etc.) | **PLANNED-ABSENT** | No series, no domain, no UI |
| Deployment automation (CI, container, deploy manifest) | **PLANNED-ABSENT** | Confirmed by direct file search: no Dockerfile, no docker-compose, no `.github/workflows`, no Procfile/fly.toml/render.yaml anywhere in the repository |
| Product analytics / telemetry | **PLANNED-ABSENT** | Confirmed by full-tree search: no analytics/telemetry/error-tracking library or call anywhere in frontend or backend |
| Onboarding / first-use experience | **PLANNED-ABSENT** | Confirmed by full-tree search: no onboarding, welcome, tour, or first-run concept anywhere |

---

## 4. Re-run experience tests (as a target user, not as architecture)

**First 60 seconds** (Overview, cold): a first-time visitor sees a broken-looking card at the very top of the page ("Recent activity could not be loaded. Retry") before anything else loads. This is a materially worse first impression than #21 ever measured, and it is new — #21 never had this section to evaluate. Below it, Current State is genuinely clear (unchanged strength), What Changed is now trustworthy (the #22 fix), and How They Relate adds a real, immediate answer to "how do these connect" that did not exist at #21. **Net: the product got better where it was audited before, and acquired one new, serious first-impression defect where it wasn't.**

**First visit, no account, no history**: correctly handled by design — `first_visit: true` semantics exist and are tested — but cannot currently be observed end-to-end live because of §2.1. On the merits of the design alone (which is what a fixed deployment would show), first-visit correctly bounds to a 90-day window rather than an unbounded dump, and states "Recent Economic Activity" rather than falsely implying a personalized return.

**Five minutes**: a user can genuinely investigate Inflation in real depth (state → why → evidence → methodology), read a real relationship sentence, and see how long the current state has held — three real, evidence-backed answers in under five minutes for the domain with real data. Labor cannot currently demonstrate this depth in this specific environment (data-limited, not code-limited).

**Day two**: nothing changes unless the user manually revisits and re-reads; the mechanism to make day-two meaningfully different (Since Last Visit) exists in code but is not currently reachable.

**Week two / month two**: State Duration begins to compound ("Mixed for 6 consecutive months" reads very differently from "Mixed for 2") — a real, small, genuine reason to return that #21 did not have. Recorded History (once productized, §13) would compound further. Today, absent Since Last Visit actually working, week-two and month-two visits are still functionally identical to a first visit's Investigate depth, just with a longer state-duration sentence.

---

## 5. Product loop and investigation depth reassessment

The Monitor → Investigate → Relate loop is now more complete than at #21: Monitor's own salience defect is fixed, Investigate remains the product's strongest dimension unchanged, and Relate — entirely unserved at #21 (1/5) — now has a real, safe, working composed answer. The loop's weak point has moved from "the entry page misrepresents what matters" (#21's finding, now fixed) to "the entry page's own newest section currently fails outright" (§2.1, a regression introduced by an operational gap, not a design one) and "nothing differentiates a return visit from a first visit in the running product" (unchanged in effect, though not in design). Investigation depth is unchanged and remains genuinely strong — full component breakdown, evidence, methodology, now plus state duration, all reachable in ≤2 clicks.

---

## 6. JTBD scoring (1-5, with explanation)

| Dimension | Score | Explanation |
|---|---|---|
| What Is Happening | **5/5** (was implicitly ~4 at #21) | Current State + State Duration together now answer both "what" and "for how long," live-confirmed, with zero click required for the headline fact |
| What Changed | **4/5** (was ~3, noise-limited) | The #22 salience fix is confirmed live and working; the one remaining gap is Recent-Data-Detected's still-unrenamed, pipeline-flavored copy (#21 §11, never acted on) |
| How Does It Relate | **4/5** (was 1/5) | Relate V1 gives a real, safe, always-present composed sentence; capped below 5 because it stops at composition by design (no cross-domain "why," which is the correct, deliberate boundary, not a shortfall to fix casually) |
| Compare | **1/5** (unchanged) | Zero frontend surface still exists; backend is real but, per `relate-compare-audit-v1.md` §4, unsafe to expose generically without a statistical-method contract that still does not exist |
| Save | **1/5** (unchanged) | No accounts, no persistence, confirmed absent |
| Return | **2/5** (down from a would-be 4/5 on design merit alone) | The mechanism is well-designed and fully tested, but as experienced by an actual user opening the actual running app today, it visibly fails — scored on what a user experiences, not on what the code proves it could do |
| Trust | **4/5** (unchanged from #21) | Methodology IDs, evidence tables, explicit revision framing, provably no AI in the canonical path, all still true; same minor internal-string overexposure noted at #21 persists |
| Explainability | **4/5** (unchanged) | Still the product's most consistently strong dimension; nothing volunteers itself without a click, unchanged |
| **Professional Credibility** | **3/5** (new dimension) | The analytical content itself (methodology versioning, evidence tables, deterministic reproducibility) would read as credible to a professional user; the visible broken card on the very first page, the complete absence of charts, and zero polish around error states for a still-obviously-early product pull this down from what the underlying rigor alone would earn |

---

## 7. Willingness-to-pay, workflow-replacement, and competitive tests

**WTP test.** Unchanged from #21's own finding in substance: the smallest missing capability that would most increase willingness to pay is not a new feature, it is **reliability of what already shipped** — a paying user who hits the exact 500 error found in §2.1 on their very first visit would reasonably conclude the product is unfinished, regardless of how sound the Inflation page underneath is. This reframes #21's "reliable change salience" finding (solved) into "reliable everything" as the new smallest-gap-to-close for WTP.

**Workflow-replacement test.** For the two supported domains, EI genuinely replaces "manually check FRED/BLS release calendars, re-derive momentum classifications, remember what I saw last time" — the first two clauses are strongly delivered (unchanged from #21), the third (remembering what was seen last time) is designed but not currently delivered live.

**FRED.** Unchanged core differentiation (classification + revision tracking FRED does not offer) plus two new advantages: Relate (FRED cannot state a composed relationship) and State Duration (FRED's charts show duration visually but do not narrate it as a fact tied to a classification). FRED still wins outright on charts/visual history.

**TradingView-class dashboards.** Not previously compared directly. TradingView offers breadth (thousands of series/instruments), charting, alerts, and a social/community layer — all things EI has none of. EI's answer is the same as its generic-macro-dashboard answer at #21 §16: a maintained, deterministic, evidence-linked classification and change-detection layer, now extended with Relate and State Duration — genuine but still under-asserted content, visually still reading as "a smaller, quieter dashboard" to a first glance, with the added risk this increment that "smaller and quieter" this week specifically includes "and currently shows an error."

**Generic AI.** Unchanged, still the product's clearest, most defensible differentiation (#21 §15): reproducibility, versioned methodology, exact evidence, provably not AI-generated in the canonical path. Relate's own composed sentence inherits the same guarantees (traceable to two exact, versioned states) — genuinely stronger than an AI's un-versioned, unreproducible prose answer to the same question.

**Institutional platforms** (Bloomberg/Refinitiv-class). Not previously compared. These offer enormous breadth, real-time data, and deep analytics at a price point and integration depth EI is nowhere near — the honest positioning is not "a Bloomberg alternative" but "a narrow, deterministic, evidence-linked intelligence layer for two specific macro domains," which the product already implicitly is and should not attempt to out-broaden.

**Professional workflow mapping.** A working analyst's actual inflation/labor check-in workflow (open FRED or an internal dashboard, note the latest print, mentally classify momentum, check if a prior view changed) maps closely onto Monitor+Investigate+Relate as shipped — the parts EI cannot yet replace are charting (visual trend-spotting) and cross-series work beyond the two curated domains.

**Decision-support / actionability boundary.** Unchanged and correctly conservative: EI states classifications and evidence, never a recommendation, prediction, or market-implication — confirmed still true live (no such language found anywhere in fresh inspection), consistent with the product's own explicit prohibitions.

**Information density.** Unchanged findings from #21 stand; State Duration and Relate both add exactly one line each and do not measurably increase clutter — confirmed live, both render as single, terse sentences.

---

## 8. Candidate reassessment (existing/near-term surfaces)

| Candidate | #21/#23A status | Status now | Verdict |
|---|---|---|---|
| **Curated Compare** | Runner-up at #23A, not built | Still not built. Backend (`/analysis/compare`) unchanged, still safe only for a curated, pre-vetted pair per `relate-compare-audit-v1.md` §22 | Real, safe, scoped candidate — reassessed in §13/§29 |
| **Open Compare** | Explicitly unsafe (#23A §4) | Unchanged — still no statistical-method contract (min-sample floor, transformation defaults, frequency/unit-compatibility) | **DEFER**, unchanged |
| **Growth Monitor** | Deferred at #21 §25 (breadth would worsen the noise problem) | The noise problem it was deferred to avoid is now fixed (§22); but the *new* problem (§2.1: the existing two-domain return loop doesn't work in production) makes adding a third domain now strictly premature for a different reason | **DEFER** — not until deployment is trustworthy |
| **Rates / Financial Conditions Monitor** | Not previously scoped as a named candidate | No domain module, no curated series, no methodology exists; same DEFER logic as Growth | **DEFER** |
| **EI-native Historical Visualization (charts)** | Deferred at #21 §22 in favor of cheaper textual framing | State Duration (textual) shipped exactly as recommended; charts remain unbuilt and still the product's clearest FRED-losing gap (#21 §14) | **LATER** — real gap, not the bottleneck |
| **Search/Explore frontend** | Not exposed (#21 §1) | Still not exposed; backend unchanged | **LATER** — no demonstrated user-facing job currently blocked on it, same as #21's own finding |
| **Save/Watchlist** | Premature at #21 §9 (nothing worth saving reliably yet) | The reliability bar it was waiting on (§22's fix) is now met for What Changed; but Save's own natural pairing, Since Last Visit, is the thing currently broken live — saving into a return loop that doesn't render is not yet worth building | **DEFER** |
| **Accounts / cross-device** | Not built | Unchanged; nothing in this audit changes the calculus — still needed only once Save/cross-device sync is itself justified | **DEFER** |
| **Notifications/alerts** | Correctly flagged as an assumption to avoid at #21 §18 | Unchanged reasoning; would compound the exact reliability risk found in §2.1 if built on top of a return mechanism that doesn't currently work | **DEFER** |
| **Production deployment + automated maintenance activation** | Not previously a named, scored candidate | **Directly, freshly, and concretely validated this increment** by §2.1's live 500 and by §14's confirmed absence of any CI/container/deploy manifest | **BLOCKER — see §29** |
| **Onboarding / first-use experience** | Not previously scored | Confirmed fully absent (§3); genuinely valuable once the product is reliably deployed and there is a stable first impression worth orienting a new user around | **HIGH-LEVERAGE ENHANCEMENT**, sequenced after deployment |
| **Product analytics + beta feedback** | Not previously scored | Confirmed fully absent (§3); without it, no beta (however recruited) produces learnable signal | **BLOCKER-ADJACENT — see §29** (paired with deployment) |
| **Recorded History productization** (surfacing "on this date, Inflation was X" to a user) | Backend-only by design at #25E | Unchanged — #25E correctly scoped this as infrastructure only; a real, compounding future asset (#21 §29) but no frontend job is currently blocked on it | **LATER** |
| **Market layer** | Not previously scored as distinct from Growth/Rates | Same absence, same reasoning as Growth/Rates | **DEFER** |
| **Stop feature development, run a target-user beta** | Not previously scored | Cannot responsibly recruit target users onto a product whose headline new feature 500s on first load and that has no telemetry to learn from a beta even if run | **LATER — sequenced directly after deployment + analytics, not before** |

---

## 9. Deployment, operations, and automation audit

- **Deployment automation**: **absent**. No Dockerfile, no docker-compose, no CI workflow (`.github/workflows` does not exist), no deploy manifest of any kind (Procfile/fly.toml/render.yaml) anywhere in the repository. The only way this product currently runs is two manually-started local dev processes (`vite`, `uvicorn`) against a manually-migrated local Postgres instance — and, per §2.1, even that manual migration step was missed for the current head.
- **Automation activation reality**: the scheduler/orchestrator code from `automated-economic-maintenance-v1.md` is real and tested, but this dev environment's own live Overview page shows both domains as "Not yet checked by Economic Intelligence" against dates already past (September releases), and the database itself is behind on schema migrations — together, strong circumstantial evidence that whatever automation exists is not currently being kept running continuously against this instance's own data. This is an environment-operations fact, not a defect in the automation code itself, which was verified correct by extensive tests in #25A/B.
- **Data freshness UX**: honestly presented where it is stale ("Not yet checked," never fabricated as current) — a real strength unchanged from prior audits — but the *actual* freshness of this instance's data is poor, which compounds the first-impression problem in §4.
- **Data breadth**: broader in the release calendar (6 release types across 4 categories) than in monitor coverage (2 domains) — a real, live-confirmed asymmetry (§2.2) worth resolving in either direction (curate the calendar to only the two covered domains, or treat the asymmetry as a roadmap signal for which domain to build next) rather than leaving it implicit.
- **Search/discovery**: confirmed absent from the frontend despite a real, tested backend (unchanged from #21 §1).
- **Onboarding**: confirmed fully absent (§3) — no first-use framing exists anywhere; a first-time visitor's very first experience today is the broken card in §2.1.
- **Quiet-period vs. high-activity-period experience**: the live Labor page (§2.2) is, in effect, a real demonstration of the "quiet"/data-scarce experience — and it degrades honestly (`INSUFFICIENT_DATA` throughout, never a fabricated state) rather than misleadingly. The "high-activity" experience (multiple structural changes at once) was not observable live in this environment and was evaluated from source/tests instead, unchanged from prior audits' findings that the architecture handles it correctly.
- **User investment / compounding value**: State Duration is a genuine, small compounding asset (a sentence that gets more informative the longer a state holds); Recorded History is a genuine, larger compounding asset once productized; neither compounds if a returning user's own primary reason to return (Since Last Visit) does not currently work.
- **Moat**: unchanged from #21 §29's own finding — the real, already-accruing moat is the revision/change/state history the pipeline has been persisting since #18, now joined by `RecordedMonitorResult`'s durable proof-of-execution history. This moat is real and grows independent of any UI decision, but is currently invisible to a user and undermined operationally by §2.1's finding that the running instance isn't reliably being kept current.
- **Pricing readiness tier**: **NOT READY**. The product has real, demonstrable differentiation (§7) but cannot be sold in its current operational state — a paying user's first click would plausibly hit an error.
- **Free vs. paid value split**: not yet a live question — there is no free/paid distinction anywhere in the product (no accounts), and building one is correctly not on the near-term path per §8's Accounts finding.
- **Beta readiness**: **NOT READY for any beta wider than the current developer's own local testing**, for reasons independent of feature completeness — see §9's own findings plus zero analytics (§3) to learn from one.
- **Should user research precede more code?** No more urgently than deployment reliability does. The product has already accumulated substantial, well-evidenced product-audit findings (#21, #23A, and now this one) without needing external user research to surface them — the clearest next uncertainty is not "what do users want" but "does the product work when a user opens it," which is answerable and fixable without research.
- **Analytics/telemetry**: confirmed fully absent (§3).
- **Feedback loop**: none exists — no comment mechanism, no survey, no contact path, no analytics to infer behavior from.

---

## 10. Weighted decision matrix

Candidates: the 15 named (A–O, using the letters as originally scoped) plus **P**, a candidate discovered during this audit's own live inspection.

- **A.** Curated Compare · **B.** Growth Monitor · **C.** Rates/Financial Conditions Monitor · **D.** EI-native Historical Visualization (charts) · **E.** Search/Explore frontend · **F.** Save/Watchlist · **G.** Accounts/cross-device · **H.** Notifications/alerts · **I.** Production deployment + automated maintenance activation · **J.** Onboarding/first-use experience · **K.** Product analytics + beta feedback · **L.** Recorded History productization · **M.** Market layer · **N.** Stop feature development, run a target-user beta · **O.** Open Compare · **P.** *(discovered this increment)* Fix the live Since-Last-Visit failure and establish migration/deploy reliability so the product works when opened.

Weights (sum to 100%, chosen to reflect this audit's own repeated finding that reliability now outweighs breadth): **User value if it works (25%)** · **Risk reduction / prevents active harm to trust (25%)** · **Effort to ship (20%, higher score = lower effort)** · **Strategic fit with the deterministic, evidence-linked thesis (15%)** · **Urgency of evidence (15%, higher score = more freshly and concretely demonstrated this increment)**.

| Candidate | User value (25%) | Risk reduction (25%) | Low effort (20%) | Strategic fit (15%) | Urgency (15%) | **Weighted total** |
|---|---|---|---|---|---|---|
| **P — Deployment/migration reliability + fix live 500** | 5 | 5 | 4 | 4 | 5 | **4.65** |
| I — Production deployment + automation activation | 5 | 5 | 3 | 4 | 5 | 4.45 |
| K — Product analytics + beta feedback | 3 | 4 | 4 | 3 | 3 | 3.40 |
| J — Onboarding/first-use experience | 3 | 3 | 4 | 3 | 2 | 3.05 |
| A — Curated Compare | 4 | 2 | 3 | 4 | 2 | 3.05 |
| D — Historical Visualization (charts) | 4 | 1 | 2 | 3 | 1 | 2.35 |
| L — Recorded History productization | 3 | 1 | 3 | 4 | 1 | 2.35 |
| N — Stop dev, run beta | 3 | 1 | 5 | 2 | 2 | 2.60 |
| E — Search/Explore frontend | 2 | 1 | 3 | 2 | 1 | 1.85 |
| F — Save/Watchlist | 3 | 1 | 2 | 2 | 1 | 1.90 |
| B — Growth Monitor | 3 | 1 | 2 | 3 | 1 | 2.05 |
| C — Rates/Financial Conditions Monitor | 2 | 1 | 2 | 3 | 1 | 1.80 |
| G — Accounts/cross-device | 2 | 1 | 1 | 2 | 1 | 1.40 |
| H — Notifications/alerts | 2 | 2 | 2 | 2 | 1 | 1.85 |
| M — Market layer | 2 | 1 | 1 | 2 | 1 | 1.40 |
| O — Open Compare | 2 | 1 | 1 | 2 | 1 | 1.40 |

**P and I score nearly identically because they are, in effect, the same underlying work item** — P is the specific, freshly-evidenced instance of the general capability I already named. P is used as the actual winner precisely because it is concrete (it names the exact bug found) rather than aspirational.

---

## 11. BLOCKER / HIGH-LEVERAGE ENHANCEMENT / LATER / DEFER classification

**BLOCKER** ("we should be uncomfortable recruiting target users without addressing it"):
- **P — fix the live Since-Last-Visit failure and establish real migration/deploy reliability.** A target user's first click can 500. This is disqualifying on its own regardless of any other finding in this document.
- **I — production deployment + automated maintenance activation**, as the general capability P is one concrete instance of. Recruiting users onto a product with no deploy pipeline, no CI, and no confirmed-continuous automation is not responsible.

**HIGH-LEVERAGE ENHANCEMENT** (large value relative to cost, not disqualifying but materially improves the product):
- **K — product analytics + beta feedback.** Cheap, and without it a beta run under N teaches nothing.
- **J — onboarding/first-use experience.** Now that Overview has real content (Relate, State Duration) worth orienting a new user toward, a short first-use frame is cheap and would directly address §4's first-60-seconds finding.
- **A — Curated Compare.** Real, safe, backend-ready, correctly scoped by `relate-compare-audit-v1.md`; the natural next content increment once P/I/K are addressed.

**LATER** (real value, correctly not now):
- **D — Historical Visualization (charts).** Real, known gap; large effort; not the bottleneck.
- **L — Recorded History productization.** Real compounding asset; no user-facing job currently blocked on it.
- **N — stop feature work, run a beta.** Directionally right eventually, sequenced strictly after P/I/K.
- **E — Search/Explore frontend.** Real backend, no demonstrated blocked job yet.
- **F — Save/Watchlist**, **H — Notifications**. Correctly deferred until Since Last Visit itself is proven live and reliable.

**DEFER** (not justified by current evidence, would add risk or premature scope):
- **B — Growth Monitor**, **C — Rates/Financial Conditions Monitor**, **M — Market layer** — breadth before reliability, the same mistake #21 warned against for a different reason (noise) now recurring for a new one (production trust).
- **G — Accounts/cross-device** — no justified need yet.
- **O — Open Compare** — unsafe without the statistical-method contract `relate-compare-audit-v1.md` §4 specified and which still does not exist.

---

## 12. Winner and runner-up

**Winner: P — Fix the live Since-Last-Visit failure and establish real deployment/migration reliability**, generalizing to candidate **I** as the durable capability behind it.

**Why P, not any content candidate:** every other finding in this document — Relate's real value, State Duration's real value, Investigate's continued strength, even Compare's readiness — is moot for a target user who cannot reliably load the product's own entry page. This is not a hypothetical risk assessment; it is a reproduced, live, exact-error-message fact discovered during this very audit. A product audit's own job is to find the sharpest, best-evidenced bottleneck, and this increment found one more concrete than any prior increment's own finding: a 500, not a UX judgment call.

**Why not a content candidate instead:** every content candidate (A, D, L, and the deferred domain-breadth candidates) makes the product larger or richer without making it trustworthy — and per this audit's own repeated finding across #21/#23A, breadth or richness before reliability has already once produced a real regression (the noise problem, since fixed) and is now producing a second, more severe one (a live 500 on the flagship feature). Fixing what is already built is smaller, safer, and higher-leverage than building anything new.

**Runner-up: K — Product analytics + beta feedback instrumentation.** The second most urgent gap once deployment is trustworthy: without it, running a beta (N) or shipping any of the HIGH-LEVERAGE candidates (A, J) produces no learnable signal about whether they actually worked. It is named ahead of J (onboarding) and A (Curated Compare) because analytics is a prerequisite for evaluating either of those once shipped, while neither is a prerequisite for analytics.

---

## 13. Explicitly, what NOT to build next

1. Any new economic domain (Growth, Rates/Financial Conditions, Market layer) — breadth before reliability, twice-demonstrated mistake.
2. Open/generic series Compare — no statistical-method contract exists; unsafe as specified in `relate-compare-audit-v1.md` §4.
3. Any cross-domain regime label or score (Goldilocks/bullish/etc.) — explicitly, repeatedly rejected across #21/#23A/#23A-and-now; nothing in this audit changes that.
4. Accounts, Save/Watchlist, or Notifications — each correctly depends on Since Last Visit actually working live first; building on top of a broken foundation compounds the exact risk this audit found.
5. Charts/visualization — real gap, large effort, not the bottleneck; do not let its visibility as a competitive weakness (§7) cause it to jump the queue ahead of reliability.
6. A beta recruitment push (candidate N) — premature until P/I/K are addressed; recruiting users now would surface the exact failure this audit already found, at a much higher reputational cost.

---

## 14. Reordered roadmap (next 3-5 increments)

1. **Fix deployment/migration reliability** (P/I): apply the missing migration to any environment intended to be shown to a real user; stand up a minimal, real deploy pipeline (even a single Dockerfile + one CI check that runs `alembic upgrade head` before serving) so this exact failure class cannot recur silently.
2. **Product analytics + minimal feedback path** (K): the cheapest possible instrumentation that would tell a builder whether Overview, Relate, State Duration, and (once fixed) Since Last Visit are actually being used and returned to.
3. **Onboarding / first-use framing** (J): a short, honest first-visit orientation now that Overview has real content worth orienting around — directly addresses §4's first-60-seconds finding.
4. **Curated Compare** (A): the next real content increment, already scoped safe and backend-ready by `relate-compare-audit-v1.md`, once the above three are in place.
5. **Recruit a small, target-user private beta** (N), now genuinely supported by working deployment, working return loop, and working instrumentation to learn from it.

---

## 15. Verdicts

- **Product thesis**: **STRONGER.** Every clause continues to gain real, tested backing (Relate closes "how does it relate," State Duration closes a slice of historical context), and this increment's own finding — that reliability, not breadth, is the bottleneck — is itself consistent with, not a challenge to, the thesis.
- **Target user**: **KEEP.** Nothing in this audit suggests narrowing, expanding, or changing who the product is for; the gap found is operational, not a mismatch with the target user's own needs.
- **Core wedge**: unchanged — a maintained, deterministic, evidence-linked change-detection and now relationship-composition layer, genuinely differentiated from FRED, generic AI, and dashboard-class competitors, still under-asserted visually.
- **Return loop**: **PARTIAL, not REAL.** Correctly designed, fully and rigorously tested (88 + 105 new tests, a proven race-safety guarantee), but not currently functioning in the actual running product due to a live, reproduced, root-caused deployment gap.
- **Investigation loop**: **STRONG,** unchanged from #21, the product's most consistently reliable dimension.
- **Commercial readiness**: **NOT READY.** Not for lack of features — for lack of demonstrated reliability. A first-time or paying user's first click can fail outright, no deployment pipeline exists to prevent recurrence, and no telemetry exists to even learn that it happened without an audit like this one finding it by hand.

---

## 16. The single biggest bottleneck

The product's own newest and most important feature — the thing meant to give a returning user a reason to come back — returns an HTTP 500 the moment a real user opens the app, because no automated process exists to keep the running database's schema in sync with the already-correct, already-tested code sitting on top of it.

---

## Appendix: secret safety and version control

No `.env`/`.env.*`/credential file was read, printed, or logged at any point this increment. No production code, migration, API, or methodology was added or changed. No file was committed or pushed. The live dev database was inspected read-only (`\dt`, `alembic current`/`heads`, a single `curl` reproduction of the existing 500) and was not modified in any way — the missing migration was deliberately left unapplied so the finding in §2.1 remains exactly as discovered for whoever applies the actual fix.
