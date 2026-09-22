# Explainability & Rabbit Holes

**Status:** implemented (Increment #44)
**Registry:** `frontend/src/explainers/registry.ts`
**Routes:** `/explain/:slug` — all prerendered

---

## 1. Pre-implementation inventory

Earlier notes said "approximately 34 curated explanations". **The real count is 71.**

| File | Unique ids | Nature |
| --- | --- | --- |
| `inflation.ts` | 19 | concepts + per-state + disclosures |
| `labor.ts` | 19 | mostly per-state, plus employment/unemployment concepts |
| `rates.ts` | 13 | yields, spreads, compensation, windows, per-concept "why" |
| `processingStatus.ts` | 9 | operational |
| `releases.ts` | 10 | release types and statuses |
| `state-duration` | 1 | disclosure |

**Assessment: reusable as-is, and not replaced.** They are *field-level annotations* bound to specific UI — "what does this number on this card mean". What they cannot do is stand alone. Someone arriving from a 30-second video has no surrounding page for a tooltip to annotate.

> **An `Explanation` is an annotation. An `Explainer` is a destination.**

So #44 added a second, complementary model rather than rewriting good content.

---

## 2. Three kinds of content, kept apart

| | Source | Authority |
| --- | --- | --- |
| **A. Canonical intelligence** | #39, frozen methodologies | Authoritative |
| **B. Curated explanation** | this registry, written and committed | General, durable, never about a specific month |
| **C. Generative interpretation** | Ask MacroChipz | Bounded, optional, never authoritative |

**No explainer prose is generated at runtime.** A guard test fails on a model SDK, a `fetch`, or a `${}` interpolation appearing in the registry's content.

---

## 3. The launch set — 10 explainers

Chosen against what MacroChipz can show *and* explain accurately today.

**Rates (5):** the Fed and mortgage rates · Treasury yields · why the 10-year matters · the yield curve · real yields
**Inflation (3):** inflation vs prices · CPI vs PCE · headline vs core
**Jobs (2):** the two jobs surveys · unemployment without layoffs

Selection rationale: each either corrects something people measurably get wrong (#35), or answers a question a product surface already raises. **Housing explainers are deliberately absent** — #45 owns Housing and MacroChipz tracks no housing series.

---

## 4. Flagship: "Wait, the Fed doesn't set mortgage rates?"

#35 identified this as the best-evidenced consumer misconception in the research set.

### The correctness boundary, enforced by test

It never asserts that the Fed sets mortgage rates, that the 10-year sets mortgage rates, that there is a fixed spread, or that the Fed is unrelated. It describes an **indirect** relationship with **multiple converging influences**.

One subtlety the tests encode: the explainer *must* be able to state the false belief in order to correct it. So the claim-checks run against `answer`/`whatItIs`/`howItWorks`/`whatThisMeansForYou`, and the `misconception` field is tested separately for being framed as a belief.

### The statistic was omitted

#35 documents "66% of prospective homebuyers think the Federal Reserve sets mortgage rates" — but as **grade B, n=400, a lender-marketing survey via a trade publication**. Documented in the repo, yes; strong enough to state publicly as fact, no. Per §8 the explainer does not need it, so it says the belief is common without quantifying it. A test asserts no `NN%` appears.

### ⚠ Claims that would need external verification before public launch

These came from the increment's own §9 framing and are **not independently sourced in this repository**:

1. Mortgage pricing reflects the market for bundled mortgage loans (MBS).
2. Prepayment risk is a component of mortgage pricing.
3. Credit and liquidity conditions, and lender economics, affect quoted rates.

They are uncontroversial in fixed-income practice and are stated generically and cautiously. **They are flagged rather than silently shipped**, per §16.

*Verified in-repo:* the Fed's 2% objective is defined on PCE (`inflation.ts`); the 10-year is a reference point that "does not set any of those rates" (`rates.ts`, #40B); CES/CPS universes (`app/concepts/registry.py`).

---

## 5. The visual

A hand-authored HTML/CSS diagram. **No diagramming or chart library.**

Its *shape* is the argument: a single top-to-bottom arrow would say "the Fed decides and it flows down to you" — the exact belief being corrected. Instead four influences **converge**, with the Fed as one of them. Every influence carries its own sentence, so the diagram works without colour, without hover, and as text.

---

## 6. Live data — a deliberate omission

Explainers **do not fetch live data**. "What MacroChipz is watching" links into the live world instead of embedding a current number.

The trade, made explicitly: embedding live data would require a fetch, which would make the prerendered HTML an empty shell — destroying the one property that makes these pages findable. Explainers are the **only** MacroChipz surface whose substance a non-JavaScript crawler can read. That was worth more than a number the reader is one click from.

It also means the page cannot fail: there is nothing to degrade.

---

## 7. Rabbit holes

`related` is a hand-written list of explainer ids, 2–4 per page. **No recommender, no ranking, no popularity, no personalisation** — tests fail on `score`, `rank`, `trending`, `recommend`, `similar`, `personal`, `Math.random`. Every id must resolve, and no explainer may link to itself.

---

## 8. Integration

- **Worlds** — "Understand this" appears beneath the intelligence on Inflation, Jobs and Rates. On Jobs this is a page-level footer *outside* the seven-section hierarchy frozen by `labor-ui-v1.md` §7; recorded in that document's addendum rather than silently changing the frozen list.
- **Permanent objects** — "Understand this" matched by **concept id** (#38), placed *after* the fact and before VERIFY. #40B's hierarchy is unchanged: education does not jump the queue.
- **Homepage** — untouched. THE LEDE was not redesigned and no new homepage request was added.
- **Ask MacroChipz** — not integrated. The current Analyst context contract is bounded to canonical monitor context; widening it for explainers was out of scope.

---

## 9. Rendering

**All 10 explainer routes are prerendered**, with their actual content. Verified with `<script>` stripped: the flagship carries **3,235 characters** of real text, its `<h1>`, the diagram, "Explore next" and "How we know".

`scripts/verify-build-output.mjs` now fails the build if any explainer prerenders under 1,200 characters of scriptless text or loses its body, rabbit hole or basis section. Sitemap grew from 11 to **21 URLs**. No SSR, no Node runtime.

`og:image` reuses #40's existing `default.png` — no graphics system was added.

---

## 10. Limitations

1. The three mortgage-pricing mechanism claims above need external verification before public launch.
2. No live data on explainer pages, by choice (§6).
3. Ask MacroChipz is not connected.
4. The 71 existing `Explanation` tooltips and the 10 explainers are two models; concepts appearing in both are written twice.
5. No search, no index page listing all explainers — they are reached from worlds, objects and each other.
