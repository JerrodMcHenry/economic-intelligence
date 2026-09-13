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
