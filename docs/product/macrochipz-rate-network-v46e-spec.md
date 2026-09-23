# Rate Network Story — implementation specification

**Increment #46E.** Written before production code, per the brief.
**Route:** `/story/fed-and-mortgage-rates` (existing prototype route, repurposed)
**Visual baseline:** `docs/product/mockups/v46e/luminous-mockup.html` (approved)

---

## 1. What this replaces, and why

#46C shipped a prototype at this route: a six-scene scrolling article whose
centrepiece was a commitment quiz. The #46E brief supersedes it explicitly —
*"the central object is an interactive economic network, NOT a scrolling article
with a quiz."*

So this increment **rewrites that route** rather than adding a second prototype
beside it. Two prototype URLs for one story is the sprawl #46C itself warned
about, and the route's surrounding contract — `noindex`, canonical pointing at
`/explain/fed-and-mortgage-rates`, prerendered, absent from navigation — is
already correct and is kept unchanged.

`RateAuthorityQuiz.tsx` and `InfluenceExplorer.tsx` are removed. **Their prose is
not lost**: every reviewed sentence they held moves into the network registry
(§3), and a guard test asserts that no node text says anything those sources did
not already say.

**Nothing at a permanent URL changes.** `/explain/fed-and-mortgage-rates` is
untouched.

---

## 2. Architecture

### 2.1 The one decision that shapes everything else

**Visuals are SVG. Interaction is HTML.**

The SVG draws the field, halos, edges and node cores, and is `aria-hidden`. Every
node is an absolutely-positioned HTML `<button>` layered over it, placed by
percentage so it tracks the SVG's coordinate space at any width.

Three problems disappear at once:

1. **Tap targets stop depending on SVG scale.** #46D shipped 41px controls
   because 48 SVG user units looked like 48 pixels; a scaled `viewBox` makes user
   units a ratio, not a measurement. An HTML button with `min-height: 44px`
   cannot be shrunk by a `viewBox`.
2. **Accessibility comes from the platform.** Focus ring, tab order, Enter/Space
   activation, `aria-pressed`, and an accessible name are native to `<button>`.
   SVG `role="button"` needs all four hand-built and gets them subtly wrong.
3. **The behaviour becomes testable in jsdom**, which has no layout engine — so
   any assertion about SVG geometry is meaningless there, while button semantics
   are fully assertable.

A second consequence, learned the hard way in the mockup: **SVG `filter` and
gradients default to `objectBoundingBox` units**, and a perfectly vertical edge
has a zero-width bounding box, so both silently render nothing. Direct edges
therefore use `gradientUnits="userSpaceOnUse"` and stacked strokes rather than a
blur filter. A test asserts this.

### 2.2 Modules

| File | Responsibility |
|---|---|
| `src/explainers/rateNetwork.ts` | The curated registry: six nodes, six edges, every string traceable to reviewed copy. No React. |
| `src/components/story/RateNetwork.tsx` | Renders the diagram (SVG) + node buttons (HTML). Controlled: takes `selectedId` and `onSelect`. |
| `src/components/story/NodePanel.tsx` | The compact selected-node panel. Pure presentation. |
| `src/components/story/ShareCardPreview.tsx` | The 9:16 card, rendered from the registry. |
| `src/routes/story.fedMortgage.tsx` | Owns `selectedId`, composes the above, carries meta. |
| `src/styles/globals.css` | Adds a **scoped** `[data-surface="luminous"]` token block. |

**Removed:** `RateAuthorityQuiz.tsx`, `InfluenceExplorer.tsx`.

### 2.3 State

One piece of state, in the route:

```ts
const [selectedId, setSelectedId] = useState<NodeId>(DEFAULT_SELECTED_ID);
```

No context, no store, no reducer, no URL parameter. Selection is ephemeral view
state; putting it in the URL would create shareable links whose canonical target
is a different page.

`selectedId` is never `null`. **A diagram that starts with nothing selected is a
diagram that starts by explaining nothing**, and the prerendered HTML would carry
an empty panel. The default is `fed-funds`, because it is the node the
misconception is actually about.

---

## 3. Economic accuracy

### 3.1 The traceability rule

> **Every user-visible sentence about the economy must be a contiguous substring
> of a string that was already reviewed.**

Reviewed sources are the #44 explainer registry entry and the #46C copy carried
in `docs/product/mockups/v46d/content.js`. Trimming a quiz-specific opener
(*"This is the one."*) is permitted because deleting a clause cannot add a claim.
Rewording is not. `rateNetwork.test.ts` enforces this mechanically.

### 3.2 The six nodes

| id | Label | Role text (source) |
|---|---|---|
| `fed-policy` | Federal Reserve policy | influence detail — *"Sets a short-term rate between banks, and shapes what investors expect next."* |
| `fed-funds` | Federal funds rate | quiz reveal — *"The Fed's committee sets a target range for it — the rate banks charge each other for lending overnight…"* |
| `treasury` | Treasury yields | quiz reveal — *"Investors set this by buying and selling government debt. The Fed's decisions shape what investors expect, but the Fed does not choose the number."* |
| `mbs` | Mortgage-backed securities | influence detail — *"Investors buy pools of home loans, and what they will pay feeds back into pricing."* |
| `lenders` | Mortgage lenders | influence detail — *"Credit conditions, the chance a loan is repaid early, and what each lender needs to earn."* |
| `mortgage-rate` | Mortgage rates | quiz reveal — *"Lenders set this, competing with each other… two lenders can quote you different rates on the same day."* |

### 3.3 The six edges

| From | To | Kind |
|---|---|---|
| `fed-policy` | `fed-funds` | **sets** |
| `fed-policy` | `treasury` | influences |
| `treasury` | `mbs` | influences |
| `treasury` | `lenders` | influences |
| `mbs` | `lenders` | influences |
| `lenders` | `mortgage-rate` | **sets** |

**Two direct edges, at opposite ends, with nothing but influence between them.**
That shape is the explanation, and it is why the legend is not optional.

**`fed-funds → treasury` is deliberately absent.** The mockup drew it, but the
reviewed copy routes the Fed's effect on long-term rates through *expectations*
(*"that decision ripples through what investors expect"*), not through the funds
rate itself. Drawing the shortcut would assert a mechanism the sources do not.

**Edges carry no prose.** They have a `kind` and nothing else; all explanation
lives on nodes. This makes it impossible for an edge to acquire a claim, and it
is why `relation` is not a field.

### 3.4 Language the brief called out

*"Six things decide what you are quoted"* is replaced. It implies both an
exhaustive list and a deciding mechanism. The replacement names the diagram as
partial and the reviewed caveat sits under it permanently:

> **Some of what reaches the rate you're quoted — and which parts anyone actually
> sets.**
> *These interact rather than forming a single chain, and their relative
> importance changes over time. This shows what feeds in, not a formula.*

### 3.5 Hard prohibitions

No figure, no live data, no fetch, no quantified Fed-to-mortgage relationship, no
direction, no magnitude, no timescale, no forecast, no new canonical claim, no
change to any frozen methodology.

### 3.6 A Constitution tension recorded rather than hidden

**§19.1** requires every explainer to link at least one claim to a live
MacroChipz figure. This prototype embeds none — #44 made that choice for the
canonical explainer, and #46C kept it, because a page with no data cannot fail
and can be prerendered whole.

The Constitution's *required movement* (CONCEPT → CURRENT DATA → RELATED WORLD →
EVIDENCE) is satisfied by the onward links to `/rates` and `/housing`, which is
where the live figures are. **It is satisfied by navigation, not by embedding**,
and that is a narrower reading than §19.1 as written. Flagged for a decision, not
resolved here.

---

## 4. Interaction

### 4.1 Selecting a node

1. Node button is pressed (tap, click, Enter or Space).
2. `selectedId` updates.
3. The node's core and halo brighten; its label chip gains the selected treatment.
4. Edges touching it become **related**; all others become **dim**.
5. The panel replaces its content and announces via `aria-live="polite"`.
6. **Focus stays on the button.** The panel is not focus-stolen — a selection is
   not a navigation, and moving focus would strand a keyboard user.

### 4.2 Dimming that stays accessible

Unrelated edges dim to `opacity: 0.32`, never to invisibility, and the floor is
chosen so the dimmed stroke stays above 3:1 against the field. The brief is
explicit: dim without making meaningful graphics inaccessible.

**Dimming is never the only signal.** Direct and indirect edges differ by dash
pattern and arrowhead as well as by brightness, so the distinction survives
monochrome rendering, low vision and forced-colours mode.

### 4.3 Keyboard

Native buttons in DOM order. Tab reaches each node; Enter and Space select.
Focus is visible via `:focus-visible` (the app already defines a 2px
`--mc-focus` outline globally). No arrow-key roving tabindex: six buttons do not
need one, and it would cost more than it buys.

### 4.4 Reduced motion

Every transition is a CSS class paired with `motion-reduce:transition-none`.
There is no animation, only transitions — so under `prefers-reduced-motion` the
interface changes state instantly and remains completely understandable, because
**no meaning is carried by movement**. Asserted by test.

---

## 5. Responsive behaviour

### 5.1 Mobile (390px, the design target)

- Network is the first substantial element. Hook is two short lines above it.
- **Network and panel both fit above 844px.** The panel sits *below* the diagram,
  not over it — a bottom sheet would obscure the very node it describes, which
  the brief forbids.
- The panel is fixed-height enough not to reflow the page on every selection.
- Every node button ≥ 44 × 44 CSS px.
- Zero horizontal overflow.

### 5.2 Desktop

Same composition, centred, with a max width. The diagram does not stretch to
fill — an edge-to-edge node graph at 1280px reads as a screensaver.

### 5.3 Verification method

`window.innerWidth === 390` and `matchMedia('(min-width: 640px)').matches ===
false`, measured inside a same-origin iframe. **OS-window resizing is not
evidence** — it reported success for three increments while `sm:` styles stayed
applied.

---

## 6. Visual contract

Carried over from the approved mockup, unchanged:

| Token | Value | Origin |
|---|---|---|
| accent / node rim | `#9facf1` | `--mc-brand`, shipped dark theme |
| selected / highlight | `#a2b0ff` | `--mc-focus`, shipped dark theme |
| text | `#e9ebef` / `#bdc1c8` / `#979ca3` | `--mc-fg*`, shipped |
| field | violet ramp + two blooms | **extended** — the shipped canvas is hue 262 at chroma 0.008, effectively neutral |

**Cyan is refused.** `--mc-state-cool` (`#85c8e6`) carries economic meaning under
the #27B hard rule; a cyan accent would collide with a classification. The second
luminous accent is violet-magenta at hue ~300.

New tokens are `--lx-*` and live in a **scoped** `[data-surface="luminous"]`
block, so the four disjoint `--mc-*` families and their guard test are untouched.

---

## 7. Security

No user input, no `dangerouslySetInnerHTML`, no network request, no secret, no
new dependency, no third-party script, no URL parameter parsed. The share card
renders registry constants only. Attack surface added: none.

---

## 8. Failure modes

| Failure | Behaviour |
|---|---|
| JavaScript never runs | Prerendered HTML carries the diagram, the default selection's panel, the takeaway and the sources. Static, correct, readable. |
| CSS fails to load | Semantic HTML order: hook → diagram → panel → takeaway → sources → onward. |
| `backdrop-filter` unsupported | Cards fall back to a solid violet surface; contrast is unchanged because the fallback colour is declared, not assumed. |
| Forced-colours / high contrast | Edge kind survives via dash pattern and arrowhead. |
| `prefers-reduced-motion` | Instant state change; nothing lost. |
| API down | Irrelevant — this route makes no request. |

---

## 9. Tests

`src/routes/story.fedMortgage.test.tsx` and `src/explainers/rateNetwork.test.ts`:

**Registry**
1. Six nodes, six edges, exactly two of kind `sets`.
2. The two `sets` edges are `fed-policy→fed-funds` and `lenders→mortgage-rate`.
3. Every node role is a contiguous substring of a reviewed source string.
4. No edge carries prose.

**Interaction**
5. Six node buttons, each with an accessible name.
6. Default selection is explained on first render.
7. Selecting each of the six updates the panel to that node's role.
8. Selected button reports `aria-pressed="true"`, others `false`.
9. Related edges are marked related and unrelated ones dim, per selection.
10. Keyboard activation works.
11. Focus remains on the activated button.

**Content safety**
12. No quantified Fed-to-mortgage relationship anywhere, at any selection.
13. No forecast language.
14. The exhaustive phrasing is absent.
15. The reviewed caveat is present.

**Structure**
16. `noindex` and the canonical to `/explain/fed-and-mortgage-rates` still ship.
17. Onward links to `/rates`, `/housing` and the canonical explainer.
18. Sources and limitations reachable.
19. Every transition class pairs with `motion-reduce:transition-none`.
20. Direct-edge gradient uses `userSpaceOnUse`, and no edge uses a bbox filter.
21. Node buttons declare a ≥44px minimum in their class list.

**Share card**
22. Takeaway matches the registry.
23. Branding, attribution and the preview marker present.
24. No figure appears on the card.

Tap-target *geometry* is verified in the browser, not in jsdom, which has no
layout engine. The test asserts the declared minimum; the browser measures the
rendered one.

---

## 10. Acceptance criteria

1. `npm test`, `npm run typecheck`, `npm run lint`, `npm run build` all pass.
2. At a verified 390px: network + panel above the fold, 0px horizontal overflow,
   every interactive target ≥44px, all six selections correct.
3. Desktop renders without stretching the diagram edge to edge.
4. Reduced motion: no loss of meaning.
5. Screenshots captured for opening, at least two selections, mobile panel,
   desktop and share card; deviations from the mockup documented.
6. No permanent URL changed; no frozen methodology touched; nothing committed.

---

## 12. Responsive refinement (measured pass)

The first implementation passed every check I ran and still had three
real defects, because I had been measuring the wrong thing. Document
`scrollWidth` reported **zero overflow at every width** — and one control
sitting on top of another does not make a document any wider.

Measuring the **rendered box of each of the six controls** instead:

| Width | Board | Unused | Overlaps | Outside board |
|---|---|---|---|---|
| 440px | 330 | **110px** | `mbs x lenders` 146x5px | — |
| 390px | 330 | 60px | `mbs x lenders` 146x5px | — |
| 320px | 273 | 47px | **three pairs** | `mbs` by 8px |

### The overlap was arithmetic, not bad luck

Nodes sat at 11/25/39/58/70/91. Two of those are twelve points apart,
which on a 330px board is 40px — and each chip is a 44px tap target. It
had to overlap, on every render, and worsen as the board narrowed.

**Fix:** even 16.8-point spacing with alternating sides. Minimum
separation is now `0.168 x boardWidth`, which clears 44px for any board
at least 262px wide. `rateNetwork.test.ts` asserts the arithmetic, so the
guarantee cannot quietly regress when someone nudges a node.

### The clipping was an offset that disagreed with itself

A chip is pushed 14px away from its dot, but its `maxWidth` allowed a
flat 2% margin — 2% of the *board*, which is under 14px on anything
narrower than 700px. So the longest chip hung outside the diagram.
`maxWidth` now uses `calc()` with the same 14px the transform uses, so
the two cannot disagree.

### The unused width was a cap that had outlived its reason

The 330px phone cap existed to keep the panel above the fold. Removing it
lets the board fill the column — and because the board is square, width
*is* vertical room, so growing it also fixed the overlap. The intro was
compacted to pay for the extra height.

### Results, all six selections at each width

| | 390px | 440px | 312px (390 @125% zoom) |
|---|---|---|---|
| Board | 343 | **393** | 265 |
| Overlaps / clipped / under-44px | **none** | **none** | **none** |
| Explanation ends at | 720px | 750px | — |
| "Who sets it" ends at | 789px | 819px | — |

### What is honestly still true

**The whole panel does not fit above 844px at 440px** (it ends at 884).
The *explanation* and the *who-sets-it* claim both do, comfortably; what
falls at the fold is the collapsed `Connections` toggle, whose content
the diagram already shows by highlighting. Fitting the entire panel as
well would mean capping the board back to ~339px, which is where this
started.

**Below ~309px CSS width the overlap returns.** Measured: 312px is clean
at 45px separation; 294px collides at 41px. That is a 390px phone beyond
about 125% browser zoom. Fixing it properly means reflowing the board to
a single column at narrow widths, which is a layout mode rather than a
tweak — proposed, not smuggled in here.

---

## 13. Narrow-screen fallback

### 13.1 The breakpoint is derived, not chosen

Six chips are 44px tall and sit 16.8 percentage points apart, so their
separation is `0.168 x boardWidth`. The board is the column minus a
gutter measured constant at 47px, so the layout survives while

```
0.168 x (viewport - 47) >= 44   =>   viewport >= 308.9px
```

Confirmed by measurement, not by the formula alone: **312px is clean at
45px of separation; 294px collides at 41px.** The switch sits at
**312px**, three pixels above the arithmetic floor. The chips
`truncate`, so a larger user font cannot wrap them onto a second line
and raise the floor underneath the breakpoint.

### 13.2 What the fallback is

**The same six buttons, in the same DOM order, stop being absolutely
positioned and become a flex column.** The SVG hides — a scatter diagram
that cannot separate its own labels is not worth drawing — and
`lx-link` rows take its place.

It is pure CSS, in the `[data-surface="luminous"]` block. No second set
of controls, no JavaScript measuring anything, no `matchMedia` in React,
and therefore nothing that can mismatch at hydration or differ between
the prerender and the browser.

### 13.3 How the two relationship kinds survive

Each connector row carries a rule and a word:

| Kind | Rule | Word |
|---|---|---|
| `sets` | 3px solid, full opacity | SETS |
| `influences` | 2px dashed, 55% opacity | INFLUENCES |

Two independent signals, as in the network, so the distinction survives
monochrome and forced-colours rendering.

**The simplification, stated plainly.** A column can only draw an edge
between rows that are adjacent. Four of the six edges are;
`fed-policy → treasury` and `treasury → lenders` skip a row and are
**not** drawn. They are not lost — the panel's `Connections` disclosure
lists every relationship of the selected node, at every width. Adjacency
without a connector means "no relationship between these two", which is
true, so the diagram never implies an edge that does not exist.

### 13.4 Node order

Registry order, DOM order, top-to-bottom visual order and the column
order are now **the same sequence**. Tab order therefore matches what a
sighted user sees, and the column reads as a sequence rather than as six
items in an arbitrary order. A test asserts it.

This cost the old "sides alternate" rule, which conflicted with keeping
`fed-policy → fed-funds` perfectly vertical. That verticality is worth
more: a vertical line has a zero-width bounding box, which is the
geometry that exposes bbox-relative gradients and filters rendering
nothing. A test now asserts a vertical `sets` edge still exists, so the
guard against that bug keeps a live example to fail against. The
spacing test, not the alternation rule, is what actually prevents
overlap.

### 13.5 Measured results

Every width, all six selections, measuring rendered control bounds:

| Viewport | Layout | Board | Overlaps | Clipped | Under 44px | Overflow |
|---|---|---|---|---|---|---|
| 294px | **column** | — | none | none | none | 0px |
| 312px | network | 265 | none | none | none | 0px |
| 320px | network | 273 | none | none | none | 0px |
| 390px | network | 343 | none | none | none | 0px |
| 440px | network | 393 | none | none | none | 0px |

At 294px in the column: DOM order equals visual order; all six
`aria-label`s carry the full accurate name; focus stays on the activated
button; 33 animating elements, all with `motion-reduce:transition-none`;
`Connections`, `The sources behind this` and `What this does not tell
you (2)` all still present.

Tests 1,917 across 78 files, typecheck, lint and production build pass.
Story chunk 6.7 KB gzipped; stylesheet 9.4 KB. No new dependency.

---

## 11. Out of scope

The Living Economy homepage, other worlds, any application-wide redesign, OG
image generation, real sharing infrastructure, new APIs, analytics events,
deployment. Hard stop after screenshots.
