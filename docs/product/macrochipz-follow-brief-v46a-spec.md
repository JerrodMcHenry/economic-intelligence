# MacroChipz — Follow & Brief Product Specification V1

**Increment #46A.** Research and specification only. No production code, no migration, no email integration, nothing committed or pushed. Baseline: HEAD `bf5f7d9` (#45B).

**Method.** Repository state inspected directly — routes, services, data models and the live development database — before any recommendation. Provider pricing and compliance requirements sourced to official documentation, with anything unverified marked **UNVERIFIED**. No user research was conducted and none is claimed; §A states explicitly what its scenarios are and are not.

---

## §0. Three measured facts that decide this increment

Everything below follows from these. They were measured, not assumed.

### 0.1 — MacroChipz currently has **zero** communication-eligible events

Queried against the development database this increment:

| Evidence class | Count | Eligible to notify? |
|---|---|---|
| Observation versions, `BACKFILL` origin | 1,072 | **No** — imported, not observed |
| Observation versions, `HOUSING_INGESTION`, `is_backfilled = true` | 4,644 | **No** — #45's baseline import |
| **Prospective revisions ever captured** | **0** | — |
| Analysis updates, `AVAILABILITY_RESTORED` | 1,488 | **No** — coverage, not economics |
| Analysis updates, `CONFIRMATION_CHANGED` | 44 | **No** — all `UNAVAILABLE → x` first computations (#42) |
| Release check runs ever executed | 3 | — |

**An event-triggered Follow feature shipped today would send nothing, to anyone, indefinitely.** That is not a reason to lower the bar. It is the reason the bar exists — and it is the single strongest argument in this document for sequencing.

### 0.2 — MacroChipz has never been deployed

The journal's increment sequence goes #26E → #27B. **#26F was a research and contract freeze; #26G (infrastructure), #26H (bootstrap + scheduler activation) and #26I (reliability verification) never ran.** There is no production environment, no domain, no TLS certificate, no sending identity.

### 0.3 — Automated sending is blocked by an already-recorded decision

ADR-029 defers scheduler activation and names the blocker precisely: activation "requires a real, network-reachable production database and an explicit, reviewed answer to whether a scheduler can reach it without weakening its own access controls — neither exists yet." A `.disabled` workflow template exists specifically so it cannot execute.

**Consequence:** any design that assumes "an event fires and an email goes out" inherits a blocker this project has already declined to resolve twice.

---

## §A. User need — five return scenarios

**What these are:** structured hypotheses about why someone would return, written to be falsifiable and to constrain design. Each names what would make it *wrong*.

**What these are not:** validated demand. No user research was conducted. No persona here represents an observed user. #28's own finding stands — the revision-intelligence moat is "a real moat and an unproven purchase reason", and nothing since has tested it.

### A1 — "Did the thing I keep hearing about actually happen?"

**Wants to know:** whether the inflation number people are arguing about on the news moved, and whether it means what the argument claims.
**Should prompt a return:** a new CPI or PCE release that MacroChipz has processed, with its state either changed or explicitly unchanged.
**Noise:** any day without a release. Intraday anything. A rates movement — this reader does not distinguish a 10-year yield from a mortgage rate, which is precisely what `fed-and-mortgage-rates` exists to correct.
**Must accompany:** the figure, the period it describes, the prior figure, the methodology id, and the source. Without the prior figure the number is unreadable.
**Right vehicle:** **periodic Brief.** Monthly cadence data does not justify an alert, and this reader's question is "what happened recently", not "tell me the instant it lands".
**Wrong if:** readers want the number within minutes of release. Then an alert is right and a Brief is late.

### A2 — "Is the job market getting harder?"

**Wants to know:** direction over months, not one print.
**Should prompt a return:** a Jobs state transition, or a monthly cadence check-in.
**Noise:** a single month's payroll change presented as a trend. Employment and unemployment disagreeing, presented as contradiction rather than as the two-survey distinction `jobs-two-surveys` explains.
**Must accompany:** both surveys, the `labor_v1.0` state, its deadbands, and the explainer link.
**Right vehicle:** **Brief.** A state transition is rare enough to be worth an alert, but transitions are exactly what MacroChipz has never yet observed (§0.1), so alerting on them promises a message that may not arrive for months.
**Wrong if:** readers experience monthly summary as stale.

### A3 — "The number changed after they published it?"

**Wants to know:** that a figure they saw was revised, what it was, and whether MacroChipz's own conclusion changed with it.
**Should prompt a return:** a `PROSPECTIVE_REVISION` — a revision MacroChipz *watched happen*.
**Noise:** a backfilled baseline presented as a revision. A first observation. A routine re-sync confirming an unchanged value.
**Must accompany:** the value MacroChipz held, the value now, when each was recorded, whether the methodology's conclusion moved, and — non-negotiably — the `revision_knowledge` distinction in words.
**Right vehicle:** **alert, eventually.** This is the one genuinely interruption-worthy event MacroChipz can produce, and the only one where MacroChipz has something competitors structurally cannot show (#28).
**Wrong if:** revisions turn out to be frequent and small enough that alerting on each is noise. **Currently untestable: zero have ever been captured.**

### A4 — "Are homes getting built near me?"

**Wants to know:** whether construction is picking up, in numbers they can picture.
**Should prompt a return:** the monthly New Residential Construction release.
**Noise:** a SAAR figure presented as homes built that month — the exact misreading `saar-housing` exists to correct. Month-to-month moves framed as trend, against Census's own guidance that a trend takes three to six months.
**Must accompany:** annual rate *and* the month's actual count, the period, Census's irregularity guidance, and the verbatim non-endorsement notice.
**Right vehicle:** **Brief.** Housing has no methodology and therefore no state transition to alert on. A Brief can report the figures without a verdict; an alert implies one by existing.
**Wrong if:** readers want a local figure. MacroChipz has national data only, and this scenario's "near me" is a demand the product cannot meet.

### A5 — "I saw a video and want to keep learning"

**Wants to know:** more questions like the one that brought them.
**Should prompt a return:** a new explainer, or a genuinely good existing one they have not read.
**Noise:** economic data. This reader arrived for an idea, not a figure.
**Must accompany:** the question, the one-sentence answer, and one link.
**Right vehicle:** **Brief**, as one editorial slot — or nothing at all, if the explainer library grows too slowly to justify a promise.
**Wrong if:** #44's deferred discovery problem is better solved on-site than by email.

### What the five have in common

Four of five point at a **periodic Brief**. The one that points at an alert (A3) depends on an event that **has never occurred**. That is the product answer to the sequencing question, arrived at before any engineering argument.

---

## §B. Follow model

### The four candidates, assessed

| Candidate | Verdict | Reasoning |
|---|---|---|
| **A world** (Inflation / Jobs / Rates / Housing) | **The only viable granularity** | Matches how the product is already organised, matches how a reader thinks ("I care about housing"), and is already the shape of `follow_signup: { target: World \| "all" }` reserved in #37's vocabulary. Four options a first-time reader understands without a preference screen. |
| **A concept** (`UST_NOMINAL_10Y`) | **Reject for V1** | Source-neutral concept ids are an engineering identity. A reader who wants "the 10-year" is a reader the Rates world already serves. Eighteen follow targets is a preference screen pretending to be a feature. |
| **A release** (CPI, Employment Situation) | **Reject for V1** | Plausible and genuinely useful later — but it promises delivery on a schedule MacroChipz cannot yet meet (§0.2, §0.3), and three of the six curated releases feed no monitor at all (#45B). Following GDP would subscribe you to a schedule and nothing else. |
| **An explainer or question** | **Reject** | Explainers are durable and rarely change. Following one means subscribing to an event that will essentially never fire. |

### Recommended initial model

**Follow a world, or follow everything. Five checkboxes, one email field, no account.**

- No password, no login, no profile. The subscription *is* the email address plus a set of world ids.
- Preferences are managed from a signed link in every email — no session, no account recovery flow, no password reset surface.
- "All" is a distinct value, not four checkboxes ticked, so a world added later does not silently expand an existing subscription without consent.

### But the recommendation below is to not ship Follow first

See §J. The model above is what Follow should be *when* it ships; §0.1 is why that is not now.

---

## §C. Notification eligibility — `communication_eligibility_v1`

### It is a separate contract, and must stay separate

`homepage_presentation_v1.0` answers **"what should MacroChipz show first?"** — a selection among things a reader chose to come and look at.

Communication eligibility answers **"is this worth interrupting someone who did not ask right now?"** That is a categorically higher bar, and the two must not share a rule set:

1. **Reusing THE LEDE's policy would import a selection rule as a permission rule.** The lede always picks *something* when anything is eligible; a communication policy must be able to pick *nothing*, indefinitely, and that must be a success state.
2. **Weakening either to serve the other is the failure mode.** If the homepage ever needed more content, the pressure would land on a shared policy, and a homepage change would silently start sending email.

**Frozen relationship: communication eligibility is a STRICT SUBSET of homepage eligibility. Never a superset, never an overlap with exceptions.** An object that may not appear on the homepage may never be emailed. A test should assert this.

### The eligibility table

| Evidence class | May trigger a user-facing communication? | Why |
|---|---|---|
| **A new official release MacroChipz processed**, where processing produced at least one observation change on a mapped canonical series | **YES**, in a Brief | A real published fact reaching MacroChipz. Not an alert: the schedule is monthly and the calendar already tells the reader it is coming. |
| **A newly observed `PROSPECTIVE_REVISION`** | **YES** — the only alert-worthy class | MacroChipz watched a published value change. The one thing it can prove that others cannot. |
| **A deterministic state change under an approved methodology** (`inflation_v1.0`, `labor_v1.0`) where `previous_value` is a real prior value | **YES** | A frozen methodology reached a different conclusion. Rates and Housing are excluded — neither has a state, and inventing one to have something to send is the exact failure this table prevents. |
| **A routine sync** that confirmed unchanged values | **NO** | Nothing happened. `ObservationVersionWriter` correctly writes no version row for it. |
| **A bootstrap / coverage record** (`AVAILABILITY_RESTORED`, `UNAVAILABLE → x`) | **NO** | 1,488 of these exist. They record MacroChipz gaining the ability to compute, not the economy moving. |
| **A backfilled observation** (`is_backfilled = true`) | **NO — absolutely** | 5,716 exist. Emailing them would claim MacroChipz watched sixty-seven years of history happen. |
| **A provider error, timeout, or unavailable data** | **NO** | An operational fact. It belongs in `housing_ingestion_runs` and operator health, never in a reader's inbox. A provider outage is not economic news. |
| **An editorially published explainer** | **YES**, in a Brief, as an editorial slot | Not canonical intelligence at all — a human wrote and reviewed it, and the Brief's own editorial section is the honest home for it. Never an alert. |

### Three rules that constrain every row above

1. **Eligibility is structural, never magnitude.** No threshold, no "big move", no score. #39 publishes no significance ranking and #46 must not introduce one through the back door of "what's worth emailing".
2. **An ingestion event is never economic news.** The distinction between "MacroChipz learned something" and "something happened" is the one this product is built on.
3. **Zero eligible events is a valid, successful outcome.** The system must be comfortable sending nothing. §D.4 defines what a Brief does in that case.

---

## §D. The MacroChipz Brief

### D.1 — The consumer promise

> **Once a week, what actually changed in the economy — and how you'd check it yourself.**

Three things that promise does *not* make: not "the biggest story", not "what it means for markets", not daily.

The Brief's differentiator is the same as the product's. Every figure carries its period, its source and a link to its evidence. It is the only economic newsletter that can say *"here is what we held before, here is what we hold now, and here is when we learned it"* — when there is a revision to say it about.

### D.2 — Cadence: weekly, and why not daily or monthly

**Weekly is right for the wrong-looking reason:** the underlying data is *monthly*. A daily Brief would have nothing to say four days in five and would manufacture content to fill the gap — the single most likely way this product acquires a fake-significance habit. A monthly Brief would miss the rhythm of readers' attention and would arrive as a digest nobody remembers subscribing to.

Weekly is the shortest cadence at which a quiet edition is **normal rather than embarrassing**, which matters because §0.1 guarantees many quiet editions.

**Revisit when** the data cadence changes — if EIA weekly energy data ever lands (#45A §H.4), weekly becomes genuinely news-bearing and the calculation changes.

### D.3 — Editorial structure

Five slots, fixed order, each independently omittable except the last two:

1. **What changed** — eligible intelligence objects under §C, rendered with figure, period, prior value, methodology and an evidence link. Omitted entirely in a quiet week; never padded.
2. **Where things stand** — the four worlds' current states and latest periods. **Always present.** This is what makes a quiet Brief still worth opening, and it is the same claim `WorldOrientation` makes on the homepage (#45B): "these exist, here is the latest data on file", never "this changed".
3. **Coming up** — the next scheduled releases from the existing calendar, with #45B's honest not-tracked marking intact. A schedule is not a publication claim.
4. **Understand this** — one curated explainer. Always present. Never generated.
5. **How we know** — sources, attributions, methodology ids, and the unsubscribe link.

### D.4 — Quiet weeks

**A quiet Brief ships, and says so.** Slots 2–5 carry it, and slot 1 is replaced by a sentence in the register `/revisions` already uses:

> *No new tracked change this week. MacroChipz records what it knew at each point in time, so when a figure does change, you will see the change rather than a quietly replaced number.*

That sentence is a claim about MacroChipz's record, not about the economy. **It must never read as "the economy was quiet"** — the economy is always operating. `QuietLede` already holds this line on the homepage and the Brief inherits it.

Weekly cadence makes this sustainable. Most editions in the first months will be quiet, and the product should be designed for that rather than surprised by it.

### D.5 — Facts versus interpretation

The Brief must carry the same machine-readable distinction `#39` already encodes, expressed visually:

- **`SOURCE_FACT`** — "Census published this." Attributed to the source.
- **`METHODOLOGY_DERIVED`** — "`inflation_v1.0` concluded this." Attributed to the named, versioned methodology.
- **Editorial** — "MacroChipz wrote this." The explainer slot, visually distinct, never adjacent to a figure in a way that could be read as commentary on it.

A reader must never have to guess which of the three they are reading.

### D.6 — Human editorial review at launch: **required**

**Yes, and it is not a temporary crutch.**

1. It is the only control that catches a sentence that is technically true and materially misleading — the failure mode this whole product is organised against.
2. At launch volume the cost is minutes per week.
3. It removes the scheduler blocker entirely (§0.3): a human pressing send is not automation, and does not need one.
4. It creates the evidence needed to decide what to automate. Automating first means automating a format nobody has read.

**Exit criterion, stated now so it is not argued later:** automation may be considered after **eight consecutive editions** reviewed with no content correction, and only once the scheduler blocker is independently resolved.

### D.7 — AI's role: **none at launch**

Assessed honestly rather than dismissed.

**Where it could plausibly help:** drafting the one-sentence summary of a change from structured fields.

**Why not:** that sentence is a template over fields MacroChipz already has — *"Core PCE momentum moved from X to Y for {period}"* — and a template is deterministic, reviewable, and cannot hallucinate a number. The generative version costs a dependency, a cost, a latency, and a whole class of failure, to produce prose a `f-string` produces correctly.

**The real argument against** is #44's: the explainer layer's value is that every sentence was written and reviewed. A Brief carrying one generated sentence forfeits the property that distinguishes it, in exchange for nothing.

**The bounded exception, if ever:** the Analyst's existing constraints already describe the only safe shape — AI may *explain* canonical intelligence that already exists; it may never *select* what is worth sending, *decide* significance, or *produce* a figure. Nothing in the Brief needs that today.

---

## §E. Delivery and privacy

### E.1 — Three delivery shapes compared

| | Minimal email subscription | Account-based Follow | On-site-only Follow |
|---|---|---|---|
| What it stores | Email + world ids + consent record | Users, passwords, sessions, resets | A browser local value |
| Return mechanism | **Push — genuinely solves RETURN** | Push | **None — the reader must already be returning** |
| Auth surface | None | Password reset, session fixation, enumeration | None |
| Consent complexity | Double opt-in | Double opt-in *and* account terms | None |
| Privacy exposure | One identifier | Identifier plus behaviour | Minimal |
| Verdict | **Recommended** | **Reject** — #45A §K names overbuilding accounts as a risk; nothing here needs identity | **Reject as the whole answer** — it does not solve RETURN; useful only as an unauthenticated preference store later |

### E.2 — Provider research

**Pricing verified against official pages this increment. Terms-of-service permitted-use clauses were NOT read and are marked UNVERIFIED — that is a required human review step, not an engineering one.**

| Provider | Free tier | Entry paid | Notes |
|---|---|---|---|
| **Postmark** | 100 emails/mo, "never expires" | **$15/mo** for 10,000; $1.80/1,000 extra | Separate **Message Streams** for transactional vs broadcast — *"transactional and marketing emails never mix"*. Strong deliverability reputation. |
| **Resend** | **3,000/mo, 100/day**, 3 domains, 1,000 marketing contacts | $20/mo (50k) transactional; marketing priced by **contacts** from $40/mo | Broadcasts included on marketing plans; dedicated IP $30/mo add-on on Scale. |
| **Amazon SES** | $200 AWS credits (new accounts, 12 mo) | **$0.10–$0.16 per 1,000** | Cheapest at volume. **New accounts are sandboxed**: verified recipients only, 200 messages/24h, 1/sec, until a production-access request is approved (initial response ~24h). Unsubscribe handling, suppression and bounce processing are largely **your** build. |
| **Buttondown** | First 100 subscribers free | à-la-carte add-ons $9–$79/mo | Newsletter-native. **Structural mismatch:** content would live in Buttondown, not in MacroChipz, which conflicts with the permanent-destination model. |

### E.3 — Recommendation, and the reasoning that is not price

At launch volume — tens to low hundreds of subscribers, one send per week — **every option above costs under $20/month. Price is not a differentiator and must not be the deciding factor** (the instruction is explicit, and it is also correct).

Decide on **operational correctness**, where the options genuinely differ:

1. **Compliance primitives built in**: RFC 8058 one-click unsubscribe, suppression list, bounce and complaint webhooks. SES makes these your problem; Postmark and Resend provide them.
2. **Transactional/broadcast separation.** MacroChipz sends both — a confirmation email (transactional) and a Brief (broadcast). Mixing them on one reputation is a known deliverability error, and Postmark's Message Streams address it as a first-class concept.
3. **Failure containment.** A provider outage must degrade to "this week's Brief is late", never to lost subscriptions or duplicate sends. That is an architecture property (§F), not a vendor one.

**Stated preference: Postmark**, on stream separation and deliverability, with **Resend** as a credible alternative whose free tier genuinely covers launch. **SES is rejected for V1** — its cost advantage is irrelevant at this volume and its operational surface is the largest.

**This is a recommendation, not a decision.** The vendor choice requires human approval and a terms read (§L.3).

### E.4 — Compliance requirements, verified

Google's bulk-sender guidelines (threshold: **more than 5,000 messages per day to Gmail**) do not bind MacroChipz at launch volume, but the requirements are the industry floor and should be met from the first send:

- **SPF, DKIM and DMARC** on the sending domain.
- **One-click unsubscribe** per **RFC 8058**: both `List-Unsubscribe-Post: List-Unsubscribe=One-Click` and `List-Unsubscribe: <https://…>` headers, plus a clearly visible unsubscribe link in the body. The sender must operate infrastructure to handle the resulting **POST**.
- **Unsubscribe processing within 48 hours** (Google's guidance; Yahoo's is 2 days). MacroChipz should process synchronously and treat 48 hours as an outer bound it never approaches.
- **Spam complaint rate below 0.30%**, ideally under 0.10%.

### E.5 — Privacy contract

| | |
|---|---|
| **Consent** | Explicit. An unchecked control, an unambiguous statement of what will be sent and how often, and a link to what is stored. No pre-ticked boxes, no consent bundled with any other action. |
| **Double opt-in** | **Yes — required, not optional.** An email field with no account is trivially abusable to subscribe someone else. Double opt-in is the only thing standing between the product and being a tool for sending mail to people who did not ask. It also protects deliverability from typo addresses. |
| **Unsubscribe** | One click, no login, no confirmation step, no "are you sure". Effective immediately and honoured before the next send under any circumstance. |
| **Data minimisation** | **Email address, chosen world ids, consent timestamp, consent source, and delivery state. Nothing else.** No name, no IP retained after the confirmation step, no open tracking, no click tracking with per-user identifiers, no third-party pixels. |
| **Retention** | Unconfirmed subscriptions **deleted after 7 days**. Unsubscribes retain a one-way hash for suppression only — enough to never mail them again, not enough to reconstruct the address. Full deletion on request. |
| **Rate limits and abuse** | Per-IP and per-address rate limiting on the subscribe endpoint; confirmation tokens single-use, expiring, and cryptographically random; unsubscribe tokens signed and non-enumerable. No endpoint reveals whether an address is subscribed. |
| **Bounces and complaints** | Hard bounce → immediate permanent suppression. Repeated soft bounces → suppression after a fixed threshold. **Any complaint → immediate permanent suppression**, never a "are you sure" flow. |
| **Operational recovery** | Every send is idempotent (§F). A partial failure resumes without re-sending. Suppression is enforced at send time, not only at subscribe time, so a stale list cannot mail a suppressed address. |

### E.6 — The analytics boundary, which must not be crossed

`product-measurement.md` §6 prohibits collecting "names, email addresses, or any personal identifier". **That prohibition stands unchanged.** A subscription is *product data* in MacroChipz's own database; it never enters the analytics path. §H is written to respect this.

---

## §F. Architecture

### F.1 — The chain

```
Official source
  → observations + versions            (#29/#31, unchanged)
  → canonical intelligence             (#39, unchanged, still generated on read)
  → communication eligibility          (NEW — §C, a pure function)
  → BriefEdition                       (NEW — PERSISTED, immutable once sent)
  → delivery                           (NEW — provider adapter at the boundary)
```

### F.2 — The one genuinely new architectural idea

**A communication object must be persisted, and it is the first thing in this system that must be.**

Intelligence objects are generated on read (#39) and are *supposed* to change when the underlying data is revised — that is the feature. An email is the opposite: once sent, what it said is fixed forever, and the data it quoted may since have been revised.

So a `BriefEdition` is **an immutable snapshot with its own identity**, holding the rendered content, the intelligence object ids it drew on, the values as they stood, and the instant it was composed. Regenerating it later would produce a different Brief — which is exactly why it cannot be regenerated.

This is the same distinction #31 drew between the current-state cache and system-time history, applied one layer up. It also makes "what did we tell people, and was it right?" answerable, which a product built on provenance should be able to answer about its own output.

### F.3 — Properties

| Concern | Design |
|---|---|
| **Idempotency** | `(edition_id, subscriber_id)` unique on the delivery table. A retried send is a no-op. The edition is composed once and never recomposed. |
| **Revisions and corrections** | A revision **after** a Brief ships is *new content for the next edition*, never a silent edit of the last. If a Brief was materially wrong, the correction is its own edition saying so — the same discipline `/revisions` applies to economic data, applied to MacroChipz's own output. |
| **Publication timing** | The edition records its **composition instant** and its **send instant**, separately, both real. Neither is ever substituted for a provider's publication time, which MacroChipz does not know (`published_at` is null on every object it holds). |
| **Retries** | Per-recipient, bounded, with backoff. A permanent failure suppresses; a transient one retries. Delivery state lives per recipient, never per edition. |
| **Duplicate suppression** | Enforced at send time against the suppression list, not at compose time — a subscriber who unsubscribes between composition and send is not mailed. |
| **Evidence links** | Every figure links to a permanent MacroChipz destination (`/intelligence/:id`, a world page, an explainer). No figure appears without a route to its evidence. |
| **Historical replay vs current publication** | A Brief is composed from **current** canonical intelligence at composition time and then frozen. #31's replay answers "what did MacroChipz know at T"; a `BriefEdition` answers "what did MacroChipz *say* at T". Related, different, and must not be conflated. |
| **Separation of concerns** | Eligibility is a **pure function** over intelligence objects, in `app/domain/`, with no I/O and no knowledge that email exists. Canonical intelligence must never learn that a communication layer exists — the dependency points one way only. |
| **Provider failures** | The provider adapter lives at the boundary, like `CensusClient`. A provider outage fails the *send*, never the composition, and never corrupts subscriber state. Credentials never logged, never persisted, never in an error message — the containment rules #45 established for Census apply unchanged. |
| **AI** | Absent from the chain. If ever added, it may only annotate an already-composed edition, downstream of eligibility and outside the delivery path, and marked non-authoritative. |

### F.4 — Data contracts

```
Subscription
  id, email, world_ids[], status (PENDING|CONFIRMED|UNSUBSCRIBED|SUPPRESSED),
  consent_recorded_at, consent_source, confirmed_at, unsubscribed_at

ConfirmationToken   single-use, expiring, hashed at rest
UnsubscribeToken    signed, non-enumerable, long-lived

BriefEdition        id, period_start, period_end, composed_at, sent_at,
                    status (DRAFT|APPROVED|SENDING|SENT|FAILED),
                    content_snapshot, intelligence_object_ids[]

BriefDelivery       edition_id, subscription_id, status, provider_message_id,
                    attempts, last_error_class     -- class name only, never a body

SuppressionEntry    email_hash, reason (BOUNCE|COMPLAINT|UNSUBSCRIBE), created_at
```

**`DRAFT → APPROVED` is a human step.** It is the editorial review of §D.6 expressed in the schema, so review cannot be skipped by forgetting.

---

## §G. User journey

```
Discover → Understand why → Consent → Confirm → Receive → Open a permanent
destination → Explore evidence → Manage or unsubscribe
```

### Entry points, and where not to put them

| Surface | Placement | Reasoning |
|---|---|---|
| **Home** | Below the world orientation, above the footer | A reader who has seen what MacroChipz covers is qualified to decide. Above it, they are not. |
| **World pages** | After evidence, near `Understand this` | Same rule #40B/#44 already apply to education: the fact comes first. |
| **Explainer pages** | After the answer, beside the existing share control | The strongest placement — a reader who finished an explainer has demonstrated the exact interest the Brief serves, and #45A found explainers are where video traffic lands. |
| **Permanent object pages** | After the evidence | Same rule. |
| **Calendar / Revisions** | **No** | Calendar is a schedule; Revisions is currently empty. Neither has earned the ask. |

**Prohibited, explicitly:** modals, interstitials, exit-intent popups, scroll-triggered overlays, anything that interrupts a first read. #45A found first-screen comprehension already weak; an overlay would make the product's worst measured problem worse to solve its second-worst.

### The consent moment

One email field, five checkboxes (four worlds + "everything"), one sentence stating **what arrives, how often, and what is stored**, and one button. No name field. No "how did you hear about us". The confirmation email states the same three things again and contains exactly one action.

### The first Brief must be worth it

A subscriber who receives a quiet Brief as their *first* edition has no basis to judge the product. **The welcome email should therefore be a real sample edition** — the current "where things stand" for their chosen worlds, plus one explainer — not a "thanks for subscribing" with no content.

---

## §H. Measurement

Reuses the existing closed vocabulary. **One event is already reserved for exactly this**: `follow_signup: { target: World | "all" }`, marked "RESERVED — not emitted today. Follow/email does not exist yet (Increment #46)."

### The funnel, and what each stage may record

| Stage | Mechanism | Data |
|---|---|---|
| **Discovery** | `page_viewed` (existing) | Route template only |
| **Subscription interest** | `follow_signup` — **activate the reserved event** | `target` only: a world id or `"all"`. **Never the address.** |
| **Confirmed subscriptions** | **Product database, not analytics** | A count queried from `Subscription`. Confirmation happens in an email client, where no analytics exists — and even if it did, joining a confirmation to a browser session would be exactly the identifier linkage §6 prohibits. |
| **Delivery** | Provider webhooks → `BriefDelivery` | Operational state, never analytics |
| **Return visits** | `page_viewed` with a **campaign-free** link | See below |
| **Unsubscribes** | Product database | A count |
| **Complaints** | Provider webhooks → suppression | A count |

### Three rules

1. **Email opens are not engagement, and are not collected.** An open pixel measures whether an image loaded — increasingly meaningless under proxy prefetching, and a tracking pixel in a product built on provenance is a poor trade. The metric that matters is whether someone *came back and read something*, which `page_viewed` already answers.
2. **No per-user tracking parameters on links.** #40's `ShareButton` already refuses to append them. A Brief link is the plain permanent URL. Attribution, if needed, uses one non-identifying path variant — and only if a specific question requires it.
3. **Two systems, one boundary.** Subscriber data lives in MacroChipz's database. Analytics receives counts and world ids. Nothing crosses.

**One addition needed:** a `brief_` prefixed event is *not* required — `follow_signup` covers interest and `page_viewed` covers return. If a later question genuinely cannot be answered by either, it gets its own documented addition, not a widened property.

---

## §I. Risks and non-goals

### Risks

| Risk | Severity | Mitigation |
|---|---|---|
| **Thin or repetitive Briefs** | **Highest** — §0.1 makes it near-certain early | Slots 2–4 are independently valuable; weekly cadence makes quiet normal; human review can hold an edition. |
| **False significance** | **High** | §C forbids magnitude and score entirely. The word "biggest" cannot appear. |
| **Misleading revisions** | **High** | Only `PROSPECTIVE_REVISION` qualifies; `revision_knowledge` is rendered in words; a backfilled baseline can never be emailed. |
| **Notification fatigue** | Medium | Weekly ceiling; no alerts in V1; one email per week maximum regardless of event count. |
| **FRED redistribution in email** | **High and specific — see below** | Resolve before any Brief containing Inflation or Jobs figures. |
| **Accidental financial advice** | High | No forward-looking statement, no "what this means for your mortgage", no action language. The existing prohibited-vocabulary guards extend to Brief copy. |
| **Overbuilt accounts** | Medium | No accounts. §B. |
| **Deliverability and cost** | Low at launch | Double opt-in, immediate suppression, authenticated domain. |
| **Premature automation** | Medium | §D.6's eight-edition exit criterion. |

### The FRED problem, stated plainly

Inflation and Jobs figures currently come from **FRED** (`PCEPILFE`, `CPILFESL`, `PCEPI`, `CPIAUCSL`, `PAYEMS`, `UNRATE`). #28 recorded two unresolved FRED terms:

- apps may not *"replicate or attempt to replace the essential user experience of the FRED® API"* — rated **High** risk;
- *"Individual users of an application must use their own API key"* — rated **Medium-High**, **UNKNOWN — REQUIRES VERIFICATION**.

A newsletter is a **new distribution channel** for that data, which sharpens rather than softens the question. Three options, in order of preference:

1. **Complete the #M2 migration** — source CPI/PCE from BLS and BEA directly, both public domain. #28 already recommended this and #45A re-recommended it. It removes the question permanently.
2. **Ship the Brief with Rates and Housing figures only** (Treasury and Census, both clean), with Inflation and Jobs limited to *state labels and links* rather than figures. Awkward, but shippable.
3. **Obtain written clarification from the St. Louis Fed.** Slowest, and outside engineering's control.

**This is a launch dependency, not a footnote.** §J sequences it accordingly.

### Explicit non-goals for the first release

Do not build: user accounts or passwords · per-concept or per-release following · real-time or same-day alerts · a preference centre beyond four worlds plus "all" · open or click tracking · AI-generated prose · a web archive of past editions · sharing/referral mechanics · SMS or push · personalisation of content by reader · an in-app notification centre · a second "recent activity" surface.

---

## §J. Recommended #46B implementation

### The sequencing decision

**Ship a small, manually reviewed Brief. Do not ship automated Follow in the same increment.**

Reasoning, product first:

1. **Four of five return scenarios point at a Brief** (§A). The one that points at an alert depends on an event that has never occurred.
2. **A Brief is useful in a quiet week by design. Follow is not.** §0.1 guarantees quiet weeks, and Follow's entire value proposition is the arrival of events.
3. **Follow shipped today would send zero emails.** A subscribe button that promises notifications and delivers silence is worse than no button — it burns the one signup a reader will give you.

Engineering second:

4. **A manually sent Brief needs no scheduler**, and therefore does not inherit ADR-029's blocker.
5. **It needs no deployment to be built and tested**, though it needs one to send (§0.2).
6. **It builds the eligibility contract anyway.** `communication_eligibility_v1` is the hard part, it is shared, and a Brief exercises it under human review — which is the safest place to discover it is wrong.

**Follow is not cancelled. It is sequenced behind the event that justifies it** — the first real `PROSPECTIVE_REVISION`, which is also the moment MacroChipz's moat becomes demonstrable.

### #46B exact scope

**Backend**
- `communication_eligibility_v1` — a pure domain module, `app/domain/communication_eligibility.py`. No I/O. Asserted as a strict subset of homepage eligibility.
- Four tables: `subscriptions`, `brief_editions`, `brief_deliveries`, `suppression_entries` (+ token storage). One additive migration.
- Subscribe, confirm, unsubscribe endpoints. Rate-limited; no enumeration; unsubscribe accepts **POST** for RFC 8058.
- Composition service: assembles a `BriefEdition` from canonical reads. Read-only with respect to intelligence.
- An operator CLI to compose a draft, review it, approve it, and send — mirroring the existing operator-token pattern.
- Provider adapter at the boundary, with the #45 credential-containment rules.

**Frontend**
- One subscribe component, placed per §G. No modal.
- Confirmation and unsubscribe result pages.
- Activate the reserved `follow_signup` event.

**Acceptance criteria**
- A quiet-week edition composes, renders and is worth reading with **zero** eligible objects.
- A backfilled observation, a coverage record and a provider error each produce **no** eligible content — asserted individually.
- Eligibility is a strict subset of homepage eligibility — asserted.
- An unconfirmed subscription is never sent to.
- Unsubscribe works from a signed link with no session, is honoured before the next send, and is idempotent.
- A repeated send attempt for one `(edition, subscriber)` sends once.
- No email address appears in any analytics payload, log line, or error message — asserted.
- Every figure in a rendered edition carries period, source and an evidence link.
- Required attributions render verbatim, including Census's non-endorsement sentence.
- A composed edition is immutable once `SENT`.

**Tests**: eligibility unit tests per evidence class; the subset assertion; composition under zero/partial/full data; idempotency; suppression precedence; token single-use and expiry; RFC 8058 POST; credential and address containment; rendered-content guards (no significance vocabulary, no forward-looking language, no advice).

**Launch dependencies** (none of which are engineering's to decide alone):
1. **Deployment** — #26G/#26H, never executed (§0.2).
2. **A sending domain** with SPF/DKIM/DMARC.
3. **Provider selection** and a terms read (§E.2, §L.3).
4. **The FRED redistribution question** (§I) — or scope the first Brief to Rates and Housing figures.

**Deferred to #46C or later**: automated Follow; alerts on prospective revisions; scheduled sending; per-release following; a public archive of editions; any AI role.

---

## §K. Unresolved #45B launch issues

Carried forward, unchanged and unresolved:

1. **Genuine 390px mobile verification.** Still outstanding across all eight surfaces. The browser tooling reports a successful resize while media queries continue to match desktop — hit in #45A and again in #45B. `/housing` was verified properly at 390px during #45; the rest are covered only by structural assertions (no fixed pixel widths, mobile-first grids). **This needs a real device or a working emulation path, and it is a launch blocker for a product whose Constitution treats mobile as first-class.**
2. **Configured Analyst testing.** `available: false, reason: NOT_CONFIGURED` in this environment; the populated experience has never been exercised. The honest unavailable state is verified. **A decision is needed on whether the Analyst is part of the launch product at all** (#45A §M.3).
3. **Point-in-time replay has no consumer surface.** Deliberately not built in #45B; still orphaned engineering.
4. **RETURN remains unsolved until #46B ships.** This specification is the plan, not the fix.

---

## §L. Open decisions requiring approval

1. **Brief first, Follow later — approve or reject the sequencing.** Everything in §J depends on it.
2. **Weekly cadence** (§D.2).
3. **Provider choice**, and who reads the terms for permitted newsletter use — **UNVERIFIED** for every provider in §E.2.
4. **The FRED redistribution question** (§I): migrate, scope around it, or seek written clarification. This gates whether the first Brief may print an inflation figure.
5. **Who performs the weekly editorial review**, and what happens in a week when nobody can.
6. **Deployment** (#26G/#26H) — a prerequisite, unscheduled.
7. **Is the Analyst in the launch product?** (carried from #45A §M.3).
8. **Sending identity**: domain, from-address, and reply-to handling.

---

## Confirmations

- **No production code written. No migration created. No email service integrated.**
- **No new source, world, methodology, AI capability, score or significance ranking.**
- `homepage_presentation_v1.0` untouched; communication eligibility is specified as a **separate, strictly narrower** contract.
- **No secrets read, printed or exposed.** The database was queried for row counts only.
- **Nothing committed. Nothing pushed.**
