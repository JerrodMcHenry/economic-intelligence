# Inflation World — product audit

**Increment #50A.** Audit and prototype only. **No production frontend or
backend file was modified**, no dependency added, nothing committed.
**Date:** 2026-09-23
**Prototype:** `docs/product/mockups/v50a/index.html`
**Specification:** `macrochipz-inflation-world-v50a-spec.md`

---

## 0. The finding that frames everything

**`/inflation` renders 41 percentages and zero charts, and never once shows the
price level.**

`document.querySelectorAll('main svg[role="img"]').length` → **0**. The page has
20 SVG elements and every one is an icon.

Meanwhile the API's own evidence carries the level: `evidence_12m` returns
`endpoint_value_past: 126.43` and `endpoint_value_current: 130.658`. Those two
numbers appear **nowhere on the page**. A reader is shown the rate of change and
never the thing that is changing — which is precisely the mechanism by which
"inflation is falling" gets read as "prices are falling".

`inflation_v1.0` is not at fault and is not proposed for change. Every figure is
backend-computed and rendered verbatim. What is under audit is what a
non-economist sees.

---

## 1. Measured, at genuine viewports

Chrome, real CSS widths, same-origin iframe, dark theme, live local API
(`calculation_period` 2026-07-01).

| | 390 | 440 | 768 | 1440 |
|---|---|---|---|---|
| **Document height** | **5,024px** | 4,919 | 3,970 | 3,958 |
| Screens of scrolling | ~6.0 | ~5.8 | ~4.4 | ~4.4 |
| Horizontal overflow | 0 | 0 | 0 | 0 |
| Text clipped | 0 | 0 | 0 | 0 |
| **Targets under 44px** (effective hit area) | **11** | 11 | **23** | **23** |
| `<h2>` sections | 12 | 12 | 12 | 12 |
| **Charts** | **0** | 0 | 0 | 0 |

The target count **doubles on desktop** because the Intelligence History rows
are 20px `<summary>` elements that only render there.

### 1.1 Section heights at 390px

| Section | Height | Share |
|---|---|---|
| Intelligence history | **1,125px** | 22% |
| What changed | 801 | 16% |
| Core PCE momentum | 619 | 12% |
| Headline context | 386 | 8% |
| Underlying momentum | 317 | 6% |
| Target / level | 281 | 6% |
| Confirmation | 245 | 5% |
| Understand this | 184 | 4% |
| Ask MacroChipz | 113 | 2% |
| Evidence & methodology | 84 | 2% |

### 1.2 Repetition

| | Count |
|---|---|
| The word **"Mixed"** | **14** |
| The word "annualized" | 14 |
| Percentage values rendered | **41** (14 distinct) |
| `3.34` (the headline 12-month rate) | 4 |
| The price **index level** | **0** |

---

## 2. Prioritized findings

### P0 — The page never shows the price level

The single most important distinction for a consumer — *rate versus level* — is
structurally impossible to make on this page, because only one of the two is
present. The data to fix it is already in the response.

*Evidence:* `126.43` / `130.658` present in `evidence_12m`, absent from the DOM.

### P1 — The first screen is a classification, not an explanation

At 390px the first screen reads: "Inflation", "Track inflation levels,
underlying momentum, confirmation, and the evidence behind each conclusion",
"Latest revised data", "Underlying momentum", **"Mixed"**, "Core PCE · July
2026", "Latest-revised reconstruction: Mixed for 2 consecutive months", then
"3M 3.05% 6M 3.46% 12M 3.34%".

A reader who does not already know what "underlying momentum" or "core PCE"
means learns nothing, and the word "Mixed" — the least actionable thing on the
page — is its largest element.

### P2 — Zero data visualisation

No chart of any kind. The Rates world has had a hand-authored curve since #30;
Inflation has never had one, despite owning a 59-observation monthly index
series that the API already serves.

### P3 — 23 undersized targets on desktop, 11 on mobile

All are 20px `<summary>` rows (evidence disclosures, history rows) and 17px
inline links. The `Disclosure` component already carries the `summaryClassName`
opt-in added in #46C for exactly this; `/inflation` has not taken it.

### P4 — "Mixed" appears 14 times

The state is repeated in the hero badge, the duration sentence, the "what
changed" rows, and twelve history rows. It is one fact.

### P5 — Intelligence history is 22% of a phone page

1,125px for 12 recorded classifications. Valuable, and not first-screen
material.

### P6 — The two-month problem is never surfaced

Core PCE runs through **July 2026**; Headline CPI through **August 2026**. The
page prints both as current without stating that they are different months —
which is a genuine comparability trap, and the kind of thing this product
normally handles well.

### P7 — Nothing states what the data cannot tell you

There is no section saying this is a national average rather than a reader's own
cost of living. For a world whose entire subject is "why does my shopping cost
more", that absence is conspicuous.

---

## 3. What is good and must survive

1. **Every figure is backend-computed** and rendered verbatim.
2. **The neutral band is explicit** — ±0.1pp around the 12-month rate, with
   boundaries published.
3. **1/3/6-month rates are labelled "annualized" and the 12-month is not.** The
   product does not relabel one as the other.
4. **Evidence disclosures carry endpoint dates and values** for every metric.
5. **`data_basis: latest_revised_data` is stated**, and revisions are recorded
   rather than overwritten.
6. **Recorded state history with replay outcomes** — a real point-in-time
   record, and `replay.outcome: MATCH` is a genuinely rare product property.
7. **The cross-world link to Rates asserts nothing**, and says so explicitly.

---

## 4. Retain / replace / move

| Element | Decision | Why |
|---|---|---|
| `inflation_v1.0`, every rate, state, band and evidence field | **Retain, untouched** | Not in scope, not defective. |
| `PageHeader` "Inflation" + four-construct standfirst | **Replace** | A hero that defines the subject in the reader's words. |
| `InflationHero` state badge | **Retain, move** | The state is a conclusion; it belongs after the reader knows what is being classified. |
| **The price level** | **ADD** | Already in the response. Never rendered. |
| `MomentumMetrics` (3M/6M/12M strip) | **Replace** | Becomes the window selector on the chart, where each rate is tied to the span it describes. |
| `WhatChangedSection` (801px) | **Retain, move** | Period-over-period deltas are evidence, not orientation. |
| `TargetPanel` | **Retain** | The 2% objective and the gap are published facts. |
| `ConfirmationPanel` | **Retain, move** | CPI checking PCE is a methodology property; it belongs with the three-measure comparison. |
| `HeadlineContext` | **Replace** | Becomes the three published measures, each with its own as-of month — which fixes P6. |
| `IntelligenceHistorySection` (1,125px) | **Retain, move, compact** | Twelve states as a strip rather than twelve disclosure rows. |
| `MethodologyDisclosure` | **Retain** | Unchanged. |
| Evidence disclosures at 20px | **Retain, enlarge** | `summaryClassName` opt-in already exists. |
| "What this cannot tell you" | **ADD** | Does not exist. |
| `AskMacroChipz`, `UnderstandWorld`, Rates link, Revisions link | **Retain** | Unchanged. |

---

## 5. Existing vs proposed functionality

**Exists today and is rendered:** four momentum rates with evidence, the state,
state duration, the neutral band, period-over-period changes, the 2% target gap,
headline PCE and CPI 12-month rates, CPI confirmation relationship, 12 recorded
states with replay outcomes, methodology, data basis, coverage flags, and all
loading/error/unavailable states.

**Exists in the API and is NOT rendered today:**

| Data | Where it already is |
|---|---|
| **Price index levels, 59 monthly observations** | `GET /api/v1/series/PCEPILFE/observations` |
| Headline CPI index, 60 observations | `GET /api/v1/series/CPIAUCSL/observations` |
| Endpoint index values per window | `evidence_{1m,3m,6m,12m}.endpoint_value_{past,current}` |

**Proposed and genuinely new (presentation only):** the climb chart, the window
selector bound to it, the rate-versus-level reading, the three-measure
comparison with distinct as-of months, the compacted state strip, and the
limitations section.

**Nothing proposed requires a new endpoint, a new field, or a new calculation.**

---

## 6. Screenshots

Current page, genuine viewports, dark theme, live API: 390px first screen
(classification-first), 1440px first screen (a badge and three numbers in a
1,216px column).

---

## 7. Recommendation

Build the climb. It is one chart, it uses data the API already serves, and it is
the only change that makes the product objective — *why lower inflation does not
mean lower prices* — visible rather than merely stated.

**HARD STOP before implementation, per the brief.**
