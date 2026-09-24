# MacroChipz Rates World — #52A experience specification

**Status:** proposed. Prototype built and measured; **no production code
written**.
**Prototype:** `docs/product/mockups/v52a/index.html` (+ `data.js`,
`rates-snapshot-2026-09-24.json`)
**Audit:** `macrochipz-rates-world-v52a-audit.md`

---

## 1. The idea in one line

**Two curves on one chart: today, and a day the reader chooses — so the page can
show that the level moved and the shape moved, which are different things.**

## 2. Why this and not something else

| World | Central visual | What it asks |
|---|---|---|
| Inflation (#50B) | Price climb | How one series accumulated over time |
| Jobs (#51B) | Survey threshold | Where one point sits against a band |
| **Rates (#52A)** | **Two curves, then and now** | **How a cross-section changed shape** |

Rates is the only world whose headline data is a *cross-section* — four prices of
the same thing at four horizons on one day. Comparing two cross-sections is a
question the other two worlds cannot ask, and a single-date curve cannot answer.

## 3. Every number is published. Nothing is calculated.

This is the constraint that shaped the design, not a compliance note bolted on.

| On screen | Source field |
|---|---|
| "Now" curve, 4 points | `nominal_curve[].latest_value` @ `latest_date` |
| "Then" curve, 4 points | `nominal_curve[].changes[w].from_value` @ `from_date` |
| "2Y moved +57 bp" | `nominal_curve[].changes[w].change_basis_points` |
| "gap was 1.00, now 0.58" | `curve_spreads[2s30s].changes[w].from_value` / `to_value` |
| "published as −42 bp" | `curve_spreads[2s30s].changes[w].change_basis_points` |
| Selected maturity reading | `latest_value`, `changes[]`, `historical_context`, `provenance` |
| Derived strip | `curve_spreads[]`, `inflation_compensation[]` |
| Movements | `/api/v1/intelligence?world=rates` `items[].evidence[]` |

The four `from_date` values are **aligned across all four maturities** (audit
§2), which is the fact that makes the second curve drawable at all.

**The wider/narrower sentence reads the spread's own `from_value` and
`to_value`.** It never subtracts one yield from another. This keeps the design
clear of `src/test/no-rates-calculation.test.ts` by construction rather than by
routing around it — and the existing `lib/cssUnits.ts` (added in #49B for exactly
this reason) stays the only place a percentage is formed.

The only arithmetic in the prototype turns a value into a pixel.

## 4. Page structure

1. **Hero** — "The whole curve moved. Its shape moved too." Existing reviewed
   yield definition, the published-date pill, the Treasury attribution.
2. **The curve, then and now** — the central visual. Four window buttons
   labelled by their *actual dates*; two curves; four 44px maturity targets; a
   two-clause reading (Level, Shape).
3. **The maturity you picked** — the #49B `SelectedMaturityPanel`'s content:
   value, four session changes each with its `from_value` and `from_date`, the
   historical-context sentence, provenance disclosure.
4. **What the shape does and does not mean** — the editorial guard (§6).
5. **What MacroChipz calculated** — the four derived numbers, condensed.
6. **Movements MacroChipz recorded** — the six intelligence records, with their
   own "carries no significance claim" framing.
7. **What this page does not have** — the audit's §1.3 gaps, on the page.
8. **Evidence & methodology** — the existing disclosure, plus "How the past
   curve is drawn".

Production sections the prototype does not restate but which **must be retained**:
`StoryTeaser`, "Where these numbers come up", `AskMacroChipz`, `RevisionsLink`,
`UnderstandWorld`. Their absence from the prototype is scope, not a proposal to
remove them — and it means the prototype's document heights below are **not**
directly comparable to the current page's.

## 5. Interaction

- **Window switch** — four buttons, 2×2 at mobile, 4-up at ≥720px. Each shows
  "21 sessions ago / Aug 19, 2026": the window in the backend's own unit
  (sessions, never months) *and* the date it resolves to, because a reader thinks
  in dates.
- **Maturity selection** — four transparent HTML buttons over the plot, 58px wide
  and the full plot height. Selection rings the "now" point and drives §3.
- **No animation.** The redraw is an instantaneous DOM replacement. Measured: the
  page has zero CSS animations and exactly two transitions (button colour, the
  disclosure chevron), both suppressed by
  `@media (prefers-reduced-motion: reduce)`. There is nothing to suppress in the
  central visual because nothing there moves.

## 6. The editorial guard — non-negotiable

Drawing a flattening curve invites two claims the product cannot support. Both
are denied **on the page**, not in a disclosure:

> MacroChipz reports the shape and the dates it changed between. It does not tell
> you what the shape predicts. `rates_v1.0` defines no state label, no forecast
> and no cross-domain conclusion — so this page does not say a flatter curve
> signals a recession, and does not say the 10-year yield sets the rate on your
> mortgage.

And the reading sentence ends: "MacroChipz publishes that as −42 bp and **draws
no conclusion from it**."

## 7. Rendering rules

**Visuals are SVG. Interaction and type are HTML.**

- Two polylines and three gridlines in a `0 0 100 100` viewBox with
  `preserveAspectRatio="none"` **plus `vector-effect="non-scaling-stroke"`**, so
  stretching cannot thicken a stroke.
- **Every dot is an HTML element.** #48B and #51B each shipped an SVG circle that
  the same stretch turned into an ellipse. A round HTML dot positioned at a
  percentage cannot be distorted by a viewBox at all. This is the catalogued trap
  avoided by construction rather than by remembering.
- Value labels, maturity labels and the 44px targets are HTML, so 11px stays 11px
  and a target stays a target.
- **No y-axis.** Eight points, eight printed values — an axis label repeats a
  number already on screen. The first draft proved worse than redundant: the
  `4.19%` axis label landed exactly on the 2Y "then" dot at 390px.
- **Padding is sized for label half-width, not for an axis.** 8% each side; at
  390px that is ~26px against a ~15px half-label.

## 8. Failure isolation

One `useApiResource` per resource, as the product already does. Verified in the
prototype, each in isolation:

| Failure | Result |
|---|---|
| Rates monitor fails | Curve, selected maturity and derived strip each show their own message. **Movements still render all six records.** Limitations and evidence intact. |
| Movements feed fails | Curve renders complete with both readings; a message replaces the list only. |
| A past value is missing | The dashed line **breaks**; the isolated point keeps its published dot and value; a named "Incomplete comparison" note says which maturity and which date. Nothing falls to zero. |
| Everything loading | Skeletons per section; static editorial unaffected. |

The missing-value case is deliberate: #51B shipped a null coerced to `0` by
`Math.min` that both dropped the axis floor and drew a line to the bottom of the
chart, fabricating a value. The path builder here filters nulls out of the
domain and starts a new run at every gap.

## 9. Measurements

### Prototype, five widths

| | 390 | 440 | 768 | 1024 | 1440 |
|---|---|---|---|---|---|
| Document height | 5,057 | 4,813 | 3,863 | 3,649 | 3,629 |
| — of which the demo panel | 304 | 252 | 182 | 130 | 130 |
| Horizontal overflow | 0 | 0 | 0 | 0 | 0 |
| Elements escaping their card | 0 | 0 | 0 | 0 | 0 |
| Interactive targets under 44px | 0 | 0 | 0 | 0 | 0 |
| Plot board | 313×240 | 363×240 | 663×300 | 538×330 | 666×330 |
| Board aspect ratio | 1.30 | 1.51 | 2.21 | 1.63 | **2.02** |

The 1440 board ratio is the one that changed during review. The first draft was a
single column and measured **3.26:1** — the same shape as the current production
chart, and wide enough that any curve reads as flat. At ≥1024 the card now splits:
plot left, Level/Shape reading right. That both fixes the ratio and puts the
desktop dead space the audit measured to work.

### Contrast, measured on rendered composites (WCAG 2.1)

Lowest text ratio on the page: **5.45:1** (11px window label). Everything else
6.08–15.55:1. Graphical objects: "now" line **8.18:1**, dashed "then" line
**4.57:1** — both above the 3:1 threshold for non-text.

One change came out of this: the "then" value labels first used the same
`#7c8697` as the dashed line and measured **4.57:1** — a pass for text with
nothing to spare. The line is a graphical object at 3:1 and the number beside it
is 12.5px text at 4.5:1; they are not the same requirement. The text now has its
own lighter step and measures **6.67:1**.

### Reduced motion

Zero CSS animations. Two transitions (button colour 0.15s, chevron 0.15s), both
covered by `* { transition: none !important }` under
`@media (prefers-reduced-motion: reduce)`.

## 10. Unresolved questions — for the review, not for me to decide

1. **The derived cards lose their per-metric change grids.** Current:
   1,902px at 390. Prototype: 874px. But the prototype's condensed strip drops
   each derived metric's four session changes, its historical-context percentile
   and its "how this is calculated" disclosure, keeping only the value, the two
   inputs and the date. **That is a content reduction, not a free win.** Options:
   (a) accept it — the four windows are already shown for the selected maturity;
   (b) keep one disclosure per derived metric holding the dropped detail;
   (c) keep the current cards and accept the height. *Recommendation: (b).*

2. **Should the window switch offer the 119 daily observations instead of four
   windows?** `/api/v1/series/{id}/observations` would allow any of 119 dates,
   and all six series share an identical date set. Four published windows need no
   extra request and carry their own `change_basis_points`; a free date picker
   would need four more requests and would produce a "then" curve whose
   comparison figures are **not** published — reintroducing subtraction. *Strong
   recommendation: keep the four windows.* Recorded here because the data exists
   and someone will ask.

3. **Spread history is a backend dependency.** The narrowing can be shown between
   two dates but not plotted over time without a stored spread series. Should
   that be raised as a backend increment, or is the two-date comparison enough?

4. **Rates has no recorded-result history.** `/monitors/rates/history` → 422.
   Inflation and Jobs can replay a past conclusion; Rates cannot.
   `IntelligenceHistorySection` takes `MonitorHistoryResponse` and is **not**
   reusable for the `/api/v1/intelligence` contract. Is the lightweight movements
   list proposed here the right answer, or should the backend gain a rates
   history first?

5. **The "cost to borrow" copy inconsistency is still open.** The explainer
   registry's own `answer` and the homepage world line both say a yield is "what
   it costs the government to borrow"; the Rates hero deliberately does not.
   Flagged in #49B, unchanged. It belongs to the registry and the homepage, and
   should be a copy-review increment rather than a patch from this page.

6. **"Every maturity pays more."** A Treasury pays a yield to its holder, so this
   is accurate consumer phrasing consistent with the hero's "what investors
   earn". Confirm the register is right before it ships.

## 11. Explicitly out of scope

No new economic metric. No spread computed in the client. No forecast, state
label or cross-domain claim. No backend change. No new dependency.
