# Inflation World #50B — implementation notes and deviations

**Increment #50B.** The #50A prototype, in production.
**Date:** 2026-09-23
**Audit:** `macrochipz-inflation-world-v50a-audit.md`
**Specification:** `macrochipz-inflation-world-v50a-spec.md`

Preserved untouched: `inflation_v1.0`, every rate, state, neutral band, evidence
field, target gap, confirmation relationship, revision handling, `data_basis`,
coverage flags and every unavailable state. No dependency added. No backend
change. **No canonical rate is computed in the frontend.**

---

## 1. What shipped

### 1.1 The climb

`components/inflation/PriceClimb.tsx` draws the **Core PCE price index** —
59 real monthly observations from `GET /api/v1/series/PCEPILFE/observations`, an
endpoint that already existed. Area fill, because the subject is accumulation.

Selecting a window brackets that span and reports, together, the rate
`inflation_v1.0` computed and the **two real index endpoints from that window's
own evidence**. Default 12 months, falling back to whichever window is computed
so the reading never opens empty.

Measured in the browser: 1m 2.99% / 130.338→130.658 · 3m 3.05% / 129.681→130.658
· 6m 3.46% / 128.455→130.658 · 12m 3.34% / 126.43→130.658.

### 1.2 Window controls, 2×2 on a phone

`grid-cols-2` below `sm`, flex row above. Measured: **two rows at 390 and 440**,
one row from 768, every control 44px tall, `aria-pressed`, one selected always,
focus retained, disabled state for a window with no computed rate.

### 1.3 One explanation, not three

The prototype explained the movement twice under the chart. Production states the
rate, the two endpoints, and **one** sentence — *"That rise is what the rate
describes."* Headline-versus-core is left to the following section, which is
`HeadlineContext`, retained with each measure's own observation month.

### 1.4 Plain-language provenance in the hero

"Core prices through July 2026" and "Published by the U.S. Bureau of Economic
Analysis, via FRED". `PCEPILFE`, `inflation_v1.0`, `Index 2017=100` and the rest
stay in `MethodologyDisclosure` and the evidence disclosures.

### 1.5 Progressive disclosure instead of a second long page

| Behind a disclosure | Was |
|---|---|
| `MomentumMetrics` + `TargetPanel` + `ConfirmationPanel` | Three full-width sections |
| `IntelligenceHistorySection` | 1,060px, 22% of a phone page |

Nothing was removed or summarised. `WhatChangedSection` stays visible — it is
period-over-period evidence a reader might act on.

### 1.6 What this cannot tell you

New section: national index ≠ personal cost of living, no category detail, a
falling rate is not a falling level (**disinflation is not deflation**), and
core and headline are published for different months.

---

## 2. Deviations from the prototype

| | Prototype | Shipped | Why |
|---|---|---|---|
| Three-measure comparison | Bespoke 3-card grid | `HeadlineContext`, retained | It already shows both headline measures with their own periods, states and evidence. Rebuilding it would have lost the evidence disclosures. |
| State strip | 12 coloured bars | `IntelligenceHistorySection`, collapsed | The real component carries replay outcomes, which the strip dropped. |
| Second explanation under the chart | Present | Removed | Brief §2. |
| Axis labels | "Sep 2021" | "September 2021", anchored to the card edges | `formatPeriod` is the shared formatter. Centring the long name put it 8px outside the card — see §4. |
| Illustration ("6% to 3%") | Always shown | Only once data has arrived | See §3. |

---

## 3. The illustration, and the guard that caught it

The reviewed explainer's *"an inflation rate dropping from 6% to 3%"* is an
example, not an observation, and it is labelled **"For example, not a current
reading"**.

That label was not enough. This page's own loading test forbids **any**
percentage before data arrives, and it failed — correctly. On an otherwise empty
Inflation page, "6% to 3%" reads as a reading whatever the sentence beside it
says. The illustration now renders only on `monitor.status === "success"`; the
two reviewed sentences carry the lesson while it loads.

---

## 4. Measured

Genuine CSS viewports, dark theme, live local API.

| | 390 | 440 | 768 | 1024 | 1440 |
|---|---|---|---|---|---|
| Document height | **4,672** | 4,487 | 4,001 | 4,003 | 4,045 |
| *Before #50B* | *5,024* | *4,919* | *3,970* | — | *3,958* |
| Horizontal overflow | 0 | 0 | 0 | 0 | 0 |
| **Controls under 44px** | **0** | **0** | **0** | **0** | **0** |
| *Before #50B* | *11* | *11* | *23* | — | *23* |
| Charts | **1** | 1 | 1 | 1 | 1 |
| *Before #50B* | *0* | *0* | *0* | — | *0* |
| Window control rows | 2 | 2 | 1 | 1 | 1 |

Mobile height falls 7%; desktop rises ~2% because the chart and two new sections
outweigh what progressive disclosure recovered. **Reaching zero undersized
targets** needed `summaryClassName="min-h-11"` on `DataBasisNote`,
`EvidenceDisclosure` and `MethodologyDisclosure` — the opt-in #46C built for
exactly this — plus the two inline links in the page footer.

**Interaction:** all four windows verified; focus retained; one selected always;
26 animated elements all carrying `motion-reduce`; reading is
`aria-live="polite"`. **Themes:** identical light and dark, lowest contrast 6.72.
**Loading and unavailable:** covered by `PriceClimb.test.tsx` — a window with no
computed rate is disabled, shows "n/a", and no `0.00%` appears.

### 4.1 One defect found by looking, two measurement artifacts

- **"September 2021" started 8px outside the card.** The label was centred on
  6% — fine for the prototype's "Sep 2021", wrong for the shared formatter's
  long month. Anchored to the card edges; verified inside at 390 and 1440.
- **Section heights inside a closed `<details>` are phantom.** The collapsed
  classification disclosure measures 44px, but the sections within it still
  report their old rects. Same artifact as #48B and #49B.
- **`getBoundingClientRect` cannot see `ExplanationTrigger`'s 44px `::before`.**
  Twelve "i" triggers read as 16px until measured by effective hit area.

---

## 5. Data dependency, restated

**There is still no rate-over-time series.** `/monitors/inflation` publishes
rates for one period; `/monitors/inflation/history` publishes twelve **states**
and no rates. The most persuasive version of this page — a falling rate line
over a rising level — remains unbuildable without a backend contract, and
deriving it from the 59 index levels would be client-side economics.

`src/api/series.types.ts` records this in the type file itself.

---

## 6. Files changed

**New:** `api/series.ts`, `api/series.types.ts`,
`components/inflation/PriceClimb.tsx` (+ test), `buildCorePceObservations`
fixture.

**Modified:** `pages/Inflation.tsx` (+ test), `components/inflation/DataBasisNote.tsx`,
`EvidenceDisclosure.tsx`, `MethodologyDisclosure.tsx`, `layouts/pageSurface.ts`
(+ test), `App.test.tsx`.

**Not touched:** every `api/inflation*`, `inflation_v1.0` behaviour,
`InflationHero`, `MomentumMetrics`, `TargetPanel`, `ConfirmationPanel`,
`HeadlineContext`, `WhatChangedSection`, `IntelligenceHistorySection`.

---

## 7. Final browser verification (2026-09-23)

Both states simulated in the **real production frontend** on `:5193`, by
patching `window.fetch` at runtime for `/api/v1/series/` and navigating
client-side. No application code was changed to produce either state.

| | Loading | Failed |
|---|---|---|
| Chart drawn | no | no |
| Skeleton | "Loading the price level" | — |
| Message | — | **"The price level could not be loaded."** + Retry, `role="alert"` |
| Illustrative "6% to 3%" | **absent** | **absent** |
| Lesson copy still renders | yes (no figures in it) | yes |
| Monitor rates still shown | yes | yes |
| Headline PCE | `(PCEPI)`, July 2026 | `(PCEPI)`, July 2026 |
| Headline CPI | `(CPIAUCSL)`, August 2026 | `(CPIAUCSL)`, August 2026 |

Failure isolation holds: only the climb section shows the error, and every other
section — classification, what changed, headline context, history — renders with
its own attribution and its own observation month unchanged.

### 7.1 One defect found, and fixed

**With the monitor resolved and the price series failed, the illustrative
"6% to 3%" appeared an inch below "The price level could not be loaded."**

It was gated on `monitor.status === "success"` alone. That was the wrong
condition: the example exists to contrast with the LEVEL the climb draws, so
with no climb it has nothing to anchor to — an unlabelled-looking pair of
percentages beside an error message is exactly the misreading the guard exists
to prevent.

Now gated on the climb as well. The two reviewed sentences carry the lesson
meanwhile and contain no figures.

Three regression tests added to `pages/Inflation.test.tsx`: the unavailable
message and Retry render instead of a chart; no illustrative percentage appears
while the climb has not loaded; and every other measure keeps its own series id
and period when the series fails independently.
