# Release Processing Read Model V1 (Increment #19B)

This document answers the question Increment #18 deliberately deferred
(see [docs/architecture/release-processing-v1.md](./release-processing-v1.md)
§21: "A public HTTP process/read endpoint... not required to prove
this pipeline") and Increment #19A deferred again ("#18's
release-processing evidence is deliberately not surfaced here"): how
does a client read #18's persisted detection/analysis evidence back
out, without conflating "never checked" with "checked and found
nothing," and without asserting a causal link the database doesn't
record?

Preceded by a focused, read-only contract audit (the #19B audit, no
production code touched). The audit's own candidate contract is **not**
authoritative where the frozen implementation prompt overrode it; see
[ADR-023](../adr/023-release-processing-read-model-no-causal-nesting.md)
for the most consequential correction (no causal nesting) and its full
reasoning.

## 1. The one endpoint

```
GET /api/v1/releases/processing-status
```

Query parameters: `occurrence_id`, `release_id`, `status`,
`start_date`, `end_date`, `limit` (default 20, 1-100), `offset`
(default 0, >= 0). No `series_id` filter -- this resource is scoped to
occurrences, not individual series.

No occurrence-detail route (`GET /releases/{occurrence_id}/processing-status`)
exists in V1 -- deliberately deferred, not designed here (see §7).
Enforced structurally by
`tests/test_release_processing_read_architecture.py::TestExactlyOneProcessingStatusEndpoint`.

## 2. Why a new, separate router/service/repository

`app/api/releases.py`, `app/services/releases.py`, and
`app/repositories/release_repository.py` are structurally forbidden
from importing anything series/observation/Inflation-shaped (see
`tests/integration/test_transaction_and_safety.py::TestReleaseCalendarStructuralIndependence`,
unmodified by #19B). The read model's repository and service
legitimately import `EconomicSeries`, `ReleaseObservationUpdate`, and
`ReleaseAnalysisUpdate` (series/observation-shaped, by construction --
this is a projection over #18's evidence). Rather than grow that
guard's forbidden-import list to carve out an exception, #19B mirrors
#18's own precedent of a small, new, separate module:

- `app/api/release_processing_read.py` -- the route.
- `app/services/release_processing_read.py` (`ReleaseProcessingReadService`)
  -- orchestration. Explicitly NOT `ReleaseProcessingService` (#18's
  write orchestrator) -- no `FREDClient`-shaped parameter anywhere.
- `app/repositories/release_processing_read_repository.py`
  (`ReleaseProcessingReadRepository`) -- all SQL. Explicitly NOT
  `ReleaseProcessingRepository` (#18's write path) -- no `add_*`/
  `write_*`/`create_*` method anywhere on it (checked structurally).
- `app/models/release_processing_read.py` -- the public response
  contract, a plain Pydantic module with no FastAPI/SQLAlchemy
  dependency, like every other `app/models/*` module.

## 3. Five public statuses, derived from the latest run only

```
NOT_CHECKED | NO_CHANGE | CHANGES_DETECTED | PARTIAL_CHECK | CHECK_FAILED
```

`NOT_CHECKED` is the absence of any `ReleaseCheckRun` row for an
occurrence -- never a persisted value, the same discipline #18 already
applies to its own internal 4-value `CheckRunStatus`. The other four
are a pure, static presentation relabeling of that internal status
(`_STATUS_MAP` in `app/services/release_processing_read.py`):

| Internal (`ReleaseCheckRun.status`) | Public (`ProcessingStatus`) |
|---|---|
| (no row exists) | `NOT_CHECKED` |
| `NO_CHANGE` | `NO_CHANGE` |
| `CHANGED` | `CHANGES_DETECTED` |
| `PARTIAL_FAILURE` | `PARTIAL_CHECK` |
| `FAILED_PROVIDER` | `CHECK_FAILED` |

The status shown is always derived from the occurrence's most recently
**completed** run only (`completed_at DESC, id DESC`, a deterministic
tie-break) -- never an aggregate or "worst of all runs" computation.

There is deliberately no sixth, catch-all status for an occurrence
whose release has zero active `ReleaseSeriesMapping` rows -- see §4.

## 4. Resource participation: mapped occurrences only

Only occurrences belonging to a release with at least one **currently**
active `ReleaseSeriesMapping` row appear in this resource at all --
filtered at the repository layer
(`ReleaseProcessingReadRepository.list_mapped_occurrences`), before any
status is ever derived. An unmapped release's occurrences are excluded
entirely, never given any status, never a `mapped: false` flag, never
a nullable status field. This was an explicit, frozen correction to
the #19B audit's own candidate contract (which had proposed a sixth
`NOT_APPLICABLE` status) -- see
[ADR-023](../adr/023-release-processing-read-model-no-causal-nesting.md)'s
sibling reasoning and
`tests/test_release_processing_read_architecture.py::TestNoNotApplicableStatus`.

"Currently active" is evaluated at query time against
`ReleaseSeriesMapping.active`, not reconstructed as-of the run's own
completion time -- V1's mapping catalog changes rarely and only ever by
direct migration/seed, so this is not a meaningful source of drift in
practice, but it is not a database-enforced point-in-time fact either.

## 5. Retry-history preservation -- the reason #19B exists

`latest_check` reflects the latest run only. `detected_observation_changes`
and `detected_analysis_changes` are the **union** of every
`ReleaseObservationUpdate`/`ReleaseAnalysisUpdate` row across **every**
run the occurrence has ever had -- not scoped to the latest run.

This is deliberate and load-bearing: a later `NO_CHANGE` (or
`CHECK_FAILED`) run's own absence of new rows must never erase an
earlier run's detected evidence from the response. Proven directly by
`TestRetryHistoryPreservation` in
`tests/integration/test_release_processing_read_service.py` and
`test_retry_history_survives_a_subsequent_no_change_run_over_http` in
`tests/api/test_release_processing_read_api.py`:

- `CHANGED` run (with a real detected change) -> `NO_CHANGE` retry:
  `latest_check.status == "NO_CHANGE"`, but the original change is
  still present in `detected_observation_changes`.
- `FAILED_PROVIDER` run -> `CHANGED` retry (once the provider recovers):
  `latest_check.status == "CHANGES_DETECTED"`, with the real change now
  present.

## 6. Sibling facts, never nested by causality

`ReleaseProcessingStatusItem` exposes `detected_observation_changes`
and `detected_analysis_changes` as two independent, top-level arrays.
Neither array's items reference the other, and no `detected_change`
wrapper object exists anywhere in this contract. See
[ADR-023](../adr/023-release-processing-read-model-no-causal-nesting.md)
for the full reasoning: `ReleaseObservationUpdate` and
`ReleaseAnalysisUpdate` each only reference `release_check_run_id` in
the database, with no persisted correspondence between a specific
observation and a specific analysis event.

## 7. Success/failure series counts: omitted, not approximated

`SeriesCheckOutcome` (#18's in-memory per-series result -- see
`app/models/release_processing.py`) is never persisted. `ReleaseCheckRun`
carries no per-series breakdown, and a series checked successfully with
zero changes leaves no row in `ReleaseObservationUpdate` either -- there
is no way to reconstruct `successful_series_count`/`failed_series_count`
from persisted data alone without fabricating them. V1's `LatestCheck`
omits both fields entirely rather than approximate; this was named in
advance as an acceptable omission, not a stop condition, and is
enforced structurally by
`TestNoSuccessFailureCountFabrication`.

## 8. Pagination and filtering

`limit`/`offset`/`returned`/`total` -- the same `PaginationMeta` shape
`GET /api/v1/releases` already uses (reused unmodified, not
redefined). No cursor pagination. `total` reflects the **status-filtered**
candidate set, not the unfiltered mapped-occurrence count -- proven by
`test_total_reflects_the_status_filtered_set_not_the_unfiltered_candidate_count`.

Filtering by `occurrence_id`/`release_id`/`start_date`/`end_date`
happens at the SQL layer (a plain `WHERE`/`IN` query -- not fragile).
Filtering by `status` happens in Python, in the service, after
deriving each candidate's latest-run status -- expressing "latest run
per occurrence, then filter by its derived status" as a single SQL
window-function query was deliberately not attempted for V1. The
mapped-catalog scale this resource operates over (a handful of curated
releases, each with at most a few dozen occurrences) makes fetching the
full filtered-but-unpaginated candidate set into Python the simpler,
not-prematurely-optimized choice; revisit only if the curated mapping
catalog grows enough for this to become a measured problem, not
speculatively.

## 9. Deferred (named explicitly, not built here)

- A single-occurrence detail endpoint
  (`GET /releases/{occurrence_id}/processing-status`) -- add once a
  real product surface needs it (e.g. an occurrence detail page); the
  collection endpoint's per-item shape is already exactly what such a
  route would return for one occurrence, so adding it later requires no
  redesign of this contract.
- `successful_series_count`/`failed_series_count` -- would require a
  #18 write-path change (persisting `SeriesCheckOutcome`), not a #19B
  read-model one.
- A persisted causal link between a specific observation change and a
  specific analysis change -- see
  [ADR-023](../adr/023-release-processing-read-model-no-causal-nesting.md)
  §Revisit When.
- Any frontend consumer of this endpoint -- #19C or later.
