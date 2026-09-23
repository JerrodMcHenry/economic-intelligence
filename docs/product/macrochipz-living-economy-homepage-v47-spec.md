# The Living Economy — homepage specification

**Increment #47, phase 1.** Specification and visual prototype only.
**Date:** 2026-09-22
**Status:** awaiting design review. No production route touched.
**Prototype:** `docs/product/mockups/v47/index.html`

---

## 1. What this page is for

One job: **a visitor who has never heard of MacroChipz should, within one
screen, understand that this is four connected parts of the economy, checkable
to the source — and be one tap from the part they came for.**

It is not a terminal, a dashboard, a SaaS landing page, an article feed or a
constellation. The test for every element: *does it help someone discover, or
does it decorate?*

### 1.1 The visitor we are designing for

Two arrivals, in this order of priority:

1. **From a short-form video**, looking for the mortgage-rate story by name.
   They must find it without scrolling past a hero they did not ask for.
2. **Cold, from search or a link**, asking "what is this?" They need
   orientation, not activity.

Both are served by the same page because both need the same thing first: *what
are the parts, and which one is mine?*

---

## 2. Section hierarchy

| # | Section | Job | Always present? |
|---|---|---|---|
| 1 | **The Living Economy** | Orientation. Four worlds, identifiable and selectable. | Yes |
| 2 | **What's happening** (THE LEDE) | The single most recent eligible development, or an honest quiet state. | Yes — one of four states |
| 3 | **Start exploring** | A route into each world with what it holds and why it matters. | Yes |
| 4 | **Discovery paths** | The mortgage-rate story and selected explainers. | Yes |
| 5 | **Trust** | One row to sources, methodology, revisions and limits. | Yes |

**Order is deliberate.** Orientation precedes news because on most days there is
no news (§4), and a page whose first section is frequently empty teaches people
it is empty. The hero is *four buttons and a panel*, not a title sequence — it
must not delay §3.

---

## 3. The Living Economy hero

### 3.1 What it shows

Four worlds — **Inflation, Jobs, Rates, Housing** — each a luminous, selectable
object in a shared field. Selecting one updates a panel with what that world
holds, why an ordinary person might care, and a link into its existing page.

### 3.2 The hard rule: no edges

**The homepage draws no connections between worlds.** The mortgage story's
diagram is a causal-ish model where an edge means "reaches" and is defended by
reviewed sources. The homepage's four worlds are **navigation categories**. A
line between Inflation and Jobs would assert a relationship nobody wrote down
and no source backs.

So the hero borrows the *lighting* — violet depth, lavender glow, glass panels,
restrained starfield — and **none of the topology**. Worlds are grouped by
proximity in a shared field, never joined.

`HowTheyRelate` already exists and *does* state a defended relationship between
inflation and labour. It stays where it is, lower on the page, in words.

### 3.3 Selection model

- Default selection on load: **Rates**, because it is the acquisition wedge
  (Constitution §3) and the world the video traffic is arriving for.
- One world selected at all times; never zero. A hero that opens explaining
  nothing has wasted the only screen it gets.
- Selecting is not navigating. Focus stays on the control; the panel is a
  polite live region. A second, explicit link enters the world.

---

## 4. THE LEDE — four states, preserved

The existing eligibility model (`homepage_presentation_v1.0`, #42) is not
modified. This page renders its four outcomes; it does not re-decide them.

| State | When | What the page shows |
|---|---|---|
| **Development** | An eligible object exists | The object, its world, its effective period, and a route to its evidence |
| **Bootstrap / coverage** | The freshest object is a coverage or first-observation record | **Nothing is promoted.** These are excluded by policy and stay excluded — they are the 1,488 coverage events and 358 first observations the filter exists for |
| **Quiet** | No object is eligible | "No new tracked change", the honest caveat, the four worlds, the calendar |
| **Unknown** | The request has not resolved or failed | An explicitly unresolved state — *not* the quiet state |

### 4.1 Rules that cannot be traded for visual appeal

1. **Never render the quiet state while the answer is unknown.** Doing so bakes
   "nothing happened" into prerendered HTML before anything has been asked.
2. **Never promote an ineligible object to fill the slot.** The fallback for an
   empty lede is the quiet state, not the freshest thing available.
3. **No clock.** Eligibility and ordering stay pure functions of the objects.
   Staleness is communicated by *showing the effective period*, never by hiding
   an object for being old.
4. **No manufactured urgency.** No "live", no pulsing dot implying a feed, no
   relative-time phrasing that ages badly in static HTML.
5. **The quiet state must be genuinely useful** — it is the majority state
   (roughly two-thirds of business days have no release), so it gets design
   attention, not an apology.

---

## 5. Start exploring

Each world states three things, and each is constrained:

| Field | Rule |
|---|---|
| **What you can learn** | The registry `description`, verbatim. |
| **Why it matters** | A consumer consequence. Must be supportable from reviewed explainer copy. |
| **What MacroChipz actually has** | The tracked measures, **and what it does not track**. |

The third field is the one that earns trust. Housing says permits, starts and
completions — *and* that MacroChipz tracks no prices, sales or affordability.
Rates says Treasury yields — *and* that it does not track mortgage rates.

**No world may advertise a capability the product does not have.**

---

## 6. Discovery paths

- The **mortgage-rate story** is surfaced by name and by its question, because
  that is the phrase video traffic is searching for.
- **Selected explainers** — the curated `FEATURED_EXPLAINER_IDS` set, unchanged.
- Nothing is ranked by popularity or personalised. The rabbit hole is a path
  someone chose to dig.

---

## 7. Trust

One row, not a wall: **Sources · Methodology · What changed · Limitations**.

- The Census non-endorsement sentence stays in the footer, verbatim, on every
  page that can show Census-derived figures.
- The design must not imply currency, completeness or authority the data lacks:
  no "live" badges, no animated counters, no fabricated timestamps, no
  precision beyond what is published.

---

## 8. Accessibility

- All interactive targets ≥ 44 × 44 CSS px.
- Native `<button>` and `<a>`. Selection is `aria-pressed`; the panel is
  `aria-live="polite"` and does not steal focus.
- Visible focus everywhere (`:focus-visible`, existing 2px `--mc-focus`).
- Every transition paired with `motion-reduce:transition-none`; **no meaning
  carried by motion**. The ambient field is decorative and pauses under
  `prefers-reduced-motion`.
- DOM order equals visual order equals tab order.
- Contrast: body text ≥ 4.5:1, meaningful graphics ≥ 3:1, verified by
  measurement rather than by eye.

---

## 9. Responsive behaviour

| Width | Hero | Lede | Worlds | Discovery |
|---|---|---|---|---|
| ≥ 1024px | Two columns: world selector left, panel right | Full width | 4 columns | 3 columns |
| 768px | Stacked, selector as a row | Full width | 2 columns | 2 columns |
| 390–440px | Stacked, 2×2 world grid, panel below | Full width | 1 column | 1 column |

- Mobile is designed first and is not a compressed desktop.
- The hero must not exceed **one screen** before §2 begins.
- Zero horizontal overflow at every width; measured on rendered bounds, not
  `document.scrollWidth` — a control can sit on top of another without making
  the document any wider.

---

## 10. Failure and empty states

| Failure | Behaviour |
|---|---|
| Intelligence API unavailable | Lede renders the **unknown** state. Hero, worlds, discovery and trust are unaffected — none of them fetch. |
| No eligible object | **Quiet** state. |
| JavaScript never runs | Hero renders with its default selection, all four worlds are links, every section is present. |
| `prefers-reduced-motion` | Ambient motion stops; nothing is lost. |

**The hero and the world routes never depend on a request.** Orientation must
survive an outage, because an outage is exactly when someone is most likely to
be confused about what this site is.

---

## 11. Acceptance criteria

1. On a 390px viewport, the four worlds and the selected panel are usable
   without scrolling past an oversized hero.
2. Selecting each of the four worlds updates the panel and offers a working
   route to the existing page. No inert controls.
3. The lede renders the quiet state without a fabricated headline, and the
   unknown state is visibly distinct from it.
4. No line, arrow or edge is drawn between worlds anywhere on the page.
5. Every world's capability text names at least one thing MacroChipz does
   **not** track.
6. Zero horizontal overflow, zero overlapping controls, zero targets under 44px
   at 390, 440, 768 and 1440px — measured.
7. Keyboard: every world reachable and selectable; focus visible; focus stays
   on the control after selection.
8. Census attribution present and verbatim.

---

## 12. What to retain, replace or move

| Existing | Verdict | Why |
|---|---|---|
| `TheLede` + `selectHomepage` policy | **Retain unchanged** | The eligibility model is the honest core of the page. Only its presentation changes. |
| `WorldOrientation` | **Replace** | Its job — name the four worlds and their latest data line — is done better by the hero. |
| `HomeQuestions` (featured explainers) | **Retain, move** | Belongs in Discovery paths (§6), lower than it sits today. |
| `RecentIntelligence` ("What changed") | **Retain, move** | Useful, but it is evidence, not orientation. Below the lede. |
| `CurrentStateSection` | **Retain, move** | Inflation and labour state with methodology. Belongs inside those worlds' entries, not on the hero. |
| `HowTheyRelate` | **Retain, move** | The one defended cross-world relationship. Keep it in words, below the fold — it is the honest version of the edges the hero refuses to draw. |
| `UpcomingReleasesPreview` / `RecentReleasePreview` / `ReleaseScheduleDisclosure` | **Retain, move** | Calendar preview belongs near Trust, with its frozen disclosure sentence unchanged. |
| `RevisionsLink` | **Retain, move** | Into the Trust row. |
| `PageHeader` "The economy right now" | **Replace** | The hero is the header. |

### 12.1 Dependencies and missing data

- **No new API is required.** Every section renders from endpoints the homepage
  already calls.
- **The hero needs nothing.** It is registry-driven and static, which is why it
  survives an outage.
- **Missing, and worth naming:** there is no per-world "latest figure" endpoint,
  so a world tile cannot show a live number without four extra calls. This
  prototype deliberately shows none — and §7's rule against implying currency
  means adding them later needs an effective-period label, not just a value.

---

## 13. Unresolved product decisions

1. **Does the hero earn its screen on repeat visits?** A returning reader may
   want the lede first. Not resolvable without traffic; the order is a bet.
2. **Default selection.** Rates is chosen for the acquisition wedge. If most
   arrivals are cold rather than video-sourced, Inflation may serve better.
3. **`HowTheyRelate` placement.** It is the only defended cross-world claim, and
   burying it may waste the product's most interesting sentence — but promoting
   it to the hero reintroduces exactly the edges §3.2 forbids.
4. **Quiet-state prominence.** If quiet is the majority state, is "What's
   happening" the right heading for a section that usually says "nothing new
   here"?

---

## 14. Out of scope for phase 1

Production routes, any API change, OG image generation, personalisation,
analytics events, the Follow/Brief work from #46A, and any change to economic
methodology or canonical data.
