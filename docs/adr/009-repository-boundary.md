# ADR-009: A Small, Concrete Repository Boundary — Not a Generic Framework

## Status
Accepted

## Context

Once `EconomicDataService` needed to persist data as well as fetch it from
FRED, something had to own the actual SQL/ORM operations against
`economic_series` and `economic_observations`. The same judgment call
[ADR-004](004-route-service-client.md) made for the FRED client — introduce
a layer only where it has a real, distinct responsibility — applied again
here, now with an added temptation: persistence code invites generic
"Repository pattern" abstractions (an abstract base repository, a generic
`Repository[T]`, a Unit-of-Work class) that many codebases reach for by
default.

## Decision

Introduce exactly one concrete class, `SeriesRepository`
(`app/repositories/series_repository.py`), with exactly one real
operation: `save_series(data: SeriesResponse) -> EconomicSeries`, which
upserts a series and its observations. It takes a `Session` the caller
already has open and never calls `commit()`/`rollback()` itself. No
abstract base repository, no generic `Repository[T]`, no separate
interface/implementation split.

## Alternatives Considered

- **SQL/ORM calls directly inside `EconomicDataService`.** Would have
  worked for this single use case, but mixes "what does syncing a series
  mean" (use-case logic) with "how do I query/upsert these two tables"
  (persistence mechanics) in one place — the same reasoning
  [ADR-004](004-route-service-client.md) already applied to keep FRED's
  HTTP mechanics out of the service.
- **A generic repository abstraction** — an abstract base class or
  `Protocol` defining repository methods, meant to be reused by future
  repositories. Rejected: there is exactly one repository in this
  codebase. A shared abstraction designed for a second implementation
  that doesn't exist yet is a guess at what that future repository will
  need, made before any real second case exists to inform it — the same
  premature-abstraction trap named directly in the project's engineering
  rules ("do not create abstract base repositories merely for
  architectural appearance").
- **A Unit-of-Work class wrapping the session.** SQLAlchemy's `Session`
  already *is* a unit of work (it tracks pending changes and flushes them
  together); wrapping it in another layer would duplicate that without
  adding a capability this increment needs.

## Why This Decision

`SeriesRepository` exists because it has one real, distinct job — SQL and
ORM query construction for two specific tables — that doesn't belong in
the service (business logic) or the route (HTTP concerns). It stays
commit-free by design: the caller (`app/api/series.py`, via
`session_scope()`) is the one place that owns "does this whole operation
succeed or fail as a unit," and a repository method that committed on its
own would make that boundary ambiguous — is *this* commit the end of the
transaction, or does more work happen after it? Keeping the answer
"the repository never decides" removes that ambiguity entirely.

## Consequences / Tradeoffs

- Gains: SQL/ORM logic lives in exactly one place, is easy to find, and
  the transaction boundary is unambiguous — one `session_scope()` per
  logical operation, always owned by the caller. Testable in isolation by
  passing it a real (or test) `Session` directly, as done during this
  increment's rollback verification.
- Cost: no shared repository interface exists to swap in a fake/mock
  implementation behind a common type — acceptable because there is only
  one concrete need today; adding that flexibility now would be
  speculative.

## Revisit When

- A second repository is actually needed (a second entity with its own
  persistence needs) — that's the point to look at what the two
  repositories genuinely have in common, if anything, and extract a
  shared abstraction from *real* duplication rather than a guessed one.
- `SeriesRepository` itself grows enough distinct operations that its
  single-class, single-responsibility shape starts to strain — not the
  case today (`save_series` is its only real operation).
