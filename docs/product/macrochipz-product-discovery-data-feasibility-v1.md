# MacroChipz — Product Discovery & Data Feasibility V1

**Increment #28.** Research, product definition, and feasibility only. No production code changed, no architecture redesigned, no SRS written, no database touched, nothing committed or pushed. Baseline: HEAD `225b5f6` ("Add MacroChipz design system, shell, Home, and theme (#27B)"), clean working tree.

This document exists to answer one question before any further engineering: **what should MacroChipz become?** It is deliberately willing to conclude that parts of the proposed thesis are not supportable.

Research standard: every licensing, pricing, and capability claim below is sourced to official provider documentation, with the URL and the access date (all fetches 2026-09-19). Where authoritative documentation could not establish a fact, this document says **UNKNOWN — REQUIRES VERIFICATION** rather than guessing. Third-party sources are labeled as such.

---

## 1. Executive Summary

**The thesis as written is not supported. A narrower one might be, and has not been tested.**

Five findings drive that, each sourced in the sections below.

1. **A five-domain MVP is not buildable at $0.** Economy, Rates and FX are public-domain and genuinely free for commercial use. **Equities has no legitimate $0 path** — index levels are licensed products with no free commercial tier, delayed data receives no relief for indices, and the free sources with usable closes (Stooq, Yahoo) carry express written prohibitions. **Crypto is restricted** — either a 365-day history cap or a signed licence of unknown cost. (§9-§11)

2. **The "expected vs actual" feature is impossible.** Release-level economist consensus, analyst EPS consensus, and CME FedWatch-style policy probabilities are all proprietary or licence-blocked — including recomputing probabilities from CME settlement prices, because CME licenses *derived* data. Market-implied inflation compensation, computed in-house from Treasury inputs, is available and is **not** a consensus and must never be labelled one. (§10.6)

3. **The core capability is narrower than proposed, but real.** General cross-market "confirmation/divergence" is inference this product cannot make canonically, and this repository already froze that boundary once. What *is* deterministic is **same-concept confirmation**: realized inflation versus market-implied inflation compensation — two measurements of one question, the same operation the shipped Core PCE vs Core CPI confirmation already performs. (§16)

4. **The competitive position is weak.** ORCA's Macro Dashboard ($29-35/mo) already ships regime classification with cross-asset confirmation, historical analogs with forward-return probabilities, and per-signal hit rates — roughly 85-90% of the thesis, inside the target price band. MacroMicro (~$27-30/mo) is bundling "traceable, verifiable" AI free into existing subscriptions. 42 Macro serves this exact customer at $55-165/mo. A hobbyist site answers "what is today's regime and what changed" for **$0**. The investor population is flat (FINRA: new-investor inflow 21% → 8%), and the $10-50 band is the most crowded shelf in the category. (§7)

5. **One genuine gap exists, and it is the thing this codebase is already best at.** No reviewed product handles **point-in-time correctness** — what was knowable when, and how revisions changed the answer. ALFRED has vintages but no analysis; every analysis product silently uses revised data, including in backtests. It is a real moat because it demands discipline rather than cleverness. It is also **unproven as a reason to pay**. (§8.2, §21.1)

**Recommendation: do not build. Run the five-step validation in §25 first — the concierge test and the licensing letters can each kill or redirect this cheaply, and neither requires a line of code.** Full reasoning and the conditions that would flip this decision are in §26.

---

## 2. Product Thesis

### 2.1 The proposed thesis, stated plainly

> MacroChipz shows serious investors what is changing across the economy and financial markets, where those signals agree or diverge, and the evidence behind every conclusion.

### 2.2 What survives scrutiny, and what does not

This increment challenges the thesis in three places, and two of them break.

**Breaks — "five domains."** The proposal lists Economy, Rates, Equities, FX, Crypto. §10-§11 show these are not equally feasible at $0: economy and rates are outright public-domain; FX is public-domain at daily frequency from the Federal Reserve; equities and crypto are where the licensing and differentiation problems concentrate. A five-domain MVP would be built on the two weakest legs.

**Breaks — "confirmation/divergence" as a general cross-market capability.** §16 shows that a general "equities are confirming the labor story" claim is not deterministic intelligence. It is a causal or statistical inference this product cannot make canonically without research it has not done. This repository has already frozen exactly this boundary once (`relate-compare-audit-v1.md` §11-§12), and #28 declines to unfreeze it.

**Survives, and is stronger than the original framing — "same-concept confirmation across measurement regimes."** There is one class of cross-market comparison that *is* deterministic, already has precedent in this codebase, and is genuinely differentiating: comparing **what the data says** against **what markets are pricing about the same concept**. Realized inflation versus market-implied inflation compensation. The Fed's own stated policy path versus the path implied by the Treasury curve. These are two measurements of one question, not two different questions correlated by hope.

### 2.3 The revised thesis

> **MacroChipz tells a self-directed investor what changed in the economy and in what markets are pricing about it, whether those two are telling the same story, and shows the evidence behind every number.**

This is narrower than "cross-market intelligence for serious investors." It is also defensible at $0, implementable deterministically, and it builds directly on the Inflation and Labor engines already shipped.

---

## 3. Problem Definition

### 3.1 The problem, as experienced

A self-directed investor who follows macro has no shortage of data. They have a shortage of *resolved* data. Concretely, the recurring failure modes are:

1. **Fragmentation.** The CPI print is on BLS, the market reaction is on a broker app, the breakeven is on FRED, the Fed's stated path is in a PDF. Nothing holds them in one frame.
2. **No memory.** Almost every free tool answers "what is the level now?" Almost none answers "what changed since I last looked, and does it matter?"
3. **No context for magnitude.** A 10bp move in the 10Y breakeven is meaningless without knowing whether that is a normal daily move or a 99th-percentile one.
4. **Unattributed conclusions.** Where a free tool *does* offer a conclusion ("inflation is cooling"), the reader cannot see the rule that produced it, the observations behind it, or whether revised data changed it.
5. **Disagreement is invisible.** The single most useful macro observation — *the data says one thing and the market is pricing another* — requires manually assembling two sources and knowing what to compare.

### 3.2 What this product is not solving

Not price discovery, not execution, not security selection, not prediction. Those are well served, heavily regulated, or both (§20).

---

## 4. Target Customer / ICP

### 4.1 The provisional ICP, tested

> "Serious self-directed investors and macro-aware traders who actively manage their own money, follow economic and cross-asset developments, but do not have institutional research infrastructure."

**Verdict: coherent as a description, but not coherent as a *wedge*, because it is already the stated target of at least four shipping products** (42 Macro names "tactical traders and retail investors"; Koyfin, MacroMicro and ORCA all serve it).

### 4.2 Size and trajectory — the uncomfortable evidence

- 62% of US adults report owning stock (Gallup, surveyed April 2025) — but overwhelmingly passive retirement money, not an addressable research audience.
- **FINRA Foundation NFCS 2024** (published 2025): the share of adults investing outside retirement **did not materially change from 2021**; the inflow of new investors **fell from 21% to 8%**; 52% have invested 10+ years. Research channels: brokerage tools 75% (free, bundled), articles 67%, **social media 29% overall and 61% under 35** (free).
- **The pool is flat, and the dominant research channels are free.**

### 4.3 Subsegments, and which has the strongest problem

| Subsegment | Problem intensity | Willingness to pay | Assessment |
|---|---|---|---|
| **A. Macro-driven allocators** (adjust exposure on macro regime) | High | **Demonstrated: $55-165/mo to 42 Macro, $104-120/mo to ORCA Premium** | The real buyer — and already served |
| **B. Serious generalist DIY investors** (macro as context) | Medium | $13-39/mo (TradingView, Koyfin) | Large, price-anchored low, served by charting/data tools |
| **C. Finance-adjacent professionals** (analysts, PMs without a terminal, advisors) | Medium-High | $39-299/mo (Koyfin Advisor tiers) | Underexplored, but they need breadth and client-ready output |
| **D. Crypto-native macro watchers** | Medium | $49+/mo (Glassnode) | Served, and our crypto data is licence-blocked (§10.5) |
| **E. Learners** | Low | Near zero | Explicitly not a paying segment |

**Finding: the willingness-to-pay evidence points at subsegment A, whose price point is 2-4× higher than the $10-50 band the brief assumed — and who are exactly the people ORCA and 42 Macro already serve.** Competing below your own customer's demonstrated willingness to pay, against free substitutes, with no distribution, is the weakest available position.

### 4.4 The honest ICP conclusion

If MacroChipz proceeds, the ICP must be **narrower than "serious self-directed investor"** and chosen for a problem the incumbents structurally do not solve. §8.2 identifies the only such problem found: people for whom **being wrong about what was knowable when** is costly — which points more toward subsegment C (people who must defend a conclusion to someone else) than toward subsegment A (people who must act on it).

That is a hypothesis, not a finding. §25 is how it gets tested.

---

## 5. Jobs To Be Done

Ranked by how well this product's actual machinery can serve them.

| # | Job (user's words) | Frequency | Served by |
|---|---|---|---|
| 1 | "Tell me what changed since I last checked, and whether it mattered." | Every visit | Since Last Visit + change detection (**shipped**) |
| 2 | "Is the market pricing the same inflation story the data is showing?" | Weekly / release day | Same-concept confirmation (§16) |
| 3 | "How unusual is this?" | Every reading | Historical context (§17) |
| 4 | "Why does this say what it says?" | On doubt | Evidence (**shipped**) |
| 5 | "What is happening right now, in one place?" | Daily | Domain states (§13) |
| 6 | "What does this mean for my portfolio?" | — | **Refused** (§20) |

Job 6 is where most retail macro products go, and it is out of scope permanently, not merely for MVP.

---

## 6. Current User Workflow

What the target user actually does today, assembled from the competitive landscape (§7) and the tools they demonstrably pay for:

| Step | Tool today | Cost | Pain |
|---|---|---|---|
| See the number | FRED, BLS, brokerage app | Free | None — data access is solved |
| Know it arrived | FRED email alerts, broker push | Free | Solved, though undifferentiated |
| See what was expected | Trading Economics, MarketWatch calendar | Free to view | Solved for them, **licence-blocked for us** (§10.6) |
| See the market reaction | TradingView, broker | $0-30/mo | Solved |
| Decide if it changed the picture | 42 Macro, ORCA, MacroMicro, or their own head | $0-165/mo | **Partly solved by newsletters/regime products** |
| Check how unusual it is | Mostly nothing; occasionally Koyfin/Core Brief | — | **Weakly served** |
| Know whether a revision moved it | **Nothing** | — | **Unserved (§8.2)** |
| Remember what changed since last time | FRED alerts (per-series), Perplexity Tasks | Free | **Weakly served across markets** |

**The workflow is not broken at the data layer; it is broken at the synthesis-and-memory layer — and even there, partial solutions exist and are cheap.** That is the central reason §26 is cautious.

---

## 7. Competitive Landscape

All pricing from official pages unless marked `[3P]` (third-party), accessed 2026-09-19. Where no official price page exists, the figure is marked UNKNOWN.

### 7.1 The products that matter

| Product | Price (official unless noted) | What it actually solves | Relevance |
|---|---|---|---|
| **ORCA Macro Dashboard** | **Free / Pro $35/mo ($29 annual) / Premium $120/mo** | Regime classification **with cross-asset confirmation**; **Analog Explorer** (historical period matching → forward-return probabilities); portfolio backtester; per-signal **hit rates**, "every claim sits on a frequency table" | **The closest competitor found. ~85-90% of the proposed thesis, shipped, mid-band.** |
| **MacroMicro** | ~$27-30/mo `[3P — Cloudflare-walled]` | Business-cycle phase framework; **US and Global recession-probability models with input variables published**; cross-asset chart collections; deep global macro | **~70% of the thesis, with the data moat and the distribution.** MM AI (rolling out from mid-2026) markets "every conclusion is drawn from a verifiable, traceable trusted database" — MacroChipz's stated differentiator, claimed by an incumbent, **bundled free into existing subscriptions**. |
| **42 Macro** | **$55 / $85 / $115 / $165 per mo** | GRID regime framework (growth × inflation rate-of-change) mapped to cross-asset allocation | ~65% of the thesis, aimed at exactly this customer, **above the proposed price ceiling** — the key pricing datapoint. |
| **Koyfin** | **Free / $39 / $79 / $209 / $299** | Bloomberg-lite for serious retail; strong macro (40+ country yield curves, calendar **with consensus**), real alerts | Has the data and alerts, **no interpretation layer, no percentile/regime tooling**. Best proxy for the niche's economics: ~200K users on **~$7M raised over a decade** `[3P]`. |
| **Trading Economics** | Basic **$29/mo**, Standard **$199/mo** | 196-country indicator breadth; **economist consensus + own ARIMA forecasts** | Has the one thing MacroChipz cannot obtain at $0 (§10.6). |
| **Glassnode** | Advanced **$49/mo**; Professional quote-only | Crypto regime scoring; **Market Compass** — 7 lenses incl. Macro and Cross-Asset Rotation, 0-100 scores, 7d/30d deltas, Risk-Off↔Risk-On composite | Same grammar as the proposed product, anchored to crypto. |
| **FRED** | **Free** | 508,000+ series; **ALFRED vintages**; **free email alerts on new data** | The free floor for economy data — and it already has change notifications. |
| **CME FedWatch** | **Free to view** | Market-implied FOMC probabilities, published methodology | Free, and licensing-blocked for us (§10.6). |
| **TradingView** | **$12.95-$199.95/mo** | Charting; 100M+ users claimed; economic calendar; **official MCP server (Essential+)** | Distribution giant; macro is a calendar widget, not intelligence. |
| **thetrading.tools Cross-Asset Macro Panel** | **Free, no account** | Literally: "what is today's macro regime, and what changed?" — 15 instruments → 4 drivers → named regimes, published methodology | **A hobbyist answers MacroChipz's core question for $0.** |

High anchors for completeness: Bloomberg ~$32K/yr/seat `[3P]`, LSEG Workspace ~$22K/user/yr `[3P]`, FactSet ~$27.5K/yr `[3P]` — no official pricing pages exist. Their relevance is not competition but direction of travel: **LSEG shipped GA "AI Search" with transparent citations in July 2026**, and FactSet pushed AI document search to 85,000+ users. Citation-grounded AI answers are becoming table stakes, funded far better than we are.

### 7.2 What this means, stated without flinching

1. **Every named pillar already exists in a shipping product**, and three of four exist *together* in ORCA at $29-35/mo.
2. **The floor is free and falling.** FRED (free, with alerts) + CME FedWatch (free) + thetrading.tools (free) + open-source FRED-based analog/scoring repos. A TradingView seat (~$13) plus an LLM (~$20) plus a free FRED MCP server reproduces much of the experience for ~$33/mo.
3. **Incumbents are bundling the differentiator for free.** MacroMicro auto-upgrades existing subscribers to MM AI at no extra cost, advertising traceability.
4. **The segment is flat, not growing.** FINRA's 2024 NFCS: new-investor inflow fell 21% → 8%; the investing population did not materially change; the fastest-growing information channel is free social media (61% under 35).
5. **The $10-50 band is the most crowded shelf in the category** — at least 14 products occupy it — while the *actual* described customer demonstrably pays **$55-165/mo** (42 Macro) and **$104-120/mo** (ORCA Premium).
6. **A cautionary datapoint:** Messari phased out self-serve Lite/Pro tiers in 2026 to focus on Enterprise — a well-known research brand concluding self-serve research subscriptions did not pay.

### 7.3 What is *not* white space

Regime detection, historical analogs, percentile/z-score framing, cross-asset confirmation, change alerts, macro breadth, and cited-evidence AI answers are **all already shipped**, several of them for free. None of these can be claimed as differentiation.

---

## 8. Proposed MacroChipz Wedge

### 8.1 The original wedge does not survive

"Cross-market intelligence with confirmation/divergence, historical context and evidence" is **not** a credible wedge in September 2026. §7 shows it shipped, cheaper, by at least three products, with a free floor underneath.

### 8.2 The one defensible piece of ground

The competitive research found exactly one capability absent from every product reviewed, and it is the one this repository is already unusually good at:

> **Point-in-time correctness: knowing what was true *when*, and showing how revisions changed the answer.**

- ALFRED has vintages but no analysis layer.
- Every analysis product reviewed — ORCA, MacroMicro, 42 Macro, Koyfin, Trading Economics — silently uses **latest-revised** data, including in backtests and analogs. A regime model backtested on revised data is measuring a world no investor could have traded.
- Nobody surfaces: *"the print you saw that morning was X; it is now Y; the signal flipped because of a revision, not because of new information."*

This is unglamorous, it compounds, and it is hard to copy because it requires **discipline rather than cleverness** — precisely the discipline this codebase has already been built around: revision-aware change detection (`NEW`/`REVISED`/`UNCHANGED`), an append-only recorded-result history, release-processing audit rows, and a shipped "latest revised data" disclosure that already refuses to pretend a reconstruction is a real-time record.

### 8.3 Honest assessment of that wedge

It is **narrow, real, and probably not by itself a business**. Revision-awareness is a credibility feature, not a reason most people subscribe. It makes a product trustworthy; it does not make it wanted. That distinction drives §26.

---

---

## 9. Domain Scope

The five proposed domains are not equally feasible. Sorted by what the research actually established:

| Domain | $0 commercial data? | Verdict |
|---|---|---|
| **Economy** | **Yes** — BLS, BEA, Board of Governors, Treasury all public domain | **IN.** Already built. |
| **Rates / Bonds** | **Yes** — Treasury curves, H.15, NY Fed rates API, ACM term premium; breakevens computed in-house | **IN.** The strongest new domain: entirely public-domain, daily, deep history, and it pairs with Economy for the one defensible confirmation loop (§16.2). |
| **FX** | **Yes, at daily frequency** — ECB reference rates + Fed H.10 | **IN, but thin.** Cheap to add and legitimately licensed. Its intelligence contribution is modest: a dollar move is context, not a conclusion. ICE's DXY is prohibited. |
| **Equities** | **No** — **no legitimate $0 path exists** | **OUT of a $0 MVP.** Index levels are licensed products with no free commercial tier; delayed data gets **no** relief for indices; the free sources with usable closes (Stooq, Yahoo) carry express prohibitions. The honest floor is a paid ETF-proxy feed at **$9.99-$149/mo**. |
| **Crypto** | **Restricted** | **OUT of MVP.** Either a 365-day history cap (CoinGecko/CMC) or a signed Bitstamp Data License Agreement of unknown cost. |

**Finding: a five-domain MVP is not buildable at $0.** A three-domain MVP (Economy + Rates + FX) is — and those three happen to contain the only cross-market comparison this product can make canonically.

**If equities are ever added**, the design is already determined by the licensing: buy adjusted daily closes for ~15-30 **ETFs**, compute intelligence server-side, publish **derived series only** (no raw OHLC tables, no CSV export of prices), and label everything by ticker — "US Large Cap (SPY)", never "S&P 500". Naming the index adds trademark exposure independent of data rights.

---

## 10. Data Source Feasibility

All findings below are from official provider documentation, accessed **2026-09-19**. The governing distinction throughout is **free to access** vs **free to use in a commercial product**.

### 10.1 The single most important finding

**Public-domain US government data is the only category that is unambiguously free for a paid commercial product.** Everything else — including data that is free to *look at* — carries a restriction: personal-use-only, non-commercial, no-redistribution, no-derived-works, or "contact us for a licence".

That is not a limitation to work around; it is the product's boundary. **A domain is in scope for MVP only if its data is public-domain or explicitly licensed for commercial redistribution.**

### 10.2 Economy — SAFE

| Source | Status | Notes |
|---|---|---|
| **BLS Public Data API** (CPI, payrolls, unemployment, JOLTS) | **Public domain** | "Everything that we publish… is in the public domain" (bls.gov/bls/linksite.htm). Cite BLS + retrieval date. **500 queries/day** on the registered v2 key is the binding constraint — cache server-side, never proxy user requests 1:1. |
| **BEA API** (GDP, PCE) | **Likely safe, unverified** | 100 req/min. **The TOS is a PDF that could not be machine-read, and BEA's citation page does not assert public-domain status** → UNKNOWN — REQUIRES VERIFICATION before launch. |
| **Federal Reserve Board** (H.15, H.10) | **Public domain** | "Information on Board's website is in the public domain and may be copied and distributed without permission" (federalreserve.gov/disclaimer.htm). Seals/logos excluded. |
| **Treasury Fiscal Data API** | **Explicit commercial grant** | "free, without restriction, and available to copy, adapt, redistribute, or otherwise use for non-commercial or commercial purposes." No key, no registration. The strongest grant of any source reviewed. |

**FRED is a special case and must not be the product's spine.** Three specific problems, all from its own terms (fred.stlouisfed.org/docs/api/terms_of_use.html, /legal/):

1. **The "replicate the essential user experience" prohibition.** Apps that "replicate or attempt to replace the essential user experience of the FRED® API, or the FRED® or ALFRED® web sites" are prohibited. A product whose core is browsing and charting FRED series is exposed. MacroChipz's derived intelligence is differentiated — but this is a real constraint on how far the product can drift toward "a nicer FRED".
2. **The per-user API key clause.** "Individual users of an application must use their own API key" — read literally, this conflicts with a single-key multi-tenant SaaS. UNKNOWN — REQUIRES VERIFICATION.
3. **Mixed copyright across series.** FRED carries three machine-readable labels: *Public Domain: Citation requested*; *Copyrighted: Citation required* (~210,000 series — FRED's grant covers "internal commercial uses" and display "in reports to clients", which does **not** clearly extend to a paid public web app); and *Copyrighted: Pre-approval required* (non-commercial/personal only).

**Therefore: source public-domain series directly from BLS / Board / Treasury, and use FRED/ALFRED for revision vintages and backfill only.** This also removes the multi-tenant key question from the critical path.

### 10.3 Rates — SAFE, and the strongest domain

Everything the product needs is public-domain or explicitly licensed:

- **Nominal Treasury curve** (CMT 1M–30Y): Treasury XML/CSV feeds and H.15. Public domain.
- **TIPS / real yield curve** (from 2004-01-02): Treasury real yield curve feeds and H.15 `DFII*`. Public domain.
- **Policy rates**: FOMC target range and effective fed funds, Board of Governors. Public domain.
- **SOFR, EFFR, OBFR, TGCR, BGCR**: NY Fed markets API — free, keyless, with an explicit licence to "use, copy, and distribute Content for your personal or business purposes", **conditional on two required legends** and an indemnification clause. SOFR revises same-day at ~2:30pm ET when the change exceeds 1bp, so ingestion must re-poll.
- **Breakevens and curve spreads**: **compute in-house.** FRED's `T10YIE`/`T5YIE`/`T10Y2Y` are St. Louis Fed–computed and tagged *Copyrighted: Citation required*; the arithmetic (nominal − real, 10Y − 2Y) over public-domain inputs is not. Computing them converts a restricted dependency into a clean one at zero cost. This is a concrete, load-bearing design decision.
- **Term premium / expected short-rate path**: NY Fed **ACM** dataset, daily 1961–present, updated weekly, business use permitted with attribution.

**Excluded:** ICE BofA index series (`BAMLxxx`) — "reproduction… prohibited except with prior written permission", and ICE additionally bars distributing end-of-day index values to third parties.

### 10.4 FX — SAFE at daily frequency

- **ECB Data Portal** (data-api.ecb.europa.eu): keyless, no documented rate limit, **full daily history from 1999-01-04**, T-0/T-1 freshness. ESCB reuse policy: "All publicly available ESCB statistics may be reused free of charge on the condition that the source is quoted… and that the statistics are not modified." EUR-crosses invert trivially to USD/JPY, GBP/USD.
- **Federal Reserve H.10**: 24 currencies plus Broad/AFE/EME dollar indexes, history to 1971. Public domain. **Published weekly (Mondays, 4:15pm) for the prior week** — so the broad dollar index can be 8–10 days stale.
- **Three obligations attach to ECB data in a paid product:** cite the ECB; state explicitly that derived changes/percentiles are the product's own modification; and — per the ECB disclaimer — inform buyers "before they pay any subscription or fee and each time they access the information" that the data is available free from the ECB. Whether that clause binds a SaaS subscription rather than "documents that are sold" is UNKNOWN — REQUIRES VERIFICATION (legal review).

**Excluded: ICE's DXY.** "Any use whatsoever of the U.S. Dollar Index, its formulation, components, weightings, values and/or methods of calculation… is strictly prohibited without the express written consent of ICE Data Indices, LLC." The Fed's trade-weighted indexes are an independent, public-domain family and must never be labelled "DXY" or presented as "the dollar index" in a way implying ICE's benchmark.

### 10.5 Crypto — RESTRICTED

There is **no zero-paperwork, terms-clean source of BTC/ETH daily closes with multi-year history and commercial rights.**

| Source | Blocker |
|---|---|
| Coinbase | Market Data ToU bars redistributing or displaying Market Data **or derived works** to third parties, and separately bars creating indexes or benchmarks. Squarely prohibits this product. |
| Kraken | Bars commercial exploitation of "Our Content" and third-party apps without written consent. Also only ~720 candles of history. |
| Gemini | "Personal and/or internal use"; distribution prohibited. ~1 year of history. |
| Binance | US egress returns HTTP 451; dataset archives reportedly CC BY-NC-SA (non-commercial). |
| CoinGecko Demo | **Commercial use permitted** with "Powered by CoinGecko" attribution — but history is hard-capped at **365 days**, and a 24-hour cache-refresh clause sits awkwardly against a permanent history store. |
| CoinMarketCap Basic | **Commercial use now included** (one product, ≤100k users) — but free daily history is ~1 year. |
| Bitstamp | **The only affirmative grant**: "Bitstamp allows the incorporation and redistribution of our exchange data for commercial purposes. This includes the right to create ratios, calculations, new original works, statistics" — history to 2011-09 — **but it runs through a signed Data License Agreement whose cost is unknown.** |

**Finding that contradicts the usual assumption:** it is not true that "exchange raw data is fine and aggregator composites are restricted". Three of five major exchanges restrict their own trade data as tightly as any index vendor, while the two aggregators with clean commercial grants cap history at a year.

### 10.6 Expectations and consensus — mostly NOT FEASIBLE

This is the most consequential negative finding in the increment.

| Concept | Verdict at $0 | Detail |
|---|---|---|
| **Economist consensus for a specific release** ("CPI expected +0.2% m/m") | **NOT FEASIBLE** | Every source is proprietary: Bloomberg, LSEG/Reuters Polls, Dow Jones/WSJ, Econoday, Trading Economics. TE's terms grant only a "limited, personal, nontransferable" licence and price by "the distribution you make"; redistribution is an Enterprise negotiation. |
| **Analyst earnings consensus** (EPS/revenue) | **NOT FEASIBLE** | Finnhub: free tier "strictly for personal use", and you may not redistribute "or derived results from the data". FMP and Alpha Vantage: personal, non-commercial only. Yahoo: may not "derive income from the use… of the Yahoo APIs" (and `yfinance` scrapes undocumented endpoints — not a licensed channel). |
| **Policy-rate probabilities from futures** (FedWatch-style) | **NOT FEASIBLE** | CME's programmatic FedWatch API requires entitlement; CME Website Terms restrict content to personal, non-commercial use; and CME's Information Policies treat **derived data** as separately licensable. Recomputing probabilities from CME settlement prices and republishing is inside the same regime. No open-licensed source of fed-funds-futures prices was found. |
| **Market-implied inflation compensation** | **FEASIBLE** | Computed in-house from Treasury/H.15 public-domain inputs (§10.3). |
| **Model-based expected short-rate path / term premium** | **FEASIBLE** | NY Fed ACM, business use permitted with attribution. Weekly-updated and model-dependent. |
| **Policymakers' own projections (SEP / dot plot)** | **FEASIBLE** | Public domain. Quarterly; HTML/PDF only (no official CSV), though FRED carries medians (e.g. `FEDTARMD`, Public Domain: Citation Requested). |
| **Consumer inflation expectations** | **FEASIBLE** | NY Fed Survey of Consumer Expectations, monthly, business use permitted with attribution. It is a *consumer* survey — must be labelled as such, never as economist consensus. |
| **Decomposed expected inflation** (expectation vs risk premium) | **FEASIBLE WITH LEGAL REVIEW** | Cleveland Fed model series are **CC BY-SA 4.0** — ShareAlike copyleft; whether embedding creates an "adapted" dataset requiring same-licence release is a legal question. |
| **University of Michigan sentiment/expectations** | **PROHIBITED** | "You agree not to reproduce, retransmit, distribute, sell, publish, or broadcast the data… without the express written consent of the University of Michigan." FRED's `UMCSENT` inherits this. |
| **Philadelphia Fed SPF** (professional forecaster medians) | **UNKNOWN** | Quarterly, 1968–present, but only "Copyright 2026. All rights reserved." — no redistribution grant. Also structurally unsuitable as release-level consensus: it is quarterly, forecasts quarterly-average annualised rates, and covers no monthly release series. |

**Direct product consequence:** MacroChipz **cannot ship an "Expected vs Actual" column** for economic releases. Any UI promising one is unfillable at $0. The honest substitutes are "Actual vs prior / vs 3-month average" (public domain, genuinely informative) and a clearly separated "market-implied" panel. The schema should reserve a consensus slot for a future licensed feed.

---

## 11. Data Source Matrix

All entries verified against official documentation on **2026-09-19**. "Commercial" = usable in a paid product. Attribution column lists the obligation that must render in the UI.

### 11.1 MVP-eligible (public domain or explicit commercial grant)

| Domain | Metric | Dataset / series | Provider | API | Cost | Commercial | Redistribution | Attribution | Depth | Freq | Rate limit | Revisions | MVP? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Economy | CPI, payrolls, unemployment, JOLTS | BLS series | BLS | `api.bls.gov/publicAPI/v2` | $0 | **Yes — public domain** | Permitted | "Source: BLS" + retrieval date + "cannot vouch" disclaimer; no BLS emblem | Full, 20yr/request | Monthly | **500 queries/day** (v2 key) | Current vintage only | **MVP** |
| Economy | GDP, PCE | NIPA tables | BEA | `apps.bea.gov/api` | $0 | **Verify** — TOS is an unreadable PDF; BEA does not assert public domain | Verify | "Citations are appreciated"; no BEA logo | Full | Q / M | 100 req/min | Current vintage | **MVP, gated on TOS read** |
| Economy | Revision vintages | ALFRED | St. Louis Fed | FRED API | $0 | Amber (see §10.2) | Restricted | FRED legend required | 1776-9999 realtime model | — | 2 req/sec | **Full vintage model** | **MVP (vintages only)** |
| Rates | Nominal curve 1M-30Y | Daily Treasury Par Yield Curve | US Treasury | XML/CSV feeds | $0 | **Yes** | Permitted | "Source: U.S. Treasury" | Long | Daily | None documented | Occasional corrections | **MVP** |
| Rates | Real yields (TIPS) | Daily Treasury Par **Real** Yield Curve | US Treasury | XML/CSV | $0 | **Yes** | Permitted | Same | From 2004-01-02 | Daily | None documented | — | **MVP** |
| Rates | Selected rates incl. `DGS*`, `DFII*` | H.15 | Fed Board | FRED / Board | $0 | **Yes — public domain** | Permitted | "Source: Federal Reserve Board"; no seals | Long | Daily | — | — | **MVP** |
| Rates | Policy target range | `DFEDTARU`/`DFEDTARL` | FOMC / Board | FRED | $0 | **Yes — public domain** | Permitted | Board citation | Long | Per meeting | — | — | **MVP** |
| Rates | SOFR, EFFR, OBFR, TGCR, BGCR | Reference rates | **NY Fed** | `markets.newyorkfed.org/api` (keyless) | $0 | **Yes — explicit business-use licence** | Permitted **with 2 required legends** | NY Fed terms legend + non-affiliation legend; DTCC disclaimer travels with SOFR | SOFR from 2018-04-02 | Daily | **Unknown** | **Same-day revision ~2:30pm ET if >1bp** — must re-poll | **MVP** |
| Rates | Breakevens 5Y/10Y, 5y5y, curve spreads | **Computed in-house** (nominal − real; 10Y−2Y; 10Y−3M) | MacroChipz, from Treasury/H.15 | — | $0 | **Yes** (public-domain inputs) | Permitted | Cite Treasury/Board + "calculated by MacroChipz" | Matches inputs | Daily | — | — | **MVP** |
| Rates | Term premium, expected short-rate path | **ACM** | NY Fed | CSV/Excel | $0 | **Yes — business use** | Permitted w/ attribution | NY Fed legend | 1961-present | Daily, **updated weekly** | — | Model re-estimated | **MVP** |
| Expectations | FOMC projections / dot plot | SEP (`FEDTARMD` etc.) | Fed Board | HTML/PDF; FRED medians | $0 | **Yes — public domain** | Permitted | Board citation | Quarterly | 4×/yr | — | — | **MVP (labelled as participants' projections)** |
| Expectations | Consumer inflation expectations | Survey of Consumer Expectations | NY Fed | Excel | $0 | **Yes — business use** | Permitted | NY Fed legend | Monthly | Monthly | — | — | **Later** |
| FX | EUR crosses → USD pairs | Reference rates `EXR` | **ECB** | `data-api.ecb.europa.eu` (keyless) | $0 | **Yes — ESCB reuse policy** | Permitted, **must not misrepresent as unmodified** | "Source: ECB"; state modifications; **tell buyers data is free from ECB** | From 1999-01-04 | Daily T-0/T-1 | None documented | — | **MVP** |
| FX | Broad/AFE/EME dollar indexes | H.10 | Fed Board | DDP / FRED | $0 | **Yes — public domain** | Permitted | Board citation | From 1971 | **Weekly release of daily data (8-10 day lag)** | — | — | **MVP, with lag disclosed** |

### 11.2 Rejected or deferred, with reasons

| Domain | Candidate | Status | Reason |
|---|---|---|---|
| Equities | S&P 500 / Nasdaq-100 / Russell 2000 index levels | **REJECT** | Licensed products; no free commercial tier. "Redistribution, reproduction… prohibited without written permission" (SPDJI); "No further distribution of data… without express written consent" (FTSE Russell). **Delayed data gets no relief**: CTA policy states "the passage of time does not alter the Participants' proprietary interest… Index information is not included". FRED's `SP500` is "Copyrighted: Pre-approval required" — non-commercial only. |
| Equities | Stooq / Yahoo (`yfinance`) free closes | **REJECT** | Express prohibitions. Stooq §5.3: "Redistribution of data found on the website is not allowed without the consent of Stooq" — plus `robots.txt` disallow-all and an anti-bot challenge, so harvesting adds circumvention exposure. Yahoo prohibits automated collection and "exploit for any commercial purposes"; Yahoo is itself a licensee and could not sublicense. |
| Equities | ETF EOD via Alpha Vantage / Tiingo / Finnhub / Massive / EODHD / Alpaca free tiers | **REJECT at $0** | All personal/non-commercial or internal-use-only. Finnhub bars business use even internally and extends the bar to "derived results"; Tiingo's free tier forbids persisting data at all; Massive/EODHD price external display at $2,499/mo. |
| Equities | ETF EOD, paid | **LATER** | Realistic floor: Marketstack Basic **$9.99/mo** (labelled "Commercial Use" — but its governing terms URL now redirects to a generic corporate hub → **UNKNOWN, get written confirmation**), or Twelve Data Business "Venture" **$149/mo** (only provider with a *published* price for external display). |
| Equities | IEX HIST | **REJECT as primary** | The one free affirmative commercial grant found — but IEX-venue-only prints in raw pcap, not a defensible closing price; IEX itself calls it "a reference point only". |
| Crypto | Coinbase / Kraken / Gemini / Binance | **REJECT** | Coinbase bars redistribution **and derived works** and bars creating benchmarks; Kraken bars commercial exploitation; Gemini is personal/internal only; Binance returns HTTP 451 from US egress and its archives are reportedly non-commercial. |
| Crypto | CoinGecko Demo / CoinMarketCap Basic | **LATER** | Commercial use granted, but free history caps at ~365 days; CoinGecko's 24-hour cache-refresh clause may conflict with a permanent store (**UNKNOWN**). |
| Crypto | Bitstamp | **LATER** | The only affirmative grant incl. "the right to create ratios, calculations, new original works, statistics", history to 2011 — **requires a signed Data License Agreement, cost unknown**. |
| Expectations | Release-level economist consensus | **REJECT** | Proprietary everywhere; Trading Economics prices by "the distribution you make" (Enterprise). |
| Expectations | Analyst EPS consensus | **REJECT** | No free commercial source exists. |
| Expectations | CME FedWatch probabilities | **REJECT** | API requires entitlement; website terms are personal/non-commercial; **derived data is separately licensable**, so recomputing and republishing is also barred. |
| Expectations | UMich sentiment | **REJECT** | "You agree not to reproduce, retransmit, distribute, sell, publish, or broadcast the data… without the express written consent of the University of Michigan." |
| Expectations | Philadelphia Fed SPF | **DEFER** | No redistribution grant ("All rights reserved") → **UNKNOWN**; and structurally unsuitable (quarterly, no monthly release series). |
| Expectations | Cleveland Fed expected-inflation decomposition | **DEFER** | **CC BY-SA 4.0** — ShareAlike copyleft; embedding may create an "adapted" dataset. Legal review. |
| Rates/Credit | ICE BofA credit spreads (`BAMLxxx`) | **REJECT** | "Reproduction… prohibited except with prior written permission"; ICE bars distributing EOD index values to third parties. |
| FX | ICE DXY | **REJECT** | "Any use whatsoever of the U.S. Dollar Index, its formulation, components, weightings, values and/or methods of calculation… is strictly prohibited without… express written consent." |

### 11.3 Reading the matrix

**The MVP is possible at $0 — but only for Economy + Rates + FX.** Every capability that needs equities, crypto, or consensus is either paid or prohibited. That is the single most actionable output of this increment.

---

## 12. Requirements Traceability

Each major proposed capability traced end to end. A capability that cannot complete this chain is not in MVP.

### 12.1 "Is the market pricing the same inflation story the data is showing?"

- **User problem:** "I can't tell whether markets are confirming the inflation story."
- **User question:** "Is market-implied inflation compensation moving with realized inflation?"
- **Required data:** Core/headline CPI and PCE; 5Y and 10Y nominal Treasury yields; 5Y and 10Y TIPS real yields.
- **Sources:** BLS (public domain) · BEA (public domain, TOS verify) · Treasury par yield + par real yield curves (public domain) or H.15 `DGS*`/`DFII*` (public domain).
- **Licence/cost:** $0. Attribution: BLS + Treasury/Board.
- **Transformations:** 12-month and annualized 3/6-month rates (existing `inflation_v1.0` machinery); breakeven = nominal − real, **computed in-house**; 5y5y forward via the published formula.
- **Methodology:** a new versioned `confirmation_v1.0` over the pre-registered pair (§16.3), with exact period alignment, latest-revised basis, and `INSUFFICIENT_DATA` when either side is missing.
- **Canonical result:** directional agreement over the aligned window + each side's percentile context. No label beyond agreement/opposition in V1.
- **Evidence:** every observation, each transformation, the methodology version, the vintage, and retrieval timestamps.
- **AI role (post-MVP):** restate the established result in prose. **AI does not determine whether confirmation exists.**

### 12.2 "What changed since I last checked?"

- **Problem:** returning after days away, unable to tell what matters.
- **Data:** everything already ingested.
- **Sources/licence:** as above, $0.
- **Transformations:** none new — this is change detection over stored canonical results.
- **Methodology:** existing salience tiering (`STATE_CHANGED`/`AVAILABILITY_*` above routine metric updates) extended to rates/FX series.
- **Canonical result:** an ordered change list since the user's server-issued watermark (**already shipped**).
- **Evidence:** each change links to before/after observations and the run that detected them.
- **AI role:** summarize; never rank (salience is canonical).

### 12.3 "How unusual is this?"

- **Problem:** a number without a scale is not information.
- **Data:** the full stored history of the series.
- **Transformations:** rolling percentile/rank over an explicit window; occurrence counts; duration.
- **Methodology:** deterministic counting; the window is declared, never implied.
- **Canonical result:** "larger than N% of k-session moves since YYYY", with window and observation count shown.
- **AI role:** none needed.

### 12.4 "Did a revision change the answer?" — the §8.2 wedge

- **Problem:** the signal moved because the past was rewritten, and no product says so.
- **Data:** ALFRED vintages plus the product's own recorded results.
- **Sources/licence:** FRED/ALFRED for vintages — **amber** (§10.2), so the product's *own* append-only history is the primary record and ALFRED is corroboration.
- **Transformations:** re-evaluate the methodology on the prior vintage and on the current one; diff the outcomes.
- **Methodology:** versioned; must state that a reconstruction is not a real-time record (the discipline already shipped with State Duration).
- **Canonical result:** "the print you saw was X; it is now Y; the state changed/did not change as a result."
- **Evidence:** both vintages, both evaluations, both timestamps.
- **AI role:** explain, never re-evaluate.

### 12.5 A capability that fails traceability, shown deliberately

- **Question:** "Are equities confirming the labor story?"
- **Required data:** broad equity index or ETF closes.
- **Licence:** index levels **prohibited**; ETF closes **not available at $0** (§11.2).
- **Methodology:** would be Class C/E cross-concept inference — **prohibited** by the frozen boundary (§16.1) and not deterministic.
- **Result: rejected on two independent grounds — data licensing and methodology.** It does not enter MVP, and would not even if the data were free.

---

## 13. Deterministic Intelligence Model

### 13.1 The candidate pipeline, challenged stage by stage

The proposed pipeline was: source → normalization → transformations → domain states → change detection → historical context → cross-market relationships → confirmation/divergence → evidence graph → optional AI.

| Stage | Verdict for MVP | Why |
|---|---|---|
| Source ingestion | **Required** | Already built for FRED; extends to Treasury/BLS/NY Fed. |
| Normalization | **Required, and bigger than it looks** | Daily market data and monthly economic data do not share a calendar. This is the stage where most incorrect cross-market claims are actually born (§16.4). |
| Transformations | **Required** | Already built and pure (`app/domain/transformations.py`). |
| Domain states | **Only where justifiable** | See §13.2 — states are appropriate for economy, questionable for markets. |
| Change detection | **Required — the core of the product** | Already built for Inflation/Labor. |
| Historical context | **Required** | The cheapest high-value addition (§17). |
| Cross-market relationships | **Narrowed to same-concept pairs** | §16. |
| Confirmation / divergence | **Only for pre-registered same-concept pairs** | §16. |
| Evidence | **Required** | Already built; relational, not a graph (§18). |
| AI explanation | **Optional, non-blocking, post-MVP** | §15. |

### 13.2 Domain states: where the existing model transfers and where it must not be forced

The Inflation/Labor state model (`COOLING`/`STABLE`/`HEATING`/`MIXED`/`INSUFFICIENT_DATA`) works because the underlying methodology defines a *neutral band* against which a reading is classified, and because monthly economic data has a natural evaluation period.

Applying the same shape to markets would require inventing thresholds. This repository already carries a warning about that: `inflation_v1.0`'s neutral band (0.10pp) and `labor_v1.0`'s deadbands (50,000 jobs; 0.2pp) are **frozen constants asserted by the methodology, not empirically derived** — defensible for a monthly economic aggregate whose noise scale is well understood, and much less defensible for a daily market series whose volatility varies by regime.

**Recommendation:** do not create `EQUITY_STATE` or `RATES_STATE` labels in MVP.

- For market series, **report the change and its historical percentile** rather than classify it. "The 10Y breakeven rose 12bp over 5 sessions — larger than 94% of 5-session moves since 2003" is deterministic, needs no invented threshold, and is more informative than a label.
- A label is only justified where a *published external definition* supplies the boundary (e.g. the FOMC's own target range; a curve inversion at exactly zero). Inversion is the one honest market "state" because the threshold is definitional, not chosen.

This is a real finding, not a stylistic preference: **percentiles replace thresholds**, and it removes the single largest methodology risk in the market domains.

---

## 14. Probabilistic Analysis Boundary

**MVP contains no probabilistic layer.** No forecasts, no ML, no anomaly models, no similarity/analog models, no regime classifiers.

Reasons, in order of weight:

1. Nothing in §5's ranked jobs requires it. The top four jobs are all deterministic.
2. A probabilistic layer done honestly requires model versioning, backtesting, calibration, and published performance history — a large increment of work with no MVP payoff.
3. A probabilistic layer done dishonestly (a forecast with no track record) is exactly the credibility failure the product's whole design exists to avoid.

**If it is ever added**, the required disclosures are fixed in advance: model version, training/evaluation window, out-of-sample methodology, uncertainty intervals, calibration record, and a permanently visible performance history. It must live in a structurally separate module that canonical results never import — the same discipline `app/domain/` already enforces against I/O.

**The line, stated precisely:** counting is deterministic; predicting is probabilistic. "This configuration has occurred 14 times since 2003" is canonical. "This configuration implies a 60% chance of X" is a model, and is out of scope.

---

## 15. Generative AI Boundary

AI is **not in MVP** and the product must be fully useful without it. When added, the permitted jobs are narrow.

| Capability | Input | Output | Deterministic boundary |
|---|---|---|---|
| Explain | A canonical result object + its evidence | Prose restating that result | May not recompute, reinterpret, or add a conclusion |
| Summarize | A set of already-detected changes | Prose summary | May not rank, weight, or judge significance — salience is canonical |
| Q&A over evidence | User question + retrieved canonical objects | Answer citing those objects | May not answer beyond retrieved evidence; must refuse instead |
| NL → structured query | User text | A **validated** query schema | Query executes deterministically; invalid schema is rejected, never "best-guessed" |

**Hard rules** (extending ADR-014, ADR-016, ADR-021, already accepted in this repository):

- AI never creates a canonical state, never calculates a financial value, never decides confirmation/divergence, never modifies evidence or provenance, never triggers ingestion, and never gates availability.
- Every AI surface must degrade to the canonical view on failure or timeout. AI failure is never an outage.
- AI output is visually labeled as interpretation, never presented in the same typographic register as a canonical number.
- No autonomous action of any kind. No trading, no orders, no alerts that imply advice.

**Containment and evaluation:** a fixed regression set of (result object → expected claim set) pairs; any AI sentence asserting a number absent from the evidence object fails. This is testable in CI and is the only way the boundary stays real.

---

## 16. Confirmation / Divergence Methodology

This is the proposed core capability and it needs the most scrutiny of anything in this document.

### 16.1 The existing frozen boundary (not reopened)

`relate-compare-audit-v1.md` §11 already classifies relationship types, and `relate-composition-v1.md` §2 already **prohibits** the words "confirms", "diverges", "contradicts" (and every regime name) for *cross-domain* claims, because combining two canonical facts into a relationship claim is inference, not composition.

| Class | Example | Status |
|---|---|---|
| A. Same-concept confirmation | Core CPI vs Core PCE | **Shipped, canonical** |
| B. Within-domain component | Employment vs Unemployment | **Shipped** (`combine_labor_state`) |
| C. Cross-domain state relationship | Inflation vs Labor | Composition only; labeling **frozen out** |
| D. Statistical series relationship | Correlation | Later; needs a statistical contract |
| E. Lead/lag | "Does labor lead inflation?" | Out of scope |
| F. Historical outcome | "What happens after divergence?" | Out of scope |

### 16.2 Where cross-market comparison legitimately fits

The insight that makes this tractable: **"market vs data" is Class A, not Class C.**

Core CPI vs Core PCE is already canonical *because both measure the same concept by different construction*. A breakeven rate and a realized CPI rate are likewise two measurements of one concept — inflation — one implied by traded instruments, one observed by a statistical agency. Comparing them is the same operation the product already performs and defends.

By contrast, "equities are confirming the labor story" compares two *different* concepts and is Class C/E. It stays prohibited.

### 16.3 The pre-registered pair registry

Confirmation is only computed for pairs declared in advance in a versioned registry — never discovered by scanning for correlations. Each entry fixes: the concept; measure A and measure B; alignment rule; comparison window; and the methodology version.

Candidate MVP pairs (all inputs public-domain — see §10):

| Concept | Measure A (data) | Measure B (market-implied) | Notes |
|---|---|---|---|
| Inflation | Realized CPI / PCE 12M rate | 5Y/10Y breakeven (computed in-house from nominal − real yields) | Breakeven ≠ forecast; see §16.6 |
| Policy path | FOMC target range (published) | Treasury curve slope / short-end shape | Definitional threshold available (inversion at 0) |
| Growth/labor | Labor state (shipped) | Curve inversion state | **Candidate only** — this is Class C and is therefore reportable side-by-side but NOT labeled as confirmation |

The third row is deliberately included to show the line: it is displayed, never labeled.

**One capability is removed by licensing, not by methodology:** meeting-dated policy probabilities (FedWatch-style) cannot be shown or recomputed-and-republished at $0 (§10.6). The policy-path pair therefore compares the FOMC's published target range and SEP medians against the *shape of the public-domain Treasury curve* and the NY Fed's ACM expected-short-rate path — never against a probability distribution we are not licensed to derive.

### 16.4 Alignment — where wrong answers actually come from

Monthly economic data and daily market data do not share a calendar, and economic data is revised. The methodology must fix, in advance:

- **Period alignment.** A monthly observation is compared to the market measure *as of the same reference period*, using exact calendar alignment — the discipline `inflation_v1.0` already enforces (exact month lookup, never row position, never interpolation).
- **Revision awareness.** Realized data revises; market prices do not. Comparisons use the latest-revised vintage and say so, exactly as the shipped "Latest revised data" disclosure already does. ALFRED vintages make a point-in-time version possible later.
- **Missing data is not zero.** If either side is unavailable for the aligned period, the result is `INSUFFICIENT_DATA` — never a partial comparison, matching the existing methodologies' "no best-effort fallback" rule.
- **Asynchronous release timing.** A market can move *because* of a release published mid-window. The methodology must not silently attribute the move; it reports the two measures, not a cause.

### 16.5 Defining the comparison without inventing thresholds

Preferred formulation, in order of defensibility:

1. **Directional agreement over an aligned window** (both rose / both fell / opposed). Sign is definitional; no threshold invented.
2. **Magnitude context by percentile**, not by a chosen cutoff: how unusual each move is against its own history.
3. **A `DIVERGES` label only when the two directions are opposed AND both moves clear their own historical noise band expressed as a percentile** — with the percentile cutoff itself declared as a frozen methodology constant and labeled as a product convention, not an economic fact.

The third form is where the product would be adding an opinion, and §26 recommends shipping only forms 1 and 2 first.

### 16.6 Language discipline

- A breakeven is **market-implied inflation compensation**, not a forecast and not "consensus". It embeds an inflation risk premium and a liquidity premium.
- Curve-implied policy expectations are **implied by prices**, not "what the market thinks will happen."
- Never "the market disagrees with the Fed"; instead "the 10Y breakeven is X while realized 12M CPI is Y, as of period P."
- No causal verbs anywhere: never "because", never "driven by", never "in response to".

### 16.7 Verdict

Confirmation/divergence **can** be canonical deterministic intelligence, but only in the narrow same-concept form, only over pre-registered pairs, only with exact alignment and honest missing-data behavior, and only with directional/percentile framing rather than invented magnitude thresholds. Anything broader is probabilistic and out of scope.

---

## 17. Historical Context

All of the following are deterministic counting operations over stored observations, and all are cheap once the data is persisted:

| Capability | Statement form | Canonical? |
|---|---|---|
| Percentile / rank | "Larger than 94% of 5-session moves since 2003" | Yes |
| Rolling distribution | "Current value vs its 1/5/10-year distribution" | Yes |
| Prior occurrences | "This configuration has occurred 14 times since 2003" | Yes |
| Duration | "Mixed for 2 consecutive months" | Yes — **already shipped** (State Duration) |
| Magnitude | "The largest 1-month change since 2022" | Yes |
| Drawdown | "12% below its trailing peak" | Yes |
| "Historically this leads to…" | — | **No — probabilistic, prohibited** |

Required disclosures for every historical claim: the exact window, the observation count, and the data vintage. A percentile computed over a short window is a different claim from one computed over 20 years, and the UI must never let those look identical.

The existing State Duration contract already solved the hardest honesty problem here — it labels its output a *latest-revised reconstruction*, not what the product said in real time. Every new historical claim inherits that discipline.

---

## 18. Evidence Architecture

**Recommendation: relational, not a graph. Do not build a graph database.**

The evidence structure this product needs is a shallow, fixed-shape lineage:

```
conclusion → methodology version → transformed metrics → observations → source + vintage + retrieval timestamp
```

That is four or five joins with a known shape, and the repository already implements it (evidence disclosures, `RecordedMonitorResult`, release-processing audit rows). A graph abstraction would add operational cost and a second storage technology to express a structure PostgreSQL already models well.

**What does need strengthening for multi-source data:** a single `source_attribution` record per observation capturing provider, dataset/series identifier, retrieval timestamp, vintage, licence class, and required attribution string. This matters for correctness *and* for compliance — §10 shows different sources carry different display obligations, and the UI must be able to render the right legend for whatever is on screen.

Revisit a graph only if relationship types become user-definable. They are not, and §16 says they must not be.

---

## 19. MVP Proposal

**This section describes the only MVP the data supports. Whether it should be built at all is §26 — and the answer there is "not yet".**

### 19.1 The one coherent user problem

> *"I follow the economy and rates. I cannot tell, without assembling four sources by hand, whether what markets are pricing has moved with the data — or whether what I remember was quietly revised."*

### 19.2 MUST HAVE

| # | Capability | Why | Built on |
|---|---|---|---|
| 1 | **Economy states** (Inflation, Labor) | Already shipped, already tested | Existing |
| 2 | **Rates panel**: full Treasury curve, real yields, policy range, SOFR/EFFR, curve spreads | 100% public domain; the densest free domain available | New ingestion |
| 3 | **Market-implied inflation compensation**, computed in-house | The other half of the one legitimate confirmation pair | Derived |
| 4 | **Same-concept confirmation**, one pair: realized inflation vs inflation compensation | The only cross-market comparison that is canonical (§16.2) | New `confirmation_v1.0` |
| 5 | **Historical context** on every figure: percentile, window, observation count | Turns a number into information, with no invented thresholds | Deterministic |
| 6 | **Since Last Visit across all of the above** | The strongest retention loop, already built | Existing |
| 7 | **Evidence on every conclusion**, incl. source, vintage, retrieval time | The trust model; also the licence-attribution mechanism | Existing + `source_attribution` |
| 8 | **Revision awareness**: what changed because data was revised | The only differentiator found (§8.2) | New, on existing foundations |

Useful without AI: **yes — there is no AI in it.**

### 19.3 LATER

FX panel (cheap, licensed, but thin) · NY Fed consumer expectations · ACM term premium · point-in-time replay of any past date · equities via paid ETF feed ($10-149/mo) · crypto via Bitstamp DLA · AI explain/summarize/Q&A · weekly digest email.

### 19.4 REJECT / OUT OF SCOPE

Release-level consensus (unobtainable) · FedWatch-style policy probabilities (licence-blocked) · index levels by name (prohibited) · UMich series (prohibited) · ICE BofA credit spreads and DXY (prohibited) · cross-concept "equities confirm labor" claims (methodologically prohibited) · every §20 non-goal.

### 19.5 What this MVP is *not*

It is not five domains, it has no consensus column, no probabilities, no AI, and no equities. **It is a rates-and-inflation intelligence product with a memory and a conscience.** That is a much smaller claim than "cross-market intelligence for serious investors" — and it is the claim the evidence supports.

---

## 20. Explicit Non-Goals

Permanent, not "later":

- Trading, execution, brokerage, order routing, portfolio management.
- Buy/sell recommendations, price targets, position sizing, "what should I do" answers.
- Security selection / full-universe screening.
- AI stock picking, AI trading bots, autonomous financial action.
- Black-box prediction presented as fact.
- Real-time tick data, streaming quotes, intraday terminal.
- Bloomberg/Koyfin/TradingView imitation.
- Social/sentiment feeds, news aggregation as a primary surface.

Deferred but legitimate later: probabilistic layer (§14), AI layer (§15), Class D statistical relationships, additional economic domains, point-in-time (vintage) replay.

**Regulatory posture:** the product describes what data and markets did. It does not advise. Every surface avoids recommendation language, and the distinction is enforced in copy review the same way the existing prohibited-vocabulary rules already are.

---

## 21. Monetization Hypotheses

### 21.1 Why would anyone pay? — the honest answers

"Lots of data" is not an answer; data is free and abundant (§7). The only defensible value dimensions, ranked by the evidence:

| Dimension | Would someone pay? | Evidence |
|---|---|---|
| **Synthesis + regime read** | Yes — demonstrably | 42 Macro at $55-165/mo, ORCA at $29-120/mo exist and sell |
| **Monitoring / change detection** | Weakly | FRED alerts are free; TradingView gives 20 alerts at $12.95 |
| **Historical context** | Possibly | Bundled into ORCA/Glassnode, never sold standalone |
| **Point-in-time correctness** | **Untested** | No competitor sells it; no evidence anyone has asked for it |
| **Evidence / provenance** | As a trust multiplier, not a purchase reason | LSEG and MacroMicro treat it as table stakes |
| **Fewer tabs** | Marginal | Koyfin's ~$7M-over-a-decade outcome bounds this |

**The uncomfortable synthesis:** the two dimensions people demonstrably pay for (synthesis, regime) are exactly the two where incumbents are strongest, and the dimension where MacroChipz would be unique (point-in-time correctness) has **zero demonstrated willingness to pay**. That is the core commercial problem, and it is not solvable by building more.

### 21.2 Pricing hypotheses (explicitly not decisions)

- **Free tier:** current states, latest changes, evidence. Everything a casual reader needs. Purpose is credibility and search presence, not conversion.
- **Paid hypothesis A — "$12-25/mo consumer":** competes directly on the most crowded shelf against free substitutes. **Weakest option**; recommended against.
- **Paid hypothesis B — "$50-80/mo serious":** matches the demonstrated willingness to pay of subsegment A, but must beat 42 Macro/ORCA on substance, which §7 says we do not today.
- **Paid hypothesis C — "$100-300/mo professional-adjacent":** subsegment C (people who must defend a conclusion), sold on point-in-time defensibility and exportable evidence. **Smallest audience, best match to the one real differentiator, least competitive pressure.**

**Speculation vs evidence, marked plainly:** the *existence* of paying customers at $29-165/mo is evidence (published prices, live products). Everything about what MacroChipz specifically could charge is **speculation** until §25's validation runs. No pricing decision is made in this increment.

---

## 22. Habit / Retention

Candidate loops, ranked by fit with what the product actually does well:

| Loop | Trigger | Strength |
|---|---|---|
| **Since Last Visit** | Any return visit | **Strongest** — already built, and it is the only loop that works regardless of whether anything happened |
| Release-day check | Scheduled release (CPI, payrolls) | **Strong** — dates are known in advance and the calendar is already built. Note: the frame must be "actual vs prior / vs 3-month average / vs market-implied", **never "actual vs consensus"** — consensus is unobtainable at $0 (§10.6) |
| Weekly macro review | Weekend habit | Moderate — a weekly digest is cheap to derive from the same change feed |
| Morning check | Daily | Weak for this product — daily macro change is usually nil, and forcing daily content invites noise |
| Big-move investigation | Market event | Moderate, but event-driven and unpredictable |

**Finding:** the retention loop should be *release-anchored*, not daily. This product's honest cadence is "a few times a week, and hard on release days." Designing for daily engagement would require manufacturing significance — the exact failure the salience work already rejected.

---

## 23. Risks

### 23.1 Data, licensing and operational risks (from §10-§11)

| Risk | Severity | Detail / mitigation |
|---|---|---|
| **Shipping on prohibited data** | **Critical** | Stooq/Yahoo/index levels/UMich/FedWatch are express written prohibitions, not grey areas, and rights-holders audit downstream commercial users. Mitigation: the §11.1 allow-list is the only permitted source set; every new series passes a licence check before ingestion. |
| **FRED "replicate the essential user experience" clause** | **High** | A FRED-browsing product is exposed. Mitigation: source public-domain data direct from BLS/Board/Treasury; use FRED/ALFRED for vintages and backfill only. |
| **FRED per-user API key clause** | **Medium-High** | "Individual users of an application must use their own API key" conflicts with multi-tenant SaaS. **UNKNOWN** — written clarification required. Mitigated by the same direct-sourcing decision. |
| **BEA TOS unread** | **Medium** | The TOS is a PDF that could not be machine-read and BEA does not assert public-domain status. Must be read before launch. |
| **ECB "free elsewhere" notice** | **Medium** | A paid product may have to tell buyers before payment and at each access that the data is free from the ECB. Whether it binds SaaS is **UNKNOWN** (legal review). |
| **NY Fed indemnification** | **Medium** | The rates licence carries an indemnity obligation and two mandatory legends. Accept knowingly or drop the SOFR family. |
| **Cleveland Fed CC BY-SA copyleft** | **Medium** | ShareAlike may force same-licence release of an "adapted" dataset. Defer until reviewed. |
| **BLS 500 queries/day** | **Medium** | Binding at scale. Server-side cache; never proxy user requests 1:1. |
| **Source fragility / no SLA** | **Medium** | No source publishes an SLA; the Fed's DDP is being retired; Treasury feeds are historically flaky. Mitigation: persist everything locally; never depend on a live upstream call to render. |
| **SOFR same-day revision** | **Low-Medium** | Revised ~2:30pm ET when >1bp. Ingestion must re-poll or publish a wrong value. |
| **Attribution drift** | **Low-Medium** | Different sources carry different obligations; the UI must render the right legend per figure — hence `source_attribution` in §18. |
| **Equities/crypto cost creep** | **Medium** | Adding equities honestly costs $10-149/mo and adds vendor-tier audit risk; crypto needs a signed DLA of unknown cost. |

### 23.2 Commercial risks (from §7)

| Risk | Severity | Detail |
|---|---|---|
| **Weak differentiation** | **Critical** | Three of four thesis pillars ship together in ORCA at $29-35/mo; the free floor answers the core question at $0. |
| **Incumbent bundling** | **High** | MacroMicro is adding AI traceability free to existing subscribers. |
| **Flat segment** | **High** | New-investor inflow fell 21% → 8% (FINRA 2024); dominant research channels are free. |
| **Crowded price band** | **High** | 14+ products in $8-50; the real buyer already pays $55-165 elsewhere. |
| **No distribution** | **High** | Competitors have audiences, newsletters and funds; we have none. |
| **Inability to monetize the one differentiator** | **High** | Point-in-time correctness has zero demonstrated willingness to pay. |

### 23.3 Product and methodology risks, independent of data findings

| Risk | Severity | Mitigation |
|---|---|---|
| Incorrect causal inference | **High** | §16.6 language discipline; no causal verbs; automated prohibited-vocabulary tests, which this repo already runs |
| Arbitrary methodology / invented thresholds | **High** | §13.2 percentiles-not-thresholds; every constant frozen and justified in writing |
| Misleading financial conclusions | **High** | §20 non-goals; no advice language; evidence always reachable |
| Users expecting predictions | **Medium-High** | Explicit positioning; refuse in-product; never ship a "forecast" surface without §14's disclosures |
| Scope explosion across five domains | **High** | §19's narrow MVP |
| Weak differentiation | **High** | §8 — must be answered by research, not assertion |
| AI hallucination | Medium (zero in MVP) | §15 containment; AI not in MVP at all |
| Revision handling errors | Medium | Latest-revised discipline already shipped; vintages available via ALFRED |
| Methodology overfitting | Medium | No fitting in MVP — nothing is estimated |

---

## 24. Open Questions

### 24.1 Licensing — must be resolved in writing before any build (each is an email)

1. **FRED** (research.data@stlouisfed.org): does a paid subscription web product count as a "report to clients" under the *Copyrighted: Citation required* grant? And does the per-user-API-key clause bar a multi-tenant application?
2. **BEA**: read `apps.bea.gov/API/_pdf/bea_api_tos.pdf` in a browser; confirm commercial redistribution and whether BEA asserts public-domain status.
3. **ECB**: does the "inform buyers the data is free" clause attach to a SaaS subscription rather than "documents that are sold"?
4. **NY Fed**: rate limits for the markets API; confirm the exact required legends for a web product.
5. **Philadelphia Fed** (PHIL.SPF@phil.frb.org): may SPF series be redistributed in a commercial product?
6. **Cleveland Fed / legal review**: does embedding CC BY-SA 4.0 series create an "adapted" dataset requiring same-licence release?
7. **Treasury**: does the Fiscal Data open-licence statement extend to the `home.treasury.gov` yield-curve XML feeds?
8. **Atlanta Fed**: GDPNow licence — no terms page renders.
9. *(If equities are ever added)* apilayer/Marketstack: written confirmation of commercial display rights, storage rights, and exchange-fee passthrough — its terms URL now redirects to a generic corporate hub. And CTA Administration: does the $1,000/mo redistribution charge attach to an EOD-only web product?
10. *(If crypto is ever added)* Bitstamp (partners@bitstamp.net): Data License Agreement cost and terms.

### 24.2 Product questions the research could not answer

11. Does anyone actually *want* revision-awareness, or is it a virtue only its author admires? (§25 step 4 tests this.)
12. Is subsegment C (people who must defend a conclusion) reachable without a sales motion?
13. Is there a wedge in **being a data layer** rather than an app — a licensed-clean, revision-aware macro API for the many builders assembling these dashboards — given how many free dashboards now exist?
14. Would the honest answer be to publish the analysis as a free/low-cost newsletter, where macro has demonstrated willingness to pay, rather than as software?
15. Does the existing deterministic engine have value independent of MacroChipz — as a portfolio artifact, or as open source?

### 24.3 Methodology questions deferred

16. If a `DIVERGES` label is ever introduced, what percentile cutoff, and on what published basis?
17. How should a point-in-time replay treat a methodology version change, as distinct from a data revision?

---

## 25. Product Validation Plan

Before any further engineering beyond MVP, the thesis needs evidence from outside this repository.

1. **Written licensing confirmations** for every source marked UNKNOWN in §11 — these are emails, not opinions, and they gate the build.
2. **Problem interviews (10-15)** with the ICP defined in §4, testing one specific claim: that "the data and the market are telling different stories" is a question they actually ask, and what they do today to answer it.
3. **A landing-page test** of the revised thesis (§2.3) against the original broad framing, measuring signup intent, not traffic.
4. **A manual concierge run:** produce the weekly "what changed and what is the market pricing" brief by hand for 4-6 weeks, for real readers. If it is not useful by hand, no amount of engineering saves it.
5. **A willingness-to-pay probe** only after (4) shows repeat readership.

The order matters: (1) and (4) can each kill the project cheaply, so they come first.

---

## 26. Recommendation

### 26.1 The decision

The question this increment had to answer was: *is there a commercially useful product between fragmented free retail information and expensive professional systems, centered on cross-market change, confirmation, divergence, historical context and evidence?*

**On the evidence gathered: not as currently framed.** Three of the four pillars ship together today in a product priced inside the intended band; the fourth (evidence/traceability) is being bundled free by an incumbent with more data and more users; the core question is answered for $0 by a hobbyist site; two of the five domains cannot be licensed at $0 at all; and the "expected vs actual" frame that anchors most competitors is legally unavailable to us.

I am explicitly not choosing GO because eight increments of good engineering already exist. The engineering is genuinely good — deterministic, tested, revision-aware, honest about missing data. **None of that is evidence of demand**, and this increment found no evidence of demand for the one thing that engineering uniquely enables.

### 26.2 What would change the decision

Each of these is cheap, none requires code, and any of them could flip this to a CONDITIONAL GO:

1. **The concierge test (§25 step 4).** Hand-produce the weekly "what changed in the data, what changed in what markets are pricing, and what a revision quietly moved" brief for 4-6 weeks with real readers. If readers return and ask for it when it is late, the demand is real.
2. **Evidence that revision-awareness is wanted**, not merely admirable — from §25 step 2 interviews, testing the specific question "have you ever been wrong because the data was revised?"
3. **A reachable subsegment C** (people who must defend a conclusion to someone else) at $100-300/mo, where the differentiator is defensibility rather than insight.
4. **Licensing answers** (§24.1) that keep the $0 spine intact — particularly FRED, BEA and ECB.

If steps 1 and 2 fail, the honest conclusion is that this should remain an engineering portfolio project and a personal tool, and that conclusion should be accepted without a further increment of building.

### 26.3 If it proceeds anyway

Build §19's MVP exactly — Economy + Rates + FX, one confirmation pair, percentiles instead of invented thresholds, no consensus, no equities, no crypto, no AI — and price it at the level the target customer already demonstrably pays, not below it. Do not build five domains. Do not ship an "Expected" column. Do not name an index.

### 26.4 What #28 changes about the existing work

Nothing needs to be thrown away, and nothing should be built on yet. The deterministic engine, the revision-aware pipeline, the evidence model and the design system all remain sound and all remain useful under the narrowed thesis. The SRS rewrite and any architecture redesign should wait for §25's results, not for this document.

---

**FINAL DECISION**

**NO-GO — CURRENT PRODUCT THESIS IS NOT SUPPORTED**

The five-domain cross-market intelligence thesis, at $10-50/month, for serious self-directed investors, is not supported by the data-licensing research (two domains unlicensable at $0, consensus unobtainable) or by the competitive research (the thesis is already shipped at or below the target price, with a free floor beneath it and incumbents bundling the differentiator).

A narrower thesis — **revision-aware, evidence-first inflation-and-rates intelligence** — survives the feasibility analysis and is technically buildable at $0 today. It is **not yet validated as a business**, and §25 is how that gets decided before any further engineering.
