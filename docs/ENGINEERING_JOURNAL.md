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
