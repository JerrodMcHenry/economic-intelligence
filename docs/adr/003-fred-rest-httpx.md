# ADR-003: Direct FRED REST Integration via Synchronous `httpx`

## Status
Accepted

## Context

Increment 002 added the project's first external data integration: the
Federal Reserve Economic Data (FRED) API, exposed to consumers as
`GET /api/v1/series/{series_id}`. Three related choices had to be made:
how to talk to FRED (SDK vs. direct REST), which HTTP client library to
use, and whether that client should be synchronous or asynchronous.

## Decision

- Call the **FRED REST API directly** over HTTP — no third-party FRED SDK.
- Use **`httpx`** as the HTTP client library.
- Use `httpx` **synchronously** (`httpx.Client`, blocking calls) for this
  increment, not `async`/`await`.

## Alternatives Considered

- **A third-party FRED Python SDK.** Rejected: it would own request
  construction, error shapes, and response parsing, all outside this
  project's control. This project specifically wants to decide how FRED
  errors get translated into its own exception types (see
  `app/clients/fred.py` and [ADR-005](005-own-data-contract.md)) — an SDK's
  own abstraction would sit in the way of that, not help it.
- **`requests`** instead of `httpx`. Rejected only for lack of a reason to
  prefer it: `requests` is sync-only, while `httpx` offers the same
  ergonomics with an async-capable API available under the same library if
  a later increment needs it — no migration required, just a different
  client class.
- **`async def` routes and an async FRED client from the start**, since
  FastAPI supports it natively. Rejected for *this* increment: there is no
  concurrency requirement yet — one request handles one external call
  chain (series metadata + observations), sequentially, and nothing is
  fanning out across multiple providers or handling volume that would
  benefit from non-blocking I/O. Adding `async`/`await` throughout the
  client and service layers now would be complexity introduced ahead of
  any actual need for it.

## Why This Decision

Direct REST integration keeps the failure-handling and normalization logic
fully within this project's control and visible in one file
(`app/clients/fred.py`), which matters because FRED's error responses are
genuinely quirky (see [current-architecture.md](../architecture/current-architecture.md)
and the journal) — both "series not found" and "bad API key" arrive as
HTTP 400, distinguished only by message text. That's exactly the kind of
detail worth owning directly rather than trusting a dependency to have
handled "correctly."

`httpx` was chosen over `requests` specifically because it doesn't close
the door on async later — the sync-first decision is about *when* to pay
for async complexity, not a bet against ever needing it.

## Consequences / Tradeoffs

- Gains: full control over timeout behavior, retry (currently: none —
  failures surface immediately as typed exceptions rather than being
  silently retried), and error translation. No SDK version-compatibility
  surface to track.
- Gains: staying synchronous keeps `FREDClient` and `EconomicDataService`
  simple to read and reason about — no `await` propagation, no event-loop
  considerations.
- Cost: synchronous HTTP calls block the worker thread/process handling
  that request for the duration of the FRED round-trip. Under concurrent
  load this does not scale as well as a non-blocking implementation would.
  This is an accepted, explicit tradeoff for the current, low-volume stage
  of the project — not an oversight.
- Cost: some request/response boilerplate that an SDK might have provided
  (e.g. typed request builders) is instead hand-written in `FREDClient`.

## Revisit When

- A concurrency or throughput requirement actually materializes (e.g.
  multiple external providers queried per request, or meaningful request
  volume where blocking I/O becomes a measured bottleneck) — at that point,
  migrate `FREDClient` and the routes that use it to `async`/`await` using
  `httpx.AsyncClient`, which requires no library change, only a usage
  change.
- FRED's API surface grows enough (many more endpoints used) that
  hand-written request handling becomes meaningfully more work than
  adopting a well-maintained SDK would be.
