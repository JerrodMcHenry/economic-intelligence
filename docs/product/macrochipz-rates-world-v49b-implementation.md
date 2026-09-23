# Rates World #49B — implementation notes and deviations

**Increment #49B.** The #49A prototype, in production.
**Date:** 2026-09-23
**Audit:** `macrochipz-rates-world-v49a-audit.md`
**Specification:** `macrochipz-rates-world-v49a-spec.md`
**Prototype:** `docs/product/mockups/v49a/index.html`

Preserved untouched: `rates_v1.0`, every figure, the published-versus-derived
provenance split, every unavailable state, the deterministic rendering
boundary (`src/test/no-rates-calculation.test.ts`), and failure isolation.
No dependency added. No backend change.

---

## 1. What shipped, against the six required refinements

### 1.1 The four maturity points are interactive

`YieldCurveChart` gained `selectedId` and `onSelect`. **Visuals are SVG;
interaction is HTML** — the four controls are `<button>`s over the plot, 44 × 44
CSS px, measured at every width. Selection adds no data: it chooses among values
the single rates request already returned.

**One control per maturity, not one per breakpoint.** The chart renders two
plots (760 × 260 and 360 × 240) against the same absolute padding, so 52px of
left padding is 6.8% of one box and 14.4% of the other — a layer computed from
either alone is visibly wrong on the other. Each control carries both coordinate
pairs as custom properties and `.rx-point` in `globals.css` picks the pair at the
same 640px boundary the plots swap at. One element, one tab stop, one accessible
name, and the breakpoint stays the browser's to evaluate.

No misrepresentation: an unavailable maturity keeps a labelled, disabled control
drawn as a dashed outline, is omitted from the line, and no zero is invented.

### 1.2 The story sits between the panel and the calculated measures

`StoryTeaser` gained `alwaysVisible`. On the homepage it is still `lg:hidden`
because `FeaturedStory` takes over there; `/rates` has no such section, and the
story is about the world the reader is standing in. Verified by DOM position:
after the panel, before "Calculated from the curve".

### 1.3 Human-readable source and date

`TREASURY · rates_v1.0 · latest_published_data` — three machine identifiers in
the page's most prominent metadata slot — became "Latest published: Sep 18,
2026" and "Published by the U.S. Department of the Treasury". **All three
identifiers are still published verbatim** in the methodology disclosure, which
is where an identifier belongs.

### 1.4 The copy is precise, and it is not new

The hero standfirst is **verbatim** from `explain.what-is-a-treasury-yield`:
*"The yield is the annual return an investor earns by holding one. Investors buy
and sell Treasuries continuously, and the yield moves with what they are willing
to accept."* A market yield on a security — not the government's exact cost of
any new borrowing. Each maturity's plain-English line is built from the same
sentence, and the 10-year's extra clause is a contiguous substring of
`explain.why-the-10-year-matters`.

**Known inconsistency, deliberately not fixed here — see §4.**

### 1.5 10Y default, nominal primary, no shape classification

Default 10Y, falling back to the first ingested maturity if the 10-year is
absent — so the panel never opens empty. Nominal yields are the curve and the
panel; real yields keep their own section because they are **published
observations, not calculations**; spreads and compensation are secondary under
"Calculated from the curve". No inverted/flat/steep label anywhere:
`rates_v1.0` defines no curve state and this increment did not add one.

### 1.6 The explanation trigger

The icon stays 16px; the **target is a transparent 44px `::before`**, centred.
Padding would have taken 44px of layout in forty-one places and pushed every
heading it sits beside out of line; a pseudo-element occupies no space, so
nothing moved on any page.

Verified by **hit-testing rather than by measuring boxes**: a
`getBoundingClientRect` on the summary cannot see a pseudo-element, so the fix
was confirmed with `elementFromPoint` at ±19px in four directions from each
icon's centre. Every on-screen trigger responds.

---

## 2. Deviations from the prototype

| | Prototype | Shipped | Why |
|---|---|---|---|
| Real yields | Absent | Own section, retained | They are published observations. Dropping them would have lost data the page carries today. |
| Historical context on derived cards | Absent | Behind a disclosure | Four derived cards render at once; two paragraphs of rank prose each made that section 2,334px of a 5,863px phone page. The data is unchanged and one tap away. The **selected maturity's** context stays open, because only one of those is on screen. |
| "What changed" table | Absent | Removed | It duplicated a change every card already carried, with the same date pair on all ten rows. Every metric still publishes all four session windows on its own card. |
| Ask MacroChipz / Revisions / Understand | Absent | Retained | Out of the prototype's scope, not out of the product's. |
| Page height at 390px | 3,497 | 5,646 | The four sections above are the difference. Against the **current page's 6,777**, this is −17%. |

### 2.1 An implementation note the prototype earned

#49A's spec warned that the prototype rebuilt its control layer on every
selection and re-focused the new button — working but fragile. React updates
attributes on persistent elements instead, and this was verified rather than
assumed: the control's **DOM node identity survives a selection**, so focus is
never destroyed.

---

## 3. Measured

Genuine CSS viewports, dark theme, live local API.

| | 390 | 440 | 768 | 1024 | 1440 |
|---|---|---|---|---|---|
| Document height | **5,646** | 5,559 | 4,059 | 4,143 | 4,175 |
| *Before #49B* | *6,777* | *6,566* | *5,076* | — | *4,334* |
| Horizontal overflow | 0 | 0 | 0 | 0 | 0 |
| **Controls under 44px** | **0** | **0** | **0** | **0** | **0** |
| *Before #49B* | *38* | *38* | *38* | — | *38* |
| Maturity controls | 4 @ 44×44 | ✓ | ✓ | ✓ | ✓ |
| Exactly one selected | ✓ | ✓ | ✓ | ✓ | ✓ |

Reaching zero needed three shared components, not one: `ExplanationTrigger`
(19 instances at 16px), the `Disclosure` summaries via the `summaryClassName`
opt-in #46C had already built for this, and the inline links in
`UnderstandLinks`, `RevisionsLink` and the provenance source URL. The last group
is **beyond the brief's stated scope** — it named only `ExplanationTrigger` —
and was fixed because reporting "targets compliant" with six known-undersized
links on the page would not have been true. Those components render on
`/inflation`, `/jobs`, `/housing` and `/`; all four were re-measured and show
zero overflow and slightly fewer undersized targets than before.

**Interaction:** each of the four maturities updates the panel to its own level,
title, observation date, plain identity, four windows, historical context and
provenance; one selected always; focus retained after pointer and keyboard
activation; panel is `aria-live="polite"`; all four animated controls carry
`motion-reduce`.

**Themes:** identical in light and dark — a `[data-surface]` page carries the
dark palette regardless of theme (#48). Lowest measured contrast 6.72:1.

**Unavailable maturity:** covered by test rather than by browser, because the
local API has all four ingested. `Rates.test.tsx` asserts the control stays
present, labelled "30Y, not yet ingested", disabled, and that no `0.00%` appears
anywhere on the page.

### 3.1 One defect found by looking, and one false alarm

- **The selected ring covered its own value label.** The 32px ring sits on the
  point; the SVG label sat 12 viewBox units above it, ~11px at mobile scale.
  Offset increased to 22 units, verified by intersecting the label's rendered
  box with the ring's.
- **A `span` reported a box past the viewport at 390px.** Inside a *closed*
  `<details>`, the same artifact #48B documented. Not a defect.

---

## 4. The copy inconsistency this increment did not fix

`/rates` now says a Treasury yield is the return an investor earns. Two places
still use the looser framing:

1. `explain.what-is-a-treasury-yield`'s own `answer`: *"It is what it costs the
   U.S. government to borrow money for a set length of time…"*
2. The homepage's world discovery line: *"Treasury yields are what it costs the
   government to borrow…"*

Both are **reviewed copy owned by the explainer registry and the homepage**.
Rewriting them from a Rates increment would be the wrong place and the wrong
review. Recommended as a small copy-review increment of its own.

---

## 5. Files changed

**New:** `components/rates/SelectedMaturityPanel.tsx`, `lib/cssUnits.ts`.

**Modified:** `components/rates/YieldCurveChart.tsx`,
`components/rates/DerivedMetricCard.tsx`, `components/rates/RateProvenance.tsx`,
`components/explanations/ExplanationTrigger.tsx` (+ test),
`components/explainers/UnderstandLinks.tsx`,
`components/revisions/RevisionsLink.tsx`,
`components/homepage/StoryTeaser.tsx`, `pages/Rates.tsx` (+ test),
`layouts/pageSurface.ts` (+ test), `styles/globals.css`, `App.test.tsx`.

**Not touched:** every `api/`, `rates_v1.0` behaviour, `lib/ratesFormat.ts`,
`HistoricalContextNote`, `RateChangeList`, `RateLevelCard`.

### 5.1 The guard that nearly got weakened

`no-rates-calculation.test.ts` scans rates UI files for `* 100`, because there
that is the shape of a percentage-point to basis-point conversion. The control
layer needs to turn a 0..1 position into a CSS percentage — the same two
characters, an entirely different act.

The guard was **not** loosened. The conversion moved to `lib/cssUnits.ts`,
outside the economics boundary, doing something no reader could mistake for a
rate calculation.
