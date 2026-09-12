# Current Architecture

This document describes the system **as it exists right now**, after
Increment 005. It is not a history — see [`../ENGINEERING_JOURNAL.md`](../ENGINEERING_JOURNAL.md)
for how it got here, and [`../adr/`](../adr/) for why specific choices were
made.

## Components

| Component | Location | Responsibility |
|---|---|---|
| ASGI server | Uvicorn (process) | Runs the FastAPI app, handles HTTP connections |
| Application | `app/main.py` | Creates the `FastAPI` app, mounts routers, defines `/health` |
| Series route | `app/api/series.py` | HTTP layer for `/api/v1/series/{series_id}`, `.../sync`, `.../observations`, and `.../transform`: request/query-parameter handling, exception → status code translation |
| Economic data service | `app/services/economic_data.py` (`EconomicDataService`) | Use-case logic: fetch + normalize a series from FRED; orchestrate fetch-then-persist for sync; validate and coordinate a persisted-observations query; validate and orchestrate a transformation (including boundary-context retrieval) |
| FRED client | `app/clients/fred.py` (`FREDClient`) | All FRED-specific HTTP: request construction, timeout, FRED error → typed exception translation |
| Series repository | `app/repositories/series_repository.py` (`SeriesRepository`) | All SQL for series/observations: upserts series metadata and observations within a caller-owned transaction; series lookup; filtered/ordered/paginated observation queries; unpaginated range queries and preceding-context queries for transformations |
| Transformation engine | `app/domain/transformations.py` (`absolute_change`, `percent_change`, `moving_average`) | Pure, deterministic math over observation lists — no FastAPI, SQLAlchemy, FRED, environment, or I/O of any kind |
| Response models | `app/models/series.py` (`Observation`, `SeriesResponse`, `PaginationMeta`, `SeriesObservationsResponse`, `TransformedObservation`, `TransformationMeta`, `SeriesTransformResponse`) | The application's own, provider-independent API response contract |
| ORM models | `app/db/models.py` (`EconomicSeries`, `EconomicObservation`) | The relational shape of persisted data |
| DB engine/session | `app/db/session.py` | Lazily-created SQLAlchemy engine (connection pool) and `session_scope()` transaction boundary |
| Configuration | `app/core/config.py` (`Settings`) | Reads `FRED_API_KEY`, `DATABASE_URL`, and the FRED request timeout from the environment |
| Schema migrations | `alembic/` | Version-controlled schema history, applied explicitly via `alembic upgrade head` |

## Architecture diagram

```mermaid
graph TD
    Consumer["API Consumer"] --> Uvicorn["Uvicorn (ASGI server)"]
    Uvicorn --> App["FastAPI app<br/>app/main.py"]

    App --> Health["GET /health<br/>app/main.py"]
    App --> GetRoute["GET /api/v1/series/{series_id}<br/>app/api/series.py"]
    App --> SyncRoute["POST /api/v1/series/{series_id}/sync<br/>app/api/series.py"]
    App --> ObsRoute["GET /api/v1/series/{series_id}/observations<br/>app/api/series.py"]
    App --> TransformRoute["GET /api/v1/series/{series_id}/transform<br/>app/api/series.py"]

    GetRoute --> Service["EconomicDataService<br/>app/services/economic_data.py"]
    SyncRoute --> Service
    ObsRoute --> Service
    TransformRoute --> Service

    Service --> Client["FREDClient<br/>app/clients/fred.py"]
    Service --> Repo["SeriesRepository<br/>app/repositories/series_repository.py"]
    Service --> Engine["Transformation engine<br/>app/domain/transformations.py<br/>(pure functions)"]

    Client -->|"httpx, timeout=10s"| FRED[("FRED REST API<br/>api.stlouisfed.org")]
    Repo -->|"session_scope():<br/>BEGIN ... COMMIT/ROLLBACK"| Orm["SQLAlchemy Engine<br/>app/db/session.py"]
    Orm --> PG[("PostgreSQL<br/>economic_intelligence")]

    Config["Settings<br/>app/core/config.py<br/>(FRED_API_KEY, DATABASE_URL, timeout)"] -.-> GetRoute
    Config -.-> SyncRoute
    Config -.-> ObsRoute
    Config -.-> TransformRoute
    Models["Observation / SeriesResponse /<br/>SeriesObservationsResponse /<br/>SeriesTransformResponse<br/>app/models/series.py"] -.-> Service
    OrmModels["EconomicSeries / EconomicObservation<br/>app/db/models.py"] -.-> Repo
    Alembic["alembic/ migrations"] -.->|"defines schema for"| PG
```

`GetRoute` and `SyncRoute` reach `FREDClient`; `ObsRoute` and
`TransformRoute` never do — both are wired only through `Service` to
`Repo` to PostgreSQL. This is a real structural fact, not just a diagram
simplification: `FREDClient` is never imported or constructed anywhere in
`get_series_observations`'s or `get_series_transform`'s call path.
`Engine` (the transformation module) has no edge to `Repo`, `Orm`, `PG`,
or `Client` at all — it only ever receives plain observation data already
fetched by the service; it cannot reach PostgreSQL or FRED even
indirectly.

## Three paths over the same persisted data

```
WRITE/SYNC PATH:
  Client -> POST /api/v1/series/{id}/sync -> Route -> EconomicDataService
    -> FREDClient -> FRED API
    -> SeriesRepository -> PostgreSQL   (INSERT/UPDATE, one transaction)

READ PATH (raw historical observations):
  Client -> GET /api/v1/series/{id}/observations -> Route -> EconomicDataService
    -> SeriesRepository -> PostgreSQL   (SELECT only)

DERIVED-DATA PATH (transformations):
  Client -> GET /api/v1/series/{id}/transform -> Route -> EconomicDataService
    -> SeriesRepository -> PostgreSQL   (SELECT only: requested range + preceding context)
    -> Transformation engine (pure, in-process; no I/O)
```

`POST .../sync` is the only way data enters PostgreSQL.
`GET .../observations` and `GET .../transform` are the only ways to read
it back through this API — the former returns raw persisted values, the
latter returns values computed from them on the fly. No path touches the
other paths' external dependency: sync never reads more than it needs to
upsert, `.../observations` and `.../transform` never call FRED, and
`.../transform` never writes anything back to PostgreSQL — the derived
values it computes are not stored anywhere (see Data model below).

`GET /api/v1/series/{series_id}` (no suffix) is a fourth, separate path,
unchanged since Increment 002 — it still reads live from FRED and never
touches PostgreSQL at all. See Response contract below for how its
contract relates to `.../observations` and `.../transform`.

## Configuration boundary

`app/core/config.py` is the single place that reads from the process
environment. It exposes a module-level `settings` object with:

- `fred_api_key: str | None` — read from `FRED_API_KEY`; `None` if unset.
- `fred_timeout_seconds: float` — currently a fixed constant (`10.0`), not
  environment-configurable.
- `database_url: str | None` — read from `DATABASE_URL`; `None` if unset.

`load_dotenv()` runs at import time to populate `os.environ` from a local
`.env` file for development convenience; it is a no-op if no `.env` file is
present. Nothing outside `app/core/config.py` reads environment variables
directly, and no secret value is ever hardcoded in source.

Alembic (`alembic/env.py`) reads the same `settings.database_url` at
migration time rather than storing a URL of its own — one source of truth
for how to reach the database.

## Database boundary

- **Engine & pooling** (`app/db/session.py`) — a single SQLAlchemy
  `Engine` (and the connection pool it owns) is created lazily, on first
  use, and cached — never at import time. This means the application
  starts, and `/health` works, even with no `DATABASE_URL` configured;
  only an operation that actually touches the database can fail on
  missing/bad configuration.
- **Session & transaction** — `session_scope()` is a context manager and
  the *only* place a transaction is committed or rolled back: commit if
  the block completes normally, rollback (and re-raise) on any exception.
  One `Session` per use, never a shared/global one.
- **Repository** (`SeriesRepository`) — the only code that issues SQL for
  series/observation data. It performs writes on the `Session` it's given
  but never calls `commit()`/`rollback()` itself; the caller (the route,
  via `session_scope()`) owns the transaction boundary.
- **Migrations** (`alembic/`) — the schema is never created by
  `Base.metadata.create_all()` at startup. It exists only because a
  migration under `alembic/versions/` created it; schema changes must go
  through a new migration.

## Response models vs. ORM models

Two distinct sets of classes, on purpose:

- `app/models/series.py` (`Observation`, `SeriesResponse`) — Pydantic, the
  **API contract** returned to consumers of both `GET` and `POST .../sync`.
- `app/db/models.py` (`EconomicObservation`, `EconomicSeries`) — SQLAlchemy
  ORM, the **relational shape** persisted in PostgreSQL.

`SeriesRepository` is the only code that translates between them. API
consumers never see the ORM models or raw database rows; the database
never stores the API's Pydantic objects directly.

## Data model

```
economic_series (1) ──< economic_observations (N)
```

| Table | Key columns |
|---|---|
| `economic_series` | `id` (PK), `series_id` (unique, e.g. `"UNRATE"`), `title`, `units`, `source`, `created_at`, `updated_at` |
| `economic_observations` | `id` (PK), `economic_series_id` (FK → `economic_series.id`, `ON DELETE CASCADE`), `observation_date`, `value` (nullable), `created_at`; `UNIQUE(economic_series_id, observation_date)` |

`economic_series.id` is the internal database identity; `series_id` is the
external, FRED-assigned business identifier — kept as separate columns
deliberately (see [ADR-006](../adr/006-postgresql-persistence.md)).

**No schema change in Increment 005.** Transformations (`absolute_change`,
`percent_change`, `moving_average`) are computed on demand from these same
two tables and are never persisted — there is no derived-data table, and
none of the transformation-engine's queries required a new index: the
existing `uq_observation_series_date` unique constraint's backing btree
index on `(economic_series_id, observation_date)` already serves both the
full-range query and the "preceding observations" query the transform
endpoint added.

## Response contract

API consumers only ever receive `app/models/series.py`'s Pydantic models —
never FRED's raw JSON and never a raw database row.
`GET /api/v1/series/{series_id}` and `POST /api/v1/series/{series_id}/sync`
return the same shape:

```json
{
  "series_id": "UNRATE",
  "title": "Unemployment Rate",
  "units": "Percent",
  "source": "FRED",
  "observations": [
    { "date": "2026-07-01", "value": 4.1 },
    { "date": "2026-08-01", "value": null }
  ]
}
```

`GET /api/v1/series/{series_id}/observations` returns
`SeriesObservationsResponse`, which extends that same shape (via Pydantic
inheritance, not field duplication) with pagination metadata:

```json
{
  "series_id": "UNRATE",
  "title": "Unemployment Rate",
  "units": "Percent",
  "source": "FRED",
  "observations": [
    { "date": "2024-01-01", "value": 3.7 }
  ],
  "pagination": {
    "limit": 100,
    "offset": 0,
    "returned": 1,
    "total": 720
  }
}
```

`GET /api/v1/series/{series_id}/transform` returns `SeriesTransformResponse`
— a distinct shape (not built on `SeriesResponse`, since its `observations`
carry both the original and derived value per point, a genuinely different
shape from plain `Observation`):

```json
{
  "series_id": "UNRATE",
  "title": "Unemployment Rate",
  "units": "Percent",
  "source": "FRED",
  "transformation": { "type": "absolute_change", "window": null },
  "observations": [
    { "date": "2025-01-01", "original_value": 4.0, "value": null },
    { "date": "2025-02-01", "original_value": 4.2, "value": 0.2 }
  ]
}
```

For `moving_average`, `transformation.window` carries the window size used
(`null` for `absolute_change`/`percent_change`, which don't take one).

Notes on the current implementation:
- On `GET /api/v1/series/{series_id}` (FRED-backed), `observations` is the
  10 most recent data points (`DEFAULT_OBSERVATION_LIMIT` in
  `app/services/economic_data.py`), ordered oldest → newest, and is not
  paginated. On `GET .../observations` (database-backed), `observations`
  is one page — up to `limit`, offset by `offset`, ordered per `order` —
  of whatever's actually persisted, with `pagination.total` reporting how
  many rows matched before pagination. `GET .../transform` always returns
  the *entire* requested date range in ascending order, unpaginated (see
  the journal for why pagination doesn't compose safely with derived
  values that depend on a preceding point).
- `value` is `null` when FRED reports a missing observation (FRED's raw `"."`),
  both in these responses and as stored (`NULL`) in `economic_observations`.
  On `.../transform`, `value` is also `null` whenever the transformation
  itself cannot produce a result there (no predecessor, a missing source
  value, division by zero, or not yet enough points for a moving average)
  — `original_value` still shows what was actually persisted for that date.
- `source` is currently always the literal string `"FRED"` — there is only
  one provider.
- `GET /api/v1/series/{series_id}` never touches the database — it is a
  pure, read-only pass-through to FRED, unchanged since Increment 002.
  `GET .../observations` and `GET .../transform` never touch FRED — both
  are pure, read-only paths over PostgreSQL (`.../transform` additionally
  computes over what it reads, in-process, before responding). `POST .../sync`
  is the only operation that writes, and the only path that touches both
  FRED and PostgreSQL.

## Health endpoint

`GET /health` is unchanged since Increment 001: a synchronous route with no
dependencies, returning `{"status": "ok"}`. It exists to prove the process
is up and serving, independent of any external integration's (FRED's or
the database's) health.

## External provider boundary

`FREDClient` (`app/clients/fred.py`) is the *only* code in the repository
that knows FRED's base URL, query parameter names, or response shape. It
communicates failure to its caller exclusively through five exception
types (`FREDError` and four subclasses — not-found, auth, timeout,
upstream/malformed), never through raw `httpx` exceptions or FRED's raw
error payload. Everything above the client (`EconomicDataService`, the
route) only ever sees those typed exceptions or valid data.

## What is deliberately NOT part of this architecture yet

The following are intentionally absent — not overlooked:

- **Database as a cache for the FRED-backed endpoint** —
  `GET /api/v1/series/{series_id}` still does not read from PostgreSQL and
  has no fallback/freshness logic; it answers strictly from FRED, as it
  always has. `GET .../observations` reads the database, but only because
  a client explicitly asked for persisted data — there is still no
  automatic "serve from DB if fresh enough, else hit FRED" behavior
  anywhere, and no cache invalidation.
- **Automatic/background synchronization** — no scheduler, no background
  job, no Celery, no message queue. Sync only happens when a client calls
  `POST .../sync`.
- **Multiple data providers** — FRED is the only source. `EconomicDataService`
  is structured so a second provider could be added behind it later, but
  no such abstraction (registry, plugin interface, etc.) exists yet.
- **AI/LLM functionality** — no reasoning layer, tool calling, RAG, or
  embeddings.
- **Authentication/authorization** — the API is unauthenticated; anyone who
  can reach it can call it.
- **Async I/O** — both `FREDClient` and the database session are
  synchronous by deliberate choice (see [ADR-003](../adr/003-fred-rest-httpx.md)
  and [ADR-007](../adr/007-synchronous-sqlalchemy.md)), even though
  FastAPI/Uvicorn support async routes and SQLAlchemy supports async
  sessions.
- **Containerization / cloud infrastructure** — no Dockerfile, no deployment
  configuration, no Terraform.
- **Observability** — no structured logging, metrics, or tracing beyond
  Uvicorn's default access logs.
- **Automated test suite** — verification so far has been done by running
  the live application and scripted checks against a real database, not a
  committed test suite.
- **Generic repository/Unit-of-Work framework** — `SeriesRepository` is a
  single, concrete class for exactly the persistence this increment needs
  (see [ADR-009](../adr/009-repository-boundary.md)); no base class or
  abstraction exists for a second repository that doesn't exist yet.
- **Persisted/cached derived data** — `.../transform` results are never
  stored; every call recomputes from raw `economic_observations`. No
  invalidation, versioning, or staleness concern exists for derived data
  because none of it is retained anywhere.
- **Pagination on derived data** — `.../transform` always returns its
  full requested range in one response; `limit`/`offset` don't apply
  here (unlike `.../observations`), because a derived value can depend on
  a preceding point that a naive page boundary could cut off.
- **Transformations beyond the three implemented** — no year-over-year,
  CAGR, volatility, z-score, or interpolation; no multi-series comparison
  or correlation.

## Future direction (not implemented)

This section is a pointer to intent only — nothing below exists in the
codebase today. Per the project purpose, later increments are expected to
add, in some order: a freshness policy connecting the FRED-backed and
database-backed read paths (e.g. serving from PostgreSQL with an
explicit staleness check, rather than two independent endpoints),
additional transformations or a pagination strategy for derived data if a
real need emerges, additional external data providers, an AI
reasoning/tool-calling layer over the persisted and derived data, and
production infrastructure concerns (Docker, CI/CD, observability, cloud
deployment). Each will get its own ADR(s) and journal entry when it
happens, the same as Increments 001–005.
