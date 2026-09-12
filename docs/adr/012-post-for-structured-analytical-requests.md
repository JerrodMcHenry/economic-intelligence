# ADR-012: POST for a Structured, Read-Only Analytical Request

## Status
Accepted

## Context

Increment 007 needed an endpoint accepting a genuinely structured
request: two series, each with an optional transformation (a type and,
for one transformation, a window), plus a requested analysis and an
optional date range. Every prior endpoint in this project used `GET`
with query parameters, consistent with each one performing no writes.
This new request shape didn't fit that pattern cleanly, and a decision
was needed on how to accept it without either mutating anything or
misusing HTTP method semantics.

## Decision

Use `POST /api/v1/analysis/pipeline`, accepting the structured
specification as a JSON request body, while performing **no database
writes at all** — `POST` here means "execute this analysis
specification," never "create a resource."

## Alternatives Considered

- **`GET` with many query parameters** (e.g.
  `?series_a_id=...&series_a_transformation=...&series_a_window=...&series_b_id=...&...`).
  Rejected: nesting "each series has an id and an optional
  type+window" into flat query parameters loses the natural grouping a
  JSON body gives for free, makes an already non-trivial parameter set
  (this project's most parameter-heavy `GET`, `.../observations`, has
  five) harder to read and to validate as a unit, and doesn't extend
  cleanly if a future increment needs to nest further (e.g. per-side date
  overrides).
- **`GET` with a request body.** Not a real option: `GET` requests are
  not guaranteed to carry a body through every part of the HTTP stack
  (proxies, some clients, caching layers may drop or ignore it), and
  FastAPI's own idioms don't encourage it. Choosing `GET`-with-body would
  have traded a real, well-known interoperability risk for staying
  nominally "read-only" in name only.
- **`POST` that also persists the pipeline's inputs or results** (e.g.
  logging the request, caching the computed result). Rejected as scope
  the prompt explicitly excluded — see
  [ADR-010](010-pure-transformation-engine.md)'s reasoning for why
  derived results aren't persisted; a pipeline result is exactly as
  reproducible as a single transformation's, for the same reasons.

## Why This Decision

`POST`'s defining property that actually matters here isn't "this creates
something" — it's "the client submits a body FastAPI/Pydantic can
validate as one structured unit." That property is genuinely useful for
this request shape and isn't available from `GET`. Nothing about using
`POST` implies mutation on its own; what determines whether an endpoint
mutates is whether its handler writes to the database, and this one
verifiably doesn't (confirmed directly — see the journal's Verification
section: row counts and timestamps compared before/after, identical).
The docstring on the route and this ADR both say so explicitly, so the
method choice is never left to imply something the implementation
doesn't do.

## Consequences / Tradeoffs

- Gains: the request body models the two-series-plus-transformations
  shape naturally and gets full Pydantic structural validation (nested
  field types, `window`'s numeric bounds) the same way every other
  request in this project is validated — no special-cased query-parameter
  parsing for a shape query parameters don't fit well.
- Cost: `POST` conventionally signals resource creation or mutation to
  someone skimming the API surface, and this endpoint deliberately
  doesn't fit that convention — it's `POST` for its request-body
  properties, not its semantics. This project accepts that departure
  explicitly (documented in the route's own docstring, this ADR, and the
  journal) rather than either forcing an awkward `GET`, or letting the
  method choice quietly misrepresent what the endpoint does.
- Cost: unlike every `GET` endpoint in this project, a caller can't
  simply paste a URL to invoke this one (a request body is required) —
  acceptable for a structured analytical specification, less so for
  something meant to be casually shareable as a link.

## Revisit When

- A future increment needs another endpoint with a comparably structured,
  multi-field, genuinely read-only request — this ADR's reasoning should
  apply directly rather than being re-litigated from scratch each time.
- If GraphQL-style or RPC-style request patterns are ever adopted
  elsewhere in this project, revisit whether `POST`-for-structured-reads
  is still the most consistent choice, or whether a dedicated query
  mechanism would serve this and future similar endpoints better.
