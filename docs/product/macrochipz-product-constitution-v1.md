# MacroChipz — Product Constitution V1

**Increment #36.** Specification only. No production code, no behaviour change, no deployment, nothing committed, no secret read.

This is the authoritative product document for MacroChipz 2.0. Subsequent implementation increments should reference it rather than re-litigating what MacroChipz is supposed to become. Where it conflicts with an older product document, **this document wins.** Where it conflicts with an **ADR**, the ADR wins until explicitly superseded by a new ADR — engineering invariants are not overridden by product intent.

Its companion is [`docs/architecture/macrochipz-2.0-architecture.md`](../architecture/macrochipz-2.0-architecture.md), which specifies how the system delivers what this document promises.

**Relationship to Increment #35.** [`macrochipz-audience-content-data-opportunity-research-v1.md`](macrochipz-audience-content-data-opportunity-research-v1.md) is an important research input, not a mandate. This Constitution adopts most of its constraints, **explicitly overrides three of its recommendations**, and records why in §38.3. Research findings that constrain what we may *honestly claim* are treated as binding. Research findings about what we should *want to build* are treated as evidence to weigh.

---

## 1. Product Mission

**Make the U.S. economy legible to people who do not have an economics degree — and prove every word of it.**

Economics is not intrinsically boring or intrinsically hard. It is badly presented. It arrives as either a wall of undifferentiated numbers or a confident opinion with no receipts. MacroChipz exists because there is a third option: show what actually happened, explain it in plain English, and let anyone who wants to check the arithmetic check it.

The economy itself is the product. MacroChipz is the interface.

## 2. Product Thesis

> **MacroChipz makes economics understandable, visual, interesting, explorable, trustworthy and shareable — and it is the only place where you can see not just what the economy says, but how our understanding of it changed.**

Three claims, in descending order of confidence:

1. **A trustworthy, plain-English, evidence-backed view of the U.S. economy is valuable.** Well-supported. Financial literacy is at a decade low; specific, measurable misconceptions are widespread; the fastest-growing information sources are the least trusted to act on.
2. **Provenance is the differentiator, not clarity.** Supported by inference from #35 §17.4: people already consult more sources and still do worse. The failure mode is trust, not comprehension. This is the bet.
3. **Revision intelligence is an unserved category.** Supported by strong negative evidence (zero products, unregistered domains, an unmet demand shock) and **unproven on the demand side**. This is the wager.

We are building all three. We will instrument all three. Claim 3 is the one most likely to be wrong, and the product is designed so that being wrong about it does not invalidate claims 1 and 2.

## 3. Target User / Initial Audience

**Primary: the economically curious adult facing a rate-sensitive decision.**

Concretely: someone deciding whether to buy, refinance, move, take a job, or simply trying to reconcile "the numbers say the economy is fine" with "everything feels expensive." They are not an investor, not a professional, and not a student doing homework.

**The acquisition wedge is narrower than the audience.** The single best-evidenced entry point is the mortgage-rate misconception cluster — 66% of prospective homebuyers believe the Federal Reserve sets mortgage rates outright; 61% believe government dictates lender rates. That is a specific, measured, correctable belief attached to a decision the CFPB prices at over $1,000/year. It is also the cleanest keyword territory available, and two major free explainers in that space stopped publishing within the last 19 months.

**The wedge is a door, not a room.** Someone arrives asking what moves their mortgage rate and finds six economic worlds, a revision history, and a calendar. The product serves the curious adult; the wedge is how they find it.

**Secondary audiences we serve but do not target:** retail investors, journalists and creators (who need a citable, point-in-time-correct evidence page and currently improvise one), and students.

**Explicitly not the initial audience:** professional economists and analysts (18,600 economist jobs exist in the entire U.S., and #28 already rejected that thesis), and day traders.

## 4. User Problem

Four problems, in the order a user encounters them.

1. **Orientation is expensive.** Finding out how the economy is doing means visiting several sites, none of which synthesise, or one site that synthesises without showing its work.
2. **Nothing connects.** The Fed changes rates; mortgage rates move the other way; nobody explains why, and the user concludes economics is arbitrary. Existing products show indicators as a list of unrelated tiles.
3. **The numbers are not what people think they are.** Economic data is revised — sometimes enormously, as with the −911,000 payroll benchmark revision. Almost nobody knows this. Every product silently overwrites the old number and moves on, which means the public's mental model of the economy is built on figures that no longer exist.
4. **Nothing is checkable.** The dominant format is a confident sentence with no path to the underlying number, the calculation, or the source. Users who want to verify cannot, and users who should want to verify have been trained not to expect it.

## 5. Product Promise

**Everything MacroChipz tells you, you can check. Nothing MacroChipz tells you requires you to check.**

Concretely, MacroChipz commits to:

- **Every number has a source, a date and a calculation** reachable in one interaction.
- **Every economic state has a named, versioned, published methodology.**
- **Every revision is shown, not silently overwritten.**
- **We say when we do not know**, including when the honest answer is "nothing meaningful changed."
- **We distinguish what we recorded from what we reconstructed.** Point-in-time claims are never made from backfilled data.
- **Sponsorship never touches the intelligence.**
- **AI explains; it never decides.**

## 6. Behavioral Loop

**WOW → UNDERSTAND → EXPLORE → SHARE → RETURN**

| Stage | Target reaction | What delivers it |
|---|---|---|
| **WOW** | *"Whoa. I didn't know you could look at the economy like this."* | The Lede; Revision Intelligence; the Pulse's visual legibility |
| **UNDERSTAND** | *"Ohhh. Now I understand."* | Plain-English summaries; Wait, Seriously?; term definitions in place |
| **EXPLORE** | *"I wonder what MacroChipz says about ______."* | Economic worlds; rabbit-hole links; Ask MacroChipz |
| **SHARE** | *"I need to send this to someone."* | Permanent URLs; share cards; evidence surviving the click-through |
| **RETURN** | *"I wonder what changed."* | Calendar; Follow; the Brief; What Changed |

**The loop is a design tool, not a scorecard.** A feature does not need to serve all five. It needs one clear job (§38).

## 7. See → Understand → Verify

The core information hierarchy. It appears at every level of the product — a homepage card, a world page, a single number.

**SEE** — what happened, at a glance. Visual, immediate, no jargon, no interaction required.
**UNDERSTAND** — what it means in normal language, why it might matter, how it connects to the rest of the economy.
**VERIFY** — the data behind it, the calculation that produced it, the source that supplied it, whether it was revised, and which methodology version produced the state.

**Rules:**

1. **A beginner must never need to open VERIFY.** If a claim is incomprehensible without its evidence, the claim is written badly.
2. **A professional must always be able to open VERIFY,** from anywhere, in one interaction.
3. **VERIFY is progressive disclosure, never a separate destination.** It expands in place. Sending a user to a different page to check a number is a failure.
4. **VERIFY is never empty.** If a claim has no evidence, the claim does not ship.
5. **The three layers must not contradict each other.** SEE and UNDERSTAND are renderings of the same structured object VERIFY exposes. They cannot be authored independently.

## 8. Product Principles

1. **Honest over impressive.** If the honest version of a feature is less exciting, ship the honest version. "No meaningful changes today" is a valid, designed, first-class product state.
2. **Never manufacture activity.** Quiet economic periods are real. The product is designed for them explicitly (§17), not papered over.
3. **Deterministic first, interpretive second.** No canonical conclusion is ever produced by a language model.
4. **Evidence is a feature, not a footnote.** It is in the interface, not in a docs directory.
5. **Progressive disclosure over dumbing down.** Keep precise terminology; teach it in place. Never remove the real word.
6. **Mobile is first-class, not a fallback.** Designed at phone width first.
7. **Connected over comprehensive.** A product with six well-linked economic worlds beats one with twenty isolated dashboards.
8. **Earn every feature.** New capabilities pass §38's decision rules before they are built, and user-facing statistical claims pass evaluation before they are shown.
9. **Preserve what works.** Thirty-four increments produced a sound engine. The consumer experience changes; the engineering invariants do not.
10. **Measure to learn, not to justify.** Analytics informs evolution. It is not permission to build.

## 9. Trust Constitution

**MacroChipz does not compete by having better opinions. It competes by being checkable.**

Trust must be **visible in the interface**, not documented elsewhere. A user who never reads a methodology page should still be able to tell that one exists.

**Required trust surfaces:**

| Mechanism | Where it appears |
|---|---|
| **Source label + retrieval date** | On every number, at VERIFY depth |
| **Calculation shown** | Every derived figure states the operation and inputs |
| **Methodology version** | Every economic state carries its frozen version string |
| **Revision history** | Every revisable number links to its revision record |
| **Knowledge-basis disclosure** | Every point-in-time claim states whether it is `OBSERVED` or `BACKFILLED` |
| **Surfacing rationale** | Every surfaced item answers "why is MacroChipz showing me this?" |
| **Uncertainty disclosure** | Any claim near a published significance threshold says so |
| **AI boundary** | Every AI-generated sentence is visibly labelled as interpretation |
| **Sponsorship disclosure** | Unmistakable, never ambiguous |
| **Correction mechanism** | A visible, dated corrections record |

**Three hard rules:**

1. **Derived figures must be labelled as MacroChipz calculations**, never attributed to the source agency as published figures. This is a licensing requirement from BEA and Census, and it happens to be the right product behaviour.
2. **A number that failed its own significance threshold must never be narrated as a change.** No "payrolls weakened" on a sub-122,000 move; no "revised unusually" on a sub-118,000 revision.
3. **Corrections are published, not silently patched.** If MacroChipz gets something wrong, the record shows it was wrong and when it was fixed.

## 10. Tone & Personality

**Curious, plain, confident where the evidence supports confidence, and visibly uncertain where it does not.**

| Do | Don't |
|---|---|
| "Something changed." | "BREAKING: economy in freefall" |
| "Here's what happened." | "What the Fed doesn't want you to know" |
| "Wait, seriously?" / "Yep. Economic numbers can change after they're published." | "This guarantees a recession." |
| "Nothing dramatic changed today. That's useful information too." | Manufacturing a narrative to fill a slot |
| "This is close to the line where BLS says it can't tell the difference from zero." | "Jobs are collapsing." |
| "We don't know yet." | Implying certainty we don't have |

**Absolute prohibitions:** investment advice or anything shaped like it ("this is bullish," "time to buy"); partisan framing or attributing economic outcomes to political actors as fact; sensationalism; false certainty; juvenile humour that undercuts the trust position.

**Personality is permitted and encouraged** — *"Wait, seriously?"* is the house voice. Personality lives in the framing and the curiosity, never in the conclusion.

**Style rules:** short sentences; the plain word first and the technical word immediately after (not the reverse); no jargon in a headline; never more than one number in a sentence a beginner reads; active voice; no hedging stacked on hedging.

## 11. Economic Pulse

**Job: ORIENT ME.**

An understandable view of the U.S. economy within seconds, across six worlds: **Inflation, Jobs, Rates, Housing, Consumer, Growth.**

**What it is:** a compact visual summary, one tile per world, each showing a current state, a direction, and when it was last updated.

**What it is not:** a differentiator. The Chicago Fed's CFNAI has collapsed dozens of indicators into a single number since 2001, and at least three free consumer products ship a similar composite today. **We build the Pulse because the product needs an orientation surface. We never sell the product on it.**

**Hard rules:**

1. **A world gets a state only when a defensible, versioned methodology produces one.** Where no methodology exists, the tile shows data and no state. An empty state is honest; an invented state is not.
2. **No composite "economy score."** A single number across unlike domains requires weighting choices we cannot defend, and it is the most-copied feature in the category. Six honest states beat one indefensible number.
3. **Non-colour-only state communication** — every state carries a text label and a shape/icon, never colour alone (§32).
4. **The Pulse never implies freshness it does not have.** Each tile shows its own as-of date. A world whose data is six weeks old says so.

## 12. What's Moving → "What Changed"

**Job: TELL ME WHAT CHANGED.**

**Renamed deliberately.** "What's Moving" implies continuous motion. The underlying data moves on a release schedule: only about 24% of business days carry a scheduled release from the current catalog, and monitors refresh once per release, not continuously. A feed UI would promise a freshness the economy does not have. **"What Changed" — with an explicit as-of — is the honest framing, and it is a better product because it sets the right expectation.**

**Every surfaced item must answer, in the object itself:**

- What changed?
- By how much, over what period?
- **Why did MacroChipz surface this?** (the surfacing rule and the threshold it cleared)
- Why might someone care?
- What evidence supports it?

**Hard rules:**

1. **Event-driven only.** Items appear because something happened, never because a slot needed filling.
2. **"No meaningful changes" is a valid, designed result** with its own layout — not an error, not an empty div.
3. **Every item declares its surfacing rule.** An item that cannot say why it is significant is not significant.
4. **State changes and metric drifts are visually distinct.** A state change is rare and meaningful by construction; a third-decimal metric move is not. Ranking them identically trains users to ignore both.
5. **Significance thresholds come from the publishing agency where the agency publishes them.** BLS's own confidence intervals are more credible than any threshold we invent, and citing them makes MacroChipz credibility-increasing rather than narrative-generating.

## 13. Explore the Economy

**Job: LET ME GO DOWN THE RABBIT HOLE.**

Six worlds, each a **destination** rather than a dashboard: **Inflation, Jobs, Rates, Housing, Consumer, Growth.**

A world may contain: current situation · what changed · key indicators with plain-English meaning · why it matters · historical context · revisions · related indicators · upcoming releases · explainers · Radar findings · video · evidence · Ask MacroChipz.

**Not every world needs every element on Day 1, and a world ships when it has something honest to say — not when it has every section filled.** A thin, honest world beats a padded one.

**Hard rules:**

1. **Every world page has at least three outbound rabbit-hole links** to other worlds, indicators, explainers or revisions (§27).
2. **A world with no data does not ship.** Placeholder worlds are worse than absent worlds.
3. **Worlds use consumer language.** The route is `/jobs`, not `/labor`.

## 14. Revision Intelligence

**Job: SHOW ME HOW OUR UNDERSTANDING CHANGED.**

**This is MacroChipz's signature capability.** The research found zero productised competitors, unregistered candidate domains, and an unmet demand shock — a −911,000 benchmark revision, a fired BLS commissioner, a data blackout, and a year of "can we trust the numbers" coverage that produced op-eds and no tools.

**The experience:** for any revisable figure — what was originally reported · what it was revised to · what it says today · the magnitude and direction of the revision · **what MacroChipz's methodology concluded then** · **what the same methodology concludes now** · evidence for both.

**Four time concepts that must never be conflated** — this is the single most important correctness requirement in the product:

| Concept | Meaning |
|---|---|
| **Observation date** | The period the data describes (e.g. August 2026) |
| **Publication date** | When the agency released that figure |
| **System recorded time** | When MacroChipz first recorded it (`recorded_from`) |
| **Provider revision time** | When the agency revised it |

**Hard rules:**

1. **Never claim knowledge MacroChipz did not possess at that historical point.** Today, every stored observation version is backfilled; zero are genuinely observed, and no revision event has ever been captured. Until genuine prospective history accumulates, every historical claim is labelled as a reconstruction.
2. **`OBSERVED` and `BACKFILLED` are visually distinguishable everywhere, not disclosed in a footnote.**
3. **Routine revisions are not news.** A 40,000 payroll revision is entirely ordinary; BLS's own mean absolute revision is ~57,000. A revision is surfaced as notable only when it clears a published threshold.
4. **The most interesting honest revision statistic is direction, not magnitude** — a binomial sign test on consecutive revisions ("the last nine revisions were all downward; under unbiased revisions that happens about one time in 250"). Deterministic, cheap, explainable, and genuinely beneath-the-headline.
5. **MacroChipz never predicts revisions.** Describing the realised record against the agency's own published distribution is descriptive. Forecasting the next one is not, and is out of scope.

## 15. MacroChipz Radar

**Job: SHOW ME SOMETHING UNUSUAL.**

Radar remains in the long-term vision. It is **not** a Day-1 feature, and the reason is arithmetic rather than taste.

**The constraint.** Broad scanning produces false findings at a rate that would destroy the trust position. A 600-test monthly scan at a 2σ bar produces roughly 27 false findings per month under a pure null. On MacroChipz's own series, a 2σ bar yields about one genuine candidate per series every two years. **Radar can be honest or frequent. It cannot be both.**

**Therefore Radar is a curated registry, never a scanner.** Each detector is an economically motivated hypothesis registered in advance, not a combination discovered by search.

**Every detector must define, before it may run:** the economic hypothesis · input series · transformations · expected relationship · detection method · minimum history · significance and effect-size requirements · multiple-testing treatment · methodology version · known limitations · backtest results · evidence requirements · user-facing explanation rules.

**Finding classes:** divergence · acceleration · deceleration · reversal · historical extreme · revision anomaly · breadth · concentration · unusual relationship.

**Hard rules:**

1. **Pre-registration is mandatory.** If the set of tests can float, no honest significance claim exists.
2. **"No unusual signals detected" is a valid and expected result**, most months.
3. **No content quota, ever.** Radar is never asked to produce something for a publishing schedule.
4. **Findings carry a data vintage stamp and must be recomputable from it.** Seasonal factors are re-estimated annually and CES recomputes its adjustment monthly — without vintage pinning, last month's finding can silently cease to exist, and Radar's own archive would contradict itself.
5. **Same-instrument comparisons only for divergence.** Two surveys with different universes and wildly different resolutions cannot confirm or contradict each other; a "divergence" between them is an artifact.
6. **"While X remains stable" requires an equivalence test.** Asserting stability from a *failure* to detect change is not a finding. The stable leg must be shown equivalent within a pre-declared trivial region.
7. **Radar earns user-facing status through evaluation**, run against real data for a meaningful period with no user-facing output, before anything is shown.
8. **Radar never gets a permanent homepage block.** Its honest state is usually empty (§25.4).

## 16. Economic Time Machine

**Job: LET ME SEE THE ECONOMY THROUGH TIME.**

**Three stages, gated on genuine data rather than on engineering readiness.**

| Stage | Capability | Gate |
|---|---|---|
| **Stage 1** | **Revision comparisons** — original vs revised vs current for a given figure, with methodology-then vs methodology-now | Available now from provider revision data. **Day 1.** |
| **Stage 2** | **Point-in-time views** where genuine recorded history exists — "here is what MacroChipz actually knew on this date" | Requires accumulated `OBSERVED` versions. Begins accumulating Day 1; surfaces when there is enough to be worth showing. |
| **Stage 3** | **Broader interactive Time Machine** — rewind the economy across worlds | Requires substantial genuine history. **Long-term.** |

**Hard rules:**

1. **Never fake historical fidelity for UX.** This is the product's most tempting possible lie and it is absolutely prohibited.
2. **Backfilled history is never presented as MacroChipz knowledge.** It may be presented as *reconstruction from provider vintages*, clearly labelled.
3. **Start accumulating trustworthy prospective history immediately.** Every release captured from now on compounds. This is the cheapest high-value thing the product can do and it should begin on Day 1 regardless of when Stage 2 ships.
4. **Historical vintages are sourced only where redistribution rights are clear.** Archived agency releases and agencies' own vintage archives are usable; third-party vintage compilations are not, absent written permission.

## 17. Today in the Economy

**Job: MAKE THE ECONOMY FEEL ALIVE.**

**Revised from #35.** That research recommended rejecting this feature because only ~24% of business days carry a release. That conclusion conflated two different things: a **daily content obligation** (which is unsupported and is rejected) and a **daily surface** (which is fine, provided it never pretends).

**The quiet day is the design problem, and solving it well is the feature.**

On an active day: what was released, what MacroChipz processed, what changed, what state moved.

On a quiet day — which is most days:

> **Quiet day. No major releases scheduled.**
> Next: **CPI, Thursday 8:30am ET** — here's what it measures and why it matters.
> Meanwhile: *"Wait, seriously? The Fed doesn't set your mortgage rate."*
> Where things stand: [current economic context]

**Hard rules:**

1. **The quiet-day state is designed first**, not as a fallback. It is the modal experience.
2. **Never manufacture events.** Processing telemetry is not an economic event; if the only thing that happened is that we ran a job, that is a quiet day.
3. **The quiet day always has somewhere to go** — the next release, a relevant explainer, current context. An honest empty state is not a dead end.

## 18. Economic Calendar

**Job: TELL ME WHAT'S COMING.**

Each event should eventually answer: what is happening · when · what it measures · why you should care · what happened last time · what MacroChipz currently shows for that world · when MacroChipz expects to process it.

**The retention action:** *"Tell me when MacroChipz processes this."* This is the product's single most honest return mechanism — it promises exactly one notification, at a known time, for a specific thing the user asked about.

**Hard rules:**

1. **First-party schedules only.** BLS publishes an iCal feed; BEA publishes ICS, JSON and RSS. These replace the current third-party calendar dependency and are more defensible.
2. **The calendar never shows an event we cannot process.**
3. **Times are explicit with a timezone**, always. "8:30am ET" is a fact; "this morning" is not.

## 19. Wait, Seriously?

**Job: TEACH ME.**

Short explanations of things people measurably get wrong, connected to live MacroChipz data.

**The launch set, chosen by evidence rather than taste:**

1. **The Fed does not set your mortgage rate.** (66% of prospective homebuyers believe otherwise.)
2. **Falling inflation does not mean falling prices.**
3. **Economic numbers change after they're published — sometimes by a lot.** (The bridge to Revision Intelligence.)
4. **What CPI actually measures** — and what it doesn't.
5. **Why GDP can look fine while your life doesn't.** (The Fed's own SHED data shows 73% say they're doing okay while 25% rate the national economy well.)

Later: what a basis point is · why Treasury yields matter · nominal vs real · seasonal adjustment · annualised rates · labour-force participation.

**The required movement:** CONCEPT → CURRENT DATA → RELATED WORLD → EVIDENCE. An explainer that does not land the reader on live data has failed its job and is a generic economics article.

**Hard rules:**

1. **Every explainer links at least one claim to a live MacroChipz figure**, and that figure updates.
2. **Explainers are evergreen and maintained.** If the linked data moves, the explainer stays correct — it references the live value, not a frozen one.
3. **Never use ambiguous head terms for discovery.** "Inflation" and "recession" are dominated by unrelated meanings on the major platforms; "mortgage rates," "interest rates" and "economics explained" are clean. Titles and slugs follow the clean terms.
4. **This carries the days releases cannot.** Roughly two-thirds of business days have no release; explainers are why the product is still worth visiting.

## 20. Ask MacroChipz

**Job: ANSWER MY QUESTION.**

The bounded architecture from Increment #33 is preserved exactly: operates over deterministic context packets · one bounded model call · no tools · no autonomous session · validated evidence references · contained failures · optional.

**Hard rules:**

1. **It never produces a canonical conclusion.** It explains what the deterministic engine already determined.
2. **It is contextual, not a destination.** It appears next to the thing being asked about — a number, a state, a revision — and answers *"why did this change?"*, *"what does this mean?"*, *"why should I care?"*, *"what is core inflation?"*, *"why was this number revised?"*
3. **It does not dominate the homepage.** There is no chat box in the hero. The AI-explainer niche being unoccupied is not a reason to lead with a chatbot; it is a reason to have the best-grounded one.
4. **The core product works fully when it is unavailable.** Nothing on any page blocks on a model call.
5. **Every response is visibly labelled as interpretation.**

## 21. MacroChipz Brief

**Job: SUMMARIZE IT FOR ME.**

Formats: **read · email · watch · listen** — derived from the same structured intelligence, never authored independently.

**Cadence follows information value:** release-driven for major releases (CPI, Employment Situation) · a weekly wrap · special events (benchmark revisions, FOMC) · **daily only if a given day genuinely warrants it, which most days do not.**

**Hard rules:**

1. **Never manufacture a daily narrative.** The cadence is a consequence of the data, not a commitment to an audience.
2. **All formats derive from one canonical intelligence object.** The email and the video script are renderings, not retellings.
3. **Every claim in the Brief links back to its evidence page**, in every format that supports a link.
4. **Human review before publication** for anything carrying the MacroChipz name in a media channel.

## 22. Follow the Economy

**Job: BRING ME BACK WHEN SOMETHING MATTERS.**

Follow targets: the six worlds · specific releases · eventually specific indicators.
Notification triggers: release processed · state changed · material revision · meaningful movement · validated Radar finding · upcoming release.

**The design constraint is that honest triggers are rare by construction.** State changes are deliberately dampened by deadbands; material revisions must clear a published threshold; Radar findings are rare by design. **This is a feature.** A notification that arrives rarely and always matters is worth more than a daily digest nobody opens.

**Hard rules:**

1. **Start minimal:** email only, world-level and release-level, release-driven. No push, no SMS, no per-indicator granularity at launch — granularity implies a frequency the data does not have.
2. **Every notification states why it fired** and links to the evidence.
3. **A hard frequency ceiling per subscriber**, enforced in the system rather than by editorial restraint.
4. **One-click unsubscribe, honoured immediately.**
5. **Never send to create engagement.** If nothing cleared a threshold, nothing sends.

## 23. Sharing

**Job: BRING SOMEONE ELSE IN.**

**Sharing is an architectural concern, not a feature bolted on at the end.** Interesting MacroChipz objects are designed to leave MacroChipz and bring someone back.

**Shareable objects:** charts · revisions · economic movements · Radar findings · Pulse snapshots · historical comparisons · release summaries · explainers.

**Every shareable object requires:**

- A **permanent, stable URL** that will still resolve years later
- **Server-visible metadata** — title, description, canonical URL (crawlers do not execute client-side JavaScript)
- A **generated Open Graph image** that is legible as a thumbnail and says something true without context
- **Mobile-first rendering** of the destination
- **Clear MacroChipz branding** on the card
- **Evidence available after the click-through** — the shared claim lands on its own proof

**Hard rules:**

1. **Screenshots are never the primary sharing mechanism.** A screenshot is an unverifiable, undated, unlinkable copy of a claim — the exact failure mode MacroChipz exists to fix.
2. **Share cards state their as-of date.** A card shared six months later must not imply currency.
3. **Every OG image is generated from the canonical object**, never hand-made, so it cannot drift from what the page says.

## 24. Economic Worlds

Six worlds. Each is a first-class destination with its own URL, own state, own revisions and own explainers.

| World | Route | Day-1 status | Primary sources |
|---|---|---|---|
| **Inflation** | `/inflation` | **Core — exists** | BLS (CPI), BEA (PCE) |
| **Jobs** | `/jobs` | **Core — exists as "Labor"** | BLS (CES, CPS) |
| **Rates** | `/rates` | **Core — exists** | U.S. Treasury |
| **Housing** | `/housing` | **SHIPPED (#45)** | Census (permits, starts, completions). **No Treasury proxy** — see note below |
| **Consumer** | `/consumer` | Post-launch | Census (retail sales), BEA (personal income/outlays) |

> **#45 did not ship the Treasury proxy this table planned.** A 10-year yield rendered beside permits and starts asserts a housing-to-rates relationship MacroChipz has measured nothing about, and labelling it a proxy does not undo what two figures side by side communicate. `/housing` names what MacroChipz tracks, names what it does not, and links to `/rates` — with no figure. See `docs/architecture/housing-world.md` §10.
| **Growth** | `/growth` | Post-launch | BEA (GDP) |

**On Housing and the mortgage-rate problem.** The weekly mortgage-rate survey most people know is not redistributable — its terms prohibit commercial republication, derived products and automated collection simultaneously. MacroChipz therefore shows the **10-year Treasury**, which is what mortgage rates actually track, and says plainly why. **The limitation is the lesson.** "We show you the 10-year Treasury because that's what actually moves your mortgage rate — and because the survey number itself isn't ours to republish" is both legally correct and exactly the thing the wedge audience needs to learn.

**Worlds are connected, not parallel.** Rates → Housing, Inflation → Rates, and Jobs → Inflation are first-class relationships with explicit links (§27).

## 25. Homepage

The eight-block hierarchy proposed in the #36 brief was evaluated against WOW/UNDERSTAND/EXPLORE/SHARE/RETURN and **is not adopted as given.** Four problems:

- **Eight blocks is a desktop dashboard.** On a phone it becomes an eight-screen scroll before anything interesting.
- **Radar at position 3 is a block whose honest state is usually empty.** Permanently reserving prime space for absence trains users to scroll past it.
- **Revisions at position 5 buries the actual differentiator** below the two most commoditised features.
- **Brief and Follow at positions 7–8** put the conversion asks where the fewest people reach.

### 25.1 Recommended hierarchy

**1. THE LEDE — one thing, always full, never manufactured.**
The single most significant intelligence object right now, chosen deterministically by significance rank. On a release day, the release. On a benchmark-revision day, the revision. On a quiet day, a *Wait, Seriously?* explainer bound to current data. **This is the WOW slot, and because an explainer is a legitimate occupant, it is always full without ever inventing activity.**

**2. PULSE — six worlds, compact.** ORIENT. Each tile: state (text + shape + colour), direction, as-of date.

**3. WHAT CHANGED — event-driven, honest empty state.** With its as-of, its surfacing rules, and a visible distinction between state changes and metric drifts.

**4. EXPLORE — entry to the worlds**, with one live hook per world rather than six identical tiles.

**5. WHAT'S NEXT — the calendar, compact**, with the Follow action inline at the point of intent rather than in a footer.

**Footer:** the Brief, methodology, corrections, about, trust statement.

**Radar, when it exists, appears inside THE LEDE when it has a finding, and inside worlds.** It does not get a standing homepage block.

> **Design rule: no homepage block whose honest state is usually empty.**

### 25.2 Mobile (first-class, designed first)

Single column. **THE LEDE fills the first screen** — one object, one claim, one visual, one action. Pulse is a horizontally scrollable row of six compact tiles (not a 2×3 grid that pushes everything below the fold). What Changed, Explore and What's Next stack. Touch targets ≥44px. VERIFY expands in place, never navigates away.

### 25.3 Desktop

THE LEDE spans full width. Pulse is a six-up grid. What Changed and What's Next sit side by side. Explore is a full-width band. **Desktop gets more density, not more features** — the two layouts render the same objects.

### 25.4 Homepage rules

1. **THE LEDE is chosen deterministically** by a published significance ranking, never by editorial mood or by a model.
2. **No block exists whose usual state is empty.**
3. **Every block has a designed empty state.**
4. **No chat box in the hero.**
5. **The homepage must be useful and complete without any AI call succeeding.**
6. **The first screen must make sense to someone who has never heard of MacroChipz** and does not know what CPI stands for.

## 26. Navigation / Information Architecture

### 26.1 Primary navigation (5 items)

**Home · Inflation · Jobs · Rates · Calendar**

Housing joins when it ships; Consumer and Growth join post-launch. At six worlds, primary nav becomes **Home · Explore ▾ · Calendar**, with the worlds under Explore. **Never more than five top-level items.**

### 26.2 Page types and URL principles

| Type | Pattern | Indexable | Purpose |
|---|---|---|---|
| Home | `/` | Yes | Orientation |
| World | `/inflation`, `/jobs`, `/rates`, `/housing`, `/consumer`, `/growth` | Yes | Destination per domain |
| Indicator | `/indicators/{slug}` — `cpi`, `unemployment-rate`, `10-year-treasury` | Yes | One series, deep |
| Release | `/releases/{release}/{period}` — `/releases/cpi/2026-09` | Yes | Permanent record of one release |
| Revision | `/revisions/{indicator}/{period}` | Yes | Permanent record of one revision |
| Explainer | `/explainers/{slug}` | Yes | Evergreen education |
| Radar finding | `/radar/{finding-id}` | Yes (later) | Permanent record of one finding |
| Calendar | `/calendar`, `/calendar/{event-id}` | Yes | Upcoming |
| Methodology | `/methodology`, `/methodology/{id}` | Yes | Trust surface |
| Evidence | `/evidence/{id}` | **No** — `noindex` | Verification target, not a landing page |
| Corrections | `/corrections` | Yes | Trust surface |

**Hard rules:**

1. **Every URL is permanent.** A release page from 2026 still resolves in 2030 with the same content plus its revision history.
2. **Renames require redirects.** `/labor` → `/jobs` and `/overview` → its replacement are 301s, not deletions.
3. **No thin pages.** A page is indexable only if it provides real standalone value. Programmatic generation of thousands of near-identical indicator/period pages is prohibited.
4. **One canonical URL per object.** Filtered and parameterised views carry a canonical link to the base object.
5. **Every page offers the next relevant thing** (§27). A page with no onward path is a leak.

## 27. Rabbit-Hole Design

Exploration is the product's retention mechanism, and it must come from genuine curiosity rather than dark patterns.

**Two designed loops, both real:**

```
Jobs → Payrolls → This month's revision → Why revisions happen
  → Historical payroll revisions → Labor state methodology
  → Upcoming jobs release → Follow Jobs
```

```
Mortgage rates → 10Y Treasury → Why Treasury yields matter
  → Inflation expectations → Inflation world → Upcoming CPI → Follow Inflation
```

### 27.1 Linking rules

Relationships are **declared in the intelligence layer, never hand-authored per page** — hand-authored links rot, and a rotted link on a trust product is expensive.

| From | Must link to |
|---|---|
| **World** | Its indicators · its latest release · its revisions · ≥1 explainer · its upcoming releases · ≥1 related world |
| **Indicator** | Its world · its release · its revision history · its methodology · ≥1 explainer defining its terms |
| **Release** | Its world · the indicators it moved · the prior release of the same series · its evidence |
| **Revision** | The original figure · the current figure · the indicator · the "why revisions happen" explainer · its evidence |
| **Explainer** | ≥1 live indicator · ≥1 world · related explainers |
| **Radar finding** | Every input series · its detector's methodology · its evidence · its world |

**Hard rules:**

1. **Minimum three outbound contextual links per substantive page.**
2. **Links are contextual, not a "related" dump.** A link is placed where the curiosity arises — inside the sentence that provokes it.
3. **No infinite scroll, no autoplay, no artificial gating, no engagement-maximising notification.** If curiosity does not carry the user forward, the content is the problem.
4. **Every rabbit hole terminates somewhere satisfying** — evidence, a methodology, or a Follow action.

## 28. Content / Media System

**One economic event produces one structured intelligence object, which renders into many surfaces.**

```
SOURCE DATA → DETERMINISTIC ENGINE → STRUCTURED INTELLIGENCE OBJECT → EVIDENCE
                                              ↓
   website · Brief · email · YouTube · Shorts/TikTok/Reels · social card · permanent page
```

**The boundary, stated precisely:**

| CANONICAL INTELLIGENCE | CONTENT PRESENTATION |
|---|---|
| What happened | How it is phrased |
| The numbers, calculations and states | Titles, thumbnails, framing, pacing |
| Significance determination | Which of several true things to lead with |
| Evidence and provenance | Format, length, channel |
| Produced deterministically | May be AI-assisted, human-reviewed |
| **Never AI-generated** | **Never contradicts the canonical object** |

**Hard rules:**

1. **The content system never determines what happened.** If the pipeline needs a model call to know what the economy did, the architecture is wrong.
2. **AI may draft scripts, summaries, titles, descriptions and social copy from structured facts.** It may not introduce a fact, a number, a state or a causal claim absent from the object.
3. **Human review before publication** for anything published under the MacroChipz name in a media channel.
4. **Every published piece carries a link back to its canonical object.**
5. **If the object says nothing significant happened, no content is produced.** The content calendar is downstream of the economy, never upstream.

## 29. Distribution

Distribution surfaces are **measurable hypotheses, not guaranteed funnels.**

| Surface | Treated as |
|---|---|
| **Search** | Evergreen discovery for explainers and permanent objects. Assume erosion; finance is the hardest category for an unknown domain. |
| **Email** | The owned, algorithm-independent **return** channel. |
| **Social sharing** | User-initiated, per-object. The reason §23 is architectural. |
| **YouTube / Shorts / TikTok / Reels** | **Channel audience**, not site traffic. Published evidence suggests near-zero referral. |
| **LinkedIn / X / Threads** | Presence and citation, not traffic. |
| **Audio** | Depth and loyalty, not traffic. |
| **Direct** | The goal state. Everything above exists to produce it. |

**MacroChipz.com is a first-class product, not an evidence appendix for social media.** #35 concluded from referral economics that the newsletter should be the primary surface; that conclusion confused *where users are acquired* with *where value is created*. **Value is created on the site — the worlds, the evidence, the rabbit holes — none of which fits in an email.** The Brief is the RETURN mechanism in the loop, not the product. This is an explicit override of #35 (§38.3).

**Hard rules:**

1. **No channel is assumed to convert.** Every one is instrumented and evaluated on measured behaviour.
2. **Server-visible share metadata is a launch requirement**, not an optimisation.
3. **We do not chase virality.** Shareability is designed per-object; reach is an outcome.
4. **A channel that does not measurably serve the loop after a fair trial is dropped**, not persisted with out of sunk cost.

## 30. Sponsorship Constitution

Consumer MacroChipz remains broadly free with no login wall on the primary experience. Sponsorship may become a monetisation model **after a meaningful audience exists.**

**The separation is absolute. Sponsors must never influence:** canonical facts · methodology · economic states · Radar findings · which evidence is shown · revisions · conclusions · Analyst responses · what appears in THE LEDE · notification triggers.

**Hard rules:**

1. **Sponsored content is unmistakably identifiable**, never ambiguous, never styled to resemble intelligence.
2. **No sponsor category may relate to the subject of a MacroChipz conclusion in a way that creates an appearance of influence.** A mortgage lender sponsoring the mortgage-rate explainer is prohibited regardless of actual independence.
3. **The product is never designed around maximising impressions.** No ad-driven pagination, no interstitials, no layout decisions justified by inventory.
4. **Audience trust has priority over revenue, every time, with no exception.**
5. **The separation is published**, in plain language, on a page users can find.

This is not only ethics. *"Isn't trying to sell me something"* ranks as the **second** trust criterion among the target demographic — and higher among non-investors than investors. **The separation is the product's principal competitive asset against the finfluencer field, and it should be stated openly rather than merely observed.**

## 31. Analytics / Measurement

**We build with conviction and measure with humility.** Instrumentation informs evolution; it is not permission to build.

**Privacy-conscious by construction:** no personal data beyond an email address the user volunteers · no cross-site tracking · no advertising pixels · no fingerprinting · cookie-free measurement where possible · aggregate analysis only.

| Loop stage | Events | The question it answers |
|---|---|---|
| **WOW** | homepage visit, LEDE view, LEDE interaction, time to first interaction | Does the first screen land? |
| **UNDERSTAND** | evidence expanded, term definition opened, explainer opened, explainer completion | **Does anyone actually verify? — the single most important question we can ask, because §2's central bet depends on it** |
| **EXPLORE** | world opened, indicator opened, related item followed, exploration depth, session path | Do rabbit holes work? |
| **SHARE** | share initiated, share completed, inbound from a share, evidence viewed after inbound share | Do objects survive leaving? |
| **RETURN** | return visit, days-to-return, email signup, follow signup, calendar follow, Brief open/click | Is there a reason to come back? |
| **Health** | Analyst question submitted, Analyst failure, quiet-day view, empty-state view | Do honest empty states retain or repel? |

**Hard rules:**

1. **Every event must name the question it answers.** No event ships without one. Data collected "because we can" is deleted.
2. **No dark-pattern optimisation.** Time-on-page is not a goal; understanding is. We would rather a user got the answer in ten seconds and left.
3. **Evidence-expansion rate is the headline metric.** If nobody opens VERIFY, the provenance bet is wrong and the product strategy needs revisiting — not the analytics.
4. **Empty states are measured, not assumed.** Whether "nothing changed today" retains or repels is an empirical question with real consequences for the honesty position.
5. **Analytics never gates publication.** We do not suppress an honest finding because it underperforms.

## 32. Accessibility

Accessibility is a **product requirement**, not a compliance exercise. Target: **WCAG 2.2 AA**.

- **Semantic HTML** — real headings, lists, landmarks, buttons. Not divs with handlers.
- **Full keyboard navigation**, visible focus, logical order, no traps. VERIFY disclosure is keyboard-operable.
- **Screen readers** — every chart has a text alternative conveying the same information; data tables are available; ARIA only where semantics are insufficient.
- **Economic state is never communicated by colour alone** — always text label plus shape/icon. This is the most likely accessibility failure in a product built on state colours, and #27B's token separation already anticipates it.
- **Reduced motion honoured** (`prefers-reduced-motion`); no essential information conveyed only through animation.
- **Contrast** meets AA for text and for state indicators against their backgrounds, in both themes.
- **Touch targets ≥44×44px.**
- **Plain language** — the accessibility requirement and the product mission are the same requirement.
- **Progressive disclosure** never hides essential information behind an interaction.

**Hard rule: an inaccessible feature is an unfinished feature.** Visual sophistication does not earn an exemption.

## 33. Performance

**MacroChipz should feel fast, and must remain useful when parts of it are not.**

1. **Server-rendered or pre-rendered HTML for anything shareable or indexable.** Crawlers and social scrapers do not execute client-side JavaScript; a client-only SPA cannot have working share cards or search presence.
2. **Nothing blocks initial understanding on an AI call.** SEE and UNDERSTAND render from canonical data; Analyst output arrives separately or not at all.
3. **Charts are not in the initial bundle.** The first meaningful paint does not wait on a charting library.
4. **Canonical reads are cached** — they change on a release schedule, which makes them exceptionally cacheable. Cache keys include the methodology version and data vintage so a revision or methodology change invalidates correctly.
5. **Video never loads until requested.** Facade first, embed on interaction.
6. **Share metadata is server-visible**, always.
7. **Every page works with the Analyst unavailable, and degrades legibly with the database unavailable.**

**We do not pre-optimise infrastructure.** Measured page experience matters; theoretical scale does not, at this size.

## 34. SEO / Permanent Knowledge Objects

Important MacroChipz objects get **permanent URLs** because they are permanent knowledge — a record of what was known, when.

**Indexable:** worlds · indicators · releases · revisions · explainers · Radar findings · calendar · methodology · corrections.
**Not indexable:** evidence endpoints (`noindex` — they are verification targets, not landing pages) · filtered or parameterised views (canonical to the base object) · any page without standalone value.

**Required per indexable page:** unique descriptive `<title>` and meta description · canonical URL · Open Graph and Twitter card metadata · a generated OG image · structured data where genuinely applicable · `sitemap.xml` entry · server-rendered content · a last-updated date.

**Hard rules:**

1. **No thin pages, no programmatic mass generation.** A page exists because a human would find it useful.
2. **Permanent means permanent.** URLs are not restructured for cosmetic reasons; renames get 301s.
3. **Titles use clean, unambiguous terms**, avoiding head terms dominated by unrelated meanings.
4. **We do not write for search engines.** Explainers exist because the misconception is real and measured.

## 35. Day-1 Scope

**Day 1 must demonstrate the system, not a feature.** A visitor should leave understanding that MacroChipz is a connected, evidence-backed view of the economy — not a dashboard, not a newsletter, not a revision tracker.

**Classification is sequencing, not deletion from the vision.**

| Feature | Classification | Why |
|---|---|---|
| **Economic Pulse** | **DAY 1 CORE** | The ORIENT job. Exists in substance today. Not a differentiator — required furniture. |
| **What Changed** | **DAY 1 CORE** | The "why return" answer. Engine already produces the events. |
| **Inflation world** | **DAY 1 CORE** | Exists. Frozen methodology, evidence, what-changed, state duration. |
| **Jobs world** | **DAY 1 CORE** | Exists as Labor. Renamed for consumer language; carries the revision story. |
| **Rates world** | **DAY 1 CORE** | Exists. The only daily-moving data, and the bridge to the mortgage wedge. |
| **Revision Intelligence** | **DAY 1 CORE** | **The signature capability.** Stage 1 (revision comparison) is available now from provider data. Without it Day 1 is a commodity dashboard. |
| **Wait, Seriously?** | **DAY 1 CORE** | Carries the ~two-thirds of days with no release; the acquisition wedge; cheapest thing to build. Five explainers. |
| **Sharing** | **DAY 1 CORE** | Architectural, not additive. Retrofitting permanent URLs and server-visible metadata later is far more expensive. |
| **Analytics** | **DAY 1 CORE** | Without it we learn nothing from launch. Currently zero exists. |
| **Housing world** | **SHIPPED (#45)** | Census permits, starts and completions, national, monthly — seasonally adjusted annual rate and unadjusted count. **No 10Y proxy shipped** (see the domain table above). No mortgage survey data — not licensable. **No state**, and none planned. |
| **Calendar** | **DAY 1 LIMITED** | Schedule + "what it measures" + "why care" + Follow. **Not** "what happened last time" (needs accumulated history). |
| **Ask MacroChipz** | **DAY 1 LIMITED** | Shipped and evaluated. Contextual placement only. Not in the hero. |
| **Today in the Economy** | **DAY 1 LIMITED** | Delivered as THE LEDE plus a designed quiet-day state. **Not** a live activity timeline. |
| **Follow / email** | **DAY 1 LIMITED** | One list, world- and release-level, release-driven. The only owned return channel — cannot be deferred, must stay small. |
| **Time Machine** | **DAY 1 LIMITED (Stage 1 only)** | Revision comparisons ship. Genuine point-in-time accumulation **starts** Day 1 and surfaces later. |
| **Brief** | **POST-LAUNCH** | Depends on a stable intelligence layer and an audience to send to. Building a distribution channel before having anything to distribute is the wrong order. |
| **Radar** | **POST-LAUNCH** | Registry design and offline evaluation first. Nothing user-facing until it earns it. |
| **Consumer world** | **POST-LAUNCH** | Zero data held. Licensing clean; effort real. |
| **Growth world** | **POST-LAUNCH** | Zero data held. BEA's own vintage archive makes it the best *second* revision story. |
| **Video** | **POST-LAUNCH** | Needs the content system and a reason to believe it converts. |
| **Time Machine Stage 2** | **POST-LAUNCH** | Gated on accumulated `OBSERVED` history — time, not engineering. |
| **Time Machine Stage 3** | **LONG-TERM** | Needs years of genuine history. |
| **Push / SMS notifications** | **LONG-TERM** | Email first; prove the trigger design before adding intrusive channels. |
| **Forecasting** | **LONG-TERM / deferred** | Must earn the right through data, evaluation and methodology. |

**Day 1 in one sentence:** *Six worlds' worth of orientation (three deep, one partial, two absent), what changed and why it mattered, the revision story nobody else tells, five explainers answering what people actually get wrong, a calendar telling you when to come back, and evidence behind every word — all of it shareable, measurable, and legible on a phone.*

## 36. Later Scope

**Post-launch, in dependency order:** the Brief (read + email) · deep historical re-ingestion · Consumer and Growth worlds · Radar registry and offline evaluation · Time Machine Stage 2 · Radar user-facing (conditional on evaluation) · video and the content system · per-indicator follows · richer calendar history.

**Long-term:** Time Machine Stage 3 · additional worlds if earned · audio · API/data licensing, embeds, B2B and white-label · forecasting, if ever.

**On later monetisation: none of it may distort the Day-1 consumer product.** One observation only — the most defensible asset MacroChipz can accumulate is a point-in-time-correct archive captured from day one. That is a reason to **start capturing immediately**, not a reason to build for licensing now.

## 37. Explicit Non-Goals

MacroChipz 2.0 is **not**:

1. A Bloomberg Terminal or a professional research platform
2. A Yahoo Finance clone or a general financial portal
3. A stock trading platform, or any surface that resembles one
4. An investment recommendation service — **no buy/sell framing, ever**
5. A political commentary product
6. A generic AI chatbot
7. An autonomous economic agent
8. A prediction market or a forecasting engine
9. A generic financial-literacy course
10. A news scraper or aggregator
11. An engagement-bait media site
12. **A daily-content obligation** — cadence follows the data
13. **An uncontrolled anomaly generator** — Radar is a curated registry
14. **A product that fabricates historical knowledge** — backfilled is never presented as observed
15. **Comprehensive** — no equities or crypto for breadth; no world without a defensible methodology

**On forecasting specifically:** deferred until MacroChipz has sufficient data, a published evaluation methodology, demonstrated calibration and honest uncertainty communication. Not prohibited forever. **Not now, and not by inference from a descriptive feature.**

## 38. Product Decision Rules

Every proposed feature is evaluated against these before it is built. **Record the answers in the proposing increment.**

### 38.1 The five loop questions

A feature **does not need all five.** It needs **one clear job** and must not damage the others.

1. **WOW** — Does this make the economy feel meaningfully different from a normal dashboard?
2. **UNDERSTAND** — Does this help a non-economist understand something important?
3. **EXPLORE** — Does it create a legitimate path to deeper understanding?
4. **SHARE** — Can the insight naturally leave MacroChipz and still make sense?
5. **RETURN** — Does it create a legitimate reason to come back?

### 38.2 The five gates — **all five are mandatory**

6. **TRUST** — Can we support every claim with evidence a user can reach? *If no: reject.*
7. **HONESTY** — Are we representing what the data actually allows us to know? Does it hold up on a quiet day, at low significance, and with thin history? *If no: reject.*
8. **SYSTEM FIT** — Does it strengthen the connected experience, or is it a standalone bolt-on? *An isolated feature is a liability.*
9. **COMPLEXITY** — Is the user value worth the engineering and operational burden, including its ongoing correctness cost?
10. **AI NECESSITY** — Does AI genuinely improve this, or are we adding AI because we can? *Default answer is no. The burden is on the proposal.*

### 38.3 Standing overrides of Increment #35

Recorded so future increments do not re-open them.

| #35 recommendation | Constitution decision | Reason |
|---|---|---|
| "Reject Today in the Economy" | **Kept as THE LEDE + designed quiet-day state** (§17) | #35 conflated a *daily content obligation* (correctly rejected) with a *daily surface* (fine if it never pretends). Solving the quiet day honestly is better product design than removing the surface. |
| "Newsletter-first; the website is the evidence library" | **The website is the product; the Brief is the RETURN mechanism** (§29) | #35 reasoned from referral economics to product architecture. Referral data says where users are *acquired*; it says nothing about where value is *created*. Worlds, evidence and rabbit holes do not fit in an email. |
| "Radar → LATER, possibly never" | **Radar → POST-LAUNCH, as a curated registry** (§15) | #35's arithmetic refutes *broad scanning*, which is correctly abandoned. A small pre-registered set of economically motivated detectors is a different thing and survives the same arithmetic. |

**Findings from #35 that are binding and not subject to override:** the multiple-comparisons arithmetic · the published significance thresholds · the prohibition on backfilled data as point-in-time knowledge · the data licensing constraints · the release-cadence reality · the requirement to re-pull rather than append seasonally adjusted series.

### 38.4 Tie-breakers

When two principles conflict:

1. **Honesty beats engagement.** Always.
2. **Trust beats reach.**
3. **Clarity beats completeness.**
4. **Connected beats comprehensive.**
5. **Mobile beats desktop.**
6. **Deterministic beats clever.**
7. **Shipping a smaller honest thing beats shipping a larger one with an asterisk.**

---

## Appendix A — Build Sequence

Proposed increments. **This is sequencing, not a commitment to an order that cannot change** — if a later increment reveals a better ordering, take it. Each increment must create meaningful user value, preserve existing functionality, carry explicit acceptance criteria, maintain the engineering boundaries, and be independently testable. **No big-bang rewrites.**

### Phase 1 — Foundations (nothing user-visible ships without these)

| # | Increment | Why here | Acceptance |
|---|---|---|---|
| **#37** | **Distribution & measurement instrumentation** | Zero exists today. Every shared link renders as a bare URL, and **no behaviour the thesis depends on is measurable.** Everything downstream is unverifiable until this lands. | OG/Twitter metadata, meta descriptions, canonical URLs, `sitemap.xml`, `robots.txt`, privacy-conscious analytics with a documented event→question map, email capture with double opt-in |
| **#38** | **Source abstraction (`SeriesSource`) + FRED adapter** | Pure refactor, zero behaviour change. The safest possible first step toward provider independence, and it must precede any migration. | All existing results byte-identical; golden vectors pass; no service depends on a concrete client |
| **#39** | **Canonical series identity + BLS migration (labor)** | Two series, one agency. Smallest real migration. Must carry identifiers, or FRED's naming survives a FRED-free system. | `labor_v1.0` results byte-identical from BLS; identifier mapping persisted; full-history re-pull implemented |
| **#40** | **BLS + BEA migration (inflation)** | Two agencies, one methodology. The seasonally-adjusted re-pull rule lands here. | `inflation_v1.0` byte-identical; SA series re-pulled in full; revisions detected rather than overwritten |
| **#41** | **Provider-neutral release calendar (BLS iCal + BEA JSON)** | The stickier FRED dependency. Supersedes ADR-020. | Calendar renders from first-party schedules; FRED release IDs demoted to bindings |

### Phase 2 — The system (this is what "MacroChipz 2.0" means)

| # | Increment | Why here |
|---|---|---|
| **#42** | **Structured Intelligence Layer** | Everything downstream is a rendering of it. Building surfaces first guarantees drift. |
| **#43** | **Server-rendered document head + rendering model** | Sharing and search are architectural; retrofitting is far more expensive. Resolves the open rendering question. |
| **#44** | **Information architecture, routing and redirects** | `/jobs`, `/calendar`, permanent object URLs, 301s from `/labor`, `/overview`, `/releases`. Must precede the homepage so URLs stabilise once. |
| **#45** | **Homepage 2.0** | THE LEDE, Pulse, What Changed, Explore, What's Next. Most of it already exists on `/overview`. |
| **#46** | **Revision Intelligence** | **The signature capability.** Resurfaces `components/history/*` as a first-class product, adds `revision_significance_v1.0`, Time Machine Stage 1. |
| **#47** | **Wait, Seriously? + explainer↔data binding** | Carries the ~two-thirds of days with no release. `content/explanations/*` already holds 34 curated explanations — the infrastructure substantially exists. |
| **#48** | **Sharing: permanent objects, share cards, OG image generation** | Depends on #42 (objects) and #43 (rendering). |
| **#49** | **Housing world (Census)** | **DELIVERED EARLY, as #45.** First genuinely new data source. Shipped with data and no state, as planned. |
| **#50** | **Follow + email** | The only owned return channel. Deliberately minimal. |

**→ LAUNCH.** Then measure, for a real period, before building more.

### Phase 3 — Post-launch, evidence-led

| # | Increment | Gate |
|---|---|---|
| **#51** | **Deep historical re-ingestion** | Unblocks historical-context claims and is a Radar precondition |
| **#52** | **MacroChipz Brief (read + email)** | Needs a stable intelligence layer and an audience to send to |
| **#53** | **Consumer + Growth worlds** | BEA's own vintage archive makes Growth the best *second* revision story |
| **#54** | **Radar registry + offline evaluation** | **No user-facing output.** Runs privately for a meaningful period first |
| **#55** | **Radar user-facing** | **Conditional on #54's evaluation.** May not ship. |
| **#56** | **Time Machine Stage 2** | Gated on accumulated `OBSERVED` history — time, not engineering |
| **#57** | **Content system + video** | Gated on evidence that evidence-linked content converts |

### Cross-cutting, in every increment

**Accessibility, mobile-first layout, evidence completeness, and the architectural guard tests are not increments.** They are acceptance criteria on every increment above. An increment that ships an inaccessible surface, a desktop-first layout, or a claim without evidence is not finished.

### Sequencing rules

1. **#37 is unconditionally first.** Without it, nothing that follows can be measured or shared.
2. **Data migration (#38–#41) precedes public launch** — FRED cannot be the spine of a public commercial product — but does not block UI work on #42–#50.
3. **#42 precedes every surface.** Surfaces built before the object will each invent their own.
4. **#44 precedes #45.** URLs stabilise once; redirects are cheap at first, expensive later.
5. **Nothing in Phase 3 begins until launch has been measured** for long enough to say something.
6. **Radar cannot skip #54.** An unevaluated detector reaching users would damage the trust position more than shipping no Radar at all.

---

**This Constitution is authoritative for MacroChipz 2.0 product decisions.** It is amended by explicit increment, not by drift. Where an implementation increment finds a rule unworkable, the correct response is to propose an amendment with reasoning — not to quietly deviate.
