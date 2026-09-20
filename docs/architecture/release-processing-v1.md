# Economic Intelligence
# Release-Driven Update Pipeline Specification v1

| | |
|---|---|
| Specification version | 1 |
| Status | **IMPLEMENTED FOR #18** |
| Scope | Release-driven observation detection, canonical persistence, and deterministic Inflation analytical-consequence auditing |
| Canonical data provider, V1 | FRED |
| AI dependency | None |
| Depends on | [Release Intelligence Specification v1](./release-intelligence-v1.md) (frozen for #17A/#17B; unmodified by this document), `inflation_v1.0`, `inflation_what_changed_v1.0` (both frozen; unmodified by this document) |

> This document describes what Increment #18 actually implemented,
> grounded directly in the repository (`app/domain/release_processing.py`,
> `app/repositories/release_processing_repository.py`,
> `app/services/release_processing.py`,
> `app/operations/process_release.py`, `app/db/models.py`,
> `app/clients/fred.py`), not a forward-looking proposal. Where this
> document and the code disagree, the code is the fact and this
> document has a bug to fix.

---

## 1. Purpose

Increment #17 answered *what's scheduled and whether a scheduled date
has passed* -- with an explicit, structural guarantee that a schedule
fact never implies anything about canonical economic data
([release-intelligence-v1.md](./release-intelligence-v1.md) §2, [ADR-019](../adr/019-release-calendar-structurally-separate.md)).
This document answers the next question #17 deliberately deferred
(§14 of that spec): *given a release occurrence, which canonical
series should be checked, did the provider actually return anything
new or revised, and did that change any deterministic Inflation
conclusion?*

---

## 2. Permanent invariants (inherited, unmodified, re-verified)

Every invariant in [release-intelligence-v1.md](./release-intelligence-v1.md)
§2 still holds, completely unmodified by this document:

1. A scheduled release date passing never itself changes a canonical
   economic conclusion.
2. Release scheduling metadata (`EconomicRelease`/`ReleaseOccurrence`)
   and economic observation availability
   (`EconomicSeries`/`EconomicObservation`) remain structurally
   separate, with `app.repositories.release_repository`,
   `app.services.releases`, and `app.api.releases` still statically
   forbidden from importing anything series/observation/Inflation-shaped
   (`tests/integration/test_transaction_and_safety.py::TestReleaseCalendarStructuralIndependence`,
   unmodified by #18).
3. Facts are sourced. Calculations are deterministic. AI is
   interpretive. #18 imports no AI/LLM module anywhere in its own
   files (checked by `tests/test_release_processing_architecture.py::TestNoAIOrNewsImports`).
4. News can never determine release schedule truth, observation
   availability, economic observations, or Inflation results -- #18
   imports no news module either (same guard).
5. Missing timing precision stays explicit, never fabricated -- #18
   never infers a time of publication, a timezone, or provider delay
   (§9 below).

#18 adds one new permanent invariant of its own:

6. **Explanations, mapping curation, and audit records never determine
   canonical results.** `ReleaseSeriesMapping` answers only "what to
   check," never "what this means" (§4). Every analytical consequence
   #18 persists is produced by calling `app.domain.inflation`'s and
   `app.domain.inflation_what_changed`'s existing, frozen, unmodified
   functions -- never a parallel reimplementation (§8, [ADR-022](../adr/022-release-processing-audit-without-monitor-snapshots.md)).

---

## 3. High-level flow (as implemented)

```
ReleaseOccurrence (eligibility only -- proves nothing about publication)
        |
        v  scheduled_date <= as_of_date (app.services.release_processing.OccurrenceNotEligibleError otherwise)
ReleaseProcessingService.process_occurrence
        |
        v
ReleaseSeriesMapping ("what to check" -- app.repositories.release_processing_repository)
        |
        v
FRED bounded date-based observation fetch (FREDClient.get_observations,
observation_start = as_of_date - 5 calendar years)
        |
        v
provider observations vs persisted observations
(app.domain.release_processing.classify_observation_change)
        |
        +-- UNCHANGED -> no observation-change row
        |
        +-- NEW / REVISED -> ReleaseObservationUpdate row + canonical write
        |
        v
affected (component, period) pairs
(app.domain.release_processing.affected_evaluation_periods x
 components_for_series)
        |
        v
BEFORE evidence (existing persisted data) -> canonical writes -> AFTER evidence
        |
        v
existing comparison primitives
(app.domain.inflation_what_changed.compare_series_momentum_section /
 compare_target_section / compare_confirmation_section)
        |
        +-- no analytical consequence -> nothing persisted
        |
        +-- analytical consequence -> ReleaseAnalysisUpdate row(s)
        |
        v
ReleaseCheckRun (status finalized), all in ONE transaction
```

The live Inflation Monitor (`GET /api/v1/monitors/inflation`) remains
100% stateless and canonical throughout -- nothing in this pipeline
persists an `InflationMonitorResult` snapshot, and the Monitor has zero
knowledge this pipeline exists (mirroring exactly how it already has
zero knowledge the release calendar exists, per
[release-intelligence-v1.md](./release-intelligence-v1.md) §11).

---

## 4. `ReleaseSeriesMapping`

Answers **only**: *"which canonical series should EI inspect when this
release is processed?"* It never answers *"what does this release
mean economically."*

| Field | Notes |
|---|---|
| `id` | EI's own canonical identity. |
| `economic_release_id` | FK to `economic_releases.id`, `ON DELETE CASCADE`. |
| `series_id` | A canonical provider series identifier **string** (`"CPIAUCSL"`, `"CPILFESL"`, `"PCEPI"`, `"PCEPILFE"`) -- deliberately **not** a foreign key to `EconomicSeries.id`. A curated mapping fact must exist independently of whether that series has ever been synced; `EconomicSeries` rows depend on ingestion state, and mapping persistence must not. |
| `active` | Curation toggle, same discipline as `EconomicRelease.active`. |
| `created_at` | Standard timestamp. |

`UNIQUE(economic_release_id, series_id)`.

**No `role`/`importance`/`weight`/`priority` column exists, and none
should ever be added** (checked structurally by
`tests/test_release_processing_architecture.py::TestNoRoleEnumOnReleaseSeriesMapping`,
which asserts the table has exactly these five columns). A release can
map to multiple series and a series can, in principle, be mapped from
multiple releases -- the schema supports both, though #18 V1's curated
data only exercises "one release, two series" (§6).

Which section of `inflation_what_changed_v1.0` a given mapped series'
change could affect is **not** read from this table at all -- it's
computed by `app.domain.release_processing.components_for_series`
(§8), a direct, verified mirror of `app.services.inflation.InflationMonitorService`'s
own existing wiring (`PRIMARY_SERIES_ID`/`CONFIRMATION_SERIES_ID`/
`TARGET_SERIES_ID`/`HEADLINE_CPI_SERIES_ID`), never invented and never
read from curated mapping data.

---

## 5. `ReleaseCheckRun`

One release-driven provider check attempt.

| Field | Notes |
|---|---|
| `id` | PK. |
| `release_occurrence_id` | FK to `release_occurrences.id`, CASCADE. Records that this check was initiated *in the context of* this occurrence -- never that the occurrence *caused* any observation to change (§9). |
| `status` | `NO_CHANGE` \| `CHANGED` \| `PARTIAL_FAILURE` \| `FAILED_PROVIDER` -- a plain `String` column, not a native enum (no existing table in this schema uses one; extending the allowed set later needs no migration). |
| `started_at` / `completed_at` | Both required, both timezone-aware. |
| `created_at` | Standard timestamp. |

**No `NOT_CHECKED` value** -- "not checked" is represented by the
absence of a row for an occurrence, never a persisted status.
**No status represents a database-transaction failure** -- if the
surrounding transaction itself fails, this row (and everything else
written alongside it) never durably exists at all. This is accepted,
documented behavior, not a gap: a second, separately-committed audit
transaction just to preserve a failure row was deliberately not built
(§10).

**Retrying an occurrence creates a NEW `ReleaseCheckRun` row every
time** -- "a check occurred" is a real, repeatable operational fact.
`ReleaseObservationUpdate`/`ReleaseAnalysisUpdate` rows are **not**
duplicated on a retry against unchanged provider data (§11).

---

## 6. Curated release -> series mappings (V1 seed data)

Seeded by `alembic/versions/cd476d227f99_seed_cpi_and_personal_income_and_.py`:

| FRED release (`provider_release_id`) | Mapped `series_id`s |
|---|---|
| `10` (Consumer Price Index) | `CPIAUCSL`, `CPILFESL` |
| `54` (Personal Income and Outlays) | `PCEPI`, `PCEPILFE` |

Deliberately **not** seeded: Employment Situation (`50`), JOLTS
(`192`), GDP (`53`), Advance Monthly Sales for Retail and Food
Services (`9`) -- none of these has a deterministic canonical
consumer in this repository yet. Seeding a mapping for them now would
mean release processing fetches and persists observations with no
analytical consequence ever computed from them -- exactly the "ingest
arbitrary series merely because their release exists" pattern #18 V1
is scoped not to do. The schema supports adding a mapping for any of
them the moment a real deterministic consumer exists; that is a future
migration, not a schema change.

---

## 7. `ReleaseObservationUpdate`

Append-only audit fact: *"during this check, EI detected that this
canonical provider observation was NEW or REVISED relative to EI's
persisted current value."*

| Field | Notes |
|---|---|
| `id` | PK. |
| `release_check_run_id` | FK, CASCADE. |
| `series_id` | The canonical provider series string. |
| `observation_date` | The affected calendar date. |
| `change_type` | `NEW` \| `REVISED` only -- **`UNCHANGED` is never persisted here.** "Unchanged" is represented by a successful check plus the absence of a row for that observation, keeping audit volume proportional to actual change, not to check frequency. |
| `previous_value` / `new_value` | Both nullable `Float` -- `EconomicObservation.value` itself is nullable, so a revision can legitimately transition into or out of `NULL` (a provider correcting a missing observation, or vice versa) without that transition being silently dropped. |
| `detected_at` | When this run detected the change. |
| `created_at` | Standard timestamp. |

`UNIQUE(release_check_run_id, series_id, observation_date)`.

### 7.1 Classification rule (`app.domain.release_processing.classify_observation_change`)

```
NEW:       the observation_date did not exist in EI's persisted data at all
REVISED:   the observation_date existed, and previous_value != new_value
UNCHANGED: the observation_date existed, and previous_value == new_value
```

Plain equality, no tolerance -- both sides reach this comparison having
passed through the same deterministic provider string -> float parse
(`app.services.economic_data._parse_value`'s exact rule, restated
independently in `app.services.release_processing._parse_value` --
see §12 for why it's restated rather than imported). Neither value is
independently *calculated*; both are only ever *parsed*, so there is
no floating-point rounding-drift risk a tolerance would need to guard
against. `None` participates in plain Python equality exactly as
defined: a transition into or out of "missing" is always `REVISED`,
never silently dropped.

### 7.2 Where classification lives, and why it's not in `SeriesRepository`

`app.repositories.release_processing_repository.ReleaseProcessingRepository`
is a **new, #18-owned repository** -- it does not retrofit
`SeriesRepository._upsert_observations` (which backs the plain,
pre-existing `POST /series/{id}/sync` and must keep meaning exactly
what it already means: a blind overwrite, no audit side effect).
`ReleaseProcessingRepository.write_observation` is a small,
independent reimplementation of the same basic insert-or-overwrite
shape -- a deliberate, accepted duplication of a few lines of
mechanical SQLAlchemy code, never of classification/economic logic.
The classification *decision* is always made by the service, before
this method is ever called; an `UNCHANGED` observation is never passed
to it at all.

---

## 8. `ReleaseAnalysisUpdate`

Structured, typed analytical consequence of one or more observation
changes in a check run -- **not** a full `InflationMonitorResult`
snapshot, and never arbitrary JSON (checked structurally by
`tests/test_release_processing_architecture.py::TestNoFullMonitorSnapshot`,
which asserts every column on this table is a small typed scalar).

| Field | Notes |
|---|---|
| `id` | PK. |
| `release_check_run_id` | FK, CASCADE. |
| `component` | `PRIMARY_MOMENTUM` \| `CONFIRMATION` \| `TARGET` \| `HEADLINE_PCE` \| `HEADLINE_CPI` -- `inflation_what_changed_v1.0`'s own frozen `ChangeComponent` enum, reused verbatim. |
| `event_type` | `METRIC_CHANGED` \| `STATE_CHANGED` \| `AVAILABILITY_LOST` \| `AVAILABILITY_RESTORED` \| `CONFIRMATION_CHANGED` -- the same frozen `ChangeEventType` enum, reused verbatim. **No new event type was invented** (no `ANALYSIS_RECOMPUTED`/`CANONICAL_STATE_CHANGED`/`DATA_CHANGED`/`NO_ANALYTICAL_CHANGE`). |
| `field` | e.g. `"state"`, `"r_3m_annualized"`, `"relationship"`, `"target_gap_pp"`. |
| `previous_value` / `current_value` | Nullable `String` -- `ChangeEvent.previous_value`/`current_value` are typed `float \| str \| None` (a numeric metric, or a state/relationship label); `str(float)` round-trips exactly in Python, so one typed column holds either without splitting one conceptual field across two nullable columns. |
| `delta` | Nullable `Float`. |
| `evaluation_period` | **One** `Date` column -- the deliberate, honest adaptation of `ChangeEvent`'s shape (§8.1). |
| `methodology_id` / `data_basis` | `"inflation_v1.0"` / `"latest_revised_data"`, populated from the same frozen constants `app.models.inflation` already defines -- never hardcoded a second place. |
| `created_at` | Standard timestamp. |

A check run producing zero analytical consequences (data changed but
no canonical Inflation evidence differed) simply has **zero rows**
here -- never a synthetic "no change" row (§14).

### 8.1 Why `evaluation_period`, not `previous_period`/`current_period`

`inflation_what_changed_v1.0`'s `ChangeEvent` carries separate
`previous_period`/`current_period` fields because it compares two
*different* calendar months (the current one and the one immediately
before it). A release-scoped before/after comparison evaluates both
snapshots at the exact **same** period -- writing a new/revised
observation doesn't move *which* calendar month is being evaluated,
only *what value* is at it. Giving `ReleaseAnalysisUpdate` a single
`evaluation_period` column, and passing that same date as both
`previous_period` and `current_period` into the existing comparators
(§8.2), is the honest release-scoped equivalent of the frozen
contract's own period semantics -- not a distortion of them.

### 8.2 Reused, not reimplemented (the central architectural proof)

`app.services.release_processing` calls `app.domain.inflation`'s
existing exact-period primitives --
`compute_series_momentum_at`/`compute_target_at`/`compute_confirmation_at`
-- once against persisted data **before** any write, and once **after**
(§13), then feeds both results through `app.domain.inflation_what_changed`'s
existing comparators -- `compare_series_momentum_section`/
`compare_target_section`/`compare_confirmation_section` -- unmodified,
with `previous_period == current_period == evaluation_period` (§8.1).
No `if r_3m < ...`, no custom target-delta logic, no custom
confirmation logic exists anywhere in `app/services/release_processing.py`
or `app/domain/release_processing.py` (checked structurally by
`tests/test_release_processing_architecture.py::TestExistingComparisonPrimitivesAreReused`
and `TestNoInflationThresholdOrClassificationLogicInReleaseProcessing`).

### 8.3 Which series feeds which component

`app.domain.release_processing.SERIES_TO_COMPONENTS`, a direct,
verified mirror of `app.services.inflation.InflationMonitorService`'s
own existing orchestration (not invented):

```
PCEPILFE  -> PRIMARY_MOMENTUM, CONFIRMATION
CPILFESL  -> CONFIRMATION
PCEPI     -> TARGET, HEADLINE_PCE
CPIAUCSL  -> HEADLINE_CPI
```

A CPI release change to `CPIAUCSL` can therefore only ever affect
`HEADLINE_CPI`; it can never fabricate a `PRIMARY_MOMENTUM` (Core PCE)
event, because Core PCE's own series (`PCEPILFE`) was never touched.
`CONFIRMATION` is affected by a change to *either* `PCEPILFE` or
`CPILFESL`, because the confirmation relationship is defined over both
together -- even though only one of them may have been mapped to the
release that triggered this particular check. For this reason, the
pipeline loads all four canonical series' persisted history for
before/after evidence regardless of which of them this release's own
mapping touches (`app.services.release_processing._load_canonical_observations`).

### 8.4 Multiple changed observations feeding one evaluation

`app.domain.release_processing.affected_evaluation_periods` computes,
for a batch of changed observation dates, every calculation period any
of them could affect -- each changed date's own period, plus (only
when a later observation already exists) each date `+1`/`+3`/`+6`/`+12`
months forward, the exact horizons `inflation_v1.0` itself defines.
The **union** across the whole batch is evaluated exactly once, before
all writes and once after all writes -- never once per individual
observation row, and never as a running/intermediate state after each
write. This is why a CPI payload that revises three different
endpoints all feeding the same later period produces one consistent
diff at that period, not three contradictory intermediate ones.

---

## 9. `ReleaseOccurrence` association semantics

A `ReleaseCheckRun` records *"this check was initiated in the context
of this `ReleaseOccurrence`"* -- a process fact. It never claims
*"this `ReleaseOccurrence` caused this observation to change"* -- an
unprovable causal fact FRED's date-only calendar cannot support (see
[release-intelligence-v1.md](./release-intelligence-v1.md) §3). Naming
throughout reflects this: `release_occurrence_id` on `ReleaseCheckRun`,
never an "occurrence caused" field anywhere.

---

## 10. Transaction boundaries and failure semantics

**One database transaction per processed release occurrence**
(`session_scope()`, exactly the same single-transaction-per-request
discipline every other write path in this project already uses). Within
that one transaction: `ReleaseCheckRun`, every successful mapped
series' canonical observation writes, every `ReleaseObservationUpdate`,
and every `ReleaseAnalysisUpdate` row are all written and committed
together, or none of them are.

| Failure | Behavior |
|---|---|
| One mapped series' FRED call fails (`FREDAuthError`/`FREDTimeoutError`/`FREDUpstreamError`, or malformed observation data) | Caught per-series in `ReleaseProcessingService._check_one_series`; recorded as that series' own `succeeded=False` outcome; **other mapped series in the same release still complete and their valid changes are still persisted.** No fake/fabricated data is ever written for the failed series. |
| All mapped series fail | `status = FAILED_PROVIDER`; zero observation/analysis rows. |
| Some succeed, some fail | `status = PARTIAL_FAILURE`; the succeeding series' real changes are persisted; the failing series contribute nothing. |
| A genuine database-layer failure (`IntegrityError`/`OperationalError`/`SQLAlchemyError`) at any point | **Not** caught inside `ReleaseProcessingService` -- propagates uncaught, aborting the whole occurrence's transaction. Every write attempted in that run (including any already-successful series' observations) is rolled back together. No partial canonical state can ever commit. |

A database failure means the `ReleaseCheckRun` row for that attempt
**never durably exists** -- this is accepted (§5), not a gap papered
over with a second, separately-committed "failure audit" transaction.

---

## 11. Idempotency

Two distinct guarantees, deliberately different:

- **Check idempotency**: re-running a check against identical provider
  data always creates a **new** `ReleaseCheckRun` row -- "a check
  occurred" is a real, repeatable operational fact worth recording
  every time, including on a retry.
- **Observation/analysis-event idempotency**: re-running against
  identical provider data produces **zero** new
  `ReleaseObservationUpdate`/`ReleaseAnalysisUpdate` rows, because
  classification (§7.1) always compares against whatever is *currently*
  persisted -- a value already matching what the provider returns
  classifies `UNCHANGED` on every subsequent run, by construction, with
  no separate deduplication logic required.

---

## 12. Bounded five-year detection horizon

`app.domain.release_processing.five_year_observation_start(as_of_date)`
computes `observation_start` by **exact calendar-year arithmetic**
(`date.replace(year=as_of_date.year - 5)`, with an explicit leap-day
fallback to Feb 28 when five years earlier isn't itself a leap year) --
never an approximation (`365 * 5` days is measurably wrong across a
five-year span containing leap days, and is directly tested against).

`FREDClient.get_observations` was extended minimally to accept this
bound:

```python
def get_observations(
    self, series_id: str, limit: int = 10,
    observation_start: date | None = None,
    sort_order: Literal["asc", "desc"] = "desc",
) -> list[dict]:
```

Every existing caller (`EconomicDataService.get_series` ->
`POST /series/{id}/sync`) is unaffected -- called with no new argument,
the request is byte-for-byte identical to before (no `observation_start`
param sent at all, `sort_order` still defaults to `"desc"`). Release
processing always passes `observation_start=five_year_observation_start(as_of_date)`,
`sort_order="asc"`, and a fixed `limit=100000` (comfortably above any
realistic monthly series' five-year observation count, well within
FRED's own documented page-size ceiling). **No second `FREDClient`
abstraction, no provider interface, no provider registry** -- this is
the same `FREDClient` class every other method already lives on
(ADR-020 remains valid; FRED is still the only provider).

This is a bounded, **ordinary** release-detection window --
newly-published observations, ordinary recent revisions, and major
recent seasonal/benchmark revisions. It is **explicitly not** a
guarantee that every historical revision in a provider's entire history
is detected by every release check. Broad, full-history reconciliation
(for annual/comprehensive benchmark revisions further back than five
years) is a different, deliberately deferred future capability -- not
built, not designed in detail here, and not something routine release
processing does (§17).

**No `expected_observation_period` was modeled.** #18 does not encode
"a September CPI release should contain August data" or any other
hardcoded publication-lag rule. The provider's actual returned data,
compared against what's already persisted, is the only evidence the
pipeline ever reasons from.

---

## 13. Before/after evidence -- the highest-risk piece, made structural

For every affected `(component, period)` pair (§8.4):

1. Load the four canonical series' current persisted observations
   (`_load_canonical_observations`) -- this is the **before** snapshot.
2. Evaluate each affected pair's evidence via `app.domain.inflation`'s
   exact-period primitives, against the before snapshot.
3. Write every classified `NEW`/`REVISED` observation.
4. Reload the four canonical series' observations -- this is the
   **after** snapshot.
5. Re-evaluate each affected pair against the after snapshot.
6. Diff before vs. after, once per pair, via
   `app.domain.inflation_what_changed`'s existing comparators (§8.2).

Steps 1-2 always complete, for every affected pair, before step 3 ever
writes anything -- there is no code path where an analytical
consequence is computed from a *partially*-written state.

---

## 14. No analytical consequence is not an error

If every fetched observation classifies `UNCHANGED`: zero
`ReleaseObservationUpdate` rows, zero `ReleaseAnalysisUpdate` rows,
`status = NO_CHANGE`. If observations changed but no affected
`(component, period)` pair's before/after evidence actually differs
(the changed value never participated in any currently-computable
state): `ReleaseObservationUpdate` rows exist, `ReleaseAnalysisUpdate`
rows do not, `status = CHANGED`. Both are normal, successful, fully
auditable outcomes -- nothing is ever recomputed merely to manufacture
an event.

---

## 15. Schedule status vs. processing status (kept separate)

`ReleaseOccurrence.schedule_status` (derived, `SCHEDULED`/`PAST_DUE`,
[release-intelligence-v1.md](./release-intelligence-v1.md) §7) is
**completely unmodified by #18** -- no `PUBLISHED`/`DATA_AVAILABLE`/
`PROCESSED` value was added to it, and nothing in `app.domain.releases`
gained any write capability (checked structurally by
`tests/test_release_processing_architecture.py::TestScheduleClassificationCannotWriteObservations`).
`ReleaseCheckRun.status` is a **separate**, new, persisted concept that
lives entirely on its own table, with zero relationship to
`ReleaseOccurrence`'s own columns.

---

## 16. Eligibility (deterministic, no fabricated precision)

An occurrence is eligible for a manual check when
`scheduled_date <= as_of_date` -- the exact complement of
`classify_schedule_status`'s own `SCHEDULED` boundary. **Today's own
scheduled date is eligible** (release times are unknown in V1; an
early same-day check may legitimately return `NO_CHANGE`, which is
valid, not a failure). A genuinely future-dated occurrence raises
`OccurrenceNotEligibleError` (`app.services.release_processing`) --
there is no provider-side reason to expect new data before its own
scheduled date has arrived. No time-of-day, timezone, or "provider
delay" inference exists anywhere in this eligibility rule.

---

## 17. Manual execution only -- no scheduler

#18 V1 adds **no** scheduler, background job, Celery/RQ worker, cron
integration, or poll loop -- there is still exactly zero background
execution capability anywhere in this project. The pipeline is
triggered explicitly, one occurrence at a time, via:

```
python -m app.operations.process_release --occurrence-id <id> [--as-of-date YYYY-MM-DD]
```

`app.operations.process_release` contains **no business logic** --
it parses arguments, resolves configuration, opens one real
`session_scope()` transaction, delegates entirely to
`ReleaseProcessingService.process_occurrence`, renders a safe summary,
and maps the outcome to a process exit code (`0` for `NO_CHANGE`/
`CHANGED`, `1` for `PARTIAL_FAILURE`/`FAILED_PROVIDER`/any operational
failure). It never prints an API key, a database URL, raw provider
response text, generated SQL, or a stack trace.

---

## 18. No public HTTP process endpoint (security)

**When #18 was written, this project had no authentication anywhere,**
and `POST /series/{id}/sync` and `POST /releases/sync` established an
existing, accepted pattern of unauthenticated mutation endpoints. As of
Increment #34 that premise no longer holds: both now require the
`X-Operator-Token` header (ADR-033). **#18's conclusion is unaffected
and, if anything, reinforced** -- release processing
is strictly more expensive (it fans out to multiple mapped series per
release, writes more rows, and performs additional computation) than
either. #18 deliberately does **not** add
`POST /api/v1/releases/{id}/process` or any equivalent route. The
existing route surface is completely unchanged (`GET /health`,
`GET/POST /api/v1/series/...`, `GET/POST /api/v1/analysis/...`,
`GET /api/v1/monitors/inflation...`, `GET/POST /api/v1/releases...`,
`POST /api/v1/ai/query` -- verified directly against the running
application's own OpenAPI schema, not just by inspecting source).
Release processing is reachable only through the operational CLI
(§17), controlled outside normal end-user HTTP traffic. The frontend
remains completely read-only -- `frontend/src/test/no-release-sync-or-coupling.test.ts`
was extended to also assert no release-related frontend file
references a process endpoint path or any of #18's new model names.
This is not a permanent decision to never add authentication (out of
scope for #18 entirely) -- it's a deliberate refusal to grow the
existing unauthenticated-mutation-surface risk further while that gap
remains unaddressed project-wide.

---

## 19. News and AI boundaries (unchanged, re-verified)

News is completely absent from this pipeline -- nothing in
`app/domain/release_processing.py`, `app/repositories/release_processing_repository.py`,
`app/services/release_processing.py`, or `app/operations/process_release.py`
imports anything news-related (checked structurally, §2). AI is
completely absent for the same reason. The entire pipeline -- fetch,
classify, write, before/after evidence, diff, persist -- is
deterministic and works identically with every AI capability in this
project permanently disabled.

---

## 20. Explainability (deferred to a future frontend increment)

No frontend explanation content was added for #18 -- zero frontend
production changes were made at all. A future increment's UI can
eventually explain concepts like "new observation detected," "revision
detected," "no change detected," "analysis changed," and "analysis
unchanged" using #17C's existing rule
([ADR-021](../adr/021-explanations-never-determine-canonical-results.md)):
canonical result -> explanation, never the reverse. Such explanation
content would be looked up by #18's own already-persisted, already-
deterministic `ReleaseCheckRun.status`/`ReleaseObservationUpdate.change_type`/
`ReleaseAnalysisUpdate.event_type` values -- never generated inside
this pipeline, and never fed back into it.

---

## 21. #18 scope (implemented)

- `ReleaseSeriesMapping`, `ReleaseCheckRun`, `ReleaseObservationUpdate`,
  `ReleaseAnalysisUpdate` (§4, §5, §7, §8) -- schema migration
  `dbd9a2889ef3`, curated seed migration `cd476d227f99` (CPI/Personal
  Income and Outlays only, §6).
- `FREDClient.get_observations` extended with `observation_start`/
  `sort_order` (§12), fully backward compatible.
- `app.domain.release_processing` -- pure classification, affected-period,
  and series-to-component logic (§7.1, §8.3, §8.4, §12).
- `app.repositories.release_processing_repository.ReleaseProcessingRepository`
  -- the new, #18-owned canonical write path + audit persistence.
- `app.services.release_processing.ReleaseProcessingService` -- the one
  new orchestration layer legitimately bridging the release-calendar
  and series/Inflation sides (§10, §13).
- `app.operations.process_release` -- the sole, manual, CLI-only
  operational trigger (§17).
- Eleven new architectural guard tests
  (`tests/test_release_processing_architecture.py`) plus two extended
  existing guards (`tests/test_domain_architectural_independence.py`,
  `tests/integration/test_transaction_and_safety.py`) plus one extended
  frontend guard (`frontend/src/test/no-release-sync-or-coupling.test.ts`).

**Not in #18** (deliberately deferred, not designed in detail here):

- Broad/full historical reconciliation beyond the five-year window (§12).
- A scheduler or any background execution (§17).
- A public HTTP process endpoint (§18) -- still not built, and still
  deliberately never planned (no authentication anywhere in this
  project). A public HTTP **read** endpoint over this pipeline's
  persisted evidence was built later, in Increment #19B -- see
  [docs/architecture/release-processing-read-model-v1.md](./release-processing-read-model-v1.md).
- Full point-in-time observation vintages/history (`EconomicObservation`
  remains one canonical current value per `(series, observation_date)`,
  overwritten on revision, with `ReleaseObservationUpdate` as the
  append-only audit trail of *that* fact -- see [ADR-022](../adr/022-release-processing-audit-without-monitor-snapshots.md)).
- `EconomicObservation.updated_at` -- deliberately **not** added (a
  generic row-touch timestamp would be semantically misleading given
  the existing blind-upsert behavior on the plain `/series/{id}/sync`
  path; `ReleaseObservationUpdate.detected_at` is the authoritative
  record of when a #18-driven change was detected).
- A `role`/`importance` enum on `ReleaseSeriesMapping` (§4).
- Employment Situation, JOLTS, GDP, or Advance Retail Sales mappings
  (§6) -- pending a real deterministic canonical consumer for any of
  them.
- Provider abstraction of any kind (§12) -- revisit only when a second
  real provider is actually integrated (ADR-020's own reversal
  condition, unchanged).
