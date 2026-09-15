# Since Last Visit V1 — Product & Architecture Contract Freeze

**Increment #25F.** Contract freeze only. No production code changed. Baseline: HEAD `cc7cd6c` ("Add Recorded State History V1 persistence (#25E)"), clean working tree. Frontend: 1,032/1,032 passed. Backend: 1,375/1,375 passed, 0 skipped, against the project's established local isolated-Postgres test mechanism.

This document is the authoritative contract for #25G (backend) and #25H (frontend). It designs the first RETURN capability this product has ever had, using exactly the evidence #25C/#25E now make available — never a reconstruction, never AI, never an aggregate score.

---

## §1. Authoritative material reviewed this turn

Read in full: `docs/product/post-state-duration-product-loop-retention-audit-v1.md` (#25A), `docs/product/automated-economic-maintenance-v1.md` (#25B), `docs/product/recorded-state-history-v1.md` (#25D), `docs/product/overview-attention-model-v1.md` (#22A), `docs/product/relate-composition-v1.md` (#23B), `docs/product/state-duration-v1.md` (#24B). Inspected `docs/product/historical-context-state-history-audit-v1.md`'s §29 (since-last-visit prior analysis). `docs/architecture/current-architecture.md`/`request-flows.md`/`docs/ENGINEERING_JOURNAL.md` inspected for their #25C/#25E entries (already established this session).

---

## §2. Fresh implementation inspection performed this turn

`frontend/src/pages/Overview.tsx` (current section order and structure, post-#23C); `frontend/src/lib/inflationSalience.ts`/`laborSalience.ts` (exact Tier 1-4 predicates); `frontend/src/lib/releaseMonitorRelation.ts` (`CANONICAL_MONITOR_RELEASE_IDS`, `canonicalMonitorDomain`, `releaseMonitorCta`); `frontend/src/api/useApiResource.ts` (independent-resource-loading pattern); `frontend/src/lib/format.ts` (`formatPeriod` — month/year only, no time-of-day formatter exists yet); confirmed, by full-tree grep, **zero existing `localStorage`/`sessionStorage` usage anywhere in this frontend** — this increment would be the first. `app/models/release_processing_read.py`/`app/repositories/release_processing_read_repository.py`/`app/services/release_processing_read.py` (the existing #19B read-model precedent: "fetch the full candidate set into Python, no window function, no N+1" — the pattern this contract's own future read model reuses). `app/db/models.py`'s `ReleaseCheckRun`/`ReleaseObservationUpdate`/`ReleaseAnalysisUpdate`/`RecordedMonitorResult`/`MaintenanceSweep` (already fresh in context from #25C/#25E's own implementation work this session, re-confirmed exact column shapes). `app/api/*.py` route prefixes (confirmed no `/overview` aggregate route exists or should be resurrected — `Overview.tsx`'s own docstring: "There is no aggregate `GET /api/v1/overview` endpoint... deliberately not built").

---

## §3. Current return-loop gap, reconfirmed (not assumed current from #25A)

**What a returning user sees today:** the identical Overview every time — no freshness indicator with time-of-day precision (only `formatPeriod`'s month/year), no "what's different since you were last here," no memory of any kind. **What must be manually repeated:** re-reading Current State, What Changed, and Recent Data Updates in full, from memory, to notice any difference. **What EI now knows that it fails to surface:** #25C proved release processing runs on a real, regular cadence; #25E proved every genuine canonical recomputation — changed or confirmed-unchanged — is durably recorded. Neither capability is visible anywhere in the UI. **#25A's own finding is not stale — it is now actionable for the first time**: #25A correctly identified RETURN as the missing link and correctly sequenced Automated Maintenance ahead of it (§44/§45 there); #25C and #25E are exactly that sequencing completed. This contract is the next, now-unblocked step, not a re-derivation of #25A's own conclusion.

---

## §4. Since Last Visit — frozen definition

> **Since Last Visit is a deterministic recap of canonical economic-intelligence activity Economic Intelligence itself durably recorded, strictly after the user's last acknowledged Overview recap — always paired with an honest statement of EI's own checking coverage during that window.**

"Visit" is deliberately not "page load," "tab focus," or "session" — see §5. The recap draws **only** from durable, already-persisted operational evidence (`ReleaseCheckRun`, `ReleaseObservationUpdate`, `ReleaseAnalysisUpdate`, `RecordedMonitorResult`, `MaintenanceSweep`) — never from State Duration's reconstruction (§103), never from AI (§119), never assigning an economic-significance score (§118).

---

## §5. Visit vs. checkpoint (frozen: automatic, on successful recap render)

Evaluated head-to-head: (A) checkpoint on Overview load — rejected, risks losing events if the recap fetch fails immediately after (violates §91's own requirement below); (D) an explicit "Mark as seen" button — rejected for V1, real friction this product's own established zero-friction idiom (no buttons anywhere else on Overview gate content) does not otherwise impose, and the correctness gain over automatic acknowledgement is marginal for this ICP. **Frozen: (B) — the checkpoint advances automatically, immediately after the Since Last Visit response is successfully received AND rendered**, never before. A refresh, a second tab, or a page visit that never reaches a successful render never advances the checkpoint (§91/§92).

---

## §6. Acknowledgement semantics (frozen: implicit, via successful render — no explicit UI)

Rendering **is** acknowledgement — no separate confirmation control exists. This is a deliberate, accepted V1 cost (a user who sees the recap but closes the tab in the first second is still treated as having "seen" it) — bounded and acceptable, matching how this product already treats every other read as sufficient (no "I have read this" pattern exists anywhere else in the UI either).

---

## §7. First visit (frozen: no false claim, different heading, still real value)

**No local checkpoint → the section never says "Since your last visit."** It renders under a different heading ("Recent Economic Activity," §75), with orientation copy (§85) explaining this is a first visit, followed by a real, bounded recap using the same tiers and the same default lookback window (§50) as any other visit — **not** an empty section, and **not** the literal current Overview repeated. After this render succeeds, a checkpoint is set exactly as any other visit (§5) — the *second* visit is the first genuine "since last visit" recap.

---

## §8. Local-only V1 (frozen, confirmed feasible and acceptable)

Confirmed, this turn: this frontend has **zero** existing storage code of any kind — `localStorage` is the correct, smallest V1 mechanism, with named, accepted limitations: device/browser-specific, cleared storage silently resets to first-visit state (§95), private browsing may not persist across sessions, no cross-device sync, not server-authoritative (the server never learns who is "visiting," §97). All acceptable for V1 per #25A's own original §26 recommendation, now executed rather than merely proposed.

---

## §9. Local state schema (frozen: minimal — one server-issued watermark, nothing else)

```
{
  schemaVersion: 1,
  through: string   // ISO-8601 UTC datetime, server-issued (§11) -- NEVER browser Date.now()
}
```

No checkpoint ID, no economic data, no per-domain state. `schemaVersion` allows a future, additive schema change to detect and gracefully reset an old-shaped value rather than crash on it (§87).

---

## §10-13. Clock source, server watermark, interval semantics, and the request-race problem (frozen — the central design decision)

**Frozen: the browser's own clock is never authoritative for event ordering.** The client stores and echoes back a **server-issued watermark**, never a value it computed itself. This resolves §10-13 together, precisely:

- **`through`** is captured **once**, from the server's own UTC wall clock, at the very start of request handling — **before** any query executes.
- The window query is **`ReleaseCheckRun.completed_at > after AND ReleaseCheckRun.completed_at <= through`** — a genuine half-open interval `(after, through]` (§12), tie-broken `completed_at ASC, id ASC` for deterministic presentation order.
- **Why capturing `through` BEFORE the query, not after, is the one detail that makes this race-safe** (§13's own named scenario): if `through` were instead captured *after* the query ran (or from "now" at response-finish), a commit landing between query-execution and response-finish could have `completed_at <= through` yet never have been read by the query that already ran — permanently lost, since the next visit's own `after` would equal that same `through` and would never see it either. Capturing `through` **first**, then filtering `completed_at <= through`, makes the opposite true: **any event this response's own query might have missed necessarily has `completed_at > through`**, and will therefore always be included in the *next* request (`after = this through`). No event is ever silently, permanently skipped — a same-second race produces, at worst, a one-visit delay, never data loss.
- **No compound cursor or monotonic event ID is needed.** `ReleaseCheckRun.completed_at` is already the same kind of value (real server wall-clock time, captured once per row, per #25C's own confirmed behavior) as the watermark itself — comparing "server clock" to "server clock" carries none of the cross-source drift risk comparing it to a *browser's* clock would.

---

## §14. Multiple tabs (frozen: last-write-wins, no synchronization mechanism)

Two Overview tabs loaded at different times can genuinely see different windows and independently advance the checkpoint — the later-rendering tab's own `through` simply becomes the new stored value, overwriting the earlier one. **No `storage`-event cross-tab synchronization is built for V1** — the realistic failure mode (a user reading a slightly-stale recap in an already-open tab after a newer tab already advanced the checkpoint) is cosmetic, not a correctness or data-loss problem (§11-13's own race-safety guarantee holds regardless of tab count), and building synchronization for it would be real complexity for a small, bounded cosmetic cost.

---

## §15. Direct-domain visits (frozen: do not advance the checkpoint)

Visiting `/inflation` or `/labor` directly, without visiting Overview, **never** advances the Since Last Visit checkpoint — only a successful Overview recap render does (§16).

---

## §16. Checkpoint owner (frozen: Overview, exclusively)

**"Since Last Visit" means, precisely, "since the last acknowledged Overview recap" — never a per-page or per-domain checkpoint.** One owner, one checkpoint, matching #25A's own original §16 framing exactly and avoiding the complexity of reconciling multiple, potentially-divergent per-page checkpoints.

---

## §17. Eligible event sources (frozen: four tables, one deliberately excluded from the item list)

`ReleaseCheckRun` (the event spine, §58), `ReleaseObservationUpdate`, `ReleaseAnalysisUpdate`, `RecordedMonitorResult` — all read via the check runs the window's own `(after, through]` filter selects. `MaintenanceSweep` is **not** unioned into the item list at all — it is evaluated **separately**, over its own `(after, through]` window by `started_at`, solely to determine coverage (§40), never rendered as its own feed item (§36). No raw table is ever dumped as an activity feed — every item is a derived, categorized fact (§18).

---

## §18. Event hierarchy — frozen (three visible tiers, one coverage-only tier)

| Tier | Meaning | Source |
|---|---|---|
| **A — Structural change** | The domain's own top-level state or availability transitioned | `ReleaseAnalysisUpdate`, Tier-1-shaped (§20) |
| **B — Recalculation confirmed unchanged** | The domain's own top-level state was genuinely recomputed and found identical | `RecordedMonitorResult` with no corresponding Tier-A row for the same run (§65) |
| **C — Source data updated, no top-level recompute** | A canonical input series changed but never reached a top-level state recomputation | `ReleaseObservationUpdate`, residual (§28-30) |
| **D — Checked, nothing to report** | (Not an item — folds into coverage/freshness only, §36/§79 row A) | `ReleaseCheckRun`, `NO_CHANGE` |

**Deliberately narrower than Overview's own What Changed salience** (§20): Since Last Visit V1 covers only each domain's own **top-level** state (mirroring `RecordedMonitorResult`'s own already-frozen narrow scope, `recorded-state-history-v1.md` §65) — never Headline PCE/CPI, Confirmation, or condition/momentum sub-signals, which remain the province of the existing, unduplicated What Changed page. This keeps Tier A and Tier B symmetric (both top-level-only) and prevents exactly the audit-log-shaped scope creep the source prompt names as an explicit anti-goal.

---

## §19. Salience reuse (frozen: same membership rules, restated in the backend layer — not imported cross-language, not a second methodology)

The backend read model's own Tier-A membership test is the **identical** predicate `overview-attention-model-v1.md` §6/§7 already froze for Inflation's/Labor's own "primary domain state" tier (Inflation: `component == "PRIMARY_MOMENTUM" && field == "state"`; Labor: `component == "LABOR"`) — re-expressed once, in Python, in the new backend module, exactly the same "two independent, already-correct restatements, never one shared abstraction across a language boundary" precedent this project already applies to `month_before`, the `NETWORK_EXCEPTIONS` allowlist, and the deadband constants. **This is PRESENTATION PRIORITY only, restated for a new surface — never a second, competing economic-significance methodology** (§118).

---

## §20. Structural-change definition (frozen, narrow — restated from §18)

A `ReleaseAnalysisUpdate` row whose `(component, field)` matches the domain's own Tier-1 predicate (§19), with `event_type` in `{STATE_CHANGED, AVAILABILITY_LOST, AVAILABILITY_RESTORED}`. Never inferred from metric magnitude (§118); never a sub-component (Headline/Confirmation/condition/momentum) event.

---

## §21. Unchanged-confirmation algorithm (frozen, exact — the central new capability)

For each `RecordedMonitorResult` row in the window, grouped by `(release_check_run_id, monitor)`:

1. **If a Tier-A row (§20) exists for the same `(release_check_run_id, monitor)`** → this is Tier A (a genuine change), not a separate unchanged-confirmation — no double-reporting.
2. **Else, if no `RecordedMonitorResult` row for this `monitor` exists with an earlier `id`** (i.e., this is the *system-wide first ever* recorded row for that monitor — a single, cheap existence check, not a window-scoped one) → **FIRST_CALCULATION** (§22).
3. **Else** → **UNCHANGED_CONFIRMATION** — a genuine, later re-verification producing the same top-level state as before, the exact durable proof #24A/#25B/#25D each independently identified as missing until #25E shipped.

No inference anywhere in this algorithm — every branch is a membership/existence test over already-persisted rows.

---

## §22. First-recorded-result behavior (frozen)

**Never** "remains X" when no prior recorded row exists for that monitor at all. Exact copy: *"Inflation was calculated as {State} for {Month Year}."* — a report of a genuine first calculation, not an implied history.

---

## §23. Repeated-unchanged aggregation (frozen: one line per monitor, count included, never one card per calculation)

Multiple UNCHANGED_CONFIRMATION rows for the same monitor within the window are aggregated to **one** line: *"Inflation was recalculated {N} time(s) since your last visit and remains {State} (most recently for {Month Year})."* Never N separate cards — this is precisely the audit-log-shaped noise the source prompt names as an explicit anti-goal, and aggregation is what makes the underlying capability (§21) a genuine product feature rather than a raw event dump.

---

## §24-25. Changed-then-changed-back / multiple transitions (frozen: every genuine transition shown, never start-vs-end collapsed)

**Every Tier-A row within the window renders as its own transition line, in chronological order — never collapsed to a single window-start-vs-window-end comparison.** COOLING→STABLE→COOLING within one window renders as two distinct lines, both visible, exactly preserving the honest history (§102's own worked example, resolved directly). No artificial cap is applied to Tier A (mirroring #22B's own "Tier 1-2 always shown, uncapped" precedent) — real-world release cadence naturally bounds this to a small number even across a multi-month gap (§77), and the lookback bound (§50) provides the actual ceiling.

---

## §26. Availability lost/restored (frozen: Tier A, existing #22B copy pattern reused verbatim)

Already covered by §18-20's own Tier-A scope (availability transitions are part of each domain's own Tier-1 predicate). Copy reuses #22B's own already-shipped, non-directional phrasing exactly — "became unavailable"/"available again" — never "improved"/"worsened."

---

## §27. Metric-only changes (frozen: folded into Tier C, never their own tier)

A metric-only `ReleaseAnalysisUpdate` (no top-level `STATE_CHANGED`) is represented, if at all, via Tier C's own "data updated, no structural recompute" framing (§18/§28) — never surfaced as its own distinct item, matching #22B's own "No structural change" philosophy extended to this surface.

---

## §28-30. Source-data updates — subject, grouping, and the revision/new distinction (frozen)

**Tier C fires only when a `ReleaseCheckRun` produced `ReleaseObservationUpdate` rows but zero Tier-A/B rows for the monitor those series belong to** — the residual case where data genuinely changed but never reached a top-level recompute (e.g., a Headline-CPI-only or Confirmation-only revision). **Subject: the series' own title** (`EconomicSeries.title`, already looked up at response time by the existing #19B read model's own precedent), never the raw series ID. **Grouping: by check run, within the monitor's own block** — canonical series membership (`PRIMARY_SERIES_ID`/`CONFIRMATION_SERIES_ID`/`TARGET_SERIES_ID`/`HEADLINE_CPI_SERIES_ID` for Inflation, `PAYEMS_SERIES_ID`/`UNRATE_SERIES_ID` for Labor — the exact, already-existing backend constants, not new ones) decides which monitor's block a Tier-C item belongs to. **Revision vs. new: shown**, directly provable from `ReleaseObservationUpdate.change_type` with zero inference — *"{Series Title} data was revised."* / *"{Series Title} data was updated."*

---

## §31-32. Grouping unit (frozen: monitor-first, release-scoped within)

**Primary hierarchy: by monitor** (Inflation block, Labor block — §33), matching Overview's own established domain-first structure. **Within a monitor's block, Tier-C items are release/check-run-scoped**, since that is genuinely what produced them — not flattened to individual observation rows (§67).

---

## §33-34. Domain separation and cross-domain composition (frozen: separate blocks, no Relate reuse)

**Inflation and Labor remain two independent, separately-gated blocks** — no merged chronological stream, mirroring #22A/#22B's own identical, already-justified cross-domain-ordering decision (no shared timestamp basis exists that wouldn't require inventing one). **Relate composition is not reused** — Relate answers "how do these two states relate *right now*"; Since Last Visit answers "what happened *over a window*" — composing a historical relationship claim from two independently-timed event streams would be exactly the kind of fabricated cross-domain synthesis Relate itself was frozen to avoid (`relate-composition-v1.md` §2). Deferred, not merely unused.

---

## §35. `ReleaseCheckRun` role (frozen: spine, not individually surfaced)

A `NO_CHANGE` `ReleaseCheckRun` is never rendered as its own item — it contributes only to coverage (§40) and, when paired with genuine child rows, to Tier A/B/C. It is the *ordering spine* (§58), not a feed entry.

---

## §36. `MaintenanceSweep` role (frozen: coverage input only, never a feed item)

Confirmed, restated from §17: evaluated independently, over its own window, solely to distinguish GAP from UNKNOWN coverage (§40) — never listed, counted, or named to the user as an individual event.

---

## §37-39. Nothing-changed / nothing-processed / coverage-unknown — three genuinely distinct, never-collapsing states (frozen)

| State | Condition | Copy anchor |
|---|---|---|
| **Checked, quiet** | Coverage `CHECKED` for the domain, zero Tier A/B/C items | §79 row A |
| **Never processed** | Zero `ReleaseCheckRun` rows at all for the domain's own curated releases in the window | §79 row C |
| **Coverage unknown** | Coverage `UNKNOWN` (§40) | §79 row D |

---

## §40-41. Coverage model (frozen: `CHECKED` / `GAP` / `UNKNOWN` — never "complete")

**"Complete"/"up to date" is never used anywhere** (restating #25B §27's own already-frozen, absolute rule for this new surface). Frozen, per domain, per window:

- **`CHECKED`**: every one of that domain's own actively-mapped curated releases has at least one **settled** (`NO_CHANGE`/`CHANGED` — reusing #25C's own already-frozen settlement definition verbatim, §10 of `automated-economic-maintenance-v1.md`) `ReleaseCheckRun` with `completed_at` in `(after, through]`.
- **`GAP`**: at least one relevant release has **no** settled run in the window, but at least one `MaintenanceSweep` row exists with `started_at` in the window (the worker genuinely ran; a specific release simply never settled — e.g. `PARTIAL_FAILURE`/`FAILED_PROVIDER`, or not yet due).
- **`UNKNOWN`**: no `MaintenanceSweep` evidence exists in the window at all — the worker's own execution cannot be confirmed from persisted data (§42), which includes the case where the checkpoint predates automation's own first sweep entirely.

`CHECKED` never requires `MaintenanceSweep` evidence — a domain fully covered by manual CLI processing alone is honestly `CHECKED` (§47), since coverage is about settlement, not about which trigger produced it.

---

## §42. Automation-capable vs. active (frozen: derive strictly from persisted `MaintenanceSweep` rows)

**Never** inferred from the mere existence of `app.services.maintenance`/`app.operations.run_maintenance` code — only from real, persisted `MaintenanceSweep` rows in the window, exactly per the source prompt's own explicit instruction. An architecture guard is required for #25G (§129) proving the new read model never imports the orchestrator itself, only reads its persisted table.

---

## §43. Maintenance freshness (frozen: a neutral timestamp fact, never an evaluative claim)

*"Last checked: {formatted date and time}."* — the most recent settled `ReleaseCheckRun.completed_at` across the domain's own relevant releases (or the most recent `MaintenanceSweep.finished_at` if no settled run exists at all) — always shown, never interpreted as "fresh"/"stale" by any frozen threshold (none is defined here, matching #25B §43's own deliberate abstention). This is the first place in this product that needs a **time-of-day** display, not just month/year (`formatPeriod`'s own existing scope) — a new formatter is required (§74).

---

## §44. Failed/unfinished sweep (frozen: never silently reads as "no changes")

A `MaintenanceSweep` row with `finished_at IS NULL` in the window (crashed or still running, per #25C's own frozen semantics) is treated identically to "sweep evidence exists" for the `GAP`-vs-`UNKNOWN` distinction (§40) — it proves an attempt occurred — but never upgrades coverage to `CHECKED` on its own; `CHECKED` still requires genuine settlement.

---

## §45-46. Failed / partial release processing (frozen: folded into the `GAP` disclosure, never a separate alarming item)

A relevant release with only `PARTIAL_FAILURE`/`FAILED_PROVIDER` attempts in the window (no settlement) contributes to `GAP` coverage and its own soft, non-alarming disclosure line — *"Some monitored releases could not be fully checked since your last visit."* — never internal error detail, never its own feed card. Domain results that **did** successfully compute (a different monitor, or a different release for the same monitor) still render normally alongside this note — partial failure narrows coverage, it does not blank the whole domain block.

---

## §47. Manual processing (frozen: recorded results are legitimate content; never proves scheduler health)

Manual and automated `ReleaseCheckRun`/`RecordedMonitorResult` rows are **indistinguishable** in this read model (per #25D §27/§28 — no origin field exists, and none should be added here either) — both count identically toward Tier A/B/C content and toward `CHECKED` settlement. They do **not**, on their own, ever contribute to `MaintenanceSweep`-based coverage evidence (§40's `GAP`/`UNKNOWN` distinction) — a domain fully covered by manual checks alone is `CHECKED` (real settlement exists) even with zero sweep rows, exactly as §40 already specifies.

---

## §48. Pre-recorded-history window (frozen: no clamping needed — falls out naturally)

A window extending before #25E's own deployment simply has no `RecordedMonitorResult` rows for that older sub-window — Tier B is silently absent there (never a fabricated claim), while Tier A (`ReleaseAnalysisUpdate`, live since #18) remains fully available. No special-case branch or explicit clamp is required — this is an honest, automatic consequence of querying real, dated persisted data, not a gap to engineer around.

---

## §49. First-launch behavior (frozen: bounded by §50, never an unbounded historical dump)

The very first #25G/#25H deployment, for a user with no prior checkpoint, behaves exactly per §7/§50 — the bounded default window, never "everything RecordedMonitorResult has ever accumulated."

---

## §50-51. Lookback bound (frozen: 90 days, clamped and disclosed — not empirically measured)

**Frozen at 90 calendar days** — not pretended-precise (mirroring this project's own established "tunable, not empirically pretended-precise" discipline, e.g. #25B §14's retry window, #24B §11's 60-month State Duration bound reused from real precedent). Reasoning: economic releases are monthly; 90 days covers roughly two to three release cycles per domain — enough for a genuinely "catching up" recap without becoming a historical archive (explicitly not this feature's job — that is a future, separate recorded-vs-reconstructed comparison surface, §103). **If the stored checkpoint is older than 90 days, `after` is clamped to `through - 90 days`**, and the recap discloses this honestly: *"This summary covers the last 90 days — your last visit was longer ago."* — never silently presented as if it were the true, full gap.

---

## §52. Backend retention (confirmed: no constraint)

`RecordedMonitorResult`/`ReleaseCheckRun`/etc. have no TTL (#25D §52-53) — the 90-day bound is a **product** choice about relevance, not a backend storage limitation; nothing prevents a future increment from widening it.

---

## §53. API route (frozen: `GET /api/v1/since-last-visit`, a new, dedicated top-level resource)

**Not** nested under `/overview` (no such prefix exists, and none is resurrected — `Overview.tsx`'s own #19A decision to avoid one aggregate endpoint stands; this is a genuinely new capability, not a redundant aggregation of already-separately-fetched resources). **Not** `/activity/since` or any name implying a generic feed (the source prompt's own explicit anti-pattern). One route, one new router (`app/api/since_last_visit.py`, `prefix="/since-last-visit"`).

---

## §54. Request contract (frozen)

`GET /api/v1/since-last-visit?after=<ISO-8601 UTC datetime>` — `after` optional (omitted → first-visit behavior, §7). **A malformed, future, or implausibly old `after` is never a `400`** — it is treated as absent (fall back to the bounded default window), matching this project's own repeated "a broken client value is a data condition to handle gracefully, not an infrastructure error," and preventing a corrupted `localStorage` value from ever hard-breaking Overview (§87).

---

## §55. Response watermark (frozen)

The response always carries **both** the `after` actually used (post-clamping, so the client's own next-stored value is correct) and the new `through` — the client stores `through` verbatim only after a successful render (§5/§93). Per-domain content is nested inside, never top-level-merged with the watermark fields.

---

## §56-57. Watermark representation and the cross-table ordering problem (frozen, restated precisely from §10-13/§58)

A single server-clock timestamp (`through`), never a compound cursor and never a new, generic event ledger (explicitly evaluated and rejected, §57's own option D — unjustified complexity given `ReleaseCheckRun` already serves as a sufficient, real spine, §58).

---

## §58-59. `ReleaseCheckRun` as the event spine (frozen)

**Confirmed and adopted.** `ReleaseObservationUpdate`, `ReleaseAnalysisUpdate`, and `RecordedMonitorResult` all carry `release_check_run_id` — filtering `ReleaseCheckRun` by `completed_at` first, then joining out to exactly the selected runs' children, turns a genuinely hard cross-table ordering problem into a single-table one. `ReleaseCheckRun` already provides a stable `id`, a real `completed_at`, and its parent `release_occurrence_id` — sufficient for deterministic ordering (`completed_at ASC, id ASC`) with no schema change.

---

## §60. Events after checkpoint vs. `MaintenanceSweep` evidence (frozen: evaluated independently, restated from §36)

Confirmed — the separation is deliberate and desirable, not an oversight: mixing "did the worker run" into the same query as "what did EI conclude" would re-conflate exactly the two concepts #25B §30 already froze as permanently distinct.

---

## §61. Query strategy (frozen: extends the existing #19B read-model pattern, no N+1)

1. Resolve `through` (server clock, captured first, §10-13).
2. Fetch the domain's own relevant `ReleaseCheckRun` rows with `completed_at` in `(after, through]` — one query.
3. Fetch every child row (`ReleaseObservationUpdate`/`ReleaseAnalysisUpdate`/`RecordedMonitorResult`) for that run-id set — three queries, each `IN (...)`, never per-run — the identical `list_*_for_runs` pattern `ReleaseProcessingReadRepository` already establishes for #19B.
4. Fetch `MaintenanceSweep` rows for the same window — one query.
5. A pure, deterministic summarizer (§62) turns the fetched rows into categorized, aggregated facts.

Five bounded queries total, independent of item count within the window — no window function, no N+1, matching #19B's own already-accepted "small, curated catalog, unpaginated candidate set" reasoning (`recorded-state-history-v1.md` §88's own growth estimate confirms the volume stays small).

---

## §62. Deterministic summarizer (frozen: pure, no LLM, backend-owned)

A pure function/module (no I/O) turning the fetched candidate rows into the categorized (§18), aggregated (§23), deduplicated (§67) structure the response returns — implementing §21's exact algorithm and the current-result-selection rule (§68-70). No AI import anywhere in this module (§129).

---

## §63. Backend/frontend boundary (frozen: backend determines truth, frontend renders)

**Every classification decision — window, coverage, tier, aggregation, current-result selection — is made once, in the backend.** The frontend never re-derives a transition, a tier, or a coverage state from raw rows; it renders the already-categorized response verbatim, plus its own localStorage read/write and request lifecycle. This directly satisfies the source prompt's own "do not send raw audit rows and force React to reconstruct truth" instruction.

---

## §64-65. Canonical-change / unchanged derivation, and availability precedence (frozen, restated exactly from §20/§21/§26)

Structural change: reuses `ReleaseAnalysisUpdate` directly (§20/§64), never re-derives Inflation/Labor methodology. Unchanged confirmation: §21's own three-branch algorithm. **Availability precedence:** an `INSUFFICIENT_DATA` transition is **always** represented via the existing availability vocabulary (§26), never via the unchanged-confirmation template's "remains X" phrasing — a *repeated*, still-insufficient confirmation (no availability transition either direction) uses a dedicated noun-phrase adaptation (§80), mirroring `relate-composition-v1.md` §4's own precedent for handling "Insufficient data" as a noun phrase, not an adjective.

---

## §66-67. Deduplication (frozen: current-result selection is the deduplication rule)

One fact, one line — never three redundant cards from one `ReleaseCheckRun` (the source prompt's own named risk). Resolved entirely by §68-70's current-result-selection rule below, applied uniformly to both Tier A and Tier B.

---

## §68-70. Multiple evaluation periods / historical revision propagation / current-result selection (frozen — the critical rule, empirically motivated by #25E's own test-writing)

**One unified rule covers both Tier A and Tier B:** within one `(release_check_run_id, monitor)` group, only the row — whether a `ReleaseAnalysisUpdate` (Tier A) or a `RecordedMonitorResult` (Tier B) — whose `evaluation_period` is the **maximum** among that group's own rows represents the "current" fact worth surfacing; any other row in the same group (an older, propagated period from the same run — the exact scenario #25E's own test suite discovered empirically: one Labor benchmark-revision check producing up to six `RecordedMonitorResult` rows across propagated periods) is **deferred from V1 entirely**, not shown at all. This is an explicit, named scope limitation (historical-revision-propagation detail is genuinely deferred, §71), not a silent truncation — and it is always safe because every rendered item explicitly names its own `evaluation_period` (§29/§74), so even the one surfaced row is never misrepresented as "the absolute latest EI has ever known," only as "what this specific check run's own most-recent-touched period showed."

---

## §71. Historical revision user value (frozen: deferred, not built)

A dedicated "Labor history for July was revised" surface is real, plausible future value — **explicitly out of V1**, per §68-70's own deferral. Revisiting this is conditional on real product demand once the base recap has shipped and been observed in use, not designed speculatively here.

---

## §72-73. Labels (frozen: reuse existing persisted metadata, never invent)

Release labels: `EconomicRelease.name`, already persisted, reused verbatim (§28-30). Series labels: `EconomicSeries.title`, looked up exactly as `ReleaseProcessingReadRepository.list_series_metadata` already does for #19B — a series with no persisted title renders its raw `series_id` rather than a fabricated name, matching that existing precedent's own null-handling exactly.

---

## §74. Timestamp display (frozen: a new formatter is required)

`formatPeriod` (month/year only) is insufficient for `"Last checked: {time}"` (§43) — **a new, small frontend formatter is required for #25H**, rendering a full UTC date-and-time (mirroring `formatPeriod`'s own discipline: parse the ISO string's digits directly, never route through `Date`/`toLocaleDateString`'s local-timezone conversion, which the existing formatter's own docstring already identifies as a real correctness risk). Calculation/check time and evaluation period remain visually and textually distinct everywhere (never "as of {check time}" applied to an evaluation-period fact, or vice versa) — restating #25D §14's own already-frozen distinction for this new surface.

---

## §75. Overview placement (frozen: top, before Current State)

**Deliberately first**, not appended after What Changed/Recent Data Updates. A RETURN feature's entire purpose is orienting a user *before* they re-scan the rest of the page from memory — placing it lower would defeat that purpose, since by the time a user reached it they would already have done the manual re-scan this feature exists to eliminate. First-visit rendering (§7) prevents this placement from ever being an empty, awkward gap.

---

## §76. Information hierarchy (frozen)

```
SINCE YOUR LAST CHECK                              (or "RECENT ECONOMIC ACTIVITY" on first visit, §85)

  [coverage/freshness note, §40/§43 -- per domain or combined]

  Inflation
    [Tier A lines, chronological, §24-25]
    [Tier B aggregate line, §23]
    [Tier C aggregate line(s), §28-30]
    (zero-state copy per §79, if applicable)
    View Inflation →

  Labor
    ...
    View Labor →
```

---

## §77. Maximum visible items (frozen: uncapped Tier A, aggregated B/C — never a raw count cap)

Tier A: uncapped (§24-25) — naturally small given real release cadence and the 90-day bound. Tier B: exactly one aggregate line per monitor (§23). Tier C: one line per distinct series-update fact per monitor (naturally small, bounded by the small curated series set).

---

## §78. Domain order (frozen: Inflation then Labor, matching every other Overview section's own stable order)

---

## §79. Zero-state copy — four genuinely distinct states, never collapsed (frozen, restated exactly from §37-39)

| State | Condition | Copy |
|---|---|---|
| A — Checked, quiet | `CHECKED`, zero A/B/C items | *"No new Inflation activity was detected since your last check."* |
| B — Checked, active | (the Tier A/B/C lines themselves are the content) | *(no separate zero-state copy needed)* |
| C — Never processed | Zero `ReleaseCheckRun` in window for the domain's curated releases | *"No monitored Inflation releases were processed since your last check."* |
| D — Coverage unknown | `UNKNOWN` | *"Coverage for Inflation could not be confirmed for this period."* |

---

## §80. Recalculation copy (frozen, exact templates)

- First calculation: *"Inflation was calculated as {State} for {Month Year}."*
- Unchanged, N=1: *"Inflation was recalculated for {Month Year} and remains {State}."*
- Unchanged, N>1: *"Inflation was recalculated {N} times since your last visit and remains {State} (most recently for {Month Year})."*
- Unchanged, `INSUFFICIENT_DATA`: *"Inflation was recalculated for {Month Year}; its state is still insufficient to classify."*

---

## §81. Structural-change copy (frozen)

*"Inflation changed from {Previous} to {Current} for {Month Year}."* — state labels are the byte-identical output of the existing label functions (`inflationStateLabel`/`laborStateLabel`), reused verbatim per `relate-composition-v1.md` §4's own already-frozen discipline. No interpretation word ("the economy weakened") is ever appended.

---

## §82. Observation-update copy (frozen)

*"{Series Title} data was revised."* / *"{Series Title} data was updated."* (§29's NEW/REVISED distinction, §72's label sourcing).

---

## §83. Release copy (frozen: folded into §82, no separate standalone line)

A bare *"{Release Name} data was processed"* line is **not** added on top of §82's own series-level line — redundant with it once the series subject is already named; avoided per the explicit "no duplicate semantic statements" discipline `overview-attention-model-v1.md` §11 already established.

---

## §84. Coverage copy (frozen, exact, restated from §40/§43-46)

*"Last checked: {formatted date and time}."* (always, when any evidence exists) + conditionally: *"Some monitored releases could not be fully checked since your last visit."* (`GAP`) or *"EI's own automated-checking coverage for this period could not be confirmed."* (`UNKNOWN`). **Never** *"Everything is up to date."*

---

## §85. First-visit copy (frozen)

Heading: *"Recent Economic Activity."* Orientation line: *"This is your first visit — future visits will show what's changed since you were last here."* — followed by the same bounded recap structure (§7).

---

## §86. Old-checkpoint copy (frozen, restated from §51)

*"This summary covers the last 90 days — your last visit was longer ago."*

---

## §87. localStorage failure (frozen: fail to first-visit, never block, never error-spam)

A throwing or unavailable `localStorage` (private browsing, disabled storage, a corrupted/old-`schemaVersion` value) is treated identically to "no checkpoint" — first-visit behavior (§7), Overview itself renders normally regardless, no error surfaced to the user for this specific failure.

---

## §88. API failure (frozen: additive, never availability-critical)

If `GET /since-last-visit` fails, the rest of Overview renders exactly as it does today, unaffected — this section shows its own existing `ErrorMessage`/retry pattern (matching every other Overview section's own established failure isolation), never blocking Current State or any other section.

---

## §89. Partial-domain failure (frozen: not applicable — one atomic backend read model)

The endpoint is single, backend-atomic: it either succeeds (200, with per-domain content that can independently be empty/quiet/active — a **data** condition) or fails as one infrastructure-level error (matching every other endpoint's own established infra-vs-data distinction) — there is no "half succeeded" response shape to design for.

---

## §90. Loading (frozen: non-blocking, existing skeleton pattern)

Renders the existing `LoadingSkeleton` pattern while pending — never blocks Current State or any other section from rendering independently, mirroring `useApiResource`'s own already-established independent-loading discipline.

---

## §91. Checkpoint on API failure (frozen: never advances)

Restated, hard requirement: the stored `through` is only ever overwritten after a genuinely successful fetch **and** render (§5/§93).

---

## §92. Checkpoint on partial render (V1 practical semantics, frozen)

If the fetch succeeds but the component itself throws during render (a genuine frontend bug), the checkpoint is **not** advanced — the write happens only after render completes without throwing (an effect keyed to successful mount, not to fetch resolution alone), erring toward "show it again next time" over "silently lose it."

---

## §93. Checkpoint-update sequence (frozen, exact)

```
1. Read stored `through` (or none) from localStorage.
2. Request with `after = stored through` (or omitted).
3. Receive response: { after (echoed, clamped), through (new), ...domain content }.
4. Render.
5. On successful render: write { schemaVersion: 1, through: response.through } to localStorage.
```

No browser-`now()` timestamp is ever written at any step.

---

## §94. Refresh behavior (frozen)

Immediately after step 5, a refresh sends `after = through` (the just-stored value) — the new window is `(through, through']`, correctly near-empty (only whatever genuinely committed in the interim, per §10-13's own race-safety guarantee) — never a repeat of the same recap.

---

## §95. Storage-cleared behavior (frozen)

Reverts the user to first-visit state (§7) — no backend history is ever deleted or affected; this is purely a client-local reset.

---

## §96. Cross-device (frozen: explicitly unsupported, disclosed by omission — no false claim of sync anywhere)

---

## §97. Privacy (confirmed)

The local checkpoint is a non-sensitive timestamp/watermark — no user identity, no account, no server-side tracking of visits, no PII of any kind. `GET /since-last-visit` requires no auth and carries no user-identifying parameter.

---

## §98. Future-account compatibility (frozen: the cursor semantics migrate cleanly, this document does not design accounts)

If a future authenticated version moves the checkpoint server-side, the exact same `(after, through]` watermark semantics apply unchanged — only the checkpoint's *storage location* (localStorage vs. a server-side per-user row) changes, never the backend's own event-truth model. This compatibility is a property of the design, not a feature built now.

---

## §99-100. Notifications and Watchlist (frozen: both explicitly deferred, unrelated to this contract)

Since Last Visit is pull-based only — no email/push/SMS. No personalization: both monitored domains are shown, identically, to every visitor, per V1's own rules.

---

## §101-102. Current-state context and recorded-vs-current boundary (frozen, restated exactly from §24-25)

The recap **never** substitutes the live current-monitor state for what actually happened during the window — every Tier-A/B line uses the recorded evidence's own `previous_value`/`current_value`/`state` at the time it was captured, never re-derived from "what the monitor says now." COOLING→STABLE→COOLING both transitions render even though current state equals the window-start state (§102's own worked example) — never collapsed to "Labor unchanged."

---

## §103. Recorded-vs-reconstructed boundary (frozen, hard rule)

**Since Last Visit uses recorded operational history exclusively — it never calls, imports, or reconstructs via State Duration.** An architecture guard (§129) enforces this structurally for #25G.

---

## §104. Pre-#25E fallback (restated exactly from §48 — resolved, not a gap)

---

## §105. Event provenance (frozen: internal only, not shown in primary copy)

Each item's response representation carries `release_check_run_id`, `release` context (name/provider_release_id), `methodology_id`, and `evaluation_period` internally — available for future debugging/trust surfaces, never rendered as raw IDs in V1's own user-facing copy.

---

## §106. Methodology display (frozen: not shown directly, carried as a machine field only)

Confirmed per §114-115: `methodology_id` travels with every item for future-proofing, never surfaced in primary V1 copy.

---

## §107-108. CTAs (frozen: reuse existing "View Inflation →"/"View Labor →" verbatim, no new destination)

No per-item evidence link, no audit-log page — one CTA per domain block, identical wording and target to every other Overview section's own established convention (`relate-composition-v1.md` §15's own identical reuse decision, extended here).

---

## §109. Nav (frozen: no new nav item — lives on Overview only)

---

## §110. Responsive (frozen: compact, no timeline visualization, text-only rows)

---

## §111. Accessibility (frozen: plain text, no color-only signaling)

State words are text, not color-coded status dots — reusing the existing label functions verbatim, matching every other state-rendering surface in this product (`relate-composition-v1.md` §32's identical precedent).

---

## §112. Performance (confirmed bounded, restated from §61/§88 of `recorded-state-history-v1.md`)

Five bounded queries, no N+1, small real data volume.

---

## §113. Caching (frozen: none — per-checkpoint responses are never server-cached)

`after` varies per client; correctness at this small volume outweighs any caching benefit.

---

## §114-115. Mixed methodology versions / no methodology-change-event (frozen)

If a window ever spans two methodology versions (not possible today — exactly one version per monitor exists), each item carries its own item-level `methodology_id` (§105) and is never compared or collapsed across versions in one sentence — restating #25D §18's own already-frozen finding for this new surface. **No methodology-deployment-event table exists** — the recap therefore never announces "methodology changed" as its own fact; it only avoids ever *misrepresenting* results produced under different versions as directly comparable.

---

## §116. Data basis (frozen: internal provenance only, never rendered as "point-in-time data")

`data_basis` (already `"latest_revised_data"` on every `RecordedMonitorResult`/`ReleaseAnalysisUpdate` row) travels as a machine field; V1 copy never claims point-in-time input fidelity it cannot prove (#25D §23's own already-frozen boundary, unchanged here).

---

## §117. Release-revision-only disclosure (frozen: deferred with §71)

"Historical Labor data was revised" (with no current structural change) is not built in V1 — folded into the same deferral as historical-revision-propagation detail.

---

## §118. Economic-significance boundary (hard prohibition, restated)

Since Last Visit assigns **no** significance score, magnitude ranking, or severity label of any kind — presentation priority (§19) is deterministic membership only, identical in kind to #22B's own already-frozen, already-tested discipline.

---

## §119. AI boundary (hard prohibition)

No AI/LLM import anywhere in the summarizer (§62), the repository, the service, or the route. A future increment may let AI *explain* an already-computed recap in prose — it may never decide what happened.

---

## §120. Product differentiation (assessed)

FRED, a charting tool, or generic AI can all show *that* data exists or changed — none of them remembers **what a specific deterministic system itself concluded, and when, between a user's own visits**. This is the same non-reproducible-asset argument #24A §35 already established for recorded state, now made visible to a user for the first time rather than sitting invisibly in the database.

---

## §121. Retention assessment — critical, not self-congratulatory

**Yes, this creates a credible RETURN trigger** — directly grounded, for the first time, in real durable evidence (§25E's own `RecordedMonitorResult`) rather than the aspirational framing #25A could only propose before automation and recording existed. **Named, real limitations, not glossed over:** local-only storage means the *same browser, same device* is required for the recap to mean anything (§8/§96); the very first visit has zero "since you left" value by construction (§7); automatic acknowledgement (§6) means a user who never actually reads the recap is still marked as having seen it. None of these are fatal to the feature's own value proposition, but none is minimized either — this is a genuine, bounded V1, not a finished, universal solution.

---

## §122. Minimum valuable V1 (frozen scope)

Overview return section; one new backend read-model endpoint; local checkpoint (server-watermark-driven); Tier A/B/C content; coverage/freshness disclosure.

---

## §123. Explicit deferrals (comprehensive)

Accounts; cross-device sync; notifications; watchlists; a generic activity feed or audit-log page; a recorded-vs-reconstructed comparison UI; AI summaries/narration; news; historical charts; a methodology-change-event system; full raw-input vintage persistence; historical-revision-propagation detail (§68-71/§117); per-item deep-link evidence anchors beyond the existing domain CTA; Relate reuse for historical claims (§34); server-side caching; multi-tab synchronization (§14).

---

## §124. Implementation split (frozen: two increments, mirroring this project's own proven pattern)

**#25G — Since Last Visit V1 Backend Read Model** (new repository, service, route, response contract, backend test matrix, architecture guards). **#25H — Since Last Visit V1 Frontend** (checkpoint storage, fetch, render, copy, frontend test matrix), gated on #25G, mirroring the State Duration (#24C/#24D) and Automated Maintenance (#25B→#25C, itself CLI-only/backend) precedent of a clean backend/frontend or design/implementation split whenever trust semantics are heavy on one side.

---

## §125. #25G backend contract (frozen, sufficient detail to prevent improvisation)

- **New files:** `app/models/since_last_visit.py` (Pydantic response contract — `SinceLastVisitResponse { after: datetime | None, through: datetime, first_visit: bool, domains: { inflation: DomainRecap, labor: DomainRecap } }`, `DomainRecap { coverage: "CHECKED"|"GAP"|"UNKNOWN", last_checked_at: datetime | None, structural_changes: [...], recalculation_summary: {...} | None, source_updates: [...] }` — exact field-level shape left to #25G's own implementation against this document's own §18-84 semantics, never improvised beyond them); `app/repositories/since_last_visit_repository.py` (the five bounded queries, §61); `app/services/since_last_visit.py` (`SinceLastVisitService` — orchestrates the queries plus the deterministic summarizer, §62); `app/api/since_last_visit.py` (`GET /api/v1/since-last-visit`, §53-54).
- **Zero migration** — every table this reads already exists (`ReleaseCheckRun`/`ReleaseObservationUpdate`/`ReleaseAnalysisUpdate`/`RecordedMonitorResult`/`MaintenanceSweep`/`EconomicRelease`/`EconomicSeries`).
- **Zero change** to any existing table, service, repository, or route.

---

## §126. #25H frontend contract (frozen)

Checkpoint storage (`lib/sinceLastVisitCheckpoint.ts`, §9/§93); fetch wrapper (`api/sinceLastVisit.ts`); render component (`components/overview/SinceLastVisit.tsx`, §76); the new time-of-day formatter (§74); `Overview.tsx` wiring (new top section, §75, no new `useApiResource` call pattern beyond the one new resource); failure/loading behavior (§87-90); copy exactly per §79-86.

---

## §127. #25G backend test matrix (frozen)

First visit (no `after`); valid checkpoint; future/malformed checkpoint (falls back to default window, never 400); boundary timestamp (`completed_at == after` excluded, `completed_at == through` included — exact half-open proof); a same-instant request-race simulation (an event committed after `through` is captured is excluded from this response and present in a follow-up query using this response's own `through`); zero events; only `NO_CHANGE` checks (zero-state A); source data NEW; source data REVISED; structural state change; availability lost/restored; unchanged confirmation, N=1 and N>1; first recorded result; changed-then-changed-back (both transitions present); multiple state changes; multiple evaluation periods from one check run (only the max-period row surfaces, per §68-70 — the direct regression test for #25E's own empirically-discovered propagation case); historical revision propagation excluded from output; partial provider failure (`GAP` coverage, note present, successful results still shown); total failure (`GAP` or `UNKNOWN` as appropriate, zero fabricated content); manual-only processing (`CHECKED` with zero sweep rows); a scheduler gap (`UNKNOWN`); a successful no-work sweep (contributes to coverage evidence, zero feed items); pre-#25E checkpoint (Tier A present, Tier B silently absent for that sub-window, no crash); lookback-boundary clamping (checkpoint older than 90 days, disclosure copy present); mixed-methodology-version window (each item retains its own `methodology_id`, no cross-version comparison); deterministic ordering (`completed_at ASC, id ASC`); deduplication (one fact per run, never three); no AI import anywhere in the new module set; no economic recomputation anywhere (a direct call to `_evaluate_component_at`/`_evaluate_labor_at`/any domain function is never made); no write side effect of any kind (a request never creates, updates, or deletes any row — a structural test, mirroring §63/§74 of `recorded-state-history-v1.md`'s own read-side guard style); no N+1 (a bounded query-count assertion for a realistic window).

---

## §128. #25H frontend test matrix (frozen)

First visit (distinct heading/copy, §7/§85); return visit (correct `after` sent); checkpoint persists across reload; server watermark used, never browser `Date.now()` (a structural test: mock the browser clock to a wrong value and confirm the stored/sent value is unaffected); no advance on API failure (§91); no advance on a render-time throw (§92); refresh immediately after a successful visit shows a near-empty window; storage unavailable (falls back to first-visit UX, no thrown error, no console spam); storage cleared mid-session (next load is first-visit); API failure (rest of Overview unaffected, existing `ErrorMessage`/retry pattern); loading is non-blocking; every zero-state copy variant (§79) renders exactly; coverage-unknown copy renders exactly, never silently upgraded to "no changes"; structural-change copy; unchanged-confirmation copy (both N=1 and N>1 phrasing); source-update copy (NEW and REVISED both); multiple transitions all render, in order, never collapsed; CTAs link to the correct, existing routes, no query params, no new destination; no new nav item exists; accessibility (state carried as text, not color, jsdom text-content assertion with styling stripped); no AI-authored copy anywhere (a structural guard, mirroring `no-economic-logic.test.ts`'s own established pattern, extended to this new module set).

---

## §129. Architecture guards (frozen, for #25G/#25H)

The new backend module set imports no AI/OpenAI/LLM dependency; it never calls, or imports a call path to, `add_recorded_monitor_result`/`add_analysis_update`/`add_observation_update`/`add_check_run` (a hard, structural read-only guard — this feature creates zero economic history); it never imports `app.domain.inflation`/`app.domain.labor`/`app.domain.state_duration` directly (it reads already-persisted rows only, never recomputes); it never imports or calls `app.services.maintenance`/`app.operations.run_maintenance` (coverage is read from `MaintenanceSweep`'s own persisted rows only, per §42, never from triggering a sweep); `GET /since-last-visit` is the only new route, and it is read-only (no `POST`/`PUT`/`PATCH`/`DELETE` exists anywhere in the new router — mirroring `TestNoPublicMaintenanceMutationEndpoint`'s own established precedent); the frontend module set never derives a canonical state transition from a raw observation value (it only renders backend-provided, already-categorized fields, §63); the frontend checkpoint code never reads the browser's own wall clock for anything stored or sent as `after`/`through` (a structural guard: no bare `Date.now()`/`new Date()` inside `lib/sinceLastVisitCheckpoint.ts`, mirroring #25C's own established "no server-local timezone dependence" grep-level guard pattern, adapted to the frontend); no account/auth dependency exists anywhere in the new code (V1 scope, §97); no generic, reusable "event ledger"/"activity log" table or module is introduced anywhere (§57's own explicit rejection, enforced structurally).

---

## §130. GO / STOP checklist

| # | Item | Status |
|---|---|---|
| 1 | What "last visit" means | ✅ §4/§16 |
| 2 | When checkpoint advances | ✅ §5/§93 |
| 3 | First-visit behavior | ✅ §7/§85 |
| 4 | Local state | ✅ §8/§9 |
| 5 | Authoritative clock/cursor | ✅ §10-13 |
| 6 | Race-safe window | ✅ §10-13 |
| 7 | Event spine | ✅ §58-59 |
| 8 | Event sources | ✅ §17 |
| 9 | Structural-change semantics | ✅ §20 |
| 10 | Unchanged-confirmation proof | ✅ §21 |
| 11 | Repeated recalculation aggregation | ✅ §23 |
| 12 | Changed-then-back handling | ✅ §24-25 |
| 13 | Multiple-evaluation-period handling | ✅ §68-70 |
| 14 | Revision propagation handling | ✅ §68-71 |
| 15 | Source-update grouping | ✅ §28-32 |
| 16 | Zero-change copy | ✅ §79 |
| 17 | No-processing copy | ✅ §79 row C |
| 18 | Coverage-unknown behavior | ✅ §40-41 |
| 19 | Maintenance-health role | ✅ §36/§40 |
| 20 | Failed-processing behavior | ✅ §44-46 |
| 21 | Pre-recorded-history behavior | ✅ §48/§104 |
| 22 | Lookback semantics | ✅ §50-51 |
| 23 | Endpoint | ✅ §53 |
| 24 | Request | ✅ §54 |
| 25 | Response/watermark | ✅ §55 |
| 26 | Deterministic ordering | ✅ §58-59 |
| 27 | Deduplication | ✅ §66-70 |
| 28 | Backend/frontend boundary | ✅ §63 |
| 29 | Checkpoint failure behavior | ✅ §91-92 |
| 30 | Methodology-version behavior | ✅ §114-115 |
| 31 | Current-vs-recorded boundary | ✅ §101-103 |
| 32 | Exact V1 scope | ✅ §122-123 |
| 33 | Implementation split | ✅ §124 |
| 34 | Tests | ✅ §127-128 |
| 35 | Guards | ✅ §129 |
| 36 | Credible retention value | ✅ §121 |

All thirty-six resolved.

---

## Appendix: secret safety and version control

No `.env`/`.env.*`/credential file was read, printed, or logged at any point this increment. Nothing in this document was committed or pushed; no production code, migration, model, repository, service, route, or frontend file was created or modified this increment — only this new document.
