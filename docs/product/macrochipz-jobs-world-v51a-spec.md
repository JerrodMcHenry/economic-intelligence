# Jobs World — experience and interaction specification

**Increment #51A.** For review. Not implemented.
**Date:** 2026-09-24
**Audit:** `macrochipz-jobs-world-v51a-audit.md`
**Prototype:** `docs/product/mockups/v51a/index.html`

---

## 1. The question the page answers

**"Employers are still adding jobs and unemployment has barely moved — so why
does MacroChipz call this Mixed?"**

That question is not invented to suit a design. It is what the live data
actually says: payroll employment is `EXPANDING` but `WORSENING`, the
unemployment trend is `STABLE`, and the overall state is `MIXED` because the two
surveys disagree.

Answering it well requires showing the reader something the page has never
shown: **the threshold that turned two numbers into a state.**

### 1.1 What the page must not imply

The reviewed explainer already says it, and the page carries the sentence
verbatim rather than paraphrasing it:

> *This is why the rate alone does not tell you whether the jobs picture
> improved.*

The unemployment rate is **not** a measure of how hard it is to find a job, and
this world has no data that is. See §5.

---

## 2. The visual, chosen from the data

Rates got a curve because it has four maturities on one date. Inflation got a
climb because it has 59 levels of one index. **Jobs has neither shape** — it has
two independent measures, each classified against an explicit numeric band.

So the hero is a **threshold diagram**: a horizontal axis centred on *no change*,
the methodology's own deadband drawn as a shaded band around it, and the
measure's own change plotted as a point.

- **Payroll employment:** −70,333 jobs a month against a ±50,000 band. The point
  sits well outside → `WORSENING`.
- **Unemployment:** −0.10 pp against a ±0.2 pp band. The point sits inside →
  `STABLE`.

Same diagram, two verdicts, one labour market. A reader sees not only what the
state is but **why**, and the two-survey principle becomes the structure of the
page rather than a footnote on it.

Beneath each, the measure's own 60-month series as **context, not hero** — the
sourced line that shows where the current reading sits in five years.

### 2.1 What the diagram must never do

- **No combined score.** The two measures are never averaged; `MIXED` is a
  statement that they disagree.
- **No good/bad colouring.** Employer and household tracks are distinguished by
  hue within the shared violet family; economic-state tones stay out.
- **No interpolation across a gap.** `UNRATE` has a null at 2025-10-01 and the
  line breaks there (§5.1).
- **No arithmetic.** Every average, delta, deadband and state is the backend's.

---

## 3. Section order

| # | Section | Job | Exists today? |
|---|---|---|---|
| 1 | **Hero** | The two-survey distinction, in reviewed words | Replaces `PageHeader` |
| 2 | **Two surveys, side by side** | The switch, the threshold diagram, the reasoning, the 60-month context | **New** (data exists) |
| 3 | **What MacroChipz concludes** | The overall state, and that it is a disagreement | Reframes `LaborHero` |
| 4 | **Why there are two numbers** | Reviewed explainer, in full | New placement |
| 5 | **What the rate alone cannot tell you** | Reviewed explainer, in full | **New placement, load-bearing** |
| 6 | **What this page does not have** | Participation, U-6, openings, claims, wages | **New** |
| 7 | **Recorded conclusions** | 12 states, behind a disclosure | Compacted from 1,413px |
| 8 | **Evidence & methodology** | Both deadband rules, stated | Exists |
| 9 | **What changed / release / Ask / Understand / Revisions** | Unchanged, below | Exists |

---

## 4. Interaction and accessibility

1. Two survey controls, HTML `<button>`, **44px minimum** (measured 168 × 54 at
   390), `aria-pressed`, one selected always, focus stays on the control.
2. The diagram panel is `aria-live="polite"`.
3. Both SVGs are `role="img"` with composed labels naming the change, the
   deadband, whether it falls inside or outside, and the resulting state.
4. A measure that was not computed renders an explicit sentence — including when
   the reader selects it deliberately — and no figure is invented.
5. Every transition paired with `motion-reduce`.
6. Contrast measured on the composite.

---

## 5. Data dependencies — documented, not simulated

| Want | Status | What it would take |
|---|---|---|
| **Job-finding difficulty** (openings per unemployed person, hires rate, median duration) | **Not available.** `JTSJOL` 404. | JOLTS ingestion. This is the single largest gap for a consumer Jobs page. |
| **Participation** (`CIVPART`) | **404** | Ingestion. Needed to explain a falling rate that is not good news. |
| **U-6 underemployment** | **404** | Ingestion. |
| **Initial claims** (`ICSA`) | **404** | Ingestion. Weekly, so also a cadence decision. |
| Wages | Not in either series | Ingestion. |
| Industry / state / demographic detail | Both series are one national number | Ingestion, and a much larger design question. |
| A monthly job-change series | The monitor publishes two 3-month averages, not a series | Backend field. Deriving it from `PAYEMS` levels would be client-side economics. |

### 5.1 A data characteristic, not a gap

`UNRATE` contains **one null observation (2025-10-01)**. It is a legitimate
absence and must be rendered as a gap. A naive minimum over the raw values
coerces `null` to `0` and destroys the axis — this bit the prototype and is
recorded in the audit §6.1.

---

## 6. Unresolved methodology questions

1. **Is `MIXED` the right word for a disagreement between two surveys?** It
   reads as "the economy is mixed", which is a claim about the world. What the
   methodology means is "our two measures disagree".
2. **Should the deadband be on a consumer page at all?** It makes the
   classification auditable, which is this product's whole thesis. It is also a
   methodology parameter, and putting it in the hero gives it prominence the
   underlying figures may deserve more.
3. **Employment `condition` and `momentum` use two different deadbands** (both
   ±50,000 today, and separately configurable). Should the page show both tests,
   or only the one that determined the state?
4. **Which survey should the page open on?** The prototype opens on payroll
   employment because that is where the movement is this month. Opening on
   whichever moved most would be a judgement the product does not currently
   make anywhere.

---

## 7. Acceptance criteria

1. Document height at 390px **below 4,000** (today 4,632).
2. **Zero** controls under 44 × 44px (today 1).
3. Both surveys selectable, each showing its own change, its own deadband,
   whether it falls inside, and the resulting state.
4. A null observation renders as a gap and never as a value.
5. Loading, failed-series and not-computed states all render without a figure.
6. Every existing calculation, provenance field, history entry and unavailable
   state still present.
7. Measured at 390, 440, 768, 1024 and 1440: no overflow, no clipping, no
   overlapping controls.

---

## 8. Existing vs proposed

**Exists and is rendered today:** both states, condition and momentum, both
3-month averages, the momentum delta, the overall state, state duration,
period-over-period changes, the Employment Situation release, 12 recorded states
with replay outcomes, methodology, data basis, and all loading/error states.

**Exists in the API and is NOT rendered today:** both deadband values, the 13
observations inside the monitor response, and the two 60-month series.

**Proposed and genuinely new (presentation only):** the threshold diagram, the
survey switch, the reasoning sentence, the 60-month context lines, and the
"what this page does not have" section.

**Nothing proposed requires a new endpoint, a new field, or a new calculation.**
