# ADR-007: SQLAlchemy 2.x, Used Synchronously

## Status
Accepted

## Context

Increment 003 needed a way to map the application's normalized data onto
PostgreSQL tables and execute queries/writes against them. A database
toolkit had to be chosen, along with whether database access would be
synchronous or asynchronous — the same synchronous-vs-async question
[ADR-003](003-fred-rest-httpx.md) already answered for the FRED HTTP
client.

## Decision

Use **SQLAlchemy 2.x**, with its modern declarative/typed API
(`DeclarativeBase`, `Mapped[...]`, `mapped_column(...)`) — not the legacy
`Column`/`declarative_base()` style from SQLAlchemy 1.x. Use it
**synchronously**: a plain `Session` bound to a plain (non-async) `Engine`
via `psycopg` (v3) as the driver, not `asyncpg`/`AsyncSession`.

## Alternatives Considered

- **Legacy SQLAlchemy 1.x query/declarative patterns**, still common in
  tutorials and older codebases. Rejected: SQLAlchemy 2.x's typed
  `Mapped[...]` style makes the ORM models' Python types match their
  database types explicitly and checkably (e.g. `Mapped[float | None]`
  mirrors the column's nullability), and is the actively maintained,
  forward-looking API — there's no reason to adopt the older pattern on a
  brand-new codebase.
- **A raw SQL / query-builder approach without an ORM** (e.g. hand-written
  SQL strings, or a lighter query builder). Would keep generated SQL
  maximally transparent, but ORM relationship/session machinery
  (`relationship()`, unit-of-work change tracking) is genuinely useful
  for exactly this shape of problem — an entity with related child rows
  that need to be inserted/updated together in one transaction — and
  SQLAlchemy 2.x's ORM doesn't hide the generated SQL from view when it
  needs inspecting.
- **Async SQLAlchemy** (`AsyncSession`, `asyncpg` or the async mode of
  `psycopg`). Rejected for the same reason async wasn't adopted for the
  FRED client: there's no concurrency requirement yet that justifies it.
  A route handling one sync request performs one sequential unit of work
  (fetch from FRED, then a handful of sequential database statements) —
  nothing here is waiting on multiple independent I/O operations at once
  in a way `async` would meaningfully help with today.

## Why This Decision

SQLAlchemy 2.x's typed style keeps the relational model's types visible
and checkable directly in the model class, which matters for a project
that wants "the relational model and generated SQL behavior to remain
understandable" rather than hidden behind heavy abstraction. Staying
synchronous keeps the database layer as simple to read and reason about
as the FRED client already is — no `await` propagation through the
route → service → repository chain, no event-loop considerations mixed
into database session management — while `psycopg` (the modern,
maintained PostgreSQL driver, chosen over the older `psycopg2`) still
leaves the door open to `AsyncSession` later without a driver change,
since `psycopg` supports both modes.

## Consequences / Tradeoffs

- Gains: ORM relationship and session/unit-of-work support for genuinely
  related data, typed model definitions that double as documentation of
  the schema, and a database layer that reads linearly (no `await`) and
  matches the synchronous FRED client already in the codebase.
- Cost: a synchronous database call blocks the worker handling that
  request for its duration, same tradeoff already accepted for FRED calls
  in ADR-003 — not a new cost introduced by this decision, but compounded
  by it (one request's worker is now blocked for the FRED round-trip
  *and* the database round-trip, sequentially).

## Revisit When

- The same concurrency/throughput trigger named in
  [ADR-003](003-fred-rest-httpx.md) actually materializes — at that point,
  the database layer and the FRED client should very likely move to async
  together, since a request that's `async` end-to-end but blocking at the
  database layer (or vice versa) gets little of the benefit.
