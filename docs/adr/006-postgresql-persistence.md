# ADR-006: PostgreSQL for Persistence

## Status
Accepted

## Context

Increment 003 needed to introduce durable storage for normalized economic
series and their observations — until now, every request re-fetched from
FRED live and nothing was ever stored. A database technology had to be
chosen, along with a relational model for the domain: one series has many
observations, and duplicate observations for the same series/date should
be impossible rather than just discouraged by convention.

## Decision

Use **PostgreSQL**, with two tables — `economic_series` and
`economic_observations` — related by a foreign key, and a database-level
`UNIQUE(economic_series_id, observation_date)` constraint enforcing
uniqueness.

## Alternatives Considered

- **SQLite.** Simple, file-based, zero setup. Rejected because it doesn't
  reflect how this system would actually run in production (a separate
  database process, concurrent connections, a real connection pool) —
  experience with those is one of this project's explicit goals — and
  because reaching for "the easy embedded option" would be picking a
  technology to avoid setup cost rather than because it fits the data.
- **A document store (e.g. MongoDB).** The natural document shape here —
  a series document with an embedded array of observations — makes
  enforcing "no duplicate date" and doing partial updates ("just this one
  observation changed") awkward compared to a relational unique
  constraint and a targeted `UPDATE`. The alternative document shape (one
  document per observation, with a series ID field standing in for a
  foreign key) reimplements a foreign key without the database enforcing
  referential integrity.
- **A key-value store (e.g. DynamoDB).** Would push relational access
  patterns (e.g. "all observations for a series in a date range") into
  application-side filtering instead of letting the database index and
  query for them directly. No requirement in this project favors
  key-value access patterns over relational ones.

## Why This Decision

The domain is genuinely, unambiguously relational — a fixed one-to-many
structure with a real uniqueness rule the database should enforce, not
something application code re-checks by convention. PostgreSQL also gives
this project hands-on, production-relevant experience — relational
modeling, constraints, indexes, transactions, and (via
[ADR-008](008-alembic-migrations.md)) version-controlled schema
migrations — that a simpler embedded database or a schema-flexible store
wouldn't have required, which matters for a project whose explicit purpose
includes demonstrating that experience.

## Consequences / Tradeoffs

- Gains: real referential integrity (`ON DELETE CASCADE` from series to
  its observations) and a real uniqueness guarantee at the database level,
  not just in application logic. A separate database process to run,
  connect to, and reason about — closer to a real deployment than an
  embedded file would be.
- Cost: requires a running PostgreSQL instance for local development and
  any future deployment — more setup than SQLite would have needed.
  Schema changes now require a deliberate migration step (see
  [ADR-008](008-alembic-migrations.md)) rather than just editing a model
  class.

## Revisit When

- A workload emerges that's genuinely better served by a different storage
  model (e.g. large-scale unstructured document storage, or a caching
  layer with different consistency needs) — evaluate that workload
  specifically rather than replacing PostgreSQL wholesale; it's likely to
  sit *alongside* PostgreSQL rather than instead of it.
- Read volume or query patterns against this data change enough to need
  read replicas, partitioning, or similar — none of that is warranted at
  this scale today.
