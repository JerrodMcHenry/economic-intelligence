# MacroChipz Visual Directions — four proposals

**Increment #46D, phase 1 — visual exploration only**
**Date:** 2026-09-22
**Status:** four reviewable mockups, awaiting a decision. Nothing implemented.
**Latest addition:** Direction D, the Signal × Field Notes hybrid (§5A), plus the
eight-criterion comparison in §5B and two cross-product studies.

**Mockups:** `docs/product/mockups/v46d/` — open `index.html` to see all four side
by side at a genuine 390px, or open a direction on its own. The quizzes and the
diagrams are live, not pictures.

---

## 0. One thing to flag before the proposals

**#46C recommended against this work.** Its §B said, in as many words, that the
visual language "is doing its job" and that nothing should replace the token
system. You have looked at the running product and decided otherwise — that it
still reads as a dark economic dashboard. That is your call to make, and this
document is written on the assumption that it is settled.

Worth keeping the disagreement visible rather than quietly dropping it, because
it is a real risk to price in: MacroChipz's credibility currently comes partly
from looking sober. Three of the four directions below spend some of that
soberness. Only Broadsheet spends almost none — and the recommendation in §6 has
changed since the hybrid was built, so read §5B before §6.

---

## 1. Method

**One content file, four skins.** All four directions read from a shared
`content.js` containing every sentence, verbatim, from the reviewed explainer
registry and the #46C prototype components. No direction gets better copy than
another, and no direction can quietly acquire a new economic claim. If a layout
cannot carry that text, that is a finding about the layout.

**No quantified Fed-to-mortgage relationship** appears in any of them — no
direction, no magnitude, no timescale. The only numeric claim on any page is the
CFPB's dispersion finding, which is about lenders differing from each other.

**Every measurement below was taken at a real 390 × 844 viewport**, using the
same-origin iframe technique #46C established, with
`matchMedia('(min-width: 640px)').matches === false` verified each time.

**They are static mockups.** No build step, no framework, no network request, no
web font, no dependency. They are not routed, not indexed, not wired to the
application, and they touch no production code.

---

## 2. Measured, all four

Story height excludes the share-card zone, so the four are compared like for
like.

| | **A · Broadsheet** | **B · Signal** | **C · Field Notes** | **D · Hybrid** | *#46C prototype* | *explainer* |
|---|---|---|---|---|---|---|
| Story height at 390px | **3.36 screens** | 4.70 | 3.59 | 3.84 | *5.1* | *3.8* |
| Horizontal overflow | 0px | 0px | 0px | 0px | *0px* | *0px* |
| Controls under 44px | **0** | **0** | **0** | **0** | *2* | *5 of 9* |
| First tappable thing at | 623px | 775px | 625px | **470px** | ~520px | *never* |
| Actions above the fold | 3 | 1 | **4** | **4** | 4 | *0* |
| SVG controls, all labelled + focusable | 4/4 | 4/4 | 8/8 | 8/8 | — | — |
| Page weight (gzip) | 6.7 KB | **6.0 KB** | 7.4 KB | 9.6 KB | — | — |
| New dependencies | 0 | 0 | 0 | 0 | *0* | *0* |
| Reduced motion honoured | yes | yes | yes | yes | *yes* | *yes* |

All four are **shorter than the #46C prototype** and all four fix its two
remaining sub-44px controls. None has any CSS animation; all motion is
transitions, and all of it is disabled under `prefers-reduced-motion`.

### Defects found by measuring rather than by eye

Every one of these is fixed in the files. They are listed because the pattern
matters more than the individual fixes: **four of the six were invisible at a
glance and only appeared when something computed a number.**

| Where | What | Was | Now |
|---|---|---|---|
| B | authority line under a dimmed option | **1.99:1** | 5.5:1 |
| B | unlit pipes in the diagram | 1.75:1 | 3.2:1 |
| C | monospace captions and gutter numbers | 3.53:1 | 4.8:1 |
| C | dashed connectors | 2.0:1 | 3.4:1 |
| A | inactive flow lines in fig. 2 | 2.07:1 | 3.5:1 |
| D | unlit rail and chip outlines | 1.47:1 | 3.0:1 |

**C's quiz nodes measured 260 × 41 px** despite being 48 units tall in the SVG,
because the figure is scaled down to fit a 390px column. User units are not
pixels. Fixed to 58 units (~50px). D carries a `verifyTapTargets()` routine that
measures rendered geometry at load and warns in the console — the thing that
would become a real test if an SVG-interaction direction is chosen.

---

## 3. Direction A — **Broadsheet**

> *Credibility as the visual argument.* Paper, a serif that carries the whole
> page, rules instead of boxes, one ink accent used sparingly. It looks like the
> thing people already trust for careful economic explanation.

**What is actually different:** the canvas flips to warm paper; a serif does all
the arguing; the quiz becomes a ruled editorial list rather than cards, with the
correction set in italic behind a hairline; scene markers become figure
references (`FIG. 1 — WHO SETS WHAT`); the conclusion is a centred pull quote
between double rules; the share card is a newspaper clipping.

**Strengths**

- **Cheapest to ship and lowest-risk.** No structural change to the shell, no
  container contract to renegotiate, no new interaction pattern to test.
- **Spends no credibility.** Of the four, this is the only one where the visual
  register and the product's actual claim to authority point the same way. For a
  product whose differentiator is *sources and limitations*, that is not
  cosmetic.
- **Best reading experience.** Longest measured page of prose per screen, and the
  quiz reveals read genuinely well as italic asides.
- **Shortest page of the four** (3.36 screens of story) despite carrying the most text.

**Weaknesses**

- **Least video-native.** Someone arriving from a thirty-second clip meets a
  newspaper. That is a real mismatch and this document should not pretend
  otherwise — it is the same criticism #46C made of the existing explainer, and A
  only partly answers it.
- **Needs a real serif to look like the mockup.** The mockup renders in Iowan Old
  Style on macOS and falls back to Georgia elsewhere; those are noticeably
  different pages. Shipping it honestly means self-hosting one subsetted display
  serif.
- **Share card is the weakest of the four.** It is a headline on paper; there is
  nothing on it that could not be a screenshot of any article.
- **Two accent colours away from the existing indigo brand.** The oxblood is
  right for the direction and wrong for the current wordmark.

**Implementation cost — low-to-medium.** A scoped token override on the story
route (~30 lines), class changes to the two existing story components with **no
logic changes**, one new hand-authored SVG, and one woff2 (~30–45 KB subset) or
an accepted quality drop. No change to `PageContainer` or the shell.

---

## 4. Direction B — **Signal**

> *Match the energy of the thing that sent them.* Each beat is a full-bleed
> poster on its own colour field — void, bone, acid, deep — with type large
> enough that the screen cannot hold anything else.

**What is actually different:** colour fields replace a single canvas entirely,
so scrolling feels like turning cards; type runs to 46px at weight 800 with tight
tracking; the quiz is a stack of slabs and the right answer **flips to acid
yellow on black**; the diagram is four thick bars feeding a single sink; the
conclusion occupies a whole acid field; verification sits on a deep blue field
rather than being tucked away.

**Strengths**

- **By far the most stop-scroll energy**, and the most obviously *not* a
  dashboard. It is the only direction that answers the brief's "arriving from
  short-form video" literally.
- **Best contrast ceiling.** Acid on near-black measures 17.4:1. The palette is
  loud *and* accessible, which is unusual.
- **Verification is given a whole field of its own** rather than a disclosure at
  the bottom — the loudest direction is, oddly, the one that makes sources
  hardest to miss.
- **Lightest page** and no font strictly required to function.

**Weaknesses**

- **The direction most at risk of sensationalising**, which is a stated design
  principle. The mockup holds the line — no superlatives, no urgency, same
  sentences — but that discipline lives in review, not in the CSS. A future
  headline written *for* this treatment is where it would go wrong.
- **Longest page of the four** (4.70 screens of story) and **the slowest to a
  first action** (775px, one tappable thing above the fold). Poster type costs
  scrolling, and the brief asked for immediate comprehension. **Direction D was
  built specifically to keep this identity and fix this defect**, and measurably
  does: 3.84 screens and a first action at 470px.
- **Breaks the one-content-width contract** (#27A §12). Full-bleed fields mean
  the shell needs a way for a route to escape `PageContainer`. That is the
  largest structural change of the three.
- **Needs a self-hosted grotesk to look the same on Android and Windows.** A
  poster design that depends on one typeface's shapes cannot use a system stack
  and stay recognisable.
- **Four colour fields = four contrast surfaces.** Every text token has to be
  verified per field; one failure already surfaced.

**Implementation cost — medium.** Token set per field, a `PageContainer` escape
hatch, one woff2 (~35 KB), restyled components (again no logic change), one new
SVG, plus a per-field contrast test that does not currently exist.

---

## 5. Direction C — **Field Notes**

> *The diagram is the medium.* Cream plotting paper, monospace for every label,
> prose demoted to annotation. The reader is not told who sets what — they point
> at a node, and the answer is **drawn**.

**What is actually different, and it is the biggest difference of the three:**
the interaction moves *into* the figure. The reader sees the FOMC and four
unlabelled rates, taps one, and a line is drawn from the committee to the rate it
actually sets — past a red cross on the wrong pick, with `set by:` annotations
appearing on every node at once. **The correction is a change in the diagram, not
a paragraph appearing underneath it.**

**Strengths**

- **The best teaching mechanism of the original three, by a clear margin.** #46C argued
  the quiz works because commitment beats reading. C goes further: the answer
  arrives as a spatial fact. Being wrong is shown, not narrated.
- **Fastest to a first action and the most interactive above the fold** (4).
- **Most natural fit with what already exists.** ADR-041 already commits to
  hand-authored SVG with no charting library; this is that house style extended
  rather than a new one.
- **Best share card of the original three** — it carries the figure, which is the
  most screenshot-able artifact any of them produces. D's card does the same
  thing in a louder register.
- **No font needed.** `ui-monospace` is genuinely consistent across platforms,
  which none of the other directions' faces are.

**Weaknesses**

- **Highest ongoing cost, and it never stops.** The quiz lives inside a bespoke
  SVG, so it is authored per story rather than reused. A and B restyle one
  component; C rebuilds the interaction for every explainer.
- **Monospace prose is a genuine readability cost.** Six lines of monospace
  verdict text is heavy, and the mockup shows it. Confining monospace to labels
  would soften the identity considerably.
- **User units are not pixels.** The 41px tap-target defect found above is not a
  one-off — it is the permanent consequence of putting controls inside a scaled
  figure, and it needs a test that measures rendered geometry.
- **Coldest register.** "Checked" rather than "engaging"; it is the least likely
  of the three to stop a scroll.
- **Accessibility work is real.** Interactive `<rect>` elements need roles,
  labels, keyboard handling and visible focus — all present in the mockup, all
  easy to get wrong when authoring the ninth one by hand.

**Implementation cost — medium-high up front, high ongoing.** Token override, one
bespoke interactive SVG per story, a rendered-geometry tap-target test, plus the
same class changes as the others. Budget roughly a day per subsequent story that
A and B would not need.

---

## 5A. Direction D — **Signal × Field Notes**

> *The identity of a consumer media brand, the teaching of a schematic.* Signal's
> acid-on-void and poster weight, Field Notes' answer-as-a-drawn-connection, and
> a device that belongs to neither parent: **chips and traces**.

**Files:** `direction-d-hybrid.html`, `direction-d-companion.html`

### 5A.1 What it takes from each parent, and what it refuses

| | Taken | Left behind |
|---|---|---|
| **from Signal** | acid-on-void palette, weight-800 poster type, colour fields that turn like cards, verification on a field of its own | the opening — 46px type over four lines that pushed the first tappable thing to **775px** |
| **from Field Notes** | the answer arrives as a **connection being made**, `set by ___` appearing on every node at once | the plotting-paper grid and the monospace prose, which made C read as an instrument rather than as media |

### 5A.2 The device

Every actor is a **chip**. Every relationship is a **trace**. A relationship that
exists lights acid and reaches its chip; a relationship that does not exist is
drawn as a **stub that stops short, with a visible gap**.

That last part is the whole design. When a reader picks "your 30-year mortgage
rate", they do not get a paragraph explaining that the Fed does not set it —
**they watch the line fail to arrive**, while a second line lights up and lands
on the federal funds rate instead. The correction is a spatial fact.

It is also the product's own name rather than a borrowed metaphor, it is legible
at thumbnail size, and it survives being screenshotted — which matters for the
one artifact that leaves the site.

Before anyone answers, the rail runs from the FOMC **past all four rates and
touches none of them**. Branching it early would give the answer away; branching
it to all four would assert something false. An unbranched rail is the question,
drawn.

### 5A.3 The second figure

Four chips at equal weight, each with its own trace into a shared bus, into the
sink chip. Nothing is ordered, nothing is weighted, **no trace is thicker than
another**, and the registry's own caveat sits under it. A first version routed
entry points evenly along the bus and produced a tangle that implied an ordering
the figure does not claim; the top row now leaves sideways down the outer rails
and the bottom row drops straight, so nothing crosses anything.

### 5A.4 Cross-product fit

`direction-d-companion.html` carries two studies — the homepage and `/rates` — to
answer one question: does the identity survive where the job is *reference*?

**It does, under one rule: the identity travels, the story typography does not.**
Nothing in either study is set above 24px. The chip is still the unit and acid is
still the accent, but a world page is opened by someone who wants a number, so
the type is reference-sized, figures are tabular, and acid is reduced to a single
mark — which world you are in.

**Every figure in both studies is a redacted placeholder**, shown as a hatched
block. Inventing plausible economic values for a mockup is how a fabricated
number ends up in a screenshot, then in a deck, then in someone's head. The
layout can be judged without them.

### 5A.5 Strengths

- **Fastest to a first interaction by a wide margin: 470px**, against 623–775px
  for the other three. The hook and all four chips are on the first screen.
- **18% shorter than Signal** (3.84 vs 4.70 screens of story) while keeping the
  identity — which was the explicit brief.
- **Best share card of the four.** It carries the mini board — FOMC, the lit
  federal funds chip, the severed stub to "your mortgage rate" — plus the
  takeaway, the mark and the three cited institutions. It explains itself with
  the sound off, which is what a card leaving the site has to do.
- **The teaching mechanism is the strongest in this increment.** C's drawn answer,
  but in a register a video-sourced reader recognises.
- **Distinctive in a way that is ownable.** Chips and traces is a system, not a
  palette: it extends to thumbnails, to the worlds, to a second story.
- **No font strictly required** and **no dependency**; accessibility on all eight
  SVG controls (labelled, focusable, `aria-pressed`, keyboard-activated, visible
  focus, `aria-live` explanation).

### 5A.6 Weaknesses

- **Still inherits Signal's structural cost.** Full-bleed colour fields break the
  one-content-width contract (#27A §12); the shell needs a `PageContainer` escape
  hatch. Unchanged from B.
- **Still inherits Signal's sensationalising risk**, and the mitigation still
  lives in review rather than in code. The mockup holds the line — same
  sentences, no superlatives, no urgency — but a headline written *for* this
  treatment is where it would go wrong.
- **Heaviest page of the four** (9.6 KB gzip) because it carries two interactive
  boards. Still trivial in absolute terms.
- **Still inherits Field Notes' per-story authoring cost**, partially. The chip
  and trace primitives are reusable; the *routing* of each figure is not, and a
  badly routed board implies claims the content does not make (see §5A.3).
- **The severed stub is subtle at 390px.** It reads, but it is the one piece of
  the mechanism that would benefit from user testing rather than from my opinion.
- **To look identical on Android and Windows it wants a self-hosted grotesk**,
  same as B. It degrades acceptably without one; it does not stay *recognisable*
  without one.

### 5A.7 Implementation cost — **medium**

Between B and C, closer to B. Token set per colour field; the `PageContainer`
escape hatch; a reusable `<Chip>` / `<Trace>` SVG primitive pair; a
rendered-geometry tap-target test (the `verifyTapTargets()` routine in the mockup
is the prototype of it); a per-field contrast test; one woff2 if
cross-platform consistency matters. Roughly **1 day more than B up front**, and
**materially cheaper than C per additional story** because the primitives are
shared even though the routing is not.

---

## 5B. Signal vs Field Notes vs the hybrid

The brief asked for these three on eight criteria. Measured where measurable,
and marked **judgement** where not — the entries below are design assessment, not
user data. **No engagement, retention or reach figure appears anywhere in this
document, because none has been collected.**

| Criterion | **B · Signal** | **C · Field Notes** | **D · Hybrid** |
|---|---|---|---|
| **First-screen comprehension** *(measured: actions above the fold)* | 1 | 4 | **4** |
| **Time to first interaction** *(measured: px to first control)* | 775px | 625px | **470px** |
| **Visual distinctiveness** *(judgement)* | high — but the palette is the whole idea | high — but reads as an instrument | **high and systematic** — chips/traces extend beyond one page |
| **Teaching effectiveness** *(judgement)* | lowest — the answer is a colour change plus a paragraph | highest of the originals — the answer is drawn | **highest** — drawn, plus a failed connection shown |
| **Mobile usability** *(measured: story height, overflow, sub-44px controls)* | 4.70 screens, 0px, 0 | 3.59 screens, 0px, 0 | **3.84 screens, 0px, 0** |
| **Accessibility** *(measured)* | 4/4 SVG controls labelled + focusable; 2 contrast defects found and fixed | 8/8; 2 contrast defects + a 41px tap target, all fixed | **8/8; 1 contrast defect, fixed; ships a runtime tap-target check** |
| **Sharing** *(judgement)* | strong card, but it is type only | best of the originals — carries the figure | **best overall** — figure + takeaway + mark + three cited sources |
| **Implementation & maintenance** *(estimate)* | medium up front, **low ongoing** | medium-high up front, **high ongoing** (bespoke SVG per story) | **medium up front, medium ongoing** — shared primitives, per-story routing |

**Reading the table honestly.** D wins or ties on six of eight. It loses to C on
raw story length (3.84 vs 3.59 screens) and to B on ongoing maintenance, because
B's restyle-only approach is genuinely the cheapest thing to keep alive. Neither
loss is large; the maintenance one is the one that compounds.

**What the table cannot tell you.** Every entry above is about the artifact, not
about readers. Whether a drawn connection teaches better than a paragraph, and
whether a video-sourced reader stays longer in any of these than in the existing
explainer, are the two questions that matter most and neither has been measured.
#46C §G listed six such hypotheses; all six still apply, to all four directions.

---

## 6. Recommendation

**Direction D — Signal × Field Notes.** This changes the recommendation made
before the hybrid existed, and the reason is that the hybrid removed the specific
objection that had disqualified its parents.

- Signal was not recommended because its opening was slow (775px to a first
  action) and its identity risked outrunning its claims. **D fixes the first
  outright and measurably** — 470px, four controls above the fold, 18% shorter —
  and it keeps the second risk, which is managed in review, not in CSS.
- Field Notes had the best idea in the increment and the worst economics: a
  bespoke interactive SVG per story, forever. **D keeps the idea and shares the
  primitives**, so the per-story cost falls from "rebuild the interaction" to
  "route one figure".
- Broadsheet remains the cheapest and the most sober, and it is still the right
  answer **if the judgement in §0 goes the other way** — if MacroChipz's
  credibility is worth more than its reach. That is a business call, not a design
  one, and I am not the one holding it.

The thing that tipped it is narrower than "it scored best". It is that D is the
only direction where **the correction and the identity are the same object**. The
acid trace that makes the page recognisable in a thumbnail is the same acid trace
that shows a reader their belief failing to connect. In the other three the
identity is a skin over the teaching; here it *is* the teaching.

### What I am explicitly not claiming

- **Not that it will perform better.** No engagement data exists. §5B's judgement
  rows are design assessment.
- **Not that the severed-stub mechanism reads for everyone.** It is subtle at
  390px and it is the single element I would put in front of real readers first.
- **Not that the identity is finished.** The companion studies show it surviving
  two reference surfaces. They do not show it surviving Calendar, Revisions or an
  intelligence object page, and #46C was explicit that story format must not
  reach those.

### If D is chosen, the first three things to settle

1. **The `PageContainer` escape hatch** — the one structural change, and the only
   part that touches shared shell code.
2. **The tap-target test** measuring rendered geometry, not source. `verifyTapTargets()`
   in the mockup is its prototype; the 41px defect in C is why it exists.
3. **The typography rule from §5A.4, written down** — identity travels, story type
   does not. It is the rule most likely to be forgotten, and forgetting it is how
   a 42px headline ends up over a yield table.

## 7. Scope discipline

**What phase 1 did:** four mockups plus two companion studies, one shared content
file, one index page, one design document.

**What phase 1 did not do, per the brief:** no application redesign, no change to
canonical economic logic, no new API, no AI capability, no new data source, no
implementation of any direction, no commit, no push, no deploy, no `.env` access.
The only files added are under `docs/product/mockups/v46d/` and this document.
`frontend/` is untouched.

**Known rough edges in the mockups**, left as-is because a mockup is for deciding
and not for shipping: A's fig. 2 routes one flow line across a neighbouring box;
A's share card is loose in its upper third; B's highlight wraps raggedly on the
card; C's monospace verdict is long; D's severed stub is subtle at 390px and its
hook headline sits close to the FOMC chip on very short viewports.

---

## 8. Hard stop

Four directions are presented for approval. **Nothing will be implemented until
you pick one.** No production design system, no token changes, no
application-wide redesign, and no change to `frontend/` of any kind until you
choose.
