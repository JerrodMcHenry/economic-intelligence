# Engineering Journal

Chronological record of what was built, why, and what was learned. This is a
companion to the code, the git history, and the [Architecture Decision
Records](adr/) — not a replacement for any of them. Where a decision was
significant enough to deserve its own record, this journal links to it
instead of re-explaining it in full.

---

## Project Purpose

This repository is the foundation of an **Enterprise AI Economic Intelligence
Platform**: a system intended to eventually combine authoritative public
economic data, private/customer data, structured storage, and AI reasoning
into a single interface a user or another system can query.

The long-term direction includes things like a persistent database, multiple
external data providers, AI-driven reasoning and tool use over that data, and
proper production infrastructure (containerization, observability, CI/CD,
cloud deployment). **None of that exists yet.** As of this journal, the
repository is a minimal FastAPI backend with one real external integration
(FRED). Every future capability is being added deliberately, one increment at
a time, specifically so that each layer is understood and verified before the
next is built on top of it.

## Engineering Workflow

Each increment follows the same loop:

```
Important decisions
   -> scoped implementation
   -> verification / debugging
   -> architecture review
   -> documentation
   -> commit / push
   -> next increment
```

AI coding tools (this project is being built with Claude Code) materially
speed up the *implementation* step — writing boilerplate, wiring modules
together, running verification commands. They do not replace the steps
around it. Architectural decisions are made deliberately and recorded (see
`docs/adr/`), every meaningful behavior is verified by actually running the
application rather than trusting that generated code is correct, and nothing
is committed without a human review of the diff. The goal is speed in
mechanics, not speed in judgment.

---

## Increment 001 — Backend Foundation

**Objective:** establish the minimal Python/FastAPI backend foundation —
project configuration, a `GET /health` endpoint, and nothing else.
Deliberately excluded from this increment: databases, external APIs, AI
functionality, Docker, auth — all of it, regardless of how small, was left
for a later increment.

### Python environment

The project standardizes on **Python 3.12** for development and runtime.
`.venv` was, at one point, accidentally created with a freshly-installed
Python 3.14 interpreter (Homebrew's `python@3.14`) rather than 3.12. This was
caught before any real work was built on top of it and corrected by deleting
`.venv` and recreating it from a Python 3.12 interpreter
(`/Library/Frameworks/Python.framework/Versions/3.12`, python.org
distribution, 3.12.5 at time of writing).

The choice of 3.12 over the newer 3.14 was deliberate: 3.12 is the more
mature target for third-party library compatibility and production
stability at this point in the ecosystem's adoption curve. See
[ADR-001](adr/001-python-312-runtime.md) for the full reasoning.

**Development runtime vs. declared compatibility are two different
concerns**, and this project treats them separately:

| Concern | Where it lives | Current value |
|---|---|---|
| What interpreter actually runs the code locally | `.venv` (created from a specific interpreter binary) | Python 3.12.5 |
| What versions the *package* declares itself compatible with | `pyproject.toml` → `requires-python` | `>=3.12` |

`requires-python` went through two revisions before landing on `>=3.12`:
it started at `>=3.11` (inherited from an earlier scaffold, before the
3.12 standardization decision), was briefly tightened to `>=3.12,<3.13`,
and was then loosened back to `>=3.12` — there was no actual technical
finding of a 3.13+ incompatibility, so declaring one would have been an
artificial constraint. The rule applied: only encode a restriction that is
backed by a real, known reason.

### Editable install (`pip install -e .`)

The project is installed into `.venv` with `pip install -e .` rather than
copied or run via ad-hoc `sys.path` manipulation. This does two things:

- It makes `import app` resolve correctly from anywhere the interpreter is
  invoked (tests, scripts, the ASGI server) without hacks, because the
  package is genuinely installed.
- It's *editable* — changes to source files take effect immediately, with
  no reinstall step — while still validating that `pyproject.toml`'s
  packaging metadata is correct, since a real (if lightweight) build
  happens. `economic_intelligence.egg-info/` is the build metadata this
  produces; see the Increment 002 section for what that directory is and
  why it should not be committed.

### Editor/runtime mismatch (VS Code interpreter selection)

A common failure mode with this setup — worth documenting even briefly
because it costs real debugging time when it happens — is the editor's
Python extension pointing at a *different* interpreter than the project's
`.venv` (e.g. a global/system Python, or a previous virtual environment).
When that happens, `import fastapi` and similar lines show as unresolved
in the editor even though the application runs correctly from the command
line, because the editor's language server is checking a Python
environment that never had FastAPI installed in it. The fix is always to
point the editor explicitly at `.venv`'s interpreter, not to reinstall
anything. The lesson generalizes: **the editor's view of the environment
and the actual execution environment are two different sources of truth,
and only one of them (actually running the code) is authoritative.**

### FastAPI, Uvicorn, and `GET /health`

`app/main.py` defines the FastAPI application object and a single route:

```python
@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

FastAPI was chosen as the web framework and Uvicorn as the ASGI server that
runs it — see [ADR-002](adr/002-fastapi-backend.md) for why, versus
alternatives like Flask or Django.

### Initial architecture

At the end of Increment 001, the entire application was one file:
`app/main.py`, containing the `FastAPI()` app object and the `/health`
route. No layering was needed yet because there was no logic to layer —
introducing `api/`, `services/`, `clients/` etc. at this stage would have
been structure for its own sake, not because any of those responsibilities
existed.

### Git/GitHub checkpoint

Work was committed as `chore: initialize FastAPI backend`, following an
earlier placeholder `first commit`.

### Lessons from Increment 001

- Keep "what runs the code" (the virtualenv's interpreter) and "what the
  package claims to support" (`requires-python`) as two explicitly
  reasoned-about values — don't let one silently drift from the other.
- An editable install (`pip install -e .`) is worth doing even for a
  single-file app; it removes an entire class of import-path problems for
  free, at essentially no cost.
- When the editor disagrees with the terminal about whether an import
  resolves, trust the terminal — verify by running, not by reading a
  squiggly underline.

---

## Increment 002 — FRED API Integration

**Objective:** add the project's first real external data integration —
`GET /api/v1/series/{series_id}`, backed by the Federal Reserve Economic
Data (FRED) REST API — and establish a request-flow pattern
(route → service → client → models) that later integrations can follow
without re-deciding these questions from scratch.

### Direct REST integration, not a FRED SDK

The FRED API is called directly over HTTP rather than through a third-party
FRED Python package. This trades a small amount of convenience (no
pre-built request helpers) for explicit control over every request: exact
query parameters, timeout behavior, and — critically — how FRED's error
responses get turned into *our* exceptions rather than whatever shape a
third-party SDK happens to raise. See
[ADR-003](adr/003-fred-rest-httpx.md).

### `httpx`, not `requests`

`httpx` was added as the HTTP client library. It's a modern fit for the
FastAPI/ASGI ecosystem and supports both sync and async usage under one
API, which matters for the next decision below. `requests` was considered
and rejected only because there was no reason to prefer it — no capability
`httpx` lacked that `requests` provided for this use case.

### Synchronous first

Every FRED call in this increment is synchronous (`httpx.Client`, blocking
calls), even though FastAPI supports `async def` routes natively. This was
a deliberate choice, not an oversight: there is no concurrency requirement
yet (the service handles one external call chain per request, and nothing
is fanning out to multiple providers or handling meaningful request
volume). Adding `async`/`await` throughout the client and service layers
now would be complexity paid for before it's earned. Full reasoning,
including what would justify revisiting this, is in
[ADR-003](adr/003-fred-rest-httpx.md).

### Environment configuration: `.env` vs `.env.example`

`FRED_API_KEY` is read from the process environment
(`app/core/config.py`), optionally populated for local development by a
`.env` file via `python-dotenv`'s `load_dotenv()`. `load_dotenv()` is a
safe no-op if no `.env` file exists (e.g. in a deployed environment where
the variable is set directly).

- `.env` — holds the real local API key. Listed in `.gitignore`; never
  committed.
- `.env.example` — a committed placeholder (`FRED_API_KEY=your_fred_api_key_here`)
  documenting which variable a new environment needs to set, with no real
  value in it.

One non-obvious behavior worth recording: `python-dotenv`'s default
`load_dotenv()` locates `.env` by walking **up from the importing module's
file location**, not from the process's current working directory. This
matters if you're ever trying to verify "what happens with no `.env`
present" by launching the server from a different directory — changing
directories alone doesn't hide the file from `load_dotenv()`; the file
itself has to be absent (or the variable already set in the environment,
which *does* take precedence — `override=False` is the default, so a
pre-set environment variable always wins over `.env`).

### Secret-handling lesson (real incident)

During the initial inspection for this increment, `.env`'s raw contents
were dumped to the terminal (via `xxd`) purely to check its formatting
(spaces around `=`). That command's output included a fragment of the real
`FRED_API_KEY`, which ended up captured in the AI assistant's conversation
transcript. This was caught immediately, later inspection switched to
redaction-safe methods (checking key *length*, never printing key
*content*; making live API calls through a script that never echoes the
key), and **the key was rotated** afterward as a precaution. Recorded here
because it's a real, reusable lesson: never dump a secrets file to a
terminal/log/transcript to check its *shape* — parse or `wc`/`grep`-count
it instead, and treat any accidental exposure as a rotation event, not
just an embarrassment.

### Explicit timeout on every outbound call

`FREDClient` opens each request through `httpx.Client(timeout=self._timeout)`
(default 10 seconds, `Settings.fred_timeout_seconds`). No request to FRED
can hang indefinitely. This was verified directly — pointing the client at
an unroutable IP address and confirming it raises `FREDTimeoutError` within
the configured timeout window, and that this becomes an HTTP `504` at the
API layer rather than a hung request.

### Assumptions about external dependency failure

FRED is treated as something that can, at any time: be slow or
unreachable, reject our credentials, report a series that doesn't exist, or
return a response that doesn't match the expected shape. All four are
handled *distinctly* (see the exception table below) rather than collapsed
into a single "something went wrong upstream" catch-all — but without
building a large exception hierarchy either. Five exception types in total
(`FREDError` base + four specific subclasses) cover every case the client
needs to raise.

### Normalization and missing-observation handling

FRED returns observation values as strings, and represents a missing
observation with the literal string `"."` (not `null`, not an empty
string). `EconomicDataService._parse_value` handles this explicitly —
`"."` becomes Python `None`, anything else is parsed with `float(...)`.
Leaving this implicit (e.g. letting `float(".")` raise and bubble up as an
unhandled 500) would have turned a normal, documented FRED behavior into
an application bug.

FRED also returns observations newest-first; the service reverses them so
the API's `observations` array reads chronologically (oldest → newest),
which is the more natural shape for a consumer plotting a time series.

### Response contract (Pydantic models)

`app/models/series.py` defines `Observation` (`date`, `value: float |
None`) and `SeriesResponse` (`series_id`, `title`, `units`, `source`,
`observations: list[Observation]`). This is *our* contract, not FRED's —
see [ADR-005](adr/005-own-data-contract.md) for why raw FRED JSON is never
returned to API consumers.

### Route → Service → Client layering

Three layers were introduced, each with one job:

- **`app/api/series.py`** (route) — HTTP concerns only: reads the path
  parameter, checks whether FRED is configured at all, calls the service,
  and translates whatever exception comes back into an `HTTPException`
  with the right status code. No FRED-specific knowledge lives here.
- **`app/services/economic_data.py`** (`EconomicDataService`) — the
  use-case: ask the client for series metadata and observations, normalize
  both into our models. No HTTP status codes, no knowledge of `httpx`.
- **`app/clients/fred.py`** (`FREDClient`) — all FRED-specific HTTP
  communication: building the request, applying the timeout, and turning
  FRED's response (including its error responses) into either a plain dict
  or one of the five typed exceptions.

Why not put this directly in the route function? At three lines of actual
logic it would have been tempting — but the reasoning behind not doing
that, and how to tell a useful layer from a decorative one, is recorded in
[ADR-004](adr/004-route-service-client.md) rather than repeated here.

### Error translation

| Failure | Where it originates | Exception raised | HTTP status | Client-facing detail |
|---|---|---|---|---|
| `FRED_API_KEY` not set at all | `app/api/series.py`, checked before a client is even constructed | *(none — early return)* | `503` | "FRED integration is not configured on this server." |
| Series ID doesn't exist in FRED | FRED responds `400` with `"...series does not exist"` | `FREDSeriesNotFoundError` | `404` | "Series '{id}' was not found." |
| FRED rejects the API key (missing/malformed/unregistered) | FRED responds `400` with `"api_key"` in the message | `FREDAuthError` | `503` | "Economic data integration is currently unavailable." |
| Request to FRED exceeds the timeout | `httpx.TimeoutException` | `FREDTimeoutError` | `504` | "Upstream FRED request timed out." |
| Network failure, non-JSON body, or missing expected fields | `httpx.HTTPError` / JSON decode failure / `KeyError` during normalization | `FREDUpstreamError` | `502` | "Upstream FRED service error." |

`FREDAuthError` was originally mapped to `502`, then deliberately changed to
`503` on review: a rejected credential is *our* server-side configuration
being unavailable, not a gateway-to-a-working-upstream problem — so `503
Service Unavailable` communicates the situation more accurately to a
consumer than `502 Bad Gateway` does. Neither the specific FRED error
message nor any credential material is ever included in the response.

FRED itself is a quirky upstream to translate correctly: both "bad series
ID" and "bad API key" arrive as HTTP `400`, distinguished only by the text
of `error_message` — there's no clean status-code split to key off of.
`FREDClient._error_for_bad_request` does simple substring matching on that
message. It's the only signal FRED provides; it does mean this piece of
the client is coupled to FRED's current wording, which is called out in
the code as an explicit tradeoff rather than hidden.

### `economic_intelligence.egg-info/` — generated, then wrongly tracked

`pip install -e .` generates `economic_intelligence.egg-info/` (package
metadata: `PKG-INFO`, `SOURCES.txt`, `requires.txt`, etc.) as a build
artifact — it's regenerated automatically on every install and belongs
only to the local checkout, never to source control. It was accidentally
committed in the very first commit, before `.gitignore` had an entry for
it. Fixing this required two separate actions, because they solve two
different problems:

1. `git rm --cached -r economic_intelligence.egg-info/` — removes it from
   Git's index (stops tracking it) **without deleting the local files**,
   so the editable install keeps working.
2. Adding `*.egg-info/` to `.gitignore` — prevents it from being
   re-added by an accidental `git add .` in the future.

Doing only one of these is not sufficient: ignoring a file that's already
tracked has no effect (Git keeps tracking files it already knows about
regardless of `.gitignore`), and un-tracking it without ignoring it means
the very next `git add .` re-adds it.

### Verification performed

Every behavior above was verified by actually running the application
(`uvicorn app.main:app`) and issuing real requests — not just by reading
the code:

- `GET /health` → `200 {"status": "ok"}`, unchanged from Increment 001.
- `GET /api/v1/series/UNRATE` against the real FRED API with a valid key →
  `200` with the normalized `SeriesResponse` shape.
- `GET /api/v1/series/NOTREALSERIES123` → `404`.
- Server started with `FRED_API_KEY` unset and no `.env` present → `503`
  ("not configured").
- Server started with a well-formed but invalid/rejected key → `503`
  ("currently unavailable"), confirmed to leak no FRED-specific detail.
- Client pointed at an unroutable host → `FREDTimeoutError` raised within
  the configured timeout, and confirmed end-to-end as `504` through the
  actual route (via a mocked client construction, since forcing a real
  FRED timeout isn't practical to reproduce on demand).
- `.env` and `economic_intelligence.egg-info/` both confirmed
  git-ignored/untracked before and after changes.

### Lessons from Increment 002

- Real third-party APIs rarely map cleanly onto REST status-code
  conventions — FRED's "everything wrong is a 400" behavior had to be
  discovered by actually calling the API with bad inputs, not assumed from
  documentation skimming.
- Never dump a secrets file to inspect its *format* — inspect it in ways
  that can't leak *content* (length checks, structural parsing without
  printing values), and treat any accidental exposure as a rotation event.
- Normalize at the boundary closest to the business logic (the service
  layer), not inside the HTTP client — it keeps the client a dumb, honest
  transport layer and keeps the "what does FRED's weirdness mean to us"
  logic in one reviewable place.
- A small number of purpose-built exception types, chosen to match exactly
  the HTTP-status decisions the API layer needs to make, beats both a
  single generic exception (loses information) and a deep exception
  hierarchy (adds ceremony with no payoff at this scale).
- A build artifact that was committed once will keep coming back —
  removing it from the index and ignoring it going forward are both
  required, and neither alone is enough.

---

## Increment 003 — PostgreSQL Persistence

**Objective:** give the application a persistence layer — retrieve real FRED
data, normalize it (as already happened in Increment 002), and store the
series and its observations transactionally in PostgreSQL. Explicitly not
in scope: using the database as a cache, database-first reads, freshness
policies, or any automatic refresh — this increment only adds the ability
to *write* normalized data deliberately, via a new endpoint.

### Architecture before this increment

At the end of Increment 002, the request flow was:

```
Client -> Route -> EconomicDataService -> FREDClient -> FRED API
```

Every request re-fetched from FRED live; nothing was ever stored.
`GET /api/v1/series/{series_id}` was, and remains, a read-only pass-through.

### Why persistence now

The project's purpose is to combine external data with the application's
own reliable data infrastructure. Increment 002 proved the external
integration works; this increment proves the application can own data
durably rather than being a pure proxy in front of FRED. It's also the
natural point to introduce the skills a "data engineering" platform is
supposed to demonstrate: relational modeling, constraints, transactions,
and version-controlled schema migrations — before layering AI reasoning on
top of data nothing actually persists.

### PostgreSQL, not SQLite or a NoSQL store

The domain here is genuinely relational: one series has many observations,
each observation belongs to exactly one series, and "don't duplicate this
row" is a real constraint the database should enforce, not something
application code should have to re-check by convention. Three realistic
alternatives and why they were set aside:

- **SQLite** — fine for a single-file embedded use case, but doesn't
  reflect how this system would actually run in production (concurrent
  connections, a separate database process, a real connection pool), and
  the project explicitly wants that production-relevant experience.
- **A document store (e.g. MongoDB)** — would mean either duplicating
  observation arrays inside series documents (awkward uniqueness
  enforcement, awkward partial updates) or building a manual "foreign key"
  by convention with no real referential integrity. The data doesn't have
  a variable/document-shaped structure that would benefit from schema
  flexibility — it has two fixed, related shapes.
- **A key-value store (e.g. DynamoDB)** — would push relational query
  patterns (e.g. "all observations for this series between two dates")
  into application code instead of letting the database do them natively.

PostgreSQL was already the decided technology (see
[ADR-006](adr/006-postgresql-persistence.md)); this section records *why*
that fits the actual data shape, not just that it was chosen.

### Relational data model

Two tables, matching the one-to-many relationship in the domain:

```
economic_series (1) ──< economic_observations (N)
```

**`economic_series`** — one row per FRED series ever synced.

| Column | Type | Notes |
|---|---|---|
| `id` | `integer`, PK | Internal database identity — see below. |
| `series_id` | `varchar(64)`, unique, not null | The provider's business identifier, e.g. `"UNRATE"`. |
| `title` | `varchar(255)`, not null | |
| `units` | `varchar(64)`, not null | |
| `source` | `varchar(32)`, not null, default `'FRED'` | Only one provider exists today; the column exists so a second provider wouldn't require a schema change. |
| `created_at` | `timestamptz`, not null, server default `now()` | |
| `updated_at` | `timestamptz`, not null, server default `now()`, updated on write | |

**`economic_observations`** — one row per (series, date).

| Column | Type | Notes |
|---|---|---|
| `id` | `integer`, PK | |
| `economic_series_id` | `integer`, FK → `economic_series.id`, not null, indexed | See naming note below. |
| `observation_date` | `date`, not null | |
| `value` | `double precision`, nullable | `NULL` represents a FRED-reported missing observation (the same thing `Observation.value: float \| None` already represents at the API layer — see [ADR-005](adr/005-own-data-contract.md)). |
| `created_at` | `timestamptz`, not null, server default `now()` | |

`UNIQUE (economic_series_id, observation_date)` — the database itself
guarantees one row per series/date, rather than trusting application code
to always check first.

### Internal identity vs. provider identity

`economic_series.id` (an auto-incrementing integer) and
`economic_series.series_id` (FRED's string, `"UNRATE"`) are deliberately
different columns with different jobs. The foreign key on
`economic_observations` points at `economic_series.id` — the *internal*
identity — not at the provider's string. This matters for two reasons:
an integer FK is cheaper to index and join on than a string one, and, more
importantly, the relational structure doesn't depend on FRED's identifier
scheme being stable or collision-free forever — if a second provider is
ever added with its own identifier format, the internal `id` is unaffected.

### Foreign key naming

The FK column is named `economic_series_id`, not `series_id`. Reusing
`series_id` for the FK would have created real ambiguity: is "series_id"
the FRED string (`"UNRATE"`) or the internal row number this observation
belongs to? Naming it `economic_series_id` makes the column
unambiguously "the `id` column of `economic_series`" at a glance, in the
schema and in every query.

### The SQLAlchemy relationship

```python
class EconomicSeries(Base):
    observations: Mapped[list["EconomicObservation"]] = relationship(
        back_populates="series", cascade="all, delete-orphan"
    )

class EconomicObservation(Base):
    series: Mapped["EconomicSeries"] = relationship(back_populates="series")
```

A plain one-to-many, both directions declared so either side can be
navigated in Python. `cascade="all, delete-orphan"` means deleting an
`EconomicSeries` deletes its observations too — the correct default for
this domain (an observation orphaned from its series is meaningless), and
nothing more elaborate (no many-to-many, no polymorphic association) was
introduced, because nothing in this increment needs it.

### SQLAlchemy: engine, pooling, session, transaction

A few ORM/database concepts as they concretely apply in this codebase
(`app/db/session.py`):

- **Engine** (`create_engine(...)`) — the object that knows how to open
  connections to PostgreSQL and owns a **connection pool** (a small set of
  reused connections, so the application isn't opening a fresh TCP/auth
  handshake for every query). Created once, lazily, the first time a
  database operation is actually attempted — not at import time — so the
  app can still start (and `/health` still work) even with no
  `DATABASE_URL` set, mirroring the same lazy-config pattern established
  for `FRED_API_KEY` in Increment 002. `pool_pre_ping=True` is the one
  pool setting applied, so a stale connection (e.g. after a database
  restart) is detected and replaced rather than causing a confusing
  failure — no other pool tuning was done; the defaults are sensible for
  this scale.
- **Session** — a single unit-of-work bound to one engine connection at a
  time: it tracks objects loaded/added/changed and turns that into SQL
  when flushed. One `Session` is created per `session_scope()` call
  (i.e., per request that touches the database) — never a global, shared
  session.
- **Transaction** — everything that happens between opening a session and
  either committing or rolling it back. `session_scope()` (a context
  manager) is the *only* place a commit or rollback happens: it commits if
  the `with` block completes normally, rolls back if any exception
  propagates out of it, and always closes the session. `SeriesRepository`
  never calls `commit()` or `rollback()` — it only `add()`s and
  `flush()`es (flush sends SQL to Postgres within the open transaction,
  without ending it — used here so a newly created series' auto-generated
  `id` is available in Python before its observations are inserted).

This gives the operation exactly the "BEGIN … COMMIT or ROLLBACK" shape
the increment asked for, with the transaction boundary owned in one place
(see [ADR-009](adr/009-repository-boundary.md) for the fuller reasoning
on why the repository itself stays commit-free).

### Repository / data-access boundary

`SeriesRepository` (`app/repositories/series_repository.py`) is the only
code that issues SQL for series/observation data. It takes a `Session` the
caller already has open, and exposes one real operation:
`save_series(data: SeriesResponse) -> EconomicSeries`, which upserts both
the series row and its observations. No generic `Repository[T]` base
class, no interface separate from the one concrete implementation — see
[ADR-009](adr/009-repository-boundary.md) for why a generic framework was
deliberately not built here.

### Alembic: migrations as the schema-management strategy

The schema is never created by calling `Base.metadata.create_all()` at
app startup — that would mean the "current schema" is just whatever the
Python models happen to say *right now*, with no history and no reviewable
diff when they change. Instead:

- `alembic/env.py` imports `Base.metadata` from `app/db/base.py` /
  `app/db/models.py` and points Alembic's `--autogenerate` at it, and
  overrides `alembic.ini`'s placeholder `sqlalchemy.url` with the real
  `DATABASE_URL` from the app's own `Settings` at runtime — so no
  credential ever needs to live in a committed file.
- The first migration (`alembic/versions/6412695f6f9d_*.py`) was
  generated with `alembic revision --autogenerate`, then reviewed by hand
  against the ORM models before being applied — autogenerate is a
  starting draft, not something to trust blindly. It matched the models
  exactly: both primary keys, the foreign key with `ON DELETE CASCADE`,
  the unique index on `series_id`, the unique constraint on
  `(economic_series_id, observation_date)`, and correct nullability
  throughout.
- The migration's `downgrade()` drops the tables in dependency order
  (observations before series) — verified by reading it, not just trusting
  the autogenerated output.

### Upsert / idempotency behavior

`SeriesRepository.save_series`:

1. Look up the series by its business identifier (`series_id`). If it
   doesn't exist, insert it and `flush()` to get its new `id`; if it
   exists, update its `title`/`units`/`source` in place — same row, same
   `id`, always.
2. For each observation FRED returned, look up whether a row already
   exists for that `(series, date)`. If yes, update its `value` in place;
   if no, insert a new row.

Calling `POST /api/v1/series/UNRATE/sync` twice therefore does not create
a second `economic_series` row or duplicate any `economic_observations`
row — verified directly (see Verification below). Observations for dates
*not* present in the latest FRED response are left untouched — the sync
operation never deletes history, only adds or updates what FRED currently
reports.

### `DATABASE_URL` configuration

Read the same way `FRED_API_KEY` is (`app/core/config.py`,
`os.environ.get("DATABASE_URL")`, populated for local dev via `.env`).
Local development uses:

```
DATABASE_URL=postgresql+psycopg://<local-user>@localhost:5432/economic_intelligence
```

No password segment — the local PostgreSQL installation used for this
increment (Homebrew `postgresql@16`) is configured with `trust`
authentication for local/loopback connections (`pg_hba.conf`), which is
standard for local development and predates this increment; it is not
something this increment changed. `.env.example` documents the variable
with a generic `user:password@localhost:5432/...` placeholder — a
production `DATABASE_URL` would include real credentials, which is
exactly why the variable is environment-sourced and never hardcoded.

### `POST /api/v1/series/{series_id}/sync` semantics

Added as a new endpoint rather than changing `GET`'s behavior:
`GET /api/v1/series/{series_id}` remains a pure read against FRED, as
before — it does not touch the database, and calling it does not persist
anything. `POST /{series_id}/sync` is the explicit, deliberate operation
that fetches from FRED *and* persists — `POST` because it changes
server-side state, which is exactly what happened here and exactly why a
`GET` was not reused for it.

### Failures encountered during this increment

- **`python-dotenv` and multi-line `.env` editing**: appending a new line
  to `.env` with a shell `>>` redirect landed on the same line as the
  existing `FRED_API_KEY` entry, because the file had no trailing newline
  — corrupting it into one unparsceable line. Caught immediately (by
  checking key names present via `grep -o '^[A-Z_]*'`, not by printing
  values) and fixed. Lesson: when a `.env` file might lack a trailing
  newline, write the whole file's structure deliberately rather than
  blindly appending.
- **A second accidental secret exposure**: inspecting `.env`'s current
  state at one point used the file-reading tool directly instead of a
  redaction-safe check, printing the real `FRED_API_KEY` value into the
  session a second time (the first was in Increment 002). Caught
  immediately; **the key should be rotated again**. Recorded here plainly
  because repeating a known mistake is itself worth a permanent note:
  the rule from Increment 002 ("never dump a secrets file — check
  structure, not content") has to be followed by *every* tool used to
  touch the file, including ones that don't look like "dumping" a file.
- **FRED latency near the configured timeout**: live verification of
  `POST /sync` hit the existing 10-second `FRED_TIMEOUT_SECONDS` a few
  times during testing, because FRED's real response time fluctuated
  between roughly 3 and 11 seconds over the course of this session. Not a
  bug — the timeout did exactly what it's supposed to (see
  [request-flows.md](architecture/request-flows.md)) — but it's a
  concrete data point that 10 seconds is a tight margin against FRED's
  actual observed latency, worth revisiting if it causes real friction.

### Verification performed

All done against the real, locally running PostgreSQL instance and the
real FRED API:

- App starts; `GET /health` → `200 {"status": "ok"}`, unchanged.
- `GET /api/v1/series/UNRATE` → still `200` with normalized FRED data,
  unaffected by the database changes.
- `alembic upgrade head` applied cleanly against a freshly created
  `economic_intelligence` database; `\d economic_series` /
  `\d economic_observations` in `psql` confirmed the schema matches the
  ORM models exactly (PK, FK with `ON DELETE CASCADE`, both unique
  constraints, correct nullability).
- `POST /api/v1/series/UNRATE/sync` (first real call): `200`, and a
  direct `psql` query confirmed exactly one `economic_series` row
  (`series_id='UNRATE'`) and ten `economic_observations` rows, dates and
  values matching what FRED returned.
- The same sync call repeated three times total: still exactly one
  series row, still ten observation rows — no duplicates.
- A targeted test through `SeriesRepository` directly (not through the
  API) changed the series title and one observation's value, then called
  `save_series` again: confirmed the *same* series `id` with the *updated*
  title (`updated_at` genuinely advanced, confirmed via `psql`, not just
  the in-memory object), the existing observation's value updated in
  place, and a new observation date inserted — proving the update path,
  not just the no-op "nothing changed" path. The synthetic test data was
  then removed and a real sync re-run to leave the database holding only
  genuine FRED data.
- Rollback: a script began a `session_scope()`, flushed a new (fake)
  series row — sending the `INSERT` to PostgreSQL inside the still-open
  transaction — then raised an injected exception before committing.
  Confirmed the series was **not** present afterward: `flush()` alone is
  not durable, and the `except`/`rollback()` path in `session_scope()`
  correctly discarded it.
- Missing `DATABASE_URL`: sync returned `503`
  ("Database is not configured on this server."); `/health` on the same
  process still returned `200`.
- Unreachable database (`DATABASE_URL` pointed at a closed port): sync
  returned `503` ("Database is currently unavailable."), and neither the
  HTTP response nor the server log contained the connection string.
- Confirmed via `git status`/`git check-ignore` that `.env` remains
  untracked and ignored, and that no tracked file (including
  `.env.example`, `alembic.ini`) contains anything but the generic
  placeholder connection string.

### Deferred decisions

- **`value` stored as `double precision` (Python `float`)**, matching the
  existing Pydantic `Observation.value: float | None` exactly, rather than
  a fixed-precision `NUMERIC` type. `NUMERIC` would be the more
  traditionally "correct" choice for financial/economic figures (no
  binary floating-point rounding), but it would introduce `Decimal`
  conversions between the ORM and the Pydantic layer for no immediate
  benefit — FRED's own values are already floating-point-precision
  strings. Worth reconsidering if this data is ever used for anything
  precision-sensitive (e.g. downstream calculation, not just display).
- **Upsert implemented as "select, then insert-or-update in Python"**,
  not PostgreSQL's native `INSERT ... ON CONFLICT DO UPDATE`. Simpler to
  read and entirely correct for this increment's single-request,
  low-concurrency usage (and the unique constraint still protects against
  a genuine race, surfacing as an `IntegrityError` mapped to `409`). Under
  real concurrent writes to the same series, the native upsert would be
  more efficient and avoid a rare race window between the `SELECT` and
  the `INSERT`/`UPDATE`; revisit if concurrent sync calls for the same
  series become a real scenario.
- **`POST /sync` returns the same `SeriesResponse` shape as `GET`**,
  rather than a distinct result carrying e.g. counts of rows
  created/updated. Kept minimal deliberately; a richer sync-result model
  is easy to add later if a consumer actually needs to know what changed.

### Reusable engineering lessons

- A relational schema question worth asking on every new entity: does
  this thing have its own lifecycle-independent identity (→ needs its own
  primary key), and is any *other* identifier attached to it (a provider
  code, a public slug) something that should also be unique but never
  double as the join key? Conflating the two saves a column today and
  costs a migration later.
- `Base.metadata.create_all()` and Alembic are not "either works, pick
  one" — only one of them produces a reviewable, revertible history of
  how the schema got to its current shape, which is the actual point of
  migrations.
- Autogenerated migrations are a draft. Reading the generated
  `upgrade()`/`downgrade()` against what was actually intended (PK, FK
  behavior, constraints, nullability) is not optional busywork — it's the
  step that catches the difference between "the tool produced valid SQL"
  and "the tool produced the SQL we meant."
- A transaction boundary should have exactly one owner. Once a repository
  is tempted to call `commit()` "just to be safe," the whole point of an
  explicit `session_scope()` — one operation, one BEGIN, one COMMIT or
  ROLLBACK — is gone; `flush()` (visible to the current transaction,
  not durable) vs. `commit()` (durable) is the tool that makes this
  possible without the repository needing to know whether it's one step
  of a larger operation or the whole thing.
- Verifying "the operation is idempotent" by calling the endpoint twice
  is necessary but not sufficient if both calls happen to hit the
  no-op path (nothing upstream changed). It's worth a second, more
  targeted check that actually forces the update-in-place path to run
  (changed metadata, changed observation value) — otherwise "idempotent"
  and "doesn't do anything on the second call" are easy to confuse.

---

## Increment 004 — Historical Data Query API

**Objective:** make the data Increment 003 started persisting actually
useful by adding a read endpoint over it —
`GET /api/v1/series/{series_id}/observations` — that queries PostgreSQL
directly, with date filtering, ordering, and pagination. Explicitly not in
scope: falling back to FRED, auto-syncing, caching, or any transformation
of the stored values (percent changes, moving averages, etc.).

### Architecture before this increment

```
POST /sync  -> Route -> Service -> FREDClient -> FRED
                              \-> SeriesRepository -> PostgreSQL (write)

GET /series/{id} -> Route -> Service -> FREDClient -> FRED (read, but from FRED, not the DB)
```

Nothing in the application read *from* PostgreSQL — Increment 003 built a
write-only path. `GET /api/v1/series/{series_id}` reads from FRED every
time, same as Increment 002; it was never changed to read the database.

### Why a database read path now, and why it's a distinct path

The persisted data was inert until something could query it — sync writes
data nobody could retrieve without going back to FRED, which defeats the
point of persisting it. This increment adds that missing read path, and
deliberately keeps it separate from the existing FRED-backed
`GET /api/v1/series/{series_id}`:

```
WRITE PATH:  POST /sync         -> Service -> FREDClient   -> FRED       -> Repository -> PostgreSQL
READ PATH:   GET  /observations -> Service -> SeriesRepository -> PostgreSQL
```

`GET /api/v1/series/{series_id}/observations` never imports, constructs,
or calls anything FRED-related — verified directly (see Verification
below) by patching `FREDClient` to raise if instantiated and confirming
the endpoint still succeeds. This is a genuinely different contract from
`GET /api/v1/series/{series_id}`: that endpoint answers "what does FRED
say right now," this one answers "what has our application actually
stored" — they can legitimately disagree if nobody has synced recently,
and that's expected, not a bug, at this stage (no freshness policy exists
yet — see Deferred decisions).

### Query parameters

| Parameter | Type | Default | Constraint |
|---|---|---|---|
| `start_date` | date, optional | none | — |
| `end_date` | date, optional | none | — |
| `limit` | int | 100 | `1 <= limit <= 1000` |
| `offset` | int | 0 | `offset >= 0` |
| `order` | `"asc"` \| `"desc"` | `"asc"` | one of the two literal values |

### Two layers of validation, on purpose

- **FastAPI/Pydantic (route layer)** — `Query(ge=1, le=1000)` on `limit`,
  `Query(ge=0)` on `offset`, a `Literal["asc", "desc"]` type on `order`,
  and `date` typing on `start_date`/`end_date`. These are all things
  FastAPI can reject before any application code runs, and it does:
  malformed dates, an out-of-range `limit`, a negative `offset`, or an
  `order` value that isn't `"asc"`/`"desc"` all come back as `422` with
  FastAPI's own structured validation error body — no code in this
  project had to write that logic.
- **Application rule (service layer)** — `start_date > end_date` is not a
  primitive-type problem (both are individually valid dates); it's a
  cross-field business rule, so it's checked in `EconomicDataService.get_observations`
  and raises a small typed `InvalidDateRangeError`, which the route maps
  to `400` with a fixed, generic message. This is the same
  "primitive validation at the boundary, business rules in the service"
  split the project has used since Increment 002 — FastAPI validates
  *shape*, the service validates *meaning*.

### Filtering, ordering, and pagination (the repository)

`SeriesRepository.get_observations` builds one shared list of SQLAlchemy
`WHERE` conditions — always `economic_series_id == ...`, plus
`observation_date >= start_date` and/or `observation_date <= end_date`
when those were given — and uses the *same* conditions for both:

1. a `SELECT count(*) ... WHERE ...` for the total matching the filters, and
2. a `SELECT * ... WHERE ... ORDER BY ... LIMIT ... OFFSET ...` for the
   actual page.

Sharing the conditions between the two queries is what guarantees
`pagination.total` always reflects exactly what `limit`/`offset` are
paginating over — if the two queries ever drifted (e.g. one used
`start_date` and the other forgot it), `total` and the actual filtered
set would silently disagree.

`ORDER BY observation_date` (ascending or descending per `order`) is the
entire sort key — no secondary tiebreaker column was added, because none
is needed: `uq_observation_series_date` (`UNIQUE(economic_series_id,
observation_date)`) already guarantees no two observations in the same
series share a date, so within one series' results, `observation_date`
alone is already a unique, deterministic sort key.

### `LIMIT`/`OFFSET`, and its known cost

Pagination is plain SQL `LIMIT`/`OFFSET` — the simplest option, and
adequate for this project's current data volumes (one series currently
holds 10 observations; even a long daily series over decades is a few
thousand rows). The known tradeoff: `OFFSET` on a large table makes
PostgreSQL walk and discard `offset` rows before it can return anything,
so a very large `offset` against a very large table gets slower as the
offset grows — a cost cursor/keyset pagination (paginating by "give me
rows after the last date I saw" instead of a row count) avoids. Not
implemented here deliberately — it would be solving a scale problem this
project doesn't have yet, at the cost of a less obvious API (`offset` is
immediately understandable; a keyset cursor is not, without explanation).
Worth revisiting if a series' observation count grows enough, or query
latency at high offsets actually becomes measurable, but not before.

### Indexing — why no migration was needed this increment

Increment 003's migration already created
`uq_observation_series_date`, a unique constraint on
`(economic_series_id, observation_date)`. PostgreSQL backs every unique
constraint with a btree index automatically — confirmed directly via
`psql`'s `\d economic_observations`, which shows
`"uq_observation_series_date" UNIQUE CONSTRAINT, btree (economic_series_id, observation_date)`.

That composite index's leading column is exactly `economic_series_id`,
which is exactly this increment's dominant filter
(`WHERE economic_series_id = ?`), and a btree index on
`(economic_series_id, observation_date)` also directly serves range
filtering and ordering on `observation_date` *within* a matching
`economic_series_id` — precisely the
`AND observation_date BETWEEN ? AND ? ORDER BY observation_date` half of
the query. Adding a second, separate index on the same two columns would
have been pure duplication: extra disk space and extra write-time
maintenance cost on every future sync, for a query the existing index
already serves. No new Alembic migration was created this increment
because no schema change was needed — the existing constraint already
implied the index this feature needed.

(Aside, not acted on: `economic_observations` also still carries the
single-column index `ix_economic_observations_economic_series_id` from
Increment 003, which is now redundant on top of the composite unique
index — a btree index on `(A, B)` already serves lookups on `A` alone
just as well as a standalone index on `A`. Removing it is a legitimate
future cleanup, but it predates this increment and wasn't requested, so
it was left alone rather than folded into an unrelated migration.)

### Database-only read semantics: 404 vs. empty result

Two different "nothing here" cases, deliberately given different
meanings:

- **The series itself was never persisted** (no `POST .../sync` has ever
  succeeded for it) → `404`. The route/service can't return "a series
  with zero observations" because there's no series row to describe —
  there's no `title`/`units` to put in the response at all.
- **The series exists, but no observation matches the date filter** (or
  the series has been synced but genuinely has no observations yet) →
  `200`, with `observations: []` and `pagination: {"total": 0, "returned": 0, ...}`.
  This is a normal, successful answer to "what do you have in this date
  range" — the honest answer is "nothing," not an error.

### Error handling — only what can actually happen on a read

The route only maps exceptions that a pure read can realistically raise:
`InvalidDateRangeError` → `400`, `SeriesNotFoundError` → `404`,
`OperationalError` (database unreachable) → `503`, and a generic
`SQLAlchemyError` fallback → `500`. `IntegrityError` — meaningful for the
`sync` endpoint's writes — was deliberately **not** given a branch here:
a `SELECT`-only code path cannot violate a unique or foreign-key
constraint, so a branch for it would be dead code asserting a failure
mode that can't occur, not real error handling.

### A small, honest signature change: `FREDClient` became optional

`EconomicDataService.__init__` previously required a `FREDClient`.
`get_observations` never touches FRED, so the new route never constructs
one — meaning the existing constructor signature would have forced either
a fake/unused client just to satisfy typing, or a second service class.
Neither was appealing, so `fred_client: FREDClient | None = None` was the
smallest honest change: the two FRED-backed methods (`get_series`,
`sync_series`) are only ever called from routes that already guarantee a
real client is present; `get_observations` never references
`self._fred_client` at all.

### Verification performed

Against the real running application and real local PostgreSQL:

- `GET /health` → `200`; `GET /api/v1/series/UNRATE` (FRED-backed) →
  `200`; `POST /api/v1/series/UNRATE/sync` → `200` — all three unchanged
  from Increment 003.
- **Proof of no FRED dependency**: `FREDClient` patched to raise on
  instantiation anywhere it could be constructed; `GET .../observations`
  still returned `200` normally — a call to FRED would have blown up the
  test, and didn't.
- Basic query (no params) → `200`, 10 observations, `pagination.total == 10`.
- `start_date` alone, `end_date` alone, and both together → each returned
  exactly the expected subset (inclusive boundaries on both ends).
- `order=asc` / `order=desc` → confirmed actual returned date ordering in
  both directions.
- `limit=3` → `returned: 3`, `total: 10` (total unaffected by limit).
- `offset=8` (10 total rows) → returned the final 2 rows, correct
  `pagination.offset`/`returned`.
- Combined filter + `limit` → `total` reflected the *filtered* count (6),
  not the unfiltered series total (10), while `returned` reflected the
  page size (3) — confirming `total` and `returned` measure different
  things, as specified.
- Nonexistent persisted series → `404`.
- Valid series with a date filter matching nothing → `200`,
  `observations: []`, `total: 0`, `returned: 0`.
- `start_date > end_date` → `400` with the fixed generic message.
- Invalid date syntax, invalid `order`, `limit=0`, `limit=-1`,
  `limit=1001`, `offset=-1` → each `422`, via FastAPI's own validation
  (no application code involved).
- Database unreachable (`DATABASE_URL` pointed at a closed port) → `503`,
  confirmed no connection string in the response or server log.
- `DATABASE_URL` unset entirely → `503`.
- Confirmed via `git status`/`grep` that no secret value appears in any
  changed file, and that `.env` itself was never read, printed, or
  otherwise displayed during this increment (only existence/ignore/
  variable-name checks and behavior through the running application).

### Deferred decisions

- **No freshness/staleness signal on the read path.** `GET .../observations`
  answers strictly "what's in our database right now" — it doesn't
  indicate how stale that is relative to FRED, or suggest a re-sync. Any
  freshness policy is explicitly a later increment's concern (per the
  project's own out-of-scope list).
- **Cursor/keyset pagination** was considered and deliberately deferred —
  see the `LIMIT`/`OFFSET` section above for the concrete tradeoff.
- **The pre-existing redundant single-column index** on
  `economic_series_id` (from Increment 003) was noticed but not removed —
  see the Indexing section above.

### Reusable engineering lessons

- "Only map the exceptions that can actually happen" is a real design
  check, not just tidiness — a read-only repository method genuinely
  cannot raise `IntegrityError`, so a handler for it in the read route
  would be asserting a false story about what can go wrong there.
  Exception handling should describe reality, not mirror a sibling
  endpoint out of habit.
- Reusing a Pydantic model via inheritance (`SeriesObservationsResponse(SeriesResponse)`)
  is a cheap, honest way to share a contract's core fields without
  duplicating field declarations — appropriate specifically because the
  new response genuinely *is* "a `SeriesResponse`, plus pagination," not
  a coincidentally similar but conceptually different shape.
- The strongest proof that a code path "doesn't call an external service"
  isn't reading the code and confirming no import is used at runtime — it's
  making that external service explode if touched, and watching the
  request still succeed. Static inspection can miss an indirect call
  through a shared helper; the exploding-mock approach can't.
- Before adding an index, check what already exists and why — a unique
  constraint already *is* an index in PostgreSQL, and the columns/order
  that make it useful for uniqueness (leading column first) are often
  exactly the columns/order a corresponding query needs too.

---

## Increment 005 — Economic Transformation Engine

**Objective:** compute deterministic derived series — `absolute_change`,
`percent_change`, `moving_average` — over the historical observations
Increment 004 made queryable, via a new
`GET /api/v1/series/{series_id}/transform` endpoint. Explicitly not in
scope: any transformation more sophisticated than these three (YoY,
CAGR, volatility, z-scores, interpolation), persisting the derived
values, or paginating the transformed output.

### Why transformation follows persistence and querying, in that order

Each increment so far has depended on the previous one actually working:
Increment 003 had nothing to query without Increment 002's normalized
data; Increment 004 had nothing to read without Increment 003's
persistence. Transformation has the same dependency — a derived value is
only as meaningful as the raw values it's derived from, and those raw
values had to be reliably gettable (Increment 004) before it was worth
building anything that computes over them. This increment adds no new
data; it adds a new way of *looking at* data that already exists.

### Raw data vs. derived data — and why derived data is never stored

`economic_observations` holds what FRED actually reported — call it raw,
source-of-truth data. `absolute_change`, `percent_change`, and
`moving_average` results are *derived*: fully and deterministically
reproducible from the raw observations plus a transformation name (and a
window, for moving averages). Nothing about a derived value carries
information the raw data didn't already contain.

That reproducibility is exactly why nothing is persisted here — no
`economic_transformed_observations` table, no derived-value cache. Storing
a value that can be recomputed exactly from data already on hand buys
nothing but costs real things: an invalidation question (when a
`sync` updates the raw data, does the stored derived value silently go
stale?), a versioning question (if the transformation logic itself
changes, are old derived rows wrong now?), and duplicate storage for no
informational gain. Recomputing on every request is cheap at this data
volume and sidesteps all three problems entirely — this project doesn't
need that optimization yet, and won't build for it before it's needed.

### Pure functions, and why purity is enforced structurally, not by convention

`app/domain/transformations.py` holds `absolute_change`, `percent_change`,
and `moving_average` — three functions that take a list of observations
(plus, for moving averages, a window size) and return a list of results,
with **no import of FastAPI, SQLAlchemy, `httpx`/FRED, `os.environ`, or
logging**, and no mutation of anything outside the function call. Given
the same input, they always produce the same output — verified directly
(see Verification below) by calling each function twice on identical
input and asserting byte-identical results.

This isn't just a style preference. A function with no I/O and no hidden
state is trivially testable without a database, a running server, or
mocked HTTP calls — the entire pure-function test suite for this
increment runs in well under a second, no PostgreSQL connection needed.
Keeping this module in its own package (`app/domain/`, distinct from
`app/services/`, which *does* coordinate I/O) makes "this code has no side
effects" a structural fact checkable by `grep`, not a claim that has to be
trusted.

### `absolute_change`: percentage-point change, not percent change

```
change[t] = value[t] - value[t-1]
```

For a *percentage-valued* series like `UNRATE` (values are already a
percent, e.g. `4.1`), `absolute_change` produces a change measured in
**percentage points** (4.1 → 4.3 is "+0.2 percentage points"), which is a
genuinely different quantity from a *percent change* (a 4.9% relative
increase). Conflating the two is a classic, easy-to-make error in
economic data work — an unemployment rate moving from 4.0 to 4.2 is "up
0.2 points," not "up 5%," even though `percent_change` of the same two
numbers *is* 5%. This project deliberately exposes both, under distinct
names, so a caller has to choose the one they actually mean rather than
one function silently being asked to answer both questions.

The first observation in any requested range has no predecessor and is
always `null` — not zero, not skipped. A `null` current or previous
*source* value also produces a `null` result; the function never looks
further back to find an earlier non-null value to substitute.

### `percent_change`: the formula, and why division by zero never happens

```
((current - previous) / previous) * 100
```

Same first-observation and missing-value alignment as `absolute_change`,
plus one more explicit rule: when the previous value is exactly `0`, the
result is `null` — never a `ZeroDivisionError`, never `inf`/`-inf`, never
a substituted `0`. This is checked *before* the division is attempted
(`previous_value == 0`), not caught after the fact, so there's no reliance
on exception handling to paper over what is really a "this transformation
isn't meaningful here" case, distinct from "an actual bug occurred."

### `moving_average`: simple moving average, and its window semantics

A plain, equally-weighted average of the trailing `window` values ending
at each point. A result is `null` until at least `window` observations
have been seen (so the first `window - 1` results in any given input list
are `null` by construction — not a special case, just what "not enough
history yet" means positionally), and `null` for any window that contains
even one `null` source value — never silently computed from just the
non-null values in that window, which would quietly change what the
average actually represents. `window` is bounded to `[2, 365]`
(`2` because a 1-point "moving average" isn't averaging anything; `365`
as a generous but finite upper bound rather than an unbounded integer).

### Chronological order is guaranteed by the service, not assumed by the engine

Every transformation function's docstring states its precondition
plainly: `observations` must already be in ascending chronological order.
The functions themselves do not sort — sorting is the *service's* job
(`EconomicDataService.get_transformed_observations`), which always
requests data from the repository in ascending order before handing it to
the transformation engine. This split matters: a pure function that
silently re-sorted its input would be hiding a correctness dependency
(what if the caller's "chronological" assumption were ever wrong?) instead
of surfacing it. Keeping the ordering *requirement* explicit and the
ordering *guarantee* in one clearly-responsible place (the service) is
more honest than either assuming order everywhere or re-sorting
defensively everywhere.

### The boundary-context problem, and how it's solved without turning the repository into a transformation engine

This was the increment's real design problem. Given persisted data:

```
Jan  100
Feb  105
Mar  110
```

a request for `percent_change` with `start_date=Feb` should return Feb's
change computed against Jan (`5.0`), **not** `null` just because Jan falls
outside the requested output range. The caller asked for observations
*starting* Feb — they didn't ask for the calculation to pretend history
before Feb doesn't exist.

The fix keeps each layer's existing responsibility intact rather than
inventing a new one:

1. **Repository** (`get_preceding_observations`): a small, honest,
   database-specific capability — "give me the `N` observations for this
   series immediately before this date, ascending" — with no idea it's
   feeding a transformation. This is exactly the kind of "database-specific
   retrieval" the repository was already responsible for; it isn't a new
   category of responsibility, just a new query shape.
2. **Service** (`get_transformed_observations`): decides *how much*
   context is needed (`1` for the change transformations — only the
   immediately preceding point matters; `window - 1` for a moving
   average) and requests it only when `start_date` actually truncates the
   series' history. It concatenates `context + requested` into one
   continuous ascending list, hands the *whole* thing to the transformation
   engine, and afterward slices off exactly `len(context)` leading results
   before building the response.
3. **Transformation engine**: never told about "context" at all. It just
   processes a continuous list positionally — the same function, the same
   logic, whether the list happens to include borrowed leading history or
   not. This is what "without turning the repository into a transformation
   engine" (and without teaching the engine about request boundaries)
   actually means in code: neither layer had to learn a new concept to
   solve this — the service is the one place that already knows both "what
   the caller asked for" and "what the math needs," so it's the natural
   (and only) place to reconcile the two.

The same mechanism handles "insufficient history exists" for free: if
fewer than the needed context observations exist before `start_date`,
`get_preceding_observations` just returns however many *do* exist (its
`LIMIT` is a maximum, not a requirement), and the transformation engine's
own "not enough points yet" logic (`index + 1 < window`, or `index == 0`)
produces the correct `null`s from wherever the combined list actually
starts — no special-casing needed anywhere for a short or missing history.

### Why the transform endpoint is not paginated

`limit`/`offset` were deliberately left off this endpoint, even though
the sibling `.../observations` endpoint has them. The reason is the same
boundary-context problem, one level up: if page 2 of a `percent_change`
result started at some arbitrary offset, computing its first value
correctly would require the *last* raw observation from page 1 — meaning
pagination on *derived* data can't be implemented by simply paginating the
underlying query the way it can for raw, context-free rows. Solving that
properly (consistent derived-data pagination with correct boundaries) is
a real design problem of its own, deliberately deferred rather than
solved partially or incorrectly under this increment's scope. For now,
`transform` always returns its full requested range in one response.

### Numerical behavior: no rounding, no `Decimal`

Transformed values are plain Python `float` arithmetic — no rounding was
introduced, and `Decimal` was not adopted. This matches the existing data
model exactly: `economic_observations.value` is already `double precision`
(`float` in Python), established back in Increment 003 — using `Decimal`
here would mean converting at the boundary for no benefit yet, since the
source data was never exact-decimal to begin with. Floating-point noise
(e.g. `-0.10000000000000053` instead of an exact `-0.1`) is visible in
real responses and is expected, ordinary `float` behavior, not a bug. If
a future increment introduces something genuinely precision-sensitive
(e.g. a financial calculation where exact decimal arithmetic matters),
that's the point to revisit `Decimal` deliberately — not here, and not as
an unrequested "improvement" bolted onto this increment.

### Architecture boundaries, restated for this increment

```
Route            (app/api/series.py)        HTTP/query boundary, primitive
                                             validation via FastAPI, exception
                                             -> status mapping
Service          (economic_data.py)         cross-field validation (date range,
                                             window applicability), boundary-
                                             context orchestration, calls the
                                             transformation engine
Repository       (series_repository.py)     database-specific retrieval only
                                             (full range, preceding context)
Transformation   (domain/transformations.py) pure math only
```

No SQL in the route or the transformation engine; no math in the route,
repository, or a SQL query; no HTTP/FastAPI concept anywhere below the
route. Each boundary from prior increments held without needing to bend.

### Verification performed

Against both isolated pure-function tests and the real running
application/database:

- **Pure-function correctness**: every example in this increment's spec
  reproduced exactly — `4.0, 4.2, 4.1` → `null, 0.2, -0.1`;
  `100, 105` → `null, 5.0`; a zero previous value → `null`;
  `10, 20, 30, 40` with `window=3` → `null, null, 20, 30`; a
  shorter-than-window dataset → all `null`; a `null` inside a moving-average
  window → `null` for every window it touches.
- **Determinism**: each function called twice on identical input,
  results compared field-by-field, confirmed identical.
- **API integration**: all three transformations exercised through the
  real endpoint against real persisted `UNRATE` data — correct shapes,
  correct first-`null` behavior, correct floating-point results.
- **Boundary context, proven by exact-value comparison** (not just "it
  didn't crash"): the unfiltered `percent_change`/`moving_average`
  response was computed first, then re-requested with a `start_date` that
  should require preceding context — the value at the boundary date
  matched the unfiltered computation byte-for-byte, and the
  context-only dates (before `start_date`) were confirmed absent from the
  response.
- **No FRED dependency**: `FREDClient` patched to raise on instantiation;
  all three transformation types still returned `200` normally.
- **No PostgreSQL mutation**: `economic_series`/`economic_observations`
  row counts, and the series' `updated_at` timestamp, compared before and
  after several transform requests — byte-identical; nothing changed.
- **Validation/error behavior**: nonexistent series → `404`;
  `start_date > end_date` → `400`; invalid `transformation` value → `422`
  (FastAPI's own `Literal` validation); `moving_average` without `window`
  → `400` (cross-field, service-level); `window` outside `[2, 365]` → `422`
  (FastAPI's own bounds validation); `window` supplied to
  `absolute_change`/`percent_change` → `400` (cross-field, service-level).
- **Database failures**: unreachable `DATABASE_URL` → `503`, no
  connection string in the response or server log; a mocked generic
  `SQLAlchemyError` → `500`, generic message only.
- Confirmed via `grep`/`git status` that no secret value appears in any
  changed file, and `.env` was never read or displayed at any point in
  this increment — only existence/ignore/variable-name checks and
  behavior through the running application were used.
- Confirmed no new Alembic migration was created and no new dependency
  was added, by inspecting `alembic/versions/` and `git diff pyproject.toml`.

### Deferred decisions

- **Transformation-aware pagination** — explicitly deferred; see "Why the
  transform endpoint is not paginated" above.
- **`Decimal`/exact-precision arithmetic** — deferred until a genuinely
  precision-sensitive calculation actually requires it.
- **A registry/dispatch table for transformation names** — the route and
  service currently branch on `transformation` with plain `if`/`elif`
  (three cases). A dict-based dispatch (`{"absolute_change": absolute_change, ...}`)
  would look "cleaner" but is unnecessary machinery for three fixed,
  known cases — worth reconsidering only if the number of transformations
  grows enough that repeated `if`/`elif` blocks become a real readability
  problem, not preemptively.

### Reusable engineering lessons

- "Pure" is easiest to keep honest when it's enforced by *what a module is
  allowed to import*, not just by what its functions happen to do today —
  a dedicated package with a stated, checkable import restriction (no
  FastAPI/SQLAlchemy/FRED) is harder to accidentally violate later than an
  unenforced convention.
- A "boundary context" problem (needing data outside a requested range to
  correctly compute values *inside* it) doesn't require inventing a new
  architectural layer — it's usually solvable by having the layer that
  already knows both "what was requested" and "what the computation needs"
  (here, the service) fetch a little extra, compute over the extended set,
  and trim before returning. The temptation to push this into the
  repository (which would need to learn about transformations) or the
  transformation engine (which would need to learn about requests) is
  worth resisting.
- The clearest proof that a boundary calculation is correct isn't
  "it returned a non-null value" — it's comparing the filtered result
  against the equivalent slice of an unfiltered computation and confirming
  they match exactly. A boundary bug can easily produce *a* number without
  producing the *right* number.
- When a domain has two similarly-named but semantically different
  quantities (percentage-point change vs. percent change), exposing both
  under clearly distinct names is safer than trying to guess which one a
  caller "really" wants, or worse, only implementing one and letting
  people misuse it for the other.

---

## Increment 006 — Multi-Series Analysis

**Objective:** compare two persisted series against each other —
exact-date alignment, spread, and Pearson correlation — via a new
`GET /api/v1/analysis/compare` endpoint. Explicitly not in scope:
comparing *transformed* series (e.g. correlating two percent-change
series), lagged/lead correlation, regression, or persisting any analysis
result.

### Why multi-series analysis follows transformations

Increment 005 established that this project can compute derived values
over *one* series' history without touching FRED or the database beyond
reading it. Multi-series analysis is the natural next question — not "how
has this series changed over time" but "how do these two series relate to
each other" — and it only became answerable once two independent series
could reliably be fetched, filtered, and handed to pure computation, which
is exactly the machinery Increment 005 built. The prompt's explicit
"no transformation composition yet" boundary matters here: correlating
`percent_change(UNRATE)` against `percent_change(CPIAUCSL)` is a real,
likely-useful future question, but it's a *composition* of two increments'
capabilities, deliberately deferred until plain multi-series semantics
(this increment) are stable and proven correct on their own.

### Exact-date inner alignment, and why array-position alignment would be wrong

Given two persisted series with different observation dates:

```
Series A: Jan -> 10, Feb -> 20, Mar -> 30
Series B: Jan -> 100, Mar -> 120, Apr -> 130
```

the only defensible way to pair these up is by matching *dates*: Jan
pairs with Jan (`10`/`100`), Mar pairs with Mar (`30`/`120`); Feb and Apr
have no counterpart and are excluded. `align_series` builds this via two
`{date: value}` dictionaries and a set intersection of their keys — there
is no `zip()`, no `enumerate()` walking both lists by position anywhere
in the implementation.

Pairing by array position (`A[0]` with `B[0]`, `A[1]` with `B[1]`, …)
would have quietly paired Jan with Jan by coincidence here, but Feb (A's
2nd point) with Mar (B's 2nd point) — two different calendar months,
silently treated as simultaneous. Two persisted series essentially never
share an identical set of observation dates in general (a provider can
revise its publication calendar, a sync can happen at different times,
one series can simply report more or less often) — array-position
alignment isn't a rare edge case away from being wrong, it's wrong by
default the moment the two series' date sets diverge at all, and it fails
*silently*: a positionally-misaligned pair still looks like a normal
`{date, value_a, value_b}` object, with nothing about its shape hinting
that `value_a` and `value_b` don't actually describe the same point in
time.

### Matching pairs vs. usable pairs

Two different counts, both reported in the response, because they answer
different questions:

- **`matching_pairs`** — how many *dates* exist in both series, regardless
  of whether either series' value for that date is itself missing. This
  is `len(aligned)`.
- **`usable_pairs`** — of those matched dates, how many have a genuine
  numeric value on *both* sides. This is the population `spread`'s
  non-null results and `pearson_correlation` actually operate over.

The distinction matters because a matched date is not automatically a
usable one: a date can exist in both `economic_observations` tables while
one series' value for it is `NULL` (a FRED-reported missing observation,
carried through unchanged since Increment 002). Reporting only one count
would hide either "how much overlap exists" or "how much of that overlap
is actually numeric" — a caller needs both to interpret `correlation` or
a `spread` sensibly (e.g. "10 matching dates but only 6 usable" is a
different, worse signal than "10 matching, 10 usable").

### Missing-value semantics: never substituted

An exact date match does not guarantee both series reported a value —
`align_series` still returns the pair (so the caller can see the dates
matched at all), but leaves `value_a`/`value_b` as `None` when the source
was `None`. Every downstream calculation respects this without
exception: `calculate_spread` returns `None` for that date rather than
treating a missing side as `0`; `pearson_correlation` excludes that pair
from its population entirely rather than substituting anything. Nothing
in this increment forward-fills, backward-fills, interpolates, or infers
a value that was never actually observed — the same discipline
established for single-series transformations in Increment 005, now
applied across two series at once.

### Spread: a simple subtraction, with a real interpretive limitation

```
spread = value_a - value_b   (per matched date; null if either side is null)
```

`calculate_spread` performs no unit reconciliation — it will happily
compute `UNRATE (Percent) - CPIAUCSL (Index 1982-1984=100)`, a spread
between a percentage and an index number, which is *arithmetically*
well-defined but not obviously *economically* meaningful (a spread is
most naturally interpreted when both sides share units, e.g. two interest
rates, or the same index rebased differently). This project deliberately
does not attempt to detect or block unit-incompatible spreads in this
increment — doing that correctly would require a real dimensional-
analysis or unit-compatibility model, which is exactly the kind of
premature, speculative machinery the project's engineering rules ask to
avoid building before there's a demonstrated need for it. The response
includes each series' actual `units` (via `SeriesSummary`) precisely so a
caller can make that judgment themselves rather than the API silently
making it for them.

### Pearson correlation: formula, range, and what it does and doesn't claim

```
r = covariance(X, Y) / sqrt(variance(X) * variance(Y))
```

computed directly with the standard deviation-from-mean formula (no
external library — see below), over exactly the *usable* pairs (both
values non-null). `r` is always in `[-1, 1]`: `+1` means a perfect
positive linear relationship between the two series over the compared
observations, `-1` a perfect negative linear one, `0` no linear
relationship. **This project's API and documentation never describe a
correlation result as evidence of causation** — a high correlation
between two economic series says nothing here about which one, if
either, drives the other, and this codebase makes no attempt to claim
otherwise.

### Insufficient-data and zero-variance behavior — undefined, not an error

Two situations where Pearson correlation is *mathematically* undefined,
both handled the same deliberate way — return `None`, respond `200`, and
never raise:

- **Fewer than 2 usable pairs.** Correlation describes a relationship
  between two *sets* of paired values; one pair (or zero) has no
  relationship to describe.
- **Either usable series has zero variance** (every usable value on one
  side is identical). The correlation formula divides by
  `sqrt(variance_x * variance_y)`; a constant series has zero variance,
  and dividing by zero is exactly what `pearson_correlation` checks for
  and refuses to do, returning `None` instead of raising
  `ZeroDivisionError`, returning `NaN`, or returning `inf`.

Both are checked explicitly, before the division is attempted — not
caught as exceptions after the fact — which keeps "this comparison has no
defined correlation" clearly distinct from "something actually went
wrong." A microscopic floating-point overshoot outside `[-1, 1]` from the
formula's arithmetic (which can happen with values very close to a
perfect ±1 relationship) is clamped back into range — the *true*
mathematical correlation coefficient can never leave `[-1, 1]`, so an
overshoot is understood as float noise, not a different real answer.

### Date filtering applies before alignment, and needs no boundary context

`start_date`/`end_date` are applied independently to each series' raw
observation query (`SeriesRepository.get_observations_in_range`, reused
unchanged from Increment 005) *before* `align_series` ever runs — a
requested range narrows what's available to match, not what's already
been matched. Unlike Increment 005's transformations, none of these three
analyses need data from *outside* the requested range to compute a
correct value at the boundary: alignment, spread, and correlation all
operate purely on the pairs that exist within whatever range was
requested, with no notion of "the point before this one." The
boundary-context machinery Increment 005 built for exactly that problem
simply doesn't apply here, and wasn't reused or reinvented for a problem
this increment doesn't have.

### Why this endpoint isn't paginated

Same underlying concern as Increment 005's transformation endpoint, one
level up: correlation is computed over a *population* (all usable pairs
in the requested range), and slicing that population into pages would
change what's actually being measured at each page boundary — a
correlation computed over "page 2's pairs alone" answers a different,
arguably meaningless question compared to the correlation over the whole
requested range. Date filtering (already supported) is the intended way
to narrow what's being compared; `limit`/`offset` pagination is not
offered here, on purpose.

### Pure domain analysis: `app/domain/analysis.py`

Four functions — `align_series`, `calculate_spread`,
`count_usable_pairs`, `pearson_correlation` — with the same purity
discipline as `app/domain/transformations.py`: no FastAPI, SQLAlchemy,
FRED/httpx, environment-variable, or logging imports anywhere in the
module (confirmed directly by inspecting its import list), no mutation of
anything outside a function call, deterministic output for identical
input. `pearson_correlation` calls `count_usable_pairs` internally rather
than recomputing "both values non-null" inline a second time — the
definition of a usable pair exists in exactly one place.

No strategy classes, no registry, no NumPy/pandas/SciPy — the Pearson
formula is a handful of `sum()`/`sqrt()`-equivalent expressions over
plain Python floats, well within what the standard library already
provides.

### Service and repository responsibilities

**No repository changes were needed.** `SeriesRepository.get_series_by_series_id`
and `get_observations_in_range` — both already built for single-series
use in Increments 004/005 — are exactly what two-series comparison needs;
`AnalysisService.compare` simply calls each one twice (once per series).
This is treated as a genuine design outcome worth recording, not an
oversight: the repository's existing responsibilities ("look up a
persisted series," "retrieve its chronological observations, optionally
date-filtered") were already series-agnostic enough that "two series"
needed no new capability, only two calls.

A new `AnalysisService` (`app/services/analysis.py`), not a method added
to `EconomicDataService`, coordinates the two lookups, calls
`align_series`, and dispatches to `calculate_spread`/`pearson_correlation`
depending on the requested `analysis`. `EconomicDataService` is
documented and structured around single-series concerns spanning FRED and
persistence (`get_series`, `sync_series`, `get_observations`,
`get_transformed_observations`) — none of which multi-series comparison
needs or extends. Forcing a `compare(series_a, series_b, ...)` method onto
a class named for *one* series' data would have made its own name and
docstring inaccurate, which is exactly the "responsibility becoming
incoherent" case worth a new, small class instead. `AnalysisService` has
no `FREDClient` at all — not even an optional one — because multi-series
analysis genuinely never touches FRED, unlike `EconomicDataService`'s
`get_observations`/`get_transformed_observations`, which still carry an
unused-but-present optional client for constructor-shape consistency with
their FRED-backed siblings.

`SeriesNotFoundError` and `InvalidDateRangeError` are imported from
`app.services.economic_data` rather than redefined in the new service —
they mean the same thing in both places, and two same-named-but-distinct
exception classes would have made `except SeriesNotFoundError` in a route
silently depend on which module it was imported from.

### A new nested-metadata model: `SeriesSummary`

`series_id`/`title`/`units`/`source` had already been reused twice by
inheritance (`SeriesObservationsResponse(SeriesResponse)` in Increment
004) — but this response needs that same quartet to appear as a *nested*
object (`series_a`/`series_b`), which inheritance can't produce (a
subclass's fields flatten into it, they don't nest as a sub-object).
`SeriesSummary` is the smallest change that made this reusable both ways
without touching `SeriesResponse`'s existing, already-relied-upon shape.

### Verification performed

Against both isolated pure-function tests and the real running
application/database (a second real series, `CPIAUCSL`, was synced
through the existing `POST /sync` endpoint purely to have two persisted
series to compare — no test-only application code was added for this):

- **Pure-function correctness**: every example in this increment's spec
  reproduced exactly — exact-date alignment on the spec's own
  Jan/Feb/Mar vs. Jan/Mar/Apr example; chronological output regardless of
  input order; null values preserved through alignment; `10 - 7 = 3` for
  spread; null propagation for spread; same-series spread of exactly `0`;
  perfectly increasing/perfectly inverse series producing correlations of
  exactly `+1.0`/`-1.0`; fewer-than-2-usable-pairs and zero-variance both
  producing `None`; a mixed dataset's `matching_pairs`/`usable_pairs`
  counted correctly (4 matched, 2 usable) with missing values properly
  excluded from the usable count; a series correlated against itself
  producing `1.0`.
- **API integration**: all three analyses exercised through the real
  endpoint against real persisted `UNRATE`/`CPIAUCSL` data (10 fully
  overlapping dates) — correct aligned pairs, correct spreads, a real
  (non-trivial, negative) correlation coefficient.
- **Date filtering**: `start_date`, `end_date`, and a combined range each
  correctly narrowed the compared dates before alignment.
- **Zero matching dates**: a date range outside both series' persisted
  history correctly returned `200` with `matching_pairs: 0`,
  `usable_pairs: 0`, `observations: []`, and `correlation: null` for all
  three analysis types.
- **Same-series comparison**: `UNRATE` vs. `UNRATE` correctly allowed
  (not rejected) — spread `0.0` for every pair, correlation exactly `1.0`.
- **No FRED dependency**: `FREDClient` patched to raise on instantiation;
  all three analysis types still returned `200` normally.
- **No PostgreSQL mutation**: `economic_series`/`economic_observations`
  row counts compared before and after several analysis requests —
  identical.
- **Validation/error behavior**: `start_date > end_date` → `400`; an
  invalid `analysis` value → `422` (FastAPI's `Literal` validation);
  missing `series_a`/`series_b` → `422` (FastAPI's own required-query-
  parameter validation); a nonexistent `series_a` or `series_b` → `404`,
  each correctly naming the specific missing series in its message.
- **Database failures**: unreachable `DATABASE_URL` → `503`, no
  connection string leaked; a mocked generic `SQLAlchemyError` → `500`.
- Confirmed via `git status`/`grep` that no secret value appears in any
  changed file, and `.env` was never read or displayed at any point in
  this increment.
- Confirmed no repository changes, no new Alembic migration, and no new
  dependency, by inspecting `git status`/`git diff` directly.

### Deferred decisions

- **Transformation composition** (correlating derived series, e.g.
  percent-change-vs-percent-change) — explicitly out of scope, per the
  reasoning in "Why multi-series analysis follows transformations" above.
- **Unit-compatibility checking for spread** — no dimensional-analysis or
  unit-reconciliation logic; deferred until a real need for it is
  demonstrated (see the Spread section above).
- **Pagination for large aligned/spread result sets** — deferred for the
  same population-integrity reason correlation isn't paginated; not a
  concern at this project's current data volumes.
- **Lagged/lead correlation, regression, covariance as its own metric** —
  all named explicitly out of scope; each would be a genuinely new
  analysis type, not a variation of the three implemented here.

### Reusable engineering lessons

- Joining two time series is a join, not a zip — the same relational
  instinct that already justified PostgreSQL over array-position data
  structures back in Increment 003 (ADR-006) applies again here at the
  domain-logic level: match by key (date), never by position, the moment
  two ordered collections might not be in lockstep.
- A count without a companion count can hide the more important half of
  a "how much data do I actually have" question — `matching_pairs` alone
  would have let a caller believe 10 dates lined up meaningfully, when
  only, say, 6 of them had two real numbers to compare.
- "Mathematically undefined" and "a server error" are not the same
  category, and conflating them (crashing, or returning a sentinel like
  `0` for correlation) actively lies to the caller about what happened.
  Checking explicitly for the undefined cases and returning `null` keeps
  "the calculation ran and correctly found no defined answer" honestly
  distinct from "the calculation failed."
- Before adding a repository method for a new use case, check whether an
  existing one, called an extra time, already covers it — the instinct to
  add `AnalysisRepository`-shaped new methods was worth resisting here;
  the two methods Increment 004/005 already built were series-agnostic
  enough to need nothing new.

---

## Increment 007 — Composable Analysis Pipeline

**Objective:** prove that the capabilities built across Increments
004–006 — persisted retrieval, single-series transformation, and
multi-series analysis — actually *compose*, by adding a structured
endpoint, `POST /api/v1/analysis/pipeline`, that lets a caller optionally
transform each side of a two-series comparison before it's aligned and
analyzed. No new mathematics, no new statistics, no AI — this increment
is entirely about correct composition of what already exists.

### Why composition follows the primitives, not more math

Increments 005 and 006 each ended with an explicit, named boundary:
Increment 005 (`ADR-010`) never lets its transformation engine touch
another series; Increment 006's journal names "transformation
composition" as future work, deliberately deferred until "plain
multi-series semantics are stable and proven correct on their own." This
increment is that deferred work, now that both primitives it depends on
have shipped, been verified independently, and been documented. Building
a pipeline before either primitive existed would have meant guessing at
an interface neither one had proven yet; building it now means wiring
together two things already known to work correctly on their own — the
actual engineering question this increment answers is narrower and more
concrete than "add more analytical power": it's "do these two already-
correct pieces still produce correct answers when chained."

### A structured request, not more query parameters

`GET /api/v1/analysis/compare` (Increment 006) already has five query
parameters; adding "and optionally transform each side, with its own
type and window" to that as more `?series_a_transformation=...&series_a_window=...`
query parameters would have made an already-parameter-heavy `GET`
request meaningfully harder to read and validate. A JSON request body —
`POST /api/v1/analysis/pipeline` — lets each side's specification
(`series_id` + optional `transformation`) nest naturally, and lets
Pydantic validate the whole structure (including per-side `window`
bounds) the same way it already validates every other request body in
this project.

### Why `POST` for a read-only computation

`POST` here means "execute this structured analysis specification,"
never "create a resource." Nothing is written to PostgreSQL by this
endpoint (verified directly — see Verification below) — `POST` is simply
the correct HTTP method for a request that carries a non-trivial
structured body the client is submitting for processing, which `GET`
(no standard body) can't express cleanly. This is a deliberate, narrow
use of `POST` for its request-shape properties, not a signal that the
endpoint mutates anything; its docstring and this journal both say so
explicitly, and the verification suite proves it rather than just
asserting it.

### Order of operations, and why it's a correctness requirement, not a style preference

The pipeline executes, in this exact order:

```
1. validate the whole request (date range, each side's transformation) -- no DB access yet
2. load both persisted series' metadata
3-6. per series, independently: retrieve requested range -> retrieve
     preceding context (if start_date given) -> transform -> trim context back out
7. exact-date align the two FINAL (possibly transformed) series
8. perform the requested analysis (aligned/spread/correlation)
9. build the response
```

Two orderings would have been *actively wrong*, not just less elegant:

- **Filtering the output range before transforming.** If a `start_date`
  filter were applied before a transformation ran, the transformation
  would never see the immediately preceding persisted observation it
  needs — exactly the bug this project has guarded against since
  Increment 005's boundary-context work. Filter-then-transform silently
  produces `null` (or a wrong value) for the first requested point of any
  transformed series whenever `start_date` is set, with no error to
  signal it.
- **Aligning before transforming.** `align_series` only sees two series'
  *final* values — if it ran on raw values and the transformation ran
  afterward independently on each already-aligned side, a transformation
  like `moving_average` would be computing its window from a date-
  intersected (and therefore potentially gappy) series instead of the
  real, complete persisted history, changing what "the preceding N-1
  points" even means.

Transforming before aligning, with context fetched before transforming
and trimmed before aligning, is the only ordering that lets each series'
transformation see its own real, undisturbed history while still
guaranteeing the final Pearson/spread/aligned-pairs math operates on
values that actually correspond to the same calendar dates.

### Retrieving context before transforming (again), now on both sides independently

The context-retrieval mechanics are unchanged from Increment 005:
`SeriesRepository.get_observations_in_range` for the requested range,
`get_preceding_observations` for up to 1 (`absolute_change`/
`percent_change`) or `window - 1` (`moving_average`) immediately
preceding persisted points when `start_date` narrows the range. This
increment calls those same two repository methods per series, once for
`series_a` and once (independently) for `series_b` — there is no
interaction between the two sides until step 7, so nothing about running
this per-series step twice (rather than "batching" both series' retrieval
before either one's transform runs) changes the result: the two sides
never share state before alignment, so per-series sequencing and
per-step-batched sequencing are equivalent here.

One deliberate implementation choice worth naming plainly: the
retrieve-context-transform-trim sequence is *re-expressed* inside
`AnalysisService._resolve_observations` rather than extracted into a
function shared with `EconomicDataService.get_transformed_observations`,
which contains the same shape of logic for the single-series transform
endpoint. Sharing it would have meant either introducing cross-service
coupling (one service calling into the other) or a new standalone
utility module outside either service — both a larger architectural
change than this increment's scope, and each carries a real risk of
touching Increment 005's already-working, already-verified code for
stylistic reasons alone (explicitly discouraged for this increment). The
modest duplication (roughly fifteen lines of orchestration, not math) was
judged the smaller cost; see Deferred decisions below.

### Raw + transformed composition

Each side is independently raw (no `transformation` in its
`PipelineSeriesSpec`) or transformed (one of the three Increment
005 types). All five combinations named in the spec were verified
directly against real persisted data: raw+raw reproduces Increment 006's
`/compare` endpoint's own results exactly (confirmed by comparing the
same correlation coefficient from both endpoints); percent_change+raw,
raw+moving_average, percent_change+absolute_change, and
moving_average+moving_average(different windows) all produce the
expected values, verified by hand-checking specific numbers (e.g. a
3-point moving average computed from the exact three persisted values it
should average).

### What the analysis engine actually receives: the final value, nothing about how it got there

When `series_a` specifies `percent_change`, `align_series`,
`calculate_spread`, and `pearson_correlation` all receive plain
`Observation(date, value)` objects where `value` *is* the percent-change
result — not the original persisted value, and not a `TransformedObservation`
carrying both. `app/domain/analysis.py` was not modified at all for this
increment (confirmed via `git status`): it has no idea a transformation
happened, because from its perspective nothing did — it's still just
given two lists of dated numbers, exactly the contract it had before this
increment existed. The original/source value survives only in the
response's per-side `transformation` metadata (which transformation, if
any, and its window) — never inside the aligned/spread `observations`,
which show only the final, already-transformed number the analysis
actually operated on.

### Exact-date alignment, unchanged

`align_series` (Increment 006, [ADR-011](adr/011-exact-date-alignment.md))
runs after both sides' transformation and trimming, over whatever dates
the final series happen to have. Two transformed series can easily have
*fewer* common dates than their raw counterparts (e.g. a `moving_average`
side's first `window - 1` points are `null` rather than absent — they're
still present as dates, so this specifically doesn't shrink the aligned
set; but two series of genuinely different lengths after transformation
still align by whatever dates both actually contain) — this is normal,
expected behavior, not a special case the pipeline needs to handle:
`align_series` was written to do exactly the right thing regardless of
*why* two date sets differ.

### Missing-value semantics: unchanged, on purpose

Nothing in the pipeline reinterprets what `null` means at either the
transformation layer or the alignment/analysis layer. A transformation's
own missing-value rules (Increment 005: no predecessor, a missing source
value, division by zero, or insufficient window history all produce
`null`) apply exactly as before, now simply feeding into `align_series`,
which applies its own unchanged rule (a matched date's value may still be
`null`; `usable_pairs`/`pearson_correlation` exclude it, never
substitute). The pipeline orchestrates two already-correct policies in
sequence; it does not add a third one on top.

### Why no pagination, no persistence, no FRED, no frequency handling

All four are direct, narrower restatements of principles already
established:

- **No pagination** — same reasoning as Increments 005/006: a
  correlation or aligned-pair count describes a population, and slicing
  that population into pages would change what's being measured at each
  boundary. The pipeline's combination of two independently-transformed
  series makes this *more* true, not less — there's no sensible way to
  define "page 2" of a two-series, two-transformation comparison.
- **No persistence** — the pipeline's result is exactly as reproducible
  from persisted raw data plus a request body as any single-series
  transformation or comparison; the reasoning in
  [ADR-010](adr/010-pure-transformation-engine.md) applies unchanged.
- **No FRED** — the pipeline operates exclusively on data `POST .../sync`
  already put in PostgreSQL; a nonexistent persisted series is a `404`,
  never an automatic sync attempt. Verified directly (see below).
- **No frequency handling** — comparing a monthly and a quarterly series
  (or any two series with different native reporting frequencies) after
  transformation still requires an *exact* date match; no resampling,
  interpolation, or period-label matching (e.g. treating "Q1 2025" and
  "2025-01-01" as equivalent) was introduced. This is the same boundary
  [ADR-011](adr/011-exact-date-alignment.md) already drew, restated here
  because it would have been easy to quietly cross it while composing
  transformations with alignment.

### Service orchestration vs. domain computation

Zero changes to either pure domain module
(`app/domain/transformations.py`, `app/domain/analysis.py`) were needed
or made — confirmed directly via `git status`. `AnalysisService.pipeline`
imports and calls the exact same six pure functions
(`absolute_change`, `percent_change`, `moving_average`, `align_series`,
`calculate_spread`/`pearson_correlation`/`count_usable_pairs`) that
already existed; the entire new code is orchestration — deciding *when*
to call each one and *how* to assemble their outputs into a response —
never a re-implementation of *what* any of them compute. This is the
clearest structural proof that Increments 005 and 006's math needed no
changes to be composed: if the pipeline had required editing either
domain module, that would have been a sign the original design was not
actually reusable, not just an inconvenience.

### Verification performed

Against both targeted correctness checks and the real running
application/database (`UNRATE`/`CPIAUCSL`, the same two series persisted
since Increment 006):

- **Regression**: `/health`, the FRED-backed `GET`, `POST /sync`, the
  single-series observations and transform endpoints, and Increment 006's
  `GET /compare` all confirmed unchanged and working.
- **Raw+raw**: `aligned`/`spread`/`correlation` through the pipeline
  reproduce Increment 006's `/compare` endpoint's results exactly for the
  same inputs — the same correlation coefficient came back from both
  endpoints, to full float precision.
- **Mixed composition**: all five example combinations named in this
  increment's spec verified against real data, including hand-checked
  arithmetic for a 3-point moving average.
- **Boundary context, proven by exact-value comparison** (the same
  technique used in Increment 005): for `percent_change`, `absolute_change`,
  and `moving_average(window=4)`, a pipeline request with `start_date` set
  produced a first value that matched the equivalent unfiltered
  single-series `.../transform` computation to full float precision, and
  the context-only preceding dates were confirmed absent from the
  pipeline's output.
- **Analysis semantics over final values**: `matching_pairs`/`usable_pairs`
  confirmed to reflect the *post-transformation* aligned set, not the raw
  one (e.g. a `percent_change` side's null first value correctly reduced
  `usable_pairs` below `matching_pairs`).
- **Zero exact-date matches and undefined correlation**: both produced
  the same `200`-with-`null`/empty-counts behavior established in
  Increment 006, unchanged.
- **Validation**: malformed body, an unsupported transformation type, and
  an unsupported analysis type all → `422` via Pydantic/FastAPI structural
  validation; `window` outside `[2, 365]` → `422` (Pydantic `Field`
  bounds); `moving_average` missing `window`, and `window` supplied to
  `absolute_change`/`percent_change` → `400`, via the same
  `InvalidWindowError` (reused, not reimplemented) Increment 005
  established for the identical rule; `start_date > end_date` → `400`;
  a nonexistent `series_a`/`series_b` → `404`, each correctly named.
- **No FRED dependency**: `FREDClient` patched to raise on instantiation;
  pipeline requests with and without transformations both still returned
  `200` normally.
- **No PostgreSQL mutation**: row counts and `UNRATE`'s `updated_at`
  timestamp compared before/after several pipeline requests (including
  transformed ones) — identical, matching the same timestamp recorded
  since Increment 003's verification.
- **Database failures**: unreachable `DATABASE_URL` → `503`, no
  connection string leaked; a mocked generic `SQLAlchemyError` → `500`.
- Confirmed via `git status` that `app/repositories/`, `app/domain/`,
  `alembic/`, and `pyproject.toml` are completely untouched by this
  increment, and that no secret value appears in any changed file.

### Deferred decisions

- **Shared context-retrieval orchestration between `EconomicDataService`
  and `AnalysisService`.** The modest duplication described above (the
  retrieve-context-transform-trim sequence, re-expressed rather than
  extracted) is a real, acknowledged tradeoff, made deliberately to avoid
  touching Increment 005's working code. If a third consumer of this
  exact sequence emerges, that's the point to extract a shared helper —
  two occurrences are a coincidence worth tolerating; three would be a
  pattern worth naming.
- **Frequency-aware composition** (comparing series of different native
  reporting frequencies) — explicitly deferred, per
  [ADR-011](adr/011-exact-date-alignment.md) and this increment's own
  "no frequency handling" boundary.
- **Pipeline result pagination** — deferred for the same population-
  integrity reason as Increments 005/006.

### Reusable engineering lessons

- The strongest evidence that two independently-built capabilities are
  actually composable isn't that they *can* be wired together — it's that
  wiring them together requires editing neither one. Confirming
  `app/domain/transformations.py` and `app/domain/analysis.py` needed
  zero changes for this increment is the real proof Increments 005 and
  006 were each designed at the right level of reusability.
- An ordering requirement that exists to prevent a *silent* wrong answer
  (filter-then-transform producing a quietly incorrect first value, not a
  crash) deserves more explicit documentation than an ordering requirement
  that would simply fail loudly if violated — a silent correctness bug is
  the more dangerous kind precisely because nothing signals it happened.
- Not every duplication is worth eliminating immediately. Extracting a
  shared abstraction to avoid ~15 lines of orchestration duplication,
  at the cost of coupling two independently-evolving services or
  modifying already-verified working code, was correctly judged not
  worth it *yet* — the honest move was to duplicate, name the tradeoff
  explicitly, and set a concrete condition ("if a third consumer appears")
  for revisiting it, rather than either silently duplicating without
  comment or over-engineering a shared abstraction for two call sites.

---

## Increment 008 — LLM Tool-Calling Foundation

**Objective:** answer natural-language questions about persisted economic
data by having an LLM call our own deterministic engine — never by having
the LLM compute an answer itself. `POST /api/v1/ai/query` accepts one
message, lets OpenAI's native tool calling invoke up to three
application-level tools over Increments 004–007's existing capabilities,
and returns the model's final answer alongside a record of which tools
ran. This is a foundation, not an agent: one request, one message, no
memory, no autonomy beyond a small bounded tool loop.

### Why AI is introduced now, not earlier

Every increment before this one built something the AI would otherwise
have had to fake. An LLM asked "what's the correlation between UNRATE and
CPIAUCSL" has no reliable way to answer correctly on its own — it would be
guessing, or worse, confidently wrong. Increments 004–007 turned "get
persisted observations," "transform a series," and "compare two series"
into deterministic, already-verified operations; Increment 008's entire
job is to let an LLM *reach* those operations, not to reimplement or
improve on them. Building an AI layer before the deterministic engine
existed would have meant building on top of nothing — either the model
would be inventing numbers, or this increment would have had to build the
engine and the AI layer at once, conflating two very different kinds of
correctness (mathematical determinism vs. natural-language usefulness)
in one change.

### Division of responsibility: the model explains, the engine calculates

This is the architectural spine of the whole increment, restated everywhere
it matters (the system instructions, this journal, the ADR): **the model
never computes an economic value.** Every number in a response — a raw
observation, a percentage-point change, a correlation coefficient — comes
from a tool call into code that existed and was verified in an earlier
increment. The model's job is entirely on the language side: deciding
*which* tool answers the question, supplying arguments, and turning a
structured JSON result into readable prose. If a user asks for a moving
average, the model calls `transform_series`; it does not receive ten raw
numbers and average them in its own reasoning. This is not a suggestion
in the system prompt alone — it's enforced architecturally, because the
model is never given raw enough data to compute the value some other way
without the tool (e.g. `get_observations` returns real values, but
nothing stops a model from doing arithmetic on them instead of calling
`transform_series` — the system instruction is the actual guard against
*that* specific failure mode, which is why it says so explicitly rather
than assuming architecture alone prevents it).

### Native OpenAI tool calling, not an agent framework

The OpenAI Python SDK's Responses API (`client.responses.create`) was used
directly — `instructions`, `input`, `tools`, `previous_response_id`, and
reading `response.output` for `function_call` items are the entire
integration surface. No LangChain, LangGraph, LlamaIndex, Semantic
Kernel, or custom agent framework was introduced. For exactly three
fixed, known tools and a request/response cycle with a small bounded
number of rounds, an agent framework would add a layer of indirection
(its own tool-registration API, its own execution loop, its own
exception types) over something the underlying SDK already does directly
and simply. See [ADR-013](adr/013-native-openai-tool-calling.md) for the
fuller reasoning, including what would justify revisiting this.

One practical note from actually building against the installed SDK: the
OpenAI Python package has moved through major version generations fast
enough (this project installed `openai` 3.13.0; the Responses API's core
shape — `instructions`/`input`/`tools`/`previous_response_id`/`output`/
`output_text` — has stayed stable across that churn) that verifying the
exact API surface by installing the real package and inspecting its types
directly (`inspect.signature`, `model_fields`, reading generated
TypedDicts) was more reliable than trusting any single remembered version
of the API. That verification step is recorded here because it's a
reusable practice, not just incidental to this increment.

### Three coarse application-level tools, not one per domain function

The tool surface is deliberately coarse: `get_observations`,
`transform_series`, `analyze_series` — one per *use case*, not one per
underlying function. `EconomicDataService` alone has four public methods
(`get_series`, `sync_series`, `get_observations`,
`get_transformed_observations`); only two of those are exposed as tools
at all, and neither `get_series` (FRED-backed) nor `sync_series`
(FRED-backed and mutating) is reachable by the model, on purpose — see
the read-only section below. `analyze_series` maps onto one method,
`AnalysisService.pipeline`, chosen deliberately over exposing
`AnalysisService.compare` as a separate fourth tool, since `pipeline` is
a strict superset of what `compare` does (raw-only comparison is just a
pipeline request with no transformation on either side) — one tool
covering both cases is simpler for the model to reason about than two
overlapping ones. Coarse, use-case-shaped tools also make the read-only
guarantee easier to state and verify: three tools to audit, not a dozen
domain functions each individually re-litigated for safety.

### Tool schemas, hand-written, not auto-generated from Pydantic

Each tool's JSON schema (name, description, parameters) is hand-written
in `app/services/ai_tools.py`, not derived from the Pydantic argument
models via `model_json_schema()`. This was a deliberate simplicity choice
for exactly three tools: a hand-written schema is fully readable in one
place, side-by-side with the Pydantic model it must stay consistent
with, without needing to reason about how Pydantic's schema generator
represents `X | None` fields (`anyOf` unions), nested models (`$defs`/
`$ref`), or OpenAI's stricter schema requirements when `strict: true` is
requested (every property effectively required, not just the ones a
caller must supply). This project uses `strict: False` for all three
tools — deliberately, because the schema shown to the model is not the
actual safety boundary; the Pydantic validation in `execute_tool` is (see
next section), so there was no correctness reason to fight `strict`
mode's stiffer requirements for schemas the model only uses as a guide.

### Tool argument validation: never trust the model

Every tool call's arguments go through `ArgsModel.model_validate(raw_arguments)`
(`GetObservationsArgs`, `TransformSeriesArgs`, or `PipelineRequest`
reused directly for `analyze_series`) before any application code runs.
A `pydantic.ValidationError` here — a missing required field, a `window`
outside `[2, 365]`, an unrecognized `transformation`/`analysis` enum
value, a wrong type — becomes a structured `{"ok": false, "error":
{"type": "invalid_arguments", ...}}` result, never an exception that
reaches application code with unvalidated data. This is the actual
security/correctness boundary named in the task: the JSON schema shown to
the model is a *hint*, not an enforcement mechanism — a model can, in
principle, emit anything as tool-call arguments (malformed JSON,
extra/missing fields, wrong types), and this project's safety depends
entirely on validating that against the same Pydantic models the rest of
the application already trusts, not on the model behaving.

### The tool dispatcher: an explicit dict, not reflection

`app/services/ai_tools.py`'s `_TOOL_HANDLERS` is a plain
`dict[str, tuple[ArgsModel, handler]]` — three entries, checked by a
single `.get(name)`. No `getattr`/dynamic import/plugin registry exists
anywhere in the AI path. For three fixed tools, a dict lookup is the
entire "dispatch" problem; building a registry or plugin system for three
entries would be solving a scaling problem this project doesn't have.

### Tool result contract: JSON-serializable, never a leaked internal

Every tool handler returns `response.model_dump(mode="json")` — the same
Pydantic response model the equivalent HTTP endpoint would return, plain
dict/list/str/float/None, `date` values already converted to ISO
strings. No SQLAlchemy ORM object, no `Session`, no exception instance,
and no raw traceback ever crosses into a tool result or gets
`json.dumps`'d back to the model. Expected failures (an unknown tool
name, arguments that don't validate, a nonexistent persisted series, a
bad date range, an invalid transformation window, a database outage) all
become the same small structured shape:
`{"ok": false, "error": {"type": "...", "message": "..."}}` — a fixed,
non-secret message string per error type, never `str()` of the raw
exception, and never a raw OpenAI/database error body.

### The tool loop and its round limit

`AIService.query` is a `while True` loop: send the message, check
`response.output` for `function_call` items, and if there are none, stop
and return the model's final text. If there are tool calls, execute each
one (multiple in the same round if the model requested several at once —
verified directly, see below), feed every result back via
`function_call_output` items keyed to `previous_response_id`, and let the
model continue. `MAX_TOOL_ROUNDS = 4` counts rounds, not individual calls
within a round — if the model still wants to call tools after 4 rounds,
`ToolRoundLimitExceededError` stops the loop deliberately rather than
letting it run indefinitely, and the route turns that into a `503` rather
than hanging the request. This is a bounded request/tool/response cycle,
not autonomous planning: nothing here lets the model decide to keep
going past a fixed, small ceiling this project controls.

### Read-only, end to end

No tool in this increment can sync, write, delete, run a migration, or
execute arbitrary SQL — `get_observations` and `transform_series` call
only the read methods already used by the existing `GET` endpoints;
`analyze_series` calls `AnalysisService.pipeline`, itself read-only since
Increment 007. `AIService`/`app.services.ai_tools` import no
`FREDClient` at all (confirmed by inspection — the only "FREDClient"
string anywhere in that module is in a docstring explaining that none is
constructed), so there is no code path by which the AI layer can reach
FRED, sync a series, or trigger a refresh — a series that isn't already
persisted is a `series_not_found` tool error, not an invitation to fetch
it. This was proven directly, not just reasoned about (see Verification).
See [ADR-014](adr/014-read-only-ai-tools.md) for why this is a durable
policy for this increment, not an incidental property of what happened to
get built.

### Provider/model configuration

`OPENAI_API_KEY` and `OPENAI_MODEL` follow the exact pattern
`FRED_API_KEY`/`DATABASE_URL` already established: read once in
`app/core/config.py` via `os.environ.get(...)`, `None` if unset, checked
at the point of use (the route returns `503` if either is missing) rather
than failing application startup. No model name is hardcoded anywhere in
application logic — `AIService` reads `settings.openai_model` and passes
it to every `responses.create` call; changing models is a configuration
change, never a code change. `openai_timeout_seconds` (a fixed constant,
`30.0`, mirroring `fred_timeout_seconds`) is passed explicitly to the
`OpenAI` client constructor, continuing this project's standing rule that
every outbound external call has an explicit timeout.

### Failure boundaries

| Condition | Where caught | Result |
|---|---|---|
| `OPENAI_API_KEY`/`OPENAI_MODEL` missing | Route, before constructing `AIService` | `503`, generic message |
| OpenAI rejects the API key | `AIService._create_response`, `openai.AuthenticationError` | `503`, generic message |
| OpenAI unreachable/timed out | `openai.APITimeoutError`/`APIConnectionError` | `503`, generic message |
| OpenAI returns another error status | `openai.APIStatusError` | `503`, generic message |
| Unknown tool name / invalid arguments | `execute_tool`, before any handler runs | Structured tool error, loop continues |
| Series not persisted / bad date range / bad window | `execute_tool`, from the existing service exceptions | Structured tool error, loop continues |
| Database unavailable during a tool call | `execute_tool`, `sqlalchemy.exc.OperationalError` | Structured tool error, loop continues |
| Tool-round limit exceeded | `AIService.query`, `ToolRoundLimitExceededError` | `503`, generic message |
| Anything genuinely unexpected | Not caught anywhere in the AI path | FastAPI's default `500` |

The last row is deliberate, not an omission: this project's established
discipline (every route since Increment 003) is to map only the
exceptions that can realistically occur, and let a truly unanticipated
exception surface loudly as a `500` rather than being absorbed into a
catch-all that would hide a real bug behind a vague AI-sounding apology.

### Verification performed

Against isolated tool-dispatcher tests, a mocked tool-calling loop (no
network dependency), and — since a real `OPENAI_API_KEY` was already
configured — real requests through the actual OpenAI API:

- **Tool dispatch** (mocked OpenAI client, real database): `get_observations`,
  `transform_series`, and `analyze_series` each verified to call through
  to the real, unmodified `EconomicDataService`/`AnalysisService` methods
  — `analyze_series`'s correlation result matched the exact value
  (`-0.8030258377001954`) already established in Increments 006/007,
  confirming zero drift from reusing the same code.
- **Validation before execution**: an unknown tool name, a `limit` outside
  its bounds, a missing required field, and a `moving_average` missing
  `window` (caught by the reused `InvalidWindowError`, not a duplicate
  check) all produced the correct structured error, and none reached a
  handler.
- **Mocked tool loop**: a no-tool response, a single-tool round, parallel
  tool calls within one round, a tool result correctly fed back via
  `function_call_output` producing a final answer, `tools_used` matching
  exactly what was called and with what arguments, malformed tool-call
  JSON, an unknown tool name mid-loop, and the round limit being enforced
  (a client that always requests another tool call was stopped exactly at
  round 4, not run indefinitely) — all verified without a network call.
- **Provider failure paths** (mocked `openai` exceptions): missing API
  key, `AuthenticationError`, `APITimeoutError`, and `APIConnectionError`
  each produced the correct generic `503`, with no OpenAI response body
  or exception detail included.
- **Real end-to-end requests** (real OpenAI API, `OPENAI_MODEL` supplied
  as a non-secret environment override, `OPENAI_API_KEY` never read or
  displayed): a "say hello, use no tools" prompt returned an answer with
  `tools_used: []`; "how has UNRATE changed, use absolute_change" correctly
  called `transform_series` and returned a table whose values matched the
  deterministic engine's known output exactly (e.g. `+0.1` for
  2026-02-01); "correlate UNRATE and CPIAUCSL" correctly called
  `analyze_series` and reported `-0.80` (matching `-0.8030...` rounded),
  explicitly framed as correlation, not causation; "what's the current
  price of gold" (data this system doesn't have) correctly triggered no
  tool call and an honest "I don't have access to that" answer rather
  than an invented number.
- **No PostgreSQL mutation, proven live**: `economic_series`/
  `economic_observations` row counts and `UNRATE`'s `updated_at`
  timestamp were unchanged after this session's real tool-calling
  requests — the same counts and the same timestamp recorded since
  Increment 003, now also surviving real LLM-driven tool calls, not just
  direct HTTP calls to the deterministic endpoints.
- **No FRED reachability, no duplicate math**: confirmed via direct
  inspection that no file in the AI path imports `FREDClient` or any
  `app.domain.*` function directly — every number the AI path can produce
  comes through `EconomicDataService`/`AnalysisService`, unmodified.
- Confirmed no schema migration, no dependency beyond `openai` itself
  (plus an unrelated, pre-existing `pyproject.toml` packaging fix — see
  below), and no secret value in any changed file or `.env.example`.

### An unrelated packaging fix, made along the way

Installing the new `openai` dependency exposed a latent, pre-existing
issue: a newer `setuptools` refuses `pip install -e .` because flat-layout
auto-discovery finds both `app/` and `alembic/` as candidate top-level
packages and won't guess which is intended. Confirmed via `git stash`
that this failure predates this increment's changes entirely — it was
simply never triggered until a fresh dependency install pulled in a
newer `setuptools`. Fixed with a two-line `[tool.setuptools.packages.find]`
addition scoping discovery to `app*`. Recorded here rather than silently
folded into the dependency-bump diff, since a reader of the `pyproject.toml`
diff should know why an unrelated-looking build-system stanza appeared in
an "add AI" increment.

### Deferred decisions

- **Auto-generating tool schemas from Pydantic models** — deferred; see
  the schema section above. Worth revisiting if the tool surface grows
  enough that hand-maintaining schema/model consistency becomes real
  effort.
- **A native `max_tool_calls` parameter** — the installed SDK exposes one
  directly on `responses.create`. Not used here in favor of this
  project's own explicit round-counting loop, which the task specifically
  asked for and which this project fully controls and tests; revisit if
  the provider-native limit offers a real advantage (e.g. enforcing the
  cap even against a provider-side bug in this project's own loop logic)
  once both approaches can be compared directly.
- **Conversation memory, streaming, series discovery/search** — all
  explicitly out of scope per the task; genuinely separate, larger design
  problems each deserving their own increment.

### Reusable engineering lessons

- When adding an LLM to a system that already has a deterministic core,
  the design question worth spending the most care on isn't "what can the
  model do" — it's "what can the model *not* do," made structurally true
  rather than merely requested in a prompt. The system instruction here
  tells the model to use tools for calculations; the actual guarantee
  that persisted values are never invented comes from what data the model
  is and isn't given access to, not from the instruction being followed.
- Verifying a fast-moving external SDK's actual current shape by
  installing it and introspecting its real types beats trusting a
  remembered API from training data — especially for a provider SDK that
  has visibly moved through several major versions.
- "Never trust model-generated input" is the same engineering discipline
  as "never trust user-generated input," applied to a new kind of caller.
  The Pydantic validation boundary that already protected every HTTP
  endpoint in this project needed no new concept to extend to tool
  arguments — only the recognition that an LLM's tool call is exactly as
  untrusted as an HTTP request body, arguably more so.
- A bounded loop with a small, explicit, tested ceiling is a simple and
  sufficient safeguard against runaway behavior — reaching for something
  more sophisticated (budget tracking, cost estimation, adaptive limits)
  would have been solving a problem this foundation increment doesn't
  have yet.

---

## Increment 009 — Economic Series Discovery & Grounding

**Objective:** let a user speak in economic concepts ("inflation,"
"unemployment," "real GDP") instead of memorized FRED identifiers, by
adding a fourth AI tool, `search_series`, that discovers real, verified
candidate series — and, just as importantly, enforcing in application
code that the model can never use a series identifier it didn't get from
a verified source. The tool surface is now exactly `search_series`,
`get_observations`, `transform_series`, `analyze_series` — discovery plus
the three read-only analysis tools from Increment 008, unchanged.

### The usability problem raw FRED identifiers create

Every AI capability before this increment required the user (or the
model) to already know that "unemployment" means `UNRATE` and "the CPI"
means `CPIAUCSL`. That's a real usability gap: the whole point of a
natural-language interface is that the user shouldn't need to know the
data provider's internal naming scheme. But closing that gap carelessly
creates a worse problem than the one it solves — an LLM asked "what's the
series ID for inflation" will confidently answer with *something*,
correct or not, because generating a plausible-looking identifier is
exactly the kind of task language models are good at even when they
shouldn't be trusted to do it. This increment's entire design is shaped
by that tension: make concepts usable, without ever letting the model's
fluency substitute for verification.

### Verified candidates vs. model invention — the core rule, made structural

"The LLM may search for series. The LLM may select from verified series.
The LLM must never invent a series identifier." The first two clauses are
served by `search_series`; the third is enforced by `GroundingContext`
(see below), not merely requested in a prompt. Every `SeriesCandidate`
this increment can ever produce traces back to one of exactly two
sources: a real row in `economic_series`, or a real FRED `series/search`
HTTP response. There is no code path anywhere in
`SeriesDiscoveryService`/`FREDClient.search_series` that constructs a
candidate from the search query text itself — a query like "inflation"
never becomes a candidate named "INFLATION" if nothing on either side
actually reports back a series by that identifier.

### Two conceptual planes, made concrete in code, not just in this journal

- **Discovery plane** ("what series exist"): `SeriesDiscoveryService`
  (`app/services/discovery.py`), which may read local PostgreSQL metadata
  *and* FRED's catalog. Read-only on both sides.
- **Analysis plane** ("what does the persisted data say"):
  `EconomicDataService`/`AnalysisService`, unchanged since Increments
  004/005/007, exclusively PostgreSQL.

The boundary isn't just documentation — it's a real dependency fact:
`SeriesDiscoveryService` never imports anything from `app.domain.*`
(confirmed by inspection), and `EconomicDataService`/`AnalysisService`
still never import `FREDClient` for anything except the pre-existing
`get_series`/`sync_series` methods that were already FRED-backed before
this increment and remain unreachable from the AI path (Increment 008's
[ADR-014](adr/014-read-only-ai-tools.md)). `search_series` is the single,
explicitly named exception allowed to reach FRED from the AI path — and
even it is restricted to one FRED endpoint
(`fred/series/search`) that returns metadata only; `FREDClient.search_series`
shares all of the existing client's HTTP/timeout/error-handling
machinery, and adds no new way to fetch observation values.

### Local search: simple, deliberately not clever

`SeriesRepository.search_series` is a case-insensitive `ILIKE` match
against `series_id` OR `title` — no PostgreSQL full-text search
infrastructure, no fuzzy-matching dependency, no embeddings. For a
catalog of a handful of persisted series, a substring match answers the
actual question ("does anything we have match this text") without adding
infrastructure sized for a catalog this project doesn't have yet. The
repository has no opinion about which match is economically
"best" — that judgment belongs to the model, working from the metadata
`SeriesDiscoveryService` hands it, not to a SQL query.

### FRED catalog search: metadata only, verified directly against the real API

`FREDClient.search_series` calls `fred/series/search` with
`search_type=full_text`, `order_by=search_rank`, `sort_order=desc`, and a
small bounded `limit` — verified directly against the real FRED API
before writing any application code around it (not assumed from
documentation): "unemployment" surfaces `UNRATE` as its top result,
"real GDP" surfaces `GDPC1` exactly as this increment's own prompt
example expects, and a zero-match query returns FRED's normal `200`
empty-list response, not an error. One genuine, unplanned discovery from
that verification: a bare "inflation" query does *not* surface `CPIAUCSL`
in FRED's own top-5 full-text ranking (FRED ranks inflation-*indexed*
Treasury securities higher) — a real fact about the provider's search
quality, not a bug in this project's code, and left exactly as FRED
reports it rather than "corrected" with a hardcoded boost (see Deferred
decisions).

### Candidate metadata: honest about what's actually persisted

`EconomicSeries` (Increment 003's schema) persists `series_id`, `title`,
`units`, and `source` -- nothing else. It has no `frequency`,
`seasonal_adjustment`, `observation_start`/`observation_end`, or
`popularity` columns. Rather than adding a migration to enrich local
storage for this increment (explicitly out of scope), a `SeriesCandidate`
simply reports `None` for whichever of those fields no source actually
supplied — a local-only match has real `units` but `None` frequency/
seasonal_adjustment/popularity/observation range; a FRED-only or merged
match has all of them, straight from FRED's own response. Nothing is
invented to fill the gap, and nothing pretends more is known locally than
actually is.

### Deduplication and merging: one candidate per series_id, richer wins

A series present in both sources appears once. `SeriesDiscoveryService._merge`
builds a `dict[series_id, SeriesCandidate]`: local matches seed it
(`persisted=True`, `discovery_source="local"`); each FRED result either
creates a new entry (`persisted=False`, `discovery_source="fred"`) or, if
the `series_id` already exists locally, replaces that entry's metadata
with FRED's richer version via `model_copy(update={...})` while forcing
`discovery_source="local_and_fred"` — `persisted=True` is never lost in
that merge, since the update never touches that field. Verified directly:
searching "unemployment" returns exactly one `UNRATE` candidate,
`persisted=True`, `discovery_source="local_and_fred"`, carrying FRED's
`frequency`/`popularity`/observation range alongside the locally-known
`units`.

### Deterministic ranking: three plain comparison keys, no scoring model

`_rank`'s sort key is `(not exact_id_match, not persisted, fred_search_rank_position)`
— nothing more. An exact `series_id` match always surfaces first
(tier 0); among the rest, a persisted (locally analyzable) candidate
outranks a FRED-only one (tier 0 vs. 1 within the remaining group); ties
within a tier keep FRED's own `search_rank` order, with local-only
candidates (no FRED signal) sorting last within their tier. No machine
learning, no embedding similarity, no LLM-generated relevance score —
three deterministic, explainable comparisons, matching the "keep it
simple, deterministic, documented" instruction directly.

### No hardcoded concept → series aliases, and why that restraint matters here specifically

A dictionary like `{"inflation": "CPIAUCSL", "gdp": "GDPC1"}` would have
made the common cases feel instant, and was deliberately not built.
"Inflation" alone is at least five real, different, non-interchangeable
FRED measures (CPI, core CPI, PCE, core PCE, PPI); "GDP" is nominal vs.
real vs. per-capita vs. growth-rate. An alias dictionary bakes in one
answer to a question that genuinely has several defensible answers,
silently, with no way for a user to know a choice was made on their
behalf. `search_series` plus the model's own judgment over real metadata
(units, frequency, persisted availability) is slower for the common case
but never silently substitutes the wrong measure for the one actually
asked about — and when the honest answer is "these are materially
different measures," the model is instructed to say that rather than
picking one arbitrarily (verified: a real ambiguous-measure request
should surface multiple candidates rather than confidently naming one).

### Grounding as an application-enforced boundary, not a prompt request

`GroundingContext` (`app/services/ai_tools.py`) is the actual mechanism:
a plain dataclass — `user_message: str`, `verified_ids: set[str]` — created
fresh inside `AIService.query()` for every request (a local variable,
never global, never written to PostgreSQL, no Redis/session
infrastructure). It's threaded as an explicit fourth parameter into every
`execute_tool` call for that request. Before `get_observations`/
`transform_series`/`analyze_series` executes, `execute_tool` extracts the
series identifier(s) from that tool's *validated* arguments (via a small
per-tool `extract_series_ids` function in `_TOOL_HANDLERS`) and checks
each one against `grounding.is_grounded(...)`. Any identifier that fails
is never passed to `EconomicDataService`/`AnalysisService` at all — the
tool call is refused with a structured `ungrounded_series` error before
the handler (and the real database lookup inside it) ever runs. This was
verified directly, not just reasoned about: a script called
`execute_tool("get_observations", {"series_id": "MADEUP123"}, ...)`
directly and confirmed the result was `{"ok": false, "error": {"type":
"ungrounded_series", ...}}`, never reaching `EconomicDataService`.

A subtlety worth naming precisely: grounding answers "is this identifier
safe to *reference*," which is a different question from "does this
identifier *exist*." A `search_series` result for a non-persisted FRED
series (e.g. `GDPC1`) is grounded — the model is allowed to mention and
reference it — but `transform_series({"series_id": "GDPC1", ...})` still
fails, now with `series_not_found` (Increment 004's existing, unmodified
check), because grounding was never meant to replace the persisted-data
check; it's an *additional*, earlier gate answering a different question.

### Request-scoped state: a local variable, not new infrastructure

The task explicitly asked for "the smallest clean mechanism for
request-scoped grounding state" and explicitly ruled out globals, Redis,
and PostgreSQL persistence. A `GroundingContext` instance's entire
lifetime is the body of one `AIService.query()` call — created at the top
of the method, passed down the call stack, and garbage-collected when the
method returns. No new architecture was needed because request-scoped
state has an obvious home in a language with function-local variables:
the function that already owns "this request," `query()`, is where its
state should live.

### Explicit user-provided identifiers: checked against the message text, not extracted from it

The task explicitly warned against "a brittle regex that treats every
uppercase word as a FRED ID." This increment does not extract candidate
identifiers from the user's message at all. Instead,
`GroundingContext.is_grounded(series_id)` checks whether *a specific
identifier the model has already proposed* appears as a case-insensitive
whole word in the user's own message
(`re.search(rf"\b{re.escape(series_id)}\b", ..., re.IGNORECASE)`). This
is a meaningfully different (and safer) operation than scanning free text
for identifier-shaped tokens: it never guesses candidates from the
message, so a vague concept word like "gdp" in "what about gdp trends"
does not accidentally ground the specific identifier `GDPC1` (verified
directly — that exact case was tested and correctly rejected as
ungrounded). A user who types "Show me UNRATE since 2020" gets it for
free, because the model proposing `series_id: "UNRATE"` and the user
having typed "UNRATE" are the same string, checked once, safely.

### No auto-sync — verified live, not just by inspection

`GDPC1`, discovered as a verified but non-persisted candidate during real
end-to-end testing (see Verification), was never synced, and the
database's row counts and `UNRATE`'s `updated_at` timestamp were
confirmed unchanged immediately afterward — the same timestamp recorded
since Increment 003, now also surviving a real conversation that
discussed a non-persisted series by name. No handler in this increment
calls `sync_series`, constructs a write-capable service, or fetches FRED
observations for a discovered-but-unpersisted series; the model's only
available response to "the data I found isn't persisted" is to say so,
which it did, unprompted by any special-cased instruction beyond the
system prompt's general "say so plainly instead of guessing."

### Graceful degradation: FRED unavailable, database unavailable, malformed FRED entries

Three distinct failure shapes, each handled at the layer that actually
owns the concern:

- **FRED unreachable/rejected/timed out during search** —
  `SeriesDiscoveryService.search` catches `FREDError` (the shared base
  class already used throughout `FREDClient`) around the FRED call only,
  setting `external_search_available=False` and returning whatever local
  results exist. Verified with both a real timeout (unroutable host) and
  a real rejected-key request against the live FRED API — both degraded
  cleanly, local `UNRATE` still returned.
- **Database unavailable during a `search_series` call** — not
  special-cased; propagates to `execute_tool`'s existing
  `OperationalError`/`SQLAlchemyError` handling (unchanged from Increment
  008), the same structured-error treatment every other tool already gets.
- **A malformed FRED search result** (missing `id`) — `_merge` skips it
  (`if not series_id: continue`) rather than fabricating a blank-identifier
  candidate or crashing.

### AI instruction changes

The system instruction gained a second paragraph: don't invent
identifiers (an invented one will be rejected regardless, but the model
should not attempt it), use `search_series` first for a named concept,
only pass an identifier from a `search_series` result or the user's own
words, say plainly when a discovered series isn't persisted rather than
substituting a different one, and prefer the candidate that actually
matches the user's concept over simply the most popular one — explaining
ambiguity rather than picking arbitrarily when it's real. This is
architecture-first, instruction-second, matching Increment 008's existing
stance: the instruction guides good behavior; `GroundingContext` is what
actually prevents bad behavior from working.

### Verification performed

Against isolated dispatcher tests, real FRED requests, real database
queries, and real OpenAI requests (no `.env` ever read):

- **Local discovery**: exact `series_id` match, title substring match,
  and both in lowercase, all correctly returned `persisted=True`;
  metadata FRED doesn't get asked for stayed `None` for a local-only
  match, as designed.
- **FRED discovery**: real requests for "unemployment," "real GDP," and
  "inflation" against the live FRED API — the first two matched this
  increment's own examples exactly (`UNRATE`, `GDPC1` as top results);
  `limit` was respected and a request for more than 10 was rejected by
  Pydantic before any network call.
- **Injection safety**: a tool call supplying extra `url`/`api_key` fields
  had them silently dropped by Pydantic (`SearchSeriesArgs` has no such
  fields) — never forwarded anywhere, confirming the model cannot control
  the FRED hostname, endpoint, or credential.
- **Merging/deduplication**: `UNRATE` (present in both sources) returned
  exactly once, `persisted=True`, `discovery_source="local_and_fred"`,
  carrying FRED's frequency/popularity/observation-range metadata.
- **Grounding**: a model-invented identifier (`MADEUP123`) was rejected
  with `ungrounded_series` *before* reaching `EconomicDataService`;
  the same for one ungrounded side of an `analyze_series` call, never
  reaching `AnalysisService`; a `search_series` call followed by
  `get_observations`/`transform_series` for a returned candidate
  succeeded; an explicit user-typed identifier (`"Show me UNRATE..."`,
  including a lowercase variant) succeeded without any search call; a
  vague concept word ("gdp") correctly did *not* ground a specific,
  unrelated identifier (`GDPC1`); a genuinely nonexistent identifier
  typed by the user (`"Show me BOGUS999..."`) passed grounding (the user
  really did say it) but still failed safely at the existing
  `series_not_found` check, never fabricating a result for it.
- **Real end-to-end conversations** (real OpenAI + real FRED + real
  database, `OPENAI_MODEL` supplied as a non-secret override): "search
  for unemployment data and show me the recent observations" correctly
  called `search_series` then `get_observations(UNRATE)` in 2 rounds;
  "what is the correlation between the consumer price index and the
  unemployment rate" correctly called two searches then `analyze_series`,
  reporting the exact known correlation (`-0.80`, matching
  `-0.8030258377001954`); "how has real GDP changed" correctly searched,
  found `GDPC1` as `persisted=False`, and explained the limitation
  without attempting analysis or synchronization.
- **No mutation, no auto-sync, proven live**: `economic_series`/
  `economic_observations` row counts and `UNRATE`'s `updated_at`
  timestamp were identical before and after this session's entire batch
  of real AI conversations (including the ones that discovered and
  discussed `GDPC1`) — the same counts and timestamp recorded since
  Increment 003.
- Confirmed via `grep`/`git status` that no domain math is duplicated
  anywhere in the new code, no concept-alias dictionary exists, no
  module-level/global grounding state exists, no schema migration was
  added, no new dependency was added, and no secret value appears in any
  changed file.

### An honest, reproducible limitation found during verification

The bare word "inflation," combined with a date-range request (e.g. "How
has inflation moved relative to unemployment since 2022?"), reliably
exceeded `MAX_TOOL_ROUNDS=4` and returned a `503` — reproduced twice, not
a flake. The root cause is upstream and understood precisely: FRED's own
full-text search ranks inflation-*indexed* Treasury securities above
`CPIAUCSL` for the literal word "inflation" (confirmed directly against
the real API — see the FRED catalog search section above), so the model
spends extra search rounds refining its query before it can proceed to
`analyze_series`, and a two-concept request with a date range leaves less
round budget to spare. The *identical* request phrased as "the consumer
price index" — exactly the kind of refinement `search_series`'s own tool
description already asks the model to make — succeeded in 2 rounds with
the exactly correct result. This is not a grounding or dispatcher bug (both
were independently verified correct in isolation); it's a real interaction
between one ambiguous natural-language term, FRED's actual search
ranking, and a deliberately small round budget. Recorded here rather than
quietly worked around, per this project's standing practice of reporting
what verification actually finds.

### Deferred decisions

- **FRED search-ranking quirks for specific terms** (e.g. "inflation" not
  surfacing CPI) are not corrected or special-cased — doing so for one
  term would be exactly the hardcoded-alias behavior this increment
  deliberately avoided elsewhere; if this becomes a recurring usability
  problem, the right fix is likely a search-refinement strategy (e.g. the
  model retrying with a narrower phrase, which it already does
  successfully when instructed generally), not a per-term correction.
- **`MAX_TOOL_ROUNDS` tuning** — left at Increment 008's value of `4`.
  The "inflation" case above is a real data point that a two-concept,
  date-ranged discovery-plus-analysis request can be tight against that
  budget; not changed here because one observed case isn't enough
  evidence to pick a new number responsibly, and a larger round budget
  has its own cost (more provider round-trips per request).
- **User-approved ingestion of a discovered-but-unpersisted series** —
  named explicitly in the task as a separate future design decision, not
  attempted here.
- **PostgreSQL full-text search / fuzzy matching for local discovery** —
  deferred until the local catalog is large enough that substring
  matching genuinely stops being sufficient; not the case yet.

### Reusable engineering lessons

- "The model must never invent an X" is only as real as the code path
  that would let it happen if it tried. Writing `GroundingContext` and
  then actually calling `execute_tool` with a fabricated identifier
  directly (not just trusting the system instruction) was what turned
  "we told it not to" into "we verified it cannot."
- A security/correctness check on *which identifier* a tool may act on is
  a different, additional layer from validating *the shape* of a tool's
  arguments (Increment 008) or checking *whether the target exists*
  (Increment 004's `SeriesNotFoundError`) — all three matter, none
  substitutes for the others, and conflating them (e.g. assuming
  "it validated" or "it exists" means "it was safe to reference") would
  have left a real gap.
- When a task warns against a specific brittle pattern ("don't extract
  candidate IDs with a regex over free text"), the fix isn't necessarily
  "don't use regex at all" — it's understanding *why* that specific
  pattern is brittle (it guesses candidates) and finding the safe version
  of the underlying need (checking one already-proposed candidate against
  the text, never generating candidates from it).
- Verifying a real upstream API's actual behavior (FRED's search ranking
  for a specific term) during testing surfaced a real, useful fact this
  project wouldn't have known from documentation alone — and the honest
  response to an inconvenient discovery like that is to document it
  precisely and explain why it isn't being papered over, not to quietly
  adjust the test case until it passes.

### Post-implementation correction: target request exhausted MAX_TOOL_ROUNDS

Increment 009's implementation above passed every check it was written to
check, but its own target usability example — "How has inflation moved
relative to unemployment since 2022?" — reproducibly exhausted
`MAX_TOOL_ROUNDS=4` and returned 503 before commit. This section
documents the diagnosis and the correction actually made, without
rewriting the history above.

**Diagnostic gate.** Before touching any code, a read-only diagnosis
reproduced the failure against the real configured environment
(`search_series`/`get_observations` called directly through
`execute_tool`, bypassing nothing) and traced every round. Round 1
correctly issued two parallel `search_series` calls (for "inflation" and
"unemployment") — proving the four-layer architecture already supports
efficient concept discovery with no code change. The failure was
entirely in round 2 onward: FRED's top-5 "inflation" results are all
Treasury/breakeven-inflation instruments, none persisted locally, and
the canonical `CPIAUCSL` doesn't appear in that top 5 at all. Rather than
using the `persisted:false` field already present in the round-1 result
to avoid a wasted call, or refining the search once with a narrower term,
the model spent one round per remaining candidate calling
`get_observations` on each in turn, learning only from the resulting
`series_not_found` error each time, until the round budget ran out.

A broader discovery check across five concepts ("inflation," "real GDP,"
"federal funds rate," "nonfarm payrolls," "unemployment") showed this
was not an inflation-specific quirk: four of the five returned zero
persisted candidates in their top-5 FRED results. The failure mode was
general and would recur for most economic concepts whose canonical
series isn't already persisted — confirming a term-specific patch (or
simply raising `MAX_TOOL_ROUNDS`) would have hidden the symptom for
"inflation" while leaving the same defect in place everywhere else.

**Root cause.** Not retrieval (candidates were real and relevant), not
candidate metadata (`persisted` was accurate and already present), not
grounding, not the tool-loop/round-counting mechanics, not a hardcoded
alias gap — all of those worked exactly as designed. The gap was that
neither the `search_series` tool description nor `SYSTEM_INSTRUCTIONS`
told the model what to *do* with `persisted:false` before it acted:
treat the field as authoritative and skip straight to a refined search,
rather than treating the candidate list as a queue to try one at a time
via execution.

**Retrieval vs. semantic-selection distinction.** The implementation
already correctly kept these separate — `search_series` never claims a
top result is "the" answer. The model's *observed behavior* is the one
place the distinction broke down in practice, and that's the one place
the fix landed: the `search_series` tool description and
`SYSTEM_INSTRUCTIONS` now say explicitly that search results are
verified candidates for evaluation, not an answer, and that retrieval
ranking is not semantic truth.

**Approved correction (three changes, no architecture change):**

1. `app/services/ai_tools.py` — `search_series`'s tool description now
   states explicitly: results are verified candidates, not one
   authoritative answer; retrieval ranking is not semantic truth;
   inspect metadata before selecting; `persisted:true` means locally
   analyzable now, `persisted:false` means verified-but-not-yet-usable
   and must not be spent on an analytical tool call to discover that;
   persisted status may only break a tie among candidates that already
   fit the concept, never override semantic fit.
2. `app/services/ai.py` — `SYSTEM_INSTRUCTIONS` gained a concise general
   strategy: check `persisted` before attempting an analytical tool;
   never call an analytical tool merely to discover unavailability the
   `persisted` field already answers; if no candidate is both a good fit
   and persisted, refine the query *once* with a more specific
   description of the same concept, then work only with that result;
   otherwise state the limitation honestly. No concept names, no
   alias table — the strategy is generic across any economic concept.
3. `app/models/ai.py` / `app/models/analysis.py` — `SearchSeriesArgs`,
   `GetObservationsArgs`, `TransformSeriesArgs`, `PipelineRequest`,
   `PipelineSeriesSpec`, and `TransformationSpec` (the last three shared
   with the AI `analyze_series` tool and the existing
   `POST /analysis/pipeline` endpoint) now set
   `model_config = ConfigDict(extra="forbid")`. Previously an unexpected
   field in a model-generated tool call was silently dropped (Pydantic
   v2's default `extra="ignore"`); it is now rejected through the
   existing `invalid_arguments` structured error path — no new
   exception handling needed, since `execute_tool` already wraps
   validation in `try/except ValidationError`. Unrelated to the
   round-exhaustion bug; approved as a second, independent hardening.

`MAX_TOOL_ROUNDS` stayed at 4 throughout — raising it would only have
delayed the same failure for a slightly larger candidate pool, and would
have hidden genuinely wasteful behavior rather than fixing it. No
concept → series alias table was added anywhere; the correction is a
strategy ("refine the query once, and check `persisted` first"), never a
mapping from a specific word to a specific identifier.

**Verification results — before/after.** Re-running the diagnostic
reproduction after the correction:

- The named target request ("How has inflation moved relative to
  unemployment since 2022?"), run three times, now converges within
  `MAX_TOOL_ROUNDS=4` every time (previously: did not converge even
  within an extended 8-round diagnostic ceiling). Each run made at most
  one wasted analytical attempt against a `persisted:false` candidate
  (`T10YIE`) before refining the search once (to "consumer price index"
  or "CPI") and reaching `CPIAUCSL`.
- Deterministic checks (tool contract shape, fail-closed argument
  rejection for all four tools and every nested model, grounding/
  persisted-check separation, no global mutable state, request-scoped
  grounding) all passed — 30/30.
- The correction is a real, measured improvement but **not a complete,
  architecturally-guaranteed fix**: re-running the same reproduction for
  other concepts found the identical serial-trial-and-error pattern
  still occurring for "real GDP," "federal funds rate," and one phrasing
  of the ambiguity test ("Compare inflation with unemployment," without
  a date qualifier) — each still exceeded `MAX_TOOL_ROUNDS` by
  serially attempting 3-4 non-persisted candidates before the round
  budget ran out, exactly the pattern the correction targeted. This is
  the expected residual risk of an instruction-level (not code-level)
  correction: a system instruction changes model behavior probabilistically,
  not deterministically, and the application layer has no code-level
  mechanism that *forces* a refine-once strategy — it can only forbid
  unsafe outcomes (grounding, persisted-check, argument validation),
  never guarantee an efficient path to a safe one. Recorded here plainly
  rather than overstated as fully resolved; see the diagnosis report for
  the full per-concept trace.
- A second, unrelated, pre-existing limitation surfaced during
  verification: even where a search correctly finds a persisted
  candidate (`UNRATE`), `get_observations` for `2022+` (and other tested
  ranges) sometimes returns zero observations — the locally synced data
  for that series does not yet cover the ranges these target questions
  ask about. This is a data-completeness gap, not a tool-calling
  architecture defect, and was left out of scope for this correction.

**Reusable engineering lesson.** A metadata field being present and
accurate (`persisted`) is not the same as it being *acted on* — an LLM
tool-use loop will use a field to justify its own after-the-fact
reasoning much more reliably than it will use that same field
*prospectively* to skip an action, unless the instruction says so
explicitly. And a prompt-level fix to a model *behavior* problem can
reduce a failure's frequency substantially without eliminating it
outright — verifying that distinction empirically, per concept, rather
than trusting the named example's improvement to generalize, was what
surfaced the residual failures above.

### Second correction: deterministic execution eligibility (ADR-017)

The prompt-level correction above was a real, measured improvement, but
live re-verification (repeated runs across six economic-concept
questions) showed it remained probabilistic: for several concepts --
real GDP, the federal funds rate, one ambiguity-test phrasing, and even
the named target question in some runs -- the model still requested
`get_observations`/`transform_series` against `persisted: false`
candidates serially, still exhausting `MAX_TOOL_ROUNDS=4`. The
conclusion drawn from that evidence: **prompt instructions are not a
reliable enforcement mechanism for execution safety.** "Remember not to
execute against persisted:false" is a fact the application already knows
with certainty the instant a `search_series` result returns -- asking an
inherently probabilistic component (the model) to carry that fact
forward correctly, unprompted, every time, across an unbounded range of
concepts, was asking wording to do a code boundary's job.

**Semantic-vs-deterministic responsibility boundary.** The correction
keeps the model responsible for everything genuinely probabilistic:
understanding intent, searching concepts, reasoning over verified
candidate metadata, choosing which verified candidate best fits the
user's meaning (including a `persisted: false` one, if that's honestly
the right answer), and explaining real ambiguity. It moves one narrow,
purely factual question out of the model's hands entirely: *may this
already-selected, already-verified series actually execute against the
local analytical dataset right now?* That's never a semantic judgment,
so it's no longer left as one.

**The invariant moved from instruction to code.** `GroundingContext`
(`app/services/ai_tools.py`) now tracks two things per series id, not
one: whether it's verified (unchanged from ADR-015: a `search_series`
result this request, or the user's own literal text), and, separately,
whether it's `persisted` -- authoritative from `search_series`'s own
result when the id came from a search, or resolved via a direct,
read-only `SeriesRepository.get_series_by_series_id` lookup (the same
local check `EconomicDataService`/`AnalysisService` already perform
internally) for an explicitly user-typed id that was never searched.
Neither piece of state has a path for the model to set directly -- no
tool argument carries a `persisted`/`verified` field, and the discovery
side of `GroundingContext` is populated only by `execute_tool` itself,
after a real search has actually returned.

`execute_tool` now runs two independent, deterministic checks for every
series a tool call references, before the underlying service handler
runs for any of them:

1. Grounded (ADR-015, unchanged) -- otherwise `ungrounded_series`.
2. Persisted (new, ADR-017) -- otherwise a new `series_not_persisted`
   error, structured exactly like every other tool error, naming the
   unavailable identifier(s), explicitly stating the determination is
   authoritative so the model shouldn't retry it.

For `analyze_series` (two series), both checks run for both series
before either is authorized -- `AnalysisService.pipeline` is never
invoked at all if either series fails either check, never partially for
one series while the other is still being resolved.

**Verification.** Proven two ways, deliberately kept separate:

- *Direct, with mocks*: `EconomicDataService.get_observations`/
  `get_transformed_observations` and `AnalysisService.pipeline` were
  patched and confirmed **never called** when the gate should block --
  not inferred from the tool result looking right, but from the actual
  service method's call count. 18/18 checks passed, covering both
  single- and two-series tools, both persisted:false and ungrounded
  cases, and the trust boundary itself (no tool-argument field can set
  `persisted`/`verified`; only `search_series`'s own successful result
  populates discovery state; explicit user mention grounds but never
  implies persisted; a fabricated id is blocked the same way a real,
  unpersisted one is).
- *Live, against the real model*: re-ran the six required questions
  (including repeats of the named target question). **Application
  behavior was 100% -- every single blocked-execution attempt across
  every run was deterministically stopped before any service call, with
  zero exceptions observed.** Model behavior (round efficiency) was
  measured honestly and separately: it did **not** reliably improve over
  the prompt-only correction -- several concepts, including the named
  target question in most repeats, still exhausted `MAX_TOOL_ROUNDS` via
  repeated (sometimes literally repeated, not just similar) blocked
  attempts. This is reported as a known, explicit limitation, not
  papered over: the deterministic gate guarantees *safety*, not
  *efficiency*, and conflating the two would be the wrong lesson to draw
  from this result. Whether round-efficiency is worth a *separate*,
  future orchestration change is left as an open question for later,
  not decided here.
- Regression: 31/31 deterministic tool-contract/fail-closed checks and
  9/9 HTTP-level checks (health, FRED GET, sync, observations,
  transformations, compare, `POST /analysis/pipeline` with both
  legitimate and deliberately-invalid bodies) all passed -- including
  confirming the shared, `extra="forbid"`-hardened `PipelineRequest`
  still accepts every legitimate HTTP body it did before.

**Reusable engineering lesson.** When a metadata fact is both available
*and accurate*, but a model still doesn't act on it reliably even after
being told to, the fix is not a better sentence -- it's recognizing that
the fact was never actually a judgment call in the first place, and
moving it to the one place a fact like that belongs: code that runs
before the consequence, not wording that asks nicely beforehand. Safety
and efficiency are different properties and can (and, here, did) move in
different directions from the same change -- measuring both honestly,
separately, rather than letting one good number stand in for the other,
is what kept this correction from being reported as more complete than
it actually is.

### Third correction attempt: dynamic tool availability (ADR-018) -- partial result

A dedicated orchestration design gate (before touching code) compared six
structural options for reducing wasted rounds, given the now-established
conclusion that prompt wording cannot guarantee execution-safety *or*
efficiency. The approved design: shape *which tools, and which
`series_id` values, are even offered* to each model inference after the
first, built fresh every round from this request's own
`GroundingContext` state -- `get_observations`/`transform_series`/
`analyze_series`'s `series_id` (both sides, for `analyze_series`)
constrained via a JSON-schema `enum` to exactly the ids currently known
persisted; omitted entirely when that set is empty. A second, narrower
mechanism -- a bounded discovery-round budget (`MAX_DISCOVERY_ROUNDS=2`)
-- caps `search_series` itself, so search-thrashing couldn't quietly
replace analytical-thrashing as the new failure mode. Round 1 keeps all
four tools unrestricted, preserving the explicit-ID fast path ("Show me
UNRATE" needs no prior search). `execute_tool`'s deterministic gate
(ADR-017) was left completely unchanged, as the frozen, unconditional
safety backstop underneath this new efficiency layer.

**Implementation**: `app/services/ai_tools.py` gained
`GroundingContext.known_persisted_ids()` (the one view of discovery
state anything outside the class gets) and `build_tool_schemas` (pure:
`GroundingContext` state in, an independent, deep-copied tool-schema
list out -- no I/O, no mutation of the module-level base schemas or of
`GroundingContext`). `app/services/ai.py` gained `MAX_DISCOVERY_ROUNDS`,
a pure `_round_had_successful_search` helper (the exact, documented rule
for what counts: a tool-bearing round with at least one `search_series`
call that returned `ok: true` -- multiple parallel searches in one round
still count as one; `invalid_arguments`/database-failure searches don't
count at all), and a rewritten `query()` loop that rebuilds the tool list
every round from current `GroundingContext`/discovery-budget state.

**Unit verification**: 31/31 -- tool-builder correctness (all four tools
round 1; correct enum construction for both single- and two-series
tools; empty-persisted-set omission; exhausted-discovery-budget
omission; base-schema immutability; independent builds share no mutable
state), discovery-budget semantics (parallel searches count once,
malformed/failed searches don't count, analytical calls don't count),
the explicit-ID fast path (unchanged, still works, still deterministically
blocks a genuinely unavailable explicit id), and -- critically -- a
direct proof that the deterministic gate still blocks a persisted:false
id *even when that id is absent from the dynamic schema*, with the
underlying service's call count staying zero: schema shaping is
optimization, never the security boundary.

**Live acceptance result: the primary gate (zero
`ToolRoundLimitExceededError` across 28 required live trials) was NOT
met.** 16 of 28 runs still exceeded `MAX_TOOL_ROUNDS=4`. Root cause,
traced precisely from safe per-round tool traces: in 58 of 97 (roughly
60%) round-2-or-later `get_observations`/`transform_series` calls, the
model supplied a `series_id` that was **not present** in that round's
offered `enum` -- it continued referencing ids from its memory of an
earlier `search_series` result rather than the narrower set actually
declared that round. This is the accepted, documented risk of a
non-`strict` JSON-schema `enum` under OpenAI function calling (`strict:
false` was an explicit, deliberate constraint for this design, to avoid
a larger schema-restructuring migration) -- it is a *strong hint*, not
an *enforced* constraint, and this model did not reliably honor it once
a plausible-looking id was already sitting in its own conversation
history. The discovery-round budget, by contrast, worked exactly as
designed in every case it was exercised (7 runs reached 2 successful
discovery rounds; `search_series` was correctly absent from the tool
list immediately afterward in all 7) -- the failure is isolated
specifically to the analytical-tool enum-narrowing mechanism, not to
`build_tool_schemas`/the discovery budget as a whole.

**Safety was not compromised even once.** Every one of the 58
enum-violating calls was still caught by `execute_tool`'s unchanged
deterministic gate and returned `series_not_persisted` -- the underlying
`EconomicDataService`/`AnalysisService` methods were never invoked for
any of them. This is precisely the property ADR-017 exists to guarantee
regardless of what the efficiency layer above it does or fails to do.

Per the explicit stop condition for this gate, no further architecture
change (e.g. a `strict: true` migration, which was explicitly out of
scope for this design) was attempted. The result is reported exactly as
measured, and the decision of whether to accept this efficiency
limitation, revert this layer, or approve a further change is left to
the next review -- not decided unilaterally here.

**Reusable engineering lesson.** A declared JSON-schema constraint
communicated to a tool-calling model is not the same kind of guarantee
as a constraint enforced in application code, even though both are
"structural" in the sense of not being prose -- `strict: false` function
calling treats a schema as strong guidance the model can and does
deviate from when its own prior context suggests a different value, at
a rate (roughly 60% here) far higher than "rare." Where a earlier
correction's assumption ("the model will very likely respect an enum
built from ids it just saw") was not empirically tested before being
adopted as the basis for an acceptance-gated design, this is the
direct, humbling result of actually measuring it instead of assuming
it -- and exactly why every correction in this project has been
verified against the real environment rather than accepted on
plausibility alone.

## Increment 010 — Deterministic Core Test Foundation

### Why this reset occurred

Three consecutive corrections to the autonomous AI tool-calling loop
(prompt wording, a deterministic execution gate, dynamic tool-schema
shaping) each fixed a real problem but exposed a deeper one: a
probabilistic component (the model) was load-bearing for product
*correctness and availability*, not just wording. The last of those
corrections measured a ~60% rate of the model ignoring its own offered
tool schema — conclusive evidence that no amount of prompt or schema
engineering was going to make an LLM behave like a deterministic
workflow engine. The product direction changed in response: Economic
Intelligence is an economic intelligence platform with optional AI
capabilities, not an AI agent that happens to access economic data.
Facts are sourced, calculations are deterministic, AI is interpretive —
and no probabilistic component may be required for the correctness,
reproducibility, availability, or integrity of the core engine.

### Autonomous AI orchestration is frozen

`AIService.query()`'s multi-round orchestration, `build_tool_schemas`'s
dynamic shaping, `MAX_TOOL_ROUNDS`, `MAX_DISCOVERY_ROUNDS`, and
model-driven tool sequencing are not being improved further. Nothing
about them was touched in this increment — confirmed directly: `git
diff` shows zero changes to `app/services/ai.py`, `app/services/ai_tools.py`,
or any other production file besides `pyproject.toml` (dev-only test
config). ADR-015 through ADR-018 and the corrections documented above
remain as accurate historical evidence of what was tried and what
failed; the deterministic execution-gate concepts from ADR-017 remain
correct and valuable, and are exactly the kind of code this new test
foundation exists to protect and eventually extend coverage to.

### Why repeatable tests now precede further architecture changes

Every verification across all nine increments and every correction in
this project, without exception, was an ad hoc script run once against
a live environment and never committed. That was adequate for
diagnosing a specific live-model behavior question, but it cannot
protect a *deterministic* engine's correctness over time — there was,
until this increment, no way to know in thirty seconds whether a change
anywhere in `app/domain/*` silently altered a calculation. That gap is
now closed for the two pure domain modules; extending the same
treatment to the rest of the deterministic core (repositories, services,
API routes) is the next work, not this increment's.

### Test boundaries

**In scope, and covered**: `app/domain/transformations.py`
(`absolute_change`, `percent_change`, `moving_average`) and
`app/domain/analysis.py` (`align_series`, `calculate_spread`,
`count_usable_pairs`, `pearson_correlation`) — golden-value tests with
independently hand-derived expected results (never obtained by calling
the implementation and asserting on its own output), determinism proofs
(same input + same operation = same output, asserted by calling each
function twice), input-non-mutation proofs (a pre-call snapshot compared
against the original argument after the call), and narrow contract
tests for the three Pydantic models these functions actually consume/
return (`Observation`, `TransformedObservation`, `ComparisonObservation`).
A small architectural-independence guard (`ast`-based import inspection,
no execution) asserts the domain layer imports nothing from `openai`,
`app.services.ai`/`app.services.ai_tools`, `app.clients.fred`,
`sqlalchemy`, `fastapi`, or `httpx` — and, more strictly, that every
import in the domain layer is either the standard library or
`app.models.*`.

**Explicitly out of scope for this increment** (deferred, not
forgotten): repository/integration tests against a real database, API
tests via `TestClient`, FRED-client tests, any AI/tool-loop test,
end-to-end tests. The audit that preceded this increment names these as
the next increments once this foundation is in place.

### Test command

```
pytest
```
or
```
python -m pytest
```
run from the repository root. Both now work identically — see the
discovered inconsistency below for why that wasn't true on the first
attempt.

### Final results

56 tests, 56 passed, 0 failed, ~0.06-0.09s per run, across four
consecutive full runs plus a fifth run instrumented to directly confirm
zero `openai`/`sqlalchemy`/`httpx`/`fastapi`/`psycopg` modules were
loaded at any point during test collection or execution — not inferred
from the absence of an error, but observed directly via `sys.modules`
before and after the run. Fully offline; no database, no FRED, no
OpenAI, confirmed both by code inspection (nothing in `tests/` imports
any of them) and by that direct runtime check.

**No production bug was discovered.** Every hand-derived expected value
(including every Pearson correlation figure, computed independently
from the textbook formula, never by running the code first) matched the
implementation's actual output on the first attempt, for every
documented edge case in both domain modules' own docstrings.

### Discovered inconsistency (infrastructure, not a domain-logic bug)

The project's own editable install (`pip install -e .` via
`__editable__.economic_intelligence-*.pth`) does not actually make
`import app` resolve outside of an incidental effect: `python -m
pytest`'s well-known behavior of adding the current working directory
to `sys.path` was masking this — confirmed directly by running `python
-c "import app"` from `/tmp` (fails) versus from the repo root (appears
to work, but only because cwd happens to equal the repo root, not
because the editable install itself resolves anything). The bare
`pytest` console-script entry point does not add cwd to `sys.path` and
failed outright with `ModuleNotFoundError: No module named 'app'` before
this was addressed. Fixed with the smallest available lever: a
`pythonpath = ["."]` entry under `[tool.pytest.ini_options]` in
`pyproject.toml` -- a pytest-only setting with zero effect on
application runtime behavior, deliberately chosen over touching
`[build-system]`/`[tool.setuptools.packages.find]` to actually repair
the editable install, which is a separate, pre-existing packaging issue
out of this increment's scope. Recorded here for whoever picks that up
later.

### Documentation/config changes this increment

`pyproject.toml`: added `[project.optional-dependencies] dev = ["pytest"]`
(dev-only, never a runtime dependency) and `[tool.pytest.ini_options]`
(`testpaths`, `pythonpath`). No `app/` file was changed. No ADR was
created — the architecture-freeze decision is already thoroughly
documented across ADR-015 through ADR-018 and the corrections above;
**a short, dedicated ADR formally recording "autonomous orchestration is
frozen, deterministic-core-first is the standing architecture" as its
own first-class decision is recommended for a future increment**, but
was not created here per this increment's own narrow scope.

## Increment 011 — Repository & Service Integration Test Foundation

### Objective

Extend permanent, repeatable test coverage one layer up from Increment
010's pure domain functions: `SeriesRepository`, `EconomicDataService`,
and `AnalysisService` composed against a real, isolated PostgreSQL
database -- proving PostgreSQL → Repository → Service → pure domain
functions actually compose correctly, which no domain-only unit test
can show on its own. No FastAPI, no OpenAI, no live FRED; API-level
testing is explicitly deferred to Increment 012.

### Packaging diagnosis

Increment 010 left the bare `pytest` entry point working only via a
`pythonpath = ["."]` workaround, without knowing why the project's own
editable install didn't make that unnecessary. Root-caused this
increment, precisely, not guessed: the generated
`__editable__.economic_intelligence-0.1.0.pth` file intermittently
carries the macOS `UF_HIDDEN` filesystem flag (confirmed directly via
`ls -lO`/`stat`), and CPython 3.12's `site.py` deliberately skips any
`.pth` file with that flag set (`site.py:176`, a real, documented
security-hardening check against silently-hidden `.pth`-based code
execution) -- silently disabling the editable-install import hook
entirely, independent of anything in `pyproject.toml`. Confirmed this is
**not** a `[tool.setuptools...]`/`[build-system]` misconfiguration:
clearing the flag (`chflags nohidden`) and even a full
`pip install -e . --force-reinstall` each fixed it only transiently --
the flag reappeared on the pre-existing file (and, separately, on the
freshly regenerated one) on a subsequent process launch, confirming this
is an environment-level artifact outside packaging-configuration
control, not a small, durably-fixable packaging bug. Per this
increment's own gate ("if the packaging problem requires something
beyond a small, clearly correct fix: stop"), no further remediation was
attempted (no repository restructuring, no venv relocation, no `site.py`
patching) -- the `pythonpath = ["."]` workaround from Increment 010
remains in place, its comment updated to record the real root cause
precisely for whoever revisits this later. `.venv/` is fully gitignored;
none of this diagnosis touched anything tracked by git.

### Test database strategy and safety guard

A real, separate, isolated PostgreSQL database
(`economic_intelligence_test`), on the same already-running local
Postgres 16 server as the development database, created directly
(`createdb`) using local trust authentication -- no credentials read,
displayed, or handled anywhere; `.env` was never opened. Deliberately
**not** SQLite: production behavior (upsert semantics, real `UNIQUE`
constraint enforcement, `OperationalError`/`IntegrityError` shapes) is
PostgreSQL-specific, and a substitute engine would prove the wrong
thing.

Isolation and safety, in `tests/integration/conftest.py`:

- Tests read their own `TEST_DATABASE_URL` environment variable --
  `app.core.config.settings.database_url` (the real app's configuration)
  is never read, imported for comparison, or touched by the integration
  suite's connection logic at all. Unset → tests skip (verified
  directly), never silently fall back to anything.
- **Deterministic safety guard**: the target database's name must
  contain "test" (case-insensitive) or setup refuses outright with a
  `RuntimeError`, before any migration or write is attempted --
  verified directly by actually pointing `TEST_DATABASE_URL` at the real
  `economic_intelligence` database and confirming the refusal fires
  before any connection is even opened for schema work.
- Existing Alembic migration(s) are applied to the isolated database via
  `alembic upgrade head` run as a subprocess with `DATABASE_URL`
  overridden only in that subprocess's environment -- alembic's normal,
  documented usage pattern, pointed at a different value; `alembic/env.py`
  and `app/core/config.py` are untouched. No new migration was created;
  the existing single migration was sufficient.
- Per-test isolation: each test runs inside one connection-level
  transaction, joined via SQLAlchemy's documented
  `join_transaction_mode="create_savepoint"` pattern, unconditionally
  rolled back afterward -- verified directly, not assumed: a smoke test
  proved a committed insert in one test was invisible in the very next
  test. This works even though the application's own code calls
  `session.commit()` internally (every service method does, via the
  pattern `app.db.session.session_scope` implements) because that inner
  commit only releases a SAVEPOINT, never the outer transaction this
  fixture controls.
- No connection string, password, or credential appears anywhere in any
  test file, fixture, or assertion message -- verified by design (the
  guard's own error message never echoes the URL) and by inspection.

Not ADR-worthy: this is ordinary test infrastructure (an isolated test
database and a naming-based safety guard), not a durable application
architecture decision with product-facing alternatives -- consistent
with the instruction not to create ADR clutter for it. Likewise the
packaging diagnosis above: an environment artifact, not an architecture
decision.

### Repository coverage

`SeriesRepository`, real PostgreSQL: series creation via `save_series`,
unknown-series lookup, observation persistence, idempotent upsert (a
second `save_series` call updates metadata and observation values in
place without duplicating rows -- proven via the real `UNIQUE` database
constraint, not assumed), the documented "never implicitly deletes
history absent from new data" rule, ascending/descending ordering,
start/end/combined date-range filtering, limit, offset, limit+offset
together, `total` reflecting the filtered (not whole-series) population
before pagination, preceding-observation retrieval (correct count,
ascending order, empty when none exists), and a direct before/after
proof that read methods change nothing.

### Service coverage

`EconomicDataService` (constructed with no `FREDClient` throughout --
confirmed directly, not just by absence of an import): persisted reads,
date filtering, pagination metadata, ordering, unknown-series and
invalid-date-range errors, all three transformations through the
service, and window validation (required for `moving_average`,
inapplicable to the other two).

**Boundary-context golden tests** (the important ones): persisted
Jan=100/Feb=110/Mar=121, requesting `percent_change` from `start_date=Feb`
returns Feb=10.0 (not null) and Mar=10.0, `absolute_change` returns
Feb=10.0/Mar=11.0, and `moving_average(window=2)` from `start_date=Mar`
returns Mar=115.5 -- every one hand-computed independently, every one
passed on the first run, proving Increment 005/007's "retrieve preceding
context, transform, trim" design is correctly wired end-to-end against
a real database. A dedicated test also confirms the borrowed context
observation (Jan) never appears in the returned response.

### AnalysisService and pipeline-composition coverage

`compare`: exact-date alignment (canonical Jan/Feb/Mar vs Jan/Mar/Apr
example), spread, correlation (reusing the hand-derived r=1.0 case),
null-value preservation on a matched date, start/end filtering, unknown
series (either side), invalid date range.

`pipeline`: raw/raw, raw/transformed, transformed/raw,
transformed/transformed, each of the three transformations individually,
`matching_pairs`/`usable_pairs`, correlation, and spread.

**The critical ordering test**: `test_transformation_happens_before_alignment_not_after`
constructs A=[Jan:100,Feb:110,Mar:121] and B=[Jan:10,Mar:30] (B
deliberately missing Feb) and applies `percent_change` to A. If
alignment happened first (wrong), A would be reduced to [Jan,Mar] before
transforming, making Mar's "previous" value Jan (100) and producing
21.0. The actual, correct, documented order (transform each series
against its own full history, then align) produces 10.0. **The result
was 10.0** -- passed on the first run, independently confirming
Increment 007's documented ordering guarantee holds against a real
database, not merely in the pure-domain unit tests. A companion test
confirms boundary context is resolved independently per series (not
shared/confused between the two sides) when both sides are transformed
and `start_date` truncates the range.

### Transaction and failure-behavior coverage

Exercises the real, unmodified `app.db.session.session_scope` (via a
`monkeypatch`-scoped, auto-reverting redirection of
`settings.database_url` to the isolated test database, clearing its two
`lru_cache`'d singletons before and after) rather than reimplementing
its logic: a successful block commits (verified via a second, separate
session proving durability, not just in-transaction visibility); an
exception inside the block rolls back, including a partial multi-step
write (a series row plus its observations) -- neither survives.
`app/db/session.py`'s transaction ownership was not redesigned or
touched.

Database-failure behavior at the service/repository layer (never
mapped to HTTP here -- that's Increment 012): an unreachable database
(a deliberately wrong port, no real credentials involved) raises
`OperationalError` unmapped, confirming the current, correct contract
that this layer does not catch it. The real `UNIQUE(economic_series_id,
observation_date)` constraint was proven enforced by PostgreSQL itself
(an `IntegrityError` on a raw duplicate insert bypassing `save_series`'s
own upsert-checking), not merely assumed from the migration's DDL.

### Test commands

```
pytest                          # everything (pure + integration)
pytest -m "not integration"     # pure domain tests only -- no TEST_DATABASE_URL needed
pytest -m integration           # integration tests only -- requires TEST_DATABASE_URL
```

### Final results

121 total tests (56 pure from Increment 010, unchanged and still
passing, + 65 new integration tests), 121 passed, 0 failed, ~2 seconds.
Verified repeatable across multiple full-suite runs, a reversed test-file
execution order, and each integration file run standalone -- identical
pass counts every time, confirming the transaction-rollback isolation
actually delivers order-independence rather than merely intending it.

**No production bug was discovered.** Every hand-derived expected value,
including the ordering-sensitive pipeline composition test, matched the
real implementation's actual behavior against real PostgreSQL on the
first attempt.

### Deferred to Increment 012

FastAPI `TestClient`-level tests, HTTP status-code mapping for every
failure branch, request/response contract validation at the API
boundary, and anything involving the AI orchestration layer (still
frozen, still untouched).

### Documentation/config changes this increment

`pyproject.toml`: registered the `integration` pytest marker; updated
the `pythonpath` comment to record the real, root-caused packaging
finding above (no functional change to that workaround). No `app/` file
was changed. No ADR created -- neither the test-database safety
mechanism nor the packaging diagnosis rises to a durable
architecture-decision-with-alternatives; both are testing/environment
infrastructure.

### Confirmations

AI orchestration untouched: `git diff --stat` shows zero new changes to
`app/services/ai.py`/`app/services/ai_tools.py` from this increment (the
diffs present predate it). No production database was mutated: every
integration test ran inside a rolled-back transaction against
`economic_intelligence_test`, never `economic_intelligence`; the
transaction/safety tests that exercise the real `session_scope` were
also redirected to the isolated test database for their duration only.

## Increment 012 — Deterministic HTTP API Contract & Failure Tests

### Objective

The last permanent layer of the deterministic reset's test foundation:
HTTP request → FastAPI route → service → repository → domain → typed
response, for every deterministic route. No FastAPI HTTP status mapping
had been locked down by a repeatable test before this increment --
Increment 011 deliberately stopped one layer below it.

### Route inventory (confirmed against actual code, not memory)

| Method & path | Request | Response model | Service | External dep | Success | Exceptions handled |
|---|---|---|---|---|---|---|
| `GET /health` | none | `{"status": "ok"}` | none | none | 200 | none (no try/except at all) |
| `GET /api/v1/series/{id}` | path param | `SeriesResponse` | `EconomicDataService.get_series` | FRED | 200 | `FREDSeriesNotFoundError`→404, `FREDAuthError`→503, `FREDTimeoutError`→504, `FREDUpstreamError`→502 |
| `POST /api/v1/series/{id}/sync` | path param | `SeriesResponse` | `EconomicDataService.sync_series` | FRED + DB | 200 | above FRED mappings + `IntegrityError`→409, `OperationalError`→503, `SQLAlchemyError`→500 |
| `GET /api/v1/series/{id}/observations` | query: start_date, end_date, limit(1-1000), offset(≥0), order(asc/desc) | `SeriesObservationsResponse` | `EconomicDataService.get_observations` | DB only | 200 | `InvalidDateRangeError`→400, `SeriesNotFoundError`→404, `OperationalError`→503, `SQLAlchemyError`→500 |
| `GET /api/v1/series/{id}/transform` | query: transformation(required), start_date, end_date, window(2-365) | `SeriesTransformResponse` | `EconomicDataService.get_transformed_observations` | DB only | 200 | above + `InvalidWindowError`→400 |
| `GET /api/v1/analysis/compare` | query: series_a, series_b, analysis(required), start_date, end_date | `SeriesComparisonResponse` | `AnalysisService.compare` | DB only | 200 | `InvalidDateRangeError`→400, `SeriesNotFoundError`→404, `OperationalError`→503, `SQLAlchemyError`→500 |
| `POST /api/v1/analysis/pipeline` | body: `PipelineRequest` (extra="forbid", nested) | `PipelineResponse` | `AnalysisService.pipeline` | DB only | 200 | above + `InvalidWindowError`→400 |
| `POST /api/v1/ai/query` | body: message | `AIQueryResponse` | `AIService.query` | OpenAI + DB | 200 | `AIProviderUnavailableError`→503, `ToolRoundLimitExceededError`→503; frozen, not behaviorally tested here |

Confirmed HTTP failure taxonomy actually in use: **200, 400, 404, 409
(sync only), 422 (FastAPI/Pydantic, automatic), 500, 502, 503, 504** --
all eight exercised by this increment; no status was manufactured for
symmetry that the code doesn't actually use.

### Test infrastructure: one shared root conftest, two suite-specific ones

`tests/integration/conftest.py` (Increment 011) was moved, not
duplicated, to `tests/conftest.py`: pytest fixture visibility flows
downward from a conftest to its subdirectories, never sideways between
siblings, and `tests/api/` needed the exact same `test_database_url`
safety guard, migration setup, and `db_session` fixture `tests/
integration/` already had. `pytest_collection_modifyitems` there now
auto-marks tests under either subdirectory (`integration`/`api`)
generically. Re-ran all 121 pre-existing tests immediately after this
move and confirmed identical results before writing anything new.

`tests/api/conftest.py` adds what's unique to HTTP-level testing:

- `client`: `fastapi.testclient.TestClient(app)` -- the real ASGI app,
  in-process, no real server, no browser tooling.
- `_redirect_database` (autouse): the real, unmodified route → `session_scope()`
  path is redirected to the isolated test database for each test's
  duration only (`monkeypatch` + explicit `lru_cache.cache_clear()` on
  both `app/db/session.py` singletons, before and after) -- the same
  technique Increment 011's transaction tests already used.
- `seed_session`: a deliberately **different** isolation strategy than
  `tests/conftest.py`'s rollback-based `db_session`, for a real reason:
  an HTTP request handled by the actual FastAPI route opens its own,
  separate PostgreSQL connection. A second connection cannot see a
  first connection's SAVEPOINT-only "commit" -- rollback isolation is
  structurally the wrong tool here. `seed_session` commits for real and
  cleans up via `TRUNCATE ... RESTART IDENTITY CASCADE` after each test
  instead -- exactly the "otherwise use explicit safe cleanup against
  the TEST database only" alternative named for this situation, not a
  second competing database architecture.
- `fred_configured`: a synthetic, non-secret sentinel string for
  `settings.fred_api_key` (never a real key) so FRED-backed routes pass
  their configuration check while every actual `FREDClient` method is
  mocked per-test at the class level -- no live network call anywhere
  in this suite.

### FRED mocking strategy

`unittest.mock.patch.object(FREDClient, "<method>", ...)` -- the
narrowest sensible external boundary named in the brief. Never mocks
`EconomicDataService`/internal deterministic logic for FRED-success
paths; the real route → service → (mocked) FREDClient path runs in
full. Service-level mocks (`EconomicDataService`/`AnalysisService`
methods) are used only for the handful of branches that can't be
naturally reached any other way -- `IntegrityError`/generic
`SQLAlchemyError` mapping, which normal use doesn't trigger.

### Test results by area

- **Health** (4 tests): 200 + exact body; works with no OpenAI key, no
  DB connectivity (a deliberately unreachable `DATABASE_URL`), no FRED
  key -- confirming `/health` truly touches none of them, as
  `app/main.py` already showed by inspection.
- **Series metadata** (9 tests): success with exact response contract
  (including FRED's newest-first→chronological reordering and `"."`→
  `null` value parsing), missing-config 503, all four typed FRED
  exceptions mapped correctly, malformed-provider-response→502, and an
  explicit no-stack-trace/no-secret check.
- **Sync** (10 tests): successful sync verified against real persisted
  rows (a separate connection, not just the response body), idempotent
  repeat (no duplicate series or observation rows), value-update-in-
  place on a changed observation, all FRED mappings, plus
  `IntegrityError`→409, `OperationalError`→503, generic
  `SQLAlchemyError`→500 (service-level mocks, real Postgres untouched).
- **Observations** (16 tests): full pagination/ordering/filtering
  matrix, an empty-range-on-existing-series 200 (not a 404), read-path
  non-mutation, repeated-request determinism, and the validation
  matrix: limit/offset/order/date-shape violations → 422,
  **start_date > end_date → 400** -- the distinction this increment
  exists to lock down permanently, confirmed structurally different
  from the 422 cases (each date is independently valid; only their
  relationship is a semantic, service-level rule).
- **Transform** (11 tests): all three transformations, exact metadata
  contract, unknown-series 404, `InvalidDateRangeError`/`InvalidWindowError`
  → 400 (both directions: missing window for `moving_average`, window
  supplied for an inapplicable type), an unrecognized transformation
  value / out-of-bounds window → 422. **The boundary-context golden
  test now runs through the full HTTP path**: Jan=100/Feb=110/Mar=121,
  `start_date=2024-02-01` → Feb=10.0 (not null), Jan correctly trimmed
  from the response -- confirming Increment 011's service-level proof
  holds all the way to the public contract.
- **Compare** (11 tests): alignment, spread, correlation, null
  preservation, date filtering, both unknown-series directions, invalid
  range → 400, invalid `analysis` value / missing required query param
  → 422.
- **Pipeline** (24 tests) -- the richest contract, and the largest
  section: every raw/transformed combination, all three transformations
  individually, aligned/spread/correlation, and **the decisive
  transformation-before-alignment ordering test carried through the
  full HTTP path** (A=[Jan:100,Feb:110,Mar:121], B=[Jan:10,Mar:30]
  deliberately missing Feb; correct answer 10.0, wrong answer 21.0 --
  **result: 10.0**, confirmed via `POST /api/v1/analysis/pipeline`
  itself, not just the service layer). Fail-closed validation matrix:
  unknown top-level/series-spec/transformation field → 422 (the
  `extra="forbid"` hardening from Increment 009/010's corrections,
  now proven at the HTTP boundary too), invalid transformation/analysis
  type → 422, out-of-bounds window → 422, missing-required-window /
  inapplicable-window-supplied → 400, malformed date → 422, bad date
  relationship → 400, unknown series → 404.
- **Cross-cutting failure mapping** (18 tests): `OperationalError`→503
  and generic `SQLAlchemyError`→500 forced at the service boundary for
  all four PostgreSQL-only routes (observations, transform, compare,
  pipeline); two dedicated safe-error-body tests using synthetic
  marker strings ("password=hunter2", "secret_table", etc.) embedded in
  a mocked exception, confirmed absent from every response body, plus a
  lowercase scan for stack-trace/file-path signatures.
- **AI independence** (7 tests): `/health`, observations, transform,
  compare, and pipeline all verified working with `OPENAI_API_KEY`
  unset; one narrow, explicitly-scoped `/ai/query` test confirms a
  clean 503 when unconfigured (no live call, no round behavior, no
  schema-compliance testing -- exactly the boundary the brief drew); a
  static `ast`-based guard confirms `app/api/series.py`/`app/api/analysis.py`
  import neither `openai` nor any `app.services.ai*` module.
- **FRED independence of persisted analytics** (1 test, deliberately
  strong): patches `FREDClient.__init__` itself to raise immediately if
  ever constructed, then successfully calls observations, transform,
  compare, and pipeline through the real HTTP client -- if any of those
  four routes' code path ever tried to construct a `FREDClient`, this
  test would fail with that exact assertion, not merely "look" like it
  passed.

### Test commands

```
pytest                                  # everything (pure + integration + api)
pytest -m "not integration and not api" # pure domain tests only -- no TEST_DATABASE_URL needed
pytest -m integration                   # repository/service integration tests
pytest -m api                           # HTTP API tests
```
Both `integration` and `api` require `TEST_DATABASE_URL` (API routes
read/write through the real `session_scope`, same as direct service
calls).

### Final results

226 total tests (56 pure + 65 integration, both unchanged from
Increments 010/011, + 105 new API tests), 226 passed, 0 failed, ~4-5
seconds. Verified repeatable across multiple full-suite runs, a
reversed API test-file execution order, and each API file run
standalone -- identical results every time.

**No production bug was discovered.** Every documented status-code
mapping, every hand-derived golden value (including the HTTP-level
transformation-before-alignment test), and every validation-boundary
case matched the real, unmodified route code's actual behavior on the
first attempt.

### Deferred (unchanged from the brief)

Any behavioral test of the autonomous AI orchestration loop (round
efficiency, tool-schema compliance, live OpenAI calls) -- that path
remains frozen, untouched, and out of this test foundation's scope by
design, not by omission.

### Documentation/config changes this increment

`pyproject.toml`: registered the `api` marker alongside `integration`.
`tests/integration/conftest.py` removed (content relocated, not
duplicated, to the new `tests/conftest.py`). No `app/` file was
changed. No ADR created -- ordinary API testing infrastructure, no
durable architecture decision with product-facing alternatives.
Architecture docs not updated -- no real architecture change occurred.

### Confirmations

AI orchestration untouched: `git diff --stat app/services/ai.py
app/services/ai_tools.py` shows only pre-existing diffs from before this
increment. No live OpenAI or FRED call: every FRED interaction in this
suite is a `patch.object(FREDClient, ...)` mock; the one AI test
verifies a configuration-absent 503 and calls no OpenAI SDK method.
No production database mutation: every API test's request handling was
redirected to `economic_intelligence_test`; `economic_intelligence` was
never connected to.

## Increment 012.5 — Working Tree Cleanup & Autonomous AI Rollback

Not a feature increment: a deliberate cleanup, restoring the working
tree to a clean, coherent state before Increment 013. This entry does
not rewrite anything above it -- the full Increment 009 narrative, all
three correction attempts, and ADR-017/018's complete empirical results
remain exactly as recorded. What follows is what changed *after* that
history, in response to it.

### Why

Increment 009 and its three corrective follow-ups were built and
verified entirely in the working tree, never committed. By the time
Increment 012 landed (the deterministic HTTP API test foundation), that
uncommitted batch mixed three genuinely different kinds of change in
the same diff: real, deterministic, independently-useful discovery
capability; real, valuable safety/validation hardening; and an
autonomous multi-round AI tool-orchestration experiment that was tried
three separate times (prompt-only guidance, a deterministic execution
gate, dynamic tool-schema shaping) and never passed its own acceptance
gate -- the last attempt's own measured result was a ~60% rate of the
model ignoring the schema constraint it was just given. Leaving that
failed experiment sitting in the tree as if it were pending, undecided
work was no longer honest about its status: it had already failed,
repeatedly and specifically, and continuing to carry it forward risked
it being mistaken for active canonical architecture.

### What was reverted

`app/services/ai.py`, `app/services/ai_tools.py`, and `app/models/ai.py`
were restored via `git checkout HEAD --` to their last-committed state
(Increment 008, commit `aff7ba4`) -- the exactly-three-tool
(`get_observations`/`transform_series`/`analyze_series`), no-discovery,
no-grounding AI path this project shipped before Increment 009 ever
touched it. This removes, as active code: the `search_series` tool and
its wiring; `GroundingContext` and `execute_tool`'s grounding/persisted-
execution gate; `build_tool_schemas`, `MAX_DISCOVERY_ROUNDS`, and
`_round_had_successful_search`; and `SearchSeriesArgs` plus the
`extra="forbid"` hardening that existed only to support the AI tool
loop. No attempt was made to fix, redesign, or improve any of it --
consistent with the explicit instruction for this cleanup, and with the
conclusion three separate corrections had already reached.

`docs/architecture/current-architecture.md` and
`docs/architecture/request-flows.md` were reverted the same way, for
the same reason: both had accumulated hundreds of lines describing the
reverted discovery/grounding/dynamic-schema system as active, current
architecture. Both now accurately describe the system as it actually
runs (three AI tools, no discovery, exactly as Increment 008 left it).

Verified directly, not assumed: a repo-wide search for every
orchestration-specific symbol (`MAX_DISCOVERY_ROUNDS`,
`build_tool_schemas`, `known_persisted_ids`, `GroundingContext`,
`_round_had_successful_search`, `register_discovery`,
`resolve_persisted`) found them nowhere outside the two files being
reverted -- confirming none of the 226 committed tests from Increments
010-012 depend on any of it, and the revert was safe by construction.
Running the full committed suite immediately afterward confirmed this:
226/226 passed, unchanged.

### What was preserved

**Deterministic discovery capability** (Category 1: independently
useful, zero AI dependency, verified by direct import/grep inspection):
`app/clients/fred.py`'s `FREDClient.search_series` (catalog metadata
only, never observations), `app/repositories/series_repository.py`'s
`SeriesRepository.search_series` (local substring match, deterministic
ordering), and the two new modules `app/models/discovery.py`/
`app/services/discovery.py` (`SeriesCandidate`, `SeriesSearchResponse`,
`SeriesDiscoveryService`) -- none of the four references `app.services.ai`,
`app.services.ai_tools`, or `openai` anywhere. This capability is
currently orphaned (nothing wires it into anything reachable -- no HTTP
route, no AI tool) but intact and correct, confirmed by four new small,
focused, offline tests (`tests/integration/test_discovery_service.py`)
exercising local-only search (`fred_client=None`) directly: find by id,
find by title substring, no-match returns an empty list (not an error),
and a non-mutation proof. Exposing this as a direct HTTP endpoint is
Increment 013's job, not this cleanup's.

**Durable validation hardening, independent of the failed orchestration**
(Category 2): `app/models/analysis.py`'s `extra="forbid"` on
`TransformationSpec`/`PipelineSeriesSpec`/`PipelineRequest` was kept
as-is. Verified precisely why this is safe and correct to keep, not an
oversight: `PipelineRequest` is the real request body for the
deterministic `POST /analysis/pipeline` HTTP endpoint (reused by the AI
`analyze_series` tool since Increment 008, predating Increment 009's
work entirely), and this exact hardening is already load-bearing for
Increment 012's own committed HTTP tests
(`test_unknown_top_level_field_returns_422` and its siblings in
`tests/api/test_analysis_api.py`). Reverting this file would have
broken currently-passing committed tests for no benefit -- confirmed by
inspecting its diff line-by-line and finding it contains only
`extra="forbid"` additions and docstring updates, nothing
orchestration-specific. One docstring correction was made for accuracy
(a stray "(Increment 009)" attribution for `analyze_series` reusing
`PipelineRequest`, corrected to "(Increment 008)", since that reuse
predates Increment 009 -- confirmed directly against the Increment
008 commit).

By contrast, `app/models/ai.py`'s `extra="forbid"` additions
(`GetObservationsArgs`/`TransformSeriesArgs`) were reverted along with
the rest of that file: confirmed by grep that neither model is used
anywhere outside `app/services/ai_tools.py` (the deterministic HTTP
routes use plain FastAPI `Query(...)` parameters, never these models),
so nothing dual-use was lost.

### ADR disposition

None of ADR-015/016/017/018 were committed before this cleanup (all
four were still untracked working-tree files), so editing their status
lines is not a rewrite of committed history -- the append-only
constraint applies to this journal, which is committed, not to them.

- **ADR-015** (verified-series grounding): kept, status amended to
  note the implementation is reverted while the decision/principle is
  preserved for future re-application.
- **ADR-016** (no AI-triggered ingestion): kept, status amended to
  "standing principle, currently inapplicable" -- there is no
  AI-driven discovery left for it to constrain right now, but the rule
  should govern that design again from the start whenever there is.
- **ADR-017** (deterministic analytical execution eligibility): kept,
  status amended the same way as ADR-015 -- this is the one piece of
  the Increment 009 era most worth re-applying essentially unchanged
  whenever AI-triggered execution returns, given its 100%-verified
  enforcement record.
- **ADR-018** (dynamic tool availability): kept, but its Status is now
  explicitly **SUPERSEDED — FAILED ACCEPTANCE GATE**, with the
  decisive empirical finding (the ~60% schema-violation rate) restated
  at the top of the document, not just buried in its Consequences
  section. The full original document is preserved unchanged below
  that notice.

### Tests

226 pre-existing tests: unchanged, all still passing. 4 new tests
(`tests/integration/test_discovery_service.py`) added to prove the
preserved discovery capability wasn't left silently broken by the
cleanup -- no live FRED, no live OpenAI, real isolated PostgreSQL test
database (same fixtures Increment 011 already established). Full
suite: **230/230 passing** after this cleanup.

### What remains true

The AI path is back to exactly what Increment 008 shipped and nothing
more: three tools, no discovery, no grounding, no dynamic anything. It
is not part of the canonical, currently-recommended product
architecture (see the architecture reset audit) -- it remains mounted
and reachable at `/api/v1/ai/query` (untouched, unimproved, not
re-evaluated by this cleanup) but is not where product development
attention belongs until the deterministic engine (Increments 010-012,
plus whatever Increment 013 and beyond add) is further along. Future AI
work should start from ADR-015/017's preserved principles and the
architecture reset audit's bounded-intent-extraction design, not from
reviving anything reverted here.

## Increment 013 — Deterministic Series Discovery API

### Product problem

A user who doesn't already know a FRED series identifier had no
deterministic way to find one. Every other endpoint in this project
requires a `series_id` up front (`GET /{series_id}`, `.../observations`,
`.../transform`, `/analysis/compare`, `/analysis/pipeline`) -- useful
only to someone who already knows what they're looking for. Increment
012.5 preserved a fully deterministic discovery capability
(`SeriesDiscoveryService` and friends) built during Increment 009, but
it was reachable only through the AI tool loop, which is frozen and not
canonical. This increment exposes that same, unmodified capability
directly, so discovery works with OpenAI completely unavailable --
exactly the standing principle: facts are sourced, calculations are
deterministic, AI is interpretive, and the product must remain useful
without AI.

### Why direct discovery matters now

Without this, "the product is useful without AI" was only true for
someone who already had a series ID in hand. This closes that gap using
code that already existed, was already correct, and had already been
proven independent of both AI and any external write capability --
Increment 013 is deliberately *exposure*, not new logic: not one line
of `SeriesDiscoveryService`/`SeriesRepository.search_series`/
`FREDClient.search_series`/the discovery models changed.

### Route contract

`GET /api/v1/series/search?q=<concept>&limit=<1-50, default 10>`,
declared **before** `GET /{series_id}` in `app/api/series.py` so `search`
is never captured as a `series_id` path parameter -- verified directly
(not just by declaration order) via a live request with
`FREDClient.get_series_info` mocked to raise if called and
`FREDClient.search_series` mocked to succeed: the response came back as
a clean discovery result, and `get_series_info` was never invoked.

Response: the existing `SeriesSearchResponse` model, unmodified --
`query`, `candidates` (each with `series_id`, `title`, `units`,
`frequency`, `seasonal_adjustment`, `observation_start`,
`observation_end`, `popularity`, `persisted`, `discovery_source`), and
`external_search_available`. No new field was added for aesthetics --
`discovery_source` (`"local"`/`"fred"`/`"local_and_fred"`) already *is*
the provenance field the brief asked to preserve-if-present, so nothing
further was needed.

`q` is required, trimmed, must contain non-whitespace text after
trimming, and capped at 200 characters; `limit` defaults to 10, bounded
1-50. The 400-vs-422 split follows this project's existing convention
exactly: FastAPI/Pydantic catches missing `q`, empty `q`, overlong `q`,
and out-of-bounds/malformed `limit` (422, structural); a
whitespace-only `q` is structurally valid (a non-empty string within
bounds) but semantically empty once trimmed -- caught explicitly in the
route body and mapped to 400, the same pattern `InvalidDateRangeError`
etc. already use everywhere else in this project.

### Deterministic ranking semantics (unchanged, now proven at HTTP level)

Three plain, explainable comparison keys, no ML/embedding/LLM-generated
relevance score: an exact `series_id` match always surfaces first;
among non-exact matches, persisted candidates rank ahead of FRED-only
ones (a tiebreaker, not a claim of semantic correctness); within each
tier, FRED's own `search_rank` order is preserved. Verified directly at
the HTTP layer with a mocked FRED response and a persisted local row
deliberately ordered last in the mock list -- the exact match still
came first, `limit` was applied *after* the merge (not before, which
would have silently dropped a real match), and identical requests
against identical data produced byte-identical responses.

### Local/FRED merge semantics

A series present in both sources returns once, `persisted=true`, with
FRED's richer metadata (frequency, seasonal adjustment, observation
range, popularity) layered onto the local match -- `discovery_source`
becomes `"local_and_fred"`. Verified explicitly: persisted status is
never downgraded by an external search result, and a series known only
locally or only via FRED reports `persisted=true`/`false` respectively,
correctly.

### Degradation behavior (unchanged, now proven at HTTP level)

FRED timeout, auth failure, or upstream failure all degrade the same
way: `external_search_available=false`, local results still returned,
`200` -- never an error response, confirmed for all three exception
types plus a fourth case (`FRED_API_KEY` simply unconfigured). The one
edge case worth naming explicitly: local results empty **and** FRED
search fails -- the existing service contract (unchanged, just newly
locked down by a permanent test) returns `200` with `candidates: []`
and `external_search_available: false`, never raises. This was
deliberately preserved rather than "fixed" into an error response --
"no matches were confidently found" and "something went wrong" are
different situations, and this project's read paths consistently treat
an honestly empty result as success, not failure.

### No-ingestion contract (ADR-016, now directly testable)

A `persisted=false` candidate found via FRED is never written to
`economic_series`/`economic_observations` -- verified two ways: a
before/after row-count-and-value snapshot around a search request
(identical), and an explicit check that a FRED-only candidate's
`series_id` does not exist in `economic_series` immediately after being
returned in a search response. Searching for a series and syncing it
(`POST /{series_id}/sync`, unchanged, unrelated) remain two entirely
separate actions.

### AI and analytics independence

Discovery works identically with `OPENAI_API_KEY` unset (locked down
directly). A static guard confirms `app/services/discovery.py` and
`app/models/discovery.py` import neither `openai`/`app.services.ai*` nor
`app.services.analysis`/`app.domain.*` -- discovery finds series
metadata only, never touches comparison, transformation, or correlation
math. A dynamic guard confirms the same for the live request path: a
search with `EconomicDataService.get_transformed_observations` patched
to raise if called still returns `200`.

### Tests and results

46 new tests: 36 in `tests/api/test_series_search_api.py` (success
paths including merge/dedup/persisted-semantics/ranking/limit,
degraded-external-search including the no-local-and-FRED-fails case,
validation, error-safety, route-collision, AI/analytics independence,
non-mutation, no-ingestion, and metadata normalization including the
one genuinely-undefined case -- `observation_start`/`observation_end`
are plain, unvalidated strings, so a malformed value from FRED passes
through as-is rather than being rejected, documented as current
behavior rather than assumed) + 10 in
`tests/integration/test_discovery_service.py` (merge/dedup/ranking-
stability/degradation proven directly against the service, below HTTP,
per the brief's own guidance not to duplicate what's already proven at
the API layer).

One existing Increment 011 test needed a narrow, deliberate adjustment,
not a weakening: `TestAIAndNetworkIndependence`'s blanket "no file in
tests/integration/ imports FREDClient/httpx" guard was written before
any discovery capability existed in that suite and is now split into
two separate checks -- AI (`openai`/`app.services.ai`) remains forbidden
in every file in the directory, without exception; the FRED/httpx
restriction remains in force for every file except
`test_discovery_service.py`, which legitimately imports `FREDClient`
only to mock its `search_series` method, exactly as this increment's
own brief required ("mock at the FREDClient boundary"). The underlying
guarantee -- no live network call anywhere in this suite -- is
unchanged and still fully enforced; only the previous, accidentally-
too-broad implementation of one static check was corrected.

Full suite: **273/273 passing** (230 pre-existing + 43 new), repeatable
across multiple full runs, and confirmed order-independent (each new
file also runs correctly standalone).

### Tradeoffs

`observation_start`/`observation_end` remain unvalidated strings passed
through verbatim from FRED -- a real, minor gap (a malformed provider
value would reach a client as-is) that predates this increment and
wasn't introduced or fixed by it; noted, not addressed, since fixing it
was not this increment's job and the brief was explicit not to "fix"
discovered behavior without stopping to report first. No production bug
was found, so no stop was warranted -- this is a documented, pre-
existing characteristic, not a defect discovered mid-implementation.

## Inflation Momentum Methodology Study (research, not a numbered increment)

Not Increment #14 — an explicit research increment, kept out of the
numbered production sequence on purpose. Its purpose: empirically
evaluate candidate deterministic inflation-momentum methodologies
*before* freezing a canonical "Inflation Monitor" specification, rather
than picking a formula first and discovering its behavioral properties
only after it ships. Methodology choice has real, durable product
consequences (which candidate becomes the thing users see as "cooling"
or "heating"); this project's own standing practice is to verify
against reality before committing to an architectural or product
decision, and a classification formula is exactly that kind of
decision.

### Why methodology first, implementation later

The same discipline this project applied to AI orchestration (diagnose
and measure before building, per the earlier architecture-reset
increments) applies here: build the smallest amount of code needed to
*measure* candidate behavior against real historical data, look at what
actually happens, and only then decide what to freeze as canonical. No
methodology was selected in this study, deliberately — the codebase's
production `app/` package was not touched at all.

### Candidate families tested

Recent-vs-Trailing (3M vs 12M, four neutral-band deltas), Dual
Confirmation (3M AND 6M vs 12M), Ordered Momentum (strict 3M<6M<12M or
reverse, plus one explicitly-separated banded variant), and Change in
Recent Momentum (delta of 3M annualized, evaluated for churn only,
never proposed as a standalone state) — each run independently against
Core PCE, Core CPI, Headline PCE, and Headline CPI.

### Data basis and current-vintage limitation

Full available history for all four canonical series (Headline/Core
CPI back to 1947/1957, Headline/Core PCE back to 1959, all through
mid-2026) fetched via the existing, unmodified production `FREDClient`
directly — reused, not duplicated — and cached as research-local JSON,
never written to the production PostgreSQL database, keeping the
research harness fully isolated from production runtime behavior. This
is explicitly a **current-vintage historical reconstruction**: FRED
does not preserve pre-revision vintages through this application today,
so this study cannot and does not claim to show what an analyst would
have known in real time at any past date. Building vintage-aware
(ALFRED-style) persistence is out of scope here.

### Reproducibility strategy

Dates sorted explicitly wherever consumed; missing values propagate as
`None`, never imputed or approximated; calculation kept fully separate
from display rounding; the entire study, run twice against the same
cached data, produces byte-identical output files — verified both
manually (`diff -rq`) and by an automated end-to-end test. 46 new,
offline, deterministic tests (`tests/research/test_inflation_momentum.py`)
cover the transformation math (hand-checked against the formula's own
definition, not against the function under test), every candidate's
boundary and adversarial behavior, the metrics definitions, common-
period alignment, and an architectural guard proving `app/` never
imports `research/` (and, empirically, that it currently does not).

### Key empirical findings

- Candidate A's (Recent vs Trailing) state-change rate is **not
  monotonic** in neutral-band width — it *increases* from delta=0.00 to
  delta=0.25 before falling at delta=0.50, because a mid-size band adds
  a third reachable state without yet being wide enough to meaningfully
  reduce boundary-crossing. "Wider band = more stable" is not a safe
  assumption for this candidate family without checking, which this
  study did.
- Dual Confirmation (Candidate B) and Ordered Momentum's banded variant
  both cut churn roughly in half relative to Candidate A at a matching
  delta, and Dual Confirmation specifically cuts *cross-measure
  opposite-state disagreement* even more (e.g. Core PCE vs Core CPI
  opposite-state: 7.4% under Candidate A, 1.3% under Candidate B).
- All four canonical series agree on the same state simultaneously in
  only ~30% of fully-classified months — four-way consensus is the
  exception, not the rule.
- The specific hierarchy-divergence pattern this study was asked to
  quantify (Core PCE and Core CPI agreeing with each other while
  Headline PCE and Headline CPI agree with each other on the *opposite*
  state) occurs in 3.4% of common months — real and non-trivial, though
  not the dominant case.
- Candidate A applied to Core PCE (delta=0.25) tracks independently-
  documented macroeconomic history well across five widely-known
  episodes (the late-1970s oil shock, Volcker disinflation, the
  2021-2022 surge, the 2022-2024 disinflation, and the COVID collapse)
  without any parameter having been chosen to produce that match —
  the strongest available evidence the methodology family measures
  something real.
- A real, current data gap exists at 2025-10-01 in both CPI series
  (FRED's own data, not a bug in this study) — an unplanned, live
  instance of exactly the "missing intermediate observation" adversarial
  case the brief asked to be tested, handled correctly (propagates as
  `None`, never imputed).
- Candidate D (change in 3M momentum) churns near 50/50 almost every
  month as a standalone signal, confirming it is not viable as a
  canonical state on its own; whether it has value as a secondary
  confirmation layer on top of another candidate was not tested.

### Rejected/weak approaches

Nothing was rejected outright — the study's mandate was explicitly not
to select a winner. The weakest empirical showing was Candidate D used
standalone (see above) and Candidate B at wide deltas, where the large
majority of months fall into MIXED_OR_STABLE and very few are
classified as COOLING/HEATING at all — a real responsiveness cost for
its stability gain.

### Unresolved methodology decisions

Which candidate/delta becomes canonical; whether MIXED_OR_STABLE should
ever be split into separate MIXED and STABLE concepts; whether the
four-series hierarchy (vs. some other structure) is the right one,
given how infrequently all four agree; what delta/band value is
"right" given Candidate A's non-monotonic response; whether Candidate D
has value as a secondary confirmation signal; how the current-vintage
limitation should be surfaced to end users; and whether a full
responsiveness/turn-persistence episode table is worth building before
finalizing. Full detail: `research/inflation_momentum/STUDY_RESULTS.md`'s
"Questions Requiring Human Decision" section.

### Reusable engineering/economic lessons

- **Level and momentum are genuinely different questions** and this
  study's target-gap analysis (Headline PCE YoY vs. the 2% objective,
  reported directly in percentage points, never bucketed into arbitrary
  categorical bands) keeps them structurally separate rather than
  collapsing both into one score — exactly the trap the research brief
  warned against.
- **A parameter's effect on a metric is not always monotonic** —
  assuming "more of X produces more of Y" without measuring it directly
  (as with Candidate A's band width vs. churn) is exactly the kind of
  assumption this project's standing practice of verifying against
  reality exists to catch.
- **Isolating a research harness from production runtime behavior is a
  real, separate design decision from "reuse existing code"** — reusing
  `FREDClient` directly (not duplicating its HTTP/auth/error logic)
  while deliberately never writing fetched data into the production
  database were two independent choices, both necessary, and neither
  implied by the other.

## Inflation Momentum Finalist Analysis (research, not a numbered increment)

Extends the Inflation Momentum Methodology Study above to resolve the
specific human-decision questions it left open, narrowed to a finalist
set: Candidate A (delta=0.25), Candidate B (deltas 0.10/0.25/0.50), and
Candidate C (band=0.25). Candidate D was excluded as a finalist (the
prior study found it churns near-continuously as a standalone signal).
No methodology was selected; no ADR was created. Full report:
`research/inflation_momentum/FINALIST_ANALYSIS.md`. Orchestration:
`research/inflation_momentum/finalist_study.py` (new file, purely
additive — re-running the original `study.py` after this file exists
still produces byte-identical output to before, verified directly).

### What was added

- `classify_candidate_b_explicit()` in `methodology.py`: an explicit
  five-state split of Candidate B (COOLING/HEATING/STABLE/MIXED/
  INSUFFICIENT_DATA) replacing the original study's single
  `MIXED_OR_STABLE` bucket for this analysis, with exact, gap-free/
  overlap-free boundary operators (`_horizon_bucket`): the neutral band
  is closed/inclusive on both ends, COOLING/HEATING use strict
  inequalities just outside it. `classify_candidate_b` itself is
  untouched.
- `compute_directional_metrics()` in `metrics.py`: separates "direct
  reversal rate" (a same-month flip straight from one directional state
  to the other) from "directional-to-neutral rate" (a move into/out of a
  neutral state) — both sharing the same denominator as the existing
  all-state churn rate, so the three are directly comparable.
- `finalist_study.py`: new orchestration computing the Core PCE decision
  table, Candidate B explicit-state distributions, the neutral-band
  mechanism investigation, the cross-measure confirmation hierarchy, the
  turn-persistence episode table, and the missing-confirmation check —
  all against the same cached FRED data the original study uses.
- 14 adversarial boundary tests for the explicit B states, 5 tests for
  the directional-metrics split, and 23 tests for the finalist
  orchestration itself (89 research tests total, up from 46).

### Key empirical findings

- The non-monotonic churn finding (Candidate A's all-state churn peaking
  at delta=0.25) is confirmed as a real mechanical effect, not a bug:
  direct reversal rate falls monotonically as delta widens (0.258 →
  0.155 → 0.044 → 0.005), but directional-to-neutral transitions rise
  faster than reversals fall until the neutral band gets wide enough
  that the series starts resting inside it rather than merely crossing
  through — producing a genuine peak in total churn around delta=0.25.
  The same shape (peak at 0.25) reproduces for Candidate B-explicit,
  driven almost entirely by MIXED/STABLE churn since B's direct
  reversal rate is already near zero at every finalist delta.
- Once MIXED and STABLE are split apart for Candidate B, its direct
  COOLING↔HEATING reversal rate is effectively 0 at all three finalist
  deltas (0.011 / 0.000 / 0.000) — the dual-confirmation design
  essentially eliminates same-month directional whipsaws, at the cost of
  a large MIXED bucket (32-45% of months).
- Candidate A is fastest to signal a turn across six tested historical
  episodes but is also the only finalist observed to reverse within one
  month at a genuine historical turning point (2008 crisis, 2022-2024
  disinflation) — no finalist achieves both speed and persistence at
  once in this data.
- The 2025-10-01 CPI gap is confirmed as a documented BLS
  government-shutdown data-collection gap (per BLS's own published page),
  not a defect in this project's retrieval code; verified directly that
  Core PCE's own classification is structurally unaffected by the
  missing Core CPI confirmation, and that the cross-measure agreement
  computation correctly reports the month as neutral disagreement rather
  than fabricating or silently dropping it.
- Cross-measure hierarchy analysis (not majority voting) shows the
  underlying pair (Core PCE/Core CPI) is rarely in direct opposition
  (≤2.84%) but agrees on the same state under 55% of the time — most of
  the remainder is neutral/mixed disagreement, not opposition. Headline
  measures agree with each other more often (63-70%) than the underlying
  pair does.
- "Current vintage" as a future UI label was found potentially
  misleading given the app's actual architecture: `EconomicObservation`
  stores exactly one value per `(series, date)`, with no revision/vintage
  dimension at all, so there is no second vintage for "current" to be
  implicitly contrasted against. Recommended a more precise label
  ("Latest revised data") plus an expanded disclosure sentence stating
  the single-value architecture explicitly. Documentation-only
  recommendation; no product code changed.

### Unresolved methodology decisions

Unchanged in kind from the original study, now sharpened to the
finalist set: which Candidate B delta to canonicalize; whether
Candidate A's speed is worth its whipsaw risk; whether Candidate C's 82%
MIXED occupancy is acceptable for a primary signal; how to surface
Core CPI confirmation-unavailable states to end users; and the
current-vintage UI label wording. Full detail:
`research/inflation_momentum/FINALIST_ANALYSIS.md`'s "Questions for
Human Decision" section.

## Inflation Monitor Methodology Freeze — inflation_v1.0 (pre-implementation, not Increment #14)

The human methodology decision left open by the finalist analysis above
has now been made: **Candidate B (Dual Confirmation), neutral band
δ = 0.10 percentage points, Core PCE primary / Core CPI confirmation**.
This entry records freezing that decision into a normative,
versioned contract *before* any production implementation, per this
project's standing principle:

> Facts are sourced. Calculations are deterministic. AI is
> interpretive. No probabilistic component may be required for the
> correctness, reproducibility, availability, or integrity of the
> Economic Intelligence Engine.

New artifact: [`docs/methodology/inflation-monitor-v1.0.md`](methodology/inflation-monitor-v1.0.md)
(`docs/methodology/` is a new directory — no established methodology-doc
convention existed in the repository before this). No production code
was written; no ADR was created for the candidate/delta selection
itself, because the methodology specification document *is* the
canonical economic-method decision record — an ADR would only be
warranted by a new durable *architectural* decision, and this freeze
did not surface one (see Architecture Compatibility below).

### Why freeze before implementation

A deterministic methodology contract, versioned and marked FROZEN, lets
Increment #14 be evaluated against a fixed target rather than an
evolving one — implementation conforms to the contract; it does not
reinterpret, extend, simplify, or "improve" the economic methodology
along the way. This mirrors ADR-010's existing precedent for the
transformation engine (spec first, then a provably pure implementation)
applied one layer up, to methodology rather than arithmetic.

### Key exact rules carried into the frozen contract

- **Exact calendar-month endpoints, not row position.** `t-3`/`t-6`/
  `t-12` must resolve by looking up the actual calendar date N months
  before `t`, never by counting back N rows of whatever happens to be
  persisted. A missing intermediate month does not invalidate an
  endpoint calculation that doesn't require it; a missing *endpoint*
  does. This explicitly forbids reusing `app/domain/transformations.py`'s
  existing row-position offset pattern for inflation horizons.
- **Primary vs. confirmation authority is a hard invariant.** Canonical
  underlying state is `classify(Core PCE)` — never `combine(...)`,
  never `vote(...)`, never AI-decided. Core CPI, Headline CPI, and
  Headline PCE can never override Core PCE's state.
- **Five canonical momentum states** (COOLING/HEATING/STABLE/MIXED/
  INSUFFICIENT_DATA) and **four confirmation relationships**
  (CONFIRMS/DIVERGES/INCONCLUSIVE/UNAVAILABLE), both exhaustively and
  unambiguously defined — no aliases, no additional states.
- **Latest-revised-data limitation is explicit and disclosed.** The
  contract forbids claiming "what was known at the time" for any
  historical calculation, since the persistence model has no
  point-in-time vintage architecture.
- **AI has zero methodology authority.** AI may explain the final
  deterministic evidence object; it may never calculate, classify,
  choose comparison periods, or alter provenance. The Monitor must be
  fully functional with AI unavailable.

### Adversarial audit

Performed against the frozen text itself (35 required cases: boundary
equality on both sides, floating-point boundary values just outside
each side, negative inflation, missing t-1/t-3/t-6/t-12, missing
intermediate months, zero/negative/non-finite index values, every
confirmation-relationship combination, both orderings of
latest-CPI-vs-latest-PCE, no-common-period, target/primary independent
availability, infrastructure vs. economic missing data, versioning
triggers, and every "accidental" failure mode: research-code
dependency, AI dependency, live-FRED dependency, row-offset mistakes,
post-rounding classification, 1M wrongly invalidating state, CPI
overriding PCE, headline series majority-voted into primary).
**Result: PASS** — every case yields one unambiguous expected behavior.
The exact `12M=3.00, delta=0.10` boundary values from the frozen text
were additionally run through the real, already-tested
`classify_candidate_b_explicit` function this session; all matched,
and `3.0 - 0.10 == 2.9` / `3.0 + 0.10 == 3.1` were confirmed exact in
IEEE-754 double precision for this constant — no hidden-epsilon problem
exists for it. Two non-blocking implementation notes were recorded for
Increment #14: NaN must be excluded with an explicit `isfinite` check
(bare `<=`/`>` does not reject NaN), and the future domain module must
build calendar-exact date lookups rather than reusing
`app/domain/transformations.py`'s row-position pattern.

### Research consistency

Confirmed, not re-decided: the frozen formulas are algebraically
identical to the research's general compounding formula at n=1/3/6/12;
the frozen boundary operators match `_horizon_bucket`'s existing
inclusive-band/strict-outside implementation exactly; δ=0.10 is one of
the three deltas the finalist analysis actually computed and reported
for Candidate B (`FINALIST_ANALYSIS.md`); and the real 2025-10-01
Core-CPI gap already empirically demonstrated Core PCE's classification
is unaffected by missing confirmation, directly supporting the Primary
Authority invariant. One implementation-pattern difference was found
and is not a mismatch: the research code resolves horizons by row
position, verified this session to be numerically equivalent to
calendar-exact lookup only because all four cached series have zero
structurally-missing calendar months across their full history (the one
real gap, 2025-10-01, is a null-valued row, not an absent one) — this
equivalence is a fact about that dataset, not a property of
row-position code in general, which is exactly why the frozen contract
states the calendar-exact rule explicitly rather than inheriting the
research shortcut. **Result: no material mismatch.**

### Architecture compatibility

Inspected `app/domain/`, `app/repositories/series_repository.py`,
`app/services/`, `app/models/series.py`, `app/api/analysis.py`, and
ADR-009/010/011/017. The repository already returns full,
chronologically-ordered observation ranges sufficient for a pure domain
function to build its own exact-date lookups; `app/domain/analysis.py`'s
`align_series` is already a directly analogous exact-date-matching
precedent (ADR-011) for the new `latest_common_period` logic;
`app/api/analysis.py` already distinguishes infrastructure failure
(503/500) from data-availability outcomes (400/404), matching this
contract's required separation; and ADR-017's "the application, never
the model, owns execution" principle already establishes the precedent
this contract's AI Boundary section needs. **Result: no blocking
conflict.** Increment #14 can implement `inflation_v1.0` as a pure
function in a new domain module, fed by the existing repository, with
no migration and no dangerous change to an existing public contract.

### Reusable lesson

Methodology decisions happen *before* implementation, and implementation
conforms to the versioned contract rather than the other way around —
the same discipline this project already applies to architecture
(ADR-first) now applied to economic methodology (spec-first). A
methodology document that is FROZEN, adversarially audited, and checked
against both its own research lineage and the target architecture
*before* a single line of production code exists is what makes "the
model doesn't get to reinterpret the methodology" an enforceable claim
later, rather than a hope.

## Increment 014 — Deterministic Inflation Monitor v1

Implements `inflation_v1.0` exactly as frozen in
[docs/methodology/inflation-monitor-v1.0.md](methodology/inflation-monitor-v1.0.md)
(the prior entry). One narrow, read-only endpoint:
`GET /api/v1/monitors/inflation`. No reinterpretation of the
specification was needed or made.

### Files

New: `app/models/inflation.py` (typed models, enums, and the one
canonical definition of every `inflation_v1.0` constant), `app/domain/inflation.py`
(pure methodology core), `app/services/inflation.py`
(`InflationMonitorService`), `app/api/inflation.py` (the route),
`tests/test_domain_inflation.py` (112 pure-domain tests),
`tests/integration/test_inflation_service.py` (9 PostgreSQL-backed
service tests), `tests/api/test_inflation_api.py` (18 HTTP tests).
Modified: `app/main.py` (router registration), `tests/test_domain_architectural_independence.py`
(added `app/domain/inflation.py` to the guarded file list and `math` to
its stdlib allowlist), `tests/api/test_failure_mapping.py` (added
`api/inflation.py` to the existing AI-independence static-import
guard), `docs/architecture/current-architecture.md`,
`docs/architecture/request-flows.md` (Flow 22/23). No ADR: nothing here
is a new durable *architectural* decision beyond what ADR-009/010/011/017
already establish and the methodology document already records as the
economic-method decision.

### Domain design

`app/domain/inflation.py` follows `app/domain/transformations.py`/
`app/domain/analysis.py`'s existing convention exactly (no FastAPI,
SQLAlchemy, FRED, httpx, environment, or `research/` import — enforced
by the existing architectural-independence test, extended to cover this
file) with one deliberate, frozen-spec-mandated departure: every
horizon (`t-1`/`t-3`/`t-6`/`t-12`) resolves by an **exact calendar-month
lookup** against an explicit `{date: value}` index (`build_index`,
`month_before`), never by row position. `classify_state` (rates in,
state out) is factored out of `classify_period` (index in, full
evidence+state out) specifically so the five-state boundary decision is
unit-testable against hand-picked float literals without needing index
values that round-trip exactly through the 3M/6M annualization
formula's 4th/2nd roots — verified, not assumed, that such a round-trip
is not generally achievable in IEEE-754 (see "Numeric safety" below).

`compute_series_momentum` (one series' own latest state),
`compute_confirmation` (Core CPI vs. Core PCE, same-period only),
`compute_target` (Headline PCE YoY vs. 2.0%), and
`compute_headline_context` (Headline PCE/CPI, independently, no
aggregate) each call `classify_period` as their shared primitive, so
"latest state" and "state at a specific comparison period" can never
drift into different classification logic.

### Service orchestration

`InflationMonitorService.get_result` fetches the four canonical series
independently via `SeriesRepository`. A series with no `EconomicSeries`
row at all yields an empty observation list — **not** `SeriesNotFoundError`
— so a missing series is indistinguishable, downstream, from one that's
persisted with insufficient history. This is a deliberate, spec-mandated
departure from `AnalysisService`'s convention (which does raise
`SeriesNotFoundError` → 404 for a missing series): the frozen
specification requires missing economic data to surface as a normal
`200` with `INSUFFICIENT_DATA`/`available: false`, never as an HTTP
error, so this endpoint's missing-series behavior is intentionally
*not* the same as `/analysis/compare`'s.

### Exact-calendar-endpoint strategy

`month_before(period, n)` computes calendar months arithmetically
(`year*12 + month - n`, then `divmod`) — no dependency on which rows
happen to exist. `build_index` turns a series' observation list into a
`{date: value}` map (excluding invalid values entirely, never leaving a
placeholder). Every horizon looks up `index.get(month_before(t, n))`
directly: a month absent from the index (no row, or a row with an
unusable value) is unavailable for that lookup, full stop, and can
never shift which calendar month a *different*, unrelated calculation
uses. Verified directly with a dedicated regression test
(`test_row_position_shifting_cannot_occur`): adding an early, unrelated
observation row changes nothing about a later period's 3M/6M/12M
values or endpoint dates.

One correctness bug caught by this increment's own integration tests
(not shipped): `latest_observation_period` was initially computed from
`build_index`'s output (valid values only), which would have silently
reported the wrong "latest observation" date whenever the true latest
row's *value* was itself missing (exactly today's real 2025-10-01 Core
CPI situation) — the row exists, but with a null value, so it was being
treated as if it didn't exist at all. Fixed by adding
`latest_observation_date`, which reads the raw observation list's dates
directly, independent of value validity. `latest_valid_state_period`
correctly continues to search backward using the valid-only index.

### Numeric safety

`_is_valid_index_value` requires `value is not None and math.isfinite(value)
and value > 0` — `math.isfinite`, not a bare `<=`/`>` comparison, is
required because `NaN` compares `False` to every comparison including
`NaN <= 0`, so a naive guard would silently let it through. No epsilon
is added anywhere in the boundary comparison; `classify_state`'s
`lower <= r_3m <= upper` is exactly the frozen spec's inclusive rule,
using `NEUTRAL_BAND_PP` (`0.10`) as-is. Verified directly (test
authoring, not production code) that `3.0 - 0.10 == 2.9` and
`3.0 + 0.10 == 3.1` hold bit-exactly in this Python's IEEE-754 double
precision — but also verified, by exhaustive attempted construction,
that hand-picking raw index *levels* whose forward-computed 3M/6M rate
round-trips to an exact chosen decimal target is generally **not**
achievable (off by ~1e-13 to 1e-14 in every combination tried), because
those horizons require a 4th/2nd root of the raw ratio. This is exactly
why `classify_state` takes already-computed rates rather than raw index
values: it makes the boundary decision testable against exact float
literals directly, sidestepping a real (not hypothetical) IEEE-754
limitation rather than working around it with an ad hoc tolerance.

### Evidence / provenance design

`InflationMetricEvidence` carries `series_id`, `calculation_period`,
`transformation`, both endpoint dates, both endpoint values (as
persisted, unrounded), the unrounded computed value, `methodology_id`,
and `data_basis` for every one of 1M/3M/6M/12M — populated even when
the metric is unavailable (endpoint dates still show which exact month
was needed; values are `null`). `TestProvenance.test_evidence_reproduces_returned_state_by_hand`
proves this is sufficient: given only the evidence fields, the exact
same state can be recomputed without calling any function in the
module under test.

### Missing-data semantics

`SeriesMomentumResult.calculation_period` is `null` only when a series
has no usable observation at all; otherwise it anchors to the latest
period that was actually evaluated (the latest valid state period, or,
failing that, the latest observation period) — never a fabricated
period. `INSUFFICIENT_DATA` never conflates with an infrastructure
failure: a missing endpoint produces a normal `200` result; a real
`OperationalError`/`SQLAlchemyError` from the database still propagates
through the service to the route's existing 503/500 mapping, unchanged
from every other PostgreSQL-backed route in this project.

### Primary/confirmation separation

Core PCE's own state is computed exclusively from Core PCE's own
observations (`compute_series_momentum(primary_observations, ...)`) —
structurally incapable of referencing Core CPI, Headline CPI, or
Headline PCE, since those functions are never called. Proven directly
(`TestPrimaryAuthority`): changing Core CPI arbitrarily, removing it
entirely, changing Headline CPI, or changing Headline PCE's level all
leave Core PCE's own `underlying_momentum` byte-for-byte identical.

### Common-period resolution

`find_latest_common_period` intersects both series' own observation
dates, then searches backward for the latest date where *both*
independently have a full valid state — never merely a shared row.
Proven with a real fallback scenario (`test_confirmation_falls_back_to_earlier_common_period`,
both at the domain and the PostgreSQL-integration level): both series
share their newest observation date, but Core CPI's t-12 endpoint for
that date is missing, so the comparison period correctly falls back one
month rather than either using the mismatched date or giving up
entirely.

### Verification

`TEST_DATABASE_URL=... .venv/bin/pytest tests/ -q`, run twice: **501
passed** both times (up from the pre-Increment-014 baseline of 362; all
139 new tests are additive, nothing existing was modified to
accommodate this increment). `app/domain/inflation.py` confirmed on the
existing pure-domain-layer architectural guard (no forbidden import,
allowlist-only imports). No new module under `app/` imports
`research/` (covered automatically by the existing repository-wide
`tests/research/test_inflation_momentum.py::TestArchitecturalIndependence`
guard, which walks all of `app/`, not a fixed file list). `git diff`
confirms: no migration, no change to `app/api/ai.py`/`app/services/ai.py`/
`app/services/ai_tools.py`/`app/models/ai.py`, no OpenAI/FRED
dependency anywhere in the monitor's request path (proven by a
fail-fast mock in `tests/api/test_inflation_api.py`), and
`docs/methodology/inflation-monitor-v1.0.md` itself was not modified —
the specification was implemented as written, not adjusted for
implementation convenience.

### Reusable lesson

Writing integration tests against a real database, not just domain unit
tests, caught a genuine bug (the `latest_observation_period`/null-value
conflation above) that an in-memory-only test suite with hand-picked
fixtures had not exposed, because the domain tests happened to always
pair "latest row" with "latest valid row" in their fixtures. The fix
came from deliberately constructing a fixture where those two diverge
— exactly the kind of case the frozen specification's own "Latest
observation period" vs. "latest valid state period" distinction was
written to guard against, which is what prompted writing that specific
test in the first place. A specification that draws a sharp distinction
between two similar-sounding concepts is often signaling exactly where
an implementation is likely to quietly conflate them.

## Pre-Increment 015 — "What Changed?" Contract Design (specification only)

Increment #14 is closed, committed, and pushed (baseline: 513 passing
tests). This entry records designing and proposing — not implementing —
the deterministic comparison contract for "what changed in inflation
since the previous comparable canonical result." New artifact:
[`docs/methodology/inflation-what-changed-v1.0.md`](methodology/inflation-what-changed-v1.0.md),
status **PROPOSED**, not FROZEN. No production code was written; no
`app/` file, test, or the frozen `inflation-monitor-v1.0.md` was
modified.

### Purpose and why the comparator does not recalculate

The product question ("what changed, what didn't, what evidence
supports that") is exactly the kind of question it would be tempting to
hand an LLM. This contract exists to make that unnecessary: `compare(previous,
current)` operates only on two already-canonical `InflationMonitorResult`
values and must never recalculate a formula, choose a different series,
reclassify momentum, alter target-gap semantics, reinterpret
confirmation, repair missing data, substitute a period, or use AI
judgment — mirroring `inflation_v1.0`'s own "facts are sourced,
calculations are deterministic" principle one layer up, applied to
comparison rather than classification.

### Previous-period semantics (the central design question)

The task's proposed default — previous means the immediately preceding
**calendar month**, never a database row, never a backward search — was
adversarially evaluated against the real #14 contract and recommended
for freezing, with one refinement: because `inflation_v1.0` already
allows Core PCE's own anchor period, Core CPI confirmation's
`latest_common_period`, Target's own period, and each headline series'
own period to differ from one another (existing, approved #14 behavior),
"previous" must be computed **per tier**, relative to that tier's own
current anchor (`month_before(tier_current_period, 1)`), not from one
forced global `t`. Critically, previous is never searched for — if the
exact calendar month before the current anchor isn't classifiable, that
is reported as an availability transition, never silently bridged to an
earlier classifiable month. This is precisely what resolves the
July/August(missing)/September adversarial case: comparing "current"
against exactly one month before it can never accidentally skip the gap
and report a direct COOLING→HEATING transition across it.

### State vs. availability vs. metric distinction

Formalized exactly as specified: a state change requires both sides to
be economically classifiable (COOLING/HEATING/STABLE/MIXED) and unequal;
`INSUFFICIENT_DATA` on either side is an availability transition, never
an economic state transition. A state that doesn't change while its
underlying metrics do (`3M: 2.8→2.6`, `state: COOLING→COOLING`) is
explicitly *not* "no change" — the metric-change fact is preserved and
reported alongside `state_changed=false`. Metric comparison is based on
canonical unrounded values (`2.844→2.846` is `changed=true` even when
both round to the same display value), with no epsilon introduced —
consistent with `inflation_v1.0`'s own "no hidden epsilon" discipline.

### Confirmation-change semantics

A relationship change and an availability change are represented as
independent, coexisting facts, never one erasing the other —
`CONFIRMS→UNAVAILABLE` is both `relationship_changed=true` and
`confirmation_availability_lost=true` simultaneously. The frozen #14
invariant (`confirmation_available == (relationship != UNAVAILABLE)`)
is read from each already-canonical `ConfirmationResult`, never
re-derived independently by the comparator.

### Latest-revised-data and release-awareness limitations

What Changed V1 inherits `inflation_v1.0`'s `latest_revised_data` basis
verbatim: a historical comparison uses the latest revised observations
currently available, never a claim about what was known at that
historical time. Because persistence overwrites revised observations in
place rather than retaining vintages, What Changed V1 cannot distinguish
"a new month arrived" from "an old month was revised between two runs"
— explicitly documented as a permanent v1 limitation, with no
revision-attribution heuristic invented to paper over it. Release-aware
framing ("since yesterday's CPI release") is explicitly deferred — the
system has no release-event metadata or point-in-time vintage snapshots
today; V1 is a plain period-to-period comparison, `MONTH_OVER_MONTH`
only (current canonical period vs. exact calendar month before it), by
explicit product direction — no week/quarter/release/custom/AI-selected
comparison mode exists in V1.

### Architecture compatibility finding

Inspected the actual committed #14 code (not recalled from memory of
writing it) rather than designing against an imagined
`InflationMonitorResult`. Finding: `InflationMonitorService.get_result`
takes no period argument and only ever computes "latest" — but the pure
primitives one layer down (`classify_period`, `_metric_evidence`,
`classify_confirmation_relationship`, `build_index`, `month_before`)
already accept or support an explicit calculation period and are not
"latest-only" internally (they're already used this way for
confirmation's own comparison-period classification). The smallest
clean #15 extension is therefore: one new, additive, pure function that
assembles an `InflationMonitorResult`-shaped object anchored at an
explicit period per tier (a sibling to, never a modification of,
`compute_inflation_monitor_result`), plus one new, pure comparator with
zero economic-formula knowledge. No repository change, no migration, no
change to any existing model or function is required.

### Adversarial audit result

All 18 originally-specified adversarial cases (A–R) resolve to one
unambiguous behavior. One additional case was found during this audit
and is not yet resolved by fiat: a tier whose current anchor period is
itself `None` (e.g. confirmation has never had a common period in
recorded history) has no date to compute "one month before" from. A
conservative default is proposed (previous also `None`, no change flags
raised) but is presented as an open decision, not silently assumed,
alongside one product-confirmation question (whether confirmation's
period basis should really follow its own `latest_common_period` rather
than primary's period, as recommended here).

### Unresolved decisions

Two, both narrow and named precisely in
`docs/methodology/inflation-what-changed-v1.0.md`'s "Remaining human
decisions" section. Status is **PROPOSED**, not FROZEN, until a human
resolves them — per this project's now-established discipline of never
marking a specification frozen merely because it was written.

### Reusable lesson

A comparison contract is not a second methodology, but it is tempting
to let it become one the moment it needs a period the underlying
methodology doesn't explicitly hand it (here: "previous period" for a
tier `inflation_v1.0` never defined a "previous" for at all). Resolving
that temptation by extending the *period selection* mechanism only —
while reusing every existing classification primitive completely
unmodified — is what keeps "the comparator recalculates nothing" true
in practice, not just in the document's stated intent.

### Amendment — decisions resolved, structural correction, FROZEN

Both decisions listed as "Unresolved decisions" above are now resolved,
and a third, more serious problem was found and fixed in the same pass:
the proposed contract's own two-snapshot assumption directly
contradicted its own per-tier independent-period design. Status moved
from **PROPOSED** to **FROZEN**.

**Decision 1 (degenerate anchor) — resolved: no `NOT_APPLICABLE` state.**
A section with no current anchor period reports
`comparison_available = false`, both periods `null`, and an empty
change list — never a fabricated transition. This is now a first-class,
explicit field, not a value smuggled into the existing
`INSUFFICIENT_DATA`/`UNAVAILABLE` states, and it is structurally
distinct from "compared successfully and found nothing different"
(`comparison_available = true`, `changes = []`) — the two cases the
task most wanted kept from collapsing into each other.

**Decision 2 (confirmation's period basis) — resolved and frozen as
originally recommended.** Confirmation's current anchor remains
`inflation_v1.0`'s own `latest_common_period` verbatim, never
re-anchored to Core PCE's standalone period. Primary's and
confirmation's periods are allowed to differ in the same report; this
is `inflation_v1.0`'s own existing design, not something to normalize
away.

**Decision 3 (found during this pass, not listed as a prior open
question) — the false global two-snapshot assumption, removed.** The
prior draft wrapped the whole comparison in one global
`previous_result`/`current_result` pair of full `InflationMonitorResult`
objects and claimed the entire comparison was auditable from those two
objects alone. That directly contradicted the document's own,
already-correct statement that primary/confirmation/target/headline may
have independently different current/previous periods — there is no
single pair of full-monitor snapshots that can truthfully represent
five independently-anchored comparisons, and the architecture has no
point-in-time monitor-vintage concept that could construct such a pair
even in principle. Corrected: each of the five change sections now owns
its exact canonical evidence (`SeriesMomentumResult`/`TargetResult`,
`inflation_v1.0`'s own unmodified shapes) and its own period pair
directly; a live, current-only `InflationMonitorResult` may still be
attached as optional convenience context but is no longer the required
evidence basis for anything.

**Comparison-availability semantics, clarified.** `comparison_available`
answers exactly one question — does this section have a current anchor
at all — never "did both sides turn out classifiable." This is
guaranteed by `inflation_v1.0` itself: every "latest" anchor
(`find_latest_valid_state_period`, `latest_common_period`,
`find_latest_period_with_valid_12m`) is by definition only ever set to
an already-classifiable period, so whenever a current anchor exists,
the current side is always valid; only the previous side can ever turn
out unavailable, and that is exactly category 4 (an availability
change), never a reason to call the comparison itself unavailable.

**Re-audit result: PASS**, 18 cases (A–O in the renumbered list,
covering every case named in this round plus every case from the first
audit), no case left ambiguous, no new open question found. Contract ID
`inflation_what_changed_v1.0`, version `1.0`, is now **FROZEN**.

### Second amendment — corrected a real contradiction found after freeze: unreachable `AVAILABLE → UNAVAILABLE`

The freeze above was premature in one respect: its own "comparison
availability" clarification asserted that `inflation_v1.0`'s existing
"latest" anchors (`latest_valid_state_period` for ordinary series,
`latest_common_period` for confirmation) guarantee the *current* side of
a comparison is always classifiable. That claim is true of those
anchors by construction — and that is exactly the problem. Anchoring
What Changed's "current" period to a *valid-state* anchor means an
unclassifiable most-recent month is, by definition, never selected as
"current" — it is silently skipped in favor of an earlier period that
does classify. That directly contradicts this same contract's own
required taxonomy: `AVAILABLE → UNAVAILABLE` (category 4) becomes
structurally unreachable, for both primary/target/headline (Core PCE
`current_period` would always resolve past an `INSUFFICIENT_DATA`
month) and, more seriously, for confirmation (`latest_common_period` is
defined as a period where *both* series are already valid, so
`CONFIRMS → UNAVAILABLE` could never be observed even though the
contract explicitly requires it as an adversarial case).

**Why this happened:** the first freeze pass correctly separated "an
anchor exists" from "the anchor's state is classifiable" at the
*comparison_available* level, but did not carry that separation through
to *which* `inflation_v1.0` period field gets used as the anchor itself
— it reused the Monitor's own "latest valid" anchors, which exist
precisely to hide an unclassifiable period from the Monitor's user-
facing "current state," the opposite of what a change-detector needs.

**Fix, now frozen:** introduced one new, purely period-selection concept
this contract owns — `latest_shared_observation_period` — the latest
calendar month for which Core PCE and Core CPI both have *any*
observation row, regardless of classifiability (computed by intersecting
the two already-fetched observation date sets and taking the max; no
new query, no repository change). Confirmation now anchors to this,
never to `inflation_v1.0`'s `latest_common_period`. Ordinary series
(primary, target, headline PCE, headline CPI) now anchor to
`inflation_v1.0`'s own existing `latest_observation_period` (a row
exists, regardless of validity) rather than `latest_valid_state_period`.
`inflation_v1.0` itself was not touched — all three of its existing
period fields keep their exact existing meanings and continue to serve
the Monitor exactly as before; this contract simply stopped reusing the
*wrong one* of them as its own anchor. A structural invariant now stated
explicitly in the spec: `latest_valid_state_period <=
latest_observation_period` and `latest_common_period <=
latest_shared_observation_period`, always — What Changed's anchors are
never earlier than the Monitor's, and are strictly later exactly when
there is an availability event the Monitor's own "current" reading
would otherwise hide.

**Re-audit result: PASS**, 17 cases, including the two that directly
exercise the fix (case 3: valid → unavailable for ordinary series; case
10: `CONFIRMS → UNAVAILABLE` for confirmation) and the two structural
invariants (cases 12/13: the Monitor's own valid-state anchor is always
at or before What Changed's observation-based anchor). No new ambiguity
found. Contract remains **FROZEN**, `inflation_what_changed_v1.0`,
version `1.0`.

## Increment 015 — Deterministic Inflation "What Changed?" Engine

Implements `inflation_what_changed_v1.0` (the frozen contract above)
exactly as specified. One new, narrow, read-only endpoint:
`GET /api/v1/monitors/inflation/changes`. No reinterpretation of the
contract was needed; no line of `inflation_v1.0`'s existing
classification logic was modified.

### Files

New: `app/domain/inflation_what_changed.py` (pure comparator, zero
`inflation_v1.0` knowledge -- does not import `app.domain.inflation`,
enforced by an extended architectural-independence test),
`app/models/inflation_what_changed.py` (`InflationWhatChangedResult`
and its five section models, `ChangeEvent` -- reuses `inflation_v1.0`'s
own `SeriesMomentumResult`/`TargetResult` verbatim, no new economic
type), `tests/test_domain_inflation_what_changed.py` (32 comparator
tests), `tests/integration/test_inflation_what_changed_service.py` (12
PostgreSQL-backed service tests), `tests/api/test_inflation_what_changed_api.py`
(22 HTTP tests). Modified: `app/domain/inflation.py` (additive: the new
period-selection function `latest_shared_observation_period`, the
exact-period siblings `compute_series_momentum_at`/`compute_target_at`/
`compute_confirmation_at`, the `month_over_month_*` orchestration
helpers, and one small justified refactor -- `compute_target`'s
assembly logic extracted into `_build_target_result` so
`compute_target_at` shares it rather than duplicating the target-gap
formula), `app/services/inflation.py` (`InflationMonitorService.get_what_changed_result`),
`app/api/inflation.py` (the new route), `app/main.py` unchanged (same
router, new route on it), `tests/test_domain_inflation.py` (+24 tests
for the new domain-layer primitives), `tests/test_domain_architectural_independence.py`
(added `app/domain/inflation_what_changed.py` to the guarded file list
plus one dedicated test asserting it never imports
`app.domain.inflation`), `docs/architecture/current-architecture.md`,
`docs/architecture/request-flows.md` (Flow 24/25). One small,
non-semantic clarification to the already-frozen
`docs/methodology/inflation-what-changed-v1.0.md`: the "Deterministic
change event model" section's `ChangeEvent` field list was missing an
explicit `delta` field, even though the earlier "Metric change" section
already required `absolute_delta` to be reported -- added `delta:
current_value - previous_value when both numeric and available, else
null` to make the two sections consistent; no rule changed. No ADR:
nothing here is a new durable architectural decision beyond what the
frozen contract and ADR-009/010/011/017 already establish.

### Architecture implemented

```
persisted observations (SeriesRepository, unmodified)
        ↓
InflationMonitorService.get_what_changed_result (NEW method)
        ↓
inflation_v1.0 exact-period canonical component construction
    (app.domain.inflation: month_over_month_series_momentum /
     month_over_month_target / month_over_month_confirmation --
     period SELECTION plus a call into the EXISTING classify_period /
     _metric_evidence / classify_confirmation_relationship primitives,
     unmodified)
        ↓
pure deterministic What Changed comparator
    (app.domain.inflation_what_changed -- zero formula knowledge,
     architecturally forbidden from importing app.domain.inflation)
        ↓
typed InflationWhatChangedResult
        ↓
GET /api/v1/monitors/inflation/changes
```

### Exact-period canonical construction

The smallest clean extension identified during the freeze review turned
out to be exactly as small as predicted: `classify_period`/
`_metric_evidence`/`classify_confirmation_relationship` already accepted
an explicit period with no search -- what was missing was a public,
convenient way to call them that way. `compute_series_momentum_at`/
`compute_target_at`/`compute_confirmation_at` are thin wrappers that
build the index and call those existing functions directly, at a
caller-supplied period, instead of searching for "latest valid." Zero
formula duplication: `compute_target`'s own logic was refactored into a
shared `_build_target_result(index, period, fed_objective_percent)`
helper so `compute_target` (search then build) and `compute_target_at`
(build directly) can never drift apart.

### Period selection behavior

Three `month_over_month_*` orchestration functions (still inside
`app.domain.inflation` -- period selection plus construction is
`inflation_v1.0`'s job, per the frozen contract's own architecture
note) each: resolve `current_period` from the relevant series' own
`latest_observation_period` (ordinary sections) or the new
`latest_shared_observation_period` (confirmation); compute
`previous_period` as the exact calendar month before it via the
existing `month_before`; then evaluate both periods through the
exact-period primitives above. No backward search anywhere in this
path -- verified directly by a real-database integration test
(`test_july_august_september_missing_month_never_bridged`) using a
genuine three-month gap scenario.

### `latest_shared_observation_period` implementation

`{obs.date for obs in primary_observations} & {obs.date for obs in
confirmation_observations}`, then `max()` (or `None` if empty) -- pure
date-set arithmetic over the same two observation lists the service
already has in memory from `_load`. No new repository method, no new
query, no migration. Proved structurally later-than-or-equal-to
`inflation_v1.0`'s own `find_latest_common_period` both at the
domain-unit level (`TestLatestSharedObservationPeriod.test_never_earlier_than_find_latest_common_period`)
and end-to-end against real Postgres
(`test_anchors_to_latest_shared_observation_period_not_latest_common_period`,
which reproduces the frozen contract's own worked example: Monitor
still shows `CONFIRMS` at `latest_common_period`, while What Changed's
later `latest_shared_observation_period` correctly shows `UNAVAILABLE`).

### Comparator behavior

`app/domain/inflation_what_changed.py` receives only already-computed
`SeriesMomentumResult`/`TargetResult`/`ConfirmationRelationship` values
and does field reads plus arithmetic/equality/membership checks --
nothing else. Verified this is architecturally true, not just
documented as true: a dedicated test parses the module's own AST and
asserts it never imports `app.domain.inflation`. The pure-domain test
suite for this module hand-constructs every evidence object directly
from the Pydantic models (never by calling `classify_period`), proving
the comparator is fully exercisable with zero economic construction
code in the loop at all.

### Change event model

Exactly the five frozen event types (`METRIC_CHANGED`/`STATE_CHANGED`/
`AVAILABILITY_LOST`/`AVAILABILITY_RESTORED`/`CONFIRMATION_CHANGED`), no
interpretation-heavy ones. Deterministic ordering implemented as a pure
three-level sort key (component, then event type, then field) against
fixed tuples (`COMPONENT_ORDER`/`EVENT_TYPE_ORDER`/`FIELD_ORDER`) --
never dict iteration order, database row order, or judgment.

### Missing-data behavior

`comparison_available` is derived solely from whether a section's
current anchor period is non-`None` -- proven, not merely asserted, to
never depend on whether the evidence itself classified: a `COOLING`→
`INSUFFICIENT_DATA` comparison and an `INSUFFICIENT_DATA`→
`INSUFFICIENT_DATA` comparison both report `comparison_available: true`
with correctly different `changes` (an `AVAILABILITY_LOST` event vs.
none at all). The July/August/September missing-month invariant holds
exactly as specified: whichever month is latest-observed is always
"current," and its immediate predecessor is always "previous" -- never
a wider search, so a genuinely absent month can never disappear from
the transition history by being silently bridged over.

### API behavior

`GET /api/v1/monitors/inflation/changes`, no request body, added
alongside the existing `GET /api/v1/monitors/inflation` on the same
router. Same infrastructure-error mapping as every other PostgreSQL-
backed route (`OperationalError` → 503, `SQLAlchemyError` → 500, no
SQL/credentials/paths/stack traces in any error body -- verified with
the same synthetic-marker-leak test pattern as the Monitor endpoint).
Missing economic data is a normal `200` with per-section unavailable
evidence, never an error.

### AI/FRED independence

Zero AI imports anywhere in the new files (grep-confirmed and already
covered by the existing `test_no_deterministic_route_file_imports_aiservice`
guard, since the new route lives in the already-guarded
`app/api/inflation.py`). Works with `OPENAI_API_KEY` unset. `FREDClient`
construction fails fast if attempted, proven at both the service and
HTTP layers -- never triggered by any test.

### Tests

Pure domain (comparator): 32, in `tests/test_domain_inflation_what_changed.py`,
covering all 21 categories named in the increment brief plus
`comparison_available` semantics and the no-change/no-comparison
distinction. Pure domain (new `app.domain.inflation` primitives): +24
in `tests/test_domain_inflation.py`. Architectural: +1 dedicated
import-boundary test. Integration (PostgreSQL): 12, in
`tests/integration/test_inflation_what_changed_service.py`, including
the exact `latest_common_period`-older-than-`latest_shared_observation_period`
scenario against a real database. HTTP: 22, in
`tests/api/test_inflation_what_changed_api.py`. **Total new: 91.**

### Verification

`TEST_DATABASE_URL=... .venv/bin/pytest tests/ -q`, run twice: **604
passed** both times (up from the pre-Increment-015 baseline of 513; all
91 new tests are additive -- nothing existing was modified to
accommodate this increment, apart from one pre-existing integration
test file's own architectural guard, which this increment's own new
test file was written to respect rather than expand: the FRED-client
fail-fast proof for the new endpoint lives at the HTTP layer only,
matching this repository's existing, deliberately narrow convention
that only `test_discovery_service.py` may import `FREDClient` inside
`tests/integration/`).

### Reusable lesson

A "smallest clean extension" claim made during a freeze review is worth
re-verifying empirically at implementation time, not just trusted: the
frozen contract predicted that `classify_period`'s existing explicit-
period parameter would be sufficient, and it was -- but discovering
*exactly* where the thin wrapper belonged (a `_build_target_result`
extraction for target, not a new duplicate formula) only became obvious
while writing the code, not while writing the specification. Freezing
the *behavior* before implementation did its job even though the
*exact* internal shape of the reuse was decided later, during
implementation -- which is the correct division of labor between a
frozen contract and the code that satisfies it.

## Increment 016 (attempt) — Inflation Monitor Product UI: STOPPED

Attempted per the standing "facts are sourced, calculations are
deterministic" principle extended to the UI layer. Inspected the full
repository before writing anything: no `package.json`, no `.tsx`/`.jsx`
file, no `frontend/`/`web/`/`ui/`/`client/` directory, no frontend
dependency in `pyproject.toml`, no `StaticFiles`/`Jinja2Templates`/CORS
middleware in `app/main.py`, and zero mentions of any frontend
framework anywhere in 18 ADRs or the architecture docs. Confirmed this
was a genuine absence, not an oversight, before stopping. Zero files
were changed. Reported the smallest recommended foundation (React +
Vite + TypeScript, grounded in this project's own demonstrated
preferences — typed contracts, minimal justified tooling, no premature
abstraction) as a recommendation, explicitly not a decision, per the
task's own instruction not to introduce a framework unilaterally.

## Increment 016A — Frontend Foundation

The architecture decision from the stopped attempt above is now made
explicitly: **React + Vite + TypeScript + Tailwind CSS + Vitest + React
Testing Library**, no Next.js. This entry records building the
foundation only — no Inflation product UI (that is Increment #16B).

### Why this stack

FastAPI already owns every backend/application concern this project
has (routing, validation, persistence, deterministic domain logic) —
there is no server-rendering or backend-routing responsibility for a
second framework to take on, so Next.js was rejected as unneeded
complexity for what is fundamentally a thin, interactive presentation
client. Vite provides that thin client build tool. TypeScript gives the
API-contract boundary real type safety. Tailwind gives a lightweight
styling foundation without inventing a component-library/design-token
system this project doesn't need yet. Vitest + React Testing Library
reuse Vite's own toolchain for tests rather than adding a second,
separately-configured runner. **Frontend is non-canonical. Backend owns
all economic truth** — restated here as the explicit architectural
principle this and every future frontend increment must preserve.

### Environment and versions

Node v26.7.0, npm 11.19.0 (both far above Vite's minimum requirements;
no compatibility issue found). Scaffolded via `npm create vite@latest
frontend -- --template react-ts`, then added Tailwind/React Router/
Vitest/RTL explicitly. Installed versions: React 19.3.0, Vite 8.3.0,
TypeScript 6.0.3, Tailwind CSS 4.3.3 (with its official `@tailwindcss/vite`
plugin — no separate `tailwind.config.js`/`postcss.config.js` needed for
v4's CSS-based configuration), React Router 7.18.3, Vitest 5.0.0,
`@testing-library/react` 16.3.3. The scaffold's own linter, `oxlint`
1.82.0 (a single Rust binary, no plugin ecosystem), was kept rather than
adding ESLint — already minimal, already established by the template
itself.

### Runtime dependencies added, and why

- `react`/`react-dom` — the framework itself.
- `react-router-dom` — client-side routing; justified now because the
  product will soon have multiple pages (Inflation, and later
  dimensions), not introduced speculatively for a single route.
- `@tailwindcss/vite`/`tailwindcss` — the styling foundation.

No state-management library, no data-fetching library (React Query/SWR),
no chart library, no component library, no analytics SDK, no
authentication library — none demonstrably required yet; each would be
premature for a two-endpoint, one-page-to-come foundation.

### Directory structure

```
frontend/
  src/
    api/         client.ts (apiGet<T>), errors.ts (ApiError)
    components/  PageContainer.tsx
    layouts/     AppShell.tsx
    pages/       Overview.tsx, Inflation.tsx (placeholder), NotFound.tsx
    styles/      globals.css
    test/        setup.ts, no-economic-logic.test.ts
    App.tsx, App.test.tsx, main.tsx
  public/favicon.svg
  index.html, package.json, tsconfig*.json, vite.config.ts, .env.example
```

Only the primitives clearly justified now were created — no `Card`,
`Badge`, `LoadingSkeleton`, or `ErrorMessage` component yet; those
belong to whichever increment first needs them (likely #16B), per the
brief's explicit instruction to avoid speculative component-library
engineering.

### API client foundation

`apiGet<T>(path)` (`frontend/src/api/client.ts`): resolves
`VITE_API_BASE_URL` (empty string in development, so requests use
relative paths against the dev-proxy origin), issues the request,
verifies `response.ok`, parses JSON. Raises `ApiError`
(`frontend/src/api/errors.ts`) with `kind: "network"` (fetch itself
threw) or `kind: "http"` (non-2xx status) — never for a successful
response, regardless of its body. This preserves, at the frontend
boundary, the exact infrastructure-failure-vs-economic-unavailability
distinction the backend methodology documents already establish: a 200
response containing `INSUFFICIENT_DATA`/`UNAVAILABLE`/
`comparison_available: false` is a normal, successfully-parsed value,
never converted into an error. No inflation-specific types or requests
exist yet, per the brief's explicit "prefer waiting for #16B."

### Local development proxy

`frontend/vite.config.ts`'s `server.proxy` forwards `/api/*` to
`http://localhost:8000` by default (FastAPI's `uvicorn` default port),
overridable via a plain `BACKEND_PROXY_TARGET` environment variable
read only by the Node-side Vite config process — never a `VITE_`-
prefixed variable, so it is never bundled into the browser. Verified
directly, not just configured: started both `uvicorn app.main:app` and
the Vite dev server, confirmed `GET http://localhost:5173/api/v1/monitors/inflation`
returns the real backend's canonical JSON through the proxy unchanged,
then stopped both processes. Because the proxy makes every request
same-origin from the browser's perspective, **no backend CORS
configuration was added** — `app/main.py` is completely untouched.

### Application shell and routing

`AppShell` (header with the product name and primary navigation, a
skip-link, a `<main>` landmark) wraps two real routes — `/` (Overview,
a "frontend foundation ready" placeholder) and `/inflation` (a
placeholder that explicitly does not fetch or render any inflation
data) — plus a catch-all not-found route, via React Router's nested-route
layout pattern. `PageContainer` is the one reusable max-width/padding
primitive every page's content sits inside.

### Styling foundation

`frontend/src/styles/globals.css`: Tailwind's `@import "tailwindcss";`
plus a handful of global rules (body background/text color, an explicit
`:focus-visible` outline). No custom `@theme` token extension — Tailwind's
own neutral palette is used directly and consistently in components,
deliberately avoiding "arbitrary giant theme/configuration systems."
Economic-state color/iconography (COOLING/STABLE/HEATING/MIXED/
INSUFFICIENT_DATA) is explicitly deferred to Increment #16B — nothing
in this foundation encodes economic meaning into color.

### No economic logic in the frontend (architectural guard)

`frontend/src/test/no-economic-logic.test.ts` scans every non-test
`.ts`/`.tsx` file under `frontend/src/` for three deliberately narrow,
high-signal patterns: the compounded-annualization exponent shape
(`** (12 / n)`), its `Math.pow` equivalent, and the frozen 0.10
percentage-point neutral-band boundary arithmetic. Currently passes by
verifying genuine absence across the real foundation source tree (no
inflation code exists yet to false-negative against) — not a
placeholder assertion. Documented as a durable regression guard to be
extended alongside whichever inflation-specific display components
Increment #16B adds.

### Tests, typecheck, lint, build

24 frontend tests across three files (`App.test.tsx`: shell/routing/
navigation/not-found, 9 tests; `api/client.test.ts`: success parsing,
network vs. HTTP failure, no-retry, economic-unavailable-response
handling, 5 tests; `test/no-economic-logic.test.ts`: the guard above, 10
tests covering the discovered source files). One real bug caught and
fixed while writing these: React Testing Library's automatic post-test
DOM cleanup only self-registers when it finds an ambient `afterEach`
(Vitest/Jest "globals" mode); this project deliberately runs Vitest
*without* `globals: true` (explicit imports over ambient test globals,
matching the backend's own explicitness convention), so cleanup had to
be registered explicitly in `frontend/src/test/setup.ts` — without it,
renders leaked across tests within a file and multi-element query
errors appeared. `npx vitest run`, run twice: **24 passed** both times.
`npm run typecheck` (`tsc -b --noEmit`, `strict: true` plus
`noUncheckedIndexedAccess` explicitly set in `tsconfig.app.json` —
`exactOptionalPropertyTypes` was tried and reverted: it produced
friction against React Router's own (correct) optional-prop types
rather than catching a real bug in this project's code): clean, zero
errors. `npm run lint` (`oxlint`): clean, exit 0. `npm run build`
(`tsc -b && vite build`): succeeds — `dist/` output ~262 KB JS / ~10 KB
CSS before gzip.

### Backend verification

`TEST_DATABASE_URL=... .venv/bin/pytest tests/ -q`: **604 passed**,
unchanged from the pre-#16A baseline — no backend file was touched by
this increment.

### Security

No `.env` contents were read. No secret value appears anywhere in
`frontend/` — `frontend/.env.example` documents only the non-secret
`VITE_API_BASE_URL` (with an explicit comment that everything
`VITE_`-prefixed is bundled into client-visible JavaScript and must
never hold a secret), and `frontend/vite.config.ts` reads only
`BACKEND_PROXY_TARGET`, a plain local-dev routing setting.

### Deferred to Increment #16B

The entire Inflation Monitor product UI: primary Core PCE state, What
Changed, target/level, confirmation, headline context, evidence
disclosure — all consuming `GET /api/v1/monitors/inflation` and
`.../inflation/changes` for real, preserving their independent period
semantics rather than flattening every component onto one page-wide
date. No chart library, no AI, no live FRED calls exist anywhere in the
frontend yet.

### Reusable lesson

A frontend "no economic logic" guard is only meaningful if it can
genuinely fail — writing it against an empty foundation (nothing to
false-negative on) still has value as a *documented commitment* and a
*mechanism already wired in*, but its real test comes the moment #16B
adds the first inflation display component. Recording that expectation
explicitly here (and in `docs/architecture/current-architecture.md`) is
itself part of making the guard durable rather than decorative.

## Increment 016B — Inflation Monitor Product UI

Replaces the #16A placeholder `/inflation` route with the real,
production-quality product page: the first user-facing surface where
"facts are sourced, calculations are deterministic, AI is
interpretive" is enforced by the frontend rather than just stated by
it. Inspected `app/models/inflation.py`, `app/models/inflation_what_changed.py`,
`app/api/inflation.py`, both frozen methodology docs, and the #16A
frontend foundation before writing anything — every TypeScript type in
`frontend/src/api/inflation.types.ts` is a field-for-field mirror of
the real Pydantic models, not inferred from earlier prompts. Zero
backend files were touched (verified by `git status` before and after
this increment); zero economic formulas were reimplemented client-side.

### What was built

- **Types & API layer**: `frontend/src/api/inflation.types.ts` (closed
  union types for `InflationState`/`ConfirmationRelationship`/
  `ChangeEventType`/etc., matching the backend's own `Literal`s exactly),
  `frontend/src/api/inflation.ts` (`getInflationMonitor`,
  `getInflationWhatChanged` — thin `apiGet<T>` callers, no
  interpretation), `frontend/src/api/useApiResource.ts` (one reusable
  `loading`/`success`/`error` hook, instantiated twice on the page so the
  two endpoints load, fail, and retry completely independently).
- **Presentation-only libraries**: `frontend/src/lib/format.ts`
  (`formatPeriod`/`formatPeriodPair` — parses ISO date strings by regex,
  deliberately never via `new Date().toLocaleDateString()`, which can
  roll a UTC-midnight date back a display month in timezones behind UTC;
  `formatPercent` for plain readings vs. `formatPercentagePoints` for
  signed deltas/`target_gap_pp`, matching the task's own "2.64%" vs.
  "+0.70 pp" convention) and `frontend/src/lib/inflationLabels.ts`
  (label + restrained "tone" lookups for both closed enums —
  `INSUFFICIENT_DATA` and `UNAVAILABLE` always resolve to the same muted
  "unavailable" tone as every other missing value, never a direction).
- **Inflation components** (`frontend/src/components/inflation/`):
  `Badge` (text-first pill; color is reinforcement, never the sole
  signal), `InflationHero` (the primary Core PCE state — the page's
  single largest visual element), `MomentumMetrics` (3M/6M/12M, 1M as
  secondary context, plus the backend's own neutral-band boundaries
  displayed, never re-derived), `TargetPanel` (headline PCE YoY vs. the
  backend-exposed `fed_objective_percent`, signed `target_gap_pp` — no
  duplicated UI constant for the objective), `ConfirmationPanel` (Core
  CPI's relationship to Core PCE, visually subordinate — never an equal
  vote — and still rendered even when `relationship: "UNAVAILABLE"`,
  so a confirmation failure never reads as a monitor failure),
  `HeadlineContext` (headline PCE/CPI shown independently, no combined
  score), `WhatChangedSection` (the precedence logic below),
  `EvidenceDisclosure`/`MethodologyDisclosure`/`DataBasisNote` (`<details>`-
  based progressive disclosure, via the new generic
  `frontend/src/components/Disclosure.tsx`).
- **`InflationPage`** (`frontend/src/pages/Inflation.tsx`): composes all
  of the above in the required hierarchy, rendering each of the
  monitor's and what-changed's independent load states truthfully (see
  [Flow 27](./architecture/request-flows.md#flow-27--inflation-page-load-increment-16b)) —
  including partial success (one endpoint failing never blanks the
  other) and the infrastructure-failure-vs-economic-unavailability
  distinction (`ApiError` only ever means network/HTTP failure; a `200`
  carrying `INSUFFICIENT_DATA`/`UNAVAILABLE`/`comparison_available:
  false` renders as normal canonical content).

### What Changed rendering precedence (the one genuinely nontrivial piece)

For a momentum-shaped section (Core PCE, Headline PCE, Headline CPI):
a `STATE_CHANGED`/`AVAILABILITY_*` event on the `"state"` field is
always the headline transition; otherwise an empty `changes` list
renders exactly "No canonical changes detected."; otherwise (metrics
changed but the state didn't) renders exactly "State remains X." —
**never** collapsed into "No change," per the task's explicit
requirement — except when both periods' `state` is
`INSUFFICIENT_DATA`, where "State remains Insufficient data" would
misleadingly read as a direction, so that case renders "Insufficient
data in both periods." instead. `comparison_available: false` renders
"Previous-period comparison unavailable." — a distinct, separately
tested message from the true-zero-change case. Confirmation's headline
is a `CONFIRMATION_CHANGED` event on `relationship` when present
(`confirmation_availability_lost`/`restored` can never be true without
`relationship_changed` also being true, since `"UNAVAILABLE"` is itself
one of the four relationship values, so no separate branch was needed).
Target has no state concept, only metric events. Every subsection
renders its own `previous_period`/`current_period` pair — there is
deliberately no page-wide "as of" date.

### Architectural guard extended

`frontend/src/test/no-economic-logic.test.ts` gained three patterns
beyond #16A's two: client-side delta recomputation
(`current... - previous...`, which should always read the backend's own
`ChangeEvent.delta` instead), the `["COOLING","HEATING"]`/
`["HEATING","COOLING"]` pair-literal shape the backend's own
confirmation-relationship derivation uses, and a *declared* function
named after a backend period-selection helper (`findLatestCommonPeriod`,
`latestSharedObservationPeriod`, etc. — scoped to declaration syntax so
that legitimately reading `data.confirmation.latest_common_period` off
a response never false-positives). The guard now scans every new
inflation component and passed against all of them.

### Tests, typecheck, lint, build

110 frontend tests across 6 files (24 pre-existing #16A tests, updated
only where they asserted the now-superseded placeholder page content;
plus new coverage: `lib/format.test.ts`, `lib/inflationLabels.test.ts`,
and `pages/Inflation.test.tsx` — an integration suite mocking
`getInflationMonitor`/`getInflationWhatChanged` at the module boundary
against deterministic fixtures in `frontend/src/test/fixtures/inflation.ts`,
covering all five `InflationState` values, all four
`ConfirmationRelationship` values, all five `ChangeEventType`s, the
state-remains/true-no-change/comparison-unavailable three-way
distinction, independent per-section periods, primary-stays-visible
when confirmation is unavailable, evidence/methodology disclosure
content and toggling, monitor/what-changed HTTP failures independently
and together with partial-success rendering, retry, the
economic-unavailable-is-not-an-error distinction, and heading-hierarchy
accessibility basics). `npx vitest run`, run twice: **110 passed** both
times. `npm run typecheck`: clean. `npm run lint` (`oxlint`): clean.
`npm run build`: succeeds (`dist/` ~280 KB JS / ~17 KB CSS before gzip).

### Backend verification

No backend file was modified this increment (confirmed via `git status`
scoped to non-`frontend/`/non-`docs/` paths — empty). This session's
shell had no `TEST_DATABASE_URL` set, so `pytest` exercised its own
documented safety behavior (`tests/conftest.py`: database-backed tests
skip rather than run against an unconfigured or implicit database) —
**604 skipped**, not run, in this session. This is a session/environment
fact, not a code regression: the prior #16A entry's **604 passed**
baseline is unaffected because the backend source tree is byte-for-byte
unchanged.

### Deferred (unchanged from the task's own scope discipline)

No chart library (deferred until a deterministic historical monitor API
exists), no AI/chat surface anywhere, no auth/billing/alerts/watchlists/
Explore/Compare/second product dimension, no live FRED calls, no
database migration, no change to frozen methodology semantics.

## Increment 016B.1 — Inflation UI Visual Hierarchy Polish

A narrowly scoped, presentation-only pass over `/inflation`, done after
visual product review against populated real development data (see the
prior session's database-population report). No backend file, API
contract, methodology, or canonical event/state semantic was touched —
every change below is markup/CSS only, verified by `git status` showing
zero diffs under `app/`, `research/`, `docs/methodology/`, `docs/adr/`,
or `tests/`.

**Hero** (`InflationHero.tsx`): the canonical `state` is now the page's
single dominant object -- a large (`Badge` size `xl`, newly added
alongside the existing `md`/`lg`) tone-colored pill, with "Core PCE ·
{period}" as a quiet subtitle beneath it. The previous giant standalone
12M number is gone from the top line; 3M/6M/12M now render as an
equal-weight, compact inline strip below the state instead of one
figure competing with it for attention. The detailed `MomentumMetrics`
section (with per-metric evidence) is unchanged and still lower on the
page -- nothing about it was removed, only de-duplicated against the
hero's now-lighter glance strip.

**What Changed** (`WhatChangedSection.tsx`): each subsection is now a
quiet left-border-accented block (`border-l-2`, colored by that
subsection's own current tone -- the same five-tone palette already
used everywhere else, never a new color system) instead of a run of
plain paragraphs. Metric rows render as a three-column CSS grid (field ·
previous → current · right-aligned delta) via `Fragment`-per-row
children of one grid container -- real column alignment across rows,
not per-row flex-wrap. 1M-field rows render visually muted relative to
3M/6M/12M, consistent with 1M's "context only" role elsewhere. The
headline sentence for each subsection (`"State remains Mixed."` /
`"Core PCE state: Stable → Cooling"` / `"Confirmation: Confirms →
Diverges"` / `"No canonical changes detected."` / `"Previous-period
comparison unavailable."`) is unchanged text, only styled with a
tone-colored, semibold treatment when it reports an actual state/
relationship (muted gray for the two "nothing to report" messages).
Event-determination logic, precedence, and every exact string were left
untouched -- confirmed by the one test that legitimately needed
updating: a previous/current/delta assertion that used to match three
separate text nodes now matches one grid cell's combined text (the
delta's display format also changed from parenthesized to a plain
right-aligned `+0.20 pp`, matching the new column).

**Confirmation** (`ConfirmationPanel.tsx`): relabeled so `INCONCLUSIVE`
(or any relationship) reads unambiguously as Core CPI's own confirmation
status, not the whole monitor's -- a "Core CPI confirmation" eyebrow
label now sits directly above the relationship badge, with "Core CPI
state" and "Confirmation period" as their own labeled fields below.
"Core PCE is primary. Core CPI confirms or diverges from it." is
unchanged. No semantic change to the relationship itself or to
`confirmation_available`/`UNAVAILABLE` handling.

**Target/level, headline context**: left effectively as-is per the
task's own instruction (Target already worked well; only a spacing
tweak for consistency with the new label rhythm elsewhere). Headline
context's two independent cards and independent periods are unchanged
-- still no aggregation.

**Visual system**: top-level page sections (`Inflation.tsx`) now use a
`divide-y` border between sections instead of pure vertical spacing, for
clearer section separation without adding cards, shadows, or gradients.
No new Tailwind utility class categories were introduced beyond what the
existing restrained palette already used (the same five tones, now also
expressed as plain text-color and border-color variants in
`lib/inflationLabels.ts`'s new `TONE_TEXT_CLASSES`/`TONE_BORDER_CLASSES`
alongside the existing `TONE_CLASSES`).

**Verification**: `npx vitest run`, twice -- **110 passed** both times
(one test updated for legitimately-changed presentation markup, per the
task's own instruction; no test weakened, none of the 40 originally
enumerated behavioral scenarios lost coverage). `npm run typecheck`:
clean. `npm run lint`: clean. `npm run build`: succeeds. Backend:
`TEST_DATABASE_URL=... .venv/bin/pytest tests/ -q` -- **604 passed**,
confirming zero backend regression from a presentation-only change.
`no-economic-logic.test.ts` (unmodified from #16B, still guarding
against reimplemented delta/tone-derivation/period-selection logic):
green against all 30 scanned files, including every file this pass
touched. Manually verified in the browser against the populated
development database (see prior session): hero, What Changed, target,
confirmation, and headline context all render as designed with no
console errors; evidence disclosures and the "Latest revised data" note
still toggle correctly.

No architecture doc update was needed -- this pass changed no data flow,
no component boundary, and no endpoint; `current-architecture.md`'s
"Frontend architecture" section already documents the same component
list and page composition this pass refined the styling of.

## Increment #17 — Release Intelligence: Architecture Audit and Frozen Spec

Two-part, documentation-only increment. No production code, migration,
test, or frontend file was touched at any point -- confirmed both times
by `git status` scoped to `app/`, `frontend/`, `tests/`, `research/`.

**Part 1 (audit)**: a read-only architecture audit of the repository
(`app/clients/fred.py`, `app/db/models.py`,
`app/repositories/series_repository.py`, `app/services/`, `alembic/`,
`docs/adr/`, `tests/`, and more) against the product's stated long-term
intent for release intelligence (what's coming up, what was just
released, did new data actually appear, what changed as a result).
Grounded every recommendation in an actual existing convention rather
than a generic best practice: extending `FREDClient` instead of a new
provider abstraction (ADR-004's own stated reversal condition, not yet
triggered), an internal-ID-vs-provider-ID split (mirroring
`EconomicSeries.id`/`series_id`), derived-not-persisted status
(mirroring `app/domain/`'s pure-function convention), and a static
AST-based test guard already in `tests/integration/test_transaction_and_safety.py`
as the direct precedent for structurally forbidding release code from
touching canonical observations. One question was explicitly left
open rather than guessed at: whether FRED's release-dates API exposes
a stable per-occurrence identifier -- flagged as a blocking
verification item rather than assumed either way, since static
inspection of the (nonexistent) client method couldn't answer it and a
live call was out of the audit's scope.

**Part 2 (freeze)**: the open FRED question was independently verified
against FRED's official API documentation and the spec was frozen with
several corrections that *narrow* the audit's own proposal, not extend
it:

- `fred/release/dates` returns `(release_id, date)` only -- no stable
  per-occurrence ID, confirming the audit's fallback identity strategy
  as the *only* strategy, not one of two options.
- FRED's data is date-only, not time-of-day -- `scheduled_at`,
  `source_timezone`, and any time-precision field are removed from
  #17A entirely (the audit had proposed them as always-present-but-
  often-null columns; the frozen spec has no such columns at all).
  `CANCELLED` and `UNKNOWN` schedule statuses, and `published_at`, are
  likewise dropped -- none are reliably sourceable from FRED's
  date-only feed in #17A, and inventing any of them would violate the
  new, explicit "missing precision stays explicit, never fabricated"
  invariant.
- `ReleaseSeriesMapping` is deferred to #18 entirely (the audit had
  scoped it into #17A) -- #17A's calendar functionality doesn't need
  it, and `EconomicSeries` rows depend on ingestion state, which
  release-calendar persistence should not be coupled to.
- The API surface is narrowed to one endpoint, `GET /api/v1/releases`,
  with `/upcoming`/`/recent` explicitly pushed to be frontend views
  over date-range filters rather than separate backend routes (the
  audit had left this as an open evaluation; the freeze decided it).
- `classify_schedule_status` must take `as_of_date` as an explicit
  parameter, never read the system clock internally -- stated as a
  hard requirement, not left as a testing-strategy suggestion.

Result: `docs/architecture/release-intelligence-v1.md` (status: FROZEN
FOR #17A/#17B), covering purpose, permanent invariants, verified source
limitations, the `EconomicRelease`/`ReleaseOccurrence` contracts,
occurrence identity, derived status semantics, idempotent sync
semantics, the API contract, failure isolation, a worked shutdown/
missing-data example, frozen #17A/#17B scope, explicitly deferred #18
scope, the news boundary, deferred time/provider enrichment, and an
acceptance-invariant checklist for whoever implements #17A/#17B.

Two ADRs, not three -- the audit's proposed "B" (date-level occurrence
identity, no invented time) and "C" (extend `FREDClient`, no provider
abstraction yet) were merged into one
([ADR-020](adr/020-fred-v1-date-level-releases-no-provider-abstraction.md))
on the judgment that both are the same underlying decision -- "don't
model or build for a FRED capability that doesn't exist" -- applied to
the data model and the client code respectively; splitting them would
have been two ADRs for one judgment call. "A" (the permanent
calendar/observation separation) got its own ADR
([ADR-019](adr/019-release-calendar-structurally-separate.md)) because
it's a different kind of decision -- a permanent invariant that outlives
#17A specifically, not a V1-scoped implementation choice.

`docs/architecture/current-architecture.md`'s "Future direction"
section gained one paragraph pointing at the frozen spec and both new
ADRs, mirroring exactly how the Inflation Monitor methodology was
introduced there before Increment #14 implemented it -- no other
change to that document, since nothing about the actually-running
architecture changed.

### Verification

No backend, frontend, test, or research file was created or modified --
only `docs/architecture/release-intelligence-v1.md` (new),
`docs/adr/019-*.md` (new), `docs/adr/020-*.md` (new),
`docs/architecture/current-architecture.md` (one paragraph appended),
and this journal entry. No migration run, no dependency added, no live
FRED call made, no secret read.

### Deferred to #17A (implementation, not yet authorized)

Everything in `release-intelligence-v1.md`'s §12: the actual
`EconomicRelease`/`ReleaseOccurrence` SQLAlchemy models, migration,
repository, service, `FREDClient` extension, `GET /api/v1/releases`
route, and full test suite (pure domain, repository/service
integration, HTTP, provider-client, and an extended architectural
guard). #17B (the `/releases` frontend page) and #18 (release-driven
observation updates, monitor recomputation, release-driven What
Changed) remain further out, per the frozen spec's own explicit scope
boundaries.

## Increment #17A — Release Intelligence Backend Foundation

Implements the frozen spec's #17A scope exactly (see
`docs/architecture/release-intelligence-v1.md` §12), narrowed by one
real gap the frozen spec left open: it never named actual curated
release names or FRED `provider_release_id` values. Per the task's own
explicit instruction ("do not guess them; no implementation
workaround"), the migration creates the schema with **zero seed rows**
-- the curated catalog is a real gap, not a placeholder decision made
here. Everything else -- schema, domain, client, repository, service,
API, and a full test suite -- is implemented, tested, and green.

### Schema

Two tables, `alembic/versions/42114760e4c8_*.py` (revises the existing
single migration; downgrade verified clean both directions;
`alembic check` confirms zero drift between the ORM models and this
migration):

- `economic_releases` (`id`, `name`, `provider`, `provider_release_id`,
  `official_url` nullable, `active`, `created_at`, `updated_at`) --
  `UNIQUE(provider, provider_release_id)`.
- `release_occurrences` (`id`, `economic_release_id` FK `ON DELETE
  CASCADE`, `scheduled_date`, `first_seen_at`, `last_seen_at`) --
  `UNIQUE(economic_release_id, scheduled_date)`, indexed on the FK.
  Deliberately no `scheduled_at`/`source_timezone`/`time_precision`/
  `cancelled_at`/`published_at`/`data_status`/`analysis_status` column
  -- exactly the frozen spec's #5, none invented.

Both classes follow `EconomicSeries`/`EconomicObservation`'s existing
conventions verbatim (internal `id` vs. business identity kept
separate, explicit non-ambiguous FK naming, `DateTime(timezone=True)`
+ `server_default=func.now()`, cascade delete matching the existing
precedent).

### Domain

`app/domain/releases.py`: `classify_schedule_status(scheduled_date,
as_of_date) -> Literal["SCHEDULED", "PAST_DUE"]`. Pure; `as_of_date` is
always an explicit parameter (proven by a signature-inspection test
that it has no default, plus a source-text guard that neither
`today(` nor `now(` appears anywhere in the module). Registered in
`tests/test_domain_architectural_independence.py`'s `DOMAIN_FILES` --
the existing generic allowlist test (stdlib + `app.models.*` only)
applies to it automatically, so it's structurally incapable of
importing SQLAlchemy, FastAPI, httpx, or any other domain module, not
just conventionally discouraged from it. No `CANCELLED`/`UNKNOWN` --
the frozen spec's own reasoning (no reliable cancellation signal in
#17A; no occurrence is ever missing a date) held up under
implementation with no contradiction found.

### FRED client

`FREDClient.get_release_dates(release_id) -> list[FredReleaseDate]`
(new `app/clients/fred.py` dataclass, `release_id`+`date` only) --
requests `include_release_dates_with_no_data=true` so scheduled/
upcoming occurrences are actually visible, not just past ones with
data already attached. Normalizes at the client boundary as the frozen
spec requires: FRED's `release_name`/`realtime_start`/`realtime_end`/
`release_last_updated` never cross it. Malformed/missing
`release_id`/`date` raises `FREDUpstreamError` (same convention as
`EconomicDataService.get_series`'s existing malformed-response
handling); an empty `release_dates` list is a normal, successful `[]`.
No `get_release_series` method, no provider abstraction -- exactly the
frozen spec's #9/ADR-020.

### Repository and services

`ReleaseRepository` (`app/repositories/release_repository.py`):
`get_active_releases`, `get_release_by_provider_identity`,
`upsert_occurrence` (idempotent -- lookup by `(economic_release_id,
scheduled_date)`, refreshes only `last_seen_at` on a repeat, preserves
`first_seen_at`, never deletes), `list_occurrences`
(filter/order/paginate, joined to the release, deterministic tie-break
by `name` then `id` since `scheduled_date` alone isn't unique across
releases). Never imports `app.clients.fred`/`httpx` at all -- checked
structurally, not just by the general FRED/AI import guard every other
integration test file already respects.

`ReleaseReadService`/`ReleaseSyncService`
(`app/services/releases.py`) are deliberately two separate classes,
not one with an optional `FREDClient` (the `EconomicDataService`
pattern): `ReleaseReadService` has no FRED-shaped parameter anywhere on
it at all, proven by a test that inspects every public method's
signature. `ReleaseSyncService.sync_all` iterates only
`active=true` releases, in deterministic name order, and degrades
per-release (mirrors `SeriesDiscoveryService.search`'s existing FRED-
failure-degrade pattern) -- one release's `FREDAuthError`/
`FREDTimeoutError`/`FREDUpstreamError` never aborts the others, and the
route still returns `200` with that release under `failed`, using a
safe, generic message per failure kind (never the raw exception text,
which could in principle echo upstream content).

### API

`GET /api/v1/releases` (`app/api/releases.py`) -- filters
`start_date`/`end_date`/`limit` (1-1000)/`offset`/`order`
(`asc`/`desc`), reusing the exact `Query(...)` bounds and
`InvalidDateRangeError` → `400` pattern `.../observations` already
established. Database-only: `as_of_date` is resolved once at the route
boundary (`datetime.now(timezone.utc).date()`) and passed explicitly
into the service/domain call -- never read a second time, never read
inside `classify_schedule_status` itself. `POST /api/v1/releases/sync`
mirrors `POST /series/{id}/sync`'s shape, widened to the whole curated
catalog (no single-release entry point makes sense from the frontend).
Both mounted under `/api/v1` in `app/main.py`.

### Failure isolation

Exactly the frozen taxonomy, no new codes invented: unconfigured/DB-
unavailable → `503`, semantic bad date range → `400`, malformed query
params → `422` (FastAPI/Pydantic validation, for free), other DB error
→ `500`; sync-only: `FREDAuthError`→ per-release failure entry (not a
route failure), `FREDTimeoutError`/`FREDUpstreamError` likewise. Proven
directly: `GET /releases` still returns `200` with `patch.object(FREDClient,
"__init__", side_effect=AssertionError(...))` in effect -- if the read
path ever tried to construct a client, the test would fail immediately
rather than merely passing by coincidence.

### Shutdown invariant

`tests/integration/test_release_shutdown_invariant.py` is a dedicated,
non-inflation-domain regression test: persist one occurrence at the
real October 2025 CPI-style date, move `as_of_date` past it (status
derives to `PAST_DUE`), assert zero `EconomicObservation` rows exist
before and after, and assert the occurrence's own `scheduled_date` is
unchanged. Nothing about this test exercises `inflation_v1.0` -- it
proves the tables never move, which is the actual invariant.

### Tests

77 new tests (604 → **681**, run twice, deterministic both times):
pure domain (`tests/test_domain_releases.py`), FRED client unit tests
mocked at the `httpx.Client.get` transport boundary
(`tests/test_fred_client.py` -- the first direct `FREDClient` unit
test file in this project; every prior FRED-touching test mocked at
the method level instead, one layer up), repository integration
(`tests/integration/test_release_repository.py`), service integration
(`tests/integration/test_release_calendar_service.py`, added to
`test_transaction_and_safety.py`'s `NETWORK_EXCEPTIONS` alongside
`test_discovery_service.py`), the dedicated shutdown-invariant test,
and HTTP tests (`tests/api/test_releases_api.py`, needing a new
`release_seed_session` fixture in `tests/api/conftest.py` -- same
real-commit-plus-TRUNCATE pattern as the existing `seed_session`,
scoped to `release_occurrences`/`economic_releases`).
`test_transaction_and_safety.py` also gained
`TestReleaseCalendarStructuralIndependence`: an AST import guard
proving `app/repositories/release_repository.py`,
`app/services/releases.py`, and `app/api/releases.py` never import
AI/`app.services.economic_data`/`app.repositories.series_repository`/
`app.services.inflation`/`app.domain.inflation`/news -- the permanent
invariant checked structurally, not left to code-review vigilance.

### Verification

`TEST_DATABASE_URL=... .venv/bin/pytest tests/ -q`, run twice: **681
passed** both times, 0 skipped. `alembic upgrade head` /
`alembic downgrade -1` / `alembic upgrade head` against the isolated
test database: clean both directions. `alembic check`: no drift. `git
status` confirms zero changes under `frontend/`, `research/`,
`docs/methodology/`, or any AI file (`app/services/ai*.py`,
`app/api/ai.py`, `app/models/ai.py`). No secret read, printed, or
logged anywhere.

### Live smoke check: skipped, honestly

The curated catalog is empty (see above), so `ReleaseSyncService.sync_all`
against the real development database would trivially iterate zero
releases -- not a meaningful smoke check of the FRED-calling code path.
Seeding one temporary release to make the check meaningful would
require a real FRED `provider_release_id`, which is exactly the value
this increment declined to guess. Skipped rather than worked around.

### Deferred (unchanged from the frozen spec's own scope discipline)

No `ReleaseSeriesMapping`, no observation-availability check, no
scheduler, no monitor recomputation, no AI, no news, no `/releases`
frontend route -- all remain #18/#17B, not designed or implemented
here.

### Outstanding before this capability is reachable end-to-end

The curated release catalog itself: exact release names and FRED
`provider_release_id` values, to be supplied and seeded via a follow-up
migration. Nothing else blocks it -- schema, sync, read, and status
derivation are all implemented and fully tested against synthetic
fixture data.

## Increment #17A follow-up — Curated Catalog Blocker Resolved

Resolves the one open item from the entry above. The six V1 provider
release IDs were independently verified against official/current FRED
release pages (verification happened outside this session; this
follow-up only implements the already-approved result) and supplied
explicitly:

| Release | `provider_release_id` |
|---|---|
| Consumer Price Index | `10` |
| Personal Income and Outlays | `54` |
| Employment Situation | `50` |
| Job Openings and Labor Turnover Survey | `192` |
| Gross Domestic Product | `53` |
| Advance Monthly Sales for Retail and Food Services | `9` |

All `provider = "FRED"`, `active = true`, `official_url = NULL` (not
separately verified/frozen -- name + provider + provider_release_id
alone are sufficient to unblock this; inventing a URL was explicitly
out of scope). FOMC, PPI, Industrial Production, housing releases, and
Initial Claims were deliberately excluded from this V1 set -- may be
curated later, in their own migration.

### New migration, existing one untouched

`alembic/versions/fbbe6b1ab8d9_seed_curated_v1_release_catalog.py`,
`down_revision = 42114760e4c8` (the existing #17A schema migration,
which this follow-up does not modify -- confirmed via file hash/line
count before and after this session touched anything else). Product
curation is kept in its own migration, separate from schema creation,
on purpose: the catalog can be re-curated later without ever touching
a table definition again. Literal seed data only (`op.bulk_insert`
against a migration-local `sa.table()` shim, not the ORM model, so this
migration stays correct even if `EconomicRelease`'s shape changes
later) -- no FRED call, no dynamic discovery, no environment read, no
`ReleaseOccurrence` rows created. Downgrade removes only the six rows
it seeded, matched by their exact `(provider, provider_release_id)`
pairs -- never a blanket `DELETE FROM economic_releases`, so an
unrelated release row (if one existed) would survive a downgrade
untouched. (If occurrences existed for one of these six at downgrade
time, the existing `ON DELETE CASCADE` FK from 42114760e4c8 would
remove them along with the release -- documented as the already-
established constraint's behavior, not something this migration adds;
isolated verification ran with zero occurrences present, as
instructed.)

### A real gap this follow-up found and fixed: test isolation from persistent seed data

Adding real, permanent baseline rows to `economic_releases` broke an
assumption every #17A test silently depended on: that the table starts
empty. Two distinct problems, both fixed:

1. **Identity collisions.** Every #17A test's `_release()`/`_seed_release()`
   helper defaulted to (or explicitly passed) `provider_release_id="10"`
   -- which now collides with the real, migration-seeded Consumer Price
   Index row's `UNIQUE(provider, provider_release_id)` constraint.
   Fixed by moving every test-created release to a `provider_release_id`
   well outside the curated range (`"9001"`+, curated range is
   `9`/`10`/`50`/`53`/`54`/`192`).
2. **`get_active_releases()`/`sync_all()` now see six extra real, active
   rows.** Tests asserting an exact active-release set or an exact sync
   result needed to either explicitly deactivate the curated catalog
   first (safe in `tests/integration/`: `db_session` rolls the whole
   transaction back at teardown, so a deactivation never leaks into
   another test) or assert containment/exact-set against the *known*
   curated names rather than assuming emptiness. `tests/api/conftest.py`'s
   `release_seed_session` fixture needed a real fix, not just a test-
   level one: its cleanup already couldn't blanket-`TRUNCATE
   economic_releases` (that would erase the persistent curated catalog
   for the rest of the session, since migrations only run once per
   pytest session) -- it now deletes only non-curated rows *and*
   restores `active=true` on the curated six, so a sync test that
   deliberately deactivates them to isolate itself can never leak that
   into the next test. This fixture bug was caught the hard way: an
   earlier, uncorrected version of it left the real database in a
   deactivated state via a genuine commit, breaking three unrelated
   tests in the next run until traced back and the test database's
   catalog was restored via a clean migration downgrade/upgrade cycle.
   Recorded here as a real lesson, not smoothed over: adding baseline
   seed data to a previously-empty table needs its test fixtures
   audited for exactly this class of bug, every time.

Also added: direct proof (not just inference) that the six real
curated rows exist, are exactly these six, are all `provider="FRED"`
and `active=true`, and that `ReleaseSyncService.sync_all` against the
real (undeactivated) curated catalog attempts exactly these six release
names and no others -- at the repository, service, and HTTP layers.

### Tests added/modified

5 new tests (686 total): `test_curated_catalog_is_active_by_default`,
`test_finds_a_real_curated_release_by_provider_identity`,
`test_unique_provider_identity_is_enforced_against_the_curated_catalog_too`
(`tests/integration/test_release_repository.py`);
`test_syncs_exactly_the_six_curated_releases_when_active`
(`tests/integration/test_release_calendar_service.py`);
`test_curated_catalog_is_what_gets_synced_when_active`
(`tests/api/test_releases_api.py`). No existing assertion was weakened
-- every fixed test still asserts the same behavior it always did, just
against a `provider_release_id` that can't collide with real seed data,
or with the curated catalog explicitly isolated where the test's own
premise required an exact, closed set.

### Migration round-trip verification

Against the isolated test database: `upgrade head` (six rows present,
exactly these six) → `downgrade -1` (all six removed, schema/other
tables fully intact) → `upgrade head` again (six rows return exactly
once, no duplicates) → `alembic check` ("No new upgrade operations
detected" -- zero model/schema drift). All four steps run clean.

### Full regression

`TEST_DATABASE_URL=... .venv/bin/pytest tests/ -q`, run twice (plus
once more after the final clean migration re-verification, for extra
confidence following the fixture bug above): **686 passed** every time,
0 skipped.

### Live smoke check: performed

The already-configured development environment safely supports FRED
(key presence checked as a boolean only, never read/printed). Applied
`alembic upgrade head` to it (a plain forward upgrade -- not the
destructive round-trip testing that stayed confined to the isolated
test database), then called the real, running server's
`POST /api/v1/releases/sync`:

| Release | `provider_release_id` | Occurrences persisted | Earliest | Latest |
|---|---|---|---|---|
| Consumer Price Index | 10 | 953 | 1949-03-24 | 2026-12-10 |
| Personal Income and Outlays | 54 | 744 | 1966-01-18 | 2026-12-23 |
| Employment Situation | 50 | 867 | 1955-05-06 | 2026-12-04 |
| JOLTS | 192 | 196 | 2010-08-11 | 2026-12-01 |
| Gross Domestic Product | 53 | 867 | 1947-07-20 | 2026-12-23 |
| Advance Monthly Retail Sales | 9 | 758 | 1966-01-10 | 2026-12-16 |

All six synced, zero failures. Confirmed
`GET /api/v1/releases?start_date=2026-08-01&end_date=2026-12-31` then
returns exactly these persisted occurrences, correctly split between
`PAST_DUE` (e.g. 2026-09-11 CPI) and `SCHEDULED` (e.g. 2026-09-16
Advance Retail Sales) around the real current date -- a live,
end-to-end confirmation of the derived-status boundary the domain unit
tests already covered synthetically. No API key, `DATABASE_URL`,
secret-bearing URL, or raw provider payload was reported or logged
anywhere in this process.

### Scope confirmation

Zero changes to `frontend/`, `research/`, `docs/methodology/`, or any
AI file. Still no `ReleaseSeriesMapping`, `scheduled_at`,
`source_timezone`, `published_at`, `data_status`, `analysis_status`,
scheduler, news integration, observation-availability logic, or
monitor recomputation anywhere in the codebase -- confirmed by direct
grep across every #17A production file, not just by omission.

## Increment #17B — Release Intelligence UI

Presentation only, on top of #17A's `GET /api/v1/releases`. Zero
backend production changes -- the existing read contract
(`ReleaseOccurrenceItem`/`PaginationMeta`/`ReleaseListResponse`) was
already sufficient for the frozen #17B experience, so no
"STOP -- BACKEND CONTRACT GAP" was ever reached. This increment picked
up an in-progress session that had completed exactly one file
(`frontend/src/api/releases.types.ts`) before hitting a usage limit --
that file was re-verified field-for-field against `app/models/releases.py`
(it was already correct and complete: no derived status logic, no
invented fields) and kept unchanged; everything else below was built
fresh in this session.

### Route, navigation, and page structure

`/releases` (`pages/Releases.tsx`), added to `App.tsx`'s route table
and `AppShell.tsx`'s primary nav (`"Releases"`, after `"Inflation"`).
One page, not tabs -- **Upcoming Releases** then **Recent Releases**,
in that order, matching `/inflation`'s existing header/disclosure/
`divide-y`-separated-sections structure exactly so the two pages read
as the same product. The mandated disclosure ("Release dates indicate
scheduled publication dates. They do not confirm that new data has
been published, ingested, or reflected in Economic Intelligence
analysis.") renders permanently visible and visually secondary (small,
muted text under the page subtitle) -- unlike `/inflation`'s
methodology note, this one is load-bearing for the whole page's
meaning, so it is never hidden behind a disclosure toggle.

### Typed API contract

`api/releases.types.ts` (pre-existing, verified) +
`api/releases.ts` (new): `getReleases(params)` on the existing
`apiGet<T>` foundation, plus two named fetchers,
`fetchUpcomingReleases`/`fetchRecentReleases`, mirroring
`api/inflation.ts`'s own pattern of exporting stable, zero-argument
functions `useApiResource` can take directly. No `any` anywhere
(enforced by the existing strict `tsconfig`). Only the read contract is
mirrored -- `ReleaseSyncResponse` and friends are deliberately not
modeled here at all, since nothing in this increment's import graph
could ever construct a request to that endpoint.

### Upcoming/Recent query windows (product default, not frozen by the spec)

`docs/architecture/release-intelligence-v1.md` §13 leaves the exact
window to a "clear bounded product default" -- none is frozen. Chosen
here: **Upcoming = today through +45 days** (ascending), **Recent =
-30 days through today** (descending), computed by
`lib/releases.ts`'s `upcomingWindow`/`recentWindow` (pure, explicit
`today` parameter, defaulting to the real current date -- this is
UI/query-window logic only, never a canonical calculation, so unlike
`classify_schedule_status` a default is appropriate here). Sized
against the real curated catalog before choosing a `limit`: the six
curated releases produced 7 occurrences in the upcoming window and 6 in
the recent window on the day this was checked against the synced
development database -- both comfortably inside the request's
`limit=100` (the backend's own default), so V1 needs no "Load more" UI
at all; both windows fit in one request with wide headroom.

### Date and status semantics

Every `schedule_status` badge renders the backend's own value verbatim
("Scheduled"/"Past due") -- proven directly with tests where a
*future*-dated release carries `PAST_DUE` and a *past*-dated release
carries `SCHEDULED` from the mock, and the UI shows exactly what the
backend said in both cases, never "correcting" it. Dates render via a
compact "SEP 17" badge (`components/releases/ReleaseDateBadge.tsx`,
wrapped in a real `<time dateTime="...">` element) plus a full
accessible date via `aria-label`/`title` -- no time of day, no
timezone, no countdown, no "released X hours ago" anywhere (checked by
a page-level test asserting no `HH:MM` pattern renders at all). No
"Today" display enhancement was implemented -- the task framed it as
strictly optional ("acceptable ONLY IF..."), and skipping it entirely
avoids any risk of the accompanying precision requirement being
implemented sloppily; the compact month/day badge is already fully
precise on its own.

### Presentation-only label and category maps

`lib/releasePresentation.ts`: a short display label for the two
curated releases whose canonical name is genuinely long ("Job Openings
and Labor Turnover Survey" -> "JOLTS", "Advance Monthly Sales for
Retail and Food Services" -> "Advance Retail Sales") plus a small
"GDP" shortening for Gross Domestic Product, and the requested
economic-category tag for all six curated releases (Inflation, Inflation
/ Consumer, Labor ×2, Growth, Consumer). Keyed by the backend's own
stable `provider_release_id`, never by matching on `name` text. Every
lookup falls back to the real canonical `name` for anything not in the
map (including a future release curated later that this map hasn't
been updated for). Where a name is shortened, the row's accessible name
(`aria-label`) is always the full canonical name -- proven by a
dedicated test. Considered, and rejected, keeping this out of scope
entirely: the map creates no coupling to #18 because it answers a
different question (which UI category badge does a release show) than
#18's eventual release-to-series mapping will (which series prove this
release's data actually arrived) -- the two never share code, a type,
or a lookup key.

### Data fetching, loading, empty, and error states

`useApiResource` reused unmodified, instantiated twice -- Upcoming and
Recent load, fail, and retry completely independently, the same
partial-failure resilience `/inflation` already established (proven
directly: Upcoming failing renders Recent normally and vice versa, in
both directions). A successful empty result ("No scheduled releases in
this window." / "No recently scheduled releases in this window.")
renders as plain text, never as an error (`role="alert"` never
appears for an empty-but-successful response) -- the same
infrastructure-failure-vs-empty-result distinction `/inflation`
already draws between `ApiError` and a canonical
`INSUFFICIENT_DATA`-shaped 200.

### Grouping

`lib/releases.ts`'s `groupReleasesByDate` groups adjacent
same-`scheduled_date` releases under one date badge (e.g. GDP and
Personal Income and Outlays, which shared a real scheduled date in the
synced development data) -- display-only, never re-sorts (the backend's
own `order` parameter already produced the chronology), and preserves
each date's items in exactly the order the backend returned them.

### Architectural guard

`test/no-release-sync-or-coupling.test.ts`: scans every file whose path
contains "release" (narrow, not a broad-word grep) for two things --
the sync endpoint path never appears anywhere, and no import references
inflation, AI, or news code. Also checked directly:
`grep -rn "releases/sync" frontend/src/` and a `POST` scan across the
release-specific files both return zero matches.

### Tests

98 new tests (110 -> **208**): `lib/releases.test.ts` (window math with
explicit reference dates, grouping, compact/full date formatting),
`lib/releasePresentation.test.ts` (short labels, categories, canonical
fallback, non-mutation), `api/releases.test.ts` (exact query-string
construction, GET-only, never `/sync`), `pages/Releases.test.tsx` (the
integration suite -- ordering, both statuses from the backend directly,
same-day-SCHEDULED not overridden, empty/loading/error per section,
both partial-failure directions, forbidden-language scan scoped around
the one sanctioned disclosure sentence, no time-of-day anywhere,
presentation labels and their accessible names, heading/landmark
structure), plus the architectural guard above and two `App.test.tsx`
routing/nav additions. One real bug caught while writing these: the
architectural guard's own regex tripped on this increment's *own*
source comments explaining that these files never call sync (the
literal URL substring appeared in prose, not code) -- fixed by
rewording the comments, the same fix already applied to an analogous
false positive in Increment #17A's domain guard test, not by weakening
the guard.

### Verification

Frontend: `npx vitest run`, run twice: **208 passed** both times.
`npm run typecheck`: clean. `npm run lint` (`oxlint`): clean.
`npm run build`: succeeds. Backend:
`TEST_DATABASE_URL=... .venv/bin/pytest tests/ -q`: **686 passed**, 0
skipped -- unchanged from the #17A baseline, since no backend file was
touched.

### Visual review

Checked live against the already-synced development database (desktop
width): hierarchy, grouping, category tags, short labels, and both
status tones render exactly as designed, with real data (Upcoming
showing Sep 16 Advance Retail Sales through mid-October; Recent showing
Sep 11 CPI back through Aug 14, newest first). Narrow/mobile-width
visual verification could not be completed in this session -- the
browser automation's window-resize did not actually change the
viewport's reported width in this environment (the same limitation
already noted in the Increment #16B.1 visual-polish entry), so no
narrow-viewport screenshot was captured. Responsive safety for the new
markup instead rests on reusing the identical Tailwind flex/wrap
patterns (`flex-none` fixed-width date badge, `min-w-0 flex-1` content
column, `flex-wrap` metadata line) already verified not to overflow on
`/inflation`.

### Deferred (unchanged from the frozen spec's own scope discipline)

No charts, no polling/auto-refresh, no sync call from the browser, no
`ReleaseSeriesMapping`, no observation-availability inference, no
monitor recomputation, no AI, no news -- all remain #18/#20, not
designed or implemented here.

## Increment #17C — Explainability & Economic Education UX Foundation

Not an AI feature. A reusable, product-wide explanation system so a
beginner can learn Economic Intelligence's concepts from the product
itself while an experienced user can keep scanning without being
slowed down -- built once and used to improve exactly two surfaces,
Inflation and Releases, establishing the pattern rather than exhausting
it. The product principle this increment exists to serve: explain
**what it is, what it means, why it matters, why EI reached the
result, how it was calculated, and what evidence supports it** -- using
progressive disclosure, never turning a primary screen into a textbook.
Zero backend changes (verified: this increment's diff touches nothing
outside `frontend/`); zero AI; zero new economic logic. Read first, in
full, before any code: `current-architecture.md`, `request-flows.md`,
this journal's #16B/#16B.1/#17B entries, `inflation-monitor-v1.0.md`,
`inflation-what-changed-v1.0.md`, `release-intelligence-v1.md`, and the
actual rendered `/inflation` and `/releases` pages -- not designed from
the spec text alone.

### The one architectural rule everything else follows from

**Explanations never determine canonical results.** Facts are sourced.
Calculations are deterministic. Canonical classifications are
deterministic. Explanations describe those results. Dependency
direction is one-way: `canonical backend result -> frontend
presentation -> curated explanation content`. Nothing in
`content/explanations/` or `components/explanations/` may flow back
into a calculation, a classification, or a mutation of an API result --
enforced by a dedicated architectural guard (below), not just asserted
in prose.

### Content model: one shape, two uses

`content/explanations/types.ts` exports a single `Explanation` type --
`{ id, title, definition, whyItMatters?, sourceNote? }` -- deliberately
smaller than the shape suggested in the originating task (no
`interpretationNotes`; `methodologyReference` renamed `sourceNote` to
also cover "Source: FRED release calendar", which isn't a methodology).
There is no separate "result explanation" type. A **concept
explanation** (e.g. "What is Core PCE?") and a **result explanation**
(e.g. "Why is momentum MIXED?") are both just `Explanation` objects --
the only difference is a result explanation is looked up by the
backend's own already-classified value (`state`, `schedule_status`) and
rendered alongside backend evidence a component already has, in
`components/inflation/WhyThisState.tsx`, rather than shown standalone.
Two content files hold the curated copy: `content/explanations/
inflation.ts` (14 standalone concepts + a `state ->
Explanation` lookup for all five `InflationState` values) and
`content/explanations/releases.ts` (2 standalone concepts + a `status
-> Explanation` lookup for both `ScheduleStatus` values + a
`provider_release_id -> Explanation` lookup for the six curated V1
release types) -- 19 and 10 concepts respectively, matching the task's
required lists exactly. All copy grounded directly in
`inflation-monitor-v1.0.md`'s classification rules (re-verified by
reading that document, not assumed) and in each release's actual
BLS/BEA/Census definition; nothing paraphrases a threshold differently
than the frozen spec states it.

### The reusable UI primitive

`components/explanations/ExplanationTrigger.tsx`: a compact "i" circle
next to a `<details className="group inline-block align-middle">` /
`<summary aria-label="What does {title} mean?">` -- the same native,
zero-dependency disclosure primitive `components/Disclosure.tsx`
already established for "Latest revised data", styled for inline
placement next to a label rather than Disclosure's block-level
treatment. No new UI library was added (none was needed): click or
keyboard (Enter/Space, native to `<summary>`) toggles it, content
expands in normal document flow (never an absolutely-positioned
popover, so it can never cause horizontal overflow on a narrow
screen), and `aria-expanded` is exposed to assistive tech automatically
by the browser's own `<details>` semantics -- the component manages no
open/closed state itself. `components/inflation/WhyThisState.tsx` is
the one place a *result* explanation composes backend evidence
(3M/6M/12M, neutral band) with a state's curated meaning instead of
using this generic concept trigger directly.

### The accessible-name/text-content bug, and the fix that generalizes

Integrating triggers into six inflation components and three release
components surfaced one real bug: nesting an interactive `<details>`
trigger (with visible "i" text and its own `aria-label`) as a **direct
child** of a heading or label element changes that ancestor's computed
accessible name *and* its raw `textContent`, via the DOM accname
algorithm -- silently breaking every exact-match
`getByRole("heading", { name: "Exact" })` / `getByText("Exact")` query
elsewhere in the suite that targeted that heading or label. First
integration pass caused widespread failures across both the Inflation
and Releases suites; the fix, applied everywhere, is now this project's
standing convention for any future explanation trigger: **the trigger
is always a DOM sibling of the text it annotates, wrapped together in a
plain flex `<div>`, never a descendant.** `components/releases/
ReleaseRow.tsx`'s pre-existing structure (label in its own `<span>`,
trigger as a sibling `<details>`) was already correct by accident and
needed no fix -- useful confirmation the sibling pattern is the right
default, not merely a workaround. A second, narrower issue followed
from the same trigger content now living in the DOM even while closed:
an `Explanation.title` can coincidentally match another element's own
visible text (`scheduleStatusExplanation("SCHEDULED").title ===
"Scheduled"`, identical to `ScheduleStatusBadge`'s own label), making
`getByText` ambiguous. Resolved with RTL's `{ selector: "span" }`
disambiguation (the Badge renders a `<span>`, the explanation panel
title a `<p>`) rather than adding `data-testid` (this project has never
used it, consistent with Testing Library's own guidance) -- and,
separately, `WhyThisState` deliberately never renders `explanation.title`
at all, avoiding the same class of collision against the primary state
Badge on `/inflation` before it could occur. One more nesting bug
surfaced only under a real browser render (not jsdom, which is
permissive about invalid HTML): `<details>` is block-level content and
cannot legally nest inside `<p>` per the HTML spec; `ReleaseRow.tsx`'s
two label rows were changed from `<p>` to `<div>` once they started
holding a trigger.

### Inflation integration

`InflationHero.tsx`: `MOMENTUM` explanation beside "Underlying
momentum", `CORE_PCE` beside the "Core PCE · {period}" line, and
`WhyThisState` rendered directly under the primary Badge (backend
evidence + the curated explanation for whatever `state` the backend
returned -- never recomputed). `MomentumMetrics.tsx`: `THREE_MONTH_ANNUALIZED`/
`SIX_MONTH_ANNUALIZED`/`TWELVE_MONTH` beside each of the 3M/6M/12M
cards. `TargetPanel.tsx`: `FED_OBJECTIVE` and `TARGET_DEVIATION` beside
"Fed objective" and "Gap". `ConfirmationPanel.tsx`: `CONFIRMATION`
beside "Core CPI confirmation"; `CORE_CPI` beside the Core CPI state
Badge. `HeadlineContext.tsx`: `HEADLINE_INFLATION` beside the section
heading; `PCE`/`CPI` beside their respective cards. `DataBasisNote.tsx`
rewritten to source both its paragraphs from `LATEST_REVISED_DATA`
instead of hardcoded strings -- the canonical sentence ("Historical
calculations use the latest revised observations available to Economic
Intelligence. They may differ from values originally reported at the
time.") is preserved byte-for-byte; only a new beginner-facing
`whyItMatters` paragraph was added alongside it. No vintage/as-known-
at-the-time capability is implied anywhere in that copy.

### Releases integration

`pages/Releases.tsx`: `ECONOMIC_RELEASE` beside "Economic Releases".
`ReleaseCalendarSection.tsx`: `SCHEDULED_DATE` beside each "Upcoming
Releases"/"Recent Releases" heading. `ReleaseRow.tsx`: a release-type
explanation (looked up by `provider_release_id`, `null` -- no trigger
-- for anything outside the curated V1 set) beside the release name,
and a status explanation beside the `ScheduleStatusBadge`. PAST_DUE's
explanation is exact-string tested end to end: *"The scheduled release
date has passed. This status does not confirm that new data has been
published, ingested, or incorporated into Economic Intelligence
analysis."* -- its one use of "published" is a negation, checked
directly (a regex count asserts exactly one occurrence, guarding
against a future edit accidentally adding an affirmative one).
SCHEDULED's explanation states only what the calendar has on file, with
no time-of-day precision, checked the same way.

### Architectural guards

Three layers, each proven by an executable test rather than by
convention alone: `test/no-economic-logic.test.ts` (pre-existing,
unmodified, but its recursive scan of all of `src/` already covers the
new `content/explanations/inflation.ts` and `WhyThisState.tsx` for the
annualization-exponent, neutral-band-arithmetic, delta-recomputation,
and confirmation-pair-literal shapes); `test/no-release-sync-or-
coupling.test.ts` (pre-existing, unmodified, its path-based "release"
scan already covers `content/explanations/releases.ts` and the release
components for the sync-endpoint and inflation/AI/news-import checks);
and a new `test/no-explanation-classification-logic.test.ts`, scoped
narrowly to `content/explanations/` + `components/explanations/` +
`WhyThisState.tsx`, checking each file imports no AI/LLM module, calls
no `fetch`/`axios`/sync endpoint directly, imports only API *types*
(never an API function) from `api/`, and never assigns into a
prop/parameter object. All three pass clean against the final tree.

### Tests

135 new tests (208 -> **343**): foundation
(`components/explanations/ExplanationTrigger.test.tsx` -- open/closed
by default, mouse and keyboard-reachability, title/definition/
whyItMatters/sourceNote rendering including their absence, multiple
independent triggers not colliding); content coverage
(`content/explanations/inflation.test.ts` and `.../releases.test.ts` --
every required concept present, non-circular, state copy grounded in
the frozen classification rules, PAST_DUE and the latest-revised-data
sentence checked byte-for-byte, no investment-recommendation language
anywhere); the result-explanation component
(`components/inflation/WhyThisState.test.tsx`, including **the
contradictory-evidence test**: a mock `SeriesMomentumResult` with
`state: "MIXED"` but `r_3m`/`r_6m`/`r_12m` all equal -- numbers a human
might read as STABLE -- and its mirror, `state: "STABLE"` with `r_3m`
far outside the band -- numbers a human might read as HEATING; in both
directions the component renders exactly the backend's own `state` and
nothing else, proving no reclassification happens in the frontend); the
new architectural guard; and integration additions to
`pages/Inflation.test.tsx`/`pages/Releases.test.tsx` (triggers present
and openable for the concepts each page surfaces, evidence values in an
opened `WhyThisState`/release-type panel traced to the exact fixture
values passed in, a page-level repeat of the contradictory-evidence
proof, SCHEDULED/PAST_DUE opened and checked verbatim, all six curated
release types opened and checked, no release-type trigger for an
uncurated release, canonical Badge text unaffected by whether any
explanation was ever opened).

### Verification

Frontend: `npx vitest run`, run twice: **343 passed** both times.
`npm run typecheck`: clean. `npm run lint` (`oxlint`): clean. `npm run
build`: succeeds. Backend:
`TEST_DATABASE_URL=... .venv/bin/pytest tests/ -q`: **686 passed**, 0
skipped -- unchanged, confirming zero backend impact (`git status`
shows every change confined to `frontend/`).

### Visual review

Checked live in a real browser (not jsdom) against the already-running
development backend, real synced data: `/inflation` with a genuine
`MIXED` reading (3M 3.05%, 6M 3.46%, 12M 3.34%, neutral band
3.24%–3.44% -- 3M below the band, 6M above it, a real-world instance of
exactly the contradictory-looking evidence the unit test constructs
synthetically) confirmed the page states MIXED, never reclassifying
toward COOLING or HEATING; every trigger on the page (`Underlying
momentum`, `Core PCE`, `Why Mixed?`, `Latest revised data`) opens
cleanly, non-overwhelming, non-floating, closes again on a second
click. `/releases` confirmed the GDP release-type panel and a real
PAST_DUE row's panel both render correctly with live data, the latter
showing the exact non-publication-claiming sentence. Narrow/mobile
visual verification could not be completed in this session -- the
browser automation's window-resize call reports success but does not
actually change the captured screenshot's viewport width in this
environment (the same limitation already noted in the #17B and #16B.1
journal entries). Responsive safety instead rests on inspecting the
actual markup: every trigger placement uses `flex`/`flex-wrap`/
`gap-1.5` with no fixed widths, the explanation panel itself is
`max-w-sm` in normal document flow (never `absolute`/`fixed`), and
`WhyThisState`'s evidence `<dl>` uses the same `grid-cols-
[max-content_1fr]` pattern already verified not to overflow elsewhere
on `/inflation`.

### Deferred (explicitly out of #17C's scope)

No documentation site, no account/beginner-mode preference, no
onboarding modal or forced tutorial, no AI-generated content of any
kind, no explanation coverage beyond Inflation and Releases -- the
pattern (content model + `ExplanationTrigger` + the sibling-placement
convention) is established here for later features to reuse, not
applied to every existing page in this increment.

## Increment #18 — Release-Driven Update Pipeline V1

Preceded by a dedicated, read-only architecture audit (no production
code touched) that surfaced the single finding this whole increment's
design hinges on: `GET /api/v1/monitors/inflation/changes` answers
*"how does the latest calendar period compare to the previous one, as
of now"* -- it re-fetches full history and re-anchors on every call,
with no stored comparator state, so a revision to an **older**,
already-past period is structurally invisible to it. #18 therefore
needed its own release-scoped before/after comparison, not a reuse of
that endpoint -- but built by reusing the exact same underlying
comparison functions, never by inventing parallel ones. Implemented
against the frozen spec verbatim; the four STOP conditions inspected
most closely at implementation time (a needed comparator missing,
transaction architecture making partial-failure semantics impossible,
the five-year fetch requiring a client redesign, the #17A structural-
independence guard needing to weaken) never materialized -- confirmed,
not assumed, by writing and running the architectural guards below
before declaring done.

### Schema: four new tables, one new column deliberately withheld

`app/db/models.py` gains `ReleaseSeriesMapping` (`id`,
`economic_release_id` FK, `series_id` **string, not an
`EconomicSeries.id` FK** -- a curated mapping fact must exist
independently of whether that series has ever been synced -- `active`,
`created_at`; `UNIQUE(economic_release_id, series_id)`; exactly five
columns, no `role`/`importance`/`weight`), `ReleaseCheckRun` (`status`
one of `NO_CHANGE`/`CHANGED`/`PARTIAL_FAILURE`/`FAILED_PROVIDER` -- no
`NOT_CHECKED`, absence of a row already means that; no status
represents a DB-transaction failure, since that row simply never
durably exists then), `ReleaseObservationUpdate` (append-only,
`change_type` `NEW`/`REVISED` only -- UNCHANGED is never persisted,
represented by a successful run plus the absence of a row;
`previous_value`/`new_value` both nullable, matching
`EconomicObservation.value`'s own nullability so a transition into or
out of missing is never silently dropped), and `ReleaseAnalysisUpdate`
(mirrors `inflation_what_changed_v1.0`'s frozen `ChangeEvent` field set
with one deliberate adaptation -- a single `evaluation_period` column
instead of `previous_period`/`current_period`, because a release-
scoped before/after pair is always evaluated at the *same* period,
never two different calendar months; `previous_value`/`current_value`
stored as nullable `String` since the frozen type is `float | str |
None` and `str(float)` round-trips exactly, verified directly with a
test rather than assumed). **`EconomicObservation.updated_at` was
deliberately NOT added** -- frozen by the spec: a generic row-touch
timestamp would be semantically misleading given the existing blind-
upsert behavior on `/series/{id}/sync`, and `ReleaseObservationUpdate.detected_at`
is already the authoritative record of when a #18-driven change was
detected.

Two migrations, mirroring #17A's own schema/seed separation exactly:
`dbd9a2889ef3` (schema, autogenerated from the ORM models against the
isolated test database, then annotated) and `cd476d227f99` (seed --
looks up each release's real `economic_releases.id` by its stable
provider identity at migration-run time, never a hardcoded/assumed
numeric id, so it stays correct regardless of a given database's row-
insertion history). Seeds exactly four mappings: Consumer Price Index
(`10`) → `CPIAUCSL`/`CPILFESL`; Personal Income and Outlays (`54`) →
`PCEPI`/`PCEPILFE` -- verified directly against
`app/models/inflation.py`'s own `PRIMARY_SERIES_ID`/
`CONFIRMATION_SERIES_ID`/`TARGET_SERIES_ID`/`HEADLINE_CPI_SERIES_ID`
constants, not guessed. Employment Situation/JOLTS/GDP/Advance Retail
Sales are deliberately unmapped -- no deterministic canonical consumer
exists for any of them yet. `alembic check` reports "No new upgrade
operations detected" (zero drift between the ORM models and the
migrations); a full downgrade-twice/upgrade-to-head roundtrip was run
by hand against the test database and produced exactly the original
four seeded rows with no drift.

### The new orchestration layer, and why it had to be new

`tests/integration/test_transaction_and_safety.py::TestReleaseCalendarStructuralIndependence`
already statically forbids `app/repositories/release_repository.py`,
`app/services/releases.py`, and `app/api/releases.py` from importing
anything series/observation/Inflation-shaped -- a hard, pre-existing,
test-enforced fact discovered during the architecture audit, not
something #18 could route around. So the pipeline lives entirely in
**new** files: `app/domain/release_processing.py` (pure -- observation-
change classification, five-year-horizon calendar arithmetic, affected-
evaluation-period computation, and the series→component mapping,
deliberately importing no other domain module, restating the one
needed calendar-forward-arithmetic helper independently rather than
importing `app.domain.inflation.month_before`, to keep every domain
module in the package independent of every other one), a new
repository (`app/repositories/release_processing_repository.py`,
owning the canonical write path and all four new tables' persistence),
and exactly one new service (`app/services/release_processing.py`,
`ReleaseProcessingService`) -- the one module in the whole project that
legitimately imports both the release-calendar side (`ReleaseRepository`,
read-only -- gained one new method, `get_occurrence_by_id`, a plain
lookup) and the series/Inflation side. This is precisely the bridging
role a genuinely new orchestration layer exists for, not a weakening of
the existing guard -- confirmed by extending
`test_domain_architectural_independence.py` (two new tests: the new
domain module is registered against the same no-forbidden-import scan,
and an explicit assertion it imports no other domain module) and by 16
new dedicated guard tests in `tests/test_release_processing_architecture.py`
(no AI/news imports; schedule classification still can't write
observations; no public process route exists anywhere in `app/api/`,
checked by parsing every route decorator, not just inspecting
`releases.py`; the service imports the *exact* existing comparator/
evaluator function names by AST inspection, not just "something from
that module"; no Inflation-formula-shaped regex pattern appears in any
#18 file; `ReleaseAnalysisUpdate` has no JSON/snapshot-shaped column;
`ReleaseSeriesMapping` has exactly its five frozen columns; `EconomicObservation`
has exactly its five pre-18 columns).

### Bounded five-year detection horizon, not "last N observations"

`FREDClient.get_observations` gained two optional parameters,
`observation_start`/`sort_order` -- fully backward compatible (checked
directly: a test asserts the exact request-params dict a pre-18 call
produces is byte-for-byte unaffected). `app.domain.release_processing.five_year_observation_start`
computes the bound by exact calendar-year arithmetic (`date.replace(year=...)`,
with an explicit leap-day fallback), proven directly to differ from a
naive `365 * 5`-day approximation across a real five-year span
containing leap days -- not asserted, computed and compared. Release
processing always calls with `sort_order="asc"` and a fixed, generous
`limit=100_000` (FRED's own documented page-size ceiling, comfortably
above any realistic monthly series' five-year count). This is an
*ordinary* detection window -- newly published data, ordinary recent
revisions, major recent seasonal/benchmark revisions -- explicitly not
a guarantee every historical revision in a provider's full history is
ever caught by a routine check; broad historical reconciliation is
named and deliberately deferred, not designed here (documented in
`docs/architecture/release-processing-v1.md` §12/§21, and flagged as an
open external-research question: the *actual* revision cadence per
release type is BLS/BEA/Census knowledge this repository cannot answer,
and no specific cadence was invented to fill that gap).

### Observation-change classification, and the write path that owns it

`app.domain.release_processing.classify_observation_change` is a pure,
three-line function: `NEW` if the date didn't exist before, `UNCHANGED`
if it did and the value is identical (plain equality -- both sides
reach this comparison via the same deterministic provider string→float
parse already used everywhere else in this codebase, so no tolerance
is needed or added), `REVISED` otherwise, including a transition into
or out of `None` (proven directly with dedicated tests, not left
implicit). `ReleaseProcessingRepository.write_observation` is a small,
deliberately independent reimplementation of `SeriesRepository._upsert_observations`'s
basic insert-or-overwrite shape -- the plain, pre-existing
`/series/{id}/sync` path is completely untouched, never retrofitted to
emit an audit side effect it was never designed for. `_check_one_series`
skips the metadata (`get_series_info`) call entirely when a mapped
series' fetch returns zero observations -- discovered while writing
the CLI's own "no live network calls in tests" verification (an
unmocked `get_series_info` call would otherwise attempt a real request
even for a series with nothing to persist), fixed in the service itself
rather than worked around per-test.

### Before/after analytical consequence -- the highest-risk piece, and how it stayed honest

For every batch of NEW/REVISED observations in one run,
`app.domain.release_processing.affected_evaluation_periods` computes
every calculation period any of them could influence: each changed
date's own period, plus (only when a *later* observation already
exists) each date `+1`/`+3`/`+6`/`+12` months forward -- the exact
horizons `inflation_v1.0` itself defines, reused from the methodology
document's own "Required observations" table, never invented. The
union across the whole batch, across every changed series mapped to
this release, is evaluated **exactly once** before any write and once
after all writes complete -- never once per row, and never against a
partially-written intermediate state (a dedicated "multi-observation
consistency" test constructs three different endpoint revisions that
all feed one later shared period and asserts the final diff matches a
direct call to the same domain function against the fully-revised
data, not anything computed along the way). Every actual before/after
evaluation and diff is delegated to the EXISTING, completely unmodified
`app.domain.inflation` exact-period primitives
(`compute_series_momentum_at`/`compute_target_at`/`compute_confirmation_at`)
and `app.domain.inflation_what_changed` comparators
(`compare_series_momentum_section`/`compare_target_section`/
`compare_confirmation_section`), called with `previous_period ==
current_period == evaluation_period` -- confirmed by name, via AST
inspection, in `tests/test_release_processing_architecture.py`, not
just by code review. Which series feeds which `inflation_what_changed_v1.0`
component (`app.domain.release_processing.SERIES_TO_COMPONENTS`) is a
direct, verified transcription of `InflationMonitorService`'s own
existing orchestration -- `PCEPILFE` → PRIMARY_MOMENTUM *and*
CONFIRMATION (confirmation depends on both Core PCE and Core CPI
together, so a Core PCE-only change still re-evaluates it); `CPILFESL`
→ CONFIRMATION only; `PCEPI` → TARGET *and* HEADLINE_PCE (both are
independently computed from the same headline PCE series, exactly as
`app/services/inflation.py` already does it); `CPIAUCSL` → HEADLINE_CPI
only -- never read from `ReleaseSeriesMapping` itself, which stays a
pure "what to check" lookup throughout (a dedicated test proves a
CPIAUCSL-only change can never fabricate a PRIMARY_MOMENTUM event,
since Core PCE was never touched).

**The old-period revision regression** (the audit's central finding,
made concrete): a fixture with August as the latest persisted period
has June revised; the release-scoped audit still detects and diffs it
(via the `+6`-month forward projection landing on August, since June is
exactly August's own r_6m endpoint) -- proving release-scoped auditing
does not depend on latest-two-month anchoring the way the ordinary
What Changed endpoint necessarily does.

### Transaction and failure semantics

One `session_scope()` transaction per processed occurrence. A mapped
series' provider-level failure (`FREDAuthError`/`FREDTimeoutError`/
`FREDUpstreamError`, or malformed observation data) is caught per-series
inside the service -- proven in both directions with two dedicated
tests (CPIAUCSL succeeds while CPILFESL fails, and the reverse) that
the succeeding series' real, valid changes are still written and
audited while the failing series contributes nothing fabricated. A
genuine database-layer failure is deliberately *not* caught -- it
propagates and rolls back the whole occurrence's transaction, including
any already-classified writes for series that individually succeeded at
the provider boundary (proven by patching the repository's own
`add_check_run` to raise mid-transaction, inside the REAL `session_scope()`,
and confirming nothing survived). `ReleaseCheckRun.status` distinguishes
all four required outcomes (`NO_CHANGE`/`CHANGED`/`PARTIAL_FAILURE`/
`FAILED_PROVIDER`) -- `NO_CHANGE` and `FAILED_PROVIDER` are never
conflated, exactly as the spec required. Idempotency is two distinct,
separately-tested guarantees: a retry against identical provider data
always creates a *new* `ReleaseCheckRun` row (a check occurring twice is
itself a real, repeatable operational fact) but *zero* new observation-
or analysis-update rows, since classification always compares against
whatever is currently persisted.

### Operational CLI, and why there's still no HTTP route

`app/operations/process_release.py` (`python -m app.operations.process_release
--occurrence-id <id> [--as-of-date YYYY-MM-DD]`) is the sole trigger --
no business logic inside it; it parses arguments, resolves settings,
opens one real transaction, delegates entirely to
`ReleaseProcessingService`, prints a safe structured summary, and maps
the outcome to an exit code (0 for `NO_CHANGE`/`CHANGED`, 1 for
`PARTIAL_FAILURE`/`FAILED_PROVIDER`/any operational failure -- invalid
occurrence, not-yet-eligible occurrence, missing configuration, database
unavailable). Deliberately **no** `POST /api/v1/releases/{id}/process`
or equivalent: this project has no authentication anywhere, and
`/series/{id}/sync`/`/releases/sync` already establish an accepted but
standing risk of unauthenticated mutation endpoints that #18's own
pipeline -- strictly more expensive per call than either -- should not
compound further. Verified directly against the running application's
own OpenAPI schema (not just by reading source) that the route surface
is completely unchanged: `/health`, the five `/series/...` routes, the
two `/analysis/...` routes, the two `/monitors/inflation...` routes,
`/releases` and `/releases/sync`, and `/ai/query` -- nothing added,
nothing removed. `frontend/src/test/no-release-sync-or-coupling.test.ts`
was extended (11 release-related frontend files, one new check each) to
also assert no release-related frontend file references a `/process`-
shaped path or any of #18's new model names -- the browser remains
completely read-only, and zero frontend production files were touched.

### Tests

97 new backend tests (686 → **783**): pure domain (24, observation
classification, five-year calendar arithmetic including two independent
leap-year boundary cases, affected-period computation including the
multi-endpoint-deduplication property, series→component mapping); FRED
client (4, the exact backward-compatible request-shape proof plus the
new bounded-fetch shape); domain-independence extension (1); repository
(16, mapping reads including "works with zero `EconomicSeries` rows,"
uniqueness, series/observation writes, check-run/update persistence and
round-tripping including exact float-as-string precision); service (25,
covering essentially the entire required matrix -- eligibility, NEW/
REVISED/UNCHANGED including missing-value transitions, multiple changes
in one payload, the bounded lookback's exact request parameters, both
directions of provider-failure isolation, complete provider failure,
a real database-failure rollback via the actual `session_scope()`,
idempotency, the shutdown/provider-lag invariant reusing #17A's own
CPI-shutdown-scenario shape, no-analytical-change, the old-period-
revision regression, multi-observation consistency, state-change with
exact previous/current state and methodology metadata, and the
CPIAUCSL-can't-fabricate-Core-PCE-events proof); CLI (11, valid/invalid/
ineligible occurrence, provider failure, both missing-configuration
paths, no-secret-output and no-stack-trace proofs, explicit `--as-of-date`
actually driving eligibility, and invalid-date-format rejection); and
16 new architectural guards. Two real, if narrow, mistakes were caught
and fixed while writing this suite, not left in: a "no analytical
change" fixture whose revised date turned out to be exactly a *different*
period's r_12m endpoint (so it produced a real event, correctly --
the test's premise, not the pipeline, was wrong, fixed by using a
deliberately too-sparse-to-classify fixture instead), and an unmocked
`get_series_info` call in two CLI tests that would otherwise have
attempted a real network request in an automated test (fixed by the
service-level "skip metadata fetch when there's nothing to write"
change above, which is a genuine improvement, not merely a test
workaround). Two long-lived-test-database cleanup gaps were found and
fixed in the test files themselves (a test using the REAL, actually-
committing `session_scope()` needs its own explicit real-delete
cleanup -- `db_session`'s savepoint rollback does not cover it) --
confirmed clean afterward directly against the database, not assumed.

### Verification

Backend: `TEST_DATABASE_URL=... pytest tests/ -q`, run three times
across the session as work progressed: **783 passed, 0 skipped** every
time (baseline 686 + 97). `alembic check`: no drift. A full migration
downgrade/upgrade roundtrip: clean, exact row counts restored. The
running application's own OpenAPI schema: unchanged route surface,
confirmed directly, not assumed from source alone. Frontend: `npm test
-- --run` (354, +11 for the extended guard -- explicitly anticipated by
the spec's own "architectural guard tests may increase the count if
they live in frontend"), `npm run typecheck`, `npm run lint`, `npm run
build`: all clean. Zero frontend *production* files were touched --
confirmed via `git diff --stat`, not merely asserted.

### Scope confirmation

`git diff --stat` confirms: backend (`app/db/models.py`,
`app/clients/fred.py`, new `app/domain/release_processing.py`, new
`app/repositories/release_processing_repository.py`, one new method on
the existing `app/repositories/release_repository.py`, new
`app/services/release_processing.py`, new `app/models/release_processing.py`,
new `app/operations/` package), two new Alembic migrations, ten backend
test files (four new, three extended), one frontend test file extended
(`no-release-sync-or-coupling.test.ts` -- test-only, no frontend
production file), and documentation. Zero frontend production changes.
Zero AI changes. Zero methodology changes (`app/domain/inflation.py`/
`app/domain/inflation_what_changed.py` were read and called, never
edited). Zero news changes. Zero scheduler. Zero public process API
route.

### Deferred (named explicitly, not designed in detail here)

Broad/full historical reconciliation beyond the five-year window; any
scheduler/background execution; a public HTTP process or read endpoint
(`GET /api/v1/releases/{id}/updates` is a plausible future read surface
once a UI actually needs one); full point-in-time observation vintage
history; `EconomicObservation.updated_at`; a role/importance enum on
`ReleaseSeriesMapping`; Employment Situation/JOLTS/GDP/Advance Retail
Sales mappings, pending a real deterministic consumer for any of them;
provider abstraction of any kind; and any frontend explanation content
for #18's new concepts (a future increment's job, reusing #17C's
existing canonical-result-to-explanation rule unchanged).

## Increment #19A — Economic Overview UI V1

Preceded by a read-only product + architecture audit (Increment #19,
no production code touched) that inventoried what could be shown
truthfully with today's canonical capabilities -- exactly one complete
monitor (Inflation) plus a real, presentation-layer-only release
calendar -- and recommended against an aggregate `GET /api/v1/overview`
endpoint, against surfacing #18's release-processing evidence yet (no
read endpoint exists for it), and against faking five more monitor
dimensions. #19A implements exactly that recommendation: presentation
only, zero backend changes, `/` becomes the real Economic Overview.

### Hierarchy: Current State -> What Changed -> Releases

Retired the Increment #16A placeholder (`pages/Overview.tsx` was five
lines: a heading and "Frontend foundation ready."). The real page
composes exactly four existing, unmodified canonical read functions --
`getInflationMonitor`/`getInflationWhatChanged`/`fetchUpcomingReleases`/
`fetchRecentReleases` -- each via its own independent `useApiResource`
call, the identical pattern `/inflation` already established for two
resources, extended here to four. No `Promise.all`, no aggregate
endpoint, no global loading state: one resource failing never blanks,
blocks, or fabricates any other section (proven directly: four
dedicated partial-failure tests, one per resource, plus a fifth proving
all four failing simultaneously still renders four independently
truthful error messages under one intact page title, never a blanked
page).

### Current State: a dimension, not an economy score

`components/overview/CurrentStateSection.tsx` is a **new, small,
Overview-specific presentation component** -- deliberately NOT
`InflationHero` reused wholesale, which would have made Overview a
second `/inflation` (no 3M/6M/12M strip, no target/confirmation/
headline detail; those stay `/inflation`-only). The one design decision
treated as load-bearing: a bold "Inflation" label sits directly beside
the state Badge, so the page reads as "Inflation is MIXED," never
"the economy is MIXED" -- the exact distinction the frozen spec
required. Reuses `Badge`/`WhyThisState` unmodified, including
`WhyThisState`'s existing contradictory-evidence guarantee (verified
live against the real backend during visual review: a genuine `MIXED`
reading where 3M sat below the neutral band and 6M sat above it --
numbers a human might read as two different directions -- rendered
`MIXED`, never recomputed). The "more dimensions" note is one
restrained sentence, never five Coming-Soon cards.

### What Changed: no invented narrative

`components/overview/WhatChangedPreview.tsx` renders only real
`ChangeEvent`s from `InflationWhatChangedResult.changes` -- the flat,
already deterministically-ordered list `inflation_what_changed_v1.0`
itself assembles across all five sections (component order, then
event-type order, then field order) -- truncated to 3 via `.slice(0, 3)`
and never reordered. Deliberately does **not** replicate `/inflation`'s
own `WhatChangedSection`, which synthesizes a "State remains X"
sentence from the *absence* of a `STATE_CHANGED` event for its own,
separately-reviewed per-section summaries -- that synthesis is a
frontend inference the frozen #19A spec explicitly forbade for
Overview. A dedicated test proves it: state is `MIXED`, the mocked
`changes` list contains only a metric event, and the page renders that
metric event and nothing resembling "remains"/"unchanged"/"stayed."
The empty-state copy ("No canonical Inflation changes were reported
for this comparison.") was chosen specifically because it stays true
whether zero events happened or a comparison was genuinely unavailable
-- it never claims "Inflation was unchanged," a stronger fact the
response contract doesn't always support.

### Releases: compact, ordered, never reclassified

`components/overview/UpcomingReleasesPreview.tsx` takes the first 3
occurrences from the *raw*, already-backend-ordered array before any
date-grouping, then reuses `groupReleasesByDate`/`ReleaseDateBadge`/
`ReleaseRow` unmodified -- the identical presentation `/releases`
already renders, just fewer of them. `components/overview/RecentReleasePreview.tsx`
shows at most one recent occurrence as one compact line; if none
exists, it renders nothing at all rather than inventing a "no recent
activity" claim. The mandatory release-schedule disclosure was
previously hardcoded inline in `pages/Releases.tsx` -- extracted
byte-for-byte into a new shared `components/releases/ReleaseScheduleDisclosure.tsx`
(a presentation-only refactor; `Releases.test.tsx`'s existing exact-
string assertions against this sentence needed no changes, since the
rendered text is unchanged) so `/releases` and Overview render the
identical sentence rather than two independently-typed copies that
could drift.

### Architectural guards

Two of the required checks were already covered for free: `no-economic-logic.test.ts`
and `no-release-sync-or-coupling.test.ts` both scan recursively (the
former all of `src/`, the latter every file whose path contains
"release"), so all five new Overview-adjacent files were picked up
automatically the moment they existed, with zero edits to either guard
file. A new, narrowly-scoped `test/no-overview-mutation.test.ts` covers
the remaining property those two don't: every `components/overview/*`
file plus `pages/Overview.tsx` imports no AI/news module, references no
sync/process endpoint, never calls `fetch` directly (network calls must
go through an `api/*` client module), contains no #18 release-processing
identifier (deferred to #19B/#19C, not #19A), and `pages/Overview.tsx`
imports only the four documented canonical read functions (plus
`useApiResource`) from `api/*` -- nothing else. One real, if narrow,
false positive was caught and fixed while writing this guard: the
page's own doc comment, explaining in prose that #18's release-
processing model names are deliberately not surfaced, itself matched
the very regex checking for those names -- fixed by rewording the
comment (not weakening the guard), the same resolution this project has
applied to the identical class of self-referential collision before.

### Tests

64 new frontend tests (354 -> **418**): 25 in `pages/Overview.test.tsx`
(loading; Current State including the contradictory-evidence proof and
the no-fake-dimension-label checks; What Changed including the non-
inference proof and the event-ordering proof; Releases including the
release-ordering proof, the schedule-does-not-mean-publication proof,
and both empty states; five independent partial-failure scenarios;
navigation exposing exactly three real CTAs and no dead links to
Explore/Compare/Research/Ask EI/News/Watchlist; page structure), 22 in
the new `no-overview-mutation.test.ts` guard, and the remainder from
the two existing guards' automatic recursive pickup of the new files.
`App.test.tsx`'s five-year-old placeholder assertion ("Frontend
foundation ready.") was replaced with a routing-only check matching
the exact pattern already used for `/inflation`/`/releases`; three
other `App.test.tsx` cases needed a `fetch` stub added (Overview now
fetches real data, where the placeholder never did) and two needed a
query fix after Overview's own per-page `<header>` -- the same
convention `/inflation`/`/releases` already use -- caused this test
environment's role computation to report two "banner" landmarks
instead of one; resolved by scoping the query to the outer, site-wide
header specifically, not by changing production markup.

### Verification

Frontend: `npx vitest run`, run twice: **418 passed** both times.
`npm run typecheck`, `npm run lint`, `npm run build`: all clean.
Backend: `TEST_DATABASE_URL=... pytest tests/ -q`: **785 passed**, 0
skipped -- unchanged, confirming zero backend impact (`git status`
shows every change confined to `frontend/` plus this documentation).

### Visual review

Checked live in a real browser against the running development
backend, real synced data: the state Badge, "Inflation" label, `Why
Mixed?` evidence panel (showing a genuine real-world contradictory-
looking 3M/6M/12M reading, MIXED rendered correctly), What Changed's
three real metric events, and the Upcoming/Recent Releases block with
real schedule-status badges and category tags all rendered exactly as
designed -- credible, scannable, not card-heavy, clearly distinct from
`/inflation` rather than a second copy of it. Narrow/mobile visual
verification could not be completed in this session -- the browser
automation's window-resize call reports success but does not actually
change the captured screenshot's viewport width in this environment,
the same limitation already noted in the #16B.1/#17B/#17C journal
entries. Responsive safety instead rests on inspecting the actual
markup: every new Overview component reuses the identical `flex-wrap`/
no-fixed-width Tailwind patterns already verified not to overflow on
`/inflation`/`/releases`, and the page container uses the same
`max-w-3xl` wrapper both of those pages already use.

### Deferred (named explicitly, not built here)

#18's release-processing evidence (no read endpoint exists yet -- that
is #19B); any aggregate `GET /api/v1/overview` endpoint (deliberately
rejected in the #19 audit; revisit only if request count materially
grows once a second monitor exists); Explore/Compare/Research/Ask EI/
News/Watchlist (none exist as frontend product surfaces); a fifth+
monitor dimension shown as anything other than the one quiet sentence
already present; any economy-wide score, health rating, or importance/
attention ranking.

## Increment #19B — Release Update Read Model V1

Preceded by a focused, read-only contract audit (Increment #19B audit,
no production code touched) built around one epistemic invariant: an
occurrence that was never checked must never look the same as one that
was checked and found unchanged. The audit's candidate contract nested
analytical consequences inside each detected observation change and
proposed a sixth `NOT_APPLICABLE` status plus two endpoints; this
implementation follows the frozen spec's three corrections instead --
sibling arrays, exactly five statuses, exactly one endpoint -- not the
audit's own draft (see [ADR-023](adr/023-release-processing-read-model-no-causal-nesting.md)).

### One endpoint, database-only, always 200 for a persisted result

`GET /api/v1/releases/processing-status` is the only new route. It
lives in a new file, `app/api/release_processing_read.py`, deliberately
separate from `app/api/releases.py` -- the same reason #18 gave
`app/services/release_processing.py` its own file rather than
extending `app/services/releases.py`
(`TestReleaseCalendarStructuralIndependence` protects `app/api/releases.py`
from importing anything series/observation-shaped, and the new read
service legitimately does). A persisted `CHECK_FAILED` or
`PARTIAL_CHECK` result is itself successfully-read product data -- it
returns HTTP 200 like every other status; only a request-shape problem
(400/422) or a genuine database failure (503/500) is an HTTP error.

### Five public statuses, derived from the latest run only

`ProcessingStatus` is `NOT_CHECKED | NO_CHANGE | CHANGES_DETECTED |
PARTIAL_CHECK | CHECK_FAILED` -- `NOT_CHECKED` is the absence of any
`ReleaseCheckRun` row for an occurrence, never a persisted value (the
same discipline #18 already applies to its own 4-value internal
status). The other four are a pure presentation relabeling of #18's
internal `CheckRunStatus` (`NO_CHANGE`/`CHANGED->CHANGES_DETECTED`/
`PARTIAL_FAILURE->PARTIAL_CHECK`/`FAILED_PROVIDER->CHECK_FAILED`),
derived from the occurrence's most recently completed run only
(`completed_at DESC, id DESC`, deterministic tie-break). An occurrence
whose release currently has zero active `ReleaseSeriesMapping` rows is
excluded from the resource entirely, at the repository layer, before a
status is ever derived -- never given a sixth, catch-all status.

### Retry-history preservation -- the reason #19B exists

`latest_check.status` reflects the latest run only, but
`detected_observation_changes`/`detected_analysis_changes` are the
UNION of every `ReleaseObservationUpdate`/`ReleaseAnalysisUpdate` row
across EVERY run the occurrence has ever had. A later `NO_CHANGE` (or
`CHECK_FAILED`) run's own absence of new rows never erases an earlier
run's detected evidence -- proven directly by
`TestRetryHistoryPreservation` in the new integration service test
file: a `CHANGED` run followed by a `NO_CHANGE` retry still reports
`NO_CHANGE` as the current status while still showing the original
run's detected changes, and a `FAILED_PROVIDER` run followed by a
`CHANGED` retry correctly surfaces the real changes once they exist. A
naive "read only the latest run's own rows" projection would have
silently discarded exactly the evidence this read model exists to
preserve.

### Sibling facts, never nested by causality

`ReleaseProcessingStatusItem` exposes `detected_observation_changes`
and `detected_analysis_changes` as two independent top-level arrays.
Neither references the other -- `ReleaseObservationUpdate` and
`ReleaseAnalysisUpdate` each only reference `release_check_run_id` in
the database, with no persisted correspondence between a specific
observation and a specific analysis event (see
`test_no_analytical_change_when_a_revision_does_not_move_any_canonical_value`
and the two-series `PARTIAL_FAILURE` tests in #18's own suite for real
cases where the two facts don't line up one-to-one). See
[ADR-023](adr/023-release-processing-read-model-no-causal-nesting.md)
for the full reasoning and the rejected `detected_change { observation,
analysis_consequences[] }` shape.

### Success/failure series counts: omitted, not approximated

`SeriesCheckOutcome` (the in-memory per-series result #18 computes
while processing) is never persisted anywhere -- `ReleaseCheckRun`
carries no per-series breakdown, and a series checked successfully
with zero changes leaves no row in `ReleaseObservationUpdate` either.
There is no way to reconstruct `successful_series_count`/
`failed_series_count` from persisted data alone without fabricating
them, so V1's `LatestCheck` omits both fields rather than approximate.
This was flagged in advance as an acceptable omission, not a stop
condition, and is enforced structurally by
`TestNoSuccessFailureCountFabrication`.

### Layering: a new read repository and service, not a reuse of #18's write path

`app/repositories/release_processing_read_repository.py`
(`ReleaseProcessingReadRepository`) and
`app/services/release_processing_read.py`
(`ReleaseProcessingReadService`) are both new, both read-only, and
neither reuses `ReleaseProcessingRepository`/`ReleaseProcessingService`
(#18's write path) -- the identical "structurally incapable, not just
conventionally disciplined" reasoning `ReleaseReadService`/
`ReleaseSyncService` already establish. Status filtering happens in
the service, in Python, after fetching every mapped occurrence
matching the `occurrence_id`/`release_id`/`start_date`/`end_date`
filters (a clean, unfragile SQL `WHERE`/`IN` query) -- deriving "latest
run per occurrence" as a SQL window function was deliberately not
attempted for V1's small, curated-catalog scale (see
docs/architecture/release-processing-read-model-v1.md).

### Tests

69 new backend tests (785 -> **854**), 0 skipped: 16 architectural
guards (`tests/test_release_processing_read_architecture.py` -- no
FRED/AI import, the read service never imports the write service, the
read repository has no write-shaped method and never mutates, exactly
one route registered and it is not occurrence-scoped, exactly five
`ProcessingStatus` values with no sixth status, sibling-not-nested
field shapes with no `detected_change` wrapper, no fabricated series
counts); 16 repository tests
(`tests/integration/test_release_processing_read_repository.py` --
mapped/unmapped exclusion including an inactive-only-mapping case,
occurrence/release/date filtering, ordering and tie-breaks, empty-input
handling, series-metadata lookup and absence); 21 service tests
(`tests/integration/test_release_processing_read_service.py` --
non-mutation, all five status derivations, both retry-history-
preservation scenarios, observation-without-analysis, series-metadata
enrichment and its null fallback, release-context contract, zero-
mapping exclusion, status/release/date filtering, ordering, pagination
including "total reflects the status-filtered set," date-range
validation, repeated-call determinism); 16 HTTP tests
(`tests/api/test_release_processing_read_api.py` -- NOT_CHECKED and
CHECK_FAILED both return 200, unmapped exclusion, sibling-shape proof
over real JSON, retry-history survival over HTTP, status filtering,
pagination defaults and explicit limit/offset, 400/422 validation
mapping, safe 503/500 error messages that never leak exception text,
repeated-request determinism, and a direct proof that no
`{occurrence_id}/processing-status` route exists -- 404). One
self-referential false positive was caught and fixed while writing the
architecture guards (the new modules' own docstrings, explaining in
prose why `NOT_APPLICABLE` and a nested `analysis_consequences[]` array
were rejected, matched the literal substring checks looking for exactly
those rejected shapes) -- fixed by rewording the docstrings, not
weakening the guards, the same resolution #19A's own journal entry
already documents for the identical class of collision.

### Verification

Backend: `TEST_DATABASE_URL=... pytest tests/ -q`, run twice: **854
passed** both times, 0 skipped. `alembic check`: no new upgrade
operations detected -- no migration, as expected (no ORM model was
added or changed). Frontend: `npx vitest run`: **418 passed**,
unchanged; `npm run typecheck`/`npm run lint`/`npm run build`: all
clean; `git status` inside `frontend/` is empty -- zero frontend
production changes, as the frozen spec required.

### Deferred (named explicitly, not built here)

A single-occurrence detail endpoint (`GET /api/v1/releases/{occurrence_id}/processing-status`)
-- explicitly out of scope for #19B, add only once a real product
surface needs it; any frontend consumer of this endpoint (#19C or
later); `successful_series_count`/`failed_series_count` (see above --
not reconstructable from persisted data, not merely postponed); a
persisted causal link between a specific observation change and a
specific analysis change (see ADR-023 -- would require a #18 write-path
change, not a #19B read-model one); any recomputation, reclassification,
or economic-significance judgment inside the read path itself.

## Increment #19C — Latest Data Detected UI

Frontend-only: the first UI consumer of #19B's read model. Overview's
hierarchy becomes Current State -> What Changed -> Latest Data
Detected -> Releases (NOW -> CHANGED -> DETECTED -> NEXT). Zero
backend production changes -- confirmed directly (`git status` shows
every change confined to `frontend/`) and by an unchanged
854-passed/0-skipped backend regression run, twice.

### A fifth independent resource, not a sixth section on an existing one

`fetchReleaseProcessingStatus` (`GET /api/v1/releases/processing-status`)
is loaded via its own `useApiResource` call in `pages/Overview.tsx`,
completely independent of the other four -- no `Promise.all`, no
aggregate endpoint, loading/error handled inline exactly like the
other four sections. One resource failing never blocks or blanks any
other; a dedicated live check confirmed this against the real dev
backend (see "Visual review" below): with the endpoint genuinely
returning 500, the rest of Overview rendered normally and the section
showed only "Release-processing status is temporarily unavailable.",
no console error, no crash.

### Where the new code lives, and why (an import-boundary constraint, not a naming preference)

`api/processingStatus.ts`/`.types.ts`, `lib/detectedChangeFormat.ts`,
`lib/selectLatestDataDetected.ts`, `content/explanations/processingStatus.ts`,
and `components/overview/LatestDataDetected.tsx` deliberately never put
the substring "release" in a file path. This is not a stylistic choice:
`test/no-release-sync-or-coupling.test.ts` forbids any file whose path
contains "release" from importing `lib/inflationLabels`/`api/inflation`
-- and #19C's whole reason to exist is rendering `DetectedAnalysisChange`
evidence that reuses Inflation's own `ChangeComponent`/`ChangeEventType`
vocabulary and label maps verbatim (mirroring the backend's own #18
`app/services/release_processing.py` bridge). `pages/Overview.tsx`/
`CurrentStateSection.tsx`/`WhatChangedPreview.tsx` already established
this exact pattern in #19A for the identical reason (see that guard's
own docstring). `api/processingStatus.types.ts` imports `ChangeComponent`/
`ChangeEventType` directly from `api/inflation.types.ts` rather than
forking a parallel enum -- the backend's own `DetectedAnalysisChange`
model does the identical thing.

### Backend-status-controls-the-message, always -- proven with a contradictory fixture

`latest_check.status` -- and only that field -- drives the primary
status line (`processingStatusLabel`); historical
`detected_observation_changes`/`detected_analysis_changes` are never
inspected to override it. The required contradictory-evidence
regression test constructs a `NO_CHANGE` item carrying real historical
observation AND analysis evidence (simulating exactly the retry
scenario #19B's own read model exists to preserve) and asserts the
section still says "No new data detected in the latest check." --
never "Data changes detected." -- while still showing the older
evidence, explicitly labeled "Earlier changes were detected for this
release occurrence." The same "earlier evidence" framing applies to
`CHECK_FAILED`, since a failed run adds no rows of its own by
construction (`_determine_status`'s own logic) -- so labeling
pre-existing evidence as "earlier" there is a true inference from the
status alone, not a guess.

### Deterministic UI selection rule (`lib/selectLatestDataDetected.ts`)

The backend orders its response `scheduled_date DESC`, but #18/#19B
processing is manual-only (no scheduler) -- so "first item exactly as
returned" would almost always show a boring, uninformative future
`NOT_CHECKED` row and bury real detected evidence beneath it. #19C
instead ranks by `latest_check.status` priority (`CHANGES_DETECTED` >
`PARTIAL_CHECK` > `CHECK_FAILED` > `NO_CHANGE` > `NOT_CHECKED`),
preserving the backend's own order within one tier -- a documented
PRODUCT priority rule using only the already-returned `status` field,
never a date computation or economic ranking. Because the selected
item is not always the most-recently-scheduled one, the section never
says "latest release" -- only "Most recent detected update."

### Sibling structure, no causal language (ADR-023 extended to the UI)

`detected_observation_changes`/`detected_analysis_changes` render as
two separate headed groups, "Source data changes" and "Tracked
analysis changes" -- never nested, never a `detected_change` wrapper.
A dedicated regression test asserts neither group's DOM contains the
other, and that no rendered text anywhere matches "caused"/"because
of"/"impact of this revision"/"resulting analysis change". When
observation changes exist but analysis changes don't, the copy is "No
tracked Inflation evidence changed during this processing history." --
deliberately scoped to the whole occurrence's history, never "this
check," since #19B's response doesn't expose which run an update
belongs to.

### A schedule_status gap #19B's own contract doesn't cover, resolved honestly

The spec's suggested NOT_CHECKED copy distinguishes SCHEDULED vs.
PAST_DUE occurrences -- but `ReleaseProcessingStatusItem` deliberately
has no `schedule_status` field (see
`app/models/release_processing_read.py`'s own docstring), and deriving
it client-side from a raw date comparison would violate this project's
standing rule that schedule-status classification is backend-owned,
never recomputed (see `lib/releases.ts`'s own docstring). #19C uses the
one wording the spec itself names as acceptable for BOTH cases -- "Not
yet checked by Economic Intelligence." -- uniformly, rather than
inventing the distinction. Not a stop condition: a real product need
for the SCHEDULED/PAST_DUE distinction here is the trigger to add
`schedule_status` to a future version of #19B's contract deliberately,
not to guess at it now.

### Value formatting stays conservative

`formatObservationValue` appends "%" only when the backend's own
`EconomicSeries.units` string says "percent" -- an index-level or
dollar-denominated value renders as a plain formatted number, never
converted, annualized, or normalized. `formatAnalysisValue` shows a
`DetectedAnalysisChange.previous_value`/`current_value` (persisted
strings) exactly as stored, reinterpreted only for the two enum-shaped
fields ("state"/"relationship") this project already has a canonical
label map for. `NEW`/`REVISED` map to "New observation"/"Revision
detected" only -- never "Published"/"Released"/"Corrected"/"Finalized".

### Dates and timestamps

`scheduled_date`/`observation_date`/`evaluation_period` reuse
`lib/releases.ts`'s existing digit-parsing `formatFullDate` (never
`new Date(dateOnlyString)`, which can roll a date back a day in
timezones behind UTC). `latest_check.checked_at` is a NEW case this
project hadn't needed before -- a full, timezone-aware ISO datetime,
safe to parse via `new Date(...)` (unlike a bare date) -- formatted by
a new `formatCheckedAt` helper with no seconds, avoiding false
precision.

### Tests

55 new frontend tests (487 total, up from 432 -- some of that delta is
the two existing architectural guards' automatic recursive pickup of
6 new source files, zero edits needed to either guard, the same
pattern #19A's own journal entry describes): 20 in
`components/overview/LatestDataDetected.test.tsx` (every one of the
five statuses, the contradictory-evidence regression, the
no-causal-nesting regression, NEW/REVISED copy, order/truncation for
both change lists, date-shift regression, methodology/data-basis
disclosure, and the empty-groups regression described below); 6
integration-level additions to `pages/Overview.test.tsx` (fifth-resource
independence and placement, empty state, and failure isolation in both
directions -- the new resource failing alone, and it succeeding while
every other resource fails); unit tests for `lib/selectLatestDataDetected.ts`,
`lib/detectedChangeFormat.ts`, `content/explanations/processingStatus.ts`,
and `api/processingStatus.ts`. `test/no-overview-mutation.test.ts`'s
own allowlist and one previously-"deferred" assertion were updated (not
weakened -- see "Where the new code lives" above and this file's own
updated doc comments) to reflect that #19C is the increment where #18's
evidence legitimately reaches the browser, through #19B's public
contract only.

One real bug was caught by live visual review, not by the 487 passing
jsdom tests: with a `NOT_CHECKED` item (no observation or analysis
evidence at all -- the actual common case, confirmed live against real
dev data), the component rendered a dangling "Tracked analysis
changes" heading with nothing under it, because that group's wrapping
`<div>` was gated on `analysisChanges.length > 0` internally rather
than on whether either evidence list had anything to show. Every
existing jsdom test happened to exercise a scenario where at least one
list was non-empty. Fixed by gating the whole group on
`analysisChanges.length > 0 || observationChanges.length > 0`, with a
new regression test added specifically for the empty-both case.

### Verification

Frontend: `npx vitest run`, run twice: **487 passed** both times.
`npm run typecheck`, `npm run lint`, `npm run build`: all clean.
Backend: `TEST_DATABASE_URL=... pytest tests/ -q`, run twice: **854
passed**, 0 skipped -- unchanged, confirming zero backend impact.

### Visual review

Checked live in a real browser against the running dev backend. The
dev database was found not migrated past an old #17A-era revision
(missing #18's tables entirely, since no prior increment's dev-server
session had run `alembic upgrade head` against it) -- a pre-existing
gap unrelated to this increment. With the user's explicit approval,
`alembic upgrade head` was run against the dev database (two
already-committed, already-tested migrations applied: `dbd9a2889ef3`,
`cd476d227f99` -- no new migration written, no migration file touched).
This unblocked a genuine live check: the section renders correctly
between What Changed and Releases with real backend data (all real
mapped occurrences are `NOT_CHECKED`, since #18 processing has never
been run against this dev database -- expected, given it's
manual/CLI-only), the info-icon explanation trigger and compact layout
matched the rest of the page, and no console errors appeared on load.
A genuine 500 from the endpoint (captured before the migration fix)
was also verified live: the section showed its local error message
with a Retry button, and Current State/What Changed/Releases rendered
completely normally around it. Real `CHANGES_DETECTED`/`PARTIAL_CHECK`/
observation-and-analysis-evidence rendering could not be verified
live -- no dev-database data exists in any of those states, and
generating it would require running #18's data-mutating operational
CLI against real data, out of scope for this frontend-only increment.
That content is instead covered by the component test suite above.
Narrow/mobile visual verification could not be completed -- the same
known window-resize limitation noted in every prior increment's
journal entry (#16B.1/#17B/#17C/#19A).

### Deferred (named explicitly, not built here)

`schedule_status` on #19B's contract (see above -- a real need for the
SCHEDULED/PAST_DUE distinction here is the trigger, not a guess now);
a persisted causal link between an observation change and an analysis
change (ADR-023, unchanged by this increment); any "Check now"/refresh
control (#19C adds no mutation path anywhere); a release-detail surface
showing full per-occurrence history (the single-occurrence endpoint
#19B itself deferred); any economic ranking, importance score, or
cross-release comparison.

## Increment #20B — Deterministic Labor Monitor V1 Backend

The second canonical monitor. Implements `labor_v1.0` exactly as
frozen in `research/labor_momentum/LABOR_V1_FROZEN_METHODOLOGY.md`
(itself preceded by #20A's architecture audit, #20A.1's historical
rejection of the original payroll formula, and #20A.2's redesigned,
re-validated replacement — all research-only, all preserved unmodified
in `research/labor_momentum/`). No methodology redesign happened in
this increment; every formula, threshold, and table below is a direct
transcription, verified against the frozen document and, independently,
against the actual validated research code.

### Route → Service → pure domain, mirroring Inflation exactly

`app/models/labor.py` (constants, enums, `LaborObservationEvidence`/
`EmploymentResult`/`UnemploymentResult`/`LaborMonitorResult`) →
`app/domain/labor.py` (pure, deterministic; no SQLAlchemy, no FastAPI,
no FRED, no import of any other domain module — checked structurally)
→ `app/services/labor.py` (`LaborMonitorService`, reusing the
*existing*, generic `SeriesRepository` — no Labor-specific repository
was needed or created) → `app/api/labor.py` (`GET /api/v1/monitors/labor`,
a new, separate router file rather than an addition to
`app/api/inflation.py`, per the frozen spec's own "no premature generic
monitor framework — implement Labor independently first" instruction).
No `BaseMonitor`/`GenericEconomicMonitor` abstraction was introduced;
Inflation's own files are completely unmodified.

### PAYEMS units — converted exactly once

FRED persists PAYEMS in "Thousands of Persons"; every `labor_v1.0`
formula operates on actual persons/jobs. `app.domain.labor.build_jobs_index`
is the ONE place the ×1,000 conversion happens — every `_jobs`-suffixed
field downstream is already converted. A dedicated regression test
(`TestUnits::test_a_native_50_never_means_50000_jobs`) pins the exact
converted magnitude, not just the resulting classification, making the
25-vs-25,000-style bug #20A.1's own research caught structurally
harder to reintroduce here.

### Employment condition/momentum/state — transcribed, not re-derived

`current_3m_avg_jobs`/`prior_3m_avg_jobs` (non-overlapping 3-month
windows), `condition_deadband_jobs = momentum_deadband_jobs = 50,000`,
boundary-inclusive `FLAT`/`STEADY`. Vocabulary is `EXPANDING/FLAT/
CONTRACTING` (condition) and `IMPROVING/STEADY/WORSENING` (momentum) —
**not** `ACCELERATING`/`DECELERATING`, which appeared only in this
increment's own framing prose, never in the validated research
artifact; the frozen spec already resolved this discrepancy in the
artifact's favor, and `app/domain/labor.py`/`tests/test_labor_architecture.py`
both enforce it (an explicit negative test proves `ACCELERATING`/
`DECELERATING` are absent from the enum). The full 9-cell
condition×momentum table (`_EMPLOYMENT_STATE_TABLE`) is a direct,
line-for-line transcription of `methodology_v2._CONDITION_MOMENTUM_TABLE`.

### Unemployment trend — unchanged

`current_3m_avg` vs. `prior_year_3m_avg` (exactly one year earlier),
`unemployment_deadband_pp = 0.2`, boundary-inclusive `STABLE`. Not
redesigned in #20A.2, not touched here.

### Top-level `LaborState` — the frozen agreement table, four clean cells and one documented default

Only `(EXPANDING, IMPROVING) → STRENGTHENING`, `(COOLING, DETERIORATING)
→ COOLING`, `(CONTRACTING, DETERIORATING) → COOLING`, and `(STABLE,
STABLE) → STABLE` resolve cleanly; every other combination — including
every `RECOVERING` pairing — is `MIXED`, by an explicit `.get(...,
"MIXED")` default, never a silent fallthrough. No weights, no score,
no majority vote, no hidden tie-breaker anywhere in this call chain.

### Shared `evaluation_period` — one rule, two owners, never two reference months

`determine_evaluation_period` picks `min(latest PAYEMS date, latest
UNRATE date)` — a deterministic bound, never a backward search for "a
month that works." If either series has zero persisted observations,
`evaluation_period` is `None` and the whole result is `INSUFFICIENT_DATA`
with empty evidence lists (not a fabricated evaluation month). Once
chosen, the SAME period is passed to both `compute_employment_result`
and `compute_unemployment_result` — proven directly by a dedicated
service-level test asserting every returned evidence date traces back
to the one shared anchor.

### Missing data — no hack, including for the real UNRATE 2025-10 gap

No forward-fill, backfill, interpolation, or partial-window averaging
anywhere. `condition` needs only 4 exact PAYEMS months (`t..t-3`);
`momentum`/`state` need the full 7 (`t..t-6`) — a real, frozen
distinction (§3 vs. §4 of the frozen spec), confirmed by a domain test
that initially asserted the WRONG thing (that `condition` also goes
`INSUFFICIENT_DATA` for every one of the 7 missing-month cases) and
was corrected once the frozen spec's own narrower condition
requirement was re-checked — see "Errors and fixes" below. A dedicated
test mirrors the real, `#20A.1`-discovered UNRATE 2025-10 collection
gap shape directly: the same missing month is inert when it falls
outside the current evaluation's required window and correctly
produces `INSUFFICIENT_DATA` when a later evaluation's window happens
to include it — no special case anywhere in the code for that specific
date.

### Affected horizons — re-verified in production code, not just research

The frozen spec's most important, most non-obvious finding — a single
PAYEMS level revision affects `EmploymentState` at exactly `{M, M+3,
M+6}` (not a contiguous range; the opposite-signed effects on two
adjacent monthly-change values cancel exactly inside any 3-month
average containing both) — was re-verified here two ways: first, a
direct numerical comparison against `research/labor_momentum`'s own
validated output (the exact `current_3m_avg_jobs`/`prior_3m_avg_jobs`
figures for August 2009 and April–June 2021 match the shipped
production code bit-for-bit); second, a dedicated pure-domain
regression test (`TestPayemsAffectedHorizons`) that applies a
synthetic revision to a real cached PAYEMS history and asserts the
changed-offset set is exactly `{0, 3, 6}` — including an explicit
assertion that offsets 1 and 2 show **zero** change (the cancellation
itself, not merely "less change"). UNRATE's own `{0,1,2}∪{12,13,14}`
disjoint set (no cancellation — it averages the rate directly) is
proven the same way.

### Historical regression — the exact real numbers, not a synthetic stand-in

August 2009 and April/May/June 2021 fixtures use REAL PAYEMS values
taken directly from `research/labor_momentum/data/PAYEMS.csv` (the
exact data that validated `labor_v1.0`), not fabricated numbers.
August 2009 locks `RECOVERING` (never `STRENGTHENING`); April/May 2021
lock `EXPANDING`+`IMPROVING`; June 2021 locks `EXPANDING`+`STEADY` —
matching the validated research output's exact figures
(`current_3m_avg_jobs`/`prior_3m_avg_jobs` pinned to within rounding).

### Evidence contract — one field decision beyond the frozen sketch

The frozen spec's own evidence sketch (§12) listed BOTH a per-component
`observations`-style evidence list AND a separate top-level
`provenance: [...]` field. Since the per-component lists already
constitute complete provenance (series_id/date/value for every exact
required month), a separate top-level `provenance` field would only
duplicate the same data — this implementation consolidates evidence
into `employment.observations`/`unemployment.observations` alone and
omits the redundant top-level field, consistent with the frozen spec's
own "do not overbuild" instruction. `data_basis` uses
`"latest_revised_data"` (the exact snake_case string
`app.models.inflation.DATA_BASIS` already establishes as this
project's actual convention), not the frozen document's own
human-sentence example string ("Latest revised data") — reconciled in
the established project convention's favor per this increment's own
explicit instruction. Both are documented discrepancies, not silent
deviations.

### JOLTS / CIVPART / release-processing / frontend — all confirmed absent

No `JTS*` series ID, no `CIVPART`, appears anywhere in the Labor call
graph (`TestNoJoltsOrCivpartInV1`, a literal string-absence guard
across every Labor file). No `ReleaseSeriesMapping` row was added, no
migration was created, `app/services/release_processing` is not
imported anywhere in the Labor call graph (checked structurally). No
`frontend/` file was touched.

### Errors and fixes

Two real bugs were caught and fixed, both in this increment's OWN test
code, never in the frozen methodology or the production domain module:
(1) a synthetic test index built with perfectly linear values made
every monthly change identically constant, so a test asserting "the
current and prior 3-month windows differ" passed vacuously regardless
of correctness — fixed by using a non-linear (quadratic) synthetic
sequence; (2) a test asserted `condition == INSUFFICIENT_DATA` for
every one of the 7 possible missing PAYEMS months, but the frozen
spec's own §3 only requires 4 exact months for `condition` specifically
(momentum/state need the full 7) — the test was over-asserting;
production code was already correct, confirmed by re-reading the
frozen spec's exact wording before deciding which side was wrong. A
third, more valuable "failure": an integration test revising a PAYEMS
month one offset away from the anchor initially failed because that
specific offset falls exactly in the frozen cancellation zone — not a
bug at all, but a live, unplanned confirmation of the `{0,3,6}`
affected-horizon property inside the full service-integration path,
not just the isolated domain functions. Fixed by revising a
genuinely-affected offset instead.

### Tests

167 new backend tests (854 → **1,021**): 145 pure-domain unit tests
across `tests/test_domain_labor.py` (units, calendar arithmetic,
monthly-change/average construction, every condition/momentum boundary
inclusive-and-just-outside, the full 9-cell employment-state table,
every explicit top-level agreement branch plus every remaining
default-MIXED combination, missing-month behavior for both the
4-month condition requirement and the 7-month momentum requirement
independently, the real 2025-10 UNRATE gap shape, determinism, the
shared-evaluation-period rule under mismatched series availability,
the two historical regressions with real PAYEMS values, and the
`{0,3,6}`/`{0,1,2}∪{12,13,14}` affected-horizon proofs) and
`tests/test_labor_architecture.py` (no AI/FRED import anywhere in the
call graph, no release-processing-mutation import, pure domain layer,
service imports only the one domain entry point, exactly one route
registered, no JOLTS/CIVPART string anywhere, and every frozen
vocabulary/threshold/methodology-id constant pinned exactly); one new
test added to the existing `tests/test_domain_architectural_independence.py`
(labor joins the domain-file allowlist and gets its own
no-other-domain-module-import guard); 11 service-level integration
tests (`tests/integration/test_labor_service.py`, real isolated
Postgres: complete history, neither/one series persisted, PAYEMS
newer than UNRATE and vice versa, a missing required month on each
side independently, the real-gap-shape scenario, non-mutation, and a
persisted revision changing the result deterministically); 17 API
tests (`tests/api/test_labor_api.py`: exact response contract for both
`employment`/`unemployment`, missing-data 200s, 503/500 infrastructure
mapping with no leaked detail, determinism, non-mutation, no FRED
client construction, no ingestion side effect, and no mutation route).

### Verification

Backend: `TEST_DATABASE_URL=... pytest tests/ -q`, run twice: **1,021
passed** both times, 0 skipped. `alembic check`: no new upgrade
operations detected — no migration, as expected (Labor reuses the
existing generic `EconomicSeries`/`EconomicObservation` schema
unmodified). No Python lint/typecheck tooling exists in this project
(unchanged from every prior increment). Frontend: not touched;
`git status` confined entirely to `app/models/labor.py`,
`app/domain/labor.py`, `app/services/labor.py`, `app/api/labor.py`,
`app/main.py` (router registration), and four new/one extended test
file.

### Deferred (named explicitly, not built here)

JOLTS confirmation (no defensible deadband was ever established across
#20A/#20A.1/#20A.2 — deferred to a dedicated future confirmation
increment, per the frozen spec's own strong preference); `CIVPART`
context (deferred to a #20B.1-style follow-on, the same precedent
#17A's own curated-catalog follow-on established); Labor What Changed
(principle-only in the frozen spec, no comparator built); Labor
release-processing integration (`ReleaseSeriesMapping` rows for
Employment Situation → PAYEMS/UNRATE — the frozen spec's own §13
affected-horizon derivations exist specifically to make this
integration correct when it happens, but it does not happen in #20B);
any Overview frontend surface for Labor; any cross-monitor
aggregation (frozen against, permanently, per #20A §28/§20A.3 §16).

## Increment #20C.2 — Deterministic Labor What Changed V1

The Labor Monitor's comparison layer. Implements `labor_what_changed_v1.0`
exactly as frozen in
`research/labor_momentum/LABOR_WHAT_CHANGED_V1_FROZEN_METHODOLOGY.md`
(written in #20C.1's own design/audit/freeze turn, which is not a
separate journal entry — no implementation happened there). The
comparator compares already-canonical `labor_v1.0` results; it
performs zero PAYEMS/UNRATE calculation, zero threshold application,
and zero classification of its own.

### Two small, additive seams in `app/domain/labor.py`, no refactor

The frozen spec's own architecture audit (§12) found that
`compute_employment_result`/`compute_unemployment_result` already
accept an explicit period parameter — unlike Inflation, which needed a
`compute_series_momentum`/`_at` split, Labor needed no equivalent
refactor. Two new, purely additive functions were added instead:
`compute_labor_monitor_result_at(payems_observations, unrate_observations,
period, ...)` (the complete `labor_v1.0` result at an EXPLICIT,
caller-given period — never searched, unlike `compute_labor_monitor_result`'s
own "latest" search) and `month_over_month_labor_periods(...)`
(`(previous_period, current_period)`, reusing `determine_evaluation_period`
unmodified for `current_period` and `month_before(current_period, 1)`
for `previous_period` — exact calendar month, never searched
backward). `compute_labor_monitor_result` itself was refactored to
delegate to `compute_labor_monitor_result_at` internally — a pure,
behavior-preserving refactor, confirmed by running the full pre-existing
121-test `tests/test_domain_labor.py` suite unchanged before AND after
the edit.

### `app/domain/labor_what_changed.py` — the pure comparator, zero `labor_v1.0` knowledge

Four public functions (`compare_employment_section`,
`compare_unemployment_section`, `compare_labor_state`,
`assemble_labor_what_changed_result`), two internal helpers
(`_state_events`, reused across all five state-shaped fields —
`LABOR.state`, `EMPLOYMENT.state`/`condition`/`momentum`,
`UNEMPLOYMENT.state`; `_metric_events`, reused across all six numeric
fields), and a deterministic sort (`COMPONENT_ORDER` →
`EVENT_TYPE_ORDER` → `FIELD_ORDER`, all three constants defined once
in `app/models/labor_what_changed.py`). The comparator never imports
`app.domain.labor` — checked structurally three ways: an import-name
guard, a module-prefix guard shared with every other domain module's
independence test, and an AST-level guard that no frozen deadband
literal (`50_000`/`0.2`) appears anywhere in the comparator's own
code, not just its imports. None of the four functions ever compares
`previous_period` to `current_period` — verified by a direct test that
passes them in reversed (later, earlier) order and confirms no
exception and no distorted output, the same property
`app.domain.inflation_what_changed`'s own equivalent functions already
established.

### `condition`/`momentum` report independently of `state` — never suppressed, including in the summary flag

The frozen spec's central design principle (§6), applied literally:
`EMPLOYMENT.state`, `EMPLOYMENT.condition`, and `EMPLOYMENT.momentum`
are each compared as their own `_state_events` call, so a momentum-only
transition (e.g. the real April→May 2021 STEADY→IMPROVING momentum
shift, which left `EMPLOYMENT.state` at `EXPANDING` both months) never
disappears. This surfaced a real design gap during implementation: the
frozen schema sketch's own `EmploymentSectionChanges.state_changed: bool`
is ambiguous with THREE state-shaped fields in one section (Inflation's
equivalent sections each have exactly one, so the ambiguity never arose
there). Interpreting it as "any state-shaped field changed" would have
meant a momentum-only or condition-only change silently flipped
`state_changed` to `True` too — reintroducing, at the summary-flag
level, exactly the suppression problem this increment's independent-
reporting principle exists to prevent. Resolved by scoping
`state_changed` specifically to the field literally named `state`
(`metric_changed`/`availability_lost`/`availability_restored` remain
section-wide, matching Inflation's own established precedent, where
those three flags already span both the state field and every metric
field collectively). A dedicated regression
(`TestEmploymentMomentumChangeIndependentOfState`, using the real
April/May 2021 PAYEMS data) pins this exact scenario. Documented here
as a disclosed, deliberate refinement of the frozen schema sketch, not
a silent deviation.

### `previous_evidence`/`current_evidence` are never `None` — a second, disclosed refinement

The frozen schema sketch (§10) wrote `EmploymentResult | None` for both
section models' evidence fields. Implemented instead as required,
never-`None` fields: `labor_v1.0`'s own established convention already
represents "nothing here" with a real, `state: "INSUFFICIENT_DATA"`-shaped
object and empty `observations` (see #20B's own
`_insufficient_labor_monitor_result`), never Python `None` — introducing
a second way to express the same "no data" condition inside the
comparator's own models would be a needless inconsistency. Similarly,
`previous_labor_state`/`current_labor_state` are typed as the real
`LaborState` Literal (never `str | None`, since `"INSUFFICIENT_DATA"`
is itself a real member of that enum) — the frozen sketch's own
`LaborState | None` annotation was reconciled to match, matching how
every other Labor field already treats missing-data as a real
economic-availability value rather than an engineering `null`.

### Real UNRATE 2025-10 gap — reproduced at the comparison layer, fixture-based

The gap #20A.1's research first found (UNRATE has no persisted 2025-10
value) stays inside a rolling 3-month prior-year window for THREE
consecutive evaluation anchors (2026-10, -11, -12 all have `2025-10`
as one of `t-12`/`t-13`/`t-14` respectively — a fact this increment's
own worked-out arithmetic corrected mid-implementation; the initial
assumption that November alone would show restoration was wrong by
two months) and only exits at 2027-01. A dedicated test
(`TestRealUnrate202510GapAtTheWhatChangedLayer`) proves both the exact
availability-loss transition (September→October 2026) and the exact
availability-restoration transition (December 2026→January 2027)
against a fixture-based synthetic index (not a live FRED call), using
the same production `compute_unemployment_result` #20B's own single-period
test already validates this gap shape against.

### Historical regressions — real PAYEMS/UNRATE data across every validated period

`tests/test_domain_labor_what_changed.py` builds real `EmploymentResult`/
`UnemploymentResult` evidence (via `app.domain.labor`'s own frozen
primitives, called directly — not hand-typed numbers) from the same
cached FRED data that validated `labor_v1.0`, spanning: the 2008-2009
Great Recession (April→May 2009, the exact real month `EMPLOYMENT.state`
first flips `CONTRACTING`→`RECOVERING`; July→August 2009, metrics-only
confirmation of an ongoing recovery); the 2020 COVID collapse/snapback
(June→July 2020, the single largest real month-over-month swing in the
validated history — condition, momentum, AND state all flip at once,
while `UNEMPLOYMENT` stays `DETERIORATING` both months, proving a huge
payroll gain does not by itself mean `LABOR.state` improves); the 2021
recovery (April→May, May→June, the latter isolating a momentum-only
change); and 2022–2024 (July→August 2022, June→July 2023, July→August→
September 2024 — a `MIXED`→`STRENGTHENING` LABOR-state transition, a
quiet metrics-only quarter, and a condition/state change that leaves
momentum untouched, its mirror image the next month).

### Same-period revision support — proven, not just claimed

A direct test calls `compare_employment_section` with
`previous_period == current_period` (simulating a future release-
processing before/after-revision comparison) and confirms it produces
the correct events with zero code change — required by the frozen
spec so the exact same comparator serves both month-over-month
(`previous != current`) and same-period revision (`previous ==
current`) comparisons.

### API: `GET /api/v1/monitors/labor/changes`, no query parameters

Mirrors `GET /api/v1/monitors/inflation/changes` exactly — same
503 (not configured) / 503 (`OperationalError`) / 500 (`SQLAlchemyError`)
error mapping, same "missing data is a 200 with `comparison_available:
false`, never a 4xx/5xx" rule. Added to the SAME `router` #20B already
registered in `app/main.py` — no new router registration needed.
`tests/test_labor_architecture.py`'s route-count guard was updated
from "exactly one" to "exactly two," and its service-import guard was
extended to also enumerate the two new `app.domain.labor` entry points
plus a new guard enumerating the four `app.domain.labor_what_changed`
comparator imports — both changes are necessary, intentional
consequences of this increment's own scope, not relaxations of the
underlying "service never reimplements domain logic" principle.

### JOLTS / CIVPART / frontend — all confirmed absent

No `JTS*` series ID, no `CIVPART`, no `CONFIRMATION_CHANGED` event type
(Labor V1 has no confirmation component), no `CONDITION_CHANGED`/
`MOMENTUM_CHANGED` event type (condition/momentum reuse `STATE_CHANGED`,
discriminated by `field`) appears anywhere in the Labor What Changed
call graph — all checked by dedicated architecture-guard tests. No
`frontend/` file was touched.

### Tests

90 new backend tests (1,021 → **1,111**): 47 pure-comparator unit
tests (`tests/test_domain_labor_what_changed.py`: every state/
condition/momentum transition using real historical PAYEMS/UNRATE
data, availability loss/restoration including co-occurring
EMPLOYMENT+LABOR loss from one PAYEMS gap, the fixture-based real
UNRATE 2025-10 gap reproduction, exact-float-inequality metric proofs,
deterministic ordering, the fully-identical no-change case, same-period
revision support, and period passthrough/non-substitution); 3 new
architecture-guard tests plus 2 rewritten ones in
`tests/test_labor_architecture.py` (comparator never imports
`app.domain.labor`, no frozen deadband literal anywhere in the
comparator's own code, `labor_what_changed_v1.0`'s own frozen
vocabulary/ordering constants pinned exactly, service-import guards
extended for both new domain seams); 1 new test in
`tests/test_domain_architectural_independence.py` (the comparator
joins the domain-file allowlist and gets its own
no-other-domain-module-import guard, mirroring Inflation's identical
precedent); 11 service-level integration tests
(`tests/integration/test_labor_what_changed_service.py`, real isolated
Postgres: ordinary month-over-month comparison, shared-period-pair
consistency across both sections, comparison-unavailable with no data
at all, an availability transition through the full service call,
a persisted revision changing the comparison deterministically,
non-mutation, and `current_labor_result` matching a separate
`get_result` call); 23 API tests
(`tests/api/test_labor_what_changed_api.py`: exact top-level and
per-section response contract, no query parameters accepted or
required, availability transitions, the no-change case, sparse/empty
data as a 200, 503/500 infrastructure mapping with no leaked detail,
determinism, non-mutation, and no FRED/OpenAI dependency).

### Verification

Backend: `TEST_DATABASE_URL=... pytest tests/ -q`, run twice: **1,111
passed** both times, 0 skipped. `alembic check`: no new upgrade
operations detected — no migration, as expected (no schema change at
all in this increment). No Python lint/typecheck tooling exists in
this project (unchanged from every prior increment). Frontend: not
touched; `git status` confined entirely to `app/domain/labor.py`
(two additive functions plus a behavior-preserving refactor),
`app/services/labor.py`, `app/api/labor.py`, two new files
(`app/models/labor_what_changed.py`, `app/domain/labor_what_changed.py`),
two modified test files, and three new test files.

### Deferred (named explicitly, not built here)

Everything #20B already deferred (JOLTS confirmation, `CIVPART`
context, Labor release-processing integration, any Overview frontend
surface, any cross-monitor aggregation) remains deferred, unchanged.
Additionally: any frontend consumption of `GET /monitors/labor/changes`
(this increment is backend-only, mirroring #18/#20B's own precedent of
shipping an API before its UI); the future release-processing
same-period revision comparison this increment's own
`previous_period == current_period` support was built to enable, but
does not itself perform (no `ReleaseSeriesMapping` row exists for
Labor yet — see #20B's own deferred section).

## Increment #20D.2 — Employment Situation Release Integration

Makes #18's release-driven update pipeline process Employment
Situation (FRED 50) and update canonical Labor intelligence,
implementing exactly what #20D.1 froze in
`docs/architecture/labor-release-integration-v1.md`. Release processing
orchestrates; `labor_v1.0` still calculates every economic value;
`labor_what_changed_v1.0` still performs every comparison — no layer
duplicates another's methodology.

### The mapping — a data migration, mirroring the CPI/PIO precedent exactly

`alembic/versions/09f4c0959e9f_*.py` seeds `Employment Situation →
PAYEMS`, `Employment Situation → UNRATE` — a straight copy of
`cd476d227f99`'s own established shape (release id resolved by
`(provider, provider_release_id)` lookup at migration-run time, never
hardcoded; downgrade removes only the rows this migration seeded).
Verified upgrade → downgrade → re-upgrade → `alembic check` all
produce the expected state, including "No new upgrade operations
detected" at head. A pre-existing #18 test
(`test_no_mapping_seeded_for_unrelated_release_families`) asserted
Employment Situation had NO mapping — correctly updated to remove it
from that list and given its own positive assertion
(`test_employment_situation_maps_exactly_payems_and_unrate`), since
that fact is now the frozen, intended state.

### `app/domain/labor_release_processing.py` — a new, independent propagation module

Mirrors `app/domain/release_processing.py`'s own role, scoped to Labor
only: `payems_affected_evaluation_periods` (the frozen sparse `{0,3,6}`
set, forward-only), `unrate_affected_evaluation_periods` (the frozen
`{0,1,2}∪{12,13,14}` two-cluster set, forward-only), and
`labor_affected_evaluation_periods` (their cross-series union). Every
offset was re-verified by direct execution against
`app.domain.labor.compute_employment_result`/`compute_unemployment_result`
(not copied from the #20D.1 freeze doc's own numbers) before being
encoded as constants. Imports no other domain module — re-derives its
own tiny `_add_months` calendar helper rather than importing
`month_before`, the identical self-containment discipline
`app.domain.release_processing._add_months` already established.
Deliberately `frozenset[date]` (periods only), never
`set[(component, date)]` pairs — Labor has no per-component evaluation
split the way Inflation does (one `compute_labor_monitor_result_at`
call already produces `LABOR`+`EMPLOYMENT`+`UNEMPLOYMENT` together).

### The service layer — explicit dispatch, two independent branches, never `elif`

`ReleaseProcessingService._apply_changes_and_compute_analysis` gained a
Labor branch alongside its existing Inflation one:
`_affected_labor_periods` (partition by series membership),
`_load_canonical_labor_observations`, `_evaluate_labor_at` (dispatches
to `compute_labor_monitor_result_at`, unmodified), `_diff_labor_at`
(dispatches to `compare_employment_section`/`compare_unemployment_section`/
`compare_labor_state`, unmodified, `previous_period = current_period =
period` — never `month_over_month_labor_periods`). Membership in
`_CANONICAL_SERIES_IDS` (Inflation) and `LABOR_SERIES_IDS` (Labor) is
checked independently for every changed observation, never as mutually
exclusive branches of one `if`/`elif` — a series belonging to both in
some future integration would correctly feed both, per the frozen
contract's own future-compatibility requirement. No adapter framework,
no registry beyond these two plain frozensets.

### A real, pre-existing #18 defect found and fixed — benefits Inflation too

While building the Labor branch's `AVAILABILITY_RESTORED` test (a NEW
PAYEMS observation completing a previously-incomplete window), the
"after" evidence read kept returning stale, pre-write data even though
the write had genuinely happened. Root cause: this project's session
factory sets `autoflush=False`
(`app.db.session._get_session_factory`), and
`ReleaseProcessingRepository.write_observation` never flushed. A
REVISED write mutates an already-identity-mapped ORM object in place,
so a later `select()`-based re-read happened to see it correctly
regardless (same Python object); a genuinely NEW observation has no
such object to mutate, so its `session.add(...)` alone was invisible to
a later re-read without an explicit flush — silently producing an
empty before/after diff for exactly the scenario
`labor_what_changed_v1.0`'s own `AVAILABILITY_RESTORED` event exists to
detect. This defect predates #20D.2 and affects Inflation's own write
path identically — it was never caught before because every existing
Inflation "before/after analysis" integration test happens to revise
already-persisted observations only, never introduces a genuinely NEW
one. Fixed with one `self._session.flush()` call at the end of
`write_observation` (the same "flush after a write that needs to be
immediately re-readable" pattern `create_series`/`add_check_run`
already establish in this exact file). Verified this fixes the Labor
scenario and causes zero regression across the full existing #18/#19B
suite (164 tests, unchanged, before and after).

### Multiple Labor evaluation periods — no schema change, confirmed empirically

A single revision that moves two of PAYEMS's own affected offsets (`r`
and `r+3`) produces `ReleaseAnalysisUpdate` rows at both evaluation
periods within one check run, each row carrying its own
`evaluation_period` — exactly the "no uniqueness constraint, one row
per event" cardinality #20D.1 predicted from the schema alone,
confirmed here against a real Postgres write/read.

### Component boundary widened, not the comparators

`AnalysisChangeRecord.component`/`DetectedAnalysisChange.component`
widened from `ChangeComponent` (Inflation's own Literal) to plain
`str`, exactly as frozen — the release-processing/read-model boundary
is generic transport/provenance metadata, never the owner of a
component vocabulary. `LaborChangeComponent`/`ChangeComponent`
themselves remain fully strongly-typed at their own comparator layers,
untouched. Regression-tested both directions: existing Inflation
component values still round-trip unchanged, and all three Labor
values (`LABOR`/`EMPLOYMENT`/`UNEMPLOYMENT`) now validate through both
the write model and the #19B read model, including a mixed
Inflation-and-Labor response in one occurrence.

### JOLTS / CIVPART / frontend / public endpoint — all confirmed absent

No `JTS*` series id, no `CIVPART`, no hardcoded `50_000`/`0.2` deadband
literal, and no reimplemented `EmploymentState`/`LaborState` table cell
string appears anywhere in the release-processing call graph — all
checked by dedicated AST-level architecture-guard tests, mirroring
#20C.2's own comparator-purity guard discipline. No `frontend/` file
touched; no new HTTP route; no scheduler/worker/cron; the CLI's only
change is two cosmetic wording updates ("Inflation" → "Inflation or
Labor").

### Tests

62 new backend tests (1,111 → **1,173**): 24 pure-domain unit tests
(`tests/test_domain_labor_release_processing.py`: exact PAYEMS/UNRATE
offset sets, the cancellation-zone exclusion, forward-only
directionality, multi-observation and cross-series union/dedup); 11
new architecture-guard tests
(`tests/test_release_processing_architecture.py`: Labor comparator/
evaluator reuse-by-name, no hardcoded deadband literal, no reimplemented
state-table string, no JOLTS/CIVPART) plus 1 new
`tests/test_domain_architectural_independence.py` test (the new
propagation module joins the domain-file allowlist and gets its own
no-other-domain-module-import guard); 1 new positive mapping assertion
in `tests/integration/test_release_processing_repository.py`
(alongside a corrected pre-existing negative one); 25 new/updated
service-level integration tests in
`tests/integration/test_release_processing_service.py` (real isolated
Postgres, the real Employment Situation release/mapping: availability
restoration, the exact `{0,3,6}`/`{0,1,2}∪{12,13,14}` propagation sets
including the cancellation-zone exclusion, cross-series union with an
overlapping period evaluated once, same-period-never-t-1 comparator
reuse, the full analysis-event matrix, observation-changed/analysis-
unchanged, multiple-period persistence, provider failure isolation in
both directions, database-failure rollback, and idempotency); 5 new
#19B read-model tests
(`tests/api/test_release_processing_read_api.py`: Labor component
round-tripping, mixed Inflation-and-Labor responses, historical
preservation across a later NO_CHANGE run); 1 new CLI integration test
(`tests/integration/test_process_release_cli.py`: the real Employment
Situation occurrence processes successfully through the unmodified
CLI entrypoint).

### Verification

Backend: `TEST_DATABASE_URL=... pytest tests/ -q`, run twice: **1,173
passed** both times, 0 skipped. `alembic check`: "No new upgrade
operations detected" at the new head (`09f4c0959e9f`) — the one new
migration is a data migration only, verified upgrade → downgrade →
re-upgrade against the real test database. No Python lint/typecheck
tooling exists in this project (unchanged from every prior increment).
Frontend: not touched; `git status` confined to five modified
production files (`app/models/release_processing.py`,
`app/models/release_processing_read.py`,
`app/repositories/release_processing_repository.py`,
`app/services/release_processing.py`,
`app/operations/process_release.py`), one new production file
(`app/domain/labor_release_processing.py`), one new migration, and six
modified/new test files.

### Deferred (named explicitly, not built here)

Everything #20B/#20C.2 already deferred remains deferred. Additionally,
per #20D.1's own frozen scope: any frontend consumption of Employment
Situation's processing evidence; a generic release-analysis adapter
framework (rejected for V1, per #20D.1 §24 — a third integration
reusing this same explicit-dispatch shape a second time would be the
appropriate trigger to reconsider); the future release-processing
same-period revision comparison this whole mechanism enables but a
production release-driven trigger has not yet actually exercised
against real FRED data (mocked FRED only, in every test here, per this
project's own established no-live-provider-in-tests discipline).

## Increment #20E.2 — Labor UI + Overview Integration

Implements the frozen `docs/architecture/labor-ui-v1.md` contract: a
dedicated `/labor` workspace, and a genuinely multi-domain Economic
Overview. Zero backend production changes — every need was already
satisfiable from the existing, confirmed `labor_v1.0`/
`labor_what_changed_v1.0` contracts and the release-processing
read model's existing `release_id` filter.

### `/labor` — the frozen 7-section hierarchy, not a mechanical Inflation clone

Current State → Employment → Unemployment → What Changed → Latest
Data Detected → Relevant Release → Evidence & methodology
(`pages/Labor.tsx`, five independent `useApiResource` calls). Employment
renders `EmploymentState` as the single primary badge with
condition/momentum as secondary explanatory text — the three-co-equal-badges
hypothesis the freeze doc itself floated was explicitly rejected.
Unemployment's own numeric fields (`current_3m_avg`/`prior_year_3m_avg`/
`delta_pp`) use the existing `formatPercent`/`formatPercentagePoints`
unchanged; Employment's three job-count fields use a new `formatJobs`
(`lib/laborFormat.ts`) instead — see the PAYEMS units section below for
why blending these two would have been a real bug.

### No directional color-coding — a deliberate departure from Inflation's own palette

`STRENGTHENING`/`COOLING`/`STABLE` (and every real `EmploymentState`/
`UnemploymentTrendState` value) all share one neutral tone;
`MIXED`→`caution`, `INSUFFICIENT_DATA`→`unavailable` (`lib/laborLabels.ts`).
Inflation's own `cool`(blue)/`warm`(orange) buckets for
COOLING/HEATING are a temperature metaphor, not a value judgment (more
or less inflation isn't obviously good or bad) — but "strengthening"
vs. "cooling" labor IS commonly read as good/bad, so Labor deliberately
declines to reuse that mapping. Text alone carries every distinction.

### PAYEMS units — two different units in one response, confirmed and protected

`EmploymentResult.current_3m_avg_jobs`/`prior_3m_avg_jobs`/
`momentum_delta_jobs` are already-converted actual jobs; the raw
`observations[].value` entries are still FRED-native "Thousands of
Persons" — the exact same response carries both. `formatJobs` (summary
tier) never divides; `formatRawObservationValue` (evidence tier) never
multiplies, and the evidence table explicitly labels its own column
"Value (Thousands of persons)" so a reader can never mistake a raw
`130,472` for the same unit as a summary-tier `-331,333`. Both formatters
and this exact distinction are directly regression-tested
(`lib/laborFormat.test.ts`), including the real August 2009 PAYEMS
values from the frozen research data.

### MIXED — contradiction shown, never hidden

`WhyLaborState` always shows both Employment's and Unemployment's own
canonical states side by side, not only when `state === "MIXED"` —
the same unconditional-disclosure shape `WhyThisState` already
establishes for Inflation. Curated copy (`content/explanations/labor.ts`)
explicitly cites the frozen agreement table's own "every RECOVERING
pairing is MIXED" rule, verified against
`research/labor_momentum/LABOR_V1_FROZEN_METHODOLOGY.md` §7 directly
rather than assumed. No exact deadband number (50,000 jobs / 0.2pp)
appears anywhere in explanation content — regression-tested.

### What Changed — a frozen 4-tier PRESENTATION priority over the backend's own flattened order

`components/labor/WhatChangedSection.tsx` filters (never reorders) the
backend's already-ordered `changes[]` into four tiers: top-level
`LABOR` state/availability; `EMPLOYMENT`/`UNEMPLOYMENT` state events;
condition/momentum events (reported independently, never suppressed by
a co-occurring state change — the exact reason #20C.2 emits them
independently in the first place); numeric `METRIC_CHANGED` events,
behind a secondary "Metric updates" disclosure so an exact-float-inequality-driven
quiet month never reads as dramatic as a real state transition. Every
event remains reachable; none is deleted from the inspectable UI.
Quiet-month copy: "No canonical Labor changes were reported for this
comparison." — never "Labor remained stable."

### Two real, pre-existing frontend bugs found by #20E.1's own audit — fixed here

`api/processingStatus.types.ts`'s `DetectedAnalysisChange.component`
was still typed with Inflation's own `ChangeComponent` Literal even
though the *backend* widened this field to plain `str` in #20D.2 —
widened to `string` here too, mirroring the backend's identical
reasoning (this read-model row is generic transport metadata, never a
component-vocabulary owner). `lib/detectedChangeFormat.ts`'s
`formatAnalysisValue` unconditionally assumed Inflation's own label
map for any "state" field — a Labor `EmploymentState` value like
`RECOVERING`/`EXPANDING` that Inflation's map doesn't recognize
previously rendered as the raw uppercase string. Fixed with a new,
domain-agnostic `humanizeEnumValue` fallback (`lib/format.ts`) rather
than hardcoding Labor's own vocabulary into a shared function — proven
to produce byte-identical output to every existing curated label for
every value already tested. A parallel fix (`analysisComponentLabel`/
`analysisFieldLabel`) makes the component/field labels in Overview's
"Latest Data Detected" section resolve correctly for Labor rows too —
previously `CHANGE_COMPONENT_LABELS[change.component]` rendered
literally nothing for a Labor component.

### Overview — two true peer domains, never an aggregate

`CurrentStateSection.tsx` now renders `InflationCurrentStateCard`/
`LaborCurrentStateCard` as two independently-gated sub-blocks under one
shared "Current State" heading — Inflation's monitor failing never
hides Labor's card and vice versa. The stale "Inflation is the first
fully deterministic monitor..." sentence is REMOVED, not replaced —
there's no monitor-count sentence that wouldn't itself go stale again
at a third monitor. "What Changed" gained the identical peer structure
(`WhatChangedPreview`/`LaborWhatChangedPreview`, both now plain
sub-cards under one shared heading rather than each owning its own
`<h2>`, so the existing `["Current State", "What Changed", "Latest
Data Detected", "Releases"]` heading-sequence test stays exactly
correct). Latest Data Detected and Releases needed **zero** Labor-specific
code — both already flow Employment Situation's own evidence through
automatically once the two bug fixes above landed. No aggregate
"Economy State"/score anywhere — two independent, sourced readings,
never combined.

### Latest Data Detected on `/labor` — scoped, not duplicated

`api/labor.ts`'s `getEmploymentSituationProcessingStatus` composes
three existing calls (`fetchUpcomingReleases`/`fetchRecentReleases` to
resolve Employment Situation's internal `release_id`, then
`fetchReleaseProcessingStatus(releaseId)` using the backend's
already-existing, previously-unused `release_id` query filter) into
one resource — genuinely different value from Overview's own unfiltered
default page, not a duplication: a reader on `/labor` sees Employment
Situation's own evidence regardless of how "busy" other releases have
been recently.

### Tests

44 new frontend test files' worth of coverage, 671 total (487 → 671,
run twice, identical): 43 new `pages/Labor.test.tsx` integration tests
(every `LaborState`/`EmploymentState`/`UnemploymentTrendState` value,
the contradictory-evidence test, PAYEMS unit-distinction regressions,
every What Changed event tier, five independent failure-isolation
scenarios, accessibility structure); 39 new
`content/explanations/labor.test.ts` tests (coverage, MIXED/RECOVERING/
INSUFFICIENT_DATA substance checks, no-threshold-leakage, no-investment-advice);
label/format unit tests (`lib/laborLabels.test.ts`,
`lib/laborFormat.test.ts`, extended `lib/format.test.ts`/
`lib/detectedChangeFormat.test.ts`); `App.test.tsx` extended for the
new nav entry and route; `pages/Overview.test.tsx` substantially
extended for the seven-resource peer structure and cross-domain
failure isolation; two architecture guards extended
(`no-overview-mutation.test.ts` for the two new read functions,
`no-economic-logic.test.ts` for the frozen 50,000-job/0.2pp deadband
comparison patterns, mirroring the backend's own AST-level guard).

### Verification

Frontend: `npm test`, run twice: **671 passed** both times, 0 skipped,
0 failed. `npm run typecheck`: clean. `npm run lint` (oxlint): 103
files scanned, 0 diagnostics. `npm run build`: succeeds. Backend:
`TEST_DATABASE_URL=... pytest tests/ -q`: **1,173 passed**, unchanged
from baseline — confirmed zero backend production files touched
(`git status --porcelain -- app/ alembic/ research/` empty).

### Deferred (named explicitly, not built here)

Charts (no chart library exists anywhere in this project; `/inflation`
itself has none despite richer available time-series data). A shared
cross-monitor `Badge`/label abstraction (two monitors don't yet justify
one). Any `/labor/employment`/`/labor/unemployment` sub-route. Any
Growth/Housing/JOLTS/CIVPART nav placeholder. A distinct payroll-benchmark-revision
disclosure sentence (none exists in the frozen methodology to
transcribe — confirmed by #20E.1's own audit, not invented here).

## Increment #22B — Overview Attention & Navigation Implementation

Implements the frozen `docs/product/overview-attention-model-v1.md`
contract (itself a corrected version of #22A's own first draft, see
that document's own §3A correction record). Zero backend production
changes — every decision was implementable from fields already on
`ChangeEvent`/`LaborChangeEvent`/`ReleaseProcessingStatusItem`, plus a
small frontend constant restating an already-committed backend fact.

### The core defect, and the fix: PRESENTATION salience, never a score

#21's audit found Overview's compact What Changed previews truncated
each domain's flat, *canonically* (structurally, not importance)
ordered `changes[]` to 3 — a section carrying only routine
`METRIC_CHANGED` events could occupy all 3 visible slots ahead of a
real `STATE_CHANGED` event in a later section. The fix is a
deterministic 4-tier classification over each event's `component`/
`field` membership only (`lib/inflationSalience.ts`,
`lib/laborSalience.ts`) — Tier 1 (primary domain state) → Tier 2
(structural change, including any-component availability) → Tier 3
(secondary/corroborating signal) → Tier 4 (routine metric, collapsed
behind a count-labeled disclosure, never capped). Labor's module is a
**refactor, not a new hierarchy**: `/labor`'s own shipped
`WhatChangedSection.tsx` already implemented this exact 4-way filter
(#20E.2); it's extracted verbatim so Overview reuses the identical,
already-tested logic. Inflation gets an analogous module implementing
the frozen table for the first time — `/inflation`'s own full page
uses fixed section order, not tiering, and stays untouched (out of
scope, confirmed by re-reading #21's own strongest scores: Investigate
and Explainability were never broken). Explicitly, by design: no score,
no magnitude-based sort, no severity/confidence/market-impact concept
anywhere — a new architecture guard (`no-economic-logic.test.ts`) scans
for exactly those smuggled-in shapes.

### Release category vs. canonical monitor relation — a real correction, not a hypothetical

#22A's own first draft used `releaseCategory()` — the existing,
honest-but-broad `/releases` display tag — as if it were equivalent to
"this release's data feeds a canonical monitor." It isn't: JOLTS
("192") carries the display category "Labor" but has zero seeded
`ReleaseSeriesMapping` rows in either backend migration
(`alembic/versions/09f4c0959e9f_...`/`cd476d227f99_...`, inspected
directly) — it is deferred from `labor_v1.0` entirely. A new, small,
separate constant (`lib/releaseMonitorRelation.ts`'s
`CANONICAL_MONITOR_RELEASE_IDS = {INFLATION: {"10","54"}, LABOR:
{"50"}}`) restates only the migration-verified fact, mirroring the
identical pattern `components/labor/RelevantRelease.tsx` already used
for Employment Situation alone. Every navigation/attribution decision
in this increment goes through this constant, never `releaseCategory()`
— enforced by a dedicated regression test
(`Overview.test.tsx`'s "THE JOLTS-EXCLUSION REGRESSION TEST") that
would have caught the original, corrected error.

### Recent Data Updates — renamed and restructured, DATA/INTELLIGENCE split preserved

"Latest Data Detected" → "Recent Data Updates" (matching the same
page's own "Upcoming/Recent Releases" naming convention one section
below it). Selection changed from one system-wide item
(`lib/selectLatestDataDetected.ts`, itself unmodified) to one slot per
canonical monitor domain — the same function called twice, pre-filtered
by `CANONICAL_MONITOR_RELEASE_IDS`. `components/overview/LatestDataDetected.tsx`
lost only its own `<section>`/`<h2>` wrapper (now a content-only slot
renderer, same `items` prop, same internals, same exports
`ObservationChangeRow`/`AnalysisChangeRow` that `components/labor/LatestDataDetected.tsx`
already imports) — its own 294-line test file
(`components/overview/LatestDataDetected.test.tsx`) required **zero
changes**, since none of its assertions touched the now-removed
heading. A new `components/overview/RecentDataUpdates.tsx` owns the
one shared heading and two independently-gated domain slots, mirroring
`CurrentStateSection`'s already-established peer-card pattern exactly.
The DATA-changed vs. INTELLIGENCE-changed sibling-array split (ADR-023)
is untouched.

### Closing the two #21 dead ends

`components/releases/ReleaseRow.tsx` gained an optional `showMonitorCta`
prop (default `false`) — "View Inflation →"/"View Labor →" for a
release with a real canonical monitor relation, "View Releases →" for
one without (JOLTS/GDP/Advance Retail Sales), so a non-monitor release
is never a hard dead end. Deliberately opt-in, not the default: the CTA
would be circular inside `ReleaseCalendarSection` (already on
`/releases`) and inside `RelevantRelease` (already on `/labor`,
Employment-Situation-only) — only `components/overview/UpcomingReleasesPreview.tsx`
(on Overview, never itself any of the three destinations) opts in.
Regression-tested from both directions: a dedicated
`pages/Releases.test.tsx` test proves the CTA never renders on
`/releases` itself, and a `pages/Labor.test.tsx` test proves the same
for `RelevantRelease`.

### CTA wording

"See full comparison →" → "View Inflation →"/"View Labor →" (What
Changed and Recent Data Updates), aligned with the existing "Open
Inflation →"/"Open Labor →" wording Current State already uses for the
same destinations — deliberately kept as a distinct verb ("Open" for a
compact-state card inviting exploration, "View" for a change/update
list inviting a fuller list), not unified into one word. New "View
Releases →" completes a consistent three-way "View {Destination} →"
pattern for the one context where it renders.

### Verification

Frontend: `npx vitest run`, run twice (plus several additional runs
while investigating one transient failure, see below): **731 passed**
both times, 0 skipped, 0 failed. `npm run typecheck`: clean. `npm run
lint` (oxlint): clean. `npm run build`: succeeds. Backend:
`TEST_DATABASE_URL=... pytest tests/ -q`: **1,173 passed**, unchanged
— confirmed zero backend files touched
(`git status --porcelain -- app/ alembic/ tests/` empty).

One frontend run, mid-increment, reported one failure in
`Overview.test.tsx > Current State > Inflation monitor fails; Labor's
own Current State card still renders` — a test this increment did not
touch, in a component (`CurrentStateSection`/`InflationCurrentStateCard`)
this increment did not modify. Five immediate re-runs of the full suite
were clean (696/696, before the later additions brought the total to
731). Per the explicit instruction to capture specifics rather than
silently relabel a flake: the exact test name and error
(`TestingLibraryElementError: Unable to find an element with the text:
Inflation data could not be loaded.`) are recorded here; it did not
reproduce again across eight subsequent full-suite runs this increment,
including the two final identical 731/731 runs above.

### New files

`lib/inflationSalience.ts`/`.test.ts`, `lib/laborSalience.ts`/`.test.ts`,
`lib/releaseMonitorRelation.ts`/`.test.ts`,
`components/overview/RecentDataUpdates.tsx`.

### Deferred (named explicitly, not built here)

Any change to `/inflation`'s or `/labor`'s own full What Changed
sections. Any backend field, endpoint, or migration. A release detail
page. An `/inflation`-side scoped Recent-Data-Updates-equivalent
section (the asymmetry with `/labor`'s own scoped section is disclosed
in the frozen contract, not fixed here). Any cross-domain regime
synthesis, aggregate score, historical context, Compare surface,
Growth/third domain, chart, AI, notification, or account/save/watchlist
— all explicitly out of scope per the frozen contract and this
prompt's own scope guards.

## Increment #23C — Relate V1 Composition Implementation

Implements the frozen `docs/product/relate-composition-v1.md` contract
(itself downstream of `docs/product/relate-compare-audit-v1.md`'s own
finding that the minimum useful next step for "how does it relate?" is
deterministic COMPOSITION of already-canonical facts, never generic
Series Compare). Zero backend changes — every input this contract
needs was already present on `InflationMonitorResult`/
`LaborMonitorResult` as fetched today.

### Composition, not inference — the one rule everything else follows

`lib/relateComposition.ts`'s two pure functions
(`composeMonitorRelation`, `composeLaborComponents`) do nothing but
concatenate already-canonical field values, through the SAME label
functions used everywhere else in the product, into fixed sentence
templates. Neither function calculates, classifies, thresholds, scores,
or imports anything backend-shaped. A new, narrowly-scoped architecture
guard (`test/no-relate-inference.test.ts`) proves the Relate
implementation's own three files contain no regime label
(Goldilocks/stagflation/bullish/bearish/risk-on/risk-off/etc.), no
cross-domain agreement/divergence word, no correlation/spread
identifier, no backend import, and no invented methodology identifier
(`relate_v1.0` or similar) — deliberately scoped to just those three
files rather than the whole tree, since a whole-tree bare-word scan for
terms like "bullish" would re-trigger the exact false positive #22B
already found and fixed in this project's own correct, existing prose
explaining the ABSENCE of that framing.

### Overview — "How They Relate," period-honest by construction

A new section between Current State and What Changed
(`components/overview/HowTheyRelate.tsx`), reusing the exact same two
`useApiResource` results `CurrentStateSection` already consumes — no
new network call. Composes Inflation's `underlying_momentum.state`/
`calculation_period` with Labor's `state`/`evaluation_period` into one
of five deterministic branches: same-period ("As of {period}, Inflation
is {state} while Labor is {state}."), different-period (two
independent, explicitly period-stamped sentences, "while" never used),
Inflation-insufficient, Labor-insufficient, or both-insufficient — the
branch is selected on STATE, never on period-nullness alone, matching
the frozen contract's own defensive reasoning even though the two are
verified-coupled in the actual backend domain code. A resource error
(as opposed to a successful `INSUFFICIENT_DATA` response) never
composes a sentence at all — the working side's own individual fact
still renders, mirroring `CurrentStateSection`'s own established
failure-isolation discipline exactly. No sentence renders while either
resource is still loading.

### Labor — the composition lives inside the existing "Why" disclosure, not a new section

`components/labor/WhyLaborState.tsx` gained one appended sentence
(`composeLaborComponents`), after its existing evidence `<dl>` and
curated explanation text: "Employment is {state} and Unemployment is
{state}. Together, Economic Intelligence classifies Labor as {state}."
`LaborState` is a plain input to this function, read directly from
`LaborMonitorResult.state` — the function contains no combination logic
of its own and never re-implements `combine_labor_state`'s own existing
table. The frozen `/labor` 7-section hierarchy is unchanged — no new
heading, no new CTA; the `WhyLaborState` `<details>` toggle is the only
interaction. "Together, Economic Intelligence classifies... as..." is
not invented phrasing — it reuses the exact verb pattern
`content/explanations/labor.ts`'s own `MIXED` explanation already uses
for this identical concept.

### A deliberate asymmetry, stated explicitly so it can never be quietly lost

Labor's own sentence may name a real, existing combined conclusion
(`LaborState`) because one genuinely exists. The Overview cross-domain
sentence has no such existing combined conclusion to name — Inflation
and Labor have never been combined into anything — and must never
acquire one; an analogous "Together, Economic Intelligence classifies
the economy as X" for Overview would be exactly the forbidden regime
label. `composeMonitorRelation` contains no such branch, by design, not
by omission.

### Verification

Frontend: `npx vitest run`, run twice: **895 passed** both times, 0
skipped, 0 failed (671 baseline at #22A → 731 after #22B → 895 after
this increment). No transient failures observed this increment.
`npm run typecheck`: clean. `npm run lint` (oxlint): clean. `npm run
build`: succeeds. Backend: `TEST_DATABASE_URL=... pytest tests/ -q`:
**1,173 passed**, unchanged — confirmed zero backend files touched
(`git status --porcelain -- app/ alembic/ tests/` empty).

### New files

`lib/relateComposition.ts`/`.test.ts` (72 unit tests, including a full
prohibited-vocabulary sweep across every canonical Inflation × Labor
state pair), `components/overview/HowTheyRelate.tsx`,
`test/no-relate-inference.test.ts` (67 guard assertions).

### Deferred (named explicitly, not built here)

Series Compare (open or curated), charts, correlation/spread display,
cross-domain labels, historical relationships, lead-lag, causal
inference, investment implications, AI narration, a new economic
domain, state-history persistence, a `/relate` route, any new
top-level nav item.

## Increment #24C — State Duration V1 Backend Implementation

Implements the frozen `docs/product/state-duration-v1.md` contract's
backend half (§52). Backend-only: zero frontend files touched, zero
migrations, zero new tables, zero FRED/provider calls, zero AI, zero
methodology change — every economic calculation this increment
performs (`compute_series_momentum_at`, `compute_labor_monitor_result_at`)
already shipped, unmodified, before this increment began.

### The core rule this entire increment exists to protect

State Duration V1 computes **latest-revised reconstruction only** —
never recorded history, never a reconstruction of what was knowable at
the time. Every field name (`earliest_confirmed_period`, never
`start_period`; `history_type: "latest_revised_reconstruction"`, a
fixed trust-boundary literal) and every response shape decision below
exists partly to make that distinction structurally hard to lose in a
future increment, not merely to document it in prose.

### One narrow, genuinely domain-agnostic pure helper — the sole exception to "no shared abstraction" in this session

`app/domain/state_duration.py` is new: one pure function
(`evaluate_state_duration`) that walks an already-built, already-
reconstructed, most-recent-first sequence of `(period, state)` points
and returns `duration_months`/`boundary_type`/`earliest_confirmed_period`/
`previous_state`/`previous_period` — zero economic content, verified
structurally (`tests/test_domain_state_duration.py`'s own source-scan
guard proves the module's source text never mentions a real economic
state literal). Justified narrowly and differently from every other
"no premature generic framework" decision this project has made: the
walk-back's own *economic* computation (calling each domain's `_at`
function repeatedly) stays domain-specific, inside each monitor's own
service; only the pure counting/equality logic downstream of that is
shared, the same category of sharing `app.domain.analysis`'s own
`align_series`/`pearson_correlation` already established as acceptable
precedent. A dedicated AST-level guard
(`tests/test_domain_architectural_independence.py`) proves this module
imports no other domain module and — stricter than every other domain
module's own guard — no `app.models` module at all.

### Two independent service methods, not a shared "historical monitor service"

`InflationMonitorService.get_state_duration_result`/
`LaborMonitorService.get_state_duration_result` (`app/services/
inflation.py`/`labor.py`) each load their own required series once
(load-once strategy, §30 — the existing, unbounded
`get_observations_in_range` call already used by each service's own
`_load` helper, reused rather than duplicated), determine the current
canonical state/anchor period via the existing plain `_at`-free
functions, and — only if that state is real and non-
`INSUFFICIENT_DATA` — build a sequence of up to 60 reconstructed points
by calling `compute_series_momentum_at`/`compute_labor_monitor_result_at`
repeatedly at `month_before(anchor, 0..59)`, then hand that sequence to
the one shared pure helper. Each service defines its own
`_STATE_DURATION_LOOKBACK_BOUND_MONTHS = 60` constant independently
(§11/§7's own "no shared calendar/policy utility" discipline, restated
here for a policy constant rather than a calendar function) — same
number, two definitions, matching `month_before`'s own established
per-domain duplication.

### Response contract — a genuine two-shape union, not a flat model with nulled fields

`app/models/state_duration.py`'s `StateDurationResult` is a real
Pydantic discriminated union (`status: "AVAILABLE" | "CURRENT_INSUFFICIENT"`)
— deliberately different from this project's usual "single model,
availability flag" convention, because the frozen contract specifies
`CURRENT_INSUFFICIENT` as carrying no duration/period/boundary fields
at all, not merely nulled ones. `boundary_type` is the frozen
three-value `Literal["EXACT", "DATA_BOUNDED", "LOOKBACK_BOUNDED"]`,
never a boolean (guarded explicitly in
`tests/test_state_duration_architecture.py`).

### Two new, narrowly-named routes

`GET /api/v1/monitors/inflation/state-duration` and
`GET /api/v1/monitors/labor/state-duration` — added to the existing
`app/api/inflation.py`/`labor.py` router files (the same file each
monitor's own `/changes` route already lives in), not a new shared
"state-duration" router spanning both monitors. Deliberately not
`/history` (§31) — this endpoint returns exactly one fact today,
leaving room for a genuinely broader history endpoint later without
redefining this one. HTTP semantics mirror every existing monitor
route exactly: infrastructure failure → 503/500; every economic-data
outcome (`CURRENT_INSUFFICIENT`/`DATA_BOUNDED`/`LOOKBACK_BOUNDED`
included) → 200.

### Hand-derived test fixtures, not just calling the code under test

Every service-level and API-level EXACT/DATA_BOUNDED/LOOKBACK_BOUNDED
fixture (`tests/integration/test_inflation_state_duration_service.py`,
`tests/integration/test_labor_state_duration_service.py`,
`tests/api/test_*_state_duration_api.py`) is hand-derived against the
frozen classification formulas before being run — e.g. Inflation's
flat-baseline-plus-one-month-spike construction
(`r_3m ≈ 185.6`, `r_6m ≈ 69.0`, `r_12m = 30.0` at the spike month,
both far outside `[r_12m − 0.10, r_12m + 0.10]` → HEATING, vs. `STABLE`
one month earlier) and Labor's real `2025-10` UNRATE gap (the
project's own canonical worked example, `tests/test_domain_labor_release_processing.py`,
reused per §25/§47 as the required `DATA_BOUNDED` test case) — every
one of these passed on first execution against the hand-derived
expected value, not adjusted to match observed output.

### Verification

Backend: `TEST_DATABASE_URL=... pytest tests/ -q`, run twice: **1,256
passed** both times, 0 skipped, 0 failed (1,173 baseline at #23C →
1,256 after this increment; +83 new tests: 23 pure-helper/architecture,
12 Inflation service, 14 Labor service, 31 API, 3 updated pre-existing
guards for the new route/import). Frontend: `npx vitest run`:
**895 passed**, unchanged from the #23C baseline — confirmed zero
frontend files touched (`git status --porcelain -- frontend/` empty).
Production-diff audit: 4 modified backend files (`app/api/inflation.py`,
`app/api/labor.py`, `app/services/inflation.py`, `app/services/labor.py`),
2 new backend files (`app/domain/state_duration.py`,
`app/models/state_duration.py`), zero changes under `app/db/` or
`alembic/`. No lint/typecheck tooling is configured for this backend
(none present in `pyproject.toml`/`.venv`), matching every prior
backend increment this session.

### New files

`app/domain/state_duration.py`, `app/models/state_duration.py`,
`tests/test_domain_state_duration.py`,
`tests/test_state_duration_architecture.py`,
`tests/integration/test_inflation_state_duration_service.py`,
`tests/integration/test_labor_state_duration_service.py`,
`tests/api/test_inflation_state_duration_api.py`,
`tests/api/test_labor_state_duration_api.py`.

### Deferred (named explicitly, restated unchanged from #24A/#24B)

Recorded state-history persistence, a full `/history` endpoint, a
rendered state timeline, a rendered transition timeline, metric
charts, percentiles, qualitative "high"/"low"/"unusual" labels,
ALFRED/vintage-data integration, as-known-at-time reconstruction,
since-last-visit, notifications, Compare (any form), Growth,
AI-generated historical summaries, regime labels,
market-outcome/backtesting analysis. The frontend consumer of these
two new endpoints (§53) is #24D's own scope, gated on this increment.

## Increment #24D — State Duration V1 Frontend Implementation

Implements the frontend half of the frozen `docs/product/state-duration-v1.md`
contract (§53), gated on #24C's own completed backend. Frontend-only:
zero backend files touched (confirmed by an unchanged 1,256-passed
backend regression run and an empty `git status --porcelain -- app/`).
State Duration now renders as one new line inside each monitor page's
existing Hero section — never a new page section, never on Overview.

### One shared type/copy/component layer, mirroring the backend's own shared file

`api/stateDuration.types.ts` mirrors `app/models/state_duration.py`
field-for-field — a genuine two-shape union (`AVAILABLE`/
`CURRENT_INSUFFICIENT`), never flattened with nulled fields, reused by
BOTH `getInflationStateDuration` (added to `api/inflation.ts`) and
`getLaborStateDuration` (added to `api/labor.ts`), mirroring how the
backend's own `StateDurationResult` is one shared Pydantic union
returned by both routes rather than two near-duplicate per-monitor
types. `lib/stateDurationCopy.ts` is the one new, genuinely shared pure
function this increment adds on the frontend side — the same narrow
exception category #24C's own `evaluate_state_duration` already
established: it renders the exact frozen §37 templates
(EXACT/DATA_BOUNDED/LOOKBACK_BOUNDED/CURRENT_INSUFFICIENT, each an
independent branch of an exhaustive `switch`, never a shared
fallthrough per §42) from fields already on the response, with
pre-resolved label strings supplied by the caller — it never imports
`inflationStateLabel`/`laborStateLabel` itself and has zero series/
monitor knowledge. `components/StateDurationLine.tsx` is the one new
shared presentation component (loading skeleton / `ErrorMessage` /
rendered copy), reused identically by `InflationHero`/`LaborHero` via a
small per-monitor label-resolution wrapper at each call site (a safe,
precedented cast, since each endpoint only ever returns its own
monitor's real state values at runtime).

### Placement — inside the existing Hero, never a new section

`InflationHero.tsx`/`LaborHero.tsx` each gained one new prop
(`stateDuration`, an `ApiResourceState<StateDurationResult>`) and one
new line, placed directly after the existing period text and before
`WhyThisState`/`WhyLaborState` (frozen §39/§40) — fetched by the PAGE
(`InflationPage`/`LaborPage`), not inside the Hero itself, matching
this project's own established "page owns every resource, components
stay dumb" convention and giving the resource exactly one clear owner
(never re-fetched inside a disclosure). `WhyLaborState`'s existing
#23C Relate composition sentence is untouched and unaffected.

### Disclosure — additive, never replacing the existing sentence

The frozen §38 sentence lives in a new `STATE_DURATION_DISCLOSURE`
constant (`content/explanations/inflation.ts`, monitor-agnostic content
despite the file's name — the same file `LATEST_REVISED_DATA` already
lives in for the identical reason: `DataBasisNote.tsx` renders both,
shared by both pages) and is rendered as a THIRD paragraph inside the
existing "Latest revised data" disclosure, alongside (never replacing)
the two existing sentences.

### `previous_state`/`previous_period` — a deliberate, minimal, non-frozen placement decision

The frozen contract's own §37 copy templates never mention
`previous_state` in the primary sentence (`§37A`'s own worked example
omits it entirely), and no section of the frozen document specifies an
exact UI location/format for it beyond §44's general "adds real
verification value" claim. Rather than paraphrase the frozen primary
template to fit it in (explicitly forbidden), this increment renders
it as a separate, secondary, plainly factual line beneath the primary
sentence ("Previously {label}, as of {period}.") — EXACT-only, never
fabricated for `DATA_BOUNDED`/`LOOKBACK_BOUNDED`, never a timeline,
never an arrow. Noted here explicitly as a genuine implementation
judgment call within #24D's own discretion, not a frozen-contract
requirement reproduced verbatim.

### Hand-derived test fixtures, continuing #24C's own discipline

Every EXACT/DATA_BOUNDED/LOOKBACK_BOUNDED test fixture asserts the
exact frozen §37 sentence byte-for-byte (e.g. "Latest-revised
reconstruction: Cooling for 3 consecutive months, since April 2026."),
computed by hand against the frozen templates before being run, not
adjusted to match observed output — every one of them passed on first
execution.

### Verification

Frontend: `npx vitest run`, run twice consecutively: **1,032 passed**
both times, 0 skipped, 0 failed (895 baseline at #23C → 1,032 after
this increment; +137 new tests). One transient failure was observed in
an earlier full-suite run (a pre-existing, unrelated "What Changed"
empty-state test, `pages/Overview.test.tsx`) — investigated: 3/3
isolated re-runs of that file passed, and 5 of 6 total full-suite runs
this session passed cleanly with the identical test; the failing
assertion touches code this increment never modified. Concluded a
pre-existing, load-related timing flake under parallel `vmThreads`
execution, not a regression introduced by #24D — not silently
dismissed, verified. `npm run typecheck`: clean. `npm run lint`
(oxlint): clean. `npm run build`: succeeds. Backend:
`TEST_DATABASE_URL=... pytest tests/ -q`: **1,256 passed**, unchanged
— confirmed zero backend files touched.

### New files

`frontend/src/api/stateDuration.types.ts`,
`frontend/src/lib/stateDurationCopy.ts`/`.test.ts`,
`frontend/src/components/StateDurationLine.tsx`,
`frontend/src/test/fixtures/stateDuration.ts`,
`frontend/src/test/no-state-duration-reconstruction.test.ts` (79 guard
assertions, narrowly scoped to the three computing/rendering files).

### Deferred (named explicitly, restated unchanged from #24A/#24B/#24C)

Recorded state-history persistence, a full `/history` endpoint, a
rendered state timeline, a rendered transition timeline, metric
charts, percentiles, qualitative "high"/"low"/"unusual" labels,
ALFRED/vintage-data integration, as-known-at-time reconstruction,
since-last-visit, notifications, Compare (any form), Growth,
AI-generated historical summaries, regime labels,
market-outcome/backtesting analysis, Overview historical context, a
new top-level nav item.

## Increment #25C — Automated Economic Maintenance Implementation

Implements the frozen `docs/product/automated-economic-maintenance-v1.md`
contract (itself downstream of #25A's own product/retention audit and
#25B's own operational-design contract freeze): release processing can
now run without a human invoking the CLI by hand, on an external
scheduler's own cadence, while the existing manual path remains fully
available and equally safe. Backend/operational-only — zero frontend
changes, zero economic-methodology changes, zero new API surface.

### Scheduler/orchestrator separation, reusing the existing service unmodified

`app/services/maintenance.py` (`MaintenanceOrchestrator.run_sweep`) is
the new orchestration layer: discover due occurrences (a new,
narrowly-scoped read query, `ReleaseProcessingRepository.list_due_occurrence_ids`),
process each individually via the EXISTING, completely unmodified
`ReleaseProcessingService.process_occurrence`, and record sweep-level
operational health separately. It runs exactly one bounded sweep per
call and terminates — it never loops, sleeps, or schedules itself; an
external scheduler (any of: a developer's own local cron, a future
platform's scheduled-task feature) is responsible for invoking the new
CLI entry point (`python -m app.operations.run_maintenance`)
periodically. See ADR-024 for the durable boundary decision this
increment commits to (no in-process scheduler, no public HTTP trigger
for processing).

### Due-work discovery — settlement derived from the existing status enum, no new bookkeeping

The single most load-bearing finding carried over from #25B, confirmed
directly in code: `CheckRunStatus` is `NO_CHANGE`/`CHANGED` **only**
when every currently-active mapped series in that run succeeded (see
`_determine_status`, unmodified) — so "has a settled run today" is
provable from the existing, already-persisted status alone, with zero
new per-series bookkeeping. `list_due_occurrence_ids` therefore needs
exactly one condition beyond eligibility/bounding: no settled
(`NO_CHANGE`/`CHANGED`) `ReleaseCheckRun` with `completed_at` inside
today's UTC day (computed explicitly in Python, never via a
database-side `func.date()`, which would silently depend on the
connection's own session timezone rather than this project's
established UTC convention). This single condition naturally
implements both halves of the frozen contract's own conservative
settlement rule at once: an unsettled occurrence is due every sweep
until it settles or its retry window (default 7 days, operator-tunable
via `--retry-window-days`, never empirically pretended-precise) is
exhausted; a settled occurrence remains due exactly once more per
calendar day, for a genuinely late-arriving revision, never
permanently excluded and never unboundedly re-checked. A real bug was
caught and fixed during test-writing, not shipped: `process_occurrence`'s
own `completed_at` is always the real wall clock, never derived from
the caller's `as_of_date` — a test asserting same-day settlement must
therefore use today's real UTC date as its own `AS_OF`, exactly as
production always does, never a fixed historical date.

### Concurrency safety — a transaction-scoped PostgreSQL advisory lock, shared by both paths

`try_acquire_and_process_occurrence` (`app/services/release_processing.py`,
added alongside the unmodified `ReleaseProcessingService` class, never
inside it) acquires `pg_try_advisory_xact_lock(namespace, occurrence_id)`
before calling `process_occurrence` — zero schema change, automatically
released on commit or rollback including an unhandled crash, no
explicit unlock call that could ever leak. **Both** the automated
orchestrator and the existing manual CLI (`app/operations/process_release.py`,
updated to call this same wrapper instead of the bare service method)
now go through this one shared entry point, so the two paths can never
diverge in locking behavior — proven directly by an integration test
holding the lock via one real session while a second, independent
session attempts to process the same occurrence and is correctly
refused (`None`, never a race).

### Sweep record — worker health, never conflated with economic freshness

A new, small table (`maintenance_sweeps`, one migration) records
per-sweep operational health — `started_at`/`finished_at`/`status`/
`due_count`/`processed_count`/`failed_count` — deliberately never the
same table or concept as `ReleaseCheckRun` (per-occurrence, economic-
check-shaped). `finished_at`/`status`/the count columns are all
nullable and written together, once, at completion: a row with
`finished_at IS NULL` is the honest, intentional signal a crashed or
still-running sweep produces, proven directly by a test that simulates
a crash mid-sweep (due-work discovery itself raises) and confirms the
started row survives unfinished while a subsequent, ordinary sweep
recovers cleanly with zero special-cased recovery logic — inheriting
release processing's own pre-existing, already-strong crash-safety
guarantee (one transaction per occurrence) for free, since the
orchestrator was built never to batch occurrences into one shared
transaction.

### Verification

Backend: `TEST_DATABASE_URL=... pytest tests/ -q`, run twice: **1,324
passed** both times, 0 skipped, 0 failed (1,256 baseline at #24C →
1,324 after this increment; +68 new tests: due-work discovery, sweep
record, orchestrator integration — no-due-work/one/multiple
occurrences/provider and database failure/locking and concurrency/
manual+automatic coexistence/crash recovery/clock injection — CLI
integration, and architecture guards). One pre-existing whole-tree
guard (`tests/integration/test_transaction_and_safety.py`'s own
FRED/network-import allowlist) needed updating to include the two new
integration test files that legitimately mock FRED at the same method
boundary every sibling release-processing test already uses — not a
regression, an expected, narrow allowlist extension, exactly mirroring
that guard's own existing precedent. Frontend: `npx vitest run`:
**1,032 passed**, unchanged — confirmed zero frontend files touched
(`git status --porcelain -- frontend/` empty). Migration verified with
a real upgrade/downgrade/upgrade round-trip against the isolated test
database before any application code was written against it.

### New files

`app/services/maintenance.py`, `app/repositories/maintenance_repository.py`,
`app/operations/run_maintenance.py`,
`alembic/versions/f12b7ec0d626_create_maintenance_sweeps.py`,
`docs/adr/024-automated-maintenance-scheduler-orchestrator-separation.md`,
`tests/integration/test_maintenance_orchestrator.py`,
`tests/integration/test_maintenance_repository.py`,
`tests/integration/test_run_maintenance_cli.py`,
`tests/test_maintenance_architecture.py`.

### Deferred (named explicitly, restated from #25B)

Recorded canonical-state/monitor-snapshot persistence (sequenced
deliberately after this increment, per #25B §35/§42/§43, so the
resulting asset is comprehensive rather than gap-prone), Since Last
Visit (frontend, #25D's own scope, now unblocked for a genuinely
honest freshness story), Watchlist, notifications, accounts,
multi-device sync, alerting infrastructure, a generic job-queue
framework, Growth, Compare, AI.

## Increment #25E — Recorded State History V1 Persistence

Implements the frozen `docs/product/recorded-state-history-v1.md`
contract (#25D). Closes the exact gap #24A/#25B each independently
named: when release processing genuinely recomputes a canonical
monitor's top-level state and finds it *unchanged*, nothing durable
previously proved that recomputation happened — `ReleaseAnalysisUpdate`
is change-only by design. A new table, `recorded_monitor_results`, now
records every genuinely-executed canonical AFTER result, regardless of
whether it changed. Backend persistence only — zero read API, zero
frontend change, zero economic-methodology change.

### One new write step, inserted at the existing, unmodified computation point

`ReleaseProcessingService._apply_changes_and_compute_analysis`
(`app/services/release_processing.py`) already computed a genuine
AFTER canonical result (`_evaluate_component_at("PRIMARY_MOMENTUM")`/
`_evaluate_labor_at`) for `ReleaseAnalysisUpdate`'s own diffing
purposes — that exact, already-executing call is now also captured as
a `RecordableMonitorResult` (a new, second return value from the same
function, never a second computation) and persisted immediately after
`check_run = repo.add_check_run(...)` obtains a real id — the identical
point `add_observation_update`/`add_analysis_update` already wait for.
`ReleaseCheckRun`'s own creation point, meaning, and timing are
completely unchanged. One rule governs recording for both the
"unchanged state" and "unchanged data" cases at once: a row is written
whenever the AFTER call genuinely runs, full stop — a `NO_CHANGE` check
never reaches that call at all (traced directly: `_apply_changes_and_compute_analysis`
returns early, before any `_evaluate_*_at` call, whenever there are no
observation changes or no affected monitor), so it correctly produces
zero rows without any separate branch.

### Identity: scoped to a genuine computation event, not to the period alone

`UNIQUE(release_check_run_id, monitor, evaluation_period)` — never
`(monitor, evaluation_period, methodology_id)`, which would collide
across every legitimate repeat (a later release, a provider revision,
a manual retry). A single check run can legitimately produce several
rows for the same monitor (a Labor benchmark revision can affect
`{t, t+3, t+6}` in one call) — proven directly against real PostgreSQL,
including the one genuine duplicate case the constraint exists to
prevent (the same run/monitor/period pair twice) and the many
legitimate repeats it must never block (the same period across two
independent runs).

### Manual and automated paths produce identical results, with no new plumbing

Because the write step lives inside `process_occurrence` itself — the
one shared entry point both the manual CLI and the automated
maintenance orchestrator (#25C) already call, unmodified since #25C —
recording behaves identically regardless of origin, with zero
automation-specific logic added anywhere. `MaintenanceSweep` is
deliberately never referenced: no `sweep_id` is threaded into
`process_occurrence`, and manual processing (which has no sweep at
all) must produce equally valid records. Proven directly: the same
fixture, run once through the manual CLI (`app/operations/process_release.py`)
and once through `MaintenanceOrchestrator.run_sweep`, produces the same
shape of `RecordedMonitorResult` row either way.

### Insufficient-data results are recorded too, uniformly

Both domains' `_evaluate_*_at` functions can genuinely return
`INSUFFICIENT_DATA` as a real, successfully-computed classification —
recorded identically to any other state, using the domain's own
existing literal value (no new nullable "status" column). This makes
`RecordedMonitorResult` honestly canonical-*result* history, not
narrowly state-only history — it can prove "EI calculated and found
insufficient evidence at T," a deliberate, accepted scope decision
(contract §37/§38), not an oversight.

### Two pre-existing architecture guards updated by name, not loosened

`tests/test_release_processing_architecture.py::TestNoFullMonitorSnapshot`
and `tests/test_maintenance_architecture.py::TestNoRecordedStatePersistence`
were both deliberate trip-wires from #18/#25C, written specifically to
force a conscious decision the moment a monitor-result-shaped table was
introduced. Both were updated with a narrow, explicit, by-name
allowlist for exactly `recorded_monitor_results` — the substring match
itself (`"monitor_result"`, `"snapshot"`, `"recorded_state"`) is
otherwise unchanged and still catches any other, undesigned table —
mirroring #25C's own `NETWORK_EXCEPTIONS` extension precedent (a
narrow, expected allowlist extension, not a weakened guard).

### Verification

Backend: `TEST_DATABASE_URL=... pytest tests/ -q`, run twice: **1,375
passed** both times, 0 skipped, 0 failed (1,324 baseline at #25C → 1,375
after this increment; +51 new tests: model/repository/constraint tests
against real PostgreSQL, the Inflation/Labor changed and — critically —
*unchanged-state* integration tests proving the closed gap directly,
insufficient-data, NO_CHANGE, retries, revision immutability,
same-period multiple runs, partial/total provider failure, a real
database-failure transaction-rollback proof, manual and automated
equivalence, a hard read-side guard proving every monitor/state-
duration/what-changed `GET` route creates zero rows, and architecture
guards). Frontend: `npx vitest run`: **1,032 passed**, unchanged —
confirmed zero frontend files touched. Migration verified with a real
upgrade/downgrade/upgrade round-trip against the isolated test database.

### New files

`alembic/versions/f5420059a092_create_recorded_monitor_results.py`,
`docs/adr/025-recorded-state-history-append-only-persistence.md`,
`tests/integration/test_recorded_monitor_result_repository.py`,
`tests/api/test_recorded_monitor_result_read_side.py`,
`tests/test_recorded_monitor_result_architecture.py`. Modified:
`app/db/models.py` (`RecordedMonitorResult`), `app/models/release_processing.py`
(`RecordableMonitorResult`), `app/repositories/release_processing_repository.py`
(`add_recorded_monitor_result`), `app/services/release_processing.py`
(the new write step and two small per-domain builder helpers),
`tests/integration/test_release_processing_service.py`/
`test_maintenance_orchestrator.py`/`test_process_release_cli.py` (new
test classes), `tests/test_release_processing_architecture.py`/
`tests/test_maintenance_architecture.py` (the two allowlist updates
above).

### Deferred (named explicitly, restated from #25D)

A read API of any shape (persistence-only for this increment, per
#25D §100); frontend UI of any shape (§101); Since Last Visit itself
(unlocked, not built); metric/evidence snapshots (§41/§42); raw
observation vintages/ALFRED integration (§23); correction/invalidation
machinery (§31/§93); an automated-vs-manual provenance field (§28/§29);
Watchlist; accounts; notifications; Growth; Compare; AI.

## Increment #25G — Since Last Visit V1 Backend Read Model

Implements the frozen `docs/product/since-last-visit-v1.md` contract
(#25F) — the first RETURN capability this product has ever had. A new,
read-only endpoint (`GET /api/v1/since-last-visit`) answers "what did
EI record after checkpoint X through server watermark Y" using
exclusively already-persisted operational evidence — never AI, never a
reconstruction, never an economic-significance score. Backend-only —
zero migration, zero frontend change, zero methodology change.

### Server-authoritative watermark, captured before any query runs

The single design detail that makes the whole feature race-safe: the
service captures `through = datetime.now(timezone.utc)` **once**,
before any query executes, then filters `ReleaseCheckRun.completed_at
<= through`. A commit landing between that capture and the response
finishing is therefore *always* excluded from the current response and
*always* included in the next one (whose own `after` becomes this
response's `through`) — proven directly against a real, separately-
committing session (`TestRaceSafety`), not merely asserted. Even a
genuine first visit is bounded to the same 90-day default window as
any other visit (`resolve_window`'s own `effective_after` is never
`None`) — only the *response's* own `after` field reports `None` on a
first visit, a presentation fact kept deliberately distinct from the
real query boundary. A real bug was caught here during test-writing:
the first implementation let a first-visit's `None` leak into the
repository as a genuinely unbounded lower edge — caught immediately by
an end-to-end integration test, fixed before verification, not shipped.

### `ReleaseCheckRun` as the event spine — the cross-table ordering problem, solved once

`ReleaseObservationUpdate`/`ReleaseAnalysisUpdate`/`RecordedMonitorResult`
all carry `release_check_run_id` — filtering `ReleaseCheckRun` by
`completed_at` first, then joining out to exactly the selected runs'
children, turns a genuinely hard cross-table ordering problem into a
single-table one, with zero new schema and zero generic event ledger
(explicitly evaluated and rejected, per the frozen contract).

### Unchanged-confirmation — the central new capability, and the multi-period rule it shares with structural change

`app/domain/since_last_visit.py` (pure, no SQLAlchemy, no I/O — mirrors
`app/domain/state_duration.py`'s own precedent) implements the frozen
three-branch algorithm: a `RecordedMonitorResult` with no corresponding
Tier-1 `ReleaseAnalysisUpdate` for the same run is either the monitor's
system-wide first-ever recorded row (`FIRST_CALCULATION`, never
"remains") or a genuine re-verification (`UNCHANGED_CONFIRMATION`,
aggregated to one line with a count). One unified "max evaluation_period
per (run, monitor)" rule governs both Tier A (structural change) and
Tier B (unchanged confirmation) selection — the direct fix for the
exact multi-evaluation-period over-surfacing risk #25E's own test suite
discovered empirically. A real end-to-end integration test reproduced
this precisely: a PAYEMS revision propagating to `{05, 08, 11}` via the
frozen `{0,3,6}`-month rule correctly surfaces only the run's own
latest-touched period (2009-11, itself genuinely `INSUFFICIENT_DATA`
against this fixture's trailing data) — not the originally-revised
date, and never three separate items.

### Coverage — a third, honest evidence-based state, never inferred from code

`CHECKED`/`GAP`/`UNKNOWN`, derived strictly from persisted
`ReleaseCheckRun` settlement and `MaintenanceSweep` rows — never from
the mere existence of `app.services.maintenance`. `CHECKED` never
requires sweep evidence (manual-only processing is honestly `CHECKED`);
the `GAP`/`UNKNOWN` split is decided only when settlement is
incomplete, using sweep evidence exclusively.

### Verification

Backend: `TEST_DATABASE_URL=... pytest tests/ -q`, run twice: **1,463
passed** both times, 0 skipped, 0 failed (1,375 baseline at #25E → 1,463
after this increment; +88 new tests: 36 pure domain unit tests
covering every algorithm branch directly, 19 repository tests against
real PostgreSQL, 6 end-to-end service tests including the real-database
race-condition proof, 10 HTTP-level API tests, 17 architecture guards).
One pre-existing whole-tree guard (`tests/integration/test_transaction_and_safety.py`'s
own FRED/network-import allowlist) needed updating to include the new
integration test file that legitimately mocks FRED at the same method
boundary every sibling release-processing test already uses — not a
regression, the same narrow, expected allowlist extension #25C/#25E
already established. Frontend: `npx vitest run`: **1,032 passed**,
unchanged — confirmed zero frontend files touched. No migration —
every table this feature reads already existed.

### New files

`app/domain/since_last_visit.py`, `app/models/since_last_visit.py`,
`app/repositories/since_last_visit_repository.py`,
`app/services/since_last_visit.py`, `app/api/since_last_visit.py`,
`docs/adr/026-since-last-visit-server-watermark-and-event-spine.md`,
`tests/test_since_last_visit_domain.py`,
`tests/integration/test_since_last_visit_repository.py`,
`tests/integration/test_since_last_visit_service.py`,
`tests/api/test_since_last_visit_api.py`,
`tests/test_since_last_visit_architecture.py`. Modified: `app/main.py`
(router registration), `tests/integration/test_transaction_and_safety.py`
(the allowlist extension above).

### Deferred (named explicitly, restated from #25F)

#25H — Since Last Visit V1 Frontend (checkpoint storage, fetch,
render, the new time-of-day formatter, Overview wiring) — the natural
next increment, gated on this one. Historical-revision-propagation
detail (§68-71 of the contract); accounts; cross-device sync;
notifications; Watchlist; a read API beyond this one endpoint's own
frozen shape; AI summarization; Growth; Compare.

## Increment #25H — Since Last Visit V1 Frontend

Implements the frozen `docs/product/since-last-visit-v1.md` contract's
own frontend half (#25F), completing the RETURN loop #25A first
identified as this product's single missing link. A new "Since Your
Last Check" section — deliberately first on Overview — renders #25G's
own already-categorized recap verbatim, backed by this frontend's
first `localStorage` usage of any kind. Frontend-only — zero backend,
migration, or methodology change.

### The checkpoint write lives in its own effect, not inside the fetch's own `.then()`

`api/useSinceLastVisit.ts` reads the local checkpoint exactly once per
request (inside the fetch effect, keyed only by an internal reload
counter — never reactively re-read after a write, which would trigger
exactly the refetch-then-recap-disappears loop the frozen contract's
own §13 warns against). The checkpoint write itself lives in a
*second*, independent effect keyed on the hook's own `state` — firing
only once React has actually committed the "success" state, never
merely upon fetch resolution. This is the one implementation detail
that turns "checkpoint advances only after a successful render"
(contract §5/§92) from a hoped-for ordering into a structural property,
and comparing against an already-persisted-value ref before writing
makes the whole thing idempotent under React Strict Mode's own
deliberate double-invocation of effects — proven directly by a test
that mounts the hook under `<StrictMode>` and confirms the persisted
value is exactly the response's own `through`, never corrupted or
double-written.

### The one hard rule, proven both structurally and behaviorally

The ONLY value ever written to `localStorage` is the server's own
`through`, copied verbatim — never `Date.now()`, `new Date()`, or any
other browser-clock read, anywhere in the checkpoint path. Proven
structurally (`test/no-since-last-visit-derivation.test.ts`'s own
comment-stripped source scan for `Date.now()`/`new Date()`/
`performance.now()`) and behaviorally (a dedicated hook test mocks
`Date.now()` to return a wrong value and confirms the persisted
checkpoint is completely unaffected, still exactly `response.through`).
`lib/sinceLastVisitCheckpoint.ts` treats `localStorage` as untrusted
input throughout — a missing key, malformed JSON, a wrong
`schemaVersion`, or `getItem`/`setItem` throwing (private browsing,
disabled storage, a quota error) all degrade identically to "no
checkpoint" (read) or "write silently skipped" (write), never a thrown
error, never a blocked Overview.

### Frontend renders truth, it does not derive truth

`components/overview/SinceLastVisit.tsx` and its own pure copy module
(`lib/sinceLastVisitCopy.ts`, mirroring `lib/stateDurationCopy.ts`'s
identical "zero economic content" boundary) render #25G's own
already-categorized response verbatim — no transition derivation, no
"remains" inference, no evaluation-period selection, no
deduplication, no salience recomputation. A dedicated, narrowly-scoped
guard (`test/no-since-last-visit-derivation.test.ts`) proves this
structurally: no file compares `previous_value`/`current_value`, sorts
by `evaluation_period`, constructs a `RecalculationKind` from a
boolean expression, or ranks items by magnitude/severity.

### A genuine factual correction to #25F, discovered and applied

#25F's own §74 claimed "no time-of-day formatter exists yet" and froze
a requirement to build a new one. Fresh inspection this increment found
`lib/detectedChangeFormat.ts`'s own `formatCheckedAt` — built for
#19C's processing-status display, already handling exactly this need
(a UTC-offset-aware datetime, safe to parse via `new Date(...)` since
the value always carries an explicit offset) — already exists and was
simply missed by #25F's own narrower inspection of `lib/format.ts`
alone. Reused verbatim rather than building a redundant new formatter:
a smaller, more correct diff than the frozen contract itself
anticipated, not a contract violation (the underlying requirement —
a real, safe time-of-day display — is fully satisfied; only the
"build new" instruction was superseded by an existing asset that
already does the job).

### Coverage zero-state reconciliation

#25F's own §37-39 sketch named a fourth product-level "never processed"
row distinct from `GAP`/`UNKNOWN`; direct inspection of #25G's own
already-shipped `compute_coverage` (three machine values only) showed
"zero check runs at all" is already one of `GAP`'s own real underlying
causes, not a separate signal. `lib/sinceLastVisitCopy.ts`'s own
`domainZeroStateCopy` resolves this honestly using only the three real
values plus item presence, reusing §79's own frozen row-C wording
verbatim for the zero-item `GAP` case — documented explicitly as a
reasoned interpretation of an already-frozen, already-implemented
backend contract, not an invented fourth signal.

### Verification

Frontend: `npx vitest run`, run twice: **1,137 passed** both times,
identical (1,032 baseline at #25G → 1,137 after this increment; +105
new tests: pure checkpoint-storage tests including simulated
`getItem`/`setItem` throws, pure copy-template tests covering every
frozen sentence exactly, an API-client test, a dedicated hook test
including the Strict Mode and browser-clock guards, a component test
covering every copy variant and CTA, and the new architecture-guard
file). One pre-existing whole-tree guard
(`test/no-overview-mutation.test.ts`'s own "exactly N documented read
functions" allowlist) needed updating to include `useSinceLastVisit` —
not a regression, the exact narrow, expected allowlist extension that
guard's own docstring already anticipated for a genuinely new *existing*
resource call. `pages/Overview.test.tsx`'s own heading-sequence and CTA-
count assertions were updated to reflect the new, intentional section
and its own "View Inflation →"/"View Labor →" CTAs (3 → 4 each) — both
real, correctly-anticipated consequences of adding this section, not
incidental breakage. `tsc -b --noEmit` (typecheck), `oxlint` (lint),
and `vite build` (production build) all pass cleanly. Backend:
`TEST_DATABASE_URL=... pytest tests/ -q`: **1,463 passed**, unchanged —
confirmed zero backend files touched.

### New files

`frontend/src/api/sinceLastVisit.types.ts`, `sinceLastVisit.ts`,
`useSinceLastVisit.ts`, `frontend/src/lib/sinceLastVisitCheckpoint.ts`,
`sinceLastVisitCopy.ts`, `frontend/src/components/overview/SinceLastVisit.tsx`,
`frontend/src/test/fixtures/sinceLastVisit.ts`,
`frontend/src/test/no-since-last-visit-derivation.test.ts`, plus each
new module's own `*.test.ts(x)` sibling. Modified:
`frontend/src/pages/Overview.tsx` (new first section),
`frontend/src/pages/Overview.test.tsx` (mock setup, heading/CTA
assertions), `frontend/src/test/no-overview-mutation.test.ts` (the
allowlist extension above). No ADR — the durable architectural
decisions (server watermark, event spine, coverage model) were already
recorded by ADR-026 at the #25G stage; this increment's own choices
(effect ordering, Strict Mode idempotency, storage-failure handling)
are implementation detail governed by, not extending, that decision.

### Deferred (named explicitly, restated from #25F)

Historical-revision-propagation detail (§68-71/§117 of the contract);
accounts; cross-device sync; notifications; Watchlist; a generic
activity/history page; AI summaries; Growth; Compare; multi-tab
synchronization (§14, explicitly last-write-wins for V1).

## Increment #26C — Schema Compatibility + Readiness Implementation

Implements the frozen `docs/product/production-reliability-deployment-v1.md`
(#26B) contract's own compatibility-checking half, directly answering
the live incident #26A reproduced: the running application's own code
expected `recorded_monitor_results` (Alembic head `f5420059a092`); the
database it was pointed at was one migration behind (`09f4c0959e9f`).
`GET /health` reported `200 ok` throughout; nothing else checked
whether the code and the database agreed at all.

### The one shared compatibility check

`app/core/schema_compatibility.py` (new) — pure, bounded (imports
nothing from `app.services`/`app.domain`/`app.repositories`/
`app.clients`, no AI, no economic dependency of any kind): expected
revision is derived from the packaged migration files themselves
(`alembic.script.ScriptDirectory.get_heads()`), never a duplicated
hard-coded string; actual revision is read via one plain, read-only
`SELECT version_num FROM alembic_version`. Seven distinguishable
outcomes (`COMPATIBLE`/`SCHEMA_BEHIND`/`SCHEMA_AHEAD`/
`SCHEMA_UNINITIALIZED`/`SCHEMA_AMBIGUOUS`/`DATABASE_UNAVAILABLE`/
`CONFIGURATION_MISSING`) — never a boolean, never a guess when the
database's own state is genuinely ambiguous (more than one
`alembic_version` row, or a revision this application's own migration
graph does not recognize as an ancestor of its expected head). Never
issues `CREATE`/`ALTER`/`DROP`, never runs `alembic upgrade`/
`downgrade`, never calls `Base.metadata.create_all()` — proven
structurally (every `text(...)` SQL literal in the module is asserted
to start with `SELECT`) as well as behaviorally, against real
PostgreSQL, across every one of the seven states.

### Health vs. readiness, live-proven against the real, still-stale development database

`GET /health` (unchanged) stays process-liveness-only. `GET /readiness`
(new) evaluates the shared compatibility check and nothing else —
never FRED, never AI, never an economic calculation — returning `200`
with `ready: true` only on exact revision equality (#26B §8/§9's V1
policy), `503` with a public-safe `reason`
(`schema_mismatch`/`database_unreachable`/`configuration_missing`) and
the expected/actual revision strings otherwise. Verified live, this
increment, against the exact database #26A's own incident described,
deliberately left unrepaired: `/health` → `200 {"status":"ok"}`,
`/readiness` → `503 {"ready":false,"reason":"schema_mismatch",
"expected_schema_revision":"f5420059a092","actual_schema_revision":
"09f4c0959e9f","version":"<git sha>"}` — the exact incident, now
diagnosable in one request, without touching the affected database.

### Worker preflight — reused, not reimplemented

`app/operations/run_maintenance.py` and `app/operations/process_release.py`
each call the identical `check_schema_compatibility()` immediately
after their own existing configuration-presence checks, before
constructing a `FREDClient` or touching `ReleaseProcessingService`/
`MaintenanceOrchestrator` — proven structurally, by source-line
ordering, not merely by convention. An incompatible schema performs
zero economic processing: zero `MaintenanceSweep`/`ReleaseCheckRun`/
`ReleaseObservationUpdate`/`ReleaseAnalysisUpdate`/
`RecordedMonitorResult` rows, proven behaviorally against the isolated
schema-drift database (below). `run_maintenance.py` reuses its own
already-established fatal/configuration exit code `2`; `process_release.py`
reuses its own already-established, uniform exit code `1` — a small,
disclosed correction to #26B's own §20 prose, which assumed exit code
`2` applied uniformly to both CLIs without having verified
`process_release.py`'s own actual, already-shipped convention (it has
never had a distinct `2`).

### A second, isolated database this project's own tests can safely migrate backward

#26B's own §11 named the exact, mandatory question: why did 1,463
passing tests coexist with a live incident? Because `tests/conftest.py`'s
own `_apply_migrations` fixture always migrates the shared
`TEST_DATABASE_URL` database to head before any test runs, by design —
every test proves code correctness against a schema the harness itself
guarantees is current, never that a specific real database agrees with
the code. Deployment-drift tests need a database they can freely
migrate to an earlier revision, or leave genuinely uninitialized,
without ever disturbing that guarantee for every other suite. A new,
session-scoped fixture (`tests/conftest.py`'s `schema_drift_database_url`,
creating `economic_intelligence_schema_drift_test` if it does not
already exist) plus two small helpers
(`migrate_schema_drift_database`/`reset_schema_drift_database_to_nothing`)
give `tests/integration/test_schema_compatibility.py` a dedicated,
freely-mutable database — sixteen tests covering every state (head,
one/three revisions behind, an unknown/"ahead" revision simulated via
direct `alembic_version` overwrite, a genuinely never-migrated
database, a multi-row ambiguous state, an unreachable database, a
fresh-to-head round trip, and explicit no-mutation proofs) — the exact
class of test this whole increment exists to add, none of which could
have existed before this increment's own compatibility-check module
did.

### An existing architecture guard's own false positive, fixed the established way

`tests/test_maintenance_architecture.py::TestNoInProcessScheduler`'s
own pre-existing guard (`"maintenance" not in main_source.lower()`)
false-positived on `/readiness`'s own accurate docstring, which
correctly *names* `run_maintenance.py` in prose as one of the two CLIs
sharing its compatibility function — the identical false-positive
shape this project has now fixed three times (#25E's `Session`-in-
docstring guard, #25H's `Date.now()`-in-docstring guard, and now this
one). Fixed by switching the guard to the AST-based `_imported_module_names`
check its own sibling test in the same class already uses, rather than
a raw whole-file substring match — precise, intent-matching, and
consistent with this project's own established repair pattern, not a
loosened guard.

### Verification

Backend: `TEST_DATABASE_URL=... pytest tests/ -q`, run twice: **1,507
passed** both times, identical, 0 skipped (1,463 baseline at #26B →
1,507; +44 new tests: 16 schema-compatibility integration tests, 8
`/readiness` API tests, 1 `/health`-vs-`/readiness` proof, 4 worker-
preflight tests across both CLIs, 15 architecture guards). Frontend:
unchanged, **1,137 passed** — confirmed zero frontend files touched.
`tsc -b --noEmit`, `oxlint`, `vite build` all pass cleanly. The
developer's own `economic_intelligence` database remains exactly as
#26A found it (`alembic current` → `09f4c0959e9f`) — deliberately not
repaired this increment; its own live `/readiness` response is the
proof this increment set out to produce, not a byproduct to clean up.

### New files

`app/core/schema_compatibility.py`, `app/core/version.py`,
`app/models/readiness.py`, `tests/integration/test_schema_compatibility.py`,
`tests/api/test_readiness.py`, `tests/test_schema_compatibility_architecture.py`,
`docs/adr/027-schema-compatibility-exact-equality-and-readiness-split.md`.
Modified: `app/main.py` (new `/readiness` route), `app/operations/run_maintenance.py`/
`process_release.py` (preflight integration), `tests/conftest.py` (the
schema-drift database fixture/helpers), `tests/api/test_health.py` (the
health-vs-readiness proof), `tests/test_maintenance_architecture.py`
(the false-positive fix above). No migration — this increment adds
zero new Alembic revisions, per its own explicit scope.

### Deferred (named explicitly, per #26B's own implementation split)

Deployment pipeline, Docker, CI/CD, hosting configuration, scheduler
execution, maintenance-automation activation, backups, product
analytics, frontend features, economic methodology, AI — all
explicitly #26D/#26E/#26F's own scope, per #26B §61.

## Increment #26D — Deployment Packaging + Migration Release Process

Implements the frozen `docs/product/production-reliability-deployment-v1.md`
(#26B) contract's own deployment-packaging half: build → test →
migration preflight → apply migrations once → verify → deploy web →
smoke test, made real and repeatable for the first time in this
project's history. See `docs/adr/028-single-container-image-and-ci-validates-never-deploys.md`
for the durable architecture decisions; `docs/operations/production-release-runbook.md`
for the operator-facing companion.

### The one place this application's schema is ever advanced

`app/operations/release.py` (new) — `preflight` (read-only, reuses
#26C's own shared `check_schema_compatibility`, refuses on
`SCHEMA_AHEAD`/`SCHEMA_AMBIGUOUS`, never a downgrade) and `migrate`
(runs `preflight` first, calls `alembic.command.upgrade` exactly once,
then re-verifies `COMPATIBLE` before reporting success — a completed
upgrade that somehow leaves the database still incompatible is a
failure, never inferred success from "the call didn't raise"). Proven,
live, against a real dev server pointed at the real, still-unrepaired
database #26A's own incident describes:
`python -m app.operations.release preflight` reports `SCHEMA_BEHIND`
without mutating anything; `migrate` (exercised only against the
isolated schema-drift database in tests, never against that real
database this increment) genuinely reaches `COMPATIBLE`.

### A real hang, root-caused and fixed during this increment's own test-writing

Writing real-Postgres tests for `migrate`'s own idempotency and
refusal behavior surfaced a genuine bug in #26C's own test
infrastructure (`tests/conftest.py`'s `migrate_schema_drift_database`):
a test-only fixture (`drift_session`, since removed) opened a database
connection at PYTEST FIXTURE SETUP time -- before the test body's own
`migrate_schema_drift_database` call ran -- which then blocked that
call's own `DROP SCHEMA ... CASCADE` on a lock indefinitely. Fixed by
(1) never opening a connection until the exact point it's used, always
after arrangement (`drift_engine` now yields a lazy `Engine`, never a
pre-connected `Session`); (2) making the reset helper itself robust
regardless of cause -- force-terminating every OTHER backend connected
to the isolated drift database before resetting it, plus a short
`statement_timeout` so any future, unanticipated lock contention fails
loudly and fast rather than hanging the whole suite silently; (3)
`pool_pre_ping=True` on the test file's own engine, mirroring
`app/db/session.py`'s own already-established production pattern
exactly, so a connection killed by that termination step is
transparently replaced rather than surfaced as a false
`DATABASE_UNAVAILABLE`. A second, related fix: `revision="base"` now
genuinely reaches "alembic_version table exists, empty" (a real
`alembic downgrade base`, reached via head first) rather than "no
table at all" -- the two are distinct, real database states this
project's own compatibility module classifies identically but arrives
at via different code paths, and #26D's own test suite needed both
distinctly reachable, not merged by an implementation shortcut.

### Packaging: one image, three entry points

`Dockerfile` (new, **not build-verified in this environment -- no
Docker daemon available; honestly disclosed, not pretended**): pins
Python 3.12, installs only production dependencies, copies no
`.env`/`.git`/test artifacts (`.dockerignore`), defaults to the web
command, and documents the other two (`release`/`run_maintenance`/
`process_release`) as command overrides against the identical image --
never three separately-built, potentially-divergent images. Frontend
remains independently built/deployed static assets (confirmed
unchanged, existing architecture) -- not bundled into this image.

### CI: validates, never deploys

`.github/workflows/ci.yml` (new) -- backend suite against an ephemeral,
CI-local PostgreSQL service container (never production, never a real
credential -- confirmed by the complete absence of any `secrets.`
reference), plus frontend test/typecheck/lint/build. No deploy job
exists; CI never invokes `app.operations.release`/`run_maintenance`/
`process_release` (architecture-guarded). Validated with PyYAML
(`pyproject.toml`'s own `dev` extra, extended) as far as tooling in
this environment permits -- a real GitHub Actions run was not
triggered.

### Smoke test

`app/operations/smoke_test.py` (new) -- GET-only, checks `/health`,
`/readiness`, both monitor endpoints, `/since-last-visit`, and
`/releases`. Live-run against the real dev server this increment
otherwise left untouched: correctly reported 2 of 6 checks failing
(`/readiness` unready, `/since-last-visit` `500`) -- the exact, real
incident, detected mechanically by a read-only script, without
mutating anything.

### CORS, HTTPS, environment contract

CORS middleware remains absent, deliberately -- not required for the
current same-origin local-dev architecture; the runbook documents the
exact narrow-allowlist requirement for whenever frontend/backend
deploy cross-origin, not implemented here since the real origin(s)
depend on a hosting choice this increment does not make. HTTPS
requirement restated, not implemented (a platform/reverse-proxy
concern). `docs/operations/production-release-runbook.md`'s own
environment-variable table documents every variable NAME (never a
value) and its required/optional classification.

### Verification

Backend: `TEST_DATABASE_URL=... pytest tests/ -q`, run twice:
**1,552 passed** both times, identical, 0 skipped (1,507 baseline at
#26C → 1,552; +45 new tests: 21 release-command integration tests
against the isolated schema-drift database, 24 architecture guards
covering the release command, the web/migration boundary, the smoke
test's read-only property, the Dockerfile/`.dockerignore`, and the CI
workflow). Frontend: unchanged, **1,137 passed** -- confirmed zero
frontend files touched. `tsc -b --noEmit`, `oxlint`, `vite build` all
pass cleanly. The developer's own `economic_intelligence` database
remains exactly as #26A found it (`alembic current` →
`09f4c0959e9f`) -- deliberately not repaired.

### New files

`app/operations/release.py`, `app/operations/smoke_test.py`,
`Dockerfile`, `.dockerignore`, `.github/workflows/ci.yml`,
`tests/integration/test_release_cli.py`,
`tests/test_release_architecture.py`,
`docs/adr/028-single-container-image-and-ci-validates-never-deploys.md`,
`docs/operations/production-release-runbook.md`. Modified:
`tests/conftest.py` (the schema-drift fixture hang fix above),
`pyproject.toml` (`pyyaml` added to the `dev` extra). No migration --
this increment adds zero new Alembic revisions.

### Deferred (named explicitly, per #26B's own implementation split)

Hosting platform selection; scheduler activation and operator
observability (#26E); production bootstrap and reliability
verification, including the failure drills and the real backup/restore
rehearsal (#26F); CORS middleware itself (documented, not implemented,
pending a hosting/origin decision); a real `docker build`/`docker run`
verification (no Docker daemon available in this environment);
migration-role separation; connection-pool tuning; economic
methodology; AI; product analytics; onboarding; notifications;
accounts.

## Increment #26E — Maintenance Scheduler Activation + Operator Observability

Implements the operator-observability half of
`docs/product/production-reliability-deployment-v1.md` (#26B) §26/§54:
a read-only maintenance-worker heartbeat, and an honest verdict on
scheduler activation itself. See
`docs/adr/029-maintenance-health-semantics-and-scheduler-activation-deferred.md`
for the durable decisions; `docs/operations/production-release-runbook.md`
for the operator-facing detail (health-status table, alert minimums,
the exact automatic-maintenance claim threshold).

### Five states, derived from `MaintenanceSweep` alone

`app/domain/maintenance_health.py` (new, pure -- no SQLAlchemy, no
clock read, mirrors `app.domain.since_last_visit`'s own established
shape): `HEALTHY`/`DEGRADED`/`STALE`/`UNFINISHED`/`NEVER_RUN`, derived
from exactly two facts (the latest sweep regardless of completion, the
latest sweep that has actually finished) plus two operator-tunable
thresholds. `NEVER_RUN` is deliberately not treated as a failure in
the "something broke" sense -- it is the honest, expected answer
before activation. A sweep still running within its own grace period
never gets misclassified as crashed; overall health instead falls back
to the most recent sweep that has actually completed.
`app/services/maintenance_health.py` orchestrates: schema
compatibility (Increment #26C's own shared checker, reused unmodified)
is checked FIRST, before any sweep evidence is interpreted at all.
`app/repositories/maintenance_repository.py` gained one small,
additive method, `get_latest_finished_sweep` (no migration -- same
table, a narrower `WHERE` clause).

### The operator CLI, live-proven against the real incident once more

`python -m app.operations.maintenance_health` (new, read-only, never
calls FRED, never triggers a sweep) -- exit `0` healthy, `1`
unhealthy/degraded/stale/unfinished/never-run, `2` schema-incompatible/
DB-unavailable/config-missing, `--json` for machine consumption. Run
live against the real dev server's own still-unrepaired database: correctly
refused to interpret sweep history at all (`SCHEMA_BEHIND`, exit `2`)
-- the same real incident, once again diagnosed mechanically without
touching the affected database.

### Scheduler activation: implementation ready, honestly not activated

A reviewable GitHub Actions template
(`.github/workflows/scheduled-maintenance.yml.disabled`) exists --
syntactically valid, invoking the exact, unmodified production
maintenance command on the frozen hourly-order cadence, secrets
referenced by name only. Deliberately named with a `.disabled` suffix
so GitHub Actions cannot recognize or execute it on any trigger,
regardless of content -- this project has never been deployed
anywhere, so the question "can a scheduler reach the production
database without weakening its own access controls" has no honest
answer yet, and fabricating an active trigger against nothing would be
exactly the "code existence is not automation" mistake this
increment's own truthfulness requirement forbids. **Verdict: B --
IMPLEMENTATION READY, NOT ACTIVATED**, restated in the runbook as a
precise, checkable list of what activation actually requires.

### Sweep-level locking: audited again, still not added

Occurrence-level advisory locking (ADR-024) already prevents the one
dangerous outcome (duplicate audit rows for one occurrence). Two
overlapping full sweeps remain theoretically possible but operationally
implausible (hourly-order cadence against a typically-seconds-long
sweep, §49 of the maintenance contract) -- no sweep-level lock added,
reasoning recorded in ADR-029, mirroring #26D's own identical
migration-locking decision.

### Verification

Backend: `TEST_DATABASE_URL=... pytest tests/ -q`, run twice: **1,605
passed** both times, identical, 0 skipped (1,552 baseline at #26D →
1,605; +53 new tests: 14 pure domain tests, 10 real-Postgres service/
repository integration tests, 9 CLI integration tests, 20 architecture
guards -- all against the isolated schema-drift database, never
`TEST_DATABASE_URL` or the developer's own database). Existing #25C
maintenance tests (50), release-processing tests (101), and #26C/#26D
deployment tests (89) all re-confirmed green, unchanged. Frontend:
unchanged, **1,137 passed**. `tsc -b --noEmit`, `oxlint`, `vite build`
all pass cleanly. The developer's own `economic_intelligence` database
remains exactly as #26A found it.

### New files

`app/domain/maintenance_health.py`, `app/services/maintenance_health.py`,
`app/operations/maintenance_health.py`,
`.github/workflows/scheduled-maintenance.yml.disabled`,
`tests/test_maintenance_health_domain.py`,
`tests/integration/test_maintenance_health.py`,
`tests/integration/test_maintenance_health_cli.py`,
`tests/test_maintenance_health_architecture.py`,
`docs/adr/029-maintenance-health-semantics-and-scheduler-activation-deferred.md`.
Modified: `app/repositories/maintenance_repository.py`
(`get_latest_finished_sweep`), `docs/operations/production-release-runbook.md`.
No migration.

### Deferred (named explicitly)

Real scheduler activation (blocked on host selection + a security
review this project cannot perform against a nonexistent production
database); a real, wired alert destination (Slack/email/PagerDuty);
sweep-level locking (no observed need); persisted manual-vs-scheduled
sweep origin (no identified product requirement); production bootstrap
and the real backup/restore rehearsal (#26F); economic methodology;
AI; product analytics; onboarding; notifications; accounts.

## CI Reliability Fix — Frontend Node Runtime Contract (pre-#27B)

### Symptom

GitHub Actions' `frontend` job failed at `npm test -- --run` while
`npm ci` succeeded. Vitest reported `Test Files: no tests`,
`Tests: no tests`, `Errors: 40 errors` — every error the same:
`TypeError: webidl.util.markAsUncloneable is not a function`, raised from
`undici/lib/web/cache/cachestorage.js` ← `undici/index.js` ←
`jsdom/lib/api.js` during Vitest worker startup. This was not 40 failing
application tests; zero tests ever ran.

### Root cause

`ci.yml` hardcoded `node-version: "20"` (resolving to 20.20.2, EOL since
April 2026). The locked test chain requires a newer runtime:

| Package (locked) | `engines.node` |
|---|---|
| vitest 5.0.0 | `^22.12.0 \|\| ^24.0.0 \|\| >=26.0.0` |
| jsdom 30.0.1 | `^22.22.2 \|\| ^24.15.0 \|\| >=26.0.0` |
| undici 8.10.2 (jsdom dependency) | `>=22.19.0` |
| whatwg-url 17.1.1 | `^22.14.0 \|\| >=24.0.0` |

undici 8 binds `webidl.util.markAsUncloneable` directly to
`require('node:worker_threads').markAsUncloneable`, which does not exist
on Node 20 (`typeof` → `undefined` on 20.20.2; `function` on 24.x).
Constructing undici's `CacheStorage` at module load therefore throws the
moment jsdom is imported.

### Why no tests executed

`environment: "jsdom"` makes every Vitest worker import jsdom before
loading its test file. The suite has 40 test files → 40 worker startups
→ 40 identical import-time crashes → no test body ever ran.

### Why `npm ci` didn't catch it

`npm ci` reproduced the lockfile faithfully (identical versions locally
and in CI). npm only *warns* on `EBADENGINE` by default, so the runtime
mismatch was visible in the install log but never failed the job. The
project also had no single Node runtime contract: no `.nvmrc`/
`.node-version`, no `engines`, and CI's `"20"` contradicted the Node
v26.7.0 the frontend was originally scaffolded and verified on (Increment
016A). A fresh development machine here ran Node
24.4.1 — *also* below jsdom's `^24.15.0` floor, merely lucky enough to
have `markAsUncloneable`.

### Fix

- `/.nvmrc` = `24.21.0` (Node 24 "Krypton", Active LTS) — the single
  runtime contract. Read by nvm/fnm locally, by `actions/setup-node` via
  `node-version-file` in CI, and by Render (which reads `.nvmrc` from the
  repo root) for the Static Site build.
- `frontend/package.json` `engines.node: "^24.15.0"` (bounded range whose
  floor is jsdom's own requirement; mirrored into the lockfile's root
  entry only — no dependency changed).
- `frontend/.npmrc` `engine-strict=true`, so an unsupported Node now fails
  `npm ci` immediately with an explicit `EBADENGINE` error instead of a
  cryptic worker crash later.
- `actions/checkout`, `actions/setup-node`, `actions/setup-python`
  bumped to `@v7` (all `node24` runtimes, clearing the Node 20
  Actions-runtime deprecation warnings). Reviewed v5–v7 release notes:
  no breaking change affects this workflow's inputs.

No test, assertion, dependency version, or Vitest setting was changed.

### Verification (local; GitHub Actions itself not runnable locally)

- Reproduced the exact CI failure under Node 20.20.2 + npm 10.8.2 with the
  unmodified lockfile: `no tests`, `40 errors`, same stack.
- With the fix, Node 20.20.2 and the machine's Node 24.4.1 both fail
  `npm ci` at once with `EBADENGINE` (`Required: {"node":"^24.15.0"}`).
- Under Node 24.21.0 + npm 11.19.0, from a clean `node_modules`:
  `npm ci` OK; tests **40 files / 1,137 passed** (run twice, identical);
  `tsc -b --noEmit`, `oxlint`, `vite build` all clean.
- Backend (Python 3.12.13, local PostgreSQL 14.20):
  **1,603 passed, 2 skipped** — both skips are research tests requiring
  gitignored cached FRED data absent from a fresh clone; unrelated.

### Lesson

A lockfile pins *packages*, not the *runtime* that executes them.
Reproducible CI needs both: one committed runtime-version file consumed
by every environment (never a second hardcoded version in workflow YAML),
and engine checks that fail installation rather than warn. A green
`npm ci` is not evidence the toolchain can run.

## Increment #27B — MacroChipz Design System + Application Shell + Home + Theme

Baseline: HEAD `78e0edd` (the frontend CI runtime fix), clean tree,
aligned with `origin/main`. Node v24.21.0 / npm 11.19.0 via `.nvmrc`
(the machine's global Node is 24.4.1, below the contract, so every
command ran through `fnm exec --using=24.21.0`). Frontend baseline
1,137/1,137. Implements `docs/product/product-ui-ux-v1.md` (#27A)
§5-20, with this increment's own instructions overriding #27A where
they differ (below).

### Why MacroChipz lives only at the presentation layer

MacroChipz is the public brand; "Economic Intelligence" remains the
category and the name of the engine. The brand appears where a visitor
meets the product — document title, shell wordmark, footer, Home — and
nowhere else. Repository, Python package, API, database, storage keys,
architecture docs, and historical entries are unchanged. So is in-product
explanation copy that names the engine ("Together, Economic Intelligence
classifies Labor as Mixed"): about 40 such strings exist, several are
frozen and test-asserted (the #23B composed sentence), and they read
correctly as the engine's name. Whether any should say "MacroChipz"
belongs to #27C's copy pass, not a mechanical rename.

**#27A overridden here, by explicit instruction:** the hero does not say
"continuously monitors" (scheduled maintenance is designed, not activated
— ADR-029); a single CTA, "Explore the Overview", with no secondary CTA;
economic-state tokens are named `state-*`, never #27A §14's
`--color-positive/--color-negative`.

### Design system

One semantic token layer (`--mc-*`, OKLCH) in
`frontend/src/styles/globals.css`, defined for `:root` (light) and
`:root[data-theme="dark"]`, bound to Tailwind as `bg-canvas`,
`bg-surface{,-secondary,-elevated,-subtle}`,
`text-fg{,-secondary,-muted,-faint,-inverse}`,
`border-line{,-strong,-subtle}`, `brand*`/`focus`/`selected*`,
`feedback-{success,error,warning,info}*`, and
`state-{cool,neutral,warm,caution,unavailable}{,-subtle,-line}`. Dark
values are chosen independently (luminance steps for depth, softer
near-white text, lower-chroma state colors), never inverted. Brand is a
restrained ink-indigo, kept away from the state-cool hue so the brand
never reads as an economic signal. Every text/background pair was
checked with a WCAG script: all 70 pairs pass AA in both themes. The
old `text-neutral-400` metadata (about 2.5:1) became `fg-muted` (5.5:1
or better). `fg-faint` is used only on `aria-hidden` glyphs.

Existing components moved to the tokens by a mechanical,
one-to-one class substitution (44 files, no markup or hierarchy change):
`neutral-900/800 → fg`, `700/600 → fg-secondary`, `500/400 → fg-muted`,
`bg-white → bg-surface`, `border-neutral-200 → border-line`, and so on.
Without this, dark mode would have shown white cards on a dark canvas.
No raw palette color utility remains in `frontend/src`.

Typography: system font stack (no web-font dependency or licensing
cost); named roles as `@utility` classes (`type-display`,
`type-page-title`, `type-section-heading`, `type-card-heading`,
`type-label`, `type-meta`, `type-numeric`); tabular numerals globally
for `table`/`time`/`data`.

### Economic-state vs. feedback separation

The five-tone taxonomy was already domain-neutral (#27A §20); only its
palette was raw Tailwind. `Tone` and its class maps moved to
`frontend/src/design/stateTone.ts` (re-exported from
`lib/inflationLabels.ts`, so no domain import changed) and now use only
`state-*` tokens. Every canonical-state → tone mapping is unchanged.
Labor's states, including EXPANDING/CONTRACTING and
IMPROVING/DETERIORATING, remain `neutral`.

`design/stateTone.test.ts` guards the separation four ways:

- each tone's classes reference only that tone's own `state-*` tokens,
  and never a feedback, verdict, or color-word token;
- each theme's state tokens are literal colors, never a `var()` alias;
- no state token shares a value with any feedback token (explicitly
  `state-cool ≠ feedback-success` and `state-warm ≠ feedback-error`);
- no source line mixes `state-*` with `feedback-*`.

I proved it by injecting three regressions (cool → success classes,
warm aliased to the error variable, cool given success's exact value).
Each one failed the guard; the originals were then restored.

One existing leak was fixed along the way: `ScheduleStatusBadge`'s
SCHEDULED pill shared the "cool" state's sky palette. A schedule status
is release logistics, not an economic reading, so it now uses
`feedback-info`.

### Shell and width strategy

`layouts/AppShell.tsx` owns the global background, a sticky header
(wordmark linking Home, primary nav, theme control), the main landmark,
page padding, and a quiet footer ("Source data: FRED®, Federal Reserve
Bank of St. Louis."). `components/PageContainer.tsx` (`max-w-app` =
76rem, defined once in CSS) is the single width authority. The four
per-page `max-w-3xl` wrappers were removed, fixing #27A's double
constraint: desktop content went from about 768px to 1,152px at a
1440px viewport. Prose keeps `max-w-prose` as a per-paragraph reading
measure, not a page width. Pages now share `components/PageHeader.tsx`.
Their section structure is untouched, apart from one spacing fix: each
`divide-y` section gains bottom padding, so the rule no longer sits
directly under the section's last link (more visible at the new width).

A second width fix came from the populated-data review, not the empty
database. The What Changed comparison rows (Inflation's field ·
previous → current · delta grid, and Labor's header and period pair)
use a `1fr` column. At full width, that pushed each delta about 700px
away from the values it belongs to. These blocks now cap themselves at
`max-w-3xl`, a content-type reading width for a table that has to be
read across in pairs. It is the documented exception, not a
reintroduced page width; the section's own divider stays full-width.

Navigation is exactly Home · Overview · Inflation · Labor · Releases,
with `aria-current="page"` from `NavLink` and a tinted `selected` pill.
Below `md`, the *same* single `<ul>` collapses behind an `aria-expanded`
Menu button, rather than shrinking the desktop row. Escape closes it and
returns focus; choosing a link closes it. `/` is now Home and Overview
moved to `/overview`. No in-app link pointed to `/` as Overview.

### Home

`pages/Home.tsx` is deliberately static: it makes no fetch, so it has no
loading or error states and states no live economic conclusion (current
states live on Overview). It covers:

- a hero (MacroChipz / Economic Intelligence, the positioning line, the
  supporting copy, one CTA);
- the three questions, each mapped to its product answer;
- the five-step how-it-works flow as an ordered list (vertical on
  mobile, horizontal on large screens);
- the trust model: "Facts are sourced. Calculations are deterministic.
  AI is interpretive.", six principles, and the canonical
  `LATEST_REVISED_DATA` copy reused verbatim in the existing
  `Disclosure`;
- current coverage for exactly Inflation and Labor;
- a closing Overview CTA.

New primitives, each with a real consumer: `PageHeader`, `Section`,
`Card`, `ThemeToggle`. Deferred, not built: #27A §49's optional "About
the engineering" link. The empty right half of the desktop hero is left
as-is rather than filled with an invented visual.

### Theme architecture

Light / Dark / System, default System, persisted under
`economic-intelligence:theme`. This follows the project's existing
storage-key convention and its untrusted-storage discipline: any
unknown value or storage exception degrades to System.

- **Before first paint:** a ~15-line inline script in `index.html`
  resolves the preference (or `prefers-color-scheme`) and sets
  `data-theme` and `color-scheme` on `<html>`. A React effect would
  flash the wrong theme.
- **After load:** `theme/ThemeProvider.tsx` (mounted inside `App`)
  keeps the attribute in sync and follows live OS changes while on
  System.
- **The control:** `ThemeToggle` is a native radio group in a
  `fieldset` with a legend "Theme". Arrow keys, checked state, and
  names come from the platform; the icons carry visually hidden text
  names plus tooltips.
- **Keeping two implementations in agreement:** the script necessarily
  duplicates `resolveTheme`, so `theme/theme.test.ts` extracts it from
  `index.html`, executes it against a fake window/document for every
  stored value × OS preference × failure mode, and asserts agreement.
- **Scope:** theme changes token values only, never which state, label,
  or tone renders.
- **Motion:** no theme-switch animation was added. The existing pulse
  skeleton and disclosure chevron now respect `prefers-reduced-motion`.

### Tradeoffs

- The inline script is a second copy of `resolveTheme`. I accepted it
  because pre-paint correctness requires it, and it is pinned by an
  executing test. A future strict Content-Security-Policy would need a
  hash for it.
- The full-width domain pages are still single-column. At 1,152px they
  read as a wide left column with space on the right. This is honest
  inheritance, not a redesign: card grids and side-by-side pairs are
  #27C (#27A §23-40).
- `text-neutral-500` and `-400` both collapsed into `fg-muted`, losing a
  sub-AA tier of hierarchy. Readable contrast won.
- Labor was not touched. Its methodology, data-sufficiency handling, and
  components are unchanged apart from token classes and the reading
  width above. The development database was later bootstrapped through
  the existing `releases/sync` + `process_release` workflow as machine
  setup, outside this increment's diff.

### Verification

Frontend, Node v24.21.0 / npm 11.19.0, from a clean `npm ci`. The final
run did the clean install in a byte-identical copy of `frontend/`, so the
developer's running Vite server and its `node_modules` were never
touched; the suite was also run in the real working tree.

- tests: **44 files, 1,189 passed**, run twice with identical results
  (+52 cases: new suites for Home, ThemeToggle, theme, and the
  state-tone guard; `App.test` expanded; and per-file cases the existing
  architecture guards generate for the new source files);
- `tsc -b --noEmit` clean; `oxlint` 0 warnings / 0 errors (one
  fast-refresh warning found mid-increment was fixed); `vite build`
  clean;
- the only install output is npm 11's pre-existing `install-scripts`
  notice for macOS-only `fsevents`.

Backend (Python 3.12.13, local PostgreSQL 14.20): **1,603 passed,
2 skipped**, unchanged. Both skips are research tests needing gitignored
cached FRED data. No backend file changed.

Visual review happened in two passes, both using real headless Chrome
via `puppeteer-core` in a scratch directory, and GET requests only:

1. **Empty database** (the isolated test database): 12 captures. Found
   and fixed the `divide-y` spacing.
2. **Populated development database**, after the machine was
   bootstrapped. Real states: Inflation *Mixed* (July 2026), Labor
   *Mixed* (August 2026). 21 captures:
   - desktop, 1440px: Home light/dark, Overview light/dark, Inflation
     light/dark, Labor light/dark, Releases light/dark;
   - tablet, 820px: Home, Overview;
   - mobile, 390px: Home light/dark with the menu open, Overview
     light/dark, Inflation;
   - OS dark preference with System selected.

   Found and fixed the What Changed reading-width defect above.

Across all 21 populated captures: zero horizontal overflow, menu open
included, and `data-theme` already `dark` at DOM-interactive, before
the React bundle runs.

State coloring with real data: *Mixed* uses the caution tone.
Employment *Cooling* and Unemployment *Stable* use the neutral tone,
labor-ui-v1 §8. Release *Scheduled* uses the info tone and *Past due*
the neutral surface. Nothing economic renders in success or error
colors, in either theme.

No `.env` or secret value was read or displayed.

**Found with populated data, deliberately NOT fixed here** (pre-existing
content and backend behavior, not design-system defects; candidates for
#27C or a dedicated fix):

- Recent Data Updates prints unformatted floats in "tracked analysis
  changes" (e.g. `3.353016322755642`).
- The Labor bootstrap's analysis-change records carry evaluation
  periods a year ahead (e.g. "Prior-year 3M avg … August 1, 2027").
- Labor's "Latest data detected" names a future occurrence (December 4,
  2026) as "Not yet checked".

### Lessons

- **A second width constraint is invisible in code review and obvious
  on a screen.** Give layout exactly one width owner and make pages
  structurally unable to add another.
- **"Domain-neutral" has to be enforced at the token layer, not just in
  naming.** The tone *names* were already neutral, yet an unrelated
  badge had quietly borrowed the "cool" palette. A guard that compares
  actual values catches what naming discipline cannot.
- **When logic must be duplicated outside the bundle, test the copy by
  executing it,** not by re-describing it.
- **Review layout with real data, not only empty states.** The empty
  database hid the one width defect that mattered: a `1fr` column is
  harmless when every row reads "unavailable", and broken once real
  deltas appear.

## Increment #28 — Product Discovery & Data Feasibility (implementation deliberately paused)

Research and product definition only. No production code, no architecture
change, no SRS, no database touched, nothing committed. Baseline: HEAD
`225b5f6` (#27B), clean tree.

### Why implementation stopped

Eight increments produced a deterministic economic-intelligence engine that
works. What none of them established is **that anyone wants it**. #27A
surfaced a broader thesis — cross-market intelligence across economy, rates,
equities, FX and crypto — and the honest response to a thesis that large was
to test it before building on it, not after. Writing an SRS first would have
encoded assumptions this increment then proved false.

Two of those assumptions were false in ways that would have been expensive to
discover in code:

1. **Two of the five proposed domains cannot be licensed at $0.** Equity index
   levels are licensed products with no free commercial tier, and — verified in
   the CTA plan's own policy — delayed data receives *no* relief for index
   information. The free equity sources with usable closes (Stooq, Yahoo)
   carry express written prohibitions, not ambiguity. Crypto is capped at ~365
   days of history on the commercially-licensed aggregators, or needs a signed
   agreement of unknown cost.
2. **The "expected vs actual" frame is legally unavailable.** Release-level
   economist consensus and analyst EPS consensus have no free commercial
   source, and CME licenses *derived* data — so recomputing FedWatch-style
   probabilities from settlement prices is barred just as republishing them is.
   A UI promising an "Expected" column could not have been filled.

### What the research established

- **Free-to-access is not free-to-use.** Only public-domain US government data
  (BLS, Board of Governors, Treasury) and a small set of explicit grants (NY
  Fed rates, ECB reference rates, Treasury Fiscal Data) are usable in a paid
  product. FRED specifically carries three problems: a prohibition on apps that
  "replicate the essential user experience", a per-user API-key clause that sits
  badly with multi-tenant SaaS, and ~210,000 series whose grant covers internal
  commercial use rather than public redistribution.
- **A load-bearing design consequence:** breakevens and curve spreads are
  arithmetic over public-domain inputs. Computing them in-house instead of
  consuming FRED's `T10YIE`/`T10Y2Y` converts an amber dependency into a clean
  one at zero cost. The same reasoning removes FRED from the critical path
  generally: source direct from BLS/Board/Treasury, use ALFRED for vintages.
- **The competitive position is weak.** ORCA's Macro Dashboard ($29-35/mo)
  already ships regime classification with cross-asset confirmation, historical
  analogs with forward-return probabilities, and per-signal hit rates.
  MacroMicro (~$27-30/mo) is bundling "traceable, verifiable" AI into existing
  subscriptions free. A hobbyist site answers "what is today's regime and what
  changed" for $0. The investor pool is flat (FINRA: new-investor inflow fell
  21% → 8%), and the $10-50 band is the most crowded shelf in the category
  while the actual target customer demonstrably pays $55-165/mo elsewhere.

### The one finding that reuses what already exists

No reviewed product handles **point-in-time correctness** — what was knowable
when, and how a revision changed the answer. ALFRED has vintages but no
analysis; every analysis product silently uses revised data, including in
backtests. That is precisely the discipline this repository already enforces:
`NEW`/`REVISED`/`UNCHANGED` classification, append-only recorded results,
release-processing audit rows, and a shipped disclosure that refuses to pass a
reconstruction off as a real-time record.

It is a real moat and an unproven purchase reason. Both halves are stated in
the artifact.

### Boundary work, reusing an already-frozen decision

`relate-compare-audit-v1.md` §11 and `relate-composition-v1.md` §2 already
prohibit cross-domain "confirms"/"diverges" language as inference. #28 did not
reopen that. Instead it found that **"market vs data" is same-concept
confirmation (Class A), not cross-domain (Class C)**: a breakeven and a
realized CPI rate measure one concept by two constructions, exactly as Core PCE
and Core CPI already do. So "are markets pricing the same inflation story?" is
canonical, while "are equities confirming labor?" stays prohibited — and would
stay prohibited even if the equity data were free.

Related: market series should get **percentiles, not invented thresholds**. The
existing neutral bands (0.10pp; 50,000 jobs) are frozen constants asserted by
methodology — defensible for a monthly aggregate, much less so for a daily
market series whose volatility varies by regime. "Larger than 94% of 5-session
moves since 2003" needs no threshold and says more.

### Verdict

**NO-GO on the current thesis.** Not because the engineering is weak, but
because the market research does not support it, and choosing GO on the
strength of work already invested is exactly the failure this increment
existed to prevent. A narrower thesis — revision-aware, evidence-first
inflation-and-rates intelligence — survives feasibility and is buildable at $0,
but is unvalidated as a business. The artifact's §25 names five cheap
validation steps, two of which (licensing letters, a hand-written concierge
brief) can kill or redirect the project without any code.

### Artifact

`docs/product/macrochipz-product-discovery-data-feasibility-v1.md` — 26
sections, every licensing and pricing claim sourced to official documentation
with access dates, and unresolved items marked UNKNOWN — REQUIRES VERIFICATION
rather than guessed. No ADR: this increment made no durable architectural
decision. No SRS and no architecture change, both deliberately deferred.

### Lesson

**Feasibility research is cheaper than a rewrite, and the licensing question is
the one most likely to be skipped.** "Free to access" and "free to use in a
commercial product" differ on almost every source that matters, and the
difference is only visible in terms-of-use pages nobody reads until something
depends on them. Two days of reading changed the domain scope, removed a
headline feature, and reversed the build decision.

## Increment #29 — Rates Intelligence Foundation

Implementation. Baseline: HEAD `a81530b` (#28's discovery artifact),
clean tree. Adds one deterministic domain — U.S. interest rates — to the
backend. No AI, no probabilistic model, no frontend change.

### Scope chosen, and what was deliberately left out

#28 established which sources are usable at $0 in a commercial product.
#29 acts on that evidence rather than on the wish-list: **one provider,
six canonical series, two derived metric families.**

- Nominal Treasury par yields 2Y/5Y/10Y/30Y and real (TIPS) par yields
  5Y/10Y, from the two U.S. Treasury XML feeds — U.S. Government works,
  unauthenticated, no key to configure or leak.
- Derived server-side: 2s10s and 2s30s curve spreads (basis points), and
  5Y/10Y market-implied inflation compensation (percentage points).

**Policy and overnight rates (target range, EFFR, SOFR) were deferred on
purpose.** Each needs a second provider: the NY Fed's rates licence
carries two mandatory legends plus an indemnification clause, and the
FRED path carries the terms ambiguity #28 §10.2 documented. Holding V1
to a single provider keeps every observation's provenance and licensing
uniform, and makes the later addition a deliberate licence review rather
than a silent widening. `5s30s` was dropped for a simpler reason: 2s10s
and 2s30s already answer the V1 question, and every extra derived metric
is more surface to justify, test and explain.

### Two decisions that shaped everything else

**1. Windows count observations, not calendar days.** A "5-session
change" is the latest observation minus the one five published sessions
earlier. The obvious alternative — "5 days ago" — needs a fallback policy
for weekends, holidays and missing prints, and every such policy quietly
changes the number reported. Counting observations needs no fallback and
is reproducible by hand from the stored series. The cost is accepted
openly: `21_SESSIONS` is approximately, not exactly, a month, so the API
names windows in sessions and never relabels them "1M".

**2. Percentiles instead of invented thresholds.** Inflation and Labor
classify into named states because their methodologies define a neutral
band around a monthly aggregate. Doing the same for a daily market series
would mean inventing a cutoff — an economic claim wearing a UI label. So
`rates_v1.0` ships no `TIGHTENING`/`EASING`/`RISK_OFF` state at all. It
reports the level, the basis-point change over an explicit window, the
spread, and where that change sits in its own history. "Larger than 91%
of 5-session changes since 2004" needs no threshold and says more than a
label would.

### Canonical vs derived, kept structurally distinct

A derived value must never look like a sourced one, so the two carry
*different provenance types*. `SourceProvenance` has provider, dataset,
upstream field, source URL, retrieval time and revision count.
`DerivedProvenance` has a methodology ID, the calculation in words, its
input series and the calculation timestamp — and deliberately no provider
or dataset field at all. A test asserts that a spread's provenance
contains no `provider` key.

### Alignment and missing data

The rules are absolute and tested: a null value is not an observation
(dropped, never zero, never carried forward); a two-series metric
requires both sides on the *same* date (no nearest-date search, no
forward-fill, no interpolation); and an unavailable derived metric says
*which* of three things went wrong —
`NO_OBSERVATIONS_FOR_EITHER_SERIES`, `NO_OBSERVATIONS_FOR_ONE_SERIES`,
or `NO_EXACTLY_SHARED_OBSERVATION_DATE`. A series that was never ingested
behaves exactly like one with too little history: `available: false`
inside a normal 200, never an error. Only genuine database failure is a
503/500.

### Persistence

Two additive tables; nothing existing was altered, so every pre-#29 row
keeps its exact meaning and the downgrade is a clean drop (verified by
running upgrade → downgrade → upgrade against the isolated drift
database).

- `observation_provenance` — one row per (series, observation_date).
  Deliberately not columns on `economic_observations`: provenance
  describes the *retrieval event*, not the economic fact, and back-filling
  a fabricated provider for historical FRED rows would itself be a
  provenance lie. A missing row means "not recorded", never an assumed
  source.
- `rates_ingestion_runs` — that a sync was attempted and how it ended.
  Counts and an exception class name only; never a payload, never a body.

Idempotency lives in the repository, not in caller discipline:
`upsert_observation` returns `INSERTED` / `REVISED` / `UNCHANGED`. A
re-sync of identical data inserts nothing and advances no revision
counter — only `retrieved_at` moves — so `revision_count` stays a
meaningful count of genuine provider corrections.

### Structure

Read and write paths are separate classes, mirroring
`ReleaseReadService`/`ReleaseSyncService`: `RatesMonitorService` has no
Treasury client anywhere in its import graph, so a read is *incapable* of
triggering ingestion. An architecture test walks the transitive imports
and asserts exactly that.

### Security

The client hardcodes its host and a closed two-entry dataset allow-list;
an unknown dataset is refused before any request is built. The only
caller-supplied values (year, month) are range-checked and rendered
through integer formatting, never interpolated raw. Redirects are
disabled, so an upstream redirect can never carry a request to a host the
allow-list never approved (tested: a 301/302/307 surfaces as a typed
error). Responses are capped at 1MB. There is no API key anywhere in this
path, and no `.env` value was read during this increment.

### Verification

- Backend suite: **1,719 passed, 2 skipped** (up from 1,603; +116 tests).
  The 2 skips are the pre-existing research tests needing gitignored
  cached FRED data.
- New tests: 31 domain, 28 client, 22 service/repository integration, 17
  API, 18 architecture guards.
- Migration reversibility confirmed on the isolated drift database.
- **Live end-to-end against the real Treasury feed** (read-only, no
  writes): 13 sessions per dataset for 2026-09, latest 2026-09-18,
  2s10s = 25.0bp, 10Y compensation = 2.33pp, 10Y 5-session change =
  5.0bp — all matching hand arithmetic on the published values.
- Existing behavior intact: Inflation, Labor, Release Intelligence,
  Since Last Visit, recorded history and readiness all unchanged and
  green. The frontend was not touched.

**One existing-test change, and why it is maintenance rather than
weakening:** four integration modules pin the migration head as a literal
(`_HEAD`, `_ONE_BEFORE_HEAD`, `_THREE_BEFORE_HEAD`) precisely so that
adding a migration forces a conscious update. They were advanced by one
revision. `test_expected_revision_is_the_real_known_head` still compares
the application's computed head against that literal, so the guard keeps
working.

**A real defect the live test caught:** the first default timeout (15s)
timed out against the production feed. The failure path behaved correctly
— a typed `TreasuryTimeoutError`, no partial write — and the default is
now 30s, since Treasury's stack is materially slower than FRED's.

### Operator note

The development database is at the previous head; `alembic upgrade head`
is required before `POST /api/v1/rates/sync`. #29 did not migrate any
database outside the isolated test ones.

### Deferred

Policy/overnight rates; 5s30s; a Rates UI (no frontend work at all in
this increment); inclusion in automated maintenance sweeps (sync remains
explicit and operator-invoked); recorded-history integration for rates;
and the realized-inflation vs market-implied-compensation comparison —
#29 exposes the canonical metrics such a methodology would consume and
implements no comparison itself.

### Lesson

**Choosing the window rule is an economic decision disguised as a
technical one.** "5-day change" sounds unambiguous until the data has
weekends, holidays and missing prints in it — at which point the fallback
policy, not the definition, decides the number the user reads. Making the
rule "count observations" removed an entire class of silent
inconsistency, and cost only the honesty of naming windows in sessions
rather than months.

## Increment #30 — Rates Intelligence UI

Frontend increment. Baseline: HEAD `548bcd2` (#29), clean tree. Turns the
deterministic `rates_v1.0` backend into a Rates page inside the existing
MacroChipz shell. No AI, no probabilistic model, no new data provider.

### The defect inspection found first

Before writing any UI, reading the live contract turned up a real #29
bug: `curve_spreads[].changes` and their historical context were **100×
too large**. The 2s10s spread moved 27bp → 25bp — a 2bp narrowing — and
the API reported `-200.0` bp.

Root cause: `spread_series` emitted basis points, but every consumer of a
series (`change_over_sessions`, `historical_session_changes`) treats a
series value as a percentage-point level and converts differences to
basis points itself. The spread was therefore scaled twice.

Fix, minimal and deterministic: `spread_series` now returns percentage
points — the natural unit of a yield difference, and the same convention
`inflation_compensation_series` already used — and the service converts
once, at the model boundary, for the reported level. Levels were always
correct and stay correct; changes and context are now right. Two
regression tests pin it, including one asserting that a 2bp move reports
−2.0 bp rather than −200.0. This was the only backend change in #30, and
it is a correctness fix, not a contract extension.

### Hard rule: no financial calculation in React

Every number on the page is the backend's number. The frontend subtracts
nothing, converts nothing to basis points, and ranks nothing. Two guards
enforce that rather than trusting review:

- `frontend/src/test/no-rates-calculation.test.ts` scans the Rates
  modules for subtraction of rate-shaped values, `* 100` / `/ 100`
  conversions, and hand-written percentile or mean math.
- `tests/test_rates_architecture.py`'s frontend guard was **retargeted**.
  It previously forbade the canonical series identifiers
  (`UST_NOMINAL_`, `UST_REAL_`) anywhere in `frontend/src` — a sound
  proxy while no Rates UI existed, but it tested the absence of a UI, not
  the absence of a calculation. #30 legitimately renders those
  identifiers because the API returns them as provenance the evidence
  panels must display. The guard now matches assignment-with-arithmetic
  shapes instead. Both guards were mutation-tested: adding a
  `computeSpread()` helper to the frontend fails both.

The single arithmetic operation in the UI is `percentile * 100` to render
an already-computed 0..1 rank as "57th", which is unit formatting of the
same class as rendering 0.25 as "25%".

### Information hierarchy

Header (with the latest observation date) → Treasury yields (2Y/5Y/10Y/30Y)
→ curve chart with its derived spreads beside it → real yields →
market-implied inflation compensation → what changed → methodology.
Each card keeps its four session changes on the face and everything
heavier — ranks, provider, dataset, retrieval, source URL — one
disclosure away.

### Decisions worth recording

**The chart is hand-drawn inline SVG, not a library.** Four points and
two axes do not justify a dependency, a bundle cost, or a second theming
system to reconcile with #27B's tokens. Every stroke is a token, so both
themes work with no second palette. It is `aria-hidden`, and the same
numbers are published beneath it as a real `<table>` — a screen-reader
user gets the values, not a description of a picture. A maturity with no
value is omitted from the line rather than interpolated across, so a gap
in the data looks like a gap.

**Source vs derived is made visible three ways.** A "Calculated by
MacroChipz" marker on the face of every derived card, the inputs shown
inline as the arithmetic that produced the number, and two structurally
different provenance panels: a source panel names provider / dataset /
retrieval / source URL, while a derived panel names methodology /
calculation / inputs and deliberately has no provider field at all.

**Session windows are never relabelled.** Labels read "1 session",
"5 sessions", "21 sessions", "63 sessions". A test asserts the page never
contains "1 week", "1 month", or "3 months". The session explanation
copy *does* discuss months — to say 21 sessions is approximately, not
exactly, one month — which is why that assertion targets labels rather
than the whole page.

**Direction is not economic meaning.** A yield moving up is neither good
nor bad, so direction uses plain foreground tokens plus an arrow glyph
plus visually hidden text ("higher"/"lower"), never #27B's economic
`state-*` palette. That palette stays reserved for classified economic
states, which is exactly the separation #27B's own guard protects.

**Nav grew to six.** #27A §11 froze five destinations and refused
speculative slots; its stated condition for adding one was that the
content exist first. `rates_v1.0` shipped in #29, so Rates earns a slot.

### Two accuracy fixes found in visual review

Real data on screen caught things tests did not: the curve card stretched
to the height of the taller spreads column, leaving ~300px of dead space
(fixed with `h-fit`), and the change grid was cramped at four across
inside a narrow card (now 2×2). More substantively, the **global footer
still claimed "Source data: FRED®"** — false on a page whose data is
Treasury. Now that a second provider exists it reads "FRED®, Federal
Reserve Bank of St. Louis; U.S. Department of the Treasury."

### Verification

- Frontend: **47 files, 1,267 passed** (was 44 / 1,189; +78). Typecheck,
  lint (0 warnings), and production build all clean.
- Backend: **1,721 passed, 2 skipped** (was 1,719; +2 spread regression
  tests). The 2 skips are the pre-existing cached-FRED-data research
  tests.
- Visual review against the live backend with real Treasury data at
  1440px, 820px and 390px in both themes: zero horizontal overflow
  everywhere, six named regions, correct active nav, and hand-checked
  values on screen (2s10s 25 bp = 5.01 − 4.76; 10Y compensation 2.33% =
  5.01 − 2.68).

### Deferred

A compensation or yield history chart (the monitor endpoint returns
latest-plus-windows, not a series — adding one would be a contract
extension #30 did not need); per-window historical context (the backend
ranks the 5-session window only); and any cross-domain comparison
between realized inflation and market-implied compensation, which
remains a future methodology, not a UI feature.

### Lesson

**Reading the live contract before designing found a bug no test caught.**
#29's own tests asserted the spread *level*, which was always right, and
nothing asserted the spread's *change* — so a 100× error sat in a green
suite until someone tried to put the number on a screen. Building the
consumer is itself a test of the producer.

## Increment #31 — Observation Versioning & Deterministic Replay

Backend increment, no UI. Baseline: HEAD `0a85f56`, #30 in tree. Adds the
minimum temporal infrastructure to answer **"what data did MacroChipz
know at time T?"** and to prove a recorded conclusion reproduces from the
data available when it was made. No AI, no probabilistic model, no new
provider, no new route.

### What the pre-#31 audit actually found

Not a design gap — a measured one. Of 1,072 observations in the dev
database, 358 had any audit row at all, and all 714 Rates observations
had none. `_upsert_observations` overwrote `value` in place, so a
provider revision erased its predecessor. `RecordedMonitorResult`
(ADR-025) could prove *what* MacroChipz concluded and never *why*: the
inputs were gone.

### System time only, and why that is the honest choice

Each version carries a half-open interval `[recorded_from, recorded_to)`
— "when did MacroChipz hold this value?". There is deliberately **no**
second valid-time axis for "when did the provider publish it?". Our
providers do not reliably supply publication timestamps, and a column
that is accurate for some rows and guessed for the rest is worse than an
absent one. `observation_date` already carries the economic period. One
axis, fully honest, beats two where one is fabricated. See ADR-030.

Half-open matters concretely: `recorded_to = recorded_from` would be a
zero-length interval, invisible to every as-of query — a version that
exists but can never be observed. A check constraint rejects it.

### One algorithm, three write paths

`ObservationVersionWriter.apply()` does the canonical write *and* the
versioning write, and is the only place either happens. Series sync,
release processing, and Rates ingestion all delegate to it, tagged
`SERIES_SYNC` / `RELEASE_PROCESSING` / `RATES_INGESTION`. Three separate
implementations of interval-closing would drift, and a versioning layer
correct on two of three paths is not a versioning layer — it is a trap,
because its gaps are invisible at read time.

`apply()` returns `INSERTED` / `REVISED` / `UNCHANGED`, decided by the
value rather than by the caller. Re-writing an identical value produces
no new row: routine re-fetches of unchanged history would otherwise bury
genuine revisions under noise.

### The backfill says what it is

The migration creates one open version per existing observation with
`change_type`/`origin` = `BACKFILL`, `is_backfilled = true`, and
`recorded_from` = the observation's own `created_at`. That timestamp
honestly supports "this value existed by then" and nothing stronger.
**Pre-#31 revisions are permanently unrecoverable** — the data to recover
them was overwritten and does not exist. The flag rides all the way up to
`ReplayResult.inputs_include_backfilled` so no consumer can mistake
reconstructed provenance for observed provenance.

### Replay re-executes; it does not read back

`ReplayService` loads the recorded row *only to compare against*,
rebuilds inputs through `get_observations_as_of` at the row's own
`calculated_at`, and calls the same `app.domain` primitives release
processing used. Two refusals are deliberate:

- **As-of never falls back to the current value.** A series with no
  version covering the anchor returns nothing. Falling back would make
  every replay pass — which converts the feature from evidence into
  decoration.
- **Coverage is checked before any calculation.** An empty input set fed
  to the methodology would return `INSUFFICIENT_DATA`, which looks like
  an economic finding but is really a storage gap. Instead:
  `NOT_REPLAYABLE` with an explicit reason.

### Methodology versions are now bound to behavior

Before #31, `methodology_id` was a label, not a binding: `inflation_v1.0`
could have been changed to mean something different with nothing failing,
silently invalidating every historical row carrying it and making replay
a lie. `tests/test_methodology_golden_vectors.py` pins fixed inputs to
fixed outputs for both frozen methodologies. Changing what they compute
now breaks CI, and the only correct response is a **new** version with
**new** vectors — never an edit to these numbers.

The guard is a test, not a runtime registry. A registry with dispatch
would oblige production code to carry every past methodology forever, to
serve a guarantee CI satisfies completely.

Writing the vectors caught two of my own errors, both from asserting what
I expected rather than what the specs say: I asserted `STRENGTHENING` for
EXPANDING×STABLE, but the frozen agreement table
(`LABOR_V1_FROZEN_METHODOLOGY.md` §7) resolves that to `MIXED` — only four
combinations produce a clean state. And I hardcoded `2.4265743` where
`(1.002**12 - 1) * 100` is `2.426576794540325`. Both were fixed against
the specification, never against the code's output — a vector derived
from the code it guards guards nothing.

### The database enforces the invariants

A partial unique index allows at most one open version per
`(series, observation_date)`; a unique constraint forbids two versions
starting at the same instant; a check constraint rejects a non-increasing
interval. The invariant tests insert through raw SQL, bypassing the
repository entirely — so a pass means PostgreSQL refused the write, not
that the application declined to attempt it. Concurrency correctness does
not rest on application discipline.

### A testing problem worth recording

The migration tests initially failed in a way that looked like a code bug
and was actually a harness mismatch: `migrate_schema_drift_database()`
always resets the database first, which structurally cannot test a
backfill — a backfill can only be exercised by migrating *forward* over
data that already exists. It also terminates connections, so any engine
held across a migration dies with `AdminShutdown`.

Fix: a local `_alembic()` helper running the same subprocess pattern
without the reset, plus a short-lived engine per assertion instead of one
held across migration steps. The shared helper was left alone — its
reset-first behavior is correct for every other caller.

### Verification

- Backend: **1,777 passed, 2 skipped** (48 new: 25 versioning, 10 replay,
  13 golden vectors; plus 8 migration tests).
- Frontend untouched and green: typecheck, lint, 1,267 tests, build.
- Migration: upgrade → downgrade → upgrade clean; downgrade preserves
  every canonical observation; backfill leaves zero observations without
  history.
- Dev database after backfill: 1,072 observations → 1,072 open versions,
  0 orphans, 12 series.
- Live revision demonstration (inside a rolled-back transaction, so dev
  data was unchanged — re-verified after): identical value → `UNCHANGED`;
  changed value → `REVISED`; as-of before the revision returns the old
  value, as-of after returns the new one; the canonical cache follows the
  revision while history does not move.
- **Deterministic replay over all 133 real recorded results: 133 MATCH**
  (59 inflation, 74 labor), 0 mismatches, 0 not-replayable. 90 of those
  are substantive economic states rather than `INSUFFICIENT_DATA`.

### Deferred

Explicit input linkage (recording which observation versions fed each
result). The brief deferred it and said to stop and report if a concrete
correctness reason emerged; none did. Monitor inputs are deterministically
derivable from `(monitor, evaluation_period)` and the methodologies are
frozen, so the as-of reconstruction is exact. A future monitor with
*dynamic* input selection would change that — and is the trigger to
revisit. Also deferred: any replay route or UI, and valid-time
bitemporality.

### Lesson

**A temporal layer's only real test is whether it can fail.** Every design
choice here that felt like extra work — as-of not falling back to current
values, coverage checked before calculation, `is_backfilled` propagated to
the result, invariants in the database rather than the repository — exists
to preserve the possibility of a negative answer. A replay that always
returns MATCH proves nothing, and the cheapest way to build one is to be
slightly generous at each of those four points.

## Increment #32 — Point-in-Time Intelligence UX

Baseline: HEAD `49f1292` (#31), clean tree. Turns #31's temporal
foundation into a product surface on Inflation and Labor. No AI, no new
provider, no new economic methodology.

### The question the UI has to answer without lying

MacroChipz now knows two different things about the same month, and they
can legitimately disagree:

- **What it knew then** — the conclusion it durably recorded, re-derived
  from the observations available at `calculated_at`.
- **What today's revised data says** — the same methodology re-run at the
  same period against the current dataset.

Conflating those is the single most misleading thing this feature could
do, so the distinction is expressed in the types (`state` vs
`current_state`), in two headings that can never collide ("What
MacroChipz knew then" / "Using today's revised data"), and in a guard
asserting the second never contains the word "knew".

### The methodology names its own inputs

The best discovery of this increment, and it removed most of the design
risk: **neither monitor needed a new "which observations mattered"
concept, because both already report one.** `inflation_v1.0` resolves
t, t-1, t-3, t-6 and t-12 by exact calendar lookup and returns each as
`InflationMetricEvidence` with both endpoints and their values;
`labor_v1.0` returns every required month as `LaborObservationEvidence`,
explicitly including the ones that were missing.

So `historical_inputs` is read off the recomputed result rather than
from a lookback window this feature invented. A window would have been a
second definition of the methodology's input set, free to drift from the
real one. Replay already recomputes that result, so the input list falls
out of work that was being done anyway.

Same reasoning drives the comparison: `compute_series_momentum_at` /
`compute_labor_monitor_result_at` are called twice — once over as-of
data, once over current data, same period, same function — so any
difference is attributable to the data rather than to two code paths
that merely resemble each other.

### A units bug the symmetry caught

The first version compared replay evidence against a raw
`economic_observations` read. Every Labor input came back `REVISED` by a
factor of 1,000: `labor_v1.0` converts PAYEMS from FRED-native thousands
into actual jobs before putting it in evidence (158,268,000), while
storage holds 158,268.

The fix was not a conversion — it was to compare **evidence against
evidence**, so both sides speak the methodology's own unit by
construction and a unit mismatch becomes structurally impossible. The
backend also now declares `value_unit` per input, so the frontend never
infers a unit from a series id, which would be re-deriving a methodology
decision in React.

Worth recording because the bug was invisible to every backend test I
had written at that point and showed up only when real Labor data was
requested through the real route.

### Cause attribution stays evidence-backed

`recorded_monitor_results` and `release_observation_updates` share a
`release_check_run_id`. That is a real persisted link, not temporal
proximity — but it still does not record that one caused the other, and
ADR-023's "no causal nesting" applies unchanged. So:

- related changes are narrowed to observations this result's methodology
  actually used (a bootstrap run carries 118 changes; attaching all of
  them to each of 59 results would be true and useless),
- the remainder is **counted, not dropped** (`other_changes_in_same_run`),
- the copy says "processed in the same run… MacroChipz records that they
  happened together; it does not record that one caused the other",
- and a guard asserts no field name in the contract implies causation.

### Replay status is a verdict, not an economic state

#27B's hard rule keeps the `state-*` and `feedback-*` token families
disjoint because an economic state is a classification, not a verdict —
"Cooling" is not success. A replay outcome is the opposite kind of thing:
it IS a verdict, about MacroChipz's own integrity. So replay badges use
`feedback-*` (success / error / warning) and economic states keep
`state-*`, and a guard asserts the replay map never reaches for a
`state-*` token. A `MISMATCH` carries the error treatment plus a
screen-reader description saying plainly that it is a data-integrity
issue rather than an economic signal — never softened to "unverified".

### Refusing rather than faking

Three cases produce an explicit refusal instead of a number:

- **Methodology version differs** — no `current_state` at all. Today's
  code implements different rules; its answer is not "the same analysis
  on newer data". `state_differs` is `null`, never defaulted to `false`,
  which would read as "nothing changed".
- **Replay unavailable** — no historical inputs to compare against, so
  the input comparison is `NOT_COMPARABLE`. Today's reconstruction still
  stands on its own and is still reported.
- **Rates** — `/monitors/rates/history` is a 422, because Rates has
  observation versioning but records no monitor state. An empty list
  would imply a history that does not exist.

### Backfill, disclosed without alarm

Every real local result replays over #31 backfill, so every row carries a
quiet "Reconstructed inputs" chip and the detail carries the full
disclosure. The wording tracks the boundary frozen in
`recorded-state-history-v1.md` §23: reproducible from MacroChipz's own
stored data, but not proof of the provider's originally published
figures. #31 moved that boundary; it did not erase it.

### Verification

- Backend **1,833 passed, 2 skipped** (+56: 24 service, 14 API, 18
  architecture).
- Frontend **1,320 passed** (+53), typecheck / lint / build clean.
- Visual review at 1440 / 820 / 390 in light and dark: zero horizontal
  overflow and zero console errors at every breakpoint.
- History API exercised against the real local database: 59 inflation
  and 74 labor recorded results, all replaying MATCH, related changes
  correctly narrowed from 118 to the 5 the methodology used.

### Known limitation found during visual review

Labor's twelve most recent recorded results are all `INSUFFICIENT_DATA`,
for evaluation periods through October 2027. That is honest — those rows
really were recorded, for future periods with no data yet — and it is an
artifact of how the local database was bootstrapped, not of this
feature. It is left as-is deliberately: filtering `INSUFFICIENT_DATA`
out of recorded history would hide real recorded conclusions to make the
page look better, which is the opposite of what this surface is for.

### Deferred

Pagination controls (the section shows the most recent 12 of a bounded,
paginated endpoint), an Overview surface, a Rates equivalent (no
recorded state exists to surface), and user-selectable arbitrary
timestamps — nothing in the product question set required one.

### Lesson

**Ask what the existing code already proves before designing a new
concept.** The two hardest-looking requirements — "show the relevant
deterministic inputs" and "compare then against today" — turned out to
need no new economics at all, because the frozen methodologies already
emit their own exact inputs as evidence and already accept an explicit
period. The one place I *did* introduce a second path (evidence on one
side, raw storage on the other) is precisely where the only real bug of
the increment appeared.

## Increment #33 — Bounded MacroChipz Analyst

Baseline: HEAD `00a3c25` (#32), clean tree. The first generative-AI
capability in the product, added **after** deterministic ingestion,
calculation, provenance, observation versioning, replay and
point-in-time UX were all working independently.

**MacroChipz Analyst explains canonical intelligence. It does not create
canonical intelligence.**

### Why AI waited until #33

Not caution for its own sake. An interpretive layer is only safe when
there is something authoritative for it to defer to, and only useful
when that something is worth explaining. Until #31/#32, MacroChipz could
not have handed a model a complete, versioned, provenance-bearing
account of its own conclusions — so an "AI analyst" would have had to
derive economics itself, which is the failure this project has spent
thirty increments avoiding.

The repo also had direct evidence of what happens otherwise. Increment
#9 tried model-driven orchestration three times (prompt guidance, a
deterministic execution gate, dynamic tool-schema shaping). The last
attempt's own measurement: **the model supplied a `series_id` outside
the offered enum in roughly 60% of later-round calls**, and 16 of 28
live trials exhausted the round budget. ADR-018 is marked SUPERSEDED —
FAILED ACCEPTANCE GATE with that finding restated at the top.

### The boundary, stated structurally

```
canonical intelligence -> deterministic context packet -> ONE LLM call -> validated prose
```

Three properties, each a fact about the import graph rather than a
promise in a prompt, and each checked by
`tests/test_analyst_architecture.py`:

1. **`app/services/analyst.py` — the only module that contacts a model —
   imports no SQLAlchemy, no `app.db`, no repository, and no canonical
   service, and takes no `Session` on any method.** The route builds the
   packet, closes the session, and then calls it with the packet alone.
   "The model cannot reach the database" is therefore not something the
   instructions ask for; there is nothing there to reach.
2. **No tools are offered at all.** ADR-014 made AI tools read-only; #33
   goes further and provides none. A tool that does not exist cannot be
   called wrongly 60% of the time.
3. **Exactly one generation per request**, asserted by counting the call
   sites and by an AST check that no loop encloses the provider call.

### Old AI code: reused vs rejected

Rejected as a starting point: `app/services/ai.py`'s bounded 4-round
tool loop and `ai_tools.py`'s three DB-backed tools. They remain
committed and reachable at `/api/v1/ai/query` exactly as #12.5 left
them; #33 neither revives nor removes them, and no Analyst file imports
either (guarded).

Reused: the OpenAI SDK error taxonomy and its proven mapping to 503; the
`settings.openai_*` configuration convention, including "unset means the
feature is simply not configured"; ADR-014/016/021 as governing
principles; and `rates_ingestion.py`'s structured-logging shape.

### Trust boundary: a browser names a context, it never supplies one

`AnalystExplainRequest` carries a context type, an optional recorded
result id, a monitor, and a question. Nothing else — `extra="forbid"`,
so an attempt to add `canonical_state` is a 422 rather than a silently
ignored field. Without this, a client could post
`{"canonical_state": "HYPERINFLATION"}` and have the Analyst explain an
economy that does not exist.

Context types are an allow-list expressed as a `Literal`, so
`/monitors/rates/history`-style probing — `EQUITIES`, `CRYPTO`, `SQL` —
is rejected by FastAPI's own validation before any code runs.

### Context packets

`analyst_context_v1`: subject, canonical state, evaluation period,
methodology (with a MacroChipz-written one-line summary rather than
leaving the model to characterise a frozen spec), deterministic metrics,
changes, evidence, provenance, historical context, replay information
and limitations. Four contexts: Inflation, Labor, Rates, Monitor
History.

Two decisions inside it are load-bearing:

- **Values are pre-formatted strings carrying their units**
  (`"158,268,000 jobs"`, `"+25 bp"`, `"2.40%"`). A model handed
  `158268000` cannot tell jobs from thousands — the exact class of
  mistake that produced a 1,000x error inside #32's own deterministic
  code before it was caught.
- **Rates has `canonical_state: null`.** `rates_v1.0` publishes levels
  and derived metrics, not a classification. Giving Rates a state to
  make the packet look uniform would fabricate intelligence the engine
  does not produce.

### Evidence references: the model points, MacroChipz owns

The packet assigns stable ids (`inflation.metric.3m_annualized`,
`rates.level.UST_NOMINAL_10Y`). The model may return ids and nothing
else — no URLs, no source names, no provenance. Every returned id is
checked against the packet that was actually sent; an unknown one is
dropped and counted, and even a valid one is re-resolved so its
label/value come from MacroChipz rather than from the model.

The response schema is deliberately **static**. Injecting the valid ids
as an enum was possible and was rejected: ADR-018's lesson is precisely
that a dynamically shaped schema is a hint, not an enforcement
mechanism. Validation is the enforcement; the schema stays reviewable.

### Failure containment

Unconfigured, timeout, connection failure, auth rejection, rate limit,
5xx, refusal, empty completion, malformed JSON, schema-validation
failure — each raises a typed error mapped to a contained 503 carrying
no provider detail. A malformed answer is deliberately **not retried**:
a second call is a second bill for the same question, and the honest
outcome is that this attempt failed. `max_retries=1` covers only the
SDK's transient conditions, which never re-run a completed generation.

Availability is a normal `200 {"available": false, "reason":
"NOT_CONFIGURED"}` — whether an optional integration is configured is
not an error, and a page should not have to catch an exception to learn
it. Verified live with no key configured: every canonical route still
200s and the UI shows one sentence.

### Observability

One structured log line per request following the repo's existing
convention: request id, context type and version, prompt version, model,
duration, input/output/total tokens, outcome, failure category, evidence
offered/returned/dropped. Absent token counts are recorded as `null`,
never `0`, so an unobserved cost is not mistaken for a free request.

Never logged: the key, the question text, the answer text, the packet,
any provider payload. The question's **length** is recorded instead of
the question.

### A logging quirk worth recording

The operational-metadata tests passed alone and failed in a full run.
Cause: Alembic's `env.py` calls `logging.config.fileConfig`, which
defaults to `disable_existing_loggers=True` and switches off every
already-created `app.*` logger in the process; an operations test
triggers that in-process. Verified this does not affect a running
deployment — the API process never executes Alembic's `env.py`
(`check_schema_compatibility` reads the script directory without it, and
`app.operations.release` is a separate `python -m` process) — so the fix
is a test fixture, not a production change.

### Evaluation

15 cases across Inflation, Labor, Rates, History and Boundary, with ten
universal objective assertions plus case-specific ones. Assertions are
pure functions over (packet, response), so the same code runs in CI
against mocked answers and in the live runner against a real provider.

**Every assertion is tested against both a violating and a compliant
answer.** An assertion only ever exercised on good output is decoration.

`python -m app.operations.analyst_eval` is explicitly invoked and exits
2 when no provider is configured; CI never depends on an external AI
service.

### Evaluation results, stated honestly

**No `OPENAI_API_KEY` is configured on this machine, so the live suite
has not been run and no claim is made about prose quality.**

What was verified, against REAL context packets from the development
database with only the provider simulated: 15 cases produced **exactly
15 provider calls** (one generation per request); all five boundary
cases were caught with the correct specific violations (personalized
advice, future certainty, self-computed figures, asserted causation,
fabricated URL); and an invented evidence id was dropped on every case.
Three history cases correctly failed the backfill-disclosure assertion
because the naive stub omitted a required disclosure — the assertion
doing its job, not a defect.

### Deferred

Persistent chat memory, conversation threads, multi-turn, model routing,
a second provider, forecasting, embeddings/RAG, and any tool calling.
Cost estimation is deferred until real token data exists to base it on.

### Lesson

**Put the boundary in the import graph, not in the prompt.** Every rule
in the instruction set that actually matters is also enforced somewhere
the model cannot influence: it has no tools, no session, no writes, and
its citations are checked against a packet it did not author. The
instructions still earn their place — they shape tone, scope and
honesty — but if the model ignored every word, the worst outcome is a
bad paragraph, never wrong canonical intelligence. That is the only
arrangement under which adding a probabilistic component to a
deterministic system is worth doing.

## Increment #33 (continued) — Live evaluation, diagnosis, and targeted correction

The full record, including the frozen baseline, is
`docs/product/analyst-evaluation-v1.md`. This entry records what the
exercise taught, not the numbers.

### The baseline was worth more than a passing score would have been

First live run of the frozen 15-case suite against `gpt-4o-mini` under
`macrochipz_analyst_v1`: **10 PASS / 5 FAIL**. The instruction was to
run the suite as built rather than a version tuned after seeing the
answers, and that discipline is what made the result useful.

Investigating before changing anything reversed the meaning of most of
it. Of five failures, **three were my own assertions firing on correct
answers**, one was a real defect in my context builder, and one was real
model misbehaviour that the architecture had already contained.

Two of the three false positives are worth naming because they are the
same mistake in different clothes, and it is a mistake I have now made
twice in this project (the first time in #30, over-broad forbidden
substrings): **a pattern that matches the words in a sentence without
regard to what the sentence is doing.** The Analyst wrote two exemplary
refusals —

> "…does not establish whether the Fed **will cut** rates next month."
> "…does not establish that the revision **caused the** state change."

— and both were flagged as the very thing they were declining to do.

### The real defect, and why no offline test caught it

`changes[]` shipped `str(3.1127788466932538)` while every other field in
the packet shipped `"3.11%"`. The model read the real value and rounded
it correctly every time; the answers were accurate. But the packet's own
documentation says values are pre-formatted strings carrying units, and
`changes[]` was the one field that ignored it — which meant the model
was doing arithmetic this architecture exists to keep out of its hands.

Twenty-nine offline tests covered the context builder and none of them
found it, because they all asserted the *shape* of the packet. Not one
asked whether a language model could read it without computing
something. That is the gap the live run closed.

The fix formats every numeric change through `_fmt` — the helper the
rest of the packet already used — with a per-field unit drawn from the
frozen `FIELD_ORDER` vocabularies. And because the ambiguity is gone at
source, **no rounded-number allowance was needed**: the strict numeric
assertion stayed strict, which is the right direction to resolve a
tension like this.

### Prompt v1.1, and why the version moved

The one genuine prompt failure: the model dropped the reconstructed-
input disclosure whenever the historical answer was reassuring ("both
views are MIXED, nothing changed"). A load-bearing limitation became
optional prose exactly when it was easiest to omit and most misleading
to lose.

`macrochipz_analyst_v1.1` makes that disclosure unconditional, in the
model's own terms, including when replay verified and when nothing
changed. The baseline version was **not** renamed — those recorded
results belong to it, and rewriting the label would destroy the only
thing that makes an evaluation record trustworthy.

Strengthening one direction created a risk in the other, so a matching
assertion was added: over-disclosure understates evidence MacroChipz
genuinely has, and `assert_no_fabricated_backfill_claim` now fails an
answer that warns about reconstruction the context never reported.

### Rerun: 10/15 → 13/15, and two honest remainders

Same model, same context version, same 15 questions. Dropped evidence
references went 1 → 0; latency improved slightly; tokens rose ~5%, the
expected price of a longer instruction.

Both remaining failures were classified and **left unfixed**, because a
second round of "fix whatever the eval flagged" is how a suite stops
measuring anything:

- **`history-backfill-meaning` (E, new regression).** The answer is the
  disclosure v1.1 asked for; it failed on `guarantee[sd]?` inside "are
  **not guaranteed** to match". The clause filter recognises refusal
  phrasing but not bare negation. A third instance of the same lesson.
- **`boundary-claim-causation` (F, arguably G).** The causal false
  positive is fixed; what remains is the model not attaching the
  reconstruction caveat to a pure refusal, despite an instruction that
  says to do so "even when the question is about something else
  entirely". Possibly correct behaviour — a caveat appended to an answer
  that establishes nothing is closer to noise than disclosure.

### Lesson

**An evaluation's first job is to be wrong in public.** The baseline's
headline number was misleading in both directions — it overstated the
model's failures and understated mine — and the only way to find that
out was to run the suite exactly as built and then read every answer
before touching a line of code. Had I tuned the assertions first, I
would have shipped a green suite over a context packet that was quietly
asking a language model to do the backend's arithmetic.

## Increment #34 — Production Hardening

Baseline: HEAD `90e7cb1`, clean tree. No new product features. The full
audit, route matrix, threat model and runbook live in
`docs/operations/production-deployment-v1.md`; ADR-033 records the
authorization and production-mode decisions. This entry records what
the exercise taught.

### The audit changed what the work was

I expected to find the usual list — CORS, headers, a rate limit — and
those were there. What I did not expect was that **a frozen deployment
contract already existed** (`render-production-architecture-v1.md`,
§1–§81, from #26F) and that it *named two required implementation tasks
that were never carried out*: the Dockerfile `$PORT` binding (§9) and
`CORS_ALLOWED_ORIGINS` (§8). Both were written down as "#26G's own
implementation task", and #26G never happened.

So the first useful output of the audit was not a new finding. It was
noticing that the most dangerous gap in a long-running project is a
decision that was made, documented, and then quietly not done — it
reads as settled every time anyone greps for it.

### The finding I would have missed without measuring

**Every `logger.info` in this application was being discarded.**

Under uvicorn's default configuration the root logger sits at WARNING
with no handler attached to `app.*`. Verified directly rather than
assumed:

```
app.services.analyst: effective level = WARNING, isEnabledFor(INFO) = False
root: level=WARNING handlers=[]
```

Which means all of #33's Analyst telemetry — model, prompt version,
context version, latency, tokens, outcome, evidence validation, every
field I wrote a test for — produced nothing in a real deployment. The
code was correct. It reached no handler.

That is a specific kind of failure worth naming: instrumentation that
is *tested* is not the same as instrumentation that is *observable*.
Every test asserted the record's fields via `caplog`, which attaches
its own handler and therefore never exercised the production path at
all. `app/core/logging.py` exists to connect the two.

A second, smaller version of the same problem surfaced immediately
after: once logs did emit, the Analyst line carried its own generated
`request_id` while the access line carried the middleware's, so the two
records for one request could not be joined. Correlation you cannot
correlate is decoration.

### Public write endpoints, and disagreeing with a frozen document

Three endpoints — series sync, rates sync, release sync — drive
outbound provider traffic and write canonical economic data, and were
anonymously reachable. Probing returned 422/404, never 401/403, because
no authentication primitive existed anywhere in the application.

`render-production-architecture-v1.md` §55.2/§63 calls these
"already-public, already-safe" and builds the bootstrap procedure
around a public `curl`. Its reasoning — idempotent, cannot corrupt
data (ADR-016) — is correct, and answers a different question than the
one that matters here. Data integrity is not the exposure. Cost and
availability are: a stranger can exhaust a FRED quota, issue unbounded
Treasury fetches, and hold transactions open without corrupting a
single row.

The fix is sized to the actual access model rather than to a checklist.
MacroChipz has no accounts, no personal data, no payments, no sessions,
and exactly one privileged actor. A shared secret in a header is the
smallest thing that solves it; ADR-033 records why accounts, OAuth and
IP allowlisting were each rejected as disproportionate.

It fails **closed** in production. A forgotten variable then means "my
sync returns 503", which I notice, rather than "anyone can drive my
quota", which nobody notices.

### What I deliberately did not build

No Redis, no queue, no Kubernetes, no Terraform, no distributed lock,
no WAF, no identity system. The rate limiter is an in-process
fixed-window counter, correct only for the single-instance deployment
the frozen architecture specifies — and the module says so at the top,
because the failure mode of an undocumented single-instance assumption
is someone scaling to two and quietly losing the control.

Two deliberate non-implementations worth recording:

- **No CSP or HSTS on the API.** This service returns JSON, never HTML;
  a CSP on its responses protects nothing, and TLS terminates at the
  platform edge which issues HSTS itself. The CSP that matters belongs
  to the static host and is specified in the deployment document
  instead — including the honest note that `script-src 'unsafe-inline'`
  is required by the pre-paint theme bootstrap, which is a real
  weakening rather than something to hide.
- **No pagination added to `/series/{id}/transform` or
  `/analysis/compare`**, which are genuinely unpaginated. Every curated
  series is monthly, so the realistic worst case is hundreds of rows.
  Adding pagination to a working public contract is a product change,
  not hardening; it is recorded as a limitation with the condition that
  would make it urgent (ingesting a daily series at scale).

### Two tests that failed for the right reasons

Writing the abuse tests surfaced two things worth keeping:

The first hung. `POST /rates/sync` needs no API key, so a test that
authenticated successfully went on to perform a **real, multi-month
Treasury ingestion**. Stubbing the client fixed it, and the near-miss
is the point: the endpoint being unauthenticated upstream is exactly
why it needed guarding.

The second was the rate limiter leaking across tests — an unrelated
test eventually received a 429 instead of the status it asserted. That
is not a test smell to paper over; it is the same per-process
accumulation the limiter is supposed to have in production, surfacing
correctly. The fix is an autouse reset, and the docstring says why.

### Verification

Backend **2,073 passed, 2 skipped** (+57). Frontend **1,366 passed**,
typecheck/lint/build clean. `npm audit`: 0 vulnerabilities. `pip-audit`:
3 findings in `setuptools`/`wheel`, both build-time tooling absent from
the application's runtime import graph.

Exercised live against a production-mode instance: docs closed (404);
all three operator endpoints 401 anonymously and with a wrong token;
legacy AI route 404; CORS allows the configured origin and refuses a
forged one with no credentials header; four security headers on every
response including errors; rate limit 3/60s produced `200,200,200,
429,429` with `Retry-After: 59`; a 5 MB body rejected `413` before
parsing; malformed JSON, wrong content type and an unsupported context
all `422`; traversal-shaped identifiers `404`. With the database
unreachable: `/health` stayed `200`, `/readiness` reported
`database_unreachable`, reads returned a contained `503`, and Analyst
availability still answered `200`. Zero secret matches across every
server log.

### Lesson

**Hardening is mostly finding out which of your existing guarantees
were never true.** The controls I added are unremarkable — a header
check, a limiter, four response headers, a logging config. What made
the increment worth doing was measuring things I had already written
tests for and finding that two of them — production telemetry, and a
documented deployment fix — existed only on paper. A checklist would
have produced the same middleware and missed both.

## Increment #35 — Audience, Content, Data & Product Feasibility Research (implementation paused again)

Research and product definition only. No production code, no behaviour
change, no deployment, nothing committed, no secret read. Deliverable:
`docs/product/macrochipz-audience-content-data-opportunity-research-v1.md`.

### Why this increment exists

#34 left MacroChipz production-ready. That surfaced the question #28 had
answered only for a *paid investor tool*: what should this become as a
free consumer product? The brief asked explicitly for a disproof attempt
rather than a justification, and the research obliged — most of the
proposed product did not survive.

### The five things that died, each to a measurement

1. **The daily product.** Only **60 of ~252 business days in 2026 (23.8%)
   have any curated release**. Independently, a Wikipedia-pageviews
   measurement against the real BLS/FOMC calendars found **"inflation"
   lifts 1.11× on CPI release day against a 1.08× placebo** — no event
   response at all. The terms that *do* spike (FOMC 6.72×, CPI 2.80×) are
   jargon with tiny baselines and a ~72-hour decay. "Today in the Economy"
   would have manufactured activity that does not exist.

2. **The Pulse as a differentiator.** Chicago Fed's CFNAI has collapsed 85
   indicators into one number since 2001. recessiondashboard.com and
   RecessionPulse ship the free consumer version *today*, with newsletters
   and alerts we do not have. fredecondashboard.com's own pitch is
   essentially our positioning statement, already written by someone else.

3. **Radar as a content engine — killed by arithmetic.** On our own data a
   2σ bar yields ~1 finding per series every two years, while a 600-test
   monthly scan produces **27 false findings a month and 328 a year** under
   a pure null. Worse: the brief's flagship example ("payroll growth
   weakening while unemployment stays stable") **is itself a false
   narrative** — Fed staff put 2026 breakeven employment growth near zero,
   so that pattern is the expected arithmetic of slowing labour supply.
   And CPS cannot resolve a change below 675,000 people while CES resolves
   122,000, so "one moved, the other didn't" is guaranteed with zero
   information content. Radar survives only pre-registered, FDR-corrected,
   TOST-tested and vintage-stamped — which by definition cannot fill a
   publishing calendar.

4. **"Social and search feed the website."** Chartbeat across ~3,750
   publisher sites: YouTube, Instagram, TikTok, LinkedIn, Threads and
   Reddit each **under 0.5%** of referrals. Google organic to 2,576 sites
   **−33% globally, −38% US** YoY. Pew's browsing study (68,879 searches):
   clicks fall from 15% to 8% when an AI Overview appears. And Robinhood
   shut **Sherwood News** on 2026-07-13 — confirmed here from its own
   sitemap (**193 articles in June 2026 → 6 in July → 1 in August → 0**)
   while the Snacks *newsletter* still ships daily.

5. **The backward Time Machine.** `observation_versions` is
   **1,072/1,072 backfilled, 0 genuinely observed, 0 REVISED events ever
   captured**. ALFRED has exactly the right capability (`output_type=4`,
   "Initial Release Only") and we cannot legally use it.

### What survived

**Revision intelligence — and it is the only unambiguous survivor.** Zero
products. The most consumer-ready artifact anywhere is a static SF Fed
chart. Candidate domains (revisions.watch, jobsrevised.com,
truejobsnumber.com and five more) have **no A records**. GitHub: 7 repos
at 0–1 stars. HN: two links. And the demand shock already fired — a
**−911,000** benchmark revision, a fired BLS commissioner, a data
blackout — producing op-eds and no supply.

Two independent research passes, #28 (paid tool) and #35 (free consumer
media), converged on the same feature. That is the strongest signal
either document produced.

Alongside it, the demand side: **66% of prospective homebuyers think the
Fed sets mortgage rates**; 61% think government dictates lender rates;
~half of under-45s think 20% down is required when the first-time median
is 10%. Specific, measured, correctable beliefs attached to decisions
CFPB prices at **over $1,000/year**.

### Two corrections to the record

**BEA's terms are now verified, and they permit commercial use.** #28
recorded them as unverified. The document is at
`apps.bea.gov/api/_pdf/bea_api_tos.pdf` (the path #28 tried 404s); it was
downloaded and parsed locally, so the quotes are byte-exact. The
attribution clause expressly contemplates entities "not-for-profit,
commercial or otherwise" and restricts only *implied endorsement*.

**#28 said FRED must not be the spine. The implementation still uses it
as the spine** — 16 files, all six canonical series. That contradiction
has been live for seven increments. It is now time-sensitive: the Fed
Board's Data Download Program loses "Build Your Package" **the week of
November 9** and redirects users to FRED, the one source we cannot
redistribute from.

### The honest answer to the hardest finding

Stantcheva et al. find economic beliefs "hard to move experimentally,"
and financial literacy hit a **decade low in 2026** despite fifteen years
of free financial content. Why would MacroChipz break that pattern?

The evidence supports exactly one answer, and it is not "better
explanations." People already consult 7.6 sources and still lose money
more often than those who consult 4.0. Only 20% of finfluencer
recommendations carry disclosure. Gen Z's #1 and #2 trust criteria are
"explains things clearly" and "isn't trying to sell me something" — the
second ranked *higher* by non-investors. **The failure is trust, not
clarity. MacroChipz's differentiator is provenance wearing an explainer's
clothes** — which is what thirty-four increments actually built.

### Cost, for the record

**$14.92/month floor, $27.92/month defensible**, both with backups and
PITR. Analyst: **$0.38 per 1,000 requests** measured, dominating the
infra bill only above ~40,000 requests/month. Cost is not a constraint on
any version of this product and should influence no decision.

### Lesson

**A measurement of your own database can kill a product feature faster
than any amount of market research.** Three of the five deaths above —
the daily cadence, Radar's frequency, the backward Time Machine — came
from four SQL queries against tables this project already had. The
external research was necessary to learn that the Pulse is a commodity
and that nobody has built the revisions product; it was not necessary to
learn that we only have data on 23.8% of business days. That was sitting
in `release_occurrences` the whole time.

## Increment #36 — Product Constitution & MacroChipz 2.0 Architecture (specification only)

Specification and architecture only. No production code, no behaviour
change, no deployment, nothing committed, no secret read. Deliverables:
`docs/product/macrochipz-product-constitution-v1.md` (38 sections + build
sequence) and `docs/architecture/macrochipz-2.0-architecture.md` (29
sections).

### Why this increment exists

#35 produced evidence. #36 produces decisions. The point is that
subsequent increments reference a document rather than re-arguing what
MacroChipz is supposed to become. Where the Constitution conflicts with
an older product document it wins; where it conflicts with an ADR, the
ADR wins until explicitly superseded. Product intent does not override an
engineering invariant.

### What the audit changed

Two assumptions I was carrying were wrong, and an agent audit caught
both before they reached the architecture.

**Rates does not come from FRED.** It comes from Treasury, already under
MacroChipz-owned identifiers (`UST_NOMINAL_10Y`, deliberately not
`DGS10`). So FRED supplies three separable things, not one: six monthly
series, series search, and — exclusively — the release calendar. They
carry very different migration difficulty, and Treasury is already the
reference implementation for every adapter the migration needs.

**Most of the new homepage already exists on `/overview`.**
`CurrentStateSection` is the Pulse. The two what-changed previews are
What Changed. `UpcomingReleasesPreview` is What's Next. `SinceLastVisit`
and `HowTheyRelate` survive unchanged. The homepage increment is largely
a re-composition, not a build.

The audit also surfaced a latent provenance lie I would otherwise have
shipped: `PCEPILFE`, `PAYEMS` and friends are FRED-shaped identifiers.
BLS's own id for payrolls is `CES0000000001`. **Migrating the source
without migrating the identifier would leave FRED's naming embedded in a
system that no longer uses FRED.** Identity migrates with the source, or
not at all.

### Three decisions worth recording

**THE LEDE replaces the eight-block homepage.** The proposed hierarchy
put Radar third — a block whose honest state is usually empty — and
revisions fifth, below the two most commoditised features. The rule that
resolved it: **no homepage block whose honest state is usually empty.**
THE LEDE is one slot filled by the highest-significance object, and
because an explainer is a legitimate occupant, it is always full without
ever inventing activity.

**No composite economy score.** The brief floated an "Overall" lens. A
single number across unlike domains needs weighting choices we cannot
defend, and it is the single most-copied feature in the category — the
Chicago Fed has shipped one since 2001. Six honest states beat one
indefensible number.

**I overrode #35 three times, and recorded why in the Constitution so it
stays settled.** (1) #35 rejected "Today in the Economy"; it conflated a
daily *content obligation* (correctly rejected) with a daily *surface*
(fine, if it never pretends) — the quiet day is the design problem and
solving it is the feature. (2) #35 said newsletter-first; it reasoned
from referral economics to product architecture. Referral data says where
users are *acquired*, not where value is *created* — and worlds, evidence
and rabbit holes do not fit in an email. (3) #35 shelved Radar; its
arithmetic refutes broad *scanning*, which is abandoned, but a small
pre-registered registry of motivated detectors survives the same
arithmetic. The findings that constrain what we may honestly *claim*
remain binding and are not subject to override.

### The architectural heart

The **Structured Intelligence Object** is the one thing most likely to be
built wrong, so the constraint is stated as an invariant: **it is a
projection, never a source of truth.** If it cannot be recomputed from
canonical facts plus methodology version plus data vintage, it cannot be
published. Without that rule it becomes a second canonical store that
drifts from the first.

Three of its fields do the real work. `surfacing_rule` +
`threshold_cleared` make "never manufacture activity" a structural
property rather than editorial discipline — an object that cannot name
why it is significant is not surfaced. `knowledge_basis` carries
OBSERVED vs BACKFILLED end to end, taking the weakest basis of its
inputs. And `limitations` is required rather than optional, because
optional fields get omitted and that field is where the honesty lives.

### The one architectural incompatibility

The frontend is a client-only SPA. Crawlers and social scrapers do not
execute JavaScript. **That is not an optimisation gap — it is a
structural incompatibility with the sharing and SEO sections of the
Constitution.** Recommended resolution: serve the HTML shell from
FastAPI with per-route server-rendered `<head>`, keeping the SPA and its
821 tests intact, rather than adding a Node SSR runtime and a second
deployable. Recorded as ADR-039 candidate, not as a decision.

### What survives

Almost everything. All 13 pure domain modules, all five frozen
methodologies, observation versioning, replay, the evidence and
provenance model, the release pipeline, the #33 Analyst, the #34
hardening, the design system — including the machine-enforced
`state-*`/`feedback-*` separation, which turns out to be exactly what the
accessibility requirement needs — and the 34 curated explanations that
are already the seed of "Wait, Seriously?". What changes is the
information architecture, the rendering model, the data sources, and one
new projection layer. Removed: the legacy AI subsystem, unmounted since
#34.

### Lesson

**A specification increment's real output is the arguments it ends.** The
temptation was to write a document that describes a product; what was
actually needed was one that settles questions so they stop being
re-opened — which is why the overrides of #35 are recorded as standing
decisions with reasons, why ten decision rules are stated as gates rather
than aspirations, and why the Day-1 table classifies every feature
including the ones being deferred. Deferral without a written reason is
just an argument waiting to happen again.

## Increment #36A — Final Architecture Decisions & Implementation Sequence (specification only)

Bounded decision pass. No production code, no behaviour change, nothing
committed, no secret read. Deliverables:
`docs/architecture/macrochipz-2.0-implementation-sequence.md` (the
authoritative roadmap), ADR-034, ADR-039, ADR-041, and targeted
corrections to the #36 architecture document.

### The brief contained a factual error, and it mattered

The prompt described "existing React/Next.js frontend infrastructure."
There is no Next.js in this repository. The frontend is **Vite 8.3 +
React 19.2 + `react-router-dom` 7.18.3** in declarative mode. Had I
taken the framing at face value I would have evaluated a migration
*from* Next.js rather than *to* it, and reached a different answer.

Two further repository facts reshaped the rendering decision, and
neither is visible from the "single container image" framing the
project has been using:

- **The production image is Python-only.** No Node, no frontend build,
  no `StaticFiles` mount. CI references "Render's Static Site build."
- **Frontend and backend deploy cross-origin**, which is why #34 needed
  a CORS allowlist and why `VITE_API_BASE_URL` exists.

So the real shape is a backend container plus a separate static site.
**Any option requiring a runtime Node server adds a third deployable
that does not exist today** — the largest hidden cost in the comparison.

### Decision 1 — rendering: I overturned my own #36 recommendation

#36 proposed serving the document head from FastAPI. #36A rejects it.
Route and metadata definitions would live in Python *and* React with
nothing keeping them in agreement — a shared secret across two
languages, drifting silently, on a product whose entire differentiator
is that its claims are checkable. The brief was right that a
server-rendered `<head>` never justified that.

**Decided: React Router framework mode, v7 line, `ssr: false` +
`prerender`** (ADR-039). Three facts settled it. React Router's current
major is **8**, and `react-router-dom` has no 8.x at all — but
`@react-router/dev@7.18.4` supports Vite 8, so framework mode is
available **without** the 21-file import codemod. The vendor publishes
a migration guide from exactly our starting point. And its official
template pins our exact stack, down to `@tailwindcss/vite`.

`ssr: false` + `prerender` **preserves the static-site deployment
entirely** — no Node in production, no third deployable — and
pre-rendered and server-rendered paths are mixable, so `ssr: true`
later needs no framework migration. **That reversibility is the real
argument: we are choosing the cheapest point on a path we can move
along, not committing to an endpoint.**

A finding that changed sequencing: **React 19 hoists `<title>` and
`<meta>` natively.** Per-route dynamic metadata needs no architectural
change at all; only metadata *in the initial byte stream* needs
pre-rendering. Two separable steps, not one big one.

Next.js was rejected as disproportionate: its own migration guide
deletes `vite.config.ts` (which holds the Tailwind plugin, the dev
proxy *and* the entire Vitest config), Vitest cannot test async Server
Components by Next's own documentation, and ISR — its main advantage —
needs a Node server to solve a problem that ~60 release days a year may
not pose.

### Decision 2 — ordering: four increments came off the critical path

No migration blocks the Structured Intelligence Layer, the homepage, or
anything else. Once concepts are separated from provider identity, FRED
is just one binding behind a stable vocabulary.

I also checked the one deadline I had been carrying: #35 flagged the
Fed's Data Download Program retiring the week of 9 November. **That is
H.15, and this repository has no Fed Board client** — rates come from
Treasury directly. The concern does not apply. FRED's licensing blocks
*public launch*, not development, so the migration track gates #47 and
nothing before it.

**Product becomes visible at #40 and recognisable at #42, three
increments earlier than #36's plan.**

### Decision 3 — the defect underneath the naming problem

#36 found that `PAYEMS` and friends are FRED-shaped identifiers. #36A
found the indirection already exists — the domain references
`PRIMARY_SERIES_ID`, not `"PCEPILFE"` — so only the *values* are
provider-shaped, and only two literals leak past it
(`labor_release_processing.py:47-48`, which the code's own comment
admits are duplicated "by convention").

The real defect is elsewhere. `Observation` carries **exactly two
fields, `date` and `value`** — no identity. So evidence is stamped from
a module constant. **Swap FRED for BLS and the observations flow
through unchanged, while evidence still says `PAYEMS`.** Evidence would
assert a provenance that no longer reflects where the number came from.
On a product whose differentiator is provenance, that is not a naming
inconvenience; it is a correctness failure waiting for a migration to
trigger it.

ADR-034: concepts code-defined (methodologies depend on them, so they
must be type-checked and un-changeable without a deploy), bindings
per-adapter in code as Rates already does, and **no new table** — the
database records concept *membership* via one additive column, while
`observation_provenance` already records which binding produced each
value. Dual bindings during cutover are both the verification
mechanism and the rollback mechanism.

### Decision 4 — #37 got smaller

Ten events, each with the product question it answers written down; an
event without one does not ship. Fire-and-forget, no-op by default, no
cookies, no identity graph. **Return measurement needed nothing new** —
Since Last Visit already keeps a client-side-only checkpoint, so a
coarse `days_since_last_visit_bucket` falls out of existing state.

I also moved OG tags, sitemap and robots *out* of #37 into the
rendering increment where they architecturally belong, and email
capture into Follow. #37 is analytics only.

### Charting: the default answer failed the hard requirement

Measured empirically against React 19.2.8 with no DOM rather than read
from documentation: **Recharts renders a 127-byte empty `<div>` with
zero `<svg>` elements.** Not a container problem — identical with full
jsdom globals. It is a tracked regression from 2.x, open and unfixed
fifteen months after 3.0. uPlot, Chart.js, Observable Plot, visx's
`XYChart` and Nivo's `ResponsiveLine` fail the same test.

ADR-041: hand-authored SVG over d3 math primitives (+15.7 KB measured
through our own Vite build, against +126 KB for Recharts), keeping the
`<svg>` element — and therefore the ARIA and the `--mc-*` tokens —
ours. visx *primitives* pass SSR and are the designated escape hatch,
triggered by needing touch tooltips on more than one chart. ECharts is
reserved for server-side rendering only, guarded out of the client
bundle.

### Two corrections to our own record

The charting evaluation read `YieldCurveChart.tsx` and found this
project has been repeating two things that are not true.

**The SVG is not `aria-hidden`.** Its own doc comment says so, and #35
and #36 both repeated it, but the code uses `role="img"` +
`aria-label`, *plus* an `sr-only` `<figcaption>`, *plus* the table —
redundant rather than clean. And **`preserveAspectRatio="none"` squashes
the chart roughly 37% horizontally at 390px**, on a product that calls
mobile first-class. Both are now #41 acceptance criteria.

Separately: #35 and #36 said there is no meta description. There is one
— static and site-wide. The gap is *per-route* metadata.

### Lesson

**Three of this increment's four decisions turned on a fact about the
repository that no amount of reasoning would have produced.** The
rendering decision turned on the Dockerfile being Python-only. The
identity decision turned on `Observation` having two fields. The
charting decision turned on rendering Recharts server-side and counting
the bytes. In each case the documentation-level answer and the
measured answer differed, and in two of them I had already written the
documentation-level answer into #36. Verify the thing itself — including
the parts of your own record you are most confident about.

## Increment #37 — Privacy-Conscious Measurement Foundation

The first implementation increment of MacroChipz 2.0, and deliberately
the smallest one in the roadmap. Frontend only; **no backend code was
changed, so the backend suite was not run** — nothing in this increment
can reach it. Nothing committed, nothing pushed, no secret read.

New: `frontend/src/analytics/` (vocabulary, `track`, provider boundary,
route hook, public surface), three test files, one architectural guard,
and `docs/architecture/product-measurement.md`.

### What this increment is

One typed event vocabulary, one `track()` function, one provider
boundary. There is no identity graph, no session replay, no
fingerprinting, no funnels, no experimentation framework. Those are not
deferred; they are excluded.

**Analytics is disabled by default and that is the supported production
state.** The whole point was to build the abstraction without inventing
a dependency.

### The provider decision was not mine to make

#36A left provider selection open, and #37 confirmed why. **Cloudflare
Web Analytics — free and cookieless — cannot carry custom events**, so
it cannot answer the one question this increment exists for. Everything
that can (Plausible $9/mo, Fathom $15/mo, self-hosted Umami) costs
either money or operational surface.

That is a trade between a small recurring cost and a small recurring
burden. Both defensible, neither mine to pick. So the abstraction
ships, the call sites are wired, and nothing is sent. Adding a provider
later is one file plus one environment variable — no component changes.

### #36A was wrong about return measurement, and I dropped it

#36A proposed deriving `days_since_last_visit_bucket` from the existing
Since Last Visit checkpoint, reasoning that return measurement needed no
new storage. Reading the module killed it.

`sinceLastVisitCheckpoint` stores a **server-issued data watermark**,
and its own guard test proves the module never reads the browser clock.
Time since that watermark measures **how stale the data a reader last
saw was — not how long ago they visited.** Shipping it as a visit
interval would have been exactly the fake precision the Constitution
forbids, and it would have looked right in a dashboard forever.

So return behaviour is not measured in #37. The two honest options are
recorded, along with the precision note that a local checkpoint
establishes behaviour *in one browser*, never a returning *person*.

### Two judgement calls worth recording

**`empty_state_viewed` is reserved rather than emitted**, and not
because the feature is missing. Empty states exist today — but they are
*data-availability artifacts* ("no rates data yet"), while the question
the event exists to answer is about the **designed** honest-absence
state that arrives with What Changed in #42. Emitting it now would
measure a different thing and quietly poison the baseline.

**`world_opened` overlaps `page_viewed`** and I kept it anyway. It
survives the planned `/labor` → `/jobs` rename and the 2.0 designs
where a world opens without a route change, and its property is
self-describing where a route template requires knowing which routes are
worlds. It is the one place #37 collects more than the strict minimum,
so it is written down rather than left to be found.

### Where the events live

Semantic actions, never DOM coordinates. `usePageViewed()` sits once in
`AppShell` so the pages stay unaware of analytics and a future route is
instrumented by existing. `ExplanationTrigger` carries its own event
because it means exactly one thing at all sixteen call sites.

`Disclosure` was the interesting one. It gained an optional `onOpen`
and is deliberately kept **ignorant of analytics**: it renders evidence,
methodology, data-basis notes and change lists alike, so only the call
site knows which product event an instance represents. Keeping the
semantics at the call site is what lets one primitive serve several
events without inventing a false one.

### Two layers, on purpose

The type system makes a wrong property a compile error. The runtime
allowlist drops any undeclared key and any non-primitive value. The
duplication is deliberate — types vanish at runtime, and the allowlist
is what stands if a type is ever widened. Tested with a payload
carrying a question and an email address: both dropped.

`track()` never throws, returns `void` so nothing can await it, creates
no promises so nothing can reject unobserved, and **does not log on
failure** — a console error on every page view in a browser with an ad
blocker would be noise reporting a state we consider normal.

### Verification

Frontend **1,406 passed** (1,366 before, +40). Typecheck clean, oxlint
clean, production build clean in 267ms. Backend untouched and not run.

Checked the built bundle rather than trusting the guard: `MODE:
"production"` and `PROD:!0` are inlined, so the debug provider's console
call is unreachable in production. Also grepped for vendor SDK names —
the only hit was "segment" inside a react-router error string about
malformed URL segments.

### The mistake

I broke the build twice with the same error: an `Edit` whose replacement
dropped the closing `>` of a JSX opening tag, in `Disclosure` and
`ExplanationTrigger`. Twelve test files failed to parse. Both were
mechanical and obvious once read, and both came from writing a
replacement string that ended at the last attribute I cared about
instead of at the end of the tag I was replacing.

### Lesson

**The smallest increment in the roadmap was the one that caught a
planning error.** #36A's return-measurement design survived two
documents and a review, and died in ten minutes of reading the module
it depended on. The same shape as #36A's own lesson, one increment
later: the plan described what the checkpoint was *for*, and the code
said what it actually *stores*. Those differed, and only one of them was
true.

## Increment #38 — Source-Neutral Economic Concept Identity

Implements ADR-034. Establishes the identity boundary the source
migrations (#M1–#M4) need, without performing any of them. Nothing
committed, nothing pushed, no secret read or printed.

New: `app/concepts/` (registry + bindings), `app/services/series_identity.py`,
`app/models/series.SeriesIdentity`, one additive migration,
`tests/test_concept_identity_boundary.py`, `tests/identities.py`, and
`docs/architecture/economic-concept-identity.md`.

### The defect, restated from the code

#36A found that `PAYEMS` — a FRED identifier — was MacroChipz's
canonical identity. The worse half is that `Observation` carries only a
date and a value, so a methodology stamped its evidence from a
module-level constant:

    LaborObservationEvidence(series_id=PAYEMS_SERIES_ID, ...)

**Change the provider and the observations flow through unchanged, while
the evidence goes on saying `PAYEMS`.** On a product whose entire
differentiator is that its claims are checkable, that is a correctness
failure waiting for a migration to trigger it.

### What was built

Twelve concepts, twelve bindings, matching the twelve persisted series
exactly. Concepts are code-defined (frozen methodologies depend on
them, so they must be type-checked and versioned with the code);
bindings carry the provider, the provider's own identifier, the native
unit and the conversion factor, plus an `equivalence_basis` that must
cite the methodology already using that series for that role. "The
names match" is not a justification.

`SeriesIdentity` — concept, provider, provider series id — now travels
with the data, resolved from the persisted row by
`SeriesRepository.get_identity`. Evidence carries all three.

### Four things the implementation changed about the plan

**1. The role constants kept their values.** ADR-034 said they would
change. They did not, and changing them would have broken the invariant
the ADR itself set: they flow into evidence's `series_id`, which
Invariant C requires to be *the provider's* identifier. They are now
*derived* from the active binding instead of hardcoded, and new
`*_CONCEPT_ID` constants sit alongside.

**2. Identity parameters are keyword-only.** Every existing positional
call to a frozen methodology keeps working, and a positional mix-up
between the employment and unemployment identities — which would
attribute one survey's evidence to the other — is now impossible to
write.

**3. Bindings needed two provider-facing identifiers.** Treasury stores
MacroChipz's own id (`UST_NOMINAL_10Y`) in `economic_series.series_id`
while FRED stores the provider's (`PAYEMS`), so `provider_series_id`
and `storage_series_id` are separate fields. That asymmetry is a
pre-existing ambiguity in that column; #38 names and contains it rather
than migrating six Treasury rows for naming symmetry.

**4. The unit conversion moved to the binding.**
`PAYEMS_JOBS_PER_NATIVE_UNIT = 1000` was documented as converting from
*"FRED's native Thousands of Persons"* — so it was always a property of
the provider. Whether BLS publishes CES in the same units is now
explicitly a verification task for #M2, not an assumption inherited
from FRED.

### A production bug I introduced, and caught

Requiring `concept_id` broke `SeriesRepository._upsert_series`, which
never set it — so a canonical series created by a fresh sync would have
had none, and the monitors would have raised instead of returning
`INSUFFICIENT_DATA`. The fix has two parts, and the second is the
better one: `_upsert_series` now sets `concept_id` by the same
deterministic rule the backfill uses, and `get_identity` treats the
column as a **denormalization of that rule** rather than the source of
truth — falling back to the binding for the concept while still reading
**provider and series id from the row**, which is what Invariants C and
D actually require. That single change fixed 149 test failures, because
they were all reporting the same real defect.

### Migration

One additive nullable column plus an index. Nullable **permanently**:
`POST /series/{id}/sync` accepts arbitrary FRED series, and forcing NOT
NULL would mean inventing a concept for each one — the fabricated
identity ADR-034 exists to prevent. Canonical paths require a concept
and fail loudly; generic endpoints do not care.

Verified against the real database after applying: 12 of 12 series
mapped, **0 unmapped**, 1,072 observations unchanged (checksum
`9414455.108000`), 175 distinct observation dates unchanged, 714
provenance rows unchanged, 1,072 observation versions unchanged, 133
recorded monitor results unchanged.

### The guard earned its keep immediately

`test_no_domain_module_contains_a_provider_series_literal` failed on
its first run — because `app/domain/labor_release_processing.py` still
carried `PAYEMS_SERIES_ID = "PAYEMS"`, with its own comment conceding
it was "kept in sync with app.models.labor **by convention**." I had
written the guard for exactly that line in #36A and then forgotten to
fix it. The guard remembered.

### Lesson

**A refactor is only as honest as the thing it makes impossible.**
Renaming constants would have satisfied the letter of ADR-034 and left
the defect entirely intact, because the defect was never *which*
constant was used — it was that identity came from a constant at all
while the data carried none. The test that matters is not "do the names
look source-neutral", it is "can evidence still name a provider that
did not supply the number", and that one is answerable only by making
identity travel with the data.

## Increment #39 — Structured Intelligence Layer

The bridge between the canonical engine and the consumer surfaces #40–#46
will build. Nothing committed, nothing pushed, no secret read.

New: `app/models/intelligence.py`, `app/services/intelligence/`
(builder, identity, service), `app/api/intelligence.py`, three test
files, and `docs/architecture/structured-intelligence.md`.

### The taxonomy came from the database, not the plan

The brief proposed a `STATE_CHANGE` type. Before designing anything I
counted what the engine has actually recorded, and found two things
that changed the answer.

**There are zero `STATE_CHANGED` rows.** Every one of the 1,532
persisted analysis updates is `CONFIRMATION_CHANGED` (44) or
`AVAILABILITY_RESTORED` (1,488). A `STATE_CHANGE` variant would have
been a well-designed model with no data behind it. So the variant is
`ANALYSIS_CHANGE`, carrying `event_type` as a typed field — which the
Constitution needs anyway, since it requires state changes and metric
drifts to be visually distinct.

**And 97% of those rows record one bootstrap event** in which
everything became computable at once. Surfacing that as economic
intelligence would be exactly the manufactured activity the
Constitution forbids. Hence `change_class`: `ECONOMIC` versus
`COVERAGE`, a deterministic documented classification rather than a
judgement, so a surface can filter without presentation guessing.

Final taxonomy, all four flowing with real data: `RELEASE_PROCESSED`
(3), `OBSERVATION_CHANGE` (358), `ANALYSIS_CHANGE` (1,532),
`RATES_MOVEMENT` (6).

### What I refused to build

**No significance score.** THE LEDE will need to pick one object, and
the temptation was to ship a ranking primitive now. But no frozen
methodology publishes a notability threshold — `rates_v1.0` explicitly
defines none — so any rule would have been invented here rather than
cited, and it would have been invented inside a *canonical* object
where it would look like a fact. Ordering is by time with the stable id
as a total tiebreak. The interpretable primitives a surface can filter
on already exist as named facts. Significance joins the contract when a
methodology publishes a threshold to cite; BLS's own confidence
intervals are the obvious first candidate.

`RATES_MOVEMENT` carries that refusal in its own `limitations`: it
reports the movement and its historical position, and says plainly that
it is not claiming the movement matters.

### Persistence: generate on read, no new table

Evaluated against every criterion in the brief. Every input is already
persisted; ids derive from semantic facts so permanent URLs resolve
without a row; `observation_versions` and `recorded_monitor_results`
mean reconstruction loses nothing about what MacroChipz knew.

The decisive argument is the last one: **a stored projection can
disagree with the facts it claims. A generated one cannot.** The
trigger to revisit is written down — if an object ever needs to carry
something not derivable from canonical data, such as a human
correction, persistence becomes necessary and gets introduced then.

### The identity guard fired in development

Ids are semantic, not database rows: `observation:{concept}:{date}:
{detected_at}`. The separator is a colon, and `_segment` rejects any
dimension containing one rather than silently minting a colliding id.

It rejected the first real timestamp I passed it, because ISO-8601
contains colons. The right fix was the encoding, not the guard —
timestamps are now compact (`20260919T184627419986Z`). A guard that
fires the first time you use it is a guard worth having.

Two identity properties worth recording: a **methodology change mints a
new id** (a conclusion under a different methodology is a different
conclusion), and a **provider migration does not** (ids key on #38's
concept identity, so an object about core PCE survives its source
moving from FRED to BEA).

### Avoiding the god object

Four variants with small typed payloads — and the test asserts it,
capping each payload at 12 fields and 2 optional ones. A consumer
switches on `type` and gets a payload where every field means
something, rather than one model with thirty nullable columns where
most mean nothing for any given object.

### Verification

Backend **2,128 passed, 2 skipped** (2,096 before, +32). Frontend
untouched, so its suite was not re-run. Guards assert no model import,
no provider client, no upward domain dependency, no Analyst dependency,
and that the API route constructs no intelligence object itself.

Verified by probe rather than assumption: list and detail both 200,
`limit=101` and `limit=0` both 422, unknown and malformed ids both 404,
`world=atlantis` 422, and two identical requests return byte-identical
payloads.

### Lesson

**Counting the rows first changed the design twice in one increment.**
The plan's `STATE_CHANGE` type had no data; the analysis-change table
was 97% bootstrap noise. Both were ten minutes of SQL to discover and
would have been months to unlearn — the first as a model nothing ever
populated, the second as a homepage feed full of "MacroChipz can now
compute this" presented as economic news. The engine's own record of
what it has actually done is a better specification than any document
about what it is for.

## Increment #40 — Rendering Foundation & First Permanent Intelligence Object

MacroChipz now has a URL for one economic fact:

```
/intelligence/rates%3AUST_NOMINAL_10Y%3A2026-09-18
```

It returns real HTML with a real `<title>`, a real description, a real
Open Graph card, and the whole page already in the body. Before this
increment every MacroChipz URL returned an empty root div, which is
fine for an application and fatal for a publication.

### Choosing the first object

The spec forbade choosing whichever object was easiest to render, so
the choice came from the database rather than from preference.
`RATES_MOVEMENT` was the only #39 type with genuine per-observation
Treasury provenance, a real frozen methodology, real evidence values,
and deterministic historical context. `RELEASE_PROCESSED` would have
been easier and would have shipped a page whose "evidence" was an
operational log entry. The first permanent URL sets the standard for
every one after it, so it had to be the one that could actually be
verified.

### The framework migration was smaller than the ADR predicted

ADR-039 anticipated migrating `<Routes>` into `routes.ts`
"incrementally". In practice the entire existing `<App/>` tree was
preserved wholesale under a `*?` splat route, so **no pre-existing
route was migrated at all**. Only `/intelligence/:id` is a real
framework route. The blast radius was the application shell —
`index.html` and `main.tsx` deleted, `root.tsx` and `entry.client.tsx`
created — and not the routes. All 1,470 frontend tests pass, including
every test written before this increment.

### Two spikes answered by being wrong first

`reactRouter()` and Vitest cannot share one Vite config. Fifteen of
fifty-four test files failed with "React Router Vite plugin can't
detect preamble" before the configs were split. The same failure
resolved the second spike at no extra cost: `@vitejs/plugin-react` must
*not* sit beside `reactRouter()`, which supplies its own React
transform — it belongs in the Vitest config, where `reactRouter()` is
absent. The vendor's upgrade guide and its own template had appeared to
contradict each other; they were describing different configs.

### What the page is not allowed to do

Three prohibitions are enforced by a test rather than by review, in
`src/test/no-intelligence-derivation.test.ts`: the rendering layer may
not recompute a change magnitude, convert to basis points, compute a
percentile, classify a world, or associate evidence. It formats; #39
computes. A page that can derive a number is a page that can disagree
with the engine.

The guard needed three corrections, and each one is the same mistake:
a pattern that matched the *shape* of a defect rather than the defect.
`*100` caught legitimate percentile formatting. The OG-screenshot check
matched its own docstring. And `published_at\s*[=:]` matched
`published_at === null` — a comparison, not an assignment. Reading the
field is the correct behaviour; inventing a value for it is the defect,
and the guard now says so in a comment so the next person does not
"fix" it in the wrong direction.

That last one matters beyond the regex. `published_at` is `null` for a
Treasury observation because Treasury does not publish an exact time.
The page therefore says *"Not known — the source does not publish an
exact time"*. Substituting `recorded_at` would have been one line and
would have been a lie about provenance on a permanent URL.

### Omission over guessing

Two places chose to emit nothing rather than emit something plausible.
When `VITE_SITE_URL` is unset, `canonical`, `og:url` and `og:image` are
omitted entirely — a guessed canonical tells a crawler the real page
lives somewhere it does not, which is worse than no canonical. When an
object lacks the facts for a truthful OG card, the card is skipped and
logged rather than filled in.

The same instinct runs the other way for build failures. An unset
`VITE_API_BASE_URL` prerenders nothing and succeeds, because
frontend-only CI must not require a database. But an API that *answers
badly* throws and fails the build, because the alternative is shipping
permanent URLs with nothing behind them. `verify-build-output.mjs` then
re-reads the actual generated HTML and fails the build if the metadata
is missing, the body is an empty shell, or anything secret-shaped
appears. Unit tests assert what the code intends; that script asserts
what the build actually produced.

### The cost, measured rather than assumed

ADR-039 required measuring build time before committing to
rebuild-per-release. Fixed cost is ~8.3 s. Marginal cost is **0.31 s per
object** — 0.29 s to prerender, 0.017 s for the Satori→sharp card. That
extrapolates to ~15 s at the current cap of 25 objects, ~84 s at 250,
and ~161 s at 500: comfortable to roughly 250, unattractive past 500.
The honest caveat is that this is linear extrapolation from n ≤ 6 and
should be re-measured at n ≈ 100. The escape hatch was already decided
and is still cheap: flip `ssr: true` in the same framework.

### One event went live

`share_initiated` is the first of #37's reserved events to be
activated, for the reason #37 required: the affordance now exists. It
records `object_type` and nothing else — not the URL, not the title,
not the clipboard, not which app the reader chose. `normalizeRoute()`
collapses `/intelligence/{anything}` to the template for the same
reason: the id would turn `page_viewed` into a reading history. And
because `track()` never throws and is called before the share attempt,
sharing keeps working when analytics throws and when it is disabled
entirely — both asserted by test.

### Still true, and worth stating

One route is crawlable. The rest of the site is still an empty shell to
a crawler that does not run JavaScript. Unfurl behaviour has never been
checked against a real platform, because that needs a public
deployment. And a new object does not appear at its permanent URL until
the site is rebuilt. Each is written down in
`docs/architecture/rendering-and-permanent-objects.md` §13 rather than
left to be discovered.

## Increment #40A — Local development regression

#40 was reported complete on the strength of 1,474 passing tests, a
clean typecheck, a clean lint, and a green production build that
prerendered six pages and verified its own output.

`npm run dev` could not serve a single request.

Under `ssr: false`, React Router allows a route to export `loader` only
if that route is matched by a prerender path **in the same
invocation**. Local development sets no `VITE_API_BASE_URL`, so nothing
is prerendered, so the `loader` on `routes/intelligenceObject` was
invalid, so the dev server threw and exited.

What makes this worth writing down is the shape of the failure rather
than the fix. The dev server printed its banner first. It reached

```
➜  Local:   http://localhost:5173/
```

and only died on the first request. Anyone glancing at the terminal
would have concluded it was running. The #40A instruction to "wait long
enough to ensure the prerender validation does not terminate the
process" was exactly right, and it is the reason the reproduction took
one attempt instead of several.

### Three blind spots, not one bug

Every automated check ran with an API available, which is the one
configuration where the defect is invisible — prerendering the route
makes `loader` legal. Unit tests could never have caught it, because
the validation is React Router's own and runs only when the dev server
or build assembles the route manifest. And #40 was *inspected* but
never *run*: its documentation asserted that local development worked
without a database, which was an assumption written in the voice of a
verified fact.

That last one is the real defect. The build was verified honestly and
thoroughly; a sentence about something adjacent was not verified at
all, and nothing in the process distinguished the two.

### The obvious fix was wrong

Deleting `loader` and keeping `clientLoader` makes `npm run dev` work
immediately. It also makes the release build emit an empty shell — no
`<h1>`, no title, no Open Graph tags — because under `ssr: false` a
route with only `clientLoader` is not rendered during prerendering at
all. That would have traded a broken dev server for a silently broken
product, and it was caught by `verify-build-output.mjs`, the script
written in #40 to check what the build actually produced rather than
what the code intended. That script justified itself within a day.

Both exports are genuinely required — in different configurations. So
the *module* varies: two route modules, the prerendered one a thin
re-export of the other plus `loader`, chosen in `src/routes.ts` from a
single memoized decision that `react-router.config.ts` also reads. One
answer, so the two cannot disagree. The condition is deliberately "will
this build prerender an intelligence path", not "is the API URL set" —
a reachable API holding no `RATES_MOVEMENT` objects prerenders nothing,
and there a `loader` would be just as invalid.

### Regression coverage, in two layers

A fast unit test asserts the client-side variant exports no `loader`,
`action` or `headers`, and that the two variants differ by exactly one
export. A second guard, `npm run verify:spa-mode`, builds with no API
and asserts React Router accepts it. The second exists because the
first is only *our restatement* of the framework's rule; if React
Router changes the rule, only the build notices. Both were checked by
reintroducing the original defect and confirming each one fails.

### Warnings, deliberately not silenced

The `envFile` deprecation is emitted by Vite 8.3.0 because
`@react-router/dev@7.18.4` sets `envFile: false` internally. It is not
our configuration and patching a dependency to quiet it would be worse
than the warning. Of the five React Router v8 future flags, none were
adopted: two could plausibly affect this increment — route-module
splitting, now that one route has two variants, and trailing-slash-aware
data requests, which touch the `.data` files prerendering writes — and
both deserve their own verification rather than being switched on to
clean up console output. Enabling `v8_viteEnvironmentApi` was measured
and does not remove the `envFile` warning; the two are unrelated.

## Increment #40B — Consumer presentation pass

#40 built a permanent, crawlable, shareable page for one economic
fact. #40B asked whether a person without a finance background could
read it. The honest answer was no: it opened with

> 10-Year Treasury Par Yield (Nominal) is 5.01%

and expressed every movement in basis points. Both are correct. Both
assume the reader already works in fixed income.

The page now opens with the name, the number, and the move, in that
order — "10-year Treasury yield", "5.01%", "↑ Up 0.05 percentage
points over the last 5 trading days" — and Treasury's own wording sits
quietly beneath it. Nothing was removed; the precise version moved to
where precision is what the reader came for.

### The bug that was hiding in the copy

#40's page said:

> Against its own history (113 observations), this level sits at the
> 57th percentile.

That sentence names the wrong quantity. `RatesService._historical_context`
ranks the current **5-session change** against every earlier 5-session
change; `_CONTEXT_WINDOW` is `"5_SESSIONS"`. Both percentiles describe
the **move**. Neither describes the level.

It was not caught in #40 because nothing about it looked wrong. The
number was real, the count was real, the sentence was fluent, and the
architectural guard was watching for recalculation rather than for
mislabelling. A guard that asks "did the frontend compute this?" cannot
ask "did the frontend understand what it was given?" — and the second
question is the one that decides whether a reader is misled.

The fix was to read the backend rather than the field name. The page
now says what is compared, distinguishes the signed rank from the
magnitude rank, states the size of the record in the same breath as the
comparison, and says outright that 113 moves is a few months of trading
and not a statement about the long run.

### Refusing the label

The obvious product move is to answer "Is this unusual?" with yes or
no. The section asks that question and then declines to answer it:

> MacroChipz does not label this move unusual or ordinary. Its rates
> methodology defines no threshold for that, so saying otherwise here
> would be inventing one.

A threshold invented in a React component is a significance methodology
with no version, no test vectors and no methodology document — and it
would be the one users actually see. Naming the refusal is more useful
than a confident label nobody could check.

### Units are presentation; canon is canon

Basis points remain the stored, methodological unit. The page divides
by one hundred to show percentage points, which is the same class of
act as rendering `5.01` as `5.01%`, and shows the basis-point figure
beside every window anyway. The distinction worth keeping straight:
changing what a number IS would be a methodology change, and changing
how it is WRITTEN is not.

### "Why this matters", and the sentence it refuses to write

Curated static prose keyed by exact concept id, reusing the same
`Explanation` model the rest of the product uses. The temptation in an
explainer about the 10-year is to say it sets mortgage rates. It does
not. The copy says it is "a reference point, not a mechanism", that the
10-year "does not set any of those rates", and that the relationship is
loose and changes over time — and the architectural guard now fails the
build on the words "determines", "controls" and "drives mortgage"
appearing in that content.

A concept with no curated entry renders no section at all. Silence is
the right failure mode for an explainer; a generic paragraph pretending
to be specific is not.

### Verified in a browser, not only in jsdom

The increment asked for real visual verification, and jsdom cannot
provide it. Chrome was already installed, so the page was driven
through the DevTools protocol at 1440×900 and at a true 390×900
viewport: `scrollWidth` equals the viewport at both, and no element
overflows except the evidence table inside its own scroll container,
which is intended.

That measurement also corrected a false alarm. Screenshots taken with
`--window-size=390` looked badly clipped, on the new page and on the
untouched Rates page alike. The layout was fine; headless Chrome had
laid the page out at 500px and captured 390 of it. Forcing the viewport
through `Emulation.setDeviceMetricsOverride` showed a clean 390px
layout. Two minutes of measurement prevented a fix to a bug that did
not exist.

## Increment #40C — Visual evidence

The permanent page could tell you the 10-year was at 5.01% and had
risen 0.05 percentage points over five trading days. It could not show
you that it had climbed from about 4.30 in late June. You can read six
numbers and still not know the shape.

#40C added the shape. The first question was whether #39 already
carried it.

### Tracing rather than assuming

It did not, and the trace was short. `RatesMovementPayload` carries a
title, a latest value, four change windows and two percentile ranks.
`evidence` carries one observation — the latest. The absolute ceiling
was five non-contiguous points, four of them only as a `from_value`
attached to a change.

Further up, `RateLevel` — what `RatesService` hands the intelligence
builder — has no series either. So the builder could not have assembled
one even if it wanted to.

That mattered because the tempting shortcut was right there: the
frontend already knows how to call an API, and there is an observations
endpoint. Taking it would have produced a chart in an afternoon and a
second account of reality forever. A chart built from a separate query
can disagree with the object it sits under, and the chart is the half
users believe, because it is the half they can see.

So the contract was extended instead: `TimeSeriesVisualEvidence`,
optional, carrying a concept id, a canonical unit, a requested and an
available session count, and a list of dated values. No colours, no
dimensions, no axis configuration, no component options — the backend
supplies economic evidence and the frontend decides how to draw it. A
test asserts that words like `color`, `width`, `ticks` and `chart`
cannot appear as keys.

The contract version was deliberately **not** bumped. It is documented
as bumped on a breaking change, and an optional field is not one; a
consumer written before #40C parses every object unchanged. Bumping
would have announced a break that did not happen.

### The window, and a subtlety worth writing down

63 published sessions, because that is already a `rates_v1.0`
comparison window. It is never called "three months": it is a session
count, and the calendar span varies.

Then a real subtlety surfaced in the data. The chart's first point is
2026-06-22; the 63-session change's `from_date` is 2026-06-18. Both are
correct. A 63-session *change* compares the latest observation with the
one 63 sessions before it, which spans 64 observations; the latest 63
observations span 62 steps. Anyone eyeballing the chart's endpoints
against the "+0.55 over the last 63 trading days" figure would get
+0.50 and conclude something was broken.

It is not an off-by-one to be corrected — the two answer different
questions — so it was documented in the contract itself, and the
caption states the series' own real date range rather than implying it
matches a change window.

### Drawing without lying

X is positioned by date, not by array index. A publication gap
therefore stays a gap, instead of being silently closed up by even
spacing. That is what "never fabricate missing trading days" means
once you are writing the path string.

The y-axis is not zero-based, which is worth defending rather than
assuming: a yield chart forced to a zero baseline flattens every real
movement into a line near the top, and that is its own dishonesty. The
axis labels always state actual values, so nothing about the scale is
hidden.

The line is a single neutral stroke. Semantic `state-*` and
`feedback-*` colours mean something specific in this design system, and
a yield moving up is neither good nor bad. A test fails if a red, green
or semantic token appears inside the chart markup.

### ADR-041's two defects became acceptance criteria

The ADR had already diagnosed the existing yield-curve chart's
`preserveAspectRatio="none"` — text and strokes squashed roughly 37%
horizontally at 390px — and prescribed the fix: a viewBox per
breakpoint with `xMidYMid meet`, because `ResizeObserver` measurement
would reintroduce the server-rendering failure that disqualified
Recharts in the first place. That is what was built, and it was
verified rather than assumed: through the DevTools protocol, viewBox
aspect and rendered aspect match to three decimals at both 390px
(1.714) and 1440px (3.167).

The ADR's second recorded defect was that the old chart used two ARIA
patterns at once. This one picks a labelled image, with the numbers
behind a disclosure as a real table — which serves sighted readers
wanting exact values just as much as screen-reader users, and is the
same "check this" instinct the rest of the page runs on.

The old `/rates` chart still has the distortion bug. #40C did not widen
to fix it; no code is shared, and it stays ADR-041's acceptance
criterion for #41.

### Proving the negative

"No provider call during intelligence read" is awkward to test by
mocking, and the first attempt did it badly: monkeypatching `httpx`
inside an integration test, which promptly failed an existing guard
forbidding integration tests from importing `httpx` at all. The guard
was right and the test was wrong — the point of that rule is that a
test file which cannot import a network client cannot accidentally use
one.

Rewritten as a static import check in the codebase's own idiom: parse
every module on the read path — domain, service, builder, repository,
contracts — and assert none imports an HTTP client, a provider client
or a model SDK. Stronger than the mock, because it covers code paths no
test exercises, and it needs no network library to state it.

### Cost

About 3.3 KB gzipped per page: +2.0 KB HTML, +1.3 KB JavaScript, and
+0.11 s of build time. The biggest raw contributor is the 63-row
verification table, which is a deliberate purchase — it is what makes
the chart checkable rather than decorative. Nothing in the numbers
suggested a problem, so nothing was optimised.

## Increment #41 — Economic Worlds & consumer information architecture

MacroChipz's navigation used to read:

> Home · Overview · Inflation · Labor · Rates · Releases

Three of those six were our words, not a reader's. "Overview" named an
internal idea — the intelligence workspace. "Labor" and "Releases" were
the engineering domain's vocabulary leaking into the product. #41 makes
the navigation the economy plus the two surfaces that are not part of
it:

> Home · Inflation · Jobs · Rates · Calendar

### The registry, and what it refuses to be

`src/worlds/registry.ts` defines a world once: id, label, route, one
plain sentence, and the analytics value. It is code rather than a table
because worlds change when the product changes, not when data changes.

What it deliberately is not is the more interesting list. Not a CMS —
no slots, no component configuration. Not a methodology — no
thresholds, no states. Not a fetcher. And not a provider identity: a
test fails if `PAYEMS`, `UNRATE`, `UST_` or `FRED` ever appears in it,
because a world is a MacroChipz concept and #38 exists to keep those
two things apart.

Housing is absent rather than present-and-empty. #27A §11 already froze
the rule — a navigation slot follows content, it does not precede it —
and an inactive world with no data is a promise the product cannot
keep. Adding it in #45 is one entry in one array.

### Jobs is a rename of the product, not of the domain

The public world is Jobs. The engineering domain stays Labor:
`labor_v1.0`, `app/domain/labor.py`, `/api/v1/monitors/labor`,
`LaborState`. The registry records that mismatch in a field called
`engineeringDomain` rather than hiding it, and a test asserts the
endpoint and the methodology id are untouched. Renaming a frozen
methodology to improve a heading would break replay against every
conclusion already recorded, which is a high price for a nicer word in
a file nobody reads.

### The distinction the frontend had been quietly dropping

`app/concepts/registry.py` makes `universe` a required field, and says
why in its own docstring: CES counts *jobs*, CPS counts *employed
people*. Nonfarm payroll employment carries
`universe="NONFARM_PAYROLL_JOBS"`; the unemployment rate carries
`universe="CIVILIAN_LABOR_FORCE_PERSONS"`.

The frontend showed none of it. Grepping the labor UI for `universe`,
`CES`, `CPS`, "establishment survey" or "household survey" returned
nothing at all. A reader saw two headings, "Employment" and
"Unemployment", with no indication they count different populations —
so the one thing most likely to confuse someone was the one thing the
page never mentioned.

It now says so, in the reader's words: one survey counts jobs, so a
person with two jobs counts twice; the other counts people, so someone
who stops looking for work leaves the count entirely rather than
appearing as a job lost. Which is why they can move in different
directions in the same month without either being wrong, and why
MacroChipz reports Mixed rather than averaging them into a number that
would describe neither.

It refuses to say which is right when they disagree — a test fails on
"more accurate", "more reliable", "better measure". Explaining a
methodological boundary is not the same as adjudicating it.

### A freeze that was worth respecting

The note first went in as its own page section, which broke the
seven-section hierarchy `docs/architecture/labor-ui-v1.md` §7 had
frozen, and a test said so immediately. The right response was not to
update the frozen list — it was to notice that the note belongs inside
the Unemployment section anyway, at the exact moment the page stops
talking about jobs and starts talking about people. The test was right
and the first instinct was wrong.

### The chart defect ADR-041 had been carrying

ADR-041 recorded `preserveAspectRatio="none"` on the Treasury curve as
a live bug, measured the damage (x scaled 0.542 against y's 0.862 at
390px — roughly 37% horizontal squash), prescribed the fix, and named
#41 as the acceptance point. #40C had already built that fix for a
different chart, so this was mostly transcription: `xMidYMid meet`,
viewBox per breakpoint, CSS-swapped.

Measured afterwards in real Chrome rather than asserted: viewBox aspect
and rendered aspect now match to three decimals at both 390px (1.500)
and 1440px (2.923).

### A redirect is not a 301, and saying so is the work

`/overview`, `/labor` and `/releases` all still resolve, via
`<Navigate replace>`. That is correct for people and incomplete for
crawlers: a crawler that does not run JavaScript sees a shell and never
learns the successor exists.

The honest thing was to find out whether a true 301 could be written at
all. It cannot — there is no Vercel, Netlify, Cloudflare or S3 config
in the repository, the Dockerfile does not serve the frontend, FastAPI
mounts no static files, and CI never deploys. So the three 301s are
specified in the rendering document as an obligation for whoever picks
the host, and the compatibility routes are deliberately left out of
both the prerender list and the sitemap so they cannot compete as
canonical URLs. A `vercel.json` for a host nobody has chosen would have
been a guess wearing the costume of completeness.

### One sweep that went too far

Late in the increment a global replace of "Economic Intelligence" with
"MacroChipz" — intended to make the actor consistent — also rewrote
curated methodology explanations and the brand line, turning the footer
into "MacroChipz · MacroChipz" and breaking seventeen tests that
encode frozen wording. Reverted the curated content and the chrome,
kept the two cases where the sentence genuinely names an actor.

The lesson is small but repeatable: a rename across a product is not a
`sed` over a repository. Curated copy and brand chrome are not the same
category of string as UI labels, and the tests knew it before I did.

## Increment #42 — THE LEDE and the MacroChipz homepage

The instruction was to build a homepage that makes the economy feel
alive within seconds, without inventing importance, urgency, causality
or news. The first thing to find out was what the data would actually
support.

### Counting before designing

1,899 Structured Intelligence objects. 1,488 of them COVERAGE. And
what the homepage would have shown with no policy at all: eight
coverage events from the jobs world, with effective periods in **2027**
— future months, sitting at the top of the default ordering.

Two findings went deeper than the counts, and neither is visible from
the taxonomy:

**All 44 "ECONOMIC" analysis changes are `UNAVAILABLE -> something`.**
Not most. All of them. They record the confirmation relationship
becoming computable during backfill. #39 classifies them ECONOMIC and
it is right to — the field genuinely is an economic field — but
"MacroChipz can now calculate this" is an availability event wearing an
economic field's clothing. Filtering on `change_class` alone, which is
the obvious implementation, would have put all 44 on the homepage as
economic news.

**All 358 observation changes are first observations**, `previous_value`
null throughout. A value arriving for the first time in a backfill is
not something that changed.

Strip those out and exactly six objects remain eligible: the six
Treasury maturities. Which is a narrow homepage, and an honest one.

### The policy, and the sentence it is not allowed to say

`homepage_presentation_v1.0` answers "what should MacroChipz show
first?" and is forbidden from answering "what is economically most
important?". #39 publishes no significance ranking and #42 did not add
one.

That boundary is enforced rather than asserted. A test reads the policy
source and fails on the strings `score`, `weight`, `importance`,
`priority`, `significance`, `severity`, `Math.random`, `Math.abs`,
`percentile`, `magnitude` and `change_basis_points`. If a future
increment wants to rank by size of move, it will have to delete a test
that says out loud why it exists.

Ordering is four structural keys — effective period, world, concept,
then id as a total-order guarantee. The concept key is the only
editorial one: the 10-year leads the rates world because it is the most
widely referenced benchmark maturity. That is a fact about how people
talk about rates, not a claim that it moved more, and the code says so
in those words.

### No clock, and why that is correctness rather than taste

Nothing in the policy reads the time. The homepage is prerendered, so a
policy that consulted a clock would bake one moment's answer into
static HTML and then quietly lie about it for as long as the build
lived.

That was only possible because the ten future-dated objects all turned
out to be COVERAGE, so the coverage filter already removed them and no
"exclude the future" rule was needed. Worth checking rather than
assuming — the time-dependent version of this policy would have looked
perfectly reasonable in review.

### The state I did not know I needed

THE LEDE started with two states, active and quiet. Building the
production bundle showed the defect: the prerendered homepage contained
**"No new tracked change"**. The page fetches in the browser, so at
prerender time there is no data, and passing an empty list to the
policy produced the quiet state — which is a claim. A crawler would
have read MacroChipz asserting the economy had produced nothing new,
permanently, on a page that had never checked.

So there are three states, and the third one matters most:
**unknown is not quiet.** Before the answer is in, the lede says what
it is and offers the three worlds, and asserts nothing about the
economy at all.

The quiet state also refuses the obvious fallback — showing the
freshest ineligible object instead of nothing. That object is by
definition one of the 1,488 coverage events the policy exists to keep
off the page. A quiet day is a valid product state. An invented
headline is not.

### Time words the data cannot pay for

`published_at` is null on every object MacroChipz holds. `recorded_at`
spans two days because it is a backfill timestamp. So the homepage
cannot say "today", "new", "just released" or "latest" about anything,
and it does not: it shows the effective period, which is the one time
concept the data actually supports. Slightly less exciting copy, and
true.

### What I found below the fold and chose not to fix

The new lede filters coverage correctly. The legacy sections beneath it
do not. Scrolling the homepage on a phone still reaches
"Availability restored" rows and, in one place, the literal string
`Unavailable -> 3.353016322755642` presented to a consumer.

That is the same class of defect #42 was written to prevent, one
section lower on the same page. I left it, deliberately: those sections
are #19A-#25H with extensive frozen tests, rewriting six of them at the
end of a long increment is how a scoped increment becomes an unscoped
one, and #43 already owns the revision experience that should replace
them. It is written up as the first residual limitation rather than
quietly tolerated — a bounded limitation beats fabricated completeness,
but only if it is actually stated.

### One repair from the previous increment

The prerendered homepage title read "MacroChipz — MacroChipz". #41's
over-broad find-and-replace had rewritten the site title's category
half. Caught by reading the built HTML rather than by any test, which
is a reminder that the build output is worth looking at directly even
when the suite is green.

## Increment #42A — Legacy change surfaces removed from the homepage

#42 built a presentation policy that keeps coverage and bootstrap
events off the homepage, and then left three older sections rendering
those same events two screens further down. Scrolling `/` on a phone
still reached "Availability restored" rows and, in one place, the
literal string `Unavailable -> 3.353016322755642` presented to a
consumer.

A filter that something else bypasses is decoration. So Since Your Last
Check, What Changed, and Recent Data Updates were removed from the
homepage composition.

Removed from the composition — not redesigned, not deleted. Every
component still exists, unchanged. `components/labor/LatestDataDetected.tsx`
turned out to be a different file from the overview one with the same
name, which is the sort of thing worth checking before deleting
anything: the Jobs page still renders it.

Nothing replaced them. The instruction was explicit that the homepage
should not gain another feed, and #43 owns the Revision Intelligence
experience that should eventually present this material properly.

### What the removal exposed

Two stale links, both pointing at `/releases` — a #41 compatibility
redirect — so the homepage had been routing readers through a redirect
to reach a canonical page. Fixed to `/calendar`.

And a coverage gap worth stating rather than hiding: `WhatChangedPreview`
and `LaborWhatChangedPreview` were tested only through Home integration
tests. With the section gone, those tests went too, and the components
are now rendered by no route and covered by no test. That is written
into the documentation as a #43 obligation instead of being left for
someone to discover.

The policy itself needed no change. It was already correct; the legacy
sections simply never consulted it.

### The test that would have caught it earlier

The new regression suite renders `/` with fixtures that deliberately
CONTAIN the noise — an `UNAVAILABLE -> 3.353016322755642` analysis
change and a COVERAGE sibling — and asserts the page shows neither, and
that THE LEDE stays quiet rather than promoting an ineligible object to
fill the slot. Fixtures that are clean prove nothing; these ones are
dirty on purpose.

## Increment #43 — Revision Intelligence

The instruction was to turn observation versioning, replay and
Structured Intelligence into a consumer feature answering one question:
*the number changed — did that change what we thought was happening?*

The first job was to find out whether the number had ever changed.

### It has not. Not once.

1,072 versioned observation rows. Every single one
`change_type=BACKFILL, origin=BACKFILL, is_backfilled=true`. Zero
observations with a second version. Zero superseded rows — every
`recorded_to` is null, which means no value MacroChipz has ever stored
has been replaced by a later one. All 358 `OBSERVATION_CHANGE` objects
are `NEW` with a null previous value.

The replay side looks healthier until you read the flag: 133 recorded
monitor results, 133 `MATCH`, and every one carrying
`inputs_include_backfilled: true`. They match because they compare
today's data against itself. The service was already honest about that;
it just needed someone to read it.

So MacroChipz has captured no genuine revision, and #43 ships a feature
whose populated state has never occurred. The instruction anticipated
exactly this and was right to: the work is to make the empty state
teach the feature, not to manufacture one.

### The distinction the whole increment rests on

`change_type` says `REVISED` for two completely different things: a
value MacroChipz watched change, and a value whose earlier version was
imported at migration time. The second is not a revision. Presenting a
#31 backfill as "originally reported" would be inventing economic
history — the most damaging thing this feature could do, and the
easiest to do by accident, because the field name invites it.

So the contract gained one small additive field, `revision_knowledge`,
with three states rather than a boolean, because they license different
sentences: `FIRST_OBSERVATION`, `PROSPECTIVE_REVISION`,
`BACKFILLED_BASELINE`. It defaults to the state that claims least, so an
object built before #43 never asserts an original value nobody saw. The
builder derives it from the stored version rows and returns the
conservative answer whenever they cannot prove otherwise.

The frontend then reads that field and never reasons about versions
itself. A guard test fails on `observation_versions`, `recorded_from`,
`recorded_to` and `is_backfilled` appearing in the selection module at
all.

### What the empty state had to earn

A dead "nothing here yet" panel would waste the only moment someone is
curious about revisions. So `/revisions` explains what a revision is,
lists exactly what will appear when one arrives, and says why the older
ones cannot be reconstructed.

That last part states no date, deliberately. The stored `recorded_from`
on a backfilled row is the migration timestamp. Printing it as "tracking
began on…" would dress a database event as an economic boundary, which
is the same false precision the increment forbids everywhere else. A
test asserts no ISO date appears on the page.

### Colour that refuses to judge

A downward revision is not bad news. Unemployment falling and inflation
falling are opposite sentiments from identical arithmetic, and
MacroChipz has no methodology that ranks either. So the comparison uses
one neutral token for both values, carries direction in the words "Up"
and "Down", and a test fails if a `state-*`, `feedback-*`, red or green
token appears in the component.

Ordering is by detection time and then by id. A test proves the larger
revision does *not* sort first — there is no significance methodology
in #43, so "the biggest revision" is not a sentence MacroChipz can say.

### The #42A obligation, discharged

#42A removed three legacy sections from the homepage and left
`WhatChangedPreview` and `LaborWhatChangedPreview` unimported and
untested. Repository search confirmed neither is imported anywhere, so
both were retired. `SinceLastVisit`, `RecentDataUpdates` and the
overview `LatestDataDetected` are also unrendered but still carry their
own tests and a guard, so they were kept with that decision written
down rather than deleted in the same sweep.

One near-miss worth recording: `components/labor/LatestDataDetected.tsx`
is a different file from `components/overview/LatestDataDetected.tsx`
and the Jobs page still renders it. Same name, different component.
Checked before deleting anything.

### A small self-inflicted detour

The "Revision history →" link went onto the Inflation and Jobs pages as
a router `<Link>`, which needs router context, which the Inflation test
suite does not provide — 56 tests went red at once. The fix was a plain
anchor rather than wrapping 56 tests in a `MemoryRouter`: this is a
cross-capability jump out of a world, a full navigation is fine, and
the page stays renderable without a router. Rates deliberately got no
link at all, because Treasury publishes one observation per business
day and MacroChipz has never recorded a second version of one.
Manufacturing symmetry there would have been the same mistake in a
different costume.

## Increment #44 — Economic explainability and rabbit holes

The brief said to inventory the existing explanation content before
writing any. Earlier notes put it at "approximately 34". It is 71.

More useful than the count was what they are: field-level annotations
bound to specific UI — what `r_3m_annualized` means on the card it sits
on. They are good at that, and they cannot do the new job at all.
Someone arriving from a thirty-second video has no surrounding page for
a tooltip to annotate.

That framing settled the architecture without much argument. An
`Explanation` is an annotation; an `Explainer` is a destination. So #44
added a second model beside the 71 rather than rewriting them.

### The statistic I did not use

#35 found the strongest consumer misconception in its whole research
set: 66% of prospective homebuyers believe the Federal Reserve sets
mortgage rates. It is documented in the repository with attribution —
and the attribution is grade B, n=400, a lender-marketing survey
reported through a trade publication.

The increment said to verify before using it publicly and noted the
explainer does not need it. Both true. So the page says the belief is
common and does not quantify it, and a test asserts no percentage
appears anywhere in the flagship.

### Three claims I flagged instead of quietly shipping

The mortgage explainer needs to say what *does* reach a mortgage rate,
and the increment's own §9 supplied the framing: the market for bundled
mortgage loans, prepayment risk, credit and liquidity conditions,
lender economics. Those are uncontroversial in fixed-income practice
and they are not sourced anywhere in this repository.

§16 says to stop and report claims needing external verification rather
than passing model knowledge off as production copy. So they are
written generically, attributed to no institution, and listed
explicitly in the architecture document as needing verification before
public launch. The parts that ARE sourced in-repo — the Fed's objective
being defined on PCE, the 10-year being a reference point that sets
nothing, the CES/CPS universe split — are marked as such.

### A test that had to learn a distinction

The guard against "never says the Fed sets mortgage rates" failed on
the explainer's own misconception field, which reads "the common belief
is that the Fed sets mortgage rates outright".

That is the sentence being corrected, not a claim. An explainer that
cannot state a false belief cannot correct one. So the claim-checks now
run against the fields that assert things and the misconception field
is tested separately for being framed as a belief with a correction
attached. The first version of the test would have forbidden the
product from doing its job.

### The shape of the diagram is the argument

A single top-to-bottom arrow — Fed, then rates, then you — would have
drawn exactly the belief the page exists to correct. So four influences
converge instead, with Fed policy as one of them rather than the source
of the chain, and a line underneath saying these interact rather than
forming a single chain. No diagram library, no colour dependency, and
every influence carries its own sentence so the whole thing works as
text.

### The live number I deliberately left out

The obvious next move was a "Right now in MacroChipz: 10-year 5.01%"
block. I did not add it, and the reason is the whole point of these
pages.

An explainer that fetches is an explainer whose prerendered HTML is an
empty shell. These ten routes are currently the only MacroChipz
surfaces whose *substance* a non-JavaScript crawler can read — 3,235
characters of real text on the flagship with every script stripped. A
live number the reader is one click from was not worth trading that
for. It also means the page has nothing that can fail.

### Respecting a freeze for the second time

Adding "Understand this" to the Jobs page broke the seven-section
hierarchy frozen in `labor-ui-v1.md` §7, exactly as the same mistake
did in #41. The difference this time is that the addition is genuinely
outside that hierarchy — a page-level footer after the evidence, not a
monitor section — so rather than avoiding an `h2` I extended the frozen
list deliberately and wrote an addendum into the frozen document
explaining what was appended and why.

Updating a freeze on purpose and recording it is fine. Editing one
quietly because a test is in the way is not.

## Increment #45 — Housing World Foundation

MacroChipz's fourth economic world, and the first one that renders no
conclusion. Baseline: HEAD `208ab7d` (#44), clean tree. 2,494 backend
tests and 1,789 frontend tests pass; nothing committed, nothing pushed.

### The increment stopped at a gate, and stopping was correct

#45 began earlier and halted before writing any production code, because
Census was not on #28's source allow-list. It is worth being precise
about why that was right rather than pedantic: #28's tables are not a
list of sources someone liked, they are the record of which providers
were verified as usable in a commercial product at $0, and Housing was
never in the domains #28 surveyed. Census appears in neither the
MVP-eligible table nor the rejected one. "Not assessed" is a different
state from "approved", and building on it would have been the exact
failure #28 existed to prevent — two days of reading that changed the
domain scope and reversed a build decision.

The source was then reviewed deliberately and admitted. §11A of the #28
artifact is an **append-only log** rather than an edit to §11: the
original tables still say what was true on 2026-09-19, and the new entry
says when Census was reviewed and on what evidence. Rewriting §11 to
include Census would have made the repository claim it had always been
approved, which is a small lie about a licensing decision — the class of
thing this project cannot afford to be casual about.

Approval attaches to the reviewed *program*. `resconst` is admitted;
retail sales, durable goods and every other Census dataset are not.

### Ninety minutes lost to an unactivated key

The first connectivity check failed. The key was present in `.env`, 40
lowercase hex characters, parsed identically by `load_dotenv`,
`dotenv_values` and a hand-parse — and rejected. The decisive test was
pointing the same key at an unrelated dataset (ACS): also rejected. That
made it account-level rather than `resconst`-specific, which is the
difference between "our request is wrong" and "the credential is not
live".

Census issues a correctly-formatted key that is rejected until the
confirmation email is used, and the rejection is indistinguishable from
a wrong key. The client now detects both of Census's key redirects and
names activation in the error, because an operator hitting this should
lose a minute rather than an afternoon.

**Census does not use 401.** A bad key is `302 → /data/invalid_key.html`
and an absent one `302 → /data/missing_key.html`, both of which render
as a `200` HTML page if redirects are followed — which is how a careless
client reports "malformed response" for what is really a configuration
problem. The client refuses to follow redirects at all, which converts
that into a typed `CensusAuthError` and has the side benefit that
nothing is ever fetched from a URL the client did not build.

### The first provider here that holds a secret

FRED's key predates all of this and is handled adequately. Census is the
first one added since the project started taking provenance seriously,
and the leak paths are all boring: a `repr` in a log line, an exception
message, a chained traceback.

The one worth recording is that **`str(httpx.HTTPError)` contains the
request URL**, and this client's request URL contains the key. So the
obvious code —

```python
raise CensusUpstreamError(f"Failed to reach Census: {exc}") from exc
```

— leaks the credential twice: once in the message, once in the chained
traceback. Both halves are wrong, and `from None` is load-bearing rather
than stylistic. The tests assert against the *full formatted traceback*,
not just `str(exc)`, because that is what actually reaches a log.

`source_url` in provenance is the program's landing page and never an
API URL, for the same reason: an API URL for this provider would write a
secret into the database.

### Two units, because one of them is a trap

Census publishes each measure twice, and the second one is not a
refinement of the first.

`1,394,000` is a **seasonally adjusted annual rate** — Census's own
definition is "the seasonally adjusted monthly value multiplied by 12",
and it is "neither a forecast nor a projection". The actual number of
homes authorised in August 2026 was `117,400`.

The tempting error is not presenting the annual rate as homes built that
month — that one is obvious once stated. It is **dividing by twelve**.
1,394,000 ÷ 12 = 116,167, against a real figure of 117,400: close enough
to look like a rounding difference, and wrong on principle, because the
seasonal adjustment that produced the annual rate is exactly what the
division throws away. A reader checking the arithmetic would find it
plausible. So would a reviewer.

There is no seasonally adjusted *monthly* level to fall back on; Census
does not publish one. Month-over-month comparison therefore requires the
annual rate, and honesty requires the unadjusted count beside it.

Hence six concepts rather than three. That is not padding: the pair is
what lets the product **show** the distinction — 117,400 sits directly
beneath 1,394,000 on the page — instead of asserting it in a footnote.
And `seasonal_adjustment` being a required field on `EconomicConcept`
stopped being a formality the moment two concepts appeared with the same
universe and different adjustments.

Both errors are now AST-guarded: no Housing module may divide or
multiply by twelve.

### The world with no state, and what that cost

Every other world renders a conclusion. Housing renders none, because
there is no `housing_v1.0` and the 2.0 sequence names five things one
would require — none of which #45 met.

Writing that page is harder than writing a graded one, and the pressure
is specific: **"Permits −2.7%" wants a word next to it.** Every instinct
says put "cooling" there. The page answers a narrower question instead —
how many homes are entering the pipeline — and leaves the conclusion to
the reader.

The guard that matters is not the one forbidding "cooling". It is the
one asserting that `HousingResult` has **no `state`-shaped field at
all**, so no surface can render a state from canonical data even if
someone wants to. Adding one would have to be a deliberate contract
change, which is the point.

### Census would not let us claim significance even if we wanted to

Census's release states that starts fell 2.6 percent (±12.0 percent),
and that a range containing zero means "it is uncertain whether there was
an increase or decrease". So the headline monthly move in the flagship
series is **not statistically significant**, by the publisher's own test.

MacroChipz cannot reproduce that test: the intervals come from sampling
variances the API does not expose. Reconstructing them would be inventing
statistics. Asserting significance without them would be worse.

So the page reports the change and **quotes Census's own guidance** — it
may take three months to establish a trend for permits and six for
starts and completions. Borrowing the provider's caution is a better
answer than either inventing a threshold or saying nothing.

### The backfill that must not become news

This is the part #43 made me get right, and the scale is what makes it
matter. The initial import is 4,644 observations spanning 1959 to 2026.
Every one of them is a value MacroChipz *learned at one instant*, not one
it watched arrive.

If those had been recorded as observed, `/revisions` and the homepage
feed would have filled with 4,644 "new data point" entries — MacroChipz
reporting its own migration as economic news, at three times the scale of
the 1,488-row coverage-noise precedent #39 already documents.

`is_backfilled` existed for #31's migration. #45 widens it to a new
source's first import, and the widening is honest because the *meaning*
is identical: #31's own sentence — "this value existed in MacroChipz by
this time", never "this was the value the source first published" —
describes both cases exactly. What I did not do is add a second flag
meaning almost the same thing.

The decision is per observation, by a pure function, and the interesting
case is the third one:

- series empty → baseline;
- month older than the newest stored → baseline (filling backwards is
  not watching);
- **month newer than the newest stored → observed.** A release arriving
  is real news, and marking it baseline because it happened to arrive in
  the same run as a backfill would throw away the only genuine first
  observations this pipeline will ever produce.

The writer enforces the other half independently: `baseline` applies only
to `NEW` versions, because reaching the revised branch at all means
MacroChipz held an earlier value and saw it change. That is the one case
where "originally reported" is provable, and a caller must not be able to
discard it by passing a flag.

Measured after the real import: 4,644 version rows, **every one
`is_backfilled = true`**; 1,899 intelligence objects, **none of them
housing**. Re-running the sync wrote nothing and created no version rows.

### The type I did not add

Housing has no release-calendar entry — Census publishes its schedule as
HTML and PDF only — so no release-processing row will ever exist for it,
and the existing `OBSERVATION_CHANGE` path had nothing to read.

The obvious move is a `HOUSING_OBSERVATION` type. I did not add one,
because every field of `ObservationChangePayload` is populated here from
real data and the semantics match exactly. A type that differs only by
*which table the data came from* would make #39's taxonomy describe our
plumbing instead of the economy — which is the same argument §10 of that
document already makes against a significance score.

So the Housing path reads a different source and produces the same type.
It is also the first world where `methodology` is `None` on every object,
and that revealed something quietly good about the contract: **`basis`
could already express a world with no methodology.** Nothing in #39
needed changing to admit one.

### A test that caught a half-honest object

`test_a_revision_of_a_backfilled_baseline_is_not_a_prospective_revision`
failed on its last assertion. The object's `revision_knowledge` was
correctly `BACKFILLED_BASELINE` — but its `limitations` said nothing
about it.

Machine-readably honest, and silent in the words a person reads. The
release-processing path had attached that sentence since #43 and the new
path had not. A typed field that is right while the prose is absent is
half honest, and on a page the prose is the half that gets read.

### Refusing to put a number in the rate section

Every reader of a housing page is thinking about mortgage rates, and the
2.0 architecture planned to show `UST_NOMINAL_10Y` there as an
"explicitly labelled proxy". I did not ship it, and the reason is not
that the label would be inaccurate.

**Two numbers side by side on one page read as connected**, whatever the
caption says. MacroChipz publishes no housing-to-rates relationship, no
elasticity and no lag — so a yield rendered beside permits and starts
would be the page asserting something its own data has measured nothing
about. "Labelled proxy" does not undo what the layout communicates.

The section is a signpost instead: what MacroChipz tracks, what it does
not, and two links. It contains no digit, and a test asserts that.

### Three guards that had to learn distinctions

#44 recorded that its assertion guards initially flagged the
`misconception` field — prose that states a belief in order to correct
it. #45 hit the same class three more times, all on my own new copy:

- Census's "neither a forecast nor a projection" tripped *makes no
  forecast*;
- "a predictable schedule", the misconception being corrected, tripped
  the same guard on `predict`;
- "MacroChipz applies no ... score", a disclaimer, tripped *implements no
  ranking, scoring*.

Each fix made the guard **more precise, not weaker**: whole-word matching
instead of substring, negated forms stripped before the forecast scan,
and the scoring guard scoped to code outside the content array — the
inverse of the scoping an adjacent test already used. A bare "forecast"
still fails.

The general lesson is now firm enough to state: **a guard that forbids a
word forbids the correction too, and the correction is usually the thing
the page exists to deliver.**

### A repository that could not be cloned and built

Measuring the bundle delta meant building HEAD, so I created a git
worktree at `208ab7d` and ran the build. It failed:

```
Error loading react-router.config.ts:
Cannot find module './src/build/prerenderPaths'
```

`frontend/.gitignore` line 28 is a bare `build/`, which matches a
directory named `build` at **any depth** — including `frontend/src/build/`,
which holds `prerenderPaths.ts`, a module both `react-router.config.ts`
and `src/routes.ts` import at config time. It has never been committed.
**A fresh clone of this repository cannot build the frontend**, and has
not been able to since #40A created that directory.

Fixed by anchoring the pattern (`/build/`). The file is now untracked
rather than ignored and needs adding. Found only because a measurement
required a clean checkout, which is an argument for measuring against one
more often.

### Measured

| | Before | After |
|---|---|---|
| Client JS | 555,536 B | 577,246 B (**+21,710**) |
| Client JS, gzipped | 161,273 B | 166,611 B (**+5,338**) |
| `entry.client` chunk | 214,868 B | 214,868 B (**+0**) |
| Prerendered pages | 15 | 18 |
| Backend tests | 2,195 | 2,494 |
| Frontend tests | 1,668 | 1,789 |

No new npm dependency, and no charting library for a three-series chart.
`GET /api/v1/housing` is 27,050 bytes in 66–81 ms; the three chart series
are 10,541 bytes of that, and the rest of the response is 6,151.

The one thing I optimised, I optimised on evidence: the read path issued
24 queries for six measures because it resolved each series row twice.
Threading the row through removed twelve. It is 18 now, and I stopped
there — 68 ms is not a problem, and the next step would be batching that
buys nothing measurable.

### Verified in a browser, not only in jsdom

Real Chrome, through the DevTools protocol. Chart aspect ratios match
their viewBoxes to three decimals at 390 px (1.286/1.286) and 1440 px
(2.533/2.533) — ADR-041's distortion defect does not exist on this chart.
One `h1`, no skipped heading levels, every `aria-labelledby` resolving, no
horizontal overflow, both tables captioned.

Two things only the browser found. The SAAR explanation rendered `--`
literally, because I wrote consumer copy in the repository's Python
docstring style. And **the site footer named FRED and Treasury but not
Census** — the required non-endorsement notice was rendering only inside
a collapsed `<details>` on one page, which is not a display. It is in the
footer now, on every page.

### Lesson

**A source-gate is only worth having if it can stop you.** #45 halted at
one, and the halt was the increment working correctly rather than a
process obstacle — the gate existed precisely so a licensing question
would be answered before code depended on the answer.

The second lesson is narrower and more practical: **when a provider
publishes the same quantity two ways, the resemblance between them is the
danger.** 1,394,000 ÷ 12 and 117,400 are 1% apart. A conflation that
produced an obviously wrong number would have been caught in review; this
one would have shipped.

## Increment #45A — Product Cohesion & Data Opportunity Audit

Audit and planning. No production code, no API integrated, no world
created, nothing committed. Baseline: HEAD `8b09b62` (#45).

Artifact: `docs/product/macrochipz-product-cohesion-data-opportunity-audit-v1.md`.

### Walking it instead of reading it

The instruction was to audit the running product rather than the source,
and the difference mattered immediately. From the code, MacroChipz has
four worlds, revision intelligence, twelve explainers, permanent objects
and an analyst. From the homepage, MacroChipz is a Treasury yield
tracker.

I extracted the internal link graph from rendered DOM across all seven
surfaces rather than reasoning about it from components, which is how
three things surfaced that I would not have trusted myself to find by
reading:

- **`/calendar` has zero outbound internal links.** A hard dead end, and
  it is one of six primary nav items.
- **`/revisions` has exactly two inbound links** — from `/inflation` and
  `/jobs`. Not from Rates, not from Housing, not from the homepage, not
  from nav.
- **Every explainer inbound link originates on a world page.** Zero
  orphans, which is good, but a reader who lands on `/` and does not
  open a world will never encounter educational content at all.

### The number that explains the homepage

1,899 intelligence objects exist. **Six are eligible for the homepage,
and all six are Treasury yields.**

That is not a bug in `homepage_presentation_v1.0`. The policy correctly
excludes 1,532 `ANALYSIS_CHANGE` objects that are mostly coverage
records and 358 `OBSERVATION_CHANGE` objects that are all first
observations rather than changes. It is doing exactly what #42 designed
it to do.

The consequence is structural rather than editorial: **the homepage can
only ever be a bond page until a second kind of object becomes
eligible.** That reframed the whole roadmap question. The homepage is
not badly designed; it is accurately rendering a database whose only
"changes" are in one world.

### The finding I nearly got wrong

"How They Relate" renders *"Inflation is Mixed as of July 2026. Jobs is
Mixed as of August 2026."* — two facts already on screen 200px above it.
My first note called it a dead section.

It is not. `relate-composition-v1.md` (#23C) freezes it to exactly one
composition sentence with no interpretation, and prohibits "confirms",
"diverges", "Goldilocks", "soft landing" and "the economy is [anything]"
absolutely. The component is doing the most it is permitted to do.

**The constraint is right and the heading oversells it.** That is a
copy fix, not an architecture fix, and writing it down the wrong way
round would have invited someone to "improve" a frozen boundary later.

### Every expensive thing is the hardest to find

Sorting the feature inventory by discoverability produced an
uncomfortable pattern: revision intelligence (#43), point-in-time replay
(#31), the Analyst (#33) and sharing (#40) are four of the most
engineering-intensive capabilities in the repository, and they occupy
the bottom four rows.

Point-in-time replay has **no consumer surface at all**. Sharing exists
only on permanent object pages, which are themselves homepage-only, and
is **absent from the explainers** — the most shareable things in the
product.

### Why #46 Follow should not be next

Follow addresses RETURN, which the loop analysis confirms is the stage
that is completely missing. That argues for building it.

Building it now would ask readers to subscribe to **Treasury yield
movements**, because that is the only thing the homepage can surface.
And a weak signup rate would be uninterpretable — indistinguishable
between "nobody wants to return" and "nobody was shown anything worth
returning for". **A measurement you cannot read is worse than no
measurement**, because it feels like evidence.

So the recommendation is #45B Product Cohesion first: no new data, no
new world, and every fix unlocks engineering already paid for.

### Polymarket: the technical answer is yes and the legal answer is no

The Gamma API answers unauthenticated with HTTP 200 and rich per-market
fields — bids, asks, condition ids, resolution dates. There is no
technical obstacle of any kind.

Then the disqualifying fact: **ICE has acquired exclusive rights to
distribute Polymarket's event-driven data globally**, as part of a
$1.6–2.0bn investment completed in March 2026, and now ships those
probabilities through the ICE Consolidated Feed and a "Signals and
Sentiment" product for institutional customers.

A public read API is an access mechanism, not a redistribution licence —
and where an *exclusive* distribution right has been sold, unlicensed
commercial redistribution is more hazardous rather than less. There is
now a counterparty with a two-billion-dollar interest in enforcing it.

Two repository precedents settle it. #28 already rejected ICE BofA
spreads and ICE DXY on exactly these grounds, and rejected CME FedWatch
because *"derived data is separately licensable, so recomputing and
republishing is also barred"* — which is precisely the shape of
displaying a probability.

Neither terms page was readable (one geo-gated, one client-rendered), so
the specific clauses are **UNRESOLVED — in the direction of caution**.
This is not a "defer pending further research" item. Further reading
will not change the exclusivity; only a written licence would, and that
is a commercial negotiation rather than an engineering task.

**The better answer was already in the repository.** #28 §11.1 lists the
FOMC Summary of Economic Projections as **MVP-eligible, public domain,
"labelled as participants' projections"**. If Expectations is ever
built, the Fed's own published projections are a better source than a
prediction market on every axis that matters — licensing, authority, and
epistemics. The dot plot does not need a disclaimer explaining that it
is not a fact; its publisher already says so.

### The Census adapter is worth more than one world

I checked whether the other Census economic programs share `resconst`'s
shape, expecting "similar". They are **identical**: `marts` (retail
sales), `bfs` (business formation), `m3` (durable goods) and `ressales`
(new home sales) all expose the same thirteen variables the #45 adapter
already parses and validates.

So retail sales — *"are Americans spending more?"*, the strongest
unbuilt consumer question in the product — is an allow-list entry and a
set of bindings. **No new adapter, no new credential, no second
architecture.** That single measurement did more to shape the roadmap
recommendation than anything in the product walk.

The caution stands and is written into the artifact: identical *schema*
is not identical *semantics*. Each program still needs its own §11A
entry, its own revision behaviour and its own missing-data review.

### The most interesting unbuilt thing

BEA's GDP would be the first series whose revisions arrive as a
**named, scheduled sequence** — advance, second, third. #43's
`PROSPECTIVE_REVISION` currently means "we watched it change", full
stop. A GDP revision is not merely *a* change; it is a *known stage*.

MacroChipz's revision moat is most valuable precisely on the series that
revise most predictably, and the product does not yet have one of those.
Recorded as an opportunity rather than a design.

### What I could not verify

The Chrome extension could not produce a true mobile viewport —
`resize_window` reported success while media queries went on matching
desktop. I ran a harsher substitute (desktop layout forced into 390px)
and it is dominated by grid classes that collapse at phone width, so it
is an upper bound rather than a finding.

Mobile is therefore marked **PARTIALLY AUDITED**, with re-verification
listed as an explicit task in #45B. `/housing` was measured properly at
390px during #45 and is fine; the other six surfaces are assumed, and
the artifact says so rather than implying a pass.

`Ask MacroChipz` reports `NOT_CONFIGURED` here, so its populated
experience could not be audited at all. Also stated rather than
smoothed over.

### Lesson

**A product audit that reads source code will describe the product the
team believes it shipped.** The link graph disagreed with the component
tree in three places, and every disagreement was a capability that
exists in the codebase and cannot be reached from the front door.

The narrower version, which I expect to keep applying: **the homepage is
not a design surface, it is a projection of what the database contains.**
Nobody made a decision to lead with bond yields. It is what 0.3%
eligibility produces, and no amount of copywriting would have fixed it.

## Increment #45B — Product Cohesion

Implementation. Baseline: HEAD `2fdde80` (#45A's audit), clean tree.
Requirements source: the #45A audit, treated as a specification rather
than as advice. 1,844 frontend tests and 2,494 backend tests pass;
nothing committed, nothing pushed.

Spec first, as instructed:
`docs/product/macrochipz-product-cohesion-v45b-spec.md` maps each audit
finding to a fix, acceptance criteria and tests, and now carries the
outcome including two deviations from itself.

### The finding that decided the shape of the increment

#45A measured 1,899 intelligence objects, of which **six are
homepage-eligible and all six are Treasury yields**. The obvious move
is to widen eligibility. It is also the wrong one: the policy excludes
1,532 coverage records and 358 first observations, and every one of
those exclusions is correct. The homepage was an accurate projection of
a database whose only *changes* live in one world.

So `homepage_presentation_v1.0` is untouched, and the homepage gained a
second layer that makes a **different claim**:

    THE LEDE       "this CHANGED"                  governed by the policy
    ORIENTATION    "these EXIST, and here is the
                    latest data on file"           governed by the registry

Keeping those apart is the whole design. Orientation carries no change
language, no direction, no significance and no state — a test asserts
all four. It deliberately does **not** repeat Inflation's and Jobs'
state badges either, because `CurrentStateSection` already publishes
those with a "Why Mixed?" explanation, and two surfaces responsible for
one fact is the duplication #45A itself flagged.

### Three guards told me I was wrong, and all three were right

**The publication-language guard.** The homepage forbids
"published"/"released"/"data available" outside one sanctioned
disclosure, because a "Past due" badge beside that word reads as a
claim the data arrived. My new copy said "revised after it is first
published" — true, general, and nowhere near a release row. The guard
cannot tell the difference and should not have to. **The copy changed,
not the guard.**

**The analytics-abstraction guard.** `ShareButton` needed the
`ObjectType` union and I imported `analytics/events` directly. The
guard forbids reaching past the `analytics` barrel. My first instinct
was "it is only a type". The barrel already re-exports it, so the right
fix took one line and the guard kept its teeth.

**The Overview read-only guard.** Adding `getHousing` to the homepage
tripped an allow-list of documented read functions. That allow-list *is*
the mechanism — `listHomepageIntelligence` and `useSinceLastVisit` were
added the same way — so the fix was to document the addition, with the
reason it is a read.

Three for three. The pattern worth keeping: **when a guard fires on new
work, the default assumption should be that the guard is right.**

### A frozen rule I changed on purpose

`overview-attention-model-v1.md` §17 froze "a non-monitor release's
next action is `/releases`". On `/calendar` that is circular, so #22B
implemented it as *no CTA at all on `/calendar`* — sound reasoning, and
the direct cause of #45A measuring `/calendar` as the product's only
page with zero outbound links.

I changed the unconditional half of the rule and wrote a §17 addendum
into the frozen document explaining what changed and why. The
replacement is better than either option the original considered:
pointing a reader at the page they are already on was never a *next
action*, it was the absence of one wearing a link's clothing. A release
whose series feed nothing now says **"Not tracked by MacroChipz yet —
the schedule only"**, which also answers the separate #45A finding that
the Calendar was advertising GDP and retail sales the product does not
have.

§3A's correction is untouched: navigation still keys off canonical
monitor relation, and JOLTS still gets no Jobs attribution — it now
gets no link at all, which is a stronger reading of §3A rather than a
weaker one.

Updating a freeze deliberately and recording it is fine. Editing one
quietly because a test is in the way is not, and the difference is a
paragraph in the document that owns the rule.

### The frozen sentence I nearly edited

Provenance had to leave the calendar rows — the literal word "FRED" was
consumer-facing jargon on the most consumer-facing schedule surface in
the product. I moved it into `ReleaseScheduleDisclosure` by appending a
sentence, and a test failed on an exact-text match.

That test was protecting a sentence `release-intelligence-v1.md` #2/#13
makes load-bearing: *a scheduled date is not proof of publication.*
Appending to it was editing frozen copy. The corrected implementation
renders the frozen sentence unchanged in its own element with the
provenance line beside it, and a new test asserts the frozen sentence
byte-for-byte so the next person cannot do what I just tried.

### What only the browser found

A test-failure message dumped the rendered page text, and buried in it
was the footer of `IntelligenceShell` — which permanent object pages
and explainers use instead of `AppShell`. It read *"Source data: U.S.
Department of the Treasury; FRED®"* and nothing else.

#45 added the required Census non-endorsement notice to `AppShell`
only. So the two shells had drifted, and the pages **most likely to be
someone's first and only view of MacroChipz** — a shared explainer, a
permanent object from a message — were the ones carrying no Census
notice. Census's terms require it to be displayed. Fixed with the
identical verbatim sentence.

Two shells and one attribution obligation is a standing hazard, and it
is now two places that must agree rather than one that must be right.

### Measured, before and after

Same method as #45A: rendered DOM, live backend.

| | before | after |
|---|---|---|
| `/` internal links | 9 | **15** |
| `/` worlds linked | 3 (no Housing) | **4** |
| `/` → explainers | 0 | **4** |
| `/calendar` outbound links | **0** | **2** |
| Worlds linking to `/revisions` | 2 of 4 | **4 of 4** |
| `/explain` | did not exist | **16 links, all 12 explainers** |
| Frontend tests | 1,795 | **1,844** |
| Prerendered pages | 18 | **19** |
| Client JS (gzip) | 166,611 B | 169,083 B (**+2,472**) |

Backend: **2,494 passed, 2 skipped** — unchanged, which was the point.
Typecheck, lint and build clean.

### What I could not verify, again

The browser tooling reports a successful window resize while media
queries go on matching desktop, so **mobile is still unverified at a
real viewport** — the same limitation #45A hit, now costing a second
increment. I added structural assertions instead (no fixed pixel
widths, mobile-first grid), which catch the defect class that actually
breaks phone layouts, and said plainly in both the artifact and here
that a genuine 390px pass across eight surfaces is outstanding.

`Ask MacroChipz` is still `NOT_CONFIGURED` in this environment. Its
honest unavailable state renders — *"MacroChipz Analyst is
unavailable."*, no input control — and its populated state remains
untested. Nothing about it was widened.

### Lesson

**An audit is only worth the increment that acts on it**, and the
acting is where the audit gets tested. Three of #45A's findings turned
out to have a frozen decision sitting underneath them, and in each case
the right move was different: one contract to update deliberately
(§17), one to leave exactly alone and work around (the schedule
sentence), and one where the label was wrong but the constraint beneath
it was right ("How They Relate" → "Inflation and Jobs, side by side").

None of those distinctions is visible from the audit. They only appear
when you try to change the code and something pushes back.

## Increment #46A — Follow & Brief Specification

Research and specification. No production code, no migration, no email
integration, nothing committed. Baseline: HEAD `bf5f7d9` (#45B).

Artifact: `docs/product/macrochipz-follow-brief-v46a-spec.md`.

### One query decided the increment

Before writing anything I asked the development database what could
actually trigger a notification today:

    prospective revisions ever captured ....................... 0
    observation versions, all backfilled ...................... 5,716
    analysis updates, AVAILABILITY_RESTORED (coverage) ........ 1,488
    analysis updates, CONFIRMATION_CHANGED (UNAVAILABLE -> x) .. 44
    release check runs ever executed .......................... 3

**MacroChipz currently has zero communication-eligible events.** Not
few. Zero.

That single fact answers the question the increment was really asked —
should Follow ship first — and it answers it against the roadmap's own
expectation. **An event-triggered Follow shipped today would send
nothing, to anyone, indefinitely.** You would ship a subscribe button
that promises notifications and then deliver silence, burning the one
signup a reader will ever give you.

So the recommendation is a **manually reviewed weekly Brief first**,
with Follow sequenced behind the first real prospective revision — the
event that both justifies an alert and makes the moat demonstrable.

What makes that recommendation hold rather than merely sound cautious
is that the product reasoning reached it independently: four of the five
return scenarios in §A point at a periodic Brief, and the one that
points at an alert (A3, "the number changed after they published it?")
depends on the event that has never occurred.

### Two blockers I found rather than assumed

**MacroChipz has never been deployed.** The journal's increment sequence
goes #26E → #27B. #26F was a research and contract freeze; #26G
(infrastructure), #26H (bootstrap and scheduler activation) and #26I
never ran. There is no production environment, no domain, no sending
identity. I had been about to write a delivery architecture for a
product with nowhere to send from.

**Automated sending inherits a blocker this project has already
declined twice.** ADR-029 defers scheduler activation and names the
reason exactly — it needs "a real, network-reachable production database
and an explicit, reviewed answer to whether a scheduler can reach it
without weakening its own access controls." A `.disabled` workflow
exists specifically so it cannot execute.

A human pressing send needs neither. That turned editorial review from a
temporary crutch into a design that **routes around a real blocker** —
and it is the second independent reason the Brief precedes Follow.

### The licensing problem nobody had to look for

Inflation and Jobs figures come from FRED. #28 recorded two unresolved
FRED terms: apps may not "replicate or attempt to replace the essential
user experience of the FRED® API" (rated High), and "individual users
of an application must use their own API key" (Medium-High, **UNKNOWN —
REQUIRES VERIFICATION**).

A newsletter is a **new distribution channel** for that data. It
sharpens the question rather than softening it, and it is the kind of
thing that is much cheaper to notice in a specification than in a
sent email.

Three ways out, in preference order: complete the #M2 migration and
source CPI/PCE direct from BLS and BEA (both public domain, and what
#28 and #45A have now both recommended); or ship the first Brief with
Rates and Housing figures only, limiting Inflation and Jobs to state
labels and links; or obtain written clarification. **Recorded as a
launch dependency, not a footnote.**

### The eligibility contract, and why it cannot be THE LEDE's

`homepage_presentation_v1.0` answers "what should we show first?" — a
selection among things a reader came to look at. Notification
eligibility answers "is this worth interrupting someone who did not
ask?" That is a categorically higher bar, and sharing a rule set would
fail in a specific, predictable way: **if the homepage ever needed more
content, the pressure would land on a shared policy, and a homepage
change would silently start sending email.**

So `communication_eligibility_v1` is separate, and frozen as a **strict
subset** — never a superset, never an overlap with exceptions. An object
that may not appear on the homepage may never be emailed, and a test
should assert the subset relation directly.

The other property that matters: the lede always picks *something* when
anything qualifies. A communication policy must be able to pick
**nothing, indefinitely, and have that be a success state**. Given §0.1,
it will be doing exactly that for a while.

### The architectural idea I did not expect to need

Intelligence objects are generated on read and are *supposed* to change
when data is revised — that is the feature (#39). An email is the
opposite: once sent, what it said is fixed forever, and the data it
quoted may since have moved.

So a `BriefEdition` has to be **persisted and immutable** — the first
thing in this system that must be. Regenerating one later would produce
a different Brief, which is precisely why it cannot be regenerated.

It is #31's current-state-cache versus system-time-history distinction
applied one layer up, and it makes "what did we tell people, and was it
right?" answerable. A product built on provenance ought to be able to
answer that about its own output, and until now it could not have.

A corollary fell out of it: a revision arriving after a Brief ships is
**new content for the next edition, never a silent edit of the last**.
If an edition was materially wrong, the correction is its own edition
saying so — the discipline `/revisions` applies to economic data,
applied to MacroChipz's own.

### Where I argued myself out of AI

The plausible use was drafting the one-sentence summary of a change from
structured fields. I talked myself into it and then back out, because
that sentence is a template over fields the system already has — *"Core
PCE momentum moved from X to Y for {period}"* — and a template is
deterministic, reviewable and cannot hallucinate a number. The
generative version buys a dependency, a cost, a latency and a whole
class of failure in exchange for prose an f-string produces correctly.

The stronger argument is #44's: the explainer layer's value is that
every sentence was written and reviewed. A Brief carrying one generated
sentence forfeits exactly the property that distinguishes it.

### On measurement, and one thing I refused

`follow_signup: { target: World | "all" }` has been sitting in #37's
vocabulary since it was written, marked "RESERVED — not emitted today.
Follow/email does not exist yet (Increment #46)." It needs activating,
not designing. That is what a closed vocabulary written with the next
increment in mind buys you.

The refusal: **no open tracking.** An open pixel measures whether an
image loaded, which proxy prefetching has been steadily making
meaningless anyway — and a tracking pixel in a product built on
provenance is a poor trade for a number that was never the real
question. The metric that matters is whether someone came back and read
something, and `page_viewed` already answers it.

`product-measurement.md` §6 prohibits collecting email addresses. That
prohibition stands unchanged: subscriber data lives in MacroChipz's own
database, analytics receives counts and world ids, and nothing crosses.

### Lesson

**Ask the database what the feature would actually do before designing
it.** The roadmap said Follow next, the audit said RETURN was the
broken stage, and both were right — and a feature built on that alone
would have shipped a promise the data cannot keep for months.

The narrower version, which I suspect generalises past this increment:
**a push feature is only as good as its worst week**, and this product's
worst week is currently every week. Designing for the quiet case first
produced a better product than designing for the eventful one and
handling quiet as an exception.

## Increment #46B — Deployment & Launch Blockers

Research, architecture and specification. No infrastructure provisioned,
no service purchased, no credential configured, no migration run, no
production code modified, nothing committed. Baseline: HEAD `d8ea5a8`
(#46A).

Artifact: `docs/architecture/macrochipz-deployment-launch-plan-v46b.md`.

### Verifying rather than assuming, in both directions

The instruction was not to assume an earlier deployment increment had
completed merely because it was planned. That turned out to cut both
ways, which I had not expected.

**Against the plan:** there is no `render.yaml` and no
infrastructure-as-code of any kind. #26F was a contract freeze; #26G,
#26H and #26I never ran. Nothing has ever been deployed.

**For the plan:** #26F recorded that the Dockerfile "hardcodes port
8000 and never reads Render's own `PORT`", naming it a required fix for
#26G. It reads `$PORT` today, at line 109. Somewhere between then and
now it was fixed, and the record still says it is outstanding.

Both directions are worth the same amount. A stale blocker costs you a
task you do not need to do; a stale completion costs you a task you
think is done.

### The free tier is disqualified on architecture, not price

The instruction says not to choose a provider on its free tier alone. On
this stack the stronger statement holds: **Render's free tier is
incompatible with what MacroChipz is**, and the reason is not cost.

Free Render Postgres **expires 30 days after creation**, gets a 14-day
grace period, and is then deleted with all its data. MacroChipz's entire
differentiator is `observation_versions` — the append-only record of
what it knew and when. A database that silently self-destructs monthly
destroys precisely the asset the product is built on.

Two more, either of which would be sufficient alone: free plans support
no pre-deploy commands, so the migration release process #26D built has
nowhere to run under #26F's exact-revision compatibility policy; and
free web services spin down after 15 minutes with a ~1 minute cold
start, so the first visitor from a shared link waits a minute for a page
that then fires five API calls.

The paid entry tiers are $7 and $6. **The whole platform is ≈$14/month**
— Render's own published example for the same shape says ~$13. The free
tier was never worth its constraints.

### A deployment ordering constraint nobody has hit yet

`prerenderPaths.ts` fetches `/api/v1/intelligence` **at build time** to
decide which permanent object pages to prerender. Unset
`VITE_API_BASE_URL` and it prerenders none, silently, and the build
succeeds.

So **the API must be deployed and reachable before the frontend can be
built with object pages** — API first, then frontend, on the very first
deploy. And the consequence is not cosmetic: permanent objects are the
SHARE stage, and without prerendering a shared link hands a social
crawler an application shell with no title, description or image. #40
built those pages specifically to survive leaving MacroChipz, and one
unset build variable undoes it silently.

### Two defects found by reading the files

**`robots.txt` has a relative sitemap directive.** It says `Sitemap:
/sitemap.xml`; the directive requires an absolute URL, so crawlers may
ignore it entirely. It has been wrong since #40 and no test covers it,
because it is a static file nothing asserts against.

**`/revisions` is neither prerendered nor in the sitemap.** It is a real
public route carrying what #45A called the strongest single piece of
writing in the product, it is now linked from all four worlds and the
homepage after #45B — and it is invisible to crawlers and unfurls. One
line in `STATIC_PATHS` fixes it.

Neither was found by thinking about deployment. Both were found by
opening the files that deployment would serve.

### The expensive endpoint nobody is guarding

`GET /api/v1/intelligence` is public, unauthenticated, rate-limited by
nothing, and regenerates all 1,899 objects on every call — 42 queries,
~194 ms, 138 KB. The homepage calls it on every load.

The only rate limiter in the product guards `POST /analyst/explain`. On
a $7 instance with 5 GB of included bandwidth, a trivial loop against
that endpoint is a cost-and-availability amplifier. **Recorded as a
launch blocker rather than a hardening nicety**, which is a judgement
call I would rather make now than after a bill.

### The licensing question, stated as a question

The rule I held to: **permission for one activity is never inferred from
permission for another.** API access does not imply redistribution;
website display does not imply email redistribution.

But one inference does hold, and stating it precisely was most of the
work: for a **public-domain U.S. Government work**, the data carries no
copyright, so the channel is not itself a copyright question. What
travels with it is the terms of the *API used to obtain it*, plus
attribution obligations that are contractual rather than copyright.

That distinction resolves the shape of the problem. **All six
FRED-dependent concepts are BLS or BEA public-domain works that FRED
merely redistributes.** MacroChipz needs nothing proprietary to FRED —
it needs a different pipe to the same public data, which is exactly what
#28 recommended and the #M1–#M4 track already plans.

And it produces a sequencing answer I did not anticipate: **FRED blocks
the Brief, not the website.** A public site showing FRED-derived figures
is the status quo, carrying the same rated risk it has carried since
#29. Pushing those figures into email is the new act. So the website can
launch with the question open; the first Brief cannot print an inflation
figure until #M2/#M3 land, or must scope around it.

What I did **not** do: contact the St. Louis Fed, obtain clarification,
or re-read FRED's terms to see whether they changed. Each is real; none
is engineering's to do alone. §D.3 says so.

### Diagnosing the mobile failure instead of retrying it

The 390px verification failed in #45A and again in #45B, both times with
the same signature: `resize_window` reports success, then the page says
`innerWidth: 1719` and `matchMedia('(min-width: 640px)')` is still true.
One reading had `outerWidth: 686` alongside `innerWidth: 1719`, which is
internally inconsistent.

**It is not a flaky tool. It is the wrong mechanism.** Resizing an OS
window is not device emulation. Emulation overrides the layout viewport,
device pixel ratio, user agent and touch capability together; a window
resize changes the window and may leave the layout viewport alone —
under page zoom, a DPR of 2, or a maximised window state. Media queries
key off the layout viewport, so nothing that matters changed.

A third attempt would have produced the same non-result. What the plan
specifies instead is DevTools device emulation or a real phone, plus a
**confirmation gate that must pass before any mobile claim is made**:
`innerWidth === 390` *and* `matchMedia('(min-width: 640px)') === false`.
Both. Neither previous increment could produce that pair, and both said
so rather than claiming a pass — which is the only reason this is a
diagnosable problem rather than a false belief.

### Recommending against a feature I built around

The Analyst recommendation is Option B: launch without it.

It is the product's **only unbounded cost**, at exactly the moment cost
predictability matters most. Its populated state has **never been tested
anywhere** — not in this environment, not in any. And #45A already
measured it as barely discoverable: three pages, below the fold, absent
from Housing by design.

The uncomfortable corollary, which I included because leaving it out
would make the recommendation look cheaper than it is: if it does not
launch, the section should be **removed** from the three world pages
rather than shipped as a permanently-unavailable heading. An unavailable
feature advertised in three places is worse than an absent one.

### Lesson

**A deployment plan is mostly an inventory, and an inventory is only
worth the reading it is based on.** Every genuinely useful finding here
came from opening a file rather than reasoning about the system:
`robots.txt` had been wrong since #40, the Dockerfile fix had quietly
been done, `/revisions` had never been added to the prerender list, and
the build-time API dependency had been sitting in `prerenderPaths.ts`
with its consequences documented and unconnected to deployment order.

None of those would have surfaced from the architecture documents, all
of which are accurate. They describe what the system is *for*. Only the
files say what it currently *does*.

---

## Increment #46C — Consumer Experience & Visual Direction

Product design plus one bounded working prototype. Nothing committed,
nothing pushed, nothing deployed, no `.env` value read. Baseline: HEAD
`937dc1d` (#46B).

Artifact: `docs/product/macrochipz-consumer-experience-v46c.md`.
Prototype: `/story/fed-and-mortgage-rates`.

### Three increments of mobile findings were measuring the wrong thing

#45A and #45B both audited "mobile" and both carried a caveat: the tool
reported the window resize as successful, and `matchMedia('(min-width:
640px)')` kept answering `true` anyway. Every Tailwind `sm:` style was
still applied. Those audits were describing a narrow desktop window,
which is a layout no phone renders.

#46B worked out why — resizing a window is not device emulation, and
nothing in that path tells the page its viewport changed. #46C worked
out the fix, which turned out to be four lines: **a same-origin iframe
has its own viewport, and media queries inside it resolve against the
iframe's width.**

```js
const frame = document.createElement('iframe');
frame.style.cssText = 'position:fixed;left:0;top:0;width:390px;height:844px;border:0';
frame.src = '/story/fed-and-mortgage-rates';
// contentWindow.innerWidth                              -> 390
// contentWindow.matchMedia('(min-width:640px)').matches -> false
```

Every measurement in this increment was taken with that gate passing.
It is the first genuinely mobile measurement this product has had.

What it found was not what the earlier audits implied. **The layout is
sound** — zero horizontal overflow on all ten surfaces, which is not
typical. **The touch layer is not**: `/calendar` has 45 controls of
which all 45 are under 44px and 43 are under 24px, `/rates` has 40 of
46, and the recurring offender is `ExplanationTrigger` at **16 × 16 px**
— the primary discovery affordance for the best content in the product.

The lesson I want to keep is narrower than "verify your tools". It is
that **a measurement tool reporting success is not evidence that it
measured anything.** `resize_window` returned `{success: true}` three
increments running. The only thing that caught it was asserting on a
property of the page itself rather than on the tool's own report.

### The interaction had to teach, which ruled out most interactions

The brief was explicit that decorative animation would not count. So the
design question was: what can a reader *do* that changes what they
understand?

What made it answerable was noticing that the misconception is not a gap
in knowledge. Nobody wonders who sets mortgage rates; they are confident
the Fed does. **Reading a correction does very little to a confident
belief.** Being asked to commit to it first does considerably more.

So the interaction is four rates and one question — which one does the
Fed actually set? — with nothing revealed until the reader picks. A
reader who picks "your 30-year mortgage rate" has performed the
misconception on themselves, which is a much better setup for the
correction than a paragraph asserting that people commonly believe it.

The constraint that shaped it most was what it had to refuse. No
quantified Fed-to-mortgage relationship — no direction, no magnitude, no
timescale — because the explainer's declared basis is
`INSTITUTIONAL_ROLE` and *who sets what* is the only thing that basis
supports. No score and no streak, because being wrong is the normal case
and the entire point. No live data, which is why the whole route
prerenders and has nothing that can fail.

One precision mattered enough to change the copy: the Fed does not set
*the* federal funds rate, the FOMC sets a **target range**. Writing it
the loose way would have been the same species of imprecision the page
exists to correct.

### The second interaction is weaker, and the code says so

The influence explorer is progressive disclosure. It does not change
what a reader believes; it changes how much they read at once. That is a
comprehension gain on a small screen, not a teaching mechanism, and both
the component docstring and the design document say so rather than
counting it as a second win.

It keeps #44's actual argument intact — all four influences and the
convergence line are visible with zero interaction, so the shape (things
converging, Fed policy one of them, not a chain) survives for a reader
who taps nothing.

### The prototype's own tests caught the prototype twice

Both worth recording because in both cases the right move was to change
the code rather than the guard.

The tap-target guard failed on an inline `<Link>` in the closing
footnote. It would have been easy to add an exception for inline prose
links. The guard was right: the link moved onto its own line as a 44px
target.

Then an earlier version of that same guard read the source with a regex
that stopped at the first `>` — which `onClick={() => …}` contains — and
so failed a control that was in fact 56px tall. That one *was* the
guard's fault, and the fix was to stop regexing JSX and assert on the
rendered tree instead.

### Prerendering and indexing turn out to be different decisions

The story is static, so it should prerender with real content like an
explainer. But it is a prototype of a page that already exists, so it
must not compete with it: it ships `robots: noindex` and a canonical
pointing at `/explain/fed-and-mortgage-rates`.

Those two facts collided in `generate-sitemap.mjs`, which since #40 has
listed exactly what was prerendered — a good rule that had never had to
distinguish the two. A sitemap entry plus a `noindex` meta gives a
crawler two contradictory instructions about one URL. The fix reads each
built page's own HTML and excludes any that declare `noindex`, so the
sitemap cannot drift from what the pages actually say.

### An early exit had been hiding a whole verification suite

`verify-build-output.mjs` used to `process.exit(0)` when no intelligence
pages had been prerendered — which is the normal local and frontend-CI
build. The #44 explainer checks live below that line. They had been
silently skipped in that build since they were written.

I only found it because I added story checks to the same file and they
did not run. That is the second time this increment that something
reported success while doing nothing.

### What I deliberately did not do

The design document proposes a direction; it did not get applied
anywhere. Eleven explainers still have no story, `/calendar` still has
45 undersized controls, and `ExplanationTrigger` is still 16px. The
brief said not to proceed to the application-wide redesign without
review, and the touch-target work is the largest measured defect in the
product, so §H proposes it as #46D's first item — explicitly worth
shipping **even if the story format is rejected**.

The evaluation section says the prototype is **34% longer** than the
explainer it reimagines, and lists six hypotheses the increment did not
test. Building something is not evidence that it works, and the
comparison is available whenever there is traffic to compare, because
both routes exist independently.

### Lesson

**Two different things reported success while doing nothing this
increment** — `resize_window` for three increments, and a build verifier
that exited before its own checks. Both were caught the same way: by
asserting on a property of the artifact rather than on the report of the
thing that produced it. A tool's own success message is the weakest
evidence available, and it is the evidence that is hardest to stop
trusting, because it is right most of the time.

---

## Increment #46E — Rate Network Story

The approved luminous visual direction, made functional. One interactive
economic network at `/story/fed-and-mortgage-rates`, replacing #46C's
scrolling article-with-a-quiz at the same URL. Nothing committed,
nothing deployed, no `.env` value read. Baseline: HEAD `937dc1d`.

Specification written before code:
`docs/product/macrochipz-rate-network-v46e-spec.md`.

### The decision that made everything else easy

**Visuals are SVG. Interaction is HTML.**

The SVG draws the field, halos, edges and node cores and is
`aria-hidden` — it is a picture. Every node is an absolutely positioned
HTML `<button>` layered over it at the same percentage coordinates.

Three problems disappeared at once. Tap targets stopped depending on SVG
scale, which is the defect #46D shipped: 48 user units looked like 48
pixels, but a scaled `viewBox` makes a user unit a RATIO, and the
controls rendered at 41px. A button with `min-h-11` cannot be shrunk by
a viewBox. Accessibility came from the platform — focus ring, tab order,
Enter/Space, `aria-pressed` and an accessible name are native to
`<button>` and all four are subtly wrong when hand-built on an SVG
`role="button"`. And the behaviour became testable, because jsdom has no
layout engine, so every assertion about SVG geometry there is theatre
while button semantics are fully assertable.

The measured result: six buttons, every one exactly 44px tall, every one
inside the board, at a verified 390px.

### Two SVG unit traps, and why one edge kept vanishing

During visual exploration the Federal-Reserve-to-federal-funds edge —
the single most important relationship on the page — rendered as nothing
twice, for two independent reasons with the same root.

`filter` and gradients both default to `objectBoundingBox` units. That
edge is perfectly vertical, so its bounding box has **zero width**. A
gradient in bounding-box units is not rendered at all on a zero-area
box, and a filter region of 340% of zero is zero.

The fixes are `gradientUnits="userSpaceOnUse"` and glow from stacked
strokes rather than a blur filter. Both are now guarded by test, because
this is not the kind of thing anyone re-derives when they next touch the
file.

### The traceability rule

A diagram is an easy place to smuggle in a claim. An edge looks like a
fact, and a confident sentence under a glowing node looks reviewed
whether or not it is. So the registry holds a mechanical rule:

> every user-visible sentence about the economy must be a **contiguous
> substring** of a string that was already reviewed.

Trimming a clause is allowed — deleting words cannot add a claim.
Rewording is not, because it can. `rateNetwork.test.ts` checks every
node's role against the #44 registry entry and the #46C copy, and the
first entries are pulled live from the registry so that editing #44
fails this suite rather than silently drifting.

**Edges carry no prose at all** — a `kind` and two endpoints, nothing
else. A test asserts the object has exactly three keys. An edge with a
description is an edge that can acquire a claim.

### One edge deliberately not drawn

The approved mockup drew `federal funds rate → Treasury yields`. The
implementation does not, and a test asserts its absence.

The reviewed copy routes the Fed's effect on long-term rates through
*expectations* — "that decision ripples through what investors expect
for the future" — not through the funds rate itself. Drawing the
shortcut would have asserted a mechanism the sources do not. It is the
one place where matching the approved visual would have cost accuracy,
and accuracy won.

What survived is better anyway: **two direct edges at opposite ends of
the graph with nothing but influence between them.** That shape is the
explanation, which is why the legend is not decoration.

### Fitting a panel under a diagram

The brief allowed a bottom sheet. A sheet was rejected because it
overlays the bottom of the viewport, which at 390px is exactly where the
lower half of the diagram lives — so the thing describing a node would
cover the node.

Putting the panel under the diagram instead meant both had to fit above
844px, and the first build missed by 157px. The board was the biggest
line item: 4:5 at full width is 447px of a 844px screen. Compressing it
to square and capping it at 330px on a phone bought 117px, and trimming
type and padding found the rest. Worst case across all six selections is
now 841px, measured per node rather than assumed from one.

The panel also carries a `min-height` floor, so switching between a long
role and a short one does not shunt the rest of the page up and down on
every tap.

### The absence is the finding

Four of the six nodes have no setter. `NodePanel` states that in words —
"Nobody sets it / it is priced in a market" — rather than leaving a
missing row, because for this story the absence of an authority IS the
substantive claim. A registry test asserts that the only two nodes
naming a setter are the two that are the target of a `sets` edge, so the
words and the picture cannot disagree.

### A Constitution tension recorded rather than resolved

§19.1 requires every explainer to bind at least one claim to a live
MacroChipz figure. This route embeds none — #44 made that choice for the
canonical explainer and #46C kept it, because a page with no data cannot
fail and prerenders whole.

The required movement (CONCEPT → CURRENT DATA → RELATED WORLD →
EVIDENCE) is satisfied by landing the reader on `/rates` and `/housing`.
That is satisfaction by navigation rather than by embedding, which is a
narrower reading than the rule as written. Written down in the spec
§3.6 and flagged here rather than quietly assumed.

Similarly §23 wants an as-of date on every share card. This card carries
no figure, so nothing on it can go stale; it says "institutional roles,
not market data" where the date would go. The rule is not waived, it is
inapplicable — and the moment the card carries a number it needs one.

### Results

1,913 tests across 78 files, typecheck, lint and production build all
pass. 64 of those tests are new. The story chunk is 6.5 KB gzipped and
adds no dependency. Prerendered HTML carries 3,710 characters of text,
six node buttons and the default panel without JavaScript.

One flake seen once in `Home.test.tsx`, a file this increment did not
touch; it passed in isolation and in three consecutive full runs
afterwards. Recorded rather than dismissed.

### Lesson

**The same bug class has now cost three increments: a measurement that
looks like a measurement but is a ratio.** `resize_window` reported
success while the viewport never changed. SVG user units looked like
pixels and shipped 41px controls. A gradient and a filter in
bounding-box units looked like geometry and rendered nothing on a
zero-width box.

Every one was caught the same way — by measuring the rendered artifact
rather than trusting the declaration that produced it. The fix that
generalises is not "remember these three"; it is that anything whose
units are relative to something else should be asserted against the
thing it actually rendered to.

---

## Increment #46E-R — Responsive refinement

A measured pass over the rate network at 390px, 440px and under browser
zoom. No visual identity change, no economic change, no architecture
change. Nothing committed.

### Three defects behind a green check

The first implementation reported **zero horizontal overflow at every
width**, and I took that as evidence the layout was sound. It was
evidence of nothing: `scrollWidth` measures how wide the document is, and
one control sitting on top of another does not make a document any wider.

Measuring the rendered box of each of the six node controls instead found
an overlap at every width, a chip hanging outside the diagram at 320px,
and 110px of a 440px screen left unused.

### The overlap was arithmetic

Nodes sat at 11/25/39/58/70/91 percent. Two of them are twelve points
apart; on a 330px board that is 40px, and each chip is a 44px tap target.
So two controls overlapped by 5px on every single render, and the gap
shrank as the board did — at 320px three pairs collided.

Even 16.8-point spacing makes the minimum separation
`0.168 x boardWidth`, which clears 44px for any board at least 262px
wide. The test asserts that arithmetic rather than a screenshot, so it
cannot regress when someone nudges a node by a point.

### The clipping was two numbers that disagreed

A chip is translated 14px away from its dot, and its `maxWidth` allowed a
flat 2% of the board. Two percent is less than 14px on anything under
700px wide, so the longest chip hung 8px outside the diagram at 320px.
`maxWidth` now uses `calc()` with the same 14px the transform uses — one
number, referenced twice, instead of two numbers that happened to agree
at one width.

### The cap that fixed one thing and caused another

The 330px phone cap existed to keep the selected-node panel above the
fold. It also made the board short, which is what pushed the chips close
enough together to overlap. Removing it fixed both, because on a square
board width *is* vertical room.

The cost came due elsewhere: a bigger board pushes the panel down. The
intro was compacted to one line carrying the tap affordance, and the
connection lists moved behind a `<details>` — leaving the role and the
"who sets it" claim always visible, which is what a reader needs
immediately after tapping, and folding away the part the diagram already
shows by highlighting.

### What is still not true

At 440px the whole panel does not fit above the fold; the explanation
(ends 750px) and the setter claim (819px) do, and the collapsed
`Connections` toggle is what crosses it. And below about 309px CSS width
the overlap returns — 312px is clean at 45px separation, 294px collides
at 41px, which is a 390px phone past roughly 125% zoom.

Both are written down in the spec with their measurements rather than
rounded off. The zoom floor needs a single-column reflow, which is a
layout mode and not a tweak, so it is proposed rather than smuggled in.

### Lesson

**A passing check is only worth the thing it measures.** `scrollWidth`
was a real measurement, taken correctly, of the wrong quantity — and it
stayed green through an overlap that had been there since the first
render. The useful habit is not "measure more", it is to ask what the
metric would look like if the defect were present. Overlap does not widen
a document, so a width check could never have found it.

---

## Increment #46E-S — Narrow-screen fallback

The last piece of the rate network's responsive work: a single-column
layout below the width at which six 44px controls can no longer avoid
each other. Bounded, no redesign, nothing committed.

### The breakpoint was calculated and then confirmed

Six chips, 44px tall, 16.8 percentage points apart on a board that is
the column minus a constant 47px gutter:

    0.168 x (viewport - 47) >= 44   =>   viewport >= 308.9px

Measured rather than trusted: 312px clean at 45px of separation, 294px
collides at 41px. The switch sits at 312px — three pixels of margin, and
the chips truncate so a larger user font cannot wrap them onto a second
line and quietly raise the floor underneath the breakpoint.

That is the difference from the earlier passes in this increment. The
number is not a round device width someone liked; it is the point where
an inequality stops holding, and the inequality is asserted by a test.

### The fallback is CSS, and that is the whole trick

The same six buttons, in the same DOM order, stop being absolutely
positioned and become a flex column. The SVG hides and connector rows
take its place.

No second set of controls to keep in sync, no `matchMedia` in React, no
measurement, and therefore nothing that can mismatch between the
prerender and the browser. Positions moved from inline `style` into CSS
custom properties so a media query could override them — which is the
only reason a pure-CSS switch was available at all.

### Where the column tells less than the truth, and how it says so

A column can only draw an edge between adjacent rows. Four of six
qualify; `fed-policy → treasury` and `treasury → lenders` skip a row and
are not drawn.

They are not lost: the panel's `Connections` disclosure lists every
relationship of the selected node at every width. And because a
connector is drawn only where an edge exists, adjacency without one
means "no relationship between these two" — which is true. The diagram
never implies an edge that is not there, which is the property that
mattered.

### A test I deleted on purpose

"Sides alternate" was belt-and-braces from the previous pass. It
conflicted with putting `fed-policy` and `fed-funds` on the same x so
their edge stays perfectly vertical, and verticality is worth more: a
vertical line has a zero-width bounding box, which is exactly the
geometry that makes a bbox-relative gradient or filter render nothing.
Keeping one vertical `sets` edge means that guard has a live example to
fail against instead of a rule nobody can trigger.

The even spacing, not the alternation, is what actually prevents
overlap — so the weaker rule went and a stronger one replaced it.

### Results

294 / 312 / 320 / 390 / 440px, all six selections at each, measuring
rendered control bounds: no overlaps, no clipping, no horizontal
overflow, nothing under 44px. At 294px the column keeps DOM order equal
to visual order, all six accurate `aria-label`s, focus on the activated
button, 33 animating elements all carrying the reduced-motion opt-out,
and all three disclosures.

1,917 tests across 78 files, typecheck, lint and build pass. Story chunk
6.7 KB gzipped, no new dependency.

### Lesson

**The good breakpoints are the ones you can derive.** Every previous
attempt in this increment picked a width because it was a common device
size, and each one either wasted space or broke somewhere nobody had
measured. This one comes out of an inequality between a tap-target
height and a percentage spacing — so it can be asserted in a unit test,
and it moves correctly on its own if either input ever changes.

---

## Increment #46F — Full-page responsive composition

#46E verified the network. This pass audited the page around it, and the
page was in worse shape than the component it contained. No visual
identity change, no economic change, nothing committed.

### The audit was the increment

Measured before touching anything, at five real CSS viewport widths. The
network passed everything — and the page it sat in never grew past
672px, so at 1440px there were **768 pixels of empty violet field** and
the interactive centrepiece was **31% of the viewport**.

Worse, the selected-node panel sat 650px down the page at every width
above the phone. A panel whose entire purpose is to be read immediately
after a tap was below the fold on a 13-inch laptop.

That is the kind of defect component-level verification cannot find. Every
#46E check was scoped to the board, and the board was fine.

### One grid, two behaviours

At `lg` the same DOM becomes two columns — diagram left, explanation
right, the explanation sticky so it stays in view while a reader
compares nodes. Below `lg` the grid is not a grid, and the block flow is
exactly the one verified at 294 to 440px. Nothing about the network's
geometry, spacing or tap targets changed on mobile, which was the
constraint worth protecting.

The measured effect at 1440px: board 448 to 608, board share 31% to 42%,
unused side space 768 to 288, panel top **650 to 173**.

### A screenshot lied and the measurements did not

The scaled whole-page capture at 1440px looked left-heavy, as though the
content were pinned to one side. It was not: the article spans 137 to
1289 in a 1440 viewport, centred with even gutters. The capture is
scaled by a CSS transform on the iframe, and reading composition off it
is exactly the mistake this increment has repeatedly punished.

Measure, then look. The screenshot is for judging design, not geometry.

### The one number that went the wrong way

Mobile page height rose 42px at 390px. The cause is copy the brief
required: the share card now states that image export and native image
sharing are not implemented, because neither is. Compacting the
canonical-link footer paid back about half.

That trade was taken deliberately and is written down rather than
averaged away. A claim the product cannot honour costs more than 42
pixels.

### Results

294 / 390 / 440 / 768 / 1024 / 1440px: zero horizontal overflow, zero
text clipping, no interactive target under 44px on this route, all six
selections correct at every width, keyboard and focus intact.

1,917 tests across 78 files, typecheck, lint and production build pass.
Story chunk 7.0 KB gzipped, stylesheet 9.5 KB, no new dependency.

### Lesson

**A verified component can sit inside an unverified page.** Everything
#46E measured was true and none of it was enough, because the questions
were all scoped to the board: is it overlapping, is it clipped, are the
targets big enough. Nobody asked what fraction of the screen it
occupied, or where the thing explaining it ended up.

The habit worth keeping is to measure the artifact the user actually
sees — the whole page at the whole width — and only then zoom in.

---

## Increment #46F-C — Page cleanup

Two bounded changes closing #46F: the upper page boundary, and removing
the share-card prototype from the story. Nothing committed.

### The boundary defect was the workaround

The story wrapped itself in `-mx-4 -my-6 px-4 pb-6 pt-4 sm:-mx-6` to make
a background escape `PageContainer`. `PageContainer` supplies the width
and the side gutters and **no vertical padding at all** — so `-my-6` had
nothing to cancel and simply pulled the violet field 24px up, through the
header's bottom border. The margin was not hiding the defect; it WAS the
defect.

It was also incomplete horizontally: the gutter is
`px-4 sm:px-6 lg:px-8` and the cancel stopped at `sm:-mx-6`, so from
`lg` up the surface sat 8px inside the gutter, aligned with nothing. And
it could never have reached the viewport edge regardless, because
`PageContainer` is capped at `max-w-app`.

The fix is a change of ownership rather than a change of numbers. A
full-width background belongs to the page, so `IntelligenceShell` now
takes a `surface` prop and puts it on `<main>` — which already spans the
full width and already starts exactly where the header ends. The route's
wrapper is a plain `<div>` with no margins at all.

Measured: `headerBottom === mainTop`, a 0px gap at 390px and 1440px, and
zero negative margins anywhere inside `main`. No `overflow: hidden`.

### Ending on an apology

The page used to close with a 9:16 preview of a share card, a note
saying no deployment origin was configured, and a second note saying
image export was not implemented. Three paragraphs explaining what the
product cannot do, in the last thing a reader sees.

All of it is gone. The story now ends on sources, related reading, the
Share button and the canonical link — things a reader can use. The
component is kept, unrendered, because its composition is the reviewed
one and it is what a real OG image generator should render when #48
builds one. Its guards still run against the file, so it cannot rot
quietly.

Page height fell from 2912 to 2294 at 390px, and the story chunk from
7.0 KB to 5.9 KB gzipped.

### The Share button was copying something useless

With no deployment origin configured it fell back to the bare path, so
the clipboard got `/story/fed-and-mortgage-rates`. That is not a
fabricated domain, but it is not a URL either.

It now falls back to the origin the page is actually served from, read
in the browser. Verified by intercepting the clipboard write rather than
by reading the code: it copies
`http://localhost:5193/story/fed-and-mortgage-rates` in dev. Honest, and
usable.

### Lesson

**A workaround that has outlived its reason looks exactly like a
feature.** `-my-6` had been on that element since the surface was
introduced, and every later pass measured around it — tap targets,
overlaps, breakpoints, column counts — without once asking what it was
cancelling. The answer was nothing. It had never cancelled anything.

Worth asking of any negative margin, any `overflow: hidden`, any `z-index`
above 1: what is this cancelling, and is that thing still there?

---

## #48 production preparation — verifying rights, and one figure

**2026-09-22.** Prototype only. No production route, component, dependency or
methodology touched.

### Three of four images could not be verified, and that is the result

The brief asked for verified federal public-domain imagery and was explicit
that hosting on a `.gov` domain proves nothing. That turned out to be the whole
exercise.

**One asset cleared the bar.** Carol M. Highsmith's photograph of the Treasury
building at the Library of Congress. The item's `rights_advisory` reads "No
known restrictions on publication." — but the Library also states it does not
own rights and that assessing them is the researcher's obligation, so the
advisory alone is not a commercial basis. What *is* one is the collection's own
sentence: the photographer dedicated the archive's rights to the American
people for copyright-free access. That is the sentence now on file.

**Three could not be.** The Highsmith archive is architecture and landscape,
not people at work or retail interiors; its steel-mill results are all *idle and
abandoned* plants, which on a Jobs tile would assert industrial decline — a
claim about the economy nothing in the product supports. The wider
no-known-restrictions pool is 1880–1950. A 1940 grocery photograph on a page
whose entire claim is *current, sourced* data misrepresents by context rather
than by caption.

So Inflation, Jobs and Housing keep marked placeholders. Deliberately: the
alternative was to make a pretty page out of four images whose provenance
nobody could state.

### The rule that came out of reviewing candidate images

Two of the four images supplied failed regardless of licence — one carried a
legible third-party trademark on a worker's shirt, another an identifiable face
with store signage. But the interesting one was subtler: **a shelf price tag,
legible in frame, on what would be the Inflation tile.**

Nobody would have written "tomatoes cost $1.49/lb" as copy. The photograph
says it anyway, in a product whose entire promise is that every figure traces
to the agency that published it. A figure that arrived through a photograph
has no such trace.

**New acceptance rule: no legible price, figure or date inside a photograph
unless we intend to stand behind it.**

### A truncated attribution is not an attribution

The on-tile credit was 7.5px with `white-space: nowrap; text-overflow: ellipsis`.
At 440px it rendered "Carol M. Highsmith Archive, Library of Congre…".

It measured clean — inside its frame, no overflow, no clipped *layout*. The
defect was only visible by reading the rendered pixels, because ellipsis is
what the CSS was *asked* to do. The chip is now 9px and wraps, and the full
required credit line is carried verbatim in the footer beside the Census
notice.

**An overflow check answers "did the box fit". It does not answer "is the
sentence still there".** For a legal notice those are different questions, and
only one of them matters.

### The figure was audited against a different endpoint

`5.01%` on `2026-09-18` was re-checked against
`/api/v1/series/UST_NOMINAL_10Y/observations` rather than the monitor the
snapshot came from — same claim, independent path. All four maturities match.
Re-reading a number from the source that produced it is not an audit.

### Lesson

**"No known restrictions" is a statement about what the archive knows, not a
licence.** The commercially usable fact was one sentence in the collection's
About page, not the field that looked like the answer. When a rights field
reads like permission, find the instrument that grants it.

---

## #48 production integration — the homepage, and three things only a measurement caught

**2026-09-22.** The Living Economy homepage shipped to `/`. 1,946 tests,
typecheck, lint and production build all pass. No canonical data, methodology
or source-licensing rule touched.

### The page now prerenders with its content

`/` used to prerender as an application shell — real `<title>`, empty body,
because every section fetched. The hero fetches nothing, so the static HTML now
carries **3,866 characters** of real text, the `<h1>`, all four worlds and the
Library of Congress credit line.

That was a side effect of the orientation-first rule, not a goal, and it is the
best argument for that rule: the same property that makes the page survive an
API outage makes it legible to a crawler.

### Three defects, none of which a screenshot would have shown

**1. The hero's lighting was invisible, and looked like a colour problem.**

It shipped as a `::before` on the hero at `z-index: -1`. Nothing appeared. The
temptation was to reach for the opacity.

The actual rule: a negative z-index child paints inside the nearest **stacking
context**, not inside its parent. Nothing between the hero and the root created
one, so the bloom painted at the root's step 3 — after the root background and
*before* every normal-flow descendant, including `<main>`'s own opaque
background, which then covered it.

The fix was not `isolation: isolate`. It was to stop having a positioned element
at all: the gradients are now `<main>`'s background, which makes them full-bleed
by construction and makes horizontal overflow impossible, because nothing is
positioned.

**2. The light theme was unreadable, and every screenshot taken during design
was taken in the dark theme.**

`[data-surface]` pages are dark by design. They were reading `--mc-fg` from the
active theme. In the light theme that is near-black — measured at
`oklch(0.22 0.018 262)` on `rgb(18, 19, 23)`.

The story page from #46F has had this since it shipped. It was never opened in
the light theme, and neither was this one until a measurement forced it. The fix
is one selector list: a permanently dark surface takes the dark palette.

**A theme toggle is a second rendering of every page, and half of it was never
being looked at.**

**3. The required credit was at 1.12:1, and a text-shadow made it look fine.**

The credit sits at the top-right of the Treasury photograph — which is exactly
where the pale stone pediment is, the brightest region in the frame. White text
on it measures **1.12:1**.

It *looked* acceptable in a screenshot, because a `0 1px 2px rgba(0,0,0,.95)`
shadow makes small white text look anchored. The shadow changes the measured
ratio by nothing at all. It is a legibility illusion, and on a legally required
attribution that is the worst place to have one.

Measured by rasterising the actual crop — source image, `object-position`
50%/58%, both overlay gradients — and taking the worst pixel under the text
box. With a scrim: **4.78:1**. The world caption, checked the same way: 5.14:1.

**The scrim is the point, not the number.** Contrast is now a property of the
component instead of a property of the picture, so the next verified photograph
cannot quietly break a legal notice.

### A defect that was not ours

The header overflows horizontally at 768px. Found while measuring the homepage;
confirmed identical on `/rates` and `/calendar`. It is the theme toggle in
`AppShell`, it predates this work, and it was reported rather than fixed — a
shared-shell change touching every route is not something to fold into a
homepage increment because it happened to be noticed there.

### The rule the tests now carry

`worldImagery.test.ts` fails the build if a `verified` photograph has no credit,
no alt, no crop or no reserved dimensions, if a file it names does not exist, if
its alt text contains an economic claim, or if the full notice stops naming an
archive that is still in use. The rights rule stopped being a review habit.

### Lesson

**Three of the four defects in this increment were invisible to the eye and
obvious to a number.** A gradient that does not paint, text that is the wrong
colour in a theme nobody opened, and an attribution that is legible-looking at
1.12:1 — none would have been caught by looking harder at a screenshot, and all
three were caught by computing a value and comparing it to a threshold.

The corollary is uncomfortable: **the parts of a design nobody measures are the
parts that ship broken.** The light theme was not a hard problem. It was an
unasked question.

---

## #48A — the rest of the homepage, and a header that never fitted

**2026-09-23.** A visual-standard pass over everything below the approved
hero. 1,953 tests, typecheck, lint and production build pass. No canonical
data, methodology or licensing rule touched.

### The header overflowed at 768px on every page, and flex-shrink was a red herring

Measured at a 768px viewport, before anything was changed: the header row has
**705px** of usable width and its three children need **762px** — brand 171,
navigation 441, theme-and-menu 102, plus two 24px gaps.

All three children have `flex-shrink: 1`. The obvious question is why nothing
shrank. Because **`min-width: auto` is the default on a flex item**, and no
child can go below its min-content width: six navigation links in a row do not
compress. A shrink factor on an item that cannot shrink is decoration.

Fixed three ways, because any one of them alone is a number that goes stale the
day a fifth world is added:

1. the wordmark tagline waits until `lg` — it is duplicated verbatim in the
   footer, so this costs nothing and frees 75px;
2. `md:gap-x-4` instead of 6, freeing 16 more — needed is now 671 against 705;
3. **the row wraps again at `md`.**

The third is the one that matters. With `flex-nowrap`, an over-long row becomes
document overflow. Without it, the navigation moves to a second line and the
header gets taller. A future world now makes the header grow instead of making
every page scroll sideways.

### Two sections that were one reading

The lede showed the 10-year Treasury yield for 2026-09-18. "Also recorded"
showed the 2-, 5- and 30-year and the real 10-year, for 2026-09-18. Same world,
same date, same source — split by a heading, a horizontal rule and 64px of
padding, as though they were different subjects.

They are now one card: figure and chart on the left, the other maturities as a
rail on the right at `lg` and beneath at every narrower width. Every value,
as-of date, world and evidence link is unchanged.

**What did not merge is the claim.** THE LEDE is chosen by
`homepage_presentation_v1.0`; the rail is what `selection.whatChanged`
returned. Two different selections, so the rail keeps its own heading — demoted
to `h3` because it now sits inside the lede's `h2`. Pouring the five values into
one undifferentiated list would have made the eligibility policy invisible, and
that policy being visible is the reason it exists.

### A preview of six unlabelled dots is not a preview

The featured story's diagram shipped as six dots, six edges and a legend. It
was accurate and it explained nothing.

The names are now an HTML layer positioned over the SVG at the registry's own
percentage coordinates — the same split the story page uses: **visuals are SVG,
anything with a type size is HTML**. A `font-size` inside a `viewBox` shrinks
with the box, which is the identical trap that gave #46D a 48-unit tap target
rendering at 41px.

Underneath it, composed from the registry's own `setBy` field rather than
written by hand, is the line that answers the question without a click: which
two of the six anyone sets, and who sets them. The diagram and that sentence
cannot disagree, because they read the same field.

Measured at 390px: six labels, zero overlaps, none outside the board.

### The lower page: two columns with different jobs

Five sections used to stack full-width with 64px between each, so everything
below the story was a column of headings separated by space. Now:

- **main** — what the economy currently reads (Inflation and Jobs as peer
  cards, side by side from `md`), the one defended cross-world sentence, and
  the questions that explain them;
- **rail** — when the next data lands, and what happens when a figure changes.

At 1440 the two columns came out 848px each without being told to. Document
height fell **4181 → 2850 (−32%)** at 1440 and **4481 → 3869 (−14%)** at 768.

Mobile went the other way: **4792 → 4886 (+94px)**, and that is the honest
result rather than a miss. The labels and the who-sets-what list are new content
the page did not have. A preview that explains itself is worth 94px.

### The repetition I did not remove

`HowTheyRelate` renders "View Inflation →" and "View Jobs →" directly beneath
two cards that already say "Open Inflation →" and "Open Jobs →". It is real
duplication and it was in scope.

It stays, because `docs/product/relate-composition-v1.md` freezes this component
as the composed sentence "plus the two existing CTAs — nothing else". A layout
pass is not the place to reopen a frozen contract, and quietly deleting a CTA
the contract names would be exactly the kind of small, reasonable-looking edit
those contracts exist to stop.

### Lesson

**`flex-shrink: 1` on an item that cannot shrink looks like a fix and is
nothing.** The header had carried a shrink factor on all three children the
whole time it was overflowing. Reading the CSS would have said the row was
allowed to compress; measuring it said the row was 57px too wide. Only one of
those was true, and `min-width: auto` is why.

---

## #48B — the best thing on the page was 1,637px down

**2026-09-23.** Presentation-only polish. 1,961 tests, typecheck, lint and
production build pass.

### The measurement that decided the whole increment

At a 390×844 viewport, the featured story — the interactive network, the one
thing on MacroChipz you can actually play with — began at **1,637px**. Two full
screens down, the second of which is a Treasury chart.

Every previous pass had been measuring the right things about that region:
overflow, tap targets, contrast, clipping. All clean. None of them asked *how
far down the page the best content is*, which turns out to be the question that
mattered.

Constitution §3 says the mortgage-rate misconception is the acquisition wedge.
The page was burying the wedge behind the data.

It now sits at **651px**, entirely inside the first screen, as a compact teaser
between the hero's discovery strip and the chart. The chart moved nowhere and
lost nothing.

### One invitation, not two

`StoryTeaser` renders below `lg`; `FeaturedStory` renders from `lg`. A phone
meets the story once, early; a desktop meets it once, in its editorial
position. The obvious cheap version — render the teaser everywhere and keep the
section too — would have put the same question on the screen twice and been
worse than the problem.

Both are gated in CSS rather than by a JS breakpoint, so the prerendered HTML
carries both and the browser picks. No layout shift, no hydration flash, and
the static page is correct for a crawler at any width.

### Removing a sentence that was true

The desktop preview said "Six actors sit between a Federal Reserve decision and
the rate a lender quotes you. Only two of them are set by anyone at all."
Registry-derived, accurate, guarded by a test.

It sat directly above a diagram that names six actors and a list that shows
exactly two of them being set. It was the caption of a picture that already
said it.

The test that guarded it now asserts the **fact** instead — six nodes, two
`sets` edges, six labels rendered, two rows in the list — and asserts the
sentence is gone. A test that pins prose pins the prose; a test that pins the
fact survives the prose changing.

The count still appears on the mobile teaser, because there is no diagram there
to carry it.

### A rail is narrower than it looks

"Personal Income and Outlays" was wrapping onto two lines under a one-line date
badge. The obvious fix is smaller type in the release row — and it would have
shrunk the type on `/releases` too, which renders the same component and has no
such problem.

So the column widened instead: 19rem → 21.5rem, which gave the name 215px and
one line. **When a shared component looks wrong in one place, suspect the
place.**

### An overflow that wasn't

At 1024 exactly one element reported a right edge past the viewport: a `span`
reading "Why it matters:" inside a release row. It appeared at 1024 and at no
other width, which is the shape of a real breakpoint bug.

It is inside a **closed `<details>`**. Opening all six produced zero
overflowing elements, and `scrollWidth === clientWidth` throughout. A closed
disclosure's subtree can report a box that participates in no layout.

Worth writing down because the instinct — a lone element, at one width, past
the edge — was to go fix it. The check that settled it was cheap: open the
thing and measure again.

### Lesson

**Every audit so far asked whether the page was correct. None asked what was
reachable.** Overflow, hit targets, contrast and clipping are all properties of
a rendered element; "how far must someone scroll before the product shows them
what it is" is a property of the *order*, and no per-element check will ever
surface it.

The number to keep taking is the y-offset of the best thing on the page.

---

## #48C — the badge that covered a node

**2026-09-23.** A presentation-only refinement of the mobile story teaser.
1,963 tests, typecheck, lint and production build pass.

### Two small decisions worth recording

**A frame, not a bigger icon.** The teaser read as a navigation row with a
picture beside it. What changed that was not making the glyph larger — it was
giving it a lit frame. A framed graphic is a thumbnail of somewhere; an
unframed one is decoration on a link. The same signal a video still gives.

**The action badge went to the top-right, and the corner was the whole
question.** Bottom-right is where an action badge goes. It also sits exactly
where the registry puts `mortgage-rate`: x 78, y 92. So the conventional
position covered one of the six nodes in a six-node diagram — on a component
whose entire job is to advertise that diagram.

The glyph is decorative and `aria-hidden`, so nothing was *wrong* in any sense
a test would catch. It was just a worse picture of the thing being advertised.
Moved to the top-right, which the registry leaves empty — nearest node is
`treasury` at y 41.6. Asserted afterwards: 0 of 6 nodes under the badge.

### The height that a layout change gave back

First attempt put the badge at the far right of the strip. Frame 56 + chip 28 +
two gaps took **36px** off the text column, which pushed the meta line from two
lines to three and grew the strip from 133px to 153.

Putting the badge on the frame's corner returned all of it. Same two elements,
same sizes, one fewer thing competing for the same row: **133px at both 390 and
440**, meta back to two lines.

**Space in a flex row is zero-sum, and a decoration placed in the flow bills
the text for it.** Placing it absolutely, on something that already occupies
the row, costs nothing.

### Lesson

Both fixes came from asking what the component is *for* rather than what looks
balanced. The frame, because the teaser advertises an interactive diagram. The
corner, because covering a node of that diagram to decorate the advert defeats
the advert.
