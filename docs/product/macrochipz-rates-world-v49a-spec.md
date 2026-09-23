# Rates World — experience and interaction specification

**Increment #49A.** Specification for review. Not implemented.
**Date:** 2026-09-23
**Audit:** `docs/product/macrochipz-rates-world-v49a-audit.md`
**Prototype:** `docs/product/mockups/v49a/index.html`

---

## 1. The job

One sentence: **a person who has heard that "rates are up" should learn, within
one screen, what the U.S. government pays to borrow, that nobody sets it, and
that it is the reference their own borrowing is priced against — and be one tap
from the story that explains the rest.**

It stays an intelligence product. The figure comes first; education sits beneath
it as an offer, never in front of it (#44's rule, unchanged).

### 1.1 Who arrives

1. **From the homepage**, having tapped "Open Rates" under the discovery line
   *"Treasury yields are what it costs the government to borrow — and the
   reference other borrowing is priced against."* They expect that sentence to
   continue. Today the page restates its own title instead.
2. **From a search for "10 year treasury"**, wanting the number.
3. **An analyst**, wanting spreads, compensation, windows and provenance. They
   are served last in layout order and losslessly.

---

## 2. Section order

| # | Section | Job | Present today? |
|---|---|---|---|
| 1 | **Hero** | The world, in the reader's words, with the as-of date once | Replaces `PageHeader` |
| 2 | **The curve** | Four maturities as one selectable instrument | Chart exists; selection is new |
| 3 | **Selected maturity** | Level, what it is, its four windows, its history rank, its provenance | All exists; regrouped |
| 4 | **Derived from the curve** | 2s10s, 2s30s, 5Y and 10Y compensation, each with its calculation | Exists |
| 5 | **The story** | The one interactive thing, linked by name | **New link** |
| 6 | **Understand this** | Existing explainers | Exists, moves up |
| 7 | **Where these numbers come up** | Housing, Inflation — links, not conclusions | Exists |
| 8 | **Evidence & methodology** | Unchanged disclosure | Exists |
| 9 | **Ask MacroChipz** / **When a number changes** | Unchanged | Exists |

Order is deliberate: **§2 and §3 are the page.** §4 onward is depth for someone
who wants it, and a reader who stops after §3 has been told the truth.

---

## 3. The curve as an instrument

### 3.1 What it is

The existing `YieldCurveChart` geometry, on the cinematic surface, with each
plotted maturity gaining a **selectable control**. Selecting one:

- lights that point and dims the other three to a **floor, never to invisible**
  (the `--lx-edge-dim` rule from #46E: a dimmed thing stays legible);
- updates the panel beneath with that maturity's level, title, four session
  windows, historical context and provenance;
- states, in the reader's words, what that maturity *is*.

Selection is not navigation. Focus stays on the control; the panel is
`aria-live="polite"`.

### 3.2 Visuals are SVG. Interaction is HTML.

The rule #46E arrived at the hard way, and it applies unchanged. The curve, its
gridlines and its line are SVG. The four selectable controls are HTML
`<button>`s positioned at percentage coordinates over it, so their hit area is
**44 × 44 CSS px regardless of the viewBox**. #46D shipped 48-unit SVG targets
that rendered at 41px; that is the defect this rule exists to prevent.

### 3.3 One selected at all times

Default **10Y**: it is the maturity the product's own explainer singles out
(*"Why does everyone watch the 10-year Treasury?"*) and the one the homepage
lede promotes. Never zero selected.

### 3.4 What the interaction must not do

- **Not a hover tooltip.** A phone has no hover.
- **Not a crosshair or a scrubber.** There are four points, not a time series.
- **No animation that carries meaning.** Every transition pairs with
  `motion-reduce`.
- **It adds no data.** Selection chooses among figures already in the single
  `/api/v1/monitors/rates` response. No new request, no new field, no
  interpolation between maturities — the space between 2Y and 10Y is a drawn
  line, and the product does not claim a value lives there.

---

## 4. Copy rules

1. Every consumer sentence is either **reviewed copy reused verbatim** (the
   registry discovery line, the explainer questions, `NETWORK_STANDFIRST`) or a
   **composition of backend fields** (e.g. "10-year minus 2-year" from
   `DerivedProvenance.calculation`). Nothing new is written about the economy.
2. `2s10s` leads with its calculation and keeps its id as secondary. Same for
   `2s30s` and for compensation.
3. Session-window vocabulary is verbatim: "21 sessions", never "1 month".
4. The as-of date is stated **once** in the hero, and again only where a series'
   own date differs from it.
5. No figure appears without a source and a date reachable from it.

---

## 5. Unavailable states

Unchanged in substance, restated because the prototype must render them:

| Case | Behaviour |
|---|---|
| `as_of_date === null` | The existing "No rates data yet" panel. Nothing estimated. |
| A maturity `available === false` | Its control is **present, labelled, disabled and explained** — never hidden, never `0.00%`. The curve omits it from the line, leaving a visible gap. |
| A derived value unavailable | Its `UnavailableReason` rendered in words. |
| `historical_context.available === false` | "Historical context needs more history than is currently stored for this metric." |
| The monitor request fails | The existing `ErrorMessage` with retry. The hero still renders — it needs no data. |

---

## 6. Accessibility acceptance criteria

1. **Every interactive control ≥ 44 × 44 CSS px**, including every explanation
   trigger and every disclosure summary. Today 38 fail; the target is zero.
2. The curve keeps `role="img"` with its composed `aria-label`, and keeps the
   `<table>` as its equally authoritative equivalent.
3. Selection uses `aria-pressed`; the panel is `aria-live="polite"` and does not
   steal focus.
4. DOM order equals visual order equals tab order.
5. Meaning never carried by colour alone — the existing sign + glyph + hidden
   word pattern is retained.
6. Text ≥ 4.5:1 and meaningful graphics ≥ 3:1, **measured on the composite**,
   not judged by eye.
7. Every transition paired with `motion-reduce`; the surface carries no ambient
   motion.

---

## 7. Responsive

| Width | Curve | Panel | Derived |
|---|---|---|---|
| ≥ 1024 | Full width, four controls | Beside the curve | 2 × 2 |
| 768 | Full width | Below | 2 × 2 |
| 390–440 | Full width, taller viewBox | Below | 1 column |

- Mobile first. The curve and its panel must both be reachable without passing
  a screen of anything else.
- Controls stay ≥ 44px at 320px, which is an **arithmetic constraint on
  spacing**, derived the way #46E derived its breakpoint — not a guess.
- Zero horizontal overflow, measured on rendered bounds.

---

## 8. Acceptance criteria

1. Document height at 390px **below 3,500px** (today 6,777).
2. **Zero** controls under 44 × 44px (today 38).
3. Selecting each of the four maturities updates the panel and states that
   maturity's own level, windows, context and provenance.
4. A link to `/story/fed-and-mortgage-rates` exists and is reachable within the
   first two screens at 390px.
5. No figure rendered without its as-of date reachable, and no invented figure.
6. The curve draws no point for an unavailable maturity, and its control says so.
7. Every existing methodology, provenance, limitation and failure state still
   present.
8. Measured at 390, 440, 768, 1024 and 1440: no overflow, no clipping, no
   overlapping controls.

---

## 9. Explicitly out of scope

Production implementation, any backend change, a new endpoint, historical
time-series charting of a single maturity, forecasts, a curve "shape" label
(inverted/flat/steep — `rates_v1.0` defines no state and this increment does not
add one), cross-domain conclusions, and any change to `/inflation`, `/jobs`,
`/housing` or the homepage.

---

## 10. Open questions for review

1. **Does the curve need a shape word at all?** A reader who sees the line rise
   will ask "is that normal?". The honest answer today is the historical
   percentile per maturity, which is not the same question. Answering the real
   one requires a methodology decision, not a design one.
2. **Real yields and compensation: fold in, or keep as their own sections?**
   The prototype folds them into §4 as derived values, which is what they are.
   An analyst may reasonably want them at the same rank as nominal yields.
3. **Default maturity.** 10Y is proposed. 30Y is what a mortgage reader is
   closest to, and the story argues lenders price against long-term conditions.

---

## 11. Prototype — measured results

`docs/product/mockups/v49a/index.html`, rendered at genuine CSS viewports
against the captured snapshot.

| | 390 | 440 | 768 | 1024 | 1440 |
|---|---|---|---|---|---|
| Document height | **3,497** | 3,415 | 2,742 | 2,737 | 2,737 |
| *Current `/rates` for comparison* | *6,777* | *6,566* | *5,076* | — | *4,334* |
| Horizontal overflow | 0 | 0 | 0 | 0 | 0 |
| **Controls under 44px** | **0** | **0** | **0** | **0** | **0** |
| *Current `/rates`* | *38* | *38* | *38* | — | *38* |
| Maturity controls | 4 @ 44×44 | 4 @ 44×44 | 4 @ 44×44 | 4 @ 44×44 | 4 @ 44×44 |
| Control overlaps | 0 | 0 | 0 | 0 | 0 |
| Label overlaps | 0 | 0 | 0 | 0 | 0 |
| Exactly one selected | yes | yes | yes | yes | yes |

**Mobile page height falls 48%** (6,777 → 3,497), and 122px of what remains is
the prototype's own review-only control block, which production would not
carry — so the comparable figure is ~3,375.

Acceptance criterion §8.1 asked for under 3,500 at 390px. Measured 3,497 with
the review block included; it passes, but only just, and it passes because the
block is counted.

**Interaction, verified:** selecting each of the four maturities updates the
panel to that maturity's own level, title, observation date, plain-English
identity, four session windows and provenance; exactly one is selected at all
times; focus lands on the newly selected control after both pointer and
keyboard activation; the panel is `aria-live="polite"`.

**Unavailable state, verified:** with the 30-year reporting as not ingested, its
control stays present and labelled ("30Y, not yet ingested"), renders as a
dashed empty ring, the axis still names it, the line stops at the 10-year
leaving a visible gap, and the composed `aria-label` says "30Y not yet
ingested". No zero is fabricated anywhere.

### 11.1 Two defects found in the prototype itself, and fixed

1. **Board height was set from `matchMedia` in JS** and came out 240px at a
   1440px viewport — the first render read the query before the frame had its
   final width and nothing re-ran. Moved into CSS. This is the same lesson
   ADR-041 recorded when it replaced measurement with a CSS-swapped viewBox: a
   breakpoint the browser owns cannot go stale.
2. **Prototype nav wrapped to two lines at 390px.** Chrome only, hidden below
   720px in the prototype; the real shell already collapses it behind a Menu
   button.

### 11.2 Implementation note for whoever builds this

The prototype rebuilds the whole control layer on every selection and then
re-focuses the newly created button. That works, and it is fragile. A React
implementation should update `aria-pressed` and class names on persistent
elements so the focused node is never destroyed — which is what
`LivingEconomyHero` already does.
