# Post-State-Duration Product Loop & Retention Audit — V1

**Increment #25A.** Read-only product/workflow/architecture audit. No production code changed. Baseline: HEAD `ba923e4` ("Add State Duration V1 frontend (#24D)"), clean working tree. Frontend: 1,032/1,032 passed. Backend: 1,256/1,256 passed, 0 skipped, against the project's established local isolated-Postgres test mechanism.

This document re-derives its findings from the actual current repository — code, tests, and the five prior product documents — not from summary or memory. Every claim below is either a direct citation of prior-audit evidence that is re-verified still true, or new evidence gathered this turn.

---

## 1. Baseline

`git status --porcelain`: empty. `git log -5 --oneline`: `ba923e4` (#24D) → `0024e19` (#24C) → `8a6e908` (#24B) → `ed9de3a` (#24A) → `6d35957` (#23C). #24 is fully committed. Frontend suite: 1,032/1,032 passed (run once, deterministic — matches the #24D final report's own double-verified count). Backend suite: 1,256/1,256 passed, 0 skipped.

---

## 2. Authoritative material reviewed this turn

Read in full: `docs/product/product-experience-audit-v1.md` (#21), `docs/product/relate-compare-audit-v1.md` (#23A), `docs/product/historical-context-state-history-audit-v1.md` (#24A). Read `docs/product/relate-composition-v1.md` and `docs/product/state-duration-v1.md` in full during the increments that produced them this same session and re-confirmed their frozen conclusions directly against current code (composition sentence templates, state-duration boundary types) rather than from memory. Inspected `docs/product/overview-attention-model-v1.md` (#22B) for its salience definition (§4), tier tables (§6-§7), and Recent Data Updates restructuring (§14). Inspected `docs/architecture/current-architecture.md`, `docs/architecture/request-flows.md`, and `docs/ENGINEERING_JOURNAL.md`'s #22B–#24D entries.

---

## 3. Actual product inspected fresh this turn

`layouts/AppShell.tsx` (nav — exactly 4 items: Overview, Inflation, Labor, Releases; no accounts, no login, no fifth item). `pages/Overview.tsx` (full file, current 5-section hierarchy). `pages/Inflation.tsx`/`Labor.tsx`/`InflationHero.tsx`/`LaborHero.tsx`/`WhyThisState.tsx`/`WhyLaborState.tsx`/`StateDurationLine.tsx`/`DataBasisNote.tsx` (all touched directly in #24D this same session — current, not stale). `components/releases/ReleaseRow.tsx` (confirmed the `showMonitorCta` link added in #22B). `pages/Releases.tsx` (header/structure). `app/operations/process_release.py` and `app/services/release_processing.py` (fresh, to settle the automation question precisely — see §25). `app/db/models.py`'s `ReleaseCheckRun` (fresh, to confirm timestamp fields exist for a since-last-visit design). No `.env`/secret file was read at any point.

---

## 4. Current product loop (exact, as built)

```
Open EI (/)
  → Current State: Inflation + Labor peer badges (state + period)
  → How They Relate: one composed sentence over both current states (#23C)
  → What Changed: salience-tiered previews, both domains (#22B fixed the #21 noise defect)
  → Recent Data Updates: one slot per domain (#22B, canonical-release-scoped)
  → Releases: upcoming/recent + schedule-vs-publication disclosure + calendar link
  → [click Inflation or Labor]
Investigate (/inflation or /labor)
  → Hero: state badge + period + State Duration line (#24D, NEW) + Why disclosure
  → full metrics / components / confirmation or employment-unemployment
  → full What Changed (4-tier priority, already existed pre-#24)
  → Recent Data Updates (Labor only) / Relevant Release
  → Evidence & methodology disclosure (now carries the new reconstruction-vs-recorded sentence, #24D)
  → [page ends — no further link]
```

**First major dead end, confirmed unchanged since #21:** the monitor page ends at Evidence & methodology with no "what's related / investigate next" prompt (§7 of #21, re-verified: `pages/Inflation.tsx`/`Labor.tsx` still end their `divide-y` stack at `MethodologyDisclosure`). What a user naturally wants next, having fully understood today's state: **either compare it against something else, or come back and see what changed.** The first is Compare; the second — unaddressed by #21 through #24 — is the actual finding of this audit.

---

## 5. First-60-seconds re-audit (vs. #21, re-scored, not reused)

| Question | #21 verdict | #25A verdict | What changed |
|---|---|---|---|
| What is happening with inflation? | CLEAR | CLEAR | Unchanged |
| What is happening with labor? | CLEAR | CLEAR | Unchanged |
| Did either materially change? | CONFUSING / TOO SHALLOW | **CLEAR** | #22B's salience tiering is real, shipped, tested — routine metric noise can no longer occupy a preview slot ahead of a real state/availability event. Direct fix of #21's own demonstrated defect. |
| Was new economic data recently detected? | CONFUSING | **CLEAR** | #22B's per-domain Recent Data Updates (two slots, canonical-release-scoped) fixes the "one domain hides another's" problem #21 demonstrated. |
| How do Inflation and Labor relate? | *(not asked in #21 — job didn't exist)* | **CLEAR** | #23C's composed sentence answers this in the same 60 seconds, no click required. |
| Is this state new or persistent? | *(not asked in #21 — job didn't exist)* | **NOT ANSWERED ON OVERVIEW** | #24D's State Duration exists but is deliberately excluded from Overview (frozen §41) — reachable only one click into a monitor page. |
| Where should I investigate? | CLEAR | CLEAR | Unchanged |

**Net verdict: materially stronger than #21.** Two of #21's three real defects (noise, single-item Recent Data Updates) are demonstrably fixed. A genuinely new job (relate) is now answered in-window. The one net-new question this iteration adds (persistence/duration) is honestly out of the 60-second window by design, not by oversight (§41 of the frozen contract) — a reasonable and disclosed tradeoff, not a regression.

---

## 6. Five-minute experience

Walking Overview → Inflation → Labor → Releases: a user leaves with a dated, evidenced read of current inflation/labor conditions, a plain-language statement of how the two currently sit together, a reconstructed answer to "how long has this been true," full per-metric evidence, and the upcoming release calendar. This is a materially richer five minutes than #21 documented — #21's five-minute experience had no relate and no duration at all. **Where the user hits a dead end:** exactly where #21 already found one (§4) — the page ends, with no next suggested action, and (new to this audit) no way to *retain* anything they just learned for their next visit. The five-minute session produces real understanding and zero durable artifact.

---

## 7. Day-two experience (critical finding)

Monday: user reads Overview in full, forms an understanding of both domains' states, drills into Labor's "why," reads the reconstructed duration.

Tuesday: user returns. **What is different is entirely a function of whether a human ran `python -m app.operations.process_release` between visits** (§25) — there is no scheduler (confirmed, §25). If nothing was run, the page is byte-for-byte the same data. If something *was* run, the page still reads identically in *shape* — same five sections, same layout — and the user must re-read the entire page from memory to notice any difference. **EI cannot answer "what changed since I was here."** What Changed compares period-over-period (month-over-month, or release-driven before/after), never session-relative (confirmed unchanged from #21 §18/§9; re-verified directly against `app/domain/inflation_what_changed.py`'s `month_over_month_series_momentum` and `app/domain/labor.py`'s `month_over_month_labor_periods` — both compute the exact prior calendar month, never a viewer-supplied timestamp). State Duration (#24D) does not help here either: `duration_months` increments roughly once per month, so two visits a day apart show identical duration text in the overwhelming majority of cases — it is not, and was never designed to be, a day-to-day return signal (confirmed directly in §39 below).

**This finding is unchanged, word for word, from #21's own §18 ("the retention loop is weak") despite four full increments of real capability shipping since.** #24 added new *content* (relate, duration); it added zero new *memory*.

---

## 8. Week-two experience (retention audit)

Does EI become more useful across two weeks of repeat visits? **No.** Nothing is learned, stored, or personalized. Visit 14 is, in kind, identical to visit 1 — same five Overview sections, same four nav items, same two monitor pages, no saved research, no watchlist, no accumulated preference, no history a user can call their own. The only thing that compounds during those two weeks is the **backend's own** revision/change-detection history (`ReleaseObservationUpdate`/`ReleaseAnalysisUpdate`, confirmed still accruing, #21 §29/#24A §3) — and that asset is completely invisible to the user; nothing on any page says "EI has been watching this since X" or shows a growing trail the user can inspect as their own. Confirmed: every session effectively resets.

---

## 9. First major dead end (named explicitly)

Two dead ends exist simultaneously, and they are different in kind:

1. **Within-session dead end** (unchanged from #21 §7/§19): a monitor page ends with no "what's related / investigate next" prompt.
2. **Across-session dead end** (the actual finding of this audit, §7/§8 above): the *first visit ends* by simply closing the tab, and *nothing on the page prepared for a second visit* — no bookmark, no save, no "come back and see" framing, no memory of any kind.

The across-session dead end is the more consequential one: it is the reason a product with four genuinely strong, deterministic, evidenced capabilities still does not generate a habit.

---

## 10. Capability vs. workflow vs. retention vs. compounding value

| Layer | Definition | Current state |
|---|---|---|
| **Capability** | "EI can calculate something." | **Very strong.** Four independent, deterministic, versioned, tested capabilities: Monitor, What Changed, Relate, State Duration. |
| **Workflow value** | "EI saves me repeated work." | **Real, and deepened by #24.** A user genuinely avoids re-deriving momentum classification, confirmation logic, and (new) "how long has this held" by hand. |
| **Retention value** | "EI becomes more useful because I return." | **Essentially zero, unchanged since #21.** Nothing distinguishes visit N from visit 1; nothing invites or rewards a second visit differently from a first. |
| **Compounding value** | "EI accumulates something valuable over time." | **Real on the backend, invisible on the frontend, and itself gated by manual operation.** The revision/change-history asset (#21 §29, #24A §35) grows only as fast as a human remembers to run the CLI — its own compounding is operator-dependent, not automatic. |

**The gap is concentrated entirely in the last two rows**, and #24 — for all its real capability work — did not touch either one. This is the single most load-bearing finding of this audit.

---

## 11. Current reasons to return (honest inventory)

| Reason | Proactively surfaced? | Must user remember to check? | New-since-last-visit distinguishable? | Personalized? |
|---|---|---|---|---|
| A new release published | No | Yes | No (calendar shows schedule, not "since you last looked") | No |
| A new canonical state | No | Yes | No | No |
| A new What Changed event | No (period-over-period only) | Yes | **No — the core gap** | No |
| A revision was detected | No | Yes | No | No |
| State duration progressed | No, and rarely perceptible day-to-day (§39) | Yes | No | No |

Every row is identical: EI never reaches out, the user must always initiate, and even when the user does initiate, EI cannot tell them what's *new* versus merely *recent*.

---

## 12. Habit loop (Trigger / Action / Reward / Investment)

Used strictly as a diagnostic lens, not consumer gamification, per instruction.

- **TRIGGER:** none generated by EI. Purely external — the user's own memory/habit of checking macro data. No email, push, Slack, or in-app badge exists (confirmed, no such code anywhere in the repo).
- **ACTION:** open EI, read Overview. Genuinely well-built as of #24 (§5/§6 above).
- **REWARD:** exists in principle (data sometimes really has changed) but is **never surfaced as new** — the user experiences every visit as "re-read everything to see if anything differs from what I remember," which is *work*, not reward. A variable reward that the product itself hides from the user does not function as a reward.
- **INVESTMENT:** **none.** Nothing about today's visit makes tomorrow's visit better, faster, or more personalized. No data is saved, no preference is set, no watchlist is built.

**Finding: no professional recurring workflow exists yet.** The loop is broken specifically at REWARD-VISIBILITY and INVESTMENT — the two links a returning-user product needs most and the two links #24 did not touch.

---

## 13. Willingness-to-pay re-audit (post-#24, ranked)

1. Maintained, deterministic classification (unchanged, #1 since #21).
2. Structured, revision-aware change detection (unchanged).
3. **State Duration** (new) — "how long has this been true" is a genuinely hard, tedious thing to self-maintain by hand; real, moderate WTP contribution.
4. **Relate composition** (new) — real but thin today (one sentence); modest WTP contribution on its own, more valuable as connective tissue between the two monitors than as a standalone reason to pay.
5. Curated, verifiable evidence trail.
6. Release calendar scoped to what matters.

**Smallest missing capability that would most increase WTP now:** not a new analytical capability — **the return experience.** A user paying for "so I don't have to check manually" cannot yet trust that checking back *itself* saves them anything, because EI still requires them to re-derive "what's new since I checked" by hand. This out-ranks Compare specifically because it completes the product's *existing* promise rather than adding a new one.

---

## 14. "Why not just FRED?" (re-audited)

Unchanged real advantages: classification, revision detection without manual vintage diffing, structured change log (#21 §14). **New, since #21/#24:** a composed cross-domain statement FRED has no equivalent of, and a maintained "how long" answer FRED requires the user to eyeball a chart and decide for themselves. **New risk surfaced by this audit, not previously named:** FRED's own data is continuously current; EI's freshness is now operator-dependent and — confirmed by direct inspection — **nowhere in the UI does a page state when it was last checked for new data** (no "as of {time}" freshness indicator exists on Overview or either monitor page; `grep` for any such string across `components/`/`pages/` returned nothing outside one unrelated docstring comment). This is a real, currently-unaddressed differentiation risk in EI's own favor narrative.

---

## 15. "Why not just ChatGPT / Claude?" (re-audited)

Strengthened, unambiguously, by #24. Beyond #21's already-strong case (reproducibility, versioned methodology, exact evidence — none of which generic AI reliably guarantees), State Duration adds a *reproducible, versioned* answer to "how long" that generic AI could only guess at non-verifiably, and Relate composition adds a reproducible cross-domain statement built from two exact, versioned inputs. Current-capability claim, not aspirational.

---

## 16. "Why not TradingEconomics / a charting tool?" (re-audited)

Unchanged in kind: EI still has no charts and covers only two domains, so it loses outright on breadth and visual history. What it adds — unchanged in *kind*, incrementally stronger in *degree* — is a maintained, deterministic, evidence-linked classification-and-duration layer no calendar or chart dashboard computes or discloses. The differentiation axis remains trust/reproducibility, not breadth.

---

## 17. Candidate audits

### A. Curated Compare

**User problem:** "How do two known-compatible measures compare?" (e.g., Core CPI vs. Core PCE, already partly answered by Confirmation). **JTBD:** deepen investigation of an already-open question. **Frequency:** per-investigation, not per-visit. **Return trigger:** none — it is a within-session depth tool. **Time saved:** real but narrow (avoids a manual FRED lookup + eyeball comparison for a known-safe pair). **Decision value:** moderate. **Differentiation:** low — #21/#23A both already found this reads as "a nicer FRED," since the underlying math (`/analysis/compare`) is unmodified and does no maintained classification of its own. **Architecture readiness:** high — reuses `/analysis/compare` as-is for a pre-vetted pair list (#23A §3/§22). **Implementation complexity:** medium (new UI surface; backend reuse). **Semantic risk:** low, for a curated pair (#23A §12). **Future compounding value:** low — correlation is recomputed fresh every call, nothing accrues. **Dependencies:** none on accounts, scheduler, persistence, or new methodology. **Relationship to core loop:** extends Investigate, does not touch Return. **WTP impact:** moderate. **Retention impact:** **none.**

### B. Save / Watchlist

**What "save" would even mean today** is genuinely underdetermined — save a monitor (there are only two; saving one of two is nearly meaningless), save a series (no series-level UI exists to save from), save a curated comparison (Compare doesn't exist yet), save a research recipe (no such concept exists), watch a release (closest to compelling, since releases are the real external trigger), watch a canonical state (closest to a genuine future notification target). **Which object would a target user naturally want to save today?** Honestly: **none compellingly** — with only two domains, everything worth seeing is already two clicks away at all times; "watching" one of two visible things saves negligible navigation cost. **Time saved:** none. **Decision value:** none by itself. **Differentiation:** none. **Architecture readiness:** localStorage-only V1 is trivial (no schema, no accounts); a cross-device/account version is a large, currently-unjustified lift. **Semantic risk:** none. **Personalization-theater risk (§18 of the prompt, audited directly):** high if shipped alone — "what happens after I watch something?" has no honest answer today (nothing prioritizes it, nothing shows its changes, nothing notifies) — **scored low, explicitly, per the instruction not to assume automatic retention value.** **Dependency:** genuinely useful only once paired with Since-Last-Visit (to filter/prioritize a diff by watched items) — it is *subordinate* to C, not a peer.

### C. Since Last Visit

**User problem:** "I checked EI yesterday (or last week). Show me only what's new." **JTBD:** eliminate the single most repetitive task this ICP performs today — manually re-scanning the whole product to notice what differs from memory. **Frequency:** every return visit — the highest-frequency candidate by construction. **Return trigger:** directly creates one (the promise itself is a reason to come back). **Evidence sources available today, confirmed by fresh inspection:** `ReleaseCheckRun` (append-only, has run timestamps — confirmed via `app/db/models.py`), `ReleaseObservationUpdate`/`ReleaseAnalysisUpdate` (append-only, real before/after evidence, #24A §3/§5). **What can be supported truthfully today, per #24A §29, re-verified:** a client-local last-visit timestamp (`localStorage`, zero accounts) compared against these existing tables' own timestamps, scoped honestly to **"N detected changes since {timestamp}"** — never "everything that changed in the economy." **Truth boundary (audited directly, §20 of the source prompt, this is the central risk):** because release processing is manual (§25), "no changes detected since your last visit" is genuinely ambiguous between "confirmed unchanged" and "nobody checked" — exactly the same ambiguity #24A §5 already proved exists in the underlying audit trail, now inherited by a headline product promise instead of a buried log. **This must be resolved by an explicit, prominent "last checked: {time}" freshness disclosure shipped alongside the diff, not by hiding the ambiguity.** **Architecture readiness:** high — no new persistence, no accounts, reuses existing tables. **Semantic risk:** low. **Future compounding:** the session-local data itself does not compound, but the feature is what makes the backend's already-compounding history visible to a user for the first time — a real, if indirect, force-multiplier on #21's own moat finding. **Dependencies:** none on accounts or scheduler *for a correctly-scoped V1* — but its *honesty* depends on either (a) an explicit freshness disclosure, or (b) reliable automated checking (F) to make "nothing detected" a trustworthy signal rather than an operational artifact.

### D. Recorded State History

**Potential value (per #24A §35, the single most important finding of that prior audit, re-confirmed):** raw historical data and even a *reconstruction* of it are not proprietary — anyone with the same public data and the same published methodology could reproduce them. **A recorded snapshot of what EI concluded in real time, before later revisions occurred, cannot be reproduced by anyone, ever, after the fact.** This is the one candidate in this entire audit that names a genuinely non-reproducible, compounding asset. **Immediate user value:** low — a user gets nothing new to look at on day one; the entire value is retrospective and accrues only with elapsed time. **Should it precede a visible retention feature?** No — #24A's own verdict stands, re-confirmed: it is infrastructure that should be planned for, not built ahead of the feature that needs it. **Architecture readiness:** medium — needs a new table/migration (real, if modest, schema work) and a write-path integration into release processing; the read/reconstruction half already exists (§40 of #24A: recompute is correct for V1, persistence is the *future* half). **Dependencies:** critically, its value is gated by automation (F) — see §21/§29 below.

### E. Growth Monitor

**Would two domains be too narrow now?** Re-evaluated, not assumed, exactly as #24A §32 already did once: the evidence still says no. A third domain requires a full, separately-researched, versioned methodology (mirroring Labor's own multi-increment #20A–#20E research arc — real, substantial, multi-week work), a new frontend page, new release integration, and — critically — **adds a third peer card to an Overview whose core unsolved problem is that a returning user cannot tell what's new even with two.** Breadth *worsens* the exact problem this audit identifies as the bottleneck before it improves anything. **Architecture readiness:** low (new methodology required from scratch). **WTP/differentiation impact:** low-to-moderate at best, and not the *current* bottleneck.

### F. Automated Release-Processing / Maintenance (hidden candidate, audited explicitly per instruction)

**Not infrastructure for its own sake — a product capability: "EI updates itself when economic data changes."** Audited fresh this turn (§25): the existing `ReleaseProcessingService`/CLI is fully deterministic, fully tested, and already contains the exact eligibility check (`occurrence.scheduled_date >= as_of_date`) an automated loop would need — **but the CLI requires an explicit `--occurrence-id`, with no bulk "find all eligible occurrences" mode.** The real gap is therefore narrow and well-scoped: (1) a new "eligible, not-yet-successfully-checked" discovery query, (2) a scheduler/trigger (cron, systemd timer, or equivalent — this project has no existing deployment/ops story beyond "run uvicorn," so *where this runs* is a real, undecided operational question), (3) failure/retry/alerting policy, reusing the existing `ReleaseCheckRun` outcome logging as-is. **Zero new economic logic, zero new persistence for the core mechanism.** **Is it prerequisite infrastructure for C/D and eventually notifications?** Yes, directly: C's own honesty depends on it (§17.C above); D's value as a non-reproducible asset is weakened, not eliminated, without it (manually-triggered snapshots only capture moments someone remembered to trigger — the same gappiness problem #24A §5 already documented for the *existing* sparse audit trail); notifications cannot exist at all without a real trigger (#24A §30).

---

## 18. Watchlist without personalization theater (explicit test)

"What happens after I watch something?" — today: nothing. It is not prioritized, not diffed, not shown differently, not eventually notified on. **Scored low, per the instruction, because it merely bookmarks a page a user could already reach in two clicks.** It becomes real only once Since-Last-Visit exists to filter/prioritize a diff by watched items — at which point "watch" stops meaning "bookmark" and starts meaning "prioritize in my personal diff," a materially different and much more defensible feature. **Verdict: defer Watchlist until after Since-Last-Visit; do not build it as a standalone feature now.**

---

## 19. Since-last-visit truth boundary (worked through explicitly)

The forbidden drift, named precisely: **"changes detected by EI since your last visit" must never read as "everything that changed in the economy since your last visit."** Given release processing is manual, the honest contract is:

- The feature answers exactly: *"Since {last-visit timestamp}, EI detected N change(s) during its own checks."*
- It **must** disclose, prominently, *when EI last actually checked* (`ReleaseCheckRun.completed_at`, most recent across all mapped releases, or per-domain) — not buried in a disclosure, but adjacent to the diff itself, so "0 changes detected" and "last checked 11 days ago" are never separated.
- It must **never** claim or imply that zero detected changes means the underlying economic data is unchanged — only that EI's own checks (whenever they last ran) found nothing.

This single disclosure requirement is what makes C buildable *without* F as a hard blocker — but it also means C's real-world usefulness is directly proportional to how often F (or a human) actually runs checks. This is the crux the rest of this audit resolves in §53/§54.

---

## 20. Recorded state history — moat stress test (repeated from #24A §35, re-verified independently)

Claim to stress-test: *"A deterministic reconstruction from public revised data can be regenerated; a state snapshot calculated at time S before later revisions cannot be recreated unless it was recorded."* **Holds.** Verified directly against the domain layer this session (the `_at`-suffixed functions in `app/domain/inflation.py`/`labor.py` are pure and always reflect *today's* persisted observations — there is no code path anywhere that reads a historical vintage). Public-source data itself is correctly never claimed as proprietary anywhere in this project's own docs (confirmed by grep across `docs/`); the audit agrees this framing is correct and should stay. **What exactly would be unique:** the row itself — `(monitor, evaluation_period, methodology_id, calculated_at)` plus the state it recorded — is a fact about *EI's own history*, not about the economy, and only EI can ever produce it, only at the moment it happens.

---

## 21. Release processing — operational truth (critical, verified fresh)

**Confirmed, directly, this turn:** `app/operations/process_release.py`'s own module docstring states plainly: *"This is deliberately the ONLY way to trigger release processing... Running this script is an operational action, controlled outside normal end-user HTTP traffic."* No scheduler, no cron, no systemd timer, no Celery/APScheduler dependency exists anywhere in `pyproject.toml` or the codebase (confirmed by search). No authentication exists for any write path (by design, per the same docstring). **If release processing remains manual, how much does this undermine "continuously maintained," Since Last Visit, watchlists, and recorded history?** Substantially, and directly: every one of them either claims or implies currency the product cannot currently guarantee without a human's active, undocumented, unscheduled intervention. **This may be more important than any of the five visible candidates — it is.** See §53/§54.

---

## 22. Automated Maintenance — architecture readiness (audited, not implemented)

Eligibility logic already exists at the single-occurrence level (`OccurrenceNotEligibleError`, `app/services/release_processing.py`). What's missing, precisely: a repository-level query for "occurrences whose `scheduled_date <= as_of_date` and no successful `ReleaseCheckRun` yet exists for the current data" (a straightforward extension of existing query patterns, not new domain logic); a process to run that query and call the existing service per eligible occurrence, on a cadence; and a decision about *where* that process runs (this project has no existing background-job or deployment infrastructure at all — the single largest genuine unknown). **None of this requires new economic logic, new persistence, or new methodology.** It is squarely OPERATIONAL DESIGN work.

---

## 23. Operational product truth (frozen language recommendation)

**Can we currently truthfully say "continuously maintained"? No — not operationally, only in the sense that the *underlying methodology* is stable and versioned, never in the sense that the *data* is kept current automatically.** Recommend, for any future copy: prefer "deterministic, versioned, reproducible" claims (all true today, unconditionally) over "continuously" or "always current" claims (not true today) until §25's engineering work lands. **This gap should outrank visible feature development in prioritization** — see §26 (weighted decision).

---

## 24. Head-to-head comparisons

**Save vs. Since Last Visit (§27):** Save alone, with today's product objects, is a bookmark — real value near zero (§18). Since Last Visit alone, even without Save, improves *every* returning user's experience unconditionally, since it needs no per-item selection to be useful. **Since Last Visit should precede Save.**

**Since Last Visit vs. Recorded History (§28):** A useful, *limited*, honestly-scoped Since Last Visit can ship before full recorded history, using existing release-processing tables (#24A §29, re-confirmed §17.C above) — it truthfully says "N detected changes since {timestamp}, last checked {time}," never "everything." Building recorded history first would create a stronger long-term foundation but delivers zero visible user value in the meantime (§17.D) and does not, by itself, solve the truth-boundary problem (§19) — that problem is about *checking cadence*, not about *whether states are durably recorded*. **Since Last Visit should precede Recorded History as a user-facing feature; Recorded History should follow once automation exists to make it comprehensive.**

**Recorded History vs. Automation (§29):** If release processing stays manual, recorded snapshots would only capture manually-triggered moments — the exact same gappiness problem #24A §5 already documented for the *existing* sparse trail, just with a nicer schema. **Automation should precede Recorded History for the resulting asset to be genuinely comprehensive**, not the reverse — persistence without a reliable trigger produces a second sparse table, not a stronger one.

**Compare vs. Retention (§30):** Compare deepens an already-served job (Investigate); it does not touch the unserved one (Return). It solves the smaller current weakness. **Retention wins.**

**Growth vs. Retention (§31):** A third domain adds more content to re-scan by eye every visit, without adding any return trigger — it *worsens* the exact problem this audit identifies before it improves anything else. **Retention wins, decisively, not narrowly.**

---

## 25. Product loop completeness

Target loop: `MONITOR → NOTICE CHANGE → INVESTIGATE → RELATE → UNDERSTAND HISTORY → SAVE/WATCH → RETURN → SEE WHAT CHANGED SINCE LAST VISIT`.

| Link | Status |
|---|---|
| MONITOR | **Exists, strong** (#19A–#22B) |
| NOTICE CHANGE | **Exists, strong** (#22B salience fix) |
| INVESTIGATE | **Exists, strong** (#16B/#20B, near-complete per #21 §7) |
| RELATE | **Exists** (#23C, composition-only, thin but real) |
| UNDERSTAND HISTORY | **Exists, narrow** (#24D — one fact, "how long," not a range/trend) |
| SAVE/WATCH | **Absent** |
| RETURN | **Absent — no trigger of any kind** |
| SEE WHAT CHANGED SINCE LAST VISIT | **Absent — the core gap** |

**First missing link that breaks the loop: RETURN.** SAVE/WATCH and SINCE-LAST-VISIT are both downstream of it conceptually, but SINCE-LAST-VISIT *is* the mechanism that would create the RETURN link in the first place — they are effectively the same missing link, not two separate ones.

---

## 26. Personalization / persistence architecture requirement

**Does EI need accounts now?** No. **Could V1 retention use `localStorage` (last-visit timestamp) without auth?** Yes — this is exactly #24A §29's own recommendation, re-confirmed sound: zero new persistence, zero accounts, a single-device-scoped but honest feature. **Would that be throwaway architecture?** No, provided the design keeps future compatibility in mind (a server-side "since" query parameterized by timestamp, rather than client-side diffing logic baked into a component) — the same discipline already used for `_at`-suffixed period-explicit functions elsewhere in this codebase.

**Multi-device / serious-user requirement:** for this ICP (a professional who may use a laptop and a phone), browser-local persistence is acceptable as a **V1**, not as a permanent production answer — a serious analyst will eventually expect cross-device continuity. **Distinguish explicitly: defer accounts, do not design them now** — nothing about a well-designed localStorage V1 forecloses a later account-backed version; the server-side "since" query shape would be identical either way, only the timestamp's storage location changes.

**Notification requirement:** would need automation (a real trigger) plus a delivery channel (email/push/Slack), neither of which exists. **An excellent return dashboard (Since Last Visit, viewed on open) can and should work before any notification infrastructure** — sequencing: dashboard first, notifications a distinct, later problem (#24A §30, re-confirmed).

---

## 27. Information architecture

Current nav (`AppShell.tsx`, re-confirmed fresh): Overview, Inflation, Labor, Releases — four items, no fifth. **Since Last Visit does not need a new nav item** — its natural home is Overview itself (§37 below), consistent with #23A/#24A's own repeated "no new nav item until content justifies it" discipline. **Watchlist, if ever built, likewise belongs inside existing pages first** (a small badge/filter on Overview), not a new destination — adding a nav item now, before either feature exists, would fragment the IA ahead of the content that should justify it.

---

## 28. Overview as the return surface

**Could Overview evolve from "current macro dashboard" into "what needs my attention since I last checked"?** Yes, and this is the single most natural evolution available given the current architecture: Overview already independently fetches every resource a since-last-visit diff would need (both monitors, both What Changed results, release-processing status) — no new network calls, only a new client-local comparison layer over data already on the page. **What already supports this direction:** the salience tiering (#22B) already produces exactly the shape of "what matters" a since-last-visit view would want to filter by (§38 below); the per-domain Recent Data Updates restructuring already scopes evidence per monitor, which a since-last-visit filter could reuse directly.

---

## 29. Salience + since-last-visit (explicit combination audit)

#22B's deterministic tiering (Tier 1 domain-state changes → Tier 2 structural → Tier 3 corroborating → Tier 4 metric-only) and a since-last-visit filter combine naturally and without any new methodology: **show Tier 1–3 canonical changes whose underlying `ReleaseCheckRun`/event timestamp falls after the viewer's last-visit timestamp, instead of "latest 3 events" full stop.** This would be a genuinely differentiated return experience — no other product in this space combines a deterministic importance tier with a session-relative filter over a maintained change log. **Recommend this combination be the explicit target shape of the Since-Last-Visit contract**, not a flat "everything since X" list.

---

## 30. State Duration + return experience

Monday: "Inflation COOLING for 3 consecutive months." A month later: "COOLING for 4 consecutive months." **Is duration progression itself a return driver? No, assessed directly and confirmed:** the number changes at most once per calendar month, so it is imperceptible across the vast majority of day-to-day or even week-to-week return intervals — it is a *depth* feature (answers "how long," valuable once investigating), not a *return* feature (gives no reason to come back sooner). This matches the prompt's own hypothesis exactly.

---

## 31. Releases + return experience

**Could upcoming releases provide the trigger ("Jobs report tomorrow") and post-release changes provide the reward ("Labor remained STABLE; payroll momentum weakened")?** Yes, in principle, and this is a genuinely strong shape for a *release-driven* (not daily) cadence — exactly matching this ICP's real workflow (§45 below). **What's missing to make it real:** (a) the trigger half exists today (the release calendar, unchanged since #21) but is not *connected* to a personal reminder of any kind — a user must already know to check; (b) the reward half requires the *exact same* honesty discipline as Since Last Visit (§19) — "Labor remained STABLE" after a release is only a trustworthy reward if release processing actually ran promptly after that release, which today depends on a human. **This is not a new candidate — it is Since-Last-Visit's most natural framing for this ICP specifically, and should inform how §67's feature is worded, not treated as a separate feature.**

---

## 32. Recorded history + releases

Would recording monitor state before/after each processed release create an auditable, queryable economic-intelligence event stream that could later power Since Last Visit, notifications, transition history, and revision-impact analysis? **Yes, architecturally** — `ReleaseAnalysisUpdate` already does exactly this today, sparsely (#24A §5). A full recorded-snapshot version (#24A §14's "evaluation snapshot" object) would be the same idea, made complete rather than gap-prone, and only becomes complete once checks run reliably (§21/§29). **Evaluated as architecture, not scheduled ahead of its prerequisite** — this reinforces, rather than changes, the sequencing already derived in §24.

---

## 33. Data freshness and trust

**How does a user know EI is current?** Today: they don't, directly — no page states an "as of" check time anywhere (confirmed, §14). Processing status per-occurrence exists (`Recent Data Updates`) but requires reading individual evidence rows, not a single trust signal. **Would a returning user trust that the dashboard reflects the latest releases? Not confidently, on inspection** — nothing on the page makes that claim or disproves it. **This is a real retention blocker in its own right**, independent of Since-Last-Visit: a user who cannot quickly confirm freshness has less reason to trust that checking back is worthwhile at all. **A prominent "last checked: {time}" indicator is therefore valuable on its own, and doubly valuable as the honesty mechanism Since-Last-Visit itself requires (§19)** — the same UI element serves both purposes.

---

## 34. Return-value sentence (frozen candidate)

**"Open EI and immediately see the important economic changes since you last checked, then drill into the deterministic evidence."** Adopted as the target return-experience thesis for the next feature increment — it composes directly from #22B's already-shipped salience tiering (the "important" half) and the not-yet-built since-last-visit filter (the "since you last checked" half), with zero new economic content in either half.

---

## 35. Natural cadence

Economic data does not change daily — CPI/PCE and the Employment Situation are monthly releases; PAYEMS/UNRATE revisions occur on a similar or slower cadence. **Forcing a daily-engagement framing would misrepresent the product's own data.** The natural cadence for this ICP and this data is **release-driven, with a weekly-review fallback** — a user should be prompted to return around known release dates (the calendar already knows these), not nudged into a false daily habit the underlying data cannot support. This directly shapes how Since-Last-Visit's own copy and framing should work: "since your last visit" naturally collapses to "since the last relevant release" for most real usage patterns, which is honest and appropriately paced, not forced.

---

## 36. Investor and analyst workflows

**Investor:** morning research, before market open, and immediately after a major release are the three most plausible open-EI moments. The current product serves the first two adequately (state + evidence, read in under a minute) but does nothing special for the third (a fresh release just landed) beyond what already existed pre-#24 — no "this just updated because of {release}" framing exists anywhere.

**Analyst / small-shop researcher:** the strongest recurring manual workflow EI could eliminate is exactly the one this audit identifies as unserved — **periodically re-checking multiple sources to notice what changed since the last check**, which is precisely what maintaining a personal macro-monitoring spreadsheet requires, and precisely what a well-built Since-Last-Visit feature replaces.

---

## 37. Time-saved ranking (qualitative, per candidate)

| Candidate | Manual workflow eliminated | Verdict |
|---|---|---|
| Curated Compare | A manual FRED lookup + eyeball comparison for a known pair | Real, narrow |
| Save/Watchlist (alone) | None — "just convenient," per the instruction's own scoring rule | **Scored low** |
| Since Last Visit | The single most repetitive task this ICP performs: manually re-scanning everything to notice what's new | **Highest** |
| Recorded State History | None immediately (value is retrospective/future) | Low, short-term |
| Growth | None — adds work (more to re-scan), does not eliminate any | **Negative** |
| Automated Maintenance | Indirect — eliminates the maintainer's own manual-check burden and makes every other candidate's time-savings trustworthy | High, indirect |

---

## 38. Dependency matrix

| Candidate | Accounts/auth | Scheduler/automation | Persistence (new) | New methodology |
|---|---|---|---|---|
| Curated Compare | No | No | No | No |
| Save/Watchlist | No (V1) | No | No (localStorage) | No |
| Since Last Visit | No | **No (hard)** / honesty-dependent (soft, §19) | No | No |
| Recorded State History | No | **Yes, for the asset to be comprehensive (soft)** | **Yes** | No |
| Growth | No | No | No (reuses generic schema) | **Yes, substantial** |
| Automated Maintenance | No | **Is the scheduler** | No | No |

---

## 39. Architecture-readiness scores (1–5, 5 = most ready)

| Candidate | Existing primitives | New schema | New methodology | Operational complexity | Semantic risk | Testability | Overall |
|---|---|---|---|---|---|---|---|
| Curated Compare | 5 | 5 | 4 | 5 | 4 | 5 | **4.7** |
| Save/Watchlist (localStorage) | 3 | 4 | 5 | 4 | 5 | 4 | **4.2** |
| Since Last Visit | 4 | 5 | 5 | 3 | 3 | 4 | **4.0** |
| Recorded State History | 3 | 2 | 4 | 3 | 3 | 4 | **3.2** |
| Growth | 2 | 3 | 1 | 3 | 3 | 4 | **2.7** |
| Automated Maintenance | 4 | 5 | 5 | 2 | 5 | 3 | **4.0** |

---

## 40. Product-value scores (1–5)

| Candidate | Return value | Time saved | Decision value | Differentiation | WTP impact | Compounding value |
|---|---|---|---|---|---|---|
| Curated Compare | 1 | 3 | 3 | 2 | 2 | 1 |
| Save/Watchlist (alone) | 2 | 1 | 1 | 1 | 1 | 2 |
| Since Last Visit | **5** | 4 | 3 | 4 | 4 | 2 |
| Recorded State History | 2 | 1 | 2 | 3 | 2 | **5** |
| Growth | 2 | 2 | 2 | 2 | 2 | 2 |
| Automated Maintenance | 3 | 2 | 2 | 3 | 3 | 4 |

---

## 41. Implementation-cost scores (relative)

| Candidate | Backend | Frontend | Persistence | Operations | Testing | Methodology | Overall |
|---|---|---|---|---|---|---|---|
| Curated Compare | LOW | MEDIUM | LOW | LOW | MEDIUM | LOW | **MEDIUM** |
| Save/Watchlist (localStorage) | LOW | MEDIUM | LOW | LOW | MEDIUM | LOW | **LOW-MEDIUM** |
| Since Last Visit | LOW | MEDIUM | LOW | LOW | MEDIUM | LOW | **LOW-MEDIUM** |
| Recorded State History | MEDIUM-HIGH | LOW | HIGH | LOW | MEDIUM-HIGH | LOW | **MEDIUM-HIGH** |
| Growth | HIGH | HIGH | LOW | MEDIUM | HIGH | **VERY HIGH** | **VERY HIGH** |
| Automated Maintenance | MEDIUM | LOW | LOW | MEDIUM-HIGH | MEDIUM | NONE | **MEDIUM** |

---

## 42. Risk scores

| Candidate | Economic-semantic | Historical-truth | Operational | UX complexity | Architecture debt |
|---|---|---|---|---|---|
| Curated Compare | LOW | LOW | LOW | LOW | LOW |
| Save/Watchlist | NONE | NONE | LOW | MEDIUM (theater risk, §18) | MEDIUM (if account migration later) |
| Since Last Visit | LOW | **MEDIUM-HIGH (§19)** | LOW | LOW | LOW |
| Recorded State History | LOW | MEDIUM (reconstructed-vs-recorded conflation, mitigable per #24B precedent) | LOW | NONE (no UI needed V1) | LOW |
| Growth | MEDIUM | LOW | MEDIUM | MEDIUM (re-crowds Overview) | LOW |
| Automated Maintenance | NONE | **NONE (reduces this risk elsewhere)** | MEDIUM-HIGH | NONE | LOW |

---

## 43. Weighted decision

Weights used exactly as suggested, unmodified: 25% return/retention, 20% time saved/workflow, 15% WTP, 15% differentiation, 10% compounding, 10% architecture readiness, 5% implementation efficiency. Scores drawn directly from §40/§39/§41 (implementation efficiency = inverse of cost, 5=cheapest).

| Candidate | Weighted score |
|---|---|
| **Since Last Visit** | **4.08** |
| Automated Maintenance | 3.00 |
| Recorded State History | 2.38 |
| Curated Compare | 2.15 |
| Growth | 1.95 |
| Save/Watchlist | 1.68 |

**Since Last Visit wins on the weighted formula, decisively — consistent with every qualitative finding above, not contradicting it.** Automated Maintenance ranks a clear second, ahead of every other visible candidate, which is exactly the signal that it is not a distraction from the real answer but the mechanism that makes the real answer trustworthy.

---

## 44. Prerequisite vs. feature (the critical distinction)

**The winner of the weighted score (Since Last Visit) is not automatically the winner of "what ships first."** Per §19, C's own honesty is conditional on either (a) a prominent freshness disclosure, or (b) reliable automated checking. Given (a) is cheap and (b) is a real, separate, well-scoped engineering effort, the correct sequencing is: **ship C with (a) as its own hard requirement, not gated on (b) — but schedule (b) immediately after, because every candidate downstream of C (Watchlist prioritization, Recorded History's comprehensiveness, eventual notifications) becomes meaningfully more valuable, and C itself becomes meaningfully more honest, the moment (b) exists.** This is the prompt's own worked example (§54), independently re-derived here, not assumed.

---

## 45. Sequencing / dependency graph (derived, not assumed)

```
Automated Maintenance (F)
  → makes "last checked" recent and trustworthy
  → makes Since Last Visit's "nothing detected" signal honest without a disclosure caveat
  → makes Recorded State History (D) a comprehensive, gap-free asset if/when built
  → is a prerequisite for real Notifications (not recommended yet)

Since Last Visit (C) — buildable now, with an explicit freshness disclosure
  → creates the RETURN trigger the product currently lacks entirely
  → makes Watchlist (B) meaningful (prioritizing a diff, not bookmarking a page)
  → is the natural home for combining with Salience (#22B) — §29 above

Recorded State History (D)
  → depends on (F) for comprehensiveness, not for basic existence
  → is the true long-term moat (#24A §35), sequenced deliberately after the visible retention win

Curated Compare (A) and Growth (E)
  → independent of all of the above; deprioritized this cycle, not blocked by it
```

---

## 46. Compounding-asset finding

**Recorded states, once written, can never be reconstructed later if the moment is missed — this is the one truly irreversible asset among all candidates audited.** Release-event history (already exists, sparsely) and user watchlists/saved research/usage preferences are all compounding in a weaker sense (delayed rather than never-recreatable if building is postponed). **Strategic implication, confirmed:** every day recorded-snapshot persistence is *not* built is a day of that specific asset gone forever — but this does not override the sequencing in §45, because building persistence before automation exists would only accumulate a second sparse, gap-prone table, not a genuinely comprehensive one. The delay cost is real but is a cost of delaying *automation*, not of delaying the *table*.

---

## 47. Delay cost

**Recorded State History:** real, non-zero, and irreversible in the narrow sense above — but its irreversibility is already partially incurred today (every day without automation is a day the *existing* sparse trail also fails to capture, regardless of whether a new table exists). **Automation delay cost, specifically:** every week release processing stays manual is a week of potential gaps in whatever historical asset is eventually built, compounding the eventual asset's own incompleteness. **This is the stronger argument for prioritizing (F) soon, not for building (D) immediately** — the asset's completeness, not its existence, is what delay actually costs.

---

## 48. MVP vs. portfolio analysis

**As a real product:** the recommendation in §53/§54 is unambiguous — retention is the bottleneck, and Since Last Visit (backed by a freshness-first Automated Maintenance increment) is the correct next investment on pure product-value grounds. **As a portfolio/engineering-demonstration project:** Automated Maintenance specifically demonstrates event-driven scheduling, idempotent operational design, and reliability engineering — skills genuinely underrepresented so far in a codebase that has, until now, been almost entirely request/response and pure-function-driven. Since Last Visit demonstrates client-local state design and a session-relative filtering layer over an existing event log — a different, complementary skill. **Neither recommendation is chosen for portfolio reasons; both happen to also serve that purpose well, which is noted, not used to override the product case.**

---

## 49. WTP moment

**First plausible "I would pay for this" moment:** a user opens EI after a week away, expecting to have to manually re-derive what changed, and instead sees — immediately, without re-reading anything — a short, honest, evidenced list of what actually moved since their last visit, each item traceable to full evidence. The pain removed is exactly the manual-re-scan tax named throughout this audit (§9/§37). **Does the recommended next candidate move toward this moment? Yes, directly — it is this moment.**

---

## 50. Return moment

**First plausible "I need to check EI" moment:** a known release date passes (§35/§45's own natural-cadence finding) and the user remembers EI will have processed it. **Does the current product generate that trigger? No** — the calendar shows the date but nothing connects it to a personal reminder or a promise that checking back will show something new. **What candidate would create it?** Since Last Visit, framed around release-driven cadence (§31/§35), directly creates this trigger for the first time.

---

## 51. Trust moment

**What makes a user trust EI enough to depend on it?** The existing pattern (#21 §13/§27, unchanged and still strong): methodology IDs, evidence tables, explicit revision framing, deterministic-never-AI guarantees. **Does the next feature strengthen or weaken trust?** Strengthens it, *conditional on* the freshness-disclosure discipline in §19/§33 being honored — an undisciplined Since-Last-Visit implementation (no freshness indicator, implicit "quiet = confirmed unchanged" framing) would be the first black-box-adjacent feature in this product's history, actively weakening the exact trust the rest of the product has carefully earned. This is not a hypothetical caution; it is the load-bearing design constraint for whichever increment implements C.

---

## 52. Candidate failure modes (mandatory)

- **Curated Compare:** ships as a nicer research toy; zero retention effect; user still has no reason to return sooner.
- **Watchlist (alone):** bookmarks with no monitoring behind them; "personalization theater" the moment a user notices nothing happens after saving.
- **Growth:** more dashboard breadth on top of the same weak habit loop; actively worsens the day-2 re-scan burden before it helps anything.
- **Recorded State History (built first, alone):** excellent infrastructure, genuinely invisible to any user for months; risks becoming a second sparse table if automation never follows.
- **Automated Maintenance (built alone, no visible feature follows):** an excellent, reliability-improving backend change with zero perceptible product improvement — a real risk if it is mistaken for the *whole* answer rather than the prerequisite half of one.
- **Since Last Visit (built without the freshness discipline in §19):** a useful-looking UI built on an honesty gap — "nothing changed" silently means "nobody checked" as often as it means the economy was quiet, eroding exactly the trust (§51) the rest of the product has earned.

---

## 53. What NOT to build next (explicit)

- **Build next (user-facing feature):** Since Last Visit (C), scoped per §19/§29/§34.
- **Prerequisite (engineering, may differ from the feature):** Automated Release-Processing Maintenance (F) — sequenced as an immediate design/freeze turn, in parallel with or just ahead of C's own contract freeze, so C can ship with an honest, improving freshness story from day one rather than a static caveat.
- **Runner-up:** Curated Compare (A) — real, safe, backend-ready, but does not touch the bottleneck this audit identifies; remains the correct #2 for exactly the reasons #23A/#24A already gave, now more clearly true given #24 already delivered Relate.
- **Defer explicitly:** Save/Watchlist (B) — until Since Last Visit exists to give it a real job. Growth (E) — breadth is not, and has repeatedly not been, the bottleneck. Recorded State History (D) — sequence after Automated Maintenance so the asset it produces is comprehensive rather than gap-prone; not abandoned, deliberately deferred.

---

## 54. Next product thesis

**"EI becomes habit-forming when it can honestly tell a returning user what's new since they last checked, without them re-reading everything."**

**"EI becomes worth paying for when that same honest 'what's new' promise is backed by reliable, automated checking, so a paying user never has to wonder whether 'nothing changed' means the economy was quiet or nobody was watching."**

These are deliberately different, per the audit's own framing — the first is a UX/product claim achievable with today's architecture (§17.C, §26); the second is a trust claim that requires the operational work in §21/§22/§25 to be fully true rather than partially true.

---

## 55. Positioning test

Current positioning (`pages/Overview.tsx`'s own header, unchanged since #19A): **"Know what changed in the economy — and prove why."** Does the retention direction suggest evolving toward **"Know what changed since you last checked — and prove why"**? **Plausible, but not adopted here** — per the explicit instruction not to change positioning merely because it sounds good. The current positioning already comfortably covers a since-last-visit feature (it is still "what changed," merely re-anchored to a session-relative period instead of a calendar period) and does not need to change to accommodate it. **Recommend leaving positioning unchanged through the next increment; revisit only if Since Last Visit becomes prominent enough to be the product's own headline framing**, mirroring #23A §40's and #24A §51's identical, repeatedly-correct caution.

---

## 56. Recommended next user-facing feature

**Since Last Visit — a deterministic, honestly-scoped, session-relative filter over Overview's already-fetched resources plus existing release-processing history, combined with the already-shipped #22B salience tiering, always paired with an explicit "last checked: {time}" freshness disclosure.**

**Why:** it is the only candidate that directly creates the RETURN trigger this product has never had (§25); it wins the weighted decision decisively (§43) without any weight manipulation; it requires no accounts, no new persistence, no new methodology (§38/§39); and it completes, rather than expands, the product's own existing positioning (§55).

---

## 57. Recommended next engineering increment

**Automated Release-Processing Maintenance — Operational Design & Contract Freeze.**

**Goal:** determine, and freeze, the exact mechanism (scheduler choice, hosting/runtime location, cadence, eligible-occurrence discovery query shape, failure/retry policy, alerting) by which release processing runs without a human invoking the CLI by hand.

**Scope:** audit/design only — a new repository query for "eligible, not-yet-successfully-checked" occurrences; evaluation of scheduler options appropriate to this project's actual deployment story (which does not exist yet and must be honestly assessed, not assumed); explicit failure/idempotency/retry semantics reusing `ReleaseCheckRun`'s existing outcome model unmodified; zero new economic logic, zero new persisted monitor-state schema (that is #59's later, separate concern).

**Why now, and not Since-Last-Visit's own implementation first:** per §44/§45, Since Last Visit's *contract* (§67-equivalent product freeze) can and should proceed in parallel — but shipping its *implementation* ahead of even a frozen automation plan risks locking in the exact honesty gap named in §19/§51 as a permanent design assumption rather than a temporary, disclosed limitation.

**What it unlocks:** an honestly-improving freshness story for Since Last Visit from day one; a comprehensive (not gap-prone) future Recorded State History asset; the real trigger notifications would eventually need; and — named plainly — the first truthful basis for ever claiming "continuously maintained" in this product's own copy.

---

## 58. Classification

**OPERATIONAL DESIGN**, for the Automated Maintenance increment specifically (§57) — it is neither a product-contract freeze (no new user-facing semantics), nor an architecture audit in the #21/#23A/#24A sense (no product/methodology question is open), nor an implementation turn (nothing should be written yet), nor methodology research (zero new economic content). It is a scoped operational decision: how, where, and how safely does an existing, fully-tested service get invoked without a human.

A **separate, PRODUCT CONTRACT FREEZE** increment is recommended immediately after (or in parallel) for Since Last Visit's own exact semantics (§67) — mirroring the #22A→#22B and #23A→#23B→#23C and #24A→#24B→#24C→#24D patterns this project has now used four times successfully.

---

## 59. Recommended next 3–5 increments

1. **#25B — Automated Release-Processing Maintenance: Operational Design & Contract Freeze** (§57/§58).
2. **#25C — Automated Release-Processing Maintenance: Implementation** (backend-only; the eligible-occurrence query + scheduler wiring frozen in #25B; the existing `ReleaseProcessingService`/CLI called unmodified per eligible occurrence; a manual-override/dry-run mode preserved for operator control).
3. **#25D — Since Last Visit V1: Product Contract Freeze** (client-local last-visit timestamp semantics; exact honest scoping per §19; exact freshness-disclosure copy and placement; exact combination with #22B's salience tiers per §29; placement decision — Overview, per §27/§28; explicit rejection of any "everything changed" phrasing).
4. **#25E — Since Last Visit V1: Implementation** (mostly frontend — `localStorage` timestamp, reuse of existing endpoints/resources already fetched by Overview; a small backend read extension only if a clean range-query over existing tables doesn't already exist cleanly at the needed grain — to be confirmed during #25D's own inspection, not assumed here).
5. *(Deferred, not scheduled yet)* **Recorded State History V1 — Product/Architecture Contract Freeze**, once #25B–E ship and the automation cadence has run long enough to be trusted as the asset's own foundation.

---

## 60. Stop conditions (explicit, not hand-waved)

The audit discovered exactly the condition named in the prompt's own §71: release processing is manual, and the best-scoring retention feature (Since Last Visit) depends, for its own honesty, on reliable automated updates. **This is accounted for directly in the final recommendation, not overridden by it:** the recommended next *engineering* increment is the automation design work (§57), explicitly sequenced ahead of Since Last Visit's *implementation* (though not ahead of its *contract freeze*, which can and should proceed in parallel, per §44). **Architecture is not fully ready for a "since last visit" feature to make its strongest, most trustworthy claim today** — it is ready for a smaller, honestly-disclosed version today, and ready for its strongest version only after #25B/#25C land. Both halves of this finding are stated plainly, per the GO standard in §61.

---

## Appendix: secret safety and version control

No `.env`/`.env.*`/credential file was read, printed, or logged at any point this increment. The backend test run used the project's established local isolated-Postgres mechanism (trust-auth, no password). Nothing in this document was committed or pushed; no production architecture doc (`current-architecture.md`, `request-flows.md`, `ENGINEERING_JOURNAL.md`) was modified this increment, per instruction; the working tree outside this new file was not modified.
