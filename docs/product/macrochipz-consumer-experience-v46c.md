# MacroChipz Consumer Experience & Visual Direction

**Increment #46C — product design plus one bounded working prototype**
**Date:** 2026-09-22
**Status:** design proposal + working prototype, awaiting review
**Prototype route:** `/story/fed-and-mortgage-rates` (additive, `noindex`, reversible)

---

## 0. What this document is, and the one thing to check first

This is a design document with a working artifact attached. The artifact is
one route. Everything else here is a proposal that has not been built.

Before reading the argument, the honest headline:

> **The prototype is measurably better on four things and measurably worse on
> one. It is 34% longer than the page it reimagines.** Whether the trade is
> worth making is a product judgement, and §G states both sides rather than
> selling one.

Nothing in this document was deployed, committed or pushed. No `.env` value was
read. No production data was touched. No licensing question was resolved that
was open before.

---

## Part A — What the product actually is on a phone

### A.1 The measurement problem, and how it was finally solved

Increments #45A and #45B both reported mobile findings with a caveat, because
`resize_window` reported success while `matchMedia('(min-width: 640px)')` kept
returning `true`. Every "mobile" observation in those audits was really a
narrow desktop window: Tailwind's `sm:` styles were still applied, so the audits
were describing a layout no phone ever renders.

#46B diagnosed the cause (window resizing is not device emulation). #46C fixed
it. A **same-origin iframe** has its own viewport, and media queries inside it
resolve against the iframe's width:

```js
const frame = document.createElement('iframe');
frame.style.cssText = 'position:fixed;left:0;top:0;width:390px;height:844px;border:0';
frame.src = '/story/fed-and-mortgage-rates';
document.body.appendChild(frame);
// frame.contentWindow.innerWidth                              -> 390
// frame.contentWindow.matchMedia('(min-width:640px)').matches -> false
```

**Every number below was taken with that gate passing.** It is the first
genuinely mobile measurement of MacroChipz in the project's history, which also
means the mobile findings in #45A and #45B should be treated as provisional
wherever they disagree with this document.

### A.2 The measurements

iPhone-class viewport, 390 × 844, local dev server, live API:

| Surface | Page height | Controls | Under 44px | Under 24px | Horizontal overflow |
|---|---|---|---|---|---|
| `/` | 4.9 screens | 32 | **28** | 25 | 0px |
| `/rates` | 8.0 screens | 46 | **40** | 35 | 0px |
| `/housing` | 4.8 screens | 11 | **11** | 6 | 0px |
| `/inflation` | 5.9 screens | 40 | **28** | 25 | 0px |
| `/jobs` | 5.4 screens | 34 | **22** | 19 | 0px |
| `/calendar` | 3.2 screens | 45 | **45** | 43 | 0px |
| `/revisions` | 1.6 screens | 7 | **7** | 5 | 0px |
| `/explain` | 3.1 screens | 17 | **17** | 9 | 0px |
| `/explain/fed-and-mortgage-rates` | 3.8 screens | 9 | **5** | 4 | 0px |
| **`/story/fed-and-mortgage-rates`** | **5.1 screens** | **19** | **2** | **1** | **0px** |

### A.3 What that table says

**The layout is genuinely sound.** Zero horizontal overflow on every surface at
390px. Nothing is clipped, nothing needs a pinch, nothing scrolls sideways.
That is not typical and it should be said plainly, because the rest of this
section is critical and the criticism is narrower than it will sound.

**The touch layer is not.** The recurring offender is
`ExplanationTrigger` — the small "i" that opens a curated explanation — which
renders at **16 × 16 px**. WCAG 2.5.8 asks for 24px; 2.5.5 asks for 44px. It
is under both, it appears many times per page, and it is the primary discovery
affordance for the product's best content. `/rates` alone has dozens.

`/calendar` is the worst surface in the product: 45 controls, **all 45** under
44px, 43 of them under 24px. It is a dense table shown at phone width.

**Depth is the second problem.** `/rates` is eight screens. A reader arriving
from a video scrolls for eight screens before running out of page, and the
thing that brought them — one specific question — is not what any of those
screens is organised around.

**The explainers are the exception and the opportunity.** `/explain/fed-and-
mortgage-rates` is 3.8 screens, has only 9 controls, and is the best-written
thing in the product. It is also, at 390px, **1,063 characters of text on the
first screen and zero interactive elements**. It answers the question in its
first paragraph and then explains for another 2,600 characters.

That is an excellent encyclopedia entry. For someone who arrived from a
thirty-second video it is a step *down* in energy from what brought them, and
it asks for a reading commitment before it has earned one.

---

## Part B — Visual direction

The direction is **not** a restyle. MacroChipz's visual language — the token
system in `styles/globals.css`, the dark canvas, the type scale, the
hand-authored SVG charts of ADR-041 — is doing its job. Nothing below proposes
replacing it.

What is proposed is a **second mode** that uses the same tokens.

| | Reference mode (today) | Story mode (proposed) |
|---|---|---|
| Unit of design | The page | The scene |
| Density | Everything visible, scan-optimised | One idea per screen |
| First screen | Orientation and data | A question and a thing to tap |
| Interaction | Annotation (the "i") | Commitment (choose, then learn) |
| Reader's job | Find what they need | Get carried to the end |
| Where it belongs | Worlds, Calendar, Revisions, objects | Explainers |

Three visual commitments the prototype makes, all expressible in existing
tokens:

1. **Numbered scenes with a rule between them.** `1 / 6`, `2 / 6`. A reader on
   a phone always knows how much is left, which is the single cheapest defence
   against abandoning a long page.
2. **56px as the story control height** (`min-h-14`), 44px as the floor
   (`min-h-11`) for anything else. Not a guideline — a test asserts it (§F.3).
3. **Motion is ornamental and always optional.** Every transition in the
   prototype carries `motion-reduce:transition-none`; verified in the built CSS
   and on all 20 animating elements in the live DOM (§F.4).

And three refusals:

- **No scroll hijacking.** No scroll-snap, no swipe capture, no fixed
  full-height panels. A story that fights the scrollbar is a story people leave.
- **No animation library.** The prototype adds zero dependencies.
- **No "story" chrome on data.** A progress bar over a Treasury yield chart
  would be dressing reference material as entertainment, which is the failure
  mode this direction is most likely to produce if generalised carelessly.

---

## Part C — The consumer experience model

#45A framed the funnel as **WOW → UNDERSTAND → EXPLORE → SHARE → RETURN** and
found RETURN entirely missing (which #46A then specified). #46C is about the
first two stages, and specifically about the seam between them.

The product's current seam is: a video creates interest, the explainer
satisfies it in one paragraph, and then the page continues for 2,600 more
characters that the reader has no remaining reason to read. **The explainer is
optimised for the person who wants the answer, and MacroChipz's opportunity is
the person who wants the answer *and might have stayed*.**

The model the prototype tests:

1. **Do not resolve the question on screen one.** Surface the belief instead.
2. **Make the reader commit before correcting them.** A confident wrong belief
   is not fixed by reading a correction; it is fixed by being caught holding it.
3. **Then give them the explanation they now want**, in the same words the
   canonical explainer uses.
4. **Let verification be a choice, not a wall.** Sources and limitations are one
   tap away, present for anyone who wants them, not in the path of anyone who
   does not.
5. **End pointing somewhere**, including at live data, so the story is a door
   into the product rather than a leaf.

---

## Part D — The signature story prototype

**Route:** `/story/fed-and-mortgage-rates`
**Source:** `frontend/src/routes/story.fedMortgage.tsx`,
`frontend/src/components/story/RateAuthorityQuiz.tsx`,
`frontend/src/components/story/InfluenceExplorer.tsx`

### D.1 The seven beats

| # | Beat | What it is | Where the words come from |
|---|---|---|---|
| — | **Hook** | "Wait, seriously?" → the question as `<h1>` → the misconception stated as a belief the reader may hold | `explainer.question`, `explainer.misconception` |
| 1 | **Interact** | *The Fed sets exactly one of these. Which?* Four rates; the reader must choose before anything is revealed | written for #46C, basis `INSTITUTIONAL_ROLE` |
| 2 | **Reveal** | What the Fed actually controls | `explainer.whatItIs`, `explainer.answer` |
| 3 | **Explore** | The four influences, convergent not sequential, each opening on tap | verbatim from #44's `InfluenceDiagram` |
| 4 | **Means** | What this means if you are borrowing | `explainer.whatThisMeansForYou`, `explainer.howItWorks` |
| 5 | **Verify** | Basis statement + named sources + limitations, both behind disclosures | `BASIS_COPY`, `explainer.limitations`, sources verified in #45 |
| 6 | **Continue + Share** | `/rates`, `/housing`, all three curated related explainers, existing `ShareButton` | `explainer.related` |

The hook is unnumbered and the beats are numbered 1–6, because the hook is not
something the reader does — it is the page introducing itself.

### D.2 Why the interaction is a quiz, and why this quiz

The brief required an interaction that **teaches**, and was explicit that
decorative animation does not count. So the question was: what can a reader
*do* that changes what they understand?

The misconception here is not a gap in knowledge. It is a **confident wrong
belief**. People do not think "I wonder who sets mortgage rates"; they think
"the Fed does". Reading a correction does very little to a confident belief.
Being asked to commit to it, and then being shown the answer, does considerably
more.

So: four interest rates, one question — *which one does the Fed actually set?*
— and nothing is revealed until the reader picks. A reader who picks "your
30-year mortgage rate" has just performed the misconception on themselves,
which is a far better setup for the correction than a paragraph asserting that
people commonly believe it.

What it refuses to do:

- **No quantified Fed-to-mortgage relationship.** Nothing says a Fed move
  produces a mortgage move of any size, direction or timescale. The question is
  *who sets what*, which is institutional role — the explainer's own declared
  basis.
- **No score, no streak, no "2 of 4".** One choice, one correction, move on.
  Being wrong here is the normal case and the entire point of the page.
- **No live data.** Not one figure on the whole route, which is why it
  prerenders completely and has nothing that can fail.

One precision that mattered: the Fed does not set *the* federal funds rate —
the FOMC sets a **target range**, and the effective rate is determined between
banks within it. Writing "the Fed sets the federal funds rate" would have been
the same species of imprecision the page exists to correct, so the correct
answer's own reveal says what actually happens.

### D.3 Why the influence explorer is the weaker of the two interactions

It is progressive disclosure, and that is a smaller claim than the quiz makes:
**it does not change what a reader believes, it changes how much they have to
read at once.** That is a comprehension gain on a small screen, not a teaching
mechanism, and this document should not pretend otherwise.

It earns its place because the alternative on mobile is skimming four stacked
paragraphs. And it keeps #44's actual argument intact: all four influences and
the convergence line are visible with zero interaction, so the shape — several
things converging, Fed policy one of them, *not* a chain — is the first thing
you see. Only the detail collapses.

### D.4 Verification is not decoration

The Verify beat is what makes this MacroChipz rather than an explainer video
with better typography. Three sources, each carrying its own weight honestly:

- **Fannie Mae**, *What Determines the Rate on a 30-Year Mortgage?* — the
  30-year rate benchmarked to the 10-year Treasury with a primary-secondary
  spread (origination, servicing, guaranty fees, lender profit) and a secondary
  spread (prepayment and credit risk).
- **NY Fed Staff Report 674**, *Understanding Mortgage Spreads* — agency MBS
  yield spreads as a key determinant of homeowners' funding costs, shown **with
  the disclaimer that a Staff Report is its authors' research and not a
  position of the Bank or the System.** It corroborates; it does not establish.
- **CFPB** — mortgage price dispersion often around 50 basis points of APR
  across virtually every market segment, and most recent borrowers believing
  price would be the same whichever lender they chose.

A test asserts the Staff Report disclaimer is present, and another asserts that
no institution appears on the page except these three.

---

## Part E — Prototype boundaries

Everything here is designed so that **deleting three files and three registry
lines removes the prototype completely.**

| Property | How it is held |
|---|---|
| Permanent URLs unchanged | `/explain/fed-and-mortgage-rates` is untouched, still prerendered with its own content, still in the sitemap |
| No search competition | The story ships `<meta name="robots" content="noindex">` and a `<link rel="canonical">` pointing at the explainer |
| Not in the sitemap | `generate-sitemap.mjs` now reads each prerendered page's own HTML and excludes any that declare `noindex` |
| No drift between the two | Every sentence with a canonical home is **imported** from `explainers/registry.ts` or from `BASIS_COPY`, never retyped |
| Not in navigation | No nav entry, no homepage link, no explainer-index entry. It is reachable only by URL, which is what a prototype under review should be |
| No new dependency | Zero. A test enumerates the imports of all three files and allows only `react` and `react-router` |
| No live data | Zero fetches, zero figures. A test asserts it |

The only change to existing application code is a one-word `export` on
`BASIS_COPY` in `routes/explainer.tsx`, so the story states the same basis
sentence rather than a second copy of it.

Three changes were made outside the prototype, each because the prototype
exposed a real gap rather than because it needed a favour:

1. **`Disclosure` gained an optional `summaryClassName`.** Its `<summary>` rows
   measure **20px tall** at 390px — a fine reading affordance and a poor tap
   target. The default is byte-identical to what every existing caller already
   renders; the story opts in to `min-h-11`. §H proposes what to do about the
   other call sites.
2. **`generate-sitemap.mjs` excludes `noindex` pages.** Listing a URL in a
   sitemap while its HTML says `noindex` hands a crawler two contradictory
   instructions. Read from the built HTML, not a hand-maintained list, so it
   cannot drift.
3. **`verify-build-output.mjs` no longer exits early when no intelligence
   pages were prerendered.** It used to `process.exit(0)` in that case — which
   is the *normal* local and frontend-CI build — meaning the #44 explainer
   checks it also contains had been silently skipped there since they were
   written. They now run, alongside new checks that the story ships with real
   prerendered substance, `noindex`, and a canonical that does not point at
   itself.

---

## Part F — Verification

### F.1 Automated

| Check | Result |
|---|---|
| `npm test` | **1,880 passed / 77 files**, including 33 new prototype tests |
| `npm run lint` (oxlint) | clean |
| `tsc -b` | clean |
| `npm run build` (prerender + sitemap + verify) | passes; `[sitemap] wrote 19 prerendered URL(s); excluded 1 that declare noindex` |
| Prerendered story HTML | 4,735 characters of text without JavaScript; `robots: noindex`; canonical → `/explain/fed-and-mortgage-rates` |
| Backend | untouched; no Python, migration or API change in this increment |

### F.2 Genuine 390px mobile verification

All with `innerWidth: 390` and `matchMedia('(min-width: 640px)').matches === false`:

| Requirement | Observed |
|---|---|
| Story progression | 6 numbered scenes, ordinary document flow, no scroll interception |
| Hook + full interaction on first screen | **both fit in the first 844px** — 4 tappable options above the fold |
| Navigation | shell breadcrumb and skip link work; no nav regressions |
| Tap targets | 19 controls, **2 under 44px** — both the pre-existing shell breadcrumb (`MacroChipz` 24px, `Rates` 20px); every control the story adds is ≥44px |
| Interactive controls | quiz reveals nothing before commitment; after commitment the chosen option and the correct one both explain; `aria-pressed` tracks the choice; `aria-live` announces the correction; "Try again" resets |
| Explorer | `aria-expanded` toggles, detail appears, convergence and caveat always visible |
| Charts / diagrams | none on this route by design (no live data) |
| Source disclosure | both `<details>` open and show all three sources and both limitations |
| Sharing | existing `ShareButton` present and ≥44px |
| Horizontal overflow | **0px** |
| Reduced motion | 20 animating elements, **all 20** carry `motion-reduce:transition-none`; the built CSS emits `@media (prefers-reduced-motion:reduce){.motion-reduce\:transition-none{transition-property:none}}` |

### F.3 Desktop and tablet

| Width | `sm:` | Overflow | Widest control | Height |
|---|---|---|---|---|
| 390px | false | 0px | 343px | 4,320px |
| 768px | true | 0px | 576px | 3,714px |
| 1280px | true | 0px | 576px | 3,781px |

A first pass had the option cards stretching to **1,118px** at 1280px — a
1,100px-wide tap target for a four-word label. Constrained to `max-w-xl`, which
does not bind at 390px. Every real prose block carries `max-w-prose`; the only
full-width text elements are two-to-four-word scene labels and two arrows.

### F.4 Two defects the prototype's own tests caught

Worth recording because in both cases the fix was the code, not the guard:

- The tap-target guard failed on an inline `<Link>` in the closing footnote.
  Correct call: the guard was right and the layout was wrong. The link moved
  onto its own line as a 44px target.
- An earlier version of the same guard read source with a regex that stopped at
  the first `>` — which `onClick={() => …}` contains — and so failed a control
  that was in fact 56px tall. The guard was rewritten to assert on the
  **rendered tree** instead.

---

## Part G — The prototype against the explainer

This is the section that decides whether any of this is worth doing, so it is
split into what was **measured** and what is **assumed**.

### G.1 Observed, at a genuine 390px viewport

| | `/explain/fed-and-mortgage-rates` | `/story/fed-and-mortgage-rates` |
|---|---|---|
| Page height | **3.8 screens** | 5.1 screens |
| First-screen text | 1,063 chars | **537 chars** |
| Interactive controls on first screen | **0** | **4** |
| Controls under 44px | 5 of 9 | **2 of 19** (both pre-existing shell) |
| Horizontal overflow | 0px | 0px |
| Prerendered text without JS | 3,510 chars | 4,735 chars |
| New economic claims | — | **0** |

Four things are measurably better: **half the reading commitment on the first
screen**, an interaction available before any scrolling, a touch layer that is
compliant rather than 5-of-9 non-compliant, and more substance available
without JavaScript.

One thing is measurably worse, and it is not a small thing: **the story is 34%
longer.** A reader who only wanted the answer now scrolls further to leave.
That is the real cost of the format and it should not be argued away.

The design's defence is that the answer is *still* one screen in — the reveal
is beat 2 — so the extra length sits *after* the point at which a
question-only reader is already satisfied. Whether that holds for real readers
is not something this increment can know.

### G.2 Assumed, and explicitly not validated

Everything in this list is a hypothesis. Building the prototype did not test
any of it:

- That commitment-then-correction changes belief more durably than reading a
  correction. **The mechanism is well-supported in learning research in
  general; its effect on this page has not been measured.**
- That a video-sourced reader stays longer in the story than in the document.
- That six numbered scenes reduce abandonment rather than signalling length.
- That the quiz reads as a genuine question rather than as a quiz someone put
  on an explainer.
- That readers open the Verify disclosures at all. The product has a
  `evidence_expanded` event and this route does not yet emit one.
- That any of this increases returning readers, which is #46A's problem, not
  this one's.

**What would actually settle it:** both routes exist and are independently
reachable, so a comparison is available whenever there is traffic to compare —
scroll depth to the Continue beat, disclosure-open rate, and share rate, on
each. That instrumentation is deliberately *not* in this increment.

### G.3 What the prototype does not fix

- It fixes tap targets **on one route**. `/calendar` still has 45 controls of
  which 45 are under 44px, and `/rates` still has 40 of 46.
- It does not touch page depth anywhere else; `/rates` is still 8 screens.
- `ExplanationTrigger` is still 16 × 16px everywhere it appears.
- Twelve explainers exist. One has a story.

---

## Part H — Proposed scope for #46D

### H.1 What to do, in this order

**H.1.1 — Fix the touch layer product-wide (do this first, and separately).**
It is the largest measured defect, it is independent of every design question
in this document, and it needs no story format to justify it. Scope:
`ExplanationTrigger` from 16px to at least 44px, `Disclosure` summaries from
20px to 44px (the `summaryClassName` seam already exists — #46D should decide
whether to flip the default instead), and `/calendar`'s 45 sub-44px controls.
**This is worth shipping even if the story format is rejected outright.**

**H.1.2 — Decide the story format on one more explainer, not on all twelve.**
The obvious second candidate is *"Wait, inflation falling doesn't mean prices
are falling?"* — same shape of defect (a confident wrong belief), and a
plausible interaction (a reader commits to what "inflation fell" implies about
a price they pay). If the second one is as easy to build honestly as the first,
the format generalises. If it needs a stretched claim to produce an
interaction, that is the format telling you it does not.

**H.1.3 — Instrument before generalising further.** §G.2's list is long and
every entry is cheap to answer with the event vocabulary that already exists.
Two stories with real numbers beat twelve built on a hypothesis.

**H.1.4 — Only then, decide adoption.** Three outcomes are all legitimate:
story replaces explainer at the canonical URL; story stays a parallel format
for a handful of high-traffic questions; or the explainer absorbs the two or
three specific wins (interaction above the fold, 44px targets, numbered
progression) without the scene structure. **The third is the cheapest and this
document does not rule it out.**

### H.2 Patterns that must NOT be generalised

- **The quiz.** It works because this specific misconception is a confident
  wrong belief with a clean four-way factual answer. Most explainers have no
  such structure, and inventing one produces exactly the fake-interactivity the
  brief prohibited. **An explainer without a genuine misconception should not
  get a quiz.**
- **Numbered scenes on reference pages.** `1 / 6` over a Treasury yield table
  would imply a narrative the data does not have.
- **Progressive disclosure on live data.** Collapsing a figure behind a tap
  hides the thing the page exists to show. The explorer works because its
  content is *explanation*, not observation.
- **`noindex` + canonical.** That pairing is correct for a prototype and wrong
  for anything adopted. If a story becomes the primary experience it must take
  the canonical URL, not sit beside it.

### H.3 Surfaces to keep out of story format entirely

- **Calendar.** It answers "when is the next release" — a lookup. Its defect is
  touch-target size and density, not a missing narrative. Story format would
  make a reference tool slower to use.
- **Revisions.** It is a record of what changed and when. Dramatising a
  revision history is exactly the "significance ranking" the Structured
  Intelligence design (#39) deliberately refused, in a new costume.
- **Intelligence object pages.** They are permanent, citable artifacts. Their
  job is to be stable and verifiable, not engaging.
- **World pages.** Arguable, and #46D should not settle it by default. They are
  the product's reference layer; the right fix for `/rates` at 8 screens is
  probably better hierarchy, not a story.

---

## Appendix — Files

**New**
- `frontend/src/routes/story.fedMortgage.tsx`
- `frontend/src/routes/story.fedMortgage.test.tsx` (33 tests)
- `frontend/src/components/story/RateAuthorityQuiz.tsx`
- `frontend/src/components/story/InfluenceExplorer.tsx`

**Modified**
- `frontend/src/routes.ts` — one route registration
- `frontend/src/build/prerenderPaths.ts` — one prerender path
- `frontend/src/routes/explainer.tsx` — `export` on `BASIS_COPY`
- `frontend/src/components/Disclosure.tsx` — optional `summaryClassName`
- `frontend/scripts/generate-sitemap.mjs` — exclude `noindex` pages
- `frontend/scripts/verify-build-output.mjs` — run static checks always; verify stories

**To revert entirely:** delete the four new files, revert the two one-line
registry entries, and revert `export` on `BASIS_COPY`. The three other changes
are independent improvements and should be kept regardless of the format
decision.
