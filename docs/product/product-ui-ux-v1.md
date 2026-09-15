# Product UI/UX Audit + Labor Data Diagnosis + Design Contract — V1

**Increment #27A.** Audit + diagnosis + design contract only. No frontend redesign, no economic methodology change, no backend contract change, no deployment. Baseline: HEAD `f266467` ("Freeze Render production architecture (#26F)"), clean working tree. Verified fresh this increment: backend 1,605/1,605 passed, 0 skipped; frontend 1,137/1,137; typecheck/lint/build all clean.

This document is the authoritative design contract for #27B (Design System + Shell + Home + Theme), #27C (Overview/Inflation/Labor/Releases redesign + approved Labor remediation), and #27D (Responsive + accessibility + states + polish). Every finding is grounded in fresh, live inspection of the running application (screenshots taken this increment) and fresh source-code inspection — never inferred from memory of prior increments alone, though prior audits (#21, #23A, #26A) are read in full and reconciled against current reality throughout.

---

## §1. Required reading, reconciled against current reality

Read in full this increment: `docs/product/product-experience-audit-v1.md` (#21), `docs/product/overview-attention-model-v1.md` (#22A), `docs/product/relate-compare-audit-v1.md` (#23A) and `docs/product/relate-composition-v1.md` (#23B), `docs/product/historical-context-state-history-audit-v1.md` and `docs/product/state-duration-v1.md`, `docs/product/since-last-visit-v1.md`, `docs/product/post-return-loop-commercial-readiness-audit-v1.md` (#26A), `docs/product/production-reliability-deployment-v1.md` (#26B), `docs/product/render-production-architecture-v1.md` (#26F), `research/inflation_momentum/` methodology docs, `research/labor_momentum/LABOR_V1_FROZEN_METHODOLOGY.md` and `LABOR_WHAT_CHANGED_V1_FROZEN_METHODOLOGY.md`, `docs/architecture/current-architecture.md`, `docs/architecture/request-flows.md`, relevant `docs/ENGINEERING_JOURNAL.md` sections (#19A Overview, #20E Labor UI, #22B salience, #23C Relate, #24D State Duration, #25H Since Last Visit), and the governing ADRs (021, 023, 026).

**What has changed since #21's own audit (the last full product-experience pass) and is now confirmed still true, live:** the salience/noise fix (#22B) is live and working; Relate composition (#23C) is live; State Duration (#24D) is live; Since Last Visit (#25H) is built and tested but **live-broken** in this exact environment (confirmed again, fresh, §28) due to the same known dev-database schema drift #26A first found and every subsequent increment has deliberately left unrepaired. **Nothing about the visual design itself has changed since #21** — the "clean but flat" character #21 never formally scored (it was out of scope for that audit) is, this increment, the primary subject.

---

## §2. Fresh frontend architecture inspection

- **Shell**: `frontend/src/layouts/AppShell.tsx` — a plain header (product wordmark, text-only nav, active state = solid dark pill), a `<main>` landmark, `PageContainer` (`max-w-5xl`, responsive padding) as the one shared width primitive.
- **The double-width-constraint finding (new this increment, not previously documented):** every page additionally wraps its own content in `max-w-3xl` (`Overview.tsx:91`, `Inflation.tsx:36`, confirmed identical elsewhere) — **inside** the shell's own `max-w-5xl`. On a real desktop viewport (confirmed live, 1533px window) this leaves the majority of the screen as dead whitespace (screenshots, §3) — not a deliberate density decision, an accident of two independently-added constraints stacking. This is the single most visually consequential, cheaply fixable finding in this whole audit.
- **Design tokens**: **none exist.** `frontend/src/styles/globals.css` imports bare Tailwind with zero `@theme` customization — `body { @apply bg-neutral-50 text-neutral-900 antialiased; }` is the entire visual foundation. No dark mode, no semantic color tokens, no typography scale beyond Tailwind's own defaults used ad hoc per component.
- **Status/tone system** (a genuine, real strength, confirmed via `frontend/src/lib/inflationLabels.ts`): a 5-value `Tone` type (`cool`/`neutral`/`warm`/`caution`/`unavailable`) already exists, already domain-neutral (never "success/danger"), already shared between Inflation and Labor (`laborLabels.ts` reuses the identical `Badge` component and tone palette) — the *naming* discipline is already correct; only the *palette itself* (current: `sky`/`orange`/`amber`/`neutral` Tailwind defaults) is visually thin and has no dark-mode counterpart.
- **Components**: `Badge`, `LoadingSkeleton`, `ErrorMessage`, `ExplanationTrigger`/`Disclosure` (native `<details>`-based, reused everywhere — confirmed, still the product's strongest existing pattern, per #21 §12, reconfirmed unchanged), `PageContainer`. No card/panel primitive exists as a named, reusable component — each page's own JSX hand-rolls its own `<div>` structure with ad hoc border/padding classes.
- **Charts/sparklines**: confirmed, zero — no charting library, no SVG sparkline anywhere in the codebase.
- **Theming**: confirmed, zero — no `data-theme`, no `prefers-color-scheme` handling, no theme toggle.
- **API client / loading-error pattern**: `useApiResource` (per-resource `loading`/`success`/`error` states), confirmed independently fetched per Overview section (no aggregate endpoint, #19A's own deliberate decision, unchanged) — this failure-isolation property is real and already correctly built; the *visual* presentation of loading/error states (§44/§45) is what needs work, not the underlying data-fetching architecture.

---

## §3. Live inspection (screenshots taken this increment, real running application)

Overview, Inflation, and Labor were loaded live against the running dev servers (backend `:8000`, frontend `:5173`) and screenshotted at a real 1533×802 desktop viewport. Confirmed, directly, not inferred: single-column, left-aligned content occupying roughly one-third of the available width (§2's own finding); one accent color per page (amber for "Mixed"); numeric evidence (3M/6M/12M on Inflation) rendered as plain inline text with no card treatment, while Labor's equivalent numbers (Current/Prior 3M Avg) **do** use a boxed metric-card treatment — an inconsistency between the two domains' own pages, not a deliberate difference; Labor's live insufficient-data state (§36-45) reads, at a glance, as "broken" (a page of gray pills and em-dashes) despite being architecturally honest.

---

## §4. Persona audit

### A. First-time visitor, little macro knowledge

**First 10 seconds**: sees "Economic Overview," "Know what changed in the economy — and prove why," a broken-looking "Recent activity could not be loaded" card, then two large state badges ("Mixed," "Insufficient data"). **Understands**: something is being tracked; unclear what "Mixed" or "Insufficient data" mean economically. **First 60 seconds**: can click "Why Mixed?" and get a real, plain-language explanation (the product's existing strength) — but nothing on the page *volunteers* this without a click, and the very first thing they see is an error. **Confusing**: "Recent Economic Activity" failing immediately undermines trust before any real content is read; "Insufficient data" with no visible reason nearby reads as a bug, not an honest state. **Feels credible**: the "Why {State}?" disclosures, once opened, are genuinely well-written. **Feels unfinished**: the overall visual density — plain text on white, no imagery, no charts, an error on load. **What makes EI different**: not communicated anywhere on this path — nothing says "deterministic," "reproducible," or "not AI" out loud. **Knows what to do next?** Marginally — "Open Inflation →" exists, but no page orients a total newcomer before dropping them into a monitor page.

### B. Independent macro investor

**First 10 seconds**: recognizes "Core PCE," "target gap," momentum figures as real, substantive content — this persona is served reasonably well by the *content*, immediately. **First 60 seconds**: can verify the 3M/6M/12M figures, see the confirmation panel, and trust the reproducibility framing once found. **Confusing**: no historical/percentile context ("is 3.05% high?"), no chart to eyeball a trend, no way to compare against a benchmark. **Feels credible**: methodology IDs, evidence tables, revision-aware "latest revised data" framing — all real, all present, all currently buried behind disclosures rather than asserted. **Feels unfinished**: the visual thinness undercuts the substance — this persona would expect a research platform to *look* like it takes data seriously (typography, precision, a chart) as much as *say* it does. **What makes EI different**: partially legible to this persona specifically (they'd recognize "deterministic" and "evidence" as real differentiators if they read the fine print) but not asserted anywhere prominent.

### C. Analyst/economist

**First 10 seconds**: immediately checks methodology rigor — finds it (Core PCE as primary, Core CPI confirmation, frozen neutral bands) and would likely respect the discipline. **Confusing**: nothing structurally; this persona reads fine print by default. **Feels credible**: the confirmation panel, the explicit "latest-revised reconstruction" framing, the evaluation-period discipline are all genuinely sophisticated and correctly communicated *in prose* — this persona is the best-served of the four, content-wise. **Feels unfinished**: same visual-thinness concern as persona B, compounded by genuine annoyance at a page that could show a 36-month Core PCE momentum chart in five seconds instead of requiring three clicks to reconstruct the same picture mentally from text.

### D. Technical hiring manager

**First 10 seconds**: sees a broken card on load — a real, immediate, negative signal for "is this finished/production-quality." **First 60 seconds**: if they click through past the broken card, they'd find real depth (revision tracking, evidence tables, a genuine multi-page app) — but the visual polish does not yet communicate "this person can ship a finished product," which is a distinct skill from "this person can build a correct backend." **What's credible**: the sheer number of correctly-labeled, correctly-reasoned disclosures. **What's unfinished**: everything visual — flat typography, no dark mode, no charts, inconsistent card treatment between pages, an error on the very first load. **Portfolio risk, stated plainly**: today, a hiring manager who spends 60 seconds clicking around would likely conclude "strong engineer, weak product sense" — exactly the gap this whole increment exists to close, and exactly why a broken first-page card is the single worst possible first impression for this specific persona.

---

## §5. Home page — verdict

**Yes, build a real Home, separate from Overview.** Overview is correctly an intelligence workspace (§23) — forcing it to also do first-time orientation and marketing is why persona A above struggles: the very first thing they see today is Overview's own operational content (and, currently, an error), not an explanation of what they're looking at or why it should be trusted. `/` becomes Home; Overview moves to `/overview`, reachable via the primary CTA (§10) and the nav (§11).

---

## §6. Home hero

**Refined, not replaced.** The existing line is strong and evidence-backed (#21 §28 already validated it as "reasonably specific... not vague") — keep it verbatim as the headline, paired with one supporting sentence that states the mechanism, not just the outcome:

> **Know what changed in the economy — and prove why.**
> Economic Intelligence continuously monitors trusted economic data, detects meaningful changes, and turns them into reproducible analysis you can trace back to the evidence.

No unsupported claim is added — "continuously monitors" is true (release-driven pipeline, though not yet *scheduled* in production, §26F/#26E — see §9's own honesty requirement below), "reproducible" and "trace back to the evidence" are both directly, currently demonstrable.

**Primary CTA**: "View Economic Overview →" (§10). **Secondary CTA**: "See how it works ↓" (an in-page anchor to §7, not a second page) — cheaper, keeps a first-time visitor on Home long enough to actually absorb the trust framing before jumping into a live monitor.

---

## §7. How It Works

Frozen visual sequence, verified against the actual system (not aspirational):

```
TRUSTED DATA  →  DETERMINISTIC ANALYSIS  →  ECONOMIC STATE  →  CHANGE DETECTION  →  EVIDENCE
(FRED, curated     (versioned,               (Mixed, Cooling,    (structural vs.      (every number
 release schedule)  reproducible               Strengthening…)    routine, never        traceable to
                     methodology)                                  sensationalized)      its source)
```

Each of the five steps gets one plain-language sentence, not a paragraph — this is an orientation diagram, not a methodology document (methodology stays behind its own disclosure, unchanged discipline).

---

## §8. Three core questions — frozen framing

**Yes**, explicitly teach this mapping on Home, using the product's own already-established, already-correct terms (never inventing new vocabulary the app itself doesn't use):

| Question | Answered by |
|---|---|
| What is happening? | Maintained economic states (Inflation, Labor) |
| What changed? | Deterministic, salience-tiered change detection |
| Why? | Methodology + evidence, always inspectable |

This mirrors #21's own three-core-job framing exactly (§3-5 there), now given an explicit home on the marketing surface rather than living only in internal product docs.

---

## §9. Trust section — frozen content, honesty-checked

Six claims, each independently, currently true — verified against real capability, not aspiration:

1. **Facts are sourced** — every figure traces to a named FRED series.
2. **Calculations are deterministic** — versioned methodology (`inflation_v1.0`/`labor_v1.0`), same input always produces the same output.
3. **Canonical conclusions are reproducible** — no randomness, no model weights, ever, in the canonical path.
4. **Evidence is inspectable** — every state has a "Why?" disclosure down to per-observation evidence.
5. **Latest-revised data is labeled as such** — the product never hides that it reflects today's revised data, not a historical vintage.
6. **AI cannot silently become canonical truth** — read-only, tool-calling, evidence-grounded when present at all; never a determinant of a canonical state.

**One claim explicitly NOT made, per this document's own honesty discipline**: nothing on Home claims the product is "continuously," "automatically," or "always" checking right now — per #26E/ADR-029's own already-frozen, still-true verdict (**IMPLEMENTATION READY, NOT ACTIVATED**), that claim remains untrue until real scheduled automation is proven (§26F). Home's own hero (§6) uses "continuously monitors" to describe the *system's design intent and demonstrated capability*, which is accurate; the trust section itself must not overclaim current operational cadence.

---

## §10. Home → product transition

**Primary CTA: "View Economic Overview →"**, frozen — the most direct, honest path into the actual product. **Secondary CTA: "Explore Inflation →"** (not "See How It Works," which is already satisfied in-page, §6) — gives a persona who already knows what they want (B/C above) a one-click path past the orientation content entirely.

---

## §11. Navigation — V1 frozen

**Home · Overview · Inflation · Labor · Releases.** `Explore`/`Compare`/`Research`/`Saved`/`Rates`/`Markets` are explicitly **not** added, even as placeholders — per this document's own explicit instruction, and consistent with #23A's own already-frozen finding that a premature nav slot commits to an IA decision ahead of the content that should justify it (`relate-compare-audit-v1.md` §29, reused verbatim here for the identical reasoning).

---

## §12. Application shell — new contract

- **Header**: unchanged structural role (wordmark left, nav right), refined visually (§13-18) — gains a theme control (§17).
- **Width**: **the double-constraint (§2) is resolved: the shell's own `max-w-5xl` becomes the single, only width authority; per-page `max-w-3xl` wrappers are removed** where they currently duplicate it, **except** where a genuinely narrow reading column is a deliberate choice for long-form prose (Home's own explanatory sections may reasonably stay narrower than data-page content, which should use the full shell width for card grids/metric rows). This is a content-width decision made per page-*section*, not a single global constraint applied blindly everywhere.
- **Vertical density**: reduced section-to-section whitespace on data pages (§19) — Home may remain more generously spaced, since it is read once, not scanned repeatedly.
- **Navigation active state**: keep the existing solid-pill treatment (already accessible, already clear) — refine only its color to the new token system (§14).
- **Logo/wordmark**: text-only "Economic Intelligence" is sufficient for V1 — no icon/logomark is invented without a real design reason to justify one.
- **Theme control**: a compact light/dark/system control in the header, right-aligned near the nav (§17).
- **Responsive navigation**: collapses to a condensed/hamburger treatment below the mobile breakpoint (§47) — not designed pixel-by-pixel here, frozen as a requirement for #27D.

---

## §13. Visual direction

**"Professional economic research + modern SaaS product," frozen, restated as concrete direction:** strong, confident typography carrying most of the hierarchy (not color or decoration); subtle, low-contrast surfaces (a card is a *very slightly* different background + a hairline border, never a heavy shadow); restrained, semantic accent color used sparingly (a state badge, a focus ring, a link) rather than washing the page; generous but *intentional* whitespace (not the accidental double-constraint of §2); numbers treated as first-class typographic objects (tabular figures, consistent alignment, §18); no gradients, no glassmorphism, no glow, no card-hover-lift theatrics, no rounded-everything softness that reads as consumer-app rather than research-tool. The existing disclosure pattern (`<details>`-based, text-first) is a genuine asset and is preserved, refined only in its visual chrome (§21).

---

## §14. Design tokens — semantic system, frozen for future implementation

```
--color-background          page canvas
--color-surface              a card/panel's own background
--color-surface-elevated     a card that sits "above" others (e.g. a modal, a tooltip)
--color-border               default hairline border
--color-border-strong        emphasis border (e.g. an active/focused card)
--color-text-primary         headings, primary values
--color-text-secondary       body copy
--color-text-muted           metadata, timestamps, labels
--color-accent               the ONE brand accent, used sparingly (links, focus, primary CTA)
--color-focus                keyboard-focus ring (may equal accent, kept distinct for clarity)
--color-positive             one pole of a domain-neutral state spectrum (never "good/bad")
--color-negative             the other pole
--color-warning              caution-tier states
--color-neutral              stable/steady states
--color-insufficient         insufficient-data states (already the product's own existing "unavailable" tone)
--color-interactive           hover/active affordance on clickable elements
```

**Never hardcode a page-specific color as the architecture** — every component consumes tokens, never a raw Tailwind color utility for anything semantic (raw utilities remain fine for pure layout — spacing, flex, grid). This directly fixes the current state (§2: Inflation's `TONE_CLASSES` hardcodes `sky`/`orange`/`amber` inline) by promoting the *existing, already-correct tone taxonomy* into the token layer rather than discarding it.

---

## §15. Light mode

**A professional off-white canvas (`--color-background`, close to the existing `neutral-50`, refined), not stark pure white** — cards (`--color-surface`) sit very slightly lighter/whiter than the canvas, creating real but subtle hierarchy without a shadow doing the work. Borders stay hairline and low-contrast (`--color-border`) except where a card genuinely needs emphasis (`--color-border-strong`).

---

## §16. Dark mode — required, designed simultaneously

**Not an inversion.** Background hierarchy: canvas darkest, surfaces a controlled step lighter (never pure black, never a single flat dark gray for everything) — real depth comes from *luminance steps*, not saturation. Text hierarchy: primary text near-white but not pure white (softer on the eyes at long reading sessions, appropriate for a research tool); secondary/muted follow the same relative-contrast ratios as light mode, not identical hex values inverted. Borders: lower-contrast than light mode by default (dark UIs need less border weight to read as separated, since surface-luminance differences already do more work). Semantic states: the same five-tone taxonomy (§14), each tone's own dark-mode value chosen independently for correct contrast — never a blind CSS `invert()`. Chart/evidence surfaces (§41): must remain legible and print-appropriately neutral in dark mode — data visualization typically wants slightly desaturated colors in dark mode to avoid vibrating against a dark background.

---

## §17. Theme control

**Light / Dark / System**, a three-way control in the header (§12). **Persistence**: `localStorage`, mirroring the exact, already-established, already-tested pattern this frontend uses for Since Last Visit's own checkpoint (`lib/sinceLastVisitCheckpoint.ts`, #25H) — the same "treat storage as untrusted, degrade to a safe default on any failure" discipline applies here too (default: `system`). **Flash-of-wrong-theme avoidance**: the theme must be read and applied to the root element **before** first paint — a small inline script in `index.html` (not a React effect, which would run after the first paint and cause a visible flash) reads the persisted preference (or `prefers-color-scheme` if unset) and sets a `data-theme` attribute synchronously. **Accessibility**: the control itself must be a real, labeled, keyboard-operable control (not a bare icon with no accessible name); `prefers-reduced-motion` (§43) is honored independently of theme choice; contrast ratios (§48) are verified for *both* themes independently, not assumed to transfer.

---

## §18. Typography

| Role | Treatment |
|---|---|
| Product name | Semibold, tight tracking, text-only wordmark |
| Page title | Large, bold — the single strongest text object below the hero |
| Page description | Regular weight, secondary color, one line |
| Section title | Small-caps-adjacent or uppercase-tracked label (already the current pattern, e.g. "Current State") — kept, refined |
| Metric label | Uppercase, small, muted — already the current Labor-page pattern (§3), extended to Inflation |
| Metric value | Large, bold, **tabular numerals** (`font-variant-numeric: tabular-nums`) — new; numbers must align in a column and scan instantly, a real, currently-missing requirement given how many multi-column metric rows this product already has (3M/6M/12M, Current/Prior/Delta) |
| Status (badge) | Existing text-first pill pattern, kept — genuinely already correct (§13) |
| Body | Regular, comfortable line-height, secondary color |
| Metadata | Small, muted (timestamps, periods, methodology IDs) |
| Evidence | Slightly condensed/monospace-adjacent for tabular evidence rows — reinforces "this is raw, inspectable data," not narrative prose |
| Methodology | Same as body, always behind a disclosure |

**No exotic font.** The system font stack already in use (implied by Tailwind defaults) is sufficient — a "professional research" feel comes from spacing/hierarchy/restraint, not a bespoke typeface; introducing one would add a real performance/licensing cost for no evidenced benefit, per this document's own "do not add without strong justification" instruction.

---

## §19. Information density — frozen principles

**More structured and more visual; not meaningfully more compact, and never Bloomberg-terminal dense.** The current problem (§2/§3) is not "too much whitespace" in the abstract — it is whitespace that is *accidental* (the double-width-constraint) rather than *intentional* (deliberate breathing room around genuinely important numbers). Fixing §12's own width contract, adding real metric-card structure (§33) and charts (§41) where they replace paragraphs of numbers with one glanceable object, and tightening only the *vertical* rhythm between sections (not cramming content horizontally) — these together make the product feel more substantial without adding raw information volume per screen.

---

## §20. Status system

**The existing five-tone taxonomy (`cool`/`neutral`/`warm`/`caution`/`unavailable`) is preserved as the correct semantic model** — confirmed, this is already domain-neutral and already avoids the "green=good/red=bad" trap (#21 never flagged it as a problem, and fresh inspection this increment confirms why: nothing in the current naming implies value judgment). **What changes**: the *palette* backing each tone is promoted into the token system (§14) with real light/dark values (currently: raw Tailwind `sky`/`orange`/`amber`/`neutral`, no dark-mode counterpart at all), and status is **never communicated by color alone** anywhere (already true today via the text-first `Badge` — reconfirmed, preserved, extended to any new status-bearing element §27D introduces).

---

## §21. Beginner explanations — progressive education

**Preserve the opt-in disclosure pattern as the primary mechanism (it already works, #21 §12's own "strongest dimension" finding, reconfirmed)** — do not turn every page into a textbook. Add exactly one new, small affordance: a compact "What does this mean?" micro-explainer *inline*, next to the specific jargon term itself (Core PCE, annualized, 3M/6M/12M, target gap, confirmation, payroll momentum, latest revised, canonical, basis points, state duration) — reusing the exact same `ExplanationTrigger` component already built (#21/#22B), just applied at the term level rather than only at the section level. **No glossary page is built in V1** — named explicitly as a LATER candidate (§59), since the inline, contextual version already solves the actual comprehension problem without a second, separately-maintained content surface.

---

## §22. Expert depth — preserved absolutely

**Never replace precise information with vague prose — restated as a hard constraint on every redesign decision in this document.** Every exact metric, period, methodology ID, evidence table, and revision disclosure currently reachable stays reachable, at the same or fewer clicks. The redesign's entire job is presentation, hierarchy, and visual credibility — never simplifying away a number an economist would need.

---

## §23. Overview — proposed hierarchy

Current order (confirmed live, §3): Recent Economic Activity → Current State → How They Relate → What Changed → Recent Data Updates → Releases. **Proposed order, refined, not reordered wholesale** (the existing sequencing logic — RETURN content first, per #25F/#25H's own already-frozen "deliberately first" placement — remains correct):

1. **Since Last Visit / Recent Economic Activity** (unchanged position — but see §28 for its own presentation fix)
2. **Current State** — redesigned as a real side-by-side card pair (§29), the answer to "what is happening"
3. **How They Relate** — kept immediately adjacent to Current State (already true), visually tightened so the composed sentence reads as a natural extension of the two cards above it, not a separate section (§30)
4. **What Changed** — the answer to "what deserves attention" (§31)
5. **Recent Data Updates** — renamed and clarified (§32, restating #21 §11's own never-actioned recommendation)
6. **Releases** — "what's next," kept last (already correct)

**Above the fold, on a real desktop viewport**: Current State + How They Relate should be visible without scrolling once the shell's own width fix (§12) reclaims the wasted horizontal space — today's narrow column pushes this content down unnecessarily.

---

## §24. Recent Economic Activity failure — diagnosed, not cosmetically hidden

**Traced fresh, this increment, live**: `GET /api/v1/since-last-visit` returns `500`. `alembic current` against the dev database reports `09f4c0959e9f`; the application's own expected head is `f5420059a092`; `GET /readiness` confirms `{"ready":false,"reason":"schema_mismatch",...}`. **This is the exact same, already-known, already-diagnosed (#26A) stale-development-database issue — not a new problem, and not a UI problem.** The dev database was deliberately left unrepaired across #26A through #26F, per every one of those increments' own explicit instructions; #27A's own instructions carry the identical constraint (do not migrate/repair). **The UI's own current behavior here is architecturally correct** (`useApiResource`'s per-section failure isolation, confirmed live: every other Overview section renders normally around this one failed card) — the *visual presentation* of that failure (§45) is what this document's own redesign addresses, not the root cause, which remains a deployment/operations fact outside this increment's scope.

---

## §25. Current State — redesign direction

**Cards, refined — not rows, not a new structure.** The current implementation is already two peer cards (Inflation, Labor); the redesign strengthens the *visual* comparison (consistent card height/structure regardless of state length, a shared metric-card chrome per §33, the state badge given more typographic weight per §18) without deriving any new economic conclusion in the frontend — the peer-card architecture's own deliberate anti-aggregation discipline (no combined "Economy Score," `labor-ui-v1.md`'s own already-frozen prohibition, unchanged) is preserved exactly.

---

## §26. How They Relate

**Keep the exact composed sentence, unchanged in wording/logic (backend-owned, #23B/#23C's own frozen contract) — improve only its visual integration.** Currently a plain paragraph below the two Current State cards; redesign direction: visually anchor it as a connective element *between* the two cards (a short rule or a distinct-but-quiet band directly under/between them) rather than a fully separate section with its own heading weight — reinforcing, visually, that this is a *composition* of the two facts above it, never a third, independent conclusion. This stays strictly within the already-frozen composition-vs-inference boundary (`relate-compare-audit-v1.md` §15) — no new visual element is added that could be read as implying correlation or causation the backend does not establish (no connecting arrow implying causality, no shared trend line, no combined score).

---

## §27. What Changed

**Preserve the canonical salience hierarchy exactly (backend-owned, #22B's own frozen tiering) — redesign only the visual weight given to each tier.** A `STATE_CHANGED`/`AVAILABILITY_*` event should be unmistakably the most visually prominent item on the page when present (larger, a stronger accent, positioned first — already true structurally, strengthened visually via the new token system) while a routine metric-only update stays visually quiet (small, muted, already correctly de-emphasized) — "visually obvious without sensationalizing" is achieved through *hierarchy* (size, weight, position) rather than alarm-colored treatment (no red flashing, no exclamation iconography) which would misrepresent a classification event as an emergency.

---

## §28. Recent Data Updates

**Rename, per #21 §11's own already-frozen-but-never-implemented recommendation, now actually specified**: "Recent Data Updates" (already renamed from "Latest Data Detected" per #22B) is a real improvement but still under-communicates the pipeline-stage-vs-fact distinction. **Redesign direction**: keep the existing, correct DATA-vs-INTELLIGENCE structural split (ADR-023, unchanged), but make the three-way distinction the source prompt names — *a release happened/is scheduled* vs. *EI processed it* vs. *the economic conclusion changed* — visually sequential rather than requiring the user to infer it from prose alone (e.g., a small, three-step inline indicator mirroring §7's own How It Works sequence, reused at a smaller scale). "Not yet checked by Economic Intelligence" is kept as copy (it is honest and correct) but gains a one-click "why" affordance for a first-time reader who doesn't already know this distinction exists.

---

## §29. Releases

Calendar treatment, upcoming/past split, domain tags, and schedule-vs-publication disclosure are all already correct and well-received in prior audits (#21 §10, unchanged) — redesign direction is purely visual (consistent card/row chrome matching the new system, §33) plus **closing the remaining dead-end** #26A's own live inspection found: release rows on `/releases` itself and Overview's own "Recently" row still render no link (`ReleaseRow`'s `showMonitorCta` is opted into only by `UpcomingReleasesPreview`, confirmed unchanged this increment) — extend the same, already-existing CTA pattern to both remaining locations. No new release precision is fabricated anywhere.

---

## §30. Inflation — hierarchy audit, verified against implementation

**Confirmed, live, this increment**: the hypothesis holds — a long, single-column, document-like layout with real content but insufficient visual separation between "the headline conclusion," "the evidence for it," and "the deeper context" (target, confirmation, headline). **Proposed hierarchy**: (1) a strengthened hero (§31) as the unmissable top-level summary; (2) a metric-card row (§33) for 3M/6M/12M momentum, replacing the current plain-text row; (3) What Changed (§32); (4) Target and Confirmation as a **side-by-side pair** once real width is reclaimed (§12) rather than stacked sections, since they are conceptually parallel ("where does this sit against the Fed's own objective" / "does a second measure agree"); (5) Headline context and evidence/methodology remain last, correctly de-prioritized (unchanged).

---

## §31. Inflation hero

Proposed structure, using only fields the backend already returns (verified against `app/models/inflation.py`'s own existing response shape — nothing new is invented):

```
INFLATION
Mixed                                    [state duration line, already exists]

Core PCE is showing mixed signals across its own short- and long-term trends.
[plain-language sentence — see note below]

CORE PCE MOMENTUM
  3M            6M            12M
  3.05%         3.46%         3.34%
```

**The plain-language sentence is the one new element requiring a decision, and it is decided conservatively**: it must be assembled from the *existing*, already-frozen explanation content (`content/explanations/inflation.ts`'s own `INFLATION_STATE_EXPLANATIONS`, confirmed already containing real per-state prose) rendered inline rather than behind a click — **never newly generated or interpreted by frontend logic**, per this document's own explicit constraint. If the existing explanation copy is not already written in a form suitable for a one-line inline summary (it is currently written for the "Why Mixed?" disclosure's own longer-form context), #27C's own implementation must reuse it verbatim or trim only mechanically (e.g., first sentence) — never paraphrase or infer new meaning.

---

## §32. What Changed — Inflation

Preserve every exact value, period, and event-type distinction (unchanged, backend-owned). Redesign direction: each subsection (Core PCE, Confirmation, Target, Headline PCE, Headline CPI) becomes a visually distinct card/row rather than a continuously-scrolling list with only a colored left border differentiating them (confirmed, current implementation, §3's own screenshot) — the existing period-pair header (`June 2026 → July 2026`) and delta formatting are correct and kept; only the container chrome changes.

---

## §33. Metric cards — a real, reusable system

**Frozen fields, one component, reused across both domains** (fixing the current Inflation/Labor inconsistency found live, §3):

```
label        (e.g. "3M ANNUALIZED")
value        (e.g. "3.05%")
unit         (already implicit in value formatting today — kept)
period       (e.g. "July 2026")
delta        (optional — only where a comparison exists)
status       (optional — a tone-colored accent, never the dominant visual element)
evidence action  (the existing "View evidence" link/disclosure trigger, unchanged)
context      (optional secondary line — e.g. neutral band, unchanged content)
```

This is a **presentation** contract only — every field already exists in some form in the current markup; the redesign's job is giving them one consistent component instead of two independently-evolved, visually inconsistent implementations (Inflation's plain-text row vs. Labor's boxed cards, §3).

---

## §34. Target section

Improve hierarchy (Headline PCE, Fed objective, gap) via the new metric-card system (§33) — three cards in a row rather than the current plain two-line list. **Do not** introduce any visual treatment implying the 2% objective is a pass/fail threshold (no green-at-target/red-off-target coloring) — the gap is presented as a fact (a number, "+1.70pp"), consistent with the existing, correct discipline (#21 §34 of the source prompt's own explicit warning, honored).

---

## §35. Confirmation

Make the three-part structure (primary measure, confirmation measure, confirmation result) legible to a beginner via one small addition: a plain-language one-line summary above the existing panel ("Core CPI and Core PCE currently disagree" / "...currently agree" / "...comparison is inconclusive" — reusing the exact, already-existing `ConfirmationRelationship` values `CONFIRMS`/`DIVERGES`/`INCONCLUSIVE`/`UNAVAILABLE` verbatim as the source of the sentence, never inferring a stronger relationship than the methodology itself establishes, per `relate-compare-audit-v1.md` §12's own already-frozen "same-concept confirmation" boundary).

---

## §36-39. Labor — diagnosis before design (the mandatory root-cause trace)

**Traced precisely, this increment, read-only, through every layer named in the source prompt:**

**Frontend** → correctly renders whatever the API returns; confirmed, no frontend logic fabricates or suppresses data.

**API response** → `GET /api/v1/monitors/labor` correctly returns `state: "INSUFFICIENT_DATA"` for every component, because the underlying domain computation genuinely, correctly returns that.

**Monitor service / classification logic** → `combine_labor_state`/`classify_employment_state`/`classify_unemployment_trend` are unmodified since their own extensive test-writing across #20A-#20E.2 (1,600+ backend tests passing, zero economic-domain files touched by any increment #21 through #26F) — no reason to suspect a logic regression, and this increment's own job is data diagnosis, not a methodology re-audit.

**Evaluation period / required observations** — verified directly against `research/labor_momentum/LABOR_V1_FROZEN_METHODOLOGY.md`: `EmploymentState` requires **exactly 7 consecutive PAYEMS calendar months** (`t` through `t-6`); `UnemploymentTrendState` requires **exactly 6 specific, non-contiguous UNRATE calendar months** (`{t, t-1, t-2, t-12, t-13, t-14}` — a 15-month span). Either sub-state missing its own required set is `INSUFFICIENT_DATA` by design (§7 of the methodology, "no partial/best-effort fallback").

**Repository observations — inspected directly, read-only, against the real dev database, no secret value touched:**

```
series_id | obs_count |  earliest  |   latest
----------+-----------+------------+-----------
CPIAUCSL  |        36 | 2023-09-01 | 2026-08-01
CPILFESL  |        36 | 2023-09-01 | 2026-08-01
PCEPI     |        36 | 2023-08-01 | 2026-07-01
PCEPILFE  |        36 | 2023-08-01 | 2026-07-01
UNRATE    |        10 | 2025-11-01 | 2026-08-01
PAYEMS    |    (does not exist as a persisted series row at all)
```

**PAYEMS**: zero observations — the series has never been synced into this database. Not a partial-history problem; a complete absence. **UNRATE**: 10 months of history (2025-11 → 2026-08) — nowhere near the ~15-month span the methodology's own trailing-year comparison (`t-12/t-13/t-14`) requires; those three months fall entirely before UNRATE's own earliest persisted observation. **Confirmed correctly mapped** (read-only inspection of `release_series_mappings`): both `PAYEMS` and `UNRATE` are `active=true`, correctly attached to the Employment Situation release — the *configuration* is correct; only the *data* is missing/shallow.

**Contrast, confirming this is Labor-specific, not systemic**: every Inflation series has 36 months of real history — comfortably enough for Core PCE's own 13-month-deep momentum requirement. Labor was never given the equivalent treatment in this specific database.

---

## §38. Labor verdict

**B — BOOTSTRAP/SYNC PROBLEM.**

Evidence, restated compactly: (1) PAYEMS has zero persisted observations — never synced at all, despite being correctly, actively mapped to a real release. (2) UNRATE has real but shallow history (10 months), insufficient for the methodology's own frozen 15-month trailing-year requirement. (3) The release→series mapping configuration is correct. (4) The classification logic is unmodified, extensively tested, and has no evidence of defect. (5) Inflation's own four series, by contrast, are fully populated (36 months each) in the identical database, confirming this is not a systemic sync failure but a Labor-specific gap in how this particular development database happened to be seeded over the course of this session's own history.

**Not A** (the persisted data genuinely is insufficient, but not because of any correctly-functioning check against a fully-bootstrapped environment — it is insufficient because bootstrap itself was never completed for this domain). **Not C or D** — no backend or frontend defect was found; both layers behave exactly as designed given the actual data on hand.

---

## §39. Labor remediation — defined, not implemented

**Exact later fix (data/bootstrap, per verdict B), directly reusing already-existing, already-tested commands — no new code required:**

1. `POST /api/v1/series/PAYEMS/sync` — brings PAYEMS into existence with real observation history (bounded window, existing endpoint, `app/api/series.py:108`, unchanged).
2. Confirm the sync's own returned observation range covers at minimum the required 7 consecutive months for whatever evaluation period is targeted; if the sync's own default window is shallower than needed, a second sync call or a real release-processing pass (`process_release`) extends coverage (release processing itself fetches over a bounded five-year window, per `automated-economic-maintenance-v1.md` §2 step 3 — already deeper than a plain sync).
3. For UNRATE, the existing 10 months of history must be extended backward to cover the `t-14` boundary — the same sync/processing mechanism, run again with attention to whether the default window reaches far enough back; if not, this may require a deliberate, wider manual pull (still using the existing `/sync` endpoint's own existing capability, not new code).
4. Re-verify via a live `GET /api/v1/monitors/labor` call showing a real, non-`INSUFFICIENT_DATA` state.

This is exactly the same class of action already named, precisely, as **#26F/#26H's own bootstrap scope** (`render-production-architecture-v1.md` §55) — this increment's own diagnosis directly informs and is consistent with that already-frozen plan, applied here to the *local development* database rather than a future production one. **Not performed this increment**, per explicit instruction.

---

## §40. Labor redesign — both states

**Sufficient-data state**, direction: overall Labor state as the hero (mirroring Inflation's own new hero, §31); Employment condition + momentum and Unemployment trend as a clearly paired, side-by-side pair of metric-card groups (using §33's own system, already closer to this shape than Inflation's page is, §3); an explicit, visually distinct one-line "how these combine" sentence directly reusing `combine_labor_state`'s own already-correct semantics (mirrors §26's own composition discipline — MIXED already means "these disagree," stated plainly, never inferring beyond it); What Changed and evidence/methodology follow the identical structural pattern established for Inflation, for cross-domain consistency.

**Insufficient-data state, designed explicitly (not merely tolerated)**: the current live rendering (§3, screenshot) — a page of gray pills and em-dashes — is honest but reads as broken to an unfamiliar visitor. Redesign direction: **when a domain is genuinely `INSUFFICIENT_DATA`, replace the metric-card grid's own empty `—` placeholders with one clear, calm explanatory panel** stating plainly what's missing in plain language ("Economic Intelligence has not yet gathered enough payroll and unemployment history to classify Labor's current state" — a real sentence, not a fabricated one, built from the already-existing `missing_required_metrics`-style backend field if one exists for Labor as it does for Inflation, confirmed present, `InflationHero.tsx:79-80`; verify the Labor equivalent during #27C's own implementation) rather than six separate boxes each independently rendering `—`. This turns "No change is valid intelligence, not an error" (§46) into a real, designed visual fact for insufficient-data specifically, not merely a copy choice.

---

## §41. Charts — evaluated per candidate, none built this increment

| Chart | Question answered | Data required | Current backend support | New API needed? |
|---|---|---|---|---|
| Core PCE momentum history (3M/6M/12M over time) | "Is this trend accelerating or decelerating?" | A time series of already-computed momentum values | **No** — momentum is computed live, on demand, never persisted as a series (confirmed, State Duration's own recompute-only architecture, `state-duration-v1.md`, unchanged) | **Yes** — a new, deterministic read model would be required (e.g. a bounded-range recompute-and-return endpoint, or built atop #25E's own `RecordedMonitorResult` history once productized per #26A's own already-identified LATER candidate) |
| Headline inflation vs. target (a horizontal line) | "How far above/below 2% are we, visually?" | Two already-available current values (Headline PCE, 2% objective) | **Yes** — both values already returned by the existing monitor response | **No** — a pure frontend rendering of already-fetched data, genuinely buildable in #27C |
| Payroll momentum (jobs added/lost over time) | "Is hiring accelerating or slowing?" | A time series of `momentum_delta_jobs` values | **No**, same reasoning as Core PCE momentum | **Yes** |
| Unemployment trend | "Is unemployment rising or falling?" | A time series of UNRATE-derived trend values | **No** | **Yes** |
| State timeline (a visual "Mixed for 2 months, previously Heating" strip) | "How has the classification itself evolved?" | Exactly `RecordedMonitorResult`'s own already-persisted history (#25D/#25E) | **Partially** — the data exists and is durable; **no read API exists yet** (`recorded-state-history-v1.md` §100 explicitly deferred this) | **Yes**, but the *asset* already exists — this is the cheapest of the five to eventually build |

**Verdict: exactly one chart (Headline PCE vs. target) is buildable in #27C with zero new backend work; every genuinely trend-shaped chart (the ones a research-tool audience would most want) requires a new, deterministic read model first — named explicitly as a real, valuable, but NOT #27-series-scoped future increment**, consistent with this document's own instruction not to add charts merely for decoration, and not to imply capability the backend does not yet have.

---

## §42. Sparklines

Same constraint discipline as §41, applied to compact Overview/domain-card sparklines: **not built in #27C** for any trend requiring history the backend does not persist and expose. The one exception mirrors §41's own single green-lit case — a static, two-point "current vs. target" micro-visual (not a true sparkline, no interpolation, no frequency-alignment risk) is the only compact visual currently safe to build without new backend work. No frontend-side interpolation, resampling, or synthetic frequency alignment is ever introduced, per this document's own explicit constraint.

---

## §43. Motion — restrained policy

Hover transitions: subtle (150-200ms, opacity/color only, never scale/shadow theatrics). Disclosure expansion: the native `<details>` element's own default behavior is kept (already correct, zero custom animation risk). Theme transition: a brief (150ms) color-property transition on theme switch, disabled entirely under `prefers-reduced-motion` (§48). **No decorative animation** — no page-load stagger, no number counting-up, no card-entrance animation — all of which would actively harm a research tool's own credibility and usability (a number that "counts up" is actively hostile to someone trying to read it quickly).

---

## §44. Loading states

Preserve the existing, correct architecture (per-resource independence, one failed/loading resource never blanking the page, #21's own confirmed strength) — redesign the *visual* skeleton: page-level skeleton (a full-page first load) and card-level skeleton (an individual Overview section still loading while others have resolved) both use the new surface tokens (§14) rather than the current plain gray-box placeholder, matching the eventual real content's own shape more closely (a metric-card skeleton should be shaped like a metric card, not a generic rectangle).

---

## §45. Error states

**Distinguish, visually and in copy, four genuinely different conditions** (currently collapsed into one generic "could not be loaded" treatment, confirmed live, §3/§24): resource unavailable (a transient fetch failure — "Retry" is the correct, already-existing affordance); a schema/deployment problem (the exact §24 case — this is an *operator*-facing fact, and a normal user should see a calm, generic "temporarily unavailable" message, never `SCHEMA_BEHIND`/`schema_mismatch`-shaped internal language); provider/data unavailable (a FRED-side issue, already distinctly handled in the backend's own `PARTIAL_FAILURE`/`FAILED_PROVIDER` vocabulary — surfaced to a user as "some data could not be checked," never a raw error code); insufficient economic data (not an error at all — §46). **Internal implementation detail is never exposed to a normal user** in any of these — the existing backend `detail` strings (already generic and safe, confirmed across every route this whole session) remain the right shape; the redesign's job is the *visual* treatment (an icon/tone that correctly signals "transient, not your fault" vs. "we're working on it" without ever showing a stack trace or a revision hash to a non-operator).

---

## §46. Empty states

**"No change" is designed as its own, calm, positive-toned state — not an error, not blank.** Four cases: no changes (What Changed's own existing "No canonical changes were reported" copy — correct, kept, given a calmer visual treatment than an "error"-adjacent box); no evidence (a plain, expected statement, not alarming); no releases (a simple "nothing scheduled in this window" statement); first visit (Since Last Visit's own already-correct, already-tested "Recent Economic Activity" framing, unchanged); insufficient data (§40's own newly-designed treatment, the most important of the five given Labor's own current live state).

---

## §47. Responsive design

**Desktop-first, fully usable on mobile — not mobile-first, and not desktop-only.** Breakpoints: desktop (the primary research experience — multi-column metric rows, side-by-side card pairs per §30/§40); tablet (single-column card stacks, metric rows may wrap to 2-across rather than 3-4); mobile (fully single-column, nav collapses per §12, metric cards stack vertically, tables/evidence rows gain horizontal scroll containers where genuinely wide — already a known, named, previously-deferred risk area, `product-experience-audit-v1.md` §26's own "minor, easily-verified-later" finding on Labor's evidence table, now formally inherited into this contract rather than left informally noted).

---

## §48. Accessibility — contract requirements

WCAG-conscious contrast (AA minimum, both themes independently verified, §16/§17); full keyboard navigation (nav, theme control, every disclosure trigger, every CTA — already largely true via native `<details>`/semantic `<a>`/`<button>` usage, reconfirmed as a hard requirement, not merely inherited); visible focus states everywhere (already partially true, `globals.css`'s own `:focus-visible` rule — extended to every new interactive element the redesign introduces, using the new `--color-focus` token); semantic headings (a real `h1`→`h2`→`h3` hierarchy per page, audited during #27C's own implementation, not assumed correct today); screen-reader labels (icon-only controls — the theme toggle, any future icon-based CTA — always carry a real accessible name); status never communicated by color alone (already true via the text-first badge pattern, §20, preserved as a hard constraint on every new status-bearing element); reduced motion honored (§43); theme accessibility (neither theme may be the sole way to achieve sufficient contrast — both are independently AA-compliant, not "light mode is the real one, dark mode is a best-effort clone").

---

## §49. Portfolio impact

**A technical hiring manager should be able to discover, within a few clicks, that this is not a mock dashboard — without every page being cluttered with architecture trivia.** Visible trust cues, already present in the content, given real visual weight rather than buried behind uniform disclosure chrome: methodology version (kept behind disclosure, but the disclosure itself gains a slightly stronger visual invitation — e.g., "Methodology `inflation_v1.0` · Evidence" as a persistent, quiet footer-style line on every monitor page, not only reachable via a generic "Evidence & methodology" link); data provenance (source series IDs, already shown); evidence (already shown, strengthened via §33's own metric-card "evidence action" field); latest-revised disclosure (already shown, kept); release processing / recorded history (not surfaced to ordinary users at all — correctly so, per #25E's own deliberate BACKEND ONLY scoping — but a small, honest technical footer or an "About the engineering" link from Home, distinct from the main product surface, is a reasonable, low-risk way to let a specifically-curious hiring-manager-type visitor find real depth (test counts, ADR references, the deterministic-vs-AI boundary stated explicitly) without imposing it on every ordinary page. **Named as a real, valuable, cheap addition for #27B's own Home page** — not invented as new product surface, merely as one clearly-labeled link.

---

## §50. Markets expansion — deferred, sequencing recorded

**Not implemented.** The audit's own hypothesis (Economy → Rates/Bonds → broad equity markets → crypto → individual equities) is **supported, with one refinement**: Rates/Financial Conditions is the most natural next domain specifically because it shares this product's own existing methodology shape most closely (a rate is a single, clean, already-well-understood time series — closer to Inflation's own shape than a multi-factor equity-market read would be) and because release-calendar infrastructure already, incidentally, tracks GDP-adjacent release categories (confirmed, #26A's own live finding — "Consumer"/"Growth" release tags already exist in the calendar with no monitor consuming them yet) — meaning Growth, not Rates, may actually be the cheaper *next* step from a pure data-readiness standpoint, even though Rates is methodologically simpler. **This document does not resolve that specific ordering question** — it is out of scope for a UI/UX contract — but records both data points honestly for whichever future product-strategy increment does decide it, rather than asserting the prompt's own hypothesis as settled without evidence.

---

## §51. Future-proof design

The design system (§14 tokens, §33 metric cards, §20 status taxonomy) is already domain-neutral by construction — nothing in it assumes exactly two domains. The navigation (§11) deliberately does **not** pre-add empty slots for Rates/Markets — consistent with `relate-compare-audit-v1.md` §29's own "do not commit to an IA decision ahead of the content that should justify it" reasoning, reused here for the identical class of decision.

---

## §52. Redesign priorities

**MUST before deployment:**
- Design tokens + light/dark theme system (§14-17)
- Application shell width fix (§12/§2 — the double-constraint)
- Metric-card system, unified across domains (§33)
- Home page (§5-10)
- Error-state redesign distinguishing the four conditions (§45) — directly protects against the exact first-impression risk §4/§24 both name
- Labor insufficient-data redesign (§40) — currently reads as broken, a real credibility risk independent of the Labor data fix itself
- Loading-state redesign (§44)
- Accessibility contract satisfied for whatever ships (§48)

**SHOULD before deployment:**
- Inflation/Labor hero redesign (§31/§40)
- Current State / How They Relate visual tightening (§25/§26)
- What Changed visual hierarchy strengthening (§27/§32)
- Inline beginner explanations (§21)
- Responsive polish beyond "not broken" (§47)
- The one buildable chart (Headline PCE vs. target, §41)

**LATER:**
- Every trend-shaped chart requiring a new read model (§41)
- Sparklines beyond the single static case (§42)
- Glossary page (§21)
- Growth/Rates domain expansion (§50)
- Recorded-history productization surfacing (already named LATER by #26A, reconfirmed)

---

## §53. Implementation plan

**#27B — Design System + Application Shell + Home + Theme.** Tokens (§14), light/dark (§15/§16), theme control (§17), shell width fix (§12), typography scale (§18), Home page in full (§5-10), navigation (§11).

**#27C — Overview + Inflation + Labor + Releases redesign, and approved Labor remediation if the operator authorizes it.** Metric-card system (§33) built once, applied to both domains; Overview hierarchy (§23-29); Inflation hierarchy/hero/What Changed/Target/Confirmation (§30-35); Labor sufficient- and insufficient-state redesign (§40); Releases dead-end closure (§29); Labor data bootstrap (§39), performed only with explicit operator authorization, since it mutates the development database — not assumed included by default.

**#27D — Responsive + accessibility + loading/error/empty states + final polish.** §44-48 in full, plus the one buildable chart (§41) and inline beginner explanations (§21) if not already folded into #27C.

No collapse or split is warranted by this audit's own findings — the three-part shape matches the natural dependency order (system before pages, pages before final-polish states) exactly.

---

## §54. Artifact

`docs/product/product-ui-ux-v1.md` — this document.

---

## §55. Documentation

**No ENGINEERING_JOURNAL.md entry** — this increment produced no durable engineering *decision* (no code shipped, no architecture changed); its own findings live entirely in this new artifact, which is itself the durable record. **`current-architecture.md` not updated** — per explicit instruction, never presented as though the redesign already exists. **No ADR** — no genuinely durable *architecture* decision was made this increment (the design-token/theme *system* is a product/design decision to be recorded structurally when #27B actually builds it, not before).

---

## §56. Verification

Backend: `TEST_DATABASE_URL=... pytest tests/ -q` → **1,605 passed**, 0 skipped, unchanged (this increment touched no application code). Frontend: `npm test -- --run` → **1,137 passed**, unchanged. `tsc -b --noEmit`, `oxlint`, `vite build` all clean, unchanged. No production behavior was altered by this increment — every finding above was reached by reading, live-inspecting, and querying (read-only) the running application and its databases, never by modifying them.

---

## Appendix: secret safety and version control

No `.env`/`.env.*`/credential file was read, printed, or logged. The Labor data diagnosis (§36-39) inspected the development database exclusively through plain, read-only `SELECT` queries against non-secret columns (series IDs, observation counts, date ranges, mapping activity flags) — no credential, connection string, or row of actual observation *values* beyond what was needed to establish counts/date-ranges was displayed, and the database itself was not modified in any way (confirmed: `alembic current` unchanged, `09f4c0959e9f`, before and after this increment). Nothing in this document was committed or pushed; the working tree outside this new file was not modified.
