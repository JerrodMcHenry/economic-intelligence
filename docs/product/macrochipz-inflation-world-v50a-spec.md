# Inflation World — experience and interaction specification

**Increment #50A.** For review. Not implemented.
**Date:** 2026-09-23
**Audit:** `macrochipz-inflation-world-v50a-audit.md`
**Prototype:** `docs/product/mockups/v50a/index.html`

---

## 1. The job

**A person who has noticed their shopping costs more should learn, within one
screen, that inflation is the *slope* of a line that has been climbing — and
that a smaller slope is still a climb.**

Four things they should leave with:

1. how quickly prices are changing;
2. why a lower rate is not a lower price;
3. what headline and core are, and why there are two;
4. what this data cannot tell them about their own expenses.

---

## 2. The idea: one chart carries the whole lesson

**Rates got a curve. Inflation gets a climb.**

The primary visualisation is the **Core PCE price index itself** — 59 real
monthly observations, `Index 2017=100`, rising 109.641 → 130.658. Drawn as an
**area**, because the subject is accumulation: the mass under the line only ever
grows.

Selecting a window (1, 3, 6 or 12 months) **brackets that span on the climb** and
states three things together:

- the rate `inflation_v1.0` computed for it;
- the two index values at its endpoints, from that window's own evidence;
- one sentence tying them: *the left one is how far prices climbed, the right one
  is how steep that climb was.*

**Why this teaches what prose cannot.** Selecting "1 month" lights a sliver at
the far right of a five-year ascent and reports 2.99%. Selecting "12 months"
lights a longer span and reports 3.34%. The reader sees a *smaller rate on a
line that is still going up* — the misconception, dismantled by geometry rather
than by being told.

### 2.1 What the chart must never do

- **No rate line.** The API publishes rates for one period. A rate history drawn
  from these levels would be client-side economics (§6).
- **No overlay of two indexes.** CPI runs 273→334 and PCE 109→130. Putting them
  on one axis requires rebasing, which changes displayed values.
- **No forecast, no trend line, no extrapolation beyond the last observation.**
- **No shaded "target zone"** on the level chart. The 2% objective is a rate
  objective; painting it onto a level chart would assert a price path nobody
  published.

---

## 3. Section order

| # | Section | Job | Exists today? |
|---|---|---|---|
| 1 | **Hero** | What inflation is, in the reader's words, with the as-of month | Replaces `PageHeader` |
| 2 | **The climb** | The index, the window selector, the reading | **New** (data exists) |
| 3 | **What that actually means** | The reviewed misconception copy, in full | New placement |
| 4 | **Three published measures** | Core PCE, headline PCE, headline CPI — each with its own month | Replaces `HeadlineContext` |
| 5 | **How MacroChipz has classified it** | 12 recorded states as a strip | Compacted from 1,125px |
| 6 | **What this cannot tell you** | Limits, stated rather than buried | **New** |
| 7 | **Evidence & methodology** | Unchanged disclosure | Exists |
| 8 | **What changed / Ask / Understand / Rates / Revisions** | Unchanged, below | Exists |

The state badge ("Mixed") moves **after** the climb. A classification is a
conclusion, and a reader should meet the thing being classified first.

---

## 4. Copy rules

Every consumer sentence is reviewed explainer copy reused **verbatim**, or a
composition of backend fields. The prototype uses:

- `explain.inflation-vs-prices` — `whatItIs` as the hero standfirst, and
  `answer`, `misconception`, `whatThisMeansForYou` as §3;
- `explain.headline-vs-core` — `answer` and `whatItIs` as §4's note.

**Disinflation is never called deflation.** The limitations section states
plainly that for the index to come down the rate would have to go below zero,
"a different thing, with a different name". No sentence anywhere infers a
reader's own cost of living from a national index.

---

## 5. Interaction and accessibility

1. Window controls are HTML `<button>`s, **44 × 44 minimum**, `aria-pressed`,
   one selected at all times, focus stays on the control.
2. The reading is `aria-live="polite"`.
3. The chart is `role="img"` with a composed `aria-label` naming the series, its
   units, its observation count, its span, and the selected window's endpoints.
4. A window with no computed value renders **disabled and labelled "n/a"** — no
   figure is invented.
5. Every transition paired with `motion-reduce`.
6. DOM order equals visual order equals tab order.
7. Contrast measured on the composite, not judged by eye.

---

## 6. Data dependencies — what a richer version would need

These are **gaps, documented rather than simulated.**

| Want | Status | What it would take |
|---|---|---|
| **A rate-over-time line** (how the 12-month rate has moved) | **Not available.** `/monitors/inflation` publishes rates for one period; `/monitors/inflation/history` publishes 12 **states** and no rates. | A backend rate series, or rate fields on history entries. Deriving it client-side from the index is forbidden and is not done. |
| Category detail (groceries, rent, fuel) | **Not available.** The index is served as one number. | Component series ingestion — a data programme, not a UI change. |
| A reader's own basket | **Out of scope by policy**, not merely missing. | Nothing. The product should not estimate it. |
| Core and headline on one level chart | Possible but **rejected** | Requires rebasing, which changes displayed values. |
| Longer history | 59 observations from Sep 2021. | More ingestion; the chart scales without change. |

---

## 7. Unresolved methodology questions

1. **Should the climb use Core PCE or Headline CPI?** Core is the series
   `inflation_v1.0` leads with, and the prototype follows it. But a reader's
   lived experience includes food and energy, and the honest answer may be that
   the *headline* index is the better climb and core is the better rate.
2. **The two-month problem.** Core PCE is through July, CPI through August. The
   prototype states each measure's own month; it does not resolve whether they
   should ever appear side by side at all.
3. **Does the neutral band belong on a consumer page?** ±0.1pp around the
   12-month rate is what produces "Mixed". It is precise, and it is the least
   intuitive thing in the methodology.
4. **Index units.** "Index 2017=100" is honest and meaningless to most readers.
   Showing a rebased "what £100 of 2021 spending costs now" would be far more
   legible — and it is a client-side transformation, so it is not in the
   prototype. Worth a decision.

---

## 8. Acceptance criteria

1. Document height at 390px **below 4,500** (today 5,024).
2. **Zero** controls under 44 × 44px (today 11 mobile / 23 desktop).
3. The price level is rendered, with its units, source and observation count.
4. Selecting each of the four windows updates the bracket, the rate, and both
   endpoint index values.
5. A window without a computed rate is disabled and says so; no zero appears.
6. Loading renders skeletons and no figures.
7. Every existing calculation, provenance field, revision note and unavailable
   state still present.
8. Measured at 390, 440, 768 and 1440: no overflow, no clipping, no overlapping
   controls.

---

## 9. Prototype — measured

| | 390 | 440 | 768 | 1440 |
|---|---|---|---|---|
| Document height | **4,181** | 3,990 | 3,249 | **3,138** |
| *Current page* | *5,024* | *4,919* | *3,970* | *3,958* |
| Horizontal overflow | 0 | 0 | 0 | 0 |
| **Controls under 44px** | **0** | 0 | 0 | 0 |
| Window controls | 4 @ 129×44 | ✓ | ✓ | ✓ |
| Exactly one selected | ✓ | ✓ | ✓ | ✓ |

**Verified:** each window updates the rate and both endpoint index values
(1m 2.99% / 130.338→130.658; 3m 3.05% / 129.681→130.658; 6m 3.46% /
128.455→130.658; 12m 3.34% / 126.43→130.658); focus retained; unavailable state
disables the 1-month control and shows "n/a" with no invented figure; loading
shows three skeletons and no numbers.

### 9.1 One defect found in the prototype and fixed

The endpoint markers were SVG `<circle>`s on a board using
`preserveAspectRatio="none"`, and rendered as **wide ellipses at 1440** — the
same trap #48B documented when it drew the teaser glyph. Moved to CSS-positioned
HTML dots, which are round because their own box is square whatever the board
does. Measured 9×9 at both 390 and 1440.
