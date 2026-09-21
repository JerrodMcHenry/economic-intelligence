# Structured Intelligence Layer

**Increment #39.** The bridge between MacroChipz's canonical economic engine and its consumer surfaces.

```
SOURCE DATA → DETERMINISTIC ENGINE → STRUCTURED INTELLIGENCE → PRESENTATION SURFACES
```

One canonical representation of what MacroChipz knows, so that every surface renders the same account of reality instead of each re-deriving it from domain results.

---

## 1. Purpose and non-goals

**Purpose.** Before #39, a surface wanting to show "what changed" had to reach into monitor results, what-changed comparators and release-processing rows and decide for itself what mattered. Two surfaces doing that independently will eventually disagree, and on a product whose differentiator is that its claims are checkable, disagreeing with yourself is expensive.

**A Structured Intelligence Object is not:** an LLM summary · a database row copied into JSON · a chart config · a UI card · a CMS entry · a replacement for canonical domain models · a generic wrapper over every API response.

**It is:** a meaningful, deterministic, evidence-backed thing MacroChipz knows about the economy.

**Explicit non-goals for v1:** Radar findings · forecasts · generative interpretation · significance scoring · content generation · notifications · presentation.

---

## 2. The v1 taxonomy, and how it was chosen

The taxonomy was derived from what the engine **actually knows**, verified against the live database rather than assumed from the plan.

| Type | Basis | Source | Count in dev DB |
|---|---|---|---|
| `RELEASE_PROCESSED` | SOURCE_FACT | `release_check_runs` + `release_occurrences` | 3 |
| `OBSERVATION_CHANGE` | SOURCE_FACT | `release_observation_updates` | 358 |
| `ANALYSIS_CHANGE` | METHODOLOGY_DERIVED | `release_analysis_updates` | 1,532 |
| `RATES_MOVEMENT` | METHODOLOGY_DERIVED | `rates_v1.0` over persisted Treasury observations | 6 |

### 2.1 Two findings that changed the plan

The #39 brief suggested a `STATE_CHANGE` type. **There are zero `STATE_CHANGED` rows in the database.** Every persisted analysis update is `CONFIRMATION_CHANGED` (44) or `AVAILABILITY_RESTORED` (1,488). A `STATE_CHANGE` type would have been a well-designed model with no data behind it.

So the variant is `ANALYSIS_CHANGE`, carrying `event_type` as a typed field — which is also what the Product Constitution §12 needs, since it requires state changes and metric drifts to be **visually distinct**.

**And 97% of those rows record a single bootstrap event** in which everything became computable at once. Presenting that as economic intelligence would be exactly the manufactured activity the Constitution forbids. Hence `change_class`:

| `change_class` | Meaning | Event types |
|---|---|---|
| `ECONOMIC` | The economy did something | `STATE_CHANGED`, `METRIC_CHANGED`, `CONFIRMATION_CHANGED` |
| `COVERAGE` | **MacroChipz's own data coverage** changed | `AVAILABILITY_LOST`, `AVAILABILITY_RESTORED` |

A deterministic, documented, interpretable classification — not a judgement. A surface filters on it; presentation never has to guess.

---

## 3. Common envelope

Every object carries: `id` · `type` · `world` · `concepts[]` · `effective_period` · `recorded_at` · `published_at` · `knowledge_basis` · `basis` · `methodology` · `evidence[]` · `relations[]` · `limitations[]` · `contract_version`.

**`limitations` is required, not optional.** Optional fields get omitted, and this is where the honesty lives.

**Not a god object.** Four variants, each with a small typed payload (≤12 fields, ≤2 optional — enforced by test). A consumer switches on `type` and gets a payload where every field means something. There is no model here with thirty nullable columns.

---

## 4. Variant payloads

- **`ReleaseProcessedPayload`** — release name, provider, provider release id, scheduled date, status, and counts of observation changes (total / new / revised).
- **`ObservationChangePayload`** — `change_type` (NEW | REVISED), previous value, new value, delta, observation date, provider, provider series id, title, units.
- **`AnalysisChangePayload`** — component, event type, `change_class`, field, previous/current value, delta, evaluation period.
- **`RatesMovementPayload`** — series title, latest value, session-counted changes, historical percentile ranks, observation count.

---

## 5. Stable identity

Derived from **semantic facts**, never from a database id (the object is not stored), a per-request UUID (it would change every read), UI position, or prose (a wording change must not mint a new object).

```
release:{provider}:{provider_release_id}:{scheduled_date}
observation:{concept_id}:{observation_date}:{detected_at}
analysis:{methodology_id}:{component}:{field}:{evaluation_period}:{event_type}
rates:{concept_id}:{as_of_date}
```

Readable, and deliberately **not a hash of the whole object** — a hash would change whenever any field changed, including one that does not affect what the object *is*.

**Stability rules:**

- **A value correction does not mutate an object.** A revision produces a *new* `OBSERVATION_CHANGE` with its own detection time. Two detections at two times are genuinely two events.
- **A methodology version change *does* change the id** for methodology-derived objects — a conclusion under a different methodology is a different conclusion. This is why `methodology_id` is an identity dimension for `ANALYSIS_CHANGE` and absent from source-fact ids.
- **A provider migration does *not* change the id.** Ids key on concept identity (#38), never a provider series identifier. An object about core PCE stays the same object when its source moves from FRED to BEA.

**Collision rules:** within a type, the listed dimensions are jointly unique. Colons separate dimensions, so a dimension containing a colon is **rejected** rather than silently producing a colliding id — a guard that fired immediately in development, because ISO-8601 timestamps contain colons. Timestamps are therefore encoded compactly (`20260919T184627419986Z`).

---

## 6. Time model

Four distinct concepts, never conflated:

| Field | Meaning |
|---|---|
| `effective_period` | The economic period this is **about** |
| `recorded_at` | When **MacroChipz** detected or recorded it — always a real system time |
| `published_at` | When the **provider** published it |
| `knowledge_basis` | `OBSERVED` (genuinely recorded at `recorded_at`) or `BACKFILLED` (reconstructed) |

**`published_at` is almost always `None`, and that is the honest answer rather than a gap.** The release calendar carries a scheduled *date*, and this project's own FRED client documents that a release date is not proof data was published. **`created_at` is never substituted for it.**

`knowledge_basis` is never inferred and never defaulted. It is what stops backfilled history masquerading as knowledge MacroChipz actually had — the constraint #35 identified (1,072 of 1,072 observation versions are backfilled) made structural.

---

## 7. Evidence and provenance

`EvidenceRef` reuses Increment #38's identity triple **unchanged**: `concept_id` (source-neutral), `provider` (who actually supplied it), `provider_series_id` (their own identifier), plus observation date and value.

Read from the **stored series row**, never from a module constant — so a provider migration cannot make an old object's evidence lie (ADR-034, Invariant D).

**No competing evidence system was created.** This is a reference to canonical evidence, not a copy of source prose, and presentation code can never invent one.

**One known limitation, recorded on the objects themselves:** Treasury observations are stored under MacroChipz's own series identifiers, so `provider_series_id` for rates is the stored identifier rather than Treasury's XML field name. That field lives in `observation_provenance.source_series_field`; see [`economic-concept-identity.md`](economic-concept-identity.md) §6.

---

## 8. Methodology semantics

`basis` is machine-readable and load-bearing:

- **`SOURCE_FACT`** → `methodology is None`. A release arriving is not a conclusion about the economy. Stamping a methodology id here would claim one was reached.
- **`METHODOLOGY_DERIVED`** → `methodology` carries the actual frozen version (`inflation_v1.0`, `labor_v1.0`, `rates_v1.0`).

Asserted by test at both the contract level and over real data.

---

## 9. Concept identity and worlds

`concepts[]` holds **source-neutral concept ids** (#38), never provider identifiers.

`world` is derived from **domain semantics only** — the methodology that produced the conclusion, or the concepts of the observations that changed. Never inferred from a provider identifier: `labor_v1.0` is the jobs world because of what it measures, not because FRED happens to publish its inputs.

**A release whose world cannot be established from either is omitted rather than assigned one.**

---

## 10. Ordering — and why there is no significance score

**There is deliberately no importance score and no relevance ranking.**

Ordering is `effective_period DESC, recorded_at DESC, id ASC` — time, with the id as a total tiebreak so pagination cannot shift items between pages.

THE LEDE (#42) will need to pick one object. The interpretable primitives for that already exist as named facts a surface can filter on: `type`, `change_class`, `event_type`, `basis`, and the magnitude in each payload. **What does not exist is a deterministic definition of "important" that the engine could defend** — `rates_v1.0` defines no notability threshold, and inventing one here would smuggle a subjective judgement into a canonical object.

Ranking is therefore **deferred**, per §10 of the #39 brief, rather than fabricated. When a methodology publishes a threshold — BLS's own published confidence intervals are the obvious candidate — significance becomes a *derived, cited* fact and can join the contract honestly.

---

## 11. Persistence decision: **generate on read**

Nothing is persisted. Every object is reconstructed from canonical stored rows on each read.

**Why this is correct here, evaluated against each criterion:**

| Criterion | Finding |
|---|---|
| **Reproducibility** | Every input is already persisted — check runs, observation updates, analysis updates, observations, provenance. Two builds over unchanged data are byte-identical (tested). |
| **Stable URLs** | Ids derive from semantic facts, so a permanent URL resolves without a row to hold it. **A future need for permanent URLs does not by itself require a table.** |
| **Point-in-time fidelity** | Nothing is lost: `observation_versions` holds system-time history and `recorded_monitor_results` holds what each methodology concluded and when. Reconstruction does not lose what MacroChipz knew. |
| **Revisions** | `release_observation_updates` already records each detection with its own timestamp, so revisions are events, not mutations. |
| **Deduplication** | Deterministic ids make duplicates impossible by construction. |
| **Notifications** | #46 needs triggers, which read the same canonical rows. |
| **Performance** | Batched reads, no N+1, bounded output. Cheap enough that a second store would be complexity without benefit. |
| **Drift** | **The decisive one.** A stored projection can disagree with the facts it claims. A generated one cannot. |

**Trigger to revisit:** if generation cost becomes material at collection scale, or if an object ever needs to record something *not* derivable from canonical data — a human correction, an editorial decision — persistence becomes necessary and should be introduced then, with justification, idempotent writes and versioning.

---

## 12. Generation architecture

```
canonical stored rows
        ↓
ReleaseProcessingReadRepository / RatesMonitorService
        ↓
IntelligenceBuilder          ← the ONE place objects are constructed
        ↓
IntelligenceService          ← filtering, bounding, lookup
        ↓
app/api/intelligence.py      ← transport only
```

The builder **may not**: call a model, call an upstream provider, infer a fact the data does not contain, fabricate a timestamp or provenance, or mutate canonical data. All guarded structurally.

---

## 13. API

| Endpoint | Behaviour |
|---|---|
| `GET /api/v1/intelligence` | Bounded, deterministically ordered page. Optional `world` and `type` filters. `limit` capped at 100 **twice** — by the route signature and again in the service. |
| `GET /api/v1/intelligence/{id}` | One object by stable id. 404 for both unknown and malformed ids, deliberately indistinguishable. |

Read-only and database-only. **An intelligence read cannot fail because FRED or Treasury is down, because it never reaches them.**

---

## 14. Relationships

Minimal and typed: `CONCERNS_CONCEPT`, `PART_OF_RELEASE`, `AFFECTS_WORLD`, `DERIVED_FROM_OBSERVATION`.

Not a graph database and not an ontology. It exists so a future surface can answer *"what should I look at next?"* without scraping prose or re-deriving domain relationships.

---

## 15. Future consumer surfaces

What Changed (#42) · THE LEDE (#42) · world pages (#41) · Revision Intelligence (#43) · permanent shareable pages (#40) · rabbit-hole navigation (#44) · Follow/alerts (#46) · the Brief · content assistance · Analyst context · Radar findings (post-launch).

**On the Analyst:** #33 was not rewritten. Structured Intelligence may eventually become an additional safe context source for it. The dependency runs one way only — the Analyst may consume intelligence; intelligence must never depend on the Analyst, or a deterministic layer would depend on a probabilistic one. Guarded.

---

## 16. Limitations

- **No `REVISED` data exists yet.** The contract represents revisions fully and tests cover them, but all 358 recorded observation changes are `NEW` — no revision event has ever been captured. A fact about how young the pipeline is, not a gap in the model.
- **No `STATE_CHANGED` data exists yet**, so the economically most interesting `ANALYSIS_CHANGE` class is currently only 44 `CONFIRMATION_CHANGED` rows.
- **97% of analysis changes are `COVERAGE`**, from one bootstrap run. Surfaces should filter on `change_class`.
- **No significance ranking** (§10).
- **Rates carries no notability threshold** and says so in its own `limitations`.
- **Treasury `provider_series_id` is the stored identifier**, not Treasury's field name (§7).
- **Housing, consumer and growth worlds do not exist**, deliberately not pre-declared.

---

## Visual evidence (Increment #40C)

**Visual evidence is part of the intelligence object's evidence contract, not a frontend side-channel into economic data.**

That sentence is the whole rule. A chart assembled from a second query is a second account of reality — and it is the one users believe, because it is the one they can see. So the points a surface draws travel *inside* the object, from the same canonical service, under the same methodology, in the same read as every number printed beside them.

### The contract

```
TimeSeriesVisualEvidence
  kind: "TIME_SERIES"
  concept_id        source-neutral concept identity (#38), never a provider series id
  unit              canonical unit, e.g. "Percent"
  requested_sessions  how many published sessions were asked for
  available_sessions  how many actually exist  (== len(points))
  points[]          { observation_date, value }, ascending, ending at effective_period
```

Carried as `RatesMovementPayload.visual_evidence`, **optional**.

### What it deliberately does not carry

No colour, no width, no height, no axis configuration, no tick counts, no component options, no theme. The backend supplies economic evidence; the frontend decides how to draw it. `tests/test_visual_evidence_contract.py` asserts that none of those keys can appear.

### Why the version was not bumped

`INTELLIGENCE_CONTRACT_VERSION` is documented as *"bumped when a breaking change is made"*. An optional field added to a payload is not breaking: a consumer written against the original `intelligence_v1` parses every object unchanged. Bumping would signal a break that did not happen, so the version stays `intelligence_v1` and the additive change is recorded here instead.

### Where the points come from

`RatesService.get_recent_observations()` → `recent_session_observations()` in `app/domain/rates.py`. Selection only: the last N **usable** observations at or before the effective date, ascending. It reuses `usable_observations`, the same rule every `rates_v1.0` change window counts by, so a drawn series and a computed change read the same population.

`IntelligenceBuilder.VISUAL_EVIDENCE_SESSIONS = 63` — already a `rates_v1.0` comparison window, roughly three months of trading, bounded so the payload cannot grow with the database. It is never called "3 months": it is a session count, and the calendar span varies.

### Honesty rules, enforced by test

- A date the provider published no value for is **absent** — never interpolated, carried forward or zero-filled.
- `available_sessions` may be less than `requested_sessions`; that is a fact about the record and is reported, not padded.
- No usable history → the field is `None`, not an empty chart.
- Nothing after the object's effective date ever appears.

### One subtlety, deliberate

A series of N published sessions is **not** the same span as `rates_v1.0`'s N-session *change*: a 63-session change compares the latest observation with the one 63 sessions before it, spanning 64 observations. So the first charted point is one session later than the 63-session change's `from_date`, and subtracting the chart's endpoints will not reproduce that change exactly. The two answer different questions. A surface should therefore caption the series with its own real date range rather than implying it matches a change window — which is what the permanent page does.

### No provider call on read

Generate-on-read never reaches the network. Guarded **statically**, by parsing imports (`TestNoProviderDependency`): every module on the RATES_MOVEMENT read path — domain, service, builder, repository, contracts — is asserted to import no `httpx`, `requests`, `aiohttp`, `app.clients.*` or model SDK. A module that cannot import a client cannot call one, on any path, including ones no test exercises.
