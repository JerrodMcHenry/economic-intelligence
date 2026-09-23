# Rates World — product and visual audit

**Increment #49A.** Audit and prototype only. **No production frontend file was
modified**, no dependency added, nothing committed.
**Date:** 2026-09-23
**Audited:** `/rates` against the approved Living Economy homepage (#48) and the
interactive mortgage-rate story (#46E).
**Prototype:** `docs/product/mockups/v49a/index.html`
**Specification:** `docs/product/macrochipz-rates-world-v49a-spec.md`

---

## 0. What is being judged, and what is not

`rates_v1.0` is **not** under audit and is not proposed for change. Every number
on `/rates` is computed by the backend and rendered verbatim;
`src/test/no-rates-calculation.test.ts` enforces that boundary automatically.
The methodology, the provenance split between published and derived values, the
session-window semantics, the unavailable states and the failure isolation are
all correct, and every one of them is in the **retain** column below.

What is under audit is the *experience*: what a person who is not a bond analyst
sees, in what order, and at what cost.

---

## 1. Measured, at genuine viewports

Rendered in Chrome at real CSS widths via a same-origin iframe, dark theme,
against the live local API (`as_of_date` 2026-09-18).

| | 390 | 440 | 768 | 1440 |
|---|---|---|---|---|
| **Document height** | **6,777px** | 6,566 | 5,076 | 4,334 |
| Screens of scrolling (at that viewport height) | **~8.0** | ~7.8 | ~5.6 | ~4.8 |
| Horizontal overflow | 0 | 0 | 0 | 0 |
| Text clipped | 0 | 0 | 0 | 0 |
| **Interactive targets under 44px** | **38** | **38** | **38** | **38** |
| `<h2>` sections | 11 | 11 | 11 | 11 |

### 1.1 Section heights at 390px

| Section | Height | Share |
|---|---|---|
| Treasury curve | **1,598px** | 24% |
| Market-implied inflation compensation | 1,255 | 19% |
| Treasury yields | 1,221 | 18% |
| Real yields | 717 | 11% |
| What changed | 559 | 8% |
| Where these numbers come up | 249 | 4% |
| Understand this | 183 | 3% |
| When a number changes | 161 | 2% |
| Evidence & methodology | 84 | 1% |
| Ask MacroChipz | 48 | 1% |

**The curve section is 1,598px and the chart inside it is 201px.** The other
1,397px are a four-row table repeating the chart's own values and two spread
cards.

### 1.2 The 38 undersized targets, by kind

| Control | Size | Count |
|---|---|---|
| **`ExplanationTrigger` "i"** | **16 × 16px** | **19** |
| `Source & provenance` disclosure | 301 × 20px | 6 |
| `How this is calculated` disclosure | 301 × 20px | 4 |
| Explainer / cross-world links | ~17–20px tall | 8 |
| `Where these numbers come from` | 343 × 20px | 1 |

16px is **36% of the 44px minimum**, and there are nineteen of them. This is the
single most serious defect on the page and it is identical at every width.

---

## 2. Prioritized findings

### P0 — 19 touch targets at 16 × 16px

`ExplanationTrigger` renders a 16px `<summary>`. It is the control that opens
every definition on the page — the one thing a non-expert reader most needs —
and it is the hardest thing on the page to hit. WCAG 2.5.8 asks for 24px
minimum; the product's own #46E work settled on 44px.

*Evidence:* measured at all four widths, count 19, size 16 × 16.

### P1 — The page opens with no orientation a consumer can use

The first 390px screen contains: the word "Rates", a sentence naming four
technical constructs ("curve structure, real yields, and market-implied
inflation compensation"), a date, and one and a bit yield cards.

Nothing on that screen answers *why does this number matter to me*. The
homepage's own discovery line for this world already does —
*"Treasury yields are what it costs the government to borrow — and the
reference other borrowing is priced against."* — and it is not on this page.

### P2 — The interactive story is unreachable from the world it is about

`grep` across `pages/Rates.tsx` and `components/rates/`: **zero** references to
`/story/fed-and-mortgage-rates`. The story explains the relationship between
Treasury yields and the rate a reader is actually quoted. A reader who arrives
at `/rates` having tapped "Open Rates" on the homepage cannot reach it.

`UnderstandWorld` does link the *explainer text page*, as its 9th–11th section.

### P3 — The same four numbers are rendered up to six times

`4.76` appears **6 times** in the rendered text of one page, `5.01` likewise:
the yield card, the curve chart's plotted label, the curve chart's data table,
the "What changed" row's from→to, and the spread cards' working
("5.01% (10Y) − 4.76% (2Y)").

Each instance is individually defensible. Together they are why the page is
6,777px.

### P4 — The visual language is not the approved one

`/rates` is flat near-black `bg-surface` cards on `--mc-canvas`. The approved
direction is charcoal and midnight with luminous violet, glass cards and a lit
hero. Apart from the shared header, a reader moving from the homepage to
`/rates` arrives somewhere that looks like a different product.

### P5 — The curve is a picture, not an instrument

The chart is `role="img"` with **no pointer handlers, no `tabindex`, no
selection state**. A reader cannot ask "what is the 10-year?" by touching the
10-year. The maturity cards above and the curve below are the same four facts
with no connection between them.

This is the largest *unrealised* opportunity on the page, and the one the
approved homepage and story have already solved elsewhere: select a thing,
everything else responds.

### P6 — Raw metric identifiers as consumer labels

`2s10s`, `2s30s`, `5Y compensation`, `10Y compensation` are rendered as row
labels and card titles. `2s10s` has a subtitle ("10-Year minus 2-Year"); the
"What changed" table has none.

### P7 — Repeated date furniture

"Sep 18, 2026" appears **5 times on the first desktop screen** — once in the
header as "Latest available", then once per yield card — and once more per row
of the curve table. The 10-row "What changed" table prints
"(Sep 11, 2026 – Sep 18, 2026)" identically on every row.

### P8 — Nine of the eleven `<h2>`s are equal weight

Every section heading is `text-sm font-medium text-fg-muted`. "Treasury yields"
and "Ask MacroChipz" have the same visual rank, so the page reads as a list of
equally important panels rather than as an argument with a beginning.

---

## 3. What is genuinely good, and must survive

1. **The curve chart itself.** Hand-authored SVG, per-breakpoint viewBox,
   `xMidYMid meet`, a real `<table>` beside it, gaps left as gaps. ADR-041's
   correction held.
2. **The two provenance shapes are never unified.** A published observation and
   a derived value render through different components with different fields.
   That is the product's core claim, expressed in code.
3. **Unavailable is a first-class state.** "Not available", "Not enough
   history", and a named `UnavailableReason` — never a fabricated `0.00%`.
4. **Direction never depends on colour.** Sign, glyph and a visually hidden word.
5. **The session-window vocabulary.** "21 sessions", never "1 month".
6. **`HistoricalContextNote` separates signed rank from magnitude rank** and
   refuses to merge them into an "unusualness" score.
7. **Failure isolation.** The Analyst panel sits outside `RatesContent`.

---

## 4. Retain / replace / move

| Element | Decision | Why |
|---|---|---|
| `rates_v1.0`, every figure, every provenance field | **Retain, untouched** | Not in scope and not defective. |
| `YieldCurveChart` geometry, viewBox strategy, `<table>` | **Retain** | Correct. Gains selection; loses nothing. |
| `RateChangeList` semantics (4 windows, glyph + sign + sr word) | **Retain** | Move into a disclosure per card, not onto the face. |
| `SourceProvenanceDisclosure` / `DerivedProvenanceDisclosure` | **Retain, enlarge the trigger** | Content correct, target 20px. |
| `HistoricalContextNote` | **Retain, move** | Currently `showContext={false}` on this page — it is fetched and never shown. Give it a home. |
| `ExplanationTrigger` at 16px | **Replace** | 44px target. Same content, same `<details>`. |
| `PageHeader` "Rates" + technical standfirst | **Replace** | A consumer-facing hero carrying the registry's own discovery line. |
| Curve chart's 4-row duplicate table | **Move** | Keep as the accessible equivalent; do not print it twice visually. |
| "What changed" 10-row table | **Replace** | Becomes the selected maturity's own change strip plus a compact all-metric view. |
| `2s10s` / `2s30s` as labels | **Replace** | Lead with "10-year minus 2-year"; keep `2s10s` as the secondary id. |
| Per-card date stamps | **Move** | One as-of statement for the page; per-card only where a series differs. |
| "Where these numbers come up" | **Retain, move** | Links, not conclusions. Belongs with the story link. |
| `UnderstandWorld` | **Retain, move up** | 9th of 11 sections today. |
| `AskMacroChipz` | **Retain, unchanged** | Outside the content, correctly. |
| `RevisionsLink context="Treasury"` | **Retain** | Unchanged. |
| Story link | **ADD** | Does not exist today. |

---

## 5. Current functionality vs proposed

**Everything below exists today** and is rendered from the API: four nominal
yields, two real yields, 2s10s and 2s30s spreads, 5Y and 10Y inflation
compensation, four session-window changes per metric, historical percentile
context per metric, full source and derived provenance, methodology id, data
basis, provider, as-of date, attribution, and the no-data state.

**Proposed and NOT currently implemented:**

| Proposed | Status |
|---|---|
| Selecting a maturity on the curve | **New interaction.** No new data — it selects among figures already fetched. |
| Consumer hero with the registry discovery line | **New presentation.** Copy already reviewed on the homepage. |
| Link to `/story/fed-and-mortgage-rates` | **New link.** Route exists. |
| Charcoal/midnight/violet surface | **New presentation.** Tokens exist (`[data-surface="cinematic"]`). |
| Historical context shown on this page | **Existing data, currently hidden** (`showContext={false}`). |

**Nothing proposed requires a new endpoint, a new field, or a new calculation.**
No figure in the prototype is invented; every one comes from the captured
snapshot in `mockups/v49a/rates-snapshot.json`, which records the endpoint, the
capture time and the attribution.

---

## 6. Screenshots

Captured at genuine CSS viewports, dark theme, live API.

- 390px — first screen: the page opens on a technical standfirst and one card
- 390px — curve section: chart, then the same four values again as a table
- 768px — "What changed": ten rows, raw metric ids, the same date pair on each
- 1440px — first screen: four competent cards; five instances of "Sep 18, 2026"

---

## 7. Recommendation

Proceed to a prototype of **one** thing: the curve as a selectable instrument,
on the approved surface, with a consumer hero and the story link — the layout
in §3 of the specification. Everything else on this page is a spacing and
target-size problem, which is cheap; the curve is the only part that needs a
design decision.

**HARD STOP before implementation, per the brief.**
