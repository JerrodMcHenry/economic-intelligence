# First-Party BLS/BEA Ingestion — Specification (#56A)

Implements steps S1–S2 of `first-party-inflation-jobs-migration-v54b-audit.md`
§5, under the decisions approved for #56A:
- the six mappings;
- new concept-keyed rows, never relabelled FRED history;
- ten years of history;
- keyless first, optional credentials where they add something.

**Out of scope, by boundary:**
- release-calendar processing and binding activation (#56B);
- any frontend or classification change;
- any copy of FRED-derived data.

## 1. What changes, and what deliberately does not

| Component | Change |
|---|---|
| `app/clients/bounded_http.py` | **New.** One bounded transport for both providers: streamed body with a byte cap, timeout, a narrow retry, and typed errors that never carry a URL or credential |
| `app/clients/bls.py` | **New.** BLS Public Data API. v1 keyless; v2 when `BLS_API_KEY` is set (the key travels in the POST body, never a URL) |
| `app/clients/bea.py` | **New.** BEA NIPA monthly flat file (`NipaDataM.txt`), keyless, streamed and filtered to the requested series codes |
| `app/concepts/bindings.py` | Six new bindings, **`active=False`**, `storage_series_id = concept_id` |
| `app/models/first_party.py` | **New.** Datasets, landing-page source URLs, titles and native units per concept |
| `app/repositories/first_party_repository.py` | **New.** Series row, observation + provenance upsert via the shared `ObservationVersionWriter`, run audit |
| `app/services/first_party_ingestion.py` | **New.** Fetch → validate → persist, per-provider failure isolation |
| `app/operations/import_first_party.py` | **New CLI.** Runs outside any HTTP request |
| `observation_versions` origins | New origin `FIRST_PARTY_INGESTION` |
| Migration | **New additive table `provider_ingestion_runs`**: the provider-neutral run audit #45 deferred |

**Unchanged — the #56A contract:**
- Active bindings: every concept still reads FRED.
- Monitors, API responses, intelligence objects, since-last-visit, replay
  and the frontend.
- Release processing, the maintenance scheduler, and Rates/Housing
  ingestion.

The new rows are **inert until #56B activates them**. Every reader
resolves storage through `active_binding()`, and the intelligence builder
selects Housing via active bindings and Inflation/Jobs via
release-processing rows.

## 2. Mappings

| Concept | Provider | Provider series | Dataset | Native unit | Factor |
|---|---|---|---|---|---|
| `us.cpi.headline.price-index.sa.monthly` | BLS | `CUSR0000SA0` | CPI-U, SA | Index 1982-1984=100 | 1 |
| `us.cpi.core.price-index.sa.monthly` | BLS | `CUSR0000SA0L1E` | CPI-U, SA | Index 1982-1984=100 | 1 |
| `us.nonfarm.payroll-employment.sa.monthly` | BLS | `CES0000000001` | CES, SA | Thousands of Persons | **1000** |
| `us.unemployment-rate.sa.monthly` | BLS | `LNS14000000` | CPS, SA | Percent | 1 |
| `us.pce.headline.price-index.sa.monthly` | BEA | `DPCERG` (T20804 line 1) | NIPA | Index 2017=100 | 1 |
| `us.pce.core.price-index.sa.monthly` | BEA | `DPCCRG` (T20804 line 25) | NIPA | Index 2017=100 | 1 |

**Values are stored in native units, as FRED's are.** The payroll ×1000
stays in the domain layer through the binding factor, so `labor_v1.0` and
its golden vectors are untouched by construction. Census's write-time
conversion is deliberately not copied: applied here, it would
double-convert.

## 3. Flows

```
python -m app.operations.import_first_party [--years 10] [--provider all|bls|bea]
  └─ config + schema compatibility check (exit 2 if not COMPATIBLE)
  └─ session_scope (one transaction for the whole run)
       ├─ BLS: 1 POST, 4 series, start..end year ── BLSClient
       │     └─ per series → FirstPartyRepository.upsert_observation(baseline)
       │     └─ provider_ingestion_runs row (provider=BLS)
       └─ BEA: 1 streamed GET of NipaDataM.txt, filtered ── BEAClient
             └─ per series → upsert (baseline)
             └─ provider_ingestion_runs row (provider=BEA)
```

**Window:** calendar years `as_of.year - (years - 1)` through
`as_of.year`. Ten years is 2017-01 onward as of 2026, exactly BLS v1's
10-year maximum per query. With a BLS key, up to 20 years.

**Budget:**
- BLS: one query per run. v1 allows 25/day, v2 500/day.
- BEA: one ~37 MB download per run, streamed. No API quota applies.

## 4. Edge cases

| Case | Behaviour |
|---|---|
| `-` value (Oct 2025 CPI/CPS: "Data unavailable due to the 2025 lapse in appropriations") | Stored as a **NULL row**, matching FRED's `.` handling, so the NULL-month sets stay identical (#54B §1.3) and a later genuine value is a real NULL→value revision. Counted separately |
| BLS `M13` (annual average) or any non-`M01..M12` period | Skipped. Only monthly observations are ingested |
| BLS footnote `P` (preliminary) | Stored as the value; its later revision is a genuine REVISED version |
| BLS `REQUEST_NOT_PROCESSED` (daily threshold) | `ProviderRateLimitedError`, not retried; that provider's run is FAILED |
| BLS `REQUEST_SUCCEEDED` but a requested series missing | That series fails validation. The others proceed |
| BEA thousands separators (`"22,068"`), quoted values | Parsed; non-numeric → rejected row |
| BEA file over the byte cap, truncated, or header changed | `ProviderResponseError`. BEA run FAILED, BLS unaffected |
| Timeout or transport error, 5xx | One retry, then a typed error |
| 4xx other than 429, malformed body | Never retried |
| 429 | `ProviderRateLimitedError`, never retried (BEA locks out for a minute; BLS counts attempts against a daily quota) |
| Re-run with identical upstream data | 0 inserted, 0 revised, **no version rows** |
| Re-run after a genuine provider revision (e.g. BEA's 2026-09-30 annual update) | REVISED versions — true revisions, never baseline (the writer enforces it) |
| Interrupted run | One transaction, so it rolls back completely and leaves no run row (#54A §7) |

## 5. No false revisions — why the initial import cannot create one

1. **New rows.** The import writes only to `storage_series_id = concept_id`
   rows whose source is BLS or BEA. A FRED row is never read or written,
   so nothing FRED stored can be "revised" by a BLS value (test-pinned).
2. **Every first write is `NEW` with `is_backfilled = true`.** The
   baseline decision is `is_baseline_import`, the same pure function
   Housing uses. A revision is impossible on an empty row.
3. **Values are the published decimal strings, parsed once by `float()`.**
   That is the same conversion FRED's path applies, which is why
   358/358 values matched in #54B. No rounding, scaling or unit
   conversion happens at write time.
4. **Unavailable stays unavailable.** A `-` is NULL, never zero and never
   carried forward.

## 6. Security

- **The BLS key is sent only in the POST body**, never in a URL.
  - `BLSClient.__repr__` redacts it.
  - Errors are raised `from None`, so no chained httpx exception can
    print a request.
  - The run audit stores an exception class name only.
- **Provenance `source_url`** is a public landing page
  (`https://data.bls.gov/timeseries/<id>`, the BEA flat-file URL), never
  an API endpoint.
- **Every response body is capped:** BLS 2 MB, BEA 64 MB, streamed. A
  hostile or broken upstream cannot exhaust memory.
- Redirects are not followed. The base URLs are constants, and no
  user-supplied value reaches a host or path.
- **No HTTP route is added.** The initial import is operator-only, via
  the CLI or a Render Shell/job.

## 7. Acceptance criteria

1. **Parity.** On an isolated database, all six concept rows hold the
   same value as the FRED rows for every overlapping month, and the same
   NULL months, checked against the development database read-only. No
   FRED value is written to the isolated database or committed.
2. **Baseline.** An initial import writes only `NEW`, `is_backfilled`
   versions, and zero `REVISED`. An identical re-run writes nothing.
3. **Provenance.**
   - One provenance row per observation, with provider, dataset,
     provider series id, landing URL and the run's single `retrieved_at`.
   - One `provider_ingestion_runs` row per provider per run.
4. **Inert.** Active bindings, golden vectors, API contracts and every
   existing test are unchanged.
5. **Failure isolation.** A BLS failure leaves BEA's import intact and
   vice versa. A failed provider writes no observations.
6. **Offline tests.** No test makes a network request. BLS parsing is
   tested against a real recorded response (public domain), and BEA
   against a trimmed copy of the real file's format.

## 8. Tradeoffs

- **BEA keyless file over the keyed API.** The file carries every value
  and is the path verified against real data. The API needs a UserID
  and has no recorded response to test against. It becomes worthwhile
  for small per-release fetches in #56B, which is where it belongs.
  Cost: ~37 MB per import.
- **One transaction per run.** Simple and all-or-nothing on interruption.
  A provider failure is isolated *within* the run: the failed provider
  simply writes nothing.
- **A new run table rather than reusing `housing_ingestion_runs`.** It is
  the provider-neutral table #45 named, not a third copy. Rates and
  Housing keep their own tables, and migrating them is not this
  increment's job.
- **`SeriesIdentity.provider_series_id` for concept-keyed rows** still
  reads the storage id (the known gap in #54B §3). Harmless while the
  rows are inert. Must be fixed before activation in #56B. **Resolved in
  #56B** (`provider_series_id_for`; see first-party-activation-v56b.md).
