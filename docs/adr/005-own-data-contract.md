# ADR-005: Normalize FRED Data Into Our Own Response Contract

## Status
Accepted

## Context

FRED's raw API responses are provider-specific: two separate endpoints
(`/fred/series` and `/fred/series/observations`), field names like
`realtime_start`/`realtime_end` that reflect FRED's own data-revision
model, observation values encoded as strings, and a missing observation
represented by the literal string `"."`. `GET /api/v1/series/{series_id}`
needed to decide whether to pass this shape through to API consumers or
define something else.

## Decision

Define the application's own response models — `Observation` and
`SeriesResponse` in `app/models/series.py` — and always return those.
Raw FRED JSON is never returned to an API consumer; `FREDClient` (the only
code that sees FRED's raw shape) hands off plain dicts to
`EconomicDataService`, which is the only code that constructs the
application's models from them.

## Alternatives Considered

- **Pass through FRED's raw JSON response(s) directly.** Rejected: it
  would make this API's contract identical to FRED's, including FRED's
  irrelevant-to-us fields (`realtime_start`, `output_type`, etc.), its
  string-typed numeric values, and its `"."` missing-value convention —
  all of which are FRED implementation details, not something this API's
  consumers should need to know about.
- **Pass through with light field renaming only**, without real type
  normalization (e.g. still leaving `value` as a string). Rejected: it
  would still leak the `"."` missing-value convention and string-typed
  numbers into the contract, just under different key names.

## Why This Decision

This API's consumers should be able to rely on a stable, predictable shape
regardless of which upstream provided the data or how that provider
happens to encode it. Concretely, in the current implementation:
`Observation.value` is a proper `float | None` (not a string that might be
`"."`), and the two separate FRED requests (metadata + observations) are
merged into one coherent `SeriesResponse`. A consumer of this API should
never need to know FRED represents a missing month as `"."`, or that the
title came from a different HTTP call than the numbers did.

This also establishes the project's data model as the one that's allowed
to grow with the project's own needs (e.g. eventually merging in a second
provider's data under the same `SeriesResponse` shape) rather than being
permanently downstream of whatever shape one specific provider happens to
use today.

## Consequences / Tradeoffs

- Gains: provider independence — consumers of this API are insulated from
  FRED-specific quirks and from any future change in how FRED shapes its
  responses (within reason; a genuinely new FRED field would still need a
  deliberate decision to surface it). A second data provider could, in
  principle, be normalized into the same `SeriesResponse` shape.
- Cost: this project now owns the transformation and must maintain it.
  Every FRED field this API wants to expose has to be explicitly mapped in
  `EconomicDataService`; nothing is exposed "for free" by pass-through.
  Bugs in that mapping (e.g. missing a `KeyError` case) are this project's
  bugs, not FRED's — Increment 002 addresses this by catching
  `KeyError`/`TypeError`/`ValueError` during normalization and raising
  `FREDUpstreamError` rather than letting a malformed upstream response
  turn into an unhandled 500.

## Revisit When

- The normalized contract is found to be dropping information API
  consumers actually need from FRED — at that point, extend
  `SeriesResponse`/`Observation` deliberately (not by falling back to
  passing raw FRED data through).
- A second data provider is added and its data needs to fit the same
  contract — that's the real test of whether `SeriesResponse`'s current
  shape is provider-agnostic enough, or needs adjustment.
