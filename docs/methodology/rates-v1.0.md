# Rates Monitor — Methodology `rates_v1.0`

**Status: frozen and normative.** `app/domain/rates.py`, `app/models/rates.py` and `app/services/rates.py` implement this document; they do not reinterpret it. Increment #29.

This methodology is entirely deterministic. It contains no model, no estimation, no forecast, no probability, and no AI. Given the same persisted observations it produces the same result every time, and every number it reports can be reproduced by hand from the stored series.

---

## 1. Canonical input series

One provider, one dataset per metric — never a silent combination of competing sources.

| Canonical series ID | Meaning | Provider dataset | Upstream field |
|---|---|---|---|
| `UST_NOMINAL_2Y` | 2-year Treasury par yield | `daily_treasury_yield_curve` | `BC_2YEAR` |
| `UST_NOMINAL_5Y` | 5-year Treasury par yield | `daily_treasury_yield_curve` | `BC_5YEAR` |
| `UST_NOMINAL_10Y` | 10-year Treasury par yield | `daily_treasury_yield_curve` | `BC_10YEAR` |
| `UST_NOMINAL_30Y` | 30-year Treasury par yield | `daily_treasury_yield_curve` | `BC_30YEAR` |
| `UST_REAL_5Y` | 5-year Treasury par **real** yield (TIPS) | `daily_treasury_real_yield_curve` | `TC_5YEAR` |
| `UST_REAL_10Y` | 10-year Treasury par **real** yield (TIPS) | `daily_treasury_real_yield_curve` | `TC_10YEAR` |

- **Units:** percent (a stored `5.01` means 5.01%).
- **Frequency:** one observation per published business session. The feeds skip weekends and US holidays; the methodology never assumes a fixed calendar cadence.
- **Identifiers are our own.** They are deliberately not FRED's (`DGS10`, `DFII10`) so a Treasury-sourced observation can never be confused with a FRED-sourced one carrying different provenance and different licensing.
- **Source timing:** Treasury derives these from indicative quotations obtained by the Federal Reserve Bank of New York at approximately 3:30 PM ET each business day.
- **Real yields begin 2004-01-02**; the nominal series run far longer. A derived metric spanning both is therefore bounded by the shorter history, which the response reports rather than papers over.

### Deliberately not included in V1

**Policy and overnight rates (federal funds target range, EFFR, SOFR) are deferred, not forgotten.** Each would introduce a second provider with its own obligations: the NY Fed's rates licence requires two specific legends and carries an indemnification clause, and the FRED route carries the terms ambiguity documented in #28 §10.2. V1 keeps exactly one provider so every observation's provenance and licensing is uniform. Adding them is a deliberate later increment with its own licence review, not an afterthought.

Also excluded, permanently for this methodology: credit spreads (ICE BofA index data is licensed), DXY (ICE proprietary), equities, crypto, and any consensus or survey series.

---

## 2. Sources, licensing, attribution

- **Provider:** U.S. Department of the Treasury, Daily Treasury Par Yield Curve Rates and Daily Treasury Par Real Yield Curve Rates.
- **Access:** unauthenticated public XML feeds. No API key exists, so none is configured, stored, or logged.
- **Licensing basis: REASONABLY SUPPORTED, not verified.** Re-checked against authoritative Treasury pages on 2026-09-19:
  - The [interest-rate statistics page](https://home.treasury.gov/policy-issues/financing-the-government/interest-rate-statistics) and the [XML feed documentation](https://home.treasury.gov/treasury-daily-interest-rate-xml-feed) publish **no terms of use, no copyright notice, no attribution requirement, and no rate limit**. The feed documentation describes only `BaseURL + Endpoint + Parameters`.
  - [Treasury's Site Policies and Notices](https://home.treasury.gov/subfooter/site-policies-and-notices) is an index and asserts no copyright or reuse terms; the [privacy policy](https://home.treasury.gov/subfooter/privacy-policy) addresses privacy only.
  - The explicit open grant — "The data is offered free, without restriction, and available to copy, adapt, redistribute, or otherwise use for non-commercial or commercial purposes" — belongs to the [Fiscal Data API](https://fiscaldata.treasury.gov/api-documentation/), which covers a **different set of endpoints and does not mention these feeds**. It is therefore *not* relied on here.
  - **A genuine counter-signal, recorded deliberately:** the Bureau of the Fiscal Service / TreasuryDirect properties carry restrictive terms — material may be viewed, downloaded and printed "for noncommercial personal use only", with "You should not assume anything on this site is necessarily in the public domain." Those terms govern *those* sites (fiscal.treasury.gov, treasurydirect.gov), **not** the `home.treasury.gov` interest-rate statistics this methodology consumes. But they show Treasury does impose restrictions on some properties, so the absence of terms on these pages must not be over-read.
  - **Operative basis:** 17 U.S.C. §105 (works of the U.S. Government are not subject to domestic copyright), plus the absence of any restrictive notice on the publishing pages.
  - **Residual risk:** no affirmative written grant covers these specific feeds. **Action before any public deployment: obtain written confirmation from Treasury.** Until then this remains a documented limitation, not a settled permission. Note also that the par yields are *derived by Treasury* from indicative quotations obtained by the Federal Reserve Bank of New York; the underlying quotations are not published and are not redistributed here.
- **Attribution rendered with every result:** `Source: U.S. Department of the Treasury (Daily Treasury Par Yield Curve Rates).` The API returns this string in `attribution` so no consumer has to invent one.
- **Not implied anywhere:** endorsement by Treasury, or any affiliation with it.

---

## 3. Transformations

### 3.1 Basis points

Yields are published in percentage points. One percentage point is 100 basis points:

```
change_bp = (later_value - earlier_value) * 100
```

`4.25% → 4.40%` is **+15 bp**, never "+0.15%". The sign always follows the direction of travel. The conversion exists in exactly one place (`app.domain.rates.to_basis_points`) and results are rounded to remove binary floating-point residue, which is why `4.25 → 4.40` returns exactly `15.0` rather than `15.000000000000002`.

### 3.2 Curve spreads (derived)

```
2s10s_bp = (UST_NOMINAL_10Y - UST_NOMINAL_2Y) * 100
2s30s_bp = (UST_NOMINAL_30Y - UST_NOMINAL_2Y) * 100
```

Both legs must come from the **same observation date**. A negative spread is reported as a negative number and nothing more: this methodology attaches no label, no "inverted" state, and no recession reading to it.

`5s30s` was considered and **excluded**: it answers a question 2s10s and 2s30s already cover for a V1 whose purpose is a foundation, and every additional derived metric is additional surface to justify, test, and explain.

### 3.3 Market-implied inflation compensation (derived)

```
compensation_5Y_pp  = UST_NOMINAL_5Y  - UST_REAL_5Y
compensation_10Y_pp = UST_NOMINAL_10Y - UST_REAL_10Y
```

Reported in percentage points, on exactly-shared dates only. **Terminology is load-bearing** — see §7.

---

## 4. Time-window semantics

**Every window is counted in published observations (sessions), never in calendar days.**

| Window | Meaning |
|---|---|
| `1_SESSION` | Latest observation vs the immediately preceding published observation |
| `5_SESSIONS` | Latest vs 5 published observations earlier |
| `21_SESSIONS` | Latest vs 21 published observations earlier (≈ 1 month of sessions) |
| `63_SESSIONS` | Latest vs 63 published observations earlier (≈ 3 months of sessions) |

Rationale, stated because the alternative is the more obvious choice: a calendar rule ("5 days ago") requires a fallback policy for weekends, holidays, and missing prints, and every such policy silently changes the number reported. An observation-count rule needs no fallback, is exactly reproducible from the stored series, and never quietly compares Friday with the previous Thursday because Monday was a holiday.

Consequences that are accepted deliberately:
- A `1_SESSION` change spans three calendar days across a weekend, and more across a holiday weekend.
- `21_SESSIONS` is approximately, not exactly, one month. The API therefore names windows in sessions, and any UI must do the same — never relabel `21_SESSIONS` as "1M".
- A window requires `sessions + 1` usable observations. With fewer, the result is explicitly **unavailable**, never computed over a shorter window.

---

## 5. Alignment and missing-data behavior

The rules, in full:

1. **A null value is not an observation.** A session the provider published without a value for a maturity is dropped from that series entirely — never read as zero, never carried forward.
2. **Two-series metrics require an exact shared date.** A spread or compensation value is computed only where both inputs have a usable value on the *same* date. No nearest-date matching, no forward-fill, no interpolation.
3. **Unavailability is explicit and reasoned.** When a derived metric cannot be computed, the response says which of three things happened:
   - `NO_OBSERVATIONS_FOR_EITHER_SERIES`
   - `NO_OBSERVATIONS_FOR_ONE_SERIES`
   - `NO_EXACTLY_SHARED_OBSERVATION_DATE`
4. **A series that was never ingested behaves exactly like one with insufficient history** — both are `available: false`, never an error.
5. **Missing economic data is not infrastructure failure.** The former is a normal `200` response; only a genuine database failure produces `503`/`500`.

---

## 6. Historical context

For the `5_SESSIONS` window, every same-length change in the persisted history is computed, and the current change is ranked against **all prior** changes (the current one is excluded from its own population, so nothing is ever counted as smaller than itself).

Reported: `percentile_rank` (share of prior changes strictly smaller in signed terms), `magnitude_percentile_rank` (share strictly smaller in absolute terms), the observation count, the history start and end dates, and the population's minimum and maximum.

- Both ranks are reported because they answer different questions: a large *fall* is unremarkable in signed terms and extreme in magnitude.
- Comparison is strict (`<`), so a population of identical values ranks a tie at 0.0 rather than implying an above-average reading.
- An empty population is `available: false`, never `0.0`.
- Every rank travels with its window, its observation count, and its history start date. A percentile computed over 40 sessions is a different claim from one computed over 20 years, and the response never lets those look identical.

A supported statement: *"The 5-session increase in the 10-year yield is larger than 91% of 5-session changes observed since 2004-01-02 (n = 5,412)."*

---

## 7. Terminology — what things are called, and why

**"Market-implied inflation compensation", never "inflation expectations" and never a forecast.** The nominal-minus-real difference decomposes roughly as:

```
compensation = expected inflation + inflation risk premium - TIPS liquidity premium
```

The inflation risk premium is compensation for bearing uncertainty; the TIPS liquidity premium moves sharply in stressed markets, which can drop compensation with no change in expectations at all. TIPS are also CPI-linked, while the Federal Reserve's target is defined on PCE. `rates_v1.0` does not decompose any of this, so it reports the measured difference under a name that describes exactly what was measured.

Equally prohibited in any surface consuming this methodology: "the market expects", "the bond market is pricing a recession", "hawkish", "dovish", "tightening", "easing", "risk-on", "risk-off". None of these is defined by this methodology, and V1 deliberately assigns no state label to any rate.

---

## 8. Why there are no state labels in V1

The Inflation and Labor monitors classify into named states because their methodologies define an explicit neutral band around a monthly economic aggregate. Applying the same shape to a daily market series would require inventing thresholds — and an invented threshold is an economic claim wearing a UI label.

V1 therefore reports **measurements**: the current value, the basis-point change over an explicit window, the curve spread, and the historical percentile of that change. These need no threshold and say more than a label would. The one place a boundary could be justified without invention is the definitional zero of a curve inversion; even that is left to the consumer, who can see the sign of a number this methodology reports honestly.

---

## 9. Revision and correction handling

Treasury occasionally corrects a published rate. The ingestion path classifies each incoming observation as:

- **inserted** — no observation existed for that series and date;
- **revised** — an observation existed and the provider's value genuinely differs (the stored value is updated, and the provenance row's `revision_count` and `last_revised_at` advance);
- **unchanged** — the value matches what is stored, so only `retrieved_at` moves.

Re-running an identical sync therefore inserts nothing and reports no revisions. Revision history never inflates through routine re-syncs, which keeps `revision_count` meaningful as an actual count of provider corrections.

This methodology reports **latest published data** (`data_basis: latest_published_data`). It is not a point-in-time reconstruction: it shows the values Treasury currently publishes, including corrections applied after the fact.

---

## 10. Provenance

Every **source observation** carries: provider, dataset, the upstream field name, the source URL, the observation date, the retrieval timestamp, the revision count, and the last revision time.

Every **derived value** carries a structurally different record: the methodology ID, the calculation in words, its input series IDs, the input observation date, and the calculation timestamp. It deliberately has no provider or dataset field, because **a derived metric must never masquerade as a directly sourced observation**.

---

## 11. What this methodology DOES support

- The current level of each canonical yield, and when it was observed.
- The change in any canonical or derived metric over an explicit number of sessions, in basis points.
- The 2s10s and 2s30s curve spreads, including their sign.
- Market-implied inflation compensation at 5 and 10 years.
- How unusual the latest 5-session change is against that metric's own history, with the window, count and start date attached.
- A complete audit trail from any reported number back to its inputs and their source.

## 12. What this methodology does NOT support

- **Any forecast or probability.** No expected path, no recession odds, no "likely to".
- **Any causal claim.** Never "yields rose because…".
- **Any cross-domain confirmation claim.** Nothing here states that rates confirm or contradict inflation, labor, growth, or equities. #29 exposes the canonical metrics a future, narrowly defined same-concept comparison could consume (realized inflation vs market-implied compensation — the Class A pattern in `relate-compare-audit-v1.md` §11), and implements no such comparison itself.
- **Any market state, regime, or sentiment label.**
- **Any investment recommendation, position sizing, or trading signal.**
- **A point-in-time view.** Historical values reflect today's published data, including later corrections.
- **Intraday precision.** These are daily, end-of-session facts.
- **Policy or overnight rates**, which V1 does not ingest (§1).

### Operational note (measured, not estimated)

Ingestion issues one request per dataset per calendar month, and the Treasury feeds are slow: a 6-month sync of both datasets (12 requests, 714 observations) took **≈226 seconds** end to end during #29's verification. The client timeout is 30s per request for that reason. `POST /api/v1/rates/sync` is therefore a deliberate operator action, not something to put behind a short-lived HTTP client or a page load; a large `lookback_months` should be run with a correspondingly patient client.
