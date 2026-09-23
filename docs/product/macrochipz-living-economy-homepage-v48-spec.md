# The Living Economy v2 — revised homepage specification

**Increment #48, phase 1.** Prototype and specification only. No production route touched.
**Prototype:** `docs/product/mockups/v48/index.html`
**Supersedes:** the v47 spec's §3 hero and §5 world presentation. Everything else in v47 stands.

---

## 1. What changed from v47, and why

v47 was four purple cards and a description panel that repeated what the cards
already said. Measured, the hero ran to 843px at 390px — the whole first screen —
so THE LEDE, the one section carrying actual news, was never seen without
scrolling.

| | v47 | v2 |
|---|---|---|
| Ground | violet everywhere | **charcoal / midnight**, violet as *light on* it |
| Worlds | text cards | **photographic frames** (placeholders, §4) |
| Selection reveals | a panel repeating the card | **one discovery line + a link** |
| Hero height at 390px | 843px | **679px** |
| Lede heading at 390px | below the fold | **709px — on the first screen** |
| Data | none | **one real measure**, snapshotted and labelled |
| Featured story | a link in a list | **its own band, with an accurate network preview** |

The colour decision is the one worth stating plainly: violet stops being the
colour of everything and becomes the colour of light falling on something. That
is the whole difference between "purple SaaS page" and "documentary".

---

## 2. Section hierarchy

1. **Compact cinematic hero** — headline, one supporting line, four photographic
   world selectors, one discovery line.
2. **The latest from the economy** — THE LEDE, near the top.
3. **Featured discovery** — the mortgage-rate story, with a preview of its
   actual network.
4. **Explore further** — three curated explainers, plus one real measure.
5. **Sources and limits** — three links, then the footer.

**No repeated four-world grid.** v47 listed the worlds three times (hero, quiet
lede, "start exploring"). They appear once, in the hero. The quiet lede links to
`/rates` and `/calendar` instead of re-listing.

---

## 3. Rules the design may not trade away

1. **No causal lines between the four worlds.** They are navigation categories.
   The only edges on the page are inside the story preview, and they carry the
   story's reviewed semantics: solid = *sets*, dashed = *influences*.
2. **The story preview must be accurate.** Same six actors, same two `sets`
   edges, same four `influences` edges as the shipped story. A decorative
   diagram that got the semantics wrong would be worse than no diagram.
3. **No invented figure, ever.** The one chart reads a snapshot captured from
   the running API and says so on its face. If the snapshot fails to load the
   panel says that, rather than drawing a plausible curve from nothing.
4. **Quiet is not "nothing is happening".** The copy says so explicitly: the
   economy is always operating; MacroChipz has not recorded a new tracked
   change.
5. **The warm accent never touches data.** `--ed-amber` is editorial only —
   section rules, the featured marker, placeholder chips. `--mc-state-warm` and
   `--mc-state-caution` carry economic classification under the #27B rule, so a
   warm colour on a number would read as a verdict.

---

## 4. Imagery

Four slots, all currently **marked placeholders**. Shot briefs, acceptance
rules, candidate licensing routes and the unresolved decision are in
`docs/product/mockups/v48/ASSETS.md`.

Summary: nothing ships until each slot has a documented commercial licence, no
identifiable person without a release, no third-party trademarks, and a credit
line stored with the file. US federal public-domain sources are worth checking
before paying for stock — free, provenance-clean, and consistent with how the
rest of the product sources its material.

---

## 5. The one data visual

Treasury par yields, four maturities, from `/api/v1/monitors/rates`.

- Rendered from a **snapshot**, captured from the local API, labelled
  `SNAPSHOT, NOT LIVE` with its capture date, the published as-of date, the
  Treasury attribution string and the methodology id.
- Genuinely interactive: four maturity controls and four focusable points, each
  with an accessible name carrying its value and units.
- Chosen because Rates is the only world whose shape reads at a glance in a
  100-pixel-tall panel. Inflation and Jobs need state and methodology to mean
  anything, and a sparkline of either would flatter the data.

**Production note:** this must become a fetch, not a file. A snapshot shipped as
live data would be exactly the dishonesty the label currently prevents.

---

## 6. Responsive and accessibility

Measured at genuine CSS viewport widths, all four world selections at each:

| | 390px | 440px | 768px | 1440px |
|---|---|---|---|---|
| Hero bottom | **679** | 692 | 529 | 639 |
| Lede heading top | **709** | 722 | 559 | 683 |
| Lede on first screen | yes | yes | yes | yes |
| Horizontal overflow | 0 | 0 | 0 | 0 |
| Text clipping | none | none | none | none |
| Targets < 44px | none | none | none | none |
| Page height | 3403 | 3307 | 2998 | 2358 |

Native `<button>`/`<a>`; `aria-pressed` on selectors; `aria-live="polite"` on the
discovery line and the lede; visible `:focus-visible`; every transition disabled
under `prefers-reduced-motion`; no meaning carried by motion.

---

## 7. Retained, removed, changed

| | Verdict |
|---|---|
| THE LEDE eligibility model (`homepage_presentation_v1.0`) | **Retained unchanged**, moved up |
| Four-world navigation | **Changed** — photographic, selected once, not repeated |
| v47's world description panel | **Removed** — replaced by one discovery line |
| v47's "Start exploring" four-card grid | **Removed** — it was the third copy of the same four links |
| Featured story | **Changed** — promoted from a list item to its own band with an accurate preview |
| Explainers | **Retained**, trimmed to three |
| Trust row | **Retained**, unchanged |
| Census attribution | **Retained verbatim** |

---

## 8. Unresolved

1. **Which imagery route** (commission / paid stock / federal public domain).
   The page's look depends on it and nobody has decided.
2. **Whether Rates is the right default selection** — it is the acquisition
   wedge, but a cold visitor may be better served by Inflation.
3. **Whether one real measure on the homepage sets a precedent** the other three
   worlds will be expected to match, and whether that is affordable without a
   per-world latest-figure endpoint (which does not exist).
4. **The lede's heading.** "The latest from the economy" above a card that
   usually says "no new tracked change" is still a slight mismatch.

---

## 9. Production-preparation addendum (2026-09-22)

### 9.1 Imagery — §8.1 partially resolved

The route is **verified U.S. federal public domain first, paid licence second**.
One asset now clears that bar and is in the prototype; three do not.

- **Rates — VERIFIED.** Carol M. Highsmith, *U.S. Treasury Department Building*,
  Library of Congress, LC-DIG-highsm-16870. The commercial basis is the
  photographer's own dedication of the archive's rights, not merely the
  item-level "no known restrictions" advisory.
- **Inflation, Jobs, Housing — UNRESOLVED.** The Highsmith archive is
  architecture and landscape, and the wider no-known-restrictions pool is
  historical (1880–1950). A 1940 grocery photograph on a page whose whole claim
  is *current, sourced* data is a contextual misrepresentation. They keep the
  marked placeholder treatment.

Full evidence, the searches run, and the rights problems found in the four
candidate images supplied with this task: `docs/product/mockups/v48/ASSETS.md`.

**A new acceptance rule came out of that review:** no legible price, figure or
date may appear inside a photograph unless the product intends to stand behind
it. One candidate image showed a shelf price tag — on an Inflation tile that
reads as a data claim MacroChipz is not making.

### 9.2 Attribution is rendered twice

At 7.5px with `white-space: nowrap`, the on-tile credit was silently
ellipsising at 440px. The chip is now 9px and wraps, and the **full required
credit line is carried verbatim in the footer** beside the Census notice. A
truncated attribution is not an attribution.

### 9.3 The Treasury figure was audited independently — MATCH

`5.01%` on `2026-09-18` was re-checked against
`/api/v1/series/UST_NOMINAL_10Y/observations`, a different endpoint from the
monitor the snapshot was captured from. All four maturities match (2Y 4.76,
5Y 4.86, 10Y 5.01, 30Y 5.34), `kind: SOURCE_OBSERVATION`,
`methodology_id: rates_v1.0`, provider TREASURY.

### 9.4 Copy

Hero headline is now **"Explore the living economy."** The quiet panel is
compacted and its two actions carry button weight rather than link weight —
the majority state gets design attention, per v47 §4.1.5.

### 9.5 Production integration

Planned in `docs/product/macrochipz-living-economy-v48-integration-plan.md`.
The governing finding: **the frontend contains zero images today**, so this is
the introduction of a new asset class, not a restyle. No new dependency is
required — `sharp` is already present.

---

## 10. Production integration — shipped (2026-09-22)

The homepage at `/` is now the Living Economy page. What follows is what
actually shipped, including where it departs from §1–§9 and why.

### 10.1 Composition

Hero → THE LEDE → what else was recorded → **Featured discovery** →
Questions people ask → Current State → Inflation and Jobs, side by side →
Releases → When a number changes → image notice.

`WorldOrientation` (#45B) was **retired**, component and test together. Its
job — name the four worlds and their latest data line — is the hero's now.

**Two duplicate world grids were removed.** Before this, a reader could meet
Housing three times within one screen: in `WorldOrientation`, in the quiet
lede's grid, and in the unknown lede's grid. A page-level test asserts exactly
one control per world.

`HomeQuestions` lost `explain.fed-and-mortgage-rates` and gained
`explain.why-the-10-year-matters`. That is not a demotion: the story built on
the first question now has its own band directly above, and the replacement is
the question a reader has immediately after.

### 10.2 The surface belongs to the shell

`<main data-surface="cinematic">`, set by `layouts/pageSurface.ts` from the
pathname. No negative margins, no `overflow: hidden`, nothing simulated —
`#46F`'s `-my-6` is the reason that is stated rather than assumed.

### 10.3 Deviations from the prototype, and the reasons

| Prototype | Shipped | Why |
|---|---|---|
| Quiet panel actions "See where things stand" / "When the next data lands" | "See when the next data is scheduled" (`/calendar`) and "How every figure is produced" (`/explain`) | Both routes exist. "See where things stand" would have pointed at the four worlds — which are now directly above it. |
| Treasury curve snapshot | **Deferred**, per the brief | It would put a network dependency in front of the one section that survives an outage. |
| PLACEHOLDER chips on three tiles | Composed gradients, no chips | A prototype announces its gaps; a shipped homepage does not wear a label saying so. The gap is stated in the page's image notice and in ASSETS.md. |
| Side panel beside a 2×2 tile block | Four tiles across from `md`, panel below | Measured: at 1440 the 2×2 block was 522px tall against a 172px panel, so two thirds of the right column was empty. |

### 10.4 Defects found by measuring, and fixed

1. **The hero's lighting was invisible.** It shipped as a `::before` at
   `z-index: -1`. A negative z-index child paints inside the nearest *stacking
   context* — the root, since nothing between created one — so it landed above
   the root background and beneath `<main>`'s, which is opaque. It is now the
   surface's own background: full-bleed by construction, no positioned element,
   no way to overflow.
2. **The light theme was unreadable.** A `[data-surface]` page is dark by
   design but was reading `--mc-fg` from the active theme, which in light
   resolves to near-black — measured at `oklch(0.22 0.018 262)` on
   `rgb(18, 19, 23)`. Fixed by listing the dark surfaces beside
   `:root[data-theme="dark"]`. **This also fixes the same latent defect on the
   story page**, which had it and had never been opened in the light theme.
3. **The credit was illegible over the photograph.** White text at the
   top-right corner sits on the pale stone pediment — the brightest part of the
   frame — at **1.12:1**. It now carries its own scrim: **4.78:1** worst-case,
   measured by compositing the actual crop and both overlays. A `text-shadow`
   had made it look survivable and changed the measured ratio not at all.
4. **`sizes` was guessed.** `22vw` against a tile that is 28vw at 1024 and a
   fixed 390px beyond 1280, where `max-w-app` caps the column.

### 10.5 Not fixed, and why

**The header overflows horizontally at 768px, on every page.** The theme
toggle's fieldset ends at x=786 in a 768px viewport. Confirmed identical on
`/rates` and `/calendar`, so it predates this work and belongs to `AppShell`,
not to the homepage. Reported rather than fixed: it is a shared-shell change
affecting every route, and it deserves its own increment.

### 10.6 §8 unresolved items, revisited

1. **Imagery route** — decided: verified federal public domain first, paid
   licence second. One of four verified; see ASSETS.md for the other three.
2. **Default selection** — still Rates, still a bet.
3. **One real measure on the homepage** — deferred with the curve visual.
4. **The lede's heading** — unchanged and still slightly mismatched.
5. **NEW: the light theme now shows a light header above a dark page.** It is
   legible and looks deliberate, but it is a seam, and whether `/` should
   simply be dark-only is a design decision nobody has made.

---

## 11. #48A — the rest of the page (2026-09-23)

The hero, visual identity and Treasury photograph were approved unchanged.
This pass brought everything below them to the same standard.

### 11.1 One data composition

THE LEDE and "Also recorded" are one card. Same world, same date, same source —
they were two sections with a rule between them. Every value, as-of date,
world, methodology link and evidence link is preserved; the rail keeps its own
`h3` heading because it is a **different selection**, and collapsing that
distinction would hide `homepage_presentation_v1.0`.

No new API call. `selection.whatChanged` was already fetched.

### 11.2 The featured preview explains itself

Six named actors (HTML labels over the SVG, so type size does not scale with
the `viewBox`), the legend, and — composed from the registry's `setBy` field —
which two of the six anyone sets and who sets them. The six nodes, two `sets`
edges and four `influences` edges are the reviewed registry unchanged, and
`fed-funds → treasury` is still absent. The route to the interactive story is
still a filled button.

### 11.3 Two-column editorial lower page

| Column | Contents |
|---|---|
| Main | Current State (Inflation and Jobs as peer cards, side by side from `md`), the #23C juxtaposition sentence, Questions people ask |
| Rail | Releases (schedule, uncertainty labels, both frozen disclosures, calendar link), When a number changes |

Failure isolation is unchanged: each domain keeps its own grid cell and its own
loading/error/success branch.

**One repetition was deliberately kept.** `HowTheyRelate`'s two CTAs duplicate
the cards' own. `docs/product/relate-composition-v1.md` freezes that component
as the sentence "plus the two existing CTAs — nothing else", so removing one
belongs to a contract change, not a layout pass.

### 11.4 The 768px header overflow — cause and fix

Cause: the header row is `flex-nowrap` at `md` with 705px available and 762px
of content, and nothing shrinks because `min-width: auto` is a flex item's
default. Present on every page, not only `/`.

Fixed by holding the wordmark tagline until `lg` (−75px, and it is duplicated
in the footer), tightening the `md` gap (−16px), and **removing `flex-nowrap`**
so a future overflow becomes a second line instead of a sideways scroll.

### 11.5 Measured

| | 390 | 440 | 768 | 1440 |
|---|---|---|---|---|
| Horizontal overflow | 0 | 0 | 0 | 0 |
| Clipped text | 0 | 0 | 0 | 0 |
| New controls < 44px | 0 | 0 | 0 | 0 |
| Document height, before → after | 4792 → 4886 | 4740 → 4680 | 4481 → 3869 | 4181 → 2850 |

Mobile is 94px taller on purpose: the network labels and the who-sets-what list
are content the page did not previously have.

---

## 12. #48B — final responsive polish (2026-09-23)

Presentation only. No data contract, eligibility rule, attribution or economic
logic touched; no new dependency, request or chart.

### 12.1 The discovery strip

The selected-world panel was a 154px card holding two lines of text and one
button. It is now a strip: description and route on **one row from `sm`**,
stacked only where the line genuinely needs the width. 154 → **136px** on a
phone, 70px on a desktop. The CTA is still 44px at every width — the strip is
shorter because the padding and the gap shrank, never because the target did.

The 2×2 tile grid is unchanged, as approved.

### 12.2 The story comes before the chart on phones

Measured at 390×844: the featured story began **1,637px** down, behind a full
screen of Treasury chart. Constitution §3 makes the mortgage-rate
misconception the acquisition wedge, and it was the least reachable thing on
the page.

`StoryTeaser` renders **below `lg`**, immediately after the discovery strip and
before the readings card. `FeaturedStory` renders **from `lg`**. The story is
therefore offered exactly once at every width, and desktop keeps its existing
editorial order. Nothing was removed: the chart, its values, its as-of date and
its evidence links are unchanged and sit directly beneath.

The teaser's question is the #44 registry's own; its count is derived from
`rateNetwork`, and its glyph draws that registry's real edges — decorative and
`aria-hidden`, which is not a licence to draw a shape the model does not have.

### 12.3 Less prose around the preview

"Six actors sit between a Federal Reserve decision and the rate a lender quotes
you. Only two of them are set by anyone at all." was true and registry-derived,
and redundant beside a diagram naming six actors and a list showing exactly two
being set. Removed. The six named actors, the exact edge semantics and both
documented set-by relationships are retained; the full detail stays in the
story. The count still appears on the mobile teaser, where no diagram carries
it.

### 12.4 Release rail

19rem → **21.5rem**, `pl-10` → `pl-8`. Measured at 1440 with the narrower rail,
a release row gave its name 169px and "Personal Income and Outlays" broke
across two lines; it is now one line at 215px. `ReleaseRow` itself is untouched
because `/releases` renders it too — the column changed, not the component.
Dates, uncertainty labels, both frozen disclosures and the calendar link are
unchanged, and `HowTheyRelate` was not reopened.

### 12.5 Measured

**Mobile first screen, 390×844, before → after**

| | Before | After |
|---|---|---|
| Document height | 4,886 | **4,108** (−16%) |
| Discovery panel height | 154 | 136 |
| Story reachable at | 1,637px | **651px** (fully on the first screen) |
| Hero bottom | 592 | 512 |

**All five viewports, all four selected worlds** (20 combinations): zero
horizontal overflow, zero clipped text, zero new controls under 44px, every
CTA 44px and routed correctly, exactly one story invitation.

One element at 1024 reports a box past the viewport — a `span` inside a
**closed** `<details>` in a release row. Opening all six produced zero
overflow, and `scrollWidth === clientWidth` throughout. A measurement artifact,
not a defect.

Contrast on the new teaser, against the strongest end of its tint: kicker 6.16,
question 11.24, meta 4.86, arrow 7.43. Identical in both themes, because a
`[data-surface]` page carries the dark palette regardless of theme (#48).

Keyboard: tab order is DOM order is visual order — four tiles, strip CTA, story
teaser, chart links. Selection works from the keyboard and focus stays on the
control. All 8 animated elements carry `motion-reduce`, and the teaser has its
own reduced-motion rule. The prerendered HTML contains the h1, all four worlds,
the teaser and its link, and the Library of Congress credit.

### 12.6 #48C — the teaser reads as an invitation

Layout and placement unchanged. Presentation only.

- The registry glyph sits in a **lit 56px frame**, which is what turns it from
  an icon decorating a navigation row into a thumbnail of somewhere you can go.
  Nodes gained a halo, drawn *under* the cores — a halo over an edge swallows
  it, which is the #46E layering defect.
- A round arrow badge sits on the frame's **top-right**. That corner is chosen,
  not default: bottom-right is conventional and it landed directly on the
  `mortgage-rate` node, which the registry puts at x 78, y 92. Covering one node
  of a six-node diagram to make room for decoration is the wrong trade; the
  top-right is empty, with `treasury` at y 41.6 well clear. Measured: **0 of 6
  nodes under the badge**.
- The badge is also what kept the height. With the arrow at the far right of
  the strip, the 56px frame plus a 28px chip plus their gaps took 36px off the
  text column, pushed the meta line to three lines and grew the strip
  133 → 153px. On the frame's corner it costs nothing: **133px at both 390 and
  440**, meta back to two lines.
- The whole strip is still one `<a>` with **zero nested interactive elements**,
  so there is one tab stop, one focus ring (the global 2px `:focus-visible`
  outline wraps the entire card) and no dead area under a thumb. The badge is
  `aria-hidden`, so it adds nothing to the accessible name.

Measured at 390 and 440: teaser fully inside the first screen (651–784px at
390), zero page overflow, nothing clipped, glyph inside its frame, badge inside
the strip, tab position 6 after the four tiles and the strip CTA, and the
reduced-motion rule covers the strip, the frame and the badge.

No prose added, no economic model change, no hero redesign, no chart moved.
