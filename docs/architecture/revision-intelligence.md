# Revision Intelligence

**Status:** implemented (Increment #43)
**Consumes:** #31 observation versioning · #32 replay · #39 Structured Intelligence · #40 permanent objects
**Route:** `/revisions` — a cross-world capability, **not** a fourth Economic World

---

## 1. Measured state before implementation

Queried directly against the local database on 2026-09-21.

| Measure | Value |
| --- | --- |
| Versioned observation rows | **1,072** |
| ...`change_type=BACKFILL, origin=BACKFILL, is_backfilled=true` | **1,072 (100%)** |
| Observations with more than one version row | **0** |
| Observations with more than one distinct value | **0** |
| Superseded rows (`recorded_to` not null) | **0** |
| `OBSERVATION_CHANGE` objects | 358, **all `NEW`**, `previous_value` null throughout |
| Recorded monitor results | 133 (59 inflation, 74 labor) |
| Replay outcomes | **133/133 `MATCH`**, every one `inputs_include_backfilled: true` |
| `recorded_from` span | 4 distinct timestamps, all 2026-09-19 (the migration) |

### **MacroChipz has never captured a genuine revision. Not one.**

Every versioned row is a migration baseline. Every observation change is a first observation. The 133 replays all MATCH trivially, because no input has ever changed — and the service says so itself via `inputs_include_backfilled`.

Stated plainly rather than worked around: `/revisions` is empty, and it says so.

---

## 2. What MacroChipz means by a revision

**A revision is something MacroChipz watched happen.** It recorded value A, then observed the provider publish B.

Three things are routinely mistaken for revisions and are none:

| Not a revision | Why | Local count |
| --- | --- | --- |
| **First observation** | Nothing changed; there was nothing to change from | 358 |
| **Backfilled baseline** | Imported at migration; earlier vintages unknowable | 1,072 |
| **Analysis/state change** | The number did not move; the conclusion did | 44 |

---

## 3. Knowledge states

`RevisionKnowledge` on `ObservationChangePayload`:

- `FIRST_OBSERVATION` — MacroChipz learned a value.
- `PROSPECTIVE_REVISION` — the only state that licenses the phrase **"originally reported"**.
- `BACKFILLED_BASELINE` — value known as of import; **earlier provider vintages are not recoverable**.

Plus `original_value_known: bool` — true only for a prospective revision with a recorded prior value.

**Three states rather than one flag, because they license completely different sentences.** `change_type` alone cannot tell a revision from a migration artifact, and filtering on it would present a database event as economic history.

### Contract change

Additive, with conservative defaults (`BACKFILLED_BASELINE`, `false`), so every pre-#43 object parses and **none claims to know an original value it never saw**. `INTELLIGENCE_CONTRACT_VERSION` is unchanged — an optional field is not a breaking change.

Derived in `IntelligenceBuilder._revision_knowledge`, which reads the stored version rows and returns the conservative answer whenever they cannot prove otherwise. **The frontend never infers revision truth**; it reads this field.

---

## 4. Actual vs reconstructed conclusions

The existing monitor-history contract already separates them, and #43 did not blur it:

| Field | Meaning |
| --- | --- |
| `state` | what MacroChipz **actually recorded** at the time |
| `replay.replayed_state` | what the methodology **reconstructs** now |
| `replay.outcome` | `MATCH` / `MISMATCH` / `NOT_REPLAYABLE` |
| `replay.inputs_include_backfilled` | whether the reconstruction leaned on imported values |

That last flag is why today's 133 MATCHes must not be read as validation: they compare today's data against itself.

---

## 5. Permanent URL decision

**`/intelligence/:id` remains canonical.** `OBSERVATION_CHANGE` already has stable semantic identity and a working permanent page with evidence, metadata and sharing (#40). `/revisions` links **to** it rather than minting a competing `/revisions/:id`, so one object never has two canonical URLs.

Share behaviour and `revision_opened` analytics are reused, not reinvented; no new event was added.

---

## 6. The empty state

`/revisions` currently renders "MacroChipz is watching for revisions", which explains what a revision is, exactly what will be shown when one arrives, and why older ones cannot be reconstructed.

**No fabricated revision appears anywhere in the product.** A test asserts the page contains no "example", "sample", "demo" or placeholder value.

### The historical boundary

`HistoricalBoundary` is reusable and deliberately **states no date**: the stored `recorded_from` on a backfilled row is a migration timestamp, and printing it would dress a database event as an economic fact.

---

## 7. World integration

"Revision history →" appears on **Inflation and Jobs** — the worlds whose providers revise. **Not on Rates**: Treasury publishes a daily observation per business day and MacroChipz has never recorded a second version of one, so a revision affordance there would manufacture symmetry that the source semantics do not support.

---

## 8. Legacy components

| Component | Decision |
| --- | --- |
| `WhatChangedPreview`, `LaborWhatChangedPreview` | **Retired** — unimported and untested after #42A; the exact orphan obligation it left |
| `SinceLastVisit`, `RecentDataUpdates`, overview `LatestDataDetected` | **Retained, unrendered** — still covered by their own tests and a guard; candidates for retirement once their data is genuinely represented |
| `components/labor/LatestDataDetected` | **Untouched** — a different component; the Jobs page still renders it |
| Intelligence History, Latest-revised disclosures | **Kept world-specific** — they answer a different question than `/revisions` |

---

## 9. Rendering

`/revisions` is **client-rendered and not prerendered**. It is not in `STATIC_PATHS`, so its content is not crawlable — consistent with every other world page (#41 §20). Not broadened into SSR.

---

## 10. Limitations

1. **Zero genuine revisions exist**, so the populated path is proven only by tests, not by production data.
2. Replay comparison is **not yet surfaced on a revision card** — there is no revision to attach it to. The contract and service support it.
3. The historical boundary has **no displayable date**, by choice.
4. Rates revisions are not represented, and should not be until source semantics justify it.


---

## Addendum — Increment #45: a new source's first import

#43 was written when every versioned row in the database came from one of two places: a live write, or #31's migration. #45 added a third — **a new provider's entire published history, imported in a single request** — and it is the case most likely to break this document's central rule.

**The rule is unchanged.** A revision is something MacroChipz *watched happen*. Sixty-seven years of Census housing figures arriving at once is not that: MacroChipz knows those values as of the import and cannot say what Census had published for those months before it.

**What changed is where the flag is set.** `is_backfilled` was introduced by #31 for versions its migration synthesized. #45 widens it to a new source's initial import, and the widening is deliberate because the *meaning* is identical — the sentence #31 wrote for it ("this value existed in MacroChipz by this time", never "this was the value the source first published") describes both cases exactly. `ObservationVersionWriter` gained a `baseline` flag, applied **only to `NEW` versions**: a revision is always genuinely observed, because reaching the revised branch at all means MacroChipz held an earlier value and saw it change.

**Which write is a baseline is decided per observation**, by a pure function (`app.domain.housing.is_baseline_import`), not by a flag someone remembers to pass:

- series empty → baseline;
- incoming month older than the newest stored → baseline (filling history backwards is not watching);
- incoming month newer than the newest stored → **observed** first observation (a release arriving; MacroChipz *is* watching);
- incoming month equal to a stored month → not this function's business; if the value differs it is an observed revision.

**The consequence, stated so it is not surprising:** Housing's 4,644-observation import produced **zero** Structured Intelligence objects and appears nowhere on `/revisions`. `IntelligenceBuilder` reads only `is_backfilled = false` versions for Housing. A backfill that surfaced as 4,644 "new data point" entries would be MacroChipz reporting its own migration as economic news — the precise failure this document exists to prevent, at three times the scale of the 1,488-row precedent #39 already records.

**The revision path is proven, without a manufactured revision.** MacroChipz has still never captured a genuine revision in real data. `tests/integration/test_housing_intelligence.py` drives one through the full pipeline against a real database — baseline import, observed arrival, then an observed change — and asserts that `selectRevisions`' existing two conditions select it with **no Housing-specific frontend logic**. It also asserts the harder case: a revision to a value that was itself an imported baseline is reported as `BACKFILLED_BASELINE`, not `PROSPECTIVE_REVISION`, because MacroChipz cannot claim the earlier value was what Census originally published.
