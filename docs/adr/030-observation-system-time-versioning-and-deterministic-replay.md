# ADR-030: Observations Carry Append-Only System-Time Versions Written by One Shared Algorithm on Every Write Path, and Replay Re-Executes the Methodology Against Them Rather Than Reading Back a Stored Result

## Status
Accepted

## Context

Through Increment #30, `economic_observations` was a **destructive current-value cache**: `_upsert_observations` overwrote `value` in place, so a provider revision erased the number that preceded it. The pre-#31 audit established this empirically rather than by reading code — of 1,072 observations in the development database, only 358 had any audit row at all, and all 714 Rates observations had none.

Two consequences followed, and both were load-bearing problems rather than cosmetic gaps:

1. **"What did MacroChipz know at time T?" had no answer.** `ReleaseObservationUpdate` (#18) recorded that a value changed, but only for observations that arrived through release processing, and it is a change log, not a reconstructable state — it cannot be asked for a full series as it stood on a date.
2. **`RecordedMonitorResult` (ADR-025) proved *what* MacroChipz concluded but could never prove *why*.** The observations behind a recorded state were gone. A stored conclusion nobody can re-derive is an assertion, not evidence — precisely the distinction ADR-025 itself drew between a recording and a reconstruction, now failing one layer down.

This project's standing principle — **facts are sourced, calculations are deterministic, AI is interpretive** — is what makes the fix worth making and also what makes it achievable: because the canonical layers are deterministic, a correct reconstruction of the inputs is sufficient to reproduce the output exactly. There is no sampling, no model state, no nondeterminism to defeat replay.

## Decision

**Add an append-only `observation_versions` table recording system-time intervals for every observation value, written by one shared algorithm that all three write paths call; and implement replay as a genuine re-execution of the frozen methodology against as-of inputs.**

Concretely:

- **`economic_observations` stays exactly what it is — the current-value cache.** It is not migrated into a history table, and no reader of it changes. History is additive, alongside. This keeps every existing query, endpoint, and monitor untouched, and means the versioning layer can be dropped (`alembic downgrade`) without losing a single canonical value.

- **System-time versioning only — deliberately not bitemporal.** Each row carries a half-open interval `[recorded_from, recorded_to)` answering "when did MacroChipz hold this value?". It does **not** carry a second, valid-time axis for "when did the provider publish it?", because MacroChipz does not reliably receive publication timestamps from its providers and a column that is honest for some rows and guessed for others is worse than no column. `observation_date` already carries the economic period. One axis, fully honest, over two axes where one is fabricated.

- **One algorithm, not three.** `ObservationVersionWriter.apply()` in `app/repositories/observation_versions.py` performs the canonical write **and** the versioning write together, and is the only place either happens. Series sync (`ORIGIN_SERIES_SYNC`), release processing (`ORIGIN_RELEASE_PROCESSING`), and Rates ingestion (`ORIGIN_RATES_INGESTION`) all delegate to it. Three independent implementations of interval-closing would drift, and a versioning layer that is correct on two of three write paths is not a versioning layer — it is a trap, because its gaps are invisible to every reader.

- **Write semantics are decided by the value, not by the caller.** `apply()` returns `INSERTED`, `REVISED`, or `UNCHANGED`. An identical value re-written produces **no new version** — routine re-fetches of unchanged history would otherwise bury genuine revisions under millions of meaningless rows and make the table useless for the question it exists to answer.

- **The backfill is marked as a backfill, and never claims to be a first publication.** The migration creates one open version per existing observation with `change_type = 'BACKFILL'`, `origin = 'BACKFILL'`, `is_backfilled = true`, and `recorded_from` set to the observation's own `created_at`. That timestamp honestly supports "this value existed by then" and nothing stronger; `is_backfilled` is exposed all the way up to `ReplayResult.inputs_include_backfilled` so a consumer can never mistake reconstructed provenance for observed provenance. **Pre-#31 revisions are permanently unrecoverable** — the data to recover them does not exist — and the schema says so rather than papering over it.

- **As-of reads never fall back to the current value.** `get_observations_as_of(series_id, at)` returns only versions whose interval contains `at`. A series with no version covering the anchor returns nothing. The alternative — silently substituting today's value for a missing version — would make every replay pass, which is precisely the failure mode that makes a temporal layer worthless.

- **Replay re-executes; it does not read back.** `ReplayService` loads the recorded result *only to compare against*, reconstructs inputs via `get_observations_as_of` at the recorded row's own `calculated_at`, and calls the same `app.domain` primitives release processing itself used. Returning the stored row would be a lookup wearing the word "replay".

- **Replay refuses rather than guesses.** Insufficient version coverage, or a `methodology_id` this binary no longer implements, yields `NOT_REPLAYABLE` with an explicit reason — never a recomputation over whatever data happened to be available, which would produce a confident, meaningless answer. In particular, coverage is checked *before* any calculation, because an empty input set would otherwise produce `INSUFFICIENT_DATA` that looks like an economic finding but is really a storage gap.

- **The database enforces the invariants, not the application.** A partial unique index permits at most one open version per `(series, observation_date)`; a unique constraint forbids two versions starting at the same instant; a check constraint rejects `recorded_to <= recorded_from`, which would otherwise create a zero-length interval invisible to every half-open query — a version that exists but can never be observed. Concurrency correctness therefore does not depend on application discipline.

- **Methodology versions are bound to behavior by golden vectors in CI, not by a runtime registry.** `tests/test_methodology_golden_vectors.py` pins fixed inputs to fixed outputs for `inflation_v1.0` and `labor_v1.0`. Before #31, `methodology_id` was a label: the meaning of `inflation_v1.0` could have changed with nothing failing, silently invalidating every historical row carrying it and making replay a lie. The guard lives in CI rather than in production code because the alternative — a version registry with dispatch — would require carrying every past methodology implementation forever, to serve a need no user has.

- **No UI, no API route, no input-linkage schema.** Replay is a service plus tests. Input linkage (explicitly recording which observation versions fed each result) was deferred by the increment brief, and implementation surfaced no correctness reason to override that: because monitor inputs are deterministically derivable from `(monitor, evaluation_period)` and the methodology is frozen, the as-of reconstruction is exact. This is recorded as a bounded assumption — a future monitor with dynamic input selection would require linkage, and that is the trigger to revisit.

## Alternatives Considered

- **Make `economic_observations` itself the versioned table.** Rejected: every existing reader would need to learn to filter for the open row, turning an additive change into a change to every query in the system, with no corresponding gain — the current-value cache is genuinely useful as a cache.
- **Bitemporal (system time + valid time).** Rejected as dishonest given current providers: valid time would be accurate where a provider supplies publication timestamps and invented everywhere else, and a column that is trustworthy for an unmarked subset of rows is worse than an absent one.
- **Version inside each repository, at each write site.** Rejected: three implementations of half-open interval closing is three chances to be subtly wrong, and an uneven versioning layer's gaps are invisible at read time.
- **Record a version on every write, including unchanged values.** Rejected: routine re-fetches would generate overwhelming noise and bury the genuine revisions the table exists to surface.
- **Have as-of reads fall back to the current observation when no version covers the anchor.** Rejected outright: it would make replay always succeed, which converts the feature from evidence into decoration.
- **Guess `recorded_from` for backfilled rows from release history where available.** Rejected: it would produce a table where some intervals are observed and others inferred, with no marker distinguishing them at read time. `is_backfilled` on every backfilled row is the honest version of this.
- **A runtime methodology-version registry with dispatch.** Rejected: it would oblige the application to carry every historical methodology implementation permanently, in production code, to satisfy a guarantee that a CI test satisfies completely.
- **Expose replay through an API route or UI panel.** Rejected for this increment: replay's value right now is as an internal correctness proof, and shipping a route would mean designing pagination, authorization, and a presentation of `NOT_REPLAYABLE` reasons before anyone has asked the product question.

## Consequences

- MacroChipz can answer "what did we know at time T?" for any series with version coverage, and can prove a recorded conclusion reproduces from the data available when it was made. All 133 real recorded results in the development database replay to `MATCH`.
- Every replay of pre-#31 history reports `inputs_include_backfilled = true`. That is accurate and will remain so for existing rows forever; coverage becomes genuinely observed only for observations written after this migration.
- Revisions to `inflation_v1.0` or `labor_v1.0` behavior now fail CI. The correct response is a **new** methodology version with **new** vectors — never an edit to the existing numbers, which would silently re-point every historical row.
- The versioning write adds one `SELECT` plus at most two writes per changed observation. Sync paths that mostly re-fetch unchanged data pay only the `SELECT`, since `UNCHANGED` writes nothing.
