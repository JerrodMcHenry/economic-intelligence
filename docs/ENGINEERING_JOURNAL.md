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
