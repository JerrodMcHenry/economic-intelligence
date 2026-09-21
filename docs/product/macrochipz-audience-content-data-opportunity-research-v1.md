# MacroChipz — Audience, Content, Data & Product Feasibility Research V1

**Increment #35.** Research and product definition only. No production code was written, no application behaviour was modified, nothing was deployed, nothing was committed or pushed, and no secret value or `.env` content was read, printed or altered. All retrieval dates are **2026-09-20** unless stated otherwise.

This document exists to answer one question: **what version of MacroChipz deserves to be built?** It was written under an explicit instruction to try to disprove the thesis, and it does disprove substantial parts of it. Where the evidence kills a favourite idea, the document says so plainly rather than softening it.

**Evidence labelling used throughout:**

- **[MEASURED]** — computed by this session directly against the MacroChipz repository, database, or a public API. Reproducible.
- **[VERIFIED]** — read from the primary/official source's own domain, with URL and retrieval date.
- **[LIKELY]** — a reasonable interpretation of a verified source, or a long-standing fact not re-fetched this session.
- **[UNKNOWN — REQUIRES CONFIRMATION]** — could not be established from an authoritative source. Not guessed.
- **[A] / [B] / [C]** — for audience and market evidence: **[A]** primary survey, study, or own computation; **[B]** credible media or trade reporting; **[C]** vendor or marketing content.

This document does not provide legal advice. Clauses marked **⚖️** need a lawyer's eyes before launch.

---

## 1. Executive Summary

**The MacroChipz 2.0 thesis is half right, and the half that is wrong is the half the current product plan is built on.**

Seven findings drive everything below.

**1. The daily product is arithmetically impossible, and the audience data independently agrees.** Only **60 of ~252 business days in 2026 (23.8%) have any curated economic release at all** [MEASURED, §7.1]. Independently, a measurement of actual public attention found that **"inflation" shows a 1.11× lift on CPI release day against a 1.08× placebo — i.e. no detectable event response whatsoever** [A, §9.1]. The terms that *do* spike — "FOMC," "consumer price index" — are jargon with tiny audiences and a 72-hour decay. A daily brief, a daily video, and a "Today in the Economy" live timeline are all unsupported by the data and by the demand. (§7, §9)

**2. The Economic Pulse is a commodity, and it is already occupied by people with email lists.** The Chicago Fed's CFNAI has collapsed 85 indicators into one number *since 2001*. Free consumer products doing exactly this ship today: **recessiondashboard.com** (a "Recession Score" of 51/100, plain-English change notes, a newsletter), **RecessionPulse** (50 indicators, a free daily email, an AI composite, SMS alerts at $6.99/mo). **fredecondashboard.com's own pitch is essentially MacroChipz's positioning statement, already written by someone else.** A normal person cannot tell these apart from the proposed Pulse. (§8.3)

**3. Radar can be honest or frequent. It cannot be both. This is arithmetic, not opinion.** On MacroChipz's own data, a 2σ bar yields roughly **one "unusual" reading per series every two years** [MEASURED, §13.1]. Scale that to a scan and the picture is damning: a 600-test monthly scan at |z|>2 produces **27 false findings per month and 328 per year** with no real signal present [§13.2]. Worse, the flagship Radar example — *"payroll growth is weakening while the headline unemployment rate remains relatively stable"* — **is a statistical artifact.** Fed staff estimate breakeven employment growth has fallen from ~155k/month (2023-24) to near zero in 2026; falling payrolls with a flat unemployment rate is the *expected arithmetic consequence* of slowing labour-force growth, not a hidden signal [VERIFIED, §13.5]. Radar as specified would manufacture exactly the false narratives the brief asked us to guard against.

**4. Social video sends essentially no traffic to websites, and search is collapsing underneath us.** Chartbeat across ~3,750 publisher sites puts **YouTube, Instagram, TikTok, LinkedIn, Threads and Reddit each below 0.5%** of publisher referrals [B, §10.1]. Google organic referrals to 2,576 publisher sites fell **33% globally and 38% in the US** year-on-year to Nov 2025 [B]. Pew's browsing-data study (n=900, 68,879 searches) found users clicked a traditional result in **8% of visits with an AI Overview vs 15% without**, and clicked links *inside* the AI summary **1%** of the time [A]. **Every channel in the acquisition plan except email sits in the "<0.5%" row or is in structural decline.** (§10)

**5. A well-funded, near-identical product died two months ago.** Robinhood shut **Sherwood News** on 2026-07-13, ~2 years after launch — free, ad-supported, no paywall, ~36 staff hired from FiveThirtyEight, Business Insider and Bloomberg [B]. This session independently confirmed the shutdown from the infrastructure: sitemap article counts went **193 in June 2026 → 6 in July → 1 in August → 0 since**, while Robinhood Snacks (the newsletter) still ships daily [MEASURED, §8.6]. The read is unambiguous: the *newsletter* survived and the *destination site* did not.

**6. Exactly one proposed feature is genuinely empty, and it is empty despite a demand shock that should have filled it.** Revision tracking has **zero products**. The most consumer-facing artifact anywhere is a static SF Fed research chart. Candidate domains (revisions.watch, datarevisions.com, jobsrevised.com, truejobsnumber.com and five more) have **no A records — all unregistered**. GitHub has 7 repos at 0–1 stars. And the demand shock already fired: a **−911,000** preliminary benchmark revision, a fired BLS commissioner, a data blackout, a year of "can we trust the numbers" coverage — and the market's entire answer was op-eds and two Fed research pages. (§8.2)

**7. The single best-evidenced consumer misconception in the entire research set is about mortgage rates.** **66% of prospective homebuyers think the Federal Reserve sets mortgage rates outright; 61% believe the government dictates lender rates; 63% think rates are at their highest point ever** [B, n=400, §5.4]. This lands exactly on top of the highest-intent, cleanest-keyword topic found anywhere in the search analysis ("how does the fed affect mortgage rates"). And two of the largest free plain-English housing-economics explainers — **Fannie Mae's Home Purchase Sentiment Index and Freddie Mac's economic outlook — both stopped publishing within the last 19 months** [B, §9.4]. That is a dated, concrete supply vacuum.

### The recommendation

**Kill the daily product. Kill Radar as a content engine. Kill the Pulse as a differentiator. Build the thing nobody has built, for the audience whose misconception is measured, on the infrastructure that does not yet exist.**

Day-1 MacroChipz 2.0 is a **revision-aware, evidence-first explainer of the two things people measurably get wrong — what the data actually said, and what actually moves their mortgage rate — distributed newsletter-first, on a release-driven cadence, with the deterministic engine as the credibility spine rather than the product surface.** Full scope in §21.

**One hard blocker precedes all of it: MacroChipz currently has zero distribution infrastructure.** No Open Graph tags, no meta description, no sitemap, no robots.txt, no analytics, no email capture [MEASURED, §10.7]. Every shared link renders as a bare URL, and **we cannot measure a single behaviour the thesis depends on.** No experiment in §20 can run until that is fixed. It is roughly a week of work and it must come first.

**Operating cost is not a constraint.** A production configuration with real backups is **$27.92/month**; a floor configuration is **$14.92/month**; the Analyst costs **$0.38 per 1,000 requests** and does not become the dominant cost until ~40,000 requests/month [VERIFIED, §16].

---

## 2. Product Thesis Being Tested

### 2.1 The thesis as stated

> MacroChipz should make the U.S. economy feel like a living system that ordinary people can see changing — free, no login wall, acquired through social video and search, monetised eventually through sponsorship, powered by one deterministic intelligence engine feeding many distribution surfaces.

With the behavioural framework **WOW → UNDERSTAND → EXPLORE → SHARE → RETURN**.

### 2.2 The five sub-claims this research tested

| # | Sub-claim | Verdict |
|---|---|---|
| T1 | There is enough economic activity to make the economy feel *alive daily* | **FALSE.** 23.8% of business days have a release; attention to consumer-facing terms shows no event response at all. (§7.1, §9.1) |
| T2 | A visual "economy right now" overview is a WOW feature | **FALSE.** Commodity. At least five free products ship it, one since 2001. (§8.3) |
| T3 | Automated detection of unusual patterns can be a signature proprietary product | **PARTIALLY FALSE.** Statistically honest detection is possible but rare by construction; the specified flagship example is an artifact. It cannot be a content engine. (§13) |
| T4 | Social video and search will feed users into the website | **FALSE as stated.** <0.5% referral share per social platform; search referrals down 33–38% YoY; finance is the hardest SEO category (YMYL). (§10) |
| T5 | Revision/point-in-time intelligence is differentiated | **TRUE, and it is the only unambiguous TRUE in the set.** Zero products, unregistered domains, unmet demand shock. (§8.2) |

### 2.3 The relationship to Increment #28

#28 (`macrochipz-product-discovery-data-feasibility-v1.md`) reached **NO-GO** on a *paid investor tool at $10–50/month*. #35 tests a **different** thesis — free, consumer, ad-supported — so that verdict does not transfer automatically. Two things from #28 do carry forward unchanged:

1. **Its licensing findings**, which this increment re-verified against current primary terms and in one case materially corrected (BEA, §6.2).
2. **Its one positive finding**, which #35 independently confirms from a completely different direction: *point-in-time correctness is the genuine gap, and it is what this codebase is already best at.* Two independent research passes, testing two different business models, converged on the same feature. That is the strongest signal in either document.

### 2.4 A live contradiction between research and code

#28 concluded that **FRED must not be the product's spine**. The implementation still uses FRED as the spine — **16 files reference it, and all six canonical monthly series flow through it** [MEASURED, §6.7]. This is an unresolved contradiction between what the research said and what the code does, and §21 treats it as a Day-1 item rather than a footnote.

---

## 3. Research Method

### 3.1 What was done

Five parallel research workstreams were dispatched, plus independent measurement against the live system:

| Workstream | Method | Output |
|---|---|---|
| **Data rights & licensing** (C) | Direct fetch of provider-owned domains only. Two PDFs (BEA TOS, BEA API User Guide) downloaded and text-extracted locally, so those quotes are byte-exact. | §6 |
| **Competitor & "wow" validation** (E, K) | Direct page fetches, Google News RSS, HN Algolia API, GitHub search API, YouTube/TikTok profile JSON, DNS/HTTP probes of candidate product domains. | §8 |
| **Audience, search, distribution, sponsorship** (A, F, G, H) | Wikimedia Pageviews API (own computation), Google/YouTube autocomplete, primary survey PDFs (FINRA, Fed SHED, Pew, Reuters Institute, TIAA-GFLEC), publisher trade reporting. | §4, §5, §9, §10, §11 |
| **Radar statistical feasibility** (J) | BLS/BEA/Census published variance and revision tables; own Monte Carlo simulations of false-positive rates under persistence. | §13 |
| **Operating cost** (Cost Analysis) | Direct fetch of vendor pricing pages; two JS-rendered pages (Render, Plausible) parsed out of their own embedded page payloads. | §16 |
| **Own measurement** | Direct queries against the MacroChipz PostgreSQL database and source tree. | F1–F10, cited inline as [MEASURED] |

### 3.2 What could not be done — stated plainly

These are real gaps, not hedges. Conclusions that depend on them are marked.

- **Google Trends: zero series retrieved.** Hard-blocked (HTTP 429) on every route including reader proxies. The event-spike analysis in §9.1 uses a Wikipedia-pageviews substitute built for this purpose, with a placebo control, plus published Trends-based peer-reviewed work. **No search volume figure appears anywhere in this document.**
- **Reddit: entirely blocked** (403 on API, HTML and proxy). The brief asked for recurring questions in r/personalfinance, r/Economics and similar. **This is unfulfilled.**
- **WebSearch budget was exhausted** in several workstreams; those relied on direct URL fetches, which is strong for "does a shipped product exist" and weak for "is there a 300-subscriber Substack nobody indexes."
- **Hard-blocked domains:** theguardian.com, businessinsider.com, cnbc.com, reuters.com, axios.com, investopedia.com, nfib.com, theharrispoll.com, Substack search, Product Hunt.
- **No "People Also Ask" data.** Substituted with Google/YouTube autocomplete, which reflects query *popularity*, not volume, and is not presented as volume.

### 3.3 Sources deliberately excluded

A large volume of AI-generated SEO content publishes precise-looking CPM tables with no source, sample or date (sponsorcal, influencerfee, newsletrix, outlierkit, vloggingpro and ~15 others). These numbers cite each other circularly and leak into LLM answers. **They were excluded entirely.** They are the single biggest source of fabricated-looking sponsorship figures in this market, and anyone continuing this research will encounter them.

---

## 4. Audience Findings

### 4.1 Economic literacy is low, flat-to-falling, and the schools are retreating [A]

- **FINRA NFCS, 6th wave** (fielded Jun–Oct 2024, **n=25,539**): only **46% answered ≥4 of 7** quiz questions correctly; **4% got all seven**. The five-question trend runs **42% (2009) → 39% → 37% → 34% → 32% (2021) → 32% (2024)**. ([PDF](https://finrafoundation.org/sites/finrafoundation/files/2025-07/NFCS-Report-Sixth-Edition-July-2025.pdf))
- **The one bright spot is inflation, and it is learning-by-experience:** the inflation question went 65% (2009) → 53% (2021) → **58% (2024)**, **+10pp among 18–34s**. *Inflation is the single concept Americans are measurably learning right now.*
- **TIAA Institute-GFLEC P-Fin Index 2026** (fielded Jan 2026, n=3,602, Ipsos KnowledgePanel): **47% of 28 questions correct — the lowest in the index's ten-year history.** Gen Z 38%. Weakest area is "comprehending risk" (36%) — the only area that does not improve with age. ([PDF](https://gflec.org/wp-content/uploads/2026/06/TIAA_GFLEC_Report_AnnualPFin_June2026_fin2.pdf))
- **Council for Economic Education, Survey of the States 2026:** **22 states require high-school economics — down 4 since 2024** — while 39 require personal finance, up 4. Three states formally replaced economics with personal finance.
- **NAEP Economics has been administered exactly twice, 2006 and 2012, with none scheduled through 2033.** There has been **no national measure of US student economic literacy for 14 years.**
- **63% agree thinking about personal finances makes them anxious** (56% in 2021); **75% among 18–34s**.

### 4.2 The perception-vs-data gap is real, large, and measured — with an important caveat [A]

The Federal Reserve states the product's reason to exist in one line. **SHED 2025** (fielded Oct 2025, ~13,000 adults, published 2026-05-13, [exec summary](https://www.federalreserve.gov/publications/2026-economic-well-being-of-us-households-in-2025-executive-summary.htm)):

- **73%** say they are doing okay or living comfortably financially
- **45%** rate their **local** economy good or excellent
- **25%** rate the **national** economy good or excellent — down 24 points from 2019

**A 48-percentage-point gap, decaying monotonically with distance from lived experience.** Corroborated across four independent survey houses: Gallup ECI −31 (Jul 2026); Pew 24% excellent/good; AP-NORC 67% say the economy is poor; UMich 47.8 (Sept 2026 preliminary).

**The adversarial counterpoint, which matters:** UMich's index is distorted by a **~9-point downward level shift** from its 2024 phone→web mode transition and by sample partisanship (~50% D / 25% R with a 53-point D–R sentiment gap) — UMich itself published a special report titled *"Sentiment, Web-Based Data Collection, and Partisanship"* (7/10/26). Independently, the **Conference Board's Present Situation Index was 121.2 and rising 6.8 points** in August 2026 while Expectations sat at 68.2. **Present conditions are fine; expectations are grim.** The "everyone thinks the economy is terrible" premise is substantially an *expectations-and-partisanship* story, not a lived-experience story. The product should not over-claim on it.

### 4.3 The hardest finding against the thesis [A]

**Economic information treatments barely move beliefs.**

- **Binetti, Nuzzi & Stantcheva, "People's Understanding of Inflation"** (NBER w32497, May 2024): the public attributes inflation to government actions, foreign aid and war spending; believes inflation can be fought without trade-offs; consequently **supports rate *cuts* to fight inflation**. And critically, these perceptions are **"hard to move experimentally."**
- **Stantcheva, "Why Do We Dislike Inflation?"** (BPEA Spring 2024): 80% believe prices systematically rise faster than wages; the median respondent put 2023 inflation at 5% against an actual 3.4%.
- **Lamla & Lein** (JMCB 2013): *"a fundamental disconnection among news on inflation, consumers' frequency of expectation updating, and the accuracy of their expectations."*
- **And the base rate is damning: financial literacy hit a decade low in 2026 despite an explosion of free financial content over the same period.**

> **Any feasibility case must answer: why would MacroChipz break a pattern that fifteen years of free financial content has not?** §17.4 gives the only honest answer this research supports.

### 4.4 What people say they want — and the counter-evidence [A]

**For the product:**

- **"Explains things clearly" is the #1 trust criterion for Gen Z** (~69% investors, ~67% non-investors), and **"isn't trying to sell me something" is #2 — ranked *higher* by non-investors** (FINRA/CFA, *Gen Z and Investing*). *This is direct validation of a free, non-commercial explainer.*
- **The bottleneck is signal quality, not user effort.** FINRA Foundation (Apr 2026, n=2,861): social-media-informed investors consult **7.6 of 10 information sources vs 4.0** for non-users and check regulator backgrounds at **36% vs 14%** — yet were fraud-targeted **13% vs 3%** and, among those targeted, **lost money 68% vs 29%**. *They do more due diligence and still lose more.*
- **Only 20% of finfluencer content containing recommendations carries any disclosure** (CFA Institute, 110-piece content analysis, Jan 2024).
- **57% made a financial decision they later regretted because of online misinformation — 64% among 25–45s** (CFP Board, Apr 2025, n=1,044).

**Against the product — and this is substantial:**

- **Pew, "Americans' Complicated Relationship With News"** (fielded Dec 2025, n=3,560): **52% worn out by news; 48% say most news isn't relevant to their lives; 60% have cut back; only 9% follow news because they enjoy it.**
- **Reuters Institute DNR 2026** (48 markets): **42% avoid news; trust 37%, lowest since 2015; interest down 13pp since 2021.** US: trust 25%, avoidance 45%.
- **Comprehension is only a second-order barrier.** DNR's reasons for avoidance: too much politics 43%, negative mood 36%, worn out 29%, distrust 29% — **"too hard to understand" only 8%.** People are not mainly disengaging because it is confusing. They are disengaging because it is exhausting and feels irrelevant.
- **The competitor is a chatbot.** Among AI-chatbot news users, top motivations are **42% "seek deeper explanations or context"** and 30% simplification — and **only 4% click through to the original source** (vs 19% from search, 17% from social). *The explainer job-to-be-done is being absorbed by ChatGPT, not by explainer websites.*

### 4.5 Segment assessment

| Segment | Evidence | Verdict as a Day-1 wedge |
|---|---|---|
| **Prospective homebuyers / mortgage-rate watchers** | 66% think the Fed sets mortgage rates; 61% think government dictates lender rates; 63% think rates are at an all-time high [B, n=400, Veterans United/Sparketing via HousingWire]. First-time buyer share **21%, a historic low** (NAR 2025); first-time median down payment **10%** while ~half of under-45s believe 20% is mandatory. Clean keywords, high intent, decisional. Two major free explainers just exited. | **STRONGEST. Recommended primary wedge.** |
| **Economically curious consumers ("why is everything so expensive")** | Autocomplete is dense with *why is inflation so high*, *why are grocery prices so high*, *why does the economy feel so bad*. Inflation is the one concept literacy is *rising* on (+10pp among 18–34s). | **STRONG secondary.** But "inflation" and "recession" are unusable as head terms (§9.3). |
| **Retail investors** | n=2,861: average 5.3/11 on the investing quiz; **more believe past performance IS predictive (47%) than know it isn't (41%)**; asked about a "guaranteed risk-free 25% annual return," **50% said they'd invest — 64% of 18–34s**. **69% overall, 87% of under-35s, say one reason they invest is "to learn about investing."** | **VIABLE but crowded.** Every finance creator targets them. |
| **Small business owners** | Fed SBCS (fielded Sep–Nov 2025, n=6,525): ~77% reported rising costs; **60% of firms that borrowed from online lenders found actual costs HIGHER than expected, vs 32–37% for bank borrowers.** US Chamber Q2 2026: **57% say inflation is their biggest challenge, up from 45%.** | **DEFER.** Real pain, but **where small business owners get economic information, and their satisfaction with it, has no reliable published figure — no such survey appears to exist.** Cannot target a channel that has not been measured. |
| **Students** | GDP's Wikipedia baseline (3,326/day) is the largest in the set and autocomplete shows *what is gdp / gdp per capita / gdp of india* — **global student reference demand**, not US consumer news demand. | **REJECT as a wedge.** Real demand, wrong product, no monetisation, global audience (which also disqualifies premium display ad networks, §11.5). |
| **Finance professionals** | **18,600 economist jobs in the US** total (BLS OOH). The real segment is analysts without formal macro training. | **REJECT as a wedge.** Too small; and it is #28's already-rejected thesis. |
| **Journalists / creators** | Not separately measurable with available tools. | **Not a wedge — but a distribution multiplier.** See §21.4. |

### 4.6 Where each segment currently gets information [A]

**CFP Board** (Apr 2025, n=1,044, ages 25–64, HHI>$50K): friends/family **55%**, financial websites **45%**, **social media 40% (48% under 45)**, bank 37%, advisor 32%, news outlets 30%, **podcasts 30%**, **generative AI 17% (21% under 45)**. Platforms: **YouTube 63%**, Facebook 45%, Instagram 40%, TikTok 35%, X 27%, Reddit 26%.

**Comfort acting without further verification:** advisor 74%, bank 67%, financial websites 54%, podcasts 48%, news outlets 47%, **generative AI 38%, social media 37%.** *The two fastest-growing sources are the two least trusted. That gap is the opening.*

**CFPB/FHFA National Survey of Mortgage Borrowers** [A, but 2014 fielding]: **77% of borrowers applied to only one lender; 70% chose the lender before deciding on loan type**; one in four first-time buyers was completely unfamiliar with the process. Among those "not at all familiar," **36% leaned heavily on friends/relatives vs 11% of the "very familiar"** — *the least-informed lean hardest on the least-reliable source.* CFPB's 2021 HMDA analysis found rate dispersion across the 20 largest lenders of **41–64bps**, where *"a 50 basis point difference amounts to over $1,000 a year."*

---

## 5. Economic Information Demand

### 5.1 The measurement, and why it was necessary [A]

Google Trends being hard-blocked, this session built a substitute from the **Wikimedia Pageviews API** (daily, en.wikipedia, `user` agent filter, 2024-09-01 → 2026-09-19) tested against the actual **BLS CPI schedule**, **BLS Employment Situation schedule** and **Federal Reserve FOMC calendar**.

**Median lift on release day vs the trailing 7–20 day median:**

| Article | Event | Median lift | Baseline views/day |
|---|---|---|---|
| Federal Open Market Committee | FOMC decision | **6.72×** | 148 |
| Federal funds rate | FOMC decision | **3.15×** | 245 |
| Consumer price index | CPI release | **2.80×** | 461 |
| Federal Reserve | FOMC decision | **2.12×** | 1,753 |
| Unemployment (US) | Jobs report | **1.47×** | 99 |
| Interest rate | FOMC decision | **1.46×** | 344 |
| **Inflation** | CPI release | **1.11×** | 894 |
| **Unemployment** | Jobs report | **1.02×** | 407 |

**Robustness:** re-run with a same-weekday baseline (±2 and ±3 weeks) and a **placebo test on 40 random non-event weekdays**. Placebos returned **1.08×** (CPI article) and **1.04×** (FOMC article), confirming the method does not manufacture lift. On the cleaner design: CPI article on CPI day **2.35×**, FOMC article on FOMC day **4.08×**, and **"Inflation" on CPI day 1.11× — indistinguishable from placebo.**

### 5.2 The structural pattern, which is the most decision-relevant finding in this document

> **Jargon terms are spiky and small. Plain-language concepts are flat and large.** "FOMC" spikes 6.7× off a base of 148/day. "Inflation" does not spike at all off a base of 894/day.

**Share of days in the last 12 months with attention >1.5× the trailing-28-day median:**

- **Mortgage loan: 0.5%** (and **0%** of days above 2×) — pure evergreen
- **Inflation: 3.0%** · GDP: 3.0% · Recession: 6.8% · Unemployment: 6.8%
- Consumer price index: 13.2% · **FOMC: 18.1%**

**Decay is fast.** CPI article: **2.80× (day 0) → 1.55× → 1.19× → 1.13× → 0.98×**. FOMC article: **6.67× → 3.24× → 1.88× → 1.11×**. **Event content has a ~72-hour shelf life.**

**Caveats, stated honestly:** Wikipedia measures *reference-lookup* demand ("what does this word mean"), not *news* demand — absence of lift there is not proof of absence of news interest. It is **global English**, not US-only. It is **not search volume** and is not presented as such.

### 5.3 Is attention growing or fading? [A]

Every economics topic fell year-on-year (median **−28.9%**). **But a control basket of 8 non-economic reference articles fell a median −29.7% over the same window.** Site-wide en.wikipedia human pageviews fell only ~4–10%.

**Conclusion: economics attention fell at exactly the same rate as comparable reference content. There is no topic-specific collapse — and no growth either.** The decline is an AI-answers phenomenon, which is itself a second, independent corroboration of the search-channel warning in §10.2.

### 5.4 Attention to inflation is state-dependent, and the US is at the threshold [A]

- **Korenok, Munro & Chen, "Inflation and Attention Thresholds,"** *Review of Economics and Statistics*, May 2026 ([DOI](https://doi.org/10.1162/rest_a_01402)), 38 countries: *"attention thresholds exist for most of the countries, and they typically occur between 2% and 4% inflation."*
- **Pfäuti, "The Inflation Attention Threshold and Inflation Surges"** ([arXiv:2308.09480](https://arxiv.org/abs/2308.09480)): threshold ≈ **4%**, and *"attention doubles when inflation exceeds this threshold."*

**Where the US actually is [VERIFIED, 2026-09-20]:** **CPI 3.4% y/y, core 2.4%** (August 2026); **30-year fixed mortgage 6.95%**, up from 6.26% a year ago; **UMich sentiment 47.8**.

> **Headline inflation sits inside the 2–4% attention-threshold band. MacroChipz would launch into a fading-attention inflation environment, partly offset by genuinely deteriorating housing affordability.** That is a second, independent argument for making housing/mortgages the wedge rather than inflation.

### 5.5 What people actually ask [A, Google/YouTube autocomplete, US-geo]

**Explainer intent exists, and it is about prices and rates:**
*why is inflation so high / still high* · *why are grocery prices so high* · *why is everything so expensive now* · *when will mortgage rates go down / drop below 5* · *will interest rates go down in 2026* · *is the economy bad right now* · **"why does the economy feel so bad"** (with a "reddit" variant)

**The highest-value intent is connective and decisional, not descriptive:**
*how does the fed affect mortgage rates / the stock market / inflation* · *how does inflation affect purchasing power* · *is now a good time to buy a house / refinance* · YouTube: *what rising treasury yields mean for the economy*

> **The winning frame is "what does [macro thing] mean for [your decision]" — not "here's today's CPI print."**

### 5.6 Testing the hypothesis "normal people care about mortgage rates and groceries far more than GDP or Treasury yields"

**Directionally right about intent, wrong about volume, and the real obstacle is something the hypothesis did not anticipate.**

**Supporting:** Treasury-yield queries are trader intent (*treasury yields today / chart / 10 year / bloomberg*). Wikipedia baselines are tiny — Yield curve 120/day, **Consumer confidence index 19/day**. Pew (fielded Jul 2026, n=3,554) **% "very concerned"**: health care costs **69%**, food/consumer goods **66%**, housing costs **64%**, gas 56%, electricity 54%, unemployment 44%, **stock market 18%**.

**Contradicting — reported against the hypothesis rather than omitted:** on Wikipedia, **GDP massively outdraws mortgage, 3,326/day vs 180/day.** Autocomplete shows why: this is student and global reference demand. *GDP has educational demand; mortgage rates have decisional demand. Different products.* And Treasury yields *do* attract explainer demand on YouTube when connected to a consumer consequence.

### 5.7 The finding nobody anticipated: keyword ambiguity is severe [A]

- **"CPI" on Google autocomplete is dominated by non-economic meanings:** *what does cpi stand for in education / in healthcare / cpi training / cpi insurance*. On Bing, the **#2 organic result for "what is the CPI report" is the Crisis Prevention Institute.**
- **"inflation" on YouTube is almost entirely not economics.** YouTube's own suggestions: *inflation animation, inflation fat, inflation roblox, inflation roulette, inflation asmr, inflation game, inflation blueberry* — the body-inflation animation genre — with *"inflation explained"* only at #10.
- **"recession" on YouTube** returns *recession pop, recessional wedding songs, recession music*.
- By contrast **"mortgage rates," "interest rates"** and **"economics explained"** are clean and intent-rich.

> **This is a concrete, checkable, non-obvious constraint: do not build video or search discovery around "inflation" or "recession" as head terms. Build it around rates, mortgages, prices, and "economics explained."**

---

## 6. Data Source & Licensing Matrix

All terms below were read from the provider's own domain on **2026-09-20**. Where a page was retrieved through an automated reader rather than extracted locally, load-bearing clauses were cross-checked with a second differently-worded query and are marked **⚖️** for counsel re-verification.

### 6.1 Headline verdict

| | Source | Use as ingestion + public redistribution source? |
|---|---|---|
| ✅ | **BLS, BEA, Census, Federal Reserve Board, Treasury, DOL** | **YES — VERIFIED.** Public-domain federal works, permissive API terms, commercial/ad-supported use fine. Attribution strings required (BEA/Census verbatim). |
| ⚠️ | **New York Fed (SOFR/EFFR/OBFR)** | **YES, but** the licence is quasi-copyleft and requires a specific legend. Workable with care. |
| 🛑 | **FRED / ALFRED** | **NO — do not build on it.** Four independent blockers. |
| 🛑 | **Freddie Mac PMMS (mortgage rates)** | **NO.** Prohibits commercial redistribution *and* automated access. |
| ❓ | **FHFA mortgage rates** | **UNKNOWN — REQUIRES CONFIRMATION.** No terms-of-use statement on the page. |

**The single most important licensing finding: every headline series MacroChipz wants is available from the originating federal agency under terms that clearly permit an ad-supported public website. FRED is a convenience wrapper whose terms do not.**

### 6.2 BLS — CPI, CES payrolls, CPS unemployment, JOLTS

**Terms:** [linksite](https://www.bls.gov/bls/linksite.htm) · [API TOS](https://www.bls.gov/developers/termsOfService.htm)

BLS material is **"in the public domain"**; users are **"free to use our public domain material without specific permission"** though BLS **"ask[s] that you cite the Bureau of Labor Statistics as the source."** API users must **"cite the date that data were accessed"** and state that **"BLS.gov cannot vouch for the data or analyses derived from these data after the data have been retrieved from BLS.gov."** [VERIFIED ⚖️]

- **Commercial use: permitted.** The words *commercial, redistribute, cache, store, resell* **do not appear anywhere in the API TOS** (explicit negative check).
- **Derived calculations: permitted**, but must be labelled as *your* calculation, not a BLS figure.
- **The BLS emblem is a registered trademark — do not use it.**
- **API limits [VERIFIED]:** v2.0 (free registered key) **500 queries/day, 50 series/query, 20 years/query, 50 requests per 10 seconds**. v1.0 unregistered: 25/25/10.
- **Vintages: NO.** Current vintage only.
- **Historical depth:** CPI-U to 1913; CES to 1939; CPS to 1948; JOLTS to Dec 2000 [LIKELY].

### 6.3 BEA — GDP, PCE, personal income

**This corrects #28, which recorded the BEA TOS as unverified.** The document is at `https://apps.bea.gov/api/_pdf/bea_api_tos.pdf` (the `www.bea.gov/API/_pdf/...` path 404s). It was downloaded and parsed locally, so **these quotes are byte-exact.**

> *"You may use the BEA API to develop a service or service to search, display, analyze, retrieve, view and otherwise 'get' information from BEA data."*
>
> *"All services, which utilize or access the API, should display the following notice prominently within the application: 'This product uses the Bureau of Economic Analysis (BEA) Data API but is not endorsed or certified by BEA.' … You may not use the BEA name, or the like to imply endorsement of any product, service, or entity, not-for-profit, commercial or otherwise."*
>
> *"You may not modify or falsely represent content accessed through the API and still claim the source is the BEA."*

**Commercial use: PERMITTED [VERIFIED].** The decisive evidence is that the attribution clause expressly contemplates **commercial** entities — *"not-for-profit, commercial or otherwise"* — and restricts only *implying endorsement*. There is no commercial-use prohibition anywhere in the two-page agreement.

- **Rate limits, byte-exact from the User Guide:** *"• Number of requests per minute (100), and/or • Data volume retrieved per minute (100 MB), and/or • Errors per minute (30)"*. Breach → HTTP 429 + `Retry-After`, 1-minute timeout. **Disposable email registrations "may be removed without warning."** *"Automating API retrievals to obtain data that has not been updated is discouraged."*
- **Mandatory verbatim attribution string** as quoted above.
- **Vintages: NO via API**, but BEA publishes a vintage archive separately on its own site — see §7.5.

### 6.4 Census Bureau — retail sales, housing starts, durable goods

**Terms:** [TOS](https://www.census.gov/data/developers/about/terms-of-service.html). Textually near-identical to BEA's.

- **Commercial use: permitted.** The words **"commercial," "redistribute," "cache," "store" do not appear anywhere in the document** (explicit negative check). Public-domain federal work.
- **Mandatory verbatim attribution:** *"This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau."*
- **Privacy constraint for the internal policy:** users must not *"use these data, alone or in combination with any other Census or non-Census data, to identify any individual person, household, business or other entity."* Irrelevant to macro aggregates, but it belongs in the policy.
- **The commonly-cited "500 queries per IP per day without a key" could NOT be confirmed from any first-party page.** [UNKNOWN — REQUIRES CONFIRMATION]
- **No iCal, JSON or CSV release calendar** — HTML and PDF only. Budget for a scraper or a hand-kept table.

### 6.5 Federal Reserve Board — H.15, H.10, G.17

**Terms:** [disclaimer](https://www.federalreserve.gov/disclaimer.htm) — *"Unless otherwise indicated, information on Board's website is in the public domain and may be copied and distributed without permission."* Citation requested, not mandatory.

- **H.15 is posted daily Mon–Fri at 4:15 p.m.** [VERIFIED]
- **The Board does not authorize framing of its website** — do not iframe federalreserve.gov.

**🚨 TIME-SENSITIVE ARCHITECTURAL RISK — the Data Download Program is being retired.** Verbatim from both the DDP landing page and the H.15 page: *"During the week of November 9, the 'Build Your Package' feature in the Data Download Program (DDP) will be removed in preparation for the eventual retirement of the DDP."* **Users are being redirected to FRED** — which is precisely the source MacroChipz cannot redistribute from. **Mitigation: ingest H.15 from the Board's own XML release and build a local archive now, before DDP goes away.**

### 6.6 U.S. Treasury — the most permissive source in the study

**Terms:** [fiscaldata API documentation](https://fiscaldata.treasury.gov/api-documentation/) —

> *"The data is offered free, without restriction, and available to copy, adapt, redistribute, or otherwise use for **non-commercial or commercial purposes**."*

- **No API key, no account, no registration, no documented rate limits, no attribution requirement.** Best-in-class.
- Yield curve: tenors 1M–30Y, based on NY Fed market quotations at **approximately 3:30 PM each business day**. Real yield curve begins **2004-01-02**.
- ⚖️ **One caveat:** the yield-curve pages on `home.treasury.gov` carry **no explicit licence text**; the "without restriction" grant is on `fiscaldata.treasury.gov`. Same agency, both federal works — **LIKELY** that it extends, worth a one-line confirmation. There is also a *"Developer Notice on changes to the XML data feeds"* to read before coding.

### 6.7 FRED / ALFRED — 🛑 do not use as the pipeline

Four **independent** blockers, any one sufficient. This is the section the project most needs, because the implementation currently contradicts it.

**BLOCKER 1 — the "essential user experience" clause.** Under Prohibitions, you agree not to:

> *"Use the FRED® API for any application that replicates or attempts to replace the essential user experience of the FRED® API, or the FRED® or ALFRED® web sites."*

MacroChipz — charting and serving US macro series to the public — *is* the essential user experience of FRED. [VERIFIED clause text; **LIKELY** that MacroChipz falls inside it]

**BLOCKER 2 — the per-user API key clause.** From the API key page:

> *"All web service requests require an API key to identify requests."* … *"Developers should request a distinct API key for each application they build."* … **"All users of an application shall use their own API key."**

The third sentence is fatal to the architecture: a free consumer website with anonymous visitors cannot have every visitor supply their own FRED key. **⚖️ This is the clause most worth a legal opinion**, because a favourable read of a cached server-side architecture (where visitors never trigger a FRED call) would unlock FRED *and* ALFRED entirely. **Conservative read: blocker.**

**BLOCKER 3 — commercial use is limited to *internal* commercial use.** From [fred.stlouisfed.org/legal/](https://fred.stlouisfed.org/legal/):

> *"You are free to access and use FRED® at no cost for your own personal use subject to certain limitations."*
>
> *"Series with the following copyright labels—Public Domain: Citation requested and Copyrighted: Citation required—may be used for **internal commercial uses** and may be displayed in textbooks, newsletters, or reports to clients provided that appropriate attribution is given."*

*Textbooks / newsletters / reports to clients* describes a closed, identified audience. A free, open, ad-supported public website is external mass redistribution.

**BLOCKER 4 — the "unique product" prohibition.** *"Take all the data on FRED or related services and claim it is a unique product or service."*

**Per-series copyright labels make this operationally worse.** FRED applies three labels with different rights — *Public Domain: Citation requested*, *Copyrighted: Citation required*, and *Copyrighted: Pre-approval required* (the last being **non-commercial educational or personal use only**). And in capitals on the legal page: *"BEFORE USING DATA SERIES OWNED BY THIRD PARTIES FOR ANYTHING OTHER THAN YOUR OWN PERSONAL USE, YOU MUST CONTACT THE DATA OWNER TO OBTAIN PERMISSION"* — and the Bank *"cannot give you such permission."* **Per-series licence checking would be mandatory if MacroChipz touches FRED at all. That burden alone argues for going direct.**

**ALFRED is technically perfect and legally unavailable.** Its tagline is literally *"Economic data time travel since 2006."* The API exposes `vintage_dates`, `realtime_start`/`realtime_end`, and `output_type=4` — **"Observations, Initial Release Only"**, which is *exactly* the "what we knew then" capability MacroChipz wants. But it runs through the FRED API (Blockers 1–2), and the archive of *which number was published on which date* is the St. Louis Fed's curatorial compilation, not a federal public-domain dataset. **Commercial redistribution of ALFRED vintages: NOT VERIFIED AS PERMITTED — treat as prohibited absent written permission.**

**Recommendation: write to the St. Louis Fed and ask.** They are generally responsive, the ask is free, and a written grant converts FRED/ALFRED from the largest blocker into the largest single accelerator. **Until then, architect as if FRED does not exist.**

### 6.8 Mortgage rates — 🛑 no free commercial path exists, and this must be said plainly

**Freddie Mac PMMS is explicitly prohibited.** From [freddiemac.com/terms](https://www.freddiemac.com/terms):

> *"You may not redistribute Data, publish Data, or commercially exploit Data or derived products/services without a separate written agreement or license from Freddie Mac."*
>
> *"You may not use any automated means (including bots, scrapers, spiders, crawlers, scripts, or other programmatic tools) to access, extract, copy, monitor, or collect any Content."*

Three separate prohibitions hit MacroChipz: no commercial exploitation, no derived products, no automated collection. ⚖️ The PMMS page itself carries a softer line (*"Information from this document may be used with proper attribution"*) which **conflicts** with the site-wide terms; a lawyer could argue the page-level grant governs the document. **Do not bet an ad-supported business on that reading.** Note also that FRED's `MORTGAGE30US` *is* the Freddie Mac series, so it is double-blocked.

**FHFA is unresolved.** [fhfa.gov/data](https://www.fhfa.gov/data) references MIRS and NMDB and states FHFA complies with the Open Government Data Act, but carries **no terms-of-use, public-domain or redistribution statement.** MIRS is monthly and lagged in any case. [UNKNOWN — REQUIRES CONFIRMATION]

**The honest answer: there is no verified free, first-party, commercially redistributable weekly US mortgage rate series.** Options in order of realism: (1) **ask Freddie Mac for a written licence** — it may be free for an attributed public-education site; (2) **use the Treasury 10-year as the proxy and say so on the page**; (3) pay a vendor. **Do not ship scraped PMMS.**

> **This constraint is, unusually, on-message.** MacroChipz already holds the Treasury curve (`rates_v1.0`). "We show you the 10-year Treasury, because that is what actually tracks your mortgage rate — and because the mortgage-rate survey itself is not ours to republish" is both *legally correct* and *exactly the educational point the wedge audience needs to learn* (§5.4, §4.5). The limitation is the lesson.

### 6.9 DOL — weekly initial claims

Public domain ([dol.gov copyright](https://www.dol.gov/general/aboutdol/copyright)). **No REST API**; the weekly release is a PDF at `https://www.dol.gov/ui/data.pdf`, **Thursdays 8:30 a.m. ET** (embargo line extracted directly from the live release). ⚠️ `oui.doleta.gov/unemploy/claims.asp` **returned a live database error** (`SQLSTATE=HY000`) on 2026-09-20 — do not make it a single point of failure. `dol.gov/newsroom/releases` returns **HTTP 403**; **no machine-readable calendar located** [UNKNOWN].

**Revision behaviour is unusually favourable and self-documenting.** The release narrates its own revisions verbatim: *"a decrease of 10,000 from the previous week's unrevised level of 206,000"* … *"The previous week's level was revised down by 5,000 from 1,774,000 to 1,769,000."* **Advance figure, then exactly one revision the following week.**

### 6.10 New York Fed — SOFR, EFFR, OBFR

The only source with a genuine licence rather than mere public domain, and it has copyleft-flavoured conditions. **Markets API is open with no key** (verified empirically: `https://markets.newyorkfed.org/api/rates/all/latest.json` returned data unauthenticated, including a **`revisionIndicator`** field).

- Commercial use permitted (*"business purposes"*), but **NY Fed's name may not appear in advertising or marketing copy.**
- **Strongest explicit derivative grant of any source:** *"Modify and create derivative works from the Content."*
- **⚖️ LAWYER FLAG — the copyleft clause:** *"If you distribute the Content, you must make the Content available with the same permissions, conditions, and restrictions set forth in these Terms."* Read literally, republishing SOFR may oblige MacroChipz to grant downstream users the same rights and pass the Terms along — **incompatible with a blanket "all rights reserved" site ToS.** Practical fix: carve NY Fed content out explicitly on rate pages. Do not let boilerplate silently breach this.

### 6.11 Required attribution block

Assembled from the verified strings above; every page must carry it:

> This product uses the Bureau of Economic Analysis (BEA) Data API but is not endorsed or certified by BEA. · This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau. · Source: U.S. Bureau of Labor Statistics; data retrieved [date]. BLS.gov cannot vouch for the data or analyses derived from these data after the data have been retrieved from BLS.gov. · Source: Board of Governors of the Federal Reserve System. · © 2026 Federal Reserve Bank of New York. Content from the New York Fed subject to the Terms of Use at newyorkfed.org. · Source: U.S. Department of Labor.

### 6.12 Three engineering rules that follow from the licensing work

1. **Label every derived figure** (YoY, 3m-annualised, real terms) as a *MacroChipz calculation* — required by BEA's and Census's "may not modify… and still claim the source is X."
2. **Re-pull full history; never append** for any seasonally adjusted series. CES re-computes seasonal adjustment concurrently **every month**, and CPI SA is revised **five years back annually**. A site that caches and appends will silently drift out of sync every January. *This is the most common correctness bug in consumer macro sites, and MacroChipz's determinism claims make it a credibility risk rather than a cosmetic one.*
3. **Snapshot every release at publication** — it is the only legally unencumbered route to "what we knew then."

### 6.13 Ranked questions for counsel ⚖️

1. FRED's *"All users of an application shall use their own API key"* — does a cached server-side architecture where end users never trigger a FRED call comply? *(Highest value: a favourable read unlocks FRED + ALFRED entirely.)*
2. FRED's "essential user experience" prohibition — does a free public macro site fall inside it? *(Assume yes.)*
3. FRED's *"internal commercial uses"* — does an ad-supported public site exceed it? *(Assume yes.)*
4. NY Fed's downstream-permissions clause — how to draft MacroChipz's own ToS so republishing SOFR does not breach the pass-through obligation.
5. Freddie Mac — page-level grant vs site-wide prohibition; which governs the PMMS document? *(Do not rely on the favourable read; ask for a licence.)*
6. ALFRED — is the *compilation* protectable separately from the public-domain underlying values?
7. Treasury — does the fiscaldata grant extend to home.treasury.gov yield-curve pages?
8. Census — confirm the 500/IP/day threshold from a first-party page before sizing infrastructure.

---

## 7. Release / Revision Opportunity

### 7.1 The cadence measurement that kills the daily product [MEASURED]

Computed directly against the `release_occurrences` table for CY2026:

- **6 curated releases → 75 scheduled events in 2026**
- **Distinct days with ≥1 release: 60 of ~252 business days = 23.8%**
- Monthly range: 5–8 events
- **Even with an aggressively expanded catalog** (+weekly claims, +8 monthlies = 223 events/year), distinct event days reach only **~150–170 of 252 (60–67%)**
- **The only genuinely every-business-day US macro signal is the Treasury yield curve (252/year)**

A cross-check from primary release calendars agrees on the raw volume: **BLS published 13 news releases in October 2026**; BEA runs ~3/month; Census ~11+/month; plus FOMC (8/year), weekly claims, and weekly PMMS. That is **~45–60 scheduled US economic events per month, roughly 2–3 per business day**.

**But volume is not the constraint — salience is.** Of the 13 BLS October releases, **exactly two** (Employment Situation, CPI) are consumer-salient. Combined with the 2–3 day attention decay measured in §5.2:

> **Event-driven content can honestly carry perhaps 6–8 elevated-attention days per month. The other ~22 days must be carried by evergreen content.** "Today in the Economy" as a daily live product, and a daily video cadence, are not supported.

### 7.2 Revision behaviour — the five headline series [VERIFIED]

| Series | Freq | Lag | Revisions |
|---|---|---|---|
| **CPI** | Monthly, 8:30 ET | ~2 wks | **NSA: never revised** — *"these series are final when issued."* **SA: revised annually, up to 5 years back.** |
| **Payrolls (CES)** | Monthly, 8:30 ET | ~3 wks | *"the prior 2 months are routinely revised"*; plus an **annual benchmark** anchored to March, published with the January release. *"The absolute average benchmark revision… over the prior 10 years is 0.2 percent."* Seasonal adjustment is **concurrent** — the whole SA series is recomputed monthly. |
| **Unemployment (CPS)** | Monthly | ~3 wks | Not revised monthly; **annual seasonal-factor revision, 5 years back.** |
| **GDP** | Quarterly, 8:30 ET | ~1 mo | **3 estimates + annual + ~5-yearly comprehensive.** |
| **Retail sales (MARTS)** | Monthly, 8:30 ET | ~2 wks | Advance → revised next month → again; annual revision. ⚠️ **A large rebenchmark was tentatively scheduled for 2026-09-28** — eight days after retrieval. |
| **Housing starts** | Monthly, 8:30 ET | ~2.5 wks | Prior months revised each release; *"On average, the preliminary seasonally adjusted estimates… are revised 3.8 percent or less."* `p`/`r` flags in tables. |

### 7.3 The revision magnitudes that determine what is publishable [VERIFIED]

From [BLS CES revision tables](https://www.bls.gov/web/empsit/cesnaicsrev.htm), mean **absolute** revision, total nonfarm SA, 1st → 3rd estimate: **57k (1979–present), 51k (2003–present), 58k (2025)**.

Backing out an implied SD (E|X| = σ√(2/π)) from MAR=57k gives σ ≈ 71k. **A revision must exceed ~118k (90%) or ~143k (95%) to be genuinely unusual.**

> **This is a critical, counter-intuitive product constraint: a 40k downward payroll revision — exactly the kind that generates headlines — is entirely routine and is NOT a finding.** A revisions product that treats every revision as news would be as dishonest as the coverage it replaces.

**Benchmark revisions are where the real story is.** The 2015–2025 level history (−172, −81, +135, −16, −489, −121, −7, +506, −187, **−598**, **−861** thousand) has mean absolute 288k and SD 353k — so **2024 (z=−1.21) and especially 2025 (z=−1.95) are genuine outliers.** Preliminary announcements: [−818,000 for March 2024](https://www.bls.gov/ces/notices/2024/2024-preliminary-benchmark-revision.htm), [−911,000 for March 2025](https://www.bls.gov/news.release/archives/prebmk_09092025.htm), [−79,000 for March 2026](https://www.bls.gov/news.release/prebmk.nr0.htm).

**GDP** ([BEA, "Comparisons of Revisions to Real GDP," Nov 2025](https://www.bea.gov/sites/default/files/2025-11/relia.pdf), 1999–2024): advance→second **0.5pp** mean absolute; advance→third **0.6pp**; advance→latest **1.2pp**. But *"the direction of change between the advance and latest estimates match 97 percent of the time."* **Implication: quarter-to-quarter GDP changes below ~1pp are not findings.**

### 7.4 The one revision statistic that is both honest and genuinely interesting

**A sign test on revision *direction*, not magnitude.** BLS publishes mean *signed* revisions precisely because *"the closer the mean revision is to zero, the less indication that revisions are predominantly either upward or downward."* Under a null of unbiased revisions each sign is a fair coin:

| Run | Two-sided p |
|---|---|
| 6 of 6 same sign | 0.031 |
| 8 of 9 same sign | 0.039 |
| 11 of 12 same sign | 0.0064 |
| 18 of 24 same sign | 0.023 |

Deterministic, cheap, assumption-light, and **exactly explainable**: *"The last nine payroll revisions have all been downward. If revisions were unbiased, that would happen about one time in 250."* Empirically, signed 1st→3rd revisions were −30k (2023), −20k (2024), **−58k (2025)** against a long-run mean of **+11k** — three consecutive negative years, though three years alone is p=0.25 and is **not** on its own significant.

**This is the single best candidate in the entire research set for the spirit of what MacroChipz wants to be.**

**On whether revisions are predictable:** the literature genuinely disagrees — [Faust, Rogers & Wright (JMCB 2005)](https://ideas.repec.org/p/fip/fedgif/690.html) find US GDP revisions *"very slightly predictable"* (mostly news), while [Aruoba, "Data Revisions Are Not Well Behaved" (JMCB 2008)](https://ideas.repec.org/a/mcb/jmoncb/v40y2008i2-3p319-340.html) finds broader revisions biased and predictable. **Either way, MacroChipz must not predict revisions — that crosses the descriptive line.** Describing the realised record against BLS's own published distribution stays inside it.

### 7.5 First-print / vintage data — what is actually obtainable

| Option | Coverage | Commercially usable? |
|---|---|---|
| **ALFRED / FRED `output_type=4`** | Excellent — vintages since 2006, "Initial Release Only" built in | 🛑 **NO** (§6.7) |
| **Philadelphia Fed Real-Time Data Set** | The standard academic vintage set | ❓ **Terms not fetched this session. UNKNOWN.** |
| **BEA vintage archives on bea.gov** | GDP prior vintages published by BEA itself | ✅ **LIKELY usable** — federal work, BEA TOS permits display. **Best legitimate lead; verify the archive URL.** |
| **Archived agency release PDFs** | First prints are *in the text of the release* | ✅ **VERIFIED usable.** Demonstrated this session by extracting exact first-print values and revision statements from the live DOL and Census PDFs. |
| **Capture own vintages from day one** | Everything, forward only | ✅ **Unambiguously ours. Zero licence risk.** |

**Recommendation: do both of the last two.** Start snapshotting every release from the day the pipeline goes live — it is cheap and it compounds — and backfill from archived agency releases where a specific story needs it. **Do not backfill from ALFRED.**

### 7.6 The honesty constraint on the Time Machine [MEASURED]

This is the most important internal finding about MacroChipz's own data:

- `observation_versions`: **1,072 of 1,072 rows are `is_backfilled = true`**
- **0 genuinely observed versions**
- **0 REVISED change events ever captured** — all 358 updates are NEW

> **MacroChipz's own data can prove "what MacroChipz knew" only going FORWARD from Increment #31.** #31/#32 already disclose this correctly in the UI; **the product claim must never exceed it.** A "rewind the economy" experience built on backfilled vintages would be a fabrication of publication-time knowledge, which the brief explicitly prohibits.

**Related [MEASURED]:** monthly series currently hold **59–60 observations** (2021-09 → 2026-08); rates hold 119 daily observations (`DEFAULT_LOOKBACK_MONTHS = 12`). Source data is far deeper (CPI to 1913, PAYEMS to 1939). **This is an ingestion choice, not a data limit — but today, any "unusual versus its own history" claim rests on ~60 monthly points, which is too thin for percentile or extreme claims.** Deep re-ingestion is a prerequisite for Radar, and it is free.

### 7.7 Release calendars

| Source | Formats | Label |
|---|---|---|
| **BLS** | HTML + **iCal**: `https://www.bls.gov/schedule/news_release/bls.ics`. *"All times on calendar are Eastern Time."* | **VERIFIED** |
| **BEA** | **Best in class — HTML + ICS + JSON + RSS.** JSON: `https://apps.bea.gov/API/signup/release_dates.json` | **VERIFIED** |
| **Census** | **HTML + PDF only. No iCal, no JSON, no CSV.** Scraper or hand-maintained table required. | LIKELY |
| **Fed Board** | No calendar file; fixed daily 4:15 p.m. cadence | VERIFIED |
| **Treasury / NY Fed / DOL** | **No machine-readable calendar located.** DOL newsroom 403s. | UNKNOWN |

> **BLS ICS + BEA JSON cover the two highest-salience releases for free.** That is the honest replacement for the FRED releases API — which, per [MEASURED F4], is the **stickier** FRED dependency than the series themselves, because no equally machine-readable public-domain calendar exists for the full catalog.

---

## 8. Competitor Landscape

Six proposed "wow" features were subjected to a deliberate kill attempt. **Four survived. Two did not.**

### 8.1 Summary verdict

| Feature | Verdict |
|---|---|
| Economic Pulse | 🛑 **ALREADY EXISTS, WELL.** Table stakes, not a differentiator. |
| What's Moving | ⚠️ **EXISTS, BUT POORLY.** Narrow gap; execution moat only. |
| Radar | ⚠️ **EXISTS, AIMED ELSEWHERE.** Math is commodity; consumer framing is rare. |
| Time Machine (vintages) | ✅ **NO CONSUMER TIER EVER ATTEMPTED.** Rare; demand unproven. |
| **Revision intelligence** | ✅✅ **GENUINELY EMPTY. The strongest card.** |
| Evidence-backed video | ✅ **EMPTY in the specific form** — but between a graveyard and a slop-flood. |

### 8.2 Revision tracking — genuinely rare, zero products

The closest artifacts anywhere, ranked by consumer-readiness:

1. **SF Fed, "Revisions to Payroll Employment Gains in Historical Context"** ([link](https://www.frbsf.org/research-and-insights/data-and-indicators/revisions-to-payroll-employment-gains/), updated 2026-09-04) — two charts, CSV + Excel download, tied to each BLS release. **The single closest thing on the internet, and it is ~20% of a consumer product**: a static research page with no narrative, no email, no alerts, no mobile design, no "what this means."
2. **Philly Fed early benchmark revisions** — quarterly, 50 states + DC. **Delivery format: a PDF and a spreadsheet.** ~10%.
3. **BLS's own revision tables** — 1st/2nd/3rd estimates for every month since 1979, raw unstyled HTML. ~3%. *This is the source data and nobody has ever wrapped it.*
4. Economic calendars leak revisions as a byproduct — Investing.com folds them **silently into the "Previous" column with no marking.** ~5%.

**The negative evidence is the interesting part:**

- Google News RSS for `"revisions tracker"` + economic: **zero items, ever**
- HN Algolia: **two links total**, both low-score news articles, **no Show HN**
- GitHub `economic data revisions`: **7 repos, all 0–1 stars**, all hobby pipelines
- Domain probes — revisions.watch, datarevisions.com, jobsrevised.com, thedatarevision.com, economicrevisions.com, revisionwatch.com, truejobsnumber.com, whatthedatasaid.com — **no A records. All unregistered or parked.**
- Employ America's MacroSuite, the most product-like indie macro shop, has **no revisions product**

**And the demand shock already happened and produced no supply.** The Sept 2025 preliminary benchmark was **−911,000**, the largest ever, finalised at an 862,000 revision with the January jobs report on 2026-02-11. Add the 2025 BLS commissioner firing, the Oct 2025 shutdown data blackout, and The Economist's *"America's economic data are becoming murkier."* That entire cycle produced **op-eds, two Fed research pages, Brookings panels and an advocacy group.** It produced no tool, no dashboard, no newsletter.

> **Verdict: genuinely rare, and not because it is impossible.** The people who understand revisions are economists who already have ALFRED and do not need a product. The people who would benefit do not know revisions exist. **That is a marketing problem, which is the good kind.**

### 8.3 Economic Pulse — already exists, well

**Government/Fed tier:** BLS Economy at a Glance (~35% similar; notably *does* mark revisions inline with `(p)`/`(r)` flags). **St. Louis Fed Economy at a Glance** — eight FRED-powered charts with genuine plain-English framing, recession shading, view toggles; **the strongest free incumbent, ~55% similar.** **Chicago Fed CFNAI** — 85 indicators collapsed to one number with published interpretive thresholds, plus MA3 and a diffusion index; **this is literally an "Economic Pulse" and it has existed since 2001 — ~70% on substance, 15% on presentation.** Plus Census's free "America's Economy" mobile app (20 indicators, push alerts) and Atlanta Fed GDPNow.

**Commercial free-tier:** Trading Economics (~50%, wins on completeness, loses badly on legibility); Investing.com calendar; **TipRanks** (~45%, genuinely consumer-legible, big cards, a yield-curve verdict); **Koyfin's free $0 tier explicitly includes macro dashboards**; Convex (673+ indicators, a 0–100 composite recession probability, free in beta).

**Indie consumer tier — the ones that should worry us most:**

- **recessiondashboard.com** — a single "Recession Score" (51/100, "Caution"), 13 indicators, genuinely plain-English update text (*"Nothing moved towards recession in the last ten weeks"*), ▼▲ change markers, a faded arrow showing the prior dial position, a "What to Look For Next" section, free, with a newsletter. **~70% of Pulse + What's Moving combined.**
- **RecessionPulse** — 50 indicators across 8 categories, free dashboard, **free daily email briefing**, an AI composite 0–100 plus **SMS threshold alerts at $6.99/mo**, screener at $9.99. **~65%, and it already has the alerting and monetisation layer MacroChipz has not built.**
- **fredecondashboard.com** — 27 series collapsed to Healthy/Caution/Alert, pitched at *"anyone who wants to understand the direction of the US economy without wading through government data releases or financial news noise."* **That is essentially MacroChipz's positioning statement, already written by someone else.**

> **Would the difference matter to a normal person? Mostly no.** A normal person cannot tell recessiondashboard.com from the proposed Pulse. **Differentiation here comes from execution and distribution, not concept. Ship the Pulse because the product needs it, not because it sells the product.**

### 8.4 Economic Time Machine — no consumer tier ever attempted

**ALFRED's own tagline is "Economic data time travel since 2006."** The St. Louis Fed has owned MacroChipz's exact positioning line for twenty years and never built a consumer product on it. Past eight category tiles it collapses into researcher-ware: series pages default to the newest vintage, vintage selection is buried in a JS download form, and **there is no documented "compare two vintages" feature.** ~15% consumer.

**FRED itself has no revision-comparison UI at all.** Its one relevant help article mentions vintages and then **points users away to ALFRED as a separate application.** *The most-used consumer-adjacent economic data site on earth deliberately hides revisions from its users.*

**The competitive signal that matters most in this entire report:** Bloomberg launched an **"Economic Releases and Surveys Point-in-Time Dataset" on 2026-05-08** — 3,000+ indicators, 100+ economies, history to 1997, with timestamped actuals-vs-consensus and full revision histories, delivered via Bloomberg Data License. Read it two ways: **(a) Bloomberg validated four months ago that point-in-time economic data is worth productising; (b) they aimed 100% of it at quants at Data License prices.**

**Indie side is empty:** HN Algolia for `ALFRED vintage data` returns **zero hits**; GitHub's top ALFRED-vintage repo has 7 stars. Consumer econ products that *do* exist on HN — theeconomicatlas.com, gorillaterminal.com, recession.fyi, factiq.com — **none touch vintages.**

> **The category is strictly bimodal: free-but-academic or expensive-and-institutional, with no consumer tier ever attempted.** The caution deserves respect: **normal people do not wake up wanting to know what the data said in March.** This works only framed as *"the number you remember was wrong,"* attached to a live news moment. **Rare ≠ wanted.**

### 8.5 Radar — exists, but aimed elsewhere

- **MacroMicro MM AI** — "The AI-Native Macro Terminal," 100M+ data points, 7.6M annual investors, shipping **Anomaly Alerts, a Risk Heatmap, a Cycle Dashboard**. **The most direct Radar competitor, real and funded, ~60% similar** — but Taiwan-based, primarily Chinese-language, global-macro/portfolio oriented, subscription.
- **`tsvetoslavtsachev/us-macro-dashboard`** — uncomfortably on-the-nose. 71 FRED series across seven lenses with **explicit cross-lens divergence detection** ("labor cooling while credit tightening"), **z-score anomaly flagging** with adaptive 10-year windows, and **historical analog matching** via cosine similarity returning top-3 nearest episodes with forward-path statistics. Output: a self-contained weekly HTML briefing. **Conceptually ~85% of Radar — with 0 stars and 0 forks.**

> **That last data point is the whole lesson: the math is commodity, and the packaging is the entire game.** Aftermath Analytics, FinRadar.ai, TradingView's Macro Regime Dashboard and Permutable AI all do versions of this. **Every one outputs a signal for someone deciding a trade. None outputs an explanation for someone deciding whether the economy is okay.** "Labor cooling while credit tightens" is a trade setup in all six products and a news story in zero. **That difference matters to a normal person if and only if the output is a sentence, not a z-score.**

### 8.6 AI economic explainers — genuinely unoccupied

- **OpenEcon Data** ([openecon.ai](https://openecon.ai)) — the closest thing that exists. Free, AGPL-3.0, no sign-up, web chat with charts, 330K+ indicators, every result carries a source URL, explicitly built against hallucination, also ships as an MCP server. **But** positioned for economics *researchers* (alongside Stata/MATLAB integration and LaTeX tooling), solo maintainer, **77 GitHub stars**. **~40% of the target. The one to watch — it proves the approach works.**
- **FRED: no AI at all.** Verified from the live 2026 nav — Tools is Excel add-in, API, mobile apps. No assistant, no chatbot, no official MCP server. *The irony: in Sept 2026 FRED announced it had added data **about** the adoption of generative AI. They added AI statistics instead of an AI.*
- **Koyfin: no AI.** The only "AI" on the site is marketing buttons that open ChatGPT/Claude/Gemini pre-loaded with *"What are the top Koyfin use cases for individual investors?"* — **AI to explain Koyfin, not the economy.**
- **28 indie FRED MCP servers on GitHub**, largest at 120 stars. Every one needs a JSON config, a terminal and an API key. **Zero consumer surface.**
- Raw ChatGPT/Claude/Gemini will confidently give a **stale, wrong** GDP number without a connector, and none has a first-party FRED connector.

> **Every component is free and on the table — public APIs, 28 open MCP servers, capable consumer LLMs — and nobody has assembled them for a normal person.** Each incumbent has a structural reason not to. **This is the second genuinely open slot, and MacroChipz's bounded Analyst (#33) is already 80% of it.**

### 8.7 Creators and media — huge audience, served 100% static

**YouTube subscriber counts pulled live 2026-09-20:**

| Channel | Subs | Videos | Lifetime views |
|---|---|---|---|
| Economics Explained | **2.88M** | 447 | 375.9M |
| How Money Works | **1.75M** | 325 | 296.9M |
| Gary's Economics | **1.65M** | 423 | 247.8M |
| Patrick Boyle | **1.33M** | 480 | — |
| The Plain Bagel | **1.21M** | 279 | 100.1M |
| Money & Macro | **674K** | 147 | 52.0M |
| Ben Felix | **639K** | 179 | 37.5M |
| **Kyla Scanlon** | **197K** | 175 | 26.2M |

**Newsletters:** Noahpinion **458,000**; Kyla Scanlon **167,000**; Apricitas/Joseph Politano **83,000**.

> **Kyla Scanlon is the closest positional comparable — economics explained for non-economists, personality-led. After ~175 videos she is at ~197K subscribers. That is the realistic order of magnitude for a well-executed new entrant, not 2.9M.**

**Does anyone tie explanation to live queryable data? Essentially no — and this was checked in the HTML, not taken on anyone's word.**

- **Joseph Politano / Apricitas is the entire state of the art, and he does it by hand.** His latest post contains **10 links to live `fred.stlouisfed.org/graph/?g=...` permalinks**. The pattern is the interesting part: the *charts* are static PNGs, but **the sentence making the claim is the hyperlink** — e.g. `<a href="...">are up more than 40% since 2020 and continue rising.</a>` The reader clicks the claim and lands on the live auto-updating series. **~50% of MacroChipz's evidence-backed concept, manually curated per post, for 83K readers.**
- **Noahpinion**, latest post: **0** data links, 11 static images. **Kyla Scanlon**, latest post: **0** data links, 38 images.
- **All eight YouTube channels:** static charts rendered into video, structurally incapable of click-through, **zero series links in descriptions.**
- **Employ America MacroSuite** — the only genuine live-data product in the set, updating *"precisely on the date when new data comes out"* — **behind a sign-in, written for policy professionals.**

**Short-form:** Gary's Economics has **519,900 TikTok followers**; Economics Explained has **15,300 on TikTok against 2.88M on YouTube** — the long-form incumbents have completely failed to translate. **Short-form personal finance is saturated; short-form macro explained with cited data is nearly empty.** But **one in five top TikTok videos in finance-adjacent searches is now AI-generated** — the *format* is crowded with slop even where the *substance* is empty.

**And the graveyard.** **Sherwood News is effectively dead, and this was not publicly announced.** The site returns HTTP 200 and looks alive. Walking its sitemap (544 URLs): /tech last posted 6/17/26, /business 6/24/26, /culture 6/29/26, /power 7/8/26, /world 7/10/26, /markets 8/17/26. **Article counts: 193 in June 2026 → 6 in July → 1 in August → 0 since.** The homepage `<lastmod>` is frozen at 2026-08-17 while still declaring `changefreq: hourly`. **But Robinhood Snacks, the daily newsletter, still ships** (issues 09.18, 09.17, 09.16, 09.15, 09.14). Nieman Lab reported the shutdown on 2026-07-13.

> **Robinhood wound down Sherwood's original journalism and kept only the newsletter. Whatever Sherwood proved, it wasn't that well-funded static explainer journalism works as a destination site.** Note also it was subsidised by a brokerage the entire time, so it was never evidence that a standalone version works.

**Other failures worth holding:** **The Messenger** raised $50M, launched May 2023, dead Jan 2024 on ~$3M revenue. **Quartz** — a business-news explainer — traffic −85% vs March 2020, sold to Redbrick Apr 2025. **theSkimm** — the closest consumer-newsletter analogue — ~$29M raised, 7M peak → 5M today, sold for undisclosed terms after years of trying. **Business Insider** cut 21% of staff in May 2025, its CEO citing *"extreme traffic drops… outside of our control."*

---

## 9. Search & Content Findings

*(§5 covers demand measurement; this section covers what it means for content.)*

### 9.1 Event-driven content cannot carry a calendar

Cross-referencing §5.2 (72-hour decay; 3.0% of days elevated for "inflation") with §7.1 (23.8% of business days have a release): **event content supports roughly 6–8 pieces per month at real attention, not 20–30.**

### 9.2 Evergreen is the volume, and it is decisional

The autocomplete evidence (§5.5) is unambiguous that the recurring, high-intent, non-decaying questions are:

1. **What actually moves my mortgage rate?** (66% get this wrong — §5.4)
2. **Why is everything so expensive / why do prices not fall when inflation falls?**
3. **How does the Fed affect [the thing I care about]?**
4. **Is now a good time to buy / refinance?**
5. **Why does the economy feel bad when the numbers look fine?** (the 48-point SHED gap — §4.2)
6. **Why does economic data get revised?** ← *the bridge between the evergreen library and the differentiated feature*

**Note that #6 is the only item that is both evergreen and unoccupied.** The others are evergreen and contested.

### 9.3 The "Wait, Seriously?" concept survives — with one renaming constraint

The proposed education concept maps directly onto the measured misconceptions and is the **highest-confidence content recommendation in this document**. But §5.7's keyword-ambiguity finding constrains it: **do not use "inflation" or "recession" as head terms in titles, slugs or video topics.** Use *mortgage rates*, *interest rates*, *prices*, *the Fed*, *economics explained*.

### 9.4 A dated, concrete supply vacuum [B]

**Fannie Mae appears to have stopped publishing the Home Purchase Sentiment Index** — its National Housing Survey page still shows a publication date of **2025-10-02**. Per HousingWire (2025-12-03), Fannie missed the November 2025 publication, the **first gap in 15+ years**, and its ESR Group forecasts also stopped. **Freddie Mac discontinued its economic/housing/mortgage outlook in February 2025.** Fannie, Freddie and FHFA did not respond to questions.

> **Two of the largest free, plain-English consumer housing-economics explainers exited the field in ~19 months. That is the most direct "room in the market" evidence anywhere in this research** — and it points at the same wedge as the misconception data.

### 9.5 The SERP reality check

Bing's top results for "are we in a recession" are Business Insider, Motley Fool, Morningstar, LendEDU, Facet, tradersunion — **affiliate and lead-gen finance content farms plus big media.** MacroChipz would enter that SERP as an unknown, in a category Google classifies as YMYL (§10.2).

---

## 10. Distribution Findings

### 10.1 The single most decision-relevant table in the document [B]

Chartbeat referral mix across **~3,750 publisher sites**:

| Source | Share |
|---|---|
| Google Discover | **25.7%** |
| Direct | **20%** |
| Google Search | **14.9%** |
| Facebook | 4% |
| X | 0.4% |
| **YouTube, Instagram, LinkedIn, Threads, Reddit, Pinterest** | **each <0.5%** |

> **Every channel in the MacroChipz growth plan except email sits in the "<0.5%" row.**

### 10.2 Search is the worst-timed bet in the plan [A/B]

- **Pew, primary browsing research** (KnowledgePanel, n=900 US adults, real browsing data, **68,879 Google searches**, March 2025): users clicked a traditional result in **8% of visits with an AI Overview vs 15% without**. Clicks on links *inside* AI summaries: **1%**. Users **ended their session after 26% of AI-summary pages vs 16%**. ([Pew](https://www.pewresearch.org/short-reads/2025/07/22/google-users-are-less-likely-to-click-on-links-when-an-ai-summary-appears-in-the-results/)) **This is the most rigorous single piece of evidence in the report, and it targets exactly the definitional query class MacroChipz would compete for.**
- **Reuters Institute / Chartbeat (2,576 sites, to Nov 2025):** Google organic **−33% globally, −38% US** YoY; Discover **−21%/−29%**; all external referrals **−24%** since May 2023. Publishers expect search traffic to **fall >40% over three years**. **Google SEO is the channel publishers are cutting hardest (net −25); YouTube is the one they are increasing most (net +74).**
- **Press Gazette (Aug 2026):** traffic to the top 10 US news sites **−32%** over two years; CNN's search traffic **−61%**. Generative-AI referrals average **0.4%** of total traffic; ChatGPT is **0.02%** of publisher referrals.
- **YMYL is specific and severe.** Google's own documentation says topics affecting **health, finances or safety** get *"even more weight to content that aligns with strong E-E-A-T,"* and flags *"writing about topics solely for search traffic without genuine expertise"* as a red flag. **Finance is the hardest possible SEO category for an unknown site.**

**Independent corroboration from a second dataset:** §5.3's finding that mature Wikipedia reference articles lost ~30% of pageviews YoY is the same AI-answers effect visible elsewhere.

### 10.3 Platform-by-platform [A/B]

| Channel | Intent | Shelf life | Realistic web traffic |
|---|---|---|---|
| **YouTube long-form** | **Best on any platform: 55% of YouTube news users say they are *intentionally* getting news there; 23% watch >20-min videos weekly** | Longest (search + suggested) | **~0. Build for audience, monetise on-platform.** |
| **YouTube Shorts** | Passive | Days | ~0. YPP threshold is **10M Shorts views in 90 days**. |
| **TikTok** | **Incidental — 54% of TikTok news users encounter news while browsing for something else; 55% watch <2 min** | Hours–days | **~0.** Condé Nast: link-in-bio *"hasn't proven to be a strong driver of referral traffic."* TikTok's own docs: **"neither follower count nor whether the account has had previous high-performing videos are direct factors"** — every video restarts from zero. |
| **Instagram Reels** | Passive | Days | **~0.** WaPo: *"We don't expect a platform like Instagram to be sending a ton of people to our website."* Instagram's ranking doc lists **no external-link signal**. |
| **Email** | **Owned, intentional** | **Permanent** | **Real — the only compounding asset.** |
| **Google Search** | High intent | Long but eroding fast | **Poor and worsening** (§10.2). |
| **LinkedIn** | Professional | Medium | **~0.** BBC: *"Don't treat it as a traffic play, full stop."* |
| **X** | News-seeking | Hours | **~0, and links are penalised.** Chartbeat traffic **−70% since 2022**. |
| **Threads** | Casual | Hours | **<1% but the only one growing** — Newsweek's Threads referrals up 20-fold in 2025 off 160K followers vs 3.5M on X. Cheap option; needs daily cadence. |
| **Podcasts** | Intentional, loyal | Long | **~0 web traffic, excellent depth. 58% of Americans 12+ (167M) consumed a podcast in the last month** (Edison Infinite Dial 2026, probability sample). |

### 10.4 What this means, stated without hedging

**The proposed model — "social video and search feed users into MacroChipz" — is not supported by any evidence found.** The convergence across Chartbeat, Reuters Institute, Pew, and on-the-record testimony from WSJ, FT, BBC, WaPo, Condé Nast and BDG is the most robust finding in this document.

**The viable shape is the inverse:**

> **Newsletter-first, with video as top-of-funnel for the *channel* (not the site), and the website as a permanent evidence library that the newsletter and video both cite into.**

This is also exactly the pattern of every successful comparable (§8.7): Morning Brew, The Hustle, Industry Dive, Semafor, Apricitas — all newsletter-native. And it is the pattern of the one survivor at Robinhood: **the newsletter lived; the destination site died.**

### 10.5 The one distribution pattern worth copying exactly

**Politano's link-the-claim technique** (§8.7): the chart is a static image, but **the sentence making the claim is a hyperlink to the live series.** That is:

- The *entire* evidence-backed concept, proven at 83K readers
- Trivially implementable
- Exactly what MacroChipz's deterministic evidence model was built to serve
- **And nobody has built the tooling for it.** Politano does it by hand, per post.

> **The single most defensible product MacroChipz could build might not be a dashboard at all. It might be the permanent, citable, point-in-time-correct evidence page that a claim links to** — the thing Politano needs and currently improvises with FRED permalinks (which, note, MacroChipz cannot legally use for the same purpose — §6.7).

### 10.6 Video: a caution and a correction

**Two honest cautions.** (a) Short-form finance video is drowning in AI slop (1 in 5 top videos), so "video" alone is a liability, not an asset. (b) Nobody has demonstrated that evidence-linked video *converts* — Politano's pattern works in text and has no video equivalent yet.

**One correction to received wisdom** [C, but the only methodology-bearing dataset found]: AIR Media-Tech, 300 channels, 3,595 monetised channel-months, medians read from YouTube Studio — **Education & Science: $10.22 median RPM, the top niche.** All-niche median ~$2.30. **Business & Finance: $2.01 median RPM — *below* the all-niche median.** (Business & Finance is asterisked as <10 channels, "directional.") Corroborating: LocaliQ 2026 puts **Finance & Insurance at $3.39 average CPC vs a $5.42 all-industry average** — below average.

> **Testable implication, worth an experiment rather than an assertion: framing and classifying the channel as *educational/explainer* rather than *finance/markets commentary* may materially improve ad RPM — the opposite of the received wisdom.**

### 10.7 The blocker: zero distribution infrastructure exists [MEASURED]

A search of `frontend/` and `app/` for sitemap, robots.txt, Open Graph tags, meta description, canonical URLs, email, newsletter, analytics and share affordances found:

- `index.html` has **charset, viewport, color-scheme and `<title>` only**
- **No `og:image` / `og:title` / `twitter:card`** → every shared MacroChipz link currently renders as a **bare URL with no preview card on every social platform**
- **No meta description, no sitemap.xml, no robots.txt** → no search surface
- **No analytics** → **we cannot measure any of the behaviours the thesis depends on** (return rate, share rate, exploration depth)
- **No email capture** → the one owned, algorithm-independent channel does not exist
- SPA with client-side routing and **no prerender** → deep links and crawlability are unproven

> **The entire acquisition thesis rests on infrastructure that is 0% built. It is cheap to fix — roughly a week — but until it is, most of §20's experiments cannot run at all. That ordering determines the Day-1 sequence.**

---

## 11. Sponsorship / Media Findings

No financial model is built here, per the brief. **No CPM below is estimated; every figure is quoted with its source and source type.**

### 11.1 Published newsletter CPMs [C — vendor/marketplace self-reported]

**Paved** ([guide](https://www.paved.com/blog/the-ultimate-newsletter-sponsorship-guide/)), "most rebooked newsletters," no sample size or period disclosed:

- **General interest / broad audience: $6.53 CPM · $4.96 CPC**
- **Highly targeted / premium niche: $23.01 CPM · $18.36 CPC**
- **Critical nuance: Paved defines CPM here as cost per 1,000 *subscribers*, not per 1,000 opens.** That is why this is an order of magnitude below the "$20–$80" figures quoted elsewhere, which are per-1,000-opens. **Confusing these two is the commonest error in this market.**
- **Conflict of interest: Paved is owned by Redbrick, which also owns Quartz.** Not a disinterested source.

**beehiiv** ([ad network](https://www.beehiiv.com/ad-network)): pays **CPM on unique opens** and/or **CPC on verified clicks**; illustrative examples "$5 CPM" and "$2 CPC"; **no rate card, no published subscriber minimum**. Cumulative: *"$37,872,727 — the amount beehiiv creators have earned so far."*

**Who Sponsors Stuff** publishes target **CPC**: consumer/general interest ≈ **$1**, interest-based ≈ $2, **financial/professional $3–$4**, B2B $6–$8+.

**Swapstack, Sponsy, Kit Sponsor Network, Substack: no published CPM figures found.**

### 11.2 The one genuinely comparable data point [B]

**1440** — a free, ad-supported, general-interest explainer newsletter, the nearest published analogue ([Digiday, 2025-03-26](https://digiday.com/media/why-1440-prefers-cpms-for-its-newsletter-business-over-other-pricing-models/)):

- **4.5M subscribers**, growing ~1M/year; **65% open rate**; readers click **2.2 links per opened issue**
- Charges **a combined ~$50 CPM** ($40 above-the-fold + $10 scroll unit)
- CEO: *"We did almost purely CPA deals when we were smaller, but as we've gotten bigger, we have some operating leverage."*

> **A general-interest explainer newsletter had to sell on CPA until it hit real scale, and only then commanded ~$50 CPM. The gap between Paved's $6.53/1,000-subscribers and 1440's $50/1,000-opens is the entire commercial question for MacroChipz.**

### 11.3 What sponsors actually ask for [A/B]

- **Clicks, not opens.** Paved (2026): *"When evaluating a newsletter, ask for click data — not open data."*
- **Why: Apple Mail Privacy Protection broke open rates.** **Litmus (July 2026, >1 billion opens): Apple = 62.26% of email opens.** **Omeda measured the inflation directly** (~80,000 deployments, ~2 billion emails): total open rate went **22.6% → 40.5%**, unique **15.2% → 29.0%** pre/post MPP.
- **Subscriber count + open rate + CTR per title.** The Daily Upside publishes exactly this triplet: **800K subs / 40% open / 3.01% CTR**.
- **Audience job titles and geography** — tier-one (US/UK/CA/AU/NZ) share is an explicit *binding* criterion on the display side (§11.5).

**Email benchmarks, both stale — flagged:** Mailchimp **Business+Finance 31.35% open / 2.78% click** (*"last updated in December 2023"*). Campaign Monitor **Media/Publishing 23.9%/2.9%; Financial Services 27.1%/2.4%** (2021 data). Both pre-date or are contaminated by MPP.

### 11.4 Audience size gates [A — hard, published]

| Gate | Published requirement |
|---|---|
| **Paved — scheduled flat-fee ads** | **Minimum 50,000 subscribers** |
| **Paved — dynamic native (PPC)** | **1,000,000 monthly impressions** |
| **Paved — pricing floor** | *"the minimum price should be $200 or more"* per placement |
| **beehiiv Ad Network** | No subscriber minimum; Scale plan ($43/mo) |
| **Swapstack** | No minimum |
| **Mediavine Journey** | 1,000 monthly sessions (higher tiers gated on *revenue*) |
| **Raptive** | **25,000 monthly pageviews** — but **sites at 25K–99,999 need 50% of traffic from tier-one markets; 100K+ need 40%** |
| **Ezoic** | **250,000 monthly users** |

**The Paved 50,000-subscriber minimum is the most concrete viability anchor in the category.** At Paved's published general-interest benchmark, a 50,000-subscriber list earns roughly **$325 per sold placement** (arithmetic on their two published figures, not a quoted rate).

**Two buried landmines:**

1. **The general-interest discount is 3.5×** ($6.53 vs $23.01). *"The US economy for non-economists"* sits on the **low** side unless it can be sold as reaching a specific monetisable professional cohort. **This is an argument for the homebuyer/mortgage wedge over the general-consumer wedge** — mortgage intent is a high-value, specifically monetisable cohort.
2. **Growth via TikTok/Shorts can disqualify you from premium display.** Raptive will not take a site under 100K pageviews unless **half its traffic is tier-one.** Short-form video skews global. *The acquisition plan and the monetisation plan are in direct tension.*

### 11.5 The free-website display leg is the weakest and is deteriorating [B]

- **Ozone (~20 billion impressions), Q2 2026 YoY:** publisher ad request volumes **−32% to −37% US**. H1 2026 US programmatic spend **−44%**. eCPMs rose slightly while volume collapsed. Named cause: declining referral traffic as platforms answer queries directly.
- **eMarketer 2025:** open auctions **$14.67bn vs private marketplaces $29.52bn** — **the open auction, the only thing a small independent site can access, is now the minority of programmatic spend.**
- **Ad blocking ~29.5% globally, 32.5% US** — a technically-literate audience is the worst case.
- **Third-party cookie deprecation is off the table** — Google confirmed Apr 2025. **Do not model it as a risk.**
- **No display RPM benchmarks are published by Raptive, Mediavine or Ezoic.** [UNKNOWN]

### 11.6 Conclusion on monetisation

**Display advertising on a free website is the weakest available path and is structurally declining.** Newsletter sponsorship is the strongest, gated at ~50,000 subscribers. **Neither is reachable for a long time, which is the correct reason not to build for it now.** The brief's own instruction stands and is reinforced by the evidence: **optimise for attention → understanding → sharing → return, not for monetisation.**

**The methodology separation stated in the brief must be written into the product's public standards page from day one:** sponsorship must never influence methodology, states, Radar findings, evidence or conclusions. Given that *"isn't trying to sell me something"* is Gen Z's **#2 trust criterion, ranked higher by non-investors** (§4.4), this separation is not merely ethical hygiene — **it is the product's principal competitive asset against the finfluencer field, and it should be marketed as such.**

---

## 12. Dream Homepage Feasibility

Each of the ten proposed components, assessed against the evidence above.

### 12.1 Economic Pulse

| | |
|---|---|
| **User value** | High — it is the "what is happening" answer, and the product needs one |
| **Audience** | All segments |
| **Data / sources** | Already built. BLS/BEA via direct APIs post-migration |
| **Licensing confidence** | **High** (public domain at source) |
| **Update frequency** | Monthly per domain |
| **Engineering** | **Already done** (`inflation_v1.0`, `labor_v1.0`, `rates_v1.0`) |
| **Differentiation** | **LOW — commodity.** CFNAI since 2001; ≥5 free consumer equivalents (§8.3) |
| **Risks** | Building the product's identity on it |
| **Recommendation** | **DAY 1 — as furniture, not as the pitch.** Ship it because the product needs an entry point. Never sell the product on it. |

### 12.2 What's Moving

| | |
|---|---|
| **User value** | Moderate |
| **Data** | Already built — **[MEASURED] 14 inflation + 9 labor = 23 change events live today** |
| **Honest constraint** | **Refreshes ONCE PER MONTH per monitor, on its release — not continuously.** Composition is mostly `METRIC_CHANGED` deltas ("r_3m went 3.11% → 3.05%"); only a minority are `STATE_CHANGED`. Inflation currently shows `any_state_changed=False`. |
| **The trap** | **A "feed" UI implies a freshness the underlying data does not have.** |
| **Differentiation** | Low-moderate. RecessionPulse ships a free daily briefing; recessiondashboard.com ships ▼▲ markers and a "What to Look For Next" section |
| **Recommendation** | **DAY 1, RENAMED.** Ship it as **"What changed at the last release"** — not a scrolling feed. And note the structural bind: **state changes are rare *by construction* (that is what a deadband is for). Good methodology directly limits content volume.** |

### 12.3 MacroChipz Radar

| | |
|---|---|
| **User value** | Potentially very high — if the output is a sentence |
| **Honest constraint** | **§13 in full. Radar can be honest or frequent, not both.** |
| **Differentiation** | Math is commodity (a 0-star GitHub repo does 85% of it); **consumer-sentence framing is rare** |
| **Major risk** | **Manufacturing false narratives — the specified flagship example is already one** (§13.5) |
| **Recommendation** | **NEEDS VALIDATION → LATER.** Not Day 1. Requires deep re-ingestion (§7.6), a pre-registered scan, BH-FDR correction, TOST equivalence testing, and vintage stamping. **And it must be architecturally capable of publishing "nothing unusual this month," which it will say most months.** |

### 12.4 Explore the Economy

| | |
|---|---|
| **User value** | High for the 20% who go deep |
| **Data** | Inflation/Labor/Rates exist. **Housing, Consumer, Growth hold ZERO data today** [MEASURED] |
| **Licensing** | Census (retail, housing starts) and BEA (GDP, PCE) are both clean [VERIFIED] |
| **Recommendation** | **DAY 1 for the three that exist; LATER for the three that do not.** Adding Housing is the highest-value expansion because it serves the recommended wedge — but it needs the mortgage-rate licensing question resolved first (§6.8). |

### 12.5 Revisions + Economic Time Machine

| | |
|---|---|
| **User value** | **The highest differentiation in the set** |
| **Data** | **Forward-only from #31 is ours and unencumbered.** Backward requires archived agency release PDFs (legal) or ALFRED (not legal) |
| **Licensing confidence** | **High forward; blocked backward via ALFRED; LIKELY via BEA's own vintage archive** |
| **Honest constraint** | **[MEASURED] 1,072/1,072 versions are backfilled; 0 genuinely observed; 0 REVISED events ever captured.** The claim must never exceed this. |
| **Differentiation** | **Highest — zero products, unregistered domains, unmet demand shock** (§8.2) |
| **Risk** | **"What did the data say in March" is not something people ask unsolicited.** Needs the news-pegged framing: *"the number you remember was wrong."* |
| **Recommendation** | **DAY 1 — this is the product.** Split it: **Revision Intelligence** ships Day 1 (the sign test, §7.4, plus prominent revision marking). **Time Machine** ships as it accumulates, honestly labelled "since MacroChipz started watching." |

### 12.6 Today in the Economy

| | |
|---|---|
| **Honest constraint** | **[MEASURED] 23.8% of business days have any release.** The only daily signal is the Treasury curve |
| **Recommendation** | **REJECT as specified.** A live daily timeline would manufacture the appearance of activity that does not exist. **Replace with a release-driven "latest release" view.** This is the clearest case in the document of a feature that looks impressive and would be dishonest. |

### 12.7 Economic Calendar

| | |
|---|---|
| **Data** | **BLS iCal + BEA JSON/ICS are free and machine-readable** [VERIFIED]. Census is HTML/PDF only — needs a scraper. Treasury/NY Fed/DOL have none found |
| **Licensing** | Clean |
| **Value** | **Underrated.** It is the honest answer to "when will there be something new," it is the natural alert surface, and it is how a monthly-cadence product stays useful between releases |
| **Recommendation** | **DAY 1.** And it replaces the FRED releases API, which is the stickier FRED dependency (§7.7). |

### 12.8 MacroChipz Brief

| | |
|---|---|
| **Honest constraint** | **Daily is unsupported** (§7.1, §5.2). **Weekly or release-driven is supported** |
| **Distribution** | **Email is the only channel with real referral value** (§10.1) and the only one every successful comparable used |
| **Recommendation** | **DAY 1 — as the primary product surface, not a secondary channel.** Release-driven plus a weekly wrap. **This is the inversion the evidence demands: the newsletter is not a marketing channel for the site; the site is the evidence library for the newsletter.** |

### 12.9 Economic Education ("Wait, Seriously?")

| | |
|---|---|
| **Evidence** | **The strongest demand evidence in the document.** 66% mortgage-rate misconception; 48-point SHED perception gap; financial literacy at a decade low; clean keywords; a dated supply vacuum (§9.4) |
| **Constraint** | Do not use "inflation"/"recession" as head terms (§5.7) |
| **Differentiation** | Moderate on concept, **high when each explainer links its claims to live, point-in-time-correct evidence** (§10.5) |
| **Recommendation** | **DAY 1 — the volume engine.** This carries the ~22 days a month that releases cannot. |

### 12.10 Follow the Economy

| | |
|---|---|
| **Value** | High retention potential — but **only if notifications are rare** |
| **Constraint** | Honest triggers are **rare by construction**: state changes are deliberately dampened, material revisions exceed ~118k, Radar findings are 0–3/month |
| **Recommendation** | **DAY 1 in the cheapest possible form: email-only, release-driven.** No push, no SMS, no per-indicator granularity. Granularity implies frequency the data does not support. **Deferring this costs the one owned channel, so it cannot be deferred — but it must be small.** |

---

## 13. MacroChipz Radar Feasibility

**Bottom line: Radar can be built honestly, but only if it is redesigned from "anomaly detection" into "exact decomposition plus agency-published uncertainty." The version implied by the brief's two examples is not honestly buildable as stated.**

### 13.1 The frequency/honesty tradeoff is arithmetic [MEASURED]

Computed on MacroChipz's actual 59 monthly changes per series:

| Series | n | mean % | sd % | >2σ events | % of obs |
|---|---|---|---|---|---|
| CPILFESL | 58 | 0.326 | 0.150 | 3 | 5.2% |
| PCEPILFE | 58 | 0.303 | 0.131 | 3 | 5.2% |
| PAYEMS | 59 | 0.125 | 0.138 | 4 | 6.8% |
| UNRATE | 58 | −0.010 | 0.126 | 1 | 1.7% |

**At a 2σ bar, each series yields roughly one "unusual" reading every two years. Running 40 monthly tests (20 series + 20 relationships) produces ~1.8 findings per month by chance alone, with no real signal present.**

### 13.2 Multiple comparisons, quantified

Under the null, |z|>2 flags 4.55% of tests; |z|>3 flags 0.27%.

| Scan design | Tests/mo | False flags/mo at \|z\|>2 | at \|z\|>3 | Bonferroni \|z\| for FWER 5% |
|---|---|---|---|---|
| 20 series × 3 transforms × 2 windows | 120 | **5.5** | 0.32 | 3.53 |
| 50 series × 4 transforms × 3 windows | 600 | **27.3** | 1.62 | 3.93 |
| Pairwise divergences: C(50,2) × 3 windows | 3,675 | **167** | 9.9 | 4.35 |
| Combined | 4,275 | **195** | 11.5 | 4.38 |

At 600 tests/month and |z|>2, **P(at least one false finding this month) = 1.0000**, accumulating **328 false findings per year**. Even the modest 120-test scan produces **65 per year**.

**Two subtleties that matter.** First, **when there are no true signals, Benjamini-Hochberg degenerates exactly to Bonferroni** — FDR only buys power when real signals exist, which in a monthly macro scan is usually not the case. Second, **dependence cuts both ways**: macro series are driven by a handful of common factors, so the effective number of independent tests is smaller (if r≈5 factors span the panel, T_eff ≈ 60 and the bar falls to |z|>3.34) — **but the same dependence means false findings arrive in correlated clusters. You do not get 27 scattered flags; you get one factor moving and 27 series "independently confirming" it. That looks like corroboration and is not.**

**The cadence answer:**

- **Pre-register the scan** — fixed series list, transforms, windows, thresholds, published in advance. If T floats, no honest p-value exists.
- **BH-FDR at q=0.10 against the pre-registered T.** For a disciplined scan (T ≈ 120), surfacing 3 findings requires **|z| ≳ 3.0**.
- **Honest output: 0–3 findings per month, frequently zero.**
- **De-duplicate across months** — under ρ=0.9 a flag persists 2.3 months on average (max 16 in simulation). Re-reporting it is double-counting one draw.

> **A feature that guarantees N findings per month is a false-narrative machine regardless of the statistics behind it. Radar therefore cannot be the thing that fills a publishing calendar. That single sentence resolves the Radar question.**

### 13.3 The low-frequency problem, with the agencies' own numbers [VERIFIED]

**BLS, Employment Situation Technical Note:** *"the confidence interval for the monthly change in total nonfarm employment from the establishment survey is on the order of plus or minus 122,000."*

| Span | 90% CI, total nonfarm | Implied per-month bar |
|---|---|---|
| 1 month (1st release) | **±122,281** | ±122,281 |
| 3 months | ±168,925 | **±56,308/mo** |
| 6 months | ±215,205 | **±35,868/mo** |
| 12 months | ±280,778 | **±23,398/mo** |

> **A +50k, +75k, +100k or even +122k payroll print is statistically indistinguishable from zero.** Any Radar finding built on a single month's payroll change below ~122k is a false narrative, full stop.

**How long until "payroll growth is weakening" is honest?** Minimum detectable slowdown at 90%: **3m vs prior 3m: 79,600/mo · 6m vs prior 6m: 50,700/mo · 12m vs prior 12m: 33,100/mo.** **Answer: roughly 6–12 months.** Widening further does not help — BLS's *"absolute average benchmark revision… 0.2 percent"* is ≈320,000 jobs, or ~26,700/month, which **already exceeds the 12-month sampling CI of 23,400/month.** Beyond about a year, benchmark error dominates and precision stops improving.

**CPS live thresholds** ([bls.gov/web/empsit/cpssigsuma.htm](https://www.bls.gov/web/empsit/cpssigsuma.htm), August 2026 reference month): **unemployment rate 0.21pp · household employment 675,000 · LFPR 0.24pp · emp-pop ratio 0.25pp.**

**CPI is the honest counterexample.** BLS: *"The estimated standard error of the 1-month percent change is 0.04 percent for the U.S. all items CPI."*

| Item | median 1-mo change | 1-mo SE | \|t\| | Monthly signal? |
|---|---|---|---|---|
| All items | 0.25 | **0.04** | 6.2 | **Yes** |
| Core | 0.25 | 0.05 | 5.0 | **Yes** |
| Shelter | 0.33 | 0.08 | 4.1 | **Yes** |
| Medical care | 0.25 | 0.12 | 2.1 | Marginal |
| **Energy** | 0.07 | **0.14** | 0.5 | **No** |
| **Apparel** | −0.29 | **0.37** | 0.8 | **No** |

> **The key design insight: the honest Radar bar is series-specific, not global.** Monthly CPI headline and core moves *are* real signals. Monthly payroll moves are *not*. Monthly energy and apparel moves are *not*. **A uniform z-score threshold across a macro panel is statistically incoherent, because measurement error varies by an order of magnitude across series.**

**Retail sales:** median SE of the m/m percent change = **0.2pp**, so a print must exceed **~0.33%** to clear 90% on sampling error alone. **+0.2% and +0.3% prints are noise.**

**Critical caveat:** published CIs measure *survey error* ("is this print different from zero?"); historical volatility measures *real variation* ("is this month unusual vs the past?"). **They answer different questions and are not interchangeable.** Most series have no published SE at all — for those, MacroChipz can make ordinal/historical statements but **cannot** make significance claims, and must never silently substitute historical SD for measurement error.

### 13.4 Technique assessment

**SHORTLIST — build these:**

1. **Contribution / identity decomposition — the core primitive.** Exact arithmetic: *"Shelter contributed 0.10pp of the 0.25pp rise in CPI."* Deterministic by construction, **zero false positives because no inference is performed**, one-sentence explainable, trivially cheap. **This, not anomaly detection, is how "signals hiding beneath the headlines" should be surfaced.**
2. **Agency-published significance flags.** Use the agencies' own uncertainty rather than inventing our own: *"BLS's own standard is that a payroll change under 122,000 can't be told apart from zero — this month's was 85,000."* **Makes MacroChipz credibility-increasing rather than narrative-generating. Its most valuable output is the negative finding.**
3. **Diffusion / breadth indices**, using BLS's published formula (0 decrease / 50 unchanged / 100 increase, averaged across industries over 1/3/6/12-month spans). Ordinal, distribution-free, exact binomial CI, already an official statistic. *"58% of industries added jobs last month, down from 64%."*
4. **Percentile rank vs own history, on a single pre-registered window** — **not** z-scores. State the ordinal fact (*"the fastest since March 2019"*), true by construction, no distributional assumption. **One window only** — offering 5y/10y/full is three shots at the same target.
5. **Revision-direction sign test** (§7.4). The best candidate in the set for the *spirit* of Radar.

**REJECT — and why:**

| Rejected | Reason |
|---|---|
| **Cointegration / spread deviation** | **81–88% spurious rejection on independent random walks**; and "the spread should revert" is a forecast |
| **Chow / Bai-Perron break tests** | **99.6–100% false break rate on persistent series, even at correct critical values.** Guaranteed to "find" a regime change every time |
| **Markov-switching** | Not deterministic (EM local optima, label switching, seed dependence); needs 200+ obs; regime probabilities are forecasts |
| **Rolling correlation** | **40% chance of \|r\|>0.5 between two independent random walks at a 36-month window.** "They stopped moving together" is the most seductive false narrative available |
| **CUSUM** | False alarm every 26–51 months on autocorrelated noise |
| **Mahalanobis distance** | **1,275 covariance parameters from 792 observations** at 50 series. Ill-conditioned by construction; zero explainability |
| **Surprise indices (Citi CESI-style)** | Requires a proprietary, revisable consensus panel → **fails reproducibility**; and measuring against a forecast is predictive framing |
| **2nd difference / acceleration** | **√6 noise amplification. The 90% CI on payroll *acceleration* is ±173,000 jobs/month** |
| **Raw rolling z-scores as the primary detector** | False-positive rate **up to 2× nominal under persistence** (9.3% at ρ=0.9 against a nominal 4.55%); flags cluster 2–3 months and get re-reported as confirmation; window length is an undisclosed researcher degree of freedom; **"z = 2.3" is not layperson-explainable.** Use percentile rank |
| **Cross-survey divergence (CES vs CPS)** | §13.5 |

### 13.5 The flagship example fails — in three separate ways

*"Payroll growth is weakening while the headline unemployment rate remains relatively stable"* is **not a defensible finding.** It is three artifacts stacked.

**Artifact 1 — different instruments with incompatible resolution.** BLS's own documentation: CES is *"an estimate of jobs (multiple jobholders are counted for each nonfarm payroll job)"*; CPS is *"an estimate of employed people."* Different universes, different reference periods. **The household survey cannot see a change smaller than 675,000 people; the payroll survey resolves 122,000 jobs. CPS is physically incapable of confirming or denying a CES-scale move** — so "CES moved and CPS didn't" is *guaranteed* to occur whenever a real move sits between 122k and 675k, with **zero information content.**

**Artifact 2 — the unemployment rate is a ratio, and its denominator moved.** Fed staff estimate breakeven employment growth has collapsed: 1970s ~185k/mo → 2010s ~80k → 2023-24 ~155k → 2025 ~85k → **2026 projected "nearly zero."** The FEDS Note states that at near-zero breakeven, *"negative job growth would be almost as likely as positive job growth in any given month"* even with the economy at potential ([Murray & Vidangos, FEDS Notes, 2026-04-02](https://www.federalreserve.gov/econres/notes/feds-notes/labor-force-growth-breakeven-employment-and-potential-gdp-growth-20260402.html)). **Falling payroll growth with a flat unemployment rate is the expected arithmetic signature of slowing labour supply.** To claim otherwise, Radar would have to assert a breakeven estimate — which is a model, and crosses into inference.

**Artifact 3 — "stable" is an accepted null, and accepting a null is not a finding.** *"Payroll growth weakening"* needs a >50,700/month deceleration over 6 months. *"Unemployment rate stable"* is asserted from a *failure* to exceed 0.21pp per month — but the rate could drift 0.4pp over six months while never once triggering a monthly flag. **The two legs of the sentence use incompatible evidentiary standards.**

> **The "while X remains stable" construction is the single biggest false-narrative generator in the Radar design.** Every such statement is a compound claim: *reject* the null for the moving series AND *accept* the null for the stable one. **Any such template must require an equivalence test (TOST) on the stable leg: its confidence interval must lie entirely inside a pre-declared "trivially small" region, not merely contain zero.**

**Multiplicity makes it worse:** simulation of two *independent* pure-noise series under a "one up, one down" rule gives a false divergence **once every 16–19 months per pair** at ±1σ. Across C(50,2)=1,225 pairs that is **~62 false divergences per month.** **Divergence scanning has the worst multiplicity-to-signal ratio of anything in the brief.**

**The second example works — and for a generalisable reason.** *"Long-term yields are rising while market-implied inflation compensation remains comparatively stable"* is sound, but **not because it detects anything.** Nominal yield ≡ real yield + breakeven inflation. It is an **identity**: nominal up + breakeven flat ≡ real yield up. Daily market data, no sampling error, no revisions, no seasonal adjustment, no estimation. **Identity/contribution decomposition is the honest core of Radar. Anomaly detection is the part that does not survive scrutiny.**

**What would make a divergence honest** (all four required): (1) both series on the **same instrument**; (2) the "stable" leg passes **TOST** against a pre-declared trivial region; (3) the moving leg clears its own published CI over a **≥6-month window**; (4) the pair is **pre-registered**. *The yields example passes all four. The payrolls example fails 1, 2 and 3.*

### 13.6 The determinism trap

**"Same inputs → same output" is satisfiable, but not by pinning the code. The data vintage must be pinned.**

BLS *"revises the historical seasonally adjusted data for the previous 5 years"* every year after re-estimating CPS seasonal factors; CES is re-benchmarked annually. **Therefore a rolling percentile, z-score or diffusion index recomputed next February on the *same* nominal series will give a *different* answer for the *same* historical month. Last month's Radar finding can silently cease to exist.**

> **Every Radar finding must carry a data vintage stamp and be recomputable from that archived vintage. Without vintage pinning, the determinism constraint is not merely unmet — it is unmeetable, and Radar's own archive would quietly contradict itself.**

**This is, notably, the one requirement MacroChipz is uniquely positioned to satisfy.** Increment #31's append-only `observation_versions` and deterministic replay are exactly the machinery Radar needs. **Radar is infeasible for most people and feasible for MacroChipz — but only in the rare, high-bar form described above, and only after deep re-ingestion (§7.6).**

---

## 14. Opportunity Matrix

Qualitative ratings with reasoning; no false numerical precision.

| Opportunity | Audience Interest | Frequency | Data Quality | Licensing | Revision Value | Shareability | Video | Search | Alerts | Engineering | Differentiation |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Payroll revisions / benchmark** | **Med-High** — spiked hard in 2025-26 news; latent otherwise | Monthly + annual benchmark | **Excellent** — BLS publishes the full revision distribution | **Clean** (BLS public domain) | **HIGHEST** — this IS the revision story | **High** — "the number you remember was wrong" | **High** | Low (jargon, ambiguous head terms) | **Yes** — >118k threshold | Low-Med | **HIGHEST — zero competitors** |
| **Mortgage rates ↔ Treasury 10Y** | **HIGHEST** — 66% misconception, clean keywords, decisional | Daily (10Y) / weekly (PMMS, unusable) | Excellent (Treasury) | **Treasury clean; PMMS BLOCKED** | Low | **High** | **High** | **HIGHEST** — clean, high-intent | Yes | **Low — already built** | **High** — two free explainers just exited |
| **CPI components / contributions** | High | Monthly | **Excellent** — CPI SE 0.04% | Clean (BLS) | Med (SA revised 5y) | Med-High | Med | **Poor** — "CPI"/"inflation" ambiguous | Yes | Low | Med — decomposition is rare, not unique |
| **Initial claims** | Low-Med | **Weekly** — best cadence available | Good | Clean (DOL PD) | **High** — self-documenting revisions | Low | Low | Low | Yes | **Med** — PDF parsing, flaky endpoint | Med |
| **Treasury yield curve** | Low direct, **High as a bridge** | **Daily — the only daily signal** | Excellent | **Best-in-class — no key, no restriction** | None | Med | Med | Low direct | Yes | **Already built** | Low standalone |
| **GDP revisions** | Med | Quarterly | Excellent | Clean (BEA) | **High** — 1.2pp advance→latest | Med | Med | Med ("is the economy shrinking") | Low | Med | **High** — BEA's own vintage archive is the legal path |
| **Retail sales** | Med | Monthly | Good (SE 0.2pp) | Clean (Census) | Med | Med | Med | Med | Yes | Med (no iCal calendar) | Low |
| **Housing starts / permits** | Med-High (wedge-adjacent) | Monthly | Good (±3.8% revision) | Clean (Census) | Med | Med | Med | Med | Yes | Med | Med |
| **JOLTS (quits/openings)** | Med | Monthly | Good | Clean (BLS) | Med | **High** — "the great resignation" framing | High | Med | Yes | Low | Med |
| **SOFR / money-market rates** | **Low** | Daily | Excellent | **⚖️ copyleft conditions** | Partial (`revisionIndicator`) | Low | Low | Low | Low | Low | Low |
| **Consumer sentiment** | High | Monthly | — | **UMich PROHIBITED (#28); Conference Board unverified** | — | High | High | Med | — | — | **Blocked** |
| **"Why prices don't fall" explainer** | **HIGHEST** | Evergreen | N/A | N/A | N/A | **High** | **High** | **High** (avoid "inflation" as head term) | No | **Lowest** | Med |

---

## 15. Dream-to-Reality Matrix

| Dream Experience | Information Needed | Source(s) | Cost | Rights Confidence | Update Frequency | Can Calculate Honestly? | Content Potential | **Build Decision** |
|---|---|---|---|---|---|---|---|---|
| **Economic Pulse** | Current state per domain | BLS, BEA (direct) | $0 | **High** | Monthly | **Yes — already shipped** | Low (commodity) | **DAY 1 — as furniture** |
| **What's Moving** | Change events vs prior release | Own engine | $0 | High | **Monthly, not continuous** | **Yes** | Medium | **DAY 1 — renamed "what changed at the last release"** |
| **Radar** | Deep history + pre-registered scan + vintages | BLS/BEA/Census + own archive | $0 | High | 0–3 findings/mo, often 0 | **Only in the restricted form of §13.4** | **Low — cannot fill a calendar** | **LATER — needs validation** |
| **Explore: Inflation / Jobs / Rates** | Already held | Own engine | $0 | High | Monthly / daily | **Yes** | Medium | **DAY 1** |
| **Explore: Housing** | Starts, permits, mortgage rates | Census ✅ / **PMMS 🛑** | $0 | **Mixed — mortgage blocked** | Monthly / weekly | Partially — **10Y as labelled proxy** | **High (wedge)** | **DAY 1 (partial, honestly labelled)** |
| **Explore: Consumer / Growth** | Retail sales, GDP, PCE | Census, BEA | $0 | High | Monthly / quarterly | Yes | Medium | **LATER** |
| **Revision Intelligence** | Revision history + published distributions | **BLS tables (clean)** | $0 | **High** | Monthly + annual | **Yes — sign test §7.4** | **HIGHEST** | **DAY 1 — the wedge** |
| **Time Machine (forward)** | Own observation versions | Own `observation_versions` | $0 | **Unencumbered** | Per release | **Yes, forward only from #31** | High | **DAY 1 — honestly scoped** |
| **Time Machine (backward)** | Historical vintages | **ALFRED 🛑 / BEA archive (LIKELY) / archived agency PDFs ✅** | $0 | **Blocked via ALFRED** | N/A | **NOT from our own data** [MEASURED] | High | **LATER — and never from ALFRED** |
| **Today in the Economy** | Daily meaningful activity | — | — | — | **23.8% of business days** | **NO — would manufacture activity** | Low | **🛑 REJECT** |
| **Economic Calendar** | Release schedules | **BLS iCal + BEA JSON** ✅ | $0 | **High** | Continuous | **Yes** | Medium | **DAY 1** |
| **MacroChipz Brief** | Everything above | Own engine | ~$0 | High | **Weekly + release-driven** | **Yes** | **HIGHEST** | **DAY 1 — as the PRIMARY surface** |
| **Economic Education** | Misconception research + live data links | Own + primary sources | $0 | High | Evergreen | **Yes** | **HIGHEST** | **DAY 1 — the volume engine** |
| **Follow the Economy** | Subscriber list + triggers | Own + beehiiv/Kit | **$0** | High | Release-driven | **Yes, if rare** | Medium | **DAY 1 — email only, minimal** |
| **Ask MacroChipz (Analyst)** | Bounded context packet | Own (#33) + OpenAI | **$0.38/1k req** | High | On demand | **Yes — already bounded and evaluated** | Medium | **DAY 1 — already shipped** |

---

## 16. Cost / Operational Implications

All prices read from vendor pages on 2026-09-20. Two JS-rendered pages (Render, Plausible) were parsed from their own embedded payloads.

### 16.1 Required now — production with real backups

| Line item | Source | Monthly |
|---|---|---|
| Render workspace — Hobby | render.com/pricing | $0.00 |
| Web Service — **Starter** (512 MB, 0.5 CPU), always on, no spin-down | render.com/pricing | **$7.00** |
| Render Postgres — **Basic-256mb** (paid ⇒ logical backups, 7-day retention + 3-day PITR) | render.com/pricing + docs | **$6.00** |
| Cron Job (per-second billing, **$1 minimum per cron service**) | render.com/docs/cronjobs | **$1.00** |
| Static Site — *"always free to deploy"* | render.com/pricing | $0.00 |
| Bandwidth — 5 GB/mo included on Hobby | render.com/pricing | $0.00 |
| DNS / CDN / SSL / DDoS — **Cloudflare Free** | cloudflare.com/plans/ | $0.00 |
| Analytics — **Cloudflare Web Analytics** (privacy-first, no cookie banner) | cloudflare.com/web-analytics/ | $0.00 |
| Transactional email — **Resend Free** (3,000/mo, 100/day) | resend.com/pricing | $0.00 |
| Newsletter — **beehiiv Launch** (≤2,500 subs) or **Kit Free** (≤10,000 subs) | beehiiv / kit | $0.00 |
| Domain — .com at $11.08/yr (Porkbun, incl. WHOIS privacy + SSL) | porkbun.com | **$0.92** |
| **TOTAL (excluding LLM)** | | **$14.92/month** |

**Honest caveat:** Basic-256mb gives Postgres 256 MB of RAM. It will run a <1 GB database for a low-traffic site but has little headroom for connection pools, concurrent queries or a vacuum under load. **The defensible production figure is Basic-1gb at $19/mo → $27.92/month.**

> **Quote $15/month as the floor and $28/month as the number that will not embarrass you at 3am.** Both include backups and PITR.

### 16.2 Near-zero-cost validation — $0.00/month

Render Free web service + **Neon Free** Postgres (**not** Render Free Postgres) + Cloudflare Pages + Cloudflare Web Analytics + beehiiv Launch.

**What you give up, ranked by how much it hurts:**

1. **The scheduled job does not reliably run.** A free Render service spins down after **15 minutes without inbound traffic** and runs nothing while down. **If the release-driven job is the product's heartbeat, this configuration does not actually validate the product.** Paying **$1 cron + $7 Starter = $8/mo** fixes it.
2. **No backups worth the name.** Neon Free gives a 6-hour history window and 1 snapshot.
3. **Cold starts** — the first visitor after 15 quiet minutes waits ~60 seconds. **Fatal for a link shared on social media**, where traffic is bursty.
4. No custom domain.

**Explicitly avoid Render's Free Postgres:** it **expires 30 days after creation** and has no backups — the database would disappear mid-validation. Neon Free scales to zero and wakes on connection; Supabase Free pauses after a week of inactivity and needs manual restoration.

### 16.3 LLM cost — measured, not estimated

Measured Analyst usage: **1,965 input + 140 output tokens per request.**

| Model | Per 1,000 requests | Per request |
|---|---|---|
| gpt-5-nano | **$0.15425** | $0.000154 |
| gpt-4.1-nano | **$0.25250** | $0.000253 |
| **gpt-4o-mini** (current) | **$0.37875** | **$0.000379** |
| gpt-5-mini | **$0.77125** | $0.000771 |
| gpt-4.1-mini | **$1.01000** | $0.001010 |

**Three observations that matter:**

1. **This workload is input-dominated — 93.5% of tokens are input**, and on gpt-4o-mini input is **78% of the cost.** **Optimise the prompt, not the response.**
2. **Prompt caching is the biggest lever.** At gpt-4o-mini's cached-input rate of $0.075/1M, total falls to **$0.23137 per 1,000 — a 39% saving**, contingent on the 1,965-token prompt qualifying for caching. [The cached-input *price* is verified; the minimum cacheable prompt length was not separately fetched — **UNKNOWN**.]
3. **Batch halves it again** but is asynchronous and therefore unusable for an interactive button.

**When does the LLM dominate?** Against the $14.92 floor: **~39,400 requests/month (~1,300/day) on gpt-4o-mini**; ~96,700/month on gpt-5-nano. Against the $27.92 config: ~73,700/month.

> **The LLM does not meaningfully threaten this budget until the site is successful enough that the budget has changed anyway.** The real risk is not organic volume — **it is an abusive script**, which is why the per-IP rate limiter shipped in #34 is the relevant control, not a model downgrade.

### 16.4 Useful later / scale cost

- **Plausible** $9/mo at 10k pageviews (only if goals/funnels are needed beyond Cloudflare's free tier); **Fathom** $15/mo for 100k pageviews, 50 sites.
- **Resend Pro** $20/mo for 50,000 emails if transactional volume outgrows the free tier.
- **beehiiv Scale** $43/mo above 2,500 subscribers — note this is also the tier required for the beehiiv Ad Network.
- **Descript** $16/mo (Hobbyist, watermark-free 1080p) if video is produced; **OpenAI transcription at $0.003–0.006/minute** is by far the cheapest captioning route (~$0.18–0.36 per hour of video).
- **YouTube / TikTok / Instagram cost $0 to upload and host.** There is no pricing page because there is no product being sold to the uploader. **Budget $0.**

### 16.5 Conclusion

> **Cost is not a constraint on any version of MacroChipz discussed in this document, and should not influence a single product decision.** The constraints are legal (§6), statistical (§13), cadence-related (§7.1) and distributional (§10) — never financial.

---

## 17. What Survived the Research

### 17.1 Revision intelligence — the only unambiguous survivor

Zero products. Unregistered domains. A demand shock that produced op-eds and no supply. The only consumer-facing artifact anywhere is a static Fed research chart at ~20% completeness. **And MacroChipz already has the hardest part built** — append-only versioning, deterministic replay, and an evidence model that can prove what it knew and when.

**Two independent research passes, testing two different business models (#28's paid tool and #35's free consumer media), converged on this same feature. That is the strongest signal either document produced.**

### 17.2 The measured misconception set — the demand side of the same coin

**66% of prospective homebuyers think the Fed sets mortgage rates. 61% think the government dictates lender rates. 63% think rates are at an all-time high.** Roughly half of under-45s believe a 20% down payment is required when the first-time median is 10%. 80% believe prices systematically rise faster than wages. The public supports rate *cuts* to fight inflation.

**These are not vague "people don't understand economics" claims. They are specific, measured, correctable beliefs, each attached to a decision worth real money** — and CFPB's own analysis puts the cost of the mortgage-shopping misconception at **over $1,000 a year** per borrower.

### 17.3 The deterministic engine, as credibility rather than as product surface

Everything #29–#34 built survives — but **as the spine, not the storefront.** Frozen versioned methodologies, evidence-validated Analyst output, point-in-time correctness, replay verification, an operator-guarded write path. **None of it is a feature a consumer will ever ask for. All of it is why a consumer could believe the answer.**

### 17.4 The honest answer to §4.3

> **Why would MacroChipz break a pattern that fifteen years of free financial content has not?**

The research supports exactly one answer, and it is not "better explanations."

**It is that the existing content fails on *trust*, not on *clarity*.** The evidence: people already consult 7.6 sources and still lose money more often; only 20% of finfluencer recommendations carry disclosure; 57% have regretted a decision made on online misinformation; the two fastest-growing information sources (social, generative AI) are the two *least* trusted to act on; and Gen Z's #1 and #2 trust criteria are **"explains things clearly"** and **"isn't trying to sell me something"** — the second ranked *higher* by non-investors.

**MacroChipz's differentiator is therefore not that it explains better. It is that every sentence can be traced to a specific number from a specific agency at a specific point in time, and that it has no position to sell.** That is a *provenance* product wearing an explainer's clothes — and provenance is precisely what this codebase spent thirty-four increments building.

### 17.5 Smaller survivors

- **The Economic Calendar** — free, machine-readable from BLS and BEA, and the honest answer to "when is there something new."
- **The Analyst (#33)** — the AI-explainer niche is genuinely unoccupied (§8.6) and MacroChipz's bounded, evidence-validated version is already ~80% of it.
- **Politano's link-the-claim pattern** (§10.5) — proven at 83K readers, trivially implementable, and nobody has built the tooling.
- **Email** — the only channel with real referral value and the only compounding asset.

---

## 18. What Did Not Survive

Stated plainly, as the brief requires.

### 18.1 🛑 The daily product

**Killed by two independent measurements.** 23.8% of business days have a release [MEASURED]; "inflation" shows a 1.11× lift against a 1.08× placebo [A]. **"Today in the Economy," a daily brief and a daily video cadence are all dead.** Release-driven plus weekly is the honest shape.

### 18.2 🛑 The Economic Pulse as a differentiator

**Killed by the competitor research.** CFNAI since 2001; St. Louis Fed's free plain-English version; recessiondashboard.com and RecessionPulse shipping the consumer version *today* with newsletters and alerts MacroChipz does not have; fredecondashboard.com already using MacroChipz's positioning sentence. **Build it. Never sell on it.**

### 18.3 🛑 Radar as a content engine

**Killed by arithmetic.** 0–3 honest findings per month, frequently zero. A scan tuned to fill a calendar produces 27 false findings a month at 600 tests. **And the specified flagship example is itself a false narrative** (§13.5) — the exact failure mode the brief asked us to guard against. **Radar survives only as a rare, high-bar, pre-registered, vintage-stamped feature, which by definition cannot carry a publishing schedule.**

### 18.4 🛑 "Social video and search feed users into the website"

**Killed by the referral data.** Every social platform <0.5%; search referrals −33% to −38% YoY; AI Overviews halve click-through; finance is the hardest YMYL category for an unknown domain. **Video and social build a *channel audience*, not website traffic. Email is the only compounding asset.** And Sherwood News is the fresh, specific, well-funded counterexample — where the newsletter survived and the destination site did not.

### 18.5 🛑 The backward-looking Time Machine, as currently imaginable

**Killed by our own data and by licensing.** 1,072/1,072 versions backfilled, 0 genuinely observed, 0 REVISED events ever captured [MEASURED]. ALFRED has exactly the right capability and **we cannot legally use it.** Backward vintages must come from archived agency releases or BEA's own archive, one story at a time. **The forward-only version is real and must be labelled as forward-only.**

### 18.6 🛑 Weekly mortgage rates as a data series

**Killed by Freddie Mac's terms** — three separate prohibitions. No verified free commercial alternative exists. **Use the Treasury 10-year as a labelled proxy, and make the limitation part of the lesson** (§6.8).

### 18.7 🛑 FRED as the spine

**Killed by four independent clauses**, and it is *already* the implementation — 16 files, all six canonical series [MEASURED]. **This is the largest single piece of technical debt the research uncovered**, and the Fed Board's DDP retirement (week of Nov 9) makes it time-sensitive rather than theoretical.

### 18.8 🛑 Students and finance professionals as Day-1 wedges

Students: real demand, wrong product, global audience (which also disqualifies premium display networks). Professionals: 18,600 economist jobs total, and it is #28's already-rejected thesis.

### 18.9 ⚠️ Deferred rather than killed

- **Small business owners** — real, measured pain, but **where they get economic information has no published figure and apparently no survey exists.** Cannot target an unmeasured channel.
- **Housing / Consumer / Growth domains** — zero data held today [MEASURED]; licensing is clean; straightforward but not free of effort.
- **Per-indicator notifications** — granularity implies a frequency the data does not have.

---

## 19. Biggest Unknowns

Ranked by how much each would change the decision.

1. **Does anyone actually want revision intelligence?** It is genuinely empty, and "rare ≠ wanted" is the most honest sentence in §8.4. The demand shock produced op-eds, not products — **which could mean the market is unserved, or that it does not exist.** This research cannot distinguish those two. **Experiment E4 is designed to.**
2. **Would the St. Louis Fed grant written permission for FRED/ALFRED?** A yes converts the largest blocker into the largest accelerator and makes the backward Time Machine immediately buildable. **Cost of asking: one email.**
3. **Does the FRED per-user-key clause bind a cached server-side architecture?** ⚖️ The single highest-value legal question.
4. **Would Freddie Mac license PMMS to an attributed public-education site?** Possibly free. **Cost of asking: one email.**
5. **Does evidence-linked content convert better than ordinary content?** Politano's link-the-claim pattern is proven at 83K readers *in text*, has **no video equivalent**, and **nobody has measured whether the evidence link changes behaviour at all.** This is MacroChipz's core bet and it is untested.
6. **Reddit — completely unmeasured.** The brief asked for it; it was hard-blocked. r/personalfinance, r/RealEstate and r/Economics are where the wedge audience's actual recurring questions live.
7. **Is "the economy feels bad" a durable premise or a partisanship artifact?** UMich's 9-point mode shift and the Conference Board's *rising* Present Situation Index (121.2) cut against it (§4.2).
8. **What content classification maximises YouTube RPM?** The only methodology-bearing dataset says **Education & Science $10.22 RPM vs Business & Finance $2.01** — the opposite of received wisdom, on <10 channels.
9. **Google Trends — zero series retrieved.** The event/evergreen split rests on a Wikipedia proxy with a placebo control plus published academic work. Directionally robust; not the same as Trends.
10. **Will inflation re-cross 4%?** The attention-threshold literature says attention *doubles* above it. At 3.4%, MacroChipz launches in the transition band.

---

## 20. Experiments Needed Before Building

Ordered by dependency. **E0 is a hard prerequisite: nothing measurable can run until it exists.**

### E0 — Build the distribution instrumentation *(prerequisite, ~1 week, $0)*

Open Graph + Twitter card tags with a real generated preview image, meta descriptions, canonical URLs, `sitemap.xml`, `robots.txt`, Cloudflare Web Analytics, an email capture form, and a share affordance. **Without this, MacroChipz cannot measure return rate, share rate or exploration depth — the three behaviours the entire thesis rests on** [MEASURED, §10.7].
**Kill signal:** none. This is unconditionally correct.

### E1 — Send the two licensing letters *(one day, $0)*

To the **St. Louis Fed** (FRED/ALFRED written permission for a free public educational site) and to **Freddie Mac** (PMMS licence for an attributed public-education site). Each is one email and each can unlock a blocked capability.
**Kill signal:** a clear "no" from St. Louis Fed makes the FRED migration (§21.1) unconditionally urgent rather than merely correct.

### E2 — The misconception test *(one week, ~$0)*

Publish **three** explainers — *"The Fed does not set your mortgage rate"*, *"Falling inflation does not mean falling prices"*, *"Why the jobs number you remember was wrong"* — each with every claim hyperlinked to a live MacroChipz evidence page (the Politano pattern). Measure: read-through, evidence-link click rate, share rate, email conversion.
**Why:** this simultaneously tests the wedge topic, the content format, and the core evidence-linking bet.
**Kill signal:** evidence-link click rate below ~2% means the provenance differentiator is invisible to users, and §17.4's entire argument fails.

### E3 — The A/B that tests the only real differentiator *(two weeks, ~$0)*

Same explainer, two versions: one with live evidence links and point-in-time stamps, one with static charts. Randomise. Measure time-on-page, scroll depth, share rate and return within 30 days.
**Why:** this is the single highest-value experiment in the list, because **nobody has ever measured whether the evidence link changes behaviour** (§19.5). MacroChipz's entire thesis is that it does.
**Kill signal:** no measurable difference means the deterministic engine has no *consumer* value and should be repositioned as infrastructure or a B2B asset rather than a consumer differentiator.

### E4 — The revision-demand probe *(one release cycle, ~$0)*

At the next Employment Situation release, publish the sign-test finding (§7.4) plus a prominent revision panel, and *separately* publish a conventional "here's the number" post. Compare reach, shares and email conversion.
**Why:** directly tests §19.1 — the biggest unknown in the document.
**Kill signal:** if the revision content underperforms the conventional post on every metric, the one genuinely empty slot is empty for the wrong reason, and §21's recommendation collapses.

### E5 — The newsletter-first test *(30 days, $0 on beehiiv Launch / Kit Free)*

Ship the Brief as the primary surface on a release-driven + weekly cadence. Measure subscriber growth per piece of content, click-through to evidence pages, and week-4 retention.
**Why:** §10 says email is the only compounding asset; this measures the rate at which it compounds for *this* topic.
**Benchmark for interpretation:** the Paved 50,000-subscriber sponsorship gate (§11.4) and Kyla Scanlon's ~197K-after-175-videos trajectory (§8.7) set the realistic order of magnitude — **not Morning Brew's 4.2M.**

### E6 — The keyword-ambiguity check *(two days, $0)*

Before producing any video, verify the §5.7 finding against the live platforms: confirm that "inflation" and "recession" are owned by unrelated genres, and that "mortgage rates," "interest rates" and "economics explained" are clean.
**Why:** it is cheap, it is checkable, and getting it wrong wastes every video produced.

### E7 — The YouTube classification test *(one month, $0)*

Publish matched content under Education & Science versus Business & Finance framing and compare RPM.
**Why:** the only methodology-bearing dataset says the received wisdom is backwards (§10.6), on fewer than 10 channels. Worth one month to find out.

### E8 — Deep re-ingestion, as a Radar precondition *(one week, $0)*

Re-ingest full history from BLS/BEA directly (CPI to 1913, CES to 1939) rather than the current 59–60 monthly observations [MEASURED, §7.6].
**Why:** no percentile, extreme or historical-position claim is honest on 60 points. **This also doubles as the first half of the FRED migration.**

### E9 — Radar dry-run, published to nobody *(three months, $0)*

Run the pre-registered scan of §13.4 monthly against the deep history, with BH-FDR at q=0.10 and vintage stamping, and record every finding privately.
**Why:** it measures the actual finding rate before anything is shown to a user, and it verifies the §13.6 determinism trap empirically — do last month's findings survive this month's recomputation?
**Kill signal:** if three months produce zero findings or produce findings that vanish on recomputation, Radar is not a product.

### E10 — Read Reddit *(a few hours, $0, needs a different tool)*

The brief asked for it and this session could not deliver it. r/personalfinance, r/RealEstate, r/Economics and r/FirstTimeHomeBuyer are where the wedge audience's actual recurring questions are written down in their own words.

---

## 21. Recommended MacroChipz 2.0 Day-1 Scope

> **MacroChipz is the place where you find out that the number you remember was wrong — and see exactly what it actually says now, with the receipts.**

That sentence covers both survivors: the revision story (what the data said then vs now) and the misconception story (what you believe vs what the data shows). It is honest, it is differentiated, and it is what the engine was already built to do.

### 21.1 Prerequisites — before any feature work

| # | Item | Why | Effort |
|---|---|---|---|
| **P1** | **E0 — distribution instrumentation** | Nothing is measurable without it [MEASURED, §10.7] | ~1 week |
| **P2** | **Migrate ingestion off FRED to BLS/BEA/Census/Fed/Treasury direct** | Four independent licence blockers (§6.7); the implementation currently contradicts #28's own conclusion; **Fed DDP retires the week of Nov 9** | ~1–2 weeks |
| **P3** | **Replace the FRED releases API with BLS iCal + BEA JSON** | The stickier FRED dependency (§7.7) | ~2 days |
| **P4** | **Deep re-ingestion (E8)** | 60 monthly points cannot support any historical claim | ~1 week |
| **P5** | **Send the two licensing letters (E1)** | Free; each can unlock a blocked capability | 1 day |
| **P6** | **Implement "re-pull, never append" for SA series** | CES recomputes SA monthly; CPI SA revises 5 years back. **A determinism-claiming product that silently drifts every January is worse than one that never claimed it** (§6.12) | ~2 days |

### 21.2 The Day-1 product

**Six surfaces. Nothing else.**

1. **The Brief (email) — the primary surface.** Release-driven plus a weekly wrap. Not daily. Every claim hyperlinked to a permanent evidence page. This is the compounding asset and the only channel with real referral value.

2. **Revision Intelligence — the wedge.** Prominent revision marking on every number; the revision-direction sign test (§7.4); BLS's own published thresholds shown alongside every payroll figure (*"BLS's own standard is that a change under 122,000 can't be told apart from zero — this month's was 85,000"*); benchmark-revision context. **This is the differentiator and it should be the first thing a visitor sees.**

3. **"Wait, Seriously?" explainers — the volume engine.** Starting with the three measured misconceptions: what actually moves your mortgage rate; why falling inflation doesn't mean falling prices; why the jobs number gets revised. Evergreen, decisional, clean keywords. **Carries the ~22 days a month that releases cannot.**

4. **Three economic worlds — Inflation, Jobs, Rates.** Already built. Pulse and "what changed at the last release" as furniture inside them, not as the pitch. **Housing added early, partial and honestly labelled** (Census starts/permits are clean; the 10-year Treasury stands in for mortgage rates with the limitation stated on the page).

5. **The Economic Calendar.** Free, machine-readable, and the honest answer to "when is there something new."

6. **Ask MacroChipz (the #33 Analyst).** Already shipped, already bounded, already evaluated at 13/15. The AI-explainer niche is genuinely unoccupied and this is ~80% of it.

**Plus one minimal retention mechanism:** email-only, release-driven follow. No push, no SMS, no per-indicator granularity.

### 21.3 Explicitly not in Day 1

Radar · the backward Time Machine · "Today in the Economy" · Consumer and Growth worlds · per-indicator alerts · any monetisation · any login.

### 21.4 The content operation, corrected

The brief's proposed engine — *event → intelligence → website story → video → social card → email → SEO page* — is **directionally right and inverted in one place.** The corrected version:

> **evergreen misconception + release event → deterministic intelligence → permanent evidence page → the Brief (primary) → video and social as top-of-funnel for the *channel*, citing back into the evidence page.**

Daily output is not the goal. **Release-driven output, plus one evergreen explainer a week, is what the data supports.** And journalists and creators are worth serving deliberately — not as a wedge audience, but because a permanent, citable, point-in-time-correct evidence page is precisely what Politano currently improvises with FRED permalinks, and MacroChipz could be the thing people link *to*.

---

## 22. Recommended Later Scope

**Tier 1 — after Day-1 metrics exist (3–6 months):**

- **Housing and Consumer worlds in full** — clean licensing (Census, BEA), directly serves the wedge.
- **The backward Time Machine, one story at a time** — from archived agency release PDFs and BEA's own vintage archive. **Never from ALFRED** absent written permission.
- **Radar, in the §13.4 restricted form only** — after E8 (deep history) and E9 (three-month dry run). Pre-registered, BH-FDR corrected, TOST-tested, vintage-stamped, architecturally capable of saying "nothing unusual this month."
- **Growth/GDP** — BEA's vintage archive makes GDP the most legally-clean revision story available.

**Tier 2 — after an audience exists (6–18 months):**

- Newsletter sponsorship, once the **50,000-subscriber** gate is in sight (§11.4).
- Video, if and only if E3 and E7 return positive signals.
- Podcast/audio — 167M monthly US listeners, excellent depth, zero web traffic.

**Tier 3 — speculative, do not design for it now:**

- API / data licensing, embeds, B2B intelligence, white-label. **The brief's own instruction stands: none of these should distort the Day-1 consumer product.** Note only that the *most* defensible asset MacroChipz could accumulate — a point-in-time-correct archive captured from day one — is also the one with the clearest later licensing value, which is a reason to start capturing it immediately rather than a reason to build for it.

---

## 23. Explicit Non-Goals

1. **Not a daily product.** 23.8% of business days have a release. Release-driven and weekly.
2. **Not a forecasting system.** Radar is descriptive. Revisions are described, never predicted (§7.4).
3. **Not a trading tool.** Every existing Radar-like product outputs a trade signal; that market is served and it is #28's rejected thesis.
4. **Not a general economics course.** Education connects to the live economy or it does not ship.
5. **Not built on FRED.** Four independent blockers. Migrate.
6. **Never republishing Freddie Mac PMMS**, scraped or otherwise.
7. **Never presenting backfilled versions as observed history.** Forward-only is forward-only.
8. **Never publishing a finding that fails its own published significance threshold** — no "payrolls weakened" on a sub-122k move; no "revised unusually" on a sub-118k revision; no "while X remains stable" without a TOST.
9. **No guaranteed content quota from Radar.** If the honest answer is zero findings, the honest output is zero findings.
10. **No login wall on the primary experience.**
11. **No monetisation before an audience**, and **sponsorship never influences methodology, states, Radar findings, evidence or conclusions** — this is the product's principal competitive asset (§11.6), not merely its ethics policy.
12. **Not "for everyone."** The wedge is people making a decision they are measurably getting wrong.
13. **Not chasing virality.** Social video's referral share is <0.5%; email is the compounding asset.

---

## 24. Sources

All retrieved **2026-09-20** unless otherwise stated. Primary/official sources listed first within each group.

### Data licensing and terms (all provider-owned domains)

- BLS: [linksite](https://www.bls.gov/bls/linksite.htm) · [API Terms of Service](https://www.bls.gov/developers/termsOfService.htm) · [release schedule + iCal](https://www.bls.gov/schedule/2026/home.htm)
- BEA: [API Terms of Service (PDF, extracted locally)](https://apps.bea.gov/api/_pdf/bea_api_tos.pdf) · [API User Guide (PDF, extracted locally)](https://apps.bea.gov/api/_pdf/bea_web_service_api_user_guide.pdf) · [signup](https://apps.bea.gov/API/signup/) · [release schedule](https://www.bea.gov/news/schedule) · [release dates JSON](https://apps.bea.gov/API/signup/release_dates.json)
- Census: [API Terms of Service](https://www.census.gov/data/developers/about/terms-of-service.html) · [economic indicators](https://www.census.gov/economic-indicators/) · [calendar](https://www.census.gov/economic-indicators/calendar-listview.html)
- Federal Reserve Board: [disclaimer / public domain](https://www.federalreserve.gov/disclaimer.htm) · [Data Download Program](https://www.federalreserve.gov/datadownload/) *(retirement notice)*
- U.S. Treasury: [fiscaldata API documentation](https://fiscaldata.treasury.gov/api-documentation/) · daily yield curve CSV/XML endpoints
- New York Fed: [Terms of Use](https://www.newyorkfed.org/privacy/termsofuse) · [Markets API](https://markets.newyorkfed.org/api/rates/all/latest.json) *(verified open, unauthenticated)*
- DOL: [copyright](https://www.dol.gov/general/aboutdol/copyright) · [weekly claims release PDF](https://www.dol.gov/ui/data.pdf)
- FRED/ALFRED: [API Terms of Use](https://fred.stlouisfed.org/docs/api/terms_of_use.html) · [legal](https://fred.stlouisfed.org/legal/) · [API key policy](https://fred.stlouisfed.org/docs/api/api_key.html) · [ALFRED](https://alfred.stlouisfed.org)
- Freddie Mac: [terms](https://www.freddiemac.com/terms) · [PMMS](https://www.freddiemac.com/pmms)
- FHFA: [data](https://www.fhfa.gov/data) *(no terms-of-use statement found)*

### Statistical methodology and uncertainty

- BLS: [Employment Situation Technical Note](https://www.bls.gov/news.release/empsit.tn.htm) · [CES confidence intervals (XLSX)](https://www.bls.gov/web/empsit/cesconfidenceintervals.xlsx) · [CPS monthly significance table](https://www.bls.gov/web/empsit/cpssigsuma.htm) · [CPI technical notes](https://www.bls.gov/cpi/technical-notes/home.htm) · [CPI variance (XLSX)](https://www.bls.gov/web/cpi/cpi-variance.xlsx) · [CES revision tables](https://www.bls.gov/web/empsit/cesnaicsrev.htm) · [benchmark article](https://www.bls.gov/web/empsit/cesbmart.htm) · [birth-death model](https://www.bls.gov/web/empsit/cesbd.htm) · [CES/CPS comparison](https://www.bls.gov/web/empsit/ces_cps_trends.htm) · [HOM diffusion formula](https://www.bls.gov/opub/hom/ces/calculation.htm)
- BLS preliminary benchmarks: [March 2024 (−818,000)](https://www.bls.gov/ces/notices/2024/2024-preliminary-benchmark-revision.htm) · [March 2025 (−911,000)](https://www.bls.gov/news.release/archives/prebmk_09092025.htm) · [March 2026 (−79,000)](https://www.bls.gov/news.release/prebmk.nr0.htm)
- BEA: ["Comparisons of Revisions to Real GDP," Nov 2025 (PDF)](https://www.bea.gov/sites/default/files/2025-11/relia.pdf) · [Fixler, de Francisco & Schaaf, SCB Aug 2024](https://apps.bea.gov/scb/issues/2024/08-august/0824-revisions-to-gdp-gdi.htm)
- Census: [MARTS Table 3 (XLSX)](https://www.census.gov/retail/marts/www/marts_current.xlsx)
- Federal Reserve: [Murray & Vidangos, "Labor Force Growth, Breakeven Employment, and Potential GDP Growth," FEDS Notes, 2026-04-02](https://www.federalreserve.gov/econres/notes/feds-notes/labor-force-growth-breakeven-employment-and-potential-gdp-growth-20260402.html)
- Philadelphia Fed: [Real-Time Data Set for Macroeconomists](https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/real-time-data-set-for-macroeconomists) · [early benchmark revisions](https://www.philadelphiafed.org/surveys-and-data/regional-economic-analysis/early-benchmark-revisions)
- San Francisco Fed: [Revisions to Payroll Employment Gains in Historical Context](https://www.frbsf.org/research-and-insights/data-and-indicators/revisions-to-payroll-employment-gains/)
- [Faust, Rogers & Wright, IFDP 690 / JMCB 2005](https://ideas.repec.org/p/fip/fedgif/690.html) · [Aruoba, "Data Revisions Are Not Well Behaved," JMCB 2008](https://ideas.repec.org/a/mcb/jmoncb/v40y2008i2-3p319-340.html)

### Audience, literacy and perception

- Federal Reserve: [SHED 2025 executive summary](https://www.federalreserve.gov/publications/2026-economic-well-being-of-us-households-in-2025-executive-summary.htm) · [Small Business Credit Survey 2026](https://www.fedsmallbusiness.org/reports/survey/2026/2026-report-on-employer-firms)
- FINRA Foundation: [NFCS 6th edition (PDF)](https://finrafoundation.org/sites/finrafoundation/files/2025-07/NFCS-Report-Sixth-Edition-July-2025.pdf) · [Gen Z and Investing (PDF)](https://finrafoundation.org/sites/finrafoundation/files/2024-10/Gen-Z-and-Investing.pdf) · [Social Media and Finfluencers brief (PDF)](https://finrafoundation.org/sites/finrafoundation/files/2026-03/FINRA_Foundation_Research_Brief_Social_Media_Finfluencers.pdf) · Investors in the United States, 4th ed. (Dec 2025)
- [TIAA Institute-GFLEC P-Fin Index 2026 (PDF)](https://gflec.org/wp-content/uploads/2026/06/TIAA_GFLEC_Report_AnnualPFin_June2026_fin2.pdf)
- [Council for Economic Education, Survey of the States 2026](https://www.councilforeconed.org/survey-of-the-states/) · [NCES NAEP Economics](https://nces.ed.gov/nationsreportcard/economics/)
- Pew Research: [Americans' Evaluations of the Economy (Jul 2026)](https://www.pewresearch.org/politics/2026/07/23/americans-evaluations-of-the-economy-remain-negative/) · [Americans' Complicated Relationship With News (Feb 2026)](https://www.pewresearch.org/journalism/2026/02/11/americans-complicated-relationship-with-news/) · [AI summaries and click behaviour (Jul 2025)](https://www.pewresearch.org/short-reads/2025/07/22/google-users-are-less-likely-to-click-on-links-when-an-ai-summary-appears-in-the-results/)
- CFPB: [Consumers' Mortgage Shopping Experience](https://www.consumerfinance.gov/data-research/research-reports/consumers-mortgage-shopping-experience/) · [HMDA rate dispersion analysis](https://www.consumerfinance.gov/archive/blog/mortgage-data-shows-borrowers-could-save-100-month-choosing-cheaper-lenders/)
- [NAR 2025 Profile of Home Buyers and Sellers](https://www.nar.realtor/research-and-statistics/research-reports/highlights-from-the-profile-of-home-buyers-and-sellers) · [US Chamber Small Business Index Q2 2026](https://www.uschamber.com/small-business/small-business-index-q2-2026)
- [Korenok, Munro & Chen, "Inflation and Attention Thresholds," REStat May 2026](https://doi.org/10.1162/rest_a_01402) · [Pfäuti, arXiv:2308.09480](https://arxiv.org/abs/2308.09480) · [Binetti, Nuzzi & Stantcheva, NBER w32497](https://www.nber.org/papers/w32497)
- [UMich Surveys of Consumers](http://www.sca.isr.umich.edu/) · [Conference Board Consumer Confidence](https://www.conference-board.org/topics/consumer-confidence) · [Nate Silver / Wertheimer, "Is the vibecession real?"](https://www.natesilver.net/p/is-the-vibecession-real-or-is-the) *(independent analyst blog, not peer-reviewed)*
- Veterans United / Sparketing (Mar 2026, n=400) and FirstHome IQ / National MI, both **via HousingWire reporting only** — [HousingWire](https://www.housingwire.com/articles/veterans-united-survey-homebuyers-credit-score-down-payment/) · [Fannie/Freddie data discontinuation](https://www.housingwire.com/articles/fannie-mae-freddie-mac-housing-market-data/)

### Distribution, publishing and sponsorship

- [Digiday — referral traffic mix (Chartbeat, ~3,750 sites)](https://digiday.com/media/referral-traffic-from-google-discover-increases-in-2024-amid-the-steady-decline-of-referrals-from-social/) · [Digiday — 1440 CPM model](https://digiday.com/media/why-1440-prefers-cpms-for-its-newsletter-business-over-other-pricing-models/)
- Reuters Institute Digital News Report 2026; Reuters Institute / Chartbeat referral study (2,576 sites, to Nov 2025); Press Gazette (Aug 2026)
- [Nieman Lab — Robinhood shuts down Sherwood News](https://www.niemanlab.org/reading/stock-trading-app-robinhood-shuts-down-sherwood-news/) *(corroborated independently from sherwoodnews.com sitemap, this session)*
- [Google Search Central — creating helpful content / YMYL](https://developers.google.com/search/docs/fundamentals/creating-helpful-content)
- [Paved newsletter sponsorship guide](https://www.paved.com/blog/the-ultimate-newsletter-sponsorship-guide/) *(vendor; owned by Redbrick, which also owns Quartz)* · [beehiiv Ad Network](https://www.beehiiv.com/ad-network) *(vendor)* · [Litmus email client market share](https://www.litmus.com/email-client-market-share) · [AIR Media-Tech RPM study](https://air.io/en/air-data-findings/which-youtube-niche-makes-the-most-money-in-2026-ranked-by-real-rpm-and-cpm) *(commercial network; Business & Finance <10 channels, "directional")*
- Edison Research Infinite Dial 2026; eMarketer 2025 programmatic spend; Ozone Q2 2026 publisher report

### Competitor and substitute products

[Chicago Fed CFNAI](https://www.chicagofed.org/research/data/cfnai/current-data) · [St. Louis Fed Economy at a Glance](https://www.stlouisfed.org/on-the-economy/data/economy-at-a-glance) · [BLS Economy at a Glance](https://www.bls.gov/eag/eag.us.htm) · [Trading Economics US indicators](https://tradingeconomics.com/united-states/indicators) · [TipRanks economic indicators](https://www.tipranks.com/economic-indicators) · [Koyfin pricing](https://www.koyfin.com/pricing/) · [recessiondashboard.com](https://recessiondashboard.com/) · [recessionpulse.com](https://recessionpulse.com/) · [MacroMicro](https://next.macromicro.me/en) · [tsvetoslavtsachev/us-macro-dashboard](https://github.com/tsvetoslavtsachev/us-macro-dashboard) · [OpenEcon Data](https://openecon.ai) · [Employ America MacroSuite](https://www.employamerica.org/macrosuite/) · [Apricitas](https://www.apricitas.io/) · Bloomberg point-in-time dataset launch (2026-05-08), [via LeapRate](https://www.leaprate.com/forex/institutional/bloomberg-launches-point-in-time-economic-dataset-for-quant-strategy-development/)

### Operating cost

[Render pricing](https://render.com/pricing) · [Render free tier](https://render.com/docs/free) · [Render Postgres backups](https://render.com/docs/postgresql-backups) · [Render cron jobs](https://render.com/docs/cronjobs) · [OpenAI API pricing](https://developers.openai.com/api/docs/pricing) · [Neon](https://neon.com/pricing) · [Supabase](https://supabase.com/pricing) · [Fly.io](https://fly.io/docs/about/pricing/) · [Railway](https://railway.com/pricing) · [Vercel](https://vercel.com/pricing) · [Netlify](https://www.netlify.com/pricing/) · [Resend](https://resend.com/pricing) · [beehiiv](https://www.beehiiv.com/pricing) · [Kit](https://kit.com/pricing) · [Amazon SES](https://aws.amazon.com/ses/pricing/) · [Cloudflare plans](https://www.cloudflare.com/plans/) · [Cloudflare Web Analytics](https://www.cloudflare.com/web-analytics/) · [Cloudflare Pages limits](https://developers.cloudflare.com/pages/platform/limits/) · [Porkbun domains](https://porkbun.com/products/domains) · [Plausible](https://plausible.io/#pricing) · [Fathom](https://usefathom.com/pricing) · [Descript](https://www.descript.com/pricing)

### Internal (measured this session)

MacroChipz repository and PostgreSQL database, 2026-09-20 — `release_occurrences`, `observation_versions`, `release_observation_updates`, `economic_observations`, `frontend/index.html`, and a source-tree audit of FRED references. Findings F1–F10, cited inline as [MEASURED]. Prior increment: `docs/product/macrochipz-product-discovery-data-feasibility-v1.md` (#28).

---

**FINAL POSITION**

**CONDITIONAL GO — on a substantially narrower product than the one proposed.**

The daily product, the Pulse-as-differentiator, Radar-as-content-engine, the social-and-search acquisition model, and the backward-looking Time Machine do not survive the evidence. What survives is narrow, unoccupied, and precisely aligned with what this codebase already does better than anything else on the internet: **prove what the data said, when it said it, and what it says now.**

The prerequisites (§21.1) are real work and must come first — instrumentation, the FRED migration, deep re-ingestion. **None of them is expensive; all of them are overdue.**

And §19.1 remains genuinely open: **revision intelligence is empty, and this research cannot tell whether that is because the market is unserved or because it does not exist.** E2, E3 and E4 are designed to answer that for roughly the cost of three blog posts. **Run them before building anything else.**
