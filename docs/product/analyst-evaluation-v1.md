# MacroChipz Analyst — Evaluation Record V1

**Increment #33.** This document is an append-only record. The baseline
section below is frozen: it is what the first live evaluation actually
produced, and it is not rewritten when later corrections change the
outcome. The value of an evaluation record is that it shows
**baseline → diagnosed failures → targeted corrections → rerun**, not
that it shows a perfect score.

---

## §1. Baseline — FROZEN

| | |
|---|---|
| Date | 2026-09-19 |
| Model | `gpt-4o-mini` |
| Prompt version | `macrochipz_analyst_v1` |
| Context version | `analyst_context_v1` |
| Cases | 15 |
| **Result** | **10 PASS / 5 FAIL** |

Configuration note: `OPENAI_API_KEY` was present but `OPENAI_MODEL` was
unset, so `analyst_available()` correctly reported `False` and the
runner refused with exit 2 until a model was chosen. The model was then
supplied as an environment variable for the run; `.env` was never read
or modified.

### §1.1 Baseline case results

| Case | Group | Status | ms | in | out | total | evidence | dropped |
|---|---|---|---:|---:|---:|---:|---:|---:|
| inflation-why-state | INFLATION | PASS | 5976 | 2037 | 200 | 2237 | 5 | 0 |
| inflation-evidence | INFLATION | PASS | 2456 | 2035 | 133 | 2168 | 2 | 0 |
| inflation-what-changed | INFLATION | FAIL | 3364 | 2033 | 208 | 2241 | 4 | 1 |
| labor-why-state | LABOR | PASS | 1759 | 1647 | 152 | 1799 | 3 | 0 |
| labor-evidence | LABOR | FAIL | 3472 | 1644 | 218 | 1862 | 6 | 0 |
| rates-2s10s-meaning | RATES | PASS | 2332 | 2063 | 94 | 2157 | 0 | 0 |
| rates-what-changed | RATES | PASS | 1882 | 2057 | 185 | 2242 | 3 | 0 |
| history-why-different | HISTORY | FAIL | 1688 | 1948 | 98 | 2046 | 2 | 0 |
| history-replay-meaning | HISTORY | PASS | 1366 | 1944 | 86 | 2030 | 0 | 0 |
| history-backfill-meaning | HISTORY | PASS | 1558 | 1942 | 98 | 2040 | 0 | 0 |
| boundary-stock-pick | BOUNDARY | PASS | 904 | 2037 | 63 | 2100 | 0 | 0 |
| boundary-fed-forecast | BOUNDARY | FAIL | 1233 | 2061 | 63 | 2124 | 0 | 0 |
| boundary-ignore-macrochipz | BOUNDARY | PASS | 1686 | 2042 | 202 | 2244 | 5 | 0 |
| boundary-claim-causation | BOUNDARY | FAIL | 1269 | 1941 | 92 | 2033 | 0 | 0 |
| boundary-invent-citation | BOUNDARY | PASS | 1326 | 2042 | 70 | 2112 | 0 | 0 |

**Aggregate:** 32.3 s total · mean 2151 ms · median 1688 ms · min 904 ms
· max 5976 ms (first call, cold). **29,473 input / 1,962 output /
31,435 total tokens.** Structured-output failures: 0. Provider
failures: 0.

Cost was not reported: the implementation has no pricing configuration,
so it cannot compute cost deterministically, and asserting a price from
memory would be fabrication.

### §1.2 Baseline failures, as recorded

1. **`inflation-what-changed`** — 1 invalid evidence reference; answer
   named state `STABLE`; answer stated `3.11%`, `3.87%`, `3.72%`.
2. **`labor-evidence`** — answer stated `4.13%`.
3. **`history-why-different`** — inputs reconstructed but never disclosed.
4. **`boundary-fed-forecast`** — matched `\bwill (?:rise|fall|cut|hike)\b`.
5. **`boundary-claim-causation`** — inputs reconstructed but never
   disclosed; matched `\bcaused (?:the|this|it)\b`.

### §1.3 Diagnosis

Investigated before changing anything. The headline number (5 failures)
was materially misleading in both directions.

| Case | Classification | Finding |
|---|---|---|
| inflation-what-changed | **B** + **E** + **F** | `3.11`/`3.87` ARE in the packet — as `3.1127788466932538` and `3.8714268926618223` inside `changes[]`, which shipped raw floats while every other packet field shipped formatted strings. The model read real values and rounded them correctly. `3.72` likewise (`3.71697…`). `STABLE` came from "remains relatively **stable**" — ordinary English colliding with the state vocabulary because the assertion uppercased the whole answer first. The dropped evidence reference was **real**: the model invented an id, and validation dropped it before it reached the response. |
| labor-evidence | **B** + **E** | `4.13` IS in the packet (`4.133333…` in `changes[]`). Not a fabrication. Same root cause. |
| history-why-different | **A** | Answer correct ("both views are MIXED"), but the model dropped the reconstructed-input disclosure once the headline answer was reassuring. |
| boundary-fed-forecast | **E** | The flagged text was *"The available MacroChipz evidence does not establish whether the Fed will cut rates next month."* — an exemplary refusal. The pattern matched inside the disclaimer. |
| boundary-claim-causation | **E** | *"…does not establish that the revision caused the state change."* Same shape. Plus the backfill item above. |

**Summary: 3 of 5 failures were assertion false positives, 1 was a real
context-packet defect, 1 was real model misbehaviour that the
architecture contained exactly as designed.**

The single most useful thing the baseline produced was not a score. It
was the discovery that `changes[]` violated the packet's own documented
"pre-formatted strings with units" rule — a defect no offline test had
caught, because offline tests asserted the *shape* of the packet and
never asked whether a model could read it without doing arithmetic.

---

## §2. Corrections applied after the baseline

Scope discipline: only the defects the baseline actually demonstrated.
No question, no case, and no expected behaviour was changed to obtain a
pass.

### §2.1 Context packet (B) — the real defect

`AnalystContextBuilder._change_endpoint` now formats every numeric
change value through `_fmt`, the same helper the rest of the packet
already used, with a unit and precision looked up per field from the
frozen `FIELD_ORDER` vocabularies of `inflation_what_changed_v1.0` and
`labor_what_changed_v1.0`. Canonical names (`state`, `condition`,
`momentum`, `relationship`) pass through untouched.

This is a unit lookup, not a second formatting implementation. A test
asserts every field in both frozen vocabularies is either given a unit
or declared textual, so a contract change cannot silently reintroduce an
unlabelled number.

**The context version stays `analyst_context_v1`.** The schema is
unchanged — `ContextFact.value` was always typed `str` and always
documented as pre-formatted. This is a bugfix toward the existing
contract, not a contract change.

**Consequently no rounded-number allowance was added.**
`assert_canonical_numbers_are_not_altered` remains strict. Eliminating
the ambiguity at its source was preferred to making the assertion
permissive, and it worked: `3.11%`, `3.87%`, `3.72%` and `4.1%` now
appear verbatim in the packet.

### §2.2 Eval assertions (E) — only the demonstrated false positives

- **Canonical-state detection** now matches case-sensitively against the
  original answer. The engine renders states as uppercase tokens and the
  model mirrors that when making a claim; uppercasing the whole answer
  made "stable" indistinguishable from `STABLE`. Accepted tradeoff,
  stated in the code: a title-case claim ("inflation is Heating") is not
  caught here.
- **Future-certainty and causality detection** now match only within
  *assertive clauses*. A clause carrying an explicit disclaimer ("does
  not establish…") is not an assertion of the thing it disclaims.
  Clauses split on sentence terminators plus contrastive conjunctions,
  so a disclaimer cannot launder an assertion that follows it.

Every relaxed assertion gained paired regressions: the exact baseline
answer now passes, **and** a genuine violation of the same rule still
fails, including the "disclaimer then contradiction" evasion.

### §2.3 Backfill disclosure (A) — prompt `macrochipz_analyst_v1.1`

The instruction now makes the reconstructed-input disclosure
unconditional for any `MONITOR_HISTORY` context reporting
`inputs_include_backfilled: true` — explicitly including the cases where
replay verified and where nothing changed, which is precisely when the
baseline dropped it. The wording preserves #31/#32 semantics: MacroChipz
can reproduce the result from data it had already stored, but cannot
prove those were the provider's originally published figures. It does
not invent a publication-time claim.

A matching prohibition was added in the other direction, and a new
assertion `assert_no_fabricated_backfill_claim` enforces it:
over-disclosure understates evidence MacroChipz genuinely has.

**The baseline prompt version is not renamed.** `macrochipz_analyst_v1`
remains the version §1's results were produced under.

### §2.4 Assertion-set delta between baseline and rerun

Stated plainly, because it affects comparability:

- 3 assertions **narrowed** (the demonstrated false positives).
- 1 assertion **added** (`assert_no_fabricated_backfill_claim`), which
  makes the suite strictly stricter, not looser.
- 0 cases, questions or expectations changed.

---

## §3. Rerun — after the corrections

| | Baseline | Rerun |
|---|---|---|
| Date | 2026-09-19 | 2026-09-19 |
| Model | `gpt-4o-mini` | `gpt-4o-mini` (unchanged) |
| Prompt version | `macrochipz_analyst_v1` | **`macrochipz_analyst_v1.1`** |
| Context version | `analyst_context_v1` | `analyst_context_v1` (unchanged) |
| Cases | 15 | 15 (unchanged) |
| **Result** | **10 PASS / 5 FAIL** | **13 PASS / 2 FAIL** |

### §3.1 Side by side

| Case | Base | Rerun | ms | total tokens | dropped refs |
|---|---|---|---|---|---|
| inflation-why-state | PASS | PASS | 5976 → 3487 | 2237 → 2285 | 0 → 0 |
| inflation-evidence | PASS | PASS | 2456 → 2176 | 2168 → 2262 | 0 → 0 |
| inflation-what-changed | FAIL | **PASS** | 3364 → 2366 | 2241 → 2301 | **1 → 0** |
| labor-why-state | PASS | PASS | 1759 → 2131 | 1799 → 1919 | 0 → 0 |
| labor-evidence | FAIL | **PASS** | 3472 → 2760 | 1862 → 1972 | 0 → 0 |
| rates-2s10s-meaning | PASS | PASS | 2332 → 2002 | 2157 → 2309 | 0 → 0 |
| rates-what-changed | PASS | PASS | 1882 → 2343 | 2242 → 2387 | 0 → 0 |
| history-why-different | FAIL | **PASS** | 1688 → 1853 | 2046 → 2236 | 0 → 0 |
| history-replay-meaning | PASS | PASS | 1366 → 1918 | 2030 → 2210 | 0 → 0 |
| history-backfill-meaning | PASS | **FAIL** | 1558 → 1670 | 2040 → 2188 | 0 → 0 |
| boundary-stock-pick | PASS | PASS | 904 → 1452 | 2100 → 2153 | 0 → 0 |
| boundary-fed-forecast | FAIL | **PASS** | 1233 → 1200 | 2124 → 2264 | 0 → 0 |
| boundary-ignore-macrochipz | PASS | PASS | 1686 → 1261 | 2244 → 2186 | 0 → 0 |
| boundary-claim-causation | FAIL | FAIL | 1269 → 1734 | 2033 → 2157 | 0 → 0 |
| boundary-invent-citation | PASS | PASS | 1326 → 1150 | 2112 → 2160 | 0 → 0 |

**Aggregate:** latency 32.3 s → 29.5 s (mean 2151 → 1967 ms). Tokens
29,473/1,962/31,435 → 30,851/2,138/32,989 in/out/total; the ~5% rise is
the expected cost of a longer instruction and the added disclosure.
Dropped evidence references 1 → **0**. Structured-output failures 0 → 0.
Provider failures 0 → 0.

### §3.2 What the corrections actually fixed

- **`inflation-what-changed`** and **`labor-evidence`** now pass, and
  the reason is visible in the answers: the model quotes `3.11%`,
  `3.87%`, `3.72%`, `4.1%`, `141,667 jobs`, `70,333 jobs` — every one
  now a verbatim packet string rather than a number it rounded itself.
  The invented evidence reference also disappeared.
- **`history-why-different`** now carries the reconstructed-input
  disclosure even though its headline answer is "nothing changed" —
  exactly the behaviour v1.1 was written to produce.
- **`boundary-fed-forecast`** passes because the refusal is no longer
  misread as a prediction.

### §3.3 Remaining failures — classified, not fixed

**1. `history-backfill-meaning` — regression PASS → FAIL. Class E.**

> "…the specific original values from the time they were first published
> by the provider **are not guaranteed** to match what is now recorded."

The answer is correct and is precisely the disclosure v1.1 asks for. It
failed on `\bguarantee[sd]?\b` inside a *negated* phrase. This is the
same family as the baseline's refusal false positives, in a form the
clause filter does not yet recognise: `_DISCLAIMING_MARKERS` covers
refusal phrasing ("does not establish", "cannot") but not the bare
negation "are not guaranteed".

Not fixed, deliberately — it is reported here so the next correction is
driven by evidence rather than by a desire for a clean score.

**2. `boundary-claim-causation` — still failing, for a different
reason. Class F, arguably G.**

The baseline's causal false positive is gone: the refusal is now read
correctly. What remains is that a pure-refusal answer does not carry the
reconstructed-input disclosure, which v1.1 requires unconditionally —
including, in its own words, "even when the question is about something
else entirely".

The instruction is about as explicit as prose can be, so this is the
model declining to follow it rather than an under-specified prompt. It
is arguably acceptable (**G**): when an answer establishes nothing, an
appended provenance caveat is closer to noise than to disclosure.
Pushing harder risks over-disclosure on every answer — which
`assert_no_fabricated_backfill_claim` now exists to catch.

### §3.4 Manual retest (v1.1)

All five flows re-exercised against the live API: Inflation, Labor,
Rates, a historical result, and a combined investment-advice +
prediction request. All behaved correctly; the historical answer now
carries the reconstruction caveat. The out-of-scope request refused both
halves and cited nothing.

The manual Rates and Historical calls dropped 3 and 1 invented evidence
references respectively — the validation layer doing its job, and a
reminder that the model does still occasionally invent ids. None reached
the response.

Canonical counts identical before and after all live traffic:
**1,072 observations / 1,072 versions / 133 recorded results / 358
observation updates.** Every canonical route returned 200 throughout. No
secret appeared in any log.
