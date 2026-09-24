# MacroChipz Rates World — #52B implementation

**Date:** 2026-09-24
**Scope:** a focused enhancement to the existing `/rates` page. The #49B
selectable yield curve remains the foundation; nothing about it was
redesigned.
**Audit:** `macrochipz-rates-world-v52a-audit.md`
**Spec:** `macrochipz-rates-world-v52a-spec.md`
**Constraints honoured:** no backend change, no new dependency, nothing
committed or pushed.

---

## 1. What shipped

### 1.1 The curve, then and now

`/rates` drew one curve for one date. It now draws two: the latest
published curve, and the curve on an earlier published day the reader
chooses from the four session windows `rates_v1.0` already publishes.

**No new request and no new arithmetic.** Every maturity's `changes[]`
array has carried `from_date` and `from_value` since #29, and #52A's
audit verified that the `from_date` values are identical across all four
nominal maturities for every window. Four published values sharing one
published date is a curve; the page was rendering them as sixteen
scattered basis-point figures.

| On screen | Source field |
|---|---|
| Solid curve | `nominal_curve[].latest_value` @ `latest_date` |
| Dashed curve | `nominal_curve[].changes[w].from_value` @ `from_date` |
| Table's Change column | `nominal_curve[].changes[w].change_basis_points` |
| "The 2Y moved +57 bp" | the same field |
| "it was 0.71 … and 0.58" | `curve_spreads[2s30s].changes[w].from_value` / `to_value` |
| "published as −13 bp" | `curve_spreads[2s30s].changes[w].change_basis_points` |

### 1.2 Recorded movements

`/api/v1/intelligence?world=rates` returns six `RATES_MOVEMENT` objects
and `/rates` rendered none of them. They now appear as secondary context,
filtered by `homepage_presentation_v1.0`'s existing `eligibility` and
ordered by its `comparePresentation` — the product's tested, score-free
policy rather than a second one invented here.

Each row separates **Observed** (`effective_period`) from **Recorded**
(`recorded_at`), because one is what the reading is about and the other
is when this product wrote it down. `published_at` is deliberately
absent: it is `null` on every object MacroChipz holds, and an empty
"published" field beside a date reads as a claim that the provider
published at that moment.

Each row's `limitations` are reproduced **verbatim**, including the one
that matters most: *"Carries no significance claim: rates_v1.0 defines no
notability threshold…"*

## 2. Files

| File | Change |
|---|---|
| `lib/ratesCurveComparison.ts` | **new.** Selects the past curve; checks date alignment; classifies the level shift; finds the published shape change. |
| `components/rates/CurveComparison.tsx` | **new.** Window controls, the Level/Shape reading, and the note explaining what could not be drawn. |
| `components/rates/RecordedMovements.tsx` | **new.** The intelligence section. |
| `components/rates/YieldCurveChart.tsx` | optional `comparison` prop: a second dashed curve, broken at gaps; a named control group; a three-value table with both dates. |
| `pages/Rates.tsx` | comparison state; wires the controls, reading and note; adds the third independent resource. |
| `api/intelligence.ts` | `world` filter on `listIntelligence`; `listRatesMovements`. |
| `test/fixtures/rates.ts` | `buildWindowedChanges`, and a coherent per-window nominal curve and spread. |
| `test/fixtures/intelligence.ts` | **new.** Six `RATES_MOVEMENT` objects. |
| `pages/Rates.test.tsx` | 6 existing tests updated; 15 added. |

## 3. Everything preserved

Verified present and unchanged: every derived metric with all four
change windows, historical context, evidence disclosures and provenance;
real yields as published observations in their own section, separate
from derived measures; the #49B hero and human-readable date;
`ExplanationTrigger`; per-maturity provenance; the full six-paragraph
methodology disclosure; the attribution line; the mortgage-rate
`StoryTeaser`, still immediately after the selected-maturity panel;
"Where these numbers come up"; `AskMacroChipz` outside the monitor
resource; `RevisionsLink`; `UnderstandWorld`.

**One thing was collapsed, nothing was deleted.** Six movement cards
measured 1,500px at 390px. The list now sits behind one disclosure whose
summary states the count — "Show all 6 recorded movements" — with the
heading and the explanation of what these are still visible. Every
record, every field and all three limitations per object are exactly
where they were. Progressive disclosure, as the brief permits; no
summarising.

## 4. Not added, on purpose

No historical spread chart (MacroChipz stores no spread series — four
candidate ids 404, documented in the audit as a backend dependency). No
curve-shape classification. No forecast. No claim about what a narrower
gap means for what happens next or for any rate a reader might be
offered. `rates_v1.0` defines no state label and no forecast, and the
page says so where a reader will actually meet the temptation.

## 5. Measurements — production `/rates`, real viewports

Measured in a same-origin iframe at genuine widths, with two known
measurement artifacts excluded **by name**: `.sr-only` (a 1px clipped
box positioned outside its parent) and any subtree inside a closed
`<details>` (which still reports rects for a panel that is not rendered).

| | 390 | 440 | 768 | 1024 | 1440 |
|---|---|---|---|---|---|
| Document height, before #52B | 5,646 | 5,559 | 4,059 | 4,143 | 4,175 |
| Document height, after | 6,540 | 6,373 | 4,709 | 4,725 | 4,757 |
| Horizontal overflow | 0 | 0 | 0 | 0 | 0 |
| Elements escaping their card | 0 | 0 | 0 | 0 | 0 |
| Interactive targets under 44px effective | 0 | 0 | 0 | 0 | 0 |

The +894px at 390 is +633 for the comparison controls and reading — the
increment's whole point, in the page's centre — and +261 for the
collapsed movements section.

### 5.1 Both curves distinguishable on mobile — measured at the hardest case

The 1-session window is the tightest: the two curves are 8–14px apart at
390px, closest at the 30-year. They stay separable because they differ in
**three independent ways**, not one:

- colour (brand violet vs muted grey),
- dash pattern (solid vs `6 4`),
- marker fill (filled disc vs hollow ring).

Both value labels are printed, above and below their own points, and
neither collides with the other or with the axis labels.

### 5.2 Contrast (WCAG 2.1), measured on rendered composites

Colours were resolved by **painting them to a canvas**, not by parsing
the computed string — Chrome returns `oklch()` verbatim, and a naive
`rgb()` parse silently returns nothing.

| Element | Size/weight | Ratio |
|---|---|---|
| Comparison label / table header | 12px/600 | 6.33 |
| Window date, unselected | 14px/600 | 9.68 |
| Window date, selected | 14px/600 | 10.08 |
| Table maturity / latest value | 14px | 14.66 |
| Table earlier value / change | 14px/400 | 9.68 |
| Latest curve value label | 12px | 14.66 |
| Earlier curve value label | 12px | 6.33 |
| Axis / maturity labels | 11–12px | 6.33 |
| Latest line (graphical) | — | 8.04 |
| Earlier dashed line (graphical) | — | 6.33 |

Lowest text ratio **6.33:1**; lowest graphical ratio **6.33:1**. Both
thresholds (4.5:1 text, 3:1 non-text) cleared with margin.

### 5.3 Both themes

`/rates` carries `data-surface="cinematic"`, so the page surface keeps
the dark token family in **both** themes while the chrome follows the
preference — the #48 behaviour, verified here rather than assumed. Every
ratio above is therefore identical in light and dark, and the light-theme
render was captured to confirm the surface boundary is clean.

### 5.4 Keyboard and reduced motion

Nine focusable controls in the curve card (5 window buttons + 4
maturities), all in document order. Verified with a **real keyboard Tab**
— a scripted `.focus()` does not reliably match `:focus-visible`, and
reported no ring until the key event was genuine. With it:
`outline: 2px solid` at `2px` offset.

Motion: the only transition #52B adds is `transition-colors` on the
window buttons, carrying `motion-reduce:transition-none`. The rule
`@media (prefers-reduced-motion: reduce) { .motion-reduce\:transition-none { transition-property: none } }`
was confirmed present in the served stylesheet **and** confirmed to match
the button. The chart redraw itself is an instantaneous DOM replacement —
there is nothing in the central visual for reduced motion to suppress.

## 6. Failure isolation — verified in the running browser

`window.fetch` was patched at runtime inside the real production
frontend and the page re-entered by client-side navigation. **No
application code was modified for these tests.**

| Scenario | Result |
|---|---|
| Intelligence endpoint 503 | Curve, 4-row table and both reading clauses fully intact. Movements show their own alert and Retry. |
| Rates monitor 503 | Monitor's own alert and Retry. **All six movement cards still render.** No fabricated zeros anywhere on the page. |
| Both hang | Two independent `role="status"` regions; no number rendered. |
| Retry after healing | Movements recover to six cards; the alert clears. |

Unit-tested in addition: a missing past reading (the dashed line breaks,
the isolated point keeps its published marker and value, and the gap is
named with its maturity and date); and misaligned `from_date`s across
maturities (no curve is drawn at all, the distinct dates are listed, and
the reading is withheld).

## 7. The guard held, and pointed at the answer

`src/test/no-rates-calculation.test.ts` forbids subtracting one
rate-shaped value from another. The "is the gap wider or narrower?"
sentence looked like it needed exactly that — until the 2s30s spread
turned out to publish its own `from_value` and `to_value` for the same
four windows. **Nothing in #52B subtracts one yield from another.** The
guard was not weakened, extended or routed around.

## 8. Known and carried forward

- **The desktop chart keeps its #49B geometry** (760×260 viewBox,
  `xMidYMid meet`, rendering ~2.92:1 at 1440). #52A's prototype proposed
  a two-column desktop card at ~2:1. That is a layout redesign, and this
  brief is explicit that #49B's chart remains the foundation — so it is
  recorded here as an open option rather than taken.
- **No recorded-result history for Rates.** `/monitors/rates/history`
  returns 422; `IntelligenceHistorySection` consumes a different
  contract and is not reusable. Backend dependency.
- **No spread history series.** Backend dependency.
- **The "cost to borrow" copy inconsistency** in the explainer registry
  and the homepage world line is still open, still owned by those
  surfaces, and still not patched from this page.
