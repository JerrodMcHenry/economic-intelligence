# MacroChipz 2.0 — Architecture

**Increment #36.** Specification only. No production code, no behaviour change, no deployment, nothing committed.

Companion to [`docs/product/macrochipz-product-constitution-v1.md`](../product/macrochipz-product-constitution-v1.md), which defines *what* MacroChipz 2.0 promises. This document defines *how the system delivers it*.

**Scope discipline.** This is a high-level architecture, not a rewrite plan. It describes the target shape, names the additions, and — deliberately — records how much of the existing system is unchanged. [`current-architecture.md`](current-architecture.md) remains the description of the system as it exists; it is superseded only as each increment lands.

**Relationship to ADRs.** Existing ADRs remain binding. Where 2.0 requires a decision to change, this document names the ADR and proposes a successor in §29. It does not silently override one.

---

## 1. Existing System Baseline

Audited 2026-09-20. This is what exists, not what is planned.

### 1.1 Backend

- **FastAPI + SQLAlchemy 2.0 + Alembic + PostgreSQL.** Strict layering: pure `app/domain/*` (AST-guarded — no FastAPI, HTTP, provider clients, SQLAlchemy, sessions, env or logging; domain modules may not import each other) → `app/services/*` → `app/repositories/*` → `app/api/*`, with Pydantic contracts in `app/models/*`.
- **26 HTTP endpoints**, all under `/api/v1` except `/health` and `/readiness`. Three are operator-guarded (`POST /series/{id}/sync`, `/releases/sync`, `/rates/sync`) via `X-Operator-Token` with `secrets.compare_digest`, failing closed in production. One is rate-limited (`POST /analyst/explain`). One is conditionally mounted and never in production (`POST /ai/query`).
- **13 tables**, 10 migrations. `economic_series`, `economic_observations`, `economic_releases`, `release_occurrences`, `release_series_mappings`, `release_check_runs`, `release_analysis_updates`, `release_observation_updates`, `maintenance_sweeps`, `recorded_monitor_results`, `observation_provenance`, `rates_ingestion_runs`, `observation_versions`.
- **Five frozen methodologies:** `inflation_v1.0`, `labor_v1.0`, `rates_v1.0`, `inflation_what_changed_v1.0`, `labor_what_changed_v1.0`. Each has a published methodology document and a version string carried in its response contract.
- **Two provider clients.** `FREDClient` (`api.stlouisfed.org`) supplies the four inflation series (`PCEPILFE`, `CPILFESL`, `PCEPI`, `CPIAUCSL`), the two labor series (`PAYEMS`, `UNRATE`), series search, **and the release calendar exclusively**. `TreasuryClient` (`home.treasury.gov` XML, unauthenticated, allow-listed datasets, 1 MiB response cap) supplies all six rates series under MacroChipz-owned identifiers (`UST_NOMINAL_10Y`, not `DGS10`).
- **Append-only system-time versioning** (`observation_versions`, half-open `[recorded_from, recorded_to)`) plus **deterministic replay** (`ReplayService`), with as-of reads and NEW/REVISED/UNCHANGED classification.
- **Bounded Analyst** (#33): one model call, no tools, no session, server-built `AnalystContextPacket`, validated evidence references, prompt `macrochipz_analyst_v1.1`, evaluated 13/15 on a frozen 15-case suite.
- **Production hardening** (#34): `ENVIRONMENT`-derived production mode, request-id correlation, JSON logging, body-size limit, four security headers, CORS allowlist, startup misconfiguration reporting.
- **1,915 test definitions** across 91 files, including an AST guard on domain purity.

### 1.2 Frontend

- **React 19 + Vite 8 + TypeScript + Tailwind v4 + Vitest.** Client-only SPA, `react-router-dom` v7, seven routes under one `AppShell` layout.
- **Routes:** `/` (static), `/overview`, `/inflation`, `/labor`, `/rates`, `/releases`, `*`.
- **Design system** in `src/styles/globals.css` — `--mc-*` tokens declared twice (light at `:root`, dark at `:root[data-theme="dark"]`, values chosen independently rather than inverted), four **deliberately disjoint** families: surfaces/text/borders, brand/interaction, `feedback-*` (12 tokens, generic UI outcomes), `state-*` (15 tokens, economic classification). **The separation is machine-enforced** by `src/design/stateTone.test.ts`, which fails if a state token is ever defined in terms of a feedback token. Seven typography utilities; `--container-app: 76rem`.
- **34 exported `Explanation` constants** across five content modules (`inflation`, `labor`, `rates`, `releases`, `processingStatus`), plus 8 state-lookup functions. Curated static TypeScript, never AI-generated, never a source of canonical classification.
- **No charting library.** One hand-written inline SVG chart (`YieldCurveChart`), with an equivalent `<table>` published beneath it. The rejection of a library is documented in the component itself.
  - **Corrected by #36A:** earlier drafts of this document and the #35 research described the SVG as `aria-hidden`. **It is not.** The component's own doc comment says so, but the code uses `role="img"` with an `aria-label`, *plus* an `sr-only` `<figcaption>`, *plus* the table — redundant rather than clean. It also carries `preserveAspectRatio="none"`, which squashes the chart roughly 37% horizontally at 390px. Both are live defects; see ADR-041.
- **51 test files, 821+ test declarations**, including **10 architectural guard tests** (`no-economic-logic`, `no-rates-calculation`, `no-analyst-derivation`, `no-history-derivation`, `no-relate-inference`, `no-state-duration-reconstruction`, and others) that fail if the frontend ever derives an economic conclusion.
- **Per-section independent loading/error branches** — one failing section does not blank a page.

### 1.3 What is missing entirely

No Open Graph or Twitter card metadata. No canonical URLs. No `sitemap.xml`. No `robots.txt`. No analytics. No email capture. No share affordance. No server-rendered HTML. No Housing, Consumer or Growth data. Historical depth is 59–60 monthly observations per series.

**Corrected by #36A:** there *is* a meta description — one static, site-wide string in `index.html`, alongside the single `<title>`. The gap is **per-route** metadata, not metadata entirely. #35 and earlier drafts overstated this.

---

## 2. MacroChipz 2.0 Architectural Goals

| # | Goal | Why |
|---|---|---|
| **G1** | **One canonical intelligence representation feeding many surfaces** | Homepage, worlds, What Changed, revisions, Radar, Brief, alerts, share cards and Analyst context must be renderings of the same object, or they will drift and contradict each other. |
| **G2** | **Provider independence for series, calendar and identity** | FRED cannot be the spine of a public commercial product. The abstraction must exist before the migration, and the migration must be behaviour-preserving. |
| **G3** | **Server-visible HTML for anything shareable or indexable** | Crawlers and social scrapers do not execute client-side JavaScript. Sharing is architectural (Constitution §23), and a client-only SPA structurally cannot deliver it. |
| **G4** | **Honest absence as a first-class system state** | "Nothing significant changed" must be a value the system produces and the UI renders, not an empty collection the UI improvises around. |
| **G5** | **Knowledge basis carried end to end** | `OBSERVED` vs `BACKFILLED` must travel from storage to pixel. If it can be lost anywhere in the pipeline, the product's central honesty claim is unenforceable. |
| **G6** | **Significance determined in the engine, never in the view** | Every surfaced item must carry the rule and threshold that surfaced it. Presentation cannot decide what matters. |
| **G7** | **Measurability** | Privacy-conscious instrumentation of the behavioural loop, absent today. |
| **G8** | **Preserve the existing engine and its guarantees** | The consumer experience changes. Determinism, provenance, layering and the frozen methodologies do not. |

---

## 3. Architectural Invariants

These hold across every 2.0 increment. Violating one is a defect, not a trade-off.

1. **Domain purity.** `app/domain/*` stays pure and mutually independent. AST-guarded.
2. **Frozen methodologies stay frozen.** A methodology changes only by a new version string and a new published document. No silent edits.
3. **The frontend derives no economic conclusion.** The 10 architectural guard tests extend to every new surface.
4. **Evidence accompanies every claim**, structurally — not by convention.
5. **AI never produces a canonical fact, calculation, state, evidence item, provenance record or causal claim.**
6. **The core product functions with the Analyst unavailable.**
7. **Reads never trigger ingestion** (ADR-016). No user request causes provider traffic.
8. **Writes are operator-guarded and fail closed in production** (ADR-033).
9. **Observation versioning is append-only.** No version row is ever updated or deleted.
10. **Knowledge basis is never inferred or defaulted.** Every version row states whether it was observed or backfilled, and that value propagates unchanged.
11. **Canonical series identifiers are MacroChipz-owned**, never provider-native. (Established for Rates; §5.3 extends it.)
12. **Every published intelligence object is recomputable** from canonical facts + methodology version + data vintage. If it cannot be recomputed, it cannot be published.
13. **Significance thresholds are declared, versioned, and carried on the object.**
14. **No surface manufactures activity.** Absence is represented, not filled.

---

## 4. Deterministic / Probabilistic / Generative Boundaries

```
  ┌─────────────────────────────────────────────────────────────┐
  │  SOURCE DATA        BLS · BEA · Census · Treasury · Fed · DOL │
  └───────────────────────────────┬─────────────────────────────┘
                                  ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  DETERMINISTIC / CANONICAL                                   │
  │  ingestion · versioning · methodologies · change detection   │
  │  revisions · evidence · provenance                           │
  │  → reproducible, versioned, testable, traceable              │
  └───────────────────────────────┬─────────────────────────────┘
                                  ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  STRUCTURED INTELLIGENCE OBJECT  (§11)                       │
  │  the single canonical representation — a projection, never   │
  │  an independent source of truth                              │
  └───┬─────────────────┬───────────────────┬───────────────────┘
      ▼                 ▼                   ▼
  ┌────────┐  ┌──────────────────┐  ┌──────────────────────────┐
  │ SURFACES│  │ PROBABILISTIC    │  │ GENERATIVE / INTERPRETIVE│
  │ web ·   │  │ Radar detectors  │  │ Analyst · content drafts │
  │ brief · │  │ → versioned,     │  │ → explains only;         │
  │ share · │  │   evaluated,     │  │   never canonical;       │
  │ alerts  │  │   optional       │  │   never required         │
  └────────┘  └──────────────────┘  └──────────────────────────┘
```

**The three tiers, with their obligations:**

| Tier | May produce | Must carry | May the system depend on it? |
|---|---|---|---|
| **Deterministic** | Facts, transformations, states, change detection, revisions, evidence, provenance | Methodology version, data vintage, evidence | **Yes — it is the system** |
| **Probabilistic** | Anomaly/divergence findings | Detector version, significance treatment, backtest record, uncertainty, vintage stamp | **No** — never required for correctness, reproducibility, availability or integrity |
| **Generative** | Explanations, summaries, drafts | Visible interpretation label, evidence references validated against canonical data | **No** — never required for availability |

**Prohibited flow, stated so it can be tested against:**

```
RAW DATA → LLM → "what the economy means"
```

**The generative tier's hard boundary** (ADR-032, unchanged): it may not create canonical facts, perform authoritative calculations, determine states, fabricate provenance, modify evidence, silently fill missing data, invent causal explanations, control permissions, or become required for availability.

---

## 5. Data Source Strategy

### 5.1 Current dependency, precisely

**FRED supplies three distinct things**, and they carry different migration difficulty:

| What | Where | Difficulty |
|---|---|---|
| **Six monthly series** — `PCEPILFE`, `CPILFESL`, `PCEPI`, `CPIAUCSL` (BEA/BLS origin), `PAYEMS`, `UNRATE` (BLS origin) | `app/services/economic_data.py`, `app/services/release_processing.py` | **Moderate.** All originate at BLS or BEA, both public domain at source, both with free APIs. |
| **The release calendar** — `get_release_dates()` for six seeded releases carrying `provider="FRED"` and numeric FRED release IDs | `app/services/releases.py` | **Harder.** Requires provider-neutral release identity and replacing a single uniform API with BLS iCal + BEA JSON + a Census scraper. ADR-020 explicitly chose no provider abstraction here. |
| **Series search/discovery** | `app/services/discovery.py` | **Trivial — by deletion.** Serves no 2.0 user need. |

**Treasury supplies all six rates series** under MacroChipz-owned identifiers and is already fully independent. **No migration needed, and it is the pattern to copy.**

### 5.2 Target sources

| Domain | Source | Auth | Licensing |
|---|---|---|---|
| CPI, payrolls, unemployment | **BLS API v2** | Free key; 500 queries/day, 50 series/query | Public domain; citation + access-date + "cannot vouch" disclaimer |
| PCE, personal income, GDP | **BEA API** | Free UserID; 100 req/min, 100 MB/min | Verbatim attribution string mandatory; commercial use permitted |
| Retail sales, housing starts, permits | **Census API** | Free key | Verbatim attribution string mandatory |
| Treasury yields | **fiscaldata + home.treasury.gov XML** | **None** | Expressly permits commercial redistribution; no attribution required |
| H.15 and other Board series (if needed) | **Fed Board XML** | None | Public domain. **Note: the Data Download Program is being retired and redirects to FRED — ingest from the XML release and keep a local archive.** |
| Initial claims | **DOL PDF** | None | Public domain. `oui.doleta.gov` returned a live database error on 2026-09-20 — never a single point of failure. |
| **Mortgage rates** | **None available** | — | Freddie Mac PMMS prohibits commercial redistribution, derived products and automated access simultaneously. **Treasury 10Y is used as a labelled proxy.** |

### 5.3 The identifier problem

Rates already does this correctly: `UST_NOMINAL_10Y`, deliberately not `DGS10`, so a Treasury observation can never be confused with a FRED one.

**Inflation and Labor do not.** `PCEPILFE`, `CPILFESL`, `PCEPI`, `CPIAUCSL`, `PAYEMS` and `UNRATE` are FRED-shaped identifiers. BLS's own identifier for payrolls is `CES0000000001`, not `PAYEMS`. **Migrating the source without migrating the identifier would leave FRED's naming embedded in a system that no longer uses FRED** — a latent provenance lie.

**Therefore:** the migration introduces MacroChipz-owned canonical identifiers for all monthly series, with a persisted mapping from each provider's native identifier.

**Implemented in Increment #38** — see [`economic-concept-identity.md`](economic-concept-identity.md) and ADR-034. Twelve concepts and twelve bindings are registered; `economic_series.concept_id` records which concept each stored series supplies; and evidence now carries `concept_id`, `provider` and `series_id`, all read from the persisted row rather than stamped from a module constant.

Two details differ from the sketch above. The concept registry and the bindings are **code-defined, not data** — frozen methodologies depend on concept identity, so it must be type-checked and versioned with the code that uses it, while `observation_provenance` already records which retrieval produced each stored value. And a second provider for the same concept is an **inactive binding plus a separate `economic_series` row**, not an insert into a mapping table: that is what lets both providers be ingested and compared before a one-line cutover, with historical rows never rewritten.

### 5.4 Non-negotiable ingestion rules

1. **Re-pull full history; never append, for any seasonally adjusted series.** CES recomputes its seasonal adjustment concurrently every month, and CPI SA is revised five years back annually. **A determinism-claiming product that silently drifts every January is worse than one that never made the claim.** This is the highest-risk correctness requirement in the migration.
2. **Label derived figures as MacroChipz calculations**, never as source-agency published figures — a BEA and Census licensing requirement that is also correct product behaviour.
3. **Snapshot every release at publication.** The only unencumbered route to genuine point-in-time history, and it compounds from the day it starts.
4. **Attribution is data, carried on provenance**, not a hardcoded footer string. The current `AppShell` footer hardcodes FRED attribution and must become source-derived.

---

## 6. Source Abstraction

**Introduce a `SeriesSource` protocol; do not build a provider framework.**

```
SeriesSource (protocol)
  ├── fetch_series_metadata(canonical_series_id) -> SeriesMetadata
  └── fetch_observations(canonical_series_id, since?) -> list[SourceObservation]

ReleaseScheduleSource (protocol)
  └── fetch_scheduled_dates(canonical_release_id) -> list[ScheduledDate]
```

Adapters: `BLSSource`, `BEASource`, `CensusSource`, `TreasurySource`, and — during migration only — `FREDSource`.

**Design rules:**

1. **The protocol is the narrowest thing that works.** Two methods. Provider-specific concerns (BLS's 20-year window, BEA's `Retry-After`, Census's absent calendar) live inside their adapter.
2. **Adapters return MacroChipz-shaped objects**, never provider-shaped ones. The existing `Observation` contract in `app/models/series.py` already establishes this pattern.
3. **Every adapter emits a `ProvenanceRecord`** — provider, dataset, retrieval timestamp, attribution string, units. `observation_provenance` already exists and already does this for Treasury.
4. **Services depend on the protocol, never on a concrete client.** Today `ReleaseSyncService` requires a `FREDClient` in its constructor; that becomes a `ReleaseScheduleSource`.
5. **Adapters are independently testable against recorded fixtures**, with no network in the test suite.
6. **Failure is contained per source.** `rates_ingestion.py` already proves the pattern: one dataset failing does not discard the other's rows, and the run records `PARTIAL_FAILURE` naming what failed. Generalise it.
7. **No adapter is required for reads.** The read path has no source client at all and is structurally incapable of calling upstream — an existing property worth preserving explicitly.

---

## 7. Ingestion

Unchanged in shape; extended in sources.

```
operator / scheduled job
   → SeriesSource.fetch_observations()
   → ObservationVersionWriter.apply()      # canonical write + version, together
   → provenance recorded
   → release check run recorded
   → affected methodologies recomputed
   → recorded_monitor_results appended
   → intelligence objects projected (§11)
```

**Rules, existing and new:**

- **Reads never ingest** (ADR-016, unchanged).
- **Writes are operator-guarded and fail closed in production** (ADR-033, unchanged).
- **Canonical write and version write happen together**, in one transaction — `ObservationVersionWriter.apply()` already enforces this and must remain the only path.
- **New:** every ingestion run records the **data vintage** it produced, so any downstream object can name the vintage it was computed from (§17, §15).
- **New:** seasonally adjusted series re-pull their full published history on every run; the diff against stored versions produces the revision record. **This is how revisions get detected at all** — the current pipeline's zero captured REVISED events is partly a consequence of not re-pulling.

---

## 8. Observation Storage

Unchanged. `economic_series` + `economic_observations` hold current canonical values; `observation_provenance` holds where each came from.

**Two additions:**

1. **Canonical identifier mapping** (§5.3) — a table mapping MacroChipz canonical series IDs to per-provider native identifiers, with an effective period so a provider change is auditable.
2. **Deep history.** Current depth is 59–60 monthly observations. Any percentile, historical-extreme or "unusual versus its own history" claim is dishonest on 60 points, and **Radar is blocked on this**. BLS carries CPI to 1913 and CES to 1939. Re-ingestion is cheap and unlocks a class of claims.

---

## 9. Versioning / Revisions

The existing `observation_versions` design is sound and is the spine of both Revision Intelligence and the Time Machine. Append-only, half-open `[recorded_from, recorded_to)` system-time intervals, NEW/REVISED/UNCHANGED classification, as-of reads.

**The honesty requirement, made architectural.** Today all 1,072 version rows are `is_backfilled = true`; zero are genuinely observed; zero REVISED events have ever been captured.

**`knowledge_basis` is promoted to a first-class, propagated field:**

| Value | Meaning | May be presented as |
|---|---|---|
| `OBSERVED` | MacroChipz recorded this value at this system time, prospectively | "What MacroChipz knew on [date]" |
| `BACKFILLED` | Reconstructed from a later state or a provider vintage | "Reconstructed from provider data" — **never** as MacroChipz knowledge |

**Rules:**

1. **It is never inferred, never defaulted, never dropped in a projection.** Every intelligence object carrying a historical claim carries the knowledge basis of every input it rests on.
2. **A mixed-basis object takes the weakest basis of its inputs.** One backfilled input makes the whole claim a reconstruction.
3. **The UI distinguishes them visually**, not in a footnote.
4. **A "what we knew then" claim with any `BACKFILLED` input is refused, not degraded.** #31/#32 already refuse rather than fake; that behaviour becomes a system-wide rule.

**Four time concepts, never conflated** — observation date · publication date · system recorded time (`recorded_from`) · provider revision time. These are distinct columns with distinct meanings, and no code path may substitute one for another.

---

## 10. Methodology Layer

Unchanged and frozen. Five methodologies, each with a published document, a version string carried in its response contract, and golden-vector binding.

**Extensions for 2.0:**

1. **New worlds require new methodologies** — Housing, Consumer, Growth each need a defensible state methodology before their tile shows a state. Until then the tile shows data and no state (Constitution §11). **A world may ship without a methodology; it may not ship with an invented one.**
2. **Significance thresholds become declared, versioned methodology artifacts** — for example, the BLS 1-month payroll confidence interval of ±122,281, or the ~118,000 revision threshold at 90%. Today these live in analysis; they become published, versioned inputs that objects can cite.
3. **A `revision_significance_v1.0` methodology** is required for Revision Intelligence: the binomial sign test on revision direction, plus the published-distribution comparison for magnitude.
4. **Methodology version is part of every cache key** (§23), so a methodology change invalidates correctly rather than serving a stale conclusion under a new version string.

---

## 11. Structured Intelligence Layer

**The central addition of 2.0, and the one most likely to be built wrong.**

### 11.1 What it is — and what it must never become

An **`IntelligenceObject`** is a *published, addressable, evidence-backed statement about the economy, produced by a named methodology, at a recorded time, from a named data vintage.*

> **It is a projection, never a source of truth.** It is derived from canonical facts plus a methodology version plus a vintage. It is not authored, not edited, and not stored as the primary record of anything. **If it cannot be recomputed from its inputs, it cannot be published** (Invariant 12).

This constraint is the entire design. Without it, the intelligence layer becomes a second canonical store that drifts from the first — the most likely architectural failure available here.

### 11.2 Types

| Type | Produced by | Example |
|---|---|---|
| `STATE` | A monitor methodology | "Core PCE momentum is Cooling" |
| `CHANGE` | A what-changed comparator | "3-month annualised fell from 3.11% to 3.05%" |
| `REVISION` | Revision detection | "August payrolls revised down 41,000" |
| `RELEASE` | Release processing | "CPI for September was published and processed" |
| `RADAR_FINDING` | A registered detector | (post-launch) |
| `CONTEXT` | Historical positioning | "This is the fastest since March 2019" |
| `EXPLAINER` | Curated content bound to live data | "The Fed does not set your mortgage rate" |

### 11.3 Shape

Conceptual, not a schema to implement now.

```
IntelligenceObject
  identity        id · type · world · canonical_url · stable across recomputation
  claim           title · plain_english_summary · magnitude · period
  determination   methodology_id · methodology_version · data_vintage
                  knowledge_basis (OBSERVED | BACKFILLED)
  significance    surfacing_rule · threshold_cleared · significance_rank
                  uncertainty (incl. agency-published CI where one exists)
  facts           observed values · deterministic calculations
                  current_state · previous_state
  revision        original · revised · current · magnitude · direction
  context         historical position · related indicators/releases/explainers
  evidence        evidence_refs → canonical evidence records
  provenance      per-input source · dataset · retrieval time · attribution
  limitations     what this object does NOT establish
  timing          recorded_at · effective_period · as_of
  presentation    share_metadata · og_image_key · content_opportunities
```

### 11.4 The three fields that do the real work

1. **`surfacing_rule` + `threshold_cleared`.** Every object states *why MacroChipz is showing it* and what bar it cleared. **An object that cannot name its surfacing rule is not surfaced.** This makes "never manufacture activity" (Invariant 14) a structural property rather than editorial discipline.
2. **`knowledge_basis`.** §9. Propagated, never inferred.
3. **`limitations`.** What this object does *not* establish. A divergence object states that it is not causal. A revision object states that a routine revision is not news. This is where the product's honesty lives, and it must be a required field — optional fields get omitted.

### 11.5 Consumers

Homepage (THE LEDE selects by `significance_rank`) · world pages · What Changed · Revision Intelligence · Radar · the Brief · alerts · share cards · OG image generation · content drafts · **Analyst context packets**.

**On the Analyst:** `analyst_context_v1` is today built per-surface. It should become a projection of the same `IntelligenceObject`, which removes a class of drift where the Analyst is given a different account of reality than the page it sits on.

### 11.6 Implemented in Increment #39

Built as specified, with one taxonomy change forced by the data and recorded in
[`structured-intelligence.md`](structured-intelligence.md).

The brief and this section both assumed a `STATE_CHANGE` type. **The database contains zero `STATE_CHANGED` rows** — every persisted analysis update is `CONFIRMATION_CHANGED` (44) or `AVAILABILITY_RESTORED` (1,488). The variant is therefore `ANALYSIS_CHANGE`, carrying `event_type` as a typed field, plus a `change_class` separating ECONOMIC from COVERAGE changes — because 97% of those rows record a single bootstrap event in which everything became computable at once, and presenting that as economic intelligence would be the manufactured activity the Constitution forbids.

`surfacing_rule`/`threshold_cleared` were **not** implemented, deliberately. No frozen methodology publishes a notability threshold today, so any rule would have been invented here rather than cited. Ordering is by time with a total tiebreak; the interpretable primitives a surface can filter on (`type`, `change_class`, `basis`, payload magnitudes) are named facts rather than a score. Significance joins the contract when a methodology publishes a threshold to cite.

Persistence: **generate on read**, no new table. Every input is already persisted, and a stored projection can disagree with the facts it claims while a generated one cannot.

### 11.7 Where it lives

`app/services/intelligence/` — a projection service over existing monitor, what-changed, history and release-processing services. **It adds no new economic logic.** Any economics it appears to need belongs in `app/domain/`, behind a versioned methodology.

---

## 12. Evidence / Provenance

Existing model is sound: `InflationMetricEvidence`, `LaborObservationEvidence`, `SourceProvenance`/`DerivedProvenance`, `observation_provenance`.

**2.0 requirements:**

1. **Every `IntelligenceObject` carries evidence references**, resolvable to canonical evidence records. Structural, not conventional.
2. **Evidence is addressable** at `/evidence/{id}` — `noindex`, because it is a verification target, not a landing page (Constitution §34).
3. **Evidence survives sharing.** A shared claim lands on a page where its evidence is one interaction away. This is the difference between MacroChipz and a screenshot.
4. **Derived values keep source and derived provenance separate.** `RateProvenance` already renders two deliberately distinct surfaces; generalise it.
5. **Attribution strings come from provenance data**, per source — required verbatim by BEA and Census, and the current hardcoded FRED footer becomes wrong the moment migration lands.

---

## 13. Economic Worlds

A **world** is a first-class aggregate: a set of canonical series, zero or one state methodology, a release schedule, an explainer set, and declared relationships to other worlds.

| World | Status | Series | State methodology |
|---|---|---|---|
| Inflation | Exists | 4 (BLS/BEA origin) | `inflation_v1.0` |
| Jobs | Exists as "Labor" | 2 (BLS origin) | `labor_v1.0` |
| Rates | Exists | 6 (Treasury) | `rates_v1.0` |
| Housing | **SHIPPED (#45)** | Census permits/starts/completions, national, SA annual rate + NSA monthly. **No `UST_NOMINAL_10Y` proxy** — see below | **None, and none planned** — data only |
| Consumer | Post-launch | Census retail, BEA income | None yet |

**#45 departed from the Housing row above in one respect, deliberately.** This table planned `UST_NOMINAL_10Y` as an "explicitly labelled proxy" for mortgage rates on the Housing page. #45 did not ship a proxy of any kind: a Treasury yield rendered beside permits and starts asserts a relationship MacroChipz has measured nothing about, and "labelled proxy" does not undo what two numbers side by side on one page communicate. The Housing page names what MacroChipz tracks, names what it does not, and links to `/rates` — with no figure. See `housing-world.md` §10.
| Growth | Post-launch | BEA GDP | None yet |

**Rules:**

1. **World membership is configuration, not code.** Adding Consumer should not require a new service module.
2. **A world without a methodology shows data and no state.** Honest and explicitly supported.
3. **Cross-world relationships are declared data** (§16 of the Constitution), typed by kind — mechanical, accounting identity, established causal mechanism, empirical relationship, correlation, contextual. **The type is carried through to the UI**, because "the 10-year Treasury tracks mortgage rates" and "inflation causes rate hikes" are different kinds of claim and must not be rendered identically.

---

## 14. What Changed

Already implemented as `inflation_what_changed_v1.0` and `labor_what_changed_v1.0` — pure comparators over already-canonical results, containing zero domain formula knowledge and deliberately not importing their own domain modules. **This is exactly the right design and it extends unchanged to new worlds.**

**2.0 additions:**

1. **Change events project into `CHANGE` intelligence objects** carrying `surfacing_rule` and `threshold_cleared`.
2. **`STATE_CHANGED` and `METRIC_CHANGED` are ranked and rendered differently.** State changes are rare by construction — deadbands exist precisely to make them rare — while metric drifts are continuous. Ranking them identically trains users to ignore both.
3. **An empty result is a typed value**, not an empty list the UI improvises around (G4).
4. **Significance gating happens in the engine.** A change below its published threshold is retained in the record and **not surfaced**, with the object stating why.
5. **As-of is explicit.** Monitors refresh once per release; the surface states when, so it never implies continuous freshness.

---

## 15. Radar Architecture

**Post-launch. The architecture is specified now so that the evaluation work can begin without redesigning it later.**

### 15.1 Registry, not scanner

```
RadarDetector (registered, versioned, immutable once published)
  hypothesis            the economic reason this relationship should hold
  inputs                canonical series ids
  transformations       declared, versioned
  expected_relationship
  detection_method
  minimum_history
  significance          effect-size + threshold + multiple-testing treatment
  equivalence_test      required for any "while X remains stable" claim
  methodology_version
  limitations
  backtest_record
  evidence_requirements
  explanation_template
```

**The registry is pre-registered and fixed before a run.** If the set of tests can float, no honest significance claim exists — this is the whole reason a scanner is rejected.

### 15.2 Why not a scanner

A 600-test monthly scan at a 2σ bar produces roughly 27 false findings per month under a pure null. On MacroChipz's own series, 2σ yields about one candidate per series every two years. **Broad scanning cannot be made honest by tuning; it must be replaced by a small, motivated registry.**

### 15.3 Hard architectural constraints

1. **Every finding carries a data vintage stamp and must be recomputable from it.** Seasonal factors are re-estimated annually; CES recomputes monthly. Without vintage pinning, last month's finding can silently cease to exist and **Radar's own archive would contradict itself** — fatal on a trust product. *This is the one Radar requirement MacroChipz is uniquely positioned to satisfy, because `observation_versions` and `ReplayService` already exist.*
2. **Significance is series-specific, never global.** A uniform z-threshold across a macro panel is statistically incoherent: monthly CPI headline moves are real signals; monthly payroll moves are not; monthly energy and apparel moves are not. Measurement error varies by an order of magnitude across series.
3. **Divergence requires same-instrument comparison.** Two surveys with different universes and incompatible resolution cannot confirm or contradict each other.
4. **"While X remains stable" requires an equivalence test** on the stable leg. Asserting stability from a failure to detect is not a finding.
5. **Detectors run offline first**, writing to a private evaluation record with no user-facing output, for a meaningful period.
6. **A zero-finding run is a successful run**, recorded as such.
7. **Radar is never required for any other surface to work** (§4).

### 15.4 Placement

`app/domain/radar/` for pure detection primitives (AST-guarded like every other domain module); `app/services/radar/` for orchestration, registry management and evaluation recording. Findings project into `RADAR_FINDING` intelligence objects like anything else.

---

## 16. Calendar / Event Architecture

**The release calendar is currently FRED-exclusive**, with `provider="FRED"` and numeric FRED release IDs seeded by migration `fbbe6b1ab8d9`. ADR-020 deliberately chose no provider abstraction here. **That decision is correct for V1 and must be superseded for 2.0** (§29).

**Target:**

```
CanonicalRelease  (provider-neutral identity, owned by MacroChipz)
   ├── ReleaseScheduleSource bindings (BLS iCal | BEA JSON | Census scraped | manual)
   ├── series mappings (existing release_series_mappings)
   └── occurrences (existing release_occurrences)
```

| Source | Format | Note |
|---|---|---|
| **BLS** | **iCal** (`bls.gov/schedule/news_release/bls.ics`) | All times Eastern |
| **BEA** | **ICS + JSON + RSS** (`apps.bea.gov/API/signup/release_dates.json`) | Best in class |
| **Census** | **HTML/PDF only** | Requires a scraper or a maintained table — budget for it |
| **DOL / Treasury / NY Fed** | None located | Manual, or derived from known fixed cadence |

**Rules:**

1. **Release identity is MacroChipz-owned.** A FRED numeric release ID is a *binding*, not an identity.
2. **`schedule_status` stays computed at response time, never persisted** — existing correct behaviour.
3. **The calendar never shows an event the system cannot process.**
4. **Manual entries are marked as such** and are a first-class, honest source type.
5. **Times carry an explicit timezone.**
6. **Release-date presence is never proof observation data is available** — an existing, important property of the FRED client docstring that must survive the migration.

---

## 17. Point-in-Time / Time Machine

Three stages, gated on genuine accumulated data rather than on engineering readiness.

| Stage | Capability | Architectural requirement | Gate |
|---|---|---|---|
| **1** | Revision comparison — original vs revised vs current, methodology-then vs methodology-now | `observation_versions` + `ReplayService` (**both exist**) | **Day 1** |
| **2** | Genuine point-in-time views | Accumulated `OBSERVED` versions | Time |
| **3** | Interactive cross-world Time Machine | Substantial genuine history | Long-term |

**Rules:**

1. **Stage 1 does not require observed history**, because provider revision data supplies the comparison. This is why it can ship Day 1.
2. **Stage 2 is gated on data, not code.** The code largely exists; the history does not.
3. **Accumulation starts Day 1 regardless of when Stage 2 ships.** Every release captured from now compounds, and it is the cheapest high-value action available.
4. **Refuse rather than fake.** ADR-031 already establishes that point-in-time reads refuse rather than fabricate; this generalises to every historical surface.
5. **Historical vintages come only from sources with clear redistribution rights** — archived agency releases and agencies' own vintage archives. Third-party vintage compilations are excluded absent written permission, regardless of technical convenience.

---

## 18. Analyst Integration

**Unchanged in architecture** (#33, ADR-032). One bounded model call, no tools, no session, server-built context packet, validated evidence references, contained failures, rate-limited, optional.

**Two 2.0 changes, both small:**

1. **Context packets become projections of `IntelligenceObject`** (§11.5), removing a drift class where the Analyst and the page disagree.
2. **Placement becomes contextual** rather than one block per page — attached to the number, state or revision being asked about.

**Unchanged constraints:** never produces a canonical conclusion · never in the hero · core product fully functional when unavailable · every response visibly labelled as interpretation · evidence references validated against canonical data before display.

---

## 19. Content Presentation Layer

```
IntelligenceObject  ──→  renderers  ──→  web · email · script draft · social copy · OG image
```

**The boundary is architectural, not editorial:**

| Canonical (deterministic) | Presentation (may be AI-assisted) |
|---|---|
| What happened; the numbers; the states; significance; evidence | Phrasing; titles; framing; format; which true thing leads |
| **Never AI-generated** | **Never contradicts the object** |

**Rules:**

1. **The content pipeline never determines what happened.** If it needs a model call to know that, the architecture is wrong.
2. **AI drafts from structured facts** and may not introduce a fact, number, state or causal claim absent from the object.
3. **Every published piece references its canonical object id**, so any claim in any channel is traceable back.
4. **Human review before publication** for anything under the MacroChipz name.
5. **No object of sufficient significance → no content.** The content calendar is downstream of the economy.

---

## 20. Sharing

**Architectural, and it is the change that most affects the frontend's shape.**

### 20.1 The structural problem

The frontend is a **client-only SPA**. Crawlers and social scrapers do not execute JavaScript. **A client-only SPA structurally cannot have working share cards or search presence** — this is not an optimisation gap, it is an architectural incompatibility with Constitution §23 and §34.

### 20.2 Required

1. **Server-visible `<head>`** per route: title, description, canonical, Open Graph, Twitter card.
2. **Generated OG images** per shareable object, produced *from the canonical object* so they cannot drift from the page.
3. **Permanent, stable URLs** (Constitution §26).
4. **Evidence reachable after click-through.**
5. **As-of date on every card**, so a card shared months later does not imply currency.

### 20.3 Decided — see ADR-039

**#36A rejected this section's original recommendation** (serving the head from FastAPI). That would put route and metadata definitions in Python *and* React with nothing keeping them in agreement — a shared secret across two languages, drifting silently, on a product whose differentiator is that its claims are checkable.

**Decision: React Router framework mode (`@react-router/dev`, v7 line), `ssr: false` with `prerender`.** It preserves Vite 8, Vitest, the Tailwind plugin, the dev proxy, every component, and — critically — **the existing static-site deployment, with no Node runtime and no third deployable.** The vendor publishes a migration guide from exactly our starting point, and its official template pins our exact stack. Pre-rendered and server-rendered paths are mixable, so `ssr: true` later requires no framework migration. Full reasoning, alternatives and accepted unknowns in ADR-039.

**One finding that changes sequencing: React 19 hoists `<title>` and `<meta>` natively.** Per-route dynamic metadata therefore needs no architectural change at all; only metadata *in the initial byte stream* requires pre-rendering. These are separable steps.

**OG images: Satori (JSX → SVG) → `sharp` (SVG → PNG), at build time.** `sharp` rather than resvg, which has had no stable release since 2024-03. Build-time generation adds no production runtime and regenerates on the same cadence as the pages. ECharts' server-side `renderToSVGString()` is available where a card needs a chart (ADR-041).

**Screenshots are never the sharing mechanism.** A screenshot is an unverifiable, undated, unlinkable copy of a claim — precisely the failure mode MacroChipz exists to fix.

---

## 21. Notifications / Follow

**Minimal by design, because honest triggers are rare by construction.**

```
IntelligenceObject (significance-gated)
   → trigger match against subscriptions
   → frequency ceiling enforced
   → email send
   → record what fired and why
```

**Rules:**

1. **Email only at launch.** World-level and release-level. No push, no SMS, no per-indicator granularity — granularity implies a frequency the data does not have.
2. **Triggers fire from significance-gated objects only.** A change that did not clear its threshold cannot notify.
3. **Every notification states why it fired** and links to evidence.
4. **A hard per-subscriber frequency ceiling, enforced in the system**, not by editorial restraint.
5. **One-click unsubscribe, honoured immediately.**
6. **Nothing cleared a threshold → nothing sends.** No digest-to-stay-present.
7. **Subscriber storage is minimal** — an email address and subscriptions. Nothing else.

---

## 22. Analytics

**Privacy-conscious by construction**, instrumenting the behavioural loop. Currently zero exists, which means no launch learning is possible without it.

- **Cookie-free, aggregate measurement.** No cross-site tracking, no advertising pixels, no fingerprinting, no personal data beyond a volunteered email address.
- **Event taxonomy follows Constitution §31**, and **every event names the question it answers** — events without one are not implemented.
- **The headline metric is evidence-expansion rate.** If nobody opens VERIFY, the product's central bet (provenance as differentiator) is wrong, and that is the single most valuable thing launch can teach us.
- **Empty states are instrumented.** Whether "nothing changed today" retains or repels is empirical and consequential.
- **Analytics never gates publication.** No honest finding is suppressed for underperforming.
- **Analytics failure never degrades the product.** Fire-and-forget; no page blocks on a beacon.

---

## 23. Caching / Performance

Canonical reads change on a release schedule, which makes them **exceptionally cacheable** — a genuine structural advantage worth exploiting.

**Cache key must include: canonical object id + methodology version + data vintage.** Omitting vintage serves a pre-revision conclusion after a revision; omitting methodology version serves an old conclusion under a new version string. **Both are correctness failures on a trust product, not performance bugs.**

**Principles:**

1. **Server-rendered or pre-rendered HTML** for anything shareable or indexable (§20).
2. **Nothing blocks initial understanding on an AI call.**
3. **Charts are not in the initial bundle.**
4. **Video loads on interaction only** — facade first.
5. **Every page works with the Analyst unavailable and degrades legibly with the database unavailable** — an existing, verified #34 property.
6. **No premature infrastructure optimisation.** Measured page experience matters; theoretical scale does not at this size.

**On charting — decided in ADR-041.** Hand-authored SVG over **d3 math primitives** (`d3-scale`, `d3-shape`, `d3-time-format`, +15.7 KB gzip measured), with ECharts reserved for **server-side rendering only** and never in the client bundle.

The SSR requirement did most of the deciding. Measured against React 19.2.8 with no DOM: **Recharts emits a 127-byte empty `<div>` with zero `<svg>`** — a tracked regression from 2.x, unfixed fifteen months on — and uPlot, Chart.js, Observable Plot, visx's `XYChart` and Nivo's `ResponsiveLine` all fail too. **visx *primitives* pass and remain the designated escape hatch, triggered by needing touch tooltips on more than one chart.**

---

## 24. Failure Containment

Existing patterns are good and generalise.

| Failure | Behaviour |
|---|---|
| One provider unreachable | Other sources proceed; run recorded `PARTIAL_FAILURE` naming what failed (existing `rates_ingestion` pattern) |
| One page section's data unavailable | That section shows its own error; the rest of the page renders (existing per-section branches) |
| Analyst unavailable | Surface hidden or shown as unavailable; page fully functional |
| Radar unavailable | No Radar objects; nothing else affected |
| Database unreachable | `/health` 200, `/readiness` reports `database_unreachable`, reads return contained 503 (verified in #34) |
| Analytics unavailable | Silent; no user-visible effect |
| Email send fails | Retried, recorded; never blocks ingestion |
| OG image generation fails | Falls back to a static default card; the page still shares |
| Schema drift | `/readiness` fails on exact-equality mismatch (ADR-027) |

**Rule: no optional subsystem may take down a required one.** Radar, Analyst, analytics, email and OG generation are all optional by this definition.

---

## 25. Security / Abuse Boundaries

**Unchanged from #34, and the model remains correctly sized: one privileged operator, everyone else an anonymous reader. No user accounts, no personal data, no payments, no sessions.**

Existing: `X-Operator-Token` with `compare_digest` on the three sync endpoints, failing closed in production · `ENVIRONMENT` as the single production switch · in-process fixed-window rate limiting on the Analyst · body-size limit · four security headers · CORS allowlist · request-id correlation · JSON logging · startup misconfiguration reporting naming variables and never values.

**2.0 additions:**

1. **Email capture is a new anonymous write surface** — the first one. It needs rate limiting, input validation, and double opt-in. It is also the only place MacroChipz will hold personal data, so it gets the narrowest possible storage.
2. **OG image generation is a new compute surface** — must be bounded and cached per object, never generated per request from arbitrary parameters.
3. **The rate limiter is in-process and per-instance**, valid only for single-instance deployment. **If 2.0 ever runs more than one instance, this becomes incorrect** and must be revisited — noting it here so it is not discovered in production.
4. **Removing the legacy AI subsystem removes the largest latent anonymous cost surface.** It is unmounted today; deleting it removes the possibility of re-mounting it by accident.

---

## 26. Deployment Implications

Unchanged in shape: single container image, CI validates and never deploys (ADR-028), `ENVIRONMENT`-derived production behaviour.

**Changes:**

1. **Serving server-rendered HTML from FastAPI** (§20) means the frontend build output is served by the backend rather than as a separate static site. **This simplifies deployment to one service** and removes a CORS surface.
2. **Scheduled ingestion needs a reliable runner.** A free-tier web service that spins down after inactivity does not run scheduled jobs — if release-driven processing is the product's heartbeat, that configuration does not validate the product.
3. **New environment variables:** per-source API keys (BLS, BEA, Census), email provider credentials, analytics site id. All follow the existing pattern — named in config, never printed, reported as configured/unconfigured at startup.
4. **Operating cost is not a constraint:** roughly $15/month floor, $28/month with defensible database headroom, plus about $0.38 per 1,000 Analyst requests. No architectural decision in this document should be driven by cost.

---

## 27. Migration Strategy

**Behaviour-preserving, incremental, reversible. No big-bang rewrite.**

### 27.1 Principles

1. **Abstraction before migration.** Introduce `SeriesSource`, implement `FREDSource` against it, verify identical behaviour, *then* add `BLSSource`.
2. **Golden-vector equality is the acceptance criterion.** Every canonical result must be byte-identical before and after a source swap. Frozen methodologies plus 1,915 existing tests make this checkable rather than aspirational.
3. **One source at a time**, each independently revertible.
4. **Identifiers migrate with the source** (§5.3), never after.
5. **Existing functionality is preserved throughout.** No user-visible regression is acceptable as migration cost.

### 27.2 Order and why

| # | Step | Why here |
|---|---|---|
| 1 | `SeriesSource` protocol + `FREDSource` adapter | Pure refactor. Zero behaviour change. Safest possible first step. |
| 2 | Canonical identifier mapping | Must precede a source swap or FRED's naming survives the migration. |
| 3 | `BLSSource` for the two labor series | Smallest real migration. Two series, one agency, verifiable against golden vectors. |
| 4 | `BLSSource` + `BEASource` for the four inflation series | Two agencies, one methodology. The seasonal-adjustment re-pull rule (§5.4) lands here. |
| 5 | `ReleaseScheduleSource` + BLS iCal + BEA JSON | The stickier dependency. Requires superseding ADR-020. |
| 6 | Deep historical re-ingestion | Unlocks historical-context claims; a Radar precondition. |
| 7 | Delete `discovery.py` (FRED search) | Removes a dependency serving no 2.0 need. |
| 8 | Remove the legacy AI subsystem | Already unmounted; deletion removes the re-mount risk. |
| 9 | Census for Housing | First genuinely new source; no migration risk since nothing depends on it yet. |

**Treasury requires no migration.** It is already independent, already uses MacroChipz-owned identifiers, and is the reference implementation for every adapter above.

### 27.3 Component preservation audit

**Backend**

| Component | Verdict | Note |
|---|---|---|
| `app/domain/*` (13 modules) | **KEEP — frozen** | Pure, AST-guarded, mutually independent. Untouched by 2.0. |
| Five frozen methodologies | **KEEP — frozen** | Version strings and documents unchanged. |
| `observation_versions` + `ObservationVersionWriter` | **KEEP** | The Time Machine and Revision Intelligence spine. |
| `ReplayService` | **KEEP** | Required for Radar vintage recomputation (§15.3) and methodology-then-vs-now. |
| `observation_provenance` | **KEEP + EXTEND** | Attribution becomes source-derived rather than hardcoded. |
| Release processing pipeline | **KEEP** | Sound; gains new sources. |
| `recorded_monitor_results` | **KEEP** | Feeds `STATE` objects and history. |
| Monitor services (inflation/labor/rates) | **KEEP** | Gain a projection consumer; no internal change. |
| `app/api/analyst.py` + Analyst services | **KEEP** | Context packet source changes (§18); architecture unchanged. |
| `app/api/operator.py`, `rate_limit.py`, `middleware.py`, `core/logging.py` | **KEEP** | #34 hardening, unchanged. |
| `app/clients/treasury.py` | **KEEP** | The reference adapter. |
| `app/clients/fred.py` | **EVOLVE → DEPRECATE** | Becomes a `SeriesSource` adapter, then is removed when the last binding moves. |
| `app/services/releases.py` (`ReleaseSyncService`) | **REFACTOR** | `FREDClient` → `ReleaseScheduleSource`. |
| `app/services/discovery.py` | **DEPRECATE** | FRED series search serves no 2.0 user need. |
| `app/api/analysis.py` (`compare`, `pipeline`) | **DEPRECATE from the public surface** | Generic increment-era endpoints; `pipeline` is also the legacy AI tool's backend. |
| `app/api/ai.py`, `services/ai.py`, `services/ai_tools.py`, `models/ai.py` | **REMOVE** | Superseded by #33, unmounted since #34. Retire ADRs 014/015/016/017/018 with it. |
| `app/api/series.py` observations/transform | **KEEP** | Backs evidence surfaces. |

**Frontend**

| Component | Verdict | Note |
|---|---|---|
| Design system (`globals.css`, `stateTone.ts`, `theme/`) | **KEEP + EXTEND** | The machine-enforced `state-*` / `feedback-*` separation is a genuine asset and exactly right for Constitution §32's non-colour-only requirement. |
| `content/explanations/*` (34 constants, 8 lookups) | **KEEP + EXTEND** | **Already the seed of "Wait, Seriously?"** — curated, never AI-generated, never canonical. The explainer infrastructure substantially exists. |
| 10 architectural guard tests | **KEEP + EXTEND** | Extend to every new surface. |
| Shared primitives (`Card`, `Disclosure`, `Section`, `PageHeader`, `PageContainer`, `LoadingSkeleton`, `ErrorMessage`, `StateDurationLine`, `ThemeToggle`) | **KEEP** | Sound. `Disclosure` is already the VERIFY primitive. |
| `components/history/*` | **KEEP — resurface** | Becomes Revision Intelligence + Time Machine Stage 1. Currently buried inside two pages. |
| `components/analyst/AskMacroChipz.tsx` | **KEEP** | Placement changes to contextual; component unchanged. |
| `components/inflation/*`, `labor/*`, `rates/*` | **EVOLVE** | Become world-page components. Substance survives. |
| `components/releases/*` | **EVOLVE → `/calendar`** | |
| `components/overview/*` | **EVOLVE → homepage** | `CurrentStateSection` → Pulse; `WhatChangedPreview`/`LaborWhatChangedPreview` → What Changed; `UpcomingReleasesPreview` → What's Next; `SinceLastVisit` and `HowTheyRelate` survive as-is. **Most of the new homepage already exists on `/overview`.** |
| `pages/Overview.tsx` | **DEPRECATE the route; keep the contents** | `/overview` 301s to `/`. |
| `pages/Home.tsx` | **REFACTOR** | Currently static marketing copy fetching nothing. Replaced by THE LEDE + Pulse + What Changed + Explore + What's Next. |
| `pages/Labor.tsx` | **EVOLVE + RENAME** | `/labor` 301s to `/jobs`. |
| `pages/Inflation.tsx`, `Rates.tsx` | **EVOLVE** | Become world pages. |
| `pages/Releases.tsx` | **EVOLVE → `/calendar`** | 301 from `/releases`. |
| `AppShell` nav | **REFACTOR** | Five items; `/jobs`; footer attribution becomes source-derived. |
| `YieldCurveChart.tsx` | **KEEP + GENERALISE** | The accessible hand-rolled SVG pattern becomes the chart primitive set (§23). |
| Client-only SPA rendering | **REFACTOR** | Server-rendered `<head>` (§20). The React app itself is preserved. |

> **The headline of this audit: almost nothing is thrown away.** The engine, methodologies, versioning, replay, evidence model, design system, explanation content and guard tests all survive. What changes is the **information architecture**, the **rendering model**, the **data sources**, and the addition of a **projection layer** — none of which requires rewriting what is already correct.

---

## 28. Open Questions

Ordered by how much each would change the architecture. **#36A resolved the first three.**

1. ~~**Rendering model.**~~ **RESOLVED — ADR-039.** React Router framework mode, `ssr: false` + `prerender`, static deployment preserved.
2. ~~**OG image rasterization.**~~ **RESOLVED — ADR-039.** Satori → `sharp`, at build time.
3. ~~**Charting.**~~ **RESOLVED — ADR-041.** Hand-authored SVG over d3 math; visx primitives behind a tooltip trigger; ECharts server-side only.
4. **Would the St. Louis Fed grant written permission for FRED/ALFRED?** A yes makes the backward Time Machine immediately buildable and materially reduces migration urgency. **Cost of asking: one email.**
5. **Does the FRED per-user-key clause bind a cached server-side architecture?** ⚖️ The highest-value legal question.
6. **Census calendar.** No iCal, JSON or CSV. Scraper or maintained table? A scraper is a recurring maintenance liability; a table is a recurring human liability.
7. **Scheduled-job runner.** Free-tier spin-down breaks scheduled processing (§26.2). Which runner, at what cost?
8. **Multi-instance.** The Analyst rate limiter is in-process. If 2.0 ever scales horizontally this is incorrect. When does that become real?
9. **Housing state methodology.** Housing ships Day-1 with data and no state. What would a defensible `housing_v1.0` require?
10. **Does anyone actually open VERIFY?** Not an architecture question, but the architecture's central bet. §22's headline metric exists to answer it.

---

## 29. Architecture Decision Candidates

**#36A wrote three of these.** The rest remain candidates for subsequent increments.

| ADR | Subject | Status | Supersedes |
|---|---|---|---|
| **ADR-034** | **Economic concept identity separate from provider series identity; evidence carries both** | **Written (#36A)** | — |
| **ADR-035** | Provider-neutral release identity and multi-source schedules | Candidate (#M4) | **ADR-020** |
| **ADR-036** | The Structured Intelligence Layer is a projection, never a source of truth | Candidate (#39) | — |
| **ADR-037** | `knowledge_basis` is propagated end to end and never inferred | Candidate (#39) | Extends **ADR-031** |
| **ADR-038** | Significance is determined in the engine and carried on the object | Candidate (#39) | — |
| **ADR-039** | **React Router framework mode with pre-rendering** | **Written (#36A)** | **The FastAPI-served-head proposal in the original §29** |
| **ADR-040** | Radar is a pre-registered detector registry, never a scanner | Candidate (post-launch) | — |
| **ADR-041** | **Hand-authored SVG over d3 math primitives; no charting library** | **Written (#36A)** | — |
| **ADR-042** | Retirement of the legacy AI subsystem and its ADRs | Candidate (#47) | Retires **ADR-014, 015, 016*, 017, 018** |
| **ADR-043** | Seasonally adjusted series are re-pulled in full, never appended | Candidate (#M3) | — |

\* **ADR-016's substance — "no AI-triggered ingestion" — is preserved as Invariant 7 and is not retired with the legacy code.** Only the ADRs describing the removed tool-calling subsystem are retired.

---

## Appendix — Target System Shape

```
                          ┌──────────────────────────────────────┐
  BLS · BEA · Census      │  SeriesSource / ReleaseScheduleSource│
  Treasury · Fed · DOL ──▶│         (adapters, §6)               │
                          └──────────────────┬───────────────────┘
                                             ▼
                          ┌──────────────────────────────────────┐
                          │  INGESTION (§7) — operator-guarded   │
                          │  ObservationVersionWriter.apply()    │
                          └──────────────────┬───────────────────┘
                                             ▼
        ┌────────────────────────────────────────────────────────────┐
        │  CANONICAL STORE                                            │
        │  observations · versions · provenance · releases · runs     │
        └────────────────────────────────────┬───────────────────────┘
                                             ▼
        ┌────────────────────────────────────────────────────────────┐
        │  DOMAIN (pure, AST-guarded) + frozen methodologies          │
        │  inflation_v1.0 · labor_v1.0 · rates_v1.0 · what-changed    │
        └────────────────────────────────────┬───────────────────────┘
                                             ▼
        ┌────────────────────────────────────────────────────────────┐
        │  STRUCTURED INTELLIGENCE LAYER (§11) — projection only      │
        │  significance · knowledge_basis · evidence · limitations    │
        └───┬──────────┬──────────┬──────────┬──────────┬────────────┘
            ▼          ▼          ▼          ▼          ▼
         web       share      alerts      brief     Analyst
      (SSR head)  (OG img)   (email)    (drafts)   (context)
            │          │          │          │          │
            └──────────┴────┬─────┴──────────┴──────────┘
                            ▼
                     ANALYTICS (§22)
                  privacy-conscious, aggregate
```

---

**This architecture is authoritative for MacroChipz 2.0 implementation increments.** It is amended by explicit increment and by ADR, not by drift.
