# Jobs World — product audit

**Increment #51A.** Audit and prototype only. **No production frontend or
backend file was modified**, no dependency added, nothing committed.
**Date:** 2026-09-24
**Prototype:** `docs/product/mockups/v51a/index.html`
**Specification:** `macrochipz-jobs-world-v51a-spec.md`

---

## 0. Where Jobs stands, after Rates and Inflation

`/jobs` has already inherited the shared fixes from #49B and #50B — the 44px
explanation trigger and the enlarged disclosure summaries — so it is in better
shape than either world was when audited.

**One target under 44px, zero overflow, zero clipping at every width.** That is
a materially better starting point than Inflation's 11/23.

What it has not inherited is the thing both other worlds gained: **a picture.**

---

## 1. Measured, at genuine viewports

Chrome, real CSS widths, same-origin iframe, dark theme, live local API
(`evaluation_period` 2026-08-01).

| | 390 | 440 | 768 | 1024 | 1440 |
|---|---|---|---|---|---|
| **Document height** | **4,632px** | 4,271 | 3,340 | 3,342 | 3,344 |
| Horizontal overflow | 0 | 0 | 0 | 0 | 0 |
| Text clipped | 0 | 0 | 0 | 0 | 0 |
| **Targets under 44px** | **1** | 1 | 1 | 1 | 1 |
| **Charts** | **0** | 0 | 0 | 0 | 0 |
| `<h2>` sections | 10 | 10 | 10 | 10 | 10 |

The single undersized target is the `Revision history →` link at the page foot
(121 × 17px).

### 1.1 Section heights at 390px

| Section | Height | Share |
|---|---|---|
| **Intelligence history** | **1,413px** | **31%** |
| Employment | 631 | 14% |
| Unemployment | 599 | 13% |
| Employment Situation release | 316 | 7% |
| What changed | 253 | 5% |
| Current state | 243 | 5% |
| Latest data detected | 145 | 3% |
| Understand this | 134 | 3% |
| Ask MacroChipz | 113 | 2% |
| Evidence & methodology | 84 | 2% |

Intelligence history is **nearly a third of the phone page** — the same finding
as Inflation's, and larger.

### 1.2 Repetition

"Mixed" ×4, "Cooling" ×2. Four state words — Mixed, Cooling, Expanding,
Worsening — appear before any plain-English sentence.

---

## 2. What the API actually has, and what it does not

This decided the design, so it is recorded first.

| Series | Status | Detail |
|---|---|---|
| `PAYEMS` | **200** | 60 monthly observations, 147,771 → 159,075 thousands, FRED |
| `UNRATE` | **200** | 60 monthly observations, 4.7 → 4.1 percent, FRED — **one null at 2025-10-01** |
| `CIVPART` (participation) | **404** | — |
| `EMRATIO` (employment ratio) | **404** | — |
| `U6RATE` (underemployment) | **404** | — |
| `JTSJOL` (job openings) | **404** | — |
| `ICSA` (initial claims) | **404** | — |

**Everything that would describe the experience of looking for work is absent.**
Participation, U-6, openings and claims all 404. The brief asked about
job-finding difficulty; the honest answer is that this API cannot speak to it
today, and the prototype says so in its own section rather than gesturing at it.

### 2.1 Data already fetched and never rendered

The monitor returns **7 payroll observations and 6 unemployment observations**
inside `employment.observations` / `unemployment.observations`. The page renders
neither as a series. The 60-month series at `/api/v1/series/{id}/observations`
are not requested at all.

### 2.2 A real data characteristic worth naming

`UNRATE` contains **one null observation (2025-10-01)**. Any chart added to this
world must break the line there rather than plot it — and a naive `Math.min`
over the raw values coerces that `null` to `0` and wrecks the axis. This bit the
prototype before it was caught (§6.1).

---

## 3. Prioritized findings

### P0 — No visualisation, and 120 observations available

Zero charts. Two 60-point monthly series are one request away, and 13 more
observations are already inside the monitor response.

### P1 — The classification is shown; the reasoning is not

The page states Mixed, Cooling, Expanding, Worsening, and prints
`CURRENT 3M AVG 71,333` / `PRIOR 3M AVG 141,667` as separate cards. It never
puts them together with the **deadband** that turned them into a state — even
though `condition_deadband_jobs`, `momentum_deadband_jobs` and
`unemployment_deadband_pp` are all in the response.

A reader cannot tell why 71,333 jobs a month is "Cooling" while a 0.1pp move in
unemployment is "Stable". The answer is in the data and is never shown.

### P2 — The most interesting fact on the page is furniture

Hiring pace **roughly halved** — 141,667 → 71,333 a month — while unemployment
moved 0.1pp. That is the story, and it is rendered as two grey stat cards.

### P3 — Intelligence history is 31% of the phone page

1,413px, for twelve recorded states.

### P4 — The first screen is four state words

"Mixed", then "Cooling", "Expanding", "Worsening", before any sentence a
non-economist can use.

### P5 — One target under 44px

`Revision history →`, 121 × 17px.

### P6 — The two-survey distinction is present but not structural

`TwoSurveysNote` exists and is good. But the page's shape — Employment section,
then Unemployment section — presents them as two parts of one report rather than
as **two different measurements that can disagree**, which is what they are and
what the reviewed explainer says.

---

## 4. What is good and must survive

1. Every figure is backend-computed; the page composes and formats.
2. **Deadbands are published**, which is rare and is what makes the
   classification auditable.
3. Employment carries *condition* and *momentum* separately and never merges
   them into one score.
4. The overall state is `MIXED` when the two disagree — **never averaged**.
5. `TwoSurveysNote` already refuses to treat the two surveys as one number.
6. Recorded state history with replay outcomes.
7. `RelevantRelease` ties the page to the Employment Situation schedule.

---

## 5. Retain / replace / move

| Element | Decision | Why |
|---|---|---|
| `labor_v1.0`, every state, deadband, average and observation | **Retain, untouched** | Not in scope, not defective. |
| `PageHeader` "Jobs" + technical standfirst | **Replace** | A hero built on the two-survey distinction. |
| `LaborHero` state badge | **Retain, move** | A conclusion; it belongs after the evidence. |
| **The deadband** | **SURFACE** | Already in the response, never rendered. |
| `EmploymentSection` / `UnemploymentSection` as sibling sections | **Replace** | Becomes one switch between two surveys — the distinction becomes the structure. |
| The 3M-average stat cards | **Replace** | Become the two ends of the threshold diagram. |
| `PAYEMS` / `UNRATE` 60-month series | **ADD** | Available, unused. |
| `WhatChangedSection` | **Retain** | Period-over-period evidence. |
| `LatestDataDetected` | **Retain, move** | Below the orientation. |
| `RelevantRelease` | **Retain** | Unchanged. |
| `IntelligenceHistorySection` | **Retain, collapse** | 1,413px, 31% of a phone page. |
| `TwoSurveysNote` | **Retain, promote** | It is the page's thesis. |
| `MethodologyDisclosure`, `AskMacroChipz`, `UnderstandWorld` | **Retain** | Unchanged. |
| `Revision history →` link | **Retain, enlarge** | 17px. |
| "What this page does not have" | **ADD** | Does not exist. |

---

## 6. Prototype — measured

| | 390 | 440 | 768 | 1024 | 1440 |
|---|---|---|---|---|---|
| Document height | **3,626** | 3,508 | 2,918 | 2,870 | 2,870 |
| *Current page* | *4,632* | *4,271* | *3,340* | *3,342* | *3,344* |
| Horizontal overflow | 0 | 0 | 0 | 0 | 0 |
| Text clipped | 0 | 0 | 0 | 0 | 0 |
| **Controls under 44px** | **0** | 0 | 0 | 0 | 0 |
| Charts | **2** | 2 | 2 | 2 | 2 |
| Survey controls | 2 @ 168×54 | ✓ | ✓ | ✓ | ✓ |

Mobile falls **22%**; desktop **14%**.

**Interaction verified:** both surveys switch, focus retained, exactly one
selected, each explains its own classification against its own deadband from the
backend's own numbers. **States verified:** loading shows three skeletons and no
figures; a failed observations request shows an alert with a Retry and no
figures, while the monitor's classification still renders; a measure that was
not computed says so and invents nothing — including when it is explicitly
selected.

### 6.1 Two defects found in the prototype and fixed

1. **A null observation was drawn as a value.** `UNRATE`'s 2025-10-01 null went
   into `Math.min`, where `null` coerces to `0` — so the axis floor became 0
   instead of 3.4 **and** the line dived to the bottom of the chart at that
   month. A figure the provider never published, rendered as data. The line is
   now broken at the gap, the axis uses only real values, and both the caption
   and the accessible label state "1 month not published".
2. **The deadband legend overflowed at 390 and 440.** Positioned at the band's
   edge, it ran past the card. It is now a caption under the track.

---

## 7. Recommendation

Build the threshold diagram. It uses only fields already in the response, it
answers the question the current page leaves unanswered — *why is this the
state?* — and switching between the two surveys makes the product's own
two-survey principle the structure of the page rather than a note on it.

**HARD STOP before implementation, per the brief.**
