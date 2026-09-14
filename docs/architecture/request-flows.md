# Request Flows

Runtime flows through the system as it exists today. See
[`current-architecture.md`](current-architecture.md) for the static
component picture.

- Flow 1 — Health Check
- Flow 2 — Economic Series Request (`GET`, FRED-backed, read-only, unchanged since Increment 002)
- Flow 3 — Failure Scenarios for the `GET` flow
- Flow 4 — Economic Series Sync (`POST .../sync`, persists to PostgreSQL) — new in Increment 003
- Flow 5 — Sync Failure Scenarios, including transaction rollback — new in Increment 003
- Flow 6 — Historical Observations Query (`GET .../observations`, PostgreSQL-only) — new in Increment 004
- Flow 7 — Observations Query Failure Scenarios — new in Increment 004
- Flow 8 — Transformation Query (`GET .../transform`, PostgreSQL-only + boundary context) — new in Increment 005
- Flow 9 — Transformation Failure Scenarios — new in Increment 005
- Flow 10 — Multi-Series Analysis Query (`GET /analysis/compare`, PostgreSQL-only) — new in Increment 006
- Flow 11 — Multi-Series Analysis Failure Scenarios, including undefined correlation — new in Increment 006
- Flow 12 — Composable Pipeline: raw/raw and mixed transformed composition — new in Increment 007
- Flow 13 — Composable Pipeline: boundary context with a `start_date` — new in Increment 007
- Flow 14 — Composable Pipeline Failure/Validation Scenarios — new in Increment 007
- Flow 15 — AI Query: no tool needed — new in Increment 008
- Flow 16 — AI Query: single-tool round (`get_observations`/`transform_series`) — new in Increment 008
- Flow 17 — AI Query: two-series tool call (`analyze_series`) — new in Increment 008
- Flow 18 — AI Query Failure Scenarios: invalid tool arguments, missing series, provider failure, tool-round limit — new in Increment 008
- Flow 19 — Series Discovery: local + FRED merge — new in Increment 013
- Flow 20 — Series Discovery: FRED degradation, local results survive — new in Increment 013
- Flow 21 — Series Discovery: no local match and FRED failure — new in Increment 013

## Flow 1 — Health Check

```mermaid
sequenceDiagram
    participant C as Client
    participant U as Uvicorn
    participant F as FastAPI app (app/main.py)

    C->>U: GET /health
    U->>F: dispatch request
    F->>F: health()
    F-->>C: 200 {"status": "ok"}
```

No dependencies, no I/O, no configuration involved — this route exists to
answer "is the process up" independent of anything else.

## Flow 2 — Economic Series Request (success path)

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route (app/api/series.py)
    participant S as EconomicDataService
    participant FC as FREDClient
    participant FRED as FRED REST API

    C->>R: GET /api/v1/series/UNRATE
    R->>R: settings.fred_api_key present?
    R->>S: get_series("UNRATE")
    S->>FC: get_series_info("UNRATE")
    FC->>FRED: GET /fred/series?series_id=UNRATE&api_key=...
    FRED-->>FC: 200 {"seriess": [{"title": "Unemployment Rate", "units": "Percent", ...}]}
    FC-->>S: series metadata dict
    S->>FC: get_observations("UNRATE", limit=10)
    FC->>FRED: GET /fred/series/observations?series_id=UNRATE&limit=10&sort_order=desc
    FRED-->>FC: 200 {"observations": [{"date": "...", "value": "4.1"}, ...]}
    FC-->>S: raw observations (newest first)
    S->>S: parse values ("." -> null), reverse to chronological order
    S-->>R: SeriesResponse
    R-->>C: 200 JSON (our contract, not FRED's)
```

Two separate FRED requests happen per series lookup — one for metadata
(title, units), one for observations — each going through the same
`FREDClient._get` request path (timeout, error translation) independently.

## Flow 3 — Failure Scenarios

All failures below funnel through the same shape: `FREDClient` raises one
of a small set of typed exceptions, and `app/api/series.py` is the single
place that maps each one to an HTTP status code. Nothing upstream of the
route (the service, the client) ever produces an HTTP response directly.

| Scenario | Where it originates | Exception | Where translated | HTTP status |
|---|---|---|---|---|
| Nonexistent series ID | FRED responds `400`, `error_message` mentions the series | `FREDSeriesNotFoundError` | `app/api/series.py` | `404` |
| `FRED_API_KEY` not configured | Checked in the route before a client is built | *(none raised — early return)* | `app/api/series.py` | `503` |
| FRED rejects the API key | FRED responds `400`, `error_message` mentions `api_key` | `FREDAuthError` | `app/api/series.py` | `503` |
| Upstream request exceeds timeout | `httpx.TimeoutException` inside `FREDClient._get` | `FREDTimeoutError` | `app/api/series.py` | `504` |
| Network failure / malformed FRED response | `httpx.HTTPError`, JSON decode failure, or missing expected fields | `FREDUpstreamError` | `app/api/series.py` | `502` |

### Nonexistent series

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route
    participant S as EconomicDataService
    participant FC as FREDClient
    participant FRED as FRED REST API

    C->>R: GET /api/v1/series/NOTREALSERIES123
    R->>S: get_series(...)
    S->>FC: get_series_info(...)
    FC->>FRED: GET /fred/series?series_id=NOTREALSERIES123&...
    FRED-->>FC: 400 {"error_message": "...series does not exist."}
    FC->>FC: raise FREDSeriesNotFoundError
    FC-->>S: (exception propagates)
    S-->>R: (exception propagates)
    R->>R: except FREDSeriesNotFoundError
    R-->>C: 404 {"detail": "Series 'NOTREALSERIES123' was not found."}
```

### Missing FRED configuration

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route

    C->>R: GET /api/v1/series/UNRATE
    R->>R: settings.fred_api_key is None
    R-->>C: 503 {"detail": "FRED integration is not configured on this server."}
```

No `FREDClient` is even constructed in this case — the route short-circuits
before any FRED call would be attempted.

### Bad FRED credentials

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route
    participant FC as FREDClient
    participant FRED as FRED REST API

    C->>R: GET /api/v1/series/UNRATE
    R->>FC: get_series_info(...)  (via the service)
    FC->>FRED: GET /fred/series?...&api_key=<rejected>
    FRED-->>FC: 400 {"error_message": "...api_key is not registered..."}
    FC->>FC: raise FREDAuthError
    FC-->>R: (exception propagates through the service)
    R->>R: except FREDAuthError
    R-->>C: 503 {"detail": "Economic data integration is currently unavailable."}
```

The client-facing message is deliberately generic: FRED's raw
`error_message` and the fact that the failure is credential-related are
never exposed to the API consumer.

### Upstream timeout

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route
    participant FC as FREDClient
    participant FRED as FRED REST API

    C->>R: GET /api/v1/series/UNRATE
    R->>FC: get_series_info(...)  (via the service)
    FC->>FRED: GET /fred/series?...
    Note over FC,FRED: no response within timeout (10s default)
    FC->>FC: httpx.TimeoutException -> raise FREDTimeoutError
    FC-->>R: (exception propagates through the service)
    R->>R: except FREDTimeoutError
    R-->>C: 504 {"detail": "Upstream FRED request timed out."}
```

## Flow 4 — Economic Series Sync (success path)

`POST /api/v1/series/{series_id}/sync` fetches from FRED (identical to
Flow 2) and then persists the result to PostgreSQL, all within one
database transaction.

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route (app/api/series.py)
    participant S as EconomicDataService
    participant FC as FREDClient
    participant FRED as FRED REST API
    participant SS as session_scope()
    participant Repo as SeriesRepository
    participant DB as PostgreSQL

    C->>R: POST /api/v1/series/UNRATE/sync
    R->>R: fred_api_key and database_url present?
    R->>SS: enter session_scope()
    SS->>DB: (session opened; transaction begins implicitly)
    R->>S: sync_series("UNRATE", session)
    S->>FC: get_series_info / get_observations (same as Flow 2)
    FC->>FRED: GET /fred/series, GET /fred/series/observations
    FRED-->>FC: 200 responses
    FC-->>S: raw metadata + observations
    S->>S: normalize -> SeriesResponse
    S->>Repo: save_series(SeriesResponse)
    Repo->>DB: SELECT economic_series WHERE series_id = 'UNRATE'
    alt series does not exist
        Repo->>DB: INSERT economic_series
        Repo->>DB: flush() (assigns new id, not yet committed)
    else series exists
        Repo->>DB: UPDATE economic_series SET title=..., units=..., source=...
    end
    Repo->>DB: SELECT existing economic_observations for this series
    loop each of the 10 normalized observations
        alt observation date already exists
            Repo->>DB: UPDATE economic_observations SET value=...
        else new date
            Repo->>DB: INSERT economic_observations
        end
    end
    Repo-->>S: EconomicSeries (persisted)
    S-->>R: SeriesResponse
    R->>SS: exit session_scope() normally
    SS->>DB: COMMIT
    R-->>C: 200 JSON (same contract as GET)
```

Calling this endpoint again with no change in FRED's data re-runs the same
sequence, but every branch takes the "already exists" path — no new rows,
no duplicate `(economic_series_id, observation_date)` pairs, because the
unique constraint backs up the upsert logic even if application logic
somehow missed a case.

## Flow 5 — Sync Failure Scenarios

Two failure categories are specific to the sync flow: FRED-side failures
(identical translation to Flow 3 — `FREDSeriesNotFoundError` → `404`,
`FREDAuthError` → `503`, `FREDTimeoutError` → `504`, `FREDUpstreamError` →
`502`) and database-side failures, new in this increment:

| Scenario | Where it originates | Exception | HTTP status |
|---|---|---|---|
| `DATABASE_URL` not configured | Checked in the route before a session is opened | *(none — early return)* | `503` |
| Database unreachable (connection refused, wrong host/port) | `sqlalchemy.exc.OperationalError` when the engine/session tries to connect | `OperationalError` | `503` |
| Unique/FK constraint violated despite the upsert logic (e.g. a genuine race) | `sqlalchemy.exc.IntegrityError` on flush/commit | `IntegrityError` | `409` |
| Any other database-layer failure | `sqlalchemy.exc.SQLAlchemyError` (base class) | `SQLAlchemyError` | `500` |

### Transaction rollback on mid-operation failure

If persistence fails *after* some work has already been flushed to
PostgreSQL but *before* the transaction commits, nothing partial is left
behind — `session_scope()`'s `except`/`rollback()` path discards
everything done inside that transaction, flushed or not:

```mermaid
sequenceDiagram
    participant R as Route
    participant SS as session_scope()
    participant Repo as SeriesRepository
    participant DB as PostgreSQL

    R->>SS: enter session_scope()
    R->>Repo: save_series(data)  (via the service)
    Repo->>DB: INSERT economic_series
    Repo->>DB: flush()  (row visible to this transaction, not committed)
    Note over Repo,DB: an error occurs before observations are saved<br/>(e.g. a constraint violation, or any other exception)
    Repo-->>R: exception propagates
    R->>SS: exception propagates out of the with-block
    SS->>DB: ROLLBACK
    Note over DB: the flushed (but never committed) series row is discarded —<br/>no economic_series row exists for this series afterward
    SS-->>R: re-raises the original exception
    R->>R: except IntegrityError / OperationalError / SQLAlchemyError
    R-->>R: translate to the appropriate HTTP status (see table above)
```

This was verified directly (not just reasoned about): a script opened a
`session_scope()`, flushed a new series row, then raised an injected
exception before committing — the series row was confirmed absent
afterward.

### Missing database configuration

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route

    C->>R: POST /api/v1/series/UNRATE/sync
    R->>R: settings.database_url is None
    R-->>C: 503 {"detail": "Database is not configured on this server."}
```

No session is opened and FRED is never called in this case — the route
short-circuits before any work begins, the same pattern used for a
missing `FRED_API_KEY`.

## Flow 6 — Historical Observations Query (success path)

`GET /api/v1/series/{series_id}/observations` reads only from PostgreSQL.
`FREDClient` never appears anywhere in this flow — no import, no
instantiation, no call.

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route (app/api/series.py)
    participant S as EconomicDataService
    participant SS as session_scope()
    participant Repo as SeriesRepository
    participant DB as PostgreSQL

    C->>R: GET /api/v1/series/UNRATE/observations?start_date=2020-01-01&limit=100&order=asc
    Note over R: FastAPI/Pydantic validate limit, offset, order,<br/>and date syntax before this handler runs
    R->>R: database_url present?
    R->>SS: enter session_scope()
    R->>S: get_observations("UNRATE", session, start_date, end_date, limit, offset, order)
    S->>S: start_date > end_date? (application-level check)
    S->>Repo: get_series_by_series_id("UNRATE")
    Repo->>DB: SELECT economic_series WHERE series_id = 'UNRATE'
    DB-->>Repo: series row
    Repo-->>S: EconomicSeries
    S->>Repo: get_observations(economic_series_id, start_date, end_date, limit, offset, order)
    Repo->>DB: SELECT count(*) FROM economic_observations WHERE economic_series_id = ? [AND date filters]
    DB-->>Repo: total
    Repo->>DB: SELECT * FROM economic_observations WHERE ... ORDER BY observation_date LIMIT ? OFFSET ?
    DB-->>Repo: page of rows
    Repo-->>S: (rows, total)
    S->>S: build SeriesObservationsResponse (observations + pagination)
    S-->>R: SeriesObservationsResponse
    R->>SS: exit session_scope() normally
    SS->>DB: COMMIT (no-op for a read, but the same owned boundary as every other DB access)
    R-->>C: 200 JSON
```

Both the count query and the page query share the same `WHERE`
conditions, which is what guarantees `pagination.total` always describes
exactly what `limit`/`offset` are paginating over.

## Flow 7 — Observations Query Failure Scenarios

| Scenario | Where it's caught | HTTP status |
|---|---|---|
| Malformed `limit`/`offset`/`order`/date syntax | FastAPI/Pydantic, before the route body runs | `422` |
| `start_date` after `end_date` | `InvalidDateRangeError` from `EconomicDataService.get_observations` | `400` |
| Series not persisted in PostgreSQL | `SeriesNotFoundError` from the service (repository returned no series row) | `404` |
| Series persisted, but no observation matches the filters | *(no exception — a normal empty result)* | `200`, `observations: []`, `total: 0` |
| `DATABASE_URL` not configured | Checked in the route before a session is opened | `503` |
| Database unreachable | `sqlalchemy.exc.OperationalError` | `503` |
| Any other database-layer failure | `sqlalchemy.exc.SQLAlchemyError` (base class) | `500` |

Note what's *not* in this table compared to Flow 5's write-side table:
`IntegrityError` has no branch here. A read-only `SELECT` cannot violate a
unique or foreign-key constraint, so there is no realistic way for this
endpoint to raise one — a handler for it would be dead code, not defense.

### Nonexistent persisted series vs. an empty filtered result

These look similar from the outside (no observations come back) but mean
different things and are handled differently:

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route
    participant S as EconomicDataService
    participant Repo as SeriesRepository
    participant DB as PostgreSQL

    rect rgb(248, 113, 113)
    Note over C,DB: Series never synced -- no row in economic_series
    C->>R: GET /api/v1/series/NOTPERSISTED/observations
    R->>S: get_observations(...)
    S->>Repo: get_series_by_series_id("NOTPERSISTED")
    Repo->>DB: SELECT ... WHERE series_id = 'NOTPERSISTED'
    DB-->>Repo: no row
    Repo-->>S: None
    S->>S: raise SeriesNotFoundError
    S-->>R: (exception propagates)
    R-->>C: 404 {"detail": "Series 'NOTPERSISTED' was not found."}
    end

    rect rgb(134, 239, 172)
    Note over C,DB: Series exists, but no observation matches the date filter
    C->>R: GET /api/v1/series/UNRATE/observations?start_date=2099-01-01
    R->>S: get_observations(...)
    S->>Repo: get_series_by_series_id("UNRATE")
    Repo->>DB: SELECT ... WHERE series_id = 'UNRATE'
    DB-->>Repo: series row (found)
    Repo-->>S: EconomicSeries
    S->>Repo: get_observations(..., start_date=2099-01-01)
    Repo->>DB: SELECT count(*) / SELECT * ... WHERE observation_date >= '2099-01-01'
    DB-->>Repo: 0 rows, total=0
    Repo-->>S: ([], 0)
    S-->>R: SeriesObservationsResponse(observations=[], pagination.total=0)
    R-->>C: 200 {"observations": [], "pagination": {"total": 0, "returned": 0, ...}}
    end
```

## Flow 8 — Transformation Query (with boundary-context retrieval)

`GET /api/v1/series/{series_id}/transform` reads only from PostgreSQL,
same as Flow 6 — `FREDClient` never appears here either. The distinctive
part of this flow is fetching enough *preceding* context to compute
correct values at the start of the requested range, then trimming that
context back out before responding.

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route (app/api/series.py)
    participant S as EconomicDataService
    participant Repo as SeriesRepository
    participant Eng as Transformation engine<br/>(app/domain/transformations.py)
    participant DB as PostgreSQL

    C->>R: GET .../UNRATE/transform?transformation=percent_change&start_date=2026-02-01
    Note over R: FastAPI/Pydantic validate transformation (Literal),<br/>window bounds (2-365 if given), and date syntax
    R->>R: database_url present?
    R->>S: get_transformed_observations("UNRATE", session, transformation, start_date, end_date, window)
    S->>S: start_date > end_date? window required/inapplicable for this transformation?
    S->>Repo: get_series_by_series_id("UNRATE")
    Repo->>DB: SELECT economic_series WHERE series_id = 'UNRATE'
    DB-->>Repo: series row
    Repo-->>S: EconomicSeries
    S->>Repo: get_observations_in_range(series.id, start_date, end_date)
    Repo->>DB: SELECT * WHERE economic_series_id = ? AND observation_date >= '2026-02-01' ORDER BY observation_date
    DB-->>Repo: requested-range rows
    Repo-->>S: requested
    Note over S: start_date given and context_size > 0 -->> fetch leading context
    S->>Repo: get_preceding_observations(series.id, before_date=start_date, count=context_size)
    Repo->>DB: SELECT * WHERE economic_series_id = ? AND observation_date < '2026-02-01' ORDER BY observation_date DESC LIMIT context_size
    DB-->>Repo: up to context_size preceding rows (most recent first)
    Repo-->>S: context (reversed back to ascending)
    S->>S: combined = context + requested  (one continuous ascending list)
    S->>Eng: percent_change(combined)
    Note over Eng: pure function -- no DB, no HTTP, no FRED;<br/>processes the list positionally, unaware<br/>any of it is "context"
    Eng-->>S: transformed (one result per input point, same length as combined)
    S->>S: output = transformed[len(context):]  (drop the context-only leading results)
    S-->>R: SeriesTransformResponse(transformation, observations=output)
    R-->>C: 200 JSON -- only dates >= 2026-02-01, but the first one's<br/>value is computed correctly against the point before it
```

The count query/page query symmetry from Flow 6 doesn't apply here —
`.../transform` has no `total`/pagination metadata at all (see Flow 9's
table and the journal for why).

## Flow 9 — Transformation Failure Scenarios

| Scenario | Where it's caught | HTTP status |
|---|---|---|
| Malformed `window`/date syntax, or an unrecognized `transformation` value | FastAPI/Pydantic, before the route body runs | `422` |
| `start_date` after `end_date` | `InvalidDateRangeError` from the service | `400` |
| `transformation=moving_average` with no `window` | `InvalidWindowError` from the service | `400` |
| `window` supplied for `absolute_change`/`percent_change` | `InvalidWindowError` from the service | `400` |
| Series not persisted in PostgreSQL | `SeriesNotFoundError` from the service | `404` |
| `DATABASE_URL` not configured | Checked in the route before a session is opened | `503` |
| Database unreachable | `sqlalchemy.exc.OperationalError` | `503` |
| Any other database-layer failure | `sqlalchemy.exc.SQLAlchemyError` (base class) | `500` |

As with Flow 7, there is no `IntegrityError` branch: this endpoint never
writes. `window`'s numeric bounds (`2`–`365`) are enforced structurally by
FastAPI whenever a value is supplied at all; whether a value is *allowed*
to be supplied depends on `transformation`, which FastAPI can't know on
its own — that cross-field decision is exactly what `InvalidWindowError`
exists for:

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route
    participant S as EconomicDataService

    rect rgb(248, 113, 113)
    Note over C,S: moving_average requested, but window omitted
    C->>R: GET .../UNRATE/transform?transformation=moving_average
    R->>S: get_transformed_observations(..., transformation="moving_average", window=None)
    S->>S: transformation == "moving_average" and window is None
    S->>S: raise InvalidWindowError("window is required when transformation=moving_average.")
    S-->>R: (exception propagates)
    R-->>C: 400 {"detail": "window is required when transformation=moving_average."}
    end

    rect rgb(248, 113, 113)
    Note over C,S: window supplied for a transformation that doesn't use one
    C->>R: GET .../UNRATE/transform?transformation=absolute_change&window=3
    R->>S: get_transformed_observations(..., transformation="absolute_change", window=3)
    S->>S: transformation != "moving_average" and window is not None
    S->>S: raise InvalidWindowError("window is not applicable to transformation=absolute_change.")
    S-->>R: (exception propagates)
    R-->>C: 400 {"detail": "window is not applicable to transformation=absolute_change."}
    end
```

## Flow 10 — Multi-Series Analysis Query (success path)

`GET /api/v1/analysis/compare` reads only from PostgreSQL, twice —
independently for `series_a` and `series_b` — then aligns and analyzes
in-process. `FREDClient` never appears anywhere in this flow.

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route (app/api/analysis.py)
    participant S as AnalysisService
    participant Repo as SeriesRepository
    participant Eng as Analysis engine<br/>(app/domain/analysis.py)
    participant DB as PostgreSQL

    C->>R: GET /analysis/compare?series_a=UNRATE&series_b=CPIAUCSL&analysis=correlation
    Note over R: FastAPI/Pydantic validate analysis (Literal)<br/>and date syntax before this handler runs
    R->>R: database_url present?
    R->>S: compare("UNRATE", "CPIAUCSL", session, analysis, start_date, end_date)
    S->>S: start_date > end_date?
    S->>Repo: get_series_by_series_id("UNRATE")
    Repo->>DB: SELECT economic_series WHERE series_id = 'UNRATE'
    DB-->>Repo: series_a row
    S->>Repo: get_series_by_series_id("CPIAUCSL")
    Repo->>DB: SELECT economic_series WHERE series_id = 'CPIAUCSL'
    DB-->>Repo: series_b row
    S->>Repo: get_observations_in_range(series_a.id, start_date, end_date)
    Repo->>DB: SELECT * WHERE economic_series_id = ? [AND date filters] ORDER BY observation_date
    DB-->>Repo: series A's observations
    S->>Repo: get_observations_in_range(series_b.id, start_date, end_date)
    Repo->>DB: SELECT * WHERE economic_series_id = ? [AND date filters] ORDER BY observation_date
    DB-->>Repo: series B's observations
    S->>Eng: align_series(observations_a, observations_b)
    Note over Eng: exact-date inner join (dict keys, never zip/position);<br/>pure -- no DB, no HTTP, no FRED
    Eng-->>S: aligned pairs (matching_pairs = len(aligned))
    S->>Eng: count_usable_pairs(aligned)
    Eng-->>S: usable_pairs
    S->>Eng: pearson_correlation(aligned)
    Note over Eng: computed over usable pairs only;<br/>null if <2 usable or zero variance
    Eng-->>S: correlation (float or null)
    S->>S: build SeriesComparisonResponse (observations=[] for correlation)
    S-->>R: SeriesComparisonResponse
    R-->>C: 200 JSON
```

Both `get_observations_in_range` calls are the *same* repository method
Increment 005 already built for single-series use — reused unchanged,
called once per compared series, with no analysis-specific repository
method added.

## Flow 11 — Multi-Series Analysis Failure Scenarios

| Scenario | Where it's caught | HTTP status |
|---|---|---|
| Malformed date syntax, or an unrecognized `analysis` value | FastAPI/Pydantic, before the route body runs | `422` |
| Missing `series_a` or `series_b` (required query params) | FastAPI/Pydantic, before the route body runs | `422` |
| `start_date` after `end_date` | `InvalidDateRangeError` from the service | `400` |
| `series_a` not persisted in PostgreSQL | `SeriesNotFoundError` from the service, naming `series_a` | `404` |
| `series_b` not persisted in PostgreSQL | `SeriesNotFoundError` from the service, naming `series_b` | `404` |
| `DATABASE_URL` not configured | Checked in the route before a session is opened | `503` |
| Database unreachable | `sqlalchemy.exc.OperationalError` | `503` |
| Any other database-layer failure | `sqlalchemy.exc.SQLAlchemyError` (base class) | `500` |

As with Flows 7 and 9, there is no `IntegrityError` branch — this endpoint
never writes.

### Zero matching dates and undefined correlation — both valid `200`s, not errors

Neither of these is a failure; both are legitimate answers a caller needs
to be able to receive without the response looking like something broke:

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route
    participant S as AnalysisService
    participant Eng as Analysis engine

    rect rgb(134, 239, 172)
    Note over C,Eng: Zero matching dates (e.g. a date range outside both series' history)
    C->>R: GET /analysis/compare?series_a=UNRATE&series_b=CPIAUCSL&analysis=aligned&start_date=2099-01-01
    R->>S: compare(...)
    S->>Eng: align_series([], [])
    Eng-->>S: []  (no common dates)
    S-->>R: SeriesComparisonResponse(matching_pairs=0, usable_pairs=0, observations=[])
    R-->>C: 200 {"matching_pairs": 0, "usable_pairs": 0, "observations": [], "correlation": null}
    end

    rect rgb(134, 239, 172)
    Note over C,Eng: Correlation requested, but fewer than 2 usable pairs or zero variance
    C->>R: GET /analysis/compare?series_a=UNRATE&series_b=UNRATE&analysis=correlation&start_date=2026-08-01&end_date=2026-08-01
    R->>S: compare(...)
    S->>Eng: align_series(...) -- one matching date
    Eng-->>S: [one pair]
    S->>Eng: pearson_correlation([one pair])
    Note over Eng: n=1 usable pair < 2 -> return None<br/>(never ZeroDivisionError, NaN, or inf)
    Eng-->>S: None
    S-->>R: SeriesComparisonResponse(matching_pairs=1, usable_pairs=1, correlation=null)
    R-->>C: 200 {"matching_pairs": 1, "usable_pairs": 1, "correlation": null}
    end
```

## Flow 12 — Composable Pipeline (raw/raw and mixed transformed composition)

`POST /api/v1/analysis/pipeline` reads only from PostgreSQL; `FREDClient`
never appears here either. Each side is resolved independently (raw
persisted values, or transformed via the exact same pure functions
`.../transform` uses) *before* the two sides are aligned.

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route (app/api/analysis.py)
    participant S as AnalysisService
    participant Repo as SeriesRepository
    participant TEng as Transformation engine<br/>(app/domain/transformations.py)
    participant AEng as Analysis engine<br/>(app/domain/analysis.py)
    participant DB as PostgreSQL

    C->>R: POST /analysis/pipeline<br/>{series_a: {CPIAUCSL, percent_change}, series_b: {UNRATE}, analysis: correlation}
    Note over R: Pydantic validates the whole body structurally<br/>(transformation type, window bounds if given, analysis type)
    R->>R: database_url present?
    R->>S: pipeline(request, session)
    S->>S: (1) validate: start_date<=end_date; each side's transformation applicability
    S->>Repo: (2) get_series_by_series_id("CPIAUCSL"), get_series_by_series_id("UNRATE")
    Repo->>DB: SELECT economic_series WHERE series_id IN (...)
    DB-->>Repo: both series rows
    Note over S,DB: (3)-(6) per series, independently
    S->>Repo: get_observations_in_range(series_a.id, ...)
    Repo->>DB: SELECT * WHERE economic_series_id = ? ORDER BY observation_date
    DB-->>Repo: series A's requested-range observations
    S->>TEng: percent_change(observations_a)
    Note over TEng: pure -- no DB, no HTTP, no FRED;<br/>receives plain Observation(date, value)
    TEng-->>S: series A's FINAL values (percent_change results)
    S->>Repo: get_observations_in_range(series_b.id, ...)
    Repo->>DB: SELECT * WHERE economic_series_id = ? ORDER BY observation_date
    DB-->>Repo: series B's observations (no transformation requested -- used as-is)
    S->>AEng: (7) align_series(final_a, final_b)
    Note over AEng: exact-date inner join over the FINAL values --<br/>unaware either side was ever transformed
    AEng-->>S: aligned pairs
    S->>AEng: (8) pearson_correlation(aligned)
    AEng-->>S: correlation
    S->>S: (9) build PipelineResponse (series_a.transformation = {percent_change, null})
    S-->>R: PipelineResponse
    R-->>C: 200 JSON
```

Raw+raw through this endpoint reproduces `GET /analysis/compare`'s result
exactly for the same series/analysis/dates — verified directly by
comparing the returned correlation coefficient from both endpoints to
full float precision.

## Flow 13 — Composable Pipeline: boundary context with `start_date`

The critical ordering: context is fetched *before* transforming, and
trimmed *before* aligning — never the reverse.

```mermaid
sequenceDiagram
    participant S as AnalysisService
    participant Repo as SeriesRepository
    participant TEng as Transformation engine
    participant AEng as Analysis engine

    Note over S: request: series_a = percent_change(CPIAUCSL), start_date = Feb
    S->>Repo: get_observations_in_range(series_a.id, start_date=Feb, end_date=None)
    Repo-->>S: [Feb, Mar, ...]  (requested range only)
    Note over S: start_date given -> fetch 1 preceding point (percent_change's context_size)
    S->>Repo: get_preceding_observations(series_a.id, before_date=Feb, count=1)
    Repo-->>S: [Jan]  (context; strictly before Feb)
    S->>S: combined = [Jan] + [Feb, Mar, ...]
    S->>TEng: percent_change(combined)
    TEng-->>S: [Jan: null, Feb: 5.0, Mar: ...]  (Feb correctly computed against Jan)
    S->>S: output = transformed[1:]  -- drop Jan (the context), keep Feb onward
    Note over S: output = [Feb: 5.0, Mar: ...] -- Jan never reaches alignment
    S->>AEng: align_series(output, series_b's final values)
    Note over AEng: only Feb onward can possibly appear in the aligned result --<br/>Jan was never a candidate, by construction
```

This was verified by exact-value comparison (the same technique used in
Increment 005): the pipeline's Feb value for `percent_change(CPIAUCSL)`
with `start_date=Feb` matched the unfiltered single-series
`GET .../transform` computation for Feb exactly, and Jan was confirmed
absent from the pipeline's `observations`. The same check was repeated
for `absolute_change` and for `moving_average(window=4)` (which needs 3
preceding points, not 1) with matching results.

## Flow 14 — Composable Pipeline Failure/Validation Scenarios

| Scenario | Where it's caught | HTTP status |
|---|---|---|
| Malformed request body, unsupported `transformation.type`, or unsupported `analysis` | FastAPI/Pydantic, before the route body runs | `422` |
| `transformation.window` outside `[2, 365]` | FastAPI/Pydantic (`TransformationSpec.window`'s `Field(ge=2, le=365)`) | `422` |
| `start_date` after `end_date` | `InvalidDateRangeError` from the service | `400` |
| `type=moving_average` with no `window` | `InvalidWindowError` from the service (reused from Increment 005) | `400` |
| `window` supplied for `absolute_change`/`percent_change` | `InvalidWindowError` from the service (reused from Increment 005) | `400` |
| `series_a`/`series_b` not persisted | `SeriesNotFoundError` from the service, naming the missing one | `404` |
| `DATABASE_URL` not configured | Checked in the route before a session is opened | `503` |
| Database unreachable | `sqlalchemy.exc.OperationalError` | `503` |
| Any other database-layer failure | `sqlalchemy.exc.SQLAlchemyError` (base class) | `500` |

As with every other read-only endpoint in this project, there is no
`IntegrityError` branch — this endpoint never writes. Note that the
window-applicability rule maps to the *same* status code (`400`) via the
*same* exception class (`InvalidWindowError`) as the single-series
`.../transform` endpoint's identical rule (Flow 9) — not a new,
differently-coded validation path for what is conceptually the same
check.

## Flow 15 — AI Query: no tool needed

The simplest case: the model can answer without touching persisted data
at all (e.g. small talk, or a question this system's data genuinely can't
answer).

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route (app/api/ai.py)
    participant S as AIService
    participant AI as OpenAI Responses API

    C->>R: POST /ai/query {"message": "What's the current price of gold?"}
    R->>R: OPENAI_API_KEY/MODEL and DATABASE_URL present?
    R->>S: query(message, session)
    S->>AI: responses.create(instructions=SYSTEM_INSTRUCTIONS, input=[user message], tools=[...])
    AI-->>S: response.output has no function_call items
    Note over S: loop's first check finds nothing to execute -- exits immediately
    S-->>R: AIQueryResult(answer="I don't have access to that...", tools_used=[])
    R-->>C: 200 {"answer": "...", "tools_used": []}
```

Verified with a real request: asked about gold prices (data this system
has no series for), the model correctly declined to invent a number and
called no tool.

## Flow 16 — AI Query: single-tool round

A request needing one persisted-data lookup or transformation.
`get_observations` and `transform_series` follow the identical shape;
this shows `transform_series`.

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route
    participant S as AIService
    participant AI as OpenAI Responses API
    participant D as Tool dispatcher<br/>(app/services/ai_tools.py)
    participant ED as EconomicDataService

    C->>R: POST /ai/query {"message": "How has UNRATE changed? Use absolute_change."}
    R->>S: query(message, session)
    S->>AI: responses.create(instructions=..., input=[user message], tools=[...])
    AI-->>S: response.output = [function_call: transform_series({"series_id":"UNRATE","transformation":"absolute_change"})]
    Note over S: round 1 of MAX_TOOL_ROUNDS=4
    S->>S: parse call.arguments as JSON
    S->>D: execute_tool("transform_series", {...}, session)
    D->>D: TransformSeriesArgs.model_validate(...) -- structural validation
    D->>ED: get_transformed_observations("UNRATE", session, "absolute_change", ...)
    ED-->>D: SeriesTransformResponse (same result GET .../transform would return)
    D-->>S: {"ok": true, "result": {...}}
    S->>S: tools_used.append({"transform_series", {...}})
    S->>AI: responses.create(input=[function_call_output], previous_response_id=...)
    AI-->>S: response.output = [message] -- no more function_call items
    S-->>R: AIQueryResult(answer="...", tools_used=[transform_series call])
    R-->>C: 200 {"answer": "The unemployment rate...", "tools_used": [...]}
```

Verified with a real request and real OpenAI response: the model called
`transform_series` with exactly these arguments, and the returned table's
values matched the deterministic `absolute_change` engine's known output
exactly (e.g. `+0.1` for 2026-02-01).

## Flow 17 — AI Query: two-series tool call

`analyze_series` maps directly onto `AnalysisService.pipeline` — the
exact same code path as `POST /analysis/pipeline` (Flow 12), just invoked
by the model instead of a direct HTTP call.

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route
    participant S as AIService
    participant AI as OpenAI Responses API
    participant D as Tool dispatcher
    participant AS as AnalysisService

    C->>R: POST /ai/query {"message": "Correlate UNRATE and CPIAUCSL."}
    R->>S: query(message, session)
    S->>AI: responses.create(...)
    AI-->>S: function_call: analyze_series({"series_a":{"series_id":"UNRATE"},<br/>"series_b":{"series_id":"CPIAUCSL"},"analysis":"correlation"})
    S->>D: execute_tool("analyze_series", {...}, session)
    D->>D: PipelineRequest.model_validate(...) -- the SAME model /analysis/pipeline uses
    D->>AS: pipeline(request, session)
    Note over AS: identical to Flow 12 -- align, then Pearson correlation
    AS-->>D: PipelineResponse {correlation: -0.803...}
    D-->>S: {"ok": true, "result": {...}}
    S->>AI: responses.create(input=[function_call_output], previous_response_id=...)
    AI-->>S: final message: "The correlation is approximately -0.80..."
    S-->>R: AIQueryResult(answer="...", tools_used=[analyze_series call])
    R-->>C: 200 JSON
```

Verified with a real request: the model reported "-0.80" (matching
`-0.8030258377001954` rounded) and explicitly noted the relationship
without claiming causation, per the system instruction.

## Flow 18 — AI Query Failure Scenarios

| Scenario | Where it's caught | Result |
|---|---|---|
| `OPENAI_API_KEY`/`OPENAI_MODEL` not configured | Route, before `AIService` is constructed | `503` |
| `DATABASE_URL` not configured | Route, before `AIService` is constructed | `503` |
| OpenAI rejects the API key | `AIService._create_response`, `AuthenticationError` | `503`, generic message |
| OpenAI unreachable/timed out | `AIService._create_response`, `APITimeoutError`/`APIConnectionError` | `503`, generic message |
| Model requests an unknown tool name | `execute_tool` returns `{"ok": false, "error": {"type": "unknown_tool", ...}}` | Loop continues; model sees the error and can respond accordingly |
| Model's tool arguments don't validate (or aren't valid JSON at all) | `execute_tool` / `AIService._parse_arguments` | Loop continues; same structured error shape |
| Series in a tool call isn't persisted | `execute_tool` catches `SeriesNotFoundError` | Loop continues; structured `series_not_found` error |
| Database unavailable during a tool call | `execute_tool` catches `OperationalError` | Loop continues; structured `database_unavailable` error |
| Model keeps requesting tools past `MAX_TOOL_ROUNDS` | `AIService.query`, `ToolRoundLimitExceededError` | `503` |
| Anything genuinely unexpected | Not caught in the AI path | FastAPI's default `500` |

The middle four rows never end the request — they hand the model a
structured error it can react to (apologize, try different arguments, or
explain the limitation), which is why `POST /ai/query` can still return
`200` even when a tool call inside it failed. Verified directly:

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route
    participant S as AIService
    participant AI as OpenAI Responses API
    participant D as Tool dispatcher

    C->>R: POST /ai/query {"message": "Show me NOTPERSISTED"}
    R->>S: query(...)
    S->>AI: responses.create(...)
    AI-->>S: function_call: get_observations({"series_id": "NOTPERSISTED"})
    S->>D: execute_tool("get_observations", {...}, session)
    D->>D: EconomicDataService.get_observations(...) raises SeriesNotFoundError
    D-->>S: {"ok": false, "error": {"type": "series_not_found", "message": "Series 'NOTPERSISTED' is not persisted."}}
    S->>AI: responses.create(input=[function_call_output], previous_response_id=...)
    AI-->>S: final message: "That series isn't available in our persisted data."
    S-->>R: AIQueryResult(answer="...", tools_used=[get_observations call])
    R-->>C: 200 {"answer": "...", "tools_used": [...]}  -- not an error response
```

Also verified: a client that always requests another tool call was
stopped exactly at round 4 (`ToolRoundLimitExceededError`), never running
indefinitely; the round counter counts *rounds* (one round may contain
several parallel tool calls, verified separately), not individual calls.

## Flow 19 — Series Discovery: local + FRED merge

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route (app/api/series.py)
    participant DS as SeriesDiscoveryService
    participant Repo as SeriesRepository
    participant FC as FREDClient
    participant FRED as FRED REST API
    participant DB as PostgreSQL

    C->>R: GET /api/v1/series/search?q=unemployment&limit=10
    R->>R: q.strip() non-empty? database configured?
    R->>DS: search("unemployment", 10, session)
    DS->>Repo: search_series("unemployment", 10)
    Repo->>DB: ILIKE '%unemployment%' on series_id OR title
    DB-->>Repo: [UNRATE]  (local match)
    Repo-->>DS: [UNRATE]
    DS->>FC: search_series("unemployment", limit=10)
    FC->>FRED: GET fred/series/search?search_text=unemployment&search_type=full_text&...
    FRED-->>FC: 200 {"seriess": [UNRATE, UNRATENSA, U6RATE, ...]}
    FC-->>DS: raw FRED rows (catalog metadata only)
    DS->>DS: merge by series_id (UNRATE deduplicated: persisted=true, discovery_source=local_and_fred)
    DS->>DS: rank: exact-id tier, then persisted tier, then FRED search_rank order; limit applied last
    DS-->>R: SeriesSearchResponse(candidates=[...], external_search_available=true)
    R-->>C: 200 JSON
```

Route ordering matters here: `GET /search` is declared before
`GET /{series_id}` in `app/api/series.py` specifically so `"search"`
is never captured as a `series_id` path parameter — verified directly
(not just by reading the declaration order) by mocking
`FREDClient.get_series_info` to raise if ever called and
`FREDClient.search_series` to succeed, then confirming a real request
to `/series/search` returns a clean discovery response with
`get_series_info` never invoked.

Verified with a real FRED response and a persisted local row: searching
"unemployment" surfaces `UNRATE` as a single, deduplicated,
`persisted: true`, `discovery_source: "local_and_fred"` candidate with
FRED's richer metadata (frequency, seasonal adjustment, observation
range, popularity) layered onto the local match — never two separate
rows for the same series.

## Flow 20 — Series Discovery: FRED degradation, local results survive

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route
    participant DS as SeriesDiscoveryService
    participant Repo as SeriesRepository
    participant FC as FREDClient
    participant FRED as FRED REST API

    C->>R: GET /api/v1/series/search?q=unemployment
    R->>DS: search("unemployment", 10, session)
    DS->>Repo: search_series(...)
    Repo-->>DS: [UNRATE]  (local match still found)
    DS->>FC: search_series("unemployment", limit=10)
    FC->>FRED: GET fred/series/search?...
    Note over FC,FRED: timeout, auth rejection, or upstream failure
    FC->>FC: raise FREDTimeoutError / FREDAuthError / FREDUpstreamError
    DS->>DS: except FREDError -> external_search_available = False
    DS-->>R: SeriesSearchResponse(candidates=[UNRATE], external_search_available=false)
    R-->>C: 200 JSON  -- NOT an error; local results are still useful
```

Verified directly for all three FRED exception types, plus the
`FRED_API_KEY`-unconfigured case (no `FREDClient` even constructed):
every one degrades identically — `200`, local candidates intact,
`external_search_available: false`. The search endpoint never becomes
unavailable merely because FRED's catalog search is unavailable when a
useful local result exists.

## Flow 21 — Series Discovery: no local match and FRED failure

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route
    participant DS as SeriesDiscoveryService
    participant Repo as SeriesRepository
    participant FC as FREDClient

    C->>R: GET /api/v1/series/search?q=totallyunknownXYZ
    R->>DS: search("totallyunknownXYZ", 10, session)
    DS->>Repo: search_series(...)
    Repo-->>DS: []  (no local match)
    DS->>FC: search_series("totallyunknownXYZ", limit=10)
    FC->>FC: raise FREDUpstreamError (or any FREDError)
    DS->>DS: except FREDError -> external_search_available = False
    DS-->>R: SeriesSearchResponse(candidates=[], external_search_available=false)
    R-->>C: 200 {"query": "...", "candidates": [], "external_search_available": false}
```

This is the existing `SeriesDiscoveryService` contract, unchanged,
newly locked down by a permanent test: no local match combined with a
FRED failure is **not** an error — it's an honestly empty result. The
service never raises here; "nothing was confidently found" and
"something went wrong" are deliberately different outcomes, consistent
with how every other read path in this project treats an empty result
as success, not failure.

## Flow 22 — Inflation Monitor (`inflation_v1.0`)

`GET /api/v1/monitors/inflation` reads only from PostgreSQL, for exactly
the four canonical series named in
[docs/methodology/inflation-monitor-v1.0.md](../methodology/inflation-monitor-v1.0.md).
`FREDClient` never appears anywhere in this flow, and no AI service is
imported or called. All four series are fetched independently; a series
that isn't persisted at all yields an empty observation list rather
than an error, so the flow below is identical whether zero, some, or
all four canonical series have data.

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route (app/api/inflation.py)
    participant S as InflationMonitorService
    participant SS as session_scope()
    participant Repo as SeriesRepository
    participant DB as PostgreSQL
    participant D as app.domain.inflation (pure)

    C->>R: GET /api/v1/monitors/inflation
    R->>R: database_url present?
    R->>SS: enter session_scope()
    R->>S: get_result(session)
    loop for each of PCEPILFE, CPILFESL, PCEPI, CPIAUCSL
        S->>Repo: get_series_by_series_id(series_id)
        Repo->>DB: SELECT economic_series WHERE series_id = ?
        DB-->>Repo: row or None
        alt series persisted
            Repo-->>S: EconomicSeries
            S->>Repo: get_observations_in_range(economic_series_id, None, None)
            Repo->>DB: SELECT * FROM economic_observations WHERE economic_series_id = ? ORDER BY observation_date
            DB-->>Repo: all rows (values may include NULL, per FRED's "." convention)
            Repo-->>S: list[Observation]
        else series not persisted
            S->>S: observations = [] (never SeriesNotFoundError)
        end
    end
    S->>D: compute_inflation_monitor_result(primary, confirmation, target, headline_cpi)
    Note over D: pure -- no session, no HTTP, no FRED, no OpenAI,<br/>no environment access; exact-calendar-month endpoint<br/>resolution throughout (never row-position)
    D-->>S: InflationMonitorResult
    S-->>R: InflationMonitorResult
    R->>SS: exit session_scope() normally
    SS->>DB: COMMIT (no-op for a read, but the same owned boundary as every other DB access)
    R-->>C: 200 JSON (methodology_id, data_basis, target,<br/>underlying_momentum, confirmation, headline_context,<br/>periods, coverage)
```

Missing or insufficient economic data for any component is **not** an
error: `compute_inflation_monitor_result` always returns a complete,
typed result, with that component's own `INSUFFICIENT_DATA`/
`available: false`/`UNAVAILABLE` value inside a normal `200` response.
Only a genuine database/infrastructure failure produces a non-`200`
response — the same infrastructure-vs-economic-data distinction every
other PostgreSQL-backed route in this project already makes.

### Flow 23 — Inflation Monitor Failure Scenarios

| Scenario | Where it's caught | HTTP status |
|---|---|---|
| `DATABASE_URL` not configured | Checked in the route before a session is opened | `503` |
| Database unreachable | `sqlalchemy.exc.OperationalError` | `503` |
| Any other database-layer failure | `sqlalchemy.exc.SQLAlchemyError` (base class) | `500` |
| One or more canonical series not persisted at all | *(no exception — that component's own `INSUFFICIENT_DATA`/`available: false`)* | `200` |
| A persisted series has insufficient trailing history (e.g. brand new) | *(no exception — `state: "INSUFFICIENT_DATA"`, `missing_required_metrics` names which of r_3m/r_6m/r_12m)* | `200` |
| A required calendar-month endpoint is missing (e.g. the real 2025-10-01 Core CPI gap) | *(no exception — the affected derived metric is `null`; an unrelated later period whose own endpoints are all present remains valid)* | `200` |
| No period exists where both Core PCE and Core CPI have a valid state | *(no exception — `confirmation.latest_common_period: null`, `confirmation.relationship: "UNAVAILABLE"`)* | `200` |

No scenario in this table ever substitutes a different series, fetches
from FRED, triggers ingestion, or calls AI to resolve a gap.

## Flow 24 — Inflation What Changed (`inflation_what_changed_v1.0`)

`GET /api/v1/monitors/inflation/changes` reads only from PostgreSQL,
for the exact same four canonical series as Flow 22. It computes a
**month-over-month** comparison, section by section, each independently
anchored per
[docs/methodology/inflation-what-changed-v1.0.md](../methodology/inflation-what-changed-v1.0.md):
ordinary sections (primary momentum, target, headline PCE, headline
CPI) anchor to that series' own `latest_observation_period`; the
confirmation section anchors to `latest_shared_observation_period` (a
NEW period-selection concept this contract introduces — see the note
below) — never to `inflation_v1.0`'s own "latest valid" concepts, so an
unclassifiable current period is correctly reported as an availability
change rather than silently skipped.

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route (app/api/inflation.py)
    participant S as InflationMonitorService
    participant SS as session_scope()
    participant Repo as SeriesRepository
    participant DB as PostgreSQL
    participant D as app.domain.inflation (pure)
    participant W as app.domain.inflation_what_changed (pure)

    C->>R: GET /api/v1/monitors/inflation/changes
    R->>R: database_url present?
    R->>SS: enter session_scope()
    R->>S: get_what_changed_result(session)
    loop for each of PCEPILFE, CPILFESL, PCEPI, CPIAUCSL
        S->>Repo: get_series_by_series_id / get_observations_in_range
        Repo->>DB: SELECT ...
        DB-->>Repo: rows (or none -- observations = [], never an error)
        Repo-->>S: list[Observation]
    end
    Note over S,D: period selection, per section -- NOT the comparator's job
    S->>D: month_over_month_series_momentum(primary_obs, "PCEPILFE")
    D-->>S: (previous_period, current_period, previous_evidence, current_evidence)
    S->>D: month_over_month_target(target_obs)
    D-->>S: (previous_period, current_period, previous_evidence, current_evidence)
    S->>D: month_over_month_series_momentum(target_obs, "PCEPI")  %% headline PCE
    D-->>S: (...)
    S->>D: month_over_month_series_momentum(headline_cpi_obs, "CPIAUCSL")
    D-->>S: (...)
    S->>D: month_over_month_confirmation(primary_obs, confirmation_obs)
    Note over D: current_confirmation_period = latest_shared_observation_period(...)<br/>-- date-set intersection only, NOT inflation_v1.0's latest_common_period
    D-->>S: (previous_period, current_period, 4x SeriesMomentumResult, 2x relationship)
    S->>D: compute_inflation_monitor_result(...)  %% optional convenience snapshot only
    D-->>S: InflationMonitorResult
    Note over S,W: comparison -- the ONLY step touching app.domain.inflation_what_changed
    S->>W: compare_series_momentum_section / compare_target_section / compare_confirmation_section (x5)
    Note over W: pure diffing only -- W never imports app.domain.inflation<br/>(enforced by the architectural-independence test)
    W-->>S: 5x SectionChanges
    S->>W: assemble_what_changed_result(...)
    W-->>S: InflationWhatChangedResult
    S-->>R: InflationWhatChangedResult
    R->>SS: exit session_scope() normally
    SS->>DB: COMMIT (no-op for a read)
    R-->>C: 200 JSON (5 sections, flattened ordered `changes`, summary flags)
```

**`latest_shared_observation_period`** (new, this contract only): the
latest calendar month for which *both* Core PCE and Core CPI have *any*
observation row, regardless of classifiability — a plain intersection
of the two already-fetched observation date sets, `max()`. It never
modifies `inflation_v1.0`, never replaces `latest_common_period` in the
Monitor (Flow 22 is completely unaffected), and requires no new
repository query — both observation lists are already in memory from
the loop above.

Missing or insufficient economic data for any section is **not** an
error: each section reports its own `comparison_available`/
`INSUFFICIENT_DATA`/`UNAVAILABLE` evidence inside a normal `200`
response. Only a genuine database/infrastructure failure produces a
non-`200` response.

### Flow 25 — Inflation What Changed Failure Scenarios

| Scenario | Where it's caught | HTTP status |
|---|---|---|
| `DATABASE_URL` not configured | Checked in the route before a session is opened | `503` |
| Database unreachable | `sqlalchemy.exc.OperationalError` | `503` |
| Any other database-layer failure | `sqlalchemy.exc.SQLAlchemyError` (base class) | `500` |
| A section's series has no observation at all (no current anchor) | *(no exception — `comparison_available: false`, both periods `null`, `changes: []`)* | `200` |
| A section's current period is classifiable but its exact previous calendar month is not (e.g. July valid / August missing) | *(no exception — `availability_lost: true`, no fabricated state transition)* | `200` |
| A section's current period is itself unclassifiable (e.g. August missing, latest observed) | *(no exception — `current_evidence.state: "INSUFFICIENT_DATA"`, still `comparison_available: true`)* | `200` |
| Confirmation has a shared observation row but one side's canonical state fails there | *(no exception — `current_relationship: "UNAVAILABLE"`, `confirmation_availability_lost: true`)* | `200` |
| Core PCE and Core CPI share no observation date anywhere in history | *(no exception — `confirmation_changes.comparison_available: false`)* | `200` |

No scenario in this table ever searches backward past the exact
previous calendar month, substitutes a different series, fetches from
FRED, triggers ingestion, or calls AI to resolve a gap.

## Flow 26 — Frontend Local Development Proxy

The infrastructure path every frontend request takes in local
development, independent of which endpoint or page triggers it — see
Flow 27 below for what actually calls this now that the `/inflation`
page (Increment #16B) is real:

```mermaid
sequenceDiagram
    participant B as Browser
    participant V as Vite dev server (localhost:5173)
    participant F as FastAPI (localhost:8000)

    B->>V: GET /api/v1/monitors/inflation
    Note over V: frontend/vite.config.ts's server.proxy --<br/>matches the "/api" prefix, forwards unchanged
    V->>F: GET /api/v1/monitors/inflation
    F-->>V: 200 JSON (canonical InflationMonitorResult)
    V-->>B: 200 JSON (proxied through, unmodified)
```

Because the proxy makes every request same-origin from the browser's
perspective, **no backend CORS configuration exists or is required**.
Application code never hardcodes `http://localhost:8000` — it calls
relative paths, and the proxy target
(`frontend/vite.config.ts`'s `BACKEND_PROXY_TARGET`, default
`http://localhost:8000`) is a Node-side, dev-only setting, never bundled
into the browser. In production, the built frontend instead uses the
explicit, non-secret `VITE_API_BASE_URL` (`frontend/.env.example`) to
address the deployed API directly — no proxy exists outside local
development.

## Flow 27 — `/inflation` Page Load (Increment #16B)

`frontend/src/pages/Inflation.tsx` calls `useApiResource(getInflationMonitor)`
and `useApiResource(getInflationWhatChanged)` in the same render, each
independently owning its own `loading`/`success`/`error` state (see
`frontend/src/api/useApiResource.ts`). Neither call waits on, retries
from, or fabricates data for the other.

```mermaid
sequenceDiagram
    participant B as Browser (InflationPage)
    participant H1 as useApiResource(getInflationMonitor)
    participant H2 as useApiResource(getInflationWhatChanged)
    participant API as FastAPI (via Flow 26's proxy in dev)

    par independent requests
        B->>H1: mount
        H1->>API: GET /api/v1/monitors/inflation
    and
        B->>H2: mount
        H2->>API: GET /api/v1/monitors/inflation/changes
    end
    API-->>H1: 200 InflationMonitorResult (or non-2xx / network failure)
    API-->>H2: 200 InflationWhatChangedResult (or non-2xx / network failure)
    H1-->>B: {status: "success", data} | {status: "error", error: ApiError} | {status: "loading"}
    H2-->>B: {status: "success", data} | {status: "error", error: ApiError} | {status: "loading"}
    Note over B: Page composes both states independently --<br/>see the rendering table below.
```

How the page renders each combination — the only failure mode
`ApiError` ever represents here is *infrastructure* (network/HTTP); a
`200` carrying `state: "INSUFFICIENT_DATA"`, `relationship:
"UNAVAILABLE"`, or `comparison_available: false` is `{status:
"success"}` and rendered as normal canonical content, never routed
through the error path:

| Monitor state | What Changed state | Rendered result |
|---|---|---|
| loading | loading | `LoadingSkeleton` (role="status") in both slots; no numbers rendered anywhere |
| success | success | `InflationHero`, `WhatChangedSection`, `MomentumMetrics`, `TargetPanel`, `ConfirmationPanel`, `HeadlineContext`, `MethodologyDisclosure` — full page |
| error | success | `ErrorMessage` ("Inflation data could not be loaded.", with Retry) in place of the monitor-driven sections; `WhatChangedSection` still renders normally |
| success | error | Monitor-driven sections render normally; `ErrorMessage` ("What changed could not be loaded.", with Retry) in place of `WhatChangedSection` |
| error | error | Both `ErrorMessage`s render; nothing else on the page claims to be inflation data |

Clicking a section's Retry button calls that resource's own `reload()`
(an incrementing token that re-runs its effect) — it never touches the
other resource. Every economic value, state, relationship, and period
shown is exactly what the corresponding endpoint returned;
`frontend/src/lib/format.ts` and `frontend/src/lib/inflationLabels.ts`
only format/label already-canonical values (see
`docs/architecture/current-architecture.md`'s "Frontend architecture"
for the full section-by-section breakdown, and
`frontend/src/test/no-economic-logic.test.ts` for the guard preventing
any of this from silently becoming a second implementation of
`inflation_v1.0` / `inflation_what_changed_v1.0`).

## Flow 28 — Release Calendar Read (`GET /api/v1/releases`, Increment #17A)

Database-only, exactly like `.../observations`/`.../transform` — never
calls FRED. Implements
[docs/architecture/release-intelligence-v1.md](./release-intelligence-v1.md)
#9/#10.

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route (app/api/releases.py)
    participant S as ReleaseReadService
    participant SS as session_scope()
    participant Repo as ReleaseRepository
    participant DB as PostgreSQL
    participant D as app.domain.releases (pure)

    C->>R: GET /api/v1/releases?start_date&end_date&limit&offset&order
    R->>R: database_url present? as_of_date = today (UTC)
    R->>SS: enter session_scope()
    R->>S: list_releases(session, filters..., as_of_date)
    S->>Repo: list_occurrences(start_date, end_date, limit, offset, order)
    Repo->>DB: SELECT economic_releases JOIN release_occurrences WHERE ... ORDER BY scheduled_date, name, id
    DB-->>Repo: page of (EconomicRelease, ReleaseOccurrence) rows + total count
    Repo-->>S: (rows, total)
    loop for each row
        S->>D: classify_schedule_status(scheduled_date, as_of_date)
        Note over D: pure -- no session, no HTTP, no FRED,<br/>as_of_date passed explicitly, never date.today()
        D-->>S: "SCHEDULED" | "PAST_DUE"
    end
    S-->>R: ReleaseListResponse (releases, pagination)
    R->>SS: exit session_scope() normally
    R-->>C: 200 JSON
```

`ReleaseReadService` has no method that accepts or constructs a
`FREDClient` at all (checked structurally, not just by convention --
see `tests/integration/test_release_calendar_service.py`). A scheduled
date being `PAST_DUE` carries no claim that data is or isn't available
-- that signal doesn't exist anywhere in this response.

| Scenario | Where it's caught | HTTP status |
|---|---|---|
| `DATABASE_URL` not configured | Checked in the route before a session is opened | `503` |
| `start_date > end_date` | `InvalidDateRangeError` | `400` |
| Malformed query param (bad type, `limit` out of bounds, invalid `order`) | FastAPI/Pydantic query validation, before the route body runs | `422` |
| Database unreachable | `OperationalError` | `503` |
| Any other database-layer failure | `SQLAlchemyError` | `500` |
| FRED unreachable/unconfigured/never synced | *(no exception -- this endpoint never calls FRED; returns whatever is persisted, possibly nothing)* | `200` |

## Flow 29 — Release Calendar Sync (`POST /api/v1/releases/sync`, Increment #17A)

The one explicit, separate write path — never invoked by a read, never
scheduled/automatic. Mirrors `POST /series/{id}/sync`'s shape, widened
to the whole curated catalog since there is no single-release entry
point from the frontend.

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route (app/api/releases.py)
    participant S as ReleaseSyncService
    participant Repo as ReleaseRepository
    participant F as FREDClient
    participant FRED as FRED release/dates API
    participant DB as PostgreSQL

    C->>R: POST /api/v1/releases/sync
    R->>R: fred_api_key and database_url present?
    R->>S: sync_all(session)
    S->>Repo: get_active_releases()
    Repo->>DB: SELECT economic_releases WHERE active
    DB-->>Repo: curated, active releases (deterministic name order)
    loop for each active release, independently
        S->>F: get_release_dates(provider_release_id)
        F->>FRED: GET /release/dates?release_id=...&include_release_dates_with_no_data=true
        alt success
            FRED-->>F: {"release_dates": [{release_id, date}, ...]}
            F-->>S: list[FredReleaseDate] (normalized, date-only)
            loop for each date
                S->>Repo: upsert_occurrence(release.id, date)
                Repo->>DB: existing? update last_seen_at : insert (first_seen_at = last_seen_at = now())
            end
            S->>S: record this release under "synced"
        else FRED failure (auth/timeout/upstream/malformed)
            F-->>S: FREDAuthError | FREDTimeoutError | FREDUpstreamError
            S->>S: record this release under "failed" (safe, generic message) -- continue the loop
        end
    end
    S-->>R: ReleaseSyncResponse (synced, failed)
    R-->>C: 200 JSON
```

One release's FRED failure never aborts the loop and never touches any
previously persisted occurrence for any release (`ReleaseRepository`
has no delete method at all). Only a configuration or database failure
raises at the route level:

| Scenario | Where it's caught | HTTP status |
|---|---|---|
| `FRED_API_KEY` not configured | Checked in the route before a client is constructed | `503` |
| `DATABASE_URL` not configured | Checked in the route before a session is opened | `503` |
| Auth failure | `FREDAuthError` | *(per-release `failed` entry, route still `200`)* |
| Timeout | `FREDTimeoutError` | *(per-release `failed` entry, route still `200`)* |
| Upstream/malformed | `FREDUpstreamError` | *(per-release `failed` entry, route still `200`)* |
| Database unreachable | `OperationalError` | `503` |
| Any other database-layer failure | `SQLAlchemyError` | `500` |

Nothing in either flow ever writes `EconomicObservation`, recomputes a
monitor, or imports AI/news — checked structurally by
`tests/integration/test_transaction_and_safety.py`'s
`TestReleaseCalendarStructuralIndependence` (an import-level guard, the
same style already used for the domain layer's architectural
independence).

## Flow 30 — Release Calendar UI (`/releases`, Increment #17B)

Presentation only, on top of Flow 28 — the browser never reaches Flow
29 (the sync write path) at all.

```mermaid
sequenceDiagram
    participant B as Browser (ReleasesPage)
    participant H1 as useApiResource(fetchUpcomingReleases)
    participant H2 as useApiResource(fetchRecentReleases)
    participant API as FastAPI (via Flow 26's proxy in dev)

    par independent requests
        B->>H1: mount
        H1->>H1: upcomingWindow() -- today through +45 days
        H1->>API: GET /api/v1/releases?start_date&end_date&order=asc
    and
        B->>H2: mount
        H2->>H2: recentWindow() -- -30 days through today
        H2->>API: GET /api/v1/releases?start_date&end_date&order=desc
    end
    API-->>H1: 200 ReleaseListResponse (or a network/HTTP failure)
    API-->>H2: 200 ReleaseListResponse (or a network/HTTP failure)
    H1-->>B: {status: "success", data} | {status: "error", error} | {status: "loading"}
    H2-->>B: {status: "success", data} | {status: "error", error} | {status: "loading"}
    Note over B: groupReleasesByDate() groups same-date items for<br/>display only -- schedule_status is rendered exactly<br/>as returned, never reclassified client-side.
```

Rendering per combination, identical shape to Flow 27's table:

| Upcoming state | Recent state | Rendered result |
|---|---|---|
| loading | loading | `LoadingSkeleton` (role="status") in both slots; no release data rendered anywhere |
| success | success | Both `ReleaseCalendarSection`s render, grouped by date, backend order and `schedule_status` preserved exactly |
| error | success | `ErrorMessage` ("Upcoming releases could not be loaded.", with Retry) in place of Upcoming; Recent still renders normally |
| success | error | Upcoming renders normally; `ErrorMessage` ("Recent releases could not be loaded.", with Retry) in place of Recent |
| error | error | Both `ErrorMessage`s render; nothing on the page claims to be release data |

A successful response with zero occurrences in the requested window
(`releases: []`) is not an error — it renders "No scheduled releases in
this window."/"No recently scheduled releases in this window." as plain
text, the same infrastructure-failure-vs-canonical-empty-result
distinction Flow 27 already draws for Inflation.

The page never constructs a request to `POST /api/v1/releases/sync`
(Flow 29) — there is no code path from `ReleasesPage` or anything it
imports that could reach it; `frontend/src/test/no-release-sync-or-coupling.test.ts`
checks this statically across every release-related file, and the
literal path does not appear anywhere in the built frontend source.

## Flow 31 — Explanation Trigger Open (Increment #17C)

Unlike every other flow in this document, opening an explanation issues
**no request at all** — no new network call, no re-fetch, no change to
any canonical value already on the page. `ExplanationTrigger` and
`WhyThisState` (`frontend/src/components/explanations/`,
`frontend/src/components/inflation/WhyThisState.tsx`) are pure,
client-side lookups against the static, curated content already bundled
in `frontend/src/content/explanations/`. This flow exists to make that
"no request" property explicit and diagrammable, not because it's
network-interesting.

```mermaid
sequenceDiagram
    participant U as User
    participant T as <details>/<summary> (ExplanationTrigger or WhyThisState)
    participant C as content/explanations/{inflation,releases}.ts

    Note over T: The canonical value (state, schedule_status,<br/>3M/6M/12M, evidence) is already on the page --<br/>fetched once, by Flow 27 or Flow 30, before this<br/>flow ever begins.
    U->>T: click summary, or focus + Enter/Space (native <summary> semantics)
    T->>T: toggle open (browser-native <details> behavior --<br/>no React state, no event handler here)
    alt concept explanation (ExplanationTrigger)
        T->>C: look up by stable id (e.g. CORE_PCE, FED_OBJECTIVE)
    else result explanation (WhyThisState)
        T->>C: inflationStateExplanation(momentum.state) --<br/>state is the backend's own already-classified value
    end
    C-->>T: Explanation { title, definition, whyItMatters?, sourceNote? }
    T-->>U: title/definition/whyItMatters/sourceNote render in the<br/>opened panel; WhyThisState also renders momentum's<br/>own r_3m/r_6m/r_12m/neutral-band fields, unchanged<br/>from what Flow 27 already fetched
```

No branch of this flow can reach a failure state the way Flows 27/30
can — there is no request to fail, time out, or retry. The only two
observable outcomes are "closed" and "open"; whichever `state`/
`schedule_status` value the backend returned is exactly what selects
the curated explanation shown, so the same contradictory-evidence
proof Flow 27's table implies (an `INSUFFICIENT_DATA`/`UNAVAILABLE`
result rendering in its own muted tone, never reinterpreted) applies
here too: opening `WhyThisState` on a `MIXED` result cannot render a
COOLING/HEATING/STABLE explanation, because the lookup key is the
backend's own `state` field, not a client-side re-evaluation of
`r_3m_annualized`/`r_6m_annualized`/`r_12m` (see
`frontend/src/components/inflation/WhyThisState.test.tsx`'s
contradictory-evidence tests, and
`frontend/src/test/no-explanation-classification-logic.test.ts` for the
static guard backing this).

## Flow 32 — Release-Driven Update Pipeline (`app.operations.process_release`, Increment #18)

Not an HTTP flow -- there is no route (see
`docs/architecture/release-processing-v1.md` §18). Triggered only by
the operational CLI, one release occurrence at a time, inside one real
database transaction.

```mermaid
sequenceDiagram
    participant Op as Operator (CLI)
    participant CLI as app.operations.process_release
    participant Svc as ReleaseProcessingService
    participant RRepo as ReleaseRepository (read-only)
    participant PRepo as ReleaseProcessingRepository
    participant FRED as FREDClient
    participant Dom as app.domain.inflation /<br/>inflation_what_changed (unmodified)

    Op->>CLI: python -m app.operations.process_release --occurrence-id N [--as-of-date D]
    CLI->>Svc: process_occurrence(N, session, as_of_date)
    Svc->>RRepo: get_occurrence_by_id(N)
    alt occurrence not found
        Svc-->>CLI: OccurrenceNotFoundError
        CLI-->>Op: exit 1, safe message
    else scheduled_date > as_of_date
        Svc-->>CLI: OccurrenceNotEligibleError
        CLI-->>Op: exit 1, safe message
    else eligible
        Svc->>PRepo: get_active_mappings(release_id)
        loop each mapped series
            Svc->>FRED: get_observations(series_id, observation_start=as_of_date-5y, sort_order=asc)
            alt provider failure (this series only)
                FRED-->>Svc: FREDError
                Note over Svc: recorded as this series' own failure;<br/>other mapped series are unaffected
            else success
                FRED-->>Svc: raw observations
                Svc->>PRepo: get_observations_by_date(series) (baseline)
                Svc->>Svc: classify_observation_change() per date<br/>(NEW / REVISED / UNCHANGED)
            end
        end
        Note over Svc: affected_evaluation_periods() across every<br/>changed series -- computed ONCE for the whole batch
        Svc->>PRepo: read current persisted data (BEFORE snapshot)
        Svc->>Dom: compute_series_momentum_at / compute_target_at /<br/>compute_confirmation_at (per affected period)
        Svc->>PRepo: write_observation() for every NEW/REVISED row
        Svc->>PRepo: read current persisted data (AFTER snapshot)
        Svc->>Dom: same exact-period primitives, again
        Svc->>Dom: compare_series_momentum_section / compare_target_section /<br/>compare_confirmation_section (before vs after, once per affected pair)
        Svc->>PRepo: add_check_run() + add_observation_update()* + add_analysis_update()*
        PRepo-->>Svc: ReleaseCheckRunResult
        Svc-->>CLI: ReleaseCheckRunResult
        CLI-->>Op: safe summary to stdout, exit 0 (NO_CHANGE/CHANGED)<br/>or exit 1 (PARTIAL_FAILURE/FAILED_PROVIDER)
    end
```

The whole `eligible` branch is one `session_scope()` transaction. A
genuine database-layer failure at any point inside it propagates
uncaught and rolls back everything written in this attempt, including
any already-classified NEW/REVISED writes for series that succeeded at
the provider boundary -- there is no partial commit, and (per
`docs/architecture/release-processing-v1.md` §5) the `ReleaseCheckRun`
row for a failed attempt like this may never durably exist at all,
which is accepted, not a gap.

**What this flow explicitly does NOT do**: it never calls
`GET /api/v1/monitors/inflation/changes` (that endpoint answers a
different question -- "what changed between the two most recent
calendar months" -- and cannot see a revision to an older period; see
`docs/architecture/release-processing-v1.md` §8.2 for why this flow
instead calls the same underlying comparator functions directly, at a
release-scoped before/after pair rather than a month-over-month pair).
It never persists a full `InflationMonitorResult`. It never writes to
`ReleaseOccurrence.schedule_status` or infers publication from the
occurrence's scheduled date. Nothing in this flow's call graph imports
AI or news.

### Flow 32B — the same pipeline, for Employment Situation / Labor (Increment #20D.2)

Employment Situation (FRED 50, mapped to PAYEMS/UNRATE by migration
`09f4c0959e9f`) is processed through the EXACT SAME `process_occurrence`
call as Flow 32 above -- same CLI, same eligibility checks, same
per-series fetch/classify loop, same transaction boundary. The only
difference is inside `_apply_changes_and_compute_analysis`, which now
runs a second, independent branch alongside the Inflation one shown in
Flow 32's own sequence diagram:

```mermaid
sequenceDiagram
    participant Svc as ReleaseProcessingService
    participant PRepo as ReleaseProcessingRepository
    participant LDom as app.domain.labor_release_processing (pure)
    participant LEng as app.domain.labor (unmodified)
    participant LCmp as app.domain.labor_what_changed (unmodified)

    Note over Svc: PAYEMS/UNRATE changed observations,<br/>partitioned independently from the Inflation ones -- never `elif`
    Svc->>LDom: labor_affected_evaluation_periods(payems_changed, unrate_changed)
    LDom-->>Svc: frozenset[date] -- periods only, no component dimension
    Svc->>PRepo: read current persisted PAYEMS/UNRATE (BEFORE snapshot)
    Svc->>LEng: compute_labor_monitor_result_at(period) -- per affected period
    Svc->>PRepo: write_observation() for every NEW/REVISED PAYEMS/UNRATE row
    Svc->>PRepo: read current persisted PAYEMS/UNRATE (AFTER snapshot)
    Svc->>LEng: compute_labor_monitor_result_at(period), again
    Svc->>LCmp: compare_labor_state / compare_employment_section /<br/>compare_unemployment_section (previous_period == current_period == t)
    Note over Svc: analysis_changes = Inflation's own list + Labor's own list, concatenated
    Svc->>PRepo: add_analysis_update()* (Inflation rows and Labor rows, same call, same transaction)
```

Same explicit "no analysis without at least one comparator event" rule
(Flow 32's own §8.2 logic, unchanged); a PAYEMS revision landing in the
cancellation zone (offset 1 or 2 from the changed month) produces a
`ReleaseObservationUpdate` row but zero `ReleaseAnalysisUpdate` rows at
that period, for the identical reason `data changed != analysis
changed` already holds for Inflation. Never calls
`GET /api/v1/monitors/labor/changes` or
`month_over_month_labor_periods` -- same reasoning as Flow 32's own
"what this flow explicitly does NOT do" note, restated for Labor. See
[docs/architecture/labor-release-integration-v1.md](./labor-release-integration-v1.md)
for the full frozen contract.

## Flow 33 — `/` Economic Overview Page Load (Increment #19A, extended #19C, extended #20E.2, extended #22B)

`frontend/src/pages/Overview.tsx` calls `useApiResource(getInflationMonitor)`,
`useApiResource(getInflationWhatChanged)`, `useApiResource(getLaborMonitor)`,
`useApiResource(getLaborWhatChanged)`, `useApiResource(fetchReleaseProcessingStatus)`,
`useApiResource(fetchUpcomingReleases)`, and `useApiResource(fetchRecentReleases)`
in the same render — seven independent resources, each owning its own
`loading`/`success`/`error` state, extending exactly the pattern Flow 27
established for two and Flow 37 (below) establishes for Labor's own
page. There is no aggregate endpoint, no `Promise.all` across domains,
and no aggregate "Economy Score" anywhere in this flow.

```mermaid
sequenceDiagram
    participant B as Browser (OverviewPage)
    participant H1 as useApiResource(getInflationMonitor)
    participant H2 as useApiResource(getInflationWhatChanged)
    participant H6 as useApiResource(getLaborMonitor)
    participant H7 as useApiResource(getLaborWhatChanged)
    participant H5 as useApiResource(fetchReleaseProcessingStatus)
    participant H3 as useApiResource(fetchUpcomingReleases)
    participant H4 as useApiResource(fetchRecentReleases)
    participant API as FastAPI (via Flow 26's proxy in dev)

    par seven independent requests
        B->>H1: mount
        H1->>API: GET /api/v1/monitors/inflation
    and
        B->>H2: mount
        H2->>API: GET /api/v1/monitors/inflation/changes
    and
        B->>H6: mount
        H6->>API: GET /api/v1/monitors/labor
    and
        B->>H7: mount
        H7->>API: GET /api/v1/monitors/labor/changes
    and
        B->>H5: mount
        H5->>API: GET /api/v1/releases/processing-status
    and
        B->>H3: mount
        H3->>API: GET /api/v1/releases?start_date&end_date&order=asc
    and
        B->>H4: mount
        H4->>API: GET /api/v1/releases?start_date&end_date&order=desc
    end
    API-->>H1: 200 InflationMonitorResult (or a network/HTTP failure)
    API-->>H2: 200 InflationWhatChangedResult (or a network/HTTP failure)
    API-->>H6: 200 LaborMonitorResult (or a network/HTTP failure)
    API-->>H7: 200 LaborWhatChangedResult (or a network/HTTP failure)
    API-->>H5: 200 ReleaseProcessingStatusResponse (or a network/HTTP failure)
    API-->>H3: 200 ReleaseListResponse (or a network/HTTP failure)
    API-->>H4: 200 ReleaseListResponse (or a network/HTTP failure)
    Note over B: Each of the seven renders independently --<br/>CurrentStateSection (a peer wrapper over<br/>InflationCurrentStateCard/LaborCurrentStateCard),<br/>WhatChangedPreview/LaborWhatChangedPreview (#22B:<br/>4-tier PRESENTATION salience, never a score),<br/>RecentDataUpdates (#22B: two canonical-monitor-<br/>domain slots), UpcomingReleasesPreview,<br/>RecentReleasePreview format/classify-into-fixed-<br/>tiers only, never reclassify a canonical value or<br/>rank by magnitude.
```

Rendering is per-resource, identical in shape to Flow 27/30/37's own
tables — any one of the seven in `loading`/`success`/`error` renders
independently of the other six; there is no combination in which one
resource's failure prevents another's success from rendering (proven
directly: dedicated single-resource-failure tests for each of the
seven, dedicated cross-domain tests added in #20E.2 — e.g. Labor
failing renders `InflationCurrentStateCard` normally and vice versa —
plus one all-fail test, the latter still rendering one intact page
title and seven independently truthful error messages, never a
blanked page).

`CurrentStateSection` (restructured in #20E.2) is now a thin peer
wrapper: one shared `<h2>Current State</h2>` over two independently-
gated cards. `InflationCurrentStateCard` renders `underlying_momentum.state`
exactly as returned (via the same `Badge`/`WhyThisState` Flow 27
already uses), labeled explicitly as "Inflation"; `LaborCurrentStateCard`
renders `LaborMonitorResult.state` exactly as returned (via `Badge`/
`WhyLaborState`, Flow 37's own components), labeled explicitly as
"Labor" — neither is a page-wide "economy" conclusion, and there is no
combined score anywhere. `WhatChangedPreview`/`LaborWhatChangedPreview`
(Increment #22B, replacing the old `.slice(0, 3)` truncation) classify
each family's own flat, already deterministically-ordered event list
(`inflation_what_changed_v1.0`/`labor_what_changed_v1.0`) into 4 fixed
presentation tiers by `component`/`field` membership only
(`lib/inflationSalience.ts`/`lib/laborSalience.ts` — Labor's a straight
extraction of `/labor`'s own already-shipped four-filter hierarchy) —
Tier 1 (primary domain state) → Tier 2 (structural change) → Tier 3
(secondary/corroborating signal) → Tier 4 (routine metric, collapsed
behind a count-labeled disclosure) — under one shared `<h2>What
Changed</h2>`. Tiers 1–3 render uncapped (the old fixed-3 truncation is
retired for structural events, precisely because it could let routine
Tier-4 noise from an earlier component crowd out a real state change
from a later one — the defect #21's audit found and this flow now
closes); Tier 4 stays collapsed but never capped or hidden from
inspection. Never a score, never a magnitude-based sort, never a
market-impact/severity concept — a dedicated architecture guard scans
for exactly those smuggled-in shapes. Still never synthesizes a
narrative from an event's *absence* the way `/inflation`'s or `/labor`'s
own `WhatChangedSection` does for its own per-section summaries; a
domain whose Tiers 1–3 are all empty but Tier 4 is not instead renders
the exact copy "No structural change." `RecentDataUpdates` (Increment
#19C as "Latest Data Detected", renamed/restructured #22B) now owns one
shared `<h2>Recent Data Updates</h2>` over two independently-gated
domain slots, each pre-filtering `processingStatus.data.occurrences` by
`lib/releaseMonitorRelation.ts`'s migration-verified
`CANONICAL_MONITOR_RELEASE_IDS` (`{"10","54"} → Inflation`, `{"50"} →
Labor` — deliberately NOT the broader `releaseCategory()` display tag,
which would incorrectly catch JOLTS) before calling the same,
unmodified per-domain-filtered `selectLatestDataDetectedItem`
(`lib/selectLatestDataDetected.ts` — see Flow 34's own entry and this
file's "Components" table for why it is not simply the backend's
first-returned item). Each selected occurrence renders its own
`latest_check.status`-driven message plus its sibling
`detected_observation_changes`/`detected_analysis_changes` lists,
truncated to 3 each in backend order, using `analysisComponentLabel`/
`analysisFieldLabel` (extended #20E.2 to humanize any family's values,
not just Inflation's) — `components/overview/LatestDataDetected.tsx`
itself is unchanged in substance, only stripped of its own former
`<section>`/heading, now called twice as a content-only slot renderer.
`UpcomingReleasesPreview`/`RecentReleasePreview` slice the
already-backend-ordered release arrays to 3 and 1 respectively, reusing
Flow 30's own `ReleaseDateBadge`/`ReleaseRow`/`ScheduleStatusBadge`
components, alongside the same mandatory schedule-vs-publication
disclosure sentence Flow 30 requires (centralized in
`components/releases/ReleaseScheduleDisclosure.tsx`, rendered on all
three of `/releases`, `/`, and `/labor`). As of #22B,
`UpcomingReleasesPreview` also enables `ReleaseRow`'s optional
`showMonitorCta` prop — each previewed row gets its own "View
Inflation →"/"View Labor →"/"View Releases →" next action, keyed by the
same `CANONICAL_MONITOR_RELEASE_IDS` constant, closing the release-row
dead end #21's audit found (`ReleaseCalendarSection` on Flow 30 and
`RelevantRelease` on Flow 37 deliberately leave the prop at its default
`false`, since the identical CTA would be circular in either context).

Nothing in this flow's call graph imports AI or news, and nothing
calls a sync/mutation endpoint of any kind — the Overview page is
exactly as read-only as `/inflation`, `/labor`, and `/releases` already
are.

## Flow 34 — Release Processing Status Read (`GET /api/v1/releases/processing-status`, Increment #19B)

Database-only, exactly like Flow 28 — never calls FRED, never calls AI.
Implements
[docs/architecture/release-processing-read-model-v1.md](./release-processing-read-model-v1.md).

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route (app/api/release_processing_read.py)
    participant S as ReleaseProcessingReadService
    participant SS as session_scope()
    participant Repo as ReleaseProcessingReadRepository
    participant DB as PostgreSQL

    C->>R: GET /api/v1/releases/processing-status?occurrence_id&release_id&status&start_date&end_date&limit&offset
    R->>R: database_url present?
    R->>SS: enter session_scope()
    R->>S: get_processing_status(session, filters...)
    S->>S: start_date > end_date? raise InvalidDateRangeError
    S->>Repo: list_mapped_occurrences(occurrence_id, release_id, start_date, end_date)
    Repo->>DB: SELECT release_occurrences JOIN economic_releases<br/>WHERE economic_release_id IN (SELECT ... FROM release_series_mappings WHERE active)
    DB-->>Repo: every mapped occurrence matching the filters (unpaginated)
    Repo-->>S: [(ReleaseOccurrence, EconomicRelease), ...]
    S->>Repo: list_check_runs_for_occurrences(occurrence_ids)
    Repo->>DB: SELECT release_check_runs WHERE release_occurrence_id IN (...) ORDER BY completed_at DESC, id DESC
    DB-->>Repo: every run ever recorded, for all candidates
    Repo-->>S: [ReleaseCheckRun, ...]
    Note over S: group by occurrence; first row per<br/>occurrence = its latest run (or None = NOT_CHECKED).<br/>Map internal status -> public 5-value ProcessingStatus.
    S->>S: filter by status (if given); total = len(filtered); slice [offset : offset+limit]
    S->>Repo: list_observation_updates_for_runs(run_ids for this page's occurrences, ALL runs not just latest)
    Repo->>DB: SELECT release_observation_updates WHERE release_check_run_id IN (...) ORDER BY detected_at DESC, id DESC
    DB-->>Repo: rows
    S->>Repo: list_analysis_updates_for_runs(same run_ids)
    Repo->>DB: SELECT release_analysis_updates WHERE release_check_run_id IN (...) ORDER BY created_at DESC, id DESC
    DB-->>Repo: rows
    S->>Repo: list_series_metadata(distinct series_ids from the observation rows)
    Repo->>DB: SELECT economic_series WHERE series_id IN (...)
    DB-->>Repo: {series_id: EconomicSeries}
    Note over S: assemble ReleaseProcessingStatusItem per occurrence:<br/>latest_check + detected_observation_changes[] + detected_analysis_changes[]<br/>as SIBLING arrays (ADR-023) -- never one nested inside the other.
    S-->>R: ReleaseProcessingStatusResponse (occurrences, pagination)
    R->>SS: exit session_scope() normally
    R-->>C: 200 JSON
```

A persisted `CHECK_FAILED`/`PARTIAL_CHECK` result is itself
successfully-read product data — it returns `200`, the same as any
other status; only a request-shape problem or a genuine database
failure is an HTTP error:

| Scenario | Where it's caught | HTTP status |
|---|---|---|
| `DATABASE_URL` not configured | Checked in the route before a session is opened | `503` |
| `start_date > end_date` | `InvalidDateRangeError` | `400` |
| Malformed query param (bad type, `limit`/`offset` out of bounds, invalid `status`) | FastAPI/Pydantic query validation, before the route body runs | `422` |
| Database unreachable | `OperationalError` | `503` |
| Any other database-layer failure | `SQLAlchemyError` | `500` |
| Occurrence never checked | *(no exception)* | `200`, `latest_check.status == "NOT_CHECKED"`, `checked_at: null` |
| Occurrence's release has zero active mappings | *(excluded at the repository layer)* | `200`, occurrence simply absent from the response |

`ReleaseProcessingReadService` has no method that accepts or
constructs a `FREDClient`, and never imports
`app.services.release_processing`/`app.repositories.release_processing_repository`
(#18's write path) — checked structurally, not just by convention (see
`tests/test_release_processing_read_architecture.py`).

## Flow 35 — Labor Monitor (`labor_v1.0`, Increment #20B)

`GET /api/v1/monitors/labor` reads only from PostgreSQL, for exactly
the two canonical series named in
[research/labor_momentum/LABOR_V1_FROZEN_METHODOLOGY.md](../../research/labor_momentum/LABOR_V1_FROZEN_METHODOLOGY.md).
`FREDClient` never appears anywhere in this flow, and no AI service is
imported or called. Both series are fetched independently; a series
that isn't persisted at all yields an empty observation list rather
than an error — identical precedent to Flow 22's own Inflation Monitor
flow.

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route (app/api/labor.py)
    participant S as LaborMonitorService
    participant SS as session_scope()
    participant Repo as SeriesRepository
    participant DB as PostgreSQL
    participant D as app.domain.labor (pure)

    C->>R: GET /api/v1/monitors/labor
    R->>R: database_url present?
    R->>SS: enter session_scope()
    R->>S: get_result(session)
    loop for each of PAYEMS, UNRATE
        S->>Repo: get_series_by_series_id(series_id)
        Repo->>DB: SELECT economic_series WHERE series_id = ?
        DB-->>Repo: row or None
        alt series persisted
            Repo-->>S: EconomicSeries
            S->>Repo: get_observations_in_range(economic_series_id, None, None)
            Repo->>DB: SELECT * FROM economic_observations WHERE economic_series_id = ? ORDER BY observation_date
            DB-->>Repo: all rows
            Repo-->>S: list[Observation]
        else series not persisted
            S->>S: observations = [] (never SeriesNotFoundError)
        end
    end
    S->>D: compute_labor_monitor_result(payems_observations, unrate_observations, deadbands...)
    Note over D: pure -- no session, no HTTP, no FRED, no OpenAI.<br/>determine_evaluation_period(): min(latest PAYEMS date, latest UNRATE date),<br/>never a backward search. PAYEMS converted thousands->jobs<br/>exactly once (build_jobs_index). Exact-calendar-month<br/>endpoint resolution throughout (never row-position).
    D-->>S: LaborMonitorResult
    S-->>R: LaborMonitorResult
    R->>SS: exit session_scope() normally
    R-->>C: 200 JSON (methodology_id, data_basis, state,<br/>evaluation_period, employment, unemployment)
```

Missing or insufficient labor data is **not** an error:
`compute_labor_monitor_result` always returns a complete, typed
result — `employment`/`unemployment` each report their own
`INSUFFICIENT_DATA` state when their required exact calendar months
aren't all present, and the whole result is `INSUFFICIENT_DATA` with
`evaluation_period: null` only when neither series has any persisted
observation at all (no candidate period could even be chosen). Only a
genuine database/infrastructure failure produces a non-`200` response.

| Scenario | Where it's caught | HTTP status |
|---|---|---|
| `DATABASE_URL` not configured | Checked in the route before a session is opened | `503` |
| Database unreachable | `OperationalError` | `503` |
| Any other database-layer failure | `SQLAlchemyError` | `500` |
| Neither PAYEMS nor UNRATE persisted at all | *(no exception)* | `200`, `state: "INSUFFICIENT_DATA"`, `evaluation_period: null` |
| One series newer than the other (e.g. PAYEMS synced, UNRATE lagging) | *(no exception — `evaluation_period` bounded by the earlier series)* | `200` |
| A required exact calendar month missing for PAYEMS's 7-month window | *(no exception — `employment.state: "INSUFFICIENT_DATA"`; `employment.condition` may still be a real value if only a momentum-only month is missing, per the frozen spec's §3-vs-§4 distinction)* | `200` |
| A required exact calendar month missing for UNRATE's 6-month window (e.g. the real 2025-10 gap, when it falls inside the required set) | *(no exception — `unemployment.state: "INSUFFICIENT_DATA"`)* | `200` |

`LaborMonitorService` has no method that accepts or constructs a
`FREDClient`, and imports no AI module anywhere in its call graph —
checked structurally, not just by convention (see
`tests/test_labor_architecture.py`).

## Flow 36 — Labor What Changed (`labor_what_changed_v1.0`, Increment #20C.2)

`GET /api/v1/monitors/labor/changes` reads only from PostgreSQL, for
the exact same two canonical series as Flow 35. It computes a single
**month-over-month** comparison against
[research/labor_momentum/LABOR_WHAT_CHANGED_V1_FROZEN_METHODOLOGY.md](../../research/labor_momentum/LABOR_WHAT_CHANGED_V1_FROZEN_METHODOLOGY.md):
unlike Inflation's own What Changed flow (Flow 24), Labor has exactly
ONE shared `evaluation_period` for both owners, so there is no
per-section period selection — `month_over_month_labor_periods`
computes the one `(previous_period, current_period)` pair, reused by
every section.

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route (app/api/labor.py)
    participant S as LaborMonitorService
    participant SS as session_scope()
    participant Repo as SeriesRepository
    participant DB as PostgreSQL
    participant D as app.domain.labor (pure)
    participant W as app.domain.labor_what_changed (pure)

    C->>R: GET /api/v1/monitors/labor/changes
    R->>R: database_url present?
    R->>SS: enter session_scope()
    R->>S: get_what_changed_result(session)
    loop for each of PAYEMS, UNRATE
        S->>Repo: get_series_by_series_id / get_observations_in_range
        Repo->>DB: SELECT ...
        DB-->>Repo: rows (or none -- observations = [], never an error)
        Repo-->>S: list[Observation]
    end
    S->>D: month_over_month_labor_periods(payems_obs, unrate_obs)
    Note over D: current_period = determine_evaluation_period(...) (unmodified,<br/>Flow 35's own rule); previous_period = month_before(current_period, 1) --<br/>exact calendar month, never searched backward
    D-->>S: (previous_period, current_period)
    alt current_period is None
        S->>D: compute_labor_monitor_result(payems_obs, unrate_obs, deadbands...)
        Note over D: the ONE degenerate/INSUFFICIENT_DATA result,<br/>reused for BOTH sides -- no second period to compute a distinct "previous" from
        D-->>S: LaborMonitorResult (INSUFFICIENT_DATA)
    else current_period is not None
        S->>D: compute_labor_monitor_result_at(payems_obs, unrate_obs, previous_period, ...)
        D-->>S: LaborMonitorResult (previous)
        S->>D: compute_labor_monitor_result_at(payems_obs, unrate_obs, current_period, ...)
        D-->>S: LaborMonitorResult (current)
    end
    Note over S,W: comparison -- the ONLY step touching app.domain.labor_what_changed
    S->>W: compare_employment_section(previous_period, current_period, prev.employment, curr.employment)
    W-->>S: EmploymentSectionChanges
    S->>W: compare_unemployment_section(previous_period, current_period, prev.unemployment, curr.unemployment)
    W-->>S: UnemploymentSectionChanges
    S->>W: compare_labor_state(previous_period, current_period, prev.state, curr.state)
    W-->>S: list[LaborChangeEvent]
    Note over W: pure diffing only -- W never imports app.domain.labor<br/>(enforced by both an import guard and an AST-level<br/>no-hardcoded-deadband-literal guard)
    S->>W: assemble_labor_what_changed_result(...)
    W-->>S: LaborWhatChangedResult
    S-->>R: LaborWhatChangedResult
    R->>SS: exit session_scope() normally
    R-->>C: 200 JSON (employment_changes, unemployment_changes,<br/>flattened ordered `changes`, summary flags)
```

Missing or insufficient labor data is **not** an error: when neither
series has any persisted observation at all,
`comparison_available: false` with `previous_period`/`current_period:
null` and `previous_labor_state`/`current_labor_state:
"INSUFFICIENT_DATA"` (the real enum member, never a bare `null`) is
returned inside a normal `200` response — the identical
infrastructure-vs-economic-data distinction Flow 24/35 already
establish. Only a genuine database/infrastructure failure produces a
non-`200` response.

| Scenario | Where it's caught | HTTP status |
|---|---|---|
| `DATABASE_URL` not configured | Checked in the route before a session is opened | `503` |
| Database unreachable | `OperationalError` | `503` |
| Any other database-layer failure | `SQLAlchemyError` | `500` |
| Neither PAYEMS nor UNRATE persisted at all | *(no exception)* | `200`, `comparison_available: false` |
| The current period's PAYEMS window loses a required month (e.g. the anchor's own value goes null) | *(no exception — `employment_changes.availability_lost: true`; `LABOR.state` co-occurring loss from the same root cause, reported independently)* | `200` |
| `EMPLOYMENT.condition`/`momentum` change without `EMPLOYMENT.state` changing (or vice versa) | *(no exception — each reported as its own `STATE_CHANGED` event, discriminated by `field`; never suppressed)* | `200` |
| The real UNRATE 2025-10 gap falls inside the current OR previous period's required prior-year window | *(no exception — `unemployment_changes.availability_lost`/`restored` fires exactly when the gap enters/exits the window, never one month early or late)* | `200` |

No scenario in this table ever searches backward past the exact
previous calendar month, substitutes a different series, fetches from
FRED, triggers ingestion, or calls AI to resolve a gap.
`LaborMonitorService.get_what_changed_result` has no method that
accepts or constructs a `FREDClient`, and imports no AI module
anywhere in its call graph — checked structurally (see
`tests/test_labor_architecture.py`).

## Flow 37 — `/labor` Page Load (Increment #20E.2)

`frontend/src/pages/Labor.tsx` calls `useApiResource(getLaborMonitor)`,
`useApiResource(getLaborWhatChanged)`, `useApiResource(getEmploymentSituationProcessingStatus)`,
`useApiResource(fetchUpcomingReleases)`, and `useApiResource(fetchRecentReleases)`
in the same render — five independent resources, each owning its own
`loading`/`success`/`error` state, extending exactly the pattern Flow 27
established for Inflation. `getEmploymentSituationProcessingStatus`
(`frontend/src/api/labor.ts`) is itself a composed async function, not
a single HTTP call: it resolves Employment Situation's internal
`release_id` via `Promise.all([fetchUpcomingReleases(), fetchRecentReleases()])`,
matching on `provider_release_id === "50"`, then calls
`fetchReleaseProcessingStatus(release_id)` using the backend's existing
(previously-unused) `?release_id=` query filter — this internal
`Promise.all` resolves two calls this same page also fires
independently for its own Upcoming/Recent resources; the composed
resource never blocks on, or is blocked by, those separate renders.

```mermaid
sequenceDiagram
    participant B as Browser (LaborPage)
    participant H1 as useApiResource(getLaborMonitor)
    participant H2 as useApiResource(getLaborWhatChanged)
    participant H3 as useApiResource(getEmploymentSituationProcessingStatus)
    participant H4 as useApiResource(fetchUpcomingReleases)
    participant H5 as useApiResource(fetchRecentReleases)
    participant API as FastAPI (via Flow 26's proxy in dev)

    par five independent requests
        B->>H1: mount
        H1->>API: GET /api/v1/monitors/labor
    and
        B->>H2: mount
        H2->>API: GET /api/v1/monitors/labor/changes
    and
        B->>H3: mount
        par resolve release_id
            H3->>API: GET /api/v1/releases?start_date&end_date&order=asc
        and
            H3->>API: GET /api/v1/releases?start_date&end_date&order=desc
        end
        API-->>H3: two ReleaseListResponse pages
        Note over H3: match provider_release_id == "50"<br/>(Employment Situation) to find release_id
        H3->>API: GET /api/v1/releases/processing-status?release_id=<id>
    and
        B->>H4: mount
        H4->>API: GET /api/v1/releases?start_date&end_date&order=asc
    and
        B->>H5: mount
        H5->>API: GET /api/v1/releases?start_date&end_date&order=desc
    end
    API-->>H1: 200 LaborMonitorResult (or a network/HTTP failure)
    API-->>H2: 200 LaborWhatChangedResult (or a network/HTTP failure)
    API-->>H3: 200 ReleaseProcessingStatusResponse, one occurrence<br/>(or a network/HTTP failure at any step)
    API-->>H4: 200 ReleaseListResponse (or a network/HTTP failure)
    API-->>H5: 200 ReleaseListResponse (or a network/HTTP failure)
    Note over B: Each of the five renders independently --<br/>LaborHero/WhyLaborState/EmploymentSection/<br/>UnemploymentSection/WhatChangedSection/<br/>LatestDataDetected/RelevantRelease format<br/>and filter only, never reclassify.
```

Rendering is per-resource, identical in shape to Flow 27/33's own
tables — any one of the five in `loading`/`success`/`error` renders
independently of the other four; a failure resolving Employment
Situation's `release_id` (either release-list call failing, or no
`provider_release_id === "50"` match found) surfaces as `H3`'s own
error state, never as a blank Latest Data Detected section silently
merged into the page's other content.

Page hierarchy (frozen by `docs/architecture/labor-ui-v1.md`, 7
sections, never reordered): `LaborHero` (primary `LaborState`, no
directional color — every real state shares one neutral tone; only
`MIXED` gets a distinct "caution" tone) → `WhyLaborState` (mirroring
`WhyThisState`'s own contradictory-evidence guarantee) →
`EmploymentSection` (`EmploymentCondition`/`EmploymentMomentum` as two
independently-reported lines; `formatJobs` for the already-converted
`current_3m_avg_jobs`/`prior_3m_avg_jobs`/`momentum_delta_jobs`,
`formatRawObservationValue` for the still-FRED-native
`observations[].value` — the two formatters are never interchanged) →
`UnemploymentSection` (`UnemploymentTrendState`) → `WhatChangedSection`
(filters — never reorders — the backend's already-ordered `changes[]`
into 4 presentation tiers: `LABOR`-component events, then
`EMPLOYMENT`/`UNEMPLOYMENT` `state` events, then `condition`/`momentum`
events, then `METRIC_CHANGED` numeric events behind a secondary
"Metric updates" disclosure) → `LatestDataDetected` (this page's own
component, scoped to Employment Situation's single occurrence via
`H3` above — architecturally distinct from `components/overview/LatestDataDetected.tsx`'s
unfiltered, cross-release version used by Flow 33) → an
"Evidence & methodology" disclosure (`MethodologyDisclosure` plus
per-metric `EvidenceDisclosure`, plus `RelevantRelease` reusing Flow
30's own `ReleaseRow`/`ReleaseDateBadge` unmodified).

Every economic value, state, condition, momentum, and period shown is
exactly what `GET /api/v1/monitors/labor`/`.../labor/changes`/
`.../releases/processing-status` returned; `lib/laborLabels.ts` and
`lib/laborFormat.ts` only format/label already-canonical values (see
`docs/architecture/current-architecture.md`'s "The Labor page" for the
full section-by-section breakdown, and
`frontend/src/test/no-economic-logic.test.ts`'s frozen-deadband guards
for the check preventing any of this from silently becoming a second
implementation of `labor_v1.0`).
