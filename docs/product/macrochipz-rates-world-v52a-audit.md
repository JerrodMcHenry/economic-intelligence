# MacroChipz Rates World — #52A audit

**Date:** 2026-09-24
**Scope:** audit and prototype only. No production frontend or backend file was
modified, no dependency added, nothing committed or pushed.
**Environment:** local backend on :8000, production frontend on :5193, prototype
server on :5312. All figures below are from that environment's seeded data.

---

## 0. The brief's premise needs correcting first

The brief asks to "explore a Treasury yield curve if the API supports comparable
maturity observations for the same date." It does, and **`/rates` already draws
one**. #49B shipped a selectable four-maturity yield curve chart in September. So
the obvious answer to this increment is already in production, and building it
again would be a restyle with a new coat of paint.

That made the audit's real question narrower and more useful: *given that the
curve is already drawn, what does the API send that the page still throws away?*

The answer turned out to be **a second curve** — and the page has been receiving
it in every response since #29.

---

## 1. What the API actually has

### 1.1 Endpoints that exist for Rates

| Endpoint | Status | What it returns |
|---|---|---|
| `GET /api/v1/monitors/rates` | 200 | The full `rates_v1.0` result |
| `GET /api/v1/series/{id}/observations` | 200 | Daily observations, 6 Treasury series |
| `GET /api/v1/series/{id}/transform` | 200 | `absolute_change`, `percent_change`, `moving_average` |
| `GET /api/v1/intelligence?world=rates` | 200 | 6 `RATES_MOVEMENT` records |
| `GET /api/v1/monitors/rates/history` | **422** | Path param accepts only `inflation` or `labor` |
| `GET /api/v1/monitors/rates/changes` | **404** | Inflation and Labor each have one |
| `GET /api/v1/rates/sync` | — | Operator route; the UI must never call it |

### 1.2 Maturities, verified one request at a time

Six series are ingested. Each returns **119 daily observations, 2026-04-01 through
2026-09-18, with zero nulls**, and — verified programmatically — **all six share an
identical set of dates**.

| Series | Title | Latest | Observations |
|---|---|---|---|
| `UST_NOMINAL_2Y` | 2-Year Par Yield (Nominal) | 4.76% | 119, no gaps |
| `UST_NOMINAL_5Y` | 5-Year Par Yield (Nominal) | 4.86% | 119, no gaps |
| `UST_NOMINAL_10Y` | 10-Year Par Yield (Nominal) | 5.01% | 119, no gaps |
| `UST_NOMINAL_30Y` | 30-Year Par Yield (Nominal) | 5.34% | 119, no gaps |
| `UST_REAL_5Y` | 5-Year Real Yield (TIPS) | 2.55% | 119, no gaps |
| `UST_REAL_10Y` | 10-Year Real Yield (TIPS) | 2.68% | 119, no gaps |

Provider `TREASURY`, dataset `daily_treasury_yield_curve`, units Percent, all
observed 2026-09-18, `revision_count: 0`.

### 1.3 Data that does **not** exist, recorded so nothing fills the gap

- **No spread history series.** `UST_SPREAD_2s10s`, `2s10s`, `UST_2s10s` and
  `T10Y2Y` all return 404. The 2s10s/2s30s spread exists only as a value on the
  latest date plus four published window comparisons. **A spread cannot be
  plotted over time without either a new backend series or client-side
  subtraction, and the second is prohibited.** Future dependency, not a feature.
- **No recorded-result history for Rates.** `/monitors/rates/history` → 422.
  Inflation and Jobs can replay a past conclusion and show whether it still
  reproduces; Rates structurally cannot. `IntelligenceHistorySection` consumes
  `MonitorHistoryResponse` and therefore **cannot be reused here as-is**.
- **No what-changed endpoint.** `/monitors/rates/changes` → 404.
- **Ten maturities absent.** Treasury publishes 1M–20Y as well; MacroChipz
  ingests six. The drawn curve is the part that exists, not the whole curve.
- **No point-in-time basis.** `data_basis: latest_published_data` — values
  include later corrections.

---

## 2. The finding: a whole second curve arrives and is rendered as four deltas

Every entry in `nominal_curve[]` carries a `changes[]` array of four session
windows. Each change publishes `from_date`, `from_value`, `to_date`, `to_value`
and `change_basis_points`.

**The `from_date` values are identical across all four maturities.** Verified:

| Window | from_date | 2Y | 5Y | 10Y | 30Y | aligned |
|---|---|---|---|---|---|---|
| 1 session | 2026-09-17 | 4.67 | 4.78 | 4.94 | 5.29 | ✅ |
| 5 sessions | 2026-09-11 | 4.63 | 4.78 | 4.96 | 5.35 | ✅ |
| 21 sessions | 2026-08-19 | 4.19 | 4.35 | 4.65 | 5.19 | ✅ |
| 63 sessions | 2026-06-18 | 4.19 | 4.23 | 4.46 | 4.90 | ✅ |

Four published values on one published date **is a curve**. The page today
renders those same numbers as sixteen basis-point figures scattered across four
cards, and never as a shape.

What that costs the reader is concrete. Over 21 sessions **two different things
happened at once**:

- **Level** — every maturity rose. 2Y +57 bp, 5Y +51 bp, 10Y +36 bp, 30Y +15 bp.
- **Shape** — the 2Y-to-30Y gap *narrowed*, from **1.00** points to **0.58**
  (published as −42 bp on the `2s30s` spread's own `changes[]` entry).

A single-date chart cannot show either. A reader looking at `/rates` today sees
an upward-sloping line and no indication that the line both rose and flattened.

**And the shape comparison needs no arithmetic.** The `2s30s` spread publishes
`from_value` and `to_value` for the same four windows, so "wider or narrower" is
a comparison of two published fields, not a subtraction of two yields. This
matters: `src/test/no-rates-calculation.test.ts` forbids exactly that
subtraction, and the design does not need to go near it.

---

## 3. Second finding: six recorded movements render nowhere

`GET /api/v1/intelligence?world=rates` returns six `RATES_MOVEMENT` records, one
per ingested series, each with evidence (`provider`, `observation_date`,
`value`), methodology and limitations.

`/rates` renders none of them. Inflation and Jobs both carry a history section;
Rates carries `RevisionsLink` and nothing else.

The limitation text on those records is worth quoting because it is exactly the
right register and the page should adopt it rather than invent its own:

> "Carries no significance claim: rates_v1.0 defines no notability threshold, so
> this reports the movement and its own historical position, not that the
> movement matters."

---

## 4. The current page, measured

Production `/rates`, post-#49B, in a same-origin iframe at five widths.

| | 390 | 440 | 768 | 1024 | 1440 |
|---|---|---|---|---|---|
| Document height | 5,646 | 5,559 | 4,059 | 4,143 | 4,175 |
| Horizontal overflow | 0 | 0 | 0 | 0 | 0 |
| Elements escaping their card | 0 | 0 | 0 | 0 | 0 |
| Interactive targets under 44px | 0 | 0 | 0 | 0 | 0 |

**#49B's accessibility work holds.** Nothing is broken. The problems are
editorial and proportional.

### 4.1 Section heights at 390px

| Section | Height | Share |
|---|---|---|
| Treasury curve | 444 | 8% |
| The maturity you selected | 665 | 12% |
| Real yields | 700 | 12% |
| **Calculated from the curve** | **1,902** | **34%** |
| Where these numbers come up | 204 | 4% |
| Evidence & methodology | 76 | 1% |
| Ask MacroChipz | 48 | 1% |
| When a number changes | 180 | 3% |
| Understand this | 283 | 5% |

**A third of the mobile page is four cards of derived numbers.** Each renders the
same structure: title, `2s10s`-style id, a "Calculated by MacroChipz" badge, one
big figure, the two inputs, a 2×2 grid of four session changes, a "Historical
context" disclosure and a "How this is calculated" disclosure. Four times. The
chart that is supposed to be the page's centre gets 444px — less than a quarter
of what the derived cards get.

### 4.2 Repetition

`"Sep 18, 2026"` appears **13 times** on the page. Every card states it; the hero
states it; the curve's own table states it four times. It is one observation date
for all six series, and it is repeated as though it varied.

### 4.3 The desktop composition

At 1440 the page is one 1,216px column. The chart card is 1,152px wide and 400px
tall around four points — measured as a **3.26:1 board**, an aspect ratio that
flattens any curve drawn in it. Everything else is a single stack with the right
half of the viewport unused.

---

## 5. Misleading or unsupported interpretations — reviewed

I looked specifically for economic claims the page makes or invites. Findings:

1. **No unsupported claim found in the shipped copy.** The hero sentences are
   verbatim from the reviewed `explain.what-is-a-treasury-yield` registry entry.
   The derived section explicitly says inflation compensation "can reflect
   inflation expectations as well as liquidity and risk premia, so `rates_v1.0`
   does not call it an inflation forecast." The cross-links section says
   "these are links, not conclusions." This is careful work and #52A should not
   disturb it.

2. **A known inconsistency, still open, still not fixed here.** The #49B source
   comment flags it: the same explainer's `answer` and the homepage's world
   discovery line both use the looser "what it costs the government to borrow"
   framing, which the hero deliberately avoids. A Treasury yield is what
   investors earn on a security trading in the market, not the government's cost
   on any new borrowing. **Still open. Owned by the explainer registry and the
   homepage, not by this page** — carried forward to #52A's spec as an unresolved
   question rather than patched from the Rates page.

3. **A risk this increment creates and must not realise.** Drawing a flattening
   curve invites the two claims a consumer product reaches for first: that a
   flattening or inverting curve predicts a recession, and that the 10-year sets
   mortgage rates. `rates_v1.0` supports neither — it "defines no state label, no
   forecast, and no cross-domain conclusion." The prototype states both
   non-claims on the page rather than leaving them to be inferred.

4. **"Latest published data" is not point-in-time.** Already disclosed. Retained.

---

## 6. What to keep

Everything the audit found working, listed so the next increment cannot quietly
drop it: the #49B hero copy and its human-readable date; `ExplanationTrigger`
and its 44px `::before` target; per-maturity provenance; the historical-context
percentile note; the full methodology disclosure with all six paragraphs;
`data_basis` / `methodology_id` / provider identifiers in the disclosure rather
than the hero; the attribution line; `RevisionsLink`; `UnderstandWorld`;
`AskMacroChipz` outside the monitor's resource so an Analyst outage cannot blank
the page; the `StoryTeaser` added in #49B; one `useApiResource` per resource.

---

## 7. Conclusion

The Rates page does not need a new chart. It needs the chart it has to be given
the second date the API has been sending all along, and it needs the 34% of
mobile height spent on repeated derived cards back.

Spec: `macrochipz-rates-world-v52a-spec.md`.
Prototype: `docs/product/mockups/v52a/`.
